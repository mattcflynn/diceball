// Cardball playtest client. All rules and AI live in Python; this file renders state and sends moves.

const SUIT_SYM = { S: "♠", D: "♦", C: "♣", H: "♥" };
const PTYPE = { S: "FB", D: "OS", C: "BR" };
const PNAME = { S: "Fastball", D: "Off-speed", C: "Breaking" };
const CELL_LABEL = c => (Number(c) === 1 ? "A" : String(c));
const rowName = r => (S.cfg.grid_size === 2 ? ["top", "bottom"] : ["top", "middle", "bottom"])[r];
const nCells = () => S.cfg.grid_size ** 2;
const maxZone = () => Math.min(S.cfg.max_grid, nCells());
const RANKS = "A23456789TJQK";

let S = null;                 // server state
let leverMeta = null;
let overrides = {};           // lever overrides vs defaults
let preset = "";
let bets = {};                // batter draft
let draft = { grid: {}, reveal: null, location: null, selected: null }; // pitcher draft
let autoTimer = null;

const $ = id => document.getElementById(id);
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; return e; };

async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opts);
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}

function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add("hidden"), 2600);
}

async function act(path, body) {
  try {
    S = await api(path, body);
    render();
  } catch (e) { toast(e.message); stopAuto(); }
}

// ---------------------------------------------------------------- helpers

function cardValue(code) {
  const n = RANKS.indexOf(code[0]) + 1;
  return n > 10 ? S.cfg.face_value : n;
}
const suitOf = code => code[1];
const rankLabel = code => (code[0] === "T" ? "10" : code[0]);
const fmt3 = x => x.toFixed(3).replace(/^0/, "");
const pct = (x, d = 1) => (100 * x).toFixed(d) + "%";

function cardEl(code, size = "", extra = "") {
  const s = suitOf(code);
  const c = el("div", `card ${s} ${size} ${extra}`);
  c.innerHTML = `<div class="rank">${rankLabel(code)}</div><div class="pip">${SUIT_SYM[s]}</div>` +
    (PTYPE[s] ? `<div class="ptype">${PTYPE[s]}</div>` : "");
  c.title = `${rankLabel(code)}${SUIT_SYM[s]} · ${PNAME[s] || ""} · value ${cardValue(code)}`;
  return c;
}
function heartEl(cell, size = "med") {
  const c = el("div", `card H ${size}`);
  c.innerHTML = `<div class="rank">${CELL_LABEL(cell)}</div><div class="pip">♥</div>`;
  c.title = `Location ${CELL_LABEL(cell)}`;
  return c;
}
function backEl(size = "med") { return el("div", `card back ${size}`); }

const PIPS = { 1: [4], 2: [0, 8], 3: [0, 4, 8], 4: [0, 2, 6, 8], 5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8] };
function dieEl(v, cls = "") {
  if (v === null || v === undefined || v > 6) {
    const d = el("div", `die num ${cls}`, v ?? "");
    return d;
  }
  const d = el("div", `die ${cls}`);
  for (let i = 0; i < 9; i++) d.appendChild(PIPS[v].includes(i) ? el("span", "p") : el("span"));
  return d;
}

function suitsBet(b, grid) {
  return new Set(Object.entries(b).filter(([, n]) => n > 0).map(([c]) => suitOf(grid[c])));
}
function penaltyParts(b, grid) {
  const cards = Object.values(b).filter(n => n > 0).length;
  if (!cards) return { cards: 0, mix: 0, total: 0, nCards: 0, nTypes: 0 };
  const nTypes = suitsBet(b, grid).size;
  const c = S.cfg.card_cost * (cards - 1), m = S.cfg.mix_penalty[nTypes - 1];
  return { cards: c, mix: m, total: c + m, nCards: cards, nTypes };
}
function penaltyFor(b, grid) { return penaltyParts(b, grid).total; }
function penaltyText(b, grid) {
  const p = penaltyParts(b, grid);
  const bits = [];
  if (p.cards) bits.push(`${p.cards} for ${p.nCards} cards`);
  if (p.mix) bits.push(`${p.mix} for ${p.nTypes} pitch types`);
  const pw = S.cfg.spread_power * Math.max(0, p.nCards - 1);
  if (!p.total) return pw ? `−${pw} power for ${p.nCards} cards` : "";
  return `−${p.total} dice (${bits.join(" + ")})` + (pw ? `, −${pw} power` : "");
}
function rerollCost(b, grid) {
  if (S.cfg.power_system === "sum") return 0;
  const cards = Object.values(b).filter(n => n > 0).length;
  if (!cards) return 0;
  return S.cfg.reroll_card_cost * (cards - 1) + S.cfg.reroll_mix_penalty[suitsBet(b, grid).size - 1];
}
function betTotal(b) { return Object.values(b).reduce((a, n) => a + n, 0); }

function suitBonus(zoneCards, s) {
  const n = zoneCards.filter(c => suitOf(c) === s).length;
  return n >= S.cfg.suit_bonus_min ? n * S.cfg.suit_bonus_per_card : 0;
}
function strikeChance(diff, bonus) {
  const sides = S.cfg.command_sides;
  let hits = 0;
  for (let r = 1; r <= sides; r++) if (r === sides || (r !== 1 && r + bonus >= diff)) hits++;
  return hits / sides;
}

