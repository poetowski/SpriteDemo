"""Parametric giant rig: a bipedal monster three tiles tall, two tiles wide.

Same contract as the biped and quadruped rigs - four facings, feet on
GROUND_Y, one exported anchor, the same build_frames shape - but drawn in a
64x64 frame, because a creature 48px tall does not fit in the 32x32 one the
people and the livestock share. That is the only difference the pipeline sees:
the rig names the sheet it belongs on, and tools/art.py gives each actor frame
size a sheet of its own rather than padding every hero frame out to the size
of the largest thing in the game.

Two tiles wide is an even tile count, and an even count has no middle tile, so
the anchor cannot sit at both the frame centre and a tile centre. It sits at a
tile centre (x=24), like the 64x64 props, and the art is drawn centred in the
frame - which means the sprite covers tile offsets 0 and +1, and a definition
that blocks says so with a two-tile footprint. The belly is the two tiles; the
arms hang past them the way a canopy hangs past a trunk.

A species is a set of silhouette flags plus a palette variant, so a second
monster on this rig is a remap and a flag rather than a second set of art.
The gas is drawn after the outline and only where nothing else is: it is the
one translucent thing on the sprite, and a cloud painted over the belly would
show the grass through him.
"""

from gen.palette import Canvas

FRAME = 64
GROUND_Y = 61                  # the row the feet stand on
ANCHOR = (24, GROUND_Y)        # a tile centre: the art covers offsets 0 and +1
ATLAS = "actors_huge"          # the 64px actor sheet, as props_huge is for props
COLS = 4

FACINGS = ["down", "left", "right", "up"]

CX = 31                        # rows span CX-w .. CX+1+w, so centred on x=32
HEAD_TOP = 13                  # 48px of monster: three tiles, crown to sole
SHOULDER_Y = 24                # the head's jowls overlap this: no neck
HIP_Y = 46
FOOT_Y = 60                    # last opaque row

# Silhouette flags, read with .get so a new one leaves the others alone.
SPECIES = {
    "troll": {"tusks": True, "gas": True},
}

# The mass, row by row from the shoulders down: half-widths of something that
# is narrow across the shoulders and widest at the gut. Written out rather
# than tapered, because the shape of the belly is the character.
TORSO = [9, 10, 11, 11, 12, 12, 12, 12, 12, 12, 12, 12,
         12, 12, 11, 11, 10, 10, 9, 9, 8, 8, 7]
# The skull: narrow over the top and widest at the jaw, and smaller than the
# shoulders it is sunk between - which is what makes the shoulders read as
# huge rather than the head as small.
HEAD = [4, 6, 7, 7, 8, 8, 8, 8, 8, 8, 7, 6, 4]

# Gas, per frame of a state: clouds that rise and thin as the cycle runs. The
# phase is the frame index, so a troll standing still still stinks.
GAS_FRONT = [
    [(11, 50, 4), (52, 46, 3), (17, 35, 2)],
    [(10, 45, 3), (53, 41, 2), (15, 30, 2), (48, 54, 4)],
    [(12, 39, 2), (51, 36, 2), (9, 52, 4)],
    [(9, 33, 2), (54, 50, 4), (14, 44, 3)],
]
GAS_SIDE = [                   # behind him, which is the way he came
    [(12, 49, 4), (5, 41, 3), (19, 32, 2)],
    [(10, 43, 3), (4, 34, 2), (16, 52, 4)],
    [(13, 37, 2), (6, 48, 4), (8, 28, 2)],
    [(9, 45, 3), (14, 33, 2), (3, 39, 3)],
]
GAS_BACK = [                   # face to face with the source of it
    [(18, 52, 4), (46, 48, 3), (31, 55, 3)],
    [(15, 46, 3), (49, 43, 2), (25, 38, 2)],
    [(20, 40, 2), (44, 36, 2), (33, 48, 4)],
    [(14, 37, 2), (50, 52, 4), (27, 44, 3)],
]


# --------------------------------------------------------------- helpers ---
def _shade(c, key, light, dark):
    """Rim-light a mass from its own silhouette: lit where it faces up-left,
    shaded where it faces down-right. Derived rather than painted by hand, so
    the shading cannot end up outside the shape it is shading."""
    for y in range(c.h):
        for x in range(c.w):
            if c.px[y][x] != key:
                continue
            if c.get(x - 1, y) is None or c.get(x, y - 1) is None:
                c.px[y][x] = light
            elif c.get(x + 1, y) is None or c.get(x, y + 1) is None:
                c.px[y][x] = dark


