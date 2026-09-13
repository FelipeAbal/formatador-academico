# Reauditoria das correções da interface web — PR #55 (Claude Opus)

**Auditor:** Claude Opus 5
**Data:** 2026-09-12
**Alvo:** PR #55, branch `fix/0058-interface-findings-clean`, head `b0516c690fb67863335fc38efc5136c315b5732d`
**Auditoria anterior:** `0058b-claude-opus-interface-fixes-audit.md`, sobre `6d0a14a`
**Mudança desde a auditoria anterior:** um commit, `b0516c6` ("fix: bound request headers and honor HEAD semantics"), em `web_app/server.py` (+48/−21) e `tests/test_web_app_server_v01.py` (+10). O diretório `static/` está **idêntico** ao de `6d0a14a`.
**Base:** `main` @ `4388bfa`
**Suíte executada localmente:** **804 passed, 1 warning, 22.00s**
**Repositório não modificado.** Sondas fora da árvore, contra instâncias efêmeras em porta 0.

---

## Veredito

# APROVADO COM AJUSTES OBRIGATÓRIOS

**Os três bloqueantes da auditoria anterior estão corrigidos**, e verifiquei isso reexecutando as mesmas sondas. O novo desenho, com um `Timer` armado em `handle_one_request` e cancelado antes do processamento, está conceitualmente certo. Mas ele criou **um bloqueante novo**: o `Timer` só é cancelado dentro dos `do_*`. Conexões que nunca chegam lá mantêm uma thread viva por 30 s **fora do teto de conexões**. Os achados de frontend da auditoria anterior continuam todos abertos, porque `static/` não mudou.

---

## Estado dos achados da auditoria 0058b

| Achado | Estado | Evidência |
|---|---|---|
| B1 — pausa de 1 s derrubava o upload | **corrigido** | pausa de 1,5 s → `200 OK` |
| B2 — prazo contornado por gotejamento de corpo | **corrigido** | 1 byte/0,5 s com prazo de 2 s → conexão encerrada em **2,0 s** |
| B3 — slowloris na fase de cabeçalhos | **corrigido** | dois gotejamentos de cabeçalho, teto 2 → cliente legítimo `200` |
| A2 (0058) — processamento cortado pelo prazo | **permanece corrigido** | processamento de 4 s com prazo de leitura de 2 s → `200` em **4,0 s** |
| I1 — mensagem de `quiescent` falsa | **aberto** | `app.js:94`, inalterado |
| I2 — `operation_limit_reached` como "concluído" | **aberto** | `app.js:95`, inalterado |
| I3 — lexema numérico sem validação | **aberto** | `app.js:22`, inalterado |
| I4 — testes de texto em vez de comportamento | **aberto, agravado** | nenhum teste de pausa, gotejamento ou prazo; B1–B3 corrigidos **sem teste de regressão** |
| I5 — trabalho órfão sem limite | **aberto** | sem limite de processamentos simultâneos |
| I6 — `ProfileRef` fixo | **aberto** | `app.js:31`, inalterado |
| M1–M9 | **abertos** | CSP sem `form-action`/`base-uri`; sem `Cross-Origin-Resource-Policy` |
| M3 (auditoria final 0057) — HEAD com corpo | **corrigido** | `_reject` suprime o corpo para HEAD, com teste |

---

## 🔴 N1 — Threads de `Timer` acumulam fora do teto de conexões

**Arquivo:** `web_app/server.py`, `handle_one_request` e `_cancel_read_deadline`.

**[FATO]** Cada conexão arma um `Timer`, e cada `Timer` é uma thread do sistema:

```python
def handle_one_request(self) -> None:
    self._read_deadline = Timer(DEFAULT_UPLOAD_TIMEOUT_SECONDS, self._expire_read_phase, (self.connection,))
    self._read_deadline.daemon = True
    self._read_deadline.start()
    super().handle_one_request()
```

O cancelamento ocorre **apenas** em `do_GET`, `do_POST`, `do_HEAD` e `_method_not_allowed`. Três caminhos nunca chegam a esses métodos, e neles o `Timer` vive até o prazo expirar:

- conexão aberta e fechada sem enviar nada — `readline` devolve vazio e `handle_one_request` retorna;
- linha de requisição malformada — `parse_request` responde erro pela classe base;
- método desconhecido — a classe base responde 501 sem chamar código do servidor.

**[FATO] Reproduzido** com o prazo reduzido a 6 s e `max_connections=4`:

```
threads em repouso: 2 | timers vivos: 0 | teto de conexoes: 4
controle: 50 GET /api/health legitimos             -> threads=2   | timers vivos=0
300 conexoes abertas e fechadas sem enviar nada    -> threads=302 | timers vivos=300
300 linhas de requisicao malformadas               -> threads=602 | timers vivos=600
300 metodos desconhecidos (FOO / HTTP/1.0)         -> threads=902 | timers vivos=900
cliente legitimo durante o acumulo                 -> 200 (as vagas do semaforo continuam livres)
apos o prazo de 6 s expirar                        -> threads=2   | timers vivos=0
```

Com o teto configurado em **4**, 900 conexões em cerca de 2 s deixaram **900 threads vivas**. O semáforo não conta os `Timer`: a vaga é liberada quando a conexão termina, e o `Timer` continua dormindo.

