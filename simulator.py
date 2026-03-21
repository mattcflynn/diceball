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

LEVER_LABELS = [
    ("pitcher_dice",         "Pitcher dice pool",           "4 or 5 d6"),
    ("gas_per_at_bat",       "Gas (re-rolls) per at-bat",   "int or 'auto'"),
    ("fb_match_count",       "FB match count",              "3=three-of-a-kind, 2=pair"),
    ("cb_run_length",        "CB run length",               "3=full run, 2=two-die run"),
    ("cb_allow_six",         "CB allow 6 in run",           "True or False"),
    ("cu_diff_count",        "CU diff count",               "3=three diff same-parity, 2=two diff"),
    ("difficulty_method",    "Pitch difficulty",            "max=high die, mid=middle die, min=low die"),
    ("correct_commit_bonus", "Correct commit bonus",        "integer, e.g. +1"),
    ("wrong_commit_penalty", "Wrong commit penalty",        "integer, e.g. -1"),
    ("hidden_reroll",        "Hidden re-roll",              "True or False"),
]


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


def main():
    cfg = GameConfig()
    print("╔═══════════════════════════════════════╗")
    print("║      DICEBALL SIMULATOR               ║")
    print("╚═══════════════════════════════════════╝")

    while True:
        display_config(cfg)
        print("\n  [e] Edit a lever")
        print("  [r] Run simulations")
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
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
