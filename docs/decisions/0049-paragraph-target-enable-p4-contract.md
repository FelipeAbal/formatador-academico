# Decisão 0049: Paragraph Target Enablement v0.1, com P4/alignment

**Status:** REVISADA APÓS AUDITORIA, PENDENTE DE APROVAÇÃO  
**Data:** 2026-09-10  
**Depende de:** decisão 0048, Product Delivery / File Naming v0.1 - freeze  
**Auditoria prevista:** Claude Opus  
**Implementação:** ainda não autorizada

## 1. Objetivo

Habilitar a primeira operação executável em nível de parágrafo no pipeline, usando P4/alignment como carga inicial.

Esta decisão não implementa P3, spacing, itálico, citações, referências, listas, tabelas, containers ou alterações de estilos. O objetivo é validar os trilhos de parágrafo com uma propriedade escalar, de tokens fechados e sem conversão de unidades.

## 2. Tipo XML abrangido

A operação desta decisão atua exclusivamente sobre o elemento `w:pPr` de parágrafo, cujo tipo no XSD é `CT_PPr`.

`CT_PPrGeneral` é um tipo distinto, usado em estilos, defaults, níveis de numeração e propriedades de estilo de tabela. Ele fica fora do escopo desta decisão. A ordem de `CT_PPr` não pode ser reutilizada por analogia para `pPr` de `styles.xml`, `numbering.xml` ou outros documentos.

## 3. Princípios preservados

- regras só existem quando declaradas explicitamente pelo usuário;
- nenhuma norma é inferida do conteúdo do documento;
- ausência de regra permanece ausência;
- ambiguidade não é resolvida em silêncio;
- o SafetyGate continua sendo veto, nunca autorização;
- a abstenção segura é resultado válido;
- o Review DOCX é instrumento de localização, não de quantificação;
- o ProductOutputBundle continua atômico;
- nenhuma camada posterior pode autorizar uma operação recusada;
- `styles.xml`, `numbering.xml`, settings e stories secundárias não são alterados.

## 4. Entrada declarativa

A propriedade `alignment` será aceita somente em `schema_version: "0.2"`.

A versão 0.2 é superconjunto estrito da versão 0.1:

- perfis 0.1 continuam válidos;
- perfil que declara `"0.1"` e usa `alignment` é inválido;
- o conjunto de propriedades aceitas é despachado pela versão declarada;
- propriedades desconhecidas continuam sendo rejeitadas;
- versões anteriores continuam aceitas;
- cada nova propriedade executável poderá gerar incremento de versão;
- P3 não será inserido antecipadamente na versão 0.2.

Forma mínima:

```json
{
  "schema_version": "0.2",
  "profile": {
    "id": "exemplo",
    "version": "0.1"
  },
  "rules": {
    "body": {
      "alignment": {
        "mode": "exact",
        "value": "justify"
      }
    }
  }
}
```

O conjunto declarativo deve ser fechado e explicitamente validado pelo Profile Input. O executor não pode aceitar token arbitrário recebido por JSON.

## 5. Escopo executável

Uma regra executável deve ter:

- `target_type="paragraph"`;
- `aspect_id="P4"`;
- `property_slot="alignment"`;
- classe `body` ou `heading`;
- modo `exact`, `set` ou `preserve`;
- valor pertencente ao conjunto fechado do contrato.

A única operação permitida é:

```text
SET_PROPERTY
target: parágrafo em word/document.xml
property: w:jc
value: token canônico
```

A operação pode criar `w:pPr` ou `w:jc` quando ausentes, desde que respeite a ordem canônica de `CT_PPr`. A operação não pode tocar qualquer outro filho ou atributo de `w:pPr`.

## 6. Tokens, vocabulário e equivalências lexicais

O vocabulário exposto ao usuário é fechado e não expõe tokens internos do OOXML:

```text
left
center
right
justify
```

O adapter converte esses valores para os tokens de escrita definidos abaixo. O conjunto canônico abaixo é a única referência comum para comparação semântica e escrita XML:

| Valor do perfil | Token escrito em `w:jc` |
|---|---|
| `left` | `left` |
| `center` | `center` |
| `right` | `right` |
| `justify` | `both` |

