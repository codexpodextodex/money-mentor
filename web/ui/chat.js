// Ask your money: chat with tool traces, a visual card per result, and a trust line.
import {
  html, useState, useEffect, useRef, useContext, streamChat,
  eur, eurSigned, num, pct, fmtDate, nice, said, words, basketOf, t, tv, has, english, getLang, periodLabel, reducedMotion,
} from './lib.js';
import {
  UI, Icon, Logo, Empty, Disclosure, Chip, KeyValue, StatusPill, Amount,
  BasketBar, BasketLegend, BarList, Waterfall, Columns, PeerBars, PillarMeter, Pillars,
  DataTable, TxList, Timeline, BasketRules, spendRows, ChangeLine, catName, subName,
} from './parts.js';
import { SAFE_STATUS } from './host.js';
import { planCard, outlookCard, noticeText } from './plan.js';
import { habitName } from './replay.js';

const SUGGESTIONS = ['fastfood', 'clothes', 'safe', 'where', 'dining', 'jacket', 'type', 'mortgage'].map((k) => 'ask.q.' + k);
const EXTRA_QUESTIONS = ['ask.q.unseen', 'ask.q.photo', 'ask.q.bill', 'plan.ask_q', 'outlook.ask_q'];

/** Without the AI model only the English keyword router answers: hand it the English question. */
function forRouter(text) {
  if (getLang() === 'en') return text;
  const key = [...SUGGESTIONS, ...EXTRA_QUESTIONS].find((k) => t(k) === text);
  return key ? english(key) : text;
}

// What each tool does, in plain words: tool.<name>.run | .done | .title
const toolText = (name, part) => {
  const key = `tool.${name}.${part}`;
  if (has(key)) return t(key);
  const plain = words(name).toLowerCase();
  return part === 'run' ? t('tool.other.run', { name: plain }) : part === 'done' ? t('tool.other.done', { name: plain }) : words(name);
};

/* ---------- result cards, one per tool ---------- */

const DECISION = {
  approved: { key: 'decision.approved', tone: 'good', icon: 'check' },
  rejected: { key: 'decision.rejected', tone: 'bad', icon: 'close' },
};
const FITS = {
  yes: { key: 'fits.yes', tone: 'good', icon: 'check' },
  tight: { key: 'fits.tight', tone: 'warn', icon: 'alert' },
  not_from_this_budget: { key: 'fits.not_from_this_budget', tone: 'bad', icon: 'alert' },
  no: { key: 'fits.no', tone: 'bad', icon: 'close' },
};

const SAMPLE_PHOTO = '/assets/img/sample-price-tag.jpg';
// A made-up bill (scripts/make_sample_bill.py): the company, the customer and the account are invented.
const SAMPLE_BILL = '/assets/img/sample-bill.jpg';

/** The model's id as the server reports it, as a name people recognise. */
const modelName = (id) => (!id ? t('chat.the_model') : /nemotron/i.test(id) ? 'NVIDIA Nemotron 3.5 Super VL' : id);
/** Where the model ran: our own container on Verda in Finland, or NVIDIA's hosted API as the fallback. */
const hostName = (host) => (
  /confidential/i.test(host) ? t('host.verda_cc')
    : /verda/i.test(host) ? t('host.verda')
      : /nvidia/i.test(host) ? t('host.nvidia') : host
);

/** Shrink a photo in the browser, so only a small JPEG ever leaves the phone. */
function readPhoto(file, max = 1280) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, max / Math.max(img.naturalWidth, img.naturalHeight, 1));
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(img.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL('image/jpeg', 0.82));
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error(t('chat.photo_error'))); };
    img.src = url;
  });
}

function filterText(filters) {
  const f = filters && typeof filters === 'object' ? filters : {};
  const parts = [];
  if (f.basket) parts.push((basketOf(f.basket) || {}).name || f.basket);
  if (f.category) parts.push(catName(f.category));
  if (f.subcategory) {
    // A plain word such as "clothes" covers several kinds of shop, which the server joins with "and".
    const one = String(f.subcategory);
    parts.push(has('sub.' + one) ? subName(one) : one.split(' and ').map(subName).join(', '));
  }
  return parts.join(', ');
}

const perMonth = (v, mode) => t('unit.per_month', { amount: eur(v, mode) });
const nDays = (n) => t('n_days', { n: Number(n), count: num(n, 0) });

/** The payments behind a total, ticked off one by one: "this is fast food, and this, and this". */
function Counted({ counted }) {
  const list = counted && Array.isArray(counted.payments) ? counted.payments : [];
  if (!list.length) return null;
  const all = Math.max(Number(counted.of) || 0, list.length);
  const more = all - list.length;
  return html`<div class="counted">
    <p class="counted__title">${t('ans.counted', { n: all, count: num(all, 0) })}</p>
    <ul class="counted__list">
      ${list.map((x, i) => html`<li key=${i} style=${`--i:${i}`}>
        <span class="counted__tick" aria-hidden="true"><${Icon} name="check" size=${14} stroke=${2.400} /></span>
        <span class="counted__what"><strong>${x.subcategory ? subName(x.subcategory) : catName(x.category)}</strong><small>${fmtDate(x.date)}</small></span>
        <span class="counted__amt">${eur(x.amount, 'cents')}</span>
      </li>`)}
    </ul>
    ${more > 0 ? html`<p class="footnote">${t('ans.counted_more', { n: more, count: num(more, 0) })}</p>` : null}
  </div>`;
}

/**
 * When a purchase that does not fit now could fit (the tool's `when`): from the next payday, or in
 * about N months with one habit changed. Nothing when the tool gives no route. Every figure is the tool's.
 */
