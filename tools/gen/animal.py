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
ATLAS = "actors"               # the same frame size, so the same sheet
COLS = 6
FACINGS = ["down", "left", "right", "up"]

FOOT_Y = 28                    # last hoof row
LEG_TOP = 23

# Flags are read with .get, so adding one to a new species leaves the others
# alone rather than needing a False written into every entry.
SPECIES = {
    "sheep": {"wool": True, "horns": False, "beard": False},
    "goat": {"wool": False, "horns": True, "beard": True},
    "boar": {"wool": False, "horns": False, "beard": False,
             "bristles": True, "tusks": True},
    # "tall" lifts the body and lengthens the legs without moving the hooves,
    # which is the whole difference between a deer and a sheep in silhouette:
    # the same barrel carried higher off the ground. The rack does the rest.
    "elk": {"wool": False, "horns": False, "beard": False,
            "tall": 3, "antlers": True, "mane": True, "rump": True},
    # A bear is not a recoloured boar, and the difference is all silhouette:
    # "bulk" deepens and widens the barrel, "hump" puts the rise over the
    # shoulders that nothing else here has, and the round ears sit on top of
    # the skull instead of behind it. Flat paws rather than hooves, a stub of
    # a tail, and a pale blunt muzzle do the rest.
    "bear": {"wool": False, "horns": False, "beard": False,
             "bulk": 1, "hump": True, "round_ears": True, "paws": True,
             "stub_tail": True, "snout": True},
    # The zebra is the horse the rig never had, and it needs exactly two
    # things to be one: the bars, and a mane that stands up instead of lying
    # along the neck.
    "zebra": {"wool": False, "horns": False, "beard": False,
              "tall": 2, "stripes": True, "crest": True},
    # A jackal is a dog, and at 32px a dog is its ears. They stand up and come
    # to a point, which nothing else on this rig does - the bear's are round
    # and on top, the rest are little flaps behind the eye. The brush and the
    # dark saddle are what stop it reading as a small deer once it moves.
    "jackal": {"wool": False, "horns": False, "beard": False,
               "prick_ears": True, "brush": True, "saddle": True,
               "paws": True},
}


# --------------------------------------------------------------- side view ---
def _side_legs(c, offsets, bob, tall=0, paws=False):
    """Four legs at fixed x, swung by per-leg offsets. Hooves stay grounded -
    a taller animal has longer legs, not floating ones."""
    for base, dx in zip((9, 12, 17, 20), offsets):
        x = base + dx
        lift = 1 if dx > 0 else 0
        c.rect(x, LEG_TOP + bob - tall, x + 1, FOOT_Y - 1 - lift,
               "ABS" if base < 15 else "AB")
        # A paw is wider than the leg and flat on the ground; a hoof is neither.
        c.rect(x - (1 if paws else 0), FOOT_Y - lift, x + 1, FOOT_Y - lift, "AH")


