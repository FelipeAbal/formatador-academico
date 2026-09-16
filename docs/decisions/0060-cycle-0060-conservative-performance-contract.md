# Decisão 0060A: contrato do ciclo 0060 — otimização conservadora com equivalência exata

**Status:** PROPOSTA, pendente de auditoria adversarial e de autorização
**Data:** 2026-09-16
**Base:** `main` após o merge do PR #60, commit `4bcda308a4975f2bb84d87ab4738faaed463bb75`
**Depende de:** `docs/benchmarks/0059-measurement-report.md`; auditoria arquitetural do Claude Opus sobre o mesmo commit
**Não altera:** nenhum código de produção. Esta decisão é contrato e critério, não implementação.

---

## 1. Contexto

A medição oficial do ciclo 0059 rodou no Ubuntu, com Python 3.12.3, `lxml` 6.1.3, no commit `84879124…`, sobre seis DOCX reais, com seis execuções por documento em ordem ABBA. Resultados registrados:

- a pós-condição ocupa de 83,0% a 90,0% do tempo de patch, e de 17,6% a 28,0% do tempo total;
- o ciclo completo repetido a cada alteração ocupa de 92,9% a 96,3% do tempo total;
- os dois parses por alteração ocupam de 32,9% a 54,5% do total;
- referência e instrumentação não divergiram em nenhuma execução;
- `input_unchanged_on_disk = true` em todas as 36 execuções: **nenhum arquivo original foi alterado**;
- os dois documentos mais pesados têm medianas de 458,3 s (artigo Hellen-2) e 502,7 s (Dissertação final).

A auditoria arquitetural acrescentou três fatos, verificados por sondas fora do repositório e por leitura do código:

1. **O parser é quadrático no número de irmãos.** `_structural_path` reconstrói a lista de irmãos de cada ancestral para cada registro. Em fixtures sintéticas isso responde por 87% do parse com 800 parágrafos. Memoizar a posição dentro de uma única chamada produziu IR idêntico byte a byte, e a sessão completa ficou 2,0× mais rápida com 400 parágrafos e 3,6× com 800, com DOCX, `transforms` e relatório idênticos.
2. **Cada Decision é serializada cerca de 11 vezes por iteração**, em planner, SafetyGate e mapas da sessão.
3. **Um patch não altera semanticamente nenhum outro alvo.** Só muda o `physical_hash` do próprio alvo e dos alvos ancestrais. `observed` e `actionability` não mudam fora do alvo, e nenhuma Decision surge ou desaparece.

Esses números vieram de fixtures sintéticas no macOS e **não são previsão para os documentos reais**. Servem para ordenar o trabalho, não para prometer ganho.

---

## 2. Decisão

1. **O agrupamento de operações em lote fica rejeitado neste ciclo.** O mesmo vale para qualquer forma de atomicidade multi-alvo.
2. O ciclo 0060 aplica **apenas otimizações compatíveis com a cadeia atual de um patch por vez**, capazes de provar equivalência exata com a implementação atual.
3. O ciclo tem cinco fases, cada uma em PR próprio, com auditoria adversarial independente: **0060A** (esta decisão), **0060B** (parser), **0060C** (serialização de decisões), **0060D** (compartilhamento do snapshot já relido e verificado) e **0060E** (medição oficial).
4. **Nenhuma nova propriedade do slice automático entra antes do fim do 0060E.**
5. Qualquer fase que não consiga provar equivalência exata é revertida, não negociada.

Motivo da rejeição do agrupamento, em uma frase: `operation_plan_ref`, os SHAs intermediários do pacote e a ordem real de aplicação entram em cada `TransformRecord` e chegam ao relatório humano, de modo que juntar iterações muda artefatos entregues ao usuário e exige emendas em pelo menos seis contratos congelados, além de um validador de delta múltiplo que é código novo e crítico para a segurança.

---

## 3. Definições obrigatórias do ciclo

### 3.1 O que significa equivalência exata

Para toda tripla de entrada

```text
(package_snapshot: bytes, profile: ProcessingProfile, max_applied_operations: int)
```

a execução otimizada deve produzir artefatos **idênticos** aos da implementação de referência, congelada em `4bcda30`, no mesmo ambiente suportado.

