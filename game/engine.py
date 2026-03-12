import random
import time
from game.pitch_utils import PITCH_REQUIREMENTS, check_pitch_combo, find_pitch_outcome
from game.ai import make_pitcher_decision, make_hitter_pre_pitch_decision, make_hitter_sit_adjustment, make_hitter_swing_decision
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
    # 6 lines: top border, 3 art lines, bottom border, index
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

def get_hitter_pre_pitch_choices():
    """Handles the hitter's approach and swing type selections."""
    # Refined choices: [t]ake, [s]it on a pitch, or [w]ait (neutral)
    hitter_approach = get_validated_input(
        "\nHitter, choose your approach: [t]ake, [s]it on a pitch, or [w]ait and see: ",
        ['t', 's', 'w']
    )

    hitter_sit_guess, swing_type = None, None
    if hitter_approach != 't':
        if hitter_approach == 's':
            hitter_sit_guess = get_validated_input(
                "What pitch are you sitting on? [fb], [cb], or [cu]: ",
                ['fb', 'cb', 'cu']
            )
        swing_type = get_validated_input(
            "Choose your swing: [p]ower (2c/4p) or [c]ontact (4c/2p): ",
            ['p', 'c']
        )
    # The 'w' (wait) approach doesn't need a special guess.
    return hitter_approach, hitter_sit_guess, swing_type

def determine_swing_modifiers(hitter_approach, hitter_sit_guess, chosen_pitch):
    """Calculates the contact and power dice modifiers based on the hitter's choices."""
    contact_mod, power_mod, contact_roll_bonus = 0, 0, 0
    # This function is now only for the "shifted sit" or incorrect "hard sit"
    if hitter_approach == 's':
        if hitter_sit_guess.upper() == chosen_pitch:
            # This is the reward for a successful "shifted sit"
            print("Hitter successfully shifted their sit! BONUS: +1 to all Contact die rolls.")
            contact_roll_bonus = 1
        else:  # Sat and guessed wrong
            print("Hitter sat on the wrong pitch! PENALTY: -1 to all Contact rolls, -1 Power Die.")
            power_mod, contact_roll_bonus = -1, -1
    # If approach is 'w' (wait), mods remain 0, which is the neutral baseline.
    return contact_mod, power_mod, contact_roll_bonus

