# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; parser físico v0.4 formalmente congelado; **Analysis View v0.1a — Normalized Text View — implementada, auditada, endurecida, mergeada e formalmente congelada.**

Validação corrente:
- parser v0.4: **102/102** regressões preservadas;
- suíte total após v0.1a: **154/154**;
- failures: 0;
- errors: 0;
- skips: 0.

Próxima etapa: **Analysis View v0.1b — Formatting Resolution View**. Abrir novo ciclo técnico, com contrato e auditoria próprios antes de código.

Este é o HANDOFF corrente. O histórico fica no Git; não criar `handoff_vNN`.

## Regra operacional

**Tudo o que puder ser corrigido com segurança dentro do escopo atual deve ser corrigido antes de avançar.**

Só postergar quando houver expansão explícita de escopo, dependência ainda não resolvida, impossibilidade técnica demonstrada ou nova decisão arquitetural que exija auditoria própria.

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
Parser físico/forense, sem análise acadêmica ou transformação. Garantias: imutabilidade, nenhuma perda silenciosa, rastreabilidade, opacos protegidos, determinismo e convenções compartilhadas com o patcher.

### 0004 — Estratégia DOCX
**OOXML + lxml autoritativo.** `python-docx` apenas auxiliar.

### 0005–0010 — Parser v0.1 a v0.3
- hardening do parser inicial;
- decomposição de parágrafos/runs;
- stories secundárias;
- parse parcial;
- freeze v0.3 em `docs/decisions/0010-freeze-parser-v03.md`.

### 0011 — Contrato v0.4: tabelas
`docs/decisions/0011-parser-v04-table-contract.md`

Incluiu:
- `table -> table_row -> table_cell -> blocks`;
- `block_container` (`sdt`, `sdtContent`, `customXml`);
- nested tables;
- `max_structural_depth = 64`;
- grid/merges crus, sem validação/interpretação;
- identidade física de blocos aninhados por path.

### 0012 — Freeze parser v0.4
`docs/decisions/0012-freeze-parser-v04.md`

Suíte congelada:
- **102 testes**;
- **102 passes**;
- 0 failures/errors/skips.

Parser versão: **0.4.0**.

### 0013 — Contrato Analysis View v0.1a
`docs/decisions/0013-analysis-v01a-normalized-text-contract.md`

A Analysis View foi dividida em:
1. v0.1a — Normalized Text View;
2. v0.1b — Formatting Resolution View.

Contrato da v0.1a:
- unidade = parágrafo;
- `segments[]` autoritativo;
- `default_text` derivado;
- um segmento por fragmento físico;
- offsets em code points da `str` Python;
- não participantes zero-width;
- `instrText`, `delText`, `sym` fora da projeção padrão;
- `w:sym` cru, sem U+FFFD;
- Analysis View imutável, determinística, serializável e sem mutar PhysicalIR.

### 0014 — Freeze Analysis View v0.1a
`docs/decisions/0014-freeze-analysis-v01a.md`

PR #2:
- branch: `analysis-v01a-normalized-text`;
- base auditada: `8c4a1ab46d15f753e617aa34b9e72ef429f9e775`;
- head final auditado: `0e1c31ab04735aea7e9f2c688560172203e5e94c`;
- merge commit: `88359be93f68a2ee664d16144f87ee7a3fdc9425`.

Auditoria adversarial pelo Kimi K3 encontrou e corrigiu antes do freeze:
- `opaque_paragraph_child`, `non_element_paragraph_child` e `opaque_container_child` desapareciam silenciosamente;
- break desconhecido/ilegível podia virar `LINE_BREAK` por falsa precisão;
- faltavam testes end-to-end com PhysicalIR real.

Hardening final:
- opacos estruturais => `OPAQUE` zero-width com provenance;
- unknown node com provenance => `normalized_unexpected_fragment` + OPAQUE;
- `w:br` sem type ou `textWrapping` => `\n`;
- page/column => zero-width estrutural;
- break desconhecido/ilegível => OPAQUE zero-width + `normalized_unknown_break_type`;
- adicionados testes `DOCX sintético -> DocxParser -> PhysicalIR real -> normalize_paragraph`.

Suíte final:
- **154 testes**;
- **154 passes**;
- **0 failures**;
- **0 errors**;
- **0 skips**;
- **102/102 testes congelados do parser preservados**.

Determinismo cross-process/hashseed confirmado pelo auditor.

Dívida aceita: `raw_text=""` em vez de `None` quando a chave textual falta em fragmento manualmente malformado; caso não produzido pelo parser real.

## Parser físico congelado

Versão: **0.4.0**

Arquivo:
`src/formatador_academico/docx_parser.py`

A PhysicalIR cobre package/ZIP/OPC, body, paragraphs, runs, run containers, fragments, block containers, tables/rows/cells, nested tables, propriedades cruas, tblGrid/gridCol, footnotes, endnotes, headers, footers, comments, stories ausentes/órfãs/falhadas/rejeitadas, parse parcial e textboxes detectados como opacos.

Identidade física global:
`part + story_id + structural_path + original_index + physical_hash`.

`children[]` é árvore autoritativa. Refs auxiliares não substituem a árvore.

Story `missing`, `failed` ou `rejected` é região não editável.

### Fora do parser
- layout visual;
- merge resolvido;
- grid lógico;
- largura efetiva;
- estilo/formatação efetiva;
- semântica acadêmica;
- patching/escrita;
- decomposição de textboxes.

## Analysis View v0.1a congelada

Arquivos:
- `src/formatador_academico/analysis/__init__.py`
- `src/formatador_academico/analysis/model.py`
- `src/formatador_academico/analysis/normalized_text.py`
- `tests/test_analysis_normalized_text_v01a.py`
- `tests/test_analysis_normalized_text_v01a_e2e.py`

Garantias:
- provenance por fragmento físico;
- nenhum opaco relevante desaparece silenciosamente;
- sem falsa precisão em break desconhecido;
- offsets monotônicos e zero-width para não participantes;
- `default_text` reconstruível dos segmentos;
- serialização determinística;
- sem objetos lxml vivos na saída;
- PhysicalIR não modificada.

Regra de reabertura da v0.1a: somente falha de teste, impossibilidade técnica demonstrada, contradição nova, mudança explícita de contrato/escopo ou novo risco de segurança.

## Próxima etapa — Analysis View v0.1b: Formatting Resolution View

**Abrir novo chat no Kimi K3.**

Primeiro passo: contrato e auditoria arquitetural, sem código.

Questões centrais a fechar:
- fronteira correta para `styles.xml`;
- `StyleCatalog` derivado;
- `docDefaults`;
- paragraph/character styles e `basedOn`;
- cycles e referências quebradas;
- precedência/cascade OOXML real;
- boolean/toggle properties;
- font specs vs theme resolution;
- tamanho em half-points -> pt com provenance;
- propriedades mínimas de run/parágrafo;
- estados `resolved/unresolved/ambiguous/absent`;
- provenance da formatação efetiva;
- falha parcial por propriedade;
- warnings analíticos separados;
- manter v0.1b independente de perfil acadêmico e sem autorização de mutação.

Não implementar v0.1b antes de fechar o contrato e auditá-lo.