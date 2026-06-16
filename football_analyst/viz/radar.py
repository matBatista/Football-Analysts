"""
radar.py — compare two players across several metrics on a radar chart.

WHAT YOU LEARN HERE
    - Per-90 normalisation: you can't compare a starter (90 min) with a sub
      (15 min) on raw totals. So we divide each count by minutes played and
      multiply by 90 -> "per 90 minutes". This is the bedrock of fair player
      comparison in football analytics.
    - Computing minutes from events: a player's minutes come from the Starting
      XI and Substitution events, not a tidy column. We work it out below.
    - Aggregating across matches: stats stabilise over more games, so this works
      on a list of match ids, not just one.

THE CHART
    mplsoccer's Radar: each axis is one metric, two overlaid polygons compare the
    two players. Bigger area on an axis = more of that thing per 90.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from mplsoccer import Radar, grid

from ..data import StatsBomb, split_xy

# Goal centre, reused for the progressive-pass test (see pass_map.py).
_GOAL = np.array([120.0, 40.0])


def _starting_players(ev: pd.DataFrame) -> set[str]:
    """Names in either team's Starting XI (parsed from the tactics dict)."""
    names: set[str] = set()
    for tactics in ev[ev["type"] == "Starting XI"]["tactics"]:
        if isinstance(tactics, dict):
            for slot in tactics.get("lineup", []):
                names.add(slot["player"]["name"])
    return names


def _player_minutes(ev: pd.DataFrame, player: str) -> float:
    """Minutes a player was on the pitch in one match.

    Logic: match length = last event minute. A starter plays from minute 0 until
    they're subbed off (a Substitution event naming them) or the final whistle.
    A substitute plays from the minute they came on until the end.
    """
    match_end = float(ev["minute"].max())
    subs = ev[ev["type"] == "Substitution"]

    came_on = subs[subs["substitution_replacement"] == player]
    went_off = subs[subs["player"] == player]
    off_min = float(went_off["minute"].min()) if len(went_off) else match_end

    if player in _starting_players(ev):
        return max(0.0, off_min - 0.0)
    if len(came_on):
        return max(0.0, off_min - float(came_on["minute"].min()))
    # Appeared in events but not as starter/sub? Assume full match as a fallback.
    return match_end


def player_season_metrics(match_ids, player: str, db: StatsBomb | None = None) -> dict:
    """Aggregate one player's per-90 metrics across a list of matches.

    Returns a dict of metric_name -> per-90 value. Metrics chosen to cover
    attacking output, passing, and defensive work:
        Shots, xG, Passes, Pass %, Progressive passes, Ball recoveries, Pressures.
    """
    if isinstance(match_ids, int):
        match_ids = [match_ids]
    db = db or StatsBomb()

    totals = dict(shots=0.0, xg=0.0, passes=0.0, passes_completed=0.0,
                  progressive=0.0, recoveries=0.0, pressures=0.0, minutes=0.0)

    for mid in match_ids:
        ev = db.events(mid)
        pev = ev[ev["player"] == player]
        if pev.empty:
            continue

        minutes = _player_minutes(ev, player)
        if minutes <= 0:
            continue
        totals["minutes"] += minutes

        shots = pev[pev["type"] == "Shot"]
        totals["shots"] += len(shots)
        if "shot_statsbomb_xg" in shots:
            totals["xg"] += shots["shot_statsbomb_xg"].astype(float).sum()

        passes = pev[pev["type"] == "Pass"].copy()
        totals["passes"] += len(passes)
        if len(passes):
            outcome = passes["pass_outcome"] if "pass_outcome" in passes else pd.Series(np.nan, index=passes.index)
            completed = outcome.isna()
            totals["passes_completed"] += int(completed.sum())

            passes = split_xy(passes, "location")
            passes = split_xy(passes, "pass_end_location", x="end_x", y="end_y")
            sd = np.hypot(_GOAL[0] - passes["x"], _GOAL[1] - passes["y"])
            ed = np.hypot(_GOAL[0] - passes["end_x"], _GOAL[1] - passes["end_y"])
            prog = completed & ((sd - ed) >= 0.25 * sd) & (passes["end_x"] > passes["x"])
            totals["progressive"] += int(prog.sum())

        totals["recoveries"] += int((pev["type"] == "Ball Recovery").sum())
        totals["pressures"] += int((pev["type"] == "Pressure").sum())

    mins = totals["minutes"]
    if mins <= 0:
        raise ValueError(f"No minutes found for {player!r} in the given matches.")

    per90 = lambda v: round(v / mins * 90, 2)
    pass_pct = round(totals["passes_completed"] / totals["passes"] * 100, 1) if totals["passes"] else 0.0
    return {
        "Shots": per90(totals["shots"]),
        "xG": per90(totals["xg"]),
        "Passes": per90(totals["passes"]),
        "Pass %": pass_pct,
        "Prog. passes": per90(totals["progressive"]),
        "Ball recov.": per90(totals["recoveries"]),
        "Pressures": per90(totals["pressures"]),
    }


# Sensible axis ranges so the radar looks reasonable for outfield players.
_RANGES = {
    "Shots": (0, 6), "xG": (0, 1.0), "Passes": (0, 100), "Pass %": (50, 100),
    "Prog. passes": (0, 15), "Ball recov.": (0, 12), "Pressures": (0, 30),
}


def player_radar(player_a: str, player_b: str, match_ids,
                 db: StatsBomb | None = None, save_path: str | None = None,
                 show: bool = False):
    """Draw a comparison radar for two players. Returns the matplotlib Figure."""
    db = db or StatsBomb()
    a = player_season_metrics(match_ids, player_a, db)
    b = player_season_metrics(match_ids, player_b, db)

    params = list(a.keys())
    low = [_RANGES[p][0] for p in params]
    high = [_RANGES[p][1] for p in params]
    vals_a = [a[p] for p in params]
    vals_b = [b[p] for p in params]

    radar = Radar(params, low, high, round_int=[False] * len(params),
                  num_rings=4, ring_width=1, center_circle_radius=1)

    fig, axs = grid(figheight=9, grid_height=0.9, title_height=0.08,
                    endnote_height=0.02, title_space=0, endnote_space=0,
                    grid_key="radar", axis=False)
    fig.set_facecolor("#0d1117")
    ax = axs["radar"]

    radar.setup_axis(ax=ax, facecolor="#0d1117")
    radar.draw_circles(ax=ax, facecolor="#1c2230", edgecolor="#3d4452")
    radar.draw_radar_compare(vals_a, vals_b, ax=ax,
                             kwargs_radar={"facecolor": "#4a9eff", "alpha": 0.55},
                             kwargs_compare={"facecolor": "#f2c14e", "alpha": 0.55})
    radar.draw_range_labels(ax=ax, fontsize=9, color="#7d8590")
    radar.draw_param_labels(ax=ax, fontsize=11, color="#c9d1d9")

    axs["title"].text(0.01, 0.30, player_a, fontsize=18, color="#4a9eff",
                      ha="left", va="center")
    axs["title"].text(0.99, 0.30, player_b, fontsize=18, color="#f2c14e",
                      ha="right", va="center")
    axs["endnote"].text(0.99, 0.5, "per 90 minutes · StatsBomb data", fontsize=9,
                        color="#7d8590", ha="right", va="center")

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    if show:
        plt.show()
    return fig
