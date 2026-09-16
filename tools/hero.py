"""Parametric pixel-art rig for a 4-direction hero.

Single source of truth for the sprite. Every frame is drawn by the same body
part functions; only pose parameters (bob, leg phase, arm swing) change between
frames, so the character cannot drift between directions or animations.

Frame: 32x32. The character is symmetric about the x=15/16 boundary.
Rule of thumb used throughout: the hips follow the body bob, the feet stay
planted on the ground line, so the legs stretch by a pixel instead of the
whole character hopping.
"""

W = H = 32

# ---------------------------------------------------------------- palette ---
# Key -> (RGBA, human name). Deliberately small: 13 colours + a shadow tint.
PALETTE = {
    "OL":  ((0x24, 0x1a, 0x2e, 255), "outline"),
    "SK":  ((0xf2, 0xc2, 0x92, 255), "skin"),
    "SKS": ((0xcc, 0x94, 0x64, 255), "skin shade"),
    "HR":  ((0x5c, 0x3a, 0x24, 255), "hair"),
    "HRL": ((0x82, 0x55, 0x35, 255), "hair light"),
    "TU":  ((0x4f, 0xa5, 0x55, 255), "tunic"),
    "TUS": ((0x2f, 0x71, 0x3c, 255), "tunic shade"),
    "TUL": ((0x74, 0xc4, 0x6b, 255), "tunic light"),
    "PN":  ((0x3d, 0x5d, 0x94, 255), "pants"),
    "PNS": ((0x28, 0x41, 0x6d, 255), "pants shade"),
    "BT":  ((0x7d, 0x51, 0x2f, 255), "boots"),
    "BTS": ((0x55, 0x34, 0x1d, 255), "boots shade"),
    "EY":  ((0x24, 0x1a, 0x2e, 255), "eye"),
    "SH":  ((0x24, 0x1a, 0x2e, 90),  "ground shadow"),
    "GR":  ((0x4e, 0x7a, 0x3a, 255), "grass"),
    "GRD": ((0x46, 0x70, 0x33, 255), "grass dark"),
    "GRL": ((0x5e, 0x8c, 0x45, 255), "grass light"),
    "BU":  ((0x35, 0x72, 0x3a, 255), "bush"),
    "BUD": ((0x23, 0x4f, 0x2b, 255), "bush dark"),
    "BUL": ((0x45, 0x89, 0x4a, 255), "bush light"),
}

class Canvas:
    """Tiny indexed pixel buffer. Stores palette keys; None = transparent."""

    def __init__(self, w=W, h=H):
        self.w, self.h = w, h
        self.px = [[None] * w for _ in range(h)]

    def set(self, x, y, key):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = key

    def rect(self, x0, y0, x1, y1, key):
        """Inclusive rectangle."""
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.set(x, y, key)

    def row(self, x0, x1, y, key):
        self.rect(x0, y, x1, y, key)

    def col(self, x, y0, y1, key):
        self.rect(x, y0, x, y1, key)

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[y][x]
        return None

    def mirrored(self):
        out = Canvas(self.w, self.h)
        for y in range(self.h):
            for x in range(self.w):
                out.px[y][x] = self.px[y][self.w - 1 - x]
        return out

    def outline(self, key="OL"):
        """Wrap the silhouette in a 1px outline (4-neighbourhood)."""
        add = []
        for y in range(self.h):
            for x in range(self.w):
                if self.px[y][x] is not None:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if self.get(x + dx, y + dy) is not None:
                        add.append((x, y))
                        break
        for x, y in add:
            self.set(x, y, key)
        return self

    def rgba_bytes(self):
        out = bytearray()
        for y in range(self.h):
            for x in range(self.w):
                k = self.px[y][x]
                out += bytes(PALETTE[k][0]) if k else b"\x00\x00\x00\x00"
        return bytes(out)


