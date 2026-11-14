// Home loan: readiness learned from real application outcomes. Guidance, not a decision.
import {
  html, useState, useEffect, useRef, useContext, useApi, useDebounced, cust,
  eur, num, pct, fmtDate, nice, words, clamp, t, tv,
} from './lib.js';
import {
  UI, Icon, Skeleton, ErrorBox, Empty, Disclosure, Stat,
  BarList, PillarMeter, Pillars, StatusPill, Timeline,
} from './parts.js';

const PRICE = { min: 80000, max: 600000, step: 1000 };
const OWN = { min: 0, max: 150000, step: 500 };
const DECISION = {
  approved: { key: 'decision.approved', tone: 'good', icon: 'check' },
  rejected: { key: 'decision.rejected', tone: 'bad', icon: 'close' },
};

function Slider({ id, label, value, range, onChange, hint }) {
  const v = Number(value) || 0;
  const fill = clamp(((v - range.min) / (range.max - range.min)) * 100, 0, 100);
  return html`<div class="slider">
    <div class="slider__head"><label for=${id}>${label}</label><output for=${id}>${eur(v, 'whole')}</output></div>
    <input id=${id} type="range" min=${range.min} max=${range.max} step=${range.step} value=${clamp(v, range.min, range.max)}
      style=${`--fill:${fill}%`} aria-valuetext=${eur(v, 'whole')} onInput=${(e) => onChange(Number(e.target.value))} />
    <div class="goal__scale" aria-hidden="true"><span>${eur(range.min, 'whole')}</span>${hint ? html`<span>${hint}</span>` : null}<span>${eur(range.max, 'whole')}</span></div>
  </div>`;
}

function paceText(months) {
  if (months === null || months === undefined || !Number.isFinite(Number(months))) return t('loan.pace_never');
  const m = Number(months);
  if (m <= 0) return t('loan.pace_now');
  if (m < 24) return t('loan.pace_months', { n: m, count: num(m, 0) });
  return t('loan.pace_years', { count: num(m / 12) });
}

function Application({ app, id }) {
  const req = useApi(cust(id, '/mortgage/application'));
  const timeline = req.data && Array.isArray(req.data.timeline) ? req.data.timeline : [];
  const outcome = app.decision === 'approved' ? t('loan.app_yes') : app.decision === 'rejected' ? t('loan.app_no') : t('loan.app_other', { outcome: words(app.decision).toLowerCase() });
  return html`<section aria-labelledby="app-h">
    <h2 id="app-h" class="sect">${t('loan.app_title')}</h2>
    <div class="card">
      <div class="card__row">
        <p class="eyebrow">${t('loan.app_eyebrow')}</p>
        <${StatusPill} status=${app.decision} map=${DECISION} />
      </div>
      <p>
        ${t('loan.app_text', { loan: eur(app.requested_loan, 'whole'), price: eur(app.property_price, 'whole') })}${app.started ? t('loan.app_started', { date: fmtDate(app.started, { year: true }) }) : ''}.
        ${' '}${outcome}${Number.isFinite(Number(app.days)) ? t('loan.app_days', { n: Number(app.days), count: num(app.days, 0) }) : ''}.
      </p>
      ${app.rejection_reason_plain ? html`<p class="callout callout--warn">${t('loan.app_reason', { reason: nice(app.rejection_reason_plain) })}</p>` : null}
      <div class="stats">
        <${Stat} label=${tv('pillar', 'Your own money')} value=${eur(app.own_money, 'whole')} hint=${t('loan.of_price', { pct: pct(app.own_money_share_pct) })} />
        <${Stat} label=${t('loan.collateral_value')} value=${eur(app.collateral_value, 'whole')} />
        <${Stat} label=${t('loan.income_required')} value=${eur(app.monthly_income_the_bank_required, 'whole')} hint=${t('unit.a_month')} />
      </div>
      <${Disclosure} label=${timeline.length ? t('loan.app_steps_n', { n: timeline.length }) : t('loan.app_steps')}>
        ${req.error ? html`<${ErrorBox} error=${req.error} onRetry=${req.reload} />` : null}
        ${!req.data && !req.error ? html`<${Skeleton} rows=${5} />` : null}
        ${req.data ? (timeline.length ? html`<${Timeline} items=${timeline} />` : html`<p class="muted">${t('loan.app_no_steps')}</p>`) : null}
      <//>
    </div>
  </section>`;
}

