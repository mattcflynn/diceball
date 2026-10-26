"""Deck, card values, and strike-zone cells.

Cards are 2-char strings: rank + suit, e.g. "KS", "TD", "AC" (T = 10).
Hearts are removed from the deck; hearts A-9 (A-4 on a 2x2 grid) are the location cards.
"""

SUITS = ("S", "D", "C")
RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K")
DECK = tuple(r + s for s in SUITS for r in RANKS)

PITCH_CODE = {"S": "FB", "D": "OS", "C": "BR"}
PITCH_NAME = {"S": "Fastball", "D": "Off-speed", "C": "Breaking ball"}
SUIT_SYMBOL = {"S": "♠", "D": "♦", "C": "♣", "H": "♥"}

# Cells read like a phone keypad: A 2 3 / 4 5 6 / 7 8 9 (2x2: A 2 / 3 4)
CELLS = tuple(range(1, 10))
CELL_LABEL = {i: ("A" if i == 1 else str(i)) for i in CELLS}


def cells(cfg):
    return tuple(range(1, cfg.grid_size ** 2 + 1))


def deck(cfg):
    """The pitcher's deck: the lowest `deck_mix[i]` ranks of each suit (trimmed from K down), minus `removed_cards`."""
    gone = removed(cfg)
    return tuple(r + s for s, n in zip(SUITS, cfg.deck_mix) for r in RANKS[:n] if r + s not in gone)


def removed(cfg):
    return {c.strip().upper() for c in cfg.removed_cards.split(",") if c.strip()}


def rank_num(card):
    return RANKS.index(card[0]) + 1


def value(card, face_value=10):
    n = rank_num(card)
    return face_value if n > 10 else n


def suit(card):
    return card[1]


def label(card):
    r = "10" if card[0] == "T" else card[0]
    return r + SUIT_SYMBOL[card[1]]
