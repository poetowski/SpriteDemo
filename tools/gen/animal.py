"""Parametric quadruped rig: 4 facings, walk + idle + graze.

Drawn at 64x64, the same contract as the biped in actor.py - same frame, same
ground line, one anchor - so animals flow through the pipeline, the atlas and
the depth sorting with no special cases.

At this size the fleece is a real texture rather than four bumps on a
silhouette, the legs are separate limbs with hooves, and the head has an eye
and a muzzle. Species differ by silhouette flags (woolly back, horns, beard)
plus a palette variant, so a sheep and a goat are one rig, not two sets of art.
"""

from gen.palette import Canvas, scatter

FRAME = 64
GROUND_Y = 58
ANCHOR = (32, GROUND_Y)
FACINGS = ["down", "left", "right", "up"]

FOOT_Y = 57                    # last hoof row
LEG_TOP = 44

SPECIES = {
    "sheep": {"wool": True, "horns": False, "beard": False},
    "goat": {"wool": False, "horns": True, "beard": True},
}


def _fleece(c, x0, y0, x1, y1, seed):
    """Curls over the coat: a scatter of light and dark two-pixel marks, fixed
    per species so the texture never shimmers between frames."""
    rnd = scatter(seed)
    for _ in range(38):
        x = x0 + rnd(max(1, x1 - x0 - 1))
        y = y0 + rnd(max(1, y1 - y0 - 1))
        key = "ABL" if rnd(2) else "ABS"
        c.set(x, y, key)
        c.set(x + 1, y, key)


# --------------------------------------------------------------- side view ---
def _side_legs(c, offsets, bob):
    """Four legs at fixed x, swung by per-leg offsets. Hooves stay grounded."""
    for base, dx in zip((18, 25, 35, 42), offsets):
        x = base + dx * 2
        lift = 2 if dx > 0 else 0
        far = base < 30
        c.rect(x, LEG_TOP + bob, x + 3, FOOT_Y - 3 - lift, "ABS" if far else "AB")
        c.col(x, LEG_TOP + bob, FOOT_Y - 3 - lift, "ABS")
        c.rect(x, FOOT_Y - 2 - lift, x + 3, FOOT_Y - lift, "AH")   # hoof
        c.row(x, x + 3, FOOT_Y - 2 - lift, "AFS")


def _side_body(c, bob, shape):
    top = 34 + bob
    c.rect(16, top + 2, 43, 48 + bob, "AB")
    c.row(19, 40, top, "AB")                      # the back
    c.row(17, 42, top + 1, "AB")
    c.row(20, 38, top, "ABL")                     # light along the spine
    c.row(17, 42, 48 + bob, "ABS")                # belly in shade
    c.row(19, 40, 49 + bob, "ABS")
    if shape["wool"]:
        _fleece(c, 17, top + 1, 42, 47 + bob, 0x5EE9)
        for x in range(18, 43, 4):                # the fleece breaks the outline
            c.set(x, top - 1, "ABL")
            c.set(x + 1, top - 1, "ABL")
    else:
        for x in range(19, 42, 6):                # a goat's coat lies flat
            c.col(x, top + 3, 46 + bob, "ABS")
    c.rect(12, top + 3, 16, top + 7, "ABS")       # tail
    if not shape["wool"]:
        c.rect(12, top + 2, 15, top + 9, "AF")


def _side_head(c, bob, shape, down=0):
    """down > 0 lowers the head towards the grass."""
    hy = 28 + bob + down
    # The neck spans shoulder to head, so grazing stretches it rather than
    # detaching the head.
    c.rect(40, 34 + bob, 47, hy + 9, "AB")
    c.col(40, 34 + bob, hy + 9, "ABS")
    c.rect(44, hy, 55, hy + 10, "AF")             # head
    c.row(45, 55, hy, "AFS")
    c.rect(52, hy + 5, 56, hy + 10, "AFS")        # muzzle
    c.set(56, hy + 7, "AFS")
    c.rect(49, hy + 3, 51, hy + 5, "EW")          # eye
    c.rect(50, hy + 4, 51, hy + 5, "EY")
    c.rect(42, hy + 1, 46, hy + 4, "AF")          # ear, swept back
    c.set(41, hy + 2, "AFS")
    if shape["horns"]:
        for i in range(6):                        # a horn curving back
            c.set(45 - i, hy - 1 - i, "HN")
            c.set(46 - i, hy - 1 - i, "HNS")
    if shape["beard"]:
        c.rect(52, hy + 11, 55, hy + 15, "AFS")


def draw_side(shape, pose):
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    _side_legs(c, pose.get("legs", (0, 0, 0, 0)), bob)
    _side_body(c, bob, shape)
    _side_head(c, bob, shape, pose.get("head_down", 0))
    return c.outline()


# ------------------------------------------------------- front / back view ---
def _front_legs(c, spread, bob):
    for x in (23 + spread * 2, 37 - spread * 2):
        c.rect(x, LEG_TOP + bob, x + 3, FOOT_Y - 3, "ABS")
        c.rect(x, FOOT_Y - 2, x + 3, FOOT_Y, "AH")
        c.row(x, x + 3, FOOT_Y - 2, "AFS")