function eventText(ev, outcome) {
  return { ball: "BALL", called_strike: "CALLED STRIKE", whiff: "SWING & MISS", foul: "FOUL BALL" }[ev] ||
    { SINGLE: "SINGLE", DOUBLE: "DOUBLE", TRIPLE: "TRIPLE", HR: "HOME RUN", OUT: "OUT IN PLAY" }[outcome] ||
    (ev === "in_play" ? "IN PLAY" : ev);
}
function resultText(r) {
  return { K_S: "Strikeout swinging", K_L: "Strikeout looking", BB: "Walk", SINGLE: "Single", DOUBLE: "Double",
    TRIPLE: "Triple", HR: "Home run", OUT: "Out in play" }[r] || r;
}
function resultTag(r) {
  const cls = ["SINGLE", "DOUBLE", "TRIPLE", "HR"].includes(r) ? "hit" : r === "BB" ? "bb" : r.startsWith("K") ? "k" : "out";
  return `<span class="tag ${cls}">${{ K_S: "K", K_L: "Kꓘ", BB: "BB", SINGLE: "1B", DOUBLE: "2B", TRIPLE: "3B", HR: "HR", OUT: "OUT" }[r]}</span>`;
}

// ---------------------------------------------------------------- render

function render() {
  if (!S) return;
  document.querySelectorAll("#modes button").forEach(b => b.classList.toggle("active", b.dataset.mode === S.mode));
  renderScoreboard();
  renderStatus();
  renderZone();
  renderSecret();
  renderControls();
  renderResult();
  renderDiscards();
  renderLogs();
}

function renderScoreboard() {
  $("ab-no").textContent = S.ab_no;
  $("pitch-no").textContent = S.pitch_no;
  const [b, s] = S.count;
  $("balls").innerHTML = [0, 1, 2, 3].map(i => `<span class="light ball ${i < b ? "on" : ""}"></span>`).join("");
  $("strikes").innerHTML = [0, 1].map(i => `<span class="light strike ${i < s ? "on" : ""}"></span>`).join("") +
    (S.result && S.result.startsWith("K") ? `<span class="light strike on"></span>` : "");
  $("hand-count").textContent = S.hand_count;
  $("deck-count").textContent = S.deck_count;
}

function renderStatus() {
  let t = "";
  if (S.phase === "result") {
    t = S.result ? `At-bat over: <b>${resultText(S.result)}</b>` : `Count ${S.count[0]}-${S.count[1]}`;
  } else if (S.mode === "bat") {
    t = `The pitcher has set the zone and a secret pitch. <b>Bet your dice</b> or take.`;
  } else if (S.mode === "pitch") {
    t = `Build your zone, pick a <b>pitch card</b> and a <b>location</b> (a ♥ on one of your zone cards), then throw.`;
  } else {
    const sc = S.scout;
    const plan = sc && Object.keys(sc.bets).length ? `swing (${Object.entries(sc.bets).map(([c, n]) => `${n} on ${CELL_LABEL(c)}`).join(", ")})` : "take";
    t = `AI batter will <b>${plan}</b> · take EV ${sc.ev_take.toFixed(3)} vs swing EV ${sc.ev_swing?.toFixed(3) ?? "-"}`;
  }
  $("status").innerHTML = t;
}

function zoneGrid() {
  if (S.mode === "pitch" && S.phase === "pitcher") return draft.grid;
  return S.grid || {};
}

function renderZone() {
  const z = $("zone");
  z.innerHTML = "";
  z.classList.toggle("g2", S.cfg.grid_size === 2);
  const grid = zoneGrid();
  const scout = S.scout && ($("scout-toggle").checked || S.mode !== "bat") ? S.scout : null;
  const shownBets = S.phase === "result" ? (S.last?.bets || {}) : (S.mode === "bat" ? bets : (S.mode === "watch" && S.scout ? S.scout.bets : {}));
  for (let c = 1; c <= nCells(); c++) {
    const cell = el("div", "cell");
    cell.appendChild(el("span", "cell-label", CELL_LABEL(c)));
    const card = grid[c];
    if (card) cell.appendChild(cardEl(card, "", S.mode === "pitch" && S.phase === "pitcher" ? "clickable" : ""));
    if (S.read_row !== null && S.read_row !== undefined && Math.floor((c - 1) / S.cfg.grid_size) === S.read_row) cell.classList.add("row-read");
    if (S.phase === "result" && S.last && S.last.location === c) cell.classList.add("located");
    if (S.mode === "pitch" && S.phase === "pitcher" && draft.location === c) cell.classList.add("located");
    if (S.mode === "watch" && S.phase === "batter" && $("peek-toggle").checked && S.secret?.location === c) cell.classList.add("located");

    if (scout && card && scout.cells[c]) {
      const p = scout.cells[c].p;
      const h = el("div", "heat", `${Math.round(p * 100)}%`);
      h.style.background = `rgba(242,193,78,${0.35 + Math.min(0.65, p)})`;
      h.title = `AI read: ${pct(p)} target · avg difficulty ${scout.cells[c].avg_diff?.toFixed(1) ?? "-"}`;
      cell.appendChild(h);
    }
    const n = shownBets[c] || 0;
    if (n) cell.appendChild(el("div", "chip", n));

    if (S.mode === "bat" && S.phase === "batter" && card) {
      cell.classList.add("droppable");
      cell.onclick = e => { e.shiftKey ? removeDie(c) : addDie(c); };
      cell.oncontextmenu = e => { e.preventDefault(); removeDie(c); };
    }
    if (S.mode === "pitch" && S.phase === "pitcher") {
      cell.classList.add("droppable");
      cell.onclick = () => placeCard(c);
    }
    z.appendChild(cell);
  }
}

