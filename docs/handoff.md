# HANDOFF — Formatador Acadêmico

## Estado do projeto

**Fase atual:** corpus-base v1 congelado; arquitetura-base do motor fechada; contrato mínimo do parser DOCX fechado; estratégia de leitura DOCX fechada; pronto para definir a primeira fatia implementável do parser.

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

`OriginalPackage` é imutável e permanece como fonte da verdade física.

`DocumentIR` é visão analítica derivada, serializável e imutável após o parse.

A saída NÃO será reconstruída a partir da IR.

Fluxo:
`DOCX original imutável -> DocumentIR -> decisões -> patches registrados -> cópia do XML original modificada`.

Identidade mínima:
- `story`;
- `structural_path`;
- `original_index`;
- `content_hash`.

Preservar `runs_raw` exatamente como vieram do DOCX. `runs_normalized` só existe como visão derivada com mapeamento para os runs originais.

Classificação semântica fica em `role_candidates`; autorização em `policy_decision`; transformações em `TransformLog`.

Tracked changes e comments ancorados criam zona protegida: preservar XML, bloquear edição automática e sinalizar.

## Decisão arquitetural 0002 — Unidade de trabalho do motor

Documento de decisão:
`docs/decisions/0002-engine-work-unit.md`

Hierarquia aprovada:
`DocumentContext -> BlockWorkItem -> Field/Aspect Decisions -> OperationPlan -> SafetyGate -> TransformLog -> XML Patches`

Unidades:
- documento = contexto;
- bloco = orquestração/rastreabilidade;
- campo/aspecto = decisão/autorização;
- operação = execução/auditoria/reversibilidade.

`OperationPlan` é a fronteira rígida entre entendimento e modificação. Depois dele, execução é determinística.

Toda operação carrega ao menos:
- `operation_id`;
- `type`;
- alvo pela identidade composta;
- campo/aspecto afetado;
- regra/subaspecto autorizador;
- `before`;
- `after`;
- nível de risco;
- classe do portão quando aplicável.

Operações estruturais fazem parte do contrato desde o início, mesmo que desabilitadas no primeiro motor.

SafetyGate verifica deterministicamente autorização, identidade/provenance, escopo da mudança e suporte seguro do patch. Falha implica `NÃO APLICAR`.

## Decisão arquitetural 0003 — Contrato mínimo do parser DOCX

Documento de decisão:
`docs/decisions/0003-parser-contract.md`

O parser é estritamente físico/forense. Ele observa e registra o pacote original sem classificar conteúdo acadêmico, normalizar destrutivamente runs ou decidir transformações.

Fluxo:
`OriginalPackage -> DOCX Parser -> PhysicalIR -> Normalizer/Analysis View -> classificação/decisão`

Saída mínima do parser:
- `package_metadata` + `package_hash`;
- stories;
- blocks;
- `styles_raw`;
- `numbering_raw`;
- `relationships_raw`;
- `protected_regions`;
- `parse_warnings`.

Stories obrigatoriamente procuradas:
- body;
- footnotes;
- endnotes;
- comments;
- headers[];
- footers[];
- textboxes[] aninhadas.

Story não mapeável gera `unsupported_story`.

Regra: tudo que existe entra na IR ou vira warning explícito.

Offsets dentro de bloco são medidos em caracteres Unicode sobre `text_raw`. Regiões multi-bloco usam âncoras compostas `(block_id, offset_in_block)`.

`styles`, `numbering` e `relationships` são lidos e preservados crus. Resolução de herança/defaults e numbering visível pertence à Analysis View.

No parser físico, `null` significa apenas propriedade não especificada no XML, nunca default calculado.

`runs_raw` são preservados exatamente; `runs_normalized` não pertence ao parser-base.

Objeto não representável vira `source_type = opaque_object`, mantém XML bruto ou referência exata, gera warning e fica protegido automaticamente.

`content_hash` usa representação canônica de `text_raw + source_type + propriedades físicas diretamente presentes`, sem valores derivados de estilos/defaults. A canonização será versionada.

Garantias formais:
- `PARSER-G1`: nunca modifica o pacote original;
- `PARSER-G2`: nenhuma estrutura conhecida ou desconhecida desaparece silenciosamente;
- `PARSER-G3`: não classifica semanticamente conteúdo acadêmico;
- `PARSER-G4`: todo dado é rastreável ao XML físico;
- `PARSER-G5`: conteúdo não representável vira opaque + warning + proteção;
- `PARSER-G6`: ParseResult é serializável e determinístico.

Objetos vivos de `python-docx`, `lxml` ou outra biblioteca não entram na IR.

## Decisão arquitetural 0004 — Estratégia de leitura do DOCX

Documento de decisão:
`docs/decisions/0004-docx-read-strategy.md`

Escolha aprovada:

> **OOXML + lxml como camada autoritativa do parser físico. `python-docx` é auxiliar opcional e nunca fonte da verdade da PhysicalIR.**

Fluxo:
`DOCX -> PackageReader/OPC -> XML Parser (lxml, autoritativo) -> PhysicalIR -> Analysis View -> motor`.

Justificativa estrutural:
- `PARSER-G2` exige observação física abrangente;
- abstrações de alto nível podem omitir estruturas sem aviso;
- detectar essa omissão exigiria varrer o XML de qualquer modo;
- logo, o custo de detectar falha silenciosa excede o custo de ler o XML diretamente.

O parser XML não implementa a semântica completa do OOXML. Ele inventaria parts, localiza stories e containers, registra o conhecido e transforma o desconhecido em `opaque_object` protegido. Interpretação complexa fica para a Analysis View.

### Invariante parse/patch

Adicionada a garantia:

- `PARSER-G7 / PATCHER-G1`: parser e patcher usam a mesma biblioteca XML, mesmas opções de parsing, política de namespaces, definição de `structural_path`, canonicalização e preservação de whitespace compatível.

A identidade física precisa ser reencontrável pelo patcher na cópia do pacote original sem divergência de construção da árvore.

### Papel de python-docx

Pode ser usado para:
- helpers de conveniência;
- propriedades comuns bem suportadas;
- conversões de unidade;
- operações auxiliares específicas;
- validação cruzada amostral em testes.

Divergência entre a leitura XML e `python-docx` vira caso de investigação, nunca autoridade automática de um lado.

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
5. unidade de trabalho do motor: Kimi K3, **APROVAR COM AJUSTES**;
6. contrato mínimo do parser DOCX: Kimi K3, **APROVAR COM AJUSTES**;
7. estratégia de leitura DOCX: Kimi K3 em auditoria adversarial, **APROVAR**.

Todos os ajustes aprovados foram integrados.

## Ressalvas não bloqueantes

- possível remodelagem futura de `nivel_principal`;
- `origem` real vs derivado de real só deve mudar com evidência;
- P23.3 ainda não tem fixture isolado específico;
- cobertura documental/transversal virá depois;
- resolução fina de confiança/classificação pode esperar;
- renderização visual do DOCX de revisão pode esperar desde que `TransformLog` exista;
- equações, gráficos e OLE podem nascer como objetos estruturais opacos;
- políticas avançadas para tracked changes ficam fora do MVP inicial;
- operações estruturais podem existir no contrato sem implementação imediata.

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

Definir a **primeira fatia implementável do parser DOCX**, com escopo mínimo suficiente para testar as garantias arquiteturais antes de ampliar a cobertura OOXML.
