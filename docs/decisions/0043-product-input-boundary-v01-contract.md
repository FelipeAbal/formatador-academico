# 0043 — Product Input Boundary v0.1 — contrato

**Status:** ACEITO PARA IMPLEMENTAÇÃO — freeze após PR + CI + auditoria final.

## Objetivo

Compor duas fronteiras já congeladas:

```text
Profile Input JSON bytes -> ProcessingProfile
DOCX bytes + ProcessingProfile -> ProductOutputBundle
```

numa única entrada user-facing:

```text
DOCX bytes + Profile Input JSON bytes -> ProductOutputBundle
```

Sem reimplementar parsing de perfil, Session, Report, Review DOCX ou Bundle e sem introduzir nova autoridade normativa.

## API pública

```text
build_product_from_inputs(
    package_snapshot: bytes,
    profile_json_bytes: bytes,
    *,
    max_applied_operations: int = 10000,
) -> ProductOutputBundle
```

## Ordem determinística

1. `package_snapshot` deve ser `bytes` exato;
2. `profile_json_bytes` deve ser `bytes` exato;
3. parse/build do Profile Input usando exclusivamente `processing_profile_from_json` congelado;
4. `build_product_output_bundle(package_snapshot, processing_profile, max_applied_operations=...)`;
5. retornar somente o `ProductOutputBundle` completo.

Não há fallback nem tentativa de processar DOCX quando o perfil é inválido/unsupported.

## Atomicidade

A função retorna exatamente um `ProductOutputBundle` completo ou levanta erro.

Nunca retorna:
- clean sem review;
- review sem report;
- report parcial;
- ProcessingProfile intermediário como sucesso parcial.

## Error model

```text
ProductInputBoundaryError
ProductInputBoundaryContractError
ProductInputBoundaryUnsupportedError
ProductInputBoundaryIntegrityError
```

Todo erro público possui:

```text
code: string estável
message: string técnica curta
stage: external_input | profile_input | product_output
```

### Tipos externos

- package_snapshot não-`bytes` -> ContractError / `external_input.package_type`;
- profile_json_bytes não-`bytes` -> ContractError / `external_input.profile_type`.

### Profile Input

`ProfileInputContractError(code=X)` vira:

```text
ProductInputBoundaryContractError
stage = profile_input
code = profile_input.X
```

`ProfileInputUnsupportedError(code=X)` vira:

```text
ProductInputBoundaryUnsupportedError
stage = profile_input
code = profile_input.X
```

Mensagem e `__cause__` são preservados.

### Product Output Bundle

`ProductOutputBundleContractError` vira:

```text
ProductInputBoundaryContractError
stage = product_output
code = product_output.contract
```

`ProductOutputBundleIntegrityError` vira:

```text
ProductInputBoundaryIntegrityError
stage = product_output
code = product_output.integrity
```

Mensagem e `__cause__` são preservados.

Erros inesperados/programming errors não são mascarados.

## `max_applied_operations`

O boundary não redefine nem normaliza esse parâmetro.

Ele é encaminhado exatamente ao Product Output Bundle. Validação permanece autoridade da camada congelada; erro correspondente retorna como `product_output.contract`.

## Imutabilidade

A função não modifica:
- `package_snapshot`;
- `profile_json_bytes`.

Não mantém estado entre chamadas.

## Determinismo

Mesmos bytes de DOCX + mesmos bytes semânticos/canônicos de perfil + mesmo limite devem produzir o mesmo Bundle que a composição manual:

```text
profile = processing_profile_from_json(profile_json_bytes)
bundle = build_product_output_bundle(package_snapshot, profile, ...)
```

A fronteira não usa clock, UUID, random, locale, filesystem, network ou LLM.

## Autoridade negativa

Product Input Boundary NÃO:
- cria regra;
- altera ProfileInput;
- inventa default;
- analisa DOCX diretamente;
- abre ZIP/OOXML;
- reclassifica/redecide;
- modifica outputs;
- localiza mensagens;
- cria filenames/downloads;
- renderiza relatório;
- persiste configuração.

É somente composição + tradução de error boundary.

## Testes mínimos

1. no-change E2E JSON+DOCX -> Bundle;
2. bold change E2E;
3. font_size change E2E;
4. review/unapplied preservados;
5. package type errado -> external_input.package_type;
6. profile type errado -> external_input.profile_type;
7. ambos tipos errados -> package_type primeiro;
8. Profile ContractError preserva code prefixado + cause;
9. Profile UnsupportedError preserva code prefixado + cause;
10. invalid DOCX com perfil válido -> product_output.contract;
11. Product Output integrity mocked -> product_output.integrity + cause;
12. max_applied_operations inválido -> product_output.contract;
13. operation_limit status preservado;
14. inputs não mutados;
15. wrapper == composição manual nos três artefatos;
16. repetição determinística;
17. regras JSON em ordem diferente/canonicalização numérica semanticamente equivalente produzem mesmo Bundle;
18. runtime sem IO/network/clock/random/LLM/dynamic import;
19. exceção inesperada não é mascarada;
20. regressão suíte completa.

## Critério de aceite

Congelar somente se:
- não houver nova autoridade normativa;
- nenhum erro de perfil chegar ao pipeline de DOCX;
- causas/códigos do Profile Input forem preservados;
- integridade upstream permanecer distinguível de erro contratual;
- Bundle final for idêntico à composição manual;
- suíte completa estiver verde.
