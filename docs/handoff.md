# HANDOFF — Formatador Acadêmico

## Estado do projeto

**Fase atual:** corpus-base v1 congelado; arquitetura-base do motor fechada; contrato e estratégia do parser DOCX fechados; parser v0.1 endurecido após auditoria adversarial; **11/11 testes locais aprovados**. Próxima etapa: definir a menor fatia v0.2 antes de escrever novo código.

Este é o HANDOFF corrente do projeto no GitHub. O histórico anterior permanece no Git; não criar `handoff_vNN`.

## Objetivo do MVP

Formatar com segurança documentos acadêmicos DOCX existentes a partir de um perfil formal explicitamente declarado. O MVP não promete conformidade ABNT genérica. A fonte operacional de verdade é o perfil ativo.

Entradas:
- DOCX;
- perfil formal estruturado.

Saídas:
1. DOCX limpo com alterações seguras;
2. DOCX de revisão com marcações/dúvidas;
3. relatório de processamento.

Princípio central: **Na dúvida, marcar.**

## Segurança

Invariantes centrais:
- nenhuma invenção substantiva;
- nenhuma perda substantiva;
- só atuar em subaspecto autorizado;
- subaspecto sem regra ativa é preservado;
- portão de conservação é veto, nunca autorização;
- exemplo humano fornece forma, nunca valores;
- não normalizar caixa ou nomes sem evidência/autorização;
- campo extra não pode ser descartado;
- não sinalizar não-problema.

C3 exige revisão humana obrigatória.

## Corpus congelado v1

- 10 tipos bibliográficos;
- 40 fixtures-base + RC3-01 = 41;
- baseline motor nulo: **20/41 = 48,8%**;
- precisão-alvo das edições automáticas: >=99%;
- alto risco desejado: >=99,5%;
- tolerância a invenção/perda conhecida, alteração indevida de citação direta ou dano a campo: zero.

Arquivos principais:
- `corpus/manifest.json`
- `corpus/fixtures/`
- `corpus/schemas/fixture-v1.2.schema.json`
- `corpus/catalogs/profile-vocabulary-v1.json`
- `corpus/catalogs/alert-catalog-v1.json`
- `tools/validate_corpus.py`
- `tools/build_corpus.py`

O corpus só reabre por falha de teste, impossibilidade técnica demonstrada, contradição nova, mudança explícita de escopo/contrato ou novo risco de segurança.

## Decisões arquiteturais fechadas

### 0001 — DocumentIR

- `OriginalPackage` imutável é a fonte física da verdade.
- `DocumentIR`/PhysicalIR é visão analítica derivada e serializável.
- saída nunca é reconstruída a partir da IR;
- classificação (`role_candidates`), autorização (`policy_decision`) e transformações (`TransformLog`) são separadas;
- tracked changes/comments ancorados formam zona protegida no MVP.

### 0002 — Unidade de trabalho

Hierarquia:
`DocumentContext -> BlockWorkItem -> Field/Aspect Decisions -> OperationPlan -> SafetyGate -> TransformLog -> XML Patches`

- documento = contexto;
- bloco = orquestração/rastreabilidade;
- campo/aspecto = decisão/autorização;
- operação = execução/auditoria/reversibilidade.

`OperationPlan` é a fronteira entre interpretação e execução determinística. Nenhum componente de análise recebe acesso de escrita ao DOCX.

### 0003 — Contrato mínimo do parser

Parser físico/forense: observa e registra; não classifica conteúdo acadêmico, não decide transformação e não normaliza runs destrutivamente.

Garantias:
- `PARSER-G1`: nunca modifica o pacote original;
- `PARSER-G2`: nenhuma estrutura conhecida ou desconhecida desaparece silenciosamente;
- `PARSER-G3`: não classifica semanticamente conteúdo acadêmico;
- `PARSER-G4`: todo dado é rastreável ao XML físico;
- `PARSER-G5`: conteúdo não representável vira opaco + warning + proteção;
- `PARSER-G6`: ParseResult serializável e determinístico;
- `PARSER-G7 / PATCHER-G1`: parser e patcher compartilham biblioteca/opções XML, namespaces, structural_path e canonicalização.

### 0004 — Estratégia de leitura

**OOXML + lxml autoritativo. `python-docx` apenas auxiliar opcional.**

Justificativa: conservadorismo na decisão exige observação física abrangente. Detectar falhas silenciosas de uma abstração de alto nível exigiria ler o XML de qualquer forma.

### 0005 — Hardening do parser v0.1

Documento: `docs/decisions/0005-parser-v01-hardening.md`.

A auditoria real do código pelo Kimi K3 encontrou um bloqueante e problemas importantes de borda; a arquitetura permaneceu válida. Todos os ajustes do patch mínimo foram incorporados antes da v0.2.

