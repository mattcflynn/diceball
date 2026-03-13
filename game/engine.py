import random
import time
from game.pitch_utils import PITCH_REQUIREMENTS, check_pitch_combo, find_pitch_outcome
from game.ai import make_pitcher_decision, make_hitter_decision
from game.bats import calculate_bats_probabilities

# --- Helper Functions ---

def roll_dice(num_dice):
    """Rolls a number of d6 and returns a sorted list."""
    if num_dice <= 0:
        return []
    return sorted([random.randint(1, 6) for _ in range(num_dice)])

def display_dice(dice_pool):
    """Creates an ASCII display for a list of dice."""
    if not dice_pool:
        return
    dice_art = {
        1: "|       |\n|   o   |\n|       |", 2: "| o     |\n|       |\n|     o |",
        3: "| o     |\n|   o   |\n|     o |", 4: "| o   o |\n|       |\n| o   o |",
        5: "| o   o |\n|   o   |\n| o   o |", 6: "| o   o |\n| o   o |\n| o   o |"
    }
    lines = [""] * 6
    border = "+-------+"
    for i, die in enumerate(dice_pool):
        art = dice_art[die].split("\n")
        lines[0] += f" {border} "
        lines[1] += f" {art[0]} "
        lines[2] += f" {art[1]} "
        lines[3] += f" {art[2]} "
        lines[4] += f" {border} "
        lines[5] += f"    ({i+1})    "
    for line in lines:
        print(line)

def get_validated_input(prompt, valid_options):
    """Generic function to get validated user input."""
    while True:
        user_input = input(prompt).lower()
        if user_input in valid_options:
            return user_input
        print(f"Invalid input. Please choose from: {', '.join(valid_options)}")

def get_hitter_post_dice_choices(pitcher_dice, re_roll_input, balls,
                                  pitch_streak_type, pitch_streak_count, pitcher_gas, swing_type_hint=None):
    """
    After seeing the pitcher's dice and re-roll plan, the hitter commits.
    Returns (final_swing_decision, commit_pitch, swing_type)
    """
    while True:
        choice = get_validated_input(
            "\nHitter — commit to pitch: [fb] [cb] [cu] to swing, [n] to take, or [b]ats: ",
            ['fb', 'cb', 'cu', 'n', 'b']
        )
        if choice == 'b':
            # Show BATS for each possible commit
            print("\n--- B.A.T.S. ACTIVATED ---")
            commit_to = get_validated_input(
                "Analyze commit to which pitch? [fb] [cb] [cu]: ",
                ['fb', 'cb', 'cu']
            )
            swing_to_analyze = get_validated_input(
                "With [p]ower (2c/4p) or [c]ontact (4c/2p) swing? ",
                ['p', 'c']
            )
            results = calculate_bats_probabilities(
                pitcher_dice, re_roll_input, swing_to_analyze, 0, 0, 0,
                0, pitch_streak_type, pitch_streak_count, 's', commit_to, pitcher_gas
            )
            print(f"\nB.A.T.S. — committing to {commit_to.upper()} with {'power' if swing_to_analyze == 'p' else 'contact'} swing:")
            header = f"{'Pitch-Diff':<12} | {'Pitch %':>8} | {'Contact %':>10}"
            print("-" * len(header))
            print(header)
            print("-" * len(header))
            for res in results:
                print(f"{res['pitch_id']:<12} | {res['pitch_prob']:>7.1%} | {res['contact_prob']:>9.1%}")
            print("-" * len(header))
            if results:
                power_probs = results[0]['power_probs']
                print(f"\nHit % (if contact): Single {power_probs['SINGLE']:.1%}  Double {power_probs['DOUBLE']:.1%}  HR {power_probs['HR']:.1%}")
                print("(Note: B.A.T.S. hit% is approximate — shown without bonus die allocation)")
        elif choice == 'n':
            return 'n', None, None
        else:
            commit_pitch = choice
            swing_type = get_validated_input(
                "Swing type: [p]ower (2c/4p) or [c]ontact (4c/2p): ",
                ['p', 'c']
            )
            return 's', commit_pitch, swing_type

