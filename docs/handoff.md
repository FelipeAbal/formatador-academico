# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; arquitetura/contrato do parser fechados; parser v0.1 e v0.2 endurecidos; **parser v0.3 recebeu o hardening integral pós-auditoria e a última aresta de `suspicious_target` foi corrigida. A suíte validada externamente tinha 55/55; o `main` atual contém 56 testes e aguarda uma última execução externa antes do congelamento formal.**

Este é o HANDOFF corrente. O histórico fica no Git; não criar `handoff_vNN`.

## Regra operacional adicional

**Tudo o que puder ser corrigido com segurança dentro do escopo atual deve ser corrigido antes de avançar.**

Só postergar quando houver:
- expansão explícita de escopo;
- dependência ainda não resolvida;
- impossibilidade técnica demonstrada;
- nova decisão arquitetural que exija auditoria própria.

## Objetivo do MVP

Formatar com segurança DOCX acadêmicos existentes a partir de perfil formal explicitamente declarado. Não promete conformidade ABNT genérica.

Saídas:
1. DOCX limpo;
2. DOCX de revisão;
3. relatório.

Princípio: **Na dúvida, marcar.**

## Segurança

- nenhuma invenção/perda substantiva;
- só atuar em subaspecto autorizado;
- ambiguidade não é resolvida silenciosamente;
- opacos são preservados/protegidos;
- Safety Gate é veto, nunca autorização;
- C3 exige revisão humana.

## Corpus congelado v1

- 41 fixtures;
- baseline motor nulo: 20/41 = 48,8%;
- precisão-alvo automática >=99%;
- alto risco desejado >=99,5%;
- tolerância zero a invenção/perda conhecida, dano a campo e alteração indevida de citação direta.

Reabrir apenas por falha de teste, impossibilidade técnica, contradição nova, mudança explícita de contrato/escopo ou novo risco de segurança.

## Arquitetura fechada

### 0001 — DocumentIR
OriginalPackage imutável; IR derivada/serializável; saída nunca reconstruída da IR.

### 0002 — Unidade de trabalho
`DocumentContext -> BlockWorkItem -> Field/Aspect Decisions -> OperationPlan -> SafetyGate -> TransformLog -> XML Patches`

### 0003 — Contrato do parser
Parser físico/forense, sem análise acadêmica ou transformação. Garantias G1-G7: imutabilidade, nenhuma perda silenciosa, rastreabilidade, opacos protegidos, determinismo e convenções compartilhadas com o patcher.

### 0004 — Estratégia DOCX
**OOXML + lxml autoritativo.** `python-docx` apenas auxiliar.

### 0005 — Hardening v0.1
`docs/decisions/0005-parser-v01-hardening.md`

### 0006 — v0.2 parágrafos/runs
`docs/decisions/0006-parser-v02-paragraph-runs.md`

- `w:pPr`/`w:rPr` crus;
- runs forenses sem coalescimento;
- containers recursivos;
- fragments tipados;
- opacos protegidos;
- sem estilo efetivo/herança/análise acadêmica.

### 0007 — Hardening v0.2
`docs/decisions/0007-parser-v02-hardening.md`

- `original_index`: posição 0-based entre todos os filhos do pai;
- `children[]` autoritativo;
- `run_refs[]`/`fragment_refs[]` são paths;
- cobertura 1:1 por paths;
- mixed content sinalizado;
- warnings agregados;
- `bdo`, `dir`, `customXml`;
- fixture de hash fixa;
- determinismo cross-process.

### 0008 — v0.3 stories secundárias
`docs/decisions/0008-parser-v03-secondary-stories.md`

Recorte: footnotes, endnotes, headers, footers e comments.

Decisão estrutural:
**falha de story secundária não derruba o documento**.

Estados de story:
- `ok`;
- `missing`;
- `failed`;
- `rejected`.

Resultado global:
- `ok` se body/pacote e stories secundárias processarem;
- `partial` se alguma story secundária estiver `missing`, `failed` ou `rejected`;
- `failed` para falha fatal do pacote/body ou política global de segurança ZIP.

### 0009 — Hardening v0.3 após auditoria
`docs/decisions/0009-parser-v03-hardening.md`

Revisão do código real pelo Kimi K3 encontrou um bloqueante de semântica de stories, gaps de observabilidade e testes não-portáveis. Todos os itens corrigíveis dentro da v0.3 foram incorporados.

