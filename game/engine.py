import random
import time
from game.pitch_utils import PITCH_REQUIREMENTS, check_pitch_combo, find_pitch_outcome
from game.ai import make_pitcher_decision

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
            "Choose your swing: [p]ower (2c/4p), [c]ontact (4c/2p), or [b]alanced (3c/3p): ",
            ['p', 'c', 'b']
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
            print("Hitter sat on the wrong pitch! PENALTY: -1 Contact Die, -1 Power Die.")
            contact_mod, power_mod = -1, -1
    # If approach is 'w' (wait), mods remain 0, which is the neutral baseline.
    return contact_mod, power_mod, contact_roll_bonus

def resolve_swing(swing_type, contact_mod, power_mod, contact_roll_bonus, pitch_difficulty, bonus_dice=0):
    """Handles the dice rolls for a hitter's swing and determines the outcome."""
    if swing_type == 'p': contact_dice, power_dice = 2, 4
    elif swing_type == 'c': contact_dice, power_dice = 4, 2
    else: contact_dice, power_dice = 3, 3

    if bonus_dice > 0:
        print(f"\nHitter has a +{bonus_dice} bonus die from taking the last pitch!")
        bonus_allocation = get_validated_input(
            "Where do you want to add the bonus die? [c]ontact or [p]ower: ",
            ['c', 'p']
        )
        if bonus_allocation == 'c':
            contact_dice += bonus_dice
        else:
            power_dice += bonus_dice

    final_contact_dice = max(0, contact_dice + contact_mod)
    final_power_dice = max(0, power_dice + power_mod)

    print(f"\nHitter is swinging with {final_contact_dice} Contact Dice and {final_power_dice} Power Dice!")
    input(f"Press Enter for the Contact roll to beat Difficulty {pitch_difficulty}...")
    
    contact_roll_result = roll_dice(final_contact_dice)
    print(f"Hitter rolls for Contact... {contact_roll_result}")

    # NEW: Check for the "Critical Hit" rule
    is_critical_hit = contact_roll_result.count(6) >= 2
    if is_critical_hit:
        print("NATURAL 6s! A critical hit, the batter connects no matter the difficulty!")

    if contact_roll_bonus > 0:
        print(f"Applying BONUS of +{contact_roll_bonus} to each die from sitting on the right pitch!")
    elif contact_roll_bonus < 0:
        print(f"Applying PENALTY of {contact_roll_bonus} to each die from sitting on the wrong pitch!")
    time.sleep(1)

    successful_dice = sum(1 for die in contact_roll_result if (die + contact_roll_bonus) >= pitch_difficulty)
    
    print("\n...RESULT...")
    time.sleep(1)

    if successful_dice >= 2 or is_critical_hit: # Ball is put in play!
        print("CONTACT! The ball is in play!")
        input("Press Enter for the Power roll to determine the outcome...")
        power_roll_result = roll_dice(final_power_dice)
        power_value = sum(power_roll_result)
        print(f"Hitter rolls for Power... {power_roll_result} = Sum: {power_value}")
        
        # New outcome table based on Power roll
        if power_value >= 17: return "HR"
        if power_value >= 14: return "DOUBLE"
        if power_value >= 11: return "SINGLE"
        if power_value >= 7:
            print("A routine grounder to the infield...")
            return "OUT"
        print("A weak pop-up or dribbler...")
        return "WEAK_OUT"
    elif successful_dice == 1:
        print("FOULED OFF! One die met the difficulty.")
        return "FOUL"
    else:
        print("Swing and a MISS!")
        return "MISS"

