# Cardball: cards vs. dice

A rework of Diceball. The pitcher plays cards into a 3×3 strike zone; the batter bets dice on those cards. The code lives in `cardball/`, separate from the dice game in `game/`.

## Running it

```bash
uv run -m cardball.server                     # playtest UI at http://localhost:8765 (opens the browser)
uv run -m cardball.server --preset ''         # raw lever defaults, untuned
uv run -m cardball.sim run -n 2000            # AI vs AI stats vs the 2026 season
uv run -m cardball.sim run -n 2000 --config cardball/presets/v2_tuned.json --set grid_size=2 deck_mix=9,13,13
uv run -m cardball.sim sweep card_cost 0 1 2 -n 1500 --config cardball/presets/v2_tuned.json
uv run -m cardball.sim tune -n 1500 --levers t1 t2 t3 t4 zone_bias --out cardball/presets/mine.json
```

`sweep` and `tune` take the lever name and values first, then `--set`/`--config`. `t1`–`t4` in `--levers` are the four power thresholds. The sim runs on all but one CPU core: about 2,000 at-bats per second.

### Playtest UI

- **Bat vs AI**: the AI pitcher sets the zone and a secret pitch. Click a zone card to add a die (shift-click or right-click to remove), then Swing or Take. **Scout overlay** shows the AI batter's read of each card; **AI suggest** fills in its bets.
- **Pitch vs AI**: click a hand card, then a cell, to place it (click a placed card to take it back). Click a card and then the *Pitch card* slot (or double-click the card), pick a ♥ location (only cells holding a zone card are allowed), and Throw. The preview shows the difference, your strike chance and what the batter needs before you commit. **AI suggest** fills in what the AI pitcher would do.
- **Watch AI vs AI**: step through, or press Auto. *Peek* shows the secret pitch before the swing.
- **Played cards** shows the whole deck as outlines; cards fill in once they've been seen (zone cards still on the table are ringed).
- **Levers** edits every rule and AI setting and loads presets. *Table* holds the grid size (2 = 2×2, 3 = 3×3), *Deck mix* (cards per suit, trimmed from K down) and *Removed cards*: click cards in the deck grid to take specific ones out (click again to put back). **Simulate** runs N at-bats with the current levers and shows the same tables as the CLI.

## Rules as implemented (v2, October 26 2026)

Deck: spades, diamonds and clubs (13 each by default; `deck_mix` trims a suit from K down, and `removed_cards` takes out specific cards, e.g. `2S,7S,KD`). ♠ = fastball, ♦ = off-speed, ♣ = breaking ball. A = 1, 2–10 face value, J/Q/K = 10. Hearts are the location cards, one per cell, laid out like a phone keypad:

```
3x3:  A 2 3      2x2:  A 2
      4 5 6            3 4
      7 8 9
```

1. The pitcher draws 10 (`hand_size`) at the start of each at-bat.
2. **Pitch**: the pitcher plays cards face up into the zone (up to one per cell), then secretly sets aside one hand card as the **pitch card** plus a heart for the **location**. The location must be a cell holding a zone card. The pitch type is the suit of the targeted zone card.
3. **Swing or take**: the batter sees the zone, the pitcher's hand count and every card played so far. To swing, they bet dice on zone cards. Spreading costs dice: `card_cost` (1) per card beyond the first, plus `mix_penalty` for 2 or 3 pitch types (1 / 2). Two cards of different suits therefore cost 2 dice. No dice bet = take.
4. **Strike roll**: difference = zone card value − pitch card value. The pitcher rolls 1d6 (`command_sides`): a 1 is always a ball, a 6 is always a strike, otherwise it's a strike when roll + multiples bonus ≥ difference. Multiples bonus = the number of zone cards sharing the target card's suit, once there are at least 2 (`suit_bonus_min`). By default it applies to both sides (`bonus_applies`): it helps the strike roll and also adds to the batter's difficulty.
5. **Contact**: roll the dice bet on the located card. Any 1 = swing and miss (`batter_ones`). Otherwise, sum > difference + multiples bonus = in play; less = foul. No dice on the located card = swing and miss. A swing at a ball is contested (`chase_rule` default) or a swing and miss (`chase_rule=whiff`, what the tuned preset uses).
6. **Power**: on a ball in play, roll the dice not bet (`power_rule=reserve`) and compare the sum (or the best `power_keep`) to `power_thresholds` (1B / 2B / 3B / HR).
7. After each pitch, all played cards go face up into rows by suit, and the pitcher draws 3 (`draw_per_pitch`). The batter gets all dice back.
8. After each at-bat, everything is reshuffled and the pitcher draws 10 again.

