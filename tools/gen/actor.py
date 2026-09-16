"""Parametric character rig: 4 facings, walk + idle.

Every frame is composed by the same body-part functions; only pose parameters
(bob, leg phase, arm swing) change, so a character cannot drift between
facings or states. The hips follow the bob while the feet stay on a fixed
ground line, so legs stretch by a pixel instead of the sprite hopping.

Frame is 32x32, symmetric about the x=15/16 boundary. ANCHOR is the point that
sits on a map tile - exported into the atlas so the engine never guesses.
"""

from gen.palette import Canvas

FRAME = 32
GROUND_Y = 29                 # the row a sprite's feet stand on
ANCHOR = (16, GROUND_Y)

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
        c.set(x + 3, foot, "BTS")          # toe points forward


# ------------------------------------------------------------------ poses ---
def draw_actor(direction, bob=0, leg=0, swing=0):
    """One cel. direction in {down, up, right}; left is the mirror of right."""
    c = Canvas(FRAME, FRAME)
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
STATES = {"walk": (WALK, 120), "idle": (IDLE, 500)}
STATE_ORDER = ["walk", "idle"]


def build_frames():
    """[(state, facing, i, actor Canvas, shadow Canvas, ms), ...]

    Linear order: facing-major, then state, then frame - which is also the
    sheet's row-major order and the .aseprite frame order.
    """
    frames = []
    for facing in FACINGS:
        src = "right" if facing == "left" else facing
        for state in STATE_ORDER:
            poses, ms = STATES[state]
            for i, p in enumerate(poses):
                cel = draw_actor(src, bob=p["bob"], leg=p["leg"], swing=p["swing"])
                if facing == "left":
                    cel = cel.mirrored()
                frames.append((state, facing, i, cel, draw_shadow(p["squash"]), ms))
    return frames
