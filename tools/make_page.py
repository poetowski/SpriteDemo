"""Bundle game/index.html into one self-contained, shareable page.

    python tools/make_page.py        (also run at the end of tools/build.py)

Writes game/page.html: the same markup and the same scene code as the local
page, with art-embed.js and main.js inlined and Phaser pointed at a pinned CDN
instead of the vendored copy. One file, no server, nothing beside it.
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "game")
PHASER_CDN = "https://cdn.jsdelivr.net/npm/phaser@3.90.0/dist/phaser.min.js"


def build():
    with open(os.path.join(GAME, "index.html"), encoding="utf-8") as fh:
        html = fh.read()

    # The page is embedded in a host document, so drop our own skeleton tags.
    html = re.sub(r"<!DOCTYPE html>\s*|</?html[^>]*>|</?head>|</?body>", "", html,
                  flags=re.I)
    html = re.sub(r'<meta charset[^>]*>|<meta name="viewport"[^>]*>', "", html,
                  flags=re.I)

    # Vendored Phaser plus its fallback become one pinned CDN tag.
    html = re.sub(
        r'<script src="vendor/phaser\.min\.js"></script>\s*<script>.*?</script>',
        f'<script src="{PHASER_CDN}"></script>',
        html, flags=re.S)

    for name in ("art-embed.js", "main.js"):
        with open(os.path.join(GAME, name), encoding="utf-8") as fh:
            body = fh.read()
        html = html.replace(f'<script src="{name}"></script>',
                            "<script>\n" + body + "\n</script>")

    external = re.findall(r'<script src="([^"]+)"', html)
    assert external == [PHASER_CDN], f"unexpected external scripts: {external}"

    out = os.path.join(GAME, "page.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html.strip() + "\n")
    return out, os.path.getsize(out)


if __name__ == "__main__":
    path, size = build()
    print(f"game/page.html  {size:>8} B  (self-contained; Phaser from CDN)")
