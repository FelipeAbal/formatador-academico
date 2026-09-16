# Decisão 0060A: contrato do ciclo 0060 — otimização conservadora com equivalência exata

**Status:** PROPOSTA, revisão 2, pendente de conferência textual e de autorização
**Data:** 2026-09-16
**Base:** `main` após o merge do PR #60, commit `4bcda308a4975f2bb84d87ab4738faaed463bb75`
**Depende de:** `docs/benchmarks/0059-measurement-report.md`; auditoria arquitetural do Claude Opus sobre o mesmo commit; parecer do DeepSeek Flash 4.1 sobre a revisão 1 desta decisão
**Não altera:** nenhum código de produção. Esta decisão é contrato e critério, não implementação.

**Revisão 2 — o que mudou em relação à revisão 1**

1. As emendas passam a apontar para os contratos normativos (0009, 0011, 0028 e 0032). Os congelamentos (0010, 0012, 0029 e 0033) aparecem como registros reafirmados, não como alvos de emenda.
2. O predicado de não interferência foi separado em três planos (valor semântico, hash físico e referências derivadas) e **saiu do conjunto de obrigações executáveis do 0060**: no 0060 ele é especificação preparatória; quem o implementa e valida é o 0061.
3. A memoização do 0060C passa a ter mecanismo definido: `EvaluationContext` explícito, com escopo por avaliação.
4. A chave do índice do parser deixa de ser `id()` de proxy do lxml.
5. O serializador canônico do oráculo está definido tipo a tipo, com as duas lacunas nomeadas.
6. Foi acrescentado teste de identidade entre a IR e o catálogo vindos da pós-condição e os de uma nova avaliação dos mesmos bytes.
7. Os critérios de desempenho passam a registrar mínimo, mediana e máximo, a regra contra regressão ficou mais rigorosa e o limite de memória só será fixado depois de medir o tamanho real da IR.

---

## 1. Contexto

A medição oficial do ciclo 0059 rodou no Ubuntu, com Python 3.12.3, `lxml` 6.1.3, no commit `84879124…`, sobre seis DOCX reais, com seis execuções por documento em ordem ABBA:

- a pós-condição ocupa de 83,0% a 90,0% do tempo de patch, e de 17,6% a 28,0% do tempo total;
- o ciclo completo repetido a cada alteração ocupa de 92,9% a 96,3% do tempo total;
- os dois parses por alteração ocupam de 32,9% a 54,5% do total;
- referência e instrumentação não divergiram em nenhuma execução;
- `input_unchanged_on_disk = true` nas 36 execuções: nenhum arquivo original foi alterado;
- medianas dos dois mais pesados: 458,3 s (artigo Hellen-2) e 502,7 s (Dissertação final).

A auditoria arquitetural acrescentou, por sondas em fixtures sintéticas e leitura de código:

1. **parser quadrático no número de irmãos**: `_structural_path` reconstrói a lista de irmãos de cada ancestral por registro; 87% do parse com 800 parágrafos; memoizar a posição dentro de uma chamada produziu IR idêntico e sessão 2,0× a 3,6× mais rápida;
2. **cada Decision serializada cerca de 11 vezes por iteração**, em planner, SafetyGate e mapas da sessão;
3. **um patch não muda o valor semântico de nenhum outro alvo**; muda o `physical_hash` do alvo e de todos os seus ancestrais.

Esses números vieram de fixtures sintéticas no macOS. Servem para ordenar o trabalho, não para prometer ganho em documento real.

---

## 2. Decisão

1. **O agrupamento de operações em lote e a atomicidade multi-alvo ficam rejeitados neste ciclo.**
2. O ciclo 0060 aplica apenas otimizações compatíveis com a cadeia atual de um patch por vez, capazes de provar equivalência exata.
3. O ciclo tem cinco fases em PRs próprios, com auditoria adversarial independente: **0060A** (este contrato), **0060B** (parser), **0060C** (serialização), **0060D** (snapshot verificado compartilhado) e **0060E** (medição oficial). O **0061** é condicional.
4. **Avaliação incremental e SafetyGate incremental não fazem parte do 0060.** Ficam para o 0061.
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

a execução otimizada produz artefatos **idênticos** aos da implementação de referência congelada em `4bcda30`, no mesmo ambiente suportado. Idêntico significa igualdade de bytes nos artefatos serializados e igualdade campo a campo nos objetos congelados. Não vale "equivalente" nem "semanticamente igual".