function renderSecret() {
  const s = $("secret");
  s.innerHTML = "";
  const add = (lbl, node) => { const w = el("div"); w.appendChild(el("div", "lbl", lbl)); w.appendChild(node); s.appendChild(w); };
  if (S.phase === "result" && S.last) {
    add("Pitch", S.last.reveal ? cardEl(S.last.reveal, "med", "flip") : el("div", "muted small", "none"));
    add("Location", S.last.location ? heartEl(S.last.location) : el("div", "muted small", "—"));
  } else if (S.phase === "batter") {
    const peek = S.mode === "watch" && $("peek-toggle").checked && S.secret;
    add("Pitch", peek && S.secret.reveal ? cardEl(S.secret.reveal, "med") : backEl());
    add("Location", peek && S.secret.location ? heartEl(S.secret.location) : backEl());
  }
  const r = $("read");
  r.textContent = (S.read_row !== null && S.read_row !== undefined) ? `👁 Batter's eye: the pitch is in the ${rowName(S.read_row)} row` : "";
}

function renderControls() {
  const batting = S.mode === "bat" && S.phase === "batter";
  const pitching = S.mode === "pitch" && S.phase === "pitcher";
  $("bat-controls").classList.toggle("hidden", S.mode !== "bat");
  $("pitch-controls").classList.toggle("hidden", !pitching);
  $("watch-controls").classList.toggle("hidden", S.mode !== "watch");
  $("next-wrap").classList.toggle("hidden", S.phase !== "result" || S.mode === "watch");
  $("btn-next").textContent = S.result ? "Next at-bat" : "Next pitch";
  if (S.mode === "bat") renderTray(batting);
  if (pitching) renderPitcher();
  if (S.mode === "watch") {
    const h = $("watch-hand");
    h.innerHTML = "";
    (S.hand || []).forEach(c => h.appendChild(cardEl(c)));
    if (!S.hand?.length) h.innerHTML = `<span class="muted small">empty</span>`;
    $("btn-step").textContent = S.phase === "batter" ? "Step: swing" : (S.result ? "Step: next at-bat" : "Step: next pitch");
  }
}

function renderTray(active) {
  const t = $("tray");
  t.innerHTML = "";
  const N = S.cfg.batter_dice;
  const grid = S.grid || {};
  const useBets = S.phase === "result" ? (S.last?.bets || {}) : bets;
  const pen = S.phase === "result" ? (S.last?.penalty || 0) : penaltyFor(useBets, grid);
  const bet = betTotal(useBets);
  const reserve = Math.max(0, N - pen - bet);
  for (let i = 0; i < bet; i++) t.appendChild(dieEl(null, "bet"));
  for (let i = 0; i < pen; i++) t.appendChild(dieEl(null, "lost"));
  for (let i = 0; i < reserve; i++) t.appendChild(dieEl(null, "power"));
  const k = suitsBet(useBets, grid).size;
  const nCards = Object.keys(useBets).filter(c => useBets[c]).length;
  const sys = S.cfg.power_system;
  const used = sys === "sum" ? reserve : Math.min(reserve, S.cfg.hand_dice);
  const powerNote = S.cfg.power_rule === "reserve" ? `${used} power dice${sys !== "sum" && reserve > used ? ` (${reserve - used} unused)` : ""}` : `power = all dice not on the hit card`;
  const keep = sys === "sum" && S.cfg.power_keep > 0 ? ` (best ${S.cfg.power_keep} count)` : "";
  let rr = "";
  if (sys !== "sum") {
    const cost = S.phase === "result" ? (S.last?.reroll_cost || 0) : rerollCost(useBets, grid);
    rr = ` · re-rolls <b>${S.rerolls}</b>${cost ? ` (spread costs <b>${cost}</b>)` : ""}`;
  }
  $("tray-summary").innerHTML = bet
    ? `Bet <b>${bet}</b> on ${nCards} card${nCards > 1 ? "s" : ""} · ${k} pitch type${k > 1 ? "s" : ""}${pen ? ` → <b>${penaltyText(useBets, grid)}</b>` : ""} · ${powerNote}${keep}${rr}`
    : `No dice bet. ${N} dice${sys !== "sum" ? ` · re-rolls <b>${S.rerolls}</b>` : ""}. Taking = no swing.`;
  ["btn-swing", "btn-take", "btn-clear", "btn-suggest"].forEach(id => $(id).disabled = !active);
  $("btn-swing").disabled = !active || bet === 0;
}

