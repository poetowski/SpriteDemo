"""Parametric bird rig: 4 facings, and every one of them in the air.

Same contract as the other three rigs - 32x32 frame, one anchor on the ground
row, the same build_frames shape - so a bird flows through the pipeline, the
atlas and the depth sorting with no special cases. It is a fourth rig rather
than a flag on the quadruped because a bird shares no part with one: no barrel
carried on four legs, no head on the end of a neck out front, and the thing
that makes it read at all is a pair of wings, which nothing else here has.

**A flying thing is drawn at the top of the frame and anchored at the bottom
of it.** That is the whole trick, and it costs nothing: the anchor is the point
the sprite is placed and sorted by, not the point the art has to touch, so
leaving twenty pixels of air between the shadow on the ground and the bird
above it puts the bird in the sky while it still stands in the tile the engine
thinks it is in. The shadow is what sells it - a bird with no shadow reads as a
sprite that forgot to land - and it is small and tight, because the thing
casting it is a long way up.

Species differ by silhouette flags plus a palette variant, the way the animals
do. Every flag is read with .get, so adding one leaves the others alone.
"""

from gen.palette import Canvas

FRAME = 32
GROUND_Y = 29
ANCHOR = (16, GROUND_Y)
ATLAS = "actors"               # the same frame size, so the same sheet
COLS = 6
FACINGS = ["down", "left", "right", "up"]

BODY_Y = 15                    # the spine, fourteen pixels off the ground

SPECIES = {
    # A grey heron. What makes one unmistakable at this size is not the
    # plumage but the proportions: a dagger of a bill out in front, the neck
    # folded back into the shoulders rather than stretched out, and the legs
    # trailing behind the tail - which is the one thing no other flying
    # silhouette does.
    "heron": {"bill": 5, "crest": True, "trail_legs": 6, "span": 10},
}