function whenItFits(when, ui) {
  const w = when && typeof when === 'object' ? when : {};
  const p = w.next_pay_period && typeof w.next_pay_period === 'object' ? w.next_pay_period : {};
  const h = w.one_habit && typeof w.one_habit === 'object' ? w.one_habit : {};
  const some = (v) => v !== null && v !== undefined && Number.isFinite(Number(v));

  if (w.route === 'next_pay_period') {
    const date = w.earliest || p.starts_on_payday;
    if (!date) return null;
    return html`<div class="tip whenfit">
      <strong>${t('ans.when_title')}</strong>
      <p class="whenfit__lead">${t('ans.when_from', { date: fmtDate(date) })}</p>
      <p class="whenfit__text">${t('ans.when_room')}</p>
      ${some(p.left_for_everything_else_a_week) && some(p.your_usual_everyday_spending_a_week) ? html`<dl class="whenfit__pair">
        <div><dt>${t('ans.when_left_week')}</dt><dd>${eur(p.left_for_everything_else_a_week, 'whole')}</dd></div>
        <div><dt>${t('ans.when_usual_week')}</dt><dd>${eur(p.your_usual_everyday_spending_a_week, 'whole')}</dd></div>
      </dl>` : null}
    </div>`;
  }

  if (w.route === 'one_habit') {
    const months = Number(h.months_for_this_price);
    if (!(months > 0)) return null;
    // The habit by the name the replay screen gives it; the tool's own words for one that screen does not know.
    const name = habitName(h.lever, h, getLang()) || nice(h.habit);
    return html`<div class="tip whenfit">
      <strong>${t('ans.when_title')}</strong>
      <p class="whenfit__lead">${t('ans.when_habit', { n: months, count: num(months, 0) })}</p>
      ${p.has_room_for_it === false ? html`<p class="whenfit__text">${t('ans.when_not_next')}</p>` : null}
      <div class="whenfit__habit">
        ${name ? html`<p class="whenfit__name">${name}</p>` : null}
        ${some(h.would_have_kept_a_month) ? html`<p>${t('ans.when_kept', { amount: eur(h.would_have_kept_a_month, 'whole') })}</p>` : null}
      </div>
      <p class="whenfit__note">${t('ans.when_past')}</p>
      ${ui && ui.go ? html`<button type="button" class="whenfit__link" onClick=${() => ui.go('replay')}>${t('ans.when_replay')}<${Icon} name="right" size=${16} /></button>` : null}
    </div>`;
  }

  return null;
}

/* ---------- a payment prepared from a photographed bill ---------- */

// What the engine found when it recalculated a number's check digits.
const CHECKED = {
  checks_out: { key: 'pay.ok', tone: 'good', icon: 'check' },
  does_not_check_out: { key: 'pay.bad', tone: 'bad', icon: 'alert' },
  missing: { key: 'pay.missing', tone: 'bad', icon: 'alert' },
};
const inDays = (n) => (n <= 0 ? t('plan.in_today') : n === 1 ? t('plan.in_tomorrow') : t('plan.in_days', { count: num(n, 0) }));

// An account number that failed its check comes back as it was read, unspaced: set it in fours, as a bill prints it, to compare.
const fours = (v) => (v && !/\s/.test(String(v)) ? String(v).replace(/(.{4})(?=.)/g, '$1 ') : v);

/** One line of the form: the number as read, and whether its check digits agree. */
function PayField({ label, value, status, quiet }) {
  const flagged = !quiet && status !== 'checks_out';
  return html`<div class=${'payfield' + (flagged ? ' is-bad' : '')}>
    <dt>${label}</dt>
    ${quiet ? null : html`<${StatusPill} status=${status} map=${CHECKED} />`}
    <dd>${value || '–'}</dd>
  </div>`;
}

/**
 * The draft, laid out as a payment form the bank filled in. Every figure is the tool's. The button
 * is there only when the engine says the draft is ready, and pressing it pays nothing: this is a demo.
 */
