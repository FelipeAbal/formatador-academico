# Auditoria do contrato 0057 — interface web local v0.1 (Claude Opus)

**Auditor:** Claude Opus 5
**Data:** 2026-09-11
**Alvo:** PR #45, branch `decision-0057-local-web-interface`, head `893f5e3c7b4bf413412448626475784007ec38da`
**Base:** `cc1e9f6` (ciclo 0056 fechado)
**Diff:** 173 linhas, apenas `docs/decisions/0057-local-web-interface-v01-contract.md`; nenhum código de produção alterado.
**Repositório não modificado durante a auditoria.**

---

## Veredito

# APROVADO COM AJUSTES

A direção está certa e o contrato acerta o principal: a interface não calcula conformidade, não reconstrói artefatos e não substitui validação de domínio. Há **três achados bloqueantes**, todos de preenchimento — nenhum exige redesenhar a proposta.

---

## 🔴 A1 — A interface ignora a camada de entrega já congelada (0047/0048)

**Seção:** §4 e §10.3.

**[FATO]** O contrato propõe compor `build_product_from_inputs` + `render_processing_report`. Mas `build_product_delivery(bundle, *, base_name)` já existe e, em `product_delivery/builder.py`:

- linha 115: **já chama `render_processing_report(bundle.processing_report)`**;
- linhas 116-117: **já verifica** `rendered.processing_report_ref == bundle.processing_report_ref`, falhando com `ProductDeliveryIntegrityError`;
- linha 97: **já gera os nomes** por `filename_for_role(base, role)`;
- produz **cinco** arquivos tipados com media types, tamanhos e hashes, mais `manifest.json`.

**[INFERÊNCIA]** Seguindo §4 como está, a interface teria de inventar nomes de arquivo — exatamente a lógica que 0047 congelou, incluindo sanitização de base name, rejeição de travessia, nomes ocultos e nomes reservados do Windows. Perderia o `manifest.json` e a verificação de lineage entre relatório humano e bundle. E chamaria `render_processing_report` uma segunda vez, duplicando o que a camada de entrega já faz.

Além disso, §4 lista **quatro** saídas; a entrega congelada tem **cinco**.

**Correção:** §4 deve nomear `build_product_delivery` como a fronteira de saída. A interface fornece apenas o `base_name` — derivado do nome do arquivo enviado e sanitizado pelo próprio `canonicalize_delivery_base_name`, nunca por regra própria — e serve os cinco `DeliveryFile` como estão. Resposta direta à pergunta 6: **sim, pode usar a fronteira pública sem duplicar regras — mas a fronteira correta é `build_product_delivery`, não o par proposto.**

---

## 🔴 A2 — `127.0.0.1` não é autorização; falta barreira de origem

**Seção:** §5.

**[FATO]** O contrato exige "não aceitar conexões externas ao próprio Ubuntu", o que o bind satisfaz. Não há autenticação, token ou verificação de origem.

**[INFERÊNCIA]** Duas superfícies ficam abertas:

1. **Navegador do Mac.** O túnel SSH torna o serviço *local para o navegador*. Qualquer página aberta nesse navegador pode fazer `POST http://localhost:8000` — é o ataque clássico contra servidores de desenvolvimento ligados a localhost. Um site qualquer pode enviar documentos e, se os downloads tiverem URL previsível, ler resultados. O bind não protege contra isso, porque a requisição parte de dentro.
2. **Outros processos ou usuários do Ubuntu.** Qualquer um alcança `127.0.0.1:8000` sem credencial.

Resposta direta à pergunta 2: **restringir a 127.0.0.1 é necessário e não é suficiente.**

**Correção, e pertence ao contrato, não à instalação:**

- token de sessão gerado no arranque, impresso no console junto com a URL e exigido em toda requisição;
- verificação de `Origin` e `Sec-Fetch-Site`, recusando requisições cross-site;
- verificação de `Host` contra um conjunto esperado;
- recusa de métodos não previstos;
- identificadores de download imprevisíveis e ligados ao token.

