"""Classification Layer v0.1 — unit, contract and adversarial tests.

Covers the ten mandatory fixtures of decision 0022, the hard model
invariants, reason priority, adversarial custom styles, projection safety,
input immutability and the forbidden-import boundary. Synthetic DOCX
packages go through the real DocxParser v0.4 (no hand-made IR).
"""

from __future__ import annotations

import inspect
import unittest
from dataclasses import FrozenInstanceError

import formatador_academico.classification as classification_pkg
from formatador_academico.classification import (
    CLASSIFICATION_VERSION,
    CLASSIFICATION_VOCABULARY_VERSION,
    ClassificationBasis,
    ClassificationEvidence,
    ClassificationProvenance,
    ClassificationReason,
    ClassificationResult,
    ClassificationStatus,
    EvidencePolarity,
    EvidenceSourceKind,
    EvidenceStrength,
    IdentityOutcome,
    ParentAnchor,
    TargetClass,
    classify_document,
    eligible_for_automatic_use,
    project_run_classification,
    project_target_classification,
    resolve_style_identity,
    serialize_classification_result,
    serialize_classification_results,
)
from formatador_academico.analysis.formatting_model import (
    ResolutionStatus,
    serialize_style_catalog,
)
from formatador_academico.analysis.style_catalog import build_style_catalog
from formatador_academico.decision import TargetClassification
from formatador_academico.docx_parser import DocxParser