Idêntico significa igualdade de bytes nos artefatos serializados e igualdade estrutural campo a campo nos objetos congelados. Não vale "equivalente", "semanticamente igual" nem "visualmente igual".

A equivalência é exigida também nos caminhos de falha: mesma exceção, mesmo tipo e mesma condição de disparo. Uma otimização que troque um `ProcessingSessionIntegrityError` por sucesso, ou o contrário, falha o critério.

A referência é a implementação de `4bcda30`, disponível como oráculo de teste em worktree fixa de CI ou cópia sob `tools/`, **nunca** como caminho alternativo em runtime.

### 3.2 Campos e artefatos que precisam permanecer idênticos

**`ProcessingSessionResult`:**
- `status`;
- `input_package_sha256` e `output_package_sha256`;
- `output_package_bytes`;
- `transforms`, na mesma ordem, com todos os campos de cada `TransformRecord`: `operation_ref`, `operation_plan_ref`, `decision_ref`, `profile_ref`, `rule_ref`, `target` (inclusive o `physical_hash` pré-transformação), `precondition_observed`, `desired_value`, `input_package_sha256`, `output_package_sha256`, `changed_part`;
- `final_classifications`, `final_decisions` e `findings`, na mesma ordem.

**Derivados:**
- `serialize_transform_record` de cada record e o `transform_ref` correspondente;
- `serialize_processing_report` do `ProcessingReport`;
- relatório humano, byte a byte;
- Review DOCX, byte a byte;
- os cinco arquivos do Product Delivery, byte a byte, com os mesmos nomes.

**Intermediários exigidos, porque entram nos artefatos acima:**
- o número de iterações lógicas e a ordem real de aplicação;
- o SHA de cada snapshot intermediário;
- o `operation_plan_ref` de cada iteração.

### 3.3 Como preservar TransformLog, ProcessingReport, Review DOCX, Product Delivery e allowed-delta

Regra estrutural do ciclo:

> **Nenhuma fase pode alterar quantas iterações lógicas existem, qual operação é aplicada em cada uma, nem sobre quais bytes.** As fases só podem eliminar recomputação de resultados idênticos.

Consequências por camada:

- **TransformLog (0030/0031):** continua com um record por patch aplicado, com a cadeia `saída N == entrada N+1`. Nenhuma fase pode produzir envelope de lote nem record sem SHA intermediário.
- **ProcessingReport (0034/0035):** um `AppliedChangeItem` por record, na ordem real. Como todos os campos de origem são preservados, o relatório serializado é idêntico por construção.
- **Review DOCX (0036/0037):** trabalha sobre o snapshot final e sobre os itens do relatório. Preservados os dois, o resultado é idêntico. A marcação e a política do primeiro run marcável não são tocadas.
- **Product Delivery (0038/0039, 0047/0048):** os cinco arquivos derivam do bundle; a igualdade é verificada por hash de cada arquivo.
- **allowed-delta (0028 §20):** permanece unitário, provando **um** delta autorizado por patch. Nenhuma fase deste ciclo pode generalizá-lo para vários alvos. A pós-condição continua rodando sobre bytes relidos do ZIP produzido, nunca sobre a árvore em memória.

### 3.4 Como impedir cache compartilhado entre sessões

A interface web usa `ThreadingHTTPServer`, com sessões simultâneas no mesmo processo. Portanto:

1. **Proibido qualquer cache em nível de módulo, classe, variável global ou atributo de instância compartilhada.**
2. Todo cache tem um destes dois escopos, declarado no código:
   - **escopo de chamada**: criado no início de uma função pública e descartado ao retornar (caso do 0060B);
   - **escopo de sessão**: criado em `process_document` e descartado ao terminar, inclusive por exceção, via `try/finally` (casos do 0060C e 0060D).
3. Nenhum cache pode sobreviver entre duas chamadas públicas.
4. Nenhum cache pode ser chaveado por algo que não identifique o snapshot, como caminho estrutural isolado ou índice de parágrafo.
5. Teste obrigatório de concorrência: N sessões simultâneas em threads, com documentos e perfis diferentes, exigindo os mesmos artefatos que a execução sequencial.
6. Teste obrigatório de sequência: duas sessões seguidas no mesmo processo, na ordem A, B, A, exigindo resultado idêntico à execução isolada de cada uma.

