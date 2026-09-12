# Auditoria Claude Opus: decisão 0051

**Data recebida:** 2026-09-10
**Objeto:** contrato P3 para `spacing.line`
**PR auditado:** #29, head `5bcdd52`
**Status do registro:** auditoria externa recebida e incorporada ao PR #29

> O texto abaixo foi fornecido pelo Felipe como resultado da auditoria do Claude Opus. Os ajustes derivados estão registrados em commits posteriores no mesmo PR.

Auditei o rascunho 0051 no head do PR #29 (`5bcdd52`) contra o código em `main` pós-P4. Antes das respostas, um achado que não é sobre a 0051 e que eu abriria como correção imediata.

---

# 🔴 Achado independente: defeito em produção no `PPR_CANONICAL_ORDER`

Reexecutei a extração do XSD contra a constante que o P4 mergeou. **Uma divergência em 36 posições:**

```
POS 24:  xsd='mirrorIndents'   code='mirrorInd'   <<< DIVERGÊNCIA
faltando no código: {'mirrorIndents'}   sobrando: {'mirrorInd'}

```

`patcher/xml_patch.py:43`. A ordem está certa; o **nome** está errado.

Consequência: `PPR_CANONICAL_RANK` ganha uma chave `{ns}mirrorInd` que nunca casa com nada, e `{ns}mirrorIndents` **fica fora da tabela**. Em `xml_patch.py:181-184`:

```python
rank = PPR_CANONICAL_RANK.get(child.tag)
if rank is None:
    raise Reject(PatchReason.NONCANONICAL_RUN_PROPERTIES, f"...outside canonical rank table: {child.tag}")

```

Qualquer parágrafo que declare `w:mirrorIndents` — legítimo, comum em documentos com margens espelhadas — é **falsamente rejeitado como não canônico**.

O comportamento é fail-safe: rejeita em vez de corromper, e como o resto da ordem está correto as posições de inserção continuam válidas. Mas é redução silenciosa de cobertura em código já mergeado, e é exatamente o risco de transcrição manual que motivou a conferência no XSD. Recomendo corrigir antes de começar o P3, com um teste que compare a constante contra o XSD programaticamente em vez de por inspeção.

---

# Auditoria adversarial do contrato 0051

## Estado verificado

PR #29 aberto, `mergeable`, 200 linhas adicionadas, **apenas o documento** — nenhum código tocado, como você disse. Base: `562d206`, com P4 integrado.

---

## 🔴 B1 — O exemplo JSON do §3 é estruturalmente inválido

```json
{
  "schema_version": "0.3",
  "rules": { "line_spacing": { "mode": "exact", "value": 1.5 } }
}

```

Dois erros contra o schema congelado:

1. **falta o bloco** **`profile`** — `{id, version}` são obrigatórios;
2. **falta o nível** **`target_class`** — a forma é `rules → body|heading → propriedade → regra`. O exemplo declara `line_spacing` como se fosse uma classe.

O correto:

```json
{
  "schema_version": "0.3",
  "profile": { "id": "exemplo", "version": "1" },
  "rules": { "body": { "line_spacing": { "mode": "exact", "value": 1.5 } } }
}

```

**Meta-observação, e é a parte que importa:** é a **terceira vez** que um exemplo JSON de contrato sai inválido — 0040 (`preferred` em `exact`), 0049 (idem), agora 0051 (estrutura). O padrão indica que o modo de escrita dos contratos não tem realimentação do parser.

