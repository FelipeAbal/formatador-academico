# 0042 — Profile Input / Form Schema v0.1 — freeze

**Status:** CONGELADO.

## Escopo congelado

Esta decisão congela a implementação da decisão 0040 após auditoria adversarial, integração dos ajustes, PR #15 e validação completa no `main`.

Também registra como **congelada** a errata de segurança 0041 do Patcher v0.1, integrada no mesmo PR, pois a suíte pós-merge validou a correção no código efetivamente incorporado.

## Evidência de integração

- PR: **#15 — Profile Input / Form Schema v0.1**;
- head final auditado: `516924475ebd945f15c0271b6ea467e98c9c70f2`;
- squash merge: `0429fa5bd115da95e8ed8c55a37099f912854e1a`;
- GitHub Actions no PR: **682/682 OK** no head final;
- GitHub Actions no `main` pós-merge: **682/682 OK** no squash;
- failures: 0;
- errors: 0;
- skips relevantes: 0.

## Fronteira pública congelada

```text
parse_profile_input_json(profile_json_bytes: bytes) -> ProfileInput
build_processing_profile(profile_input: ProfileInput) -> ProcessingProfile
processing_profile_from_json(profile_json_bytes: bytes) -> ProcessingProfile
```

A fronteira user-facing não recebe DOCX e não cria autoridade normativa própria.

## Schema v0.1

Envelope obrigatório:

```json
{
  "schema_version": "0.1",
  "profile": {
    "id": "...",
    "version": "..."
  },
  "rules": {
    "body": {
      "bold": {"mode":"exact","value":false},
      "font_size": {"mode":"exact","value":12}
    },
    "heading": {
      "bold": {"mode":"preserve"}
    }
  }
}
```

Vocabulário v0.1:

```text
target classes: body, heading
properties: bold, font_size
modes: exact, set, preserve
```

Nenhuma regra é criada para campo ausente.

## Autoridade e ausência

Invariantes congelados:

- ausência permanece ausência;
- `null` nunca significa ausência;
- body não herda heading;
- heading não herda body;
- nenhum default normativo é criado;
- o adapter não lê DOCX;
- o adapter não interpreta “ABNT”, revista, evento, TCC ou instituição;
- todo `RuleBinding` interno possui origem em declaração user-facing explícita.

## `preserve`

Mapeamento congelado:

```text
preserve -> RuleMode.CONTAINMENT
```

Semântica:

> NÃO TOCAR + NÃO SINALIZAR por esta regra.

### Clarificação do freeze

A auditoria externa descreveu `preserve` como observacionalmente equivalente à omissão. A implementação e os testes refinam essa afirmação:

- `preserve` e omissão são equivalentes **quanto a transformação normativa, AppliedChangeItem, UnappliedChangeItem, ReviewItem e highlight**;
- clean/review podem permanecer byte-idênticos;
- `preserve` cria uma Decision interna `CONTAINMENT/PRESERVE`, enquanto omissão não cria Decision;
- portanto, o `ProcessingReport` inteiro **não precisa ser byte-idêntico**, pois o summary pode diferir em `final_decision_count`.

Perfil só-`preserve` é válido, mas nunca deve ser apresentado como evidência de conformidade.

## JSON / encoding congelados

- input público aceita `bytes` exato;
- input vazio rejeitado;
- máximo 256 KiB;
- UTF-8 BOM rejeitado;
- decode UTF-8 estrito obrigatório;
- bytes nunca são passados diretamente a `json.loads`;
- UTF-16/UTF-32 válidos como JSON são rejeitados;
- duplicate object keys rejeitados em todos os níveis;
- unknown fields rejeitados;
- `schema_version` é validada antes de unknown fields internos;
- NaN/Infinity/-Infinity rejeitados;
- RecursionError/profundidade patológica é contida em erro de contrato.

## Identidade lexical

`profile.id` e `profile.version`:

- string exata;
- 1..128 code points;
- sem whitespace nas bordas;
- sem controles Unicode `Cc`;
- sem surrogate code points;
- sem normalização Unicode silenciosa.

A identidade é a sequência exata de code points declarada.

### Limitação conhecida