from test_analysis_formatting_v01b_m1 import (
    build_docx,
    document,
    first_run,
    styles_part,
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

NORMAL = (
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
    '<w:name w:val="Normal"/></w:style>'
)
HEADING1 = (
    '<w:style w:type="paragraph" w:styleId="Heading1">'
    '<w:name w:val="heading 1"/><w:basedOn w:val="Normal"/></w:style>'
)


def classify(body: str, styles: str | None, extra_parts=None, story_rels=None):
    pkg = build_docx(document(body), styles, extra_parts=extra_parts,
                     story_rels=story_rels)
    ir = DocxParser().parse_bytes(pkg)
    assert ir["status"] == "ok", ir.get("errors")
    catalog = build_style_catalog(pkg, ir)
    return pkg, ir, catalog, classify_document(ir, catalog)


def paragraph_blocks(ir, story_index=0):
    return ir["stories"][story_index]["blocks"]


class ClassificationV01Fixtures(unittest.TestCase):
    """The ten mandatory fixtures of decision 0022."""

    def test_fixture_1_normal_identity_classifies_body(self):
        # explicit w:pStyle=Normal
        _, _, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
            '<w:r><w:t>corpo</w:t></w:r></w:p>',
            styles_part(NORMAL),
        )
        (result,) = results
        self.assertEqual(result.status, ClassificationStatus.CLASSIFIED)
        self.assertEqual(result.target_class, TargetClass.BODY)
        self.assertEqual(result.basis, ClassificationBasis.EXPLICIT)
        self.assertEqual(result.reasons, (ClassificationReason.EXPLICIT_STYLE_SIGNAL,))
        self.assertEqual(result.metadata, ())
        self.assertEqual(result.provenance, ClassificationProvenance.DIRECT)
        self.assertTrue(result.evidence)
        self.assertTrue(eligible_for_automatic_use(result))

    def test_fixture_1b_default_normal_style_classifies_body(self):
        # no direct pStyle; the applicable default paragraph style is Normal
        _, _, _, results = classify(
            '<w:p><w:r><w:t>corpo</w:t></w:r></w:p>', styles_part(NORMAL)
        )
        (result,) = results
        self.assertEqual(result.target_class, TargetClass.BODY)
        features = [e.feature for e in result.evidence]
        self.assertIn("default_paragraph_style", features)

    def test_fixture_2_heading1_classifies_heading_level_1(self):
        _, _, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            '<w:r><w:t>Título</w:t></w:r></w:p>',
            styles_part(NORMAL + HEADING1),
        )
        (result,) = results
        self.assertEqual(
            (result.status, result.target_class, result.metadata, result.basis),
            (ClassificationStatus.CLASSIFIED, TargetClass.HEADING,
             (("level", 1),), ClassificationBasis.EXPLICIT),
        )

    def test_heading_levels_1_to_9(self):
        styles = NORMAL + "".join(
            f'<w:style w:type="paragraph" w:styleId="Heading{n}">'
            f'<w:name w:val="heading {n}"/></w:style>' for n in range(1, 10)
        )
        body = "".join(
            f'<w:p><w:pPr><w:pStyle w:val="Heading{n}"/></w:pPr>'
            f'<w:r><w:t>h{n}</w:t></w:r></w:p>' for n in range(1, 10)
        )
        _, _, _, results = classify(body, styles_part(styles))
        self.assertEqual(
            [r.metadata for r in results],
            [(("level", n),) for n in range(1, 10)],
        )
        self.assertTrue(all(r.target_class is TargetClass.HEADING for r in results))

    def test_fixture_3_custom_style_based_on_heading1_inherits_heading(self):
        custom = (
            '<w:style w:type="paragraph" w:styleId="MyHeading" w:customStyle="1">'
            '<w:name w:val="Meu Título"/><w:basedOn w:val="Heading1"/></w:style>'
        )
        _, _, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="MyHeading"/></w:pPr>'
            '<w:r><w:t>Título custom</w:t></w:r></w:p>',
            styles_part(NORMAL + HEADING1 + custom),
        )
        (result,) = results
        self.assertEqual(result.status, ClassificationStatus.CLASSIFIED)
        self.assertEqual(result.target_class, TargetClass.HEADING)
        self.assertEqual(result.metadata, (("level", 1),))
        self.assertIn("based_on_chain", [e.feature for e in result.evidence])

    def test_fixture_4_direct_formatting_lookalike_without_identity_abstains(self):
        # bold + 14pt + centered, but no recognizable style identity anywhere
        only_custom = (
            '<w:style w:type="paragraph" w:styleId="CustomBody" w:customStyle="1">'
            '<w:name w:val="Texto"/></w:style>'
        )
        _, _, _, results = classify(
            '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
            '<w:r><w:rPr><w:b/><w:sz w:val="28"/></w:rPr>'
            '<w:t>PARECE TITULO</w:t></w:r></w:p>',
            styles_part(only_custom),
        )
        (result,) = results
        self.assertEqual(result.status, ClassificationStatus.ABSTAINED)
        self.assertEqual(result.reasons, (ClassificationReason.INSUFFICIENT_EVIDENCE,))
        self.assertIsNone(result.target_class)

    def test_fixture_5_empty_paragraph_abstains_empty_content(self):
        _, _, _, results = classify('<w:p/>', styles_part(NORMAL))
        (result,) = results
        self.assertEqual(
            (result.status, result.reasons),
            (ClassificationStatus.ABSTAINED, (ClassificationReason.EMPTY_CONTENT,)),
        )

    def test_fixture_6_paragraph_in_table_abstains_unsupported_context(self):
        body = (
            '<w:tbl><w:tr><w:tc>'
            '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
            '<w:r><w:t>célula</w:t></w:r></w:p>'
            "</w:tc></w:tr></w:tbl>"
        )
        _, _, _, results = classify(body, styles_part(NORMAL))
        (result,) = results
        self.assertEqual(
            (result.status, result.reasons),
            (ClassificationStatus.ABSTAINED, (ClassificationReason.UNSUPPORTED_CONTEXT,)),
        )

    def test_fixture_6b_heading_style_inside_table_still_abstains(self):
        # unsupported_context vetoes an otherwise positive identity (0022 priority)
        body = (
            '<w:tbl><w:tr><w:tc>'
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            '<w:r><w:t>título em tabela</w:t></w:r></w:p>'
            "</w:tc></w:tr></w:tbl>"
        )
        _, _, _, results = classify(body, styles_part(NORMAL + HEADING1))
        (result,) = results
        self.assertEqual(result.reasons, (ClassificationReason.UNSUPPORTED_CONTEXT,))
        self.assertIsNone(result.target_class)

    def test_fixture_7_numbering_warning_abstains_unsupported_context(self):
        body = (
            "<w:p><w:pPr><w:numPr><w:ilvl w:val=\"0\"/><w:numId w:val=\"1\"/>"
            '</w:numPr></w:pPr><w:r><w:t>item</w:t></w:r></w:p>'
        )
        _, _, _, results = classify(body, styles_part(NORMAL))
        (result,) = results
        self.assertEqual(
            (result.status, result.reasons),
            (ClassificationStatus.ABSTAINED, (ClassificationReason.UNSUPPORTED_CONTEXT,)),
        )

    def test_fixture_8_run_inherits_body_with_parent_anchor(self):
        _, ir, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
            '<w:r><w:t>corpo</w:t></w:r></w:p>',
            styles_part(NORMAL),
        )
        (paragraph_result,) = results
        run = first_run(paragraph_blocks(ir)[0])
        run_result = project_run_classification(run, paragraph_result)
        self.assertEqual(run_result.status, ClassificationStatus.CLASSIFIED)
        self.assertEqual(run_result.target_type, "run")
        self.assertEqual(run_result.target_class, TargetClass.BODY)
        self.assertEqual(
            run_result.provenance, ClassificationProvenance.INHERITED_FROM_PARAGRAPH
        )
        self.assertEqual(
            run_result.parent_anchor,
            ParentAnchor(paragraph_result.structural_path, paragraph_result.physical_hash),
        )
        self.assertEqual(run_result.reasons, (ClassificationReason.INHERITED_FROM_PARAGRAPH,))
        # provenance is distinguishable from direct in projection
        projected = project_target_classification(run_result)
        self.assertEqual(projected.provenance, "classification:inherited_from_paragraph")
        self.assertEqual(projected.target_type, "run")

    def test_fixture_9_custom_style_named_like_heading_without_based_on_abstains(self):
        fake = (
            '<w:style w:type="paragraph" w:styleId="Fake" w:customStyle="1">'
            '<w:name w:val="Heading 1"/></w:style>'
        )
        _, _, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="Fake"/></w:pPr>'
            '<w:r><w:t>título falso</w:t></w:r></w:p>',
            styles_part(NORMAL + fake),
        )
        (result,) = results
        self.assertEqual(
            (result.status, result.reasons),
            (ClassificationStatus.ABSTAINED, (ClassificationReason.INSUFFICIENT_EVIDENCE,)),
        )

    def test_fixture_10_reference_section_does_not_activate_reference_class(self):
        body = (
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            '<w:r><w:t>REFERÊNCIAS</w:t></w:r></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
            '<w:r><w:t>SOUZA, J. Título. 2020.</w:t></w:r></w:p>'
        )
        _, _, _, results = classify(body, styles_part(NORMAL + HEADING1))
        heading, entry = results
        self.assertEqual(heading.target_class, TargetClass.HEADING)
        self.assertEqual(entry.target_class, TargetClass.BODY)
        self.assertNotIn(TargetClass.REFERENCE, [r.target_class for r in results])
        self.assertNotIn(TargetClass.LONG_QUOTE, [r.target_class for r in results])


