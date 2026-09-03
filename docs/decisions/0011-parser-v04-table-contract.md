# Decisão 0011 — Contrato do parser v0.4: decomposição física segura de tabelas

## Contexto

A v0.3 do parser foi formalmente congelada após revalidação externa com 56/56 testes aprovados. A próxima fronteira da PhysicalIR é a decomposição de `w:tbl`.

O contrato da v0.4 foi submetido a auditoria do Kimi K3. Veredito: **APROVAR COM AJUSTES**.

Os ajustes são todos internos ao escopo da v0.4 e entram antes da implementação.

## Objetivo

Decompor fisicamente tabelas WordprocessingML mantendo o parser estritamente forense:

`table -> row -> cell -> blocks`

Sem resolver layout, merges, grid lógico, estilos efetivos, semântica acadêmica ou qualquer transformação.

## Modelo autoritativo

### Table

- `source_type = table`
- campos físicos congelados da v0.3 permanecem estáveis:
  - `id`
  - `canonical_xml`
  - `physical_hash`
  - `structural_path`
  - `original_index`
  - `source_type`
- `properties_raw` consome o primeiro `w:tblPr`;
- `grid_raw` consome o primeiro `w:tblGrid`;
- `children[]` é a árvore autoritativa para os demais filhos, preservando ordem física;
- `row_refs[]` e quaisquer views auxiliares, se existirem, contêm apenas `structural_path`, nunca cópias.

`w:tblPr` duplicado vira opaco protegido + `duplicate_table_properties`.
`w:tblGrid` duplicado vira opaco protegido + `duplicate_table_grid`.

### Row

- `source_type = table_row`;
- `properties_raw` consome o primeiro `w:trPr`;
- `children[]` autoritativo contém cells e opacos na ordem física;
- `cell_refs[]` opcional, apenas paths.

`w:trPr` duplicado vira opaco protegido + `duplicate_row_properties`.

Wrappers de row/cell, inclusive tracked changes/SDT/customXml que envolvam células, permanecem opacos protegidos na v0.4. Isso é limitação conhecida e não implica interpretação.

### Cell

- `source_type = table_cell`;
- `properties_raw` consome o primeiro `w:tcPr`;
- `children[]` autoritativo representa a sequência física interna;
- parágrafos e tabelas usam o mesmo parser de blocos já estabilizado;
- tabela aninhada é decomposta recursivamente;
- `block_refs[]` opcional, apenas paths.

`w:tcPr` duplicado vira opaco protegido + `duplicate_cell_properties`.

Célula sem parágrafo é válida para o parser físico: não inserir conteúdo e não gerar warning apenas por estar vazia.

## `tblGrid`

`grid_raw` preserva o `canonical_xml` integral de `w:tblGrid` e decompõe fisicamente `w:gridCol[]`.

Cada `gridCol` mantém atributos crus como strings. Não interpretar largura.

- grid ausente -> `grid_raw = null`;
- grid vazio -> `grid_cols = []`;
- divergência entre grid e células físicas -> preservar sem validar ou corrigir.

## Merges e propriedades estruturais

`gridSpan`, `vMerge`, `gridBefore`, `gridAfter`, larguras e demais propriedades permanecem dentro de `tcPr`/`trPr`/`tblPr` crus.

O parser NÃO:
- valida `gridSpan`/`vMerge`;
- cria células virtuais;
- calcula colspan/rowspan;
- resolve coordenadas visuais;
- compara grid declarado com estrutura física.

Mesmo valores inválidos permanecem crus sem warning de validação. Validação pertence à futura Analysis View.

## Block containers — ajuste obrigatório

A v0.4 introduz `block_container`, análogo ao `run_container`, para wrappers de nível de bloco que carregam conteúdo substantivo em sequência:

- `w:sdt`;
- `w:sdtContent`;
- `w:customXml`.

