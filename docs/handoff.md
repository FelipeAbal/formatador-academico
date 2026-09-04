# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; parser físico v0.4 formalmente congelado; **Analysis View v0.1a — Normalized Text View — implementada, auditada, endurecida, mergeada e formalmente congelada**; **contrato da Analysis View v0.1b — Formatting Resolution View — aprovado na decisão 0015 e corrigido normativamente pela decisão 0016.**

Validação corrente congelada:
- parser v0.4: **102/102** regressões preservadas;
- suíte total após v0.1a: **154/154**;
- failures: 0;
- errors: 0;
- skips: 0.

Implementação corrente:
- PR #3 — `analysis-v01b-formatting-m1` — Marco 1 da v0.1b;
- head auditado antes da errata: `550db1a6335e32da29af04252439128536af9a71`;
- suíte reportada antes da errata: **213/213**;
- **NÃO mergear ainda**: corrigir o PR #3 conforme decisão 0016 e reexecutar auditoria adversarial.

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
- opacos estruturais desapareciam silenciosamente;
- break desconhecido/ilegível podia virar `LINE_BREAK` por falsa precisão;
- faltavam testes end-to-end com PhysicalIR real.

Suíte final:
- **154 testes**;
- **154 passes**;
- **0 failures**;
- **0 errors**;
- **0 skips**;
- **102/102 testes congelados do parser preservados**.

### 0015 — Contrato Analysis View v0.1b: Formatting Resolution
`docs/decisions/0015-analysis-v01b-formatting-resolution-contract.md`

Contrato único, implementação em dois marcos internos.

Decisões centrais mantidas:
- `styles.xml` fora da PhysicalIR;
- `StyleCatalog` derivado do OriginalPackage e verificado contra `part_name + sha256` da PhysicalIR;
- `RawPropertyBag` como único extrator local de XML de propriedades;
- statuses fechados `resolved`, `absent`, `unresolved`, `invalid`, `ambiguous`;
- `invalid` terminal por propriedade/slot;
- evidence/provenance completa obrigatória;
- `docDefaults` participa da cascade;
- missing/wrong-type refs => ignore determinístico + warning;
- `w:link` preservado, fora da cascade;
- theme refs são valores documentais `resolved`;
- fonts por slots, sem `effective_font` visual;
- Decimal para unidades exatas;
- falha parcial por `(target, propriedade/slot)`;
- v0.1b ortogonal à v0.1a e independente de perfil acadêmico.

### 0016 — Errata normativa da seleção de styles
`docs/decisions/0016-analysis-v01b-style-selection-errata.md`

Corrige a 0015 antes do merge do Marco 1:

#### Multiple default styles
- se múltiplos styles do mesmo tipo têm `w:default=true`, **a última ocorrência documental vence**;
- manter `formatting_multiple_default_styles` como warning;
- não usar `ambiguous`.

#### Duplicate `styleId`
- **a primeira ocorrência documental conserva o ID**;
- referências `pStyle`/`rStyle`/`basedOn` ao ID original resolvem pela primeira definição;
- ocorrências posteriores permanecem no catálogo por identidade física, mas não são endereçáveis por aquele ID;
- manter `formatting_duplicate_style_id` como warning;
- não usar `ambiguous`.

#### `styleId` ausente
- `StyleEntry.style_id: str | None`;
- `None` significa ausência física;
- não inventar ID;
- múltiplos `None` não contam como duplicidade;
- `w:styleId=""` explicitamente declarado continua distinto de ausência.

#### Default sem `styleId`
- continua elegível como default;
- seleção de default é por identidade física/tipo/ordem, não por `find_styles(style_id)`.

#### `w:type` ausente
- default normativo = `paragraph`.

#### `ambiguous` revisado
No Marco 1 fica legitimamente usado apenas para duplicate property conflitante no mesmo container/slot sem precedência normativa segura.

### Toggle `w:b`/`w:i`

Marco 2 apenas.

**Style hierarchy composition** (`docDefaults` + style chains):
- true/1/omitido => toggle;
- false/0 => no-op.

**Direct formatting:**
- true/1/omitido => `true` absoluto;
- false/0 => `false` absoluto;
- direct terminal.

### Numbering ↔ indent

Numbering completo fora do Marco 1, mas:
- direct indent resolve;
- paragraph-style indent com precedência resolve;
- somente slot que possa depender de numbering não implementado => `unresolved(reason=numbering_indent_unsupported)` + `formatting_numbering_present`.

## Parser físico congelado

Versão: **0.4.0**.

`children[]` é árvore autoritativa. Stories missing/failed/rejected são não editáveis.

## Analysis View v0.1a congelada

Garantias:
- provenance física;
- nenhum opaco relevante desaparece silenciosamente;
- sem falsa precisão em breaks;
- offsets determinísticos;
- serialização determinística;
- sem lxml vivo;
- PhysicalIR não modificada.

## Analysis View v0.1b — Marco 1

Escopo:
1. modelos públicos de resolução/evidence/specs;
2. `RawPropertyBag`;
3. `StyleCatalog` + `docDefaults`;
4. cascade de parágrafo;
5. run NÃO-toggle: `w:sz`, `w:rFonts`, `w:lang`, `w:u`, `w:vertAlign`;
6. paragraph: pStyle, `w:jc`, `w:spacing`, `w:ind`;
7. serialização determinística;
8. testes unitários + E2E;
9. regressão integral dos **154 testes congelados**.

### Fora do Marco 1
- `w:b`, `w:i`, demais toggles;
- theme resolution real;
- numbering completo;
- table styles;
- section/page;
- renderer/layout;
- profile acadêmico;
- SafetyGate;
- patching.

## Próximo passo

**Corrigir o PR #3 na mesma branch `analysis-v01b-formatting-m1` conforme decisão 0016.**

Ao terminar:
1. publicar novo head no mesmo PR;
2. ajustar testes de multiple defaults e duplicate style id;
3. adicionar testes para styleId ausente, default sem ID, type ausente e caso combinado;
4. executar suíte completa real;
5. preservar os 154 testes congelados;
6. trazer novo head e resultados para auditoria adversarial;
7. não mergear nem iniciar Marco 2 antes da revisão final.
