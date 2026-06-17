"""Unit tests for football_metrics.py.

All tests are deterministic: they rely exclusively on small synthetic DataFrames
built from known inputs so the expected output can be calculated by hand.
No network calls, no StatsBomb data required.

Coverage: all 16 public functions in football_metrics.py.
"""

import math

import pandas as pd
import pytest

import football_metrics as fm


# ── expected_goals ────────────────────────────────────────────────────────────

class TestExpectedGoals:
    def test_total_xg(self, events):
        # Only one shot in the fixture (xG=0.35)
        assert fm.expected_goals(events) == pytest.approx(0.35)

    def test_filter_by_team_a(self, events):
        assert fm.expected_goals(events, team="A") == pytest.approx(0.35)

    def test_filter_by_team_b_no_shots(self, events):
        assert fm.expected_goals(events, team="B") == pytest.approx(0.0)

    def test_multiple_shots(self):
        df = pd.DataFrame([
            {"type": "Shot", "team": "A", "shot_statsbomb_xg": 0.20},
            {"type": "Shot", "team": "A", "shot_statsbomb_xg": 0.45},
            {"type": "Shot", "team": "B", "shot_statsbomb_xg": 0.10},
        ])
        assert fm.expected_goals(df) == pytest.approx(0.75)

    def test_nan_xg_treated_as_zero(self):
        df = pd.DataFrame([
            {"type": "Shot", "shot_statsbomb_xg": None},
            {"type": "Shot", "shot_statsbomb_xg": 0.30},
        ])
        assert fm.expected_goals(df) == pytest.approx(0.30)

    def test_empty_df_returns_zero(self, empty_events):
        assert fm.expected_goals(empty_events) == pytest.approx(0.0)

    def test_missing_type_column_raises(self):
        df = pd.DataFrame({"shot_statsbomb_xg": [0.3]})
        with pytest.raises(KeyError):
            fm.expected_goals(df)

    def test_missing_xg_column_raises(self):
        df = pd.DataFrame({"type": ["Shot"]})
        with pytest.raises(KeyError):
            fm.expected_goals(df)


# ── expected_assists ──────────────────────────────────────────────────────────

class TestExpectedAssists:
    def test_total_xa(self, events):
        # Winger key-passed in poss 1 → credits the xG of poss-1 shot (0.35)
        assert fm.expected_assists(events) == pytest.approx(0.35)

    def test_filter_by_team_a(self, events):
        assert fm.expected_assists(events, team="A") == pytest.approx(0.35)

    def test_filter_by_team_b_returns_zero(self, events):
        assert fm.expected_assists(events, team="B") == pytest.approx(0.0)

    def test_no_key_passes_returns_zero(self, events):
        ev = events.copy()
        ev["pass_shot_assist"] = False
        assert fm.expected_assists(ev) == pytest.approx(0.0)

    def test_missing_pass_shot_assist_raises(self, events):
        ev = events.drop(columns=["pass_shot_assist"])
        with pytest.raises(KeyError):
            fm.expected_assists(ev)

    def test_missing_possession_raises(self, events):
        ev = events.drop(columns=["possession"])
        with pytest.raises(KeyError):
            fm.expected_assists(ev)


# ── possession_pct ────────────────────────────────────────────────────────────

class TestPossessionPct:
    def test_equal_possession(self, events):
        # 2 passes by A, 2 passes by B → 50 %
        assert fm.possession_pct(events, "A") == pytest.approx(50.0)

    def test_100_pct_possession(self):
        df = pd.DataFrame([
            {"type": "Pass", "team": "A"},
            {"type": "Pass", "team": "A"},
        ])
        assert fm.possession_pct(df, "A") == pytest.approx(100.0)

    def test_no_passes_returns_zero(self):
        df = pd.DataFrame([{"type": "Shot", "team": "A"}])
        assert fm.possession_pct(df, "A") == pytest.approx(0.0)

    def test_unknown_team_returns_zero(self, events):
        assert fm.possession_pct(events, "C") == pytest.approx(0.0)

    def test_empty_df_returns_zero(self, empty_events):
        assert fm.possession_pct(empty_events, "A") == pytest.approx(0.0)


