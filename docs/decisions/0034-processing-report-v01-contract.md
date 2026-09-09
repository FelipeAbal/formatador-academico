# Decisão 0034 — Processing Report v0.1 — contrato

Status: **PROPOSED**

Date: 2026-09-09

## 1. Objetivo

Processing Report v0.1 transforma exclusivamente o `ProcessingSessionResult` congelado em 0033 em um artefato machine-readable autocontido o suficiente para alimentar, depois:

1. relatório legível ao usuário;
2. DOCX de revisão/highlight;
3. UI/API futura.

Ele NÃO é uma nova camada normativa e NÃO pode criar, alterar, completar ou reinterpretar Decisions/Classifications/TransformRecords.

Princípio:

```text
ProcessingSessionResult
→ ProcessingReport
```

Sem DOCX/package bytes de entrada adicionais, sem Parser/Analysis/Classification/Decision novos, sem rede, sem LLM e sem heurística.

## 2. Não objetivos v0.1

Fora deste slice:
- PDF/HTML/DOCX user-facing;
- tradução de códigos técnicos para linguagem natural final;
- escolha de cor/highlight;
- inserção de comentários no DOCX;
- agrupamento por página física;
- paginação;
- UI;
- severidade inferida por heurística;
- ranking por importância;
- deduplicação sem regra explícita;
- reexecução do pipeline;
- leitura de raw OOXML;
- cálculo de conformidade global;
- promessa de “documento conforme”.

## 3. Fronteira pública conceitual

```text
build_processing_report(
    session_result: ProcessingSessionResult,
) -> ProcessingReport
```

Input obrigatório: um `ProcessingSessionResult` válido.

O builder nunca recebe `ProcessingProfile` separado. `profile_ref` vem do próprio resultado congelado.

## 4. Categorias v0.1

O relatório consolida quatro famílias de informação:

```text
A. applied_changes
B. unapplied_changes
C. review_items
D. classification_items
```

Além disso, expõe `summary` derivado mecanicamente.

Nenhuma família cria nova autoridade. Cada item é projeção de um artefato upstream identificável.

## 5. AppliedChangeItem

Fonte exclusiva: `ProcessingSessionResult.transforms`.

Um `TransformRecord` gera exatamente um `AppliedChangeItem`.

Campos mínimos:

```text
kind = applied_change
transform_ref
decision_ref
operation_ref
profile_ref
rule_ref
target
observed_before
desired_applied
input_package_sha256
output_package_sha256
changed_part
```

Regras:
- ordem preserva a ordem real de `session_result.transforms`;
- `observed_before = TransformRecord.precondition_observed`;
- `desired_applied = TransformRecord.desired_value`;
- nenhuma tentativa de reconstruir “valor depois” por Analysis;
- sem raw XML;
- sem bytes do DOCX.

## 6. UnappliedChangeItem

Fonte exclusiva: `ProcessingSessionResult.findings` + `final_decisions` canonicamente ligadas.

Kinds upstream aceitos:
- `gate_blocked`;
- `patch_rejected`;
- `operation_limit`.

Campos mínimos:

```text
kind = unapplied_change
finding_kind
decision_ref
operation_ref
profile_ref
rule_ref | None
target
reason
compliance
actionability
analysis_status
observed
desired_value
decision_reason
```

Cross-binding obrigatório:
- `finding.decision_ref` deve resolver para exatamente uma final Decision;
- target deve coincidir;
- a final Decision deve ser `deterministic_change`;
- `desired_value` vem da Decision, não do finding;
- reason permanece exatamente o código upstream, sem reinterpretação.

## 7. ReviewItem

Fonte exclusiva: `ProcessingSessionResult.final_decisions`.

Gerar item individual somente quando:

```text
actionability in {review, human_choice}
```

`preserve` e `no_action` NÃO geram ReviewItem no v0.1.

Racional:
- `preserve` é contenção intencional, não pendência;
- `no_action` inclui conformidade/ausência de ação e não deve inflar o relatório.

Campos mínimos:

```text
kind = review_item
decision_ref
profile_ref
rule_ref | None
target
compliance
actionability
reason
analysis_status
observed
evidence_ref | None
decision_warnings
```

Não existe `desired_value` significativo fora de deterministic_change; o campo não deve ser inventado.

