# Auditoria 0052A: revisão de código pelo DeepSeek Flash 4.1

## Objeto

Revisar o código integrado do Formatador Acadêmico no commit:

```text
08fed75e81541d439bf31bd532ecf4096896a6b2
```

O PR #29, que implementou P3/`spacing.line`, foi integrado por squash após auditoria do Claude Opus e CI verde com 758 testes.

## Papel da auditoria

Esta é uma revisão técnica de código. Não alterar arquivos, não criar commits e não redesenhar contratos. O objetivo é encontrar defeitos concretos que possam ter passado pelos testes.

## Áreas prioritárias

1. **P3 e Profile Input 0.3**
   - validação de múltiplos de linha;
   - equivalência de `1.5`, `1.50` e `1.5e0`;
   - conversão exata por 240;
   - limites, expoentes e precisão;
   - modos `exact`, `set` e `preserve`;
   - compatibilidade estrita com schemas 0.1 e 0.2.

2. **Analysis**
   - leitura de `auto`, `exact` e `atLeast`;
   - `lineRule` sem `line`;
   - unidades universais como `18pt`;
   - herança por estilo;
   - listas e bidi;
   - preservação da evidência bruta.

3. **Patcher**
   - mutação mínima;
   - ordem de `w:pPr` e `w:spacing`;
   - preservação dos demais atributos;
   - pré-condição, allowed delta e pós-condição;
   - duplicatas e formas não canônicas;
   - conversões que dependam do contexto global de `Decimal`.

4. **Pipeline**
   - Decision Layer não alterar automaticamente `exact` ou `atLeast`;
   - Processing Session;
   - SafetyGate;
   - Transform Log;
   - Review DOCX;
   - determinismo e reexecução.

5. **Regressões**
   - P1, P2 e P4;
   - documentos sem estilos;
   - múltiplos runs;
   - falhas atômicas;
   - preservação de arquivos e partes não autorizadas.

## Procedimento

- ler os contratos 0048, 0049 e 0051;
- ler a auditoria Claude registrada em `docs/audits/auditoria_claude_opus_0051.md`;
- inspecionar o diff do PR #29 e o código final na `main`;
- executar a suíte existente quando possível;
- propor casos de teste mínimos para cada achado;
- não considerar “os testes passam” como prova de ausência de defeito.

## Formato da resposta

Para cada achado:

- severidade: bloqueante, alta, média ou baixa;
- arquivo e função;
- comportamento observado;
- impacto;
- reprodução ou teste sugerido;
- correção recomendada;
- confiança.

Separar claramente:

- defeitos confirmados;
- riscos não confirmados;
- sugestões de melhoria;
- pontos aprovados.

Não sugerir mudanças apenas por preferência de estilo. Priorizar segurança, preservação do DOCX, determinismo, compatibilidade e coerência entre camadas.