# ------------------------------------------------------------- body parts ---
# Anatomy constants, in frame pixels, for bob == 0.
HEAD_TOP = 4     # first hair row
NECK_Y = 13
TORSO_TOP = 14   # shoulders
BELT_Y = 21
HIP_Y = 22       # first leg row
FOOT_Y = 28      # last boot row (the ground line, never moves)

LEG_L = (12, 14)  # left leg columns, front/back views
LEG_R = (17, 19)  # right leg columns


def head_front(c, dy=0):
    t = HEAD_TOP + dy
    c.row(13, 18, t + 0, "HRL")
    c.row(12, 19, t + 1, "HR")
    c.row(11, 20, t + 2, "HR")
    c.row(11, 20, t + 3, "HR")            # fringe
    c.row(11, 12, t + 4, "HR")
    c.row(13, 18, t + 4, "SK")            # face starts
    c.row(19, 20, t + 4, "HR")
    c.set(11, t + 5, "HR")
    c.row(12, 19, t + 5, "SK")
    c.set(20, t + 5, "HR")
    c.set(11, t + 6, "SKS")               # sideburn shade
    c.row(12, 19, t + 6, "SK")
    c.set(20, t + 6, "SKS")
    c.row(12, 19, t + 7, "SK")
    c.row(13, 18, t + 8, "SKS")           # jaw in shade
    c.set(14, t + 6, "EY")
    c.set(17, t + 6, "EY")


def head_back(c, dy=0):
    t = HEAD_TOP + dy
    c.row(13, 18, t + 0, "HRL")           # crown catches the light
    c.row(12, 19, t + 1, "HRL")
    c.rect(11, t + 2, 20, t + 6, "HR")
    c.row(12, 19, t + 7, "HR")            # rounded off at the nape
    c.row(13, 18, t + 8, "HR")


def head_side(c, dy=0):
    """Profile facing +x. One pixel narrower than the front view."""
    t = HEAD_TOP + dy
    c.row(13, 19, t + 0, "HRL")
    c.row(12, 20, t + 1, "HR")
    c.row(12, 20, t + 2, "HR")
    c.row(12, 17, t + 3, "HR")            # fringe over the brow
    c.row(18, 20, t + 3, "SK")
    c.row(12, 15, t + 4, "HR")
    c.row(16, 20, t + 4, "SK")
    c.set(21, t + 4, "SK")                # nose
    c.row(12, 14, t + 5, "HR")
    c.row(15, 20, t + 5, "SK")
    c.set(15, t + 5, "SKS")               # ear
    c.set(18, t + 5, "EY")
    c.row(12, 13, t + 6, "HR")
    c.row(14, 20, t + 6, "SK")
    c.set(13, t + 7, "SKS")
    c.row(14, 19, t + 7, "SK")
    c.row(14, 18, t + 8, "SKS")           # jaw


def torso_front(c, dy=0, back=False):
    t = TORSO_TOP + dy
    b = BELT_Y + dy
    c.rect(12, t, 19, b - 1, "TU")
    c.row(12, 19, t, "TUL")               # shoulder highlight
    if not back:
        c.col(15, t + 2, b - 2, "TUS")    # tunic fold
    c.row(12, 19, b, "BT")                # belt
    c.set(15, b, "BTS")
    c.set(16, b, "BTS")
    c.row(14, 17, NECK_Y + dy, "HR" if back else "SKS")


def torso_side(c, dy=0):
    t = TORSO_TOP + dy
    b = BELT_Y + dy
    c.rect(13, t, 19, b - 1, "TU")
    c.row(13, 19, t, "TUL")
    c.col(13, t + 1, b - 1, "TUS")        # back of the tunic in shade
    c.row(13, 19, b, "BT")
    c.set(13, b, "BTS")
    c.row(14, 17, NECK_Y + dy, "SKS")


