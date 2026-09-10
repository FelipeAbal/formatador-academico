# 0051: Contrato de P3 para `spacing.line`

**Status:** aprovado para implementação após auditoria Claude Opus  
**Branch de trabalho:** `implement-0051-p3-line-spacing`  
**Precedência:** este documento depende de 0048 e 0049. O contrato foi aprovado após os ajustes registrados em `docs/audits/auditoria_claude_opus_0051.md`.

## 1. Objetivo

Adicionar ao produto a propriedade executável de parágrafo `spacing.line`, permitindo corrigir a entrelinha declarada em múltiplos de linha, com `rule="auto"`.

O slice não inclui:

- `spacing.before` ou `spacing.after`;
- patching automático de itálico;
- altura fixa declarada em pontos;
- listas com `w:numPr`;
- documentos bidi com `w:bidi` ativo;
- inferência de valores ausentes ou inválidos.

A Analysis continua podendo observar formas existentes do OOXML que não podem ser declaradas pelo perfil, inclusive `atLeast` e `exact`.

## 2. Versão do schema

P3 introduz o schema de Profile Input `0.3`.

A compatibilidade é cumulativa e despachada pela versão declarada:

| Versão | Propriedades aceitas |
| --- | --- |
| `0.1` | `bold`, `font_size` |
| `0.2` | `bold`, `font_size`, `alignment` |
| `0.3` | `bold`, `font_size`, `alignment`, `line_spacing` |

Um perfil que declara `0.1` ou `0.2` e usa `line_spacing` deve falhar na validação. A aceitação de uma versão anterior não autoriza propriedades de versões posteriores.

A regra de evolução é uma versão por ciclo de propriedade executável. Versões anteriores continuam aceitas, quando seus conjuntos próprios de propriedades são respeitados.

## 3. Contrato declarativo

O perfil poderá declarar `line_spacing` apenas para múltiplos de linha. O valor semântico representa a quantidade de linhas desejada, por exemplo `1.0`, `1.5` ou `2.0`.

A proposta de representação interna é:

```text
target_type = paragraph
property_group = P3
property = spacing.line
value = LineSpacing(rule="auto", value=<multiple>, unit="multiple")
```

A entrada pública deve permanecer compatível com o formato de regras existente, que usa `mode`, `value`, `allowed` e `preferred`. A forma exata para representar o múltiplo precisa ser confirmada na auditoria. A proposta inicial é:

```json
{
  "schema_version": "0.3",
  "profile": { "id": "exemplo", "version": "1" },
  "rules": {
    "body": {
      "line_spacing": { "mode": "exact", "value": 1.5 }
    }
  }
}
```

Nesta proposta, o número é sempre um múltiplo de linha e `rule="auto"` é implícito. Não deve existir uma forma declarativa pública para `atLeast` ou `exact` em pontos.

Se `allowed` e `preferred` continuarem sendo aceitos pelo formato genérico, seus valores também devem ser múltiplos de linha. O contrato deve definir se a propriedade P3 permite somente `mode="exact"` ou se preserva os modos genéricos existentes com semântica específica.

## 4. Valor observado

A Analysis deve continuar lendo a informação efetivamente presente no documento:

- `w:lineRule="auto"` representa múltiplos de linha;
- `w:lineRule="atLeast"` continua sendo observado;
- `w:lineRule="exact"` continua sendo observado;
- a unidade observada deve permanecer distinguível de `multiple`, quando aplicável;
- ausência, token inválido ou valor lexical inválido não deve ser convertido em um valor presumido.

A comparação entre o valor desejado e o observado deve ser semântica. A mudança determinística só é autorizada quando a observação resolvida já tiver `rule="auto"`, `unit="multiple"` e valor válido. Observações `atLeast` e `exact` devem permanecer sem patch automático e exigir escolha humana, com `HUMAN_CHOICE` e razão explícita `human_choice_required`. O Patcher não deve ser usado como bloqueio tardio, pois uma rejeição nessa etapa derruba a sessão.

## 5. Seleção do alvo

O alvo de P3 é o parágrafo físico representado por `w:p`.

