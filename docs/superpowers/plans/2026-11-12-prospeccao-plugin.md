# Plugin de prospecção fria · Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plugin desktop do Hermes que busca leads no Maps, classifica, cria e publica landing pages e prepara a comunicação aprovada pelo usuário.

**Architecture:** Plugin do tipo pacote com backend Python (`dashboard/plugin_api.py`, chamado via `ctx.rest`) e pane desktop em JS único (`desktop/plugin.js`). Leads em SQLite no diretório do plugin. Ferramentas existentes (gosom, Scrapling, Firecrawl, hermes-whatsapp, conector iCloud) são chamadas, não reimplementadas.

**Tech Stack:** Python 3 (stdlib + pytest), SQLite, JavaScript ESM sem build (`@hermes/plugin-sdk`, `react/jsx-runtime`), builder existente a definir na Task 0.

**Spec:** `docs/superpowers/specs/2026-11-12-prospeccao-design.md`

## Global Constraints

- Localização do plugin: `~/.hermes/plugins/prospeccao/` (plugin.yaml, dashboard/, desktop/).
- Nenhum código de scraping do Google Maps; a busca só chama gosom, Scrapling ou Firecrawl.
- Nenhum envio sem status `aprovado` gravado pelo usuário.
- Nenhum serviço pago novo; Google Places fora do escopo.
- Chaves de Vercel e Cloudflare só em `~/.hermes/.env`; nunca em UI, log ou resposta da API.
- Configuração via `hermes config set`; não editar `config.yaml` à mão.
- JS do pane: só imports de `@hermes/plugin-sdk`, `react` e `react/jsx-runtime`; sem JSX; sem cores fixas (usar variáveis de tema).
- Dados não medidos ficam `NULL`, nunca `0`.

## Review Focus

1. Busca com serviço fora do ar ou erro: a UI mostra erro; não mostra lista vazia como se não houvesse resultados.
2. Lead sem telefone ou e-mail: o canal fica indisponível; nenhuma mensagem vai para destino vazio.
3. Mesma busca repetida: atualiza por `place_id`, sem duplicar leads.
4. Publicação que falha no meio: status de erro; o lead não fica marcado como publicado.
5. Opt-out registrado: nenhum envio posterior ao mesmo lead, em nenhum canal.

Cada linha tem teste na task que é dona do código.

---

### Task 0: Verificação de ferramentas e escolha do builder

Gate: nenhuma task seguinte começa sem o resultado desta.

**Files:**
- Create: `docs/superpowers/notes/2026-11-12-discovery.md`

**Interfaces:**
- Produces: endpoint ou tool de cada fonte (gosom, Scrapling, Firecrawl); nome do tool de envio do hermes-whatsapp; nome do tool de e-mail do iCloud; builder escolhido; API de publicação de Vercel e Cloudflare Pages.

- [ ] **Step 1: Listar como cada fonte é chamada**

Run: `hermes mcp list` e `hermes config show` (ou `grep -n -i "gosom\|scrapling\|firecrawl" ~/.hermes/config.yaml`)
Expected: para cada fonte, ou um servidor MCP com URL, ou um comando/endpoint HTTP. Registrar no discovery.md.

- [ ] **Step 2: Testar uma chamada real de cada fonte**

Run: uma busca pequena (ex.: nicho "encanador", cidade "Vitória") pela ferramenta de cada fonte.
Expected: JSON com ao menos um negócio com nome. Se não houver resposta, registrar o erro e parar: a fonte não entra no v1 até ser resolvida.

- [ ] **Step 3: Escolher o builder**

Pesquisar (context7 ou docs oficiais) builders que aceitem templates, referências externas e design.md. Registrar 2 candidatos, a escolha e o motivo.
Expected: uma escolha registrada, com o comando de build que gera `index.html` em pasta.

- [ ] **Step 4: Confirmar APIs de publicação**

Consultar docs oficiais de Vercel (deployments) e Cloudflare Pages (direct upload). Registrar endpoint, método, autenticação e nome da variável de ambiente.

- [ ] **Step 5: Registrar nomes dos tools de envio**

Listar via `tool_search` ou config: tool do hermes-whatsapp e do conector iCloud `send_email`. Registrar nome e parâmetros.

- [ ] **Step 6: Commit**

```bash
cd "/Users/dan/01 - workspaces oficial/hermes-prospeccao" && git init && git add docs && git commit -m "docs: discovery de ferramentas e builder"
```

---

### Task 1: Scaffold do plugin e healthcheck

**Files:**
- Create: `~/.hermes/plugins/prospeccao/plugin.yaml`
- Create: `~/.hermes/plugins/prospeccao/dashboard/plugin_api.py`
- Create: `~/.hermes/plugins/prospeccao/desktop/plugin.js`
- Test: `tests/test_plugin_api.py` (no projeto)

