# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; parser físico v0.4 congelado; Analysis View v0.1a/v0.1b congeladas; Decision Vocabulary v0.1 congelado; Decision Layer v0.1 congelada em 0021; Classification Layer v0.1 congelada em 0023; OperationPlan v0.1 congelado em 0025; **SafetyGate v0.1 contratado e aprovado para implementação em 0026.**

Validação corrente:
- parser v0.4: **102/102**;
- parser + Analysis v0.1a: **154/154**;
- Analysis até v0.1b Marco 1: **222/222**;
- Analysis completa: **267/267**;
- após Decision Layer v0.1: **290/290**;
- após Classification Layer v0.1: **335/335**;
- após OperationPlan v0.1: **389/389**;
- failures: 0;
- errors: 0;
- skips: 0.

PRs/freeze principais:
- PR #3 — Analysis v0.1b Marco 1; freeze 0017;
- PR #4 — Analysis v0.1b Marco 2; freeze 0018;
- PR #5 — Decision Layer v0.1; head auditado `c340d1ab2c94b7c4af802419d0e414c4019be246`; squash `b81f628a0358cbc9483e9207d4f749ea4a2ca475`; freeze 0021;
- PR #6 — Classification Layer v0.1; head final auditado `94fb797fec1f44508274ec47ba87409da8e4537d`; squash `736c33036224562549b1b5cb026bd6bfdfd2e112`; freeze 0023;
- PR #7 — OperationPlan v0.1; head final auditado `871e4a5cc379bbb2b2e04504a871188366718092`; squash `1c11d08dcd6fc219bb2f4e0ce5321db027a5801a`; freeze 0025.

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
- sempre começar com HANDOFF + SHA exato do `main` + tarefa fechada;
- implementação só conta com branch/commit/PR real ou diff completo;
- GitHub remoto é fonte de verdade;
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
- classificação errada é risco upstream: **precision > coverage**;
- abstention correta é sucesso seguro;
- plano antigo/documento alterado deve ser detectável antes de qualquer patch;
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
- stories secundárias, parse parcial, tabelas, nested tables e block containers;
- parser v0.4.0;
- PhysicalIR inclui `package.sha256` do DOCX e sha256 por part;
- `physical_hash` por alvo protege identidade física local;
- suíte: **102/102**.

## Analysis View v0.1a — 0013–0014

Congelada:
- segmentos físicos autoritativos;
- `default_text` derivado;
- offsets em code points Python;
- não-participantes zero-width;
- opacos preservados;
- serialização determinística;
- sem live lxml;
- PhysicalIR imutável.

## Analysis View v0.1b — 0015–0018

Congelada:
- run: `w:sz`, `w:rFonts` 8 slots, `w:lang` 3 slots, `w:u`, `w:vertAlign`, `w:b`, `w:i`;
- paragraph: `pStyle`, `w:jc`, `w:spacing`, `w:ind`;
- toggle semantics correta em styles;
- defaults/style chains conforme 0016–0018;
- tudo ausente => `absent`, nunca false;
- duplicates/cycles/evidence conforme contrato.

Suíte Analysis completa: **267/267**.

## Decision Vocabulary v0.1 — 0019

`decision_vocabulary_version = "0.1"`

```text
P1 / run / bold
P1 / run / italic
P2 / run / font_size
P3 / paragraph / spacing.line
P4 / paragraph / alignment
```

DecisionKey = `(target_type, aspect_id, property_slot)`.

## Decision Layer v0.1 — 0020 + freeze 0021

Pipeline:

