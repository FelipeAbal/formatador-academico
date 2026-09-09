# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** core vertical do MVP integrado até a fronteira user-facing completa + relatório humano Markdown.

Este é o HANDOFF corrente. O histórico detalhado fica no Git; não criar `handoff_vNN`.

## Baseline validado

- Parser físico v0.4 congelado;
- Analysis v0.1a/v0.1b congeladas;
- Decision Vocabulary v0.1 congelado;
- Decision Layer v0.1 — freeze 0021;
- Classification Layer v0.1 — freeze 0023;
- OperationPlan v0.1 — freeze 0025;
- SafetyGate v0.1 — freeze 0027;
- Patcher/Applicator v0.1 — freeze 0029 + errata Decimal 0041;
- TransformLog v0.1 — freeze 0031;
- Processing Session v0.1 — freeze 0033;
- Processing Report v0.1 — freeze 0035;
- Review/Highlight DOCX v0.1 — freeze 0037;
- Product Output Bundle v0.1 — freeze 0039;
- Profile Input / Form Schema v0.1 — freeze 0042;
- Product Input Boundary v0.1 — freeze 0044;
- Human-readable Processing Report v0.1 — freeze 0046.

Suíte completa atual: **716/716 OK** no PR #17 e GitHub Actions `success` no `main` pós-merge `804ce6f3fa1eac05f09e623f5587a9cb29446446`.

Failures: 0. Errors: 0.

GitHub Actions é a execução padrão da suíte; não gastar Kimi apenas para testar.

## PRs / merges principais

- PR #3 — Analysis v0.1b Marco 1;
- PR #4 — Analysis v0.1b Marco 2;
- PR #5 — Decision Layer v0.1 — squash `b81f628a0358cbc9483e9207d4f749ea4a2ca475`;
- PR #6 — Classification v0.1 — squash `736c33036224562549b1b5cb026bd6bfdfd2e112`;
- PR #7 — OperationPlan v0.1 — squash `1c11d08dcd6fc219bb2f4e0ce5321db027a5801a`;
- PR #8 — SafetyGate v0.1 — squash `d47b8e67d2788eb1912ef951ec7dcedb457376cb`;
- PR #9 — Patcher v0.1 — squash `559cf8ec812320d066e8b91d431873f7a91f2c1c`;
- PR #10 — TransformLog v0.1 — squash `eff4770f2f5ec848d0f5d6b9afb6b2cdfdc8e355`;
- PR #11 — Processing Session v0.1 — squash `17b0a37529012a0873c76f27c1072ce297240f5d`;
- PR #12 — Processing Report v0.1 — squash `3328b8f9eb8f582aa19c7ced9168561621f32bfb`;
- PR #13 — Review DOCX v0.1 — squash `0b8ebad402dd558b357006d98a0d54014d8b5c58`;
- PR #14 — Product Output Bundle v0.1 — squash `f87ea08511febd403b75874771ed5aff5db59fc9`;
- PR #15 — Profile Input + Patcher Decimal erratum — squash `0429fa5bd115da95e8ed8c55a37099f912854e1a`;
- PR #16 — Product Input Boundary v0.1 — squash `5cbf53a798ef7d9e78e56f2993e466af43b21d7f`;
- PR #17 — Human-readable Processing Report v0.1 — head final `92cb328d8cf86ac3fcf1167d93433b380771f689`; squash `804ce6f3fa1eac05f09e623f5587a9cb29446446`.

## Regra operacional

**Tudo o que puder ser corrigido com segurança dentro do escopo atual deve ser corrigido antes de avançar.**

Só postergar quando houver expansão explícita de escopo, dependência não resolvida, impossibilidade técnica demonstrada, contradição normativa/arquitetural nova ou novo risco de segurança.

Fluxo:
1. ChatGPT propõe;
2. Claude Opus audita quando houver ganho real em segurança/arquitetura;
3. ChatGPT integra;
4. Felipe só é interrompido quando sua decisão/conhecimento é realmente necessário ou quando precisa enviar algo a outro modelo;
5. implementação em branch/PR;
6. CI + inspeção final;
7. freeze + HANDOFF.

### Uso de modelos / custo

- ChatGPT: arquitetura, integração, metodologia, implementação e GitHub quando viável;
- Claude Opus: auditoria adversarial de alto risco quando houver ganho real;
- Kimi K3: somente implementação/auditoria especializada quando ganho justificar custo extra;
- GitHub Actions: testes normais.

Kimi está pago por crédito extra; minimizar agressivamente.

## Objetivo do MVP

Formatar com segurança DOCX acadêmicos existentes a partir de regras explicitamente declaradas pelo usuário.

Não promete “conformidade ABNT” genérica e não inventa regras ausentes.

Princípio: **Na dúvida, marcar.**

## Fronteira user-facing atual

```text
DOCX bytes
+ Profile Input JSON bytes
→ build_product_from_inputs(...)
→ ProductOutputBundle
```

`ProductOutputBundle` entrega atomicamente e vincula:

