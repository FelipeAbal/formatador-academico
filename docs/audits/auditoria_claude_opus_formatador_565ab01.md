# Auditoria técnica — Formatador Acadêmico

**Auditor:** Claude Opus 5
**Data:** 2026-09-10
**Escopo:** repositório `FelipeAbal/formatador-academico`, `main` @ `565ab01d4afab0dc240f136c70995ebd1227ac79`
**Método:** leitura do código real, execução independente da suíte, verificação do CI via API.

Convenções: **[FATO]** = observado no repositório · **[INFERÊNCIA]** = dedução a partir do observado · **[RECOMENDAÇÃO]** = juízo do auditor.

---

## 1. Resumo executivo

O projeto está **saudável e o briefing do ChatGPT é factualmente correto** em tudo que foi verificado. Confirmados 735/735 testes verdes localmente e CI `success` no SHA exato. As correções da auditoria anterior (0040) foram efetivamente incorporadas — inclusive a errata de exatidão Decimal do Patcher (0041), que era um dos três BLOCKERs daquela auditoria.

A recomendação preliminar — "ampliar o núcleo antes de UI/API" — está **certa em direção e errada em recorte**.

O achado central desta auditoria: **P3 não é uma extensão de propriedade; é a primeira execução em nível de parágrafo do sistema inteiro.** Há **cinco contratos congelados** que precisam ser emendados antes que qualquer decisão P3 consiga sair do pipeline — e um deles, o Review DOCX, **não degrada com elegância: ele levanta exceção**, e como o `ProductOutputBundle` é atômico, o produto inteiro deixa de entregar.

Além disso, há uma lacuna latente na camada Analysis congelada: **a resolução de `spacing` e `alignment` ignora `numbering.xml`**, enquanto o mesmo código já reconhece e sinaliza esse risco para `indents`. Hoje é inofensivo (o slice é run-scoped); P3 e P4 ativam a lacuna.

Consequência prática: "implementar P3" e "implementar P4" custam **quase o mesmo trabalho estrutural**, e a diferença está toda no risco semântico da propriedade. Daí a recomendação de dividir: pagar a habilitação de parágrafo uma vez, usando a propriedade mais simples como carga, e só então executar P3.

Há ainda **duas pendências de processo**: o Product Delivery v0.1 está mergeado em `main` sem decisão de freeze, e a seção "Próximo passo operacional" do handoff está desatualizada.

---

## 2. Estado confirmado do repositório

### 2.1 Verificações independentes **[FATO]**

| Afirmação do briefing | Verificação | Resultado |
|---|---|---|
| `main` = `565ab01d…` | `git rev-parse HEAD` | ✅ confere |
| CI verde, run `34500432604` | `gh run list` | ✅ `success`, `headSha` = `565ab01d…` |
| 735 testes | `pytest -q` local (venv própria, `PYTHONPATH=src`) | ✅ **735 passed, 1 warning, 6.32s** |
| PR #18 integrado | `git log` | ✅ `565ab01 Product Delivery / File Naming v0.1` |
| Nenhuma falha conhecida | suíte + CI | ✅ confirmado |
| PRs abertos | `gh pr list --state open` | ✅ nenhum |

O único aviso da suíte vem de `zipfile` (`_open_to_write`), não do código do projeto. Sem gravidade.

### 2.2 Módulos e decisões **[FATO]**

18 módulos em `src/formatador_academico/`, 47 decisões em `docs/decisions/`. A última é `0047-product-delivery-file-naming-v01-contract.md`.

### 2.3 Prontidão real por camada para execução em nível de parágrafo **[FATO]**

Mapa verificado no código, não inferido do handoff.

