# Decisão 0057: interface web local v0.1

**Estado:** proposta para auditoria
**Data:** 2026-09-11
**Escopo:** primeira interface utilizável do Formatador Acadêmico

## 1. Decisão

A primeira interface user-facing será uma aplicação web local, executada no Ubuntu do mantenedor e acessada pelo navegador no Mac.

O servidor será iniciado manualmente no Ubuntu e ficará restrito a `127.0.0.1`. O acesso a partir do Mac ocorrerá por túnel SSH:

```text
Mac, navegador
    ↓ http://localhost:8000
túnel SSH
    ↓
Ubuntu, servidor local em 127.0.0.1:8000
```

Não haverá hospedagem pública, envio automático de documentos para a internet ou dependência de serviço externo.

## 2. Objetivo da v0.1

Permitir que uma pessoa:

1. selecione um DOCX existente;
2. informe regras explicitamente declaradas;
3. execute o pipeline congelado do produto;
4. veja um resumo honesto do resultado;
5. baixe os arquivos produzidos.

A interface não calcula conformidade por conta própria. Ela apenas coleta a entrada, chama a fronteira pública do produto e apresenta as saídas tipadas.

## 3. Entradas

### 3.1 Documento

- um arquivo DOCX selecionado pelo usuário;
- leitura integral em memória;
- nenhuma alteração no arquivo original;
- limite inicial de corpo HTTP de 64 MiB, verificado antes de materializar o corpo completo;
- rejeição de arquivo vazio, tipo incompatível ou falha de leitura.

### 3.2 Perfil

A interface produzirá JSON compatível com o Profile Input v0.3 já existente. Esse JSON será transportado como uma parte opaca `application/json` da requisição multipart e será repassado em bytes, sem ser convertido em objeto, reserializado ou incorporado a outro JSON. Assim permanecem ativas as rejeições de chaves duplicadas, BOM, encoding inválido e campos desconhecidos.

O formulário inicial permitirá configurar, separadamente para `body` e `heading`:

- negrito;
- tamanho da fonte;
- entrelinha em múltiplos de linha;
- alinhamento.

Campos sem regra permanecerão ausentes no JSON. A interface não criará regras implícitas para campos não preenchidos.

O JSON final deverá continuar sendo validado pelo parser congelado do Profile Input. A interface não substituirá as validações do domínio.

## 4. Saídas

Após processamento bem-sucedido, a interface apresentará os cinco arquivos tipados produzidos pela camada de entrega:

1. DOCX limpo;
2. DOCX destacado para revisão;
3. Processing Report JSON;
4. relatório humano Markdown;
5. `manifest.json`, com nomes, papéis, media types, tamanhos e hashes.

O resumo será exibido na página e não será contado como arquivo adicional. A categoria de abstenções corresponderá literalmente a `classification_items` do `ProcessingReport`.

Os arquivos serão derivados das APIs já existentes:

```text
build_product_from_inputs(...)
→ ProductOutputBundle
→ build_product_delivery(...)
→ ProductDelivery, com cinco DeliveryFile
```

A interface fornecerá apenas o `base_name`, derivado do nome enviado e entregue à camada congelada para canonicalização. Não chamará `render_processing_report` diretamente, não inventará nomes, não reconstruirá o manifest e não editará os arquivos por conta própria.

## 5. Transporte local

A primeira implementação usará `ThreadingHTTPServer`, da biblioteca padrão, e uma página HTML estática, sem biblioteca JavaScript externa. A superfície pública será uma lista fechada de três recursos, comparados por igualdade exata: `/`, `/static/app.js` e `/static/style.css`. Eles conterão somente recursos estáticos, sem dados do usuário, token ou nomes de arquivos. Não haverá servidor de arquivos por prefixo, acesso ao sistema de arquivos derivado do caminho recebido ou rotas públicas adicionais. Somente `GET` será público; `HEAD` e os demais métodos continuarão sujeitos à autorização.

O navegador enviará o documento e o perfil ao servidor local por multipart. O servidor retornará, em uma única resposta, os cinco `DeliveryFile` codificados para que o navegador crie os downloads localmente. Não haverá endpoint posterior de download nem retenção de bytes entre requisições.

