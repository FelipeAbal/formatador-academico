# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; parser físico v0.4 congelado; Analysis View v0.1a/v0.1b congeladas; Decision Vocabulary v0.1 congelado; Decision Layer v0.1 congelada em 0021; Classification Layer v0.1 congelada em 0023; OperationPlan v0.1 congelado em 0025; SafetyGate v0.1 congelado em 0027; Patcher/Applicator v0.1 congelado em 0029; **TransformLog / Execution Record v0.1 implementado, auditado, mergeado e congelado em 0031**.

Validação corrente:
- parser v0.4: **102/102**;
- Analysis completa: **267/267**;
- Decision Layer v0.1: **290/290**;
- Classification Layer v0.1: **335/335**;
- OperationPlan v0.1: **389/389**;
- SafetyGate v0.1: **442 testes descobertos**;
- Patcher v0.1: **502/502 OK**;
- TransformLog v0.1: **524/524 OK**;
- suíte final completa repetida **3×**, resultados idênticos;
- TransformLog específico: **21/21 OK**;
- failures: 0;
- errors: 0;
- skips: 0.

PRs/freeze principais:
- PR #3 — Analysis v0.1b Marco 1; freeze 0017;
- PR #4 — Analysis v0.1b Marco 2; freeze 0018;
- PR #5 — Decision Layer v0.1; squash `b81f628a0358cbc9483e9207d4f749ea4a2ca475`; freeze 0021;
- PR #6 — Classification Layer v0.1; squash `736c33036224562549b1b5cb026bd6bfdfd2e112`; freeze 0023;
- PR #7 — OperationPlan v0.1; squash `1c11d08dcd6fc219bb2f4e0ce5321db027a5801a`; freeze 0025;
- PR #8 — SafetyGate v0.1; squash `d47b8e67d2788eb1912ef951ec7dcedb457376cb`; freeze 0027;
- PR #9 — Patcher v0.1; head final `2d8b9c48a0831a361dc8a152e6a1a876b2318a56`; squash `559cf8ec812320d066e8b91d431873f7a91f2c1c`; freeze 0029;
- PR #10 — TransformLog v0.1; head final `d0a5d94e0c7345baeb5012860773bce6027aa245`; squash `eff4770f2f5ec848d0f5d6b9afb6b2cdfdc8e355`; freeze 0031.

Este é o HANDOFF corrente. O histórico fica no Git; não criar `handoff_vNN`.

## Regra operacional

**Tudo o que puder ser corrigido com segurança dentro do escopo atual deve ser corrigido antes de avançar.**

Só postergar quando houver expansão explícita de escopo, dependência não resolvida, impossibilidade técnica demonstrada, contradição normativa/arquitetural nova ou novo risco de segurança.

Fluxo formal:
1. ChatGPT propõe;
2. modelo apropriado audita quando necessário;
3. ChatGPT integra;
4. Felipe aprova quando necessário;
5. HANDOFF + decisão/commit.

### Uso de modelos / custo

Kimi K3 é recurso caro por créditos extras. Usar apenas quando houver ganho técnico claro, principalmente implementação pesada ou execução de suíte quando o ambiente do ChatGPT não conseguir rodar. Preferir ChatGPT para contrato, arquitetura, integração, auditoria estática e GitHub; Claude Opus para auditoria adversarial de alto risco; Kimi só quando estritamente necessário.

Para Kimi:
- novo chat por etapa técnica grande;
- começar com HANDOFF + SHA exato do `main` + tarefa fechada;
- GitHub remoto é fonte de verdade;
- implementação só conta com branch/commit/PR real ou diff completo;
- nunca confiar em claim de testes/PR sem inspeção independente.

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
- stale plan/document drift detectado antes de patch;
- patcher só executa GateClearedOperation;
- snapshot hash e target physical_hash são revalidados antes da mutação;
- mutação mínima + allowed-delta + postcondition Analysis obrigatórios;
- OriginalPackage/snapshot de entrada nunca é mutado in-place;
- TransformRecord só existe para patch efetivamente `APPLIED` e é proveniência, nunca autorização.

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

API pública aditiva de helpers físicos após 0029:
- `canonical_xml`;
- `inherited_xml_attrs`;
- `physical_hash`;
- `structural_path`;
- `resolve_structural_path`.

