# HANDOFF — Formatador Acadêmico

## Estado do projeto

**Fase atual:** corpus-base v1 congelado; arquitetura-base do motor fechada; pronto para desenho do parser DOCX.

Este é o HANDOFF corrente do projeto no GitHub. O histórico posterior deve ser preservado pelo Git, sem criar arquivos `handoff_vNN`.

## Objetivo

Formatar com segurança documentos acadêmicos DOCX já existentes a partir de um perfil formal explicitamente declarado pelo usuário, revista, evento, programa ou instituição.

O MVP não promete conformidade ABNT genérica. A fonte operacional de verdade é o perfil ativo.

## Princípio central

**Na dúvida, marcar.**

O sistema deve maximizar utilidade segura sem:
- inventar conteúdo substantivo;
- perder conteúdo substantivo;
- reescrever conteúdo intelectual;
- aplicar regra não configurada;
- resolver ambiguidade silenciosamente.

## Entrada e saídas do MVP

Entrada:
- DOCX;
- perfil formal estruturado.

Saídas:
1. DOCX limpo, apenas com alterações seguras;
2. DOCX de revisão, com marcações e dúvidas;
3. relatório de processamento.

## Segurança e portão de conservação

Invariantes centrais:
- nenhuma invenção substantiva;
- nenhuma perda substantiva;
- só atuar em subaspecto autorizado;
- subaspecto sem regra ativa é preservado;
- o portão de conservação é veto, nunca autorização;
- reordenação estrutural deve ser rastreável;
- exemplo humano fornece forma, nunca valores;
- não normalizar caixa sem evidência e autorização;
- não uniformizar nomes completos/iniciais sem evidência;
- não sinalizar não-problema;
- campo extra não pode ser descartado.

Classes de operação:
- `tipografica`: propriedade tipográfica, sem alteração substantiva;
- `1`: permutação/movimento de segmento identificado;
- `2`: duplicação de valor identificado para papel explicitamente exigido;
- `3a`: literal/separador formal neutro;
- `3b`: literal de papel ou relação;
- `4`: literal formal herdado de exemplo humano confirmado;
- `5`: redução formal autorizada, fechada e rastreável.

C3 exige revisão humana obrigatória.

## Configuração

Vocabulário P1–P27:
`corpus/catalogs/profile-vocabulary-v1.json`

Regras:
- configuração opera por subaspecto;
- P1–P9 ainda podem funcionar como macroaspectos;
- P10–P27 exigem subaspecto explícito;
- sem preferência entre formas aceitas implica preservar;
- P23 representa formas alternativas aceitas.

## Corpus congelado v1

Estrutura:
- 10 tipos bibliográficos;
- 4 funções por tipo;
- 40 fixtures-base;
- RC3-01 adicional;
- total: 41 fixtures.

Funções:
1. controle positivo;
2. correção real;
3. incompletude/indeterminação;
4. contenção.

Distribuição das correções reais:
- B1: 5;
- C2: 4;
- C3: 1.

Contenção significa exatamente:
**NÃO TOCAR + NÃO SINALIZAR.**

Baseline obrigatório do motor nulo:
**20/41 = 48,8%**

Meta de precisão das edições automáticas: >= 99%.
Casos de alto risco: desejo >= 99,5%.
Tolerância a invenção/perda conhecida, alteração indevida de citação direta ou dano a campo: zero.

Arquivos principais:
- `corpus/manifest.json`
- `corpus/fixtures/`
- `corpus/schemas/fixture-v1.2.schema.json`
- `corpus/catalogs/profile-vocabulary-v1.json`
- `corpus/catalogs/alert-catalog-v1.json`
- `corpus/catalogs/expected-validation-warnings-v1.json`
- `tools/validate_corpus.py`
- `tools/build_corpus.py`

## Decisão arquitetural 0001 — DocumentIR

A arquitetura separa obrigatoriamente:
1. o que veio fisicamente do DOCX;
2. o que o motor inferiu;
3. o que o perfil autorizou;
4. o que foi efetivamente modificado.

### Arquitetura dual

`OriginalPackage` é imutável e permanece como fonte da verdade física.

`DocumentIR` é visão analítica derivada, serializável e imutável após o parse.

A saída NÃO será reconstruída a partir da IR.

Fluxo:
`DOCX original imutável -> DocumentIR -> decisões -> patches registrados -> cópia do XML original modificada`.

### Stories e blocos

A IR deve preservar stories separadas, incluindo ao menos:
- body;
- footnotes;
- endnotes;
- headers;
- footers.

Blocos/objetos estruturais devem distinguir, quando aplicável:
- paragraph;
- table;
- table_row;
- table_cell;
- structural_object;
- section_break;
- field;
- bookmark_boundary;
- textbox;
- note_reference.

Hyperlinks são spans/anotações, não necessariamente blocos.

### Identidade/provenance

`paragraph_index` isolado é proibido como chave.

Identidade mínima:
- `story`;
- `structural_path`;
- `original_index`;
- `content_hash`.

O pacote original possui hash próprio.

### Runs e formatação

Preservar `runs_raw` exatamente como vieram do DOCX.

`runs_normalized` pode existir apenas como visão derivada para análise, com mapeamento de offsets para os runs originais.

Normalização destrutiva no parse é proibida.

Cada propriedade de formatação relevante registra:
- valor;
- origem: `direct | style | inherited | default`.

Objetos vivos de `python-docx` ou outra biblioteca não entram na IR.

### Inferência, política e transformação

Classificação semântica fica em `role_candidates`.

