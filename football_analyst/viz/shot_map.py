"""
shot_map.py — plot every shot in a match.

WHAT YOU LEARN HERE
    xG (expected goals): the probability a shot becomes a goal, from 0 to 1,
    based on factors like distance and angle. A tap-in might be 0.7 xG; a
    speculative 30-yarder 0.03. Summing a team's xG tells you how many goals
    they "should" have scored — a much better signal than shots alone.

THE CHART
    One pitch, both teams shooting toward the same goal (we mirror one team so
    you can compare them head-to-head). Each marker is one shot:
        - size  = xG (bigger = better chance)
        - a star = goal, a circle = no goal
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from mplsoccer import VerticalPitch

from ..data import StatsBomb, split_xy


def get_shots(match_id: int, db: StatsBomb | None = None) -> pd.DataFrame:
    """Return a tidy shots table for one match.

    Columns: team, player, minute, x, y, xg, outcome, is_goal.
    Separated from the plotting so you can also use it for tables/analysis.
    """
    db = db or StatsBomb()
    ev = db.events(match_id)

    shots = ev[ev["type"] == "Shot"].copy()
    shots = split_xy(shots, "location")  # -> x, y columns
    shots["xg"] = shots["shot_statsbomb_xg"].astype(float)
    shots["outcome"] = shots["shot_outcome"]
    shots["is_goal"] = shots["outcome"] == "Goal"
    return shots[["team", "player", "minute", "x", "y", "xg", "outcome", "is_goal"]]


def shot_map(match_id: int, db: StatsBomb | None = None,
             save_path: str | None = None, show: bool = False):
    """Draw a two-team shot map for a match and return the matplotlib Figure.

    Args:
        match_id:  StatsBomb match id (e.g. 8658 = 2018 World Cup final).
        db:        optional shared StatsBomb instance (reuses the cache).
        save_path: if given, write a PNG there.
        show:      call plt.show() (useful in a notebook).
    """
    db = db or StatsBomb()
    shots = get_shots(match_id, db)
    teams = shots["team"].dropna().unique().tolist()

    # Two stacked half-pitches, one per team, attacking upward.
    pitch = VerticalPitch(pitch_type="statsbomb", half=True,
                          pitch_color="#0d1117", line_color="#3d4452", linewidth=1)
    fig, axes = pitch.draw(nrows=1, ncols=2, figsize=(13, 8))
    fig.set_facecolor("#0d1117")

    for ax, team in zip(axes, teams):
        tshots = shots[shots["team"] == team]
        goals = tshots[tshots["is_goal"]]
        misses = tshots[~tshots["is_goal"]]

        # Marker size scales with xG. *900 keeps the biggest chances readable.
        pitch.scatter(misses["x"], misses["y"], s=misses["xg"] * 900 + 40,
                      ax=ax, edgecolors="#c9d1d9", c="#30557a",
                      alpha=0.8, zorder=2)
        pitch.scatter(goals["x"], goals["y"], s=goals["xg"] * 900 + 60,
                      ax=ax, marker="*", edgecolors="black", c="#f2c14e",
                      linewidths=0.8, zorder=3)

        total_xg = tshots["xg"].sum()
        n_goals = int(tshots["is_goal"].sum())
        ax.set_title(f"{team}\n{len(tshots)} shots · {total_xg:.2f} xG · {n_goals} goals",
                     color="#c9d1d9", fontsize=13, pad=8)

    fig.suptitle("Shot map — marker size = xG · ★ = goal",
                 color="#f0f6fc", fontsize=15, y=0.98)

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    if show:
        plt.show()
    return fig
