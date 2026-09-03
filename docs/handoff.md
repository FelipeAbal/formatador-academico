# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; parser físico v0.4 formalmente congelado após auditoria adversarial e hardening (**102/102 testes, 0 failures, 0 errors, 0 skips**); **contrato da Analysis View v0.1a — Normalized Text View — auditado pelo Kimi K3, refinado e aprovado para implementação.**

Próximo passo: implementar somente a **Analysis View v0.1a — Normalized Text View**, conforme decisão 0013. Não iniciar Formatting Resolution antes de congelar a v0.1a.

Este é o HANDOFF corrente. O histórico fica no Git; não criar `handoff_vNN`.

## Regra operacional

**Tudo o que puder ser corrigido com segurança dentro do escopo atual deve ser corrigido antes de avançar.**

Só postergar quando houver:
- expansão explícita de escopo;
- dependência ainda não resolvida;
- impossibilidade técnica demonstrada;
- nova decisão arquitetural que exija auditoria própria.

Para trabalho com Kimi:
- mesmo projeto;
- novo chat por etapa técnica grande;
- no início do chat: HANDOFF corrente + commit exato do `main` + tarefa fechada;
- ao terminar uma implementação, não considerar concluída sem commit/PR publicado ou diff/arquivos completos;
- estado do GitHub prevalece sobre estado de sandbox/conversa.

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

## Decisões arquiteturais

### 0001 — DocumentIR
OriginalPackage imutável; IR derivada/serializável; saída nunca reconstruída da IR.

### 0002 — Unidade de trabalho
`DocumentContext -> BlockWorkItem -> Field/Aspect Decisions -> OperationPlan -> SafetyGate -> TransformLog -> XML Patches`

### 0003 — Contrato do parser
Parser físico/forense, sem análise acadêmica ou transformação. Garantias G1–G7: imutabilidade, nenhuma perda silenciosa, rastreabilidade, opacos protegidos, determinismo e convenções compartilhadas com o patcher.

### 0004 — Estratégia DOCX
**OOXML + lxml autoritativo.** `python-docx` apenas auxiliar.

### 0005 — Hardening v0.1
`docs/decisions/0005-parser-v01-hardening.md`

### 0006 — v0.2 parágrafos/runs
`docs/decisions/0006-parser-v02-paragraph-runs.md`

### 0007 — Hardening v0.2
`docs/decisions/0007-parser-v02-hardening.md`

- `children[]` autoritativo;
- refs auxiliares são paths;
- cobertura 1:1 por paths;
- mixed content sinalizado;
- determinismo cross-process.

### 0008 — v0.3 stories secundárias
`docs/decisions/0008-parser-v03-secondary-stories.md`

Footnotes, endnotes, headers, footers e comments; parse parcial; falha de story secundária não derruba body/pacote.

### 0009 — Hardening v0.3
`docs/decisions/0009-parser-v03-hardening.md`

### 0010 — Freeze v0.3
`docs/decisions/0010-freeze-parser-v03.md`

**56/56 testes externos**, sem regressões.

### 0011 — Contrato v0.4: tabelas
`docs/decisions/0011-parser-v04-table-contract.md`

Incluiu:
- `table -> table_row -> table_cell -> blocks`;
- `block_container` (`sdt`, `sdtContent`, `customXml`);
- nested tables;
- `max_structural_depth = 64`;
- grid/merges crus, sem validação/interpretação;
- IDs apenas em blocos raiz; blocos aninhados usam identidade física por path.

### 0012 — Freeze v0.4
`docs/decisions/0012-freeze-parser-v04.md`

Implementação recuperada da sandbox do Kimi e publicada no PR #1. Auditoria adversarial encontrou dois menores, ambos corrigidos antes do merge:
- `tcPr` duplicado uniformizado como `opaque_cell_child`;
- `block_refs` limitado a `paragraph`, `table`, `block_container`.

Revisão pré-merge encontrou e corrigiu três falhas de qualidade dos testes:
- teste v0.3 parcialmente comentado;
- teste de profundidade com asserção tautológica;
- teste sem asserções e duplicado removido.

Suíte final validada externamente:
- **102 testes**;
- **102 passes**;
- **0 failures**;
- **0 errors**;
- **0 skips**.