def _side_body(c, bob, shape):
    tall = shape.get("tall", 0)
    bulk = shape.get("bulk", 0)
    top = 18 + bob - tall - bulk
    belly = 24 + bob - tall + bulk
    c.rect(8 - bulk, top + 1, 21 + bulk, belly, "AB")
    c.row(10 - bulk, 19 + bulk, top, "AB")
    c.row(9 - bulk, 20 + bulk, belly, "ABS")    # underside in shade
    c.row(11, 18, top, "ABL")                   # lit along the spine
    if shape.get("hump"):
        # Over the shoulders, which are at the head end - so it rises towards
        # the neck and falls away to the rump, and the animal reads as leaning
        # forward even standing still.
        for x, up in ((15, 1), (16, 2), (17, 2), (18, 2), (19, 2), (20, 1)):
            c.col(x, top - up, top, "AB")
        c.row(16, 19, top - 2, "ABL")
    if shape["wool"]:                           # woolly back breaks the outline
        for x in (10, 13, 16, 19):
            c.set(x, top - 1, "ABL")
        c.set(8, top + 1, "ABL")
    if shape.get("bristles"):                   # a raised ridge along the back,
        for x in range(9, 21, 2):               # which is what makes a boar
            c.set(x, top - 1, "AFS")            # read as bristling and not fat
        c.set(21, top, "AFS")
    if shape.get("stripes"):                    # bars round the barrel. Every
        for i, x in enumerate(range(10, 22, 4)):    # third pixel was a black
            c.col(x, top + 1 + (i % 2), belly - 1, "AFS")   # horse; every
            c.set(x + 1, top + 1 + (i % 2), "AFS")          # fourth is a zebra
    if shape.get("saddle"):
        # A stripe down the spine and a little way onto the shoulder, no more.
        # Painted over the whole back it was a dark slab with legs, and the
        # animal lost the sandy colour that is the point of it.
        c.row(9, 20, top, "AFS")
        c.row(10, 19, top + 1, "AFS")
        c.col(16, top, top + 3, "AFS")
        c.col(17, top, top + 3, "AFS")
    if shape.get("rump"):                       # the pale patch a deer shows
        c.rect(8, top + 2, 11, belly - 1, "AR")  # you as it goes away
    if shape.get("brush"):
        # Thick and carried low. A one-pixel tail on a lean animal reads as a
        # piece of wire, and the brush is half of why a jackal is not a fox.
        for i, y in enumerate(range(19 + bob - tall, 25 + bob - tall)):
            c.rect(5 - (i > 2), y, 8 - (i > 3), y, "AB")
            c.set(5 - (i > 2), y, "ABS")
            c.set(8 - (i > 3), y, "AFS")            # a dark edge where it
        c.col(8, 19 + bob - tall, 21 + bob - tall, "AFS")   # leaves the rump
    elif shape.get("stub_tail"):                  # barely there, and that is the
        c.rect(7 - bulk, 21 + bob, 8 - bulk, 22 + bob, "ABS")     # look of it
    else:
        c.rect(6, 19 + bob - tall, 7, 21 + bob - tall, "ABS")     # tail
        if not shape["wool"]:
            c.rect(6, 19 + bob - tall, 7, 20 + bob - tall, "AF")  # thin dark


