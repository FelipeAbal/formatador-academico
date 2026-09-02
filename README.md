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
- `corpus/`: corpus congelado, schema, catálogos e relatórios.
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

## Validação

O corpus congelado deve passar por:

```bash
python tools/validate_corpus.py \
  corpus/schemas/fixture-v1.2.schema.json \
  corpus/corpus-fixtures-v1.json \
  corpus/catalogs/alert-catalog-v1.json \
  corpus/catalogs/profile-vocabulary-v1.json \
  corpus/catalogs/expected-validation-warnings-v1.json
```

## Status

**Corpus-base v1 congelado para implementação.**

A próxima fase é o desenho da arquitetura mínima do motor.
