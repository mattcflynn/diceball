"""All tunable levers. Rules levers change the game; AI levers change how mortals play it."""
import json
from dataclasses import dataclass, asdict, fields


@dataclass
class Config:
    # --- Table ---
    grid_size: int = 2             # 2 = 2x2 zone (hearts A-4), 3 = 3x3 (hearts A-9)
    deck_mix: tuple = (13, 13, 13) # cards per suit (spades, diamonds, clubs); trimmed from K down
    removed_cards: str = ""        # specific cards out of the deck, e.g. "2S,7S,KD"

    # --- Pitcher cards ---
    hand_size: int = 10            # cards drawn at the start of each at-bat
    draw_per_pitch: int = 3        # cards drawn after each pitch
    max_hand: int = 0              # hand cap (0 = none)
    max_grid: int = 9              # max cards played into the zone
    face_value: int = 10           # value of J/Q/K (A = 1)
    reshuffle_when_empty: bool = True  # deck empty mid-AB -> shuffle discards back in

    # --- Batter dice ---
    batter_dice: int = 10
    die_sides: int = 6
    card_cost: int = 1                 # dice lost per extra card bet on (2 cards = 1, 3 cards = 2)
    mix_penalty: tuple = (0, 1, 2)     # additional dice lost for betting on 1 / 2 / 3 pitch types
    power_rule: str = "reserve"        # reserve = unbet dice | all_but_contact = every die not on the hit card
    power_keep: int = 0                # power = sum of the highest k power dice (0 = all)
    power_thresholds: tuple = (14, 19, 22, 23)  # min power sum for 1B, 2B, 3B, HR
    power_bonus: int = 0               # flat add to power sum (hitter strength)
    spread_power: int = 0              # power sum lost per extra card bet on (sitting on one zone = A swing)

    # --- Power hand / climb (power_system = hand | climb) ---
    power_system: str = "sum"          # sum = power thresholds | hand = Yahtzee-style hand | climb = streak of non-dropping dice
    climb_ladder: tuple = (3, 4, 5)    # climb streak lengths for 1B, 2B, HR (a strictly rising 2B streak = 3B)
    hand_dice: int = 5                 # most power dice rolled for the hand
    hand_map: str = "trips=SINGLE,straight=DOUBLE,four_kind=TRIPLE,full_house=HR,five_kind=HR"  # unlisted hands = out
    rerolls: int = 3                   # re-rolls per at-bat (each re-rolls one power die)
    reroll_card_cost: int = 1          # re-rolls lost per extra card bet on
    reroll_mix_penalty: tuple = (0, 1, 2)  # re-rolls lost for betting on 1 / 2 / 3 pitch types
    reroll_per_ball: int = 0           # re-rolls earned for each ball taken (working the count)

    # --- Strike roll (pitcher) ---
    command_sides: int = 6             # pitcher's die: 1 = always ball, max = always strike, else roll + bonus >= difference
    command_bonus: int = 0             # flat add to the pitcher's roll (control)
    suit_bonus_min: int = 2            # same-suit cards in zone needed before the multiples bonus applies
    suit_bonus_per_card: int = 1       # bonus per same-suit card (3 spades = +3)
    bonus_applies: str = "both"        # multiples bonus adds to: both | pitcher (strike roll) | batter (difficulty)

    # --- Contact (batter) ---
    one_whiffs: bool = True            # contact dice roll one at a time: a 1 = swing and miss
    six_hits: bool = True              # a 6 (top face) = ball in play
    difficulty_floor: int = 0
    tie_rule: str = "foul"             # contact sum == difficulty: foul | play

    # --- Pitcher AI ---
    pitcher_keep: int = 3              # cards held back (incl. the pitch card) when building the zone
    pitcher_temp: float = 1.5          # softmax temperature over strike targets (higher = less predictable)
    zone_bias: float = 0.0             # added to count-based strike intent
    command_weight: float = 8.0        # how much the pitcher values strike chance vs difficulty
    grid_noise: float = 0.15           # chance the zone is built from shuffled cards instead of high cards

    # --- Batter AI ---
    batter_eye: float = 0.0            # chance the batter reads the pitch's row before betting (0 = rules as written)
    batter_temp: float = 0.0           # noise on take vs swing (0 = pure EV; ~0.03 = human-ish)
    belief_samples: int = 24           # Monte Carlo samples of the pitcher's hidden hand
    counts_cards: bool = True          # batter uses the discard rows to narrow the hidden hand
    count_values: dict = None          # {"b-s": wOBA}; None = built-in MLB-ish table


