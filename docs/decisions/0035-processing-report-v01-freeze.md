# Decisão 0035 — Freeze do Processing Report v0.1

Status: **FROZEN**

Date: 2026-09-09

## 1. Escopo congelado

Processing Report v0.1 é uma projeção read-only, determinística e machine-readable do `ProcessingSessionResult` congelado em 0033.

API pública:

```text
build_processing_report(
    session_result: ProcessingSessionResult,
) -> ProcessingReport
```

Não relê DOCX, não executa Parser/Analysis/Classification/Decision e não cria nova autoridade normativa.

## 2. Categorias congeladas

O relatório expõe quatro famílias:

```text
applied_changes
unapplied_changes
review_items
classification_items
```

mais `ProcessingReportSummary` e `StoryCoverage`.

### applied_changes

Fonte exclusiva: `TransformRecord`.

Um TransformRecord gera exatamente um AppliedChangeItem, preservando ordem real de aplicação, refs, target, valores antes/desejado e package hashes.

### unapplied_changes

Fonte exclusiva: `SessionFinding` + final Decision canonicamente ligada.

Cobre:
- gate_blocked;
- patch_rejected;
- operation_limit.

Reason upstream é preservado literalmente; desired/observed vêm da final Decision.

### review_items

Fonte exclusiva: final Decisions com:

```text
actionability in {review, human_choice}
```

`no_action` e `preserve` não geram ReviewItem.

### classification_items

Gerado quando:
- status == abstained; ou
- classification_warnings não vazio.

`not_applicable` puro não gera item individual; permanece contabilizado no summary/StoryCoverage.

Um result simultaneamente abstained + warning gera um único item.

## 3. StoryCoverage

Por `story_id`, em ordem da primeira aparição:

```text
story_id
total_count
classified_count
abstained_count
not_applicable_count
warning_count
```

Counts são puramente mecânicos. Não há score de conformidade nem julgamento de qualidade da cobertura.

## 4. Summary

Campos congelados:

```text
session_status
applied_change_count
unapplied_change_count
review_item_count
classification_item_count
final_decision_count
final_classification_count
classified_count
abstained_count
not_applicable_count
classification_warning_count
story_coverage
input_package_sha256
output_package_sha256
```

Invariantes globais e por story exigem soma exata.

## 5. ProcessingReport

Campos públicos:

```text
processing_report_version
processing_session_version
profile_ref
summary
applied_changes
unapplied_changes
review_items
classification_items
```

Não contém package bytes, raw XML, Analysis Views, SafetyGateReport, PatchResult, GateClearedOperation, timestamp, UUID, hostname ou ambiente.

## 6. Identidade determinística

`PROCESSING_REPORT_VERSION = "0.1"`.

```text
processing_report_ref(report)
=
sha256(serialize_processing_report(report))
```

Serialização canônica:
- UTF-8;
- JSON compact;
- keys ordenadas;
- Decimal -> string;
- enums -> value;
- tuples -> arrays;
- LengthValue preservado como objeto `{value, unit}`;
- bytes rejeitados.

Sem clock/random/locale.

## 7. Localização / futuro DOCX de revisão

Os itens preservam `structural_path` e `target_class` quando upstream possui.

No slice atual, isso é suficiente para o futuro review/highlight DOCX localizar:
- alterações aplicadas;
- deterministic changes não aplicadas;
- review/human_choice;
- abstentions representáveis no story executável.

Processing Report não promete que todo ClassificationItem seja marcável no DOCX final; stories/targets fora do slice podem permanecer apenas no relatório.

## 8. Evidence de Classification

`ClassificationEvidence` detalhada NÃO é duplicada no v0.1.

Reasons + warnings + localização são suficientes para os consumidores planejados do slice atual; evidence continua disponível no `ProcessingSessionResult` upstream.

## 9. Segurança

Runtime do Processing Report é derivacional/read-only.

Proibido:
- abrir DOCX/ZIP;
- filesystem;
- rede;
- relógio/random;
- LLM;
- reanalysis/reclassification/redecision;
- inferir desired;
- inventar localização;
- suprimir warning por heurística.

Inconsistências impossíveis em cross-bindings falham rápido via `ProcessingReportContractError` / `ProcessingReportIntegrityError`.

## 10. Auditoria / hardening

Antes do freeze foram validados explicitamente:
- gate blocked -> UnappliedChangeItem;
- Patcher rejection real por duplicate direct `w:b` -> UnappliedChangeItem;
- operation limit -> UnappliedChangeItem;
- review/human_choice -> ReviewItem;
- no_action/preserve excluídos de ReviewItem;
- abstention -> ClassificationItem;
- not_applicable puro -> summary only;
- classified warning -> ClassificationItem;
- abstained + warning -> item único;
- StoryCoverage global/per-story;
- target_class preservado;
- typed Decimal/LengthValue serialization;
- ausência de package bytes;
- input session imutável;
- runtime sem DOCX/IO/network/clock/random/dynamic import;
- determinismo cross-hashseed.

## 11. PR / commits

PR #12 head final auditado:

`28ffb60224509cce0bd7916ae39810a2c6397a81`

Squash merge:

`3328b8f9eb8f582aa19c7ced9168561621f32bfb`

## 12. Validação final

GitHub Actions no head final do PR e no `main` pós-merge:

```text
591/591 OK
failures: 0
errors: 0
skips: 0
```

Todos os regressions congelados anteriores permaneceram verdes.

## 13. Dívidas / não objetivos

- renderer human-readable (HTML/PDF/JSON presentation);
- tradução/localização user-facing dos códigos;
- review/highlight DOCX;
- severity/ranking visual;
- paginação física;
- drill-down de ClassificationEvidence autocontida;
- user-facing grouping/dedup visual;
- UI/API final.

## 14. Freeze

**Processing Report v0.1 está congelado.**

Mudanças semânticas exigem nova decisão/versionamento.

Próximo estágio recomendado: **Review/Highlight DOCX v0.1 — contrato primeiro**, consumindo o DOCX limpo da sessão e o ProcessingReport congelado sem alterar conteúdo substantivo.