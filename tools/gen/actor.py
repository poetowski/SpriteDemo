"""Parametric character rig: 4 facings, walk + idle + gather + slash.

Drawn at 64x64. Not the old 32x32 art doubled - at twice the size the face has
room for brows, a white in the eye and a mouth, the tunic gets a collar and a
buckle, boots get a cuff, and a sword gets a fuller and a pommel instead of
being a two-pixel line.

Every frame is composed by the same body part functions; only pose parameters
(bob, leg phase, arm swing, reach) change, so a character cannot drift between
facings or states. The hips follow the bob while the feet stay on a fixed
ground line, so legs stretch by a pixel instead of the sprite hopping.

ANCHOR is the point that sits on a map tile - exported into the atlas so the
engine never guesses where the feet are.
"""

from gen.palette import Canvas

FRAME = 64
GROUND_Y = 58                 # the row the feet stand on
ANCHOR = (32, GROUND_Y)

FACINGS = ["down", "left", "right", "up"]

# Anatomy, in frame pixels, for bob == 0. The body is symmetric about the
# x=31/32 boundary.
HEAD_TOP = 8
NECK_Y = 26
TORSO_TOP = 28
BELT_Y = 43
HIP_Y = 46
FOOT_Y = 57                   # last boot row

LEG_L = (24, 30)
LEG_R = (33, 39)
ARM_L = 17                    # outer column of the left sleeve
ARM_R = 42


# ------------------------------------------------------------- body parts ---
def head_front(c, dy=0):
    t = HEAD_TOP + dy
    c.row(26, 37, t, "HRL")                       # crown
    c.row(24, 39, t + 1, "HRL")
    c.row(23, 40, t + 2, "HR")
    c.rect(22, t + 3, 41, t + 6, "HR")            # the mass of the hair
    c.row(25, 33, t + 2, "HRL")                   # light down one side
    c.row(24, 31, t + 3, "HRL")
    c.row(22, 41, t + 7, "HR")                    # fringe, cut straight

    c.rect(22, t + 8, 25, t + 12, "HR")           # hair falls past the temples
    c.rect(38, t + 8, 41, t + 12, "HR")
    c.rect(26, t + 8, 37, t + 16, "SK")           # the face
    c.rect(24, t + 10, 25, t + 15, "SK")
    c.rect(38, t + 10, 39, t + 15, "SK")
    c.col(23, t + 10, t + 14, "SKS")              # cheeks turn away at the edge
    c.col(40, t + 10, t + 14, "SKS")

    c.row(26, 29, t + 9, "HR")                    # brows
    c.row(34, 37, t + 9, "HR")
    c.rect(26, t + 11, 29, t + 12, "EW")          # eyes: white, then the pupil
    c.rect(34, t + 11, 37, t + 12, "EW")
    c.rect(27, t + 11, 28, t + 12, "EY")
    c.rect(35, t + 11, 36, t + 12, "EY")

    c.col(31, t + 13, t + 14, "SKS")              # nose
    c.set(32, t + 14, "SKS")
    c.row(29, 34, t + 16, "SKS")                  # mouth
    c.row(27, 36, t + 17, "SKS")                  # jaw
    c.row(29, 34, t + 18, "SKS")                  # chin
    c.rect(28, NECK_Y + dy, 35, NECK_Y + dy + 1, "SKS")


def head_back(c, dy=0):
    t = HEAD_TOP + dy
    c.row(26, 37, t, "HRL")
    c.row(24, 39, t + 1, "HRL")
    c.rect(22, t + 2, 41, t + 15, "HR")
    c.row(25, 34, t + 2, "HRL")                   # the crown catches the light
    c.row(24, 32, t + 3, "HRL")
    c.col(31, t + 4, t + 14, "HRL")               # a parting down the back
    c.col(32, t + 4, t + 14, "HRD")
    c.row(24, 39, t + 16, "HR")
    c.row(27, 36, t + 17, "HR")                   # the nape
    c.rect(28, NECK_Y + dy, 35, NECK_Y + dy + 1, "HR")


