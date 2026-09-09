# 0040 — Profile Input / Form Schema v0.1 — contrato

**Status:** PROPOSTO — auditoria adversarial pendente antes da implementação.

## Contexto

O core congelado recebe `ProcessingProfile`, um agregado tipado interno. O produto, porém, foi concebido como **DOCX + formulário explícito de regras**. Falta uma fronteira user-facing que converta configuração declarada pelo usuário em `ProcessingProfile` sem criar normatividade, defaults silenciosos ou a promessa vaga de “conforme ABNT”.

Esta decisão define somente o primeiro schema de entrada e seu adapter determinístico. Não expande o slice automático congelado.

## Princípio central

> **Só existe regra quando o usuário a declarou explicitamente.**

Campo ausente nunca significa valor default, `false`, zero, “padrão acadêmico”, “ABNT”, herança de outra classe ou qualquer outra inferência normativa.

## Fronteira v0.1

Entrada pública canônica:

```text
profile JSON bytes
→ parse/validate Profile Input v0.1
→ deterministic adapter
→ ProcessingProfile
```

API conceitual:

```text
parse_profile_input_json(profile_json_bytes: bytes) -> ProfileInput
build_processing_profile(profile_input: ProfileInput) -> ProcessingProfile
```

Uma convenience API poderá compor ambas:

```text
processing_profile_from_json(profile_json_bytes: bytes) -> ProcessingProfile
```

A fronteira não recebe DOCX e não analisa documento.

## Formato user-facing v0.1

Exemplo:

```json
{
  "schema_version": "0.1",
  "profile": {
    "id": "revista-exemplo",
    "version": "2026-09"
  },
  "rules": {
    "body": {
      "bold": {
        "mode": "exact",
        "value": false
      },
      "font_size": {
        "mode": "exact",
        "value": 12
      }
    },
    "heading": {
      "bold": {
        "mode": "preserve"
      }
    }
  }
}
```

### Campos de topo

Obrigatórios e únicos:

```text
schema_version
profile
rules
```

Campos desconhecidos em qualquer nível são rejeitados no v0.1. O adapter não ignora extensões silenciosamente.

### `schema_version`

Valor exato:

```text
"0.1"
```

É versão do schema user-facing, distinta de `profile.version` e das versões internas do pipeline.

### `profile`

```json
{
  "id": "...",
  "version": "..."
}
```

Ambos obrigatórios, strings não vazias após validação lexical.

Não existe geração automática de `profile.id` ou `profile.version` no v0.1.

`profile.version` é a versão substantiva declarada do conjunto de regras. Mudança substantiva de regra deve implicar nova versão pelo produtor do perfil até existir fingerprint de conteúdo congelado.

## Vocabulário exposto v0.1

Classes:

```text
body
heading
```

Propriedades:

```text
bold
font_size
```

O schema não expõe `P1`, `P2`, `target_type=run`, `property_slot`, `RuleBinding`, `FormattingRule`, `RuleRef`, `path` ou outros detalhes internos.

Mapeamento fechado:

```text
body.bold      -> target_class=body,    target_type=run, aspect_id=P1, property_slot=bold
body.font_size -> target_class=body,    target_type=run, aspect_id=P2, property_slot=font_size
heading.bold      -> target_class=heading, target_type=run, aspect_id=P1, property_slot=bold
heading.font_size -> target_class=heading, target_type=run, aspect_id=P2, property_slot=font_size
```

Nenhuma outra classe/propriedade é aceita no v0.1.

## Semântica de ausência

### Classe ausente

Exemplo:

```json
{"rules": {"body": {...}}}
```

Ausência de `heading` = **nenhuma regra para heading**.

### Propriedade ausente

Exemplo:

```json
{"body": {"font_size": {...}}}
```

Ausência de `bold` = **nenhuma regra de bold para body**.

### Objeto `rules` vazio

Rejeitado no v0.1 porque produziria `ProcessingProfile.bindings` vazio, que é inválido no contrato congelado.

