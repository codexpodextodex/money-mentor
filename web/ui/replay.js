// Your year, replayed: the customer's own 12 months with one habit changed.
// Self-contained on purpose: its own strings (en, fi, sv) and its own styles,
// so it keeps working while the rest of the shell changes around it.
import { html, useState, useEffect, useContext, useApi, cust } from './lib.js';
import { UI, Load } from './parts.js';

const TEXT = {
  en: {
    title: 'Your year, replayed',
    intro: 'Your real payments from {from} to {to}, with one habit changed. This is a replay of the past, not a forecast.',
    actual: 'What happened', replayed: 'With the change',
    kept: 'Kept over the year', perMonth: '{amount} a month',
    days: 'Days below zero', was: 'was {n}', lowest: 'Lowest balance',
    today: 'Balance today', insteadOf: 'instead of {amount}',
    levers: 'Your levers, by what they would have changed',
    noEffect: 'No effect for you: {list}.',
    holdTitle: 'Does it hold?',
    holdSame: 'Your biggest lever was the same the year before, so it is a habit, not a one-off.',
    holdDiff: 'Your biggest lever was a different one the year before, so treat this as a pattern of this year.',
    holdThis: 'In the year before ({from} to {to}) this change would have kept {amount} and ranked number {rank} of your levers.',
    readTitle: 'How to read this',
    read: 'It is your own history with one rule applied. It assumes the money you did not spend stayed on the account.',
    planTitle: 'Make it this week’s plan',
    planText: 'An everyday ceiling of {amount} a week, with a check-in on Sunday.',
    planButton: 'Set the plan', planSet: 'Plan set for this week',
    planDone: 'Your weekly ceiling is {amount}. The trainer compares it with your real spending on Sunday.',
    ask: 'Ask the trainer about this', askQ: 'What would have helped me most last year?',
    checkTitle: 'The last four weeks against this ceiling', checkSummary: '{n} of 4 weeks stayed within it.',
    weekOk: 'within', weekOver: 'over by {amount}',
    thisWeek: 'This week so far: {spent} spent, {left} left, {days} days to go.',
    chartLabel: 'Lowest balance each week, as it happened and with the change',
    L: {
      weekly_rhythm: ['Trim your heaviest weeks to a normal busy week ({amount})', 'Only the heaviest quarter of your weeks is trimmed. Every other week stays as it was.'],
      everyday_less: ['Spend 20% less on everyday things', 'The same 20% off every everyday purchase.'],
      small_purchases: ['Halve the purchases under €15', 'The ones that slip through your fingers.'],
      big_purchases: ['Halve the everyday purchases of €300 or more', 'A cheaper choice, or every second one skipped.'],
      top_category: ['Spend 30% less on {category}', 'Your biggest everyday category.'],
    },
    C: {},
  },
  fi: {
    title: 'Vuotesi uusinta',
    intro: 'Oikeat maksusi ajalta {from}–{to}, yhdellä tavalla muutettuna. Tämä on menneen uusinta, ei ennuste.',
    actual: 'Mitä tapahtui', replayed: 'Muutoksen kanssa',
    kept: 'Jäänyt vuodessa', perMonth: '{amount} kuukaudessa',
    days: 'Päiviä miinuksella', was: 'oli {n}', lowest: 'Alin saldo',
    today: 'Saldo tänään', insteadOf: 'eikä {amount}',
    levers: 'Vipusi sen mukaan, mitä ne olisivat muuttaneet',
    noEffect: 'Ei vaikutusta sinulle: {list}.',
    holdTitle: 'Pitääkö se paikkansa?',
    holdSame: 'Suurin vipusi oli sama myös edellisenä vuonna, joten kyse on tavasta eikä sattumasta.',
    holdDiff: 'Edellisenä vuonna suurin vipusi oli toinen, joten pidä tätä tämän vuoden ilmiönä.',
    holdThis: 'Edellisenä vuonna ({from}–{to}) tämä muutos olisi jättänyt {amount} ja ollut vivuistasi sijalla {rank}.',
    readTitle: 'Näin luet tämän',
    read: 'Tämä on oma historiasi, johon on sovellettu yhtä sääntöä. Oletuksena on, että käyttämättä jäänyt raha olisi pysynyt tilillä.',
    planTitle: 'Tee siitä tämän viikon suunnitelma',
    planText: 'Arjen kulutuksen katto {amount} viikossa ja tarkistus sunnuntaina.',
    planButton: 'Aseta suunnitelma', planSet: 'Suunnitelma asetettu tälle viikolle',
    planDone: 'Viikkokattosi on {amount}. Valmentaja vertaa sitä toteutuneeseen kulutukseesi sunnuntaina.',
    ask: 'Kysy tästä valmentajalta', askQ: 'Mikä olisi auttanut minua eniten viime vuonna?',
    checkTitle: 'Viimeiset neljä viikkoa tätä kattoa vasten', checkSummary: '{n}/4 viikkoa pysyi katon alla.',
    weekOk: 'katon alla', weekOver: 'yli {amount}',
    thisWeek: 'Tämä viikko tähän asti: käytetty {spent}, jäljellä {left}, päiviä jäljellä {days}.',
    chartLabel: 'Viikon alin saldo sellaisena kuin se toteutui ja muutoksen kanssa',
    L: {
      weekly_rhythm: ['Karsi raskaimmat viikkosi tavallisen kiireisen viikon tasolle ({amount})', 'Vain raskain neljännes viikoistasi karsitaan. Muut viikot pysyvät ennallaan.'],
      everyday_less: ['Käytä 20 % vähemmän arjen kulutukseen', 'Sama 20 % pois jokaisesta arjen ostoksesta.'],
      small_purchases: ['Puolita alle 15 euron ostokset', 'Ne, jotka valuvat sormien läpi.'],
      big_purchases: ['Puolita vähintään 300 euron arkiostokset', 'Edullisempi valinta, tai joka toinen jää väliin.'],
      top_category: ['Käytä 30 % vähemmän: {category}', 'Suurin arjen kulutuksen luokkasi.'],
    },
    C: { Restaurants: 'ravintolat', Entertainment: 'viihde', Lifestyle: 'elämäntyyli', Travel: 'matkailu', 'Home & Tech': 'koti ja tekniikka', Transportation: 'liikenne', Groceries: 'ruokaostokset', Health: 'terveys' },
  },
  sv: {
    title: 'Ditt år i repris',
    intro: 'Dina verkliga betalningar från {from} till {to}, med en vana ändrad. Det här är en repris av det som varit, ingen prognos.',
    actual: 'Vad som hände', replayed: 'Med ändringen',
    kept: 'Kvar över året', perMonth: '{amount} i månaden',
    days: 'Dagar på minus', was: 'var {n}', lowest: 'Lägsta saldo',
    today: 'Saldo i dag', insteadOf: 'i stället för {amount}',
    levers: 'Dina spakar, efter vad de skulle ha ändrat',
    noEffect: 'Ingen effekt för dig: {list}.',
    holdTitle: 'Håller det?',
    holdSame: 'Din största spak var densamma året innan, så det är en vana och ingen engångshändelse.',
    holdDiff: 'Året innan var din största spak en annan, så se det här som ett mönster för i år.',
    holdThis: 'Året innan ({from} till {to}) hade den här ändringen lämnat {amount} kvar och varit nummer {rank} bland dina spakar.',
    readTitle: 'Så läser du det här',
    read: 'Det är din egen historik med en regel tillämpad. Det förutsätter att pengarna du inte använde hade stannat på kontot.',
    planTitle: 'Gör det till veckans plan',
    planText: 'Ett tak för vardagskonsumtionen på {amount} i veckan, med avstämning på söndag.',
    planButton: 'Sätt planen', planSet: 'Planen är satt för den här veckan',
    planDone: 'Ditt veckotak är {amount}. Tränaren jämför det med din verkliga konsumtion på söndag.',
    ask: 'Fråga tränaren om det här', askQ: 'Vad hade hjälpt mig mest förra året?',
    checkTitle: 'De fyra senaste veckorna mot det här taket', checkSummary: '{n} av 4 veckor höll sig under taket.',
    weekOk: 'under taket', weekOver: '{amount} över',
    thisWeek: 'Den här veckan hittills: {spent} använt, {left} kvar, {days} dagar kvar.',
    chartLabel: 'Veckans lägsta saldo, som det blev och med ändringen',
    L: {
      weekly_rhythm: ['Kapa dina tyngsta veckor till en vanlig intensiv vecka ({amount})', 'Bara den tyngsta fjärdedelen av dina veckor kapas. Alla andra veckor är som de var.'],
      everyday_less: ['Använd 20 % mindre på vardagskonsumtion', 'Samma 20 % av på varje vardagsköp.'],
      small_purchases: ['Halvera köpen under 15 euro', 'De som rinner mellan fingrarna.'],
      big_purchases: ['Halvera vardagsköpen på minst 300 euro', 'Ett billigare val, eller vartannat hoppas över.'],
      top_category: ['Använd 30 % mindre på {category}', 'Din största vardagskategori.'],
    },
    C: { Restaurants: 'restauranger', Entertainment: 'nöjen', Lifestyle: 'livsstil', Travel: 'resor', 'Home & Tech': 'hem och teknik', Transportation: 'transport', Groceries: 'matvaror', Health: 'hälsa' },
  },
};

