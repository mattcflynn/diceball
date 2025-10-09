from itertools import combinations

# Use FB, CB, CU for abbreviations
PITCH_REQUIREMENTS = {
    "FB": {"type": "3-of-a-kind", "name": "Fastball"},
    "CB": {"type": "3-die run", "name": "Curveball"},
    "CU": {"type": "3 different odd or even dice", "name": "Changeup"}
}

def check_pitch_combo(dice_selection, pitch_type):
    """Checks if the 3 chosen dice form a valid pitch combo."""
    if len(dice_selection) != 3: return False
    req = PITCH_REQUIREMENTS.get(pitch_type, {}).get("type")
    if req == "3-of-a-kind":
        return dice_selection[0] == dice_selection[1] == dice_selection[2]
    if req == "3-die run":
        s_dice = sorted(dice_selection)
        return 6 not in s_dice and s_dice[0] + 1 == s_dice[1] and s_dice[1] + 1 == s_dice[2]
    if req == "3 different odd or even dice":
        all_different = len(set(dice_selection)) == 3
        if not all_different: return False
        all_odd = all(d % 2 != 0 for d in dice_selection)
        all_even = all(d % 2 == 0 for d in dice_selection)
        return all_odd or all_even
    return False

def find_pitch_outcome(dice_pool, committed_pitch):
    """
    Automatically finds the best possible version of the committed pitch.
    Returns: (chosen_dice, difficulty, pitch_result)
    """
    best_combo = None
    highest_difficulty = -1

    # Find the best valid combo for the committed pitch
    for combo in combinations(dice_pool, 3):
        if check_pitch_combo(list(combo), committed_pitch):
            difficulty = max(combo)
            if difficulty > highest_difficulty:
                highest_difficulty = difficulty
                best_combo = sorted(list(combo))

    if best_combo:
        return best_combo, highest_difficulty, "STRIKE"
    else:
        # If no valid combo, it's a failed pitch (ball). The difficulty is the highest 3 dice.
        failed_attempt_dice = sorted(dice_pool, reverse=True)[:3]
        return failed_attempt_dice, max(failed_attempt_dice), "BALL"
