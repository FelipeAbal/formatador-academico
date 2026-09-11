# Auditoria 0056 — revisão adversarial (DeepSeek Flash 4.1)

**Objeto:** `71bdd90206df6e1f7ea5558c7488826e5472c130` (código em `226e87a`, docs em `71bdd90`; base `main` = `a9b612a`).
**Método:** a árvore de trabalho foi movida externamente para `main` durante a sessão, então extraí a versão auditada com `git archive 71bdd90` para um diretório temporário — **não alterei o repositório** (`git status` só mostra o diretório privado pré-existente `Para teste formatador/`). Rodei a suíte no commit exato (**772 passed, 89 subtests**), sondas de equivalência, igualdade de saída e benchmarks. Usei os DOCX reais apenas em leitura, sem copiá-los nem reproduzir seu conteúdo.

---

## 1. Veredito geral

**APROVADO COM AJUSTES.**

Não encontrei defeito de correção. O índice é semanticamente equivalente a `resolve_target` para todos os casos testados, não altera hash, evidência, veto, decisão nem `GateClearedOperation`, e a otimização é um ganho real e bem isolado. Os ajustes são de **cobertura de teste, documentação de escopo e um comportamento de borda** — nenhum bloqueante.

---

## 2. Achados por gravidade

### A1 — Baixa (mudança de comportamento observável): plano vazio passou a validar `blocks` ansiosamente

- **Arquivo/função:** `src/formatador_academico/safety_gate/gate.py:611-612` (`evaluate_operation_plan` chama `index_story_targets(story)` incondicionalmente após o veto global).
- **Reprodução:** IR com `stories[0]["status"]=="ok"` mas `blocks=None`, plano com `operations == ()`.
  - Antes (emulado com `gate.index_story_targets = lambda s: None`): retorna `SafetyGateReport` com `results=()`.
  - Agora: `SafetyGateContractError: current story lacks a blocks sequence`.
- **Impacto:** para planos sem operações e story estruturalmente inválida, o gate agora lança em vez de devolver relatório vazio. Só alcançável com IR forjado (o parser produz `blocks` quando `status=="ok"`), e é mais fail-fast que antes; porém é uma mudança de contrato não documentada nem testada.
- **Correção recomendada:** ou (a) só construir o índice quando `plan.operations` for não vazio (`if plan.operations: target_index = index_story_targets(story)`), ou (b) documentar/assumir explicitamente a validação antecipada e adicionar teste para plano vazio + story inválida.

### A2 — Média-baixa (lacuna de teste): o teste novo cobre só um caminho

- **Arquivo:** `tests/test_safety_gate_v01.py:327-333`.
- **Observado:** `test_story_target_index_preserves_path_resolution` compara `indexed[path] == resolve_target(story, path)` para **um único** `structural_path` de run, não duplicado.
- **Impacto:** um erro de ordenação em caminhos duplicados, perda de caminhos ausentes, índice vazio, ou divergência de ancestrais em containers/tabelas não seria capturado por esse teste. O caminho indexado do gate é exercitado indiretamente por vários testes de `evaluate_operation_plan` (ex.: `test_hyperlink...` via `_evaluate`, `test_partial_clearance` para `PHYSICAL_HASH_MISMATCH`, `test_empty_plan`), mas **`TARGET_NOT_FOUND` e `TARGET_NOT_UNIQUE` são asseverados só via `gate_operation`** (caminho direto, sem índice). O caminho de Review DOCX é bem coberto pelos testes existentes de parágrafo.
- **Correção recomendada:** ver seção 4 (testes adicionais).

### A3 — Baixa (custo residual, informativo): índice para 0–1 operações

- **Arquivo/função:** `targets.py:index_story_targets` (uma caminhada completa) vs `resolve_target` (uma caminhada por consulta).
- **Observado:** medição sintética — construir o índice custa ≈ **1,2×** uma única `resolve_target`. Para plano com 0 operações, o índice é trabalho extra; medi no documento mínimo de 1 parágrafo/0 operações **+0,05 ms (~4% do total)**. Para 1 operação, o custo é praticamente neutro.
- **Impacto:** desprezível; o ganho só aparece com M ≥ 2 operações, o que domina no uso real.
- **Correção recomendada:** nenhuma obrigatória; se quiser, condicionar a construção a `plan.operations`.

### A4 — Sugestão (encapsulamento/documentação)