const LOCALE = { en: 'en-IE', fi: 'fi-FI', sv: 'sv-FI' };
const fill = (text, vars) => String(text).replace(/\{(\w+)\}/g, (_, k) => (vars && vars[k] !== undefined ? vars[k] : ''));
const pageLang = () => {
  const v = (document.documentElement.lang || 'en').slice(0, 2).toLowerCase();
  return TEXT[v] ? v : 'en';
};

/** Follow the page language, so the screen re-renders when the app switches it. */
function useLang() {
  const [lang, setLang] = useState(pageLang);
  useEffect(() => {
    const watch = new MutationObserver(() => setLang(pageLang()));
    watch.observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    return () => watch.disconnect();
  }, []);
  return lang;
}

const STYLE = `
.rp { display: flex; flex-direction: column; gap: 12px; }
.rp-card { background: var(--surface, #fff); border-radius: var(--r-card, 10px); padding: 16px; }
.rp-title { font-size: 22px; font-weight: 800; letter-spacing: -0.01em; color: var(--accent, #007841); line-height: 1.15; }
.rp-sub { font-size: 14.5px; color: var(--ink-2, #4a4a4a); margin-top: 6px; }
.rp-h { font-size: 17px; font-weight: 750; color: var(--accent, #007841); margin: 6px 2px 0; }
.rp-chart { display: block; width: 100%; height: auto; }
.rp-key { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 12.5px; color: var(--ink-2, #4a4a4a); margin-top: 6px; }
.rp-key i { display: inline-block; width: 18px; height: 3px; border-radius: 2px; margin-right: 6px; vertical-align: middle; }
.rp-facts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 12px; }
.rp-facts div { min-width: 0; padding: 10px; border-radius: 8px; background: var(--surface-2, #eef6ef); }
.rp-facts dt { font-size: 12px; line-height: 1.25; color: var(--ink-2, #4a4a4a); }
.rp-facts dd { margin: 2px 0 0; font-size: 19px; font-weight: 800; letter-spacing: -0.01em; color: var(--accent, #007841); font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.rp-facts small { display: block; font-size: 11.5px; font-weight: 500; color: var(--ink-2, #4a4a4a); letter-spacing: 0; }
.rp-levers { display: flex; flex-direction: column; gap: 8px; }
.rp-lever { display: grid; grid-template-columns: 30px 1fr auto; align-items: center; gap: 12px; width: 100%; min-height: 64px; padding: 12px 14px;
  border-radius: var(--r-card, 10px); background: var(--surface, #fff); text-align: left; box-shadow: inset 0 0 0 1px transparent; transition: box-shadow 150ms ease, background-color 150ms ease; }
.rp-lever[aria-pressed="true"] { box-shadow: inset 0 0 0 2px var(--accent, #007841); }
.rp-lever:active { background: var(--surface-2, #eef6ef); }
.rp-rank { display: grid; place-items: center; width: 30px; height: 30px; border-radius: 50%; font-size: 13.5px; font-weight: 800; background: var(--surface-2, #eef6ef); color: var(--ink, #1f1f1f); }
.rp-lever[aria-pressed="true"] .rp-rank { background: var(--accent, #007841); color: #fff; }
.rp-lever strong { display: block; font-size: 15px; font-weight: 700; line-height: 1.25; color: var(--ink, #1f1f1f); }
.rp-lever small { display: block; font-size: 13px; line-height: 1.3; color: var(--ink-2, #4a4a4a); margin-top: 2px; }
.rp-lever em { font-style: normal; font-size: 16px; font-weight: 800; color: var(--accent, #007841); font-variant-numeric: tabular-nums; white-space: nowrap; }
.rp-note { font-size: 13px; color: var(--ink-2, #4a4a4a); margin: 2px 2px 0; }
.rp-hold p { font-size: 14.5px; margin-top: 6px; }
.rp-hold p + p { color: var(--ink-2, #4a4a4a); font-size: 13.5px; }
.rp-plan { display: flex; flex-direction: column; gap: 10px; }
.rp-plan p { font-size: 14.5px; }
.rp-btn { align-self: flex-start; min-height: 46px; padding: 0 22px; border-radius: 23px; background: var(--accent, #007841); color: #fff; font-weight: 700; font-size: 15px; }
.rp-btn:active { opacity: 0.8; }
.rp-link { align-self: flex-start; min-height: 44px; color: var(--accent, #007841); font-weight: 650; font-size: 14.5px; }
.rp-done { padding: 12px 14px; border-radius: 8px; background: var(--surface-2, #eef6ef); font-size: 14.5px; }
.rp-done strong { display: block; color: var(--accent, #007841); }
.rp-check { display: flex; flex-direction: column; gap: 8px; padding-top: 12px; border-top: 1px solid var(--line, rgba(0,0,0,0.1)); }
.rp-weeks { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin: 0; padding: 0; list-style: none; }
.rp-weeks li { display: flex; flex-direction: column; gap: 1px; min-width: 0; padding: 8px; border-radius: 8px; background: var(--surface-2, #eef6ef); }
.rp-weeks li.is-over { background: var(--warn-soft, #fdf1d7); }
.rp-weeks span { font-size: 11.5px; color: var(--ink-2, #4a4a4a); }
.rp-weeks strong { font-size: 15px; font-weight: 800; font-variant-numeric: tabular-nums; color: var(--ink, #1f1f1f); }
.rp-weeks small { font-size: 11.5px; line-height: 1.2; color: var(--ink-2, #4a4a4a); }
.rp-weeks li.is-over small { color: var(--warn, #8a5300); font-weight: 650; }
.rp-fade { transition: opacity 180ms ease; }
.rp-fade.is-stale { opacity: 0.55; }
@media (prefers-reduced-motion: reduce) { .rp-lever, .rp-fade { transition: none; } }
`;

