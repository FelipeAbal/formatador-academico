# 0013 — Analysis View v0.1a: contrato da Normalized Text View

Status: **APROVADO PARA IMPLEMENTAÇÃO**

## Contexto

Após o congelamento formal do parser físico v0.4, a próxima camada do pipeline é a Analysis View. A auditoria arquitetural recomendou dividir a Analysis View em duas subetapas independentes:

1. **v0.1a — Normalized Text View**;
2. **v0.1b — Formatting Resolution View**.

Esta decisão fecha apenas a v0.1a. A v0.1b terá contrato e auditoria próprios.

A PhysicalIR/parser v0.4 permanece congelada e não é redesenhada por esta decisão.

## Objetivo

Construir uma visão textual derivada, determinística, serializável e imutável por parágrafo, capaz de recompor texto lógico contínuo a partir de fragments físicos sem destruir provenance nem alterar a PhysicalIR.

A v0.1a NÃO realiza:
- resolução de styles.xml;
- formatting efetivo;
- theme/font resolution;
- semantic classification;
- numbering;
- table styles;
- page/section resolution;
- patching;
- Safety Gate;
- regras de perfil acadêmico;
- coalescência multi-source;
- grapheme segmentation.

## Unidade de análise

A unidade inicial é **um parágrafo físico**.

Parágrafos em body, table cells, footnotes, endnotes, headers, footers e comments usam o mesmo mecanismo.

Não concatenar parágrafos, cells, tables ou stories nesta versão.

## Estrutura autoritativa

`segments[]` é a fonte da verdade.

`default_text` é apenas projeção derivada, recomposta deterministicamente dos segmentos participantes.

Não usar `text + source_map[]` como estruturas paralelas autoritativas.

## Um segmento por fragmento físico

Na v0.1a, cada fragmento físico representável gera no máximo um `NormalizedSegment`.

Não coalescer múltiplos fragments em um único segmento multi-source.

Exemplo:

- fragmento 1: `Com`
- fragmento 2: `pra`
- fragmento 3: ` sem`
- fragmento 4: `ântica`

=> quatro segmentos; `default_text == "Compra semântica"`.

A coalescência, se necessária no futuro, será view derivada posterior e não altera o contrato de provenance da v0.1a.

## Schema mínimo

### SegmentKind

Valores fechados da v0.1a:
- `TEXT`
- `TAB`
- `LINE_BREAK`
- `PAGE_BREAK`
- `COLUMN_BREAK`
- `CARRIAGE_RETURN`
- `NO_BREAK_HYPHEN`
- `SOFT_HYPHEN`
- `SYMBOL`
- `FIELD_CODE`
- `DELETED_TEXT`
- `OPAQUE`

### TextRole

Valores fechados:
- `CONTENT`
- `DELETED`
- `FIELD_INTERNAL`
- `STRUCTURAL`
- `OPAQUE`

### SourceAnchor

Campos mínimos:

```text
story_id
part
structural_path
physical_hash
fragment_type
source_start
source_end
```

`structural_path` aponta para o fragmento físico na PhysicalIR.

`source_start` inclusivo e `source_end` exclusivo são offsets em **code points da `str` Python do texto físico/raw do fragmento**, nunca bytes UTF-8, UTF-16 code units ou grapheme clusters.

### NormalizedSegment

Campos mínimos:

```text
segment_kind
text_role
raw_text?
projected_text?
logical_start
logical_end
contributes_to_default_text
source
metadata?
```

`raw_text` preserva texto textual existente no fragmento quando aplicável.

`projected_text` é o texto que contribui para `default_text`; é `None` para não-participantes.

`metadata` é usado apenas quando necessário para preservar informação física que não cabe nos campos principais, por exemplo `w:sym` com `font` e `char` crus.

### NormalizedParagraph

Campos mínimos:

```text
paragraph_path
paragraph_hash
segments
 default_text
has_non_content
analysis_warnings
```

`default_text` é derivado de `segments[]`.

## Contrato de offsets

`logical_start` e `logical_end` são índices sobre a sequência de code points da `str` Python que forma `default_text`:

- start inclusivo;
- end exclusivo;
- combining marks contam separadamente;
- emoji fora do BMP conta como um code point na `str` Python;
- não usar grapheme clusters.

Segmentos que não participam de `default_text` são **zero-width**:

```text
logical_start == logical_end
```

A ordem desses segmentos permanece preservada pela ordem em `segments[]`.

## Política de default_text

`default_text` é a concatenação, em ordem física, de `projected_text` dos segmentos com `contributes_to_default_text = true`.

### Mapeamento fechado v0.1a

| fragment_type físico | SegmentKind | TextRole | participa? | projected_text |
|---|---|---|---|---|
| `text` | `TEXT` | `CONTENT` | sim | texto literal |
| `tab` | `TAB` | `CONTENT` | sim | `\t` |
| `break` sem type | `LINE_BREAK` | `CONTENT` | sim | `\n` |
| `break` type=page | `PAGE_BREAK` | `STRUCTURAL` | não | `None` |
| `break` type=column | `COLUMN_BREAK` | `STRUCTURAL` | não | `None` |
| `carriage_return` | `CARRIAGE_RETURN` | `CONTENT` | sim | `\r` |
| `no_break_hyphen` | `NO_BREAK_HYPHEN` | `CONTENT` | sim | U+2011 |
| `soft_hyphen` | `SOFT_HYPHEN` | `CONTENT` | sim | U+00AD |
| `symbol` | `SYMBOL` | `OPAQUE` | não | `None` |
| `instruction_text` | `FIELD_CODE` | `FIELD_INTERNAL` | não | `None` |
| `deleted_text` | `DELETED_TEXT` | `DELETED` | não | `None` |
| opaque fragment | `OPAQUE` | `OPAQUE` | não | `None` |
| non-element fragment | `OPAQUE` | `OPAQUE` | não | `None` |