def head_side(c, dy=0):
    """Profile facing +x."""
    t = HEAD_TOP + dy
    c.row(27, 38, t, "HRL")
    c.row(25, 40, t + 1, "HRL")
    c.rect(24, t + 2, 41, t + 6, "HR")
    c.row(26, 34, t + 2, "HRL")
    c.rect(24, t + 7, 35, t + 9, "HR")            # fringe over the brow
    c.rect(36, t + 7, 41, t + 9, "SK")
    c.rect(24, t + 10, 31, t + 13, "HR")          # hair down the back of the head
    c.rect(32, t + 10, 42, t + 13, "SK")
    c.rect(43, t + 11, 43, t + 12, "SK")          # the nose stands proud
    c.set(44, t + 12, "SKS")
    c.row(34, 37, t + 9, "HR")                    # brow
    c.rect(37, t + 11, 39, t + 12, "EW")          # one eye, seen from the side
    c.rect(38, t + 11, 39, t + 12, "EY")
    c.rect(30, t + 11, 33, t + 14, "SKS")         # ear
    c.set(31, t + 12, "SK")
    c.rect(24, t + 14, 29, t + 15, "HR")
    c.rect(30, t + 14, 41, t + 16, "SK")
    c.row(38, 41, t + 15, "SKS")                  # the lip line
    c.row(30, 39, t + 17, "SKS")                  # jaw
    c.row(31, 37, t + 18, "SKS")
    c.rect(29, NECK_Y + dy, 36, NECK_Y + dy + 1, "SKS")


def torso_front(c, dy=0, back=False):
    t = TORSO_TOP + dy
    b = BELT_Y + dy
    c.rect(23, t, 40, b - 1, "TU")
    c.row(23, 40, t, "TUL")                       # lit across the shoulders
    c.row(24, 39, t + 1, "TUL")
    if back:
        c.rect(28, t, 35, t + 2, "TUS")           # a yoke seam across the back
    else:
        c.rect(28, t, 35, t + 3, "TUS")           # a collar
        c.rect(29, t, 34, t + 2, "SKS")           # open at the throat
        c.col(31, t + 5, b - 3, "TUS")            # the fold down the front
        c.col(32, t + 5, b - 3, "TUS")
    c.col(23, t + 1, b - 1, "TUS")                # the sides turn away
    c.col(40, t + 1, b - 1, "TUS")

    c.rect(23, b, 40, b + 2, "BT")                # belt
    c.row(23, 40, b, "BTL")
    c.rect(29, b, 34, b + 2, "BTS")               # buckle
    c.rect(30, b + 1, 33, b + 1, "BTL")
    c.rect(28, NECK_Y + dy, 35, NECK_Y + dy + 1, "HR" if back else "SKS")


def torso_side(c, dy=0):
    t = TORSO_TOP + dy
    b = BELT_Y + dy
    c.rect(27, t, 41, b - 1, "TU")
    c.row(27, 41, t, "TUL")
    c.row(28, 40, t + 1, "TUL")
    c.col(27, t + 1, b - 1, "TUS")                # the back of the tunic
    c.col(28, t + 2, b - 1, "TUS")
    c.rect(27, b, 41, b + 2, "BT")
    c.row(27, 41, b, "BTL")
    c.rect(33, b, 38, b + 2, "BTS")
    c.rect(34, b + 1, 37, b + 1, "BTL")
    c.rect(29, NECK_Y + dy, 36, NECK_Y + dy + 1, "SKS")


def _arm_off(side, swing, reach):
    """Vertical offset of one arm: swing lifts one and drops the other,
    reach drops both - that is the crouch-and-pick-up."""
    return (-2 if swing * side > 0 else (2 if swing else 0)) + reach


def _hand(c, x0, x1, y, back=False):
    """A hand with a thumb, rather than a two-pixel stub."""
    key = "SKS" if back else "SK"
    c.rect(x0, y, x1, y + 3, key)
    c.set(x0, y + 1, "SKS")
    c.set(x1, y + 1, "SKS")
    c.row(x0 + 1, x1 - 1, y + 3, "SKS")


def arms_front(c, dy=0, swing=0, back=False, reach=0):
    """swing > 0: left arm up / right arm down; < 0 is the mirror."""
    t = TORSO_TOP + dy + 2
    for side, x0, inner in ((-1, ARM_L, ARM_L + 4), (1, ARM_R, ARM_R)):
        off = _arm_off(side, swing, reach)
        x1 = x0 + 4
        c.rect(x0, t + off, x1, t + 8 + off, "TU")         # sleeve
        c.row(x0, x1, t + off, "TUL")
        c.col(inner, t + off, t + 8 + off, "TUS")          # seam against the body
        c.row(x0, x1, t + 8 + off, "TUS")                  # cuff
        _hand(c, x0 + 1, x1 - 1, t + 9 + off, back)