function PaymentDraft({ r }) {
  const [pressed, setPressed] = useState(false);
  const done = useRef(null);
  // The note that replaces the button is taller than the button: bring all of it into view.
  useEffect(() => {
    if (pressed && done.current) done.current.scrollIntoView({ block: 'nearest', behavior: reducedMotion() ? 'auto' : 'smooth' });
  }, [pressed]);
  const d = r.draft && typeof r.draft === 'object' ? r.draft : {};
  const c = r.checks && typeof r.checks === 'object' ? r.checks : {};
  const bal = r.balance && typeof r.balance === 'object' ? r.balance : null;
  const basket = r.basket && typeof r.basket === 'object' ? r.basket : null;
  const b = basket ? basketOf(basket.name) : null;
  const ready = r.ready_to_confirm === true;
  const days = Number(d.due_in_days);
  const noRef = c.reference === 'missing';
  const differs = [c.amount, c.due_date].includes('readings_differ') || c.due_date === 'not_after_the_bill_date'
    || ['smaller_than_another_amount', 'not_read_twice'].includes(c.amount);
  const twice = c.amount === 'read_twice_same' && (c.due_date === 'read_twice_same' || c.due_date === 'missing');
  const wrong = differs || [c.account_number, c.reference].includes('does_not_check_out');
  // What stops the draft, said from the statuses (the tool's own sentences are in English, for the model).
  const stops = [
    c.account_number === 'does_not_check_out' ? t('pay.fix_account') : c.account_number === 'missing' ? t('pay.fix_account_missing') : null,
    c.reference === 'does_not_check_out' ? t('pay.fix_reference') : null,
    c.amount === 'readings_differ' ? t('pay.fix_amount') : c.amount === 'smaller_than_another_amount' ? t('pay.fix_amount_larger')
      : c.amount === 'not_read_twice' ? t('pay.fix_amount_once') : null,
    c.due_date === 'readings_differ' ? t('pay.fix_due') : c.due_date === 'not_after_the_bill_date' ? t('pay.fix_due_order') : null,
  ].filter(Boolean);
  return html`
    <div class="pay__top">
      <p class="pay__to"><span>${t('pay.payee')}</span><strong>${d.payee || t('pay.payee_missing')}</strong></p>
      <span class="pay__badge">${t(pressed ? 'pay.badge_done' : 'pay.badge')}</span>
    </div>
    <p class="pay__amount"><${Amount} value=${d.amount} mode="cents" /></p>
    <p class="pay__due"><${Icon} name="calendar" size=${18} />${d.due_date
      ? html`<span>${t('pay.due', { date: fmtDate(d.due_date, { year: true }) })}${Number.isFinite(days) && d.due_in_days !== null
        ? html` · <b class=${d.overdue ? 'is-bad' : ''}>${d.overdue ? t('pay.overdue', { days: nDays(Math.abs(days)) }) : inDays(days)}</b>` : null}</span>`
      : html`<span>${t('pay.no_due')}</span>`}</p>
    <dl class="pay__fields">
      <${PayField} label=${t('pay.account')} value=${fours(d.account_number)} status=${c.account_number} />
      <${PayField} label=${t('pay.reference')} value=${d.reference} status=${c.reference} quiet=${noRef} />
    </dl>
    ${noRef ? html`<p class="pay__how"><${Icon} name="info" size=${16} /><span>${t('pay.ref_none')}</span></p>` : null}
    ${ready ? html`<p class="pay__how pay__how--ok"><${Icon} name="shield" size=${16} /><span>${t(noRef ? 'pay.how_one' : 'pay.how')}${twice ? ' ' + t('pay.how_twice') : ''}</span></p>` : null}
    ${ready ? null : html`<div class="pay__fix" role="alert">
      <${Icon} name="alert" size=${20} />
      <div><strong>${t('pay.fix_title')}</strong>
        ${stops.map((line, i) => html`<p key=${i}>${line}</p>`)}
        <p>${t(wrong ? 'pay.fix_do' : 'pay.fix_retake')}</p></div>
    </div>`}
    <ul class="pay__facts">
      ${bal ? html`<li class=${bal.covers_it ? 'is-good' : 'is-bad'}>
        <${Icon} name=${bal.covers_it ? 'check' : 'alert'} size=${18} stroke=${2} />
        <span><strong>${t(bal.covers_it ? 'pay.covers' : 'pay.covers_not')}</strong>
          <small>${t('pay.left_after', { amount: eur(bal.left_on_the_account_after, 'cents') })}</small></span>
      </li>` : null}
      ${b ? html`<li><i class=${'dot b-' + b.id} aria-hidden="true"></i><span>${b.name}${basket.category ? ` · ${catName(basket.category)}` : ''}</span></li>` : null}
    </ul>
    ${ready && !pressed ? html`
      <button type="button" class="btn btn--primary btn--wide" onClick=${() => setPressed(true)}>${t('pay.confirm')}</button>
      <p class="pay__note">${t('pay.confirm_note')}</p>` : null}
    ${ready && pressed ? html`<div class="pay__done" role="status" ref=${done}>
      <span class="demo">${t('common.demo')}</span>
      <strong>${t('pay.done_title')}</strong>
      <p>${t('pay.done_text')}</p>
    </div>` : null}`;
}