---

## 🔴 A3 — Perfil como objeto aninhado em JSON destrói a rejeição de chaves duplicadas

**Seção:** §3.2 e §11 (primeira questão aberta).

**[FATO]** `parse_profile_input_json` recebe **bytes** e rejeita chaves duplicadas em todos os níveis — invariante congelada em 0040/0042, cuja razão declarada é que declaração normativa ambígua é erro de contrato, nunca "last wins".

**[INFERÊNCIA]** Se o perfil viajar como objeto aninhado dentro de um JSON externo, o `json.loads` do envelope **colapsa as duplicatas silenciosamente** antes que o parser congelado veja qualquer coisa. A garantia desaparece sem nenhum sinal:

```json
{"docx_base64": "...",
 "profile": {"rules": {"body": {"bold": {...}, "bold": {...}}}}}
```

O parser externo resolve para um único `bold`; o boundary recebe um perfil aparentemente íntegro e aceita. A mesma erosão atinge BOM, encoding e campos desconhecidos, todos validados sobre os **bytes originais**.

**Correção:** o perfil deve chegar como **bytes opacos** e ser entregue ao parser sem reserialização — parte multipart com `application/json`, ou string base64 decodificada e repassada intacta. **Nunca** como objeto aninhado no envelope.

---

## 🟠 I1 — JSON versus multipart, e a dívida de stdlib (perguntas 3 e 11)

Com A3 resolvido, base64 em JSON é viável, mas custa +33% de tamanho, mantém a string inteira em memória e acrescenta um decode. Multipart é o transporte natural e é o que `<input type="file">` já produz.

**[FATO]** A ressalva de stdlib é concreta: o módulo `cgi`, parser multipart histórico da biblioteca padrão, está deprecado e **foi removido no Python 3.13** (PEP 594). O CI usa 3.12 (`.github/workflows`), então funciona hoje e quebra no próximo upgrade.

**Correção:** decidir explicitamente e registrar a razão, porque as duas opções têm dívida — multipart com parser mínimo próprio sobre o módulo `email`, ou base64 em JSON com o perfil como string opaca. Recomendo multipart sobre `email`: evita o inchaço do base64 e não depende de um módulo em remoção.

Resposta à pergunta 11: **sim, começar só com a biblioteca padrão é adequado** para um serviço local de usuário único, desde que as duas ressalvas acima e a de I4 estejam escritas.

---

## 🟠 I2 — §6 e §9.4 se contradizem: limpar bytes ao fim da requisição versus permitir download

**[FATO]** §6 exige "limpar referências aos bytes do documento ao final da requisição". §4 e §9.4 exigem baixar os artefatos.

**[INFERÊNCIA]** Downloads são requisições posteriores; os bytes precisam sobreviver entre requisições. Uma implementação fiel a §6 torna §9.4 impossível.

**Correção — escolher e escrever:**

- **(a)** devolver tudo numa única resposta e montar os downloads no navegador a partir dela — mantém §6 verdadeiro;
- **(b)** reter em memória com chave de sessão e TTL explícito, reescrevendo §6 para descrever a política real de retenção;
- **(c)** ZIP único — **excluído**, porque 0047 rejeitou ZIP explicitamente.

Recomendo (a), que é a única que preserva a promessa de §6 sem ficção.

---

## 🟠 I3 — Limite de tamanho em aberto, e o custo dominante não é o tamanho

**Seção:** §3.1, §11 (segunda questão aberta).

**[INFERÊNCIA]** Dois problemas distintos:

1. **Memória.** `http.server` lê o corpo inteiro em memória, e o pipeline mantém simultaneamente bytes de entrada, clean, review, report JSON e as árvores lxml de cada iteração — vários múltiplos do arquivo.
2. **Tempo, que é o problema maior.** A auditoria 0056 mediu ~6,8 s **por alteração**, e `processing_session` refaz o pipeline completo a cada patch aplicado. O custo escala com o **número de correções**, não com o tamanho do arquivo. Uma tese com centenas de parágrafos divergentes leva dezenas de minutos. Um limite de bytes não protege contra isso.

