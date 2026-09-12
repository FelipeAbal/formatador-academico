# Decisão 0022 — Classification Layer v0.1 Contract

Status: **APPROVED FOR IMPLEMENTATION**

## Objetivo

Definir a camada determinística que transforma fatos documentais em classificação acadêmica de bloco, sem contaminar parser, Analysis View ou Decision Layer.

Pipeline:

```text
PhysicalIR
+ Normalized Text
+ Formatting Analysis / StyleCatalog
+ contexto estrutural/sequencial
-> Classification Layer
-> ClassificationResult
-> projeção segura para TargetClassification
-> Decision Layer
```

A Classification Layer NÃO:
- decide conformidade;
- consulta regra normativa do perfil como verdade classificatória;
- gera desired_value;
- cria OperationPlan;
- chama SafetyGate;
- altera DOCX/XML;
- interpreta OOXML cru por conta própria;
- usa LLM, probabilidade, random, relógio ou locale em runtime na v0.1.

## Princípio de segurança

Classificação errada pode autorizar formatação errada em cascata. Portanto:

**precision > coverage**.

Abstenção é resultado seguro e esperado. Body nunca é fallback residual.

## Unidade primária

O parágrafo é a unidade primária de classificação na v0.1.

Classes de bloco congeladas:

```text
body
heading
long_quote
reference
```

`unknown` NÃO é classe.

Runs não são classificados independentemente; recebem classe somente por projeção explícita da classificação do parágrafo pai.

## Taxonomia e heading level

Heading é representado por:

```text
target_class = heading
metadata.level = int | None
```

Não criar classes `heading_1`, `heading_2`, etc.

`level` só é preenchido quando houver evidência explícita suficiente. Heading pode ser classificado com `level=None`.

`reference` significa entrada individual da lista de referências. O cabeçalho da seção de referências continua sendo `heading`.

`long_quote` e `reference` entram no vocabulário v0.1, mas ficam fora do primeiro slice executável.

## ClassificationStatus

Conjunto fechado:

```text
classified
abstained
not_applicable
```

`ambiguous` não é status. Ambiguidade é razão de abstenção (`conflicting_evidence`).

Invariante:

```text
status == classified  IFF  target_class is not None
status != classified  IFF  target_class is None
```

Resultados `abstained` e `not_applicable` não podem ser projetados para `TargetClassification`.

## Classification basis

Conjunto fechado:

```text
explicit
structural
heuristic
```

Na v0.1, apenas `explicit` e `structural` podem ser elegíveis a uso automático.

Não criar campo separado `safe_for_automatic_use` nem eixo paralelo de confiabilidade.

Elegibilidade é função pura:

```text
eligible_for_automatic_use(result) =
    result.status == classified
    and result.basis in {explicit, structural}
```

`heuristic` fica reservado para extensão futura e não classifica automaticamente na v0.1.

Não usar confiança numérica.

## Modelo rico de output

Estrutura conceitual congelada:

```text
ClassificationResult:
    classification_version
    classification_vocabulary_version
    target_type
    structural_path
    physical_hash
    story_id
    status
    target_class
    metadata
    basis
    reasons
    evidence
    provenance
    parent_anchor
    classification_warnings
```

Modelos devem ser frozen, serializáveis e determinísticos, sem lxml vivo nem referências mutáveis à Analysis.

### Provenance

Vocabulário fechado inicial:

```text
direct
inherited_from_paragraph
```

Para runs herdados:
- `provenance = inherited_from_paragraph`;
- `parent_anchor = (structural_path, physical_hash)` obrigatório;
- `target_type = run`;
- a provenance não pode ser indistinguível de classificação direta.

Na projeção ao `TargetClassification` congelado em 0021, o campo `provenance: str | None` usa convenção fechada:

```text
classification:direct
classification:inherited_from_paragraph
```

A provenance completa permanece no modelo rico; não reabrir 0021.

## ClassificationEvidence

Estrutura conceitual mínima:

```text
ClassificationEvidence:
    source_kind
    source_ref
    feature
    observed_value
    polarity
    strength
```

`source_kind` inicial:

```text
physical_structure
normalized_text
formatting_analysis
style_catalog
sequence_context
```

`polarity`:

```text
supports
contradicts
```

`strength`:

```text
explicit
structural
weak
```

Evidência registra fatos observados, não conclusões. A conclusão fica em `target_class` + `reasons`.

Ordenação da evidence tuple deve ser determinística.

## Política de evidência

### Evidência de identidade — explicit

Pode classificar positivamente quando a identidade documental é verificável.

No primeiro slice, a principal fonte é estilo de parágrafo associado deterministicamente a classe por mapa versionado da Classification Layer.

### Evidência estrutural — structural

Contexto de story, ordem, contenção e seção pode qualificar, contradizer ou restringir.

Não deve ser confundido com aparência.

### Evidência de aparência — weak

Bold, centralização, font size, recuo, texto curto, caixa alta e demais aparências NÃO classificam sozinhos na v0.1.

Aparência pode estar errada — justamente o que o produto corrige.

## Mapa built-in style identity -> classe

