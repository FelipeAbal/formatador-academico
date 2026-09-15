# Revisão do PR #58 — ferramenta de benchmark do ciclo 0059 (Claude Opus)

**Auditor:** Claude Opus 5
**Data:** 2026-09-13
**Alvo:** PR #58, branch `implement/0059-benchmark`, head `52db94ef21989885222428482add80fbbbfdc4d5`
**Diff:** 1 arquivo, `tools/benchmark_0059.py` (+314)
**Base:** `main` @ `73a23dc`
**CI do PR:** `unittest` aprovado
**Repositório não modificado.** Verificações fora da árvore, com uma cópia do script.
**Plataforma das verificações:** macOS, Python 3.9.6. Estas execuções servem **apenas para verificar a correção do instrumento**; não são medição oficial.

**Contexto:** esta revisão confere, contra o código, a revisão do PR #58 feita pelo ChatGPT, e verifica os sete ajustes aprovados para o protocolo do ciclo 0059.

---

## Veredito

# APROVADO COM AJUSTES OBRIGATÓRIOS — medição oficial bloqueada

Concordo com a revisão do ChatGPT: **as seis afirmações procedem**, verificadas contra o código. Acrescento **dois achados de mesma gravidade** que ela não menciona — a etapa de análise está mal rotulada, e o limite de operações torna inócua a validação de alterações esperadas — e **quantifico** o erro do parse. Com o instrumento atual, a divisão por etapa levaria a conclusões erradas sobre exatamente as hipóteses que motivam o ciclo.

---

## Confirmação da revisão do ChatGPT

| Afirmação | Verificado | Evidência |
|---|---|---|
| 1. `DocxParser` envolvido como classe; mede a construção, não `parse_bytes` | **sim** | linha 118; medido abaixo |
| 2. Equivalência compara só partes, contagem e transformações parciais | **sim** | linhas 271-275 |
| 3. `applied_changes == expected_changes` nunca é exigido | **sim, e é pior** | ver N3 |
| 4. Timeout sem etapa nem progresso parcial | **sim** | linhas 243-245 |
| 5. Nenhuma estatística ou agregação | **sim** | a saída é só a lista bruta de execuções |
| 6. Nenhum teste da ferramenta | **sim** | o PR altera um único arquivo |

---

## 🔴 N1 — O parse sai do cronômetro: cerca de 23% do tempo fica sem etapa

**Arquivo:** `tools/benchmark_0059.py:118`.

**[FATO]** `engine.DocxParser` é substituído por uma função que cronometra `DocxParser(*args)`, ou seja, a construção do objeto. Em `processing_session/engine.py`, a chamada é `DocxParser().parse_bytes(package_bytes)`: `parse_bytes` roda **depois** que o invólucro retorna, fora de qualquer cronômetro.

**[FATO] Medido** num caso de 400 parágrafos com 5 alterações:

```
benchmark 400x5 -> total=5.84s
   parse   calls=6   seconds=0.000029
parse_bytes real, 1 chamada: mediana=0.2274s  -> x6 chamadas = 1.36s
```

**Impacto:** cerca de **1,36 s de 5,84 s** não pertence a nenhuma etapa. O tempo de parse reportado erra por um fator próximo de 47.000. A comparação pedida no ajuste 4 do protocolo — parse da avaliação contra parse da pós-condição — fica impossível.

**Correção:** cronometrar `parse_bytes`, por exemplo substituindo `engine.DocxParser` por uma subclasse cujo `parse_bytes` seja medido, e fazer o mesmo com o `DocxParser` usado em `patcher/validation.py`, para que a pós-condição também mostre seu parse.

## 🔴 N2 — "analysis" mede só o catálogo de estilos; a análise real está dentro de "decision"

**Arquivo:** `tools/benchmark_0059.py:119-121`; `processing_session/engine.py:175` e `:211`.

**[FATO]** O benchmark rotula como `analysis` apenas `build_style_catalog`. A resolução de formatação — `resolve_paragraph_formatting` (`engine.py:175`) e `resolve_run_formatting` (`engine.py:211`) — é chamada **dentro** de `_build_decisions`, que o benchmark rotula como `decision`.

**[FATO] Medido** no mesmo caso:

```
analysis   calls=6   seconds=0.002320
decision   calls=6   seconds=0.471941
```

**Impacto:** o relatório concluiria que a análise custa quase nada e que a decisão é cara. É o contrário do que acontece. A hipótese 3 do protocolo — se análise e classificação precisam ser repetidas — e a opção B, reavaliação parcial, seriam julgadas sobre números errados.

**Correção:** envolver também `resolve_paragraph_formatting` e `resolve_run_formatting` como `analysis`. Como os invólucros ficam aninhados (análise dentro de decisão, mutação e pós-condição dentro do patch), registrar tempo **inclusivo e exclusivo** por etapa. Sem isso, as etapas se somam em dobro.

## 🔴 N3 — O limite de operações igual às alterações esperadas esconde fixtures defeituosas

**Arquivo:** `tools/benchmark_0059.py:178` — `max_applied_operations=max(changes, 1)`.

**[FATO] Reproduzido** com uma fixture que declara 5 alterações mas tem 7 defeitos:

```
declaradas=5 | aplicadas=5 | status=operation_limit_reached | nao aplicadas=2
com o limite padrao do produto: aplicadas=7 | status=quiescent
```

**[INFERÊNCIA]** A execução de referência usa o **mesmo** limite. Então partes, contagem e transformações coincidem, e todas as verificações do PR passam. A correção proposta na afirmação 3 — exigir `applied_changes == expected_changes` — **também passaria**, porque o limite corta exatamente no número esperado. O erro da fixture fica invisível, e o custo medido é o de uma execução truncada.

