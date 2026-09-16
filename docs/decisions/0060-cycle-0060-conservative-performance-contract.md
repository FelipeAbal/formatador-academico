# Decisão 0060A: contrato do ciclo 0060 — otimização conservadora com equivalência exata

**Status:** PROPOSTA, revisão 5, com as escolhas pendentes já decididas
**Data:** 2026-09-16
**Base:** `main` após o merge do PR #60, commit `4bcda308a4975f2bb84d87ab4738faaed463bb75`
**Depende de:** `docs/benchmarks/0059-measurement-report.md`; auditoria arquitetural do Claude Opus sobre o mesmo commit; pareceres do DeepSeek Flash 4.1 sobre as revisões 1, 2, 3 e 4
**Não altera:** nenhum código de produção. Esta decisão é contrato e critério, não implementação.

**Revisão 5 — o que mudou em relação à revisão 4**

1. **Bloqueante corrigido:** desfeita a circularidade do limite de memória. O limite definitivo passa a ser condição para **integrar** o PR do 0060D, e não para **iniciar** a fase.
2. Mecanismo de fixação do oráculo especificado: `git worktree` ou `git archive` pelo SHA completo, em caminho temporário, nunca a árvore de trabalho atual.
3. Gating explícito entre fases, em seção própria (§3.12).
4. Distinção entre entregáveis do 0060A, pré-requisito do 0060B e pré-requisito de integração do 0060D.
5. Mantida a natureza manual e autorizada da verificação dos seis DOCX reais no 0060B.

Nada mais foi alterado: critérios de equivalência, rejeição do agrupamento, ordem dos subciclos, as sete escolhas registradas, `PatchResult`, as cinco igualdades de reuso e os nove gatilhos de fallback permanecem como na revisão 4.

**Revisão 4 — o que mudou em relação à revisão 3**

1. Separação explícita entre o compartilhamento de parse do 0060D e o fallback semântico, que é assunto do 0061.
2. A medição de tamanho da IR fica no 0060A, por ferramenta separada; a pergunta correspondente saiu da lista de pendências.
3. A tabela do critério passa a ser descrita como seis linhas que cobrem nove células combinadas, com os casos assimétricos nomeados.
4. Limite de memória definido sem ambiguidade: `1,15 × (pico de 0059 + delta medido)`.
5. A verificação nos seis DOCX reais é procedimento manual autorizado no Ubuntu, separada do CI, que usa apenas fixtures sintéticas.
6. `PatchResult` permanece intacto, com entrega por API interna ou retorno aditivo separado.
7. O 0061 avaliará os normativos 0015 e 0022, com 0018 e 0023 reafirmados.
8. Mantidos os nove gatilhos de fallback integral e as cinco igualdades simultâneas do reuso.
9. Oráculo em `tools/oracle_0060.py`, com testes em `tests/test_oracle_0060.py`.
10. Critério de abertura do 0061 fixado em três casos, sem abertura automática na faixa parcial.
11. **Retirada** do 0060D qualquer forma de reuso semântico após rejeição.
12. Proveniência da auditoria de arquitetura corrigida: os números vieram do parecer entregue a Felipe, que não está versionado no repositório.

---

## 1. Contexto

Medição oficial do ciclo 0059, no Ubuntu, Python 3.12.3, `lxml` 6.1.3, commit `84879124…`, seis DOCX reais, seis execuções por documento em ordem ABBA:

- a pós-condição ocupa de 83,0% a 90,0% do tempo de patch, e de 17,6% a 28,0% do tempo total;
- o ciclo completo repetido a cada alteração ocupa de 92,9% a 96,3% do total;
- os dois parses por alteração ocupam de 32,9% a 54,5% do total;
- referência e instrumentação não divergiram;
- `input_unchanged_on_disk = true` nas 36 execuções;
- medianas dos dois mais pesados: 458,3 s (artigo Hellen-2) e 502,7 s (Dissertação final).

Auditoria arquitetural, por sondas em fixtures sintéticas e leitura de código:

1. **parser quadrático no número de irmãos**: 87% do parse com 800 parágrafos; memoizar a posição dentro de uma chamada produziu IR idêntica e sessão 2,0× a 3,6× mais rápida;
2. **cada Decision serializada cerca de 11 vezes por iteração**;
3. **um patch não muda o valor semântico de nenhum outro alvo**, mas muda o hash físico do alvo e de todos os ancestrais.

Números de fixtures sintéticas no macOS: servem para ordenar o trabalho, não para prometer ganho em documento real.

---

## 2. Decisão

1. **Agrupamento de operações em lote e atomicidade multi-alvo ficam rejeitados neste ciclo.**
2. O 0060 aplica apenas otimizações compatíveis com a cadeia atual de um patch por vez, capazes de provar equivalência exata.
3. Cinco fases em PRs próprios, com auditoria adversarial independente: **0060A** (contrato), **0060B** (parser), **0060C** (serialização), **0060D** (snapshot verificado) e **0060E** (medição oficial). O **0061** é condicional e nunca automático.
4. **Avaliação incremental e SafetyGate incremental não fazem parte do 0060.**
5. Nenhuma nova propriedade do slice automático entra antes do fim do 0060E.
6. Qualquer fase que não prove equivalência exata é revertida, não negociada.

Motivo da rejeição do agrupamento: `operation_plan_ref`, os SHAs intermediários e a ordem real de aplicação entram em cada `TransformRecord` e chegam ao relatório humano. Juntar iterações muda artefato entregue ao usuário, exige emendas em pelo menos seis contratos e um validador de delta múltiplo, que é código novo e crítico para a segurança.

---

## 3. Definições obrigatórias

### 3.1 Equivalência exata

Para toda tripla

```text
(package_snapshot: bytes, profile: ProcessingProfile, max_applied_operations: int)
```

a execução otimizada produz artefatos **idênticos** aos da referência congelada em `4bcda30`, no mesmo ambiente suportado. Idêntico significa igualdade de bytes nos artefatos serializados e igualdade campo a campo nos objetos congelados.

