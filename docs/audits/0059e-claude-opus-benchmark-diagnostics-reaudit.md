# Reauditoria 0059E — correções pós-DeepSeek do benchmark, PR #59 em `8234d9d` (Claude Opus)

**Auditor:** Claude Opus 5
**Data:** 2026-09-14
**Alvo:** PR #59, branch `implement/0059-benchmark-diagnostics`, head `8234d9d5dcf087688ceb1b411527d58e1885a8f5`
**Mudança auditada:** quatro commits desde `c47b6eb` — `f0e9405`, `d3634b5`, `344c719`, `8234d9d` — em `tools/benchmark_0059.py`, `tests/test_benchmark_0059.py`, `docs/benchmarks/0059-benchmark-tool.md` e no brief 0059D (+41/−8)
**Base:** `main` @ `99cde01`
**Suíte executada localmente:** **822 testes OK** em Python 3.12.13 com `lxml` 6.1.3, pelo comando do CI (`unittest discover -s tests`); CI do PR aprovado
**Repositório não modificado.** Sondas fora da árvore; uma verificação usou uma extração por `git archive` em diretório temporário.

**Independência.** O código-base deste PR (`c47b6eb`) foi escrito por mim, por isso minha leitura dele não é independente; a auditoria independente dessa base foi a do DeepSeek. Os quatro commits auditados aqui são do ChatGPT.

---

## Veredito

# APROVADO

As três correções aceitas para antes da medição — L2, L3 e L1 — estão implementadas e **foram verificadas por execução**. Nada impede o merge nem a linha de base sintética. Restam dois ajustes menores, que podem entrar no mesmo PR se for conveniente.

---

## Verificações

### L2 — resolução de formatação do SafetyGate: corrigido

**[FATO]** `gate.resolve_run_formatting` e `gate.resolve_paragraph_formatting` estão envolvidos como `safety_gate_formatting_resolution`, e `STAGE_HIERARCHY` ganhou `safety_gate ⊃ safety_gate_formatting_resolution`.

**[FATO]** Esses são os nomes efetivamente exercitados. Em `safety_gate/gate.py`, a resolução acontece em `_current_semantic_value` (linhas 373 e 375), chamada por operação dentro de `_gate_operation_local`, no laço `for operation in plan.operations` (linhas 618-619).

**[FATO] Medido**, 40 parágrafos, variante instrumentada:

```
alteracoes= 5 | gate_resolucao chamadas= 15 | gate chamadas= 6 | gate exclusivo=0.0368s
alteracoes=10 | gate_resolucao chamadas= 55 | gate chamadas=11 | gate exclusivo=0.0657s
alteracoes=20 | gate_resolucao chamadas=210 | gate chamadas=21 | gate exclusivo=0.1352s
```

As chamadas seguem **exatamente `n(n+1)/2`**: a cada iteração, o gate resolve de novo a formatação de todas as operações ainda pendentes. Com 160 alterações, isso daria 12.880 resoluções. O rótulo agora captura esse crescimento quadrático, que antes ficava escondido dentro de `safety_gate`. O tempo exclusivo do gate não ficou negativo em nenhum caso.

**Estes tempos verificam o instrumento; não são medição oficial.** O peso relativo desse custo em documentos grandes é justamente o que a linha de base precisa medir.

### Restauração dos nomes em exceção: confirmada

**[FATO]** Com instrumentação instalada e um pacote inválido, `_run_pipeline` levantou `ProductInputBoundaryContractError`. Depois disso, `gate.resolve_run_formatting`, `gate.resolve_paragraph_formatting`, `engine.evaluate_operation_plan` e `engine.DocxParser` eram **idênticos por identidade** aos originais.

### L3 — variável de teste fora das medições: corrigido

**[FATO]** `_spawn` copia o ambiente e remove `BENCHMARK_0059_TEST_HOLD_AFTER`, exceto com `allow_test_hooks=True`. `run_suite` e `run_docx_suite` **nunca** passam essa permissão.

**[FATO] Medido**, com a variável definida no processo principal:

```
medicao normal com a variavel no pai -> complete=True outcome=quiescent em 0.2s
controle: allow_test_hooks=True      -> complete=False outcome=timeout last_completed_stage=evaluation em 8.0s
```

Uma variável esquecida no shell não trava mais a linha de base.

### L1 — teste fora de repositório git: corrigido

**[FATO]** Numa extração por `git archive`, sem `.git`:

```
test_docx_mode_measures_a_file_in_place_without_copying_it ... skipped 'test root is not a git work tree'
test_docx_mode_records_errors_without_messages ... ok
```

### L4 — `patches_completed`: incorporado

Execuções completas registram `patches_completed`, e o teste exige que seja igual às alterações aplicadas na fixture mínima.

---

## Achados menores

### M1 — `\n` literal na documentação da ferramenta

**[FATO]** `docs/benchmarks/0059-benchmark-tool.md:72`:

```
\n`input_unchanged_in_memory` é uma verificação de identidade sobre `bytes` imutáveis; a verificação substantiva do arquivo DOCX é `input_unchanged_on_disk`.\n
```

A linha substituiu a linha em branco que separava dois parágrafos. No Markdown, "Em timeout…", esta nota e "A variável `BENCHMARK_0059_TEST_HOLD_AFTER`…" viram um único parágrafo com as barras visíveis. É o mesmo tipo de defeito que já quebrou títulos do contrato 0049.

**Correção:** trocar as sequências por linhas em branco reais.

### M2 — falta teste da remoção padrão da variável de teste

**[FATO]** O único teste alterado passa `allow_test_hooks=True`, cobrindo o caminho de teste. Nenhum teste prova que, **sem** a permissão, a variável é removida e a medição termina.

**[INFERÊNCIA]** Uma refatoração futura de `_spawn` pode reintroduzir o repasse integral do ambiente, e a suíte continuaria verde.

**Correção:** um teste que defina a variável com `mock.patch.dict`, chame `run_case` sem a permissão e exija `complete=True`, com timeout curto. A sonda desta reauditoria cabe como teste e roda em menos de um segundo.

---

## Observações

- A nota sobre `input_unchanged_in_memory` (L5) está correta: é verificação de identidade de `bytes` imutáveis, e a verificação útil é `input_unchanged_on_disk`.
- O adendo ao brief 0059D descreve fielmente o que os quatro commits fazem.

## O que está correto e deve ser preservado

- Rótulo e hierarquia da resolução de formatação do gate, sobre os nomes efetivamente exercitados.
- Remoção da variável de teste por padrão, com permissão explícita e restrita aos testes.
- Pulo do teste de git fora de uma árvore de trabalho, com mensagem clara.
- `patches_completed` nos resultados completos.
- 822 testes verdes, verificados de forma independente, e CI aprovado no Ubuntu.

---

## Recomendação

1. **M1 e M2 se for conveniente, no próprio PR**; nenhum dos dois afeta a medição;
2. merge por squash, com autorização do Felipe;
3. linha de base sintética no Ubuntu;
4. seis DOCX reais;
5. decisão de arquitetura, agora com a resolução do gate separada — o dado que a sequência `n(n+1)/2` mostra ser relevante para escolher entre operar em lote e reavaliar parcialmente.
