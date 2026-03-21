from itertools import combinations
from game.pitch_utils import check_pitch_combo, calc_difficulty
from game.config import DEFAULT_CONFIG
import random
import math

def _pitcher_min_difficulty(balls, strikes):
    """
    Minimum pitch difficulty the AI pitcher is willing to commit.
    Below this threshold, it prefers an intentional ball over risking contact.
    """
    if balls >= 3:
        return 1   # Must throw — take whatever we have
    if strikes == 2 and balls == 0:
        return 3   # 0-2: two strikes of cushion — only commit a quality pitch
    if strikes == 2:
        return 2   # 1-2, 2-2: a bit of cushion — skip very weak pitches
    return 1       # All other counts: throw anything valid, avoid free balls


def make_pitcher_decision(dice, balls, strikes, streak_type, streak_count, gas_remaining,
                           config=None, verbose=True):
    """
    Determines the AI pitcher's move: optional re-roll (costs 1 gas per die) + pitch commitment.
    Count-aware: will intentionally ball a weak pitch rather than gift an easy hit.

    Returns: (re_roll_input, chosen_pitch)
    """
    if config is None:
        config = DEFAULT_CONFIG
    if verbose:
        print("\nAI Pitcher is thinking...")

    analysis = _analyze_dice(dice, config)
    possible_pitches = analysis["possible"]
    must_throw = balls >= 3   # another ball = walk
    min_diff = _pitcher_min_difficulty(balls, strikes)

    # Score a valid pitch: difficulty + streak-break bonus
    def pitch_score(p):
        s = p['difficulty']
        cat = "FB" if p['type'] == "FB" else "OFFSPEED"
        if streak_count >= 2 and cat != streak_type:
            s += min(streak_count - 1, 2)
        return s

    best_in_hand = max(possible_pitches, key=pitch_score) if possible_pitches else None

    # --- Commit if best pitch meets the quality bar ---
    if best_in_hand and best_in_hand['difficulty'] >= min_diff:
        # On must-throw counts, always pick the safest (best) pitch.
        # Otherwise, use weighted random selection: mostly optimal, but occasionally
        # commits a surprise pitch — creating genuine uncertainty BATS can't resolve.
        valid = [p for p in possible_pitches if p['difficulty'] >= min_diff]
        if must_throw or len(valid) == 1:
            chosen = best_in_hand
        else:
            scores = [pitch_score(p) for p in valid]
            max_s = max(scores)
            # T=0.5: ~86% best pitch, ~12% one step down, ~2% two steps down
            weights = [math.exp((s - max_s) / 0.5) for s in scores]
            chosen = random.choices(valid, weights=weights)[0]
            if verbose and chosen['type'] != best_in_hand['type']:
                print(f"  AI Pitcher mixes it up — going with {chosen['type']} (diff {chosen['difficulty']}).")
        return "", chosen['type']

    # --- Try to re-roll toward a better pitch ---
    if gas_remaining > 0:
        near_misses = _find_near_misses(dice, config)
        near_misses = [p for p in near_misses if len(p['reroll_indices'].split()) <= gas_remaining]
        if near_misses:
            for p in near_misses:
                p['score'] = p['potential_difficulty']
                cat = "FB" if p['type'] == "FB" else "OFFSPEED"
                if streak_count >= 2 and cat != streak_type:
                    p['score'] += min(streak_count - 1, 2)
                # Off-speed is more deceptive when behind in count
                if balls >= 2 and p['type'] in ('CB', 'CU'):
                    p['score'] += 1

            # Only pursue near-misses that could yield an acceptable pitch
            viable = [p for p in near_misses if must_throw or p['potential_difficulty'] >= min_diff]
            if viable:
                best_target = max(viable, key=lambda p: p['score'])
                if verbose:
                    reason = "aiming higher" if best_in_hand else "building pitch"
                    print(f"  AI Pitcher re-rolling toward {best_target['type']} ({reason})")
                return best_target['reroll_indices'], best_target['type']

    # --- No gas / no viable re-roll ---
    if must_throw:
        # Have to throw something, even weak
        if best_in_hand:
            if verbose:
                print(f"  AI Pitcher commits {best_in_hand['type']} (diff {best_in_hand['difficulty']}) — must avoid a walk.")
            return "", best_in_hand['type']
        # No valid pitch at all — commit FB, it'll be a ball but nothing to be done
        return "", "FB"

    # Not forced — intentionally ball the weak pitch, but occasionally surprise them
    if best_in_hand:
        if random.random() < 0.10:
            # "Gotcha" pitch: commit the weak pitch hoping hitter is sitting on a bluff
            if verbose:
                print(f"  AI Pitcher surprises — throws {best_in_hand['type']} (diff {best_in_hand['difficulty']}) to catch them looking.")
            return "", best_in_hand['type']

        have_types = {p['type'] for p in possible_pitches}
        for t in ["CB", "CU", "FB"]:   # prefer to fake off-speed (more plausible bluff)
            if t not in have_types:
                if verbose:
                    print(f"  AI Pitcher holds off — diff {best_in_hand['difficulty']} too hittable at {balls}-{strikes}. Intentional ball.")
                return "", t
        # Somehow holds all 3 types — throw best anyway
        return "", best_in_hand['type']

    # No valid pitch, no gas, not forced — just commit FB (ball)
    return "", "FB"

