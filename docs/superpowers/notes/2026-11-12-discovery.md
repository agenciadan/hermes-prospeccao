# Discovery com escopo Dokploy (Task 0) · 2026-11-12

Status: **DONE_WITH_CONCERNS**. Gate de busca passou: gosom devolveu negócios reais. Relatório completo fora do repo: `.superpowers/sdd/2026-11-12-prospeccao-plugin/task-0-report-2.md`.

## Fontes de busca

- **gosom** (`https://maps.adxpro.com.br`, sem token). Verificado: spec em `/static/spec/spec.yaml`.
  - `POST /api/v1/jobs` → 201 `{"id"}`. Exige `lat` e `lon` (422 sem eles).
  - `GET /api/v1/jobs/{id}` → `Status` "ok" quando pronto.
  - `GET /api/v1/jobs/{id}/download` → CSV (36 colunas, incluindo `place_id`).
  - Teste "encanador em Vitória": 16 negócios. `place_id` vazio na linha de exemplo; cobertura não verificada.
  - Risco: POST/DELETE sem autenticação.
- **Scrapling** (`https://scrap.adxpro.com.br/mcp`, Bearer `MCP_SCRAPLING_API_KEY`). Verificado: 16 tools (`make_request`, `browser_fetch_once`, `browser_fetch`, `browser_extract`, sessões, rede, screenshot). É um fetcher genérico, não fonte de busca de negócios.
- **Firecrawl:** fora do v1 (decisão do controlador). Não chamado.

## Envio

- **WhatsApp:** `hermes send --to whatsapp:<chat>` existe, mas `hermes send --list whatsapp` → "Configured: (none)". Canal indisponível até configurar. Funcionamento sem gateway: NÃO VERIFICADO.
- **E-mail:** `himalaya` NÃO instalado (SMTP NÃO VERIFICADO). Caminho: `mcp__icloud__send_email` (envia na hora; gate obrigatório).

## Builder

- Eleventy (`npx @11ty/eleventy`, saída `_site/index.html`). Alternativa: Astro (`dist/`).
- `DESIGN.md`: `@google/design.md` 0.4.0 exporta `css-tailwind` (CSS `@theme` Tailwind v4), `dtcg` (W3C tokens) e `json-tailwind` (Tailwind v3). CSS puro não existe. Não instalado.

## APIs de publicação

- **Vercel:** `POST https://api.vercel.com/v2/files` (upload, Bearer, `x-vercel-digest` SHA1) → `POST https://api.vercel.com/v13/deployments` (`files` com `sha`/`size` ou inline). Env var: `VERCEL_TOKEN`. Formato do corpo do upload: NÃO VERIFICADO.
- **Cloudflare Pages:** `POST https://api.cloudflare.com/client/v4/accounts/{account_id}/pages/projects/{project_name}/deployments` (multipart, `manifest`, Bearer com "Pages Write"). Env var: `CLOUDFLARE_API_TOKEN`. Env var do account ID: NÃO VERIFICADO.

## Pendências

1. Ajustar spec/plano Task 3 ao fluxo gosom de 3 passos, com lat/lon; definir geocodificação cidade→coordenadas.
2. Confirmar cobertura de `place_id` (ou fallback `data_id`/`cid`).
3. Decidir configuração do WhatsApp.
4. Decidir proteção da API gosom antes de produção.
5. Criar `VERCEL_TOKEN`, `CLOUDFLARE_API_TOKEN` e account ID no `.env`.
