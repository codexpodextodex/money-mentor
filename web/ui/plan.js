// The payday plan: the next salary split into essentials, a buffer, savings and everyday
// spending, ready to accept. And the weeks ahead: the balance projected day by day.
// Also the pieces other screens borrow: the entry card on the trainer, the heads-up notice,
// and the compact cards the chat shows for the two tools.
import {
  html, useState, useEffect, useRef, useContext, useApi, useDebounced, cust, store,
  eur, eurShort, num, pct, fmtDate, parseDate, nice, clamp, BASKETS, t, tv, has,
} from './lib.js';
import { UI, Icon, Amount, Skeleton, ErrorBox, Disclosure, BarList } from './parts.js';

const DEFAULT_GOAL = 10;
const GOAL_MAX = 30;

/* ---------- words ---------- */

// A date ends in a full stop in Finnish and Swedish ("14.10."): a sentence that ends with one keeps a single stop.
const tidy = (s) => String(s).replace(/\.\.(?=\s|$)/g, '.');
const nDays = (n) => t('n_days', { n: Number(n), count: num(n, 0) });
const billName = (what) => tv('bill', what);

/** "in 15 days" (lead "plan.in") or "Payday in 15 days" (lead "plan.when"). */
function when(inDays, lead) {
  const n = Number(inDays);
  if (!Number.isFinite(n)) return '';
  if (n <= 0) return t(`${lead}_today`);
  if (n === 1) return t(`${lead}_tomorrow`);
  return t(`${lead}_days`, { count: num(n, 0) });
}

/* ---------- the accepted plan: per customer and pay period, on this device only ---------- */

const ACCEPT_KEY = (id) => `money-mentor.payday-plan.${id}`;
const acceptMemory = new Map(); // storage can be blocked: the choice still holds for this visit
const acceptListeners = new Set();

function readAccepted(id) {
  const v = acceptMemory.has(id) ? acceptMemory.get(id) : store.get(ACCEPT_KEY(id));
  return v && typeof v === 'object' && typeof v.from === 'string' && typeof v.to === 'string' ? v : null;
}

function writeAccepted(id, value) {
  acceptMemory.set(id, value || null);
  store.set(ACCEPT_KEY(id), value || null);
  acceptListeners.forEach((fn) => fn(id));
}

/** The accepted plan, kept in step between the trainer's card and the plan screen. */
function useAccepted(id) {
  const [value, setValue] = useState(() => readAccepted(id));
  useEffect(() => {
    setValue(readAccepted(id));
    const fn = (changed) => { if (changed === id) setValue(readAccepted(id)); };
    acceptListeners.add(fn);
    return () => acceptListeners.delete(fn);
  }, [id]);
  return [value, (next) => writeAccepted(id, next)];
}

const acceptedFor = (accepted, plan) => Boolean(accepted && plan && plan.pay_period
  && accepted.from === plan.pay_period.from && accepted.to === plan.pay_period.to);
const goalOf = (accepted) => (accepted && Number.isFinite(Number(accepted.goal)) ? clamp(Math.round(Number(accepted.goal)), 0, GOAL_MAX) : DEFAULT_GOAL);

/* ---------- the split ---------- */

const SPLIT_TONE = { essentials: 'b-essentials', transfer: 't-ink', unexpected: 'b-unexpected', savings: 't-save', everyday: 'b-everyday' };
const splitRows = (plan) => (Array.isArray(plan && plan.split) ? plan.split.filter((r) => r && typeof r.key === 'string') : []);
const rowOf = (plan, key) => splitRows(plan).find((r) => r.key === key) || null;
const some = (v) => Number(v) > 0.004;

function splitName(row) {
  if (BASKETS[row.key]) return BASKETS[row.key].name;
  if (has(`plan.row.${row.key}`)) return t(`plan.row.${row.key}`);
  return nice(row.label || row.key);
}

function splitSub(row) {
  const amount = Number(row.amount) || 0;
  if (row.key === 'essentials') return t('plan.sub.essentials');
  if (row.key === 'transfer') return t('plan.sub.transfer');
  if (row.key === 'unexpected') {
    if (row.kept_in_full !== false) return t('plan.sub.unexpected_full');
    return some(amount)
      ? t('plan.sub.unexpected_cut', { usual: eur(row.usual, 'whole'), amount: eur(amount, 'whole') })
      : t('plan.sub.unexpected_none', { usual: eur(row.usual, 'whole') });
  }
  if (row.key === 'savings') {
    const goal = Number(row.goal_pct) || 0;
    const auto = Number(row.already_automatic) || 0;
    if (!some(goal) && !some(amount)) return t('plan.sub.savings_off');
    if (row.goal_kept === false) {
      return some(amount) ? t('plan.sub.savings_cut', { pct: pct(goal), amount: eur(amount, 'whole') }) : t('plan.sub.savings_none', { pct: pct(goal) });
    }
    // A regular investment deposit that is already larger than the goal is the whole line.
    if (some(auto) && auto >= amount - 0.01) return t('plan.sub.savings_auto_all', { pct: pct(goal) });
    const kept = row.to ? t('plan.sub.savings_kept', { pct: pct(goal), to: row.to }) : t('trainer.goal_value', { pct: num(goal, 0) });
    return some(auto) ? `${kept}. ${t('plan.sub.savings_auto', { amount: eur(auto, 'whole') })}` : kept;
  }
  if (row.key === 'everyday') {
    return some(amount) ? t('plan.sub.everyday', { week: eur(row.a_week, 'whole'), day: eur(row.a_day) }) : t('plan.sub.everyday_none');
  }
  return row.note ? nice(row.note) : '';
}

