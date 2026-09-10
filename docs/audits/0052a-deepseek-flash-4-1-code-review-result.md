# Auditoria 0052A — revisão de código pelo DeepSeek Flash 4.1

**Objeto:** `08fed75e81541d439bf31bd532ecf4096896a6b2` (main pós-PR #29)
**Método:** leitura de 0048/0049/0051, da auditoria Claude 0051, diff do PR #29 e código final; execução da suíte; sondas adversariais executadas fora do repositório (não alterei a árvore — `git status` limpo). Suíte: **758 passed, 87 subtests**, com Python 3.12 + lxml 6.1.3.

**Veredito: APROVAR COM AJUSTES OBRIGATÓRIOS.** O núcleo do P3 (Profile→Analysis→Decision→Plan→Gate→Patcher→Log) está correto e bem defendido. Há, porém, um defeito bloqueante na ponta de entrega (relatório humano) e lacunas de coerência/determinismo que os 758 testes não tocaram.

---

## Defeitos confirmados

### F1 — 🔴 BLOQUEANTE — Relatório humano não suporta `LineSpacingValue`

- **Arquivo/função:** `src/formatador_academico/human_report/renderer.py`, `_value_text` (l. 76-89); uso em `_render_applied` (l. 135-136), `_render_unapplied` (l. 148-149), `_render_review` (l. 164); chamada final em `product_delivery/builder.py:115`.
- **Observado:** `_value_text` trata `None`, `bool`, `Decimal`, `LengthValue`, `str` e `Enum`, mas não `LineSpacingValue`. Qualquer `AppliedChangeItem`, `UnappliedChangeItem` ou `ReviewItem` de P3 carrega `observed`/`desired` como `LineSpacingValue`, e a renderização levanta `HumanReportIntegrityError: unsupported report value type: LineSpacingValue`.
- **Impacto:** `build_product_from_inputs` (ProductOutputBundle) funciona, mas a **entrega final** (`build_product_delivery`, decisões 0047/0048) **falha atomicamente** para todo documento em que P3 gera mudança aplicada ou item de revisão — isto é, para o caso de uso inteiro do P3. É uma falha dura, sem recuperação, e o `test_line_spacing_schema_03_e2e` não a pega porque para no bundle e nunca passa pelo renderer.
- **Reprodução:** DOCX com `<w:spacing w:line="480" w:lineRule="auto"/>` + perfil 0.3 `line_spacing exact 1.5` → `build_product_from_inputs` OK → `build_product_delivery(bundle, base_name="x")` → `HumanReportIntegrityError`. Mesmo resultado para observação `exact`/`atLeast` (revisão).
- **Teste mínimo sugerido:** estender `tests/test_product_delivery_v01.py` com um fluxo P3 aplicado e um P3 em revisão; em `tests/test_human_report_v01.py`, um teste `test_line_spacing_value_renders` sobre `report.applied_changes[0].observed_before` e um sobre review `observed`.
- **Correção recomendada:** adicionar ramo `isinstance(value, LineSpacingValue)` em `_value_text` (ex.: `"1.5 linhas"` para `unit=="multiple"`; `"12 pt (exact)"`/`"12 pt (atLeast)"` para `pt`), importando de `decision.model`; e acrescentar `"alignment"`/`"spacing.line"` a `_PROPERTY_LABELS` (l. 25-28). Manter o erro de integridade para tipos realmente inesperados.
- **Confiança:** alta (reproduzido duas vezes).

### F2 — 🟠 MÉDIA — Conversões da Analysis dependem do contexto global de `Decimal`

- **Arquivo/função:** `src/formatador_academico/analysis/formatting.py`, `_conv_line_spacing` (l. 268: `Decimal(line)/240`; l. 269: `Decimal(line)/20`). Mesma classe em `_conv_font_size` (l. 245) e `_conv_twips` (l. 251).
- **Observado:** com `getcontext().prec = 1`, o valor observado de `w:line="360"` vira `2` em vez de `1.5`; um documento que já satisfaz o perfil passa a ser visto como divergente, é planejado um patch, e a pós-condição estoura: `PatcherIntegrityError: postcondition mismatch: current ... Decimal('2') ... != desired ... Decimal('1.5')`. Comportamento idêntico, já existente, em P2 (`_check_output_property` faz `int(desired.value * 2)` sob contexto).
- **Impacto:** quebra o princípio congelado na errata 0041 ("nenhuma operação Decimal sujeita ao contexto global decide representabilidade") e o determinismo prometido. O gatilho exige mutação externa de `getcontext()`, mas a própria errata 0041 trata isso como adversarial e o caminho P2 já quebra com o mesmo mecanismo — logo não é hipotético.
- **Reprodução:** executar o fluxo P3 (ou P2) sob `decimal.getcontext().prec = 1`. At default `prec=28`, todos os múltiplos representáveis terminam exatamente, então o defeito fica latente.
- **Teste mínimo sugerido:** análogo a `test_patcher_v01_decimal_erratum.py::test_global_decimal_precision_does_not_change_result`, aplicado a `resolve_paragraph_formatting`/`resolve_run_formatting` com `prec` baixo, exigindo valor observado invariante.
- **Correção recomendada:** derivar o valor observado por aritmética inteira exata a partir de `raw_line` (inteiro) e do divisor (`240`/`20`/`2`), como já é feito em `_line_spacing_twips`/`line_twips_lexical`; não usar `/` Decimal. Corrigir também `_check_output_property` (`int(desired.value * 2)`).
- **Confiança:** alta (reproduzido; causa isolada).

### F3 — 🟠 MÉDIA — Razão `line_rule_not_auto_unsupported` não é a razão produzida para `exact`/`atLeast`; razões de exclusão específicas não chegam ao relatório

- **Arquivo/função:** `analysis/formatting.py` l. 507-510 (`reason = R_LINE_RULE_NOT_AUTO if ... else R_LINE_WITHOUT_VALUE`); `decision/engine.py` l. 116-124 e l. 132-141; `human_report/renderer.py:163`.
- **Observado:** a 0051 §4/§8.6 determina que observações `atLeast`/`exact` vão para revisão **como `UNRESOLVED`, com razão explícita `line_rule_not_auto_unsupported`**. Na prática `_conv_line_spacing` **resolve** `exact`/`atLeast` normalmente e o `decision/engine` as converte para `ComplianceStatus.NON_COMPLIANT / Actionability.REVIEW / DecisionReason.HUMAN_CHOICE_REQUIRED`. Reprodução end-to-end de `atLeast`: `decision.reason == human_choice_required`, `analysis_status == resolved`. O motivo `R_LINE_RULE_NOT_AUTO` só aparece para formas lexicais não-inteiras com `lineRule` exato/atLeast (ex.: `18pt exact`). Adicionalmente, `_resolve_spacing_slot` devolve `R_NUMBERING_SPACING`/`R_BIDI_DIRECTION`/`R_LINE_WITHOUT_VALUE`, mas `decide_property` mapeia todo `UNRESOLVED` para `ANALYSIS_UNRESOLVED`, de modo que a razão específica morre antes do ProcessingReport (o relatório só imprime `analysis_status` + `decision.reason`).
- **Impacto:** divergência contrato↔implementação; o usuário vê `human_choice_required`/`analysis_unresolved` em vez de `line_rule_not_auto_unsupported`/`numbering_spacing_unsupported`/`bidi_direction_unsupported`, contrariando 0051 §5 ("aparecer no relatório humano com razão explícita"). É o mesmo padrão já aceito em P4, mas a 0051 o especificou explicitamente para o slot de spacing.
- **Teste mínimo sugerido:** e2e de `atLeast` e `exact` afirmando `analysis_status == "unresolved"` e a razão `line_rule_not_auto_unsupported` no `ReviewItem`; e2e de `w:numPr`/`w:bidi` classificável como `body` afirmando a razão específica no relatório.
- **Correção recomendada:** propagar `ResolvedValue.reason` para o `Decision` (campo já existente no vocabulário ou reuso de `DecisionWarning`) **ou** rotular `exact`/`atLeast` como `UNRESOLVED` na Analysis, conforme o contrato. Sem inventar vocabulário novo: usar a razão já congelada na camada que a produz.
- **Confiança:** alta para o desvio `human_choice_required` vs contrato; alta (por código) para a perda da razão específica.

### F4 — 🟡 BAIXA/MÉDIA — Código de erro errado para `line_spacing` não numérico

- **Arquivo/função:** `profile_input/model.py`, `canonical_decimal` (l. 78-85) chamado por `canonical_rule_value` para `line_spacing` (l. 158-160).
- **Observado:** `{"mode":"exact","value":"1.5"}` em `line_spacing` produz `ProfileInputContractError` com código `font_size_type` e mensagem "font_size must be a JSON number". Via `product_input_boundary`, o código chega como `profile_input.font_size_type`.
- **Impacto:** código machine-readable e mensagem incorretos para um defeito de P3, poluindo diagnóstico/telemetria e contrariando a estabilidade das razões.
- **Reprodução:** `parse_profile_input_json` de um perfil 0.3 com `line_spacing` string.
- **Teste mínimo sugerido:** `assert cm.exception.code == "line_spacing_type"`.
- **Correção recomendada:** parametrizar o nome da propriedade nas mensagens de `canonical_decimal` (ou um `_require_json_number(property_name, value)`), preservando os códigos atuais de `font_size` para não quebrar compatibilidade.
- **Confiança:** alta.

### F5 — 🟡 BAIXA — Mensagem de duplicata afirma `w:jc` no alvo `w:spacing`

- **Arquivo/função:** `patcher/xml_patch.py`, `validate_ppr_shape` (l. 181-183).
- **Observado:** `raise Reject(..., "more than one direct w:jc")` é fixo, mesmo quando `target_tag == W_SPACING`. O `PatchReason.DUPLICATE_TARGET_PROPERTY` está correto; só o detalhe textual mente.
- **Impacto:** detalhe textual/florestal incorreto; não altera comportamento.
- **Teste mínimo sugerido:** parágrafo com dois `w:spacing` → conferir a mensagem.
- **Correção recomendada:** usar `target_tag`/`_qn` na mensagem.
- **Confiança:** alta.

### F6 — 🟡 BAIXA — `patcher/validation.py::_line_twips` não valida finitude/sinal

- **Arquivo/função:** `patcher/validation.py`, `_line_twips` (l. 156-167).
- **Observado:** diverge de `xml_patch.line_twips_lexical`: não verifica `is_finite`, `> 0`, nem o sinal (`sign` ignorado no cálculo), embora nunca seja alcançado pelo pipeline (o patch rejeita antes).
- **Impacto:** defesa em profundidade incompleta em função pública (`validate_allowed_delta` é exportada).
- **Correção recomendada:** espelhar as checagens de `line_twips_lexical` ou extrair uma única implementação compartilhada.
- **Confiança:** alta.

### F7 — 🟡 BAIXA — Formas lexicais válidas de `w:line` rejeitadas como não suportadas

- **Arquivo/função:** `analysis/formatting.py`, `_conv_line_spacing` (l. 265: `raw_line.lstrip("-").isdigit()`).
- **Observado:** `w:line=" 360 "` (whitespace é colapsável em `xsd:integer`) e `w:line="+360"` (sinal opcional) caem em `_UnsupportedObserved` e a razão reportada é `line_rule_without_line_unsupported`. `_int_lexical` conseguiria interpretá-los.
- **Impacto:** falso "não suportado" em documentos schema-válidos; ruído de diagnóstico. (P3 só lê; não escreve essas formas.)
- **Teste mínimo sugerido:** `w:line=" 360 "` e `"+360"` resolvidos como `1.5` múltiplo.
- **Correção recomendada:** tentar `_int_lexical` primeiro (que faz `strip`) e reservar `_UnsupportedObserved` para formas realmente não-inteiras (universais/frações).
- **Confiança:** alta.

---

## Riscos não confirmados

- **R1 (defesa em profundidade).** O Planner/Patcher não revalidam `precondition_observed.rule == "auto"`. A restrição `exact`/`atLeast`→`auto` vive **apenas** no guard do `decision/engine.py:132`. Uma `Decision` `deterministic_change` construída diretamente (fora do engine) com `observed.rule=="exact"` seria planejada e o Patcher converteria o modelo de espaçamento. O pipeline normal não produz isso; ainda assim, a invariante de segurança do 0051 §4 não tem segunda barreira. *Confiança: alta no comportamento; baixa de que seja explorável no fluxo congelado.*
- **R2.** `numbering_relevant` (`analysis/formatting.py:536`) considera `direct_bag` + `style_levels`, mas **não** `doc_defaults`; o bidi (`:541`) inclui `all_levels`. Um `w:numPr` declarado em `docDefaults/pPrDefault` não bloquearia P3, embora bloqueie alinhamento. *Confiança: média; não exercitei docDefaults com numPr.*
- **R3.** `processing_session/model.py::_validate_rule_value` (l. 82-89) valida tipo/positividade, mas não `multiple*240` inteiro nem o teto `ST_SignedTwipsMeasure`. Um `ProcessingProfile` construído diretamente com múltiplo não representável só é contido tarde, como `patch_rejected`, em vez de `UnsupportedError` na fronteira. *Confiança: média.*
- **R4.** A ordem de `PPR_CANONICAL_ORDER` continua verificada por regressão local (só `mirrorIndents`), não por comparação programática contra o XSD versionado — o próprio handoff registra a pendência. *Confiança: alta de que é lacuna documentada, não defeito.*

---

## Sugestões de melhoria

1. Adicionar P3 ao `_PROPERTY_LABELS` do relatório humano (`alignment`, `spacing.line`) com unidade por extenso (0051 §6).
2. Cobrir as validações de `line_spacing` já implementadas e hoje sem teste: negativo, zero, não-múltiplo (`1.001`), fora da faixa (`1e16`), expoente (`1e-17`, `1e17`), precisão (`>32` dígitos) e igualdade de hash `1.5`/`1.50`/`1.5e0` **na ponta** (não só no modelo).
3. Unificar `MAX_LINE_TWIPS` (hoje duplicado em `profile_input/model.py:18` e `patcher/xml_patch.py:76`), evitando drift.
4. Incluir P3 no teste e2e de `product_delivery` e no de `human_report` — exatamente o vão que deixou F1 passar.

---

## Pontos aprovados

- **Profile Input 0.3:** despacho por versão correto; 0.1/0.2 rejeitam `line_spacing`; `1.5`/`1.50`/`1.5e0` geram perfil e **hash de pacote idênticos** (verificado); `*240` por aritmética inteira sobre `as_tuple` (context-safe); limites de precisão/expoente/faixa coerentes.
- **Analysis:** `lineRule` ausente com `line` usa default `auto` do XSD; `lineRule` sem `line` é `UNRESOLVED` e **não mascara herança** (testei: direto `lineRule` só, estilo com `line=360` → resolve 1.5); `18pt` e tokens desconhecidos ficam `UNRESOLVED`; guardas de numeração/bidi presentes **no slot de spacing** (não herdadas de P4); bidi `val="0"/"false"` corretamente não bloqueia.
- **Decision:** guard impede troca automática `exact`/`atLeast`→`auto` e produz revisão; `LineSpacingValue` tipado em Planner/SafetyGate/TransformLog.
- **Patcher:** mutação mínima (só `w:line`/`w:lineRule`), `w:spacing` criado/reusado na posição canônica (`spacing` antes de `ind`); `before`/`beforeLines`/`beforeAutospacing`/`after`… preservados por releitura (testado); duplicatas e formas não-canônicas rejeitadas; allowed-delta por c14n integral + prolog/epilog + docinfo; pós-condição semântica.
- **Pipeline:** determinismo confirmado (duas execuções byte-idênticas); `exact`→revisão sem patch; `duplicate_target_property` vira `patch_rejected` gracioso (sem derrubar a sessão); `mirrorIndents` corrigido; Review DOCX marca só o primeiro run marcável (testado com primeiro run já destacado → marca o segundo).
- **Regressões:** P1/P2/P4 intactos; falha em documento sem `styles.xml` (`part_status 'unreadable'`) é **pré-existente e idêntica** para P2/P3/P4 — não é regressão do P3.