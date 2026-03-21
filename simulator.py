#!/usr/bin/env python
"""
Diceball Simulator — tune game levers, run N at-bats CPU vs CPU,
and compare results to MLB target stats.
"""
from game.engine import play_at_bat
from game.config import GameConfig

# 2024 MLB league averages: (target, tolerance for ✓)
MLB_TARGETS = {
    "BA":    (0.248, 0.015),
    "OBP":   (0.317, 0.020),
    "SLG":   (0.407, 0.025),
    "OPS":   (0.724, 0.040),
    "BB%":   (0.085, 0.015),
    "K%":    (0.230, 0.020),
    "HR/PA": (0.030, 0.010),
    "BABIP": (0.300, 0.020),
}

# Pitcher levers — affect how dominant/deceptive the pitcher is
PITCHER_LEVERS = [
    ("pitcher_dice",      "Pitcher dice pool",         "4 or 5 d6"),
    ("gas_per_at_bat",    "Gas (re-rolls) per at-bat", "int or 'auto'"),
    ("fb_match_count",    "FB match count",            "3=three-of-a-kind, 2=pair"),
    ("cb_run_length",     "CB run length",             "3=full run, 2=two-die run"),
    ("cb_allow_six",      "CB allow 6 in run",         "True or False"),
    ("cu_diff_count",     "CU diff count",             "3=three diff same-parity, 2=two diff"),
    ("difficulty_method", "Pitch difficulty",          "max=high die, mid=middle die, min=low die"),
    ("hidden_reroll",     "Hidden re-roll",            "True or False"),
]

# Hitter levers — affect how good the batter is
HITTER_LEVERS = [
    ("correct_commit_bonus", "Correct commit bonus",  "integer, e.g. +1"),
    ("wrong_commit_penalty", "Wrong commit penalty",  "integer, e.g. -1"),
    ("hitter_power_bonus",   "Hitter power bonus",    "integer added to every power roll"),
]

LEVER_LABELS = PITCHER_LEVERS + HITTER_LEVERS


def display_config(cfg):
    gas = cfg.effective_gas()
    gas_label = "auto" if cfg.gas_per_at_bat is None else "explicit"
    values = {
        "pitcher_dice":         str(cfg.pitcher_dice),
        "gas_per_at_bat":       f"{gas}  ({gas_label})",
        "fb_match_count":       f"{cfg.fb_match_count}  ({'three-of-a-kind' if cfg.fb_match_count == 3 else 'pair'})",
        "cb_run_length":        f"{cfg.cb_run_length}  ({'full 3-die run' if cfg.cb_run_length == 3 else '2-die run'})",
        "cb_allow_six":         str(cfg.cb_allow_six),
        "cu_diff_count":        f"{cfg.cu_diff_count}  ({'three diff same-parity' if cfg.cu_diff_count == 3 else 'two diff same-parity'})",
        "difficulty_method":    f"{cfg.difficulty_method}  ({'high die' if cfg.difficulty_method == 'max' else 'middle die' if cfg.difficulty_method == 'mid' else 'low die'})",
        "correct_commit_bonus": f"+{cfg.correct_commit_bonus}",
        "wrong_commit_penalty": str(cfg.wrong_commit_penalty),
        "hitter_power_bonus":   f"{cfg.hitter_power_bonus:+d}",
        "hidden_reroll":        str(cfg.hidden_reroll),
    }
    print("\nConfig:")
    for i, (key, label, _) in enumerate(LEVER_LABELS, 1):
        print(f"  [{i}] {label:<30} {values[key]}")


def edit_config(cfg):
    display_config(cfg)
    raw = input("\nEnter lever number to edit (or Enter to cancel): ").strip()
    if not raw:
        return
    try:
        idx = int(raw) - 1
        if idx < 0 or idx >= len(LEVER_LABELS):
            print("Invalid number.")
            return
    except ValueError:
        print("Invalid input.")
        return

    key, label, hint = LEVER_LABELS[idx]
    current = getattr(cfg, key)
    val = input(f"  {label} [{current}]  ({hint}): ").strip()
    if not val:
        return

    if key == "hidden_reroll":
        if val.lower() in ("true", "yes", "1"):
            cfg.hidden_reroll = True
        elif val.lower() in ("false", "no", "0"):
            cfg.hidden_reroll = False
        else:
            print("Must be True or False.")
    elif key == "cb_allow_six":
        if val.lower() in ("true", "yes", "1"):
            cfg.cb_allow_six = True
        elif val.lower() in ("false", "no", "0"):
            cfg.cb_allow_six = False
        else:
            print("Must be True or False.")
    elif key == "gas_per_at_bat":
        if val.lower() == "auto":
            cfg.gas_per_at_bat = None
        else:
            cfg.gas_per_at_bat = int(val)
    elif key == "difficulty_method":
        if val in ("max", "mid", "min"):
            cfg.difficulty_method = val
        else:
            print("Must be max, mid, or min.")
    elif key == "pitcher_dice":
        cfg.pitcher_dice = int(val)
        cfg.gas_per_at_bat = None  # reset gas to auto when dice pool changes
    else:
        setattr(cfg, key, int(val))
    print(f"  → {label} set.")