/** One whole salary, split in order. When the essentials alone are more than the salary, a line marks where it ends. */
export function SplitBar({ plan }) {
  const rows = splitRows(plan).filter((r) => some(r.amount));
  const sum = rows.reduce((a, r) => a + Number(r.amount), 0);
  const salary = Number(plan.payday && plan.payday.expected_salary) || 0;
  if (!(sum > 0)) return html`<div class="seg seg--empty" role="img" aria-label=${t('plan.bar_empty')}><span>${t('plan.bar_empty')}</span></div>`;
  const over = plan.fits === false && salary > 0 && sum > salary + 0.5;
  const aria = t('plan.bar_aria', { list: rows.map((r) => `${splitName(r)} ${eur(r.amount, 'whole')}`).join(', ') });
  return html`<div class=${'seg splitbar' + (over ? ' splitbar--over' : '')} role="img" aria-label=${over ? `${aria}. ${t('plan.bar_mark')}` : aria}>
    ${rows.map((r) => {
      const share = (Number(r.amount) / sum) * 100;
      const said = Number.isFinite(Number(r.share_of_salary_pct)) ? Number(r.share_of_salary_pct) : share;
      return html`<div class=${'seg__part ' + (SPLIT_TONE[r.key] || 't-ink')} style=${`flex:${share.toFixed(2)} 1 0%`} key=${r.key}>
        ${share >= 13 ? html`<span>${Math.round(said)}%</span>` : null}
      </div>`;
    })}
    ${over ? html`<i class="splitbar__mark" style=${`left:${((salary / sum) * 100).toFixed(2)}%`} aria-hidden="true"></i>` : null}
  </div>
  ${over ? html`<p class="splitbar__note" aria-hidden="true"><i class="tick tick--v"></i>${t('plan.bar_mark')}</p>` : null}`;
}

function SplitRow({ row, open, onToggle }) {
  const parts = row.key === 'essentials' && Array.isArray(row.parts) ? row.parts.filter((p) => p && p.label) : [];
  const share = Number(row.share_of_salary_pct);
  const body = html`
    <i class=${'dot ' + (SPLIT_TONE[row.key] || 't-ink')} aria-hidden="true"></i>
    <span class="splitrow__text">
      <span class="splitrow__name">${splitName(row)}${parts.length ? html`<${Icon} name="chevron" size=${18} />` : null}</span>
      <span class="splitrow__sub">${splitSub(row)}</span>
    </span>
    <span class="splitrow__num"><strong>${eur(row.amount, 'whole')}</strong>${Number.isFinite(share) ? html`<small>${pct(Math.round(share))}</small>` : null}</span>`;
  const cls = 'splitrow' + (some(row.amount) ? '' : ' is-zero');
  if (!parts.length) return html`<li><div class=${cls}>${body}</div></li>`;
  return html`<li>
    <button type="button" class=${cls} aria-expanded=${open ? 'true' : 'false'} aria-controls="plan-parts" onClick=${onToggle}>${body}</button>
    ${open ? html`<ul class="splitparts" id="plan-parts" aria-label=${t('plan.parts_aria')}>
      ${parts.map((p) => html`<li key=${p.label}><span>${nice(p.label)}</span><span>${eur(p.amount, 'whole')}</span></li>`)}
    </ul>` : null}
  </li>`;
}

function SplitTotal({ plan }) {
  const salary = Number(plan.payday && plan.payday.expected_salary);
  if (plan.fits === false) {
    return html`<dl class="kv kv--sum splitsum">
      <div><dt>${t('plan.adds_up')}</dt><dd>${eur(plan.adds_up_to, 'whole')}</dd></div>
      <div><dt>${t('plan.salary')}</dt><dd>${eur(salary, 'whole')}</dd></div>
      <div class="kv__total"><dt>${t('plan.missing')}</dt><dd class="is-bad">${eur(plan.short_by, 'whole')}</dd></div>
    </dl>`;
  }
  return html`<p class="splittotal"><span>${t('plan.adds_up')} <small>${t('plan.adds_up_note')}</small></span><strong>${eur(plan.adds_up_to, 'whole')}</strong></p>`;
}

const PLAN_PILL = {
  fits: { key: 'fits.yes', tone: 'good', icon: 'check' },
  tight: { key: 'fits.tight', tone: 'warn', icon: 'alert' },
  short: { key: 'plan.pill.short', tone: 'bad', icon: 'alert' },
};
const planState = (plan) => (plan.fits === false ? 'short' : plan.tight ? 'tight' : 'fits');

function PlanPill({ plan }) {
  const s = PLAN_PILL[planState(plan)];
  return html`<span class=${'pill pill--' + s.tone}><${Icon} name=${s.icon} size=${14} />${t(s.key)}</span>`;
}

/** Calm words for a salary that leaves no room, or does not cover the essentials. */
function PlanCaution({ plan }) {
  const state = planState(plan);
  if (state === 'fits') return null;
  return html`<div class="callout callout--warn caution" role="note">
    <strong>${t(state === 'short' ? 'plan.short_title' : 'plan.tight_title')}</strong>
    <p>${state === 'short' ? t('plan.short', { amount: eur(plan.short_by, 'whole') }) : t('plan.tight')}</p>
  </div>`;
}

/* ---------- the plan against the last pay period ---------- */

