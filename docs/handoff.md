# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; parser físico v0.4 congelado; Analysis View v0.1a/v0.1b congeladas; Decision Vocabulary v0.1 congelado; Decision Layer v0.1 congelada em 0021; Classification Layer v0.1 congelada em 0023; OperationPlan v0.1 congelado em 0025; **SafetyGate v0.1 implementado, auditado, mergeado e congelado em 0027**.

Validação corrente:
- parser v0.4: **102/102**;
- Analysis completa: **267/267**;
- após Decision Layer v0.1: **290/290**;
- após Classification Layer v0.1: **335/335**;
- após OperationPlan v0.1: **389/389**;
- head final SafetyGate: **442 testes descobertos**;
- 11/12 execuções completas: **442/442**;
- 1/12: **441/442** por flake conhecido do helper sintético `build_docx`/timestamp ZIP; nenhuma regressão funcional identificada;
- errors: 0;
- skips: 0.

PRs/freeze principais:
- PR #3 — Analysis v0.1b Marco 1; freeze 0017;
- PR #4 — Analysis v0.1b Marco 2; freeze 0018;
- PR #5 — Decision Layer v0.1; squash `b81f628a0358cbc9483e9207d4f749ea4a2ca475`; freeze 0021;
- PR #6 — Classification Layer v0.1; squash `736c33036224562549b1b5cb026bd6bfdfd2e112`; freeze 0023;
- PR #7 — OperationPlan v0.1; head auditado `871e4a5cc379bbb2b2e04504a871188366718092`; squash `1c11d08dcd6fc219bb2f4e0ce5321db027a5801a`; freeze 0025;
- PR #8 — SafetyGate v0.1; head final auditado/hardened `a867af747875b3e88047d80844f7eaa2df78db30`; squash `d47b8e67d2788eb1912ef951ec7dcedb457376cb`; freeze 0027.

Este é o HANDOFF corrente. O histórico fica no Git; não criar `handoff_vNN`.

## Regra operacional

**Tudo o que puder ser corrigido com segurança dentro do escopo atual deve ser corrigido antes de avançar.**

Só postergar quando houver expansão explícita de escopo, dependência não resolvida, impossibilidade técnica demonstrada, contradição normativa/arquitetural nova ou novo risco de segurança.

Fluxo formal:
1. ChatGPT propõe;
2. modelo apropriado audita;
3. ChatGPT integra;
4. Felipe aprova quando necessário;
5. HANDOFF + decisão/commit.

Para Kimi:
- novo chat por etapa técnica grande;
- começar com HANDOFF + SHA exato do `main` + tarefa fechada;
- GitHub remoto é fonte de verdade;
- implementação só conta com branch/commit/PR real ou diff completo;
- auditoria adversarial antes de merge/freeze.

## Objetivo do MVP

Formatar com segurança DOCX acadêmicos existentes a partir de perfil formal explicitamente declarado. Não promete conformidade ABNT genérica.

Saídas previstas:
1. DOCX limpo;
2. DOCX de revisão;
3. relatório.

Princípio: **Na dúvida, marcar.**

## Segurança congelada

- nenhuma invenção/perda substantiva;
- só atuar em subaspecto autorizado;
- ambiguidade não é resolvida silenciosamente;
- opacos são preservados/protegidos;
- SafetyGate é veto, nunca autorização;
- C3 exige revisão humana;
- precision > coverage na classificação;
- abstention correta é sucesso seguro;
- stale plan/document drift deve ser detectado antes de qualquer patch;
- operação é compare-and-set semântico: observed/precondition + desired.

## Corpus-base v1

- 41 fixtures;
- baseline motor nulo: 20/41 = 48,8%;
- precisão-alvo automática >=99%;
- alto risco desejado >=99,5%;
- tolerância zero a invenção/perda conhecida, dano a campo e alteração indevida de citação direta.

## Physical layer / parser — 0001–0012

Congelado:
- OriginalPackage imutável;
- PhysicalIR serializável/forense;
- OOXML+lxml autoritativo;
- saída nunca reconstruída da IR;
- parser v0.4.0;
- package sha256 + sha256 por part;
- `physical_hash` por alvo;
- stories secundárias parseadas, mas não executáveis neste slice.

## Analysis View v0.1a/v0.1b — 0013–0018

Congelada:
- Normalized Text por segmentos físicos;
- StyleCatalog;
- formatting factual/resolved;
- run: size/fonts/lang/underline/vertAlign/bold/italic;
- paragraph: pStyle/alignment/spacing/indent;
- toggle semantics correta;
- defaults/style chains;
- statuses `resolved/absent/unresolved/invalid/ambiguous`;
- tudo ausente => `absent`, nunca false;
- sem reescrita/sem semântica normativa.

