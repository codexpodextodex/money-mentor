// Choosing who you are: eight demo customers, or any customer id.
import { html, useState, useApi, api, cust, eur, initials, t, has, getLang, useLang } from './lib.js';
import { Icon, Skeleton, ErrorBox } from './parts.js';

const local = (p, field) => {
  const key = `persona.${p.customer_id}.${field}`;
  return getLang() !== 'en' && has(key) ? t(key) : p[field];
};

function PersonaList({ current, onPick }) {
  const req = useApi('/api/personas');
  if (req.error && !req.data) return html`<${ErrorBox} title=${t('picker.error')} error=${req.error} onRetry=${req.reload} />`;
  if (!req.data) return html`<${Skeleton} rows=${6} />`;
  const list = Array.isArray(req.data) ? req.data : [];
  if (!list.length) return html`<p class="muted">${t('picker.none')}</p>`;
  return html`<ul class="personas">
    ${list.map((p) => {
      const active = current && current.id === p.customer_id;
      const label = local(p, 'label');
      const meta = [p.age ? t('picker.age', { age: p.age }) : null, p.area, p.monthly_income ? t('unit.per_month', { amount: eur(p.monthly_income, 'whole') }) : null].filter(Boolean).join(' · ');
      return html`<li key=${p.customer_id}>
        <button type="button" class=${'persona' + (active ? ' is-active' : '')} aria-pressed=${active ? 'true' : 'false'}
          onClick=${() => onPick({ id: p.customer_id, label: p.label, blurb: p.blurb })}>
          <span class="avatar avatar--lg" aria-hidden="true">${initials(label)}</span>
          <span class="persona__text">
            <strong>${label}</strong>
            <span>${local(p, 'blurb')}</span>
            <small>${meta}</small>
          </span>
          ${active ? html`<span class="persona__on"><${Icon} name="check" size=${20} /></span>` : html`<${Icon} name="right" size=${20} />`}
        </button>
      </li>`;
    })}
  </ul>`;
}

function IdForm({ onPick }) {
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    if (busy) return;
    let id = value.trim().toUpperCase().replace(/\s+/g, '');
    if (/^\d{1,5}$/.test(id)) id = 'CUST' + id.padStart(5, '0');
    if (!/^CUST\d{5}$/.test(id)) {
      setError(t('picker.bad_id'));
      return;
    }
    setBusy(true);
    setError('');
    try {
      const o = await api(cust(id, '/overview'));
      const c = (o && o.customer) || {};
      onPick({
        id: c.customer_id || id,
        label: null,
        blurb: [c.age ? t('picker.age', { age: c.age }) : null, c.area].filter(Boolean).join(' · '),
      });
    } catch (err) {
      setError(err.message || t('picker.open_error'));
    } finally {
      setBusy(false);
    }
  };

  return html`<form class="idform" onSubmit=${submit} novalidate>
    <label for="cust-id">${t('picker.id_label')}</label>
    <div class="idform__row">
      <input id="cust-id" type="text" inputmode="text" autocapitalize="characters" autocorrect="off" autocomplete="off"
        spellcheck=${false} enterkeyhint="go" placeholder="CUST00874" maxlength="9" value=${value}
        aria-describedby="cust-id-help" aria-invalid=${error ? 'true' : 'false'}
        onInput=${(e) => { setValue(e.target.value); if (error) setError(''); }} />
      <button type="submit" class="btn btn--primary" disabled=${busy || !value.trim()}>${busy ? t('picker.opening') : t('picker.open')}</button>
    </div>
    <p id="cust-id-help" class=${error ? 'idform__error' : 'idform__help'} role=${error ? 'alert' : undefined}>
      ${error || t('picker.id_help')}
    </p>
  </form>`;
}

export function SyntheticNote() {
  return html`<p class="synthetic"><${Icon} name="shield" size=${20} />
    <span><strong>${t('picker.demo_data')}</strong> ${t('picker.demo_text')}</span></p>`;
}

/** Inside the bottom sheet, from the Me tab. */
export function SwitchBody({ current, onPick }) {
  useLang();
  return html`<div class="switch">
    <${PersonaList} current=${current} onPick=${onPick} />
    <${IdForm} onPick=${onPick} />
    <${SyntheticNote} />
  </div>`;
}
