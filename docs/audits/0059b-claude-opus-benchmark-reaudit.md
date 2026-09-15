# Reauditoria do PR #58 — ferramenta de benchmark 0059, head `4ac248a` (Claude Opus)

**Auditor:** Claude Opus 5
**Data:** 2026-09-14
**Alvo:** PR #58, branch `implement/0059-benchmark`, head `4ac248a794d47480ddec53577e7386b509ef3bfa`
**Revisão anterior:** `0059-claude-opus-benchmark-review.md`, sobre `52db94e`
**Mudança desde a revisão anterior:** um commit, `4ac248a` ("fix: complete cycle 0059 benchmark instrumentation"), em `tools/benchmark_0059.py` (+193/−20)
**Base:** `main` @ `73a23dc`
**Suíte executada localmente:** **804 passed, 1 warning, 23.10s**; CI do PR aprovado
**Repositório não modificado.** O script foi executado a partir da árvore do head, sem `--output`; os arquivos de progresso foram gravados fora do repositório.
**Plataforma das verificações:** macOS, Python 3.9.6, **apenas para verificar a correção do instrumento**. Os tempos abaixo não são medição oficial.

---

## Veredito

# APROVADO COM AJUSTES OBRIGATÓRIOS — medição oficial ainda bloqueada

Boa parte das correções funciona: o `parse_bytes` agora é medido, a resolução de formatação tem rótulo próprio, o limite de operações é o padrão do produto, a fixture é validada por completo, a equivalência foi ampliada e o ambiente registra RAM, `lxml` e commit.

Mas **a correção do progresso em timeout introduziu uma distorção grave**: as gravações de progresso **dobram o tempo total** nos casos com muitas alterações, que é exatamente o eixo que o ciclo precisa medir. E o diagnóstico de timeout **não funciona na execução de referência**, a única que roda quando o caso é grande demais.

---

## Estado dos achados da revisão anterior

| Achado | Estado | Evidência |
|---|---|---|
| N1 — `parse_bytes` fora do cronômetro | **corrigido** | `TimedDocxParser.parse_bytes`, linhas 158-171 |
| N2 — análise mal rotulada | **parcial** | `formatting_resolution` separado, mas `decision` continua inclusivo — ver T3 |
| N3 — limite de operações escondia fixture defeituosa | **corrigido** | limite padrão (linha 282); exige alterações esperadas, `quiescent`, zero não aplicadas e zero em revisão (398-404) |
| Equivalência incompleta | **corrigido** | relatório, partes do DOCX de revisão, metadados da entrega, status e contagens (434-439) |
| Timeout sem progresso | **não funciona onde importa** | ver T2 |
| Estatísticas | **parcial** | mínimo, mediana e máximo; mas vêm só de execuções instrumentadas (T1) e somem com uma execução incompleta (T6) |
| Ambiente | **parcial** | RAM, `lxml`, zlib e commit; CPU ainda sem modelo; sem indicação de árvore alterada |
| Montagem final por etapa | **aberto** | relatório, serializações e DOCX de revisão sem cronômetro |
| Modo para os DOCX reais | **aberto** | `cases()` só gera fixtures sintéticas |
| Testes da ferramenta | **aberto** | o PR continua alterando um único arquivo |

---

## 🔴 T1 — As gravações de progresso dobram o tempo medido

**Arquivo:** `tools/benchmark_0059.py:100-122` e `:350-351`.

**[FATO]** Todo invólucro chama `self.progress(label)` no `finally`, e cada chamada grava um JSON em disco com renomeação atômica. `run_case` **sempre** passa `--progress-file`, e `_statistics` calcula tudo **apenas a partir das execuções instrumentadas**.

A resolução de formatação é chamada uma vez por run a cada iteração do laço, então as gravações chegam aos milhares. Cada gravação de uma chamada interna acontece dentro do intervalo medido da etapa externa e dentro do tempo total.

**[FATO] Medido:**

```
400 x 5, medianas de 3 execuções
  instrumentado, SEM arquivo de progresso    total=7.18s | decision=0.56s
  instrumentado, COM arquivo (como run_case) total=7.65s | decision=1.60s
  gravacoes de progresso numa execucao: ~2473

200 x 40, 1 execucao cada
  sem arquivo: total=19.18s | com arquivo: total=38.99s | gravacoes ~8728
```

**Impacto:** no caso com 40 alterações, o tempo total **dobra**, e a distorção cresce com o número de alterações. Os números oficiais do eixo B e dos pontos cruzados sairiam inflados justamente na direção da hipótese 1 — "o custo cresce com as alterações" —, confirmando-a em parte por um artefato da própria ferramenta. A etapa `decision` fica quase três vezes maior.

**Correção:**

- gravar progresso **só em fronteiras de iteração**, por exemplo após `build_transform_record` e após cada parse da avaliação, ou no máximo a cada N segundos. Nunca dentro de chamadas por run;
- calcular os **tempos totais oficiais a partir de execuções sem instrumentação, repetidas**. Usar as instrumentadas apenas para a divisão por etapa;
- reportar a sobrecarga da instrumentação: total instrumentado menos total de referência.

## 🔴 T2 — O diagnóstico de timeout falha na execução de referência

**Arquivo:** `tools/benchmark_0059.py:334`, `:396-397` e `:412-413`.

