# Decisão 0049: Paragraph Target Enablement v0.1, com P4/alignment

**Status:** PROPOSTA PARA AUDITORIA  
**Data:** 2026-09-10  
**Depende de:** decisão 0048, Product Delivery / File Naming v0.1 - freeze  
**Auditoria prevista:** Claude Opus  
**Implementação:** ainda não autorizada

## 1. Objetivo

Habilitar a primeira operação executável em nível de parágrafo no pipeline, usando P4/alignment como carga inicial.

Esta decisão não implementa P3, spacing, itálico, citações, referências, listas, tabelas, containers ou alterações de estilos. O objetivo é validar os trilhos de parágrafo com uma propriedade escalar, de tokens fechados e sem conversão de unidades.

## 2. Princípios preservados

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

## 3. Entrada declarativa

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
        "preferred": "both"
      }
    }
  }
}
```

O conjunto declarativo deve ser fechado e explicitamente validado pelo Profile Input. O executor não pode aceitar token arbitrário recebido por JSON.

## 4. Escopo executável

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

## 5. Tokens e equivalências lexicais

Para o recorte P4:

- o texto é considerado LTR;
- documentos bidirecionais ficam fora do slice executável;
- `start` e `left` são tratados como equivalentes semânticos em texto LTR;
- `end` e `right` são tratados como equivalentes semânticos em texto LTR;
- a equivalência é uma normalização lexical do OOXML, não uma regra normativa de formatação;
- o valor declarado pelo usuário deve ser comparado após normalização;
- se os valores forem semanticamente equivalentes, não há achado nem patch;
- tokens fora do conjunto fechado são rejeitados ou encaminhados para revisão conforme a camada responsável;
- valores de orientação bidi, tokens especializados ou casos cuja direção não possa ser determinada não entram no slice executável.

O conjunto final de tokens aceitos deve ser enumerado no código e coberto por testes. Não é permitido usar comparação textual bruta quando a normalização LTR for aplicável.

## 6. Exclusões obrigatórias

O alvo não pode ser executado quando:

- o parágrafo tiver `w:numPr` direto;
- o parágrafo herdar `w:numPr` de estilo;
- o documento exigir resolução de `numbering.xml`;
- o parágrafo estiver em tabela ou container não incluído no slice;
- o parágrafo estiver sob `w:del` ou `w:ins`;
- o parágrafo estiver em story secundária;
- o documento for bidirecional ou tiver direção não resolvida;
- o alvo estiver fora de `word/document.xml`;
- houver drift entre o plano e o documento físico;
- `pPr` ou `jc` tiver forma física não canônica;
- o token não pertencer ao conjunto fechado;
- a pré-condição física não puder ser comprovada.

Toda exclusão deve gerar item de revisão com razão explícita. Nenhuma lista pode ser silenciosamente omitida. O relatório humano deve tornar visível que a cobertura foi reduzida pela exclusão.

## 7. Resolução da propriedade

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

## 8. Decisão e segurança

A matriz de decisão congelada permanece vigente:

- regra ausente: `preserve / rule_absent`;
- `preserve`: `containment`;
- valor ausente com regra ativa: `review / analysis_absent`;
- valor não resolvido, inválido ou ambíguo: `review`;
- regra `exact` satisfeita: nenhuma operação;
- regra `exact` divergente, com todas as pré-condições satisfeitas: `deterministic_change`;
- modo `set` sem escolha determinística: `human_choice` ou revisão, sem mutação.

A operação deve ser recusada quando houver qualquer dúvida sobre o alvo, o valor, a forma física, a herança relevante, a direção do texto ou a preservação dos demais campos.

## 9. Review DOCX

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

## 10. Camadas a emendar

A implementação deverá emendar formalmente, sem quebrar os contratos anteriores:

- Processing Session 0033: aceitar `target_type="paragraph"` para o binding previsto;
- Patcher 0029: habilitar `w:pPr` e `w:jc`, com `PPR_CANONICAL_ORDER` verificado contra ECMA-376;
- TransformLog 0031: aceitar `("paragraph", "P4", "alignment")`;
- Review DOCX 0037: aceitar item de parágrafo e aplicar a política do primeiro run marcável;
- Profile Input 0042: aceitar `alignment` em schema 0.2;
- demais camadas: preservar os contratos existentes e aceitar apenas a extensão estritamente necessária.

A constante de propriedades suportadas do Profile Input deve ter uma única fonte de verdade. O conjunto por versão não pode permanecer duplicado em `model.py` e `parser.py`.

## 11. Allowed delta

A mutação deve preservar todos os atributos e filhos de `w:pPr`, exceto a inserção ou alteração autorizada de `w:jc`.

O patcher deve comprovar:

- somente `word/document.xml` foi alterado;
- somente o parágrafo alvo foi alterado;
- nenhum atributo ou filho não autorizado foi removido;
- a posição de `w:pPr` e `w:jc` respeita o schema;
- a releitura do valor produz o mesmo valor semântico;
- o `physical_hash` do alvo é atualizado e registrado;
- a pós-condição do Analysis é satisfeita.

## 12. Testes mínimos

Antes do merge, a implementação deverá incluir:

- regra de alinhamento direto em parágrafo;
- alinhamento herdado de estilo;
- alinhamento herdado de `docDefaults`;
- cadeia `basedOn`;
- `w:pPr` ausente;
- `w:jc` ausente;
- forma não canônica rejeitada;
- lista com `w:numPr` não alterada e relatada;
- tabela e story secundária não alteradas;
- documento bidi não alterado e relatado;
- `start` equivalente a `left`;
- `end` equivalente a `right`;
- token não suportado;
- valor ausente;
- regra ausente;
- modo `preserve`;
- modo `set` não determinístico;
- parágrafo sob revisão;
- primeiro run marcável;
- nenhum run marcável;
- marca preexistente preservada;
- relatório JSON e Markdown coerentes;
- ProductOutputBundle com cinco arquivos;
- manifest com hashes e tamanhos corretos;
- segunda passada com zero operações;
- execução repetida determinística;
- suíte anterior integralmente verde.

## 13. Critérios de aceitação

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
