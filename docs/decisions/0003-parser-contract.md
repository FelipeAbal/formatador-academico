# Decisão 0003 — Contrato mínimo do parser DOCX

## Status

**APROVADA**

## Objetivo

Definir um parser DOCX estritamente físico/forense, responsável por observar e registrar o pacote original sem classificar conteúdo acadêmico, normalizar runs de forma destrutiva ou decidir transformações.

## Princípio

O parser recebe o `OriginalPackage` imutável e produz um `ParseResult`/`PhysicalIR` serializável, determinístico e rastreável.

O parser não:
- decide se algo é título, citação ou referência;
- decide se algo está correto/incorreto;
- aplica regra de perfil;
- modifica o DOCX;
- resolve estilos herdados ou numbering visível;
- normaliza destrutivamente runs.

## Saída mínima

`ParseResult` contém:
- `package_metadata` e `package_hash`;
- `stories`;
- `blocks`;
- `styles_raw`;
- `numbering_raw`;
- `relationships_raw`;
- `protected_regions`;
- `parse_warnings`.

## Stories obrigatórias

O parser deve procurar ao menos:
- `body`;
- `footnotes`;
- `endnotes`;
- `comments`;
- `headers[]` por seção/tipo;
- `footers[]` por seção/tipo;
- `textboxes[]` aninhadas em qualquer story.

Story encontrada mas não mapeável gera `unsupported_story`.

Regra: tudo que existe entra na IR ou vira warning explícito.

## Blocos e objetos opacos

Cada bloco mantém identidade composta e provenance físico.

Objetos não representáveis com segurança usam:
- `source_type = opaque_object`;
- XML bruto ou referência exata ao nó;
- warning correspondente;
- proteção automática contra edição.

Nenhum objeto desconhecido desaparece silenciosamente.

## Coordenadas e offsets

Offsets dentro de um bloco são medidos em caracteres Unicode sobre `text_raw`.

Regiões que cruzam runs ou blocos usam âncoras compostas:
- `start = (block_id, offset_in_block)`;
- `end = (block_id, offset_in_block)`.

## Styles, numbering e relationships

Leitura bruta é obrigatória.

O parser preserva:
- referências de estilo e árvore bruta de `styles.xml`;
- `numId`, `ilvl` e conteúdo bruto de `numbering.xml`;
- relationships e seus identificadores, inclusive hyperlinks.

Resolução de herança de estilos, defaults, numbering visível e valores efetivos pertence à camada derivada `Analysis View`, não ao parser.

## Formatação física

No parser, `null` significa estritamente **propriedade não especificada no XML**.

Nunca significa default calculado.

Valores derivados de estilo/herança/default não entram na camada física como se fossem valores diretos.

## Runs

O parser preserva apenas `runs_raw`, exatamente como aparecem no DOCX.

`runs_normalized` pertence à camada posterior de análise e deve manter mapeamento de offsets para os runs originais.

Normalização destrutiva no parse é proibida.

## Protected regions

Tracked changes, comments ancorados e outras regiões protegidas previamente definidas são detectadas e registradas, sem interpretação editorial.

O parser apenas identifica localização/tipo. A política de bloqueio já definida permanece aplicada downstream.

## Content hash

O `content_hash` de bloco é calculado sobre uma representação canônica de:
- `text_raw`;
- `source_type`;
- propriedades físicas diretamente presentes no bloco/run.

Não entram no hash valores efetivos derivados de herança de estilo ou defaults calculados.

A serialização canônica usada pelo hash deve ser definida e versionada no schema/implementação para garantir estabilidade.

## Garantias formais

### PARSER-G1
Nunca modifica o pacote original.

### PARSER-G2
Nenhuma estrutura conhecida ou desconhecida desaparece silenciosamente. Estrutura conhecida é tipada; desconhecida vira `opaque_object` + warning.

### PARSER-G3
Não classifica semanticamente conteúdo acadêmico.

### PARSER-G4
Todo dado extraído é rastreável à sua origem física no XML/pacote.

### PARSER-G5
Conteúdo não representável vira `opaque_object` + warning + proteção automática.

### PARSER-G6
O `ParseResult` é totalmente serializável e determinístico: mesmo DOCX + mesma versão do parser deve produzir representação serializada idêntica.

Objetos vivos de `python-docx`, `lxml` ou outra biblioteca não entram na IR.

## Separação de camadas

Fluxo aprovado:

`OriginalPackage -> DOCX Parser -> PhysicalIR -> Normalizer/Analysis View -> classificação/decisão`

O parser é a única camada de leitura física do pacote original. Bibliotecas são detalhes substituíveis atrás de adaptadores.

## Auditoria

Contrato auditado pelo Kimi K3.

Parecer: **APROVAR COM AJUSTES**.

Ajustes A1–A6 e a garantia adicional de determinismo foram incorporados e aprovados por Felipe.

## Próximo passo

Comparar estratégias de leitura do DOCX exclusivamente por cobertura, fidelidade e capacidade de cumprir este contrato:
- XML direto;
- `python-docx` + XML/lxml;
- arquitetura híbrida.
