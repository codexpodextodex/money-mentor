// Explore: build your own question with chips, drill into the bars, or ask in SQL.
import {
  html, useState, useEffect, useRef, useContext, useApi, useJob, tool,
  eur, num, pct, fmtDate, fmtMonth, parseDate, isoDate, nice, BASKETS, BASKET_ORDER, basketOf, t, periodLabel, useLang,
} from './lib.js';
import {
  UI, Icon, Skeleton, ErrorBox, Empty, Disclosure, Chip,
  BarList, DataTable, TxList, spendRows, ChangeLine, catName, subName,
} from './parts.js';

const PERIODS = ['last_month', 'last_3_months', 'last_6_months', 'last_12_months', 'this_year', 'all_time'];
const GROUPS = ['category', 'subcategory', 'basket', 'merchant', 'month', 'week', 'weekday'];
const CATEGORIES = ['Housing', 'Utilities', 'Groceries', 'Transportation', 'Health', 'Home & Tech', 'Restaurants', 'Entertainment', 'Lifestyle', 'Travel'];
const START = { period: 'last_3_months', custom: null, basket: null, category: null, subcategory: null, groupBy: 'category' };
const DRILLS = { category: 'explore.drill.category', basket: 'explore.drill.basket', subcategory: 'explore.drill.payments', month: 'explore.drill.month', week: 'explore.drill.payments' };

function filterArgs(q) {
  const a = q.custom ? { ...q.custom.args } : { period: q.period };
  if (q.basket) a.basket = q.basket;
  if (q.category) a.category = q.category;
  if (q.subcategory) a.subcategory = q.subcategory;
  return a;
}

function filterTitle(q) {
  const parts = [];
  if (q.basket) parts.push(BASKETS[q.basket].name);
  if (q.category) parts.push(catName(q.category));
  if (q.subcategory) parts.push(subName(q.subcategory));
  return parts.length ? parts.join(' · ') : t('explore.all');
}

/* ---------- payments in a sheet ---------- */

function PaymentsBody({ id, args }) {
  useLang();
  const [sort, setSort] = useState('date');
  const job = useJob();
  const load = () => job.run(() => tool(id, 'list_transactions', { ...args, sort, limit: 50 }));
  useEffect(() => { load(); }, [sort]);
  const d = job.data;
  return html`<div class="payments">
    <div class="chips" role="group" aria-label=${t('explore.sort')}>
      <${Chip} active=${sort === 'date'} onClick=${() => setSort('date')}>${t('explore.newest')}<//>
      <${Chip} active=${sort === 'amount'} onClick=${() => setSort('amount')}>${t('explore.largest')}<//>
    </div>
    ${job.error ? html`<${ErrorBox} error=${job.error} onRetry=${load} />` : null}
    ${!d && !job.error ? html`<${Skeleton} rows=${6} />` : null}
    ${d ? html`<div class=${job.loading ? 'is-stale' : ''}>
      <p class="sub">${t('n_payments', { n: Number(d.matching_transactions), count: num(d.matching_transactions, 0) })}${d.period ? ` · ${periodLabel(d.period)}` : ''}${Number(d.matching_transactions) > Number(d.shown) ? ` · ${t('explore.showing', { n: num(d.shown, 0) })}` : ''}</p>
      <${TxList} transactions=${d.transactions} />
    </div>` : null}
  </div>`;
}

/* ---------- ask in SQL ---------- */

const EXAMPLES = [
  ['explore.sql.top', "SELECT subcategory, round(sum(spent), 2) AS total\nFROM my_transactions\nWHERE basket = 'everyday'\nGROUP BY 1 ORDER BY 2 DESC"],
  ['explore.sql.weekday', "SELECT dayname(date) AS weekday, round(sum(spent), 2) AS total, count(*) AS payments\nFROM my_transactions\nWHERE flow = 'spend'\nGROUP BY 1 ORDER BY 2 DESC"],
  ['explore.sql.largest', "SELECT date, subcategory, basket, spent\nFROM my_transactions\nWHERE flow = 'spend'\nORDER BY spent DESC LIMIT 10"],
];

