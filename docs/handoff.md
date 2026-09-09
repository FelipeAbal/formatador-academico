# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** core vertical do MVP integrado até a fronteira user-facing completa.

Congelados:
- corpus-base v1;
- Parser físico v0.4;
- Analysis v0.1a/v0.1b;
- Decision Vocabulary v0.1;
- Decision Layer v0.1 — freeze 0021;
- Classification Layer v0.1 — freeze 0023;
- OperationPlan v0.1 — freeze 0025;
- SafetyGate v0.1 — freeze 0027;
- Patcher/Applicator v0.1 — freeze 0029 + errata Decimal 0041;
- TransformLog / Execution Record v0.1 — freeze 0031;
- Processing Session / Orchestration v0.1 — freeze 0033;
- Processing Report v0.1 — freeze 0035;
- Review/Highlight DOCX v0.1 — freeze 0037;
- Product Output Bundle v0.1 — freeze 0039;
- Profile Input / Form Schema v0.1 — freeze 0042;
- **Product Input Boundary v0.1 — freeze 0044**.

Este é o HANDOFF corrente. O histórico detalhado fica no Git; não criar `handoff_vNN`.

## Validação corrente

Baselines históricos:
- Parser v0.4: 102/102;
- Analysis completa: 267/267;
- Decision Layer: 290/290;
- Classification: 335/335;
- OperationPlan: 389/389;
- SafetyGate: 442 testes no freeze próprio;
- Patcher: 502/502 no freeze próprio;
- TransformLog: 524/524;
- Processing Session: 565/565;
- Processing Report: 591/591;
- Review DOCX: 627/627;
- Product Output Bundle: 644/644;
- Profile Input: 682/682.

Baseline atual após Product Input Boundary:
- **699/699 OK** no PR #16;
- `main` pós-merge: GitHub Actions **success**;
- failures: 0;
- errors: 0.

GitHub Actions é a execução padrão da suíte. Não gastar Kimi apenas para testar.

## PRs / freezes principais

- PR #5 — Decision Layer; freeze 0021;
- PR #6 — Classification; freeze 0023;
- PR #7 — OperationPlan; freeze 0025;
- PR #8 — SafetyGate; freeze 0027;
- PR #9 — Patcher; squash `559cf8ec812320d066e8b91d431873f7a91f2c1c`; freeze 0029;
- PR #10 — TransformLog; squash `eff4770f2f5ec848d0f5d6b9afb6b2cdfdc8e355`; freeze 0031;
- PR #11 — Processing Session; squash `17b0a37529012a0873c76f27c1072ce297240f5d`; freeze 0033;
- PR #12 — Processing Report; squash `3328b8f9eb8f582aa19c7ced9168561621f32bfb`; freeze 0035;
- PR #13 — Review DOCX; squash `0b8ebad402dd558b357006d98a0d54014d8b5c58`; freeze 0037;
- PR #14 — Product Output Bundle; squash `f87ea08511febd403b75874771ed5aff5db59fc9`; freeze 0039;
- PR #15 — Profile Input + Patcher Decimal erratum; squash `0429fa5bd115da95e8ed8c55a37099f912854e1a`; errata 0041 + freeze 0042;
- PR #16 — Product Input Boundary; head final `4b987fca29c42eb5f80ad5da3ef506209fb50945`; squash `5cbf53a798ef7d9e78e56f2993e466af43b21d7f`; freeze 0044.

## Regra operacional

**Tudo o que puder ser corrigido com segurança dentro do escopo atual deve ser corrigido antes de avançar.**

Só postergar quando houver expansão explícita de escopo, dependência não resolvida, impossibilidade técnica demonstrada, contradição normativa/arquitetural nova ou novo risco de segurança.

Fluxo formal:
1. ChatGPT propõe;
2. modelo apropriado audita quando necessário;
3. ChatGPT integra;
4. Felipe só é interrompido quando sua decisão/conhecimento ou relay externo for realmente necessário;
5. HANDOFF + decisão/commit ao fechar etapa.

### Uso de modelos / custo

- ChatGPT: integração, arquitetura, implementação, auditoria estática, GitHub e HANDOFF;
- Claude Opus: auditoria adversarial quando houver ganho real, especialmente fronteiras de segurança/normatividade;
- Kimi K3: apenas quando execução/implementação especializada justificar custo;
- GitHub Actions: execução normal da suíte.

## Objetivo do MVP

Formatar com segurança DOCX acadêmicos existentes a partir de perfil formal explicitamente declarado.

Não promete conformidade ABNT genérica.

Princípio: **Na dúvida, marcar.**

Saídas centrais:
1. DOCX limpo;
2. DOCX de revisão/highlight;
3. Processing Report canônico.

## Fronteira user-facing congelada

API:

```text
build_product_from_inputs(
    package_snapshot: bytes,
    profile_json_bytes: bytes,
    *,
    max_applied_operations: int = 10000,
) -> ProductOutputBundle
```

