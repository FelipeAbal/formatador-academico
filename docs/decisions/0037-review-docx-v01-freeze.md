# Decisão 0037 — Review/Highlight DOCX v0.1 — freeze

Status: **FROZEN**

Date: 2026-09-09

## 1. Escopo congelado

Congela a implementação do Review/Highlight DOCX v0.1 definida pelo contrato 0036, após auditoria adversarial, implementação, endurecimento de testes, inspeção estática, merge e validação no `main`.

Fronteira:

```text
clean_package_snapshot: bytes
+ ProcessingReport v0.1
→ ReviewDocxResult
```

A camada é exclusivamente visual e nunca cria autoridade normativa nova.

## 2. Auditoria adversarial

A proposta inicial 0036 foi auditada externamente por Claude Opus sobre o SHA:

`6a2eb711b5b85af75cd5e05aea3129d48d5f4b30`

Veredito:

`APROVAR COM AJUSTES`

Três bloqueadores concretos foram identificados e integrados antes da implementação:

1. allowed-delta simétrico poderia ocultar overwrite de highlight autoral;
2. ClassificationItem run-level não existe no pipeline congelado e não poderia ser testado honestamente;
3. target drift/hash mismatch não pode ser degradado para `unmarked` normal em artefatos hash-bound.

Também foram integrados os ajustes sobre superfície visual segura, tolerância a extensões estrangeiras em rPr, ausência de postcondition semântica para highlight e completude do ReviewDocxResult.

Contrato auditado/aceito para implementação em:

`b8c5440c6ca829e671cab6ab441f50954659cdc3`

## 3. Implementação congelada

PR:

`#13 — Review DOCX v0.1: safe visual highlighting`

Head final auditado:

`8458874f8533f2107f85a6d4d8dde8e7cfa09e53`

Squash merge / integração no `main`:

`0b8ebad402dd558b357006d98a0d54014d8b5c58`

API pública:

```text
build_review_docx(
    clean_package_snapshot: bytes,
    processing_report: ProcessingReport,
) -> ReviewDocxResult
```

Constante:

```text
REVIEW_DOCX_VERSION = "0.1"
```

## 4. Semântica visual congelada

Única marca criada:

```xml
<w:highlight w:val="yellow"/>
```

Significado único:

> existe informação correspondente no ProcessingReport para este run.

Não representa severity, categoria, compliance ou prioridade.

Não há cores múltiplas, comentários OOXML ou legenda textual no v0.1.

## 5. Itens marcáveis

Somente targets físicos `run` provenientes de:

- AppliedChangeItem;
- UnappliedChangeItem;
- ReviewItem.

ClassificationItems permanecem report-only no v0.1 e são contabilizados em:

```text
unmarkable_classification_item_count
```

Nenhum fallback por parágrafo, primeiro run, texto semelhante ou heurística é permitido.

## 6. Conservação e highlight preexistente

Se existir direct `w:highlight` antes da camada review:

```text
unmarked / existing_highlight
```

O highlight existente não é alterado, mesmo se já amarelo.

O allowed-delta é assimétrico e set-driven:

- somente paths efetivamente `marked` podem ter o highlight criado neutralizado na árvore AFTER para comparação;
- runs `unmarked` nunca têm seus highlights neutralizados;
- overwrite de highlight autoral permanece detectável;
- após neutralização autorizada, o restante do document.xml deve ser canonicamente equivalente.

Não reutilizar o `_strip_target_for_comparison` simétrico do Patcher para esta prova.

## 7. Superfície visual segura

Marcáveis:
- `w:t` com conteúdo visível;
- `w:sym`;
- `w:tab`;
- `w:br`;
- runs visíveis dentro de hyperlink / insertion / containers compatíveis.

Normalmente `unmarked`:

```text
existing_highlight
noncanonical_run_properties
no_visual_surface
protected_revision_run
```

`no_visual_surface` inclui run vazio/rPr-only, instrText-only, fldChar-only, drawing/object/pict-only.

`protected_revision_run` inclui w:delText e run sob w:del.

## 8. rPr e extensões

A camada review preserva a disciplina CT_RPr dos filhos `w:` conhecidos, porém tolera extensões de namespace estrangeiro (`w14:` etc.) sem movê-las ou normalizá-las.

Essa tolerância é exclusiva da camada visual e NÃO altera o Patcher normativo congelado.

`w:rPrChange` permanece protegido.

## 9. Target identity / integrity

AppliedChangeItem:
- stored physical_hash é pré-transformação e normalmente stale;
- resolução usa structural_path apenas após runtime guard P1/P2 + document.xml.

UnappliedChangeItem / ReviewItem:
- physical_hash pertence ao snapshot final e deve ser revalidado.

Com clean/report hash-bound:

```text
target_not_found
target_type_mismatch
physical_hash_mismatch
```

são `ReviewDocxIntegrityError`, nunca `unmarked` normal.

## 10. Postcondition

Analysis congelada não modela `w:highlight`.

Portanto não existe postcondition semântica via Analysis no v0.1.

A postcondition física é load-bearing e exige, nos paths `marked`:
- exatamente um direct w:highlight;
- `w:val == "yellow"`;
- target ainda resolve para w:r;
- package scope e allowed-delta preservados.

## 11. Package preservation

Somente:

```text
word/document.xml
```

pode mudar.

Reutiliza infraestrutura segura do Patcher para package/ZIP e serialização documental.

Partes não autorizadas permanecem byte-idênticas; entry order, ZIP metadata, archive comment e declaração XML/prolog/epilog são preservados segundo os invariantes congelados do Patcher.

## 12. Determinismo / separação clean-review

Mesmo clean bytes + mesmo ProcessingReport → mesmos review bytes e mesmos mark_results no runtime suportado.

Sem filesystem/network/clock/random/LLM/dynamic import no runtime.

Se não houver nenhum candidato marcável:

```text
review output bytes == clean input bytes
```

O DOCX limpo nunca é mutado in-place.

Review highlight:
- não entra em TransformLog;
- não é compliance;
- não deve ser reinjetado automaticamente no Processing Session como clean input.

## 13. ReviewDocxResult congelado

Campos:

```text
review_docx_version
parser_version
processing_report_version
processing_report_ref
changed_part
input_clean_package_sha256
output_review_package_sha256
output_review_package_bytes
mark_results
unmarkable_classification_item_count
```

ReviewMarkResult:

```text
target_type
structural_path
physical_hash
status
reason
source_kinds
```

`source_kinds` usa ordem canônica:

```text
applied_change
unapplied_change
review_item
```

## 14. Validação final

PR #13 validado antes do merge e `main` validado após squash merge.

GitHub Actions pós-merge:

- run id: `34378127660`;
- head SHA: `0b8ebad402dd558b357006d98a0d54014d8b5c58`;
- suite: **627/627 OK**;
- failures: 0;
- errors: 0.

A suíte inclui testes adversariais específicos para:
- overwrite de highlight existente;
- unrelated text mutation;
- target path drift;
- physical_hash drift;
- visual-surface policy;
- deterministic repeated output;
- ausência de runtime IO/network/clock/random/dynamic import.

## 15. Dívidas explícitas não bloqueadoras

- highlight herdado por style não modelado;
- Classification run-level não persistida;
- target_physical_hash_after não persistido no TransformRecord;
- semântica de cor/legenda/comments;
- part/story_id na identidade de target;
- stories secundárias marcáveis.

## 16. Regra de reabertura

Este freeze só deve ser reaberto por:
- teste falhando;
- impossibilidade técnica demonstrada;
- contradição com contrato congelado;
- mudança explícita de escopo;
- novo risco de segurança/conservação.
