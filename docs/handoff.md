# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; arquitetura e contrato do parser fechados; parser DOCX v0.2 implementado e endurecido após revisão adversarial do código real. **18/18 testes específicos da v0.2 aprovados localmente** após as correções. Próximo passo: definir e auditar a v0.3 para stories secundárias.

Este é o HANDOFF corrente. O histórico anterior fica no Git; não criar `handoff_vNN`.

## Objetivo do MVP

Formatar com segurança DOCX acadêmicos existentes a partir de perfil formal explicitamente declarado. Não promete conformidade ABNT genérica. Fonte operacional da verdade: perfil ativo.

Saídas: DOCX limpo, DOCX de revisão e relatório de processamento.

Princípio: **Na dúvida, marcar.**

## Segurança

- nenhuma invenção ou perda substantiva;
- só atuar em subaspecto autorizado;
- subaspecto sem regra ativa é preservado;
- portão de conservação é veto, nunca autorização;
- campo extra não pode ser descartado;
- conteúdo ambíguo não é resolvido silenciosamente;
- C3 exige revisão humana.

## Corpus congelado v1

- 41 fixtures: 40 base + RC3-01;
- baseline motor nulo: 20/41 = 48,8%;
- precisão-alvo de edição automática >=99%;
- alto risco desejado >=99,5%;
- tolerância zero a invenção/perda conhecida, dano a campo ou alteração indevida de citação direta.

Só reabrir por falha de teste, impossibilidade técnica demonstrada, nova contradição, mudança explícita de escopo/contrato ou novo risco de segurança.

## Decisões arquiteturais

### 0001 — DocumentIR
`OriginalPackage` imutável é fonte física da verdade. IR é derivada/serializável. A saída nunca é reconstruída da IR.

### 0002 — Unidade de trabalho
`DocumentContext -> BlockWorkItem -> Field/Aspect Decisions -> OperationPlan -> SafetyGate -> TransformLog -> XML Patches`

### 0003 — Contrato do parser
Parser físico/forense, sem análise acadêmica ou transformação. Garantias G1-G7: imutabilidade, nenhuma perda silenciosa, rastreabilidade, opacos protegidos, determinismo e convenções compartilhadas com o patcher.

### 0004 — Estratégia DOCX
**OOXML + lxml autoritativo.** `python-docx` apenas auxiliar opcional.

### 0005 — Hardening v0.1
Documento: `docs/decisions/0005-parser-v01-hardening.md`.

Incluiu proteção contra comentários/PI, parts duplicadas, contexto `xml:*`, erros controlados, versões lxml/libxml2, namespace Strict e convenções de structural path/hash.

### 0006 — Parser v0.2: parágrafos e runs
Documento: `docs/decisions/0006-parser-v02-paragraph-runs.md`.

- `w:pPr` e `w:rPr` crus;
- `w:r` forense, sem coalescimento;
- containers recursivos com path físico real;
- fragmentos conhecidos tipados, desconhecidos opacos/protegidos;
- sem formatação efetiva, herança, análise acadêmica ou patches.

### 0007 — Hardening v0.2 pós-auditoria
Documento: `docs/decisions/0007-parser-v02-hardening.md`.

Revisão Kimi K3: **APROVAR COM CORREÇÕES**, nenhum bloqueante. Ajustes incorporados:

- `original_index` = posição 0-based entre todos os filhos do pai imediato em qualquer profundidade;
- `structural_path` mantém posição 1-based entre irmãos da mesma tag/tipo;
- `children[]` é a árvore autoritativa;
- `run_refs[]` e `fragment_refs[]` são referências por `structural_path`, não cópias completas;
- cobertura 1:1 é validada por multiconjunto de paths;
- `mixed_content_text` para texto/tail inesperado;
- warnings repetitivos agregados com `count` e `sample_paths`;
- `bdo`, `dir`, `customXml` adicionados aos run containers;
- `duplicate_run_properties` específico para `w:rPr` duplicado;
- fixture de hash esperado fixo;
- determinismo testado entre processos com `PYTHONHASHSEED` diferentes usando os mesmos bytes DOCX.

