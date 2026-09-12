# 0017 — Freeze Analysis View v0.1b Marco 1

## Status

**FROZEN**

A Analysis View v0.1b — Formatting Resolution View, Marco 1 (propriedades não-toggle), foi implementada no PR #3, corrigida conforme a errata normativa 0016, auditada contra o código publicado e mergeada.

## Base contratual

- `0015-analysis-v01b-formatting-resolution-contract.md`
- `0016-analysis-v01b-style-selection-errata.md`

A 0016 prevalece sobre os pontos conflitantes da 0015 relativos a seleção de styles.

## PR auditado

- PR: #3
- branch: `analysis-v01b-formatting-m1`
- head final auditado: `294316174624f7ece7b15d0f12b525a0f538f16d`
- merge commit: `4850dc264d28b50f5f480888a13662331772417e`

## Escopo congelado do Marco 1

Implementado:
- modelos públicos imutáveis de resolução/evidence/specs;
- `RawPropertyBag` como único extrator local de `pPr`/`rPr`;
- `StyleCatalog` derivado de `word/styles.xml` + verificação por SHA-256 contra inventário da PhysicalIR;
- `docDefaults`;
- cascade de parágrafo;
- resolução não-toggle de run: `w:sz`, `w:rFonts`, `w:lang`, `w:u`, `w:vertAlign`;
- paragraph formatting: `pStyle`, `w:jc`, `w:spacing`, `w:ind`;
- cláusula conservadora numbering↔indent;
- evidence chain completa;
- statuses fechados `resolved`, `absent`, `unresolved`, `invalid`, `ambiguous`;
- serialização determinística;
- falha parcial por propriedade/slot;
- testes unitários e E2E.

## Correções normativas incorporadas antes do freeze

### Duplicate styleId
- primeira ocorrência documental é o referencial normativo do ID;
- referências `pStyle`, `rStyle` e `basedOn` resolvem para a primeira definição;
- warning `formatting_duplicate_style_id` permanece documental;
- não gera `ambiguous`.

### Multiple default styles
- última ocorrência documental do mesmo tipo vence;
- warning `formatting_multiple_default_styles` permanece documental;
- não gera `ambiguous`.

### styleId ausente
- `StyleEntry.style_id: str | None`;
- ausência física = `None`;
- IDs não são inventados;
- styles sem ID podem ser default e não contam como duplicidade entre si.

### type ausente
- default normativo = `paragraph`.

### ambiguous
No Marco 1 fica reservado a duplicate property conflitante no mesmo container/slot sem precedência normativa segura.

## Auditoria final

A revisão final conferiu o PR real publicado e confirmou:
- head correto;
- PR mergeável antes do merge;
- seis arquivos alterados, sem alterações nos artefatos congelados anteriores;
- remoção dos caminhos antigos de ambiguous para duplicate style/default;
- seleção normativa por primeira definição de styleId e última definição default;
- ausência de `styleId` preservada como `None`;
- `w:type` ausente normalizado para `paragraph`.

Foi também verificado que, quando `rStyle` é omitido, nenhum character style é aplicado; portanto `use_default=False` para character style em resolução de runs está correto.

## Testes

Resultado reportado e executado pelo implementador sobre clone fresco do head remoto:
- **222 testes**;
- **222 passes**;
- **0 failures**;
- **0 errors**;
- **0 skips**.

Regressões congeladas preservadas:
- parser v0.4 + v0.1a: **154/154**.

## Fora do Marco 1

Permanece fora e NÃO está congelado como implementado:
- `w:b`;
- `w:i`;
- demais toggles;
- theme resolution real;
- numbering.xml completo;
- table styles;
- section/page;
- renderer/layout;
- profile acadêmico;
- SafetyGate;
- patching.

## Regra de reabertura

Reabrir somente por:
- falha de teste;
- impossibilidade técnica demonstrada;
- contradição normativa/arquitetural nova;
- mudança explícita de contrato/escopo;
- novo risco de segurança.

## Próxima etapa

Implementar somente o **Marco 2 da v0.1b**: `w:b` e `w:i` com semântica toggle da decisão 0015, mantendo a distinção entre composição de style hierarchy e direct formatting absoluto.
