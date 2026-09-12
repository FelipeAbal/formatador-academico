Fiz a conferência direta no XSD. Resultado: **a sequência prevista no contrato está correta, sem uma única divergência** — e a conferência produziu quatro achados novos que valem a pena entrar antes da implementação.

---

# Conferência de `CT_PPr` no `wml.xsd` + aprovação final da 0049

## 1. Método e proveniência

Não consegui a ZIP publicada pela ECMA diretamente. Usei **duas cópias distribuídas de forma independente** do `wml.xsd` da ISO/IEC 29500-4:2016 — que é a parte *Transitional*, correspondente ao namespace que este projeto de fato parseia (`docx_parser.py:17`):

| Fonte SHA-256                                                                 |                            |
| ----------------------------------------------------------------------------- | -------------------------- |
| `dolanmiu/docx`, `ooxml-schemas/ISO-IEC29500-4_2016/wml.xsd`                  | `cf90407251dff196…1111354` |
| cópia local, `skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/wml.xsd` | `c2dd9f61f892deae…d218cfd` |

Arquivos com hashes diferentes (formatação distinta), `targetNamespace` idêntico, e **sequências extraídas idênticas**.

**Validação do método:** extraí também `EG_RPrBase` e comparei com `RPR_CANONICAL_ORDER` (`patcher/xml_patch.py:42-49`) — os 39 elementos batem **na ordem exata**. Ou seja, o mesmo procedimento reproduz o resultado que vocês já haviam verificado à mão contra a especificação. Isso é o controle que dá confiança no restante.

## 2. Resultado: a hipótese do §11 está correta

`CT_PPrBase` é `xsd:sequence`, todos os filhos `minOccurs="0"`, **33 elementos**:

```
pStyle, keepNext, keepLines, pageBreakBefore, framePr, widowControl,
numPr, suppressLineNumbers, pBdr, shd, tabs, suppressAutoHyphens,
kinsoku, wordWrap, overflowPunct, topLinePunct, autoSpaceDE,
autoSpaceDN, bidi, adjustRightInd, snapToGrid, spacing, ind,
contextualSpacing, mirrorIndents, suppressOverlap, jc, textDirection,
textAlignment, textboxTightWrap, outlineLvl, divId, cnfStyle

```

`CT_PPr` é `xsd:extension base="CT_PPrBase"` acrescida de `xsd:sequence(rPr?, sectPr?, pPrChange?)`. Como extensão por sequência coloca a partícula da base primeiro, a ordem canônica completa é os 33 acima seguidos de `rPr, sectPr, pPrChange` — **36 posições, exatamente como o contrato previu**.

Podem promover o bloco do §11 de "hipótese de trabalho" a **ordem verificada**, com a citação da fonte no comentário do código, no padrão de `xml_patch.py:36-49`.

Confirmado de passagem: `w:jc` fica **depois** de `spacing`, `ind` e `contextualSpacing` e **antes** de `textDirection`; `w:spacing` fica logo antes de `ind` — o dado que o ciclo P3 vai precisar, já resolvido.

---

## 3. Quatro achados novos vindos da conferência

### 🟠 N1 — Existem **dois** tipos de `pPr`, e uma única tabela de ordem seria errada

O XSD mostra que o elemento `pPr` aparece com dois tipos distintos:

| Tipo Onde Conteúdo  |                                                        |                                            |
| ------------------- | ------------------------------------------------------ | ------------------------------------------ |
| `CT_PPr`            | `CT_P` — **só o parágrafo**                            | CT\_PPrBase + `rPr`, `sectPr`, `pPrChange` |
| `CT_PPrGeneral`     | `CT_Style`, `CT_PPrDefault`, `CT_Lvl`, `CT_TblStylePr` | CT\_PPrBase + **apenas** `pPrChange`       |

A 0049 só muta `pPr` de parágrafo em `document.xml`, então o tipo operante é `CT_PPr`. Mas uma constante genérica chamada `PPR_CANONICAL_ORDER`, se reaproveitada um dia para `pPr` de estilo, produziria posições válidas para `rPr`/`sectPr` que **não existem** naquele tipo.

