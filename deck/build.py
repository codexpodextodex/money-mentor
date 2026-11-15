"""Money Mentor pitch deck: build deck/out/money-mentor-deck.pdf and slide-01.png to slide-14.png.

    python deck/build.py             # build; photographs the app's screens first if deck/screens/ is empty
    python deck/build.py --capture   # photograph every screen again from the running app, then build

What it does, in order:
  1. Refuses to go on without the bank's typefaces and logo in web/brand/ (no stand-in fonts).
  2. Photographs the app's screens (deck/capture.py) when they are missing or --capture is given.
     The demo app must then be running on http://127.0.0.1:8791.
  3. Writes the QR code (reportlab's encoder) and the phone's soft shadow (Pillow) to deck/out/.
  4. Serves deck/ on 127.0.0.1 with web/ at /assets/ (fonts, logo, the sample photo) and video/ at
     /film/ (the film's phone, device.js). Nothing is copied.
  5. Opens deck.html in headless Chromium, checks fonts, images and layout, and prints the PDF.
  6. Opens the PDF with PyMuPDF: 14 pages, 16:9, every word set in the bank's typefaces, the two
     links, the QR modules; and rasterises each page to 1920 x 1080.

It installs nothing and downloads nothing: system Python with Playwright (Chromium), Pillow,
PyMuPDF and reportlab.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WEB = ROOT / "web"
FILM = ROOT / "video"
OUT = HERE / "out"
SCREENS = HERE / "screens"
PDF = OUT / "money-mentor-deck.pdf"
PORT = 8793
URL = "https://95-216-229-240.sslip.io"
PAGES = 14
W, H = 1920, 1080
BRAND = ["brand.css", "logo-wordmark.svg", "logo-wordmark-white.svg", "SBonusDisplay-Bold.woff2",
         "SBonusUX-Regular.woff2", "SBonusUX-Medium.woff2", "SBonusUX-Bold.woff2"]
CHROME_ARGS = ["--disable-lcd-text", "--font-render-hinting=none", "--force-color-profile=srgb", "--hide-scrollbars"]

sys.path.insert(0, str(HERE))


# ---------- a small read-only file server ----------

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        rel = unquote(urlsplit(path).path).lstrip("/")
        root = HERE
        if rel.startswith("assets/"):
            root, rel = WEB, rel[len("assets/"):]
        elif rel.startswith("film/"):
            root, rel = FILM, rel[len("film/"):]
        target = (root / rel).resolve()
        if root.resolve() not in target.parents and target != root.resolve():
            return str(HERE / "__nothing__")
        return str(target)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args) -> None:
        pass


Handler.extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript", ".woff2": "font/woff2", ".svg": "image/svg+xml"}


def serve() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=str(HERE)))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


# ---------- build products that are not photographs ----------

def qr_matrix() -> list[list[bool]]:
    from reportlab.graphics.barcode import qrencoder
    qr = qrencoder.QRCode(None, qrencoder.QRErrorCorrectLevel.M)
    qr.addData(URL)
    qr.make()
    n = qr.getModuleCount()
    return [[bool(qr.isDark(r, c)) for c in range(n)] for r in range(n)]


QUIET = 2  # light modules around the code inside the SVG; the white tile around it adds the rest


def write_qr(matrix: list[list[bool]]) -> None:
    n = len(matrix)
    d = "".join(f"M{c + QUIET} {r + QUIET}h1v1h-1z" for r in range(n) for c in range(n) if matrix[r][c])
    size = n + 2 * QUIET
    (OUT / "qr.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" shape-rendering="crispEdges">'
        f'<rect width="{size}" height="{size}" fill="#FFFFFF"/><path d="{d}" fill="#000000"/></svg>', encoding="utf-8")


def write_shadows() -> None:
    """The film's phone shadow (a blurred rounded rectangle, film.js), as a small picture so it prints the same everywhere."""
    from PIL import Image, ImageDraw, ImageFilter
    for name, rgb, alpha, blur in (("light", (6, 44, 26), 0.36, 44), ("dark", (0, 8, 4), 0.6, 56)):
        mask = Image.new("L", (324, 570), 0)
        ImageDraw.Draw(mask).rounded_rectangle([60, 67, 264, 497], radius=36, fill=round(255 * alpha))
        mask = mask.filter(ImageFilter.GaussianBlur(blur / 2))
        picture = Image.new("RGBA", mask.size, rgb + (0,))
        picture.putalpha(mask)
        picture.save(OUT / f"shadow-{name}.png")


