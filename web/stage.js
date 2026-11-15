// Money Mentor: the demo page. Draws the phone, runs the guided tour, and talks to the
// app inside the phone with postMessage (the contract is in README.md).
import tour, { STEPS } from './i18n/tour.js';

const LANGS = ['en', 'fi', 'sv'];
const LOCALES = { en: 'en-IE', fi: 'fi-FI', sv: 'sv-FI' };
const KEY_LANG = 'mm-stage.lang';
const KEY_WHO = 'mm-stage.who';
const DEFAULT_WHO = 'CUST00086';
const READY_TIMEOUT = 6000;

const $ = (id) => document.getElementById(id);
const store = {
  get(key) { try { return localStorage.getItem(key); } catch (err) { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch (err) { /* fine without it */ } },
};
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const narrow = window.matchMedia('(max-width: 699px)');
const params = new URLSearchParams(location.search);
const still = params.has('still'); // `?still=1`: everything at rest, for screenshots and automated checks

const pick = (value, allowed, fallback) => (allowed.includes(value) ? value : fallback);
const isCustomer = (id) => typeof id === 'string' && /^CUST\d{3,8}$/.test(id);

// With no choice made yet, start in the visitor's own language: a Finnish browser opens in Finnish.
const browserLang = () => {
  const wanted = (navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || ''])
    .map((l) => String(l).slice(0, 2).toLowerCase());
  return wanted.find((l) => LANGS.includes(l)) || 'en';
};

const state = {
  lang: pick(params.get('lang') || store.get(KEY_LANG), LANGS, browserLang()),
  who: [params.get('who'), store.get(KEY_WHO), DEFAULT_WHO].find(isCustomer),
  personas: [],
  personasDone: false, // true once /api/personas has answered, or failed
  mode: 'intro', // intro | tour | end | free
  step: 0,
  auto: true,
  asked: false,
  photoAsked: false,
  photosSent: new Set(), // the steps whose sample photo has gone out in this run
  sawTour: false,
  ready: false,
  route: null,
};

const el = {
  stage: $('stage'),
  phone: $('phone'),
  slot: $('device-slot'),
  device: $('device'),
  screen: $('device-screen'),
  clock: $('clock'),
  panels: { intro: $('panel-intro'), tour: $('panel-tour'), end: $('panel-end') },
  customer: $('customer'),
  pickerBtn: $('picker-btn'),
  pickerPop: $('picker-pop'),
  bar: $('tour-bar'),
  copy: $('tour-copy'),
  text: $('tour-text'),
  proof: $('tour-proof'),
  back: $('tour-back'),
  next: $('tour-next'),
  toggle: $('tour-toggle'),
};
let frame = null;

/* ---------- Words ---------- */

const words = () => tour[state.lang] || tour.en;
function t(key, vars) {
  let text = words()[key];
  if (text == null) text = tour.en[key];
  if (text == null) return '';
  return vars ? text.replace(/\{(\w+)\}/g, (m, name) => (name in vars ? vars[name] : m)) : text;
}

