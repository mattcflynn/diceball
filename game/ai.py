from itertools import combinations
from game.pitch_utils import check_pitch_combo
import random

def make_pitcher_decision(dice, balls, strikes, streak_type, streak_count, gas_remaining):
    """
    Determines the AI pitcher's move: optional re-roll (costs 1 gas per die) + pitch commitment.
    gas_remaining is the current public gas token count.

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

    # If we already have a good pitch in hand, consider whether to re-roll for better
    if possible_pitches:
        # Already have a valid pitch — commit to the best one, don't spend gas upgrading
        best_in_hand = max(possible_pitches, key=lambda p: p['difficulty'])
        return "", best_in_hand['type']

    # No valid pitch in hand — must try to re-roll if gas is available
    if gas_remaining > 0:
        near_misses = _find_near_misses(dice)
        near_misses = [p for p in near_misses if len(p['reroll_indices'].split()) <= gas_remaining]
        if near_misses:
            # Score: potential difficulty + streak setup bonus
            for p in near_misses:
                p['score'] = p['potential_difficulty']
                category = "FB" if p['type'] == "FB" else "OFFSPEED"
                if streak_count >= 2 and category != streak_type:
                    p['score'] += min(streak_count - 1, 2)
                if aggressiveness == "conservative" and p['type'] in ('FB', 'CU'):
                    p['score'] += 1  # Prefer easier-to-form pitches when behind in count
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

def make_hitter_pre_pitch_decision(balls, strikes, pitch_streak_type, pitch_streak_count):
    """
    AI hitter's pre-pitch decisions: approach, sit guess, and swing type.
    Made before the pitcher rolls.

    Returns: (hitter_approach, hitter_sit_guess, swing_type)
    """
    # With 3 balls, take to fish for a walk
    if balls == 3:
        print("\nAI Hitter takes to try for a walk.")
        return 't', None, None

    # With 2 strikes, protect the plate with contact swing
    if strikes == 2:
        swing_type = 'c'
        if pitch_streak_count >= 2:
            sit_pitch = 'fb' if pitch_streak_type == 'FB' else ('cb' if pitch_streak_type == 'CB' else 'cu')
            print(f"\nAI Hitter hard sits on {sit_pitch.upper()} (pitcher streak) with contact swing.")
            return 's', sit_pitch, swing_type
        print("\nAI Hitter waits with contact swing (2 strikes).")
        return 'w', None, swing_type

    # Sit on a pitch if the pitcher has a clear streak — go for power
    if pitch_streak_count >= 2:
        sit_pitch = 'fb' if pitch_streak_type == 'FB' else ('cb' if pitch_streak_type == 'CB' else 'cu')
        print(f"\nAI Hitter hard sits on {sit_pitch.upper()} (streak of {pitch_streak_count}) with power swing.")
        return 's', sit_pitch, 'p'

    # Default: power swing
    print("\nAI Hitter waits with power swing.")
    return 'w', None, 'p'


def make_hitter_sit_adjustment(pitcher_dice, hitter_sit_guess):
    """
    After seeing pitcher's initial dice, decide to keep or shift the hard sit.

    Returns: ('k' or 'sh', new_sit_guess)
    """
    inferred = _infer_likely_pitch(pitcher_dice)
    if inferred and inferred.lower() != hitter_sit_guess:
        print(f"\nAI Hitter shifts sit from {hitter_sit_guess.upper()} to {inferred} based on dice.")
        return 'sh', inferred.lower()
    print(f"\nAI Hitter keeps sit on {hitter_sit_guess.upper()}.")
    return 'k', hitter_sit_guess


def make_hitter_swing_decision(pitcher_dice, re_roll_input, swing_type, balls, strikes,
                                hitter_approach, hitter_sit_guess, pitch_streak_type,
                                pitch_streak_count, bonus_dice, pitcher_gas=0):
    """
    AI hitter decides whether to swing or take, and picks the optimal swing type.
    Compares power vs contact expected value using BATS and selects the better option.

    Returns: ('s' or 'n', optimal_swing_type)
    """
    from game.bats import calculate_bats_probabilities

    # Hit values for EV calculation (approximate run values)
    HIT_VALUES = {'HR': 4.0, 'DOUBLE': 1.5, 'SINGLE': 1.0}

    def _ev_for_swing(st):
        results = calculate_bats_probabilities(
            pitcher_dice, re_roll_input, st, 0, 0, 0, bonus_dice,
            pitch_streak_type, pitch_streak_count, hitter_approach, hitter_sit_guess, pitcher_gas
        )
        if not results:
            return 0.0, 0.0
        total_weight = sum(r['pitch_prob'] for r in results)
        if total_weight == 0:
            return 0.0, 0.0
        weighted_contact = sum(r['pitch_prob'] * r['contact_prob'] for r in results) / total_weight
        ev = sum(
            (r['pitch_prob'] / total_weight) * r['contact_prob'] *
            sum(r['power_probs'].get(h, 0) * v for h, v in HIT_VALUES.items())
            for r in results
        )
        return weighted_contact, ev

    # With 2 strikes, protect the plate — always use contact swing
    if strikes == 2:
        contact_prob, _ = _ev_for_swing('c')
        threshold = 0.10
        decision = 's' if contact_prob >= threshold else 'n'
        print(f"\nAI Hitter {'swings' if decision == 's' else 'takes'} with contact swing (contact: {contact_prob:.1%}).")
        return decision, 'c'

    # Otherwise pick the swing type with higher expected value
    p_contact, p_ev = _ev_for_swing('p')
    c_contact, c_ev = _ev_for_swing('c')
    best_type = 'p' if p_ev >= c_ev else 'c'
    best_contact = p_contact if best_type == 'p' else c_contact

    threshold = 0.30 if balls == 3 else 0.10
    decision = 's' if best_contact >= threshold else 'n'
    print(f"\nAI Hitter {'swings' if decision == 's' else 'takes'} with {best_type} swing "
          f"(contact: {best_contact:.1%}, EV p={p_ev:.2f} c={c_ev:.2f}).")
    return decision, best_type


def _infer_likely_pitch(dice):
    """Look at pitcher's dice and guess the most likely pitch they can throw."""
    for pitch_type in ['FB', 'CB', 'CU']:
        for combo in combinations(dice, 3):
            if check_pitch_combo(list(combo), pitch_type):
                return pitch_type
    return None