A exigência vale nos caminhos de falha: mesmo tipo de exceção e mesma condição de disparo.

A referência vive como oráculo de teste e **nunca** como caminho alternativo em runtime.

### 3.2 Ferramentas do ciclo

1. **`tools/benchmark_0059.py` permanece intacto durante todo o ciclo.** Ele define a linha de base e a semântica de tempo; alterá-lo invalidaria a comparação.
2. O oráculo fica em **`tools/oracle_0060.py`**, com testes próprios em **`tests/test_oracle_0060.py`**. Ele **não importa e não modifica** `tools/benchmark_0059.py`.
3. O comparador de artefatos por hash e a instrumentação de tamanho da IR e de pico de memória são scripts separados, sob `tools/` ou `tests/`, com a mesma proibição de tocar no benchmark.
4. Se, apesar disso, o benchmark precisar mudar, a mudança vira PR próprio e anterior, **a linha de base 0059 precisa ser inteiramente refeita** antes de qualquer comparação, e esta decisão precisa de emenda.

**Mecanismo de fixação do código de referência.**

1. O código de referência é o commit completo **`4bcda308a4975f2bb84d87ab4738faaed463bb75`**. O SHA curto nunca é usado para fixar a referência, apenas para citação em texto.
2. No CI e em qualquer execução do oráculo, a referência é obtida por **`git worktree add`** num caminho temporário, ou por **`git archive`** extraído num caminho temporário, sempre pelo **SHA completo**.
3. **Proibido usar a árvore de trabalho atual como referência implícita.** O oráculo precisa falhar, e não cair no código corrente, se a referência não puder ser materializada pelo SHA.
4. O oráculo verifica, antes de comparar, que a referência materializada corresponde ao SHA fixado, e registra esse SHA em toda saída de comparação.
5. O caminho temporário é removido ao fim da execução; nenhuma referência materializada é versionada nem reaproveitada entre execuções.

### 3.3 Serializador canônico do oráculo

Implementado em `tools/oracle_0060.py`. Usa serializadores canônicos congelados, nunca `repr` ou `pickle`. Convenção: enums viram string, `Decimal` vira string, tuplas viram array, `sort_keys=True`, separadores compactos, UTF-8, sem timestamp e sem valor aleatório.

| Artefato comparado | Serializador |
| --- | --- |
| `ClassificationResult`, com evidências, avisos, metadata, proveniência e `parent_anchor` | `classification.serialization` |
| `Decision`, com `evidence_ref`, `decision_warnings` e `analysis_reason` | `decision.serialization.serialize_decision` |
| `PlannedOperation`, `PlanningResult` e `OperationPlan` | `operation_plan.serialization` |
| `GateResult` e `SafetyGateReport` | `safety_gate.serialization` |
| `TransformRecord` | `transform_log.serialization`, com `transform_ref` |
| `ProcessingReport` | `processing_report.serialization`, com `processing_report_ref` |
| DOCX limpo, Review DOCX, relatório humano, relatório técnico e manifesto | SHA-256 dos bytes, com `filename` e `DeliveryRole` na ordem de `ROLE_ORDER` |

**Duas lacunas, preenchidas dentro do oráculo e nunca como API pública:**

1. **`SessionFinding`**, que não tem serializador congelado: o oráculo define um, com `kind`, `decision_ref`, `operation_ref`, `target` e `reason`.
2. **Envelope do `ProcessingSessionResult`**, que também não tem: o oráculo compõe os serializadores existentes na ordem `processing_session_version`, `status`, `profile_ref`, `input_package_sha256`, `output_package_sha256`, `sha256(output_package_bytes)`, `transforms`, `final_classifications`, `final_decisions` e `findings`, preservando a ordem real de cada tupla.

Se algum campo exigido pelo envelope não estiver exposto por modelo congelado, a fase para e abre emenda específica.

**Teste cross-process obrigatório do envelope**, em `tests/test_oracle_0060.py`: duas execuções em subprocessos distintos, com `PYTHONHASHSEED` diferente em cada um, produzindo bytes idênticos, para referência e para otimizado. Sem isso, o oráculo poderia mascarar dependência de ordenação de dicionário.

### 3.4 Campos e artefatos que precisam permanecer idênticos

**`ProcessingSessionResult`:** `status`; `input_package_sha256`; `output_package_sha256`; `output_package_bytes`; `transforms`, na mesma ordem e com todos os campos de cada record, inclusive `operation_ref`, `operation_plan_ref`, `decision_ref`, `profile_ref`, `rule_ref`, `target` com o hash pré-transformação, `precondition_observed`, `desired_value`, `input_package_sha256`, `output_package_sha256` e `changed_part`; `final_classifications`, `final_decisions` e `findings`, na mesma ordem.

**Derivados:** `serialize_transform_record` e `transform_ref` de cada record; `serialize_processing_report`; relatório humano; Review DOCX; os cinco arquivos do Product Delivery, com os mesmos nomes e papéis.

**Intermediários exigidos:** número de iterações lógicas; ordem real de aplicação; SHA de cada snapshot intermediário; `operation_plan_ref` de cada iteração.

**Modelos que permanecem intactos:** `PatchResult`, `GateClearedOperation`, `TransformRecord`, `ProcessingSessionResult`, `ProcessingReport` e os modelos de entrega. Nenhuma fase acrescenta, remove ou reordena campo de modelo congelado.

### 3.5 Preservação de TransformLog, ProcessingReport, Review DOCX, Product Delivery e allowed-delta

> **Nenhuma fase pode alterar quantas iterações lógicas existem, qual operação é aplicada em cada uma, nem sobre quais bytes.** As fases só podem deixar de recalcular resultados idênticos.

