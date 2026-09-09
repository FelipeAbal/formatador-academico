# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; Parser físico v0.4 congelado; Analysis v0.1a/v0.1b congeladas; Decision Vocabulary v0.1 congelado; Decision Layer v0.1 congelada em 0021; Classification Layer v0.1 congelada em 0023; OperationPlan v0.1 congelado em 0025; SafetyGate v0.1 congelado em 0027; Patcher/Applicator v0.1 congelado em 0029 com **errata Decimal 0041 congelada**; TransformLog / Execution Record v0.1 congelado em 0031; Processing Session / Orchestration v0.1 congelado em 0033; Processing Report v0.1 congelado em 0035; Review/Highlight DOCX v0.1 congelado em 0037; Product Output Bundle v0.1 congelado em 0039; **Profile Input / Form Schema v0.1 implementado, auditado, mergeado e congelado em 0042**.

Este é o HANDOFF corrente. O histórico fica no Git; não criar `handoff_vNN`.

## Validação corrente

- parser v0.4: **102/102**;
- Analysis completa: **267/267**;
- Decision Layer v0.1: **290/290**;
- Classification Layer v0.1: **335/335**;
- OperationPlan v0.1: **389/389**;
- SafetyGate v0.1: **442 testes descobertos** no freeze próprio;
- Patcher v0.1: **502/502 OK** no freeze próprio; errata 0041 incluída na suíte atual;
- TransformLog v0.1: **524/524 OK** no freeze próprio;
- Processing Session v0.1: **565/565 OK** no freeze próprio;
- Processing Report v0.1: **591/591 OK** no freeze próprio;
- Review/Highlight DOCX v0.1: **627/627 OK** no freeze próprio;
- Product Output Bundle v0.1: **644/644 OK** no freeze próprio;
- Profile Input / suíte completa atual: **682/682 OK**;
- GitHub Actions verde no head final do PR #15 e no `main` pós-merge;
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
- PR #11 — Processing Session v0.1; squash `17b0a37529012a0873c76f27c1072ce297240f5d`; freeze 0033;
- PR #12 — Processing Report v0.1; squash `3328b8f9eb8f582aa19c7ced9168561621f32bfb`; freeze 0035;
- PR #13 — Review DOCX v0.1; squash `0b8ebad402dd558b357006d98a0d54014d8b5c58`; freeze 0037;
- PR #14 — Product Output Bundle v0.1; head final `c4dd6ed6792cd1f88d58159c7640ac78b1b2ce1d`; squash `f87ea08511febd403b75874771ed5aff5db59fc9`; freeze 0039;
- PR #15 — Profile Input v0.1 + Patcher Decimal erratum; head final `516924475ebd945f15c0271b6ea467e98c9c70f2`; squash `0429fa5bd115da95e8ed8c55a37099f912854e1a`; errata 0041 + freeze 0042.

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

As três saídas centrais já existem e têm uma única fronteira de produto:

1. **DOCX limpo**;
2. **DOCX de revisão/highlight**;
3. **relatório de processamento JSON canônico**.

Agora também existe a fronteira user-facing de perfil:

```text
Profile Input JSON bytes
→ ProcessingProfile
```

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
- Patcher font_size usa aritmética half-point exata, sem dependência de `Decimal` context e sem arredondamento silencioso;
- OriginalPackage/snapshot nunca mutado in-place;
- TransformRecord só existe para patch APPLIED e é proveniência, nunca autorização;
- Processing Session nunca cria autoridade normativa nova nem reutiliza token stale;
- Processing Report é projeção read-only e nunca reanalisa/reclassifica/redecide;
- Review DOCX é apresentação visual derivada do clean + report, nunca correção normativa;
- marca visual do Review DOCX nunca entra em TransformLog e não deve ser reinjetada automaticamente como clean input;
- Product Output Bundle apenas compõe e prova lineage entre artefatos; não cria nova verdade normativa;
- Profile Input só transforma declaração explícita em ProcessingProfile: ausência permanece ausência, sem defaults/herança/inferência.

## Pipeline de produto congelado

```text
Profile Input JSON bytes
→ parse_profile_input_json
→ ProfileInput
→ build_processing_profile
→ ProcessingProfile

input DOCX bytes + ProcessingProfile
→ Processing Session
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
    → rerun completo até quiescência/limite
→ ProcessingSessionResult
→ clean DOCX
→ ProcessingReport
→ canonical report JSON
→ Review DOCX derivado do clean + report
→ ProductOutputBundle
```

## Slice automático atual

Somente:

```text
P1 / run / bold
P2 / run / font_size
```

Classes executáveis:

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

Após cada patch APPLIED, todo o pipeline é reconstruído e tokens anteriores são descartados.

Status:

```text
quiescent
quiescent_with_unapplied
operation_limit_reached
```

`quiescent` significa ausência de automação segura restante; não significa plena conformidade.

## Processing Report v0.1 — 0034 + freeze 0035

```text
build_processing_report(session_result: ProcessingSessionResult) -> ProcessingReport
```

Famílias:

```text
applied_changes
unapplied_changes
review_items
classification_items
```

Identidade:

```text
processing_report_ref(report)
= sha256(serialize_processing_report(report))
```

Não calcula percentual de conformidade.

