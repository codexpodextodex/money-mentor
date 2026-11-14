// The app shell: a bank app in the style of S-mobiili, with the money trainer built in.
// Four tabs, stack navigation for sub-pages, the launch screen, and the messages
// that let the demo page drive it (see README.md).
import {
  html, render, useState, useEffect, useRef, useErrorBoundary, useApi, store,
  t, initLang, setLang, getLang, onLang, Lang, reducedMotion,
} from './ui/lib.js';
import { UI, Icon, SolidIcon, BrandMark, Sheet, ErrorBox, probeLogo } from './ui/parts.js';
import { SwitchBody } from './ui/picker.js';
import { HomeTab, CardTab, BankTab, MeTab, Messages, Account, AboutBody, LanguageBody, whoName } from './ui/host.js';
import { Trainer } from './ui/trainer.js';
import { Chat } from './ui/chat.js';
import { Find } from './ui/find.js';
import { Explore } from './ui/explore.js';
import { Loan } from './ui/loan.js';
import { Replay } from './ui/replay.js';
import { BasketQuiz } from './ui/quiz.js';
import { Plan } from './ui/plan.js';

const params = new URLSearchParams(window.location.search);
const EMBED = params.get('embed') === '1';
const TOUR = params.get('tour') === '1';
const WHO_KEY = 'money-mentor.customer';
const DEFAULT_WHO = { id: 'CUST00086', label: 'Month-end stretcher', blurb: 'Balance dips below zero most months' };
const ID = /^CUST\d{5}$/;

/* ---------- routes ---------- */

const Wrapped = (View) => () => html`<div class="stack"><${View} /></div>`;

// title: a dictionary key, or text as it is. parent: where the back chevron leads.
const ROUTES = {
  home: { tab: true, view: HomeTab, label: 'tab.home' },
  card: { tab: true, view: CardTab, label: 'tab.card' },
  bank: { tab: true, view: BankTab, label: 'tab.bank', title: 'bank.title' },
  me: { tab: true, view: MeTab, label: 'tab.me' },
  messages: { view: Messages, title: 'messages.title' },
  account: { view: Account, text: 'S-Tili' },
  trainer: { view: Trainer, title: 'trainer.title' },
  plan: { view: Plan, title: 'plan.title', parent: 'trainer' },
  replay: { view: Wrapped(Replay), title: 'replay.title', parent: 'trainer' },
  ask: { view: Chat, title: 'ask.title', parent: 'trainer', fixed: true },
  find: { view: Find, title: 'find.title', parent: 'trainer' },
  explore: { view: Explore, title: 'explore.title', parent: 'trainer' },
  loan: { view: Loan, title: 'loan.title', parent: 'trainer' },
  quiz: { view: Wrapped(BasketQuiz), title: 'quiz.title', parent: 'trainer' },
};
const TABS = ['home', 'card', 'bank', 'me'];
const titleOf = (route) => {
  const r = ROUTES[route] || {};
  return r.text || (r.title ? t(r.title) : r.label ? t(r.label) : '');
};

/* ---------- talking to the demo page ---------- */

function post(message) {
  if (window.parent && window.parent !== window) {
    window.parent.postMessage({ source: 'mm', ...message }, window.location.origin);
  }
}

function readWho() {
  const fromUrl = (params.get('who') || '').toUpperCase();
  if (ID.test(fromUrl)) {
    const saved = store.get(WHO_KEY);
    return saved && saved.id === fromUrl ? saved : { id: fromUrl, label: fromUrl === DEFAULT_WHO.id ? DEFAULT_WHO.label : null };
  }
  const saved = store.get(WHO_KEY);
  return saved && typeof saved.id === 'string' && ID.test(saved.id) ? saved : DEFAULT_WHO;
}

/* ---------- pieces of the shell ---------- */

function Boundary({ children }) {
  const [error, reset] = useErrorBoundary();
  if (error) {
    return html`<div class="stack"><${ErrorBox} title=${t('state.screen_error')} error=${error} onRetry=${reset} /></div>`;
  }
  return children;
}

function MessageIcon() {
  return html`<svg class="ico" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.600"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <path d="M15.200 5H5.500a1 1 0 0 0-1 1v13.200l4-3.200h9a1 1 0 0 0 1-1V8.300" />
    <circle cx="19" cy="4.800" r="1.700" fill="currentColor" stroke="none" />
  </svg>`;
}

