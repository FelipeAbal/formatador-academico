# Decisão 0019 — Decision Vocabulary v0.1

Status: **APPROVED / FROZEN FOR DECISION LAYER V0.1**

## Contexto

A Analysis View v0.1a/v0.1b já está congelada. A próxima camada compara fatos analíticos com regras de perfil validadas. Antes de implementar a Decision Layer, era necessário tornar P1–P9 endereçáveis em granularidade de propriedade sem decompor prematuramente todos os aspectos macro.

## Princípio

A unidade lógica de vocabulário da Decision Layer é:

```text
DecisionKey = (target_type, aspect_id, property_slot)
```

`physical_anchor` pertence ao `DecisionTarget`, não à chave lógica. `target_class` é contexto externo de classificação e não faz parte do vocabulário da propriedade.

## Convenção de nomes

- ASCII;
- lowercase;
- `snake_case` para nomes atômicos;
- ponto apenas para decomposição real de uma spec (`spacing.line`);
- sem nomes OOXML (`w:sz`, `w:jc` etc.) na API de decisão;
- sem rótulos traduzidos de UI;
- nomes semânticos estáveis.

## decision_vocabulary_version

Todo envelope serializado da Decision Layer deve carregar um identificador explícito de versão do vocabulário:

```text
decision_vocabulary_version = "0.1"
```

Expansões futuras do vocabulário são aditivas; alteração de significado ou renomeação exige nova versão.

## Vocabulário v0.1 congelado

| aspect_id | target_type | property_slot | Analysis source |
|---|---|---|---|
| P1 | run | `bold` | `ResolvedRunFormatting.bold` |
| P1 | run | `italic` | `ResolvedRunFormatting.italic` |
| P2 | run | `font_size` | `ResolvedRunFormatting.font_size` |
| P3 | paragraph | `spacing.line` | `ResolvedParagraphFormatting.spacing.line` |
| P4 | paragraph | `alignment` | `ResolvedParagraphFormatting.alignment` |

A tabela `property_slot -> Analysis source` é a única fronteira autorizada entre o vocabulário de decisão e o modelo público da Analysis. O acoplamento não deve ser disperso pelo código.

## P1 — destaque tipográfico

`bold` e `italic` são slots distintos sob o mesmo aspecto P1.

Não criar novos aspectos como `P1-bold`/`P1-italic`.

### Limitação conhecida v0.1

Regras cross-slot de destaque, por exemplo uma regra de aspecto do tipo:

```text
allowed = [bold, italic]
```

operando sobre alternativas entre slots, ficam **fora da Decision Layer v0.1**. A v0.1 suporta comparação por slot. Uma futura regra cross-slot deverá ser adicionada como extensão de regra sem renomear ou reinterpretar `P1/bold` e `P1/italic`.

## P2 — fonte

Na v0.1, P2 expõe apenas:

```text
font_size
```

Slots futuros como `font.ascii`, `font.h_ansi`, `font.east_asia` etc. poderão ser adicionados de forma estritamente aditiva quando a Decision Layer passar a suportá-los.

## P3 — espaçamento

Na v0.1:

```text
spacing.line
```

`spacing.before`, `spacing.after`, `spacing.before_lines` e `spacing.after_lines` permanecem fora do vocabulário formal até entrarem em implementação.

## P4 — alinhamento

Na v0.1:

```text
alignment
```

Não usar `paragraph_alignment`, pois `target_type=paragraph` já fornece a categoria física.

## P5–P9

P5–P9 permanecem macro e não são decompostos nesta decisão.

Especialmente:
- P5 recuos: `indent.*` ainda não congelado;
- P6 página: fora da Analysis atual;
- P7 notas: fora do slice atual;
- P8 apresentação de citação: depende de classificação acadêmica externa;
- P9 sistema de citação: semanticamente distinto de formatação física.

Regra: um slot só entra no vocabulário formal quando a Decision Layer efetivamente o suporta.

## TargetClassification

`target_class` é input externo e separado. Exemplo:

```text
target_class = body
target_type = run
aspect_id = P2
property_slot = font_size
```

`body` não entra em `property_slot`.

Regras para `body` e `heading_1` podem usar o mesmo `P2/font_size`; a diferença está no contexto/classificação, não no vocabulário da propriedade.

## Extensibilidade garantida

Adições futuras como:

```text
P2 / run / font.ascii
P3 / paragraph / spacing.before
P5 / paragraph / indent.first_line
```

não alteram a semântica dos cinco slots v0.1.

## Reabertura

Reabrir apenas por:
- falha de teste ou impossibilidade técnica;
- contradição nova;
- mudança explícita de escopo;
- novo risco de segurança;
- necessidade demonstrada de breaking change no vocabulário.
