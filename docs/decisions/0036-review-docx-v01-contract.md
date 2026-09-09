# Decisão 0036 — Review/Highlight DOCX v0.1 — contrato

Status: **PROPOSED — PENDING ADVERSARIAL AUDIT**

Date: 2026-09-09

## 1. Objetivo

Produzir o segundo DOCX do produto: uma cópia visualmente marcada do **snapshot limpo final** da Processing Session, sem alterar conteúdo substantivo.

Fronteira conceitual:

```text
clean_package_snapshot: bytes
+ ProcessingReport v0.1
→ ReviewDocxResult
```

O Review DOCX é derivado do DOCX limpo. O DOCX limpo jamais é mutado in-place.

## 2. Papel da camada

Review DOCX v0.1 é uma camada exclusivamente de apresentação visual.

Ela NÃO pode:
- criar nova Decision;
- reclassificar;
- reinterpretar reason/status;
- aplicar correção normativa;
- alterar texto;
- alterar field code;
- alterar tracked revisions;
- alterar hyperlinks;
- alterar estrutura documental;
- apagar marca visual preexistente;
- decidir severity;
- esconder item do ProcessingReport.

## 3. Snapshot binding obrigatório

Primeira precondição absoluta:

```text
sha256(clean_package_snapshot)
==
processing_report.summary.output_package_sha256
```

Mismatch → fail-fast `ReviewDocxIntegrityError` antes de qualquer mutação.

O report deve ser `PROCESSING_REPORT_VERSION == 0.1`.

## 4. Slice de marcação v0.1

Marcação automática somente para targets físicos de tipo:

```text
run
```

Categorias candidatas:
- AppliedChangeItem;
- UnappliedChangeItem;
- ReviewItem;
- ClassificationItem apenas quando `target_type == run`.

Paragraph/table/container/story-only items permanecem no ProcessingReport, mas não são artificialmente convertidos em marca run-level no v0.1.

Racional: evitar destacar texto mais amplo do que o alvo realmente identificado.

## 5. Semântica visual única

V0.1 usa uma única marca visual:

```xml
<w:highlight w:val="yellow"/>
```

A cor NÃO representa severity, categoria ou prioridade. Significa apenas:

> existe informação correspondente no ProcessingReport para este run.

Nenhuma legenda textual é inserida no DOCX.

Não há cores diferentes para applied/unapplied/review/abstention no v0.1.

Racional:
- múltiplas categorias podem coexistir no mesmo run;
- `w:highlight` suporta um valor por run;
- uma precedência de cores criaria semântica nova e poderia esconder fatos;
- o ProcessingReport é a fonte de verdade para a natureza do item.

## 6. Deduplicação visual

Vários report items podem apontar para o mesmo run.

A marcação visual é deduplicada por identidade de localização do snapshot final:

```text
(target_type="run", structural_path)
```

Um run recebe no máximo uma marca `w:highlight` criada por esta camada.

A deduplicação visual NÃO deduplica nem remove itens do ProcessingReport.

## 7. Existing highlight — regra de conservação

Se o target run já contém `w:highlight` direto antes da camada de review:

```text
NÃO TOCAR
```

Mesmo se já for amarelo.

O item/run é registrado como não marcado com reason:

```text
existing_highlight
```

Racional: não é possível distinguir de forma segura marca autoral/preexistente de marca que poderíamos substituir.

Não remover, trocar nem duplicar highlight preexistente.

## 8. Forma física do `w:rPr`

A camada reutiliza as regras seguras congeladas do Patcher 0028/0029 quando aplicáveis:
- target exato por structural_path;
- somente direct child `w:rPr`;
- >1 direct `w:rPr` → não marcar;
- `w:rPr` fora da primeira posição → não marcar;
- `mc:AlternateContent` direto dentro de rPr → não marcar;
- rPr children fora da ordem CT_RPr → não marcar;
- `w:rPrChange` é protegido/opaco;
- nunca usar eixo descendente para localizar `w:highlight`;
- se rPr não existir, criar como primeiro filho do `w:r`;
- se `<w:rPr/>` existir, reutilizar.

Reason fechado para forma não segura:

```text
noncanonical_run_properties
```

Não normalizar/reparar o run.

## 9. Ordem canônica de highlight

`w:highlight` deve ser inserido na posição CT_RPr canônica, sem mover nenhum sibling existente.

Usar a mesma tabela de ordem validada no Patcher:

```text
...
sz, szCs, highlight, u, effect,
...
```

Se os siblings existentes não estiverem em ordem canônica, não marcar.

## 10. Target resolution

Resolver exclusivamente via a API física pública congelada:

```text
resolve_structural_path(root, structural_path)
```

`structural_path` não é XPath.

Exigir que o nó resolvido seja exatamente `w:r`.

### AppliedChangeItem

O `physical_hash` do TransformRecord é pré-transformação e normalmente diverge do snapshot limpo final.

Portanto, v0.1 NÃO exige igualdade de `physical_hash` para AppliedChangeItem.