/** The launch screen: bright green, the mark drawing itself in, then a cross-fade to the app. */
function Splash({ state }) {
  if (!state) return null;
  return html`<div class=${'splash' + (state.phase === 'out' ? ' is-out' : '')} key=${state.n} role="img" aria-label=${t('splash.aria')}>
    <div class="splash__mark"><${BrandMark} size=${188} draw=${true} /></div>
    <p class="splash__note">${t('splash.note')}</p>
  </div>`;
}

function Toast({ toast }) {
  const [shown, setShown] = useState(null);
  const [on, setOn] = useState(false);
  useEffect(() => {
    if (!toast) { setOn(false); return undefined; }
    setShown(toast);
    const frame = requestAnimationFrame(() => setOn(true));
    return () => cancelAnimationFrame(frame);
  }, [toast]);
  return html`<div class=${'toast' + (on ? ' is-on' : '')} role="status" aria-live="polite">
    ${shown ? html`<span><${Icon} name="info" size=${18} />${shown.text}</span>` : null}
  </div>`;
}

/** The tour's highlight: a green ring that follows one data-tour element, the rest slightly dimmed. */
function Ring({ target }) {
  const box = useRef(null);
  const name = target ? target.name : null;
  const n = target ? target.n : 0;
  useEffect(() => {
    const el = box.current;
    if (!el) return undefined;
    if (!name) { el.classList.remove('is-on'); return undefined; }
    const app = el.parentElement;
    const safe = window.CSS && CSS.escape ? CSS.escape(name) : name.replace(/[^\w-]/g, '');
    const find = () => app.querySelector(`.screen.is-active [data-tour="${safe}"]`)
      || app.querySelector(`.topbar [data-tour="${safe}"], .tabs [data-tour="${safe}"]`);
    let frame = 0;
    let found = null;
    let foundAt = 0;
    let lastScroll = 0;
    let touched = false;
    let last = '';
    const touch = () => { touched = true; };
    app.addEventListener('pointerdown', touch, { passive: true });
    app.addEventListener('wheel', touch, { passive: true });
    // The part of the app a target can show in: its own scroller, never the bars around it.
    const frameOf = (node) => node.closest('.chat__scroll, .sheet__body, .screen') || app;
    let lastFrame = 0;
    let drawn = true;
    const bring = (now) => {
      lastScroll = now;
      const room = frameOf(found).getBoundingClientRect().height;
      const tall = found.getBoundingClientRect().height > room - 32;
      // No frames are being drawn (a background tab): a smooth scroll would never finish.
      found.scrollIntoView({ block: tall ? 'start' : 'center', inline: 'nearest', behavior: reducedMotion() || !drawn ? 'auto' : 'smooth' });
    };
    const loop = (now) => {
      frame = requestAnimationFrame(loop);
      lastFrame = now;
      drawn = true;
      tick(now);
    };
    const tick = (now) => {
      // The name can move to another element (the newest answer in the chat): follow it.
      if (!found || !found.isConnected || found.getAttribute('data-tour') !== name || !found.closest('.screen.is-active, .topbar, .tabs')) {
        found = find();
        if (found) { foundAt = now; touched = false; bring(now); }
      }
      if (!found) { el.classList.remove('is-on'); last = ''; return; }
      const a = app.getBoundingClientRect();
      const r = found.getBoundingClientRect();
      if (!r.width && !r.height) { el.classList.remove('is-on'); return; }
      const f = frameOf(found).getBoundingClientRect();
      // Content that loads above the target pushes it away: bring it back while things settle.
      if (!touched && now - foundAt < 3200 && now - lastScroll > 520) {
        const fits = r.height <= f.height - 32;
        if (fits ? (r.top < f.top + 8 || r.bottom > f.bottom - 8) : (r.top > f.top + f.height * 0.4 || r.bottom < f.top + 80)) bring(now);
      }
      // Draw only the part that shows inside its scroller, so the ring never crosses the composer or the bars.
      const pad = 5;
      const inset = found.closest('.screen') ? 3 : -pad;
      const x0 = Math.max(r.left - pad, f.left + Math.max(inset, 0));
      const x1 = Math.min(r.right + pad, f.right - Math.max(inset, 0));
      const y0 = Math.max(r.top - pad, f.top + inset);
      const y1 = Math.min(r.bottom + pad, f.bottom - inset);
      if (y1 - y0 < 24 || x1 - x0 < 24) { el.classList.remove('is-on'); return; }
      const next = `${Math.round(x0 - a.left)},${Math.round(y0 - a.top)},${Math.round(x1 - x0)},${Math.round(y1 - y0)}`;
      if (next !== last) {
        last = next;
        const [x, y, w, h] = next.split(',');
        el.style.transform = `translate(${x}px, ${y}px)`;
        el.style.width = `${w}px`;
        el.style.height = `${h}px`;
      }
      el.classList.add('is-on');
    };
    frame = requestAnimationFrame(loop);
    // Animation frames stop in a background tab; a slow timer keeps the ring's state true there.
    const idle = setInterval(() => {
      const now = performance.now();
      if (now - lastFrame > 400) { drawn = false; tick(now); }
    }, 300);
    return () => {
      cancelAnimationFrame(frame);
      clearInterval(idle);
      app.removeEventListener('pointerdown', touch);
      app.removeEventListener('wheel', touch);
    };
  }, [name, n]);
  return html`<div class="ring" ref=${box} aria-hidden="true"></div>`;
}

