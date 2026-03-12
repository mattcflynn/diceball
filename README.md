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
1. Hitter chooses approach and swing type (secretly)
2. Pitcher rolls dice (shown publicly)
3. Hitter sees the dice and may adjust their sit
4. Pitcher decides on re-rolls (public), commits to pitch type (secret)
5. Hitter decides to swing or not (secret)
6. Reveal — everything resolves simultaneously
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

- Pitcher starts each at-bat with **0 gas**.
- After each pitch resolves, the pitcher earns **+1 gas** (max 2).
- Gas is spent to **re-roll dice**: 1 gas per die re-rolled.
- Re-roll intent is **public** — the hitter sees which dice are being replaced.
- Re-rolls happen before the pitch is thrown; the new dice are shown to both players.

> First pitch always has 0 gas — no re-rolls available. Gas builds up over the at-bat.

---

## Hitter Mechanics

### Approach (chosen before pitcher rolls)

| Choice | Key | Effect |
|--------|-----|--------|
| **Take** | `t` | Don't swing no matter what. Earn a +1 bonus die on your next swing. |
| **Sit** | `s` | Declare a pitch you're looking for. Bonus if right, penalty if wrong. |
| **Wait** | `w` | Neutral. Decide to swing or not after seeing the dice. |

### Sit Mechanic

When you **hard sit** on a pitch (`s`), you commit before the dice are rolled:

- **Correct sit:** +2 to every contact die roll
- **Wrong sit:** −1 to every contact die roll, −1 power die

After the pitcher rolls, you get one chance to **keep** your sit or **shift** it to a different pitch:
- Shifted sit (if correct): +1 to every contact die roll
- Shifted sit (if wrong): −1 contact, −1 power (same penalty)

### Swing Type (chosen alongside approach)

You choose between two swings — the tradeoff is contact reliability vs. power ceiling:

| Type | Key | Contact Dice | Power Dice | Best for |
|------|-----|-------------|------------|---------|
| **Power** | `p` | 2 | 4 | Going for extra-base hits; lower contact rate but HR possible |
| **Contact** | `c` | 4 | 2 | Putting the ball in play; higher contact rate but no HRs or doubles |

> Against a high-difficulty pitch (5 or 6), contact swing is often the right call — 4 contact dice vs. 2 makes a big difference. Against easier pitches in a hitter's count, power is the play.

### Bonus Die

Taking a pitch (approach `t`) awards a **+1 bonus die** on your next swing. You choose to add it to contact or power dice when you swing.

---

## Contact Roll

Roll your contact dice. You make contact if **2 or more dice meet or exceed the pitch difficulty**.

- Sit bonus/penalty applies: add the modifier to every die before comparing.
- **Critical Hit:** Two or more natural 6s always make contact, regardless of difficulty.

---

## Power Roll (on contact)

Sum all power dice. The result depends on swing type:

### Power swing (4 power dice)

| Sum | Result |
|-----|--------|
| ≥ 19 | **Home Run** |
| ≥ 16 | **Double** |
| ≥ 14 | **Single** |
| ≥ 7 | **Out** |
| < 7 | **Weak Out** |

### Contact swing (2 power dice)

| Sum | Result |
|-----|--------|
| ≥ 10 | **Single** |
| ≥ 6 | **Out** |
| < 6 | **Weak Out** |

*No HRs or doubles are possible with a contact swing — max sum of 2 dice is 12.*

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

When it's your turn to swing or not, press `b` to run **B.A.T.S.** It shows the probability of each pitch type at each difficulty level, and your contact probability against each — given the current dice, re-rolls, streak, and your approach/sit.

```
Pitch-Diff   |  Pitch %  |  Contact %
-----------  |  -------  |  ---------
FB-4         |    22.3%  |    68.1%
CB-3         |    14.7%  |    71.4%
...
```

Power probabilities (HR/2B/1B) are also shown if contact is made. B.A.T.S. doesn't consume your turn.

---

## Count & At-Bat Ending

- **3 strikes** → Strikeout. Swinging (K_S) or looking (K_L).
- **4 balls** → Walk (BB).
- **Contact** → Single, Double, HR, Out, or Weak Out ends the at-bat immediately.
- Foul balls add a strike only if the count is below 2 strikes.

---

## 4 vs. 5 Pitcher Dice

| | 4 dice | 5 dice |
|--|--------|--------|
| Walk rate | ~11% | ~8% |
| Strikeout rate | ~25% | ~22% |
| Batting average | ~.262 | ~.276 |
| Variance | High — pitches are less predictable | Lower — pitcher is more consistent |

A 4-dice pitcher throws more balls (harder to form valid combos), but is also less predictable. The hitter can't read the situation as cleanly, leading to more swing-and-misses on unexpectedly hard pitches. A 5-dice pitcher is more controlled: fewer walks, more reliable pitch formation.

---

## Quick Reference Card

```
PITCH TYPES
  FB  Three-of-a-kind          [3,3,3]
  CB  Three consecutive, no 6  [2,3,4]
  CU  Three diff, all odd/even [1,3,5] or [2,4,6]

CONTACT  2+ dice ≥ difficulty  (or two natural 6s)

POWER SWING (4p)        CONTACT SWING (2p)
  ≥19 HR                  ≥10 Single
  ≥16 Double              ≥6  Out
  ≥14 Single              <6  Weak Out
  ≥7  Out
  <7  Weak Out

SWING TYPES      Contact  Power
  Power (p)         2       4    ← HRs possible
  Contact (c)       4       2    ← No HRs, but hard to miss

SIT RESULT
  Hard sit correct  +2 contact bonus
  Hard sit wrong    -1 contact, -1 power die
  Shifted correct   +1 contact bonus
  Shifted wrong     -1 contact, -1 power die

GAS 🔥  Earns 1 per pitch (max 2). 1 gas = re-roll 1 die.
TAKE    No swing. Earn +1 bonus die on next swing.
```
