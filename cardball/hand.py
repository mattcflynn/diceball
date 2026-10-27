"""
Yahtzee-style power: after contact the batter rolls up to `hand_dice` power dice and
assembles a hand. Each re-roll re-rolls one die. The batter plays re-rolls to maximize
expected wOBA (exact DP over face counts).
"""
from functools import lru_cache
from itertools import combinations_with_replacement
from math import factorial

from cardball.rules import WOBA

HANDS = ("none", "pair", "two_pair", "trips", "straight", "full_house", "four_kind", "five_kind")
HAND_NAME = {"none": "nothing", "pair": "one pair", "two_pair": "two pair", "trips": "three of a kind",
             "straight": "straight", "full_house": "full house", "four_kind": "four of a kind",
             "five_kind": "five of a kind"}
HAND_OUTCOMES = ("OUT", "FOUL", "SINGLE", "DOUBLE", "TRIPLE", "HR")


def parse_map(s):
    """'trips=SINGLE,straight=DOUBLE' -> {hand: outcome}; unlisted hands are outs."""
    out = dict.fromkeys(HANDS, "OUT")
    for part in s.split(","):
        if not part.strip():
            continue
        h, o = (x.strip() for x in part.split("="))
        o = o.upper().replace("1B", "SINGLE").replace("2B", "DOUBLE").replace("3B", "TRIPLE")
        if h not in HANDS or o not in HAND_OUTCOMES:
            raise ValueError(f"bad hand_map entry {part!r}")
        out[h] = o
    return out


def hands_of(c, run=5):
    """Every hand present in face counts c."""
    h = {"none"}
    pairs = sum(1 for x in c if x >= 2)
    top = max(c)
    if pairs:
        h.add("pair")
    if pairs >= 2:
        h.add("two_pair")
    if top >= 3:
        h.add("trips")
        if sorted(c)[-2] >= 2:
            h.add("full_house")
    if top >= 4:
        h.add("four_kind")
    if top >= 5:
        h.add("five_kind")
    if any(all(c[i:i + run]) for i in range(len(c) - run + 1)):
        h.add("straight")
    return h


@lru_cache(maxsize=None)
def roll_dist(m, sides):
    """Distribution of face-count vectors for m dice."""
    out = {}
    for combo in combinations_with_replacement(range(sides), m):
        c = [0] * sides
        for f in combo:
            c[f] += 1
        w = factorial(m)
        for x in c:
            w //= factorial(x)
        out[tuple(c)] = w / sides ** m
    return out


def _bump(c, f, g):
    k = list(c)
    k[f] -= 1
    k[g] += 1
    return tuple(k)


@lru_cache(maxsize=None)
def _solver(map_items, sides, foul_v):
    mp = dict(map_items)
    val = {h: (foul_v if o == "FOUL" else WOBA[o]) for h, o in mp.items()}

    @lru_cache(maxsize=None)
    def best(c):
        return max(hands_of(c), key=lambda h: (val[h], HANDS.index(h)))

    @lru_cache(maxsize=None)
    def choice(c, r):
        """(value, face to re-roll or None)."""
        v, pick = val[best(c)], None
        if r:
            for f in range(sides):
                if c[f]:
                    e = sum(choice(_bump(c, f, g), r - 1)[0] for g in range(sides)) / sides
                    if e > v + 1e-12:
                        v, pick = e, f
        return v, pick

    @lru_cache(maxsize=None)
    def dist(n, r):
        """P(outcome) and expected re-rolls used, starting from a fresh roll of n dice."""
        out, used = {}, 0.0

        def go(c, r, p, k):
            nonlocal used
            pick = choice(c, r)[1]
            if pick is None:
                o = mp[best(c)]
                out[o] = out.get(o, 0.0) + p
                used += p * k
                return
            for g in range(sides):
                go(_bump(c, pick, g), r - 1, p / sides, k + 1)

        for c, p in roll_dist(n, sides).items():
            go(c, r, p, 0)
        return out, used

    return best, choice, dist


def solver(cfg, foul_v=0.0):
    return _solver(tuple(sorted(parse_map(cfg.hand_map).items())), cfg.die_sides, round(foul_v, 3))


def hand_probs(n, rerolls, cfg, foul_v=0.0):
    """P(outcome) for a ball in play with n power dice (capped at hand_dice) and `rerolls` left."""
    n = min(n, cfg.hand_dice)
    if n <= 0:
        return {"OUT": 1.0}
    return solver(cfg, foul_v)[2](n, max(0, rerolls))[0]


