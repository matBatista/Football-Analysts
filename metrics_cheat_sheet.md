# ⚽ Football Metrics Cheat Sheet

**Milestone 1** of the Football Analysts system. This is your reference for the core metrics every analyst talks about: what each one means, the formula, how to read it, and the Python function that computes it.

Everything here is implemented in `football_metrics.py`. Import it and call the functions on your match data:

```python
import pandas as pd
import football_metrics as fm

events = pd.read_json("match_events.json")   # StatsBomb-style event data
fm.expected_goals(events, team="Arsenal")
```

---

## How the data is shaped

The library works with two kinds of data, because that's what you'll actually run into:

**1. Event data (StatsBomb-style)** — one row per on-ball action. The pitch is **120 long × 80 wide** (x runs goal-to-goal toward the attack, y is the width). Key columns: `type`, `team`, `player`, `location` `[x, y]`, `possession`, `shot_statsbomb_xg`, `pass_shot_assist`. This is the format of the free StatsBomb open data.

**2. Aggregate / season data (FBref-style)** — plain totals you already have (goals, assists, xG, minutes). The per-90 and ratio helpers take these as simple numbers.

---

## 1. Core metrics

These are the foundation — the numbers you'll quote in almost every conversation.

### xG — Expected Goals

The single most important metric. Every shot is given a value between 0 and 1 for how likely an *average* player would be to score it, based on distance, angle, body part, defenders, and so on. Sum them up and you get how many goals a team or player "should" have scored.

- **Formula:** total xG = sum of the xG value on every shot taken.
- **How to read it:** A team with 2.4 xG created chances worth roughly 2–3 goals. Compare it to actual goals to judge finishing or luck. Over a season, xG predicts future results better than past goals do.
- **Function:** `fm.expected_goals(events, team="Arsenal")`

### xA — Expected Assists

The passing version of xG. A pass that sets up a shot is credited with the xG of that shot. It rewards creating good chances, even when the teammate misses.

- **Formula:** xA = sum of the xG of the shots that a player's passes created.
- **How to read it:** A playmaker with high xA but low actual assists is creating great chances that teammates are wasting — the creation is real, the finishing isn't.
- **Function:** `fm.expected_assists(events, team="Arsenal")`

### Possession %

The share of the ball a team has. The library uses share of completed passes as a light, data-friendly proxy.

- **Formula:** team passes / all passes × 100.
- **How to read it:** High possession isn't automatically good — some elite teams sit at 40% and counter-attack lethally. Read it alongside field tilt and xG, not on its own.
- **Function:** `fm.possession_pct(events, "Arsenal")`

### Shot accuracy %

How many shots are on target.

- **Formula:** shots on target / total shots × 100.
- **How to read it:** Useful, but volume and shot *quality* (xG per shot) matter more. A team can be very accurate while taking only low-value shots.
- **Function:** `fm.shot_accuracy(shots_on_target, total_shots)`

### Pass completion %

The share of attempted passes that find a teammate.

- **Formula:** completed / attempted × 100.
- **How to read it:** Very high numbers (90%+) can mean control — or safe, sideways passing that never threatens. Context matters: a 78% completion from a team that plays risky forward passes can be more valuable than 92% from sideways passing.
- **Function:** `fm.pass_completion(passes_completed, passes_attempted)`

---

## 2. Pressing & defensive metrics

These describe how a team behaves *without* the ball.

### PPDA — Passes Per Defensive Action

The standard measure of pressing intensity: how many passes you let the opponent make before you try to win the ball back, measured in the attacking ~60% of the pitch.

- **Formula:** opposition passes / your defensive actions (tackles + interceptions + challenges + fouls), counted in the press zone.
- **How to read it:** **Lower = more aggressive pressing.** A PPDA around 8–10 is intense, high-press football (think Liverpool/Man City at their peak). Around 15+ means a passive team that sits back. *This is the one metric where a low number is the impressive one.*
- **Function:** `fm.ppda(events, defending_team="Arsenal", attacking_team="Chelsea")`

### Defensive actions

The raw count of tackles, interceptions, challenges, and fouls.

- **How to read it:** A high count can mean an active defense — or a team constantly chasing the ball because they can't keep it. Always pair with possession.
- **Function:** `fm.defensive_actions(events, "Arsenal")`

