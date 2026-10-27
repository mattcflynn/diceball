"""
Local playtest server. Single session, stdlib only.

    uv run -m cardball.server            # http://localhost:8765
    uv run -m cardball.server --port 9000 --no-browser
    uv run -m cardball.server --preset ''     # rules exactly as written, untuned
"""
import argparse
import json
import random
import threading
import webbrowser
from collections import Counter
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from cardball import config as config_mod
from cardball.ai import pitcher_plan, batter_decide
from cardball.cards import SUITS, deck, rank_num, suit
from cardball.game import AtBat
from cardball.rules import HITS
from cardball import sim

WEB = Path(__file__).parent / "web"
PRESETS = Path(__file__).parent / "presets"
DEFAULT_PRESET = "v2_tuned"
STATIC = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
          "/style.css": ("style.css", "text/css")}


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    return x


class Session:
    def __init__(self, mode, cfg, seed=None, preset=""):
        if mode not in ("bat", "pitch", "watch"):
            raise ValueError("mode must be bat, pitch or watch")
        self.mode, self.cfg, self.preset = mode, cfg, preset
        self.rng = random.Random(seed)
        self.ab_no = 0
        self.outcomes = Counter()
        self.history = []
        self.new_ab()

    def new_ab(self):
        self.ab = AtBat(self.cfg, self.rng)
        self.ab_no += 1
        self.last = None
        self.start_pitch()

    def start_pitch(self):
        self.scout, self.secret = None, None
        if self.mode == "pitch":
            self.phase = "pitcher"
            return
        grid, reveal, loc = pitcher_plan(self.ab.hand, self.ab.count, self.cfg, self.rng)
        self.ab.commit_pitch(grid, reveal, loc)
        self.secret = {"reveal": reveal, "location": loc}
        self.scout = batter_decide(self.ab.public(), self.cfg, self.rng)
        self.phase = "batter"

    def suggest_pitch(self):
        self._need("pitch", "pitcher")
        grid, reveal, loc = pitcher_plan(self.ab.hand, self.ab.count, self.cfg, random.Random())
        return {"grid": grid, "reveal": reveal, "location": loc}

    def pitch(self, grid, reveal, location):
        self._need("pitch", "pitcher")
        self.ab.commit_pitch({int(c): v for c, v in grid.items()}, reveal, int(location) if location else None)
        self.secret = {"reveal": reveal, "location": location}
        self.scout = batter_decide(self.ab.public(), self.cfg, self.rng)
        self._resolve(self.scout[0])

    def swing(self, bets):
        self._need("bat", "batter")
        self._resolve({int(c): int(n) for c, n in bets.items() if int(n) > 0})

    def step(self):
        if self.mode != "watch":
            raise ValueError("step is for watch mode")
        if self.phase == "batter":
            self._resolve(self.scout[0])
        else:
            self.next()

    def next(self):
        if self.phase != "result":
            raise ValueError("pitch not resolved yet")
        if self.ab.over:
            self.new_ab()
        else:
            self.start_pitch()

    def _need(self, mode, phase):
        if self.mode != mode or self.phase != phase:
            raise ValueError(f"not allowed now (mode {self.mode}, phase {self.phase})")

    def _resolve(self, bets):
        self.last = self.ab.resolve(bets)
        self.phase = "result"
        if self.ab.over:
            self.outcomes[self.ab.result] += 1
            self.history.append({"ab": self.ab_no, "result": self.ab.result, "pitches": len(self.ab.pitches)})

    def _scout_view(self):
        if not self.scout:
            return None
        bets, info = self.scout
        b = info["beliefs"]
        cells = {}
        for c in self.ab.public()["grid"] if self.phase == "batter" else (self.last or {}).get("grid", {}):
            q = b["contest"].get(c, {})
            qs = sum(q.values())
            cells[c] = {"p": b["target"].get(c, 0.0), "p_strike": b["strike_by_cell"].get(c, 0.0),
                        "avg_diff": (sum(d * w for d, w in q.items()) / qs) if qs else None}
        return {"cells": cells, "p_empty": b["p_empty"], "p_strike": b["p_strike"],
                "ev_take": info["ev_take"], "ev_swing": info["ev_swing"], "bets": bets}

    def state(self):
        ab = self.ab
        pub = ab.public()
        if self.phase == "result" and self.last:
            grid = self.last["grid"]
        else:
            grid = pub["grid"]
        discards = {s: sorted((c for c in ab.discards if suit(c) == s), key=rank_num) for s in SUITS}
        pa = sum(self.outcomes.values())
        o = self.outcomes
        h = sum(o[x] for x in HITS)
        abs_ = pa - o["BB"]
        tb = o["SINGLE"] + 2 * o["DOUBLE"] + 3 * o["TRIPLE"] + 4 * o["HR"]
        show_hand = self.mode in ("pitch", "watch")
        # In bat mode the AI's thinking is shown before the swing (public info only).
        # In pitch mode it is only shown once the pitch is resolved.
        scout = self._scout_view() if (self.mode != "pitch" or self.phase == "result") else None
        return _jsonable({
            "mode": self.mode, "phase": self.phase, "ab_no": self.ab_no,
            "count": list(ab.count) if self.phase != "result" else list((self.last or {}).get("count_after", ab.count)),
            "pitch_no": len(ab.pitches) + (0 if self.phase == "result" else 1),
            "grid": grid, "hand": sorted(ab.hand, key=lambda c: (c[1], rank_num(c))) if show_hand else None,
            "hand_count": len(ab.hand), "deck_count": len(ab.deck), "discards": discards,
            "read_row": pub["read_row"] if self.phase == "batter" else (self.last or {}).get("read_row"),
            "secret": self.secret if self.mode == "watch" else None,
            "scout": scout, "last": self.last, "result": ab.result,
            "ab_log": [{"event": p["event"], "outcome": p["outcome"], "reveal": p["reveal"], "target": p["target"],
                        "location": p["location"], "count": p["count_after"]} for p in ab.pitches],
            "session": {"pa": pa, "outcomes": dict(o), "BA": h / abs_ if abs_ else 0,
                        "OBP": (h + o["BB"]) / pa if pa else 0, "SLG": tb / abs_ if abs_ else 0,
                        "history": self.history[-12:]},
            "rerolls": (self.last or {}).get("rerolls_left", ab.rerolls) if self.phase == "result" else ab.rerolls,
            "cfg": config_mod.to_dict(self.cfg), "preset": self.preset, "deck_cards": list(deck(self.cfg)),
        })


