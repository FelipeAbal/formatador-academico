# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; parser físico v0.4 congelado; Analysis View v0.1a congelada; **Analysis View v0.1b — Formatting Resolution View — Marco 1 (não-toggle) implementado, auditado, corrigido pelas decisões 0015/0016, mergeado e formalmente congelado pela decisão 0017.**

Validação corrente:
- parser v0.4 congelado: **102/102**;
- baseline congelado parser + v0.1a: **154/154**;
- suíte total após Marco 1 v0.1b: **222/222** reportada em clone fresco do head remoto;
- failures: 0;
- errors: 0;
- skips: 0.

PR #3:
- branch: `analysis-v01b-formatting-m1`;
- head final auditado: `294316174624f7ece7b15d0f12b525a0f538f16d`;
- merge commit: `4850dc264d28b50f5f480888a13662331772417e`.

Próximo passo: implementar **somente o Marco 2 da Analysis View v0.1b**, limitado a `w:b` e `w:i` com semântica toggle correta. Não iniciar outras propriedades nem nova camada antes de congelar o Marco 2.

Este é o HANDOFF corrente. O histórico fica no Git; não criar `handoff_vNN`.

## Regra operacional

**Tudo o que puder ser corrigido com segurança dentro do escopo atual deve ser corrigido antes de avançar.**

Só postergar quando houver expansão explícita de escopo, dependência não resolvida, impossibilidade técnica demonstrada, contradição normativa/arquitetural nova ou novo risco de segurança.

Para trabalho com Kimi:
- mesmo projeto;
- novo chat por etapa técnica grande;
- no início do chat: HANDOFF corrente + commit exato do `main` + tarefa fechada;
- implementação só conta como entregue com branch/commit/PR real ou diff completo;
- estado do GitHub prevalece sobre sandbox/conversa;
- após implementação, auditoria adversarial antes de merge/freeze.

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

## Decisões principais

### 0001–0012 — Physical layer / parser
- OriginalPackage imutável;
- PhysicalIR derivada, serializável e forense;
- saída nunca reconstruída da IR;
- OOXML + lxml autoritativo; python-docx auxiliar;
- `children[]` autoritativo;
- stories secundárias e parse parcial;
- tabelas/nested tables/block containers;
- parser v0.4.0 congelado em `0012-freeze-parser-v04.md`;
- suíte congelada do parser: **102/102**.

### 0013–0014 — Analysis View v0.1a: Normalized Text
Contrato e freeze da Normalized Text View.

Garantias:
- um segmento por fragmento físico;
- `segments[]` autoritativo;
- `default_text` derivado;
- offsets em code points Python;
- zero-width para não participantes;
- opacos relevantes preservados;
- break desconhecido/ilegível não ganha precisão inventada;
- serialização determinística;
- sem lxml vivo;
- PhysicalIR não modificada.

Freeze v0.1a: **154/154** total, incluindo **102/102** parser.

### 0015 — Contrato Analysis View v0.1b
`docs/decisions/0015-analysis-v01b-formatting-resolution-contract.md`

Contrato único dividido em dois marcos internos.

Princípios:
- `styles.xml` fora da PhysicalIR;
- `StyleCatalog` derivado do OriginalPackage e verificado por `part_name + sha256`;
- `RawPropertyBag` como único extrator local de propriedades;
- statuses: `resolved`, `absent`, `unresolved`, `invalid`, `ambiguous`;
- `invalid` terminal por propriedade/slot;
- evidence/provenance completa;
- `docDefaults` na cascade;
- theme refs como valores documentais `resolved`;
- fonts por slots, sem `effective_font` visual;
- Decimal, nunca float;
- falha parcial por `(target, propriedade/slot)`;
- v0.1b ortogonal à v0.1a.

### 0016 — Errata normativa de seleção de styles
`docs/decisions/0016-analysis-v01b-style-selection-errata.md`

Prevalece sobre conflitos da 0015:
- multiple defaults do mesmo tipo: **última ocorrência documental vence** + warning;
- duplicate `styleId`: **primeira ocorrência documental é o referencial normativo** + warning;
- `styleId` ausente = `None`, sem inventar ID;
- style sem ID pode ser default;
- `w:type` ausente => `paragraph`;
- `ambiguous` no Marco 1 fica reservado a duplicate property conflitante sem precedência normativa segura.

### 0017 — Freeze Analysis View v0.1b Marco 1
`docs/decisions/0017-freeze-analysis-v01b-m1.md`

Marco 1 congelado após auditoria do PR #3 e incorporação da 0016.

Implementado:
- `formatting_model.py`;
- `property_bag.py`;
- `style_catalog.py`;
- `formatting.py`;
- testes unitários e E2E.

Propriedades de run congeladas no Marco 1:
- `w:sz`;
- `w:rFonts` por 8 slots;
- `w:lang` por 3 slots;
- `w:u`;
- `w:vertAlign`.

Propriedades de parágrafo congeladas no Marco 1:
- `pStyle`;
- `w:jc`;
- `w:spacing`;
- `w:ind` com cláusula numbering↔indent.

Auditoria final também verificou que a ausência de `rStyle` significa que nenhum character style é aplicado; o resolver não deve aplicar automaticamente o default character style a runs sem `rStyle`.

## Marco 2 — próximo ciclo

Escopo EXCLUSIVO:
- `w:b`;
- `w:i`.

Semântica contratual já fechada:

### Style hierarchy composition
Ordem do menos específico ao mais específico:
`docDefaults -> paragraph style chain (root→child) -> character style chain (root→child)`.

Dentro de styles/docDefaults:
- `true`, `1` ou atributo omitido => **toggle** do estado acumulado;
- `false` ou `0` => **no-op**;
- ausente => herda.

### Direct formatting
No `w:rPr` direto do run:
- `true`, `1` ou omitido => `true` absoluto;
- `false` ou `0` => `false` absoluto;
- direct é terminal e NÃO participa da paridade.

Vetores mínimos obrigatórios:
- docDefaults on -> true;
- parent on + child on -> false;
- parent on + child false -> true;
- paragraph style on + character style on -> false;
- paragraph style on + character style false -> true;
- docDefaults on + paragraph style on -> false;
- docDefaults + paragraph + character on -> true;
- style on + direct on -> true;
- style on + direct false -> false;
- direct inválido -> invalid;
- tudo ausente -> absent.

## Fora do próximo ciclo

Continuam fora:
- demais toggles;
- theme resolution real;
- numbering.xml completo;
- table styles;
- section/page;
- renderer/layout;
- profile acadêmico;
- SafetyGate;
- patching.

## Próximo passo operacional

Abrir **novo chat no Kimi K3** para o Marco 2, porque é um novo marco técnico com semântica qualitativamente diferente.

No novo chat:
1. ler este HANDOFF;
2. ler decisões 0015, 0016 e 0017;
3. confirmar SHA exato do `main`;
4. implementar apenas `w:b`/`w:i` em branch própria;
5. preservar os **222 testes** correntes e adicionar vetores adversariais de toggle;
6. publicar PR real;
7. trazer para auditoria antes de merge/freeze.