const CARDS = {
  get_spending(r) {
    const b = basketOf(r.filters && r.filters.basket);
    const n = Number(r.transactions) || 0;
    const rows = spendRows(r, b ? 'b-' + b.id : 't-accent');
    return {
      title: filterText(r.filters) ? t('ans.spending_on', { what: filterText(r.filters) }) : t('tool.get_spending.title'),
      body: html`
        <p class="figure"><strong>${eur(r.total)}</strong><span>${t('n_payments', { n, count: num(n, 0) })}${n > 1 ? ` · ${t('ans.avg', { amount: eur(r.average_per_transaction) })}` : ''}</span></p>
        <${ChangeLine} prev=${r.previous_period} />
        ${rows.length ? html`<${BarList} rows=${rows} />` : html`<${Counted} counted=${r.counted} />`}
        ${n === 0 ? html`<${Empty} icon="search" title=${t('ans.nothing_title')}>${t('ans.nothing_text')}<//>` : null}`,
    };
  },
  list_transactions(r) {
    const shown = Number(r.shown) || 0;
    const all = Number(r.matching_transactions) || 0;
    return {
      title: filterText(r.filters) ? t('ans.payments_on', { what: filterText(r.filters) }) : t('tool.list_transactions.title'),
      body: html`<${TxList} transactions=${r.transactions} />
        ${all > shown ? html`<p class="footnote">${t('ans.showing', { shown, all, order: t(r.sorted_by === 'amount' ? 'ans.largest_first' : 'ans.newest_first') })}</p>` : null}`,
    };
  },
  get_baskets(r) {
    const s = r.small_everyday_purchases;
    return {
      body: html`<${BasketBar} parts=${r.baskets} /><${BasketLegend} parts=${r.baskets} />
        <dl class="trio">
          <div><dt>${t('cols.money_in')}</dt><dd>${eur(r.income, 'whole')}</dd></div>
          <div><dt>${t('cols.spent')}</dt><dd>${eur(r.spending, 'whole')}</dd></div>
          <div><dt>${t('baskets.left')}</dt><dd class=${Number(r.left_over) < 0 ? 'is-bad' : ''}>${eur(r.left_over, 'whole')}</dd></div>
        </dl>
        ${s && Number(s.count) > 0 ? html`<p class="footnote">${t('slip.title')}: ${t('slip.text', { n: Number(s.count), count: num(s.count, 0), under: eur(s.under_eur, 'whole'), total: eur(s.total) })}.</p>` : null}`,
    };
  },
  get_cashflow(r) {
    return { body: html`<${Columns} months=${r.months} />` };
  },
  get_safe_to_spend(r) {
    const w = r.this_week || {};
    const p = r.pay_period || {};
    return {
      body: html`
        <div class="card__row"><p class="figure"><strong>${eur(w.safe_to_spend, 'whole')}</strong><span>${t('ans.next_days', { days: nDays(w.days_left) })}</span></p>
          <${StatusPill} status=${r.status} map=${SAFE_STATUS} /></div>
        <dl class="trio">
          <div><dt>${t('trainer.a_day')}</dt><dd>${eur(r.safe_per_day)}</dd></div>
          <div><dt>${t('trainer.until_payday')}</dt><dd>${eur(r.safe_to_spend_until_payday, 'whole')}</dd></div>
          <div><dt>${t('trainer.next_payday')}</dt><dd>${fmtDate(p.next_payday)}</dd></div>
        </dl>
        <${Disclosure} label=${t('ans.see_budget')}><${Waterfall} lines=${r.budget} /><//>`,
    };
  },
  simulate_change(r) {
    const b = basketOf(r.target);
    const saving = Number(r.monthly_saving) || 0;
    const less = saving >= 0;
    const change = Number(r.change_pct);
    const target = b ? b.name : r.target ? catName(r.target) : '';
    return {
      title: t('ans.what_if', { target, change: `${change > 0 ? '+' : ''}${pct(change)}` }),
      period: r.based_on,
      body: html`
        <${BarList} tone=${b ? 'b-' + b.id : 't-accent'} rows=${[
          { key: 'now', label: t('ans.now'), value: r.monthly_now, text: perMonth(r.monthly_now) },
          { key: 'after', label: t('ans.after'), value: r.monthly_after, text: perMonth(r.monthly_after) },
        ]} />
        <dl class="trio">
          <div><dt>${t(less ? 'ans.freed_month' : 'ans.extra_month')}</dt><dd>${eur(Math.abs(saving))}</dd></div>
          <div><dt>${t(less ? 'ans.freed_year' : 'ans.extra_year')}</dt><dd>${eur(Math.abs(Number(r.yearly_saving) || 0), 'whole')}</dd></div>
          <div><dt>${t('ans.left_month')}</dt><dd>${eur(r.monthly_left_over_after, 'whole')}<small> ${t('ans.was', { amount: eur(r.monthly_left_over_now, 'whole') })}</small></dd></div>
        </dl>`,
    };
  },
  check_affordability(r, ui) {
    const item = r.item || {};
    const b = basketOf(item.basket);
    const treat = r.if_it_is_a_treat && typeof r.if_it_is_a_treat === 'object' ? r.if_it_is_a_treat : null;
    const e = r.everyday_budget || (treat && treat.everyday_budget);
    const u = r.unexpected_buffer;
    return {
      title: item.what ? t('ans.afford', { what: item.what }) : t('tool.check_affordability.title'),
      body: html`
        <div class="card__row"><p class="figure"><strong>${eur(item.amount)}</strong>
          <span>${b ? html`<i class=${'dot b-' + b.id} aria-hidden="true"></i> ${b.name}` : nice(item.basket)}${item.category ? ` · ${catName(item.category)}` : ''}</span></p>
          ${treat ? null : html`<${StatusPill} status=${r.fits} map=${FITS} />`}</div>
        ${treat ? html`
          <ul class="readings">
            <li><div class="readings__head"><strong>${t('ans.if_need')}</strong><${StatusPill} status=${r.fits} map=${FITS} /></div>${said(r.why) ? html`<p>${said(r.why)}</p>` : null}</li>
            <li><div class="readings__head"><strong>${t('ans.if_treat')}</strong><${StatusPill} status=${treat.fits} map=${FITS} /></div>${said(treat.why) ? html`<p>${said(treat.why)}</p>` : null}</li>
          </ul>
          ${said(item.basket_depends_on) ? html`<p class="footnote">${said(item.basket_depends_on)}</p>` : null}`
          : said(r.why) ? html`<p>${said(r.why)}</p>` : null}
        ${e ? html`<${BarList} tone="b-everyday" max=${Math.max(Number(e.safe_until_payday) || 0, Number(item.amount) || 0)} rows=${[
          { key: 'price', label: t('ans.this_purchase'), value: item.amount, text: eur(item.amount) },
          { key: 'week', label: t('home.safe_label'), value: Math.max(0, Number(e.safe_this_week) || 0), text: eur(e.safe_this_week, 'whole') },
          { key: 'payday', label: `${t('ans.safe_payday')}${r.next_payday ? ` (${fmtDate(r.next_payday)})` : ''}`, value: Math.max(0, Number(e.safe_until_payday) || 0), text: eur(e.safe_until_payday, 'whole') },
        ]} />` : null}
        ${u ? html`<dl class="trio">
          <div><dt>${t('ans.set_aside')}</dt><dd>${eur(u.set_aside_per_month, 'whole')}</dd></div>
          <div><dt>${t('ans.can_cover')}</dt><dd>${eur(r.balance_can_cover_before_payday, 'whole')}</dd></div>
          <div><dt>${t('ans.left_after')}</dt><dd class=${Number(r.balance_left_after) < 0 ? 'is-bad' : ''}>${eur(r.balance_left_after, 'whole')}</dd></div>
        </dl>` : null}
        ${whenItFits(r.when, ui)}
        ${said(item.why_this_basket) ? html`<p class="footnote">${said(item.why_this_basket)}</p>` : null}`,
    };
  },
  get_highlights(r) {
    const list = Array.isArray(r.notices) ? r.notices : [];
    return {
      period: r.month,
      body: list.length
        ? html`<ul class="tx">${list.map((n) => {
            const text = noticeText(n);
            return html`<li key=${n.kind}>
              <span class="tx__what"><strong class="wrap">${text.title}</strong><small class="wrap">${text.detail}</small></span>
            </li>`;
          })}</ul>`
        : html`<${Empty} icon="check" title=${t('ans.nothing_unusual')}>${t('trainer.notices_none')}<//>`,
    };
  },
  get_spender_profile(r) {
    const cats = Array.isArray(r.top_everyday_categories) ? r.top_everyday_categories : [];
    const text = (field) => (has(`type.${r.spender_type}.${field}`) ? t(`type.${r.spender_type}.${field}`) : nice(r[field]));
    return {
      period: r.based_on,
      body: html`<p class="profile__type">${tv('type', r.spender_type)}</p><p>${text('summary')}</p>
        ${cats.length ? html`<${BarList} tone="b-everyday" rows=${cats.map((c) => ({ key: c.category, label: catName(c.category), value: c.monthly, text: perMonth(c.monthly) }))} />` : null}
        ${r.tip ? html`<div class="tip"><strong>${t('profile.next')}</strong><p>${text('tip')}</p></div>` : null}`,
    };
  },
  compare_with_peers(r) {
    return {
      period: r.based_on,
      body: html`<p class="sub">${t('profile.compared', { who: nice(r.compared_with) })}</p><${PeerBars} comparisons=${r.comparisons} />`,
    };
  },
  get_regular_payments(r) {
    const items = Array.isArray(r.items) ? r.items : [];
    return {
      period: r.based_on,
      body: items.length
        ? html`<ul class="tx">${items.map((it, i) => html`<li key=${i}>
            <span class="tx__what"><strong>${nice(it.what)}</strong>
              <small>${[it.usual_day_of_month ? t('ans.day', { n: it.usual_day_of_month }) : t('ans.varies'), it.next_expected ? t('ans.next', { date: fmtDate(it.next_expected) }) : null, Number(it.payments_per_month) > 1 ? t('ans.per_month_n', { n: num(it.payments_per_month) }) : null].filter(Boolean).join(' · ')}</small></span>
            <span class=${'tx__amt' + (it.direction === 'in' ? ' is-in' : '')}>${eurSigned(it.direction === 'in' ? it.monthly_amount : -Math.abs(Number(it.monthly_amount) || 0))}</span>
          </li>`)}</ul>`
        : html`<${Empty} icon="calendar" title=${t('ans.no_regular')}>${t('ans.no_regular_text')}<//>`,
    };
  },
  get_mortgage_readiness(r, ui) {
    const h = r.home || {};
    const first = Array.isArray(r.what_would_matter_most) ? r.what_would_matter_most[0] : null;
    return {
      body: html`
        <p class="sub">${t('ans.home', { price: eur(h.property_price, 'whole'), own: eur(h.own_money, 'whole'), loan: eur(h.loan, 'whole') })}</p>
        <p class="figure"><strong>${nice(r.readiness)}</strong></p>
        <${PillarMeter} pillars=${r.pillars} />
        <${Pillars} pillars=${r.pillars} compact=${true} />
        ${first ? html`<div class="tip"><strong>${t('loan.matter')}</strong><p>${nice(first.change)}</p></div>` : null}
        ${r.note ? html`<p class="footnote">${nice(r.note)}</p>` : null}
        <button type="button" class="btn btn--small" onClick=${() => ui.go('loan', { price: h.property_price, own: h.own_money })}>${t('ans.try_prices')}<${Icon} name="right" size=${16} /></button>`,
    };
  },
  get_mortgage_application(r) {
    if (!r.has_application) {
      return { body: html`<${Empty} icon="doc" title=${t('ans.no_app')}>${nice(r.note || '')}<//>` };
    }
    return {
      body: html`
        <div class="card__row"><p class="figure"><strong>${eur(r.property_price, 'whole')}</strong><span>${t('ans.home_loan', { loan: eur(r.requested_loan, 'whole') })}</span></p>
          <${StatusPill} status=${r.decision} map=${DECISION} /></div>
        ${r.rejection_reason_plain ? html`<p>${t('ans.reason', { reason: nice(r.rejection_reason_plain) })}</p>` : null}
        <${Disclosure} label=${t('ans.steps', { n: (r.timeline || []).length })}><${Timeline} items=${r.timeline} /><//>`,
    };
  },
  run_sql(r) {
    return {
      body: html`<pre class="sql"><code>${r.sql}</code></pre>
        <${DataTable} columns=${r.columns} rows=${r.rows} />
        <p class="footnote">${t('n_rows', { n: Number(r.row_count), count: num(r.row_count, 0) })}${r.truncated ? t('ans.shortened') : ''}. ${t('ans.sql_note')}</p>`,
    };
  },
  explain_baskets(r) {
    return { body: html`<${BasketRules} data=${r} />` };
  },
  // A bill from a photo, as a draft to look over. Nothing is paid.
  prepare_payment(r) {
    return { body: html`<${PaymentDraft} r=${r} />` };
  },
  // The next salary, split and ready to accept; and the weeks ahead (both drawn in plan.js).
  get_payday_plan(r, ui) {
    return planCard(r, ui);
  },
  get_balance_outlook(r, ui) {
    return outlookCard(r, ui);
  },
};

