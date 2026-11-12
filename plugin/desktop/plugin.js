// Prospecção: pane do Hermes Desktop com abas Leads e Configuração.
// Carregado sem build, então sem JSX: a UI é montada com jsxs() do runtime.
import { Button, Input, Textarea, useQuery, useQueryClient } from '@hermes/plugin-sdk';
import { useState } from 'react';
import { jsxs } from 'react/jsx-runtime';

const TITULO = 'Prospecção';
const STATUS = ['novo', 'rascunho', 'aprovado', 'enviado', 'respondeu', 'erro'];
// Não é status no backend: é o flag optout, então o filtro roda no cliente.
const OPTOUT = 'opt-out';
const AVISO_ENVIO = 'Envio de mensagens ainda não está ativo: o plugin só gera rascunhos.';
const CAMPOS_CONFIG = ['canal_padrao', 'remetente_email', 'assunto_padrao', 'modelo_mensagem', 'publicar_provedor_padrao'];
const SELECT = 'h-7 rounded-md border border-(--ui-stroke-secondary) bg-transparent px-2 text-sm';

// Filhos variádicos, como createElement.
const h = (tipo, props, ...filhos) => jsxs(tipo, { ...props, children: filhos.flat() });
const num = (texto) => (texto.trim() === '' ? null : Number(texto)); // campo vazio vira null, nunca 0
const erroDe = (e) => e?.message || String(e);
const sitio = (t) => (t === true ? 'sim' : t === false ? 'não' : 'não medido'); // None = não medido
const aviso = (m) => m && h('div', null, m.ok ? m.texto : `Erro: ${m.texto}`);
const campo = (rotulo, controle) =>
  h('label', { className: 'flex flex-col gap-1' }, h('span', { className: 'text-xs text-(--ui-text-tertiary)' }, rotulo), controle);
const opcoesConfig = (ctx) => ({ queryKey: ['prospeccao', 'config'], queryFn: () => ctx.rest('/config'), retry: false });