A autorização para usar `structural_path` repousa no contrato congelado atual:
- somente property edits P1/P2;
- nenhum MOVE/INSERT/MERGE estrutural;
- 0031 registra structural_path estável pré/pós no slice atual.

Se operações estruturais forem adicionadas futuramente, esta regra deve ser versionada antes de uso.

### UnappliedChangeItem / ReviewItem

Esses itens são derivados das final Decisions do snapshot final. Quando possuem target físico, `physical_hash` deve ser revalidado contra o run resolvido.

Mismatch → não marcar, reason `physical_hash_mismatch`.

### ClassificationItem

É derivado das final Classifications. Para `target_type == run`, `physical_hash` deve ser revalidado.

Mismatch → não marcar, reason `physical_hash_mismatch`.

## 11. Targets não resolvíveis

Item run-level cujo structural_path:
- não resolve;
- resolve mais de uma vez;
- resolve para tipo diferente;

NÃO causa fallback heurístico.

Não procurar texto semelhante.

Registrar não marcado com reason fechado:

```text
target_not_found
target_not_unique
target_type_mismatch
```

Esses casos são resultados de review rendering, não autorização para modificar outro local.

## 12. ReviewMarkResult

Cada localização run-level deduplicada gera exatamente um resultado de marcação.

Modelo conceitual:

```text
ReviewMarkStatus = marked | unmarked

ReviewMarkResult:
    target_type
    structural_path
    status
    reason | None
    source_kinds: tuple[str, ...]
```

`source_kinds` é conjunto ordenado deterministicamente dos tipos de item que apontaram ao run:

```text
applied_change
unapplied_change
review_item
classification_item
```

Não contém texto user-facing.

Para `marked`: reason == None.
Para `unmarked`: reason obrigatório.

## 13. Itens não marcáveis por design

ClassificationItems cujo target_type != run não geram ReviewMarkResult run-level.

Eles são contabilizados separadamente em:

```text
unmarkable_report_item_count
```

No v0.1 isso NÃO é erro: o ProcessingReport continua sendo o registro completo.

Não criar marca artificial em parágrafo pai ou primeiro run descendente.

## 14. ReviewDocxResult

Modelo conceitual:

```text
review_docx_version
processing_report_ref
input_clean_package_sha256
output_review_package_sha256
output_review_package_bytes
mark_results: tuple[ReviewMarkResult, ...]
unmarkable_report_item_count
```

Invariantes:
- input SHA == report summary output SHA;
- output SHA == sha256(output bytes);
- output bytes só são produzidos após todas as postconditions globais;
- cada localização run-level deduplicada aparece exatamente uma vez em mark_results;
- `unmarkable_report_item_count` conta apenas itens deliberadamente fora do slice de marcação.

## 15. Atomicidade

O clean snapshot é imutável.

A camada trabalha sobre cópia em memória e retorna novo package somente após validação completa.

Erro inesperado/integrity failure → nenhum output válido.

Resultados `unmarked` de targets individuais NÃO impedem marcações independentes seguras.

## 16. Package scope

V0.1 modifica somente:

```text
word/document.xml
```

Nenhuma part adicionada/removida.

Todas as demais payload bytes permanecem byte-idênticas.

Entry set/order/metadata ZIP seguem a preservação congelada do Patcher 0029.

Não criar comments.xml, relationships ou content types.

## 17. XML serialization

Reutilizar a disciplina congelada do Patcher:
- lxml seguro;
- ElementTree/document-level;
- preservar encoding físico;
- preservar declaration/standalone quando existentes;
- preservar comments/PIs de prólogo/epílogo;
- no `cleanup_namespaces()`;
- no DTD/entities/network/recover;
- preservar ZIP metadata allowlist e timestamps;
- compresslevel fixo.

Preferir extrair/reusar helpers públicos ou compartilhados existentes do Patcher em vez de copiar lógica divergente.

## 18. Allowed-delta

Após construir output e relê-lo do ZIP:

O único delta XML permitido em `word/document.xml` é, para runs marcados:
- criação necessária de `w:rPr` vazio/novo na posição canônica;
- criação de exatamente um direct `w:highlight w:val="yellow"` na posição canônica.

Nenhuma alteração permitida em:
- texto;
- tabs/breaks/symbols;
- instrText/fields;
- deleted text;
- hyperlink/container structure;
- bookmarks/comments/PIs;
- tracked revisions/rPrChange;
- propriedades de formatação preexistentes;
- paragraph properties;
- styles.xml;
- other parts.

Validator deve neutralizar apenas os highlights criados e wrappers rPr criados exclusivamente por esta camada, então exigir equivalência canônica do restante do document tree + docinfo/prolog/epilog.

## 19. Postcondition

Reabrir os bytes finais do ZIP produzido.

Para cada `marked`:
- structural_path ainda resolve para o mesmo tipo run;
- existe exatamente um direct `w:highlight`;
- valor lexical final é exatamente `yellow`;
- rPr permanece canônico.

Para cada `unmarked`:
- o target não foi alterado pela camada de review.

