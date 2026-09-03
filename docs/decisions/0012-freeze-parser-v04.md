# Decisão 0012 — Congelamento formal do parser v0.4

## Contexto

A v0.4 implementou a decomposição física segura de tabelas conforme a decisão 0011, incluindo `block_container`, tabelas aninhadas e limite estrutural de profundidade.

A implementação foi auditada adversarialmente pelo Kimi K3. O primeiro passe encontrou dois achados menores, ambos corrigidos antes do congelamento:

1. `w:tcPr` duplicado passou a usar `source_type = "opaque_cell_child"`, mantendo `protected = true` e warning `duplicate_cell_properties`.
2. `block_refs[]` em cells e block containers passou a referenciar somente blocos estruturais (`paragraph`, `table`, `block_container`), enquanto `children[]` continua autoritativo e preserva todos os filhos em ordem física.

Na revisão pré-merge do PR #1 foram encontrados três problemas de qualidade de testes, também corrigidos antes do merge:

- `test_warnings_are_story_scoped` estava parcialmente comentado e foi refeito para executar parse e asserção reais;
- `test_20_depth_exceeded_degrades_locally` continha uma asserção tautológica e passou a procurar efetivamente `depth_limited = true` na árvore;
- um teste sem asserções e duplicado foi removido.

## Resultado final da suíte

Suíte completa validada no workspace externo do Kimi K3:

- **102 testes executados**;
- **102 passes**;
- **0 failures**;
- **0 errors**;
- **0 skips**.

O PR #1 foi revisado e mergeado no `main`.

Merge commit:

`10b8ca39c4fa2cef7e2f0638a63cc8683926f691`

## Estado congelado da v0.4

Versão do parser:

`0.4.0`

A PhysicalIR passa a representar de forma física e endereçável:

- package/ZIP/OPC;
- body;
- paragraphs;
- runs;
- run containers;
- fragments;
- block containers;
- tables, rows e cells;
- nested tables;
- `tblPr`, `trPr`, `tcPr` crus;
- `tblGrid` e `gridCol` crus;
- footnotes;
- endnotes;
- headers;
- footers;
- comments;
- stories ausentes, órfãs, falhadas e rejeitadas;
- parse parcial;
- textboxes detectados e preservados como opacos.

## Garantias preservadas

Continuam válidas as garantias G1–G7 e decisões anteriores:

- OriginalPackage imutável;
- OOXML + lxml como camada física autoritativa;
- nenhuma reconstrução do DOCX pela IR;
- nenhuma interpretação acadêmica no parser;
- `children[]` autoritativo;
- refs auxiliares por `structural_path`;
- identidade física composta por `part + story_id + structural_path + original_index + physical_hash`;
- conteúdo não compreendido preservado/protegido;
- warnings versionados;
- determinismo;
- limite estrutural com degradação local em vez de `RecursionError`.

## Fora do parser congelado

Permanecem fora do escopo:

- resolução lógica/visual de merges;
- grid visual;
- largura efetiva;
- layout;
- estilo efetivo;
- semântica acadêmica;
- patching/escrita;
- decomposição de textboxes.

## Regra de reabertura

A v0.4 só reabre por:

- falha de teste;
- impossibilidade técnica demonstrada;
- contradição nova;
- mudança explícita de contrato/escopo;
- novo risco de segurança.

## Próxima etapa

A camada física está suficientemente completa para abrir a **Analysis View v0.1**.

O próximo recorte deve ser definido em novo ciclo de contrato → auditoria → integração antes de implementação.