function useStyle() {
  useEffect(() => {
    if (document.getElementById('rp-style')) return;
    const el = document.createElement('style');
    el.id = 'rp-style';
    el.textContent = STYLE;
    document.head.appendChild(el);
  }, []);
}

/** A "nice" step for the y axis, so the labels are round numbers. */
function niceStep(span) {
  const rough = span / 4;
  const pow = 10 ** Math.floor(Math.log10(Math.max(rough, 1)));
  const unit = rough / pow;
  return (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 5 ? 5 : 10) * pow;
}

function Chart({ series, lang, label }) {
  const weeks = series.week_starts || [];
  const actual = series.lowest_balance_each_week || [];
  const replayed = series.with_the_change || [];
  const n = Math.min(weeks.length, actual.length, replayed.length);
  if (n < 2) return null;
  const W = 340, H = 180, L = 40, R = 8, T = 10, B = 22;
  const lowest = Math.min(0, ...actual, ...replayed);
  const highest = Math.max(1, ...actual, ...replayed);
  const step = niceStep(highest - lowest);
  const lo = Math.floor(lowest / step) * step;
  const hi = Math.ceil(highest / step) * step;
  const x = (i) => L + (i / (n - 1)) * (W - L - R);
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const path = (s) => s.slice(0, n).map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  const ticks = [];
  for (let v = lo; v <= hi + 0.5; v += step) ticks.push(v);
  const short = (v) => {
    const a = Math.abs(v);
    const text = a >= 1000 ? `${(a / 1000).toLocaleString(LOCALE[lang], { maximumFractionDigits: 1 })}k` : String(Math.round(a));
    return `${v < 0 ? '−' : ''}${text} €`;
  };
  // One label at the first week of every third month.
  const marks = [];
  let lastMonth = -1;
  for (let i = 0; i < n; i += 1) {
    const d = new Date(`${weeks[i]}T00:00:00`);
    const month = d.getMonth();
    if (month !== lastMonth && month % 3 === 0 && (marks.length === 0 || i - marks[marks.length - 1].i > 8)) {
      marks.push({ i, text: d.toLocaleDateString(LOCALE[lang], { month: 'short' }).replace('.', '') });
    }
    lastMonth = month;
  }
  return html`<svg class="rp-chart" viewBox=${`0 0 ${W} ${H}`} role="img" aria-label=${label}>
    ${lo < 0 ? html`<rect x=${L} y=${y(0)} width=${W - L - R} height=${y(lo) - y(0)} fill="var(--bad-soft, #fdeae8)" />` : null}
    ${ticks.map((v) => html`<g key=${v}>
      <line x1=${L} x2=${W - R} y1=${y(v)} y2=${y(v)} stroke=${v === 0 ? 'var(--bad, #b3261e)' : 'var(--line, rgba(0,0,0,0.1))'} stroke-width="1" stroke-dasharray=${v === 0 ? '3 3' : null} />
      <text x=${L - 6} y=${y(v) + 3.5} text-anchor="end" font-size="9.5" fill="var(--ink-2, #4a4a4a)">${short(v)}</text>
    </g>`)}
    ${marks.map((m) => html`<text key=${m.i} x=${x(m.i)} y=${H - 6} text-anchor=${m.i === 0 ? 'start' : 'middle'} font-size="9.5" fill="var(--ink-2, #4a4a4a)">${m.text}</text>`)}
    <path d=${path(actual)} fill="none" stroke="var(--ink-3, #8a8f8b)" stroke-width="1.6" stroke-linejoin="round" />
    <path d=${path(replayed)} fill="none" stroke="var(--accent, #007841)" stroke-width="2.4" stroke-linejoin="round" />
    <circle cx=${x(n - 1)} cy=${y(replayed[n - 1])} r="3.6" fill="var(--accent, #007841)" />
    <circle cx=${x(n - 1)} cy=${y(actual[n - 1])} r="2.8" fill="var(--ink-3, #8a8f8b)" />
  </svg>`;
}