def _rows(c, y0, widths, key, cx=CX, dx=0):
    """A stack of centred rows - one half-width per row."""
    for i, w in enumerate(widths):
        c.row(cx - w + dx, cx + 1 + w + dx, y0 + i, key)


def _lobe(c, cx, cy, r, key, only=None):
    """A filled disc. With `only`, it repaints an existing mass instead of
    adding to the silhouette - which is how volume gets painted without any
    risk of putting pixels outside the shape."""
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 > r * r:
                continue
            if only is None or c.get(x, y) == only:
                c.set(x, y, key)


def _limb(c, x0, y0, x1, y1, key="SK", edge="SKS"):
    """A mass with an edge of its own, for a limb drawn over the body: the
    outline pass only wraps the silhouette, so an arm in front of the belly
    would otherwise be a shape of exactly the same green on green. A rim of
    the shade colour, not the outline - a black line through the middle of him
    reads as a crack, not as an arm."""
    c.rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1, edge)
    c.rect(x0, y0, x1, y1, key)


def _arm_side(c, spans, y0, edge="OL"):
    """An arm given as one (x0, x1) span per row, then edged from those spans.
    In profile the arm hangs over the gut rather than beside it, so it has no
    silhouette edge of its own and the outline pass cannot give it one."""
    for i, (x0, x1) in enumerate(spans):
        c.row(x0, x1, y0 + i, "SK")
    for i, (x0, x1) in enumerate(spans):
        c.set(x0, y0 + i, edge)
        c.set(x1, y0 + i, edge)
    c.row(spans[0][0], spans[0][1], y0, edge)
    c.row(spans[-1][0], spans[-1][1], y0 + len(spans) - 1, edge)


def _fist(c, cx, cy, r, edge="SKS"):
    """A fist: a rimmed mass, lit across the top and knuckled underneath, so
    it reads as a fist rather than as a ring on the end of an arm."""
    _lobe(c, cx, cy, r + 1, edge)
    _lobe(c, cx, cy, r, "SK")
    _lobe(c, cx - 1, cy - 1, r - 2, "SKL", only="SK")
    for x in range(cx - r + 2, cx + r - 1, 2):
        c.set(x, cy + 1, "SKS")


def _puff(c, cx, cy, r):
    """One cloud of gas: overlapping lobes, painted only where nothing else
    is. A single disc reads as a bubble; a lumpy one reads as a smell."""
    for ox, oy, rr in ((0, 0, r), (-r, 1, r - 1), (r - 1, -2, r - 2),
                       (1, r - 1, r - 2)):
        if rr <= 0:
            continue
        for y in range(cy + oy - rr, cy + oy + rr + 1):
            for x in range(cx + ox - rr, cx + ox + rr + 1):
                d = (x - cx - ox) ** 2 + (y - cy - oy) ** 2
                if d > rr * rr or c.get(x, y) is not None:
                    continue
                c.set(x, y, "GSL" if d <= max(0, rr - 2) ** 2 else "GS")


def _gas(c, table, phase):
    for cx, cy, r in table[phase % len(table)]:
        _puff(c, cx, cy, r)


# ------------------------------------------------------------- front view ---
def _legs_front(c, bob, leg):
    """Two stumps under the gut. `leg` lifts one heel, which is all a walk
    needs on legs this short - anything more and the belly starts hopping."""
    lift_l, lift_r = {0: (0, 0), 1: (0, 2), -1: (2, 0)}[leg]
    for x0, x1, lift, out in ((20, 29, lift_l, -2), (34, 43, lift_r, 2)):
        foot = FOOT_Y - lift
        c.rect(x0, HIP_Y + bob, x1, foot - 3, "SK")
        fx0, fx1 = (x0 + out, x1) if out < 0 else (x0, x1 + out)
        c.rect(fx0, foot - 2, fx1, foot, "SK")       # the foot turns out
        for i in range(3):
            c.set(fx0 + 1 + i * 3, foot, "BT")       # toenails


