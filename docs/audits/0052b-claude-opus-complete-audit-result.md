# Auditoria 0052B — auditoria completa do Formatador Acadêmico pelo Claude Opus

**Auditor:** Claude Opus 5
**Data:** 2026-09-10
**Commit auditado:** `08fed75e81541d439bf31bd532ecf4096896a6b2` (P3 / `spacing.line`), verificado como ancestral de `f1cf0785b9278fb6454fd614ffba77a36bc51d92`
**Suíte executada localmente:** **758 passed, 1 warning, 6.87s** (venv fora do repositório, `PYTHONPATH=src`)
**Repositório não foi modificado durante a auditoria.**

Convenções: **[FATO]** = observado no código, no XSD ou em execução · **[INFERÊNCIA]** = dedução · **[RECOMENDAÇÃO]** = juízo do auditor.
Achados marcados **CONFIRMADO** foram reproduzidos por execução; os demais são risco derivado de leitura de código.

---

## 1. Veredito geral

# APROVADO COM AJUSTES

O P3 **pode permanecer em produção**. Não encontrei nenhum caminho em que ele corrompa, apague ou invente conteúdo do DOCX: a mutação é mínima, a aritmética é exata, o allowed-delta é verificado por c14n e o par `(w:line, w:lineRule)` é sempre escrito junto. As quatro condições bloqueantes da auditoria 0051 foram atendidas.

O que encontrei foi outra classe de problema, e ela é séria: **três caminhos de conformidade falsa na camada Analysis**, em que o sistema declara o parágrafo conforme sem nunca ter observado o valor efetivo. Nenhum destrói documento; todos fazem o produto afirmar algo que não verificou — o que, para este projeto, é o risco central.

---

## 2. Tabela de achados

| # | Sev. | Local | Impacto | Evidência |
|---|---|---|---|---|
| A1 | **ALTO** | `analysis/formatting.py:493-511` | Conformidade falsa: `lineRule` direto sem `w:line` é detectado e depois descartado quando um nível inferior fornece `w:line` | **CONFIRMADO** por execução |
| A2 | **ALTO** | `analysis/formatting.py:498` | Conformidade falsa: `w:spacing` duplicado com valores conflitantes resolve silenciosamente pelo primeiro | **CONFIRMADO** por execução |
| A3 | **ALTO** | `decision/engine.py` (ramo `spacing.line`) | Combinação `non_compliant / review / human_choice_required` não existe na matriz congelada 0020/0021; especialização por slot entra na Decision Layer contra o §10 da 0049 | **CONFIRMADO** por execução |
| M1 | MÉDIO | `analysis/formatting.py:509` | Razão machine-readable invertida: `line_rule_without_line_unsupported` reportado para valores que **têm** `w:line` | **CONFIRMADO** (`w:line="+360"`) |
| M2 | MÉDIO | `patcher/xml_patch.py:76`, `profile_input/model.py:18` | `MAX_LINE_TWIPS = 2_147_483_647` é INT32_MAX, não limite OOXML/Word: aceita ~8,9 milhões de linhas; mensagem alega base OOXML inexistente | leitura de código |
| M3 | MÉDIO | 3 módulos | Conversão ×240 triplicada e `MAX_LINE_TWIPS` duplicado: risco de deriva entre boundary e executor | leitura de código |
| M4 | MÉDIO | `docs/handoff.md:160-175, 268-278, 471` | Handoff contradiz a si mesmo: "Slice automático atual" ainda exclui P3; "Expansões futuras" ainda lista P3/P4; PR #29 descrita como branch | **CONFIRMADO** |
| M5 | MÉDIO | `analysis/formatting.py:265`, `:93-99` | Porta lexical aceita dígitos Unicode (schema-inválido) e recusa `+360` (schema-válido) | **CONFIRMADO** |
| m1 | MENOR | `patcher/xml_patch.py:183` | Mensagem fixa "more than one direct w:jc" dispara também para `w:spacing` | leitura |
| m2 | MENOR | `patcher/model.py:62` | `NONCANONICAL_RUN_PROPERTIES` nomeia "run" em rejeições de parágrafo (herdado do P4, ainda aberto) | leitura |
| m3 | MENOR | `tests/test_profile_input_v01.py:405-418` | Teste de exemplos: `Path` relativo ao CWD, `continue` silencioso em JSON malformado, pula exemplos sem `schema_version` | leitura |
| m4 | MENOR | `analysis/formatting.py:486-488` | Guardas de numbering/bidi retornam cadeia de evidência vazia `()`, ao contrário de `_resolve_indent_slot` | leitura |

---

## 3. Achados de alta gravidade em detalhe

### A1 — `lineRule` direto sem `w:line` é descartado quando o estilo fornece `w:line` — CONFIRMADO