**Correção:** além do limite de corpo HTTP, expor `max_applied_operations` — já parâmetro de `build_product_from_inputs` — como limite de trabalho, e tratar `operation_limit_reached` como resultado de primeira classe na tela, não como sucesso silencioso.

---

## 🟠 I4 — Servidor bloqueante durante minutos

**[INFERÊNCIA]** Com `HTTPServer` de thread única, a rota de saúde do §10.1 não responde durante o processamento e o navegador pode expirar antes do fim. Não é falha de segurança; é usabilidade previsível dado I3.

**Correção:** `ThreadingHTTPServer` (também stdlib), resposta imediata com consulta de estado, ou no mínimo registrar a limitação como premissa aceita. Resposta à pergunta 11 fica condicionada a isto.

---

## 🟡 M1 — "Abstenções" precisa mapear para uma família real do relatório

**Seção:** §4.5.

**[FATO]** As famílias do `ProcessingReport` são `applied_changes`, `unapplied_changes`, `review_items` e `classification_items`.

**[INFERÊNCIA]** "Abstenções" presumivelmente é `classification_items`, mas o contrato não diz. Sem a correspondência explícita, a interface pode inventar uma quinta categoria ou contar duas vezes.

**Correção:** nomear a correspondência literal no §4.

---

## 🟡 M2 — Critérios de aceitação só parcialmente testáveis (pergunta 9)

**[FATO]** Dos dez critérios do §9: 1 e 2 são ambientais; 10 depende de seis DOCX privados que, por decisão do próprio contrato, não entram no Git — logo não é reproduzível em CI; 8 só é verificável negativamente.

**Correção:** separar em duas listas — **automatizáveis** (3, 4, 5, 6, 7, 9 mais os adversariais abaixo) e **checklist manual de instalação** (1, 2, 8, 10), com o resultado do checklist registrado no handoff em vez de no CI.

---

## 🟡 M3 — Falta o correlato positivo da proibição de afirmar conformidade (pergunta 10)

**[FATO]** §6 já proíbe "afirmar conformidade integral apenas porque o processamento terminou". Correto e necessário.

**[INFERÊNCIA]** Falta o outro lado. Um documento que retorna `quiescent` com zero itens será lido como "conforme" por qualquer usuário, e isso é exatamente a falsa promessa que o projeto evitou por doze ciclos. O contrato congelado diz que `quiescent` significa ausência de automação segura restante, não conformidade — e as exclusões do slice (listas com `numPr`, bidi, stories secundárias, tabelas) saem como abstenção.

**Correção:** a interface deve exibir sempre, junto com as contagens, o status da sessão e uma linha de cobertura — quantos alvos ficaram fora do slice automático e por quê. "0 itens para revisão" sem essa linha é uma afirmação de conformidade por omissão.

---

## Respostas diretas

