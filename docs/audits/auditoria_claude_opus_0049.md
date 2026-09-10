Auditei a 0049 contra o código em `86e420e`. Confirmo antes de tudo o estado: CI run `34504152848` = `success`, e `git diff 565ab01..HEAD -- src/ tests/` está **vazio** — nenhum código de produção foi tocado, como você disse.

O contrato melhorou muito em relação ao que discutimos. As cinco escolhas de produto estão bem registradas e a §9 ficou exatamente certa. Mas há **três bloqueios** que impedem a implementação como está — todos por omissão, nenhum por erro de direção.

---

# Auditoria da decisão 0049

## Veredito: **APROVAR COM AJUSTES**

Nenhum achado exige mudar a direção do contrato. Três exigem preenchimento antes de autorizar código.

---

## 🔴 B1 — O exemplo JSON canônico do §3 é inválido contra o parser congelado

**[FATO]** O §3 traz:

```json
"alignment": { "mode": "exact", "preferred": "both" }

```

`profile_input/parser.py:78-82`:

```python
if "value" not in obj:
    _contract("exact_value_missing", "exact mode requires value")
if "allowed" in obj or "preferred" in obj:
    _contract("exact_shape", "exact mode accepts only value")

```

`preferred` pertence a `set`, nunca a `exact`. O `FormattingRule` congelado também rejeita `preferred` em `EXACT`. O exemplo que o contrato oferece como forma mínima seria recusado pelo próprio sistema.

**Gravidade:** é o exemplo que vai ser copiado — pelo implementador, pelos testes e pela futura documentação de usuário.

**Ajuste mínimo:** `{"mode": "exact", "value": "..."}`.

---

## 🔴 B2 — As doze exclusões do §6 não têm camada dona nem vocabulário de razão

**[FATO]** O §6 exige que *"toda exclusão deve gerar item de revisão com razão explícita"*. Mas os vocabulários que carregariam essa razão são **enums fechados e congelados**:

- `DecisionReason` (`decision/model.py:26-38`) — 12 valores, nenhum significa "fora do slice executável";
- `GateReason` (`safety_gate/model.py:54-72`) — 11 valores, e o próprio docstring diz: *"Any semantic change to a reason requires a SafetyGate version bump."*

Não existe hoje forma de dizer "este parágrafo foi excluído porque está em lista numerada". Os candidatos existentes seriam mentiras semânticas: `TARGET_TYPE_MISMATCH` e `CURRENT_VALUE_UNAVAILABLE` significam outra coisa.

Pior, as exclusões não são homogêneas — verifiquei que hoje elas se comportam de formas diferentes:

| Exclusão do §6 Mecanismo hoje Produz o quê  |                                                                                                   |                                          |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| `w:numPr` direto ou herdado                 | **nenhum** para alignment                                                                         | nada — a lacuna A1 da auditoria anterior |
| bidi                                        | **nenhum**                                                                                        | nada — ver I1                            |
| tabela / container                          | nenhum a montante; `_iter_paragraph_bindings` (`engine.py:85-107`) percorre `children` sem filtro | rejeição a jusante                       |
| story secundária                            | idem; o walk percorre **todas** as stories e partes                                               | rejeição a jusante                       |
| fora de `word/document.xml`                 | Patcher (`applicator.py`, `DOCUMENT_XML`)                                                         | rejeição a jusante                       |
| `w:del`/`w:ins`                             | Patcher / marcabilidade                                                                           | rejeição a jusante                       |
| drift, hash, forma não canônica             | Gate + Patcher                                                                                    | `gate_blocked` / `patch_rejected`        |

**[INFERÊNCIA]** "Rejeição a jusante" e "item de revisão com razão explícita" são coisas diferentes. A primeira produz `unapplied_changes` e status `quiescent_with_unapplied` — o sistema diz "eu queria mudar e não consegui". A segunda diz "eu nem deveria tentar aqui". Para uma lista numerada, a segunda é a verdade; a primeira é enganosa.

**Ajuste mínimo recomendado:** implementar as exclusões *de conhecimento* (numbering, bidi) **na Analysis**, seguindo o precedente que já existe no próprio arquivo. `analysis/formatting.py:373-374` já faz exatamente isso para indents:

```python
if level is doc_defaults and numbering_relevant:
    _warn(warnings, W_NUMBERING_PRESENT, "Indent slot ... may depend on numbering.xml ...")

```

com `R_NUMBERING_INDENT` devolvendo `ResolutionStatus.UNRESOLVED`.

Aplique o mesmo shape a `alignment`: `UNRESOLVED` + razão `numbering_alignment_unsupported` / `bidi_direction_unsupported`. A matriz congelada do 0020 então produz `unknown / review / analysis_unresolved` **sozinha**, sem tocar em `DecisionReason`, `GateReason`, Decision Layer ou Processing Session. Zero vocabulário novo.