function LastPeriod({ plan, stale }) {
  const last = plan.last_pay_period;
  if (!last) return null;
  const everyday = rowOf(plan, 'everyday');
  const planned = Number(everyday && everyday.amount) || 0;
  const spent = Number(last.everyday) || 0;
  const diff = Number.isFinite(Number(last.everyday_against_this_plan)) ? Number(last.everyday_against_this_plan) : spent - planned;
  const lines = [
    ['essentials', last.essentials, rowOf(plan, 'essentials')],
    ['unexpected', last.unexpected, rowOf(plan, 'unexpected')],
    ['everyday', last.everyday, everyday],
    ['savings', last.saved, rowOf(plan, 'savings')],
  ].filter((l) => l[2]);
  return html`<section aria-labelledby="plan-last-h">
    <h2 id="plan-last-h" class="sect">${t('plan.last_title')}</h2>
    <div class=${'card' + (stale ? ' is-stale' : '')}>
      <p class="sub sub--first">${tidy(t('plan.last_text', { from: fmtDate(last.from), to: fmtDate(last.to), last: eur(spent, 'whole'), plan: eur(planned, 'whole') }))}</p>
      <${BarList} tone="b-everyday" rows=${[
        { key: 'last', label: t('plan.last_label'), value: spent, text: eur(spent, 'whole') },
        { key: 'plan', label: t('plan.this_label'), value: planned, text: eur(planned, 'whole') },
      ]} />
      <p class=${'callout ' + (diff > 0.5 ? 'callout--warn' : 'callout--good')}>
        ${diff > 0.5 ? t('plan.last_over', { amount: eur(diff, 'whole') }) : diff < -0.5 ? t('plan.last_under', { amount: eur(-diff, 'whole') }) : t('plan.last_same')}
      </p>
      <${Disclosure} label=${t('plan.last_more')}>
        <table class="cmp">
          <thead><tr><th scope="col"><span class="sr">${t('plan.cmp_line')}</span></th><th scope="col">${t('plan.last_label')}</th><th scope="col">${t('plan.this_label')}</th></tr></thead>
          <tbody>
            ${lines.map(([key, was, row]) => html`<tr key=${key}>
              <th scope="row"><i class=${'dot ' + SPLIT_TONE[key]} aria-hidden="true"></i>${key === 'savings' ? t('plan.saved') : BASKETS[key].short}</th>
              <td>${eur(was, 'whole')}</td><td>${eur(row.amount, 'whole')}</td>
            </tr>`)}
          </tbody>
        </table>
      <//>
    </div>
  </section>`;
}

/* ---------- accepting ---------- */

function AcceptCard({ plan, accepted, stale, onAccept, onChange }) {
  const period = plan.pay_period || {};
  const savings = rowOf(plan, 'savings');
  const everyday = rowOf(plan, 'everyday');
  const done = acceptedFor(accepted, plan);
  const saves = Boolean(savings && some(savings.amount));
  const spends = Boolean(everyday && some(everyday.amount));
  // What the plan comes to, in one sentence, whichever of the two has room.
  const sum = t(saves && spends ? 'plan.sum_both' : saves ? 'plan.sum_savings' : spends ? 'plan.sum_everyday' : 'plan.sum_none',
    { savings: eur(savings && savings.amount, 'whole'), week: eur(everyday && everyday.a_week, 'whole') });
  if (done) {
    return html`<section class="card accept accept--done" data-tour="plan-accept" aria-labelledby="plan-accept-h">
      <div class="accept__done" role="status">
        <span class="accept__tick" aria-hidden="true"><${Icon} name="check" size=${22} stroke=${2.200} /></span>
        <div>
          <h2 id="plan-accept-h" class="h2">${t('plan.accepted', { from: fmtDate(period.from), to: fmtDate(period.to) })}</h2>
          <p class=${'sub' + (stale ? ' is-stale' : '')}>${sum}</p>
        </div>
      </div>
      <p class="accept__note"><${Icon} name="info" size=${18} /><span>${t('plan.accepted_note')}</span></p>
      <button type="button" class="btn btn--small accept__change" onClick=${onChange}><${Icon} name="refresh" size=${16} />${t('plan.change')}</button>
    </section>`;
  }
  return html`<section class="card accept" data-tour="plan-accept" aria-labelledby="plan-accept-h">
    <h2 id="plan-accept-h" class="h2">${t('plan.accept_title')}</h2>
    <p class=${'sub' + (stale ? ' is-stale' : '')}>${tidy(t('plan.accept_text', { from: fmtDate(period.from), to: fmtDate(period.to) }))} ${sum}</p>
    <button type="button" class="btn btn--primary btn--wide" disabled=${stale} onClick=${onAccept}><${Icon} name="check" size=${20} stroke=${2} />${t('plan.accept')}</button>
    <p class="accept__note"><${Icon} name="info" size=${18} /><span>${t('plan.accept_note')}</span></p>
  </section>`;
}

/* ---------- the weeks ahead ---------- */

const OUTLOOK_PILL = {
  fine: { tone: 'good', icon: 'check' },
  thin: { tone: 'warn', icon: 'alert' },
  short: { tone: 'bad', icon: 'alert' },
};

function OutlookPill({ outlook }) {
  const s = OUTLOOK_PILL[outlook.status] || OUTLOOK_PILL.fine;
  const key = `outlook.status.${outlook.status}`;
  return html`<span class=${'pill pill--' + s.tone}><${Icon} name=${s.icon} size=${14} />${has(key) ? t(key) : t('outlook.status.fine')}</span>`;
}

/** The one sentence that says where the balance is heading. */
function outlookLine(o) {
  const low = o.lowest_point || {};
  const h = o.heads_up;
  if (h) {
    if (Number(o.balance_today) < 0) return t('outlook.short_now');
    return tidy(t('outlook.short', { date: fmtDate(h.below_zero_from), when: when(h.in_days, 'plan.in') }));
  }
  const vars = { amount: eur(low.balance, 'whole'), date: fmtDate(low.date) };
  return tidy(t(o.status === 'thin' ? 'outlook.thin' : 'outlook.fine', vars));
}

