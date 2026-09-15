# Relatório do ciclo 0059: medição de desempenho

Registro documental do fechamento da medição oficial do ciclo 0059. Nenhum código de produção foi alterado neste ciclo nem neste registro.

Todos os valores abaixo foram extraídos dos dois arquivos de resultado e conferidos contra eles em 2026-09-15. Medianas de três execuções por variante; percentuais de etapa calculados sobre a mediana da variante instrumentada.

## 1. Ferramenta e commit medido

| Item | Valor |
| --- | --- |
| Ferramenta | `tools/benchmark_0059.py` (documentação em `docs/benchmarks/0059-benchmark-tool.md`) |
| Introdução da ferramenta | PR #58, squash `99cde017f956e223cdc31b4ca2aa5e3004fb0490`, mesclado em 2026-09-14T12:30:17Z, CI run `34843782049` |
| Diagnósticos por etapa | PR #59, squash `84879124d4f9868fd09df751b992eef967dbd463`, mesclado em 2026-09-14T17:09:43Z, CI run `34873050614` |
| Commit registrado em todas as execuções | `84879124d4f9868fd09df751b992eef967dbd463` |
| Árvore de trabalho | o campo `commit` não indica alterações locais (limitação conhecida da ferramenta) |

Protocolo aplicado em cada caso ou documento:

- duas variantes: `reference`, que fornece o total oficial (`total_seconds`), e `instrumented`, que fornece a divisão por etapa;
- ordem fixa ABBA: referência, instrumentada, instrumentada, referência, e assim por diante, sem aleatoriedade;
- `--repeats 3`, isto é, seis execuções por caso ou documento (três por variante);
- `stage_seconds` inclusivos e `stage_seconds_exclusive` derivados pela hierarquia declarada em `timing_semantics`;
- a pós-condição tem filhos próprios (`postcondition_parse`, `postcondition_style_catalog`, `postcondition_target_resolution`, `postcondition_formatting_resolution`), separados do `parse` da avaliação;
- a resolução de formatação do SafetyGate é medida à parte (`safety_gate_formatting_resolution`).

## 2. Ambiente

| Item | Valor |
| --- | --- |
| Sistema | Ubuntu (informado); registrado como `Linux`, kernel `7.0.0-31-generic`, `x86_64` |
| Python | 3.12.3 |
| `lxml` / zlib | 6.1.3 / 1.3 |
| RAM | 16.042.893.312 bytes |
| CPU | `x86_64` (`platform.processor()` não informa o modelo) |
| Perfil dos documentos reais | `builtin-academic-0059`: 12 pt, entrelinha 1,5, justificado; SHA-256 `cf6b338aa873ebb6ef2e49e9521f0f1d1cb8431afea166658bd9982a2bce8d10` |
| Sintético | 2026-09-14, 17:34:03 a 18:05:41 UTC; prazo de 1.800 s por execução |
| Documentos reais | 2026-09-14, 21:18:41 a 23:26:16 UTC; prazo de 3.600 s por execução |

O ambiente e o commit são idênticos em todas as 90 execuções sintéticas e nas 36 execuções reais.

## 3. Arquivos de resultado

Os resultados ficam fora do repositório. Só os hashes são registrados aqui.

| Arquivo (Ubuntu) | Bytes | SHA-256 |
| --- | ---: | --- |
| `/home/fca/benchmark-0059/sintetico-full.json` | 961.810 | `23bddc80fba62ff9cbcd9c6ef812bf3945d2ae721f44a3e01db65efbc7d87226` |
| `/home/fca/benchmark-0059/reais-full.json` | 1.215.433 | `659f9360f7b6d4881b5b5c0ee27f07a94eb2a40d45931efc06101c57611a6331` |

Os JSONs registram, de cada documento, apenas nome do arquivo, tamanho e SHA-256. Não contêm texto dos documentos nem caminho absoluto: `--record-docx-path` não foi usado, e a busca por caminhos no arquivo não encontrou nenhum.

## 4. Linha de base sintética