**Interfaces:**
- Produces: `GET /health` → `{"ok": true}`; pane registrado com título "Prospecção" (área `panes`, placement `main`).

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_health_returns_ok():
    from dashboard.plugin_api import router  # ajustar ao padrão exato do plugin_api de exemplo
    client = TestClient(router)  # fastapi.testclient
    assert client.get("/health").json() == {"ok": True}
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_plugin_api.py -v`
Expected: FAIL (módulo não existe).

- [ ] **Step 3: Implementar `plugin_api.py` com `/health` e os arquivos de manifest e pane**

Usar `plugin.yaml` e `plugin_api.py` do exemplo da skill `hermes-agent` (references/plugin-load-troubleshooting.md). Pane: `ctx.register({ id: 'prospeccao', area: 'panes', data: { title: 'Prospecção', placement: 'main' }, render })` com texto fixo.

- [ ] **Step 4: Rodar teste**

Run: `pytest tests/test_plugin_api.py -v`
Expected: PASS.

- [ ] **Step 5: Verificar carregamento**

Run: `hermes plugins doctor`
Expected: `prospeccao` listado sem erro. No desktop: ⌘K → Reload desktop plugins; o pane aparece sem toast de erro.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: scaffold do plugin prospeccao"
```

---

### Task 2: Armazenamento de leads

**Files:**
- Create: `prospeccao/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Produces:
  - `init_db(path: str) -> None`
  - `upsert_leads(path: str, leads: list[dict]) -> int` (chave `place_id`; retorna o total gravado)
  - `list_leads(path: str, filters: dict) -> list[dict]`
  - `set_status(path: str, place_id: str, status: str) -> None`
  - `mark_optout(path: str, place_id: str) -> None`

Schema: `leads(place_id TEXT PRIMARY KEY, nome TEXT, nicho TEXT, cidade TEXT, nota REAL NULL, avaliacoes INTEGER NULL, site_url TEXT NULL, telefone TEXT NULL, email TEXT NULL, fonte TEXT, status TEXT DEFAULT 'novo', optout INTEGER DEFAULT 0, updated_at TEXT)`.

- [ ] **Step 1: Testes que falham**

```python
def test_upsert_nao_duplica(tmp_path):
    db = str(tmp_path / "l.db"); init_db(db)
    lead = {"place_id": "p1", "nome": "A", "nota": None}
    upsert_leads(db, [lead]); upsert_leads(db, [lead])
    assert len(list_leads(db, {})) == 1

def test_nao_medido_fica_null(tmp_path):
    db = str(tmp_path / "l.db"); init_db(db)
    upsert_leads(db, [{"place_id": "p1", "nome": "A", "nota": None}])
    assert list_leads(db, {})[0]["nota"] is None

def test_optout_marcado(tmp_path):
    db = str(tmp_path / "l.db"); init_db(db)
    upsert_leads(db, [{"place_id": "p1", "nome": "A"}])
    mark_optout(db, "p1")
    assert list_leads(db, {})[0]["optout"] == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_store.py -v`
Expected: FAIL (import).

- [ ] **Step 3: Implementar**

Usar `sqlite3` da stdlib. Upsert com `INSERT ... ON CONFLICT(place_id) DO UPDATE`, atualizando só campos não nulos do lead recebido. `updated_at` em ISO UTC.

- [ ] **Step 4: Rodar teste**

Run: `pytest tests/test_store.py -v`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add prospeccao/store.py tests/test_store.py && git commit -m "feat: armazenamento de leads em sqlite"
```

---

### Task 3: Adaptador de busca

**Files:**
- Create: `prospeccao/busca.py`
- Test: `tests/test_busca.py`

**Interfaces:**
- Consumes: endpoint/tool de cada fonte registrado na Task 0.
- Produces:
  - `class SourceError(Exception)`
  - `buscar(nicho: str, cidade: str, fonte: str) -> list[dict]` (cada dict com as chaves do schema da Task 2; `place_id` obrigatório)
  - Lança `SourceError` em erro de rede, HTTP não-2xx ou resposta sem lista.

- [ ] **Step 1: Testes que falham (com resposta simulada da fonte)**

