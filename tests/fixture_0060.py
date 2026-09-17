"""Reusable builder for the synthetic parser stress fixture of cycle 0060."""

from __future__ import annotations

import json
from pathlib import Path

from test_analysis_formatting_v01b_m1 import build_docx, styles_part
from test_classification_v01_e2e import NORMAL


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "tests" / "fixtures" / "0060-parser-structural-stress.json"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"


def load_stress_spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def _deep_sdt(levels: int) -> str:
    content = "<w:p><w:r><w:t>depth</w:t></w:r></w:p>"
    for _ in range(levels):
        content = f"<w:sdt><w:sdtContent>{content}</w:sdtContent></w:sdt>"
    return content


def _same_name_run_stress(count: int) -> str:
    children = []
    for index in range(count):
        children.append(f"<w:r><w:t>run-{index}</w:t></w:r>")
        if index + 1 < count:
            children.append(
                f'<w:bookmarkStart w:id="{index}" w:name="stress-{index}"/>'
                f'<w:bookmarkEnd w:id="{index}"/>'
            )
    return "<w:p>" + "".join(children) + "</w:p>"


def _same_name_table_stress(count: int) -> str:
    records = []
    for index in range(count):
        records.append(
            "<w:tbl><w:tr><w:tc><w:p><w:r>"
            f"<w:t>table-{index}</w:t>"
            "</w:r></w:p></w:tc></w:tr></w:tbl>"
        )
        records.append(f"<w:p><w:r><w:t>separator-{index}</w:t></w:r></w:p>")
    return "".join(records)


def build_structural_stress_package() -> bytes:
    spec = load_stress_spec()
    body = (
        spec["document_body"]
        + _same_name_run_stress(spec["same_name_sibling_runs"])
        + _same_name_table_stress(spec["same_name_sibling_tables"])
        + _deep_sdt(spec["deep_sdt_levels"])
    )
    document = (
        f'<w:document xmlns:w="{W}" xmlns:r="{R}" xmlns:mc="{MC}" '
        f'xmlns:w14="{W14}" mc:Ignorable="w14"><w:body>{body}</w:body></w:document>'
    )
    extra_parts = {
        item["part"]: item["xml"].encode("utf-8")
        for item in spec["secondary_stories"]
    }
    story_rels = [
        (item["relationship_id"], item["story_type"], item["target"])
        for item in spec["secondary_stories"]
    ]
    return build_docx(
        document,
        styles_part(NORMAL),
        extra_parts=extra_parts,
        story_rels=story_rels,
    )
