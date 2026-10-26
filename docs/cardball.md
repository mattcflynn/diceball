# Cardball: cards vs. dice

A rework of Diceball. The pitcher plays cards into a 3×3 strike zone; the batter bets dice on those cards. The code lives in `cardball/`, separate from the dice game in `game/`.

## Running it

```bash
uv run -m cardball.server                     # playtest UI at http://localhost:8765 (opens the browser)
uv run -m cardball.server --preset ''         # raw lever defaults, untuned
uv run -m cardball.sim run -n 2000            # AI vs AI stats vs the 2026 season
uv run -m cardball.sim run -n 2000 --config cardball/presets/v2_tuned.json --set grid_size=3 one_whiffs=false
uv run -m cardball.sim sweep card_cost 0 1 2 -n 1500 --config cardball/presets/v2_tuned.json
uv run -m cardball.sim tune -n 1500 --levers t1 t2 t3 t4 zone_bias --out cardball/presets/mine.json
```

`sweep` and `tune` take the lever name and values first, then `--set`/`--config`. `t1`–`t4` in `--levers` are the four power thresholds. The sim runs on all but one CPU core: about 2,000 at-bats per second.

### Playtest UI

- **Bat vs AI**: the AI pitcher sets the zone and a secret pitch. Click a zone card to add a die (shift-click or right-click to remove), then Swing or Take. **Scout overlay** shows the AI batter's read of each card; **AI suggest** fills in its bets.
- **Pitch vs AI**: click a hand card, then a cell, to place it (click a placed card to take it back). Click a card and then the *Pitch card* slot (or double-click the card), pick a ♥ location (only cells holding a zone card are allowed), and Throw. The preview shows the difference, your strike chance and what the batter needs before you commit. **AI suggest** fills in what the AI pitcher would do.
- **Watch AI vs AI**: step through, or press Auto. *Peek* shows the secret pitch before the swing.
- **Played cards** shows the whole deck as outlines; cards fill in once they've been seen (zone cards still on the table are ringed).
- **Levers** edits every rule and AI setting and loads presets. *Table* holds the grid size (2 = 2×2, the default; 3 = 3×3), *Deck mix* (cards per suit, trimmed from K down) and *Removed cards*: click cards in the deck grid to take specific ones out (click again to put back). **Simulate** runs N at-bats with the current levers and shows the same tables as the CLI.

## Rules as implemented (v2, October 26 2026)

Deck: spades, diamonds and clubs (13 each by default; `deck_mix` trims a suit from K down, and `removed_cards` takes out specific cards, e.g. `2S,7S,KD`). ♠ = fastball, ♦ = off-speed, ♣ = breaking ball. A = 1, 2–10 face value, J/Q/K = 10. Hearts are the location cards, one per cell, laid out like a phone keypad:

```
2x2 (default):  A 2      3x3:  A 2 3
                3 4            4 5 6
                               7 8 9
```

1. The pitcher draws 10 (`hand_size`) at the start of each at-bat.
2. **Pitch**: the pitcher plays cards face up into the zone (up to one per cell), then secretly sets aside one hand card as the **pitch card** plus a heart for the **location**. The location must be a cell holding a zone card. The pitch type is the suit of the targeted zone card.
3. **Swing or take**: the batter sees the zone, the pitcher's hand count and every card played so far. To swing, they bet dice on zone cards. Spreading costs dice: `card_cost` (1) per card beyond the first, plus `mix_penalty` for 2 or 3 pitch types (1 / 2). Two cards of different suits therefore cost 2 dice. No dice bet = take.
4. **Take → strike roll**: only if the batter takes. Difference = zone card value − pitch card value. The pitcher rolls 1d6 (`command_sides`): a 1 is always a ball, a 6 is always a strike, otherwise it's a strike when roll + multiples bonus ≥ difference. Multiples bonus = the number of zone cards sharing the target card's suit, once there are at least 2 (`suit_bonus_min`). By default it applies to both sides (`bonus_applies`): it helps the strike roll and also adds to the batter's difficulty.
5. **Swing → contact roll** (no strike roll, so a swing never knows if it was a ball): the batter rolls the dice bet on the located card **one at a time**, keeping a running total, up to as many dice as they bet. A 1 ends the swing as a swing and miss (`one_whiffs`). A 6 ends it as a hit, i.e. a ball in play (`six_hits`). Once the total beats difference + multiples bonus, the ball is in play. Running out of dice first = foul. No dice on the located card = swing and miss. More dice means more chances to get there, but also more chances to roll a 1 first.
6. **Power**: on a ball in play, roll the dice not bet (`power_rule=reserve`) and compare the sum (or the best `power_keep`) to `power_thresholds` (1B / 2B / 3B / HR).
7. After each pitch, all played cards go face up into rows by suit, and the pitcher draws 3 (`draw_per_pitch`). The batter gets all dice back.
8. After each at-bat, everything is reshuffled and the pitcher draws 10 again.