function addDie(c) {
  const grid = S.grid;
  const nb = { ...bets, [c]: (bets[c] || 0) + 1 };
  if (betTotal(nb) > S.cfg.batter_dice - penaltyFor(nb, grid)) return toast("Not enough dice (spreading costs dice)");
  if (rerollCost(nb, grid) > S.rerolls) return toast("Not enough re-rolls (spreading costs re-rolls)");
  bets = nb;
  render();
}
function removeDie(c) {
  if (!bets[c]) return;
  bets = { ...bets, [c]: bets[c] - 1 };
  if (!bets[c]) delete bets[c];
  render();
}

// ---- pitcher

function draftUsed() {
  return new Set([...Object.values(draft.grid), draft.reveal].filter(Boolean));
}
function renderPitcher() {
  const h = $("hand");
  h.innerHTML = "";
  const used = draftUsed();
  (S.hand || []).filter(c => !used.has(c)).forEach(c => {
    const e = cardEl(c, "", "clickable" + (draft.selected === c ? " selected" : ""));
    e.onclick = () => { draft.selected = draft.selected === c ? null : c; render(); };
    e.ondblclick = () => { draft.reveal = c; draft.selected = null; render(); };
    h.appendChild(e);
  });
  if (!h.children.length) h.innerHTML = `<span class="muted small">All cards placed.</span>`;
  const slot = $("reveal-slot");
  slot.innerHTML = "";
  if (draft.reveal) {
    const e = cardEl(draft.reveal, "", "clickable");
    slot.appendChild(e);
  } else slot.textContent = "click a hand card, then here (or double-click it)";
  slot.onclick = () => {
    if (draft.selected) { draft.reveal = draft.selected; draft.selected = null; }
    else if (draft.reveal) draft.reveal = null;
    render();
  };
  const hearts = $("hearts");
  hearts.innerHTML = "";
  hearts.classList.toggle("g2", S.cfg.grid_size === 2);
  for (let c = 1; c <= nCells(); c++) {
    const b = el("button", "heart-btn" + (draft.location === c ? " sel" : ""), `${CELL_LABEL(c)}♥`);
    b.disabled = !draft.grid[c];
    b.title = draft.grid[c] ? "" : "Location must be a cell with a zone card";
    b.onclick = () => { draft.location = draft.location === c ? null : c; render(); };
    hearts.appendChild(b);
  }
  const nGrid = Object.keys(draft.grid).length;
  $("pitch-hint").textContent = `${nGrid}/${maxZone()} in zone · ${S.hand.length - draftUsed().size} left in hand · draw ${S.cfg.draw_per_pitch} after`;
  // preview
  let pv = "";
  if (draft.reveal && draft.location) {
    const target = draft.grid[draft.location];
    const zone = Object.values(draft.grid);
    const diff = cardValue(target) - cardValue(draft.reveal);
    const sb = suitBonus(zone, suitOf(target));
    const ba = S.cfg.bonus_applies;
    const bonus = (ba !== "batter" ? sb : 0) + S.cfg.command_bonus;
    const bb = ba !== "pitcher" ? sb : 0;
    const d = Math.max(S.cfg.difficulty_floor, diff + bb);
    pv = `${PNAME[suitOf(target)]} at ${CELL_LABEL(draft.location)} · difference ${cardValue(target)} − ${cardValue(draft.reveal)} = <b>${diff}</b>. ` +
      `If the batter swings, they need more than <b>${d}</b> to make contact${bb ? ` (${diff} + ${bb} multiples)` : ""}. ` +
      `If they take, strike chance <b>${pct(strikeChance(diff, bonus), 0)}</b> (d${S.cfg.command_sides}${bonus ? ` + ${bonus}` : ""} ≥ ${diff}; 1 = ball, ${S.cfg.command_sides} = strike).`;
  }
  $("pitch-preview").innerHTML = pv;
  $("btn-throw").disabled = !(draft.location && (draft.reveal || !S.hand.length));
}

function placeCard(c) {
  if (draft.grid[c]) {           // return to hand
    delete draft.grid[c];
    if (draft.location === c) draft.location = null;
  } else if (draft.selected) {
    if (Object.keys(draft.grid).length >= maxZone()) return toast(`Max ${maxZone()} zone cards`);
    draft.grid[c] = draft.selected;
    draft.selected = null;
  }
  render();
}

// ---- result

