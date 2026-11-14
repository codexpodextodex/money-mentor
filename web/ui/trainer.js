// The money trainer's landing page: safe to spend, what stands out, the payday plan, the tools,
// the three baskets, month by month, safe to save and the spender type.
import {
  html, useState, useContext, useApi, useDebounced, cust,
  eur, pct, num, fmtDate, nice, words, clamp, BASKETS, basketOf, t, tv, has, periodLabel, useLang,
} from './lib.js';
import {
  UI, Icon, Amount, Load, Skeleton, ErrorBox, Empty, Disclosure, Stat, Chip, BasketIcon,
  BasketBar, BasketLegend, BarList, Waterfall, BalanceCheck, Columns, PeerBars, RulesBody, catName, subName,
} from './parts.js';
import { SAFE_STATUS } from './host.js';
import { PlanEntry, HeadsUpNotice } from './plan.js';

const nDays = (n) => t('n_days', { n: Number(n), count: num(n, 0) });

/* ---------- safe to spend ---------- */

function SafeCard({ safe, stale, goal, onGoal, error }) {
  const ui = useContext(UI);
  const week = safe.this_week || {};
  const pay = safe.pay_period || {};
  const st = SAFE_STATUS[safe.status] || { tone: 'muted', icon: 'info' };
  const left = Number(week.days_left);
  const lines = Array.isArray(safe.budget) ? safe.budget : [];
  const last = lines.length ? Number(lines[lines.length - 1].amount) : NaN;
  const over = safe.status === 'over_budget' && last < 0 ? Math.abs(last) : 0;
  const usual = Number(week.your_usual_spending);
  const value = goal ?? Number(safe.savings_goal_pct ?? 10);
  const saving = lines.find((l) => /^savings goal/i.test(String(l.label || '')));
  const hasDays = Number.isFinite(left) && left > 0;
  const statusKey = SAFE_STATUS[safe.status] ? `status.${safe.status}.text` : null;

  return html`<section class="card thero" data-tour="trainer-hero" aria-labelledby="thero-h">
    <div class=${stale ? 'is-stale' : ''}>
      <div class="thero__top">
        <h2 id="thero-h" class="thero__label">${t('home.safe_label')}</h2>
        <span class=${'pill pill--' + st.tone}><${Icon} name=${st.icon} size=${14} />${st.key ? t(st.key) : words(safe.status)}</span>
      </div>
      <p class=${'thero__num' + (st.tone === 'bad' && !(Number(week.safe_to_spend) > 0) ? ' is-zero' : '')}><${Amount} value=${week.safe_to_spend} mode="whole" /></p>
      <p class="thero__sub">
        ${hasDays ? t('trainer.sub_days', { days: nDays(left) }) : t('trainer.sub_week')}${week.until ? t('trainer.sub_until', { date: fmtDate(week.until, { weekday: true }) }) : ''}
      </p>
      <p class="thero__text">
        ${statusKey ? t(statusKey) : ''}
        ${over ? ' ' + t('trainer.over_by', { amount: eur(over) }) : ''}
        ${Number.isFinite(usual) && hasDays ? ' ' + t('trainer.usual', { amount: eur(usual), days: nDays(left) }) : ''}
        ${safe.limited_by === 'balance' ? ' ' + t('trainer.limited_balance') : ''}
      </p>
      <dl class="thero__stats">
        <div><dt>${t('trainer.a_day')}</dt><dd>${eur(safe.safe_per_day)}</dd></div>
        <div><dt>${t('trainer.until_payday')}</dt><dd>${eur(safe.safe_to_spend_until_payday, 'whole')}</dd></div>
        <div><dt>${t('trainer.next_payday')}</dt><dd>${fmtDate(pay.next_payday)}${Number.isFinite(Number(pay.payday_in_days ?? pay.days_left)) ? html`<small>${t('trainer.in_days', { days: nDays(pay.payday_in_days ?? pay.days_left) })}</small>` : null}</dd></div>
      </dl>
    </div>
    <div class="goal">
      <div class="goal__head">
        <label for="goal">${t('trainer.goal')}</label>
        <output for="goal" class=${stale ? 'is-stale' : ''}>${t('trainer.goal_value', { pct: num(value, 0) })}${saving ? html`<small> · ${t('trainer.goal_period', { amount: eur(Math.abs(Number(saving.amount)), 'whole') })}</small>` : null}</output>
      </div>
      <input id="goal" type="range" min="0" max="30" step="1" value=${value} style=${`--fill:${(clamp(value, 0, 30) / 30) * 100}%`}
        aria-valuetext=${t('trainer.goal_value', { pct: value })}
        onInput=${(e) => onGoal(Number(e.target.value))} />
      <div class="goal__scale" aria-hidden="true"><span>0 %</span><span>${t('trainer.goal_hint')}</span><span>30 %</span></div>
      ${error ? html`<p class="inline-error" role="alert">${t('trainer.goal_error', { message: error.message })}</p>` : null}
    </div>
    <${Disclosure} label=${t('trainer.how')}>
      <p class="sub">${t('trainer.how_text')}</p>
      <div class=${stale ? 'is-stale' : ''}><${Waterfall} lines=${safe.budget} /></div>
      <h3 class="h3">${t('trainer.check_title')}</h3>
      <p class="sub">${t('trainer.check_text')}${safe.limited_by ? ' ' + t(safe.limited_by === 'balance' ? 'trainer.check_now_balance' : 'trainer.check_now_budget') : ''}</p>
      <${BalanceCheck} check=${safe.balance_check} />
    <//>
    <button type="button" class="textlink thero__ask" onClick=${() => ui.ask(t('ask.q.safe'))}><${Icon} name="chat" size=${18} />${t('trainer.ask_this')}</button>
  </section>`;
}