```python
def test_mapeia_resposta_para_lead(monkeypatch):
    monkeypatch.setattr(busca, "_chamar_fonte", lambda *a: [{"place_id": "p1", "name": "Encanador X", "rating": 4.5}])
    leads = buscar("encanador", "Vitória", "gosom")
    assert leads[0]["place_id"] == "p1" and leads[0]["nome"] == "Encanador X" and leads[0]["nota"] == 4.5

def test_erro_nao_vira_lista_vazia(monkeypatch):
    def falha(*a): raise ConnectionError("offline")
    monkeypatch.setattr(busca, "_chamar_fonte", falha)
    with pytest.raises(SourceError):
        buscar("encanador", "Vitória", "gosom")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_busca.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar**

`_chamar_fonte` faz a chamada HTTP ou MCP definida na Task 0. `buscar` converte chaves da fonte para o schema e envolve qualquer exceção em `SourceError`. Campos ausentes viram `None`.

- [ ] **Step 4: Rodar teste**

Run: `pytest tests/test_busca.py -v`
Expected: PASS.

- [ ] **Step 5: Verificação real**

Run: `python -c "from prospeccao.busca import buscar; print(len(buscar('encanador','Vitória','<fonte>')))"`
Expected: número > 0 com a fonte ativa no Dokploy.

- [ ] **Step 6: Commit**

```bash
git add prospeccao/busca.py tests/test_busca.py && git commit -m "feat: adaptador de busca para fontes existentes"
```

---

### Task 4: Classificação e filtro

**Files:**
- Create: `prospeccao/filtro.py`
- Test: `tests/test_filtro.py`

**Interfaces:**
- Produces:
  - `classificar(lead: dict) -> dict` (acrescenta `tem_site: bool | None`; `None` quando não há como saber)
  - `filtrar(leads: list[dict], criterios: dict) -> list[dict]` com chaves opcionais `nota_min: float`, `avaliacoes_min: int`, `sem_site: bool`

- [ ] **Step 1: Testes que falham**

```python
def test_sem_site_e_none_quando_nao_sabe():
    assert classificar({"site_url": None, "verificado_site": False})["tem_site"] is None

def test_filtra_nota_minima_ignora_nulo():
    leads = [{"nota": 4.8}, {"nota": None}, {"nota": 3.0}]
    assert filtrar(leads, {"nota_min": 4.0}) == [{"nota": 4.8}]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_filtro.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar**

`tem_site` vira `True` se `site_url` existe, `False` se a verificação confirmou ausência, `None` caso contrário. Filtro exclui `None` quando o critério exige valor.

- [ ] **Step 4: Rodar teste**

Run: `pytest tests/test_filtro.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add prospeccao/filtro.py tests/test_filtro.py && git commit -m "feat: classificacao e filtro de leads"
```

---

### Task 5: Builder de landing

**Files:**
- Create: `prospeccao/site.py`
- Test: `tests/test_site.py`

**Interfaces:**
- Consumes: builder escolhido na Task 0.
- Produces: `gerar_site(lead: dict, template: str, design_md: Path, refs: list[str], saida: Path) -> Path` (retorna a pasta gerada, com `index.html`).

- [ ] **Step 1: Testes que falham**

```python
def test_gera_index_com_nome_do_lead(tmp_path):
    design = tmp_path / "design.md"; design.write_text("# cor: #0a0")
    out = gerar_site({"nome": "Encanador X"}, "basico", design, [], tmp_path / "out")
    assert "Encanador X" in (out / "index.html").read_text()

def test_design_md_ausente_falha(tmp_path):
    with pytest.raises(FileNotFoundError):
        gerar_site({"nome": "X"}, "basico", tmp_path / "nao.md", [], tmp_path / "out")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_site.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar**

Chama o builder da Task 0 com template, design.md e referências; copia a saída para `saida`. Não gera HTML próprio.

- [ ] **Step 4: Rodar teste**

Run: `pytest tests/test_site.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add prospeccao/site.py tests/test_site.py && git commit -m "feat: builder de landing com templates e design.md"
```

---

### Task 6: Publicação

**Files:**
- Create: `prospeccao/publicar.py`
- Test: `tests/test_publicar.py`

**Interfaces:**
- Consumes: endpoints da Task 0; chaves `VERCEL_TOKEN` e `CLOUDFLARE_API_TOKEN` lidas de `~/.hermes/.env`.
- Produces: `publicar(pasta: Path, provedor: str, projeto: str) -> str` (URL pública). Levanta `PublishError` em falha e em `provedor` desconhecido.

- [ ] **Step 1: Testes que falham**

```python
def test_sucesso_retorna_url(monkeypatch, tmp_path):
    monkeypatch.setattr(publicar, "_enviar", lambda *a: {"url": "https://x.vercel.app"})
    assert publicar(tmp_path, "vercel", "x") == "https://x.vercel.app"

def test_falha_levanta_erro(monkeypatch, tmp_path):
    def falha(*a): raise publicar.PublishError("500")
    monkeypatch.setattr(publicar, "_enviar", falha)
    with pytest.raises(publicar.PublishError):
        publicar(tmp_path, "cloudflare", "x")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_publicar.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar**

