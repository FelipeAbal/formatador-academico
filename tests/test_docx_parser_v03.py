from __future__ import annotations
import io, unittest, zipfile
from lxml import etree
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from formatador_academico.docx_parser import DocxParser, serialize_parse_result

W="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR="http://schemas.openxmlformats.org/package/2006/relationships"
CT="http://schemas.openxmlformats.org/package/2006/content-types"
RELBASE="http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
MAINCT="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
CTS={
 "footnotes":"application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml",
 "endnotes":"application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml",
 "header":"application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml",
 "footer":"application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml",
 "comments":"application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml",
}
def qn(ns,t): return f"{{{ns}}}{t}"

def run(text):
    r=etree.Element(qn(W,"r")); t=etree.SubElement(r,qn(W,"t")); t.text=text; return r
def p(text):
    x=etree.Element(qn(W,"p")); x.append(run(text)); return x
def table():
    t=etree.Element(qn(W,"tbl")); tr=etree.SubElement(t,qn(W,"tr")); tc=etree.SubElement(tr,qn(W,"tc")); tc.append(p("cell")); return t
def doc():
    root=etree.Element(qn(W,"document"),nsmap={"w":W,"r":R}); body=etree.SubElement(root,qn(W,"body"))
    body.append(p("body")); etree.SubElement(body,qn(W,"sectPr"))
    return etree.tostring(root,xml_declaration=True,encoding="UTF-8")
def notes(kind, items):
    root=etree.Element(qn(W,kind),nsmap={"w":W})
    tag="footnote" if kind=="footnotes" else "endnote"
    for ident,typ,children in items:
        attrs={qn(W,"id"):str(ident)}
        if typ is not None: attrs[qn(W,"type")]=typ
        it=etree.SubElement(root,qn(W,tag),attrs)
        for c in children: it.append(c)
    return etree.tostring(root,xml_declaration=True,encoding="UTF-8")
def comments(items):
    root=etree.Element(qn(W,"comments"),nsmap={"w":W})
    for ident,children in items:
        c=etree.SubElement(root,qn(W,"comment"),{qn(W,"id"):str(ident),qn(W,"author"):"A"})
        for x in children: c.append(x)
    return etree.tostring(root,xml_declaration=True,encoding="UTF-8")
def hf(kind, children):
    root=etree.Element(qn(W,"hdr" if kind=="header" else "ftr"),nsmap={"w":W})
    for c in children: root.append(c)
    return etree.tostring(root,xml_declaration=True,encoding="UTF-8")
def ct(parts):
    root=etree.Element(qn(CT,"Types"),nsmap={None:CT})
    etree.SubElement(root,qn(CT,"Default"),Extension="rels",ContentType="application/vnd.openxmlformats-package.relationships+xml")
    etree.SubElement(root,qn(CT,"Default"),Extension="xml",ContentType="application/xml")
    etree.SubElement(root,qn(CT,"Override"),PartName="/word/document.xml",ContentType=MAINCT)
    for name,ctype in parts.items():
        etree.SubElement(root,qn(CT,"Override"),PartName="/"+name,ContentType=ctype)
    return etree.tostring(root,xml_declaration=True,encoding="UTF-8")
def rels(story_rels):
    root=etree.Element(qn(PR,"Relationships"),nsmap={None:PR})
    for rid,stype,target in story_rels:
        etree.SubElement(root,qn(PR,"Relationship"),Id=rid,Type=RELBASE+stype,Target=target)
    return etree.tostring(root,xml_declaration=True,encoding="UTF-8")
def package(parts=None, story_rels=None, ctype_overrides=None):
    parts=parts or {}; story_rels=story_rels or []; ctype_overrides=ctype_overrides or {}
    b=io.BytesIO()
    with zipfile.ZipFile(b,"w",compression=zipfile.ZIP_DEFLATED) as z:
        timestamp=(2026,1,1,0,0,0)
        entries={"[Content_Types].xml":ct(ctype_overrides),"_rels/.rels":rels([]),"word/document.xml":doc(),
                 "word/_rels/document.xml.rels":rels(story_rels)}
        entries.update(parts)
        for name,data in entries.items():
            i=zipfile.ZipInfo(name,timestamp); i.compress_type=zipfile.ZIP_DEFLATED; z.writestr(i,data)
    return b.getvalue()

