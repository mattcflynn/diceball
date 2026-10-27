"""
Mortal brains.

Pitcher: builds a zone (high cards out, low cards held as pitch cards), then picks a
location and pitch card from a count-aware softmax over difficulty and strike chance.

Batter: samples the pitcher's hidden hand from unseen cards, runs the same pitch policy
on each sample to get beliefs, then finds the dice allocation that maximizes expected
wOBA (exact DP over suit masks x reserve size x cards used x cells).
"""
import math
from collections import defaultdict
from itertools import combinations

from cardball.cards import deck, cells, suit, value
from cardball.rules import WOBA, bip_value, batter_bonus, batter_difficulty, command_bonus, contact_probs, p_strike
from cardball.game import row_of
from cardball.hand import power_value

# Rough MLB wOBA from each count
DEFAULT_COUNT_VALUES = {
    (0, 0): 0.318, (1, 0): 0.357, (2, 0): 0.408, (3, 0): 0.500,
    (0, 1): 0.275, (1, 1): 0.305, (2, 1): 0.345, (3, 1): 0.440,
    (0, 2): 0.210, (1, 2): 0.232, (2, 2): 0.268, (3, 2): 0.350,
}

# How much the pitcher wants a strike, by count
STRIKE_INTENT = {
    (0, 0): 0.62, (1, 0): 0.66, (2, 0): 0.74, (3, 0): 0.88,
    (0, 1): 0.56, (1, 1): 0.62, (2, 1): 0.68, (3, 1): 0.82,
    (0, 2): 0.40, (1, 2): 0.48, (2, 2): 0.56, (3, 2): 0.78,
}


def count_values(cfg):
    if not cfg.count_values:
        return DEFAULT_COUNT_VALUES
    return {tuple(int(x) for x in k.split("-")): v for k, v in cfg.count_values.items()}


def softmax(scores, temp):
    if not scores:
        return []
    m = max(scores)
    if temp <= 0:
        top = [1.0 if s == m else 0.0 for s in scores]
        t = sum(top)
        return [x / t for x in top]
    w = [math.exp((s - m) / temp) for s in scores]
    t = sum(w)
    return [x / t for x in w]


# ---------------------------------------------------------------- pitcher

MAX_CELLS = 5   # most cards the AI batter will spread dice over


def location_options(grid, hand, count, cfg):
    """
    Pitcher's mixed policy given the zone and the cards still in hand.
    Returns [(prob, cell, reveal_card, p_strike if taken, batter difficulty)].
    """
    if not hand or not grid:
        return [(1.0, None, None, 0.0, None)]
    fv = cfg.face_value
    zone = list(grid.values())
    by_value = {}
    for c in sorted(hand):
        by_value.setdefault(value(c, fv), c)
    w = cfg.command_weight * min(1.0, max(0.0, STRIKE_INTENT[count] + cfg.zone_bias))
    cands, scores = [], []
    for cell in sorted(grid):
        g = grid[cell]
        bonus, bb = command_bonus(g, zone, cfg), batter_bonus(g, zone, cfg)
        for v, r in by_value.items():
            diff = value(g, fv) - v
            ps = p_strike(diff, bonus, cfg.command_sides)
            d = batter_difficulty(diff, cfg, bonus=bb)
            cands.append((cell, r, ps, d))
            scores.append(d + w * ps)
    return [(pr, cell, r, ps, d) for (cell, r, ps, d), pr in zip(cands, softmax(scores, cfg.pitcher_temp))]


def choose_zone_cards(hand, cfg, rng):
    """Which cards go into the zone: the high ones, holding `pitcher_keep` low cards back."""
    if len(hand) < 2:
        return []
    k = max(1, min(cfg.max_grid, cfg.grid_size ** 2, len(hand) - cfg.pitcher_keep, len(hand) - 1))
    order = sorted(hand, key=lambda c: value(c, cfg.face_value), reverse=True)
    if rng.random() < cfg.grid_noise:
        rng.shuffle(order)
    return order[:k]


