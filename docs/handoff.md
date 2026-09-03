# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; arquitetura/contrato do parser fechados; parser v0.2 endurecido; **parser v0.3 implementado com stories secundárias e parse parcial por story, 20/20 testes específicos aprovados localmente**. Próximo passo: revisão adversarial do código real da v0.3 pelo Kimi K3.

Este é o HANDOFF corrente. O histórico fica no Git; não criar `handoff_vNN`.

## Objetivo do MVP

Formatar com segurança DOCX acadêmicos existentes a partir de perfil formal explicitamente declarado. Não promete conformidade ABNT genérica.

Saídas:
1. DOCX limpo;
2. DOCX de revisão;
3. relatório.

Princípio: **Na dúvida, marcar.**

## Segurança

- nenhuma invenção/perda substantiva;
- só atuar em subaspecto autorizado;
- ambiguidade não é resolvida silenciosamente;
- opacos são preservados/protegidos;
- Safety Gate é veto, nunca autorização;
- C3 exige revisão humana.

## Corpus congelado v1

- 41 fixtures;
- baseline motor nulo: 20/41 = 48,8%;
- precisão-alvo automática >=99%;
- alto risco desejado >=99,5%;
- tolerância zero a invenção/perda conhecida, dano a campo e alteração indevida de citação direta.

Reabrir apenas por falha de teste, impossibilidade técnica, contradição nova, mudança explícita de contrato/escopo ou novo risco de segurança.

## Arquitetura fechada

### 0001 — DocumentIR
OriginalPackage imutável; IR derivada/serializável; saída nunca reconstruída da IR.

### 0002 — Unidade de trabalho
`DocumentContext -> BlockWorkItem -> Field/Aspect Decisions -> OperationPlan -> SafetyGate -> TransformLog -> XML Patches`

### 0003 — Contrato do parser
Parser físico/forense, sem análise acadêmica ou transformação. Garantias G1-G7: imutabilidade, nenhuma perda silenciosa, rastreabilidade, opacos protegidos, determinismo e convenções compartilhadas com o patcher.

### 0004 — Estratégia DOCX
**OOXML + lxml autoritativo.** `python-docx` apenas auxiliar.

### 0005 — Hardening v0.1
`docs/decisions/0005-parser-v01-hardening.md`

### 0006 — v0.2 parágrafos/runs
`docs/decisions/0006-parser-v02-paragraph-runs.md`

- `w:pPr`/`w:rPr` crus;
- runs forenses sem coalescimento;
- containers recursivos;
- fragments tipados;
- opacos protegidos;
- sem estilo efetivo/herança/análise acadêmica.

### 0007 — Hardening v0.2
`docs/decisions/0007-parser-v02-hardening.md`

- `original_index`: posição 0-based entre todos os filhos do pai;
- `children[]` autoritativo;
- `run_refs[]`/`fragment_refs[]` são paths;
- cobertura 1:1 por paths;
- mixed content sinalizado;
- warnings agregados;
- `bdo`, `dir`, `customXml`;
- fixture de hash fixa;
- determinismo cross-process.

### 0008 — v0.3 stories secundárias
`docs/decisions/0008-parser-v03-secondary-stories.md`

Recorte aprovado pelo Kimi K3: footnotes, endnotes, headers, footers e comments na mesma versão.

Decisão estrutural:
**falha de story secundária não derruba o documento**.

Estados de story:
- `ok`;
- `missing`;
- `failed`.

Resultado global:
- `ok` se body/pacote e stories secundárias processarem;
- `partial` se alguma story secundária estiver `missing`/`failed`;
- `failed` para falha fatal do pacote/body.

## Parser atual

Versão: **0.3.0**

Arquivo:
`src/formatador_academico/docx_parser.py`

### Body e blocos

O dispatch foi extraído para `_parse_block_sequence`, reutilizado por body, header/footer e itens de notes/comments.

Parágrafos/runs preservam comportamento v0.2.

Tabelas permanecem integrais.

### Descoberta de stories

Relationships de `word/document.xml` são a autoridade de vínculo, identificados pelo Type URI.

`Target` relativo é resolvido contra a part de origem.

Content type funciona como validação cruzada.

Warnings:
- `story_type_mismatch`;
- `orphan_story_part`;
- `duplicate_story_relationship`;
- `textbox_detected`.

Missing related part:
- story registrada `missing`;
- `missing_related_part`;
- documento `partial`.

Part relacionada malformada:
- apenas a story fica `failed`;
- documento `partial`.

### Footnotes / endnotes

Stories coletivas com `items[]`.

Cada item preserva:
- `note_id` como string crua;
- `note_type` cru;
- structural_path;
- canonical_xml;
- inherited_xml_attrs;
- physical_hash;
- blocks.

IDs reservados/separadores não são filtrados.

### Comments

Story coletiva com `items[]`.

Cada comment preserva `comment_id` cru e blocos.

A ligação range↔comment fica para Analysis View futura.

### Headers / footers

Uma story por part.

Não inferir seção, primeira página ou par/ímpar.

### Textboxes

Ainda não decompostas.

Se `w:txbxContent` aparecer dentro de opaco, gerar `textbox_detected`.

### Identidade

`structural_path` permanece relativo à part.

Identidade global:
`story_id + structural_path + original_index + physical_hash`.

`original_index` = posição 0-based entre todos os filhos do pai imediato.

`physical_hash` atual = SHA-256 de JSON determinístico com `canonical_xml + inherited_xml_attrs`.

O patcher nunca reconstrói DOCX a partir de canonical XML.

## Testes v0.3

**20/20 aprovados localmente.**

Cobrem:
- ausência de stories;
- footnotes/endnotes;
- IDs especiais;
- comments;
- múltiplos headers/footers;
- missing part;
- XML malformado contido por story;
- part órfã;
- duplicate relationship;
- mismatch content type;
- target relativo;
- textbox detectado;
- warnings por story;
- unicidade de story/part;
- todas as cinco stories juntas;
- filho root não-item preservado;
- determinismo mesmo input;
- determinismo cross-PYTHONHASHSEED;
- smoke regression do body v0.2;
- parser_version 0.3.0.

## Auditorias

1. schema corpus: Kimi K3;
2. corpus adversarial: Claude Opus;
3. corpus final: Claude Opus;
4. DocumentIR: Kimi K3;
5. unidade de trabalho: Kimi K3;
6. contrato parser: Kimi K3;
7. estratégia leitura: Kimi K3;
8. recorte v0.1: Kimi K3;
9. código v0.1: Kimi K3;
10. recorte v0.2: Kimi K3;
11. código v0.2: Kimi K3, APROVAR COM CORREÇÕES;
12. recorte v0.3: Kimi K3, **APROVAR COM AJUSTES**; ajustes incorporados na implementação.

## Regra de revisão

Decisão técnica relevante:
1. ChatGPT propõe;
2. auditor adequado revisa;
3. ChatGPT integra;
4. Felipe decide quando necessário;
5. registrar e commitar.

Implementação relevante também passa por revisão técnica antes da próxima fatia.

## Próximo passo

Submeter a implementação real da v0.3 ao Kimi K3.

**Não iniciar decomposição de tabelas, textboxes ou Analysis View antes dessa revisão.**