def arm_side(c, dy=0, swing=0, reach=0):
    """The near arm only; the far arm is implied, which keeps the read clean."""
    t = TORSO_TOP + dy + 3 + reach
    x = 35 + swing * 2 + reach
    c.rect(x, t, x + 4, t + 7, "TU")
    c.row(x, x + 4, t, "TUL")
    c.col(x, t, t + 7, "TUS")
    c.row(x, x + 4, t + 7, "TUS")
    _hand(c, x + 1, x + 3, t + 8)


# ---------------------------------------------------------------- weapons ---
# A weapon is a line of pixels laid out from the hand along a unit step, with a
# guard or a head hung off the perpendicular. Describing it that way means the
# swing is just a different step per frame, not a redraw per orientation. At
# 64x64 the blade is three pixels across with a fuller down the middle.
WEAPONS = {
    "sword": dict(length=18, grip=5, shaft="MTL", edge="MT", core="MTD",
                  guard=True, pommel=True),
    "axe":   dict(length=16, grip=3, shaft="WD", edge="WDD", head="axe"),
    "spear": dict(length=21, grip=3, shaft="WD", edge="WDD", head="spear"),
}

REST_AIM = {"down": (0, -1), "up": (0, -1), "right": (1, -1)}


def draw_weapon(c, hx, hy, aim, name):
    spec = WEAPONS[name]
    dx, dy = aim
    px, py = -dy, dx                       # the perpendicular, for guards
    straight = not (dx and dy)
    for i in range(spec["length"] + 1):
        x, y = hx + dx * i, hy + dy * i
        if i < spec["grip"]:
            c.set(x, y, "WDD")             # the grip, bound in leather
            c.set(x + px, y + py, "WD")
            continue
        c.set(x, y, spec["shaft"])
        if straight:
            c.set(x + px, y + py, spec["edge"])
            if spec.get("core") and i > spec["grip"] + 1:
                c.set(x - px, y - py, spec["core"])   # a fuller down the blade
    if spec.get("pommel"):
        c.set(hx - dx, hy - dy, "MTD")
        c.set(hx - dx + px, hy - dy + py, "MTD")
    if spec.get("guard"):
        g = spec["grip"]
        for k in (-3, -2, -1, 0, 1, 2, 3, 4):
            c.set(hx + dx * g + px * k, hy + dy * g + py * k, "MT")
            c.set(hx + dx * (g - 1) + px * k, hy + dy * (g - 1) + py * k, "MTD")
    head = spec.get("head")
    if head == "axe":                      # a bit hung on one side of the haft
        for i in range(spec["length"] - 5, spec["length"] + 1):
            for k in (1, 2, 3, 4):
                c.set(hx + dx * i + px * k, hy + dy * i + py * k,
                      "MTL" if k >= 3 else "MT")
    elif head == "spear":
        n = spec["length"]
        for k in (-1, 0, 1):
            c.set(hx + dx * (n - 3) + px * k, hy + dy * (n - 3) + py * k, "WDD")
        for i, spread in ((n - 2, 1), (n - 1, 1), (n, 0), (n + 1, 0)):
            for k in range(-spread, spread + 1):
                c.set(hx + dx * i + px * k, hy + dy * i + py * k,
                      "MTL" if k == 0 else "MT")


# ------------------------------------------------------------------ armour ---
# Worn over the tunic after the torso is drawn, before the arms and the head,
# so sleeves and collar stay the character's own. Like a weapon, armour is
# baked into a frame set of its own rather than layered at runtime.
def mail(c, direction, dy=0):
    t = TORSO_TOP + dy
    b = BELT_Y + dy
    x0, x1 = (27, 41) if direction == "right" else (24, 39)
    c.rect(x0, t, x1, b - 1, "MT")
    for y in range(t + 2, b - 1):                  # the rings, as a fine mesh
        for x in range(x0, x1 + 1):
            if (x + y) % 2:
                c.set(x, y, "MTD")
    c.rect(x0, t, x1, t + 1, "MTL")                # a lit collar
    c.rect(x0 - 2, t, x0 + 1, t + 3, "MTL")        # pauldrons over the shoulder
    c.rect(x1 - 1, t, x1 + 2, t + 3, "MTL")        # seams
    c.row(x0 - 2, x0 + 1, t + 4, "MTD")
    c.row(x1 - 1, x1 + 2, t + 4, "MTD")
    c.row(x0, x1, b - 1, "MTD")                    # the skirt of the hauberk