Fluxo completo:

```text
DOCX bytes
+ Profile Input JSON bytes
→ Product Input Boundary
    → Profile Input parser/adapter
    → ProcessingProfile
    → Product Output Bundle
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
        → clean DOCX
        → ProcessingReport
        → canonical report JSON
        → Review DOCX
→ ProductOutputBundle
```

Product Input Boundary valida Profile Input antes de tocar o pipeline de DOCX. Erros são classificados por stage:

```text
external_input
profile_input
product_output
```

Sem sucesso parcial.

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

Profile Input v0.1 expõe:

```text
schema_version: "0.1"
profile: {id, version}
rules -> body|heading -> bold|font_size -> exact|set|preserve
```

Ausência não cria regra. `null` não é ausência. Não há defaults/herança normativa entre classes.

## Segurança congelada essencial

- nenhuma invenção/perda substantiva;
- só atuar em subaspecto autorizado;
- ambiguidade não é resolvida silenciosamente;
- opacos preservados/protegidos;
- SafetyGate é veto, nunca autorização;
- precision > coverage;
- abstention correta é sucesso seguro;
- stale snapshot/plan detectado;
- patcher só executa GateClearedOperation;
- snapshot hash + physical_hash revalidados;
- mutação mínima + allowed-delta + postcondition Analysis;
- OriginalPackage nunca mutado in-place;
- `font_size` half-point exato, sem arredondamento/contexto Decimal;
- TransformRecord só para patch APPLIED;
- Session reexecuta pipeline após cada patch;
- Processing Report é projeção read-only;
- Review DOCX é apresentação, não normatividade;
- Review highlight nunca entra no TransformLog;
- Product Output Bundle apenas compõe/prova lineage;
- Profile Input só traduz declaração explícita;
- Product Input Boundary só compõe Profile Input + Bundle e preserva error lineage.

## Processing Session status

```text
quiescent
quiescent_with_unapplied
operation_limit_reached
```

`quiescent` significa apenas que não resta automação segura dentro do slice; não significa conformidade integral.

## Review DOCX v0.1

Única marca criada:

```xml
<w:highlight w:val="yellow"/>
```

Significa apenas “há informação correspondente no relatório”. Não representa severidade nem conformidade.

Direct highlight preexistente nunca é sobrescrito.

## Profile Input / Decimal

- strict UTF-8 bytes;
- UTF-8 BOM / UTF-16 / UTF-32 rejeitados;
- duplicate keys e unknown fields rejeitados;
- JSON numbers → Decimal exato;
- `12`, `12.0`, `1.2e1` canonicalizam igualmente;
- `11.25pt` é unsupported, nunca arredondado;
- `MAX_HALF_POINTS=3276` compartilhado com Patcher;
- `preserve -> RuleMode.CONTAINMENT`;
- `set.allowed` canonicalizado; duplicates semânticos rejeitados.

## Fora do slice automático atual

- P3 spacing patching;
- P4 alignment patching;
- italic patching;
- long_quote/reference execution;
- heading-level rules;
- tables/containers/numbering execution;
- secondary-story execution;
- MOVE/INSERT/MERGE estrutural;
- styles.xml mutation.

## Dívidas não bloqueadoras imediatas

- profile content hash;
- pipeline-context hash;
- equivalência semântica de DOCX reempacotado byte-diferente;
- partial-story isolation;
- multi-operation transaction/rollback;
- persistence/resume;
- exception telemetry;
- otimização para muitos patches sequenciais;
- tradução/localização user-facing dos códigos;
- filenames e download/delivery;
- ZIP opcional de entrega;
- highlight herdado por style;
- target_physical_hash_after em TransformRecord;
- severity/ranking visual;
- paginação física;
- ClassificationEvidence autocontida;
- UI/API final.

### Dívida importante antes de uso amplo

`w:szCs` não é modelado/mutado em `font_size`. O sistema NÃO deve prometer correção visual completa de complex-script; `w:szCs` permanece intacto.

## Próximo passo operacional

**Human-readable Processing Report / Renderer v0.1 — contrato primeiro.**

O core já produz `ProcessingReport` JSON canônico e o DOCX de revisão aponta visualmente onde há informação. Falta uma saída legível por pessoa que explique, sem reler/redecidir:
- o que foi alterado automaticamente;
- o que não pôde ser alterado;
- o que precisa de revisão humana;
- abstentions/warnings relevantes;
- limitações explícitas do processamento;
- referências ao perfil/regra e ao alvo sem expor jargão desnecessário.

Esse renderer deve ser derivado exclusivamente do `ProcessingReport`; não pode calcular conformidade, reanalisar o DOCX, inventar severidade, resolver ambiguity ou criar normatividade.

Primeiro fechar formato e semântica do renderer. UI/download/API vêm depois.
