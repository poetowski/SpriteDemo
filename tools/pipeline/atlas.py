"""Pack generated canvases into grid spritesheets.

Every entry carries its anchor - the pixel that sits on a map tile - so the
engine never has to guess where a sprite's feet are, and art of different sizes
still lines up. Frames are laid out row-major, which makes the index both the
atlas position and the animation frame number.
"""

from PIL import Image

from gen.palette import resolve


class Atlas:
    def __init__(self, name, frame_w, frame_h, cols):
        self.name = name
        self.fw, self.fh, self.cols = frame_w, frame_h, cols
        self.entries = []          # (key, [Canvas], anchor, ms, palette)

    def add(self, key, layers, anchor=(0, 0), ms=0, palette=None):
        """Add one frame; layers composite bottom-up. Returns its index."""
        self.entries.append((key, list(layers), tuple(anchor), ms,
                             palette or resolve()))
        return len(self.entries) - 1

    @property
    def rows(self):
        return max(1, -(-len(self.entries) // self.cols))

    def cell(self, index):
        return (index % self.cols) * self.fw, (index // self.cols) * self.fh

    def render(self):
        sheet = Image.new("RGBA", (self.cols * self.fw, self.rows * self.fh),
                          (0, 0, 0, 0))
        for i, (_k, layers, _a, _ms, pal) in enumerate(self.entries):
            for c in layers:
                img = Image.new("RGBA", (c.w, c.h))
                img.frombytes(c.rgba_bytes(pal))
                sheet.alpha_composite(img, self.cell(i))
        return sheet

    def sprites(self):
        """key -> record, for the manifest."""
        return {
            key: {"atlas": self.name, "index": i, "anchor": list(anchor)}
            for i, (key, _l, anchor, _ms, _p) in enumerate(self.entries)
        }

    def meta(self):
        return {"image": f"atlas/{self.name}.png",
                "frame": [self.fw, self.fh],
                "cols": self.cols, "rows": self.rows,
                "count": len(self.entries)}