function renderResult() {
  const r = $("result");
  const L = S.last;
  if (!L) { r.className = "result muted"; r.textContent = "No pitch yet."; return; }
  r.className = "result";
  r.innerHTML = "";
  const isHit = ["SINGLE", "DOUBLE", "TRIPLE", "HR"].includes(L.outcome);
  const cls = isHit ? "hit" : L.event === "ball" ? "ball" : ["whiff", "called_strike"].includes(L.event) ? "strike" : "out";
  r.appendChild(el("div", `outcome ${cls}`, eventText(L.event, L.outcome)));
  if (S.result) r.appendChild(el("div", "", `At-bat: ${resultTag(S.result)} ${resultText(S.result)}`));

  const target = L.target;
  if (!L.reveal) r.appendChild(el("div", "small", "Pitcher had no cards: automatic ball."));
  else {
    r.appendChild(el("div", "small", `${PNAME[suitOf(target)]} at ${CELL_LABEL(L.location)}: ${rankLabel(target)}${SUIT_SYM[suitOf(target)]} − ${rankLabel(L.reveal)}${SUIT_SYM[suitOf(L.reveal)]} = difference <b>${L.difference}</b>`));
    if (L.command_roll === null) {
      r.appendChild(el("div", "small muted", `Batter swung, so no strike roll (it was ${pct(L.p_strike, 0)} to be a strike).`));
    } else {
      const row = el("div", "dice-row");
      row.appendChild(dieEl(L.command_roll, "roll pitcher"));
      const sides = S.cfg.command_sides;
      const how = L.command_roll === 1 ? "a 1 is always a ball" : L.command_roll === sides ? `a ${sides} is always a strike`
        : `${L.command_roll}${L.command_bonus ? ` + ${L.command_bonus}` : ""} ${L.strike ? "≥" : "<"} ${L.difference}`;
      row.appendChild(el("span", "small", `&nbsp;${how} → <b>${L.strike ? "strike" : "ball"}</b>`));
      r.appendChild(el("div", "small muted", "Pitcher's strike roll (batter took)"));
      r.appendChild(row);
    }
  }

  const betStr = Object.entries(L.bets).map(([c, n]) => `${n} on ${CELL_LABEL(c)}`).join(", ");
  r.appendChild(el("div", "small muted", L.swing ? `Swing: ${betStr}${L.penalty ? ` (${penaltyText(L.bets, L.grid)})` : ""}` : "No swing."));
  if (L.whiff_reason === "missed") r.appendChild(el("div", "small", `No dice on the pitch's card: <b>swing and miss</b>.`));

  if (L.parts) {
    const p = L.parts;
    r.appendChild(el("div", "math", `Difficulty ${p.zone} − ${p.reveal}` + (p.suit_bonus ? ` + ${p.suit_bonus} multiples` : "") + ` = <b>${p.total}</b>`));
    const row = el("div", "dice-row");
    const rolls = L.contact_roll, last = rolls[rolls.length - 1], top = S.cfg.die_sides;
    rolls.forEach((v, i) => row.appendChild(dieEl(v, "roll" + (i === rolls.length - 1 && L.whiff_reason === "ones" ? " one" : ""))));
    for (let i = rolls.length; i < L.contact_dice; i++) row.appendChild(dieEl(null, "unrolled"));
    let why;
    if (L.whiff_reason === "ones") why = `rolled a 1 → <b>swing and miss</b>`;
    else if (L.event === "in_play" && S.cfg.six_hits && last === top) why = `rolled a ${top} → <b>hit</b>`;
    else if (L.event === "in_play") why = `total ${L.contact_sum} > ${p.total} → <b>contact</b>`;
    else why = `out of dice at ${L.contact_sum} (needed more than ${p.total}) → foul`;
    row.appendChild(el("span", "small", `&nbsp;${why}`));
    r.appendChild(el("div", "small muted", `Contact roll: one die at a time, up to ${L.contact_dice}`));
    r.appendChild(row);
  }
  if (L.climb) {
    const row = el("div", "dice-row");
    L.climb.forEach(x => row.appendChild(dieEl(x.face, "roll" + (x.status === "rerolled" ? " unrolled" : x.status === "break" ? " one" : ""))));
    const len = L.climb_length;
    row.appendChild(el("span", "small", `&nbsp;streak of <b>${len}</b>${L.rerolls_used ? ` · ${L.rerolls_used} re-roll${L.rerolls_used > 1 ? "s" : ""} used` : ""}`));
    const [c1, c2, c3] = S.cfg.climb_ladder;
    r.appendChild(el("div", "small muted", `Climb (${L.power_dice} power dice, up to ${S.cfg.hand_dice} count): each die must be at least the last. Faded = re-rolled, red = broke the streak.`));
    r.appendChild(row);
    r.appendChild(el("div", "small muted", `${c1} = 1B · ${c2} = 2B (rising every die = 3B) · ${c3} = HR`));
  } else if (L.hand) {
    const row = el("div", "dice-row");
    L.power_roll.forEach(v => row.appendChild(dieEl(v, "roll")));
    row.appendChild(el("span", "small", `&nbsp;<b>${L.hand.replace("_", " ")}</b>${L.rerolls_used ? ` · ${L.rerolls_used} re-roll${L.rerolls_used > 1 ? "s" : ""}` : ""}`));
    r.appendChild(el("div", "small muted", `Power hand (first roll ${L.power_first.join("-")})`));
    r.appendChild(row);
    r.appendChild(el("div", "small muted", S.cfg.hand_map));
  } else if (L.event === "in_play") {
    const keep = S.cfg.power_keep;
    const sorted = [...L.power_roll].map((v, i) => [v, i]).sort((a, b) => b[0] - a[0]);
    const counted = new Set(keep > 0 ? sorted.slice(0, keep).map(x => x[1]) : L.power_roll.map((_, i) => i));
    const row = el("div", "dice-row");
    L.power_roll.forEach((v, i) => row.appendChild(dieEl(v, "roll" + (counted.has(i) && keep > 0 ? " counted" : ""))));
    const [t1, t2, t3, t4] = S.cfg.power_thresholds;
    const mod = L.power_mod || 0;
    row.appendChild(el("span", "small", `&nbsp;${mod ? (mod > 0 ? `+ ${mod}` : `− ${-mod}`) + " " : ""}= <b>${L.power_total}</b>`));
    r.appendChild(el("div", "small muted", `Power roll (${L.power_dice} dice${keep > 0 ? `, best ${keep} count` : ""})`));
    r.appendChild(row);
    r.appendChild(el("div", "small muted", `1B ${t1}+ · 2B ${t2}+ · 3B ${t3}+ · HR ${t4}+`));
  }
  if (S.scout && S.mode === "pitch") {
    r.appendChild(el("div", "small muted", `AI batter read: take EV ${S.scout.ev_take.toFixed(3)}, best swing EV ${S.scout.ev_swing?.toFixed(3) ?? "-"}`));
  }
}

