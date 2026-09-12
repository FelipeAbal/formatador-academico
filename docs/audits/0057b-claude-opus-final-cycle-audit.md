# Auditoria final do ciclo 0057 — interface web local (Claude Opus)

**Auditor:** Claude Opus 5
**Data:** 2026-09-12
**Alvo:** `main` @ `94309fc`
**Escopo:** `web_app/server.py` (390 linhas), `tests/test_web_app_server_v01.py` (200), `tests/test_web_app_processing_v01.py` (174), contrato 0057 e handoff
**Suíte executada localmente:** **797 passed, 1 warning, 18.13s**
**Repositório não modificado.** Sondas fora da árvore, contra instâncias efêmeras em porta 0.

---

## Veredito

# APROVADO COM AJUSTES

O ciclo pode ser encerrado. Verifiquei, por execução, que **todos os bloqueantes das auditorias anteriores foram corrigidos** — inclusive o A3 do contrato 0057, que era o mais sutil. Restam quatro achados; um deles é mais grave do que o acompanhamento registrado sugere, e é o único que eu trataria antes de uso real com documentos de terceiros.

---

## 1. Confirmação dos bloqueantes anteriores

| Achado | Origem | Estado verificado |
|---|---|---|
| `Host: localhost` rejeitado | A1 / PR #46 | **corrigido** — conjunto fechado `{127.0.0.1, localhost, [::1]}:porta`; fluxo real responde 200 |
| Sem timeout, threads ilimitadas | A2 / PR #46 | **corrigido parcialmente** — `timeout = 30` e `BoundedSemaphore(32)`; ver A1 abaixo |
| `request_log` sem teto, com caminho bruto | I1 / PR #46 | **corrigido** — `deque(maxlen=100)`, só `(método, código)`; `log_message` e `log_error` são no-op |
| `OPTIONS` negado por acidente | I2 / PR #46 | **corrigido** — `do_OPTIONS` explícito, 405 |
| `Server:` com versão do Python | I3 / PR #46 | **corrigido** — `server_version`/`sys_version` suprimidos |
| Ignorava `build_product_delivery` | A1 / 0057 | **corrigido** — cinco arquivos na ordem canônica |
| CSRF sem barreira de origem | A2 / 0057 | **corrigido** — token, `Host`, `Origin`, `Sec-Fetch-Site`, duplicatas rejeitadas |
| **Perfil aninhado destruindo rejeição de chaves duplicadas** | **A3 / 0057** | **corrigido — verificado por execução** |
| "Abstenções" sem família real | M1 / 0057 | **corrigido** — `abstained_count` vem no `summary` |
| `max_body_bytes` inerte | M1 / 0057 | **corrigido** — aplicado antes da leitura |

**A3 é o que mais importa e foi genuinamente resolvido.** Enviei um perfil com `bold` declarado duas vezes no mesmo objeto, por multipart:

```
perfil com chave DUPLICADA  -> 422 {"error":"document or profile was rejected"}
```

O perfil chega como bytes opacos ao parser congelado e a rejeição de declaração ambígua sobrevive ao transporte. Era o risco de autoridade normativa mais discreto de toda a camada web.

Fluxo válido ponta a ponta:

```
fluxo valido -> 200
   session_status: quiescent
   arquivos: ['clean_docx','review_docx','technical_report','human_report','manifest']
   abstained_count: 0 | applied: 1
```

---

## 2. Achados

### 🟠 A1 — O teto de conexões virou o vetor de negação de serviço

**Arquivo:** `web_app/server.py:124` (`timeout = 30`), `:325` (`BoundedSemaphore`), `:327-335` (`process_request`).

**[FATO] Reproduzido** com `max_connections=2`:

```
A) cliente legitimo com 2 conexoes lentas -> NEGADO (ConnectionResetError) apos 0.0s
   apos trickle de 1 byte              -> AINDA NEGADO (ConnectionResetError)
```

Duas conexões que enviam apenas uma linha de requisição parcial bastam para excluir completamente o cliente legítimo — **imediatamente**, com reset, porque `process_request` chama `shutdown_request` quando o semáforo está esgotado.

**[INFERÊNCIA]** Três agravantes:

