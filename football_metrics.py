"""
football_metrics.py
====================

A small, readable library of football (soccer) analytics metrics for the
"Football Analyst" system — Milestone 1: the metrics cheat sheet.

It is built around two common data shapes:

1. EVENT data (StatsBomb-style)
   One row per on-ball event. Key columns used here:
     - type        : event name, e.g. "Pass", "Shot", "Interception", ...
     - team        : team name
     - player      : player name
     - location    : [x, y] on a 120 x 80 pitch (x: 0->120 attacking, y: 0->80)
     - shot_statsbomb_xg : xG value attached to a Shot event
     - pass_shot_assist  : True when a pass directly assists a shot (key pass)
     - pass_goal_assist  : True when a pass directly assists a goal (assist)
     - possession  : possession sequence id (groups events in one possession)
   These names match the StatsBomb open-data spec (pitch is 120 x 80).

2. AGGREGATE / SEASON data (FBref-style season totals)
   Plain numbers you already have per player or per team, e.g. goals,
   assists, xG, minutes. The per-90 and ratio helpers work on these.

Everything is plain pandas + Python so you can read it, change it, and learn
from it. Functions raise clear errors instead of failing silently.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

# StatsBomb pitch dimensions (used for zone-based metrics like field tilt / PPDA)
PITCH_LENGTH = 120.0  # x axis, goal-to-goal
PITCH_WIDTH = 80.0    # y axis

# Defensive-action event types that count toward a press (StatsBomb naming)
DEFENSIVE_ACTIONS = ("Tackle", "Interception", "Challenge", "Foul Committed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _x_from_location(df: pd.DataFrame) -> pd.Series:
    """Extract the x coordinate from a StatsBomb-style 'location' [x, y] column."""
    if "x" in df.columns:
        return pd.to_numeric(df["x"], errors="coerce")
    if "location" in df.columns:
        return df["location"].apply(
            lambda loc: loc[0] if isinstance(loc, (list, tuple)) and len(loc) >= 1 else float("nan")
        )
    raise KeyError("Need either an 'x' column or a 'location' [x, y] column.")


def _require(df: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required column(s): {missing}")


# ===========================================================================
# CORE METRICS
# ===========================================================================
def expected_goals(events: pd.DataFrame, team: str | None = None) -> float:
    """Total xG = sum of the xG value on every shot.

    If `team` is given, only that team's shots are counted.
    """
    _require(events, ["type"])
    shots = events[events["type"] == "Shot"].copy()
    if team is not None:
        _require(shots, ["team"])
        shots = shots[shots["team"] == team]
    xg_col = "shot_statsbomb_xg" if "shot_statsbomb_xg" in shots.columns else "xg"
    _require(shots, [xg_col])
    return float(pd.to_numeric(shots[xg_col], errors="coerce").fillna(0).sum())


def expected_assists(events: pd.DataFrame, team: str | None = None) -> float:
    """Total xA = sum of the xG of the shots that assisting passes created.

    A pass is an "assist to a shot" (key pass) when pass_shot_assist is True.
    We credit that pass with the xG of the shot in the same possession.
    """
    _require(events, ["type", "possession"])
    xg_col = "shot_statsbomb_xg" if "shot_statsbomb_xg" in events.columns else "xg"
    _require(events, [xg_col])

    if "pass_shot_assist" not in events.columns:
        raise KeyError("Need a 'pass_shot_assist' boolean column to compute xA.")

    # xG of each shot, keyed by possession
    shots = events[events["type"] == "Shot"]
    shot_xg_by_poss = (
        pd.to_numeric(shots[xg_col], errors="coerce").groupby(shots["possession"]).sum()
    )

    key_passes = events[(events["type"] == "Pass") & (events["pass_shot_assist"] == True)]  # noqa: E712
    if team is not None:
        _require(key_passes, ["team"])
        key_passes = key_passes[key_passes["team"] == team]

    total = key_passes["possession"].map(shot_xg_by_poss).fillna(0).sum()
    return float(total)


def possession_pct(events: pd.DataFrame, team: str) -> float:
    """Possession % by share of completed passes (a common, data-light proxy).

    = team passes / all passes * 100
    """
    _require(events, ["type", "team"])
    passes = events[events["type"] == "Pass"]
    total = len(passes)
    if total == 0:
        return 0.0
    return round(len(passes[passes["team"] == team]) / total * 100, 1)


def shot_accuracy(shots_on_target: int, total_shots: int) -> float:
    """Shot accuracy % = shots on target / total shots * 100."""
    if total_shots <= 0:
        return 0.0
    return round(shots_on_target / total_shots * 100, 1)


def pass_completion(passes_completed: int, passes_attempted: int) -> float:
    """Pass completion % = completed / attempted * 100."""
    if passes_attempted <= 0:
        return 0.0
    return round(passes_completed / passes_attempted * 100, 1)


# ===========================================================================
# PRESSING / DEFENSIVE METRICS
# ===========================================================================
def ppda(events: pd.DataFrame, defending_team: str, attacking_team: str,
         zone_start: float = 0.4) -> float:
    """PPDA — Passes Per Defensive Action.

    Opposition passes / defensive actions, measured in the ~60% of the pitch
    nearest the opponent's goal (defending team pressing high up).

    A LOW PPDA = intense, high pressing. A HIGH PPDA = passive, sit-back team.

    zone_start: fraction of the pitch from the defending team's own goal where
    the press "zone" begins. 0.4 means we count events in the attacking 60%
    (the StatsBomb convention: opponent's half + first fifth of own half).
    """
    _require(events, ["type", "team"])
    x = _x_from_location(events)
    x_threshold = PITCH_LENGTH * zone_start

    in_zone = x >= x_threshold

    opp_passes = events[(events["team"] == attacking_team)
                        & (events["type"] == "Pass") & in_zone]
    def_actions = events[(events["team"] == defending_team)
                         & (events["type"].isin(DEFENSIVE_ACTIONS)) & in_zone]

    n_actions = len(def_actions)
    if n_actions == 0:
        return float("inf")  # no pressure applied at all
    return round(len(opp_passes) / n_actions, 2)


def defensive_actions(events: pd.DataFrame, team: str) -> int:
    """Count of defensive actions (tackles, interceptions, challenges, fouls)."""
    _require(events, ["type", "team"])
    mask = (events["team"] == team) & (events["type"].isin(DEFENSIVE_ACTIONS))
    return int(mask.sum())


def high_turnovers(events: pd.DataFrame, team: str, high_x: float = 80.0) -> int:
    """Ball recoveries / defensive actions won high up the pitch (x >= high_x).

    Default high_x = 80 on a 120-long pitch = the attacking third.
    A proxy for how often a team wins the ball close to the opponent's goal.
    """
    _require(events, ["type", "team"])
    x = _x_from_location(events)
    recover_types = ("Ball Recovery", "Interception", "Tackle")
    mask = (events["team"] == team) & (events["type"].isin(recover_types)) & (x >= high_x)
    return int(mask.sum())


def field_tilt(events: pd.DataFrame, team: str, final_third_x: float = 80.0) -> float:
    """Field tilt % = a team's share of touches in the final third.

    High field tilt = the team controls play in dangerous areas (territorial
    dominance), regardless of raw possession.
    """
    _require(events, ["team"])
    x = _x_from_location(events)
    in_final_third = x >= final_third_x
    total = int(in_final_third.sum())
    if total == 0:
        return 0.0
    team_touches = int((in_final_third & (events["team"] == team)).sum())
    return round(team_touches / total * 100, 1)


# ===========================================================================
# ATTACKING / CREATION METRICS
# ===========================================================================
def key_passes(events: pd.DataFrame, player: str | None = None,
               team: str | None = None) -> int:
    """Key passes = passes that directly lead to a shot (pass_shot_assist)."""
    _require(events, ["type"])
    if "pass_shot_assist" not in events.columns:
        raise KeyError("Need a 'pass_shot_assist' boolean column.")
    kp = events[(events["type"] == "Pass") & (events["pass_shot_assist"] == True)]  # noqa: E712
    if player is not None:
        _require(kp, ["player"])
        kp = kp[kp["player"] == player]
    if team is not None:
        _require(kp, ["team"])
        kp = kp[kp["team"] == team]
    return int(len(kp))


def shot_creating_actions(events: pd.DataFrame, player: str) -> int:
    """Shot-Creating Actions (SCA) — simplified.

    The two offensive actions directly leading to a shot. Here we credit a
    player for each shot in a possession they touched the ball in, immediately
    before the shot. This is a light approximation of FBref's SCA; swap in the
    full 2-action rule when you have ordered event sequences.
    """
    _require(events, ["type", "player", "possession"])
    shot_possessions = set(events[events["type"] == "Shot"]["possession"])
    touched = events[(events["player"] == player)
                     & (events["possession"].isin(shot_possessions))]
    return int(touched["possession"].nunique())


def xg_chain(events: pd.DataFrame, player: str) -> float:
    """xGChain — sum of xG of every possession the player was involved in.

    Credits players who build attacks, not just those who shoot/assist.
    """
    _require(events, ["type", "player", "possession"])
    xg_col = "shot_statsbomb_xg" if "shot_statsbomb_xg" in events.columns else "xg"
    _require(events, [xg_col])

    shots = events[events["type"] == "Shot"]
    xg_by_poss = pd.to_numeric(shots[xg_col], errors="coerce").groupby(shots["possession"]).sum()

    player_possessions = set(events[events["player"] == player]["possession"])
    return float(xg_by_poss[xg_by_poss.index.isin(player_possessions)].sum())


# ===========================================================================
# PER-90 AND RATIO METRICS
# ===========================================================================
def per_90(total: float, minutes: float) -> float:
    """Normalize any counting stat to a per-90-minutes rate.

    Lets you compare a player who played 300 mins with one who played 3000.
    """
    if minutes <= 0:
        return 0.0
    return round(total / minutes * 90, 2)


def goals_minus_xg(goals: float, xg: float) -> float:
    """G - xG: finishing over/under-performance.

    Positive = scoring more than chances suggest (clinical / hot streak / luck).
    Negative = under-performing the chances created.
    """
    return round(goals - xg, 2)


def goal_difference_per_90(goals_for: float, goals_against: float, minutes: float) -> float:
    """Goal difference normalized per 90 (team-level form proxy)."""
    return per_90(goals_for - goals_against, minutes)


def buildup_ratio(xg_buildup: float, xg_chain_value: float) -> float:
    """Buildup ratio = xGBuildup / xGChain.

    High = a player contributes mostly in early buildup (controller / deep
    creator). Low = a player contributes mostly near the shot (finisher).
    """
    if xg_chain_value <= 0:
        return 0.0
    return round(xg_buildup / xg_chain_value, 2)


# ===========================================================================
# Quick demo when run directly
# ===========================================================================
if __name__ == "__main__":
    # Tiny synthetic possession dataset on a 120 x 80 pitch.
    demo = pd.DataFrame([
        # possession 1: Team A builds and shoots (assisted)
        {"type": "Pass", "team": "A", "player": "Midfielder", "location": [60, 40],
         "possession": 1, "pass_shot_assist": False, "shot_statsbomb_xg": None},
        {"type": "Pass", "team": "A", "player": "Winger", "location": [95, 30],
         "possession": 1, "pass_shot_assist": True, "shot_statsbomb_xg": None},
        {"type": "Shot", "team": "A", "player": "Striker", "location": [110, 40],
         "possession": 1, "pass_shot_assist": False, "shot_statsbomb_xg": 0.35},
        # possession 2: Team B passes in their build-up, A presses
        {"type": "Pass", "team": "B", "player": "CB", "location": [70, 40],
         "possession": 2, "pass_shot_assist": False, "shot_statsbomb_xg": None},
        {"type": "Pass", "team": "B", "player": "FB", "location": [85, 20],
         "possession": 2, "pass_shot_assist": False, "shot_statsbomb_xg": None},
        {"type": "Interception", "team": "A", "player": "DM", "location": [90, 35],
         "possession": 2, "pass_shot_assist": False, "shot_statsbomb_xg": None},
    ])

    print("xG (A):           ", expected_goals(demo, team="A"))
    print("xA (A):           ", expected_assists(demo, team="A"))
    print("Possession % (A): ", possession_pct(demo, "A"))
    print("PPDA (A press B): ", ppda(demo, defending_team="A", attacking_team="B"))
    print("Field tilt (A):   ", field_tilt(demo, "A"))
    print("Key passes (A):   ", key_passes(demo, team="A"))
    print("xGChain Winger:   ", xg_chain(demo, "Winger"))
    print("Per-90 (10 in 720):", per_90(10, 720))
    print("G - xG (8, 6.2):  ", goals_minus_xg(8, 6.2))
    print("Buildup ratio:    ", buildup_ratio(0.6, 1.5))
