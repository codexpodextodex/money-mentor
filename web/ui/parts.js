// Shared building blocks: icons, the brand mark, cards, sheets and the hand-drawn charts.
import {
  html, useState, useEffect, useRef, createContext,
  BASKETS, BASKET_ORDER, basketOf, eur, eurSigned, eurShort, num, pct,
  fmtDate, fmtMonth, nice, words, clamp, useApi, t, tv, has, useLang,
} from './lib.js';

/** App-wide handles: the customer, today's date, navigation and the bottom sheet. */
export const UI = createContext({});

/* ---------- icons: green outline, 24 grid ---------- */

const PATHS = {
  // navigation and actions
  chevron: 'M6 9l6 6 6-6',
  right: 'M9.5 5.5 16 12l-6.500 6.500',
  back: 'M14.500 5.500 8 12l6.500 6.500',
  close: 'M6 6l12 12M18 6 6 18',
  check: 'M5 12.500l4.500 4.500L19 7.500',
  plus: 'M12 5v14 M5 12h14',
  half: 'M6 12h12',
  circle: 'M12 6a6 6 0 1 0 0 12 6 6 0 0 0 0-12z',
  up: 'M12 19V5 M6 11l6-6 6 6',
  down: 'M12 5v14 M6 13l6 6 6-6',
  send: 'M12 19V6 M6.500 11.500 12 6l5.500 5.500',
  refresh: 'M19 12a7 7 0 1 1-2.100-5 M19 5v4h-4',
  swap: 'M7 8h11l-3-3 M17 16H6l3 3',
  external: 'M13.500 5H19v5.500 M19 5l-7.500 7.500 M10.500 6.500h-5V19h12.500v-5',
  copy: 'M9 8.500h10V20H9z M6.500 15.500h-1.500V4h10.500v1.500',
  logout: 'M10.500 4.500H6a1 1 0 0 0-1 1v13a1 1 0 0 0 1 1h4.500 M14.500 8.500 18 12l-3.500 3.500 M18 12H9.500',
  search: 'M10.500 4.500a6 6 0 1 0 0 12 6 6 0 0 0 0-12z M15 15l4.500 4.500',
  list: 'M9 7h10 M9 12h10 M9 17h10 M5 7h.010 M5 12h.010 M5 17h.010',
  play: 'M8 5.500v13l10-6.500z',
  calendar: 'M5 6h14v13.500H5z M5 10h14 M8.500 4v3.500 M15.500 4v3.500',

  // states
  alert: 'M12 4.500 3 19.500h18z M12 10.500v4 M12 17v.200',
  info: 'M12 3.500a8.500 8.500 0 1 0 0 17 8.500 8.500 0 0 0 0-17z M12 11v5 M12 7.900v.200',
  shield: 'M12 3.500 5 6v5.500c0 4.200 2.900 7.300 7 9 4.100-1.700 7-4.800 7-9V6z M9 12l2.200 2.200L15 10.400',
  lock: 'M7 10.500h10a1 1 0 0 1 1 1V19a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-7.500a1 1 0 0 1 1-1z M8.500 10.500V8a3.500 3.500 0 0 1 7 0v2.500 M12 14.300v1.900',
  spark: 'M12 4l1.800 4.700L18.500 10.500l-4.700 1.800L12 17l-1.800-4.700L5.500 10.500l4.700-1.800z M18.500 16v3 M17 17.500h3',

  // host app
  home: 'M4 10.700 12 4.250l8 6.450V20h-5.500v-5.500h-5V20H4z',
  wallet: 'M4.500 8h15a1 1 0 0 1 1 1v9.500a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z M6 8l9.700-2.700a.900.900 0 0 1 1.150.860V8 M16.600 13.750h.010',
  person: 'M12 4.250a3.250 3.250 0 1 0 0 6.500 3.250 3.250 0 0 0 0-6.500z M5.500 20v-1.250a5 5 0 0 1 5-5h3a5 5 0 0 1 5 5V20z',
  mail: 'M4 6.500h16v11H4z M4 6.500l8 6.500 8-6.500 M4 17.500l5.800-5.700 M20 17.500l-5.800-5.700',
  chat: 'M5.500 6a1 1 0 0 1 1-1h11a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-8l-4 3.200z',
  book: 'M6 4.500h11.500v13H7.250A1.250 1.250 0 0 0 6 18.750z M6 18.750A1.250 1.250 0 0 0 7.250 20H17.500 M9.500 8.250h5 M9.500 11.250h5',
  invoice: 'M6.500 3.500h11v17h-11z M9.500 14.500h5 M9.500 17.250h5 M14 7.300a2.300 2.300 0 1 0 0 3.900 M9.500 8.600h2.800 M9.500 10h2.500',
  card: 'M4 6.500h16v11H4z M4 10h16 M7 14.500h4',
  trophy: 'M8 4.500h8v5a4 4 0 0 1-8 0z M8 6H5.500v1.500A2.500 2.500 0 0 0 8 10 M16 6h2.500v1.500A2.500 2.500 0 0 1 16 10 M12 13.500V17 M9 19.500h6V17H9z',
  invest: 'M4 8.500h16V19H4z M9 8.500V6.200a.700.700 0 0 1 .700-.700h4.600a.700.700 0 0 1 .700.700v2.300 M7 15.500l3-2.500 2.500 1.500 4-3.500',
  loandoc: 'M14.500 9.500V4h-9v15.500h6 M8.500 8h3 M8.500 11h3 M13.500 19.500l.800-3.200 4.900-4.900 2.400 2.400-4.900 4.900z',
  salary: 'M4 9.500l8 5.500 8-5.500v10H4z M6.500 11V4.500h11V11 M9.500 8h5',
  whistle: 'M19.500 9.500h-10a4.500 4.500 0 1 0 4.400 3.200h5.600z M9.500 14h.010 M5.200 6.300 4 4.800 M8.500 5V3.200 M11.800 6.300 13 4.800',
  receipt: 'M6.500 3.500h11v17l-2.200-1.600-1.650 1.600-1.650-1.600-1.650 1.600-1.650-1.600-2.200 1.600z M9.500 8h5 M9.500 11.500h5',
  bag: 'M5.500 8h13l-1 12h-11z M9 8V6.500a3 3 0 0 1 6 0V8 M12 16.200l-2-2a1.300 1.300 0 0 1 2-1.600 1.300 1.300 0 0 1 2 1.600z',
  barcode: 'M5 7v10 M8 7v10 M10.500 7v10 M14 7v10 M16.500 7v10 M19 7v10',
  globe: 'M12 3.500a8.500 8.500 0 1 0 0 17 8.500 8.500 0 0 0 0-17z M3.500 12h17 M12 3.500c2.300 2.400 3.500 5.300 3.500 8.500s-1.200 6.100-3.500 8.500c-2.300-2.400-3.500-5.300-3.500-8.500s1.200-6.100 3.500-8.500z',
  phone: 'M8 3.500h8a1 1 0 0 1 1 1v15a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1v-15a1 1 0 0 1 1-1z M10.500 17.500h3',
  bell: 'M6.500 16.500V11a5.500 5.500 0 0 1 11 0v5.500l1.500 2H5z M10 20.500a2 2 0 0 0 4 0',
  doc: 'M6.500 3.500H14l3.500 3.500v13.500h-11z M9.500 11h5 M9.500 14h5 M9.500 17h3',
  star: 'M12 4.500l2.300 4.700 5.200.750-3.750 3.650.900 5.150L12 16.300l-4.650 2.450.900-5.150L4.500 9.950l5.200-.750z',

  // the trainer
  replay: 'M4.500 12a7.500 7.500 0 1 0 2.400-5.500 M4.500 4.500V8H8 M10.500 9.200v5.600l4.500-2.800z',
  explore: 'M12 3.500a8.500 8.500 0 1 0 0 17 8.500 8.500 0 0 0 0-17z M15.400 8.600l-1.900 4.900-4.900 1.900 1.900-4.900z',
  loan: 'M3.500 20h17 M5.500 20v-9.300L12 5.500l6.500 5.200V20 M10 20v-5h4v5',
  quiz: 'M12 3.500a8.500 8.500 0 1 0 0 17 8.500 8.500 0 0 0 0-17z M9.700 9.600a2.400 2.400 0 1 1 3.500 2.100c-.800.400-1.200.900-1.200 1.800 M12 16.400v.200',
  camera: 'M4 8.500A1.500 1.500 0 0 1 5.500 7h2l1.300-2h6.400l1.300 2h2A1.500 1.500 0 0 1 20 8.500v9a1.500 1.500 0 0 1-1.500 1.500h-13A1.500 1.500 0 0 1 4 17.500z M12 9.700a3.300 3.300 0 1 0 0 6.600 3.300 3.300 0 0 0 0-6.600z',
  db: 'M5 6.500C5 5.100 8.100 4 12 4s7 1.100 7 2.500S15.900 9 12 9 5 7.900 5 6.500z M5 6.500v11C5 18.900 8.100 20 12 20s7-1.100 7-2.500v-11 M5 12c0 1.400 3.100 2.500 7 2.500s7-1.100 7-2.500',
  gauge: 'M4.500 17a7.500 7.500 0 0 1 15 0 M12 17l3.500-5 M4.500 19.500h15',

  // the three baskets
  b_essentials: 'M4 10.700 12 4.250l8 6.450V20H4z M10 20v-5.500h4V20',
  b_unexpected: 'M14.700 6.300a4 4 0 0 0-5.400 5.100l-4.800 4.800a1.500 1.500 0 0 0 0 2.100l1.200 1.200a1.500 1.500 0 0 0 2.100 0l4.800-4.800a4 4 0 0 0 5.100-5.400l-2.600 2.600-2.300-.700-.700-2.300z',
  b_everyday: 'M6 9h10v5a4 4 0 0 1-4 4h-2a4 4 0 0 1-4-4z M16 10.500h1.500a2 2 0 0 1 0 4H16 M5 20.500h12 M9.200 4v2 M12.800 4v2',
};