O primeiro slice precisa de uma fonte forte e determinística de identidade. Congela-se a existência de um mapa versionado, mas com contenção estrita:

```text
classification_style_identity_version = "0.1"
```

O mapa opera sobre identidade documental verificável, não sobre mera semelhança de nome.

Regras:
- `Heading1`, `Heading2`, ... só podem mapear para `heading`/level quando a identidade do style for explicitamente verificável no StyleCatalog/cadeia `basedOn`;
- `Normal`/`BodyText` só podem mapear para `body` quando a identidade documental correspondente estiver presente e o contexto não estiver excluído pela política v0.1;
- nome de style custom como `Heading 1`, `Título 1`, `Cabeçalho 1`, `Normal` etc. NÃO é aceito por matching ad hoc;
- style custom sem cadeia verificável até identidade reconhecida NÃO classifica automaticamente;
- localização/renomeação de styles exigirá artefato futuro `ClassificationHints`, versionado e separado do perfil normativo;
- o classifier não pode inferir classe a partir de regras de formatação associadas ao style.

Esse mapa pertence à Classification Layer e deve ter testes próprios. Expansões são aditivas; renomeação ou mudança de significado exige nova versão.

## Body

`body` exige evidência positiva. Proibido qualquer fallback do tipo:

```text
if not heading and not quote and not reference:
    body
```

No primeiro slice, `body` requer identidade de style reconhecida como corpo + contexto permitido.

Contextos excluídos no slice 1:
- tabela/célula/block container;
- lista/numeration warning;
- story secundária;
- conteúdo vazio.

## Heading

No primeiro slice, `heading` exige identidade de style reconhecida como heading.

Cadeia `basedOn` pode fornecer identidade explícita quando resolve de forma determinística até style reconhecido.

Nível é metadata, não classe.

Formatting direta parecida com heading NÃO classifica.

## Long quote

Entra no vocabulário, mas NÃO no primeiro slice executável.

Recuo + fonte menor não é suficiente.

Ativação futura exige decisão formal de evidência mínima + avaliação em corpus anotado.

## Reference

Entra no vocabulário, mas NÃO no primeiro slice executável.

Cabeçalho `REFERÊNCIAS` = heading.

Entradas individuais dependem de contexto de seção e consistência estrutural; não implementar parser de referências na v0.1.

## Contexto sequencial

A API pública primária deve ser por documento/story, não parágrafo isolado.

Estrutura conceitual:

```text
ClassificationContext:
    story_id
    blocks
    containment
    section_state
```

`classify_paragraph` pode existir internamente como função pura, mas recebe contexto.

O estado de seção deve ser derivado deterministicamente e permanecer mínimo. Não criar máquina de estados acadêmica geral.

## API mínima

```text
classify_document(physical_ir, analysis_views, style_catalog)
    -> tuple[ClassificationResult, ...]

project_run_classification(run_ref, paragraph_result)
    -> ClassificationResult

project_target_classification(result)
    -> TargetClassification
```

`project_target_classification` só aceita resultado elegível para uso automático.

## Runs e mixed paragraphs

Run herda a classe estrutural do parágrafo, não semântica inline.

Citação curta, ênfase, links, markers e outros fenômenos inline ficam fora desta camada v0.1.

Run sem parágrafo classificável/classificado não recebe classe inventada.

## Stories, tables, lists, empty paragraphs

### Stories

Primeiro slice classifica apenas documento principal/body story.

Stories secundárias -> `not_applicable / unsupported_story`.

### Tables / block containers

Parágrafo dentro de tabela/célula/block_container -> `abstained / unsupported_context` no primeiro slice, mesmo se style parecer body/heading.

### Lists

Numeração estruturada ainda não existe como fato completo na Analysis. Quando houver `formatting_numbering_present`, o primeiro slice abstém (`unsupported_context`).

### Empty paragraphs

Parágrafo vazio ou sem conteúdo classificável -> `abstained / empty_content`.

Nunca herdar classe de vizinho por default.

## Inputs permitidos

- PhysicalIR congelada;
- Normalized Text v0.1a;
- Formatting Analysis v0.1b;
- StyleCatalog v0.1b;
- contexto estrutural/sequencial derivado deterministicamente desses fatos.

## Inputs proibidos

- perfil normativo/FormattingRule/ValidatedProfile;
- expected/allowed/preferred;
- OperationPlan/Decision/SafetyGate downstream;
- LLM/embeddings/modelos estatísticos;
- parsing OOXML cru ad hoc dentro do classifier;
- dicionário de style names vindo do perfil normativo.

## Missing facts / Analysis debts

Verificado e registrado:

1. `w:outlineLvl` não está exposto hoje como fato da Analysis;
2. numeração estruturada não está disponível, apenas warning de presença;
3. identidade built-in/localizada de style é parcialmente disponível via StyleCatalog, mas não existe ainda hints layer para nomes localizados/renomeados.

Essas dívidas NÃO bloqueiam o primeiro slice `body + heading + abstain`.

Se um fato físico necessário surgir no futuro:

```text
missing physical fact
-> expand Analysis View factual layer
-> Classification consome
```

