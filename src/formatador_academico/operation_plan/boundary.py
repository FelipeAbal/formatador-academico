"""Boundary helper: derive SourceDocumentRef from an already-produced PhysicalIR.

Kept outside the pure planner core. This helper only reads the in-memory
PhysicalIR mapping; it never re-parses DOCX, never reads files, never
imports lxml/zipfile, and never recomputes hashes.
"""

from __future__ import annotations

from typing import Any, Mapping

from .model import SourceDocumentRef
from .planner import OperationPlanContractError


def source_document_ref_from_physical_ir(physical_ir: Mapping[str, Any]) -> SourceDocumentRef:
    if not isinstance(physical_ir, Mapping):
        raise OperationPlanContractError("physical_ir must be a mapping produced by the parser")
    package = physical_ir.get("package")
    if not isinstance(package, Mapping):
        raise OperationPlanContractError("physical_ir lacks a package mapping")
    package_sha256 = package.get("sha256")
    parser_version = physical_ir.get("parser_version")
    if not isinstance(package_sha256, str) or not package_sha256:
        raise OperationPlanContractError("physical_ir package.sha256 missing or invalid")
    if not isinstance(parser_version, str) or not parser_version:
        raise OperationPlanContractError("physical_ir parser_version missing or invalid")
    return SourceDocumentRef(package_sha256=package_sha256, parser_version=parser_version)