def _torso_front(c, bob):
    _rows(c, SHOULDER_Y + bob, TORSO, "SK")
    for side in (-1, 1):                             # shoulders, rounded out to
        _lobe(c, 19 if side < 0 else 44, 29 + bob, 6, "SK")   # meet the arms
    _lobe(c, 24, 35 + bob, 10, "SKL", only="SK")     # the gut catches the light
    _lobe(c, 39, 41 + bob, 8, "SKS", only="SK")      # and falls away under it
    c.row(25, 38, 31 + bob, "SKS")                   # the crease under a chest
    c.row(27, 36, 32 + bob, "SKS")                   # that rests on the gut
    c.rect(31, 38 + bob, 32, 39 + bob, "SKS")        # navel
    c.set(31, 39 + bob, "OL")


def _skirt_front(c, bob):
    """A hide slung round the waist, hanging in tatters over the thighs."""
    y = 43 + bob
    c.rect(19, y, 44, y + 5, "TU")
    c.row(19, 44, y, "TUL")
    c.row(19, 44, y + 5, "TUS")
    for x in (21, 28, 35, 41):                       # the tatters
        c.rect(x, y + 6, x + 3, y + 7, "TU")
        c.row(x, x + 3, y + 7, "TUS")
    c.rect(29, y - 1, 34, y + 1, "BT")               # a knot of strapping
    c.row(29, 34, y - 1, "BTS")


def _arm_front(c, side, bob, swing, punch, back=False):
    """One hanging arm, hung outside the gut where it can be seen and angled in
    towards the hip, so the widest thing about him is his shoulders. side is -1
    for screen left, +1 for screen right; the right one throws the punch, and
    face on that means a fist coming at you rather than an arm swinging across,
    and from behind it means one going away.
    """
    off = (-1 if swing * side > 0 else (1 if swing else 0))
    if side > 0 and punch:
        if punch > 0 and back:                       # thrown away from us
            c.rect(43, 24 + bob, 47, 35 + bob, "SK")
            _lobe(c, 45, 22 + bob, 4, "SK")
            c.row(42, 48, 21 + bob, "SKS")
            return
        if punch > 0:                                # thrown at the camera
            c.rect(43, 29 + bob, 48, 36 + bob, "SK")         # upper arm
            _limb(c, 38, 35 + bob, 46, 41 + bob, edge="OL")  # forearm, short
            _fist(c, 36, 41 + bob, 5, edge="OL")             # and a fist, near
            return
        c.rect(44, 26 + bob, 48, 33 + bob, "SK")             # wound up, high
        _lobe(c, 47, 35 + bob, 4, "SK")
        c.row(44, 50, 34 + bob, "SKS")
        return
    top = 27 + bob + off
    lean = -1 if side < 0 else 1                     # the arm comes in as it
    x0 = 14 if side < 0 else 45                      # drops, like a gorilla's
    seam = x0 + (4 if side < 0 else 0)               # the side against the gut
    c.rect(x0, top, x0 + 4, top + 9, "SK")
    c.rect(x0 + lean, top + 9, x0 + 4 + lean, top + 15, "SK")
    _lobe(c, x0 + 2 + lean, top + 17, 3, "SK")       # the fist, hanging low
    # Where the arm lies against the gut there is nothing between them but a
    # change of green, so the seam is drawn as outline: at this size a shade
    # colour is not enough to tell an arm from the belly behind it.
    c.col(seam, top + 4, top + 9, "OL")
    c.col(seam + lean, top + 9, top + 16, "OL")
    c.col(seam - lean, top, top + 4, "SKS")


def _head_front(c, bob, shape):
    t = HEAD_TOP + bob
    _rows(c, t, HEAD, "SK")
    c.rect(22, t + 4, 23, t + 6, "SK")               # ears, small on a big skull
    c.rect(40, t + 4, 41, t + 6, "SK")
    _lobe(c, 28, t + 3, 4, "SKL", only="SK")         # light on a bald crown
    c.row(24, 39, t + 4, "SKS")                      # brow ridge, jutting
    c.rect(26, t + 5, 27, t + 6, "OL")               # small eyes under it
    c.rect(36, t + 5, 37, t + 6, "OL")
    c.rect(30, t + 6, 33, t + 8, "SKS")              # snout
    c.set(30, t + 8, "OL")
    c.set(33, t + 8, "OL")
    c.row(26, 37, t + 9, "OL")                       # the maw
    c.row(27, 36, t + 10, "OL")
    if shape.get("tusks"):
        for x in (28, 34):
            c.rect(x, t + 8, x + 1, t + 9, "HN")
            c.set(x + 1, t + 9, "HNS")


