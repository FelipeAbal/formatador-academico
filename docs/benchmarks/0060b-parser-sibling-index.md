# Medição sintética do índice de irmãos — 0060B

Data: 2026-09-17.

## Escopo

Esta medição compara o parser da `main` no commit `c0604ca429232fb044d05ac7f0e0b20bc144d664` com a implementação do 0060B. Os dois lados processaram exatamente os mesmos bytes da fixture `0060-parser-structural-stress`, construída pelo instrumento congelado do 0060A.

O experimento mede somente a melhora sintética e reproduzível. Os seis DOCX reais não foram acessados. A validação real continua pendente da trilha manual no Ubuntu e de autorização explícita.

## Ambiente e método

- macOS;
- Python 3.12.13;
- lxml 6.1.3;
- uma worktree temporária destacada em `c0604ca429232fb044d05ac7f0e0b20bc144d664` para a referência;
- três execuções de aquecimento e vinte execuções medidas por implementação;
- mesmo interpretador, ambiente virtual, arquivo DOCX e processo de medição;
- coleta de lixo desativada somente durante as vinte execuções medidas;
- estatística principal: mediana do tempo de `DocxParser.parse_bytes`.

## Resultado

| Implementação | Mínimo | Mediana | Máximo |
| --- | ---: | ---: | ---: |
| referência | 88,7 ms | 102,7 ms | 139,6 ms |
| 0060B | 31,0 ms | 35,3 ms | 52,6 ms |

A razão entre as medianas foi de **2,91×** em favor do 0060B. O oráculo do 0060A confirmou que a serialização canônica da IR da mesma fixture permaneceu byte-idêntica à referência congelada.

Este resultado não substitui o critério de aprovação nos dois documentos reais mais pesados. Ele demonstra que o índice remove o custo repetido na carga estrutural criada especificamente para esta fase.