function ToolCard({ step }) {
  const ui = useContext(UI);
  const r = step.result;
  if (!r || typeof r !== 'object') return null;
  if (r.error) {
    return html`<article class="toolcard toolcard--error">
      <header><h4>${toolText(step.name, 'title')}</h4></header>
      <p><${Icon} name="alert" size=${16} /> ${t('chat.step_failed', { error: nice(r.error) })}</p>
    </article>`;
  }
  let card;
  try {
    card = CARDS[step.name] ? CARDS[step.name](r, ui) : { body: html`<${KeyValue} data=${r} />` };
  } catch (e) {
    card = { body: html`<${KeyValue} data=${r} />` };
  }
  const period = card.period || r.period;
  // The walkthrough rings the payment draft itself.
  return html`<article class="toolcard" data-tour=${step.name === 'prepare_payment' ? 'ask-draft' : undefined}>
    <header><h4>${card.title || toolText(step.name, 'title')}</h4>${period && (period.label || period.start) ? html`<small>${periodLabel(period)}</small>` : null}</header>
    ${card.body}
  </article>`;
}

/* ---------- answer pieces ---------- */

function inline(text) {
  return String(text).split(/(\*\*[^*]+\*\*)/g).map((p, i) => (
    /^\*\*[^*]+\*\*$/.test(p) ? html`<strong key=${i}>${p.slice(2, -2)}</strong>` : p
  ));
}

