# HANDOFF — Formatador Acadêmico

## Estado do projeto

**Fase atual:** corpus-base v1 congelado; pronto para desenho e implementação do motor.

Este arquivo passa a ser o HANDOFF corrente a partir da entrada do projeto no GitHub. O histórico posterior deve ser preservado pelo Git, sem criar arquivos `handoff_vNN`.

## Objetivo

Formatar com segurança documentos acadêmicos já existentes a partir de um perfil formal explicitamente declarado pelo usuário, revista, evento, programa ou instituição.

O MVP não promete conformidade ABNT genérica. A fonte operacional de verdade é o perfil ativo.

## Princípio central

**Na dúvida, marcar.**

O sistema deve maximizar utilidade segura sem:
- inventar conteúdo;
- perder conteúdo substantivo;
- reescrever conteúdo intelectual;
- aplicar regra não configurada;
- resolver ambiguidade silenciosamente.

## Entradas e saídas do MVP

Entrada:
- DOCX;
- perfil formal estruturado.

Saídas:
1. DOCX limpo, apenas com alterações seguras;
2. DOCX de revisão, com marcações e dúvidas;
3. relatório de processamento.

## Segurança

### Invariantes principais

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

### Classes de operação

- `tipografica`: propriedade tipográfica, sem alteração substantiva;
- `1`: permutação/movimento de segmento identificado;
- `2`: duplicação de valor identificado para papel explicitamente exigido;
- `3a`: literal/separador formal neutro;
- `3b`: literal de papel ou relação;
- `4`: literal formal herdado de exemplo humano confirmado;
- `5`: redução formal autorizada, fechada e rastreável.

C3 exige revisão humana obrigatória.

## Escopo de referências do MVP

Tipos:
1. livro;
2. capítulo;
3. artigo;
4. trabalho publicado em evento;
5. dissertação;
6. tese;
7. documento online;
8. legislação;
9. jurisprudência;
10. fonte histórica/arquivo.

Entrevista/testemunho fica fora do MVP inicial.

## Configuração

Vocabulário P1–P27 está em:
`corpus/catalogs/profile-vocabulary-v1.json`

Regra metodológica:
- configuração opera por subaspecto;
- P1–P9 ainda podem funcionar como macroaspectos;
- P10–P27 exigem subaspecto explícito;
- sem preferência entre formas aceitas implica preservar;
- P23 representa formas alternativas aceitas.

## Corpus congelado v1

Estrutura:
- 10 tipos;
- 4 funções por tipo;
- 40 fixtures-base;
- RC3-01 adicional.

Cada tipo possui:
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

## Métricas

A métrica principal é taxa de decisão correta.

Contam como sucesso:
- corrigir automaticamente de forma correta;
- corrigir parcialmente e sinalizar;
- preservar e sinalizar;
- abster-se corretamente.

Erros incluem:
- alterar caso ambíguo;
- inventar;
- perder;
- editar região errada;
- deixar de sinalizar problema atribuído;
- sinalizar problema inexistente.

Meta de precisão das edições automáticas: >= 99%.
Casos de alto risco: desejo >= 99,5%.
Tolerância a invenção/perda conhecida, alteração indevida de citação direta ou dano a campo: zero.

### Baseline obrigatório

Motor nulo, que nunca altera e nunca sinaliza:
**20/41 = 48,8%**

Todo relatório de avaliação do motor deve mostrar esse baseline ao lado do resultado bruto.

## Schema e validação

Schema:
`corpus/schemas/fixture-v1.2.schema.json`

Catálogos:
- `corpus/catalogs/profile-vocabulary-v1.json`
- `corpus/catalogs/alert-catalog-v1.json`
- `corpus/catalogs/expected-validation-warnings-v1.json`

Validador:
`tools/validate_corpus.py`

O validador verifica:
- JSON Schema;
- identidade e tipo;
- markup abstrato `<b>/<i>/<u>`;
- vocabulário de aspectos;
- operações autorizadas e bloqueadas;
- classes de portão;
- subaspectos presentes/configurados;
- C3 com revisão humana;
- contenção;
- entradas duplicadas;
- links de regressão;
- catálogo fechado de alertas;
- mapeamento determinístico de mudanças;
- baseline fechado de warnings lexicais.

## Rastreabilidade de transformação

Fixtures transformadores/propostas usam `mudancas_esperadas`.

Cada etapa contém:
- `trecho_antes`;
- `trecho_depois`;
- `codigo_operacao`.

A cadeia deve começar na entrada e terminar exatamente na saída esperada. Toda operação autorizada de um fixture transformador deve aparecer no mapeamento.

## Auditorias concluídas

1. auditoria técnica do schema por Kimi K3;
2. auditoria adversarial do corpus por Claude Opus;
3. reauditoria final por Claude Opus.

Parecer final externo:
**pode congelar o corpus: SIM.**

Não houve impedimento técnico ou metodológico para iniciar a implementação do motor.

## Ressalvas não bloqueantes

- possível remodelagem futura de `nivel_principal`;
- `origem` real vs derivado de real só deve mudar com evidência;
- P23.3 ainda não tem fixture isolado específico;
- fixtures isolados exercitam aproximadamente metade do vocabulário catalogado; P2–P9, P24 e outros terão cobertura natural em testes documentais/transversais.

## Regra de congelamento

O corpus-base v1 só pode ser reaberto diante de:
- falha de teste;
- impossibilidade técnica demonstrada;
- contradição nova;
- mudança explícita de escopo ou contrato.

Não reabrir por preferência estilística.

## Organização de trabalho

Modelos:
- ChatGPT: arquitetura, integração, decisões e HANDOFF;
- Claude Opus: auditor adversarial;
- Kimi K3: implementação, parsing, DOCX, heurísticas e revisão técnica;
- Felipe: decisão final de produto.

Fluxo:
- passo pequeno;
- teste;
- resultado;
- aprovação;
- próximo passo;
- atualizar este HANDOFF ao fechar etapa relevante.

## Próximo passo

Desenhar a arquitetura mínima do motor e definir a ordem de implementação das classes de operação antes de escrever código de produção.