function LeadsTab({ ctx }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState('');
  const [msg, setMsg] = useState(null);
  const [pend, setPend] = useState(null); // primeiro clique arma ('acao:place_id' ou 'busca'), segundo executa
  const [urls, setUrls] = useState({});
  const [rascunhos, setRascunhos] = useState({});
  const [busca, setBusca] = useState({ nicho: '', cidade: '', lat: '', lon: '' });
  const provedor = useQuery(opcoesConfig(ctx)).data?.publicar_provedor_padrao;
  const leads = useQuery({
    queryKey: ['prospeccao', 'leads', status],
    queryFn: () => ctx.rest(status && status !== OPTOUT ? `/leads?status=${status}` : '/leads'),
    retry: false,
  });
  const lista = (leads.data ?? []).filter((l) => status !== OPTOUT || l.optout);

  // Erro do backend vira mensagem no pane; sucesso invalida o cache de prospecção.
  async function rodar(fn, ok) {
    setPend(null);
    try {
      const r = await fn();
      setMsg({ ok: true, texto: ok(r) });
      qc.invalidateQueries({ queryKey: ['prospeccao'] });
      return r;
    } catch (e) {
      setMsg({ ok: false, texto: erroDe(e) });
    }
  }

  const dois = (chave, rotulo, confirmaRotulo, fn, ok) => {
    const armado = pend === chave;
    return h(
      Button,
      { size: 'xs', variant: armado ? 'default' : 'outline', onClick: () => (armado ? rodar(fn, ok) : setPend(chave)) },
      armado ? confirmaRotulo : rotulo,
    );
  };

  function linha(lead) {
    const id = lead.place_id;
    const publicando = pend === `publicar:${id}`;
    return h(
      'li',
      { className: 'flex flex-col gap-1 border-b border-(--ui-stroke-secondary) py-2' },
      h('div', { className: 'font-medium' }, lead.nome || '(sem nome)'),
      h(
        'div',
        { className: 'text-xs text-(--ui-text-tertiary)' },
        `nota ${lead.nota ?? '—'} · ${lead.avaliacoes ?? '—'} avaliações · site: ${sitio(lead.tem_site)} · ${lead.status}${lead.optout ? ' · opt-out' : ''}`,
      ),
      h(
        'div',
        { className: 'flex flex-wrap gap-1' },
        dois(`site:${id}`, 'Gerar site', 'Confirmar geração', () => ctx.rest('/site', { method: 'POST', body: { place_id: id, confirmar: true } }), (r) => `Site gerado: ${r.pasta}`),
        dois(
          `publicar:${id}`,
          'Publicar',
          'Confirmar publicação',
          () => ctx.rest('/publicar', { method: 'POST', body: { place_id: id, provedor, confirmar: true } }),
          (r) => {
            setUrls((u) => ({ ...u, [id]: r.url }));
            return `Publicado: ${r.url}`;
          },
        ),
        h(
          Button,
          {
            size: 'xs',
            variant: 'outline',
            onClick: () =>
              rodar(
                () => ctx.rest('/rascunho', { method: 'POST', body: { place_id: id, url: urls[id] } }),
                (r) => {
                  setRascunhos((x) => ({ ...x, [id]: r }));
                  return 'Rascunho gerado. Nada foi enviado.';
                },
              ),
          },
          'Rascunho',
        ),
        h(
          Button,
          { size: 'xs', variant: 'outline', onClick: () => rodar(() => ctx.rest('/optout', { method: 'POST', body: { place_id: id } }), () => 'Opt-out registrado.') },
          'Opt-out',
        ),
      ),
      publicando &&
        h('div', { className: 'text-xs' }, `Publicação externa: o site deste lead fica público em ${provedor ?? 'provedor não definido'}.`),
      rascunhos[id] &&
        h(
          'pre',
          { className: 'whitespace-pre-wrap text-xs text-(--ui-text-secondary)' },
          `Assunto: ${rascunhos[id].email.assunto}\n\n${rascunhos[id].email.corpo}\n\nWhatsApp:\n${rascunhos[id].whatsapp.texto}`,
        ),
    );
  }

  const campoBusca = (chave, rotulo) =>
    campo(rotulo, h(Input, { value: busca[chave], onChange: (e) => setBusca((b) => ({ ...b, [chave]: e.target.value })) }));
  const armadoBusca = pend === 'busca';

  let conteudo;
  if (leads.isLoading) conteudo = 'Carregando leads…';
  else if (leads.error) conteudo = `Erro: ${erroDe(leads.error)}`;
  else if (lista.length === 0) conteudo = 'Nenhum lead encontrado.';
  else conteudo = h('ul', { className: 'flex flex-col' }, lista.map(linha));

  return h(
    'div',
    { className: 'flex min-h-0 flex-1 flex-col gap-3 overflow-auto' },
    h(
      'div',
      { className: 'flex flex-col gap-2 rounded-md border border-(--ui-stroke-secondary) p-2' },
      h('div', { className: 'font-medium' }, 'Buscar leads'),
      h('div', { className: 'grid grid-cols-2 gap-2' }, campoBusca('nicho', 'Nicho'), campoBusca('cidade', 'Cidade'), campoBusca('lat', 'Latitude'), campoBusca('lon', 'Longitude')),
      h(
        'div',
        { className: 'flex flex-wrap items-center gap-2' },
        h(
          Button,
          {
            size: 'xs',
            variant: armadoBusca ? 'default' : 'outline',
            onClick: () =>
              armadoBusca
                ? rodar(
                    () => ctx.rest('/busca', { method: 'POST', body: { nicho: busca.nicho, cidade: busca.cidade, lat: num(busca.lat), lon: num(busca.lon), confirmar: true } }),
                    (r) => `${r.gravados} lead(s) gravado(s).`,
                  )
                : setPend('busca'),
          },
          armadoBusca ? 'Confirmar busca' : 'Buscar',
        ),
        armadoBusca && h('span', { className: 'text-xs text-(--ui-text-tertiary)' }, 'Consulta a fonte externa (gosom) e grava os leads.'),
      ),
    ),
    h(
      'div',
      { className: 'flex items-center gap-2' },
      h('span', { className: 'text-xs text-(--ui-text-tertiary)' }, 'Status'),
      h(
        'select',
        { value: status, onChange: (e) => setStatus(e.target.value), className: SELECT },
        h('option', { value: '' }, 'Todos'),
        ...[...STATUS, OPTOUT].map((s) => h('option', { value: s }, s)),
      ),
    ),
    aviso(msg),
    conteudo,
  );
}

