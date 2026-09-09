# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; Parser físico v0.4 congelado; Analysis v0.1a/v0.1b congeladas; Decision Vocabulary v0.1 congelado; Decision Layer v0.1 congelada em 0021; Classification Layer v0.1 congelada em 0023; OperationPlan v0.1 congelado em 0025; SafetyGate v0.1 congelado em 0027; Patcher/Applicator v0.1 congelado em 0029; TransformLog / Execution Record v0.1 congelado em 0031; Processing Session / Orchestration v0.1 congelado em 0033; **Processing Report v0.1 implementado, auditado, mergeado e congelado em 0035**.

Este é o HANDOFF corrente. O histórico fica no Git; não criar `handoff_vNN`.

## Validação corrente

- parser v0.4: **102/102**;
- Analysis completa: **267/267**;
- Decision Layer v0.1: **290/290**;
- Classification Layer v0.1: **335/335**;
- OperationPlan v0.1: **389/389**;
- SafetyGate v0.1: **442 testes descobertos** no freeze próprio;
- Patcher v0.1: **502/502 OK** no freeze próprio;
- TransformLog v0.1: **524/524 OK** no freeze próprio;
- Processing Session v0.1: **565/565 OK** no freeze próprio;
- Processing Report / suíte completa atual: **591/591 OK**;
- GitHub Actions verde no head final do PR #12 e no `main` pós-merge;
- failures: 0;
- errors: 0;
- skips: 0;
- CI é a execução padrão da suíte; não gastar Kimi apenas para testar.

## PRs / freezes principais

- PR #3 — Analysis v0.1b Marco 1; freeze 0017;
- PR #4 — Analysis v0.1b Marco 2; freeze 0018;
- PR #5 — Decision Layer v0.1; squash `b81f628a0358cbc9483e9207d4f749ea4a2ca475`; freeze 0021;
- PR #6 — Classification Layer v0.1; squash `736c33036224562549b1b5cb026bd6bfdfd2e112`; freeze 0023;
- PR #7 — OperationPlan v0.1; squash `1c11d08dcd6fc219bb2f4e0ce5321db027a5801a`; freeze 0025;
- PR #8 — SafetyGate v0.1; squash `d47b8e67d2788eb1912ef951ec7dcedb457376cb`; freeze 0027;
- PR #9 — Patcher v0.1; squash `559cf8ec812320d066e8b91d431873f7a91f2c1c`; freeze 0029;
- PR #10 — TransformLog v0.1; squash `eff4770f2f5ec848d0f5d6b9afb6b2cdfdc8e355`; freeze 0031;
- PR #11 — Processing Session v0.1; head final `20717d2b36f180644675bbc1720357de1e8aa2a6`; squash `17b0a37529012a0873c76f27c1072ce297240f5d`; freeze 0033;
- PR #12 — Processing Report v0.1; head final `28ffb60224509cce0bd7916ae39810a2c6397a81`; squash `3328b8f9eb8f582aa19c7ced9168561621f32bfb`; freeze 0035.

## Regra operacional

**Tudo o que puder ser corrigido com segurança dentro do escopo atual deve ser corrigido antes de avançar.**

Só postergar quando houver expansão explícita de escopo, dependência não resolvida, impossibilidade técnica demonstrada, contradição normativa/arquitetural nova ou novo risco de segurança.

Fluxo formal:
1. ChatGPT propõe;
2. modelo apropriado audita quando necessário;
3. ChatGPT integra;
4. Felipe aprova quando realmente necessário;
5. HANDOFF + decisão/commit.

### Uso de modelos / custo

- ChatGPT: integração, arquitetura, metodologia, auditoria estática, implementação quando viável, GitHub e HANDOFF.
- Claude Opus: auditoria adversarial de alto risco quando houver ganho real.
- Kimi K3: implementação pesada/auditoria especializada apenas quando ganho justificar custo.
- GitHub Actions: execução normal da suíte.