### 3.5 Como provar que um patch em um run não muda semanticamente os demais alvos

A prova tem três camadas, e as três são obrigatórias.

**a) Matriz de dependência declarada.** O ciclo registra, por camada, o conjunto de leitura:

| Camada | Lê | Afetada por bold/font_size (run)? | Afetada por alignment/spacing.line (parágrafo)? |
| --- | --- | :---: | :---: |
| Classificação de parágrafo | tipo de story, texto normalizado, contêiner, `pStyle` resolvido, catálogo | não | não |
| Projeção de run | classe do parágrafo e `physical_hash` do próprio run | só o hash do run alvo | não |
| Formatação de run | bag do run, `pStyle` do parágrafo, catálogo, `docDefaults` | só o run alvo | não |
| Formatação de parágrafo | bag do parágrafo, catálogo, `docDefaults` | não | só o parágrafo alvo |
| StyleCatalog | `word/styles.xml` | não, o Patcher nunca altera `styles.xml` | não |
| Hashes físicos | XML canônico do registro | alvo e todos os ancestrais | alvo e todos os ancestrais |

**b) Teste diferencial com oráculo.** Fixtures com vários runs por parágrafo e regras de parágrafo e de run ativas ao mesmo tempo. Depois de cada patch, comparar a avaliação completa com a da referência e exigir que fora do alvo mudem **apenas** os `physical_hash` de ancestrais.

**c) Modo sombra.** Enquanto qualquer fase reusar resultado entre snapshots, o CI roda um modo que recalcula tudo e compara a cada iteração, falhando na primeira divergência. O modo sombra é de teste; não vai para produção.

**Cláusula de validade:** esta prova vale para o slice congelado atual. **Qualquer propriedade nova precisa declarar seu conjunto de leitura e refazer a prova antes de entrar.** Uma propriedade que altere `pStyle`, numeração, texto ou `styles.xml` invalida a matriz.

### 3.6 O hash físico do parágrafo muda quando só um run muda

Isso é comportamento correto e esperado: o XML canônico do parágrafo contém os runs.

Regras do ciclo:

1. **Hashes físicos nunca são reaproveitados entre snapshots.** São sempre recalculados a partir do XML corrente, para o alvo e para todos os ancestrais.
2. Como o hash do parágrafo muda, mudam `decision_ref`, `operation_ref` e `operation_plan_ref` das Decisions de parágrafo daquele parágrafo. Todos precisam ser recalculados, e é por isso que a preservação do `operation_plan_ref` é item de aceitação (§3.2).
3. Nenhum cache pode ser chaveado só por `structural_path`. A chave precisa incluir o `physical_hash` corrente ou o SHA do pacote.
4. O SafetyGate e o Patcher mantêm a comparação de hash físico como está. Este ciclo não afrouxa nenhuma dessas verificações.
5. Consequência para o futuro: duas operações no mesmo parágrafo, ou uma de run e uma do parágrafo que a contém, **não** são compatíveis para lote. Isso é parte do motivo de o agrupamento ficar fora.

### 3.7 Como registrar e invalidar caches

Todo cache introduzido no ciclo precisa de um registro no código e na decisão da fase, com sete campos:

```text
nome
o que guarda
chave exata
escopo (chamada | sessão)
evento de invalidação
custo de memória esperado
teste que prova a invalidação
```

Regras de invalidação:

1. **Mudou o snapshot, caiu o cache.** Qualquer cache ligado a bytes é descartado, ou trocado, quando o SHA do pacote muda.
2. **Ligação obrigatória por SHA.** Um artefato guardado só pode ser consumido depois de conferir que o SHA do pacote que o gerou é igual ao do pacote corrente. Divergência é `ProcessingSessionIntegrityError`, nunca uso degradado.
3. **Proibido chavear por igualdade semântica.** `Decimal("1.5") == Decimal("1.50")` e `True == 1`, mas a serialização difere. Caches de serialização devem usar identidade do objeto, com a referência mantida viva, jamais `__eq__`/`__hash__`.
4. **Retenção mínima.** Guarda-se apenas o snapshot corrente. Nada de histórico de snapshots.
5. **Sem estado entre chamadas públicas** (§3.4).
6. **Observabilidade em teste.** Em modo de teste, cada cache expõe acertos, erros e invalidações, para que os testes provem que a invalidação ocorreu, e não apenas que o resultado bateu.

