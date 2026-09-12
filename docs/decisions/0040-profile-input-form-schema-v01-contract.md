# 0040 — Profile Input / Form Schema v0.1 — contrato

**Status:** ACEITO PARA IMPLEMENTAÇÃO — auditoria adversarial integrada; freeze somente após implementação + CI + auditoria final.

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
→ decode UTF-8 estrito
→ parse/validate Profile Input v0.1
→ deterministic adapter
→ ProcessingProfile
```

API conceitual:

```text
parse_profile_input_json(profile_json_bytes: bytes) -> ProfileInput
build_processing_profile(profile_input: ProfileInput) -> ProcessingProfile
processing_profile_from_json(profile_json_bytes: bytes) -> ProcessingProfile
```

A fronteira não recebe DOCX e não analisa documento.

## Formato user-facing v0.1

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

Campos de topo obrigatórios e únicos:

```text
schema_version
profile
rules
```

Campos desconhecidos em qualquer nível são rejeitados no v0.1. O adapter não ignora extensões silenciosamente.

## `schema_version`

Valor suportado:

```text
"0.1"
```

É versão do schema user-facing, distinta de `profile.version` e das versões internas do pipeline.

### Ordem obrigatória de validação

Para compatibilidade futura e erro determinístico, a ordem é congelada:

1. tipo externo deve ser `bytes` exato;
2. input não vazio e dentro do limite de tamanho;
3. rejeitar UTF-8 BOM;
4. `bytes.decode("utf-8")` estrito; **é proibido passar bytes diretamente a `json.loads`**;
5. JSON sintaticamente válido, sem constants não finitas e com duplicate-key rejection;
6. top-level deve ser object;
7. `schema_version` deve existir, ser string e ser avaliada **antes** de unknown-field/estrutura interna;
8. `schema_version != "0.1"` → `ProfileInputUnsupportedError`;
9. validar campos de topo/profile/rules;
10. validar classes em ordem canônica;
11. validar propriedades em ordem canônica;
12. validar rule object/mode/payload/tipos/capacidade.

Quando houver múltiplos erros, vale política **first-error deterministic**, conforme essa ordem e ordenação lexical canônica de classes/propriedades. O mesmo input inválido deve produzir sempre o mesmo código de erro.

## `profile`

```json
{
  "id": "...",
  "version": "..."
}
```

Ambos obrigatórios.

### Regras lexicais de `profile.id` e `profile.version`

- tipo string exato;
- comprimento entre 1 e 128 code points;
- não pode ter whitespace nas bordas;
- não pode conter caracteres Unicode de categoria `Cc` (controle);
- não pode conter surrogate code points U+D800–U+DFFF;
- não é feita normalização NFC/NFD/NFKC/NFKD: **a identidade é a sequência exata de code points declarada pelo usuário**;
- não existe geração automática.

Isso evita falha tardia de serialização UTF-8 e deixa explícito que formas Unicode visualmente equivalentes podem ser identidades diferentes.

`profile.version` representa versão substantiva declarada do conjunto de regras.

### Limitação conhecida de identidade

Até existir `profile content hash`, o sistema **não consegue detectar** que o produtor alterou valores/semântica sem mudar `profile.version`. Duas configurações substantivamente diferentes usando o mesmo `(profile.id, profile.version)` podem ficar indistinguíveis na provenance. Isso é dívida conhecida, não garantia do sistema.

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

O schema não expõe `P1`, `P2`, `target_type`, `property_slot`, `RuleBinding`, `FormattingRule`, `RuleRef` ou `path`.

Tabela fechada de mapeamento:

```text
public property | target_type | aspect_id | property_slot | unit
bold            | run         | P1        | bold          | boolean
font_size       | run         | P2        | font_size     | pt
```

`target_class` vem do caminho user-facing (`body` ou `heading`).

Nenhuma outra classe/propriedade é aceita no v0.1.

A unidade é definida **por propriedade** na tabela de mapeamento, não como política global. Em v0.1 apenas `font_size` usa `pt`.

## Semântica de ausência

- classe ausente = nenhuma regra para aquela classe;
- propriedade ausente = nenhuma regra para aquela propriedade;
- `null` nunca significa ausência;
- nenhuma classe herda regras da outra;
- nenhum default é criado.

`rules: {}` é rejeitado porque produziria `ProcessingProfile.bindings` vazio, inválido no contrato congelado.

Classe presente mas vazia também é rejeitada para não produzir configuração aparentemente ativa sem binding.

## Modos user-facing

Vocabulário público:

```text
exact
set
preserve
```

### `exact`

```json
{"mode":"exact","value":...}
```

Mapeia para `RuleMode.EXACT`.

Campos permitidos: exatamente `mode`, `value`.

### `set`

```json
{
  "mode":"set",
  "allowed":[...],
  "preferred": ...
}
```

- `allowed` obrigatório, array não vazio, sem duplicatas semânticas;
- `preferred` opcional e, quando presente, deve pertencer a `allowed`;
- sem `preferred`, mais de um valor permitido não autoriza escolha automática; permanece o comportamento congelado `human_choice` quando aplicável;
- `allowed` com **um único elemento e sem `preferred` é rejeitado como `ProfileInputContractError`**; usar `exact` ou declarar `preferred` explicitamente.

Mapeia para `RuleMode.SET`.

Nota: `bold` com `set.allowed=[true,false]` cobre todo o domínio observado; é permitido, mas em geral não autoriza mudança automática e pode gerar review quando Analysis estiver ausente. Não deve ser apresentado como garantia de conformidade.

### `preserve`

```json
{"mode":"preserve"}
```

Não aceita `value`, `allowed` ou `preferred`.

Mapeia estritamente para `RuleMode.CONTAINMENT`.

Semântica:

> **NÃO TOCAR + NÃO SINALIZAR por esta regra.**

### Limitação observável de `preserve`

No pipeline v0.1, `preserve` é **declarativo** e observacionalmente equivalente à omissão para os artefatos de produto:

- não produz transformação;
- não produz `AppliedChangeItem`;
- não produz `UnappliedChangeItem`;
- não produz `ReviewItem`;
- não produz highlight.

A diferença existe internamente em `final_decisions` (CONTAINMENT/PRESERVE), mas não no Processing Report v0.1.

Perfil somente com regras `preserve` é válido e pode terminar `quiescent` com clean/review byte-idênticos e report sem itens. **A camada de produto/UI não pode apresentar isso como evidência de conformidade.**

Não rejeitar perfil só-preserve: o boundary não decide “utilidade” da configuração.

## Tipos e valores

### `bold`

Valores válidos em `exact.value`, `set.allowed`, `set.preferred`:

```text
true | false
```

Somente JSON boolean real. `0`, `1`, strings, `null` etc. são `ProfileInputContractError`.

### `font_size`

User-facing v0.1: unidade `pt` implícita pela propriedade.

Valor válido no modelo:

- `Decimal` exato;
- finito;
- estritamente positivo;
- forma Decimal canônica;
- representável exatamente em half-points;
- dentro do domínio suportado pelo Patcher v0.1.

### Parse numérico

JSON deve usar:

```text
parse_float=Decimal
parse_int=Decimal
parse_constant=<raiser>
```

ou mecanismo semanticamente equivalente.

Nunca `Decimal(float)`.

`NaN`, `Infinity`, `-Infinity` nus são `ProfileInputContractError`.

### Canonicalização Decimal

O boundary deve canonicalizar numeric strings semanticamente equivalentes para a mesma representação `Decimal`, **sem depender do contexto Decimal global**.

Forma canônica v0.1:

1. partir de `Decimal.as_tuple()`;
2. rejeitar não finitos antes;
3. remover zeros finais do coeficiente enquanto ajusta o expoente exatamente;
4. zero canônico é `Decimal("0")`;
5. valores integrais canônicos não mantêm escala redundante (`12`, `12.0`, `1.2e1` → `Decimal("12")`);
6. `11.50` → `Decimal("11.5")`;
7. não usar `normalize()` nem aritmética sujeita ao `decimal.getcontext()` como fonte de verdade.

O mesmo valor semântico deve produzir o mesmo `ProcessingProfile`, Decision refs, report bytes e lineage, independentemente da forma lexical JSON.

### Limites de segurança numérica

Para evitar aritmética adversarial e dependência de contexto:

- máximo de **32 dígitos significativos** no literal numérico;
- expoente Decimal efetivo deve estar no intervalo `[-16, 16]` antes da validação de domínio;
- excedente → `ProfileInputUnsupportedError`.

Esses limites são de capacidade da versão, não validade normativa.

### Representabilidade exata em half-points

**É proibido validar com `d * 2` usando o contexto Decimal global/default.**

A representabilidade deve ser decidida por aritmética exata derivada de `Decimal.as_tuple()` (ou `localcontext` com precisão calculada a partir do próprio valor), provando que `2 * points` é inteiro sem arredondamento.

Exemplos:

```text
12    -> suportado
11.5  -> suportado
11.25 -> não suportado
```

Valor não representável ou fora do domínio do executor é `ProfileInputUnsupportedError`, não `ContractError`.

### Limite de domínio compartilhado

O Profile Input **não deve duplicar magic numbers** do Patcher. O limite superior deve vir de símbolo público compartilhado/exposto pela camada Patcher (ou por módulo comum de contrato de capacidade) e testes devem provar igualdade com a capacidade real do executor.

Até o símbolo público existir, a implementação desta etapa deve promovê-lo de forma aditiva, sem alterar a semântica congelada do Patcher.

## `null`

`null` nunca significa ausência normativa. Em qualquer campo de regra no v0.1 é inválido.

Para não declarar regra, omitir a propriedade.

## IDs internos de regra

O usuário não fornece `rule_id`.

O adapter gera:

```text
<target_class>:<public_property>
```

Exemplos:

```text
body:bold
heading:font_size
```

**Não incluir `schema_version` no `rule_id`.** A identidade da regra não deve mudar apenas porque o envelope user-facing evoluiu.

`target_class` é obrigatório no ID porque `RuleRef` congelado não o carrega.

O ID não incorpora valor, ordem de entrada nem hash do documento.

`FormattingRule.path = None` no v0.1.

Comparação cross-schema de uma regra semanticamente preservada pode continuar usando a identidade pública `target_class:property`.

## Ordenação e determinismo

Ordem das propriedades/classes no JSON não tem significado normativo.

`ProfileInput.rules` deve ser armazenado em ordem canônica:

```text
(target_class, property_name)
```

O adapter deve produzir bindings em ordem canônica independente da ordem das chaves.

Mesmo conteúdo semântico + mesmo profile id/version deve produzir objetos e serializações internas equivalentes.

O resultado e o **erro** devem ser independentes de:

- ordem de chaves JSON;
- `PYTHONHASHSEED`;
- `decimal.getcontext().prec` do chamador;
- clock/UUID/random/locale/filesystem/network/LLM.

## Duplicidade de chaves JSON

Duplicate object keys são `ProfileInputContractError` em **todos os níveis**:

- top-level;
- `profile`;
- `rules`/classe;
- rule object.

Nunca “last wins”.

## Encoding / tamanho / profundidade

Entrada pública aceita **somente `bytes` exato**.

`str`, `bytearray`, `memoryview` etc. → `ProfileInputContractError`.

- input vazio → ContractError;
- tamanho máximo: **256 KiB** no v0.1; excedente → ContractError;
- UTF-8 BOM → ContractError;
- decode UTF-8 estrito obrigatório;
- UTF-16/UTF-32 JSON válido → ContractError;
- trailing non-whitespace data → ContractError;
- top-level não-object → ContractError;
- `RecursionError`/profundidade patológica durante parse/validação → ContractError, nunca vazamento cru.

## Modelos públicos e invariantes

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

Modelos frozen.

### `ProfileInputRule.__post_init__`

Deve validar independentemente do parser:

- classe/propriedade suportadas;
- mode suportado;
- shape exato por mode;
- tipos estritos;
- `allowed` não vazio e sem duplicatas;
- preferred membro;
- singleton-set sem preferred rejeitado;
- `preserve` sem payload;
- `font_size` positivo, canônico, dentro dos limites e representável exatamente;
- valores armazenados em forma canônica.

### `ProfileInput.__post_init__`

Deve validar independentemente do parser:

- schema_version suportada;
- regras lexicais de id/version;
- `rules` tuple não vazio;
- todos os itens `ProfileInputRule`;
- unicidade de `(target_class, property_name)`;
- ordem canônica já materializada.

A API programática não pode criar estados que o JSON parser rejeitaria semanticamente.

## Error model

```text
ProfileInputError
ProfileInputContractError
ProfileInputUnsupportedError
```

Cada erro deve ter:

```text
code: string estável machine-readable
message: string técnica curta em inglês
```

### ContractError

Forma/declaração malformada:

- tipo externo não-bytes;
- input vazio/grande demais;
- JSON inválido;
- encoding/BOM inválido;
- duplicate key;
- campo obrigatório ausente;
- campo desconhecido;
- schema_version com tipo errado;
- tipo errado;
- `null` onde não permitido;
- array vazio/duplicado;
- preferred fora de allowed;
- singleton set sem preferred;
- classe vazia;
- rules vazio;
- mode ausente ou tipo não-string;
- profile id/version lexicalmente inválidos;
- non-finite constants.

### UnsupportedError

Declaração bem formada mas fora da capacidade/vocabulário desta versão:

- schema_version string diferente de `0.1`;
- classe fora de body/heading;
- propriedade fora de bold/font_size;
- mode string fora de exact/set/preserve;
- `font_size` finito/positivo mas não representável em half-points;
- `font_size` fora do domínio do Patcher;
- literal numérico excedendo limites de dígitos/expoente da versão.

Não existe fallback/best effort.

Mensagens localizadas/user-facing ficam fora desta camada.

## Adapter para `ProcessingProfile`

Mapeamento mecânico e total para todo `ProfileInput` válido:

```text
ProfileInput profile_id/version -> ProfileRef
ProfileInputRule -> FormattingRule + RuleBinding
```

- `exact` -> `RuleMode.EXACT`;
- `set` -> `RuleMode.SET`;
- `preserve` -> `RuleMode.CONTAINMENT`;
- bool permanece bool exato;
- font_size permanece Decimal canônico em pt;
- `rule_id = target_class:property_name`;
- `path=None`;
- nenhuma regra adicional/ausente é criada;
- nenhuma classe herda de outra;
- nenhum valor é lido do documento.

O `ProcessingProfile` congelado continua sendo validação upstream adicional.

## Autoridade negativa

Profile Input / Form Schema v0.1 NÃO:

- interpreta “ABNT”, revista, evento, TCC ou instituição;
- consulta norma externa;
- sugere valores;
- preenche defaults;
- infere regra ausente;
- analisa DOCX;
- decide conformidade;
- classifica conteúdo;
- cria OperationPlan;
- chama SafetyGate/Patcher;
- altera OOXML;
- gera relatório;
- gera UI;
- localiza mensagens;
- persiste perfis;
- calcula fingerprint de conteúdo.

É somente declaração explícita + adapter determinístico.

## Extensibilidade

A forma:

```text
rules -> target_class -> property -> rule object
```

permite adicionar propriedades/classes em nova schema_version sem reabrir contratos internos congelados.

- P3/P4: propriedades futuras podem mapear para `target_type=paragraph` pela tabela, sem expor target_type;
- italic: nova propriedade futura;
- valores compostos podem usar object como payload em schema futuro;
- heading-levels dependem de expansão upstream de classes;
- **margens/seções/configuração de página não pertencem a target_class e deverão usar chave irmã de `rules` em schema futuro**, não ser forçadas em `rules.body`.

Unknown-field rejection garante que nenhuma dessas extensões seja aceita antes de contrato explícito.

## Integração futura com produto

Ciclo separado poderá oferecer:

```text
DOCX bytes + Profile Input JSON bytes
→ parse profile
→ build ProcessingProfile
→ build_product_output_bundle(...)
```

0040 não modifica `ProductOutputBundle` v0.1.

## Testes mínimos obrigatórios

### API/encoding/JSON
1. bytes exatos aceitos;
2. str rejeitado;
3. bytearray/memoryview rejeitados;
4. input vazio rejeitado;
5. >256KiB rejeitado;
6. UTF-8 válido;
7. UTF-8 inválido;
8. BOM UTF-8 rejeitado;
9. JSON UTF-16 válido rejeitado;
10. JSON UTF-32 válido rejeitado;
11. invalid JSON;
12. top-level não-object;
13. trailing data;
14. NaN literal rejeitado;
15. Infinity/-Infinity literais rejeitados;
16. profundidade/RecursionError vira ContractError.

### Duplicate keys / estrutura
17. duplicate top-level;
18. duplicate dentro de profile;
19. duplicate class/property;
20. duplicate dentro de rule object;
21. unknown top-level field;
22. unknown profile field;
23. unknown rule field;
24. schema_version ausente;
25. schema_version tipo errado -> Contract;
26. schema_version string desconhecida -> Unsupported antes de unknown fields internos;
27. profile ausente/não-object;
28. profile.id/version ausentes;
29. rules ausente/não-object/vazio;
30. classe não-object;
31. classe presente vazia;
32. rule não-object;
33. mode ausente/tipo errado;
34. classe desconhecida -> Unsupported;
35. propriedade desconhecida -> Unsupported;
36. mode desconhecido -> Unsupported.

### Identidade lexical
37. id/version vazios;
38. leading/trailing whitespace;
39. control chars;
40. surrogate solto;
41. >128 code points;
42. NFC vs NFD não são normalizados silenciosamente.

### Ausência / preserve
43. heading ausente gera zero binding heading;
44. propriedade ausente gera zero binding;
45. null não equivale a ausência;
46. nenhum default;
47. body não herda heading;
48. preserve válido -> CONTAINMENT;
49. preserve com payload rejeitado;
50. perfil só-preserve válido;
51. perfil só-preserve → quiescent + clean/review idênticos + report sem itens;
52. preserve e omissão produzem mesmo ProcessingReport quando demais condições são iguais, embora final_decisions possam diferir.

### Modes
53. exact válido;
54. exact payload inválido;
55. set multi allowed válido;
56. duplicate semantic allowed rejeitado;
57. preferred membro válido;
58. preferred fora rejeitado;
59. singleton set sem preferred rejeitado;
60. singleton set com preferred válido;
61. bold set [true,false] comportamento documentado.

### Tipos / Decimal
62. bold true/false;
63. bold int/string/null rejeitados;
64. integer JSON -> Decimal canônico;
65. decimal JSON -> Decimal canônico;
66. `12`, `12.0`, `1.2e1` -> mesmo Decimal("12") e mesmo ProcessingProfile;
67. `11.50` -> Decimal("11.5");
68. 11.5 suportado;
69. 11.25 -> Unsupported;
70. zero/negativo -> Contract;
71. acima do domínio Patcher -> Unsupported;
72. literal com >32 dígitos -> Unsupported;
73. expoente fora [-16,16] -> Unsupported;
74. adversarial >28 dígitos que arredondaria no contexto default -> rejeitado/canonicalizado corretamente sem arredondamento;
75. contexto Decimal externo com prec baixo não altera resultado;
76. limite compartilhado com Patcher provado por teste.

### Model invariants
77. modelos frozen;
78. construção programática inválida é rejeitada;
79. ProfileInputRule canonicaliza/valida independentemente do parser;
80. ProfileInput exige rules em ordem canônica;
81. duplicate identity programática rejeitada.

### Adapter / IDs
82. ProfileRef exato;
83. rule_id body:bold;
84. rule_id heading:font_size;
85. rule_id não contém schema version;
86. mapping P1/P2 fechado;
87. unidade font_size pt;
88. exact -> EXACT;
89. set -> SET;
90. preserve -> CONTAINMENT;
91. path None;
92. bindings em ordem canônica;
93. mesmo conteúdo com ordem JSON diferente -> mesmo ProcessingProfile;
94. todo ProfileInput válido constrói ProcessingProfile.

### Determinismo / erros
95. repetição mesmo input -> mesmo objeto;
96. key order diferente -> mesmo objeto;
97. hashseed diferente -> mesmo resultado;
98. decimal context diferente -> mesmo resultado;
99. input inválido repetido -> mesmo error code;
100. múltiplos erros -> first-error determinístico;
101. sem filesystem/network/clock/random/LLM/dynamic import;
102. regressão suíte completa.

## Auditoria adversarial incorporada

A auditoria externa concluiu **APROVAR COM AJUSTES** e confirmou:

- ausência permanece ausência;
- `preserve -> CONTAINMENT` é semanticamente fiel;
- body/heading não herdam entre si;
- schema fechado/duplicate-key rejection/extensibilidade não exigem redesenho;
- nenhum upstream precisa ser expandido para autoridade normativa.

Foram incorporados os blockers de UTF-8 explícito, aritmética Decimal exata e canonicalização Decimal, além dos ajustes de error taxonomy, validação determinística, identidade lexical, self-validating models, rule_id cross-schema, preserve observacional e singleton set.

## Critério de aceite

Só congelar após implementação se:

- ausência permanecer ausência;
- todo binding interno tiver origem explícita numa rule user-facing;
- nenhuma declaração ambígua for resolvida silenciosamente;
- nenhuma aritmética Decimal depender do contexto global;
- valores semanticamente equivalentes forem canonicalizados antes de entrar no pipeline;
- erro/código forem determinísticos;
- modelos públicos se auto-validarem;
- Profile Input não introduzir normatividade própria;
- suíte completa e adversarial estiver verde.