LEVERS = [
    # key, group, label, hint
    ("grid_size", "Table", "Grid size", "2 = 2x2, 3 = 3x3"),
    ("deck_mix", "Table", "Deck mix", "cards per suit ♠,♦,♣ (max 13)"),
    ("removed_cards", "Table", "Removed cards", "click cards below to remove them"),
    ("hand_size", "Pitcher cards", "Starting hand", "cards per at-bat"),
    ("draw_per_pitch", "Pitcher cards", "Draw per pitch", "cards"),
    ("max_hand", "Pitcher cards", "Hand cap", "0 = none"),
    ("max_grid", "Pitcher cards", "Max zone cards", "1-9"),
    ("face_value", "Pitcher cards", "Face card value", "J/Q/K"),
    ("batter_dice", "Batter dice", "Batter dice", "pool size"),
    ("die_sides", "Batter dice", "Die sides", "d6, d8, ..."),
    ("card_cost", "Batter dice", "Cost per extra card", "dice"),
    ("mix_penalty", "Batter dice", "Mix penalty", "extra dice for 1,2,3 types"),
    ("power_rule", "Batter dice", "Power dice", "reserve | all_but_contact"),
    ("power_keep", "Batter dice", "Power keeps best", "k dice (0 = all)"),
    ("power_thresholds", "Batter dice", "Power thresholds", "1B,2B,3B,HR min sums"),
    ("power_bonus", "Batter dice", "Power bonus", "flat"),
    ("spread_power", "Batter dice", "Power lost per extra card", "pips off power sum"),
    ("power_system", "Power hand", "Power system", "sum | hand | climb"),
    ("climb_ladder", "Power hand", "Climb lengths", "1B,2B,HR streaks"),
    ("hand_dice", "Power hand", "Hand dice", "most power dice rolled (hand and climb)"),
    ("hand_map", "Power hand", "Hand outcomes", "hand=1B/2B/3B/HR/FOUL; rest are outs"),
    ("rerolls", "Power hand", "Re-rolls per at-bat", "one die each"),
    ("reroll_card_cost", "Power hand", "Re-rolls per extra card", ""),
    ("reroll_mix_penalty", "Power hand", "Re-roll mix penalty", "for 1,2,3 types"),
    ("reroll_per_ball", "Power hand", "Re-rolls per ball taken", ""),
    ("command_sides", "Strike roll", "Pitcher die sides", "d6"),
    ("command_bonus", "Strike roll", "Pitcher roll bonus", "+n"),
    ("suit_bonus_min", "Strike roll", "Multiples bonus starts at", "cards"),
    ("suit_bonus_per_card", "Strike roll", "Multiples bonus per card", "+n"),
    ("bonus_applies", "Strike roll", "Multiples bonus applies to", "both | pitcher | batter"),
    ("one_whiffs", "Contact", "Rolling a 1 = swing and miss", "true | false"),
    ("six_hits", "Contact", "Rolling a 6 = hit", "true | false"),
    ("difficulty_floor", "Contact", "Difficulty floor", ""),
    ("tie_rule", "Contact", "Tie goes to", "foul | play"),
    ("pitcher_keep", "Pitcher AI", "Cards held back", ""),
    ("pitcher_temp", "Pitcher AI", "Unpredictability", "temperature"),
    ("zone_bias", "Pitcher AI", "Zone bias", "+/- strike intent"),
    ("command_weight", "Pitcher AI", "Strike-chance weight", "vs difficulty"),
    ("grid_noise", "Pitcher AI", "Zone noise", "0-1"),
    ("batter_eye", "Batter AI", "Eye (row read chance)", "0-1, 0 = rules as written"),
    ("batter_temp", "Batter AI", "Take/swing noise", "0 = pure EV"),
    ("belief_samples", "Batter AI", "Scouting samples", ""),
    ("counts_cards", "Batter AI", "Counts cards", "true | false"),
]