function SqlPanel({ id }) {
  const schema = useApi('/api/explore/schema');
  const [sql, setSql] = useState(EXAMPLES[0][1]);
  const job = useJob();
  const out = useRef(null);
  const table = (schema.data && schema.data.table) || 'my_transactions';
  const cols = schema.data && Array.isArray(schema.data.columns) ? schema.data.columns : [];

  const run = (text) => {
    const q = String(text ?? sql).trim();
    if (!q || job.loading) return;
    job.run(() => tool(id, 'run_sql', { sql: q })).then(() => {
      if (out.current && out.current.scrollIntoView) out.current.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    });
  };
  const d = job.data;

  return html`<section aria-labelledby="sql-h">
    <h2 id="sql-h" class="sect">${t('explore.sql.title')}</h2>
    <div class="card sqlpanel">
      <p class="sub sub--first">${t('explore.sql.sub')} <code>${table}</code>.</p>
      <p class="synthetic"><${Icon} name="shield" size=${20} />
        <span><strong>${t('explore.sql.private')}</strong> ${t('explore.sql.private_text')}</span></p>
      <div class="chips" role="group" aria-label=${t('explore.sql.examples')}>
        ${EXAMPLES.map(([label, text]) => html`<${Chip} key=${label} active=${sql === text} onClick=${() => { setSql(text); run(text); }}>${t(label)}<//>`)}
      </div>
      <form onSubmit=${(e) => { e.preventDefault(); run(); }}>
        <label class="sr" for="sql">${t('explore.sql.label')}</label>
        <textarea id="sql" class="sqlbox" rows="5" spellcheck=${false} autocapitalize="none" autocorrect="off" autocomplete="off"
          value=${sql} onInput=${(e) => setSql(e.target.value)}
          onKeyDown=${(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); run(); } }}></textarea>
        <button type="submit" class="btn btn--primary" disabled=${job.loading || !sql.trim()}>
          <${Icon} name="play" size=${16} />${job.loading ? t('explore.sql.running') : t('explore.sql.run')}
        </button>
      </form>
      <div ref=${out} aria-live="polite">
        ${job.error ? html`<div class="state state--error" role="alert">
          <span class="state__icon"><${Icon} name="alert" /></span>
          <div class="state__text"><strong>${t('explore.sql.failed')}</strong><p>${job.error.message}</p></div>
        </div>` : null}
        ${d ? html`<div class=${job.loading ? 'is-stale' : ''}>
          ${Array.isArray(d.rows) && d.rows.length
            ? html`<${DataTable} columns=${d.columns} rows=${d.rows} />`
            : html`<${Empty} icon="search" title=${t('explore.sql.no_rows')}>${t('explore.sql.no_rows_text')}<//>`}
          <p class="footnote">${t('n_rows', { n: Number(d.row_count), count: num(d.row_count, 0) })}${d.truncated ? `. ${t('explore.sql.truncated')}` : ''}.</p>
        </div>` : null}
      </div>
      <${Disclosure} label=${t('explore.sql.schema')}>
        ${schema.error ? html`<${ErrorBox} error=${schema.error} onRetry=${schema.reload} />` : null}
        ${!schema.data && !schema.error ? html`<${Skeleton} rows=${4} />` : null}
        ${schema.data ? html`
          <p class="sub"><code>${table}</code>${schema.data.dialect ? ` · ${schema.data.dialect}` : ''}</p>
          <ul class="schema">${cols.map((c) => html`<li key=${c.name}><code>${c.name}</code><small>${String(c.type || '').toLowerCase()}</small><span>${nice(c.meaning)}</span></li>`)}</ul>` : null}
      <//>
    </div>
  </section>`;
}

/* ---------- the query builder ---------- */

const memo = new Map();