class V03(unittest.TestCase):
    def setUp(self): self.parser=DocxParser()

    def story(self,r,typ):
        return [s for s in r["stories"] if s["story_type"]==typ][0]

    def test_no_secondary_stories_is_ok(self):
        r=self.parser.parse_bytes(package())
        self.assertEqual(r["status"],"ok")
        self.assertEqual([s["story_type"] for s in r["stories"]],["body"])

    def test_footnotes_ids_raw_special_and_blocks(self):
        part="word/footnotes.xml"
        data=notes("footnotes",[("-1","separator",[p("sep")]),("3",None,[p("real"),table()])])
        r=self.parser.parse_bytes(package({part:data},[("rF","footnotes","footnotes.xml")],{part:CTS["footnotes"]}))
        s=self.story(r,"footnotes")
        self.assertEqual(s["status"],"ok")
        self.assertEqual([i["note_id"] for i in s["items"]],["-1","3"])
        self.assertEqual(s["items"][0]["note_type"],"separator")
        self.assertEqual([b["source_type"] for b in s["items"][1]["blocks"]],["paragraph","table"])

    def test_endnote_empty(self):
        part="word/endnotes.xml"; data=notes("endnotes",[("1",None,[])])
        r=self.parser.parse_bytes(package({part:data},[("rE","endnotes","endnotes.xml")],{part:CTS["endnotes"]}))
        self.assertEqual(self.story(r,"endnotes")["items"][0]["blocks"],[])

    def test_multiple_headers_footers_by_relationship_type(self):
        parts={"word/headerA.xml":hf("header",[p("h1")]),"word/headerB.xml":hf("header",[p("h2")]),"word/f.xml":hf("footer",[p("f")])}
        rels0=[("h1","header","headerA.xml"),("h2","header","headerB.xml"),("f1","footer","f.xml")]
        cts={k:CTS["header" if "header" in k else "footer"] for k in parts}
        r=self.parser.parse_bytes(package(parts,rels0,cts))
        self.assertEqual(len([s for s in r["stories"] if s["story_type"]=="header"]),2)
        self.assertEqual(len([s for s in r["stories"] if s["story_type"]=="footer"]),1)
        self.assertTrue(all(s["relationship_id"] for s in r["stories"] if s["story_type"] in ("header","footer")))

    def test_comments_items_and_no_range_link_required(self):
        part="word/comments.xml"; data=comments([("7",[p("a"),p("b"),table()])])
        r=self.parser.parse_bytes(package({part:data},[("c1","comments","comments.xml")],{part:CTS["comments"]}))
        s=self.story(r,"comments")
        self.assertEqual(s["items"][0]["comment_id"],"7")
        self.assertEqual(len(s["items"][0]["blocks"]),3)
        self.assertEqual(r["status"],"ok")

    def test_missing_related_part_is_partial_not_fatal(self):
        r=self.parser.parse_bytes(package({},[("x","footnotes","missing.xml")],{}))
        self.assertEqual(r["status"],"partial")
        s=self.story(r,"footnotes")
        self.assertEqual(s["status"],"missing")
        self.assertEqual(s["errors"][0]["code"],"missing_related_part")

    def test_malformed_story_is_contained(self):
        part="word/comments.xml"
        r=self.parser.parse_bytes(package({part:b"<w:comments xmlns:w='"+W.encode()+b"'><bad>"},[("c","comments","comments.xml")],{part:CTS["comments"]}))
        self.assertEqual(r["status"],"partial")
        self.assertEqual(self.story(r,"comments")["status"],"failed")
        self.assertEqual(self.story(r,"body")["status"],"ok")

    def test_orphan_story_part_is_parsed_with_warning(self):
        part="word/header9.xml"
        r=self.parser.parse_bytes(package({part:hf("header",[p("orphan")])},[],{part:CTS["header"]}))
        s=self.story(r,"header")
        self.assertIsNone(s["relationship_id"])
        self.assertIn("orphan_story_part",[w["code"] for w in r["parse_warnings"]])

    def test_duplicate_relationship_same_part_one_story(self):
        part="word/header1.xml"
        r=self.parser.parse_bytes(package({part:hf("header",[p("x")])},[("a","header","header1.xml"),("b","header","header1.xml")],{part:CTS["header"]}))
        self.assertEqual(len([s for s in r["stories"] if s["part"]==part]),1)
        self.assertIn("duplicate_story_relationship",[w["code"] for w in r["parse_warnings"]])

    def test_content_type_mismatch_warns_relationship_wins(self):
        part="word/weird.xml"
        r=self.parser.parse_bytes(package({part:hf("header",[p("x")])},[("a","header","weird.xml")],{part:CTS["footer"]}))
        self.assertEqual(self.story(r,"header")["status"],"ok")
        self.assertIn("story_type_mismatch",[w["code"] for w in r["parse_warnings"]])

    def test_relative_target_resolution(self):
        part="word/header1.xml"
        r=self.parser.parse_bytes(package({part:hf("header",[p("x")])},[("a","header","header1.xml")],{part:CTS["header"]}))
        rr=[x for x in r["relationships"] if x["id"]=="a"][0]
        self.assertEqual(rr["resolved_target"],part)

    def test_textbox_detected_inside_opaque_drawing(self):
        drawing=etree.Element(qn(W,"drawing")); tx=etree.SubElement(drawing,qn(W,"txbxContent")); tx.append(p("inside"))
        head=hf("header",[p("x")])
        root=etree.fromstring(head); root[0][0].append(drawing); head=etree.tostring(root)
        part="word/header1.xml"
        r=self.parser.parse_bytes(package({part:head},[("a","header","header1.xml")],{part:CTS["header"]}))
        ws=[w for w in r["parse_warnings"] if w["code"]=="textbox_detected"]
        self.assertTrue(ws); self.assertEqual(ws[0]["story_id"],"header:word/header1.xml")

    def test_warnings_are_story_scoped(self):
        part="word/header1.xml"; head=hf("header",[p("x")])
        root=etree.fromstring(head); root.append(etree.Element(qn(W,"sdt"))); head=etree.tostring(root)
        r=self.parser.parse_bytes(package({part:head},[("a","header","header1.xml")],{part:CTS["header"]}))
        w=[x for x in r["parse_warnings"] if x["code"]=="unsupported_story_child"][0]
        self.assertEqual(w["story_id"],"header:word/header1.xml")

    def test_unique_story_ids_and_parts(self):
        part="word/comments.xml"
        r=self.parser.parse_bytes(package({part:comments([("1",[p("x")])])},[("c","comments","comments.xml")],{part:CTS["comments"]}))
        self.assertEqual(len({s["story_id"] for s in r["stories"]}),len(r["stories"]))
        self.assertEqual(len({s["part"] for s in r["stories"]}),len(r["stories"]))

    def test_determinism_same_input(self):
        part="word/footnotes.xml"; data=notes("footnotes",[("1",None,[p("x")])])
        pkg=package({part:data},[("f","footnotes","footnotes.xml")],{part:CTS["footnotes"]})
        self.assertEqual(serialize_parse_result(self.parser.parse_bytes(pkg)),serialize_parse_result(self.parser.parse_bytes(pkg)))

    def test_body_v02_smoke_preserved(self):
        r=self.parser.parse_bytes(package())
        b=self.story(r,"body")["blocks"]
        self.assertEqual([x["source_type"] for x in b],["paragraph","section_properties"])
        self.assertEqual(b[0]["structural_path"],"/w:document/w:body[1]/w:p[1]")
        self.assertEqual(b[0]["children"][0]["children"][0]["text"],"body")

    def test_all_story_parts_are_represented_once(self):
        parts={
            "word/footnotes.xml":notes("footnotes",[("1",None,[p("f")])]),
            "word/endnotes.xml":notes("endnotes",[("2",None,[p("e")])]),
            "word/header1.xml":hf("header",[p("h")]),
            "word/footer1.xml":hf("footer",[p("ft")]),
            "word/comments.xml":comments([("3",[p("c")])]),
        }
        rels0=[("rf","footnotes","footnotes.xml"),("re","endnotes","endnotes.xml"),
               ("rh","header","header1.xml"),("rft","footer","footer1.xml"),("rc","comments","comments.xml")]
        cts={k:CTS["header" if "header" in k else "footer" if "footer" in k else
                   "footnotes" if "footnotes" in k else "endnotes" if "endnotes" in k else "comments"] for k in parts}
        r=self.parser.parse_bytes(package(parts,rels0,cts))
        self.assertEqual(r["status"],"ok")
        represented=[s["part"] for s in r["stories"] if s["story_type"]!="body"]
        self.assertEqual(sorted(represented),sorted(parts))
        self.assertEqual(len(represented),len(set(represented)))

    def test_non_item_root_children_are_explicitly_preserved(self):
        root=etree.Element(qn(W,"footnotes"),nsmap={"w":W})
        root.append(etree.Comment("c"))
        note=etree.SubElement(root,qn(W,"footnote"),{qn(W,"id"):"1"}); note.append(p("x"))
        data=etree.tostring(root)
        part="word/footnotes.xml"
        r=self.parser.parse_bytes(package({part:data},[("f","footnotes","footnotes.xml")],{part:CTS["footnotes"]}))
        s=self.story(r,"footnotes")
        self.assertEqual(len(s["items"]),1)
        self.assertEqual(len(s["opaque_items"]),1)
        self.assertEqual(s["opaque_items"][0]["source_type"],"opaque_story_child")

    def test_determinism_cross_pythonhashseed(self):
        import base64, os, subprocess
        part="word/comments.xml"
        data=package({part:comments([("1",[p("x")])])},[("c","comments","comments.xml")],{part:CTS["comments"]})
        encoded=base64.b64encode(data).decode("ascii")
        script=("import base64,sys;"
                f"sys.path.insert(0,{str(ROOT/'src')!r});"
                "from formatador_academico.docx_parser import DocxParser,serialize_parse_result;"
                f"d=base64.b64decode({encoded!r});"
                "sys.stdout.buffer.write(serialize_parse_result(DocxParser().parse_bytes(d)))")
        outs=[]
        for seed in ("1","9999"):
            env=os.environ.copy(); env["PYTHONHASHSEED"]=seed
            outs.append(subprocess.check_output([sys.executable,"-c",script],env=env))
        self.assertEqual(outs[0],outs[1])

    def test_version(self):
        self.assertEqual(self.parser.parse_bytes(package())["parser_version"],"0.3.0")

if __name__=="__main__": unittest.main()