def arms_front(c, dy=0, swing=0, back=False):
    """swing > 0: left arm up / right arm down; < 0 is the mirror."""
    t = TORSO_TOP + dy + 1
    for side, x0, inner in ((-1, 10, 11), (1, 20, 20)):
        off = -1 if swing * side > 0 else (1 if swing else 0)
        x1 = x0 + 1
        c.rect(x0, t + off, x1, t + 3 + off, "TU")
        c.col(inner, t + off, t + 3 + off, "TUS")   # seam against the torso
        c.rect(x0, t + 4 + off, x1, t + 5 + off, "SKS" if back else "SK")


def arm_side(c, dy=0, swing=0):
    """The near arm only; the far arm is implied, which keeps the read clean."""
    t = TORSO_TOP + dy + 1
    x = 17 + swing                         # hangs near the chest, swings 1px
    c.rect(x, t + 1, x + 1, t + 4, "TU")
    c.col(x, t + 1, t + 4, "TUS")          # one seam, not a stripe pattern
    c.rect(x, t + 5, x + 1, t + 6, "SK")   # the hand below the hem carries it


def _leg_front(c, x0, x1, top, lift, toe):
    foot = FOOT_Y - lift
    c.rect(x0, top, x1, foot - 2, "PN")
    c.col(x0, top, foot - 2, "PNS")
    bx0 = x0 - 1 if toe < 0 else x0
    bx1 = x1 + 1 if toe > 0 else x1
    c.rect(bx0, foot - 1, bx1, foot, "BT")
    c.row(bx0, bx1, foot, "BTS")


def legs_front(c, top_dy=0, phase=0):
    """phase: 0 both planted, +1 right leg lifted, -1 left leg lifted."""
    top = HIP_Y + top_dy
    lift_l, lift_r = {0: (0, 0), 1: (0, 2), -1: (2, 0)}[phase]
    _leg_front(c, LEG_L[0], LEG_L[1], top, lift_l, -1)
    _leg_front(c, LEG_R[0], LEG_R[1], top, lift_r, +1)


def legs_side(c, top_dy=0, phase=0):
    """phase: +1 near leg forward, -1 near leg back, 0 legs passing."""
    top = HIP_Y + top_dy
    near_x = 14 + 3 * phase
    far_x = 14 - 3 * phase
    lift = 1 if phase == 0 else 0
    for x, pants, boot, lf in ((far_x, "PNS", "BTS", 0),
                               (near_x, "PN", "BT", lift)):
        foot = FOOT_Y - lf
        c.rect(x, top, x + 2, foot - 2, pants)
        c.col(x, top, foot - 2, "PNS")
        c.rect(x, foot - 1, x + 2, foot, boot)
        c.row(x, x + 2, foot, "BTS")
        c.set(x + 3, foot, "BTS")                  # toe points forward


# ------------------------------------------------------------------ poses ---
def draw_hero(direction, bob=0, leg=0, swing=0):
    """Draw one hero cel. direction in {down, up, right}; left is mirrored."""
    c = Canvas()
    if direction == "down":
        legs_front(c, bob, leg)
        torso_front(c, bob)
        arms_front(c, bob, swing)
        head_front(c, bob)
    elif direction == "up":
        legs_front(c, bob, leg)
        torso_front(c, bob, back=True)
        arms_front(c, bob, swing, back=True)
        head_back(c, bob)
    elif direction == "right":
        legs_side(c, bob, leg)
        torso_side(c, bob)
        head_side(c, bob)
        arm_side(c, bob, swing)
    else:
        raise ValueError(direction)
    return c.outline()


def draw_shadow(squash=0):
    """Ground shadow cel, on its own layer under the hero."""
    c = Canvas()
    y = FOOT_Y + 1
    if squash:
        c.row(12, 19, y, "SH")
        c.row(14, 17, y + 1, "SH")
    else:
        c.row(11, 20, y, "SH")
        c.row(13, 18, y + 1, "SH")
    return c


# ------------------------------------------------------------------ props ---
# Scenery shares the hero's frame size, palette and outline pass, so the demo
# scene is one art pipeline rather than two.