class App:
    def __init__(self, preset=""):
        self.lock = threading.Lock()
        self.session = Session("bat", self.cfg_from({"preset": preset}), preset=preset)

    def cfg_from(self, body):
        cfg = config_mod.Config()
        if body.get("preset"):
            cfg = config_mod.load(PRESETS / f"{body['preset']}.json")
        return config_mod.apply_overrides(cfg, body.get("config") or {})

    def handle(self, method, path, body):
        s = self.session
        if method == "GET" and path == "/api/state":
            return s.state()
        if method == "GET" and path == "/api/levers":
            defaults = config_mod.to_dict(config_mod.Config())
            return {"levers": [{"key": k, "group": g, "label": l, "hint": h, "default": defaults[k]}
                               for k, g, l, h in config_mod.LEVERS],
                    "presets": sorted(p.stem for p in PRESETS.glob("*.json"))}
        if method == "GET" and path.startswith("/api/preset/"):
            name = path.rsplit("/", 1)[1]
            return config_mod.to_dict(config_mod.load(PRESETS / f"{name}.json"))
        if method != "POST":
            raise KeyError(path)
        if path == "/api/new":
            self.session = Session(body.get("mode", "bat"), self.cfg_from(body), body.get("seed"), body.get("preset") or "")
            return self.session.state()
        if path == "/api/pitch":
            s.pitch(body["grid"], body.get("reveal"), body.get("location"))
            return s.state()
        if path == "/api/suggest_pitch":
            return _jsonable(s.suggest_pitch())
        if path == "/api/swing":
            s.swing(body.get("bets", {}))
            return s.state()
        if path == "/api/step":
            s.step()
            return s.state()
        if path == "/api/next":
            s.next()
            return s.state()
        if path == "/api/sim":
            n = max(100, min(int(body.get("n", 1000)), 20000))
            res = sim.simulate(self.cfg_from(body), n)
            return {"result": res, "targets": sim.TARGETS, "approx": sorted(sim.APPROX),
                    "mix_targets": sim.TARGET_MIX, "discipline_targets": sim.DISCIPLINE_TARGETS,
                    "pitch_mix_targets": sim.PITCH_MIX_TARGET}
        raise KeyError(path)


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, payload, ctype="application/json"):
            data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _api(self, method):
            body = {}
            if method == "POST":
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
            try:
                if self.path == "/api/sim":
                    out = app.handle(method, self.path, body)   # long-running; don't hold the game lock
                else:
                    with app.lock:
                        out = app.handle(method, self.path, body)
                self._send(200, out)
            except KeyError as e:
                self._send(404 if method == "GET" else 400, {"error": f"unknown: {e}"})
            except (ValueError, RuntimeError, FileNotFoundError) as e:
                self._send(400, {"error": str(e)})

        def do_GET(self):
            if self.path in STATIC:
                name, ctype = STATIC[self.path]
                return self._send(200, (WEB / name).read_bytes(), ctype + "; charset=utf-8")
            if self.path.startswith("/api/"):
                return self._api("GET")
            self._send(404, {"error": "not found"})

        def do_POST(self):
            self._api("POST")

    return Handler


def main():
    ap = argparse.ArgumentParser(prog="cardball.server")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--preset", default=DEFAULT_PRESET, help="preset name in cardball/presets ('' = rules defaults)")
    a = ap.parse_args()
    if a.preset and not (PRESETS / f"{a.preset}.json").exists():
        raise SystemExit(f"no preset {a.preset!r} in {PRESETS}")
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(App(a.preset)))
    url = f"http://localhost:{a.port}"
    print(f"Cardball playtest at {url}  (ctrl-c to stop)")
    if not a.no_browser:
        threading.Timer(0.5, webbrowser.open, (url,)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