### 3.8 Como medir o ganho no Ubuntu

Mesma máquina, mesmo Python 3.12.3, máquina ociosa, mesma ferramenta `tools/benchmark_0059.py`, sem alteração da ferramenta durante o ciclo. Se a ferramenta precisar mudar, a mudança é um PR próprio, anterior à medição, e a comparação passa a exigir remedição da linha de base.

Protocolo por medição:

1. linha de base sintética completa, `--repeats 3`, `--timeout 1800`;
2. os seis documentos reais, `--repeats 3`, `--timeout 3600`, perfil embutido `builtin-academic-0059`, com os arquivos fora do repositório e `--record-docx-path` **não** usado;
3. saída gravada fora do repositório; só hashes, nomes, tamanhos e SHA-256 entram em documento;
4. comparação contra a linha de base do ciclo 0059: `sintetico-full.json` `23bddc80…` e `reais-full.json` `659f9360…`;
5. verificação de que `input_unchanged_on_disk` é verdadeiro em todas as execuções;
6. verificação de equivalência por hash dos cinco arquivos entregues, referência × otimizado, para cada documento, gravando **apenas os hashes**.

Comparações usam a mediana da variante `reference`, que é o total oficial. A variação observada em 0059 foi pequena: entre o mínimo e o máximo de cada documento, no máximo 1,2% da mediana. Esse é o ruído de fundo aceito.

Cada fase de código (0060B, 0060C e 0060D) roda um recorte sintético e os dois documentos mais pesados, para decidir continuar. A medição completa dos seis documentos é o 0060E.

### 3.9 Critério relativo para Hellen-2 e para a Dissertação

Os dois documentos mais pesados são a referência de sucesso do ciclo, porque concentram os dois padrões de custo: muitas alterações (288 em Hellen-2) e pacote grande com muitos parágrafos (3,2 MB e 514 parágrafos na Dissertação).

```text
reducao = 1 - (mediana_0060E / mediana_0059)

mediana_0059:
    artigo Hellen-2       458,3 s
    Dissertação final     502,7 s
```

- **Meta do ciclo:** `reducao >= 0,40` nos dois documentos, medida depois do 0060D, no conjunto das fases, não em cada uma.
- **Piso de continuidade:** `reducao >= 0,25` nos dois. Entre 0,25 e 0,40, o ciclo é integrado assim mesmo, com registro explícito de meta não atingida, e o ciclo 0061 é aberto para avaliação incremental e SafetyGate preguiçoso.
- **Abaixo de 0,25 nos dois documentos:** as fases de código continuam integráveis se a equivalência estiver provada e não houver regressão, mas o ciclo é registrado como insuficiente e o 0061 passa a ser obrigatório.
- A meta é relativa à própria linha de base de cada documento. Não existe meta absoluta em segundos nesta etapa, porque ela dependeria de hardware.

---

## 4. Avaliação do critério preliminar proposto

| Critério proposto | Parecer | Forma adotada |
| --- | --- | --- |
| Nenhum documento real pode piorar mais de 10% | **frouxo demais.** A variação medida em 0059 ficou em no máximo 1,2% da mediana, então 10% aceitaria uma regressão real e reprodutível | **Nenhum documento pode piorar mais de 3%.** Entre 0 e 3% exige justificativa escrita na fase; acima de 3% bloqueia o merge |
| Redução mediana mínima de 40% nos dois mais pesados | **ambicioso, porém plausível.** Os dois parses ocupam 44,3% e 54,5% do total nesses documentos; 0060B ataca o custo do parse e 0060D elimina um dos dois | Mantido como **meta do ciclo**, com piso de 25% (§3.9), medido no 0060E |
| Equivalência sem divergências | **obrigatório e inegociável** | Mantido, estendido aos caminhos de falha e aos cinco arquivos entregues (§3.1 e §3.2) |
| Todos os testes atuais devem continuar passando | **necessário, insuficiente** | Mantido, somado aos testes novos de cada fase e aos diferenciais contra o oráculo |
| Três execuções ABBA com a mesma ferramenta 0059 | **correto** | Mantido: `--repeats 3`, seis execuções por documento, mesma ferramenta, mesmo ambiente, mais a linha de base sintética completa |