def _coerce(current, raw):
    if isinstance(raw, str):
        s = raw.strip()
        if isinstance(current, bool):
            if s.lower() in ("true", "1", "yes"):
                return True
            if s.lower() in ("false", "0", "no"):
                return False
            raise ValueError(f"expected true/false, got {raw!r}")
        if isinstance(current, int):
            return int(s)
        if isinstance(current, float):
            return float(s)
        if isinstance(current, tuple):
            return tuple(int(x) for x in s.split(","))
        if current is None or isinstance(current, dict):
            return json.loads(s) if s and s.lower() != "none" else None
        return s
    if isinstance(current, tuple):
        return tuple(raw)
    if isinstance(current, float):
        return float(raw)
    return raw


def apply_overrides(cfg, overrides):
    """Return a new Config with overrides applied. Unknown keys fail fast."""
    names = {f.name for f in fields(Config)}
    data = asdict(cfg)
    for k, v in overrides.items():
        if k not in names:
            raise KeyError(f"unknown lever: {k}")
        data[k] = _coerce(data[k], v)
    out = Config(**data)
    validate(out)
    return out


def validate(cfg):
    if len(cfg.power_thresholds) != 4 or list(cfg.power_thresholds) != sorted(cfg.power_thresholds):
        raise ValueError("power_thresholds must be 4 non-decreasing ints (1B,2B,3B,HR)")
    if len(cfg.mix_penalty) != 3:
        raise ValueError("mix_penalty must be 3 ints")
    if cfg.power_system not in ("sum", "hand", "climb"):
        raise ValueError("power_system must be sum, hand or climb")
    if len(cfg.climb_ladder) != 3 or list(cfg.climb_ladder) != sorted(set(cfg.climb_ladder)) or cfg.climb_ladder[0] < 1:
        raise ValueError("climb_ladder must be 3 increasing lengths (1B,2B,HR)")
    if len(cfg.reroll_mix_penalty) != 3:
        raise ValueError("reroll_mix_penalty must be 3 ints")
    from cardball.hand import parse_map
    parse_map(cfg.hand_map)
    if cfg.power_rule not in ("reserve", "all_but_contact"):
        raise ValueError("power_rule must be reserve or all_but_contact")
    if cfg.tie_rule not in ("foul", "play"):
        raise ValueError("tie_rule must be foul or play")
    if not 1 <= cfg.max_grid <= 9:
        raise ValueError("max_grid must be 1-9")
    if cfg.grid_size not in (2, 3):
        raise ValueError("grid_size must be 2 or 3")
    if len(cfg.deck_mix) != 3 or not all(0 <= n <= 13 for n in cfg.deck_mix) or sum(cfg.deck_mix) < 2:
        raise ValueError("deck_mix must be 3 counts of 0-13 (spades, diamonds, clubs)")
    from cardball.cards import DECK, deck, removed
    bad = removed(cfg) - set(DECK)
    if bad:
        raise ValueError(f"removed_cards: unknown cards {sorted(bad)} (use rank+suit like 2S, TD, KC)")
    if len(deck(cfg)) < 2:
        raise ValueError("the deck needs at least 2 cards")
    if cfg.bonus_applies not in ("both", "pitcher", "batter"):
        raise ValueError("bonus_applies must be both, pitcher or batter")
    if cfg.command_sides < 2:
        raise ValueError("command_sides must be at least 2")


def to_dict(cfg):
    d = asdict(cfg)
    for k, v in d.items():
        if isinstance(v, tuple):
            d[k] = list(v)
    return d


def load(path=None, overrides=None):
    cfg = Config()
    if path:
        with open(path) as f:
            cfg = apply_overrides(cfg, json.load(f))
    if overrides:
        cfg = apply_overrides(cfg, overrides)
    return cfg
