"""Football Analyst — a small, reusable football-analysis toolkit.

Public API:
    from football_analyst import StatsBomb, shot_map, pass_map, player_radar
"""

from .data import StatsBomb, split_xy
from .viz.shot_map import shot_map
from .viz.pass_map import pass_map
from .viz.radar import player_radar, player_season_metrics

__all__ = [
    "StatsBomb",
    "split_xy",
    "shot_map",
    "pass_map",
    "player_radar",
    "player_season_metrics",
]
