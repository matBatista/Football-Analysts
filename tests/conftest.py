"""Shared pytest fixtures for Football Analyst test suite."""

import pandas as pd
import pytest


@pytest.fixture
def events():
    """Minimal StatsBomb-shaped DataFrame covering two synthetic possessions.

    Possession 1: Team A builds (Midfielder → Winger key-pass → Striker shot xG=0.35)
    Possession 2: Team B passes, Team A intercepts high up the pitch.

    Pitch coordinates follow the StatsBomb 120×80 convention (x: 0→120 attacking).
    """
    return pd.DataFrame([
        # ── possession 1: A builds and shoots ───────────────────────────────
        {"type": "Pass",        "team": "A", "player": "Midfielder",
         "possession": 1, "location": [60, 40],
         "pass_shot_assist": False, "shot_statsbomb_xg": None},
        {"type": "Pass",        "team": "A", "player": "Winger",
         "possession": 1, "location": [95, 30],
         "pass_shot_assist": True,  "shot_statsbomb_xg": None},
        {"type": "Shot",        "team": "A", "player": "Striker",
         "possession": 1, "location": [110, 40],
         "pass_shot_assist": False, "shot_statsbomb_xg": 0.35},
        # ── possession 2: B passes, A presses and intercepts ─────────────────
        {"type": "Pass",        "team": "B", "player": "CB",
         "possession": 2, "location": [70, 40],
         "pass_shot_assist": False, "shot_statsbomb_xg": None},
        {"type": "Pass",        "team": "B", "player": "FB",
         "possession": 2, "location": [85, 20],
         "pass_shot_assist": False, "shot_statsbomb_xg": None},
        {"type": "Interception","team": "A", "player": "DM",
         "possession": 2, "location": [90, 35],
         "pass_shot_assist": False, "shot_statsbomb_xg": None},
    ])


@pytest.fixture
def empty_events():
    """Empty DataFrame with the standard event columns."""
    return pd.DataFrame(columns=[
        "type", "team", "player", "possession",
        "location", "pass_shot_assist", "shot_statsbomb_xg",
    ])
