# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; parser físico v0.4 congelado; Analysis View v0.1a/v0.1b congeladas; Decision Vocabulary v0.1 congelado; Decision Layer v0.1 congelada em 0021; Classification Layer v0.1 congelada em 0023; OperationPlan v0.1 congelado em 0025; SafetyGate v0.1 congelado em 0027; **Patcher/Applicator v0.1 implementado, auditado, mergeado e congelado em 0029**.

Validação corrente:
- parser v0.4: **102/102**;
- Analysis completa: **267/267**;
- após Decision Layer v0.1: **290/290**;
- após Classification Layer v0.1: **335/335**;
- após OperationPlan v0.1: **389/389**;
- após SafetyGate v0.1: **442 testes descobertos**;
- após Patcher v0.1: **502/502 OK**;
- suíte final repetida **3×**, resultados idênticos;
- failures: 0;
- errors: 0;
- skips: 0.

PRs/freeze principais:
- PR #3 — Analysis v0.1b Marco 1; freeze 0017;
- PR #4 — Analysis v0.1b Marco 2; freeze 0018;
- PR #5 — Decision Layer v0.1; squash `b81f628a0358cbc9483e9207d4f749ea4a2ca475`; freeze 0021;
- PR #6 — Classification Layer v0.1; squash `736c33036224562549b1b5cb026bd6bfdfd2e112`; freeze 0023;
- PR #7 — OperationPlan v0.1; head auditado `871e4a5cc379bbb2b2e04504a871188366718092`; squash `1c11d08dcd6fc219bb2f4e0ce5321db027a5801a`; freeze 0025;
- PR #8 — SafetyGate v0.1; head final auditado/hardened `a867af747875b3e88047d80844f7eaa2df78db30`; squash `d47b8e67d2788eb1912ef951ec7dcedb457376cb`; freeze 0027;
- PR #9 — Patcher v0.1; head final auditado/hardened `2d8b9c48a0831a361dc8a152e6a1a876b2318a56`; squash `559cf8ec812320d066e8b91d431873f7a91f2c1c`; freeze 0029.

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

### Uso de modelos / custo

Kimi K3 passou a ser recurso caro por créditos extras. Usar apenas quando houver ganho técnico claro, principalmente para implementação pesada ou execução de suíte quando o ambiente local do ChatGPT não conseguir rodar. Preferir ChatGPT para contrato, arquitetura, integração, auditoria estática e GitHub; Claude Opus para auditoria adversarial de alto risco; Kimi só quando estritamente necessário.

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
- OriginalPackage/snapshot de entrada nunca é mutado in-place.

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

Após 0029 existe API pública aditiva de helpers físicos para downstream:
- `canonical_xml`;
- `inherited_xml_attrs`;
- `physical_hash`;
- `structural_path`;
- `resolve_structural_path`.

`structural_path` não é XPath. Resolver dedicado suporta QName real, índices 1-based e namespace URI contendo `/`.

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

`desired_value != None` iff `actionability == deterministic_change`.

Slice executivo upstream continua:
- P1/run/bold;
- P2/run/font_size;
- P3/paragraph/spacing.line;
- P4/paragraph/alignment.

## Classification Layer v0.1 — 0022 + freeze 0023

Pipeline:

```text
PhysicalIR + StyleCatalog
→ Analysis pública determinística
→ ClassificationResult
→ TargetClassification elegível
→ Decision Layer
```

Escopo executável atual: `body | heading`.

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

Princípio:

**OperationPlan propõe; SafetyGate veta ou libera; Patcher executa.**

OperationKind v0.1: `SET_PROPERTY`.

Cada operação preserva target físico/classificado, physical_hash, precondition_observed, desired_value e decision_ref.

Stale/drift anchors:
1. package_sha256;
2. physical_hash;
3. precondition_observed.

## SafetyGate v0.1 — 0026 + freeze 0027

Pipeline:

```text
DOCX
→ Parser
→ Analysis
→ Classification
→ Decision
→ OperationPlan
→ SafetyGate
```

SafetyGate é veto final, nunca nova autorização normativa.

Global context reasons:
- source_document_changed;
- parser_version_mismatch;
- analysis_version_mismatch;
- classification_version_mismatch;
- profile_context_changed.

Local reasons:
- target_not_found;
- target_not_unique;
- target_type_mismatch;
- physical_hash_mismatch;
- current_value_unavailable;
- precondition_mismatch.

`GateClearedOperation` carrega operation, operation_ref, operation_plan_ref e current_package_sha256, com autocoerência de operation_ref.

