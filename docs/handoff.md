# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; parser físico v0.4 congelado; Analysis View v0.1a congelada; **Analysis View v0.1b — Formatting Resolution View — Marcos 1 e 2 implementados, auditados, mergeados e formalmente congelados.**

Validação corrente:
- parser v0.4: **102/102**;
- baseline parser + v0.1a: **154/154**;
- após Marco 1 v0.1b: **222/222**;
- após Marco 2 v0.1b: **267/267**;
- failures: 0;
- errors: 0;
- skips: 0.

PR #3 — Marco 1:
- branch: `analysis-v01b-formatting-m1`;
- head final auditado: `294316174624f7ece7b15d0f12b525a0f538f16d`;
- merge commit: `4850dc264d28b50f5f480888a13662331772417e`;
- freeze: decisão 0017.

PR #4 — Marco 2:
- branch: `analysis-v01b-formatting-m2`;
- base: `48b1a08468c076a3891e8592ca804623556ca847`;
- head final auditado: `d681e49512932d127840f1102ed8f18b272d2c6e`;
- merge por squash: `db5a2f98445c80a686d209e635710f72dc36b72f`;
- freeze: decisão 0018.

Este é o HANDOFF corrente. O histórico fica no Git; não criar `handoff_vNN`.

## Regra operacional

**Tudo o que puder ser corrigido com segurança dentro do escopo atual deve ser corrigido antes de avançar.**

Só postergar quando houver expansão explícita de escopo, dependência não resolvida, impossibilidade técnica demonstrada, contradição normativa/arquitetural nova ou novo risco de segurança.

Fluxo formal:
1. ChatGPT propõe;
2. modelo apropriado audita;
3. ChatGPT integra;
4. Felipe aprova quando necessário;
5. HANDOFF + decisão/commit.

Para trabalho com Kimi:
- mesmo projeto;
- novo chat por etapa técnica grande;
- no início: HANDOFF + SHA exato do `main` + tarefa fechada;
- implementação só conta com branch/commit/PR real ou diff completo;
- estado do GitHub prevalece sobre sandbox/conversa;
- auditoria adversarial antes de merge/freeze.

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
- OOXML + lxml autoritativo;
- `children[]` autoritativo;
- stories secundárias, parse parcial, tabelas, nested tables e block containers;
- parser v0.4.0 congelado em `0012-freeze-parser-v04.md`;
- suíte do parser: **102/102**.

### 0013–0014 — Analysis View v0.1a: Normalized Text
Congelada com:
- um segmento por fragmento físico;
- `segments[]` autoritativo;
- `default_text` derivado;
- offsets em code points Python;
- zero-width para não participantes;
- opacos preservados;
- sem falsa precisão em breaks;
- serialização determinística;
- sem lxml vivo;
- PhysicalIR imutável.

### 0015 — Contrato Analysis View v0.1b
- `styles.xml` fora da PhysicalIR;
- `StyleCatalog` derivado do OriginalPackage e verificado por `part_name + sha256`;
- `RawPropertyBag` único extrator de propriedades;
- statuses `resolved`, `absent`, `unresolved`, `invalid`, `ambiguous`;
- evidence/provenance completa;
- `docDefaults` na cascade;
- theme refs documentais `resolved`;
- fonts por slots, sem `effective_font` visual;
- Decimal, nunca float;
- falha parcial por propriedade/slot;
- v0.1b ortogonal à v0.1a.

### 0016 — Errata normativa de seleção de styles
- multiple defaults do mesmo tipo: última ocorrência documental vence + warning;
- duplicate `styleId`: primeira ocorrência documental é o referencial normativo + warning;
- `styleId` ausente = `None`;
- style sem ID pode ser default;
- `w:type` ausente => `paragraph`;
- `ambiguous` não é usado para essas anomalias.

### 0017 — Freeze v0.1b Marco 1
Congeladas propriedades:

Run:
- `w:sz`;
- `w:rFonts` 8 slots;
- `w:lang` 3 slots;
- `w:u`;
- `w:vertAlign`.

Paragraph:
- `pStyle`;
- `w:jc`;
- `w:spacing`;
- `w:ind` com cláusula numbering↔indent.

Também congelado: run sem `rStyle` não recebe default character style automaticamente.

### 0018 — Freeze v0.1b Marco 2
`docs/decisions/0018-freeze-analysis-v01b-m2.md`

Congelados:
- `w:b`;
- `w:i`.

Semântica:

#### Styles/docDefaults
Ordem:
`docDefaults -> paragraph root→specific -> character root→specific`

- omitido/`1`/`true`/`on` => toggle;
- `0`/`false`/`off` => no-op;
- lexical inválido, inclusive `w:val=""`, => `invalid`.

#### Direct formatting
- omitido/`1`/`true`/`on` => `true` absoluto;
- `0`/`false`/`off` => `false` absoluto;
- direct é terminal e nunca participa da paridade.

#### Outros invariantes
- tudo ausente => `absent`, nunca `resolved false`;
- duplicate semanticamente idêntico => aplica uma vez + warning;
- duplicate conflitante => `ambiguous`;
- cycle relevante sem direct => `unresolved(style_cycle)`;
- direct terminal pode resolver apesar de cycle inferior;
- evidence segue ordem real de composição;
- multi-evidence não recebe falsa causalidade em `winning_evidence`.

Auditoria do PR #4 encontrou e corrigiu desalinhamento `visited`/`levels` em cycle com style sem `styleId`.

Suíte final: **267/267**; regressões anteriores **222/222 preservadas**.

## Estado da Analysis View

Para o escopo contratado, a Analysis View está agora fechada:

1. v0.1a — texto normalizado;
2. v0.1b Marco 1 — formatação não-toggle;
3. v0.1b Marco 2 — bold/italic toggle.

Ela responde a fatos documentais; não decide conformidade acadêmica e não autoriza mutação.

## Fora do escopo atual

Continuam fora:
- demais toggles (`bCs`, `iCs`, strike, caps etc.);
- theme resolution visual real;
- numbering.xml completo;
- table styles;
- section/page;
- renderer/layout;
- patching;
- profile acadêmico aplicado;
- SafetyGate aplicado.

## Próximo passo

**Abrir o ciclo da camada de decisão/comparação entre fatos documentais resolvidos e o perfil formal ativo.**

Primeiro passo obrigatório: contrato/arquitetura, sem código.

Questões centrais da próxima etapa:
- unidade de decisão (`target + aspect`);
- como ligar PhysicalIR/Analysis View ao perfil P1–P27;
- diferença entre fato documental, regra ativa, decisão e autorização;
- statuses de decisão (`compliant`, `needs_change`, `flag`, `abstain`, etc.) sem antecipar OperationPlan;
- regras ausentes/ambíguas/variantes aceitas;
- provenance da regra e da evidência documental;
- separação estrita entre Decision Engine e SafetyGate;
- como preservar IA1–IA13 e IB1–IB2;
- testes mínimos contra o corpus-base congelado.

Não implementar mutação nem patching antes desse contrato ser fechado e auditado.