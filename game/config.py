from dataclasses import dataclass


@dataclass
class GameConfig:
    """All tunable levers for Diceball simulation."""

    # Pitcher
    pitcher_dice: int = 4
    gas_per_at_bat: int = None  # None = auto: max(0, 6 - pitcher_dice)

    # Pitch requirements: how many dice must satisfy the pattern
    fb_match_count: int = 3  # 3 = three-of-a-kind, 2 = pair
    cb_run_length: int = 3   # 3 = full 3-die run, 2 = any 2 consecutive
    cb_allow_six: bool = False  # allow 6 to be part of a CB run
    cu_diff_count: int = 3   # 3 = three different same-parity, 2 = any two different same-parity

    # Pitch difficulty: which die in the matching set determines difficulty
    difficulty_method: str = "max"  # "max" (high die), "mid" (middle die), "min" (low die)

    # Hitter commit bonuses
    correct_commit_bonus: int = 1
    wrong_commit_penalty: int = -1

    # Information asymmetry
    hidden_reroll: bool = False  # True = hitter decides before pitcher re-rolls

    def effective_gas(self):
        if self.gas_per_at_bat is not None:
            return self.gas_per_at_bat
        return max(0, 6 - self.pitcher_dice)


DEFAULT_CONFIG = GameConfig()
