# 0016 — Errata normativa da Analysis View v0.1b: seleção de styles

## Status

**APROVADA E INCORPORADA AO CONTRATO 0015**

Esta decisão corrige pontos normativos da decisão 0015 identificados durante a auditoria pré-merge do PR #3. Não reabre parser v0.4 nem Analysis View v0.1a e não altera o escopo do Marco 1 além das regras de seleção de styles.

## Motivo da reabertura

A decisão 0015 tratava dois casos como `ambiguous` por ausência suposta de precedência normativa:
- múltiplos default styles do mesmo tipo;
- `styleId` duplicado relevante à resolução.

Verificação normativa do WordprocessingML mostrou comportamento determinístico para ambos. Pela regra de reabertura do projeto, contradição nova com a especificação exige correção antes do merge.

## 1. Multiple default styles

Se múltiplos `w:style` do mesmo `w:type` declararem `w:default=true`, a **última ocorrência em ordem documental** é o default aplicável.

Política:
- resolução determinística pela última ocorrência;
- manter warning `formatting_multiple_default_styles` como registro documental;
- não usar `ambiguous` neste caso.

A seleção de default é por identidade física da definição (`style_type + posição/structural_path`), não por `styleId`.

## 2. Duplicate `styleId`

Se múltiplas definições declararem o mesmo `w:styleId`, a **primeira ocorrência documental** conserva o identificador; ocorrências posteriores deixam de ser endereçáveis por aquele ID para fins de resolução read-only.

Política:
- manter warning `formatting_duplicate_style_id` no catálogo;
- `pStyle`, `rStyle` e `basedOn` que referenciam o ID original resolvem pela primeira definição documental;
- não usar `ambiguous` para duplicidade de `styleId`;
- a Analysis View NÃO reassina IDs das definições posteriores.

Evidence deve poder registrar que a definição vencedora é a primeira ocorrência normativa, por exemplo `detail="duplicate_style_id_first_definition"`.

## 3. `styleId` ausente

`StyleEntry.style_id` passa a ser:

```text
str | None
```

Semântica:
- `None` = ausência física de `w:styleId`;
- não inventar identificador;
- styles sem `styleId` permanecem no catálogo com identidade física via `structural_path`/posição;
- não são localizáveis por referência de ID inexistente;
- múltiplos `None` NÃO constituem duplicate style id;
- `w:styleId=""` explicitamente declarado permanece string vazia, distinta de ausência.

## 4. Default sem `styleId`

A ausência de `styleId` NÃO impede um style de participar da seleção por `w:default`.

Um style sem ID:
- pode ser default;
- pode ser a última ocorrência default aplicável;
- produz evidence com `style_id=None` e `structural_path` físico;
- não exige ID inventado.

## 5. Interação duplicate ID × default

Os conceitos são independentes:

- **ID referenciável:** primeira ocorrência documental do `styleId`;
- **identidade física:** posição no catálogo + `structural_path`;
- **seleção default:** última definição do tipo com `w:default=true`, por identidade física.

Portanto uma ocorrência posterior com `styleId` duplicado pode não ser referenciável pelo ID original e ainda assim ser o default aplicável.

## 6. `w:type` ausente

Se `w:type` estiver ausente em `w:style`, o valor normativo assumido é:

```text
paragraph
```

Logo `StyleEntry.style_type` deve normalizar ausência para `"paragraph"`, preservando a distinção entre valor normativamente defaultado e valores explicitamente declarados na provenance quando necessário.

## 7. `ambiguous` — lista fechada revisada

Após esta errata, o caso legitimamente suportado no Marco 1 é:

- propriedade duplicada com valores conflitantes no mesmo container/propriedade-slot, quando não há precedência normativa segura.

Saem da lista:
- duplicate `styleId`;
- multiple default styles.

`ResolutionStatus.AMBIGUOUS` permanece no schema público porque ainda é necessário para duplicate property conflitante.

## 8. Warnings

O conjunto de warnings permanece fechado e inalterado:
- `formatting_missing_style`
- `formatting_style_cycle`
- `formatting_invalid_value`
- `formatting_duplicate_property`
- `formatting_wrong_style_type`
- `formatting_multiple_default_styles`
- `formatting_duplicate_style_id`
- `formatting_numbering_present`
- `formatting_styles_part_unreadable`

`formatting_duplicate_style_id` e `formatting_multiple_default_styles` são warnings documentais e não implicam `ambiguous`.

## 9. Impacto no Marco 1

O PR #3 deve ser corrigido na mesma branch:
- `StyleEntry.style_id: str | None`;
- style sem ID não gera falsa duplicata;
- type ausente => `paragraph`;
- default selection => última ocorrência;
- referências por duplicate `styleId` => primeira ocorrência;
- basedOn duplicado => primeira ocorrência e cadeia continua;
- remover maquinário de ambiguity específico de duplicate style id/defaults;
- atualizar testes e adicionar casos adversariais combinados.

Nenhuma outra arquitetura do Marco 1 é reaberta.

## Regra de regressão

Após a correção:
- todos os 154 testes congelados anteriores devem permanecer verdes;
- testes novos do Marco 1 devem ser atualizados para refletir esta decisão;
- não implementar Marco 2 (`w:b`/`w:i`) ainda.
