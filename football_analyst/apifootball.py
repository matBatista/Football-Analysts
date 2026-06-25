"""
apifootball.py — a richer live data layer backed by API-Football (api-sports.io).

WHY THIS EXISTS
---------------
`worldcup.py` gives you the score and goal timeline of a finished match — useful,
but thin. API-Football adds the next tier of detail for recent tournaments
(including World Cup 2026): full team match statistics (possession, shots, passes,
corners, xG when published) and *per-player* match performances (shots, key
passes, dribbles, tackles, rating...).

That per-player data is enough to build a **real player radar** for the 2026 World
Cup. What it is NOT is event coordinates — there is no (x, y) for each pass/shot —
so shot maps and pass maps still need the StatsBomb layer. This module gets you
"the maximum analysis possible without coordinates".

WHAT YOU NEED
-------------
A free API-Football key. Create one at https://www.api-football.com (or via
RapidAPI) and expose it as an environment variable before running:

    export API_FOOTBALL_KEY="your_key_here"     # macOS/Linux
    setx  API_FOOTBALL_KEY "your_key_here"      # Windows (new terminals)

The free plan is rate-limited (a few hundred requests/day), which is exactly why
this client is **cache-first**: every response is saved under
`sb_cache/apifootball/` and reused, so repeated runs cost zero requests and work
offline.

KEY IDS
-------
World Cup is league id **1** in API-Football. A "season" is the tournament's
starting year, e.g. 2026.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE_DIR = _PROJECT_ROOT / "sb_cache"

API_HOST = "https://v3.football.api-sports.io"
WORLD_CUP_LEAGUE_ID = 1


class APIFootballError(RuntimeError):
    """Raised when the API returns an error or no key is available."""


class APIFootball:
    """Cache-first client for API-Football v3.

    Usage:
        from football_analyst.apifootball import APIFootball
        api = APIFootball()                         # reads API_FOOTBALL_KEY
        fx  = api.fixtures(season=2026)             # all World Cup 2026 matches
        api.match_stats(fixture_id)                 # team stats side by side
        api.player_radar("Vinícius", "Mbappé", fixture_ids)
    """

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: str | os.PathLike | None = None,
        save: bool = True,
        refresh: bool = False,
    ):
        # Key is optional *if* everything you ask for is already cached.
        self.api_key = api_key or os.environ.get("API_FOOTBALL_KEY")
        self.save = save
        self.refresh = refresh
        base = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_dir = base / "apifootball"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # -- the cache-first request core ---------------------------------------
    def _cache_key(self, endpoint: str, params: dict) -> Path:
        """A stable filename from endpoint + sorted params (e.g. fixtures_league-1_season-2026.json)."""
        items = "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
        name = endpoint.replace("/", "-")
        stem = f"{name}_{items}" if items else name
        return self.cache_dir / f"{stem}.json"

    def _get(self, endpoint: str, params: dict) -> list:
        """Return the `response` list for an endpoint, cache-first."""
        cache_file = self._cache_key(endpoint, params)
        if cache_file.exists() and not self.refresh:
            with open(cache_file, "r", encoding="utf-8") as fh:
                return json.load(fh)["response"]

        if not self.api_key:
            raise APIFootballError(
                "No API_FOOTBALL_KEY set and this request isn't cached yet. "
                "Get a free key at https://www.api-football.com and run:\n"
                '    export API_FOOTBALL_KEY="your_key"'
            )

        url = f"{API_HOST}/{endpoint}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"x-apisports-key": self.api_key})
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))

        errors = payload.get("errors")
        if errors:  # API-Football reports quota/auth problems here, not via HTTP codes.
            raise APIFootballError(f"API-Football error: {errors}")

        if self.save:
            with open(cache_file, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
        return payload["response"]

    # -- raw endpoints ------------------------------------------------------
    def fixtures(self, season: int = 2026, league: int = WORLD_CUP_LEAGUE_ID) -> pd.DataFrame:
        """All fixtures for a competition + season as a tidy DataFrame."""
        rows = []
        for f in self._get("fixtures", {"league": league, "season": season}):
            rows.append(
                {
                    "fixture_id": f["fixture"]["id"],
                    "date": f["fixture"]["date"],
                    "status": f["fixture"]["status"]["short"],
                    "round": f["league"].get("round"),
                    "home": f["teams"]["home"]["name"],
                    "away": f["teams"]["away"]["name"],
                    "goals_home": f["goals"]["home"],
                    "goals_away": f["goals"]["away"],
                    "venue": (f["fixture"].get("venue") or {}).get("name"),
                }
            )
        df = pd.DataFrame(rows)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    def statistics(self, fixture_id: int) -> list:
        """Raw per-team statistics blocks for one fixture."""
        return self._get("fixtures/statistics", {"fixture": fixture_id})

    def players(self, fixture_id: int) -> list:
        """Raw per-team player-performance blocks for one fixture."""
        return self._get("fixtures/players", {"fixture": fixture_id})

    def events(self, fixture_id: int) -> list:
        """Raw event list (goals, cards, subs) for one fixture."""
        return self._get("fixtures/events", {"fixture": fixture_id})

    # -- tidy: team match statistics ----------------------------------------
    def match_stats(self, fixture_id: int) -> pd.DataFrame:
        """Team statistics side by side: one row per stat, one column per team.

        Possession/percentage strings like "60%" are converted to floats.
        """
        blocks = self.statistics(fixture_id)
        if not blocks:
            return pd.DataFrame()

        columns = {}
        for block in blocks:
            team = block["team"]["name"]
            col = {}
            for stat in block["statistics"]:
                col[stat["type"]] = _coerce_stat(stat["value"])
            columns[team] = col

        df = pd.DataFrame(columns)
        df.index.name = "statistic"
        return df


    # -- tidy: per-player metrics + radar -----------------------------------
    def player_metrics(self, player: str, fixture_ids) -> dict:
        """Aggregate one player's per-90 metrics across a list of fixtures.

        Matching is case-insensitive and substring-based, so "vinícius" or
        "mbappe" works. Counts are normalised per-90 minutes; rating is a
        minute-weighted average (it's already a 0-10 score, not a count).

        Metrics (all per-90 except rating):
            Shots, Key passes, Passes, Dribbles, Tackles, Interceptions
        """
        if isinstance(fixture_ids, int):
            fixture_ids = [fixture_ids]

        totals = dict(minutes=0.0, shots=0.0, key_passes=0.0, passes=0.0,
                      dribbles=0.0, tackles=0.0, interceptions=0.0, rating_x_min=0.0)
        found = False

        for fid in fixture_ids:
            stat = _find_player_stat(self.players(fid), player)
            if stat is None:
                continue
            minutes = stat.get("games", {}).get("minutes") or 0
            if minutes <= 0:
                continue
            found = True
            totals["minutes"] += minutes
            totals["shots"] += _num((stat.get("shots") or {}).get("total"))
            passes = stat.get("passes") or {}
            totals["key_passes"] += _num(passes.get("key"))
            totals["passes"] += _num(passes.get("total"))
            totals["dribbles"] += _num((stat.get("dribbles") or {}).get("success"))
            tackles = stat.get("tackles") or {}
            totals["tackles"] += _num(tackles.get("total"))
            totals["interceptions"] += _num(tackles.get("interceptions"))
            rating = stat.get("games", {}).get("rating")
            totals["rating_x_min"] += _num(rating) * minutes

        if not found or totals["minutes"] <= 0:
            raise APIFootballError(
                f"No minutes found for {player!r} in the given fixtures "
                "(check the name spelling and that the matches are cached)."
            )

        mins = totals["minutes"]

        def per90(v):
            return round(v / mins * 90, 2)

        return {
            "Shots": per90(totals["shots"]),
            "Key passes": per90(totals["key_passes"]),
            "Passes": per90(totals["passes"]),
            "Dribbles": per90(totals["dribbles"]),
            "Tackles": per90(totals["tackles"]),
            "Interceptions": per90(totals["interceptions"]),
            "_rating": round(totals["rating_x_min"] / mins, 2),
            "_minutes": int(mins),
        }

    def player_radar(self, player_a: str, player_b: str, fixture_ids,
                     save_path: str | None = None, show: bool = False):
        """Draw a comparison radar for two players. Returns the matplotlib Figure."""
        a = self.player_metrics(player_a, fixture_ids)
        b = self.player_metrics(player_b, fixture_ids)
        return draw_player_radar(player_a, a, player_b, b, save_path=save_path, show=show)


# Sensible per-90 axis ranges for outfield players in a tournament.
_RADAR_RANGES = {
    "Shots": (0, 6), "Key passes": (0, 5), "Passes": (0, 100),
    "Dribbles": (0, 8), "Tackles": (0, 8), "Interceptions": (0, 6),
}


def draw_player_radar(name_a, metrics_a, name_b, metrics_b,
                      save_path=None, show=False):
    """Render a two-player radar from metric dicts (keys must match _RADAR_RANGES)."""
    import matplotlib.pyplot as plt
    from mplsoccer import Radar, grid

    params = list(_RADAR_RANGES.keys())
    low = [_RADAR_RANGES[p][0] for p in params]
    high = [_RADAR_RANGES[p][1] for p in params]
    vals_a = [metrics_a[p] for p in params]
    vals_b = [metrics_b[p] for p in params]

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

    ra, rb = metrics_a.get("_rating"), metrics_b.get("_rating")
    axs["title"].text(0.01, 0.30, f"{name_a}  ({ra})", fontsize=18,
                      color="#4a9eff", ha="left", va="center")
    axs["title"].text(0.99, 0.30, f"{name_b}  ({rb})", fontsize=18,
                      color="#f2c14e", ha="right", va="center")
    axs["endnote"].text(0.99, 0.5, "per 90 minutes · API-Football data · (rating in brackets)",
                        fontsize=9, color="#7d8590", ha="right", va="center")

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    if show:
        plt.show()
    return fig


def _num(value) -> float:
    """Best-effort numeric coercion; None/'' -> 0.0."""
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _find_player_stat(team_blocks: list, player: str) -> dict | None:
    """Locate a player's first statistics block across both teams (substring match)."""
    needle = player.lower()
    for block in team_blocks:
        for entry in block.get("players", []):
            name = entry.get("player", {}).get("name", "")
            if needle in name.lower():
                stats = entry.get("statistics") or []
                return stats[0] if stats else None
    return None


def _coerce_stat(value):
    """Turn '60%' -> 60.0, '2.1' -> 2.1, None -> 0, leave ints as ints."""
    if value is None:
        return 0
    if isinstance(value, str):
        v = value.strip().rstrip("%")
        try:
            return float(v) if "." in v else int(v)
        except ValueError:
            return value
    return value


if __name__ == "__main__":
    # Quick smoke test: `python -m football_analyst.apifootball`
    api = APIFootball()
    try:
        fx = api.fixtures(season=2026)
        print(f"World Cup 2026 — {len(fx)} fixtures pulled.")
        print(fx[["date", "home", "away", "status"]].head().to_string(index=False))
    except APIFootballError as e:
        print(e)