def _analyze_dice(dice, config=None):
    """Helper to find possible pitches in the current hand."""
    if config is None:
        config = DEFAULT_CONFIG
    from game.pitch_utils import find_key_dice
    possible = []
    for pitch_type in ["FB", "CB", "CU"]:
        for combo_indices in combinations(range(len(dice)), 3):
            combo_dice = [dice[i] for i in combo_indices]
            key_dice = find_key_dice(combo_dice, pitch_type, config)
            if key_dice is not None:
                possible.append({
                    "type": pitch_type,
                    "difficulty": calc_difficulty(key_dice, config.difficulty_method),
                    "combo": combo_dice
                })
    return {"possible": possible}


def _find_near_misses(dice, config=None):
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


def _hitter_swing_threshold(balls, strikes):
    """
    Returns (min_contact_prob, always_take).
    always_take=True: don't swing no matter the pitch quality.
    """
    if balls == 3 and strikes == 0:
        return 0.0, True    # 3-0: take — walk is almost free
    if balls == 3 and strikes == 1:
        return 0.15, False  # 3-1: take a real bad pitch, but willing to swing
    if strikes == 2:
        return 0.12, False  # Two-strike counts: wary of waste pitches — take low-contact looks
    return 0.0, False       # All other counts: hack away — don't give away free balls


def make_hitter_decision(pitcher_dice, re_roll_input, balls, strikes,
                          pitch_streak_type, pitch_streak_count, pitcher_gas,
                          config=None, verbose=True):
    """
    AI hitter's post-dice decision. Count-aware: works the count, protects the plate,
    and won't waste a 3-0 count by hacking at a bad pitch.

    Returns: (swing_decision, commit_pitch, swing_type)
    """
    from game.bats import calculate_bats_probabilities
    if config is None:
        config = DEFAULT_CONFIG

    HIT_VALUES = {'HR': 4.0, 'TRIPLE': 2.5, 'DOUBLE': 1.5, 'SINGLE': 1.0}

    min_contact, always_take = _hitter_swing_threshold(balls, strikes)

    if always_take:
        if verbose:
            print("\nAI Hitter takes — 3-0, sitting on a walk.")
        return 'n', None, None

    # --- 0-2 read: pitcher has max cushion to waste a pitch ---
    # On 0-2 the pitcher will bluff weak dice ~90% of the time. Hitter reads this
    # but imperfectly — takes 25% of the time when expecting a bluff, occasionally
    # getting burned by a surprise commit → K Looking.
    if strikes == 2 and balls == 0:
        pitcher_hand = _analyze_dice(pitcher_dice, config)
        best_diff = max((p['difficulty'] for p in pitcher_hand['possible']), default=0)
        if best_diff < _pitcher_min_difficulty(balls, strikes):
            if random.random() < 0.50:
                if verbose:
                    print(f"\nAI Hitter reads weak hand at 0-2 — takes (expecting bluff).")
                return 'n', None, None

    best_ev, best_commit, best_swing, best_contact = -1.0, 'FB', 'p', 0.0

    for commit_pitch in ['FB', 'CB', 'CU']:
        for st in ['p', 'c']:
            results = calculate_bats_probabilities(
                pitcher_dice, re_roll_input, st, 0, 0, 0, 0,
                pitch_streak_type, pitch_streak_count, 's', commit_pitch.lower(), pitcher_gas,
                config=config
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
                best_ev, best_commit, best_swing, best_contact = ev, commit_pitch, st, weighted_contact

    if best_contact < min_contact:
        if verbose:
            if strikes == 2:
                print(f"\nAI Hitter takes — two strikes, but pitch quality too low ({best_contact:.1%} contact). Looking.")
            elif balls == 3:
                print(f"\nAI Hitter takes — 3-1, working the count (contact only {best_contact:.1%}).")
            else:
                print(f"\nAI Hitter takes — pitch quality too low ({best_contact:.1%} contact).")
        return 'n', None, None

    if verbose:
        count_note = ""
        if strikes == 2:
            count_note = " [protecting the plate]"
        elif balls >= 2:
            count_note = " [hitter's count]"
        print(f"\nAI Hitter commits to {best_commit} with {'power' if best_swing == 'p' else 'contact'} swing "
              f"(contact: {best_contact:.1%}, EV: {best_ev:.2f}){count_note}.")
    return 's', best_commit, best_swing


def _infer_likely_pitch(dice):
    """Look at pitcher's dice and guess the most likely pitch they can throw."""
    for pitch_type in ['FB', 'CB', 'CU']:
        for combo in combinations(dice, 3):
            if check_pitch_combo(list(combo), pitch_type):
                return pitch_type
    return None
