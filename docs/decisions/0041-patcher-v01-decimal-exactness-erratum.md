# 0041 — Patcher v0.1 Decimal exactness erratum

**Status:** ACEITO COMO ERRATA DE SEGURANÇA — validação final junto ao PR #15; não altera o contrato normativo congelado em 0028/0029.

## Motivo de reabertura

A auditoria adversarial do Profile Input v0.1 revelou um bug de implementação pré-existente no Patcher v0.1. O contrato 0028 §15 já exigia explicitamente:

```text
half_points = points * 2
inteiro exato
sem arredondamento
```

A implementação, porém, realizava `Decimal * 2` sob o contexto Decimal global/default antes de verificar integralidade. Para valores com mais dígitos significativos que a precisão corrente, essa multiplicação pode arredondar silenciosamente e produzir um inteiro diferente do valor declarado.

Exemplo adversarial:

```text
Decimal("1.000000000000000000000000000005")
```

Sob contexto default, `* 2` pode arredondar para um valor integral e o Patcher poderia emitir `w:sz="2"`, violando o próprio contrato de no-rounding.

Isso é gatilho legítimo de reabertura de freeze por **novo risco de segurança / implementação contraditória com contrato congelado**.

## Correção

`half_points_lexical` passa a calcular half-points por aritmética inteira exata derivada de `Decimal.as_tuple()`:

1. coeficiente decimal é reconstruído como inteiro;
2. multiplicação por 2 ocorre em inteiro Python;
3. expoente >= 0 usa potência inteira de 10;
4. expoente < 0 exige divisibilidade exata pelo denominador `10**(-exp)`;
5. qualquer resto => `unrepresentable_value`;
6. limite `MAX_HALF_POINTS=3276` permanece inalterado;
7. output lexical permanece inteiro decimal canônico.

Nenhuma operação Decimal sujeita ao contexto global decide representabilidade.

## Semântica preservada

Continuam exatamente iguais:

```text
12 pt    -> 24
11.5 pt  -> 23
11.25 pt -> rejected / unrepresentable_value
1638 pt  -> 3276
>1638 pt -> rejected / unrepresentable_value
```

A errata não:
- expande o slice;
- muda OperationPlan/SafetyGate;
- muda tipos públicos de valor;
- altera OOXML permitido;
- adiciona arredondamento;
- relaxa qualquer gate.

Ela apenas torna a implementação fiel ao contrato já congelado.

## Capacidade pública

`MAX_HALF_POINTS` passa a ser exportado publicamente pelo pacote `patcher` de forma aditiva, para que boundaries de capacidade como Profile Input não dupliquem magic numbers e possam rejeitar cedo valores que o executor atual não representa.

## Testes obrigatórios

- Decimal adversarial acima deve ser rejeitado, nunca arredondado;
- resultado independente de `decimal.getcontext().prec`;
- 12 -> 24;
- 11.5 -> 23;
- 11.25 rejeitado;
- 1638 -> 3276;
- acima do limite rejeitado;
- toda suíte congelada deve permanecer verde.

## Freeze

Esta decisão será considerada congelada quando o PR #15 integrar a correção com CI completo verde e o `main` pós-merge também permanecer verde. O HANDOFF deve registrar explicitamente a errata 0041 junto ao freeze do Profile Input.
