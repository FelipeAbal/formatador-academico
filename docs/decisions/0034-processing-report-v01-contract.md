# Decisão 0034 — Processing Report v0.1 — contrato

Status: **ACCEPTED FOR IMPLEMENTATION**

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

## 3. Fronteira pública

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

Campos:

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
- `target.target_class` é preservado;
- nenhuma tentativa de reconstruir “valor depois” por Analysis;
- sem raw XML;
- sem bytes do DOCX.

## 6. UnappliedChangeItem

Fonte exclusiva: `ProcessingSessionResult.findings` + `final_decisions` canonicamente ligadas.

Kinds upstream aceitos:
- `gate_blocked`;
- `patch_rejected`;
- `operation_limit`.

Campos:

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
- `finding.decision_ref` resolve para exatamente uma final Decision;
- target coincide integralmente;
- a final Decision é `deterministic_change`;
- `desired_value` vem da Decision, não do finding;
- `target.target_class` é preservado;
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

Campos:

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

`target.target_class` é preservado.

Não existe `desired_value` significativo fora de deterministic_change; o campo não é inventado.

RuleRef ausente, se ocorrer em Decision upstream válida, é preservado como `None`; o report builder não decide se a ausência torna a revisão mais ou menos relevante.

## 8. ClassificationItem

Fonte exclusiva: `ProcessingSessionResult.final_classifications`.

Gerar item individual quando:

```text
status == abstained
```

Também gerar item quando `classification_warnings` não estiver vazio, independentemente de status, para não perder anomalias já registradas upstream.

`not_applicable` puro, sem warning, NÃO gera item individual no v0.1.

Racional: `not_applicable` é frequentemente resultado esperado para story/target fora do slice; itemizar cada ocorrência produziria ruído e falsos alertas. Sua cobertura permanece explícita no summary global e por story.

Campos:

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

### Evidence

`ClassificationEvidence` detalhada NÃO é duplicada no ProcessingReport v0.1.

Justificativa:
- reasons + warnings + localização bastam para renderer/review v0.1;
- evidence continua preservada no `ProcessingSessionResult` upstream;
- duplicá-la agora aumentaria muito o artefato sem necessidade operacional demonstrada.

Se futura UI exigir drill-down autocontido sem sessão original, versionar o relatório.

## 9. StoryCoverage

Para transparência sem ruído, o summary contém cobertura agregada por `story_id`.

Modelo conceitual:

```text
StoryCoverage:
    story_id
    total_count
    classified_count
    abstained_count
    not_applicable_count
    warning_count
```

Regras:
- uma entrada por story_id presente em `final_classifications`;
- ordem de primeira aparição da story em `final_classifications`;
- counts são somas mecânicas;
- `classified + abstained + not_applicable == total_count` por story;
- warning_count soma exatamente o número de `classification_warnings` naquela story.

Não há julgamento de “boa” ou “má” cobertura.

## 10. ProcessingReportSummary

Derivado somente por contagem, sem julgamento.

Campos:

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

Invariantes:
- applied count == len(transforms);
- unapplied count == len(findings);
- classified + abstained + not_applicable == final_classification_count;
- warning count é soma exata de `classification_warnings` nas final classifications;
- story coverage soma exatamente para os totais globais;
- nenhum percentual de “conformidade” é calculado.

## 11. ProcessingReport

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

## 12. Ordenação determinística

### applied_changes
Ordem real de `TransformRecord` da sessão.

### unapplied_changes
Ordem exata de `session_result.findings`.

### review_items
Ordem das `final_decisions` congeladas.

### classification_items
Ordem das `final_classifications` congeladas.

### story_coverage
Ordem da primeira aparição de cada story em `final_classifications`.

O builder não reordena por mensagem, severity, reason ou target_class.

## 13. Identidade / refs

Refs upstream são preservados quando existem.

`decision_ref` usa a serialização canônica congelada da Decision.

`transform_ref` usa a serialização canônica congelada do TransformRecord.

O relatório não cria refs artificiais por item no v0.1.

O envelope completo TEM identidade determinística:

```text
processing_report_ref(report)
=
sha256(serialize_processing_report(report))
```

Isso é obrigatório no v0.1.

## 14. Valores tipados

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

## 15. Nenhuma linguagem user-facing no core

O core NÃO gera frases como:
- “Fonte corrigida com sucesso”;
- “Recomendamos revisar”;
- “Seu documento está 95% conforme”.

Ele fornece códigos e dados estruturados. Um renderer futuro poderá mapear esses códigos para português/inglês e níveis visuais sem alterar a verdade do core.

## 16. Relação com o DOCX de revisão

