# Decisão 0033 — Freeze do Processing Session / Orchestration v0.1

Status: **FROZEN**

Date: 2026-09-08

## 1. Escopo congelado

Processing Session v0.1 coordena o pipeline já congelado sobre snapshots sucessivos do mesmo DOCX até a automação segura atingir quiescência.

API pública:

```text
process_document(
    package_snapshot: bytes,
    profile: ProcessingProfile,
    *,
    max_applied_operations: int = 10000,
) -> ProcessingSessionResult
```

A sessão não cria nova autoridade normativa e não contorna nenhum gate downstream.

## 2. Pipeline operacional congelado

Por iteração:

```text
current DOCX bytes
→ Parser
→ StyleCatalog / Analysis
→ Classification
→ Decision
→ OperationPlan
→ SafetyGate
→ no máximo 1 GateClearedOperation
→ Patcher
→ PatchResult
→ TransformRecord se APPLIED
→ novo snapshot
→ pipeline completo novamente
```

Tokens do SafetyGate anterior nunca são reutilizados após APPLIED.

## 3. Slice automático

Somente:

```text
P1 / run / bold
P2 / run / font_size
```

RuleBinding v0.1 admite target_class:

```text
body
heading
```

Não há heading-level-specific rule no v0.1 porque o nível não é carregado pelo TargetClassification congelado.

## 4. Perfil mínimo de orquestração

Modelos públicos congelados:

```text
RuleBinding:
    target_class
    target_type
    rule: FormattingRule

ProcessingProfile:
    profile_ref: ProfileRef
    bindings: tuple[RuleBinding, ...]
```

Esse aggregate é deliberadamente mínimo e NÃO é o schema final de perfil/UI do produto.

Restrições:
- target_type == run;
- target_class body|heading;
- apenas P1/bold e P2/font_size;
- uma binding por identidade `(target_class,target_type,aspect_id,property_slot)`;
- caller order não resolve conflitos;
- bold rule value é bool exato;
- font_size rule value é Decimal em pt;
- profile_id/profile_version/rule_id não vazios.

## 5. Ordem determinística

Aplicação usa:

```text
ordem física de parágrafos/runs
→ ordem canônica das bindings no mesmo run
```

Bindings são canonizadas por:

```text
(target_class,target_type,aspect_id,property_slot,rule_id,path_or_empty)
```

OperationPlan serialization order NÃO é application order.

Runs sob containers suportados, como hyperlink, são enumerados recursivamente em ordem PhysicalIR.

## 6. Decision authority

A sessão gera Decisions somente via APIs congeladas:
- `project_run_classification`;
- `project_target_classification`;
- `resolve_run_formatting`;
- `extract_resolved_value`;
- `evaluate_target`.

Ela nunca:
- decide compliance por OOXML cru;
- inventa desired;
- promove abstention;
- reinterpreta RuleMode;
- resolve Analysis ambiguous/invalid/unresolved por heurística.

## 7. Snapshot binding

Cada iteração liga PhysicalIR, StyleCatalog, Classification, Decisions, OperationPlan e SafetyGateReport ao mesmo package SHA.

O conjunto de GateResults deve corresponder exatamente ao conjunto de operações do plano. Cada cleared token deve mapear de volta à Decision/operação canônica correspondente.

Mistura de snapshots ou impossível divergência de refs = `ProcessingSessionIntegrityError`.

## 8. APPLIED

Após patch APPLIED:
1. exatamente um TransformRecord é construído;
2. lineage input/output é verificado;
3. record é acrescentado em ordem real de execução;
4. output bytes viram o snapshot atual;
5. tokens e suppressions do snapshot anterior são descartados;
6. pipeline completo roda novamente.

Original input bytes não são mutados.

## 9. Patcher rejection

Rejeição física legítima não derruba operações independentes.

Suppression vale apenas para o mesmo:

```text
(package_sha256, operation_ref)
```

Após APPLIED mudar o snapshot, o pipeline pode produzir/tentar novamente uma operação fresca.

Reasons que podem virar finding normal:
- `noncanonical_run_properties`;
- `duplicate_target_property`;
- `unrepresentable_value`.

Dentro de uma sessão ligada corretamente, são impossíveis e portanto fail-fast:
- `snapshot_hash_mismatch`;
- `unsupported_operation`.

## 10. Gate blocked

Blocked nunca é enviado ao Patcher.

Bloqueio local não impede operação independente CLEARED.

Global blocked context emite zero tokens executáveis.

Findings finais representam somente o snapshot final/corrente; findings intermediários stale não são reportados como estado final depois de um patch bem-sucedido.

## 11. Status técnico

Congelados:

```text
quiescent
quiescent_with_unapplied
operation_limit_reached
```

`quiescent` NÃO significa “documento plenamente conforme”. Pode haver review, human_choice, preserve, abstention e conteúdo fora de escopo.

`quiescent_with_unapplied` exige deterministic_change final bloqueado/rejeitado.