def hand_value(n, rerolls, cfg, foul_v=0.0):
    probs = hand_probs(n, rerolls, cfg, foul_v)
    return sum(p * (foul_v if o == "FOUL" else WOBA[o]) for o, p in probs.items())


def play_hand(rng, n, rerolls, cfg, foul_v=0.0):
    """Roll n power dice (capped) and play re-rolls. Returns a record for the pitch log."""
    n = min(n, cfg.hand_dice)
    sides = cfg.die_sides
    dice = [rng.randint(1, sides) for _ in range(n)]
    first = list(dice)
    if n <= 0:
        return {"first": [], "dice": [], "rerolls": [], "hand": "none", "outcome": "OUT"}
    best, choice, _ = solver(cfg, foul_v)
    steps = []
    r = rerolls
    while True:
        c = tuple(dice.count(f + 1) for f in range(sides))
        pick = choice(c, r)[1]
        if pick is None:
            break
        i = dice.index(pick + 1)
        new = rng.randint(1, sides)
        steps.append({"index": i, "old": dice[i], "new": new})
        dice[i] = new
        r -= 1
    c = tuple(dice.count(f + 1) for f in range(sides))
    h = best(c)
    return {"first": first, "dice": dice, "rerolls": steps, "hand": h,
            "outcome": parse_map(cfg.hand_map)[h]}


# ---------------------------------------------------------------- climb

def climb_outcome(length, strict, cfg):
    """Streak length -> outcome. A double-length streak that strictly climbs is a triple."""
    s1, s2, hr = cfg.climb_ladder
    if length >= hr:
        return "HR"
    if length >= s2:
        return "TRIPLE" if strict and length == s2 else "DOUBLE"
    return "SINGLE" if length >= s1 else "OUT"


@lru_cache(maxsize=None)
def _climb_probs(n, r, sides, ladder):
    """Exact P(outcome): dice rolled one at a time, the streak lives while each die >= the last.
    A re-roll re-rolls the die that broke the streak."""
    class C:
        climb_ladder = ladder
    out = {}

    @lru_cache(maxsize=None)
    def go(last, length, strict, left, rr):
        if left == 0:
            return ((climb_outcome(length, strict, C), 1.0),)
        acc = {}
        for f in range(1, sides + 1):
            if f >= last:
                res = go(f, length + 1, strict and f > last, left - 1, rr)
            elif rr:
                res = go(last, length, strict, left, rr - 1)
            else:
                res = ((climb_outcome(length, strict, C), 1.0),)
            for o, p in res:
                acc[o] = acc.get(o, 0.0) + p / sides
        return tuple(acc.items())

    for f in range(1, sides + 1):
        for o, p in go(f, 1, True, n - 1, r):
            out[o] = out.get(o, 0.0) + p / sides
    return out


def climb_probs(n, rerolls, cfg):
    n = min(n, cfg.hand_dice)
    if n <= 0:
        return {"OUT": 1.0}
    return _climb_probs(n, max(0, rerolls), cfg.die_sides, tuple(cfg.climb_ladder))


def play_climb(rng, n, rerolls, cfg):
    """Roll the climb. Returns {rolls: [{face, status}], length, strict, outcome, used}."""
    n = min(n, cfg.hand_dice)
    rolls, last, length, strict, used = [], 0, 0, True, 0
    while length < n:
        f = rng.randint(1, cfg.die_sides)
        if f >= last:
            strict = strict and (length == 0 or f > last)
            rolls.append({"face": f, "status": "up"})
            last, length = f, length + 1
        elif used < rerolls:
            rolls.append({"face": f, "status": "rerolled"})
            used += 1
        else:
            rolls.append({"face": f, "status": "break"})
            break
    return {"rolls": rolls, "length": length, "strict": strict, "used": used,
            "outcome": climb_outcome(length, strict, cfg) if n > 0 else "OUT"}


# ---------------------------------------------------------------- dispatch

def power_value(n, rerolls, cfg, foul_v=0.0):
    """Expected wOBA of a ball in play for the re-roll power systems."""
    if cfg.power_system == "climb":
        return sum(p * WOBA[o] for o, p in climb_probs(n, rerolls, cfg).items())
    return hand_value(n, rerolls, cfg, foul_v)
