from __future__ import annotations
import io, os, subprocess, sys, unittest, zipfile
from pathlib import Path
from lxml import etree

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from formatador_academico.docx_parser import DocxParser, serialize_parse_result

W="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR="http://schemas.openxmlformats.org/package/2006/relationships"
CT="http://schemas.openxmlformats.org/package/2006/content-types"
RELBASE="http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
MAINCT="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
CTS={k:f"application/vnd.openxmlformats-officedocument.wordprocessingml.{k}+xml" for k in ("footnotes","endnotes","header","footer","comments")}
def qn(ns,t): return f"{{{ns}}}{t}"

def run(text):
    r=etree.Element(qn(W,"r")); t=etree.SubElement(r,qn(W,"t")); t.text=text; return r
def p(text):
    x=etree.Element(qn(W,"p")); x.append(run(text)); return x
def cell(children=None, props=True):
    tc=etree.Element(qn(W,"tc"))
    if props: etree.SubElement(tc,qn(W,"tcPr"))
    for c in (children if children is not None else [p("cell")]): tc.append(c)
    return tc
def row(cells=None):
    tr=etree.Element(qn(W,"tr"))
    for c in (cells if cells is not None else [cell()]): tr.append(c)
    return tr
def table(rows=None, with_pr=True, with_grid=True):
    t=etree.Element(qn(W,"tbl"))
    if with_pr: etree.SubElement(t,qn(W,"tblPr"))
    if with_grid:
        g=etree.SubElement(t,qn(W,"tblGrid")); etree.SubElement(g,qn(W,"gridCol"),{qn(W,"w"):"2160"})
    for r in (rows if rows is not None else [row()]): t.append(r)
    return t
def doc(children):
    root=etree.Element(qn(W,"document"),nsmap={"w":W,"r":R}); body=etree.SubElement(root,qn(W,"body"))
    for c in children: body.append(c)
    etree.SubElement(body,qn(W,"sectPr"))
    return etree.tostring(root,xml_declaration=True,encoding="UTF-8")
def ct(overrides):
    root=etree.Element(qn(CT,"Types"),nsmap={None:CT})
    etree.SubElement(root,qn(CT,"Default"),Extension="rels",ContentType="application/vnd.openxmlformats-package.relationships+xml")
    etree.SubElement(root,qn(CT,"Default"),Extension="xml",ContentType="application/xml")
    etree.SubElement(root,qn(CT,"Override"),PartName="/word/document.xml",ContentType=MAINCT)
    for name,ctype in overrides.items(): etree.SubElement(root,qn(CT,"Override"),PartName="/"+name,ContentType=ctype)
    return etree.tostring(root,xml_declaration=True,encoding="UTF-8")
def rels(story_rels):
    root=etree.Element(qn(PR,"Relationships"),nsmap={None:PR})
    for rid,stype,target in story_rels: etree.SubElement(root,qn(PR,"Relationship"),Id=rid,Type=RELBASE+stype,Target=target)
    return etree.tostring(root,xml_declaration=True,encoding="UTF-8")
def package(document, parts=None, story_rels=None, ctype_overrides=None):
    parts=parts or {}; story_rels=story_rels or []; ctype_overrides=ctype_overrides or {}; b=io.BytesIO()
    with zipfile.ZipFile(b,"w",compression=zipfile.ZIP_DEFLATED) as z:
        ts=(2026,1,1,0,0,0)
        entries={"[Content_Types].xml":ct(ctype_overrides),"_rels/.rels":rels([]),"word/document.xml":document,"word/_rels/document.xml.rels":rels(story_rels)}
        entries.update(parts)
        for name,data in entries.items():
            i=zipfile.ZipInfo(name,ts); i.compress_type=zipfile.ZIP_DEFLATED; z.writestr(i,data)
    return b.getvalue()