1. `BaseHTTPRequestHandler.timeout` é prazo **por operação de socket**, não total. Um byte a cada 29 s mantém a conexão viva indefinidamente — confirmado pelo trickle acima;
2. a autorização acontece **depois** de a requisição ser lida, então **não é preciso token**. Qualquer processo ou usuário local alcança `127.0.0.1` e monta isto com 32 sockets;
3. o teto de conexões foi introduzido como proteção e, sem prazo total, transformou uma degradação em **negação completa e instantânea**: antes, threads presas apenas consumiam recursos; agora elas fecham a porta.

**Impacto:** o serviço fica indisponível sem credencial. Em uso pessoal numa máquina confiável é aceitável; deixa de ser no momento em que o Ubuntu tiver outro usuário, outro serviço comprometido ou qualquer processo não confiável.

**Correção:** prazo total por requisição, medido do primeiro byte ao fim do corpo, independente do timeout por operação — por exemplo um *deadline* absoluto verificado durante a leitura, encerrando a conexão ao expirar. O acompanhamento que vocês registraram ("prazo total contra requisições lentas") é exatamente isto; a nota apenas subestima a gravidade, porque a consequência não é lentidão, é lockout.

### 🟠 I1 — Memória da resposta: quantificando o acompanhamento

**Arquivo:** `web_app/server.py:260-286`.

**[FATO]** Medido no fluxo válido: resposta de **12.146 bytes para um DOCX de 1.689 bytes — 7,2×**.

**[INFERÊNCIA]** A resposta carrega clean + review + relatório JSON + Markdown + manifest, todos em Base64, num único `bytes`. Para entradas grandes o fator converge para aproximadamente `(clean + review) × 1,33` mais os relatórios, e o pico de memória é pior que o tamanho final, porque `json.dumps` constrói a string inteira e `.encode()` faz outra cópia:

```
entrada de 64 MB (o limite atual)
  → clean + review ≈ 128 MB
  → base64 na lista ≈ 171 MB
  → string do json.dumps ≈ 171 MB
  → bytes codificados ≈ 171 MB
  → pico transitório ≳ 500 MB, sem contar as cópias do próprio pipeline
```

Nada é transmitido em fluxo. **Correção:** reduzir `DEFAULT_MAX_BODY_BYTES` para um valor coerente com a memória disponível e com a medição real de documentos acadêmicos — 64 MB é ordens de grandeza acima de qualquer tese —, e transmitir os artefatos em fluxo em vez de montar um único payload. Enquanto não houver fluxo, o limite de corpo é o único controle de memória e deve ser dimensionado por ele, não por generosidade.

### 🟠 I2 — `delivery.files[2]` é um índice mágico sobre uma camada congelada

**Arquivo:** `web_app/server.py:272`.

**[FATO]** `report = json.loads(delivery.files[2].content_bytes.decode("utf-8"))`. O índice 2 é hoje `TECHNICAL_REPORT`, confirmado na construção de `product_delivery/builder.py`.

**[INFERÊNCIA]** É uma dependência de ordenação de outra camada expressa como número literal. Se a ordem de `DeliveryRole` mudar, isto lê o arquivo errado: com o Markdown, `json.loads` levanta e cai no `except Exception` → 500 "internal error"; com o manifest, `json.loads` **funciona** e `report["summary"]` levanta `KeyError` → também 500. Em nenhum dos casos a causa aparece, porque o diagnóstico é nulo (ver I3).

**Correção:** selecionar por papel — `next(f for f in delivery.files if f.role is DeliveryRole.TECHNICAL_REPORT)` — e falhar explicitamente se não houver exatamente um.

### 🟠 I3 — Diagnóstico nulo: um defeito real em produção é invisível

**Arquivo:** `web_app/server.py:128-137`, `:213-215`, `:343-345`.

**[FATO]** `log_message` e `log_error` retornam sem fazer nada; `log_request` guarda apenas `(método, código)`; `handle_error` guarda `("ERROR","500")`; e `except Exception` devolve `"internal error"` sem preservar nada.

**[INFERÊNCIA]** A privacidade foi maximizada até o ponto de tornar o sistema não diagnosticável. Um `KeyError` de I2, um `MemoryError` de I1 e um defeito de lógica produzem exatamente a mesma saída: `500 {"error":"internal error"}` e uma tupla `("POST","500")` num deque. Não há traceback em lugar algum.

**Correção:** registrar no log limitado o **nome do tipo** da exceção — nunca a mensagem, que pode conter dados do documento —, e prever um modo de depuração local explícito, desligado por padrão. `("POST","500","KeyError")` não vaza nada e é a diferença entre diagnosticar em minutos ou às cegas.