## Patcher/Applicator v0.1 — contrato 0028 + freeze 0029

Pipeline real agora congelado:

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
→ patched DOCX bytes
```

### Fronteira pública

```text
apply_cleared_operation(
    package_snapshot: bytes,
    cleared_operation: GateClearedOperation,
) -> PatchResult
```

Não aceita PlannedOperation crua.

### Slice executável

Somente:

```text
P1/run/bold
P2/run/font_size
```

Uma operação por chamada.

### Snapshot / integrity

Antes de abrir XML:

```text
sha256(package_snapshot)
==
cleared_operation.current_package_sha256
```

Mismatch → ordinary rejection `snapshot_hash_mismatch`.

Depois de snapshot match, path/type/physical_hash drift → `PatcherIntegrityError`.

Token não é tratado como capability security; patcher revalida suas próprias precondições.

### OOXML mutation

- somente `word/document.xml`;
- lxml/ElementTree;
- DTD/DOCTYPE rejeitado;
- direct children only para `w:rPr`/`w:b`/`w:sz`;
- `w:rPrChange` protegido;
- duplicate `w:rPr` ou shape não-canônico → reject;
- duplicate target property → reject;
- ordem CT_RPr congelada; inserir sem mover siblings;
- sem implicit normalization.

Bold:

```text
true  → <w:b/>
false → <w:b w:val="0"/>
```

Font size:

```text
half_points = Decimal(points) * 2
```

Exato, sem arredondamento, >0, <=3276 half-points.

`w:szCs` nunca é alterado no v0.1.

### Package/ZIP

Preserva entry set/order, metadata allowlist, archive/per-entry comments e payload byte-idêntico de todo part não alterado. Compresslevel fixo e sem clock.

O flake anterior de `build_docx` foi eliminado fixando metadata temporal no ZIP sintético.

### XML serialization hardened

Auditoria final corrigiu antes do merge:
- namespace URI com `/` no resolver físico;
- encoding físico real preservado, inclusive UTF-16;
- declaration + standalone preservados;
- UTF-16 sem declaration continua sem declaration;
- prolog/epilog comments/PIs preservados.

### Allowed-delta + postcondition

`applied` só existe depois de:
- reabrir os bytes produzidos;
- provar que o único delta semântico OOXML é a propriedade autorizada + wrapper necessário;
- validar package scope;
- Parser → StyleCatalog → Analysis no output;
- provar `current == desired`.

Delta extra/postcondition divergente → integrity error.

### PatchResult

Frozen. Para applied:

```text
output_package_sha256 == sha256(output_package_bytes)
```

é invariante obrigatória.

### Single-operation limitation

Após patch, package/physical hashes mudam. Outros tokens do mesmo report ficam stale. Não iterar `cleared_operations` em sequência sem reexecutar pipeline/gate.

### Testes finais

Head final: `2d8b9c48a0831a361dc8a152e6a1a876b2318a56`.

Squash: `559cf8ec812320d066e8b91d431873f7a91f2c1c`.

Suite: **502/502 OK**, 3 rodadas idênticas, 0 failures/errors/skips.

## Dívidas registradas

### Não bloqueadoras para o próximo ciclo
- analysis/classification versions ainda são assertions do orchestrator;
- possível pipeline-context hash;
- equivalência semântica de DOCX reempacotado byte-diferente;
- profile content hash;
- long_quote/reference executáveis;
- story_id/part/original_index para stories secundárias;
- ordem documental para futuras operações estruturais;
- multi-operation transaction;
- styles.xml patching;
- secondary-story execution;
- spacing/alignment patching;
- TransformLog;
- clean/review/report orchestration.

### Dívida importante antes de uso amplo em documentos reais

`w:szCs` não é modelado/mutado no slice font_size. O sistema NÃO deve prometer correção visual completa de complex-script enquanto esse subaspecto não tiver contrato próprio. `w:szCs` deve permanecer intacto no v0.1.

## Próximo passo operacional

**TransformLog / Execution Record — contrato primeiro.**

Agora já conseguimos produzir um DOCX modificado com segurança para uma operação. O próximo elo deve registrar de forma determinística e auditável o que aconteceu entre snapshot de entrada, token liberado e snapshot de saída, sem ampliar ainda o escopo de mutação.

Objetivo conceitual:

```text
GateClearedOperation
+ PatchResult applied
→ TransformLogEntry
```

Ainda não implementar clean/review/report nem transação multi-operação antes do contrato dessa trilha de execução.