`structural_path` não é XPath; resolver dedicado suporta QName real, índice 1-based e namespace URI contendo `/`.

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

```text
Analysis View
+ TargetClassification
+ profile/rule context validado
→ Decision
```

`desired_value != None` iff `actionability == deterministic_change`.

Slice executivo upstream:
- P1/run/bold;
- P2/run/font_size;
- P3/paragraph/spacing.line;
- P4/paragraph/alignment.

Decision guarda `ProfileRef`, `RuleRef`, target, observed e desired. Para `font_size`, Decision usa `Decimal` em pontos.

## Classification Layer v0.1 — 0022 + freeze 0023

```text
PhysicalIR + StyleCatalog
→ Analysis determinística
→ ClassificationResult
→ TargetClassification elegível
→ Decision Layer
```

Escopo executável atual: `body | heading`.

`long_quote` e `reference` existem no vocabulário, mas ainda não executáveis.

Body nunca é fallback residual. `Normal → body`; `Heading1..Heading9 → heading level N`; runs herdam classe apenas do parágrafo físico real. Secondary stories continuam `not_applicable` para execução.

## OperationPlan v0.1 — 0024 + freeze 0025

Princípio: **OperationPlan propõe; SafetyGate veta/libera; Patcher executa.**

OperationKind v0.1: `SET_PROPERTY`.

Cada operação preserva target físico/classificado, physical_hash, precondition_observed, desired_value e decision_ref.

Para `font_size`, o planner converte deliberadamente:

```text
Decision Decimal(pt)
→ LengthValue(Decimal, unit="pt")
```

Stale/drift anchors:
1. package_sha256;
2. physical_hash;
3. precondition_observed.

## SafetyGate v0.1 — 0026 + freeze 0027

SafetyGate é veto final, nunca nova autorização normativa.

`GateClearedOperation` carrega:
- operation;
- operation_ref;
- operation_plan_ref;
- current_package_sha256.

Global context reasons incluem source_document/parser/analysis/classification/profile drift. Local reasons incluem target/path/type/hash/current/precondition drift.

## Patcher/Applicator v0.1 — contrato 0028 + freeze 0029

Fronteira:

```text
apply_cleared_operation(
    package_snapshot: bytes,
    cleared_operation: GateClearedOperation,
) -> PatchResult
```

Slice executável:

```text
P1/run/bold
P2/run/font_size
```

Uma operação por chamada.

Regras congeladas principais:
- snapshot sha revalidado antes de abrir XML;
- path/type/physical_hash drift após snapshot match = integrity error;
- somente `word/document.xml` pode mudar;
- direct children only para `w:rPr`/`w:b`/`w:sz`;
- `w:rPrChange` protegido;
- ordem CT_RPr canônica;
- duplicate/noncanonical shapes rejeitados;
- bold true → `<w:b/>`;
- bold false → `<w:b w:val="0"/>`;
- font_size → half-points exatos, sem rounding;
- `w:szCs` permanece intacto;
- XML ElementTree preserva encoding/declaration/prolog/epilog;
- package ZIP preserva parts/ordem/metadata allowlist;
- allowed-delta + Parser→StyleCatalog→Analysis postcondition obrigatórios;
- PatchResult APPLIED vincula `output_package_sha256 == sha256(output_package_bytes)`.

Single-operation limitation: depois de um patch, demais tokens do mesmo report ficam stale. Reexecutar pipeline/gate para a próxima alteração.

## TransformLog / Execution Record v0.1 — contrato 0030 + freeze 0031

Pipeline real agora:

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

### Fronteira pública

```text
build_transform_record(
    cleared_operation: GateClearedOperation,
    patch_result: PatchResult,
    source_decision: Decision,
) -> TransformRecord
```

Não recebe DOCX/package bytes e não faz IO/XML/ZIP.

### Semântica applied-only

TransformRecord existe somente para patch `APPLIED`.

Blocked SafetyGate, rejected PatchResult e exceções não geram TransformRecord. Não existe status `rejected` no record.

### Cross-binding