function ConfigForm({ inicial, ctx }) {
  const qc = useQueryClient();
  const [valores, setValores] = useState(() => Object.fromEntries(CAMPOS_CONFIG.map((c) => [c, inicial[c] ?? ''])));
  const [msg, setMsg] = useState(null);
  const [salvando, setSalvando] = useState(false);
  const set = (c) => (e) => setValores((v) => ({ ...v, [c]: e.target.value }));

  async function salvar() {
    setSalvando(true);
    try {
      await ctx.rest('/config', { method: 'PUT', body: valores });
      setMsg({ ok: true, texto: 'Configuração salva.' });
      qc.invalidateQueries({ queryKey: ['prospeccao', 'config'] });
    } catch (e) {
      setMsg({ ok: false, texto: erroDe(e) });
    } finally {
      setSalvando(false);
    }
  }

  return h(
    'div',
    { className: 'flex flex-col gap-3' },
    h('div', { className: 'text-xs text-(--ui-text-tertiary)' }, AVISO_ENVIO),
    campo(
      'Canal padrão',
      h('select', { value: valores.canal_padrao, onChange: set('canal_padrao'), className: SELECT }, h('option', { value: 'email' }, 'E-mail'), h('option', { value: 'whatsapp' }, 'WhatsApp')),
    ),
    campo('Remetente (e-mail)', h(Input, { value: valores.remetente_email, onChange: set('remetente_email') })),
    campo('Assunto padrão', h(Input, { value: valores.assunto_padrao, onChange: set('assunto_padrao') })),
    campo('Modelo de mensagem (use {nome} e {url})', h(Textarea, { rows: 4, value: valores.modelo_mensagem, onChange: set('modelo_mensagem') })),
    campo(
      'Provedor de publicação (externo)',
      h(
        'select',
        { value: valores.publicar_provedor_padrao, onChange: set('publicar_provedor_padrao'), className: SELECT },
        h('option', { value: 'vercel' }, 'Vercel'),
        h('option', { value: 'cloudflare' }, 'Cloudflare'),
      ),
    ),
    h('div', { className: 'flex items-center gap-2' }, h(Button, { size: 'xs', disabled: salvando, onClick: salvar }, 'Salvar'), aviso(msg)),
  );
}

function ConfigTab({ ctx }) {
  const cfg = useQuery(opcoesConfig(ctx));
  // Sem config carregada não há formulário: salvar um padrão vazio sobrescreveria a config real.
  if (!cfg.data) return h('div', null, cfg.error ? `Erro: ${erroDe(cfg.error)}` : 'Carregando configuração…');
  return h(ConfigForm, { inicial: cfg.data, ctx });
}

function ProspeccaoPane({ ctx }) {
  const [aba, setAba] = useState('leads');
  return h(
    'div',
    { className: 'flex h-full min-h-0 flex-col gap-3 p-3 text-sm' },
    h(
      'div',
      { className: 'flex gap-1' },
      h(Button, { size: 'xs', variant: aba === 'leads' ? 'default' : 'ghost', onClick: () => setAba('leads') }, 'Leads'),
      h(Button, { size: 'xs', variant: aba === 'config' ? 'default' : 'ghost', onClick: () => setAba('config') }, 'Configuração'),
    ),
    aba === 'leads' ? h(LeadsTab, { ctx }) : h(ConfigTab, { ctx }),
  );
}

export default {
  id: 'prospeccao',
  name: TITULO,
  register(ctx) {
    ctx.register({
      id: 'prospeccao',
      area: 'panes',
      title: TITULO,
      data: { title: TITULO, placement: 'main' },
      render: () => h(ProspeccaoPane, { ctx }),
    });
  },
};
