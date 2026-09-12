from __future__ import annotations
import base64, io, os, subprocess, sys, unittest, zipfile
from pathlib import Path
from lxml import etree

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from formatador_academico.docx_parser import DocxParser

W="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT="http://schemas.openxmlformats.org/package/2006/content-types"
PR="http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
XML="http://www.w3.org/XML/1998/namespace"
def qn(ns,t): return f"{{{ns}}}{t}"

def p_with(children, with_ppr=False):
    p=etree.Element(qn(W,"p"))
    if with_ppr:
        ppr=etree.SubElement(p,qn(W,"pPr"))
        etree.SubElement(ppr,qn(W,"jc"),{qn(W,"val"):"center"})
    for c in children: p.append(c)
    return p

def run(*children, with_rpr=False):
    r=etree.Element(qn(W,"r"))
    if with_rpr:
        rpr=etree.SubElement(r,qn(W,"rPr")); etree.SubElement(rpr,qn(W,"b"))
    for c in children: r.append(c)
    return r

def frag(tag,text=None,attrs=None):
    e=etree.Element(qn(W,tag),attrs or {})
    e.text=text
    return e

def sectpr(): return etree.Element(qn(W,"sectPr"))

def document(children):
    root=etree.Element(qn(W,"document"),nsmap={"w":W,"r":R})
    body=etree.SubElement(root,qn(W,"body"))
    for c in children: body.append(c)
    return etree.tostring(root,xml_declaration=True,encoding="UTF-8")

