# Front end

No build step. Plain ES modules, Preact + htm vendored in `vendor/`, hand-written SVG charts.

## Two pages

| URL | File | What it is |
|---|---|---|
| `/` | `index.html` + `stage.css` + `stage.js` | The demo page: a white page with the project name, a language switch, the guided tour, and a realistic phone that shows `/app` in an iframe. On a real phone it sends the visitor straight to `/app`. |
| `/app` | `phone.html` + `app.js` + `ui/*.js` + `styles.css` | The app: a bank-app shell in the style of S-mobiili, with the money trainer built in. Works on its own, full screen, on a phone. |

`/app` accepts `?lang=en|fi|sv`, `?who=CUST00086` and `?embed=1` (inside the demo page's phone: no browser chrome assumptions, splash plays on load).

## Messages between the two pages

`window.postMessage`, same origin, always `{ source: 'mm', type, ... }`.

Demo page to app:

| type | fields | effect |
|---|---|---|
| `goto` | `route`, `highlight?` | Show that screen. If `highlight` names a `data-tour` element, scroll it into view and ring it; `highlight: null` clears the ring. |
| `lang` | `lang` | Switch language. |
| `who` | `id`, `label` | Switch demo customer. |
| `splash` | | Play the launch screen again. |
| `ask` | `text`, `photo?` | Open the chat and send this question. `photo: 'sample'` sends the built-in sample price tag (`img/sample-price-tag.jpg`, a made-up brand) with it; with no text the chat asks "Can I afford this?". `photo: 'bill'` sends the built-in sample bill (`img/sample-bill.jpg`, a made-up company, customer and account); with no text the chat asks "Get this bill ready to pay". |

App to demo page:

| type | fields | when |
|---|---|---|
| `ready` | `route`, `lang`, `who` | Once after load. |
| `route` | `route` | Every time the screen changes. |
| `chrome` | `tone`: `light` or `dark` | When the colour behind the status bar changes. `light` means white status-bar text (over the green launch screen or a green header), `dark` means near-black text. |

In embed mode (`?embed=1`) the app keeps 54px free at the top and 34px at the bottom: the demo page draws the phone's status bar and home indicator there.

## Routes

Host app tabs: `home`, `card`, `bank`, `me`. Host sub-screens: `messages` (message centre), `account`.
Trainer: `trainer` (landing), `plan`, `replay`, `ask`, `find`, `explore`, `loan`, `quiz`.

`plan` (in `ui/plan.js`) is the payday plan: the next salary split into essentials, a buffer for the unexpected, savings and everyday spending (`GET /payday-plan`), with a savings-goal slider, the last pay period next to it and one "Accept the plan" button; under it "The weeks ahead", the balance projected day by day (`GET /outlook`). Accepting is a demo: it is kept in `localStorage` under `money-mentor.payday-plan.<customer id>` as `{ from, to, goal }` for that pay period, and nothing is moved. Inside the app a screen can be opened at one of its sections with `ui.go(route, { focus: '<data-tour name>' })`: the heads-up notice in "Worth a look" opens `plan` at `plan-outlook` this way. `ui/plan.js` also holds the entry card on the trainer, the heads-up notice (written from the notice's `data`, so it reads the same in all three languages) and the chat's cards for `get_payday_plan` and `get_balance_outlook`.

`ui/replay.js` and `ui/quiz.js` are self-contained screens: each carries its own strings (en, fi, sv) and styles, reads the language from `document.documentElement.lang`, and uses only `ui.who.id`, `ui.ask(text)` and `ui.go(route)` from the `UI` context.

The chat's affordability card (`check_affordability` in `ui/chat.js`) ends with a "When it could fit" block whenever the tool's result has `when` with a `route`: from the next payday (`next_pay_period`), or in about N months with one habit changed (`one_habit`). Without a route it shows nothing, and an answer without `when` looks as it always did. Its words are the `ans.when_*` strings; the habit's name comes from `habitName()` in `ui/replay.js`, so the card and the replay screen share one set of names.

The chat's payment draft card (`prepare_payment` in `ui/chat.js`, `PaymentDraft`) is a bill from a photo laid out as a payment form: payee, amount, due date, the account number and the reference number each with the engine's check (`checks_out`, `does_not_check_out`, `missing`), whether the balance covers it, and the basket. The "Confirm the payment" button is there only when the tool's `ready_to_confirm` is true, and pressing it pays nothing: the card shows "Nothing was paid" in the demo's own colour. When a check fails the field is flagged, the card says what to do, and there is no button. Its words are the `pay.*` strings, written from the tool's statuses and not from its English `problems`. The ways in: the sample bill under the sample price tag on the chat's first screen, and "A bill? Get it ready to pay" under a photo attached with the camera button; both send the question `ask.q.bill`.

## Tour anchors (`data-tour`)

`home-trainer` (trainer slide or tile on Home), `bank-trainer` (trainer card on the Bank tab), `assistant-entry` (assistant row in the message centre), `trainer-hero`, `trainer-notices`, `trainer-plan` (the payday card on the trainer landing), `trainer-baskets`, `trainer-quiz`, `plan-split` (the salary split), `plan-accept` (the accept area), `plan-outlook` (the weeks-ahead chart), `replay-chart`, `replay-levers`, `replay-honesty`, `ask-answer`, `ask-trust`, `ask-camera`, `find-bar`, `loan-pillars`.

## Languages

`i18n/en.js`, `i18n/fi.js`, `i18n/sv.js` each export one flat object of strings. `t(key, vars?)` from `ui/lib.js` reads the current language and falls back to English. Numbers and dates are formatted per language (`fi` and `sv`: `1 234,56 €`, `15.10.`; `en`: `€1,234.56`, `15 Oct`).

## Look

Modelled on S-mobiili as recorded on 14 Nov 2026: pale green page (`#EBF7EC`), white cards with a 10px radius and no shadow, green section titles, big green amounts with a smaller euro sign, green outline icons, round dark-green action buttons, square black segmented controls, a white top bar with a back chevron and a centred title, and a white four-tab bar whose active icon is solid green.

Tokens are at the top of `styles.css`. Light theme only, like the real app.

**Type.** The stack asks for the bank's own faces first: `"S Bonus UX", Figtree, system-ui` for text and `"S Bonus Display", "Barlow Condensed"` for the large uppercase headings (the S-Etukortti header, the name on the Me tab). `phone.html` links `/assets/brand/brand.css`, which declares them when `web/brand/` holds the font files; without it the open-licensed stand-ins in `web/fonts` are used. S Bonus UX has only 300, 400, 500 and 700, so the stylesheet uses 400, 500 and 700 and nothing in between.

**Logo.** One component, `BrandMark` in `ui/parts.js`, is used wherever the mark appears (launch screen, S-Etukortti tab and header, card icons). It looks for `/assets/brand/logo.svg` once: if it is there it is drawn as a CSS mask, so it takes the colour around it; if not, a neutral stand-in is drawn (a rounded square with a plain "S"). `Wordmark` shows `logo-wordmark.svg` at the foot of the Me tab, and nothing when the file is missing. The logo is never redrawn by hand. The brand files are not in this repository: see `brand/README.md`.

Every screen carries a small "Demo" mark (top bar, the S-Etukortti header, the launch screen), and nothing asks for credentials. Inert parts of the host app answer with a "Not part of this demo" toast.

`/app?tour=1` runs the walkthrough inside the app for a visitor on a real phone: a caption card docked above the tab bar, driven by the steps and captions in `i18n/tour.js`. While that card is up (`html.in-tour`) the chat hides its composer and suggestion chips, so a long answer and its card have the whole screen above the caption; they are back when the card is closed.

## The walkthrough

`i18n/tour.js` holds the twelve steps (`STEPS`: what the phone shows) and their captions in three languages (`steps`, index-aligned with `STEPS`). Both the demo page (`stage.js`) and the card in the app (`TourCard` in `app.js`) read them.

A step is `{ route, highlight, seconds }`, plus `ask: true` (send that step's own `ask` question) or `photo: true` (send the sample price tag). On the demo page a step stays up for `seconds` and then the tour moves on by itself.

The last step is the closing one: `{ route, highlight, closing: true, icons }` with no `seconds`. A step without `seconds` rests: no timer, no pause button, its bar segment full, and the tour stays there until the visitor moves on. Its caption is a title and a list, `proof: [{ figure?, lead, text }]`, instead of a `text` paragraph. A row with a `figure` shows it; a row without one shows the icon named at the same index in `icons` (`#i-<name>` in the sprite of `index.html`, and the icon of the same name in `ui/parts.js`). The primary button reads `tryIt` and leads to the closing panel as before. On the demo page, if the visitor skipped ahead and the tour has asked nothing yet, the closing step asks the question of the first `ask` step, so the phone shows an answer with its evidence line ringed and not an empty chat.

The two figures on the closing step are measured (`eval/results.md`). If the evaluation is run again, change them in all three languages.