Kimi está pago por crédito extra; minimizar agressivamente.

## Objetivo do MVP

Formatar com segurança DOCX acadêmicos existentes a partir de perfil formal explicitamente declarado. Não promete conformidade ABNT genérica.

Saídas previstas:
1. DOCX limpo;
2. DOCX de revisão/highlight;
3. relatório de processamento.

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
- snapshot hash e target physical_hash revalidados antes da mutação;
- mutação mínima + allowed-delta + postcondition Analysis obrigatórios;
- OriginalPackage/snapshot nunca mutado in-place;
- TransformRecord só existe para patch APPLIED e é proveniência, nunca autorização;
- Processing Session nunca cria autoridade normativa nova nem reutiliza token stale;
- Processing Report é projeção read-only e nunca reanalisa/reclassifica/redecide.

## Pipeline real congelado

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
→ ProcessingSessionResult
→ ProcessingReport
```

## Slice automático atual

Somente:

```text
P1 / run / bold
P2 / run / font_size
```

Classes executáveis do ProcessingProfile v0.1:

```text
body
heading
```

Ainda fora do slice automático:
- P3 spacing patching;
- P4 alignment patching;
- italic patching;
- long_quote/reference execution;
- tables/containers/numbering execution;
- secondary-story execution;
- structural MOVE/INSERT/MERGE;
- styles.xml mutation.

## Processing Session / Orchestration v0.1 — 0032 + freeze 0033

API pública:

```text
process_document(
    package_snapshot: bytes,
    profile: ProcessingProfile,
    *,
    max_applied_operations: int = 10000,
) -> ProcessingSessionResult
```

### Perfil mínimo

```text
RuleBinding:
    target_class
    target_type
    rule: FormattingRule

ProcessingProfile:
    profile_ref: ProfileRef
    bindings: tuple[RuleBinding, ...]
