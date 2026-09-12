# Auditoria de segurança da PR #46 — servidor web local 0057 (Claude Opus)

**Auditor:** Claude Opus 5
**Data:** 2026-09-11
**Alvo:** PR #46, branch `implement-0057-web-server`, head `5b7d2cb4ec39eafd0dbe31bd96ee711ad0f1d16b`
**Base:** `98e865c` (contrato 0057 revisado, PR #45)
**Diff:** 231 linhas — `web_app/server.py` (141), `web_app/__init__.py` (5), `tests/test_web_app_server_v01.py` (85)
**Suíte executada localmente:** **781 passed, 1 warning, 8.70s**
**Repositório não modificado.** Sondas executadas fora da árvore, contra instâncias efêmeras em porta 0.

---

## Veredito

# APROVADO COM AJUSTES OBRIGATÓRIOS

A estrutura de segurança está certa: bind validado, token com `compare_digest`, estado imutável por processo, `ThreadingHTTPServer` bem usado. Mas **o servidor rejeita 100% do caminho de acesso que o próprio contrato define**, e o teste novo consagra esse comportamento como correto. Isso precisa ser resolvido antes de mesclar, porque qualquer correção posterior será a fronteira de segurança real.

---

## 🔴 A1 — O servidor rejeita o caminho de acesso documentado, e o teste petrifica o defeito

**Arquivo:** `web_app/server.py:53` e `:98`; `tests/test_web_app_server_v01.py:67-72`.

**[FATO]** `expected_host = f"{bound_host}:{bound_port}"` produz `"127.0.0.1:8000"`, e `_authorized` exige igualdade exata com o cabeçalho `Host`.

**[FATO]** O contrato 0057 §1 define o acesso como `http://localhost:8000` através do túnel SSH, e `main()` imprime exatamente essa URL (`server.py:129`).

**[FATO]** Um navegador que abre `http://localhost:8000` envia `Host: localhost:8000`. Reprodução:

```
expected_host='127.0.0.1:52568'

Host: localhost:PORT + token (navegador real)  -> 400 {"error":"host not allowed"}
Host: 127.0.0.1:PORT + token                   -> 200 {"service":"formatador-academico","status":"ok"}
```

**[FATO]** `test_unexpected_host_is_rejected` afirma que `Host: localhost:8000` deve devolver **400**. O caminho obrigatório do contrato está codificado na suíte como "host inesperado".

**Impacto:** a interface é inutilizável pelo navegador do Mac. Não é um detalhe de configuração: é o único modo de uso previsto. E como o teste consagra o comportamento, a correção exige mexer no teste, o que aumenta a chance de alguém "consertar" afrouxando a verificação de `Host` por inteiro — perdendo a defesa contra DNS rebinding, que é justamente o que essa verificação existe para dar.

**Correção recomendada:** aceitar um **conjunto fechado** de hosts esperados, `{"127.0.0.1:<port>", "localhost:<port>", "[::1]:<port>"}`, derivado da porta ligada; e o mesmo conjunto para `expected_origin`. Nunca aceitar `Host` arbitrário, nunca derivar a origem do próprio cabeçalho recebido. Corrigir `test_unexpected_host_is_rejected` para usar um host de fato inesperado (`evil.example:8000`), e **acrescentar** um teste que prove que `localhost:<port>` funciona.

**O contrato também precisa de uma linha:** §5 diz "aceitando somente o host local esperado" sem definir o conjunto. Essa ambiguidade foi resolvida pela implementação na direção errada.

---

## 🔴 A2 — Sem timeout de requisição, com threads ilimitadas

**Arquivo:** `web_app/server.py:87-100`.

**[FATO]** `LocalWebServer(ThreadingHTTPServer)` com `daemon_threads = True` e, verificado em execução, `RequestHandlerClass.timeout is None`. `ThreadingHTTPServer` cria uma thread por conexão, sem limite.

**[INFERÊNCIA]** Qualquer processo local — incluindo qualquer outro usuário do Ubuntu, que alcança `127.0.0.1` sem credencial — pode abrir conexões que nunca completam a linha de requisição e manter threads presas indefinidamente. Não é preciso token: a autorização só acontece depois que a requisição é lida. É slowloris clássico, e o custo de montá-lo é um laço de três linhas.

Hoje o alcance é limitado, porque só há a rota de saúde. Quando o upload entrar, cada thread presa também segurará buffers de corpo.

**Correção recomendada:** definir `timeout` na classe do handler (por exemplo 30 s) e tratar `socket.timeout` fechando a conexão; considerar um teto de conexões simultâneas. Ambos ficam na biblioteca padrão.

---

## 🟠 I1 — `request_log` cresce sem limite e captura a linha de requisição inteira

**Arquivo:** `web_app/server.py:38-40` e `:100`.

**[FATO]** `log_message` substitui a escrita em stderr por `self.server.request_log.append(format % args)`, sobre uma `list` comum criada em `__init__`. Verificado: após 15 requisições, `request_log` tinha 15 entradas, a última sendo `'"HEAD /api/health HTTP/1.1" 501 -'`.

**[INFERÊNCIA]** Três consequências:

1. **crescimento ilimitado** — nada rotaciona nem descarta; um processo de longa duração acumula uma entrada por requisição para sempre;
2. **retenção de metadados de requisição em memória viva**, indefinidamente — hoje o caminho é fixo, mas a lista guarda a linha de requisição completa, e quando rotas de processamento chegarem com identificadores no caminho, eles entram aqui;
3. o comentário da linha 39 diz que o servidor "não deve imprimir dados ou cabeçalhos do documento", mas o efeito real não é *não registrar*: é **registrar na memória do processo**, sem teto. `log_error` da classe base também chama `log_message`, então erros entram no mesmo balde.

**Correção recomendada:** usar `collections.deque(maxlen=N)`, registrar apenas método, status e uma rota **canonizada** (nunca o caminho bruto recebido), e declarar no contrato que o log é volátil, limitado e não recebe identificadores.

---

## 🟠 I2 — O bloqueio cross-site funciona por acidente, não por decisão

**Arquivo:** `web_app/server.py:59-66`.

**[FATO]** As duas verificações são condicionais: `if origin is not None and ...` e `if fetch_site is not None and ...`. Reprodução:

```
Origin de outro site                    -> 403
Sec-Fetch-Site: cross-site              -> 403
sem Origin e sem Sec-Fetch-Site (curl)  -> 200
OPTIONS (preflight)                     -> 501
```

**[INFERÊNCIA]** A proteção real contra CSRF **é o token**, não as duas verificações. Um site malicioso aberto no navegador do Mac não consegue montar a requisição por dois motivos: não conhece o token, e o cabeçalho `X-Formatador-Session` força um preflight `OPTIONS` — que hoje falha com 501 **porque `do_OPTIONS` não existe**.

Isso é sólido hoje e frágil amanhã: no dia em que alguém implementar `do_OPTIONS` para "arrumar o preflight", a barreira desaparece se vier acompanhada de cabeçalhos CORS permissivos.

**Correção recomendada:** registrar explicitamente, em comentário e no contrato, que (a) o token é a fronteira, (b) `Origin` e `Sec-Fetch-Site` são defesa em profundidade e não controles independentes, e (c) `OPTIONS` **deve** permanecer negado, com teste que falhe se algum dia responder 2xx ou emitir `Access-Control-Allow-*`.

---

## 🟠 I3 — Respostas 501 vazam versão e quebram o contrato de erro JSON

**[FATO]** Métodos não implementados caem no tratador padrão de `BaseHTTPRequestHandler`, que devolve uma página HTML completa. Cabeçalhos verificados numa resposta 200:

```
Server : BaseHTTP/0.6 Python/3.9.6
```

**[INFERÊNCIA]** Duas coisas: a versão exata do Python e da biblioteca é anunciada em toda resposta, e os erros de método fogem do formato `{"error": ...}` que o resto do servidor usa. Em `127.0.0.1` o risco de divulgação é baixo, mas é gratuito de eliminar e a inconsistência de formato atrapalha o cliente.

**Correção recomendada:** definir `server_version` e `sys_version = ""` na classe do handler, e implementar os métodos previstos devolvendo 405 em JSON — mantendo `OPTIONS` negado conforme I2.

---

## 🟡 Menores

- **M1 — `max_body_bytes` é código morto.** Aparece 8 vezes, é validado em `create_server` e guardado no servidor, mas **nunca é aplicado**: `do_POST` responde 404 antes de qualquer leitura. Não é defeito hoje; é risco de leitura. Marcar como não aplicado até o upload chegar, para que ninguém suponha proteção existente.
- **M2 — `--host` sugere configuração que não existe.** `create_server` rejeita qualquer valor diferente de `127.0.0.1` (`:112`), mas o CLI expõe a opção. Ou remover a flag, ou documentar que só aceita o padrão.
- **M3 — `allow_reuse_address = False`** não acrescenta segurança no Linux e faz o reinício falhar durante `TIME_WAIT`. Se a intenção foi evitar sequestro de porta, o efeito não é esse.
- **M4 — Ordem rota-antes-de-autenticação enumera rotas.** `do_GET` verifica `self.path` antes de `_authorized`, então um chamador sem token distingue rota existente (401) de inexistente (404). Em localhost é menor, mas inverter a ordem é gratuito.
- **M5 — O token é por processo, não por sessão**, e é impresso em stdout (`:130`). Se o terminal do Ubuntu for registrado (tmux, script, CI), o token persiste em disco. Nomear corretamente no contrato e considerar gravar em arquivo com permissão restrita em vez de imprimir.

---

## Respostas diretas

| # | Pergunta | Resposta |
|---|---|---|
| 1 | Bind em 127.0.0.1 | **Correto.** `create_server:112` recusa qualquer outro host e `test_server_is_local_only` cobre. Ressalva: bind não é autorização — outros processos locais alcançam a porta |
| 2 | Geração e comparação do token | **Correta.** `secrets.token_urlsafe(32)` (256 bits) e `secrets.compare_digest`, com default `""` que não quebra a comparação. Ver M5 quanto ao ciclo de vida |
| 3 | Host, Origin, Sec-Fetch-Site | **Host está errado** (A1). `Origin` e `Sec-Fetch-Site` funcionam quando presentes, mas são opcionais (I2) |
| 4 | Métodos e rotas não previstas | Rotas: negadas. Métodos: 501 pelo tratador padrão, com o vazamento de I3 e a ordem de M4 |
| 5 | Isolamento entre requisições concorrentes | **Adequado hoje.** Handlers são por requisição; o estado do servidor é somente-leitura após `__init__`, exceto `request_log` (I1). **Regra a fixar antes do upload:** bytes de documento nunca podem morar no objeto servidor |
| 6 | Uso de `ThreadingHTTPServer` | **Correto**, com `daemon_threads = True`. O problema não é o uso, é a ausência de timeout (A2) |
| 7 | Vazamentos por log, exceção ou cabeçalho | `request_log` (I1) e `Server:` (I3). Os corpos de erro JSON não vazam detalhe interno — bom |
| 8 | Compatibilidade com o 0057 revisado | **Compatível na direção**; incompatível em um ponto: o contrato manda acessar por `localhost` e a implementação só aceita `127.0.0.1`. O contrato também precisa definir o conjunto de hosts aceitos |
| 9 | Rota de saúde protegida? | **Sim**, exige token, `Host` e passa pelas verificações de origem. Mas hoje é inalcançável pelo navegador (A1) |
| 10 | Testes faltantes | Abaixo |

---

## Testes adversariais ainda faltantes (pergunta 10)

1. `Host: localhost:<port>` com token → **200** (prova de A1; hoje o teste afirma o contrário);
2. `Host: evil.example:8000` → 400 (o teste atual deveria ser este);
3. `Host` ausente em HTTP/1.0 → comportamento definido e testado;
4. sem `Origin` e sem `Sec-Fetch-Site`, com token → documenta que o token é a única fronteira (I2);
5. `OPTIONS` → negado, **e** ausência de qualquer `Access-Control-Allow-*` na resposta (trava de I2);
6. `PUT`, `DELETE`, `PATCH`, `HEAD` → resposta prevista, em JSON, sem página HTML padrão;
7. resposta não contém `Server` com versão de Python (I3);
8. token de comprimento diferente → rejeitado (exercita `compare_digest` com entradas desiguais);
9. cabeçalho de sessão duplicado → comportamento definido;
10. conexão que envia cabeçalhos parciais e não completa → encerrada por timeout (prova de A2);
11. N requisições concorrentes com tokens distintos → nenhum vazamento de estado entre elas;
12. `request_log` não cresce além do teto e não contém o caminho bruto (I1);
13. rota inexistente **sem** token → 401 antes de 404, se M4 for corrigido.

---

## Sequência recomendada antes de mesclar

1. **A1** — conjunto fechado de hosts e origens aceitos; corrigir o teste que petrifica o defeito e acrescentar o teste do caminho real;
2. **A2** — `timeout` no handler;
3. **I1** — `deque(maxlen=...)` e rota canonizada no log;
4. **I2** — registrar que o token é a fronteira e travar `OPTIONS` com teste;
5. **I3** — suprimir `Server`/`sys_version` e padronizar 405 em JSON;
6. menores M1–M5 quando convier.

Os dois primeiros são bloqueantes. Sem A1 o produto não funciona pelo caminho previsto; sem A2 qualquer processo local derruba o servidor sem credencial.

## O que está correto e deve ser preservado

- bind validado por igualdade estrita, com teste;
- `secrets.token_urlsafe(32)` e `secrets.compare_digest` — geração e comparação corretas;
- estado de segurança imutável após `__init__`, lido e nunca reescrito pelos handlers;
- `ThreadingHTTPServer` com `daemon_threads`, escolha certa dado o custo de processamento medido na 0056;
- corpos de erro em JSON curto, sem detalhe interno, com `Cache-Control: no-store`;
- `create_server` separado de `serve_forever`, o que torna o servidor testável sem porta fixa;
- nenhuma rota de escrita exposta nesta fatia — a decisão de entregar só a saúde primeiro foi acertada.
