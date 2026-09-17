# Formatador Acadêmico

Protótipo local para adaptar documentos DOCX a regras formais explicitamente declaradas pelo usuário.

O sistema não promete conformidade acadêmica genérica. Ele altera somente propriedades autorizadas, preserva o documento original e encaminha casos ambíguos para revisão.

> **Princípio central:** na dúvida, marcar.

## Estado atual

O protótipo possui motor e interface web local funcionais. O fluxo recebe um DOCX e um perfil de regras, executa o pipeline conservador e entrega cinco arquivos vinculados por hashes:

1. DOCX limpo;
2. DOCX com destaques para revisão;
3. relatório técnico JSON;
4. relatório humano Markdown;
5. manifesto da entrega.

O slice automático atual cobre, separadamente para corpo e títulos:

- negrito;
- tamanho da fonte;
- entrelinha;
- alinhamento.

A suíte possui **851 testes**. O ciclo 0060A, que congelou o oráculo de equivalência das próximas otimizações, está integrado. O próximo passo técnico é o 0060B, dedicado ao desempenho do parser.

## Requisitos

- Python 3.12;
- ambiente virtual recomendado;
- dependências de `requirements.txt`.

No macOS ou Linux:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Iniciar o protótipo

Na raiz do repositório:

```bash
.venv/bin/python tools/run_local_web.py
```

O servidor imprime uma URL semelhante a:

```text
Formatador Acadêmico: http://localhost:8000/#TOKEN_DA_SESSAO
```

Abra exatamente essa URL no navegador. O token é válido somente enquanto aquele processo estiver rodando e não deve ser compartilhado ou salvo em favoritos.

Para usar outra porta:

```bash
.venv/bin/python tools/run_local_web.py --port 8080
```

O servidor aceita conexões somente em `127.0.0.1`.

## Usar a interface

1. selecione um arquivo `.docx`;
2. declare ao menos uma regra para corpo ou títulos;
3. ajuste o limite máximo de alterações, se necessário;
4. selecione **Processar documento**;
5. leia o status e o resumo;
6. baixe os cinco arquivos produzidos.

“Processamento concluído” significa que não restou outra alteração automática segura dentro do slice atual. Isso não significa conformidade integral.

## Acesso do Mac a um servidor no Ubuntu

Inicie o protótipo no Ubuntu. No Mac, abra um túnel SSH, substituindo o destino pelo usuário e host reais:

```bash
ssh -N -L 8000:127.0.0.1:8000 usuario@servidor-ubuntu
```

Depois abra no navegador do Mac a URL completa, incluindo o fragmento `#TOKEN`, impressa pelo processo no Ubuntu.

O servidor permanece inacessível pela rede externa: o acesso ocorre pelo túnel autenticado.

## Executar os testes

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```

O GitHub Actions executa a mesma suíte em cada PR e push para `main`.

## Limites atuais

- o protótipo é local; não há hospedagem pública, contas ou banco de dados;
- documentos e artefatos permanecem apenas em memória durante a requisição;
- não há correção automática de referências, citações, margens, tabelas ou estrutura intelectual;
- documentos grandes ainda podem levar vários minutos;
- documentos reais não entram no repositório nem no CI;
- medições com o corpus real ocorrem somente no Ubuntu e com autorização explícita.

## Próximas fases

O ciclo de desempenho segue fases independentes e sequenciais:

1. **0060B:** índice estrutural por chamada no parser;
2. **0060C:** reuso de bytes de serialização;
3. **0060D:** compartilhamento do parse verificado do mesmo snapshot;
4. **0060E:** medição oficial de desempenho e memória.

O 0061 só será considerado depois da medição final e não começa automaticamente.

## Documentação

- [estado corrente](docs/handoff.md);
- [guia do protótipo local](docs/guides/local-prototype-v01.md);
- [contrato do ciclo 0060](docs/decisions/0060-cycle-0060-conservative-performance-contract.md);
- [freeze do 0060A](docs/decisions/0060a-oracle-instruments-freeze.md).