The tension: a big difference (high zone card, low pitch card) is hard to hit but hard to throw for a strike. Stacking same-suit cards in the zone buys control and makes the pitch harder to hit, but tells the batter what pitch type is coming.

### Choices made where the draft was open

Each of these is a lever, so the alternatives can be simulated.

| Question | Default | Lever |
|---|---|---|
| Which roll does the multiples bonus help? | Both: the strike roll and the batter's difficulty | `bonus_applies`: `both` / `pitcher` / `batter` |
| "A 1 is always a swing and miss" with several dice? | Any die showing 1 | `batter_ones`: `any` / `all` / `off` |
| Swing at a ball? | Contested like a strike | `chase_rule`: `contest` / `whiff`, `chase_penalty` |
| Which dice roll for power? | Dice not bet ("reserve"). Dice lost to spreading are gone. | `power_rule`: `reserve` / `all_but_contact` |
| Contact sum equals difference? | Foul | `tie_rule`: `foul` / `play` |
| Pitch card worth more than the zone card? | Batter difficulty floors at 0; the strike roll only fails on a 1 | `difficulty_floor` |
| Fewer cards of a suit: which ones go? | Trimmed from K down (a 9-spade deck is A–9♠), or pick exact cards | `deck_mix`, `removed_cards` |
| Deck runs out mid-at-bat | Played rows shuffle back in | `reshuffle_when_empty` |

### Added levers (not in the draft, off by default)

- `power_keep`: power = the best *k* power dice instead of all of them.
- `batter_eye`: chance the batter reads the location's **row** before betting.
- `batter_temp`: noise on the AI's swing/take choice.
- `command_bonus`: flat add to the pitcher's strike roll.

## The AI

**Pitcher** (`ai.py: choose_zone_cards, location_options`): plays its highest cards into the zone, holding `pitcher_keep` low cards back as pitch cards. For every (zone card, pitch card value) pair it scores `batter difficulty + command_weight × intent(count) × P(strike)` and picks by softmax (`pitcher_temp`). `intent` comes from the `STRIKE_INTENT` count table plus `zone_bias`, so it chases difficulty when ahead and throws strikes when behind.

**Batter** (`ai.py: batter_beliefs, batter_decide`): samples the pitcher's hidden hand from the unseen cards. Because the pitcher plays its high cards, it samples mostly cards no higher than the lowest zone card. It then runs the pitcher's policy on each sample to get, for every cell, the chance it is targeted, the strike chance and the difficulty spread. An exact dynamic program over suit subsets × power dice kept × cards used × cells finds the dice allocation with the best expected wOBA, pricing in the spread cost and the 1s rule. It uses a table of MLB-like count values.

The batter knows the pitcher's policy, but the pitcher doesn't model the batter. That's a level-1 setup, not an equilibrium, so a strong human pitcher should beat the AI batter by exploiting it.

## Findings (v2)

Presets: `v2_tuned` (the playtest default) keeps "any 1 whiffs", and sets `card_cost=0`, `power_keep=3`, thresholds 15/17/18/18 and `chase_rule=whiff`. `v2_all_ones` only whiffs on all 1s and uses 9 batter dice.

The multiples bonus applying to both sides (October 26) moves `v2_tuned` from .258/.316/.451, 53% K, 7.8% BB to **.233/.308/.416, 56% K, 9.7% BB** (8,000 PA). The table below was measured before that change, with the bonus on the strike roll only (`bonus_applies=pitcher`).