# --- Main Game Loop ---
def play_at_bat(pitcher_dice_pool, pitcher_is_ai=False):
    balls, strikes, at_bat_over = 0, 0, False
    pitcher_hand, bonus_dice = ["FB", "CB", "CU"], 0
    pitch_streak_type, pitch_streak_count = None, 0

    print("========================================")
    print("      --== DICEBALL DUEL v3 ==--      ")
    print("========================================")

    while not at_bat_over:
        print(f"\n--- NEW PITCH --- COUNT: {balls}-{strikes} ---")
        if pitch_streak_count > 0:
            streak_name = "Fastball" if pitch_streak_type == "FB" else "Off-speed"
            print(f"Current Pitcher Streak: {pitch_streak_count} {streak_name} pitch(es).")
        
        # --- HITTER'S INITIAL APPROACH ---
        # TODO: Add AI hitter logic here
        hitter_approach, hitter_sit_guess, swing_type = get_hitter_pre_pitch_choices() # Assuming human hitter for now


        is_hard_sit = hitter_approach == 's'

        # Pitcher's Turn
        print("\nPitcher is winding up... rolls the dice!")
        pitcher_dice = roll_dice(pitcher_dice_pool)
        display_dice(pitcher_dice)

        # --- NEW: HITTER'S SIT ADJUSTMENT PHASE ---
        if is_hard_sit:
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
            # We check for success later, but define the potential bonus now
            hard_sit_contact_bonus = 2
            hard_sit_power_die_bonus = 1
        
        # --- PUBLIC PITCHER RE-ROLL DECISION ---
        if pitcher_is_ai:
            # The AI makes both decisions (re-roll and pitch choice) at once.
            re_roll_input, chosen_pitch = make_pitcher_decision(
                pitcher_dice, balls, strikes, pitch_streak_type, pitch_streak_count
            )
            # Announce the public part of the AI's decision (the re-roll)
            if re_roll_input:
                print(f"\nThe AI pitcher will re-roll dice: {re_roll_input}")
            else:
                print("\nThe AI pitcher will not re-roll any dice.")
            print("--- AI pitcher has secretly chosen its pitch! ---")
        else:
            # Human pitcher makes decisions in two steps
            print("\nPitcher, publicly declare which dice you will re-roll.")
            re_roll_input = input("Choose dice to re-roll (e.g., '1 3 4') or press Enter: ")
            print("\n--- Both players make their secret choice! ---")
            chosen_pitch = get_validated_input(
                "Pitcher, which pitch will you secretly commit to? [fb], [cb], or [cu]: ",
                [p.lower() for p in pitcher_hand]
            ).upper()


        # 2. Get Hitter's secret swing decision
        final_swing_decision = "n" # Default to not swinging if taking
        if hitter_approach != 't':
            final_swing_decision = get_validated_input(
                "\nHitter, will you secretly [s]wing or [n]ot swing? ",
                ['s', 'n']
            )
        
        # --- REVEAL AND EXECUTION ---
        print("\n--- REVEAL! ---")
        full_pitch_name = PITCH_REQUIREMENTS.get(chosen_pitch, {}).get("name", "Unknown")
        print(f"Pitcher secretly committed to a {full_pitch_name}.")
        print(f"Hitter chose to {'SWING' if final_swing_decision == 's' else 'NOT SWING'}.")
        time.sleep(1)
        
        # Execute the re-roll
        if re_roll_input:
            try:
                indices = [int(i) - 1 for i in re_roll_input.split()]
                new_dice = roll_dice(len(indices))
                for i, new_die in zip(indices, new_dice):
                    if 0 <= i < len(pitcher_dice): pitcher_dice[i] = new_die
                pitcher_dice.sort()
                print("\nPitcher adjusts... the final dice are:")
                display_dice(pitcher_dice)
            except (ValueError, IndexError):
                print("Invalid re-roll input. Keeping all dice.")

        # --- PITCH OUTCOME ---
        # The game now automatically finds the best pitch outcome.
        difficulty_modifier = 0
        current_pitch_category = "FB" if chosen_pitch == "FB" else "OFFSPEED"

        # 1. Check for streak-related modifiers
        if current_pitch_category != pitch_streak_type: # Streak is broken
            if pitch_streak_count >= 2:
                setup_bonus = min(pitch_streak_count - 1, 2)  # Cap the setup bonus at +2
                difficulty_modifier = setup_bonus
                print(f"\nA streak of {pitch_streak_count} {pitch_streak_type} pitches sets up the {current_pitch_category}! PITCH DIFFICULTY +{setup_bonus}!")
        else: # Streak continues
            if pitch_streak_count >= 2: # This is the 3rd or more consecutive pitch of this type
                difficulty_modifier = -1
                print(f"\nPitcher is getting predictable with {current_pitch_category} pitches! PITCH DIFFICULTY -1!")

        chosen_dice, pitch_difficulty, pitch_result = find_pitch_outcome(pitcher_dice, chosen_pitch)
        pitch_difficulty += difficulty_modifier

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
                strikes += 1; print("\nHitter takes for a called STRIKE!")
            else:
                balls += 1; print("\nHitter takes for a BALL!")
            bonus_dice = 1 # Award the bonus die for the next pitch
            print("Patience rewarded! Hitter gets +1 bonus die on their next swing for taking the pitch.")
        elif final_swing_decision == 'n': # Hitter decided not to swing, but didn't commit to 'take'
            if pitch_result == "STRIKE": strikes += 1; print("\nHitter takes for a called STRIKE!")
            else: balls += 1; print("\nHitter takes for a BALL!")
        else: # Hitter Swings
            contact_mod, power_mod, contact_roll_bonus = 0, 0, 0
            
            if is_hard_sit:
                if hitter_sit_guess.upper() == chosen_pitch:
                    print(f"Hitter's hard sit on {hitter_sit_guess.upper()} paid off! HUGE BONUS!")
                    contact_roll_bonus = hard_sit_contact_bonus
                    power_mod += hard_sit_power_die_bonus
                else:
                    print(f"Hitter's hard sit on {hitter_sit_guess.upper()} was wrong! PENALTY: -1 Contact Die, -1 Power Die.")
                    contact_mod, power_mod = -1, -1
            else: # It was a 'wait' or a 'shifted sit'
                contact_mod, power_mod, contact_roll_bonus = determine_swing_modifiers(hitter_approach, hitter_sit_guess, chosen_pitch)

            swing_result = resolve_swing(swing_type, contact_mod, power_mod, contact_roll_bonus, pitch_difficulty, bonus_dice)
            bonus_dice = 0 # Reset bonus dice after any swing attempt

            if swing_result in ["SINGLE", "DOUBLE", "HR", "OUT", "WEAK_OUT"]:
                if swing_result == "HR": print("That ball is OBLITERATED! HOME RUN!")
                elif swing_result == "DOUBLE": print("Smoked into the gap! That's a DOUBLE!")
                elif swing_result == "SINGLE": print("A sharp line drive for a SINGLE!")
                else: # It's an OUT or WEAK_OUT
                    print("...and the defense makes the play! OUT!")
                at_bat_over = True
            elif swing_result == "FOUL":
                if strikes < 2: strikes += 1
            elif swing_result == "MISS":
                strikes += 1
        
        # Check end of at-bat conditions
        if not at_bat_over:
            if strikes >= 3: print("\nSTRIKE THREE! You're out!"); at_bat_over = True
            if balls >= 4: print("\nBALL FOUR! Take your base."); at_bat_over = True