### Classe presente mas vazia

Rejeitada no v0.1 para evitar configuração aparentemente ativa que não produz autoridade alguma.

## Modos user-facing

O vocabulário público é:

```text
exact
set
preserve
```

Não expõe o termo interno `containment`.

### `exact`

```json
{"mode":"exact","value":...}
```

Significa valor único explicitamente requerido.

Mapeia para `RuleMode.EXACT`.

### `set`

```json
{
  "mode":"set",
  "allowed":[...],
  "preferred": ...
}
```

`allowed` é obrigatório, array não vazio e sem duplicatas semânticas.

`preferred` é opcional. Se presente, deve pertencer a `allowed`.

Sem `preferred`, mais de um valor permitido não autoriza escolha automática entre eles; o comportamento permanece o já congelado na Decision Layer (`human_choice` quando aplicável).

Mapeia para `RuleMode.SET`.

### `preserve`

```json
{"mode":"preserve"}
```

Não aceita `value`, `allowed` ou `preferred`.

Semântica user-facing congelada:

> **NÃO TOCAR + NÃO SINALIZAR por esta regra.**

Mapeia estritamente para `RuleMode.CONTAINMENT`, preservando a semântica já congelada de contenção.

`preserve` não significa “usar default”, “manter se conforme”, “ignorar erros do documento” ou “herdar outra regra”.

## Tipos e unidades

### `bold`

Valores válidos em `exact.value`, `set.allowed` e `set.preferred`:

```text
true | false
```

Somente JSON boolean real. `0`, `1`, `"true"`, `"false"`, `null` etc. são rejeitados.

### `font_size`

Unidade user-facing v0.1 é sempre **pt** e não é escrita no JSON.

Valores válidos:
- JSON number finito;
- estritamente positivo;
- convertido deterministicamente para `Decimal` sem passar por float binário;
- deve respeitar a representabilidade já exigida pelo slice mutável quando chegar ao Patcher (meio ponto exato); porém o adapter **não deve fingir que uma regra semanticamente válida é executável** se o valor não puder ser representado pelo Patcher atual.

Decisão v0.1 para evitar autoridade ilusória:

> `font_size` declarado no Profile Input v0.1 deve ser representável em meio ponto exato (`points * 2` inteiro) e dentro do domínio suportado pelo Patcher v0.1. Caso contrário, o perfil é rejeitado no input boundary.

Exemplos:

```text
12    -> válido
11.5  -> válido
11.25 -> rejeitado
```

O parser JSON deve usar `Decimal` diretamente para números decimais (por exemplo `json.loads(..., parse_float=Decimal, parse_int=Decimal)` ou mecanismo equivalente), nunca `Decimal(float)`.

Notação não finita (`NaN`, `Infinity`, `-Infinity`) é rejeitada.

## `null`

`null` nunca significa ausência normativa. Em qualquer campo de regra no v0.1, `null` é inválido.

Para “não declarar regra”, o campo deve estar ausente.

## IDs internos de regra

O usuário não fornece `rule_id` no v0.1.

O adapter gera deterministicamente um ID fechado a partir da identidade pública:

```text
v0.1:<target_class>:<public_property>
```

Exemplos:

```text
v0.1:body:bold
v0.1:heading:font_size
```

O ID não incorpora valor, ordem de entrada nem hash do documento.

`FormattingRule.path = None` no v0.1.

A mudança substantiva de valor fica vinculada pela `ProfileRef(profile.id, profile.version)`; por isso `profile.version` deve mudar quando a configuração substantiva muda.

## Ordenação e determinismo

Ordem das propriedades e classes no JSON não possui significado normativo.

O adapter deve produzir `ProcessingProfile` com bindings em ordem canônica independente da ordem de chaves do JSON.

Mesmo conteúdo semântico + mesmo `profile.id/version` deve produzir objeto e serialização interna equivalentes.

Não usar clock, UUID, random, locale, filesystem, rede ou LLM.

