# Decisão 0029 — Freeze do Patcher/Applicator v0.1

Status: **FROZEN**

Date: 2026-09-08

## 1. Escopo congelado

O Patcher/Applicator v0.1 é a primeira camada autorizada a produzir bytes DOCX modificados a partir de uma operação previamente liberada pelo SafetyGate.

Fronteira pública:

```text
package_snapshot: bytes
+ GateClearedOperation
→ PatchResult
```

Primeiro slice executável congelado:

```text
P1 / run / bold
P2 / run / font_size
```

Uma chamada aplica exatamente uma `GateClearedOperation`.

## 2. Pipeline real congelado

```text
DOCX
→ Parser
→ Analysis
→ Classification
→ Decision
→ OperationPlan
→ SafetyGate
→ GateClearedOperation
→ Patcher
→ patched DOCX bytes
```

## 3. Segurança / snapshot

Antes de abrir XML:

```text
sha256(package_snapshot)
==
GateClearedOperation.current_package_sha256
```

Mismatch → `rejected/snapshot_hash_mismatch`, sem output.

O patcher não trata a existência do token como prova suficiente de gating. Revalida tipo, slice executável, target path e `physical_hash` com semântica pública do parser.

Depois de snapshot match, divergência de path/type/hash é `PatcherIntegrityError`, não ordinary rejection.

## 4. Parser public API aditiva

Congelada uma superfície pública para evitar drift entre parser e executor:

```text
canonical_xml(node)
inherited_xml_attrs(node)
physical_hash(canonical_xml, inherited)
structural_path(node, root)
resolve_structural_path(root, path)
```

Os quatro primeiros delegam à semântica congelada do Parser v0.4.0.

`resolve_structural_path` é o inverso dedicado do path físico e NÃO é XPath. Resolve passo a passo por QName real e índice 1-based entre irmãos homônimos. O hardened head corrige URIs de namespace que contêm `/`.

## 5. XML / OOXML

- lxml autoritativo;
- sem python-docx para save;
- DTD/DOCTYPE rejeitado;
- `resolve_entities=False`, `no_network=True`, `recover=False`;
- sem `cleanup_namespaces()`;
- serialização em nível `ElementTree`;
- comentários/PIs de prólogo/epílogo preservados;
- encoding físico preservado, inclusive UTF-16;
- declaração XML preservada semanticamente e, quando existente, sua forma lexical é preservada no hardened head;
- XML sem declaration não ganha declaration apenas por causa de BOM/encoding.

## 6. Target e forma física

Target executável v0.1 deve ser `w:r` real em `word/document.xml`.

Buscas de `w:rPr`, `w:b` e `w:sz` são exclusivamente em filhos diretos.

`w:rPrChange` e conteúdo histórico aninhado permanecem protegidos e não contam como propriedade direta.

Reject `noncanonical_run_properties` quando:
- há mais de um direct `w:rPr`;
- o único `w:rPr` não é o primeiro filho elemento de `w:r`;
- há direct `mc:AlternateContent` no `w:rPr` alvo;
- filhos preexistentes de `w:rPr` estão fora da ordem canônica congelada;
- há propriedade fora da rank table v0.1.

Duplicata direta da propriedade alvo (`w:b` ou `w:sz`) → `duplicate_target_property`, inclusive quando lexicalmente idêntica.

## 7. Ordem canônica de rPr

Congelada a rank table ECMA-376/CT_RPr usada para inserção mínima.

Regra:
1. nunca mover sibling existente;
2. inserir antes do primeiro child de rank maior;
3. senão append;
4. `rPrChange` fica naturalmente ao fim da ordem.

Forma preexistente fora da ordem não é reparada: é rejeitada.

## 8. Bold

Output canônico:

```text
true  → <w:b/>
false → <w:b w:val="0"/>
```

Para `false`, remover `w:b` é proibido porque ausência pode reexpor bold herdado/toggle da cascata.

## 9. Font size

Entrada: `LengthValue(value, unit="pt")`.

Conversão:

```text
half_points = points * 2
```

Requisitos:
- Decimal;
- unit `pt`;
- finito;
- > 0;
- `points*2` inteiro exato;
- sem rounding;
- máximo 3276 half-points;
- lexical inteiro canônico.

`w:szCs` nunca é alterado no v0.1.

## 10. ZIP / package

Somente `word/document.xml` pode ter payload diferente.

