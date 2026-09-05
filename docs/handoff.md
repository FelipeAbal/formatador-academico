# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; parser físico v0.4 congelado; Analysis View v0.1a/v0.1b congeladas; Decision Vocabulary v0.1 congelado; Decision Layer v0.1 congelada em 0021; Classification Layer v0.1 congelada em 0023; **OperationPlan v0.1 implementado, auditado, mergeado e congelado em 0025**.

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
-> future SafetyGate
-> future XML patch
```

Princípio:

**OperationPlan propõe; SafetyGate veta ou libera; patcher executa.**

### Fronteira

Planner é puro e determinístico. NÃO:
- redecide conformidade;
- escolhe variante normativa;
- reclassifica alvo;
- reexecuta Analysis;
- abre DOCX;
- lê OOXML/lxml;
- gera/aplica patch;
- executa SafetyGate;
- usa IO/rede/LLM/clock/random/locale.

### API

```text
plan_decision(decision) -> PlanningResult
build_operation_plan(source_document, upstream_versions, decisions) -> OperationPlan
```

PlanningStatus:

```text
planned
skipped
unsupported
```

Somente `deterministic_change` em slot suportado produz operação.

`no_action | human_choice | review | preserve` -> `skipped`.

`deterministic_change` conhecido mas fora do planner slice -> `unsupported`.

### Operation vocabulary

```text
OPERATION_PLAN_VERSION = "0.1"
OPERATION_VOCABULARY_VERSION = "0.1"
OperationKind.SET_PROPERTY
```

Reutiliza `DecisionKey`.

Slice executável:

```text
P1/run/bold
P2/run/font_size
P3/paragraph/spacing.line
P4/paragraph/alignment
```

### Compare-and-set semântico

Cada PlannedOperation preserva:
- DecisionKey;
- target físico/classificado;
- `precondition_observed`;
- `desired_value`;
- `decision_ref`.

Invariantes:

```text
precondition_observed is not None
desired_value is not None
precondition_observed != desired_value
rule_ref != None para deterministic_change
```

Sem conversão OOXML no plano:
- bold -> bool;
- font_size -> `LengthValue(Decimal, "pt")`;
- spacing.line -> `LineSpacingValue` da Decision;
- alignment -> token canônico.

### Provenance e stale/drift anchors

SourceDocumentRef:

```text
package_sha256
parser_version
```

No slice v0.1:

```text
planned_story_part = "word/document.xml"
```

Cada operação preserva `physical_hash` 64-hex-lowercase e `target_class` não vazio.

Três níveis de futura proteção:
1. package_sha256;
2. target physical_hash;
3. semantic precondition_observed.

`decision_ref = sha256(serialize_decision(decision))`.

Envelope carrega `source_decisions_hash` order-independent sobre conjunto canônico de Decisions.

### Agregação e determinismo

- duplicated Decision idêntica -> aggregation error;
- mesma identidade física+key com mesmo before/after -> duplicate operation error;
- mesma identidade física+key com before/after divergente -> conflict error;
- `target_class` NÃO participa da identidade de conflito físico;
- operations e planning_results são canonizados;
- mesma entrada lógica em qualquer ordem do caller -> bytes idênticos;
- ordem lexicográfica do plano NÃO é ordem documental/aplicação;
- empty plan é válido;
- skipped/unsupported ficam preservados em planning_results;
- `len(operations)` é o mutation budget.

### Provenance de versões

Envelope registra:
- analysis_formatting_version;
- classification_version;
- decision_version;
- decision_vocabulary_version.

Decision version e vocabulary são vinculáveis às Decisions.

Analysis formatting version e classification version são, no v0.1, **assertions do orchestrator**, porque a Decision congelada não as serializa. SafetyGate futuro não pode tratá-las como prova criptograficamente vinculada sem mecanismo adicional de pipeline context.

### Auditoria PR #7

Achados corrigidos antes do freeze:
1. **BLOQUEADOR:** `planning_results` preservava ordem do caller e quebrava determinismo byte-a-byte do plano completo;
2. **BLOQUEADOR:** `target_class` participava da identidade de conflito, permitindo duas operações no mesmo slot físico sob classes divergentes;
3. **IMPORTANTE:** `physical_hash` aceitava string arbitrária;
4. **IMPORTANTE:** `target_class=""` era aceito;
5. **MENOR:** semântica de provenance de UpstreamVersions estava ambígua.

Todos corrigidos na mesma branch antes do merge.

### E2E congelado

```text
DOCX
-> Parser
-> Analysis
-> Classification
-> TargetClassification
-> Decision
-> OperationPlan
```

Sem target_class manual.

Resultado auditado:
- bold true -> false => planned SET_PROPERTY;
- font 11pt -> 12pt => planned SET_PROPERTY;
- spacing compliant => skipped;
- alignment compliant => skipped;
- exatamente 2 operações;
- package_sha256 real transportado.

Suíte final: **389/389**, com **335/335 regressões preservadas**.

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

OperationPlan:
- classification/analysis_formatting version ainda são assertions do orchestrator;
- possível pipeline-context hash futuro;
- story_id/part/original_index ainda não propagados até DecisionTarget para execução de stories secundárias;
- ordem lexicográfica do plano não é ordem documental.

## Fora do próximo ciclo

Continuam fora até contrato específico:
- TransformLog;
- XML patch/applicator;
- DOCX clean/review;
- half-points/twips;
- structural operations;
- secondary-story execution;
- UI/API web.

## Próximo passo operacional

**SafetyGate v0.1 — contrato primeiro.**

Objetivo do próximo elo:

```text
OperationPlan
+ estado atual revalidado
-> GateDecision por operação
```

O SafetyGate deve ser veto, nunca autorização. Deve revalidar ao menos:
1. source package fingerprint;
2. target physical_hash;
3. semantic precondition_observed;
4. operação/slot autorizado;
5. contexto necessário para impedir stale-plan, target drift e mutação fora do contrato.

Ainda sem aplicar XML durante a fase de contrato do SafetyGate.
