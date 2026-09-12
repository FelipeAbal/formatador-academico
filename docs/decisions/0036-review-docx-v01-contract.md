# Decisão 0036 — Review/Highlight DOCX v0.1 — contrato

Status: **ACCEPTED FOR IMPLEMENTATION — adversarial audit integrated**

Date: 2026-09-09

Audit base SHA: `6a2eb711b5b85af75cd5e05aea3129d48d5f4b30`

Audit verdict: **APROVAR COM AJUSTES**.

## 1. Objetivo

Produzir o segundo DOCX do produto: uma cópia visualmente marcada do **snapshot limpo final** da Processing Session, sem alterar conteúdo substantivo.

Fronteira:

```text
clean_package_snapshot: bytes
+ ProcessingReport v0.1
→ ReviewDocxResult
```

O Review DOCX é derivado do DOCX limpo. O DOCX limpo jamais é mutado in-place.

## 2. Papel da camada

Review DOCX v0.1 é exclusivamente uma camada de apresentação visual.

Ela NÃO pode:
- criar nova Decision;
- reclassificar;
- reinterpretar reason/status;
- aplicar correção normativa;
- alterar texto, field code ou estrutura documental;
- alterar tracked revisions;
- alterar hyperlinks;
- apagar/trocar marca visual preexistente;
- decidir severity;
- esconder item do ProcessingReport;
- entrar em TransformLog.

## 3. Snapshot binding obrigatório

Primeira precondição absoluta:

```text
sha256(clean_package_snapshot)
== processing_report.summary.output_package_sha256
```

Mismatch → `ReviewDocxIntegrityError` antes de qualquer mutação.

Exigir:
- `processing_report.processing_report_version == PROCESSING_REPORT_VERSION == "0.1"`;
- snapshot parseável pelo Parser congelado;
- root `word/document.xml` compatível com `parser_api.resolve_structural_path`.

## 4. Slice de marcação v0.1

Marcação automática somente para report items com target físico de tipo `run`:
- `AppliedChangeItem`;
- `UnappliedChangeItem`;
- `ReviewItem`.

**ClassificationItems são integralmente não marcáveis no v0.1.**

Razão: `final_classifications` congelado contém classificação primária de parágrafos; as projeções run-level usadas internamente para Decision não são persistidas no `ProcessingSessionResult`. Não criar ramo fictício nem fixture forjada para isso.

ClassificationItems continuam integralmente no ProcessingReport e são contabilizados em:

```text
unmarkable_classification_item_count
```

Não marcar parágrafo pai, primeiro run descendente ou texto aproximado.

## 5. Semântica visual única

V0.1 usa apenas:

```xml
<w:highlight w:val="yellow"/>
```

A cor não representa severity, categoria ou prioridade. Significa apenas:

> existe informação correspondente no ProcessingReport para este run.

Sem legenda textual, comentários OOXML ou cores por categoria.

`w:highlight` é apresentação da cópia review, nunca autoridade normativa.

## 6. Deduplicação visual

Deduplicar por:

```text
(target_type="run", structural_path)
```

Um run recebe no máximo um highlight criado por esta camada.

`source_kinds` registra todas as categorias que apontaram ao run em ordem canônica fixa:

```text
applied_change
unapplied_change
review_item
```

A deduplicação visual não remove itens do ProcessingReport.

A chave atual é segura somente para `word/document.xml`. Se stories secundárias se tornarem marcáveis, a identidade deverá incorporar part/story antes de habilitação.

## 7. Existing highlight — conservação

Se o target run já contém `w:highlight` **direto** antes da camada de review:

```text
NÃO TOCAR
```

Mesmo se amarelo.

Resultado:

```text
unmarked / existing_highlight
```

Highlight herdado por style NÃO é detectado no v0.1 porque Analysis não modela `w:highlight`. Um highlight herdado pode ser visualmente sobreposto pelo direct yellow apenas na cópia review; o clean permanece intacto. Essa limitação é dívida explícita.

`w:highlight` dentro de `w:rPrChange` é histórico/protegido e não conta como highlight direto atual; deve permanecer intacto.

## 8. Superfície visual segura

A decisão é feita somente por filhos físicos diretos do run e ancestralidade estrutural já conhecida; não por texto semelhante.

### Marcáveis
- `w:t` com conteúdo visível;
- `w:sym`;
- `w:tab`;
- `w:br`;
- runs dentro de `w:hyperlink`, `w:ins`, `w:smartTag`, `w:sdtContent`, desde que possuam superfície acima.