- **TransformLog (0030, congelado em 0031):** um record por patch, com a cadeia `saída N == entrada N+1`.
- **ProcessingReport (0034, congelado em 0035):** um `AppliedChangeItem` por record, na ordem real.
- **Review DOCX (0036, congelado em 0037):** opera sobre o snapshot final e sobre os itens do relatório.
- **Product Delivery (0038/0047, congelados em 0039/0048):** cinco arquivos comparados por hash, papel e nome.
- **allowed-delta (0028 §20):** permanece unitário; a pós-condição continua sobre bytes relidos do ZIP produzido.

### 3.6 Caches: escopo, registro e invalidação

A interface web usa `ThreadingHTTPServer`, com sessões simultâneas no mesmo processo. Portanto:

1. **Proibido cache em nível de módulo, de classe, global ou em `ContextVar`.** A proibição do `ContextVar` é explícita: ele sobrevive à chamada e é invisível na assinatura.
2. Escopo declarado: de **chamada** (0060B) ou de **avaliação/sessão**, descartado em `finally` (0060C e 0060D).
3. Nenhum cache sobrevive entre duas chamadas públicas.
4. Chaves proibidas: caminho estrutural isolado, índice de parágrafo, qualquer coisa que não identifique o snapshot.
5. **Proibido chavear por igualdade semântica:** `Decimal("1.5") == Decimal("1.50")` e `True == 1`, mas a serialização difere.
6. Registro obrigatório por cache, na decisão da fase: nome; o que guarda; chave exata; escopo; evento de invalidação; custo de memória esperado; teste que prova a invalidação.
7. Invalidação: mudou o snapshot, o cache cai. Consumo exige conferência de SHA; divergência é `ProcessingSessionIntegrityError`, nunca uso degradado. Retém-se apenas o snapshot corrente.
8. Em modo de teste, cada cache expõe acertos, erros e invalidações.
9. Testes obrigatórios: N sessões simultâneas em threads, com documentos e perfis diferentes; e duas sessões em sequência no mesmo processo, na ordem A, B, A.

### 3.7 Duas coisas diferentes que não podem ser confundidas

Esta seção existe porque os dois mecanismos abaixo têm nomes parecidos e riscos opostos.

| | **Compartilhamento de parse — 0060D** | **Reuso semântico — 0061, fora deste ciclo** |
| --- | --- | --- |
| O que reaproveita | o resultado do parse **dos mesmos bytes**, feito uma vez em vez de duas | valor semântico de Analysis e Classification de alvos **não tocados**, entre snapshots diferentes |
| Fronteira | **um único snapshot**, identificado pelo seu SHA | atravessa snapshots |
| Depende do predicado de não interferência? | **não**; é a mesma função, sobre os mesmos bytes | **sim**, integralmente |
| Reaproveita Decision, Classification ou findings? | **nunca** | sim, apenas o valor semântico, com objetos reconstruídos |
| Fase | 0060D | 0061 |

**No 0060 nenhuma fase reusa resultado de avaliação entre snapshots diferentes.** O predicado abaixo é especificação preparatória do 0061, registrada aqui porque o 0060B e o 0060D precisam respeitá-la para não fechar portas.

#### Os quatro planos

| Plano | O que é | Muda quando um run é alterado? |
| --- | --- | --- |
| **Físico** | XML canônico do nó, atributos `xml:` herdados e `physical_hash` | sim, no alvo e em todos os ancestrais |
| **Estrutural** | `structural_path`, `original_index`, cadeia de ancestrais, unicidade do alvo | o caminho do run permanece; o `original_index` dos filhos do run muda quando se cria `w:rPr`, e o mesmo vale para `w:pPr` no parágrafo |
| **Semântico** | valor resolvido pela Analysis, status e classe da Classificação | não, fora do alvo, no slice congelado |
| **Referências derivadas** | `decision_ref`, `operation_ref`, `operation_plan_ref`, `transform_ref`, `TargetClassification.physical_hash`, `DecisionTarget` e `OperationTarget` | sim, por consequência do plano físico, mesmo sem mudança semântica |

Os quatro planos nunca podem ser confundidos. Em especial, o plano estrutural é o motivo de a pós-condição do 0028 §22 proibir comparar `original_index` como identidade.

#### Conjunto de leitura por camada (plano semântico)

| Camada | Lê | Sensível a bold/font_size em run? | Sensível a alignment/spacing.line em parágrafo? |
| --- | --- | :---: | :---: |
| Classificação de parágrafo | tipo de story, texto normalizado, contêiner, `pStyle` resolvido, catálogo | não | não |
| Projeção de run | classe do parágrafo e hash do próprio run | não, quanto ao valor | não |
| Formatação de run | bag do run, `pStyle` do parágrafo, catálogo, `docDefaults` | só o run alvo | não |
| Formatação de parágrafo | bag do parágrafo, catálogo, `docDefaults` | não | só o parágrafo alvo |
| StyleCatalog | `word/styles.xml` | não; o Patcher nunca altera `styles.xml` | não |

#### Condição de reuso verbatim

Um resultado de camada só pode ser reusado verbatim se **as cinco igualdades valerem simultaneamente**, entre o snapshot anterior e o corrente:

1. `physical_hash` do alvo inalterado;
2. `part_sha256` do StyleCatalog inalterado;
3. texto normalizado do alvo, e do parágrafo que o contém, inalterado;
4. `pStyle` resolvido inalterado;
5. conjunto de leitura da camada inalterado, item a item, conforme a tabela acima.

**Hash igual, sozinho, não basta.** Falhando qualquer uma das cinco, o resultado é **reconstruído**, e não remendado.

Mesmo com as cinco igualdades, permanece proibido reusar `ClassificationResult` ou `Decision` **verbatim** se qualquer referência derivada mudou: o reuso admissível é o do **valor semântico**, que alimenta objetos novos, com `physical_hash`, `DecisionTarget`, `OperationTarget`, `TargetClassification`, `decision_ref`, `operation_ref` e `operation_plan_ref` recalculados.

#### Fallback integral obrigatório

