from itertools import combinations
from game.pitch_utils import check_pitch_combo

def make_pitcher_decision(dice, balls, strikes, streak_type, streak_count):
    """
    Determines the AI pitcher's move, including re-roll and pitch commitment.

    Args:
        dice: The pitcher's current dice roll.
        balls: Current ball count.
        strikes: Current strike count.
        streak_type: The type of the current pitch streak (e.g., "FB").
        streak_count: The length of the current pitch streak.

    Returns:
        A tuple containing (re_roll_input, chosen_pitch).
        re_roll_input (str): A string of dice indices to re-roll (e.g., "1 2 3").
        chosen_pitch (str): The pitch the AI commits to (e.g., "FB").
    """
    print("AI Pitcher is thinking...")

    # --- AI Logic Placeholder ---
    # This is a simple starting point. We will make this much smarter.
    # TODO: Add logic based on count, streak, and bluffing.

    possible_pitches = []
    for pitch_type in ["FB", "CB", "CU"]:
        for combo in combinations(dice, 3):
            if check_pitch_combo(list(combo), pitch_type):
                difficulty = max(combo)
                possible_pitches.append({
                    "type": pitch_type,
                    "difficulty": difficulty,
                    "combo": list(combo)
                })

    # Simple Strategy: Find the best possible pitch right now.
    if possible_pitches:
        # Prioritize highest difficulty pitch
        best_pitch = max(possible_pitches, key=lambda x: x['difficulty'])
        chosen_pitch = best_pitch['type']
        re_roll_input = "" # Don't re-roll if we have a good pitch
    else:
        # If no pitch is possible, re-roll the three lowest dice.
        # This is a naive strategy we can improve later.
        chosen_pitch = "FB" # Default guess, will be re-evaluated after re-roll
        re_roll_input = "1 2 3"

    return re_roll_input, chosen_pitch

def get_ai_hitter_choice():
    # TODO: Implement AI logic for hitter
    pass