Contrato:
- preservar `canonical_xml` integral;
- `protected = true`;
- warning `unparsed_block_container`;
- `children[]` decompostos recursivamente pelo mesmo dispatch de blocos;
- ordem física preservada;
- aplicar em células e também no dispatch compartilhado do body/stories.

Essa mudança é aditiva da v0.4 e fecha uma limitação conhecida da v0.3 sem alterar a identidade física dos blocos existentes.

## IDs de blocos aninhados

O formato histórico `{story_id}/block-NNNNNN` é garantido apenas para a sequência raiz de cada story/item.

Blocos aninhados em célula ou `block_container` NÃO recebem ids sequenciais que possam colidir.

Identidade de blocos aninhados é dada por:

`part + story_id + structural_path + original_index + physical_hash`

O `structural_path` é a âncora física para nested blocks.

## Structural path

A convenção é estendida explicitamente para `tbl/tr/tc` e block containers.

Exemplo:

`/w:document/w:body[1]/w:tbl[2]/w:tr[3]/w:tc[1]/w:p[2]`

Não achatar paths. O patcher futuro deve endereçar `part + structural_path`.

## Limite estrutural

`ParserLimits` passa a incluir `max_structural_depth`, default 64.

Esse limite vale para recursão estrutural de:
- tabelas aninhadas;
- block containers;
- combinações entre ambos.

Ao atingir o limite:
- não aprofundar;
- preservar o subtree integral como opaco protegido;
- warning `max_depth_exceeded`;
- nunca deixar `RecursionError` escapar por input profundo.

O limite de profundidade é contenção estrutural. Limites de ZIP continuam globais e fatais conforme decisão 0009.

## Tracked changes

- `tblPrChange`, `trPrChange`, `tcPrChange` permanecem dentro de `properties_raw`;
- wrappers de row/cell por tracked changes permanecem opacos protegidos;
- nenhuma resolução de revisão é feita na v0.4.

## Mixed content e textboxes

`mixed_content_text` aplica-se a `w:tbl`, `w:tr`, `w:tc` e block containers.

A detecção existente de textboxes/text bodies deve continuar funcionando em tabelas, células, nested tables e stories secundárias:
- `w:txbxContent`;
- `a:txBody`;
- `p:txBody`.

Textboxes continuam opacos.

## Cobertura 1:1

Obrigatório testar por multiconjunto de `structural_path`, com cálculo independente:

- cada filho de `w:tbl` exatamente uma representação;
- cada filho de `w:tr` exatamente uma representação;
- cada filho de `w:tc` exatamente uma representação.

Slots nomeados (`properties_raw`, `grid_raw`) consomem o nó físico. `children[]` carrega o restante. Nenhum nó pode aparecer em dois lugares como fonte autoritativa.

## Regressão v0.3 -> v0.4

Para bloco `table`, permanecer byte-idêntico nos campos:
- `id` (quando raiz);
- `canonical_xml`;
- `physical_hash`;
- `structural_path`;
- `original_index`;
- `source_type`.

O warning genérico `unparsed_children` para tabela desaparece quando a decomposição é bem-sucedida.

Blocos não-tabela devem manter comportamento congelado, exceto pela nova decomposição aditiva de `block_container`.

## Escopo explicitamente fora

- layout visual;
- merge resolvido;
- grid lógico;
- largura efetiva;
- repeat header;
- autofit;
- estilos/propriedades/borders/shading efetivos;
- direção textual efetiva;
- semântica acadêmica;
- conversão de tabela em texto;
- patching/escrita;
- decomposição de textboxes;
- validação estrutural de grid/merge.

## Estado esperado após v0.4

Com tabelas decompostas, a PhysicalIR é considerada suficientemente completa para iniciar a Analysis View, mantendo duas limitações conhecidas e sinalizadas:

1. textboxes continuam opacos detectados;
2. wrappers em nível de row/cell podem continuar opacos protegidos.

Próxima etapa candidata após congelamento da v0.4: **Analysis View v0.1**, começando por visão normalizada de runs com mapa de offsets e resolução de formatação com proveniência.