A exigência vale também nos caminhos de falha: mesmo tipo de exceção e mesma condição de disparo.

A referência vive como oráculo de teste, em worktree fixa de CI ou cópia sob `tools/`, e **nunca** como caminho alternativo em runtime.

### 3.2 Serializador canônico do oráculo

A comparação usa serializadores canônicos já congelados, e não `repr`, `pickle` ou comparação de objetos ad hoc. Convenção comum: enums viram string, `Decimal` vira string, tuplas viram array, `sort_keys=True`, separadores compactos, UTF-8, sem timestamp e sem valor aleatório.

| Artefato comparado | Serializador |
| --- | --- |
| `ClassificationResult`, inclusive evidências, avisos, metadata, proveniência e `parent_anchor` | `classification.serialization.serialize_classification_result` e `serialize_classification_results` |
| `Decision`, inclusive `evidence_ref`, `decision_warnings` e `analysis_reason` | `decision.serialization.serialize_decision` |
| `PlannedOperation`, `PlanningResult` e `OperationPlan` | `operation_plan.serialization` |
| `GateResult` e `SafetyGateReport` | `safety_gate.serialization` |
| `TransformRecord` | `transform_log.serialization.serialize_transform_record` e `transform_ref` |
| `ProcessingReport` | `processing_report.serialization.serialize_processing_report` e `processing_report_ref` |
| DOCX limpo, Review DOCX, relatório humano, relatório técnico e manifesto | SHA-256 dos bytes, com o `filename` e o `DeliveryRole` de cada item na ordem de `ROLE_ORDER` |

**Duas lacunas a preencher no 0060A, como ferramenta de teste e não como API pública:**

1. **`SessionFinding`**: não possui serializador congelado. O oráculo define um, com os campos `kind`, `decision_ref`, `operation_ref`, `target` e `reason`, reusando a convenção acima.
2. **Envelope do `ProcessingSessionResult`**: não possui serializador congelado. O oráculo define um envelope que compõe os serializadores existentes, na ordem `processing_session_version`, `status`, `profile_ref`, `input_package_sha256`, `output_package_sha256`, `sha256(output_package_bytes)`, `transforms`, `final_classifications`, `final_decisions` e `findings`, preservando a ordem real de cada tupla.

Ambos vivem sob `tools/` ou `tests/`. Nenhum deles altera modelo congelado, e nenhum deles vira API de produção. Se, em qualquer fase, o serializador do oráculo precisar de um campo que o modelo congelado não expõe, a fase para e abre emenda específica.

### 3.3 Campos e artefatos que precisam permanecer idênticos

**`ProcessingSessionResult`:** `status`; `input_package_sha256`; `output_package_sha256`; `output_package_bytes`; `transforms`, na mesma ordem e com todos os campos de cada record, inclusive `operation_ref`, `operation_plan_ref`, `decision_ref`, `profile_ref`, `rule_ref`, `target` com o `physical_hash` pré-transformação, `precondition_observed`, `desired_value`, `input_package_sha256`, `output_package_sha256` e `changed_part`; `final_classifications`, `final_decisions` e `findings`, na mesma ordem.

**Derivados:** `serialize_transform_record` e `transform_ref` de cada record; `serialize_processing_report`; relatório humano; Review DOCX; os cinco arquivos do Product Delivery, com os mesmos nomes e papéis.

**Intermediários exigidos, porque entram nos artefatos acima:** número de iterações lógicas; ordem real de aplicação; SHA de cada snapshot intermediário; `operation_plan_ref` de cada iteração.

### 3.4 Preservação de TransformLog, ProcessingReport, Review DOCX, Product Delivery e allowed-delta

Regra estrutural do ciclo:

> **Nenhuma fase pode alterar quantas iterações lógicas existem, qual operação é aplicada em cada uma, nem sobre quais bytes.** As fases só podem deixar de recalcular resultados idênticos.

- **TransformLog (0030, congelado em 0031):** um record por patch, com a cadeia `saída N == entrada N+1`. Proibido envelope de lote ou record sem SHA intermediário.
- **ProcessingReport (0034, congelado em 0035):** um `AppliedChangeItem` por record, na ordem real.
- **Review DOCX (0036, congelado em 0037):** opera sobre o snapshot final e sobre os itens do relatório; preservados os dois, o resultado é idêntico.
- **Product Delivery (0038/0047, congelados em 0039/0048):** cinco arquivos comparados por hash, papel e nome.
- **allowed-delta (0028 §20):** permanece unitário, provando um delta autorizado por patch; a pós-condição continua rodando sobre bytes relidos do ZIP produzido, nunca sobre a árvore em memória.

