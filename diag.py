"""Quick diagnostic: what contact probabilities does the AI see when it takes?"""
import builtins
from collections import defaultdict
from game.engine import roll_dice
from game.pitch_utils import find_pitch_outcome
from game.bats import calculate_bats_probabilities

_real_print = builtins.print
builtins.print = lambda *a, **k: None

import random
samples = 5000
contact_probs_on_take = []
contact_probs_on_swing = []

for _ in range(samples):
    pitcher_dice = roll_dice(5)
    balls, strikes = random.randint(0, 3), random.randint(0, 2)
    swing_type = 'b'
    hitter_approach = 'w'
    hitter_sit_guess = None

    results = calculate_bats_probabilities(
        pitcher_dice, "", swing_type, 0, 0, 0, 0,
        None, 0, hitter_approach, hitter_sit_guess
    )
    if not results:
        continue

    total_weight = sum(r['pitch_prob'] for r in results)
    if total_weight == 0:
        continue
    wc = sum(r['pitch_prob'] * r['contact_prob'] for r in results) / total_weight

    if strikes == 2:
        threshold = 0.25
    elif balls == 3:
        threshold = 0.55
    else:
        threshold = 0.35

    if wc >= threshold:
        contact_probs_on_swing.append(wc)
    else:
        contact_probs_on_take.append(wc)

builtins.print = _real_print

def stats(lst):
    if not lst: return "n/a"
    return f"min={min(lst):.2f} mean={sum(lst)/len(lst):.2f} max={max(lst):.2f}"

_real_print(f"Samples: {samples}")
_real_print(f"Would swing ({len(contact_probs_on_swing)}): {stats(contact_probs_on_swing)}")
_real_print(f"Would take  ({len(contact_probs_on_take)}):  {stats(contact_probs_on_take)}")
_real_print(f"\nContact prob distribution on takes:")
buckets = defaultdict(int)
for p in contact_probs_on_take:
    buckets[int(p * 10) / 10] += 1
for k in sorted(buckets):
    bar = '#' * (buckets[k] // 20)
    _real_print(f"  {k:.1f}-{k+0.1:.1f}  {buckets[k]:>5}  {bar}")
