# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** ciclo 0060, com o **0060A integrado e congelado** e o **0060B implementado localmente**.

**Branch corrente:** `implement/0060b-parser-sibling-index`.
**Commit local do 0060B:** `8842d0e`.
**0060C não foi iniciado.**

Este é o HANDOFF corrente. O histórico detalhado fica no Git; não criar `handoff_vNN`.

## Baseline de implementação validado

- implementação do 0060A: `fb3f2a67f59a00cabdb8023377c924fc67792a34`;
- freeze e HANDOFF: PR #64, squash `8fb2c1195dde92b08890ca940cd4d979713d191d`;
- suíte completa: **851/851 OK**;
- CI pós-merge da implementação: run `35254093051`, `success`;
- CI pós-merge do freeze: run `35254795199`, `success`;
- Python local de validação: 3.12.13;
- `lxml`: 6.1.3;
- failures: 0;
- errors: 0.

GitHub Actions é a execução padrão da suíte. Não gastar outro modelo apenas para repetir testes normais.

## Checkpoint demonstrável do protótipo

- inicialização única: `.venv/bin/python tools/run_local_web.py`;
- guia: `docs/guides/local-prototype-v01.md`;
- smoke test real do servidor aprovado com fixture sintética;
- resposta HTTP 200, sessão `quiescent` e cinco artefatos com tamanho e SHA-256 conferidos;
- nenhum DOCX real usado, copiado ou versionado.

## Estado do 0060B

- índice de posição de irmãos local a cada `parse_bytes`, construído sob demanda por pai;
- chaves formadas pelos próprios objetos do lxml, mantendo os proxies vivos durante o uso;
- descarte em `finally`, inclusive em falha inesperada;
- `PARSER_VERSION` preservado em `0.4.0`;
- errata de implementação acrescentada às decisões 0009 e 0011;
- API pública de caminhos preservada e `parser_api.resolve_structural_path` inalterado;
- oráculo do 0060A: IR byte-idêntica na fixture estrutural;
- suíte completa local: **858/858 OK**;
- medição sintética: mediana de 102,7 ms para 35,3 ms, ganho de **2,91×**;
- parses A/B/A, threads concorrentes, story parcial, comentários, instruções de processamento e descarte cobertos por testes;
- `tools/benchmark_0059.py` permanece intacto;
- nenhum DOCX real foi acessado.

Ainda faltam, antes da integração: enviar a branch, abrir o PR, obter CI verde, executar a trilha manual autorizada dos seis DOCX reais no Ubuntu e concluir a auditoria adversarial independente.

## Fechamento do 0060A

- PR #61 — contrato do ciclo 0060, revisão 6; squash `d8093730cc6378eefb2c7801287fc5da13fd500c`;
- PR #62 — oráculo, comparador, ferramenta de memória e fixture estrutural; squash `c0495c7af473a45afde08497be6d6803aa3cb320`;
- PR #63 — hardening pós-auditoria e contrato revisão 7; squash `fb3f2a67f59a00cabdb8023377c924fc67792a34`.

Freeze: `docs/decisions/0060a-oracle-instruments-freeze.md`.

As reauditorias independentes do commit final do PR #62 concluíram **APROVADO COM RESSALVAS NÃO BLOQUEANTES**, sem bloqueantes. Os pareceres permanecem locais e não são versionados:

- DeepSeek: `0062-reauditoria-0060a-deepseek.md`;
- Claude Opus: `0062-reauditoria-0060a-claude-opus.md`.

Os acompanhamentos comuns foram resolvidos no PR #63: códigos fechados de diagnóstico, isolamento contra `.pyc` obsoleto, tratamento de namespace package, limitação de RSS por plataforma e esclarecimento do fetch da referência no CI.

## Referência e ferramentas congeladas

Referência pré-0060:

```text
4bcda308a4975f2bb84d87ab4738faaed463bb75
```

Arquivos centrais:

- `docs/decisions/0060-cycle-0060-conservative-performance-contract.md` — revisão 7;
- `tools/oracle_0060.py`;
- `tools/artifact_comparator_0060.py`;
- `tools/measure_memory_0060.py`;
- `tests/fixture_0060.py`;
- `tests/fixtures/0060-parser-structural-stress.json`.

`tools/benchmark_0059.py` permanece byte-idêntico e não pode ser alterado durante o ciclo 0060 sem refazer integralmente a linha de base.

## Restrições do ciclo 0060

1. equivalência exata contra o SHA congelado; nenhuma tolerância aproximada;
2. nenhum fallback para a árvore corrente se a referência estiver ausente;
3. nenhum DOCX real no repositório ou no CI;
4. documentos reais somente na trilha manual do Ubuntu, sob autorização explícita de Felipe;
5. nenhuma nova propriedade do slice automático antes do fim do 0060E;
6. nenhum agrupamento de operações ou atomicidade multi-alvo;
7. qualquer fase que não prove equivalência exata é revertida;
8. 0060C só começa depois da integração do 0060B;
9. 0060D só começa depois da integração do 0060C;
10. 0061 é condicional e nunca automático.

## Próximo passo exato — não executado

Enviar `8842d0e` para `origin/implement/0060b-parser-sibling-index`, abrir o PR próprio do **0060B** e acompanhar o CI.

Escopo exclusivo do 0060B:

1. implementar índice de posição de irmãos por chamada no parser, removendo o caminho quadrático;
2. preservar a PhysicalIR byte-idêntica pelo oráculo congelado;
3. acrescentar a nota de erratum aos contratos 0009 e 0011;
4. usar a fixture estrutural entregue pelo 0060A;
5. manter `tools/benchmark_0059.py` intacto;
6. não iniciar 0060C, 0060D, 0060E ou 0061.

Antes de integrar o 0060B:

- suíte e CI verdes;
- comparação exata nas fixtures sintéticas;
- verificação manual dos seis DOCX reais no Ubuntu, com autorização explícita;
- auditoria adversarial independente;
- nenhum documento real ou conteúdo privado em logs.

## Produto e segurança que permanecem congelados

O core continua com parser físico v0.4; Analysis v0.1a/v0.1b; Decision, Classification, OperationPlan, SafetyGate, Patcher, TransformLog, Processing Session, Processing Report, Review DOCX, Product Output Bundle, Profile Input, Product Input Boundary, relatório humano e Product Delivery congelados.

O slice automático permanece limitado a:

```text
P1 / run / bold
P2 / run / font_size
P3 / paragraph / spacing.line
P4 / paragraph / alignment
```

Princípios obrigatórios:

- nenhuma invenção ou perda substantiva;
- ausência de regra continua ausência;
- ambiguidade não é resolvida silenciosamente;
- SafetyGate é veto, nunca autorização;
- mutação mínima, allowed-delta e pós-condição continuam obrigatórios;
- OriginalPackage e snapshot nunca são mutados in-place;
- Review DOCX é apresentação, não correção normativa;
- o relatório humano projeta o ProcessingReport e não inventa conformidade;
- na dúvida, marcar.

## Regra operacional

Tudo o que puder ser corrigido com segurança dentro do escopo atual deve ser corrigido antes de avançar. Só postergar por expansão explícita de escopo, dependência não resolvida, impossibilidade demonstrada, contradição normativa ou novo risco de segurança.

Fluxo:

1. ChatGPT propõe e implementa;
2. Claude Opus audita quando houver ganho real em segurança ou arquitetura;
3. ChatGPT integra;
4. Felipe só é interrompido quando sua decisão, autorização para documentos reais ou envio a outro modelo forem necessários;
5. CI e inspeção final;
6. freeze e atualização deste HANDOFF.
