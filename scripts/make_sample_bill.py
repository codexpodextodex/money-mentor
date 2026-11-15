"""Render a made-up Finnish bill as a photo-like JPEG, for testing how the model reads one.

Everything on it is invented. The IBAN uses a bank code no Finnish bank has (99), with a correct
check number, and the reference number has a correct check digit, so a reader can be checked.
"""

import pathlib
import sys

from playwright.sync_api import sync_playwright

OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).with_name("sample-bill.jpg")


def iban_fi(bban: str) -> str:
    assert len(bban) == 14 and bban.isdigit()
    rearranged = bban + "151800"  # F=15, I=18, "00"
    check = 98 - int(rearranged) % 97
    return f"FI{check:02d}{bban}"


def reference(base: str) -> str:
    weights = (7, 3, 1)
    total = sum(int(d) * weights[i % 3] for i, d in enumerate(reversed(base)))
    return base + str((10 - total % 10) % 10)


def grouped(text: str, size: int = 4, from_right: bool = False) -> str:
    if from_right:
        text = text[::-1]
    parts = [text[i : i + size] for i in range(0, len(text), size)]
    out = " ".join(parts)
    return out[::-1] if from_right else out


IBAN = iban_fi("99999900012344")
REF = reference("202610457")
AMOUNT = "84,60"
DUE = "12.10.2026"
barcode = "4" + IBAN[2:] + "000084" + "60" + "000" + REF.zfill(20) + "261012"

html = f"""<!doctype html><meta charset="utf-8">
<style>
  body {{ margin: 0; background: #6f6a63; font-family: Arial, Helvetica, sans-serif; }}
  .desk {{ width: 1100px; height: 1400px; display: grid; place-items: center;
           background: radial-gradient(circle at 30% 20%, #8a847b, #5d5850); }}
  .paper {{ width: 820px; min-height: 1080px; background: #fbfaf6; color: #1b1b1b; padding: 56px 60px; box-sizing: border-box;
            transform: rotate(-1.6deg); box-shadow: 0 30px 60px rgba(0,0,0,.45), 0 2px 4px rgba(0,0,0,.3); }}
  h1 {{ font-size: 40px; margin: 0; letter-spacing: 1px; }}
  .top {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 3px solid #1b1b1b; padding-bottom: 18px; }}
  .brand {{ font-size: 28px; font-weight: 700; }} .brand small {{ display: block; font-size: 14px; font-weight: 400; color: #555; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 26px; font-size: 18px; }}
  td {{ padding: 9px 0; vertical-align: top; }} td.k {{ color: #555; width: 44%; }}
  .lines td {{ border-bottom: 1px solid #d8d5cc; }} .lines td:last-child {{ text-align: right; }}
  .pay {{ margin-top: 34px; border: 2px solid #1b1b1b; padding: 20px 22px; }}
  .pay h2 {{ margin: 0 0 8px; font-size: 20px; letter-spacing: 1px; }}
  .pay td {{ font-size: 21px; padding: 7px 0; }} .pay td.v {{ font-weight: 700; font-family: "Courier New", monospace; font-size: 23px; }}
  .sum td.v {{ font-size: 30px; }}
  .barcode {{ margin-top: 26px; font-family: "Courier New", monospace; font-size: 15px; color: #333; word-break: break-all; }}
  .fine {{ margin-top: 22px; font-size: 13px; color: #666; }}
</style>
<div class="desk"><div class="paper">
  <div class="top">
    <div class="brand">Demo Sähkö Oy<small>Esimerkkikatu 1, 00100 Helsinki · Y-tunnus 0000000-0</small></div>
    <h1>LASKU</h1>
  </div>
  <table>
    <tr><td class="k">Asiakas</td><td>Demo Asiakas<br>Mallitie 2 A 3, 02100 Espoo</td></tr>
    <tr><td class="k">Laskun numero</td><td>2026-104573</td></tr>
    <tr><td class="k">Laskun päivämäärä</td><td>28.9.2026</td></tr>
    <tr><td class="k">Laskutuskausi</td><td>1.8.2026 – 31.8.2026</td></tr>
  </table>
  <table class="lines">
    <tr><td>Sähköenergia 412 kWh</td><td>41,20 €</td></tr>
    <tr><td>Sähkön siirto</td><td>31,90 €</td></tr>
    <tr><td>Perusmaksu</td><td>4,90 €</td></tr>
    <tr><td>Sähkövero ja ALV sisältyvät hintoihin</td><td>6,60 €</td></tr>
  </table>
  <div class="pay">
    <h2>MAKSUTIEDOT</h2>
    <table>
      <tr><td class="k">Saaja</td><td class="v">Demo Sähkö Oy</td></tr>
      <tr><td class="k">Saajan tilinumero (IBAN)</td><td class="v">{grouped(IBAN)}</td></tr>
      <tr><td class="k">Viitenumero</td><td class="v">{grouped(REF, 5, from_right=True)}</td></tr>
      <tr><td class="k">Eräpäivä</td><td class="v">{DUE}</td></tr>
      <tr class="sum"><td class="k">Maksettava yhteensä</td><td class="v">{AMOUNT} €</td></tr>
    </table>
  </div>
  <div class="barcode">Virtuaaliviivakoodi<br>{barcode}</div>
  <div class="fine">Esimerkkilasku demoa varten. Yritys, asiakas ja tili ovat keksittyjä.</div>
</div></div>"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1100, "height": 1400})
    page.set_content(html)
    page.screenshot(path=str(OUT), type="jpeg", quality=82)
    browser.close()
print(OUT, "| IBAN", IBAN, "| reference", REF, "| amount", AMOUNT, "| due", DUE)
