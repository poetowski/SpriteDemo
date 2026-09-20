"""Parametric character rig: 4 facings; walk, idle, gather, and slash.

Every frame is composed by the same body-part functions; only pose parameters
(bob, leg phase, arm swing, reach) change, so a character cannot drift between
facings or states. The hips follow the bob while the feet stay on a fixed
ground line, so legs stretch by a pixel instead of the sprite hopping - which
is also what makes the gather crouch free: bob the body down and the legs
simply get shorter.

A held weapon is part of the pose, not a second sprite. It is drawn from the
hand out along a direction, so one description of a sword serves every frame
of the swing, and the same frame decides whether it is in front of the body
or behind it. A character wielding something is therefore a separate frame
set (actor.hero_sword), baked here, and the engine just switches sprite base.

Frame is 32x32, symmetric about the x=15/16 boundary. ANCHOR is the point that
sits on a map tile - exported into the atlas so the engine never guesses.
"""

from gen.palette import Canvas

FRAME = 32
GROUND_Y = 29                 # the row a sprite's feet stand on
ANCHOR = (16, GROUND_Y)
ATLAS = "actors"              # the sheet this rig's frames are packed into
COLS = 6

FACINGS = ["down", "left", "right", "up"]

# Anatomy constants, in frame pixels, for bob == 0.
HEAD_TOP = 4
NECK_Y = 13
TORSO_TOP = 14
BELT_Y = 21
HIP_Y = 22
FOOT_Y = 28                   # last boot row

LEG_L = (12, 14)
LEG_R = (17, 19)


# ------------------------------------------------------------- body parts ---
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


def _arm_off(side, swing, reach):
    """Vertical offset of one arm: swing lifts one and drops the other,
    reach drops both - that is the crouch-and-pick-up."""
    return (-1 if swing * side > 0 else (1 if swing else 0)) + reach


def arms_front(c, dy=0, swing=0, back=False, reach=0):
    """swing > 0: left arm up / right arm down; < 0 is the mirror."""
    t = TORSO_TOP + dy + 1
    for side, x0, inner in ((-1, 10, 11), (1, 20, 20)):
        off = _arm_off(side, swing, reach)
        x1 = x0 + 1
        c.rect(x0, t + off, x1, t + 3 + off, "TU")
        c.col(inner, t + off, t + 3 + off, "TUS")   # seam against the torso
        c.rect(x0, t + 4 + off, x1, t + 5 + off, "SKS" if back else "SK")


def arm_side(c, dy=0, swing=0, reach=0):
    """The near arm only; the far arm is implied, which keeps the read clean."""
    t = TORSO_TOP + dy + 1 + reach
    x = 17 + swing + reach // 2            # hangs near the chest, swings 1px,
    c.rect(x, t + 1, x + 1, t + 4, "TU")   # and reaches forward when crouched
    c.col(x, t + 1, t + 4, "TUS")          # one seam, not a stripe pattern
    c.rect(x, t + 5, x + 1, t + 6, "SK")   # the hand below the hem carries it


# ---------------------------------------------------------------- weapons ---
# A weapon is a line of pixels laid out from the hand along a unit step, with
# a guard or a head hung off the perpendicular. Describing it that way means
# the swing is just a different step per frame, not a redraw per orientation.
WEAPONS = {
    "sword": dict(length=8, grip=2, shaft="MTL", edge="MT", guard=True),
    "axe":   dict(length=7, grip=0, shaft="WD", edge="WDD", head="axe"),
    "spear": dict(length=9, grip=0, shaft="WD", edge="WDD", head="spear"),
    # The one blade here that is not metal, and the only one longer than the
    # hero is tall from shoulder to boot. Its `glow` puts a third row of light
    # on the side the steel weapons leave dark: inside a weapon drawn as a
    # line, **width is the only thing that can say "lit"**. Colour alone says
    # "blue", and a blue line the same two pixels thick as the sword reads as
    # a sword somebody painted.
    "azure_blade": dict(length=10, grip=2, shaft="CYL", edge="CY", glow="CY",
                        guard=True, grip_key="STX", guard_key="CYD",
                        thick=True),
}

REST_AIM = {"down": (0, -1), "up": (0, -1), "right": (1, -1)}