def resolve_swing(swing_type, contact_mod, power_mod, contact_roll_bonus, pitch_difficulty, verbose=True):
    """Handles the dice rolls for a hitter's swing and determines the outcome."""
    if swing_type == 'p': contact_dice, power_dice = 2, 4
    else: contact_dice, power_dice = 4, 2

    final_contact_dice = max(0, contact_dice + contact_mod)
    final_power_dice = max(0, power_dice + power_mod)

    if verbose:
        print(f"\nHitter is swinging with {final_contact_dice} Contact Dice and {final_power_dice} Power Dice!")
        input(f"Press Enter for the Contact roll to beat Difficulty {pitch_difficulty}...")

    contact_roll_result = roll_dice(final_contact_dice)
    if verbose:
        print(f"Hitter rolls for Contact... {contact_roll_result}")

    is_critical_hit = contact_roll_result.count(6) >= 2
    if verbose:
        if is_critical_hit:
            print("NATURAL 6s! A critical hit, the batter connects no matter the difficulty!")
        if contact_roll_bonus > 0:
            print(f"Applying BONUS of +{contact_roll_bonus} to each die from committing to the right pitch!")
        elif contact_roll_bonus < 0:
            print(f"Applying PENALTY of {contact_roll_bonus} to each die from committing to the wrong pitch!")
        time.sleep(1)

    successful_dice = sum(1 for die in contact_roll_result if (die + contact_roll_bonus) >= pitch_difficulty)

    if verbose:
        print("\n...RESULT...")
        time.sleep(1)

    if successful_dice >= 2 or is_critical_hit:
        power_roll_result = roll_dice(final_power_dice)
        power_value = sum(power_roll_result)
        if verbose:
            print("CONTACT! The ball is in play!")
            input("Press Enter for the Power roll...")
            print(f"Power roll: {power_roll_result} (sum {power_value})")

        if final_power_dice >= 3:  # power swing (2c/4p) — full range: HR, TRIPLE, DOUBLE, SINGLE
            if power_value >= 20: result = "HR"
            elif power_value == 19: result = "TRIPLE"
            elif power_value == 18: result = "DOUBLE"
            elif power_value >= 16: result = "SINGLE"
            elif power_value >= 7:
                if verbose: print("A routine grounder to the infield...")
                result = "OUT"
            else:
                if verbose: print("A weak pop-up or dribbler...")
                result = "WEAK_OUT"
        else:  # contact swing (4c/2p) — hard line drives; ceiling is double (max roll)
            if power_value == 12: result = "DOUBLE"
            elif power_value >= 10: result = "SINGLE"
            elif power_value >= 6:
                if verbose: print("A routine grounder to the infield...")
                result = "OUT"
            else:
                if verbose: print("A weak pop-up or dribbler...")
                result = "WEAK_OUT"

        return result
    elif successful_dice == 1:
        if verbose: print("FOULED OFF! One die met the difficulty.")
        return "FOUL"
    else:
        if verbose: print("Swing and a MISS!")
        return "MISS"

