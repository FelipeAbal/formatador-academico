# 0015 — Analysis View v0.1b: Formatting Resolution View

## Status

**APROVADO PARA IMPLEMENTAÇÃO EM DOIS MARCOS INTERNOS**

Contrato arquitetural auditado pelo Kimi K3 e corrigido antes do fechamento após verificação normativa das propriedades toggle do WordprocessingML.

Esta decisão NÃO implementa código e NÃO reabre o parser v0.4 nem a Analysis View v0.1a.

---

## Objetivo

Definir uma view analítica, documental, determinística e somente leitura capaz de resolver propriedades efetivas de formatação a partir da PhysicalIR + recursos documentais de estilo, sem aplicar normas acadêmicas e sem autorizar mutações.

Fluxo relevante:

`OriginalPackage imutável -> PhysicalIR -> Analysis View v0.1b -> classificação/decisão -> OperationPlan -> SafetyGate -> patches`

A v0.1b responde a fatos documentais como:
- tamanho efetivo do run;
- alinhamento documental do parágrafo;
- origem do negrito/itálico;
- cadeia de evidência de uma propriedade.

Ela NÃO responde:
- se a formatação está correta;
- qual formatação deveria ser aplicada;
- se o trecho pode ser alterado;
- layout/paginação/renderização visual.

---

## Fronteira com PhysicalIR

- `word/styles.xml` NÃO passa a fazer parte da PhysicalIR.
- O parser v0.4 permanece congelado.
- `StyleCatalog` é derivado diretamente dos bytes imutáveis do `OriginalPackage`.
- A integridade do part deve ser conferida por `part_name + sha256` contra o inventário físico já registrado pela PhysicalIR.
- O catálogo vive na camada `analysis/`, é imutável, serializável, determinístico e não retém objetos lxml vivos.

A leitura analítica de `styles.xml` não constitui nova PhysicalIR e não é usada pelo patcher como fonte de identidade física.

---

## Implementação em dois marcos internos

A v0.1b é um contrato único, implementado em dois marcos sem criar nova versão pública.

### Marco 1
- `RawPropertyBag`;
- `StyleCatalog`;
- `docDefaults`;
- cascade de parágrafo;
- propriedades de run não-toggle;
- provenance/evidence;
- statuses;
- serialização determinística;
- testes unitários e end-to-end.

### Marco 2
- `w:b` e `w:i` com semântica toggle correta;
- vetores de regressão específicos para composição de styles vs direct formatting.

O schema público já deve acomodar toggle desde o Marco 1.

---

## StyleCatalog mínimo

```text
StyleCatalog:
    part_name
    part_sha256
    doc_defaults
    styles
    catalog_warnings

StyleEntry:
    style_id
    style_type
    is_default
    custom_style
    based_on_id
    link_id
    name
    ppr_bag
    rpr_bag
    structural_path
    physical_hash

DocDefaults:
    rpr_bag
    ppr_bag
```

### Fora do catálogo inicial
- `latentStyles`;
- `aliases`;
- `uiPriority`;
- `qFormat`;
- `semiHidden`;
- `rsid`;
- `next`;
- `autoRedefine`.

`w:link` é preservado como fato documental, mas NÃO participa da cascade. Um character style ligado por `w:link` só participa da resolução se for normalmente referenciado por `rStyle`.

Se `styles.xml` não existir: catálogo vazio válido, sem warning.

Se `styles.xml` estiver ilegível: catálogo degradado com `formatting_styles_part_unreadable`; direct formatting continua resolvível, e somente propriedades que dependem de styles/docDefaults degradam.

---

## RawPropertyBag

Único ponto da v0.1b que interpreta XML de `properties_raw`/pPr/rPr.

```text
RawPropertyBag:
    source_anchor
    entries

RawProperty:
    property_name
    raw_attrs
    canonical_xml
    structural_path
```

Requisitos:
- parsing XML local endurecido;
- `resolve_entities=False`;
- `no_network=True`;
- `recover=False`;
- saída sem lxml vivo;
- ordem documental preservada;
- duplicatas detectadas no bag.

---

## ResolvedValue

```text
ResolvedValue[T]:
    status
    value
    winning_evidence
    evidence_chain
    reason
```

### Status fechado

1. `resolved`
   - valor determinado documentalmente.

2. `absent`
   - cascade completa percorrida e nenhuma fonte aplicável declarou a propriedade.
   - não injeta defaults da aplicação/Word.

3. `unresolved`
   - existe dependência documental relevante que a v0.1b deliberadamente não resolve, por exemplo numbering necessário para indent.

4. `invalid`
   - declaração presente com valor lexical malformado.
   - terminal para aquela propriedade/slot: não deixar nível inferior vencer silenciosamente.