# ── shot_accuracy ─────────────────────────────────────────────────────────────

class TestShotAccuracy:
    def test_normal(self):
        assert fm.shot_accuracy(8, 10) == pytest.approx(80.0)

    def test_all_on_target(self):
        assert fm.shot_accuracy(5, 5) == pytest.approx(100.0)

    def test_none_on_target(self):
        assert fm.shot_accuracy(0, 10) == pytest.approx(0.0)

    def test_zero_total_shots(self):
        assert fm.shot_accuracy(0, 0) == pytest.approx(0.0)

    def test_negative_total(self):
        assert fm.shot_accuracy(3, -1) == pytest.approx(0.0)


# ── pass_completion ───────────────────────────────────────────────────────────

class TestPassCompletion:
    def test_normal(self):
        assert fm.pass_completion(85, 100) == pytest.approx(85.0)

    def test_perfect(self):
        assert fm.pass_completion(10, 10) == pytest.approx(100.0)

    def test_zero_attempted(self):
        assert fm.pass_completion(0, 0) == pytest.approx(0.0)

    def test_negative_attempted(self):
        assert fm.pass_completion(5, -1) == pytest.approx(0.0)


# ── ppda ──────────────────────────────────────────────────────────────────────

class TestPPDA:
    def test_normal(self, events):
        # Zone x >= 120*0.4=48. B passes in zone: CB(70), FB(85) → 2.
        # A defensive actions in zone: Interception(90) → 1.
        # PPDA = 2/1 = 2.0
        result = fm.ppda(events, defending_team="A", attacking_team="B")
        assert result == pytest.approx(2.0)

    def test_no_defensive_actions_returns_inf(self):
        df = pd.DataFrame([
            {"type": "Pass", "team": "B", "location": [80, 40]},
        ])
        assert math.isinf(fm.ppda(df, defending_team="A", attacking_team="B"))

    def test_no_opponent_passes_returns_zero(self):
        df = pd.DataFrame([
            {"type": "Tackle", "team": "A", "location": [80, 40]},
        ])
        assert fm.ppda(df, defending_team="A", attacking_team="B") == pytest.approx(0.0)

    def test_events_outside_zone_ignored(self):
        # All events below the zone threshold → both counts = 0 → inf
        df = pd.DataFrame([
            {"type": "Pass",  "team": "B", "location": [10, 40]},
            {"type": "Tackle","team": "A", "location": [20, 40]},
        ])
        # Tackle is below zone (x=20 < 48) → no in-zone defensive actions → inf
        assert math.isinf(fm.ppda(df, defending_team="A", attacking_team="B"))

    def test_missing_type_column_raises(self):
        df = pd.DataFrame({"team": ["A"], "location": [[80, 40]]})
        with pytest.raises(KeyError):
            fm.ppda(df, "A", "B")


# ── defensive_actions ─────────────────────────────────────────────────────────

class TestDefensiveActions:
    def test_counts_interception(self, events):
        assert fm.defensive_actions(events, "A") == 1

    def test_counts_all_four_types(self):
        df = pd.DataFrame([
            {"type": "Tackle",         "team": "X"},
            {"type": "Interception",   "team": "X"},
            {"type": "Challenge",      "team": "X"},
            {"type": "Foul Committed", "team": "X"},
            {"type": "Pass",           "team": "X"},  # should NOT be counted
        ])
        assert fm.defensive_actions(df, "X") == 4

    def test_other_team_returns_zero(self, events):
        assert fm.defensive_actions(events, "B") == 0

    def test_empty_df_returns_zero(self, empty_events):
        assert fm.defensive_actions(empty_events, "A") == 0


# ── high_turnovers ────────────────────────────────────────────────────────────

