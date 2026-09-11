# Brief de auditoria 0056

## Alvo

Auditar o commit `226e87a600260fd895e230aac8857ce66fcafd44`, na branch `perf/index-gate-review-targets-0056`, PR #43 do repositório `FelipeAbal/formatador-academico`.

O commit altera somente a resolução interna de alvos do SafetyGate e do Review DOCX. A proposta é construir um índice por `structural_path` uma vez por avaliação e reutilizá-lo, preservando a lista ordenada e todos os caminhos duplicados.

## Perguntas para o DeepSeek Flash 4.1

Faça uma auditoria adversarial focada no código:

1. `index_story_targets` retorna exatamente os mesmos registros e cadeias de ancestrais que `resolve_target`?
2. Caminhos duplicados continuam produzindo `TARGET_NOT_UNIQUE`?
3. Há risco de índice stale, mutação acidental, aliasing ou uso entre avaliações de snapshots diferentes?
4. O caminho unitário `gate_operation` continua semanticamente igual ao caminho de avaliação do plano?
5. O Review DOCX mantém a mesma seleção de candidatos, a mesma ordem e as mesmas provas de integridade?
6. Os testes cobrem suficientemente equivalência, duplicidade, histórias e falhas?
7. O ganho alegado de aproximadamente 15,7 s para 6,8 s em uma alteração é medido de forma válida?

## Perguntas para o Claude Opus

Faça uma auditoria completa de código, contratos, segurança e integração:

1. Compare a alteração com as decisões 0026, 0036, 0037 e o handoff atual.
2. Verifique se a otimização muda qualquer decisão, veto, evidência, hash, ordem de operações ou semântica de `ReviewMarkResult`.
3. Verifique determinismo, imutabilidade, comportamento com caminhos duplicados e preservação da cadeia de ancestrais.
4. Procure efeitos em `word/document.xml`, histórias, tabelas, hyperlinks, runs aninhados e candidatos de parágrafo.
5. Avalie se a redução de custo justifica o risco e se o PR deve ser integrado, ajustado ou rejeitado.
6. Indique testes adversariais faltantes e qualquer necessidade de revisar o handoff ou abrir nova emenda contratual.

## Limites

Não alterar o repositório durante a auditoria. Não usar os seis DOCX privados como parte do commit. A auditoria deve reproduzir ou inspecionar o código e os 772 testes, podendo usar fixtures sintéticas próprias.

## Evidência local

- `main` antes do PR: `a9b612af56b1eaca7d440d4c48ff47c498395e44`;
- 772 testes locais aprovados;
- CI do commit: run `34630021414`, concluída com sucesso;
- primeiro DOCX real, limitado a uma alteração: aproximadamente 15,7 s antes da indexação e 6,8 s depois, sob `cProfile`;
- os arquivos reais não devem ser incluídos no relatório de auditoria nem no Git.

## Formato esperado

Entregar achados por gravidade, cada um com arquivo/função, reprodução, impacto e correção recomendada. Encerrar com veredito: aprovado, aprovado com ajustes ou rejeitado.
