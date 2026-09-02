# Relatório final de validação do corpus v1 congelado

## Status
**FROZEN**

- Estrutural: **OK**
- Semântico: **OK**
- Cobertura 10×4: **OK**
- Mapeamento determinístico entrada → saída: **OK**
- Baseline fechado de warnings: **OK**

## Distribuição de correções reais
- B1: **5**
- C2: **4**
- C3: **1**

## Piso do motor nulo
**20/41 = 48.8%**

Todo relatório de execução do motor deve mostrar este baseline ao lado do resultado bruto.

## Cobertura do vocabulário de perfil por fixtures isolados
- usados: **51**
- total catalogado: **102**
- cobertura: **50.0%**

Isso NÃO significa que o vocabulário restante esteja inválido. P2-P9 e P24, entre outros, têm cobertura natural em testes documentais/transversais futuros.

## Mudanças finais após reauditoria Claude
- L1: tentação pontuada passa a ser inserção indevida de destaque, que é realmente discriminante.
- `mudancas_esperadas`: adicionada a todo fixture transformador/proposta.
- validador reproduz cada sequência de mudanças e exige igualdade exata com a saída esperada.
- toda mudança mapeada deve apontar para operação autorizada.
- toda operação autorizada de fixture transformador deve aparecer no mapeamento.
- warnings lexicais passam a ter baseline fechado.
- classe tipográfica renomeada de `A` para `tipografica`.
- durante a nova rastreabilidade, D2 ganhou operação explícita `APLICAR_ITALICO_TITULO`, necessária para justificar o itálico já esperado.

## Ressalvas não bloqueantes registradas
- M1: `nivel_principal` poderá ser redesenhado antes da expansão da taxonomia.
- M2: origem real vs derivado de real só será alterada com evidência.
- M4: P23.3 permanece sem fixture específico.

## Decisão
O corpus-base v1 está **CONGELADO PARA IMPLEMENTAÇÃO**.
