// Find a payment: ask in your own words, or narrow the list down with quick filters.
// The filters call the list_transactions tool directly, so results show at once.
import {
  html, useState, useContext, useTool, eur, num, fmtDate, parseDate, isoDate, t, periodLabel,
} from './lib.js';
import { UI, Icon, Chip, Skeleton, ErrorBox, Empty, TxList, catName } from './parts.js';

const PERIODS = ['today', 'this_week', 'last_month'];
const CATEGORIES = ['Groceries', 'Restaurants', 'Transportation', 'Housing', 'Utilities', 'Health', 'Home & Tech', 'Entertainment', 'Lifestyle', 'Travel'];
const OVER = 100;
const ISO = /^\d{4}-\d{2}-\d{2}$/;

export function Find() {
  const ui = useContext(UI);
  const id = ui.who.id;
  const today = ui.today || isoDate(new Date());
  const [text, setText] = useState('');
  const [period, setPeriod] = useState('this_week');
  const [range, setRange] = useState(null);
  const [category, setCategory] = useState(null);
  const [big, setBig] = useState(false);

  const openDates = () => {
    if (!range) {
      const d = parseDate(today) || new Date();
      setRange({ start: isoDate(new Date(d.getFullYear(), d.getMonth(), 1)), end: today });
    }
    setPeriod('custom');
  };

  let args = null;
  let rangeError = null;
  if (period === 'custom') {
    if (range && ISO.test(range.start) && ISO.test(range.end)) {
      if (range.start > range.end) rangeError = t('find.range_order');
      else args = { start: range.start, end: range.end };
    } else rangeError = t('find.range_pick');
  } else args = { period };
  if (args && category) args.category = category;
  if (args && big) args.min_amount = OVER;

  const list = useTool(id, 'list_transactions', args ? { ...args, sort: 'date', limit: 50 } : null);
  const sum = useTool(id, 'get_spending', args);
  const d = args ? list.data : null;
  const total = args && sum.data ? sum.data : null;
  const matching = d ? Number(d.matching_transactions) || 0 : 0;
  const shown = d ? Number(d.shown) || 0 : 0;
  const rows = d && Array.isArray(d.transactions) ? d.transactions.map((x) => ({ ...x, amount: -Math.abs(Number(x.amount) || 0) })) : null;
  const filtered = Boolean(category || big);

  const submit = (e) => {
    e.preventDefault();
    const q = text.trim();
    if (!q) return;
    setText('');
    ui.ask(q);
  };

  return html`<div class="stack find">
    <form class="findbar" role="search" data-tour="find-bar" onSubmit=${submit}>
      <label class="sr" for="find-q">${t('find.label')}</label>
      <span class="findbar__icon" aria-hidden="true"><${Icon} name="search" size=${22} /></span>
      <input id="find-q" type="search" enterkeyhint="search" autocomplete="off" maxlength="300"
        placeholder=${t('find.placeholder')} value=${text} onInput=${(e) => setText(e.target.value)} />
      <button type="submit" class="findbar__go" aria-label=${t('find.ask')} disabled=${!text.trim()}><${Icon} name="send" size=${20} /></button>
    </form>
    <p class="hint hint--tight">${t('find.hint')}</p>

    <section class="card builder" aria-label=${t('find.filters')}>
      <div class="builder__row">
        <span class="builder__label" id="find-when">${t('find.when')}</span>
        <div class="chips chips--scroll" role="group" aria-labelledby="find-when">
          ${PERIODS.map((p) => html`<${Chip} key=${p} active=${period === p} onClick=${() => setPeriod(p)}>${t('find.period.' + p)}<//>`)}
          <${Chip} active=${period === 'custom'} onClick=${openDates}><${Icon} name="calendar" size=${16} />${t('find.period.custom')}<//>
        </div>
        ${period === 'custom' && range ? html`<div class="dates">
          <label><span>${t('find.from')}</span>
            <input type="date" value=${range.start} max=${today} onInput=${(e) => setRange({ ...range, start: e.target.value })} /></label>
          <label><span>${t('find.to')}</span>
            <input type="date" value=${range.end} max=${today} onInput=${(e) => setRange({ ...range, end: e.target.value })} /></label>
        </div>` : null}
      </div>
      <div class="builder__row">
        <span class="builder__label" id="find-cat">${t('find.category')}</span>
        <div class="chips chips--scroll" role="group" aria-labelledby="find-cat">
          <${Chip} active=${!category} onClick=${() => setCategory(null)}>${t('find.all')}<//>
          ${CATEGORIES.map((c) => html`<${Chip} key=${c} active=${category === c} onClick=${() => setCategory(category === c ? null : c)}>${catName(c)}<//>`)}
        </div>
      </div>
      <div class="builder__row">
        <span class="builder__label" id="find-amt">${t('find.amount')}</span>
        <div class="chips" role="group" aria-labelledby="find-amt">
          <${Chip} active=${big} onClick=${() => setBig(!big)}>${t('find.over', { amount: eur(OVER, 'whole') })}<//>
        </div>
      </div>
    </section>

    <section aria-labelledby="find-res" aria-live="polite" aria-busy=${list.loading ? 'true' : 'false'}>
      <h2 id="find-res" class="sect">${t('find.results')}</h2>
      <div class="group group--pad">
        ${rangeError ? html`<${Empty} icon="calendar" title=${rangeError}>${t('find.range_text')}<//>` : null}
        ${args && list.error && !d ? html`<${ErrorBox} error=${list.error} onRetry=${list.reload} />` : null}
        ${args && !d && !list.error ? html`<${Skeleton} rows=${6} />` : null}
        ${d ? html`<div class=${list.loading || list.stale ? 'is-stale' : ''}>
          <div class="find__sum">
            <div>
              <span class="find__count">${t('n_payments', { n: matching, count: num(matching, 0) })}</span>
              <span class="find__period">${periodLabel(d.period)}</span>
            </div>
            <div class="find__total">
              <span>${t('find.total')}</span>
              <strong>${total && sum.url && !sum.loading ? eur(total.total, 'cents') : matching === 0 ? eur(0, 'cents') : '…'}</strong>
            </div>
          </div>
          ${rows && rows.length
            ? html`<${TxList} signed=${true} transactions=${rows} />`
            : html`<${Empty} icon="search" title=${t('find.none')}>${filtered ? t('find.none_filtered') : t('find.none_text')}<//>`}
          ${matching > shown && shown > 0 ? html`<p class="footnote">${t('find.shown', { shown: num(shown, 0), all: num(matching, 0) })}</p>` : null}
        </div>` : null}
      </div>
      ${d && d.period && matching > 0 ? html`<button type="button" class="textlink textlink--center" onClick=${() => ui.ask(t('find.ask_q', { period: periodLabel(d.period), from: fmtDate(d.period.start, { year: true }), to: fmtDate(d.period.end, { year: true }) }))}>
        <${Icon} name="chat" size=${18} />${t('find.ask_about')}</button>` : null}
    </section>
  </div>`;
}