def resolve_swing(swing_type, contact_mod, power_mod, contact_roll_bonus, pitch_difficulty, bonus_dice=0, bonus_allocation=None, verbose=True):
    """Handles the dice rolls for a hitter's swing and determines the outcome."""
    if swing_type == 'p': contact_dice, power_dice = 2, 4
    else: contact_dice, power_dice = 4, 2

    if bonus_dice > 0:
        if verbose:
            print(f"\nHitter has a +{bonus_dice} bonus die from taking the last pitch!")
        if bonus_allocation is None:
            bonus_allocation = get_validated_input(
                "Where do you want to add the bonus die? [c]ontact or [p]ower: ",
                ['c', 'p']
            )
        if bonus_allocation == 'c':
            contact_dice += 1
        else:
            power_dice += 1

    final_contact_dice = max(0, contact_dice + contact_mod)
    final_power_dice = max(0, power_dice + power_mod)

    if verbose:
        print(f"\nHitter is swinging with {final_contact_dice} Contact Dice and {final_power_dice} Power Dice!")
        input(f"Press Enter for the Contact roll to beat Difficulty {pitch_difficulty}...")

    contact_roll_result = roll_dice(final_contact_dice)
    if verbose:
        print(f"Hitter rolls for Contact... {contact_roll_result}")

    # NEW: Check for the "Critical Hit" rule
    is_critical_hit = contact_roll_result.count(6) >= 2
    if verbose:
        if is_critical_hit:
            print("NATURAL 6s! A critical hit, the batter connects no matter the difficulty!")
        if contact_roll_bonus > 0:
            print(f"Applying BONUS of +{contact_roll_bonus} to each die from sitting on the right pitch!")
        elif contact_roll_bonus < 0:
            print(f"Applying PENALTY of {contact_roll_bonus} to each die from sitting on the wrong pitch!")
        time.sleep(1)

    successful_dice = sum(1 for die in contact_roll_result if (die + contact_roll_bonus) >= pitch_difficulty)

    if verbose:
        print("\n...RESULT...")
        time.sleep(1)

    if successful_dice >= 2 or is_critical_hit: # Ball is put in play!
        if verbose:
            print("CONTACT! The ball is in play!")
            input("Press Enter for the Power roll to determine the outcome...")
        power_roll_result = roll_dice(final_power_dice)
        power_value = sum(power_roll_result)
        if verbose:
            print(f"Hitter rolls for Power... {power_roll_result} = Sum: {power_value}")

        if final_power_dice >= 3:  # power swing
            if power_value >= 19: return "HR"
            if power_value >= 16: return "DOUBLE"
            if power_value >= 14: return "SINGLE"
            if power_value >= 7:
                if verbose: print("A routine grounder to the infield...")
                return "OUT"
        else:  # contact swing
            if power_value >= 10: return "SINGLE"
            if power_value >= 6:
                if verbose: print("A routine grounder to the infield...")
                return "OUT"
        if verbose: print("A weak pop-up or dribbler...")
        return "WEAK_OUT"
    elif successful_dice == 1:
        if verbose: print("FOULED OFF! One die met the difficulty.")
        return "FOUL"
    else:
        if verbose: print("Swing and a MISS!")
        return "MISS"

