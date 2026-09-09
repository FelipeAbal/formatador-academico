# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; Parser físico v0.4 congelado; Analysis v0.1a/v0.1b congeladas; Decision Vocabulary v0.1 congelado; Decision Layer v0.1 congelada em 0021; Classification Layer v0.1 congelada em 0023; OperationPlan v0.1 congelado em 0025; SafetyGate v0.1 congelado em 0027; Patcher/Applicator v0.1 congelado em 0029; TransformLog / Execution Record v0.1 congelado em 0031; Processing Session / Orchestration v0.1 congelado em 0033; Processing Report v0.1 congelado em 0035; **Review/Highlight DOCX v0.1 implementado, auditado, mergeado e congelado em 0037**.

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
- Processing Report v0.1: **591/591 OK** no freeze próprio;
- Review/Highlight DOCX / suíte completa atual: **627/627 OK**;
- GitHub Actions verde no head final do PR #13 e no `main` pós-merge;
- failures: 0;
- errors: 0;
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
- PR #12 — Processing Report v0.1; head final `28ffb60224509cce0bd7916ae39810a2c6397a81`; squash `3328b8f9eb8f582aa19c7ced9168561621f32bfb`; freeze 0035;
- PR #13 — Review DOCX v0.1; head final `8458874f8533f2107f85a6d4d8dde8e7cfa09e53`; squash `0b8ebad402dd558b357006d98a0d54014d8b5c58`; freeze 0037.

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

Saídas previstas e agora tecnicamente existentes no core:
1. **DOCX limpo** — `ProcessingSessionResult.output_package_bytes`;
2. **DOCX de revisão/highlight** — `ReviewDocxResult.output_review_package_bytes`;
3. **relatório de processamento machine-readable** — `ProcessingReport` + serialização canônica.

Ainda não existe uma API de produto única que empacote as três saídas nem renderer human-readable do relatório.

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
- mutação mínima + allowed-delta + postcondition Analysis obrigatórios no Patcher normativo;
- OriginalPackage/snapshot nunca mutado in-place;
- TransformRecord só existe para patch APPLIED e é proveniência, nunca autorização;
- Processing Session nunca cria autoridade normativa nova nem reutiliza token stale;
- Processing Report é projeção read-only e nunca reanalisa/reclassifica/redecide;
- Review DOCX é apresentação visual derivada do clean + report, nunca correção normativa;
- marca visual do Review DOCX nunca entra em TransformLog e não deve ser reinjetada automaticamente como clean input.

## Pipeline core congelado