`_enviar` faz upload conforme a API da Task 0. Sem token: `PublishError("token ausente")`, sem mostrar valor. Quem chama grava `status='erro'` se levantar exceção.

- [ ] **Step 4: Rodar teste**

Run: `pytest tests/test_publicar.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add prospeccao/publicar.py tests/test_publicar.py && git commit -m "feat: publicacao na vercel e cloudflare pages"
```

---

### Task 7: Comunicação

**Files:**
- Create: `prospeccao/comunicacao.py`
- Test: `tests/test_comunicacao.py`

**Interfaces:**
- Consumes: tools de envio da Task 0; `list_leads`, `set_status`, `mark_optout` da Task 2.
- Produces:
  - `rascunhar(lead: dict, url_landing: str) -> dict` → `{"email": {"assunto": str, "corpo": str}, "whatsapp": {"texto": str}}`
  - `enviar(path: str, place_id: str, canal: str, aprovado_por: str) -> None` (`canal` ∈ `{"whatsapp", "email"}`)

Levanta `PermissionError` se o lead não estiver `aprovado`, se `optout=1`, ou se o canal exigido não tiver destino (telefone ou e-mail).

- [ ] **Step 1: Testes que falham**

```python
def test_envio_sem_aprovacao_bloqueado(tmp_path):
    db = str(tmp_path/"l.db"); init_db(db)
    upsert_leads(db, [{"place_id":"p1","telefone":"+5527999999999"}])
    with pytest.raises(PermissionError):
        enviar(db, "p1", "whatsapp", "dan")

def test_optout_bloqueia_todos_os_canais(tmp_path):
    db = str(tmp_path/"l.db"); init_db(db)
    upsert_leads(db, [{"place_id":"p1","telefone":"+5527999999999","email":"a@b.com"}])
    set_status(db, "p1", "aprovado"); mark_optout(db, "p1")
    with pytest.raises(PermissionError):
        enviar(db, "p1", "email", "dan")

def test_sem_telefone_nao_envia_whatsapp(tmp_path):
    db = str(tmp_path/"l.db"); init_db(db)
    upsert_leads(db, [{"place_id":"p1"}]); set_status(db, "p1", "aprovado")
    with pytest.raises(PermissionError):
        enviar(db, "p1", "whatsapp", "dan")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_comunicacao.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar**

Checagens nesta ordem: optout, aprovado, destino do canal. Depois chama o tool de envio da Task 0 e grava status `enviado`. Falha de envio grava `erro`, não `enviado`.

- [ ] **Step 4: Rodar teste**

Run: `pytest tests/test_comunicacao.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add prospeccao/comunicacao.py tests/test_comunicacao.py && git commit -m "feat: rascunho e envio aprovado de comunicacao"
```

---

### Task 8: Pane desktop

**Files:**
- Modify: `~/.hermes/plugins/prospeccao/desktop/plugin.js`

**Interfaces:**
- Consumes: rotas do `plugin_api.py` (`GET /leads`, `POST /busca`, `POST /site`, `POST /publicar`, `POST /rascunho`, `POST /enviar`, `POST /optout`) via `ctx.rest`.
- Produces: pane com lista filtrável, botões Buscar, Gerar site, Publicar, Gerar mensagens, Aprovar e Enviar, e exibição de erro vindo do backend.

As rotas do backend (Tasks 2–7) são adicionadas em `plugin_api.py` nesta task, uma por função, com cada uma chamando o módulo correspondente.

- [ ] **Step 1: Verificar sintaxe**

Run: `node --check ~/.hermes/plugins/prospeccao/desktop/plugin.js`
Expected: sem saída (sintaxe OK).

- [ ] **Step 2: Verificar no app**

Run: ⌘K → Reload desktop plugins. Abrir o pane.
Expected: pane "Prospecção" carrega; lista vazia mostra estado vazio; nenhum toast de erro de plugin.

- [ ] **Step 3: Verificar fluxo de erro**

Parar a fonte de busca (ou usar nicho inválido). Clicar Buscar.
Expected: mensagem de erro no pane. Lista não mostra "nenhum resultado".

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: pane desktop de prospeccao"
```

---

## Verificação final

- [ ] `pytest -v` passa em todos os módulos.
- [ ] `hermes plugins doctor` lista `prospeccao` sem erro.
- [ ] Fluxo real com um lead de teste: buscar, filtrar, gerar site, publicar em ambiente de teste, rascunhar, aprovar, enviar para número próprio. Cada passo com saída real registrada.
- [ ] Revisar os 5 itens de Review Focus contra os testes que os cobrem.

## Fora do v1

- Webhook de saída HMAC para CRM.
- Expiração automática de preview.
