// The host app's own screens: Home, S-Etukortti, Bank, Me, the message centre and the account page.
// Everything personal on them comes from the API for the chosen demo customer; the rest is inert.
import {
  html, useState, useRef, useContext, useApi, useTool, cust,
  eur, fmtDate, nice, initials, t, has, useLang, getLang, LANGS, LANG_NAMES,
} from './lib.js';
import {
  UI, Icon, BrandMark, Wordmark, CardGlyph, Amount, Row, Segmented, Skeleton, ErrorBox, Empty, TxList,
} from './parts.js';

const FAKE_IBAN = 'FI00 0000 0000 0000 00';
const FAKE_CARD = '•••• 0000';

/** The demo customer's name: translated for the eight personas, otherwise as given. */
export function whoName(who) {
  const key = `persona.${who.id}.label`;
  if (getLang() !== 'en' && has(key)) return t(key);
  return who.label || t('who.customer', { n: String(who.id).replace(/^CUST0*/, '') || who.id });
}
export function whoBlurb(who) {
  const key = `persona.${who.id}.blurb`;
  if (getLang() !== 'en' && has(key)) return t(key);
  return who.blurb || '';
}

export const SAFE_STATUS = {
  comfortable: { key: 'status.comfortable', tone: 'good', icon: 'check' },
  on_track: { key: 'status.on_track', tone: 'good', icon: 'check' },
  tight: { key: 'status.tight', tone: 'warn', icon: 'alert' },
  over_budget: { key: 'status.over_budget', tone: 'bad', icon: 'alert' },
  short: { key: 'status.short', tone: 'bad', icon: 'alert' },
};

const noticeCount = (req) => (req.data && Array.isArray(req.data.notices) ? req.data.notices.length : null);

/* ---------- Home ---------- */

function HeroCarousel({ overview }) {
  const ui = useContext(UI);
  const track = useRef(null);
  const [at, setAt] = useState(0);
  const o = overview.data;
  const safe = o && o.safe_to_spend;
  const week = (safe && safe.this_week) || {};
  const pay = (safe && safe.pay_period) || {};
  const st = safe ? SAFE_STATUS[safe.status] : null;
  const perDay = Number(safe && safe.safe_per_day);

  const onScroll = () => {
    const el = track.current;
    if (el && el.clientWidth) setAt(Math.round(el.scrollLeft / el.clientWidth));
  };
  const show = (i) => {
    const el = track.current;
    if (el) el.scrollTo({ left: i * el.clientWidth, behavior: 'smooth' });
  };

  let line = '';
  if (safe) {
    const parts = [st ? t(st.key) : null];
    if (perDay > 0) parts.push(t('home.per_day', { amount: eur(perDay, 'whole'), date: fmtDate(pay.next_payday) }));
    else if (pay.next_payday) parts.push(t('home.payday', { date: fmtDate(pay.next_payday) }));
    line = parts.filter(Boolean).join(' · ');
  }

  return html`<section class="hero" aria-roledescription="carousel" aria-label=${t('home.hero_aria')}>
    <div class="hero__track" ref=${track} onScroll=${onScroll}>
      <div class="hero__slide" role="group" aria-label="1 / 2">
        <div class="hero__body" data-tour="home-trainer">
          <span class="hero__shape" aria-hidden="true"></span>
          <span class="hero__icon" aria-hidden="true"><${Icon} name="whistle" size=${34} stroke=${1.300} /></span>
          ${overview.error && !o ? html`
            <p class="hero__label">${t('trainer.title')}</p>
            <p class="hero__status">${overview.error.message}</p>
            <button type="button" class="textlink" onClick=${overview.reload}><${Icon} name="refresh" size=${18} />${t('common.try_again')}</button>`
          : !o ? html`
            <p class="hero__label">${t('home.safe_label')}</p>
            <span class="hero__skel" role="status" aria-label=${t('common.loading')}></span>
            <span class="hero__skel hero__skel--line"></span>`
          : safe ? html`
            <p class="hero__label">${t('home.safe_label')}</p>
            <p class=${'hero__num' + (st && st.tone === 'bad' && !(Number(week.safe_to_spend) > 0) ? ' is-zero' : '')}><${Amount} value=${week.safe_to_spend} mode="whole" /></p>
            <p class="hero__status">${st ? html`<i class=${'statusdot is-' + st.tone} aria-hidden="true"></i>` : null}${line}</p>`
          : html`
            <p class="hero__label">${t('trainer.title')}</p>
            <p class="hero__status">${t('trainer.no_safe_title')}</p>`}
          <button type="button" class="textlink textlink--lg" onClick=${() => ui.go('trainer')}>${t('home.open_trainer')}<${Icon} name="right" size=${22} /></button>
        </div>
      </div>
      <div class="hero__slide" role="group" aria-label="2 / 2">
        <div class="hero__body">
          <span class="hero__shape" aria-hidden="true"></span>
          <span class="hero__icon" aria-hidden="true"><${BrandMark} size=${34} /></span>
          <p class="hero__label">${t('home.bonus_title')}</p>
          <p class="hero__status hero__status--calm">${t('home.bonus_text')}</p>
        </div>
      </div>
    </div>
    <div class="hero__dots">
      ${[0, 1].map((i) => html`<button type="button" key=${i} class=${at === i ? 'is-on' : ''} aria-label=${`${i + 1} / 2`} aria-current=${at === i ? 'true' : undefined} onClick=${() => show(i)}></button>`)}
    </div>
  </section>`;
}