Parágrafos que tenham `w:numPr` direto ou herdado ficam fora do slice executável. Essa exclusão deve produzir item de revisão com razão explícita e aparecer no relatório humano. Não pode ser tratada como ausência silenciosa de achado.

As guardas de `w:numPr` e `w:bidi` não são herdadas da implementação de P4: precisam existir novamente na resolução do slot de spacing. Parágrafos com `w:bidi` ativo também ficam fora deste slice, com razão explícita própria ou reutilizada conforme o vocabulário congelado.

## 6. Regras XML

### 6.1 Forma do parágrafo

`w:pPr`, quando existir, deve ser o primeiro filho de `w:p`.

Dentro de `w:pPr`, `w:spacing` deve ocupar sua posição canônica conforme `CT_PPr`, preservando a ordem dos demais elementos. A posição de `w:spacing` é anterior a `w:ind`.

A implementação deve rejeitar, em vez de normalizar silenciosamente:

- `w:pPr` duplicado;
- `w:spacing` duplicado no mesmo `w:pPr`;
- elementos fora da forma canônica já definida para o patcher;
- token de `w:lineRule` desconhecido;
- forma lexical não suportada de `w:line`, incluindo unidades universais como `18pt`.

A ausência de `w:lineRule` com `w:line` presente usa o default `auto` definido pelo XSD, não uma inferência da aplicação. A ausência de `w:line` não deve ser convertida em zero: `w:lineRule` presente sem `w:line` é `UNRESOLVED` com razão explícita e não pode interromper a busca de valor herdado. O XSD também declara default lexical `0` para `w:line`, mas esse default não autoriza a aplicação a declarar uma entrelinha de zero.

### 6.2 Mutação mínima

Ao corrigir P3, a implementação pode alterar apenas:

- `w:line`;
- `w:lineRule`;
- a criação de `w:pPr` ou `w:spacing`, quando ausentes.

Após a mutação, todos os atributos de `w:spacing` fora de `{w:line, w:lineRule}` devem ter valor idêntico ao anterior, verificado por releitura. Isso inclui os atributos de `CT_Spacing` não pertencentes a P3, nominalmente `before`, `beforeLines`, `beforeAutospacing`, `after`, `afterLines` e `afterAutospacing`. A garantia é semântica e verificável, não uma expectativa condicional sobre a biblioteca.

A forma canônica proposta para um múltiplo é:

```xml
<w:spacing w:line="360" w:lineRule="auto"/>
```

para `1.5` linhas, pois OOXML usa unidades de 240 avos de linha para `auto`.

A conversão deve ser exata: `multiple * 240` precisa resultar em inteiro sem arredondamento. O cálculo deve usar aritmética inteira sobre `Decimal.as_tuple()`, sem multiplicação dependente do contexto global. O valor deve ser estritamente positivo, obedecer às constantes de precisão e expoente já existentes no Profile Input e ser rejeitado como `UnsupportedError` quando não couber em `ST_SignedTwipsMeasure`. Assim, `1.5`, `1.50` e `1.5e0` têm o mesmo valor canônico, enquanto `1.001` não é representável exatamente.

### 6.3 Precondição e pós-condição

A decisão deve registrar:

- valor observado;
- valor desejado;
- unidade e regra observadas;
- razão de exclusão, quando o parágrafo estiver fora do slice.

O patch só pode ser aplicado se a precondição observada permanecer válida. Após o patch, a validação deve confirmar que:

```text
observed.rule == "auto"
observed.unit == "multiple"
observed.value == desired.value
```

A validação de delta deve aceitar somente a mutação P3 prevista e a criação mínima de contêineres ausentes.

## 7. Relatório, Review DOCX e Transform Log

P3 deve seguir a mesma separação estabelecida para P4:

- o Analysis relata o alvo e o valor observado;
- o Processing Session decide a correção;
- o Patcher aplica somente a mudança autorizada;
- o Validation confirma a alteração;
- o Transform Log registra decisão, operação, valor anterior, valor posterior e razão;
- o Review DOCX localiza o achado sem tentar quantificá-lo.

