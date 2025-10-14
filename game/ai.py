from itertools import combinations
from game.pitch_utils import check_pitch_combo
import random

def make_pitcher_decision(dice, balls, strikes, streak_type, streak_count, rerolls_remaining):
    """
    Determines the AI pitcher's move, including re-roll and pitch commitment.

    Args:
        dice: The pitcher's current dice roll.
        balls: Current ball count.
        strikes: Current strike count.
        streak_type: The type of the current pitch streak (e.g., "FB").
        streak_count: The length of the current pitch streak.
        rerolls_remaining: How many dice the pitcher can re-roll this at-bat.

    Returns:
        A tuple containing (re_roll_input, chosen_pitch).
        re_roll_input (str): A string of dice indices to re-roll (e.g., "1 2 3").
        chosen_pitch (str): The pitch the AI commits to (e.g., "FB").
    """
    print("\nAI Pitcher is thinking...")

    # If no re-rolls are left, the AI cannot choose to re-roll.
    if rerolls_remaining == 0:
        print("AI has no re-rolls left, must play the hand as is.")
        near_misses = [] # Effectively blocks re-roll logic

    # 1. Analyze hand for possible and near-miss pitches
    analysis = _analyze_dice(dice)
    possible_pitches = analysis["possible"]
    near_misses = analysis["near_misses"]

    # 2. Determine aggressiveness based on the count
    aggressiveness = "neutral"
    if balls >= 3:
        aggressiveness = "conservative"  # Must throw a strike
    elif strikes == 2:
        aggressiveness = "aggressive"  # Go for the K

    # --- DECISION LOGIC ---

    # If we have a pitch available in hand
    if possible_pitches:
        # Conservative: Just throw a strike. Pick the highest difficulty one available.
        if aggressiveness == "conservative":
            best_pitch = max(possible_pitches, key=lambda p: p['difficulty'])
            return "", best_pitch['type']

        # Aggressive: Go for the best pitch, don't re-roll.
        if aggressiveness == "aggressive":
            best_pitch = max(possible_pitches, key=lambda p: p['difficulty'])
            return "", best_pitch['type']

        # Neutral: Decide if it's worth re-rolling for something better.
        # If we have a high-difficulty pitch already, just take it.
        best_in_hand = max(possible_pitches, key=lambda p: p['difficulty'])
        if best_in_hand['difficulty'] >= 5:
            return "", best_in_hand['type']

        # If our best pitch is mediocre, see if a near-miss is better.
        if near_misses:
            best_potential_pitch = max(near_misses, key=lambda p: p['potential_difficulty'])
            # If potential is better than what we have, re-roll.
            # NEW: Check if we have enough re-rolls for this move.
            num_dice_to_reroll = len(best_potential_pitch['reroll_indices'].split())
            if num_dice_to_reroll > rerolls_remaining:
                return "", best_in_hand['type'] # Not enough re-rolls, stick with current hand

            if best_potential_pitch['potential_difficulty'] > best_in_hand['difficulty']:
                return best_potential_pitch['reroll_indices'], best_potential_pitch['type']

        # Otherwise, just stick with what we have.
        return "", best_in_hand['type']

    # If no pitch is currently possible, we MUST re-roll.
    else:
        # If there are ways to make a pitch, choose the best one to aim for.
        if near_misses:
            # Filter out any near-misses that require more re-rolls than we have
            near_misses = [p for p in near_misses if len(p['reroll_indices'].split()) <= rerolls_remaining]
            if not near_misses: return "1 2 3", "FB" # Disaster recovery if no valid re-rolls

            # Conservative: Aim for the easiest pitch to complete.
            if aggressiveness == "conservative":
                # FB is generally easiest, then CU. Prioritize those.
                fb_targets = [p for p in near_misses if p['type'] == 'FB']
                if fb_targets:
                    target_pitch = max(fb_targets, key=lambda p: p['potential_difficulty'])
                    return target_pitch['reroll_indices'], target_pitch['type']
                
                cu_targets = [p for p in near_misses if p['type'] == 'CU']
                if cu_targets:
                    target_pitch = max(cu_targets, key=lambda p: p['potential_difficulty'])
                    return target_pitch['reroll_indices'], target_pitch['type']

            # Aggressive/Neutral: Aim for the highest potential difficulty.
            # Also consider breaking a streak for a bonus.
            for p in near_misses:
                p['score'] = p['potential_difficulty']
                current_pitch_category = "FB" if p['type'] == "FB" else "OFFSPEED"
                if streak_count >= 2 and current_pitch_category != streak_type:
                    p['score'] += min(streak_count - 1, 2) # Add setup bonus to score

            best_target = max(near_misses, key=lambda p: p['score'])
            return best_target['reroll_indices'], best_target['type']

        # Disaster scenario: No valid pitches and no near-misses.
        # Re-roll the 3 lowest dice and hope for the best, aiming for a Fastball.
        return "1 2 3", "FB"

def _analyze_dice(dice):
    """Helper to find possible and near-miss pitches."""
    possible = []
    near_misses = []
    dice_with_indices = list(enumerate(dice))

    # Check for complete pitches
    for pitch_type in ["FB", "CB", "CU"]:
        for combo_indices in combinations(range(len(dice)), 3):
            combo_dice = [dice[i] for i in combo_indices]
            if check_pitch_combo(combo_dice, pitch_type):
                possible.append({
                    "type": pitch_type,
                    "difficulty": max(combo_dice),
                    "combo": combo_dice
                })

    # Check for "near misses" (2 out of 3 dice)
    # This is a simplified check for demonstration. A more robust check could be more complex.
    # FB: two of a kind
    for i, j in combinations(range(len(dice)), 2):
        if dice[i] == dice[j]:
            reroll_indices = [str(k + 1) for k in range(len(dice)) if k not in (i, j)]
            near_misses.append({
                "type": "FB", "potential_difficulty": dice[i], "reroll_indices": " ".join(reroll_indices)
            })

    # CB: two parts of a run
    for i, j in combinations(range(len(dice)), 2):
        d1, d2 = sorted((dice[i], dice[j]))
        if d2 - d1 == 1 and d2 < 6: # e.g., have 2,3 need 1 or 4
            reroll_indices = [str(k + 1) for k in range(len(dice)) if k not in (i, j)]
            near_misses.append({
                "type": "CB", "potential_difficulty": d2 + 1, "reroll_indices": " ".join(reroll_indices)
            })
        if d2 - d1 == 2 and d2 < 6: # e.g., have 2,4 need 3
            reroll_indices = [str(k + 1) for k in range(len(dice)) if k not in (i, j)]
            near_misses.append({
                "type": "CB", "potential_difficulty": d2, "reroll_indices": " ".join(reroll_indices)
            })

    # CU: two different odd/even
    for i, j in combinations(range(len(dice)), 2):
        d1, d2 = dice[i], dice[j]
        if d1 != d2 and (d1 % 2 == d2 % 2):
            reroll_indices = [str(k + 1) for k in range(len(dice)) if k not in (i, j)]
            near_misses.append({
                "type": "CU", "potential_difficulty": max(d1, d2), "reroll_indices": " ".join(reroll_indices)
            })

    return {"possible": possible, "near_misses": near_misses}

def get_ai_hitter_choice():
    # TODO: Implement AI logic for hitter
    pass