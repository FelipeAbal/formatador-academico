# 0046 — Human-readable Processing Report / Renderer v0.1 — freeze

**Status:** CONGELADO.

## Contrato

Contrato aceito: decisão 0045.

## Implementação

PR #17 — `Human-readable Processing Report v0.1`.

- head final auditado: `92cb328d8cf86ac3fcf1167d93433b380771f689`;
- squash merge: `804ce6f3fa1eac05f09e623f5587a9cb29446446`;
- base: decisão 0045 em `970d1d7ecc824cc791f56f6bdf4849f679f7d2aa`.

## Evidência de teste

Suíte completa no head final do PR: **716/716 OK** após correção de um teste excessivamente amplo.

A primeira rodada falhou em um único teste porque ele proibia a palavra `gravidade` no relatório inteiro, enquanto a seção fixa de limitações corretamente dizia que a cor do Review DOCX não representa gravidade. O teste/linguagem foi alinhado sem relaxar a autoridade do renderer; a rodada seguinte ficou integralmente verde.

GitHub Actions no `main` pós-merge `804ce6f...`: **success**.

## Superfície pública congelada

```text
render_processing_report(report: ProcessingReport) -> RenderedProcessingReport
```

```text
HUMAN_REPORT_VERSION = "0.1"
HUMAN_REPORT_MEDIA_TYPE = "text/markdown; charset=utf-8"
```

`RenderedProcessingReport` vincula:
- `processing_report_ref`;
- bytes Markdown UTF-8;
- SHA-256 do conteúdo;
- versão/media type.

## Semântica congelada

- projeção pura de `ProcessingReport`;
- Markdown pt-BR;
- nenhuma reanálise de DOCX;
- nenhuma nova classificação/Decision;
- nenhuma severity/ranking;
- nenhum percentual de conformidade;
- nenhuma afirmação de conformidade integral;
- `quiescent` permanece estado técnico, não certificação;
- valores livres/tokens são protegidos contra interpretação Markdown indevida;
- saída determinística, UTF-8 sem BOM, LF canônico e exatamente um newline final;
- não altera `ProductOutputBundle` v0.1.

## Cobertura relevante

Testes reais incluem:
- no-change;
- bold aplicado;
- font_size aplicado com `LengthValue`;
- patch rejection/unapplied;
- ReviewItem;
- classification abstention;
- bindings de hash/ref;
- Decimal/None;
- Markdown hostil/backticks/newlines;
- tipo de valor inesperado;
- determinismo e imutabilidade;
- auditoria estática de autoridade/IO/clock/network/random/locale/LLM.

## Dívidas / fora de escopo

Permanecem fora:
- HTML/PDF/DOCX do relatório;
- multilíngue;
- localização física por página;
- recommendations/severity;
- filenames/download/delivery;
- inclusão do renderer no ProductOutputBundle congelado.

## Próximo passo

Fechar uma camada de **Product Delivery / File Naming v0.1** fora do core normativo, que transforme resultados já produzidos em artefatos de entrega com nomes determinísticos e, se útil, ZIP opcional. Essa camada não deve reprocessar DOCX nem introduzir verdade normativa.