export function Icon({ name, size = 20, stroke = 1.6 }) {
  return html`<svg class="ico" width=${size} height=${size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width=${stroke} stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <path d=${PATHS[name] || PATHS.circle} /></svg>`;
}

/** The solid versions the tab bar shows for the active tab. */
const SOLID = {
  home: 'M3.400 10.300 12 3.300l8.600 7V20.600H3.400z M9.800 14.200v6.400h4.400v-6.400z',
  wallet: 'M4.500 7.400h15a1.600 1.600 0 0 1 1.600 1.600v9.500a1.600 1.600 0 0 1-1.600 1.600h-15a1.600 1.600 0 0 1-1.600-1.600V9a1.600 1.600 0 0 1 1.600-1.600z M15.500 13.750a1.100 1.100 0 1 0 2.200 0 1.100 1.100 0 0 0-2.200 0z M6 6.300l9.500-2.650a1.500 1.500 0 0 1 1.900 1.450V6.300z',
  person: 'M12 3.500a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M4.750 20.750v-2a5.750 5.750 0 0 1 5.750-5.750h3a5.750 5.750 0 0 1 5.750 5.750v2z',
};

export function SolidIcon({ name, size = 26 }) {
  return html`<svg class="ico" width=${size} height=${size} viewBox="0 0 24 24" fill="currentColor" fill-rule="evenodd"
    aria-hidden="true" focusable="false"><path d=${SOLID[name] || SOLID.home} /></svg>`;
}

/* ---------- the brand mark ---------- */

// The bank's logo is not in this repository. If web/brand/logo.svg exists it is used
// (as a mask, so it takes the colour of its surroundings); otherwise a neutral stand-in.
const LOGO_URL = '/assets/brand/logo.svg';
let logoKnown = null;
let logoProbe = null;

export function probeLogo() {
  if (!logoProbe) {
    logoProbe = fetch(LOGO_URL)
      .then((r) => r.ok && /svg|image/.test(r.headers.get('content-type') || ''), () => false)
      .then((ok) => { logoKnown = ok; return ok; });
  }
  return logoProbe;
}

