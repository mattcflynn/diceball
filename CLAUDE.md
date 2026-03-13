# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Game

```bash
uv run main.py
```

No tests or linter are configured yet.

## Architecture

Diceball Duel is a CLI dice baseball simulation. One at-bat is the unit of play: a pitcher rolls dice to form a pitch combo, and a hitter rolls to make contact and determine the hit outcome.

**Entry point:** `main.py` — collects top-level settings (human vs. CPU pitcher, pitcher dice count) and loops over at-bats via `game/engine.py:play_at_bat`.

**`game/engine.py`** — The entire at-bat state machine. Handles:
- Dice rolling and ASCII display
- Hitter's post-dice commit (pitch type + swing type), or take (no swing)
- Pitcher re-roll decisions (human or AI), gas budget management
- Simultaneous reveal of pitcher commit + hitter swing/no-swing
- Contact and power roll resolution
- Ball/strike count and at-bat termination

**`game/pitch_utils.py`** — Pitch type definitions and combo logic:
- `FB` (Fastball): 3-of-a-kind
- `CB` (Curveball): 3-die sequential run, no 6s
- `CU` (Changeup): 3 different dice, all odd or all even
- Pitch difficulty = `max()` of the 3 matching dice
- `find_pitch_outcome` auto-selects the highest-difficulty valid combo from the pitcher's pool

**`game/ai.py`** — AI pitcher brain. `make_pitcher_decision` analyzes the dice hand for complete pitches and "near misses" (2-of-3), then decides which dice to re-roll and which pitch to commit to, factoring in ball/strike count aggressiveness and streak bonuses. AI hitter (`make_hitter_decision`) uses BATS to evaluate all 6 combos (3 commit pitches × 2 swing types) and picks max EV.

**`game/bats.py`** — B.A.T.S. (Batting Analysis and Targeting System). Exhaustive combinatorial probability calculator. Given the pitcher's current dice and planned re-rolls, computes exact probabilities for each pitch type at each difficulty, then layers in contact probability (given hitter's swing type and commit bonus) and power outcome probabilities (HR/Triple/Double/Single). Called mid-at-bat when hitter chooses `[b]ats`.

**`game/player.py`** — Stub `Player`, `Pitcher`, `Hitter` classes (not yet integrated into engine).

**`game/abilities.py`** — Stub `Ability` class (not yet implemented).

## Key Game Mechanics

- **Pitcher dice pool:** 4 or 5 d6. Gas budget = `max(0, 6 - dice_pool)`: 5 dice → 1 gas, 4 dice → 2 gas. Gas is spent down over the at-bat (not refilled). 1 gas = re-roll 1 die.
- **Hitter commit mechanic:** After seeing the dice + re-roll plan, hitter commits to a pitch type (fb/cb/cu). Correct commit = +1 to all contact dice rolls. Wrong commit = −1. Or take (n) for no swing + bonus die.
- **Swing types:** Power (2c/4p) — full range including HR, TRIPLE, DOUBLE, SINGLE. Contact (4c/2p) — hard line drives, SINGLE + rare DOUBLE (max power roll = 12).
- **Power outcomes (power swing, 4 dice):** sum ≥20 HR, =19 TRIPLE, =18 DOUBLE, 16-17 SINGLE, 7-15 OUT, <7 WEAK\_OUT.
- **Power outcomes (contact swing, 2 dice):** sum =12 DOUBLE, 10-11 SINGLE, 6-9 OUT, <6 WEAK\_OUT.
- **Streak modifier:** 2+ consecutive same-category pitches → difficulty −1. Breaking a streak after 2+ → difficulty +1 per streak length (capped at +2).
- **Contact:** Need 2+ dice ≥ difficulty, OR 2+ natural 6s (critical hit, always makes contact).
- **Taking a pitch** (choosing `n`) works the count but provides no bonus die.