def _side_head(c, bob, shape, down=0, lunge=0):
    """down > 0 lowers the head towards the grass; lunge > 0 throws it forward,
    which is the whole of a quadruped's attack - it has nothing else to hit
    you with."""
    tall = shape.get("tall", 0)
    hy = 15 + bob + down - tall - shape.get("bulk", 0)
    hx = 22 + lunge
    # The neck spans from the shoulder to wherever the head is, so lowering the
    # head to graze - or throwing it forward - stretches the neck instead of
    # detaching it.
    c.rect(20, 18 + bob - tall, hx, hy + 4, "AB")
    c.rect(hx, hy, hx + 4, hy + 5, "AF")        # head
    c.row(hx + 1, hx + 4, hy + 5, "AFS")
    c.set(hx + 4, hy + 3, "AFS")                # muzzle
    if shape.get("snout"):                      # pale, blunt and dropped: the
        c.rect(hx + 2, hy + 3, hx + 4, hy + 5, "HN")   # front half of a bear's
        c.row(hx + 2, hx + 4, hy + 5, "HNS")           # face is all muzzle
    c.set(hx + 3, hy + 2, "OL")                 # eye
    if shape.get("round_ears"):                 # on top of the skull, not
        c.rect(hx, hy - 3, hx + 2, hy - 1, "AF")       # behind it
        c.set(hx, hy - 3, "AFS")
        c.set(hx + 2, hy - 3, "AFS")
    elif shape.get("prick_ears"):
        # A triangle standing clear of the skull. At 32px a dog is its ears,
        # so this is the one part worth three pixels of width.
        c.rect(hx - 1, hy - 1, hx + 2, hy - 1, "AF")
        c.rect(hx - 1, hy - 2, hx + 1, hy - 2, "AF")
        c.rect(hx - 1, hy - 3, hx, hy - 3, "AF")
        c.set(hx - 1, hy - 4, "AF")
        c.set(hx, hy - 2, "AB")                     # lit inside the cup
        c.set(hx - 1, hy - 4, "AFS")
    else:
        c.rect(hx - 1, hy + 1, hx, hy + 1, "AF")    # ear
    if shape["horns"]:
        c.rect(hx, hy - 2, hx + 1, hy - 1, "HN")
        c.set(hx + 2, hy - 2, "HNS")
    if shape.get("stripes"):                    # short ones down the neck
        for i in range(3):
            c.col(20 + i * 2, hy + 3 + i, hy + 5 + i, "AFS")
        c.set(hx + 2, hy + 1, "AFS")
    if shape.get("crest"):                      # a mane standing up off it
        for i, x in enumerate(range(19, 24)):
            c.set(x, hy - 1, "AFS")
            c.set(x, hy, "AFS" if i % 2 else "AF")
    if shape.get("mane"):                       # shaggy throat, under the neck
        for i, x in enumerate(range(19, 24)):
            c.col(x, hy + 4, hy + 6 + (i % 2), "AFS")
    if shape.get("antlers"):
        # One beam sweeping back over the shoulders, with tines of different
        # lengths standing off it. Every pixel of it is a step from the one
        # before, starting on the skull: drawn as a spray of pixels two apart
        # it came out as a detached shrub floating behind the head, and drawn
        # as tines of one length it came out as a comb. Laid down after the
        # body, so a lowered head puts the rack along the back and not inside
        # it.
        c.set(hx + 2, hy - 2, "HN")                  # brow tine, forward
        c.set(hx + 2, hy - 3, "HN")
        beam = ((hx + 1, hy - 1), (hx, hy - 2), (hx - 1, hy - 3),
                (hx - 2, hy - 4), (hx - 3, hy - 4), (hx - 4, hy - 5),
                (hx - 5, hy - 5), (hx - 6, hy - 6))
        for i, (bx, by) in enumerate(beam):
            c.set(bx, by, "HNS" if i < 2 else "HN")  # darker where it is skull
        for (tx, ty), length in zip((beam[2], beam[4], beam[6], beam[7]),
                                    (3, 4, 3, 2)):
            for i in range(length):
                c.set(tx + (i + 1) // 2, ty - 1 - i, "HN")
    if shape["beard"]:
        c.rect(hx + 2, hy + 6, hx + 3, hy + 7, "AFS")
    if shape.get("tusks"):                      # curving up clear of the muzzle
        c.set(hx + 4, hy + 4, "HN")
        c.set(hx + 5, hy + 3, "HN")
        c.set(hx + 5, hy + 2, "HNS")


def draw_side(shape, pose):
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    _side_legs(c, pose.get("legs", (0, 0, 0, 0)), bob, shape.get("tall", 0),
               shape.get("paws", False))
    _side_body(c, bob, shape)
    _side_head(c, bob, shape, pose.get("head_down", 0), pose.get("lunge", 0))
    return c.outline()


# ------------------------------------------------------- front / back view ---
def _front_legs(c, spread, bob, tall=0, paws=False):
    for x in (12 + spread, 18 - spread):
        c.rect(x, LEG_TOP + bob - tall, x + 1, FOOT_Y - 1, "ABS")
        c.rect(x - (1 if paws else 0), FOOT_Y, x + 1, FOOT_Y, "AH")


def draw_front(shape, pose):
    """Facing the camera: head drawn over the body, ears out to the sides."""
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    tall = shape.get("tall", 0)
    down = pose.get("head_down", 0) // 3       # head-on, the drop barely reads
    bulk = shape.get("bulk", 0)
    _front_legs(c, pose.get("spread", 0), bob, tall, shape.get("paws", False))
    c.rect(10 - bulk, 16 + bob - tall, 21 + bulk, 24 + bob - tall, "AB")  # body
    c.row(11 - bulk, 20 + bulk, 15 + bob - tall, "AB")
    c.row(12, 19, 15 + bob - tall, "ABL")
    if shape["wool"]:
        for x in (11, 14, 17, 20):
            c.set(x, 14 + bob - tall, "ABL")
    if shape.get("bristles"):
        for x in range(11, 21, 2):
            c.set(x, 14 + bob - tall, "AFS")
    if shape.get("stripes"):
        for x in range(11, 21, 4):
            c.col(x, 16 + bob - tall, 24 + bob - tall, "AFS")
    if shape.get("hump"):                   # head-on it is shoulders, not a
        c.rect(12, 13 + bob - tall, 19, 15 + bob - tall, "AB")   # peak
        c.row(13, 18, 13 + bob - tall, "ABL")

    hy = 18 + bob + down - tall
    if shape["horns"]:                                  # above the head, so they
        c.rect(12, hy - 4, 13, hy - 2, "HN")            # clear the body outline
        c.rect(18, hy - 4, 19, hy - 2, "HN")
    if shape.get("antlers"):
        # Head-on, a rack is wider than the animal - which is the view you get
        # when an elk has decided about you. It goes out well before it goes
        # up, and the tines stand clear of the beam: a pair of beams that only
        # rise read as ears, and beam and tines run together into a solid curve
        # read as an ox.
        for side, bx in ((-1, 12), (1, 19)):
            beam = [(bx + side * i, hy - 1 - (i + 1) // 2) for i in range(6)]
            for px, py in beam:
                c.set(px, py, "HN")
            for i, length in ((2, 3), (4, 4), (5, 2)):
                px, py = beam[i]
                c.col(px, py - length, py - 1, "HN")
    if shape.get("round_ears"):
        # Clear of the shoulders, not level with the eyes: drawn at the head's
        # own height they sat under the hump and the bear lost the one part of
        # its outline you can read across a field.
        top = 11 + bob - tall
        c.rect(10, top, 12, top + 2, "AF")
        c.rect(19, top, 21, top + 2, "AF")
        c.set(10, top, "AFS")
        c.set(21, top, "AFS")
    elif shape.get("prick_ears"):
        # Wide at the base and outside the skull rather than on top of it:
        # drawn two pixels wide against the head they vanished into it, and a
        # jackal without ears is a small dog of no particular kind.
        for i in range(5):
            c.rect(10 + (i < 2), hy - 8 + i, 12, hy - 8 + i, "AF")
            c.rect(19, hy - 8 + i, 21 - (i < 2), hy - 8 + i, "AF")
        for i in range(3):                              # lit inside the cup
            c.set(11, hy - 6 + i, "AB")
            c.set(20, hy - 6 + i, "AB")
        c.set(11, hy - 8, "AFS")
        c.set(20, hy - 8, "AFS")
    else:
        c.rect(10, hy + 1, 11, hy + 2, "AF")            # ears
        c.rect(20, hy + 1, 21, hy + 2, "AF")
    c.rect(12, hy, 19, hy + 6, "AF")                    # head over the body
    c.row(13, 18, hy + 6, "AFS")
    if shape.get("snout"):
        c.rect(14, hy + 3, 17, hy + 6, "HN")            # the pale muzzle again
        c.row(14, 17, hy + 6, "HNS")
    else:
        c.rect(14, hy + 4, 17, hy + 6, "AFS")           # muzzle
    if shape.get("stripes"):
        # Head-on the head covers the body, so bars on the barrel are hidden
        # and the animal comes at you as a blank white box. A zebra's face is
        # barred too - down the forehead and along the cheeks - and that is
        # what has to carry it from this angle.
        # The forehead only: the eye row stays clear, because bars down the
        # cheeks ran into the eyes and the face became one dark smudge, and
        # the muzzle is already dark enough to finish the head from below.
        for x in (13, 16, 18):
            c.set(x, hy, "AFS")
            c.set(x, hy + 1, "AFS")
        c.set(14, hy, "AFS")
    c.set(13, hy + 2, "OL")
    c.set(18, hy + 2, "OL")
    if shape.get("crest"):                              # the mane, end on
        c.rect(15, hy - 3, 16, hy - 1, "AFS")
    if shape.get("mane"):
        c.rect(13, hy + 7, 18, hy + 8, "AFS")
    if shape["beard"]:
        c.rect(15, hy + 7, 16, hy + 8, "AFS")
    if shape.get("tusks"):                              # one either side of the
        c.set(13, hy + 6, "HN")                         # muzzle, seen head-on,
        c.set(13, hy + 7, "HNS")                        # which is the view you
        c.set(18, hy + 6, "HN")                         # get when it charges
        c.set(18, hy + 7, "HNS")
    return c.outline()


def draw_back(shape, pose):
    """Facing away: rump and tail, ears just visible over the shoulders."""
    c = Canvas(FRAME, FRAME)
    bob = pose.get("bob", 0)
    tall = shape.get("tall", 0)
    bulk = shape.get("bulk", 0)
    _front_legs(c, pose.get("spread", 0), bob, tall, shape.get("paws", False))
    c.rect(10 - bulk, 16 + bob - tall, 21 + bulk, 25 + bob - tall, "AB")  # body
    c.row(11 - bulk, 20 + bulk, 15 + bob - tall, "AB")
    c.row(12, 19, 15 + bob - tall, "ABL")
    c.row(11 - bulk, 20 + bulk, 25 + bob - tall, "ABS")
    if shape.get("hump"):
        c.rect(11, 13 + bob - tall, 20, 15 + bob - tall, "AB")
        c.row(13, 18, 13 + bob - tall, "ABL")
    if shape["wool"]:
        for x in (11, 14, 17, 20):
            c.set(x, 14 + bob - tall, "ABL")
    if shape.get("bristles"):
        for x in range(11, 21, 2):
            c.set(x, 14 + bob - tall, "AFS")
    if shape.get("stripes"):
        # The rump is where a zebra's bars are boldest and they run across it,
        # not down it - and drawn down it they land under the tail and vanish.
        # So: horizontal, and either side of where the tail hangs.
        for i, y in enumerate(range(17 + bob - tall, 25 + bob - tall, 2)):
            c.row(11, 14 - (i % 2), y, "AFS")
            c.row(17 + (i % 2), 20, y, "AFS")
    if shape.get("crest"):
        c.rect(15, 12 + bob - tall, 16, 14 + bob - tall, "AFS")
    if shape.get("rump"):                  # going away is the view a deer gives
        c.rect(13, 18 + bob - tall, 18, 23 + bob - tall, "AR")
        for x, y in ((13, 18), (18, 18), (13, 23), (18, 23)):
            c.set(x, y + bob - tall, "AB")     # corners off, so it is a patch

    if shape.get("saddle"):
        c.rect(14, 15 + bob - tall, 17, 22 + bob - tall, "AFS")
    if shape.get("brush"):                     # end on it is the widest thing
        for i, y in enumerate(range(17 + bob - tall, 25 + bob - tall)):
            w = 2 - (i > 5)
            c.rect(15 - w, y, 16 + w, y, "ABS")
            c.set(15 - w, y, "AFS")
            c.set(16 + w, y, "AFS")
    elif shape.get("stub_tail"):
        c.rect(15, 20 + bob - tall, 16, 21 + bob - tall, "ABS")
    else:
        c.rect(15, 16 + bob - tall, 16, 20 + bob - tall, "ABS")  # tail
        if not shape["wool"]:
            c.rect(15, 15 + bob - tall, 16, 19 + bob - tall, "AF")

    # From behind the head is hidden, so grazing reads through the body bob only.
    if shape.get("round_ears"):                              # still the widest
        c.rect(10, 11 + bob - tall, 12, 13 + bob - tall, "AF")   # thing on it
        c.rect(19, 11 + bob - tall, 21, 13 + bob - tall, "AF")
    elif shape.get("prick_ears"):
        for i in range(4):
            c.rect(11 + i // 3, 10 + bob - tall + i, 12, 10 + bob - tall + i, "AF")
            c.rect(19, 10 + bob - tall + i, 20 - i // 3, 10 + bob - tall + i, "AF")
        c.set(11, 10 + bob - tall, "AFS")
        c.set(20, 10 + bob - tall, "AFS")
    else:
        c.rect(11, 13 + bob - tall, 12, 14 + bob - tall, "AF")   # ear tips, over
        c.rect(19, 13 + bob - tall, 20, 14 + bob - tall, "AF")   # the shoulders
    if shape["horns"]:
        c.rect(13, 12 + bob - tall, 14, 13 + bob - tall, "HN")
        c.rect(17, 12 + bob - tall, 18, 13 + bob - tall, "HN")
    if shape.get("antlers"):               # the rack still clears the shoulders
        top = 12 + bob - tall
        for side, bx in ((-1, 12), (1, 19)):
            beam = [(bx + side * i, top - (i + 1) // 2) for i in range(5)]
            for px, py in beam:
                c.set(px, py, "HN")
            for i, length in ((2, 3), (4, 2)):
                px, py = beam[i]
                c.col(px, py - length, py - 1, "HN")
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
ATTACK = [                      # head down and thrown forward: a goring
    dict(bob=0, legs=(0, 0, 0, 0), spread=0, head_down=1),
    dict(bob=-1, legs=(2, -1, -1, 1), spread=1, head_down=4, lunge=2),
    dict(bob=0, legs=(3, -2, -2, 2), spread=2, head_down=6, lunge=4),
    dict(bob=-1, legs=(1, 0, 0, 1), spread=1, head_down=3, lunge=1),
]
# state -> (poses, ms per frame, loops). Everything an animal does by itself
# loops; a blow is a one-shot, because the engine times how long the creature
# stands still to throw it from the length of this animation.
STATES = {"walk": (WALK, 150, True), "idle": (IDLE, 600, True),
          "graze": (GRAZE, 380, True), "attack": (ATTACK, 110, False)}
STATE_ORDER = ["walk", "idle", "graze", "attack"]


def states_for(states=None, held=None):
    """Same contract as the biped rig. Animals hold nothing, so `held` is
    accepted and ignored rather than being a special case downstream."""
    return [s for s in STATE_ORDER if s in (states or STATE_ORDER)]


def draw_shadow():
    c = Canvas(FRAME, FRAME)
    c.row(8, 22, GROUND_Y, "SH")
    c.row(10, 20, GROUND_Y + 1, "SH")
    return c


def build_frames(species="sheep", states=None, held=None, worn=None):
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
