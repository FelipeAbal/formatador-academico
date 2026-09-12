# Nota de decisão 0052C: proveniência da Analysis e escolha humana

**Data:** 2026-09-10  
**Base:** auditorias DeepSeek Flash 4.1 e Claude Opus sobre o P3

## Decisões

1. Observação resolvida, porém incomensurável com a regra declarada, permanece resolvida na Analysis e produz `non_compliant / human_choice / human_choice_required`. Isso se aplica ao P3 observado como `exact` ou `atLeast`, sem converter a altura fixa em múltiplos de linha.
2. Razões produzidas pela Analysis não serão convertidas em valores do vocabulário semântico da Decision Layer. Serão transportadas literalmente pelo campo aditivo opcional `Decision.analysis_reason`.
3. `analysis_reason` será propagado para `ReviewItem` e `UnappliedChangeItem`, e renderizado no relatório humano. Os enums congelados permanecem inalterados.
4. A segunda barreira da regra P3 exige, no OperationPlan, que uma operação determinística de `spacing.line` tenha precondição `LineSpacingValue(rule="auto", unit="multiple")`.
5. A presença de `w:numPr` em `docDefaults/pPrDefault` também bloqueia o spacing P3.
6. `w:lineRule` sem `w:line` usa a razão `line_rule_without_line_unsupported`; essa razão não será usada para valores não inteiros quando `w:line` estiver presente.

## Justificativa

A Analysis conhece o valor de `exact` e `atLeast` com cadeia de evidência. A incomensurabilidade é uma decisão de execução, não ausência de conhecimento. Já listas e bidi são casos em que o valor efetivo não pode ser determinado no slice atual, por isso permanecem `UNRESOLVED` e precisam expor sua razão específica ao usuário.
