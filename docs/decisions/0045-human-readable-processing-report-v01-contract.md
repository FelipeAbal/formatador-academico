# 0045 — Human-readable Processing Report / Renderer v0.1 — contrato

**Status:** ACEITO PARA IMPLEMENTAÇÃO — freeze após PR + CI + auditoria final.

## Objetivo

Produzir uma apresentação humana, determinística e somente-leitura a partir do `ProcessingReport` já congelado.

Fronteira:

```text
ProcessingReport v0.1
→ RenderedProcessingReport v0.1 (Markdown UTF-8, pt-BR)
```

O renderer NÃO reanalisa DOCX, NÃO reclassifica, NÃO redecide, NÃO calcula conformidade e NÃO cria severidade.

## Princípio de autoridade

O `ProcessingReport` é a única fonte de verdade desta camada.

O renderer pode:
- selecionar e ordenar campos já existentes;
- converter valores tipados em representação textual fiel;
- traduzir rótulos fixos de apresentação;
- agrupar itens por família já existente.

O renderer não pode:
- inferir causa não registrada;
- inferir localização física por texto/página;
- inferir gravidade;
- inferir sucesso global;
- dizer “conforme”, “não conforme”, “100% correto” ou equivalentes;
- transformar abstention em erro;
- transformar ausência de item em aprovação normativa.

## API pública

```text
render_processing_report(
    report: ProcessingReport,
) -> RenderedProcessingReport
```

## Modelo de saída

```text
HUMAN_REPORT_VERSION = "0.1"
HUMAN_REPORT_MEDIA_TYPE = "text/markdown; charset=utf-8"

RenderedProcessingReport:
    human_report_version: str
    processing_report_ref: str
    media_type: str
    content_bytes: bytes
    content_sha256: str
```

Invariantes:
- `report` deve ser `ProcessingReport` exato/compatível;
- `processing_report_ref == processing_report_ref(report)`;
- `content_bytes` é UTF-8 válido sem BOM;
- `content_sha256 == sha256(content_bytes)`;
- newline canônico `\n`;
- termina com exatamente um `\n`;
- nenhuma dependência de clock, locale do sistema, filesystem, network, LLM, UUID ou random.

## Idioma

v0.1 é explicitamente `pt-BR` e não aceita parâmetro de locale.

Localização futura exige nova versão/contrato. Os códigos machine-readable do upstream podem ser mostrados entre backticks sem tradução semântica.

## Estrutura Markdown v0.1

Ordem fixa:

```text
# Relatório de processamento

## Resumo

## Alterações aplicadas

## Alterações não aplicadas

## Itens para revisão

## Observações de classificação

## Limitações e interpretação
```

Se uma família estiver vazia, a seção continua existindo e informa `Nenhum item.`. Isso mantém formato estável e evita que ausência seja interpretada como conformidade.

## Resumo

Deve exibir, a partir de `report.summary`, no mínimo:
- status técnico da sessão como token machine-readable;
- quantidade de alterações aplicadas;
- quantidade de alterações não aplicadas;
- quantidade de itens para revisão;
- quantidade de observações de classificação;
- quantidade total de classificações finais;
- classificadas / abstidas / não aplicáveis;
- quantidade de warnings de classificação.

Não calcular porcentagens.

O status `quiescent` deve ser descrito apenas como estado técnico de ausência de automação segura restante, nunca como conformidade.

## Alterações aplicadas

Para cada `AppliedChangeItem`, em ordem já fornecida pelo ProcessingReport, mostrar:
- classe do alvo;
- propriedade (`property_slot`);
- valor observado antes;
- valor aplicado;
- `structural_path`;
- `rule_id`;
- `transform_ref` abreviado ou integral de forma determinística.

O renderer não procura texto do documento nem tenta gerar trecho/contexto.

## Alterações não aplicadas

Para cada `UnappliedChangeItem`:
- classe do alvo;
- propriedade;
- valor observado;
- valor desejado;
- razão machine-readable `reason`;
- `finding_kind`;
- `structural_path`;
- `rule_id` quando existir.

Não converter reason em gravidade nem inventar explicação causal além do token registrado.

## Itens para revisão

Para cada `ReviewItem`:
- classe do alvo;
- propriedade;
- `actionability`;
- `reason` machine-readable;
- valor observado quando presente;
- `structural_path`;
- warnings de Decision como tokens, quando existirem;
- `rule_id` quando existir.

Não afirmar que o item é erro; somente que requer revisão/human choice conforme o upstream.

## Observações de classificação

Para cada `ClassificationItem`:
- `classification_status`;
- `target_type`;
- `target_class` quando existir;
- `story_id`;
- `structural_path`;
- reasons como tokens;
- warnings como tokens.