Até existir `profile content hash`, o sistema não consegue provar que uma mudança substantiva de regra foi acompanhada por bump de `profile.version`. Essa dívida permanece aberta e não é mascarada como garantia.

## Regras internas

IDs gerados deterministicamente:

```text
body:bold
body:font_size
heading:bold
heading:font_size
```

Não incluem `schema_version`.

Mapeamento:

```text
bold      -> run / P1 / bold / bool
font_size -> run / P2 / font_size / pt
```

`path=None` no v0.1.

## `set`

- allowed obrigatório e não vazio;
- duplicatas semânticas rejeitadas;
- allowed canonicalizado em ordem determinística;
- preferred, quando presente, deve pertencer a allowed;
- singleton set sem preferred é rejeitado;
- singleton set com preferred é permitido;
- set sem preferred e com múltiplos valores mantém `human_choice` congelado da Decision Layer quando aplicável.

## Decimal / font_size

O boundary congela:

- JSON integer/decimal lido como `Decimal` exato;
- nunca `Decimal(float)`;
- canonicalização baseada em `Decimal.as_tuple()`;
- 12, 12.0 e 1.2e1 tornam-se `Decimal("12")`;
- 11.50 torna-se `Decimal("11.5")`;
- canonicalização independente do contexto Decimal global;
- máximo 32 dígitos significativos;
- expoente suportado no Profile Input v0.1: [-16,16];
- valor deve ser positivo, finito e exatamente representável em half-points;
- 11.25pt é `ProfileInputUnsupportedError`, não arredondado;
- limite superior é derivado da capacidade pública do Patcher (`MAX_HALF_POINTS=3276`).

## Error model

```text
ProfileInputError
ProfileInputContractError
ProfileInputUnsupportedError
```

Cada erro possui `code` estável machine-readable e mensagem técnica curta.

ContractError representa forma/declaração malformada.
UnsupportedError representa declaração bem formada fora do vocabulário/capacidade da versão.

A ordem de validação e o first-error são determinísticos.

## Modelos auto-validantes

`ProfileInputRule` e `ProfileInput` são frozen e auto-validam invariantes independentemente do parser JSON.

Uma futura UI/API que construa os modelos programaticamente não consegue introduzir estado semanticamente inválido que o parser rejeitaria.

## Errata 0041 — Patcher Decimal exactness

A auditoria do Profile Input revelou que o Patcher v0.1, embora seu contrato 0028 já proibisse arredondamento, usava `Decimal * 2` sob o contexto global antes da verificação de integralidade.

A errata congelada substitui essa implementação por aritmética inteira exata derivada de `Decimal.as_tuple()`.

Preservado:

```text
12     -> 24 half-points
11.5   -> 23
11.25  -> rejected / unrepresentable_value
1638   -> 3276
>1638  -> rejected
```

Além disso, expoentes extremos positivos/negativos são rejeitados antes de materializar potências inteiras gigantescas.

`MAX_HALF_POINTS` passa a ser API pública aditiva do pacote Patcher.

A errata não expande o slice nem muda qualquer autoridade normativa; ela torna a implementação fiel ao contrato de no-rounding já congelado.

## Auditoria externa

Claude Opus concluiu **APROVAR COM AJUSTES**. Os três blockers identificados foram incorporados antes da implementação:

1. UTF-8 explícito/estrito;
2. representabilidade Decimal exata sem contexto global;
3. forma canônica Decimal para identidade/determinismo.

Também foram incorporados os ajustes de taxonomia de erros, ordem de validação, identidade lexical, self-validating models, rule IDs cross-schema, preserve, singleton set e testes adversariais.

Nenhuma expansão upstream de autoridade normativa foi necessária.

## Baseline congelado

Suíte completa pós-merge:

```text
Ran 682 tests
OK
```

## Próximo elo

O core agora possui:

```text
Profile Input JSON
→ ProcessingProfile
```

E já possuía:

```text
DOCX + ProcessingProfile
→ ProductOutputBundle
```

O próximo ciclo deve compor essas duas fronteiras numa entrada de produto única, sem criar nova normatividade:

```text
DOCX bytes + Profile Input JSON bytes
→ ProductOutputBundle
```

Esse ciclo é composição/error-boundary, não nova análise ou mutação OOXML.