export function Explore() {
  const ui = useContext(UI);
  const id = ui.who.id;
  const [q, setQ] = useState(START);
  const [trail, setTrail] = useState([]);
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);
  const args = { ...filterArgs(q), group_by: q.groupBy };
  const key = id + JSON.stringify(args);

  useEffect(() => {
    if (memo.has(key)) {
      setState({ data: memo.get(key), error: null, loading: false });
      return undefined;
    }
    let alive = true;
    setState((s) => ({ ...s, error: null, loading: true }));
    tool(id, 'get_spending', args).then(
      (data) => { memo.set(key, data); if (alive) setState({ data, error: null, loading: false }); },
      (error) => { if (alive) setState({ data: null, error, loading: false }); },
    );
    return () => { alive = false; };
  }, [key, tick]);

  const change = (patch) => setQ((cur) => ({ ...cur, ...patch }));
  const dive = (next) => { setTrail((list) => [...list, q]); setQ(next); };
  const back = () => {
    if (!trail.length) return;
    setQ(trail[trail.length - 1]);
    setTrail(trail.slice(0, -1));
  };
  const reset = () => { setTrail([]); setQ(START); };

  const openPayments = (extra, title) => ui.openSheet({
    title: title || t('tool.list_transactions.title'),
    body: html`<${PaymentsBody} id=${id} args=${{ ...filterArgs(q), ...extra }} />`,
  });

  const pick = (row) => {
    const k = row.raw.key;
    const g = q.groupBy;
    if (g === 'category') dive({ ...q, category: k, subcategory: null, groupBy: 'subcategory' });
    else if (g === 'basket') {
      const b = basketOf(k);
      if (b) dive({ ...q, basket: b.id, groupBy: 'category' });
    } else if (g === 'subcategory') openPayments({ subcategory: k }, subName(k));
    else if (g === 'month') dive({ ...q, custom: { month: k, args: { period: k } }, groupBy: 'category' });
    else if (g === 'week') {
      const start = parseDate(k);
      if (!start) return;
      const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 6);
      openPayments({ period: undefined, start: k, end: isoDate(end) }, t('explore.week_of', { date: fmtDate(k) }));
    }
  };

  const setBasket = (b) => {
    const basket = q.basket === b ? null : b;
    change({ basket, groupBy: basket && q.groupBy === 'basket' ? 'category' : q.groupBy });
  };
  const setCategory = (c) => {
    const category = q.category === c ? null : c;
    change({ category, subcategory: null, groupBy: category && q.groupBy === 'category' ? 'subcategory' : q.groupBy });
  };

  const d = state.data;
  const filtered = Boolean(q.basket || q.category || q.subcategory);
  const tone = q.basket ? 'b-' + q.basket : 't-accent';
  const canDrill = Boolean(DRILLS[q.groupBy]);
  const rows = d ? spendRows(d, tone).map((r) => ({ ...r, pick: canDrill && !/^\d+ more$/.test(r.key) })) : [];
  const n = d ? Number(d.transactions) || 0 : 0;
  const changed = JSON.stringify(q) !== JSON.stringify(START);
  const customLabel = q.custom ? fmtMonth(q.custom.month, true) : '';
  const drill = canDrill ? t(DRILLS[q.groupBy]) : '';

  return html`<div class="stack">
    <section class="card builder" aria-label=${t('explore.build')}>
      <p class="lead">${t('explore.lead')}</p>
      <div class="builder__row">
        <span class="builder__label" id="xp-period">${t('explore.period')}</span>
        <div class="chips chips--scroll" role="group" aria-labelledby="xp-period">
          ${q.custom ? html`<${Chip} active=${true} onClick=${() => change({ custom: null })} label=${t('explore.remove', { what: customLabel })}>${customLabel}<${Icon} name="close" size=${14} /><//>` : null}
          ${PERIODS.map((k) => html`<${Chip} key=${k} active=${!q.custom && q.period === k} onClick=${() => change({ period: k, custom: null })}>${t('explore.p.' + k)}<//>`)}
        </div>
      </div>
      <div class="builder__row">
        <span class="builder__label" id="xp-filter">${t('explore.show')}</span>
        <div class="chips chips--scroll" role="group" aria-labelledby="xp-filter">
          ${q.subcategory ? html`<${Chip} active=${true} onClick=${() => change({ subcategory: null })} label=${t('explore.remove', { what: subName(q.subcategory) })}>${subName(q.subcategory)}<${Icon} name="close" size=${14} /><//>` : null}
          <${Chip} active=${!filtered} onClick=${() => change({ basket: null, category: null, subcategory: null })}>${t('explore.all')}<//>
          ${BASKET_ORDER.map((b) => html`<${Chip} key=${b} tone=${'chip--basket b-' + b} active=${q.basket === b} onClick=${() => setBasket(b)}>
            <i class="dot" aria-hidden="true"></i>${BASKETS[b].short}<//>`)}
          ${CATEGORIES.map((c) => html`<${Chip} key=${c} active=${q.category === c} onClick=${() => setCategory(c)}>${catName(c)}<//>`)}
        </div>
      </div>
      <div class="builder__row">
        <span class="builder__label" id="xp-group">${t('explore.break')}</span>
        <div class="chips chips--scroll" role="group" aria-labelledby="xp-group">
          ${GROUPS.map((k) => html`<${Chip} key=${k} active=${q.groupBy === k} onClick=${() => change({ groupBy: k })}>${t('explore.g.' + k)}<//>`)}
        </div>
      </div>
    </section>

    <section class="card result" aria-live="polite" aria-busy=${state.loading ? 'true' : 'false'}>
      ${trail.length || changed ? html`<div class="result__nav">
        ${trail.length ? html`<button type="button" class="textlink" onClick=${back}><${Icon} name="back" size=${18} />${t('common.back')}</button>` : html`<span></span>`}
        ${changed ? html`<button type="button" class="textlink" onClick=${reset}>${t('explore.reset')}</button>` : null}
      </div>` : null}
      ${state.error ? html`<${ErrorBox} title=${t('explore.error')} error=${state.error} onRetry=${() => setTick((x) => x + 1)} />` : null}
      ${!d && !state.error ? html`<${Skeleton} rows=${5} tall=${true} />` : null}
      ${d && !state.error ? html`<div class=${state.loading ? 'is-stale' : ''}>
        <p class="eyebrow">${filterTitle(q)}${d.period ? ` · ${periodLabel(d.period)}` : ''}</p>
        <p class="big">${eur(d.total)}</p>
        <p class="sub">
          ${t('n_payments', { n, count: num(n, 0) })}${n > 1 ? ` · ${t('ans.avg', { amount: eur(d.average_per_transaction) })} · ${t('explore.largest_one', { amount: eur(d.largest_transaction) })}` : ''}${filtered && Number.isFinite(Number(d.share_of_all_spending_pct)) ? ` · ${t('explore.share', { pct: pct(d.share_of_all_spending_pct) })}` : ''}
        </p>
        <${ChangeLine} prev=${d.previous_period} />
        ${rows.length ? html`
          <h3 class="h3">${t('explore.by', { what: t('explore.g.' + q.groupBy).toLowerCase() })}</h3>
          <${BarList} key=${key} rows=${rows} onPick=${canDrill ? pick : null} pickLabel=${drill} />
          <p class="footnote">${canDrill ? t('explore.tap', { what: drill.toLowerCase() }) : t('explore.each')}</p>`
          : html`<${Empty} icon="search" title=${t('ans.nothing_title')}>
              ${t('explore.none')}${filtered ? ' ' + t('explore.none_filter') : ''}
            <//>`}
        ${n > 0 ? html`<button type="button" class="btn btn--small" onClick=${() => openPayments({}, filterTitle(q))}><${Icon} name="list" size=${16} />${t('explore.see_payments')}</button>` : null}
      </div>` : null}
    </section>

    <${SqlPanel} id=${id} />
  </div>`;
}