def content_types():
    root=etree.Element(qn(CT,"Types"),nsmap={None:CT})
    etree.SubElement(root,qn(CT,"Default"),Extension="rels",ContentType="application/vnd.openxmlformats-package.relationships+xml")
    etree.SubElement(root,qn(CT,"Default"),Extension="xml",ContentType="application/xml")
    etree.SubElement(root,qn(CT,"Override"),PartName="/word/document.xml",ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml")
    return etree.tostring(root,xml_declaration=True,encoding="UTF-8")

def rels():
    root=etree.Element(qn(PR,"Relationships"),nsmap={None:PR})
    etree.SubElement(root,qn(PR,"Relationship"),Id="rId1",Type=OFFICE_REL,Target="word/document.xml")
    return etree.tostring(root,xml_declaration=True,encoding="UTF-8")

def docx(doc):
    b=io.BytesIO()
    with zipfile.ZipFile(b,"w",compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",content_types())
        z.writestr("_rels/.rels",rels())
        z.writestr("word/document.xml",doc)
    return b.getvalue()

class V02(unittest.TestCase):
    def setUp(self): self.parser=DocxParser()

    def parse_paragraph(self,p):
        result=self.parser.parse_bytes(docx(document([p,sectpr()])))
        self.assertEqual(result["status"],"ok")
        return result,result["stories"][0]["blocks"][0]

    def test_ppr_and_rpr_are_raw_properties(self):
        result,p=self.parse_paragraph(p_with([run(frag("t","A"),with_rpr=True)],with_ppr=True))
        self.assertEqual(p["properties_raw"]["source_type"],"properties_raw")
        r=[c for c in p["children"] if c["source_type"] == "run_raw"][0]
        self.assertEqual(r["properties_raw"]["source_type"],"properties_raw")
        self.assertEqual(r["children"][0]["text"],"A")

    def test_fragment_types(self):
        r=run(frag("t","A"),frag("tab"),frag("br"),frag("cr"),frag("noBreakHyphen"),frag("softHyphen"),frag("instrText","X"),frag("delText","Y"))
        _,p=self.parse_paragraph(p_with([r]))
        self.assertEqual([f["fragment_type"] for f in [c for c in p["children"] if c["source_type"] == "run_raw"][0]["children"]],
            ["text","tab","break","carriage_return","no_break_hyphen","soft_hyphen","instruction_text","deleted_text"])

    def test_hyperlink_preserves_linear_position_and_nested_run(self):
        before=run(frag("t","before")); link=etree.Element(qn(W,"hyperlink")); link.append(run(frag("t","link"))); after=run(frag("t","after"))
        result,p=self.parse_paragraph(p_with([before,link,after]))
        self.assertEqual([c["source_type"] for c in p["children"]],["run_raw","run_container","run_raw"])
        c=p["children"][1]; self.assertEqual(c["container_type"],"hyperlink")
        self.assertEqual([x for x in c["children"] if x["source_type"] == "run_raw"][0]["children"][0]["text"],"link")
        self.assertTrue([x for x in c["children"] if x["source_type"] == "run_raw"][0]["structural_path"].endswith("/w:hyperlink[1]/w:r[1]"))
        self.assertIn("unparsed_container",[w["code"] for w in result["parse_warnings"]])

    def test_nested_container_keeps_real_path(self):
        ins=etree.Element(qn(W,"ins")); sdt=etree.SubElement(ins,qn(W,"sdt")); sdtc=etree.SubElement(sdt,qn(W,"sdtContent")); sdtc.append(run(frag("t","nested")))
        _,p=self.parse_paragraph(p_with([ins])); inner=p["children"][0]["children"][0]["children"][0]
        rr=[x for x in inner["children"] if x["source_type"] == "run_raw"][0]
        self.assertIn("/w:ins[1]/w:sdt[1]/w:sdtContent[1]/w:r[1]",rr["structural_path"])

    def test_opaque_run_fragment_is_preserved(self):
        drawing=etree.Element(qn(W,"drawing")); etree.SubElement(drawing,"x")
        result,p=self.parse_paragraph(p_with([run(frag("t","A"),drawing)])); fragments=[c for c in p["children"] if c["source_type"] == "run_raw"][0]["children"]
        self.assertEqual(fragments[1]["source_type"],"opaque_fragment"); self.assertTrue(fragments[1]["protected"])
        self.assertIn("opaque_run_fragment",[w["code"] for w in result["parse_warnings"]])

    def test_xml_space_on_fragment_is_recorded(self):
        t=frag("t"," A ",{qn(XML,"space"):"preserve"}); _,p=self.parse_paragraph(p_with([run(t)])); f=[c for c in p["children"] if c["source_type"] == "run_raw"][0]["children"][0]
        self.assertEqual(f["xml_attrs"]["xml:space"],"preserve")

    def test_no_run_coalescing(self):
        _,p=self.parse_paragraph(p_with([run(frag("t","A")),run(frag("t","B"))])); self.assertEqual(len([c for c in p["children"] if c["source_type"] == "run_raw"]),2)

    def test_paragraph_child_coverage_one_to_one(self):
        link=etree.Element(qn(W,"hyperlink")); link.append(run(frag("t","L"))); unknown=etree.Element(qn(W,"bookmarkStart"),{qn(W,"id"):"1",qn(W,"name"):"x"})
        p=p_with([run(frag("t","A")),link,unknown],with_ppr=True); _,parsed=self.parse_paragraph(p)
        represented=[]
        if parsed["properties_raw"]: represented.append(parsed["properties_raw"]["structural_path"])
        represented.extend(c["structural_path"] for c in parsed["children"])
        root=etree.Element(qn(W,"document"),nsmap={"w":W}); body=etree.SubElement(root,qn(W,"body")); body.append(p)
        def path(n):
            parts=[]; cur=n
            while cur is not None:
                name="w:"+etree.QName(cur).localname; par=cur.getparent()
                if par is None: parts.append(name); break
                peers=[c for c in par if isinstance(c.tag,str) and c.tag==cur.tag]; parts.append(f"{name}[{peers.index(cur)+1}]"); cur=par
            return "/"+"/".join(reversed(parts))
        self.assertEqual(sorted(represented),sorted(path(c) for c in p))

    def test_run_child_coverage_one_to_one(self):
        drawing=etree.Element(qn(W,"drawing")); r=run(frag("t","A"),drawing,etree.Comment("c"),with_rpr=True); _,p=self.parse_paragraph(p_with([r]))
        rr=[c for c in p["children"] if c["source_type"] == "run_raw"][0]; represented=[]
        if rr["properties_raw"]: represented.append(rr["properties_raw"]["structural_path"])
        represented.extend(c["structural_path"] for c in rr["children"])
        root=etree.Element(qn(W,"document"),nsmap={"w":W}); body=etree.SubElement(root,qn(W,"body")); pp=etree.SubElement(body,qn(W,"p")); pp.append(r)
        def path(n):
            parts=[]; cur=n
            while cur is not None:
                name="w:"+etree.QName(cur).localname if isinstance(cur.tag,str) else "comment()"; par=cur.getparent()
                if par is None: parts.append(name); break
                peers=[c for c in par if isinstance(c.tag,str) and c.tag==cur.tag] if isinstance(cur.tag,str) else [c for c in par if isinstance(c,etree._Comment)]
                parts.append(f"{name}[{peers.index(cur)+1}]"); cur=par
            return "/"+"/".join(reversed(parts))
        self.assertEqual(sorted(represented),sorted(path(c) for c in r))

    def test_paragraph_physical_hash_stays_whole_paragraph_based(self):
        p=p_with([run(frag("t","A"))]); _,parsed=self.parse_paragraph(p); canonical=etree.tostring(p,method="c14n",exclusive=False,with_comments=True).decode("utf-8")
        self.assertEqual(parsed["canonical_xml"],canonical)

    def test_original_index_is_position_among_all_siblings(self):
        r1=run(frag("t","A")); marker=etree.Element(qn(W,"bookmarkStart"),{qn(W,"id"):"1",qn(W,"name"):"x"}); r2=run(frag("t","B")); _,p=self.parse_paragraph(p_with([r1,marker,r2]))
        self.assertEqual([c["original_index"] for c in p["children"]],[0,1,2])

    def test_additional_text_containers_are_decomposed(self):
        for tag in ("bdo","dir","customXml"):
            c=etree.Element(qn(W,tag)); c.append(run(frag("t",tag))); _,p=self.parse_paragraph(p_with([c])); container=p["children"][0]
            self.assertEqual(container["source_type"],"run_container"); self.assertEqual([x for x in container["children"] if x["source_type"]=="run_raw"][0]["children"][0]["text"],tag)

    def test_duplicate_run_properties_get_specific_warning(self):
        r=run(frag("t","A"),with_rpr=True); r.insert(1,etree.Element(qn(W,"rPr"))); result,_=self.parse_paragraph(p_with([r]))
        self.assertIn("duplicate_run_properties",[w["code"] for w in result["parse_warnings"]])

    def test_mixed_content_warns(self):
        r=run(frag("t","A")); r[0].tail="TAIL"; result,_=self.parse_paragraph(p_with([r])); self.assertIn("mixed_content_text",[w["code"] for w in result["parse_warnings"]])

    def test_auxiliary_lists_are_references_not_copies(self):
        _,p=self.parse_paragraph(p_with([run(frag("t","A")),run(frag("t","B"))])); self.assertTrue(all(isinstance(x,str) for x in p["run_refs"]))
        rr=[c for c in p["children"] if c["source_type"]=="run_raw"][0]; self.assertTrue(all(isinstance(x,str) for x in rr["fragment_refs"]))

    def test_fixed_physical_hash_fixture(self):
        _,p=self.parse_paragraph(p_with([run(frag("t","HASH"))])); self.assertEqual(p["physical_hash"],"13fae2462972d1ca6fce5571dd9183a9cbe3af2b45882f7dc12770532a83fc27")

    def test_determinism_across_pythonhashseed(self):
        data=docx(document([p_with([run(frag("t","A"))]),sectpr()])); encoded=base64.b64encode(data).decode("ascii")
        script=("import base64,sys;" f"sys.path.insert(0,{str(ROOT/'src')!r});" "from formatador_academico.docx_parser import DocxParser,serialize_parse_result;" f"data=base64.b64decode('{encoded}');" "sys.stdout.buffer.write(serialize_parse_result(DocxParser().parse_bytes(data)))")
        outputs=[]
        for seed in ("1","987654"):
            env=os.environ.copy(); env["PYTHONHASHSEED"]=seed; outputs.append(subprocess.check_output([sys.executable,"-c",script],env=env))
        self.assertEqual(outputs[0],outputs[1])

    def test_current_parser_version_is_at_least_v02_contract(self):
        result,_=self.parse_paragraph(p_with([run(frag("t","A"))]))
        major,minor,*_=map(int,result["parser_version"].split("."))
        self.assertGreaterEqual((major,minor),(0,2))

if __name__=="__main__": unittest.main()