export function HomeTab() {
  const ui = useContext(UI);
  const id = ui.who.id;
  const overview = useApi(cust(id, '/overview'));
  const notices = useApi(cust(id, '/notices'));
  const latest = useTool(id, 'list_transactions', { period: 'last_12_months', limit: 5, sort: 'date' });
  const [cards, setCards] = useState(true);
  const n = noticeCount(notices);
  const o = overview.data;
  const list = latest.data && Array.isArray(latest.data.transactions) ? latest.data.transactions : null;

  return html`<div class="hometab">
    <${HeroCarousel} overview=${overview} />
    <div class="stack">
      <div class="group">
        <${Row} icon="whistle" title=${t('trainer.title')} badge=${n ? String(n) : null} chevron=${false}
          sub=${n === null ? (notices.error ? t('home.open_trainer') : t('home.notice_loading')) : n === 0 ? t('home.notice_none') : t('home.notice_n', { n })}
          onClick=${() => ui.go('trainer')} />
      </div>
      <div class="group">
        <${Row} icon="mail" title=${t('home.bank_messages')} chevron=${false} onClick=${() => ui.demo()} />
      </div>

      <div class="actions">
        <button type="button" class="action" onClick=${() => ui.go('ask')}><span class="action__dot"><${Icon} name="chat" size=${26} /></span><span>${t('home.ask')}</span></button>
        <button type="button" class="action" onClick=${() => ui.go('find')}><span class="action__dot"><${Icon} name="search" size=${26} /></span><span>${t('home.find')}</span></button>
        <button type="button" class="action" onClick=${() => ui.demo()}><span class="action__dot"><${Icon} name="plus" size=${28} /></span><span>${t('home.new_payment')}</span></button>
      </div>

      <section aria-labelledby="home-acc">
        <h2 id="home-acc" class="sect">${t('home.accounts')}</h2>
        <div class="group">
          <${Row} icon="book" title="S-Tili" chevron=${false} onClick=${() => ui.go('account')}
            value=${o ? html`<strong class=${'money' + (Number(o.balance) < 0 ? ' is-bad' : '')}>${eur(o.balance, 'cents')}</strong>` : overview.error ? '–' : html`<span class="skel__line skel__line--value"></span>`} />
          ${cards ? html`<${Row} icon=${html`<${CardGlyph} solid=${true} />`} title="S-Etukortti Visa" sub=${`Debit ${FAKE_CARD}`} chevron=${false} onClick=${() => ui.demo()} />` : null}
          <button type="button" class="group__more" aria-expanded=${cards ? 'true' : 'false'} onClick=${() => setCards(!cards)}>${cards ? t('common.hide') : t('common.show_more')}</button>
        </div>
      </section>

      <section aria-labelledby="home-tx">
        <h2 id="home-tx" class="sect">${t('home.latest')}</h2>
        <div class="group group--pad">
          ${latest.error && !list ? html`<${ErrorBox} error=${latest.error} onRetry=${latest.reload} />` : null}
          ${!list && !latest.error ? html`<${Skeleton} rows=${5} />` : null}
          ${list ? html`<${TxList} signed=${true} transactions=${list.map((x) => ({ ...x, amount: -Math.abs(Number(x.amount) || 0) }))} />` : null}
          <button type="button" class="group__more" onClick=${() => ui.go('account')}>${t('home.show_all')}</button>
        </div>
      </section>

      <p class="endnote">${t('demo.endnote')}</p>
    </div>
  </div>`;
}