```text
Analysis View
+ TargetClassification
+ profile/rule context validado
-> Decision
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

Slice executável congelado:

```text
P1/run/bold
P2/run/font_size
P3/paragraph/spacing.line
P4/paragraph/alignment
```

Suíte após Decision: **290/290**.

## Classification Layer v0.1 — 0022 + freeze 0023

Pipeline congelado:

```text
PhysicalIR + StyleCatalog
-> Analysis pública determinística
-> ClassificationResult
-> TargetClassification elegível
-> Decision Layer
```

Escopo executável:

```text
body
heading
abstain / not_applicable
```

Vocabulário também contém `long_quote` e `reference`, ainda não executáveis.

Regras congeladas principais:
- `unknown` não é target_class;
- body nunca é fallback residual;
- style map v0.1: `Normal -> body`, `Heading1..Heading9 -> heading level N`;
- `BodyText` ficou fora por falta de evidência real suficiente;
- style name sozinho nunca classifica;
- custom style pode herdar via `basedOn` válida;
- wrong-type hop/cycle/dangling não classificam;
- empty -> abstain;
- tables/containers/list-numbering -> abstain;
- secondary stories -> not_applicable;
- run herda classe apenas do seu parágrafo físico real.

Auditoria PR #6 corrigiu antes do freeze:
1. parent/run binding ausente;
2. basedOn atravessando style-type boundary.

Suíte final Classification: **335/335**.

## OperationPlan v0.1 — contrato 0024 + freeze 0025

Pipeline congelado:

```text
Decision
-> PlanningResult
-> OperationPlan
-> SafetyGate
-> future XML patch
```

Princípio:

**OperationPlan propõe; SafetyGate veta ou libera; patcher executa.**

Planner é puro/determinístico e não toca XML/DOCX.

PlanningStatus:
`planned | skipped | unsupported`

OperationKind v0.1:
`SET_PROPERTY`

Slice executável:

```text
P1/run/bold
P2/run/font_size
P3/paragraph/spacing.line
P4/paragraph/alignment
```

Compare-and-set semântico obrigatório:
- `precondition_observed`;
- `desired_value`;
- `precondition != desired`;
- `rule_ref != None` para deterministic_change.

Stale/drift anchors:
1. `package_sha256`;
2. target `physical_hash`;
3. semantic `precondition_observed`.

`decision_ref = sha256(serialize_decision(decision))`.

`source_decisions_hash` é canônico e order-independent.

Agregação:
- duplicata idêntica -> erro;
- mesma identidade física+key com same before/after -> duplicate operation error;
- mesma identidade física+key com before/after divergente -> conflict error;
- `target_class` não participa da identidade física de conflito;
- operations e planning_results canonizados;
- same logical input -> same bytes;
- empty plan válido.

Suíte final OperationPlan: **389/389**.

## SafetyGate v0.1 — contrato 0026

Status: **APPROVED FOR IMPLEMENTATION**.

Pipeline:

```text
OperationPlan
+ source Decisions
+ current PhysicalIR
+ current StyleCatalog
+ active ProfileRef
-> SafetyGateReport
-> future patcher
```

Princípio:

**SafetyGate é veto final de segurança, nunca nova autorização normativa.**

### Inputs/runtime binding

Gate recebe:
- OperationPlan congelado;
- tuple completa de source Decisions;
- PhysicalIR atual recém-derivada do snapshot que seria mutado;
- StyleCatalog atual derivado dos MESMOS bytes;
- active ProfileRef.

Não recebe AnalysisViews prontas. Reobserva semanticamente via APIs públicas da Analysis.

### Plan/source integrity — exception/fail-fast

Antes de gatear:
- recomputar e validar `source_decisions_hash`;
- resolver cada operation `decision_ref` em exatamente uma Decision;
- rejeitar duplicata de Decision serializada;
- validar operation↔Decision target/key;
- validar operation precondition↔Decision observed;
- validar desired↔Decision desired;
- exigir `deterministic_change` e `rule_ref != None`;
- validar versions/kind/story part compatíveis.

Isso é integridade/provenance, não re-decisão.

### Profile

`active_profile_ref` é obrigatório.

Mismatch profile_id/profile_version -> GLOBAL block `profile_context_changed`.

Contrato: alteração substantiva de profile exige nova `profile_version` enquanto não houver fingerprint de conteúdo.

### Binding PhysicalIR ↔ StyleCatalog

Não exige reabrir upstream.

Gate revalida:

```text
StyleCatalog.part_sha256
==
sha do part word/styles.xml no inventário da PhysicalIR atual
```

+ status esperado do part.

PhysicalIR A + StyleCatalog B -> integrity/binding exception.

### Global context vetoes

`ContextStatus = compatible | blocked`.

Reasons globais v0.1:
- `source_document_changed`;
- `parser_version_mismatch`;
- `analysis_version_mismatch`;
- `classification_version_mismatch`;
- `profile_context_changed`.

Package mismatch é sempre global no v0.1, mesmo se target hash coincidir.

Parser mismatch é global porque paths/hashes dependem do parser.

Analysis mismatch é global porque Gate usa Analysis atual para a precondition.

Classification mismatch é global/conservador porque `target_class` foi produzido sob aquela versão.

### Local target/precondition vetoes

`GateStatus = cleared | blocked`.

Reasons locais v0.1:
- `target_not_found`;
- `target_not_unique`;
- `target_type_mismatch`;
- `physical_hash_mismatch`;
- `current_value_unavailable`;
- `precondition_mismatch`.

Gate localiza target no body story de `word/document.xml`, exige match único e valida target type/hash.

Para run, parent paragraph vem da árvore física real, nunca de prefixo textual do path.

Current semantic state é derivado via Analysis + StyleCatalog bound.

Não-resolved Analysis -> `current_value_unavailable`.

`current != precondition` -> `precondition_mismatch`, inclusive quando current já é desired. Gate nunca converte stale operation em no_action.

### Typed semantic comparison

- bold: bool;
- font size: Analysis Length ↔ OperationPlan LengthValue por `(value, unit)`;
- spacing.line: Analysis LineSpacing ↔ Decision/Plan LineSpacingValue por `(rule,value,unit)`, ignorando raw forensic fields;
- alignment: canonical token.

Sem half-points/twips/raw OOXML.

### Partial clearance

Contexto global compatível permite resultados mistos:
- operação A cleared;
- operação B blocked.

Falha local não derruba operações independentes.

Global block impede todas as operações e cada operação recebe GateResult blocked para trilha completa.

### Result/report models

`SAFETY_GATE_VERSION = "0.1"`.

Sem versão separada para reason vocabulary no v0.1.

Modelos-alvo frozen:

```text
GateResult:
    operation_ref
    status
    reasons
    evidence

