# Decisão 0048: Product Delivery / File Naming v0.1 - freeze

**Status:** ACEITA E CONGELADA  
**Data:** 2026-09-10  
**Base:** PR #18, merge squash `565ab01d4afab0dc240f136c70995ebd1227ac79`  
**Auditoria:** Claude Opus, `docs/audits/auditoria_claude_opus_formatador_565ab01.md`

## Decisão

O contrato Product Delivery / File Naming v0.1 fica congelado na forma implementada e validada na PR #18.

A camada entrega exatamente cinco arquivos tipados em memória:

1. `<base>_limpo.docx`;
2. `<base>_revisao.docx`;
3. `<base>_relatorio.json`;
4. `<base>_relatorio.md`;
5. `<base>_manifest.json`.

## Garantias congeladas

- nomes determinísticos e seguros;
- rejeição de paths, traversal, nomes ocultos e nomes reservados do Windows;
- bytes derivados do `ProductOutputBundle` e do relatório humano;
- hashes, tamanhos, roles e media types no manifest;
- vínculo das mídias incorporadas ao DOCX;
- processamento inteiramente em memória;
- nenhuma gravação em filesystem;
- nenhum ZIP;
- nenhuma reexecução do processamento;
- nenhuma alteração no `ProductOutputBundle` congelado;
- nenhuma nova autoridade normativa.

## Evidências

- PR #18 integrada na `main`;
- CI pós-merge verde na run `34500432604`;
- suíte com 735 testes aprovados;
- auditoria independente do Claude Opus sem falha conhecida no contrato;
- PR #19, que registrou a auditoria e corrigiu o handoff, integrada na `main` pelo commit `af7451f356259550dfe03016177444afed747d29`.

## Limites

Esta decisão não inclui:

- ZIP;
- persistência;
- interface;
- API;
- alteração de propriedades de formatação;
- execução em nível de parágrafo;
- alteração de `styles.xml`, `numbering.xml` ou stories secundárias.

## Relação com as próximas decisões

O próximo ciclo será a decisão 0049, Paragraph Target Enablement v0.1, com P4/alignment como carga executável.

A decisão 0049 deverá preservar este contrato e provar que a extensão de parágrafo não quebra a entrega atômica, o manifest, os hashes, o relatório ou a rastreabilidade do bundle.
