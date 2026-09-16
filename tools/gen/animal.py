"""Parametric quadruped rig: 4 facings, walk + idle + graze.

Same contract as the biped rig in actor.py - 32x32 frame, feet on GROUND_Y,
one anchor - so animals flow through the pipeline, the atlas and the depth
sorting with no special cases.

Species differ by silhouette flags (woolly back, horns, beard) plus a palette
variant, so a sheep and a goat are one rig rather than two sets of art.
"""

from gen.palette import Canvas

FRAME = 32
GROUND_Y = 29
ANCHOR = (16, GROUND_Y)
FACINGS = ["down", "left", "right", "up"]

FOOT_Y = 28                    # last hoof row
LEG_TOP = 23

SPECIES = {
    "sheep": {"wool": True, "horns": False, "beard": False},
    "goat": {"wool": False, "horns": True, "beard": True},
}


# --------------------------------------------------------------- side view ---
def _side_legs(c, offsets, bob):
    """Four legs at fixed x, swung by per-leg offsets. Hooves stay grounded."""
    for base, dx in zip((9, 12, 17, 20), offsets):
        x = base + dx
        lift = 1 if dx > 0 else 0
        c.rect(x, LEG_TOP + bob, x + 1, FOOT_Y - 1 - lift, "ABS" if base < 15 else "AB")
        c.rect(x, FOOT_Y - lift, x + 1, FOOT_Y - lift, "AH")


def _side_body(c, bob, shape):
    top = 18 + bob
    c.rect(8, top + 1, 21, 24 + bob, "AB")
    c.row(10, 19, top, "AB")
    c.row(9, 20, 24 + bob, "ABS")               # underside in shade
    c.row(11, 18, top, "ABL")                   # lit along the spine
    if shape["wool"]:                           # woolly back breaks the outline
        for x in (10, 13, 16, 19):
            c.set(x, top - 1, "ABL")
        c.set(8, top + 1, "ABL")
    c.rect(6, 19 + bob, 7, 21 + bob, "ABS")     # tail
    if not shape["wool"]:
        c.rect(6, 19 + bob, 7, 20 + bob, "AF")  # goats have a thin dark tail


def _side_head(c, bob, shape, down=0):
    """down > 0 lowers the head towards the grass."""
    hy = 15 + bob + down
    # The neck spans from the shoulder to wherever the head is, so lowering the
    # head to graze stretches the neck instead of detaching it.
    c.rect(20, 18 + bob, 22, hy + 4, "AB")
    c.rect(22, hy, 26, hy + 5, "AF")            # head
    c.row(23, 26, hy + 5, "AFS")
    c.set(26, hy + 3, "AFS")                    # muzzle
    c.set(25, hy + 2, "OL")                     # eye
    c.rect(21, hy + 1, 22, hy + 1, "AF")        # ear
    if shape["horns"]:
        c.rect(22, hy - 2, 23, hy - 1, "HN")
        c.set(24, hy - 2, "HNS")
    if shape["beard"]:
        c.rect(24, hy + 6, 25, hy + 7, "AFS")


def draw_side(shape, pose):
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    _side_legs(c, pose.get("legs", (0, 0, 0, 0)), bob)
    _side_body(c, bob, shape)
    _side_head(c, bob, shape, pose.get("head_down", 0))
    return c.outline()


# ------------------------------------------------------- front / back view ---
def _front_legs(c, spread, bob):
    for x in (12 + spread, 18 - spread):
        c.rect(x, LEG_TOP + bob, x + 1, FOOT_Y - 1, "ABS")
        c.rect(x, FOOT_Y, x + 1, FOOT_Y, "AH")