# ------------------------------------------------------------------ armour ---
# Worn over the tunic after the torso is drawn, before the arms and the head,
# so sleeves and collar stay the character's own. Like a weapon, armour is
# baked into a frame set of its own rather than layered at runtime.
def mail(c, direction, dy=0):
    t = TORSO_TOP + dy
    b = BELT_Y + dy
    x0, x1 = (13, 19) if direction == "right" else (12, 19)
    c.rect(x0, t, x1, b - 1, "MT")
    for y in range(t + 1, b - 1):                  # the rings, as a checker
        for x in range(x0, x1 + 1):
            if (x + y) % 2:
                c.set(x, y, "MTD")
    c.row(x0, x1, t, "MTL")                        # a lit collar
    c.rect(x0 - 1, t, x0, t + 1, "MTL")            # and pauldrons over the
    c.rect(x1, t, x1 + 1, t + 1, "MTL")            # shoulder seams
    c.set(x0 - 1, t + 2, "MTD")
    c.set(x1 + 1, t + 2, "MTD")


def desert_tunic(c, direction, dy=0):
    """Linen to the waist under a broad gilt collar. The collar is the armour
    and the rest is cloth, which is how it reads at a glance against the mail:
    one is metal all over and this is one bright band at the shoulders."""
    t = TORSO_TOP + dy
    b = BELT_Y + dy
    x0, x1 = (13, 19) if direction == "right" else (12, 19)
    c.rect(x0, t, x1, b - 1, "CL")                 # the linen
    for y in range(t + 3, b - 1):                  # and the weave of it, as a
        for x in range(x0, x1 + 1):                # dither: a dark row every
            if (x * 2 + y) % 4 == 0:               # other line was a striped
                c.set(x, y, "CLD")                 # shirt, not woven cloth
    c.rect(x0, t, x1, t + 2, "GD")                 # the broad collar
    c.row(x0, x1, t, "GDL")
    c.row(x0, x1, t + 2, "GDD")
    c.set(x0 + 1, t + 1, "LP")                     # inlaid, twice
    c.set(x1 - 1, t + 1, "LP")
    c.rect(x0 - 1, t, x0, t + 1, "GDL")            # over the shoulder seams
    c.rect(x1, t, x1 + 1, t + 1, "GDL")
    c.set(x0 - 1, t + 2, "GDD")
    c.set(x1 + 1, t + 2, "GDD")
    c.row(x0, x1, b - 1, "LP")                     # a sash at the waist
    c.set(x0 + 2, b - 1, "LPL")


def nomad_armor(c, direction, dy=0):
    """A travelling robe: heavy linen with an indigo mantle over the shoulders
    and a sash. Where the desert tunic is one bright band at the collar, this
    is dark at the top and pale below - the two read apart at a glance even
    though both are cloth, which is the only thing that matters in a bag."""
    t = TORSO_TOP + dy
    b = BELT_Y + dy
    x0, x1 = (13, 19) if direction == "right" else (12, 19)
    c.rect(x0, t, x1, b - 1, "CL")                 # the robe
    for y in range(t + 4, b - 1):                  # woven, as a dither - a
        for x in range(x0, x1 + 1):                # dark row every other line
            if (x * 2 + y) % 4 == 0:               # is a striped shirt
                c.set(x, y, "CLD")
    c.rect(x0, t, x1, t + 3, "LP")                 # the mantle over it
    c.row(x0, x1, t, "LPL")
    c.row(x0, x1, t + 3, "LPD")
    c.rect(x0 - 1, t, x0, t + 2, "LP")             # over the shoulder seams
    c.rect(x1, t, x1 + 1, t + 2, "LP")
    c.set(x0 - 1, t + 2, "LPD")
    c.set(x1 + 1, t + 2, "LPD")
    c.row(x0, x1, b - 1, "GD")                     # and a sash at the waist
    c.set(x0 + 2, b - 1, "GDL")


ARMOURS = {"mail": mail, "desert_tunic": desert_tunic,
           "nomad_armor": nomad_armor}