### 3.5 Caches: escopo, registro e invalidação

A interface web usa `ThreadingHTTPServer`, com sessões simultâneas no mesmo processo. Portanto:

1. **Proibido cache em nível de módulo, de classe, de variável global ou de `ContextVar`.** A proibição do `ContextVar` é explícita: ele sobrevive à chamada e é invisível na assinatura.
2. Todo cache tem escopo declarado, de **chamada** (criado e descartado dentro de uma função pública, caso do 0060B) ou de **avaliação/sessão** (criado em `process_document` e descartado em `finally`, casos do 0060C e do 0060D).
3. Nenhum cache sobrevive entre duas chamadas públicas.
4. Nenhum cache é chaveado por algo que não identifique o snapshot: caminho estrutural isolado e índice de parágrafo são chaves proibidas.
5. **Proibido chavear por igualdade semântica.** `Decimal("1.5") == Decimal("1.50")` e `True == 1`, mas a serialização difere.
6. Cada cache é registrado na decisão da sua fase com sete campos: nome; o que guarda; chave exata; escopo; evento de invalidação; custo de memória esperado; teste que prova a invalidação.
7. Invalidação: mudou o snapshot, o cache cai. Consumo de artefato ligado a bytes exige conferência de SHA; divergência é `ProcessingSessionIntegrityError`, nunca uso degradado. Retém-se apenas o snapshot corrente.
8. Em modo de teste, cada cache expõe acertos, erros e invalidações, para que o teste prove a invalidação, e não apenas o resultado.
9. Testes obrigatórios: N sessões simultâneas em threads com documentos e perfis diferentes; e duas sessões em sequência no mesmo processo, na ordem A, B, A.

### 3.6 Predicado de não interferência (especificação preparatória, não obrigação do 0060)

Este predicado **não é implementado no 0060**. Nenhuma fase do 0060 reusa resultado de avaliação entre snapshots diferentes. A especificação fica aqui porque é o pré-requisito formal do 0061, e porque o 0060B e o 0060D precisam respeitá-la para não fechar portas.

O predicado se divide em **três planos, que nunca podem ser confundidos**:

**Plano 1 — valor semântico.** Depois de um patch no alvo T, o valor resolvido pela Analysis e o resultado da Classificação de qualquer alvo diferente de T permanecem iguais, no slice congelado atual:

| Camada | Conjunto de leitura | Sensível a bold/font_size em run? | Sensível a alignment/spacing.line em parágrafo? |
| --- | --- | :---: | :---: |
| Classificação de parágrafo | tipo de story, texto normalizado, contêiner, `pStyle` resolvido, catálogo | não | não |
| Projeção de run | classe do parágrafo e hash do próprio run | não, quanto ao valor | não |
| Formatação de run | bag do run, `pStyle` do parágrafo, catálogo, `docDefaults` | só o run alvo | não |
| Formatação de parágrafo | bag do parágrafo, catálogo, `docDefaults` | não | só o parágrafo alvo |
| StyleCatalog | `word/styles.xml` | não; o Patcher nunca altera `styles.xml` | não |

**Plano 2 — hash físico.** O XML canônico do parágrafo contém os seus runs. Logo, **uma alteração em um run muda o `physical_hash` do parágrafo que o contém**, e o de todos os demais ancestrais, como contêiner de run, célula, linha e tabela. Isso é correto e esperado. Hashes físicos **nunca** são reaproveitados entre snapshots: são sempre recalculados a partir do XML corrente.

**Plano 3 — referências derivadas.** Como `DecisionTarget` e `OperationTarget` carregam `physical_hash`, e `TargetClassification` também, a mudança do plano 2 propaga para `decision_ref`, `operation_ref` e `operation_plan_ref`, ainda que o plano 1 não mude nada.

**Regras que valem desde já, inclusive para o 0061:**