`operation_limit_reached` exige que reste deterministic_change executável e nenhum patch além do budget é aplicado.

## 12. Operation budget

Default:

```text
10000
```

Exact positive int; bool inválido. Conta apenas patches APPLIED / TransformRecords.

É safety fuse, não promessa de performance.

## 13. Cycle detection

Qualquer output package SHA de APPLIED que já tenha aparecido na mesma sessão → `ProcessingSessionIntegrityError`.

Cycle não é status normal.

## 14. Final state

ProcessingSessionResult preserva:

```text
processing_session_version
status
profile_ref
input_package_sha256
output_package_sha256
output_package_bytes
transforms
final_classifications
final_decisions
findings
```

Final classifications são do snapshot final e preservam abstention/non-applicability.

Final Decisions preservam no_action/review/preserve/human_choice e deterministic changes não aplicáveis.

## 15. SessionFinding

Kinds:
- `gate_blocked`;
- `patch_rejected`;
- `operation_limit`.

Todo finding contém decision_ref, operation_ref, target e reason fechado ao vocabulário correspondente.

Todo finding deve ligar a uma final Decision deterministic_change e ao mesmo target.

Não embute bytes/tokens/reports downstream.

## 16. Result invariants

Obrigatório:

```text
output_package_sha256 == sha256(output_package_bytes)
```

Transform chain:
- first input == session input;
- adjacent output/input hashes iguais;
- last output == session output;
- zero transforms implica input_sha == output_sha.

Todos TransformRecords e final Decisions usam o session ProfileRef.

Status, findings e final deterministic Decisions são cruzadamente coerentes no modelo público frozen.

## 17. Partial parser strictness

Classification congelada exige PhysicalIR `status == ok`; Session v0.1 herda essa exigência.

Parser `partial` (inclusive por secondary story defeituosa) não é silenciosamente bypassado. Suporte seguro a body utilizável com story secundária partial exige contrato upstream futuro.

## 18. Determinismo

Mesmo package bytes + ProcessingProfile + max_applied_operations → mesma semântica e mesmos output bytes no runtime suportado.

Caller binding order não altera output, order de transforms, final Decisions ou findings.

Sem filesystem/network/clock/random/LLM no runtime da sessão.

## 19. GitHub Actions CI

PR #11 introduziu CI em `.github/workflows/tests.yml`:
- pull_request;
- push main;
- Ubuntu;
- Python 3.12;
- requirements.txt;
- `PYTHONPATH=src python -m unittest discover -s tests -v`.

Objetivo operacional: eliminar a dependência de Kimi pago apenas para execução da suíte.

## 20. Auditoria / hardening

Contrato 0032 foi auditado contra as APIs congeladas antes e durante implementação.

Hardening antes do merge:
- `complete` renomeado para `quiescent` para evitar overclaim;
- profile values validados eager;
- rejeições impossíveis promovidas a integrity errors;
- conjunto OperationPlan↔GateResult explicitamente ligado;
- findings restritos a vocabulários válidos;
- finding obrigatoriamente ligado à final deterministic Decision/target;
- result status↔findings↔final Decisions cruzadamente validado;
- somente API pública `decision_ref` usada;
- abstention final preservada;
- caller binding order independente;
- rejection suppression resetada somente quando snapshot muda.

## 21. Testes finais

PR #11 head final auditado:

`20717d2b36f180644675bbc1720357de1e8aa2a6`

Squash merge:

`17b0a37529012a0873c76f27c1072ce297240f5d`

GitHub Actions no PR e no `main` pós-merge:

```text
565/565 OK
failures: 0
errors: 0
skips: 0
```

Cobertura inclui:
- no-change byte-identical;
- one bold / one font;
- bold+font no mesmo run com rerun completo;
- multiple runs/paragraphs em document order;
- hyperlink run;
- heading-only binding;
- caller binding order invariance;
- abstention final;
- final classifications rederived from final snapshot;
- gate global block;
- patch rejection + independent progress + fresh-snapshot retry;
- impossible patch rejection fail-fast;
- operation limit;
- cycle detection;
- transform hash chain;
- input immutability;
- repeat/hashseed determinism;
- profile contracts;
- finding/result adversarial invariants;
- todas as regressões congeladas anteriores.

## 22. Dívidas / não objetivos

- schema final de perfil e UI;
- heading-level rules;
- P3/P4 patching;
- atomic multi-operation transaction/rollback;
- persistence/resume;
- human-readable Processing Report;
- review/highlight DOCX;
- secondary-story execution;
- partial-story isolation;
- `w:szCs` correction;
- performance optimization para grande número de sequential patches.

## 23. Freeze

**Processing Session / Orchestration v0.1 está congelado.**

Mudanças semânticas exigem nova decisão/versionamento.

Próximo estágio recomendado: **Processing Report v0.1 — contrato primeiro**, usando somente os artefatos machine-readable já congelados da sessão.
