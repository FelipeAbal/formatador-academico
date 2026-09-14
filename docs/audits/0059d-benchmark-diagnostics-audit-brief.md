# Brief de auditoria 0059D — diagnósticos da ferramenta de benchmark

## Alvo

Branch `implement/0059-benchmark-diagnostics`, a partir de `main` @ `99cde017f956e223cdc31b4ca2aa5e3004fb0490` (PR #58 mesclado). O SHA do commit auditado é o head do PR aberto com esta branch.

Nenhum código de produção foi alterado. Mudaram apenas:

- `tools/benchmark_0059.py`;
- `tests/test_benchmark_0059.py` (novo, 18 testes);
- `docs/benchmarks/0059-benchmark-tool.md` (novo);
- este brief.

**Não iniciar a medição oficial nem escolher arquitetura com base neste PR.**

## O que foi feito

### Tarefa 1 — pós-condição medida por dentro

`verify_postcondition` resolve `DocxParser`, `build_style_catalog`, `find_story`, `resolve_target` e `resolve_*` pelo namespace de `patcher/validation.py`. Esses nomes são usados **somente** dentro de `verify_postcondition` (verificado por varredura do módulo). A instrumentação os envolve com rótulos próprios:

- `postcondition_parse` — `DocxParser.parse_bytes` de `validation`, por subclasse;
- `postcondition_style_catalog`;
- `postcondition_target_resolution` — `find_story` e `resolve_target`;
- `postcondition_formatting_resolution` — `resolve_run_formatting` e `resolve_paragraph_formatting`.

O parse da avaliação continua em `parse`, pelo `DocxParser` do `engine`. Os dois são ligações distintas, então nenhum parse é contado duas vezes.

`stage_seconds` segue **inclusivo**. `stage_seconds_exclusive` subtrai as filhas conforme `STAGE_HIERARCHY` (`decision`, `patch_total`, `postcondition`). `postcondition_share_of_patch_total` responde quanto do patch pertence à pós-condição. As regras vão no JSON em `timing_semantics`.

### Tarefa 2 — progresso também na referência

`Progress` grava em fronteiras grossas: início e fim de `_evaluate`, após `build_transform_record`, em torno de `build_processing_report`, `build_review_docx` e da entrega final, na contagem do documento e ao concluir. Nada é gravado dentro de chamadas por run.

As fronteiras são instaladas **nas duas variantes** e como camada **mais externa**, fora de qualquer cronômetro. As gravações são idênticas entre referência e instrumentada; o teste exige igualdade.

Em timeout, o registro traz `current_stage`, `last_completed_stage`, `evaluations_started`, `patches_completed`, `applied_changes` e a forma do documento.

Gancho só para testes: `BENCHMARK_0059_TEST_HOLD_AFTER` suspende o processo depois de uma fronteira, tornando o timeout determinístico.

### Tarefa 3 — execuções intercaladas

`schedule(repeats)` retorna a ordem fixa ABBA: referência, instrumentada, instrumentada, referência, e assim por diante. Não há aleatoriedade. Cada execução registra `sequence`, `case_position`, `started_at` e `finished_at`.

**Tempo total oficial: variante `reference`.** A instrumentada serve só para a divisão por etapa. `instrumentation_overhead_median_seconds` registra a diferença.

A equivalência compara toda execução completa com a primeira completa do caso. No modo sintético, divergência interrompe; no modo `--docx`, é registrada em `equivalence_mismatch_positions`.

Após timeout ou erro, a outra variante roda uma vez como diagnóstico, se ainda não rodou, e o caso para.

As estatísticas passam a ser calculadas sobre as execuções completas, com contagem das incompletas; antes, uma execução incompleta apagava tudo.

### Tarefa 4 — `--docx`

- `--docx CAMINHO` (repetível), `--profile CAMINHO` e `--record-docx-path`;
- sem `--profile`, usa o perfil acadêmico embutido: fonte 12 pt, entrelinha 1,5, justificado, validado pela fronteira real;
- `outcome` é o status da sessão, `timeout` ou `error`; terminar o processo não conta como sucesso;
- bytes verificados em memória e em disco antes e depois;
- registra só nome, tamanho e SHA-256 por padrão; em erro, só o tipo e o código da exceção.

### Correções colaterais necessárias

- `_json_value` agora serializa dataclasses como `LengthValue` e `LineSpacingValue`; antes devolvia um `Decimal` e quebrava `json.dumps` assim que o perfil acadêmico aplicava fonte ou entrelinha;
- `transform_refs` passou a incluir `property_slot`;
- a contagem de parágrafos e runs usa `walk_records` sobre `word/document.xml`, cobrindo parágrafos aninhados em tabelas;
- `mkstemp` agora fecha o descritor.

## Verificação feita pelo autor

- suíte completa em **Python 3.12.13 com lxml 6.1.3**, pelo mesmo comando do CI (`unittest discover -s tests`): **822 testes OK** — as 804 anteriores e as 18 novas;
- os 18 testes novos também passaram em Python 3.9.6;
- smoke A1 pela linha de comando: execuções intercaladas; 6 parses de avaliação e 5 de pós-condição; 25 gravações de progresso em cada variante;
- smoke `--docx` com perfil acadêmico sobre documento sintético com fonte 11 pt, entrelinha simples e alinhamento à esquerda: 15 alterações aplicadas, 5 em cada propriedade, `quiescent`, sem divergência de equivalência, valores serializados corretamente.

As frações de pós-condição observadas nos smokes (88,8% no A1, 66,4% no documento com propriedades de parágrafo) servem **só para verificar o instrumento**. Não são medição oficial.

## Pontos para auditoria adversarial

### DeepSeek Flash 4.1 — código

1. O parse da pós-condição é realmente medido, e nunca somado a `parse`?
2. `stage_seconds_exclusive` pode ficar negativo por sobreposição não prevista entre etapas?
3. As fronteiras de progresso ficam fora de todos os cronômetros, inclusive `transform_record`, dada a ordem de instalação (instrumentação primeiro, progresso por fora)?
4. As duas variantes produzem as mesmas gravações de progresso em qualquer documento, inclusive com patches rejeitados?
5. O desfazer das substituições restaura exatamente os nomes originais, na ordem certa, mesmo quando o pipeline levanta exceção?
6. A regra de parada após timeout ou erro pode descartar dados úteis ou rodar execuções demais?
7. O gancho `BENCHMARK_0059_TEST_HOLD_AFTER` pode ser ativado por acidente numa medição, ou vazar para o processo pai?
8. O modo `--docx` pode gravar, copiar ou registrar conteúdo do documento em algum caminho, incluindo arquivos temporários de progresso e mensagens de erro?

### Claude Opus — completa

1. Os buckets inclusivos e exclusivos permitem responder, sem ambiguidade, quanto do patch pertence à pós-condição e quanto da pós-condição é parse?
2. A ordem ABBA e o uso da referência como tempo oficial resolvem o ruído de ordem medido nas reauditorias 0059B e 0059C, ou falta algo?
3. O progresso da referência preserva o diagnóstico sem contaminar o tempo oficial?
4. A mudança do formato do JSON (referência repetida, execuções com variantes, estatísticas por variante) está documentada o bastante para quem for ler a linha de base?
5. O modo `--docx` respeita a privacidade dos documentos e distingue corretamente `quiescent`, `operation_limit_reached`, timeout e erro?
6. Algum ponto impede iniciar a linha de base sintética no Ubuntu depois deste PR?

## Limitações conhecidas

- a montagem final do bundle continua sem cronômetro por etapa;
- `cpu` não informa o modelo do processador, e `commit` não indica árvore alterada;
- as fixtures sintéticas exercitam só negrito (operação de run);
- a contagem de parágrafos e runs cobre só `word/document.xml`;
- documento que estoura o prazo nas duas variantes gera diagnóstico, mas nenhum tempo total;
- a verificação de timeout usa o gancho de teste; o comportamento em Linux fica verificado pelo CI, em `ubuntu-latest`.


## Escopo da correção posterior à auditoria 0059D

O head seguinte incorpora o L2 e os ajustes pequenos aceitos para o mesmo ciclo:

- `safety_gate.resolve_run_formatting` e `safety_gate.resolve_paragraph_formatting` são instrumentados como `safety_gate_formatting_resolution`; a hierarquia e os tempos exclusivos refletem essa inclusão;
- o processo pai remove `BENCHMARK_0059_TEST_HOLD_AFTER` do ambiente dos workers, salvo autorização explícita usada pelos testes;
- execuções completas registram `patches_completed`;
- o teste de modo DOCX identifica corretamente uma execução fora de uma árvore Git e a documentação explica o alcance limitado de `input_unchanged_in_memory`.

A reauditoria deve confirmar que os nomes importados pelo SafetyGate são realmente os exercitados, que a restauração continua exata em exceções e que os testes do gancho não deixam o ambiente de medição contaminado. O head a auditar é o informado pelo PR, após a conclusão do CI.
