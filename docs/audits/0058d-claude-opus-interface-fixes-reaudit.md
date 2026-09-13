# Reauditoria das correções da interface web — PR #55, head `d42a3b8` (Claude Opus)

**Auditor:** Claude Opus 5
**Data:** 2026-09-13
**Alvo:** PR #55, branch `fix/0058-interface-findings-clean`, head `d42a3b8638045d097b6fd67551c499453f0c4846`
**Auditoria anterior:** `0058c-claude-opus-interface-fixes-reaudit.md`, sobre `b0516c6`
**Mudança desde a auditoria anterior:** um commit, `d42a3b8` ("fix: close request deadlines and explain processing limits"), em `web_app/server.py`, `static/app.js` e `tests/test_web_app_server_v01.py` (+2)
**Base:** `main` @ `4388bfa`
**Suíte executada localmente:** **804 passed, 1 warning, 22.76s**
**Repositório não modificado.** Sondas fora da árvore, contra instâncias efêmeras em porta 0.
**Plataforma das sondas:** macOS. **Não havia ambiente Linux disponível** — sem Docker, Podman, Colima, OrbStack, Multipass ou Lima. O servidor de produção é Ubuntu, e o CI roda em `ubuntu-latest` com Python 3.12.

---

## Veredito

# APROVADO COM AJUSTES OBRIGATÓRIOS

**O bloqueante N1 está corrigido, e os três bloqueantes anteriores seguem corrigidos**, todos verificados pela reexecução das mesmas sondas. `operation_limit_reached` e `quiescent_with_unapplied` passaram a ter mensagens fiéis. Não restam bloqueantes de segurança verificados no macOS.

Duas coisas ainda precisam entrar antes do merge:

- a mensagem de `quiescent` **continua afirmando algo falso**;
- as correções do servidor seguem **sem nenhum teste de comportamento**. Como o expirar do prazo agora depende da semântica de `shutdown(SHUT_RD)`, que varia entre sistemas operacionais, esses testes são **a única forma de verificar o comportamento no Linux**, que é o sistema de produção.

---

## Estado dos achados

| Achado | Estado | Evidência |
|---|---|---|
| N1 — `Timer` acumulando fora do teto | **corrigido** | 900 conexões vazias, malformadas e com método desconhecido → **0 timers vivos**, 2 threads em repouso |
| B1 — pausa derrubava o upload | **corrigido** | pausa de 1,5 s → `200 OK` |
| B2 — gotejamento de corpo contornava o prazo | **corrigido** | 1 byte/0,5 s com prazo de 2 s → `400 request body is incomplete` em **2,0 s** |
| B3 — slowloris em cabeçalhos | **corrigido** | dois gotejamentos, teto 2 → cliente legítimo `200` |
| A2 (0058) — processamento cortado pelo prazo | **preservado** | 4 s de processamento com prazo de leitura de 2 s → `200` em **4,1 s** |
| I2 — `operation_limit_reached` como "concluído" | **corrigido** | `app.js:96` "Limite de alterações atingido…"; `app.js:98` "…com ressalvas…" |
| I1 — mensagem de `quiescent` falsa | **aberto** | `app.js:94`, texto inalterado |
| I3 — lexema numérico sem validação | **aberto** | `app.js:22` |
| I4 — testes de texto em vez de comportamento | **aberto, mais crítico** | ver L1 |
| I5 — trabalho órfão sem limite | **aberto** | sem limite de processamentos simultâneos |
| I6 — `ProfileRef` fixo | **aberto** | `app.js:31` |
| M1, M4 — CSP sem `form-action`/`base-uri`; sem CORP | **abertos** | ausentes em `server.py` |
| M6 — formato do log depende do Python | **aberto** | `server.py:142`, `str(code)`; sonda registrou `('POST', 'HTTPStatus.OK')` |
| M2, M3, M5, M7, M8, M9 | **abertos** | ver auditorias 0058b e 0058c |

---