Acréscimos obrigatórios:

- os seis documentos precisam manter **as mesmas alterações automáticas e os mesmos itens de revisão** da medição 0059 (51/84, 53/9, 288/100, 99/23, 63/130 e 26/6);
- nenhuma execução pode terminar em timeout ou erro;
- `input_unchanged_on_disk` verdadeiro em todas as execuções;
- o pico de memória não pode subir mais de 20% em nenhum documento, porque o 0060D passa a reter um IR adicional.

---

## 5. Fases

### 0060A — decisão, critérios e oráculo de equivalência

**Objetivo.** Fixar a decisão, o significado de equivalência exata, o oráculo, as regras de cache e os critérios de aceitação, antes de qualquer otimização.

**Escopo.** Este documento; a preparação do oráculo de referência (worktree de `4bcda30` no CI ou cópia sob `tools/`); a ferramenta de comparação por hashes dos cinco arquivos entregues, que grava só hashes; a fixture de estresse estrutural descrita no 0060B. Nenhuma alteração em `src/`.

**Contratos afetados.** Nenhum. Esta decisão cria um contrato de ciclo, sem emendar contrato congelado.

**Contratos intactos.** Todos: 0003–0012, 0013–0023, 0024–0039, 0041, 0043–0048, 0049, 0051, 0052C e 0057.

**Invariantes de segurança.** O oráculo é artefato de teste e nunca vira caminho de runtime. A ferramenta de comparação não copia documento, não grava caminho absoluto e não registra texto.

**Testes.** A própria ferramenta de comparação precisa de teste: dois artefatos iguais dão igual, um byte diferente dá diferente, e nenhum conteúdo de documento aparece na saída.

**Aprovação.** Auditoria adversarial independente do contrato; concordância explícita de Felipe com os critérios do §3.9 e do §4.

**Fallback.** Não se aplica: nada em produção muda.

---

### 0060B — correção e otimização do parser

**Objetivo.** Remover o custo quadrático do caminho estrutural, sem alterar em nada o PhysicalIR.

**Escopo.** `docx_parser.py`: índice de posição entre irmãos por tipo de nó e índice de `original_index`, construídos **uma vez por chamada de `parse_bytes`** e descartados no retorno. Sem mudança de campos, de ordem, de avisos ou de semântica de caminho. `parser_api.resolve_structural_path` fica fora desta fase.

**Contratos afetados.** 0010 e 0012, apenas por **nota de erratum de implementação**, registrando a mudança de custo e a obrigação de IR idêntico. `PARSER_VERSION` **não** muda, porque a saída não muda; a nota é necessária porque 0012 exige decisão explícita para alterações no parser congelado.

**Contratos intactos.** Todos os demais, incluindo 0026, 0028, 0030, 0032 e 0034.

**Invariantes de segurança.**
- IR idêntico, campo a campo e byte a byte na serialização canônica;
- índice local à chamada, nunca global (§3.4);
- a chave precisa manter viva a referência ao nó, porque a identidade de elementos do lxml só é estável enquanto há referência;
- nenhuma mudança nas regras de profundidade, limites de ZIP ou avisos.

**Testes.**
- IR idêntico ao oráculo em todas as fixtures existentes;
- fixture de estresse: irmãos de mesmo nome intercalados com outros elementos, comentários e instruções de processamento como irmãos, `mc:AlternateContent`, `w:sdt`, hyperlinks, campos, tabelas aninhadas, profundidade próxima do limite, stories secundárias;
- dois parses sucessivos no mesmo processo e parses concorrentes em threads;
- documento com story parcial, mantendo `status = partial`;
- suíte completa atual.

**Aprovação.** IR idêntico em 100% dos casos; CI verde; recorte sintético e os dois documentos mais pesados sem regressão e com ganho mensurável; auditoria adversarial.

**Fallback.** Reversão do PR. Como nenhuma outra camada muda, voltar ao caminho atual é um `git revert` isolado.

---

### 0060C — redução de serializações repetidas de decisões

**Objetivo.** Eliminar recomputações idênticas de `serialize_decision`, `decision_ref` e `source_decisions_hash` dentro de uma mesma avaliação, sem mudar nenhum valor.