Casos gerados em memória por `make_docx`, com operações de negrito em run. Os 15 casos terminaram em `quiescent`, com as alterações esperadas aplicadas e sem timeout, erro ou execução incompleta.

| Caso | Parágrafos | Alterações | Mediana oficial | Por alteração | Pós-condição / patch | Dois parses / total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A1 | 50 | 5 | 0,33 s | 0,066 s | 90,0% | 28,3% |
| A2 | 100 | 5 | 0,70 s | 0,140 s | 93,8% | 34,7% |
| A3 | 200 | 5 | 1,62 s | 0,325 s | 95,9% | 43,5% |
| A4 | 400 | 5 | 4,22 s | 0,844 s | 97,5% | 54,4% |
| A5 | 800 | 5 | 14,58 s | 2,915 s | 98,8% | 69,8% |
| B1 | 400 | 0 | 0,53 s | — | — | 39,4% |
| B2 | 400 | 1 | 1,46 s | 1,462 s | 97,4% | 43,6% |
| B3 | 400 | 5 | 4,25 s | 0,850 s | 97,5% | 54,3% |
| B4 | 400 | 10 | 7,77 s | 0,777 s | 97,6% | 57,1% |
| B5 | 400 | 20 | 14,84 s | 0,742 s | 97,6% | 58,7% |
| B6 | 400 | 40 | 29,00 s | 0,725 s | 97,6% | 59,2% |
| B7 | 400 | 80 | 57,81 s | 0,723 s | 97,6% | 59,2% |
| B8 | 400 | 160 | 116,59 s | 0,729 s | 97,6% | 58,5% |
| C1 | 100 | 40 | 4,93 s | 0,123 s | 93,9% | 36,5% |
| C2 | 800 | 20 | 51,83 s | 2,592 s | 98,9% | 75,3% |

"Dois parses" soma o `parse` da avaliação e o `postcondition_parse`.

Leitura:

- **Linear no número de alterações.** Com 400 parágrafos, o custo marginal estabiliza em cerca de 0,72 a 0,78 s por alteração a partir de 10 alterações: cada alteração paga um ciclo completo.
- **Superlinear no tamanho.** Com 5 alterações, dobrar os parágrafos multiplica o tempo por 2,1; 2,3; 2,6 e 3,5. De 50 para 800 parágrafos (16 vezes), o tempo cresce 44 vezes. A participação dos dois parses sobe de 28% para 70%.
- **Resolução no SafetyGate.** As chamadas seguem exatamente `n(n+1)/2`: 15, 55, 210, 820, 3.240 e 12.880 para 5, 10, 20, 40, 80 e 160 alterações. O custo absoluto, porém, ainda é pequeno nesses tamanhos: 1,79 s de 116,6 s em B8 (1,5%).

## 5. Seis documentos reais

Documentos identificados apenas por nome, tamanho e SHA-256. Nenhum deles foi copiado ou incorporado ao repositório.

| Documento | Bytes | SHA-256 |
| --- | ---: | --- |
| `A Boca da Lei Feita Máquina.docx` | 50.532 | `dc1015b8b655f0e757f0648a20ef3f004213e3c4120d9b9268774e7d66c9c311` |
| `Artigo Claudir.docx` | 47.033 | `1ef4aec271ed877e3dfdd3aec5a7ae0b408233ecc4ec8986a9ba2af67618c901` |
| `artigo Hellen-2.docx` | 131.824 | `29677ceec0c5a877b067ca80d27b484351cfaf44fbe6296dc8b272ddcdebd4d4` |
| `Diovana.docx` | 55.115 | `1884bcea9e665ab8e2e1885536f166b5c0d3d088f889a9f4fbae073ad327256c` |
| `Dissertação final .docx` | 3.244.874 | `bf0ac52941af21293da636892891c938b17c7c9240f59dc88a394a06522da6aa` |
| `Soberania_verificavel_sem_metadados.docx` | 52.828 | `31edad8936d1ca2110876c51b6701eafac1a139de37948326debb7b13ff52862` |