def draw_weapon(c, hx, hy, aim, name):
    spec = WEAPONS[name]
    dx, dy = aim
    px, py = -dy, dx                       # the perpendicular, for guards
    straight = not (dx and dy)
    # Everything a weapon does not say for itself falls back to the wooden
    # haft the first three are built from, so adding a field leaves them alone.
    glow = spec.get("glow")
    # Width goes on along the perpendicular while the weapon points along an
    # axis. On a diagonal the perpendicular is diagonal too, so the extra rows
    # land on diagonal neighbours and the blade comes out a chequerboard - a
    # barber's pole, not a sword. A sideways step gives a solid parallel line,
    # which is also how the 16px icons draw a diagonal blade.
    wx, wy = (px, py) if straight else (dx, 0)
    for i in range(spec["length"] + 1):
        x, y = hx + dx * i, hy + dy * i
        if i < spec["grip"]:
            c.set(x, y, spec.get("grip_key", "WD"))
            continue
        c.set(x, y, spec["shaft"])
        # The steel weapons are one pixel wide when they point on a diagonal,
        # which is fine for them and is not for a blade whose whole character
        # is that it is lit: held at rest facing right it came out a thin
        # white stick, with none of the colour that is the point of it. A
        # weapon can ask to keep its width in every direction instead.
        if (straight or spec.get("thick")) and i >= spec["grip"] + 1:
            c.set(x + wx, y + wy, spec["edge"])    # a second row gives it width
            if glow:
                c.set(x - wx, y - wy, glow)        # and a third one gives light
    if spec.get("guard"):
        g = spec["grip"]
        for k in (-1, 0, 1, 2):
            c.set(hx + dx * g + px * k, hy + dy * g + py * k,
                  spec.get("guard_key", "WDD"))
    head = spec.get("head")
    if head == "axe":                      # a bit hung on one side of the haft
        for i in range(spec["length"] - 2, spec["length"] + 1):
            for k in (1, 2):
                c.set(hx + dx * i + px * k, hy + dy * i + py * k,
                      "MTL" if k == 2 else "MT")
    elif head == "spear":
        n = spec["length"]
        c.set(hx + dx * (n - 1), hy + dy * (n - 1), "WDD")   # the collar
        c.set(hx + dx * n, hy + dy * n, "MTL")
        c.set(hx + dx * (n + 1), hy + dy * (n + 1), "MTL")


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
        c.set(x + 3, foot, "BTS")          # toe points forward


# ------------------------------------------------------------------ poses ---
def weapon_hand(direction, dy=0, swing=0, reach=0):
    """Where a held weapon starts: just outside the weapon hand, which is the
    character's right - screen right facing us, screen left from behind, the
    near hand in profile. Follows the arm, so the weapon rides the walk cycle."""
    if direction == "down":
        return 22, 20 + dy + _arm_off(1, swing, reach)
    if direction == "up":
        return 9, 20 + dy + _arm_off(-1, swing, reach)
    return 19 + swing + reach // 2, 20 + dy + reach


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
        c.row(12, 19, y, "SH")
        c.row(14, 17, y + 1, "SH")
    else:
        c.row(11, 20, y, "SH")
        c.row(13, 18, y + 1, "SH")
    return c


# --------------------------------------------------------------- timeline ---
WALK = [                       # contact, passing, contact, passing
    dict(bob=0, leg=1, swing=-1, squash=0),
    dict(bob=-1, leg=0, swing=0, squash=1),
    dict(bob=0, leg=-1, swing=1, squash=0),
    dict(bob=-1, leg=0, swing=0, squash=1),
]
IDLE = [                       # 2-frame breath
    dict(bob=0, leg=0, swing=0, squash=0),
    dict(bob=-1, leg=0, swing=0, squash=0),
]
GATHER = [                     # crouch, hands to the ground, rise
    dict(bob=1, leg=0, swing=0, squash=0, reach=2),
    dict(bob=3, leg=0, swing=0, squash=1, reach=4),
    dict(bob=1, leg=0, swing=0, squash=0, reach=2),
]
SLASH = [                      # wind up, strike, follow through, recover
    dict(bob=-1, leg=0, swing=1, squash=0),
    dict(bob=1, leg=1, swing=-1, squash=1),
    dict(bob=1, leg=1, swing=-1, squash=1),
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
