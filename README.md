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
| Walk rate | ~13% | ~6% |
| Batting average | ~.240 | ~.251 |
| Gas budget | 2 | 1 |
| Variance | High — pitches are less predictable | Lower — pitcher is more controlled |

A 4-dice pitcher throws more balls (harder to form valid combos) and has 2 gas to compensate — but still walks more batters. A 5-dice pitcher is more controlled with 1 gas.

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