def pitcher_plan(hand, count, cfg, rng):
    """Returns (grid {cell: card}, reveal card, location cell)."""
    zone = choose_zone_cards(hand, cfg, rng)
    grid = dict(zip(rng.sample(cells(cfg), len(zone)), zone))
    remaining = [c for c in hand if c not in zone]
    opts = location_options(grid, remaining, count, cfg)
    pick = rng.choices(opts, weights=[o[0] for o in opts])[0]
    return grid, pick[2], pick[1]


# ---------------------------------------------------------------- batter

def batter_beliefs(view, cfg, rng):
    """Probability the pitch targets each card, strike chance, and the difficulty spread if contested."""
    grid, count = view["grid"], tuple(view["count"])
    seen = set(grid.values())
    if cfg.counts_cards:
        seen |= set(view["discards"])
    unseen = [c for c in deck(cfg) if c not in seen]
    n_hidden = min(len(unseen), view["hand_count"] + (1 if view["has_reveal"] else 0))

    target = defaultdict(float)
    contest = defaultdict(lambda: defaultdict(float))
    strike_by_cell = defaultdict(float)
    p_empty = p_strike_tot = 0.0
    read = view.get("read_row")
    # The pitcher plays its high cards, so the hidden ones are usually no higher than the lowest zone card
    floor = min((value(c, cfg.face_value) for c in grid.values()), default=99)
    low = [c for c in unseen if value(c, cfg.face_value) <= floor]
    samples = []
    for _ in range(max(1, cfg.belief_samples)):
        pool = low if len(low) >= n_hidden and rng.random() >= cfg.grid_noise else unseen
        opts = location_options(grid, rng.sample(pool, n_hidden), count, cfg)
        if read is not None:
            opts = [o for o in opts if o[1] is not None and row_of(o[1], cfg) == read]
        samples.append(opts)
    mass = sum(o[0] for opts in samples for o in opts) or 1.0
    for opts in samples:
        for prob, cell, _r, ps, d in opts:
            w = prob / mass
            if cell is None:
                p_empty += w
                continue
            target[cell] += w
            p_strike_tot += w * ps
            strike_by_cell[cell] += w * ps
            contest[cell][d] += w
    return {"target": dict(target), "contest": {c: dict(v) for c, v in contest.items()},
            "strike_by_cell": dict(strike_by_cell),
            "p_empty": p_empty, "p_strike": p_strike_tot}


NEG = -1e18


def _alloc_table(cells_, T, M, val):
    """dp[m][t] = best value spreading exactly t dice over exactly m of the cells."""
    dp = [[NEG] * (T + 1) for _ in range(M + 1)]
    dp[0][0] = 0.0
    hist = []
    for c in cells_:
        vals = [val(c, n) for n in range(T + 1)]
        new = [[NEG] * (T + 1) for _ in range(M + 1)]
        ch = [[0] * (T + 1) for _ in range(M + 1)]
        for m in range(M + 1):
            cur, prev_row = dp[m], dp[m - 1] if m else None
            for t in range(T + 1):
                best = cur[t] + vals[0] if cur[t] > NEG else NEG
                bn = 0
                if prev_row:
                    for n in range(1, t + 1):
                        pv = prev_row[t - n]
                        if pv > NEG and pv + vals[n] > best:
                            best, bn = pv + vals[n], n
                new[m][t], ch[m][t] = best, bn
        dp = new
        hist.append(ch)
    return dp, hist


def _backtrack(cells_, hist, m, t):
    alloc = {}
    for c, ch in zip(reversed(cells_), reversed(hist)):
        n = ch[m][t]
        if n:
            alloc[c] = n
            m, t = m - 1, t - n
    return alloc


