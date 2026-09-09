# Decisão 0038 — Product Output Bundle v0.1 — contrato

Status: **ACCEPTED FOR IMPLEMENTATION**

Date: 2026-09-09

## 1. Objetivo

Fechar a primeira fronteira única de produto capaz de receber um DOCX + `ProcessingProfile` e devolver, de forma deterministicamente vinculada, as três saídas centrais do MVP já implementadas:

1. DOCX limpo;
2. DOCX de revisão/highlight;
3. relatório de processamento em JSON canônico.

Esta camada é somente composição/orquestração de APIs congeladas. Ela não cria autoridade normativa, não reimplementa Analysis/Classification/Decision, não modifica OOXML diretamente e não altera os contratos das camadas upstream.

## 2. Pipeline autorizado

```text
input DOCX bytes + ProcessingProfile
→ process_document(...)
→ ProcessingSessionResult
→ clean DOCX = ProcessingSessionResult.output_package_bytes
→ build_processing_report(ProcessingSessionResult)
→ ProcessingReport
→ serialize_processing_report(ProcessingReport)
→ canonical report JSON bytes
→ build_review_docx(clean DOCX, ProcessingReport)
→ ReviewDocxResult
→ ProductOutputBundle
```

Nenhuma etapa pode ser pulada, reordenada ou substituída por inferência local.

## 3. API pública conceitual

```python
build_product_output_bundle(
    package_snapshot: bytes,
    profile: ProcessingProfile,
    *,
    max_applied_operations: int = DEFAULT_MAX_APPLIED_OPERATIONS,
) -> ProductOutputBundle
```

O Bundle recebe somente o DOCX de entrada, o `ProcessingProfile` congelado e o limite operacional já suportado pela Processing Session.

## 4. Resultado

```text
ProductOutputBundle:
    product_output_bundle_version
    processing_session_version
    processing_report_version
    review_docx_version
    profile_ref
    session_status
    input_package_sha256
    clean_package_sha256
    clean_package_bytes
    review_package_sha256
    review_package_bytes
    processing_report_ref
    processing_report_json_bytes
    processing_report
```

O objeto é imutável.

`processing_report` é preservado como objeto tipado para consumidores internos. `processing_report_json_bytes` é a saída material do relatório no v0.1.

Não há ZIP adicional contendo as três saídas no v0.1. “Bundle” significa aggregate de produto, não arquivo-container.

## 5. Binding obrigatório entre artefatos

O construtor deve provar antes de retornar:

1. `sha256(package_snapshot) == input_package_sha256`;
2. `clean_package_bytes is session_result.output_package_bytes` por conteúdo e `sha256(clean_package_bytes) == session_result.output_package_sha256`;
3. `processing_report.summary.input_package_sha256 == session_result.input_package_sha256`;
4. `processing_report.summary.output_package_sha256 == clean_package_sha256`;
5. `processing_report_ref == sha256(processing_report_json_bytes)`;
6. `processing_report_json_bytes == serialize_processing_report(processing_report)`;
7. `review_result.input_package_sha256 == clean_package_sha256`;
8. `review_result.processing_report_ref == processing_report_ref`;
9. `sha256(review_package_bytes) == review_result.output_package_sha256`;
10. as versões registradas no Bundle são exatamente as versões públicas das camadas chamadas.

Qualquer contradição é falha de integridade, nunca saída parcial.

## 6. Sem saída parcial

A API é atomicamente observável: ou retorna um `ProductOutputBundle` completo e autoconsistente, ou levanta exceção.

Não retorna apenas clean/report/review quando uma etapa posterior falha.

Isso não desfaz o fato de que `process_document` pode internamente ter chegado a um snapshot limpo válido; apenas significa que esta fronteira de produto não publica um bundle incompleto.

## 7. Erros

```text
ProductOutputBundleError
├── ProductOutputBundleContractError
└── ProductOutputBundleIntegrityError
```

- tipo de entrada, perfil e limite operacional inválidos → `ProductOutputBundleContractError`;
- contradições de hash/ref/versão/lineage ou falhas upstream de integridade → `ProductOutputBundleIntegrityError`.