Global:
- nenhum texto/conteúdo substantivo mudou;
- parts não autorizadas byte-idênticas;
- package/output SHA coerentes;
- allowed-delta aprovado.

## 20. Ordem / determinismo

A camada constrói a ordem de targets pela primeira aparição nos grupos do ProcessingReport em ordem:

```text
applied_changes
unapplied_changes
review_items
classification_items
```

Dentro de cada grupo, preserva ordem do report.

Essa ordem serve apenas para `mark_results` e execução determinística; NÃO significa prioridade semântica.

`source_kinds` usa ordem canônica fixa da lista acima.

Mesmo clean bytes + mesmo ProcessingReport → mesmos review bytes e mesmos mark_results no runtime suportado.

Sem timestamp atual, UUID, locale, clock, random, network ou LLM.

## 21. Clean/Review separation

Invariante central:

```text
clean DOCX bytes permanecem exatamente os bytes recebidos
review DOCX é uma nova saída derivada
```

O sistema nunca substitui silenciosamente o clean output pelo review output.

Review highlighting não entra em TransformLog: não é correção normativa do documento limpo.

## 22. Error model

```text
ReviewDocxError
ReviewDocxContractError
ReviewDocxIntegrityError
```

### Fail-fast / integrity
- clean snapshot SHA não corresponde ao report;
- report version incompatível;
- XML/package impossível de reler;
- allowed-delta falha;
- output hash incoerente;
- package part set divergente;
- erro inesperado de serialização;
- invariant/model impossível.

### Normal `unmarked`
- existing_highlight;
- noncanonical_run_properties;
- physical_hash_mismatch;
- target_not_found;
- target_not_unique;
- target_type_mismatch.

Nunca converter integrity failure global em unmarked silencioso.

## 23. Questões para auditoria adversarial

1. `w:highlight` único amarelo é a opção mais conservadora, ou `w:shd`/comments seriam mais seguros?
2. Existing direct highlight → abstain é suficiente para preservação, inclusive quando highlight é herdado por style?
3. `w:highlight` é toggle/cascaded de modo que direct yellow sempre vence de forma previsvisível?
4. Há restrições de schema/ordem além de CT_RPr já cobertas pelo Patcher?
5. O uso de structural_path sem physical_hash para AppliedChangeItem é seguro sob os freezes 0029/0031/0033 ou precisamos registrar final target identity antes desta camada?
6. Neutralizar highlights criados no allowed-delta é suficiente para provar ausência de outros deltas?
7. A política de item-level unmarked versus fail-fast global está bem delimitada?
8. A ausência de marcação para paragraph/table ClassificationItems mantém corretamente “na dúvida, marcar” porque eles permanecem no ProcessingReport?
9. Precisamos detectar highlight efetivo herdado por style ou basta preservar direct property existente?
10. A camada deve marcar runs vazios/sem texto, ou estes deveriam ser `unmarked` por ausência de superfície visual útil?
11. `w:highlight` em runs de field instructions/deleted text deve ser proibido mesmo quando target run resolve?
12. Há necessidade de preservar/considerar `w:highlight` dentro de `w:rPrChange` ou style chain como impeditivo?

## 24. Testes mínimos antes do freeze

1. clean/report SHA mismatch fail-fast;
2. raw report type/version inválido;
3. one applied run marked yellow;
4. one unapplied run marked;
5. one review run marked;
6. run ClassificationItem marked;
7. paragraph ClassificationItem counted unmarkable, no fallback;
8. same run in multiple report categories → one highlight, source_kinds complete;
9. existing direct highlight yellow → unmarked/preserved;
10. existing direct highlight other color → unmarked/preserved;
11. duplicate rPr → unmarked;
12. misplaced rPr → unmarked;
13. AlternateContent in rPr → unmarked;
14. out-of-order rPr → unmarked;
15. rPrChange protected;
16. create rPr as first run child;
17. dense rPr insertion position exact;
18. applied item physical_hash stale but path stable → mark succeeds;
19. final Decision physical_hash mismatch → unmarked;
20. target path not found/type mismatch → unmarked, no heuristic;
21. mixed marked + unmarked independent progress;
22. no report items → review bytes either identical or deterministic no-op policy explicitly tested;
23. text/tabs/breaks/sym/instrText/delText preserved;
24. hyperlink run marked without breaking container;
25. no tracked revision mutation;
26. all non-document.xml payload bytes identical;
27. ZIP metadata/order preserved;
28. XML declaration/UTF-16/prolog/PI preserved;
29. allowed-delta catches unrelated property mutation;
30. marked postcondition reopens output bytes;
31. unmarked target unchanged;
32. output SHA matches bytes;
33. deterministic repeated bytes;
34. cross-hashseed determinism where relevant;
35. input clean bytes immutable;
36. runtime no filesystem/network/clock/random/LLM;
37. all 591+ regressions green.

## 25. Critério de implementação

Não implementar antes de auditoria adversarial independente, pois esta etapa volta a mutar OOXML/DOCX.

Auditoria recomendada: **Claude Opus**, não Kimi, porque o risco principal é contrato/conservação OOXML, não volume de implementação.