- `index_story_targets` não é exportado por `safety_gate/__init__.py` (é interno), mas tem nome público. Como é uma aceleração **local à avaliação** e não deve ser reutilizada entre snapshots, sugiro renomear para `_index_story_targets` e/ou registrar no docstring a invariante "build-and-consume local; nunca cachear entre snapshots". Não é defeito.

**Nenhum defeito de correção, segurança, preservação de DOCX, determinismo ou contrato foi encontrado.**

---

## 3. Respostas às perguntas A–E

| # | Pergunta | Resultado |
|---|---|---|
| 1 | Índice == `resolve_target`? | **Sim.** Comparei todos os `structural_path` de IRs com parágrafos, runs, `text_fragment`, tabela, `run_container`/hyperlink: 0 divergências, incluindo cadeia de ancestrais idêntica. |
| 2 | Ordem preservada? | **Sim.** `index_story_targets` usa o mesmo `walk_records` (mesma ordem de `sorted(keys)` e de listas), inserindo em ordem. |
| 3 | Duplicados → `TARGET_NOT_UNIQUE`? | **Sim.** Verificado com IR duplicado: relatório serializado byte-idêntico ao caminho sem índice, `reasons=(TARGET_NOT_UNIQUE,)`. |
| 4 | Perde tabelas/hyperlinks/containers? | **Não.** É o mesmo walk. Confirmei que tabelas e `run_container` (hyperlink) aparecem no índice com ancestrais corretos. |
| 5 | `.get(path, [])` para inexistente? | **Sim.** Ausente ⇒ `[]` == `resolve_target`, tanto no gate (`TARGET_NOT_FOUND`) quanto no Review DOCX (`len != 1` ⇒ erro). |
| 6 | Índice stale entre snapshots? | **Não no uso atual.** Reconstruído a cada `evaluate_operation_plan`/`build_review_docx` e consumido no mesmo escopo, sem mutação do IR. Risco latente apenas se reutilizado após mutação estrutural (ver A4). |
| 7 | Mutação/aliasing do PhysicalIR? | **Não.** `index_story_targets` só lê e cria dict/listas novas; armazena referências, não altera registros. |
| 8 | Ancestrais de run corretos? | **Sim.** Cadeia `paragraph → run_container → run_raw` idêntica; `paragraph_ancestor` resolve o parágrafo real via índice. |
| 9 | Muda hash/evidência/veto/decisão/token? | **Não.** `serialize_safety_gate_report` **byte-idêntico** entre caminho indexado e o emulado sem índice, nos cenários normal, duplicado, não-encontrado e veto global. `GateClearedOperation` (op, refs, `current_package_sha256`, `_proof`) inalterado. |
| 10 | `gate_operation` equivalente ao plano? | **Sim.** Para cada operação, `_gate_operation_local(..., idx)` == `(..., None)` == `gate_operation(...)`, com mesmo `status/reasons/evidence`; token corresponde à mesma operação. |
| 11 | Review DOCX preserva candidatos/ordem? | **Sim.** Índice construído após `_collect_candidates`, sem tocar candidatos nem a ordem de marcação. |
| 12 | Review detecta não-encontrado/não-único? | **Sim.** Mesma checagem `len(paragraph_matches) != 1` ⇒ `ReviewDocxIntegrityError`; o `resolve_structural_path` no lxml continua detectando ausência. |
| 13 | História errada? | **Não.** Índice é da story de `DOCUMENT_PART` (`find_story`), como antes. |
| 14 | Compatível com `physical_hash`, 1º run marcável, run+parágrafo? | **Sim.** O índice só fornece o `paragraph_record`; `physical_hash`, seleção do primeiro run e coexistência de candidatos permanecem inalterados (testes existentes passam). |
| 15 | Determinismo e DOCX limpo? | **Sim.** Em caso real com 2 mudanças de parágrafo, `output_review_package_bytes` e `mark_results` **byte-idênticos** com índice vs `resolve_target`; o pacote limpo não é tocado. |

**Bônus 16 (cobertura):** o índice é exercitado por muitos testes de `evaluate_operation_plan` (cleared, `PHYSICAL_HASH_MISMATCH`, plano vazio, hyperlink), mas faltam equivalência explícita para duplicado, ausente, índice vazio e comparação plano-vs-unitário. Ver seção 4.

**E 18–20:** ver seção 5.

---

## 4. Testes adicionais recomendados (mínimos)