/* ---------- worth a look ---------- */

const NOTICE_TONE = { warning: 'warn', positive: 'good' };

function NoticesSection({ id }) {
  const ui = useContext(UI);
  const req = useApi(cust(id, '/notices'));
  const list = req.data && Array.isArray(req.data.notices) ? req.data.notices : [];
  // Nothing to say is a fine state: one calm line instead of an empty card.
  if (req.error) return null;
  return html`<section aria-labelledby="notice-h" data-tour="trainer-notices">
    <h2 id="notice-h" class="sect">${t('trainer.notices')}</h2>
    <div class="group">
      ${!req.data ? html`<div class="group__pad"><${Skeleton} rows=${3} /></div>` : null}
      ${req.data && !list.length ? html`<div class="row"><span class="row__icon"><${Icon} name="check" size=${28} stroke=${1.400} /></span>
        <span class="row__text"><span class="row__title">${t('home.notice_none')}</span><span class="row__sub">${t('trainer.notices_none')}</span></span></div>` : null}
      ${list.map((n) => {
        // The heads-up is said from its numbers, and opens the weeks ahead instead of the chat.
        if (n.kind === 'heads_up' && n.data) return html`<${HeadsUpNotice} key=${n.kind} notice=${n} />`;
        const b = basketOf(n.basket);
        const tone = NOTICE_TONE[n.tone] || 'plain';
        return html`<button type="button" key=${n.kind} class=${`row row--tap notice notice--${tone}${b ? ` b-${b.id}` : ''}`} onClick=${() => ui.ask(nice(n.ask))}>
          <span class="notice__mark" aria-hidden="true">
            ${n.tone === 'warning' ? html`<${Icon} name="alert" size=${20} />` : n.tone === 'positive' ? html`<${Icon} name="check" size=${20} />` : b ? html`<${BasketIcon} basket=${b.id} size=${20} />` : html`<${Icon} name="info" size=${20} />`}
          </span>
          <span class="row__text"><span class="row__title">${nice(n.title)}</span><span class="row__sub">${nice(n.detail)}</span></span>
          <span class="row__chev"><${Icon} name="right" size=${20} /></span>
        </button>`;
      })}
    </div>
    ${list.length ? html`<p class="hint">${t('trainer.notices_hint')}</p>` : null}
  </section>`;
}

/* ---------- the tools ---------- */

