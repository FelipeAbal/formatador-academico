# Auditoria completa — interface web local, PR #51 (Claude Opus)

**Auditor:** Claude Opus 5
**Data:** 2026-09-12
**Alvo:** PR #51, branch `implement/0058-web-interface`, head `9a1af9317ed56c912011590b59736e9f2d71e54d`
**Base:** `main` @ `4388bfa` (achados finais da auditoria 0057 fechados)
**Diff:** +295/−7 — `server.py` (56), `static/app.js` (95), `static/index.html` (71), `static/style.css` (17), testes (55), contrato 0057 (8)
**Suíte executada localmente:** **801 passed, 1 warning, 23.41s**
**Repositório não modificado.** Sondas fora da árvore, contra instâncias efêmeras em porta 0.

**Nota de processo:** não havia pedido formal de auditoria no git para esta etapa — o único brief versionado é `0056-performance-index-audit-brief.md`. Esta auditoria cobre o PR #51 e incorpora os achados levantados sobre `main` desde a auditoria final do ciclo 0057.

---

## Veredito

# APROVADO COM AJUSTES OBRIGATÓRIOS

A superfície pública foi implementada com precisão — lista fechada, igualdade exata sobre a linha de requisição bruta, conteúdo carregado no arranque, `Host` validado antes de tudo — e o token segue o modelo acordado. **Dois achados bloqueiam o merge**, ambos reproduzidos: a tela não consegue declarar texto justificado, e qualquer documento real cujo processamento passe de 30 segundos falha.

---

## 🔴 A1 — "Justificado" envia `both`, que o Profile Input 0.3 recusa

**Arquivo:** `static/index.html:33` e `:51` (`<option value="both">justificado</option>`); `profile_input/model.py:27`.

**[FATO]** O vocabulário congelado desde a 0049 é:

```python
_ALIGNMENT_VALUES = frozenset({"left", "center", "right", "justify"})
```

`both` é o token OOXML de escrita; `justify` é o valor user-facing. A tela envia o token interno.

**[FATO] Reproduzido** com o perfil exato que `app.js` monta:

```
alignment "both"    (opção "justificado" da tela)  -> 422 {"error":"document or profile was rejected"}
alignment "justify" (vocabulário do 0.3)           -> 200
alignment "left"    (opção "esquerda")             -> 200
```

**Impacto:** texto justificado é a regra de alinhamento mais comum em trabalho acadêmico, e é exatamente a única opção de alinhamento que falha. O usuário recebe uma recusa genérica sem indicação da causa. Nenhum dos 801 testes pega isso, porque nenhum teste liga o HTML ao parser congelado.

**Correção:** `value="justify"` nas duas ocorrências; e um teste que extraia todos os `<option value>` de `data-property="alignment"` do `index.html` e verifique que o conjunto não vazio está contido em `_ALIGNMENT_VALUES`. É a mesma lição do teste de exemplos JSON dos contratos: artefato que produz entrada precisa ser validado contra o parser real.

---

## 🔴 A2 — O prazo total de 30 s derruba o processamento legítimo

**Arquivo:** `web_app/server.py:356-364` (em `main`, herdado pelo PR).

**[FATO]** O `Timer` introduzido para fechar o A1 da auditoria final envolve o `process_request_thread` inteiro — leitura do upload, `build_product_from_inputs`, `build_product_delivery` e escrita da resposta:

```python
def process_request_thread(self, request, client_address):
    deadline = Timer(DEFAULT_REQUEST_TIMEOUT_SECONDS, self._expire_request, (request,))
    deadline.start()
    try:
        super().process_request_thread(request, client_address)
    finally:
        deadline.cancel()
        self._connection_slots.release()
```

**[FATO] Reproduzido em escala reduzida** — prazo de 2 s, processamento simulado de 4 s:

```
cliente: FALHA RemoteDisconnected apos 2.0s
pipeline ainda rodando no momento da queda do cliente: True
pipeline terminou 4.0s apos o inicio -> trabalho continuou sem ninguem esperando
```

**[INFERÊNCIA]** Em escala real, o prazo é 30 s e a auditoria 0056 mediu ~6,8 s **por alteração**, com o pipeline refeito a cada patch. Um documento com cinco ou seis correções já estoura. A tela agrava: o padrão de `max_applied_operations` em `index.html:58` é **1000**.

Três consequências simultâneas:

1. o usuário vê "Processando…" virar um erro de rede do navegador após 30 s, sem explicação;
2. o `Timer` fecha só o socket — **o pipeline continua**, consumindo CPU até o fim, sem destinatário;
3. durante todo esse tempo a thread **segura uma vaga do semáforo**. Algumas tentativas repetidas pela tela esgotam as 32 vagas com trabalho órfão.

É uma regressão: a correção do slowloris derrubou também o caso de uso central da tela.

**Correção:** separar os prazos.

- **prazo total apenas para ler a requisição**, até o fim do corpo — é ele que fecha o slowloris;
- **processamento sem esse prazo**, ou com limite próprio muito maior, coerente com `max_applied_operations`;
- **escrita** com o timeout por operação de socket que já existe;
- teste com processamento mais longo que o prazo de leitura, verificando que a resposta chega.

E rever o padrão `1000` da tela à luz do custo medido.

---

## 🟠 I1 — O JavaScript arredonda o valor declarado antes do parser exato

**Arquivo:** `static/app.js:22` — `Number(control.value)` seguido de `JSON.stringify`.

**[FATO]** Verificado com o motor JavaScript:

```
"1.5"                     -> {"v":1.5}
"1.0000000000000000001"   -> {"v":1}
"11.25000000000000001"    -> {"v":11.25}
"0.30000000000000004"     -> {"v":0.30000000000000004}
```

**[INFERÊNCIA]** O Profile Input existe para preservar exatamente o que o usuário declarou — `Decimal` exato, forma canônica, rejeição de não representável sem arredondamento (0040, 0041, 0051). A tela reescreve o valor em ponto flutuante binário **antes** de ele chegar à fronteira. Uma entrelinha digitada como `1.0000000000000000001` chega como `1` e é aceita como uma linha simples: o valor declarado mudou e ninguém foi avisado. É a classe de defeito que a errata 0041 fechou no Patcher, reaberta no navegador.

**Correção:** validar o lexema no JavaScript com expressão regular estrita (`^[0-9]+(\.[0-9]+)?$`) e inserir o **texto original** como número literal no JSON montado, sem passar por `Number`. A fronteira congelada continua sendo quem decide representabilidade.

---

## 🟠 I2 — A tela não consegue exigir negrito

**Arquivo:** `static/index.html:24`, `:42`; `static/app.js:19-20`.

**[FATO]** O controle é um checkbox rotulado "Negrito ausente" que só emite `{"mode":"exact","value":false}`. Desmarcado, não há regra. **[FATO]** O schema aceita `value: true` — verificado, 200.

**[INFERÊNCIA]** "Títulos em negrito" é uma das regras mais comuns em normas de trabalho acadêmico e é inexpressível pela tela. Não há risco de norma inventada — a ausência continua ausência —, mas a interface não cobre o vocabulário que o núcleo já suporta.

**Correção:** controle de três estados — *sem regra* / *exigir negrito* / *exigir sem negrito*.

---

## 🟠 I3 — A tela apresenta o resultado sem explicar o que ele significa

**Arquivo:** `static/app.js:35-44`, `:86-87`.

**[FATO]** A tela exibe `Sessão: quiescent` e despeja as chaves técnicas do `summary` em inglês — `applied_change_count`, `abstained_count`, `story_coverage` serializado como JSON cru.

**[INFERÊNCIA]** O M3 da auditoria do contrato 0057 pedia o correlato positivo da proibição de afirmar conformidade: explicar que `quiescent` significa ausência de automação segura restante, não documento conforme, e mostrar a cobertura. Nenhuma das duas coisas está na tela. Para um usuário acadêmico, "Sessão: quiescent" com `review_item_count: 0` é lido como "está tudo certo" — a falsa promessa que o projeto evita há doze ciclos. O relatório humano em Markdown tem a explicação, mas é um download que a pessoa pode nunca abrir.

**Correção:** rótulos em português; frase fixa junto ao status explicando o significado de `quiescent`; destaque visual para itens em revisão, não aplicados e abstenções; mensagem própria para `operation_limit_reached`.

---

## 🟠 I4 — Todo perfil gerado pela tela tem a mesma identidade

**Arquivo:** `static/app.js:30` — `profile: { id: "web-interface", version: "1" }`.

**[INFERÊNCIA]** Qualquer combinação de regras produz o mesmo `ProfileRef`. Relatórios gerados com regras diferentes ficam com proveniência idêntica. A auditoria do contrato 0040 registrou como limitação conhecida que "mudança substantiva sem bump de `profile.version` é indetectável"; a tela transforma essa limitação de caso raro em **comportamento de todo uso**.