---

## 3. Achados menores

- **M1 — `Content-Transfer-Encoding` é honrado.** `part.get_payload(decode=True)` decodifica, então `max_body_bytes` limita o **fio**, não o conteúdo decodificado. Verificado: um `document` com `Content-Transfer-Encoding: base64` é aceito e processado (200). O fator é limitado (~1,33× com base64), logo não é amplificação perigosa — mas o limite efetivo é 33% mais folgado do que parece, e convém dizer isso onde o limite é documentado.
- **M2 — mensagem enganosa para nome de arquivo.** `filename = ".docx"` passa as validações de multipart, produz base vazia em `filename.rsplit(".",1)[0]` e retorna `422 {"error":"document or profile was rejected"}`. Verificado. O documento e o perfil estão íntegros; o problema é o nome. Validar que a base é não vazia antes de chamar a camada de entrega, com mensagem própria.
- **M3 — resposta a HEAD carrega corpo.** `do_HEAD = _method_not_allowed` responde 405 com `Content-Length: 30` e escreve o corpo no socket. Verificado (o cliente reporta `corpo=0` porque descarta por conhecer a semântica de HEAD). É violação de HTTP, inofensiva com HTTP/1.0 e fechamento de conexão. Suprimir o corpo quando `self.command == "HEAD"`.
- **M4 — `message.defects` não é verificado.** Testei o caso mais perigoso, corpo sem boundary inicial: o parser registra `StartBoundaryNotFoundDefect` e `MultipartInvariantViolationDefect`, mas `is_multipart()` devolve `False` e a guarda da linha 79 rejeita. **O guard atual cobre esse caso.** Ainda assim, asserir `not message.defects` é defesa em profundidade barata, porque `is_multipart()` não cobre todas as classes de defeito.

---

## 4. O que está correto e deve ser preservado

- **A rejeição de chaves duplicadas sobrevive ao transporte** — o perfil chega opaco ao parser congelado. É a invariante de autoridade normativa mais frágil da camada web e está de pé, verificada por execução.
- `build_product_delivery` como fronteira única de saída: cinco arquivos, ordem canônica, papéis, media types, hashes e tamanhos vindos da camada congelada, sem reconstrução.
- `summary` repassado íntegro, incluindo `session_status` e `abstained_count` — o produto informa abstenção e status em vez de apenas "sucesso".
- Fronteira de autorização: conjunto fechado de hosts e origens derivado da porta ligada; rejeição de `Host`, token e `Origin` duplicados; `Sec-Fetch-Site`; autorização **antes** do roteamento, fechando a enumeração de rotas.
- `max_body_bytes` aplicado antes da leitura integral, com tratamento de `Content-Length` ausente e duplicado e recusa de `Transfer-Encoding`.
- `max_applied_operations` exposto com validação lexical estrita e teto no default congelado.
- Estado do servidor somente-leitura após `__init__`; bytes de documento existem apenas em variáveis locais do handler. **A regra que pedi antes do upload foi cumprida.**
- Erros mapeados por camada: contrato e não suportado → 422; integridade → 500. A distinção entre recusa de entrada e falha interna está preservada.
- 797 testes verdes, verificados de forma independente, sem afrouxamento de nenhum teste anterior.

---

## 5. Sequência recomendada

1. **A1** — prazo total por requisição. É o único que eu trataria antes de qualquer uso com documentos de terceiros;
2. **I2** — seleção por papel em vez de índice;
3. **I3** — nome do tipo da exceção no log limitado;
4. **I1** — dimensionar `DEFAULT_MAX_BODY_BYTES` pela memória real e planejar transmissão em fluxo;
5. **M1–M4** quando convier.

Nenhum impede encerrar o ciclo 0057. A1 impede tratar a interface como exposta a qualquer processo não confiável — o que, no modelo de uso atual, máquina pessoal e túnel autenticado, é uma restrição que vocês já assumem.

---

## 6. Nota sobre o ciclo

Vale registrar: das duas auditorias externas deste ciclo, a do contrato pegou três problemas de arquitetura antes de existir código — a fronteira de entrega errada, a ausência de barreira de origem e a erosão da rejeição de chaves duplicadas —, e os três foram corrigidos no contrato antes da implementação. Auditar contrato antes de código custou menos do que teria custado descobrir A3 depois de a interface estar em uso.
