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

from gen.palette import Canvas, scatter

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
    # A giraffe is the same rig used at its other extreme: the mass is in the
    # legs and the neck rather than in the barrel, so "neck" does not add a
    # part to the elephant's body - it replaces the proportions entirely. It
    # is still the same frame, the same anchor, the same sheet and the same
    # build_frames, which is the whole of what a rig is.
    "giraffe": {"neck": True, "ossicones": True, "patches": True,
                "tail": True, "legs_long": True},
}


# --------------------------------------------------------------- helpers ---
def _pillar(c, x, top, key, dark, w=7, foot="AH", nails=True):
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
    if nails:
        for i in range(3):
            c.set(x + 1 + i * 2, FOOT_Y - 1, "ABL")  # toenails
    else:
        c.col(x + w // 2, FOOT_Y - 2, FOOT_Y, key)   # or a cloven hoof, split
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


def _patches(c, seed, x0, y0, x1, y1, on="AB", key="ABS"):
    """The coat, as blobs of the shade key laid only over pixels that are
    already the body tone - so a patch cannot spill off the animal onto the
    background, which is the same rule as shading inside the silhouette and
    just as easy to get wrong when the shape is this irregular."""
    rnd = scatter(0x6C1F + seed * 733)
    for _ in range((x1 - x0) * (y1 - y0) // 26):
        px, py, r = x0 + rnd(x1 - x0), y0 + rnd(y1 - y0), 1 + rnd(2)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if abs(dx) + abs(dy) > r:
                    continue
                x, y = px + dx, py + dy
                if 0 <= x < FRAME and 0 <= y < FRAME and c.px[y][x] == on:
                    c.set(x, y, key)


def _neck(c, shape, x0, y0, x1, y1, w):
    """Shoulder to skull in a straight run, lit down one side. Drawn as a
    column it read as a chimney: a neck is a line with a thickness, and the
    lean is what says which way the animal is looking."""
    n = max(abs(x1 - x0), abs(y1 - y0))
    for i in range(n + 1):
        t = i / n
        x = round(x0 + (x1 - x0) * t)
        y = round(y0 + (y1 - y0) * t)
        c.rect(x - w, y, x + w, y, "AB")
        c.set(x - w, y, "ABS")
        c.set(x + w, y, "ABL")
        if i % 3 == 0:                                # the mane, in bristles
            c.set(x - w - 1, y, "AFS")


def _tusk(c, x, y, dx, n):
    for i in range(n):
        c.set(round(x + dx * i), round(y + i * 0.5 - (i * i) * 0.06), "HN")
        c.set(round(x + dx * i), round(y + 1 + i * 0.5 - (i * i) * 0.06), "HNS")


# --------------------------------------------------------------- giraffe ---
def _giraffe_side(shape, pose):
    """All the height is in the legs and the neck, and the barrel between them
    is short and slopes down to the rump - which is the one proportion that
    stops a tall quadruped reading as a horse."""
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    swing = pose.get("legs", (0, 0, 0, 0))
    down = pose.get("head_down", 0)

    _pillar(c, 18 + swing[1], 30 + bob, "ABS", "AFS", w=4, nails=False)
    _pillar(c, 34 + swing[3], 27 + bob, "ABS", "AFS", w=4, nails=False)

    # The barrel: shallow, and higher at the shoulder than at the rump. Most
    # of a giraffe is leg and neck, and drawn as deep as an elephant's the
    # whole animal came out a tall horse with a crane on the front.
    top = 24 + bob
    c.rect(16, top + 2, 42, 35, "AB")
    c.row(18, 40, top + 1, "AB")
    for i in range(6):                                # the back falls away
        c.row(18 + i * 4, 42, top + 2 - i // 2, "AB")
    c.row(30, 41, top, "ABL")
    c.row(17, 41, 35, "ABS")
    c.rect(14, top + 5, 17, 33, "ABS")                # the rump
    if shape.get("tail"):
        c.col(15, 30 + bob, 43, "AFS")
        c.rect(14, 43, 16, 46, "AFS")                 # with a tuft on it

    _pillar(c, 16 + swing[0], 32 + bob, "AB", "ABS", w=4, nails=False)
    _pillar(c, 32 + swing[2], 29 + bob, "AB", "ABS", w=4, nails=False)

    hy = 8 + bob + down
    _neck(c, shape, 40, top + 2, 49, hy + 3, 3)
    c.rect(47, hy, 55, hy + 6, "AF")                  # the head, small
    c.row(48, 54, hy, "ABL")
    c.rect(54, hy + 3, 58, hy + 6, "AF")              # and the muzzle on it
    c.row(54, 58, hy + 6, "AFS")
    c.set(52, hy + 2, "OL")                           # the eye
    c.rect(45, hy + 1, 46, hy + 3, "AF")              # an ear behind it
    c.set(45, hy + 1, "AFS")
    if shape.get("ossicones"):
        for x in (49, 53):                            # two knobs, not horns:
            c.col(x, hy - 3, hy - 1, "HN")            # blunt, and they end in
            c.set(x, hy - 3, "HNS")                   # a tuft rather than a tip
    if shape.get("patches"):
        _patches(c, 1, 14, top, 43, 36)
        _patches(c, 2, 38, hy + 2, 50, top + 3)
    return c.outline()


def _giraffe_front(shape, pose):
    """Head on it is a neck with an animal hanging off the bottom."""
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    down = pose.get("head_down", 0)
    spread = pose.get("spread", 0)
    _pillar(c, 25 - spread, 28 + bob, "ABS", "AFS", w=3, nails=False)
    _pillar(c, 34 + spread, 28 + bob, "ABS", "AFS", w=3, nails=False)
    _pillar(c, 22 - spread, 30 + bob, "AB", "ABS", w=3, nails=False)
    _pillar(c, 37 + spread, 30 + bob, "AB", "ABS", w=3, nails=False)

    c.rect(24, 25 + bob, 39, 34, "AB")                # a narrow chest
    c.row(26, 37, 24 + bob, "AB")
    c.row(28, 35, 24 + bob, "ABL")

    hy = 8 + bob + down
    c.rect(28, hy + 4, 35, 27 + bob, "AB")            # the neck, straight up
    c.col(28, hy + 4, 27 + bob, "ABS")
    c.col(35, hy + 4, 27 + bob, "ABL")
    c.rect(27, hy, 36, hy + 6, "AF")                  # the head
    c.row(29, 34, hy, "ABL")
    c.rect(29, hy + 5, 34, hy + 8, "AF")              # muzzle
    c.row(29, 34, hy + 8, "AFS")
    c.set(28, hy + 2, "OL")
    c.set(35, hy + 2, "OL")
    c.rect(24, hy + 1, 26, hy + 2, "AF")              # ears out to the sides
    c.rect(37, hy + 1, 39, hy + 2, "AF")
    if shape.get("ossicones"):
        for x in (29, 34):
            c.col(x, hy - 3, hy - 1, "HN")
            c.set(x, hy - 3, "HNS")
    if shape.get("patches"):
        _patches(c, 3, 24, 24 + bob, 40, 35)
        _patches(c, 4, 28, hy + 6, 36, 27 + bob)
    return c.outline()


def _giraffe_back(shape, pose):
    """Going away: the rump is the narrow end, and the neck still towers."""
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    spread = pose.get("spread", 0)
    _pillar(c, 25 - spread, 28 + bob, "ABS", "AFS", w=3, nails=False)
    _pillar(c, 34 + spread, 28 + bob, "ABS", "AFS", w=3, nails=False)
    _pillar(c, 22 - spread, 30 + bob, "AB", "ABS", w=3, nails=False)
    _pillar(c, 37 + spread, 30 + bob, "AB", "ABS", w=3, nails=False)

    c.rect(24, 24 + bob, 39, 34, "AB")
    c.row(26, 37, 23 + bob, "AB")
    c.row(28, 35, 23 + bob, "ABL")
    c.row(25, 38, 34, "ABS")

    hy = 8 + bob
    c.rect(28, hy + 4, 35, 25 + bob, "AB")            # the neck
    c.col(28, hy + 4, 25 + bob, "ABS")
    c.rect(28, hy, 35, hy + 5, "AF")                  # the back of the skull
    c.row(29, 34, hy, "ABL")
    c.rect(25, hy + 1, 27, hy + 2, "AF")
    c.rect(36, hy + 1, 38, hy + 2, "AF")
    if shape.get("ossicones"):
        for x in (29, 34):
            c.col(x, hy - 3, hy - 1, "HN")
            c.set(x, hy - 3, "HNS")
    if shape.get("tail"):
        c.col(31, 30 + bob, 43, "AFS")
        c.rect(30, 43, 32, 46, "AFS")
    if shape.get("patches"):
        _patches(c, 5, 24, 23 + bob, 40, 35)
        _patches(c, 6, 28, hy + 5, 36, 25 + bob)
    return c.outline()


# ------------------------------------------------------------- side view ---
def draw_side(shape, pose):
    if shape.get("neck"):
        return _giraffe_side(shape, pose)
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
    if shape.get("neck"):
        return _giraffe_front(shape, pose)
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
    if shape.get("neck"):
        return _giraffe_back(shape, pose)
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
GRAZE = [                       # the trunk down, feeling about - and for an
    # animal with a neck instead, the whole head going with it. Both keys live
    # in the same pose and each rig reads only its own with .get, so adding
    # the second changed nothing about the elephant.
    dict(bob=0, legs=(0, 0, 0, 0), spread=1, trunk_down=5, head_down=14),
    dict(bob=0, legs=(0, 0, 0, 0), spread=1, trunk_down=7, head_down=17),
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
