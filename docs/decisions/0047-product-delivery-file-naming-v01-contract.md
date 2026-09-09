# 0047 — Product Delivery / File Naming v0.1 — contrato

**Status:** ACEITO PARA IMPLEMENTAÇÃO — freeze após PR + CI + auditoria final.

## Objetivo

Transformar resultados já produzidos em uma coleção tipada de arquivos de entrega, inteiramente em memória, sem reprocessar DOCX e sem reabrir o ProductOutputBundle congelado.

Fronteira:

```text
ProductOutputBundle v0.1
+ base_name explícito do chamador
→ ProductDelivery v0.1
```

O renderer humano congelado é chamado internamente apenas como projeção do `bundle.processing_report`.

## API pública

```text
build_product_delivery(
    bundle: ProductOutputBundle,
    *,
    base_name: str,
) -> ProductDelivery
```

Não aceita path/diretório de saída. Não toca filesystem.

## Arquivos v0.1

Exatamente cinco arquivos, em ordem fixa:

```text
<base>_limpo.docx
<base>_revisao.docx
<base>_relatorio.json
<base>_relatorio.md
<base>_manifest.json
```

Roles fechados:

```text
clean_docx
review_docx
technical_report
human_report
manifest
```

## Modelo

```text
PRODUCT_DELIVERY_VERSION = "0.1"

DeliveryFile:
    role
    filename
    media_type
    content_bytes
    content_sha256
    size_bytes

ProductDelivery:
    product_delivery_version
    base_name
    product_output_bundle_ref
    human_report_ref
    files
```

`files` contém exatamente os cinco roles acima, na ordem congelada.

## Binding

`product_output_bundle_ref` é SHA-256 de uma serialização canônica mínima das identidades do Bundle, não do `repr()` Python e não de bytes concatenados ambiguamente.

Payload canônico v0.1:

```json
{
  "product_output_bundle_version": "0.1",
  "input_package_sha256": "...",
  "clean_package_sha256": "...",
  "review_package_sha256": "...",
  "processing_report_ref": "...",
  "profile_id": "...",
  "profile_version": "...",
  "session_status": "..."
}
```

Serialização: JSON UTF-8, `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, sem BOM, sem newline.

`human_report_ref` é o `content_sha256` do `RenderedProcessingReport` produzido do report tipado do Bundle.

Cada `DeliveryFile.content_sha256 == sha256(content_bytes)` e `size_bytes == len(content_bytes)`.

## Manifest v0.1

O manifest é JSON UTF-8 canônico e contém:

```text
product_delivery_version
base_name
product_output_bundle_ref
human_report_ref
files: [
  {role, filename, media_type, sha256, size_bytes}
  ... apenas os 4 arquivos de conteúdo, NÃO o próprio manifest
]
```

O manifest não se auto-inclui para evitar recursão de hash.

Após gerar o manifest, cria-se o quinto `DeliveryFile(role=manifest)` com SHA/tamanho próprios.

O manifest não contém timestamps, paths locais, hostname, username ou metadados de ambiente.

## Fonte dos bytes

Mapeamento exato:

```text
clean_docx.content_bytes      = bundle.clean_package_bytes
review_docx.content_bytes     = bundle.review_package_bytes
technical_report.content_bytes= bundle.processing_report_json_bytes
human_report.content_bytes    = render_processing_report(bundle.processing_report).content_bytes
manifest.content_bytes        = manifest canônico
```

Nenhum desses bytes é modificado.

## Media types

```text
clean_docx      application/vnd.openxmlformats-officedocument.wordprocessingml.document
review_docx     application/vnd.openxmlformats-officedocument.wordprocessingml.document
technical_report application/json; charset=utf-8
human_report    text/markdown; charset=utf-8
manifest        application/json; charset=utf-8
```

## `base_name`

`base_name` é metadata explícita do chamador. Nunca é inferida do conteúdo do DOCX, título, autor ou Profile.

### Validação/canonicalização v0.1

Entrada:
- deve ser `str` exato;
- 1 a 120 codepoints antes da canonicalização;
- não pode conter NUL;
- não pode ser apenas whitespace/pontos.

Canonicalização determinística:
1. remover whitespace Unicode nas extremidades com `strip()`;
2. cada `/`, `\\`, `:`, `*`, `?`, `"`, `<`, `>`, `|` e ASCII control U+0001–U+001F vira `_`;
3. qualquer sequência de whitespace interno vira um único espaço ASCII;
4. qualquer sequência de `_` gerada/adjacente vira um único `_`;
5. remover espaços e pontos finais;
6. rejeitar resultado vazio, `.` ou `..`;
7. rejeitar nomes reservados Windows, case-insensitive, antes de sufixos: `CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`;
8. limitar o base canônico a no máximo 100 codepoints para reservar espaço aos sufixos; se exceder, truncar deterministicamente nos primeiros 100 codepoints e novamente remover espaço/ponto final; se isso resultar inválido, ContractError.