Qualquer um destes nove gatilhos obriga o recálculo completo da avaliação, sem reuso de nenhuma camada:

1. `property_slot` fora do conjunto conhecido do slice;
2. dependência do valor por estilo ou por cadeia `basedOn`;
3. presença de numeração relevante (`w:numPr`) em qualquer nível aplicável;
4. direção bidirecional relevante (`w:bidi`);
5. alvo em forma física não canônica;
6. cadeia de evidência incompleta, ou status de Analysis diferente de resolvido;
7. mutação que tocar mais nós do que o previsto para a operação;
8. mudança de catálogo, de texto ou de `pStyle`;
9. rejeição do Patcher que altere `findings` ou o snapshot.

O fallback é integral: não existe reuso parcial em caminho degradado.

#### Validade e validação

O predicado vale só para o slice congelado. **Qualquer propriedade nova precisa declarar seu conjunto de leitura e refazer a prova antes de entrar.** Uma propriedade que altere `pStyle`, numeração, texto ou `styles.xml` invalida a tabela semântica.

Quando o 0061 for aberto, a validação exige modo sombra no CI, recalculando tudo e comparando a cada iteração, com falha na primeira divergência.

### 3.8 Medição e verificação: CI e Ubuntu

Duas trilhas separadas, que nunca se misturam.

**Trilha do CI, automática.** Usa **apenas fixtures sintéticas**, versionadas no repositório: diferenciais contra o oráculo, testes de equivalência de IR, testes de cache, concorrência, sequência, determinismo e cross-process. Nenhum DOCX real entra no CI, nem como arquivo nem como hash de conteúdo.

**Trilha do Ubuntu, manual e autorizada.** Roda na máquina de Felipe, com os seis DOCX reais fora do repositório, sob autorização explícita dele a cada rodada. Cobre a medição de desempenho e as verificações que exigem documento real: IR byte-idêntica no 0060B, identidade entre pós-condição e nova avaliação no 0060D, delta de memória e a medição oficial do 0060E. Nos documentos, registram-se apenas nome, tamanho, SHA-256 e os hashes comparados. O procedimento é descrito no relatório da fase, para ser reproduzível, e seu resultado é anexado ao PR como texto, não como arquivo de documento.

**Protocolo de medição**, na trilha do Ubuntu, com `tools/benchmark_0059.py` intacto (§3.2):

1. linha de base sintética completa, `--repeats 3`, `--timeout 1800`;
2. os seis documentos reais, `--repeats 3`, `--timeout 3600`, perfil `builtin-academic-0059`, arquivos fora do repositório e sem `--record-docx-path`;
3. saída gravada fora do repositório; em documento entram apenas hashes, nomes, tamanhos e SHA-256;
4. comparação com `sintetico-full.json` `23bddc80…` e `reais-full.json` `659f9360…`;
5. verificação de `input_unchanged_on_disk` em todas as execuções;
6. equivalência por hash dos cinco arquivos entregues, referência × otimizado, por documento.

Para cada documento registram-se **mínimo, mediana e máximo** da variante `reference`. A variação observada em 0059 entre mínimo e máximo foi de no máximo 1,2% da mediana; esse é o ruído de fundo aceito.

Cada fase de código roda um recorte sintético e os dois documentos mais pesados. A medição completa é o 0060E.

### 3.9 Critério de desempenho para Hellen-2 e para a Dissertação

```text
reducao = 1 - (mediana_0060E / mediana_0059)

mediana_0059:
    artigo Hellen-2       458,3 s   (min 458,2  max 463,5)
    Dissertação final     502,7 s   (min 500,1  max 503,6)
```

A tabela tem **seis linhas, que cobrem as nove células combinadas** das três faixas de cada documento, incluindo os dois casos assimétricos, em que um documento atinge a meta e o outro fica no piso:

| artigo Hellen-2 | Dissertação final | Resultado | Consequência |
| --- | --- | --- | --- |
| `>= 40%` | `>= 40%` | **meta atingida** | ciclo encerrado; o 0061 não abre automaticamente |
| `>= 40%` | `>= 25%` e `< 40%` | **parcial** (assimétrico) | integra, registra meta não atingida e obriga **decisão registrada** sobre o 0061 |
| `>= 25%` e `< 40%` | `>= 40%` | **parcial** (assimétrico) | idem |
| `>= 25%` e `< 40%` | `>= 25%` e `< 40%` | **parcial** | idem |
| `< 25%` | qualquer valor | **insuficiente** | **0061 obrigatório** |
| qualquer valor | `< 25%` | **insuficiente** | **0061 obrigatório** |

Em todos os casos, a integração das fases exige equivalência exata e ausência de regressão (§3.10). A meta é relativa à linha de base de cada documento; não há meta absoluta em segundos, que dependeria de hardware.

### 3.10 Regra contra regressão

1. **Bloqueio:** nenhum documento pode ter mediana acima de 1,03 × mediana de 0059.
2. **Justificativa obrigatória:** qualquer mediana acima da de 0059, mesmo dentro dos 3%, exige justificativa escrita e concordância explícita de Felipe.
3. **Regra de máximo:** o máximo de cada documento não pode superar o máximo de 0059 em mais de 5%.
4. **Regra de forma:** a dispersão relativa, `(máximo − mínimo) / mediana`, não pode passar de 3%; acima disso a medição é instável e precisa ser repetida.
5. A linha de base sintética não pode regredir em nenhum dos 15 casos, pelo mesmo critério de mediana.

### 3.11 Memória

**Limite definitivo:**

```text
pico permitido = 1,15 × (pico de memória da linha de base 0059
                         + delta de pico causado pela retenção da IR)
```

**Trava provisória**, válida enquanto o limite definitivo não estiver escrito: nenhum documento pode ultrapassar o dobro do pico registrado em 0059, que vai de 48 MiB a 170 MiB conforme o documento.

**Sequência, sem circularidade:**

