# Reauditoria do PR #58 — ferramenta de benchmark 0059, head `15d0c40` (Claude Opus)

**Auditor:** Claude Opus 5
**Data:** 2026-09-14
**Alvo:** PR #58, branch `implement/0059-benchmark`, head `15d0c40f0e3f8efd061aaea4ccde15929fbbaa59`
**Reauditoria anterior:** `0059b-claude-opus-benchmark-reaudit.md`, sobre `4ac248a`
**Mudança desde a reauditoria anterior:** um commit, `15d0c40` ("fix: keep benchmark progress out of measured calls"), em `tools/benchmark_0059.py` (+5/−2)
**Base:** `main` @ `73a23dc`
**Suíte executada localmente:** **804 passed, 1 warning, 22.01s**; CI do PR aprovado
**Repositório não modificado.** O script foi executado a partir da árvore do head, sem `--output`; os arquivos de progresso foram gravados fora do repositório.
**Plataforma das verificações:** macOS, Python 3.9.6, **apenas para verificar a correção do instrumento**. Os tempos abaixo não são medição oficial.

---

## Veredito

# APROVADO COM AJUSTES OBRIGATÓRIOS

**T1 está corrigido e verificado.** O progresso deixou de contaminar a medição. Com isso, a linha de base sintética já pode ser coletada, desde que se registre que `decision` e `patch_total` são tempos inclusivos (T3): como as etapas filhas também são registradas, o tempo exclusivo pode ser calculado depois, na agregação.

Continuam obrigatórios:

- **T4**, antes de decidir a arquitetura. O parse da pós-condição não pode ser separado depois, porque não é medido;
- **T2**, antes de medir os DOCX reais. A execução de referência continua sem diagnóstico no timeout.

---

## Estado dos achados

| Achado | Estado | Evidência |
|---|---|---|
| T1 — progresso distorcia a medição | **corrigido** | progresso só nas fronteiras de `decision` e `patch_total`; 200×40: 16,21 s sem arquivo, 16,83 s com arquivo (antes, 19,18 s e 38,99 s) |
| T2 — timeout sem diagnóstico na referência | **aberto** | prazo de 1,5 s: referência sem `last_stage` nem alterações; instrumentada com `last_stage=patch_total` |
| T3 — etapas inclusivas somadas em dobro | **aberto, contornável na agregação** | soma das etapas 7,45 s contra total 7,29 s |
| T4 — parse da pós-condição não separado | **aberto** | o `DocxParser` de `patcher/validation.py` segue sem cronômetro |
| T5 — ruído de ordem | **aberto, agora medido** | ver abaixo |
| T6 — uma execução incompleta apaga as estatísticas | **aberto** | `_statistics`, sem alteração |
| Montagem final por etapa, modo para DOCX reais, testes, modelo de CPU, indicação de árvore alterada | **abertos** | sem alteração neste commit |

---

## ✅ T1 — corrigido

**[FATO]** O invólucro agora chama `progress()` só quando o rótulo é `decision` ou `patch_total`, e a chamada de progresso dentro de `TimedDocxParser.parse_bytes` foi removida. As gravações passam a ser uma por iteração do laço mais uma por patch, e deixam de ocorrer dentro de chamadas por run.

**[FATO] Medido:**

```
200 x 40, 1 execucao cada
  sem arquivo: total=16.21s | com arquivo: total=16.83s
400 x 5, decision: 0.51s sem arquivo, 0.54s com arquivo
gravacoes reais de progresso por execucao (decision + patch_total + complete): 12
```

A diferença de 4% no caso 200×40 está dentro do ruído medido em T5.

**Nota sobre a sonda:** a linha "gravacoes ~2473", impressa pela sonda desta reauditoria, soma todas as chamadas instrumentadas. A fórmula correspondia ao código de `4ac248a`, onde toda chamada instrumentada gravava progresso, mas **não se aplica a `15d0c40`**. A contagem real no head atual é a da última linha acima.

---

## 🟠 T5 — o ruído de ordem é maior que os efeitos a medir