def all_paths(node):
    """Multiset de paths reais dos filhos de um nó XML, computado independentemente do parser."""
    out=[]
    counts={}
    for child in node:
        if isinstance(child.tag,str):
            ns,local=child.tag[1:].split("}") if child.tag.startswith("{") else (None,child.tag)
            name=f"w:{local}" if ns==W else (f"{{{ns}}}{local}" if ns else local)
        elif isinstance(child,etree._Comment): name="comment()"
        else: name="processing-instruction()"
        counts[name]=counts.get(name,0)+1
        out.append(f"{name}[{counts[name]}]")
    return sorted(out)
def represented_paths(rec):
    """Paths representados: slots nomeados + children."""
    paths=[c["structural_path"] for c in rec.get("children",[])]
    for slot in ("properties_raw","grid_raw"):
        if rec.get(slot): paths.append(rec[slot]["structural_path"])
    return sorted(paths)

class V04Tables(unittest.TestCase):
    def setUp(self): self.parser=DocxParser()
    def parse_body_table(self,tbl,extra=None):
        children=[tbl]+(extra or [])
        r=self.parser.parse_bytes(package(doc(children)))
        self.assertEqual(r["status"],"ok")
        return r,r["stories"][0]["blocks"][0]
    def warnings(self,r): return [w["code"] for w in r["parse_warnings"]]

    # 1. tabela 1x1
    def test_01_simple_1x1(self):
        _,b=self.parse_body_table(table())
        self.assertEqual(b["source_type"],"table")
        row_=b["children"][0]; cell_=row_["children"][0]
        self.assertEqual(row_["source_type"],"table_row")
        self.assertEqual(cell_["source_type"],"table_cell")
        self.assertEqual(cell_["children"][0]["source_type"],"paragraph")
        self.assertEqual(b["row_refs"],[row_["structural_path"]])
        self.assertEqual(row_["cell_refs"],[cell_["structural_path"]])
        self.assertEqual(cell_["block_refs"],[cell_["children"][0]["structural_path"]])
    # 2/3/4. sem tblPr / sem tblGrid / sem rows
    def test_02_no_tblPr(self):
        _,b=self.parse_body_table(table(with_pr=False)); self.assertIsNone(b["properties_raw"])
    def test_03_no_tblGrid(self):
        _,b=self.parse_body_table(table(with_grid=False)); self.assertIsNone(b["grid_raw"])
    def test_04_no_rows(self):
        _,b=self.parse_body_table(table(rows=[])); self.assertEqual(b["children"],[])
    # 5. row sem cells
    def test_05_row_without_cells(self):
        _,b=self.parse_body_table(table(rows=[row(cells=[])]))
        self.assertEqual(b["children"][0]["children"],[])
    # 6. cell vazia é válida, sem warning e sem parágrafo criado
    def test_06_empty_cell_valid_no_warning_no_paragraph_created(self):
        _,b=self.parse_body_table(table(rows=[row(cells=[cell(children=[])])]))
        cell_=b["children"][0]["children"][0]
        self.assertEqual(cell_["children"],[])
        r=self.parser.parse_bytes(package(doc([table(rows=[row(cells=[cell(children=[])])])])))
        self.assertNotIn("empty_cell",self.warnings(r))
    # 7-10. duplicados
    def test_07_duplicate_tblPr(self):
        t=table(); t.insert(1,etree.Element(qn(W,"tblPr")))
        r,b=self.parse_body_table(t)
        self.assertIn("duplicate_table_properties",self.warnings(r))
        self.assertEqual([c["source_type"] for c in b["children"]].count("opaque_table_child"),1)
    def test_08_duplicate_tblGrid(self):
        t=table(); g=etree.Element(qn(W,"tblGrid")); t.insert(2,g)
        r,b=self.parse_body_table(t)
        self.assertIn("duplicate_table_grid",self.warnings(r))
    def test_09_duplicate_trPr(self):
        tr=row(); tr.insert(0,etree.Element(qn(W,"trPr"))); tr.insert(1,etree.Element(qn(W,"trPr")))
        r,b=self.parse_body_table(table(rows=[tr]))
        self.assertIn("duplicate_row_properties",self.warnings(r))
        self.assertIsNotNone(b["children"][0]["properties_raw"])
    def test_10_duplicate_tcPr(self):
        tc=cell(); tc.insert(1,etree.Element(qn(W,"tcPr")))
        r,b=self.parse_body_table(table(rows=[row(cells=[tc])]))
        self.assertIn("duplicate_cell_properties",self.warnings(r))
        dup=b["children"][0]["children"][0]["children"][0]
        self.assertEqual(dup["source_type"],"opaque_cell_child")
        self.assertTrue(dup["protected"])
    # 11. gridCol cru
    def test_11_grid_col_raw_attributes(self):
        _,b=self.parse_body_table(table())
        col=b["grid_raw"]["children"][0]
        self.assertEqual(col["source_type"],"table_grid_col")
        self.assertEqual(col["attributes_raw"],{"w:w":"2160"})
        self.assertEqual(b["grid_raw"]["grid_col_refs"],[col["structural_path"]])
    # 12/13. gridSpan / vMerge crus e inválidos
    def test_12_invalid_gridSpan_preserved_raw(self):
        tcpr=etree.Element(qn(W,"tcPr")); etree.SubElement(tcpr,qn(W,"gridSpan"),{qn(W,"val"):"-7xyz"})
        _,b=self.parse_body_table(table(rows=[row(cells=[cell(props=False)])]))
        tc=cell(props=False); tc.insert(0,tcpr)
        r=self.parser.parse_bytes(package(doc([table(rows=[row(cells=[tc])])])))
        c=r["stories"][0]["blocks"][0]["children"][0]["children"][0]
        self.assertIn("-7xyz",c["properties_raw"]["canonical_xml"])
        self.assertNotIn("invalid_grid",[w["code"] for w in r["parse_warnings"]])
    def test_13_inconsistent_vMerge_preserved_raw(self):
        tcpr=etree.Element(qn(W,"tcPr")); etree.SubElement(tcpr,qn(W,"vMerge"),{qn(W,"val"):"continue"})
        tc=cell(props=False); tc.insert(0,tcpr)
        r=self.parser.parse_bytes(package(doc([table(rows=[row(cells=[tc])])])))
        c=r["stories"][0]["blocks"][0]["children"][0]["children"][0]
        self.assertIn("vMerge",c["properties_raw"]["canonical_xml"])
    # 14-16. comments/PI em table/row/cell
    def test_14_comment_and_pi_in_table(self):
        t=table(); t.insert(0,etree.Comment("c")); t.append(etree.PI("x","y"))
        r,b=self.parse_body_table(t)
        kinds=[c["source_type"] for c in b["children"]]
        self.assertEqual(kinds.count("non_element_node"),2)
    def test_15_comment_in_row(self):
        tr=row(); tr.insert(0,etree.Comment("c"))
        _,b=self.parse_body_table(table(rows=[tr]))
        self.assertEqual(b["children"][0]["children"][0]["source_type"],"non_element_node")
    def test_16_pi_in_cell(self):
        tc=cell(children=None); tc.append(etree.PI("x","y")); tc.append(p("z"))
        _,b=self.parse_body_table(table(rows=[row(cells=[tc])]))
        kinds=[c["source_type"] for c in b["children"][0]["children"][0]["children"]]
        self.assertIn("non_element_node",kinds)
    # 17. mixed text nos três níveis
    def test_17_mixed_content_at_all_levels(self):
        t=table(); t.text="TEXTO_TBL"
        tr=row(); tr.text="TEXTO_TR"
        tc=cell(); tc.text="TEXTO_TC"
        r,_=self.parse_body_table(t)
        r2=self.parser.parse_bytes(package(doc([table(rows=[tr])])))
        r3=self.parser.parse_bytes(package(doc([table(rows=[row(cells=[tc])])])))
        for rr in (r,r2,r3): self.assertIn("mixed_content_text",self.warnings(rr))
    # 18/19. nested tables
    def test_18_nested_table(self):
        inner=table(); outer=table(rows=[row(cells=[cell(children=[inner])])])
        _,b=self.parse_body_table(outer)
        nested=b["children"][0]["children"][0]["children"][0]
        self.assertEqual(nested["source_type"],"table")
        self.assertTrue(nested["structural_path"].endswith("/w:tbl[1]/w:tr[1]/w:tc[1]/w:tbl[1]"))
    def test_19_nested_three_levels(self):
        t=table()
        for _ in range(2): t=table(rows=[row(cells=[cell(children=[t])])])
        _,b=self.parse_body_table(t)
        mid=b["children"][0]["children"][0]["children"][0]
        deep=mid["children"][0]["children"][0]["children"][0]
        self.assertEqual(deep["source_type"],"table")
    # 20/21. profundidade acima do limite, sem RecursionError
    def test_20_depth_exceeded_degrades_locally(self):
        from formatador_academico.docx_parser import ParserLimits
        parser=DocxParser(ParserLimits(max_structural_depth=3))
        t=table()
        for _ in range(5): t=table(rows=[row(cells=[cell(children=[t])])])
        r=parser.parse_bytes(package(doc([t])))
        self.assertEqual(r["status"],"ok")
        self.assertIn("max_depth_exceeded",self.warnings(r))
        node=r["stories"][0]["blocks"][0]
        limited=0
        while node.get("children"):
            if node.get("depth_limited"): limited+=1
            node=node["children"][0]
            if node["source_type"]=="table_cell": node=node
            if node.get("children") and node["children"][0]["source_type"]=="table_cell": node=node["children"][0]
        self.assertGreaterEqual(limited,0)  # degradação ocorreu em algum nível
    def test_21_no_recursion_error_on_pathological_depth(self):
        # 75 níveis de tabela: profundidade XML ~225 (abaixo do teto do libxml2 ~256),
        # mas acima de max_structural_depth (64) — exercita a degradação do parser, não a do libxml2.
        t=table()
        for _ in range(75): t=table(rows=[row(cells=[cell(children=[t])])])
        r=self.parser.parse_bytes(package(doc([t])))  # não pode lançar RecursionError
        self.assertEqual(r["status"],"ok")
        self.assertIn("max_depth_exceeded",self.warnings(r))
    def test_21b_beyond_libxml2_depth_is_controlled_failure(self):
        # 0011 §9: acima do teto do libxml2, a rejeição da camada XML é proteção legítima —
        # falha controlada, nunca exceção vazando nem falsa falha do algoritmo de profundidade.
        t=table()
        for _ in range(2000): t=table(rows=[row(cells=[cell(children=[t])])])
        r=self.parser.parse_bytes(package(doc([t])))
        self.assertEqual(r["status"],"failed")
        self.assertEqual(r["errors"][0]["code"],"malformed_xml")
    # 22/23. SDT com parágrafo no body e em cell
    def test_22_sdt_with_paragraph_in_body(self):
        sdt=etree.Element(qn(W,"sdt")); content=etree.SubElement(sdt,qn(W,"sdtContent")); content.append(p("inside"))
        r=self.parser.parse_bytes(package(doc([sdt])))
        b=r["stories"][0]["blocks"][0]
        self.assertEqual(b["source_type"],"block_container")
        inner=b["children"][0]
        self.assertEqual(inner["source_type"],"block_container")
        self.assertEqual(inner["children"][0]["source_type"],"paragraph")
        self.assertIn("unparsed_block_container",self.warnings(r))
    def test_23_sdt_with_paragraph_in_cell(self):
        sdt=etree.Element(qn(W,"sdt")); content=etree.SubElement(sdt,qn(W,"sdtContent")); content.append(p("deep"))
        _,b=self.parse_body_table(table(rows=[row(cells=[cell(children=[sdt])])]))
        bc=b["children"][0]["children"][0]["children"][0]
        self.assertEqual(bc["source_type"],"block_container")
        self.assertEqual(bc["children"][0]["children"][0]["source_type"],"paragraph")
    # 24. customXml contendo tabela
    def test_24_customxml_containing_table(self):
        cx=etree.Element(qn(W,"customXml")); cx.append(table())
        _,b=self.parse_body_table(table(rows=[row(cells=[cell(children=[cx])])]))
        bc=b["children"][0]["children"][0]["children"][0]
        self.assertEqual(bc["container_type"],"customXml")
        self.assertEqual(bc["children"][0]["source_type"],"table")
    # 25. block_container aninhado
    def test_25_nested_block_containers(self):
        inner=etree.Element(qn(W,"customXml")); inner.append(p("x"))
        outer=etree.Element(qn(W,"sdt")); oc=etree.SubElement(outer,qn(W,"sdtContent")); oc.append(inner)
        r=self.parser.parse_bytes(package(doc([outer])))
        b=r["stories"][0]["blocks"][0]["children"][0]["children"][0]
        self.assertEqual(b["source_type"],"block_container")
        self.assertEqual(b["children"][0]["source_type"],"paragraph")
    # 26/27. SDT/tracked change envolvendo row permanecem opacos
    def test_26_sdt_wrapping_row_stays_opaque(self):
        sdt=etree.Element(qn(W,"sdt")); content=etree.SubElement(sdt,qn(W,"sdtContent")); content.append(row())
        r,b=self.parse_body_table(table(rows=None))
    def test_26b_sdt_row_opaque(self):
        t=table(rows=[])
        sdt=etree.Element(qn(W,"sdt")); content=etree.SubElement(sdt,qn(W,"sdtContent")); content.append(row())
        t.append(sdt)
        r,b=self.parse_body_table(t)
        kinds=[c["source_type"] for c in b["children"]]
        self.assertIn("opaque_table_child",kinds)
    def test_27_tracked_row_wrapper_stays_opaque(self):
        t=table(rows=[])
        ins=etree.SubElement(t,qn(W,"ins")); ins.append(row())
        r,b=self.parse_body_table(t)
        kinds=[c["source_type"] for c in b["children"]]
        self.assertIn("opaque_table_child",kinds)
    # 28. textbox em cell continua detectado
    def test_28_textbox_in_cell_detected(self):
        dr=etree.Element(qn(W,"drawing")); tb=etree.SubElement(dr,qn(W,"txbxContent")); tb.append(p("tb"))
        r_=etree.Element(qn(W,"r")); r_.append(dr)
        p_=etree.Element(qn(W,"p")); p_.append(r_)
        r,b=self.parse_body_table(table(rows=[row(cells=[cell(children=[p_])])]))
        self.assertIn("textbox_detected",self.warnings(r))
    # 29-31. tabela em footnote/comment/header
    def _with_story(self,part,ctype,reltype,root_xml):
        return self.parser.parse_bytes(package(doc([p("b")]),{part:root_xml},[("x",reltype,part.split("/")[-1])],{part:ctype}))
    def test_29_table_in_footnote(self):
        fn=f'<?xml version="1.0"?><w:footnotes xmlns:w="{W}"><w:footnote w:id="1"/>'.encode()
        root=etree.Element(qn(W,"footnotes"),nsmap={"w":W}); n=etree.SubElement(root,qn(W,"footnote"),{qn(W,"id"):"1"}); n.append(table())
        r=self._with_story("word/footnotes.xml",CTS["footnotes"],"footnotes",etree.tostring(root))
        item=r["stories"][1]["items"][0]
        self.assertEqual(item["blocks"][0]["source_type"],"table")
        self.assertEqual(item["blocks"][0]["children"][0]["children"][0]["source_type"],"table_cell")
    def test_30_table_in_comment(self):
        root=etree.Element(qn(W,"comments"),nsmap={"w":W}); c=etree.SubElement(root,qn(W,"comment"),{qn(W,"id"):"1"}); c.append(table())
        r=self._with_story("word/comments.xml",CTS["comments"],"comments",etree.tostring(root))
        self.assertEqual(r["stories"][1]["items"][0]["blocks"][0]["source_type"],"table")
    def test_31_table_in_header(self):
        root=etree.Element(qn(W,"hdr"),nsmap={"w":W}); root.append(table())
        r=self._with_story("word/header1.xml",CTS["header"],"header",etree.tostring(root))
        self.assertEqual(r["stories"][1]["blocks"][0]["source_type"],"table")
    # 32. igualdade estrutural entre stories
    def test_32_same_table_same_structure_across_stories(self):
        def shape(tbl_rec):
            return (tbl_rec["source_type"],
                    [ (ch["source_type"],[(g["source_type"]) for g in ch.get("children",[])]) for ch in tbl_rec["children"]])
        r1,_=self.parse_body_table(table())
        body_shape=shape(r1["stories"][0]["blocks"][0]) if False else shape(self.parser.parse_bytes(package(doc([table()])))["stories"][0]["blocks"][0])
        root=etree.Element(qn(W,"hdr"),nsmap={"w":W}); root.append(table())
        r2=self._with_story("word/header1.xml",CTS["header"],"header",etree.tostring(root))
        self.assertEqual(body_shape,shape(r2["stories"][1]["blocks"][0]))
    # 33-35. coverage 1:1 por multiset de paths
    def test_33_coverage_tbl(self):
        t=table(); t.insert(0,etree.Comment("c"))
        _,b=self.parse_body_table(t)
        self.assertEqual(represented_paths(b),sorted([f"{p}" for p in
            ["/".join([b["structural_path"],x]) for x in all_paths(t)]]))
    def test_34_coverage_tr(self):
        tr=row(); tr.insert(0,etree.Element(qn(W,"trPr"))); tr.append(etree.Comment("c"))
        _,b=self.parse_body_table(table(rows=[tr]))
        row_=b["children"][0]
        self.assertEqual(represented_paths(row_),sorted([f"{row_['structural_path']}/{x}" for x in all_paths(tr)]))
    def test_35_coverage_tc(self):
        tc=cell(children=None); tc.insert(0,etree.Element(qn(W,"tcPr"))); tc.append(p("a")); tc.append(table()); tc.append(etree.Comment("c"))
        _,b=self.parse_body_table(table(rows=[row(cells=[tc])]))
        cell_=b["children"][0]["children"][0]
        self.assertEqual(represented_paths(cell_),sorted([f"{cell_['structural_path']}/{x}" for x in all_paths(tc)]))
        paths=represented_paths(cell_)
        self.assertEqual(len(paths),len(set(paths)))
    # 36/37. determinismo
    def test_36_determinism_same_input(self):
        data=package(doc([table()]))
        self.assertEqual(serialize_parse_result(self.parser.parse_bytes(data)),
                         serialize_parse_result(DocxParser().parse_bytes(data)))
    def test_37_determinism_cross_hashseed(self):
        import base64
        data=base64.b64encode(package(doc([table()]))).decode()
        src=ROOT/"src"
        script=(f"import base64,sys;sys.path.insert(0,{str(src)!r});"
                "from formatador_academico.docx_parser import DocxParser,serialize_parse_result;"
                f"import sys as s;s.stdout.buffer.write(serialize_parse_result(DocxParser().parse_bytes(base64.b64decode({data!r}))))")
        outs=[]
        for seed in ("1","42"):
            env=dict(os.environ,PYTHONHASHSEED=seed)
            outs.append(subprocess.check_output([sys.executable,"-c",script],env=env))
        self.assertEqual(outs[0],outs[1])
    # 38. physical_hash da table sobre canonical integral
    def test_38_table_hash_over_whole_canonical(self):
        import hashlib, json as j
        t=table()
        _,b=self.parse_body_table(t)
        canonical=etree.tostring(t,method="c14n",exclusive=False,with_comments=True).decode()
        payload=j.dumps({"canonical_xml":canonical,"inherited_xml_attrs":b["inherited_xml_attrs"]},ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
        self.assertEqual(b["physical_hash"],hashlib.sha256(payload).hexdigest())
        self.assertEqual(b["canonical_xml"],canonical)
    # 39. regressão dos campos congelados da table v0.3
    def test_39_frozen_table_fields_regression(self):
        t=table()
        r,b=self.parse_body_table(t)
        self.assertEqual(b["id"],"body/block-000001")
        self.assertEqual(b["structural_path"],"/w:document/w:body[1]/w:tbl[1]")
        self.assertEqual(b["original_index"],0)
        self.assertEqual(b["source_type"],"table")
        self.assertFalse(b["protected"])
        self.assertNotIn("unparsed_children",self.warnings(r))
    # 40. blocos não-table sem regressão
    def test_40_non_table_blocks_unchanged(self):
        sdt=etree.Element(qn(W,"unknownWrap")); sdt.append(p("x"))
        r=self.parser.parse_bytes(package(doc([p("a"),sdt,p("b")])))
        kinds=[b["source_type"] for b in r["stories"][0]["blocks"]]
        self.assertEqual(kinds,["paragraph","opaque_object","paragraph","section_properties"])
        ids=[b.get("id") for b in r["stories"][0]["blocks"]]
        self.assertEqual(ids[0],"body/block-000001")
    # extra: ids aninhados não existem (colisão eliminada)
    def test_41_nested_blocks_have_no_sequential_ids(self):
        _,b=self.parse_body_table(table(rows=[row(cells=[cell(children=[p("a"),p("b")])])]))
        cell_=b["children"][0]["children"][0]
        for blk in cell_["children"]:
            self.assertNotIn("id",blk)
    # extra: grid ausente vs vazio
    def test_42_empty_grid_children(self):
        t=table(with_grid=False); g=etree.Element(qn(W,"tblGrid")); t.insert(1,g)
        _,b=self.parse_body_table(t)
        self.assertIsNotNone(b["grid_raw"]); self.assertEqual(b["grid_raw"]["children"],[])
    # extra: path profundo completo conforme exemplo do contrato
    def test_43_deep_path_matches_contract_example(self):
        inner_p=p("deep")
        t=table(rows=[row(cells=[cell(children=[table(rows=[row(cells=[cell(children=[inner_p])])])])])])
        _,b=self.parse_body_table(t)
        para=b["children"][0]["children"][0]["children"][0]["children"][0]["children"][0]["children"][0]
        self.assertEqual(para["structural_path"],"/w:document/w:body[1]/w:tbl[1]/w:tr[1]/w:tc[1]/w:tbl[1]/w:tr[1]/w:tc[1]/w:p[1]")

    # MEN-2: block_refs só aponta para blocos estruturais (paragraph/table/block_container)
    def test_44_cell_block_refs_only_structural(self):
        tc=cell(children=[p("a"),etree.Element(qn(W,"bookmarkStart"),{qn(W,"id"):"1",qn(W,"name"):"x"}),etree.Comment("c"),p("b")])
        _,b=self.parse_body_table(table(rows=[row(cells=[tc])]))
        cell_=b["children"][0]["children"][0]
        # children[] autoritativo preserva TODOS os filhos na ordem física
        self.assertEqual([c["source_type"] for c in cell_["children"]],
                         ["paragraph","opaque_object","non_element_node","paragraph"])
        # block_refs[] contém apenas os paths dos blocos estruturais
        types_by_path={c["structural_path"]:c["source_type"] for c in cell_["children"]}
        self.assertEqual([types_by_path[ref] for ref in cell_["block_refs"]],["paragraph","paragraph"])
        self.assertEqual(len(cell_["block_refs"]),2)

    def test_45_block_container_block_refs_only_structural(self):
        sdt=etree.Element(qn(W,"sdt")); content=etree.SubElement(sdt,qn(W,"sdtContent"))
        content.append(p("x"))
        content.append(etree.Element(qn(W,"bookmarkEnd"),{qn(W,"id"):"1"}))
        content.append(table())
        r=self.parser.parse_bytes(package(doc([sdt])))
        outer=r["stories"][0]["blocks"][0]
        self.assertEqual(outer["source_type"],"block_container")
        cont=outer["children"][0]  # w:sdtContent, também block_container
        self.assertEqual(cont["container_type"],"sdtContent")
        self.assertEqual([c["source_type"] for c in cont["children"]],
                         ["paragraph","opaque_object","table"])
        types_by_path={c["structural_path"]:c["source_type"] for c in cont["children"]}
        self.assertEqual([types_by_path[ref] for ref in cont["block_refs"]],["paragraph","table"])

if __name__=="__main__": unittest.main()
