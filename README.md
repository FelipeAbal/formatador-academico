# Formatador Acadêmico

Projeto para adaptação conservadora de documentos acadêmicos a perfis formais explicitamente declarados.

## Estado atual

O projeto está na transição entre a fase metodológica e a implementação do motor.

O **corpus-base v1 está congelado** após:
- construção de 40 fixtures-base;
- inclusão de regressão C3;
- auditoria técnica do schema;
- auditoria adversarial externa;
- validação estrutural e semântica;
- rastreabilidade determinística entrada → saída.

Nenhum código do motor foi escrito até o congelamento do corpus.

## Princípio central

**Na dúvida, marcar.**

O sistema deve maximizar utilidade segura sem:
- inventar conteúdo;
- perder conteúdo substantivo;
- reescrever conteúdo intelectual;
- aplicar regra não configurada;
- alterar caso ambíguo silenciosamente.

## Estrutura

- `docs/handoff.md`: estado corrente e decisões consolidadas.
- `docs/architecture/`: decisões de arquitetura que começam na próxima fase.
- `docs/decisions/`: registros de decisões importantes.
- `corpus/manifest.json`: índice e metadados do corpus congelado.
- `corpus/fixtures/`: fixtures separados por tipo bibliográfico para facilitar diffs.
- `corpus/schemas/`: contratos JSON Schema.
- `corpus/catalogs/`: vocabulário, alertas e warnings esperados.
- `corpus/reports/`: relatórios de validação.
- `tools/build_corpus.py`: recompõe o corpus monolítico a partir dos fixtures por tipo.
- `tools/validate_corpus.py`: validação estrutural e semântica.
- `src/`: implementação do motor, ainda vazia.
- `tests/`: testes do motor, ainda vazia.

## Corpus v1

- 10 tipos bibliográficos.
- 4 funções por tipo.
- 40 fixtures-base.
- 1 regressão C3.
- Correções reais: 5 B1, 4 C2, 1 C3.
- Piso do motor nulo: 20/41 = 48,8%.

## Reconstrução e validação

Primeiro, gere o corpus monolítico:

```bash
python tools/build_corpus.py
```

Depois valide:

```bash
python tools/validate_corpus.py \
  corpus/schemas/fixture-v1.2.schema.json \
  corpus/corpus-fixtures-v1.generated.json \
  corpus/catalogs/alert-catalog-v1.json \
  corpus/catalogs/profile-vocabulary-v1.json \
  corpus/catalogs/expected-validation-warnings-v1.json
```

O corpus reconstruído a partir dos arquivos por tipo foi validado localmente com **zero erros estruturais e zero erros semânticos** antes da subida inicial ao GitHub.

## Status

**Corpus-base v1 congelado para implementação.**

A próxima fase é o desenho da arquitetura mínima do motor.