function renderDiscards() {
  // Whole deck as outlines; cards the batter has seen (played rows + current zone) are filled in
  const d = $("discards");
  d.innerHTML = "";
  const played = new Set(Object.values(S.discards).flat());
  const inZone = new Set(Object.values(S.grid || {}));
  ["S", "D", "C"].forEach(s => {
    const cards = S.deck_cards.filter(c => suitOf(c) === s);
    const n = cards.length;
    if (!n) return;
    const seen = cards.filter(c => played.has(c) || inZone.has(c)).length;
    d.appendChild(el("div", "dlabel", `${SUIT_SYM[s]} ${PNAME[s]} <span class="muted">· ${n - seen} of ${n} unseen</span>`));
    const row = el("div", "drow");
    cards.forEach(c => {
      if (played.has(c)) row.appendChild(cardEl(c, "mini"));
      else if (inZone.has(c)) row.appendChild(cardEl(c, "mini", "in-zone"));
      else {
        const g = el("div", `card mini ghost ${s}`, `<div class="rank">${rankLabel(c)}</div>`);
        g.title = `${rankLabel(c)}${SUIT_SYM[s]}: not seen yet (deck or pitcher's hand)`;
        row.appendChild(g);
      }
    });
    d.appendChild(row);
  });
}

function renderLogs() {
  const o = S.session;
  $("slash").textContent = `${fmt3(o.BA)} / ${fmt3(o.OBP)} / ${fmt3(o.SLG)}`;
  const oc = o.outcomes;
  $("session-line").textContent = `${o.pa} PA · ${(oc.HR || 0)} HR · ${(oc.BB || 0)} BB · ${((oc.K_S || 0) + (oc.K_L || 0))} K`;
  $("history").innerHTML = [...o.history].reverse().map(h => `<li>AB ${h.ab}: ${resultTag(h.result)} ${h.pitches} pitches</li>`).join("");
  $("ab-log").innerHTML = S.ab_log.map(p =>
    `<li>${p.target ? SUIT_SYM[suitOf(p.target)] : "–"} @${p.location ? CELL_LABEL(p.location) : "–"} · ${eventText(p.event, p.outcome).toLowerCase()} → ${p.count[0]}-${p.count[1]}</li>`).join("");
}

// ---------------------------------------------------------------- actions

$("btn-swing").onclick = () => { const b = bets; bets = {}; act("/api/swing", { bets: b }); };
$("btn-take").onclick = () => { bets = {}; act("/api/swing", { bets: {} }); };
$("btn-clear").onclick = () => { bets = {}; render(); };
$("btn-suggest").onclick = () => { if (S.scout) { bets = { ...S.scout.bets }; render(); } };
$("scout-toggle").onchange = render;
$("peek-toggle").onchange = render;
$("btn-next").onclick = () => { bets = {}; resetDraft(); act("/api/next", {}); };

function resetDraft() { draft = { grid: {}, reveal: null, location: null, selected: null }; }
$("btn-pclear").onclick = () => { resetDraft(); render(); };
$("btn-psuggest").onclick = async () => {
  try {
    const p = await api("/api/suggest_pitch", {});
    draft = { grid: Object.fromEntries(Object.entries(p.grid).map(([k, v]) => [Number(k), v])), reveal: p.reveal, location: p.location, selected: null };
    render();
  } catch (e) { toast(e.message); }
};
$("btn-throw").onclick = () => {
  const body = { grid: draft.grid, reveal: draft.reveal, location: draft.location };
  resetDraft();
  act("/api/pitch", body);
};

$("btn-step").onclick = () => act("/api/step", {});
function stopAuto() { clearTimeout(autoTimer); autoTimer = null; $("btn-auto").textContent = "Auto ▶"; }
$("btn-auto").onclick = () => {
  if (autoTimer) return stopAuto();
  $("btn-auto").textContent = "Pause ❚❚";
  const tick = async () => { await act("/api/step", {}); if (autoTimer !== null) autoTimer = setTimeout(tick, Number($("speed").value)); };
  autoTimer = setTimeout(tick, 10);
};

document.querySelectorAll("#modes button").forEach(b => b.onclick = () => newGame(b.dataset.mode));

// Drop overrides for levers the server no longer has (e.g. after a restart with new rules)
async function pruneOverrides() {
  const known = new Set((await api("/api/levers")).levers.map(l => l.key));
  overrides = Object.fromEntries(Object.entries(overrides).filter(([k]) => known.has(k)));
}

async function newGame(mode) {
  stopAuto();
  await pruneOverrides();
  bets = {};
  resetDraft();
  act("/api/new", { mode: mode || S?.mode || "bat", config: overrides, preset: preset || undefined });
}