def draw_front(shape, pose):
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    _legs_front(c, bob, pose.get("leg", 0))
    _torso_front(c, bob)
    _skirt_front(c, bob)
    for side in (-1, 1):
        _arm_front(c, side, bob, pose.get("swing", 0), pose.get("punch", 0))
    _head_front(c, bob, shape)
    _shade(c, "SK", "SKL", "SKS")
    c.outline()
    if shape.get("gas"):
        _gas(c, GAS_FRONT, pose.get("phase", 0))
    return c


# -------------------------------------------------------------- back view ---
def draw_back(shape, pose):
    """Facing away: all back and no face, which is also the view you get of
    the gas - so this is the one that has to be funny rather than frightening."""
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    _legs_front(c, bob, pose.get("leg", 0))
    _rows(c, SHOULDER_Y + bob, TORSO, "SK")
    _lobe(c, 24, 31 + bob, 11, "SKL", only="SK")     # the light across his back
    _lobe(c, 40, 40 + bob, 9, "SKS", only="SK")
    for cx in (25, 38):                              # shoulder blades
        _lobe(c, cx, 30 + bob, 4, "SKS", only="SK")
        _lobe(c, cx - 1, 29 + bob, 3, "SK", only="SKS")
    c.col(CX, SHOULDER_Y + 4 + bob, 40 + bob, "SKS")         # the spine
    c.row(25, 38, 37 + bob, "SKS")                   # and a roll of fat across
    _skirt_front(c, bob)
    for side in (-1, 1):
        _arm_front(c, side, bob, pose.get("swing", 0), pose.get("punch", 0),
                   back=True)
    t = HEAD_TOP + bob
    _rows(c, t, HEAD, "SK")
    c.rect(22, t + 4, 23, t + 6, "SK")
    c.rect(40, t + 4, 41, t + 6, "SK")
    _lobe(c, 28, t + 3, 4, "SKL", only="SK")
    c.row(26, 37, t + 10, "SKS")                     # the fold where the skull
    c.row(27, 36, t + 11, "SKS")                     # meets a neck that is not
    _shade(c, "SK", "SKL", "SKS")
    c.outline()
    if shape.get("gas"):
        _gas(c, GAS_BACK, pose.get("phase", 0))
    return c


# -------------------------------------------------------------- side view ---
# In profile the mass leads with the gut and trails a rump, so the rows are
# given as spans rather than half-widths: an egg tipped forward.
SIDE = [(26, 40), (24, 42), (23, 44), (22, 45), (21, 46), (20, 47), (19, 47),
        (18, 48), (18, 48), (17, 48), (17, 48), (17, 48), (17, 47), (17, 47),
        (18, 46), (18, 45), (19, 44), (20, 43), (21, 42), (22, 41), (23, 40),
        (24, 39), (25, 38)]


def _legs_side(c, bob, leg):
    """Near leg and far leg; the far one stays in shade so the two read apart
    even when they pass each other."""
    near_x = 30 + 3 * leg
    far_x = 24 - 3 * leg
    for x, key, nail in ((far_x, "SKS", "BTS"), (near_x, "SK", "BT")):
        c.rect(x, HIP_Y + bob, x + 8, FOOT_Y - 3, key)
        c.rect(x, FOOT_Y - 2, x + 11, FOOT_Y, key)   # the foot points the way
        for i in range(3):                           # he is going
            c.set(x + 5 + i * 2, FOOT_Y, nail)