/** What would keep the balance above zero: a lower everyday pace, or a paused deposit. */
function OutlookFix({ outlook }) {
  const h = outlook.heads_up;
  if (!h) return null;
  const fix = h.fix;
  const none = h.everyday_spending_alone_is_not_enough;
  const pause = h.or_pause;
  const lines = [];
  if (fix) {
    lines.push(tidy(t('outlook.fix', { week: eur(fix.a_week, 'whole'), usual: eur(fix.instead_of_a_week, 'whole'), date: fmtDate(fix.hold_it_until) })
      + (Number.isFinite(Number(fix.lowest_point_then)) ? t('outlook.fix_low', { amount: eur(fix.lowest_point_then) }) : '')));
  } else {
    lines.push(none && Number(none.still_short_by) > 0.5 ? t('outlook.fix_none', { amount: eur(none.still_short_by, 'whole') }) : t('outlook.fix_none_plain'));
  }
  if (pause) lines.push(t(pause.covers_it ? 'outlook.pause_covers' : 'outlook.pause_helps', { amount: eur(pause.a_month, 'whole') }));
  return html`<div class=${'tip' + (fix ? '' : ' tip--plain')}>
    <strong>${t(fix ? 'outlook.fix_title' : 'outlook.fix_none_title')}</strong>
    ${lines.map((line, i) => html`<p key=${i}>${line}</p>`)}
  </div>`;
}

function niceStep(range) {
  const rough = range / 4.5;
  const pow = 10 ** Math.floor(Math.log10(Math.max(rough, 1)));
  const unit = rough / pow;
  return (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 5 ? 5 : 10) * pow;
}

let chartSeq = 0;

/**
 * The balance day by day, from today to the payday after next: a zero line, the part below zero
 * in red, the payday, the dated bills, and the same weeks with the fix as a dashed green line.
 */