# ---------- checks in the page, before printing ----------

PAGE_CHECK = r"""
() => {
  const problems = [];
  const loaded = new Set();
  document.fonts.forEach((face) => { if (face.status === 'loaded') loaded.add(face.family.replace(/["']/g, '') + ' ' + face.weight); });
  for (const need of ['S Bonus Display 700', 'S Bonus UX 400', 'S Bonus UX 500', 'S Bonus UX 700']) {
    if (!loaded.has(need)) problems.push('font not loaded: ' + need);
  }
  const slides = [...document.querySelectorAll('.slide')];
  if (slides.length !== 14) problems.push('expected 14 slides, found ' + slides.length);
  slides.forEach((slide, index) => {
    const box = slide.getBoundingClientRect();
    const phones = [...slide.querySelectorAll('.ph__body')].map((el) => el.getBoundingClientRect());
    const walker = document.createTreeWalker(slide, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!node.textContent.trim()) continue;
      const el = node.parentElement;
      const style = getComputedStyle(el);
      const family = style.fontFamily.split(',')[0].replace(/["']/g, '').trim();
      const words = node.textContent.trim().slice(0, 40);
      if (!/^S Bonus (UX|Display)$/.test(family)) problems.push(`slide ${index + 1}: "${words}" is set in ${family}`);
      if (!['400', '500', '700'].includes(style.fontWeight)) problems.push(`slide ${index + 1}: "${words}" asks for weight ${style.fontWeight}, which the bank's face does not have`);
      if (el.closest('.ph')) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      for (const r of range.getClientRects()) {
        if (r.width < 1) continue;
        if (r.left < box.left + 40 || r.right > box.right - 40 || r.top < box.top + 30 || r.bottom > box.bottom - 30) problems.push(`slide ${index + 1}: "${words}" leaves the slide's safe area`);
        for (const p of phones) {
          if (r.left < p.right + 16 && r.right > p.left - 16 && r.top < p.bottom && r.bottom > p.top) problems.push(`slide ${index + 1}: "${words}" runs into the phone`);
        }
      }
    }
    for (const el of slide.querySelectorAll('.ln, .chip, .crit__tag, .baskets li, .eyebrow, .proof strong, .score strong, .flow__node, .checks li, .parts li')) {
      if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).display !== 'inline') problems.push(`slide ${index + 1}: "${el.textContent.trim().slice(0, 40)}" is wider than its box`);
    }
  });
  const qr = document.querySelector('.cta__qr img').getBoundingClientRect();
  const last = slides[slides.length - 1].getBoundingClientRect();
  return { problems: [...new Set(problems)], missing: window.__missing, qr: [qr.left - last.left, qr.top - last.top, qr.width, qr.height] };
}
"""


async def print_pdf() -> dict:
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=CHROME_ARGS)
        page = await browser.new_page(viewport={"width": W, "height": H})
        failed: list[str] = []
        page.on("pageerror", lambda err: failed.append(f"page error: {err}"))
        page.on("requestfailed", lambda request: failed.append(request.url))
        page.on("response", lambda response: failed.append(f"{response.status} {response.url}") if response.status >= 400 else None)
        await page.goto(f"http://127.0.0.1:{PORT}/deck.html")
        try:
            await page.wait_for_function("() => window.__ready === true", timeout=30000)
        except Exception:
            failed.append("the page never became ready")
        if failed:
            await browser.close()
            raise SystemExit("The deck did not load completely, nothing was printed:\n  " + "\n  ".join(failed)
                             + "\nCheck that web/brand/ holds the bank's fonts and logo and that deck/screens/ has the screens.")
        report = await page.evaluate(PAGE_CHECK)
        if report["missing"]:
            await browser.close()
            raise SystemExit("Pictures did not load: " + ", ".join(report["missing"]))
        await page.emulate_media(media="screen")
        await page.pdf(path=str(PDF), width=f"{W}px", height=f"{H}px", print_background=True, prefer_css_page_size=True)
        await browser.close()
    return report


