"""The big-quadruped rig: 4 facings, walk + idle + graze, in a 64x64 frame.

Same contract as every other rig - one ground line, one exported anchor, the
same build_frames shape - but drawn at the giant's size rather than the
livestock's, and on the giant's sheet, because the frame size is what decides
which sheet a rig belongs to. An elephant in the 32x32 frame the sheep share
comes out the size of a bear, and the whole point of one is that it is not.

The anchor sits at a tile centre (x=24) like the giant and the 64px props, so
the art covers tile offsets 0 and +1 and the definition says so with a
two-tile footprint. Everything is drawn centred on x=32, which is where those
two tiles meet.

Species differ by silhouette flags plus a palette variant, the same way the
small quadrupeds do.
"""

import math

from gen.palette import Canvas

FRAME = 64
GROUND_Y = 61                  # the row the feet stand on
ANCHOR = (24, GROUND_Y)        # a tile centre: the art covers offsets 0 and +1
ATLAS = "actors_huge"          # the 64px actor sheet, shared with the giant
COLS = 4
FACINGS = ["down", "left", "right", "up"]

FOOT_Y = 60
MID = 32                       # where the two tiles it stands on meet

SPECIES = {
    # "ears" is the flag that carries the whole animal: an elephant seen from
    # any angle is mostly ear. "tusks" and a trunk that reaches the ground do
    # the rest; nothing else here needs either.
    "elephant": {"ears": True, "tusks": True, "trunk": True, "tail": True},
}


# --------------------------------------------------------------- helpers ---
def _pillar(c, x, top, key, dark, w=7, foot="AH"):
    """A leg like a column, because that is what one looks like: no taper, a
    flat foot, and toenails. Drawn from `top` to the ground every time - a
    walking elephant lifts a foot barely a pixel, and at this size a leg that
    leaves the ground reads as a stumble.

    The width matters more than it looks: eight wide and the four feet ran
    together into one black plinth the length of the animal, which read as a
    thing on a stand rather than a thing standing."""
    c.rect(x, top, x + w, FOOT_Y - 2, key)
    c.col(x, top, FOOT_Y - 2, dark)
    c.rect(x - 1, FOOT_Y - 2, x + w + 1, FOOT_Y, foot)
    for i in range(3):
        c.set(x + 1 + i * 2, FOOT_Y - 1, "ABL")      # toenails
    return


def _trunk(c, x, y, drop, curl, key, dark):
    """From the brow to the ground, tapering. `drop` is how far down it
    reaches and `curl` swings the tip - the two together are the difference
    between an elephant standing still and one eating."""
    n = max(6, drop)
    for i in range(n):
        t = i / (n - 1)
        w = round(3 - t * 2)                          # it narrows to the tip
        px = round(x + math.sin(t * 1.6) * curl)
        py = y + i
        c.rect(px - w, py, px + w, py, key)
        c.set(px + w, py, "AFS")                      # a hard edge down one
        c.set(px - w, py, dark)                       # side, or it is a smudge
    return px, py


def _ear_side(c, x0, wide, top, deep, key, dark):
    """A flap hung off the skull: a straight top edge where it is attached, and
    a rounded bottom falling away behind. Drawn as a lens centred on the
    shoulder it came out an oval floating on the animal's side - a sticker, not
    an ear. What reads is the hanging: one edge attached, the rest loose. It
    also has to be a different tone from the shoulder it covers, or it
    disappears into it and an elephant without an ear is a grey pig."""
    for i in range(deep):
        t = i / (deep - 1)
        w = round(wide * (1 - t * t * 0.8))
        if w < 1:
            break
        c.rect(x0, top + i, x0 + w, top + i, key)
        c.set(x0 + w, top + i, "AFS")                 # the loose edge, hard
    c.row(x0, x0 + wide, top, "AFS")                  # the line it hangs from
    c.col(x0 + 3, top + 2, top + deep - 6, dark)      # and one fold down it


def _tusk(c, x, y, dx, n):
    for i in range(n):
        c.set(round(x + dx * i), round(y + i * 0.5 - (i * i) * 0.06), "HN")
        c.set(round(x + dx * i), round(y + 1 + i * 0.5 - (i * i) * 0.06), "HNS")


