# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; Parser físico v0.4 congelado; Analysis v0.1a/v0.1b congeladas; Decision Vocabulary v0.1 congelado; Decision Layer v0.1 congelada em 0021; Classification Layer v0.1 congelada em 0023; OperationPlan v0.1 congelado em 0025; SafetyGate v0.1 congelado em 0027; Patcher/Applicator v0.1 congelado em 0029; TransformLog / Execution Record v0.1 congelado em 0031; **Processing Session / Orchestration v0.1 implementado, auditado, mergeado e congelado em 0033**.

Este é o HANDOFF corrente. O histórico fica no Git; não criar `handoff_vNN`.

### SHA corrente do `main` antes desta atualização

`acefa7f338cc4e626fc6ce2b139021801909cd27`

Esse commit é o freeze 0033. A presente atualização do HANDOFF gera um novo SHA documental, sem alterar contratos congelados.

## Validação corrente

- parser v0.4: **102/102**;
- Analysis completa: **267/267**;
- Decision Layer v0.1: **290/290**;
- Classification Layer v0.1: **335/335**;
- OperationPlan v0.1: **389/389**;
- SafetyGate v0.1: **442 testes descobertos** no freeze próprio;
- Patcher v0.1: **502/502 OK** no freeze próprio;
- TransformLog v0.1: **524/524 OK** no freeze próprio;
- Processing Session / suíte completa atual: **565/565 OK**;
- GitHub Actions verde no PR #11 e no `main` pós-merge;
- failures: 0;
- errors: 0;
- CI agora elimina a dependência de Kimi pago apenas para execução da suíte.

## PRs / freezes principais

- PR #3 — Analysis v0.1b Marco 1; freeze 0017;
- PR #4 — Analysis v0.1b Marco 2; freeze 0018;
- PR #5 — Decision Layer v0.1; squash `b81f628a0358cbc9483e9207d4f749ea4a2ca475`; freeze 0021;
- PR #6 — Classification Layer v0.1; squash `736c33036224562549b1b5cb026bd6bfdfd2e112`; freeze 0023;
- PR #7 — OperationPlan v0.1; squash `1c11d08dcd6fc219bb2f4e0ce5321db027a5801a`; freeze 0025;
- PR #8 — SafetyGate v0.1; squash `d47b8e67d2788eb1912ef951ec7dcedb457376cb`; freeze 0027;
- PR #9 — Patcher v0.1; squash `559cf8ec812320d066e8b91d431873f7a91f2c1c`; freeze 0029;
- PR #10 — TransformLog v0.1; squash `eff4770f2f5ec848d0f5d6b9afb6b2cdfdc8e355`; freeze 0031;
- PR #11 — Processing Session v0.1; head final auditado `20717d2b36f180644675bbc1720357de1e8aa2a6`; squash `17b0a37529012a0873c76f27c1072ce297240f5d`; freeze 0033.

## Regra operacional

**Tudo o que puder ser corrigido com segurança dentro do escopo atual deve ser corrigido antes de avançar.**

Só postergar quando houver expansão explícita de escopo, dependência não resolvida, impossibilidade técnica demonstrada, contradição normativa/arquitetural nova ou novo risco de segurança.

Fluxo formal:
1. ChatGPT propõe;
2. modelo apropriado audita quando necessário;
3. ChatGPT integra;
4. Felipe aprova quando necessário;
5. HANDOFF + decisão/commit.

### Uso de modelos / custo

- ChatGPT: integração, arquitetura, metodologia, auditoria estática, GitHub e HANDOFF.
- Claude Opus: auditoria adversarial de alto risco quando houver ganho real.
- Kimi K3: implementação pesada ou auditoria técnica especializada somente quando necessário.
- GitHub Actions: execução normal da suíte; não gastar Kimi só para testar.

Para Kimi:
- novo chat por etapa técnica grande;
- começar com HANDOFF + SHA exato do `main` + tarefa fechada;
- GitHub remoto é fonte de verdade;
- implementação só conta com branch/commit/PR real ou diff completo;
- nunca confiar em claim de testes/PR sem inspeção independente.

## Objetivo do MVP

Formatar com segurança DOCX acadêmicos existentes a partir de perfil formal explicitamente declarado. Não promete conformidade ABNT genérica.

Saídas previstas:
1. DOCX limpo;
2. DOCX de revisão;
3. relatório de processamento.

Princípio: **Na dúvida, marcar.**

## Segurança congelada

- nenhuma invenção/perda substantiva;
- só atuar em subaspecto autorizado;
- ambiguidade não é resolvida silenciosamente;
- opacos são preservados/protegidos;
- SafetyGate é veto, nunca autorização;
- C3 exige revisão humana;
- precision > coverage na classificação;
- abstention correta é sucesso seguro;
- stale plan/document drift detectado antes de patch;
- patcher só executa GateClearedOperation;
- snapshot hash e target physical_hash são revalidados antes da mutação;
- mutação mínima + allowed-delta + postcondition Analysis obrigatórios;
- OriginalPackage/snapshot de entrada nunca é mutado in-place;
- TransformRecord existe apenas para patch `APPLIED` e é proveniência, nunca autorização;
- Processing Session nunca cria autoridade normativa nova nem reutiliza token stale.

## Pipeline real congelado até 0033

```text
current DOCX bytes
→ Parser
→ StyleCatalog / Analysis
→ Classification
→ Decision
→ OperationPlan
→ SafetyGate
→ no máximo 1 GateClearedOperation
→ Patcher
→ PatchResult
→ TransformRecord se APPLIED
→ novo snapshot
→ pipeline completo novamente
→ quiescência segura
```