1. O **0060A entrega a ferramenta** de medição de tamanho da IR e de pico de memória, como script separado, sem tocar em `tools/benchmark_0059.py` (§3.2). Ele não mede nada em documento real.
2. O **delta real é medido na branch do 0060D**, com a implementação já escrita, comparando a execução que retém a IR do snapshot com a que não retém. Mede-se o delta, e não o tamanho da IR isolado: assumir que o pico cresce pelo tamanho inteiro da IR seria errado, porque a IR antiga é liberada quando o snapshot muda.
3. A medição roda na trilha do Ubuntu (§3.8), nos seis documentos reais, sob autorização explícita.
4. O **limite definitivo é fixado por emenda a esta decisão antes da integração do PR do 0060D**, com o delta já medido. **Ele não é requisito para iniciar o 0060D**, porque só pode ser calculado depois que a fase existir.
5. Até essa medição, vale a trava provisória do item anterior, inclusive durante o desenvolvimento do 0060D.
6. O registro grava apenas nome, tamanho, SHA-256 e os bytes medidos.

Referência de ordem de grandeza, apenas indicativa: em fixtures sintéticas a IR ocupa cerca de 28 vezes o tamanho do DOCX (1,8 MiB para 67 KiB; 3,7 MiB para 132 KiB). Esse fator **não pode ser extrapolado** para a Dissertação, onde a maior parte dos 3,2 MB é imagem, que não vira registro.

### 3.12 Dependências e gating entre fases

| Fase | Entregáveis | Pré-requisito para **iniciar** | Pré-requisito para **integrar** |
| --- | --- | --- | --- |
| **0060A** | oráculo `tools/oracle_0060.py` com `tests/test_oracle_0060.py`; comparador de artefatos por hash; ferramenta de medição de IR e de pico de memória; fixture de estresse estrutural; este contrato | contrato auditado | oráculo e comparador funcionando sobre fixtures sintéticas, com testes próprios verdes |
| **0060B** | parser com índice por chamada; nota de erratum a 0009 e 0011 | **0060A integrado**, com oráculo disponível e mecanismo de fixação definido (§3.2) | IR idêntica no CI e nos seis DOCX reais; sem regressão |
| **0060C** | `EvaluationContext` e reuso de bytes de serialização | 0060B integrado | diferenciais idênticos; escolha de fronteira registrada |
| **0060D** | compartilhamento do parse verificado do mesmo snapshot; emendas a 0028 e 0032 | 0060C integrado; **não depende do limite definitivo de memória** | **delta de memória medido e limite definitivo fixado por emenda**; identidade verificada; diferenciais idênticos |
| **0060E** | relatório de medição e atualização do handoff | 0060D integrado | critérios do §3.9, §3.10 e §3.11 |

Observações de dependência:

- o **0060B depende funcionalmente do oráculo**, porque é ele que prova a IR idêntica; sem o 0060A integrado, a fase não tem como ser aprovada;
- a **ferramenta de memória é entregue no 0060A, mas só é usada no 0060D**, na medição do delta;
- nenhuma fase começa antes de a anterior estar integrada, e nenhuma é integrada sem auditoria adversarial.

---

## 4. Avaliação do critério preliminar

| Critério proposto originalmente | Parecer | Forma adotada |
| --- | --- | --- |
| Nenhum documento piora mais de 10% | frouxo: o ruído medido é de 1,2% da mediana | §3.10: bloqueio em 3% pela mediana, mais regras de máximo e de dispersão |
| Redução mediana de 40% nos dois mais pesados | ambicioso e plausível: os dois parses ocupam 44,3% e 54,5% do total nesses documentos | mantido como meta, com piso de 25% e tabela fechada (§3.9) |
| Equivalência sem divergências | obrigatório | mantido, estendido aos caminhos de falha e aos cinco arquivos entregues |
| Todos os testes atuais passando | necessário, insuficiente | mantido, somado aos testes novos e aos diferenciais |
| Três execuções ABBA com a ferramenta 0059 | correto | mantido, com mínimo, mediana e máximo, e com a ferramenta intacta |

Acréscimos obrigatórios: os seis documentos mantêm exatamente as alterações e os itens de revisão de 0059 (51/84, 53/9, 288/100, 99/23, 63/130 e 26/6); nenhuma execução pode terminar em timeout ou erro; `input_unchanged_on_disk` verdadeiro em todas; memória conforme §3.11.

---

## 5. Fases

### 0060A — contrato, critérios e oráculo

**Objetivo.** Fixar decisão, equivalência, oráculo, regras de cache e critérios antes de qualquer otimização.

**Entregáveis.**

1. este documento;
2. **oráculo** em `tools/oracle_0060.py`, fixado no commit completo `4bcda308a4975f2bb84d87ab4738faaed463bb75` pelo mecanismo do §3.2, com `tests/test_oracle_0060.py` e o serializador canônico do §3.3, incluindo as duas lacunas;
3. **comparador** de artefatos por hash;
4. **ferramenta de medição** de tamanho da IR e de pico de memória, usada só no 0060D (§3.11);
5. fixture de estresse estrutural do 0060B.

Tudo sem tocar em `tools/benchmark_0059.py`. Nada em `src/`.

**Contratos emendados.** Nenhum.

**Contratos e congelamentos reafirmados.** 0009, 0011, 0015, 0022, 0024, 0026, 0028, 0030, 0032, 0034, 0036, 0038 e 0047, normativos; 0010, 0012, 0018, 0023, 0025, 0027, 0029, 0031, 0033, 0035, 0037, 0039 e 0048, congelamentos.

**Invariantes de segurança.** Oráculo e serializador do oráculo são artefatos de teste e nunca viram runtime. O comparador não copia documento, não grava caminho absoluto e não registra texto. O benchmark permanece intacto.

**Testes.** Comparador: artefatos iguais dão igual; um byte diferente dá diferente; nenhum conteúdo de documento na saída. Oráculo: cobertura de campos, que falha se um campo novo de modelo congelado ficar de fora; e o teste cross-process do envelope sob `PYTHONHASHSEED` variado (§3.3). Tudo com fixtures sintéticas, na trilha do CI.

