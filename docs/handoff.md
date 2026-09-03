# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; arquitetura física do parser consolidada; **parser v0.4 formalmente congelado após auditoria adversarial, hardening e validação externa completa: 102/102 testes, 0 failures, 0 errors, 0 skips.**

Próxima etapa: **Analysis View v0.1**. Abrir **novo chat no Kimi K3** para esse ciclo, usando este HANDOFF + commit atual do `main` como verdade operacional.

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

## Próxima etapa — Analysis View v0.1

**Abrir novo chat no Kimi K3.**

Primeiro passo: definir e auditar o contrato da Analysis View antes de código.

Direção preliminar já sugerida pela auditoria do parser:
1. visão normalizada derivada de runs, com coalescência não destrutiva + mapa de offsets de volta à PhysicalIR;
2. resolução de formatação efetiva com origem/proveniência (`direct` / `style` / `inherited` / `default`);
3. classificação semântica (`role_candidates`) fica para etapa posterior.

Não implementar Analysis View antes de fechar o contrato e submetê-lo à auditoria técnica.