## Slice automático atual

Somente:

```text
P1 / run / bold
P2 / run / font_size
```

Classes executáveis do ProcessingProfile v0.1:

```text
body
heading
```

Ainda fora do slice automático:
- P3 spacing patching;
- P4 alignment patching;
- italic patching;
- long_quote/reference execution;
- tables/containers/numbering execution;
- secondary-story execution;
- structural MOVE/INSERT/MERGE;
- styles.xml mutation;
- review/highlight DOCX;
- relatório user-facing.

## Processing Session / Orchestration v0.1 — 0032 + freeze 0033

API pública:

```text
process_document(
    package_snapshot: bytes,
    profile: ProcessingProfile,
    *,
    max_applied_operations: int = 10000,
) -> ProcessingSessionResult
```

### Perfil mínimo

```text
RuleBinding:
    target_class
    target_type
    rule: FormattingRule

ProcessingProfile:
    profile_ref: ProfileRef
    bindings: tuple[RuleBinding, ...]
```

Não é o schema final de perfil/UI.

Restrições congeladas:
- target_type == run;
- target_class body|heading;
- apenas P1/bold e P2/font_size;
- uma binding por identidade `(target_class,target_type,aspect_id,property_slot)`;
- caller order não resolve conflitos;
- bold usa bool exato;
- font_size usa Decimal em pt;
- profile_id/profile_version/rule_id não vazios.

### Ordem e rerun

- ordem física de parágrafos/runs;
- bindings em ordem canônica dentro do run;
- OperationPlan serialization order não define application order;
- após cada APPLIED, todo o pipeline é reconstruído;
- tokens do gate anterior são descartados.

### Rejeições e bloqueios

Patcher rejection legítima pode virar finding final apenas para:
- `noncanonical_run_properties`;
- `duplicate_target_property`;
- `unrepresentable_value`.

`snapshot_hash_mismatch` e `unsupported_operation` dentro da sessão são integrity errors, não findings normais.

Gate blocked nunca chega ao Patcher. Bloqueio local não impede progresso independente.

### Status técnico

```text
quiescent
quiescent_with_unapplied
operation_limit_reached
```

`quiescent` significa apenas que não há mais automação segura executável. NÃO significa documento plenamente conforme; pode haver review, human_choice, preserve, abstention e conteúdo fora do escopo.

### Resultado final

`ProcessingSessionResult` preserva:
- processing_session_version;
- status;
- profile_ref;
- input_package_sha256;
- output_package_sha256;
- output_package_bytes;
- transforms;
- final_classifications;
- final_decisions;
- findings.

Final classifications e Decisions pertencem ao snapshot final. Findings precisam ligar a uma final Decision `deterministic_change` e ao mesmo target.

Transform chain é obrigatoriamente contígua do input SHA ao output SHA.

### Determinismo / limites

- default `max_applied_operations = 10000`;
- cycle por package SHA repetido = `ProcessingSessionIntegrityError`;
- sem filesystem/network/clock/random/LLM no runtime;
- mesmo input/profile/budget produz mesma semântica e mesmos output bytes no runtime suportado;
- caller binding order não muda resultado.

### Partial parser

Classification congelada exige PhysicalIR `status == ok`. Processing Session v0.1 herda essa exigência. Parser `partial`, inclusive por story secundária defeituosa, não é silenciosamente bypassado.

## Corpus-base v1

- 41 fixtures;
- baseline motor nulo: 20/41 = 48,8%;
- precisão-alvo automática >=99%;
- alto risco desejado >=99,5%;
- tolerância zero a invenção/perda conhecida, dano a campo e alteração indevida de citação direta.

## Dívidas registradas

### Não bloqueadoras imediatas
- schema final de perfil/UI;
- heading-level rules;
- analysis/classification versions ainda como assertions do orchestrator;
- possível pipeline-context hash;
- profile content hash;
- equivalência semântica de DOCX reempacotado byte-diferente;
- P3/P4 patching;
- italic patching;
- long_quote/reference executáveis;
- story_id/part/original_index para stories secundárias;
- partial-story isolation;
- secondary-story execution;
- multi-operation transaction/rollback;
- persistence/resume;
- styles.xml patching;
- exception telemetry;
- performance optimization para muitos sequential patches;
- review/highlight DOCX;
- Processing Report user-facing.

### Dívida importante antes de uso amplo

`w:szCs` não é modelado/mutado no slice font_size. O sistema NÃO deve prometer correção visual completa de complex-script enquanto esse subaspecto não tiver contrato próprio. `w:szCs` permanece intacto.

## Próximo passo operacional

**Processing Report v0.1 — contrato primeiro.**

Objetivo do próximo ciclo: transformar exclusivamente os artefatos machine-readable já congelados da `ProcessingSessionResult` em um relatório determinístico, explicável e útil ao usuário, sem criar nova verdade normativa.

O relatório deverá distinguir claramente, no mínimo:
- alterações efetivamente aplicadas (`TransformRecord`);
- alterações determinísticas que ficaram bloqueadas/rejeitadas (`SessionFinding`);
- itens que exigem revisão/human choice (`final_decisions`);
- abstentions/non-applicability relevantes (`final_classifications`);
- resumo técnico da sessão e hashes de origem/saída.

Ainda NÃO implementar DOCX de revisão/highlight no mesmo ciclo. Primeiro congelar a fronteira e a semântica do Processing Report v0.1.