As demais exclusões (tabela, story, `w:del`, drift) devem ser **identificadas com seu mecanismo atual** no contrato, não reescritas — e o §6 deve dizer qual delas produz revisão e qual produz `unapplied_change`, porque não são a mesma coisa no relatório.

---

## 🔴 B3 — A equivalência `start`/`left` não tem onde acontecer

**[FATO]** `analysis/formatting.py:434` resolve alinhamento com `_conv_token`, que devolve o `w:val` **bruto**. A comparação acontece em `decision/engine.py:130`:

```python
if observed == rule.expected:

```

Igualdade de string crua, numa camada **congelada em 0021**.

O §5 diz *"o valor declarado pelo usuário deve ser comparado após normalização"* mas não diz **onde**. As três possibilidades não são equivalentes:

1. **Analysis normaliza** `w:jc` na conversão, preservando o bruto em `FormattingEvidence.raw_value` — exatamente o que `Length` e `LineSpacing` já fazem (valor semântico derivado + `raw_value`/`raw_line` forenses). Decision fica intocada.
2. **Decision ganha comparação por slot** — emenda 0021, a camada mais sensível do sistema.
3. **Session pré-normaliza** antes de chamar `evaluate_target` — esconde semântica em orquestração.

**Recomendação: opção 1.** É a única com precedente no próprio código e a única que não abre um contrato congelado de decisão.

**Consequência que o contrato precisa absorver:** o §10 lista cinco camadas a emendar e **não inclui a Analysis (0018)**. Com B2 e B3, ela passa a ser a sexta — e, na verdade, a mais importante das duas primeiras entregas. A lista de emendas está incompleta.

---

## 🟠 I1 — A detecção de bidi não existe, e há uma armadilha com nome parecido

**[FATO]** `analysis/formatting_model.py:135` tem `bidi: ResolvedValue`, mas dentro de `LanguageSpec`, alimentado por `_LANG_SLOTS` (`formatting.py:442`): é o atributo `w:bidi` de **`w:lang`**, ou seja, a *tag de idioma* bidirecional do run (algo como `ar-SA`). **Não** é o `w:bidi` de `w:pPr`, que é o flag de direção do parágrafo.

O §6 exige excluir documentos bidirecionais. Nenhum modelo atual expõe essa informação — e existe um campo de nome idêntico que significa outra coisa e está a um autocompletar de distância.

**Ajuste mínimo:** o contrato deve dizer que a direção do parágrafo é lida do **raw property bag de** **`pPr`** (`w:bidi`), autorizar essa leitura explicitamente, e registrar em nota que `LanguageSpec.bidi` **não** é a fonte. Vale um teste que falhe se alguém ligar na fonte errada.

Vale também decidir o escopo: `w:bidi` é por parágrafo, mas o §6 fala em "documento bidirecional". São critérios diferentes — parágrafo a parágrafo é mais preciso e mais barato.

---

## 🟠 I2 — O §11 exige um campo que o TransformRecord não tem

**[FATO]** §11: *"o* *`physical_hash`* *do alvo é atualizado e registrado"*. `TransformRecord` (`transform_log/model.py:29-44`) tem 13 campos e **nenhum** guarda o hash do alvo após a mutação. `target_physical_hash_after` consta como dívida registrada no handoff, não como implementação.

**[INFERÊNCIA]** O que o Patcher de fato faz é *revalidar* o `physical_hash` **antes** de mutar (`applicator.py`, precondição 5). Escrever "atualizado e registrado" ou obriga a ampliar o TransformLog além da tupla de slice — expandindo o escopo de 0049 sem necessidade — ou é imprecisão de redação.

**Ajuste mínimo:** reescrever como "o `physical_hash` do alvo é revalidado imediatamente antes da mutação", e manter `target_physical_hash_after` como dívida.

---

## 🟠 I3 — O binding de parágrafo não é uma mudança de validação; é de fluxo

**[FATO]** `processing_session/engine.py:167-197`: o laço é run-cêntrico —

```python
for run in _iter_runs(paragraph):
    ...
    for rule_binding in matching:
        ...
        decisions.append(produced[0])

```

**[INFERÊNCIA]** Se um binding de parágrafo entrar nesse laço, ele será avaliado uma vez **por run**, produzindo N decisões idênticas. `ProcessingSessionResult.__post_init__` (`model.py`) então levanta *"final\_decisions must have unique canonical decision refs"* — e o produto inteiro cai.

O §10 descreve a emenda a 0033 como *"aceitar* *`target_type='paragraph'`* *para o binding previsto"*, o que soa como afrouxar uma validação. Não é: exige separar o laço em duas passagens — bindings de parágrafo uma vez por parágrafo, bindings de run uma vez por run.

