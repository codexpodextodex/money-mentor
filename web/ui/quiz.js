// The basket quiz: sort six of your own payments into the three baskets.
// Self-contained like replay.js: its own strings (en, fi, sv) and its own styles.
import { html, useState, useEffect, useContext, useApi, cust } from './lib.js';
import { UI, Load } from './parts.js';

const TEXT = {
  en: {
    title: 'Which basket?',
    intro: 'Six of your own payments. Tap the basket each one belongs to. It takes a minute, and afterwards the three baskets stick.',
    start: 'Start', next: 'Next', finish: 'See my result', again: 'Try again',
    of: '{i} of {n}', right: 'Right', notQuite: 'Not quite',
    scoreTitle: '{right} of {n} right',
    scoreAll: 'You read your own money the way the bank does.',
    scoreSome: 'The ones people miss are the in-between cases: a taxi, a big home purchase, the pharmacy.',
    realSplit: 'Where your money really went, last 6 months',
    open: 'See your baskets',
    empty: 'There are not enough payments in the last six months for a quiz.',
    B: { essentials: 'Regular essentials', unexpected: 'Unexpected necessities', everyday: 'Everyday spending' },
    W: {},
  },
  fi: {
    title: 'Mihin koriin?',
    intro: 'Kuusi omaa maksuasi. Napauta koria, johon kukin kuuluu. Tähän menee minuutti, ja sen jälkeen kolme koria jäävät mieleen.',
    start: 'Aloita', next: 'Seuraava', finish: 'Näytä tulokseni', again: 'Yritä uudelleen',
    of: '{i}/{n}', right: 'Oikein', notQuite: 'Ei aivan',
    scoreTitle: '{right}/{n} oikein',
    scoreAll: 'Luet omaa rahankäyttöäsi samalla tavalla kuin pankki.',
    scoreSome: 'Useimmiten väärin menevät rajatapaukset: taksi, iso kodin hankinta, apteekki.',
    realSplit: 'Mihin rahasi oikeasti menivät, viimeiset 6 kuukautta',
    open: 'Katso korisi',
    empty: 'Viimeisen kuuden kuukauden ajalta ei ole tarpeeksi maksuja kyselyä varten.',
    B: { essentials: 'Säännölliset pakolliset', unexpected: 'Yllättävät pakolliset', everyday: 'Arjen kulutus' },
    W: {
      taxi: 'Taksi on oma valintasi, joten se on arjen kulutusta, vaikka muu liikkuminen on pakollista.',
      home_small: 'Pienempi kodin ja tekniikan ostos on oma valintasi: arjen kulutusta.',
      eating_out: 'Ulkona syöminen on oma valintasi: arjen kulutusta.',
      fun: 'Tämä on oma valintasi, sitä rahaa joka valuu sormien läpi: arjen kulutusta.',
      home_big: 'Vähintään 300 euron kodin ja tekniikan ostos tarkoittaa, että jotain korvataan tai korjataan: yllättävä pakollinen meno.',
      health: 'Terveysmenot ovat välttämättömiä, mutta niiden ajankohtaa ei voi suunnitella: yllättävä pakollinen meno.',
      transport_big: 'Vähintään 300 euron liikennemaksu näyttää korjaukselta: yllättävä pakollinen meno.',
      housing: 'Asuminen on säännöllinen pakollinen meno: se on maksettava, ja tiedät milloin.',
      bills: 'Sähkö, vesi ja muut laskut ovat säännöllisiä pakollisia menoja: ne tulevat joka kuukausi.',
      groceries: 'Ruokaostokset ovat säännöllinen pakollinen meno.',
      transport: 'Liikkuminen (joukkoliikenne, polttoaine, pysäköinti) on säännöllinen pakollinen meno.',
    },
  },
  sv: {
    title: 'Vilken korg?',
    intro: 'Sex av dina egna betalningar. Tryck på korgen som var och en hör till. Det tar en minut, och efteråt sitter de tre korgarna.',
    start: 'Börja', next: 'Nästa', finish: 'Visa mitt resultat', again: 'Försök igen',
    of: '{i} av {n}', right: 'Rätt', notQuite: 'Inte riktigt',
    scoreTitle: '{right} av {n} rätt',
    scoreAll: 'Du läser dina egna pengar på samma sätt som banken.',
    scoreSome: 'De som oftast blir fel är gränsfallen: en taxi, ett stort köp till hemmet, apoteket.',
    realSplit: 'Vart dina pengar faktiskt gick, senaste 6 månaderna',
    open: 'Se dina korgar',
    empty: 'Det finns inte tillräckligt många betalningar från de senaste sex månaderna för ett quiz.',
    B: { essentials: 'Regelbundna nödvändiga', unexpected: 'Oväntade nödvändiga', everyday: 'Vardagskonsumtion' },
    W: {
      taxi: 'En taxi är ditt eget val, så den är vardagskonsumtion, fast annan transport är nödvändig.',
      home_small: 'Ett mindre köp till hem och teknik är ditt eget val: vardagskonsumtion.',
      eating_out: 'Att äta ute är ditt eget val: vardagskonsumtion.',
      fun: 'Det här är ditt eget val, den sortens pengar som rinner mellan fingrarna: vardagskonsumtion.',
      home_big: 'Ett köp till hem och teknik på minst 300 euro betyder att något ersätts eller repareras: en oväntad nödvändig utgift.',
      health: 'Hälsokostnader är nödvändiga, men du kan inte planera när de kommer: en oväntad nödvändig utgift.',
      transport_big: 'En transportbetalning på minst 300 euro ser ut som en reparation: en oväntad nödvändig utgift.',
      housing: 'Boendet är en regelbunden nödvändig utgift: du måste betala, och du vet när.',
      bills: 'El, vatten och andra räkningar är regelbundna nödvändiga utgifter: de kommer varje månad.',
      groceries: 'Matvaror är en regelbunden nödvändig utgift.',
      transport: 'Att ta sig fram (kollektivtrafik, bränsle, parkering) är en regelbunden nödvändig utgift.',
    },
  },
};