Não realizar Unicode normalization/transliteration. A forma Unicode do usuário é preservada, exceto pelas regras acima.

O base canônico é retornado em `ProductDelivery.base_name`; o original não é persistido.

## Filename safety

Todos os filenames gerados:
- são nomes simples, nunca paths;
- não contêm `/` ou `\\`;
- não começam com `.`;
- não terminam com espaço ou ponto;
- têm extensão fixa por role;
- são distintos entre si;
- não excedem 140 codepoints.

Nenhum filename do chamador é usado diretamente além do `base_name` canonicalizado.

## Error model

```text
ProductDeliveryError
ProductDeliveryContractError
ProductDeliveryIntegrityError
```

ContractError:
- tipo de Bundle/base_name errado;
- base_name vazio/inválido/reservado.

IntegrityError:
- Bundle internamente incompatível apesar do modelo;
- renderer humano não vincula ao mesmo ProcessingReport;
- hash/tamanho de DeliveryFile divergente;
- role/ordem/filename/media-type divergente;
- manifest não corresponde aos quatro arquivos de conteúdo.

Programming errors inesperados não são mascarados.

## Atomicidade

Retorna um `ProductDelivery` completo ou erro. Nunca retorna coleção parcial.

## Imutabilidade

Não modifica Bundle, ProcessingReport ou bytes upstream.

## Determinismo

Mesmo Bundle + mesmo `base_name` canônico → mesmo ProductDelivery byte a byte.

Não usar:
- filesystem;
- clock/time/datetime;
- random/uuid;
- locale;
- network;
- LLM;
- ambiente do sistema.

## Sem ZIP na v0.1

ZIP está explicitamente fora do escopo. Motivo: não é necessário para fechar nomes/manifest e introduziria nova superfície de metadados/serialização de container já conhecida como sensível.

Uma futura camada de ZIP deve consumir `ProductDelivery`, não reprocessar os artefatos.

## Fora de escopo

- persistir arquivos;
- download HTTP;
- multipart;
- ZIP;
- escolher diretório;
- abrir Finder/Explorer;
- inferir base_name do DOCX;
- renomear segundo título/autor;
- alterar conteúdo dos quatro artefatos;
- assinar/criptografar manifest;
- UI.

## Testes mínimos

1. tipo de Bundle errado;
2. tipo de base_name errado;
3. base vazio/whitespace/pontos;
4. NUL;
5. separadores/path traversal;
6. caracteres Windows proibidos;
7. whitespace interno canonicalizado;
8. underscores colapsados;
9. trailing dot/space removidos;
10. nomes reservados Windows rejeitados case-insensitive;
11. Unicode preservado sem normalization;
12. truncamento determinístico 100 codepoints;
13. cinco roles/ordem exatos;
14. filenames esperados e distintos;
15. nenhuma barra/path nos filenames;
16. bytes clean idênticos ao Bundle;
17. bytes review idênticos;
18. JSON técnico idêntico;
19. Markdown humano idêntico ao renderer congelado;
20. SHA/tamanho de cada arquivo;
21. media types exatos;
22. bundle_ref canônico correto;
23. human_report_ref correto;
24. manifest contém somente quatro arquivos de conteúdo;
25. manifest hashes/tamanhos/names/roles fecham;
26. manifest não contém timestamp/path/environment;
27. manifest JSON determinístico;
28. inputs não mutados;
29. repetição byte-idêntica;
30. runtime sem IO/network/clock/random/locale/LLM;
31. nenhum import de Parser/Analysis/Classification/Decision/Patcher para reexecução;
32. E2E real a partir de `build_product_from_inputs` com no-change;
33. E2E real com alteração aplicada;
34. E2E com review/unapplied;
35. suíte completa regressiva verde.

## Critério de aceite

Congelar somente se:
- os quatro conteúdos forem byte-identical às fontes congeladas;
- o manifest fechar os hashes/tamanhos/nomes;
- filenames forem determinísticos e path-safe;
- nenhuma nova autoridade normativa existir;
- não houver filesystem/ZIP;
- suíte completa estiver verde.