| Camada | Evidência | Estado para P3/P4 | Congelada em |
|---|---|---|---|
| Analysis — spacing | `analysis/formatting.py:397-435`, `SpacingSpec` com 5 slots | **pronta**, com ressalva §3 A1 | 0018 |
| Analysis — alignment | `formatting.py:434`, `_cascade(...,"w:jc",_conv_token,...)` | **pronta**, com ressalva §3 A1 | 0018 |
| Decision Vocabulary | `decision/vocabulary.py:19-20` — P3 e P4 com `supported_in_slice=True` | **pronta** | 0019 |
| Decision Layer | `decision/engine.py:60,73` — trata `spacing.line`/`LineSpacingValue` | **pronta** | 0021 |
| Classification | `classification/classifier.py:146` — já emite `target_type="paragraph"` | **pronta** | 0023 |
| OperationPlan | `operation_plan/planner.py:60-61` — tipa P3→`LineSpacingValue`, P4→`str` | **pronta** | 0025 |
| SafetyGate | `safety_gate/gate.py:401-411` — projeta `LineSpacing`→`LineSpacingValue` | **pronta** | 0027 |
| **Processing Session** | `processing_session/model.py:23` `_SUPPORTED_BINDINGS` run-only; `RuleBinding.__post_init__` rejeita `target_type != "run"` | **bloqueia** | **0033** |
| **Patcher** | `patcher/applicator.py:46` `_EXECUTABLE_SLICE`; `xml_patch.py:310`, `validation.py:37` — só `W_B`/`W_SZ`, só `mutate_run`, só `RPR_CANONICAL_ORDER` | **bloqueia** | **0029** |
| **TransformLog** | `transform_log/builder.py:20` `_SUPPORTED_SLICE` run-only | **bloqueia** | **0031** |
| Processing Report | sem restrição de slot/target_type | **pronta** | 0035 |
| **Review DOCX** | `review_docx/builder.py:138` **levanta** `ReviewDocxIntegrityError`; `:156` restringe a `{bold, font_size}`; `model.py:56` exige `target_type == "run"` | **bloqueia com exceção** | **0037** |
| **Profile Input** | `profile_input/model.py:19` e `parser.py:21` `_SUPPORTED_PROPERTIES = {bold, font_size}` | **bloqueia** | **0042** |
| Human report | sem restrição de slot | **pronta** | 0046 |
| Product Delivery | sem restrição de slot | **pronta** | *(sem freeze)* |

**[INFERÊNCIA]** O miolo do pipeline (Decision → Plan → Gate) já foi projetado para P3/P4 e está pronto. O que falta está nas **pontas**: entrada (perfil), execução (patcher), e saída (log, review). São exatamente as camadas onde erro custa integridade do documento.

---

## 3. Achados por gravidade

### 🔴 CRÍTICO

#### C1 — Review DOCX aborta o produto inteiro no primeiro item de parágrafo

**[FATO]** `review_docx/builder.py:132-142`:

```python
for item in group:
    target = item.target
    if target.target_type != "run":
        raise ReviewDocxIntegrityError(
            f"v0.1 report item {source_kind} unexpectedly targets {target.target_type!r}"
        )
```

E `builder.py:153-160` restringe `AppliedChangeItem` a `property_slot in {"bold","font_size"}` com `target_type == "run"`.

**Cenário concreto:** habilita-se P3, um parágrafo de corpo tem `spacing.line` divergente, a Decision emite `deterministic_change`, o Patcher aplica, o Processing Report cria um `AppliedChangeItem` com `target_type="paragraph"`. `build_review_docx` levanta. Como o `ProductOutputBundle` é atômico e não publica bundle parcial, **o usuário não recebe nem o DOCX limpo, que já estava correto**.

**Gravidade:** crítica porque a falha é total, não parcial, e atinge um documento processado com sucesso.

**Barreira concreta:** antes de qualquer emissão de decisão P3, emendar 0036/0037 com política explícita de marcação para itens de parágrafo. O `w:highlight` é propriedade de *run* — marcar um achado de parágrafo exige decidir **quais runs** recebem a marca. Decisão normativa e de produto, não de implementação; ver §9.

#### C2 — `w:spacing` é um elemento compartilhado; o padrão de canonicidade do Patcher não se transfere

**[FATO]** O Patcher v0.1 valida canonicidade assim (`xml_patch.py:293-299`):

```python
if set(element.attrib) - {W_VAL} or _element_children(element):
    raise Reject(PatchReason.NONCANONICAL_RUN_PROPERTIES, ...)
```

Isso funciona para `w:b` e `w:sz` porque são elementos dedicados de atributo único. **`w:spacing` carrega legitimamente até 8 atributos** (`w:before`, `w:beforeLines`, `w:beforeAutospacing`, `w:after`, `w:afterLines`, `w:afterAutospacing`, `w:line`, `w:lineRule`) — o próprio Analysis lê os cinco slots do mesmo elemento (`formatting.py:435`).

**[INFERÊNCIA]** Port ingênua produz um de dois desastres: rejeita praticamente todo parágrafo real (atributos extras são a norma), ou — se a checagem for "corrigida" — passa a poder apagar `before`/`after` ao reescrever o elemento.