## Duplicidade de chaves JSON

**Obrigatório detectar e rejeitar duplicate object keys.**

JSON como:

```json
{"rules":{"body":{"bold":{...},"bold":{...}}}}
```

não pode ser aceito com política “last wins”. Ambiguidade na própria declaração normativa é contract error.

## Encoding

Entrada canônica v0.1: UTF-8 bytes.

- BOM UTF-8: rejeitado no v0.1 para manter uma forma canônica simples;
- bytes inválidos em UTF-8: contract error;
- trailing non-whitespace data: rejeitado;
- JSON top-level deve ser object.

## Validação estrutural

O parser deve distinguir:

```text
schema/contract error
unsupported schema vocabulary
```

mas ambos são falhas de entrada, nunca findings do documento.

O Profile Input boundary não gera `ReviewItem`, não modifica Processing Report e não tenta recuperar perfil malformado.

## Modelos públicos propostos

```text
PROFILE_INPUT_SCHEMA_VERSION = "0.1"

ProfileInput
  schema_version
  profile_id
  profile_version
  rules: tuple[ProfileInputRule, ...]

ProfileInputRule
  target_class
  property_name
  mode
  value | allowed | preferred
```

Modelos imutáveis e já canonicalizados.

Valores de `font_size` permanecem `Decimal` no modelo tipado.

## Error model

Base:

```text
ProfileInputError
```

Subclasses:

```text
ProfileInputContractError
ProfileInputUnsupportedError
```

### ContractError

Exemplos:
- JSON inválido;
- UTF-8 inválido/BOM;
- duplicate key;
- campo obrigatório ausente;
- campo desconhecido;
- tipo errado;
- null onde não permitido;
- array vazio/duplicado;
- preferred fora de allowed;
- classe vazia;
- rules vazio;
- font_size não finito/não positivo/não representável.

### UnsupportedError

Exemplos:
- `schema_version` diferente de `0.1`;
- classe fora de body/heading;
- propriedade fora de bold/font_size;
- mode fora de exact/set/preserve.

Não existe fallback de versão nem “best effort”.

Mensagens user-facing/localizadas ficam fora desta camada. Os erros devem possuir código estável machine-readable + mensagem técnica curta em inglês para debugging, se o modelo adotado suportar isso sem complexidade excessiva.

## Adapter para `ProcessingProfile`

Mapeamento deve ser mecânico e total para todo `ProfileInput` válido:

```text
ProfileInput profile_id/version -> ProfileRef
ProfileInputRule -> FormattingRule + RuleBinding
```

Regras:
- `exact` -> `RuleMode.EXACT`;
- `set` -> `RuleMode.SET`;
- `preserve` -> `RuleMode.CONTAINMENT`;
- `bold` mantém bool exato;
- `font_size` mantém `Decimal` em pontos;
- IDs internos conforme seção própria;
- `path=None`;
- nenhuma regra adicional é criada;
- nenhuma regra ausente é criada;
- nenhuma classe herda de outra;
- nenhum valor é lido do documento.

Após construir, o próprio `ProcessingProfile` congelado permanece como validação upstream adicional.

## Autoridade negativa

Profile Input / Form Schema v0.1 NÃO:
- interpreta “ABNT”, revista, evento, TCC ou instituição;
- consulta norma externa;
- sugere valores;
- preenche defaults;
- infere heading a partir de body ou vice-versa;
- analisa DOCX;
- decide conformidade;
- classifica conteúdo;
- cria OperationPlan;
- chama SafetyGate/Patcher;
- altera OOXML;
- gera relatório;
- gera UI visual;
- localiza mensagens;
- persiste perfis;
- resolve versionamento/fingerprint automaticamente.

É apenas um contrato de declaração explícita + adapter determinístico.

## Extensibilidade

O v0.1 é fechado por precisão, mas a forma `rules -> target_class -> property -> rule object` deve permitir adicionar futuramente novas propriedades/classes por nova `schema_version` ou extensão explicitamente versionada.