**Correção:** derivar `version` de um hash do JSON canônico das regras — determinístico, sem inferência, e distingue perfis diferentes na proveniência.

---

## 🟡 Menores

- **M1 — CSP sem `form-action` e `base-uri`.** O formulário não tem `method` nem `action`. Se `app.js` não carregar, o envio nativo faz `GET /?document=nome.docx`, colocando o nome do arquivo na URL e no histórico (a requisição em si cai em 401). Acrescentar `form-action 'none'; base-uri 'none'` à CSP e `method="post"` ao formulário.
- **M2 — Blob URLs.** Revogados 1 s após o primeiro clique, então um segundo clique quebra o link; os não clicados nunca são revogados e retêm na aba cópias decodificadas do DOCX limpo e do de revisão.
- **M3 — Mensagens de erro cruas.** Erros do servidor em inglês são exibidos como vieram. Um token obsoleto — `sessionStorage` sobrevivendo a reinício do servidor — mostra "session token required" sem instruir a reabrir a URL impressa. A queda pelo `Timer` (A2) mostra a mensagem de rede do navegador.
- **M4 — Sem `Cross-Origin-Resource-Policy`.** Uma página de outra origem pode incluir `<script src="http://localhost:8000/static/app.js">`. Verificado por leitura que é inofensivo — executa no contexto do atacante, sem token, e `form` nulo lança exceção na primeira linha útil —, mas `Cross-Origin-Resource-Policy: same-origin` nos três recursos é defesa gratuita.
- **M5 — Falta o teste do arquivo extra.** A implementação não é servidor por prefixo — três `joinpath` literais —, então é estruturalmente impossível hoje. O teste que crie um arquivo na pasta `static/` e verifique que ele não fica acessível é a trava contra uma refatoração futura para `startswith`.
- **M6 — Branches acumuladas.** Quatro podem ser apagadas: `docs/auditoria-0057-final-opus` (conteúdo já em `main`), `docs/close-0057-handoff` (#49), `fix/0057-final-audit-findings` (#50) e `implement-0057-processing` (#47). Manter `main` e `implement/0058-web-interface`.

---

## O que está correto e deve ser preservado

- **Superfície pública fechada.** Três rotas por igualdade exata, comparadas contra a linha de requisição **bruta** (`_request_target` sobre `raw_requestline`), não contra `self.path`. O conteúdo é carregado uma vez no arranque a partir dos recursos do pacote, sem acesso ao sistema de arquivos derivado do caminho. A armadilha do prefixo foi evitada.
- **`Host` validado antes de qualquer outra coisa**, inclusive nas rotas públicas.
- **Cabeçalhos**: CSP com `default-src 'none'` e `frame-ancestors 'none'`, `nosniff`, `no-referrer`, `DENY`, `no-store`.
- **Testes adversariais da superfície**: travessia, `%2e%2e`, query string, `//`, `/static/`, arquivo inexistente, host inesperado e métodos.
- **Token**: fragmento → `sessionStorage` → `replaceState`, nessa ordem, antes de qualquer uso; nunca `localStorage`. O contrato registra corretamente os limites do `replaceState` e o motivo do túnel.
- **Sem `innerHTML`**: resumo e nomes de arquivo passam por `textContent` e `createElement`. Não há vetor de injeção a partir do relatório ou do nome do arquivo.
- **Perfil opaco**: `app.js` envia o JSON como `Blob` `application/json`, preservando o transporte por bytes que mantém a rejeição de chaves duplicadas.
- **Achados da auditoria final corrigidos em `4388bfa`**: seleção por `DeliveryRole`, nome do tipo da exceção no log, base de nome vazia, HEAD sem corpo, `message.defects`.
- 801 testes verdes, verificados de forma independente.

---

## Sequência recomendada

**Antes do merge:**

1. **A1** — `value="justify"` e teste do HTML contra `_ALIGNMENT_VALUES`;
2. **A2** — separar prazo de leitura do processamento, com teste de processamento longo, e rever o padrão `1000`.

**Antes de uso com usuários:**

3. **I3** — explicação de `quiescent`, cobertura e rótulos em português;
4. **I1** — lexema numérico preservado sem `Number`;
5. **I2** — negrito em três estados;
6. **I4** — versão do perfil derivada do conteúdo.

**Quando convier:** M1–M6.
