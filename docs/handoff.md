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
- Human-readable Processing Report v0.1 — freeze 0046;
- Product Delivery / File Naming v0.1 — freeze 0048.

Suíte completa atual: **745/745 OK** no PR #27, após a implementação integrada de P4/alignment. O CI verde foi a run `34511314480`.

GitHub Actions: `success` na run `34511533013`, sobre o commit da branch `9d571f688d8e1ce5849bb09d3bb16e58a029eb5a`, antes do merge. A main recebeu o squash do PR #27 `858a33f09104fce0a5804caec6c1df07b0151ad2`.

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
- PR #17 — Human-readable Processing Report v0.1 — head final `92cb328d8cf86ac3fcf1167d93433b380771f689`; squash `804ce6f3fa1eac05f09e623f5587a9cb29446446`;
- PR #18 — Product Delivery / File Naming v0.1 — merge squash `565ab01d4afab0dc240f136c70995ebd1227ac79`; CI pós-merge `34500432604`.
- PR #19 — registro da auditoria Claude Opus inicial; merge `af7451f...`;
- PR #20 — decisão 0048 Product Delivery congelada; merge `d56f71...`;
- PR #21 — contrato inicial da decisão 0049; merge `86e420e...`;
- PR #22 — primeira auditoria Claude Opus e revisão do contrato 0049; merge `1880a955...`;
- PR #23 — auditoria final do XSD e correções documentais da decisão 0049; merge `1eed32ec...`;
- PR #24 — Analysis: salvaguardas para alinhamento de parágrafo; merge `843045d...`, CI `34507770885`;
- PR #25 — Profile Input schema 0.2 para alinhamento; merge squash `d3770c055c43ceaea0df32c44095bc3422199627`, CI `34508799107`.
- PR #27 — implementação integrada de P4/alignment; merge squash `858a33f09104fce0a5804caec6c1df07b0151ad2`; CI `34511533013`.

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
P4 / paragraph / alignment
```

Classes executáveis:

```text
body
heading
```

Ainda fora do slice automático:
- P3 spacing patching;
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

## Profile Input v0.2 e compatibilidade com v0.1

Implementado no PR #25 e integrado na main.

- schema 0.1 continua aceito;
- schema 0.2 é superconjunto estrito de 0.1;
- propriedades aceitas são despachadas pela versão declarada, a partir de uma única tabela;
- `alignment` aceita somente o vocabulário user-facing `left`, `center`, `right`, `justify`;
- `alignment` continua rejeitado em perfil declarado como 0.1;
- `line_spacing` permanece fora do schema 0.2;
- 740/740 testes passaram no CI.

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

## Etapa concluída: Product Delivery / File Naming v0.1 — decisão 0047

Implementada e validada na PR #18.

- cinco arquivos tipados em ordem fixa;
- bytes derivados exatamente do ProductOutputBundle e do renderer humano congelado;
- manifest canônico com hashes, tamanhos, roles e media types;
- nomes determinísticos, sem paths, traversal ou nomes reservados do Windows;
- processamento inteiramente em memória;
- sem ZIP, filesystem ou nova autoridade normativa;
- 735/735 testes verdes na CI.

Correções finais realizadas após a primeira execução:

- normalização correta de tabulações e quebras de linha;
- teste de path traversal alinhado à rejeição de nomes ocultos;
- teste do relatório humano ajustado para texto UTF-8 com acentos.

## Auditoria Claude Opus registrada: estado em 2026-09-10

Arquivo integral: `docs/audits/auditoria_claude_opus_formatador_565ab01.md`.

A auditoria independente foi executada sobre a main em `565ab01d4afab0dc240f136c70995ebd1227ac79`, com verificação do código, execução local da suíte, conferência do CI e inspeção do histórico.

Conclusões registradas:

- estado saudável: 735/735 testes aprovados e CI pós-merge verde na run `34500432604`;
- PR #18 confirmada como integrada;
- nenhum PR aberto no momento da auditoria;
- o briefing anterior foi considerado factualmente correto;
- P3 não deve ser a próxima implementação direta;
- a execução em nível de parágrafo exige emendas coordenadas nos contratos 0029, 0031, 0033, 0037 e 0042;
- a análise atual não incorpora `numbering.xml` à resolução de spacing e alignment;
- o Review DOCX pode lançar exceção diante do primeiro item de parágrafo, interrompendo a entrega atômica;
- o espaçamento exige tratamento conjunto de `w:line` e `w:lineRule`, além de preservação por atributo dos demais campos de `w:spacing`;
- itálico permanece fora do slice por risco semântico, apesar do baixo custo técnico;
- a auditoria recomenda uma habilitação de parágrafo com P4/alignment como carga inicial, seguida de P3;
- a auditoria recomenda formalizar o freeze do Product Delivery antes da próxima decisão de implementação.

## Decisão de Felipe para o próximo ciclo

A sequência foi aprovada:

1. 0048: freeze do Product Delivery;
2. 0049: habilitação de execução em nível de parágrafo, com P4/alignment como carga;
3. 0051: P3/spacing.line após os trilhos de parágrafo estarem validados.

Escolhas de produto confirmadas para a decisão 0049:

- Review DOCX: marcar somente o primeiro run marcável do parágrafo, em ordem de documento;
- se nenhum run for marcável, não inserir marca e relatar a razão;
- a marca passa a indicar informação sobre o alvo do run, e não somente sobre o run;
- o Review DOCX não usará cores ou marcas diferentes para distinguir achados de run e de parágrafo;
- Profile Input: `schema_version 0.2` será superconjunto estrito de 0.1;
- o conjunto de propriedades aceitas será despachado pela versão declarada;
- perfis 0.1 continuam válidos, mas `alignment` em perfil declarado como 0.1 continua inválido;
- versões anteriores continuarão aceitas;
- a versão será incrementada por ciclo de propriedade executável, sem inserir P3 prematuramente no schema 0.2;
- parágrafos com `w:numPr` direto ou herdado ficarão fora do slice executável e aparecerão no relatório humano com razão explícita;
- P3 v0.1 governará somente `spacing.line`;
- P3 aceitará declarativamente apenas múltiplos de linha com `rule="auto"`;
- o Analysis continuará lendo `atLeast` e `exact` como valores observados, sem permitir sua declaração no primeiro ciclo;
- itálico permanecerá fora do patching automático, mas poderá entrar futuramente como detecção sem alteração;
- P4 tratará `start` como equivalente a `left` e `end` como equivalente a `right` em texto LTR;
- documentos bidirecionais ficarão fora do slice P4;
- a equivalência lexical será registrada como fato do OOXML, não como regra normativa de formatação.

Nenhuma implementação de P3, P4, UI ou API foi iniciada por este registro.

Modelos previstos:

- ChatGPT: integração, implementação e controle do fluxo;
- Claude Sonnet: redação e implementação do contrato 0049;
- Claude Opus: auditoria do contrato 0049, sobretudo a ordem canônica de `CT_PPr` e a equivalência lexical de `w:jc`;
- Kimi: somente se surgir uma tarefa especializada com ganho claro.


## Decisão 0049 revisada após auditoria do Claude Opus

Arquivos:

- contrato: `docs/decisions/0049-paragraph-target-enable-p4-contract.md`;
- auditoria: `docs/audits/auditoria_claude_opus_0049.md`.

A auditoria classificou a proposta como **APROVAR COM AJUSTES**. Os ajustes foram incorporados nesta branch, sem alteração de código de produção.

Correções incorporadas:

- exemplo JSON corrigido para usar `value` em modo `exact`;
- Analysis 0018 incluída entre as camadas a emendar;
- normalização de `w:jc` atribuída à Analysis, preservando `raw_value`;
- `w:bidi` de `pPr` distinguido de `LanguageSpec.bidi`;
- exclusões com camada responsável e diferença entre `review` e `unapplied_change`;
- fluxo do Processing Session separado entre bindings de parágrafo e de run;
- vocabulário user-facing definido como `left`, `center`, `right` e `justify`;
- tokens de escrita definidos, com `justify` convertido para `both`;
- revalidação de `physical_hash` mantida como precondição, sem prometer campo inexistente no TransformRecord;
- ordem de `CT_PPr` incluída como hipótese a conferir diretamente no `wml.xsd`;
- testes de compatibilidade de schema, equivalência lexical, cardinalidade de decisões e marcação única adicionados;
- `line_spacing` explicitamente fora do schema 0.2.

A decisão continua pendente de aprovação final do contrato e da conferência do `wml.xsd`. Nenhuma implementação de P4 foi autorizada.

Modelos previstos:

- ChatGPT: integração e implementação após aprovação;
- Claude Sonnet: implementação estreita, se desejado;
- Claude Opus: auditoria final da ordem de `CT_PPr` e do contrato revisado;
- Kimi: somente se surgir uma tarefa especializada com ganho claro.


## P4 / alignment implementado

A implementação integrada foi concluída na branch `implement-0049-p4-end-to-end`.

- Profile Input 0.2 aceita `alignment` com vocabulário `left`, `center`, `right`, `justify`;
- o adapter converte `justify` para o token interno `both`;
- Analysis normaliza `start` para `left` e `end` para `right`, preservando o token bruto na evidência;
- listas com `w:numPr` e parágrafos bidi ficam fora do patching automático, com razão explícita;
- Patcher cria ou reutiliza `w:pPr` como primeiro filho de `w:p` e escreve `w:jc` na posição canônica;
- `w:jc` sem `w:val`, duplicado ou fora da forma canônica é rejeitado com segurança;
- TransformLog registra a operação `paragraph/P4/alignment` com a mesma cadeia de proveniência;
- Review DOCX marca somente o primeiro run marcável do parágrafo;
- o teste da fronteira DOCX + Profile Input 0.2 passou;
- 745/745 testes passaram no CI.

O P4 ainda não cobre listas, documentos bidirecionais ou alteração de estilos globais, conforme o contrato 0049.

Próxima etapa aprovada: P3, limitado a `spacing.line`, com declaração user-facing somente em múltiplos de linha e `rule="auto"`. A leitura observada continuará aceitando `auto`, `atLeast` e `exact`.

## Auditoria final da decisão 0049

Arquivo: `docs/audits/auditoria_xsd_0049_aprovacao.md`.

A conferência direta do `wml.xsd` confirmou a ordem prevista de `CT_PPrBase` e `CT_PPr`, usando duas cópias independentes do schema e validação do método contra a ordem já registrada de `CT_RPr`.

A implementação decorrente dessa decisão foi validada no PR #27 com 745 testes verdes.

A auditoria classificou a 0049 como **aprovada para implementação**, condicionada a cinco correções de contrato. Todas foram incorporadas nesta branch:

1. remoção das cinco sequências literais que quebravam a renderização dos títulos;
2. promoção da ordem de `CT_PPr` para ordem verificada, com proveniência ISO/IEC 29500-4:2016;
3. distinção explícita entre `CT_PPr` e `CT_PPrGeneral`;
4. separação das regras de posicionamento de `w:pPr` e `w:jc`, incluindo `w:jc` sem `w:val` como forma inválida;
5. definição de um único conjunto canônico para comparação e escrita de alinhamento.

Após o merge desta correção documental e CI verde, a implementação de P4 foi iniciada e concluída na branch própria. A implementação deverá manter atenção especial à separação entre bindings de parágrafo e de run, à leitura de `pPr/w:bidi` e ao bloqueio de razões falsas para exclusões de slice.

## Etapa atual após o merge do PR #25

A etapa de Profile Input 0.2 está concluída e integrada. A próxima branch é `implement-0049-processing-session-paragraphs`.

Próximo passo: adaptar Processing Session para separar bindings de parágrafo e de run, mantendo o ciclo atual de rerun, os tokens stale e os limites de operação. Patcher, TransformLog e Review DOCX só serão alterados depois que esse contrato intermediário estiver coberto por testes.




## Auditoria Claude Opus da decisão 0051 e correção independente

Em 2026-09-10, a auditoria do Claude Opus sobre o rascunho 0051 foi registrada em `docs/audits/auditoria_claude_opus_0051.md`.

A auditoria aprovou o desenho geral com ajustes e encontrou um defeito independente já presente na implementação de P4: a tabela `PPR_CANONICAL_ORDER` usava `mirrorInd` em vez de `mirrorIndents`. A correção foi aplicada na branch `implement-0051-p3-line-spacing`, acompanhada de teste de regressão.

Também foram incorporados ao contrato 0051:

- exemplo JSON corrigido com `profile` e classe `body`;
- mudança automática restrita a observações `rule="auto"`;
- observações `atLeast` e `exact` encaminhadas para revisão;
- `lineRule` ausente tratado pelo default `auto` do XSD quando `line` existe;
- `lineRule` presente sem `line` tratado como não resolvido;
- unidade universal como `18pt` tratada como não suportada;
- preservação verificável dos atributos de `w:spacing` fora do P3;
- guardas de numbering e bidi explicitamente repetidas na resolução de spacing;
- conversão por aritmética inteira exata sobre múltiplos de 240;
- modos `exact`, `set` e `preserve` mantidos, com validação de múltiplos;
- `rule="auto"` implícito na entrada e explícito no XML escrito;
- validação das invariantes de `LineSpacingValue` no modelo;
- compatibilidade temporária documentada de `NONCANONICAL_RUN_PROPERTIES` para propriedades de parágrafo.

O PR #29 permanece aberto como rascunho documental. A implementação de P3 ainda não começou. Próximo passo após CI: congelar o contrato, caso não surja nova objeção, e iniciar a implementação em ciclo próprio.


## P3 em implementação: `spacing.line`

O contrato 0051 foi aprovado após a auditoria Claude Opus e a implementação inicial está na branch `implement-0051-p3-line-spacing`, PR #29.

Já integrado na branch:

- Profile Input schema 0.3, cumulativo com 0.1 e 0.2;
- declaração pública de múltiplos de linha, com `rule="auto"` implícito;
- conversão exata por aritmética inteira sobre unidades de 240 avos de linha;
- adapter para `paragraph/P3/spacing.line`;
- validação de invariantes no Processing Session;
- Analysis com leitura observacional de `auto`, `atLeast` e `exact`;
- `lineRule` sem `line` não mascara valor herdado;
- unidades universais como `18pt` tratadas como não suportadas;
- listas e bidi bloqueados no slot de spacing;
- Decision Layer impede troca automática de `exact` ou `atLeast` para `auto`;
- Patcher altera somente `w:line` e `w:lineRule`, preservando os demais atributos de `w:spacing`;
- Transform Log e Review DOCX reconhecem P3;
- correção independente de `mirrorInd` para `mirrorIndents`, com regressão;
- auditoria integral registrada em `docs/audits/auditoria_claude_opus_0051.md`.

CI atual: **757/757 testes verdes**, run `34525989518`, após a matriz adversarial inicial de P3.

Antes do merge ainda faltam a matriz adversarial específica de P3, a comparação programática da ordem canônica contra o XSD versionado, a validação automatizada dos exemplos JSON dos contratos e uma inspeção final do diff. O PR permanece aberto até essa revisão.