export function OutlookChart({ outlook, compact }) {
  const [uid] = useState(() => `oc${++chartSeq}`);
  const s = outlook.series || {};
  const today = Number(outlook.balance_today);
  const lead = parseDate(outlook.as_of) && Number.isFinite(today);
  const dates = (lead ? [outlook.as_of] : []).concat(Array.isArray(s.dates) ? s.dates : []);
  const usual = (lead ? [today] : []).concat(Array.isArray(s.balance) ? s.balance.map(Number) : []);
  const fix = Array.isArray(s.with_the_fix) ? (lead ? [today] : []).concat(s.with_the_fix.map(Number)) : null;
  const n = Math.min(dates.length, usual.length, fix ? fix.length : Infinity);
  if (n < 2 || usual.slice(0, n).some((v) => !Number.isFinite(v))) return null;

  const W = 340;
  const H = compact ? 164 : 200;
  const L = 46, R = 12, T = 24, B = 24;
  const all = usual.slice(0, n).concat(fix ? fix.slice(0, n) : []);
  const lowest = Math.min(0, ...all);
  const highest = Math.max(1, ...all);
  const step = niceStep(highest - lowest);
  const hi = Math.ceil(highest / step) * step;
  // Below zero the scale leaves room (20px) under the deepest point for its label.
  const plot = H - T - B;
  const lo = lowest < 0 ? lowest - (hi - lowest) * (20 / (plot - 20)) : 0;
  const x = (i) => L + (i / (n - 1)) * (W - L - R);
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * plot;
  const path = (list) => list.slice(0, n).map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  const ticks = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step / 100; v += step) ticks.push(Math.abs(v) < step / 100 ? 0 : v);
  const base = H - B;
  const zero = y(0);
  const at = (iso) => dates.indexOf(iso);

  const payAt = outlook.next_payday ? at(outlook.next_payday) : -1;
  const bills = (outlook.assumes && Array.isArray(outlook.assumes.bills) ? outlook.assumes.bills : [])
    .map((b) => ({ b, i: at(b.date) })).filter((m) => m.i > 0 && m.i < n);
  let lowAt = lead ? 1 : 0;
  for (let i = lowAt; i < n; i += 1) if (usual[i] < usual[lowAt]) lowAt = i;
  const low = usual[lowAt];
  const lx = x(lowAt);
  const ly = y(low);
  // The label of the lowest point: under it when there is room, else beside the climb that follows.
  let label;
  if (base - ly >= 17) label = { x: clamp(lx, L + 26, W - R - 26), y: ly + 14, anchor: 'middle', halo: false };
  else if (lx < W - R - 64) label = { x: (payAt > lowAt && x(payAt) - lx < 14 ? x(payAt) : lx) + 8, y: ly - 4, anchor: 'start', halo: true };
  else label = { x: lx - 8, y: ly - 9, anchor: 'end', halo: true };
  if (label.anchor === 'middle') {
    // Keep it clear of the payday line (the lowest day is often the one before) and of the right edge.
    if (lowAt === n - 1) label = { ...label, x: W - R, anchor: 'end' };
    else if (payAt > 0 && Math.abs(x(payAt) - lx) < 30) label = payAt >= lowAt && lx - L > 60 ? { ...label, x: lx + 4, anchor: 'end' } : { ...label, x: Math.max(lx, x(payAt)) + 5, anchor: 'start' };
  }

  const h = outlook.heads_up;
  const aria = tidy(t('outlook.aria', {
    from: fmtDate(dates[0]), to: fmtDate(dates[n - 1]), start: eur(usual[0], 'whole'), low: eur(low, 'whole'), date: fmtDate(dates[lowAt]),
  }) + (h ? ' ' + t('outlook.aria_below', { date: fmtDate(h.below_zero_from) }) : '')
    + (fix ? ' ' + t('outlook.aria_fix') : ''));
  const startLabel = payAt < 0 || x(payAt) - L > 52;
  const endLabel = payAt < 0 || W - R - x(payAt) > 52;

  return html`<svg class=${'oc' + (compact ? ' oc--compact' : '')} viewBox=${`0 0 ${W} ${H}`} role="img" aria-label=${aria}>
    <defs>
      <clipPath id=${uid + 'u'}><rect x=${L - 4} y="0" width=${W - L - R + 8} height=${zero} /></clipPath>
      <clipPath id=${uid + 'd'}><rect x=${L - 4} y=${zero} width=${W - L - R + 8} height=${H - zero} /></clipPath>
    </defs>
    ${lo < 0 ? html`<rect class="oc__band" x=${L} y=${zero} width=${W - L - R} height=${base - zero} />` : null}
    ${ticks.map((v) => html`<g key=${v}>
      <line class=${v === 0 ? (lo < 0 ? 'oc__zero oc__zero--red' : 'oc__zero') : 'oc__grid'} x1=${L} x2=${W - R} y1=${y(v)} y2=${y(v)} />
      <text class=${'oc__tick' + (v === 0 && lo < 0 ? ' is-zero' : '')} x=${L - 6} y=${y(v) + 3.5} text-anchor="end">${eurShort(v)}</text>
    </g>`)}
    ${lo < 0 ? html`<path class="oc__under" d=${`${path(usual)} L${x(n - 1).toFixed(1)} ${zero.toFixed(1)} L${x(0).toFixed(1)} ${zero.toFixed(1)} Z`} clip-path=${`url(#${uid}d)`} />` : null}
    ${payAt > 0 && payAt < n ? html`<g>
      <line class="oc__payday" x1=${x(payAt)} x2=${x(payAt)} y1=${T - 4} y2=${base} />
      <text class="oc__paylabel" x=${clamp(x(payAt), L + 28, W - R - 28)} y=${T - 9} text-anchor="middle">${t('outlook.l.payday')}</text>
      <text class="oc__date" x=${x(payAt)} y=${H - 7} text-anchor="middle">${fmtDate(dates[payAt])}</text>
    </g>` : null}
    ${startLabel ? html`<text class="oc__date" x=${L} y=${H - 7} text-anchor="start">${fmtDate(dates[0])}</text>` : null}
    ${endLabel ? html`<text class="oc__date" x=${W - R} y=${H - 7} text-anchor="end">${fmtDate(dates[n - 1])}</text>` : null}
    ${fix ? html`<path class="oc__fix" d=${path(fix)} />` : null}
    <path class="oc__line" d=${path(usual)} clip-path=${`url(#${uid}u)`} />
    <path class="oc__line oc__line--below" d=${path(usual)} clip-path=${`url(#${uid}d)`} />
    ${fix ? html`<circle class="oc__fixend" cx=${x(n - 1)} cy=${y(fix[n - 1])} r="3.4" />` : null}
    <circle class="oc__start" cx=${x(0)} cy=${y(usual[0])} r="3.2" />
    ${bills.map(({ b, i }) => html`<rect key=${b.what + b.date} class="oc__bill" x=${x(i) - 3.3} y=${y(usual[i]) - 3.3} width="6.6" height="6.6"
      transform=${`rotate(45 ${x(i).toFixed(1)} ${y(usual[i]).toFixed(1)})`}><title>${billName(b.what)} ${eur(b.amount, 'whole')} · ${fmtDate(b.date)}</title></rect>`)}
    <circle class=${'oc__low' + (low < 0 ? ' is-below' : '')} cx=${lx} cy=${ly} r="4.2" />
    <text class=${'oc__lowlabel' + (low < 0 ? ' is-below' : '') + (label.halo ? ' has-halo' : '')} x=${label.x} y=${label.y} text-anchor=${label.anchor}>${eur(low, 'whole')}</text>
  </svg>`;
}

export function OutlookLegend({ outlook }) {
  const s = outlook.series || {};
  const bills = outlook.assumes && Array.isArray(outlook.assumes.bills) ? outlook.assumes.bills : [];
  return html`<ul class="legend legend--inline oc-legend">
    <li><span class="legend__key"><i class="oc-key" aria-hidden="true"></i>${t('outlook.l.usual')}</span></li>
    ${Array.isArray(s.with_the_fix) ? html`<li><span class="legend__key"><i class="oc-key oc-key--fix" aria-hidden="true"></i>${t('outlook.l.fix')}</span></li>` : null}
    ${outlook.heads_up ? html`<li><span class="legend__key"><i class="oc-key oc-key--below" aria-hidden="true"></i>${t('outlook.l.below')}</span></li>` : null}
    ${bills.length ? html`<li><span class="legend__key"><i class="oc-key oc-key--bill" aria-hidden="true"></i>${t('outlook.l.bill')}</span></li>` : null}
  </ul>`;
}

function OutlookFacts({ outlook }) {
  const low = outlook.lowest_point || {};
  const h = outlook.heads_up;
  const bill = h && h.biggest_bill_before;
  return html`<dl class="kv facts">
    <div><dt>${t('bc.balance_today')}</dt><dd class=${Number(outlook.balance_today) < 0 ? 'is-bad' : ''}>${eur(outlook.balance_today, 'whole')}</dd></div>
    <div><dt>${t('outlook.f.lowest')}</dt><dd class=${Number(low.balance) < 0 ? 'is-bad' : ''}>${eur(low.balance, 'whole')}<small>${fmtDate(low.date, { weekday: true })}</small></dd></div>
    ${h ? html`<div><dt>${t('outlook.f.below_from')}</dt><dd>${fmtDate(h.below_zero_from, { weekday: true })}<small>${when(h.in_days, 'plan.in')}</small></dd></div>` : null}
    ${h && Number.isFinite(Number(h.days_below_zero)) ? html`<div><dt>${t('outlook.f.days_below')}</dt><dd>${t('outlook.days_of', { n: num(h.days_below_zero, 0), of: num(outlook.days, 0) })}</dd></div>` : null}
    ${bill ? html`<div><dt>${t('outlook.f.bill_before')}</dt><dd>${billName(bill.what)}<small>${eur(bill.amount, 'whole')} · ${bill.overdue ? t('outlook.a.overdue') : fmtDate(bill.date)}</small></dd></div>` : null}
  </dl>`;
}

function OutlookAssumes({ outlook }) {
  const a = outlook.assumes || {};
  const bills = Array.isArray(a.bills) ? a.bills : [];
  const rate = (v) => t('outlook.a_day', { amount: eur(v, 'cents') });
  return html`<${Disclosure} label=${t('outlook.assumes')}>
    <dl class="kv">
      ${outlook.next_payday && Number.isFinite(Number(a.salary)) ? html`<div><dt>${t('outlook.a.salary', { date: fmtDate(outlook.next_payday) })}</dt><dd>${eur(a.salary, 'whole')}</dd></div>` : null}
      ${bills.map((b) => html`<div key=${b.what + b.date}><dt>${billName(b.what)}, ${b.overdue ? t('outlook.a.overdue') : fmtDate(b.date)}</dt><dd>${eur(b.amount, 'whole')}</dd></div>`)}
      ${some(a.other_bills_a_day) ? html`<div><dt>${t('outlook.a.other_bills')}</dt><dd>${rate(a.other_bills_a_day)}</dd></div>` : null}
      <div><dt>${t('outlook.a.groceries')}</dt><dd>${rate(a.groceries_and_transport_a_day)}</dd></div>
      <div><dt>${t('outlook.a.everyday')}</dt><dd>${rate(a.everyday_spending_a_day)}</dd></div>
    </dl>
  <//>`;
}