def draw_side(shape, pose):
    """Profile facing +x: the gut goes in front, the rump and the smell behind."""
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    punch = pose.get("punch", 0)
    _legs_side(c, bob, pose.get("leg", 0))
    for i, (x0, x1) in enumerate(SIDE):
        c.row(x0, x1, SHOULDER_Y + bob + i, "SK")
    _lobe(c, 24, 32 + bob, 10, "SKL", only="SK")     # lit along the back
    _lobe(c, 43, 40 + bob, 9, "SKS", only="SK")      # the gut falls into shade
    _lobe(c, 21, 42 + bob, 6, "SKS", only="SK")      # and so does the rump

    c.rect(21, 42 + bob, 46, 47 + bob, "TU")         # the hide, side on
    c.row(21, 46, 42 + bob, "TUL")
    c.row(21, 46, 47 + bob, "TUS")
    for x in (24, 31, 38):
        c.rect(x, 48 + bob, x + 3, 49 + bob, "TU")
        c.row(x, x + 3, 49 + bob, "TUS")

    t = HEAD_TOP + bob
    _rows(c, t, HEAD, "SK", dx=5)                    # the skull, carried forward
    for i, (x0, x1) in enumerate(((29, 47), (29, 48), (30, 48),
                                  (31, 47), (32, 45))):
        c.row(x0, x1, t + 6 + i, "SK")               # the jaw leads, not a beak
    _lobe(c, 33, t + 3, 4, "SKL", only="SK")
    c.row(38, 46, t + 4, "SKS")                      # brow
    c.rect(41, t + 5, 42, t + 6, "OL")               # eye
    c.set(47, t + 7, "OL")                           # nostril
    c.row(38, 48, t + 8, "OL")                       # the maw, side on
    c.rect(29, t + 3, 31, t + 6, "SK")               # the near ear
    if shape.get("tusks"):
        c.rect(44, t + 7, 45, t + 8, "HN")
        c.set(45, t + 8, "HNS")

    # The near arm, which in profile hangs over the body and so is drawn with
    # an edge of its own: hanging, wound up, or thrown straight out in front of
    # him - the frame the blow lands on, so it has to read across the screen.
    if punch > 0:
        _arm_side(c, [(34, 50)] * 6, 32 + bob)       # straight out in front
        _fist(c, 52, 35 + bob, 5, edge="OL")
    elif punch < 0:
        _arm_side(c, [(20, 34)] * 6, 31 + bob)       # drawn back behind him
        _fist(c, 18, 34 + bob, 5, edge="OL")
    else:
        sw = pose.get("swing", 0)
        spans = [(31 + i // 4 + sw, 36 + i // 4 + sw) for i in range(16)]
        spans += [(33 + sw, 39 + sw)] * 3            # and a fist on the end
        _arm_side(c, spans, 29 + bob)
    _shade(c, "SK", "SKL", "SKS")
    c.outline()
    if shape.get("gas"):
        _gas(c, GAS_SIDE, pose.get("phase", 0))
    return c


# ------------------------------------------------------------------ shadow ---
def draw_shadow(squash=0):
    c = Canvas(FRAME, FRAME)
    y = GROUND_Y
    c.row(18 + squash, 45 - squash, y, "SH")
    c.row(22 + squash, 41 - squash, y + 1, "SH")
    return c


# --------------------------------------------------------------- timeline ---
# Slow all the way through: a heavy thing that has to shift its own weight is
# the whole read, and it is also what makes the punch something you can walk
# out of rather than something that simply happens to you.
WALK = [
    dict(bob=0, leg=1, swing=-1, squash=0),
    dict(bob=-1, leg=0, swing=0, squash=1),
    dict(bob=0, leg=-1, swing=1, squash=0),
    dict(bob=-1, leg=0, swing=0, squash=1),
]
IDLE = [
    dict(bob=0, leg=0, swing=0, squash=0),
    dict(bob=-1, leg=0, swing=0, squash=0),
]
ATTACK = [                     # wind up, throw, hold, drop the arm
    dict(bob=-1, leg=0, swing=0, punch=-1, squash=0),
    dict(bob=1, leg=0, swing=0, punch=1, squash=1),
    dict(bob=1, leg=0, swing=0, punch=1, squash=1),
    dict(bob=0, leg=0, swing=0, punch=0, squash=0),
]
STATES = {"walk": (WALK, 230, True), "idle": (IDLE, 620, True),
          "attack": (ATTACK, 170, False)}
STATE_ORDER = ["walk", "idle", "attack"]


def states_for(states=None, held=None):
    """Same contract as the other rigs. A giant holds nothing - its fists are
    the weapon - so `held` is accepted and ignored rather than being a special
    case in the pipeline."""
    return [s for s in STATE_ORDER if s in (states or STATE_ORDER)]


def build_frames(species="troll", states=None, held=None, worn=None):
    """[(state, facing, i, cel, shadow, ms, loops), ...] - the biped's shape."""
    shape = SPECIES[species]
    frames = []
    for facing in FACINGS:
        for state in states_for(states, held):
            poses, ms, loops = STATES[state]
            for i, pose in enumerate(poses):
                pose = dict(pose, phase=i)
                if facing in ("left", "right"):
                    cel = draw_side(shape, pose)
                    if facing == "left":
                        cel = cel.mirrored()
                elif facing == "down":
                    cel = draw_front(shape, pose)
                else:
                    cel = draw_back(shape, pose)
                frames.append((state, facing, i, cel,
                               draw_shadow(pose.get("squash", 0)), ms, loops))
    return frames