Autorização do perfil fica em `policy_decision`.

A IR não é mutada.

Transformações ficam em `TransformLog`, separadas da representação original.

### Tracked changes e comments

No MVP, presença de `w:ins`, `w:del` ou comentário ancorado cria **zona protegida**.

Regra:
- preservar XML original intacto;
- bloquear edição automática na região afetada;
- sinalizar para revisão humana;
- não assumir revisões como aceitas ou rejeitadas;
- não editar comentário nem seu conteúdo automaticamente.

## Decisão arquitetural 0002 — Unidade de trabalho do motor

Documento de decisão:
`docs/decisions/0002-engine-work-unit.md`

Hierarquia aprovada:

`DocumentContext -> BlockWorkItem -> Field/Aspect Decisions -> OperationPlan -> SafetyGate -> TransformLog -> XML Patches`

### Unidades

- documento = contexto;
- bloco = unidade de orquestração e rastreabilidade;
- campo/aspecto = unidade de decisão/autorização;
- operação = unidade de execução, auditoria e reversibilidade.

### Dois níveis de contexto

`LocalContext` é uma visão curada e limitada para regras locais.

`GlobalContext` é reservado a regras verdadeiramente documentais.

Regra local não recebe pacote DOCX nem visão global irrestrita.

### OperationPlan como fronteira de segurança

`OperationPlan` é a fronteira rígida entre entendimento e modificação.

Antes dele, o sistema pode lidar com classificação, hipóteses e incerteza.

Depois dele, a execução é determinística.

Se ainda existe dúvida relevante, a operação não deve existir.

Componentes de análise/decisão não recebem referência ao pacote DOCX e não podem escrever nele por construção.

### Contrato mínimo de operação

Toda operação deve carregar ao menos:
- `operation_id`;
- `type`;
- alvo pela identidade composta;
- campo/aspecto afetado;
- regra/subaspecto do perfil autorizador;
- `before`;
- `after`;
- nível de risco;
- classe do portão quando aplicável.

### Operações estruturais

O contrato admite desde o início, mesmo que inicialmente desabilitadas:
- `MOVE_BLOCK`;
- `INSERT_BLOCK`;
- `MERGE_BLOCKS`.

### Endereçamento e aplicação

Operações são registradas em coordenadas do documento original.

Regra inicial:
1. validar todas as operações;
2. aplicar operações internas de conteúdo/formatação;
3. verificar novamente identidades relevantes;
4. aplicar operações estruturais por último;
5. validar o pacote resultante.

A camada de aplicação é responsável por re-resolver endereços e detectar conflitos quando operações estruturais forem implementadas.

### SafetyGate

O gate verifica deterministicamente, no mínimo:
1. existe regra ativa autorizando a operação?
2. o alvo ainda corresponde ao provenance/content hash esperado?
3. a operação altera somente o aspecto autorizado?
4. o aplicador sabe executar esse tipo de patch com segurança?

Falha em qualquer verificação implica `NÃO APLICAR`.

O gate nunca corrige, reinterpreta ou completa uma operação.

### Fluxo unidirecional

`análise -> decisão -> plano -> gate -> log -> patch`

Dados entre camadas devem ser serializáveis.

## Regra de revisão técnica

Nenhuma decisão técnica relevante de arquitetura ou implementação é considerada fechada apenas por proposta do ChatGPT.

Fluxo obrigatório:
1. ChatGPT propõe;
2. auditor/modelo adequado revisa;
3. ChatGPT integra o parecer;
4. Felipe aprova;
5. decisão é registrada e commitada.

Papéis:
- ChatGPT: arquitetura, integração, decisões e HANDOFF;
- Claude Opus: auditor adversarial de metodologia/segurança;
- Kimi K3: implementação, parsing, DOCX, heurísticas e revisão técnica;
- Felipe: decisão final de produto.

## Auditorias concluídas

1. schema do corpus: Kimi K3;
2. auditoria adversarial do corpus: Claude Opus;
3. reauditoria final do corpus: Claude Opus;
4. arquitetura `DocumentIR`: Kimi K3, **APROVAR COM AJUSTES**;
5. unidade de trabalho do motor: Kimi K3, **APROVAR COM AJUSTES**.

Ajustes das auditorias 4 e 5 foram integrados e aprovados.

## Ressalvas não bloqueantes

- possível remodelagem futura de `nivel_principal`;
- `origem` real vs derivado de real só deve mudar com evidência;
- P23.3 ainda não tem fixture isolado específico;
- fixtures isolados exercitam aproximadamente metade do vocabulário catalogado; cobertura documental/transversal virá depois;
- resolução fina de confiança/classificação pode esperar;
- renderização visual do DOCX de revisão pode esperar desde que `TransformLog` exista;
- equações, gráficos e OLE podem nascer como objetos estruturais opacos;
- políticas avançadas para tracked changes ficam fora do MVP inicial;
- operações estruturais podem estar presentes no contrato sem implementação imediata.

## Regra de congelamento do corpus

O corpus-base v1 só pode ser reaberto diante de:
- falha de teste;
- impossibilidade técnica demonstrada;
- contradição nova;
- mudança explícita de escopo ou contrato;
- novo risco de segurança demonstrado.

Não reabrir por preferência estilística.

## Organização de trabalho

Fluxo operacional:
- passo pequeno;
- revisão adequada;
- integração;
- aprovação;
- commit coerente;
- próximo passo.

## Próximo passo

Definir o **contrato mínimo do parser DOCX** e sua primeira fatia implementável, preservando a arquitetura dual e sem escrever ainda código de produção.