### High turnovers

Ball recoveries won high up the pitch (attacking third). A signature of aggressive pressing teams that try to win the ball near the opponent's goal.

- **How to read it:** More high turnovers = more chances to attack a disorganized defense. Strongly linked to high-pressing identities.
- **Function:** `fm.high_turnovers(events, "Arsenal")`

### Field tilt %

Territorial dominance: a team's share of touches in the **final third**. It answers "who is camped in the dangerous areas?" better than possession does.

- **Formula:** team's final-third touches / all final-third touches × 100.
- **How to read it:** A team can have 50% possession but 70% field tilt — that means they're doing their passing where it actually hurts. A great companion to possession %.
- **Function:** `fm.field_tilt(events, "Arsenal")`

---

## 3. Attacking & creation metrics

These find the players who make attacks happen — including the ones who don't show up on the scoresheet.

### Key passes

Passes that directly lead to a shot.

- **How to read it:** A simple, reliable creativity count. A winger with 4+ key passes a game is a genuine chance-creation engine.
- **Function:** `fm.key_passes(events, player="Saka")`

### Shot-Creating Actions (SCA)

The offensive actions that lead directly to a shot (passes, dribbles, drawn fouls). The library uses a simplified version; swap in the full two-action rule when you have fully ordered event sequences.

- **How to read it:** Broader than key passes — it captures dribbles and other actions, not just passes. Good for spotting all-round creators.
- **Function:** `fm.shot_creating_actions(events, "Saka")`

### xGChain

Sum of the xG of **every possession a player was involved in**, whether they shot, assisted, or just kept the move alive. This is how you credit the deep-lying playmaker who starts attacks but never touches the final ball.

- **How to read it:** High xGChain from a midfielder who has low goals + assists tells you they're the "invisible builder" of the attack. It surfaces contribution that traditional stats miss entirely.
- **Function:** `fm.xg_chain(events, "Ødegaard")`

---

## 4. Per-90 & ratio metrics

These make players and teams **comparable** regardless of minutes played or sample size.

### Per-90

Any counting stat normalized to a 90-minute rate, so a substitute and a starter can be compared fairly.

- **Formula:** stat / minutes × 90.
- **How to read it:** A striker with 6 goals in 400 minutes (1.35/90) is hotter than one with 10 in 900 (1.0/90). Always prefer per-90 when comparing different playing times — but watch small samples, where a few games can distort the rate.
- **Function:** `fm.per_90(total, minutes)`

### G − xG (finishing)

Goals minus expected goals — the cleanest read on finishing.

- **How to read it:** **Positive** = scoring more than the chances were worth (clinical finisher, hot streak, or luck). **Negative** = wasting good chances. Over a big sample, elite finishers stay positive; over a few games, it's mostly noise.
- **Function:** `fm.goals_minus_xg(goals, xg)`

### Goal difference per 90

Team goal difference normalized per 90 — a quick form/quality proxy.

- **Function:** `fm.goal_difference_per_90(goals_for, goals_against, minutes)`

### Buildup ratio

xGBuildup ÷ xGChain — tells you *where* in the attack a player contributes.

- **How to read it:** **High ratio** = contributes mostly in early buildup (a controller / deep creator). **Low ratio** = contributes near the shot (a finisher). It's how dashboards classify player archetypes.
- **Function:** `fm.buildup_ratio(xg_buildup, xg_chain_value)`

---

## 5. Expected Threat (xT)

xT asks a simpler question than xG: *how much does moving the ball from zone A to zone B increase the probability of scoring?* It assigns every pitch cell a threat value, then credits passes and carries with the difference between destination and origin.

### How the grid works

The pitch is divided into a **12 × 8 grid** (12 along the length, 8 across the width). Each cell holds the empirical probability that a possession starting there leads to a goal. Values are low near the own goal (~0.006) and rise steeply in the penalty area (~0.41).

The values used here are Karun Singh's published grid (2019):
> "Having the ball near the opponent's goal is inherently more dangerous — xT quantifies exactly *how much* more dangerous."

```
     own half →→→→→→→→→→→→ attacking goal
low  0.006  0.008  0.012  …  0.131  0.269  high   (bottom/top rows)
     0.008  0.010  0.014  …  0.224  0.414         (central rows, most dangerous)
```

