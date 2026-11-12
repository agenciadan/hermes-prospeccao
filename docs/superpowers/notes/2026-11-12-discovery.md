# Discovery de ferramentas e builder (Task 0) · 2026-11-12

Status: **BLOCKED**. Discovery feito; nenhuma fonte de busca respondeu. Relatório completo fora do repo: `.superpowers/sdd/2026-11-12-prospeccao-plugin/task-0-report.md`.

## Fontes de busca

- **gosom:** não instalado (sem MCP, sem comando, sem arquivo). Não testado.
- **Scrapling:** skill opcional existe; pacote `scrapling` não instalado; sem servidor MCP configurado. Não testado.
- **Firecrawl:** AGUARDA AUTORIZAÇÃO DO DAN (pago por uso). Não chamado. `web_search`/`web_extract` do Hermes usam Firecrawl no `config.yaml` (`search_backend`, `extract_backend`).

## Builder

- Escolhido: **Eleventy** (`npx @11ty/eleventy` gera `_site/index.html`, doc https://www.11ty.dev/docs/).
- Alternativa: Astro (`astro build` gera `dist/`).
- `DESIGN.md` não é lido nativamente; precisa de export (`npx @google/design.md export --format css-tailwind`), CLI ainda não instalado.

## APIs de publicação

- **Vercel:** `POST https://api.vercel.com/v13/deployments`, `Authorization: Bearer <token>`. Upload de arquivos: endpoint NÃO VERIFICADO. Nome da env var: NÃO VERIFICADO.
- **Cloudflare Pages:** `POST https://api.cloudflare.com/client/v4/accounts/{account_id}/pages/projects/{project_name}/deployments` (multipart, manifest). Auth: Bearer com permissão "Pages Write". Env var: `CLOUDFLARE_API_TOKEN`. Env var do account ID: NÃO VERIFICADO.

## Envio

- **WhatsApp:** não há tool de envio para o agente (`send_message` não é model tool, `tools/send_message_tool.py:28`). Alternativa: CLI `hermes send -t whatsapp:<chat>`. Funcionamento sem gateway: NÃO VERIFICADO.
- **E-mail:** `mcp__icloud__send_email` (`to`, `subject`, `body`; opcionais `cc`, `bcc`, `isHtml`). Envia na hora, sem rascunho: gate de aprovação obrigatório antes.

## Pendências

1. Gate: gosom e Scrapling sem resposta; Firecrawl aguarda autorização.
2. Spec/plano: substituir "tool do hermes-whatsapp" pelo mecanismo real.
3. Criar no `.env` as variáveis de Vercel e Cloudflare.
4. Mover `DOKPLOY_API_KEY` de `config.yaml` para `.env` e rotacionar a chave.
