#!/usr/bin/env python3
"""Build index.html from captions.json. Python 3 standard library only.

Usage: add an image to images/, add an entry to captions.json, run
`python build.py`, then commit and push.

Animated GIFs are large, so for each images/NAME.gif the grid tile plays a
small looping MP4 (video/NAME.mp4, with a first-frame poster video/NAME.jpg)
and the lightbox shows the original GIF. If those files are missing and
ffmpeg is installed, build.py creates them; without ffmpeg the tile just
uses the GIF.
"""
import html
import json
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WP = "https://wp.lancs.ac.uk/mortlab/"
FAVICON = "https://wp.lancs.ac.uk/mortlab/files/2019/11/cropped-logo-2-270x270.png"
DEFAULT_ALT = "Fluorescence microscopy image from the Mort Lab"
VIDEO_DIR = "video"
CRF = "20"  # H.264 quality for tile videos (lower = better/larger)

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


def is_animated_gif(path):
    """True if the GIF has more than one frame (counts image descriptors)."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        return False
    pos = 13
    flags = data[10]
    if flags & 0x80:
        pos += 3 * (2 ** ((flags & 7) + 1))
    frames = 0
    n = len(data)
    while pos < n:
        block = data[pos]
        if block == 0x3B:  # trailer
            break
        if block == 0x21:  # extension: skip label then sub-blocks
            pos += 2
        elif block == 0x2C:  # image descriptor
            frames += 1
            if frames > 1:
                return True
            lflags = data[pos + 9]
            pos += 10
            if lflags & 0x80:
                pos += 3 * (2 ** ((lflags & 7) + 1))
            pos += 1  # LZW min code size
        else:
            return False
        while pos < n and data[pos] != 0:
            pos += data[pos] + 1
        pos += 1
    return False


def tile_video(rel):
    """For an animated GIF, return (mp4, poster) relative paths, creating them
    with ffmpeg if needed. Returns None if unavailable."""
    stem = os.path.splitext(os.path.basename(rel))[0]
    mp4 = f"{VIDEO_DIR}/{stem}.mp4"
    jpg = f"{VIDEO_DIR}/{stem}.jpg"
    src = os.path.join(HERE, rel)
    mp4_abs, jpg_abs = os.path.join(HERE, mp4), os.path.join(HERE, jpg)
    fresh = lambda p: os.path.isfile(p) and os.path.getmtime(p) >= os.path.getmtime(src)
    if fresh(mp4_abs) and fresh(jpg_abs):
        return mp4, jpg
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print(f"  note: ffmpeg not found, {rel} tile will use the GIF directly")
        return None
    os.makedirs(os.path.join(HERE, VIDEO_DIR), exist_ok=True)
    print(f"  encoding {mp4} ...")
    even = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-i", src, "-an",
                    "-c:v", "libx264", "-preset", "slow", "-crf", CRF,
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    "-vf", even, mp4_abs], check=True)
    subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-i", src,
                    "-frames:v", "1", "-q:v", "3", "-vf", even, jpg_abs], check=True)
    return mp4, jpg


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
        vid = tile_video(rel) if rel.lower().endswith(".gif") and is_animated_gif(path) else None
        if vid:
            mp4, jpg = vid
            media = (f'<video data-src="{esc(mp4)}" poster="{esc(jpg)}" width="{w}" height="{h}" '
                     f'muted loop playsinline preload="none" aria-label="{esc(alt)}"></video>')
        else:
            media = (f'<img src="{esc(rel)}" alt="{esc(alt)}" width="{w}" height="{h}" '
                     f'loading="lazy" decoding="async">')
        tiles.append(
            f'<li><button type="button" class="tile" data-src="{esc(rel)}" '
            f'data-caption="{esc(cap)}">{media}{overlay}</button></li>'
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
        menu="\n          ".join(menu),
        tiles="\n      ".join(tiles),
    )
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print(f"Wrote index.html with {len(tiles)} images.")


# Header styling mirrors the Astra theme on wp.lancs.ac.uk/mortlab/gallery/:
# 80px bar, 1px #d1d5db bottom border, 26px/600 site title, 16px menu items
# with 0 1em padding, 1200px content width, hamburger menu below 922px.
TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gallery – The Mort Lab</title>
<link rel="icon" href="{favicon}">
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  html {{ font-size: 100%; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    background: #0d0d0d; color: #f0f0f0;
    font-family: Roboto, system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 1rem; line-height: 1.65;
    min-height: 100vh; display: flex; flex-direction: column;
  }}
  a {{ color: #4dd0e1; text-decoration: none; }}
  a:hover {{ color: #4dd0e1; }}
  :focus-visible {{ outline: 2px solid #4dd0e1; outline-offset: 2px; }}
  .wrap {{ max-width: 1240px; margin: 0 auto; padding: 0 20px; width: 100%; }}

  /* Header */
  .site-header {{ background: #0d0d0d; border-bottom: 1px solid #d1d5db; position: relative; }}
  .site-header .wrap {{ display: flex; align-items: center; justify-content: space-between; min-height: 80px; }}
  .site-title {{ font-size: 1.625rem; font-weight: 600; line-height: 1.23; padding: 1em 0; margin: 0; }}
  .site-title a, .site-title a:hover {{ color: #f0f0f0; }}
  .main-nav ul {{ list-style: none; margin: 0; padding: 0; display: flex; }}
  .main-nav a {{ display: block; padding: 0 1em; line-height: 80px; color: #f0f0f0; transition: color .2s linear; }}
  .main-nav a:hover, .main-nav a.active {{ color: #4dd0e1; }}
  .menu-toggle {{ display: none; background: none; border: 0; padding: 8px; margin-right: -8px; color: #f0f0f0; cursor: pointer; }}
  .menu-toggle svg {{ width: 20px; height: 20px; fill: currentColor; display: block; }}
  .menu-toggle .icon-close {{ display: none; }}
  .menu-toggle[aria-expanded="true"] .icon-open {{ display: none; }}
  .menu-toggle[aria-expanded="true"] .icon-close {{ display: block; }}
  @media (max-width: 921.98px) {{
    html {{ font-size: 91.2%; }}
    .menu-toggle {{ display: block; }}
    .main-nav {{ display: none; position: absolute; top: 100%; left: 0; right: 0; z-index: 50;
                 background: #0d0d0d; border-bottom: 1px solid #d1d5db; }}
    .main-nav.open {{ display: block; }}
    .main-nav ul {{ flex-direction: column; padding: 0 0 10px; }}
    .main-nav a {{ line-height: 1.65; padding: 0.6em 20px; }}
    .main-nav a:hover, .main-nav a.active {{ background: #1a1a1a; }}
  }}

  /* Content */
  main {{ flex: 1 0 auto; }}
  main .wrap {{ max-width: 1240px; padding-top: 3em; padding-bottom: 3em; }}
  h1 {{ font-size: 2rem; font-weight: 600; line-height: 1.4; margin: 0 0 0.6em; color: #f0f0f0; }}
  @media (max-width: 921.98px) {{ main .wrap {{ padding-top: 2em; }} }}
  .grid {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; grid-template-columns: 1fr; }}
  @media (min-width: 500px) {{ .grid {{ grid-template-columns: repeat(2, 1fr); }} }}
  @media (min-width: 900px) {{ .grid {{ grid-template-columns: repeat(3, 1fr); }} }}
  .tile {{
    position: relative; display: block; width: 100%; aspect-ratio: 1 / 1; padding: 0; margin: 0;
    border: 0; border-radius: 6px; overflow: hidden; background: #000; cursor: zoom-in; color: inherit; font: inherit;
  }}
  .tile img, .tile video {{ display: block; width: 100%; height: 100%; object-fit: cover; border: 0; transition: transform .3s; }}
  .tile:hover img, .tile:hover video {{ transform: scale(1.03); }}
  .cap {{
    position: absolute; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.65); color: #f0f0f0;
    text-align: center; font-size: 0.8em; padding: 0.5em; overflow-wrap: anywhere; line-height: 1.35;
  }}

  /* Footer */
  footer {{ text-align: center; font-size: 1rem; }}
  footer .wrap {{ min-height: 60px; display: flex; align-items: center; justify-content: center; padding-top: 1em; padding-bottom: 1em; }}
  footer p {{ margin: 0; }}

  /* Lightbox */
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
<header class="site-header">
  <div class="wrap">
    <p class="site-title"><a href="{wp}" rel="home">The Mort Lab</a></p>
    <button type="button" class="menu-toggle" id="menu-toggle" aria-expanded="false" aria-controls="main-nav" aria-label="Main menu toggle">
      <svg class="icon-open" viewBox="0 0 20 20" aria-hidden="true"><rect y="3" width="20" height="2"/><rect y="9" width="20" height="2"/><rect y="15" width="20" height="2"/></svg>
      <svg class="icon-close" viewBox="0 0 20 20" aria-hidden="true"><path d="M3.5 2.1 10 8.6l6.5-6.5 1.4 1.4L11.4 10l6.5 6.5-1.4 1.4L10 11.4l-6.5 6.5-1.4-1.4L8.6 10 2.1 3.5z"/></svg>
    </button>
    <nav class="main-nav" id="main-nav" aria-label="Primary Site Navigation">
      <ul>
          {menu}
      </ul>
    </nav>
  </div>
</header>
<main>
  <div class="wrap">
    <h1>Gallery</h1>
    <ul class="grid" id="grid">
      {tiles}
    </ul>
  </div>
</main>
<footer>
  <div class="wrap"><p>Copyright © 2026 <a href="{wp}">The Mort Lab</a></p></div>
</footer>
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

  // Mobile menu toggle
  var toggle = document.getElementById("menu-toggle"), nav = document.getElementById("main-nav");
  toggle.addEventListener("click", function () {{
    var open = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    nav.classList.toggle("open", open);
  }});

  // Tile videos: load when near the viewport, pause when off-screen
  var videos = grid.querySelectorAll("video[data-src]");
  function start(v) {{
    if (!v.src) {{ v.src = v.getAttribute("data-src"); }}
    var p = v.play(); if (p && p.catch) p.catch(function () {{}});
  }}
  if ("IntersectionObserver" in window) {{
    var io = new IntersectionObserver(function (entries) {{
      entries.forEach(function (en) {{
        if (en.isIntersecting) start(en.target); else if (en.target.src) en.target.pause();
      }});
    }}, {{ rootMargin: "200px" }});
    videos.forEach(function (v) {{ io.observe(v); }});
  }} else {{
    videos.forEach(start);
  }}

  // Lightbox (shows the original file, e.g. the full GIF)
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
    if (e.key === "Escape" && nav.classList.contains("open") && lb.hidden) {{
      toggle.click(); toggle.focus(); return;
    }}
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
