"""API-Football (v3) client with SQLite cache and FastAPI router.

Mounted at /apifootball by app.py.

Endpoints:
  GET /apifootball/leagues          — curated league list + available seasons
  GET /apifootball/fixtures         — finished fixtures for league+season
  GET /apifootball/fixture-stats    — aggregated stats for a single fixture
"""
import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_API_BASE = "https://v3.football.api-sports.io"
_CACHE_DB = Path(__file__).parent / "af_cache.db"
_FIXTURES_TTL_H = 24    # finished fixtures; conservative (they don't change)
_STATS_TTL_H = 720      # per-fixture stats: 30 days (result is final after FT)

# Curated leagues — static list avoids a costly /leagues call (saves quota)
_LEAGUES = [
    {"league_id": 39,  "name": "Premier League",         "country": "England"},
    {"league_id": 140, "name": "La Liga",                 "country": "Spain"},
    {"league_id": 135, "name": "Serie A",                 "country": "Italy"},
    {"league_id": 78,  "name": "Bundesliga",              "country": "Germany"},
    {"league_id": 61,  "name": "Ligue 1",                 "country": "France"},
    {"league_id": 71,  "name": "Brasileirão Série A",     "country": "Brazil"},
    {"league_id": 72,  "name": "Brasileirão Série B",     "country": "Brazil"},
    {"league_id": 73,  "name": "Copa do Brasil",          "country": "Brazil"},
    {"league_id": 2,   "name": "UEFA Champions League",   "country": "World"},
    {"league_id": 3,   "name": "UEFA Europa League",      "country": "World"},
    {"league_id": 1,   "name": "FIFA World Cup",          "country": "World"},
    {"league_id": 13,  "name": "Copa Libertadores",       "country": "South America"},
]

_CURRENT_YEAR = datetime.utcnow().year
_SEASONS = list(range(_CURRENT_YEAR, 2019, -1))  # [2025, 2024, ... 2020]

# Stats to expose — (api_type_key, human_label, unit or None)
_STAT_KEYS: list[tuple[str, str, str | None]] = [
    ("Ball Possession",    "Posse de Bola",         "%"),
    ("Total Shots",        "Finalizações",           None),
    ("Shots on Goal",      "Chutes no Gol",          None),
    ("Shots off Goal",     "Chutes Fora",            None),
    ("Corner Kicks",       "Escanteios",             None),
    ("Fouls",              "Faltas",                 None),
    ("Yellow Cards",       "Cartões Amarelos",       None),
    ("Red Cards",          "Cartões Vermelhos",      None),
    ("Goalkeeper Saves",   "Defesas do Goleiro",     None),
    ("Total passes",       "Passes Totais",          None),
    ("Passes %",           "Precisão de Passes",     "%"),
    ("expected_goals",     "xG (Gols Esperados)",    None),
]