Não reservar comportamento semântico para campos desconhecidos.

P3/P4, italic, referências, citações, margens, etc. NÃO podem ser aceitos silenciosamente antes de contratos próprios.

## Integração futura com produto

Após congelado, uma camada superior poderá oferecer:

```text
DOCX bytes + Profile Input JSON bytes
→ parse profile
→ build ProcessingProfile
→ build_product_output_bundle(...)
```

Essa convenience boundary será ciclo separado. O schema 0040 não deve modificar `ProductOutputBundle` v0.1.

## Testes mínimos obrigatórios

### Parsing / estrutura
1. exemplo mínimo válido body.bold exact;
2. body.font_size exact;
3. heading válido;
4. body + heading;
5. ordem de chaves irrelevante;
6. invalid JSON;
7. invalid UTF-8;
8. BOM rejeitado;
9. top-level não-object;
10. trailing data;
11. duplicate top-level key;
12. duplicate nested property key;
13. campo top-level desconhecido;
14. campo de profile desconhecido;
15. campo de rule desconhecido;
16. profile.id ausente/vazio;
17. profile.version ausente/vazio;
18. rules ausente/vazio;
19. classe presente vazia;
20. classe desconhecida -> UnsupportedError;
21. propriedade desconhecida -> UnsupportedError;
22. schema_version desconhecida -> UnsupportedError.

### Ausência / autoridade
23. heading ausente gera zero binding heading;
24. bold ausente gera zero binding bold;
25. null não equivale a ausência;
26. nenhum default é criado;
27. body não herda heading nem vice-versa.

### Modes
28. exact shape válido;
29. exact com allowed/preferred rejeitado;
30. set non-empty válido;
31. set duplicate allowed rejeitado;
32. set preferred membro válido;
33. set preferred fora rejeitado;
34. preserve shape válido;
35. preserve com payload rejeitado;
36. mode desconhecido -> UnsupportedError.

### Tipos
37. bold true/false;
38. bold int/string/null rejeitados;
39. font integer -> Decimal exato;
40. font decimal -> Decimal exato;
41. 11.5 válido;
42. 11.25 rejeitado;
43. zero/negativo rejeitados;
44. NaN/Infinity rejeitados;
45. bool não aceito como number.

### Adapter
46. ProfileRef exato;
47. rule_id determinístico;
48. aspect/property mapping fechado;
49. preserve -> CONTAINMENT;
50. exact -> EXACT;
51. set -> SET;
52. path None;
53. binding ordering canônica;
54. mesmo conteúdo com ordem JSON diferente -> mesmo ProcessingProfile;
55. ProcessingProfile aceita todo ProfileInput válido.

### Static / determinismo
56. modelos frozen;
57. sem filesystem/network/clock/random/LLM;
58. repetição determinística;
59. regressão da suíte completa.

## Questões específicas para auditoria adversarial

Antes da implementação, auditar especialmente:
1. se `preserve` -> `CONTAINMENT` é semanticamente seguro e não confunde ausência;
2. se rejeitar `font_size` não representável no input boundary é correto ou mistura schema com capacidade atual do executor;
3. se `rule_id` determinístico sem valor é suficiente em conjunto com `profile.version`;
4. se duplicate-key rejection precisa valer em todos os níveis;
5. se erros `ContractError` vs `UnsupportedError` estão bem separados;
6. se schema fechado com unknown-field rejection é a melhor política para v0.1;
7. se parse_int=Decimal cria alguma armadilha de tipo/JSON;
8. se falta algum caminho pelo qual ausência/null/default possa gerar autoridade não declarada.

## Critério de aceite

Só implementar se a auditoria concluir que:
- ausência permanece ausência;
- todo binding interno possui origem explícita em uma regra user-facing;
- nenhuma declaração ambígua é silenciosamente resolvida;
- o adapter não introduz normatividade própria;
- o schema pode evoluir sem obrigar quebra dos contratos internos congelados.
