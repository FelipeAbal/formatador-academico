# Decisão 0002 — Unidade de trabalho do motor

## Status
APROVADA

## Hierarquia

A arquitetura do motor adota a hierarquia:

`DocumentContext -> BlockWorkItem -> Field/Aspect Decisions -> OperationPlan -> SafetyGate -> TransformLog -> XML Patches`

## Unidades por camada

- O documento é contexto, não unidade direta de escrita.
- O bloco é a unidade principal de orquestração e rastreabilidade.
- Campo/aspecto é a unidade de decisão e autorização.
- Operação é a unidade de execução, auditoria e reversibilidade.

## Contextos documentais

Há dois níveis distintos:

### LocalContext
Exposto às regras locais e limitado ao necessário, por exemplo:
- seção do bloco;
- estilo resolvido;
- propriedades locais;
- numbering aplicável;
- vizinhança estritamente necessária;
- posição lógica relevante.

### GlobalContext
Exposto apenas a regras realmente documentais, por exemplo:
- estrutura do documento;
- conjuntos de blocos;
- lista de referências;
- relações entre seções;
- dependências entre blocos.

Uma regra local não recebe o pacote DOCX nem uma visão irrestrita do documento.

## Fronteira OperationPlan

`OperationPlan` é a fronteira rígida entre entendimento e modificação.

Antes do `OperationPlan`, o sistema pode classificar, inferir, comparar hipóteses e lidar com incerteza.

Depois do `OperationPlan`, a execução é determinística. Se ainda existe dúvida relevante, a operação não deve existir.

Componentes de análise e decisão não recebem referência ao pacote DOCX original e não podem escrever no documento por construção.

## Contrato mínimo de uma operação

Toda operação deve carregar, no mínimo:
- `operation_id`;
- `type`;
- alvo pela identidade composta do bloco;
- campo/aspecto afetado;
- regra/subaspecto do perfil que autorizou;
- `before`;
- `after`;
- nível de risco;
- classe do portão de conservação quando aplicável.

Não existe operação sem autorização rastreável, alvo verificável e diferença explícita entre estado anterior e posterior.

## Operações estruturais

O contrato deve admitir desde o início operações estruturais, mesmo que fiquem desabilitadas na primeira versão do motor, incluindo pelo menos:
- `MOVE_BLOCK`;
- `INSERT_BLOCK`;
- `MERGE_BLOCKS`.

Operações de conteúdo/formatação e operações estruturais são categorias distintas.

## Endereçamento e ordem de aplicação

Operações são registradas em coordenadas do documento original, usando a identidade composta já aprovada (`story`, `structural_path`, `original_index`, `content_hash`).

Regra inicial de aplicação:
1. validar todas as operações;
2. aplicar operações internas de conteúdo/formatação;
3. verificar novamente as identidades relevantes;
4. aplicar operações estruturais por último;
5. validar o pacote resultante.

Caso operações estruturais passem a ser implementadas, a camada de aplicação é responsável por re-resolver endereços e detectar conflitos. Nenhuma camada anterior corrige caminhos silenciosamente.

## SafetyGate

O `SafetyGate` é determinístico. No mínimo, verifica:

1. existe regra ativa autorizando a operação?
2. o alvo ainda corresponde ao provenance/content hash esperado?
3. a operação altera somente o aspecto autorizado?
4. o aplicador sabe executar esse tipo de patch com segurança?

Falha em qualquer verificação implica `NÃO APLICAR`.

O gate nunca tenta corrigir, reinterpretar ou completar uma operação. O resultado posterior é preservar ou preservar + sinalizar, conforme a regra aplicável.

## Fluxo unidirecional

As camadas se comunicam apenas por dados serializáveis e seguem fluxo estritamente unidirecional:

`análise -> decisão -> plano -> gate -> log -> patch`

Objetos vivos de bibliotecas DOCX não atravessam essa fronteira.

## Auditoria

Proposta inicial: ChatGPT.

Auditoria técnica: Kimi K3.

Parecer: **APROVAR COM AJUSTES**.

Ajustes incorporados:
1. operações estruturais no contrato;
2. regra de ordenação/re-endereçamento;
3. contrato mínimo explícito da operação;
4. checklist determinístico do SafetyGate;
5. LocalContext e GlobalContext separados.

Integração aprovada por Felipe.

## Consequência

Com esta decisão e a decisão anterior sobre `DocumentIR`, não há pendência arquitetural bloqueante identificada antes do desenho do parser.

O próximo passo é definir o contrato mínimo do parser DOCX e sua primeira fatia implementável, sem ainda escrever código de produção.
