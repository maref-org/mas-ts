# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Tests for MAS-TS-001 Pairwise Elo Ranking."""

import pytest

from mas_eval.scoring.elo import (
    ELO_INITIAL,
    ELO_MIN_MATCHES,
    EloRating,
)


class TestEloInit:
    def test_default_initial(self):
        elo = EloRating()
        assert elo.initial_elo == 1200
        assert elo.k == 32

    def test_custom_params(self):
        elo = EloRating(initial_elo=1000, k=16)
        assert elo.initial_elo == 1000
        assert elo.k == 16

    def test_add_contestant(self):
        elo = EloRating()
        elo.add_contestant("agent_a")
        assert elo.ratings["agent_a"] == 1200
        assert elo.match_counts["agent_a"] == 0

    def test_add_contestant_duplicate(self):
        elo = EloRating()
        elo.add_contestant("agent_a")
        elo.add_contestant("agent_a")
        assert len(elo.ratings) == 1
        assert elo.match_counts["agent_a"] == 0


class TestExpectedScore:
    def test_equal_ratings(self):
        elo = EloRating()
        assert elo._expected_score(1200, 1200) == pytest.approx(0.5)

    def test_higher_rating_favored(self):
        elo = EloRating()
        assert elo._expected_score(1600, 1200) > 0.5

    def test_lower_rating_underdog(self):
        elo = EloRating()
        assert elo._expected_score(1200, 1600) < 0.5

    def test_large_gap(self):
        elo = EloRating()
        expected = elo._expected_score(2000, 1200)
        assert expected > 0.9

    def test_symmetric(self):
        elo = EloRating()
        a = elo._expected_score(1500, 1300)
        b = elo._expected_score(1300, 1500)
        assert a + b == pytest.approx(1.0)


class TestRecordMatch:
    def test_winner_gains_elo(self):
        elo = EloRating()
        elo.record_match("a", "b", 90, 50)
        assert elo.get_rating("a") > ELO_INITIAL
        assert elo.get_rating("b") < ELO_INITIAL

    def test_draw_no_large_change(self):
        elo = EloRating()
        elo.record_match("a", "b", 75, 75)
        assert abs(elo.get_rating("a") - ELO_INITIAL) < 20
        assert abs(elo.get_rating("b") - ELO_INITIAL) < 20

    def test_margin_affects_k(self):
        elo1 = EloRating()
        elo1.record_match("a", "b", 99, 1)

        elo2 = EloRating()
        elo2.record_match("c", "d", 51, 49)

        change_a = abs(elo1.get_rating("a") - ELO_INITIAL)
        change_c = abs(elo2.get_rating("c") - ELO_INITIAL)
        assert change_a > change_c

    def test_match_counts(self):
        elo = EloRating()
        elo.record_match("a", "b", 80, 70)
        assert elo.match_counts["a"] == 1
        assert elo.match_counts["b"] == 1

    def test_match_history(self):
        elo = EloRating()
        elo.record_match("a", "b", 90, 50)
        assert len(elo.match_history) == 1
        h = elo.match_history[0]
        assert h["contestant_a"] == "a"
        assert h["contestant_b"] == "b"
        assert h["score_a"] == 90
        assert h["score_b"] == 50

    def test_history_tracks_before_after(self):
        elo = EloRating()
        elo.record_match("a", "b", 80, 70)
        h = elo.match_history[0]
        assert h["rating_a_before"] != h["rating_a_after"]

    def test_auto_adds_contestants(self):
        elo = EloRating()
        elo.record_match("new_a", "new_b", 85, 75)
        assert "new_a" in elo.ratings
        assert "new_b" in elo.ratings


class TestGetRating:
    def test_unknown_returns_initial(self):
        elo = EloRating()
        assert elo.get_rating("unknown") == ELO_INITIAL

    def test_known_returns_rating(self):
        elo = EloRating()
        elo.add_contestant("a")
        assert elo.get_rating("a") == ELO_INITIAL


class TestGetMatches:
    def test_unknown_returns_zero(self):
        elo = EloRating()
        assert elo.get_matches("unknown") == 0

    def test_known_match_count(self):
        elo = EloRating()
        elo.record_match("a", "b", 80, 70)
        elo.record_match("a", "c", 90, 60)
        assert elo.get_matches("a") == 2
        assert elo.get_matches("b") == 1


class TestConfidenceInterval:
    def test_below_min_matches(self):
        elo = EloRating()
        elo.record_match("a", "b", 80, 70)
        result = elo.confidence_interval("a")
        assert result is None

    def test_above_min_returns_ci(self):
        elo = EloRating()
        for i in range(60):
            elo.record_match(f"x{i}", "target", 80, 70)
        result = elo.confidence_interval("target")
        assert result is not None
        assert "rating" in result
        assert "ci_lower" in result
        assert "ci_upper" in result
        assert result["matches"] >= ELO_MIN_MATCHES

    def test_ci_range_plausible(self):
        elo = EloRating()
        for i in range(60):
            elo.record_match(f"x{i}", "target", 80, 70)
        result = elo.confidence_interval("target")
        assert result["ci_lower"] < result["rating"] < result["ci_upper"]


class TestLeaderboard:
    def test_empty(self):
        elo = EloRating()
        assert elo.leaderboard() == []

    def test_single_entry(self):
        elo = EloRating()
        elo.add_contestant("a")
        lb = elo.leaderboard()
        assert len(lb) == 1
        assert lb[0]["name"] == "a"
        assert lb[0]["rank"] == 1

    def test_sorted_by_elo_desc(self):
        elo = EloRating()
        elo.record_match("winner", "loser", 99, 1)
        lb = elo.leaderboard()
        assert lb[0]["name"] == "winner"
        assert lb[1]["name"] == "loser"

    def test_min_matches_filter(self):
        elo = EloRating()
        elo.add_contestant("nobody")
        elo.record_match("active", "other", 80, 70)
        lb = elo.leaderboard(min_matches=1)
        assert len(lb) == 2
        assert "nobody" not in [e["name"] for e in lb]

    def test_leaderboard_structure(self):
        elo = EloRating()
        elo.record_match("a", "b", 80, 70)
        e = elo.leaderboard()[0]
        assert "rank" in e
        assert "name" in e
        assert "elo" in e
        assert "matches" in e


class TestClear:
    def test_clears_all_state(self):
        elo = EloRating()
        elo.record_match("a", "b", 80, 70)
        elo.clear()
        assert elo.ratings == {}
        assert elo.match_counts == {}
        assert elo.match_history == []