class ClassificationV01ModelInvariants(unittest.TestCase):
    def _result(self, **overrides):
        base = dict(
            classification_version=CLASSIFICATION_VERSION,
            classification_vocabulary_version=CLASSIFICATION_VOCABULARY_VERSION,
            target_type="paragraph",
            structural_path="/w:p[1]",
            physical_hash="h",
            story_id="body",
            status=ClassificationStatus.ABSTAINED,
            target_class=None,
            metadata=(),
            basis=None,
            reasons=(ClassificationReason.INSUFFICIENT_EVIDENCE,),
            evidence=(),
            provenance=ClassificationProvenance.DIRECT,
            parent_anchor=None,
        )
        base.update(overrides)
        return ClassificationResult(**base)

    def _evidence(self):
        return ClassificationEvidence(
            EvidenceSourceKind.FORMATTING_ANALYSIS, "/w:p[1]", "paragraph_style_id",
            "Normal", EvidencePolarity.SUPPORTS, EvidenceStrength.EXPLICIT,
        )

    def test_classified_iff_target_class(self):
        with self.assertRaises(ValueError):
            self._result(status=ClassificationStatus.CLASSIFIED)
        with self.assertRaises(ValueError):
            self._result(target_class=TargetClass.BODY)
        with self.assertRaises(ValueError):
            self._result(status=ClassificationStatus.NOT_APPLICABLE,
                         target_class=TargetClass.BODY,
                         reasons=(ClassificationReason.UNSUPPORTED_STORY,))

    def test_classified_requires_evidence_and_basis(self):
        with self.assertRaises(ValueError):
            self._result(status=ClassificationStatus.CLASSIFIED,
                         target_class=TargetClass.BODY,
                         basis=ClassificationBasis.EXPLICIT,
                         reasons=(ClassificationReason.EXPLICIT_STYLE_SIGNAL,))
        with self.assertRaises(ValueError):
            self._result(status=ClassificationStatus.CLASSIFIED,
                         target_class=TargetClass.BODY,
                         evidence=(self._evidence(),),
                         reasons=(ClassificationReason.EXPLICIT_STYLE_SIGNAL,))

    def test_reason_sets_are_closed_per_status(self):
        with self.assertRaises(ValueError):
            self._result(reasons=(ClassificationReason.EXPLICIT_STYLE_SIGNAL,))
        with self.assertRaises(ValueError):
            self._result(status=ClassificationStatus.NOT_APPLICABLE,
                         reasons=(ClassificationReason.EMPTY_CONTENT,))

    def test_inherited_requires_run_target_and_parent_anchor(self):
        with self.assertRaises(ValueError):
            self._result(provenance=ClassificationProvenance.INHERITED_FROM_PARAGRAPH,
                         parent_anchor=ParentAnchor("/w:p[1]", "h"))
        with self.assertRaises(ValueError):
            self._result(target_type="run",
                         provenance=ClassificationProvenance.INHERITED_FROM_PARAGRAPH,
                         reasons=(ClassificationReason.PARENT_NOT_CLASSIFIED,))
        # direct provenance cannot carry an anchor
        with self.assertRaises(ValueError):
            self._result(parent_anchor=ParentAnchor("/w:p[1]", "h"))

    def test_metadata_must_be_sorted_unique_immutable_scalars(self):
        with self.assertRaises(ValueError):
            self._result(metadata=(("b", 1), ("a", 2)))
        with self.assertRaises(ValueError):
            self._result(metadata=(("a", 1), ("a", 2)))
        with self.assertRaises(TypeError):
            self._result(metadata=(("a", [1]),))

    def test_models_are_frozen(self):
        result = self._result()
        with self.assertRaises(FrozenInstanceError):
            result.status = ClassificationStatus.CLASSIFIED
        evidence = self._evidence()
        with self.assertRaises(FrozenInstanceError):
            evidence.feature = "other"
        anchor = ParentAnchor("/w:p[1]", "h")
        with self.assertRaises(FrozenInstanceError):
            anchor.physical_hash = "x"

    def test_eligibility_is_pure_and_heuristic_never_projects(self):
        classified = self._result(
            status=ClassificationStatus.CLASSIFIED,
            target_class=TargetClass.BODY,
            basis=ClassificationBasis.HEURISTIC,
            evidence=(self._evidence(),),
            reasons=(ClassificationReason.EXPLICIT_STYLE_SIGNAL,),
        )
        self.assertFalse(eligible_for_automatic_use(classified))
        with self.assertRaises(ValueError):
            project_target_classification(classified)


