#!/usr/bin/env python3
import json,re,sys
from pathlib import Path
from collections import Counter
from jsonschema import Draft202012Validator

TYPE_PREFIX={"L":"livro","C":"capitulo","A":"artigo","E":"evento","D":"dissertacao","T":"tese","O":"online","G":"legislacao","J":"jurisprudencia","H":"fonte_historica"}

def markup_ok(text):
    r=re.compile(r"</?(b|i|u)>"); st=[]
    for m in r.finditer(text):
        raw=m.group(0); tag=m.group(1)
        if raw.startswith("</"):
            if not st or st[-1]!=tag:return False
            st.pop()
        else: st.append(tag)
    cleaned=r.sub("",text)
    return not st and not re.search(r"</?[A-Za-z][^>]*>",cleaned)

def toks(s):
    s=re.sub(r"</?(?:b|i|u)>","",s)
    return re.findall(r"\w+",s,flags=re.UNICODE)

def validate_semantic(corpus,alerts,vocab,expected_warning_pairs):
    errors=[]; warnings=[]; fs=corpus["fixtures"]; ids=[f["id"] for f in fs]; idset=set(ids); allowed=set(vocab["allowed_aspects"])
    if len(ids)!=len(idset): errors.append({"id":"CORPUS","code":"DUPLICATE_ID","message":"IDs duplicados."})

    seen={}
    for f in fs:
        if f["entrada"] in seen:
            errors.append({"id":f["id"],"code":"DUPLICATE_INPUT","message":f"Entrada idêntica à de {seen[f['entrada']]}."})
        else: seen[f["entrada"]]=f["id"]

    for f in fs:
        fid=f["id"]; se=f["saida_esperada"]
        if fid.startswith("RC3-"):
            if f["tipo_bibliografico"]!="regressao_c3" or f["funcao_corpus"]!="regressao_c3":
                errors.append({"id":fid,"code":"IDENTITY_MISMATCH","message":"RC3 incoerente."})
        elif TYPE_PREFIX.get(fid[0])!=f["tipo_bibliografico"]:
            errors.append({"id":fid,"code":"TYPE_PREFIX_MISMATCH","message":"Prefixo/tipo incoerentes."})

        for name,text in [("entrada",f["entrada"])] + [(f"saida.{k}",se[k]) for k in ("texto","proposta") if k in se]:
            if not markup_ok(text):
                errors.append({"id":fid,"code":"MARKUP_INVALID","message":name})

        for a in f["perfil"]["aspectos"]:
            if a not in allowed:
                errors.append({"id":fid,"code":"UNKNOWN_ASPECT","message":a})

        auth=f["operacoes_autorizadas"]; block=f["operacoes_bloqueadas"]
        ac=[o["codigo"] for o in auth]; bc=[o["codigo"] for o in block]
        amap={o["codigo"]:o for o in auth}
        if len(ac)!=len(set(ac)): errors.append({"id":fid,"code":"DUP_AUTH_OP","message":"Operação autorizada duplicada."})
        if len(bc)!=len(set(bc)): errors.append({"id":fid,"code":"DUP_BLOCK_OP","message":"Operação bloqueada duplicada."})
        if set(ac)&set(bc): errors.append({"id":fid,"code":"OP_CONFLICT","message":"Operação autorizada e bloqueada."})

        for o in auth:
            if o.get("classe_portao") is None:
                errors.append({"id":fid,"code":"AUTHORIZED_OP_WITHOUT_CLASS","message":o["codigo"]})
            for a in o.get("subaspectos",[]):
                if a not in allowed:
                    errors.append({"id":fid,"code":"OP_UNKNOWN_ASPECT","message":f"{o['codigo']}->{a}"})
                    continue
                c=f["perfil"]["aspectos"].get(a)
                if not c:
                    errors.append({"id":fid,"code":"OP_ASPECT_NOT_IN_PROFILE","message":f"{o['codigo']}->{a}"})
                elif c["estado"]!="configurado":
                    errors.append({"id":fid,"code":"OP_ASPECT_NOT_CONFIGURED","message":f"{o['codigo']}->{a}={c['estado']}"})

        # Deterministic change mapping: apply every declared step.
        changes=f.get("mudancas_esperadas",[])
        if se["modo"] in ("transformar","propor_revisao"):
            if not changes:
                errors.append({"id":fid,"code":"CHANGE_MAP_MISSING","message":"Transformação/proposta sem mudancas_esperadas."})
            current=f["entrada"]
            used_ops=set()
            for idx,ch in enumerate(changes):
                code=ch["codigo_operacao"]
                if code not in amap:
                    errors.append({"id":fid,"code":"CHANGE_MAP_UNKNOWN_OP","message":f"Etapa {idx}: {code} não é operação autorizada."})
                    continue
                before=ch["trecho_antes"]; after=ch["trecho_depois"]
                if current != before:
                    errors.append({"id":fid,"code":"CHANGE_MAP_CHAIN_BREAK","message":f"Etapa {idx}: trecho_antes não coincide com estado atual."})
                    break
                current=after
                used_ops.add(code)
            target=se.get("texto") or se.get("proposta") or ""
            if current != target:
                errors.append({"id":fid,"code":"CHANGE_MAP_OUTPUT_MISMATCH","message":"Aplicação das mudanças não produz saída esperada exata."})
            # Every authorized op that changes this fixture must be represented.
            unused=set(amap)-used_ops
            if unused:
                errors.append({"id":fid,"code":"AUTHORIZED_OP_UNMAPPED","message":"Operações autorizadas sem mudança mapeada: "+", ".join(sorted(unused))})
        else:
            if changes:
                errors.append({"id":fid,"code":"PRESERVE_WITH_CHANGE_MAP","message":"Modo preservar não pode possuir mudanças esperadas."})

        for a in f["alertas_esperados"]:
            if a not in alerts: errors.append({"id":fid,"code":"UNKNOWN_ALERT","message":a})
        for link in f.get("regression_links",[]):
            if link not in idset: errors.append({"id":fid,"code":"BROKEN_REGRESSION_LINK","message":link})

        if f["nivel_principal"]=="C3" and not f["criterio_acerto"].get("revisao_humana_obrigatoria",False):
            errors.append({"id":fid,"code":"C3_REVIEW_FALSE","message":"C3 exige revisão humana."})

        if f["funcao_corpus"]=="contencao":
            if se["modo"]!="preservar" or f["alertas_esperados"]:
                errors.append({"id":fid,"code":"CONTAINMENT_CONTRADICTION","message":"Contenção deve preservar sem alertar."})

        if se["modo"] in ("transformar","propor_revisao"):
            target=se.get("texto") or se.get("proposta") or ""
            src=Counter(toks(f["entrada"])); dst=Counter(toks(target))
            ad=list((dst-src).elements()); rm=list((src-dst).elements())
            if ad or rm:
                warnings.append({"id":fid,"code":"TOKEN_MULTISET_CHANGED","added":ad[:30],"removed":rm[:30]})

    actual={(w["id"],w["code"]) for w in warnings}
    unexpected=actual-expected_warning_pairs
    missing=expected_warning_pairs-actual
    if unexpected:
        errors.append({"id":"CORPUS","code":"UNEXPECTED_VALIDATION_WARNING","message":repr(sorted(unexpected))})
    if missing:
        errors.append({"id":"CORPUS","code":"EXPECTED_WARNING_MISSING","message":repr(sorted(missing))})

    return errors,warnings

def main():
    if len(sys.argv)!=6:
        print("uso: validate_corpus_v3.py schema corpus alert_catalog vocabulary expected_warnings"); return 2
    schema=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    corpus=json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    alerts=set(json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))["alerts"])
    vocab=json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
    ew=json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))["expected"]
    expected={(x["id"],x["code"]) for x in ew}

    structural=[]
    sv=Draft202012Validator(schema)
    for f in corpus["fixtures"]:
        for e in sv.iter_errors(f):
            structural.append({"id":f["id"],"path":".".join(map(str,e.path)),"message":e.message})
    semantic,warnings=validate_semantic(corpus,alerts,vocab,expected)
    out={"structural_errors":structural,"semantic_errors":semantic,"warnings":warnings,"ok":not structural and not semantic}
    print(json.dumps(out,ensure_ascii=False,indent=2)); return 0 if out["ok"] else 1

if __name__=="__main__": raise SystemExit(main())
