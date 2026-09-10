"""Review/Highlight DOCX v0.1 builder (decision 0036)."""
from __future__ import annotations

import hashlib
from collections import OrderedDict

from lxml import etree

from .. import parser_api
from ..docx_parser import DocxParser, PARSER_VERSION, W_NS
from ..patcher.document import parse_document_xml, serialize_document_xml
from ..patcher.model import PatcherContractError, PatcherIntegrityError
from ..patcher.package import read_package_parts, repackage, verify_package_scope
from ..patcher.validation import relread_document_xml
from ..patcher.xml_patch import MC_ALTERNATE_CONTENT, RPR_CANONICAL_RANK, W_P, W_R, W_RPR
from ..safety_gate.targets import find_story, resolve_target
from ..processing_report import (
    PROCESSING_REPORT_VERSION,
    AppliedChangeItem,
    ProcessingReport,
    ReviewItem,
    UnappliedChangeItem,
    processing_report_ref,
)
from .model import (
    DOCUMENT_PART,
    REVIEW_DOCX_VERSION,
    ReviewDocxContractError,
    ReviewDocxIntegrityError,
    ReviewDocxResult,
    ReviewMarkReason,
    ReviewMarkResult,
    ReviewMarkStatus,
)
from .validation import validate_allowed_delta

W_HIGHLIGHT = f"{{{W_NS}}}highlight"
W_VAL = f"{{{W_NS}}}val"
W_T = f"{{{W_NS}}}t"
W_SYM = f"{{{W_NS}}}sym"
W_TAB = f"{{{W_NS}}}tab"
W_BR = f"{{{W_NS}}}br"
W_DELTEXT = f"{{{W_NS}}}delText"
W_DEL = f"{{{W_NS}}}del"

_SOURCE_ORDER = ("applied_change", "unapplied_change", "review_item")


def _direct(node: etree._Element, tag: str) -> list[etree._Element]:
    return [c for c in node if isinstance(c.tag, str) and c.tag == tag]


def _physical_hash(node: etree._Element) -> str:
    return parser_api.physical_hash(
        parser_api.canonical_xml(node), parser_api.inherited_xml_attrs(node)
    )


def _is_under_deleted_revision(run: etree._Element) -> bool:
    node = run.getparent()
    while node is not None:
        if isinstance(node.tag, str) and node.tag == W_DEL:
            return True
        node = node.getparent()
    return False


def _has_visual_surface(run: etree._Element) -> bool:
    for child in run:
        if not isinstance(child.tag, str):
            continue
        if child.tag == W_T and (child.text or ""):
            return True
        if child.tag in {W_SYM, W_TAB, W_BR}:
            return True
    return False


def _validate_rpr_for_review(run: etree._Element) -> etree._Element | None:
    rprs = _direct(run, W_RPR)
    if len(rprs) > 1:
        return None
    if not rprs:
        return None
    rpr = rprs[0]
    first_element = next((c for c in run if isinstance(c.tag, str)), None)
    if first_element is not rpr:
        raise ValueError("noncanonical")
    if _direct(rpr, MC_ALTERNATE_CONTENT):
        raise ValueError("noncanonical")

    known_ranks: list[int] = []
    for child in rpr:
        if not isinstance(child.tag, str):
            continue
        if child.tag.startswith(f"{{{W_NS}}}"):
            rank = RPR_CANONICAL_RANK.get(child.tag)
            if rank is None:
                raise ValueError("noncanonical")
            known_ranks.append(rank)
    if known_ranks != sorted(known_ranks):
        raise ValueError("noncanonical")
    return rpr


def _ensure_rpr(run: etree._Element, rpr: etree._Element | None) -> etree._Element:
    if rpr is not None:
        return rpr
    new = etree.Element(W_RPR)
    run.insert(0, new)
    return new


def _insert_highlight(rpr: etree._Element) -> None:
    element = etree.Element(W_HIGHLIGHT)
    element.set(W_VAL, "yellow")
    target_rank = RPR_CANONICAL_RANK[W_HIGHLIGHT]
    for child in rpr:
        if not isinstance(child.tag, str):
            continue
        rank = RPR_CANONICAL_RANK.get(child.tag)
        if rank is not None and rank > target_rank:
            child.addprevious(element)
            return
    rpr.append(element)


def _candidate_groups(report: ProcessingReport):
    yield "applied_change", report.applied_changes
    yield "unapplied_change", report.unapplied_changes
    yield "review_item", report.review_items


def _collect_candidates(report: ProcessingReport):
    candidates: OrderedDict[tuple[str, str], dict] = OrderedDict()
    for source_kind, group in _candidate_groups(report):
        for item in group:
            target = item.target
            if target.target_type not in {"run", "paragraph"}:
                raise ReviewDocxIntegrityError(
                    f"v0.1 report item {source_kind} unexpectedly targets {target.target_type!r}"
                )
            key = (target.target_type, target.structural_path)
            entry = candidates.setdefault(
                key,
                {"path": target.structural_path, "items": [], "source_kinds": set()},
            )
            entry["items"].append(item)
            entry["source_kinds"].add(source_kind)
    return tuple(candidates.values())