**Ajuste:** o contrato deve nomear `CT_PPr` explicitamente e registrar que `CT_PPrGeneral` é outro modelo de conteúdo, fora do escopo. Sugiro que a constante se chame `P_PPR_CANONICAL_ORDER` ou carregue o tipo no comentário — o suficiente para que ninguém a reutilize por analogia num futuro ciclo de `styles.xml`.

### 🟢 N2 — Boa notícia: o padrão de canonicidade do `w:sz` **transfere** para `w:jc`

```xml
<xsd:complexType name="CT_Jc">
  <xsd:attribute name="val" type="ST_Jc" use="required"/>
</xsd:complexType>

```

Um único atributo, nenhum filho. Diferente de `w:spacing` (que confirmei ter os 8 atributos previstos — `before, beforeLines, beforeAutospacing, after, afterLines, afterAutospacing, line, lineRule`), o `w:jc` é isomorfo ao `w:sz`. A checagem existente

```python
if set(element.attrib) - {W_VAL} or _element_children(element): raise Reject(...)

```

pode ser reaproveitada **como está**. Isso confirma, agora com o schema na mão, que P4 era mesmo a carga certa para estrear os trilhos de parágrafo.

### 🟠 N3 — `val` é `use="required"`: `w:jc` sem `val` é forma inválida, não valor ausente

Como o atributo é obrigatório, um `<w:jc/>` sem `w:val` é schema-inválido. A implementação precisa tratá-lo como **forma física não canônica** (rejeição ordinária), e não como "propriedade ausente" — que levaria a Analysis a `ABSENT` e a Decision a `review / analysis_absent`, razão errada para o que de fato é um documento malformado.

Vale um teste dedicado; a lista do §12 tem "forma não canônica rejeitada", mas não cobre este caso específico.

### 🟠 N4 — `w:pPr` criado precisa ser o **primeiro filho** de `w:p`

```
CT_P = xsd:sequence( pPr?, EG_PContent* )

```

São duas regras de posicionamento diferentes, e o §11 hoje as funde em "a posição de `w:pPr` e `w:jc` respeita o schema":

1. `w:pPr`, quando criado, vai **antes de qualquer conteúdo** do parágrafo — antes de `w:r`, bookmarks, `w:hyperlink`, marcas de revisão;
2. `w:jc`, quando criado, vai na posição 27 da sequência de `CT_PPr`.

Separe as duas no contrato. A primeira é onde uma implementação apressada erra, porque `append` num `w:p` vazio funciona e num `w:p` com runs não.

---

## 4. 🔴 Defeito no arquivo do contrato

`docs/decisions/0049-...md` contém **cinco sequências** **`\n\n`** **literais** (barra invertida + n), nas linhas 120, 160, 226, 253 e 292. O efeito é que os títulos das seções **6, 7, 11, 12 e 13 não são títulos**: viraram texto colado no fim do parágrafo anterior. Só 8 dos 13 `##` renderizam.

O conteúdo está todo lá, mas o documento que governa a implementação está estruturalmente quebrado quando renderizado. Provavelmente escapou de um heredoc ou `sed` na integração. Correção trivial, mas precisa entrar antes do freeze.

---

## 5. Revisão dos doze ajustes

Confirmo, item a item, que todos foram incorporados — e alguns melhor do que eu havia pedido:

| # Ajuste Estado  |                                                                     |                                                                                                                                                                                                                                                                                                            |
| ---------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1                | exemplo `"value": "justify"`                                        | ✅                                                                                                                                                                                                                                                                                                          |
| 2                | camada dona por exclusão                                            | ✅ **acima do pedido** — o §6 separa Analysis de camadas posteriores, distingue `review` de `unapplied_change`, e ainda acrescenta a regra de parada: *"a implementação deve parar e abrir emenda específica, sem reutilizar uma razão falsa"*. Essa frase vale mais que o resto do parágrafo.              |
| 3                | normalização na Analysis com `raw_value` preservado                 | ✅                                                                                                                                                                                                                                                                                                          |
| 4                | Analysis 0018 no §10                                                | ✅                                                                                                                                                                                                                                                                                                          |
| 5                | `w:bidi` do raw bag, com a ressalva sobre `LanguageSpec.bidi`       | ✅ — e virou teste                                                                                                                                                                                                                                                                                          |
| 6                | §11 "revalidado antes da mutação" + dívida mantida                  | ✅                                                                                                                                                                                                                                                                                                          |
| 7                | duas passagens no Processing Session                                | ✅ — com o exemplo dos cinco runs                                                                                                                                                                                                                                                                           |
| 8                | vocabulário `{left, center, right, justify}`                        | ✅                                                                                                                                                                                                                                                                                                          |
| 9                | tabela de token de escrita                                          | ✅                                                                                                                                                                                                                                                                                                          |
| 10               | token declarado vs observado                                        | ✅ — e a lista dos seis tokens não declaráveis (`distribute`, `mediumKashida`, `lowKashida`, `highKashida`, `thaiDistribute`, `numTab`) confere **exatamente** com a enumeração `ST_Jc` do XSD, que tem 12 valores: esses seis, mais `start/left`, `end/right`, `center` e `both`. Nada sobra e nada falta. |
| 11               | testes acrescentados                                                | ✅                                                                                                                                                                                                                                                                                                          |
| 12               | sequência de `CT_PPrBase` no contrato com status epistêmico correto | ✅                                                                                                                                                                                                                                                                                                          |

Um ponto de precisão que sobrou do #8/#9: a tabela de escrita (`left`, `center`, `right`, `both`) é implicitamente **também** o alvo da normalização da Analysis — é o que faz `end`→`right` encontrar `right` declarado, e `justify`→`both` encontrar `both` observado. O contrato deixa isso implícito em duas seções. Nomeie o conjunto uma vez, como conjunto canônico único de comparação e de escrita, para que ninguém implemente a normalização com um alvo e a escrita com outro.

---

## 6. Veredito

# ✅ APROVADO para implementação

A 0049 está tecnicamente sólida. A ordem de `CT_PPr` está verificada contra o XSD por duas cópias independentes, com o método validado contra o `CT_RPr` que vocês já haviam conferido. Não encontrei risco novo de perda de informação, de autoridade normativa indevida ou de quebra de contrato congelado.

Condiciono a aprovação a **cinco correções pontuais**, todas de redação — nenhuma altera o desenho:

1. corrigir as cinco `\n\n` literais que quebram os títulos das seções 6, 7, 11, 12 e 13;
2. promover o bloco de `CT_PPrBase` de "hipótese de trabalho" a ordem verificada, citando ISO/IEC 29500-4:2016 `wml.xsd`, `CT_PPrBase` + `CT_PPr`, no padrão do comentário de `CT_RPr`;
3. nomear `CT_PPr` explicitamente e registrar `CT_PPrGeneral` como modelo distinto e fora de escopo **(N1)**;
4. separar as duas regras de posicionamento — `w:pPr` como primeiro filho de `w:p`, `w:jc` na posição 27 de `CT_PPr` — e acrescentar o teste de `w:jc` sem `w:val` como forma não canônica **(N3, N4)**;
5. nomear uma única vez o conjunto canônico `{left, center, right, both}` como alvo comum de normalização e escrita.

Feito isso, podem abrir a branch. As duas coisas que eu vigiaria durante a implementação são as que continuam sendo silenciosas na leitura do contrato: a separação das duas passagens no `_build_decisions` e a tentação de reciclar uma `GateReason` existente para uma exclusão de slice — o §6 já proíbe, mas é a proibição que mais custa obedecer quando o teste está vermelho.

Quer que eu salve esta conferência em `.md` no padrão das anteriores, incluindo os hashes das cópias do XSD para o registro de proveniência?