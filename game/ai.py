from itertools import combinations
from game.pitch_utils import check_pitch_combo
import random

def make_pitcher_decision(dice, balls, strikes, streak_type, streak_count, gas_remaining):
    """
    Determines the AI pitcher's move: optional re-roll (costs 1 gas per die) + pitch commitment.

    Returns: (re_roll_input, chosen_pitch)
    """
    print("\nAI Pitcher is thinking...")

    analysis = _analyze_dice(dice)
    possible_pitches = analysis["possible"]

    aggressiveness = "neutral"
    if balls >= 3:
        aggressiveness = "conservative"
    elif strikes == 2:
        aggressiveness = "aggressive"

    if possible_pitches:
        # Already have a valid pitch — commit to the best one, don't spend gas upgrading
        best_in_hand = max(possible_pitches, key=lambda p: p['difficulty'])
        return "", best_in_hand['type']

    # No valid pitch in hand — must try to re-roll if gas is available
    if gas_remaining > 0:
        near_misses = _find_near_misses(dice)
        near_misses = [p for p in near_misses if len(p['reroll_indices'].split()) <= gas_remaining]
        if near_misses:
            for p in near_misses:
                p['score'] = p['potential_difficulty']
                category = "FB" if p['type'] == "FB" else "OFFSPEED"
                if streak_count >= 2 and category != streak_type:
                    p['score'] += min(streak_count - 1, 2)
                if aggressiveness == "conservative" and p['type'] in ('FB', 'CU'):
                    p['score'] += 1
            best_target = max(near_misses, key=lambda p: p['score'])
            return best_target['reroll_indices'], best_target['type']

    # Out of gas and no valid pitch — commit to FB (will be a ball)
    return "", "FB"

def _analyze_dice(dice):
    """Helper to find possible pitches in the current hand."""
    possible = []
    for pitch_type in ["FB", "CB", "CU"]:
        for combo_indices in combinations(range(len(dice)), 3):
            combo_dice = [dice[i] for i in combo_indices]
            if check_pitch_combo(combo_dice, pitch_type):
                possible.append({
                    "type": pitch_type,
                    "difficulty": max(combo_dice),
                    "combo": combo_dice
                })
    return {"possible": possible}


def _find_near_misses(dice):
    """Find 2-of-3 near-miss opportunities and which dice to re-roll to complete them."""
    near_misses = []

    # FB: two of a kind
    for i, j in combinations(range(len(dice)), 2):
        if dice[i] == dice[j]:
            reroll_indices = [str(k + 1) for k in range(len(dice)) if k not in (i, j)]
            near_misses.append({
                "type": "FB", "potential_difficulty": dice[i],
                "reroll_indices": " ".join(reroll_indices)
            })

    # CB: two adjacent non-6 values (need one more)
    for i, j in combinations(range(len(dice)), 2):
        d1, d2 = sorted((dice[i], dice[j]))
        if d2 - d1 == 1 and d2 < 6:
            reroll_indices = [str(k + 1) for k in range(len(dice)) if k not in (i, j)]
            near_misses.append({
                "type": "CB", "potential_difficulty": d2 + 1,
                "reroll_indices": " ".join(reroll_indices)
            })
        if d2 - d1 == 2 and d2 < 6:
            reroll_indices = [str(k + 1) for k in range(len(dice)) if k not in (i, j)]
            near_misses.append({
                "type": "CB", "potential_difficulty": d2,
                "reroll_indices": " ".join(reroll_indices)
            })

    # CU: two different same-parity values
    for i, j in combinations(range(len(dice)), 2):
        d1, d2 = dice[i], dice[j]
        if d1 != d2 and (d1 % 2 == d2 % 2):
            reroll_indices = [str(k + 1) for k in range(len(dice)) if k not in (i, j)]
            near_misses.append({
                "type": "CU", "potential_difficulty": max(d1, d2),
                "reroll_indices": " ".join(reroll_indices)
            })

    return near_misses


def make_hitter_decision(pitcher_dice, re_roll_input, balls, strikes,
                          pitch_streak_type, pitch_streak_count, pitcher_gas):
    """
    AI hitter's post-dice decision. Sees the pitcher's initial dice and re-roll plan.
    Picks the best (commit_pitch, swing_type) combination using BATS expected value,
    then decides whether the EV is worth swinging.

    Returns: (swing_decision, commit_pitch, swing_type)
    """
    from game.bats import calculate_bats_probabilities

    HIT_VALUES = {'HR': 4.0, 'TRIPLE': 2.5, 'DOUBLE': 1.5, 'SINGLE': 1.0}

    # With 3 balls, take to fish for a walk
    if balls == 3:
        print("\nAI Hitter takes to try for a walk.")
        return 'n', None, None

    best_ev = -1
    best_commit = 'FB'
    best_swing = 'p'
    best_contact = 0.0

    for commit_pitch in ['FB', 'CB', 'CU']:
        for st in ['p', 'c']:
            results = calculate_bats_probabilities(
                pitcher_dice, re_roll_input, st, 0, 0, 0, 0,
                pitch_streak_type, pitch_streak_count, 's', commit_pitch.lower(), pitcher_gas
            )
            if not results:
                continue
            total_weight = sum(r['pitch_prob'] for r in results)
            if total_weight == 0:
                continue

            weighted_contact = sum(r['pitch_prob'] * r['contact_prob'] for r in results) / total_weight
            ev = sum(
                (r['pitch_prob'] / total_weight) * r['contact_prob'] *
                sum(r['power_probs'].get(h, 0) * v for h, v in HIT_VALUES.items())
                for r in results
            )

            if ev > best_ev:
                best_ev = ev
                best_commit = commit_pitch
                best_swing = st
                best_contact = weighted_contact

    threshold = 0.10
    if best_contact < threshold:
        print(f"\nAI Hitter takes (best contact prob: {best_contact:.1%}).")
        return 'n', None, None

    print(f"\nAI Hitter commits to {best_commit} with {'power' if best_swing == 'p' else 'contact'} swing "
          f"(contact: {best_contact:.1%}, EV: {best_ev:.2f}).")
    return 's', best_commit, best_swing


def _infer_likely_pitch(dice):
    """Look at pitcher's dice and guess the most likely pitch they can throw."""
    for pitch_type in ['FB', 'CB', 'CU']:
        for combo in combinations(dice, 3):
            if check_pitch_combo(list(combo), pitch_type):
                return pitch_type
    return None
