# Mort Lab gallery

Static image gallery for [The Mort Lab](https://wp.lancs.ac.uk/mortlab/), served by GitHub Pages at
https://richiemort79.github.io/mortlab-gallery/

## Adding an image

1. Copy the image into `images/` (web-safe name: lowercase, hyphens, no spaces).
2. Add an entry to `captions.json`: `{"file": "images/your-image.png", "caption": "..."}`.
3. Run `python build.py` (Python 3, standard library only) to regenerate `index.html`.
4. Commit and push.

Animated GIFs play in the grid as small MP4 copies in `video/` (made automatically by `build.py` when ffmpeg is installed); the lightbox plays the same video larger, with a link to the original GIF. Set `SPEED` in `build.py` to change playback speed (0.5 = half the GIF speed).

Tile order is randomised on each load; set `const SHUFFLE = false;` in the template in `build.py` to keep the `captions.json` order.