SafetyGateReport:
    safety_gate_version
    operation_plan_ref
    current_package_sha256
    context_status
    context_reasons
    results
    cleared_operations
```

Reason e evidence são separados. Evidence carrega somente fatos expected/actual necessários ao relatório técnico.

### Deterministic refs

```text
operation_plan_ref = sha256(serialize_operation_plan(plan))
operation_ref = sha256(canonical serialize PlannedOperation)
```

OperationPlan deve expor helpers públicos canônicos aditivos; não duplicar serialização privada.

### GateClearedOperation — fronteira obrigatória

```text
GateClearedOperation:
    operation: PlannedOperation
    operation_ref
    operation_plan_ref
    current_package_sha256
```

A operação embutida permanece idêntica ao input.

`cleared` significa somente “nenhum veto acionado no estado observado”.

Future patcher deve aceitar **GateClearedOperation**, nunca PlannedOperation crua.

### TOCTOU/snapshot

Gate e patcher devem ficar ligados ao MESMO snapshot.

SafetyGateReport e GateClearedOperation carregam `current_package_sha256`.

Future patcher deve:
1. operar sobre o mesmo OriginalPackage/package snapshot usado para IR/StyleCatalog; OU
2. revalidar sha256 dos bytes imediatamente antes de mutar.

É proibido gatear um estado e reabrir silenciosamente outro arquivo/estado para aplicar.

### Error model

1. **exception/integrity error**: artifact/plan/source Decisions/binding inválidos, StyleCatalog↔IR mismatch, unexpected Analysis exception etc.;
2. **global blocked context**: plano válido, contexto global mudou;
3. **local blocked operation**: contexto global compatível, target/precondition local não prova segurança;
4. **cleared**: nenhum veto acionado para aquela operação.

Unexpected Analysis exception é fail-fast; status Analysis não-resolved é local block.

### Determinism

Modelos frozen; tuples; serialização canônica sem timestamp/random.

Same logical plan/source Decisions/current context/profile -> same report bytes independentemente da ordem do caller e hashseed.

### First vertical slice / tests requeridos

Primeiro E2E alvo:

```text
DOCX
-> Parser
-> Analysis
-> Classification
-> Decision
-> OperationPlan
-> SafetyGate
```

Documento unchanged:
- bold true→false -> cleared;
- font 11→12pt -> cleared;
- spacing/alignment continuam skipped upstream;
- context compatible;
- exatamente 2 GateClearedOperations.

A implementação deve cobrir também package/parser/analysis/classification/profile global vetoes; target/hash/Analysis/precondition local vetoes; partial clearance; source provenance integrity; PhysicalIR A + StyleCatalog B; run_container com parent paragraph real; empty plan; determinismo cross-order/hashseed; imutabilidade.

## Dívidas registradas, não bloqueadoras

Classification:
- long_quote executável;
- reference executável;
- ClassificationHints/localização de styles;
- outlineLvl factual;
- numeração estruturada;
- title/subtitle;
- short_quote/classes inline;
- corpus real anotado e métricas por classe.

OperationPlan/SafetyGate:
- analysis/classification versions ainda são orchestrator assertions, não provenance criptográfica;
- possível pipeline-context hash futuro;
- semantic equivalence para DOCX reempacotado byte-diferente;
- story_id/part/original_index ainda não propagados para execução secundária;
- ordem lexicográfica do plano não é ordem documental;
- full execution snapshot envelope ficará para o patcher, além do SHA já congelado;
- TransformLog ainda não implementado.

## Fora do próximo ciclo

Continuam fora até contrato específico:
- XML patch/applicator;
- TransformLog;
- DOCX clean/review;
- structural operations;
- secondary-story execution;
- UI/API web.

## Próximo passo operacional

**Implementar SafetyGate v0.1 conforme decisão 0026.**

Antes de implementação:
- novo chat Kimi K3;
- partir do SHA atual exato do main;
- branch própria;
- preservar os **389/389** testes congelados;
- abrir PR real;
- não mergear antes de auditoria adversarial.