ClassificationItem não recebe severity nem recomendação inventada.

## Valores tipados

Representação determinística e fiel:

- `bool` → `sim` / `não` apenas quando semanticamente é valor booleano; não reinterpretar token;
- `Decimal` → string decimal canônica sem notação dependente de locale;
- `LengthValue(value, "pt")` → `<valor> pt`;
- enums → `.value` entre backticks quando usados como códigos;
- `None` → `não disponível` somente quando o campo upstream admite ausência;
- `str` → texto escapado para Markdown inline, sem alterar conteúdo semântico;
- tuplas/listas de tokens → sequência determinística na ordem upstream.

Tipos inesperados são `HumanReportIntegrityError`, não `repr()` silencioso.

## Escaping Markdown

Todo valor externo/upstream inserido como texto livre deve ser escapado para não criar headings, links, listas ou code fences acidentais.

Tokens de máquina podem ser renderizados como inline code desde que crases internas sejam escapadas/rejeitadas de forma determinística.

Nenhum conteúdo upstream é interpretado como Markdown confiável.

## Referências e hashes

O renderer calcula `processing_report_ref(report)` pela API congelada. Não aceita ref fornecido pelo chamador.

`content_sha256 = sha256(content_bytes)`.

Esses hashes são provenance de apresentação; não autorizam mutação nem entram em TransformLog.

## Limitações e interpretação

A seção final deve conter texto fixo v0.1 deixando explícito:
- relatório é derivado do processamento e não prova conformidade integral;
- `quiescent` não significa conformidade;
- itens abstidos/não aplicáveis permanecem fora de conclusão normativa;
- Review DOCX usa marca visual apenas como indicação de informação correspondente no relatório;
- `w:szCs` permanece fora da correção automática de `font_size` no slice atual.

Não deve afirmar que uma dívida futura ocorreu naquele documento se o ProcessingReport não fornecer essa informação. A redação de `w:szCs` deve ser apresentada como limitação geral do slice, não como diagnóstico daquele arquivo.

## Error model

```text
HumanReportError
HumanReportContractError
HumanReportIntegrityError
```

- tipo de input errado → ContractError;
- versão incompatível/malformed ProcessingReport que atravessasse construção → IntegrityError;
- tipo de valor inesperado em item → IntegrityError;
- erro de encoding/hash/model invariant → IntegrityError;
- programming errors inesperados não são mascarados.

## Imutabilidade

Renderer não modifica o `ProcessingReport` nem qualquer objeto aninhado.

## Determinismo

Mesmo `ProcessingReport` → mesmos bytes e mesmo SHA em qualquer chamada/processo suportado.

Não usar:
- clock/time/datetime;
- random/uuid;
- locale;
- filesystem/open/pathlib;
- network;
- LLM;
- hash() de Python para identidade.

## Fora de escopo v0.1

- HTML;
- PDF;
- DOCX de relatório;
- paginação;
- hyperlinks clicáveis para documento;
- localização por página/linha;
- severity/ranking;
- percentuais de conformidade;
- recomendações geradas;
- tradução multilíngue;
- UI;
- filenames/download;
- alteração do ProductOutputBundle congelado.

## Testes mínimos

1. tipo inválido → ContractError;
2. relatório vazio/no-change renderiza todas as seções;
3. applied bold;
4. applied font_size tipado;
5. unapplied real por patch rejection;
6. review item real;
7. classification abstention real;
8. counts do resumo correspondem ao ProcessingReport;
9. quiescent nunca contém palavra `conforme`/`conformidade` como conclusão positiva;
10. seções vazias dizem `Nenhum item.`;
11. bool determinístico;
12. Decimal canônico;
13. LengthValue pt;
14. None onde permitido;
15. escaping de `#`, `*`, `[`, `]`, backticks e newline em texto livre;
16. structural_path não é interpretado como Markdown;
17. reason/warning tokens preservados;
18. processing_report_ref correto;
19. content_sha256 correto;
20. UTF-8 sem BOM e newline canônico;
21. output termina com exatamente um newline;
22. inputs não mutados;
23. repetição byte-idêntica;
24. sem IO/network/clock/random/locale/LLM/dynamic import;
25. tipo de valor inesperado → IntegrityError;
26. renderer não importa parser/analysis/classification engine/decision engine/patcher para reexecução;
27. suíte completa regressiva verde.

## Critério de aceite

Congelar somente se:
- renderer for projeção pura do ProcessingReport;
- não houver nova verdade normativa;
- nenhuma frase puder ser lida como certificação de conformidade;
- conteúdo livre estiver escapado;
- hashes/ref fecharem;
- determinismo for provado;
- suíte completa estiver verde.