# ------------------------------------------------------------- side view ---
def draw_side(shape, pose):
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    swing = pose.get("legs", (0, 0, 0, 0))
    drop = pose.get("trunk_down", 0)

    # The far pair first, in shade, so the body covers where they join it.
    # Rear pair and front pair, with daylight between them: an elephant's legs
    # are close-set for its size, but not so close that the four of them are
    # one mass.
    _pillar(c, 17 + swing[1], 42 + bob, "ABS", "AFS")
    _pillar(c, 36 + swing[3], 42 + bob, "ABS", "AFS")

    back = 25 + bob
    c.rect(10, back + 2, 44, 48, "AB")                # the barrel
    c.row(12, 42, back, "AB")
    c.row(11, 43, back + 1, "AB")                     # corners off the back
    c.row(14, 40, back, "ABL")                        # lit along the spine
    c.row(11, 43, 48, "ABS")                          # and shaded underneath
    c.rect(8, back + 5, 11, back + 15, "ABS")         # the rump
    if shape.get("tail"):
        c.col(8, back + 7, back + 18, "AFS")
        c.rect(7, back + 18, 8, back + 20, "AFS")     # with a tuft on it

    _pillar(c, 11 + swing[0], 44 + bob, "AB", "ABS")  # and the near pair
    _pillar(c, 31 + swing[2], 44 + bob, "AB", "ABS")

    # The head, and the step up to it. The crown sits above the line of the
    # back - that step is the whole of an elephant in profile, and drawn level
    # with the barrel in the same tone the animal was one long grey brick with
    # a hose on the end of it.
    hy = 17 + bob
    c.rect(41, hy + 2, 56, 43, "AB")
    c.row(43, 54, hy, "AB")
    c.row(42, 55, hy + 1, "AB")
    c.row(45, 52, hy, "ABL")                          # the domed forehead, lit
    c.col(56, hy + 4, 40, "ABS")                      # the face falling away
    c.row(43, 55, 43, "ABS")                          # and the jaw under it
    if shape.get("ears"):
        # Hung off the skull and over the shoulder behind it, which is where
        # the join between head and body would otherwise show as a seam.
        _ear_side(c, 38, 13, hy + 4, 22, "ABS", "AFS")
    c.set(52, hy + 9, "OL")                           # the eye, small and high
    if shape.get("trunk"):
        tx, ty = _trunk(c, 54, hy + 20, 18 + drop, 2 + drop * 0.3, "AB", "ABS")
        c.set(tx, ty, "ABS")                          # the lip at the end
    if shape.get("tusks"):
        _tusk(c, 51, hy + 23, 1.1, 7)
    return c.outline()


# ------------------------------------------------------ front / back view ---
def _legs_front(c, spread, bob):
    _pillar(c, 16 - spread, 40 + bob, "ABS", "AFS")   # the far pair, inside
    _pillar(c, 38 + spread, 40 + bob, "ABS", "AFS")
    _pillar(c, 12 - spread, 42 + bob, "AB", "ABS")
    _pillar(c, 42 + spread, 42 + bob, "AB", "ABS")


def draw_front(shape, pose):
    """Head on, an elephant is two ears with an animal between them."""
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    drop = pose.get("trunk_down", 0)
    _legs_front(c, pose.get("spread", 0), bob)
    c.rect(14, 24 + bob, 50, 48, "AB")                # the body behind it all
    c.row(16, 48, 24 + bob, "ABL")

    hy = 18 + bob
    if shape.get("ears"):
        for side in (-1, 1):                          # one flap either side,
            for i in range(26):                       # rounded, rimmed dark
                y = hy - 2 + i
                w = round(9 * math.sin((i + 1) / 27 * math.pi) + 3)
                x0 = 31 + side * 10
                lo, hi = (x0 - w, x0) if side < 0 else (x0, x0 + w)
                c.rect(lo, y, hi, y, "AB")
                c.set(lo if side < 0 else hi, y, "AFS")
            c.col(x0, hy + 2, hy + 20, "ABS")         # the fold at the skull
    c.rect(22, hy, 41, hy + 26, "AB")                 # the skull
    c.row(24, 39, hy, "ABL")
    for y in range(hy + 4, hy + 12, 3):               # the wrinkles on it
        c.row(24, 39, y, "ABS")
    c.set(26, hy + 9, "OL")
    c.set(37, hy + 9, "OL")
    if shape.get("trunk"):
        _trunk(c, 31, hy + 14, 22 + drop, 0, "ABL", "AFS")   # lit, so it
        c.col(31, hy + 14, hy + 34 + drop, "AB")             # stands off the
    if shape.get("tusks"):
        _tusk(c, 27, hy + 20, -0.7, 8)
        _tusk(c, 36, hy + 20, 0.7, 8)
    return c.outline()