## 🟠 L1 — O expirar do prazo depende de `SHUT_RD`, não verificado no Linux e sem rede de segurança

**Arquivo:** `web_app/server.py`, `_expire_read_phase` e `_read_body_bytes`.

**[FATO]** O commit trocou o fechamento do socket por um desligamento só da leitura:

```python
@staticmethod
def _expire_read_phase(connection: socket.socket) -> None:
    try:
        connection.shutdown(socket.SHUT_RD)
    except OSError:
        pass
```

e a leitura do corpo segue sem timeout de operação:

```python
self.connection.settimeout(None)
return self.rfile.read(limit)
```

Assim, o prazo **só** interrompe uma leitura bloqueada se `shutdown(SHUT_RD)` acordar o `recv` em andamento. Não há outra barreira.

**[FATO]** No macOS isso funciona. B2 e B3 foram cortados no prazo, conforme a tabela acima.

**[INFERÊNCIA]** No Linux, a expectativa é a mesma: `shutdown(SHUT_RD)` marca a leitura como desligada e acorda quem espera no socket, e o `recv` bloqueado retorna 0. O Linux tem uma particularidade conhecida — dados que chegam **depois** do `SHUT_RD` ainda podem ser entregues por `recv` —, mas `BufferedReader` trata o primeiro retorno 0 como fim de arquivo e devolve o que já leu. Por isso a peculiaridade não deveria manter a leitura viva. **Isso não foi executado em Linux.**

**Impacto se a inferência estiver errada:** com `settimeout(None)`, uma leitura não acordada fica bloqueada **indefinidamente**, segurando uma vaga de conexão. Seria o slowloris de volta, sem nenhum limite.

**Correção:**

1. **Rede de segurança:** em vez de `settimeout(None)`, usar um timeout de operação igual ao prazo mais uma margem, por exemplo `DEFAULT_UPLOAD_TIMEOUT_SECONDS + 5`. Isso não reintroduz B1: aquele defeito vinha de um timeout **curto** seguido de **nova tentativa**. Um timeout longo e terminal, sem nova tentativa, só atua se o `Timer` falhar.
2. **Verificação no sistema de produção:** transformar as quatro sondas desta auditoria em testes da suíte — pausa no upload, gotejamento de corpo, gotejamento de cabeçalhos e acúmulo de `Timer`. O CI roda em `ubuntu-latest`, então esses testes passam a ser a verificação da semântica de `SHUT_RD` no Linux, que esta auditoria não conseguiu fazer.

---

## 🟠 I1 — A mensagem de `quiescent` continua falsa

**Arquivo:** `static/app.js:94`.

**[FATO]** O texto não mudou: *"Processamento concluído. Nenhuma alteração automática segura foi necessária. Isso não significa conformidade integral."*

**[FATO]** A auditoria 0058b reproduziu `session_status=quiescent` com `applied=3`, e o comportamento do servidor que produz esse status não foi alterado.

**[INFERÊNCIA]** `quiescent` significa que **não restou** alteração automática segura ao final, não que nenhuma foi necessária. O commit corrigiu as duas mensagens vizinhas e deixou justamente esta. O teste `test_page_explains_quiescent_and_uses_session_storage` continua garantindo a presença da frase.

**Correção:** *"Processamento concluído. Não restaram alterações automáticas seguras a aplicar. Isso não significa conformidade integral."*, acompanhada das contagens de aplicadas, em revisão, não aplicadas e abstenções.

---

## 🟠 I4 — As correções do servidor continuam sem teste de comportamento

**[FATO]** A busca por testes de pausa, gotejamento, prazo, `Timer` ou contagem de threads nos testes da interface não encontra nada. As duas linhas acrescentadas por este commit são `assertIn` de texto estático das mensagens novas.

**[INFERÊNCIA]** N1, B1, B2 e B3 foram corrigidos ao longo de três commits e **nenhum** entrou com teste de regressão. Cada um já foi quebrado uma vez por uma correção vizinha — o A2 pelo `Timer` total, B1–B3 pelo leitor com prazo, N1 pelo `Timer` por requisição —, e a suíte ficou verde em todos esses casos. Somado a L1, o custo de não ter esses testes deixou de ser teórico.

