# Brand assets (not in the repository)

Everything in this folder except this file is ignored by git. It holds S-Pankki's logo and typefaces, which belong to the bank. The team uses them with the bank's permission for the Junction 2026 challenge; they are not ours to publish under the project's MIT licence.

Without these files the app still works: it shows a neutral mark and open-licensed fonts (Figtree, Barlow Condensed and Inter, in `web/fonts`).

| File | Used for |
|---|---|
| `logo.svg` | The S mark alone, square. The app uses it as a mask, so it takes the colour around it: white on the launch screen, green in the tab bar. |
| `logo-white.svg` | The same mark in white. |
| `logo-tight.svg` | The same mark with no space around it, for use next to text. |
| `logo-wordmark.svg` | The full logo (mark and "PANKKI"), green. The demo page header. |
| `logo-wordmark-white.svg` | The full logo in white, for green backgrounds. |
| `brand.css` | `@font-face` rules for `S Bonus UX` (300, 400, 500, 700) and `S Bonus Display` (600, 700). |
| `SBonusUX-*.woff2`, `SBonusDisplay-*.woff2` | The font files. |
| `s-pankki-logo-107x46.svg` | The logo file as downloaded, untouched. |

## Where they came from

Downloaded on 14 Nov 2026 from `www.s-pankki.fi`:

- `/Assets/img/logos/s-pankki-logo-107x46.svg`
- `/Assets/fonts/SBonusUX-Light.woff2`, `-Regular`, `-Medium`, `-Bold`
- `/Assets/fonts/SBonusDisplay-SemiBold.woff2`, `-Bold`

The mark-only and white files are made from the downloaded logo: same path, different frame or fill.

## Setting up another machine

Copy this folder from a teammate. A fresh clone has only this file, and the app falls back to the stand-ins until the rest is copied in.