**[FATO]** `_resolve_spacing_slot` detecta a forma malformada e marca `malformed_line`, mas a verificação final só é alcançada se o laço terminar sem resolver:

```python
if line_slot:
    for sp in spacings:
        if _attr(sp,"w:line") is None and _attr(sp,"w:lineRule") is not None:
            malformed_line = True
            chain.append(LevelEvidence(level.name,True,"line_rule_without_line",...))
target = next((sp for sp in spacings if ... and (not line_slot or _attr(sp,"w:line") is not None)), None)
...
    chain.append(...); return ResolvedValue(ResolutionStatus.RESOLVED, value, ev, tuple(chain), None)  # <- sai aqui
...
if malformed_line:                                   # <- nunca alcançado se algum nível resolveu
    return ResolvedValue(ResolutionStatus.UNRESOLVED, ..., R_LINE_WITHOUT_VALUE)
```

**[FATO] Reprodução.** Parágrafo com `pStyle="X"` e `<w:spacing w:lineRule="exact"/>` direto; estilo `X` com `<w:spacing w:line="360" w:lineRule="auto"/>`:

```
A) direto lineRule=exact (sem line) + estilo line=360 auto
   status=resolved reason=None value=('auto', '1.5', 'multiple')
B) direto lineRule=auto (sem line) + estilo line=360 auto
   status=resolved reason=None value=('auto', '1.5', 'multiple')
C) controle: so o estilo
   status=resolved reason=None value=('auto', '1.5', 'multiple')
E) w:line=+360 (sem estilo)
   status=unresolved reason=line_rule_without_line_unsupported
```

A e C são indistinguíveis. O caso E prova que a guarda existe e só é derrotada quando um nível inferior resolve.

**[INFERÊNCIA]** No OOXML os atributos de `w:spacing` são herdados atributo a atributo: `lineRule="exact"` direto sobre `line="360"` herdado renderiza altura fixa de 18 pt. O sistema reporta 1,5 linhas. Se o perfil declarar 1,5, a decisão é `compliant / no_action`: **o produto afirma conformidade sobre um parágrafo que não está conforme**, sem marca no Review DOCX e sem item no relatório. Se o perfil declarar outro valor, o patch acaba corrigindo por sobreposição — ou seja, o caso perigoso é exatamente o de conformidade falsa.

**[RECOMENDAÇÃO]** Retornar `UNRESOLVED` **no momento da detecção**, sem continuar a cascata. Declaração ambígua não deve ser resolvida por um nível mais distante.

### A2 — `w:spacing` duplicado resolve em silêncio — CONFIRMADO

**[FATO]** Reprodução com `<w:spacing w:line="360"/><w:spacing w:line="480"/>` no mesmo `w:pPr`:

```
F) w:spacing duplicado conflitante
   status=resolved reason=None value=('auto', '1.5', 'multiple')
```

Resolve pelo primeiro, sem `W_DUPLICATE_PROPERTY`, sem `AMBIGUOUS`.

**[FATO]** O mesmo arquivo trata o caso análogo para indents (`_resolve_indent_slot`): duplicata conflitante de `w:ind` emite `W_DUPLICATE_PROPERTY` e devolve `AMBIGUOUS`. **[FATO]** O contrato 0051 §6.1 exige rejeitar `w:spacing` duplicado. **[FATO]** O Patcher rejeita (`DUPLICATE_TARGET_PROPERTY`, `xml_patch.py:182-184`).

**[INFERÊNCIA]** A rejeição do Patcher só protege quando há mudança a aplicar. Quando o primeiro `w:spacing` coincide com o perfil, a decisão é `compliant / no_action`, o Patcher nunca é chamado e a ambiguidade **jamais aparece**. É o mesmo padrão de A1: falso conforme.

**[RECOMENDAÇÃO]** Replicar no slot de spacing a detecção de duplicata já existente para `w:ind`: `AMBIGUOUS` + `W_DUPLICATE_PROPERTY`.

### A3 — Combinação de decisão inexistente na matriz congelada — CONFIRMADO

**[FATO]** `decision/engine.py` ganhou ramo específico por slot:

```python
if context.key.property_slot == "spacing.line":
    if observed.rule != "auto" or observed.unit != "multiple":
        return _decision(..., compliance=ComplianceStatus.NON_COMPLIANT,
                         actionability=Actionability.REVIEW,
                         reason=DecisionReason.HUMAN_CHOICE_REQUIRED, ...)
```

**[FATO]** Execução com observado `exact 18pt` contra regra de 1,5 linhas:

```
compliance    = non_compliant
actionability = review
reason        = human_choice_required
desired       = None
```

**[FATO]** A matriz congelada da 0020 prevê `human_choice_required` **apenas** com `actionability=human_choice` (`non_compliant / human_choice / human_choice_required`), e `review` **apenas** com razões `analysis_*` (`unknown / review / analysis_*`). A combinação produzida não existe em nenhuma linha.