ARMOURS = {"mail": mail}


# -------------------------------------------------------------------- legs ---
def _leg_front(c, x0, x1, top, lift, toe):
    foot = FOOT_Y - lift
    c.rect(x0, top, x1, foot - 4, "PN")
    c.col(x0, top, foot - 4, "PNS")               # the inside of the leg
    c.col(x0 + 1, top, top + 2, "PNL")            # a lit thigh
    c.row(x0, x1, foot - 6, "PNS")                # the knee
    bx0 = x0 - 1 if toe < 0 else x0
    bx1 = x1 + 1 if toe > 0 else x1
    c.rect(bx0, foot - 3, bx1, foot, "BT")        # boot
    c.row(bx0, bx1, foot - 3, "BTL")              # its cuff
    c.row(bx0, bx1, foot, "BTS")                  # and its sole
    c.set(bx0 if toe < 0 else bx1, foot - 1, "BTS")


def legs_front(c, top_dy=0, phase=0):
    """phase: 0 both planted, +1 right leg lifted, -1 left leg lifted."""
    top = HIP_Y + top_dy
    lift_l, lift_r = {0: (0, 0), 1: (0, 4), -1: (4, 0)}[phase]
    _leg_front(c, LEG_L[0], LEG_L[1], top, lift_l, -1)
    _leg_front(c, LEG_R[0], LEG_R[1], top, lift_r, +1)


def legs_side(c, top_dy=0, phase=0):
    """phase: +1 near leg forward, -1 near leg back, 0 legs passing."""
    top = HIP_Y + top_dy
    # Passing, the two legs would land on the same column and read as one, so
    # the near one steps a pixel clear of the far one.
    near_x = 28 + 6 * phase + (1 if phase == 0 else 0)
    far_x = 28 - 6 * phase
    lift = 2 if phase == 0 else 0
    for x, pants, shade, boot, lf in ((far_x, "PNS", "PNS", "BTS", 0),
                                      (near_x, "PN", "PNS", "BT", lift)):
        foot = FOOT_Y - lf
        c.rect(x, top, x + 6, foot - 4, pants)
        c.col(x, top, foot - 4, shade)
        c.row(x, x + 6, foot - 6, "PNS")          # knee
        c.rect(x, foot - 3, x + 6, foot, boot)
        c.row(x, x + 6, foot - 3, "BTL" if boot == "BT" else "BTS")
        c.row(x, x + 6, foot, "BTS")
        c.rect(x + 7, foot - 1, x + 8, foot, boot)   # the toe points forward
        c.row(x + 7, x + 8, foot, "BTS")


# ------------------------------------------------------------------ poses ---
def weapon_hand(direction, dy=0, swing=0, reach=0):
    """Where a held weapon starts: just outside the weapon hand, which is the
    character's right - screen right facing us, screen left from behind, the
    near hand in profile. Follows the arm, so the weapon rides the walk cycle."""
    if direction == "down":
        return ARM_R + 2, 41 + dy + _arm_off(1, swing, reach)
    if direction == "up":
        return ARM_L + 2, 41 + dy + _arm_off(-1, swing, reach)
    return 38 + swing * 2 + reach, 41 + dy + reach


def draw_actor(direction, bob=0, leg=0, swing=0, reach=0, held=None, aim=None,
               worn=None):
    """One cel. direction in {down, up, right}; left is the mirror of right.
    held names a WEAPONS entry; aim is the step it points along (rest if
    None); worn names an ARMOURS entry. Seen from behind the weapon hand is
    the far one, so the weapon goes down first and the body over it."""
    c = Canvas(FRAME, FRAME)
    aim = aim or REST_AIM[direction]
    hx, hy = weapon_hand(direction, bob, swing, reach)

    def armour():
        if worn:
            ARMOURS[worn](c, direction, bob)

    if direction == "down":
        legs_front(c, bob, leg)
        torso_front(c, bob)
        armour()
        arms_front(c, bob, swing, reach=reach)
        head_front(c, bob)
        if held:
            draw_weapon(c, hx, hy, aim, held)
    elif direction == "up":
        if held:
            draw_weapon(c, hx, hy, aim, held)
        legs_front(c, bob, leg)
        torso_front(c, bob, back=True)
        armour()
        arms_front(c, bob, swing, back=True, reach=reach)
        head_back(c, bob)
    elif direction == "right":
        legs_side(c, bob, leg)
        torso_side(c, bob)
        armour()
        head_side(c, bob)
        arm_side(c, bob, swing, reach)
        if held:
            draw_weapon(c, hx, hy, aim, held)
    else:
        raise ValueError(direction)
    return c.outline()