5. `ambiguous`
   - somente para conflito documental sem precedência normativa segura.

### Casos legítimos de ambiguous
- propriedade duplicada com valores conflitantes no mesmo container;
- `style_id` duplicado quando efetivamente relevante à resolução;
- múltiplos default styles do mesmo tipo quando efetivamente necessários.

Duplicata com valores idênticos: `resolved` + warning de duplicidade.

Anomalia não exercitada por uma resolução não contamina seu status.

---

## Evidence / provenance

```text
FormattingEvidence:
    source_kind
    part
    structural_path
    style_id
    property_name
    raw_value

LevelEvidence:
    level
    declared
    detail
    evidence
```

`ResolvedValue` mantém:
- `winning_evidence`;
- `evidence_chain` completa, em ordem determinística.

Objetivo: explicar de onde veio cada valor sem depender de reinterpretação posterior.

---

## Paragraph cascade

Para propriedades de parágrafo, sem numbering completo:

1. direct `pPr`;
2. paragraph style referenciado/default, incluindo sua cadeia `basedOn` válida;
3. `docDefaults/pPrDefault`.

Dentro de style chains, percorre-se do style mais específico em direção aos ancestrais para propriedades não-toggle, usando a primeira declaração válida encontrada.

### Default paragraph style
- usado apenas quando não há `pStyle` válido explicitamente aplicado;
- nenhum default: situação legítima, sem warning;
- múltiplos defaults relevantes: `ambiguous`.

---

## Run cascade — propriedades não-toggle

Para propriedades de run não-toggle:

1. direct `rPr`;
2. character style (`rStyle`) + cadeia `basedOn`;
3. paragraph style (`pStyle`) `rPr` + cadeia `basedOn`;
4. `docDefaults/rPrDefault`.

Cada cadeia `basedOn` pertence ao seu próprio nível; `basedOn` não é um nível global separado.

---

## Toggle properties: `w:b` e `w:i`

Esta decisão distingue obrigatoriamente dois contextos.

### A. STYLE HIERARCHY COMPOSITION

Dentro de definições de style e `docDefaults`:
- `true`, `1` ou atributo omitido: **toggle** do estado acumulado;
- `false` ou `0`: **não altera** o estado acumulado;
- ausente: herda estado anterior.

A composição percorre do menos específico ao mais específico:

```text
estado inicial false
-> docDefaults/rPrDefault
-> paragraph style chain da raiz ao style mais específico
-> character style chain da raiz ao style mais específico
```

### B. DIRECT FORMATTING OVERRIDE

No `w:rPr` direto do run:
- `true`, `1` ou omitido: valor absoluto `true`;
- `false` ou `0`: valor absoluto `false`;
- declaração direct é terminal para a propriedade;
- direct formatting NÃO participa de paridade/toggle.

### Pseudocódigo contratual

```text
resolve_toggle(property, run, paragraph_context, catalog):

    if direct rPr declares property:
        if lexical invalid:
            return invalid(direct evidence)
        return resolved(absolute boolean from direct)

    state = false
    declared_any = false

    for level in style_hierarchy_from_least_to_most_specific:
        if level declares property:
            declared_any = true
            if lexical invalid:
                return invalid(level evidence)
            if lexical is true/1/omitted:
                state = not state
            if lexical is false/0:
                state unchanged

    if not declared_any:
        return absent

    return resolved(state)
```

### Vetores mínimos obrigatórios
- docDefaults on -> true;
- style on -> true;
- basedOn parent on + child on -> false;
- parent on + child false -> true;
- paragraph style on + character style on -> false;
- paragraph style on + character style false -> true;
- docDefaults on + paragraph style on -> false;
- docDefaults on + paragraph + character on -> true;
- style on + direct on -> **true**;
- style on + direct false -> false;
- direct on sem styles -> true;
- direct inválido -> invalid;
- tudo ausente -> absent.

Somente `b` e `i` entram na primeira versão. Outros toggles ficam fora.

---

## docDefaults

Entram na v0.1b inicial.

- `pPrDefault` = base da cascade de paragraph formatting.
- `rPrDefault` = base da cascade de run formatting.
- para toggle, `rPrDefault` participa da style hierarchy composition, não como direct formatting.
- application/renderer defaults não são modelados.

---

## basedOn, referências quebradas e tipos incompatíveis

### style diretamente referenciado inexistente
`pStyle`/`rStyle` apontando para id inexistente:
- referência ignorada conforme comportamento documental determinístico;
- warning `formatting_missing_style`;
- cascade continua;
- não gerar `unresolved` apenas por isso.

### basedOn inexistente
- parent inválido ignorado;
- style atual torna-se efetivamente raiz daquela cadeia;
- warning `formatting_missing_style`;
- cascade continua.

