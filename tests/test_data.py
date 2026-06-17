"""Tests for the data layer: split_xy helper and StatsBomb cache integration.

Unit tests: split_xy — no I/O, purely deterministic.

Integration tests: marked with @pytest.mark.integration. They read from the
local StatsBomb cache (sb_cache/events/8658.json) and require no network
access — but they will be skipped automatically if the cache file is absent.
The cache ships with the repo for the 2018 World Cup Final (match_id=8658).
"""

from pathlib import Path

import pandas as pd
import pytest

from football_analyst.data import split_xy

# Path used by integration tests to guard against a missing cache.
_CACHE_EVENTS = Path(__file__).resolve().parent.parent / "sb_cache" / "events" / "8658.json"
_cache_available = pytest.mark.skipif(
    not _CACHE_EVENTS.exists(),
    reason="StatsBomb cache for match 8658 not found — run once online to populate.",
)


# ── split_xy ─────────────────────────────────────────────────────────────────

class TestSplitXY:
    def test_basic_split(self):
        df = pd.DataFrame({"location": [[10, 20], [30, 40]]})
        out = split_xy(df)
        assert list(out["x"]) == [10, 30]
        assert list(out["y"]) == [20, 40]

    def test_custom_column_names(self):
        df = pd.DataFrame({"location": [[5, 15]]})
        out = split_xy(df, x="px", y="py")
        assert "px" in out.columns and "py" in out.columns
        assert out["px"].iloc[0] == 5
        assert out["py"].iloc[0] == 15

    def test_custom_source_column(self):
        df = pd.DataFrame({"pass_end_location": [[100, 50]]})
        out = split_xy(df, col="pass_end_location", x="end_x", y="end_y")
        assert out["end_x"].iloc[0] == 100

    def test_does_not_mutate_original(self):
        df = pd.DataFrame({"location": [[10, 20]]})
        _ = split_xy(df)
        assert "x" not in df.columns

    def test_invalid_location_gives_none(self):
        df = pd.DataFrame({"location": [None, [10, 20]]})
        out = split_xy(df)
        assert pd.isna(out["x"].iloc[0])
        assert out["x"].iloc[1] == 10

    def test_scalar_location_gives_none(self):
        # Single value instead of [x, y] list
        df = pd.DataFrame({"location": [42]})
        out = split_xy(df)
        assert pd.isna(out["x"].iloc[0])

    def test_preserves_other_columns(self):
        df = pd.DataFrame({"location": [[10, 20]], "type": ["Pass"], "team": ["A"]})
        out = split_xy(df)
        assert "type" in out.columns and "team" in out.columns


# ── Integration: StatsBomb cache (match 8658, 2018 WC Final) ─────────────────

@pytest.mark.integration
@_cache_available
class TestStatsBombIntegration:
    """Sanity-check that the cached events DataFrame has the expected shape and
    that the metrics functions return plausible values on real match data.

    France 4-2 Croatia (2018 FIFA World Cup Final).
    """

    @pytest.fixture(scope="class")
    @classmethod
    def wc_events(cls):
        from football_analyst.data import StatsBomb
        return StatsBomb().events(8658)

    def test_events_loaded_has_rows(self, wc_events):
        assert len(wc_events) > 1000, "Expected ~3 000 events for a full match."

    def test_events_has_required_columns(self, wc_events):
        for col in ("type", "team", "player", "possession", "location"):
            assert col in wc_events.columns, f"Missing column: {col}"

    def test_france_has_positive_xg(self, wc_events):
        import football_metrics as fm
        xg = fm.expected_goals(wc_events, team="France")
        assert xg > 0, "France must have positive xG in a 4-goal game."

    def test_croatia_has_positive_xg(self, wc_events):
        import football_metrics as fm
        xg = fm.expected_goals(wc_events, team="Croatia")
        assert xg > 0

    def test_possession_sums_to_100(self, wc_events):
        import football_metrics as fm
        pct_fra = fm.possession_pct(wc_events, "France")
        pct_cro = fm.possession_pct(wc_events, "Croatia")
        assert pct_fra + pct_cro == pytest.approx(100.0, abs=0.2)

    def test_ppda_is_finite_positive(self, wc_events):
        import math
        import football_metrics as fm
        result = fm.ppda(wc_events, defending_team="France", attacking_team="Croatia")
        assert not math.isinf(result) and result > 0

    def test_field_tilt_within_range(self, wc_events):
        import football_metrics as fm
        tilt = fm.field_tilt(wc_events, "France")
        assert 0.0 <= tilt <= 100.0

    def test_split_xy_on_real_events(self, wc_events):
        shots = wc_events[wc_events["type"] == "Shot"].copy()
        out = split_xy(shots)
        assert "x" in out.columns and "y" in out.columns
        assert out["x"].notna().any(), "Shot coordinates should parse without NaN."
