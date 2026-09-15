> Parecer do DeepSeek Flash 4.1 entregue por Felipe em 2026-09-14 e registrado aqui sem alteração. Após este parecer, L2 e L3 foram tratados no commit `8234d9d` do PR #59; ver a reauditoria `0059e-claude-opus-benchmark-diagnostics-reaudit.md`.

# Auditoria 0059D — diagnósticos do benchmark, commit `c47b6eb` (DeepSeek Flash 4.1)

**Commit auditado:** `c47b6ebc25a0b2cd11c224082f93a0571bf6bf23` (branch `implement/0059-benchmark-diagnostics`).
**Ambiente:** Python **3.12.13**, Darwin 25.6.0, arm64, `lxml` 6.1.3, zlib 1.2.12, macOS.
**Suíte:** **822 passed, 117 subtests** no repositório (804 anteriores + 18 novos). Nenhum arquivo do repositório foi alterado — leitura e execução de sondas com saída fora do repo; `git status` limpo (só o diretório privado pré-existente).

> Nota de método: na extração via `git archive` (sem `.git`), 1 teste falha por depender de `git status`; no repositório/CI ele passa. Isso é um achado de robustez do teste (L1), não do instrumento.

---

## Veredito

# APROVADO

A medição **não é materialmente contaminada** pelo mecanismo de diagnóstico e as etapas são **interpretáveis com clareza** (inclusivas + exclusivas + hierarquia declarada em `timing_semantics`). Os oito pontos do DeepSeek e os seis do Opus foram confirmados por execução. Restam apenas achados **baixos** e limitações já documentadas. A medição oficial pode começar.

---

## 1. Confirmações por execução

### DeepSeek

1. **Parse da pós-condição medido e separado do `parse`.** `engine.DocxParser` (rótulo `parse`) e `validation.DocxParser` (`postcondition_parse`) são ligações distintas. Em 6×2: `parse calls = 3` (changes+1), `postcondition_parse calls = 2` (changes), `postcondition_parse ≤ postcondition`. Em 200×40: `postcondition_parse = 40`. Nunca somados. **Confirmado.**

2. **`stage_seconds_exclusive` não fica negativo.** 6×2 → `decision` 0,010591; `patch_total` 0,006796; `postcondition` 0,000079. Em 200×40 → **nenhum bucket negativo**. Estruturalmente, `resolve_*` só é usado dentro de `_build_decisions` (`engine.py:175,211`) e os nomes `validation.*` só dentro de `verify_postcondition` (`validation.py:338-387`); os filhos são disjuntos e internos aos pais. **Confirmado.**

3. **Fronteiras de progresso fora de todos os cronômetros.** `install_progress` é a camada mais externa (`install_instrumentation` primeiro, `install_progress` depois); `count_patch` não escreve; `count_transform` chama `progress.end()` **depois** de o wrapper de tempo de `transform_record` retornar; `around("evaluation"/"report_build"/"review_docx_build")` não têm cronômetro. **Confirmado por inspeção e pelo fato de `decision`/`patch_total` não inflarem.**

4. **Mesmas gravações de progresso nas duas variantes, inclusive com patch rejeitado.** 6×2 → 16=16; DOCX com `<w:b/><w:b/>` (rejeição `duplicate_target_property`) + um defeito normal → **`applied_changes=1`, `unapplied_changes=1`, `outcome=quiescent_with_unapplied`, `progress_writes=17` em todas as 4 execuções**, sem divergência de equivalência. **Confirmado.**

5. **Undo exato e na ordem certa, mesmo com exceção.** Injetei `RuntimeError` em `build_product_from_inputs`; os 15 nomes instrumentados/progresso (`engine._evaluate/apply_cleared_operation/build_transform_record/DocxParser/resolve_run_formatting`, `validation.DocxParser/build_style_catalog/find_story/resolve_target`, `applicator.mutate_run/repackage/verify_postcondition`, `product_delivery.build_product_delivery`, `bundle_builder.build_processing_report/build_review_docx`) foram **todos restaurados**. **Confirmado.**

6. **Regra de parada após timeout/erro.** Com `repeats=3` e hold em `evaluation`: `planned_runs=6`, `runs=2` (uma por variante), `stopped_early=True`, `skipped_runs=4`. Não roda em excesso e **não apaga** o registro: `statistics` traz `complete_runs=0`, `incomplete_runs=1` por variante. **Aceitável.**

7. **`BENCHMARK_0059_TEST_HOLD_AFTER`.** O processo pai **nunca** o lê (não vaza para o pai); os workers o herdam via `{**os.environ}`. Ativação acidental é possível se a variável estiver no shell (documentada como proibida). **Achado baixo (L3).**

8. **`--docx` não grava/copia/registra conteúdo.** Roda in-place; registra só `label` (basename), tamanho e SHA-256; caminho absoluto apenas com `--record-docx-path`; em erro, só `error_type`/`error_code`. Verifiquei: DOCX válido → `quiescent`; com patch rejeitado → `quiescent_with_unapplied`; arquivo quebrado → `outcome=error`, `error_type=ProductInputBoundaryContractError`; **nenhum caminho nem texto do documento no JSON**. Mutação em disco checada (`input_unchanged_on_disk`). **Confirmado.**