// ---------------------------------------------------------------- levers & sim

function openModal(title, body) {
  $("modal-title").textContent = title;
  $("modal-body").innerHTML = "";
  $("modal-body").appendChild(body);
  $("modal").classList.remove("hidden");
}
$("modal-close").onclick = () => $("modal").classList.add("hidden");
$("modal").onclick = e => { if (e.target.id === "modal") $("modal").classList.add("hidden"); };

function leverValueStr(v) { return Array.isArray(v) ? v.join(",") : String(v); }

async function leverForm(values) {
  leverMeta = await api("/api/levers");   // re-fetch: the server's levers change between restarts
  const wrap = el("div");
  const top = el("div", "buttons");
  const sel = el("select");
  sel.innerHTML = `<option value="">(defaults)</option>` + leverMeta.presets.map(p => `<option ${p === preset ? "selected" : ""}>${p}</option>`).join("");
  top.appendChild(el("span", "muted small", "Preset"));
  top.appendChild(sel);
  wrap.appendChild(top);
  const groups = el("div", "lever-groups");
  const byGroup = {};
  leverMeta.levers.forEach(l => (byGroup[l.group] ||= []).push(l));
  const inputs = {};
  for (const [g, ls] of Object.entries(byGroup)) {
    const box = el("div", "panel");
    box.appendChild(el("h3", "", g));
    ls.forEach(l => {
      const row = el("label", "lever");
      row.appendChild(el("span", "", l.label));
      const inp = el("input");
      if (typeof l.default === "boolean") { inp.type = "checkbox"; inp.checked = values[l.key]; }
      else inp.value = leverValueStr(values[l.key]);
      if (leverValueStr(values[l.key]) !== leverValueStr(l.default)) row.classList.add("changed");
      inputs[l.key] = inp;
      row.appendChild(inp);
      if (l.hint) row.appendChild(el("span", "hint", l.hint));
      box.appendChild(row);
      if (l.key === "removed_cards") {
        inp.readOnly = true;
        inp.placeholder = "none";
        box.appendChild(cardPicker(inp, () => inputs.deck_mix?.value));
      }
    });
    groups.appendChild(box);
  }
  wrap.appendChild(groups);
  sel.onchange = async () => {
    const vals = sel.value ? await api(`/api/preset/${sel.value}`) : Object.fromEntries(leverMeta.levers.map(l => [l.key, l.default]));
    leverMeta.levers.forEach(l => {
      const inp = inputs[l.key];
      if (inp.type === "checkbox") inp.checked = vals[l.key]; else inp.value = leverValueStr(vals[l.key]);
      inp._refresh?.();
    });
  };
  const collect = () => {
    const out = {};
    leverMeta.levers.forEach(l => {
      const inp = inputs[l.key];
      const v = inp.type === "checkbox" ? inp.checked : inp.value.trim();
      if (leverValueStr(v) !== leverValueStr(l.default)) out[l.key] = v;
    });
    return out;
  };
  return { wrap, collect, presetSel: sel };
}

// Click-to-remove grid of the whole deck; writes "2S,7S,..." into the removed_cards input
function cardPicker(inp, deckMix) {
  const wrap = el("div", "picker");
  const get = () => new Set(inp.value.split(",").map(x => x.trim().toUpperCase()).filter(Boolean));
  const draw = () => {
    wrap.innerHTML = "";
    const gone = get();
    const mix = (deckMix() || "13,13,13").split(",").map(Number);
    ["S", "D", "C"].forEach((s, i) => {
      const row = el("div", "picker-row");
      [...RANKS].forEach((r, j) => {
        const c = r + s;
        const trimmed = j >= (mix[i] ?? 13);
        const e = cardEl(c, "mini", "clickable" + (gone.has(c) ? " removed" : "") + (trimmed ? " trimmed" : ""));
        e.title = trimmed ? `${rankLabel(c)}${SUIT_SYM[s]}: already out via Deck mix` : `${rankLabel(c)}${SUIT_SYM[s]}: click to ${gone.has(c) ? "put back" : "remove"}`;
        if (!trimmed) e.onclick = () => {
          const g = get();
          g.has(c) ? g.delete(c) : g.add(c);
          inp.value = [...g].sort().join(",");
          draw();
        };
        row.appendChild(e);
      });
      wrap.appendChild(row);
    });
    wrap.appendChild(el("div", "muted small", `${get().size} removed · click again to put a card back`));
  };
  inp._refresh = draw;
  draw();
  return wrap;
}

$("btn-levers").onclick = async () => {
  const f = await leverForm(S.cfg);
  const btns = el("div", "buttons");
  btns.style.marginTop = "12px";
  const apply = el("button", "primary", "Apply &amp; new game");
  const simb = el("button", "", "Simulate with these");
  const reset = el("button", "", "Reset to defaults");
  btns.append(apply, simb, reset);
  f.wrap.appendChild(btns);
  // Presets carry levers the form doesn't show (e.g. count values), so keep the preset name too
  apply.onclick = () => { preset = f.presetSel.value; overrides = f.collect(); $("modal").classList.add("hidden"); newGame(); };
  simb.onclick = () => { preset = f.presetSel.value; overrides = f.collect(); openSim(); };
  reset.onclick = () => { preset = ""; overrides = {}; $("modal").classList.add("hidden"); newGame(); };
  openModal("Levers", f.wrap);
};

