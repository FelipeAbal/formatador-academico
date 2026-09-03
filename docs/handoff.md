# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; parser v0.3 formalmente congelado após revalidação externa completa (**56/56 testes**); **contrato da v0.4 — decomposição física segura de tabelas — auditado pelo Kimi K3 e aprovado com ajustes, todos incorporados na decisão 0011.** Próximo passo: implementar a v0.4 e submetê-la a revisão adversarial do código real.

Este é o HANDOFF corrente. O histórico fica no Git; não criar `handoff_vNN`.

## Regra operacional adicional

**Tudo o que puder ser corrigido com segurança dentro do escopo atual deve ser corrigido antes de avançar.**

Só postergar quando houver:
- expansão explícita de escopo;
- dependência ainda não resolvida;
- impossibilidade técnica demonstrada;
- nova decisão arquitetural que exija auditoria própria.

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

### 0007 — Hardening v0.2
`docs/decisions/0007-parser-v02-hardening.md`

- `children[]` autoritativo;
- refs auxiliares são paths;
- cobertura 1:1 por paths;
- mixed content sinalizado;
- determinismo cross-process.

### 0008 — v0.3 stories secundárias
`docs/decisions/0008-parser-v03-secondary-stories.md`

Recorte: footnotes, endnotes, headers, footers e comments.

### 0009 — Hardening v0.3
`docs/decisions/0009-parser-v03-hardening.md`

### 0010 — Congelamento formal da v0.3
`docs/decisions/0010-freeze-parser-v03.md`

Revalidação externa final:
- **56/56 testes**;
- 0 failures;
- 0 errors;
- 0 skips;
- nenhuma regressão.

Veredito: **CONGELAR v0.3**.

### 0011 — Contrato da v0.4: tabelas
`docs/decisions/0011-parser-v04-table-contract.md`

Auditoria de contrato pelo Kimi K3: **APROVAR COM AJUSTES**.

Ajustes incorporados antes do código:
1. `block_container` para `w:sdt`/`w:sdtContent`/`w:customXml` em nível de bloco, inclusive no dispatch compartilhado de body/stories/cells;
2. blocos aninhados não usam ids sequenciais locais que possam colidir; `structural_path` é sua identidade física;
3. `ParserLimits.max_structural_depth = 64` com degradação para opaco + `max_depth_exceeded`;
4. `structural_path` formalmente estendido a `tbl/tr/tc` e block containers;
5. validação de grid, `gridSpan`, `vMerge`, merges e layout permanece explicitamente fora do parser.

Modelo:
`table -> row -> cell -> blocks`

`children[]` permanece autoritativo em table/row/cell. Slots nomeados (`properties_raw`, `grid_raw`) consomem seus nós; refs auxiliares, se usadas, contêm apenas paths.

## Parser congelado v0.3

Versão: **0.3.0**

Arquivo:
`src/formatador_academico/docx_parser.py`

Identidade física global:
`part + story_id + structural_path + original_index + physical_hash`.

Story `missing`, `failed` ou `rejected` é região não editável.

Textboxes permanecem opacos detectados por `w:txbxContent`, `a:txBody` e `p:txBody`.

## Contrato da v0.4

### Table
- preservar campos físicos do bloco da v0.3;
- `tblPr` -> `properties_raw`;
- `tblGrid` -> `grid_raw` + `gridCol` crus;
- `tr` -> `table_row`;
- demais filhos -> opacos protegidos;
- sem validação de grid/layout/merge.

### Row
- `trPr` -> `properties_raw`;
- `tc` -> `table_cell`;
- wrappers de row/cell não decompostos nesta versão permanecem opacos protegidos.

### Cell
- `tcPr` -> `properties_raw`;
- sequência de blocos preservada;
- paragraphs reutilizam parser existente;
- nested tables são recursivas;
- cell vazia não é corrigida nem sinalizada só por estar vazia.

### Block containers
`w:sdt`, `w:sdtContent`, `w:customXml` em nível de bloco tornam-se `block_container`, preservados/protegidos e decompostos recursivamente para não perder sequência substantiva.

### Limite estrutural
Default: **64** níveis.

Ao atingir limite:
- preservar subtree integral;
- `protected = true`;
- warning `max_depth_exceeded`;
- não permitir `RecursionError` por input profundo.

### Fora da v0.4
- layout visual;
- merge resolvido;
- grid lógico;
- largura efetiva;
- repeat header/autofit;
- estilo/propriedades efetivas;
- semântica acadêmica;
- patching/escrita;
- decomposição de textboxes;
- validação estrutural de tabela.

## Testes congelados antes da v0.4

- v0.1: 11;
- v0.2: 18;
- v0.3: 26;
- edge final: 1;
- **56/56 aprovados externamente**.

A implementação v0.4 deve acrescentar testes para cobertura 1:1 de `tbl/tr/tc`, nested tables, block containers, profundidade, grid cru, propriedades duplicadas, mixed content, textboxes em cells e reutilização em stories secundárias.

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
11. código v0.2: Kimi K3;
12. recorte v0.3: Kimi K3;
13. código v0.3: Kimi K3;
14. verificação externa pós-hardening: Kimi K3;
15. revalidação final v0.3: **56/56, CONGELAR**;
16. contrato v0.4: Kimi K3, **APROVAR COM AJUSTES**, incorporados na decisão 0011.

## Regra de revisão

Decisão técnica relevante:
1. ChatGPT propõe;
2. auditor adequado revisa;
3. ChatGPT integra;
4. Felipe decide quando necessário;
5. registrar e commitar.

Implementação relevante também passa por revisão técnica antes da próxima fatia.

## Próximo passo

**Implementar a v0.4** conforme decisão 0011, executar regressões e testes adversariais locais e então submeter o código real ao Kimi K3.

Não iniciar Analysis View antes de congelar a v0.4.