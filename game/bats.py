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

def _calculate_pitch_success_prob(kept_dice, num_reroll, pitch_type):
    """Calculates the probability of successfully forming a pitch after a re-roll."""
    if len(kept_dice) + num_reroll < 3:
        return 0.0

    # If we can already make the pitch with the dice we kept, it's 100%
    if len(kept_dice) >= 3:
        for combo in combinations(kept_dice, 3):
            if check_pitch_combo(list(combo), pitch_type):
                return 1.0

    # If we can't make it yet, calculate the odds based on the re-roll
    successful_outcomes = 0
    possible_rolls = product(range(1, 7), repeat=num_reroll)
    total_outcomes = 6 ** num_reroll

    if total_outcomes == 0: # This case happens if num_reroll is 0 and we couldn't make it above
        return 0.0

    for roll in possible_rolls:
        final_hand = kept_dice + list(roll)
        # Check if any 3-dice combination in the final hand makes the pitch
        is_successful = False
        for combo in combinations(final_hand, 3):
            if check_pitch_combo(list(combo), pitch_type):
                is_successful = True
                break
        if is_successful:
            successful_outcomes += 1

    return successful_outcomes / total_outcomes

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

    # --- Determine Hitter's Dice Pool ---
    # For simplicity, if bonus die is available, we check both allocations
    bonus_allocations = ['none']
    if bonus_dice > 0:
        bonus_allocations = ['c', 'p']

    # We will analyze for the best case if bonus die is available
    best_case_results = {}

    for bonus_allocation in bonus_allocations:
        base_contact, base_power = _get_swing_dice(swing_type, bonus_allocation)
        final_contact_dice = max(0, base_contact + contact_mod)
        final_power_dice = max(0, base_power + power_mod)

        power_probs = _calculate_power_probs(final_power_dice)

        for pitch_type in ["FB", "CB", "CU"]:
            # --- Calculate Pitch Modifiers ---
            pitch_success_prob = _calculate_pitch_success_prob(kept_dice, num_reroll, pitch_type)

            difficulty_mod = 0
            current_pitch_category = _get_pitch_category(pitch_type)
            if current_pitch_category != pitch_streak_type and pitch_streak_count >= 2:
                difficulty_mod = min(pitch_streak_count - 1, 2)
            elif current_pitch_category == pitch_streak_type and pitch_streak_count >= 2:
                difficulty_mod = -1

            # Estimate difficulty based on kept dice - this is a simplification
            est_difficulty = _get_estimated_difficulty(kept_dice, pitch_type)
            final_difficulty = est_difficulty + difficulty_mod

            # --- Calculate Contact Probability ---
            contact_prob = _simulate_contact_prob(final_contact_dice, contact_roll_bonus, final_difficulty)

            # The final probability is conditional on the pitch being successful
            final_contact_prob = pitch_success_prob * contact_prob

            # Store results
            result_key = f"{pitch_type}_{bonus_allocation}"
            best_case_results[result_key] = {
                "pitch_type": pitch_type,
                "pitch_success_prob": pitch_success_prob,
                "single_prob": final_contact_prob * power_probs["SINGLE"],
                "double_prob": final_contact_prob * power_probs["DOUBLE"],
                "hr_prob": final_contact_prob * power_probs["HR"],
            }

    return best_case_results