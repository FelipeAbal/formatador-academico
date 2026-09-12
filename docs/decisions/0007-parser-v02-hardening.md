# Decisão 0007 — Hardening do parser v0.2 após revisão adversarial

## Contexto

O código real da v0.2 foi revisado pelo Kimi K3 com 22/22 testes existentes aprovados e doze ataques adversariais. Veredito: **APROVAR COM CORREÇÕES**, sem bloqueantes.

## Ajustes incorporados

1. `original_index` passa a ter semântica única em toda profundidade: posição 0-based entre **todos** os filhos do pai imediato. O índice 1-based entre irmãos da mesma tag/tipo continua exclusivamente no `structural_path`.
2. O algoritmo de `physical_hash` é versionado. Desde o hardening v0.1/v0.2 ele é SHA-256 da serialização JSON determinística de `canonical_xml + inherited_xml_attrs`. Hashes de versões anteriores que usavam somente C14N não são comparáveis. Comparações cruzadas de versão devem usar `canonical_xml` e contexto explícito, não igualdade de `physical_hash`.
3. `children[]` é a representação autoritativa. Visões auxiliares deixam de serializar cópias completas: `run_refs[]` e `fragment_refs[]` contêm apenas `structural_path`.
4. Cobertura 1:1 de `w:p` e `w:r` é validada por correspondência de multiconjunto de `structural_path`, não apenas por contagem.
5. Mixed content inesperado (`node.text` direto ou `tail` fora dos fragmentos previstos) gera `mixed_content_text`. Warnings repetitivos são agregados por código+mensagem com `count` e até três `sample_paths`.
6. `w:bdo`, `w:dir` e `w:customXml` entram em `RUN_CONTAINER_TYPES`, reutilizando a decomposição recursiva existente.
7. `w:rPr` duplicado gera `duplicate_run_properties` e é preservado como filho opaco.
8. A suíte inclui fixture com `physical_hash` esperado fixo e teste determinístico entre processos com `PYTHONHASHSEED` distintos usando os mesmos bytes DOCX.

## Decisões preservadas

- OOXML + lxml permanecem autoritativos.
- `canonical_xml` integral do parágrafo continua como rede de segurança.
- Runs não são coalescidos.
- Fields complexos não são interpretados; `fldChar` pode permanecer opaco na v0.2.
- bookmarks, proofing markers, permissões e comment-range markers podem permanecer opacos no nível de parágrafo na v0.2.
- Containers de parágrafo no nível do body podem permanecer opacos até etapa posterior.
- O patcher futuro nunca reconstrói documento a partir da IR/canonical XML; atua sobre cópia do pacote original.

## Resultado

Suíte específica atualizada da v0.2: **18/18 testes aprovados localmente**.

A v0.3 pode começar depois deste hardening e deve focar stories secundárias reutilizando o parser de parágrafo/run.
