"""Thin FastAPI wrapper exposing the Football Analyst library as HTTP endpoints.

Each viz function returns a matplotlib Figure; we render it to PNG and stream it.
Part of the BulkFoot gateway (the "Analyze" section).
"""
import io
import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import football_analyst as fa
from football_analyst.data import StatsBomb

app = FastAPI(title="Football Analyst API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_db = StatsBomb()


def _to_png(result):
    """Accept a Figure, (fig, ax) tuple, or an Axes and return PNG bytes."""
    fig = None
    if isinstance(result, tuple):
        result = result[0]
    if hasattr(result, "savefig"):          # Figure
        fig = result
    elif hasattr(result, "figure"):         # Axes
        fig = result.figure
    if fig is None:
        fig = plt.gcf()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


@app.get("/health")
def health():
    return {"status": "ok", "service": "analyst-api"}


# ---------------------------------------------------------------------------
# Metadata endpoints — feed the cascading pickers in the UI
# ---------------------------------------------------------------------------

@app.get("/competitions")
def list_competitions():
    """Return all competitions grouped by competition, each with their seasons."""
    try:
        df = _db.competitions()
        grouped: dict[int, dict] = {}
        for _, row in df.iterrows():
            cid = int(row["competition_id"])
            if cid not in grouped:
                grouped[cid] = {
                    "competition_id": cid,
                    "competition_name": str(row["competition_name"]),
                    "country_name": str(row.get("country_name", "")),
                    "seasons": [],
                }
            grouped[cid]["seasons"].append({
                "season_id": int(row["season_id"]),
                "season_name": str(row["season_name"]),
            })
        # Sort each competition's seasons newest-first by name (lexicographic works for YYYY/YYYY)
        for c in grouped.values():
            c["seasons"].sort(key=lambda s: s["season_name"], reverse=True)
        result = sorted(grouped.values(), key=lambda c: c["competition_name"])
        return {"competitions": result}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/matches")
def list_matches(competition_id: int, season_id: int):
    """Return all matches for a competition+season with human-readable labels."""
    try:
        df = _db.matches(competition_id, season_id)
        records = []
        for _, row in df.iterrows():
            mid = int(row["match_id"])
            # statsbombpy flattens home_team/away_team dicts to team-name strings
            home = str(row["home_team"])
            away = str(row["away_team"])
            date = str(row.get("match_date", ""))
            hs = row.get("home_score")
            as_ = row.get("away_score")
            score = (
                f"{int(hs)}-{int(as_)}"
                if pd.notna(hs) and pd.notna(as_)
                else ""
            )
            label = f"{home} {score} {away} ({date})" if score else f"{home} x {away} ({date})"
            records.append({
                "match_id": mid,
                "label": label,
                "home_team": home,
                "away_team": away,
                "match_date": date,
            })
        records.sort(key=lambda r: r["match_date"], reverse=True)
        return {"matches": records}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/lineups")
def list_lineups(match_id: int):
    """Return teams and player names for a match (from the StatsBomb lineup cache)."""
    try:
        raw = _db.lineups(match_id)
        players_by_team: dict[str, list[str]] = {}
        for team_name, df in raw.items():
            col = "player_name" if "player_name" in df.columns else df.columns[0]
            players_by_team[str(team_name)] = sorted(df[col].dropna().tolist())
        return {"teams": list(players_by_team.keys()), "players": players_by_team}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Visualization endpoints — return PNG images
# ---------------------------------------------------------------------------

@app.get("/shot-map")
def shot_map(match_id: int = Query(..., description="StatsBomb match id")):
    try:
        return StreamingResponse(_to_png(fa.shot_map(match_id, db=_db)), media_type="image/png")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/pass-map")
def pass_map(match_id: int, player: str | None = None, team: str | None = None):
    if not player and not team:
        raise HTTPException(status_code=400, detail="Provide 'player' or 'team'")
    try:
        return StreamingResponse(
            _to_png(fa.pass_map(match_id, player=player, team=team, db=_db)),
            media_type="image/png",
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/radar")
def radar(
    player_a: str,
    player_b: str,
    match_ids: str = Query(..., description="comma-separated match ids"),
):
    try:
        ids = [int(x) for x in match_ids.split(",") if x.strip()]
        return StreamingResponse(
            _to_png(fa.player_radar(player_a, player_b, ids, db=_db)),
            media_type="image/png",
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))