Preservados:
- entry set;
- entry order;
- filename;
- date_time;
- compress_type;
- external_attr;
- internal_attr;
- create_system;
- per-entry comment;
- directory identity;
- archive comment;
- untouched part payload bytes.

ZipInfo é reconstruído por allowlist; CRC/compress_size/header_offset/stale extras não são copiados cegamente.

Compresslevel é fixo; não há relógio no runtime do patcher.

## 11. Allowed-delta / postcondition

Antes de `applied`:

1. output é relido do ZIP produzido;
2. árvores original/output são comparadas após neutralizar somente a propriedade alvo e wrapper `w:rPr` estritamente necessário;
3. restante do documento deve ser c14n-equivalente;
4. prólogo/epílogo e docinfo relevante são comparados separadamente;
5. propriedade final deve ter forma e posição canônicas;
6. package scope é revalidado;
7. output passa novamente por Parser → StyleCatalog → Analysis;
8. valor semântico atual deve ser exatamente o `desired_value`.

Delta extra ou postcondition divergente → `PatcherIntegrityError`.

## 12. PatchResult

`PatchStatus = applied | rejected`.

`PatchResult` frozen carrega:
- patcher_version;
- status;
- operation_ref;
- operation_plan_ref;
- input_package_sha256;
- output_package_sha256 | None;
- output_package_bytes | None;
- reason | None;
- changed_part | None.

Invariante hardened:

```text
output_package_sha256 == sha256(output_package_bytes)
```

para qualquer resultado `applied`.

## 13. Error model

Ordinary rejection vocabulary v0.1:
- `snapshot_hash_mismatch`;
- `unsupported_operation`;
- `noncanonical_run_properties`;
- `duplicate_target_property`;
- `unrepresentable_value`.

API misuse → `PatcherContractError`.

Drift/serializer/package/postcondition/internal integrity → `PatcherIntegrityError`.

## 14. Single-operation semantics

Após a primeira aplicação, package hash e normalmente physical hashes mudam. Tokens adicionais do mesmo SafetyGate report ficam stale.

É proibido iterar `cleared_operations` e aplicar sequencialmente sem reexecutar pipeline/gate.

Isso é limitação intencional do v0.1, não bug.

## 15. Auditorias e hardening

Contrato 0028 foi auditado adversarialmente por Claude Opus antes da implementação.

Achados incorporados antes do código:
- ordem schema de `w:rPr`;
- direct-child-only + proteção de `w:rPrChange`;
- ElementTree/prolog/docinfo;
- error model fail-fast;
- parser public API;
- proibição nominal de XPath;
- dívida `w:szCs`.

PR #9 foi implementado por Kimi K3 e auditado novamente por ChatGPT.

Hardening adicional aplicado diretamente na branch antes do merge:
1. `resolve_structural_path` passou a suportar namespace URI contendo `/`;
2. serialização passou a preservar encoding físico real, inclusive UTF-16;
3. XML UTF-16 sem declaration não ganha declaration;
4. `PatchResult` passou a vincular `output_package_sha256` aos bytes reais.

## 16. Testes finais

Head final auditado/hardened:

`2d8b9c48a0831a361dc8a152e6a1a876b2318a56`

PR #9 squash merge:

`559cf8ec812320d066e8b91d431873f7a91f2c1c`

Suite final:
- **502 testes descobertos**;
- **502/502 OK**;
- failures: 0;
- errors: 0;
- skips: 0;
- repetida **3 vezes**, resultados idênticos.

Casos adversariais finais verdes incluem:
- namespace URI com `/`;
- UTF-16 com declaration + standalone;
- UTF-16 sem declaration;
- PatchResult SHA self-consistency;
- prolog comment/PI preservation.

O flake anterior do helper sintético `build_docx` foi removido fixando metadata temporal do ZIP sintético; não houve regressão nos 442 testes anteriores.

## 17. Dívidas que permanecem

- `w:szCs` não é modelado/mutado; não usar o slice de font_size como garantia de renderização para complex-script até contrato específico;
- multi-operation transaction;
- TransformLog;
- clean/review/report orchestration;
- semantic equivalence para package byte-diferente;
- secondary-story execution;
- spacing/alignment patching;
- styles.xml patching.

## 18. Freeze

**Patcher/Applicator v0.1 está congelado.**

Mudanças semânticas exigem nova decisão/versionamento.

Próximo estágio deve começar por contrato, não por implementação.