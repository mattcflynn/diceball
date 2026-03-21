# Diceball Duel — User Manual

## What Is This?

Diceball Duel is a two-player dice baseball simulation. One at-bat is the unit of play. The pitcher rolls dice to form a pitch combo; the hitter rolls to make contact and determine the hit outcome. Either player can be human or CPU.

---

## Setup

```bash
uv run main.py
```

You'll be asked:
1. Human or CPU **pitcher**?
2. Human or CPU **hitter**?
3. Number of **pitcher dice** — `4` (less reliable) or `5` (more reliable)

---

## The Pitch Loop

Each pitch follows this sequence:

```
1. Pitcher rolls dice (shown publicly)
2. Pitcher decides on re-rolls (public, costs gas), commits to pitch type (secret)
3. Hitter sees the dice and re-roll plan, then commits to a pitch type and swing type (secret)
4. Reveal — everything resolves simultaneously
```

---

## Pitcher Mechanics

### Dice Pool

The pitcher rolls 4 or 5 d6. Any three dice can form a pitch. The remaining dice are ignored.

### Pitch Types

| Name | Code | Requirement | Example |
|------|------|-------------|---------|
| Fastball | FB | Three-of-a-kind | `[4, 4, 4]` |
| Curveball | CB | Three consecutive values, no 6s | `[3, 4, 5]` |
| Changeup | CU | Three *different* values, all odd or all even | `[2, 4, 6]` or `[1, 3, 5]` |

### Pitch Difficulty

Difficulty = the **highest die** in the valid combo. A CB using `[3, 4, 5]` has difficulty 5. Higher difficulty is harder to hit.

### Failed Pitch = Ball

If the committed pitch type can't be formed from the final dice, the pitch is a **ball**.

### Gas Tokens 🔥

- Pitcher starts each at-bat with **gas based on dice count**: 5 dice → 1 gas, 4 dice → 2 gas.
- Gas is **spent down** over the at-bat — it's not refilled. The pitcher weakens over a long at-bat.
- Gas is spent to **re-roll dice**: 1 gas per die re-rolled.
- Re-roll intent is **public** — the hitter sees which dice are being replaced.
- Re-rolls happen before the pitch is thrown; the new dice are shown to both players.

> First pitch: pitcher uses whatever gas they have. A 5-dice pitcher has 1 gas; a 4-dice pitcher has 2.

---

## Hitter Mechanics

### Post-Dice Commit

After seeing the pitcher's dice and re-roll plan, the hitter **commits to a pitch type** they're swinging at:

- **Correct commit** (`fb`, `cb`, or `cu` matches the pitcher's actual pitch): **+1 to every contact die roll**
- **Wrong commit**: **−1 to every contact die roll**
- **Take** (`n`): Don't swing. No bonus — just working the count.

You can also press `b` to run **B.A.T.S.** before deciding (see below).

### Swing Type

You choose your swing type when you commit:

| Type | Key | Contact Dice | Power Dice | Best for |
|------|-----|-------------|------------|---------|
| **Power** | `p` | 2 | 4 | Going for extra-base hits; lower contact rate but HR/TRIPLE possible |
| **Contact** | `c` | 4 | 2 | Putting the ball in play; higher contact rate, hard line drives |

---

## Contact Roll

Roll your contact dice. You make contact if **2 or more dice meet or exceed the pitch difficulty**.

- Commit bonus/penalty applies: add the modifier to every die before comparing.
- **Critical Hit:** Two or more natural 6s always make contact, regardless of difficulty.

---

## Power Roll (on contact)

Sum all power dice. The result depends on swing type:

### Power swing (4 power dice)

| Sum | Result |
|-----|--------|
| ≥ 20 | **Home Run** |
| = 19 | **Triple** |
| = 18 | **Double** |
| 16–17 | **Single** |
| 7–15 | **Out** |
| < 7 | **Weak Out** |

### Contact swing (2 power dice)

| Sum | Result |
|-----|--------|
| = 12 | **Double** (max roll — a laser line drive) |
| 10–11 | **Single** |
| 6–9 | **Out** |
| < 6 | **Weak Out** |

*No HRs or triples are possible with a contact swing — it's all about putting the ball in play.*

---

## Streak Modifier

The pitcher's last two (or more) pitches of the same **category** (FB vs. off-speed) create a streak.

| Situation | Effect |
|-----------|--------|
| 2+ same-category pitches in a row | Next same-category pitch: difficulty **−1** (getting predictable) |
| Break a streak of 2+ | Next pitch: difficulty **+1 per streak length** (capped at +2) |

> Example: Three FBs in a row, then a CU → the CU gets +2 difficulty (setup bonus). But a fourth FB would get −1 (predictable).

---

## B.A.T.S. (Batting Analysis & Targeting System)

When it's your turn to commit, press `b` to run **B.A.T.S.** It shows the probability of each pitch type at each difficulty level, and your contact probability against each — given the current dice, re-rolls, streak, and your committed pitch.

```
Pitch-Diff   |  Pitch %  |  Contact %
-----------  |  -------  |  ---------
FB-4         |    22.3%  |    68.1%
CB-3         |    14.7%  |    71.4%
...
```

Power probabilities (HR/Triple/2B/1B) are also shown if contact is made. B.A.T.S. doesn't consume your turn.

---

## Count & At-Bat Ending

- **3 strikes** → Strikeout. Swinging (K_S) or looking (K_L).
- **4 balls** → Walk (BB).
- **Contact** → Single, Double, Triple, HR, Out, or Weak Out ends the at-bat immediately.
- Foul balls add a strike only if the count is below 2 strikes.

---

## 4 vs. 5 Pitcher Dice

| | 4 dice | 5 dice |
|--|--------|--------|
| Walk rate | ~10% | ~6% |
| Batting average | ~.232 | ~.251 |
| Gas budget | 2 | 1 |
| Variance | High — pitches are less predictable | Lower — pitcher is more controlled |

A 4-dice pitcher throws more balls (harder to form valid combos) and has 2 gas to compensate — but still walks more batters. A 5-dice pitcher is more controlled with 1 gas.

---

## Simulator

```bash
uv run simulator.py
```

Runs CPU vs. CPU at-bats in bulk and compares results to 2024 MLB league averages. Levers are split into two groups:

**Pitcher levers** — control how dominant or deceptive the pitcher is:

| # | Lever | Default | Description |
|---|-------|---------|-------------|
| 1 | Pitcher dice pool | 4 | 4 or 5 d6 |
| 2 | Gas per at-bat | auto | Re-rolls available; auto = `max(0, 6 − dice)` |
| 3 | FB match count | 3 | 3 = three-of-a-kind, 2 = pair |
| 4 | CB run length | 3 | 3 = full 3-die run, 2 = any 2 consecutive |
| 5 | CB allow 6 in run | False | Allow 6 as part of a curveball run |
| 6 | CU diff count | 3 | 3 = three different same-parity, 2 = any two |
| 7 | Pitch difficulty | max | `max` = high die, `mid` = middle die, `min` = low die |
| 8 | Hidden re-roll | False | Hitter decides before seeing pitcher's re-roll plan |

**Hitter levers** — control how good the batter is:

| # | Lever | Default | Description |
|---|-------|---------|-------------|
| 9 | Correct commit bonus | +1 | Contact die bonus for guessing right |
| 10 | Wrong commit penalty | −1 | Contact die penalty for guessing wrong |
| 11 | Hitter power bonus | +0 | Flat bonus added to every power roll result |

**Hidden re-roll** (`True`) changes the information structure of the game: the hitter commits based only on the pre-reroll dice, not knowing which dice the pitcher intends to replace. This increases K% and K Looking by creating genuine uncertainty.

**Hitter power bonus** shifts all power roll outcomes — a +2 bonus effectively lowers the HR threshold from ≥20 to ≥18, modeling a true power hitter.

With default settings (4 dice, hidden re-roll off), simulated stats land close to 2024 MLB averages on BB%, SLG, OPS, and HR/PA. Enabling hidden re-roll brings K% to target at the cost of a slight BB% increase.

### Player profiling

The simulator can work in reverse — enter a target slash line and it searches for the best lever configuration:

- **`[h]` Hitter search** — keeps the current pitcher config fixed, searches hitter levers (commit bonus/penalty, power bonus) to match a batter's slash line. Use this to model a specific hitter against a league-average pitcher.
- **`[p]` Pitcher search** — keeps the current hitter config fixed, searches pitcher levers (dice pool, difficulty, pitch requirements, hidden re-roll) to match a pitcher's slash line against that hitter.

After each search, the best config is loaded and a 2,000-sim verification run is shown automatically. Results include **wOBA**, **wRC+**, and **oWAR** (projected to 600 PA) so you can compare directly to real player values.

Example workflow — modeling Trout vs. Cole:
```
[h] BA .301 / OBP .397 / SLG .566  →  finds hitter levers for Trout
[p] BA .200 / OBP .270 / SLG .320  →  finds pitcher levers for Cole against that hitter
[r] 5000                             →  full sim of that matchup
```

---

## Quick Reference Card

```
PITCH TYPES
  FB  Three-of-a-kind          [3,3,3]
  CB  Three consecutive, no 6  [2,3,4]
  CU  Three diff, all odd/even [1,3,5] or [2,4,6]

CONTACT  2+ dice ≥ difficulty  (or two natural 6s)

POWER SWING (4p)        CONTACT SWING (2p)
  ≥20 HR                  =12 Double (max roll)
  =19 Triple              10-11 Single
  =18 Double              6-9 Out
  16-17 Single            <6 Weak Out
  7-15 Out
  <7  Weak Out

SWING TYPES      Contact  Power
  Power (p)         2       4    ← HRs/Triples possible
  Contact (c)       4       2    ← Hard line drives

COMMIT (after seeing dice)
  Right pitch  +1 to every contact die
  Wrong pitch  -1 to every contact die
  Take (n)     No swing. Working the count.

GAS 🔥  5 dice → 1 gas, 4 dice → 2 gas. Spent down, not refilled.
       1 gas = re-roll 1 die (public).
```

---

## Fork Ideas

The game is designed to be hackable. The current stable state is tagged:

```bash
git checkout v5   # simulator, count-aware AI, hidden re-roll mechanic
```

Here are directions worth exploring:

### Information asymmetry
The **hidden re-roll** lever (simulator option 10) is a proof of concept. A fuller version would hide the original dice roll from the hitter entirely until the pitch resolves — forcing a swing/take decision with incomplete information. This would make K Looking much more common and bring it in line with MLB rates (~7.5%).

### Multi-inning scoring
The current unit is a single at-bat. Adding baserunners, inning state, and a run-scoring model would let you simulate full games. The `game/player.py` and `game/abilities.py` stubs are placeholders for this direction.

### Player abilities
`game/abilities.py` has an `Ability` stub. Possible ability directions:
- **Pitcher:** "Power arm" (all FB difficulties +1), "Pinpoint" (no difficulty penalty on intentional bluffs), "Filthy curve" (CB threshold lowered)
- **Hitter:** "Good eye" (threshold for taking balls reduced), "Clutch" (contact bonus with 2 strikes), "Pull hitter" (power swing HR threshold lowered by 1)

### Pitch arsenal expansion
Add pitch types beyond FB/CB/CU. Ideas:
- **Slider (SL):** Two same-value dice + one lower adjacent value (e.g., `[4, 4, 3]`). Hybrid of FB and CB.
- **Splitter (FS):** Two dice summing to 7 (e.g., `[1,6]`, `[2,5]`, `[3,4]`) — the "falling" pitch. Difficulty = lower die.
- **Knuckleball (KN):** Any four different values. Low difficulty but hard to commit to.

### Difficulty tuning
The `difficulty_method` lever (`max` / `mid` / `min`) has a large effect on BA and BABIP. `mid` brings BABIP closer to the .300 MLB target while keeping pitch variety. Worth exploring as a per-pitch-type setting (e.g., FB uses `max`, CB uses `mid`).

### Lineup simulation
Run a full 9-batter lineup through multiple innings. Aggregate stats (BA, OBP, SLG) per lineup slot. Compare different pitcher configurations against a fixed lineup to find optimal pitcher builds.