**Recomendação permanente:** um teste que extraia todo bloco \`\`\`json de `docs/decisions/*.md` e o passe pelo `parse_profile_input_json` real, exigindo sucesso ou o erro declarado. Barato, roda no CI, e teria pego os três.

---

## 🔴 B2 — O §4 autoriza converter `atLeast`/`exact` em `auto`, e não existe freio a jusante

O §4 diz: *"P3 pode corrigir uma observação* *`atLeast`* *ou* *`exact`* *para o valor declarativo* *`auto`**"*.

Isso é **mudança de espécie, não de grau**. `exact` fixa a altura da linha: texto que não cabe é cortado. `auto` escala com a fonte. Converter troca o modelo tipográfico do parágrafo — pode reflowar o documento e mudar a paginação. É plausível que `exact` seja decisão autoral deliberada (caber numa célula, respeitar uma diagramação).

Pior: **o pipeline vai fazer isso sozinho, e não há onde bloquear.**

- `decision/engine.py:130` compara `observed == rule.expected`. `LineSpacing(rule="exact", value=18, unit="pt")` nunca é igual a `LineSpacingValue(rule="auto", value=1.5, unit="multiple")` → `differs_from_rule` → `deterministic_change`, automático, na camada congelada;
- bloquear no Patcher é **impossível**: `processing_session/engine.py:80-82`

```python
_IMPOSSIBLE_PATCH_REJECTIONS = frozenset(
    {PatchReason.SNAPSHOT_HASH_MISMATCH, PatchReason.UNSUPPORTED_OPERATION}
)

```

Uma rejeição `unsupported_operation` levanta `ProcessingSessionIntegrityError` e **derruba o produto inteiro**. `UNSUPPORTED_OPERATION` também não está em `_ALLOWED_PATCH_FINDING_REASONS`, então nem vira `SessionFinding`.

**Recomendação:** restringir a mudança determinística a `observed.rule == "auto"`. Observações `atLeast` e `exact` vão para **revisão**, pelo mesmo mecanismo que o P4 já usa: `UNRESOLVED` na Analysis com razão explícita (`line_rule_not_auto_unsupported`), produzindo `unknown / review / analysis_unresolved` pela matriz congelada, sem vocabulário novo.

O usuário continua sendo informado de que o parágrafo não está em 1,5 linhas — só não tem a troca de modelo feita em silêncio. É a aplicação direta de "na dúvida, marcar" e de "abstenção correta é sucesso seguro".

---

## Respostas aos seus sete pontos

### 1. Formato público de `line_spacing`

**Manter implícito. Não expor** **`rule`****.** É a mesma decisão que transformou `both` em `justify` na 0049, pelo mesmo princípio do 0040: o schema não expõe detalhes internos do OOXML. Expor `rule` convidaria a declarar `exact`, que está fora do slice — e nenhum usuário acadêmico pensa em `lineRule`; pensa em "1,5 linhas".

Um risco de uso que vale registrar: um usuário pode escrever `12` querendo 12 pt e receber 12 linhas. Não é resolvível no schema sem inventar normatividade; resolve-se na futura UI e no relatório humano, que deve imprimir a unidade por extenso. Vale ficar na seção de limitações.

### 2. `mode="exact"` ou `allowed`/`preferred`

**Manter os modos genéricos.** Restringir a `exact` seria o schema inventando uma limitação que a Decision Layer não tem, e `set` é caso real: normas que aceitam 1,5 **ou** duplo existem. `preserve` também precisa continuar disponível.

Com duas condições já estabelecidas: todos os valores de `allowed`/`preferred` são múltiplos de linha sujeitos à mesma validação de `exact`; e `allowed` de um único elemento sem `preferred` continua rejeitado, pela regra adotada na auditoria do 0040.

### 3. Limites e precisão dos múltiplos

Reaproveite o que já existe em `profile_input/model.py:14-17` — `MAX_DECIMAL_SIGNIFICANT_DIGITS = 32`, `MIN/MAX_DECIMAL_EXPONENT = ±16` — e acrescente a regra própria de P3:

- `multiple × 240` deve ser inteiro exato, calculado por **aritmética inteira** sobre `as_tuple()`, nunca por multiplicação `Decimal` sob o contexto global — a lição da errata 0041, que vale igual aqui;
- estritamente positivo;
- forma canônica de `Decimal` já aplicada pelo boundary, para `1.5`, `1.50` e `1.5e0` produzirem o mesmo perfil e os mesmos hashes;
- limite superior declarado e verificado contra o que o `w:line` comporta.

Do XSD: `w:line` é `ST_SignedTwipsMeasure`, e valor não representável deve ser **`UnsupportedError`**, não `ContractError` — é limite de executor, como ficou definido para `font_size`.

Múltiplos exatos são os de denominador que divide 240: `1.0`, `1.15`, `1.5`, `2.0` passam; `1.001` (=240,24) não.

### 4. Ausência ou invalidez de `w:lineRule` — e as duas perguntas do §8

**`lineRule`** **ausente com** **`line`** **presente (Q4): o código já está certo, e agora está provado.** O XSD:

```xml
<xsd:attribute name="lineRule" type="ST_LineSpacingRule" use="optional" default="auto"/>

```

`analysis/formatting.py:259` faz `rule = raw_rule or "auto"`. Isso é **default de schema, não inferência** — pode ser afirmado no contrato com a citação. `ST_LineSpacingRule` é fechado em `{auto, exact, atLeast}`, então não há superfície de token desconhecido além de lexema inválido.

**🟠** **`lineRule="auto"`** **sem** **`w:line`** **(Q5): aqui há um defeito real que o P3 ativa.**

`formatting.py:260`: `if raw_line is None: return LineSpacing(rule=rule, value=None, unit=None, ...)` — devolvido como **`RESOLVED`** **com** **`value=None`**. E `formatting.py:482` seleciona como alvo da cascata o primeiro `w:spacing` que tenha `w:line` **ou** `w:lineRule`:

```python
target = next((sp for sp in spacings if any(_attr(sp,a) is not None for a in slot_attrs)), None)

```

Ou seja: um `<w:spacing w:lineRule="auto"/>` direto, **sem** `w:line`, **interrompe a cascata** e mascara um `w:line` herdado do estilo. O sistema reporta "resolvido, sem valor" quando na verdade existe valor herdado que ele não foi buscar. Comparado contra o desejado, isso vira `deterministic_change` sobre uma observação falsa.

**Recomendação:** tratar `lineRule` presente sem `line` como **`UNRESOLVED`** com razão explícita, não como `RESOLVED(None)`. O XSD diz `w:line` tem `default="0"`, mas assumir 0 linhas seria pior. É o mesmo padrão de abstenção do resto do sistema.

**🟠 Terceiro caso, que o contrato não previu:** `ST_SignedTwipsMeasure` é `union(xsd:integer, ST_UniversalMeasure)` — `w:line="18pt"` é **schema-válido**. Hoje `_int_lexical` levanta `_InvalidLexical` → status `INVALID` + `W_INVALID_VALUE`. O sistema rotula como inválido um documento perfeitamente válido. Deve ser **não suportado** (unresolved), não inválido. O §6.1 do rascunho diz "valor lexical não inteiro quando a forma OOXML exigir inteiro" — a forma OOXML **não** exige inteiro; essa frase precisa ser corrigida.

### 5. Preservação dos demais atributos de `w:spacing` (Q8)

O §6.2 diz *"preservados byte a byte sempre que a biblioteca permitir"*. **Essa formulação não pode entrar num contrato de segurança** — transforma uma invariante em expectativa sobre lxml.

E é desnecessária: a preservação **é** verificável, e o P4 já provou o mecanismo. `validate_allowed_delta` opera sobre a releitura dos bytes; o Patcher muta só o elemento alvo e comprova o delta. Para P3 a invariante é enunciável de forma dura:

> Após a mutação, todos os atributos de `w:spacing` fora de `{w:line, w:lineRule}` — nominalmente `before`, `beforeLines`, `beforeAutospacing`, `after`, `afterLines`, `afterAutospacing`, confirmados como os 8 atributos de `CT_Spacing` no XSD — têm valor idêntico ao de antes, verificado na releitura.

Substitua "byte a byte sempre que a biblioteca permitir" por essa invariante e um teste que a exercite num `w:spacing` populado.

### 6. Exclusão de listas e bidi (Q7)

**Correta em princípio, mas o contrato assume herança que não existe.** O §5 diz que a exclusão segue "a fronteira definida em 0049". Verifiquei: o P4 implementou `R_NUMBERING_ALIGNMENT` e `R_BIDI_DIRECTION` **dentro da resolução de alignment** (`formatting.py:326-355`). `_resolve_spacing_slot` **não tem nenhuma dessas guardas**.

Nada é herdado. As duas exclusões precisam ser implementadas de novo no slot de spacing, com razões próprias (`numbering_spacing_unsupported`, e a de bidi reaproveitada ou análoga). Sem isso, um parágrafo de lista passa direto para `deterministic_change` — que é a lacuna A1 da primeira auditoria, reaparecendo num slot novo.

O §5 deve dizer isso explicitamente, para ninguém partir do pressuposto de que 0049 já cobriu.

### 7. Compatibilidade com o modelo `LineSpacing` existente (Q10)

**Boa notícia: o modelo está compatível e não precisa de tipo novo.**

| Camada Tipo Campos       |                    |                                         |
| ------------------------ | ------------------ | --------------------------------------- |
| Analysis                 | `LineSpacing`      | `rule, value, unit, raw_line, raw_rule` |
| Decision / OperationPlan | `LineSpacingValue` | `rule, value, unit`                     |

`safety_gate/gate.py:401-411` já projeta um no outro, descartando os campos forenses — implementado, congelado e testado desde o SafetyGate. `operation_plan/planner.py:61` já tipa `DecisionKey("paragraph","P3","spacing.line") → LineSpacingValue`. `decision/engine.py:60,73` já valida os dois lados. **O miolo do pipeline está pronto para P3 desde o começo.**

Duas ressalvas:

- `LineSpacingValue.value` e `.unit` são `| None`. Nada no dataclass impede um valor de regra com `value=None`. A garantia de `rule="auto"`, `unit="multiple"` e `value` não nulo tem de estar no **modelo do Profile Input**, pelo princípio já adotado de que invariante mora no modelo e não no parser;
- `processing_session/model.py:64-81` — `_validate_rule_value` cobre `bold`, `font_size`, `alignment` e **levanta para qualquer outro slot**. Precisa de um ramo `spacing.line` com essas três checagens. É emenda pontual a 0033, no mesmo padrão do P4.

---

## Achados menores

**🟠** **`NONCANONICAL_RUN_PROPERTIES`** **já mente no relatório (Q6).** O P4 usa essa razão para rejeições de `w:pPr` e `w:jc` (`xml_patch.py:172,175,184,186,202,204`). O nome diz "run properties" e o valor é machine-readable, indo para o Processing Report e o relatório humano. Para duplicatas, `DUPLICATE_TARGET_PROPERTY` está correta e já é aceita como razão de finding.

Como `PatchReason` é fechada e renomear exige bump de versão do Patcher, recomendo: **documentar agora** na 0051 que a razão cobre também propriedades de parágrafo, e acrescentar `NONCANONICAL_PARAGRAPH_PROPERTIES` no próximo bump que ocorrer por outro motivo. O que não vale é deixar implícito — P4 já embarcou assim.

**🟢 Q9 — pós-patch deve exigir** **`lineRule="auto"`** **explícito?** **Sim.** Custa um atributo, elimina qualquer dependência de como um consumidor trata o default, e torna a pós-condição verificável por releitura direta. Escreva sempre o par completo `(w:line, w:lineRule)`, como a auditoria anterior já recomendara para o risco C3.

**🟢 Q6, parte de duplicatas** — `w:pPr` duplicado e `w:spacing` duplicado: `DUPLICATE_TARGET_PROPERTY`, já congelada e já aceita em `_ALLOWED_PATCH_FINDING_REASONS`. Nada a criar.

---

## Veredito

# APROVAR COM AJUSTES

O desenho está certo: a propriedade certa, o recorte certo, o slice certo. O miolo do pipeline já suporta P3 desde o SafetyGate. Os problemas são de precisão do contrato e um deles é de comportamento — nenhum é de direção.

**Bloqueantes antes de congelar:**

1. corrigir `mirrorInd` → `mirrorIndents` em `xml_patch.py:43`, com teste que compare a constante contra o XSD programaticamente *(defeito em produção, independente da 0051)*;
2. corrigir o exemplo JSON do §3 — bloco `profile` e nível `target_class` — e adicionar o teste que valida todos os exemplos das decisões contra o parser real;
3. restringir a mudança determinística a `observed.rule == "auto"`; `atLeast` e `exact` vão para revisão via `UNRESOLVED` na Analysis, nunca via rejeição do Patcher, que é impossível por `_IMPOSSIBLE_PATCH_REJECTIONS`;
4. declarar que as guardas de numbering e bidi **não são herdadas** do P4 e precisam ser implementadas no slot de spacing.

**Ajustes de precisão:**

5. `lineRule` sem `line` → `UNRESOLVED`, não `RESOLVED(None)`, encerrando o mascaramento de valor herdado;
6. `w:line` em `ST_UniversalMeasure` (`"18pt"`) → não suportado, não inválido; corrigir a frase do §6.1 sobre "exigir inteiro";
7. substituir "byte a byte sempre que a biblioteca permitir" pela invariante verificada sobre os 6 atributos não-P3 de `CT_Spacing`;
8. fixar limites e precisão reaproveitando as constantes de `profile_input/model.py`, com `×240` por aritmética inteira exata e não representável como `UnsupportedError`;
9. manter os modos genéricos (`exact`/`set`/`preserve`) com validação de múltiplo em todos os valores;
10. manter `rule="auto"` implícito no schema público e sempre explícito no XML escrito;
11. acrescentar o ramo `spacing.line` em `_validate_rule_value` e as invariantes de `LineSpacingValue` no modelo do Profile Input;
12. registrar que `NONCANONICAL_RUN_PROPERTIES` cobre propriedades de parágrafo, com o rename previsto para o próximo bump do Patcher;
13. citar no contrato os defaults do XSD (`lineRule` default `auto`, `line` default `0`) como fonte da semântica de ausência.

**Testes que faltam no §9:** observação `exact`/`atLeast` não é alterada e vira revisão; `lineRule` sem `line` não mascara herança; `w:line="18pt"` tratado como não suportado; `w:spacing` com `before`/`after` populados preservado após o patch; parágrafo de lista e bidi no slot de spacing (não só no de alignment); `1.5`, `1.50` e `1.5e0` produzindo perfil e hashes idênticos; e `w:mirrorIndents` num parágrafo alvo deixando de ser falsamente rejeitado.

Quero registrar o que está bom, porque é bastante: a 0051 já nasce com as exclusões corretas, com o par `(line, lineRule)` tratado como indissociável, com a política de marcação do Review DOCX certa e com a separação de camadas do P4 preservada. Os quatro bloqueantes são preenchimento, não redesenho.

Salvo em `.md` no padrão dos anteriores, com os hashes do XSD e a saída do diff da constante?
