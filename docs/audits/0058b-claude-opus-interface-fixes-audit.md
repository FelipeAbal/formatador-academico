# Auditoria das correções da interface web — PR #55 (Claude Opus)

**Auditor:** Claude Opus 5
**Data:** 2026-09-12
**Alvo:** PR #55, branch `fix/0058-interface-findings-clean`, head `6d0a14ab6079a5af4efb0c2d02fdbe9a80685e02`
**Base:** `main` @ `4388bfa`
**Diff contra `main`:** 6 arquivos, +364/−28 — `server.py`, `static/app.js`, `static/index.html`, `static/style.css`, testes e contrato 0057
**Suíte executada localmente:** **803 passed, 1 warning, 19.86s**
**Repositório não modificado.** Sondas fora da árvore, contra instâncias efêmeras em porta 0.

**Nota de processo:** não há pedido formal de auditoria versionado para esta etapa. Esta auditoria verifica o PR #55 contra os achados da auditoria `0058-claude-opus-web-interface-audit.md` e procura regressões introduzidas pelas correções.

---

## Veredito

# APROVADO COM AJUSTES OBRIGATÓRIOS

Várias correções estão boas e foram verificadas: `justify`, negrito em três estados, preservação exata do decimal até o parser e o processamento liberado do prazo. Mas **a substituição do `Timer` por um leitor de corpo com prazo introduziu três defeitos na leitura da requisição**, todos reproduzidos: uploads legítimos com pausa de 1 s falham, o prazo do corpo é contornado por gotejamento, e o slowloris na fase de cabeçalhos voltou. Além disso, a mensagem criada para evitar afirmação falsa **afirma algo falso**.

---

## Estado dos achados da auditoria 0058

| Achado | Estado verificado |
|---|---|
| A1 — "justificado" enviava `both` | **corrigido** — `value="justify"` |
| A2 — prazo total cortava o processamento | **corrigido no processamento, com regressão na leitura** — ver B1, B2, B3 |
| I1 — `Number()` arredondava o valor | **corrigido na preservação**; falta validar o lexema — ver I3 |
| I2 — não era possível exigir negrito | **corrigido** — seletor sem regra / ausente / exigido |
| I3 — resultado sem explicação | **parcial, com mensagem falsa** — ver I1 e I2 |
| I4 — `ProfileRef` fixo | **não tratado** |
| M1–M6 | **não tratados** |

---

## 🔴 B1 — Qualquer pausa de 1 s no upload derruba a requisição

**Arquivo:** `web_app/server.py`, `_read_body_bytes`.

**[FATO]** O leitor ajusta o timeout do socket para no máximo 1 s e repete a leitura quando ele expira:

```python
self.connection.settimeout(min(1.0, remaining_time))
try:
    chunk = self.rfile.read(min(64 * 1024, limit - total))
except socket.timeout:
    continue
```

**[FATO]** No CPython, o objeto de arquivo do socket fica **permanentemente inutilizado** depois do primeiro timeout. Em `socket.SocketIO.readinto`:

```python
if self._timeout_occurred:
    raise OSError("cannot read from timed out object")
```

Presente em Python 3.9.6 (`socket.py:700-701`, marcado na `:706`) e em **3.12.13** (`socket.py:717`), a versão usada no CI.

**[FATO] Reproduzido** com um DOCX e um perfil válidos:

```
upload com pausa de 0,3 s no meio do corpo -> HTTP/1.0 200 OK
upload com pausa de 1,5 s no meio do corpo -> HTTP/1.0 500 Internal Server Error  {"error":"internal error"}
request_log: [..., ('POST', 'OSError'), ('POST', 'HTTPStatus.INTERNAL_SERVER_ERROR')]
```

**Impacto:** o `continue` nunca produz uma nova leitura útil. A segunda tentativa levanta `OSError`, que cai no `except Exception` e vira "internal error". Um upload pelo túnel SSH com qualquer oscilação de rede de 1 s, comum em arquivo grande ou conexão doméstica, falha sem explicação.

## 🔴 B2 — O prazo do upload é contornado por gotejamento

**[FATO] Reproduzido** com o prazo de upload reduzido a 2 s e o corpo chegando 1 byte a cada 0,5 s:

```
B) corpo gotejando 1 byte/0,5 s -> (sem resposta) apos 10.0s
```

**[INFERÊNCIA]** O prazo só é conferido **entre** chamadas a `rfile.read(n)`. `BufferedReader.read(n)` repete a leitura internamente até juntar `n` bytes, desde que cada `recv` retorne em menos de 1 s. O código nunca volta ao laço para conferir o prazo.

**B1 e B2 juntos:** uma pausa de 1 s ou mais derruba o cliente legítimo, e um gotejamento abaixo de 1 s contorna o prazo. O mecanismo falha nas duas direções.

## 🔴 B3 — O slowloris na fase de cabeçalhos voltou

**[FATO] Reproduzido** com `max_connections=2` e duas conexões enviando cabeçalhos em gotejamento por 3 s:

```
A) cabecalhos gotejando ha 3 s (prazo de upload=2 s) -> cliente legitimo NEGADO (ConnectionResetError)
```

**[INFERÊNCIA]** O `Timer` removido cobria a thread inteira. O novo prazo cobre **apenas o corpo**. A linha de requisição e os cabeçalhos são lidos por `handle_one_request`, antes de `do_POST`, só com o timeout de 30 s por operação de socket, e a autorização acontece depois disso. Não é preciso token. É o A1 da auditoria final do ciclo 0057, reaberto.

### Correção única para B1, B2 e B3

Manter a ideia do `Timer`, mas **restrita à fase de leitura**:

- armar um prazo absoluto no início de `process_request_thread`;
- **cancelá-lo assim que a leitura terminar**: após os cabeçalhos em `do_GET`, e após o corpo completo em `do_POST`, **antes** de `build_product_from_inputs`;
- manter o timeout por operação de socket em 30 s, sem timeouts curtos em `rfile`. Assim desaparece o estado envenenado de B1;
- ao expirar, o `Timer` fecha o socket, e a leitura em andamento falha e encerra a conexão.

Isso cobre cabeçalhos e corpo contra gotejamento, não derruba pausas legítimas dentro do prazo e deixa o processamento livre. É exatamente a separação de fases pedida na auditoria 0058.

---

## 🟠 I1 — A mensagem de `quiescent` afirma algo falso

**Arquivo:** `static/app.js:93-95`.

**[FATO]** Para `quiescent`, a tela mostra: *"Processamento concluído. Nenhuma alteração automática segura foi necessária. Isso não significa conformidade integral."*

**[FATO] Reproduzido** com três parágrafos em negrito e a regra "negrito ausente":

```
HTTP 200 | session_status=quiescent | applied=3 | unapplied=0
a tela mostraria: "Processamento concluído. Nenhuma alteração automática segura foi necessária. ..."
```

**[INFERÊNCIA]** `quiescent` significa que **não restou** alteração automática segura ao final, e não que nenhuma foi necessária. A tela afirma que nada precisou mudar enquanto oferece para download um DOCX com três alterações aplicadas. A frase criada para impedir afirmação falsa afirma algo falso.

**Correção:** *"Não restaram alterações automáticas seguras a aplicar"*, seguido das contagens de aplicadas, em revisão, não aplicadas e abstenções.

## 🟠 I2 — `operation_limit_reached` aparece como "Processamento concluído"

**[FATO] Reproduzido** com `max_applied_operations=1` e três alterações necessárias:

```
HTTP 200 | session_status=operation_limit_reached | applied=1 | unapplied=2
a tela mostraria: "Processamento concluído. Status técnico da sessão: operation_limit_reached."
```

**[FATO]** O contrato 0057 §6, **alterado por este mesmo PR**, diz: *"O resultado `operation_limit_reached` será mostrado como limite atingido, nunca como processamento concluído sem ressalvas."*

**Correção:** uma mensagem própria por status — `operation_limit_reached` como limite atingido, com alterações pendentes; `quiescent_with_unapplied` como alterações identificadas e não aplicadas.

## 🟠 I3 — Lexema numérico sem validação gera JSON inválido

**Arquivo:** `static/app.js:22-23` — o valor de `control.value.trim()` é inserido cru no JSON.

**[FATO]** Na fronteira congelada:

```
1.5                   -> aceito
1.5e0 / 1E0           -> aceito
.5                    -> ProfileInputContractError: json_invalid
1.0000000000000000001 -> ProfileInputUnsupportedError: line_spacing_exponent_unsupported
```

**[INFERÊNCIA]** Pela especificação HTML, `.5` é um *valid floating-point number*. Por isso `<input type="number">` o mantém em `.value`, e ele passa pela restrição `min="0.01" step="0.01"` da entrelinha. Não executei isso num navegador. O JSON gerado é inválido e o usuário recebe a recusa genérica.

**Ponto positivo verificado:** a preservação exata está correta. `1.0000000000000000001` chega ao parser e é recusado como não suportado, em vez de ser arredondado. A correção de I1 da auditoria 0058 funciona. Faltou apenas a validação de lexema recomendada.

**Correção:** validar com `^[0-9]+(\.[0-9]+)?$` antes de inserir, com mensagem em português quando falhar.

## 🟠 I4 — Os testes novos verificam texto, não comportamento

**Arquivo:** `tests/test_web_app_server_v01.py`.

**[FATO]** Os testes acrescentados procuram trechos nos bytes estáticos:

- `assertNotIn(b"Number(control.value)", ...)` — passa com `parseFloat(control.value)` ou `Number( control.value )`;
- `assertIn(b'value="justify">justificado', ...)` — fixa uma opção em vez de extrair todos os `<option value>` e validá-los contra `_ALIGNMENT_VALUES`;
- `assertIn(b"Isso n\xc3\xa3o significa conformidade integral", ...)` — **garante a presença da mensagem falsa de I1**.