A Analysis normaliza o valor observado para o conjunto canônico abaixo antes da comparação, preservando o token físico bruto em `FormattingEvidence.raw_value`:

- `start` e `left` são aliases lexicais equivalentes do OOXML;
- `end` e `right` são aliases lexicais equivalentes do OOXML;
- a equivalência lexical não depende da direção do texto;
- a intenção visual de valores como esquerda e direita depende da direção;
- por isso, o recorte executável aceita apenas texto LTR;
- documentos bidirecionais ou com direção não resolvida ficam fora do slice;
- se o valor observado e o valor declarado forem semanticamente equivalentes, não há achado nem patch;
- o token físico original permanece preservado quando não há alteração;
- quando houver alteração, o token de escrita será o definido nesta tabela, sem tentar inferir o dialeto predominante do documento.

Token declarado fora do vocabulário acima é erro de Profile Input. Token observado fora do conjunto tratado pela Analysis, como `distribute`, `mediumKashida`, `lowKashida`, `highKashida`, `thaiDistribute` ou `numTab`, gera revisão, nunca erro de perfil.

A direção do parágrafo deve ser lida do atributo `w:bidi` no raw property bag de `pPr`. `LanguageSpec.bidi` não é essa fonte: ele se refere à informação bidirecional dentro da especificação de idioma do run e não à direção do parágrafo.

## 7. Exclusões obrigatórias e camada responsável

As exclusões precisam ser tratadas na camada que conhece a razão, sem reciclar enums fechados com significado diferente.

### Analysis

A Analysis deve produzir `UNRESOLVED` para:

- parágrafo com `w:numPr` direto ou herdado de estilo, quando a resolução depender de `numbering.xml`;
- direção `w:bidi` presente ou não resolvida;
- qualquer outra condição semântica que impeça declarar com segurança o alinhamento efetivo.

Esses estados devem usar a cadeia de evidência e as razões de análise já previstas para valores não resolvidos, com identificadores explícitos como `numbering_alignment_unsupported` e `bidi_direction_unsupported`. A matriz congelada de decisão produzirá revisão sem criar falsos significados em `DecisionReason` ou `GateReason`.

A Analysis 0018 deve ser emendada para:

- ler `w:bidi` no `pPr`, sem usar `LanguageSpec.bidi`;
- sinalizar a dependência de `numbering.xml` para alinhamento;
- preservar o token bruto observado em `FormattingEvidence.raw_value`;
- normalizar aliases lexicais antes da comparação;
- manter `atLeast` e `exact` como valores observados somente no futuro contrato P3, sem relação com P4.

### Processing Session e camadas posteriores

As seguintes condições são identificadas pelos mecanismos já existentes e não devem ser falsamente convertidas em razões de Analysis:

- tabelas e containers fora do slice;
- stories secundárias;
- alvo fora de `word/document.xml`;
- `w:del` e `w:ins`;
- drift e hash divergente;
- forma física não canônica.

O contrato deve distinguir:

- `review`: condição conhecida que torna a decisão insegura, com item de revisão e razão explícita;
- `unapplied_change`: decisão já produzida, mas operação recusada a jusante, com registro da recusa correspondente.

Nenhuma exclusão pode ser silenciosa. Parágrafos de lista e parágrafos com direção bidirecional devem aparecer no relatório humano como revisão, não como simples ausência de resultado.

A decisão 0049 não cria novos valores em `DecisionReason` ou `GateReason`. Se a implementação demonstrar que um caso não pode ser representado pelos contratos atuais, a implementação deve parar e abrir emenda específica, sem reutilizar uma razão falsa.

## 8. Resolução da propriedade

O Analysis continua sendo a fonte única da leitura do valor efetivo. A cadeia de evidência deve preservar se o valor veio de:

- propriedade direta;
- estilo;
- cadeia `basedOn`;
- `docDefaults`;
- ausência;
- estado não resolvido, inválido ou ambíguo.

A decisão compara a regra declarada com o valor efetivo resolvido pelo Analysis. Quando a operação for autorizada, o Patcher grava `w:jc` diretamente no parágrafo.