| # | Pergunta | Resposta |
|---|---|---|
| 1 | Ubuntu servidor + Mac cliente por SSH é coerente? | **Sim.** Mantém documentos fora da internet, reaproveita canal já autenticado, não cria superfície de credencial nova, e coloca o trabalho na máquina com mais CPU e memória — o que importa dado I3. Ressalva: é justamente o túnel que torna o serviço "local" para o navegador, habilitando A2; a coerência não dispensa a verificação de origem |
| 2 | `127.0.0.1` é suficiente? | **Não.** Necessário, não suficiente — ver A2 |
| 3 | JSON ou multipart? | **Multipart**, com o perfil como parte opaca. Se ficar em JSON, o perfil precisa ser string base64 repassada intacta — ver A3 e I1 |
| 4 | Riscos de memória, tamanho, temporários, persistência, vazamento? | Ver I2 e I3. O risco maior não é tamanho, é tempo; e a contradição de retenção precisa ser resolvida |
| 5 | Respeita as decisões congeladas? | **Quase.** A1 é a exceção: ignora 0047/0048 |
| 6 | Pode usar as fronteiras públicas sem duplicar regras? | **Sim**, usando `build_product_delivery` — ver A1 |
| 7 | Saídas completas e coerentes com o bundle? | **Não.** São cinco arquivos com manifest, não quatro — ver A1 |
| 8 | Formulário deve gerar Profile Input v0.3? | **Sim, sem incompatibilidade.** O 0.3 cobre exatamente `bold`, `font_size`, `alignment` e `line_spacing` para `body` e `heading`, que é o formulário proposto. A regra de ausência do §3.2 está correta. O cuidado é de transporte, não de schema — A3 |
| 9 | Critérios testáveis? | **Parcialmente** — ver M2 |
| 10 | Risco de afirmar conformidade? | **Sim, por omissão** — ver M3 |
| 11 | Só biblioteca padrão? | **Sim**, condicionado a I1 e I4 |
| 12 | Testes adversariais | Abaixo |

---

## Testes adversariais exigidos antes da implementação (pergunta 12)

**Transporte e autoridade do perfil**
1. perfil com chave duplicada preservado ponta a ponta → **rejeitado pelo boundary** (prova de A3);
2. perfil com BOM, UTF-16 ou bytes UTF-8 inválidos → rejeitado;
3. perfil com campo desconhecido → rejeitado;
4. perfil `schema_version` 0.1 ou 0.2 declarando `line_spacing` → rejeitado.

**Superfície HTTP**
5. POST com `Origin` de outro site → recusado;
6. requisição sem token de sessão → recusada;
7. `Host` inesperado → recusado;
8. método não previsto → recusado;
9. corpo acima do limite → recusado **sem** materializar tudo em memória;
10. download com identificador de outra sessão → negado.

**Entrada**
11. arquivo vazio, arquivo não-ZIP, ZIP que não é DOCX;
12. DOCX válido com perfil inválido → **nenhum processamento do documento** (critério 9.6), verificável pela ausência de parse;
13. `base_name` com travessia, nome oculto ou nome reservado do Windows → sanitizado pela camada congelada, exercitado pela interface.

**Honestidade do resultado**
14. documento que gera zero alterações → a interface **não** afirma conformidade (M3);
15. `operation_limit_reached` exibido como tal, não como sucesso;
16. erro de contrato ou integridade do núcleo → superfície de erro, nunca 200;
17. bytes dos artefatos servidos **idênticos** aos do `ProductDelivery`, provando que a interface não reconstrói nada.

**Retenção**
18. concluída a sessão, nenhum resíduo do documento em disco (varredura de temporários);
19. duas requisições concorrentes → sem vazamento de bytes entre sessões.

---

## Ajustes que devem entrar no contrato antes da implementação

1. **A1** — `build_product_delivery` como fronteira de saída; cinco arquivos, não quatro; `base_name` sanitizado pela camada congelada;
2. **A2** — token de sessão, verificação de `Origin`/`Sec-Fetch-Site`/`Host`, identificadores de download imprevisíveis, tudo no contrato;
3. **A3** — perfil transportado como bytes opacos, entregue ao parser sem reserialização;
4. **I1** — decidir multipart versus base64 e registrar a razão, com a nota sobre a remoção do `cgi` em 3.13;
5. **I2** — resolver a contradição entre limpar bytes e permitir download;
6. **I3** — fixar limite de corpo **e** expor `max_applied_operations`, tratando `operation_limit_reached` como resultado de primeira classe;
7. **I4** — `ThreadingHTTPServer` ou premissa registrada;
8. **M1** — mapear "abstenções" para `classification_items`;
9. **M2** — separar critérios automatizáveis de checklist manual;
10. **M3** — exibir status da sessão e linha de cobertura junto com as contagens.

Os três primeiros são bloqueantes. Do quarto ao décimo evitam retrabalho, mas não impedem começar pelo item 10.1 da sequência.