def run_simulations(cfg, n):
    counts = {"BB": 0, "K_S": 0, "K_L": 0,
              "SINGLE": 0, "DOUBLE": 0, "TRIPLE": 0, "HR": 0,
              "OUT": 0, "WEAK_OUT": 0}
    for i in range(n):
        if i % 200 == 0:
            print(f"\r  Simulating... {i}/{n}", end="", flush=True)
        ab = play_at_bat(cfg.pitcher_dice, pitcher_is_ai=True, hitter_is_ai=True,
                         verbose=False, config=cfg)
        r = ab["result"]
        if r in counts:
            counts[r] += 1
    print(f"\r  Done — {n} at-bats simulated.       ")
    return counts


def display_results(counts, n):
    BB  = counts["BB"]
    K_S = counts["K_S"]
    K_L = counts["K_L"]
    H1  = counts["SINGLE"]
    H2  = counts["DOUBLE"]
    H3  = counts["TRIPLE"]
    HR  = counts["HR"]
    OUT = counts["OUT"]
    WOUT = counts["WEAK_OUT"]

    K  = K_S + K_L
    H  = H1 + H2 + H3 + HR
    AB = n - BB
    TB = H1 + 2 * H2 + 3 * H3 + 4 * HR

    BA    = H / AB      if AB > 0 else 0.0
    OBP   = (H + BB) / n if n > 0 else 0.0
    SLG   = TB / AB     if AB > 0 else 0.0
    OPS   = OBP + SLG
    BB_p  = BB / n
    K_p   = K / n
    HR_p  = HR / n
    BIP   = AB - K - HR          # balls in play (no HR, no K)
    BABIP = (H - HR) / BIP if BIP > 0 else 0.0

    # MLB 2024 per-PA rates for outcome comparison
    # OUT_IP = outs in play (groundouts + flyouts); WEAK_OUT has no direct MLB equivalent
    MLB_OUTCOME = {
        "BB (Walk)":   0.085,
        "K Swinging":  0.155,
        "K Looking":   0.075,
        "SINGLE":      0.148,
        "DOUBLE":      0.045,
        "TRIPLE":      0.004,
        "HR":          0.030,
        "OUT+WEAK":    0.458,   # combined outs in play
    }

    # Column widths between pipes: 19 | 8 | 10 | 17  (total inner = 57)
    O_TOP = "┌" + "─" * 57 + "┐"
    O_SEP = "├───────────────────┬────────┬──────────┬─────────────────┤"
    O_MID = "├───────────────────┼────────┼──────────┼─────────────────┤"
    O_BOT = "└───────────────────┴────────┴──────────┴─────────────────┘"

    print(f"\n{O_TOP}")
    print(f"│{'  OUTCOME BREAKDOWN  (' + str(f'{n:,}') + ' at-bats)':<57}│")
    print(O_SEP)
    print(f"│  {'Result':<16} │ {'Count':>6} │ {'Game %':>7}  │ {'MLB 2024 ~':<15} │")
    print(O_MID)
    rows = [
        ("BB (Walk)",  BB),
        ("K Swinging", K_S),
        ("K Looking",  K_L),
        ("SINGLE",     H1),
        ("DOUBLE",     H2),
        ("TRIPLE",     H3),
        ("HR",         HR),
        ("OUT",        OUT),
        ("WEAK OUT",   WOUT),
    ]
    for label, cnt in rows:
        rate = cnt / n
        if label == "OUT":
            mlb_str = "~45.8% combined"
        elif label == "WEAK OUT":
            mlb_str = "(incl. above)"
        elif label in MLB_OUTCOME:
            mlb_str = f"~{MLB_OUTCOME[label]:.1%}"
        else:
            mlb_str = ""
        print(f"│  {label:<16} │ {cnt:>6} │ {rate:>7.1%}  │ {mlb_str:<15} │")
    print(O_BOT)

    def flag(val, target, tol):
        diff = val - target
        if abs(diff) <= tol:
            return "✓"
        return f"{'↑' if diff > 0 else '↓'} ({diff:+.3f})"

    game_stats = [
        ("BA",    BA,    ".3f", *MLB_TARGETS["BA"]),
        ("OBP",   OBP,   ".3f", *MLB_TARGETS["OBP"]),
        ("SLG",   SLG,   ".3f", *MLB_TARGETS["SLG"]),
        ("OPS",   OPS,   ".3f", *MLB_TARGETS["OPS"]),
        ("BB%",   BB_p,  ".1%", *MLB_TARGETS["BB%"]),
        ("K%",    K_p,   ".1%", *MLB_TARGETS["K%"]),
        ("HR/PA", HR_p,  ".1%", *MLB_TARGETS["HR/PA"]),
        ("BABIP", BABIP, ".3f", *MLB_TARGETS["BABIP"]),
    ]

    # Column widths between pipes: 11 | 10 | 10 | 18  (total inner = 52)
    S_TOP = "┌" + "─" * 52 + "┐"
    S_SEP = "├───────────┬──────────┬──────────┬──────────────────┤"
    S_MID = "├───────────┼──────────┼──────────┼──────────────────┤"
    S_BOT = "└───────────┴──────────┴──────────┴──────────────────┘"

    print(f"\n{S_TOP}")
    print(f"│{'  STAT LINE vs MLB 2024 AVG':<52}│")
    print(S_SEP)
    print(f"│  {'Stat':<8} │ {'Game':>8} │ {'Target':>8} │ {'':16} │")
    print(S_MID)
    for name, val, fmt, target, tol in game_stats:
        game_str   = format(val, fmt)
        target_str = format(target, fmt)
        status = flag(val, target, tol)
        print(f"│  {name:<8} │ {game_str:>8} │ {target_str:>8} │ {status:<16} │")
    print(S_BOT)

    # --- wOBA / wRC+ / WAR ---
    # 2024 MLB linear weights (FanGraphs)
    LG_wOBA      = 0.317
    wOBA_SCALE   = 1.20   # converts wOBA gap to runs
    LG_R_PA      = 0.120  # league runs per PA
    RUNS_PER_WIN = 9.5
    REPL_RUNS    = 20     # replacement level: ~20 runs below average per 600 PA
    SEASON_PA    = 600

    wOBA = (0.690*BB + 0.888*H1 + 1.271*H2 + 1.616*H3 + 2.101*HR) / n if n > 0 else 0.0
    wRC_plus = round(((wOBA - LG_wOBA) / wOBA_SCALE + LG_R_PA) / LG_R_PA * 100)
    wRAA_600 = ((wOBA - LG_wOBA) / wOBA_SCALE) * SEASON_PA
    oWAR_600 = (wRAA_600 + REPL_RUNS) / RUNS_PER_WIN

    W_TOP = "┌" + "─" * 44 + "┐"
    W_MID = "├───────────┼────────────────────────────────┤"
    W_BOT = "└───────────┴────────────────────────────────┘"

    print(f"\n{W_TOP}")
    print(f"│{'  VALUE METRICS (proj. 600 PA)':<44}│")
    print(W_MID)
    print(f"│  {'wOBA':<8} │ {wOBA:.3f}{'  (lg avg .317)':>26} │")
    print(f"│  {'wRC+':<8} │ {wRC_plus:<4}{'  (100 = lg avg)':>26} │")
    print(f"│  {'oWAR':<8} │ {oWAR_600:+.1f}{'  (0.0 = replacement)':>26} │")
    print(W_BOT)


