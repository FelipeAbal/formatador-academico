# Decisão 0031 — Freeze do TransformLog / Execution Record v0.1

Status: **FROZEN**

Date: 2026-09-08

## 1. Escopo congelado

TransformLog v0.1 registra, como proveniência forense imutável e determinística, uma transformação **efetivamente aplicada** pelo Patcher/Applicator v0.1.

Fronteira pública congelada:

```text
GateClearedOperation
+ PatchResult(APPLIED)
+ source Decision
→ TransformRecord
```

O TransformLog não decide, não autoriza, não bloqueia, não reavalia compliance, não lê DOCX/XML/ZIP e não modifica o documento.

Slice v0.1:

```text
P1 / run / bold
P2 / run / font_size
```

## 2. Sequência arquitetural

Pipeline real após 0031:

```text
DOCX
→ Parser
→ Analysis
→ Classification
→ Decision
→ OperationPlan
→ SafetyGate
→ GateClearedOperation
→ Patcher
→ PatchResult(APPLIED)
→ TransformRecord
```

A ordem conceitual antiga `SafetyGate -> TransformLog -> XML patch` fica definitivamente esclarecida: antes do patch existe intenção/autorização, não transformação realizada. O registro forense final nasce somente após sucesso do Patcher, quando os hashes de entrada e saída existem.

## 3. Applied-only

TransformRecord existe somente para `PatchResult.status == applied`.

Não há TransformRecord para:
- SafetyGate blocked;
- PatchResult rejected;
- exceções internas;
- warnings/review humanos.

A ausência de TransformRecord, isoladamente, não indica sucesso nem falha. Relatórios completos futuros devem combinar SafetyGateReport, PatchResult, Decisions e TransformRecords conforme necessário.

## 4. Cross-binding obrigatório

Antes de construir o record, o builder revalida:

### PatchResult ↔ GateClearedOperation

```text
patch_result.operation_ref == cleared_operation.operation_ref
patch_result.operation_plan_ref == cleared_operation.operation_plan_ref
patch_result.input_package_sha256 == cleared_operation.current_package_sha256
```

Também revalida que:

```text
cleared_operation.operation_ref
==
canonical operation_ref(cleared_operation.operation)
```

### source Decision ↔ PlannedOperation

```text
sha256(serialize_decision(source_decision))
==
operation.decision_ref
```

E exige:
- `actionability == deterministic_change`;
- `rule_ref != None`;
- target completo equivalente;
- perfil/regra coerentes;
- `rule_ref.aspect_id` compatível com o target;
- observed/desired equivalentes à projeção semântica congelada do OperationPlan.

## 5. Conversão semântica congelada para font_size

A Decision Layer guarda `font_size` como `Decimal` em pontos.

O OperationPlan v0.1 materializa isso como:

```text
LengthValue(value=<Decimal>, unit="pt")
```

TransformLog valida esta equivalência deliberada sem replanejar nem redecidir.

Para bold, exige `bool` exato; `1/0` não é aceito como substituto por igualdade Python.

## 6. TransformRecord congelado

Campos:

```text
transform_log_version
patcher_version
operation_ref
operation_plan_ref
decision_ref
profile_ref
rule_ref
target
precondition_observed
desired_value
input_package_sha256
output_package_sha256
changed_part
```

`target` reutiliza `OperationTarget` e inclui:
- target_type;
- structural_path;
- physical_hash pré-transformação;
- target_class;
- aspect_id;
- property_slot.

Não armazena:
- output DOCX bytes;
- GateClearedOperation;
- PatchResult;
- Decision inteira;
- raw XML;
- timestamp/UUID/hostname.

## 7. Proveniência normativa

Além de `decision_ref`, o record copia:

```text
ProfileRef
RuleRef
```

Isso permite que relatórios futuros expliquem qual perfil e qual regra originaram a correção sem depender de recuperar a Decision inteira nem reler o DOCX apenas para descobrir a motivação normativa.

## 8. Valores semânticos

TransformRecord registra valores semânticos do OperationPlan/Patcher boundary:

```text
bold: true → false
font_size: LengthValue(11pt) → LengthValue(12pt)
```

Não expõe half-points, `w:b`, `w:sz`, `w:val` ou qualquer detalhe OOXML.

## 9. structural_path

Para o slice property-only v0.1, o mesmo `structural_path` continua resolvendo o run no output, conforme postcondition do Patcher.