## Identidade física

Cada nó físico relevante registra:
- `structural_path`;
- `original_index`;
- `canonical_xml`;
- `inherited_xml_attrs`;
- `physical_hash`.

Algoritmo atual de `physical_hash`:
SHA-256 de JSON determinístico contendo `canonical_xml + inherited_xml_attrs`.

**Migração:** hashes antigos baseados apenas em C14N não são comparáveis com o algoritmo atual. Comparações entre versões devem usar `canonical_xml` + contexto/versionamento, não igualdade cega de hash.

Canonicalização:
- elementos: C14N 1.0 inclusivo com comentários;
- comentário/PI isolado: serialização XML direta determinística sem tail.

O patcher futuro nunca reconstrói DOCX a partir de `canonical_xml`; opera sobre cópia do pacote original.

## Parser v0.2 atual

Versão: `0.2.0`.

### Parágrafo
- `properties_raw`;
- `children[]` na ordem física, fonte autoritativa;
- `run_refs[]` somente referências;
- `canonical_xml`, contexto `xml:*`, hash físico.

### Run
- `properties_raw`;
- `children[]` na ordem física;
- `fragment_refs[]` somente referências;
- sem inferir formatação efetiva.

### Run containers reconhecidos
`hyperlink`, `ins`, `del`, `fldSimple`, `sdt`, `sdtContent`, `smartTag`, `bdo`, `dir`, `customXml`.

Containers são protegidos; runs internos são decompostos recursivamente para preservar ordem textual e path real.

### Fragmentos tipados
`w:t`, `w:tab`, `w:br`, `w:cr`, `w:noBreakHyphen`, `w:softHyphen`, `w:sym`, `w:instrText`, `w:delText`.

Outros filhos de run ficam como `opaque_fragment` protegido. `fldChar` continua legitimamente opaco na v0.2.

## Limitações conhecidas e aceitas

- tabelas continuam bloco único; candidata a v0.4;
- containers em nível de body podem continuar opacos;
- markers inline zero-width (bookmark/proofErr/perm/comment ranges) podem permanecer opacos na v0.2;
- stories secundárias ainda não são abertas;
- proteção contextual de runs dentro de `ins/del` deve ser respeitada pela futura Analysis View.

## Segurança ZIP/XML

XXE/rede desabilitados, DOCTYPE recusado, sem `recover`, sem `huge_tree`, limites de parts/tamanho/razão de compressão, parts duplicadas recusadas, compressão não suportada com erro próprio, nenhuma extração em filesystem.

## Auditorias concluídas

1. schema corpus — Kimi K3;
2. corpus adversarial — Claude Opus;
3. corpus final — Claude Opus;
4. DocumentIR — Kimi K3, aprovar com ajustes;
5. unidade de trabalho — Kimi K3, aprovar com ajustes;
6. contrato parser — Kimi K3, aprovar com ajustes;
7. estratégia leitura — Kimi K3, aprovar;
8. primeira fatia v0.1 — Kimi K3, aprovar com ajustes;
9. código real v0.1 — Kimi K3, aprovar com correções; integradas;
10. recorte v0.2 — Kimi K3, aprovar com ajustes; integrados;
11. código real v0.2 — Kimi K3, **aprovar com correções**; integradas nesta etapa.

## Regra de revisão técnica

Decisão técnica relevante:
1. ChatGPT propõe;
2. auditor adequado revisa;
3. ChatGPT integra;
4. Felipe aprova quando for decisão de produto/arquitetura não rotineira;
5. decisão é registrada e commitada.

Auditorias técnicas rotineiras e correções diretamente decorrentes de decisão já aprovada podem ser executadas sem nova autorização intermediária, conforme orientação de Felipe.

## Próximo passo

**v0.3 = stories secundárias**, reutilizando o parser já endurecido de parágrafo/run. Antes do código, fechar o menor recorte de stories e submetê-lo ao Kimi K3. Tabelas ficam para etapa posterior, provavelmente v0.4.