def draw_back(shape, pose):
    """Going away: rump, tail, and the ears flaring past the shoulders."""
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    _legs_front(c, pose.get("spread", 0), bob)
    if shape.get("ears"):
        # Out past the body, drawn first so the rump covers where they attach.
        # Tucked inside its edges and in a tone a step off it, they showed six
        # pixels each and the animal going away was a grey crate.
        for side, x0 in ((-1, 14), (1, 50)):
            for i in range(17):
                y = 21 + bob + i
                w = round(8 * math.sin((i + 1) / 18 * math.pi) + 2)
                lo, hi = (x0 - w, x0) if side < 0 else (x0, x0 + w)
                c.rect(lo, y, hi, y, "ABS")
                c.set(lo if side < 0 else hi, y, "AFS")
    c.rect(14, 21 + bob, 50, 48, "AB")                # the rump
    c.row(16, 48, 20 + bob, "AB")                     # domed over, not flat:
    c.row(19, 45, 19 + bob, "AB")                     # a straight top edge is
    c.row(22, 42, 19 + bob, "ABL")                    # a box seen end on
    c.row(15, 49, 48, "ABS")
    for i, y in enumerate(range(28 + bob, 46, 5)):    # hide folds, staggered -
        c.row(18 + (i % 2) * 4, 46 - (i % 2) * 4, y, "ABS")   # drawn the full
    c.col(32, 22 + bob, 46, "ABS")                    # width they were seams
    if shape.get("tail"):
        c.rect(31, 26 + bob, 33, 44, "ABS")
        c.rect(30, 44, 34, 47, "AFS")                 # the tuft
    return c.outline()


# ----------------------------------------------------------------- poses ----
WALK = [
    dict(bob=0, legs=(2, -2, -2, 2), spread=1),
    dict(bob=-1, legs=(0, 0, 0, 0), spread=0),
    dict(bob=0, legs=(-2, 2, 2, -2), spread=1),
    dict(bob=-1, legs=(0, 0, 0, 0), spread=0),
]
IDLE = [
    dict(bob=0, legs=(0, 0, 0, 0), spread=0, trunk_down=0),
    dict(bob=-1, legs=(0, 0, 0, 0), spread=0, trunk_down=1),
]
GRAZE = [                       # the trunk down, feeling about
    dict(bob=0, legs=(0, 0, 0, 0), spread=1, trunk_down=5),
    dict(bob=0, legs=(0, 0, 0, 0), spread=1, trunk_down=7),
]
STATES = {"walk": (WALK, 220, True), "idle": (IDLE, 700, True),
          "graze": (GRAZE, 520, True)}
STATE_ORDER = ["walk", "idle", "graze"]


def states_for(states=None, held=None):
    """Same contract as every other rig. Nothing this size holds anything, so
    `held` is accepted and ignored rather than being a special case."""
    return [s for s in STATE_ORDER if s in (states or STATE_ORDER)]


def draw_shadow():
    c = Canvas(FRAME, FRAME)
    c.row(12, 52, GROUND_Y, "SH")
    c.row(16, 48, GROUND_Y + 1, "SH")
    return c


def build_frames(species="elephant", states=None, held=None, worn=None):
    """[(state, facing, i, cel, shadow, ms, loops), ...] - every rig's shape."""
    shape = SPECIES[species]
    frames = []
    for facing in FACINGS:
        for state in states_for(states, held):
            poses, ms, loops = STATES[state]
            for i, pose in enumerate(poses):
                if facing in ("left", "right"):
                    cel = draw_side(shape, pose)
                    if facing == "left":
                        cel = cel.mirrored()
                elif facing == "down":
                    cel = draw_front(shape, pose)
                else:
                    cel = draw_back(shape, pose)
                frames.append((state, facing, i, cel, draw_shadow(), ms, loops))
    return frames