$("btn-sim").onclick = () => openSim();

function openSim() {
  const wrap = el("div");
  const bar = el("div", "buttons");
  const n = el("input");
  n.type = "number"; n.value = 2000; n.min = 100; n.max = 20000; n.style.width = "90px";
  const run = el("button", "primary", "Run");
  const desc = Object.keys(overrides).length || preset ? `${preset ? `preset <b>${preset}</b> + ` : ""}${Object.keys(overrides).length} lever change(s)` : "default levers";
  bar.append(el("span", "muted small", "At-bats"), n, run, el("span", "muted small", `Using ${desc}. Edit in Levers.`));
  const out = el("div", "", "");
  wrap.append(bar, out);
  run.onclick = async () => {
    run.disabled = true;
    out.innerHTML = `<p class="muted">Simulating ${n.value} at-bats…</p>`;
    try {
      await pruneOverrides();
      const r = await api("/api/sim", { n: Number(n.value), config: overrides, preset: preset || undefined });
      out.innerHTML = "";
      out.appendChild(simTables(r));
    } catch (e) { out.innerHTML = `<p class="hi">${e.message}</p>`; }
    run.disabled = false;
  };
  openModal("Simulate", wrap);
}

function simTables(r) {
  const res = r.result;
  const grid = el("div", "sim-grid");
  const table = (title, head, rows) => {
    const box = el("div", "panel");
    box.appendChild(el("h3", "", title));
    const t = el("table", "stats");
    t.innerHTML = `<tr>${head.map(h => `<th>${h}</th>`).join("")}</tr>` + rows.map(row => `<tr>${row.map(c => `<td>${c}</td>`).join("")}</tr>`).join("");
    box.appendChild(t);
    return box;
  };
  const isPct = k => k.endsWith("%") || k === "HR/PA";
  const f = (k, v) => isPct(k) ? pct(v) : k === "P/PA" ? v.toFixed(2) : fmt3(v);
  const statRows = Object.entries(r.targets).map(([k, [t, tol]]) => {
    const v = res.stats[k];
    const d = v - t;
    const flag = Math.abs(d) <= tol ? `<span class="ok">✓</span>` : `<span class="${d > 0 ? "hi" : "lo"}">${d > 0 ? "↑" : "↓"} ${isPct(k) ? pct(Math.abs(d)) : Math.abs(d).toFixed(3)}</span>`;
    return [k, f(k, v), f(k, t) + (r.approx.includes(k) ? "~" : ""), flag];
  });
  grid.appendChild(table(`Stat line vs 2026 (${res.pa.toLocaleString()} PA)`, ["Stat", "Game", "2026", ""], statRows));
  const o = res.outcomes, pa = res.pa, m = r.mix_targets;
  grid.appendChild(table("Outcomes per PA", ["", "Game", "MLB"], [
    ["Walk", pct(o.BB / pa), pct(m.BB)], ["K swinging", pct(o.K_S / pa), ""], ["K looking", pct(o.K_L / pa), ""],
    ["K total", pct((o.K_S + o.K_L) / pa), pct(m.K)], ["Single", pct(o.SINGLE / pa), pct(m.SINGLE)],
    ["Double", pct(o.DOUBLE / pa), pct(m.DOUBLE)], ["Triple", pct(o.TRIPLE / pa), pct(m.TRIPLE)],
    ["Home run", pct(o.HR / pa), pct(m.HR)], ["Out in play", pct(o.OUT / pa), pct(m.OUT)],
  ]));
  grid.appendChild(table("Plate discipline", ["", "Game", "MLB~"],
    Object.entries(r.discipline_targets).map(([k, t]) => [k, pct(res.discipline[k]), pct(t, 0)])));
  const names = { FB: "♠ Fastball", BR: "♣ Breaking", OS: "♦ Off-speed" };
  grid.appendChild(table("Pitch mix", ["", "Game", "MLB~"],
    Object.entries(r.pitch_mix_targets).map(([k, t]) => [names[k], pct(res.mix[k]), pct(t, 0)])));
  const u = res.usage;
  grid.appendChild(table("Cards & dice", ["", ""], [
    ["Zone cards by pitch #", Object.entries(u.zone_cards_by_pitch).map(([k, v]) => `#${k}: ${v.toFixed(1)}`).join(" ")],
    ["Cells bet per swing", u.cells_per_swing.toFixed(2)], ["Dice bet per swing", u.dice_bet_per_swing.toFixed(1)],
    ["Dice lost to mix", u.penalty_per_swing.toFixed(2)], ["Power dice per swing", u.reserve_per_swing.toFixed(1)],
  ]));
  const ev = res.events;
  grid.appendChild(table("Pitch events", ["", "Share"],
    ["ball", "called_strike", "whiff", "foul", "in_play"].map(k => [eventText(k, null).toLowerCase(), pct(ev[k] || 0)])));
  return grid;
}

// ---------------------------------------------------------------- boot
api("/api/state").then(s => { S = s; preset = s.preset || ""; render(); }).catch(e => toast(e.message));