Quando houver item de parágrafo no relatório, o Review DOCX deve marcar apenas o primeiro run marcável daquele parágrafo, em ordem de documento. A marca significa que existe informação para o alvo do parágrafo, não que aquele run seja necessariamente a propriedade que originou o achado. Achados de run e de parágrafo não precisam de distinção visual nesta etapa.

Se nenhum run for marcável, o resultado deve permanecer sem marca e conter `no_markable_run`.

## 8. Decisões fechadas após auditoria do Claude Opus

1. A entrada pública mantém `rule="auto"` implícito. O usuário declara múltiplos de linha, sem expor `lineRule`.
2. Os modos genéricos `exact`, `set` e `preserve` permanecem disponíveis. Todo valor usado por P3 deve ser um múltiplo positivo válido.
3. A conversão usa aritmética inteira exata sobre `Decimal.as_tuple()`. Valores não representáveis no limite de `ST_SignedTwipsMeasure` são `UnsupportedError`.
4. `lineRule` ausente com `line` presente usa o default `auto` do XSD. `lineRule` presente sem `line` é `UNRESOLVED` e não interrompe a cascata.
5. Unidades universais como `18pt` são válidas no OOXML, mas ficam fora da capacidade declarativa deste slice e devem ser tratadas como não suportadas.
6. `atLeast` e `exact` observados nunca são convertidos automaticamente para `auto`; seguem para escolha humana.
7. As guardas de numbering e bidi precisam ser implementadas no slot de spacing. Elas não são herdadas da resolução de alignment.
8. A preservação dos atributos não P3 de `w:spacing` é uma invariante verificada por releitura.
9. O XML escrito sempre contém `w:line` e `w:lineRule="auto"` explicitamente.
10. `NONCANONICAL_RUN_PROPERTIES` permanece por compatibilidade nesta versão, cobrindo também propriedades de parágrafo. O rename fica reservado a um bump futuro do Patcher.

## 9. Testes mínimos antes da implementação e da integração

- Profile Input `0.3` aceita `line_spacing`.
- Profile Input `0.1` e `0.2` rejeitam `line_spacing`.
- Valor não múltiplo, negativo, zero ou fora dos limites é rejeitado.
- Analysis lê `auto`, `atLeast` e `exact`.
- Ausência e tokens inválidos permanecem não resolvidos.
- Observações `exact` e `atLeast` não são alteradas e exigem escolha humana.
- `lineRule` sem `line` não mascara valor herdado.
- `w:line="18pt"` é tratado como não suportado, não como inválido.
- Patcher cria `pPr` e `spacing` na posição canônica.
- Patcher altera somente `line` e `lineRule`.
- Atributos `before`, `after` e os demais atributos não P3 são preservados por releitura.
- `1.5`, `1.50` e `1.5e0` produzem perfil e hashes idênticos.
- Listas e bidi são relatados com razão explícita também no slot de spacing.
- `w:mirrorIndents` em um parágrafo alvo não é falsamente rejeitado.
- Precondição, delta e pós-condição falham de forma determinística quando o XML muda.
- Transform Log contém valor observado e desejado.
- Review DOCX marca somente o primeiro run elegível.
- Suite completa e CI permanecem verdes.

## 10. Compatibilidade de razões e emendas de modelo

A razão machine-readable `NONCANONICAL_RUN_PROPERTIES` é mantida nesta versão por compatibilidade com o vocabulário fechado do Patcher, embora também cubra propriedades de parágrafo. Um rename para `NONCANONICAL_PARAGRAPH_PROPERTIES` fica reservado ao próximo bump do Patcher por outro motivo.

O modelo `LineSpacing` existente é suficiente. O modelo do Profile Input deve garantir que o valor declarado seja não nulo, estritamente positivo, `rule="auto"` e `unit="multiple"`. A validação correspondente também deve existir no ramo `spacing.line` de `_validate_rule_value`, para que a invariante não dependa apenas do parser.

## 11. Não objetivos

Este ciclo não implementa:

- `spacing.before`;
- `spacing.after`;
- alinhamento adicional além do P4 já integrado;
- itálico automático;
- suporte a listas;
- suporte a documentos bidi;
- conversão declarativa de pontos para múltiplos de linha;
- normalização geral de XML fora da mudança autorizada.
