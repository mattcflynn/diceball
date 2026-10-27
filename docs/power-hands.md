# Cardball power: from dice sums to dice hands

Research log for October 26–27 2026: how the batter's power roll should work, and how dice "hands" map to MLB hit rates. The rules themselves live in [cardball.md](cardball.md); this doc covers why the climb exists and what the numbers say.

## Stats used

**Counting terms**
- **PA** (plate appearance): one finished at-bat in this game: a walk, a strikeout or a ball in play. The game has no hit-by-pitch, sacrifices or errors.
- **AB** (at-bat): a PA that isn't a walk.
- **BIP** (ball in play): contact that isn't a foul. It ends the PA as an out or a hit.
- **H** (hits) = singles + doubles + triples + home runs. **TB** (total bases) = 1B + 2×2B + 3×3B + 4×HR.

**Batting lines**
- **BA** (batting average) = H / AB.
- **OBP** (on-base percentage) = (H + BB) / PA.
- **SLG** (slugging) = TB / AB. **OPS** = OBP + SLG.
- **K%**, **BB%**, **HR/PA**: strikeouts, walks and home runs per PA.
- **BABIP** (batting average on balls in play) = (H − HR) / (AB − K − HR). Measures how often contact that stays in the park falls for a hit.
- **P/PA**: pitches per plate appearance.

**Value**
- **wOBA** (weighted on-base average): each outcome gets a run value, then divide by PA. The game uses FanGraphs-style weights: BB 0.69, 1B 0.88, 2B 1.25, 3B 1.59, HR 2.04, outs and strikeouts 0. Unlike OBP or SLG, it credits each event by how many runs it's worth. MLB is about .315.
- **wOBA on contact**: the same weights averaged over balls in play only. It's the right yardstick for a power system, because power only matters once there's contact. MLB is about **.350**.
- **Count value**: the average wOBA of PAs that pass through a count (0-0 ≈ .318, 3-0 ≈ .500, 0-2 ≈ .210). The AI batter uses these to price a ball, strike or foul.
- **EV** (expected value): the probability-weighted average wOBA of a choice. The AI batter compares the EV of taking with the EV of its best dice split.

**Plate discipline** (shares of pitches)
- **Zone%**: pitches that would be strikes. Swings never take the strike roll, so the sim uses each pitch's strike chance instead of the roll.
- **Swing%**: pitches swung at. **Chase%** (O-Swing%): swings at pitches outside the zone. **Z-Swing%**: swings at pitches in the zone.
- **Contact%**: swings that make contact (foul or in play).