**Ajuste mínimo:** dizer isso no §10, e incluir teste: paragrafo com 5 runs e regra de alinhamento → **exatamente uma** decisão.

---

## 🟠 I4 — O vocabulário declarável expõe token OOXML, contra o princípio do 0040

**[FATO]** O exemplo declara `"both"`. O contrato 0040 congelado diz explicitamente: *"O schema não expõe* *`P1`**,* *`P2`**,* *`target_type=run`**,* *`property_slot`**,* *`RuleBinding`**,* *`FormattingRule`**,* *`RuleRef`**,* *`path`* *ou outros detalhes internos."*

`both` é o token OOXML de justificado. Expô-lo ao usuário é a mesma categoria de vazamento que o 0040 fechou.

**Recomendação:** vocabulário user-facing fechado `{left, center, right, justify}`, mapeado pelo adapter para tokens OOXML — na mesma linha do mapeamento fechado `body.bold → target_class/aspect_id/property_slot` que já existe. Bônus: resolve o problema de `start`/`left` no nível declarativo, porque o usuário nunca escolhe entre os dois.

---

## 🟠 I5 — "token canônico" não está definido

**[FATO]** §4: `value: token canônico`. Não há definição de **qual** token é escrito no XML.

Quando o alvo precisa mudar de `start` para justificado, escreve-se `both`. Mas quando o destino é alinhamento à esquerda e o documento usa a família `start`/`end`, escreve-se `left` ou `start`?

Preservar o "dialeto predominante do documento" seria inferência — proibida. **Recomendação:** fixar um token de escrita por valor user-facing, escrito no contrato (`left`, `center`, `right`, `both`), e aceitar a inconsistência lexical resultante como consequência declarada e determinística.

---

## 🟡 Menores

- **M1** — `STRICT_W_NS` (`docx_parser.py:18`) está **definido e nunca usado** em nenhum lugar do `src/`. Antes de fundamentar o §5 na convivência entre dialetos, verifique empiricamente o que acontece com um pacote Strict: se ele não é sequer parseado, `start`/`end` só aparecem como tokens legais-porém-raros de documentos transitional, e a motivação da regra muda (continua correta, mas por outro motivo).
- **M2** — §5: *"tokens fora do conjunto fechado são rejeitados ou encaminhados para revisão conforme a camada responsável"* é ambíguo e mistura dois casos que precisam ser separados: **token declarado** fora do conjunto → erro de Profile Input; **token observado** fora do conjunto (`distribute`, `mediumKashida`, `numTab`, `thaiDistribute`, kashidas) → **sempre revisão, nunca erro** — é fato do documento, não do perfil.
- **M3** — Testes faltantes no §12: (a) perfil `schema_version 0.1` declarando `alignment` → rejeitado, citado no §3 mas ausente da lista; (b) `line_spacing` **não** aceito em 0.2; (c) parágrafo com achado de run *e* achado de parágrafo → uma única marca, sem dupla marcação; (d) equivalência não altera nada: documento com `start`, perfil declarando esquerda → **zero operações e** **`start`** **preservado no XML** (hoje a lista testa a equivalência, não a não alteração); (e) parágrafo com N runs → exatamente uma decisão (I3).

---

## Respostas diretas às suas cinco perguntas

**1. Coerência com o código atual** — boa no desenho, com três lacunas de coerência: B1 (exemplo inválido contra o parser), B3 (normalização sem camada) e I3 (o laço de decisões). O §10 subestima duas emendas e omite uma camada inteira.

**2. A ordem de** **`CT_PPr`** **foi corretamente prevista?** — **Prevista sim, especificada não.** O §4 e o §10 exigem `PPR_CANONICAL_ORDER` verificado contra ECMA-376, o que está certo, mas o contrato não traz a sequência. Como esse é o artefato de maior risco da implementação — erro de ordem gera DOCX inválido que abre em alguns leitores e não em outros —, a sequência esperada de `CT_PPrBase` é:

```
pStyle, keepNext, keepLines, pageBreakBefore, framePr, widowControl,
numPr, suppressLineNumbers, pBdr, shd, tabs, suppressAutoHyphens,
kinsoku, wordWrap, overflowPunct, topLinePunct, autoSpaceDE,
autoSpaceDN, bidi, adjustRightInd, snapToGrid, spacing, ind,
contextualSpacing, mirrorIndents, suppressOverlap, jc, textDirection,
textAlignment, textboxTightWrap, outlineLvl, divId, cnfStyle

```

e `CT_PPr` = essa sequência seguida de `rPr`, `sectPr`, `pPrChange`.

**Dois pontos que o contrato deve absorver:**

- `w:jc` fica **depois** de `spacing`, `ind` e `contextualSpacing` e **antes** de `textDirection`. Registre também a posição de `w:spacing` (antes de `ind`) desde já, para o ciclo P3 não repetir o trabalho.
- Note que **`w:bidi`** **está nessa mesma sequência** — o que confirma I1: a direção do parágrafo está disponível no raw bag de `pPr`, ao alcance da implementação, mas não modelada pela Analysis.