### `unmarked / no_visual_surface`
- run vazio ou somente `w:rPr`;
- somente `w:instrText`;
- somente `w:fldChar`;
- somente `w:drawing`, `w:object` ou `w:pict`;
- combinações que não produzam glifo/superfície textual destacável.

### `unmarked / protected_revision_run`
- run contendo `w:delText`;
- run situado sob `w:del`.

`w:ins` é marcável: a cópia review pode receber direct highlight sem criar `w:rPrChange`; isso é apresentação, não revisão normativa.

## 9. Forma física de `w:rPr`

Reusar disciplina do Patcher quando aplicável, sem alterar o Patcher congelado:
- somente direct `w:rPr`;
- >1 direct `w:rPr` → `unmarked / noncanonical_run_properties`;
- `w:rPr` fora da primeira posição → `unmarked / noncanonical_run_properties`;
- `mc:AlternateContent` direto dentro de rPr → `unmarked / noncanonical_run_properties`;
- elementos `w:` conhecidos fora da ordem CT_RPr → `unmarked / noncanonical_run_properties`;
- `w:rPrChange` protegido/opaco;
- não usar eixo descendente para `w:highlight`;
- se rPr não existir, criar como primeiro filho do run;
- se `<w:rPr/>` existir, reutilizar.

### Extensões de namespace estrangeiro

A camada review é mais tolerante que o Patcher normativo:
- filhos de namespace estrangeiro (`w14:`, extensões MCE etc.) não tornam o rPr automaticamente não canônico;
- a posição de `w:highlight` é calculada apenas em relação aos filhos `w:` reconhecidos na tabela canônica;
- extensões estrangeiras permanecem exatamente onde estavam e nunca são movidas, reescritas ou normalizadas.

Essa tolerância é exclusiva da camada visual.

## 10. Ordem canônica de highlight

Inserir `w:highlight` na posição CT_RPr canônica:

```text
..., sz, szCs, highlight, u, effect, ...
```

Não mover sibling existente.

## 11. Target resolution e identidade

Resolver exclusivamente via API pública congelada:

```text
resolve_structural_path(root, structural_path)
```

`structural_path` não é XPath.

`StructuralPathError` deve ser capturada e convertida conforme o error model; nunca procurar por texto.

O nó resolvido deve ser exatamente `w:r`.

### AppliedChangeItem

O `physical_hash` registrado é pré-transformação e normalmente stale no snapshot final. Portanto não se exige igualdade desse hash.

Antes de confiar em path-only, runtime deve afirmar para cada AppliedChangeItem:
- `target.target_type == "run"`;
- `target.property_slot in {"bold", "font_size"}`;
- `changed_part == "word/document.xml"`.

Sob o slice atual property-only, `structural_path` é congeladamente estável e pode identificar o mesmo run final.

### UnappliedChangeItem / ReviewItem

São derivados das final Decisions do snapshot final. O `physical_hash` deve ser revalidado contra o run resolvido.

Qualquer mismatch é **integrity error**, não resultado normal.

## 12. Error model de target resolution

Com clean/report hash-bound:
- `target_not_found` → `ReviewDocxIntegrityError`;
- `target_type_mismatch` → `ReviewDocxIntegrityError`;
- `physical_hash_mismatch` → `ReviewDocxIntegrityError`;
- `target_not_unique` não faz parte do vocabulário v0.1 porque `resolve_structural_path` resolve um único nó ou falha.

Esses estados indicam drift/bug entre artefatos já vinculados ao mesmo snapshot.

## 13. ReviewMarkReason e ReviewMarkResult

Vocabulário fechado:

```text
ReviewMarkReason =
    existing_highlight
    noncanonical_run_properties
    no_visual_surface
    protected_revision_run

ReviewMarkStatus = marked | unmarked
```

Modelo:

```text
ReviewMarkResult:
    target_type
    structural_path
    physical_hash
    status
    reason: ReviewMarkReason | None
    source_kinds: tuple[str, ...]
```

`physical_hash` é o hash físico do run resolvido no snapshot limpo final, antes da marca visual.

Invariantes:
- `marked` → `reason is None`;
- `unmarked` → reason obrigatório;
- um resultado por localização deduplicada;
- `source_kinds` em ordem canônica fixa, não por ordem de descoberta.

## 14. Itens deliberadamente não marcáveis

Todos os `ClassificationItem` permanecem fora do slice visual v0.1.

Resultado global registra:

```text
unmarkable_classification_item_count
```

Esse contador é exatamente `len(processing_report.classification_items)` no v0.1.

Não transformar isso em `ReviewMarkResult` artificial.

