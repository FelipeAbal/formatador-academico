# Decisão 0009 — Hardening do parser v0.3 após revisão adversarial

## Contexto

A implementação real da v0.3 foi revisada adversarialmente pelo Kimi K3. O veredito foi **NÃO CONGELAR v0.3** antes das correções, com um bloqueante central e problemas de portabilidade/observabilidade.

O bloqueante demonstrado era incompatível com a própria semântica aprovada da v0.3: duas parts distintas relacionadas como o mesmo tipo de story podiam produzir colisão de `story_id` e derrubar o documento inteiro, apesar de o body estar íntegro.

Felipe estabeleceu também a regra operacional de que tudo o que puder ser corrigido com segurança dentro do escopo atual deve ser corrigido antes de avançar.

## Correções incorporadas

1. **Identidade de story baseada na part**
   - Toda story secundária usa `story_id = "{story_type}:{part}"`.
   - `part` passa a ser âncora física obrigatória da identidade global, junto com `structural_path`, `original_index` e `physical_hash`.
   - Duas parts do mesmo tipo não causam falha fatal.

2. **Duplicidade de tipo de story**
   - Duas parts distintas relacionadas como o mesmo `story_type` são ambas preservadas.
   - O parser emite `duplicate_story_type`.
   - A duplicidade da mesma part continua impedida por inventário/`seen_parts`.

3. **Parse parcial preservado**
   - Defeito de story secundária continua limitado à story.
   - `status = partial` permanece válido quando alguma story está `missing`, `failed` ou `rejected`.
   - `partial_stories[]` lista diretamente os `story_id` não-ok.

4. **Testes legados portáveis**
   - O teste cross-processo da v0.2 deixa de usar path absoluto de ambiente temporário e deriva `src` de `Path(__file__)`.
   - O contrato v0.2 não exige que a versão corrente do parser permaneça literalmente `0.2.0`; o teste passa a verificar compatibilidade mínima de contrato.

5. **Detecção de texto em caixas/formas opacas ampliada**
   - Continua detectando `w:txbxContent`.
   - Passa também a detectar `a:txBody` (DrawingML) e `p:txBody` (PresentationML).
   - O conteúdo continua opaco/protegido; decomposição fica fora da v0.3.

6. **IDs de notes/comments observáveis**
   - `duplicate_note_id`
   - `missing_note_id`
   - `duplicate_comment_id`
   - `missing_comment_id`
   - IDs continuam crus; o parser não tenta corrigi-los ou interpretar unicidade normativa.

7. **Autoridade de erros**
   - `errors[]` no topo é a lista autoritativa para erros do resultado de parse.
   - `story.errors[]` é espelho local de conveniência para a story correspondente.
   - Consumidores não devem modificar uma lista independentemente da outra; ambas são imutáveis após o parse.

8. **Schema de stories uniformizado**
   - Stories expõem consistentemente `blocks`, `items` e `opaque_items`, usando `None` quando o campo não se aplica.
   - Isso vale também para stories `failed`, `missing` e `rejected`.

9. **Targets suspeitos**
   - Target de story que, após resolução, escapa da raiz lógica do pacote gera warning `suspicious_target`.
   - A story é registrada como `status = rejected`, com erro `suspicious_target`, em vez de ser confundida com uma part meramente ausente.
   - O documento fica `partial`, o body permanece utilizável e nenhuma leitura fora do pacote é tentada.
   - Part genuinamente ausente continua `status = missing` + `missing_related_part`.

10. **Naming de stories órfãs uniformizado**
    - Stories órfãs usam o mesmo esquema `{story_type}:{part}` das stories relacionadas.

11. **Warning codes como contrato versionado**
    - A generalização da v0.3 substituiu o antigo `unsupported_body_child` pelo código genérico `unsupported_story_child` no dispatch compartilhado.
    - Mudanças futuras em warning codes devem ser registradas como mudança de contrato, não feitas silenciosamente.

12. **Limites ZIP continuam globais por decisão**
    - Limites de quantidade de parts, tamanho, expansão e razão de compressão são aplicados antes da decomposição das stories.
    - Violação desses limites continua sendo falha fatal do pacote inteiro, mesmo que a part ofensora seja uma story secundária.
    - Isso é política de segurança do pacote, não falha de contenção de story.

## Safety Gate e patcher

- Story `failed`, `missing` ou `rejected` é região absolutamente não editável.
- Um documento `partial` pode futuramente permitir operações apenas em stories `ok`, desde que o Safety Gate valide também `part + structural_path + physical_hash` e não exista dependência estrutural com a story indisponível.
- O patcher deve endereçar fisicamente `part + structural_path`; `story_id` é identificador lógico estável, não substituto da part.

## Testes

Após o hardening inicial:

- suíte específica da v0.3: **26 testes**;
- suíte v0.2: **18 testes**;
- suíte v0.1: **11 testes**;
- suíte completa validada externamente: **55/55 aprovados**.

Após a verificação final do Kimi K3, a única aresta restante (`suspicious_target` aparecendo como `missing`) foi corrigida e recebeu teste dedicado em `tests/test_docx_parser_v03_edges.py`. A suíte passa, portanto, a conter **56 testes** e deve ser reexecutada antes do congelamento formal final.

A cobertura inclui, entre outros:
- duas parts do mesmo story type sem falha global;
- ids de note/comment duplicados e ausentes;
- `a:txBody`/`p:txBody`;
- `partial_stories`;
- schema consistente de story;
- determinismo cross-processo sem path absoluto de máquina;
- target que escapa da raiz do pacote tratado como story `rejected`.

## Regra operacional do projeto

Quando uma auditoria encontrar um problema que:
1. seja corrigível agora;
2. permaneça dentro do escopo da etapa atual; e
3. não exija reabrir uma decisão arquitetural já congelada,

**a correção deve ser feita antes de avançar.**

Só se posterga algo por expansão explícita de escopo, dependência ainda não resolvida, impossibilidade técnica demonstrada ou nova decisão que exija auditoria própria.

## Estado

A v0.3 recebeu também o último ajuste menor apontado na verificação externa. Falta somente executar a suíte completa de **56 testes** no `main` atualizado e confirmar especificamente o novo estado `rejected` para `suspicious_target`.

Se verde, a v0.3 deve ser congelada formalmente e a próxima etapa proposta é v0.4: decomposição física segura de tabelas.