Principais ajustes:
- `story_id = {story_type}:{part}` para toda story secundária;
- `part` é âncora física obrigatória da identidade;
- duas parts do mesmo story type são preservadas + `duplicate_story_type`, nunca falha global;
- `partial_stories[]` no resultado;
- detecção de `w:txbxContent`, `a:txBody` e `p:txBody`;
- warnings para IDs de notes/comments duplicados ou ausentes;
- story schema uniformizado;
- target que escape da raiz lógica do pacote gera `suspicious_target` e story `rejected`;
- naming de órfãs uniformizado;
- `errors[]` global é autoridade; `story.errors[]` é espelho local de conveniência;
- warning codes passam a ser contrato versionado;
- limites ZIP permanecem globais/fatais por decisão de segurança;
- testes v0.2 tornados portáveis entre máquinas e versões posteriores do parser.

## Parser atual

Versão: **0.3.0**

Arquivo:
`src/formatador_academico/docx_parser.py`

### Body e blocos

O dispatch usa `_parse_block_sequence`, reutilizado por body, header/footer e itens de notes/comments.

Parágrafos/runs preservam o contrato v0.2.

Tabelas permanecem integrais e serão a candidata da v0.4.

### Descoberta de stories

Relationships de `word/document.xml` são a autoridade de vínculo, identificados por Type URI.

`Target` relativo é resolvido contra a part de origem. Content type é validação cruzada.

Stories conhecidas por content type e sem relationship são preservadas como órfãs com warning.

Target de story que resolve para fora da raiz lógica do pacote não é tratado como mera ausência: a story fica `rejected`, com erro e warning `suspicious_target`, e nenhuma leitura externa é tentada.

### Footnotes / endnotes / comments

Stories coletivas com `items[]`.

IDs são strings cruas. O parser não corrige nem interpreta valores reservados.

Duplicidade/ausência de ID é sinalizada, sem alterar o conteúdo.

A ligação comment range↔comment continua futura, pois ambos os lados físicos permanecem recuperáveis.

### Headers / footers

Uma story por part. Não inferir seção, primeira página ou par/ímpar.

### Textboxes / text bodies

Ainda não decompostos.

Presença detectada em opacos por:
- `w:txbxContent`;
- DrawingML `a:txBody`;
- PresentationML `p:txBody`.

Gera `textbox_detected`.

### Identidade

Identidade física global deve considerar:
`part + story_id + structural_path + original_index + physical_hash`.

`structural_path` permanece relativo à part.

`original_index` = posição 0-based entre todos os filhos do pai imediato.

`physical_hash` = SHA-256 de JSON determinístico com `canonical_xml + inherited_xml_attrs`.

O patcher nunca reconstrói DOCX a partir de canonical XML.

### Parse parcial e Safety Gate futuro

Story `missing`, `failed` ou `rejected` é região absolutamente não editável.

Documento `partial` pode futuramente permitir patches somente em stories `ok`, desde que o Safety Gate valide identidade/proveniência e ausência de dependência com story indisponível.

`errors[]` no topo é autoritativo. `story.errors[]` é cópia local imutável de conveniência.

## Testes atuais

A última suíte completa **executada externamente** antes da aresta final passou em **55/55**.

O `main` atual acrescenta:
- `tests/test_docx_parser_v03_edges.py`;
- 1 teste dedicado para target suspeito tratado como `rejected`.

Total atual esperado: **56 testes**.

O novo caso exige confirmar:
- `status = partial` no documento;
- story `status = rejected`;
- erro `suspicious_target` no topo e na story;
- `partial_stories` contendo a story rejeitada;
- body permanecendo `ok`.

## Auditorias

1. schema corpus: Kimi K3;
2. corpus adversarial: Claude Opus;
3. corpus final: Claude Opus;
4. DocumentIR: Kimi K3;
5. unidade de trabalho: Kimi K3;
6. contrato parser: Kimi K3;
7. estratégia leitura: Kimi K3;
8. recorte v0.1: Kimi K3;
9. código v0.1: Kimi K3;
10. recorte v0.2: Kimi K3;
11. código v0.2: Kimi K3, APROVAR COM CORREÇÕES;
12. recorte v0.3: Kimi K3, APROVAR COM AJUSTES;
13. código v0.3: Kimi K3, NÃO CONGELAR antes das correções;
14. verificação externa pós-hardening: **55/55, CONGELAR v0.3**, com um único menor não bloqueante (`suspicious_target` aparecendo como `missing`); esse menor foi corrigido depois da verificação e agora requer apenas reexecução da suíte de 56 testes.

## Regra de revisão

Decisão técnica relevante:
1. ChatGPT propõe;
2. auditor adequado revisa;
3. ChatGPT integra;
4. Felipe decide quando necessário;
5. registrar e commitar.

Implementação relevante também passa por revisão técnica antes da próxima fatia.

## Próximo passo

Executar a suíte completa atualizada (**56 testes**) em ambiente externo e confirmar o caso `suspicious_target -> rejected`.

Se verde, **congelar formalmente a v0.3** e abrir o escopo da **v0.4 = decomposição física segura de tabelas**.

Não iniciar v0.4 antes dessa última verificação.