1. `clean_package_bytes` — DOCX limpo;
2. `review_package_bytes` — DOCX de revisão/highlight;
3. `processing_report_json_bytes` — Processing Report JSON canônico;
4. `processing_report` — modelo tipado correspondente.

O relatório humano é derivado separadamente:

```text
ProcessingReport
→ render_processing_report(...)
→ RenderedProcessingReport
```

Saída v0.1: Markdown UTF-8 pt-BR, determinístico, hash-bound ao ProcessingReport.

## Pipeline congelado

```text
Profile Input JSON bytes
→ parse_profile_input_json
→ ProfileInput
→ build_processing_profile
→ ProcessingProfile

DOCX bytes + ProcessingProfile
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

ProcessingReport
→ Human-readable Markdown report
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

## Segurança congelada

- nenhuma invenção ou perda substantiva;
- só atuar no subaspecto autorizado;
- ausência de regra continua ausência;
- `null` não vira default;
- body/heading não herdam normatividade entre si;
- ambiguidade não é resolvida silenciosamente;
- opacos são preservados/protegidos;
- SafetyGate é veto, nunca autorização;
- abstention correta é sucesso seguro;
- stale plan/document drift detectado antes de patch;
- Patcher só executa `GateClearedOperation`;
- snapshot SHA + target physical_hash revalidados antes da mutação;
- mutação mínima + allowed-delta + postcondition Analysis obrigatórios no Patcher;
- Patcher font_size usa half-points exatos sem depender do `Decimal` context;
- OriginalPackage/snapshot nunca mutado in-place;
- TransformRecord só existe para patch APPLIED e nunca autoriza transformação;
- Processing Session refaz todo o pipeline após cada patch e descarta tokens stale;
- Processing Report é projeção read-only;
- Review DOCX é apresentação visual, não correção normativa;
- marca de Review DOCX não entra em TransformLog e não deve ser reinjetada automaticamente como clean input;
- Product Output Bundle apenas compõe e prova lineage;
- Product Input Boundary apenas compõe Profile Input + Product Output Bundle;
- Human-readable Report apenas projeta o ProcessingReport e não calcula conformidade/severity/recomendação.

## Profile Input v0.1

Schema:

```text
schema_version: "0.1"
profile: {id, version}
rules -> body|heading -> bold|font_size -> exact|set|preserve
```

Regras:
- campo ausente não cria regra;
- `null` é inválido;
- JSON strict UTF-8, sem BOM;
- duplicate keys/unknown fields rejeitados;
- Decimal exato e canonicalizado;
- 11.25 pt é unsupported, nunca arredondado;
- `preserve -> RuleMode.CONTAINMENT`;
- `set.allowed` canonicalizado; duplicatas semânticas rejeitadas;
- modelos frozen e auto-validantes.

## Human-readable Processing Report v0.1 — 0045 + freeze 0046

```text
render_processing_report(report: ProcessingReport)
→ RenderedProcessingReport
```

Características:
- Markdown pt-BR;
- UTF-8 sem BOM;
- LF canônico;
- exactly one final newline;
- `processing_report_ref` calculado pela API congelada;
- SHA-256 dos bytes renderizados;
- resumo + quatro famílias do relatório + limitações;
- valores bool/Decimal/LengthValue renderizados deterministicamente;
- tokens machine-readable preservados;
- dados livres protegidos contra interpretação Markdown;
- `quiescent` explicitamente não significa conformidade integral;
- não altera o `ProductOutputBundle` congelado.

## Dívidas registradas

### Importantes antes de uso amplo

- `w:szCs` não é modelado/mutado no slice `font_size`; não prometer correção visual completa de complex-script;
- profile content hash ainda não existe;
- equivalência semântica de DOCX reempacotado byte-diferente não está resolvida;
- performance de muitos patches sequenciais ainda não otimizada.

### Expansões futuras

- heading-level rules;
- P3/P4 patching;
- italic patching;
- long_quote/reference executáveis;
- stories secundárias;
- transaction/rollback multi-operação;
- persistence/resume;
- styles.xml patching;
- exception telemetry;
- HTML/PDF/DOCX do relatório;
- multilíngue;
- localização física por página;
- severity/ranking;
- UI/API final.

## Próximo passo operacional

**Product Delivery / File Naming v0.1.**

Objetivo: transformar resultados já produzidos em artefatos de entrega sem reprocessar o documento.

Deve fechar, antes de implementar:
- nomes determinísticos e seguros para DOCX limpo, DOCX review, JSON técnico e Markdown humano;
- sanitização de nome-base fornecido pelo usuário sem inferir título do documento;
- manifest/hash binding entre os arquivos;
- decidir se v0.1 retorna coleção tipada de arquivos ou também ZIP determinístico;
- não alterar ProductOutputBundle congelado;
- sem filesystem obrigatório no core; bytes in-memory;
- nenhum novo conteúdo normativo.

Em princípio ChatGPT + GitHub bastam; Claude só se o contrato de ZIP/manifest introduzir risco de integridade ou ambiguidade relevante.