**[FATO]** A execução de referência roda sem instrumentação e grava progresso apenas ao terminar (`timing.progress("complete")`). `run_suite` executa a referência **primeiro** e, se ela não terminar, não executa nenhuma instrumentada.

**[FATO] Medido** com prazo de 1,5 s no caso 400×5:

```
referencia (sem instrumentacao) -> complete=False | last_stage=None     | applied_changes=None | chaves=[]
instrumentada                   -> complete=False | last_stage=decision | applied_changes=0    | chaves=['applied_changes', 'last_stage', 'stage_calls']
```

**Impacto:** no caso que motivou o ciclo — a dissertação que não termina —, a referência estoura o prazo, devolve diagnóstico vazio, e nenhuma execução instrumentada chega a rodar. O protocolo exige última etapa e alterações aplicadas em timeout, e o PR declara esse item corrigido. Ele só funciona nos casos em que não era necessário.

**Correção:** dar à execução de referência um progresso mínimo, só nas fronteiras de iteração, compatível com T1. Ou, quando a referência estourar o prazo, executar ainda uma instrumentada só para diagnóstico, marcada como tal e fora das estatísticas.

---

## 🟠 Achados importantes

- **T3 — as etapas contam tempo em dobro.** `decision` (`_build_decisions`) continua **inclusiva**: contém `formatting_resolution`. `patch_total` contém mutação, reempacotamento, validação e pós-condição. **Medido:** a soma das etapas deu **8,50 s** para um total de **7,30 s**. A "distribuição do tempo por etapa" exigida pelo protocolo sai errada se as colunas forem somadas. Registrar tempo exclusivo por etapa, ou apresentar a hierarquia de forma explícita.
- **T4 — o parse da pós-condição continua sem separação** (ajuste 4 do protocolo). `patcher/validation.py` usa seu próprio `DocxParser`, que não é cronometrado, e `verify_postcondition` é medida como um bloco. A revisão anterior viu a pós-condição ocupar cerca de 97% do patch. Sem dividi-la, a escolha entre as opções A e B fica sem o dado decisivo.
- **T5 — a ordem das execuções gera ruído do tamanho da sobrecarga.** No teste A, a referência sem instrumentação (**8,62 s**) saiu mais lenta que a instrumentada (**7,18 s**). As três referências rodaram primeiro, em sequência. Efeitos de ordem, temperatura e cache neste Mac são comparáveis à própria sobrecarga que se quer medir. Intercalar referência e instrumentadas, e registrar a ordem.
- **T6 — uma execução incompleta apaga as estatísticas do caso.** `_statistics` devolve `{}` se **qualquer** execução não terminar (linha 443). Calcular sobre as completas e reportar quantas ficaram incompletas.
- **Abertos da revisão anterior:**
  - a montagem final — `build_processing_report`, as serializações repetidas do relatório e `build_review_docx` — segue sem cronômetro por etapa;
  - não há modo para os seis DOCX reais;
  - não há testes da ferramenta;
  - a CPU aparece só como `platform.processor()` (`'arm'` no Mac), sem o modelo, que no Linux vem de `/proc/cpuinfo` e no Mac de `sysctl machdep.cpu.brand_string`;
  - o commit é registrado sem indicação de árvore alterada, então uma execução com mudanças locais aparece com o SHA de um commit limpo.

## 🟡 Menores

- `tempfile.mkstemp` devolve um descritor que nunca é fechado (linha 350): um vazamento de descritor por execução.
- `_json_value` segue quebrando com `LengthValue` e `LineSpacingValue`; funciona só porque a fixture usa negrito.
- `transform_refs` segue sem slot da propriedade e sem valor observado.
- A fixture exercita só operações de run; operações de parágrafo têm custo de patch diferente.

---

## O que está correto e deve ser preservado

- **`TimedDocxParser` como subclasse**, medindo `parse_bytes` sem alterar o código de produção.
- **Validação estrita da fixture na referência**: alterações esperadas, `quiescent`, zero não aplicadas e zero em revisão, com o limite padrão do produto. É exatamente o que fecha N3.
- **Validação da forma da fixture pelo parser** (`_ir_counts`), antes de medir.
- **Equivalência ampliada**, incluindo relatório, DOCX de revisão e metadados da entrega.
- **Gravação atômica do progresso**, por arquivo temporário e renomeação. O mecanismo é bom; o problema é a frequência.
- **Ambiente com RAM, `lxml`, zlib e commit.**
- **Mínimo, mediana e máximo** por campo e por etapa.
- Processo novo por execução, `ZIP_STORED`, pontos cruzados e eixo de alterações até 160.
- 804 testes verdes, verificados de forma independente.

---

## Sequência recomendada

**Antes da medição oficial:**

1. **T1** — progresso só em fronteiras de iteração; tempos totais de execuções sem instrumentação; sobrecarga reportada;
2. **T2** — diagnóstico de timeout também na referência;
3. **T3** — tempo exclusivo por etapa;
4. **T4** — parse da pós-condição separado;
5. **T5 e T6** — execuções intercaladas e estatísticas sobre as completas.

**Em seguida:** montagem final por etapa, modo para os DOCX reais, modelo de CPU e indicação de árvore alterada.

**Depois:** testes da ferramenta. Um bom primeiro teste: com fixture mínima, o número de gravações de progresso não deve passar de iterações mais uma constante. Ele trava T1 sem depender de tempo, e por isso não fica instável.