function applyLang() {
  const w = words();
  document.documentElement.lang = state.lang;
  document.title = `${w.name} · ${w.tagline.split(' · ')[0]}`;
  document.querySelectorAll('[data-t]').forEach((node) => { node.textContent = t(node.dataset.t); });
  document.querySelectorAll('[data-lang]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.lang === state.lang)));
  $('lang').setAttribute('aria-label', w.language);
  $('m-open').href = `/app?lang=${state.lang}`;
  $('m-start').href = `/app?lang=${state.lang}&tour=1`;
  el.device.setAttribute('aria-label', w.phoneLabel);
  el.bar.setAttribute('aria-label', w.walkthrough);
  if (frame) frame.title = w.frameTitle;
  $('asks').replaceChildren(...w.questions.map(askButton));
  renderClock();
  renderPicker();
  renderEnd();
  if (state.mode === 'tour') renderStep({ quiet: true });
}

function setLang(lang) {
  if (!LANGS.includes(lang) || lang === state.lang) return;
  state.lang = lang;
  store.set(KEY_LANG, lang);
  applyLang();
  post('lang', { lang });
}

/* ---------- Messages to and from the app ---------- */

function post(type, extra) {
  if (!frame || !frame.contentWindow) return;
  try { frame.contentWindow.postMessage({ source: 'mm', type, ...extra }, location.origin); } catch (err) { /* the app is not there yet */ }
}

window.addEventListener('message', (event) => {
  if (event.origin !== location.origin) return;
  const data = event.data;
  if (!data || typeof data !== 'object' || data.source !== 'mm') return;
  if (!frame || event.source !== frame.contentWindow) return;
  if (data.type === 'ready') {
    state.ready = true;
    if (typeof data.route === 'string') state.route = data.route;
    // Anything chosen while the app was still loading is sent again now that it listens.
    if (data.lang !== state.lang) post('lang', { lang: state.lang });
    if (isCustomer(data.who) && data.who !== state.who) post('who', { id: state.who, label: personaText(currentPersona()).label });
    if (state.mode === 'tour') sendStep();
    wake();
  } else if (data.type === 'route') {
    if (typeof data.route === 'string') state.route = data.route;
  } else if (data.type === 'chrome') {
    if (data.tone === 'light' || data.tone === 'dark') el.device.dataset.tone = data.tone;
  }
});

/* ---------- The phone ---------- */

// iPhone 16 Pro, in CSS px: a 402 x 874 display with 62px continuous corners, a 7.5px black
// border and a 5.5px titanium band. Every curve below is derived from these five numbers.
const GEO = { sw: 402, sh: 874, r: 62, bezel: 7.5, band: 5.5 };
const EDGE = GEO.bezel + GEO.band;
const BODY_W = GEO.sw + EDGE * 2;
const BODY_H = GEO.sh + EDGE * 2;
const PROUD = 2.2; // how far the side buttons stand out from the band

// The continuous-curvature corner iOS and the iPhone's own hardware use, not a plain arc.
function squircle(x, y, w, h, r) {
  const a = 1.528665, b = 1.088493, c = 0.868407, d = 0.631494, e = 0.074911, f = 0.372824, g = 0.16906;
  const n = (v) => +v.toFixed(3);
  const tl = (X, Y) => `${n(x + X * r)} ${n(y + Y * r)}`;
  const tr = (X, Y) => `${n(x + w - X * r)} ${n(y + Y * r)}`;
  const br = (X, Y) => `${n(x + w - X * r)} ${n(y + h - Y * r)}`;
  const bl = (X, Y) => `${n(x + X * r)} ${n(y + h - Y * r)}`;
  return `M${tl(a, 0)}L${tr(a, 0)}C${tr(b, 0)} ${tr(c, 0)} ${tr(d, e)}C${tr(f, g)} ${tr(g, f)} ${tr(e, d)}C${tr(0, c)} ${tr(0, b)} ${tr(0, a)}`
    + `L${br(0, a)}C${br(0, b)} ${br(0, c)} ${br(e, d)}C${br(g, f)} ${br(f, g)} ${br(d, e)}C${br(c, 0)} ${br(b, 0)} ${br(a, 0)}`
    + `L${bl(a, 0)}C${bl(b, 0)} ${bl(c, 0)} ${bl(d, e)}C${bl(f, g)} ${bl(g, f)} ${bl(e, d)}C${bl(0, c)} ${bl(0, b)} ${bl(0, a)}`
    + `L${tl(0, a)}C${tl(0, b)} ${tl(0, c)} ${tl(e, d)}C${tl(g, f)} ${tl(f, g)} ${tl(d, e)}C${tl(c, 0)} ${tl(b, 0)} ${tl(a, 0)}Z`;
}
// The same outline, pulled in by `inset` on every side.
const outline = (inset) => squircle(inset, inset, BODY_W - inset * 2, BODY_H - inset * 2, GEO.r + EDGE - inset);

function buildDevice() {
  const W = BODY_W, H = BODY_H, band = GEO.band;
  const outer = outline(0);
  const glass = outline(band);
  const hole = outline(EDGE);

  // Side buttons sit behind the band and stand 2px proud of it: [y, height, how proud].
  const left = [[163, 34, PROUD], [229, 62, PROUD], [311, 62, PROUD]]; // action, volume up, volume down
  const right = [[262, 100, PROUD, 'l'], [536, 92, 1.1, 'd']]; // power, camera control
  const button = (side) => ([y, h, proud, kind]) => {
    const w = proud + 2.5;
    const x = side === 'l' ? -proud : W - 2.5;
    const fill = kind === 'd' ? `mm-btn-${side}-d` : `mm-btn-${side}`;
    return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="1.3" fill="url(#${fill})"/>`
      + `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="1.3" fill="url(#mm-btn-ends)"/>`;
  };
  // Antenna lines: thin breaks across the band.
  const breaks = [
    [0, 96, band, 1.2], [0, H - 97.2, band, 1.2], [W - band, 96, band, 1.2], [W - band, H - 97.2, band, 1.2],
    [W - 105, 0, 1.2, band], [103.8, H - band, 1.2, band],
  ].map(([x, y, w, h]) => `<rect x="${x}" y="${y}" width="${w}" height="${h}"/>`).join('');

  const shell = $('device-shell');
  shell.setAttribute('viewBox', `-6 0 ${W + 12} ${H}`);
  shell.innerHTML = `
    <defs>
      <linearGradient id="mm-ti" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="${H}">
        <stop offset="0" stop-color="#D8D4CC"/><stop offset=".025" stop-color="#C7C2B9"/><stop offset=".11" stop-color="#B3AEA4"/>
        <stop offset=".3" stop-color="#C3BEB5"/><stop offset=".5" stop-color="#A9A49A"/><stop offset=".7" stop-color="#BBB6AC"/>
        <stop offset=".89" stop-color="#9E998F"/><stop offset=".975" stop-color="#8A857B"/><stop offset="1" stop-color="#79746A"/>
      </linearGradient>
      <linearGradient id="mm-ti-x" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="${W}" y2="0">
        <stop offset="0" stop-color="#FFFFFF" stop-opacity=".2"/><stop offset=".5" stop-color="#FFFFFF" stop-opacity="0"/>
        <stop offset=".5" stop-color="#000000" stop-opacity="0"/><stop offset="1" stop-color="#000000" stop-opacity=".12"/>
      </linearGradient>
      <linearGradient id="mm-rim" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="${W}" y2="${H}">
        <stop offset="0" stop-color="#FFFFFF" stop-opacity=".95"/><stop offset=".45" stop-color="#FFFFFF" stop-opacity=".6"/>
        <stop offset="1" stop-color="#FFFFFF" stop-opacity=".35"/>
      </linearGradient>
      <linearGradient id="mm-glass" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="${W}" y2="${H}">
        <stop offset="0" stop-color="#FFFFFF" stop-opacity=".2"/><stop offset=".3" stop-color="#FFFFFF" stop-opacity=".04"/>
        <stop offset=".7" stop-color="#FFFFFF" stop-opacity=".02"/><stop offset="1" stop-color="#FFFFFF" stop-opacity=".1"/>
      </linearGradient>
      <linearGradient id="mm-btn-l" gradientUnits="userSpaceOnUse" x1="${-PROUD}" y1="0" x2="0.5" y2="0">
        <stop offset="0" stop-color="#8A857B"/><stop offset=".38" stop-color="#E4E1DA"/><stop offset=".8" stop-color="#B4AFA5"/><stop offset="1" stop-color="#8F8A80"/>
      </linearGradient>
      <linearGradient id="mm-btn-r" gradientUnits="userSpaceOnUse" x1="${W + PROUD}" y1="0" x2="${W - 0.5}" y2="0">
        <stop offset="0" stop-color="#7E796F"/><stop offset=".38" stop-color="#D6D2CA"/><stop offset=".8" stop-color="#A9A49A"/><stop offset="1" stop-color="#8A857B"/>
      </linearGradient>
      <linearGradient id="mm-btn-r-d" gradientUnits="userSpaceOnUse" x1="${W + 1.1}" y1="0" x2="${W - 0.5}" y2="0">
        <stop offset="0" stop-color="#6F6A61"/><stop offset=".5" stop-color="#A8A399"/><stop offset="1" stop-color="#7C776D"/>
      </linearGradient>
      <linearGradient id="mm-btn-ends" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#000000" stop-opacity=".32"/><stop offset=".05" stop-color="#000000" stop-opacity="0"/>
        <stop offset=".95" stop-color="#000000" stop-opacity="0"/><stop offset="1" stop-color="#000000" stop-opacity=".36"/>
      </linearGradient>
      <clipPath id="mm-band"><path clip-rule="evenodd" d="${outer}${glass}"/></clipPath>
    </defs>
    <g>${left.map(button('l')).join('')}${right.map(button('r')).join('')}</g>
    <path fill-rule="evenodd" d="${outer}${glass}" fill="url(#mm-ti)"/>
    <path fill-rule="evenodd" d="${outer}${glass}" fill="url(#mm-ti-x)"/>
    <g clip-path="url(#mm-band)" fill="#5E5A52" fill-opacity=".62">${breaks}</g>
    <path d="${outline(0.4)}" fill="none" stroke="#3F3B34" stroke-opacity=".55" stroke-width=".8"/>
    <path d="${outline(band - 1.15)}" fill="none" stroke="url(#mm-rim)" stroke-width=".9"/>
    <path fill-rule="evenodd" d="${glass}${hole}" fill="#030303"/>
    <path d="${glass}" fill="none" stroke="#17150F" stroke-width=".7"/>
    <path d="${outline(band + 0.9)}" fill="none" stroke="url(#mm-glass)" stroke-width=".7"/>`;

  // The shadow that grounds it on the white page: contact, mid, ambient.
  const far = { x: -260, y: -160, w: W + 520, h: H + 520 };
  const filter = (id, blur) => `<filter id="${id}" filterUnits="userSpaceOnUse" x="${far.x}" y="${far.y}" width="${far.w}" height="${far.h}" color-interpolation-filters="sRGB"><feGaussianBlur stdDeviation="${blur}"/></filter>`;
  const shadow = $('device-shadow');
  shadow.setAttribute('viewBox', `0 0 ${W} ${H}`);
  shadow.innerHTML = `
    <defs>${filter('mm-sh-a', 30)}${filter('mm-sh-b', 12)}${filter('mm-sh-c', 2.6)}</defs>
    <path d="${squircle(22, 56, W - 44, H - 52, GEO.r)}" fill="#0A2A19" fill-opacity=".27" filter="url(#mm-sh-a)"/>
    <path d="${squircle(6, 22, W - 12, H - 12, GEO.r + EDGE - 6)}" fill="#07180F" fill-opacity=".2" filter="url(#mm-sh-b)"/>
    <path d="${squircle(1, 4.5, W - 2, H - 2, GEO.r + EDGE - 1)}" fill="#000000" fill-opacity=".34" filter="url(#mm-sh-c)"/>`;
}

// Scale the phone to the space it has, never above 1. `zoom` re-rasterises the text inside the
// iframe; a transform would only stretch its pixels, so that is the fallback.
let zoomWorks = typeof CSS !== 'undefined' && typeof CSS.supports === 'function' && CSS.supports('zoom', '0.5');
let scale = 1;

function fit() {
  if (narrow.matches) return;
  const box = el.phone;
  if (!box.clientHeight || !box.clientWidth) return;
  const padY = Math.min(56, Math.max(20, box.clientHeight * 0.045));
  let k = Math.min(1, (box.clientHeight - padY * 2) / BODY_H, (box.clientWidth - 16) / (BODY_W + 12));
  k = Math.max(0.4, k);
  k = Math.floor(k * GEO.sw) / GEO.sw; // the display is a whole number of pixels wide
  scale = k;
  el.device.classList.toggle('is-transform', !zoomWorks);
  el.device.style.setProperty('--k', String(k));
  el.slot.style.width = `${(BODY_W * k).toFixed(2)}px`;
  el.slot.style.height = `${(BODY_H * k).toFixed(2)}px`;
}

function ensureFrame() {
  if (frame || narrow.matches) return;
  frame = document.createElement('iframe');
  frame.className = 'device__app';
  frame.title = t('frameTitle');
  frame.setAttribute('allow', 'camera; clipboard-write');
  frame.addEventListener('load', onFrameLoad);
  frame.src = `/app?embed=1&lang=${state.lang}&who=${encodeURIComponent(state.who)}`;
  el.screen.prepend(frame);
  setTimeout(wake, READY_TIMEOUT); // reveal anyway if the app never says it is ready
  // Get the phone-glass rules in as soon as the app's document exists, not only once it has loaded.
  // And wake the phone as soon as the app has painted its green launch screen, which it does when
  // its stylesheet is in, well before its scripts have loaded. Otherwise the glass stays black for
  // as long as the scripts take to arrive, which on a slow first load looks broken.
  let tries = 0;
  const early = setInterval(() => {
    const dressed = dressFrame();
    if (dressed && launchScreenPainted()) {
      el.device.dataset.tone = 'light'; // white status bar over the green, until the app says otherwise
      wake();
      clearInterval(early);
    } else if (++tries > 320) clearInterval(early);
  }, 25);
}

function launchScreenPainted() {
  try {
    const doc = frame.contentDocument;
    const boot = doc && doc.querySelector('.boot, .splash');
    return Boolean(boot) && getComputedStyle(boot).backgroundColor !== 'rgba(0, 0, 0, 0)';
  } catch (err) { return false; }
}

// A phone never shows a desktop scrollbar. On a laptop the browser would draw one inside the
// display, so the stage hides scrollbars in the embedded app. This is the only thing it changes
// inside the app; everything else goes through the message contract.
function dressFrame() {
  try {
    const doc = frame.contentDocument;
    if (!doc || !doc.head || doc.location.href === 'about:blank') return false;
    if (!doc.getElementById('mm-stage-glass')) {
      const style = doc.createElement('style');
      style.id = 'mm-stage-glass';
      style.textContent = '*{scrollbar-width:none}*::-webkit-scrollbar{display:none}';
      doc.head.append(style);
    }
    return true;
  } catch (err) { return false; }
}

function onFrameLoad() {
  let inner = null;
  try { inner = frame.contentWindow; inner.document; } catch (err) { inner = null; }
  if (!inner) return;
  dressFrame();
  // Touching the phone hands control to the visitor: the tour stops advancing by itself.
  const taken = () => { if (state.mode === 'tour' && state.auto) setAuto(false); };
  ['pointerdown', 'keydown', 'wheel', 'touchstart'].forEach((type) => {
    try { inner.addEventListener(type, taken, { capture: true, passive: true }); } catch (err) { /* ignore */ }
  });
  // If `zoom` did not reach into the frame, the app would lay itself out too narrow: use a transform.
  if (zoomWorks && scale < 0.97 && Math.abs(inner.innerWidth - GEO.sw) > 4) {
    zoomWorks = false;
    fit();
  }
}

function wake() { el.device.classList.add('is-awake'); }

function renderClock() {
  const now = new Date();
  el.clock.textContent = `${now.getHours()}${state.lang === 'fi' ? '.' : ':'}${String(now.getMinutes()).padStart(2, '0')}`;
}
function runClock() {
  renderClock();
  const now = new Date();
  setTimeout(runClock, (60 - now.getSeconds()) * 1000 - now.getMilliseconds() + 40);
}

/* ---------- Brand slot ---------- */

// The bank's logo comes only from the bank's own files in /assets/brand (git-ignored). The page
// asks for the full logo, then the mark alone; if neither is there it shows a neutral mark.
// Nothing here draws or imitates the logo.
function loadBrand() {
  const slot = $('brand-slot');
  const img = $('brand-logo');
  if (!slot || !img) return;
  const fallbacks = ['/assets/brand/logo.svg'];
  const failed = () => {
    const next = fallbacks.shift();
    if (next) {
      img.classList.add('brand__logo--mark');
      img.width = 40;
      img.src = next;
      return;
    }
    img.remove();
    slot.classList.add('is-placeholder');
    slot.querySelector('.brand__mark').hidden = false;
  };
  img.addEventListener('error', failed);
  if (img.complete && img.naturalWidth === 0) failed(); // it had already failed before this script ran
}

/* ---------- Demo customer chooser ---------- */

const currentPersona = () => state.personas.find((p) => p.customer_id === state.who) || null;

function personaText(p) {
  if (!p) return { label: '', blurb: '', meta: '' };
  const w = words();
  const local = (w.personas && w.personas[p.customer_id]) || {};
  const area = (w.areas && w.areas[p.area]) || p.area || '';
  let income = '';
  if (Number.isFinite(p.monthly_income)) {
    const amount = new Intl.NumberFormat(LOCALES[state.lang], { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(p.monthly_income);
    income = t('perMonth', { amount });
  }
  return {
    label: local.label || p.label || p.customer_id,
    blurb: local.blurb || p.blurb || '',
    meta: [p.age, area, income].filter(Boolean).join(' · '),
  };
}

function make(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}
function icon(name, className) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', className || 'ico');
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `#${name}`);
  svg.append(use);
  return svg;
}

function renderPicker() {
  const current = currentPersona();
  // Until the list arrives the chooser holds its place as a quiet placeholder, so nothing jumps.
  el.customer.hidden = state.mode === 'tour' || (!current && state.personasDone);
  el.customer.classList.toggle('is-loading', !current);
  el.pickerBtn.disabled = !current;
  if (!current) return;
  const text = personaText(current);
  $('picker-name').textContent = text.label;
  $('picker-meta').textContent = text.meta;
  $('picker-blurb').textContent = text.blurb;
  el.pickerBtn.setAttribute('aria-label', `${t('customerChange')}: ${text.label}`);
  el.pickerPop.replaceChildren(...state.personas.map((p) => {
    const info = personaText(p);
    const option = make('button', 'picker__opt');
    option.type = 'button';
    option.dataset.who = p.customer_id;
    option.setAttribute('aria-pressed', String(p.customer_id === state.who));
    const body = make('span', 'picker__text');
    const line = make('span', 'picker__line');
    line.append(make('strong', '', info.label), make('span', 'picker__meta', info.meta));
    body.append(line, make('span', 'picker__blurb', info.blurb));
    option.append(icon('i-check'), body);
    return option;
  }));
}

const picker = {
  open: false,
  timer: 0,
  show() {
    if (this.open) return;
    this.open = true;
    clearTimeout(this.timer);
    const rect = el.pickerBtn.getBoundingClientRect();
    const above = rect.top - document.querySelector('.top').getBoundingClientRect().bottom - 16;
    const below = window.innerHeight - rect.bottom - 16;
    const side = below >= 320 || below > above ? 'below' : 'above';
    el.pickerPop.dataset.side = side;
    el.pickerPop.style.maxHeight = `${Math.max(160, Math.min(480, side === 'below' ? below : above))}px`;
    el.pickerPop.classList.add('is-closed');
    el.pickerPop.hidden = false;
    el.pickerBtn.setAttribute('aria-expanded', 'true');
    void el.pickerPop.offsetWidth; // start the transition from the closed state
    el.pickerPop.classList.remove('is-closed');
    const selected = el.pickerPop.querySelector('[aria-pressed="true"]') || el.pickerPop.firstElementChild;
    if (selected) selected.focus({ preventScroll: true });
    if (selected) selected.scrollIntoView({ block: 'nearest' });
  },
  hide(refocus) {
    if (!this.open) return;
    this.open = false;
    el.pickerBtn.setAttribute('aria-expanded', 'false');
    el.pickerPop.classList.add('is-closed');
    this.timer = setTimeout(() => { el.pickerPop.hidden = true; }, 170);
    if (refocus) el.pickerBtn.focus({ preventScroll: true });
  },
};

function choosePersona(id) {
  const persona = state.personas.find((p) => p.customer_id === id);
  picker.hide(true);
  if (!persona || id === state.who) return;
  state.who = id;
  store.set(KEY_WHO, id);
  renderPicker();
  post('who', { id, label: personaText(persona).label });
}

async function loadPersonas() {
  try {
    const response = await fetch('/api/personas', { headers: { Accept: 'application/json' } });
    const list = response.ok ? await response.json() : null;
    if (Array.isArray(list)) state.personas = list.filter((p) => p && isCustomer(p.customer_id));
    if (state.personas.length && !currentPersona()) {
      // The remembered customer is not one of the demo customers: fall back to one that is.
      const fallback = state.personas.find((p) => p.customer_id === DEFAULT_WHO) || state.personas[0];
      state.who = fallback.customer_id;
      post('who', { id: state.who, label: personaText(fallback).label });
    }
  } catch (err) { /* the page works without the chooser */ }
  state.personasDone = true;
  renderPicker();
}

/* ---------- Tour ---------- */

// The tour runs on its own timer and never waits for the app to answer.
const timer = { id: 0, startedAt: 0, left: 0, total: 0, running: false, fill: null, askId: 0 };

function stopTimer() {
  clearTimeout(timer.id);
  timer.running = false;
  if (timer.fill) { timer.fill.cancel(); timer.fill = null; }
}
// A step with no `seconds` (the closing step) rests: the tour stays there until the visitor moves on.
const rests = () => !STEPS[state.step].seconds;

function startTimer() {
  stopTimer();
  timer.total = timer.left = (STEPS[state.step].seconds || 0) * 1000;
  if (!timer.total) return;
  const bar = el.bar.children[state.step] && el.bar.children[state.step].firstElementChild;
  if (bar && typeof bar.animate === 'function') {
    timer.fill = bar.animate([{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], { duration: timer.total, easing: 'linear', fill: 'both' });
    timer.fill.pause();
  }
  if (!document.hidden) resumeTimer();
}
function resumeTimer() {
  if (timer.running || timer.left <= 0) return;
  timer.running = true;
  timer.startedAt = performance.now();
  timer.id = setTimeout(() => { timer.running = false; go(1, {}); }, timer.left);
  if (timer.fill) timer.fill.play();
}
function holdTimer() {
  if (!timer.running) return;
  clearTimeout(timer.id);
  timer.running = false;
  timer.left = Math.max(0, timer.left - (performance.now() - timer.startedAt));
  if (timer.fill) timer.fill.pause();
}

function setAuto(on) {
  state.auto = Boolean(on) && !reduceMotion.matches;
  renderToggle();
  if (state.mode !== 'tour') return;
  if (state.auto) startTimer(); else stopTimer();
  renderBar();
}

function renderToggle() {
  // Nothing to pause on a step that rests, so the button is not offered there.
  const hide = reduceMotion.matches || rests();
  if (hide && document.activeElement === el.toggle) el.next.focus({ preventScroll: true });
  el.toggle.hidden = hide;
  el.toggle.dataset.auto = state.auto ? 'on' : 'off';
  const label = state.auto ? t('pause') : t('play');
  el.toggle.setAttribute('aria-label', label);
  el.toggle.title = label;
}

function renderBar() {
  if (el.bar.children.length !== STEPS.length) {
    el.bar.replaceChildren(...STEPS.map(() => { const seg = make('span', 'seg'); seg.append(make('i')); return seg; }));
  }
  [...el.bar.children].forEach((seg, i) => {
    // Done steps are full. The current one fills as its time runs, or is full when the tour is paused.
    seg.classList.toggle('is-done', i < state.step || (i === state.step && !timer.fill));
  });
  el.bar.setAttribute('aria-valuemax', String(STEPS.length));
  el.bar.setAttribute('aria-valuenow', String(state.step + 1));
  el.bar.setAttribute('aria-valuetext', t('of', { n: state.step + 1, total: STEPS.length }));
}

const EASE_OUT = 'cubic-bezier(0.23, 1, 0.32, 1)';

// One row of the closing step: the figure (or an icon) a glance takes away, then what it stands for.
function proofRow(row, iconName) {
  const item = make('li', 'proof__row');
  const token = make('span', row.figure ? 'proof__token proof__token--figure' : 'proof__token', row.figure || null);
  if (!row.figure && iconName) token.append(icon(`i-${iconName}`));
  const body = make('p', 'proof__body');
  body.append(make('strong', 'proof__lead', row.lead), ' ', make('span', 'proof__text', row.text));
  item.append(token, body);
  return item;
}

// The story is centred in the stage, so when the caption changes height (only the closing step is
// taller) the whole panel moves: what is above the caption goes up, what is below it goes down.
let parts = null;
const tops = () => {
  if (!parts) parts = [...el.panels.tour.children].concat(document.querySelector('.disclaimer') || []);
  // Where the layout puts each part: `offsetTop` leaves out any animation still in flight.
  return parts.map((node) => node.offsetTop);
};
// Glide each part from where it was to where it is now, instead of letting it jump. The caption
// travels with the bar above it while it fades in, so the two never cross.
function glide(before) {
  tops().forEach((top, i) => {
    const dy = before[i] - top;
    if (Math.abs(dy) < 1 || typeof parts[i].animate !== 'function') return;
    parts[i].animate([{ transform: `translateY(${dy}px)` }, { transform: 'translateY(0)' }], { duration: 360, easing: EASE_OUT });
  });
}

function renderStep({ quiet } = {}) {
  const w = words();
  const step = STEPS[state.step];
  const copy = w.steps[state.step] || tour.en.steps[state.step];
  const last = state.step === STEPS.length - 1;
  const proof = Array.isArray(copy.proof) ? copy.proof : null;
  const animate = !quiet && !still && typeof el.copy.animate === 'function';
  const move = animate && !reduceMotion.matches; // keyboard moves, `?still=1` and reduced motion: nothing moves
  const before = move ? tops() : null;
  $('tour-count').textContent = t('of', { n: state.step + 1, total: STEPS.length });
  $('tour-title').textContent = copy.title;
  el.text.textContent = proof ? '' : copy.text;
  el.text.hidden = Boolean(proof);
  el.proof.replaceChildren(...(proof || []).map((row, i) => proofRow(row, step.icons && step.icons[i])));
  el.proof.hidden = !proof;
  el.stage.classList.toggle('is-closing', Boolean(proof));
  $('tour-next-label').textContent = step.closing ? w.tryIt : last ? w.finish : w.next;
  el.back.setAttribute('aria-disabled', String(state.step === 0));
  renderToggle();
  renderBar();
  if (animate) {
    const from = reduceMotion.matches ? { opacity: 0 } : { opacity: 0, transform: 'translateY(6px)' };
    const to = reduceMotion.matches ? { opacity: 1 } : { opacity: 1, transform: 'translateY(0)' };
    el.copy.animate([from, to], { duration: reduceMotion.matches ? 160 : 280, easing: EASE_OUT });
  }
  if (move) {
    glide(before);
    // The proofs come in one after the other, each a beat behind the one above.
    [...el.proof.children].forEach((row, i) => {
      row.animate([{ opacity: 0, transform: 'translateY(8px)' }, { opacity: 1, transform: 'translateY(0)' }],
        { duration: 380, delay: 60 + i * 50, easing: EASE_OUT, fill: 'backwards' });
    });
  }
}

function sendStep() {
  const step = STEPS[state.step];
  clearTimeout(timer.askId);
  post('goto', { route: step.route, highlight: step.highlight });
  if (step.ask && !state.asked) {
    const copy = words().steps[state.step] || tour.en.steps[state.step];
    // Once per run: going back to this step must not ask the same question twice.
    timer.askId = setTimeout(() => {
      state.asked = true;
      post('ask', { text: copy.ask });
      // The app drops its highlight when a question is sent, so the highlight is named again
      // after the question: the app then waits for the answer and rings it when it arrives.
      post('goto', { route: step.route, highlight: step.highlight });
    }, 450);
  }
  if (step.photo && !state.photosSent.has(state.step)) {
    // Once per run as well: the app sends its sample photo (the price tag, or the bill) and the model reads it.
    const at = state.step;
    timer.askId = setTimeout(() => {
      state.photoAsked = true;
      state.photosSent.add(at);
      post('ask', { photo: step.photo === 'bill' ? 'bill' : 'sample' });
      post('goto', { route: step.route, highlight: step.highlight });
    }, 450);
  }
  if (step.closing && !state.asked && !state.photoAsked) {
    // The closing step rings the evidence under the last answer. A visitor who skipped ahead has
    // asked nothing yet, and the chat would be empty: ask the tour's own question now instead.
    const at = STEPS.findIndex((s) => s.ask);
    const text = at >= 0 && (words().steps[at] || tour.en.steps[at]).ask;
    if (text) {
      timer.askId = setTimeout(() => {
        state.asked = true;
        post('ask', { text });
        post('goto', { route: step.route, highlight: step.highlight });
      }, 450);
    }
  }
}

function showStep(index, { keyboard } = {}) {
  state.step = Math.max(0, Math.min(STEPS.length - 1, index));
  if (state.auto) startTimer(); else stopTimer();
  renderStep({ quiet: Boolean(keyboard) }); // keyboard moves are instant: no animation on a key press
  sendStep();
}

function go(delta, { manual, keyboard } = {}) {
  if (state.mode !== 'tour') return;
  const target = state.step + delta;
  if (target < 0) return;
  if (manual && state.auto) { state.auto = false; }
  if (target >= STEPS.length) { finishTour(keyboard); return; }
  showStep(target, { keyboard });
}

function startTour(event) {
  const keyboard = Boolean(event && event.detail === 0);
  picker.hide(false);
  state.asked = false;
  state.photoAsked = false;
  state.photosSent.clear();
  state.auto = !reduceMotion.matches;
  // Lay the first step out while the panel is still hidden: after "Watch again" it would otherwise
  // enter in the shape of the closing step and then move.
  state.step = 0;
  renderStep({ quiet: true });
  setMode('tour', { keyboard });
  showStep(0, { keyboard });
}

function finishTour(keyboard) {
  stopTimer();
  clearTimeout(timer.askId);
  state.sawTour = true;
  post('goto', { route: 'trainer', highlight: null });
  setMode('end', { keyboard });
}

// Skip goes to the app's home screen; Escape leaves the phone on the screen it is showing.
function leaveTour(keyboard, stay) {
  stopTimer();
  clearTimeout(timer.askId);
  post('goto', { route: stay ? STEPS[state.step].route : 'home', highlight: null });
  setMode('free', { keyboard });
}

// The app opens the way it does on a phone: launch screen, then its home screen.
function openApp() {
  stopTimer();
  clearTimeout(timer.askId);
  post('goto', { route: 'home', highlight: null });
  post('splash');
  if (state.mode !== 'end') setMode('free'); // the closing panel stays put: nothing moves under the pointer
}

function renderEnd() {
  const free = state.mode === 'free';
  $('end-tag').textContent = t(free ? 'freeTag' : 'endTag');
  $('end-title').textContent = t(free ? 'freeTitle' : 'endTitle');
  $('end-open').hidden = free;
  $('end-again-label').textContent = t(state.sawTour ? 'again' : 'start');
  const use = $('end-again').querySelector('use');
  if (use) use.setAttribute('href', state.sawTour ? '#i-again' : '#i-play');
}

function askButton(text) {
  const button = make('button', 'ask');
  button.type = 'button';
  button.append(icon('i-ask'), make('span', '', text), icon('i-right', 'ico ico--s'));
  button.addEventListener('click', () => post('ask', { text }));
  return button;
}

function setMode(mode, { keyboard } = {}) {
  const previous = state.mode;
  state.mode = mode;
  el.stage.dataset.mode = mode;
  if (mode !== 'tour') el.stage.classList.remove('is-closing'); // the closing step's layout ends with the tour
  $('story').classList.remove('is-first'); // the first-load entrance is over
  const visible = mode === 'intro' ? 'intro' : mode === 'tour' ? 'tour' : 'end';
  const hadFocus = document.activeElement && document.activeElement !== document.body
    && Object.values(el.panels).some((panel) => panel.contains(document.activeElement));
  Object.entries(el.panels).forEach(([name, panel]) => {
    const show = name === visible;
    const wasHidden = panel.hidden;
    panel.hidden = !show;
    panel.classList.remove('is-entering');
    if (show && wasHidden && !keyboard) {
      void panel.offsetWidth;
      panel.classList.add('is-entering');
    }
  });
  renderEnd();
  renderPicker();
  // Keep the keyboard somewhere useful when the control that was pressed has just gone away.
  if (hadFocus || keyboard || previous !== mode) {
    const target = mode === 'tour' ? el.next : mode === 'intro' ? $('start') : (mode === 'end' ? $('end-open') : $('end-again'));
    if (target && (hadFocus || keyboard)) target.focus({ preventScroll: true });
  }
}

/* ---------- Wiring ---------- */

$('choose').addEventListener('click', (event) => {
  const button = event.target.closest('[data-lang]');
  if (button) setLang(button.dataset.lang);
});
$('lang').addEventListener('click', (event) => {
  const button = event.target.closest('[data-lang]');
  if (button) setLang(button.dataset.lang);
});
$('start').addEventListener('click', startTour);
$('open').addEventListener('click', openApp);
$('end-open').addEventListener('click', openApp);
$('end-again').addEventListener('click', startTour);
$('tour-skip').addEventListener('click', (event) => leaveTour(event.detail === 0, false));
// A click with no pointer behind it (detail 0) came from the keyboard: those moves are instant.
el.next.addEventListener('click', (event) => go(1, { manual: true, keyboard: event.detail === 0 }));
el.back.addEventListener('click', (event) => { if (state.step > 0) go(-1, { manual: true, keyboard: event.detail === 0 }); });
el.toggle.addEventListener('click', () => setAuto(!state.auto));

el.pickerBtn.addEventListener('click', () => (picker.open ? picker.hide(true) : picker.show()));
el.pickerPop.addEventListener('click', (event) => {
  const option = event.target.closest('[data-who]');
  if (option) choosePersona(option.dataset.who);
});
$('picker').addEventListener('keydown', (event) => {
  if (!picker.open) return;
  const options = [...el.pickerPop.querySelectorAll('.picker__opt')];
  const at = options.indexOf(document.activeElement);
  const move = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: options.length - 1 }[event.key];
  if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); picker.hide(true); }
  else if (move !== undefined && options.length) {
    event.preventDefault();
    options[(move + options.length) % options.length].focus();
  }
});
$('picker').addEventListener('focusout', (event) => {
  if (picker.open && event.relatedTarget && !$('picker').contains(event.relatedTarget)) picker.hide(false);
});
document.addEventListener('pointerdown', (event) => {
  if (picker.open && !$('picker').contains(event.target)) picker.hide(false);
});
window.addEventListener('blur', () => { if (picker.open) picker.hide(false); });