1. **Proibido reusar `ClassificationResult` ou `Decision` verbatim quando o `physical_hash` do alvo mudou.** O reuso admissível é apenas o do **valor semântico** (resultado da Analysis, status e classe da Classificação), que reconstrói objetos novos.
2. Toda reconstrução recalcula `physical_hash`, `DecisionTarget`, `OperationTarget`, `TargetClassification.physical_hash`, `decision_ref`, `operation_ref` e `operation_plan_ref`.
3. O conjunto de alvos afetados por um patch em T é T mais **todos** os ancestrais de T, e precisa ser derivado da árvore real, nunca de prefixo de caminho.
4. O predicado vale só para o slice congelado. **Qualquer propriedade nova precisa declarar seu conjunto de leitura e refazer a prova antes de entrar.** Uma propriedade que altere `pStyle`, numeração, texto ou `styles.xml` invalida a tabela do plano 1.
5. A validação do predicado, quando o 0061 for aberto, exige modo sombra no CI: recalcular tudo e comparar a cada iteração, falhando na primeira divergência.

### 3.7 Medição no Ubuntu

Mesma máquina, mesmo Python 3.12.3, máquina ociosa, mesma ferramenta `tools/benchmark_0059.py`, sem alterá-la durante o ciclo. Se a ferramenta precisar mudar, isso vira PR próprio e anterior, e a linha de base precisa ser remedida.

Protocolo por medição:

1. linha de base sintética completa, `--repeats 3`, `--timeout 1800`;
2. os seis documentos reais, `--repeats 3`, `--timeout 3600`, perfil `builtin-academic-0059`, arquivos fora do repositório e sem `--record-docx-path`;
3. saída gravada fora do repositório; em documento entram apenas hashes, nomes, tamanhos e SHA-256;
4. comparação com a linha de base 0059: `sintetico-full.json` `23bddc80…` e `reais-full.json` `659f9360…`;
5. verificação de `input_unchanged_on_disk` em todas as execuções;
6. verificação de equivalência por hash dos cinco arquivos entregues, referência × otimizado, por documento, gravando **apenas hashes**.

Para cada documento registram-se **mínimo, mediana e máximo** da variante `reference`, que é o total oficial. A variação observada em 0059 entre mínimo e máximo foi de no máximo 1,2% da mediana; esse é o ruído de fundo aceito.

Cada fase de código roda um recorte sintético e os dois documentos mais pesados, para decidir continuar. A medição completa é o 0060E.

### 3.8 Critério relativo para Hellen-2 e para a Dissertação

```text
reducao = 1 - (mediana_0060E / mediana_0059)

mediana_0059:
    artigo Hellen-2       458,3 s   (min 458,2  max 463,5)
    Dissertação final     502,7 s   (min 500,1  max 503,6)
```

- **Meta do ciclo:** `reducao >= 0,40` nos dois, medida no 0060E, sobre o conjunto das fases.
- **Piso de continuidade:** `reducao >= 0,25` nos dois. Entre 0,25 e 0,40, o ciclo é integrado com a meta registrada como não atingida, e o 0061 é aberto.
- **Abaixo de 0,25 nos dois:** as fases seguem integráveis se houver equivalência e nenhuma regressão, mas o ciclo é registrado como insuficiente e o 0061 passa a ser obrigatório.
- A meta é relativa à linha de base de cada documento. Não há meta absoluta em segundos, que dependeria de hardware.

### 3.9 Regra contra regressão

Mais rigorosa que a da revisão 1, porque o ruído medido é pequeno:

1. **Bloqueio:** nenhum documento pode ter mediana acima de 1,03 × mediana de 0059. Acima disso, o merge está barrado.
2. **Justificativa obrigatória:** qualquer mediana acima da mediana de 0059, mesmo dentro dos 3%, exige justificativa escrita na fase e concordância explícita de Felipe.
3. **Regra de máximo:** o máximo de cada documento não pode superar o máximo de 0059 em mais de 5%. Isso pega piora de cauda que a mediana esconde.
4. **Regra de forma:** a dispersão relativa, `(máximo − mínimo) / mediana`, não pode passar de 3% em nenhum documento. Acima disso a medição é considerada instável e precisa ser repetida antes de qualquer conclusão.
5. A linha de base sintética não pode regredir em nenhum dos 15 casos, pelo mesmo critério de mediana.

### 3.10 Memória

O limite de 20% da revisão 1 foi fixado sem medida e **fica suspenso**.

Em fixtures sintéticas, a IR ocupa cerca de 28 vezes o tamanho do DOCX, com 1,8 MiB para um documento de 67 KiB e 3,7 MiB para um de 132 KiB. Esse fator **não pode ser extrapolado** para a Dissertação, porque lá a maior parte dos 3,2 MB é imagem, que não se expande em registros.

Portanto:

1. O **0060A** entrega a instrumentação de tamanho da IR: bytes da IR em memória e do catálogo, por documento.
2. A medição desse tamanho nos seis documentos reais roda **no Ubuntu, antes do 0060D**, e registra apenas nome, tamanho, SHA-256 e os bytes medidos.
3. Só depois disso o limite é fixado, na forma `pico permitido = pico de 0059 + tamanho medido da IR + 15%`, escrito como emenda a esta decisão.
4. Até lá vale uma trava de segurança: nenhum documento pode ultrapassar o dobro do pico registrado em 0059 (de 48 MiB a 170 MiB, conforme o documento).

---

## 4. Avaliação do critério preliminar

| Critério proposto | Parecer | Forma adotada |
| --- | --- | --- |
| Nenhum documento piora mais de 10% | frouxo: o ruído medido é de 1,2% da mediana | §3.9: bloqueio em 3% pela mediana, mais regra de máximo e de dispersão |
| Redução mediana de 40% nos dois mais pesados | ambicioso e plausível: os dois parses ocupam 44,3% e 54,5% do total nesses documentos | mantido como meta, com piso de 25% (§3.8) |
| Equivalência sem divergências | obrigatório | mantido, estendido aos caminhos de falha e aos cinco arquivos entregues |
| Todos os testes atuais passando | necessário, insuficiente | mantido, somado aos testes novos e aos diferenciais contra o oráculo |
| Três execuções ABBA com a ferramenta 0059 | correto | mantido, com registro de mínimo, mediana e máximo |

Acréscimos obrigatórios: os seis documentos mantêm exatamente as alterações e os itens de revisão de 0059 (51/84, 53/9, 288/100, 99/23, 63/130 e 26/6); nenhuma execução pode terminar em timeout ou erro; `input_unchanged_on_disk` verdadeiro em todas; memória conforme §3.10.

---

## 5. Fases

### 0060A — contrato, critérios e oráculo

**Objetivo.** Fixar decisão, equivalência, oráculo, regras de cache e critérios antes de qualquer otimização.

**Escopo.** Este documento; o oráculo de referência de `4bcda30`; o serializador canônico do oráculo (§3.2), incluindo as duas lacunas; a ferramenta de comparação por hashes dos cinco arquivos entregues; a instrumentação de tamanho da IR (§3.10); a fixture de estresse estrutural usada no 0060B. Nada em `src/`.

**Contratos emendados.** Nenhum.

**Contratos e congelamentos reafirmados.** 0009 e 0011 (parser, normativos), 0010 e 0012 (congelamentos), 0024, 0026, 0028, 0030, 0032, 0034, 0036, 0038 e 0047 (normativos), 0025, 0027, 0029, 0031, 0033, 0035, 0037, 0039 e 0048 (congelamentos).

**Invariantes de segurança.** O oráculo e o serializador do oráculo são artefatos de teste e nunca viram runtime. A ferramenta de comparação não copia documento, não grava caminho absoluto e não registra texto.

**Testes.** A ferramenta de comparação precisa de teste próprio: artefatos iguais dão igual; um byte diferente dá diferente; nenhum conteúdo de documento aparece na saída. O serializador do oráculo precisa de teste de cobertura de campos, que falha se um campo novo de um modelo congelado ficar de fora.

**Aprovação.** Auditoria adversarial do contrato; concordância explícita de Felipe com §3.8, §3.9 e §3.10.

**Fallback.** Não se aplica; nada em produção muda.

---

### 0060B — parser

**Objetivo.** Remover o custo quadrático do caminho estrutural, sem alterar a IR.

**Escopo.** `docx_parser.py`: índice de posição entre irmãos por tipo de nó e índice de `original_index`, construídos **uma vez por chamada de `parse_bytes`** e descartados no retorno. Sem mudança de campos, de ordem, de avisos ou de semântica de caminho. `parser_api.resolve_structural_path` fica fora.

**Chave do índice (correção obrigatória).** **Proibido usar `id()` de proxy do lxml como chave isolada**, porque o identificador pode ser reaproveitado depois que o proxy é coletado. A implementação deve:

1. usar como chave o próprio objeto elemento, num dicionário que mantém a referência viva;
2. manter uma referência à árvore, ou ao `ElementTree`, durante toda a indexação e todo o uso do índice;
3. construir o índice de um nó pai sob demanda e descartá-lo junto com a chamada;
4. nunca guardar o índice além do `parse_bytes` que o criou.