**Barreira concreta:** o contrato P3 deve exigir **allowed-delta em granularidade de atributo**, não de elemento, com invariante explícita: *todos os atributos de `w:spacing` fora de `{w:line, w:lineRule}` devem ser byte-idênticos antes e depois*, verificada na releitura do XML. Além disso, `CT_PPr` tem ordem canônica própria e bem mais longa que `CT_RPr`; será preciso um `PPR_CANONICAL_ORDER` verificado contra o ECMA-376, no mesmo rigor do comentário existente em `xml_patch.py:36-49`.

#### C3 — `w:line` sem `w:lineRule` muda o significado do valor

**[FATO]** `analysis/formatting.py:246-253`:

```python
if rule == "auto":              value = Decimal(line) / 240   # múltiplos de linha
if rule in ("atLeast","exact"): value = Decimal(line) / 20    # pontos (twips)
```

O mesmo inteiro `360` significa **1,5 linhas** sob `auto` e **18 pt** sob `exact`.

**Cenário concreto:** o usuário declara "1,5 linhas". O parágrafo alvo tem `w:lineRule="exact"` herdado do estilo. Se o Patcher escrever apenas `w:line="360"`, o resultado é 18 pt de altura fixa — texto potencialmente cortado, documento silenciosamente destruído, e qualquer teste que só compare `w:line` passa.

**Barreira concreta:** `LineSpacingValue` já é composto (`rule`, `value`, `unit`) e o Gate já o projeta corretamente (`gate.py:409`). O contrato P3 deve exigir que `(w:line, w:lineRule)` sejam escritos **atomicamente como par**, e rejeitar como `unsupported_operation` qualquer `LineSpacingValue` sem `rule` explícita. Teste obrigatório: alvo com `lineRule="exact"` e regra `auto` declarada → o par inteiro é reescrito, nunca só um lado.

### 🟠 ALTO

#### A1 — A resolução de `spacing` e `alignment` ignora `numbering.xml`, e o código já sabe que isso é um risco para `indents`

**[FATO]** `analysis/formatting.py:436-437`:

```python
numbering_relevant = _has_property(direct_bag,"w:numPr") or any(... for level in style_levels)
indents = IndentSpec(**{slot: _resolve_indent_slot(slot, attr, chars, all_levels, numbering_relevant, ...)})
```

`numbering_relevant` é calculado e passado **exclusivamente para `_resolve_indent_slot`**, que emite `W_NUMBERING_PRESENT` e `R_NUMBERING_INDENT` (linhas 373-374). `spacing` (linha 435) e `alignment` (linha 434) usam apenas `all_levels = direct + estilos + docDefaults` — **`numbering.xml` não entra na cascata e nenhum aviso é emitido**.

**[INFERÊNCIA]** `w:lvl/w:pPr` em `numbering.xml` pode declarar `w:spacing` e `w:jc`. Para parágrafos de lista, o valor "efetivo" reportado pelo Analysis pode estar **errado** — reportando `ABSENT` ou o valor de `docDefaults` quando o valor real vem da numeração. A Decision compararia contra um `observed` incorreto e poderia emitir `deterministic_change` desnecessário ou equivocado.

Hoje é **inofensivo**: o slice executável é run-scoped, e `w:lvl/w:rPr` formata o marcador da lista, não os runs do parágrafo. **P3 e P4 ativam a lacuna.** O código reconhecer o risco para `indents` e não para `spacing` parece descuido de escopo do Marco 1, mas não há registro que confirme em qualquer sentido.

**Barreira concreta (conservadora, alinhada à política da casa):** excluir do slice executável P3/P4 todo parágrafo com `w:numPr` direto ou herdado de estilo, tratando-o como `review` com razão explícita. `numbering_relevant` já está computado na linha 436 — custo baixo. A alternativa (estender a cascata para `numbering.xml`) é ciclo próprio de Analysis e não deve ser embutida no ciclo P3.

#### A2 — Patch direto sobre valor herdado desacopla o parágrafo do estilo

**[FATO]** O precedente congelado é *decidir sobre o valor efetivo, gravar como propriedade direta*: `apply_font_size` (`xml_patch.py:283`) cria um `w:sz` direto mesmo quando o valor observado veio de um estilo.

**[INFERÊNCIA]** Para `font_size` isso é discreto. Para `spacing`, gravar `w:spacing` direto em centenas de parágrafos cujo valor vinha do estilo "Normal" **quebra a governança do documento**: o autor edita o estilo depois e nada propaga. O documento fica correto hoje e frágil para sempre.

**Barreira concreta:** não mudar o padrão (mutação de `styles.xml` está fora e é bem mais perigosa), mas **tornar o fato visível**. O `EvidenceRef` já carrega `source_kind` e `style_id`; o contrato P3 deve exigir que o relatório humano distinga "valor direto corrigido" de "valor herdado de estilo, agora fixado no parágrafo", e que a seção de limitações declare o desacoplamento.