def draw_front(shape, pose):
    """Facing the camera: the head is drawn over the body, ears to the sides."""
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    down = pose.get("head_down", 0) // 3       # head-on, the drop barely reads
    _front_legs(c, pose.get("spread", 0), bob)
    c.rect(20, 32 + bob, 43, 48 + bob, "AB")            # body
    c.row(23, 40, 30 + bob, "AB")
    c.row(25, 38, 30 + bob, "ABL")
    if shape["wool"]:
        _fleece(c, 21, 31 + bob, 42, 47 + bob, 0x77A1)
        for x in range(22, 43, 4):
            c.set(x, 29 + bob, "ABL")
            c.set(x + 1, 29 + bob, "ABL")

    hy = 36 + bob + down
    if shape["horns"]:
        for i in range(5):
            c.rect(24 - i // 2, hy - 2 - i, 25 - i // 2, hy - 1 - i, "HN")
            c.rect(38 + i // 2, hy - 2 - i, 39 + i // 2, hy - 1 - i, "HN")
    c.rect(18, hy + 2, 23, hy + 6, "AF")               # ears
    c.rect(40, hy + 2, 45, hy + 6, "AF")
    c.rect(24, hy, 39, hy + 12, "AF")                  # head over the body
    c.row(25, 38, hy + 12, "AFS")
    c.rect(27, hy + 8, 36, hy + 12, "AFS")             # muzzle
    c.rect(26, hy + 3, 29, hy + 5, "EW")               # eyes
    c.rect(34, hy + 3, 37, hy + 5, "EW")
    c.rect(27, hy + 4, 28, hy + 5, "EY")
    c.rect(35, hy + 4, 36, hy + 5, "EY")
    c.set(30, hy + 10, "AF")                           # nostrils
    c.set(33, hy + 10, "AF")
    if shape["beard"]:
        c.rect(29, hy + 13, 34, hy + 17, "AFS")
    return c.outline()


def draw_back(shape, pose):
    """Facing away: rump and tail, ears just visible over the shoulders."""
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    _front_legs(c, pose.get("spread", 0), bob)
    c.rect(20, 32 + bob, 43, 50 + bob, "AB")           # body
    c.row(23, 40, 30 + bob, "AB")
    c.row(25, 38, 30 + bob, "ABL")
    c.row(22, 41, 50 + bob, "ABS")
    if shape["wool"]:
        _fleece(c, 21, 31 + bob, 42, 49 + bob, 0x31C4)
        for x in range(22, 43, 4):
            c.set(x, 29 + bob, "ABL")
            c.set(x + 1, 29 + bob, "ABL")
    c.rect(30, 33 + bob, 33, 41 + bob, "ABS")          # tail
    if not shape["wool"]:
        c.rect(30, 31 + bob, 33, 40 + bob, "AF")

    # From behind the head is hidden, so grazing reads through the body alone.
    c.rect(21, 26 + bob, 26, 30 + bob, "AF")           # ear tips over the shoulders
    c.rect(37, 26 + bob, 42, 30 + bob, "AF")
    if shape["horns"]:
        for i in range(5):
            c.rect(26 + i // 2, 25 - i + bob, 27 + i // 2, 26 - i + bob, "HN")
            c.rect(36 - i // 2, 25 - i + bob, 37 - i // 2, 26 - i + bob, "HN")
    return c.outline()


# ----------------------------------------------------------------- poses ----
WALK = [
    dict(bob=0, legs=(1, -1, -1, 1), spread=1),
    dict(bob=-2, legs=(0, 0, 0, 0), spread=0),
    dict(bob=0, legs=(-1, 1, 1, -1), spread=1),
    dict(bob=-2, legs=(0, 0, 0, 0), spread=0),
]
IDLE = [
    dict(bob=0, legs=(0, 0, 0, 0), spread=0),
    dict(bob=-2, legs=(0, 0, 0, 0), spread=0),
]
GRAZE = [                       # head down, chewing
    dict(bob=0, legs=(0, 0, 0, 0), spread=1, head_down=17),
    dict(bob=0, legs=(0, 0, 0, 0), spread=1, head_down=15),
]
STATES = {"walk": (WALK, 150, True), "idle": (IDLE, 600, True),
          "graze": (GRAZE, 380, True)}
STATE_ORDER = ["walk", "idle", "graze"]


def draw_shadow(*_args):
    c = Canvas(FRAME, FRAME)
    c.row(16, 47, GROUND_Y, "SH")
    c.row(20, 43, GROUND_Y + 1, "SH")
    c.row(26, 37, GROUND_Y + 2, "SH")
    return c


def build_frames(species="sheep", states=None, held=None, worn=None):
    """[(state, facing, i, cel, shadow, ms, loops), ...] - the biped's shape."""
    shape = SPECIES[species]
    frames = []
    for facing in FACINGS:
        for state in (states or STATE_ORDER):
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