**[INFERÊNCIA]** No prazo real de 30 s, um processo local — no Ubuntu, ou no Mac pelo túnel — que abra e feche conexões num laço sustenta milhares de threads simultâneas sem token e **sem manter nenhuma conexão aberta**. Ao atingir o limite de threads do processo, `Thread.start()` levanta `RuntimeError`, e `ThreadingHTTPServer` deixa de conseguir atender qualquer requisição. É a mesma classe de negação de serviço sem credencial que motivou o prazo total, só que **mais barata**: antes era preciso segurar conexões abertas; agora basta abri-las e fechá-las. **Não executei o esgotamento até o limite do sistema**, para não afetar a máquina; o crescimento linear está medido acima.

**Correção:** cancelar o `Timer` em `finish()`, que o `socketserver` executa sempre, em qualquer caminho, depois de `handle()`:

```python
def finish(self) -> None:
    try:
        self._cancel_read_deadline()
    finally:
        super().finish()
```

Com isso, o tempo de vida de cada `Timer` fica limitado ao da conexão, e o número de `Timer` vivos passa a ser limitado pelo teto de conexões. Os cancelamentos antecipados dentro dos `do_*` continuam úteis para liberar o processamento. **Teste obrigatório:** após N conexões vazias, malformadas e com método desconhecido, o número de `threading.Timer` vivos volta a zero sem esperar o prazo.

---

## 🟠 Achados que continuam abertos da auditoria 0058b

O diretório `static/` é idêntico ao da auditoria anterior, então todos os achados de frontend permanecem, nas mesmas linhas:

- **I1 — `app.js:94`.** Para `quiescent`, a tela diz *"Nenhuma alteração automática segura foi necessária"*. A auditoria anterior reproduziu `quiescent` com **três alterações aplicadas**. `quiescent` significa que não **restou** alteração segura, não que nenhuma foi necessária.
- **I2 — `app.js:95`.** `operation_limit_reached` aparece como *"Processamento concluído. Status técnico da sessão: operation_limit_reached."*, contra o texto do contrato 0057 §6 alterado por este mesmo PR.
- **I3 — `app.js:22`.** O valor de `control.value.trim()` é inserido cru no JSON. `.5`, aceito por `<input type="number">`, gera `json_invalid`.
- **I4 — testes.** Continuam verificando texto estático, e um deles garante a presença da mensagem falsa de I1. Mais importante agora: **as correções de B1, B2 e B3 entraram sem nenhum teste de regressão**, e o único teste acrescentado cobre HEAD. As quatro sondas desta auditoria cabem como testes: pausa no upload, gotejamento de corpo, gotejamento de cabeçalhos e acúmulo de `Timer`.
- **I5 — trabalho órfão.** Fechar a aba não interrompe o processamento; não há limite de processamentos simultâneos separado das vagas de conexão.
- **I6 — `app.js:31`.** `ProfileRef` segue fixo em `web-interface`/`1`.

## 🟡 Menores

- **M1 e M4.** A CSP ainda não tem `form-action 'none'` nem `base-uri 'none'`, e os estáticos não enviam `Cross-Origin-Resource-Policy: same-origin`. Verificado por busca em `b0516c6`.
- **M2, M3 e M5.** Revogação dos Blob URLs, mensagens de erro cruas em inglês e teste do arquivo extra na pasta `static/` continuam abertos.
- **M6.** O log continua gravando `str(code)`: na sonda de pausa, `request_log` registrou `('POST', 'HTTPStatus.OK')` no Python 3.9, formato que muda no 3.11+.
- **M7.** O prazo de 30 s agora cobre a linha de requisição, os cabeçalhos **e** o corpo de até 64 MiB. Um DOCX grande por túnel lento é encerrado à força no meio do envio. Prazo e limite de corpo seguem sem dimensionamento conjunto.
- **M8.** Mesclar por **squash**: o histórico do PR apaga 204 arquivos, restaura +40.311 linhas e tem commits vazios de CI.
- **M9 — branches.** `fix/0058-interface-findings`, sem o sufixo `-clean`, continua sendo a publicação incompleta e não deve ser mesclada. Podem ser apagadas depois de resolvidas: `docs/auditoria-0057-final-opus`, `docs/close-0057-handoff`, `fix/0057-final-audit-findings`, `implement-0057-processing`, `implement/0058-web-interface` e as branches de auditoria já incorporadas.
- **Descrição do PR desatualizada.** Ainda diz "803 testes aprovados" e não menciona a troca do leitor com prazo pelo `Timer` restrito à fase de leitura, que é a mudança mais relevante do commit novo.

---

## O que está correto e deve ser preservado

- **Separação de fases:** o prazo cobre linha de requisição, cabeçalhos e corpo, e é cancelado **antes** de `build_product_from_inputs`. É o desenho pedido nas duas auditorias anteriores. Os três cenários de B1–B3 e o processamento longo foram verificados.
- **`settimeout(None)` na leitura do corpo**, eliminando o estado envenenado do `SocketIO` que causava B1.
- **Cancelamento em `finally` ao redor da leitura do corpo em `do_POST`**, que libera o prazo mesmo quando a leitura falha.
- **HEAD sem corpo em `_reject`**, com teste.
- Tudo o que a auditoria anterior listou como correto continua valendo: `justify`, negrito em três estados, decimal preservado até a fronteira, superfície pública fechada, `Host` antes de tudo, CSP e cabeçalhos, ausência de `innerHTML` e perfil opaco.
- 804 testes verdes, verificados de forma independente.

---

## Sequência recomendada

**Antes do merge:**

1. **N1** — cancelar o `Timer` em `finish()`, com teste de acúmulo;
2. **I4** — testes de regressão para B1, B2, B3 e N1;
3. **I1 e I2** — mensagens fiéis a cada status e ao contrato;
4. **M8** — squash.

**Antes de uso com usuários:** I3, I5, I6.

**Quando convier:** M1–M7, M9 e a descrição do PR.
