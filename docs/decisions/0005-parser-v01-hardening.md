# Decisão 0005 — Hardening do parser DOCX v0.1

Status: APROVADA

## Contexto

A implementação real do parser v0.1 foi auditada adversarialmente por Kimi K3 após execução dos testes. O parecer foi **APROVAR COM CORREÇÕES**. A arquitetura permaneceu válida; os achados ficaram concentrados em bordas de XML/ZIP e rastreabilidade.

## Correções incorporadas antes da v0.2

1. Comentários XML e processing instructions como filhos diretos de `w:body` são preservados como `non_element_node`, protegidos e sinalizados; não podem derrubar o parse.
2. Nomes de parts duplicados no ZIP são rejeitados com `duplicate_part_name`.
3. Cada bloco registra `inherited_xml_attrs` para `xml:space`, `xml:lang` e `xml:base` herdados.
4. `physical_hash` passa a ser calculado sobre `canonical_xml` + `inherited_xml_attrs`, serializados deterministicamente.
5. Exceções de leitura de ZIP foram estreitadas. `NotImplementedError` ao ler compressão não suportada vira `unsupported_compression`.
6. O ParseResult registra versões de parser, `lxml` e `libxml2` em `environment`.
7. OOXML Strict e outros namespaces WordprocessingML não suportados falham explicitamente com `unsupported_namespace`.
8. Erros fatais ficam em `errors[]`; `parse_warnings[]` permanece reservado a condições não fatais.
9. `raw_xml` foi renomeado para `canonical_xml`: não é cópia byte-exata do nó original.
10. O patcher futuro nunca poderá reconstruir o documento a partir de `canonical_xml`; deve operar sobre cópia do pacote original.

## Canonicalização

- Elementos XML: C14N 1.0 inclusivo, com comentários.
- Comentários/processing instructions isolados: serialização XML direta determinística (`etree.tostring(..., with_tail=False)`). Durante os testes, C14N sobre nós não-elemento isolados causou falha do libxml2; a exceção é deliberada e versionada.
- A identidade física do bloco é `SHA256(JSON_CANONICAL({canonical_xml, inherited_xml_attrs}))`.

## Structural path

Convenção v0.1:
- escopo sempre dentro de uma única part;
- raiz sem predicado;
- elementos: posição 1-based entre irmãos com a mesma tag;
- namespace `w` representado por `w:local`;
- namespaces estrangeiros por `{namespace}local`;
- comentários: `comment()[n]`;
- processing instructions: `processing-instruction()[n]`.

O futuro patcher deve usar a mesma convenção e as mesmas opções de parsing (PARSER-G7 / PATCHER-G1).

## Testes

Suíte ampliada local: **11/11 aprovados**.

Cobertura adicionada:
- comentários e PI em `w:body`;
- part duplicada;
- `xml:space` herdado alterando `physical_hash`;
- namespace OOXML Strict;
- body vazio;
- `document.xml` em encoding não UTF-8;
- separação de erros fatais e warnings;
- registro de ambiente;
- determinismo e independência do empacotamento ZIP mantidos.

## Próximo passo

Não iniciar v0.2 sem considerar esta v0.1 endurecida como baseline. A próxima fatia deve ser definida separadamente e submetida à revisão técnica antes de implementação.