### xT added by an action

For a pass or carry:

```
xT_added = xT(destination) − xT(origin)
```

Positive = the player moved the ball into a more dangerous zone (forward pass, progressive carry). Negative = moved it backward. Summed over a match, this tells you which players drove the attack.

### How to read it

- **High xT added** = a player who consistently moves the ball into dangerous areas — often midfielders and wide forwards who don't show up on the scoresheet.
- **Team xT total** reflects *ball progression*, not finishing quality. A team can have higher xT but lose if they're inefficient in front of goal (Croatia had 19.9 vs France's 9.4 in the 2018 WC Final, yet France won 4-2).
- **xT per action** (total ÷ actions) measures *efficiency* of ball progression.

### Functions

```python
# Single location → threat value
fm.location_to_xt(x=115, y=34)           # → 0.4143  (six-yard box)
fm.location_to_xt(x=60,  y=40)           # → 0.0307  (pitch centre)

# Per-action xT delta for every pass and carry in a match
enriched = fm.xt_added(events)            # DataFrame with 'xt_added' column
enriched = fm.xt_added(events, team="France")

# Aggregated by player (positive contributions only, sorted desc)
leaderboard = fm.xt_by_player(events)
leaderboard = fm.xt_by_player(events, team="France")
```

### 2018 World Cup Final — top xT contributors

```
Rank  Player                  xT Added
1     Ivan Rakitić              3.712   ← Croatia's midfield engine
2     Luka Modrić               3.321
3     Ivan Perišić              2.900
4     Šime Vrsaljko             2.438
5     Kylian Mbappé Lottin      1.611   ← France's top mover
6     Marcelo Brozović          1.466
11    Paul Pogba                1.120
13    Antoine Griezmann         0.950
```

Run `python examples/run_xt.py` to reproduce this table from the offline cache.

---

## Quick reference table

| Metric | What it tells you | Good direction | Function |
|---|---|---|---|
| xG | Quality of chances created | Higher | `expected_goals` |
| xA | Quality of chances set up | Higher | `expected_assists` |
| Possession % | Share of the ball | Context | `possession_pct` |
| Shot accuracy % | Shots on target | Higher | `shot_accuracy` |
| Pass completion % | Passing reliability | Context | `pass_completion` |
| PPDA | Pressing intensity | **Lower** | `ppda` |
| Defensive actions | Defensive volume | Context | `defensive_actions` |
| High turnovers | Ball wins near opp. goal | Higher | `high_turnovers` |
| Field tilt % | Territorial dominance | Higher | `field_tilt` |
| Key passes | Chances created (passes) | Higher | `key_passes` |
| SCA | Chances created (all actions) | Higher | `shot_creating_actions` |
| xGChain | Involvement in scoring moves | Higher | `xg_chain` |
| Per-90 | Fair comparison by minutes | — | `per_90` |
| G − xG | Finishing over/under-perform | Positive | `goals_minus_xg` |
| Buildup ratio | Builder vs. finisher | — | `buildup_ratio` |
| xT (location) | Threat value of a zone | Higher | `location_to_xt` |
| xT added | Threat gained by an action | Higher | `xt_added` |
| xT by player | Ball-progression ranking | Higher | `xt_by_player` |

---

## Try it

Run the built-in demo to see every metric computed on a tiny sample dataset:

```bash
python3 football_metrics.py
```

When you have real data, point the functions at a StatsBomb open-data match file (or your own CSV with the same column names) and the same calls work unchanged.

---

### Sources

- [PPDA explained — Premier League](https://www.premierleague.com/en/news/4250153/passes-per-defensive-action-explained)
- [PPDA — Hudl / StatsBomb glossary](https://support.hudl.com/s/article/passes-defensive-action)
- [Introducing xGChain and xGBuildup — StatsBomb](https://statsbomb.com/articles/soccer/introducing-xgchain-and-xgbuildup/)
- [Analyze Field Tilt — Hudl / StatsBomb](https://support.hudl.com/s/article/analyze-field-tilt-statsbomb)
- [StatsBomb open data (GitHub)](https://github.com/statsbomb/open-data)