/**
 * The walkthrough for a visitor on a real phone (/app?tour=1): the demo page's own steps and
 * captions (i18n/tour.js), in a card docked above the tab bar. Next and Back drive the app.
 */
function TourCard({ data, lang, at, onStep, onClose }) {
  const words = (data.tour && (data.tour[lang] || data.tour.en)) || {};
  const steps = Array.isArray(words.steps) ? words.steps : [];
  const total = Math.min(steps.length, data.STEPS.length);
  const step = steps[at] || {};
  const last = at >= total - 1;
  const fill = (text, vars) => String(text || '').replace(/\{(\w+)\}/g, (m, k) => (vars[k] !== undefined ? vars[k] : m));
  return html`<aside class="tourcard" aria-label=${words.walkthrough || 'Walkthrough'}>
    <span class="tourcard__bar" aria-hidden="true"><i style=${`transform:scaleX(${(at + 1) / Math.max(total, 1)})`}></i></span>
    <div class="tourcard__top">
      <span class="tourcard__count">${words.walkthrough || 'Walkthrough'} · ${fill(words.of || '{n} / {total}', { n: at + 1, total })}</span>
      <button type="button" class="tourcard__close" aria-label=${t('common.close')} onClick=${onClose}><${Icon} name="close" size=${20} /></button>
    </div>
    <div class="tourcard__body" aria-live="polite" key=${at}>
      <h2>${step.title}</h2>
      <p>${step.text}</p>
    </div>
    <div class="tourcard__nav">
      <button type="button" class="btn btn--small" disabled=${at === 0} onClick=${() => onStep(at - 1)}><${Icon} name="back" size=${18} />${words.back || t('common.back')}</button>
      ${last
        ? html`<button type="button" class="btn btn--primary" onClick=${onClose}>${words.finish || 'Finish'}<${Icon} name="check" size=${18} /></button>`
        : html`<button type="button" class="btn btn--primary" onClick=${() => onStep(at + 1)}>${words.next || 'Next'}<${Icon} name="right" size=${18} /></button>`}
    </div>
  </aside>`;
}

/* ---------- the app ---------- */