**Escopo.** Memo por avaliação, **chaveado por identidade do objeto Decision**, consumido por planner, SafetyGate e mapas da sessão. As verificações continuam existindo: o SafetyGate segue recomputando o `source_decisions_hash` e comparando com `plan.source_decisions_hash`, e segue detectando Decisions duplicadas; o que muda é só a reserialização do mesmo objeto.

**Contratos afetados.** Nenhum. As funções públicas, os valores e as verificações permanecem.

**Contratos intactos.** Todos, em especial 0024/0025 (ordem canônica do plano) e 0026/0027 (integridade de proveniência no gate).

**Invariantes de segurança.**
- **proibido** chavear por igualdade: `Decimal("1.5")` e `Decimal("1.50")` são iguais, mas produzem bytes diferentes (§3.7, regra 3);
- o memo morre com a avaliação;
- nenhuma verificação de integridade pode ser pulada por estar "já conferida";
- refs continuam derivados, não armazenados nos modelos congelados.

**Testes.**
- Decisions com `Decimal("1.5")` e `Decimal("1.50")` coexistindo produzem refs distintos e corretos;
- `bool` e `int` em valores observados;
- Decisions iguais vindas de snapshots diferentes não compartilham entrada;
- duplicata de Decision continua sendo erro de integridade no gate;
- `source_decisions_hash` alterado artificialmente continua sendo erro;
- determinismo com `PYTHONHASHSEED` variado, inclusive em subprocesso;
- diferenciais de sessão contra o oráculo.

**Aprovação.** Diferenciais idênticos; CI verde; sem regressão nos dois documentos mais pesados; auditoria adversarial.

**Fallback.** Reversão do PR, independente do 0060B.

---

### 0060D — compartilhamento seguro do snapshot já relido e verificado

**Objetivo.** Fazer um parse por snapshot, em vez de dois. Hoje a pós-condição faz o parse dos bytes de saída, e a iteração seguinte faz o parse dos mesmos bytes.

**Escopo.** Um contexto de sessão guarda o par (PhysicalIR, StyleCatalog) do **snapshot corrente**, produzido pela pós-condição, ligado por `sha256` dos bytes e por `parser_version`, e consumido pela avaliação seguinte. Opcionalmente, reuso da avaliação depois de rejeição comum do Patcher, quando os bytes não mudaram.

**Contratos afetados.**
- **0029, emenda:** o Patcher pode entregar ao chamador o resultado do parse que ele já fez na pós-condição, sem mudar a pós-condição em si.
- **0033, emenda:** "o pipeline completo roda novamente" passa a significar que a avaliação é recomputada por inteiro sobre o novo snapshot, admitindo que o parse desse snapshot seja obtido uma única vez, com ligação obrigatória por SHA.

**Contratos intactos.** 0026/0027, 0030/0031, 0032 (nas partes de ordem, seleção, orçamento, ciclo e resultado), 0034/0035, 0036/0037, 0038/0039.

**Invariantes de segurança.**
- a pós-condição continua rodando sobre bytes **relidos do ZIP produzido**, nunca sobre a árvore em memória (0028 §19);
- nada é guardado se a pós-condição falhar; a falha continua sendo fail-fast antes de APPLIED;
- consumo só depois de conferir o SHA; divergência é erro de integridade;
- só o snapshot corrente é retido;
- o PhysicalIR compartilhado não pode ser mutado por nenhum consumidor;
- cache de sessão, descartado em `finally` (§3.4).

**Testes.**
- consumidor instrumentado que muta o IR é detectado por hash canônico do IR antes e depois da avaliação;
- SHA divergente entre IR guardado e bytes correntes gera `ProcessingSessionIntegrityError`;
- falha de pós-condição não deixa IR guardado e preserva a exceção;
- rejeição comum, progresso independente e nova tentativa depois da mudança de snapshot (0032 §9);
- limite de operações exatamente no ponto de corte;
- detecção de ciclo de SHA;
- concorrência e sequência de sessões (§3.4, itens 5 e 6);
- pico de memória dentro do limite do §4;
- diferenciais de sessão contra o oráculo, incluindo bold e font no mesmo run, P3 e P4 no mesmo parágrafo, operação de run e de parágrafo no mesmo parágrafo, run em hyperlink, `w:rPrChange`, `w:del`/`w:ins` e campos.

