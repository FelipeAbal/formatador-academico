# Decisão 0008 — Parser v0.3: stories secundárias e parse parcial

## Contexto

Após o hardening da v0.2, o Kimi K3 auditou o recorte da v0.3 no commit `1833ff3`. Veredito: **APROVAR COM AJUSTES**.

A v0.3 mantém o recorte inteiro:
- footnotes;
- endnotes;
- headers;
- footers;
- comments.

Textboxes continuam fora da decomposição, mas passam a ser detectadas explicitamente.

## Decisão estrutural

Falha em uma story secundária **não derruba o documento inteiro**.

Estados:
- `story.status = ok`;
- `story.status = missing` quando relationship aponta para part ausente;
- `story.status = failed` quando a part existe mas não pode ser parseada;
- resultado global `status = partial` quando ao menos uma story secundária falha ou está ausente;
- falha do body/pacote principal continua sendo `status = failed`.

Stories `failed`/`missing` deverão ser tratadas pelo futuro Safety Gate como regiões sem autorização automática.

## Modelo de stories

- `body`, `header` e `footer`: `blocks[]`.
- `footnotes`, `endnotes` e `comments`: `items[]`.
- Uma story não mistura `blocks[]` e `items[]`.

Campos:
- `story_id`;
- `story_type`;
- `part`;
- `relationship_id`;
- `status`;
- `errors[]`.

Notes/comments preservam IDs como strings cruas. Não converter IDs para inteiro nem interpretar separadores/reservados no parser.

## Descoberta

Stories secundárias relacionadas ao documento são descobertas pelos relationships de `word/document.xml`, usando o **Type URI**, nunca pelo nome do arquivo.

O `Target` relativo é resolvido contra a part de origem.

Content type é usado como validação cruzada:
- divergência gera `story_type_mismatch`;
- o relationship continua sendo a autoridade física do vínculo.

Parts com content type conhecido de story, mas sem relationship do documento, são parseadas como órfãs e geram `orphan_story_part`.

Relationship para part inexistente gera story `missing` + `missing_related_part`.

Relationships duplicados para a mesma part não criam story duplicada; geram `duplicate_story_relationship`.

## Reuso

O dispatch de blocos é extraído para `_parse_block_sequence(...)`, reutilizado por body, headers, footers e itens de notes/comments.

O parser de parágrafo/run/container continua único.

IDs de bloco são parametrizados pelo `story_id`.

Warnings agregados passam a carregar `story_id` quando originados de story específica.

## Identidade

`structural_path` continua relativo à part.

Identidade global exige story/part + path:
`{story_id, structural_path, original_index, physical_hash}`.

`original_index` mantém a regra v0.2:
posição 0-based entre todos os filhos do pai imediato.

## Notes e comments

Footnotes/endnotes:
- `note_id` cru;
- `note_type` cru quando existir;
- identidade física do item;
- `blocks[]`.

Comments:
- `comment_id` cru;
- atributos físicos preservados no `canonical_xml`;
- `blocks[]`.

A ligação comment range ↔ comment não é resolvida na v0.3. Os IDs físicos permanecem recuperáveis.

## Headers e footers

Uma story por part.

Não inferir:
- seção;
- primeira página;
- par/ímpar.

`relationship_id` é preservado para resolução futura.

## Textboxes

Textboxes não são decompostas na v0.3.

Quando um nó opaco contiver `w:txbxContent`, emitir `textbox_detected`. O conteúdo continua preservado no `canonical_xml` do opaco.

## Tabelas

Tabelas permanecem blocos integrais em qualquer story e geram `unparsed_children`.

## Testes mínimos

A implementação deve testar:
- documento sem stories secundárias;
- footnotes/endnotes com IDs crus e especiais;
- comments multi-bloco;
- múltiplos headers/footers;
- target relativo;
- part ausente;
- story malformada com falha contida;
- part órfã;
- relationship duplicado;
- mismatch relationship/content type;
- textboxes detectadas;
- warnings com story_id;
- unicidade de story_id/part;
- cobertura de todas as story parts conhecidas;
- filhos não-item preservados;
- determinismo mesmo input e entre `PYTHONHASHSEED`;
- regressão central do body v0.2.

## Resultado esperado

Após implementação e testes, submeter o código real da v0.3 ao Kimi K3 antes de abrir decomposição de tabelas ou textboxes.
