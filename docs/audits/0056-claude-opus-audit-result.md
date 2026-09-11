# Auditoria 0056 — indexação de alvos do SafetyGate e do Review DOCX (Claude Opus)

**Auditor:** Claude Opus 5
**Data:** 2026-09-11
**Alvo:** `226e87a600260fd895e230aac8857ce66fcafd44`, branch `perf/index-gate-review-targets-0056`, PR #43
**Head auditado:** `71bdd90206df6e1f7ea5558c7488826e5472c130` (inclui o brief)
**Base:** `a9b612af56b1eaca7d440d4c48ff47c498395e44`
**Suíte executada localmente:** **772 passed, 1 warning, 6.35s**
**Repositório não modificado durante a auditoria.** Sondas adversariais executadas fora da árvore; nenhum DOCX privado utilizado.

---

## Veredito

# APROVADO

A mudança é pequena, bem delimitada e não altera nenhuma decisão, veto, evidência, hash, ordem ou semântica de `ReviewMarkResult`. A equivalência entre `index_story_targets` e `resolve_target` foi verificada de forma exaustiva, não por leitura. Três ajustes menores recomendados; nenhum bloqueante.

---

## 1. Equivalência — verificada exaustivamente

**[FATO]** Construí uma história sintética com 14 registros e 12 caminhos distintos, cobrindo parágrafos, runs aninhados, tabela com célula e parágrafo interno, `run_container` de hyperlink e **dois caminhos deliberadamente duplicados**. Para **todos** os caminhos, comparei `resolve_target(story, p)` com `index_story_targets(story)[p]`:

```
registros percorridos: 14
caminhos distintos   : 12
divergencias: NENHUMA
duplicado /w:body/w:p[9]: resolve=2 index=2
caminho inexistente -> index: []  resolve: []
chaves do indice == caminhos percorridos: True
index_story_targets: SafetyGateContractError
resolve_target:      SafetyGateContractError
```

A comparação verificou, para cada posição da lista:

- **identidade de objeto** (`record_a is record_b`), não apenas igualdade — o índice referencia os mesmos mappings, sem cópia ou aliasing novo;
- **cadeia de ancestrais idêntica**, incluindo ordem outermost-first;
- **ordem da lista** preservada;
- **duplicatas preservadas** — 2 entradas dos dois lados;
- **caminho ausente** → `[]` nos dois;
- **conjunto de chaves** do índice igual ao conjunto de caminhos percorridos;
- **mesmo tipo de erro** quando `blocks` é malformado.

**[INFERÊNCIA]** As duas funções partilham `walk_records`, cuja travessia é determinística (`for key in sorted(node)`), então a equivalência não é acidental: o índice é uma reorganização da mesma travessia, filtrada por `isinstance(path, str)` em vez de por igualdade com um alvo. Como `walk_records` só emite nós que possuem `structural_path`, e o parser sempre os produz como `str`, o filtro é um superconjunto seguro do predicado original.

**Respostas diretas ao brief:**

| Pergunta | Resposta |
|---|---|
| 1. Mesmos registros e cadeias de ancestrais? | **Sim**, verificado por identidade de objeto |
| 2. Duplicatas continuam gerando `TARGET_NOT_UNIQUE`? | **Sim** — o índice devolve 2 entradas e `gate.py:457-463` mantém o `len(matches) > 1` intacto |
| 3. Índice stale, mutação, aliasing, uso entre snapshots? | **Não.** O índice é local a uma chamada de `evaluate_operation_plan`, construído a partir da `story` daquela avaliação e descartado ao fim. O Gate é puro e não muta registros. O aliasing é o mesmo de antes |
| 4. `gate_operation` permanece semanticamente igual? | **Sim.** `gate.py:672` chama `_gate_operation_local` sem `target_index`; o parâmetro tem default `None` e o caminho cai em `resolve_target` |
| 5. Review DOCX mantém candidatos, ordem e provas? | **Sim.** Só a origem dos `paragraph_matches` mudou; `len(...) != 1` e todas as verificações posteriores seguem idênticas |

---

## 2. Achados

### 🟡 M1 — O índice é construído incondicionalmente, antes do laço de operações

**Arquivo:** `safety_gate/gate.py:612` (`target_index = index_story_targets(story)` antes de `for operation in plan.operations`).

**[FATO]** `index_story_targets` valida `blocks` e levanta `SafetyGateContractError` quando ele não é lista/tupla. Antes, essa validação ocorria dentro de `resolve_target`, isto é, **apenas se houvesse ao menos uma operação**. Agora ocorre sempre.

**[FATO]** Plano vazio não é caso raro: é o caso normal de documento já conforme.

**[FATO]** O parser produz histórias com `status == "ok"` e `blocks = None` — `docx_parser.py:651` (`"status":"ok","blocks":None,"items":items,...`) e `:583`.

**[INFERÊNCIA]** Hoje é **inalcançável**: `gate.py:114` exige `plan.planned_story_part == PLANNED_STORY_PART` e `:671` fixa a mesma constante, e a história de `word/document.xml` sempre recebe `blocks` como lista (`docx_parser.py:683`). Mas a premissa "a história planejada sempre tem `blocks` lista" passa a estar embutida no caminho quente exatamente onde o roadmap pretende relaxá-la — execução em stories secundárias consta das expansões futuras do handoff.

**Impacto:** nenhum hoje; endurecimento silencioso de um contrato congelado (0026/0027), alcançável no dia em que stories secundárias entrarem no slice.