export function BrandMark({ size = 28, draw = false }) {
  const [ok, setOk] = useState(logoKnown);
  useEffect(() => {
    let alive = true;
    if (logoKnown === null) probeLogo().then((v) => { if (alive) setOk(v); });
    return () => { alive = false; };
  }, []);
  const box = `width:${size}px;height:${size}px`;
  if (ok === null) return html`<span class="brandmark" style=${box} aria-hidden="true"></span>`;
  if (ok) {
    return html`<span class=${'brandmark brandmark--img' + (draw ? ' brandmark--draw' : '')} aria-hidden="true"
      style=${`${box};-webkit-mask-image:url(${LOGO_URL});mask-image:url(${LOGO_URL})`}></span>`;
  }
  return html`<svg class=${'brandmark brandmark--stand-in' + (draw ? ' brandmark--draw' : '')} width=${size} height=${size}
    viewBox="0 0 32 32" aria-hidden="true" focusable="false">
    <rect class="brandmark__frame" x="2.500" y="2.500" width="27" height="27" rx="7.500" fill="none" stroke="currentColor" stroke-width="2" pathLength="100" />
    <text class="brandmark__s" x="16" y="23.400" text-anchor="middle" fill="currentColor">S</text>
  </svg>`;
}

/** The bank's full logo, where the real app shows it. Nothing at all when the file is not there. */
export function Wordmark({ height = 26 }) {
  const [ok, setOk] = useState(logoKnown);
  useEffect(() => {
    let alive = true;
    if (logoKnown === null) probeLogo().then((v) => { if (alive) setOk(v); });
    return () => { alive = false; };
  }, []);
  if (!ok) return null;
  return html`<img class="wordmark" src="/assets/brand/logo-wordmark.svg" height=${height} alt="S-Pankki"
    onError=${(e) => { e.currentTarget.hidden = true; }} />`;
}

/** Kept for older call sites: the small mark next to the assistant's name. */
export function Logo({ size = 24 }) {
  return html`<span class="logo" style=${`width:${size}px;height:${size}px`}><${Icon} name="whistle" size=${Math.round(size * 0.66)} /></span>`;
}

/** A payment card the size of an icon, carrying the mark. */
export function CardGlyph({ solid = false }) {
  return html`<span class=${'cardglyph' + (solid ? ' cardglyph--solid' : '')} aria-hidden="true"><${BrandMark} size=${16} /></span>`;
}

/* ---------- money, the way the app writes it: a big number and a smaller euro sign ---------- */

export function Amount({ value, mode, signed }) {
  const s = signed ? eurSigned(value, mode) : eur(value, mode);
  const lead = /^([−+-]?)€(.*)$/.exec(s);
  if (lead) return html`<span class="amt">${lead[1]}<small class="amt__cur">€</small>${lead[2]}</span>`;
  const trail = /^(.*?)\s*€$/.exec(s);
  if (trail) return html`<span class="amt">${trail[1]}<small class="amt__cur amt__cur--after">€</small></span>`;
  return html`<span class="amt">${s}</span>`;
}

/* ---------- states: loading, error, empty ---------- */

export function Skeleton({ rows = 3, tall }) {
  const widths = ['62%', '100%', '84%', '92%', '70%'];
  return html`<div class="skel" role="status" aria-label=${t('common.loading')}>
    ${tall ? html`<span class="skel__block"></span>` : null}
    ${Array.from({ length: rows }, (_, i) => html`<span class="skel__line" style=${`width:${widths[i % widths.length]}`} key=${i}></span>`)}
  </div>`;
}

export function ErrorBox({ error, onRetry, title }) {
  const message = error && error.message ? error.message : t('state.error_generic');
  return html`<div class="state state--error" role="alert">
    <span class="state__icon"><${Icon} name="alert" /></span>
    <div class="state__text">
      <strong>${title || t('state.error_title')}</strong>
      <p>${message}</p>
      ${onRetry ? html`<button type="button" class="btn btn--small" onClick=${onRetry}><${Icon} name="refresh" size=${16} />${t('common.try_again')}</button>` : null}
    </div>
  </div>`;
}

export function Empty({ title, children, icon = 'info' }) {
  return html`<div class="state state--empty">
    <span class="state__mark" aria-hidden="true"><${Icon} name=${icon} size=${20} /></span>
    <div class="state__text"><strong>${title}</strong>${children ? html`<p>${children}</p>` : null}</div>
  </div>`;
}

/** Wraps the three states of a request around its content. */
export function Load({ req, rows = 3, tall, children }) {
  if (req.error && !req.data) return html`<${ErrorBox} error=${req.error} onRetry=${req.reload} />`;
  if (!req.data) return html`<${Skeleton} rows=${rows} tall=${tall} />`;
  const draw = Array.isArray(children) ? children.find((c) => typeof c === 'function') : children;
  return html`<div class=${req.stale || req.loading ? 'is-stale' : ''}>${typeof draw === 'function' ? draw(req.data) : null}</div>`;
}

/* ---------- small pieces ---------- */

export function Disclosure({ label, children, open: initial = false }) {
  const [open, setOpen] = useState(initial);
  return html`<div class=${'disc' + (open ? ' is-open' : '')}>
    <button type="button" class="disc__btn" aria-expanded=${open ? 'true' : 'false'} onClick=${() => setOpen(!open)}>
      <span>${label}</span><${Icon} name="chevron" size=${18} />
    </button>
    ${open ? html`<div class="disc__body">${children}</div>` : null}
  </div>`;
}

export function Chip({ active, onClick, children, tone, label }) {
  return html`<button type="button" class=${'chip' + (active ? ' is-active' : '') + (tone ? ' ' + tone : '')}
    aria-pressed=${active ? 'true' : 'false'} aria-label=${label} onClick=${onClick}>${children}</button>`;
}

