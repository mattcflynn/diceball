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


def power_mod(cards, cfg):
    """Flat add to the power sum: hitter strength minus the cost of sitting on several cards."""
    return cfg.power_bonus - cfg.spread_power * max(0, cards - 1)


def bip_value(n, cfg, cards=1):
    """Expected wOBA of a ball in play hit with n power dice, having bet on `cards` cards."""
    probs = power_probs(n, cfg.die_sides, cfg.power_keep, tuple(cfg.power_thresholds), power_mod(cards, cfg))
    return sum(p * WOBA[o] for o, p in probs.items())


def contact_step(total, face, d, sides, one_whiffs, six_hits, tie_play):
    """One contact die. Returns (result, new total); result is "play", "whiff" or None (keep rolling)."""
    if face == 1 and one_whiffs:
        return "whiff", total
    if face == sides and six_hits:
        return "play", total + face
    total += face
    if total > d or (tie_play and total == d):
        return "play", total
    return None, total


@lru_cache(maxsize=None)
def contact_probs(n, sides, d, one_whiffs, six_hits, tie_play):
    """(P in play, P foul) rolling up to n dice one at a time vs difficulty d; the rest is a whiff."""
    play = whiff = 0.0
    alive = {0: 1.0}
    for _ in range(n):
        nxt = {}
        for t, p in alive.items():
            for f in range(1, sides + 1):
                res, nt = contact_step(t, f, d, sides, one_whiffs, six_hits, tie_play)
                if res == "play":
                    play += p / sides
                elif res == "whiff":
                    whiff += p / sides
                else:
                    nxt[nt] = nxt.get(nt, 0.0) + p / sides
        alive = nxt
    return play, sum(alive.values())


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


def batter_difficulty(diff, cfg, bonus=0):
    return max(cfg.difficulty_floor, diff + bonus)


def suits_bet(bets, grid):
    return {suit(grid[c]) for c, n in bets.items() if n > 0}


def bet_penalty(bets, grid, cfg):
    """Dice lost for spreading: card_cost per card beyond the first, plus mix_penalty by suits."""
    cards = sum(1 for n in bets.values() if n > 0)
    if not cards:
        return 0
    return cfg.card_cost * (cards - 1) + cfg.mix_penalty[len(suits_bet(bets, grid)) - 1]


def reroll_cost(bets, grid, cfg):
    """Re-rolls lost for spreading (re-roll power systems)."""
    cards = sum(1 for n in bets.values() if n > 0)
    if not cards or cfg.power_system == "sum":
        return 0
    return cfg.reroll_card_cost * (cards - 1) + cfg.reroll_mix_penalty[len(suits_bet(bets, grid)) - 1]


def validate_bets(bets, grid, cfg, rerolls=None):
    for c, n in bets.items():
        if n < 0:
            raise ValueError("negative bet")
        if n and c not in grid:
            raise ValueError(f"bet on empty cell {c}")
    if sum(bets.values()) > cfg.batter_dice - bet_penalty(bets, grid, cfg):
        raise ValueError("bets exceed dice after spread penalty")
    if rerolls is not None and reroll_cost(bets, grid, cfg) > rerolls:
        raise ValueError("not enough re-rolls to spread that bet")


def roll(rng, n, sides):
    return [rng.randint(1, sides) for _ in range(n)]