The tension: a big difference (high zone card, low pitch card) is hard to hit but hard to throw for a strike. Stacking same-suit cards in the zone buys control and makes the pitch harder to hit, but tells the batter what pitch type is coming.

### Choices made where the draft was open

Each of these is a lever, so the alternatives can be simulated.

| Question | Default | Lever |
|---|---|---|
| Which roll does the multiples bonus help? | Both: the strike roll and the batter's difficulty | `bonus_applies`: `both` / `pitcher` / `batter` |
| "1 = whiff, 6 = hit" with several dice? | Roll one at a time; the first 1 or 6 ends the swing (a 1 after the total already got there never happens, because rolling stops) | `one_whiffs`, `six_hits` |
| Does a swing trigger the strike roll? | No: the strike roll only happens on a take | — |
| Which dice roll for power? | Dice not bet ("reserve"). Dice lost to spreading are gone. | `power_rule`: `reserve` / `all_but_contact` |
| Contact sum equals difference? | Foul | `tie_rule`: `foul` / `play` |
| Pitch card worth more than the zone card? | Batter difficulty floors at 0; a take is a strike unless the roll is a 1 | `difficulty_floor` |
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

Presets, both on the default 2×2 grid with `card_cost=1`, `power_keep=4` and `batter_temp=0.03`:
- **`v2_tuned`** (the playtest default): the rules as written, so 1 = swing and miss and 6 = hit. Thresholds 20/22/24/24, `zone_bias=+0.05`.
- **`v2_no_ones`**: `one_whiffs=false`. Thresholds 21/22/24/24, `zone_bias=+0.1`.

| 8,000 PA | BA | OBP | SLG | K% | BB% | HR/PA | P/PA |
|---|---|---|---|---|---|---|---|
| 2026 MLB | .244 | .319 | .401 | 22.1% | 8.9% | ~2.9% | ~3.9 |
| `v2_tuned` | .285 | .319 | .448 | **40.0%** | 4.7% | 1.8% | 3.57 |
| `v2_no_ones` | .243 | .308 | .427 | 26.4% | 8.6% | 1.8% | 4.20 |
| `v2_tuned` on 3×3 (4,000 PA) | .314 | .343 | .488 | 34.5% | 4.2% | — | — |

1. **"1 = swing and miss" is the biggest strikeout lever.** With one-at-a-time contact, a 1 ends 16% of swings. Turning it off takes K from 40% to 26% and brings contact to 71% (MLB 76%). `v2_no_ones` is the closest fit so far.
2. **Wrong-card whiffs are now the main strikeout source** (29–35% of swings): dice on a card the pitch didn't target. A 2×2 zone after pitch one is usually 2 cards, and covering both costs a die (`card_cost`).
3. **The strike roll only happens on a take, so walks depend on swings not being too lucrative.** The batter takes when the strike roll looks likely to fail. If hitting is strong, swinging always wins and walks vanish (the raw lever defaults: .698 BA, 0% BB).
4. **Spread costs work as written.** `card_cost=1` plus `mix_penalty` 0/1/2: two cards of two suits cost 2 dice. The playtest shows the breakdown, e.g. "−2 dice (1 for 2 cards + 1 for 2 pitch types)".
5. **Power is still coarse.** Best-4 of d6 (4–24) is the finest scale that works so far. The singles threshold is knife-edge (20 → 21 drops BA from .286 to .170), and triples collapse into HR at 24. Ideas: more power dice kept, a d8 power die, or a separate triple roll.
6. **The zone is ~2 cards after the first pitches** (`draw − 1`). On 2×2 the first two pitches show 4 cards. The pitch mix is 33/33/33, because suit doesn't change the pitcher's odds. `deck_mix` and `removed_cards` are the levers for a fastball-heavy pitcher.

Zone%, Chase% and Z-Swing% are computed from each pitch's strike chance, since swings never roll it.

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