Erros upstream de contrato devem ser traduzidos para `ProductOutputBundleContractError` preservando a causa (`raise ... from exc`).

Erros upstream de integridade devem ser traduzidos para `ProductOutputBundleIntegrityError` preservando a causa.

Exceções inesperadas/programming errors continuam fail-fast e não são mascaradas como erro ordinário.

## 8. Determinismo

Mesmos `package_snapshot`, `ProcessingProfile` e `max_applied_operations` devem produzir Bundle semanticamente idêntico e bytes idênticos para:

- clean DOCX;
- review DOCX;
- report JSON.

Esta camada não usa filesystem, network, clock, random, UUID, locale, LLM ou serviços externos.

## 9. Imutabilidade

A entrada `package_snapshot` não pode ser modificada.

O Bundle não pode alterar:
- `ProcessingSessionResult`;
- `ProcessingReport`;
- `ReviewDocxResult`.

Os bytes devolvidos são os bytes produzidos pelas camadas congeladas; não há reempacotamento adicional.

## 10. Autoridade negativa

Product Output Bundle v0.1 NÃO:

- formata DOCX diretamente;
- abre ou escreve ZIP/XML;
- reanalisa o documento;
- reclassifica;
- cria Decisions;
- cria OperationPlan;
- executa SafetyGate;
- chama Patcher diretamente;
- cria TransformRecord diretamente;
- interpreta findings;
- traduz códigos para linguagem humana;
- calcula score/percentual de conformidade;
- renomeia arquivos;
- salva em disco;
- gera PDF/HTML;
- cria um ZIP com as três saídas;
- implementa UI/API HTTP.

## 11. Nomes de arquivos

Fora do v0.1. A camada entrega artefatos tipados/bytes; nomes user-facing serão responsabilidade posterior de delivery/UI.

## 12. Relatório human-readable

Fora do v0.1. O terceiro artefato é o JSON canônico congelado do Processing Report.

## 13. Compatibilidade com status da sessão

Todos os status válidos da Processing Session são publicáveis:

```text
quiescent
quiescent_with_unapplied
operation_limit_reached
```

O Bundle não transforma status e não interpreta `quiescent` como conformidade total.

## 14. Testes mínimos obrigatórios

1. fluxo real sem alteração;
2. fluxo real com bold aplicado;
3. fluxo real com font_size aplicado;
4. fluxo real com ReviewItem;
5. fluxo real com Patcher rejection/unapplied;
6. clean bytes == Session output bytes;
7. clean SHA binding;
8. report summary output SHA == clean SHA;
9. canonical report bytes == serializer real;
10. processing_report_ref == sha256(report bytes);
11. review input SHA == clean SHA;
12. review report_ref == report ref;
13. review output SHA == review bytes;
14. input snapshot não mutado;
15. profile não mutado;
16. determinismo same-process das três saídas;
17. caller binding order não muda resultado quando ProcessingProfile semanticamente equivalente;
18. `operation_limit_reached` preservado;
19. contract error upstream traduzido para ProductOutputBundleContractError;
20. integrity error upstream traduzido para ProductOutputBundleIntegrityError;
21. nenhum IO/network/clock/random/dynamic import no runtime;
22. regressão completa verde.

## 15. Critério de freeze

Product Output Bundle v0.1 só pode ser congelado após:

- implementação em branch/PR separado;
- testes reais das três saídas;
- auditoria estática do diff;
- CI completo verde no head do PR;
- squash merge;
- CI verde no `main` pós-merge;
- decisão de freeze subsequente;
- atualização de `docs/handoff.md`.

## 16. Dívidas explicitamente fora do freeze

- filenames e download packaging;
- renderer human-readable;
- UI/API HTTP;
- persistence/storage;
- ZIP de entrega com múltiplos arquivos;
- profile schema final/user-facing;
- localização/tradução de mensagens;
- P3/P4/italic e demais expansões do motor;
- secondary-story execution;
- `w:szCs` visual completeness.
