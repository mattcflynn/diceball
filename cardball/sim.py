"""
Cardball simulator: AI vs AI at-bats, stats vs the 2026 MLB season.

    uv run -m cardball.sim run -n 2000
    uv run -m cardball.sim run -n 2000 --set batter_dice=9 draw_per_pitch=2
    uv run -m cardball.sim sweep batter_dice 8 9 10 11 -n 1000
    uv run -m cardball.sim tune -n 2000 --levers t1 t2 t3 t4 zone_bias --out cardball/presets/tuned.json
"""
import argparse
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

from cardball import config as config_mod
from cardball.ai import pitcher_plan, batter_decide
from cardball.cards import PITCH_CODE, suit
from cardball.game import AtBat, woba_of
from cardball.rules import HITS

# 2026 regular season, AL+NL combined (StatMuse totals). Rows marked ~ are recent-season approximations.
TARGETS = {
    "BA": (0.244, 0.012), "OBP": (0.319, 0.015), "SLG": (0.401, 0.020), "OPS": (0.719, 0.030),
    "K%": (0.221, 0.020), "BB%": (0.089, 0.012), "HR/PA": (0.029, 0.006), "BABIP": (0.291, 0.015),
    "wOBA": (0.315, 0.012), "P/PA": (3.90, 0.25),
}
APPROX = {"HR/PA", "BABIP", "wOBA", "P/PA"}
# Per-PA outcome mix consistent with the targets above
TARGET_MIX = {"BB": 0.089, "K": 0.221, "SINGLE": 0.140, "DOUBLE": 0.043, "TRIPLE": 0.0035, "HR": 0.029}
TARGET_MIX["OUT"] = 1 - sum(TARGET_MIX.values())
DISCIPLINE_TARGETS = {"Zone%": 0.49, "Swing%": 0.475, "Chase%": 0.285, "Z-Swing%": 0.67, "Contact%": 0.765}
PITCH_MIX_TARGET = {"FB": 0.53, "BR": 0.29, "OS": 0.18}


# ---------------------------------------------------------------- simulation

def play_at_bat(cfg, rng):
    ab = AtBat(cfg, rng)
    while not ab.over:
        grid, reveal, loc = pitcher_plan(ab.hand, ab.count, cfg, rng)
        ab.commit_pitch(grid, reveal, loc)
        bets, _ = batter_decide(ab.public(), cfg, rng)
        ab.resolve(bets)
    return ab


def _empty_tally():
    return {
        "pa": 0, "results": Counter(), "pitches": 0, "events": Counter(),
        "zone": 0, "swings": 0, "z_swings": 0, "o_swings": 0, "contact": 0,
        "mix": Counter(), "grid_by_pitch": defaultdict(lambda: [0, 0]),
        "cells_bet": 0, "dice_bet": 0, "penalty": 0, "reserve_on_swing": 0, "whiff_reason": Counter(),
        "power_hist": Counter(), "count_woba": defaultdict(lambda: [0.0, 0]),
    }


def _tally_ab(t, ab, cfg):
    t["pa"] += 1
    t["results"][ab.result] += 1
    w = woba_of(ab.result)
    for c in set(ab.counts_seen):
        cw = t["count_woba"][f"{c[0]}-{c[1]}"]
        cw[0] += w
        cw[1] += 1
    for i, p in enumerate(ab.pitches, 1):
        t["pitches"] += 1
        t["events"][p["event"]] += 1
        if p["target"]:
            t["mix"][PITCH_CODE[suit(p["target"])]] += 1
        if p["whiff_reason"]:
            t["whiff_reason"][p["whiff_reason"]] += 1
        g = t["grid_by_pitch"][min(i, 6)]
        g[0] += len(p["grid"])
        g[1] += 1
        ps = p["p_strike"]   # swings skip the strike roll, so zone stats use the expected strike chance
        t["zone"] += ps
        if p["swing"]:
            t["swings"] += 1
            t["z_swings"] += ps
            t["o_swings"] += 1 - ps
            t["cells_bet"] += len(p["bets"])
            dice = sum(p["bets"].values())
            t["dice_bet"] += dice
            t["penalty"] += p["penalty"]
            t["reserve_on_swing"] += cfg.batter_dice - p["penalty"] - dice
        if p["event"] in ("foul", "in_play"):
            t["contact"] += 1
        if p["event"] == "in_play":
            t["power_hist"][p["power_total"]] += 1