**Contratos emendados.** **0009 e 0011**, os contratos normativos do parser, por nota de erratum de implementação registrando a mudança de custo e a obrigação de IR idêntica. `PARSER_VERSION` **não** muda, porque a saída não muda.

**Congelamentos reafirmados.** 0010 e 0012: o congelamento continua válido justamente porque a IR não muda.

**Contratos intactos.** Todos os demais, inclusive 0024, 0026, 0028, 0030, 0032 e 0034.

**Invariantes de segurança.** IR idêntica, campo a campo e na serialização canônica; índice local à chamada, nunca global nem em `ContextVar`; nenhuma mudança em limites de ZIP, profundidade ou avisos; `status = partial` preservado.

**Testes.**
- IR idêntica ao oráculo em todas as fixtures existentes;
- fixture de estresse: irmãos de mesmo nome intercalados com outros elementos; comentários e instruções de processamento como irmãos; `mc:AlternateContent`; `w:sdt`; hyperlinks; campos; tabelas aninhadas; profundidade próxima do limite; stories secundárias;
- dois parses sucessivos no mesmo processo e parses concorrentes em threads;
- documento com story parcial;
- **IR byte-idêntica nos seis DOCX reais**, verificada no Ubuntu, comparando o hash da serialização canônica da IR entre referência e otimizado, gravando apenas os hashes;
- suíte completa atual.

**Aprovação.** IR idêntica em 100% dos casos, sintéticos e reais; CI verde; recorte sintético e os dois documentos mais pesados sem regressão (§3.9) e com ganho mensurável; auditoria adversarial.

**Fallback.** `git revert` isolado do PR; nenhuma outra camada depende desta fase.

---

### 0060C — serialização de decisões

**Objetivo.** Eliminar reserializações idênticas dentro de **uma mesma avaliação**, sem mudar nenhum valor.

**Mecanismo (definido, não deixado à implementação).** Um `EvaluationContext` explícito, criado em `_evaluate` e passado adiante por parâmetro:

```text
EvaluationContext:
    package_sha256: str
    decision_blobs: dict[identidade da Decision -> bytes]
    decision_refs:  dict[identidade da Decision -> str]
```

Regras:

1. escopo estritamente por avaliação; nasce e morre dentro de `_evaluate`;
2. chave por **identidade do objeto**, com a referência mantida viva pelo próprio contexto, jamais por `__eq__`/`__hash__` (§3.5, regra 5);
3. **proibido** cache global, de módulo, de classe ou em `ContextVar`;
4. nenhuma verificação de integridade pode ser pulada por estar "já conferida": o SafetyGate continua recomputando `source_decisions_hash` e comparando com `plan.source_decisions_hash`, e continua detectando Decisions duplicadas; o que se evita é reserializar o mesmo objeto;
5. refs continuam derivados, nunca armazenados em modelo congelado.

**Contratos emendados.** Nenhum, **se** o contexto for passado por parâmetro interno, com valor padrão que preserva as assinaturas públicas de `build_operation_plan`, `evaluate_operation_plan`, `source_decisions_hash` e `decision_ref`.

**Cláusula de escape.** Se a implementação concluir que alguma assinatura pública precisa mudar, a fase **para** e abre emenda ao contrato normativo correspondente: **0024** para OperationPlan, **0026** para SafetyGate e **0032** para Processing Session. Nesse caso, 0025, 0027 e 0033 são reafirmados como congelamentos e a mudança exige nova auditoria antes do código.

**Congelamentos reafirmados.** 0025, 0027, 0031 e 0033.

**Invariantes de segurança.** Nenhum valor muda; nenhuma verificação some; determinismo preservado.

**Testes.**
- Decisions com `Decimal("1.5")` e `Decimal("1.50")` coexistindo produzem refs distintos e corretos;
- `bool` e `int` em valores observados;
- Decisions iguais vindas de snapshots diferentes não compartilham entrada de cache;
- duplicata de Decision continua sendo erro de integridade no gate;
- `source_decisions_hash` adulterado continua sendo erro;
- o contexto não sobrevive à avaliação, verificado por instrumentação de cache;
- concorrência e sequência de sessões (§3.5, regra 9);
- determinismo com `PYTHONHASHSEED` variado, inclusive em subprocesso;
- diferenciais de sessão contra o oráculo.

**Aprovação.** Diferenciais idênticos; CI verde; sem regressão; auditoria adversarial.

**Fallback.** `git revert` isolado, independente do 0060B.

---