const PLAN_KEY = (id) => `money-mentor.plan.${id}`;

export function Replay() {
  useStyle();
  const ui = useContext(UI) || {};
  const id = (ui.who && ui.who.id) || new URLSearchParams(location.search).get('who') || '';
  const lang = useLang();
  const t = TEXT[lang];
  const [lever, setLever] = useState(null);
  const [plan, setPlan] = useState(() => {
    try { return JSON.parse(localStorage.getItem(PLAN_KEY(id)) || 'null'); } catch (e) { return null; }
  });
  const req = useApi(id ? cust(id, `/replay${lever ? `?lever=${encodeURIComponent(lever)}` : ''}`) : null);

  const money = (v, digits = 0) => new Intl.NumberFormat(LOCALE[lang], { style: 'currency', currency: 'EUR', maximumFractionDigits: digits, minimumFractionDigits: digits }).format(Number(v) || 0);
  const day = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(LOCALE[lang], { month: 'short', year: 'numeric' });
  const leverText = (entry, d) => {
    const pair = t.L[entry.lever] || [entry.title, entry.how];
    const category = d.biggest_everyday_category ? (t.C[d.biggest_everyday_category] || d.biggest_everyday_category) : '';
    return [fill(pair[0], { amount: money(d.normal_busy_week), category }), pair[1]];
  };
  const savePlan = (amount) => {
    const next = { allowance: amount, set: new Date().toISOString().slice(0, 10) };
    try { localStorage.setItem(PLAN_KEY(id), JSON.stringify(next)); } catch (e) { /* the plan still shows for this visit */ }
    setPlan(next);
  };

  return html`<div class="rp">
    <${Load} req=${req} rows=${5} tall=${true}>${(d) => {
      const shown = d.shown || {};
      const days = shown.days_below_zero || {};
      const lowest = shown.lowest_balance || {};
      const balance = shown.balance_today || {};
      const hold = d.does_it_hold;
      const period = d.period || {};
      const hadDays = Number(days.before) > 0;
      const stale = Boolean(req.loading || req.stale);
      const levers = Array.isArray(d.levers) ? d.levers : [];
      const none = (d.levers_without_effect || []).length;
      return html`
        <div class="rp-card">
          <h2 class="rp-title">${t.title}</h2>
          <p class="rp-sub">${fill(t.intro, { from: period.start ? day(period.start) : '', to: period.end ? day(period.end) : '' })}</p>
        </div>

        <div class=${`rp-card rp-fade${stale ? ' is-stale' : ''}`} data-tour="replay-chart">
          <${Chart} series=${d.series || {}} lang=${lang} label=${t.chartLabel} />
          <div class="rp-key"><span><i style="background:var(--ink-3, #8a8f8b)"></i>${t.actual}</span><span><i style="background:var(--accent, #007841)"></i>${t.replayed}</span></div>
          <dl class="rp-facts">
            <div><dt>${t.kept}</dt><dd>${money(shown.kept_over_the_year)}<small>${fill(t.perMonth, { amount: money(shown.kept_per_month) })}</small></dd></div>
            ${hadDays
              ? html`<div><dt>${t.days}</dt><dd>${days.after}<small>${fill(t.was, { n: days.before })}</small></dd></div>`
              : html`<div><dt>${t.lowest}</dt><dd>${money(lowest.after)}<small>${fill(t.was, { n: money(lowest.before) })}</small></dd></div>`}
            <div><dt>${t.today}</dt><dd>${money(balance.after)}<small>${fill(t.insteadOf, { amount: money(balance.before) })}</small></dd></div>
          </dl>
        </div>

        <h3 class="rp-h">${t.levers}</h3>
        <div class="rp-levers" data-tour="replay-levers">
          ${levers.map((entry) => {
            const [title, how] = leverText(entry, d);
            return html`<button type="button" key=${entry.lever} class="rp-lever" aria-pressed=${entry.lever === shown.lever ? 'true' : 'false'} onClick=${() => setLever(entry.lever)}>
              <span class="rp-rank">${entry.rank}</span>
              <span><strong>${title}</strong><small>${how}</small></span>
              <em>+${money(entry.kept_over_the_year)}</em>
            </button>`;
          })}
        </div>
        ${none ? html`<p class="rp-note">${fill(t.noEffect, { list: d.levers_without_effect.map((entry) => {
          const [title] = leverText(entry, d);
          return title.charAt(0).toLowerCase() + title.slice(1);
        }).join(', ') })}</p>` : null}

        ${hold ? html`<div class="rp-card rp-hold" data-tour="replay-honesty">
          <h3 class="rp-h" style="margin:0">${t.holdTitle}</h3>
          <p>${hold.top_lever_was_also_top_the_year_before ? t.holdSame : t.holdDiff}</p>
          <p>${fill(t.holdThis, { from: day(hold.year_before.start), to: day(hold.year_before.end), amount: money(hold.this_lever_kept_the_year_before), rank: hold.this_lever_rank_the_year_before })}</p>
          <p><strong>${t.readTitle}.</strong> ${t.read}</p>
        </div>` : null}

        <div class="rp-card rp-plan">
          ${d.plan ? html`
            <h3 class="rp-h" style="margin:0">${t.planTitle}</h3>
            ${plan && Number(plan.allowance) === Number(d.plan.weekly_everyday_allowance)
              ? html`<div class="rp-done" role="status"><strong>${t.planSet}</strong>${fill(t.planDone, { amount: money(plan.allowance) })}</div>`
              : html`<p>${fill(t.planText, { amount: money(d.plan.weekly_everyday_allowance) })}</p>
                  <button type="button" class="rp-btn" onClick=${() => savePlan(d.plan.weekly_everyday_allowance)}>${t.planButton}</button>`}
            ${d.plan.check_in ? html`<div class="rp-check">
              <p><strong>${t.checkTitle}.</strong> ${fill(t.checkSummary, { n: d.plan.check_in.weeks_within_ceiling })}</p>
              <ul class="rp-weeks">${(d.plan.check_in.last_four_weeks || []).map((w) => html`<li key=${w.week_start} class=${w.within_ceiling ? 'is-ok' : 'is-over'}>
                <span>${new Date(`${w.week_start}T00:00:00`).toLocaleDateString(LOCALE[lang], { day: 'numeric', month: 'short' })}</span>
                <strong>${money(w.everyday_spending)}</strong>
                <small>${w.within_ceiling ? t.weekOk : fill(t.weekOver, { amount: money(w.over_by) })}</small>
              </li>`)}</ul>
              <p class="rp-note">${fill(t.thisWeek, { spent: money(d.plan.check_in.this_week.spent_so_far), left: money(d.plan.check_in.this_week.left), days: d.plan.check_in.this_week.days_left })}</p>
            </div>` : null}` : null}
          ${ui.ask ? html`<button type="button" class="rp-link" onClick=${() => ui.ask(t.askQ)}>${t.ask} ›</button>` : null}
        </div>`;
    }}<//>
  </div>`;
}