# ---------- checks on the finished file ----------

def check_pdf(matrix: list[list[bool]], qr_box: list[float]) -> list[str]:
    import pymupdf
    problems: list[str] = []
    doc = pymupdf.open(PDF)
    if doc.page_count != PAGES:
        problems.append(f"the PDF has {doc.page_count} pages, not {PAGES}")
    fonts: set[str] = set()
    links: dict[int, list[str]] = {}
    for number, page in enumerate(doc, start=1):
        if abs(page.rect.width / page.rect.height - 16 / 9) > 0.001:
            problems.append(f"page {number} is {page.rect.width:.0f} x {page.rect.height:.0f} pt, not 16:9")
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    if not span["text"].strip():
                        continue
                    # Chromium embeds S Bonus Display (TrueType outlines) under its own name and S Bonus UX
                    # (OpenType with CFF outlines) as unnamed Type 3 fonts. A stand-in from the system
                    # would be embedded under its own name, and is caught here.
                    kind = span["font"].split(" (")[0]
                    fonts.add(kind)
                    if kind != "Type3" and "SBonus" not in kind.replace(" ", ""):
                        problems.append(f'page {number}: "{span["text"].strip()[:40]}" is set in {span["font"]}, not the bank\'s typeface')
        links[number] = [link.get("uri", "") for link in page.get_links() if link.get("uri")]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(W / page.rect.width, H / page.rect.height), alpha=False)
        if (pix.width, pix.height) != (W, H):
            problems.append(f"page {number} rasterised to {pix.width} x {pix.height}")
        pix.save(OUT / f"slide-{number:02d}.png")
        if number == PAGES:
            # The QR code as it came out of the PDF, module by module, against the encoder's own matrix.
            n = len(matrix)
            x0, y0, w, h = qr_box
            step = w / (n + 2 * QUIET)
            wrong = 0
            for r in range(n):
                for c in range(n):
                    px = pix.pixel(round(x0 + (c + QUIET + 0.5) * step), round(y0 + (r + QUIET + 0.5) * step))
                    if (sum(px[:3]) < 384) != matrix[r][c]:
                        wrong += 1
            if wrong:
                problems.append(f"{wrong} QR modules in the PDF differ from the encoder's matrix")
    for number in (1, PAGES):
        if not any(uri.rstrip("/") == URL for uri in links.get(number, [])):
            problems.append(f"page {number} has no clickable link to {URL}")
    size = PDF.stat().st_size
    if size > 15 * 1024 * 1024:
        problems.append(f"the PDF is {size / 1024 / 1024:.1f} MB, over 15 MB")
    print(f"{PDF}\n  {doc.page_count} pages, {doc[0].rect.width:.0f} x {doc[0].rect.height:.0f} pt, {size / 1024 / 1024:.2f} MB")
    print("  fonts in the text: " + ", ".join(sorted(fonts)))
    print("  links: " + "; ".join(f"page {n}: {', '.join(sorted(set(u)))}" for n, u in links.items() if u))
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--capture", action="store_true", help="photograph every app screen again before building")
    args = parser.parse_args()

    lacking = [name for name in BRAND if not (WEB / "brand" / name).exists()]
    if lacking:
        raise SystemExit("web/brand/ is missing " + ", ".join(lacking) + ". The deck is not built with stand-in fonts: copy the folder from a teammate.")
    OUT.mkdir(exist_ok=True)
    SCREENS.mkdir(exist_ok=True)

    import capture
    need = [name for name in capture.SHOTS if not (SCREENS / f"{name}.png").exists()]
    if args.capture or need:
        asyncio.run(capture.main(list(capture.SHOTS) if args.capture else need))

    matrix = qr_matrix()
    write_qr(matrix)
    write_shadows()

    server = serve()
    try:
        report = asyncio.run(print_pdf())
    finally:
        server.shutdown()
    problems = report["problems"] + check_pdf(matrix, report["qr"])
    print(f"  slide-01.png to slide-{PAGES:02d}.png, {W} x {H}, rasterised from the PDF")
    if problems:
        print("\nLook at these before sending the deck:")
        for line in problems:
            print("  - " + line)
        raise SystemExit(1)
    print("  checks passed: fonts, pictures, layout, links, QR modules")


if __name__ == "__main__":
    main()
