# 0027 — Freeze SafetyGate v0.1

Status: FROZEN

## Contexto

A decisão 0026 aprovou o contrato do SafetyGate v0.1. O PR #8 implementou o primeiro vertical slice completo:

```text
DOCX
→ Parser
→ Analysis
→ Classification
→ Decision
→ OperationPlan
→ SafetyGate
```

O SafetyGate continua sendo **veto final de segurança, nunca nova autorização normativa**.

## Implementação congelada

PR #8: `SafetyGate v0.1 — vertical slice (decision 0026)`.

Base auditada:

`3b1d9650569997b969b502ba3e7cf0ba69974eec`

Head inicial implementado:

`208c73047abb44a8225919a6764981dfbe11d1c1`

Head final após hardening adversarial:

`a867af747875b3e88047d80844f7eaa2df78db30`

Squash merge:

`d47b8e67d2788eb1912ef951ec7dcedb457376cb`

## Fronteira congelada

```text
OperationPlan
+ source Decisions
+ current PhysicalIR
+ current StyleCatalog
+ active ProfileRef
→ SafetyGateReport
```

O gate:

- não escolhe `desired_value`;
- não redecide conformidade;
- não reclassifica;
- não gera XML;
- não modifica DOCX;
- não produz patch;
- não usa LLM, heurística, score, relógio, random ou IO no core.

## Status e reasons

`GateStatus`:

```text
cleared
blocked
```

`ContextStatus`:

```text
compatible
blocked
```

Reasons globais:

- `source_document_changed`;
- `parser_version_mismatch`;
- `analysis_version_mismatch`;
- `classification_version_mismatch`;
- `profile_context_changed`.

Reasons locais:

- `target_not_found`;
- `target_not_unique`;
- `target_type_mismatch`;
- `physical_hash_mismatch`;
- `current_value_unavailable`;
- `precondition_mismatch`.

## Cadeia de integridade

Antes de qualquer observação semântica, o gate valida fail-fast:

- `source_decisions_hash`;
- duplicatas de source Decision;
- resolução de `decision_ref`;
- binding operation↔Decision;
- `deterministic_change`;
- `rule_ref`;
- versões/kind/story part compatíveis;
- PhysicalIR↔StyleCatalog.

Integridade inválida é exception; nunca `blocked`.

## Global vetoes

Ordem canônica congelada:

```text
package
→ parser
→ analysis
→ classification
→ profile
```

O primeiro mismatch global domina; nenhuma checagem local é executada depois de global block.

Package mismatch bloqueia todo o plano mesmo se algum target hash coincidir.

## Target e precondition

Contexto global compatível permite avaliação por operação.

A ordem local é factual e conservadora:

1. localizar target na story principal;
2. exigir unicidade;
3. validar tipo;
4. validar `physical_hash`;
5. reobservar semanticamente via Analysis pública;
6. exigir `current_semantic_value == precondition_observed`.

`current == desired`, mas diferente da precondition, continua `precondition_mismatch`: o plano está stale e deve ser refeito.

## PhysicalIR ↔ StyleCatalog

O gate revalida o binding usando a identidade de `word/styles.xml`:

```text
StyleCatalog.part_sha256
==
sha256 do part no inventário da PhysicalIR atual
```

+ status de part compatível.

Misturar PhysicalIR A com StyleCatalog B é integrity error.

## Parent/run binding

Runs usam o ancestral `paragraph` físico real da árvore da PhysicalIR; nunca inferência por prefixo textual do `structural_path`.

`paragraph → run_container → run` é suportado.

## Comparação semântica tipada

- bold → `bool`;
- font size → Analysis `Length(pt)` ↔ OperationPlan `LengthValue(pt)`;
- spacing.line → `(rule, value, unit)`; raw forensic fields não entram;
- alignment → token canônico literal.

Nenhuma conversão OOXML acontece no SafetyGate.

## Partial clearance

Com `context_status=compatible`, resultados mistos são válidos.

Uma operação localmente bloqueada não derruba operações independentes.

## GateClearedOperation

Fronteira tipada congelada para o futuro patcher:

```text
GateClearedOperation:
    operation
    operation_ref
    operation_plan_ref
    current_package_sha256
```

Hardening adversarial adicionou invariante obrigatória:

```text
operation_ref == operation_ref(operation)
```

O token não pode carregar operação A com hash de operação B.

`_EMISSION_PROOF` evita promoção acidental via API pública, mas não é tratado como capability security absoluta em Python.

`gate_operation(...)` é helper diagnóstico/unit-level e não emite `GateClearedOperation`.

## SafetyGateReport

O report frozen exige coerência cruzada:

- contexto `compatible` → reasons de blocked results apenas locais;
- contexto `blocked` → todos os results blocked pelo reason global do contexto;
- nenhum cleared token em contexto blocked;
- `cleared_operations` corresponde exatamente e em ordem aos results cleared;
- token e report compartilham `operation_plan_ref` e `current_package_sha256`.

## TOCTOU

O futuro patcher deve operar sobre o MESMO snapshot gateado.

Todo `GateClearedOperation` carrega `current_package_sha256`.

O patcher deve:

```text
sha256(snapshot a aplicar)
==
token.current_package_sha256
```

ou operar diretamente sobre o OriginalPackage imutável que originou o contexto gateado.

É proibido gatear bytes A e reabrir/aplicar silenciosamente bytes B.

## Auditoria adversarial

Achados corrigidos antes do freeze:

1. **BLOQUEADOR:** `GateClearedOperation` não provava `operation_ref ↔ embedded operation`;
2. **IMPORTANTE:** `SafetyGateReport` aceitava combinações incoerentes de global/local reasons;
3. **IMPORTANTE:** `SafetyGateReport` não estava exportado publicamente;
4. **MENOR:** wording de `_EMISSION_PROOF` sugeria garantia absoluta demais;
5. **MENOR:** `gate_operation` precisava deixar explícito que é diagnóstico e não token executável.

Todos os ajustes foram publicados no mesmo PR antes do merge.

## Testes

Head final remoto contém **442 testes descobertos**.

Em 12 execuções do clone limpo:

- 11 execuções: `442/442`;
- 1 execução: `441/442`, com única falha intermitente em `test_hashseed_determinism`;
- 0 errors;
- 0 skips.

A falha foi diagnosticada como **flake do harness sintético**, não regressão do SafetyGate: `build_docx` usa `zipfile.writestr` sem `ZipInfo.date_time` fixo, de modo que subprocessos que cruzam boundary temporal podem produzir ZIPs byte-diferentes e portanto `package_sha256` diferente.

A implementação do produto não usa esse helper. O flake fica registrado como dívida de infraestrutura de testes e não reabre o contrato congelado.

## Dívidas não bloqueadoras

- estabilizar timestamps do helper sintético `build_docx` sem alterar semântica de produto;
- analysis/classification versions ainda são assertions do orchestrator, não provenance criptográfica;
- possível pipeline-context hash futuro;
- equivalência semântica de DOCX reempacotado byte-diferente;
- hash de conteúdo de profile; enquanto não existir, alteração substantiva exige bump de `profile_version`;
- stories secundárias executáveis e `original_index` futuro;
- TransformLog;
- envelope completo de execução snapshot→patch.

## Próximo passo

Contrato do patcher/applicator v0.1.

O patcher deverá consumir **somente `GateClearedOperation`**, operar no mesmo snapshot identificado por `current_package_sha256` e realizar mutações OOXML mínimas, sem reconstruir o DOCX a partir da IR.
