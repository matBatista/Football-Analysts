"""Tests for Expected Threat (xT) functions in football_metrics.py.

All unit tests are deterministic: exact (x, y) coordinates are used so cell
indices and expected values can be verified by hand against XT_GRID.

Grid mapping reminder (StatsBomb 120×80, grid 12×8):
    col = clamp(floor(x / 120 * 12), 0, 11)
    row = clamp(floor(y /  80 *  8), 0,  7)

Spot-check coordinates used in tests:
    (60, 40)  → col 6, row 4 → XT_GRID[4,6]  = 0.03066
    (100, 40) → col 10, row 4 → XT_GRID[4,10] = 0.22406
    (0, 0)    → col 0, row 0 → XT_GRID[0,0]  = 0.00638
    (119, 79) → col 11, row 7 → XT_GRID[7,11] = 0.26938
"""

import math
from pathlib import Path

import pandas as pd
import pytest

from football_metrics import XT_GRID, location_to_xt, xt_added, xt_by_player

# ── Helpers ───────────────────────────────────────────────────────────────────

def _pass_events(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal events DataFrame with the columns xT functions need."""
    base = {"type": "Pass", "team": "A", "player": "P1",
            "pass_end_location": None, "carry_end_location": None}
    return pd.DataFrame([{**base, **r} for r in rows])


# ── location_to_xt ────────────────────────────────────────────────────────────

class TestLocationToXt:
    def test_centre_of_pitch(self):
        # (60, 40) → col 6, row 4
        assert location_to_xt(60, 40) == pytest.approx(XT_GRID[4, 6])

    def test_near_opponent_goal(self):
        # (100, 40) → col 10, row 4
        assert location_to_xt(100, 40) == pytest.approx(XT_GRID[4, 10])

    def test_own_goal_corner(self):
        # (0, 0) → col 0, row 0
        assert location_to_xt(0, 0) == pytest.approx(XT_GRID[0, 0])

    def test_clamping_x_above_max(self):
        # x=120 would give col=12, must clamp to 11
        assert location_to_xt(120, 40) == pytest.approx(XT_GRID[4, 11])

    def test_clamping_y_above_max(self):
        # y=80 would give row=8, must clamp to 7
        assert location_to_xt(60, 80) == pytest.approx(XT_GRID[7, 6])

    def test_clamping_negative_x(self):
        assert location_to_xt(-5, 40) == pytest.approx(XT_GRID[4, 0])

    def test_clamping_negative_y(self):
        assert location_to_xt(60, -1) == pytest.approx(XT_GRID[0, 6])

    def test_exact_pitch_end_x(self):
        # x just inside the last column (e.g. 119.99)
        val = location_to_xt(119.99, 40)
        assert val == pytest.approx(XT_GRID[4, 11])

    def test_grid_symmetry_top_bottom(self):
        # The grid is y-symmetric: row 0 == row 7, row 1 == row 6
        assert location_to_xt(60,  5) == pytest.approx(location_to_xt(60, 75))

    def test_return_type_is_float(self):
        assert isinstance(location_to_xt(60, 40), float)

    def test_values_between_zero_and_one(self):
        for x in [0, 30, 60, 90, 119]:
            for y in [0, 20, 40, 60, 79]:
                v = location_to_xt(x, y)
                assert 0.0 <= v <= 1.0, f"Out of [0,1] at ({x},{y}): {v}"


# ── xt_added ──────────────────────────────────────────────────────────────────

class TestXtAdded:
    def test_forward_pass_positive(self):
        # Pass from (60,40) → (100,40): moves into higher-xT zone
        df = _pass_events([{"location": [60, 40], "pass_end_location": [100, 40]}])
        result = xt_added(df)
        expected = location_to_xt(100, 40) - location_to_xt(60, 40)
        assert result["xt_added"].iloc[0] == pytest.approx(expected)

    def test_backward_pass_negative(self):
        # Pass from (100,40) → (60,40): moves into lower-xT zone
        df = _pass_events([{"location": [100, 40], "pass_end_location": [60, 40]}])
        result = xt_added(df)
        expected = location_to_xt(60, 40) - location_to_xt(100, 40)
        assert result["xt_added"].iloc[0] == pytest.approx(expected)
        assert result["xt_added"].iloc[0] < 0

    def test_same_origin_destination_is_zero(self):
        df = _pass_events([{"location": [60, 40], "pass_end_location": [60, 40]}])
        result = xt_added(df)
        assert result["xt_added"].iloc[0] == pytest.approx(0.0)

    def test_carry_event_uses_carry_end_location(self):
        df = pd.DataFrame([{
            "type": "Carry", "team": "A", "player": "P1",
            "location": [60, 40],
            "carry_end_location": [100, 40],
            "pass_end_location": None,
        }])
        result = xt_added(df)
        expected = location_to_xt(100, 40) - location_to_xt(60, 40)
        assert result["xt_added"].iloc[0] == pytest.approx(expected)

    def test_non_pass_carry_events_excluded(self):
        df = pd.DataFrame([
            {"type": "Shot",        "team": "A", "player": "P1",
             "location": [110, 40], "pass_end_location": None, "carry_end_location": None},
            {"type": "Interception","team": "A", "player": "P1",
             "location": [80, 40],  "pass_end_location": None, "carry_end_location": None},
        ])
        result = xt_added(df)
        assert len(result) == 0

    def test_team_filter_excludes_other_team(self):
        df = _pass_events([
            {"team": "A", "location": [60, 40], "pass_end_location": [100, 40]},
            {"team": "B", "location": [60, 40], "pass_end_location": [100, 40]},
        ])
        result = xt_added(df, team="A")
        assert len(result) == 1
        assert result["team"].iloc[0] == "A"

    def test_empty_dataframe_returns_empty(self):
        df = pd.DataFrame(columns=["type", "team", "player",
                                   "location", "pass_end_location",
                                   "carry_end_location"])
        result = xt_added(df)
        assert result.empty

    def test_missing_location_column_raises(self):
        df = pd.DataFrame([{"type": "Pass", "team": "A"}])
        with pytest.raises(KeyError):
            xt_added(df)

    def test_multiple_actions_correct_count(self):
        df = _pass_events([
            {"location": [60, 40], "pass_end_location": [80, 40]},
            {"location": [80, 40], "pass_end_location": [100, 40]},
        ])
        result = xt_added(df)
        assert len(result) == 2
        assert (result["xt_added"] > 0).all()

    def test_missing_end_location_gives_nan(self):
        # pass_end_location is None → xT(dest) = NaN → xt_added = NaN
        df = _pass_events([{"location": [60, 40], "pass_end_location": None}])
        result = xt_added(df)
        assert math.isnan(result["xt_added"].iloc[0])


# ── xt_by_player ─────────────────────────────────────────────────────────────

class TestXtByPlayer:
    def _two_player_events(self) -> pd.DataFrame:
        return pd.DataFrame([
            # P1: forward pass → positive xT
            {"type": "Pass", "team": "A", "player": "P1",
             "location": [60, 40], "pass_end_location": [100, 40],
             "carry_end_location": None},
            # P2: also a forward pass
            {"type": "Pass", "team": "A", "player": "P2",
             "location": [30, 40], "pass_end_location": [60, 40],
             "carry_end_location": None},
            # P1: backward pass → negative, should NOT count toward sum
            {"type": "Pass", "team": "A", "player": "P1",
             "location": [100, 40], "pass_end_location": [60, 40],
             "carry_end_location": None},
        ])

    def test_returns_dataframe_with_expected_columns(self):
        df = self._two_player_events()
        result = xt_by_player(df)
        assert list(result.columns) == ["player", "xt_added"]

    def test_sorted_descending(self):
        df = self._two_player_events()
        result = xt_by_player(df)
        assert result["xt_added"].iloc[0] >= result["xt_added"].iloc[1]

    def test_only_positive_contributions_summed(self):
        # P1 has one positive (+0.193) and one negative (−0.193) pass.
        # Only the positive one should count.
        df = self._two_player_events()
        result = xt_by_player(df)
        p1_row = result[result["player"] == "P1"]
        expected_positive = location_to_xt(100, 40) - location_to_xt(60, 40)
        assert p1_row["xt_added"].iloc[0] == pytest.approx(expected_positive)

    def test_team_filter(self):
        df = pd.DataFrame([
            {"type": "Pass", "team": "A", "player": "PA",
             "location": [60, 40], "pass_end_location": [100, 40],
             "carry_end_location": None},
            {"type": "Pass", "team": "B", "player": "PB",
             "location": [60, 40], "pass_end_location": [100, 40],
             "carry_end_location": None},
        ])
        result = xt_by_player(df, team="A")
        assert list(result["player"]) == ["PA"]

    def test_empty_events_returns_empty_df(self):
        df = pd.DataFrame(columns=["type", "team", "player",
                                   "location", "pass_end_location",
                                   "carry_end_location"])
        result = xt_by_player(df)
        assert result.empty
        assert list(result.columns) == ["player", "xt_added"]

    def test_all_backward_passes_returns_empty(self):
        # If all passes are backward the >0 filter drops everything
        df = pd.DataFrame([{
            "type": "Pass", "team": "A", "player": "P1",
            "location": [100, 40], "pass_end_location": [60, 40],
            "carry_end_location": None,
        }])
        result = xt_by_player(df)
        assert result.empty

    def test_missing_player_column_raises(self):
        df = pd.DataFrame([{"type": "Pass", "team": "A",
                            "location": [60, 40],
                            "pass_end_location": [100, 40]}])
        with pytest.raises(KeyError):
            xt_by_player(df)


# ── Integration: 2018 World Cup Final (match 8658, offline cache) ─────────────

_CACHE = Path(__file__).resolve().parent.parent / "sb_cache" / "events" / "8658.json"
_cache_available = pytest.mark.skipif(
    not _CACHE.exists(),
    reason="StatsBomb cache for match 8658 not found.",
)


@pytest.mark.integration
@_cache_available
class TestXtIntegration:
    @pytest.fixture(scope="class")
    @classmethod
    def wc_events(cls):
        from football_analyst.data import StatsBomb
        return StatsBomb().events(8658)

    def test_xt_added_returns_rows_for_real_match(self, wc_events):
        result = xt_added(wc_events)
        assert len(result) > 100, "Expected many pass/carry actions."

    def test_xt_added_column_is_numeric(self, wc_events):
        result = xt_added(wc_events)
        assert pd.api.types.is_float_dtype(result["xt_added"])

    def test_xt_by_player_top_contributors_are_plausible(self, wc_events):
        result = xt_by_player(wc_events)
        assert len(result) >= 10, "Should have many player rows."
        top_xt = result["xt_added"].iloc[0]
        # Top contributor should have meaningful xT (>0.5) in a high-scoring final
        assert top_xt > 0.5, f"Top xT {top_xt:.3f} seems too low."

    def test_both_teams_have_meaningful_xt(self, wc_events):
        fra = xt_by_player(wc_events, team="France")["xt_added"].sum()
        cro = xt_by_player(wc_events, team="Croatia")["xt_added"].sum()
        # Both teams must have generated threat (xT > 0).
        # Croatia had ~61% possession so their raw xT total is higher — that is
        # expected; France were more efficient (4 goals from less ball time).
        assert fra > 0, f"France xT={fra:.2f} must be positive."
        assert cro > 0, f"Croatia xT={cro:.2f} must be positive."
        assert fra + cro > 10, "Combined xT for a 4-2 final should exceed 10."

    def test_location_to_xt_on_real_shot(self, wc_events):
        shots = wc_events[wc_events["type"] == "Shot"]
        assert len(shots) > 0
        first_shot_loc = shots["location"].iloc[0]
        val = location_to_xt(first_shot_loc[0], first_shot_loc[1])
        assert 0.0 < val <= 1.0