def _merge(a, b):
    for k, v in b.items():
        if isinstance(v, Counter):
            a[k].update(v)
        elif k == "grid_by_pitch" or k == "count_woba":
            for kk, (x, y) in v.items():
                a[k][kk][0] += x
                a[k][kk][1] += y
        else:
            a[k] += v
    return a


def _worker(args):
    cfg_dict, n, seed = args
    cfg = config_mod.apply_overrides(config_mod.Config(), cfg_dict)
    rng = random.Random(seed)
    t = _empty_tally()
    for _ in range(n):
        _tally_ab(t, play_at_bat(cfg, rng), cfg)
    # plain dicts for pickling
    t["grid_by_pitch"] = dict(t["grid_by_pitch"])
    t["count_woba"] = dict(t["count_woba"])
    return t


def simulate(cfg, n, seed=None, workers=None, progress=False):
    """Run n at-bats across processes. Returns a stats dict (JSON-safe)."""
    workers = workers or max(1, (os.cpu_count() or 2) - 1)
    seed = random.randrange(1 << 30) if seed is None else seed
    chunks = max(workers * 4, 1)
    sizes = [n // chunks + (1 if i < n % chunks else 0) for i in range(chunks)]
    jobs = [(config_mod.to_dict(cfg), s, seed + i) for i, s in enumerate(sizes) if s]
    total = _empty_tally()
    t0 = time.time()
    done = 0
    if workers == 1:
        results = map(_worker, jobs)
    else:
        ex = ProcessPoolExecutor(max_workers=workers)
        results = ex.map(_worker, jobs)
    for job, part in zip(jobs, results):
        _merge(total, part)
        done += job[1]
        if progress:
            print(f"\r  simulating {done}/{n} at-bats", end="", file=sys.stderr, flush=True)
    if workers != 1:
        ex.shutdown()
    if progress:
        print(f"\r  {n} at-bats in {time.time() - t0:.1f}s" + " " * 20, file=sys.stderr)
    return summarize(total)


def summarize(t):
    pa = t["pa"]
    r = t["results"]
    bb, ks, kl = r["BB"], r["K_S"], r["K_L"]
    h1, h2, h3, hr = (r[x] for x in HITS)
    out = r["OUT"]
    h = h1 + h2 + h3 + hr
    ab = pa - bb
    k = ks + kl
    tb = h1 + 2 * h2 + 3 * h3 + 4 * hr
    bip_nohr = ab - k - hr
    woba = (0.69 * bb + 0.88 * h1 + 1.25 * h2 + 1.59 * h3 + 2.04 * hr) / pa
    pitches = t["pitches"]
    sw = t["swings"]
    stats = {
        "BA": h / ab if ab else 0, "OBP": (h + bb) / pa, "SLG": tb / ab if ab else 0,
        "K%": k / pa, "BB%": bb / pa, "HR/PA": hr / pa,
        "BABIP": (h - hr) / bip_nohr if bip_nohr else 0, "wOBA": woba, "P/PA": pitches / pa,
    }
    stats["OPS"] = stats["OBP"] + stats["SLG"]
    zone = t["zone"]
    disc = {
        "Zone%": zone / pitches, "Swing%": sw / pitches,
        "Chase%": t["o_swings"] / (pitches - zone) if pitches > zone else 0,
        "Z-Swing%": t["z_swings"] / zone if zone else 0,
        "Contact%": t["contact"] / sw if sw else 0,
    }
    mix_total = sum(t["mix"].values()) or 1
    return {
        "pa": pa, "pitches": pitches,
        "outcomes": {"BB": bb, "K_S": ks, "K_L": kl, "SINGLE": h1, "DOUBLE": h2, "TRIPLE": h3, "HR": hr, "OUT": out},
        "stats": stats, "discipline": disc,
        "events": {e: c / pitches for e, c in t["events"].items()},
        "mix": {p: t["mix"][p] / mix_total for p in ("FB", "BR", "OS")},
        "usage": {
            "zone_cards_by_pitch": {str(i): g[0] / g[1] for i, g in sorted(t["grid_by_pitch"].items())},
            "cells_per_swing": t["cells_bet"] / sw if sw else 0,
            "dice_bet_per_swing": t["dice_bet"] / sw if sw else 0,
            "penalty_per_swing": t["penalty"] / sw if sw else 0,
            "reserve_per_swing": t["reserve_on_swing"] / sw if sw else 0,
            "whiff_reason_per_swing": {k: v / sw for k, v in t["whiff_reason"].items()} if sw else {},
        },
        "power_hist": {str(k): v for k, v in sorted(t["power_hist"].items())},
        "count_woba": {c: s / n for c, (s, n) in sorted(t["count_woba"].items()) if n},
    }


# ---------------------------------------------------------------- calibration

LOSS_KEYS = {"BA": 1.0, "OBP": 1.0, "SLG": 1.0, "K%": 1.0, "BB%": 1.0, "HR/PA": 1.0, "P/PA": 0.25}
TUNE_STEPS = {
    "t1": 1, "t2": 1, "t3": 1, "t4": 1, "zone_bias": 0.05, "batter_eye": 0.1, "batter_temp": 0.02, "pitcher_temp": 0.5,
    "batter_dice": 1, "hand_size": 1, "draw_per_pitch": 1, "power_bonus": 1, "suit_bonus_per_card": 1,
    "pitcher_keep": 1, "grid_noise": 0.05, "command_bonus": 1, "command_weight": 1.0,
    "card_cost": 1, "suit_bonus_min": 1,
}


def loss(stats):
    return sum(w * ((stats[k] - TARGETS[k][0]) / TARGETS[k][1]) ** 2 for k, w in LOSS_KEYS.items())


def _step(cfg, lever, delta):
    """cfg with one lever nudged, or None if the move is invalid."""
    if lever[0] == "t" and lever[1:].isdigit():
        th = list(cfg.power_thresholds)
        th[int(lever[1:]) - 1] += delta
        if th != sorted(th) or th[0] < 1 or th[0] == th[1]:
            return None
        return config_mod.apply_overrides(cfg, {"power_thresholds": th})
    v = getattr(cfg, lever) + delta
    if isinstance(v, float):
        v = round(v, 3)
    if v < 0 or (lever in ("grid_noise",) and v > 1):
        return None
    try:
        return config_mod.apply_overrides(cfg, {lever: v})
    except ValueError:
        return None


def tune(cfg, n, levers, seed=0, workers=None, rounds=8):
    """Coordinate descent on the stat-line loss. Same seed for every eval (common random numbers)."""
    def evaluate(c):
        return simulate(c, n, seed=seed, workers=workers)

    res = evaluate(cfg)
    best = loss(res["stats"])
    print(f"  start loss {best:.2f}", file=sys.stderr)
    for rnd in range(1, rounds + 1):
        improved = False
        for lever in levers:
            for sign in (1, -1):
                while True:
                    cand = _step(cfg, lever, sign * TUNE_STEPS.get(lever, 1))
                    if cand is None:
                        break
                    r = evaluate(cand)
                    l = loss(r["stats"])
                    if l >= best:
                        break
                    cfg, res, best, improved = cand, r, l, True
                    st = r["stats"]
                    print(f"  r{rnd} {lever}{'+' if sign > 0 else '-'} loss {best:6.2f} | th {tuple(cfg.power_thresholds)} "
                          f"zb {cfg.zone_bias:+.2f} | BA {st['BA']:.3f} OBP {st['OBP']:.3f} SLG {st['SLG']:.3f} "
                          f"K {st['K%']:.1%} BB {st['BB%']:.1%} HR {st['HR/PA']:.1%}", file=sys.stderr)
        if not improved:
            break
    return cfg, res


# ---------------------------------------------------------------- output

def _flag(v, target, tol):
    d = v - target
    return "✓" if abs(d) <= tol else ("↑" if d > 0 else "↓") + f" {d:+.3f}"


def report(res, title="CARDBALL"):
    pa = res["pa"]
    lines = [f"\n{title} — {pa:,} PA, {res['pitches']:,} pitches", ""]
    lines.append(f"  {'Outcome':<12}{'Game':>8}{'MLB':>9}")
    o = res["outcomes"]
    rows = [("BB", o["BB"], TARGET_MIX["BB"]), ("K swinging", o["K_S"], None), ("K looking", o["K_L"], None),
            ("K total", o["K_S"] + o["K_L"], TARGET_MIX["K"]),
            ("Single", o["SINGLE"], TARGET_MIX["SINGLE"]), ("Double", o["DOUBLE"], TARGET_MIX["DOUBLE"]),
            ("Triple", o["TRIPLE"], TARGET_MIX["TRIPLE"]), ("HR", o["HR"], TARGET_MIX["HR"]),
            ("Out in play", o["OUT"], TARGET_MIX["OUT"])]
    for name, c, tgt in rows:
        lines.append(f"  {name:<12}{c / pa:>8.1%}{(f'{tgt:.1%}' if tgt is not None else ''):>9}")

    lines += ["", f"  {'Stat':<12}{'Game':>8}{'2026':>9}   "]
    for k, (tgt, tol) in TARGETS.items():
        v = res["stats"][k]
        fmt = ".1%" if k.endswith("%") or k == "HR/PA" else (".2f" if k == "P/PA" else ".3f")
        mark = "~" if k in APPROX else " "
        lines.append(f"  {k:<12}{format(v, fmt):>8}{format(tgt, fmt):>8}{mark}  {_flag(v, tgt, tol)}")

    lines += ["", f"  {'Discipline':<12}{'Game':>8}{'MLB~':>9}"]
    for k, tgt in DISCIPLINE_TARGETS.items():
        lines.append(f"  {k:<12}{res['discipline'][k]:>8.1%}{tgt:>9.0%}")

    lines += ["", f"  {'Pitch mix':<12}{'Game':>8}{'MLB~':>9}"]
    for k, tgt in PITCH_MIX_TARGET.items():
        name = {"FB": "♠ Fastball", "BR": "♣ Breaking", "OS": "♦ Off-speed"}[k]
        lines.append(f"  {name:<12}{res['mix'][k]:>8.1%}{tgt:>9.0%}")

    u = res["usage"]
    zc = "  ".join(f"#{k}:{v:.1f}" for k, v in u["zone_cards_by_pitch"].items())
    lines += ["", f"  Zone cards by pitch #   {zc}",
              f"  Per swing: {u['cells_per_swing']:.2f} cells, {u['dice_bet_per_swing']:.1f} dice bet, "
              f"{u['penalty_per_swing']:.2f} lost to spread, {u['reserve_per_swing']:.1f} power dice",
              "  Whiffs per swing: " + ", ".join(f"{k} {v:.1%}" for k, v in sorted(u["whiff_reason_per_swing"].items()))]
    ev = res["events"]
    lines.append("  Pitch events: " + ", ".join(f"{k} {ev.get(k, 0):.1%}" for k in
                                                 ("ball", "called_strike", "whiff", "foul", "in_play")))
    return "\n".join(lines)


SWEEP_COLS = ("BA", "OBP", "SLG", "K%", "BB%", "HR/PA", "P/PA")


def sweep_row(label, res):
    st = res["stats"]
    cells = []
    for k in SWEEP_COLS:
        v = st[k]
        cells.append(f"{v:>7.1%}" if k.endswith("%") or k == "HR/PA" else (f"{v:>7.2f}" if k == "P/PA" else f"{v:>7.3f}"))
    return f"  {label:<14}" + "".join(cells)


def _parse_sets(items):
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        out[k] = v
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cardball.sim")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "sweep", "tune"):
        p = sub.add_parser(name)
        p.add_argument("-n", type=int, default=2000)
        p.add_argument("--config", help="JSON preset to start from")
        p.add_argument("--set", nargs="*", help="lever=value overrides")
        p.add_argument("--seed", type=int)
        p.add_argument("--workers", type=int)
        p.add_argument("--json", action="store_true", help="print raw stats JSON")
        if name == "sweep":
            p.add_argument("lever")
            p.add_argument("values", nargs="+")
        if name == "tune":
            p.add_argument("--levers", nargs="+", default=["t1", "t2", "t3", "t4", "zone_bias"],
                           help="t1..t4 = power thresholds; any numeric lever")
            p.add_argument("--rounds", type=int, default=8)
            p.add_argument("--out", help="write tuned preset JSON here")
    a = ap.parse_args(argv)
    cfg = config_mod.load(a.config, _parse_sets(a.set))

    if a.cmd == "run":
        res = simulate(cfg, a.n, a.seed, a.workers, progress=True)
        print(json.dumps(res, indent=2) if a.json else report(res))
    elif a.cmd == "sweep":
        print(f"\n  {a.lever:<14}" + "".join(f"{c:>7}" for c in SWEEP_COLS))
        for v in a.values:
            c = config_mod.apply_overrides(cfg, {a.lever: v})
            print(sweep_row(v, simulate(c, a.n, a.seed, a.workers)), flush=True)
    elif a.cmd == "tune":
        cfg, _ = tune(cfg, a.n, a.levers, a.seed or 0, a.workers, a.rounds)
        res = simulate(cfg, a.n * 2, (a.seed or 0) + 999, a.workers, progress=True)
        print(report(res, "TUNED (fresh seed, 2x sample)"))
        preset = {k: v for k, v in config_mod.to_dict(cfg).items() if v != config_mod.to_dict(config_mod.Config())[k]}
        print("\n" + json.dumps(preset, indent=2))
        if a.out:
            with open(a.out, "w") as f:
                json.dump(preset, f, indent=2)
            print(f"\n  wrote {a.out}")


if __name__ == "__main__":
    main()