class ClassificationV01Projection(unittest.TestCase):
    def test_only_eligible_results_project(self):
        _, _, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
            '<w:r><w:t>corpo</w:t></w:r></w:p><w:p/>',
            styles_part(NORMAL),
        )
        body_result, empty_result = results
        projected = project_target_classification(body_result)
        self.assertIsInstance(projected, TargetClassification)
        self.assertEqual(
            (projected.target_type, projected.target_class,
             projected.classification_version, projected.provenance),
            ("paragraph", "body", "0.1", "classification:direct"),
        )
        self.assertEqual(projected.structural_path, body_result.structural_path)
        self.assertEqual(projected.physical_hash, body_result.physical_hash)
        with self.assertRaises(ValueError):
            project_target_classification(empty_result)

    def test_projection_does_not_mutate_decision_model(self):
        # TargetClassification keeps its frozen 0021 shape
        _, _, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            '<w:r><w:t>t</w:t></w:r></w:p>',
            styles_part(NORMAL + HEADING1),
        )
        projected = project_target_classification(results[0])
        self.assertEqual(projected.target_class, "heading")
        with self.assertRaises(FrozenInstanceError):
            projected.target_class = "body"


class ClassificationV01Adversarial(unittest.TestCase):
    def test_document_without_recognizable_styles_abstains_everywhere(self):
        customs = (
            '<w:style w:type="paragraph" w:styleId="A" w:customStyle="1">'
            '<w:name w:val="x"/></w:style>'
            '<w:style w:type="paragraph" w:styleId="B" w:customStyle="1">'
            '<w:name w:val="y"/><w:basedOn w:val="A"/></w:style>'
        )
        _, _, _, results = classify(
            '<w:p><w:r><w:t>um</w:t></w:r></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="A"/></w:pPr><w:r><w:t>dois</w:t></w:r></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="B"/></w:pPr><w:r><w:t>três</w:t></w:r></w:p>',
            styles_part(customs),
        )
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.status is ClassificationStatus.ABSTAINED for r in results))
        self.assertTrue(
            all(r.reasons == (ClassificationReason.INSUFFICIENT_EVIDENCE,) for r in results)
        )

    def test_document_without_styles_part_abstains(self):
        _, _, _, results = classify(
            '<w:p><w:r><w:t>sem estilos</w:t></w:r></w:p>', None
        )
        (result,) = results
        self.assertEqual(result.status, ClassificationStatus.ABSTAINED)
        self.assertEqual(result.reasons, (ClassificationReason.INSUFFICIENT_EVIDENCE,))

    def test_builtin_id_with_custom_flag_does_not_classify_directly(self):
        evil = (
            '<w:style w:type="paragraph" w:styleId="Heading1" w:customStyle="1">'
            '<w:name w:val="forjado"/></w:style>'
        )
        _, _, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            '<w:r><w:t>forjado</w:t></w:r></w:p>',
            styles_part(evil),
        )
        (result,) = results
        self.assertEqual(result.status, ClassificationStatus.ABSTAINED)

    def test_bodytext_is_not_admitted_in_identity_map_v01(self):
        # audited item 28: BodyText identity is not verifiable in the available
        # evidence base, so the v0.1 map deliberately excludes it
        bt = (
            '<w:style w:type="paragraph" w:styleId="BodyText">'
            '<w:name w:val="Body Text"/></w:style>'
        )
        _, _, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>'
            '<w:r><w:t>corpo</w:t></w:r></w:p>',
            styles_part(bt),
        )
        (result,) = results
        self.assertEqual(result.status, ClassificationStatus.ABSTAINED)

    def test_based_on_cycle_never_classifies(self):
        cycle = (
            '<w:style w:type="paragraph" w:styleId="A" w:customStyle="1">'
            '<w:name w:val="a"/><w:basedOn w:val="B"/></w:style>'
            '<w:style w:type="paragraph" w:styleId="B" w:customStyle="1">'
            '<w:name w:val="b"/><w:basedOn w:val="A"/></w:style>'
        )
        _, _, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="A"/></w:pPr><w:r><w:t>ciclo</w:t></w:r></w:p>',
            styles_part(cycle),
        )
        (result,) = results
        self.assertEqual(
            (result.status, result.reasons),
            (ClassificationStatus.ABSTAINED, (ClassificationReason.INSUFFICIENT_EVIDENCE,)),
        )

    def test_dangling_style_reference_abstains_without_duplicate_warning(self):
        _, _, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="Inexistente"/></w:pPr>'
            '<w:r><w:t>quebrado</w:t></w:r></w:p>',
            styles_part(NORMAL),
        )
        (result,) = results
        self.assertEqual(result.status, ClassificationStatus.ABSTAINED)
        # Analysis already emitted formatting_missing_style; classification
        # must not duplicate it (briefing item 37)
        self.assertEqual(result.classification_warnings, ())

    def test_reason_priority_empty_beats_unsupported_context(self):
        body = '<w:tbl><w:tr><w:tc><w:p/></w:tc></w:tr></w:tbl>'
        _, _, _, results = classify(body, styles_part(NORMAL))
        (result,) = results
        self.assertEqual(result.reasons, (ClassificationReason.EMPTY_CONTENT,))

    def test_secondary_story_is_not_applicable(self):
        header = (
            f'<w:hdr xmlns:w="{W_NS}">'
            '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
            '<w:r><w:t>cabeçalho</w:t></w:r></w:p></w:hdr>'
        )
        _, _, _, results = classify(
            '<w:p><w:r><w:t>corpo</w:t></w:r></w:p>',
            styles_part(NORMAL),
            extra_parts={"word/header1.xml": header},
            story_rels=[("rId9", "header", "header1.xml")],
        )
        by_story = {r.story_id: r for r in results}
        self.assertEqual(by_story["body"].status, ClassificationStatus.CLASSIFIED)
        header_result = by_story["header:word/header1.xml"]
        self.assertEqual(
            (header_result.status, header_result.reasons),
            (ClassificationStatus.NOT_APPLICABLE,
             (ClassificationReason.UNSUPPORTED_STORY,)),
        )
        with self.assertRaises(ValueError):
            project_target_classification(header_result)

    def test_partial_abstention_does_not_take_down_other_blocks(self):
        _, _, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            '<w:r><w:t>título</w:t></w:r></w:p>'
            "<w:p/>"
            '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
            '<w:r><w:t>corpo</w:t></w:r></w:p>',
            styles_part(NORMAL + HEADING1),
        )
        self.assertEqual(
            [r.status for r in results],
            [ClassificationStatus.CLASSIFIED, ClassificationStatus.ABSTAINED,
             ClassificationStatus.CLASSIFIED],
        )

    def test_run_of_non_classified_paragraph_gets_parent_not_classified(self):
        _, ir, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="Fake"/></w:pPr>'
            '<w:r><w:t>texto</w:t></w:r></w:p>',
            styles_part(
                '<w:style w:type="paragraph" w:styleId="Fake" w:customStyle="1">'
                '<w:name w:val="Normal"/></w:style>'
            ),
        )
        (paragraph_result,) = results
        run = first_run(paragraph_blocks(ir)[0])
        run_result = project_run_classification(run, paragraph_result)
        self.assertEqual(
            (run_result.status, run_result.reasons),
            (ClassificationStatus.NOT_APPLICABLE,
             (ClassificationReason.PARENT_NOT_CLASSIFIED,)),
        )
        self.assertIsNone(run_result.target_class)
        with self.assertRaises(ValueError):
            project_target_classification(run_result)

    def test_broken_analysis_binding_is_contract_error_not_abstention(self):
        _, ir, catalog, _ = classify(
            '<w:p><w:r><w:t>corpo</w:t></w:r></w:p>', styles_part(NORMAL)
        )
        broken = dict(ir)
        broken["stories"] = [dict(ir["stories"][0])]
        broken["stories"][0]["blocks"] = [
            {"source_type": "paragraph", "children": []}  # no provenance
        ]
        with self.assertRaises(ValueError):
            classify_document(broken, catalog)

    def test_classifier_does_not_import_normative_profile_or_raw_ooxml(self):
        import ast

        import formatador_academico.classification.classifier as clf
        import formatador_academico.classification.identity as ident
        import formatador_academico.classification.model as model
        import formatador_academico.classification.projection as proj
        import formatador_academico.classification.serialization as ser

        def imported_modules(module):
            tree = ast.parse(inspect.getsource(module))
            names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names.update(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    base = node.module.rsplit("formatador_academico.", 1)[-1]
                    for alias in node.names:
                        names.add(f"{base}.{alias.name}")
            return names

        forbidden = (
            "lxml", "lxml.etree",
            "decision.engine", "decision.model.FormattingRule",
            "decision.model.ValidatedProfile", "decision.model.ProfileRef",
            "decision.model.FormattingRule",
        )
        for module in (clf, ident, model, proj, ser):
            names = imported_modules(module)
            for token in forbidden:
                self.assertNotIn(token, names, f"{module.__name__} imports {token}")
        # classifier, identity and model do not touch the Decision Layer at all;
        # only projection may, and only for the frozen TargetClassification
        for module in (clf, ident, model):
            self.assertFalse(
                any(n.startswith("decision") for n in imported_modules(module))
            )
        self.assertIn("decision.model.TargetClassification", imported_modules(proj))

    def test_inputs_are_not_mutated(self):
        import copy

        pkg = build_docx(
            document('<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
                     '<w:r><w:t>t</w:t></w:r></w:p>'),
            styles_part(NORMAL + HEADING1),
        )
        ir = DocxParser().parse_bytes(pkg)
        catalog = build_style_catalog(pkg, ir)
        ir_before = copy.deepcopy(ir)
        catalog_before = serialize_style_catalog(catalog)
        classify_document(ir, catalog)
        self.assertEqual(ir, ir_before)
        self.assertEqual(serialize_style_catalog(catalog), catalog_before)

    def test_same_process_serialization_is_byte_stable(self):
        _, _, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            '<w:r><w:t>t</w:t></w:r></w:p><w:p/>',
            styles_part(NORMAL + HEADING1),
        )
        self.assertEqual(
            serialize_classification_results(results),
            serialize_classification_results(results),
        )
        blob = serialize_classification_result(results[0])
        self.assertIn(b'"classification_version":"0.1"', blob)
        self.assertIn(b'"classification_vocabulary_version":"0.1"', blob)

    def test_run_of_different_paragraph_never_inherits_class(self):
        # Audit item 23 (parent binding): a run of paragraph A presented with
        # the classification of paragraph B is a contract error, never a
        # silent inheritance of a foreign class.
        _, ir, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
            '<w:r><w:t>corpo</w:t></w:r></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            '<w:r><w:t>titulo</w:t></w:r></w:p>',
            styles_part(NORMAL + HEADING1),
        )
        body_result, heading_result = results
        run_of_body = first_run(paragraph_blocks(ir)[0])
        with self.assertRaises(ValueError):
            project_run_classification(run_of_body, heading_result)
        # the correct parent still projects fine
        ok = project_run_classification(
            first_run(paragraph_blocks(ir)[1]), heading_result
        )
        self.assertEqual(ok.target_class, TargetClass.HEADING)
        self.assertEqual(
            ok.parent_anchor,
            ParentAnchor(heading_result.structural_path, heading_result.physical_hash),
        )

    def test_run_mismatch_detection_is_not_fooled_by_prefix_siblings(self):
        # /w:p[1] must not accept runs of /w:p[10+]: the separator-aware
        # prefix check guards against naive startswith binding.
        paragraphs = "".join(
            '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
            f'<w:r><w:t>p{n}</w:t></w:r></w:p>'
            for n in range(12)
        )
        _, ir, _, results = classify(paragraphs, styles_part(NORMAL))
        run_of_p12 = first_run(paragraph_blocks(ir)[11])
        with self.assertRaises(ValueError):
            project_run_classification(run_of_p12, results[0])

    def test_multi_hop_based_on_chain_inherits_terminal_builtin_level(self):
        styles = NORMAL + (
            '<w:style w:type="paragraph" w:styleId="Heading2">'
            '<w:name w:val="h2"/><w:basedOn w:val="Normal"/></w:style>'
            '<w:style w:type="paragraph" w:styleId="C1" w:customStyle="1">'
            '<w:name w:val="c1"/><w:basedOn w:val="C2"/></w:style>'
            '<w:style w:type="paragraph" w:styleId="C2" w:customStyle="1">'
            '<w:name w:val="c2"/><w:basedOn w:val="Heading2"/></w:style>'
        )
        _, _, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="C1"/></w:pPr>'
            '<w:r><w:t>multi-hop</w:t></w:r></w:p>',
            styles_part(styles),
        )
        (result,) = results
        self.assertEqual(result.status, ClassificationStatus.CLASSIFIED)
        self.assertEqual(result.target_class, TargetClass.HEADING)
        # level is the terminal built-in's, never invented mid-chain
        self.assertEqual(result.metadata, (("level", 2),))

    def test_based_on_chain_crossing_non_paragraph_style_never_classifies(self):
        # Audit item 13: basedOn is normatively same-type; a chain that hops
        # through a character style has crossed a type boundary and its
        # identity is not verifiable, even if it later reaches Heading1.
        styles = NORMAL + HEADING1 + (
            '<w:style w:type="character" w:styleId="CharX" w:customStyle="1">'
            '<w:name w:val="cx"/><w:basedOn w:val="Heading1"/></w:style>'
            '<w:style w:type="paragraph" w:styleId="Evil" w:customStyle="1">'
            '<w:name w:val="evil"/><w:basedOn w:val="CharX"/></w:style>'
        )
        _, _, catalog, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="Evil"/></w:pPr>'
            '<w:r><w:t>contaminado</w:t></w:r></w:p>',
            styles_part(styles),
        )
        (result,) = results
        self.assertEqual(result.status, ClassificationStatus.ABSTAINED)
        self.assertIsNone(result.target_class)
        resolution = resolve_style_identity(catalog, "Evil")
        self.assertEqual(resolution.outcome, IdentityOutcome.BROKEN_CHAIN)

    def test_pstyle_pointing_to_non_paragraph_style_abstains(self):
        # wrong style_type at the requested id itself: no identity governs
        styles = NORMAL + (
            '<w:style w:type="character" w:styleId="Heading1" w:customStyle="1">'
            '<w:name w:val="forjado"/></w:style>'
        )
        _, _, _, results = classify(
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            '<w:r><w:t>tipo errado</w:t></w:r></w:p>',
            styles_part(styles),
        )
        (result,) = results
        self.assertEqual(result.status, ClassificationStatus.ABSTAINED)
        self.assertIsNone(result.target_class)

    def test_identity_resolution_reports_broken_chain(self):
        _, _, catalog, _ = classify(
            '<w:p><w:r><w:t>x</w:t></w:r></w:p>', styles_part(NORMAL)
        )
        resolution = resolve_style_identity(catalog, "Ghost")
        self.assertEqual(resolution.outcome, IdentityOutcome.BROKEN_CHAIN)
        self.assertIsNone(resolution.target_class)


if __name__ == "__main__":
    unittest.main()