**Aprovação.** Diferenciais idênticos; CI verde; ganho medido nos dois documentos mais pesados; memória dentro do limite; auditoria adversarial.

**Fallback.** Reversão do PR. Como o 0060D é a única fase que emenda contrato, a reversão também reverte as emendas 0029 e 0033, que só passam a valer com a implementação integrada.

---

### 0060E — medição oficial novamente no Ubuntu

**Objetivo.** Medir o ciclo inteiro com o protocolo do 0059 e decidir se a meta foi atingida.

**Escopo.** Execução do §3.8; comparação de equivalência por hash dos cinco arquivos entregues em cada um dos seis documentos; relatório `docs/benchmarks/0060-measurement-report.md`; atualização do `docs/handoff.md`. Nenhuma alteração de código.

**Contratos afetados.** Nenhum.

**Contratos intactos.** Todos.

**Invariantes de segurança.** Os DOCX reais continuam fora do repositório, identificados só por nome, tamanho e SHA-256; nenhum caminho absoluto é gravado; a integridade dos originais é verificada por `input_unchanged_on_disk`.

**Testes.** Não se aplica; o que se exige é o protocolo de medição e os hashes de equivalência.

**Aprovação.** Critérios do §3.9 e do §4, avaliados em conjunto.

**Fallback.** Se a medição mostrar regressão em algum documento, ou qualquer divergência de equivalência, as fases de código são revertidas na ordem inversa, e o ciclo volta ao estado de `4bcda30`, que é uma linha de base já medida e registrada.

---

## 6. Fora do escopo, explicitamente

Ficam adiados para ciclo posterior, com contrato próprio e auditoria própria:

1. **agrupamento de operações compatíveis numa mesma passagem;**
2. **atomicidade multi-alvo, com transação e rollback;**
3. avaliação incremental, que reusa Analysis, Classification e Decision de alvos não tocados;
4. SafetyGate preguiçoso, que avalia até o primeiro token liberado;
5. `allowed-delta` de múltiplos alvos;
6. qualquer mudança na semântica de `TransformRecord`, na ordem de aplicação ou nos identificadores do relatório.

Os itens 3 e 4 são os candidatos naturais ao ciclo **0061**, e só serão abertos se o 0060E indicar necessidade. Os itens 1, 2 e 5 exigem, antes de qualquer discussão técnica, uma **decisão de produto** sobre mudar o que o usuário recebe no relatório, porque a ordem, os identificadores e os hashes intermediários deixariam de corresponder à execução atual.

Também fica fora deste ciclo qualquer nova propriedade do slice automático, conforme a decisão do ciclo 0059.

---

## 7. Riscos reconhecidos

- **Ganho menor que o das sondas.** As fixtures sintéticas são largas e rasas; documentos reais têm tabelas, SDT e campos. Só o 0060E decide.
- **Cache e concorrência.** É o risco mais provável de defeito silencioso, tratado por §3.4 e pelos testes de concorrência e sequência.
- **Mutação do IR compartilhado.** Hoje nenhum consumidor muta o PhysicalIR, mas nada impede. Tratado por teste no 0060D.
- **Identidade de proxies do lxml.** Chaves por identidade exigem manter referências vivas.
- **Plataforma.** As sondas rodaram no macOS; a equivalência de bytes precisa ser verificada no Ubuntu, que é onde o produto roda.
- **Memória.** O 0060D retém um IR a mais; o pico já chega a 170 MiB na Dissertação.

---

## 8. Proveniência

- Medição: `docs/benchmarks/0059-measurement-report.md`, com `sintetico-full.json` `23bddc80fba62ff9cbcd9c6ef812bf3945d2ae721f44a3e01db65efbc7d87226` e `reais-full.json` `659f9360f7b6d4881b5b5c0ee27f07a94eb2a40d45931efc06101c57611a6331`, ambos fora do repositório.
- Auditoria arquitetural do Claude Opus sobre `4bcda30`, com três sondas em fixtures sintéticas, no macOS com Python 3.12.13. Nenhum DOCX real foi lido nessas sondas.
- Os percentuais de etapa citados no §1 vêm da variante instrumentada da medição oficial, no Ubuntu.