/* ---------- the account page ---------- */

const SEG_WHERE = { all: '', in: 'WHERE amount > 0', out: 'WHERE amount < 0' };

export function Account() {
  const ui = useContext(UI);
  const id = ui.who.id;
  const overview = useApi(cust(id, '/overview'));
  const [seg, setSeg] = useState('all');
  const sql = `SELECT date, amount, category, subcategory, basket, flow FROM my_transactions ${SEG_WHERE[seg]} ORDER BY time DESC LIMIT 40`.replace(/\s+/g, ' ');
  const req = useTool(id, 'run_sql', { sql });
  const o = overview.data;

  let rows = null;
  if (req.data && Array.isArray(req.data.rows)) {
    const cols = req.data.columns || [];
    rows = req.data.rows.map((r) => Object.fromEntries(cols.map((c, i) => [c, r[i]])));
  }

  return html`<div class="acct">
    <div class="acct__head">
      <h2 class="acct__name">S-Tili</h2>
      <p class="acct__kind">${t('account.kind')}</p>
      <p class=${'acct__bal' + (o && Number(o.balance) < 0 ? ' is-bad' : '')}>
        ${o ? html`<${Amount} value=${o.balance} mode="cents" />` : overview.error ? '–' : html`<span class="hero__skel"></span>`}
      </p>
      <div class="iban">
        <span>${FAKE_IBAN}</span>
        <button type="button" class="iconbtn" aria-label=${t('account.copy')} onClick=${() => ui.demo(t('account.iban_fake'))}><${Icon} name="copy" size=${22} /></button>
      </div>
      <${Segmented} label=${t('account.show')} value=${seg} onChange=${setSeg}
        options=${[['all', t('account.all')], ['in', t('account.income')], ['out', t('account.expenses')]]} />
      <button type="button" class="findrow" onClick=${() => ui.go('find')}>
        <${Icon} name="search" size=${22} /><span>${t('home.find')}</span><${Icon} name="right" size=${20} />
      </button>
    </div>
    <h3 class="acct__band">${t('account.transactions')}</h3>
    <div class=${'acct__list' + (req.loading && rows ? ' is-stale' : '')} aria-live="polite">
      ${req.error && !rows ? html`<${ErrorBox} error=${req.error} onRetry=${req.reload} />` : null}
      ${!rows && !req.error ? html`<${Skeleton} rows=${8} />` : null}
      ${rows && rows.length ? html`<${TxList} signed=${true} transactions=${rows} />` : null}
      ${rows && !rows.length ? html`<${Empty} icon="receipt" title=${t(seg === 'in' ? 'account.none_in' : 'account.none')}>${t('account.none_text')}<//>` : null}
    </div>
    ${rows && rows.length ? html`<p class="endnote">${t('account.shown', { n: rows.length })}</p>` : null}
  </div>`;
}

/* ---------- S-Etukortti ---------- */

export function CardTab() {
  const ui = useContext(UI);
  return html`<div class="cardtab">
    <header class="cardtab__top">
      <div class="cardtab__demo"><span class="demo demo--on-green">${t('common.demo')}</span></div>
      <div class="cardtab__card">
        <${BrandMark} size=${38} />
        <h1 class="display">S-Etukortti</h1>
        <button type="button" class="cardtab__scan" aria-label=${t('card.show_card')} onClick=${() => ui.demo()}><${Icon} name="barcode" size=${24} /></button>
      </div>
    </header>
    <div class="stack">
      <div class="tiles tiles--2">
        <button type="button" class="tile" onClick=${() => ui.demo()}><${Icon} name="bag" size=${28} stroke=${1.400} /><span>${t('card.bonus')}</span></button>
        <button type="button" class="tile" onClick=${() => ui.demo()}><${Icon} name="receipt" size=${28} stroke=${1.400} /><span>${t('card.receipts')}</span></button>
      </div>
      <div class="group group--pad calm">
        <span class="calm__icon" aria-hidden="true"><${Icon} name="info" size=${24} /></span>
        <div>
          <strong>${t('card.calm_title')}</strong>
          <p>${t('card.calm_text')}</p>
          <button type="button" class="textlink" onClick=${() => ui.go('trainer')}>${t('home.open_trainer')}<${Icon} name="right" size=${18} /></button>
        </div>
      </div>
    </div>
  </div>`;
}

/* ---------- Bank ---------- */

function BankCard({ icon, title, lines = [], muted, chip, tag, onClick, tour }) {
  return html`<button type="button" class="bankcard" data-tour=${tour} onClick=${onClick}>
    <span class="bankcard__icon" aria-hidden="true">${typeof icon === 'string' ? html`<${Icon} name=${icon} size=${54} stroke=${0.800} />` : icon}</span>
    <span class="bankcard__body">
      <span class="bankcard__title">${title}${tag ? html`<em class="newchip">${tag}</em>` : null}</span>
      ${lines.filter(Boolean).map((l, i) => html`<span class="bankcard__line" key=${i}>${l}</span>`)}
      ${muted ? html`<span class="bankcard__muted">${muted}</span>` : null}
      ${chip ? html`<span class="warnchip"><${Icon} name="alert" size=${16} />${chip}</span>` : null}
    </span>
    <span class="bankcard__chev" aria-hidden="true"><${Icon} name="right" size=${22} stroke=${1.800} /></span>
  </button>`;
}

export function BankTab() {
  const ui = useContext(UI);
  const id = ui.who.id;
  const overview = useApi(cust(id, '/overview'));
  const notices = useApi(cust(id, '/notices'));
  const loan = useApi(cust(id, '/mortgage'));
  const o = overview.data;
  const safe = o && o.safe_to_spend;
  const st = safe ? SAFE_STATUS[safe.status] : null;
  const n = noticeCount(notices);
  const inert = () => ui.demo();

  const trainerLine = safe
    ? t('bank.trainer_line', { amount: eur(safe.this_week && safe.this_week.safe_to_spend, 'whole') })
    : overview.error ? t('bank.trainer_fallback') : o ? t('bank.trainer_fallback') : t('common.loading');

  return html`<div class="stack stack--bank">
    <${BankCard} icon="book" title=${t('bank.accounts')} lines=${['S-Tili']} muted=${o ? eur(o.balance, 'cents') : null} onClick=${() => ui.go('account')} />
    <${BankCard} icon="invoice" title=${t('bank.payments')} muted=${t('bank.payments_sub')} onClick=${inert} />
    <${BankCard} icon=${html`<span class="bankcard__cardglyph"><${CardGlyph} /></span>`} title=${t('bank.cards')} lines=${['S-Etukortti Visa']} muted=${`Debit ${FAKE_CARD}`} onClick=${inert} />
    <${BankCard} icon="whistle" title=${t('trainer.title')} tag=${t('common.new')} tour="bank-trainer"
      lines=${[trainerLine]}
      muted=${n ? t('home.notice_n', { n }) : n === 0 ? t('home.notice_none') : null}
      chip=${st && st.tone !== 'good' ? t(st.key) : null}
      onClick=${() => ui.go('trainer')} />
    <${BankCard} icon="trophy" title="Säästäjä" lines=${[t('bank.saver_sub')]} onClick=${inert} />
    <${BankCard} icon="invest" title=${t('bank.investments')} lines=${[t('bank.investments_sub')]} onClick=${inert} />
    <${BankCard} icon="loandoc" title=${t('bank.loans')} lines=${[t('bank.loans_sub')]}
      muted=${loan.data && loan.data.readiness ? nice(loan.data.readiness) : null} onClick=${() => ui.go('loan')} />
    <${BankCard} icon="salary" title=${t('bank.salary')} lines=${[t('bank.salary_sub')]} onClick=${inert} />
    <p class="endnote">${t('demo.endnote')}</p>
  </div>`;
}

/* ---------- Me ---------- */

export function MeTab() {
  const ui = useContext(UI);
  const name = whoName(ui.who);
  return html`<div class="me">
    <header class="me__head">
      <span class="me__avatar" aria-hidden="true">${initials(name)}</span>
      <h2 class="display me__name">${name}</h2>
      <p class="me__sub">${t('me.sub')}</p>
    </header>
    <div class="stack">
      <div class="group">
        <${Row} icon="swap" title=${t('me.switch')} sub=${whoBlurb(ui.who) || ui.who.id} onClick=${ui.openSwitch} />
        <${Row} icon="globe" title=${t('me.language')} value=${LANG_NAMES[ui.lang] || ui.lang} onClick=${ui.openLanguage} />
        <${Row} icon="info" title=${t('me.about')} onClick=${ui.openAbout} />
      </div>
      <section aria-labelledby="me-app">
        <h2 id="me-app" class="sect">${t('me.settings')}</h2>
        <div class="group">
          <${Row} icon="phone" title=${t('me.version')} value=${t('me.version_value')} />
          <${Row} icon="bell" title=${t('me.notifications')} onClick=${() => ui.demo()} />
          <${Row} icon="doc" title=${t('me.terms')} onClick=${() => ui.demo()} />
          <${Row} icon="shield" title=${t('me.privacy')} onClick=${() => ui.demo()} />
          <${Row} icon="logout" title=${t('home.logout')} onClick=${() => ui.demo()} />
        </div>
      </section>
      <div class="me__foot"><${Wordmark} height=${26} /></div>
      <p class="endnote">${t('demo.endnote')}</p>
    </div>
  </div>`;
}

export function LanguageBody({ onPick }) {
  const lang = useLang();
  return html`<ul class="options">
    ${LANGS.map((l) => html`<li key=${l}>
      <button type="button" class=${'option' + (l === lang ? ' is-active' : '')} aria-pressed=${l === lang ? 'true' : 'false'} lang=${l} onClick=${() => onPick(l)}>
        <span>${LANG_NAMES[l]}</span>${l === lang ? html`<${Icon} name="check" size=${22} />` : null}
      </button>
    </li>`)}
  </ul>`;
}

export function AboutBody() {
  useLang();
  return html`<div class="about">
    <p class="lead">${t('about.lead')}</p>
    <ul class="about__list">
      <li><${Icon} name="whistle" size=${22} /><span><strong>${t('about.what_title')}</strong>${t('about.what')}</span></li>
      <li><${Icon} name="db" size=${22} /><span><strong>${t('about.data_title')}</strong>${t('about.data')}</span></li>
      <li><${Icon} name="shield" size=${22} /><span><strong>${t('about.safe_title')}</strong>${t('about.safe')}</span></li>
      <li><${Icon} name="info" size=${22} /><span><strong>${t('about.brand_title')}</strong>${t('about.brand')}</span></li>
    </ul>
  </div>`;
}

/* ---------- message centre ---------- */

export function Messages() {
  const ui = useContext(UI);
  return html`<div class="stack">
    <div class="group">
      <${Row} icon="chat" title=${t('messages.assistant')} sub=${t('messages.assistant_sub')} tour="assistant-entry" onClick=${() => ui.go('ask')} />
      <${Row} icon="info" title=${t('messages.faq')} external=${true} onClick=${() => ui.demo()} />
      <${Row} icon="star" title=${t('messages.feedback')} onClick=${() => ui.demo()} />
    </div>
    <section aria-labelledby="msg-cs">
      <h2 id="msg-cs" class="sect">${t('messages.service')}</h2>
      <div class="group">
        <${Row} icon="mail" title=${t('messages.bank')} sub=${t('messages.bank_sub')} onClick=${() => ui.demo()} />
        <${Row} icon="doc" title=${t('messages.dispute')} onClick=${() => ui.demo()} />
      </div>
    </section>
    <p class="endnote">${t('demo.endnote')}</p>
  </div>`;
}