**Aprovação.** Auditoria adversarial do contrato; escolhas da §8 registradas.

**Fallback.** Não se aplica; nada em produção muda.

---

### 0060B — parser

**Objetivo.** Remover o custo quadrático do caminho estrutural, sem alterar a IR.

**Pré-requisito para iniciar.** O **0060A precisa estar integrado**, com o oráculo e o comparador funcionando e o mecanismo de fixação do §3.2 definido. Esta fase **depende funcionalmente do oráculo**: a prova de IR idêntica, no CI e nos seis DOCX reais, é feita contra a referência fixada pelo SHA completo. Sem isso, a fase não pode ser aprovada.

**Escopo.** `docx_parser.py`: índice de posição entre irmãos por tipo de nó e índice de `original_index`, construídos **uma vez por chamada de `parse_bytes`** e descartados no retorno. Sem mudança de campos, de ordem, de avisos ou de semântica de caminho. `parser_api.resolve_structural_path` fica fora.

**Chave do índice.** **Proibido usar `id()` de proxy do lxml como chave isolada**, porque o identificador pode ser reaproveitado depois que o proxy é coletado. A implementação deve: usar como chave o próprio objeto elemento, num dicionário que mantém a referência viva; manter referência à árvore durante toda a indexação e todo o uso do índice; construir o índice de um pai sob demanda; e nunca guardar o índice além do `parse_bytes` que o criou.

**Contratos emendados.** **0009 e 0011**, normativos do parser, por nota de erratum de implementação registrando a mudança de custo e a obrigação de IR idêntica. `PARSER_VERSION` **não** muda, porque a saída não muda.

**Congelamentos reafirmados.** 0010 e 0012, válidos justamente porque a IR não muda.

**Invariantes de segurança.** IR idêntica, campo a campo e na serialização canônica; índice local à chamada, nunca global nem em `ContextVar`; limites de ZIP, profundidade e avisos inalterados; `status = partial` preservado; planos físico e estrutural (§3.7) idênticos, inclusive `original_index`.

**Testes na trilha do CI.**
- IR idêntica ao oráculo em todas as fixtures existentes;
- fixture de estresse: irmãos de mesmo nome intercalados com outros elementos; comentários e instruções de processamento como irmãos; `mc:AlternateContent`; `w:sdt`; hyperlinks; campos; tabelas aninhadas; profundidade próxima do limite; stories secundárias;
- dois parses sucessivos no mesmo processo e parses concorrentes em threads;
- documento com story parcial;
- suíte completa atual.

**Verificação na trilha do Ubuntu.** IR byte-idêntica nos seis DOCX reais, comparando o hash da serialização canônica da IR entre referência e otimizado, sob autorização explícita, registrando apenas os hashes no PR.

**Aprovação.** IR idêntica em 100% dos casos, sintéticos e reais; CI verde; sem regressão (§3.10) e com ganho mensurável nos dois mais pesados; auditoria adversarial.

**Fallback.** `git revert` isolado; nenhuma outra camada depende desta fase.

---

### 0060C — serialização de decisões

**Objetivo.** Eliminar reserializações idênticas dentro de **uma mesma avaliação**, sem mudar nenhum valor.

**Mecanismo.** Um `EvaluationContext` explícito, criado em `_evaluate`:

```text
EvaluationContext:
    package_sha256: str
    decision_blobs: dict[identidade da Decision -> bytes]
    decision_refs:  dict[identidade da Decision -> str]
```

Regras:

1. escopo estritamente por avaliação; nasce e morre dentro de `_evaluate`;
2. chave por **identidade do objeto**, com a referência mantida viva pelo contexto, jamais por `__eq__`/`__hash__`;
3. **proibido** cache global, de módulo, de classe ou em `ContextVar`;
4. nenhuma verificação de integridade pode ser pulada: o SafetyGate continua recomputando `source_decisions_hash` e comparando com `plan.source_decisions_hash`, e continua detectando Decisions duplicadas; evita-se apenas reserializar o mesmo objeto;
5. refs continuam derivados, nunca armazenados em modelo congelado.

**Fronteiras públicas — regra de decisão explícita.**

- **Preferência obrigatória:** implementar por **API interna**, com funções privadas que recebem o contexto, preservando byte a byte as assinaturas públicas de `build_operation_plan`, `evaluate_operation_plan`, `source_decisions_hash`, `decision_ref` e `process_document`. Nesse caminho, **nenhum contrato é emendado**.
- **Se a preferência não for viável**, e alguma assinatura pública precisar de parâmetro novo, ainda que opcional e aditivo, então a **emenda aditiva a 0024 (OperationPlan) e a 0026 (SafetyGate) é obrigatória**, e a 0032 também, caso a fronteira da sessão mude. A emenda precisa dizer que o parâmetro é opcional, que o comportamento padrão é idêntico ao atual e que nenhum artefato muda.
- Em qualquer dos dois caminhos, **0025 e 0027 permanecem reafirmados como congelamentos**, e a fase não pode começar a codificar antes de a escolha estar registrada e auditada.
- `PatchResult` e os demais modelos congelados permanecem intactos (§3.4).

**Invariantes de segurança.** Nenhum valor muda; nenhuma verificação some; determinismo preservado.

**Testes na trilha do CI.**
- Decisions com `Decimal("1.5")` e `Decimal("1.50")` coexistindo produzem refs distintos e corretos;
- `bool` e `int` em valores observados;
- Decisions iguais vindas de snapshots diferentes não compartilham entrada de cache;
- duplicata de Decision continua sendo erro de integridade no gate;
- `source_decisions_hash` adulterado continua sendo erro;
- o contexto não sobrevive à avaliação, verificado por instrumentação de cache;
- concorrência e sequência de sessões (§3.6, regra 9);
- determinismo com `PYTHONHASHSEED` variado, inclusive cross-process;
- diferenciais de sessão contra o oráculo.