Além disso, a interface usa o limite padrão do produto; com este limite, o benchmark não mede o caminho que o usuário percorre.

**Correção:** usar o limite padrão do produto e exigir, juntos:

```
applied_changes == expected_changes
session_status == "quiescent"
unapplied_changes == 0
review_items == 0
```

---

## 🟠 Achados importantes

- **A montagem final não é medida por etapa.** `build_product_from_inputs` constrói o relatório (`product_output_bundle/builder.py:97`), serializa o relatório em `builder.py:98` e de novo em `builder.py:54` e `model.py:91`, e constrói o DOCX de revisão (`builder.py:105`). Nada disso tem cronômetro próprio: só `build_product_delivery` é medido. O ajuste 5 do protocolo — separar reempacotamento por patch de montagem final — fica parcial, e as serializações repetidas do relatório, que podem pesar, ficam invisíveis.
- **O ambiente registrado não permite comparar execuções.** A CPU aparece como `'arm'`, porque `platform.processor()` não dá o modelo; a RAM não é registrada, embora o protocolo a exija; também faltam a versão do `lxml` e o **SHA do commit** do repositório, com indicação de árvore alterada. Sem o commit, duas linhas de base não podem ser associadas ao código que as produziu.
- **Não há modo para os seis DOCX reais.** O protocolo pede os resultados externos desses documentos, identificados por nome, tamanho e SHA-256. `cases()` só gera fixtures sintéticas. Falta algo como `--external CAMINHO`, que meça sem armazenar o arquivo.
- **Timeout descarta justamente os casos que importam** (detalhe da afirmação 4). O worker só imprime ao terminar, então tudo se perde quando o processo é encerrado. E quando a execução de **referência** estoura o prazo, `measured = []`: o caso não gera nenhum dado. É o caso da dissertação que motivou o ciclo. Correção: o worker emitir progresso durante a execução — etapa corrente e quantidade de `apply_cleared_operation` concluídas — em arquivo lateral ou na saída de erro.

## 🟡 Menores

- **Referência para a arquitetura futura incompleta** (ajuste 7 e detalhe da afirmação 2). `transform_refs` guarda só caminho e valor desejado, sem slot da propriedade nem valor observado. Faltam `processing_report_ref`, status, hashes das partes do DOCX de revisão e dos arquivos da entrega.
- **`_json_value` quebra com `LengthValue` e `LineSpacingValue`.** Devolve o `Decimal` interno, que `json.dumps` não serializa. Hoje funciona só porque a fixture usa negrito; quebra no dia em que houver série de fonte ou entrelinha.
- **Só operações de run.** A fixture exercita apenas negrito. Operações de parágrafo (`w:pPr`, P3/P4) têm custo de patch diferente. Declarar a limitação ou acrescentar uma série de propriedade de parágrafo.
- **Custo da instrumentação não reportado.** A referência sem instrumentação já existe, mas a diferença de tempo total entre as duas execuções não é calculada.
- **Versão do Python.** Estas verificações rodaram em 3.9.6 só para conferir o instrumento. A medição oficial deve usar 3.12, no Ubuntu e no Mac.

---

## Estado dos sete ajustes aprovados para o protocolo

| Ajuste | Estado |
|---|---|
| 1. Medir etapas envolvendo os nomes do laço | **parcial** — a abordagem está certa, mas parse (N1) e análise (N2) saem errados |
| 2. Pontos cruzados de tamanho × alterações | **atendido** — `C1` 100×40 e `C2` 800×20 |
| 3. Eixo B além de 40 alterações | **atendido** — até 160 |
| 4. Parse da pós-condição separado do parse da avaliação | **parcial** — a pós-condição é medida à parte, mas o parse da avaliação está quebrado |
| 5. Coluna de ponta a ponta com `build_product_delivery` | **parcial** — a entrega é medida; relatório, serializações e DOCX de revisão não |
| 6. `ZIP_STORED` e hash de partes descompactadas | **atendido** |
| 7. Saídas de referência guardadas | **parcial** — incompleto |

---

## Sinal preliminar, não oficial

No caso 400×5, no Mac com Python 3.9: a **pós-condição levou 1,21 s dos 1,25 s do patch (97%)**, e `planning` (0,84 s) e `safety_gate` (0,77 s) superaram `classification` (0,29 s). Se isso se confirmar na medição oficial, o gargalo do patch não é o reempacotamento ZIP da hipótese 2, e sim a reanálise feita pela pós-condição.

**Não use esse sinal para decidir nada.** Ele vem de uma execução, em Python 3.9, com o parse fora do cronômetro e a análise mal rotulada. Serve só para mostrar por que N1 e N2 precisam ser corrigidos antes: são justamente as etapas que decidem entre as opções A e B.

---

## Sequência recomendada

**Antes da medição oficial:**

1. **N1** — cronometrar `parse_bytes`, na avaliação e na pós-condição;
2. **N2** — medir a resolução de formatação como análise, com tempo inclusivo e exclusivo;
3. **N3** — limite padrão do produto, exigindo alterações esperadas, `quiescent`, zero não aplicadas e zero em revisão;
4. **equivalência completa** e referência para a arquitetura futura;
5. **progresso emitido durante a execução**, para que um timeout ainda gere dado;
6. **ambiente completo**: modelo de CPU, RAM, versão do `lxml`, SHA do commit;
7. **modo para os DOCX reais**, sem armazená-los.

**Depois:** agregação estatística e testes da ferramenta. Um teste rápido, com fixture mínima, deveria exigir tempo de parse positivo e proporcional a `parse_bytes`, alterações aplicadas iguais às declaradas com o limite padrão, e resultados idênticos com e sem instrumentação.