### tipo incompatível
- referência inválida ignorada;
- warning `formatting_wrong_style_type`;
- cascade continua;
- não gerar `unresolved` apenas por isso.

### cycle
- detectar iterativamente com visited set;
- sem recursão infinita;
- membros do ciclo não podem produzir resolução inventada;
- propriedade dependente exclusivamente do ciclo fica `unresolved(reason=style_cycle)`;
- warning `formatting_style_cycle`.

---

## Duplicate style_id

Não existe regra contratual `first wins`.

- duplicidade sempre gera `formatting_duplicate_style_id` no catálogo;
- se id duplicado não for usado na resolução: sem efeito no status daquela propriedade;
- se id duplicado for necessário: `ambiguous`, com todas as definições relevantes em evidence.

---

## Numbering ↔ indentation

Numbering completo continua fora da v0.1b inicial, mas `w:numPr` pode afetar indentação.

Para cada slot de indent relevante (`left`, `start`, `right`, `end`, `firstLine`, `hanging`):

1. se direct pPr declara o slot -> `resolved` direct;
2. senão, se paragraph style chain declara o slot em fonte que tem precedência sobre numbering -> `resolved` pelo style;
3. senão, se `numPr` relevante está presente e o slot pode depender de `numbering.xml` -> `unresolved(reason=numbering_indent_unsupported)` + `formatting_numbering_present`;
4. senão, seguir `docDefaults`/`absent` normalmente.

O warning só é emitido quando uma propriedade concreta materializa a dependência não resolvida; mera presença de `numPr` não gera ruído global.

---

## Propriedades de run — primeira fatia

### Marco 1
- font size `w:sz`;
- font specification `w:rFonts`;
- language `w:lang`;
- underline `w:u`;
- vertical alignment `w:vertAlign`.

### Marco 2
- bold `w:b`;
- italic `w:i`.

### Fora inicialmente
- `szCs`, `bCs`, `iCs`;
- color/highlight;
- borders;
- kerning;
- caps/smallCaps;
- strike/dstrike;
- character spacing;
- hidden text;
- demais propriedades de run.

---

## Font specification

Não produzir `effective_font` visual.

Modelar slots documentalmente:
- ascii;
- hAnsi;
- eastAsia;
- cs;
- asciiTheme;
- hAnsiTheme;
- eastAsiaTheme;
- csTheme.

Cada slot é resolvido independentemente, com provenance própria.

Theme refs são valores documentais válidos:

```text
status = resolved
value = ThemeRef(...)
```

Não gerar `unresolved` só porque `theme1.xml` não é resolvido nesta versão.

`theme1.xml` fica fora da v0.1b inicial.

---

## Language

`w:lang` entra com slots independentes:
- `val`;
- `eastAsia`;
- `bidi`.

Valores lexicais são preservados; sem inferência de script/rendering.

---

## Underline

`w:u` não é boolean.

- atributo omitido em `<w:u/>` => valor documental `single`;
- tokens conhecidos ou futuros são preservados lexicalmente;
- token desconhecido não vira `invalid` apenas por não estar em enum local fechado.

Princípio geral: não reduzir agressivamente enums OOXML.

---

## Vertical alignment

`w:vertAlign` preserva valor lexical documental, incluindo:
- baseline;
- superscript;
- subscript.

Token desconhecido permanece documentalmente resolvido se lexicalmente válido como token; a v0.1b não valida contra enum fechado local desatualizável.

---

## Units

### Font size
`w:sz` em half-points:
- raw lexical preservado;
- valor normalizado em `Decimal`;
- `24 -> Decimal("12") pt`.

### Twips/dxa
- converter exatamente para `Decimal` em pt quando semântica da unidade for inequívoca;
- raw lexical e raw unit permanecem em evidence.

### Regras
- nunca usar float;
- Decimal serializado como string em JSON determinístico;
- não usar `Fraction` sem necessidade.

---

## Paragraph properties — primeira fatia

- paragraph style id;
- alignment `w:jc`;
- spacing `w:spacing`;
- indents `w:ind`.

### Alignment
Preservar token OOXML cru (`left`, `right`, `center`, `both`, `start`, `end`, `distribute`, etc.).

Não criar `normalized_alignment` dependente de bidi.

### Spacing
Modelar como spec, não número simplificado:
- line;
- lineRule;
- before;
- after;
- beforeLines;
- afterLines.

`lineRule=auto` -> múltiplo de linha quando valor estiver em 240ths de linha.
`exact`/`atLeast` -> twips para pt.
`beforeLines`/`afterLines` permanecem em centésimos de linha.
`beforeAutospacing`/`afterAutospacing` relevantes -> slot `unresolved(reason=autospacing_unsupported)`.

