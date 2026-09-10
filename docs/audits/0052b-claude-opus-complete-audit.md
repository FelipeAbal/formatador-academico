# Auditoria 0052B: auditoria completa pelo Claude Opus

## Objeto

Auditar integralmente o Formatador Acadêmico no commit:

```text
08fed75e81541d439bf31bd532ecf4096896a6b2
```

O PR #29, que implementou o contrato 0051 e o P3/`spacing.line`, foi integrado por squash. A implementação teve auditoria anterior do Claude Opus e CI verde com 758 testes.

## Objetivo

Avaliar se o produto continua seguro, determinístico, coerente e fiel aos contratos congelados após a integração do P3. Esta auditoria deve considerar o sistema como um todo, não apenas o último diff.

## Material obrigatório

- `docs/handoff.md`;
- decisões 0028, 0031, 0033, 0037, 0048, 0049 e 0051;
- auditorias anteriores em `docs/audits/`;
- código completo de `src/formatador_academico/`;
- suíte completa de `tests/`;
- histórico e diff do PR #29.

## Eixos da auditoria

### 1. Contratos

- compatibilidade entre contratos antigos e P3;
- schema 0.3 como superconjunto estrito;
- coerência entre Profile Input, Decision, OperationPlan, SafetyGate, Patcher, Transform Log, Processing Report e Review DOCX;
- vocabulário e razões machine-readable;
- exemplos documentais e afirmações do handoff.

### 2. Segurança do DOCX

- preservação de conteúdo e propriedades não autorizadas;
- mutação mínima;
- ordem canônica de `w:pPr`;
- duplicatas;
- herança por estilos;
- listas, bidi, revisões, tabelas, containers e stories secundárias;
- atomicidade e ausência de saída parcial;
- stale plans, hashes e drift físico.

### 3. P3

- semântica de `auto`, `atLeast` e `exact`;
- ausência de `line` ou `lineRule`;
- unidades universais;
- conversão para unidades OOXML;
- limites e precisão;
- preservação de `before`, `after` e demais atributos;
- casos de herança e múltiplos elementos.

### 4. P4 e regressões

- equivalência `left/start` e `right/end`;
- `justify/both`;
- listas e bidi;
- marcação no Review DOCX;
- efeitos da inclusão de P3 sobre P1, P2 e P4.

### 5. Qualidade de engenharia

- determinismo entre execuções;
- dependência do contexto global de `Decimal`;
- coerência de tipos;
- superfícies não testadas;
- complexidade e performance;
- mensagens e razões reportadas;
- adequação dos testes ao risco real.

### 6. XSD e proveniência

- verificar a ordem de `CT_PPr` contra fonte primária adequada;
- avaliar a decisão de não versionar o `wml.xsd` inteiro;
- recomendar se basta uma fixture verificável do fragmento relevante;
- não exigir dependência de rede no CI sem justificar a reprodutibilidade.

## Procedimento

- executar a suíte completa;
- inspecionar o diff do PR #29;
- criar mentalmente e, quando possível, executar casos adversariais;
- rastrear cada operação desde o JSON de entrada até os arquivos de saída;
- distinguir defeito confirmado de risco hipotético;
- não modificar o repositório durante a auditoria.

## Entrega exigida

1. veredito geral: aprovado, aprovado com ajustes ou bloquear;
2. tabela de achados com severidade, localização, impacto, evidência e correção;
3. regressões encontradas;
4. lacunas de teste;
5. contratos que precisam de emenda;
6. recomendação sobre o `wml.xsd`;
7. sequência de correções por prioridade;
8. avaliação específica sobre se o P3 pode permanecer em produção;
9. lista do que está correto e deve ser preservado.

A auditoria deve ser independente da revisão do DeepSeek. Não assumir que a aprovação anterior elimina a necessidade de verificar o código final.