const TOOLS = [
  ['ask', 'chat', 'tile.ask'],
  ['replay', 'replay', 'tile.replay'],
  ['find', 'search', 'tile.find'],
  ['explore', 'explore', 'tile.explore'],
  ['loan', 'loan', 'tile.loan'],
  ['quiz', 'quiz', 'tile.quiz'],
];

function Tools() {
  const ui = useContext(UI);
  return html`<nav class="tiles tiles--3" aria-label=${t('trainer.tools')}>
    ${TOOLS.map(([route, icon, key]) => html`<button type="button" class="tile" key=${route}
      data-tour=${route === 'quiz' ? 'trainer-quiz' : undefined} onClick=${() => ui.go(route)}>
      <${Icon} name=${icon} size=${28} stroke=${1.400} /><span>${t(key)}</span>
    </button>`)}
  </nav>`;
}

/* ---------- profile ---------- */

const TRAITS = {
  share_of_income_left_over_pct: (v) => [pct(v), t('trait.left_over')],
  essentials_share_of_income_pct: (v) => [pct(v), t('trait.essentials')],
  small_everyday_purchases_per_week: (v) => [num(v), t('trait.small_week')],
  small_everyday_purchases_monthly_total: (v) => [eur(v), t('trait.small_month')],
  big_purchases_share_of_everyday_pct: (v) => [pct(v), t('trait.big')],
  weekend_share_of_everyday_pct: (v) => [pct(v), t('trait.weekend')],
  restaurants_share_of_everyday_pct: (v) => [pct(v), t('trait.restaurants')],
  days_below_zero_balance: (v) => [num(v, 0), t('trait.below_zero')],
  months_spent_more_than_earned: (v) => [num(v, 0), t('trait.months_over')],
  invests_regularly: (v) => [v ? t('common.yes') : t('common.no'), t('trait.invests')],
};

const PEER_GROUPS = ['age', 'area', 'age_and_area', 'all'];