/** The square, black-and-white control the bank app uses to switch a list. */
export function Segmented({ options, value, onChange, label }) {
  return html`<div class="segctl" role="group" aria-label=${label}>
    ${options.map(([key, text]) => html`<button type="button" key=${key} class=${'segctl__opt' + (value === key ? ' is-active' : '')}
      aria-pressed=${value === key ? 'true' : 'false'} onClick=${() => onChange(key)}>${text}</button>`)}
  </div>`;
}

export function BasketIcon({ basket, size = 20 }) {
  const b = basketOf(basket);
  if (!b) return null;
  return html`<${Icon} name=${'b_' + b.id} size=${size} />`;
}

export function BasketTag({ basket }) {
  const b = basketOf(basket);
  if (!b) return null;
  return html`<span class=${'tag b-' + b.id}><i class="dot" aria-hidden="true"></i>${b.short}</span>`;
}

export function Stat({ label, value, hint, tone }) {
  return html`<div class="stat">
    <span class="stat__label">${label}</span>
    <span class=${'stat__value' + (tone ? ' is-' + tone : '')}>${value}</span>
    ${hint ? html`<span class="stat__hint">${hint}</span>` : null}
  </div>`;
}

/** One line in a white list card: icon, title, optional second line, value or chevron. */
export function Row({ icon, title, sub, value, onClick, tour, chevron = true, badge, external }) {
  const body = html`
    ${icon ? html`<span class="row__icon">${typeof icon === 'string' ? html`<${Icon} name=${icon} size=${28} stroke=${1.400} />` : icon}</span>` : null}
    <span class="row__text"><span class="row__title">${title}</span>${sub ? html`<span class="row__sub">${sub}</span>` : null}</span>
    ${value ? html`<span class="row__value">${value}</span>` : null}
    ${badge ? html`<span class="count">${badge}</span>` : null}
    ${onClick && chevron ? html`<span class="row__chev"><${Icon} name=${external ? 'external' : 'right'} size=${20} /></span>` : null}`;
  if (!onClick) return html`<div class="row" data-tour=${tour}>${body}</div>`;
  return html`<button type="button" class="row row--tap" data-tour=${tour} onClick=${onClick}>${body}</button>`;
}

/* ---------- bottom sheet ---------- */

export function Sheet({ sheet, onClose }) {
  useLang();
  const [current, setCurrent] = useState(sheet);
  const [shown, setShown] = useState(false);
  const panel = useRef(null);
  const before = useRef(null);

  useEffect(() => {
    if (sheet) {
      if (!current) before.current = document.activeElement;
      setCurrent(sheet);
      const frame = requestAnimationFrame(() => requestAnimationFrame(() => setShown(true)));
      return () => cancelAnimationFrame(frame);
    }
    setShown(false);
    const timer = setTimeout(() => setCurrent(null), 260);
    return () => clearTimeout(timer);
  }, [sheet]);

  useEffect(() => {
    if (!shown) return undefined;
    if (panel.current) panel.current.focus();
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      const el = before.current;
      if (el && el.focus && document.contains(el)) el.focus();
    };
  }, [shown]);

  if (!current) return null;
  return html`<div class=${'sheet-wrap' + (shown ? ' is-open' : '')}>
    <div class="sheet-backdrop" onClick=${onClose}></div>
    <section class="sheet" role="dialog" aria-modal="true" aria-label=${current.title} tabindex="-1" ref=${panel}>
      <header class="sheet__head">
        <h2>${current.title}</h2>
        <button type="button" class="iconbtn" aria-label=${t('common.close')} onClick=${onClose}><${Icon} name="close" /></button>
      </header>
      <div class="sheet__body">${current.body}</div>
    </section>
  </div>`;
}

/* ---------- the three-basket bar ---------- */

function basketTotals(parts) {
  const list = Array.isArray(parts) ? parts : [];
  return BASKET_ORDER.map((id) => {
    const hit = list.find((p) => p && (basketOf(p.basket) || basketOf(p.name) || basketOf(p.key) || {}).id === id);
    return { b: BASKETS[id], total: Math.max(0, Number(hit && hit.total) || 0), src: hit || null };
  });
}

/** One whole, split into the three baskets. Shares are printed inside when they fit. */
export function BasketBar({ parts }) {
  const rows = basketTotals(parts);
  const sum = rows.reduce((a, r) => a + r.total, 0);
  if (sum <= 0) {
    return html`<div class="seg seg--empty" role="img" aria-label=${t('bar.empty')}><span>${t('bar.empty')}</span></div>`;
  }
  const aria = rows.map((r) => `${r.b.name} ${eur(r.total)}, ${Math.round((r.total / sum) * 100)} %`).join('; ');
  return html`<div class="seg" role="img" aria-label=${aria}>
    ${rows.filter((r) => r.total > 0).map((r) => {
      const share = (r.total / sum) * 100;
      return html`<div class=${'seg__part b-' + r.b.id} style=${`flex:${share.toFixed(2)} 1 0%`} key=${r.b.id}>
        ${share >= 13 ? html`<span>${Math.round(share)}%</span>` : null}
      </div>`;
    })}
  </div>`;
}

export function BasketLegend({ parts, perMonth }) {
  const rows = basketTotals(parts);
  const sum = rows.reduce((a, r) => a + r.total, 0);
  return html`<ul class="legend legend--rows">
    ${rows.map((r) => html`<li key=${r.b.id}>
      <span class=${'legend__key b-' + r.b.id}><i class="dot" aria-hidden="true"></i>${r.b.name}</span>
      <span class="legend__val">${eur(perMonth && r.src && r.src.monthly_average !== undefined ? r.src.monthly_average : r.total)}${perMonth ? html`<small> ${t('unit.a_month')}</small>` : null}
        <small> · ${sum > 0 ? Math.round((r.total / sum) * 100) : 0} %</small></span>
    </li>`)}
  </ul>`;
}

/* ---------- horizontal bar list ---------- */

/**
 * rows: [{ key, label, value, text, note, tone, icon, pick }]
 * The value is always written out next to the bar, so colour never carries it alone.
 */