Não será feita mutação de `styles.xml`. O desacoplamento entre o parágrafo e o estilo de origem deve aparecer no Processing Report e no relatório humano quando o valor corrigido tiver sido herdado.

A resolução de `numbering.xml` não faz parte desta decisão. A exclusão de parágrafos com `w:numPr` é a barreira temporária adotada para evitar decisões baseadas em valor efetivo incompleto.

## 9. Decisão e segurança

A matriz de decisão congelada permanece vigente:

- regra ausente: `preserve / rule_absent`;
- `preserve`: `containment`;
- valor ausente com regra ativa: `review / analysis_absent`;
- valor não resolvido, inválido ou ambíguo: `review`;
- regra `exact` satisfeita: nenhuma operação;
- regra `exact` divergente, com todas as pré-condições satisfeitas: `deterministic_change`;
- modo `set` sem escolha determinística: `human_choice` ou revisão, sem mutação.

A operação deve ser recusada quando houver qualquer dúvida sobre o alvo, o valor, a forma física, a herança relevante, a direção do texto ou a preservação dos demais campos.

## 10. Review DOCX

A marca de um item de parágrafo terá semântica própria:

> o run marcado indica que existe informação no relatório sobre o alvo de parágrafo ao qual ele pertence.

O Review DOCX não distinguirá visualmente, por cor ou marca, achados de run e achados de parágrafo. Essa distinção ficará no relatório.

Para cada item de parágrafo:

1. percorrer os runs em ordem de documento;
2. aplicar os critérios de marcabilidade já congelados;
3. selecionar somente o primeiro run marcável;
4. inserir a marca nesse run;
5. preservar marcas autorais preexistentes;
6. se nenhum run for marcável, não inserir marca e registrar a razão.

Não marcar todos os runs do parágrafo. O objetivo do Review DOCX é localizar achados, e não pintar integralmente documentos com divergências gerais.

A emenda ao contrato Review DOCX deve registrar que a marca mudou de referência: de informação sobre o run para informação sobre o alvo ao qual o run pertence.

## 11. Camadas e fluxo a emendar

A implementação deverá emendar formalmente, sem quebrar os contratos anteriores:

- Analysis 0018: ler direção de `pPr/w:bidi`, sinalizar dependências de `numbering.xml`, preservar `raw_value` e normalizar aliases de `w:jc`;
- Processing Session 0033: separar duas passagens, avaliando cada binding de parágrafo uma vez por parágrafo e cada binding de run uma vez por run;
- Patcher 0029: habilitar `w:pPr` e `w:jc`, com `PPR_CANONICAL_ORDER` verificado contra ECMA-376;
- TransformLog 0031: aceitar `("paragraph", "P4", "alignment")`;
- Review DOCX 0037: aceitar item de parágrafo e aplicar a política do primeiro run marcável;
- Profile Input 0042: aceitar `alignment` em schema 0.2, usando uma única fonte para as propriedades suportadas por versão;
- demais camadas: preservar os contratos existentes e aceitar apenas a extensão estritamente necessária.

A mudança no Processing Session não é mero afrouxamento de validação. O fluxo precisa impedir que um binding de parágrafo seja avaliado dentro do laço de runs. Com um parágrafo de cinco runs e uma regra de alinhamento, deve existir exatamente uma decisão canônica para o parágrafo e não cinco decisões idênticas.

A Analysis deve ser a camada onde ocorre a normalização lexical. A Decision Layer continua comparando valores semânticos já normalizados, sem introduzir comparação especial para `w:jc`.

## 12. Allowed delta e precondições

A mutação deve preservar todos os atributos e filhos de `w:pPr`, exceto a inserção ou alteração autorizada de `w:jc`.

O patcher deve comprovar:

- somente `word/document.xml` foi alterado;
- somente o parágrafo alvo foi alterado;
- nenhum atributo ou filho não autorizado foi removido;
- `w:pPr`, quando criado, é inserido como primeiro filho de `w:p`, antes de qualquer run, bookmark, hyperlink ou marca de revisão;
- `w:jc`, quando criado, é inserido na posição correspondente da sequência de `CT_PPr`, depois de `spacing`, `ind` e `contextualSpacing`, e antes de `textDirection`;
- a posição de `w:pPr` e `w:jc` respeita o schema;
- a releitura do valor produz o mesmo valor semântico;
- o `physical_hash` do alvo é revalidado imediatamente antes da mutação;
- `target_physical_hash_after` continua sendo dívida registrada e não é adicionado ao TransformRecord nesta decisão;
- a pós-condição da Analysis é satisfeita.

A sequência de `CT_PPrBase` deve ser verificada diretamente contra o `wml.xsd` do ECMA-376 antes do merge. O comentário e a validação devem registrar a fonte da ordem, nos moldes da documentação já existente para `CT_RPr`. A sequência prevista para revisão é:

```text
pStyle, keepNext, keepLines, pageBreakBefore, framePr, widowControl,
numPr, suppressLineNumbers, pBdr, shd, tabs, suppressAutoHyphens,
kinsoku, wordWrap, overflowPunct, topLinePunct, autoSpaceDE,
autoSpaceDN, bidi, adjustRightInd, snapToGrid, spacing, ind,
contextualSpacing, mirrorIndents, suppressOverlap, jc, textDirection,
textAlignment, textboxTightWrap, outlineLvl, divId, cnfStyle,
rPr, sectPr, pPrChange
```

A sequência foi verificada contra duas cópias independentes do ISO/IEC 29500-4:2016, `wml.xsd`, nas definições `CT_PPrBase` e `CT_PPr`. O procedimento também foi conferido contra a ordem de `CT_RPr` já documentada no código. A implementação deve manter essa proveniência no comentário de `P_PPR_CANONICAL_ORDER`.

## 13. Testes mínimos

Antes do merge, a implementação deverá incluir:

- regra de alinhamento direto em parágrafo;
- alinhamento herdado de estilo;
- alinhamento herdado de `docDefaults`;
- cadeia `basedOn`;
- `w:pPr` ausente;
- `w:jc` ausente;
- forma não canônica rejeitada;
- `w:jc` sem o atributo obrigatório `w:val` é forma física inválida e deve ser rejeitado, não tratado como propriedade ausente;
- lista com `w:numPr` não alterada e relatada;
- tabela e story secundária não alteradas;
- documento bidi não alterado e relatado;
- direção lida de `pPr/w:bidi`, nunca de `LanguageSpec.bidi`;
- `start` observado equivalente a `left` declarado;
- `end` observado equivalente a `right` declarado;
- equivalência lexical produz zero operações e preserva o token físico original;
- vocabulário declarado aceita `justify` e mapeia para `both`;
- token OOXML observado não tratado gera revisão;
- token declarado não suportado é rejeitado no Profile Input;
- perfil `schema_version 0.1` que declara `alignment` é rejeitado;
- `line_spacing` não é aceito em schema 0.2;
- valor ausente;
- regra ausente;
- modo `preserve`;
- modo `set` não determinístico;
- parágrafo sob revisão;
- parágrafo com cinco runs produz exatamente uma decisão;
- parágrafo com achado de run e de parágrafo produz uma única marca;
- primeiro run marcável;
- nenhum run marcável;
- marca preexistente preservada;
- relatório JSON e Markdown coerentes;
- exclusão de lista e bidi aparece no relatório humano com razão explícita;
- ProductOutputBundle com cinco arquivos;
- manifest com hashes e tamanhos corretos;
- segunda passada com zero operações;
- execução repetida determinística;
- suíte anterior integralmente verde.

## 14. Critérios de aceitação

A decisão só poderá ser congelada após:

1. auditoria do Claude Opus;
2. implementação em branch própria;
3. PR com diff restrito ao escopo;
4. CI verde;
5. inspeção dos XMLs antes e depois;
6. conferência visual dos Review DOCX;
7. confirmação de que a suíte anterior não foi afrouxada;
8. atualização do handoff;
9. nova decisão de freeze.

Até lá, esta decisão é uma proposta de contrato e não autoriza alterações no código.
