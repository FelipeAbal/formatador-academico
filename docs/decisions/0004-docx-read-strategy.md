# Decisão 0004 — Estratégia de leitura do DOCX

## Status

**APROVADA**

## Contexto

O contrato mínimo do parser DOCX já está fechado. O parser deve ser físico/forense, preservar estruturas conhecidas e desconhecidas, produzir `PhysicalIR` serializável e determinística, e nunca depender de uma abstração que possa omitir silenciosamente partes do pacote.

Foram comparadas três abordagens:

1. `python-docx` como parser principal;
2. XML/OOXML direto para toda a leitura;
3. arquitetura híbrida com XML/lxml autoritativo e `python-docx` auxiliar.

A proposta foi submetida a auditoria adversarial por Kimi K3 com a instrução explícita de tentar derrubá-la.

## Decisão

Adotar:

> **OOXML + lxml como camada autoritativa do parser físico. `python-docx` será auxiliar opcional, nunca fonte da verdade da `PhysicalIR`.**

Fluxo conceitual:

`DOCX -> PackageReader/OPC -> XML Parser (lxml, autoritativo) -> PhysicalIR -> Analysis View -> motor`

`python-docx` fica em paralelo como helper de conveniência e instrumento de validação cruzada em testes.

## Justificativa estrutural

A garantia `PARSER-G2` exige que nenhuma estrutura conhecida ou desconhecida desapareça silenciosamente.

Uma abstração de alto nível pode omitir partes do pacote sem sinal explícito. Detectar posteriormente essa omissão exigiria varrer o XML bruto de qualquer forma. Portanto:

> o custo de detectar falha silenciosa excede o custo de ler o XML diretamente.

A decisão não depende do corpus atual conter tracked changes, text boxes ou outras estruturas complexas. Ela deriva do contrato do produto para documentos futuros.

Conservadorismo na decisão exige observação física abrangente: para não tocar no que o sistema não entende, ele precisa primeiro saber que aquilo existe e onde está.

## Papel do parser XML

O parser físico não reimplementa a semântica completa do OOXML.

Ele precisa:
- abrir o pacote ZIP/OPC;
- inventariar parts e relationships;
- localizar stories;
- reconhecer containers estruturais essenciais;
- registrar nós conhecidos;
- transformar o desconhecido em `opaque_object` + warning + proteção;
- preservar XML e provenance.

A interpretação mais complexa fica na `Analysis View` e pode crescer incrementalmente conforme as regras ativas precisarem dela.

## Invariante parse/patch

Fica adicionada a garantia combinada:

### PARSER-G7 / PATCHER-G1

Parser e patcher devem usar:
- a mesma biblioteca XML;
- as mesmas opções de parsing;
- a mesma política de namespaces;
- a mesma definição de `structural_path`;
- a mesma canonicalização usada em identidade/hash;
- preservação de whitespace compatível com o pacote original.

A implementação deve evitar qualquer diferença de construção da árvore que possa fazer o patcher reencontrar um nó diferente daquele auditado pelo parser.

`structural_path` é definido sobre a representação XML física conforme a política de canonicalização versionada do projeto.

## Complexidade

A complexidade deve ser entendida em duas camadas:

- parse forense XML: custo proporcional e necessário;
- interpretação semântica OOXML: custo alto, mas incremental e fora do parser-base.

Não será implementado um interpretador completo de OOXML antes da necessidade real.

## Papel de python-docx

`python-docx` pode ser usado para:
- helpers de conveniência;
- propriedades comuns já bem suportadas;
- conversões de unidade;
- operações auxiliares específicas;
- validação cruzada em testes.

Ele nunca será autoridade sobre existência, posição ou completude das estruturas da `PhysicalIR`.

## Validação cruzada

Para estruturas comuns, testes podem comparar leituras independentes do parser XML e do `python-docx`.

Exemplos:
- contagem de parágrafos simples;
- tabelas;
- propriedades comuns;
- outras estruturas cobertas por ambas as leituras.

Divergência vira sinal para investigar o parser, não prova automática de erro de um lado.

## Consequências

- `lxml` passa a ser dependência arquitetural do parser/patcher.
- `python-docx` permanece substituível e auxiliar.
- unknown OOXML continua visível via `opaque_object`.
- leitura e escrita física compartilham a mesma base técnica.
- a primeira fatia implementável do parser pode agora ser desenhada sem pendência arquitetural sobre a estratégia de leitura.