1. `index_story_targets` vs `resolve_target` para **caminho duplicado** (2 blocos iguais) e para **caminho ausente**.
2. **Índice vazio:** story com `blocks == []` ⇒ `{}`; e `blocks` inválido ⇒ `SafetyGateContractError`.
3. **Equivalência plano vs unitário:** para cada tipo de veto local (`TARGET_NOT_FOUND`, `TARGET_NOT_UNIQUE`, `TARGET_TYPE_MISMATCH`, `PHYSICAL_HASH_MISMATCH`, `CURRENT_VALUE_UNAVAILABLE`, `PRECONDITION_MISMATCH`) comparar `evaluate_operation_plan(...)` (índice) com `gate_operation(...)` (direto), exigindo `status/reasons/evidence` iguais.
4. **Igualdade de relatório:** serializar `evaluate_operation_plan` com e sem índice (emulando sem índice) e exigir bytes idênticos — bom teste de regressão que protege a equivalência.
5. **Ancestrais em container/tabela:** percorrer todos os `structural_path` de IR com hyperlink + tabela e exigir `index[p] == resolve_target(story, p)`.
6. **Plano vazio + story sem `blocks`:** fixar o comportamento desejado (retornar vazio ou lançar) — hoje não testado (A1).

---

## 5. Avaliação do ganho de desempenho

**O ganho é real e a otimização é correta e isolada.** Reproduzi independentemente na mesma corpus (mediana de 3 execuções, **sem cProfile**, emulando o comportamento anterior por monkeypatch `index_story_targets → None` no gate e um resolvedor preguiçoso no Review):

| Documento (≈50 KB) | Antes (mediana) | Depois (mediana) | Ganho |
|---|---:|---:|---:|
| A Boca da Lei Feita Máquina | 5,385 s | 3,094 s | 42,5% |
| Artigo Claudir | 3,068 s | 1,811 s | 41,0% |
| Diovana | 5,130 s | 2,578 s | 49,7% |

Bate em direção e magnitude com os 57% relatados. Em nível de componente, o ganho é superlinear: benchmark sintético de 2.000 parágrafos/2.000 consultas → `resolve_target` 42,1 s vs índice 0,025 s (~**1.700×**); construir o índice custa ≈1,2× uma única `resolve_target`.

**Validade metodológica do número original:** direção correta, mas a medição do briefing é fraca — execução única por versão, sob `cProfile` (instrumentação distorce custos relativos de forma não uniforme), sem repetições/mediana/aquecimento, corpus privado e versões provavelmente não intercaladas. O próprio briefing reconhece isso. O harness `tools/measure_real_docx.py` é um bom ponto de partida, mas mede só tempo total, sem repetições nem A/B; não isola a contribuição causal do índice.

**Custos que ainda dominam** (cProfile pós-otimização, documento de 50 KB, `max_applied_operations=1`):
- `serialize_decision`/`_jsonable`: ~2,7 s acumulados em **27.765 chamadas** (serialização redundante para `decision_ref`/`source_decisions_hash`/dedup);
- `DocxParser.parse_bytes`: ~1,8 s, com **reparsing completo a cada reavaliação** e no Review;
- `build_operation_plan`/`decision_ref`: ~1,0–1,4 s;
- `evaluate_operation_plan` (o gate): ~1,0 s — **não é mais o gargalo**.

Ou seja: a indexação resolveu o termo O(M·N) do gate, mas o custo dominante continua sendo a **reavaliação sequencial completa** e a **serialização/hash repetida das mesmas decisões** — consistente com a dívida já registrada no handoff.

**Isolamento:** a mudança fica em `safety_gate/targets.py`, `safety_gate/gate.py` e `review_docx/builder.py`, ambos internos. Não altera tipos públicos, serialização, autorização, classificação, hashes, vetos nem o pacote limpo. Pode ser integrada sem emenda de contrato.

---

## 6. Pode seguir para auditoria completa do Claude Opus?

**Sim.** O PR é seguro e semanticamente equivalente, e o ganho é verificável. Recomendo que a auditoria completa do Claude Opus:

1. confirme a equivalência com foco nos casos **duplicado/ausente/índice vazio** (A2);
2. delibere sobre o comportamento de **plano vazio + story inválida** (A1) — retornar vazio (comportamento anterior) ou documentar o fail-fast novo;
3. registre a natureza **evaluation-local** do índice (A4) para impedir reuso entre snapshots no futuro.

Nada aqui exige redesenho; são ajustes de teste/documentação e um comportamento de borda. **Não há bloqueio.**