export function BarList({ rows, max, onPick, tone, pickLabel }) {
  if (!rows || !rows.length) return null;
  const top = max ?? Math.max(0, ...rows.map((r) => Math.max(0, Number(r.value) || 0)));
  return html`<ul class="bars">
    ${rows.map((r, i) => {
      const v = Math.max(0, Number(r.value) || 0);
      let w = top > 0 ? clamp((v / top) * 100, 0, 100) : 0;
      if (v > 0 && w < 1.5) w = 1.5;
      const inner = html`
        <span class="bar__top">
          <span class="bar__label">${r.label}</span>
          <span class="bar__value">${r.text}</span>
        </span>
        <span class="bar__track"><span class=${'bar__fill ' + (r.tone || tone || 't-accent')} style=${`width:${w.toFixed(2)}%;animation-delay:${Math.min(i, 8) * 30}ms`}></span></span>
        ${r.note ? html`<span class="bar__note">${r.note}</span>` : null}`;
      const pick = Boolean(onPick) && r.pick !== false;
      return html`<li key=${r.key ?? r.label}>
        ${pick
          ? html`<button type="button" class="bar bar--pick" onClick=${() => onPick(r)}
              aria-label=${`${r.label}, ${r.text}. ${r.pickLabel || pickLabel || t('common.show_more')}`}>
              <span class="bar__main">${inner}</span><${Icon} name="right" size=${16} />
            </button>`
          : html`<div class="bar"><span class="bar__main">${inner}</span></div>`}
      </li>`;
    })}
  </ul>`;
}

/* ---------- spending results (shared by Explore and the chat cards) ---------- */

const WEEKDAYS = { monday: 1, tuesday: 2, wednesday: 3, thursday: 4, friday: 5, saturday: 6, sunday: 0 };

/** A category or subcategory from the data, in the current language. */
export const catName = (v) => tv('cat', v);
export const subName = (v) => tv('sub', v);

export function keyLabel(groupBy, key) {
  if (key === null || key === undefined || key === '') return t('common.other');
  if (groupBy === 'month') return fmtMonth(key, true);
  if (groupBy === 'week') return t('explore.week_of', { date: fmtDate(key) });
  if (groupBy === 'day') return fmtDate(key, { weekday: true });
  if (groupBy === 'category') return catName(key);
  if (groupBy === 'subcategory') return subName(key);
  if (groupBy === 'basket') { const b = basketOf(key); return b ? b.name : String(key); }
  if (groupBy === 'weekday' && WEEKDAYS[String(key).toLowerCase()] !== undefined) {
    const k = 'weekday.' + String(key).toLowerCase();
    return has(k) ? t(k) : String(key);
  }
  const more = /^(\d+) more$/.exec(String(key));
  if (more) return t('explore.n_more', { n: more[1] });
  return String(key);
}

/** Turn a get_spending breakdown into bar rows. Basket rows keep their basket colour. */
export function spendRows(result, tone) {
  const g = result && result.group_by;
  const list = Array.isArray(result && result.breakdown) ? result.breakdown : [];
  return list.map((row) => {
    const b = g === 'basket' ? basketOf(row.key) : null;
    const n = Number(row.transactions);
    return {
      key: String(row.key), label: keyLabel(g, row.key),
      value: row.total, text: eur(row.total),
      note: [Number.isFinite(Number(row.share_pct)) ? pct(row.share_pct) : null,
        Number.isFinite(n) ? t('n_payments', { n, count: num(n, 0) }) : null].filter(Boolean).join(' · '),
      tone: b ? 'b-' + b.id : tone, raw: row,
    };
  });
}

/** "▼ 18.7%  €1,749 less than the period before". */
export function ChangeLine({ prev }) {
  if (!prev || !Number.isFinite(Number(prev.total))) return null;
  const change = Number(prev.change);
  const range = prev.start && prev.end ? `${fmtDate(prev.start)} – ${fmtDate(prev.end, { year: true })}` : t('change.before');
  if (!Number.isFinite(change) || Math.abs(change) < 0.005) {
    return html`<p class="change">${t('change.same', { range })}</p>`;
  }
  const up = change > 0;
  const hasPct = prev.change_pct !== null && prev.change_pct !== undefined && Number.isFinite(Number(prev.change_pct));
  return html`<p class="change">
    <span class=${'delta ' + (up ? 'is-up' : 'is-down')}><${Icon} name=${up ? 'up' : 'down'} size=${14} />${hasPct ? pct(Math.abs(Number(prev.change_pct))) : up ? t('change.new') : t('change.less_word')}</span>
    <span>${t(up ? 'change.more' : 'change.less', { amount: eur(Math.abs(change)), range, total: eur(prev.total) })}</span>
  </p>`;
}

/* ---------- budget waterfall: from salary down to what is left ---------- */

export function Waterfall({ lines }) {
  const rows = (Array.isArray(lines) ? lines : []).filter((l) => l && Number.isFinite(Number(l.amount)));
  if (!rows.length) return html`<${Empty} title=${t('wf.empty_title')}>${t('wf.empty_text')}<//>`;
  const top = Math.max(1, ...rows.map((l) => Math.abs(Number(l.amount))));
  let running = 0;
  const out = rows.map((l, i) => {
    const amount = Number(l.amount);
    let from = 0;
    let to = amount;
    const kind = i === 0 ? 'start' : l.total ? 'total' : 'step';
    if (kind === 'step') { from = running; to = running + amount; }
    running = to;
    const lo = clamp(Math.min(from, to), 0, top);
    const hi = clamp(Math.max(from, to), 0, top);
    const b = basketOf(l.basket);
    return {
      label: nice(l.label), amount, kind, b,
      left: (lo / top) * 100, width: ((hi - lo) / top) * 100,
      tone: b ? 'b-' + b.id : kind === 'start' ? 't-ink' : 't-save',
    };
  });
  return html`<ol class="wf">
    ${out.map((r, i) => html`<li class=${'wf__row wf__row--' + r.kind + (r.amount < -0.004 && r.kind === 'total' ? ' is-neg' : '')} key=${i}>
      <span class="wf__label"><i class=${'dot ' + r.tone} aria-hidden="true"></i>${r.label}</span>
      <span class="wf__amt">${r.kind === 'step' ? eurSigned(r.amount) : eur(r.amount)}</span>
      <span class="wf__track" aria-hidden="true">
        <span class=${'wf__bar ' + r.tone} style=${`left:${r.left.toFixed(2)}%;width:${Math.max(r.width, r.amount ? 0.8 : 0).toFixed(2)}%`}></span>
      </span>
    </li>`)}
  </ol>`;
}