## Review/Highlight DOCX v0.1 — 0036 + freeze 0037

```text
build_review_docx(clean_package_snapshot, processing_report) -> ReviewDocxResult
```

Única marca criada:

```xml
<w:highlight w:val="yellow"/>
```

Significa apenas que há informação correspondente no relatório; não representa severity/categoria/compliance.

## Product Output Bundle v0.1 — 0038 + freeze 0039

```text
build_product_output_bundle(
    package_snapshot: bytes,
    profile: ProcessingProfile,
    *,
    max_applied_operations: int = 10000,
) -> ProductOutputBundle
```

Produz atomicamente e vincula:

```text
clean_package_bytes
review_package_bytes
processing_report_json_bytes
processing_report
```

## Profile Input / Form Schema v0.1 — 0040 + freeze 0042

API pública:

```text
parse_profile_input_json(profile_json_bytes: bytes) -> ProfileInput
build_processing_profile(profile_input: ProfileInput) -> ProcessingProfile
processing_profile_from_json(profile_json_bytes: bytes) -> ProcessingProfile
```

### Schema exposto

```text
schema_version: "0.1"
profile: {id, version}
rules -> body|heading -> bold|font_size -> exact|set|preserve
```

### Autoridade

- campo ausente não cria regra;
- `null` é inválido, nunca default;
- body/heading não herdam entre si;
- schema não interpreta “ABNT”;
- rules vazias/classe vazia são rejeitadas;
- IDs internos são `body:bold`, `body:font_size`, `heading:bold`, `heading:font_size`;
- schema version não entra no rule_id.

### Encoding/JSON

- bytes exato;
- até 256 KiB;
- strict UTF-8;
- UTF-8 BOM rejeitado;
- UTF-16/32 rejeitados;
- duplicate keys rejeitadas em todos os níveis;
- unknown fields rejeitados;
- `schema_version` é avaliada antes de campos futuros;
- erros têm `code` estável e first-error determinístico.

### Decimal/font_size

- JSON numbers viram Decimal exato;
- 12 / 12.0 / 1.2e1 canonicalizam para `Decimal("12")`;
- 11.50 -> `Decimal("11.5")`;
- resultado independente de `decimal.getcontext()`;
- 11.25pt → Unsupported, nunca arredondado;
- máximo 32 dígitos significativos e expoente [-16,16] no input v0.1;
- limite deriva de `patcher.MAX_HALF_POINTS=3276`.

### `preserve`

```text
preserve -> RuleMode.CONTAINMENT
```

Sem transformação, item de mudança/revisão ou highlight. Pode existir Decision interna, portanto o summary técnico pode diferir da completa omissão. Perfil só-preserve é válido, mas não é evidência de conformidade.

### `set`

- allowed canonicalizado;
- semantic duplicates rejeitados;
- singleton sem preferred rejeitado;
- preferred deve pertencer a allowed.

### Modelo

`ProfileInput` e `ProfileInputRule` são frozen e auto-validantes; construção programática não bypassa invariantes semânticos.

## Patcher Decimal exactness erratum — 0041

O contrato 0028 já exigia no-rounding, mas a implementação original podia arredondar `Decimal * 2` conforme o contexto global antes da checagem.

0041 corrige somente a implementação:

- half-points por aritmética inteira exata via `Decimal.as_tuple()`;
- contexto Decimal não interfere;
- Decimal adversarial não é arredondado;
- expoentes extremos são rejeitados antes de materializar potências gigantes;
- `MAX_HALF_POINTS` exportado publicamente de forma aditiva.

Sem expansão do slice ou da autoridade normativa.

## Corpus-base v1

- 41 fixtures;
- baseline motor nulo: 20/41 = 48,8%;
- precisão-alvo automática >=99%;
- alto risco desejado >=99,5%;
- tolerância zero a invenção/perda conhecida, dano a campo e alteração indevida de citação direta.

## Dívidas registradas

### Não bloqueadoras imediatas
- heading-level rules;
- analysis/classification versions ainda como assertions do orchestrator;
- possível pipeline-context hash;
- **profile content hash**;
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
- filenames e camada de download/delivery;
- ZIP opcional de entrega;
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

**Product Input Boundary v0.1 — contrato primeiro.**

Agora já existem separadamente:

```text
Profile Input JSON bytes -> ProcessingProfile
DOCX bytes + ProcessingProfile -> ProductOutputBundle
```

O próximo ciclo deve compor as duas fronteiras numa API user-facing única:

```text
DOCX bytes + Profile Input JSON bytes
→ ProductOutputBundle
```

Sem reimplementar parser de perfil, Processing Session ou Product Output Bundle e sem criar nova normatividade.

O contrato deve fechar:
- API única de produto;
- tradução/encapsulamento de `ProfileInputError` e `ProductOutputBundleError` numa fronteira única;
- preservação das causas e códigos machine-readable;
- atomicidade: nunca devolver bundle parcial;
- input/profile bytes imutáveis;
- determinismo;
- comportamento de `max_applied_operations`;
- sem filesystem/UI/filenames/downloads nesta etapa.

Este ciclo é composição/error-boundary. Claude só é necessário se surgir nova autoridade ou ambiguidade de segurança; em princípio ChatGPT + GitHub bastam.