# --- Main Game Loop ---
def play_at_bat(pitcher_dice_pool, pitcher_is_ai=False, hitter_is_ai=False, verbose=True):
    balls, strikes, at_bat_over = 0, 0, False
    pitcher_hand = ["FB", "CB", "CU"]
    pitch_streak_type, pitch_streak_count = None, 0
    pitcher_gas = max(0, 6 - pitcher_dice_pool)  # 4 dice → 2 gas, 5 dice → 1 gas
    # Gas is spent down, not refilled — pitcher weakens over a long at-bat
    final_result, pitch_count, last_strike_swinging = None, 0, False

    if verbose:
        print("========================================")
        print("      --== DICEBALL DUEL v4 ==--      ")
        print("========================================")
        print(f"Pitcher starts with {pitcher_gas} gas 🔥 (spent on re-rolls, not refilled)")

    while not at_bat_over:
        pitch_count += 1
        if verbose:
            print(f"\n--- NEW PITCH --- COUNT: {balls}-{strikes} ---")
            print(f"Pitcher gas remaining: {pitcher_gas} 🔥")
            if pitch_streak_count > 0:
                streak_name = "Fastball" if pitch_streak_type == "FB" else "Off-speed"
                print(f"Current Pitcher Streak: {pitch_streak_count} {streak_name} pitch(es).")

        # --- PITCHER ROLLS ---
        if verbose: print("\nPitcher is winding up... rolls the dice!")
        pitcher_dice = roll_dice(pitcher_dice_pool)
        if verbose: display_dice(pitcher_dice)

        # --- PUBLIC PITCHER RE-ROLL DECISION + SECRET COMMIT ---
        if pitcher_is_ai:
            re_roll_input, chosen_pitch = make_pitcher_decision(
                pitcher_dice, balls, strikes, pitch_streak_type, pitch_streak_count, pitcher_gas
            )
            if verbose:
                if re_roll_input:
                    print(f"\nThe AI pitcher will re-roll dice: {re_roll_input}")
                else:
                    print("\nThe AI pitcher will not re-roll any dice.")
                print("--- AI pitcher has secretly chosen its pitch! ---")
        else:
            re_roll_input = ""
            if pitcher_gas > 0:
                while True:
                    print(f"\nPitcher, you have {pitcher_gas} gas 🔥. Each die re-rolled costs 1 gas.")
                    re_roll_input = input("Choose dice to re-roll (e.g., '1 3 4') or press Enter to skip: ")
                    if not re_roll_input:
                        break
                    num_to_reroll = len(re_roll_input.split())
                    if num_to_reroll > pitcher_gas:
                        print(f"Not enough gas! You have {pitcher_gas} but tried to use {num_to_reroll}.")
                    else:
                        break
            else:
                print("\nPitcher is out of gas 💨 — no re-rolls available.")

            print("\n--- Both players now make their secret choices! ---")
            chosen_pitch = get_validated_input(
                "Pitcher, which pitch will you secretly commit to? [fb], [cb], or [cu]: ",
                [p.lower() for p in pitcher_hand]
            ).upper()

        # --- HITTER'S DECISION (after seeing dice + re-roll plan) ---
        if hitter_is_ai:
            final_swing_decision, commit_pitch, swing_type = make_hitter_decision(
                pitcher_dice, re_roll_input, balls, strikes,
                pitch_streak_type, pitch_streak_count, pitcher_gas
            )
        else:
            final_swing_decision, commit_pitch, swing_type = get_hitter_post_dice_choices(
                pitcher_dice, re_roll_input, balls,
                pitch_streak_type, pitch_streak_count, pitcher_gas
            )

        # --- REVEAL ---
        if verbose:
            print("\n--- REVEAL! ---")
            full_pitch_name = PITCH_REQUIREMENTS.get(chosen_pitch, {}).get("name", "Unknown")
            print(f"Pitcher committed to a {full_pitch_name}.")
            if final_swing_decision == 's':
                print(f"Hitter committed to {commit_pitch.upper()} and SWINGS!")
            else:
                print("Hitter TAKES.")
            time.sleep(1)

        # Execute the re-roll
        if re_roll_input:
            num_rerolled = len(re_roll_input.split())
            pitcher_gas -= num_rerolled
            try:
                indices = [int(i) - 1 for i in re_roll_input.split()]
                new_dice = roll_dice(len(indices))
                for i, new_die in zip(indices, new_dice):
                    if 0 <= i < len(pitcher_dice): pitcher_dice[i] = new_die
                pitcher_dice.sort()
                if verbose:
                    print("\nPitcher adjusts... the final dice are:")
                    display_dice(pitcher_dice)
            except (ValueError, IndexError):
                if verbose: print("Invalid re-roll input. Keeping all dice.")

        # --- PITCH OUTCOME ---
        difficulty_modifier = 0
        current_pitch_category = "FB" if chosen_pitch == "FB" else "OFFSPEED"

        if current_pitch_category != pitch_streak_type:
            if pitch_streak_count >= 2:
                setup_bonus = min(pitch_streak_count - 1, 2)
                difficulty_modifier = setup_bonus
                if verbose: print(f"\nStreak of {pitch_streak_count} {pitch_streak_type} pitches sets up the {current_pitch_category}! PITCH DIFFICULTY +{setup_bonus}!")
        else:
            if pitch_streak_count >= 2:
                difficulty_modifier = -1
                if verbose: print(f"\nPitcher getting predictable with {current_pitch_category} pitches! PITCH DIFFICULTY -1!")

        chosen_dice, pitch_difficulty, pitch_result = find_pitch_outcome(pitcher_dice, chosen_pitch)
        pitch_difficulty += difficulty_modifier

        if verbose:
            full_pitch_name = PITCH_REQUIREMENTS.get(chosen_pitch, {}).get("name", "Unknown")
            print(f"\nPitcher's final dice for the {full_pitch_name} are {chosen_dice}.")
            if pitch_result == "STRIKE":
                print(f"It's a {full_pitch_name}! STRIKE — difficulty {pitch_difficulty}.")
            else:
                print(f"Failed {full_pitch_name}! BALL — difficulty {pitch_difficulty}.")
            time.sleep(1)

        if current_pitch_category == pitch_streak_type:
            pitch_streak_count += 1
        else:
            pitch_streak_type = current_pitch_category
            pitch_streak_count = 1

        # --- RESOLUTION ---
        if final_swing_decision == 'n':
            if pitch_result == "STRIKE":
                strikes += 1
                last_strike_swinging = False
                if verbose: print("\nHitter takes for a called STRIKE!")
            else:
                balls += 1
                if verbose: print("\nHitter takes for a BALL!")
        else:  # Hitter swings
            # Commit bonus: +1 if committed to correct pitch, -1 if wrong
            contact_roll_bonus = 0
            if commit_pitch:
                if commit_pitch.upper() == chosen_pitch:
                    contact_roll_bonus = 1
                    if verbose: print(f"\nHitter's commit on {commit_pitch.upper()} was RIGHT! +1 to all contact dice.")
                else:
                    contact_roll_bonus = -1
                    if verbose: print(f"\nHitter committed to {commit_pitch.upper()} but it's a {chosen_pitch}! -1 to all contact dice.")

            swing_result = resolve_swing(swing_type, 0, 0, contact_roll_bonus, pitch_difficulty, verbose)

            if swing_result in ["SINGLE", "DOUBLE", "TRIPLE", "HR", "OUT", "WEAK_OUT"]:
                if verbose:
                    if swing_result == "HR": print("That ball is OBLITERATED! HOME RUN!")
                    elif swing_result == "TRIPLE": print("Screaming line drive into the corner — TRIPLE!")
                    elif swing_result == "DOUBLE": print("Smoked into the gap! That's a DOUBLE!")
                    elif swing_result == "SINGLE": print("A sharp line drive for a SINGLE!")
                    else: print("...and the defense makes the play! OUT!")
                final_result = swing_result
                at_bat_over = True
            elif swing_result == "FOUL":
                if strikes < 2: strikes += 1
            elif swing_result == "MISS":
                strikes += 1
                last_strike_swinging = True

        # Check end of at-bat conditions
        if not at_bat_over:
            if strikes >= 3:
                if verbose: print("\nSTRIKE THREE! You're out!")
                final_result = "K_S" if last_strike_swinging else "K_L"
                at_bat_over = True
            if balls >= 4:
                if verbose: print("\nBALL FOUR! Take your base.")
                final_result = "BB"
                at_bat_over = True

    return {"result": final_result, "pitches": pitch_count, "balls": balls, "strikes": strikes}