Na primeira sonda, sequencial, o caso 400×5 deu **8,09 s** com arquivo contra **5,94 s** sem, uma diferença que 12 gravações não explicam e que não aparecia em nenhuma etapa. Para separar ruído de sobrecarga, a comparação foi repetida **intercalando** as variantes, quatro rodadas:

```
ordem: referencia 5.77 | sem 5.68 | com 5.53 | referencia 5.82 | sem 5.61 | com 5.88
       referencia 7.10 | sem 5.73 | com 6.12 | referencia 6.50 | sem 6.47 | com 6.58
  referencia                  min=5.77 mediana=6.16 max=7.10
  instrumentado sem arquivo   min=5.61 mediana=5.70 max=6.47
  instrumentado com arquivo   min=5.53 mediana=6.00 max=6.58
```

**[INFERÊNCIA]** A diferença entre variantes (até 0,46 s) é **menor** que a variação dentro de uma mesma variante (até 1,33 s), e há deriva de subida ao longo da sequência. Os 8,09 s eram efeito de ordem. Neste Mac, três repetições têm amplitude de cerca de ±12%, então **não distinguem efeitos menores que cerca de 20%**.

**Correção (protocolo e ferramenta):**

- intercalar execuções de referência e instrumentadas e registrar a ordem;
- aumentar as repetições nos casos em que a comparação importa, ou reportar a amplitude junto da mediana;
- executar a medição oficial com a máquina ociosa, no Ubuntu;
- não tratar como achado uma diferença menor que a amplitude observada no próprio caso.

---

## 🟠 Achados que continuam abertos

- **T2 — diagnóstico de timeout na referência.** Sem mudança. A referência roda sem instrumentação, grava progresso só ao terminar e é executada primeiro. Se ela estourar o prazo, nenhuma instrumentada roda. **Obrigatório antes de medir os DOCX reais**, porque é o caso da dissertação.
- **T3 — tempos inclusivos.** `decision` inclui `formatting_resolution`; `patch_total` inclui mutação, reempacotamento, validação e pós-condição. Como as filhas também são registradas, o tempo exclusivo pode ser **derivado na agregação**, desde que a hierarquia fique documentada no relatório. Não bloqueia a coleta.
- **T4 — parse da pós-condição.** `patcher/validation.py` usa seu próprio `DocxParser`, sem cronômetro. **Obrigatório antes de decidir entre as opções A e B**: na primeira revisão, a pós-condição ocupou cerca de 97% do patch, e esse tempo não pode ser dividido depois se não for medido.
- **T6.** Uma execução incompleta ainda apaga as estatísticas do caso.
- **Abertos desde a primeira revisão:** montagem final sem cronômetro por etapa; nenhum modo para os DOCX reais; nenhum teste da ferramenta; CPU sem modelo; commit sem indicação de árvore alterada.

## 🟡 Menores

Sem alteração: `mkstemp` sem fechar o descritor, `_json_value` com `LengthValue`, `transform_refs` sem slot e valor observado, fixture só com operações de run.

---

## O que está correto e deve ser preservado

- **Progresso em granularidade de iteração**, com o comentário explicando por que não pode ir mais fundo.
- **Remoção da gravação de progresso no parse**, que ocorria duas vezes por iteração.
- Tudo o que a reauditoria anterior listou como correto: `TimedDocxParser`, validação estrita da fixture com o limite padrão, equivalência ampliada, gravação atômica, ambiente com RAM, `lxml`, zlib e commit, e mínimo, mediana e máximo.
- 804 testes verdes, verificados de forma independente.

---

## Sequência recomendada

1. **Linha de base sintética:** pode ser coletada agora, com execuções intercaladas (T5) e tempos inclusivos documentados (T3);
2. **T4**, antes da decisão de arquitetura;
3. **T2** e **modo para os DOCX reais**, antes de medir os documentos reais;
4. **T6**, montagem final por etapa, modelo de CPU, indicação de árvore alterada;
5. **Testes da ferramenta.** O teste sugerido na reauditoria anterior — gravações de progresso não passam do número de iterações mais uma constante — agora trava exatamente a correção deste commit.
