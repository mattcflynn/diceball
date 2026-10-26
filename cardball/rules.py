"""Pure rules: difficulty, dice odds, power outcomes, and single-pitch resolution."""
from collections import Counter
from functools import lru_cache
from itertools import combinations_with_replacement
from math import factorial

from cardball.cards import suit, value

# FanGraphs-style linear weights (recent seasons)
WOBA = {"BB": 0.69, "SINGLE": 0.88, "DOUBLE": 1.25, "TRIPLE": 1.59, "HR": 2.04, "OUT": 0.0}
HITS = ("SINGLE", "DOUBLE", "TRIPLE", "HR")
BIP_OUTCOMES = ("OUT",) + HITS


@lru_cache(maxsize=None)
def sum_pmf(n, sides):
    """P(sum of n dice = k) as a tuple indexed by k."""
    pmf = [1.0]
    for _ in range(n):
        nxt = [0.0] * (len(pmf) + sides)
        for k, p in enumerate(pmf):
            if p:
                for f in range(1, sides + 1):
                    nxt[k + f] += p / sides
        pmf = nxt
    return tuple(pmf)


def power_outcome(total, thresholds):
    t1, t2, t3, t4 = thresholds
    if total >= t4:
        return "HR"
    if total >= t3:
        return "TRIPLE"
    if total >= t2:
        return "DOUBLE"
    if total >= t1:
        return "SINGLE"
    return "OUT"


@lru_cache(maxsize=None)
def keep_high_pmf(n, sides, keep):
    """P(sum of the highest `keep` of n dice = k). keep=0 means all dice."""
    if keep <= 0 or keep >= n:
        return sum_pmf(n, sides)
    pmf = [0.0] * (keep * sides + 1)
    total = sides ** n
    for faces in combinations_with_replacement(range(1, sides + 1), n):
        ways = factorial(n)
        for c in Counter(faces).values():
            ways //= factorial(c)
        pmf[sum(faces[-keep:])] += ways / total
    return tuple(pmf)


def power_sum(roll, keep):
    return sum(sorted(roll, reverse=True)[:keep]) if keep > 0 else sum(roll)


@lru_cache(maxsize=None)
def power_probs(n, sides, keep, thresholds, bonus):
    pmf = keep_high_pmf(n, sides, keep)
    out = dict.fromkeys(BIP_OUTCOMES, 0.0)
    for k, p in enumerate(pmf):
        if p:
            out[power_outcome(k + bonus, thresholds)] += p
    return out


def bip_value(n, cfg):
    """Expected wOBA of a ball in play hit with n power dice."""
    probs = power_probs(n, cfg.die_sides, cfg.power_keep, tuple(cfg.power_thresholds), cfg.power_bonus)
    return sum(p * WOBA[o] for o, p in probs.items())


@lru_cache(maxsize=None)
def _sum_pmf_no_ones(n, sides):
    """P(no die shows 1 and the sum = k), indexed by k."""
    pmf = [1.0]
    for _ in range(n):
        nxt = [0.0] * (len(pmf) + sides)
        for k, p in enumerate(pmf):
            if p:
                for f in range(2, sides + 1):
                    nxt[k + f] += p / sides
        pmf = nxt
    return tuple(pmf)


@lru_cache(maxsize=None)
def contact_probs(n, sides, d, ones, tie_play):
    """(P in play, P foul) for n contact dice vs difficulty d; the rest is a whiff on 1s."""
    if n <= 0:
        return 0.0, 0.0
    if ones == "any":
        pmf = _sum_pmf_no_ones(n, sides)
    else:
        pmf = list(sum_pmf(n, sides))
        if ones == "all":
            pmf[n] -= (1 / sides) ** n
    play = sum(p for k, p in enumerate(pmf) if k > d or (tie_play and k == d))
    return play, sum(pmf) - play


def suit_bonus(zone_cards, s, cfg):
    n = sum(1 for c in zone_cards if suit(c) == s)
    return n * cfg.suit_bonus_per_card if n >= cfg.suit_bonus_min else 0


def difference(zone_card, reveal, cfg):
    return value(zone_card, cfg.face_value) - value(reveal, cfg.face_value)


def command_bonus(zone_card, zone_cards, cfg):
    sb = suit_bonus(zone_cards, suit(zone_card), cfg) if cfg.bonus_applies in ("both", "pitcher") else 0
    return sb + cfg.command_bonus


def batter_bonus(zone_card, zone_cards, cfg):
    return suit_bonus(zone_cards, suit(zone_card), cfg) if cfg.bonus_applies in ("both", "batter") else 0