## Decision Vocabulary v0.1 — 0019

```text
P1 / run / bold
P1 / run / italic
P2 / run / font_size
P3 / paragraph / spacing.line
P4 / paragraph / alignment
```

`DecisionKey = (target_type, aspect_id, property_slot)`.

## Decision Layer v0.1 — 0020 + freeze 0021

Pipeline:

```text
Analysis View
+ TargetClassification
+ profile/rule context validado
→ Decision
```

ComplianceStatus:
`compliant | non_compliant | unknown | not_applicable | not_evaluated`

Actionability:
`no_action | deterministic_change | human_choice | review | preserve`

Invariante:

```text
desired_value != None
IFF
actionability == deterministic_change
```

Slice executável:

```text
P1/run/bold
P2/run/font_size
P3/paragraph/spacing.line
P4/paragraph/alignment
```

## Classification Layer v0.1 — 0022 + freeze 0023

Pipeline:

```text
PhysicalIR + StyleCatalog
→ Analysis pública determinística
→ ClassificationResult
→ TargetClassification elegível
→ Decision Layer
```

Escopo executável:
`body | heading`.

`long_quote` e `reference` existem no vocabulário, mas ainda não executáveis.

Regras principais:
- body nunca fallback residual;
- `Normal → body`;
- `Heading1..Heading9 → heading level N`;
- style name sozinho não classifica;
- basedOn só atravessa tipos compatíveis;
- empty/tables/containers/numbering unsupported → abstain;
- secondary stories → not_applicable;
- runs herdam classe apenas do parágrafo físico real.

## OperationPlan v0.1 — 0024 + freeze 0025

Pipeline:

```text
Decision
→ PlanningResult
→ OperationPlan
→ SafetyGate
```

Princípio:

**OperationPlan propõe; SafetyGate veta ou libera; patcher executa.**

PlanningStatus:
`planned | skipped | unsupported`.

OperationKind v0.1:
`SET_PROPERTY`.

Cada operação preserva:
- DecisionKey;
- target físico/classificado;
- `physical_hash`;
- `precondition_observed`;
- `desired_value`;
- `decision_ref`.

Stale/drift anchors:
1. `package_sha256`;
2. `physical_hash`;
3. `precondition_observed`.

Refs:
- `decision_ref = sha256(serialize_decision(decision))`;
- `source_decisions_hash` canônico/order-independent;
- `operation_ref` e `operation_plan_ref` públicos e canônicos após PR #8.

Determinismo:
- operations e planning_results canonizados;
- caller order não altera bytes;
- duplicates/conflicts falham, nunca deduplicam silenciosamente.

## SafetyGate v0.1 — 0026 + freeze 0027

Pipeline congelado real:

```text
DOCX
→ Parser
→ Analysis
→ Classification
→ Decision
→ OperationPlan
→ SafetyGate
```

API conceitual:

```text
OperationPlan
+ source Decisions
+ current PhysicalIR
+ current StyleCatalog
+ active ProfileRef
→ SafetyGateReport
```

### Fronteira

SafetyGate é **veto final**, nunca nova autorização normativa.

Não:
- escolhe desired;
- redecide compliance;
- reclassifica;
- gera XML;
- aplica patch;
- modifica DOCX;
- usa raw OOXML para resolver precondition;
- usa LLM/heurística/score.

### Integridade fail-fast

Antes de observar o documento:
- source_decisions_hash;
- duplicate source Decision;
- decision_ref resolution;
- operation↔Decision binding;
- deterministic_change + rule_ref;
- versions/kind/story part;
- PhysicalIR↔StyleCatalog binding.

Integridade inválida = exception, nunca `blocked`.

### Binding PhysicalIR ↔ StyleCatalog

Revalida `StyleCatalog.part_sha256` contra o sha do `word/styles.xml` no inventário da PhysicalIR atual, com part status compatível.

PhysicalIR A + StyleCatalog B → integrity error.

### Global context vetoes

`ContextStatus = compatible | blocked`.

Ordem canônica:

```text
package
→ parser
→ analysis
→ classification
→ profile
```

Reasons:
- `source_document_changed`;
- `parser_version_mismatch`;
- `analysis_version_mismatch`;
- `classification_version_mismatch`;
- `profile_context_changed`.

Global mismatch bloqueia todas as operações e impede checks locais.

### Local vetoes

`GateStatus = cleared | blocked`.

Reasons:
- `target_not_found`;
- `target_not_unique`;
- `target_type_mismatch`;
- `physical_hash_mismatch`;
- `current_value_unavailable`;
- `precondition_mismatch`.