**Aprovação.** Diferenciais idênticos; CI verde; sem regressão; escolha de fronteira registrada; auditoria adversarial.

**Fallback.** `git revert` isolado, independente do 0060B.

---

### 0060D — snapshot verificado compartilhado

**Objetivo.** Fazer um parse por snapshot em vez de dois. Hoje a pós-condição faz o parse dos bytes de saída e a iteração seguinte repete o mesmo parse.

**Escopo.** Um contexto de sessão guarda, apenas para o **snapshot corrente**, o par (PhysicalIR, StyleCatalog) produzido na pós-condição, ligado por `sha256` dos bytes e por `parser_version`, consumido pela avaliação seguinte.

**Limite explícito do escopo.** O 0060D **compartilha apenas o parse verificado do mesmo snapshot**. Ele **não** reutiliza decisões, classificações, findings, planos ou resultados de gate, nem dentro do mesmo snapshot nem entre snapshots. Em particular, **não há reuso semântico após rejeição do Patcher**: quando uma operação é rejeitada, a avaliação seguinte é recomputada normalmente, como hoje, e a única coisa que persiste é o estado `rejected_on_snapshot`, que já existe e governa a seleção do próximo token. Qualquer reuso além do parse é assunto do 0061 (§3.7).

Por operar sobre um único snapshot, esta fase **não depende do predicado de não interferência**: é a mesma função, sobre os mesmos bytes, executada uma vez em vez de duas.

**`PatchResult` permanece intacto.** A entrega do par verificado ocorre por **API interna** — por exemplo, uma função interna do Patcher que devolve o resultado da pós-condição ao chamador da sessão — ou por retorno aditivo separado, nunca por campo novo em `PatchResult` nem em qualquer outro modelo congelado.

**Contratos emendados.**
- **0028**, normativo do Patcher: o resultado do parse já feito na pós-condição pode ser entregue ao chamador. A pós-condição não muda: continua relendo os bytes do ZIP produzido, com o Parser real, conforme 0028 §19.
- **0032**, normativo do Processing Session: "o pipeline completo roda novamente" passa a significar que a avaliação é recomputada por inteiro sobre o novo snapshot, admitindo que o parse desse snapshot seja obtido uma única vez, com ligação obrigatória por SHA.

**Congelamentos reafirmados.** 0029 e 0033, que passam a valer com a semântica emendada em 0028 e 0032 somente com a implementação integrada.

**Invariantes de segurança.**
- pós-condição sobre bytes relidos do ZIP produzido, nunca sobre a árvore em memória;
- nada é guardado se a pós-condição falhar; a falha continua fail-fast antes de APPLIED;
- consumo só depois de conferir o SHA; divergência é erro de integridade;
- retém-se apenas o snapshot corrente;
- a IR compartilhada não pode ser mutada por nenhum consumidor;
- cache de sessão descartado em `finally`;
- `PatchResult` intacto.

**Pré-requisito para iniciar.** 0060C integrado. **O limite definitivo de memória não é requisito de início**: ele só pode ser calculado depois que esta fase existir. Durante o desenvolvimento vale a trava provisória do §3.11.

**Pré-requisito para integrar.** O **delta de pico de memória precisa estar medido** na trilha do Ubuntu, nos seis documentos reais, e o **limite definitivo precisa estar fixado por emenda a esta decisão**, na forma `1,15 × (pico de 0059 + delta medido)`, antes do merge do PR desta fase.

**Testes na trilha do CI.**
- consumidor instrumentado que muta a IR é detectado por hash canônico antes e depois da avaliação;
- SHA divergente entre IR guardada e bytes correntes gera `ProcessingSessionIntegrityError`;
- falha de pós-condição não deixa IR guardada e preserva a exceção;
- rejeição comum, progresso independente e nova tentativa depois da mudança de snapshot (0032 §9), provando que nada além do parse é reaproveitado;
- limite de operações no ponto exato de corte;
- detecção de ciclo de SHA;
- concorrência e sequência de sessões;
- identidade entre IR e catálogo da pós-condição e os de uma nova avaliação dos mesmos bytes, em fixtures sintéticas;
- diferenciais contra o oráculo: bold e font no mesmo run; P3 e P4 no mesmo parágrafo; operação de run e de parágrafo no mesmo parágrafo; run em hyperlink; `w:rPrChange`; `w:del` e `w:ins`; campos.

**Verificação na trilha do Ubuntu.** Identidade entre pós-condição e nova avaliação nos seis DOCX reais; delta real de pico de memória entre manter e não manter a IR; ganho nos dois documentos mais pesados.

**Aprovação.** Diferenciais idênticos; identidade verde nos sintéticos e nos seis reais; CI verde; memória dentro do limite definitivo; auditoria adversarial.

**Fallback.** `git revert` do PR, que também reverte as emendas a 0028 e 0032.

---

### 0060E — medição oficial no Ubuntu

**Objetivo.** Medir o ciclo inteiro com o protocolo do 0059 e classificar o resultado pela tabela do §3.9.

**Escopo.** Execução do §3.8; equivalência por hash dos cinco arquivos entregues nos seis documentos; relatório `docs/benchmarks/0060-measurement-report.md`; atualização de `docs/handoff.md`. Nenhuma alteração de código, e nenhuma alteração no benchmark.

**Contratos emendados.** Nenhum. **Congelamentos reafirmados:** todos.

**Invariantes de segurança.** Os DOCX reais continuam fora do repositório, identificados só por nome, tamanho e SHA-256; nenhum caminho absoluto gravado; integridade verificada por `input_unchanged_on_disk`.

**Aprovação.** §3.9, §3.10, §3.11 e §4, avaliados em conjunto.

**Fallback.** Havendo regressão ou divergência de equivalência, as fases de código são revertidas na ordem inversa, voltando a `4bcda30`, que é linha de base já medida.