## 15. ReviewDocxResult

```text
ReviewDocxResult:
    review_docx_version
    parser_version
    processing_report_version
    processing_report_ref
    changed_part
    input_clean_package_sha256
    output_review_package_sha256
    output_review_package_bytes
    mark_results: tuple[ReviewMarkResult, ...]
    unmarkable_classification_item_count
```

Constantes:

```text
REVIEW_DOCX_VERSION = "0.1"
changed_part = "word/document.xml"
```

Invariantes:
- input SHA == report summary output SHA;
- output SHA == sha256(output bytes);
- parser/report versions explícitas;
- output somente após postconditions globais;
- cada localização run-level deduplicada aparece uma vez;
- zero candidatos marcáveis → output bytes **byte-idênticos** ao clean input.

Não armazenar contadores marked/unmarked redundantes; derivá-los de `mark_results`.

## 16. Atomicidade

Clean snapshot imutável.

Trabalhar sobre cópia em memória. Resultado individual `unmarked` não impede marcações independentes. Integrity failure global ou de binding não produz output válido.

## 17. Package scope / reutilização

Modificar somente:

```text
word/document.xml
```

Nenhuma part adicionada/removida.

Reusar diretamente infraestrutura segura do Patcher para:
- leitura/escrita de package;
- ZIP entry order;
- timestamps;
- compress_type;
- attrs internos/externos;
- archive comment;
- parser lxml seguro;
- ElementTree/document serialization;
- encoding/declaration/standalone;
- comments/PIs de prólogo/epílogo;
- docinfo/prolog/epilog fingerprints.

Não copiar/reimplementar essas rotinas se já puderem ser compartilhadas com segurança.

**Não reutilizar `_strip_target_for_comparison` do Patcher como está.** Seu comportamento simétrico é inseguro para existing highlights.

## 18. Allowed-delta — neutralização assimétrica set-driven

Após construir output e relê-lo do ZIP, o único delta permitido é, nos runs cujo `ReviewMarkResult.status == marked`:
- criação necessária de `w:rPr`;
- criação de exatamente um direct `<w:highlight w:val="yellow"/>`.

O validador mantém um conjunto explícito de paths marcados.

Neutralização para comparação:
- remover/neutralizar `w:highlight` **somente do lado after e somente em paths `marked`**;
- neutralizar wrapper `w:rPr` criado exclusivamente pela camada somente nesses paths;
- **nunca** remover highlight de run `unmarked` em nenhum lado;
- especialmente `existing_highlight` permanece participante da comparação canônica.

Depois da neutralização set-driven, exigir equivalência canônica do restante do document tree + docinfo/prolog/epilog.

Nenhuma alteração permitida em texto, tabs/breaks/symbols, fields, deleted text, hyperlinks/containers, bookmarks/comments/PIs, tracked revisions/rPrChange, propriedades preexistentes, paragraph properties, styles.xml ou outras parts.

## 19. Postcondition

A Analysis congelada não modela `w:highlight`; portanto **não existe postcondition semântica via Analysis no v0.1**. Não inventar uma.

A postcondition física é load-bearing.

Reabrir os bytes finais do ZIP.

Para cada `marked`:
- structural_path resolve para `w:r`;
- exatamente um direct `w:highlight`;
- `w:val == "yellow"`;
- rPr preserva a ordem dos elementos `w:` conhecidos;
- extensões estrangeiras permanecem intactas.

Para cada `unmarked`:
- target físico correspondente permanece canonicamente equivalente ao before.

Global:
- content/text unchanged;
- parts não autorizadas byte-idênticas;
- part set/order/metadata preservados;
- package/output SHA coerentes;
- allowed-delta aprovado.

## 20. Ordem / determinismo

Grupos processados em ordem:

```text
applied_changes
unapplied_changes
review_items
```

Dentro de cada grupo, preservar ordem do report.

Primeira aparição define a posição do `ReviewMarkResult`; `source_kinds` é sempre reordenado pela lista canônica fixa acima.

Mesmo clean bytes + mesmo ProcessingReport → mesmos review bytes e mesmos mark_results no runtime suportado.

Sem timestamp atual, UUID, locale, clock, random, network ou LLM.

## 21. Clean/Review separation

```text
clean DOCX bytes permanecem exatamente os bytes recebidos
review DOCX é nova saída derivada
```

Review highlighting:
- não entra em TransformLog;
- não pode ser usado como prova de compliance;
- não substitui o clean output;
- não deve ser reinjetado automaticamente no Processing Session como se fosse clean input.

A API/integração futura deve manter tipos/nomes distintos para clean e review bytes para reduzir reinjeção acidental.