**Correção recomendada:** construir o índice apenas quando `plan.operations` for não vazio, ou registrar a premissa explicitamente no contrato. A primeira é uma linha e também evita percorrer a árvore inteira no caso mais comum de todos — documento conforme, plano vazio.

### 🟡 M2 — No Review DOCX, o índice ficou dentro de um `try` que não captura o erro que ele levanta

**Arquivo:** `review_docx/builder.py:236` (`target_index = index_story_targets(physical_story)` dentro do bloco `try`).

**[FATO]** O `try` captura `(KeyError, PatcherContractError, PatcherIntegrityError)` e reescreve como `ReviewDocxIntegrityError`. `index_story_targets` levanta `SafetyGateContractError`, que **não** está na tupla.

**[INFERÊNCIA]** O comportamento observável é idêntico ao anterior — antes, `resolve_target` era chamado fora do `try` e também propagava `SafetyGateContractError` crua. Não há regressão. O problema é de legibilidade defensiva: a colocação dentro do bloco sugere uma cobertura que não existe, e um leitor futuro que acrescente `SafetyGateContractError` à tupla mudará o comportamento sem perceber.

**Correção recomendada:** mover a construção do índice para fora do `try`, ou incluir `SafetyGateContractError` na tupla capturada e converter para `ReviewDocxIntegrityError` — o que, aliás, seria a fronteira de erro correta para uma API pública do Review DOCX.

### 🟡 M3 — O teste novo não sustenta a afirmação de equivalência

**Arquivo:** `tests/test_safety_gate_v01.py`, `test_story_target_index_preserves_path_resolution`.

**[FATO]** O teste compara **um único caminho** (o de um `run_raw`) entre índice e `resolve_target`.

**[INFERÊNCIA]** É a afirmação central do PR — "preserva a lista ordenada e todos os caminhos duplicados" — e o teste não exercita duplicatas, nem igualdade exaustiva sobre todos os caminhos, nem caminho ausente, nem paridade do erro de `blocks` malformado. Um erro de agrupamento que afetasse apenas caminhos duplicados passaria verde.

**Correção recomendada:** teste que percorra `walk_records` da fixture, e para **todo** caminho afirme `index[p] == resolve_target(story, p)` com identidade de objeto, mais fixture com caminho duplicado afirmando 2 entradas e `TARGET_NOT_UNIQUE` a jusante, mais caminho ausente e `blocks` malformado. É o probe que executei nesta auditoria e pode ser doado como teste.

---

## 3. Sobre o ganho medido e o risco

**A redução justifica o risco? Sim, com folga.** O risco é próximo de zero — reorganização de uma travessia determinística compartilhada, sem novo aliasing, sem estado entre chamadas —, e o ganho é estrutural: `resolve_target` era chamado uma vez por operação, cada chamada percorrendo a árvore inteira, ou seja `O(N·T)`; o índice torna isso `O(T)` por avaliação. A metodologia (`cProfile` sobre o mesmo DOCX, mesma operação, antes e depois) é válida para o que mede.

**Mas o número não deve ser lido como "desempenho resolvido".** Os 15,7 → 6,8 s são **por uma alteração**. `processing_session/engine.py:459-460` refaz o pipeline completo a cada patch aplicado:

```python
while True:
    evaluation = _evaluate(current_bytes, profile)
```

Para um documento com N correções, o custo permanece N × pipeline completo. Uma tese com 300 parágrafos a corrigir sai de aproximadamente 78 minutos para aproximadamente 34 — melhor, e ainda inviável para uso real.

**[RECOMENDAÇÃO]** Integrar este PR pelo que ele é: uma otimização correta e barata. E registrar no handoff que o custo dominante é o re-run por patch, congelado em 0032/0033, e que atacá-lo é uma conversa de arquitetura própria — não deste ciclo. Sem esse registro, o número 6,8 s corre o risco de ser lido como capacidade de produção.

**Observação de memória:** o índice retém `O(T)` tuplas mais as cadeias de ancestrais durante a avaliação, e é reconstruído a cada iteração da sessão. O tamanho é irrelevante; o churn por iteração só passa a importar se o re-run for atacado.

---

## 4. Contratos

**[FATO]** Comparei com 0026/0027 (SafetyGate) e 0036/0037 (Review DOCX).

- nenhuma `GateReason`, `GateStatus` ou evidência muda;
- `TARGET_NOT_UNIQUE`, `TARGET_NOT_FOUND` e `TARGET_TYPE_MISMATCH` preservados;
- ordem de `results` e `cleared` inalterada — o laço sobre `plan.operations` é o mesmo;
- nenhum hash, `operation_ref`, `decision_ref` ou prova de emissão é tocado;
- `ReviewMarkResult` e a política do primeiro run marcável intactas;
- nenhum efeito sobre `word/document.xml`, histórias, tabelas, hyperlinks, runs aninhados ou seleção de candidatos de parágrafo — verificado pela sonda, que cobre essas formas.

**Nenhuma emenda contratual é necessária.** O handoff deve registrar a otimização e a ressalva da seção 3.

---

## 5. Sequência recomendada

1. M1 — condicionar a construção do índice a plano não vazio *(uma linha; também evita trabalho no caso mais comum)*;
2. M3 — substituir o teste pontual pelo exaustivo, com duplicata e caminho ausente;
3. M2 — reposicionar ou capturar corretamente em `review_docx/builder.py`;
4. registrar no handoff o ganho **e** o limite do ganho.

Com 1 a 3 aplicados, integrar. Se preferir integrar já e tratar os três num PR de acompanhamento, também é defensável: nenhum deles altera comportamento observável hoje.
