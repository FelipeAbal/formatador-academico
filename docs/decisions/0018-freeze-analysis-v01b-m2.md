# 0018 — Freeze Analysis View v0.1b Marco 2

**Status:** CONGELADA

## Contexto

A Analysis View v0.1b — Formatting Resolution View foi definida na decisão 0015, corrigida normativamente na 0016 e teve seu Marco 1 congelado na 0017.

O Marco 2 tinha escopo exclusivo de resolver `w:b` e `w:i` com semântica toggle correta no WordprocessingML, sem expandir para outras propriedades.

## Implementação

PR #4 — `analysis-v01b-formatting-m2`

Base auditada:
`48b1a08468c076a3891e8592ca804623556ca847`

Head inicial auditado:
`7759e6c0d4670c6940ecfe08d012a9e3630b20a5`

Head final após auditoria/correções:
`d681e49512932d127840f1102ed8f18b272d2c6e`

Merge por squash:
`db5a2f98445c80a686d209e635710f72dc36b72f`

## Contrato congelado

### Direct formatting

No `w:rPr` direto do run:
- atributo `w:val` omitido, `1`, `true`, `on` => `true` absoluto;
- `0`, `false`, `off` => `false` absoluto;
- valor lexical inválido, inclusive `w:val=""`, => `invalid`;
- direct é terminal e nunca participa de paridade toggle.

### Style hierarchy composition

Ordem do menos específico para o mais específico:

`docDefaults -> paragraph style chain root→specific -> character style chain root→specific`

Dentro de styles/docDefaults:
- atributo omitido, `1`, `true`, `on` => toggle do estado acumulado;
- `0`, `false`, `off` => no-op;
- ausência => herda estado corrente.

### Ausência

Se nenhuma fonte declara a propriedade:
- `status = absent`;
- `value = None`.

Nunca inferir `resolved false` apenas porque o estado interno inicial é falso.

### Duplicatas

No mesmo container:
- declarações semanticamente equivalentes => uma aplicação + `formatting_duplicate_property`;
- declarações conflitantes => `ambiguous` + warning.

Não aplicar dois toggles por causa de duplicata física equivalente.

### Cycles

- cycle relevante sem direct terminal => `unresolved(reason=style_cycle)`;
- direct presente e válido continua terminal e resolve a propriedade;
- cadeia de evidence não pode descartar níveis não pertencentes ao cycle.

### Character style default

Run sem `rStyle` não recebe automaticamente default character style.

## Modelo público

`ResolvedRunFormatting` passa a incluir:
- `bold: ResolvedValue`;
- `italic: ResolvedValue`.

A versão da formatting view passa a `0.1b-m2`.

## Auditoria adversarial

A auditoria do PR #4 encontrou um ponto importante:

- desalinhamento entre `visited` e `levels` na detecção de cycles quando havia style sem `styleId`; isso podia remover da cadeia níveis não pertencentes ao cycle.

Correção aplicada no mesmo PR:
- `visited` passou a permanecer paralelo a `levels`, inclusive com `None`;
- dois testes adversariais foram adicionados: ordem de evidence e cycle após default anônimo.

Não houve bloqueadores restantes.

## Validação final

Suíte final real em clone fresco do head remoto:
- **267 testes**;
- **267 passes**;
- **0 failures**;
- **0 errors**;
- **0 skips**.

Regressões congeladas anteriores:
- **222/222 preservadas**.

Determinismo:
- serialização byte-idêntica em múltiplos `PYTHONHASHSEED`;
- suíte completa verde sob seeds diferentes.

Imutabilidade:
- PhysicalIR não modificada;
- package bytes não modificados;
- StyleCatalog não modificado;
- modelos de saída frozen;
- sem lxml vivo na saída.

## Escopo fora deste freeze

Continuam fora:
- `w:bCs`, `w:iCs` e demais toggles;
- theme resolution real;
- numbering.xml completo;
- table styles;
- section/page;
- renderer/layout;
- profile acadêmico;
- Decision Engine;
- OperationPlan/SafetyGate;
- patching.

## Regra de reabertura

Reabrir o Marco 2 somente por:
- falha de teste;
- contradição normativa nova;
- impossibilidade técnica demonstrada;
- mudança explícita de escopo/contrato;
- novo risco de segurança.

## Próxima etapa

A Analysis View v0.1b está encerrada para o escopo contratado dos Marcos 1 e 2.

O próximo ciclo deve definir a camada de **decisão/comparação entre fatos documentais resolvidos e o perfil formal ativo**, sem ainda aplicar mudanças ao DOCX.