export function BalanceCheck({ check }) {
  if (!check) return null;
  const rows = [
    ['bc.balance_today', check.balance_today, false],
    ['bc.salary_expected', check.salary_expected_tomorrow, false, true],
    ['bc.bills_due', -Math.abs(Number(check.bills_due_before_payday) || 0), true],
    ['bc.groceries', -Math.abs(Number(check.groceries_and_transport_before_payday) || 0), true],
  ].filter((r) => !(r[3] && !Number(r[1])));
  return html`<dl class="kv kv--sum">
    ${rows.map(([label, value, signed]) => html`<div key=${label}><dt>${t(label)}</dt><dd>${signed ? eurSigned(value) : eur(value)}</dd></div>`)}
    <div class="kv__total"><dt>${t('bc.can_cover')}</dt><dd>${eur(check.balance_can_cover)}</dd></div>
  </dl>`;
}

/* ---------- month-by-month stacked columns ---------- */

export function Columns({ months, initial }) {
  const list = (Array.isArray(months) ? months : []).filter(Boolean);
  const [picked, setPicked] = useState(initial ?? list.length - 1);
  if (!list.length) return html`<${Empty} icon="calendar" title=${t('cols.empty_title')}>${t('cols.empty_text')}<//>`;
  const sel = clamp(picked, 0, list.length - 1);
  const W = 340, H = 168, L = 6, R = 334, TOP = 24, BASE = 138;
  const plot = BASE - TOP;
  const band = (R - L) / list.length;
  const colW = Math.min(24, band * 0.5);
  const val = (m, k) => Math.max(0, Number(m[k]) || 0);
  const spendOf = (m) => BASKET_ORDER.reduce((a, k) => a + val(m, k), 0);
  const max = Math.max(1, ...list.map((m) => Math.max(spendOf(m), val(m, 'income'))));
  const y = (v) => BASE - (v / max) * plot;
  const m = list[sel];
  const net = Number(m.net);
  const low = Number(m.lowest_balance);

  return html`<div class="colchart">
    <ul class="legend legend--inline">
      ${BASKET_ORDER.map((id) => html`<li key=${id}><span class=${'legend__key b-' + id}><i class="dot" aria-hidden="true"></i>${BASKETS[id].short}</span></li>`)}
      <li><span class="legend__key"><i class="tick" aria-hidden="true"></i>${t('cols.money_in')}</span></li>
    </ul>
    <svg class="cols" viewBox=${`0 0 ${W} ${H}`} role="group" aria-label=${t('cols.aria')}>
      <line x1=${L} x2=${R} y1=${BASE + 0.5} y2=${BASE + 0.5} class="cols__base" />
      ${list.map((mo, i) => {
        const cx = L + band * (i + 0.5);
        const x = cx - colW / 2;
        let acc = 0;
        const segs = BASKET_ORDER.map((id) => {
          const v = val(mo, id);
          const y1 = y(acc + v);
          const hgt = y(acc) - y1;
          acc += v;
          return { id, y: y1, h: hgt };
        }).filter((s) => s.h > 0.4);
        const total = spendOf(mo);
        const yTop = y(total);
        const yIn = y(val(mo, 'income'));
        const labelY = Math.min(yTop, yIn) - 7;
        const label = t('cols.month_aria', { month: fmtMonth(mo.month, true), spent: eur(total), income: eur(mo.income) });
        return html`<g key=${mo.month} class=${'cols__col' + (i === sel ? ' is-picked' : '')}>
          <rect class="cols__hit" x=${L + band * i + 2} y="2" width=${band - 4} height=${H - 4} rx="6"
            role="button" tabindex="0" aria-label=${label} aria-pressed=${i === sel ? 'true' : 'false'}
            onClick=${() => setPicked(i)}
            onKeyDown=${(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setPicked(i); } }} />
          <g class="cols__stack" style=${`animation-delay:${i * 40}ms`}>
            ${segs.map((s, k) => {
              const isTop = k === segs.length - 1;
              const hgt = isTop ? s.h : Math.max(0.5, s.h - 2);
              const yy = isTop ? s.y : s.y + 2;
              if (!isTop) return html`<rect key=${s.id} class=${'b-' + s.id} x=${x} y=${yy} width=${colW} height=${hgt} />`;
              const r = Math.min(3, hgt, colW / 2);
              const d = `M${x},${yy + hgt}V${yy + r}Q${x},${yy} ${x + r},${yy}H${x + colW - r}Q${x + colW},${yy} ${x + colW},${yy + r}V${yy + hgt}Z`;
              return html`<path key=${s.id} class=${'b-' + s.id} d=${d} />`;
            })}
          </g>
          <line class="cols__income" x1=${cx - colW / 2 - 6} x2=${cx + colW / 2 + 6} y1=${yIn} y2=${yIn} />
          <text class="cols__val" x=${cx} y=${Math.max(11, labelY)} text-anchor="middle">${eurShort(total)}</text>
          <text class="cols__month" x=${cx} y=${BASE + 19} text-anchor="middle">${fmtMonth(mo.month)}</text>
        </g>`;
      })}
    </svg>
    <div class="colchart__detail" aria-live="polite">
      <div class="colchart__head">
        <strong>${fmtMonth(m.month, true)}</strong>
        <span class=${'delta ' + (net < 0 ? 'is-bad' : 'is-good')}>
          ${net < 0 ? t('cols.spent_more', { amount: eur(Math.abs(net)) }) : t('cols.left_over', { amount: eur(net) })}
        </span>
      </div>
      <dl class="kv kv--grid">
        <div><dt>${t('cols.money_in')}</dt><dd>${eur(m.income)}</dd></div>
        <div><dt>${t('cols.spent')}</dt><dd>${eur(m.spending ?? spendOf(m))}</dd></div>
        ${BASKET_ORDER.map((id) => html`<div key=${id}><dt><i class=${'dot b-' + id} aria-hidden="true"></i>${BASKETS[id].short}</dt><dd>${eur(m[id])}</dd></div>`)}
        ${Number(m.to_savings) > 0 ? html`<div><dt>${t('cols.to_savings')}</dt><dd>${eur(m.to_savings)}</dd></div>` : null}
        ${Number(m.transfer_out) > 0 ? html`<div><dt>${t('cols.to_other')}</dt><dd>${eur(m.transfer_out)}</dd></div>` : null}
        ${Number.isFinite(low) ? html`<div><dt>${t('cols.lowest')}</dt><dd class=${low < 0 ? 'is-bad' : ''}>${eur(low)}</dd></div>` : null}
      </dl>
    </div>
  </div>`;
}