#### A3 — Aritmética de unidades precisa do mesmo rigor da errata 0041

**[FATO]** A errata 0041 corrigiu `Decimal * 2` sob contexto global para aritmética inteira exata (`xml_patch.py:_exact_half_points`, com `numerator // denominator`). O código atual está correto.

**[INFERÊNCIA]** P3 introduz **três** conversões novas: 240-avos de linha (`auto`), twips (`atLeast`/`exact`), centésimos de linha (`beforeLines`/`afterLines`). Cada uma é ponto de reintrodução do mesmo bug.

**Barreira concreta:** um conversor por regra, todos em aritmética inteira exata, `unrepresentable_value` sem arredondamento, e teste de fronteira para valores não exatos — replicando literalmente a disciplina de 0041.

#### A4 — Convergência do loop de sessão não é óbvia para valores compostos

**[FATO]** `processing_session/engine.py` refaz o pipeline inteiro após cada patch aplicado, até quiescência ou `max_applied_operations`.

**[INFERÊNCIA]** A convergência depende de o valor escrito re-resolver para o mesmo valor semântico. Trivial para `bool` e `Decimal`. Para `LineSpacingValue`, o ciclo grava→relê→converte passa por duas conversões de unidade; qualquer assimetria produz alvo que nunca fica conforme e consome o orçamento até `operation_limit_reached`.

**Barreira concreta:** teste de round-trip semântico obrigatório por regra (`auto`, `atLeast`, `exact`), e teste de idempotência de segunda passada com asserção de **zero** operações aplicadas.

### 🟡 MÉDIO

#### M1 — Product Delivery v0.1 está em `main` sem freeze

**[FATO]** `docs/decisions/0047-...md` declara: *"Status: ACEITO PARA IMPLEMENTAÇÃO — freeze após PR + CI + auditoria final."* Não existe `0048`. O handoff lista corretamente os freezes 0021…0046 em "Baseline validado" e **não inclui** Product Delivery — a documentação está coerente consigo mesma, mas o ciclo está aberto.

**[INFERÊNCIA]** Por todos os ciclos anteriores, o padrão é `contrato → PR → CI → freeze → handoff`. Este parou no CI.

**Barreira:** emitir `0048 — Product Delivery / File Naming v0.1 — freeze` antes de abrir o próximo ciclo.

#### M2 — Seção "Próximo passo operacional" do handoff está obsoleta

**[FATO]** `docs/handoff.md`, seção final, ainda descreve o ciclo do Product Delivery como *futuro*: *"Definir a próxima decisão de produto após o fechamento da PR #18… decidir se v0.1 retorna coleção tipada de arquivos ou também ZIP determinístico"* — decisões já tomadas e implementadas, descritas na seção "Etapa concluída" imediatamente acima. O documento se contradiz.

**[INFERÊNCIA]** Risco real de handoff: um modelo ou colaborador que leia a seção final como instrução vai reimplementar o que existe.

**Barreira:** reescrever a seção com a decisão que sair desta auditoria.

#### M3 — Adicionar propriedade ao Profile Input exige decisão de versionamento não tomada

**[FATO]** `profile_input/model.py:19` e `parser.py:21` fixam `{bold, font_size}`. O contrato 0040 previu extensão *"por nova `schema_version` ou extensão explicitamente versionada"*, mas não escolheu o mecanismo. `_SUPPORTED_PROPERTIES` está **duplicado** em dois arquivos — hoje consistente, mas ponto de deriva.

**Barreira:** decidir (ver §9) e unificar a constante numa fonte única.

#### M4 — `italic` está congelado no vocabulário mas fora do slice

**[FATO]** `decision/vocabulary.py:17` — `VocabularyEntry(DecisionKey("run","P1","italic"), ..., supported_in_slice=False)`, e `require_supported_key` levanta para ele.

**[INFERÊNCIA + RECOMENDAÇÃO]** Tecnicamente italic é a expansão **mais barata** de todas: toggle de run idêntico a `bold`, o Analysis já o resolve (`ResolvedRunFormatting.italic`), sem habilitação de parágrafo. **E mesmo assim não é recomendável agora.** Itálico em texto acadêmico é *semântico*, não apresentacional: títulos de obras, termos estrangeiros, ênfase autoral, nomes científicos. Uma regra `body.italic = exact false` destruiria significado autoral em massa — exatamente a categoria de dano listada como tolerância zero. Barato de implementar não é o mesmo que seguro de oferecer.