def draw_ground():
    """A 32x32 grass tile. All detail is inset so the tile repeats seamlessly."""
    c = Canvas()
    c.rect(0, 0, W - 1, H - 1, "GR")
    for x, y, n in ((3, 5, 3), (17, 3, 2), (25, 9, 3), (9, 13, 2),
                    (20, 17, 3), (4, 21, 2), (27, 24, 2), (13, 27, 3)):
        c.row(x, x + n - 1, y, "GRD")                 # flattened blades
    for x, y in ((7, 8), (22, 12), (12, 20), (28, 19), (17, 25), (2, 16)):
        c.row(x, x + 1, y, "GRL")                     # lit tufts
        c.set(x + (1 if x % 2 else 0), y - 1, "GRL")
    return c


def draw_bush():
    """A bush, grounded on the same foot line as the hero so depth sorting
    by sprite y works for both without per-object tuning."""
    c = Canvas()
    for y, x0, x1 in ((16, 11, 20), (17, 9, 22), (18, 8, 23), (19, 7, 24),
                      (20, 6, 25), (21, 6, 25), (22, 6, 25), (23, 6, 25),
                      (24, 6, 25), (25, 6, 25), (26, 6, 25), (27, 6, 25),
                      (28, 7, 24), (29, 9, 22)):
        c.row(x0, x1, y, "BU")
    for y, x0, x1 in ((17, 12, 15), (18, 10, 16), (19, 9, 15),
                      (20, 8, 13), (21, 8, 11), (22, 9, 10)):
        c.row(x0, x1, y, "BUL")          # light crescent on the upper left
    for y, x0, x1 in ((22, 22, 25), (23, 21, 25), (24, 20, 25), (25, 18, 25),
                      (26, 16, 25), (27, 6, 25), (28, 7, 24), (29, 9, 22)):
        c.row(x0, x1, y, "BUD")          # shade curves round the lower right
    for x, y in ((13, 16), (18, 16)):
        c.set(x, y, None)                # notch the crown so it reads as leaves
    for x, y in ((14, 21), (11, 25), (19, 19)):
        c.set(x, y, "BUD")               # sparse leaf gaps
    return c.outline()


PROPS = ["ground", "bush"]


def build_props():
    """[(name, Canvas), ...] in sheet order."""
    return [("ground", draw_ground()), ("bush", draw_bush())]


# --------------------------------------------------------------- timeline ---
DIRECTIONS = ["down", "left", "right", "up"]

# 4-frame walk: contact, passing, contact, passing.
WALK = [
    dict(bob=0, leg=1, swing=-1, squash=0),
    dict(bob=-1, leg=0, swing=0, squash=1),
    dict(bob=0, leg=-1, swing=1, squash=0),
    dict(bob=-1, leg=0, swing=0, squash=1),
]
# 2-frame idle breath.
IDLE = [
    dict(bob=0, leg=0, swing=0, squash=0),
    dict(bob=-1, leg=0, swing=0, squash=0),
]
WALK_MS = 120
IDLE_MS = 500

COLS = 6                   # sheet layout: one row of 6 per direction


def build_frames():
    """Linear frame list: [(name, hero Canvas, shadow Canvas, duration_ms)]."""
    frames = []
    for d in DIRECTIONS:
        src = "right" if d == "left" else d
        for kind, poses, ms in (("walk", WALK, WALK_MS), ("idle", IDLE, IDLE_MS)):
            for i, p in enumerate(poses):
                hero = draw_hero(src, bob=p["bob"], leg=p["leg"], swing=p["swing"])
                if d == "left":
                    hero = hero.mirrored()
                frames.append((f"{kind}-{d}-{i}", hero, draw_shadow(p["squash"]), ms))
    return frames


def build_tags():
    """Frame tags, in the same linear order as build_frames()."""
    tags, i = [], 0
    for d in DIRECTIONS:
        for kind, n in (("walk", len(WALK)), ("idle", len(IDLE))):
            tags.append((f"{kind}-{d}", i, i + n - 1))
            i += n
    return tags