### 0060D — snapshot verificado compartilhado

**Objetivo.** Fazer um parse por snapshot em vez de dois. Hoje a pós-condição faz o parse dos bytes de saída e a iteração seguinte repete o mesmo parse.

**Escopo.** Um contexto de sessão guarda, apenas para o **snapshot corrente**, o par (PhysicalIR, StyleCatalog) produzido na pós-condição, ligado por `sha256` dos bytes e por `parser_version`, consumido pela avaliação seguinte. Opcionalmente, reuso da avaliação depois de rejeição comum do Patcher, quando os bytes não mudaram.

Este compartilhamento **não** é reuso entre snapshots diferentes, e por isso não depende do predicado do §3.6: é o mesmo parse dos mesmos bytes, feito uma vez.

**Contratos emendados.**
- **0028**, contrato normativo do Patcher: o Patcher pode entregar ao chamador o resultado do parse que já fez na pós-condição. A pós-condição em si não muda: continua relendo os bytes do ZIP produzido, com o Parser real, conforme 0028 §19.
- **0032**, contrato normativo do Processing Session: "o pipeline completo roda novamente" passa a significar que a avaliação é recomputada por inteiro sobre o novo snapshot, admitindo que o parse desse snapshot seja obtido uma única vez, com ligação obrigatória por SHA.

**Congelamentos reafirmados.** 0029 e 0033, que continuam valendo com a semântica emendada em 0028 e 0032; a emenda só passa a valer com a implementação integrada.

**Contratos intactos.** 0024/0025, 0026/0027, 0030/0031, 0034/0035, 0036/0037, 0038/0039 e 0047/0048.

**Invariantes de segurança.**
- a pós-condição continua sobre bytes relidos do ZIP produzido, nunca sobre a árvore em memória;
- nada é guardado se a pós-condição falhar; a falha continua fail-fast antes de APPLIED;
- consumo só depois de conferir o SHA; divergência é erro de integridade;
- retém-se apenas o snapshot corrente;
- a IR compartilhada não pode ser mutada por nenhum consumidor;
- cache de sessão descartado em `finally`.

**Testes.**
- **identidade obrigatória:** para os mesmos bytes, a IR e o catálogo vindos da pós-condição são idênticos aos de uma nova avaliação, comparados pela serialização canônica da IR e pelos campos do catálogo (`part_name`, `part_sha256`, `part_status`, `doc_defaults`, `styles` e avisos). Esse teste roda em fixtures sintéticas e, no Ubuntu, nos seis documentos reais, gravando só hashes;
- consumidor instrumentado que muta a IR é detectado por hash canônico antes e depois da avaliação;
- SHA divergente entre IR guardada e bytes correntes gera `ProcessingSessionIntegrityError`;
- falha de pós-condição não deixa IR guardada e preserva a exceção;
- rejeição comum, progresso independente e nova tentativa depois da mudança de snapshot (0032 §9);
- limite de operações no ponto exato de corte;
- detecção de ciclo de SHA;
- concorrência e sequência de sessões;
- memória dentro da trava do §3.10;
- diferenciais contra o oráculo: bold e font no mesmo run; P3 e P4 no mesmo parágrafo; operação de run e de parágrafo no mesmo parágrafo; run em hyperlink; `w:rPrChange`; `w:del` e `w:ins`; campos.

**Aprovação.** Diferenciais idênticos; teste de identidade verde nos sintéticos e nos seis reais; CI verde; ganho medido nos dois mais pesados; memória dentro do limite; auditoria adversarial.

**Fallback.** `git revert` do PR, que também reverte as emendas a 0028 e 0032, já que elas só valem com a implementação integrada.

---

### 0060E — medição oficial no Ubuntu

**Objetivo.** Medir o ciclo inteiro com o protocolo do 0059 e decidir se a meta foi atingida.

**Escopo.** Execução do §3.7; equivalência por hash dos cinco arquivos entregues nos seis documentos; relatório `docs/benchmarks/0060-measurement-report.md`; atualização de `docs/handoff.md`. Nenhuma alteração de código.

**Contratos emendados.** Nenhum.

**Congelamentos reafirmados.** Todos.

**Invariantes de segurança.** Os DOCX reais continuam fora do repositório, identificados só por nome, tamanho e SHA-256; nenhum caminho absoluto gravado; integridade verificada por `input_unchanged_on_disk`.

**Testes.** Não se aplica; exige-se o protocolo e os hashes de equivalência.

