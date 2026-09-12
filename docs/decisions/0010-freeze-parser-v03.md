# Decisão 0010 — Congelamento formal do parser v0.3

## Contexto

Após o hardening da v0.3, o código foi revalidado externamente pelo Kimi K3 no `main`.

Resultado final da suíte completa:
- 56 testes executados;
- 56 passes;
- 0 failures;
- 0 errors;
- 0 skips.

A revalidação confirmou também, em experimento próprio, o último ajuste de borda:
- relationship de story cujo target resolve para fora da raiz lógica do pacote gera `suspicious_target`;
- a story fica `rejected`;
- `story.errors[0].code = suspicious_target`;
- o erro aparece também no `errors[]` global;
- a story entra em `partial_stories[]`;
- o documento fica `partial`;
- o body permanece `ok`;
- nenhuma leitura fora do pacote é tentada.

Nenhuma regressão nova foi encontrada. A única mudança intencional confirmada em relação à v0.3 pré-hardening é o esquema de `story_id` baseado na part para stories secundárias, já registrado na decisão 0009.

## Veredito externo

**CONGELAR v0.3**.

## Estado congelado

A v0.3 fecha o ciclo atual do parser físico para:
- pacote/ZIP/OPC e segurança básica;
- body;
- parágrafos;
- runs;
- containers de runs;
- fragmentos tipados e opacos;
- footnotes;
- endnotes;
- headers;
- footers;
- comments;
- descoberta por relationships;
- content type como validação cruzada;
- stories órfãs;
- parse parcial por story;
- stories `ok`, `missing`, `failed` e `rejected`;
- detecção ativa de textboxes/text bodies ainda opacos;
- identidade física rastreável por `part + story_id + structural_path + original_index + physical_hash`.

## Regra de reabertura

A v0.3 só deve ser reaberta por:
- falha de teste;
- impossibilidade técnica demonstrada em etapa posterior;
- contradição nova;
- mudança explícita de contrato/escopo;
- novo risco de segurança.

Melhorias cosméticas ou expansões estruturais não reabrem a v0.3 por si só.

## Próxima etapa

A próxima fatia técnica é **v0.4 — decomposição física segura de tabelas**.

A v0.4 deve ser auditada em nível de contrato antes de implementação. Textboxes continuam fora dessa fatia e permanecem detectados/protegidos.