### 🔵 BAIXO

- **B1** — `_SUPPORTED_PROPERTIES` duplicado (`model.py:19` / `parser.py:21`); unificar.
- **B2** — `pyproject` não instalou em modo editável numa venv limpa (`ModuleNotFoundError` sem `PYTHONPATH=src`); a CI cobre, mas convém checar se um clone novo roda `pytest` sem ajuste.
- **B3** — Aviso de `zipfile` na suíte; ruído, sem gravidade.

---

## 4. Comparação das alternativas de próxima etapa

Critérios: valor para o usuário · risco de dano ao documento · custo estrutural (contratos congelados a emendar) · capacidade de validação objetiva.

| # | Alternativa | Valor | Risco semântico | Contratos a emendar | Validável? | Veredito |
|---|---|---|---|---|---|---|
| 1 | **P3 spacing.line** | **Alto** — 1,5 entrelinhas é a regra acadêmica mais pedida | **Alto** (C2, C3, A1, A3) | 0029, 0031, 0033, 0037, 0042 | sim, com fixtures novas | **valioso, mas não como primeiro passo** |
| 2 | **P4 alignment** | Médio-alto — justificação é regra padrão | **Baixo**: `w:jc` é elemento dedicado, atributo único, token fechado, sem unidade — isomorfo a `w:b` | **os mesmos 5** | sim, trivialmente | **melhor veículo para a habilitação de parágrafo** |
| 3 | Italic / props de run | Baixo | **Muito alto** (M4 — destrói semântica autoral) | 0019, 0029, 0031, 0042 | sim | **não** |
| 4 | Citações e referências | Muito alto | **Proibitivo** — exige classificação semântica confiável, hoje `precision > coverage` com abstenção | vários + Classification | não com o corpus atual | **não** |
| 5 | UI / API / persistência | Alto percebido | Baixo tecnicamente, **alto de produto**: congela superfície sobre núcleo de 2 propriedades | nenhum | sim | **depois** |
| 6 | Ampliar sistema de perfis | Baixo isolado | Baixo | 0042 | sim | **não isolado** — subproduto de 1 ou 2 |

**[INFERÊNCIA] Observação decisiva:** as alternativas 1 e 2 têm **custo estrutural idêntico** — as mesmas cinco emendas da §2.3. A diferença é inteiramente o risco semântico da propriedade. Escolher P4 primeiro **não adia P3**: constrói e valida os trilhos de parágrafo contra a propriedade mais simples do sistema, e entrega P3 no ciclo seguinte com risco isolado.

O argumento contrário — "faça P3 direto e economize um ciclo" — falha na capacidade de diagnóstico: se algo quebrar num ciclo que estreia simultaneamente mutação de `pPr`, binding de parágrafo, marcação de parágrafo no Review e semântica composta de entrelinha, não haverá como saber se o defeito está nos trilhos ou na propriedade.

---

## 5. Recomendação final

**[RECOMENDAÇÃO]**

**Não aprovar P3 como a próxima decisão. Aprovar, em seu lugar, uma decisão de habilitação de parágrafo cuja carga executável é P4/alignment — e P3 imediatamente depois, como segundo ciclo.**

Sequência proposta:

```
0048  Product Delivery v0.1 — freeze              (encerrar ciclo aberto)
0049  Paragraph Target Enablement v0.1 + P4/alignment
0050  freeze
0051  P3 / spacing.line v0.1                       (sobre trilhos já validados)
0052  freeze
```

A decisão 0049 paga, uma única vez e contra a propriedade mais simples do sistema:

1. `RuleBinding` com `target_type="paragraph"` (emenda a 0033);
2. mutação de `pPr` no Patcher, com `PPR_CANONICAL_ORDER` verificado contra ECMA-376 (emenda a 0029);
3. slice do TransformLog (emenda a 0031);
4. **política de marcação de itens de parágrafo no Review DOCX** (emenda a 0037) — item de maior risco, resolvido contra o caso mais simples;
5. exposição de propriedade de parágrafo no Profile Input (emenda a 0042);
6. exclusão de parágrafos com `w:numPr` do slice executável (barreira A1).

A decisão 0051 fica com escopo estreito e auditável: conversão de unidades, par `(w:line, w:lineRule)`, allowed-delta em granularidade de atributo sobre `w:spacing`, convergência.

**Sobre UI/API:** correto adiar, mas não indefinidamente. **[INFERÊNCIA]** Com bold, font_size, alignment e spacing, o produto cobre a maior parte do que uma normalização acadêmica básica realmente faz. Esse é o ponto natural para a interface — não antes, não muito depois.