**[FATO]** A decisão 0049 §10 estabeleceu: *"A Decision Layer continua comparando valores semânticos já normalizados, sem introduzir comparação especial."* O P3 introduziu exatamente uma comparação especial por slot na camada congelada em 0021.

**[INFERÊNCIA]** O comportamento observável é seguro — vai para revisão e não muta nada. O problema é de contrato: a matriz deixou de ser fechada, e a próxima propriedade poderá inventar outra combinação por analogia.

**[RECOMENDAÇÃO]** Duas saídas legítimas, ambas sem vocabulário novo:
1. usar `Actionability.HUMAN_CHOICE`, recuperando a linha congelada `non_compliant / human_choice / human_choice_required` — há de fato uma escolha humana ("converter altura fixa em múltiplo?"); ou
2. mover a guarda para a Analysis (`UNRESOLVED` + `R_LINE_RULE_NOT_AUTO`), obtendo `unknown / review / analysis_unresolved` pela matriz, como a 0051 previa.

A opção 2 é a que o contrato prometeu. A opção 1 é a de menor diff. O que não se sustenta é a combinação atual.

---

## 4. Regressões encontradas

**[FATO]** Nenhuma regressão funcional em P1, P2 ou P4: a suíte de 758 passa integralmente e nenhum teste anterior foi afrouxado. **[FATO]** As guardas de `numbering_relevant`/`bidi_relevant` são passadas **somente** ao slot `line` (`formatting.py:542`), preservando `before`, `after`, `before_lines` e `after_lines` com o comportamento anterior — escopo correto.

**[FATO]** O único efeito colateral do P3 sobre camadas anteriores é o ramo por slot em `decision/engine.py` (achado A3), que não altera o resultado de bold, font_size ou alignment.

**Regressão documental (M4):** `docs/handoff.md:160-175` ainda declara o slice automático como `P1 / P2 / P4` e lista **"P3 spacing patching"** entre os itens *fora* do slice; `:268-278` mantém "P3/P4 patching" em "Expansões futuras"; `:471` descreve a PR #29 como branch em andamento. A seção final (`:444-490`) registra corretamente o P3, os 758 testes e o schema 0.3 — o documento se contradiz. Como o handoff é o primeiro documento que qualquer colaborador ou modelo lê, a seção estruturada vale mais que a seção narrativa e precisa ser corrigida.

---

## 5. Lacunas de teste

1. `lineRule` direto sem `w:line` **com estilo fornecendo `w:line`** (A1) — o teste atual cobre só o caso sem estilo, que é justamente o que passa;
2. `w:spacing` duplicado conflitante na Analysis (A2) — só o Patcher é testado;
3. razão retornada em `test_spacing_universal_measure_is_unsupported` — o teste afirma o `status` e não a `reason`, deixando M1 sem cobertura;
4. `w:line="+360"` (`xsd:integer` válido) e `w:line` com dígitos Unicode (M5);
5. comparação **integral** de `PPR_CANONICAL_ORDER` contra o schema — `test_ppr_order_uses_the_xsd_mirror_indents_local_name` verifica só o nome corrigido e sua posição relativa a `suppressOverlap`, não os 36 elementos;
6. limite superior efetivo de `line_spacing` (M2): não há teste de valor absurdo aceito;
7. paridade das três implementações da conversão ×240 (M3);
8. conformidade falsa ponta a ponta: perfil 1,5 + documento A1/A2 → nenhum item no relatório, nenhuma marca no Review DOCX.

---

## 6. Contratos que precisam de emenda

- **0021 / Decision Layer** — ou reverter A3 para a Analysis, ou emendar formalmente a matriz reconhecendo a nova linha. Hoje o código diverge do contrato congelado sem emenda registrada.
- **0018 / Analysis** — registrar a semântica de `lineRule` sem `line` (A1) e de `w:spacing` duplicado (A2) como estados de abstenção, alinhando com o tratamento já existente para `w:ind`.
- **0051** — registrar o limite real de `line_spacing` (M2) e a taxonomia correta das razões (M1).
- **0028 / Patcher** — `NONCANONICAL_RUN_PROPERTIES` já cobre propriedades de parágrafo desde o P4 (m2): documentar agora e renomear no próximo bump.
- **0049** — o §10 foi contrariado pelo P3 (A3); ou o P3 se ajusta, ou o §10 é emendado com justificativa.

---

## 7. Recomendação sobre o `wml.xsd`

**[RECOMENDAÇÃO]** Não versionar o `wml.xsd` inteiro (~170 KB), e **não** introduzir dependência de rede no CI. Versionar uma **fixture verificável do fragmento relevante**, com proveniência registrada no próprio arquivo:

- a sequência de `CT_PPrBase` + `CT_PPr` (36 nomes, em ordem);
- os 8 atributos de `CT_Spacing` com seus defaults (`lineRule` default `auto`, `line` default `0`);
- a enumeração de `ST_LineSpacingRule` (`auto`, `exact`, `atLeast`);
- a enumeração de `ST_Jc` (12 valores);
- o tipo de `w:line` (`ST_SignedTwipsMeasure = union(xsd:integer, ST_UniversalMeasure)`).

Cabe em poucos KB, é auditável a olho, e permite um teste que compare a **tupla inteira** — o que a versão atual não faz (lacuna 5). A proveniência (edição da norma e hashes das cópias conferidas) fica no cabeçalho da fixture, como já está no anexo de `auditoria_xsd_0049_aprovacao.md`.

Conferência de reprodutibilidade desta auditoria: duas cópias distribuídas independentemente do `wml.xsd` da ISO/IEC 29500-4:2016, SHA-256 `cf90407251dff196…1111354` e `c2dd9f61f892deae…d218cfd`, com sequências extraídas idênticas.

---

## 8. Sequência de correções por prioridade

1. **A1** — `UNRESOLVED` na detecção de `lineRule` sem `line`, sem continuar a cascata *(conformidade falsa)*;
2. **A2** — duplicata de `w:spacing` → `AMBIGUOUS` + `W_DUPLICATE_PROPERTY`, espelhando `w:ind` *(conformidade falsa)*;
3. **A3** — resolver a combinação de decisão: mover para a Analysis ou usar `HUMAN_CHOICE`;
4. **M4** — corrigir as seções contraditórias do handoff;
5. **M1** — separar as razões: `w:line` ausente, unidade não suportada e regra não-auto são três coisas distintas;
6. **M2** — limite real de `line_spacing`, com base declarada, e mensagem que não invoque o OOXML sem base;
7. **M3** — fonte única para a conversão ×240 e para `MAX_LINE_TWIPS`;
8. **M5** — porta lexical ASCII explícita em vez de `isdigit()` + `int()`;
9. **lacuna 5** — teste comparando a tupla inteira contra a fixture do schema;
10. **m1–m4** — mensagens, taxonomia, robustez do teste de exemplos e cadeia de evidência das guardas.

Os itens 1 a 3 deveriam entrar antes do próximo ciclo de propriedade. Os demais podem acompanhar o ciclo seguinte.

---

## 9. O que está correto e deve ser preservado

- **As quatro condições bloqueantes da auditoria 0051 foram atendidas**: `mirrorIndents` corrigido com teste; exemplo JSON do §3 corrigido; `atLeast`/`exact` fora da mudança determinística; guardas de numbering e bidi implementadas no slot de spacing.
- **Aritmética exata por `as_tuple()`** em `line_twips_lexical`, sem depender do contexto global de `Decimal` — a lição da errata 0041 aplicada corretamente.
- **`(w:line, w:lineRule)` sempre escritos como par**, eliminando o risco C3.
- **Allowed-delta genuinamente verificado**: `_strip_spacing_line_for_comparison` remove apenas `line`/`lineRule` nos dois lados e compara o documento inteiro por c14n. Isso implementa a invariante dura que a auditoria 0051 pediu, muito acima do "byte a byte sempre que a biblioteca permitir" do rascunho.
- **Escopo das guardas restrito ao slot `line`**, preservando `before`/`after` intactos.
- **Medida universal tratada como não suportada, não como inválida** — a distinção correta entre documento malformado e capacidade do executor.
- **Teste de exemplos JSON dos contratos adotado** (`test_profile_input_v01.py:405`), fechando a recorrência de exemplos inválidos.
- **Profile Input** reaproveita as constantes decimais existentes e separa corretamente `ContractError` de `UnsupportedError`.
- **Validação por camada** (`_validate_rule_value` na Processing Session, `transform_log/builder`, `review_docx/builder`) estendida de forma consistente com o padrão do P4.
- **758/758 verdes**, verificados de forma independente nesta auditoria, sem afrouxamento de nenhum teste anterior.

---

## 10. Resposta específica: o P3 pode permanecer em produção?

**Sim.** Nenhum dos achados produz perda, invenção ou corrupção de conteúdo, e nenhum torna o DOCX de saída inválido. A execução em si — precondição, mutação mínima, allowed-delta, pós-condição — está entre as partes mais bem construídas do sistema.

A ressalva é de **promessa**, não de dano: nos casos A1 e A2 o produto declara conformidade sem ter observado o valor efetivo, e essa afirmação chega ao usuário pelo relatório e pela ausência de marca no Review DOCX. Enquanto A1 e A2 não forem corrigidos, o P3 não deve ser apresentado como verificação confiável de entrelinha em documentos que usem espaçamento herdado de estilo — que é a maioria dos documentos acadêmicos reais.

Corrigidos A1, A2 e A3, considero o P3 sólido.