**[INFERÊNCIA]** Nenhum teste exercita upload com pausa, gotejamento de corpo ou de cabeçalhos, processamento mais longo que o prazo, ou validade do JSON gerado pelo formulário. Por isso a suíte passa com 803 testes, e com B1, B2, B3, I1, I2 e I3 presentes.

**Correção:** substituir as buscas de texto por testes de comportamento, a começar pelas quatro sondas desta auditoria, que cabem como testes da suíte.

## 🟠 I5 — Trabalho órfão sem cancelamento nem limite

**[INFERÊNCIA]** Sem o `Timer` e com o padrão da tela em `max_applied_operations=10000`, fechar a aba ou recarregar a página não interrompe o processamento. A thread segue consumindo CPU e segurando uma vaga de conexão até o pipeline terminar. O mecanismo foi reproduzido na auditoria 0058, onde o pipeline continua depois da queda do cliente. Com ~6,8 s por alteração, um documento grande roda por horas, e algumas tentativas repetidas esgotam as 32 vagas.

**Correção:** limitar processamentos simultâneos, por exemplo a um ou dois, separadamente das vagas de conexão, e recusar os excedentes com mensagem clara. Rever também o padrão da tela à luz do custo medido.

## 🟠 I6 — `ProfileRef` fixo continua

`app.js:31` segue com `{"id":"web-interface","version":"1"}`. O I4 da auditoria 0058 não foi tratado: regras diferentes produzem proveniência idêntica.

---

## 🟡 Menores

- **M1–M5 da auditoria 0058 continuam abertos:**
  - CSP sem `form-action 'none'` e `base-uri 'none'`;
  - revogação dos Blob URLs;
  - mensagens de erro cruas em inglês e token obsoleto sem instrução; o resumo segue exibindo as chaves técnicas em inglês e a cobertura como JSON cru;
  - falta `Cross-Origin-Resource-Policy: same-origin` nos estáticos;
  - falta o teste do arquivo extra na pasta `static/`.
- **M6 — o formato do log depende da versão do Python.** `log_request` grava `str(code)`, que no Python 3.9 vira `"HTTPStatus.OK"` (verificado no `request_log`) e no 3.11+ vira `"200"`. Gravar `int(code)`.
- **M7 — prazo e limite de corpo incoerentes.** `DEFAULT_UPLOAD_TIMEOUT_SECONDS = 30` com `DEFAULT_MAX_BODY_BYTES = 64 MiB` exige cerca de 17 Mbit/s sustentados pelo túnel. Dimensionar os dois juntos.
- **M8 — o histórico do PR tem deleção e restauração em massa.** `ebbadf8` tem a árvore sem 204 arquivos, `6d0a14a` restaura +40.311 linhas, e `cd7ba50` e `ede617a` são commits vazios de CI. **Mesclar por squash**, senão `git blame` e `git bisect` atravessam a deleção e a restauração.
- **M9 — branches.** `fix/0058-interface-findings`, sem o sufixo `-clean`, é a publicação incompleta: em relação à `-clean`, faltam nela 204 arquivos. **Não mesclar; apagar.** Também podem ser apagadas `docs/auditoria-0057-final-opus`, `docs/close-0057-handoff` (#49), `fix/0057-final-audit-findings` (#50), `implement-0057-processing` (#47) e, resolvido o #55, `implement/0058-web-interface` (#51, fechado).

---

## O que está correto e deve ser preservado

- **`justify`**, o valor aceito pelo perfil, no lugar de `both`.
- **Negrito em três estados**, cobrindo o vocabulário que o núcleo já suporta.
- **Decimal preservado até a fronteira congelada.** O valor digitado não é mais reescrito em ponto flutuante; o parser decide a representabilidade.
- **Processamento fora do prazo de leitura.** A intenção de A2 foi atingida para o processamento; o que falhou foi a leitura.
- **Verificação de regra vazia** antes do envio, com mensagem em português.
- **`max_applied_operations`** igual ao padrão do núcleo, conforme o contrato.
- **Superfície pública intacta:** lista fechada, igualdade exata sobre a linha de requisição bruta, `Host` antes de tudo, CSP e cabeçalhos.
- **Sem `innerHTML`**, e perfil transportado como `Blob` opaco.
- **URL impressa com o token no fragmento.**
- 803 testes verdes, verificados de forma independente.

---

## Sequência recomendada

**Antes do merge:**

1. **B1, B2 e B3** — prazo absoluto armado no início da thread e cancelado ao fim da leitura, sem timeouts curtos em `rfile`, com testes de pausa, gotejamento de corpo e gotejamento de cabeçalhos;
2. **I1 e I2** — mensagens por status fiéis ao significado de cada um e ao contrato;
3. **I4** — trocar as buscas de texto por testes de comportamento;
4. **M8** — mesclar por squash.

**Antes de uso com usuários:**

5. **I3** — validação de lexema;
6. **I5** — limite de processamentos simultâneos;
7. **I6** — versão do perfil derivada do conteúdo.

**Quando convier:** M1–M7 e M9.
