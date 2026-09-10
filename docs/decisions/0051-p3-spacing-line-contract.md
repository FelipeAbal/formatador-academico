# 0051: Contrato de P3 para `spacing.line`

**Status:** rascunho para auditoria externa  
**Branch de trabalho:** `implement-0051-p3-line-spacing`  
**Precedência:** este documento depende de 0048 e 0049. Ele não congela a implementação até que as perguntas abertas sejam respondidas.

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
  "rules": {
    "line_spacing": {
      "mode": "exact",
      "value": 1.5
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

A comparação entre o valor desejado e o observado deve ser semântica. P3 pode corrigir uma observação `atLeast` ou `exact` para o valor declarativo `auto` quando o resultado pós-patch satisfizer exatamente o contrato desejado.

## 5. Seleção do alvo

O alvo de P3 é o parágrafo físico representado por `w:p`.

Parágrafos que tenham `w:numPr` direto ou herdado ficam fora do slice executável. Essa exclusão deve produzir item de revisão com razão explícita e aparecer no relatório humano. Não pode ser tratada como ausência silenciosa de achado.

Parágrafos com `w:bidi` ativo também ficam fora deste slice, seguindo a fronteira definida em 0049 para propriedades de parágrafo direcionais.

## 6. Regras XML

### 6.1 Forma do parágrafo

`w:pPr`, quando existir, deve ser o primeiro filho de `w:p`.

Dentro de `w:pPr`, `w:spacing` deve ocupar sua posição canônica conforme `CT_PPr`, preservando a ordem dos demais elementos. A posição de `w:spacing` é anterior a `w:ind`.

A implementação deve rejeitar, em vez de normalizar silenciosamente:

- `w:pPr` duplicado;
- `w:spacing` duplicado no mesmo `w:pPr`;
- elementos fora da forma canônica já definida para o patcher;
- `w:line` sem a estrutura necessária para determinar seu significado;
- token de `w:lineRule` desconhecido;
- valor lexical não inteiro quando a forma OOXML exigir inteiro.

### 6.2 Mutação mínima

Ao corrigir P3, a implementação pode alterar apenas:

- `w:line`;
- `w:lineRule`;
- a criação de `w:pPr` ou `w:spacing`, quando ausentes.

Atributos de `w:spacing` relativos a `before`, `after`, `beforeLines`, `afterLines` e outros atributos não pertencentes a P3 devem ser preservados byte a byte sempre que a biblioteca permitir.

A forma canônica proposta para um múltiplo é:

```xml
<w:spacing w:line="360" w:lineRule="auto"/>
```

para `1.5` linhas, pois OOXML usa unidades de 240 avos de linha para `auto`.

A conversão deve ser exata: `multiple * 240` precisa resultar em inteiro sem arredondamento. O contrato deve estabelecer limites mínimo e máximo e a política para casas decimais excessivas.

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

## 8. Perguntas para auditoria do Claude Opus

1. A forma pública proposta para P3 deve usar `mode="exact", value=1.5`, com `rule="auto"` implícito, ou o schema deve expor explicitamente `rule="auto"`?
2. P3 deve aceitar somente `mode="exact"`, ou `allowed` e `preferred` devem ser mantidos para consistência com o formato genérico?
3. Quais limites e precisão decimal devem ser aceitos para o múltiplo de linha?
4. Como tratar `w:lineRule` ausente quando `w:line` está presente?
5. Como tratar `w:lineRule="auto"` sem `w:line`?
6. A rejeição de `w:spacing` duplicado e de atributos desconhecidos deve usar a razão de erro já congelada para propriedades não canônicas?
7. A exclusão de `w:numPr` e `w:bidi` está corretamente posicionada no slice P3, com item visível no relatório?
8. A preservação byte a byte de atributos não P3 é viável com o modelo XML atual, ou o contrato deve exigir apenas preservação semântica?
9. O pós-patch deve exigir sempre `lineRule="auto"` explícito, mesmo se uma biblioteca puder interpretar o default de outra forma?
10. Há algum ponto de 0049, da implementação de P4 ou do modelo `LineSpacing` que impeça esta forma de P3?

## 9. Testes mínimos antes de congelar

- Profile Input `0.3` aceita `line_spacing`.
- Profile Input `0.1` e `0.2` rejeitam `line_spacing`.
- Valor não múltiplo, negativo, zero ou fora dos limites é rejeitado.
- Analysis lê `auto`, `atLeast` e `exact`.
- Ausência e tokens inválidos permanecem não resolvidos.
- Patcher cria `pPr` e `spacing` na posição canônica.
- Patcher altera somente `line` e `lineRule`.
- Atributos `before` e `after` são preservados.
- Listas e bidi são relatados com razão explícita.
- Precondição, delta e pós-condição falham de forma determinística quando o XML muda.
- Transform Log contém valor observado e desejado.
- Review DOCX marca somente o primeiro run elegível.
- Suite completa e CI permanecem verdes.

## 10. Não objetivos

Este ciclo não implementa:

- `spacing.before`;
- `spacing.after`;
- alinhamento adicional além do P4 já integrado;
- itálico automático;
- suporte a listas;
- suporte a documentos bidi;
- conversão declarativa de pontos para múltiplos de linha;
- normalização geral de XML fora da mudança autorizada.
