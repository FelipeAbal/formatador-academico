# Decisão 0039 — Product Output Bundle v0.1 — freeze

Status: **FROZEN**

Date: 2026-09-09

## 1. Objeto congelado

Esta decisão congela a implementação do **Product Output Bundle v0.1**, contratada em 0038.

Fronteira pública:

```python
build_product_output_bundle(
    package_snapshot: bytes,
    profile: ProcessingProfile,
    *,
    max_applied_operations: int = DEFAULT_MAX_APPLIED_OPERATIONS,
) -> ProductOutputBundle
```

O Bundle é a primeira fronteira única de produto que entrega, em uma chamada, os três artefatos centrais do MVP:

1. clean DOCX;
2. review/highlight DOCX;
3. Processing Report JSON canônico + objeto tipado.

## 2. Evidência de implementação

- contrato: decisão 0038;
- PR: #14 — `Product Output Bundle v0.1`;
- head final auditado do PR: `c4dd6ed6792cd1f88d58159c7640ac78b1b2ce1d`;
- squash merge em `main`: `f87ea08511febd403b75874771ed5aff5db59fc9`;
- arquivos de runtime novos:
  - `src/formatador_academico/product_output_bundle/__init__.py`;
  - `src/formatador_academico/product_output_bundle/builder.py`;
  - `src/formatador_academico/product_output_bundle/model.py`;
- testes dedicados: `tests/test_product_output_bundle_v01.py`.

## 3. Validação

CI no head final do PR:

```text
644/644 OK
failures: 0
errors: 0
```

CI no `main` pós-merge, run #28, SHA `f87ea08511febd403b75874771ed5aff5db59fc9`:

```text
Ran 644 tests in 6.326s
OK
```

Nenhuma regressão das camadas congeladas anteriores foi detectada.

## 4. Contrato efetivamente implementado

Pipeline do Bundle:

```text
package_snapshot + ProcessingProfile
→ process_document
→ ProcessingSessionResult
→ clean DOCX
→ build_processing_report
→ ProcessingReport
→ serialize_processing_report
→ canonical report JSON
→ build_review_docx(clean DOCX, ProcessingReport)
→ review DOCX
→ ProductOutputBundle
```

A camada não abre nem modifica OOXML/ZIP diretamente e não cria nova autoridade normativa.

## 5. Binding congelado

Antes de publicar um Bundle, a implementação prova:

- SHA do input contra a Processing Session;
- SHA dos clean bytes contra o output da Session;
- lineage input/output do Processing Report contra a Session/clean DOCX;
- JSON do relatório contra o serializer canônico;
- `processing_report_ref` contra os bytes JSON;
- input SHA do Review DOCX contra o clean DOCX;
- `processing_report_ref` do Review contra o relatório;
- SHA do review DOCX contra seus bytes;
- versões públicas das três camadas.

Além disso, o próprio `ProductOutputBundle` é self-binding: construção manual não pode substituir silenciosamente JSON/report/profile/clean snapshot por artefatos inconsistentes.

## 6. Atomicidade de produto

A fronteira publica somente o Bundle completo. Falha na Session, Report, Review ou em qualquer prova de lineage impede retorno parcial.

Isso não altera a semântica interna das camadas upstream; apenas define o que esta fronteira considera uma saída completa de produto.

## 7. Erros congelados

```text
ProductOutputBundleError
├── ProductOutputBundleContractError
└── ProductOutputBundleIntegrityError
```

Erros upstream de contrato/integridade são traduzidos para a fronteira correspondente com causa preservada. Programming errors inesperados continuam fail-fast.

## 8. Determinismo e autoridade negativa

O runtime novo não usa filesystem, network, clock, random, UUID, locale, LLM ou serviços externos.

O Bundle NÃO:

- formata diretamente;
- reanalisa/reclassifica/redecide;
- cria OperationPlan/SafetyGate/Patch/TransformRecord por conta própria;
- interpreta findings;
- calcula score de conformidade;
- gera nomes de arquivos;
- salva artefatos;
- gera ZIP de entrega;
- implementa UI/API HTTP;
- renderiza relatório human-readable.

## 9. Casos reais validados

Foram testados no Bundle, usando as camadas reais:

- documento sem alteração;
- bold aplicado;
- font_size aplicado;
- ReviewItem;
- rejeição real do Patcher por propriedade duplicada;
- `operation_limit_reached`;
- equivalência sob ordem de bindings;
- imutabilidade de input/profile;
- repetição byte-determinística das três saídas;
- erros de contrato e integridade;
- tentativas de fabricar Bundle com JSON/profile/clean lineage divergentes.

## 10. Dívidas que permanecem fora deste freeze

- schema de perfil user-facing/final;
- ingestão/validação de perfil vindo de formulário/JSON;
- nomes de arquivos e camada de download/delivery;
- relatório human-readable;
- UI/API HTTP;
- persistence/storage;
- ZIP opcional de entrega;
- expansão do motor para P3/P4/italic e demais regras;
- secondary-story execution;
- `w:szCs` visual completeness.

## 11. Regra de reabertura

0039 só deve ser reaberta por:

- falha de teste/regressão;
- impossibilidade técnica demonstrada;
- contradição com contrato congelado;
- mudança explícita de escopo/API;
- novo risco de segurança ou integridade.

Expansões user-facing devem preferencialmente ser novas decisões/camadas, não alterações silenciosas neste freeze.
