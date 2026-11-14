// Shared helpers: the view library, languages, formatting, the API client and small hooks.
import { useState, useEffect, useRef, useContext, createContext } from '../vendor/preact-htm.js';
import en from '../i18n/en.js';
import fi from '../i18n/fi.js';
import sv from '../i18n/sv.js';
import { RULES } from './phrases.js';

export {
  h, html, render, Component, createContext,
  useState, useReducer, useEffect, useLayoutEffect, useRef,
  useMemo, useCallback, useContext, useErrorBoundary,
} from '../vendor/preact-htm.js';

/* ---------- storage (never throws) ---------- */

export const store = {
  get(key) {
    try {
      const raw = window.localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  },
  set(key, value) {
    try {
      if (value === null || value === undefined) window.localStorage.removeItem(key);
      else window.localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      /* private mode or blocked storage: the app still works for this visit */
    }
  },
};

/* ---------- languages ---------- */

const DICTS = { en, fi, sv };
export const LANGS = ['en', 'fi', 'sv'];
export const LANG_NAMES = { en: 'English', fi: 'Suomi', sv: 'Svenska' };
const LANG_KEY = 'money-mentor.lang';
const listeners = new Set();
let LANG = 'en';

const okLang = (v) => (typeof v === 'string' && LANGS.includes(v.toLowerCase().slice(0, 2)) ? v.toLowerCase().slice(0, 2) : null);

/** First language: ?lang=, then the saved one, then English. */
export function initLang() {
  let fromUrl = null;
  try { fromUrl = okLang(new URLSearchParams(window.location.search).get('lang')); } catch (e) { fromUrl = null; }
  LANG = fromUrl || okLang(store.get(LANG_KEY)) || 'en';
  document.documentElement.lang = LANG;
  return LANG;
}

export const getLang = () => LANG;

export function setLang(next) {
  const lang = okLang(next);
  if (!lang) return LANG;
  document.documentElement.lang = lang;
  if (lang === LANG) return LANG;
  LANG = lang;
  store.set(LANG_KEY, lang);
  listeners.forEach((fn) => fn(lang));
  return LANG;
}

export function onLang(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** The language context: a component that reads it re-renders when the language changes. */
export const Lang = createContext('en');
export const useLang = () => useContext(Lang);

/**
 * A string in the current language, English when it is missing.
 * {name} is filled from vars. With vars.n, "key_one" / "key_other" is chosen first.
 */
export function t(key, vars) {
  const d = DICTS[LANG] || en;
  let s;
  if (vars && vars.n !== undefined && vars.n !== null) {
    const k = key + (Number(vars.n) === 1 ? '_one' : '_other');
    s = d[k] ?? en[k];
  }
  if (s === undefined) s = d[key] ?? en[key];
  if (s === undefined) return key;
  if (!vars) return s;
  return s.replace(/\{(\w+)\}/g, (m, k) => (vars[k] !== undefined && vars[k] !== null ? String(vars[k]) : m));
}

/** True when there is a string for this key (in the current language or in English). */
export const has = (key) => (DICTS[LANG] || en)[key] !== undefined || en[key] !== undefined;

/** The English string, whatever the current language (for the English-only keyword router). */
export const english = (key) => en[key] ?? key;

/** A value from the data (a category, a status) in the current language: "cat" + "Groceries". */
export function tv(prefix, value) {
  if (value === null || value === undefined || value === '') return '';
  const k = `${prefix}.${value}`;
  const d = DICTS[LANG] || en;
  return d[k] ?? en[k] ?? String(value);
}

/* ---------- the three baskets: one fixed colour each, everywhere ---------- */

function basket(id, emoji) {
  return {
    id, emoji,
    get name() { return t(`basket.${id}.name`); },
    get short() { return t(`basket.${id}.short`); },
    get meaning() { return t(`basket.${id}.meaning`); },
  };
}
export const BASKETS = {
  essentials: basket('essentials', '🏠'),
  unexpected: basket('unexpected', '🔧'),
  everyday: basket('everyday', '☕'),
};
export const BASKET_ORDER = ['essentials', 'unexpected', 'everyday'];
const BASKET_EN = {
  essentials: ['regular essentials', 'essentials', 'regular_essentials'],
  unexpected: ['unexpected necessities', 'unexpected', 'unexpected_necessities'],
  everyday: ['everyday spending', 'everyday', 'everyday_spending'],
};

/** Find a basket from an id ("everyday") or a name ("Everyday spending"). */
export function basketOf(value) {
  if (!value) return null;
  const v = String(value).toLowerCase();
  for (const id of BASKET_ORDER) {
    if (v === id || BASKET_EN[id].includes(v)) return BASKETS[id];
    const b = BASKETS[id];
    if (v === b.name.toLowerCase() || v === b.short.toLowerCase()) return b;
  }
  for (const id of BASKET_ORDER) {
    if (v.includes(BASKET_EN[id][0])) return BASKETS[id];
  }
  return null;
}

/* ---------- numbers and dates ---------- */

const LOCALE = { en: 'en-IE', fi: 'fi-FI', sv: 'sv-FI' };
const fmtCache = {};
function F() {
  if (!fmtCache[LANG]) {
    const l = LOCALE[LANG] || LOCALE.en;
    fmtCache[LANG] = {
      F0: new Intl.NumberFormat(l, { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }),
      F2: new Intl.NumberFormat(l, { style: 'currency', currency: 'EUR' }),
      N0: new Intl.NumberFormat(l, { maximumFractionDigits: 0 }),
      N1: new Intl.NumberFormat(l, { maximumFractionDigits: 1 }),
      N2: new Intl.NumberFormat(l, { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    };
  }
  return fmtCache[LANG];
}

const minus = (s) => s.replace(/^-/, '−');
const isNum = (v) => v !== null && v !== '' && v !== undefined && Number.isFinite(Number(v));

/** Euros. Whole euros from 100 up, cents below. mode: 'whole' | 'cents' to force. */
export function eur(v, mode) {
  if (!isNum(v)) return '–';
  const n = Number(v);
  const f = F();
  if (mode === 'whole' || (mode !== 'cents' && Math.abs(n) >= 100)) {
    const r = Math.round(n);
    return minus(f.F0.format(r === 0 ? 0 : r));
  }
  if (Math.abs(n) < 0.005) return mode === 'cents' ? f.F2.format(0) : f.F0.format(0);
  return minus(f.F2.format(n));
}

/** Euros with an explicit sign, for budget lines. */
export function eurSigned(v, mode) {
  if (!isNum(v)) return '–';
  const n = Number(v);
  if (Math.abs(n) < 0.005) return eur(0, mode);
  return n > 0 ? '+' + eur(n, mode) : eur(n, mode);
}

/** Short euros for chart labels: €950, €1.9k, €12k (1,9 t€ in Finnish). */
export function eurShort(v) {
  if (!isNum(v)) return '–';
  const n = Number(v);
  const a = Math.abs(n);
  const sign = n < 0 ? '−' : '';
  let body;
  let k = false;
  if (a >= 10000) { body = String(Math.round(a / 1000)); k = true; }
  else if (a >= 1000) { body = (Math.round(a / 100) / 10).toFixed(1).replace(/\.0$/, ''); k = true; }
  else body = String(Math.round(a));
  if (LANG === 'en') return `${sign}€${body}${k ? 'k' : ''}`;
  return `${sign}${body.replace('.', ',')}${k ? (LANG === 'fi' ? ' t€' : ' k€') : ' €'}`;
}

export function num(v, digits) {
  if (!isNum(v)) return '–';
  const n = Number(v);
  const f = F();
  if (digits === 0) return minus(f.N0.format(n));
  if (digits === 2) return minus(f.N2.format(n));
  return minus(f.N1.format(n));
}

export function pct(v) {
  if (!isNum(v)) return '–';
  return LANG === 'en' ? `${num(v)}%` : `${num(v)} %`;
}

const MONTHS = {
  en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
  fi: ['tammi', 'helmi', 'maalis', 'huhti', 'touko', 'kesä', 'heinä', 'elo', 'syys', 'loka', 'marras', 'joulu'],
  sv: ['jan', 'feb', 'mars', 'apr', 'maj', 'juni', 'juli', 'aug', 'sep', 'okt', 'nov', 'dec'],
};
const MONTHS_LONG = {
  en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
  fi: ['tammikuu', 'helmikuu', 'maaliskuu', 'huhtikuu', 'toukokuu', 'kesäkuu', 'heinäkuu', 'elokuu', 'syyskuu', 'lokakuu', 'marraskuu', 'joulukuu'],
  sv: ['januari', 'februari', 'mars', 'april', 'maj', 'juni', 'juli', 'augusti', 'september', 'oktober', 'november', 'december'],
};
const DAYS = {
  en: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
  fi: ['su', 'ma', 'ti', 'ke', 'to', 'pe', 'la'],
  sv: ['sön', 'mån', 'tis', 'ons', 'tors', 'fre', 'lör'],
};
const of = (table) => table[LANG] || table.en;

export function parseDate(s) {
  const m = /^(\d{4})-(\d{2})(?:-(\d{2}))?/.exec(String(s ?? ''));
  if (!m) return null;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, m[3] ? Number(m[3]) : 1);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function isoDate(d) {
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** "15 Oct" (15.10. in Finnish and Swedish), optionally with weekday and/or year. */
export function fmtDate(s, opts = {}) {
  const d = parseDate(s);
  if (!d) return s ? String(s) : '–';
  let out;
  if (LANG === 'en') {
    out = `${d.getDate()} ${MONTHS.en[d.getMonth()]}`;
    if (opts.year) out += ` ${d.getFullYear()}`;
  } else {
    out = `${d.getDate()}.${d.getMonth() + 1}.`;
    if (opts.year) out += d.getFullYear();
  }
  if (opts.weekday) out = `${of(DAYS)[d.getDay()]} ${out}`;
  return out;
}

/** "2026-04" -> "Apr" or "Apr 2026" (huhti, huhtikuu 2026). */
export function fmtMonth(s, withYear) {
  const d = parseDate(s);
  if (!d) return s ? String(s) : '–';
  if (!withYear) return of(MONTHS)[d.getMonth()];
  return LANG === 'en' ? `${MONTHS.en[d.getMonth()]} ${d.getFullYear()}` : `${of(MONTHS_LONG)[d.getMonth()]} ${d.getFullYear()}`;
}

/** "September 2026" (syyskuu 2026). */
export function fmtMonthLong(s) {
  const d = parseDate(s);
  if (!d) return s ? String(s) : '–';
  return `${of(MONTHS_LONG)[d.getMonth()]} ${d.getFullYear()}`;
}

/** A period from the server, { start, end, label }, said in the current language. */
export function periodLabel(p) {
  if (!p || typeof p !== 'object') return '';
  if (LANG === 'en' && p.label) return fragment(p.label);
  const a = parseDate(p.start);
  const b = parseDate(p.end);
  if (!a || !b) return p.label ? fragment(p.label) : '';
  if (p.start === p.end) return fmtDate(p.start, { year: true });
  const lastDay = new Date(b.getFullYear(), b.getMonth() + 1, 0).getDate();
  const wholeMonths = a.getDate() === 1 && b.getDate() === lastDay;
  if (wholeMonths && a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth()) return fmtMonthLong(p.start);
  if (wholeMonths) return `${fmtMonth(p.start, true)} – ${fmtMonth(p.end, true)}`;
  return `${fmtDate(p.start)} – ${fmtDate(p.end, { year: true })}`;
}

/* ---------- sentences from the server ---------- */

const EN_MONTH = MONTHS_LONG.en.map((m) => m.toLowerCase());

function moneyText(raw) {
  const n = Number(String(raw).replace(/,/g, ''));
  if (!Number.isFinite(n)) return `€${raw}`;
  return eur(n, /\.\d/.test(String(raw)) ? 'cents' : 'whole');
}

/** "EUR 1,234" -> "€1,234" (1 234 €) and ISO dates -> "15 Oct" (15.10.). */
function fragment(text) {
  return String(text)
    .replace(/\bEUR\s?(-?\d[\d,]*(?:\.\d+)?)/g, (m, n) => moneyText(n))
    .replace(/\b\d{4}-\d{2}-\d{2}\b/g, (m) => fmtDate(m));
}

function nameText(raw) {
  const s = String(raw);
  const lower = s === s.toLowerCase();
  const d = DICTS[LANG] || en;
  const keys = Object.keys(d);
  const want = s.toLowerCase();
  for (const prefix of ['cat.', 'sub.', 'basketname.']) {
    const hit = keys.find((k) => k.startsWith(prefix) && k.slice(prefix.length).toLowerCase() === want);
    if (hit) return lower ? d[hit].toLowerCase() : d[hit];
  }
  return s;
}

function groupText(kind, raw) {
  if (raw === undefined) return '';
  if (kind === 'money') return moneyText(raw);
  if (kind === 'num') {
    const n = Number(raw);
    return Number.isFinite(n) ? num(n, /\./.test(raw) ? undefined : 0) : raw;
  }
  if (kind === 'date') return fmtDate(raw);
  if (kind === 'monthyear') {
    const m = /^([A-Za-z]+) (\d{4})$/.exec(raw);
    const at = m ? EN_MONTH.indexOf(m[1].toLowerCase()) : -1;
    return at >= 0 ? `${of(MONTHS_LONG)[at]} ${m[2]}` : raw;
  }
  if (kind === 'name') return nameText(raw);
  return raw;
}

function phrase(text) {
  const d = DICTS[LANG];
  if (!d) return null;
  for (const rule of RULES) {
    const tpl = d['ph.' + rule.key];
    if (tpl === undefined) continue;
    const m = rule.re.exec(text);
    if (!m) continue;
    const out = tpl.replace(/\{(\d)\}/g, (x, i) => groupText(rule.g[Number(i) - 1], m[Number(i)]));
    // A template that opens with a filled-in name starts the sentence: give it a capital.
    return tpl.charAt(0) === '{' ? out.charAt(0).toUpperCase() + out.slice(1) : out;
  }
  return null;
}

/**
 * Tidy a server sentence for the screen. In Finnish and Swedish a known sentence is
 * rebuilt from its template; anything else keeps its words and gets local numbers and dates.
 */
export function nice(text) {
  if (text === null || text === undefined) return '';
  const s = String(text).trim();
  if (LANG !== 'en') {
    const hit = phrase(s);
    if (hit !== null) return hit;
  }
  return fragment(s);
}

/** The same, but nothing at all when a sentence has no translation: for card text the answer already covers. */
export function said(text) {
  if (text === null || text === undefined || text === '') return '';
  if (LANG === 'en') return fragment(String(text).trim());
  return phrase(String(text).trim()) || '';
}

/** "application_created" -> "Application created" (or its translation under "word."). */
export function words(key) {
  const raw = String(key ?? '');
  const d = DICTS[LANG] || en;
  if (d['word.' + raw] !== undefined) return d['word.' + raw];
  const s = raw.replace(/[_-]+/g, ' ').trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
}

export function initials(label) {
  // Words are split on spaces only, so "Month-end stretcher" is MS, not ME.
  const parts = String(label || '').split(/[\s,]+/).map((w) => w.replace(/[^\p{L}\p{N}]/gu, '')).filter(Boolean);
  if (!parts.length) return 'MM';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

export const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/* ---------- API ---------- */

function errorFrom(status, body) {
  let message = '';
  const detail = body && body.detail;
  if (typeof detail === 'string') message = detail;
  else if (Array.isArray(detail) && detail[0] && detail[0].msg) message = detail[0].msg;
  if (!message) message = t('err.server', { status });
  const err = new Error(nice(message));
  err.status = status;
  return err;
}

export async function api(path, options) {
  let res;
  try {
    res = await fetch(path, options);
  } catch (e) {
    if (e && e.name === 'AbortError') throw e;
    const err = new Error(t('err.offline'));
    err.offline = true;
    throw err;
  }
  let body = null;
  try {
    body = await res.json();
  } catch (e) {
    body = null;
  }
  if (!res.ok) throw errorFrom(res.status, body);
  return body;
}

export function tool(customerId, name, args, signal) {
  return api(`/api/customers/${encodeURIComponent(customerId)}/tools/${name}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ arguments: args || {} }),
    signal,
  });
}

export const cust = (id, path = '') => `/api/customers/${encodeURIComponent(id)}${path}`;

/** Read the chat's server-sent events from a POST response. */
export async function streamChat(customerId, message, history, onEvent, signal, image) {
  let res;
  try {
    res = await fetch(cust(customerId, '/chat'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(image ? { message, history, image } : { message, history }),
      signal,
    });
  } catch (e) {
    if (e && e.name === 'AbortError') throw e;
    throw new Error(t('err.offline'));
  }
  if (!res.ok) {
    let body = null;
    try { body = await res.json(); } catch (e) { body = null; }
    throw errorFrom(res.status, body);
  }
  const handle = (block) => {
    for (const line of block.split('\n')) {
      if (!line.startsWith('data:')) continue;
      const payload = line.slice(5).trim();
      if (!payload) continue;
      if (payload === '[DONE]') return true;
      try {
        onEvent(JSON.parse(payload));
      } catch (e) {
        /* skip a malformed event, keep the stream going */
      }
    }
    return false;
  };
  if (!res.body || !res.body.getReader) {
    const text = await res.text();
    text.replace(/\r\n/g, '\n').split('\n\n').some(handle);
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
    let at;
    while ((at = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, at);
      buffer = buffer.slice(at + 2);
      if (handle(block)) return;
    }
  }
  if (buffer.trim()) handle(buffer);
}

/* ---------- hooks ---------- */

const cache = new Map();

function useCached(key, load) {
  const [state, setState] = useState(() => (
    key && cache.has(key)
      ? { data: cache.get(key), error: null, loading: false, stale: false, url: key }
      : { data: null, error: null, loading: Boolean(key), stale: false, url: null }
  ));
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!key) return undefined;
    if (cache.has(key)) {
      setState({ data: cache.get(key), error: null, loading: false, stale: false, url: key });
      return undefined;
    }
    let alive = true;
    setState((s) => ({ ...s, error: null, loading: true, stale: s.data !== null }));
    load().then(
      (data) => {
        cache.set(key, data);
        if (alive) setState({ data, error: null, loading: false, stale: false, url: key });
      },
      (error) => {
        if (alive) setState({ data: null, error, loading: false, stale: false, url: key });
      },
    );
    return () => { alive = false; };
  }, [key, tick]);

  const reload = () => {
    if (key) cache.delete(key);
    setTick((n) => n + 1);
  };
  // A key that is already cached answers in the same render, not one effect later.
  const view = key && state.url !== key && cache.has(key)
    ? { data: cache.get(key), error: null, loading: false, stale: false, url: key }
    : state;
  return { ...view, reload };
}

/**
 * GET a URL. Answers are cached for the visit, so going back to a screen is instant.
 * While a new URL loads, the previous data stays available (stale: true) so the
 * screen can dim instead of jumping.
 */
export function useApi(url) {
  return useCached(url || null, () => api(url));
}

/** The same for a tool call: POST /tools/{name} with arguments. Pass args = null to wait. */
export function useTool(customerId, name, args) {
  const key = customerId && name && args ? `tool:${customerId}:${name}:${JSON.stringify(args)}` : null;
  return useCached(key, () => tool(customerId, name, args));
}

export function useDebounced(value, ms = 250) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setV(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return v;
}

/** Run an async job on demand, keeping the last result while the next one loads. */
export function useJob() {
  const [state, setState] = useState({ data: null, error: null, loading: false });
  const seq = useRef(0);
  const run = (promiseFactory) => {
    const mine = ++seq.current;
    setState((s) => ({ ...s, error: null, loading: true }));
    return Promise.resolve()
      .then(promiseFactory)
      .then(
        (data) => { if (mine === seq.current) setState({ data, error: null, loading: false }); },
        (error) => { if (mine === seq.current) setState({ data: null, error, loading: false }); },
      );
  };
  const reset = () => { seq.current += 1; setState({ data: null, error: null, loading: false }); };
  return { ...state, run, reset };
}

export const reducedMotion = () => Boolean(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