---

## 6. Contrato sugerido para a próxima decisão

Esboço de **0049 — Paragraph Target Enablement v0.1 (carga: P4/alignment)**. O contrato P3 (0051) reaproveita esta estrutura substituindo a seção de valores.

**Entradas aceitas**
`ProcessingProfile` com binding `target_type="paragraph"`, `aspect_id="P4"`, `property_slot="alignment"`, classes `body`/`heading`, modos `exact`/`set`/`preserve`. Valores: apenas tokens do conjunto fechado observado pelo Analysis, declarados explicitamente pelo usuário. **Nenhuma regra normativa embutida** — sem "ABNT justifica corpo".

**Estados de evidência** (já existentes, sem ampliação)
`RESOLVED` · `ABSENT` · `UNRESOLVED` · `INVALID` · `AMBIGUOUS`, com `evidence_chain` preservada.

**Estados de decisão** (matriz congelada 0020, sem alteração)
`ABSENT` + regra ativa → `unknown / review / analysis_absent`. `UNRESOLVED`/`INVALID`/`AMBIGUOUS` → `review`. Regra ausente → `preserve / rule_absent`. `preserve` → `containment`, silencioso.

**Operações permitidas**
Exatamente uma: `SET_PROPERTY` sobre `w:jc` direto no `w:pPr` do parágrafo alvo, em `word/document.xml`. Criação de `w:pPr` ou de `w:jc` apenas na posição canônica de schema. Nenhuma outra propriedade tocada.

**Situações que devem ser recusadas** (`Reject` ordinário, sem output)
- parágrafo com `w:numPr` direto ou herdado — **barreira A1**;
- `w:pPr` ou `w:jc` com forma física não canônica (atributos/filhos fora do modelo de conteúdo);
- alvo sob `w:del`/`w:ins` ou revisão protegida;
- `physical_hash` divergente após releitura;
- valor fora do conjunto de tokens suportados;
- qualquer alvo fora de `word/document.xml`.

**Situações que devem apenas ser relatadas**
Toda `actionability` em `review`/`human_choice`; parágrafos de lista excluídos pela barreira A1, com razão explícita; parágrafos cujo valor vencedor era herdado de estilo — aplicados, **mas com a herança declarada no relatório humano** (barreira A2).

**Formato do log**
`TransformRecord` existente, com `_SUPPORTED_SLICE` estendido para `("paragraph","P4","alignment")`. Sem novos campos. `LengthValue` não se aplica; valor é token.

**Propriedades parcialmente especificadas**
Não aplicável a `alignment` (slot escalar). **Para 0051/P3 esta cláusula é essencial:** a regra governa **exclusivamente** o slot `line`; `before`, `after`, `beforeLines`, `afterLines` e os flags de autospacing permanecem intocados e não geram achado.

**Herança não resolvida**
Mantém-se o padrão congelado: **decidir sobre o valor efetivo, gravar como propriedade direta.** Não introduzir mutação de `styles.xml`. Não introduzir cálculo próprio de herança — o Analysis já o faz e é a fonte única.

> **Resposta explícita à pergunta do briefing:** a primeira versão deve **decidir sobre o valor efetivo herdado** (que o Analysis já resolve, com cadeia de evidência) e **alterar apenas por propriedade direta**. Não deve calcular herança por conta própria, nem alterar estilos. Isso não é escolha nova: é o comportamento já congelado de `font_size`, e divergir dele criaria duas semânticas de patch no mesmo produto.

**Autoridade negativa**
Não interpreta ABNT. Não infere alinhamento a partir de conteúdo. Não altera `styles.xml`, `numbering.xml` nem `settings.xml`. Não toca stories secundárias, tabelas ou containers. Não amplia o Review DOCX além da política de marcação decidida. Não reprocessa o documento.

---

## 7. Plano mínimo de testes antes de qualquer merge

### Unitários
1. conversão de valor por regra, aritmética inteira exata, sem arredondamento *(P3: uma por regra `auto`/`atLeast`/`exact`)*;
2. valores não representáveis → `unrepresentable_value`, nunca arredondados;
3. ordem canônica de `CT_PPr` verificada contra o schema, criando `w:pPr` e `w:jc` ausentes na posição certa;
4. `w:pPr`/`w:jc` não canônico → rejeição ordinária;
5. `RuleBinding` com `target_type="paragraph"` aceito; `target_type` inválido rejeitado;
6. Profile Input aceita a propriedade nova; `schema_version` antiga rejeita a nova propriedade com o erro correto;
7. **P3:** `(w:line, w:lineRule)` sempre escritos como par; `LineSpacingValue` sem `rule` → rejeitado.

