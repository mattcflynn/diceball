"""At-bat state machine: deck, hand, discards, count."""
from cardball.cards import deck, cells
from cardball.rules import resolve_pitch, WOBA


class AtBat:
    def __init__(self, cfg, rng):
        self.cfg, self.rng = cfg, rng
        self.deck = list(deck(cfg))
        rng.shuffle(self.deck)
        self.hand, self.discards = [], []
        self.balls = self.strikes = 0
        self.pitches = []          # resolved pitch records
        self.counts_seen = [(0, 0)]
        self.pending = None        # (grid, reveal, location) once the pitcher commits
        self.read_row = None       # row the batter read, when batter_eye fires
        self.result = None
        self.draw(cfg.hand_size)

    @property
    def over(self):
        return self.result is not None

    @property
    def count(self):
        return (self.balls, self.strikes)

    def draw(self, n):
        for _ in range(n):
            if self.cfg.max_hand and len(self.hand) >= self.cfg.max_hand:
                return
            if not self.deck:
                if not (self.cfg.reshuffle_when_empty and self.discards):
                    return
                self.deck, self.discards = self.discards, []
                self.rng.shuffle(self.deck)
            self.hand.append(self.deck.pop())

    def commit_pitch(self, grid, reveal, location):
        if self.over or self.pending:
            raise RuntimeError("cannot commit a pitch now")
        grid = {int(c): card for c, card in grid.items()}
        cards = list(grid.values()) + ([reveal] if reveal else [])
        if len(set(cards)) != len(cards) or any(c not in self.hand for c in cards):
            raise ValueError("pitch uses cards not in hand")
        if len(grid) > self.cfg.max_grid or any(c not in cells(self.cfg) for c in grid):
            raise ValueError("bad zone layout")
        if self.hand and not reveal:
            raise ValueError("pitch card required")
        if reveal and location not in grid:
            raise ValueError("location must be a cell with a zone card")
        for c in cards:
            self.hand.remove(c)
        self.pending = (grid, reveal, location if reveal else None)
        self.read_row = None
        if reveal and self.cfg.batter_eye > 0 and self.rng.random() < self.cfg.batter_eye:
            self.read_row = row_of(location, self.cfg)

    def public(self):
        """What the batter can see."""
        grid = self.pending[0] if self.pending else {}
        return {
            "count": self.count,
            "grid": dict(grid),
            "hand_count": len(self.hand),
            "has_reveal": bool(self.pending and self.pending[1]),
            "discards": list(self.discards),
            "deck_count": len(self.deck),
            "pitch_no": len(self.pitches) + 1,
            "read_row": self.read_row if self.pending else None,
        }

    def resolve(self, bets):
        if not self.pending:
            raise RuntimeError("no pitch committed")
        grid, reveal, location = self.pending
        rec = resolve_pitch(grid, reveal, location, {int(c): n for c, n in bets.items()}, self.cfg, self.rng)
        rec["grid"] = dict(grid)
        rec["count_before"] = self.count
        rec["hand_after_play"] = len(self.hand)
        rec["read_row"] = self.read_row
        ev = rec["event"]
        if ev == "ball":
            self.balls += 1
        elif ev in ("called_strike", "whiff"):
            self.strikes += 1
        elif ev == "foul" and self.strikes < 2:
            self.strikes += 1
        elif ev == "in_play":
            self.result = rec["outcome"]

        if not self.result:
            if self.balls >= 4:
                self.result = "BB"
            elif self.strikes >= 3:
                self.result = "K_L" if ev == "called_strike" else "K_S"

        self.discards.extend(list(grid.values()) + ([reveal] if reveal else []))
        self.pending = None
        if not self.over:
            self.draw(self.cfg.draw_per_pitch)
            self.counts_seen.append(self.count)
        rec["count_after"] = self.count
        rec["result"] = self.result
        self.pitches.append(rec)
        return rec


def row_of(cell, cfg):
    return (cell - 1) // cfg.grid_size


def woba_of(result):
    if result in ("K_S", "K_L"):
        return 0.0
    return WOBA[result]