```

Não é o schema final de perfil/UI.

### Ordem / rerun / status

- ordem física de parágrafos/runs;
- bindings em ordem canônica dentro do run;
- após cada APPLIED, todo o pipeline é reconstruído;
- tokens do gate anterior são descartados.

Status:

```text
quiescent
quiescent_with_unapplied
operation_limit_reached
```

`quiescent` significa apenas ausência de automação segura restante; não significa documento plenamente conforme.

### Resultado final

`ProcessingSessionResult` preserva:
- processing_session_version;
- status;
- profile_ref;
- input/output package SHA;
- output_package_bytes;
- transforms;
- final_classifications;
- final_decisions;
- findings.

Parser `partial` não é bypassado silenciosamente.

## Processing Report v0.1 — contrato 0034 + freeze 0035

Fronteira:

```text
build_processing_report(
    session_result: ProcessingSessionResult,
) -> ProcessingReport
```

É machine-readable e read-only. Não é ainda o renderer human-readable.

### Famílias de itens

```text
applied_changes
unapplied_changes
review_items
classification_items
```

#### AppliedChangeItem
Fonte exclusiva: TransformRecord. Um record → um item. Preserva transform_ref, decision_ref, operation_ref, profile/rule, target, observed_before, desired_applied e package hashes.

#### UnappliedChangeItem
Fonte: SessionFinding + final Decision ligada. Cobre gate_blocked, patch_rejected e operation_limit. Reason upstream não é reinterpretado.

#### ReviewItem
Fonte: final Decisions com `actionability in {review, human_choice}`. `no_action` e `preserve` não geram item.

#### ClassificationItem
Gerado para `abstained` ou qualquer ClassificationResult com warning. `not_applicable` puro não é individualizado para evitar ruído; permanece contabilizado no summary/StoryCoverage. Abstained + warning gera um único item.

### StoryCoverage

Por `story_id`, em ordem de primeira aparição:

```text
story_id
total_count
classified_count
abstained_count
not_applicable_count
warning_count
```

Sem julgamento/score.

### Summary

Inclui counts de applied/unapplied/review/classification, final Decisions/Classifications, classified/abstained/not_applicable, warnings, StoryCoverage e input/output SHA.

**Não calcula percentual de conformidade.**

### Serialização / identidade

`PROCESSING_REPORT_VERSION = "0.1"`.

```text
processing_report_ref(report)
=
sha256(serialize_processing_report(report))
```

JSON canônico UTF-8, keys ordenadas, Decimal→string, enums→value, tuples→arrays, LengthValue como `{value, unit}`. Bytes são rejeitados.

### Deliberações importantes

- ClassificationEvidence não é duplicada no v0.1; reasons/warnings/path bastam para os consumidores atuais e evidence permanece no SessionResult.
- target_class é preservado quando upstream possui.
- structural_path permite ao futuro DOCX de revisão localizar itens do slice atual sem nova Analysis.
- ProcessingReport não promete que todo ClassificationItem seja marcável no DOCX final; stories fora do slice podem existir apenas no relatório.
- runtime sem DOCX/ZIP/lxml/filesystem/network/clock/random/LLM.

### Validação

- CI final: **591/591 OK**;
- gate blocked → UnappliedChangeItem;
- Patcher rejection real por duplicate direct `w:b` → UnappliedChangeItem;
- operation limit → UnappliedChangeItem;
- review/human_choice → ReviewItem;
- no_action/preserve não inflam review;
- abstention/warnings corretamente projetados;
- StoryCoverage consistente;
- cross-hashseed determinism verde;
- todos regressions anteriores verdes.

## Corpus-base v1

- 41 fixtures;
- baseline motor nulo: 20/41 = 48,8%;
- precisão-alvo automática >=99%;
- alto risco desejado >=99,5%;
- tolerância zero a invenção/perda conhecida, dano a campo e alteração indevida de citação direta.

## Dívidas registradas

### Não bloqueadoras imediatas
- schema final de perfil/UI;
- heading-level rules;
- analysis/classification versions ainda como assertions do orchestrator;
- possível pipeline-context hash;
- profile content hash;
- equivalência semântica de DOCX reempacotado byte-diferente;
- P3/P4 patching;
- italic patching;
- long_quote/reference executáveis;
- story_id/part/original_index para stories secundárias;
- partial-story isolation;
- secondary-story execution;
- multi-operation transaction/rollback;
- persistence/resume;
- styles.xml patching;
- exception telemetry;
- performance optimization para muitos sequential patches;
- renderer human-readable do Processing Report;
- tradução/localização user-facing dos códigos;
- review/highlight DOCX;
- severity/ranking visual;
- paginação física;
- drill-down de ClassificationEvidence autocontida;
- user-facing grouping/dedup visual;
- UI/API final.

### Dívida importante antes de uso amplo

`w:szCs` não é modelado/mutado no slice font_size. O sistema NÃO deve prometer correção visual completa de complex-script enquanto esse subaspecto não tiver contrato próprio. `w:szCs` permanece intacto.

## Próximo passo operacional

**Review/Highlight DOCX v0.1 — contrato primeiro.**

Objetivo: produzir o segundo DOCX do produto a partir do snapshot limpo da Processing Session + ProcessingReport, sem alterar conteúdo substantivo.

O próximo contrato deve fechar, antes de implementação:
- quais categorias recebem marca visual no DOCX de revisão;
- mecanismo OOXML de marcação (highlight, shading, comentário ou combinação);
- como distinguir applied / unapplied / review / abstention sem ambiguidade;
- como localizar targets pelo structural_path no snapshot final;
- o que fazer quando o target não resolve no final;
- preservação de texto/campos/revisões/estilos;
- allowed-delta específico da marcação;
- separação absoluta entre clean DOCX e review DOCX;
- tratamento de stories/targets não marcáveis;
- determinismo e ZIP/XML preservation.

Por ser uma nova camada de mutação DOCX, considerar auditoria adversarial externa (Claude Opus) antes de freeze/implementação.