### Indents
Resolver slots independentemente:
- left/right/firstLine/hanging em twips->pt;
- start/end preservados como slots próprios, sem mapear para left/right;
- `*Chars` -> `unresolved(reason=unsupported_unit)` para o slot correspondente.

### Fora inicialmente
- keepNext;
- keepLines;
- widowControl;
- contextualSpacing;
- tabs;
- borders;
- shading;
- numbering completo;
- outline level.

---

## Unidade de resolução

- paragraph formatting por target físico de paragraph;
- run formatting por target físico de `run_raw`;
- NÃO duplicar formatting por `NormalizedSegment`.

Associação futura segment -> run é derivada pelo `structural_path` físico.

---

## Relação com v0.1a

As views permanecem ortogonais:

- v0.1a consome PhysicalIR;
- v0.1b consome PhysicalIR + StyleCatalog/OriginalPackage;
- uma não importa a outra;
- combinação futura é terceira view derivada.

---

## Falha parcial

Invariante: unidade de falha = `(target, propriedade)` ou `(target, slot)`.

Exemplo válido:
- font theme slot resolved como ThemeRef;
- font size resolved;
- indent unresolved por numbering;
- bold resolved.

Uma propriedade problemática nunca derruba o run/parágrafo inteiro.

Conteúdo documental ruim não deve produzir exceção global, salvo violação estrutural do próprio contrato de entrada.

---

## Warnings mínimos

1. `formatting_missing_style`
2. `formatting_style_cycle`
3. `formatting_invalid_value`
4. `formatting_duplicate_property`
5. `formatting_wrong_style_type`
6. `formatting_multiple_default_styles`
7. `formatting_duplicate_style_id`
8. `formatting_numbering_present`
9. `formatting_styles_part_unreadable`

Não existe `formatting_unsupported_theme_resolution` nesta versão.

---

## Determinismo e serialização

- dataclasses/estruturas finais imutáveis;
- tuples, não lists mutáveis, nas saídas;
- nenhum lxml vivo;
- order de styles = document order;
- evidence chain em ordem contratual estável;
- JSON determinístico com keys ordenadas e separators fixos;
- Decimal serializado como string;
- mesma entrada -> mesmos bytes;
- teste cross-process/hashseed obrigatório.

---

## Cache

Não implementar agora.

Chave futura pode usar:
- `package_sha256`;
- `parser_version`;
- `analysis_formatting_version`.

Perfil acadêmico NÃO participa da chave desta view documental.

---

## Fora de escopo da v0.1b inicial

- renderer/layout visual;
- paginação;
- line wrapping;
- fontes instaladas/substituição de fontes pelo SO/Word;
- theme resolution real;
- numbering completo;
- table styles/conditional formatting;
- section/page/margins;
- color/highlight/borders;
- complex-script run resolution;
- proteção/autorização de edição;
- SafetyGate;
- perfil acadêmico;
- patching;
- qualquer decisão de correção normativa.

---

## Testes mínimos obrigatórios

### StyleCatalog / PropertyBag
- styles.xml ausente;
- styles.xml ilegível;
- style simples paragraph/character;
- docDefaults only;
- basedOn chain;
- missing parent;
- wrong type;
- cycle;
- duplicate style id;
- multiple defaults;
- duplicate property idêntica/conflitante.

### Run
- direct size;
- style size;
- direct override;
- docDefaults;
- character style;
- paragraph style rPr;
- basedOn;
- underline;
- vertAlign;
- font slots;
- theme ref;
- lang slots;
- invalid lexical.

### Toggle Marco 2
Cobrir todos os vetores definidos na seção de toggle, especialmente:
- parent on + child false -> true;
- style on + direct on -> true;
- style on + direct false -> false.

### Paragraph
- direct/style/default alignment;
- spacing specs;
- indents;
- numbering-indentation casos A/B/C;
- `*Chars` unsupported;
- autospacing unsupported.

### Robustez
- falha parcial;
- determinismo;
- cross-process/hashseed;
- PhysicalIR não modificada;
- OriginalPackage/bytes não modificados;
- nenhuma referência lxml viva;
- body/table/footnote/header/comment.

---

## Reabertura

Esta decisão só reabre por:
- falha de teste;
- impossibilidade técnica demonstrada;
- contradição normativa nova;
- mudança explícita de escopo/contrato;
- novo risco de segurança.

---

## Próximo passo

Implementar SOMENTE o **Marco 1 da v0.1b** em branch própria, começando por:

1. modelos públicos (`ResolvedValue`, evidence, specs);
2. `RawPropertyBag`;
3. `StyleCatalog` + `docDefaults`;
4. cascade de parágrafo;
5. run properties não-toggle;
6. serialização determinística;
7. suíte de testes e regressão integral dos 154 testes congelados.

O Marco 2 (`w:b`/`w:i`) só começa depois da revisão adversarial do Marco 1.
