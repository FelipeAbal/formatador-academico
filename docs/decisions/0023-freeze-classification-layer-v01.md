# 0023 — Freeze Classification Layer v0.1

## Status

**FROZEN**

A Classification Layer v0.1 — primeiro vertical slice (`body + heading + abstain`) — está implementada, auditada, mergeada e congelada.

## Implementação auditada

- PR: #6
- branch: `classification-v01-vertical-slice`
- base auditada: `d05cf0bd9b25d91c3602f8e7ea672be5c3d90ec5`
- head inicial auditado: `85d1eaa93d8c99640186656177d7514f560f368a`
- head final auditado: `94fb797fec1f44508274ec47ba87409da8e4537d`
- merge por squash: `736c33036224562549b1b5cb026bd6bfdfd2e112`

## Validação final

Suíte completa em clone fresco do head final:

- total: **335**
- passes: **335**
- failures: **0**
- errors: **0**
- skips: **0**

Regressões preservadas:

- parser v0.4: 102/102
- parser + Analysis v0.1a: 154/154
- Analysis completa: 267/267
- Decision Layer v0.1: 290/290
- novos testes Classification: 45

## Escopo congelado

Executável:

- `body`
- `heading`
- `abstained`
- `not_applicable`

No vocabulário, mas ainda não executáveis:

- `long_quote`
- `reference`

`unknown` não existe como `target_class`.

## Status e basis

ClassificationStatus:

```text
classified
abstained
not_applicable
```

ClassificationBasis:

```text
explicit
structural
heuristic
```

Elegibilidade automática é derivada:

```text
status == classified
AND basis in {explicit, structural}
```

Não existe confidence numérico nem `safe_for_automatic_use` redundante.

## Style identity map v0.1

Mapa executável congelado:

```text
Normal -> body
Heading1..Heading9 -> heading level N
```

`BodyText` não foi admitido por falta de evidência real suficiente no corpus disponível.

Regras:

- identidade usa `style_id` exato;
- `style_type` deve ser `paragraph`;
- `customStyle=true` impede identidade built-in direta;
- `style.name` sozinho nunca classifica;
- custom style pode classificar por cadeia `basedOn` válida que termine em identidade built-in reconhecida;
- cadeia que cruza style type, entra em ciclo ou aponta para referência ausente não classifica.

## Default paragraph style

Quando `pStyle` está ausente, o default paragraph style aplicável do StyleCatalog pode fornecer identidade positiva.

Esse sinal permanece congelado como `basis=explicit`, pois é declaração documental explícita do catálogo e é rastreado por evidence própria (`default_paragraph_style`).

## Body

Nunca é fallback residual.

Só é produzido com identidade positiva verificável de estilo + contexto permitido.

Documento sem identidade reconhecida deve poder produzir 100% abstention.

## Heading

`HeadingN` produz:

```text
target_class = heading
metadata.level = N
basis = explicit
reason = explicit_style_signal
```

Aparência tipográfica sem identidade não classifica heading.

## Contextos conservadores

- secondary stories -> `not_applicable / unsupported_story`;
- tabelas, células, nested tables e block containers -> `abstained / unsupported_context`;
- numbering warning -> `abstained / unsupported_context`;
- empty paragraph -> `abstained / empty_content`;
- empty_content tem prioridade sobre unsupported_context.

## Run inheritance

Runs não são classificados independentemente.

A classificação de parágrafo é projetada explicitamente para runs descendentes.

Regra de segurança congelada após auditoria:

- o `run.structural_path` deve ser descendente estrito do `paragraph_result.structural_path`;
- run de outro parágrafo é erro de contrato e nunca herda classe;
- prefixos irmãos (`/w:p[1]` vs `/w:p[12]`) não contam como parentesco;
- run herdado carrega path/hash próprios, `parent_anchor`, provenance `inherited_from_paragraph` e evidence própria apontando para a classificação do pai.

## basedOn type-boundary

Achado importante da auditoria: uma cadeia de paragraph style não pode atravessar um style de outro tipo e continuar até um built-in paragraph.

Regra congelada:

- qualquer hop `style_type != paragraph` quebra a cadeia;
- resultado = não identificado / abstention;
- nunca há identidade além da fronteira de tipo.

## API congelada

A API pública permanece:

```text
classify_document(physical_ir, style_catalog)
project_run_classification(run, paragraph_result)
project_target_classification(result)
```

`classify_document` deriva Normalized Text e Formatting Analysis internamente usando as APIs públicas congeladas da Analysis.

Esta escolha foi auditada e aceita porque:

- a derivação é pura e determinística;
- usa as mesmas entradas (`PhysicalIR + StyleCatalog`);
- elimina risco de views externas dessincronizadas;
- não interpreta OOXML cru;
- não cria uma segunda semântica factual diferente;
- o mesmo input produz os mesmos fatos byte a byte.

Uma separação futura entre núcleo puro e helper orquestrador só é necessária se surgir ganho real de cache/reuso, não por elegância arquitetural.

## Projeção para Decision Layer

Somente resultados elegíveis projetam para `decision.TargetClassification`.

Provenance fechada:

```text
classification:direct
classification:inherited_from_paragraph
```

Abstained, not_applicable e heuristic não projetam.

## Invariantes congeladas

- `status == classified` IFF `target_class is not None`;
- classified exige evidence não vazia;
- inherited_from_paragraph exige target_type run + parent_anchor;
- metadata é imutável e determinística;
- modelos são frozen;
- sem dict/list mutável escondido;
- serialização determinística;
- sem live lxml;
- sem profile normativo;
- sem LLM/random/clock/locale;
- Classification não altera PhysicalIR/Analysis/StyleCatalog.

## E2E congelado

Fluxo comprovado sem `TargetClassification` manual:

```text
DOCX
-> Parser
-> Analysis
-> Classification(body)
-> TargetClassification
-> Decision
```

Cenário auditado:

- bold true vs false -> non_compliant / deterministic_change;
- font_size 11pt vs 12pt -> non_compliant / deterministic_change;
- spacing 1.5 vs 1.5 -> compliant / no_action;
- alignment both vs both -> compliant / no_action.

Também congelado:

```text
Heading1 -> classified heading -> level=1 -> projection paragraph/run
```

## Achados de auditoria incorporados antes do freeze

### Bloqueador corrigido

Parent/run binding ausente permitia herança silenciosa de classe estrangeira.

Correção: parentesco físico obrigatório por `structural_path` hierárquico.

### Importante corrigido

`basedOn` atravessava style-type boundary.

Correção: cadeia quebra em qualquer entry não-paragraph.

### Testes adicionados

- parent mismatch;
- prefix siblings;
- multi-hop basedOn;
- wrong-type hop;
- pStyle apontando para character style.

## Dívidas permitidas

Podem esperar:

- `long_quote` executável;
- `reference` executável;
- ClassificationHints/localização/renomeação de styles;
- `outlineLvl` factual;
- numeração estruturada;
- title/subtitle;
- short_quote/classes inline;
- LLM separado para abstentions;
- corpus real anotado de classificação;
- métricas de produção por classe;
- refinamento de cache/reuso de Analysis.

## Condições para reabrir

Só reabrir esta decisão se houver:

1. falha de teste congelado;
2. impossibilidade técnica demonstrada;
3. contradição com contrato congelado;
4. mudança explícita de escopo/produto;
5. novo risco de segurança classificatória.

## Próximo ciclo

A Classification Layer v0.1 está fechada para o slice contratado.

O próximo passo deve ser decidido em nova etapa arquitetural pequena, sem reabrir este freeze automaticamente.