---

### 0061 — condicional, fora do 0060

**Critério de abertura**, conforme a tabela do §3.9:

- **(a)** ambos os documentos com redução de pelo menos 40%: meta atingida, **sem abertura automática**;
- **(b)** ambos com pelo menos 25%, e algum abaixo de 40%: resultado parcial, com **decisão obrigatória registrada** sobre abrir ou não o 0061, tomada por Felipe depois do 0060E;
- **(c)** qualquer documento abaixo de 25%: **0061 obrigatório**.

Em nenhum caso o 0061 começa a ser implementado sem contrato próprio e auditoria própria.

**Conteúdo previsto:**

1. avaliação incremental, reusando **valor semântico** de alvos não tocados, sob as cinco igualdades e o fallback integral do §3.7;
2. SafetyGate incremental, avaliando até o primeiro token liberado, com avaliação integral no snapshot terminal;
3. implementação e validação do predicado do §3.7, com modo sombra no CI e matriz de dependência por `(target_type, property_slot)`.

**Contratos a avaliar no desenho do 0061**, porque o reuso passaria a atravessar snapshots: **0015** (Analysis View v0.1b, resolução de formatação) e **0022** (Classification Layer v0.1), ambos normativos, além de **0026** e **0032**. Os congelamentos **0018** e **0023** são reafirmados e só podem ser tocados por emenda explícita. Se a avaliação concluir que o reuso exige mudar a semântica dessas camadas, o 0061 para e abre contrato próprio para elas.

---

## 6. Fora do escopo, explicitamente

1. agrupamento de operações compatíveis numa mesma passagem;
2. atomicidade multi-alvo, com transação e rollback;
3. `allowed-delta` de múltiplos alvos;
4. qualquer mudança na semântica de `TransformRecord`, na ordem de aplicação ou nos identificadores do relatório;
5. avaliação incremental, SafetyGate incremental e qualquer reuso semântico entre snapshots, que são o 0061;
6. qualquer alteração em `tools/benchmark_0059.py`;
7. qualquer nova propriedade do slice automático.

Os itens 1, 2 e 3 exigem, antes de discussão técnica, **decisão de produto** sobre mudar o que o usuário recebe no relatório.

---

## 7. Riscos reconhecidos

- **Ganho menor que o das sondas:** fixtures sintéticas são largas e rasas; documentos reais têm tabelas, SDT e campos. Só o 0060E decide.
- **Cache e concorrência:** risco mais provável de defeito silencioso; tratado por §3.6 e pelos testes de concorrência e sequência.
- **Mutação da IR compartilhada:** hoje nenhum consumidor muta a IR, mas nada impede; teste no 0060D.
- **Identidade de proxies do lxml:** tratada pela regra de chave do 0060B.
- **Plano estrutural:** `original_index` muda quando se cria `w:rPr` ou `w:pPr`; qualquer otimização que assuma estabilidade posicional está errada.
- **Duas trilhas de verificação:** o CI não vê documento real, então a trilha do Ubuntu é a única que prova equivalência no corpus. Ela depende de execução manual e de registro fiel no PR.
- **Plataforma:** as sondas rodaram no macOS; a equivalência precisa ser verificada no Ubuntu.
- **Memória:** o 0060D retém uma IR a mais; o limite definitivo sai antes da fase, com o delta medido.

---

## 8. Escolhas registradas

Decididas por Felipe em 2026-09-16, após o parecer final do DeepSeek:

1. **Meta de redução:** 40% nos dois documentos mais pesados. **Aceita.**
2. **Piso de continuidade:** 25%. **Aceito.**
3. **Regressão:** até 3% pela mediana, máximo 5% acima da linha de base e dispersão relativa de até 3%. **Aceita.**
4. **Medição da IR:** fica no **0060A**, como instrumento separado, sem alterar `tools/benchmark_0059.py`.
5. **Oráculo:** `tools/oracle_0060.py`, com testes em `tests/test_oracle_0060.py`.
6. **Memória:** limite definitivo `1,15 × (pico de 0059 + delta medido da IR)`, fixado por emenda **antes da integração** do PR do 0060D, e não antes do seu início; até a medição vale a trava provisória do dobro do pico.
7. **0061:** nunca abre automaticamente como implementação. Na faixa parcial, decisão obrigatória registrada após o 0060E; abaixo de 25% em qualquer documento, torna-se obrigatório.
8. **Reuso após rejeição:** **removido** do 0060D. Só o parse verificado do mesmo snapshot é compartilhado.

Não há, nesta revisão, ponto pendente de escolha. Qualquer mudança nesses itens exige emenda a esta decisão.

---

## 9. Proveniência

- Medição: `docs/benchmarks/0059-measurement-report.md`, com `sintetico-full.json` `23bddc80fba62ff9cbcd9c6ef812bf3945d2ae721f44a3e01db65efbc7d87226` e `reais-full.json` `659f9360f7b6d4881b5b5c0ee27f07a94eb2a40d45931efc06101c57611a6331`, ambos fora do repositório.
- Auditoria arquitetural do Claude Opus sobre `4bcda30`: o parecer foi entregue a Felipe como arquivo fora do repositório e **não está versionado aqui**. Os números do §1 (parser quadrático, serialização repetida, não interferência) vêm desse parecer, produzido com sondas em fixtures sintéticas, no macOS com Python 3.12.13. Nenhum DOCX real foi lido nessas sondas. Se o parecer for incorporado ao repositório em algum momento, esta seção passa a citá-lo por caminho.
- Pareceres do DeepSeek Flash 4.1 sobre as revisões 1, 2 e 3 desta decisão, incorporados nas revisões 2, 3 e 4.
- Percentuais de etapa do §1: variante instrumentada da medição oficial, no Ubuntu.
- Tamanho da IR do §3.11: medido em fixtures sintéticas, 1,8 MiB para um DOCX de 67 KiB e 3,7 MiB para um de 132 KiB.