function AnswerText({ text }) {
  const lines = nice(text).split(/\n+/).map((s) => s.trim()).filter(Boolean);
  const blocks = [];
  let list = null;
  for (const line of lines) {
    const m = /^(?:[-*•]|\d+[.)])\s+(.*)$/.exec(line);
    if (m) {
      if (!list) { list = []; blocks.push(list); }
      list.push(m[1]);
    } else {
      list = null;
      blocks.push(line.replace(/^#+\s*/, ''));
    }
  }
  return blocks.map((b, i) => (Array.isArray(b)
    ? html`<ul key=${i}>${b.map((x, j) => html`<li key=${j}>${inline(x)}</li>`)}</ul>`
    : html`<p key=${i}>${inline(b)}</p>`));
}

function Trust({ answer, tour }) {
  const g = answer.grounding || {};
  const n = Number(g.numbers_checked) || 0;
  const bad = Array.isArray(g.unverified) ? g.unverified : [];
  if (g.ok === false || bad.length) {
    return html`<p class="trust trust--warn" role="note" data-tour=${tour}><${Icon} name="alert" size=${18} />
      <span><strong>${t('chat.trust_warn', { n: bad.length || 2 })}</strong>
      ${bad.length ? ' ' + t('chat.trust_untraced', { list: bad.join(', ') }) : ' ' + t('chat.trust_untraced_some')}</span></p>`;
  }
  let text;
  if (n > 0) text = t('chat.trust_checked', { n }) + (g.rewritten ? t('chat.trust_corrected') : '');
  else if (answer.mode === 'offline') text = t('chat.trust_offline');
  else text = t('chat.trust_none');
  return html`<p class="trust trust--ok" role="note" data-tour=${tour}><${Icon} name="shield" size=${18} /><span>${text}</span></p>`;
}

function argText(v) {
  if (v === null || v === undefined) return '';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

function Worked({ msg }) {
  const a = msg.answer || {};
  const steps = msg.steps.length ? msg.steps : (Array.isArray(a.tools_used) ? a.tools_used.map((x) => ({ name: x.name, args: x.arguments || {}, done: true, failed: x.ok === false })) : []);
  return html`<div class="worked">
    ${steps.length ? html`<ol>
      ${steps.map((s, i) => {
        const args = Object.entries(s.args || {}).filter(([k]) => k !== 'sql');
        const failed = s.failed || (s.result && s.result.error);
        return html`<li key=${i}>
          <p><strong>${toolText(s.name, 'done')}</strong> <code>${s.name}</code></p>
          ${args.length ? html`<dl class="args">${args.map(([k, v]) => html`<div key=${k}><dt>${words(k)}</dt><dd>${argText(v)}</dd></div>`)}</dl>` : html`<p class="muted">${t('chat.no_settings')}</p>`}
          ${s.args && s.args.sql ? html`<pre class="sql"><code>${s.args.sql}</code></pre>` : null}
          ${failed ? html`<p class="inline-error">${t('chat.step_error')}${s.result && s.result.error ? `: ${nice(s.result.error)}` : ''}.</p>` : null}
        </li>`;
      })}
    </ol>` : html`<p class="muted">${t('chat.worked_none')}</p>`}
    <p class="footnote">
      ${a.mode === 'offline'
        ? t('chat.offline_note')
        : t('chat.written_by', { model: modelName(a.model) })
          + (a.served_by ? t('chat.running_on', { host: hostName(a.served_by) }) : '')
          + (Number.isFinite(Number(a.seconds)) ? t('chat.in_seconds', { s: num(a.seconds) }) : '') + '.'}
      ${' '}${t('chat.rules_note')}
    </p>
  </div>`;
}

function Working({ steps }) {
  const running = steps.some((s) => !s.done);
  return html`<div class="working" role="status" aria-live="polite">
    <ul>
      ${steps.map((s, i) => html`<li key=${i} class=${s.done ? 'is-done' : ''}>
        ${s.done ? html`<${Icon} name="check" size=${16} />` : html`<span class="spinner" aria-hidden="true"></span>`}
        <span>${toolText(s.name, s.done ? 'done' : 'run')}${s.done ? '' : '…'}</span>
      </li>`)}
      ${!running ? html`<li><span class="spinner" aria-hidden="true"></span><span>${steps.length ? t('chat.working_words') : t('chat.working_read')}</span></li>` : null}
    </ul>
  </div>`;
}

function BotMessage({ msg, onRetry, latest }) {
  const a = msg.answer;
  // A bill that was read again after a failed check shows its last draft only.
  const lastDraft = msg.steps.map((s) => s.name).lastIndexOf('prepare_payment');
  const cards = msg.steps.filter((s, i) => s.done && s.result && (s.name !== 'prepare_payment' || i === lastDraft));
  return html`<li class="msg msg--bot" id=${'m-' + msg.id}>
    <span class="msg__who"><${Logo} size=${22} />${t('trainer.title')}</span>
    ${msg.pending ? html`<${Working} steps=${msg.steps} />` : null}
    ${a ? html`<div class="bubble bubble--bot" data-tour=${latest ? 'ask-answer' : undefined}><${AnswerText} text=${a.text} /></div>` : null}
    ${msg.error ? html`<div class="bubble bubble--error" role="alert">
      <p>${msg.error}</p>
      ${onRetry ? html`<button type="button" class="btn btn--small" onClick=${onRetry}><${Icon} name="refresh" size=${16} />${t('common.try_again')}</button>` : null}
    </div>` : null}
    ${a ? cards.map((s, i) => html`<${ToolCard} key=${i} step=${s} />`) : null}
    ${a ? html`<${Trust} answer=${a} tour=${latest ? 'ask-trust' : undefined} />` : null}
    ${a && a.mode === 'offline' ? html`<p class="mode-note"><${Icon} name="info" size=${14} />${t('chat.offline_note')}</p>` : null}
    ${a ? html`<${Disclosure} label=${t('chat.how')}><${Worked} msg=${msg} /><//>` : null}
  </li>`;
}

/* ---------- the screen ---------- */

let nextId = 1;

export function Chat() {
  const ui = useContext(UI);
  const id = ui.who.id;
  const [msgs, setMsgs] = useState([]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [photo, setPhoto] = useState(null);
  const [photoError, setPhotoError] = useState(null);
  const [preparing, setPreparing] = useState(false);
  const live = useRef({ msgs: [], busy: false, abort: null, seen: 0, follow: null });
  const scroller = useRef(null);
  const input = useRef(null);
  const picker = useRef(null);
  live.current.msgs = msgs;
  live.current.busy = busy;
  const health = ui.health || {};

  const onPhoto = (e) => {
    const file = e.target.files && e.target.files[0];
    e.target.value = '';
    if (!file) return;
    setPhotoError(null);
    readPhoto(file).then(setPhoto, (err) => setPhotoError((err && err.message) || t('chat.photo_error')));
  };

  const send = (raw, image) => {
    // A photo on its own asks the obvious question.
    const text = String(raw || '').trim().slice(0, 2000) || (image ? t('ask.q.photo') : '');
    if (!text) return;
    if (live.current.busy) { setDraft(text); return; }
    const outgoing = health.llm_configured === false ? forRouter(text) : text;
    const history = live.current.msgs
      .filter((m) => m.role === 'user' || (m.answer && m.answer.text))
      .map((m) => (m.role === 'user' ? { role: 'user', content: m.sent || m.text } : { role: 'assistant', content: String(m.answer.text).slice(0, 2000) }))
      .slice(-8);
    const userId = nextId++;
    const botId = nextId++;
    const patch = (fn) => setMsgs((list) => list.map((m) => (m.id === botId ? fn(m) : m)));
    setMsgs((list) => [...list, { id: userId, role: 'user', text, sent: outgoing, image: image || null }, { id: botId, role: 'bot', ask: text, image: image || null, pending: true, steps: [], answer: null, error: null }]);
    setDraft('');
    setPhoto(null);
    setPhotoError(null);
    setBusy(true);
    live.current.busy = true;
    live.current.follow = { userId, stage: 'sent' };
    if (input.current) input.current.style.height = '';
    const ctrl = new AbortController();
    live.current.abort = ctrl;

    streamChat(id, outgoing, history, (ev) => {
      if (!ev || typeof ev !== 'object') return;
      if (ev.type === 'tool_call') {
        patch((m) => ({ ...m, steps: [...m.steps, { name: ev.name, args: ev.arguments || {}, done: false }] }));
      } else if (ev.type === 'tool_result') {
        patch((m) => {
          const steps = m.steps.slice();
          const at = steps.findIndex((s) => !s.done && s.name === ev.name);
          const step = { name: ev.name, args: ev.arguments || {}, result: ev.result, done: true };
          if (at >= 0) steps[at] = step; else steps.push(step);
          return { ...m, steps };
        });
      } else if (ev.type === 'answer') {
        live.current.follow = { userId, stage: 'answered' };
        patch((m) => ({ ...m, pending: false, answer: ev }));
      } else if (ev.type === 'error') {
        patch((m) => ({ ...m, pending: false, error: nice(ev.message || t('chat.err_generic')) }));
      }
    }, ctrl.signal, image).then(
      () => patch((m) => (m.pending ? { ...m, pending: false, error: t('chat.err_cut') } : m)),
      (err) => patch((m) => ({ ...m, pending: false, error: err && err.name === 'AbortError' ? t('chat.err_stopped') : (err && err.message) || t('chat.err_generic') })),
    ).then(() => {
      if (live.current.abort === ctrl) {
        live.current.abort = null;
        live.current.busy = false;
        setBusy(false);
      }
    });
  };

  // The built-in sample photos: a made-up shelf price tag, or a made-up bill, for anyone without one at hand.
  const sendSample = (text, src = SAMPLE_PHOTO) => {
    if (live.current.busy) return;
    setPhotoError(null);
    setPreparing(true);
    fetch(src)
      .then((r) => (r.ok ? r.blob() : Promise.reject(new Error(t('chat.photo_error')))))
      .then((blob) => readPhoto(blob))
      .then((image) => send(text, image), (err) => setPhotoError((err && err.message) || t('chat.photo_error')))
      .then(() => setPreparing(false));
  };

  // A question handed over from another screen ("Ask about this"), or from the tour.
  useEffect(() => {
    const q = ui.question;
    if (q && q.n !== live.current.seen) {
      live.current.seen = q.n;
      if (q.photo === 'sample') sendSample(q.text);
      else if (q.photo === 'bill') sendSample(q.text || t('ask.q.bill'), SAMPLE_BILL);
      else send(q.text);
    }
  }, [ui.question]);

  // Stop the stream if the screen goes away (for example when switching customer).
  useEffect(() => () => { if (live.current.abort) live.current.abort.abort(); }, []);

  // Keep the newest part of the conversation in view.
  useEffect(() => {
    const el = scroller.current;
    const f = live.current.follow;
    if (!el || !f) return;
    if (f.stage === 'answered') {
      const q = el.querySelector('#m-' + f.userId);
      if (q) el.scrollTo({ top: Math.max(0, q.offsetTop - 8), behavior: reducedMotion() ? 'auto' : 'smooth' });
      live.current.follow = null;
    } else {
      el.scrollTo({ top: el.scrollHeight, behavior: 'auto' });
    }
  }, [msgs]);

  const stop = () => { if (live.current.abort) live.current.abort.abort(); };
  const reset = () => { stop(); setMsgs([]); live.current.follow = null; };
  const onSubmit = (e) => { e.preventDefault(); send(draft, photo); };
  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(draft, photo); }
  };
  const onInput = (e) => {
    setDraft(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  };
  const empty = msgs.length === 0;
  // The newest answer carries the tour anchors. While a question is on its way there is none,
  // so a highlight waits for the new answer instead of sitting on the old one.
  let latest = null;
  for (const m of msgs) if (m.role === 'bot') latest = m.answer ? m.id : null;
  if (preparing) latest = null;

  return html`<div class="chat">
    <div class="chat__scroll" ref=${scroller}>
      ${empty ? html`<div class="chat__intro">
        <span class="chat__mark" aria-hidden="true"><${Icon} name="whistle" size=${30} stroke=${1.400} /></span>
        <h2>${t('chat.intro_title')}</h2>
        <p>${t('chat.intro_text')}</p>
        <button type="button" class="photocta" onClick=${() => picker.current && picker.current.click()}>
          <span class="photocta__icon" aria-hidden="true"><${Icon} name="camera" size=${26} /></span>
          <span class="photocta__text"><strong>${t('chat.photo_cta')}</strong><span>${t('chat.photo_cta_sub')}</span></span>
          <${Icon} name="right" size=${20} />
        </button>
        <button type="button" class="photosample" onClick=${() => sendSample('')}>
          <img src=${SAMPLE_PHOTO} alt="" width="44" height="33" />
          <span>${t('chat.photo_sample')}</span>
        </button>
        <button type="button" class="photosample" onClick=${() => sendSample(t('ask.q.bill'), SAMPLE_BILL)}>
          <img src=${SAMPLE_BILL} alt="" width="44" height="33" />
          <span>${t('chat.bill_sample')}</span>
        </button>
        <ul class="suggest">
          ${SUGGESTIONS.map((k) => html`<li key=${k}><button type="button" onClick=${() => send(t(k))}><span>${t(k)}</span><${Icon} name="right" size=${18} /></button></li>`)}
        </ul>
        <p class="mode-note mode-note--center"><${Icon} name=${health.llm_configured ? 'spark' : 'info'} size=${14} />
          ${health.llm_configured ? t('chat.mode_llm') : t('chat.mode_offline')}
        </p>
      </div>` : html`<ol class="msgs" aria-live="polite" aria-relevant="additions">
        ${msgs.map((m) => (m.role === 'user'
          ? html`<li class="msg msg--user" id=${'m-' + m.id} key=${m.id}>
              ${m.image ? html`<img class="msg__photo" src=${m.image} alt=${t('chat.photo_alt_sent')} />` : null}
              <div class="bubble bubble--user">${m.text}</div>
            </li>`
          : html`<${BotMessage} key=${m.id} msg=${m} latest=${m.id === latest} onRetry=${m.error && !busy ? () => send(m.ask, m.image) : null} />`))}
      </ol>`}
    </div>
    <div class="chat__dock">
      ${!empty ? html`<div class="chips chips--dock" role="group" aria-label=${t('chat.suggested')}>
        <${Chip} onClick=${reset} label=${t('chat.new_chat_aria')}><${Icon} name="plus" size=${14} />${t('chat.new_chat')}<//>
        ${SUGGESTIONS.map((k) => html`<${Chip} key=${k} onClick=${() => send(t(k))}>${t(k)}<//>`)}
      </div>` : null}
      ${photo ? html`<div class="attached">
        <img src=${photo} alt=${t('chat.photo_alt_send')} />
        <p><strong>${t('chat.photo_attached')}</strong><span>${t('chat.photo_hint')}</span>
          <button type="button" class="attached__bill" disabled=${busy} onClick=${() => send(t('ask.q.bill'), photo)}>${t('chat.photo_bill')}</button></p>
        <button type="button" class="iconbtn" aria-label=${t('chat.photo_remove')} onClick=${() => setPhoto(null)}><${Icon} name="close" size=${18} /></button>
      </div>` : null}
      ${photoError ? html`<p class="attached attached--error" role="alert">${photoError}</p>` : null}
      <form class="composer" onSubmit=${onSubmit}>
        <input ref=${picker} class="sr" type="file" accept="image/*" tabindex="-1" aria-hidden="true" onChange=${onPhoto} />
        <button type="button" class="attach" data-tour="ask-camera" disabled=${busy} onClick=${() => picker.current && picker.current.click()}
          aria-label=${t('chat.camera_aria')}><${Icon} name="camera" size=${24} /></button>
        <label class="sr" for="ask">${t('chat.input_label')}</label>
        <textarea id="ask" ref=${input} rows="1" maxlength="2000" placeholder=${photo ? t('ask.q.photo') : t('chat.placeholder')} enterkeyhint="send"
          autocomplete="off" value=${draft} onInput=${onInput} onKeyDown=${onKey}></textarea>
        ${busy
          ? html`<button type="button" class="send send--stop" aria-label=${t('chat.stop_aria')} onClick=${stop}><span class="stop" aria-hidden="true"></span></button>`
          : html`<button type="submit" class="send" aria-label=${t('chat.send_aria')} disabled=${!draft.trim() && !photo}><${Icon} name="send" /></button>`}
      </form>
    </div>
  </div>`;
}
