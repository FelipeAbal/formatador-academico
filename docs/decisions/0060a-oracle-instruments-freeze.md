# 0060A — Oráculo e instrumentos do ciclo 0060 — freeze

**Status:** CONGELADO

**Data:** 2026-09-17

**Contrato normativo:** `docs/decisions/0060-cycle-0060-conservative-performance-contract.md`, revisão 7

**Referência imutável:** `4bcda308a4975f2bb84d87ab4738faaed463bb75`

**Integração:** PR #62, squash `c0495c7af473a45afde08497be6d6803aa3cb320`; hardening pós-auditoria no PR #63, squash `fb3f2a67f59a00cabdb8023377c924fc67792a34`

## 1. Escopo congelado

O 0060A entrega somente instrumentos e contrato. Nenhum código em `src/` foi alterado e nenhuma implementação do 0060B foi iniciada.

Ficam congelados:

1. `tools/oracle_0060.py`, que compara candidato e referência em processos isolados;
2. `tools/artifact_comparator_0060.py`, que compara os cinco artefatos somente por papel, nome, tamanho e SHA-256;
3. `tools/measure_memory_0060.py`, schema `0060.2`, como ferramenta preparatória para a medição oficial do 0060D;
4. a fixture estrutural sintética do 0060B, com profundidade limite, stories secundárias, 128 runs irmãos homônimos e 16 tabelas homônimas;
5. os testes próprios desses instrumentos.

`tools/benchmark_0059.py` permaneceu byte-idêntico à referência.

## 2. Semântica congelada do oráculo

O oráculo materializa a referência exclusivamente pelo SHA completo, em worktree temporária, e verifica `HEAD` e limpeza antes e depois do uso. Ausência do objeto é falha explícita; a árvore corrente nunca substitui a referência.

Cada lado usa somente o `src` selecionado. A origem do pacote importado é validada, inclusive contra namespace package. O processo isolado não lê nem grava o `__pycache__` local.

Resultados da CLI:

| Código | Significado |
| ---: | --- |
| 0 | equivalência exata, ou equivalência de dois erros aceita por opção explícita |
| 1 | divergência entre referência e candidato |
| 2 | falha do instrumento, referência ou infraestrutura; nenhum veredito |
| 3 | os dois lados falharam da mesma forma, sem `--allow-error-equivalence` |

Erros internos do instrumento nunca são convertidos em observações da aplicação. Diagnósticos usam vocabulário fechado e hashes sanitizados; caminhos, traceback, stderr livre e conteúdo do documento não são publicados.

A observação vincula as duas execuções internas por seis igualdades: entrada, DOCX limpo, status, perfil, referência do relatório e SHA do Review DOCX.

## 3. Memória

A ferramenta registra tamanho profundo da IR, tamanho e SHA serializados, baseline, pico e delta de RSS, além do pico do `tracemalloc`.

Limitações congeladas no próprio JSON:

- tamanho profundo é limite inferior para estado nativo não tratado;
- `tracemalloc` não cobre alocações nativas do `lxml` e altera o custo de execução;
- delta de RSS só é significativo no Linux;
- o delta de retenção exige o harness do 0060D.

Ela não fixa o limite definitivo do 0060D.

## 4. Evidência de validação

- suíte local completa: **851 testes aprovados**, Python 3.12.13 e `lxml` 6.1.3;
- CI do PR #62 aprovado;
- CI do PR #63 aprovado, run `35253920909`;
- CI pós-merge da `main` aprovado, run `35254093051`;
- DeepSeek: **APROVADO COM RESSALVAS NÃO BLOQUEANTES** no commit `c9fd7c2`;
- Claude Opus: **APROVADO COM RESSALVAS NÃO BLOQUEANTES** no mesmo commit;
- os acompanhamentos comuns das auditorias foram integrados no PR #63.

Nenhum DOCX real foi usado, copiado ou versionado nesta fase.

## 5. Limitações residuais aceitas

- caminhos de erro da aplicação continuam conservadores: diferenças na mensagem hasheada podem produzir falso negativo de equivalência;
- concorrência entre duas execuções do oráculo no mesmo repositório não foi provada;
- morte abrupta por `SIGKILL` pode deixar registro de worktree para `git worktree prune`;
- a amarração completa exige duas execuções por lado e pode aumentar o custo da trilha manual;
- medições fora do Ubuntu são apenas diagnósticas.

Nenhum item invalida o uso do oráculo como gate do 0060B.

## 6. Regra de reabertura

Este freeze só pode ser reaberto por falha reproduzível do instrumento, divergência não detectada, vazamento de dado privado, incompatibilidade com o contrato revisão 7 ou necessidade formal de emenda antes de uma fase posterior.

O próximo passo permitido é o 0060B, em PR próprio, começando pelo índice estrutural por chamada do parser. O 0060C não começa antes da integração do 0060B.