def compute_stats(counts, n):
    """Return a dict of key stats from raw counts."""
    BB  = counts["BB"]
    H1  = counts["SINGLE"]
    H2  = counts["DOUBLE"]
    H3  = counts["TRIPLE"]
    HR  = counts["HR"]
    K   = counts["K_S"] + counts["K_L"]
    H   = H1 + H2 + H3 + HR
    AB  = n - BB
    TB  = H1 + 2*H2 + 3*H3 + 4*HR
    BA  = H / AB       if AB > 0 else 0.0
    OBP = (H + BB) / n if n  > 0 else 0.0
    SLG = TB / AB      if AB > 0 else 0.0
    wOBA = (0.690*BB + 0.888*H1 + 1.271*H2 + 1.616*H3 + 2.101*HR) / n if n > 0 else 0.0
    return {"BA": BA, "OBP": OBP, "SLG": SLG, "wOBA": wOBA,
            "BB%": BB/n, "K%": K/n, "HR/PA": HR/n}


def _run_search(base_cfg, search_space, target_ba, target_obp, target_slg, n_sims=1000):
    """Generic search over a lever subspace. Returns best GameConfig."""
    from itertools import product
    import copy

    keys = list(search_space.keys())
    candidates = list(product(*search_space.values()))
    total = len(candidates)
    best_cfg, best_score = None, float("inf")

    for i, values in enumerate(candidates):
        print(f"\r  Searching... {i+1}/{total}", end="", flush=True)
        cfg = copy.copy(base_cfg)
        for k, v in zip(keys, values):
            setattr(cfg, k, v)
        counts = run_simulations(cfg, n_sims)
        s = compute_stats(counts, n_sims)
        score = (
            ((s["BA"]  - target_ba)  / 0.020) ** 2 +
            ((s["OBP"] - target_obp) / 0.025) ** 2 +
            ((s["SLG"] - target_slg) / 0.030) ** 2
        )
        if score < best_score:
            best_score, best_cfg = score, cfg

    print(f"\r  Done — searched {total} configurations.       ")
    return best_cfg


