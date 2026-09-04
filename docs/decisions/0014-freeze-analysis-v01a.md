# 0014 — Freeze da Analysis View v0.1a — Normalized Text View

Status: **CONGELADA**

## Contexto

A decisão 0013 definiu o contrato da Analysis View v0.1a — Normalized Text View. A implementação foi desenvolvida na branch `analysis-v01a-normalized-text`, publicada no PR #2 e auditada adversarialmente pelo Kimi K3 sobre o código real do GitHub.

O PR #2 foi mergeado no `main` após auditoria e hardening.

- base auditada: `8c4a1ab46d15f753e617aa34b9e72ef429f9e775`
- head final auditado: `0e1c31ab04735aea7e9f2c688560172203e5e94c`
- merge commit: `88359be93f68a2ee664d16144f87ee7a3fdc9425`

## Validação final

Suíte completa executada pelo auditor externo sobre clone limpo do head remoto:

- **154 testes**
- **154 passes**
- **0 failures**
- **0 errors**
- **0 skips**

Os **102 testes congelados do parser v0.4** permaneceram verdes.

## Achados da auditoria e hardening

### 1. Opacos estruturais não podem desaparecer silenciosamente

A implementação inicial ignorava alguns `source_type` reais emitidos pelo parser v0.4, em especial:

- `opaque_paragraph_child`
- `non_element_paragraph_child`
- `opaque_container_child`

Isso permitia continuidade textual artificial entre conteúdos separados por estrutura opaca.

Correção fechada:

- esses nós passam a gerar `NormalizedSegment` `OPAQUE` zero-width com provenance física;
- nós desconhecidos com provenance suficiente geram `normalized_unexpected_fragment` + segmento opaco;
- nada relevante no fluxo físico do parágrafo pode desaparecer silenciosamente.

### 2. Break desconhecido não pode virar line break por aproximação

A implementação inicial tratava `w:br` desconhecido ou XML ilegível como line break.

Correção fechada:

- sem `w:type` ou `w:type="textWrapping"` => `LINE_BREAK` / `\n`;
- `page` => `PAGE_BREAK` estrutural zero-width;
- `column` => `COLUMN_BREAK` estrutural zero-width;
- tipo desconhecido ou `canonical_xml` ilegível => `OPAQUE` zero-width + warning `normalized_unknown_break_type`.

Assim, a Analysis View não inventa semântica textual quando a evidência física é insuficiente.

### 3. Testes end-to-end reais

Além dos testes unitários de contrato, foram adicionados testes:

`DOCX sintético -> DocxParser v0.4 -> PhysicalIR real -> normalize_paragraph`

Cobertura inclui:

- palavra fragmentada em runs;
- hyperlink;
- line/page/column break;
- `instrText`;
- tracked deletion / `delText`;
- `w:sym`;
- opaco entre conteúdos;
- table cell;
- footnote;
- header;
- comment;
- combining mark;
- emoji fora do BMP;
- regressões dos opacos e break desconhecido;
- não mutação da PhysicalIR real.

## Contrato congelado

### Unidade
Um parágrafo físico por `NormalizedParagraph`.

### Autoridade
`segments[]` é autoritativo. `default_text` é projeção derivada e reconstruível.

### Granularidade
Um segmento por fragmento físico representável, sem coalescência multi-source na v0.1a.

### Offsets
Offsets textuais são code points da `str` Python: start inclusivo, end exclusivo; não bytes UTF-8, UTF-16 units ou grapheme clusters. Segmentos não participantes são zero-width.

### Projeção padrão
- `text` -> literal;
- `tab` -> `\t`;
- line break -> `\n`;
- page/column break -> zero-width;
- carriage return -> `\r`;
- no-break hyphen -> U+2011;
- soft hyphen -> U+00AD;
- field/deleted/symbol/opaque -> zero-width.

### Symbols
`w:sym` não é convertido para Unicode, não usa U+FFFD, preserva `font` e `char` crus em metadata imutável e não entra em `default_text`.

### Imutabilidade
Os modelos analíticos são imutáveis e serializáveis, sem objetos lxml vivos. A normalização não modifica a PhysicalIR.

### Traversal
`children[]` da PhysicalIR é a única árvore autoritativa para traversal. Refs auxiliares não são percorridos como árvore paralela.

### Warnings analíticos
Warnings da Analysis View ficam separados dos warnings físicos do parser. Códigos relevantes da v0.1a:
- `normalized_unexpected_fragment`
- `normalized_unknown_break_type`

## Arquivos congelados
- `src/formatador_academico/analysis/__init__.py`
- `src/formatador_academico/analysis/model.py`
- `src/formatador_academico/analysis/normalized_text.py`
- `tests/test_analysis_normalized_text_v01a.py`
- `tests/test_analysis_normalized_text_v01a_e2e.py`

## Dívida aceita
`raw_text=""` em vez de `None` quando a chave textual está ausente em um fragmento textual manualmente malformado. O parser v0.4 real sempre fornece `text`; portanto não bloqueia o freeze.

## Regra de reabertura
A v0.1a só reabre por falha de teste, impossibilidade técnica demonstrada, contradição nova, mudança explícita de contrato/escopo ou novo risco de segurança.

## Próxima etapa
Abrir contrato e auditoria próprios para **Analysis View v0.1b — Formatting Resolution View**. A v0.1b não pode reabrir a v0.1a por conveniência arquitetural.