function PeerSection({ id }) {
  const [group, setGroup] = useState('age');
  const req = useApi(cust(id, `/benchmark?peer_group=${group}`));
  return html`<section>
    <h3 class="h3">${t('profile.compare')}</h3>
    <div class="chips" role="group" aria-label=${t('profile.compare_with')}>
      ${PEER_GROUPS.map((key) => html`<${Chip} key=${key} active=${group === key} onClick=${() => setGroup(key)}>${t('peer.' + key)}<//>`)}
    </div>
    <${Load} req=${req} rows=${5}>${(d) => html`
      <p class="sub">${t('profile.compared', { who: nice(d.compared_with) })}${d.based_on ? ` ${t('profile.over', { period: periodLabel(d.based_on) })}` : ''}</p>
      <${PeerBars} comparisons=${d.comparisons} />`}<//>
  </section>`;
}

const typeText = (d, field) => {
  const key = `type.${d.spender_type}.${field}`;
  return has(key) ? t(key) : nice(d[field]);
};
const typeName = (d) => (d.spender_type ? tv('type', d.spender_type) : t('profile.no_type'));

function ProfileBody({ data, id }) {
  useLang();
  const traits = data.traits && typeof data.traits === 'object' ? Object.entries(data.traits) : [];
  const cats = Array.isArray(data.top_everyday_categories) ? data.top_everyday_categories : [];
  return html`<div class="profile">
    <p class="eyebrow">${t('profile.eyebrow')}</p>
    <h3 class="profile__type">${typeName(data)}</h3>
    <p class="lead">${typeText(data, 'summary')}</p>
    ${data.why ? html`<p class="sub">${t('profile.why', { why: typeText(data, 'why') })}</p>` : null}
    ${data.tip ? html`<div class="tip"><strong>${t('profile.next')}</strong><p>${typeText(data, 'tip')}</p></div>` : null}
    ${traits.length ? html`<h3 class="h3">${t('profile.habits')}</h3>
      <ul class="traits">
        ${traits.map(([k, v]) => {
          const [value, label] = TRAITS[k] ? TRAITS[k](v) : [typeof v === 'number' ? num(v) : String(v), words(k).toLowerCase()];
          return html`<li key=${k}><strong>${value}</strong><span>${label}</span></li>`;
        })}
      </ul>` : null}
    <h3 class="h3">${t('profile.everyday_goes')}</h3>
    ${cats.length
      ? html`<${BarList} tone="b-everyday" rows=${cats.map((c) => ({ key: c.category, label: catName(c.category), value: c.monthly, text: t('unit.per_month', { amount: eur(c.monthly) }) }))} />`
      : html`<${Empty} icon="b_everyday" title=${t('profile.no_everyday')}>${t('profile.no_everyday_text')}<//>`}
    <${PeerSection} id=${id} />
    ${data.based_on ? html`<p class="footnote">${t('profile.based_on', { period: periodLabel(data.based_on) })}</p>` : null}
  </div>`;
}

function ProfileCard({ id }) {
  const ui = useContext(UI);
  const req = useApi(cust(id, '/profile'));
  return html`<section aria-labelledby="profile-h">
    <h2 id="profile-h" class="sect">${t('profile.eyebrow')}</h2>
    <div class="card card--profile">
      <${Load} req=${req} rows=${3}>${(d) => html`
        <h3 class="profile__type">${typeName(d)}</h3>
        <p>${typeText(d, 'summary')}</p>
        <button type="button" class="textlink" onClick=${() => ui.openSheet({ title: t('profile.sheet'), body: html`<${ProfileBody} data=${d} id=${id} />` })}>
          ${t('profile.see_why')}<${Icon} name="right" size=${18} />
        </button>`}<//>
    </div>
  </section>`;
}

/* ---------- money at another bank (the multi-bank view) ---------- */

function OtherBankCard({ other }) {
  const ui = useContext(UI);
  if (!other) return null;
  return html`<section class="card card--other" aria-labelledby="other-h">
    <p class="eyebrow">${t('other.eyebrow')}</p>
    <h2 id="other-h" class="h2">${t('other.title', { pct: pct(other.share_of_income_pct) })}</h2>
    <p class="sub">${t('other.text', { amount: eur(other.monthly_transfer_to_other_accounts, 'whole') })}</p>
    <p class="callout">${t('other.psd2')}</p>
    <button type="button" class="textlink" onClick=${() => ui.ask(t('ask.q.unseen'))}><${Icon} name="chat" size=${18} />${t('other.ask')}</button>
  </section>`;
}

/* ---------- the three baskets ---------- */

function BasketCard({ row, slip, largest }) {
  const b = basketOf(row.basket) || basketOf(row.name);
  if (!b) return null;
  const top = Array.isArray(row.top) ? row.top : [];
  const total = Number(row.total) || 0;
  return html`<article class=${'card basket b-' + b.id} aria-label=${b.name}>
    <header class="basket__head">
      <span class="basket__icon" aria-hidden="true"><${BasketIcon} basket=${b.id} size=${24} /></span>
      <div><h3>${b.name}</h3><p>${b.meaning}</p></div>
    </header>
    ${total > 0 ? html`
      <div class="stats">
        <${Stat} label=${t('basket.a_month')} value=${eur(row.monthly_average ?? total, 'whole')} />
        <${Stat} label=${t('basket.of_spending')} value=${pct(row.share_of_spending_pct)} />
        <${Stat} label=${t('basket.of_income')} value=${pct(row.share_of_income_pct)} />
      </div>
      <${BarList} tone=${'b-' + b.id} rows=${top.map((x) => ({
        key: x.subcategory, label: subName(x.subcategory), value: x.total, text: eur(x.total),
        note: t('n_payments', { n: Number(x.transactions), count: num(x.transactions, 0) }),
      }))} />`
      : html`<${Empty} icon=${'b_' + b.id} title=${t('basket.none')}>
          ${b.id === 'unexpected' ? t('basket.none_unexpected') : t('basket.none_text')}
        <//>`}
    ${b.id === 'unexpected' && Array.isArray(largest) && largest.length ? html`
      <p class="basket__note">${t('basket.largest', { list: largest.slice(0, 2).map((u) => t('basket.largest_item', { what: subName(u.what), amount: eur(u.amount), date: fmtDate(u.date) })).join(', ') })}</p>` : null}
    ${b.id === 'everyday' && slip ? html`<div class="slip">
      <strong>${t('slip.title')}</strong>
      ${Number(slip.count) > 0
        ? html`<p>${t('slip.text', { n: Number(slip.count), count: num(slip.count, 0), under: eur(slip.under_eur, 'whole'), total: eur(slip.total) })}${Number(slip.per_week) > 0 ? ', ' + t('slip.week', { count: num(slip.per_week) }) : ''}. ${t('slip.tail')}</p>`
        : html`<p>${t('slip.none', { under: eur(slip.under_eur, 'whole') })}</p>`}
    </div>` : null}
  </article>`;
}

function BasketsSection({ id }) {
  const ui = useContext(UI);
  const req = useApi(cust(id, '/baskets?period=last_3_months'));
  const openRules = () => ui.openSheet({ title: t('baskets.why'), body: html`<${RulesBody} />` });
  return html`<section aria-labelledby="baskets-h">
    <h2 id="baskets-h" class="sect">${t('baskets.title')}</h2>
    <div class="card" data-tour="trainer-baskets">
      <${Load} req=${req} rows=${4} tall=${true}>${(d) => html`
        <p class="sub sub--first">${t('baskets.sub')}${d.period ? ` ${t('baskets.period', { period: periodLabel(d.period) })}` : ''}</p>
        <dl class="trio">
          <div><dt>${t('cols.money_in')}</dt><dd>${eur(d.income, 'whole')}</dd></div>
          <div><dt>${t('cols.spent')}</dt><dd>${eur(d.spending, 'whole')}</dd></div>
          <div><dt>${t('baskets.left')}</dt><dd class=${Number(d.left_over) < 0 ? 'is-bad' : ''}>${eur(d.left_over, 'whole')}</dd></div>
        </dl>
        <${BasketBar} parts=${d.baskets} />
        <${BasketLegend} parts=${d.baskets} perMonth=${true} />
        ${Number(d.moved_to_savings) > 0 || Number(d.transferred_to_other_accounts) > 0 ? html`<p class="footnote">
          ${t('baskets.not_counted', { list: [Number(d.moved_to_savings) > 0 ? t('baskets.to_savings', { amount: eur(d.moved_to_savings, 'whole') }) : null,
            Number(d.transferred_to_other_accounts) > 0 ? t('baskets.to_other', { amount: eur(d.transferred_to_other_accounts, 'whole') }) : null].filter(Boolean).join(t('common.and')) })}</p>` : null}
        <div class="card__actions">
          <button type="button" class="textlink" onClick=${openRules}><${Icon} name="info" size=${18} />${t('baskets.why')}</button>
          <button type="button" class="textlink" onClick=${() => ui.ask(t('ask.q.where'))}><${Icon} name="chat" size=${18} />${t('baskets.ask')}</button>
        </div>`}<//>
    </div>
    ${req.data && Array.isArray(req.data.baskets) ? req.data.baskets.map((row) => html`
      <${BasketCard} key=${row.basket} row=${row} slip=${req.data.small_everyday_purchases} largest=${req.data.largest_unexpected} />`) : null}
  </section>`;
}

/* ---------- month by month ---------- */

function CashflowSection({ id }) {
  const req = useApi(cust(id, '/cashflow?months=6'));
  return html`<section aria-labelledby="cash-h">
    <h2 id="cash-h" class="sect">${t('cash.title')}</h2>
    <div class="card">
      <${Load} req=${req} rows=${3} tall=${true}>${(d) => {
        const months = Array.isArray(d.months) ? d.months : [];
        const over = Number(d.months_spent_more_than_earned);
        const avg = d.average || {};
        return html`
          <p class="sub sub--first">${d.period ? `${periodLabel(d.period)}. ` : ''}${t('cash.tap')}</p>
          ${months.length && Number.isFinite(over) ? html`<p class=${'callout ' + (over > 0 ? 'callout--warn' : 'callout--good')}>
            ${over > 0 ? t('cash.over', { n: num(over, 0), of: months.length }) : t('cash.under', { of: months.length })}
          </p>` : null}
          <${Columns} months=${months} />
          ${months.length ? html`<p class="footnote">${t('cash.typical', { income: eur(avg.income, 'whole'), spending: eur(avg.spending, 'whole') })}</p>` : null}`;
      }}<//>
    </div>
  </section>`;
}

/* ---------- safe to save ---------- */

function SaveCard({ save, stale }) {
  if (!save) return null;
  const now = Number(save.now) || 0;
  const cover = Number(save.balance_covers_months_of_spending);
  const cushion = Number(save.cushion_months) || 3;
  const idle = Number(save.idle_above_cushion) || 0;
  const fill = Number.isFinite(cover) ? clamp((cover / cushion) * 100, 0, 100) : 0;
  return html`<section aria-labelledby="save-h">
    <h2 class="sect" id="save-h">${t('save.title')}</h2>
    <div class=${'card card--save' + (stale ? ' is-stale' : '')}>
      <p class="big"><${Amount} value=${now} mode="whole" /></p>
      <p class="sub">${now > 0 ? t('save.can') : t('save.cannot')}</p>
      ${save.why ? html`<p class="footnote">${nice(save.why)}</p>` : null}
      ${Number.isFinite(cover) ? html`<div class="cushion">
        <div class="cushion__head"><span>${t('save.buffer')}</span><strong>${t('save.months', { have: num(cover), want: num(cushion, 0) })}</strong></div>
        <div class="meter" role="img" aria-label=${t('save.covers_short', { have: num(cover), want: cushion })}>
          <span class="meter__fill" style=${`width:${fill}%`}></span>
        </div>
        <p class="sub">${cover >= cushion ? t('save.covers_enough', { have: num(cover), want: cushion }) : t('save.covers_short', { have: num(cover), want: cushion })}</p>
      </div>` : null}
      ${idle > 0 ? html`<p class="callout callout--good">${t('save.idle', { amount: eur(idle, 'whole'), want: cushion })}</p>` : null}
    </div>
  </section>`;
}

/* ---------- the screen ---------- */

export function Trainer() {
  const ui = useContext(UI);
  const id = ui.who.id;
  const overview = useApi(cust(id, '/overview'));
  const [goal, setGoal] = useState(null);
  const goalQ = useDebounced(goal, 280);
  const tuned = useApi(goalQ === null ? null : cust(id, `/safe-to-spend?savings_goal_pct=${goalQ}`));

  if (overview.error && !overview.data) {
    return html`<div class="stack"><${ErrorBox} title=${t('trainer.error')} error=${overview.error} onRetry=${overview.reload} /><${Tools} /></div>`;
  }
  if (!overview.data) {
    return html`<div class="stack">
      <div class="card"><${Skeleton} rows=${3} tall=${true} /></div>
      <div class="card"><${Skeleton} rows=${3} /></div>
      <div class="card"><${Skeleton} rows=${4} tall=${true} /></div>
    </div>`;
  }

  const o = overview.data;
  const safe = (goalQ !== null && tuned.data) || o.safe_to_spend || null;
  const stale = goal !== null && (goal !== goalQ || tuned.loading);

  return html`<div class="stack">
    ${safe
      ? html`<${SafeCard} safe=${safe} stale=${stale} goal=${goal} onGoal=${setGoal} error=${goalQ !== null ? tuned.error : null} />`
      : html`<div class="card" data-tour="trainer-hero"><${Empty} icon="gauge" title=${t('trainer.no_safe_title')}>${t('trainer.no_safe_text')}<//></div>`}
    <${NoticesSection} id=${id} />
    <${PlanEntry} id=${id} />
    <${Tools} />
    <${OtherBankCard} other=${o.other_accounts} />
    <${BasketsSection} id=${id} />
    <${CashflowSection} id=${id} />
    ${safe ? html`<${SaveCard} save=${safe.safe_to_save} stale=${stale} />` : null}
    <${ProfileCard} id=${id} />
    <p class="endnote">${t('trainer.endnote')}</p>
  </div>`;
}