### Tempos e quantidades de alterações

| Documento | Execuções completas | Alterações automáticas | Itens de revisão | Revisão no conjunto | Mediana oficial (mín.–máx.) | Pico de memória |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A Boca da Lei Feita Máquina | 6/6 | 51 | 84 | 62,2% | 78,9 s (78,7–79,4) | 60 MiB |
| Artigo Claudir | 6/6 | 53 | 9 | 14,5% | 48,0 s (47,6–48,1) | 48 MiB |
| artigo Hellen-2 | 6/6 | 288 | 100 | 25,8% | 458,3 s (458,2–463,5) | 57 MiB |
| Diovana | 6/6 | 99 | 23 | 18,9% | 122,7 s (122,4–122,8) | 54 MiB |
| Dissertação final | 6/6 | 63 | 130 | 67,4% | 502,7 s (500,1–503,6) | 170 MiB |
| Soberania verificável sem metadados | 6/6 | 26 | 6 | 18,8% | 59,7 s (59,4–59,8) | 74 MiB |

Todas as execuções terminaram em `quiescent`, sem alterações não aplicadas, sem timeout e sem erro. "Revisão no conjunto" é `revisão / (automáticas + revisão)`. Não indica quanto do documento está errado; indica quanto das intervenções identificadas depende de decisão humana. O pico de memória é a mediana da variante de referência.

Comparação com a medição inicial de 2026-09-11 (seção "Medição inicial com corpus DOCX real" do handoff):

- Boca, Claudir, Diovana e Soberania repetem as mesmas alterações e itens de revisão;
- Hellen-2 e Dissertação, que antes não concluíam de ponta a ponta, agora concluem, com as 288 e 63 alterações previstas aplicadas;
- os itens de revisão de Hellen-2 passam de 99 previstos para 100 medidos, valor estável nas seis execuções. A diferença não foi investigada neste registro.

## 6. Equivalência entre referência e instrumentação

Nos seis documentos, `equivalence_mismatch_positions` está vazio, e as seis execuções de cada documento têm o mesmo status, alterações aplicadas, não aplicadas e itens de revisão. A instrumentação altera tempos, não resultados.

A diferença mediana entre as variantes (`instrumentation_overhead_median_seconds`) ficou entre −2,69 s (Hellen-2) e +0,27 s (Diovana), ou seja, no máximo 0,6% do total, dentro da variação entre execuções.

## 7. Integridade dos originais

**Os arquivos DOCX originais não foram modificados.** Em todas as 36 execuções dos seis documentos, `input_unchanged_on_disk = true`: ao fim de cada execução, a ferramenta relê o arquivo em disco, recalcula o SHA-256 e compara com o valor inicial. O modo `--docx` processa os bytes em memória e não grava nem copia o documento.

## 8. Gargalo

### A pós-condição dentro do patch

Nos documentos reais, a pós-condição ocupa de **83,0% a 90,0%** do tempo de patch (`postcondition_share_of_patch_total`): Boca 86,2%, Claudir 84,9%, Hellen-2 90,0%, Diovana 87,9%, Dissertação 83,0% e Soberania 88,4%. Dentro dela, de 92,6% a 96,4% é o parse do pacote reempacotado.

### O ciclo inteiro por alteração

O patch, porém, é só uma parte do tempo total. Divisão por etapa na variante instrumentada:

| Documento | Avaliações | Parse | Decisão | Planejamento | SafetyGate | Patch | (pós-condição) | Dois parses | Etapas do ciclo |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Boca | 52 | 20,7% | 23,8% | 10,7% | 10,7% | 24,8% | 21,4% | 41,0% | 93,7% |
| Claudir | 54 | 16,6% | 27,6% | 12,3% | 12,4% | 20,6% | 17,6% | 32,9% | 92,9% |
| Hellen-2 | 289 | 22,2% | 18,5% | 10,8% | 13,6% | 25,9% | 23,3% | 44,3% | 94,2% |
| Diovana | 100 | 19,7% | 20,3% | 12,1% | 12,9% | 23,8% | 20,9% | 39,3% | 93,3% |
| Dissertação | 64 | 27,5% | 19,0% | 7,0% | 6,9% | 33,7% | 28,0% | 54,5% | 96,3% |
| Soberania | 27 | 26,6% | 14,4% | 8,6% | 8,6% | 30,4% | 26,9% | 52,2% | 94,3% |