function OutlookSection({ req }) {
  const ui = useContext(UI);
  const o = req.data;
  return html`<section aria-labelledby="plan-outlook-h">
    <h2 id="plan-outlook-h" class="sect">${t('outlook.title')}</h2>
    <div class="card outlook">
      ${req.error && !o ? html`<div data-tour="plan-outlook"><${ErrorBox} error=${req.error} onRetry=${req.reload} /></div>` : null}
      ${!o && !req.error ? html`<div data-tour="plan-outlook"><${Skeleton} rows=${4} tall=${true} /></div>` : null}
      ${o ? html`
        <div class="outlook__chart" data-tour="plan-outlook">
          <div class="outlook__top">
            <p class="outlook__line">${outlookLine(o)}</p>
            <${OutlookPill} outlook=${o} />
          </div>
          <p class="sub">${tidy(t('outlook.sub', { date: fmtDate(o.until) }))}</p>
          <${OutlookChart} outlook=${o} />
          <${OutlookLegend} outlook=${o} />
        </div>
        <${OutlookFacts} outlook=${o} />
        <${OutlookFix} outlook=${o} />
        <p class="guidance"><${Icon} name="info" size=${18} /><span>${t('outlook.honest')}</span></p>
        <${OutlookAssumes} outlook=${o} />
        <button type="button" class="textlink" onClick=${() => ui.ask(t('outlook.ask_q'))}><${Icon} name="chat" size=${18} />${t('trainer.ask_this')}</button>` : null}
    </div>
  </section>`;
}

/* ---------- the screen ---------- */