/* ---------- you compared with peers ---------- */

export function PeerBars({ comparisons }) {
  const list = (Array.isArray(comparisons) ? comparisons : []).filter(Boolean);
  if (!list.length) return html`<${Empty} icon="person" title=${t('peers.empty_title')}>${t('peers.empty_text')}<//>`;
  const fmt = (c, v) => (c.unit === 'pct' ? pct(v) : c.unit === 'eur' ? eur(v) : num(v));
  return html`<div class="peers">
    <ul class="legend legend--inline">
      <li><span class="legend__key"><i class="dot t-accent" aria-hidden="true"></i>${t('peers.you')}</span></li>
      <li><span class="legend__key"><i class="band" aria-hidden="true"></i>${t('peers.middle')}</span></li>
      <li><span class="legend__key"><i class="tick tick--v" aria-hidden="true"></i>${t('peers.typical')}</span></li>
    </ul>
    ${list.map((c, i) => {
      const you = Number(c.you) || 0;
      const med = Number(c.peer_median) || 0;
      const q = Array.isArray(c.peer_middle_half) ? c.peer_middle_half.map(Number) : [med, med];
      const lo = Math.min(0, you, q[0], med);
      const hi = Math.max(you, q[1], med, lo + 1);
      const span = (hi - lo) * 1.08;
      const pos = (v) => clamp(((v - lo) / span) * 100, 0, 100);
      const b = basketOf(String(c.metric || '').replace(/^Monthly spending on /, ''));
      const higher = Number(c.higher_than_pct_of_peers);
      return html`<div class="peer" key=${i}>
        <div class="peer__title">${b ? html`<i class=${'dot b-' + b.id} aria-hidden="true"></i>` : null}${nice(c.metric)}</div>
        <div class="peer__track" role="img" aria-label=${`${t('peers.you')} ${fmt(c, you)}, ${t('peers.typical')} ${fmt(c, med)}`}>
          <span class="peer__band" style=${`left:${pos(q[0])}%;width:${Math.max(1, pos(q[1]) - pos(q[0]))}%`}></span>
          <span class="peer__median" style=${`left:${pos(med)}%`}></span>
          <span class=${'peer__you ' + (b ? 'b-' + b.id : 't-accent')} style=${`left:${pos(you)}%`}></span>
        </div>
        <div class="peer__nums">
          <span><strong>${fmt(c, you)}</strong> ${t('peers.you_lc')}</span>
          <span><strong>${fmt(c, med)}</strong> ${t('peers.typical_lc')}</span>
          ${Number.isFinite(higher) ? html`<span class="peer__rank">${t('peers.higher_than', { pct: num(higher, 0) })}</span>` : null}
        </div>
      </div>`;
    })}
  </div>`;
}

/* ---------- home loan pillars ---------- */

export const PILLAR_STATUS = {
  strong: { key: 'status.strong', tone: 'good', icon: 'check' },
  close: { key: 'status.close', tone: 'warn', icon: 'half' },
  not_yet: { key: 'status.not_yet', tone: 'bad', icon: 'circle' },
};
const statusLabel = (s, status) => (s && s.key ? t(s.key) : (s && s.label) || words(status) || '–');

export function StatusPill({ status, map = PILLAR_STATUS }) {
  const s = map[status] || { tone: 'muted', icon: 'circle' };
  return html`<span class=${'pill pill--' + s.tone}><${Icon} name=${s.icon} size=${14} />${statusLabel(map[status], status)}</span>`;
}

export function PillarMeter({ pillars }) {
  const list = Array.isArray(pillars) ? pillars : [];
  return html`<div class="meter4" role="img" aria-label=${list.map((p) => `${tv('pillar', p.pillar)}: ${statusLabel(PILLAR_STATUS[p.status], p.status)}`).join(', ')}>
    ${list.map((p, i) => html`<span class=${'meter4__cell is-' + ((PILLAR_STATUS[p.status] || {}).tone || 'muted')} key=${i}>
      <${Icon} name=${(PILLAR_STATUS[p.status] || {}).icon || 'circle'} size=${14} /><em>${tv('pillar', p.pillar)}</em>
    </span>`)}
  </div>`;
}

export function Pillars({ pillars, compact, tour }) {
  const list = Array.isArray(pillars) ? pillars : [];
  if (!list.length) return null;
  return html`<ul class=${'pillars' + (compact ? ' pillars--compact' : '')} data-tour=${tour}>
    ${list.map((p, i) => html`<li class="pillar" key=${i}>
      <div class="pillar__head"><strong>${tv('pillar', p.pillar)}</strong><${StatusPill} status=${p.status} /></div>
      <dl class="pillar__facts">
        <div><dt>${t('pillar.you')}</dt><dd>${nice(p.you)}</dd></div>
        <div><dt>${t('pillar.needed')}</dt><dd>${nice(p.needed)}</dd></div>
      </dl>
      ${!compact && p.explanation ? html`<p class="pillar__why">${nice(p.explanation)}</p>` : null}
    </li>`)}
  </ul>`;
}