### Integração de pipeline
8. ponta a ponta com regra de parágrafo: perfil JSON → cinco arquivos de entrega;
9. parágrafo com `w:numPr` → **não alterado**, relatado com razão explícita;
10. valor herdado de estilo → aplicado como direto, herança visível no relatório;
11. `ABSENT` + regra ativa → `review`, documento intocado;
12. autospacing (`UNRESOLVED`) → `review`, nunca alteração *(P3)*;
13. limite de operações respeitado com muitos parágrafos.

### Fixtures DOCX necessárias
14. parágrafo com `w:jc`/`w:spacing` direto;
15. valor apenas no estilo de parágrafo;
16. valor apenas em `docDefaults`;
17. cadeia `basedOn` de dois níveis;
18. **parágrafo de lista com `w:numPr`** (barreira A1);
19. **`w:spacing` com `before`/`after` presentes ao lado de `line`** (barreira C2);
20. **`lineRule="exact"` com regra `auto` declarada** (barreira C3);
21. `beforeAutospacing="1"`;
22. valor lexical inválido;
23. parágrafo sob `w:del`/`w:ins`;
24. estilo ausente / ciclo de estilos.

### Não alteração
25. fixture 19 → `before`/`after`/`*Lines`/`*Autospacing` **byte-idênticos** antes e depois;
26. perfil só-`preserve` → clean byte-idêntico ao input;
27. regra ausente → zero decisão para o slot;
28. nenhuma parte do pacote fora de `word/document.xml` modificada;
29. `w:szCs` e demais pontos cegos declarados permanecem intactos.

### Idempotência
30. segunda passada sobre o clean → **zero** operações aplicadas, mesmo SHA;
31. round-trip semântico por regra: valor gravado re-resolve para o valor decidido;
32. determinismo byte a byte em execuções repetidas e sob `PYTHONHASHSEED` variado.

### Relatório e documento de revisão
33. item de parágrafo **não** levanta `ReviewDocxIntegrityError` (regressão direta de C1);
34. política de marcação de parágrafo produz exatamente o que o contrato definir;
35. highlight autoral preexistente preservado;
36. relatório humano distingue valor direto de valor herdado;
37. relatório JSON e Markdown consistentes entre si e com o `processing_report_ref`.

### Regressão de Bundle e manifest
38. lineage completo do `ProductOutputBundle` com decisões de parágrafo presentes;
39. cinco arquivos, ordem fixa, hashes e tamanhos do manifest conferem byte a byte;
40. **a suíte de 735 passa integralmente sem alteração** — nenhum teste existente pode ser afrouxado para acomodar P3/P4. *(Se um teste precisar mudar, é sinal de que um contrato congelado foi violado sem emenda formal.)*

### Casos ambíguos cuja saída correta é **não alterar**
41. lista numerada; 42. autospacing; 43. valor inválido; 44. parágrafo em revisão; 45. estilo ausente; 46. `set` sem `preferred` com valor fora → `human_choice`, documento intocado.

---

## 8. Riscos residuais

Permanecem mesmo com todas as barreiras acima:

1. **`w:szCs`** — já registrado como dívida bloqueante de uso amplo; não resolvido e não afetado por este ciclo.
2. **Numeração** — a barreira A1 *exclui* parágrafos de lista em vez de resolvê-los. Documentos acadêmicos têm listas; a cobertura será menor do que o usuário espera. Abstenção correta, mas precisa aparecer no relatório humano.
3. **Desacoplamento de estilo** (A2) — mitigado por transparência, não eliminado.
4. **Corpus** — o corpus-base v1 tem 41 fixtures dimensionadas para o slice run-scoped. **[INFERÊNCIA]** As metas de precisão (≥99%, ≥99,5% em alto risco) não foram medidas para propriedades de parágrafo. Antes de prometer P3/P4 em produção, o corpus precisa de fixtures de parágrafo — os itens 14-24 são o mínimo, não o suficiente.
5. **Equivalência semântica de DOCX reempacotado** — dívida já registrada, não afetada.
6. **Ausência de rollback multi-operação** — com P3 o número de operações por documento cresce muito (uma por parágrafo, não por run divergente); `operation_limit` e performance de patches sequenciais, ambos já registrados como dívida, ficam mais próximos de importar.

---

## 9. Perguntas que precisam da decisão do Felipe