**Ressalva honesta:** essa sequência é a que eu tenho como correta, mas não a validei contra o XSD nesta sessão, e ela não deve ser aceita da minha palavra nem da de nenhum modelo. O projeto já fez a coisa certa uma vez — `xml_patch.py:36-49` documenta a ordem de `CT_RPr` com a citação do modelo de conteúdo. Faça igual: abrir `wml.xsd` do ECMA-376 Part 1, transcrever `CT_PPrBase`/`CT_PPr` e deixar a citação no comentário. É a única forma aceitável de fechar esse item.

**3. A equivalência lexical de** **`w:jc`** **está tecnicamente correta?** — **Correta, mas com as duas justificativas fundidas numa só, e isso atrapalha.** São coisas independentes:

- `start ≡ left` e `end ≡ right` é **alias lexical do OOXML**, verdadeiro **independentemente da direção do texto** — `left`/`right` existem por compatibilidade e mapeiam para `start`/`end`.
- A restrição a LTR não é necessária para a *equivalência*; ela é necessária porque o **token declarado pelo usuário tem significado visual**. Quem declara "esquerda" quer o texto encostado à esquerda; em parágrafo RTL, `start` renderiza à direita e a intenção é violada.

O §5 diz "`start` e `left` são equivalentes **em texto LTR**", o que sugere que a equivalência depende da direção. Não depende — a *intenção do usuário* depende. Separe as duas frases: uma sobre alias lexical (incondicional), outra sobre por que bidi sai do slice (semântica da declaração). Sem isso, alguém pode concluir que num documento LTR a checagem de bidi é dispensável, ou que a equivalência precisa ser recalculada por parágrafo.

**4. A marcação pelo primeiro run preserva o objetivo do Review DOCX?** — **Sim, e o §9 está bem escrito.** A sequência (ordem de documento → critérios de marcabilidade congelados → primeiro marcável → sem marca com razão se nenhum for) é determinística, respeita a política congelada e mantém a densidade visual proporcional ao número de achados. A frase que declara a mudança de referência da marca — de "informação sobre o run" para "informação sobre o alvo ao qual o run pertence" — é exatamente a emenda semântica que 0037 precisava e que eu havia pedido. Nada a corrigir aqui, exceto o teste (M3c) do parágrafo que tem achado de run **e** de parágrafo ao mesmo tempo.

**5. Risco novo antes da implementação** — o mais relevante é **I3**, porque é silencioso na leitura do contrato e fatal na execução: nada no §10 sugere mexer no fluxo de `_build_decisions`, e a implementação óbvia derruba o produto inteiro na primeira execução com regra de parágrafo. Depois dele, **B2**, porque é o achado com maior chance de virar improviso: sem vocabulário para "excluído do slice", a saída fácil é reciclar uma `GateReason` existente e registrar uma razão falsa no relatório.

---

## Ajustes que precisam entrar no contrato antes de autorizar código

1. corrigir o exemplo do §3 para `{"mode": "exact", "value": "..."}` **(B1)**;
2. atribuir camada dona a cada exclusão do §6, implementando numbering e bidi como `UNRESOLVED` na Analysis pelo precedente `R_NUMBERING_INDENT`, e distinguir quais exclusões produzem revisão e quais produzem `unapplied_change` **(B2)**;
3. fixar que a normalização de `w:jc` ocorre na Analysis, com o token bruto preservado em `FormattingEvidence.raw_value` **(B3)**;
4. **acrescentar Analysis (0018) à lista de camadas a emendar no §10** — consequência de B2 e B3;
5. declarar que a direção vem de `w:bidi` no raw bag de `pPr`, com nota de que `LanguageSpec.bidi` não é a fonte **(I1)**;
6. reescrever o §11 para "revalidado imediatamente antes da mutação" **(I2)**;
7. descrever a emenda a 0033 como separação do laço de decisões, não como afrouxamento de validação **(I3)**;
8. substituir o vocabulário declarável por `{left, center, right, justify}`, mapeado pelo adapter **(I4)**;
9. definir o token de escrita por valor user-facing **(I5)**;
10. separar token declarado de token observado no §5 **(M2)**;
11. acrescentar os cinco testes de M3;
12. transcrever `CT_PPrBase`/`CT_PPr` do `wml.xsd` para o contrato ou para o comentário do código, com citação, nos moldes de `xml_patch.py:36-49`.

Os itens 1 a 4 são bloqueantes. Do 5 ao 12 são ajustes de precisão que evitam retrabalho, mas não impedem começar se você preferir tratá-los no PR.

Quer que eu salve esta auditoria em `.md` também, no mesmo padrão da anterior?