## Deleted text

`w:delText` é preservado como:

- `segment_kind = DELETED_TEXT`;
- `text_role = DELETED`;
- `raw_text = conteúdo físico`;
- `projected_text = None`;
- `contributes_to_default_text = false`;
- zero-width.

O conteúdo deletado não é perdido. Uma projeção futura poderá produzir texto com revisões.

## Field code

`w:instrText` é preservado como:

- `segment_kind = FIELD_CODE`;
- `text_role = FIELD_INTERNAL`;
- `raw_text = conteúdo físico`;
- `projected_text = None`;
- zero-width.

Nenhum placeholder textual é introduzido.

## Symbols

Na v0.1a, `w:sym` NÃO é convertido para Unicode.

Preservar em metadata:
- `font` cru;
- `char` cru.

O segmento é `SYMBOL`, não participa de `default_text` e é zero-width.

É expressamente proibido usar U+FFFD como substituto, pois isso inventaria conteúdo inexistente no documento.

## Empty runs e empty paragraphs

Run sem fragmentos não gera segmento artificial.

O run continua integralmente presente na PhysicalIR.

Parágrafo vazio é válido e produz:

```text
segments = ()
default_text = ""
```

Sem warning obrigatório apenas por estar vazio.

## Containers e ancestry

O `structural_path` do fragmento já contém hierarquia física de containers, por exemplo hyperlink/run containers.

Não adicionar `container_path` único.

`ancestor_context[]` e protection context ficam fora da v0.1a e podem ser adicionados posteriormente como dados derivados sem mudar o SourceAnchor.

## Identidade

Não criar `analysis_id` nem `span_id` na v0.1a.

Origem física é identificada pelo compound target do SourceAnchor; a posição do segmento em `segments[]` preserva sua posição analítica.

## Warnings

Warnings da Analysis View são separados de `parse_warnings`.

Warning mínimo obrigatório:

- `normalized_unexpected_fragment`: fragment type físico não reconhecido pela tabela fechada da v0.1a; comportamento = `warn + opaque`.

Não emitir warning apenas por parágrafo vazio.

## Falha parcial

Fragmento não compreendido não derruba o parágrafo:

- gerar `OPAQUE` zero-width;
- emitir `normalized_unexpected_fragment`;
- continuar os demais segmentos.

Falha completa da normalização só é aceitável quando a PhysicalIR entregue viola invariantes físicos necessários à provenance de forma que torne impossível construir âncoras confiáveis.

## Imutabilidade e determinismo

A Normalized Text View deve ser:
- derivada;
- descartável/reconstruível;
- serializável;
- determinística;
- sem objetos lxml vivos;
- incapaz de modificar a PhysicalIR.

Mesma PhysicalIR + mesma versão de Analysis View => mesma saída serializada.

## Invariantes v0.1a

1. `segments[]` é autoritativo.
2. Cada segmento aponta para um fragmento físico existente.
3. Nenhum fragmento é convertido em conteúdo textual não autorizado pela tabela fechada.
4. Segmento não participante é zero-width.
5. Offsets lógicos são monotônicos e em code points.
6. Participantes consecutivos são contíguos na projeção.
7. Concatenação dos `projected_text` participantes é exatamente `default_text`.
8. Normalização não altera a PhysicalIR.
9. `w:sym` não inventa caractere substituto.
10. Fragment type desconhecido => `warn + opaque`, nunca invenção silenciosa.

## Testes mínimos

A implementação deve cobrir pelo menos:

1. 1 run / 1 text;
2. vários runs com palavra fragmentada;
3. run vazio;
4. parágrafo vazio;
5. hyperlink com vários runs;
6. containers de run aninhados;
7. tab;
8. line break;
9. page break zero-width;
10. column break zero-width;
11. carriage return;
12. soft hyphen;
13. no-break hyphen;
14. field code entre conteúdos;
15. deleted text entre conteúdos;
16. opaque fragment entre conteúdos;
17. dois zero-width consecutivos;
18. symbol cru/zero-width;
19. combining mark;
20. emoji fora BMP;
21. parágrafo em table cell;
22. parágrafo em footnote;
23. parágrafo em header;
24. parágrafo em comment;
25. determinismo same-input;
26. PhysicalIR não modificada;
27. SourceAnchor aponta para fragmento físico existente;
28. monotonicidade dos offsets;
29. participantes contíguos;
30. concatenação de participantes == `default_text`;
31. fragment type desconhecido => warning + opaque.

## Próxima etapa

Implementar apenas a **Normalized Text View v0.1a** contra o parser físico v0.4 congelado.

Depois:
1. auditoria adversarial da implementação v0.1a;
2. hardening e freeze;
3. abrir contrato próprio para **v0.1b — Formatting Resolution View**.
