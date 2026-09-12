# Decisão 0006 — Parser v0.2: decomposição física de parágrafos e runs

## Status

APROVADA por Felipe após proposta do ChatGPT e auditoria técnica do Kimi K3.

## Objetivo

Expandir a cobertura física do parser sem entrar em formatação efetiva, semântica acadêmica ou stories secundárias.

A v0.2 decompõe `w:p` e seus runs físicos mantendo `canonical_xml` integral do parágrafo como rede de segurança.

## Escopo

- `w:pPr` vira `properties_raw` do parágrafo, sem interpretação;
- `w:r` vira `run_raw`, sem coalescimento;
- `w:rPr` vira `properties_raw` do run, sem cálculo de formatação efetiva;
- containers intermediários de runs são representados por `run_container`;
- runs dentro de containers são decompostos recursivamente mantendo o path físico real;
- fragmentos de run são tipados quando reconhecidos;
- qualquer filho não coberto vira representação opaca/protegida;
- `canonical_xml`, `inherited_xml_attrs` e `physical_hash` continuam presentes para rastreabilidade física.

## Containers de runs

Tipos inicialmente reconhecidos como `run_container`:
- `w:hyperlink`;
- `w:ins`;
- `w:del`;
- `w:fldSimple`;
- `w:sdt`;
- `w:sdtContent`;
- `w:smartTag`.

O container permanece protegido e gera `unparsed_container`, porque sua semântica editorial/estrutural não é interpretada nesta versão. Seus runs internos podem ser decompostos para preservar ordem e provenance.

## Fragmentos de run

Tipos inicialmente reconhecidos:
- `w:t` -> `text`;
- `w:tab` -> `tab`;
- `w:br` -> `break`;
- `w:cr` -> `carriage_return`;
- `w:noBreakHyphen` -> `no_break_hyphen`;
- `w:softHyphen` -> `soft_hyphen`;
- `w:sym` -> `symbol`;
- `w:instrText` -> `instruction_text`;
- `w:delText` -> `deleted_text`.

Qualquer outro filho de `w:r` vira `opaque_fragment`, preservado e protegido.

Atributos `xml:space`, `xml:lang` e `xml:base` próprios do fragmento são registrados explicitamente. O contexto herdado continua sendo capturado por `inherited_xml_attrs`.

## Ordem e identidade física

Não há achatamento de paths.

Exemplos:
- `/w:document/w:body[1]/w:p[3]/w:r[7]`;
- `/w:document/w:body[1]/w:p[3]/w:hyperlink[1]/w:r[2]`.

`original_index` de estruturas internas é 0-based entre irmãos do mesmo tipo no pai imediato. `structural_path` permanece 1-based por tipo, conforme a convenção do parser.

O `physical_hash` do parágrafo continua baseado no parágrafo integral, preservando compatibilidade conceitual com a v0.1. Runs, containers, propriedades e fragmentos recebem identidade física própria adicional.

## Cobertura mecânica

A suíte deve testar cobertura 1:1 dos filhos de `w:p` e `w:r`:
- `w:pPr` -> `properties_raw`;
- `w:r` -> `run_raw`;
- container reconhecido -> `run_container`;
- outro filho -> representação opaca/protegida;
- comentário/PI -> nó preservado/protegido.

Nenhum filho pode desaparecer silenciosamente.

## Fora do escopo

- cálculo de negrito/itálico/fonte efetivos;
- resolução de styles/herança;
- normalização ou fusão de runs;
- interpretação editorial de tracked changes;
- classificação acadêmica;
- tabelas internas;
- footnotes/endnotes/headers/footers/comments como stories;
- patches/escrita DOCX.

## Próximo passo

Implementar a v0.2 e submetê-la a revisão técnica antes de abrir stories secundárias.
