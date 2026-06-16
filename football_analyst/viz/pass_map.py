"""
pass_map.py — plot a player's or a team's passes.

WHAT YOU LEARN HERE
    - Event filtering: a match has ~850 passes; you slice to one player/team.
    - Completed vs incomplete: in StatsBomb, an *incomplete* pass has a value in
      `pass_outcome` (e.g. "Incomplete", "Out"). A *completed* pass has no
      outcome (NaN). This trips up everyone once — read the code below.
    - Progressive passes: passes that meaningfully advance the ball toward goal.
      They're a key modern metric for spotting line-breaking, creative players.

THE CHART
    Arrows from start to end of each pass on a full pitch:
        - grey   = completed, non-progressive
        - blue   = progressive (moves ball >= 25% closer to goal)
        - red    = incomplete
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from mplsoccer import Pitch

from ..data import StatsBomb, split_xy

# Opponent goal centre on a StatsBomb pitch (120 long x 80 wide).
_GOAL = np.array([120.0, 40.0])
_PROGRESSIVE_FRACTION = 0.25  # ball must get >=25% closer to goal


def get_passes(match_id: int, player: str | None = None, team: str | None = None,
               db: StatsBomb | None = None) -> pd.DataFrame:
    """Return a tidy passes table, optionally filtered to a player or team.

    Columns: team, player, minute, x, y, end_x, end_y, completed, progressive.
    """
    db = db or StatsBomb()
    ev = db.events(match_id)

    passes = ev[ev["type"] == "Pass"].copy()
    if team:
        passes = passes[passes["team"] == team]
    if player:
        passes = passes[passes["player"] == player]

    # Start location -> x, y ; end location -> end_x, end_y.
    passes = split_xy(passes, "location")
    passes = split_xy(passes, "pass_end_location", x="end_x", y="end_y")

    # KEY GOTCHA: a completed pass has NO pass_outcome (NaN).
    if "pass_outcome" not in passes.columns:
        passes["pass_outcome"] = np.nan
    passes["completed"] = passes["pass_outcome"].isna()

    # Progressive: distance to goal drops by >= 25% (and the pass goes forward).
    start_dist = np.hypot(_GOAL[0] - passes["x"], _GOAL[1] - passes["y"])
    end_dist = np.hypot(_GOAL[0] - passes["end_x"], _GOAL[1] - passes["end_y"])
    passes["progressive"] = (
        passes["completed"]
        & ((start_dist - end_dist) >= _PROGRESSIVE_FRACTION * start_dist)
        & (passes["end_x"] > passes["x"])
    )

    cols = ["team", "player", "minute", "x", "y", "end_x", "end_y",
            "completed", "progressive"]
    return passes[cols]


def pass_map(match_id: int, player: str | None = None, team: str | None = None,
             db: StatsBomb | None = None, save_path: str | None = None,
             show: bool = False):
    """Draw a pass map for a player or team. Returns the matplotlib Figure.

    Provide `player` for an individual, or `team` for a whole side. `player`
    takes precedence for the title.
    """
    if not player and not team:
        raise ValueError("Pass a `player` name or a `team` name to plot.")

    db = db or StatsBomb()
    passes = get_passes(match_id, player=player, team=team, db=db)

    completed = passes[passes["completed"] & ~passes["progressive"]]
    progressive = passes[passes["progressive"]]
    incomplete = passes[~passes["completed"]]

    pitch = Pitch(pitch_type="statsbomb", pitch_color="#0d1117",
                  line_color="#3d4452", linewidth=1)
    fig, ax = pitch.draw(figsize=(12, 8))
    fig.set_facecolor("#0d1117")

    # Arrows: start -> end. comet=True fades the tail so direction is obvious.
    pitch.arrows(incomplete.x, incomplete.y, incomplete.end_x, incomplete.end_y,
                 ax=ax, color="#d9534f", width=1.5, headwidth=5, alpha=0.6, zorder=2)
    pitch.arrows(completed.x, completed.y, completed.end_x, completed.end_y,
                 ax=ax, color="#7d8590", width=1.5, headwidth=5, alpha=0.5, zorder=2)
    pitch.arrows(progressive.x, progressive.y, progressive.end_x, progressive.end_y,
                 ax=ax, color="#4a9eff", width=2, headwidth=6, alpha=0.95, zorder=3)

    subject = player or team
    n = len(passes)
    comp_rate = (passes["completed"].mean() * 100) if n else 0
    ax.set_title(
        f"{subject} — {n} passes · {comp_rate:.0f}% completed · "
        f"{len(progressive)} progressive\n"
        "blue = progressive · grey = completed · red = incomplete",
        color="#c9d1d9", fontsize=13, pad=10,
    )

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    if show:
        plt.show()
    return fig