Proibido o classifier contornar isso lendo OOXML cru.

## Reason codes v0.1

Classificação:

```text
explicit_style_signal
structural_context_signal
inherited_from_paragraph
```

Abstenção:

```text
insufficient_evidence
conflicting_evidence
empty_content
unsupported_context
```

Não aplicabilidade:

```text
unsupported_story
unsupported_target
parent_not_classified
```

`unsupported_class` não é reason; classe fora do vocabulário é erro de contrato.

## Prioridade de reasons concorrentes

Para o primeiro slice, congelar prioridade determinística:

1. `unsupported_story` / `unsupported_target` -> `not_applicable`;
2. `parent_not_classified` para run sem parent projetável -> `not_applicable`;
3. `empty_content` -> `abstained`;
4. `unsupported_context` -> `abstained`;
5. `conflicting_evidence` -> `abstained`;
6. `insufficient_evidence` -> `abstained`;
7. razões positivas só são consideradas se nenhum veto classificatório anterior se aplicar.

Isso significa, por exemplo, que style Heading dentro de tabela não classifica automaticamente no slice 1: `unsupported_context` prevalece.

## Warnings

Abstenção não é warning.

Warnings são reservados para anomalias de contrato/execução, como:
- anchor inconsistente;
- provenance quebrada;
- style reference dangling inesperada;
- erro interno de serialização/determinismo.

## Primeiro vertical slice executável

Implementar apenas:

```text
body
heading
abstain
```

`long_quote` e `reference` ficam fora do slice, embora pertençam ao vocabulário.

O slice deve provar:
- discriminação entre duas classes;
- ausência de fallback;
- abstention segura;
- heading level metadata;
- projeção paragraph -> run;
- projeção segura -> TargetClassification;
- E2E sem fixture manual de `target_class`.

## Fixtures mínimas obrigatórias

1. `Normal`/identidade body reconhecida -> body;
2. `Heading1` reconhecido -> heading level 1;
3. custom style baseado em Heading1 -> heading via basedOn;
4. formatação direta parecida com heading sem style reconhecido -> abstain;
5. parágrafo vazio -> abstain;
6. paragraph em tabela com style body -> abstain unsupported_context;
7. numbering warning -> abstain unsupported_context;
8. run de paragraph body -> inherited_from_paragraph + parent anchor;
9. custom style sem basedOn, nome semelhante a heading -> abstain;
10. seção de referências sem ativar reference entries -> nenhuma falsa classificação como reference.

## Testes adversariais mínimos

- `status != classified` nunca projeta;
- documento sem styles reconhecíveis pode produzir 100% abstentions sem falha;
- classifier não importa/consulta perfil normativo;
- same-process + subprocess/hashseed determinismo;
- inputs não mutados;
- falha parcial por bloco;
- prioridade de reasons concorrentes;
- provenance de herança distinta de direct;
- basis heuristic nunca projeta;
- E2E completo:

```text
DOCX
-> Parser
-> Analysis
-> Classification(body)
-> TargetClassification
-> Decision P1–P4
```

com resultado equivalente ao E2E manual congelado em 0021.

## Corpus de classificação

Criar corpus separado do corpus-base de formatação.

O corpus-base de 41 fixtures não possui ground truth de classe e não deve ser reutilizado como se tivesse.

Fases:
1. fixtures sintéticas adversariais do slice;
2. pequeno corpus real anotado antes de ativar long_quote/reference/heuristic;
3. thresholds de produção somente após avaliação nesse corpus.

## Métricas para freeze futuro

Obrigatórias:
- precision por classe;
- false-positive rate por classe;
- coverage;
- abstention rate;
- desagregação por basis/contexto quando aplicável.

Não usar accuracy isolada.

Princípio congelado:

**precision > coverage**.

Classes críticas que mudem fortemente as regras de formatação devem atingir precisão ao menos compatível com as metas do produto antes da ativação automática.

## Threshold policy

Nenhuma classe recebe threshold de produção antes de avaliação em corpus anotado.

Na v0.1 não há score numérico nem threshold estatístico.

## Versionamento

```text
CLASSIFICATION_VERSION = "0.1"
CLASSIFICATION_VOCABULARY_VERSION = "0.1"
classification_style_identity_version = "0.1"
```

Mudança de significado/renomeação exige nova versão. Expansões estritamente aditivas podem manter a semântica dos itens já congelados.

## Determinismo e falha parcial

- frozen models;
- tuples/enums;
- sem random/clock/locale;
- sem live lxml;
- serialização byte-estável;
- cross-process/hashseed determinístico;
- um alvo abstido/not-applicable não derruba os demais.

## Reabertura

Reabrir apenas por:
- falha de teste;
- impossibilidade técnica;
- contradição normativa/arquitetural nova;
- mudança explícita de escopo;
- novo risco de segurança;
- necessidade demonstrada de breaking change.

## Próximo passo

Implementar o primeiro vertical slice `body + heading + abstain` em branch própria, preservando os 290 testes congelados e adicionando auditoria adversarial antes de merge/freeze.

Não expandir Analysis para outlineLvl/numeração antes de necessidade demonstrada do slice seguinte.