export function Plan() {
  const ui = useContext(UI);
  const id = ui.who.id;
  const [accepted, setAccepted] = useAccepted(id);
  const [goal, setGoal] = useState(() => goalOf(accepted));
  const goalQ = useDebounced(goal, 280);
  const req = useApi(cust(id, `/payday-plan?savings_goal_pct=${goalQ}`));
  const outlook = useApi(cust(id, '/outlook'));
  const [open, setOpen] = useState(false);
  const root = useRef(null);
  const plan = req.data;
  const stale = Boolean(plan) && (goal !== goalQ || req.loading || req.stale);
  const locked = acceptedFor(accepted, plan);

  // Opened at one of its sections (the heads-up notice opens the weeks ahead): bring it to the top,
  // and again when the blocks above it have loaded and pushed it down.
  const focus = ui.focus && ui.focus.route === 'plan' && /^[\w-]+$/.test(ui.focus.name) ? ui.focus : null;
  const settled = Boolean((req.data || req.error) && (outlook.data || outlook.error));
  const handled = useRef(0);
  useEffect(() => {
    if (!focus || handled.current === focus.n) return undefined;
    const timer = setTimeout(() => {
      const el = root.current && root.current.querySelector(`[data-tour="${focus.name}"]`);
      const scroller = el && el.closest('.screen');
      if (el && scroller) {
        // Start at the section's title when it has one, so the heading is read first.
        const section = el.closest('section');
        const head = (section && section.querySelector(':scope > .sect')) || el;
        scroller.scrollTop += head.getBoundingClientRect().top - scroller.getBoundingClientRect().top - 6;
      }
      if (settled) handled.current = focus.n;
    }, 40);
    return () => clearTimeout(timer);
  }, [focus && focus.n, settled, Boolean(req.data), Boolean(outlook.data)]);

  const accept = () => {
    if (!plan || !plan.pay_period) return;
    setAccepted({ from: plan.pay_period.from, to: plan.pay_period.to, goal: Number(plan.savings_goal_pct), on: plan.as_of || null });
  };

  let body;
  if (req.error && !plan) {
    body = html`<${ErrorBox} title=${t('plan.error')} error=${req.error} onRetry=${req.reload} />`;
  } else if (!plan) {
    body = html`
      <div class="card"><${Skeleton} rows=${3} tall=${true} /></div>
      <div class="card" data-tour="plan-split"><${Skeleton} rows=${5} tall=${true} /></div>
      <div class="card" data-tour="plan-accept"><${Skeleton} rows=${2} /></div>`;
  } else {
    const pay = plan.payday || {};
    const period = plan.pay_period || {};
    const savings = rowOf(plan, 'savings');
    const shown = Number(plan.savings_goal_pct);
    const value = locked ? goalOf(accepted) : goal;
    body = html`
      <section class="card phead" aria-labelledby="phead-h">
        <div class="thero__top">
          <h2 id="phead-h" class="thero__label">${t('plan.next_salary')}</h2>
          <span class=${stale ? 'is-stale' : ''}><${PlanPill} plan=${plan} /></span>
        </div>
        <p class="thero__num"><${Amount} value=${pay.expected_salary} mode="whole" /></p>
        <p class="thero__sub">${t('plan.header_when', { date: fmtDate(pay.date, { weekday: true }), when: when(pay.in_days, 'plan.in') })}</p>
        <p class="thero__text">${tidy(t('plan.period', { from: fmtDate(period.from), to: fmtDate(period.to), days: nDays(period.days) }))}</p>
      </section>

      <section aria-labelledby="plan-split-h">
        <h2 id="plan-split-h" class="sect">${t('plan.split_title')}</h2>
        <div class="card" data-tour="plan-split">
          <p class="sub sub--first">${t('plan.teach')}</p>
          <div class=${stale ? 'is-stale' : ''}>
            <${SplitBar} plan=${plan} />
            <ul class="split">
              ${splitRows(plan).map((row) => html`<${SplitRow} key=${row.key} row=${row} open=${open} onToggle=${() => setOpen(!open)} />`)}
            </ul>
            <${SplitTotal} plan=${plan} />
            <${PlanCaution} plan=${plan} />
          </div>
          <div class=${'goal' + (locked ? ' goal--locked' : '')}>
            <div class="goal__head">
              <label for="plan-goal">${t('trainer.goal')}</label>
              <output for="plan-goal" class=${stale ? 'is-stale' : ''}>${t('trainer.goal_value', { pct: num(value, 0) })}${savings && shown === value
                ? html`<small> · ${t('plan.goal_amount', { amount: eur(savings.amount, 'whole') })}</small>` : null}</output>
            </div>
            <input id="plan-goal" type="range" min="0" max=${GOAL_MAX} step="1" value=${value} disabled=${locked}
              style=${`--fill:${(clamp(value, 0, GOAL_MAX) / GOAL_MAX) * 100}%`}
              aria-valuetext=${t('trainer.goal_value', { pct: value })}
              onInput=${(e) => setGoal(Number(e.target.value))} />
            <div class="goal__scale" aria-hidden=${locked ? undefined : 'true'}>
              ${locked ? html`<span>${t('plan.goal_locked')}</span>` : html`<span>0 %</span><span>${t('trainer.goal_hint')}</span><span>${GOAL_MAX} %</span>`}
            </div>
            ${req.error ? html`<p class="inline-error" role="alert">${t('trainer.goal_error', { message: req.error.message })}</p>` : null}
          </div>
        </div>
      </section>

      <${LastPeriod} plan=${plan} stale=${stale} />

      <${AcceptCard} plan=${plan} accepted=${accepted} stale=${stale} onAccept=${accept}
        onChange=${() => { setGoal(goalOf(accepted)); setAccepted(null); }} />
      <button type="button" class="textlink textlink--center" onClick=${() => ui.ask(t('plan.ask_q'))}><${Icon} name="chat" size=${18} />${t('plan.ask')}</button>`;
  }

  return html`<div class="stack plan" ref=${root}>
    ${body}
    <${OutlookSection} req=${outlook} />
    <p class="endnote">${t('plan.endnote')}</p>
  </div>`;
}

/* ---------- on the trainer: the way in ---------- */

export function PlanEntry({ id }) {
  const ui = useContext(UI);
  const [accepted] = useAccepted(id);
  const req = useApi(cust(id, `/payday-plan?savings_goal_pct=${goalOf(accepted)}`));
  const plan = req.data;
  // No regular salary, no payday to plan for: the trainer simply has no such card.
  if (req.error && !plan) return null;
  if (!plan) return html`<div class="card" data-tour="trainer-plan"><${Skeleton} rows=${2} /></div>`;
  const pay = plan.payday || {};
  const period = plan.pay_period || {};
  const done = acceptedFor(accepted, plan);
  const rows = splitRows(plan).filter((r) => some(r.amount));
  const sum = rows.reduce((a, r) => a + Number(r.amount), 0);
  return html`<button type="button" class="plancta" data-tour="trainer-plan" onClick=${() => ui.go('plan')}>
    <span class="plancta__icon" aria-hidden="true"><${Icon} name=${done ? 'check' : 'calendar'} size=${40} stroke=${1} /></span>
    <span class="plancta__text">
      <strong>${when(pay.in_days, 'plan.when')}</strong>
      <span>${done
        ? t('plan.entry_accepted', { from: fmtDate(period.from), to: fmtDate(period.to) })
        : t('plan.entry_ready', { amount: eur(pay.expected_salary, 'whole') })}</span>
    </span>
    <span class="plancta__chev" aria-hidden="true"><${Icon} name="right" size=${22} stroke=${1.800} /></span>
    ${sum > 0 ? html`<span class="plancta__bar" aria-hidden="true">
      ${rows.map((r) => html`<i key=${r.key} class=${SPLIT_TONE[r.key] || 't-ink'} style=${`flex:${((Number(r.amount) / sum) * 100).toFixed(2)} 1 0%`}></i>`)}
    </span>` : null}
  </button>`;
}