O perfil será uma parte multipart opaca `application/json`. O parser multipart mínimo será implementado sobre componentes disponíveis na biblioteca padrão, sem usar o módulo `cgi`, removido no Python 3.13. O corpo será limitado antes da leitura integral.

O servidor não deverá:

- aceitar conexões externas ao próprio Ubuntu;
- gravar documentos em diretórios permanentes;
- manter histórico de documentos processados;
- executar comandos recebidos pelo navegador;
- carregar recursos externos;
- aceitar caminhos de arquivo enviados pelo cliente.

Cada processo do servidor gerará um token aleatório de sessão no arranque. O token será impresso junto com a URL e exigido em toda requisição de saúde e processamento. A aplicação verificará:

- `Origin`, aceitando somente a origem local esperada;
- `Sec-Fetch-Site`, recusando requisições cross-site quando presente;
- `Host`, aceitando somente o conjunto fechado derivado da porta ligada: `127.0.0.1:<porta>`, `localhost:<porta>` e `[::1]:<porta>`;
- método HTTP, aceitando apenas os métodos previstos;
- token de sessão, usando comparação segura.

Como o fragmento de uma URL não é enviado ao servidor, a URL inicial terá o formato `http://localhost:8000/#TOKEN`. O `GET /` e os dois recursos estáticos acima não exigirão o token, mas continuarão exigindo um `Host` permitido. Essa é uma superfície pública fechada, estática e sem dados. As rotas de saúde, processamento e qualquer outro caminho exigirão autenticação antes do roteamento.

O JavaScript lerá o token de `location.hash`, gravará esse valor em `sessionStorage` e depois usará `history.replaceState` para removê-lo da barra de endereços e da entrada atual da sessão. Isso não apaga necessariamente histórico, preenchimento automático, sincronização, restauração de sessão ou recuperação de falha do navegador. A URL com o token não deverá ser salva em favoritos nem compartilhada. O token não será guardado em `localStorage`.

Os recursos públicos enviarão `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` e `X-Frame-Options: DENY`. A página enviará também a política `Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'`, que torna verificável a ausência de recursos externos. A escolha do fragmento é especialmente importante porque o túnel SSH faz `localhost` existir também no Mac: servir o token em HTML ou em resposta HTTP o exporia a processos locais daquela máquina.

O token é a fronteira de autorização. `Host`, `Origin` e `Sec-Fetch-Site` são camadas adicionais contra roteamento incorreto e requisições iniciadas por outra origem; a ausência dos cabeçalhos opcionais não substitui o token. `OPTIONS` permanecerá recusado enquanto não houver contrato explícito de CORS.

O servidor usará prazo absoluto de 30 segundos para receber o corpo do upload, além do timeout de operação de socket, e limite de conexões simultâneas. O prazo de upload não será aplicado durante o processamento do pipeline, para que a conexão do usuário permaneça disponível enquanto os cinco artefatos são produzidos. O log operacional será limitado e não reterá linhas de requisição, caminhos, cabeçalhos ou bytes de documentos.

Como os downloads serão montados no navegador a partir da resposta única, não haverá identificador de download reutilizável nem armazenamento de artefatos no servidor.

O uso pelo Mac dependerá de um túnel SSH autenticado pelo usuário. A configuração de SSH e a eventual regra de firewall pertencem à instalação operacional, não ao contrato do produto.

## 6. Segurança e preservação

A aplicação deverá respeitar todas as invariantes do núcleo:

- na dúvida, não alterar;
- não alterar conteúdo intelectual;
- não inventar regras ou valores;
- preservar o arquivo original;
- executar somente o que o pipeline congelado autorizar;
- manter a distinção entre alteração aplicada, revisão, item não aplicado e abstenção;
- exibir erros de contrato e integridade sem convertê-los em sucesso;
- não afirmar conformidade integral apenas porque o processamento terminou;
- não reter bytes do documento ou artefatos depois de concluída a resposta;
- manter os bytes somente durante a requisição e a criação dos downloads no navegador.

O servidor deverá rejeitar o corpo antes de materializá-lo quando o `Content-Length` exceder 64 MiB e, quando o cabeçalho estiver ausente ou não for confiável, ler no máximo 64 MiB mais um byte antes de rejeitar. Requisições fora do formato definido deverão ser recusadas.