def batter_decide(view, cfg, rng):
    """Returns (bets {cell: dice}, info). Empty bets = take."""
    grid = view["grid"]
    b, s = tuple(view["count"])
    V = count_values(cfg)
    strike_v = 0.0 if s == 2 else V[(b, s + 1)]
    ball_v = WOBA["BB"] if b == 3 else V[(b + 1, s)]
    foul_v = V[(b, s)] if s == 2 else strike_v
    whiff_v = strike_v

    bel = batter_beliefs(view, cfg, rng)
    ev_take = bel["p_strike"] * strike_v + (1 - bel["p_strike"]) * ball_v
    info = {"beliefs": bel, "ev_take": ev_take, "ev_swing": None}
    if not grid:
        return {}, info

    pool, sides = cfg.batter_dice, cfg.die_sides
    tie_play = cfg.tie_rule == "play"
    gcells = sorted(grid)
    play, foul, qsum = {}, {}, {}
    for c in gcells:
        q = bel["contest"].get(c, {})
        qsum[c] = sum(q.values())
        play[c], foul[c] = [0.0], [0.0]
        for n in range(1, pool + 1):
            pl = fo = 0.0
            for d, w in q.items():
                a, f = contact_probs(n, sides, d, cfg.one_whiffs, cfg.six_hits, tie_play)
                pl += w * a
                fo += w * f
            play[c].append(pl)
            foul[c].append(fo)
    rr = view.get("rerolls", 0)
    hand = cfg.power_system != "sum"
    B = {m: [bip_value(r, cfg, m) for r in range(pool + 1)] for m in range(1, MAX_CELLS + 1)} if not hand else None

    def bvec(m, k):
        if not hand:
            return B[m]
        left = rr - cfg.reroll_card_cost * (m - 1) - cfg.reroll_mix_penalty[k - 1]
        return [power_value(r, left, cfg, foul_v) for r in range(pool + 1)]
    tgt = bel["target"]

    def cell_val(c, n, bv):
        if n == 0:
            return tgt.get(c, 0.0) * whiff_v
        pl, fo = play[c][n], foul[c][n]
        return pl * bv + fo * foul_v + (qsum[c] - pl - fo) * whiff_v

    best_ev, best_alloc = ev_take, {}
    best_swing, best_swing_alloc = NEG, None

    def consider(ev, alloc_fn):
        nonlocal best_ev, best_alloc, best_swing, best_swing_alloc
        if ev > best_swing:
            best_swing, best_swing_alloc = ev, alloc_fn()
            if ev > best_ev:
                best_ev, best_alloc = ev, best_swing_alloc

    present = sorted({suit(card) for card in grid.values()})
    for k in range(1, len(present) + 1):
        for mask in combinations(present, k):
            mcells = [c for c in gcells if suit(grid[c]) in mask]
            M = min(len(mcells), MAX_CELLS)
            avail = {m: pool - cfg.mix_penalty[k - 1] - cfg.card_cost * (m - 1) for m in range(1, M + 1)}
            avail = {m: a for m, a in avail.items() if a >= m
                     and (not hand or cfg.reroll_card_cost * (m - 1) + cfg.reroll_mix_penalty[k - 1] <= rr)}
            if not avail:
                continue
            base = bel["p_empty"] * whiff_v + sum(tgt.get(c, 0.0) * whiff_v for c in gcells if c not in mcells)
            if cfg.power_rule == "reserve":
                for m, a in avail.items():
                    Bm = bvec(m, k)
                    for R in range(a - m + 1):
                        bv, t = Bm[R], a - R
                        dp, hist = _alloc_table(mcells, t, m, lambda c, n: cell_val(c, n, bv))
                        if dp[m][t] > NEG:
                            consider(dp[m][t] + base, lambda: _backtrack(mcells, hist, m, t))
            else:
                for m, a in avail.items():
                    Bm = bvec(m, k)
                    dp, hist = _alloc_table(mcells, a, m, lambda c, n: cell_val(c, n, Bm[a - n]))
                    t = max(range(m, a + 1), key=lambda i: dp[m][i])
                    if dp[m][t] > NEG:
                        consider(dp[m][t] + base, lambda: _backtrack(mcells, hist, m, t))
    info["ev_swing"] = best_swing if best_swing_alloc is not None else None
    if cfg.batter_temp > 0 and best_swing_alloc:
        # Noisy take/swing: logistic on the EV gap; the swing itself stays EV-optimal
        swing = rng.random() < _p_swing(best_swing - ev_take, cfg.batter_temp)
        best_alloc = best_swing_alloc if swing else {}
    return best_alloc, info


def _p_swing(gap, temp):
    x = max(-50.0, min(50.0, gap / temp))
    return 1.0 / (1.0 + math.exp(-x))