## 22. Error model

```text
ReviewDocxError
ReviewDocxContractError
ReviewDocxIntegrityError
```

### Normal `unmarked`
- `existing_highlight`;
- `noncanonical_run_properties`;
- `no_visual_surface`;
- `protected_revision_run`.

### Fail-fast / integrity
- clean/report SHA mismatch;
- report/parser version incompatível;
- target final não encontrado;
- target final resolve para tipo divergente;
- physical hash divergente para item final-snapshot;
- applied item fora das premissas P1/P2/document.xml;
- XML/package impossível de reler;
- allowed-delta failure;
- output hash incoerente;
- package part set divergente;
- erro inesperado de serialização;
- invariant/model impossível.

Nunca degradar integrity failure para `unmarked`.

## 23. Dívidas explícitas

- highlight herdado por style não modelado;
- Classification run-level não persistida;
- `target_physical_hash_after` não persistido no TransformRecord;
- semântica de cor/legenda/comments;
- part/story_id na identidade de target;
- stories secundárias marcáveis.

Nenhuma dessas bloqueia o v0.1.

## 24. Testes mínimos antes do freeze

1. clean/report SHA mismatch fail-fast;
2. report type/version inválido;
3. one applied run marked yellow;
4. one unapplied run marked;
5. one review run marked;
6. paragraph ClassificationItem counted only in `unmarkable_classification_item_count`, no fallback;
7. same run in applied/unapplied/review → one highlight, canonical source_kinds;
8. existing direct yellow → unmarked/preserved and participates in allowed-delta comparison;
9. existing direct non-yellow → unmarked/preserved and participates in allowed-delta comparison;
10. duplicate rPr → unmarked noncanonical;
11. misplaced rPr → unmarked noncanonical;
12. AlternateContent direct in rPr → unmarked noncanonical;
13. known `w:` child out of order → unmarked noncanonical;
14. foreign `w14:` child tolerated and preserved;
15. rPrChange protected and preserved;
16. create rPr as first run child;
17. dense rPr insertion position exact;
18. applied item stale physical_hash + valid P1/P2 path → mark succeeds;
19. applied item outside P1/P2/document.xml → integrity error;
20. final item physical_hash mismatch → integrity error;
21. target path not found/type mismatch → integrity error, no heuristic;
22. mixed marked + ordinary unmarked progress independently;
23. zero markable report items → output bytes exactly equal clean input;
24. run with w:t marked;
25. w:sym marked;
26. w:tab marked;
27. w:br marked;
28. hyperlink run marked without container mutation;
29. w:ins run with visible surface marked;
30. empty/rPr-only run → no_visual_surface;
31. instrText-only → no_visual_surface;
32. fldChar-only → no_visual_surface;
33. drawing/object/pict-only → no_visual_surface;
34. delText / ancestor w:del → protected_revision_run;
35. text/tabs/breaks/sym/instrText/delText all preserved;
36. tracked revision markup preserved;
37. all non-document.xml payload bytes identical;
38. ZIP metadata/order/archive comment preserved;
39. XML declaration/UTF-16/prolog/PI preserved;
40. set-driven allowed-delta catches overwrite of existing highlight;
41. set-driven allowed-delta catches unrelated rPr mutation;
42. set-driven allowed-delta catches unrelated document mutation;
43. postcondition direct yellow exact;
44. ReviewMarkResult records final physical_hash;
45. result records parser/report versions and changed_part;
46. deterministic repeated output bytes;
47. deterministic mark_results/source_kinds;
48. clean input bytes unchanged;
49. no filesystem/network/clock/random/LLM/dynamic import runtime;
50. all existing regressions green.

## 25. Resultado da auditoria adversarial

Achados integrados:
- B1: allowed-delta agora é assimétrico/set-driven; helper simétrico do Patcher não pode ser reutilizado diretamente;
- B2: removido ramo impossível de ClassificationItem run-level; classification items são explicitamente não marcáveis no v0.1;
- B3: drift de target/hash volta a ser integrity error, consistente com 0029;
- I1: política fechada para runs sem superfície e tracked deletion;
- I2: extensões de namespace estrangeiro toleradas sem relaxar ordem dos filhos `w:` conhecidos;
- I3: postcondition física explicitamente load-bearing; Analysis não modela highlight;
- I4: ReviewDocxResult registra parser/report versions, changed_part e physical_hash final; reason virou enum fechado;
- M1–M5 incorporados.

Contrato aprovado para implementação. Freeze somente após implementação, CI completo e auditoria estática final.