# --- Main Game Loop ---
def play_at_bat(pitcher_dice_pool, pitcher_is_ai=False, hitter_is_ai=False, verbose=True):
    balls, strikes, at_bat_over = 0, 0, False
    pitcher_hand, bonus_dice = ["FB", "CB", "CU"], 0
    pitch_streak_type, pitch_streak_count, pitcher_gas = None, 0, 0
    final_result, pitch_count, last_strike_swinging = None, 0, False

    if verbose:
        print("========================================")
        print("      --== DICEBALL DUEL v3 ==--      ")
        print("========================================")

    while not at_bat_over:
        pitch_count += 1
        if verbose:
            print(f"\n--- NEW PITCH --- COUNT: {balls}-{strikes} ---")
            print(f"Pitcher gas: {pitcher_gas} 🔥 (earns 1/pitch after each pitch, max 2 — spent on re-rolls)")
            if pitch_streak_count > 0:
                streak_name = "Fastball" if pitch_streak_type == "FB" else "Off-speed"
                print(f"Current Pitcher Streak: {pitch_streak_count} {streak_name} pitch(es).")
        
        # --- HITTER'S INITIAL APPROACH ---
        if hitter_is_ai:
            hitter_approach, hitter_sit_guess, swing_type = make_hitter_pre_pitch_decision(
                balls, strikes, pitch_streak_type, pitch_streak_count
            )
        else:
            hitter_approach, hitter_sit_guess, swing_type = get_hitter_pre_pitch_choices()


        is_hard_sit = hitter_approach == 's'

        # Pitcher's Turn
        if verbose: print("\nPitcher is winding up... rolls the dice!")
        pitcher_dice = roll_dice(pitcher_dice_pool)
        if verbose: display_dice(pitcher_dice)

        # --- NEW: HITTER'S SIT ADJUSTMENT PHASE ---
        if is_hard_sit:
            if hitter_is_ai:
                shift_choice, hitter_sit_guess = make_hitter_sit_adjustment(pitcher_dice, hitter_sit_guess)
                if shift_choice == 'sh':
                    is_hard_sit = False
            else:
                print(f"\nHitter, you are currently 'hard sitting' on {hitter_sit_guess.upper()}.")
                shift_choice = get_validated_input(
                    "Seeing the initial dice, do you want to [k]eep your sit or [sh]ift it? ",
                    ['k', 'sh']
                )
                if shift_choice == 'sh':
                    is_hard_sit = False # No longer a hard sit, payoff is smaller
                    hitter_sit_guess = get_validated_input(
                        "What pitch are you shifting your sit to? [fb], [cb], or [cu]: ",
                        ['fb', 'cb', 'cu']
                    )
                    print(f"Hitter has shifted their focus to {hitter_sit_guess.upper()}.")

        # Pre-calculate hard sit bonuses to be applied later
        hard_sit_contact_bonus = 0
        hard_sit_power_die_bonus = 0
        if is_hard_sit:
            # Hard sit reward: bonus to contact roll only (no extra power die)
            hard_sit_contact_bonus = 2
            hard_sit_power_die_bonus = 0
        
        # --- PUBLIC PITCHER RE-ROLL DECISION ---
        if pitcher_is_ai:
            # The AI makes both decisions (re-roll and pitch choice) at once.
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
            # Human pitcher makes decisions in two steps
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
                re_roll_input = ""

            print("\n--- Both players make their secret choice! ---")
            chosen_pitch = get_validated_input(
                "Pitcher, which pitch will you secretly commit to? [fb], [cb], or [cu]: ",
                [p.lower() for p in pitcher_hand]
            ).upper()


        # 2. Get Hitter's secret swing decision
        final_swing_decision = "n" # Default to not swinging if taking
        if hitter_approach != 't':
            if hitter_is_ai:
                final_swing_decision, swing_type = make_hitter_swing_decision(
                    pitcher_dice, re_roll_input, swing_type, balls, strikes,
                    hitter_approach, hitter_sit_guess, pitch_streak_type, pitch_streak_count, bonus_dice, pitcher_gas
                )
            else:
                while True:
                    swing_choice = get_validated_input(
                        "\nHitter, will you secretly [s]wing, [n]ot swing, or use [b]ats? ",
                        ['s', 'n', 'b']
                    )
                    if swing_choice == 'b':
                        print("\n--- B.A.T.S. ACTIVATED ---")
                        print("Calculating probabilities based on current game state...")
                        if is_hard_sit:
                            print(f"B.A.T.S. is analyzing outcomes based on your hard sit on {hitter_sit_guess.upper()}.")

                        results = calculate_bats_probabilities(pitcher_dice, re_roll_input, swing_type, 0, 0, 0, bonus_dice, pitch_streak_type, pitch_streak_count, hitter_approach, hitter_sit_guess, pitcher_gas)

                        print("\nB.A.T.S. Analysis:")
                        header = f"{'Pitch-Diff':<12} | {'Pitch %':>8} | {'Contact %':>10}"
                        print("-" * len(header))
                        print(header)
                        print("-" * len(header))
                        for res in results:
                            print(f"{res['pitch_id']:<12} | {res['pitch_prob']:>7.1%} | {res['contact_prob']:>9.1%}")
                        print("-" * len(header))

                        if results:
                            power_probs = results[0]['power_probs']
                            print("\nHit % (if contact is made):")
                            print(f"  Single: {power_probs['SINGLE']:.1%}, Double: {power_probs['DOUBLE']:.1%}, HR: {power_probs['HR']:.1%}")
                    else:
                        final_swing_decision = swing_choice
                        break
        
        # --- REVEAL AND EXECUTION ---
        if verbose:
            print("\n--- REVEAL! ---")
            full_pitch_name = PITCH_REQUIREMENTS.get(chosen_pitch, {}).get("name", "Unknown")
            print(f"Pitcher secretly committed to a {full_pitch_name}.")
            print(f"Hitter chose to {'SWING' if final_swing_decision == 's' else 'NOT SWING'}.")
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

        # 1. Check for streak-related modifiers
        if current_pitch_category != pitch_streak_type: # Streak is broken
            if pitch_streak_count >= 2:
                setup_bonus = min(pitch_streak_count - 1, 2)
                difficulty_modifier = setup_bonus
                if verbose: print(f"\nA streak of {pitch_streak_count} {pitch_streak_type} pitches sets up the {current_pitch_category}! PITCH DIFFICULTY +{setup_bonus}!")
        else: # Streak continues
            if pitch_streak_count >= 2:
                difficulty_modifier = -1
                if verbose: print(f"\nPitcher is getting predictable with {current_pitch_category} pitches! PITCH DIFFICULTY -1!")

        chosen_dice, pitch_difficulty, pitch_result = find_pitch_outcome(pitcher_dice, chosen_pitch)
        pitch_difficulty += difficulty_modifier

        if verbose:
            full_pitch_name = PITCH_REQUIREMENTS.get(chosen_pitch, {}).get("name", "Unknown")
            print(f"\nPitcher's final dice for the {full_pitch_name} are {chosen_dice}.")
            if pitch_result == "STRIKE":
                print(f"It's a perfect {full_pitch_name}! A STRIKE with a final difficulty of {pitch_difficulty}.")
            else:
                print(f"It's a failed {full_pitch_name}! A BALL with a final difficulty of {pitch_difficulty}.")
            time.sleep(1)

        # 2. Update the pitch streak for the next pitch
        if current_pitch_category == pitch_streak_type:
            pitch_streak_count += 1
        else:
            pitch_streak_type = current_pitch_category
            pitch_streak_count = 1

        # --- Resolution ---
        if hitter_approach == 't': # Hitter committed to taking from the start
            if pitch_result == "STRIKE":
                strikes += 1
                last_strike_swinging = False
                if verbose: print("\nHitter takes for a called STRIKE!")
            else:
                balls += 1
                if verbose: print("\nHitter takes for a BALL!")
            bonus_dice = 1
            if verbose: print("Patience rewarded! Hitter gets +1 bonus die on their next swing for taking the pitch.")
        elif final_swing_decision == 'n': # Hitter decided not to swing, but didn't commit to 'take'
            if pitch_result == "STRIKE":
                strikes += 1
                last_strike_swinging = False
                if verbose: print("\nHitter takes for a called STRIKE!")
            else:
                balls += 1
                if verbose: print("\nHitter takes for a BALL!")
        else: # Hitter Swings
            contact_mod, power_mod, contact_roll_bonus = 0, 0, 0

            if is_hard_sit:
                if hitter_sit_guess.upper() == chosen_pitch:
                    if verbose: print(f"Hitter's hard sit on {hitter_sit_guess.upper()} paid off! HUGE BONUS!")
                    contact_roll_bonus = hard_sit_contact_bonus
                    power_mod += hard_sit_power_die_bonus
                else:
                    if verbose: print(f"Hitter's hard sit on {hitter_sit_guess.upper()} was wrong! PENALTY: -1 to all Contact rolls, -1 Power Die.")
                    power_mod, contact_roll_bonus = -1, -1
            else:
                contact_mod, power_mod, contact_roll_bonus = determine_swing_modifiers(hitter_approach, hitter_sit_guess, chosen_pitch)

            bonus_allocation = 'c' if hitter_is_ai else None
            swing_result = resolve_swing(swing_type, contact_mod, power_mod, contact_roll_bonus, pitch_difficulty, bonus_dice, bonus_allocation, verbose)
            bonus_dice = 0

            if swing_result in ["SINGLE", "DOUBLE", "HR", "OUT", "WEAK_OUT"]:
                if verbose:
                    if swing_result == "HR": print("That ball is OBLITERATED! HOME RUN!")
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

        # Pitcher earns 1 gas after each pitch resolves (max 2)
        if not at_bat_over:
            pitcher_gas = min(pitcher_gas + 1, 2)

    return {"result": final_result, "pitches": pitch_count, "balls": balls, "strikes": strikes}
