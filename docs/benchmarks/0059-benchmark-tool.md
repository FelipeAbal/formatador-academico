# Ferramenta de benchmark do ciclo 0059

Arquivo: `tools/benchmark_0059.py`. Testes: `tests/test_benchmark_0059.py`.

A ferramenta mede o custo do pipeline sem alterar código de produção. A instrumentação substitui, só dentro do processo medido, nomes que os módulos de produção já importam.

## Modos

### Sintético (padrão)

Gera fixtures DOCX determinísticas, sem compressão (`ZIP_STORED`) e com data fixa. Os casos cobrem o eixo de tamanho (A1–A5), o eixo de alterações (B1–B8, até 160) e pontos cruzados (C1, C2).

Cada caso precisa produzir **exatamente** as alterações esperadas com o limite padrão de operações do produto: status `quiescent`, zero itens não aplicados e zero em revisão. Caso contrário, a ferramenta interrompe a execução.

### Documentos reais (`--docx`)

Mede arquivos DOCX existentes no próprio lugar, somente para leitura. Não exige número conhecido de alterações.

- `--docx CAMINHO` pode ser repetido.
- `--profile CAMINHO` usa um Profile Input JSON; sem ele, usa o perfil acadêmico embutido: corpo com fonte 12 pt, entrelinha 1,5 e alinhamento justificado.
- Cada execução registra `outcome`: `quiescent`, `quiescent_with_unapplied`, `operation_limit_reached`, `timeout` ou `error`. **Terminar o processo não é tratado como sucesso**; o resultado é o status da sessão.
- Os bytes do arquivo são verificados antes e depois (`input_unchanged_in_memory`, `input_unchanged_on_disk`).

**Privacidade.** Nenhum documento é copiado. O relatório registra só o nome do arquivo (`label`), o tamanho e o SHA-256. O caminho absoluto só aparece com `--record-docx-path`. Em caso de erro, registra-se o tipo e o código da exceção, nunca a mensagem, que pode conter texto do documento. Grave `--output` fora do repositório quando medir documentos privados.

## Variantes e tempo oficial

| Variante | Cronômetros por etapa | Uso |
|---|---|---|
| `reference` | não | **tempo total oficial** (`total_seconds`) |
| `instrumented` | sim | divisão do tempo por etapa |

As duas variantes gravam o mesmo progresso, nas mesmas fronteiras, então a escrita em disco é idêntica entre elas.

`statistics.instrumentation_overhead_median_seconds` registra a diferença entre as medianas dos totais das duas variantes.

## Ordem das execuções

Dentro de cada caso, a ordem é fixa, no padrão ABBA: referência, instrumentada, instrumentada, referência, e assim por diante (`schedule(repeats)`). Isso equilibra a deriva linear entre as variantes. Nenhuma aleatoriedade é usada.

Cada execução registra `sequence` (global), `case_position`, `started_at` e `finished_at`.

Depois de um timeout ou de um erro, a outra variante ainda roda uma vez, se ainda não tiver rodado, como diagnóstico; o caso então para (`stopped_early`, `skipped_runs`).

## Tempos por etapa

`stage_seconds` é **inclusivo**. `stage_seconds_exclusive` subtrai as etapas filhas medidas:

```text
decision      ⊃ formatting_resolution
safety_gate   ⊃ safety_gate_formatting_resolution
patch_total   ⊃ xml_mutation, zip_repackaging, allowed_delta_validation, postcondition
postcondition ⊃ postcondition_parse, postcondition_style_catalog,
                postcondition_target_resolution, postcondition_formatting_resolution
```

- `parse` é só o parse da avaliação. O parse feito pela pós-condição aparece apenas em `postcondition_parse` e nunca é somado a `parse`.
- `parse`, `analysis`, `classification`, `decision`, `planning`, `safety_gate`, `patch_total` e `transform_record` não se sobrepõem entre si.
- `total_seconds` inclui a montagem final do bundle (relatório e DOCX de revisão), que não tem cronômetro por etapa, as gravações de progresso e `final_delivery`.
- `postcondition_share_of_patch_total` é a fração do patch ocupada pela pós-condição.
- `safety_gate_formatting_resolution` mede a resolução feita pelas referências próprias do SafetyGate.

**Não some as etapas diretamente**: os tempos inclusivos contam as etapas filhas mais de uma vez.

O JSON de saída repete estas regras em `timing_semantics`.

## Progresso e timeout

O progresso é gravado só em fronteiras grossas: início e fim de cada avaliação, após cada registro de transformação, em torno da montagem do relatório, do DOCX de revisão e da entrega final, e ao concluir. Nada é gravado dentro de chamadas por run ou por parágrafo.

Em timeout, o registro da execução inclui `current_stage`, `last_completed_stage`, `evaluations_started`, `patches_completed`, `applied_changes` e a forma do documento. Isso vale para as duas variantes.
\n`input_unchanged_in_memory` é uma verificação de identidade sobre `bytes` imutáveis; a verificação substantiva do arquivo DOCX é `input_unchanged_on_disk`.\n
A variável `BENCHMARK_0059_TEST_HOLD_AFTER` existe só para os testes: ela suspende o processo depois de uma fronteira, tornando o timeout determinístico. **Nunca a defina durante uma medição.**

## Comandos

### Linha de base sintética no Ubuntu

Com a máquina ociosa, Python 3.12 e as dependências de `requirements.txt`:

```bash
cd ~/formatador-academico
git checkout main && git pull --ff-only
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
mkdir -p ~/benchmark-0059
.venv/bin/python tools/benchmark_0059.py --repeats 3 --timeout 1800 --output ~/benchmark-0059/sintetico-$(date +%Y%m%d-%H%M).json
```

Para um recorte, use `--only A1,B1,C1`.

### Os seis DOCX reais

Com os arquivos numa pasta **fora do repositório**:

```bash
.venv/bin/python tools/benchmark_0059.py \
  --docx ~/docx-medicao/documento-1.docx \
  --docx ~/docx-medicao/documento-2.docx \
  --docx ~/docx-medicao/documento-3.docx \
  --docx ~/docx-medicao/documento-4.docx \
  --docx ~/docx-medicao/documento-5.docx \
  --docx ~/docx-medicao/documento-6.docx \
  --repeats 3 --timeout 3600 \
  --output ~/benchmark-0059/reais-$(date +%Y%m%d-%H%M).json
```

Para um perfil próprio, acrescente `--profile ~/docx-medicao/perfil.json`.

## Limitações conhecidas

- A montagem final do bundle (relatório, serializações do relatório e DOCX de revisão) não tem cronômetro por etapa; entra no resíduo de `total_seconds`.
- `cpu` vem de `platform.processor()`, que não informa o modelo do processador.
- `commit` não indica se a árvore tinha alterações locais.
- As fixtures sintéticas exercitam só operações de run (negrito); operações de parágrafo têm custo de patch diferente.
- A contagem de parágrafos e runs cobre só a história principal (`word/document.xml`).
- Um documento que estoura o prazo nas duas variantes gera diagnóstico de progresso, mas nenhum tempo total.