Gate localiza target na story principal, exige unicidade/tipo/hash e só então reobserva semanticamente pela Analysis pública.

Para run, paragraph ancestor vem da árvore física real, inclusive sob `run_container`; nunca por prefixo textual.

### Compare-and-set runtime

```text
current_semantic_value == precondition_observed
```

é obrigatório para `cleared`.

`current == desired`, mas diferente da precondition → `precondition_mismatch`.

Gate nunca replaneja nem converte stale em no_action.

### Value typing

- bold → bool;
- font_size → `Length(pt) ↔ LengthValue(pt)`;
- spacing.line → `(rule,value,unit)`;
- alignment → token canônico.

Sem half-points/twips/XML no gate.

### Partial clearance

Contexto compatible pode ter results mistos. Falha local não derruba operações independentes.

### GateClearedOperation

Token congelado para o futuro patcher:

```text
GateClearedOperation:
    operation
    operation_ref
    operation_plan_ref
    current_package_sha256
```

Invariante adversarialmente reforçada:

```text
operation_ref == operation_ref(operation)
```

`_EMISSION_PROOF` só evita bypass acidental pela API pública; não é capability security absoluta em Python.

`gate_operation(...)` é diagnóstico/unit-level e não emite token executável.

### SafetyGateReport

Frozen e serializável.

Coerência cruzada obrigatória:
- compatible → blocked results usam apenas reasons locais;
- blocked → todos os results blocked pelo reason global do contexto;
- zero cleared tokens em contexto blocked;
- `cleared_operations` corresponde exatamente aos results cleared;
- tokens compartilham plan ref e snapshot sha do report.

### TOCTOU

Todo token carrega `current_package_sha256`.

Future patcher deve operar sobre o mesmo snapshot gateado e verificar:

```text
sha256(snapshot bytes) == token.current_package_sha256
```

ou consumir diretamente o OriginalPackage imutável que originou IR/StyleCatalog.

Nunca gatear A e aplicar silenciosamente em B.

### Auditoria PR #8

Achados corrigidos antes do freeze:
1. **BLOQUEADOR:** token não vinculava `operation_ref` à operação embutida;
2. **IMPORTANTE:** report aceitava combinações incoerentes de global/local reason;
3. **IMPORTANTE:** `SafetyGateReport` não estava exportado;
4. **MENOR:** wording de `_EMISSION_PROOF` forte demais;
5. **MENOR:** `gate_operation` precisava ser explicitamente diagnóstico.

Head final auditado/hardened: `a867af747875b3e88047d80844f7eaa2df78db30`.

Squash: `d47b8e67d2788eb1912ef951ec7dcedb457376cb`.

### Flake conhecido do harness

O head final descobre 442 testes. Em 12 rodadas:
- 11: 442/442;
- 1: 441/442 em `test_hashseed_determinism`.

Diagnóstico confirmado no código: o helper sintético `build_docx` usa `zipfile.writestr` sem `ZipInfo.date_time` fixo. Subprocessos que cruzam boundary temporal podem produzir ZIPs byte-diferentes e `package_sha256` diferente. Isso não é comportamento do produto/SafetyGate.

Registrar como dívida de infraestrutura de teste; não alterar contratos de produto para acomodar o flake.

## Dívidas registradas, não bloqueadoras

- estabilizar timestamp do helper sintético `build_docx`;
- analysis/classification versions ainda são assertions do orchestrator;
- possível pipeline-context hash;
- equivalência semântica de DOCX reempacotado byte-diferente;
- profile content hash; enquanto não existir, mudança substantiva exige bump de `profile_version`;
- long_quote/reference executáveis;
- story_id/part/original_index para stories secundárias;
- ordem documental para futuras operações estruturais;
- TransformLog;
- envelope completo snapshot→patch.

## Fora do próximo ciclo

Até contrato específico:
- TransformLog;
- DOCX review/highlight;
- structural MOVE/INSERT/MERGE;
- secondary-story execution;
- UI/API web.

## Próximo passo operacional

**Patcher/applicator v0.1 — contrato primeiro.**

Objetivo do próximo elo:

```text
OriginalPackage snapshot
+ GateClearedOperation
→ minimal OOXML mutation on a copy
→ modified DOCX bytes
```

Restrições já herdadas:
- patcher aceita somente `GateClearedOperation`, nunca `PlannedOperation` crua;
- revalida snapshot sha antes de mutar;
- altera somente o subaspecto autorizado;
- não reconstrói DOCX a partir da IR;
- preserva o OriginalPackage;
- conversões OOXML (half-points/twips etc.) só entram aqui, com contrato explícito;
- primeiro vertical slice deve alterar bold/font_size com patch mínimo e provar preservação do restante.
