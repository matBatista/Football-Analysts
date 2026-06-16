# Football Analyst — Setup & Project Guide

## What this project is

A small, self-contained football analytics toolkit built in Python. It connects to
**StatsBomb Open Data** (free, no credentials required) through a cache-first data
layer and provides three ready-made visualisations:

| Visualisation | Function | Key metric taught |
|---|---|---|
| Shot map + xG | `fa.shot_map(match_id)` | Expected goals — chance quality |
| Pass map | `fa.pass_map(match_id, player=…)` | Event filtering, progressive passes |
| Player radar | `fa.player_radar(a, b, match_ids)` | Per-90 normalisation, fair comparison |

There is also a standalone metrics library (`football_metrics.py`) with 15+
analyst-grade functions (xG, xA, PPDA, field tilt, xGChain, …) and a study
notebook (`notebooks/01_getting_started.ipynb`).

---

## Prerequisites

| Tool | Minimum version | Notes |
|---|---|---|
| Python | **3.10** | `KW_ONLY` in dataclasses is required by mplsoccer ≥ 1.4. Python 3.9 (macOS system default) will fail at import. |
| pip | any recent | Comes with Python |
| Internet | first run only | StatsBomb data is cached in `sb_cache/` after the first download |

### Confirm your Python version

```bash
python3 --version      # must print 3.10 or higher
```

On macOS with Homebrew, the system `/usr/bin/python3` is often 3.9. If so, use the
Homebrew interpreter explicitly:

```bash
/opt/homebrew/bin/python3 --version    # Homebrew Python (3.10+)
```

All commands below assume `python3` resolves to 3.10+. Substitute the full path if needed.

---

## Setup — step by step

### 1. Clone or download the project

```bash
# If you have a git remote set up:
git clone <repo-url> football-analyst
cd football-analyst

# Otherwise, the project folder is already on disk — just open a terminal there.
```

### 2. (Recommended) Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

Run from the project root (the folder that contains `requirements.txt`):

```bash
pip install -r requirements.txt
```

**What gets installed** (confirmed installed versions as of June 2026):

| Package | Minimum in requirements.txt | Confirmed version |
|---|---|---|
| statsbombpy | ≥ 1.11 | 1.19.0 |
| mplsoccer | ≥ 1.2 | 1.6.0 |
| pandas | ≥ 1.5 | 2.3.3 |
| matplotlib | ≥ 3.6 | 3.9.4 |
| numpy | ≥ 1.23 | 2.0.2 |
| jupyter | any | — |

---

## Running the project

All commands are run from the **project root** (the folder containing `requirements.txt`).

### Option A — run the example scripts (save PNGs)

```bash
python3 examples/run_shot_map.py   # → outputs/shot_map.png
python3 examples/run_pass_map.py   # → outputs/pass_map_player.png, pass_map_team.png
python3 examples/run_radar.py      # → outputs/radar.png
```

### Option B — import the package in a Python script or REPL

```python
import football_analyst as fa

db = fa.StatsBomb()          # cache-first data gateway
MATCH = 8658                 # 2018 World Cup final: France 4-2 Croatia

fa.shot_map(MATCH, db=db, show=True)
fa.pass_map(MATCH, player="Antoine Griezmann", db=db, show=True)
fa.player_radar("Antoine Griezmann", "Luka Modrić", [MATCH], db=db, show=True)
```

### Option C — Jupyter notebook (interactive)

```bash
jupyter notebook notebooks/01_getting_started.ipynb
```

The notebook walks through all three visualisations and includes scratch cells to
experiment with different players and matches.

### Metrics library demo

```bash
python3 football_metrics.py
```

Runs a built-in demo on a tiny synthetic dataset and prints all 10 metric values.
No data download required.

### Data layer smoke test

```bash
python3 -m football_analyst.data
```

Loads 2 978 events from the cached 2018 World Cup final and prints event-type counts.

---

## How the cache works

The first time you call any `db.*` method, `statsbombpy` fetches data from GitHub
and `StatsBomb` saves it to `sb_cache/`. Subsequent calls read from disk — instant
and works offline. The cache layout mirrors StatsBomb's open-data repository:

```
sb_cache/
  competitions.json
  events/8658.json
  lineups/8658.json
  matches/43/3.json
```

To pull a new match, just call `db.events(<new_match_id>)` once while online.

---

## Verification status

Commands confirmed working on Python 3.14 (Homebrew) with the versions above:

| Command | Status | Notes |
|---|---|---|
| `pip install -r requirements.txt` | **CONFIRMED** | Installs cleanly |
| `python3 football_metrics.py` | **CONFIRMED** | All 10 metrics print correctly |
| `python3 examples/run_shot_map.py` | **CONFIRMED** | Saves `outputs/shot_map.png` |
| `python3 examples/run_pass_map.py` | **CONFIRMED** | Saves `pass_map_player.png` + `pass_map_team.png` |
| `python3 examples/run_radar.py` | **CONFIRMED** | Saves `outputs/radar.png` |
| `python3 -m football_analyst.data` | **CONFIRMED** | Loads 2978 events from cache |
| `jupyter notebook notebooks/01_getting_started.ipynb` | **PENDING** | Requires a browser/GUI — not verified headlessly |

### Known issue — Python 3.9 (macOS system default)

`mplsoccer ≥ 1.4` uses `dataclasses.KW_ONLY`, which was added in Python 3.10.
Running with the macOS system `python3` (3.9.6) produces:

```
ImportError: cannot import name 'KW_ONLY' from 'dataclasses'
```

**Fix:** use Python 3.10+ (`/opt/homebrew/bin/python3` on macOS with Homebrew, or
any `python3.10` / `python3.11` / … on your PATH).

### Known warning — LibreSSL / urllib3

```
urllib3 v2 only supports OpenSSL 1.1.1+, currently 'LibreSSL 2.8.3'
```

This is a macOS quirk. It does not prevent data download or cache reads.

---

## Finding player names and match IDs

```python
db = fa.StatsBomb()

db.competitions()                       # all competitions available in open data
db.matches(43, 3)["match_id"]          # all match IDs for 2018 World Cup
db.events(8658)["player"].unique()     # exact player names (mind the accents — e.g. "Luka Modrić")
```

---

## Project layout

```
football_analyst/        importable package
  data.py                StatsBomb gateway — cache-first loading
  viz/
    shot_map.py          shot map + xG
    pass_map.py          pass map + progressive passes
    radar.py             per-90 metrics + comparison radar
examples/                ready-to-run scripts
notebooks/               study lab (Jupyter)
sb_cache/                downloaded StatsBomb data (auto-managed)
outputs/                 generated chart PNGs
football_metrics.py      standalone analytics library (15+ metrics)
metrics_cheat_sheet.md   reference doc for every metric
requirements.txt         Python dependencies
```