def hitter_search(base_cfg, target_ba, target_obp, target_slg, n_sims=1000):
    """Search over hitter levers (commit bonuses, power bonus). Pitcher config fixed."""
    return _run_search(base_cfg, {
        "correct_commit_bonus": [0, 1, 2],
        "wrong_commit_penalty": [-2, -1, 0],
        "hitter_power_bonus":   [-2, -1, 0, 1, 2, 3],
    }, target_ba, target_obp, target_slg, n_sims)


def pitcher_search(base_cfg, target_ba, target_obp, target_slg, n_sims=1000):
    """Search over pitcher levers (dice, difficulty, pitch requirements, deception). Hitter config fixed."""
    return _run_search(base_cfg, {
        "pitcher_dice":      [4, 5],
        "difficulty_method": ["max", "mid", "min"],
        "hidden_reroll":     [False, True],
        "cb_allow_six":      [False, True],
        "fb_match_count":    [2, 3],
    }, target_ba, target_obp, target_slg, n_sims)


def main():
    cfg = GameConfig()
    print("╔═══════════════════════════════════════╗")
    print("║      DICEBALL SIMULATOR               ║")
    print("╚═══════════════════════════════════════╝")

    while True:
        display_config(cfg)
        print("\n  [e] Edit a lever")
        print("  [r] Run simulations")
        print("  [h] Target hitter slash line  (searches hitter levers, pitcher config fixed)")
        print("  [p] Target pitcher slash line (searches pitcher levers, hitter config fixed)")
        print("  [q] Quit")
        choice = input("\nChoice: ").strip().lower()

        if choice == "q":
            break
        elif choice == "e":
            edit_config(cfg)
        elif choice == "r":
            raw = input("Number of simulations [1000]: ").strip()
            try:
                n = int(raw) if raw else 1000
            except ValueError:
                print("Invalid number.")
                continue
            counts = run_simulations(cfg, n)
            display_results(counts, n)
        elif choice in ("h", "p"):
            side = "hitter" if choice == "h" else "pitcher"
            print(f"\nTarget {side} slash line (e.g. .301 .397 .566):")
            try:
                tba  = float(input("  BA:  ").strip())
                tobp = float(input("  OBP: ").strip())
                tslg = float(input("  SLG: ").strip())
            except ValueError:
                print("Invalid input — enter decimals like .301")
                continue
            label = f".{int(tba*1000):03d}/.{int(tobp*1000):03d}/.{int(tslg*1000):03d}"
            print(f"\n  Searching {side} levers for {label} ...")
            best = hitter_search(cfg, tba, tobp, tslg) if choice == "h" else pitcher_search(cfg, tba, tobp, tslg)
            print(f"\n  Best {side} config found:")
            cfg = best
            display_config(cfg)
            print("\n  Running 2,000 verification sims...")
            counts = run_simulations(cfg, 2000)
            display_results(counts, 2000)
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
