from itertools import combinations
from collections import Counter

# Use FB, CB, CU for abbreviations
PITCH_REQUIREMENTS = {
    "FB": {"type": "3-of-a-kind", "name": "Fastball"},
    "CB": {"type": "3-die run", "name": "Curveball"},
    "CU": {"type": "3 different odd or even dice", "name": "Changeup"}
}


def calc_difficulty(key_dice, method):
    """Compute difficulty from the key dice using the specified method."""
    s = sorted(key_dice)
    if method == "min":
        return s[0]
    if method == "mid":
        return s[len(s) // 2]
    return s[-1]  # default: "max"


def find_key_dice(combo, pitch_type, config):
    """
    Returns the key dice that form the pitch within a 3-die combo, or None if invalid.
    Selects the best key set (maximizing difficulty by config.difficulty_method).
    """
    if pitch_type == "FB":
        counts = Counter(combo)
        valid = [(val, cnt) for val, cnt in counts.items() if cnt >= config.fb_match_count]
        if not valid:
            return None
        best_val = max(valid, key=lambda x: x[0])[0]
        return [best_val] * config.fb_match_count

    if pitch_type == "CB":
        eligible = combo if config.cb_allow_six else [d for d in combo if d != 6]
        if config.cb_run_length == 3:
            s = sorted(eligible)
            if len(s) < 3 or s[0] + 1 != s[1] or s[1] + 1 != s[2]:
                return None
            return s
        elif config.cb_run_length == 2:
            unique_el = sorted(set(eligible))
            best_pair, best_diff = None, -1
            for i in range(len(unique_el) - 1):
                if unique_el[i] + 1 == unique_el[i + 1]:
                    pair = [unique_el[i], unique_el[i + 1]]
                    d = calc_difficulty(pair, config.difficulty_method)
                    if d > best_diff:
                        best_diff, best_pair = d, pair
            return best_pair

    if pitch_type == "CU":
        if config.cu_diff_count == 3:
            if len(set(combo)) != 3:
                return None
            s = sorted(combo)
            if all(d % 2 != 0 for d in s) or all(d % 2 == 0 for d in s):
                return s
            return None
        elif config.cu_diff_count == 2:
            odds = sorted(set(d for d in combo if d % 2 != 0))
            evens = sorted(set(d for d in combo if d % 2 == 0))
            best_pair, best_diff = None, -1
            for group in [odds, evens]:
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        pair = [group[i], group[j]]
                        d = calc_difficulty(pair, config.difficulty_method)
                        if d > best_diff:
                            best_diff, best_pair = d, pair
            return best_pair

    return None


def check_pitch_combo(dice_selection, pitch_type, config=None):
    """Checks if the 3 chosen dice form a valid pitch combo."""
    if len(dice_selection) != 3:
        return False
    if config is None:
        from game.config import DEFAULT_CONFIG
        config = DEFAULT_CONFIG
    return find_key_dice(dice_selection, pitch_type, config) is not None


def find_pitch_outcome(dice_pool, committed_pitch, config=None):
    """
    Automatically finds the best possible version of the committed pitch.
    Returns: (chosen_dice, difficulty, pitch_result)
    """
    if config is None:
        from game.config import DEFAULT_CONFIG
        config = DEFAULT_CONFIG

    best_combo = None
    best_key_dice = None
    highest_difficulty = -1

    for combo in combinations(dice_pool, 3):
        key_dice = find_key_dice(list(combo), committed_pitch, config)
        if key_dice is not None:
            difficulty = calc_difficulty(key_dice, config.difficulty_method)
            if difficulty > highest_difficulty:
                highest_difficulty = difficulty
                best_combo = sorted(list(combo))
                best_key_dice = key_dice

    if best_combo:
        return best_combo, highest_difficulty, "STRIKE"
    else:
        failed_attempt_dice = sorted(dice_pool, reverse=True)[:3]
        difficulty = calc_difficulty(failed_attempt_dice, config.difficulty_method)
        return failed_attempt_dice, difficulty, "BALL"