| 8,000 PA (raw: 4,000) | BA | OBP | SLG | K% | BB% | HR/PA | P/PA |
|---|---|---|---|---|---|---|---|
| 2026 MLB | .244 | .319 | .401 | 22.1% | 8.9% | ~2.9% | ~3.9 |
| `v2_tuned` | .258 | .316 | .451 | **53.4%** | 7.8% | 4.0% | 3.70 |
| `v2_all_ones` | .252 | .317 | .421 | **50.2%** | 8.7% | 3.3% | 3.72 |
| `v2_tuned` + `card_cost=1` | .217 | .300 | .390 | 58.2% | 10.7% | 3.5% | 3.91 |
| `v2_tuned` + 2×2 grid | .274 | .328 | .468 | 52.6% | 7.5% | 3.9% | 3.61 |
| raw defaults | .682 | .682 | 2.267 | 31.4% | 0.0% | 46.3% | 2.44 |

1. **The strike roll brought walks back.** Under v1, ball vs strike was a hidden suit match the batter couldn't read, so walks were 0%. Now the batter can estimate the strike chance from the visible zone card values (bigger zone cards mean bigger differences and more balls). The AI takes more when that chance is low, and walks land at 8–9% with no "batter's eye".
2. **A swing at a ball has to be a whiff.** If it's contested, swinging always beats taking (98–100% swing rate) and walks vanish again.
3. **Strikeouts are the open problem (~50%).** Contact is ~30% of swings vs 76% in MLB. Whiffs per swing in `v2_tuned`: 37% chasing a ball, 25% dice on the wrong card, 9% rolling a 1. Chase% (48%) is still close to Z-Swing% (61%), because the batter commits before the strike roll. Ideas:
   - A swing at a ball fouls off instead of whiffing.
   - A whiff on the wrong card becomes a foul when the card is adjacent to the location.
   - The pitcher shows the strike roll before the batter commits (then the batter knows ball/strike, but not where).
4. **The tuner turns `card_cost` off.** At `card_cost=1`, K rises to 58%: covering both cards of a 2-card zone costs a die, so the AI guesses one card instead.
5. **"Any 1 whiffs" punishes stacking dice.** The chance of no 1s on n dice is (5/6)ⁿ: 83% with one die, 48% with four. The AI responds by betting few dice per card (~2.4 per swing) and keeping 7 for power. Under `all`, 1s barely matter (2% of swings).
6. **The zone is still 2 cards after the first pitch** (`draw − 1`), on either grid size. The 2×2 grid plays almost the same as 3×3 once the first pitch is gone.
7. **The pitch mix is still 33/33/33**, because the pitcher's choices don't depend on suit. `deck_mix` is the lever for a fastball-heavy pitcher (e.g. `13,9,9`).

### v1 history (suit-match strikes, October 25)

Under v1 the pitch was a strike when the pitch card's suit matched the zone card. With empty-cell locations allowed, the best fit was .275/.333/.432 with 39% K, and only because of an added "batter's eye" lever. Once the location had to hit a zone card, walks fell to 0%: the batter had no signal for a suit mismatch. That led to v2's strike roll.


## Files

| File | What |
|---|---|
| `cardball/cards.py` | deck, values, cells |
| `cardball/config.py` | every lever, parsing, presets |
| `cardball/rules.py` | difficulty, dice odds, power, single-pitch resolution |
| `cardball/game.py` | at-bat state machine (hand, deck, played rows, count) |
| `cardball/ai.py` | pitcher and batter AI |
| `cardball/sim.py` | simulator, sweeps, tuner, 2026 targets |
| `cardball/server.py` | playtest server (stdlib) |
| `cardball/web/` | playtest UI (vanilla JS, no build) |
| `cardball/presets/` | tuned lever sets |

2026 targets: AL+NL regular-season totals from StatMuse (BA .244, OBP .319, SLG .401, K 22.1%, BB 8.9%). HR/PA, BABIP, wOBA, P/PA and the plate-discipline and pitch-mix rows are recent-season approximations and are marked `~`.