**Game-specific measures**
- **Cards per swing**: how many zone cards the batter bets on. 1.0 means it never hedges; around 1.5 or more means hedging is a live choice.
- **Re-rolls per PA**: re-rolls actually spent (on spreading or on power) per plate appearance.
- **Miss score** (the tuner's loss): the sum over BA, OBP, SLG, K%, BB% and HR/PA of ((game − MLB) / tolerance)², plus a quarter weight on P/PA. The tolerances are in `sim.py: TARGETS` (BA ±.012, K% ±2 points, and so on). Under 10 is a close fit, under 50 is in range, over 200 is broken.

**MLB targets.** 2026 AL+NL: BA .244, OBP .319, SLG .401, K 22.1%, BB 8.9%, HR ~2.9% of PA. Per ball in play, from the simulator's per-PA mix:

| Out | 1B | 2B | 3B | HR | Hit% | At least 2B | wOBA on contact |
|---|---|---|---|---|---|---|---|
| 68.8% | 20.3% | 6.2% | 0.5% | 4.2% | 31.2% | 10.9% | ~.350 |

## 1. The problem: sums are coarse and punish hedging

The v2 power roll sums the best 4 unbet dice against thresholds 20/22/24/24.

- **Thresholds are knife-edge.** Moving the singles threshold from 20 to 21 drops BA from about .300 to .190. There's no setting in between.
- **Spreading is never worth it.** Every die bet anywhere is a lost power die, worth about .13 wOBA on contact. The AI bet 2 dice on one card 76% of the time and spread to a second card only 19% of the time (1.19 cards per swing).

Sweeps of the v2 levers (3,000 PA each):

| Setup | Cards per swing | BA | OBP | SLG | K% | BB% | Miss |
|---|---|---|---|---|---|---|---|
| `v2_tuned` | 1.19 | .286 | .319 | .449 | 39.0% | 4.6% | 107 |
| Dice on wrong cards count as power | 1.60 | .309 | .340 | .463 | 28.9% | 4.5% | 72 |
| ...and no cost per extra card | 2.19 | .268 | .326 | .382 | 26.2% | 7.9% | 12.5 |
| Lose 1 power pip per extra card | 1.29 | .292 | .322 | .423 | 34.9% | 4.3% | 84 |
| Lose 3 power pips per extra card | 1.03 | .263 | .299 | .406 | 44.8% | 4.9% | 151 |

Free spreading fit MLB best but broke the core trade-off: a batter sitting on two or three quadrants should have less power. A pip penalty was the right idea on the wrong scale, since one pip is worth too much near the thresholds. The `spread_power` lever stays (default 0) for later.

## 2. Yahtzee hands

The idea: after contact, the batter makes a poker-style hand from the power dice. Re-rolls become the currency, and spreading costs re-rolls instead of dice.

Exact odds of hands rolled all at once (best hand present, d6):

| Hand | 3 dice | 4 dice | 5 dice | 6 dice |
|---|---|---|---|---|
| Pair | 44.4% | 72.2% | 90.7% | 98.5% |
| Pair of 6s | 7.4% | 13.2% | 19.6% | 26.3% |
| Two pair | – | 6.9% | 27.0% | 55.6% |
| Three of a kind | 2.8% | 9.7% | 21.3% | 36.7% |
| Straight of 3 | 11.1% | 27.8% | 44.8% | 59.4% |
| Straight of 4 | – | 5.6% | 15.4% | 27.0% |
| Straight of 5 | – | – | 3.1% | 9.3% |
| Full house | – | – | 3.9% | 17.0% |
| Four of a kind | – | 0.5% | 2.0% | 5.2% |
| Five of a kind | – | – | 0.1% | 0.4% |
| All different | 55.6% | 27.8% | 9.3% | 1.5% |
| All odd or all even | 25.0% | 12.5% | 6.2% | 3.1% |
| All 4 or higher | 12.5% | 6.2% | 3.1% | 1.6% |
| In roll order, never drops | 25.9% | 9.7% | 3.2% | 1.0% |
| In roll order, always climbs | 9.3% | 1.2% | 0.1% | – |

What we learned:
1. **Set hands get much easier with more dice.** With 8 dice a full house shows up 64% of the time, so the hand has to be capped at 5 dice (`hand_dice`).
2. **The suggested mapping gives too many hits.** Two pair turns up in 27% of 5-dice rolls, so it can't be a double (MLB: 6% of balls in play). A rarity-matched mapping works at 5 dice with no re-rolls: three of a kind = 1B, straight = 2B, four of a kind = 3B, full house = HR. That gives 76% outs, 15% 1B, 3% 2B, 2% 3B and 4% HR (.285 on contact).
3. **Re-rolls are far too strong.** Re-rolling any number of dice took home runs from 4% to 19% of balls in play. Even re-rolling one die adds .2–.3 wOBA on contact, because a hand is easy to chase: two pair plus one re-roll is a 1-in-3 full house.
4. **In full at-bats, each extra re-roll per at-bat added about .09 BA.** The AI never paid one to spread (1.04–1.17 cards per swing), and walks fell to 0–6%, because with re-rolls in hand swinging always beats taking. Best full-game miss score: 103.

The hand system is kept as `power_system=hand` (`hand_map`, `hand_dice`, `rerolls`) for comparison.

## 3. Hands that need more dice

The goal: certain hits need certain dice. A slap or contact swing can only produce a single, while a home run needs a full A swing. Set hands fail here because extra dice also make every hand easier. A hand built **in roll order** does the opposite: each extra die is another chance to fail.

**The climb.** After contact, roll the power dice one at a time. The streak continues while each die is at least as high as the last (3-3-5 is fine; 4-2 ends it). Streak length decides the hit:

| Streak | Hit |
|---|---|
| 3 dice | Single |
| 4 dice | Double, or a **triple** if every die rose (1-3-4-6, no ties) |
| 5 dice | Home run |
| shorter | Out |

Exact odds, with no re-rolls:

| Power dice | Out | 1B | 2B | 3B | HR | Hit% | wOBA on contact |
|---|---|---|---|---|---|---|---|
| 3 (slap) | 74.1% | 25.9% | – | – | – | 25.9% | .228 |
| 4 | 74.1% | 16.2% | 8.6% | 1.2% | – | 25.9% | .268 |
| 5 (A swing) | 74.1% | 16.2% | 5.6% | 0.9% | 3.2% | 25.9% | .293 |
| MLB | 68.8% | 20.3% | 6.2% | 0.5% | 4.2% | 31.2% | .350 |

Why it works:
- **The hit chance doesn't change with dice count. Only the kind of hit does.** Contact and power hitters have similar BABIPs; power shows up as extra-base hits. Three dice cap you at a single, four can reach a triple, and a home run needs all five.
- **The odds follow from counting.** A streak of k that never drops has C(k+5, 5) / 6^k chance: 25.9%, 9.7% and 3.2% for 3, 4 and 5 dice. That's almost exactly MLB's at-least-1B (31%), at-least-2B (11%) and HR (4%).
- **Every die is a moment.** A high early die is a trap: start with a 6 and every later die must be a 6.

With re-rolls (a re-roll re-rolls the die that broke the streak, as many times as you have re-rolls):

| Power dice | Re-rolls | Out | 1B | 2B | 3B | HR | wOBA on contact |
|---|---|---|---|---|---|---|---|
| 5 | 0 | 74.1% | 16.2% | 5.6% | 0.9% | 3.2% | .293 |
| 5 | 1 | 57.9% | 22.7% | 10.2% | 1.5% | 7.7% | .504 |
| 5 | 2 | 46.3% | 25.2% | 13.8% | 1.8% | 12.9% | .679 |

Each re-roll adds about 16 points of hit chance. That's still a big unit, but a fractional average (for example 0.3 re-rolls reaching each ball in play) would land on MLB.

Step-rule variants:

| Rule | Ladder | Hit% | HR | Verdict |
|---|---|---|---|---|
| Never drops (ties OK) | 3 / 4 / 5 | 25.9% | 3.2% | closest |
| Strictly climbs | 2 / 3 / 4 | 41.7% | 1.2% | too many singles, too few HR |
| May drop by 1 | 4 / 5 / 6 | 28.1% | 9.6% | too many HR, needs 6 dice |

## 4. The climb in full at-bats

Wired in as `power_system=climb`:
- **Ladder:** `climb_ladder` = 3,4,5 (1B / 2B / HR streak lengths). A 2B-length streak that strictly rises is a triple.
- **Dice:** `hand_dice` caps the dice counted at 5.
- **Re-rolls:** the batter starts each at-bat with `rerolls`. Spreading costs re-rolls, not dice: `reroll_card_cost` per extra card plus `reroll_mix_penalty` for 2 or 3 pitch types. In these runs the dice costs (`card_cost`, `mix_penalty`) are 0, so the dice trade-off is purely contact vs power.
- **Spending:** re-rolls left at contact are spent on dice that break the streak. A ball in play ends the at-bat, so they're never worth saving at that point.
- **AI:** the batter values contact with the exact climb odds for its power dice and the re-rolls left after any spread cost.

Full games, 3,000 PA each, 2×2 grid, `batter_temp=0.03`:

| Setup | Cards per swing | Contact dice | BA | OBP | SLG | K% | BB% | HR | P/PA | Miss |
|---|---|---|---|---|---|---|---|---|---|---|
| 6 dice, 1 re-roll | 1.12 | 2.06 | .208 | .295 | .296 | 43.6% | 11.0% | 0.3% | 3.78 | 177 |
| 7 dice, 0 re-rolls | 1.00 | 1.72 | .085 | .307 | .133 | 52.6% | 24.3% | 0.5% | 4.40 | 772 |
| 7 dice, 1 re-roll | 1.06 | 2.73 | .273 | .321 | .457 | 32.4% | 6.6% | 1.6% | 3.19 | 50.5 |
| 7 dice, 1 re-roll, pitcher holds 7 back | 1.08 | 2.65 | **.262** | **.333** | **.444** | 30.5% | **9.6%** | 1.5% | 3.25 | **32.9** |
| 7 dice, 1 re-roll, extra cards free | 1.32 | 2.77 | .294 | .332 | .463 | 29.0% | 5.5% | 1.1% | 3.29 | 57.7 |
| 7 dice, 2 re-rolls | 1.07 | 2.85 | .349 | .352 | .561 | 32.0% | 0.4% | 0.9% | 2.65 | 237 |
| 8 dice, 1 re-roll | 1.03 | 2.97 | .276 | .297 | .520 | 32.9% | 2.9% | 5.0% | 2.88 | 115 |
| 8 dice, 1 re-roll, "1 = swing and miss" off | 1.02 | 3.14 | .362 | .371 | .632 | 13.7% | 1.4% | 4.9% | 2.32 | 320 |
| MLB 2026 | | | .244 | .319 | .401 | 22.1% | 8.9% | 2.9% | 3.9 | |

The tuner, starting from 7 dice and 1 re-roll and adjusting the pitcher and strike levers, settled on `pitcher_keep=7` (row 4). It gave BB 10.0% but K 31.6% and HR 1.3% on a fresh 6,000-PA check.

Findings:
1. **The climb is the best power system so far.** 7 dice with 1 re-roll gets BA, OBP, SLG and BB% into range at once (miss 33, against 107 for `v2_tuned`) with no threshold hand-tuning.
2. **Re-rolls per at-bat are still a cliff.** At 0 the climb alone is worth only .29 on contact, so the AI takes nearly everything (BB 24–34%). At 2, swinging always wins and walks vanish. Only 1 works. The fix is probably a fractional average, such as a pool per game.
3. **Home runs are short.** A home run needs 5 power dice, so the batter must bet at most 2 contact dice from a 7-dice pool. The AI usually bets about 3, leaving 4 power dice, which caps it at a triple. With 8 dice, HR rises to 5% but walks fall to 3%.
4. **Spreading is still rare** (1.03–1.32 cards per swing). One re-roll per at-bat is the whole power budget, so no hedge is worth it. Wrong-card whiffs (39% of swings) and 1s (17%) drive the high K%.
5. **"1 = swing and miss" can't simply be turned off.** K drops to 14% but hitting runs away (.362 BA).

Next experiments: a re-roll pool per game or per inning (fractional re-rolls per PA), an AI that values saving re-rolls, and a softer 1s rule.

## Reproducing

- Climb odds: `cardball/hand.py: climb_probs` (exact) and `play_climb` (the in-game roll).
- Full games: `uv run -m cardball.sim run -n 6000 --config cardball/presets/climb_v1.json`. That's row 4 above, and on a fresh seed it gives .260/.330/.435, K 31.0%, BB 9.4%. To play it, pick the `climb_v1` preset in the playtest UI's Levers panel.
- Hand odds: `cardball/hand.py: hand_probs`. The one-off catalog and ladder scripts were scratch work; every table above can be rebuilt from these functions or by enumerating `itertools.product(range(1, 7), repeat=n)`.