## Parser v0.1 endurecido

Implementação:
- `src/formatador_academico/docx_parser.py`
- `tests/test_docx_parser_v01.py`
- `requirements.txt`

Versão interna atual: **0.1.1**.

Escopo implementado:
- recebe bytes de DOCX;
- abre ZIP/OPC somente em memória;
- SHA-256 do pacote;
- inventário de parts com nome, tamanho, SHA-256 e content type;
- inventário cru de relationships;
- `word/document.xml` via lxml;
- percorre filhos diretos de `w:body`;
- reconhece `paragraph`, `table`, `section_properties`;
- desconhecidos viram `opaque_object` protegido;
- comentários XML e processing instructions viram `non_element_node` protegido;
- tabela ainda não é decomposta;
- parts duplicadas são rejeitadas;
- OOXML Strict/namespaces WordprocessingML não suportados falham explicitamente;
- erros fatais ficam em `errors[]`, warnings em `parse_warnings[]`;
- versões de parser/lxml/libxml2 ficam em `environment`;
- nenhuma extração para filesystem.

### Identidade física

Cada bloco registra:
- `structural_path`;
- `original_index`;
- `canonical_xml`;
- `inherited_xml_attrs` (`xml:space`, `xml:lang`, `xml:base` em escopo);
- `physical_hash`.

`physical_hash` = SHA-256 de uma serialização JSON determinística de `canonical_xml + inherited_xml_attrs`.

O patcher futuro **nunca** reconstrói o documento a partir de `canonical_xml`; atua sempre sobre uma cópia do pacote original.

### Canonicalização

- elementos XML: C14N 1.0 inclusivo com comentários;
- comentário/PI isolado: serialização XML direta determinística sem tail.

A exceção para nós não-elemento é deliberada: durante o hardening, C14N sobre comentário/PI isolado provocou falha do libxml2.

### Structural path v0.1

- escopo dentro de uma única part;
- raiz sem predicado;
- elemento: posição 1-based entre irmãos da mesma tag;
- `w` usa `w:local`;
- namespace estrangeiro usa `{namespace}local`;
- comentário: `comment()[n]`;
- PI: `processing-instruction()[n]`.

## Segurança ZIP/XML já implementada

- `resolve_entities=False`;
- `no_network=True`;
- `remove_blank_text=False`;
- `strip_cdata=False`;
- `recover=False`;
- `huge_tree=False`;
- DTD/DOCTYPE recusado;
- limite de número de parts;
- limite por part;
- limite total descomprimido;
- limite de razão de compressão;
- parts duplicadas recusadas;
- compressão não suportada tem erro próprio.

## Testes atuais

Suíte local endurecida: **11/11 aprovados**.

Inclui:
- documento básico;
- determinismo mesmo input;
- comentário/PI preservados e protegidos;
- part duplicada rejeitada;
- `xml:space` herdado altera hash;
- OOXML Strict falha honestamente;
- body vazio válido;
- document.xml não UTF-8;
- hash físico independente do timestamp do ZIP;
- erros separados de warnings;
- ambiente lxml/libxml2 registrado.

## Auditorias concluídas

1. schema do corpus: Kimi K3;
2. corpus adversarial: Claude Opus;
3. corpus final: Claude Opus;
4. DocumentIR: Kimi K3, APROVAR COM AJUSTES;
5. unidade de trabalho: Kimi K3, APROVAR COM AJUSTES;
6. contrato do parser: Kimi K3, APROVAR COM AJUSTES;
7. estratégia de leitura: Kimi K3 adversarial, APROVAR;
8. primeira fatia v0.1: Kimi K3, APROVAR COM AJUSTES;
9. revisão do código real v0.1: Kimi K3, **APROVAR COM CORREÇÕES**; correções integradas e testadas.

## Regra de revisão técnica

Decisão técnica relevante segue obrigatoriamente:
1. ChatGPT propõe;
2. auditor/modelo adequado revisa;
3. ChatGPT integra;
4. Felipe aprova;
5. decisão é commitada e registrada aqui.

Papéis:
- ChatGPT: arquitetura, integração, decisões e HANDOFF;
- Claude Opus: auditor adversarial de metodologia/segurança;
- Kimi K3: implementação, parsing, DOCX, heurísticas e revisão técnica;
- Felipe: decisão final de produto.

## Próximo passo

**Não escrever v0.2 ainda.** Primeiro definir a menor expansão de cobertura que produza valor técnico sem misturar responsabilidades. Candidatas a comparar: decomposição física de parágrafos/runs ou inclusão de stories secundárias. A proposta deve ser auditada pelo Kimi K3 antes da implementação.
