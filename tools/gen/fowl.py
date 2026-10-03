"""Ground-bird rig: 4 facings, walk + idle + graze (which, for a hen, is pecking).

A fifth-sized animal on two legs shares nothing with the quadruped - no barrel
on four legs, no head on a neck out in front at shoulder height - so it is its
own rig rather than a flag. It is the same 32x32 frame with the same anchor,
which is what puts it on the same sheet as the sheep and lets it wander,
depth-sort and collide exactly like one.

What makes a hen at this size is three things and nothing else: the tail
cocked up behind, the red comb on top, and the body carried low and round.
The legs are the difficulty. Two legs a pixel apart pick up an outline each
and close into one dark block, so they are drawn as the heron's were - one
line, with the feet turned out at the bottom.
"""

from gen.palette import Canvas

FRAME = 32
GROUND_Y = 29
ANCHOR = (16, GROUND_Y)
ATLAS = "actors"
COLS = 6
FACINGS = ["down", "left", "right", "up"]
FOOT_Y = 28

SPECIES = {
    "chicken": {"comb": True},
}


def _legs_side(c, step):
    """One leg line under the body, the far foot forward or back."""
    c.col(16, 25, FOOT_Y, "TH")
    c.set(17, FOOT_Y, "TH")
    c.set(15 + step, FOOT_Y, "THD")


def draw_side(shape, pose):
    c = Canvas(FRAME, FRAME)
    bob, peck = pose.get("bob", 0), pose.get("peck", 0)
    _legs_side(c, pose.get("step", 0))
    # The body: a round mass carried low, deepest at the breast.
    for y, x0, x1 in ((19, 13, 18), (20, 12, 19), (21, 11, 20), (22, 11, 20),
                      (23, 11, 20), (24, 12, 19), (25, 13, 18)):
        c.row(x0, x1, y + bob, "AB")
    c.row(13, 18, 19 + bob, "ABL")                # lit along the back
    c.row(12, 19, 25 + bob, "ABS")
    c.rect(13, 21 + bob, 16, 23 + bob, "ABS")     # the folded wing
    c.row(13, 16, 21 + bob, "AB")
    # The tail, cocked up behind: the one part of a hen's outline that is not
    # round, which is why it has to be there in every view that can show it.
    for y, x0, x1 in ((15, 10, 11), (16, 9, 12), (17, 9, 12), (18, 10, 12)):
        c.row(x0, x1, y + bob, "AB")
    c.set(9, 16 + bob, "ABS")
    # The head, on a short neck; pecking takes it down to the ground in front.
    hx, hy = 19 + peck // 2, 14 + bob + peck
    c.rect(18, 17 + bob, 20, 20 + bob, "AB")      # neck
    if peck:
        for i in range(peck):
            c.rect(19 + i // 2, 17 + bob + i, 21 + i // 2, 18 + bob + i, "AB")
    c.rect(hx, hy, hx + 3, hy + 3, "AB")
    c.set(hx + 2, hy + 1, "OL")                   # eye
    c.rect(hx + 4, hy + 2, hx + 5, hy + 2, "FL")  # beak
    if shape.get("comb"):
        c.rect(hx, hy - 1, hx + 2, hy - 1, "RF")
        c.set(hx + 1, hy - 2, "RF")
        c.set(hx + 3, hy + 4, "RF")               # wattle
    return c.outline()


def draw_front(shape, pose):
    c = Canvas(FRAME, FRAME)
    bob, peck = pose.get("bob", 0), pose.get("peck", 0)
    c.col(15, 25, FOOT_Y, "TH")                   # the legs, as one line
    c.col(16, 25, FOOT_Y, "THD")
    c.row(13, 14, FOOT_Y, "TH")
    c.row(17, 18, FOOT_Y, "TH")
    for y, x0, x1 in ((19, 13, 18), (20, 12, 19), (21, 11, 20), (22, 11, 20),
                      (23, 11, 20), (24, 12, 19), (25, 13, 18)):
        c.row(x0, x1, y + bob, "AB")
    c.row(12, 19, 25 + bob, "ABS")
    c.col(11, 21 + bob, 23 + bob, "ABS")          # wings held in at the sides
    c.col(20, 21 + bob, 23 + bob, "ABS")
    hy = 14 + bob + peck // 2
    c.rect(14, hy, 17, hy + 4, "AB")              # head over the breast
    c.set(14, hy + 1, "OL")
    c.set(17, hy + 1, "OL")
    c.rect(15, hy + 2, 16, hy + 3, "FL")          # beak, end on
    if shape.get("comb"):
        c.rect(15, hy - 2, 16, hy - 1, "RF")
        c.rect(15, hy + 4, 16, hy + 5, "RF")      # wattles under the beak
    return c.outline()


def draw_back(shape, pose):
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    c.col(15, 25, FOOT_Y, "THD")
    c.col(16, 25, FOOT_Y, "TH")
    for y, x0, x1 in ((19, 13, 18), (20, 12, 19), (21, 11, 20), (22, 11, 20),
                      (23, 11, 20), (24, 12, 19), (25, 13, 18)):
        c.row(x0, x1, y + bob, "AB")
    c.row(12, 19, 25 + bob, "ABS")
    # From behind the tail is a fan standing over the rump, and it is most of
    # what you see; the head only shows its comb over the top.
    for y, x0, x1 in ((14, 14, 17), (15, 13, 18), (16, 13, 18), (17, 13, 18),
                      (18, 14, 17)):
        c.row(x0, x1, y + bob, "AB")
    c.col(15, 15 + bob, 18 + bob, "ABS")
    c.col(16, 15 + bob, 18 + bob, "ABL")
    if shape.get("comb"):
        c.rect(15, 12 + bob, 16, 13 + bob, "RF")
    return c.outline()


WALK = [dict(bob=0, step=1), dict(bob=-1, step=0),
        dict(bob=0, step=-1), dict(bob=-1, step=0)]
IDLE = [dict(bob=0), dict(bob=0, peck=1)]
GRAZE = [dict(bob=0, peck=6), dict(bob=0, peck=8), dict(bob=0, peck=6),
         dict(bob=0, peck=0)]
STATES = {"walk": (WALK, 120, True), "idle": (IDLE, 500, True),
          "graze": (GRAZE, 160, True)}
STATE_ORDER = ["walk", "idle", "graze"]


def states_for(states=None, held=None):
    return [s for s in STATE_ORDER if s in (states or STATE_ORDER)]


def draw_shadow():
    c = Canvas(FRAME, FRAME)
    c.row(12, 19, GROUND_Y, "SH")
    return c


def build_frames(species="chicken", states=None, held=None, worn=None):
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
