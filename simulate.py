"""
Diceball simulation harness.
Runs N at-bats with AI pitcher vs AI hitter and reports MLB-comparable stats.

Usage:
    uv run simulate.py [num_at_bats] [pitcher_dice]
    uv run simulate.py 1000 5
    uv run simulate.py 5000          # uses all pitcher dice counts (4-7)
"""

import sys
from collections import defaultdict
from game.engine import play_at_bat

# Suppress AI decision prints during simulation
import builtins
_real_print = builtins.print

def _silent_print(*args, **kwargs):
    pass

def run_simulation(num_at_bats: int, pitcher_dice: int | None = None) -> dict:
    """Run num_at_bats simulated at-bats and return aggregated stats."""
    dice_counts = [pitcher_dice] if pitcher_dice else [4, 5]
    results = defaultdict(int)
    pitch_totals = []

    builtins.print = _silent_print
    try:
        for i in range(num_at_bats):
            dice = dice_counts[i % len(dice_counts)]
            outcome = play_at_bat(dice, pitcher_is_ai=True, hitter_is_ai=True, verbose=False)
            results[outcome["result"]] += 1
            pitch_totals.append(outcome["pitches"])
    finally:
        builtins.print = _real_print

    return dict(results), pitch_totals


def print_report(results: dict, pitch_totals: list, num_at_bats: int, pitcher_dice: int | None):
    hits = results.get("SINGLE", 0) + results.get("DOUBLE", 0) + results.get("TRIPLE", 0) + results.get("HR", 0)
    k_s = results.get("K_S", 0)
    k_l = results.get("K_L", 0)
    k_total = k_s + k_l
    ab_for_avg = num_at_bats - results.get("BB", 0)

    ba  = hits / ab_for_avg if ab_for_avg else 0
    obp = (hits + results.get("BB", 0)) / num_at_bats
    hr_rate = results.get("HR", 0) / num_at_bats
    k_rate  = k_total / num_at_bats
    bb_rate = results.get("BB", 0) / num_at_bats
    avg_pitches = sum(pitch_totals) / len(pitch_totals) if pitch_totals else 0

    dice_label = str(pitcher_dice) if pitcher_dice else "4-5 (mixed)"

    _real_print(f"\n{'='*50}")
    _real_print(f"  DICEBALL SIMULATION  —  {num_at_bats:,} at-bats  |  Pitcher dice: {dice_label}")
    _real_print(f"{'='*50}")
    _real_print(f"\n  Outcome breakdown:")
    for label, key in [("  Home Run", "HR"), ("  Triple", "TRIPLE"), ("  Double", "DOUBLE"), ("  Single", "SINGLE"),
                        ("  Out (hard)", "OUT"), ("  Out (weak)", "WEAK_OUT"),
                        ("  Walk", "BB")]:
        n = results.get(key, 0)
        _real_print(f"    {label:<20} {n:>6,}   ({n/num_at_bats:>5.1%})")
    _real_print(f"    {'  Strikeout (swing)':<20} {k_s:>6,}   ({k_s/num_at_bats:>5.1%})")
    _real_print(f"    {'  Strikeout (look)':<20} {k_l:>6,}   ({k_l/num_at_bats:>5.1%})")
    _real_print(f"    {'  Strikeout (total)':<20} {k_total:>6,}   ({k_rate:>5.1%})")

    _real_print(f"\n  Rate stats (MLB 2023 benchmarks in brackets):")
    _real_print(f"    BA          {ba:.3f}   [.248]")
    _real_print(f"    OBP         {obp:.3f}   [.320]")
    _real_print(f"    HR/AB       {hr_rate:.3f}   [.034]")
    _real_print(f"    K%          {k_rate:.1%}   [22.7%]")
    _real_print(f"    K% swing    {k_s/num_at_bats:.1%}   [~14%]")
    _real_print(f"    K% look     {k_l/num_at_bats:.1%}   [~9%]")
    _real_print(f"    BB%         {bb_rate:.1%}   [ 8.4%]")
    _real_print(f"    Avg pitches {avg_pitches:.1f}   [3.8 P/PA in MLB]")
    _real_print(f"{'='*50}\n")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    dice = int(sys.argv[2]) if len(sys.argv) > 2 else None

    _real_print(f"Running {n:,} simulated at-bats... ", end="", flush=True)
    results, pitch_totals = run_simulation(n, dice)
    _real_print("done.")
    print_report(results, pitch_totals, n, dice)
