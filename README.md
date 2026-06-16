# Football Analyst

A small, reusable football-analysis toolkit. Three starter projects, one clean
data layer, free data. Built to learn on — every module is heavily commented and
there's a study notebook to experiment in.

Data source: **StatsBomb Open Data** (free) via `statsbombpy`.

## What's inside

| Project | Function | What it teaches |
|---|---|---|
| Shot map + xG | `shot_map(match_id)` | Chance quality — expected goals (xG) |
| Pass map | `pass_map(match_id, player=…/team=…)` | Event filtering, progressive passes |
| Player radar | `player_radar(a, b, match_ids)` | Per-90 normalisation, fair comparison |

## Setup

```bash
pip install -r requirements.txt
```

## Quick start

```python
import football_analyst as fa

db = fa.StatsBomb()          # data gateway (caches to sb_cache/)
MATCH = 8658                 # 2018 World Cup final: France 4-2 Croatia

fa.shot_map(MATCH, show=True)
fa.pass_map(MATCH, player="Antoine Griezmann", show=True)
fa.player_radar("Antoine Griezmann", "Luka Modrić", [MATCH], show=True)
```

Or run the ready-made scripts (they save PNGs to `outputs/`):

```bash
python examples/run_shot_map.py
python examples/run_pass_map.py
python examples/run_radar.py
```

Or open the study notebook:

```bash
jupyter notebook notebooks/01_getting_started.ipynb
```

## Project layout

```
football_analyst/        the system (importable package)
  data.py                StatsBomb gateway — cache-first loading
  viz/shot_map.py        shot map + xG
  viz/pass_map.py        pass map + progressive passes
  viz/radar.py           per-90 metrics + comparison radar
examples/                runnable scripts
notebooks/               study lab
sb_cache/                downloaded data (auto-managed)
outputs/                 generated charts
```

## How the data layer works

`StatsBomb` is cache-first: every fetch checks `sb_cache/` before going online.
First run downloads from StatsBomb and saves it; after that it's instant and
works offline. Because it reuses `statsbombpy`'s own parsing, the DataFrames are
identical online and offline.

```python
db = fa.StatsBomb()
events  = db.events(8658)      # ~3000 rows, one per action
matches = db.matches(43, 3)    # all 2018 World Cup games
lineups = db.lineups(8658)
```

## Finding match ids and player names

```python
db.competitions()                       # what's available
db.matches(43, 3)["match_id"]           # ids for a competition+season
db.events(8658)["player"].unique()      # exact player names (mind the accents)
```

## Notes on the metrics

- **xG** comes straight from StatsBomb (`shot_statsbomb_xg`).
- **Progressive pass**: completed, forward, and moves the ball ≥25% closer to the
  opponent's goal. Definitions vary — the threshold lives in `viz/pass_map.py`.
- **Per-90**: counts ÷ minutes played × 90, so starters and subs compare fairly.
  Minutes are derived from Starting XI + Substitution events.