```text
input DOCX bytes
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
→ Review DOCX derivado do clean final + ProcessingReport
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

Após cada patch APPLIED, todo o pipeline é reconstruído e os tokens anteriores são descartados.

Status:

```text
quiescent
quiescent_with_unapplied
operation_limit_reached
```

`quiescent` significa ausência de automação segura restante; não significa plena conformidade.

## Processing Report v0.1 — contrato 0034 + freeze 0035

Fronteira:

```text
build_processing_report(
    session_result: ProcessingSessionResult,
) -> ProcessingReport
```

Machine-readable, read-only e determinístico.

Famílias:

```text
applied_changes
unapplied_changes
review_items
classification_items
```

- applied_changes: TransformRecord efetivamente aplicado;
- unapplied_changes: gate blocked, patch rejected ou operation limit ligados a final Decision;
- review_items: final Decisions review/human_choice;
- classification_items: abstention ou warning relevante.

`not_applicable` puro permanece em summary/StoryCoverage para não gerar ruído individual.

Identidade:

```text
processing_report_ref(report)
=
sha256(serialize_processing_report(report))
```

Não calcula percentual de conformidade.

## Review/Highlight DOCX v0.1 — contrato 0036 + freeze 0037

Fronteira:

```text
build_review_docx(
    clean_package_snapshot: bytes,
    processing_report: ProcessingReport,
) -> ReviewDocxResult
```

### Marca visual

Única marca criada:

```xml
<w:highlight w:val="yellow"/>
```

Significa apenas: existe informação correspondente no ProcessingReport para este run.

Não representa severity/categoria/compliance.

### Marcáveis

Somente run targets de:
- AppliedChangeItem;
- UnappliedChangeItem;
- ReviewItem.

ClassificationItems são integralmente report-only no v0.1 e contabilizados em `unmarkable_classification_item_count`.

### Existing highlight

Direct highlight preexistente, amarelo ou não:

```text
unmarked / existing_highlight
```

Nunca sobrescrever.

Highlight herdado por style não é modelado no v0.1.

### Superfície visual

Marcáveis:
- w:t com conteúdo;
- w:sym;
- w:tab;
- w:br;
- runs visíveis em containers compatíveis, inclusive hyperlink e w:ins.

Unmarked normal:

```text
existing_highlight
noncanonical_run_properties
no_visual_surface
protected_revision_run
```

`no_visual_surface`: empty/rPr-only, instrText-only, fldChar-only, drawing/object/pict-only.

`protected_revision_run`: delText ou run sob w:del.

### Conservação

- apenas `word/document.xml` pode mudar;
- usa infraestrutura de package/XML congelada do Patcher;
- extensões estrangeiras como w14 são preservadas/toleradas somente na camada review;
- allowed-delta é **assimétrico/set-driven**: neutraliza apenas o highlight criado no AFTER dos paths realmente marked;
- highlight autoral de run unmarked continua participando da comparação;
- sem postcondition Analysis, pois Analysis não modela w:highlight; a postcondition física é load-bearing;
- zero candidatos marcáveis → review bytes exatamente iguais aos clean bytes.

### Target identity / error model

AppliedChangeItem usa structural_path com guard P1/P2/document.xml porque o hash armazenado é pré-transformação.

UnappliedChangeItem/ReviewItem exigem physical_hash do snapshot final.

Drift em path/type/hash é `ReviewDocxIntegrityError`, não resultado normal.

### Resultado

`ReviewDocxResult` registra:
- review_docx_version;
- parser_version;
- processing_report_version/ref;
- changed_part;
- input/output SHA;
- output review bytes;
- mark_results;
- unmarkable_classification_item_count.

CI pós-merge: **627/627 OK** no SHA `0b8ebad402dd558b357006d98a0d54014d8b5c58`.

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
- highlight herdado por style;
- Classification run-level persistida;
- target_physical_hash_after em TransformRecord;
- severity/ranking visual;
- paginação física;
- drill-down de ClassificationEvidence autocontida;
- UI/API final.

### Dívida importante antes de uso amplo

`w:szCs` não é modelado/mutado no slice font_size. O sistema NÃO deve prometer correção visual completa de complex-script enquanto esse subaspecto não tiver contrato próprio. `w:szCs` permanece intacto.

## Próximo passo operacional

**Product Output Bundle / end-to-end product boundary v0.1 — contrato primeiro.**

Agora os três artefatos centrais existem separadamente. O próximo ciclo deve definir uma fronteira única que receba:

```text
input DOCX bytes
+ ProcessingProfile
```

e entregue de forma vinculada e determinística:

```text
clean DOCX bytes
review DOCX bytes
ProcessingReport / serialized report
```

Sem reimplementar nenhum motor congelado e sem criar nova verdade normativa.

O contrato deve fechar antes de implementação:
- API de produto única;
- vínculo/hash entre input, clean, report e review;
- comportamento quando a Processing Session termina com unapplied/operation_limit;
- nomes/tipos distintos para evitar reinjeção acidental do review como clean;
- serialização do report como terceiro artefato;
- atomicidade do bundle;
- error propagation;
- determinismo;
- possibilidade de renderer human-readable como etapa separada, não misturada ao core.

Esse ciclo é de composição/orquestração de outputs, não de nova mutação OOXML. Auditoria externa só será necessária se surgir nova autoridade, novo formato mutável ou mudança nos contracts congelados.