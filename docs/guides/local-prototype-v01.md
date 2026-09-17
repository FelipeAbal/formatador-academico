# Guia do protótipo local v0.1

## Objetivo

Este guia executa o protótipo de ponta a ponta sem publicar documentos ou abrir o servidor para a rede.

## 1. Preparação

Na raiz do repositório:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## 2. Inicialização

```bash
.venv/bin/python tools/run_local_web.py
```

Mantenha o processo aberto. Ele imprime a URL completa e o token da sessão. O serviço escuta somente em `127.0.0.1:8000`.

Para encerrar, pressione `Ctrl+C` no terminal.

## 3. Acesso no mesmo computador

Abra exatamente a URL impressa pelo servidor, incluindo `#TOKEN`.

O navegador guarda o token em `sessionStorage` e o remove da barra de endereços. Não salve a URL original em favoritos nem compartilhe o token.

## 4. Acesso do Mac ao Ubuntu

Com o servidor já iniciado no Ubuntu, execute no Mac:

```bash
ssh -N -L 8000:127.0.0.1:8000 usuario@servidor-ubuntu
```

Abra no Mac a URL impressa no Ubuntu. O túnel precisa permanecer ativo durante o processamento e os downloads.

## 5. Smoke test manual

Use primeiro um DOCX sintético ou descartável, sem dados pessoais.

1. selecione o DOCX;
2. em “Regras para o corpo do texto”, escolha **Negrito: ausente**;
3. mantenha o limite padrão de operações;
4. processe o documento;
5. confirme que o resultado não afirma conformidade integral;
6. confirme a presença de cinco links de download;
7. baixe os arquivos e preserve o original separadamente.

Arquivos esperados:

- DOCX limpo;
- DOCX de revisão;
- relatório técnico JSON;
- relatório humano Markdown;
- manifesto JSON.

## 6. Verificações antes de usar documentos reais

- execute a suíte completa;
- confirme que o servidor está ligado somente a `127.0.0.1`;
- use um token recém-gerado;
- confirme espaço e tempo disponíveis no Ubuntu;
- não copie os documentos para o repositório;
- não publique logs, nomes ou hashes sem revisar o registro autorizado da rodada.

O teste formal dos seis documentos reais exige autorização explícita por rodada e pertence às fases de medição do ciclo 0060.

## 7. Resolução rápida de problemas

**A página informa token ausente.** Abra novamente a URL completa impressa pelo servidor.

**A porta 8000 está ocupada.** Inicie com `--port 8080` e ajuste os dois lados do túnel.

**O perfil foi rejeitado.** Declare ao menos uma regra e use apenas os valores oferecidos pela interface.

**O processamento demora.** Não interrompa documentos grandes sem necessidade. O ciclo 0060B–0060E existe para reduzir esse custo sem alterar os resultados.

**O navegador perdeu os downloads.** Processe novamente; o servidor não mantém os artefatos depois da resposta.

## 8. Evidência do checkpoint

Em 2026-09-17, o launcher foi executado em processo real e recebeu uma requisição HTTP com fixture DOCX sintética. O resultado foi:

```text
HTTP 200
session_status: quiescent
file_count: 5
roles: clean_docx, review_docx, technical_report, human_report, manifest
```

Os cinco conteúdos foram decodificados e seus tamanhos e SHA-256 foram conferidos contra o envelope da resposta. Nenhum documento real foi usado.
