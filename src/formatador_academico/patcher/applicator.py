"""Patcher v0.1 — execution orchestration (decision 0028).

    apply_cleared_operation(package_snapshot, cleared_operation) -> PatchResult

Execution preconditions are enforced IN THIS ORDER, before any mutation:

1. API contract: bytes + GateClearedOperation (never a raw PlannedOperation);
2. snapshot fingerprint: sha256(snapshot) == token.current_package_sha256,
   otherwise ordinary rejection `snapshot_hash_mismatch` with no output;
3. executable slice: SET_PROPERTY on run/P1/bold or run/P2/font_size,
   otherwise ordinary rejection `unsupported_operation`;
4. target resolution via parser_api.resolve_structural_path on the real
   tree of the gated snapshot — drift after a matching snapshot is a
   fail-fast PatcherIntegrityError, never a rejection;
5. physical identity: recomputed parser physical_hash must equal the
   operation's target hash, otherwise PatcherIntegrityError.

Only after every validation (allowed-delta on relread bytes, package scope,
semantic postcondition) may a result become `applied` (atomicity, §5/§19).

The token type is NOT treated as proof that SafetyGate ran: everything above
is revalidated here (decision 0028 §1, adversarial finding I2).
"""

from __future__ import annotations

import hashlib

from ..docx_parser import DOCUMENT_XML
from ..operation_plan.model import OperationKind
from ..safety_gate.model import GateClearedOperation
from .. import parser_api
from .document import parse_document_xml, serialize_document_xml
from .model import (
    PATCHER_VERSION,
    PatchReason,
    PatchResult,
    PatchStatus,
    PatcherContractError,
    PatcherIntegrityError,
)
from .package import read_package_parts, repackage, verify_package_scope
from .validation import relread_document_xml, validate_allowed_delta, verify_postcondition
from .xml_patch import Reject, W_R, mutate_run

_EXECUTABLE_SLICE = frozenset({("run", "P1", "bold"), ("run", "P2", "font_size")})


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def apply_cleared_operation(
    package_snapshot: bytes,
    cleared_operation: GateClearedOperation,
) -> PatchResult:
    """Apply exactly one GateClearedOperation to the exact gated snapshot."""

    if not isinstance(package_snapshot, bytes):
        raise PatcherContractError("package_snapshot must be bytes")
    if not isinstance(cleared_operation, GateClearedOperation):
        raise PatcherContractError(
            "the patcher accepts only GateClearedOperation; a raw PlannedOperation "
            "is never an executable input"
        )

    operation = cleared_operation.operation
    input_sha = _sha256(package_snapshot)

    def rejected(reason: PatchReason) -> PatchResult:
        return PatchResult(
            patcher_version=PATCHER_VERSION,
            status=PatchStatus.REJECTED,
            operation_ref=cleared_operation.operation_ref,
            operation_plan_ref=cleared_operation.operation_plan_ref,
            input_package_sha256=input_sha,
            output_package_sha256=None,
            output_package_bytes=None,
            reason=reason,
            changed_part=None,
        )

    # Step 2 — snapshot/TOCTOU precondition, before opening any XML.
    if input_sha != cleared_operation.current_package_sha256:
        return rejected(PatchReason.SNAPSHOT_HASH_MISMATCH)

    # Step 3 — v0.1 executable slice.
    key = operation.key
    if (
        operation.kind is not OperationKind.SET_PROPERTY
        or (key.target_type, key.aspect_id, key.property_slot) not in _EXECUTABLE_SLICE
        or operation.target.target_type != "run"
    ):
        return rejected(PatchReason.UNSUPPORTED_OPERATION)

    try:
        infos, payloads, archive_comment = read_package_parts(package_snapshot)
        document_xml = payloads.get(DOCUMENT_XML)
        if document_xml is None:
            raise PatcherIntegrityError(
                "snapshot matched but word/document.xml is missing from the package"
            )
        tree = parse_document_xml(document_xml, DOCUMENT_XML)

        # Step 4 — dedicated inverse-walk resolution, never XPath.
        try:
            target = parser_api.resolve_structural_path(
                tree.getroot(), operation.target.structural_path
            )
        except parser_api.StructuralPathError as exc:
            raise PatcherIntegrityError(
                f"snapshot matched but target path does not resolve: {exc}"
            ) from exc
        if not isinstance(target.tag, str) or target.tag != W_R:
            raise PatcherIntegrityError(
                "snapshot matched but the resolved target is not a w:r"
            )

        # Step 5 — mandatory physical identity recheck (parser semantics).
        canonical = parser_api.canonical_xml(target)
        recomputed = parser_api.physical_hash(
            canonical, parser_api.inherited_xml_attrs(target)
        )
        if recomputed != operation.target.physical_hash:
            raise PatcherIntegrityError(
                "snapshot matched but the recomputed target physical_hash diverges"
            )

        # Mutation (ordinary shape rejections surface as PatchResult).
        mutate_run(target, key.property_slot, operation.desired_value)
    except Reject as exc:
        return rejected(exc.reason)

    new_document_xml = serialize_document_xml(tree, document_xml)
    output_bytes = repackage(infos, payloads, archive_comment, new_document_xml)

    # Fail-fast postconditions on RELREAD bytes; no partial output escapes.
    verify_package_scope(package_snapshot, output_bytes)
    validate_allowed_delta(
        document_xml,
        relread_document_xml(output_bytes),
        operation.target.structural_path,
        key.property_slot,
        operation.desired_value,
    )
    verify_postcondition(output_bytes, operation)

    return PatchResult(
        patcher_version=PATCHER_VERSION,
        status=PatchStatus.APPLIED,
        operation_ref=cleared_operation.operation_ref,
        operation_plan_ref=cleared_operation.operation_plan_ref,
        input_package_sha256=input_sha,
        output_package_sha256=_sha256(output_bytes),
        output_package_bytes=output_bytes,
        reason=None,
        changed_part=DOCUMENT_XML,
    )