## 8. ClassificationItem

Fonte exclusiva: `ProcessingSessionResult.final_classifications`.

Gerar item individual para:

```text
status == abstained
```

Também gerar item quando `classification_warnings` não estiver vazio, independentemente de status, para não perder anomalias contratuais/executivas já registradas upstream.

`not_applicable` puro, sem warning, NÃO gera item individual no v0.1.

Racional: `not_applicable` é muitas vezes resultado esperado para story/target fora do slice; itemizar cada ocorrência produziria ruído e falsos alertas. Seu volume continua visível no `summary`.

Campos mínimos:

```text
kind = classification_item
classification_status
target_type
structural_path
physical_hash
story_id
target_class | None
reasons
basis | None
provenance
metadata
classification_warnings
```

Evidence detalhada NÃO precisa ser duplicada no item v0.1; permanece no `ProcessingSessionResult` upstream. Se futura UI exigir drill-down sem sessão original, versionar o relatório.

## 9. Summary

`ProcessingReportSummary` é derivado somente por contagem, sem julgamento.

Campos mínimos:

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
input_package_sha256
output_package_sha256
```

Invariantes:
- applied count == len(transforms);
- unapplied count == len(findings);
- classified + abstained + not_applicable == final_classification_count;
- warning count é soma exata de `classification_warnings` nas final classifications;
- nenhum percentual de “conformidade” é calculado.

## 10. ProcessingReport

Campos públicos conceituais:

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

Não embute:
- output_package_bytes;
- DOCX input/output;
- SafetyGateReport;
- PatchResult;
- GateClearedOperation;
- raw XML;
- Analysis Views completas;
- timestamp;
- UUID;
- hostname;
- ambiente.

## 11. Ordenação determinística

### applied_changes
Ordem real de `TransformRecord` da sessão.

### unapplied_changes
Ordem exata de `session_result.findings`.

### review_items
Ordem das `final_decisions` congeladas.

### classification_items
Ordem das `final_classifications` congeladas.

O builder não reordena por mensagem, severity, reason ou target_class.

## 12. Identidade / refs

Refs upstream devem ser preservados quando existem.

`decision_ref` usa a serialização canônica congelada da Decision.

`transform_ref` usa a serialização canônica congelada do TransformRecord.

O relatório não cria refs artificiais por item no v0.1.

Opcionalmente o envelope completo terá:

```text
processing_report_ref
=
sha256(serialize_processing_report(report))
```

se a serialização canônica for implementada no mesmo ciclo.

## 13. Valores tipados

O relatório preserva os tipos semânticos upstream internamente.

Na serialização canônica:
- Decimal → string;
- enums → `.value`;
- tuples → arrays JSON;
- dataclasses/provenance refs → objetos JSON determinísticos;
- bool permanece bool;
- `LengthValue(pt)` preserva `{value, unit}`;
- nenhuma conversão para strings human-readable como “12 pt” dentro do core.

A tradução para texto é responsabilidade de renderer futuro.

## 14. Nenhuma linguagem user-facing no core

O core NÃO gera frases como:
- “Fonte corrigida com sucesso”;
- “Recomendamos revisar”;
- “Seu documento está 95% conforme”.

Ele fornece códigos e dados estruturados. Um renderer futuro poderá mapear esses códigos para português/inglês e níveis visuais sem alterar a verdade do core.

## 15. Relação com o DOCX de revisão

O futuro DOCX de revisão pode consumir:
- `AppliedChangeItem.target.structural_path` para sinalizar alteração aplicada;
- `UnappliedChangeItem.target.structural_path` para sinalizar alteração não executada;
- `ReviewItem.target.structural_path` para sinalizar revisão humana;
- `ClassificationItem.structural_path` para sinalizar abstention quando o alvo for representável no story executável.

Processing Report v0.1 NÃO garante que todo ClassificationItem seja marcável no DOCX final. Stories/targets fora do slice podem existir apenas como informação de relatório.

## 16. Deduplicação

Não fazer deduplicação sem chave upstream inequívoca.

É permitido que o mesmo structural_path apareça em categorias diferentes quando representam fatos diferentes, por exemplo:
- uma mudança aplicada em P1;
- uma ReviewItem em outro aspecto;
- uma ClassificationWarning no mesmo bloco.

O renderer pode agrupar visualmente no futuro, mas o core não perde eventos.

## 17. Invariantes de completude interna

Obrigatório:

```text
len(applied_changes) == len(session_result.transforms)
len(unapplied_changes) == len(session_result.findings)
```

Todo ReviewItem corresponde a exatamente uma final Decision com actionability review|human_choice.

Todo abstained ClassificationResult corresponde a exatamente um ClassificationItem.

Todo ClassificationResult com warning deve estar representado por ClassificationItem, sem duplicar o mesmo result em dois itens.

## 18. Status da sessão

O relatório copia `ProcessingSessionStatus` exatamente.

Nunca renomeia:
- `quiescent` para “complete”;
- `quiescent_with_unapplied` para “failed”;
- `operation_limit_reached` para “partial success”.

Interpretação humana pertence ao renderer.

## 19. Segurança

Processing Report v0.1 é read-only e derivacional.

Proibido:
- abrir ZIP/DOCX;
- mutar inputs;
- usar filesystem;
- usar rede;
- usar relógio/random;
- chamar LLM;
- reexecutar Analysis/Classification/Decision;
- inferir desired;
- inventar localização;
- apagar warning por parecer irrelevante.

## 20. Determinismo

Mesma instância semanticamente válida de `ProcessingSessionResult` → mesmo ProcessingReport e mesma serialização canônica.

Sem timestamp/UUID/locale.

## 21. Error model

Inputs malformados ou inconsistências impossíveis nos cross-bindings → fail-fast `ProcessingReportContractError` / `ProcessingReportIntegrityError`.

Não existe “best effort” silencioso.

Exemplos de integrity error:
- finding sem final Decision correspondente;
- transform_ref recalculado divergente;
- item count não bate com upstream;
- status/classification enum inesperado;
- duplicate canonical decision refs quando upstream prometeu unicidade.

## 22. Testes mínimos

1. sessão sem mudanças → relatório válido, applied=0;
2. uma mudança bold aplicada;
3. uma mudança font_size aplicada;
4. duas mudanças aplicadas preservam ordem real;
5. gate blocked vira exatamente um UnappliedChangeItem;
6. patch rejected vira exatamente um UnappliedChangeItem;
7. operation limit vira exatamente um UnappliedChangeItem;
8. final Decision review vira ReviewItem;
9. final Decision human_choice vira ReviewItem;
10. no_action não vira ReviewItem;
11. preserve não vira ReviewItem;
12. abstained classification vira ClassificationItem;
13. not_applicable sem warning não vira ClassificationItem;
14. classified com warning vira ClassificationItem;
15. abstained com warning gera um único item;
16. summary counts exatos;
17. `classified+abstained+not_applicable == total`;
18. applied item preserva transform_ref/refs/values;
19. unapplied item liga finding à final Decision;
20. review item preserva evidence_ref/warnings;
21. input não mutado;
22. runtime sem IO/network/clock/random/LLM;
23. determinismo same-process;
24. determinismo cross-hashseed;
25. canonical serialization roundtrip/bytes stable;
26. Decimal/LengthValue/bool serialização tipada;
27. report não contém package bytes;
28. todos regressions 565+ permanecem verdes.

## 23. Perguntas de auditoria antes do freeze

- `ClassificationItem` deve incorporar evidence agora ou é correto manter evidence somente no SessionResult?
- `not_applicable` sem warning deve permanecer apenas no summary ou há classes específicas que merecem item individual?
- ReviewItem deve incluir `rule_ref=None` quando rule absent ou excluir rule-absent decisions por não serem revisão real?
- applied/unapplied/review/classification são suficientes para o futuro DOCX de revisão sem nova análise?
- precisamos de `processing_report_ref` já no v0.1?
- o relatório deve carregar `target_class` em todos os itens em que upstream possui essa informação?
- há alguma informação já disponível que, se omitida agora, obrigaria reler o DOCX para gerar o renderer futuro?

## 24. Critério de freeze

Só congelar depois de auditoria contra:
- `ProcessingSessionResult` 0033;
- TransformRecord 0031;
- Decision 0021;
- ClassificationResult 0023;
- necessidades mínimas do futuro DOCX de revisão.

Nenhuma implementação antes de resolver as perguntas de §23.