def _validate_item_binding(item, final_hash: str) -> None:
    if isinstance(item, AppliedChangeItem):
        if item.changed_part != DOCUMENT_PART:
            raise ReviewDocxIntegrityError("AppliedChangeItem changed_part is outside the document part")
        if item.target.target_type == "run":
            if item.target.property_slot not in {"bold", "font_size"}:
                raise ReviewDocxIntegrityError("AppliedChangeItem is outside frozen P1/P2 premises")
        elif item.target.target_type == "paragraph":
            if item.target.property_slot != "alignment":
                raise ReviewDocxIntegrityError("AppliedChangeItem is outside frozen P4 premises")
        else:
            raise ReviewDocxIntegrityError("AppliedChangeItem target type is unsupported")
        return
    if isinstance(item, (UnappliedChangeItem, ReviewItem)):
        if item.target.physical_hash != final_hash:
            raise ReviewDocxIntegrityError(
                "final-snapshot report item physical_hash mismatch"
            )
        return
    raise ReviewDocxIntegrityError(
        f"unsupported candidate item type: {type(item).__name__}"
    )


def _ordinary_reason(
    run: etree._Element,
) -> tuple[ReviewMarkReason | None, etree._Element | None]:
    if _is_under_deleted_revision(run) or _direct(run, W_DELTEXT):
        return ReviewMarkReason.PROTECTED_REVISION_RUN, None
    rprs = _direct(run, W_RPR)
    if len(rprs) == 1 and _direct(rprs[0], W_HIGHLIGHT):
        return ReviewMarkReason.EXISTING_HIGHLIGHT, None
    try:
        rpr = _validate_rpr_for_review(run)
    except ValueError:
        return ReviewMarkReason.NONCANONICAL_RUN_PROPERTIES, None
    if len(rprs) > 1:
        return ReviewMarkReason.NONCANONICAL_RUN_PROPERTIES, None
    if not _has_visual_surface(run):
        return ReviewMarkReason.NO_VISUAL_SURFACE, None
    return None, rpr