const LOCALE = { en: 'en-IE', fi: 'fi-FI', sv: 'sv-FI' };
const ORDER = ['essentials', 'unexpected', 'everyday'];
const fill = (text, vars) => String(text).replace(/\{(\w+)\}/g, (_, k) => (vars && vars[k] !== undefined ? vars[k] : ''));
const pageLang = () => {
  const v = (document.documentElement.lang || 'en').slice(0, 2).toLowerCase();
  return TEXT[v] ? v : 'en';
};

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
.qz { display: flex; flex-direction: column; gap: 12px; }
.qz-card { background: var(--surface, #fff); border-radius: var(--r-card, 10px); padding: 16px; display: flex; flex-direction: column; gap: 10px; }
.qz-title { font-size: 22px; font-weight: 800; letter-spacing: -0.01em; color: var(--accent, #007841); line-height: 1.15; }
.qz-text { font-size: 15px; color: var(--ink-2, #4a4a4a); }
.qz-step { font-size: 12.5px; font-weight: 650; color: var(--ink-2, #4a4a4a); font-variant-numeric: tabular-nums; }
.qz-pay { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 14px; border-radius: 8px; background: var(--surface-2, #eef6ef); }
.qz-pay strong { font-size: 17px; font-weight: 750; color: var(--ink, #1f1f1f); }
.qz-pay small { display: block; font-size: 13px; color: var(--ink-2, #4a4a4a); }
.qz-pay em { font-style: normal; font-size: 22px; font-weight: 800; color: var(--ink, #1f1f1f); font-variant-numeric: tabular-nums; white-space: nowrap; }
.qz-opts { display: flex; flex-direction: column; gap: 8px; }
.qz-opt { display: flex; align-items: center; gap: 12px; width: 100%; min-height: 56px; padding: 10px 14px; border-radius: 10px; text-align: left;
  background: var(--surface, #fff); box-shadow: inset 0 0 0 1.5px var(--line, rgba(0,0,0,0.14)); font-size: 15.5px; font-weight: 650; color: var(--ink, #1f1f1f);
  transition: box-shadow 150ms ease, background-color 150ms ease, transform 120ms ease; }
.qz-opt:active:not(:disabled) { transform: scale(0.985); }
.qz-opt i { font-style: normal; font-size: 20px; }
.qz-opt.is-right { box-shadow: inset 0 0 0 2px var(--good, #007841); background: var(--good-soft, #e1f3e9); }
.qz-opt.is-wrong { box-shadow: inset 0 0 0 2px var(--bad, #b3261e); background: var(--bad-soft, #fdeae8); }
.qz-opt:disabled { cursor: default; }
.qz-why { padding: 12px 14px; border-radius: 8px; background: var(--surface-2, #eef6ef); font-size: 14.5px; }
.qz-why strong { display: block; }
.qz-why.is-right strong { color: var(--good, #007841); }
.qz-why.is-wrong strong { color: var(--bad, #b3261e); }
.qz-btn { align-self: flex-start; min-height: 46px; padding: 0 22px; border-radius: 23px; background: var(--accent, #007841); color: #fff; font-weight: 700; font-size: 15px; }
.qz-btn:active { opacity: 0.8; }
.qz-link { align-self: flex-start; min-height: 44px; color: var(--accent, #007841); font-weight: 650; font-size: 14.5px; }
.qz-score { font-size: 34px; font-weight: 800; letter-spacing: -0.02em; color: var(--accent, #007841); line-height: 1.1; }
.qz-bar { display: flex; gap: 2px; height: 12px; border-radius: 6px; overflow: hidden; }
.qz-bar span { display: block; height: 100%; }
.qz-legend { display: flex; flex-direction: column; gap: 6px; margin: 0; padding: 0; list-style: none; font-size: 14px; }
.qz-legend li { display: flex; justify-content: space-between; gap: 12px; font-variant-numeric: tabular-nums; }
.qz-legend b { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 8px; }
@media (prefers-reduced-motion: reduce) { .qz-opt { transition: none; } }
`;

function useStyle() {
  useEffect(() => {
    if (document.getElementById('qz-style')) return;
    const el = document.createElement('style');
    el.id = 'qz-style';
    el.textContent = STYLE;
    document.head.appendChild(el);
  }, []);
}

const COLOR = { essentials: 'var(--b-essentials, #2a78d6)', unexpected: 'var(--b-unexpected, #e08a00)', everyday: 'var(--b-everyday, #c9457a)' };

export function BasketQuiz() {
  useStyle();
  const ui = useContext(UI) || {};
  const id = (ui.who && ui.who.id) || new URLSearchParams(location.search).get('who') || '';
  const lang = useLang();
  const t = TEXT[lang];
  const req = useApi(id ? cust(id, '/quiz') : null);
  const [at, setAt] = useState(-1); // -1 intro, 0..n-1 questions, n result
  const [answers, setAnswers] = useState([]);

  const money = (v) => new Intl.NumberFormat(LOCALE[lang], { style: 'currency', currency: 'EUR' }).format(Number(v) || 0);
  const day = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(LOCALE[lang], { day: 'numeric', month: 'long' });
  const restart = () => { setAnswers([]); setAt(0); };

  return html`<div class="qz">
    <${Load} req=${req} rows=${4}>${(d) => {
      const questions = Array.isArray(d.questions) ? d.questions : [];
      const emoji = Object.fromEntries((d.baskets || []).map((b) => [b.basket, b.emoji]));
      const n = questions.length;
      if (n < 3) return html`<div class="qz-card"><h2 class="qz-title">${t.title}</h2><p class="qz-text">${t.empty}</p></div>`;

      if (at < 0) {
        return html`<div class="qz-card">
          <h2 class="qz-title">${t.title}</h2>
          <p class="qz-text">${t.intro}</p>
          <button type="button" class="qz-btn" onClick=${() => setAt(0)}>${t.start}</button>
        </div>`;
      }

      if (at >= n) {
        const right = answers.filter((a, i) => a === questions[i].basket).length;
        const split = Array.isArray(d.your_real_split) ? d.your_real_split : [];
        return html`<div class="qz-card" role="status">
          <p class="qz-score">${fill(t.scoreTitle, { right, n })}</p>
          <p class="qz-text">${right === n ? t.scoreAll : t.scoreSome}</p>
        </div>
        <div class="qz-card">
          <p class="qz-step">${t.realSplit}</p>
          <div class="qz-bar" role="img" aria-label=${split.map((s) => `${t.B[s.basket]} ${Math.round(s.share_pct)}%`).join(', ')}>
            ${split.map((s) => html`<span key=${s.basket} style=${`width:${Math.max(s.share_pct, 1)}%;background:${COLOR[s.basket]}`}></span>`)}
          </div>
          <ul class="qz-legend">${split.map((s) => html`<li key=${s.basket}><span><b style=${`background:${COLOR[s.basket]}`}></b>${emoji[s.basket] || ''} ${t.B[s.basket]}</span><span>${money(s.total)} · ${Math.round(s.share_pct)} %</span></li>`)}</ul>
          ${ui.go ? html`<button type="button" class="qz-btn" onClick=${() => ui.go('trainer')}>${t.open}</button>` : null}
          <button type="button" class="qz-link" onClick=${restart}>${t.again}</button>
        </div>`;
      }

      const q = questions[at];
      const given = answers[at];
      const answered = given !== undefined;
      const correct = given === q.basket;
      return html`<div class="qz-card">
        <span class="qz-step">${fill(t.of, { i: at + 1, n })}</span>
        <div class="qz-pay">
          <span><strong>${q.what}</strong><small>${day(q.date)}</small></span>
          <em>${money(q.amount)}</em>
        </div>
        <div class="qz-opts" role="group" aria-label=${t.title}>
          ${ORDER.map((b) => html`<button type="button" key=${b} disabled=${answered}
            class=${`qz-opt${answered && b === q.basket ? ' is-right' : ''}${answered && b === given && !correct ? ' is-wrong' : ''}`}
            onClick=${() => setAnswers((list) => { const next = list.slice(); next[at] = b; return next; })}>
            <i aria-hidden="true">${emoji[b] || ''}</i>${t.B[b]}
          </button>`)}
        </div>
        ${answered ? html`<div class=${`qz-why ${correct ? 'is-right' : 'is-wrong'}`} role="status">
          <strong>${correct ? t.right : t.notQuite}</strong>${t.W[q.kind] || q.why}
        </div>
        <button type="button" class="qz-btn" onClick=${() => setAt(at + 1)}>${at + 1 >= n ? t.finish : t.next}</button>` : null}
      </div>`;
    }}<//>
  </div>`;
}