O futuro DOCX de revisão pode consumir:
- `AppliedChangeItem.target.structural_path` para sinalizar alteração aplicada;
- `UnappliedChangeItem.target.structural_path` para sinalizar alteração não executada;
- `ReviewItem.target.structural_path` para sinalizar revisão humana;
- `ClassificationItem.structural_path` para sinalizar abstention quando o alvo for representável no story executável.

Processing Report v0.1 NÃO garante que todo ClassificationItem seja marcável no DOCX final. Stories/targets fora do slice podem existir apenas como informação de relatório.

Não é necessária nova Analysis para localizar os itens do slice atual.

## 17. Deduplicação

Não fazer deduplicação sem chave upstream inequívoca.

É permitido que o mesmo structural_path apareça em categorias diferentes quando representam fatos diferentes, por exemplo:
- uma mudança aplicada em P1;
- uma ReviewItem em outro aspecto;
- uma ClassificationWarning no mesmo bloco.

Um `ClassificationResult` que seja simultaneamente abstained e tenha warnings gera UM único ClassificationItem.

O renderer pode agrupar visualmente no futuro, mas o core não perde eventos.

## 18. Invariantes de completude interna

Obrigatório:

```text
len(applied_changes) == len(session_result.transforms)
len(unapplied_changes) == len(session_result.findings)
```

Todo ReviewItem corresponde a exatamente uma final Decision com actionability review|human_choice.

Todo final Decision review|human_choice corresponde a exatamente um ReviewItem.

Todo abstained ClassificationResult corresponde a exatamente um ClassificationItem.

Todo ClassificationResult com warning está representado por ClassificationItem, sem duplicar o mesmo result.

Todo item que possui profile_ref usa `session_result.profile_ref`.

## 19. Status da sessão

O relatório copia `ProcessingSessionStatus` exatamente.

Nunca renomeia:
- `quiescent` para “complete”;
- `quiescent_with_unapplied` para “failed”;
- `operation_limit_reached` para “partial success”.

Interpretação humana pertence ao renderer.

## 20. Segurança

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

## 21. Determinismo

Mesma instância semanticamente válida de `ProcessingSessionResult` → mesmo ProcessingReport, mesma serialização canônica e mesmo processing_report_ref.

Sem timestamp/UUID/locale.

## 22. Error model

Inputs malformados ou inconsistências impossíveis nos cross-bindings → fail-fast:

```text
ProcessingReportError
ProcessingReportContractError
ProcessingReportIntegrityError
```

Não existe “best effort” silencioso.

Exemplos de integrity error:
- finding sem final Decision correspondente;
- transform_ref recalculado divergente;
- item count não bate com upstream;
- duplicate canonical decision refs quando upstream prometeu unicidade;
- summary/story coverage incoerentes com os itens upstream.

## 23. Resultado da auditoria pré-implementação

Perguntas da proposta inicial resolvidas:

1. `ClassificationEvidence` não entra no v0.1; reasons/warnings/localização bastam para os consumidores planejados.
2. `not_applicable` puro permanece fora dos itens, mas fica visível em counts globais e `StoryCoverage`.
3. ReviewItem preserva `rule_ref=None` se upstream trouxer isso; o builder não reinterpretará.
4. applied/unapplied/review/classification + structural_path são suficientes para o futuro DOCX de revisão no slice atual.
5. `processing_report_ref` é obrigatório já no v0.1.
6. `target_class` é preservado sempre que upstream o possui.
7. Nenhuma informação adicional disponível hoje foi identificada como necessária para evitar releitura do DOCX no renderer/review do slice atual.

Conclusão: contrato pronto para implementação sem auditoria externa adicional, porque a camada é estritamente read-only/projetiva e não amplia autoridade nem mutação.

## 24. Testes mínimos

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
18. StoryCoverage por story exato;
19. soma StoryCoverage == global;
20. applied item preserva transform_ref/refs/values;
21. unapplied item liga finding à final Decision;
22. review item preserva evidence_ref/warnings;
23. input não mutado;
24. runtime sem IO/network/clock/random/LLM;
25. determinismo same-process;
26. determinismo cross-hashseed;
27. canonical serialization bytes stable;
28. `processing_report_ref == sha256(serialization)`;
29. Decimal/LengthValue/bool serialização tipada;
30. report não contém package bytes;
31. target_class preservado;
32. todos regressions 565+ permanecem verdes.

## 25. Critério de freeze

Congelar somente após:
- implementação em pacote separado;
- suíte específica verde;
- CI completo verde;
- auditoria estática de cross-bindings/serialização;
- nenhuma alteração semântica em ProcessingSession/TransformLog/Decision/Classification.
