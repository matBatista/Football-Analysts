# Football Analyst

A small, reusable football analytics toolkit in Python. Three production-ready
visualisations, a standalone metrics library, a cache-first data layer, and free
data — all built to be read and learned from.

Data source: **StatsBomb Open Data** (free, no credentials) via `statsbombpy`.

---

## What's inside

| Module | Function | What it does |
|---|---|---|
| Shot map | `fa.shot_map(match_id)` | Plots every shot on a pitch; bubble size = xG |
| Pass map | `fa.pass_map(match_id, player=…)` | Filters passes for a player or team; highlights progressive passes |
| Player radar | `fa.player_radar(a, b, match_ids)` | Per-90 spider chart comparing two players across 6 metrics |
| Metrics library | `football_metrics` | 15+ analyst-grade functions: xG, xA, PPDA, field tilt, xGChain, per-90, … |

---

## Gallery

> Run the examples below to regenerate these charts.

**Shot map — 2018 World Cup final (France 4-2 Croatia)**
![Shot map](outputs/shot_map_wc2018_final.png)

**Pass map — Antoine Griezmann (France, 2018 WCF)**
![Pass map Griezmann](outputs/pass_map_griezmann.png)

**Pass map — full team (France, 2018 WCF)**
![Pass map team](outputs/pass_map_team.png)

**Player radar — Griezmann vs Modrić**
![Radar](outputs/radar_griezmann_modric.png)

Generate all charts:
```bash
python examples/run_shot_map.py   # → outputs/shot_map_wc2018_final.png
python examples/run_pass_map.py   # → outputs/pass_map_griezmann.png, pass_map_team.png
python examples/run_radar.py      # → outputs/radar_griezmann_modric.png
```

---

## Installation

Requires **Python 3.10+** (the macOS system `python3` is 3.9 — see [SETUP.md](SETUP.md)).

```bash
# Recommended: editable install so the package reflects any local edits
pip install -e .

# Alternative: install dependencies only (no package registration)
pip install -r requirements.txt
```

`pip install -e .` registers `football_analyst` as an importable package project-wide
and keeps `football_metrics.py` accessible from the project root.

---

## Quick start

```python
import football_analyst as fa

db = fa.StatsBomb()          # cache-first data gateway
MATCH = 8658                 # 2018 World Cup final: France 4-2 Croatia

fa.shot_map(MATCH, show=True)
fa.pass_map(MATCH, player="Antoine Griezmann", show=True)
fa.player_radar("Antoine Griezmann", "Luka Modrić", [MATCH], show=True)
```

Or run the ready-made scripts (save PNGs to `outputs/`):

```bash
python examples/run_shot_map.py
python examples/run_pass_map.py
python examples/run_radar.py
```

Or open the interactive notebook:

```bash
jupyter notebook notebooks/01_getting_started.ipynb
```

---

## Metrics library

`football_metrics.py` is a standalone module — no package install needed. It
covers the most common analytics questions:

```python
import football_metrics as fm

# from a StatsBomb events DataFrame (db.events(match_id)):
fm.expected_goals(events, team="France")     # → 2.41
fm.ppda(events, "France", "Croatia")        # → 7.2 (lower = more pressing)
fm.field_tilt(events, "France")             # → 61.3 % of final-third touches
fm.xg_chain(events, "Antoine Griezmann")    # → 1.85 xGChain
fm.per_90(goals, minutes)                   # normalise any stat to per-90
```

See [metrics_cheat_sheet.md](metrics_cheat_sheet.md) for the full reference.

---

## How the data layer works

`StatsBomb` is cache-first: every fetch checks `sb_cache/` before hitting the
network. First run downloads from StatsBomb and saves to disk; after that it's
instant and works offline. The DataFrames are identical to the online versions
(statsbombpy does the JSON→DataFrame conversion either way).

```python
db = fa.StatsBomb()
events  = db.events(8658)      # ~3 000 rows, one per on-ball action
matches = db.matches(43, 3)    # all 2018 World Cup games
lineups = db.lineups(8658)
```

Finding match IDs and player names:

```python
db.competitions()                       # what's available
db.matches(43, 3)["match_id"]           # IDs for a competition + season
db.events(8658)["player"].unique()      # exact names (mind accents: "Luka Modrić")
```

---

## Project layout

```
football_analyst/        installable package
  data.py                StatsBomb gateway — cache-first loading
  viz/
    shot_map.py          shot map + xG
    pass_map.py          pass map + progressive passes
    radar.py             per-90 metrics + comparison radar
examples/                ready-to-run scripts
notebooks/               study lab (Jupyter)
sb_cache/                cached StatsBomb JSON (auto-managed, gitignored)
outputs/                 generated chart PNGs
football_metrics.py      standalone analytics library (15+ metrics)
metrics_cheat_sheet.md   metric reference
requirements.txt         pinned dependencies
pyproject.toml           package metadata (pip install -e .)
```

Full setup and verification steps: [SETUP.md](SETUP.md)

---

## Running the tests

```bash
pip install -e ".[dev]"   # installs pytest

pytest -q                  # all 94 tests (unit + integration, fully offline)
pytest -q -m "not integration"  # unit tests only
```

The integration tests read from `sb_cache/events/8658.json` (ships with the repo)
and require no network access.

---

## Roadmap

- [ ] Expected Threat (xT) — value each pitch zone
- [ ] Passing networks — weighted graphs of team ball circulation
- [ ] Heatmaps — density maps of touches, pressures, carries
- [ ] Season aggregations — multi-match player rankings
- [x] Unit tests + pytest coverage — 94 tests, 16/16 metric functions covered
- [ ] CI (GitHub Actions) — lint, type-check, run test suite on push