PR #1 mergeado no `main`.
Merge commit: `10b8ca39c4fa2cef7e2f0638a63cc8683926f691`.

### 0013 — Analysis View v0.1a: Normalized Text View
`docs/decisions/0013-analysis-v01a-normalized-text-contract.md`

Auditoria arquitetural pelo Kimi K3 recomendou dividir a Analysis View:
1. **v0.1a — Normalized Text View**;
2. **v0.1b — Formatting Resolution View**.

A v0.1a foi refinada e aprovada para implementação.

Decisões principais:
- unidade inicial = parágrafo;
- `segments[]` é autoritativo;
- `default_text` é projeção derivada;
- um segmento por fragmento físico, sem coalescência multi-source;
- offsets lógicos e físicos textuais em code points da `str` Python, start inclusivo/end exclusivo;
- não-participantes são zero-width;
- `w:instrText`, `w:delText`, `w:sym` não entram em `default_text`;
- `w:sym` permanece cru em metadata, sem U+FFFD ou falsa conversão Unicode;
- desconhecido => `normalized_unexpected_fragment` + segmento opaco zero-width;
- sem `span_id`, `analysis_id` ou protection context nesta versão;
- Analysis View imutável, serializável, determinística, sem lxml vivo e sem mutar PhysicalIR.

Mapeamento da projeção padrão:
- text -> literal;
- tab -> `\t`;
- line break -> `\n`;
- page/column break -> zero-width estrutural;
- carriage return -> `\r`;
- no-break hyphen -> U+2011;
- soft hyphen -> U+00AD;
- field/deleted/symbol/opaque -> zero-width.

A Formatting Resolution terá contrato e auditoria próprios somente depois do freeze da v0.1a.

## Parser físico congelado

Versão: **0.4.0**

Arquivo:
`src/formatador_academico/docx_parser.py`

A PhysicalIR cobre:
- package/ZIP/OPC;
- body;
- paragraphs;
- runs;
- run containers;
- fragments;
- block containers;
- tables/rows/cells;
- nested tables;
- propriedades cruas de table/row/cell;
- tblGrid/gridCol crus;
- footnotes;
- endnotes;
- headers;
- footers;
- comments;
- stories ausentes, órfãs, falhadas e rejeitadas;
- parse parcial;
- textboxes detectados e preservados como opacos.

Identidade física global:
`part + story_id + structural_path + original_index + physical_hash`.

`children[]` é árvore autoritativa. Refs auxiliares contêm apenas `structural_path` e nunca substituem a árvore.

Story `missing`, `failed` ou `rejected` é região não editável.

Textboxes continuam fora da decomposição, detectados por `w:txbxContent`, `a:txBody` e `p:txBody`.

### Fora do parser

- layout visual;
- merge resolvido;
- grid lógico;
- largura efetiva;
- estilo/formatação efetiva;
- semântica acadêmica;
- patching/escrita;
- decomposição de textboxes.

## Regra de reabertura do parser v0.4

Somente por:
- falha de teste;
- impossibilidade técnica demonstrada;
- contradição nova;
- mudança explícita de contrato/escopo;
- novo risco de segurança.

## Analysis View v0.1a — implementação

Implementar conforme decisão 0013.

Escopo mínimo:
- pacote `src/formatador_academico/analysis/`;
- tipos imutáveis para `SourceAnchor`, `NormalizedSegment`, `NormalizedParagraph`, `SegmentKind`, `TextRole`;
- builder por parágrafo físico;
- projeção `default_text` derivada;
- mapping fechado dos fragment types da v0.4;
- warning analítico separado;
- determinismo e serialização;
- regressão integral dos 102 testes do parser.

Testes novos devem cobrir pelo menos os 31 casos listados na decisão 0013.

## Próximo passo

**Implementar a v0.1a** no mesmo chat atual do Kimi K3.

Não abrir novo chat ainda: o contrato e a implementação pertencem ao mesmo ciclo técnico da Normalized Text View.

Ao terminar:
1. publicar branch/PR ou fornecer diff/arquivos completos;
2. rodar suíte completa, incluindo os 102 testes congelados do parser;
3. trazer resultado para revisão adversarial;
4. corrigir tudo o que couber no escopo;
5. congelar v0.1a;
6. só então abrir novo ciclo para v0.1b — Formatting Resolution.