Não respondíveis a partir do código — são de produto ou normativas.

1. **Marcação de parágrafo no Review DOCX.** `w:highlight` é propriedade de run. Um achado de espaçamento pertence ao parágrafo. Marcar **todos** os runs do parágrafo (visualmente pesado, mas honesto), apenas o **primeiro** run (discreto, mas arbitrário), ou **não marcar** e deixar o achado só nos relatórios? Bloqueia 0049.
2. **Versionamento do Profile Input.** Adicionar `alignment`/`line_spacing` como `schema_version: "0.2"` aceitando "0.1" em paralelo, ou estender "0.1" no lugar? Recomendação: 0.2 com aceitação dupla — perfis já escritos continuam válidos.
3. **Parágrafos de lista.** Confirmar exclusão do slice executável de P3/P4 (abstenção segura, cobertura menor), ou abrir antes um ciclo de Analysis para incorporar `numbering.xml` à cascata?
4. **Sequência.** Aceitar P4 antes de P3 pelos motivos de §4-5, ou o valor de entrelinha 1,5 é tão dominante que se prefere P3 direto assumindo o risco acoplado? *(Se for P3 direto, o menor recorte seguro está na §11.)*
5. **`before`/`after`.** Confirmar que a v0.1 de P3 governa **somente** `line`? Perfis acadêmicos reais costumam especificar espaçamento antes/depois de títulos.
6. **Itálico.** Manter fora por risco semântico (M4), apesar de ser tecnicamente a expansão mais barata?

---

## 10. Modelo Claude adequado para a próxima tarefa

**Esta auditoria:** exigiu Opus. O achado central (mapa de bloqueios da §2.3 e lacuna de numeração em A1) veio de correlacionar oito arquivos em camadas diferentes contra contratos congelados — não de ler qualquer documento isoladamente.

| Tarefa | Modelo | Motivo |
|---|---|---|
| Redigir 0048 (freeze Product Delivery) e atualizar handoff | **Sonnet** | mecânico, evidência já reunida aqui |
| Redigir o contrato 0049 | **Sonnet**, com Opus na revisão final | o esboço da §6 já fixa a estrutura |
| Implementar 0049 | **Sonnet** | escopo estreito e bem definido |
| **Auditar `PPR_CANONICAL_ORDER` contra ECMA-376** | **Opus** | erro de ordem de schema corrompe DOCX silenciosamente |
| **Auditar o contrato 0051 (P3) antes de implementar** | **Opus** | C2, C3 e A3 concentram-se aqui |
| Implementar 0051 | Sonnet ou Kimi | após contrato auditado |

---

## 11. Pergunta final — resposta direta

> **Devemos aprovar agora a implementação de P3, espaçamento de parágrafos?**

**Não como próximo passo.** A evidência é a tabela §2.3: P3 não é extensão de propriedade, é a estreia da execução em nível de parágrafo, e exige emendar cinco contratos congelados (0029, 0031, 0033, 0037, 0042). Um deles, o Review DOCX, **levanta exceção** em vez de degradar (`review_docx/builder.py:138`), e como o `ProductOutputBundle` é atômico, o primeiro achado de parágrafo derruba a entrega inteira de um documento que já foi processado corretamente. Somam-se três riscos específicos de `spacing` — elemento XML compartilhado (C2), par `(w:line, w:lineRule)` semanticamente inseparável (C3), e a lacuna de `numbering.xml` na camada Analysis congelada (A1).

**Qual etapa vem antes:** `0048` fechando o freeze do Product Delivery, e `0049 — Paragraph Target Enablement v0.1` com **P4/alignment** como carga executável. `w:jc` é elemento dedicado, atributo único, valor de token fechado, sem unidade — isomorfo ao `w:b` que o Patcher já executa com segurança. Paga exatamente o mesmo custo estrutural que P3 pagaria, contra a propriedade de menor risco do sistema, e entrega justificação de texto, que tem valor próprio.

**P3 vem em seguida (`0051`)**, sobre trilhos já validados, com escopo reduzido ao que é genuinamente difícil.

**Se a decisão for P3 direto**, o menor recorte seguro é: apenas o slot `line`; apenas `rule="auto"` (múltiplos de linha); apenas parágrafos **sem** `w:numPr`; par `(w:line, w:lineRule)` escrito sempre atomicamente; allowed-delta em granularidade de atributo garantindo que `before`/`after`/`*Lines`/`*Autospacing` fiquem byte-idênticos; e a política de marcação de parágrafo do Review DOCX decidida **antes** de a primeira decisão P3 ser emitida.
