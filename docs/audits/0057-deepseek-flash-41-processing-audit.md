# Auditoria 0057 — endpoint de processamento da interface web local (DeepSeek Flash 4.1)

**Objeto:** branch `implement-0057-processing`, commit `91912c5` (base `9e15893`, PR #46).
**Método:** extraí o commit com `git archive` para um diretório temporário (não alterei arquivos do repo; apenas fiz `git fetch` do ref para conseguir lê-lo). Suíte completa no commit auditado: **793 passed**. Sondas adversariais executadas fora do repositório.

---

## Veredito final

# APROVADO COM AJUSTES

A fronteira está correta: o perfil chega intacto ao parser congelado, os cinco `DeliveryFile` são entregues sem reconstrução de nome/manifest, os limites de corpo funcionam e a autenticação precede o roteamento. Nenhuma brecha bloqueante para o cenário-alvo (local, `127.0.0.1`, túnel SSH, usuário único). Há três achados médios de robustez/contrato e lacunas de teste que devem ser corrigidos antes de uso mais amplo.

---

## Achados

### A1 — MÉDIO — Exceção inesperada do pipeline derruba a conexão e vaza traceback no stderr

- **Arquivo/linha:** `server.py:170-191` (`do_POST`), `server.py:263-305` (`LocalWebServer` não sobrescreve `handle_error`); `product_delivery/builder.py:115` chama `render_processing_report` sem envolver `HumanReportError`.
- **Fato observado:** o `try` cobre `MultipartInputError`, `ProductInputBoundaryError`, `ProductDeliveryContractError` e `ProductDeliveryIntegrityError`. Qualquer outra exceção (`HumanReportError` de `render_processing_report`, `BrokenPipeError` ao escrever a resposta depois de o cliente desconectar, `MemoryError`, ou bug futuro) propaga. Reprodução por monkeypatch: cliente recebe `RemoteDisconnected` (nenhuma resposta HTTP) e o stderr recebe `traceback.print_exc()` completo, incluindo a mensagem interna (`RuntimeError: SECRET internal detail leaked`) e o endereço do cliente.
- **Impacto:** contraria §6 do 0057 (“exibir erros de contrato e integridade sem convertê-los em sucesso”) e o requisito de não vazar detalhes internos; cliente fica sem status seguro; stderr pode acumular dados do erro. `BrokenPipeError` por cancelamento de download é um caminho realista.
- **Reprodução mínima:** `srv.build_product_from_inputs = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("SECRET"))`, enviar multipart válido → conexão fechada sem resposta e traceback no stderr.
- **Correção:** adicionar `except Exception` retornando `500` com JSON genérico (`{"error":"internal error"}`) e sobrescrever `handle_error` para registrar de forma limitada, sem traceback. Envolver a chamada de `render_processing_report` em `build_product_delivery` também ajuda, mas a defesa pertence ao servidor.
- **Teste que impede regressão:** monkeypatch do pipeline levantando `RuntimeError`; assertar status 500, corpo genérico sem a mensagem interna, e stderr sem o marcador.

### A2 — MÉDIO — Amplificação de memória na resposta Base64 única

- **Arquivo/linha:** `server.py:232-250` (`_send_delivery`), `server.py:25` (`DEFAULT_MAX_BODY_BYTES = 64 MiB`), `server.py:29` (`DEFAULT_MAX_CONNECTIONS = 32`).
- **Fato observado:** todos os 5 artefatos são materializados em memória: `delivery` (~2 DOCX + JSON + Markdown + manifest), depois uma lista de strings Base64 (~1,33× cada) e, por fim, um único `bytes` JSON. O pico por requisição é várias vezes o corpo de entrada (para 64 MiB, ordem de centenas de MB) e o limite de conexões (32) não limita o número de processamentos simultâneos.
- **Impacto:** em documentos grandes e/ou algumas requisições concorrentes, pressão de memória muito acima do teto nominal de 64 MiB. Mitigado pelo uso local/usuário único, mas é uma amplificação não limitada pelo contrato.
- **Correção:** limitar o tamanho total da resposta/derivados, reduzir o teto padrão de corpo, ou transmitir os arquivos em partes; alternativamente, limitar conexões de processamento (não só conexões TCP) e liberar referências.
- **Teste:** medir pico de memória/RSS com entrada próxima ao limite e assertar um teto de resposta, ou um limite configurável de memória.

### A3 — MÉDIO — Erros de integridade do núcleo são mascarados como rejeição do usuário (422)

- **Arquivo/linha:** `server.py:186-188`: `except (ProductInputBoundaryError, ProductDeliveryContractError)` → `422`.
- **Fato observado:** `ProductInputBoundaryIntegrityError` é subclasse de `ProductInputBoundaryError`, então uma contradição interna de lineage/integridade do núcleo vira `422 "document or profile was rejected"`, igual a um perfil inválido do usuário.
- **Impacto:** apaga a distinção exigida entre erro de contrato/entrada e falha de integridade (§6 do 0057), dificultando diagnóstico e podendo sugerir culpa do usuário por um bug do núcleo.
- **Correção:** mapear `ProductInputBoundaryUnsupportedError`/`ProductInputBoundaryContractError` → 422; `ProductInputBoundaryIntegrityError` → 500.
- **Teste:** levantar cada subtipo e assertar o status esperado.

### A4 — BAIXO/MÉDIO — Resposta não distingue “concluído” de `operation_limit_reached`

- **Arquivo/linha:** `server.py:244` (`{"status":"ok","files":[...]}`).
- **Fato observado:** todo processamento bem-sucedido retorna `status:"ok"`, independentemente de o `ProcessingReport` trazer `quiescent`, `quiescent_with_unapplied` ou `operation_limit_reached`. Reprodução com perfil 0.3: `200`, `status:"ok"`, mas o report interno diz `session_status: quiescent_with_unapplied`.
- **Impacto:** o contrato §6/§9.9 exige exibir `operation_limit_reached` como “limite atingido”, nunca como concluído. Os dados existem dentro do arquivo `technical_report`, mas não são surfaced no transporte; a futura página precisa decodificar o JSON para não enganar o usuário.
- **Correção:** incluir `session_status` (e opcionalmente as contagens do resumo) no envelope da resposta, ou documentar explicitamente que a página deve ler o relatório técnico.
- **Teste:** sessão com limite atingido e sessão quiescente; assertar distinção no envelope.

### A5 — BAIXO — `max_applied_operations` aceita formas não decimais

- **Arquivo/linha:** `server.py:198-206` (`int(raw.decode("ascii"), 10)`).
- **Fato observado:** `b"1_0"` → 10, `b"+5"` → 5, `b" 5 "` → 5; todos retornam `200`. É limitado a `<= 10000`, sem impacto de segurança.
- **Impacto:** frouxidão em relação a “texto ASCII decimal”; aceita entrada ambígua.
- **Correção:** validar com `re.fullmatch(r"[0-9]+", raw)` antes do `int`.
- **Teste:** `b"1_0"`, `b"+5"`, `b" 5 "`, `b"5\n"` → 400.

### A6 — BAIXO — `Transfer-Encoding` não é recusado explicitamente

- **Arquivo/linha:** `server.py:208-230`.
- **Fato observado:** requisição chunked não é de-chunked; é tratada como “sem Content-Length”, lida como cru e recusada como multipart inválido (400). Requisição com `Transfer-Encoding` + `Content-Length` usa o `Content-Length` (mais seguro) sem recusar a ambiguidade.
- **Impacto:** baixo (HTTP/1.0, sem proxy), mas a prática recomendada é rejeitar TE explicitamente.
- **Correção:** recusar quando `Transfer-Encoding` estiver presente.
- **Teste:** `Transfer-Encoding: chunked` → 400 com mensagem clara.

### A7 — BAIXO — Timeout é por operação de socket, não prazo total da requisição

- **Arquivo/linha:** `server.py:108` (`timeout = 30`), `_read_multipart_body`.
- **Fato observado:** o `socket.settimeout(30)` reinicia a cada `recv`; um cliente lento (slowloris) pode segurar um slot muito além de 30s, inclusive sem token (drip de cabeçalhos antes do `_authorized`).
- **Impacto:** baixo (local/túnel SSH, 32 conexões, cenário single-user), mas esgota slots.
- **Correção:** prazo total por requisição ou teto de conexões mais baixo.
- **Teste:** sonda de drip lento.

### A8 — BAIXO (pré-existente do PR #46) — `Host`/`Origin` duplicados só validam o primeiro valor

- **Arquivo/linha:** `server.py:133` e `server.py:140` usam `self.headers.get(...)`.
- **Fato observado:** um segundo `Host` (ou `Origin`) inválido é ignorado. Não permite bypass (o primeiro é validado), mas diverge de HTTP/1.1 e da intenção de conjunto fechado.
- **Correção:** exigir exatamente um, via `get_all`.
- **Teste:** `Host` duplicado (válido + inválido) → 400.

### A9 — INFORMATIVO — `boundary` sem limite explícito

- **Arquivo/linha:** `server.py:53-58`.
- **Fato:** boundary de 10.000 caracteres é aceito (limitado apenas pelo teto de 64 KiB por linha de cabeçalho). Sem impacto prático; um limite explícito seria mais defensivo.

---

## Pontos aprovados (verificados)

- **Perfil intacto (§3.2):** `_parse_multipart` devolve bytes exatos para `binary`/`8bit`/sem CTE; CTE `base64` decodifica corretamente; nada de `json.loads`, reserialização ou normalização antes de `processing_profile_from_json`. BOM, UTF-8 inválido e chave duplicada chegam ao parser congelado e viram **422** (não erro do transporte).
- **Entrega fiel (§4, critério 12):** os 5 `DeliveryFile` retornados são byte/sha/nome/media/size **idênticos** a uma chamada direta de `build_product_delivery`, em `ROLE_ORDER` (`clean_docx, review_docx, technical_report, human_report, manifest`), sem reconstrução de nome/manifest.
- **Limite de corpo:** com `Content-Length` rejeita antes de ler; sem o cabeçalho lê `max+1` e rejeita; `Content-Length` duplicado ou inválido → 400; corpo truncado → 400. O caminho sem `Content-Length` com corpo válido e half-close retorna 200.
- **Multipart:** allowlist de campos, rejeição de duplicado/desconhecido/vazio, partes não `form-data` e campos não suportados; `max_applied_operations` obrigatoriamente `<= 10000` e `> 0`.
- **Filename:** `/`, `\`, NUL, CRLF e controles rejeitados; `.docx` exigido; Unicode preservado; base vazia/`..`/`CON` caem na canonicalização congelada → 422.
- **Sem header injection:** dados do usuário só no corpo JSON (escapados); `Content-Length` calculado; sem `Content-Disposition` derivado.
- **Autenticação:** `_authorized()` antes do roteamento em `do_POST` e `do_GET`; rota desconhecida com token → 404, sem token → 401; token errado → 401; `PUT` → 405; `OPTIONS` sem token → 401.
- **Concorrência/ciclo de vida:** sem estado de requisição compartilhado; duas requisições concorrentes com perfis diferentes retornam 200; semáforo liberado no `finally`; `HTTP/1.0` fecha a conexão (mitiga desync por corpo não consumido).
- **Sem retenção:** `request_log` limitado guarda só `(método, status)`; `log_message`/`log_error` são no-op; bytes ficam em locais da requisição.
- Suíte completa: **793 passed**.

---

## Testes adicionais recomendados (lacunas atuais)

O arquivo `tests/test_web_app_processing_v01.py` cobre apenas 3 casos (5 arquivos, chave duplicada, limite de corpo). Faltam, no mínimo:

1. `Content-Length` duplicado/conflitante; ausente; truncado.
2. boundary ausente/inválido/muito grande.
3. campo obrigatório duplicado; campo desconhecido; parte aninhada.
4. perfil com BOM, encoding inválido e chave duplicada (os dois primeiros não testados).
5. filename com `/`, `\`, NUL, CRLF, sem `.docx`, e Unicode.
6. perfil válido com `Content-Transfer-Encoding: base64`.
7. `max_applied_operations` > padrão, `== 0`, `== 1` e formas não decimais.
8. rota desconhecida com e sem token.
9. duas requisições concorrentes com perfis distintos (verificando os artefatos corretos).
10. exceção inesperada do pipeline → 500 genérico, sem mensagem interna e sem traceback no stderr (achado A1).
11. mapeamento de status por subtipo do boundary (A3).
12. distinção de `session_status`/limite no envelope (A4).
13. byte-exatidão dos 5 arquivos contra `build_product_delivery` direto (hoje só há checagem de sha/tamanho do Base64, não comparação com a fonte).

---

## Observações metodológicas

- Reproduzi cada item com sondas fora do repositório (sockets crus e `http.client`), inclusive o vazamento de traceback (A1) e a amplificação/ambiguidade (A2/A4). Os tamanhos de memória de A2 são estimados por construção (não medi RSS de um caso de 64 MiB), por isso o achado é “médio” e não bloqueante.
- Não alterei arquivos do repositório; o `git fetch` do ref e a extração via `git archive` não mudam a árvore de trabalho.