# --------------------------------------------------------------- side view ---
def _side_wing(c, sx, sy, lift, span):
    """The near wing, seen from the side. Raised and lowered it is broadside
    and shows its whole area; level it is edge-on and shows almost none. A
    wing drawn the same size in all three reads as a plank hinged to a bird,
    so the level frame is deliberately the thin one."""
    if lift == 0:
        c.rect(sx - span + 2, sy - 1, sx + 1, sy, "AB")
        c.row(sx - span + 2, sx - 2, sy - 1, "ABL")
        c.set(sx - span + 2, sy, "AF")                   # the dark tip
        return
    up = lift > 0
    for i in range(span):
        x = sx - i
        # The further out along the wing, the further from the body it gets -
        # a swept curve, not a triangle with a straight edge.
        top = sy - (i * 2) // 3 - (1 if i else 0)
        depth = max(1, 3 - i // 4)
        if up:
            c.rect(x, top - depth, x, top, "AB")
            c.set(x, top - depth, "ABL")
        else:
            c.rect(x, 2 * sy - top, x, 2 * sy - top + depth, "AB")
            c.set(x, 2 * sy - top + depth, "ABS")
    tip = sx - span + 1
    c.rect(tip, sy - (span * 2) // 3 - 3 if up else sy + (span * 2) // 3,
           tip + 1, sy - (span * 2) // 3 if up else sy + (span * 2) // 3 + 3,
           "AF")                                         # the primaries


def draw_side(shape, pose):
    """In profile, facing right."""
    c = Canvas(FRAME, FRAME)
    y = BODY_Y + pose.get("bob", 0)
    lift = pose.get("wing", 0)
    span = shape.get("span", 8)

    if shape.get("trail_legs"):                          # behind the tail, and
        n = shape["trail_legs"]                          # the giveaway in the
        c.row(12 - n, 12, y + 2, "AH")                   # whole silhouette
        c.row(12 - n, 12, y + 3, "AH")
        c.row(12 - n - 1, 12 - n + 1, y + 3, "AFS")      # the feet, trailing

    c.rect(11, y - 1, 19, y + 2, "AB")                   # the body
    c.row(12, 18, y - 2, "AB")
    c.row(13, 17, y - 2, "ABL")                          # lit along the back
    c.row(12, 18, y + 2, "ABS")                          # and shaded beneath
    c.rect(9, y, 12, y + 1, "AB")                        # the tail
    c.set(9, y + 1, "ABS")

    hx = 20
    c.rect(hx, y - 2, hx + 1, y + 1, "ABL")              # the folded neck
    c.rect(hx + 1, y - 3, hx + 3, y - 1, "ABL")          # and the head on it
    c.set(hx + 2, y - 2, "EY")
    if shape.get("crest"):                               # a plume off the back
        c.row(hx - 1, hx + 1, y - 4, "AF")               # of the skull
        c.set(hx - 2, y - 3, "AF")
    bill = shape.get("bill", 4)
    c.row(hx + 4, hx + 3 + bill, y - 1, "HN")            # the dagger
    c.row(hx + 4, hx + 2 + bill, y, "HNS")

    _side_wing(c, 16, y - 2 if lift >= 0 else y, lift, span)
    return c.outline()


# ------------------------------------------------------- front / back view ---
def _spread(c, y, lift, span):
    """Both wings, from in front or behind.

    Head on, a wing is edge-on and has no area to show, so drawn honestly it
    is a line - and a line each side of an upright body is a scarecrow, which
    is exactly what the first version of this view was. What fixes it is the
    thing the view is actually seen from, which is slightly *above*: from
    there a wing sweeps back as it goes out, and that curve is what says bird
    rather than cross. So every wing carries a fixed backward sweep, deepest
    at the shoulder and tapering to a point, and the beat only decides how far
    the tips are flicked up or down over the top of it."""
    for side in (-1, 1):
        sx = 15 if side < 0 else 16
        for i in range(span):
            x = sx + side * (i + 1)
            t = (i + 1) / span                           # 0 shoulder, 1 tip
            dy = round(2.6 * t * t - lift * t * 2.5)
            th = 3 - round(t * 2)                        # 3px at the base, 1 out
            c.rect(x, y + dy, x, y + dy + th - 1, "AB")
            c.set(x, y + dy, "ABL")                      # lit along the leading
            if i >= span - 3:                            # edge, dark primaries
                c.rect(x, y + dy, x, y + dy + th - 1, "AF")


def draw_front(shape, pose):
    """Coming at you. The bill points at the camera, so it is a stub and
    cannot carry the view - what does is the spread and the hunch: a heron
    flies with its neck folded, so head on it is a head sunk into shoulders."""
    c = Canvas(FRAME, FRAME)
    y = BODY_Y + pose.get("bob", 0)
    lift = pose.get("wing", 0)
    _spread(c, y, lift, shape.get("span", 8))
    c.rect(13, y - 2, 18, y + 3, "AB")                   # the body, end on
    c.row(14, 17, y - 3, "AB")
    c.row(14, 17, y - 3, "ABL")
    c.row(14, 17, y + 3, "ABS")
    c.rect(14, y + 4, 17, y + 4, "ABS")                  # the tail under it
    c.rect(14, y - 5, 17, y - 3, "ABL")                  # head, sunk in
    c.set(14, y - 4, "EY")
    c.set(17, y - 4, "EY")
    if shape.get("crest"):
        c.row(14, 17, y - 6, "AF")
    c.rect(15, y - 3, 16, y - 2, "HN")                   # the bill, foreshortened
    c.row(15, 16, y - 2, "HNS")
    return c.outline()


def draw_back(shape, pose):
    """Going away: a tail where the head was, and the legs trailing at you -
    which is the one view that shows what a heron does with them."""
    c = Canvas(FRAME, FRAME)
    y = BODY_Y + pose.get("bob", 0)
    lift = pose.get("wing", 0)
    _spread(c, y, lift, shape.get("span", 8))
    c.rect(13, y - 3, 18, y + 2, "AB")                   # the back
    c.row(14, 17, y - 4, "AB")
    c.row(14, 17, y - 4, "ABL")
    c.rect(14, y + 2, 17, y + 4, "ABS")                  # the tail, spread
    c.row(14, 17, y + 4, "AF")
    if shape.get("crest"):
        c.row(15, 16, y - 5, "AF")
    if shape.get("trail_legs"):
        # Together, not either side of the tail. Drawn apart they picked up an
        # outline each, the two of them closed into one dark block under the
        # body, and the bird came back wearing trousers. A heron trails its
        # legs as a single line with the feet turned out at the end of it.
        n = shape["trail_legs"]
        c.rect(15, y + 5, 16, y + 4 + n, "AH")
        c.row(13, 14, y + 3 + n, "AFS")
        c.row(17, 18, y + 3 + n, "AFS")
    return c.outline()


# ----------------------------------------------------------------- poses ----
# A wingbeat is not symmetrical: the down-stroke is the one that does the work,
# so it is the one drawn hardest, and the recovery passes through level twice.
FLY = [
    dict(wing=2, bob=-1),
    dict(wing=0, bob=0),
    dict(wing=-2, bob=1),
    dict(wing=0, bob=0),
]
# Hanging on the air rather than standing on the ground: the wings stay out and
# the whole bird rises and falls a pixel. This is what a bird does when it is
# not going anywhere, and it is the pose the engine reaches for most.
HOVER = [
    dict(wing=1, bob=-1),
    dict(wing=0, bob=0),
]
# The engine's third state is whatever a creature does when it stops moving and
# is not idling, and it calls it "graze" because the first thing that used it
# was a sheep. For a bird it is a long coast: wings held flat and still, losing
# height a pixel at a time. No other name for it exists in game/main.js, and
# inventing one here would mean teaching the engine about birds.
COAST = [
    dict(wing=0, bob=0),
    dict(wing=0, bob=1),
]
STATES = {"walk": (FLY, 120, True), "idle": (HOVER, 420, True),
          "graze": (COAST, 520, True)}
STATE_ORDER = ["walk", "idle", "graze"]


def states_for(states=None, held=None):
    """Same contract as the other rigs. A bird carries nothing, so `held` is
    accepted and ignored rather than being a special case downstream."""
    return [s for s in STATE_ORDER if s in (states or STATE_ORDER)]


def draw_shadow():
    """Small and tight. The animals' shadow is the width of the animal because
    the animal is standing on it; this one is cast from twenty pixels up, so
    scaling it to the wingspan would put a dark stain the width of the tile
    under a bird you can see daylight through."""
    c = Canvas(FRAME, FRAME)
    c.row(14, 17, GROUND_Y, "SH")
    c.row(15, 16, GROUND_Y + 1, "SH")
    return c


def build_frames(species="heron", states=None, held=None, worn=None):
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
