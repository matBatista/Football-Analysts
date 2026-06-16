"""
data.py — the data layer of the Football Analyst system.

This is the only module that knows *where* football data comes from. Everything
else (shot maps, pass maps, radars) just asks this module for tidy pandas
DataFrames and never touches the internet directly. Keeping I/O in one place is a
core software-engineering habit: if the data source ever changes, you fix it here
once instead of in ten plotting scripts.

Data source: StatsBomb Open Data (free), accessed through the `statsbombpy`
library — the standard starting point for football analytics.

KEY IDEA — cache-first loading:
    We hand statsbombpy a custom downloader. Before any HTTP request, that
    downloader checks `sb_cache/` for a local copy. If it's there we read the
    file (instant, works offline). If not, we download once and *save it* so the
    next run is free. This is why the exact same code runs on your laptop
    (online) and in a restricted/offline environment — and why repeated runs
    don't hammer StatsBomb's servers.

    Because we let statsbombpy do its own JSON->DataFrame conversion, the
    DataFrames you get offline are identical to the online ones. No schema drift.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from statsbombpy import sb, public

# Keep a handle to statsbombpy's real network downloader so we can fall back to
# it when a file isn't cached yet.
_ORIGINAL_GET_RESPONSE = public.get_response


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE_DIR = _PROJECT_ROOT / "sb_cache"


def _relative_data_path(url: str) -> str:
    """Turn a StatsBomb URL into a cache-relative path.

    e.g. ".../data/events/8658.json" -> "events/8658.json"
    The open-data repo and our cache share the same layout under `data/`.
    """
    marker = "/data/"
    return url.split(marker, 1)[1] if marker in url else url.rsplit("/", 1)[-1]


class StatsBomb:
    """Cache-first gateway to StatsBomb Open Data.

    Usage:
        from football_analyst.data import StatsBomb
        db = StatsBomb()
        events  = db.events(8658)     # 2018 World Cup final
        matches = db.matches(43, 3)   # competition 43, season 3 (WC 2018)
    """

    def __init__(self, cache_dir: str | os.PathLike | None = None, save: bool = True):
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.save = save
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # -- the custom downloader handed to statsbombpy ------------------------
    def _loader(self, url: str):
        """Cache-first replacement for statsbombpy's network downloader."""
        rel = _relative_data_path(url)
        local = self.cache_dir / rel

        if local.exists():
            with open(local, "r", encoding="utf-8") as fh:
                return json.load(fh)

        # Not cached -> download via statsbombpy's real fetcher (needs internet).
        data = _ORIGINAL_GET_RESPONSE(url)

        if self.save:
            local.parent.mkdir(parents=True, exist_ok=True)
            with open(local, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
        return data

    def _activate(self):
        """Point statsbombpy at our cache for the duration of a call.

        statsbombpy's public functions call the module-level name
        `get_response`, so swapping it here makes sb.events()/sb.matches()/etc.
        read from our cache transparently.
        """
        public.get_response = self._loader

    # -- public API: tidy DataFrames (identical to online statsbombpy) ------
    def competitions(self) -> pd.DataFrame:
        """All competitions/seasons available in the open data."""
        self._activate()
        return sb.competitions()

    def matches(self, competition_id: int, season_id: int) -> pd.DataFrame:
        """All matches for one competition + season."""
        self._activate()
        return sb.matches(competition_id=competition_id, season_id=season_id)

    def lineups(self, match_id: int) -> dict:
        """Lineups per team: {team_name: DataFrame of players}."""
        self._activate()
        return sb.lineups(match_id=match_id)

    def events(self, match_id: int) -> pd.DataFrame:
        """Every event in a match as one flat DataFrame.

        ~3000 rows per match, one row per action (pass, shot, carry, pressure...).
        Columns the viz modules rely on:
            type, team, player, minute, location ([x, y] list),
            pass_end_location, pass_outcome, shot_statsbomb_xg, shot_outcome.
        """
        self._activate()
        return sb.events(match_id=match_id)


# ---------------------------------------------------------------------------
# Small conveniences so studying is quick.
# ---------------------------------------------------------------------------
def split_xy(df: pd.DataFrame, col: str = "location",
             x: str = "x", y: str = "y") -> pd.DataFrame:
    """Split a [x, y] list column into numeric x/y columns.

    StatsBomb stores positions as a 2-element list. mplsoccer wants separate x/y,
    so almost every plot starts by calling this. Pitch is 120 long x 80 wide.
    """
    out = df.copy()
    xy = out[col].apply(
        lambda v: (v[0], v[1]) if isinstance(v, (list, tuple)) and len(v) >= 2
        else (None, None)
    )
    out[x] = xy.apply(lambda t: t[0])
    out[y] = xy.apply(lambda t: t[1])
    return out


if __name__ == "__main__":
    # Quick smoke test: `python -m football_analyst.data`
    db = StatsBomb()
    ev = db.events(8658)
    print(f"Loaded {len(ev)} events for the 2018 World Cup final.")
    print("Event types:\n", ev["type"].value_counts().head())