router = APIRouter(prefix="/apifootball", tags=["apifootball"])

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _init_cache() -> None:
    _CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_CACHE_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS af_cache (
            key   TEXT PRIMARY KEY,
            data  TEXT NOT NULL,
            ts    TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def _cache_get(key: str, ttl_h: int) -> Any | None:
    _init_cache()
    conn = sqlite3.connect(_CACHE_DB)
    row = conn.execute("SELECT data, ts FROM af_cache WHERE key=?", (key,)).fetchone()
    conn.close()
    if not row:
        return None
    data, ts = row
    try:
        if datetime.utcnow() - datetime.fromisoformat(ts) > timedelta(hours=ttl_h):
            return None
    except Exception:
        return None
    return json.loads(data)


def _cache_set(key: str, data: Any) -> None:
    _init_cache()
    conn = sqlite3.connect(_CACHE_DB)
    conn.execute(
        "INSERT OR REPLACE INTO af_cache (key, data, ts) VALUES (?, ?, ?)",
        (key, json.dumps(data), datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# API-Football HTTP helpers
# ---------------------------------------------------------------------------

def _api_headers() -> dict[str, str]:
    key = os.getenv("API_FOOTBALL_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="API_FOOTBALL_KEY not configured on this server")
    return {"x-apisports-key": key}


def _api_get(path: str, params: dict[str, Any]) -> list:
    """Call API-Football v3 and return the response list."""
    try:
        resp = httpx.get(
            f"{_API_BASE}/{path}",
            params=params,
            headers=_api_headers(),
            timeout=15.0,
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="API-Football request timed out")

    if resp.status_code == 429:
        raise HTTPException(
            status_code=429,
            detail="API-Football daily quota exceeded — try again tomorrow or use cached data",
        )
    if not resp.is_success:
        raise HTTPException(status_code=502, detail=f"API-Football returned HTTP {resp.status_code}")

    body = resp.json()
    errors = body.get("errors")
    if errors and errors not in ({}, []):
        raise HTTPException(status_code=502, detail=f"API-Football error: {errors}")

    return body.get("response", [])


# ---------------------------------------------------------------------------
# Stat value parser
# ---------------------------------------------------------------------------

def _parse_val(raw: Any) -> float | int | str | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return raw
    if isinstance(raw, str):
        stripped = raw.strip()
        if "%" in stripped:
            try:
                return float(stripped.replace("%", "").strip())
            except ValueError:
                return stripped
        try:
            return int(stripped)
        except ValueError:
            pass
        try:
            return float(stripped)
        except ValueError:
            return stripped or None
    return raw


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/leagues")
def list_leagues():
    """Curated list of popular leagues with selectable seasons."""
    return {"leagues": [{**lg, "seasons": _SEASONS} for lg in _LEAGUES]}


@router.get("/fixtures")
def list_fixtures(
    league_id: int = Query(..., description="API-Football league id"),
    season: int = Query(..., description="Season year, e.g. 2023"),
):
    """List finished fixtures for a league + season, sorted newest-first."""
    key = f"fixtures:{league_id}:{season}"
    cached = _cache_get(key, _FIXTURES_TTL_H)
    if cached is not None:
        return {"fixtures": cached, "source": "cache"}

    raw = _api_get("fixtures", {"league": league_id, "season": season, "status": "FT"})

    fixtures = []
    for fx in raw:
        fid = int(fx["fixture"]["id"])
        home = fx["teams"]["home"]["name"]
        away = fx["teams"]["away"]["name"]
        hs = fx["goals"]["home"]
        as_ = fx["goals"]["away"]
        date_raw: str = fx["fixture"]["date"] or ""
        date = date_raw[:10]
        score = f"{hs}-{as_}" if hs is not None and as_ is not None else "?-?"
        fixtures.append({
            "fixture_id": fid,
            "label": f"{home} {score} {away} ({date})",
            "home_team": home,
            "away_team": away,
            "home_score": hs,
            "away_score": as_,
            "date": date,
        })

    fixtures.sort(key=lambda f: f["date"], reverse=True)
    _cache_set(key, fixtures)
    return {"fixtures": fixtures, "source": "api"}


@router.get("/fixture-stats")
def fixture_stats(fixture_id: int = Query(..., description="API-Football fixture id")):
    """Aggregated stats for a single finished fixture."""
    key = f"stats:{fixture_id}"
    cached = _cache_get(key, _STATS_TTL_H)
    if cached is not None:
        return {**cached, "source": "cache"}

    raw = _api_get("fixtures/statistics", {"fixture": fixture_id})
    if not raw or len(raw) < 2:
        raise HTTPException(status_code=404, detail="No statistics available for this fixture")

    team_names: list[str] = []
    team_stats: dict[str, dict[str, Any]] = {}
    for entry in raw[:2]:  # always home then away
        name: str = entry["team"]["name"]
        team_names.append(name)
        team_stats[name] = {item["type"]: item["value"] for item in entry.get("statistics", [])}

    home_name, away_name = team_names[0], team_names[1]
    home_s, away_s = team_stats[home_name], team_stats[away_name]

    stats: list[dict[str, Any]] = []
    for api_key, label, unit in _STAT_KEYS:
        hv = _parse_val(home_s.get(api_key))
        av = _parse_val(away_s.get(api_key))
        if hv is None and av is None:
            continue  # omit fields the API doesn't return (e.g. xG on free tier)
        stats.append({"stat": label, "home": hv, "away": av, "unit": unit})

    result = {
        "fixture_id": fixture_id,
        "home_team": home_name,
        "away_team": away_name,
        "stats": stats,
    }
    _cache_set(key, result)
    return {**result, "source": "api"}
