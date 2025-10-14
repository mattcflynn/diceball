import random
from itertools import product, combinations
from game.pitch_utils import find_pitch_outcome, check_pitch_combo

def _get_swing_dice(swing_type, bonus_dice_allocation):
    """Determines the base number of contact and power dice for a swing."""
    if swing_type == 'p': contact_dice, power_dice = 2, 4
    elif swing_type == 'c': contact_dice, power_dice = 4, 2
    else: contact_dice, power_dice = 3, 3

    if bonus_dice_allocation == 'c': contact_dice += 1
    elif bonus_dice_allocation == 'p': power_dice += 1
    return contact_dice, power_dice

def _simulate_contact_prob(contact_dice, contact_roll_bonus, pitch_difficulty):
    """Calculates the probability of making contact (2+ successful dice or crit)."""
    if contact_dice <= 0: return 0.0

    # Generate all possible outcomes for the contact roll
    possible_rolls = product(range(1, 7), repeat=contact_dice)
    total_outcomes = 6 ** contact_dice
    successful_outcomes = 0

    for roll in possible_rolls:
        is_critical_hit = roll.count(6) >= 2
        successful_dice = sum(1 for die in roll if (die + contact_roll_bonus) >= pitch_difficulty)
        if successful_dice >= 2 or is_critical_hit:
            successful_outcomes += 1

    return successful_outcomes / total_outcomes

def _calculate_power_probs(power_dice):
    """Calculates the probability of hitting a SINGLE, DOUBLE, or HR."""
    if power_dice <= 0: return {"SINGLE": 0, "DOUBLE": 0, "HR": 0}

    # Generate all possible outcomes for the power roll
    possible_rolls = product(range(1, 7), repeat=power_dice)
    total_outcomes = 6 ** power_dice
    
    single_count, double_count, hr_count = 0, 0, 0

    for roll in possible_rolls:
        power_value = sum(roll)
        if power_value >= 17: hr_count += 1
        elif power_value >= 14: double_count += 1
        elif power_value >= 11: single_count += 1

    return {
        "SINGLE": single_count / total_outcomes,
        "DOUBLE": double_count / total_outcomes,
        "HR": hr_count / total_outcomes,
    }

def _calculate_pitch_difficulty_probs(kept_dice, num_reroll, pitch_type):
    """
    Calculates the probability of forming a pitch at each possible difficulty level.
    Returns a dictionary mapping difficulty (int) to probability (float).
    """
    difficulty_counts = {i: 0 for i in range(1, 7)}

    if len(kept_dice) + num_reroll < 3:
        return {i: 0.0 for i in range(1, 7)}

    possible_rolls = product(range(1, 7), repeat=num_reroll)
    total_outcomes = 6 ** num_reroll
    if total_outcomes == 0: # This happens if num_reroll is 0
        total_outcomes = 1 # Avoid division by zero, loop won't run

    for roll in possible_rolls:
        final_hand = kept_dice + list(roll)
        
        # Find the best possible version of this pitch type in the hand
        best_difficulty = -1
        for combo in combinations(final_hand, 3):
            if check_pitch_combo(list(combo), pitch_type):
                difficulty = max(combo)
                if difficulty > best_difficulty:
                    best_difficulty = difficulty
        
        if best_difficulty != -1:
            difficulty_counts[best_difficulty] += 1

    return {diff: count / total_outcomes for diff, count in difficulty_counts.items()}

def _get_pitch_category(pitch_type):
    """Helper to get the category ('FB' or 'OFFSPEED') of a pitch."""
    return "FB" if pitch_type == "FB" else "OFFSPEED"

def _get_estimated_difficulty(pitcher_dice, pitch_type):
    """A simple estimation of difficulty if the pitch is made."""
    _, difficulty, result = find_pitch_outcome(pitcher_dice, pitch_type)
    return difficulty if result == "STRIKE" else 3 # Assume average difficulty on failure

def calculate_bats_probabilities(
    pitcher_dice, re_roll_input, swing_type, contact_mod, power_mod, contact_roll_bonus,
    bonus_dice, pitch_streak_type, pitch_streak_count, hitter_approach, hitter_sit_guess
):
    """
    Calculates and displays the B.A.T.S. probabilities for the hitter.
    """
    # --- Determine Kept vs. Re-rolled Dice ---
    kept_dice = []
    all_indices = list(range(len(pitcher_dice)))
    reroll_indices = []
    if re_roll_input:
        reroll_indices = [int(i) - 1 for i in re_roll_input.split()]

    for i in all_indices:
        if i not in reroll_indices:
            kept_dice.append(pitcher_dice[i])

    num_reroll = len(reroll_indices)

    analysis_results = []

    # B.A.T.S. will now show the base probabilities without the bonus die for clarity.
    # The player can infer the effect of adding the bonus die.
    bonus_allocation = 'none'

    for pitch_type in ["FB", "CB", "CU"]:
        # --- Determine situational modifiers for THIS specific pitch analysis ---
        current_contact_mod, current_power_mod, current_contact_roll_bonus = 0, 0, 0
        if hitter_approach == 's':
            if hitter_sit_guess.upper() == pitch_type:
                # Assume CORRECT sit for this analysis
                current_contact_roll_bonus = 2
                current_power_mod = 1
            else:
                # Assume INCORRECT sit for this analysis
                current_contact_roll_bonus = -1
                current_power_mod = -1

        base_contact, base_power = _get_swing_dice(swing_type, bonus_allocation)
        final_contact_dice = max(0, base_contact + current_contact_mod)
        final_power_dice = max(0, base_power + current_power_mod)

        power_probs = _calculate_power_probs(final_power_dice)

        # --- Calculate Pitch Probabilities by Difficulty ---
        pitch_difficulty_probs = _calculate_pitch_difficulty_probs(kept_dice, num_reroll, pitch_type)

        for difficulty, pitch_prob in pitch_difficulty_probs.items():
            if pitch_prob < 0.01: continue # Don't show outcomes with less than 1% chance

            # --- Calculate Pitch Streak Modifiers ---
            difficulty_mod = 0
            current_pitch_category = _get_pitch_category(pitch_type)
            if current_pitch_category != pitch_streak_type and pitch_streak_count >= 2:
                difficulty_mod = min(pitch_streak_count - 1, 2)
            elif current_pitch_category == pitch_streak_type and pitch_streak_count >= 2:
                difficulty_mod = -1

            final_difficulty = difficulty + difficulty_mod

            # --- Calculate Contact Probability for this specific difficulty ---
            contact_prob = _simulate_contact_prob(final_contact_dice, current_contact_roll_bonus, final_difficulty)

            analysis_results.append({
                "pitch_id": f"{pitch_type}-{difficulty}",
                "pitch_prob": pitch_prob,
                "contact_prob": contact_prob,
                "power_probs": power_probs, # Store the independent power probabilities
            })

    return sorted(analysis_results, key=lambda x: x['pitch_prob'], reverse=True)