@lru_cache(maxsize=None)
def p_strike(diff, bonus, sides):
    """Pitcher's strike roll: 1 = ball, max face = strike, otherwise roll + bonus >= diff."""
    hits = sum(1 for r in range(1, sides + 1) if r == sides or (r != 1 and r + bonus >= diff))
    return hits / sides


def is_strike_roll(r, diff, bonus, sides):
    return r == sides or (r != 1 and r + bonus >= diff)


def batter_difficulty(diff, cfg, chase=False, bonus=0):
    return max(cfg.difficulty_floor, diff + bonus) + (cfg.chase_penalty if chase else 0)


def suits_bet(bets, grid):
    return {suit(grid[c]) for c, n in bets.items() if n > 0}


def bet_penalty(bets, grid, cfg):
    """Dice lost for spreading: card_cost per card beyond the first, plus mix_penalty by suits."""
    cards = sum(1 for n in bets.values() if n > 0)
    if not cards:
        return 0
    return cfg.card_cost * (cards - 1) + cfg.mix_penalty[len(suits_bet(bets, grid)) - 1]


def validate_bets(bets, grid, cfg):
    for c, n in bets.items():
        if n < 0:
            raise ValueError("negative bet")
        if n and c not in grid:
            raise ValueError(f"bet on empty cell {c}")
    if sum(bets.values()) > cfg.batter_dice - bet_penalty(bets, grid, cfg):
        raise ValueError("bets exceed dice after spread penalty")


def roll(rng, n, sides):
    return [rng.randint(1, sides) for _ in range(n)]


def _contact_whiffs(dice, ones):
    if ones == "any":
        return 1 in dice
    if ones == "all":
        return all(v == 1 for v in dice)
    return False


def resolve_pitch(grid, reveal, location, bets, cfg, rng):
    """
    Resolve one pitch. grid: {cell: card}, reveal: card or None, location: cell or None,
    bets: {cell: dice}. Returns a record of everything that happened.
    """
    bets = {c: n for c, n in bets.items() if n > 0}
    validate_bets(bets, grid, cfg)
    target = grid.get(location) if location else None
    pen = bet_penalty(bets, grid, cfg)
    swing = bool(bets)
    rec = {
        "reveal": reveal, "location": location, "target": target, "strike": False,
        "bets": bets, "swing": swing, "penalty": pen, "difficulty": None, "parts": None,
        "command_roll": None, "command_bonus": 0, "difference": None,
        "contact_roll": [], "contact_sum": None, "power_roll": [], "power_total": None,
        "power_dice": 0, "event": None, "outcome": None, "whiff_reason": None,
    }
    if target is not None and reveal is not None:
        diff = difference(target, reveal, cfg)
        bonus = command_bonus(target, list(grid.values()), cfg)
        r = rng.randint(1, cfg.command_sides)
        rec.update(difference=diff, command_bonus=bonus, command_roll=r,
                   strike=is_strike_roll(r, diff, bonus, cfg.command_sides))
    strike = rec["strike"]

    if not swing:
        rec["event"] = "called_strike" if strike else "ball"
        return rec

    n = bets.get(location, 0) if location else 0
    if target is None or n == 0:
        rec["event"], rec["whiff_reason"] = "whiff", "missed"
        return rec
    if not strike and cfg.chase_rule == "whiff":
        rec["event"], rec["whiff_reason"] = "whiff", "chase"
        return rec

    bb = batter_bonus(target, list(grid.values()), cfg)
    d = batter_difficulty(rec["difference"], cfg, chase=not strike, bonus=bb)
    rec["difficulty"] = d
    rec["parts"] = {"zone": value(target, cfg.face_value), "reveal": value(reveal, cfg.face_value),
                    "suit_bonus": bb, "chase": cfg.chase_penalty if not strike else 0, "total": d}
    rec["contact_roll"] = roll(rng, n, cfg.die_sides)
    s = sum(rec["contact_roll"])
    rec["contact_sum"] = s
    if _contact_whiffs(rec["contact_roll"], cfg.batter_ones):
        rec["event"], rec["whiff_reason"] = "whiff", "ones"
    elif s > d or (s == d and cfg.tie_rule == "play"):
        avail = cfg.batter_dice - pen
        pdice = avail - sum(bets.values()) if cfg.power_rule == "reserve" else avail - n
        rec["power_dice"] = pdice
        rec["power_roll"] = roll(rng, pdice, cfg.die_sides)
        rec["power_total"] = power_sum(rec["power_roll"], cfg.power_keep) + cfg.power_bonus
        rec["event"] = "in_play"
        rec["outcome"] = power_outcome(rec["power_total"], cfg.power_thresholds)
    else:
        rec["event"] = "foul"
    return rec