/* ---------- the heads-up notice, said from its numbers ---------- */

function headsUpText(d) {
  const bill = d.bill;
  const fix = d.fix;
  const lines = [];
  if (bill) {
    const what = billName(bill.what);
    lines.push(t(bill.overdue ? 'hu.bill_overdue' : 'hu.bill', { what, what_lc: what.toLowerCase(), amount: eur(bill.amount, 'whole'), date: fmtDate(bill.date) }));
  }
  lines.push(t('hu.short', { amount: eur(d.short_by, 'whole'), date: fmtDate(d.deepest_date) }));
  lines.push(fix ? t('hu.fix', { week: eur(fix.a_week, 'whole'), usual: eur(fix.instead_of_a_week, 'whole') }) : t('hu.fix_none'));
  return {
    title: Number(d.in_days) <= 1 ? t('hu.title_now') : t('hu.title', { date: fmtDate(d.below_zero_from) }),
    detail: tidy(lines.join(' ')),
  };
}

/** A notice's title and detail in the current language: from its numbers when it carries them. */
export function noticeText(n) {
  if (n && n.kind === 'heads_up' && n.data && typeof n.data === 'object') return headsUpText(n.data);
  return { title: nice(n.title), detail: nice(n.detail) };
}

/** The heads-up in "Worth a look": a tap opens the weeks ahead, and a second link asks about it. */
export function HeadsUpNotice({ notice }) {
  const ui = useContext(UI);
  const { title, detail } = noticeText(notice);
  const open = () => ui.go('plan', { focus: 'plan-outlook' });
  return html`<div class="headsup">
    <button type="button" class="row row--tap notice notice--warn" onClick=${open}>
      <span class="notice__mark" aria-hidden="true"><${Icon} name="alert" size=${20} /></span>
      <span class="row__text"><span class="row__title">${title}</span><span class="row__sub">${detail}</span>
        <span class="headsup__go">${t('hu.open')}</span></span>
      <span class="row__chev"><${Icon} name="right" size=${20} /></span>
    </button>
    ${notice.ask ? html`<button type="button" class="textlink headsup__ask" onClick=${() => ui.ask(nice(notice.ask))}><${Icon} name="chat" size=${18} />${t('trainer.ask_this')}</button>` : null}
  </div>`;
}

/* ---------- in the chat: compact cards for the two tools ---------- */

export function planCard(r, ui) {
  const pay = r.payday || {};
  const period = r.pay_period || {};
  const last = r.last_pay_period;
  const everyday = rowOf(r, 'everyday');
  return {
    period: period.from && period.to ? { start: period.from, end: period.to } : null,
    body: html`
      <div class="card__row"><p class="figure"><strong>${eur(pay.expected_salary, 'whole')}</strong>
        <span>${t('ans.plan_salary', { date: fmtDate(pay.date), when: when(pay.in_days, 'plan.in') })}</span></p>
        <${PlanPill} plan=${r} /></div>
      <${SplitBar} plan=${r} />
      <ul class="legend legend--rows">
        ${splitRows(r).map((row) => html`<li key=${row.key}>
          <span class=${'legend__key ' + (SPLIT_TONE[row.key] || 't-ink')}><i class="dot" aria-hidden="true"></i>${splitName(row)}</span>
          <span class="legend__val">${eur(row.amount, 'whole')}${Number.isFinite(Number(row.share_of_salary_pct)) ? html`<small> · ${pct(Math.round(Number(row.share_of_salary_pct)))}</small>` : null}</span>
        </li>`)}
      </ul>
      ${everyday && some(everyday.amount) ? html`<p class="callout planline"><strong>${BASKETS.everyday.name}:</strong> ${splitSub(everyday)}</p>` : null}
      <${PlanCaution} plan=${r} />
      ${last ? html`<p class="footnote">${tidy(t('plan.last_text', { from: fmtDate(last.from), to: fmtDate(last.to), last: eur(last.everyday, 'whole'), plan: eur(everyday && everyday.amount, 'whole') }))}</p>` : null}
      <button type="button" class="btn btn--small" onClick=${() => ui.go('plan')}>${t('ans.open_plan')}<${Icon} name="right" size=${16} /></button>`,
  };
}

export function outlookCard(r, ui) {
  const low = r.lowest_point || {};
  return {
    period: r.as_of && r.until ? { start: r.as_of, end: r.until } : null,
    body: html`
      <div class="card__row"><p class="figure"><strong class=${Number(low.balance) < 0 ? 'is-bad' : ''}>${eur(low.balance, 'whole')}</strong>
        <span>${t('ans.outlook_low', { date: fmtDate(low.date) })}</span></p>
        <${OutlookPill} outlook=${r} /></div>
      <p>${outlookLine(r)}</p>
      <${OutlookChart} outlook=${r} compact=${true} />
      <${OutlookLegend} outlook=${r} />
      <${OutlookFix} outlook=${r} />
      <p class="footnote">${t('outlook.honest')}</p>
      <button type="button" class="btn btn--small" onClick=${() => ui.go('plan', { focus: 'plan-outlook' })}>${t('ans.open_outlook')}<${Icon} name="right" size=${16} /></button>`,
  };
}
