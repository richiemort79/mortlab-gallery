#!/usr/bin/env python3
"""Build index.html from captions.json. Python 3 standard library only.

Usage: add an image to images/, add an entry to captions.json, run
`python build.py`, then commit and push.
"""
import html
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WP = "https://wp.lancs.ac.uk/mortlab/"
FAVICON = "https://wp.lancs.ac.uk/mortlab/files/2019/11/cropped-logo-2-270x270.png"
DEFAULT_ALT = "Fluorescence microscopy image from the Mort Lab"

MENU = [
    ("Home", "http://wp.lancs.ac.uk/mortlab"),
    ("Projects", WP + "members/"),
    ("Gallery", None),  # this page
    ("Publications", WP + "publications/"),
    ("Resources", WP + "resources/"),
    ("Code", WP + "mort-lab-code/"),
    ("Fucci", WP + "r26fucci2a-applications/"),
    ("Contact", WP + "contact/"),
    ("Profiles", WP + "profiles/"),
    ("Outreach", WP + "outreach/"),
]


def image_size(path):
    """Return (width, height) for PNG, GIF, JPEG or WebP, or None."""
    with open(path, "rb") as f:
        head = f.read(32)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", head[16:24])
        if head[:6] in (b"GIF87a", b"GIF89a"):
            return struct.unpack("<HH", head[6:10])
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            chunk = head[12:16]
            if chunk == b"VP8 ":
                w, h = struct.unpack("<HH", head[26:30])
                return w & 0x3FFF, h & 0x3FFF
            if chunk == b"VP8L":
                b = head[21:25]
                w = 1 + (((b[1] & 0x3F) << 8) | b[0])
                h = 1 + (((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
                return w, h
            if chunk == b"VP8X":
                w = 1 + int.from_bytes(head[24:27], "little")
                h = 1 + int.from_bytes(head[27:30], "little")
                return w, h
            return None
        if head[:2] == b"\xff\xd8":
            f.seek(2)
            while True:
                b = f.read(1)
                while b and b != b"\xff":
                    b = f.read(1)
                while b == b"\xff":
                    b = f.read(1)
                if not b:
                    return None
                marker = b[0]
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                    continue
                seg_len = struct.unpack(">H", f.read(2))[0]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                              0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    f.read(1)
                    h, w = struct.unpack(">HH", f.read(4))
                    return w, h
                f.seek(seg_len - 2, 1)
    return None


def esc(s):
    return html.escape(s, quote=True)


def build():
    with open(os.path.join(HERE, "captions.json"), encoding="utf-8") as f:
        entries = json.load(f)

    tiles = []
    for e in entries:
        rel = e["file"]
        cap = (e.get("caption") or "").strip()
        path = os.path.join(HERE, rel)
        if not os.path.isfile(path):
            sys.exit(f"Missing image: {rel}")
        size = image_size(path)
        if not size:
            sys.exit(f"Could not read dimensions of {rel}")
        w, h = size
        alt = cap or DEFAULT_ALT
        overlay = f'<span class="cap">{esc(cap)}</span>' if cap else ""
        tiles.append(
            f'<li><button type="button" class="tile" data-src="{esc(rel)}" '
            f'data-caption="{esc(cap)}">'
            f'<img src="{esc(rel)}" alt="{esc(alt)}" width="{w}" height="{h}" '
            f'loading="lazy" decoding="async">{overlay}</button></li>'
        )

    menu = []
    for label, href in MENU:
        if href is None:
            menu.append(f'<li><a href="./" class="active" aria-current="page">{label}</a></li>')
        else:
            menu.append(f'<li><a href="{esc(href)}">{label}</a></li>')

    page = TEMPLATE.format(
        favicon=esc(FAVICON),
        wp=esc(WP),
        menu="\n        ".join(menu),
        tiles="\n      ".join(tiles),
    )
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print(f"Wrote index.html with {len(tiles)} images.")


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gallery – The Mort Lab</title>
<link rel="icon" href="{favicon}">
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    background: #0d0d0d; color: #f0f0f0;
    font-family: Roboto, system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    line-height: 1.5;
  }}
  a {{ color: #4dd0e1; text-decoration: none; }}
  a:hover, a:focus-visible {{ text-decoration: underline; }}
  :focus-visible {{ outline: 2px solid #4dd0e1; outline-offset: 2px; }}
  .site-header {{
    background: #0d0d0d; display: flex; flex-wrap: wrap; align-items: center;
    justify-content: space-between; gap: 0.5em 1.5em; padding: 1em 16px;
    max-width: 1200px; margin: 0 auto;
  }}
  .site-title {{ font-size: 1.4em; font-weight: 700; color: #f0f0f0; }}
  .site-title:hover {{ color: #4dd0e1; text-decoration: none; }}
  nav ul {{ list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 0.25em 1.1em; }}
  nav a {{ color: #f0f0f0; font-size: 0.95em; }}
  nav a:hover, nav a.active {{ color: #4dd0e1; text-decoration: none; }}
  main {{ max-width: 1200px; margin: 0 auto; padding: 0 16px 2em; }}
  h1 {{ font-weight: 400; font-size: 2em; margin: 0.6em 0 0.6em; }}
  .grid {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; grid-template-columns: 1fr; }}
  @media (min-width: 500px) {{ .grid {{ grid-template-columns: repeat(2, 1fr); }} }}
  @media (min-width: 900px) {{ .grid {{ grid-template-columns: repeat(3, 1fr); }} }}
  .tile {{
    position: relative; display: block; width: 100%; aspect-ratio: 1 / 1; padding: 0; margin: 0;
    border: 0; border-radius: 6px; overflow: hidden; background: #000; cursor: zoom-in; color: inherit; font: inherit;
  }}
  .tile img {{ display: block; width: 100%; height: 100%; object-fit: cover; border: 0; transition: transform .3s; }}
  .tile:hover img {{ transform: scale(1.03); }}
  .cap {{
    position: absolute; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.65); color: #f0f0f0;
    text-align: center; font-size: 0.8em; padding: 0.5em; overflow-wrap: anywhere; line-height: 1.35;
  }}
  footer {{ text-align: center; padding: 2em 16px; font-size: 0.9em; color: #f0f0f0; }}
  .lightbox {{
    position: fixed; inset: 0; z-index: 100; background: rgba(0,0,0,0.92); display: none;
    flex-direction: column; align-items: center; justify-content: center; padding: 48px 16px 16px;
  }}
  .lightbox.open {{ display: flex; }}
  .lightbox figure {{ margin: 0; max-width: 100%; max-height: 100%; display: flex; flex-direction: column; align-items: center; }}
  .lightbox img {{ max-width: 100%; max-height: calc(100vh - 160px); object-fit: contain; border-radius: 6px; }}
  .lightbox figcaption {{ margin-top: 0.75em; max-width: 60em; text-align: center; font-size: 0.95em; }}
  .lb-close {{
    position: absolute; top: 8px; right: 12px; background: none; border: 0; color: #f0f0f0;
    font-size: 2.2em; line-height: 1; cursor: pointer; padding: 0.1em 0.3em;
  }}
  .lb-close:hover {{ color: #4dd0e1; }}
  body.no-scroll {{ overflow: hidden; }}
</style>
</head>
<body>
<header>
  <div class="site-header">
    <a class="site-title" href="{wp}">The Mort Lab</a>
    <nav aria-label="Main">
      <ul>
        {menu}
      </ul>
    </nav>
  </div>
</header>
<main>
  <h1>Gallery</h1>
  <ul class="grid" id="grid">
      {tiles}
  </ul>
</main>
<footer>Copyright © 2026 <a href="{wp}">The Mort Lab</a></footer>
<div class="lightbox" id="lightbox" role="dialog" aria-modal="true" aria-label="Image viewer" hidden>
  <button type="button" class="lb-close" id="lb-close" aria-label="Close">&times;</button>
  <figure>
    <img id="lb-img" alt="">
    <figcaption id="lb-cap"></figcaption>
  </figure>
</div>
<script>
const SHUFFLE = true;
(function () {{
  var grid = document.getElementById("grid");
  if (SHUFFLE) {{
    var items = Array.prototype.slice.call(grid.children);
    for (var i = items.length - 1; i > 0; i--) {{
      var j = Math.floor(Math.random() * (i + 1));
      var t = items[i]; items[i] = items[j]; items[j] = t;
    }}
    items.forEach(function (li) {{ grid.appendChild(li); }});
  }}
  var lb = document.getElementById("lightbox"), img = document.getElementById("lb-img"),
      cap = document.getElementById("lb-cap"), closeBtn = document.getElementById("lb-close"), last = null;
  function open(btn) {{
    last = btn;
    var c = btn.getAttribute("data-caption");
    img.src = btn.getAttribute("data-src");
    img.alt = c || "{default_alt}";
    cap.textContent = c;
    cap.hidden = !c;
    lb.hidden = false; lb.classList.add("open"); document.body.classList.add("no-scroll");
    closeBtn.focus();
  }}
  function close() {{
    lb.classList.remove("open"); lb.hidden = true; document.body.classList.remove("no-scroll");
    img.removeAttribute("src");
    if (last) last.focus();
  }}
  grid.addEventListener("click", function (e) {{
    var btn = e.target.closest(".tile"); if (btn) open(btn);
  }});
  closeBtn.addEventListener("click", close);
  lb.addEventListener("click", function (e) {{ if (e.target !== img && e.target !== cap) close(); }});
  document.addEventListener("keydown", function (e) {{
    if (lb.hidden) return;
    if (e.key === "Escape") close();
    else if (e.key === "Tab") {{ e.preventDefault(); closeBtn.focus(); }}
  }});
}})();
</script>
</body>
</html>
""".replace("{default_alt}", DEFAULT_ALT)

if __name__ == "__main__":
    build()
