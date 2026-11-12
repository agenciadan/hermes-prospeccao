# Plugin de prospecção fria · Design (v1)

**Status:** aprovado pelo Dan em 2026-11-12.

## Intenção

Plugin completo para o Hermes Desktop que cobre a prospecção fria de sites: buscar negócios no Google Maps, classificar e filtrar, criar e editar landing pages, publicar e preparar a comunicação com o lead. O plugin não implementa scraping nem serviços novos: chama ferramentas que o usuário já tem e mostra os dados.

## Objetivos

- Pane desktop com lista de leads, filtros, ordenação e status.
- Criação de landing a partir de templates, referências externas e design.md, usando um builder existente que suporte esse formato.
- Publicação na Vercel ou na Cloudflare Pages, escolhida por site.
- Geração de rascunhos de e-mail e WhatsApp por lead, com envio pelos canais já conectados ao Hermes.

## Não-objetivos (v1)

- Código próprio de scraping do Google Maps.
- Integração com CRM. Fica para webhook futuro.
- Envio automático. Nenhuma mensagem sai sem aprovação do usuário.
- Google Places API e outros serviços pagos novos.

## Pipeline

Busca (gosom, Scrapling, Firecrawl) → Classifica e filtra → Landing page → Publica.

## Componentes

- **Pane desktop:** plugin JS único, sem build.
- **Backend Python:** `dashboard/plugin_api.py`, chamado via `ctx.rest`. Guarda leads, executa busca, classificação, build, publicação e envio.
- **Armazenamento:** SQLite no diretório do plugin. Chave: `place_id`. Rodar a mesma busca atualiza, não duplica.
- **Sites gerados:** uma pasta por lead.

## Comunicação

configuração dentro do painel; envio pendente de transporte confirmado.

## Webhook (futuro)

URL cadastrada recebe o JSON do lead, assinado com HMAC-SHA256. O segredo fica no `.env`.

## Decisões assumidas (podem ser trocadas)

- SQLite no diretório do plugin.
- Um builder escolhido na implementação, entre os que suportam templates e design.md.
- Publicação com adaptador para Vercel e Cloudflare Pages.

## Pendências de verificação (não verificadas)

- Como o plugin chama gosom, Scrapling e Firecrawl (MCP ou HTTP) e os endpoints do Dokploy.
- Builder que atende templates, referências externas e design.md.
- APIs atuais de Vercel e Cloudflare Pages.
- Nome exato dos tools de envio do hermes-whatsapp e do conector iCloud.