def draw_shadow(squash=0):
    """Ground shadow cel, kept on its own layer."""
    c = Canvas(FRAME, FRAME)
    y = FOOT_Y + 1
    if squash:
        c.row(24, 39, y, "SH")
        c.row(27, 36, y + 1, "SH")
        c.row(30, 33, y + 2, "SH")
    else:
        c.row(22, 41, y, "SH")
        c.row(25, 38, y + 1, "SH")
        c.row(28, 35, y + 2, "SH")
    return c


# --------------------------------------------------------------- timeline ---
WALK = [                       # contact, passing, contact, passing
    dict(bob=0, leg=1, swing=-1, squash=0),
    dict(bob=-2, leg=0, swing=0, squash=1),
    dict(bob=0, leg=-1, swing=1, squash=0),
    dict(bob=-2, leg=0, swing=0, squash=1),
]
IDLE = [                       # 2-frame breath
    dict(bob=0, leg=0, swing=0, squash=0),
    dict(bob=-2, leg=0, swing=0, squash=0),
]
GATHER = [                     # crouch, hands to the ground, rise
    dict(bob=2, leg=0, swing=0, squash=0, reach=4),
    dict(bob=6, leg=0, swing=0, squash=1, reach=8),
    dict(bob=2, leg=0, swing=0, squash=0, reach=4),
]
SLASH = [                      # wind up, strike, follow through, recover
    dict(bob=-2, leg=0, swing=1, squash=0),
    dict(bob=2, leg=1, swing=-1, squash=1),
    dict(bob=2, leg=1, swing=-1, squash=1),
    dict(bob=0, leg=0, swing=0, squash=0),
]
# Where the weapon points on each slash frame, per source facing. Facing us it
# sweeps across our right; from behind, the far hand does the mirror; in
# profile it is raised beside the head and chopped down and forward.
SLASH_AIM = {
    "down":  [(1, -1), (1, 0), (1, 1), None],
    "up":    [(-1, 1), (-1, 0), (-1, -1), None],
    "right": [(0, -1), (1, 0), (1, 1), None],
}
# state -> (poses, ms per frame, loops). One-shot states end and hand control
# back; the engine reads the flag rather than knowing which is which.
STATES = {
    "walk": (WALK, 120, True),
    "idle": (IDLE, 500, True),
    "gather": (GATHER, 140, False),
    "slash": (SLASH, 90, False),
}
STATE_ORDER = ["walk", "idle", "gather", "slash"]
BASE_STATES = ["walk", "idle", "gather"]       # what an unarmed biped has


def states_for(states=None, held=None):
    """The states one frame set carries: the actor's own, plus slash when it
    is wielding something - nobody swings an empty hand."""
    out = [s for s in STATE_ORDER if s in (states or BASE_STATES)]
    if held and "slash" not in out:
        out.append("slash")
    return out


def build_frames(variant=None, states=None, held=None, worn=None):
    """[(state, facing, i, actor Canvas, shadow Canvas, ms, loops), ...]

    `variant` is accepted for a uniform rig interface but unused: biped
    variants are pure palette swaps, so every variant shares these pixels.
    `held` bakes a weapon into every frame and adds the slash state; `worn`
    bakes armour over the tunic.

    Linear order: facing-major, then state, then frame - which is also the
    sheet's row-major order and the .aseprite frame order.
    """
    if held and held not in WEAPONS:
        raise ValueError(f"no such weapon drawing: {held!r}")
    if worn and worn not in ARMOURS:
        raise ValueError(f"no such armour drawing: {worn!r}")
    frames = []
    for facing in FACINGS:
        src = "right" if facing == "left" else facing
        for state in states_for(states, held):
            poses, ms, loops = STATES[state]
            for i, p in enumerate(poses):
                aim = SLASH_AIM[src][i] if state == "slash" else None
                cel = draw_actor(src, bob=p["bob"], leg=p["leg"], swing=p["swing"],
                                 reach=p.get("reach", 0), held=held, aim=aim,
                                 worn=worn)
                if facing == "left":
                    cel = cel.mirrored()
                frames.append((state, facing, i, cel, draw_shadow(p["squash"]),
                               ms, loops))
    return frames
