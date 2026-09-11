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
- limite inicial de tamanho definido no servidor antes do processamento;
- rejeição de arquivo vazio, tipo incompatível ou falha de leitura.

### 3.2 Perfil

A interface produzirá JSON compatível com o Profile Input v0.3 já existente.

O formulário inicial permitirá configurar, separadamente para `body` e `heading`:

- negrito;
- tamanho da fonte;
- entrelinha em múltiplos de linha;
- alinhamento.

Campos sem regra permanecerão ausentes no JSON. A interface não criará regras implícitas para campos não preenchidos.

O JSON final deverá continuar sendo validado pelo parser congelado do Profile Input. A interface não substituirá as validações do domínio.

## 4. Saídas

Após processamento bem-sucedido, a interface apresentará:

1. DOCX limpo;
2. DOCX destacado para revisão;
3. Processing Report JSON;
4. relatório humano Markdown;
5. resumo com alterações aplicadas, itens para revisão, itens não aplicados e abstenções.

Os arquivos serão derivados das APIs já existentes:

```text
build_product_from_inputs(...)
→ ProductOutputBundle

render_processing_report(...)
→ RenderedProcessingReport
```

A interface não editará nem reconstruirá esses arquivos por conta própria.

## 5. Transporte local

A primeira implementação usará um servidor HTTP local e uma página HTML estática, sem biblioteca JavaScript externa.

O navegador enviará o documento e o perfil ao servidor local. O servidor retornará os artefatos para download na mesma sessão.

O servidor não deverá:

- aceitar conexões externas ao próprio Ubuntu;
- gravar documentos em diretórios permanentes;
- manter histórico de documentos processados;
- executar comandos recebidos pelo navegador;
- carregar recursos externos;
- aceitar caminhos de arquivo enviados pelo cliente.

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
- limpar referências aos bytes do documento ao final da requisição, quando tecnicamente possível.

O servidor deverá limitar o tamanho do corpo HTTP e rejeitar requisições que não estejam no formato definido pela aplicação.

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

A v0.1 será considerada pronta para teste quando:

1. iniciar no Ubuntu com um comando documentado;
2. abrir no navegador do Mac por túnel SSH;
3. aceitar um DOCX e um perfil válido;
4. produzir os quatro artefatos previstos;
5. exibir contagens coerentes com o Processing Report;
6. recusar perfil inválido sem executar o DOCX;
7. recusar arquivo vazio ou requisição acima do limite;
8. não gravar o documento enviado em diretório permanente;
9. manter a suíte existente verde;
10. ser testada com os seis DOCX reais fornecidos, sem incorporá-los ao Git.

## 10. Sequência de implementação

1. servidor local mínimo com rota de saúde;
2. página inicial com seleção de DOCX e edição do perfil;
3. endpoint de processamento usando a fronteira pública existente;
4. apresentação dos resumos e downloads;
5. testes de contrato, limites e erros;
6. instalação orientada no Ubuntu;
7. teste end-to-end a partir do Mac.

## 11. Decisões ainda abertas

Antes da implementação, a auditoria deverá verificar:

- se o transporte de bytes em JSON é adequado para o limite inicial ou se deve ser usado multipart;
- qual limite inicial de tamanho do DOCX é seguro para o processamento disponível;
- se o relatório humano deve ser baixado junto com os demais arquivos ou apenas exibido e baixado separadamente;
- se o servidor padrão deve encerrar após uma requisição ou permanecer ativo até interrupção manual.

Nenhuma dessas questões altera a autoridade do núcleo de processamento. Elas pertencem somente à camada de interface local.
