# HANDOFF — Formatador Acadêmico

## Estado do projeto

**Fase atual:** corpus-base v1 congelado; arquitetura-base do motor fechada; contrato e estratégia do parser DOCX fechados; parser v0.1 endurecido; **parser v0.2 implementado localmente e no GitHub, com 11/11 testes próprios + 5/5 smoke regressions da v0.1 aprovados**. Próxima etapa: revisão técnica do código real da v0.2 antes de abrir stories secundárias.

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

### 0005 — Hardening do parser v0.1

Documento: `docs/decisions/0005-parser-v01-hardening.md`.

A auditoria do código pelo Kimi K3 encontrou um bloqueante e problemas importantes de borda; a arquitetura permaneceu válida. Todos os ajustes mínimos foram incorporados.

### 0006 — Parser v0.2: parágrafos e runs

Documento: `docs/decisions/0006-parser-v02-paragraph-runs.md`.

Escolha aprovada após auditoria do Kimi K3:
- decompor `w:p` antes de abrir stories secundárias;
- `w:pPr` e `w:rPr` permanecem crus;
- `w:r` vira `run_raw`, sem coalescimento;
- containers (`hyperlink`, `ins`, `del`, `fldSimple`, `sdt`, `sdtContent`, `smartTag`) viram `run_container` protegido;
- runs dentro de containers são decompostos recursivamente mantendo path real;
- fragmentos conhecidos são tipados; desconhecidos viram `opaque_fragment` protegido;
- cobertura 1:1 de filhos de `w:p` e `w:r` é testada mecanicamente;
- sem formatação efetiva, herança, análise acadêmica ou patches.

## Parser v0.1 endurecido

Versão interna final da v0.1: **0.1.1**.

Implementa pacote/body, inventário de parts/relationships, proteção ZIP/XML, opacos, comentários/PI, identidade física e erros controlados.

Cada bloco registra:
- `structural_path`;
- `original_index`;
- `canonical_xml`;
- `inherited_xml_attrs` (`xml:space`, `xml:lang`, `xml:base` em escopo);
- `physical_hash`.

`physical_hash` = SHA-256 de serialização JSON determinística de `canonical_xml + inherited_xml_attrs`.

O patcher futuro **nunca** reconstrói o documento a partir de `canonical_xml`; atua sempre sobre uma cópia do pacote original.

Canonicalização:
- elementos XML: C14N 1.0 inclusivo com comentários;
- comentário/PI isolado: serialização XML direta determinística sem tail.

Structural path:
- escopo de uma única part;
- raiz sem predicado;
- posição 1-based entre irmãos da mesma tag/tipo;
- `w` usa `w:local`;
- namespace estrangeiro usa `{namespace}local`;
- comentário `comment()[n]`;
- PI `processing-instruction()[n]`.

## Parser v0.2 implementado

Arquivo principal:
- `src/formatador_academico/docx_parser.py`

Testes novos:
- `tests/test_docx_parser_v02.py`

Versão interna atual: **0.2.0**.

### Parágrafo

Um `paragraph` agora expõe:
- `properties_raw` para o primeiro `w:pPr`;
- `children[]` na ordem física;
- `runs_raw[]` para runs diretos;
- `canonical_xml`, `inherited_xml_attrs`, `physical_hash` do parágrafo inteiro.

O `physical_hash` do parágrafo continua baseado no parágrafo integral, preservando a identidade física estabelecida na v0.1.

### Run

`run_raw` expõe:
- `properties_raw` para `w:rPr`;
- `fragments[]`;
- `children[]` na ordem física;
- `canonical_xml`, `inherited_xml_attrs`, `physical_hash`;
- sem inferir formatação efetiva.

Runs adjacentes nunca são fundidos.

### Containers

`run_container` é recursivo e protegido. Tipos iniciais:
- `w:hyperlink`;
- `w:ins`;
- `w:del`;
- `w:fldSimple`;
- `w:sdt`;
- `w:sdtContent`;
- `w:smartTag`.

O path permanece físico e não achatado, por exemplo:
`/w:document/w:body[1]/w:p[3]/w:hyperlink[1]/w:r[2]`.

### Fragmentos tipados

- `w:t` -> `text`;
- `w:tab` -> `tab`;
- `w:br` -> `break`;
- `w:cr` -> `carriage_return`;
- `w:noBreakHyphen` -> `no_break_hyphen`;
- `w:softHyphen` -> `soft_hyphen`;
- `w:sym` -> `symbol`;
- `w:instrText` -> `instruction_text`;
- `w:delText` -> `deleted_text`.

Qualquer outro filho de run vira `opaque_fragment` protegido. `xml:space`, `xml:lang` e `xml:base` próprios do fragmento são registrados em `xml_attrs`; contexto ancestral continua em `inherited_xml_attrs`.

### Cobertura mecânica

A suíte v0.2 verifica que cada filho de `w:p` e de `w:r` tem exatamente uma representação correspondente, além de testar containers aninhados, paths profundos, fragmentos opacos e ausência de coalescimento.

Resultados locais antes do commit:
- **11/11 testes específicos da v0.2 aprovados**;
- **5/5 smoke regressions das garantias centrais da v0.1 aprovados**.

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
- compressão não suportada tem erro próprio;
- nenhuma extração para filesystem.

## Auditorias concluídas

1. schema do corpus: Kimi K3;
2. corpus adversarial: Claude Opus;
3. corpus final: Claude Opus;
4. DocumentIR: Kimi K3, APROVAR COM AJUSTES;
5. unidade de trabalho: Kimi K3, APROVAR COM AJUSTES;
6. contrato do parser: Kimi K3, APROVAR COM AJUSTES;
7. estratégia de leitura: Kimi K3 adversarial, APROVAR;
8. primeira fatia v0.1: Kimi K3, APROVAR COM AJUSTES;
9. revisão do código real v0.1: Kimi K3, APROVAR COM CORREÇÕES; correções integradas;
10. recorte v0.2 parágrafos/runs: Kimi K3, **APROVAR COM AJUSTES**; cinco ajustes integrados antes da implementação.

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

Submeter a **implementação real da v0.2** ao Kimi K3 para revisão adversarial do código e dos testes. Não abrir footnotes/endnotes/headers/footers/comments antes dessa revisão e das correções eventualmente necessárias.