### Claude Opus

1. **Inclusivo/exclusivo respondem sem ambiguidade.** `postcondition_share_of_patch_total` (0,459 em 6×2; 0,956 em 200×40) responde “quanto do patch é pós-condição”; e `postcondition` vs `postcondition_parse` (ex.: 0,009663 vs 0,003297) responde “quanto da pós-condição é parse”. **Confirmado.**
2. **ABBA + referência como total oficial.** `schedule` = `[ref, instr, instr, ref, …]`, determinístico, mediana por variante; `statistics.official_total_variant="reference"` e `instrumentation_overhead_median_seconds`. Resolve o viés de ordem; a variância residual fica exposta por `min/median/max`. **Adequado.**
3. **Progresso da referência preserva diagnóstico sem contaminar o tempo oficial.** Escritas idênticas entre variantes; o total oficial inclui apenas as escritas grosseiras (~16 no 6×2; ~centenas em casos grandes, dezenas de ms). Residual pequeno e documentado. **Adequado (observação O3).**
4. **Formato do JSON documentado.** `docs/benchmarks/0059-benchmark-tool.md` descreve modos, variantes, total oficial, ABBA, hierarquia, privacidade e comandos; o JSON repete tudo em `timing_semantics`. **Confirmado.**
5. **`--docx`: privacidade e distinção de desfecho.** `outcome` é o status da sessão, `timeout` ou `error`; terminar o processo não é sucesso. Verifiquei `quiescent`, `quiescent_with_unapplied` e `error`. **Confirmado.**
6. **Nenhum bloqueio para a linha de base sintética no Ubuntu.** `_environment` usa `/proc/meminfo` no Linux e `sysctl` no macOS; `ru_maxrss` convertido; CSV/log fora do repo; comando documentado. **Nada encontrado.**

---

## 2. Achados (todos baixos, nenhum bloqueia)

- **L1 — BAIXO — teste depende de `.git` sem skip.** `test_benchmark_0059.py::DocxModeTests::_git_status` roda `git status` em `ROOT` e falha com exit 128 fora de uma árvore git; só pula se o binário `git` não existe. Reprodução: rodar a suíte a partir de um `git archive`/sdist → 1 falha. Correção: pular quando `git rev-parse --is-inside-work-tree` falhar. (No repo/CI passa: **822**.)
- **L2 — BAIXO — `formatting_resolution` cobre só a fase de decisão.** O SafetyGate resolve formatação com bindings próprios (`safety_gate/gate.py:373-375`) **não instrumentados**; esse custo fica dentro de `safety_gate`. O doc não menciona. Correção: rotular `safety_gate_formatting_resolution` ou registrar que a resolução se divide entre `decision.formatting_resolution` e `safety_gate`.
- **L3 — BAIXO — `TEST_HOLD_ENV` herdado sem filtro.** O pai poderia removê-lo do `env` dos workers (só reintroduzir sob um modo de teste explícito), para impedir medição acidental travada por variável de ambiente.
- **L4 — BAIXO — `patches_completed` só aparece no progresso de timeout**, não no resultado de execuções completas.
- **L5 — BAIXO — `input_unchanged_in_memory` é trivialmente verdadeiro** (mesmo objeto `bytes` imutável); o check útil é `input_unchanged_on_disk`.

---

## 3. Limitações aceitas (documentadas)

- Montagem final do bundle (relatório, serializações, Review DOCX) sem cronômetro por etapa — entra no resíduo de `total_seconds`.
- `cpu` = `platform.processor()` sem modelo; `commit` não sinaliza árvore suja.
- Fixtures sintéticas exercitam só negrito (run); operações de parágrafo têm custo de patch próprio.
- Contagem de parágrafos/runs cobre só `word/document.xml`.
- Documento que estoura o prazo nas duas variantes gera diagnóstico de progresso, mas nenhum tempo total.

---

## 4. Melhorias opcionais

- Fazer o teste git-dependente pular fora de uma work tree (L1).
- Filtrar `TEST_HOLD_ENV` no pai salvo em teste (L3).
- Incluir `patches_completed` no resultado completo (L4).
- Usar uma fonte de CPU melhor e sinalizar árvore suja no `commit`.

---

## 5. Conclusão

- **Bloqueios para iniciar a medição oficial:** **nenhum.**
- **Lacunas de protocolo:** nenhuma relevante; apenas as observações L2/L4 (atribuição/documentação) e L1 (teste).
- **PR:** **pode ser mesclado.** Recomendo, sem bloquear, corrigir L1 (skip fora de work tree) e, se trivial, L3.
- **Alterações no repositório:** nenhuma. Sondas executadas com saída fora do repo; a única falha observada foi artefato da extração sem `.git`, inexistente no repo/CI (822 verdes).