def build_review_docx(
    clean_package_snapshot: bytes,
    processing_report: ProcessingReport,
) -> ReviewDocxResult:
    if not isinstance(clean_package_snapshot, bytes):
        raise ReviewDocxContractError("clean_package_snapshot must be bytes")
    if not isinstance(processing_report, ProcessingReport):
        raise ReviewDocxContractError("processing_report must be ProcessingReport")
    if processing_report.processing_report_version != PROCESSING_REPORT_VERSION:
        raise ReviewDocxContractError("unsupported ProcessingReport version")

    input_sha = hashlib.sha256(clean_package_snapshot).hexdigest()
    if input_sha != processing_report.summary.output_package_sha256:
        raise ReviewDocxIntegrityError(
            "clean snapshot SHA does not match ProcessingReport output SHA"
        )

    candidates = _collect_candidates(processing_report)
    if not candidates:
        return ReviewDocxResult(
            REVIEW_DOCX_VERSION,
            PARSER_VERSION,
            PROCESSING_REPORT_VERSION,
            processing_report_ref(processing_report),
            DOCUMENT_PART,
            input_sha,
            input_sha,
            clean_package_snapshot,
            (),
            len(processing_report.classification_items),
        )

    try:
        infos, payloads, archive_comment = read_package_parts(clean_package_snapshot)
        before_xml = payloads[DOCUMENT_PART]
        tree = parse_document_xml(before_xml, DOCUMENT_PART)
        physical_ir = DocxParser().parse_bytes(clean_package_snapshot)
        if physical_ir.get("status") != "ok":
            raise ReviewDocxIntegrityError("clean package did not produce usable PhysicalIR")
        physical_story = find_story(physical_ir, DOCUMENT_PART)
    except (KeyError, PatcherContractError, PatcherIntegrityError) as exc:
        raise ReviewDocxIntegrityError(
            f"unable to open clean package safely: {exc}"
        ) from exc

    root = tree.getroot()
    results: list[ReviewMarkResult] = []
    marked_paths: list[str] = []

    for candidate in candidates:
        path = candidate["path"]
        source_kinds = tuple(
            x for x in _SOURCE_ORDER if x in candidate["source_kinds"]
        )
        try:
            target = parser_api.resolve_structural_path(root, path)
        except parser_api.StructuralPathError as exc:
            raise ReviewDocxIntegrityError(
                f"report target path does not resolve: {path}: {exc}"
            ) from exc
        final_hash = _physical_hash(target)
        for item in candidate["items"]:
            _validate_item_binding(item, final_hash)

        if target.tag == W_P:
            paragraph_matches = resolve_target(physical_story, path)
            if len(paragraph_matches) != 1:
                raise ReviewDocxIntegrityError(
                    f"report paragraph target does not resolve uniquely: {path}"
                )
            paragraph_record, _ = paragraph_matches[0]
            run_records = []

            def collect_runs(records):
                for record in records or ():
                    if not isinstance(record, dict):
                        continue
                    if record.get("source_type") == "run_raw":
                        run_records.append(record)
                        continue
                    children = record.get("children")
                    if isinstance(children, list):
                        collect_runs(children)

            collect_runs(paragraph_record.get("children"))
            selected_run = None
            selected_rpr = None
            selected_reason = None
            for run_record in run_records:
                run_path = run_record.get("structural_path")
                if not isinstance(run_path, str):
                    continue
                try:
                    run = parser_api.resolve_structural_path(root, run_path)
                except parser_api.StructuralPathError as exc:
                    raise ReviewDocxIntegrityError(
                        f"paragraph run target path does not resolve: {run_path}: {exc}"
                    ) from exc
                reason, rpr = _ordinary_reason(run)
                if reason is None:
                    selected_run = run
                    selected_rpr = rpr
                    selected_reason = None
                    selected_run_path = run_path
                    break
                selected_reason = reason

            if selected_run is None:
                results.append(
                    ReviewMarkResult(
                        "paragraph",
                        path,
                        final_hash,
                        ReviewMarkStatus.UNMARKED,
                        ReviewMarkReason.NO_MARKABLE_RUN,
                        source_kinds,
                    )
                )
                continue

            selected_rpr = _ensure_rpr(selected_run, selected_rpr)
            _insert_highlight(selected_rpr)
            marked_paths.append(selected_run_path)
            results.append(
                ReviewMarkResult(
                    "paragraph",
                    path,
                    final_hash,
                    ReviewMarkStatus.MARKED,
                    None,
                    source_kinds,
                )
            )
            continue

        if target.tag != W_R:
            raise ReviewDocxIntegrityError(f"report target is not w:r or w:p: {path}")
        reason, rpr = _ordinary_reason(target)
        if reason is not None:
            results.append(
                ReviewMarkResult(
                    "run",
                    path,
                    final_hash,
                    ReviewMarkStatus.UNMARKED,
                    reason,
                    source_kinds,
                )
            )
            continue

        rpr = _ensure_rpr(target, rpr)
        _insert_highlight(rpr)
        marked_paths.append(path)
        results.append(
            ReviewMarkResult(
                "run",
                path,
                final_hash,
                ReviewMarkStatus.MARKED,
                None,
                source_kinds,
            )
        )

    if not marked_paths:
        output = clean_package_snapshot
    else:
        try:
            after_xml_in_memory = serialize_document_xml(tree, before_xml)
            output = repackage(
                infos, payloads, archive_comment, after_xml_in_memory
            )
            verify_package_scope(clean_package_snapshot, output)
            after_xml = relread_document_xml(output)
            validate_allowed_delta(
                before_xml, after_xml, tuple(marked_paths)
            )

            out_tree = parse_document_xml(after_xml, DOCUMENT_PART)
            out_root = out_tree.getroot()
            for path in marked_paths:
                try:
                    run = parser_api.resolve_structural_path(out_root, path)
                except parser_api.StructuralPathError as exc:
                    raise ReviewDocxIntegrityError(
                        f"postcondition path failed: {path}: {exc}"
                    ) from exc
                if run.tag != W_R:
                    raise ReviewDocxIntegrityError(
                        "postcondition target is not w:r"
                    )
                rprs = _direct(run, W_RPR)
                if len(rprs) != 1:
                    raise ReviewDocxIntegrityError(
                        "postcondition requires exactly one direct w:rPr"
                    )
                highlights = _direct(rprs[0], W_HIGHLIGHT)
                if (
                    len(highlights) != 1
                    or dict(highlights[0].attrib) != {W_VAL: "yellow"}
                ):
                    raise ReviewDocxIntegrityError(
                        "postcondition direct yellow highlight failed"
                    )
        except (PatcherContractError, PatcherIntegrityError) as exc:
            raise ReviewDocxIntegrityError(
                f"review DOCX conservation proof failed: {exc}"
            ) from exc

    output_sha = hashlib.sha256(output).hexdigest()
    return ReviewDocxResult(
        REVIEW_DOCX_VERSION,
        PARSER_VERSION,
        PROCESSING_REPORT_VERSION,
        processing_report_ref(processing_report),
        DOCUMENT_PART,
        input_sha,
        output_sha,
        output,
        tuple(results),
        len(processing_report.classification_items),
    )