Portanto o único `target.structural_path` serve como localização estável pré/pós dentro dos snapshots vinculados pelos package hashes.

Isso NÃO se estende automaticamente a futuras operações MOVE/INSERT/MERGE.

## 10. Sem post-transform physical_hash

O record não contém `target_physical_hash_after`.

Racional:
- output package SHA vincula todo snapshot de saída;
- o Patcher já valida semanticamente a saída;
- o mesmo path é estável no slice atual;
- o próximo ciclo Parser/Analysis produz um novo physical_hash quando necessário;
- TransformLog permanece sem DOCX/XML IO.

## 11. Serialização e transform_ref

`TRANSFORM_LOG_VERSION = "0.1"`.

Serialização canônica segue Decision/OperationPlan:
- dataclasses → objects;
- enums → strings;
- Decimal → strings;
- tuples → arrays;
- sort_keys;
- compact separators;
- UTF-8;
- sem clock/random/locale.

```text
transform_ref(record)
=
sha256(serialize_transform_record(record))
```

`transform_ref` é derivado e não fica armazenado no record.

## 12. Determinismo

Mesmos inputs:

```text
GateClearedOperation
+ PatchResult(APPLIED)
+ source Decision
```

produzem bytes de serialização idênticos e mesmo `transform_ref`.

## 13. One-record-per-patch

Patcher v0.1 aplica uma operação por chamada. Portanto:

```text
1 APPLIED PatchResult
→ 1 TransformRecord
```

Não existe envelope batch/session no v0.1.

Também não se deve inferir ordem de aplicação por `transform_ref`, `structural_path`, `operation_ref` ou ordem canônica de serialização.

## 14. Package lineage

Cada record preserva:

```text
input_package_sha256
output_package_sha256
```

Futuramente, uma sessão poderá validar:

```text
record N.output_package_sha256
==
record N+1.input_package_sha256
```

A validação de cadeia fica fora do TransformLog v0.1.

## 15. Error model

Congelado:

```text
TransformLogError
TransformLogContractError
TransformLogIntegrityError
```

ContractError:
- tipos errados;
- PatchResult não APPLIED;
- versão/artefato não suportado;
- operação fora do slice v0.1.

IntegrityError:
- refs/hashes divergentes;
- Decision ref divergente;
- Decision ↔ operation target/value/provenance incoerente;
- origem normativa impossível/incompatível.

Não existe status `rejected` para TransformRecord.

## 16. Auditoria e hardening

Contrato 0030 foi proposto e auditado por ChatGPT antes/durante implementação.

Achados incorporados:
1. `decision_ref` sozinho era insuficiente para relatório autocontido → ProfileRef/RuleRef copiados;
2. `font_size` Decision Decimal ≠ OperationPlan LengthValue(pt) → equivalência explícita conforme planner congelado;
3. slice de runtime explicitamente fechado em P1/bold + P2/font_size;
4. bold exige bool exato, evitando `1 == True` como bypass de proveniência;
5. E2E real foi estendido até TransformRecord.

Não foi necessário Kimi para programação desta etapa; uso externo ficou restrito à execução da suíte final.

## 17. Validação final

Head final do PR #10:

`d0a5d94e0c7345baeb5012860773bce6027aa245`

Squash merge:

`eff4770f2f5ec848d0f5d6b9afb6b2cdfdc8e355`

Resultados:
- TransformLog específico: **21/21 OK**;
- suíte completa: **524 testes descobertos**;
- rodada 1: **524/524 OK**;
- rodada 2: **524/524 OK**;
- rodada 3: **524/524 OK**;
- failures: 0;
- errors: 0;
- skips: 0;
- working tree limpa antes/depois.

E2E verde:

```text
Parser
→ Analysis
→ Classification
→ Decision
→ OperationPlan
→ SafetyGate
→ Patcher
→ TransformRecord
```

Caso Decimal → LengthValue(pt) também verde.

## 18. Dívidas que permanecem

- processing/session envelope;
- multi-record chain validator;
- user-facing Processing Report;
- review/highlight DOCX;
- rejected/blocked event ledger;
- exception telemetry;
- target post-transform physical_hash;
- multi-operation transaction;
- spacing/alignment patching;
- secondary stories;
- `w:szCs` production gap.

## 19. Freeze

**TransformLog / Execution Record v0.1 está congelado.**

Mudanças semânticas ou de serialização exigem nova decisão/versionamento.

Próximo estágio deve começar por contrato.