**Aprovação.** §3.8, §3.9, §3.10 e §4, avaliados em conjunto.

**Fallback.** Havendo regressão ou qualquer divergência de equivalência, as fases de código são revertidas na ordem inversa, voltando a `4bcda30`, que é linha de base já medida.

---

### 0061 — condicional, fora do 0060

Aberto somente se o 0060E não atingir a meta, ou se Felipe decidir seguir mesmo com a meta atingida. Conteúdo previsto:

1. avaliação incremental, reusando **valor semântico** de alvos não tocados, com reconstrução obrigatória de hashes e referências derivadas (§3.6);
2. SafetyGate incremental, avaliando até o primeiro token liberado, com avaliação integral no snapshot terminal;
3. implementação e validação do predicado do §3.6, com modo sombra no CI e matriz de dependência por `(target_type, property_slot)`.

O 0061 exige contrato próprio, auditoria própria e emendas a **0026** e **0032**.

---

## 6. Fora do escopo, explicitamente

Adiados, com contrato e auditoria próprios:

1. agrupamento de operações compatíveis numa mesma passagem;
2. atomicidade multi-alvo, com transação e rollback;
3. `allowed-delta` de múltiplos alvos;
4. qualquer mudança na semântica de `TransformRecord`, na ordem de aplicação ou nos identificadores do relatório;
5. avaliação incremental e SafetyGate incremental, que são o 0061.

Os itens 1, 2 e 3 exigem, antes de discussão técnica, **decisão de produto** sobre mudar o que o usuário recebe no relatório. Também fica fora qualquer nova propriedade do slice automático.

---

## 7. Riscos reconhecidos

- **Ganho menor que o das sondas:** fixtures sintéticas são largas e rasas; documentos reais têm tabelas, SDT e campos. Só o 0060E decide.
- **Cache e concorrência:** risco mais provável de defeito silencioso; tratado por §3.5 e pelos testes de concorrência e sequência.
- **Mutação da IR compartilhada:** hoje nenhum consumidor muta a IR, mas nada impede; teste no 0060D.
- **Identidade de proxies do lxml:** tratada pela regra de chave do 0060B.
- **Plataforma:** as sondas rodaram no macOS; a equivalência precisa ser verificada no Ubuntu.
- **Memória:** o 0060D retém uma IR a mais, e o limite só será fixado depois de medir (§3.10).

---

## 8. Pontos que ainda dependem de escolha

1. **Meta e piso (§3.8):** 40% e 25% precisam do seu aval explícito. Eles orientam o que fazer se o ganho ficar no meio.
2. **Regra contra regressão (§3.9):** bloqueio em 3% pela mediana, mais as regras de máximo e de dispersão. Se preferir tolerância zero acima da mediana de 0059, diga, e o texto muda.
3. **Limite de memória (§3.10):** a fórmula só será escrita depois de medir a IR nos seis documentos. Falta decidir se essa medição entra no 0060A ou vira pré-requisito do 0060D.
4. **Reuso depois de rejeição** no 0060D: é opcional e não traz ganho nos seis documentos, que não tiveram rejeições. Pode ser cortado para reduzir superfície.
5. **Onde vivem o oráculo e o serializador do oráculo:** worktree de CI ou cópia sob `tools/`. A cópia é mais simples de auditar; a worktree não duplica código.
6. **Abertura do 0061:** decidir se ele é automático quando a meta não for atingida, ou se depende de nova autorização sua.

---

## 9. Proveniência

- Medição: `docs/benchmarks/0059-measurement-report.md`, com `sintetico-full.json` `23bddc80fba62ff9cbcd9c6ef812bf3945d2ae721f44a3e01db65efbc7d87226` e `reais-full.json` `659f9360f7b6d4881b5b5c0ee27f07a94eb2a40d45931efc06101c57611a6331`, ambos fora do repositório.
- Auditoria arquitetural do Claude Opus sobre `4bcda30`, com sondas em fixtures sintéticas, no macOS com Python 3.12.13. Nenhum DOCX real foi lido nessas sondas.
- Parecer do DeepSeek Flash 4.1 sobre a revisão 1 desta decisão, achados A1 a A10, incorporados nesta revisão.
- Percentuais de etapa do §1: variante instrumentada da medição oficial, no Ubuntu.
- Tamanho da IR do §3.10: medido em fixtures sintéticas, 1,8 MiB para um DOCX de 67 KiB e 3,7 MiB para um de 132 KiB.