def resolve_pitch(grid, reveal, location, bets, cfg, rng, rerolls=None):
    """
    Resolve one pitch. grid: {cell: card}, reveal: card or None, location: cell or None,
    bets: {cell: dice}, rerolls: the batter's re-rolls left (hand system).
    Returns a record of everything that happened.
    """
    bets = {c: n for c, n in bets.items() if n > 0}
    rerolls = cfg.rerolls if rerolls is None else rerolls
    validate_bets(bets, grid, cfg, rerolls if cfg.power_system != "sum" else None)
    target = grid.get(location) if location else None
    pen = bet_penalty(bets, grid, cfg)
    swing = bool(bets)
    rec = {
        "reveal": reveal, "location": location, "target": target, "strike": None, "p_strike": 0.0,
        "bets": bets, "swing": swing, "penalty": pen, "difficulty": None, "parts": None,
        "command_roll": None, "command_bonus": 0, "difference": None,
        "contact_roll": [], "contact_sum": None, "power_roll": [], "power_total": None,
        "power_dice": 0, "power_mod": 0, "event": None, "outcome": None, "whiff_reason": None,
        "reroll_cost": reroll_cost(bets, grid, cfg), "rerolls_used": 0, "hand": None,
    }
    if target is not None and reveal is not None:
        diff = difference(target, reveal, cfg)
        bonus = command_bonus(target, list(grid.values()), cfg)
        rec.update(difference=diff, command_bonus=bonus, p_strike=p_strike(diff, bonus, cfg.command_sides))

    # The strike roll only happens on a take; a swing goes straight to contact
    if not swing:
        strike = False
        if target is not None and reveal is not None:
            r = rng.randint(1, cfg.command_sides)
            strike = is_strike_roll(r, rec["difference"], rec["command_bonus"], cfg.command_sides)
            rec["command_roll"] = r
        rec["strike"] = strike
        rec["event"] = "called_strike" if strike else "ball"
        return rec

    n = bets.get(location, 0) if location else 0
    if target is None or n == 0:
        rec["event"], rec["whiff_reason"] = "whiff", "missed"
        return rec
    bb = batter_bonus(target, list(grid.values()), cfg)
    d = batter_difficulty(rec["difference"], cfg, bonus=bb)
    rec["difficulty"] = d
    rec["parts"] = {"zone": value(target, cfg.face_value), "reveal": value(reveal, cfg.face_value),
                    "suit_bonus": bb, "total": d}
    # Roll the bet dice one at a time; stop on a 1 (whiff), a 6 (hit) or once the total beats d
    total, res = 0, None
    for _ in range(n):
        face = rng.randint(1, cfg.die_sides)
        rec["contact_roll"].append(face)
        res, total = contact_step(total, face, d, cfg.die_sides, cfg.one_whiffs, cfg.six_hits, cfg.tie_rule == "play")
        if res:
            break
    rec["contact_sum"] = total
    rec["contact_dice"] = n
    if res == "whiff":
        rec["event"], rec["whiff_reason"] = "whiff", "ones"
    elif res == "play":
        avail = cfg.batter_dice - pen
        pdice = avail - sum(bets.values()) if cfg.power_rule == "reserve" else avail - n
        rec["power_dice"] = pdice
        if cfg.power_system == "climb":
            from cardball.hand import play_climb
            c = play_climb(rng, pdice, rerolls - rec["reroll_cost"], cfg)
            rec.update(power_roll=[x["face"] for x in c["rolls"]], climb=c["rolls"], climb_length=c["length"],
                       rerolls_used=c["used"], event="in_play", outcome=c["outcome"])
            return rec
        if cfg.power_system == "hand":
            from cardball.hand import play_hand
            h = play_hand(rng, pdice, rerolls - rec["reroll_cost"], cfg)
            rec.update(power_roll=h["dice"], power_first=h["first"], reroll_steps=h["rerolls"],
                       rerolls_used=len(h["rerolls"]), hand=h["hand"])
            if h["outcome"] == "FOUL":
                rec["event"] = "foul"
            else:
                rec["event"], rec["outcome"] = "in_play", h["outcome"]
            return rec
        rec["power_roll"] = roll(rng, pdice, cfg.die_sides)
        rec["power_mod"] = power_mod(len(bets), cfg)
        rec["power_total"] = power_sum(rec["power_roll"], cfg.power_keep) + rec["power_mod"]
        rec["event"] = "in_play"
        rec["outcome"] = power_outcome(rec["power_total"], cfg.power_thresholds)
    else:
        rec["event"] = "foul"
    return rec