Antes de construir, revalida:
- PatchResult operation_ref ↔ GateClearedOperation operation_ref;
- operation_plan_ref;
- input package SHA ↔ token snapshot;
- token operation_ref ↔ operação embutida;
- `sha256(serialize_decision(source_decision)) == operation.decision_ref`;
- target completo Decision ↔ OperationTarget;
- deterministic_change + RuleRef;
- ProfileRef ↔ RuleRef;
- rule aspect ↔ operation target;
- observed/desired equivalentes à projeção congelada do planner.

Para `font_size`, valida Decimal da Decision contra `LengthValue(pt)` da operação. Para bold, exige `bool` exato; `1/0` não substitui booleano.

### TransformRecord

Campos congelados:
- transform_log_version;
- patcher_version;
- operation_ref;
- operation_plan_ref;
- decision_ref;
- profile_ref;
- rule_ref;
- target;
- precondition_observed;
- desired_value;
- input_package_sha256;
- output_package_sha256;
- changed_part.

Não embute output bytes, token, PatchResult, Decision inteira, raw XML, timestamp, UUID ou hostname.

`ProfileRef` + `RuleRef` são copiados para permitir relatório futuro autocontido quanto à origem normativa.

### Target / localização

No slice property-only atual, `target.structural_path` permanece resolvível no output e serve de localização pré/pós quando interpretado contra os package hashes correspondentes.

Não há post-transform physical_hash no v0.1.

### Determinismo

```text
transform_ref(record)
=
sha256(serialize_transform_record(record))
```

Serialização canônica segue Decision/OperationPlan: UTF-8, sorted keys, compact, Decimal→string, sem clock/random/locale.

### One-record-per-patch

```text
1 APPLIED PatchResult
→ 1 TransformRecord
```

Ainda não há envelope de sessão/batch nem validador de cadeia multi-record.

### Validação final

Head PR #10: `d0a5d94e0c7345baeb5012860773bce6027aa245`.

Squash: `eff4770f2f5ec848d0f5d6b9afb6b2cdfdc8e355`.

- TransformLog específico: **21/21 OK**;
- suíte total: **524/524 OK**;
- 3 rodadas completas idênticas;
- 0 failures/errors/skips;
- E2E real até TransformRecord verde;
- Decimal → LengthValue(pt) verde.

## Dívidas registradas

### Não bloqueadoras imediatas
- analysis/classification versions ainda são assertions do orchestrator;
- possível pipeline-context hash;
- equivalência semântica de DOCX reempacotado byte-diferente;
- profile content hash;
- long_quote/reference executáveis;
- story_id/part/original_index para stories secundárias;
- ordem documental para futuras operações estruturais;
- multi-operation transaction;
- multi-record chain validator;
- processing/session envelope;
- styles.xml patching;
- secondary-story execution;
- spacing/alignment patching;
- rejected/blocked event ledger;
- exception telemetry;
- clean/review/report orchestration.

### Dívida importante antes de uso amplo em documentos reais

`w:szCs` não é modelado/mutado no slice font_size. O sistema NÃO deve prometer correção visual completa de complex-script enquanto esse subaspecto não tiver contrato próprio. `w:szCs` permanece intacto no v0.1.

## Próximo passo operacional

**Processing Session / Orchestration v0.1 — contrato primeiro.**

Agora existe um pipeline real capaz de executar uma alteração segura e gerar proveniência forense da transformação. O próximo problema é orquestrar um documento inteiro com várias Decisions sem violar a limitação single-operation/stale-token do Patcher.

Objetivo conceitual do próximo ciclo:

```text
input DOCX snapshot
+ validated profile/rules
→ repeated fresh pipeline per safe applied mutation
→ final clean DOCX snapshot
+ ordered tuple[TransformRecord, ...]
+ complete outcome ledger/session result
```

A sessão deve definir explicitamente:
- ordem real de aplicação;
- re-run de Parser→...→SafetyGate entre mutações;
- cadeia input/output package hashes;
- parada segura em rejected/integrity failure;
- separação entre applied TransformRecords e blocked/review/rejected outcomes;
- como produzir um resultado de processamento autocontido para alimentar depois DOCX de revisão + relatório.

Ainda NÃO implementar DOCX review/highlight nem relatório user-facing antes de congelar esta orquestração.