O formulário deverá expor `max_applied_operations`, com valor inicial igual ao limite padrão vigente do núcleo e possibilidade de redução pelo usuário. O resultado `operation_limit_reached` será mostrado como limite atingido, nunca como processamento concluído sem ressalvas. A interface deverá preservar a representação decimal digitada pelo usuário até o parser do perfil, sem converter números por `Number()` antes do envio. O controle de negrito deverá permitir ausência, exigência ou ausência de regra. O resultado deverá explicar que `quiescent` não equivale a conformidade integral.

## 7. Tecnologia inicial

A implementação preferirá a biblioteca padrão do Python, com servidor HTTP local e frontend HTML/CSS/JavaScript sem dependências externas.

O uso da GPU do Ubuntu não faz parte desta versão. O processamento atual é determinístico e não utiliza modelo de IA. A escolha do Ubuntu se deve à maior disponibilidade de CPU, memória e armazenamento, além da possibilidade de acrescentar tarefas locais futuras sem mover a aplicação.

## 8. Fora do escopo

Ficam fora da v0.1:

- hospedagem pública;
- contas e autenticação própria;
- banco de dados;
- fila de processamento;
- processamento simultâneo de vários documentos;
- edição de conteúdo;
- referências bibliográficas;
- PDF;
- alteração global de estilos;
- novas propriedades de formatação;
- uso de IA durante o processamento;
- instalação automática no Ubuntu;
- abertura automática de portas na rede local.

## 9. Critérios de aceitação

A v0.1 será considerada pronta para teste quando os critérios automatizáveis forem atendidos:

1. aceitar multipart com DOCX e perfil JSON opaco;
2. produzir os cinco arquivos da camada `ProductDelivery`, sem reconstrução na interface;
3. exibir contagens coerentes com o `ProcessingReport`;
4. mapear abstenções para `classification_items`;
5. recusar perfil inválido sem executar o DOCX;
6. recusar arquivo vazio ou corpo acima do limite sem leitura integral acima do limite;
7. não afirmar conformidade quando o resultado for quiescente ou tiver zero itens;
8. exibir sempre status da sessão, contagens e cobertura, inclusive as exclusões do slice;
9. exibir `operation_limit_reached` como limite atingido;
10. recusar origem, host, token ou método não previstos;
11. manter a suíte existente verde;
12. preservar os bytes dos `DeliveryFile` exatamente;
13. duas requisições concorrentes não podem compartilhar artefatos ou token.

O checklist manual de instalação e uso será separado:

1. iniciar no Ubuntu com um comando documentado;
2. abrir no navegador do Mac por túnel SSH;
3. confirmar que o servidor permanece em `127.0.0.1`;
4. confirmar que não há arquivos temporários persistentes;
5. testar os seis DOCX reais fornecidos, sem incorporá-los ao Git.

## 10. Sequência de implementação

1. servidor local mínimo com rota de saúde;
2. página inicial com seleção de DOCX e edição do perfil;
3. endpoint de processamento usando a fronteira pública existente;
4. apresentação dos resumos e downloads;
5. testes de contrato, limites e erros;
6. instalação orientada no Ubuntu;
7. teste end-to-end a partir do Mac.

## 11. Decisões fechadas após auditoria

- transporte: multipart;
- perfil: parte `application/json` opaca, repassada em bytes;
- limite inicial de corpo HTTP: 64 MiB;
- limite de trabalho: `max_applied_operations` exposto no formulário;
- resposta: única resposta contendo os cinco arquivos da `ProductDelivery`, sem endpoint posterior de download;
- servidor: `ThreadingHTTPServer`;
- transporte: hosts locais em conjunto fechado, timeout por requisição e teto de conexões simultâneas;
- segurança: token de arranque, verificação de `Origin`, `Sec-Fetch-Site`, `Host` e métodos;
- abstenções: correspondem a `classification_items`;
- zero itens não significa conformidade;
- critérios ambientais e uso com DOCX reais ficam em checklist manual.

Essas decisões pertencem somente à camada de interface local e não alteram a autoridade do núcleo de processamento.
