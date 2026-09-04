"""Unit tests — Analysis View v0.1b Marco 1 (Formatting Resolution, non-toggle).

Covers StyleCatalog, RawPropertyBag, cascade policies, statuses, numbering
clause, duplicates, invalid lexicals and determinism. Synthetic DOCX packages
go through the real DocxParser v0.4 (no hand-made IR) unless stated otherwise.
"""

from __future__ import annotations

import io
import unittest
import zipfile
from decimal import Decimal
from dataclasses import FrozenInstanceError

from formatador_academico.docx_parser import DocxParser
from formatador_academico.analysis.formatting import (
    resolve_paragraph_formatting,
    resolve_run_formatting,
)
from formatador_academico.analysis.formatting_model import (
    ResolutionStatus,
    ThemeRef,
    serialize_resolved_paragraph,
    serialize_resolved_run,
    serialize_style_catalog,
)
from formatador_academico.analysis.style_catalog import build_style_catalog

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"

MAIN_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
STYLES_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"

RES = ResolutionStatus


def build_docx(doc_xml: str, styles_xml: str | None = None,
               extra_parts: dict[str, bytes] | None = None,
               story_rels: list[tuple[str, str, str]] | None = None) -> bytes:
    extra_parts = extra_parts or {}
    story_rels = story_rels or []
    overrides = [f'<Override PartName="/word/document.xml" ContentType="{MAIN_CT}"/>']
    if styles_xml is not None:
        overrides.append(f'<Override PartName="/word/styles.xml" ContentType="{STYLES_CT}"/>')
    story_cts = {
        "footnotes": "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml",
        "endnotes": "application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml",
        "comments": "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml",
        "header": "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml",
        "footer": "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml",
    }
    for name, _ in extra_parts.items():
        base = name.split("/")[-1].split(".")[0]
        kind = base if base in story_cts else base.rstrip("0123456789")
        ctype = story_cts.get(kind, "application/xml")
        overrides.append(f'<Override PartName="/{name}" ContentType="{ctype}"/>')
    ct = (f'<?xml version="1.0"?><Types xmlns="{CT}">'
          f'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          f'<Default Extension="xml" ContentType="application/xml"/>'
          + "".join(overrides) + "</Types>")
    root_rels = (f'<Relationships xmlns="{PR}"><Relationship Id="rId1" '
                 f'Type="{R}/officeDocument" Target="word/document.xml"/></Relationships>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("word/document.xml", doc_xml.encode("utf-8"))
        if story_rels:
            rels = "".join(
                f'<Relationship Id="{rid}" Type="{R}/{t}" Target="{t}"/>'
                for rid, t, target in story_rels)
            # fix target usage
            rels = "".join(
                f'<Relationship Id="{rid}" Type="{R}/{stype}" Target="{target}"/>'
                for rid, stype, target in story_rels)
            z.writestr("word/_rels/document.xml.rels",
                       f'<Relationships xmlns="{PR}">{rels}</Relationships>')
        if styles_xml is not None:
            z.writestr("word/styles.xml", styles_xml.encode("utf-8"))
        for name, data in extra_parts.items():
            z.writestr(name, data)
    return buf.getvalue()


def document(body: str) -> str:
    return (f'<w:document xmlns:w="{W}" xmlns:r="{R}"><w:body>{body}'
            f"</w:body></w:document>")


def styles_part(inner: str) -> str:
    return f'<w:styles xmlns:w="{W}">{inner}</w:styles>'


def parse(body: str, styles: str | None = None):
    pkg = build_docx(document(body), styles)
    ir = DocxParser().parse_bytes(pkg)
    assert ir["status"] == "ok", ir.get("errors")
    catalog = build_style_catalog(pkg, ir)
    return pkg, ir, catalog, ir["stories"][0]["blocks"]


def first_run(paragraph):
    return next(c for c in paragraph["children"] if c["source_type"] == "run_raw")


def resolve_run(body: str, styles: str | None = None):
    pkg, ir, catalog, blocks = parse(body, styles)
    p = next(b for b in blocks if b["source_type"] == "paragraph")
    run = first_run(p)
    return resolve_run_formatting(run, p, catalog, "word/document.xml")


def resolve_par(body: str, styles: str | None = None):
    pkg, ir, catalog, blocks = parse(body, styles)
    p = next(b for b in blocks if b["source_type"] == "paragraph")
    return resolve_paragraph_formatting(p, catalog, "word/document.xml")


# ---------------------------------------------------------------------------
# StyleCatalog
# ---------------------------------------------------------------------------

class StyleCatalogTests(unittest.TestCase):
    def test_styles_part_absent_empty_catalog(self):
        pkg, ir, catalog, _ = parse('<w:p><w:r><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(catalog.part_status, "missing")
        self.assertEqual(catalog.styles, ())
        self.assertIsNone(catalog.doc_defaults)
        self.assertEqual(catalog.catalog_warnings, ())

    def test_styles_part_unreadable_degrades_without_exception(self):
        body = '<w:p><w:r><w:rPr><w:sz w:val="24"/></w:rPr><w:t>a</w:t></w:r></w:p>'
        pkg = build_docx(document(body), "<w:styles><broken")
        ir = DocxParser().parse_bytes(pkg)
        catalog = build_style_catalog(pkg, ir)
        self.assertEqual(catalog.part_status, "unreadable")
        self.assertEqual(catalog.catalog_warnings[0].code, "formatting_styles_part_unreadable")
        # direct formatting still resolves; style-dependent property degrades
        rf = resolve_run(body, None)  # noqa: F841 (sanity: separate path)
        p = ir["stories"][0]["blocks"][0]
        run = first_run(p)
        fmt = resolve_run_formatting(run, p, catalog, "word/document.xml")
        self.assertEqual(fmt.font_size.status, RES.RESOLVED)
        self.assertEqual(fmt.font_size.value.value, Decimal("12"))
        self.assertEqual(fmt.underline.status, RES.UNRESOLVED)
        self.assertEqual(fmt.underline.reason, "styles_unavailable")

    def test_sha_mismatch_raises_contract_violation(self):
        body = '<w:p><w:r><w:t>a</w:t></w:r></w:p>'
        pkg_a = build_docx(document(body), styles_part('<w:style w:type="paragraph" w:styleId="X"/>'))
        ir = DocxParser().parse_bytes(pkg_a)
        pkg_b = build_docx(document(body), styles_part('<w:style w:type="paragraph" w:styleId="Y"/>'))
        with self.assertRaises(ValueError):
            build_style_catalog(pkg_b, ir)

    def test_docdefaults_only(self):
        s = styles_part('<w:docDefaults><w:rPrDefault><w:rPr><w:sz w:val="20"/>'
                        '</w:rPr></w:rPrDefault></w:docDefaults>')
        pkg, ir, catalog, _ = parse('<w:p><w:r><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(catalog.part_status, "ok")
        self.assertEqual(catalog.styles, ())
        self.assertIsNotNone(catalog.doc_defaults)
        self.assertIsNotNone(catalog.doc_defaults.rpr_bag)
        self.assertIsNone(catalog.doc_defaults.ppr_bag)

    def test_duplicate_style_id_catalog_warning(self):
        s = styles_part('<w:style w:type="paragraph" w:styleId="A"/>'
                        '<w:style w:type="paragraph" w:styleId="A"/>')
        _, _, catalog, _ = parse('<w:p/>', s)
        codes = [w.code for w in catalog.catalog_warnings]
        self.assertIn("formatting_duplicate_style_id", codes)

    def test_multiple_defaults_catalog_warning(self):
        s = styles_part('<w:style w:type="paragraph" w:default="1" w:styleId="A"/>'
                        '<w:style w:type="paragraph" w:default="1" w:styleId="B"/>')
        _, _, catalog, _ = parse('<w:p/>', s)
        codes = [w.code for w in catalog.catalog_warnings]
        self.assertIn("formatting_multiple_default_styles", codes)

    def test_link_preserved_but_never_used(self):
        s = styles_part(
            '<w:style w:type="paragraph" w:styleId="H"><w:link w:val="HChar"/>'
            '<w:pPr><w:jc w:val="center"/></w:pPr></w:style>'
            '<w:style w:type="character" w:styleId="HChar"><w:rPr><w:sz w:val="40"/></w:rPr></w:style>')
        rf = resolve_run(
            '<w:p><w:pPr><w:pStyle w:val="H"/></w:pPr><w:r><w:t>a</w:t></w:r></w:p>', s)
        # The linked character style must NOT leak into the run cascade.
        self.assertEqual(rf.font_size.status, RES.ABSENT)
        entry = next(e for e in build_style_catalog(
            build_docx(document('<w:p/>'), s),
            DocxParser().parse_bytes(build_docx(document('<w:p/>'), s)),
        ).styles if e.style_id == "H")
        self.assertEqual(entry.link_id, "HChar")


# ---------------------------------------------------------------------------
# Run cascade (non-toggle)
# ---------------------------------------------------------------------------

class RunCascadeTests(unittest.TestCase):
    def test_direct_size(self):
        rf = resolve_run('<w:p><w:r><w:rPr><w:sz w:val="24"/></w:rPr><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rf.font_size.status, RES.RESOLVED)
        self.assertEqual(rf.font_size.value.value, Decimal("12"))
        self.assertEqual(rf.font_size.value.unit, "pt")
        self.assertEqual(rf.font_size.value.raw_value, "24")
        self.assertEqual(rf.font_size.value.raw_unit, "half_point")
        self.assertEqual(rf.font_size.winning_evidence.source_kind, "direct")

    def test_size_from_docdefaults(self):
        s = styles_part('<w:docDefaults><w:rPrDefault><w:rPr><w:sz w:val="22"/>'
                        '</w:rPr></w:rPrDefault></w:docDefaults>')
        rf = resolve_run('<w:p><w:r><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rf.font_size.status, RES.RESOLVED)
        self.assertEqual(rf.font_size.value.value, Decimal("11"))
        self.assertEqual(rf.font_size.winning_evidence.source_kind, "doc_defaults")

    def test_character_style_size_and_basedon(self):
        s = styles_part(
            '<w:style w:type="character" w:styleId="Base"><w:rPr><w:sz w:val="20"/></w:rPr></w:style>'
            '<w:style w:type="character" w:styleId="Child"><w:basedOn w:val="Base"/></w:style>')
        rf = resolve_run(
            '<w:p><w:r><w:rPr><w:rStyle w:val="Child"/></w:rPr><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rf.font_size.status, RES.RESOLVED)
        self.assertEqual(rf.font_size.value.value, Decimal("10"))
        self.assertEqual(rf.font_size.winning_evidence.style_id, "Base")
        levels = [e.level for e in rf.font_size.evidence_chain]
        # chain stops at the winning level: direct -> Child -> Base(winner)
        self.assertEqual(levels, ["direct", "character_style", "character_style"])

    def test_paragraph_style_rpr_contributes(self):
        s = styles_part('<w:style w:type="paragraph" w:styleId="P">'
                        '<w:rPr><w:sz w:val="26"/></w:rPr></w:style>')
        rf = resolve_run(
            '<w:p><w:pPr><w:pStyle w:val="P"/></w:pPr><w:r><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rf.font_size.status, RES.RESOLVED)
        self.assertEqual(rf.font_size.value.value, Decimal("13"))
        self.assertEqual(rf.font_size.winning_evidence.level
                         if hasattr(rf.font_size.winning_evidence, "level") else
                         rf.font_size.winning_evidence.style_id, "P")

    def test_direct_overrides_style(self):
        s = styles_part('<w:style w:type="character" w:styleId="C">'
                        '<w:rPr><w:sz w:val="20"/></w:rPr></w:style>')
        rf = resolve_run(
            '<w:p><w:r><w:rPr><w:rStyle w:val="C"/><w:sz w:val="32"/></w:rPr>'
            '<w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rf.font_size.value.value, Decimal("16"))
        self.assertEqual(rf.font_size.winning_evidence.source_kind, "direct")

    def test_character_style_beats_paragraph_style(self):
        s = styles_part(
            '<w:style w:type="paragraph" w:styleId="P"><w:rPr><w:sz w:val="20"/></w:rPr></w:style>'
            '<w:style w:type="character" w:styleId="C"><w:rPr><w:sz w:val="28"/></w:rPr></w:style>')
        rf = resolve_run(
            '<w:p><w:pPr><w:pStyle w:val="P"/></w:pPr>'
            '<w:r><w:rPr><w:rStyle w:val="C"/></w:rPr><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rf.font_size.value.value, Decimal("14"))

    def test_missing_referenced_style_ignored_with_warning(self):
        rf = resolve_run(
            '<w:p><w:r><w:rPr><w:rStyle w:val="Ghost"/><w:sz w:val="24"/></w:rPr>'
            '<w:t>a</w:t></w:r></w:p>',
            styles_part('<w:style w:type="character" w:styleId="Real"/>'))
        self.assertEqual(rf.font_size.status, RES.RESOLVED)  # cascade continues
        self.assertIn("formatting_missing_style", [w.code for w in rf.analysis_warnings])

    def test_wrong_type_reference_ignored(self):
        s = styles_part('<w:style w:type="character" w:styleId="C">'
                        '<w:rPr><w:sz w:val="20"/></w:rPr></w:style>')
        # pStyle referencing a character style: ignored, no crash, no unresolved.
        rp = resolve_par(
            '<w:p><w:pPr><w:pStyle w:val="C"/><w:jc w:val="center"/></w:pPr>'
            '<w:r><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rp.alignment.status, RES.RESOLVED)
        self.assertEqual(rp.alignment.value, "center")
        self.assertIn("formatting_wrong_style_type", [w.code for w in rp.analysis_warnings])

    def test_missing_basedon_parent_becomes_root(self):
        s = styles_part('<w:style w:type="character" w:styleId="C">'
                        '<w:basedOn w:val="Ghost"/><w:rPr><w:sz w:val="18"/></w:rPr></w:style>')
        rf = resolve_run(
            '<w:p><w:r><w:rPr><w:rStyle w:val="C"/></w:rPr><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rf.font_size.status, RES.RESOLVED)
        self.assertEqual(rf.font_size.value.value, Decimal("9"))
        self.assertIn("formatting_missing_style", [w.code for w in rf.analysis_warnings])

    def test_style_cycle_unresolved_for_dependent_property(self):
        s = styles_part(
            '<w:style w:type="character" w:styleId="C"><w:basedOn w:val="A"/>'
            '<w:rPr><w:sz w:val="20"/></w:rPr></w:style>'
            '<w:style w:type="character" w:styleId="A"><w:basedOn w:val="B"/></w:style>'
            '<w:style w:type="character" w:styleId="B"><w:basedOn w:val="A"/>'
            '<w:rPr><w:u w:val="single"/></w:rPr></w:style>')
        rf = resolve_run(
            '<w:p><w:r><w:rPr><w:rStyle w:val="C"/></w:rPr><w:t>a</w:t></w:r></w:p>', s)
        # sz is declared by C, before the cycle {A, B}: still resolved.
        self.assertEqual(rf.font_size.status, RES.RESOLVED)
        # underline would depend on cycle member B: unresolved(style_cycle).
        self.assertEqual(rf.underline.status, RES.UNRESOLVED)
        self.assertEqual(rf.underline.reason, "style_cycle")
        self.assertIn("formatting_style_cycle", [w.code for w in rf.analysis_warnings])

    def test_invalid_lexical_size_is_terminal(self):
        s = styles_part('<w:docDefaults><w:rPrDefault><w:rPr><w:sz w:val="24"/>'
                        '</w:rPr></w:rPrDefault></w:docDefaults>')
        rf = resolve_run(
            '<w:p><w:r><w:rPr><w:sz w:val="banana"/></w:rPr><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rf.font_size.status, RES.INVALID)
        self.assertIsNone(rf.font_size.value)
        self.assertEqual(rf.font_size.winning_evidence, None)
        self.assertEqual(rf.font_size.evidence_chain[-1].detail, "invalid")
        self.assertEqual(rf.font_size.evidence_chain[-1].evidence.raw_value, "banana")
        self.assertIn("formatting_invalid_value", [w.code for w in rf.analysis_warnings])

    def test_duplicate_property_identical_values(self):
        rf = resolve_run(
            '<w:p><w:r><w:rPr><w:sz w:val="24"/><w:sz w:val="24"/></w:rPr>'
            '<w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rf.font_size.status, RES.RESOLVED)
        self.assertEqual(rf.font_size.value.value, Decimal("12"))
        self.assertIn("formatting_duplicate_property", [w.code for w in rf.analysis_warnings])

    def test_duplicate_property_conflicting_values_ambiguous(self):
        rf = resolve_run(
            '<w:p><w:r><w:rPr><w:sz w:val="24"/><w:sz w:val="28"/></w:rPr>'
            '<w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rf.font_size.status, RES.AMBIGUOUS)
        self.assertIsNone(rf.font_size.value)
        details = [e.detail for e in rf.font_size.evidence_chain]
        self.assertIn("duplicate_conflict", details)

    def test_duplicate_style_id_first_definition_wins(self):
        # Decision 0016: first documental definition is the normative referent.
        s = styles_part(
            '<w:style w:type="character" w:styleId="C"><w:rPr><w:sz w:val="20"/></w:rPr></w:style>'
            '<w:style w:type="character" w:styleId="C"><w:rPr><w:sz w:val="28"/></w:rPr></w:style>')
        rf = resolve_run(
            '<w:p><w:r><w:rPr><w:rStyle w:val="C"/></w:rPr><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rf.font_size.status, RES.RESOLVED)
        self.assertEqual(rf.font_size.value.value, Decimal("10"))
        self.assertIn("duplicate_style_id_first_definition",
                      [e.detail for e in rf.font_size.evidence_chain])

    def test_duplicate_style_id_not_referenced_has_no_effect(self):
        s = styles_part(
            '<w:style w:type="character" w:styleId="C"><w:rPr><w:sz w:val="20"/></w:rPr></w:style>'
            '<w:style w:type="character" w:styleId="C"><w:rPr><w:sz w:val="28"/></w:rPr></w:style>')
        rf = resolve_run('<w:p><w:r><w:rPr><w:sz w:val="24"/></w:rPr><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rf.font_size.status, RES.RESOLVED)

    def test_underline_default_single_and_tokens(self):
        rf = resolve_run('<w:p><w:r><w:rPr><w:u/></w:rPr><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rf.underline.status, RES.RESOLVED)
        self.assertEqual(rf.underline.value, "single")
        rf2 = resolve_run('<w:p><w:r><w:rPr><w:u w:val="double"/></w:rPr><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rf2.underline.value, "double")
        # unknown token preserved lexically (no aggressive enum reduction)
        rf3 = resolve_run('<w:p><w:r><w:rPr><w:u w:val="wavyFuture"/></w:rPr><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rf3.underline.status, RES.RESOLVED)
        self.assertEqual(rf3.underline.value, "wavyFuture")

    def test_vert_align_tokens(self):
        rf = resolve_run('<w:p><w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr>'
                         '<w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rf.vert_align.value, "superscript")

    def test_font_slots_independent(self):
        s = styles_part('<w:docDefaults><w:rPrDefault><w:rPr>'
                        '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="SimSun" w:cs="Courier"/>'
                        '</w:rPr></w:rPrDefault></w:docDefaults>')
        rf = resolve_run(
            '<w:p><w:r><w:rPr><w:rFonts w:ascii="Times"/></w:rPr><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rf.font_spec.ascii.value, "Times")          # direct wins
        self.assertEqual(rf.font_spec.h_ansi.value, "Arial")         # docDefaults
        self.assertEqual(rf.font_spec.east_asia.value, "SimSun")
        self.assertEqual(rf.font_spec.cs.value, "Courier")
        self.assertEqual(rf.font_spec.ascii_theme.status, RES.ABSENT)

    def test_font_theme_ref_is_resolved_documental_value(self):
        rf = resolve_run(
            '<w:p><w:r><w:rPr><w:rFonts w:asciiTheme="majorHAnsi" w:cstheme="minorBidi"/>'
            '</w:rPr><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rf.font_spec.ascii_theme.status, RES.RESOLVED)
        self.assertIsInstance(rf.font_spec.ascii_theme.value, ThemeRef)
        self.assertEqual(rf.font_spec.ascii_theme.value.theme_slot, "majorHAnsi")
        self.assertEqual(rf.font_spec.cs_theme.value.theme_slot, "minorBidi")
        self.assertEqual(rf.analysis_warnings, ())

    def test_lang_slots(self):
        rf = resolve_run(
            '<w:p><w:r><w:rPr><w:lang w:val="pt-BR" w:eastAsia="ja-JP" w:bidi="ar-SA"/>'
            '</w:rPr><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rf.language.val.value, "pt-BR")
        self.assertEqual(rf.language.east_asia.value, "ja-JP")
        self.assertEqual(rf.language.bidi.value, "ar-SA")

    def test_partial_failure_is_per_property(self):
        s = styles_part('<w:docDefaults><w:rPrDefault><w:rPr><w:sz w:val="24"/>'
                        '</w:rPr></w:rPrDefault></w:docDefaults>')
        rf = resolve_run(
            '<w:p><w:r><w:rPr><w:sz w:val="banana"/><w:u w:val="single"/></w:rPr>'
            '<w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rf.font_size.status, RES.INVALID)
        self.assertEqual(rf.underline.status, RES.RESOLVED)


# ---------------------------------------------------------------------------
# Paragraph cascade
# ---------------------------------------------------------------------------

class ParagraphCascadeTests(unittest.TestCase):
    def test_direct_alignment_raw_token(self):
        rp = resolve_par('<w:p><w:pPr><w:jc w:val="both"/></w:pPr><w:r><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rp.alignment.status, RES.RESOLVED)
        self.assertEqual(rp.alignment.value, "both")

    def test_style_alignment_and_pstyle_id(self):
        s = styles_part('<w:style w:type="paragraph" w:styleId="P">'
                        '<w:pPr><w:jc w:val="center"/></w:pPr></w:style>')
        rp = resolve_par(
            '<w:p><w:pPr><w:pStyle w:val="P"/></w:pPr><w:r><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rp.alignment.value, "center")
        self.assertEqual(rp.paragraph_style_id.status, RES.RESOLVED)
        self.assertEqual(rp.paragraph_style_id.value, "P")

    def test_default_paragraph_style_alignment(self):
        s = styles_part('<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
                        '<w:pPr><w:jc w:val="both"/></w:pPr></w:style>')
        rp = resolve_par('<w:p><w:r><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rp.alignment.value, "both")
        self.assertEqual(rp.alignment.winning_evidence.style_id, "Normal")

    def test_multiple_defaults_last_instance_wins(self):
        # Decision 0016: deterministic last-instance selection + documentary warning.
        s = styles_part(
            '<w:style w:type="paragraph" w:default="1" w:styleId="A">'
            '<w:pPr><w:jc w:val="left"/></w:pPr></w:style>'
            '<w:style w:type="paragraph" w:default="1" w:styleId="B">'
            '<w:pPr><w:jc w:val="right"/></w:pPr></w:style>')
        _, _, catalog, blocks = parse('<w:p><w:r><w:t>a</w:t></w:r></w:p>', s)
        rp = resolve_paragraph_formatting(blocks[0], catalog, "word/document.xml")
        self.assertEqual(rp.alignment.status, RES.RESOLVED)
        self.assertEqual(rp.alignment.value, "right")
        self.assertEqual(rp.alignment.winning_evidence.style_id, "B")
        self.assertEqual(rp.alignment.evidence_chain[-1].detail,
                         "multiple_defaults_last_instance")
        self.assertIn("formatting_multiple_default_styles",
                      [w.code for w in catalog.catalog_warnings])

    def test_alignment_start_not_mapped(self):
        rp = resolve_par('<w:p><w:pPr><w:jc w:val="start"/></w:pPr><w:r><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rp.alignment.value, "start")

    def test_spacing_auto_multiple(self):
        rp = resolve_par('<w:p><w:pPr><w:spacing w:line="360" w:lineRule="auto"/></w:pPr>'
                         '<w:r><w:t>a</w:t></w:r></w:p>')
        ls = rp.spacing.line
        self.assertEqual(ls.status, RES.RESOLVED)
        self.assertEqual(ls.value.rule, "auto")
        self.assertEqual(ls.value.value, Decimal("1.5"))
        self.assertEqual(ls.value.unit, "multiple")

    def test_spacing_exact_and_atleast(self):
        rp = resolve_par('<w:p><w:pPr><w:spacing w:line="240" w:lineRule="exact"/></w:pPr>'
                         '<w:r><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rp.spacing.line.value.value, Decimal("12"))
        self.assertEqual(rp.spacing.line.value.unit, "pt")
        rp2 = resolve_par('<w:p><w:pPr><w:spacing w:line="300" w:lineRule="atLeast"/></w:pPr>'
                          '<w:r><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rp2.spacing.line.value.unit, "pt")

    def test_spacing_before_after_twips(self):
        rp = resolve_par('<w:p><w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>'
                         '<w:r><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rp.spacing.before.value.value, Decimal("12"))
        self.assertEqual(rp.spacing.after.value.value, Decimal("6"))

    def test_spacing_beforelines_hundredths(self):
        rp = resolve_par('<w:p><w:pPr><w:spacing w:beforeLines="150"/></w:pPr>'
                         '<w:r><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rp.spacing.before_lines.status, RES.RESOLVED)
        self.assertEqual(rp.spacing.before_lines.value, Decimal("1.5"))

    def test_autospacing_unresolved(self):
        rp = resolve_par('<w:p><w:pPr><w:spacing w:beforeAutospacing="1"/></w:pPr>'
                         '<w:r><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rp.spacing.before.status, RES.UNRESOLVED)
        self.assertEqual(rp.spacing.before.reason, "autospacing_unsupported")
        # sibling slots unaffected
        self.assertEqual(rp.spacing.after.status, RES.ABSENT)

    def test_indents_twips_and_start_end_preserved(self):
        rp = resolve_par('<w:p><w:pPr><w:ind w:left="1440" w:firstLine="360" '
                         'w:start="720" w:hanging="240"/></w:pPr><w:r><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rp.indents.left.value.value, Decimal("72"))
        self.assertEqual(rp.indents.first_line.value.value, Decimal("18"))
        self.assertEqual(rp.indents.start.value.value, Decimal("36"))
        self.assertEqual(rp.indents.hanging.value.value, Decimal("12"))
        self.assertEqual(rp.indents.right.status, RES.ABSENT)

    def test_indent_chars_unsupported_unit(self):
        rp = resolve_par('<w:p><w:pPr><w:ind w:leftChars="200"/></w:pPr><w:r><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rp.indents.left.status, RES.UNRESOLVED)
        self.assertEqual(rp.indents.left.reason, "unsupported_unit")

    # Numbering clause — decision 0015 cases A/B/C
    def test_numbering_case_a_style_wins(self):
        s = styles_part('<w:style w:type="paragraph" w:styleId="L">'
                        '<w:pPr><w:numPr><w:numId w:val="1"/></w:numPr>'
                        '<w:ind w:left="1440" w:right="100" w:firstLine="0" '
                        'w:hanging="0" w:start="100" w:end="100"/></w:pPr></w:style>')
        rp = resolve_par('<w:p><w:pPr><w:pStyle w:val="L"/></w:pPr><w:r><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rp.indents.left.status, RES.RESOLVED)
        self.assertEqual(rp.indents.left.value.value, Decimal("72"))
        # every indent slot determined by the style => numbering never materializes
        self.assertNotIn("formatting_numbering_present", [w.code for w in rp.analysis_warnings])

    def test_numbering_case_a_partial_other_slots_unresolved(self):
        s = styles_part('<w:style w:type="paragraph" w:styleId="L">'
                        '<w:pPr><w:numPr><w:numId w:val="1"/></w:numPr>'
                        '<w:ind w:left="1440"/></w:pPr></w:style>')
        rp = resolve_par('<w:p><w:pPr><w:pStyle w:val="L"/></w:pPr><w:r><w:t>a</w:t></w:r></w:p>', s)
        # left is determined by the style (more specific than numbering)
        self.assertEqual(rp.indents.left.status, RES.RESOLVED)
        # first_line is not determined anywhere supported and may come from numbering
        self.assertEqual(rp.indents.first_line.status, RES.UNRESOLVED)
        self.assertEqual(rp.indents.first_line.reason, "numbering_indent_unsupported")

    def test_numbering_case_b_unresolved(self):
        rp = resolve_par('<w:p><w:pPr><w:numPr><w:numId w:val="1"/></w:numPr></w:pPr>'
                         '<w:r><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rp.indents.left.status, RES.UNRESOLVED)
        self.assertEqual(rp.indents.left.reason, "numbering_indent_unsupported")
        self.assertIn("formatting_numbering_present", [w.code for w in rp.analysis_warnings])
        # alignment is not an indent slot: unaffected
        self.assertEqual(rp.alignment.status, RES.ABSENT)

    def test_numbering_case_c_direct_wins(self):
        rp = resolve_par('<w:p><w:pPr><w:numPr><w:numId w:val="1"/></w:numPr>'
                         '<w:ind w:left="2880"/></w:pPr><w:r><w:t>a</w:t></w:r></w:p>')
        self.assertEqual(rp.indents.left.status, RES.RESOLVED)
        self.assertEqual(rp.indents.left.value.value, Decimal("144"))

    def test_numpr_alone_no_warning_when_no_indent_dependency(self):
        # numPr present but every indent slot resolved by direct => no warning.
        rp = resolve_par('<w:p><w:pPr><w:numPr><w:numId w:val="1"/></w:numPr>'
                         '<w:ind w:left="100" w:right="100" w:firstLine="0" '
                         'w:hanging="0" w:start="100" w:end="100"/></w:pPr>'
                         '<w:r><w:t>a</w:t></w:r></w:p>')
        self.assertNotIn("formatting_numbering_present", [w.code for w in rp.analysis_warnings])


# ---------------------------------------------------------------------------
# Decision 0016 — style selection errata
# ---------------------------------------------------------------------------

def _walk_resolved(obj):
    """Yield every ResolvedValue reachable from a resolved formatting object."""
    from formatador_academico.analysis.formatting_model import ResolvedValue as RV
    if isinstance(obj, RV):
        yield obj
    elif hasattr(obj, "__dataclass_fields__"):
        for f in obj.__dataclass_fields__:
            yield from _walk_resolved(getattr(obj, f))
    elif isinstance(obj, tuple):
        for v in obj:
            yield from _walk_resolved(v)


class StyleSelectionErrata0016Tests(unittest.TestCase):
    def test_three_defaults_last_wins(self):
        s = styles_part(
            '<w:style w:type="paragraph" w:default="1" w:styleId="A">'
            '<w:pPr><w:jc w:val="left"/></w:pPr></w:style>'
            '<w:style w:type="paragraph" w:default="1" w:styleId="B">'
            '<w:pPr><w:jc w:val="right"/></w:pPr></w:style>'
            '<w:style w:type="paragraph" w:default="1" w:styleId="C">'
            '<w:pPr><w:jc w:val="center"/></w:pPr></w:style>')
        rp = resolve_par('<w:p><w:r><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rp.alignment.status, RES.RESOLVED)
        self.assertEqual(rp.alignment.value, "center")
        self.assertEqual(rp.alignment.winning_evidence.style_id, "C")
        self.assertNotEqual(rp.alignment.status, RES.AMBIGUOUS)

    def test_duplicate_style_id_via_basedon_first_wins(self):
        s = styles_part(
            '<w:style w:type="character" w:styleId="C"><w:basedOn w:val="X"/></w:style>'
            '<w:style w:type="character" w:styleId="X"><w:rPr><w:sz w:val="20"/></w:rPr></w:style>'
            '<w:style w:type="character" w:styleId="X"><w:rPr><w:sz w:val="28"/></w:rPr></w:style>')
        rf = resolve_run(
            '<w:p><w:r><w:rPr><w:rStyle w:val="C"/></w:rPr><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rf.font_size.status, RES.RESOLVED)
        self.assertEqual(rf.font_size.value.value, Decimal("10"))  # first X, not 14pt
        self.assertIn("duplicate_style_id_first_definition",
                      [e.detail for e in rf.font_size.evidence_chain])
        self.assertNotEqual(rf.font_size.status, RES.AMBIGUOUS)

    def test_two_styles_without_styleid_no_duplicate_warning(self):
        s = styles_part(
            '<w:style w:type="paragraph"><w:pPr><w:jc w:val="left"/></w:pPr></w:style>'
            '<w:style w:type="paragraph"><w:pPr><w:jc w:val="right"/></w:pPr></w:style>')
        _, _, catalog, _ = parse('<w:p/>', s)
        self.assertEqual(len(catalog.styles), 2)
        self.assertNotIn("formatting_duplicate_style_id",
                         [w.code for w in catalog.catalog_warnings])

    def test_absent_styleid_is_none(self):
        s = styles_part('<w:style w:type="paragraph"><w:pPr><w:jc w:val="left"/></w:pPr></w:style>')
        _, _, catalog, _ = parse('<w:p/>', s)
        self.assertIsNone(catalog.styles[0].style_id)

    def test_default_without_styleid_applies(self):
        s = styles_part(
            '<w:style w:type="paragraph" w:default="1">'
            '<w:pPr><w:jc w:val="center"/></w:pPr></w:style>')
        rp = resolve_par('<w:p><w:r><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rp.alignment.status, RES.RESOLVED)
        self.assertEqual(rp.alignment.value, "center")
        self.assertIsNone(rp.alignment.winning_evidence.style_id)
        self.assertIn("/w:styles/w:style[1]", rp.alignment.winning_evidence.structural_path)

    def test_missing_type_defaults_to_paragraph(self):
        s = styles_part('<w:style w:styleId="P"><w:pPr><w:jc w:val="right"/></w:pPr></w:style>')
        _, _, catalog, _ = parse('<w:p/>', s)
        self.assertEqual(catalog.styles[0].style_type, "paragraph")
        # and it is reachable as a paragraph style
        rp = resolve_par(
            '<w:p><w:pPr><w:pStyle w:val="P"/></w:pPr><w:r><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rp.alignment.status, RES.RESOLVED)
        self.assertEqual(rp.alignment.value, "right")

    def test_explicit_empty_styleid_stays_empty_string(self):
        s = styles_part('<w:style w:type="paragraph" w:styleId=""/>')
        _, _, catalog, _ = parse('<w:p/>', s)
        self.assertEqual(catalog.styles[0].style_id, "")
        self.assertIsNotNone(catalog.styles[0].style_id)

    def test_duplicate_id_plus_multiple_defaults_combined(self):
        s = styles_part(
            '<w:style w:type="paragraph" w:default="1" w:styleId="A">'
            '<w:pPr><w:jc w:val="left"/></w:pPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="X">'
            '<w:pPr><w:ind w:left="720"/></w:pPr></w:style>'
            '<w:style w:type="paragraph" w:default="1" w:styleId="X">'
            '<w:pPr><w:jc w:val="right"/></w:pPr></w:style>'
            '<w:style w:type="paragraph" w:default="1" w:styleId="B">'
            '<w:pPr><w:jc w:val="both"/></w:pPr></w:style>')
        _, _, catalog, _ = parse('<w:p/>', s)
        codes = [w.code for w in catalog.catalog_warnings]
        self.assertIn("formatting_duplicate_style_id", codes)
        self.assertIn("formatting_multiple_default_styles", codes)
        # no pStyle: default selection picks B (last default), not the
        # duplicated-id default X#2 — selection is by physical identity.
        rp = resolve_par('<w:p><w:r><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rp.alignment.value, "both")
        self.assertEqual(rp.alignment.winning_evidence.style_id, "B")
        self.assertNotEqual(rp.alignment.status, RES.AMBIGUOUS)
        # pStyle="X" references the FIRST definition of X (indent, no jc).
        rp2 = resolve_par(
            '<w:p><w:pPr><w:pStyle w:val="X"/></w:pPr><w:r><w:t>a</w:t></w:r></w:p>', s)
        self.assertEqual(rp2.indents.left.status, RES.RESOLVED)
        self.assertEqual(rp2.indents.left.value.value, Decimal("36"))
        self.assertEqual(rp2.alignment.status, RES.ABSENT)
        self.assertNotEqual(rp2.indents.left.status, RES.AMBIGUOUS)

    def test_no_ambiguous_anywhere_in_errata_scenarios(self):
        scenarios = [
            ('<w:p><w:r><w:t>a</w:t></w:r></w:p>', styles_part(
                '<w:style w:type="paragraph" w:default="1" w:styleId="A">'
                '<w:pPr><w:jc w:val="left"/></w:pPr></w:style>'
                '<w:style w:type="paragraph" w:default="1" w:styleId="B">'
                '<w:pPr><w:jc w:val="right"/></w:pPr></w:style>')),
            ('<w:p><w:pPr><w:pStyle w:val="X"/></w:pPr>'
             '<w:r><w:rPr><w:rStyle w:val="X"/></w:rPr><w:t>a</w:t></w:r></w:p>',
             styles_part(
                 '<w:style w:type="character" w:styleId="X"><w:rPr><w:sz w:val="20"/></w:rPr></w:style>'
                 '<w:style w:type="character" w:styleId="X"><w:rPr><w:sz w:val="28"/></w:rPr></w:style>')),
            ('<w:p><w:r><w:t>a</w:t></w:r></w:p>', styles_part(
                '<w:style w:type="paragraph" w:default="1">'
                '<w:pPr><w:jc w:val="center"/></w:pPr></w:style>')),
        ]
        for body, styles in scenarios:
            pkg, ir, catalog, blocks = parse(body, styles)
            p = next(b for b in blocks if b["source_type"] == "paragraph")
            run = first_run(p)
            pf = resolve_paragraph_formatting(p, catalog, "word/document.xml")
            rf = resolve_run_formatting(run, p, catalog, "word/document.xml")
            for rv in list(_walk_resolved(pf)) + list(_walk_resolved(rf)):
                self.assertNotEqual(rv.status, RES.AMBIGUOUS,
                                    f"unexpected ambiguous in scenario {body!r}")


# ---------------------------------------------------------------------------
# Determinism / immutability
# ---------------------------------------------------------------------------

class DeterminismTests(unittest.TestCase):
    BODY = ('<w:p><w:pPr><w:pStyle w:val="P"/><w:spacing w:line="360" w:lineRule="auto"/></w:pPr>'
            '<w:r><w:rPr><w:sz w:val="24"/><w:rFonts w:asciiTheme="majorHAnsi"/></w:rPr>'
            '<w:t>a</w:t></w:r></w:p>')
    STYLES = styles_part(
        '<w:docDefaults><w:rPrDefault><w:rPr><w:sz w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults>'
        '<w:style w:type="paragraph" w:styleId="P"><w:pPr><w:jc w:val="both"/></w:pPr></w:style>')

    def _resolve(self):
        pkg, ir, catalog, blocks = parse(self.BODY, self.STYLES)
        p = blocks[0]
        run = first_run(p)
        return pkg, ir, catalog, p, run

    def test_serialization_deterministic_same_process(self):
        _, _, catalog, p, run = self._resolve()
        a = serialize_resolved_paragraph(resolve_paragraph_formatting(p, catalog, "word/document.xml"))
        b = serialize_resolved_paragraph(resolve_paragraph_formatting(p, catalog, "word/document.xml"))
        self.assertEqual(a, b)
        c1 = serialize_resolved_run(resolve_run_formatting(run, p, catalog, "word/document.xml"))
        c2 = serialize_resolved_run(resolve_run_formatting(run, p, catalog, "word/document.xml"))
        self.assertEqual(c1, c2)
        self.assertEqual(serialize_style_catalog(catalog), serialize_style_catalog(catalog))

    def test_serialization_deterministic_cross_process(self):
        import subprocess, sys
        _, _, catalog, p, run = self._resolve()
        expected = serialize_resolved_run(
            resolve_run_formatting(run, p, catalog, "word/document.xml")).decode("utf-8")
        script = f'''
import sys, io, zipfile
sys.path.insert(0, "src")
sys.path.insert(0, "tests")
from test_analysis_formatting_v01b_m1 import parse, first_run
from formatador_academico.analysis.formatting import resolve_run_formatting
from formatador_academico.analysis.formatting_model import serialize_resolved_run
pkg, ir, catalog, blocks = parse({self.BODY!r}, {self.STYLES!r})
p = blocks[0]; run = first_run(p)
sys.stdout.write(serialize_resolved_run(resolve_run_formatting(run, p, catalog, "word/document.xml")).decode())
'''
        for seed in ("0", "42"):
            out = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, cwd=".",
                env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
            )
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(out.stdout, expected)

    def test_physical_ir_and_package_not_modified(self):
        import copy
        pkg, ir, catalog, p, run = self._resolve()
        ir_before = copy.deepcopy(ir)
        resolve_paragraph_formatting(p, catalog, "word/document.xml")
        resolve_run_formatting(run, p, catalog, "word/document.xml")
        self.assertEqual(ir, ir_before)

    def test_catalog_immutable(self):
        _, _, catalog, _, _ = self._resolve()
        with self.assertRaises(FrozenInstanceError):
            catalog.part_status = "hacked"  # type: ignore[misc]

    def test_no_lxml_in_output(self):
        from lxml import etree
        _, _, catalog, p, run = self._resolve()
        rf = resolve_run_formatting(run, p, catalog, "word/document.xml")

        def walk(obj):
            if isinstance(obj, (etree._Element, etree._ElementTree)):
                raise AssertionError("live lxml object in output")
            if hasattr(obj, "__dataclass_fields__"):
                for f in obj.__dataclass_fields__:
                    walk(getattr(obj, f))
            elif isinstance(obj, tuple):
                for v in obj:
                    walk(v)
        walk(rf)
        walk(catalog)


if __name__ == "__main__":
    unittest.main()