// Right or Space: next. Left: back. Escape: end the tour.
document.addEventListener('keydown', (event) => {
  if (state.mode !== 'tour' || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
  const onControl = event.target instanceof Element && event.target.closest('button, a, input, select, textarea');
  if (event.key === 'ArrowRight') { event.preventDefault(); go(1, { manual: true, keyboard: true }); }
  else if (event.key === 'ArrowLeft') { event.preventDefault(); go(-1, { manual: true, keyboard: true }); }
  else if (event.key === ' ' || event.code === 'Space') {
    if (onControl) return; // a focused button handles Space itself
    event.preventDefault();
    go(1, { manual: true, keyboard: true });
  } else if (event.key === 'Escape') { event.preventDefault(); leaveTour(true, true); }
});

// The tour's timer stops while the tab is in the background.
document.addEventListener('visibilitychange', () => {
  if (state.mode !== 'tour' || !state.auto) return;
  if (document.hidden) holdTimer(); else resumeTimer();
});

const onMotionChange = () => { if (reduceMotion.matches) setAuto(false); else renderToggle(); };
if (reduceMotion.addEventListener) reduceMotion.addEventListener('change', onMotionChange);

const onNarrowChange = () => {
  if (narrow.matches) {
    if (state.mode !== 'intro') { stopTimer(); setMode('intro'); }
    return;
  }
  fit();
  ensureFrame();
  if (!state.personas.length) loadPersonas();
};
if (narrow.addEventListener) narrow.addEventListener('change', onNarrowChange);

/* ---------- Start ---------- */

if (still) document.documentElement.classList.add('is-still');

buildDevice();
applyLang();
runClock();
loadBrand();
fit();
if (typeof ResizeObserver === 'function') new ResizeObserver(fit).observe(el.phone);
window.addEventListener('resize', fit);
ensureFrame();
requestAnimationFrame(() => el.slot.classList.add('is-in')); // the phone's one entrance
if (!narrow.matches) loadPersonas();