function App() {
  const [lang, setLangState] = useState(getLang);
  const [who, setWho] = useState(readWho);
  const [nav, setNav] = useState({ stack: ['home'], from: null, dir: null, n: 0 });
  const [visited, setVisited] = useState({ home: true });
  const [sheet, setSheet] = useState(null);
  const [question, setQuestion] = useState(null);
  const [preset, setPreset] = useState(null);
  const [focus, setFocus] = useState(null);
  const [toast, setToast] = useState(null);
  const [ring, setRing] = useState(null);
  const [splash, setSplash] = useState(EMBED ? { n: 1, phase: 'in' } : null);
  const [tourData, setTourData] = useState(null);
  const [tourAt, setTourAt] = useState(TOUR ? 0 : null);
  const asked = useRef({});
  const counter = useRef(1);
  const timers = useRef({ nav: 0, toast: 0, splash: [] });
  const live = useRef({});
  const health = useApi('/api/health');
  const personas = useApi('/api/personas');

  const route = nav.stack[nav.stack.length - 1];
  const tab = nav.stack[0];

  /* --- navigation --- */

  const move = (stack, how) => {
    const top = stack[stack.length - 1];
    setVisited((v) => (v[top] ? v : { ...v, [top]: true }));
    setSheet(null);
    setNav((cur) => {
      const was = cur.stack[cur.stack.length - 1];
      if (was === top && cur.stack.length === stack.length) return { ...cur, stack };
      let dir = how || null;
      if (!how) {
        const grows = stack.length > cur.stack.length && cur.stack.every((r, i) => stack[i] === r);
        const shrinks = stack.length < cur.stack.length && stack.every((r, i) => cur.stack[i] === r);
        dir = grows ? 'push' : shrinks ? 'pop' : null;
      }
      return { stack, from: dir ? was : null, dir, n: cur.n + 1 };
    });
  };

  // Follow a link inside the app: a tab resets the stack, anything else goes on top.
  const go = (id, extra) => {
    if (!ROUTES[id]) return;
    if (id === 'loan' && extra) setPreset({ ...extra, n: ++counter.current });
    // Open a screen at one of its sections: { focus: 'plan-outlook' } names a data-tour element.
    if (extra && typeof extra.focus === 'string') setFocus({ route: id, name: extra.focus, n: ++counter.current });
    setRing(null);
    const { stack } = live.current.nav;
    if (ROUTES[id].tab) { move([id]); return; }
    const at = stack.indexOf(id);
    move(at >= 0 ? stack.slice(0, at + 1) : [...stack, id]);
  };
  const back = () => {
    const { stack } = live.current.nav;
    setRing(null);
    if (stack.length > 1) move(stack.slice(0, -1));
  };
  // Land on a screen from outside (the tour): rebuild the path that leads to it.
  const jump = (id) => {
    if (!ROUTES[id]) return;
    const { stack } = live.current.nav;
    if (ROUTES[id].tab) { move([id]); return; }
    if (stack[stack.length - 1] === id) return;
    const path = [id];
    while (ROUTES[path[0]].parent) path.unshift(ROUTES[path[0]].parent);
    const trainerSide = path[0] === 'trainer';
    const root = trainerSide && (stack[0] === 'card' || stack[0] === 'me') ? 'bank' : stack[0];
    move([root, ...path]);
  };
  const ask = (text, fromOutside, photo) => {
    const q = String(text || '').trim();
    // photo: 'sample' sends the built-in price-tag photo along (the tour uses it to show photo reading).
    if (q || photo) setQuestion({ text: q, photo: photo || null, n: ++counter.current });
    if (fromOutside) jump('ask'); else go('ask');
  };
  const demo = (text) => {
    clearTimeout(timers.current.toast);
    setToast({ text: typeof text === 'string' && text ? text : t('common.not_in_demo'), n: ++counter.current });
    timers.current.toast = setTimeout(() => setToast(null), 2200);
  };

  /* --- customer, language, launch screen --- */

  const choose = (next, stay) => {
    if (!next || !ID.test(String(next.id || ''))) return;
    const person = { id: next.id, label: next.label || null, blurb: next.blurb || null };
    store.set(WHO_KEY, person);
    setSheet(null);
    setQuestion(null);
    setPreset(null);
    setFocus(null);
    setRing(null);
    if (stay) {
      const { stack } = live.current.nav;
      setVisited({ [stack[stack.length - 1]]: true });
    } else {
      post({ type: 'who', id: person.id, label: person.label || whoName(person) });
      setVisited({ home: true });
      setNav((cur) => ({ stack: ['home'], from: null, dir: null, n: cur.n + 1 }));
    }
    setWho(person);
  };
  const changeLang = (next) => { setLang(next); };
  const playSplash = () => {
    timers.current.splash.forEach(clearTimeout);
    const n = ++counter.current;
    setSplash({ n, phase: 'in' });
    timers.current.splash = [
      setTimeout(() => setSplash({ n, phase: 'out' }), 1300),
      setTimeout(() => setSplash((s) => (s && s.n === n ? null : s)), 1300 + 360),
    ];
  };

  live.current = { nav, who, lang, jump, ask, choose, changeLang, playSplash, setRing, go, back };

  // The walkthrough on a phone: load the page's steps, then let each step place the app.
  useEffect(() => {
    if (!TOUR) return;
    import('./i18n/tour.js').then(
      (m) => { if (Array.isArray(m.STEPS) && m.STEPS.length) setTourData({ STEPS: m.STEPS, tour: m.tour || m.default || {} }); else setTourAt(null); },
      () => { setTourAt(null); live.current.jump('trainer'); },
    );
  }, []);
  useEffect(() => {
    if (tourAt === null || !tourData) return;
    const step = tourData.STEPS[tourAt];
    if (!step) return;
    const now = live.current;
    const words = tourData.tour[now.lang] || tourData.tour.en || {};
    const text = step.ask && words.steps && words.steps[tourAt] ? words.steps[tourAt].ask : null;
    if (text && !asked.current[tourAt]) {
      asked.current[tourAt] = true;
      now.ask(text, true);
    } else if (step.photo && !asked.current[tourAt]) {
      asked.current[tourAt] = true;
      now.ask('', true, 'sample');
    } else {
      now.jump(step.route);
    }
    setRing(step.highlight ? { name: step.highlight, n: ++counter.current } : null);
  }, [tourAt, tourData]);
  const endTour = () => { setTourAt(null); setRing(null); };

  // The slide lasts 220ms; after it the screen that was left goes back to rest.
  useEffect(() => {
    if (!nav.from) return undefined;
    const timer = setTimeout(() => setNav((cur) => (cur.n === nav.n ? { ...cur, from: null, dir: null } : cur)), 260);
    return () => clearTimeout(timer);
  }, [nav.n]);

  // A screen that is opened starts at its top (the chat keeps its own place).
  useEffect(() => {
    if (nav.dir !== 'push' || ROUTES[route].fixed) return;
    const el = document.getElementById('scr-' + route);
    if (el) el.scrollTop = 0;
  }, [nav.n]);

  // Language: keep <html lang> and the tree in step.
  useEffect(() => onLang((next) => { setSheet(null); setLangState(next); }), []);

  // The demo customer's name comes from the list of personas when the page was opened by id.
  useEffect(() => {
    if ((who.label && who.blurb) || !Array.isArray(personas.data)) return;
    const p = personas.data.find((x) => x.customer_id === who.id);
    if (p) setWho((w) => (w.id === p.customer_id ? { ...w, label: w.label || p.label, blurb: w.blurb || p.blurb } : w));
  }, [personas.data, who.id]);

  // Messages from the demo page. Same origin and our own envelope only.
  useEffect(() => {
    const onMessage = (e) => {
      if (e.origin !== window.location.origin) return;
      const m = e.data;
      if (!m || typeof m !== 'object' || m.source !== 'mm' || typeof m.type !== 'string') return;
      const now = live.current;
      if (m.type === 'goto') {
        if (typeof m.route === 'string' && ROUTES[m.route]) now.jump(m.route);
        now.setRing(typeof m.highlight === 'string' && m.highlight ? { name: m.highlight, n: ++counter.current } : null);
      } else if (m.type === 'lang') {
        now.changeLang(m.lang);
      } else if (m.type === 'who') {
        if (m.id !== now.who.id) now.choose({ id: String(m.id || '').toUpperCase(), label: m.label }, true);
      } else if (m.type === 'splash') {
        now.setRing(null);
        now.jump('home');
        now.playSplash();
      } else if (m.type === 'ask') {
        // The ring, if any, stays: it shows again as soon as its element is on the chat screen.
        now.ask(typeof m.text === 'string' ? m.text : '', true, m.photo === 'sample' ? 'sample' : null);
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);

  // First load: the launch screen (inside the demo phone), then "ready".
  useEffect(() => {
    probeLogo();
    if (EMBED) {
      timers.current.splash = [
        setTimeout(() => setSplash((s) => (s ? { ...s, phase: 'out' } : s)), 1300),
        setTimeout(() => setSplash(null), 1300 + 360),
      ];
    }
    post({ type: 'ready', route, lang: getLang(), who: who.id, label: who.label || null });
    return () => {
      timers.current.splash.forEach(clearTimeout);
      clearTimeout(timers.current.toast);
    };
  }, []);

  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    post({ type: 'route', route });
  }, [route]);

  // The colour behind the status bar: green under the launch screen and the S-Etukortti header.
  const green = Boolean(splash && splash.phase === 'in') || route === 'card';
  useEffect(() => { post({ type: 'chrome', tone: green ? 'light' : 'dark' }); }, [green]);
  useEffect(() => {
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', splash && splash.phase === 'in' ? '#0fc348' : route === 'card' ? '#0a8942' : '#ffffff');
  }, [green, route]);

  useEffect(() => {
    document.title = `${titleOf(route) || 'S-mobiili'} · Money Mentor demo`;
  }, [route, lang]);

  /* --- sheets --- */

  const openSwitch = () => setSheet({
    title: t('me.switch'),
    body: html`<${SwitchBody} current=${who} onPick=${(p) => choose(p)} />`,
  });
  const openLanguage = () => setSheet({
    title: t('me.language'),
    body: html`<${LanguageBody} onPick=${(l) => { changeLang(l); setSheet(null); }} />`,
  });
  const openAbout = () => setSheet({ title: t('me.about'), body: html`<${AboutBody} />` });

  const ui = {
    who,
    today: health.data && health.data.today,
    health: health.data,
    question,
    preset,
    focus,
    lang,
    route,
    embed: EMBED,
    go,
    back,
    ask,
    demo,
    openSheet: setSheet,
    closeSheet: () => setSheet(null),
    openSwitch,
    openLanguage,
    openAbout,
  };

  const deep = nav.stack.length > 1;
  const title = route === 'home' || route === 'me' ? '' : titleOf(route);
  const screens = Object.keys(ROUTES).filter((id) => visited[id] || id === route || id === nav.from);

  return html`<${Lang.Provider} value=${lang}><${UI.Provider} value=${ui}>
    ${route === 'card' ? null : html`<header class="topbar">
      <div class="topbar__side">
        ${deep
          ? html`<button type="button" class="topbar__btn" aria-label=${t('common.back')} onClick=${back}><${Icon} name="back" size=${26} /></button>`
          : route === 'home'
            ? html`<button type="button" class="topbar__btn" aria-label=${t('home.logout')} onClick=${() => demo()}><${Icon} name="logout" size=${26} /></button>`
            : null}
      </div>
      <h1 class=${'topbar__title' + (title ? '' : ' sr')}>${title || whoName(who)}</h1>
      <div class="topbar__side topbar__side--end">
        <span class="demo" title=${t('demo.title')}>${t('common.demo')}</span>
        ${route === 'messages' ? null : html`<button type="button" class="topbar__btn" aria-label=${t('messages.title')} onClick=${() => go('messages')}><${MessageIcon} /></button>`}
      </div>
    </header>`}

    <main class="screens" key=${who.id}>
      ${screens.map((id) => {
        const r = ROUTES[id];
        const active = id === route;
        const leaving = id === nav.from && !active;
        const cls = 'screen screen--' + id + (r.fixed ? ' screen--fixed' : '')
          + (active ? ' is-active' + (nav.from && nav.dir ? ' in-' + nav.dir : '') : '')
          + (leaving ? ' is-leaving out-' + nav.dir : '');
        return html`<section key=${id} id=${'scr-' + id} class=${cls} aria-label=${titleOf(id)} aria-hidden=${active ? 'false' : 'true'}>
          <${Boundary}><${r.view} /><//>
        </section>`;
      })}
    </main>

    ${tourAt !== null && tourData ? html`<${TourCard} data=${tourData} lang=${lang} at=${tourAt} onStep=${setTourAt} onClose=${endTour} />` : null}

    <nav class="tabs" aria-label=${t('tab.aria')}>
      ${TABS.map((id) => {
        const on = tab === id;
        return html`<button key=${id} type="button" class=${'tab' + (on ? ' is-active' : '')} aria-current=${on ? 'page' : undefined} onClick=${() => go(id)}>
          <span class="tab__icon">
            ${id === 'card' ? html`<${BrandMark} size=${26} />`
              : on ? html`<${SolidIcon} name=${id === 'bank' ? 'wallet' : id === 'me' ? 'person' : 'home'} size=${27} />`
                : html`<${Icon} name=${id === 'bank' ? 'wallet' : id === 'me' ? 'person' : 'home'} size=${27} stroke=${1.400} />`}
          </span>
          <span class="tab__label">${t(ROUTES[id].label)}</span>
        </button>`;
      })}
    </nav>

    <${Sheet} sheet=${sheet} onClose=${() => setSheet(null)} />
    <${Toast} toast=${toast} />
    <${Ring} target=${ring} />
    <${Splash} state=${splash} />
  <//><//>`;
}

initLang();
if (EMBED) document.documentElement.classList.add('embed');
const root = document.getElementById('app');
root.textContent = '';
render(html`<${App} />`, root);