/* ---------- tables, payments, timeline ---------- */

function cell(v) {
  if (v === null || v === undefined || v === '') return html`<span class="muted">–</span>`;
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : num(v, 2);
  if (typeof v === 'boolean') return v ? t('common.yes').toLowerCase() : t('common.no').toLowerCase();
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

export function DataTable({ columns, rows, note }) {
  const cols = Array.isArray(columns) ? columns : [];
  const data = Array.isArray(rows) ? rows : [];
  if (!cols.length) return null;
  const numeric = cols.map((_, i) => data.length > 0 && data.every((r) => r[i] === null || typeof r[i] === 'number'));
  return html`<div class="tablewrap" tabindex="0" role="region" aria-label=${t('table.result')}>
    <table class="tbl">
      <thead><tr>${cols.map((c, i) => html`<th scope="col" class=${numeric[i] ? 'is-num' : ''} key=${i}>${c}</th>`)}</tr></thead>
      <tbody>
        ${data.map((r, ri) => html`<tr key=${ri}>${cols.map((_, i) => html`<td class=${numeric[i] ? 'is-num' : ''} key=${i}>${cell(Array.isArray(r) ? r[i] : null)}</td>`)}</tr>`)}
      </tbody>
    </table>
    ${note ? html`<p class="tbl__note">${note}</p>` : null}
  </div>`;
}

/** Payments the way the account page lists them: what, when, how much. */
export function TxList({ transactions, signed }) {
  const list = Array.isArray(transactions) ? transactions : [];
  if (!list.length) return html`<${Empty} icon="receipt" title=${t('tx.empty_title')}>${t('tx.empty_text')}<//>`;
  return html`<ul class="tx">
    ${list.map((x, i) => {
      const b = basketOf(x.basket);
      const amount = Number(x.amount);
      const income = signed && amount > 0;
      const name = x.subcategory ? subName(x.subcategory) : x.category ? catName(x.category) : t('tx.payment');
      const cat = x.category && x.category !== x.subcategory ? catName(x.category) : null;
      return html`<li key=${i}>
        <span class="tx__what">
          <strong>${name}</strong>
          <small>${fmtDate(x.date, { year: Boolean(signed) })}${b ? html`<span class="tx__sep" aria-hidden="true">·</span><i class=${'dot b-' + b.id} aria-hidden="true"></i>${b.short}` : cat && !signed ? html`<span class="tx__sep" aria-hidden="true">·</span>${cat}` : null}</small>
        </span>
        <span class=${'tx__amt' + (income ? ' is-in' : '')}>${signed ? eurSigned(amount, 'cents') : eur(amount, 'cents')}</span>
      </li>`;
    })}
  </ul>`;
}

export function Timeline({ items }) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return null;
  return html`<ol class="tl">
    ${list.map((x, i) => html`<li class=${'tl__item' + (x.event === 'loan_decision' ? ' is-key' : '')} key=${i}>
      <span class="tl__date">${fmtDate(x.date)}</span>
      <span class="tl__dot" aria-hidden="true"></span>
      <div class="tl__body"><strong>${words(x.event)}</strong><p>${nice(String(x.note || '').replace(/\bThe customer\b/g, 'You').replace(/\bthe customer\b/g, 'you'))}</p></div>
    </li>`)}
  </ol>`;
}

/* ---------- generic key/value fallback ---------- */

function plain(v) {
  if (v === null || v === undefined || v === '') return '–';
  if (typeof v === 'number') return Number.isInteger(v) ? num(v, 0) : num(v, 2);
  if (typeof v === 'boolean') return v ? t('common.yes') : t('common.no');
  if (Array.isArray(v)) {
    if (v.every((x) => x === null || typeof x !== 'object')) return v.map(plain).join(', ');
    return t('kv.items', { n: v.length });
  }
  if (typeof v === 'object') {
    if (v.label) return nice(v.label);
    return Object.entries(v).filter(([, x]) => x === null || typeof x !== 'object').slice(0, 4)
      .map(([k, x]) => `${words(k).toLowerCase()} ${plain(x)}`).join(', ') || '–';
  }
  return nice(v);
}

export function KeyValue({ data, skip = [] }) {
  const entries = Object.entries(data && typeof data === 'object' ? data : {})
    .filter(([k]) => k !== 'customer_id' && !skip.includes(k));
  if (!entries.length) return html`<p class="muted">${t('kv.none')}</p>`;
  return html`<dl class="kv">
    ${entries.slice(0, 14).map(([k, v]) => html`<div key=${k}><dt>${words(k)}</dt><dd>${plain(v)}</dd></div>`)}
  </dl>`;
}

/* ---------- the basket rules ("Why is this in this basket?") ---------- */

export function BasketRules({ data }) {
  const baskets = Array.isArray(data && data.baskets) ? data.baskets : [];
  const rules = Array.isArray(data && data.rules) ? data.rules : [];
  return html`<div class="rules">
    <ul class="rules__baskets">
      ${baskets.map((b) => {
        const known = basketOf(b.basket) || basketOf(b.name);
        return html`<li class=${'rules__basket' + (known ? ' b-' + known.id : '')} key=${b.basket}>
          <span class="rules__icon" aria-hidden="true">${known ? html`<${BasketIcon} basket=${known.id} size=${22} />` : null}</span>
          <div><strong>${known ? known.name : b.name}</strong><p>${nice(b.meaning)}</p>${b.examples ? html`<p class="muted">${t('rules.example', { examples: nice(b.examples) })}</p>` : null}</div>
        </li>`;
      })}
    </ul>
    ${rules.length ? html`<h3 class="h3">${t('rules.exact')}</h3>
      <ol class="rules__list">${rules.map((r, i) => html`<li key=${i}>${nice(r)}</li>`)}</ol>` : null}
  </div>`;
}

export function RulesBody() {
  useLang();
  const req = useApi('/api/baskets/rules');
  return html`<${Load} req=${req} rows=${6}>${(d) => html`
    <p class="lead">${t('rules.lead')}</p>
    <${BasketRules} data=${d} />`}<//>`;
}