"Avaliações" é o número de parses da avaliação: sempre alterações aplicadas + 1. "Etapas do ciclo" soma as oito etapas de topo; o restante inclui a montagem final do bundle e as gravações de progresso. Análise e registro de transformação ficam em até 0,3%.

Leitura técnica:

- a pós-condição sozinha responde por 17,6% a 28,0% do total. Otimizar só a pós-condição limitaria o ganho a essa faixa;
- o custo dominante é a **repetição do ciclo completo a cada alteração**: parse da avaliação, decisão, planejamento, SafetyGate e patch com pós-condição somam de 92,9% a 96,3% do total;
- o pacote é analisado duas vezes por alteração (avaliação e pós-condição), o que sozinho ocupa de 32,9% a 54,5%;
- nos documentos reais, a decisão pesa mais que no sintético (14,4% a 27,6%), quase toda em resolução de formatação;
- a resolução de formatação no SafetyGate cresce quadraticamente em chamadas (41.616 em Hellen-2), mas custa de 0,2% a 2,7% do total. É um risco para documentos com muito mais alterações, não o gargalo atual.

Portanto, a conclusão de que o gargalo é a repetição da pós-condição e das validações a cada alteração se confirma, com uma precisão: o que se repete é o ciclo inteiro de avaliação, validação e verificação, não apenas a pós-condição.

## 9. Dependência de revisão humana

A proporção de revisão varia de 14,5% a 67,4%. Em dois documentos (Boca e Dissertação), a maior parte das intervenções identificadas depende de decisão humana. Isso decorre das regras congeladas (ausência de estilo resolvido, containment e escolhas incomensuráveis vão para revisão) e não é defeito de desempenho. É, porém, um dado de produto: reduzir o tempo não reduz o trabalho do revisor. A qualidade e a ordenação da revisão continuam como trabalho a priorizar depois da otimização.

## 10. Decisão

- A medição do ciclo 0059 está encerrada.
- O próximo ciclo trata de uma **mudança arquitetural para reduzir reprocessamentos** entre alterações sucessivas, com contrato próprio, auditoria adversarial e critério de aceitação medido com esta mesma ferramenta.
- A proposta deve atacar a repetição do ciclo completo (em especial os dois parses por alteração e a reavaliação de decisão e planejamento), e não apenas a pós-condição.
- **Nenhuma nova propriedade** entra antes dessa otimização.
- A mudança deve preservar o resultado funcional atual: mesmas alterações, mesmos itens de revisão, mesmo DOCX limpo e mesmas garantias de pós-condição. Otimizar não pode significar deixar de verificar.
- Os dois JSONs deste ciclo, identificados pelos hashes da seção 3, são a linha de base de comparação para o próximo.

## 11. Registro de auditorias do ciclo

- `docs/audits/0059-claude-opus-benchmark-review.md` — auditoria do PR #58;
- `docs/audits/0059b-claude-opus-benchmark-reaudit.md` e `0059c-claude-opus-benchmark-reaudit.md` — reauditorias do PR #58;
- `docs/audits/0059d-benchmark-diagnostics-audit-brief.md` — brief dos diagnósticos;
- `docs/audits/0059d-deepseek-flash-41-benchmark-audit.md` — parecer do DeepSeek Flash 4.1 sobre `c47b6eb`;
- `docs/audits/0059e-claude-opus-benchmark-diagnostics-reaudit.md` — reauditoria do Claude Opus sobre `8234d9d`.

Pendência menor da ferramenta, sem efeito sobre a validade da medição: teste da remoção padrão de `BENCHMARK_0059_TEST_HOLD_AFTER` do ambiente dos workers (M2 da reauditoria 0059E).