export function Loan() {
  const ui = useContext(UI);
  const id = ui.who.id;
  const [price, setPrice] = useState(null);
  const [own, setOwn] = useState(null);
  const seen = useRef(0);

  // A price handed over from the chat ("Try other prices in Home loan").
  useEffect(() => {
    const p = ui.preset;
    if (p && p.n !== seen.current) {
      seen.current = p.n;
      if (Number.isFinite(Number(p.price))) setPrice(Number(p.price));
      if (Number.isFinite(Number(p.own))) setOwn(Number(p.own));
    }
  }, [ui.preset]);

  const wanted = [price !== null ? `property_price=${price}` : null, own !== null ? `own_money=${own}` : null].filter(Boolean).join('&');
  const query = useDebounced(wanted, 280);
  const req = useApi(cust(id, '/mortgage' + (query ? `?${query}` : '')));

  if (req.error && !req.data) {
    return html`<div class="stack"><${ErrorBox} title=${t('loan.error')} error=${req.error} onRetry=${req.reload} /></div>`;
  }
  if (!req.data) {
    return html`<div class="stack">
      <div class="card"><${Skeleton} rows=${3} tall=${true} /></div>
      <div class="card"><${Skeleton} rows=${4} /></div>
      <div class="card"><${Skeleton} rows=${5} /></div>
    </div>`;
  }

  const d = req.data;
  const home = d.home || {};
  const you = d.you || {};
  const stale = wanted !== query || req.loading || req.stale;
  const shownPrice = price ?? Number(home.property_price) ?? PRICE.min;
  const shownOwn = own ?? Number(home.own_money) ?? 0;
  const matter = Array.isArray(d.what_would_matter_most) ? d.what_would_matter_most : [];
  const costs = Array.isArray(d.other_costs_to_plan_for) ? d.other_costs_to_plan_for : [];
  const learned = d.learned_from || {};
  const rejections = Array.isArray(learned.rejections) ? learned.rejections : [];
  const pillars = Array.isArray(d.pillars) ? d.pillars : [];
  const turnedDown = Number(learned.applications) - Number(learned.approved);
  const note = nice(d.note) || t('loan.note');

  return html`<div class="stack">
    <section class=${'card loanhead' + (stale ? ' is-stale' : '')} aria-labelledby="loan-h">
      <p class="eyebrow">${t('loan.eyebrow')}</p>
      <h2 id="loan-h" class="loanhead__title">${nice(d.readiness) || t('loan.no_readiness')}</h2>
      <${PillarMeter} pillars=${pillars} />
      <p class="guidance"><${Icon} name="info" size=${18} /><span>${note}</span></p>
    </section>

    <section class="card" aria-label=${t('loan.home_aria')}>
      <${Slider} id="loan-price" label=${t('loan.price')} value=${shownPrice} range=${PRICE} onChange=${setPrice} />
      <${Slider} id="loan-own" label=${tv('pillar', 'Your own money')} value=${shownOwn} range=${OWN} onChange=${setOwn}
        hint=${Number.isFinite(Number(home.own_money_share_pct)) ? t('loan.of_price', { pct: pct(home.own_money_share_pct) }) : null} />
      <dl class=${'trio' + (stale ? ' is-stale' : '')}>
        <div><dt>${t('loan.needed')}</dt><dd>${eur(home.loan, 'whole')}</dd></div>
        <div><dt>${t('loan.largest')}</dt><dd>${eur(you.largest_loan_your_income_supports, 'whole')}</dd></div>
        <div><dt>${t('loan.reach')}</dt><dd>${eur(you.price_range_with_this_own_money, 'whole')}</dd></div>
      </dl>
      ${Number.isFinite(Number(you.monthly_income)) ? html`<p class="footnote">${t('loan.based', { income: eur(you.monthly_income, 'whole'), left: eur(you.monthly_left_over, 'whole'), balance: eur(you.balance_today, 'whole') })}</p>` : null}
    </section>

    <section aria-labelledby="checks-h" class=${stale ? 'is-stale' : ''}>
      <h2 id="checks-h" class="sect">${t('loan.checks')}</h2>
      ${pillars.length ? html`<${Pillars} pillars=${pillars} tour="loan-pillars" />` : html`<div class="card" data-tour="loan-pillars"><${Empty} icon="loan" title=${t('loan.no_checks')}>${t('loan.no_checks_text')}<//></div>`}
    </section>

    <section class=${stale ? 'is-stale' : ''} aria-labelledby="matter-h">
      <h2 id="matter-h" class="sect">${t('loan.matter')}</h2>
      <div class="card">
        ${matter.length ? html`<ol class="matter">
          ${matter.map((m, i) => {
            const reachable = m.months_at_your_saving_pace !== null && m.months_at_your_saving_pace !== undefined;
            return html`<li key=${i}>
              <span class="matter__n" aria-hidden="true">${i + 1}</span>
              <div>
                <strong>${nice(m.change)}</strong>
                <p>${nice(m.why)}</p>
                <p class=${'pace ' + (reachable ? 'pace--ok' : 'pace--far')}><${Icon} name=${reachable ? 'up' : 'info'} size=${14} />${paceText(m.months_at_your_saving_pace)}</p>
              </div>
            </li>`;
          })}
        </ol>` : html`<${Empty} icon="check" title=${t('loan.all_strong')}>${t('loan.all_strong_text')}<//>`}
      </div>
    </section>

    ${d.your_application ? html`<${Application} app=${d.your_application} id=${id} />` : null}

    <section aria-labelledby="costs-h">
      <h2 id="costs-h" class="sect">${t('loan.costs')}</h2>
      <div class="card">
        <p class="sub sub--first">${t('loan.costs_sub')}</p>
        ${costs.length ? html`<ul class="tx">
          ${costs.map((c, i) => html`<li key=${i}>
            <span class="tx__what"><strong>${tv('cost', c.what) === c.what ? words(c.what) : tv('cost', c.what)}</strong>
              <small>${Number.isFinite(Number(c.seen_in_applications)) ? t('loan.seen', { n: num(c.seen_in_applications, 0) }) : ''}</small></span>
            <span class="tx__amt">${eur(c.typical, 'whole')}<small>${t('loan.typical')}</small></span>
          </li>`)}
        </ul>` : html`<p class="muted">${t('loan.no_costs')}</p>`}
      </div>
    </section>

    <section aria-labelledby="learned-h">
      <h2 id="learned-h" class="sect">${t('loan.learned')}</h2>
      <div class="card">
        <p>${t('loan.learned_text', { n: num(learned.applications, 0), approved: num(learned.approved, 0) })}${Number.isFinite(turnedDown) ? t('loan.learned_down', { n: num(turnedDown, 0) }) : ''}. ${t('loan.learned_tail')}</p>
        ${rejections.length ? html`
          <h3 class="h3">${t('loan.why_down')}</h3>
          <${BarList} tone="t-ink" rows=${rejections.map((r) => ({ key: r.reason, label: (() => { const s = nice(r.reason); return s.charAt(0).toUpperCase() + s.slice(1); })(), value: r.count, text: `${num(r.count, 0)}` }))} />` : null}
        <p class="guidance"><${Icon} name="info" size=${18} /><span>${note}</span></p>
      </div>
    </section>
  </div>`;
}