class TestHighTurnovers:
    def test_interception_above_threshold(self, events):
        # A's interception at x=90 >= default 80 → 1 high turnover
        assert fm.high_turnovers(events, "A") == 1

    def test_recovery_below_threshold_not_counted(self):
        df = pd.DataFrame([
            {"type": "Interception", "team": "A", "location": [50, 40]},
        ])
        assert fm.high_turnovers(df, "A") == 0

    def test_all_three_recover_types_counted(self):
        df = pd.DataFrame([
            {"type": "Ball Recovery", "team": "A", "location": [90, 40]},
            {"type": "Interception",  "team": "A", "location": [85, 40]},
            {"type": "Tackle",        "team": "A", "location": [82, 40]},
            {"type": "Pass",          "team": "A", "location": [90, 40]},  # excluded
        ])
        assert fm.high_turnovers(df, "A") == 3

    def test_other_team_returns_zero(self, events):
        assert fm.high_turnovers(events, "B") == 0

    def test_custom_threshold(self, events):
        # Raise the threshold above all events → 0
        assert fm.high_turnovers(events, "A", high_x=115.0) == 0


# ── field_tilt ────────────────────────────────────────────────────────────────

class TestFieldTilt:
    def test_a_dominates_final_third(self, events):
        # Events with x >= 80: Pass(95,A), Shot(110,A), Pass(85,B), Interception(90,A)
        # Team A in final third: 3, total: 4 → 75.0 %
        assert fm.field_tilt(events, "A") == pytest.approx(75.0)

    def test_no_events_in_final_third_returns_zero(self):
        df = pd.DataFrame([
            {"type": "Pass", "team": "A", "location": [30, 40]},
            {"type": "Pass", "team": "B", "location": [50, 40]},
        ])
        assert fm.field_tilt(df, "A") == pytest.approx(0.0)

    def test_100_pct_field_tilt(self):
        df = pd.DataFrame([
            {"type": "Pass", "team": "A", "location": [90, 40]},
            {"type": "Shot", "team": "A", "location": [110, 40]},
        ])
        assert fm.field_tilt(df, "A") == pytest.approx(100.0)

    def test_empty_df_returns_zero(self, empty_events):
        assert fm.field_tilt(empty_events, "A") == pytest.approx(0.0)


# ── key_passes ────────────────────────────────────────────────────────────────

class TestKeyPasses:
    def test_by_team_a(self, events):
        assert fm.key_passes(events, team="A") == 1

    def test_by_player_winger(self, events):
        assert fm.key_passes(events, player="Winger") == 1

    def test_by_player_midfielder_zero(self, events):
        assert fm.key_passes(events, player="Midfielder") == 0

    def test_other_team_returns_zero(self, events):
        assert fm.key_passes(events, team="B") == 0

    def test_no_key_passes_in_df(self, events):
        ev = events.copy()
        ev["pass_shot_assist"] = False
        assert fm.key_passes(ev) == 0

    def test_multiple_key_passes(self):
        df = pd.DataFrame([
            {"type": "Pass", "team": "A", "player": "P1", "pass_shot_assist": True},
            {"type": "Pass", "team": "A", "player": "P2", "pass_shot_assist": True},
            {"type": "Pass", "team": "A", "player": "P3", "pass_shot_assist": False},
        ])
        assert fm.key_passes(df) == 2

    def test_missing_column_raises(self, events):
        ev = events.drop(columns=["pass_shot_assist"])
        with pytest.raises(KeyError):
            fm.key_passes(ev)


# ── shot_creating_actions ─────────────────────────────────────────────────────

class TestShotCreatingActions:
    def test_midfielder_in_shot_possession(self, events):
        # Midfielder touched the ball in poss 1 which has a shot → SCA = 1
        assert fm.shot_creating_actions(events, "Midfielder") == 1

    def test_cb_not_in_shot_possession(self, events):
        # CB only in poss 2 which has no shot → SCA = 0
        assert fm.shot_creating_actions(events, "CB") == 0

    def test_striker_in_shot_possession(self, events):
        assert fm.shot_creating_actions(events, "Striker") == 1

    def test_unknown_player_returns_zero(self, events):
        assert fm.shot_creating_actions(events, "Unknown Player") == 0

    def test_no_shots_anywhere_returns_zero(self):
        df = pd.DataFrame([
            {"type": "Pass", "team": "A", "player": "P", "possession": 1},
        ])
        assert fm.shot_creating_actions(df, "P") == 0