**Correção:** as quatro sondas desta auditoria como testes, com o prazo reduzido por monkeypatch, como foi feito aqui. Mantidas curtas, cabem na suíte.

---

## 🟠 Achados que continuam abertos das auditorias anteriores

- **I3 — `app.js:22`.** O valor de `control.value.trim()` é inserido cru no JSON. `.5` gera `json_invalid`.
- **I5.** Fechar a aba não interrompe o processamento, e não há limite de processamentos simultâneos separado das vagas de conexão.
- **I6 — `app.js:31`.** `ProfileRef` segue fixo em `web-interface`/`1`.

## 🟡 Menores

- **M1 e M4.** A CSP ainda não tem `form-action 'none'` nem `base-uri 'none'`, e os estáticos não enviam `Cross-Origin-Resource-Policy: same-origin`.
- **M2, M3 e M5.** Revogação dos Blob URLs; resumo com as chaves técnicas em inglês (`appendSummary` inalterado) e erros do servidor exibidos crus; teste do arquivo extra em `static/`.
- **M6.** `server.py:142` grava `str(code)`, que muda de formato entre Python 3.9 e 3.11+.
- **M7.** O prazo de 30 s cobre linha de requisição, cabeçalhos e corpo de até 64 MiB, o que exige cerca de 17 Mbit/s sustentados pelo túnel. Dimensionar os dois juntos.
- **M8.** Mesclar por **squash**: o histórico do PR tem deleção e restauração em massa e commits vazios de CI.
- **M9.** `fix/0058-interface-findings`, sem o sufixo `-clean`, é a publicação incompleta e não deve ser mesclada. As branches de ciclos fechados e as de auditoria já incorporadas podem ser apagadas depois do merge.
- **N2 — silêncio em `_reject`.** Falhas de escrita da resposta agora são descartadas por `except OSError: return`, sem registro no log limitado. É aceitável para conexões encerradas pelo prazo, mas convém registrar ao menos `("REJECT", "OSError")` para manter o diagnóstico que a auditoria final do ciclo 0057 pediu.
- **Descrição do PR desatualizada.** Ainda diz "803 testes aprovados" e não descreve o mecanismo de prazo atual.

---

## O que está correto e deve ser preservado

- **Cancelamento do `Timer` em `finally` dentro de `handle_one_request`.** Cobre conexão vazia, linha malformada, método desconhecido e toda rota. O número de timers vivos fica limitado pelas conexões simultâneas.
- **Separação de fases preservada.** O prazo cobre linha de requisição, cabeçalhos e corpo, e é cancelado antes de `build_product_from_inputs`.
- **`SHUT_RD` em vez de fechar o socket.** Permite escrever a resposta de erro depois de o prazo expirar: o gotejamento de corpo recebe `400 request body is incomplete` em vez de um reset silencioso.
- **Mensagens fiéis para `operation_limit_reached` e `quiescent_with_unapplied`**, alinhadas ao contrato 0057 §6.
- **`settimeout` restaurado dentro de `try`**, tolerante a socket já desligado.
- Tudo o que as auditorias anteriores listaram como correto continua valendo: superfície pública fechada, `Host` antes de tudo, CSP e cabeçalhos, `justify`, negrito em três estados, decimal preservado até a fronteira, perfil opaco e ausência de `innerHTML`.
- 804 testes verdes, verificados de forma independente.

---

## Sequência recomendada

**Antes do merge:**

1. **I1** — corrigir a frase de `quiescent` e o teste que a garante;
2. **I4 + L1** — as quatro sondas como testes, executadas no CI em Linux, e timeout de operação terminal como rede de segurança no lugar de `settimeout(None)`;
3. **M8** — squash.

**Antes de uso com usuários:** I3, I5, I6.

**Quando convier:** M1–M7, M9, N2 e a descrição do PR.