def draw_front(shape, pose):
    """Facing the camera: head drawn over the body, ears out to the sides."""
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    down = pose.get("head_down", 0) // 3       # head-on, the drop barely reads
    _front_legs(c, pose.get("spread", 0), bob)
    c.rect(10, 16 + bob, 21, 24 + bob, "AB")            # body
    c.row(11, 20, 15 + bob, "AB")
    c.row(12, 19, 15 + bob, "ABL")
    if shape["wool"]:
        for x in (11, 14, 17, 20):
            c.set(x, 14 + bob, "ABL")

    hy = 18 + bob + down
    if shape["horns"]:                                  # above the head, so they
        c.rect(12, hy - 4, 13, hy - 2, "HN")            # clear the body outline
        c.rect(18, hy - 4, 19, hy - 2, "HN")
    c.rect(10, hy + 1, 11, hy + 2, "AF")                # ears
    c.rect(20, hy + 1, 21, hy + 2, "AF")
    c.rect(12, hy, 19, hy + 6, "AF")                    # head over the body
    c.row(13, 18, hy + 6, "AFS")
    c.rect(14, hy + 4, 17, hy + 6, "AFS")               # muzzle
    c.set(13, hy + 2, "OL")
    c.set(18, hy + 2, "OL")
    if shape["beard"]:
        c.rect(15, hy + 7, 16, hy + 8, "AFS")
    return c.outline()


def draw_back(shape, pose):
    """Facing away: rump and tail, ears just visible over the shoulders."""
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    _front_legs(c, pose.get("spread", 0), bob)
    c.rect(10, 16 + bob, 21, 25 + bob, "AB")            # body
    c.row(11, 20, 15 + bob, "AB")
    c.row(12, 19, 15 + bob, "ABL")
    c.row(11, 20, 25 + bob, "ABS")
    if shape["wool"]:
        for x in (11, 14, 17, 20):
            c.set(x, 14 + bob, "ABL")
    c.rect(15, 16 + bob, 16, 20 + bob, "ABS")           # tail
    if not shape["wool"]:
        c.rect(15, 15 + bob, 16, 19 + bob, "AF")

    # From behind the head is hidden, so grazing reads through the body bob only.
    c.rect(11, 13 + bob, 12, 14 + bob, "AF")            # ear tips over the shoulders
    c.rect(19, 13 + bob, 20, 14 + bob, "AF")
    if shape["horns"]:
        c.rect(13, 12 + bob, 14, 13 + bob, "HN")
        c.rect(17, 12 + bob, 18, 13 + bob, "HN")
    return c.outline()


# ----------------------------------------------------------------- poses ----
WALK = [
    dict(bob=0, legs=(1, -1, -1, 1), spread=1),
    dict(bob=-1, legs=(0, 0, 0, 0), spread=0),
    dict(bob=0, legs=(-1, 1, 1, -1), spread=1),
    dict(bob=-1, legs=(0, 0, 0, 0), spread=0),
]
IDLE = [
    dict(bob=0, legs=(0, 0, 0, 0), spread=0),
    dict(bob=-1, legs=(0, 0, 0, 0), spread=0),
]
GRAZE = [                       # head down, chewing
    dict(bob=0, legs=(0, 0, 0, 0), spread=1, head_down=7),
    dict(bob=0, legs=(0, 0, 0, 0), spread=1, head_down=6),
]
# state -> (poses, ms per frame, loops); every animal state loops.
STATES = {"walk": (WALK, 150, True), "idle": (IDLE, 600, True),
          "graze": (GRAZE, 380, True)}
STATE_ORDER = ["walk", "idle", "graze"]


def states_for(states=None, held=None):
    """Same contract as the biped rig. Animals hold nothing, so `held` is
    accepted and ignored rather than being a special case downstream."""
    return [s for s in STATE_ORDER if s in (states or STATE_ORDER)]


def draw_shadow():
    c = Canvas(FRAME, FRAME)
    c.row(8, 22, GROUND_Y, "SH")
    c.row(10, 20, GROUND_Y + 1, "SH")
    return c


def build_frames(species="sheep", states=None, held=None):
    """[(state, facing, i, cel, shadow, ms, loops), ...] - the biped's shape."""
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