# ── xg_chain ─────────────────────────────────────────────────────────────────

class TestXgChain:
    def test_winger_in_shot_possession(self, events):
        # Winger is in poss 1 which has xG=0.35 → xGChain = 0.35
        assert fm.xg_chain(events, "Winger") == pytest.approx(0.35)

    def test_midfielder_in_shot_possession(self, events):
        assert fm.xg_chain(events, "Midfielder") == pytest.approx(0.35)

    def test_dm_not_in_shot_possession(self, events):
        # DM only in poss 2 (no shot there) → xGChain = 0.0
        assert fm.xg_chain(events, "DM") == pytest.approx(0.0)

    def test_unknown_player_returns_zero(self, events):
        assert fm.xg_chain(events, "Ghost") == pytest.approx(0.0)

    def test_player_in_multiple_shot_possessions(self):
        df = pd.DataFrame([
            {"type": "Pass", "team": "A", "player": "Creator",
             "possession": 1, "shot_statsbomb_xg": None},
            {"type": "Shot", "team": "A", "player": "S1",
             "possession": 1, "shot_statsbomb_xg": 0.30},
            {"type": "Pass", "team": "A", "player": "Creator",
             "possession": 2, "shot_statsbomb_xg": None},
            {"type": "Shot", "team": "A", "player": "S2",
             "possession": 2, "shot_statsbomb_xg": 0.20},
        ])
        assert fm.xg_chain(df, "Creator") == pytest.approx(0.50)


# ── per_90 ────────────────────────────────────────────────────────────────────

class TestPer90:
    def test_normal(self):
        assert fm.per_90(10, 720) == pytest.approx(1.25)

    def test_exact_90_minutes(self):
        assert fm.per_90(3, 90) == pytest.approx(3.0)

    def test_zero_minutes_returns_zero(self):
        assert fm.per_90(5, 0) == pytest.approx(0.0)

    def test_negative_minutes_returns_zero(self):
        assert fm.per_90(5, -10) == pytest.approx(0.0)

    def test_zero_stat_with_nonzero_minutes(self):
        assert fm.per_90(0, 90) == pytest.approx(0.0)


# ── goals_minus_xg ────────────────────────────────────────────────────────────

class TestGoalsMinusXg:
    def test_overperforming(self):
        assert fm.goals_minus_xg(8, 6.2) == pytest.approx(1.8)

    def test_underperforming(self):
        assert fm.goals_minus_xg(3, 5.5) == pytest.approx(-2.5)

    def test_on_expectation(self):
        assert fm.goals_minus_xg(4.0, 4.0) == pytest.approx(0.0)


# ── goal_difference_per_90 ────────────────────────────────────────────────────

class TestGoalDifferencePerNinety:
    def test_positive_gd(self):
        assert fm.goal_difference_per_90(4, 2, 90) == pytest.approx(2.0)

    def test_negative_gd(self):
        assert fm.goal_difference_per_90(1, 3, 90) == pytest.approx(-2.0)

    def test_zero_minutes_returns_zero(self):
        assert fm.goal_difference_per_90(5, 1, 0) == pytest.approx(0.0)

    def test_equal_goals_returns_zero(self):
        assert fm.goal_difference_per_90(2, 2, 90) == pytest.approx(0.0)


# ── buildup_ratio ─────────────────────────────────────────────────────────────

class TestBuildupRatio:
    def test_normal(self):
        assert fm.buildup_ratio(0.6, 1.5) == pytest.approx(0.4)

    def test_full_buildup(self):
        assert fm.buildup_ratio(1.0, 1.0) == pytest.approx(1.0)

    def test_zero_xg_chain_returns_zero(self):
        assert fm.buildup_ratio(0.6, 0.0) == pytest.approx(0.0)

    def test_negative_xg_chain_returns_zero(self):
        assert fm.buildup_ratio(0.5, -0.1) == pytest.approx(0.0)
