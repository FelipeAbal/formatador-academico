# 0044 — Product Input Boundary v0.1 — freeze

**Status:** CONGELADO

## Decisão

Congelar o Product Input Boundary v0.1 conforme contrato 0043 e implementação mergeada no PR #16.

## Fronteira pública congelada

```text
build_product_from_inputs(
    package_snapshot: bytes,
    profile_json_bytes: bytes,
    *,
    max_applied_operations: int = 10000,
) -> ProductOutputBundle
```

A camada compõe exclusivamente:

```text
Profile Input JSON bytes
→ processing_profile_from_json
→ ProcessingProfile
→ build_product_output_bundle
→ ProductOutputBundle
```

Sem nova autoridade normativa.

## Ordem determinística congelada

1. validar `package_snapshot` como `bytes` exato;
2. validar `profile_json_bytes` como `bytes` exato;
3. validar/construir Profile Input;
4. somente então executar Product Output Bundle;
5. retornar apenas bundle completo.

Perfil inválido/unsupported nunca alcança processamento de DOCX.

## Error boundary congelado

Público:

```text
ProductInputBoundaryError
ProductInputBoundaryContractError
ProductInputBoundaryUnsupportedError
ProductInputBoundaryIntegrityError
```

Stages:

```text
external_input
profile_input
product_output
```

Regras:
- tipos externos errados → `external_input.package_type` / `external_input.profile_type`;
- ProfileInput ContractError → ContractError com prefixo `profile_input.`;
- ProfileInput UnsupportedError → UnsupportedError com prefixo `profile_input.`;
- ProductOutputBundle ContractError → `product_output.contract`;
- ProductOutputBundle IntegrityError → `product_output.integrity`;
- `__cause__` upstream preservado;
- programming/unexpected errors não são mascarados.

## Atomicidade

Não há sucesso parcial. A API retorna exatamente um `ProductOutputBundle` completo ou levanta erro.

## Determinismo e autoridade negativa

A camada:
- não interpreta norma;
- não inventa defaults;
- não abre DOCX/ZIP/OOXML diretamente;
- não reanalisa/reclassifica/redecide;
- não altera outputs;
- não persiste estado;
- não usa filesystem/network/clock/random/LLM/dynamic import.

Mesmos inputs semânticos produzem o mesmo bundle da composição manual das APIs congeladas.

## Evidência

- PR #16;
- head final: `4b987fca29c42eb5f80ad5da3ef506209fb50945`;
- squash merge: `5cbf53a798ef7d9e78e56f2993e466af43b21d7f`;
- CI no PR: **699/699 OK**;
- CI no `main` pós-merge: **success**;
- failures: 0;
- errors: 0.

Cobertura inclui no-change, bold, font_size, ReviewItem, Patcher rejection, operation limit, canonicalização JSON numérica/ordem, equivalência com composição manual, inputs imutáveis, error-stage/code/cause, perfil inválido sem downstream e exceção inesperada não mascarada.

## Consequência de produto

A partir deste freeze, o core possui uma fronteira user-facing completa:

```text
DOCX bytes
+ Profile Input JSON bytes
→ ProductOutputBundle
    → clean DOCX
    → review DOCX
    → canonical Processing Report JSON
```

A próxima lacuna já não é ligação do core, mas apresentação/entrega e expansão segura de capacidades.
