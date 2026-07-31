# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Pairwise Elo Ranking for MAS-TS-001 v3.0.

Usage:
  elo = EloRating()
  elo.add_contestant("agent_a")
  elo.add_contestant("agent_b")
  elo.record_match("agent_a", "agent_b", score_a=85, score_b=72)
  rankings = elo.leaderboard()
"""

import math

ELO_INITIAL = 1200
ELO_K = 32
ELO_MIN_MATCHES = 50
ELO_CONFIDENCE_Z = 1.96


class EloRating:
    """Pairwise Elo rating system for agent capability comparison.

    Supports contestant management, match recording with score-margin-aware
    K-factors, and leaderboard generation with confidence intervals.
    """

    def __init__(self, initial_elo=ELO_INITIAL, k=ELO_K):
        self.ratings = {}
        self.match_counts = {}
        self.match_history = []
        self.initial_elo = initial_elo
        self.k = k

    def add_contestant(self, name):
        """Register a contestant with the initial Elo rating.

        Args:
        name: Contestant identifier string.
        """
        if name not in self.ratings:
            self.ratings[name] = self.initial_elo
            self.match_counts[name] = 0

    def _expected_score(self, rating_a, rating_b):
        return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

    def record_match(self, name_a, name_b, score_a, score_b):
        """Record a match between two contestants and update ratings.

        Uses score-difference-aware K-factor: larger margins cause larger
        rating adjustments. Handles ties (0.5/0.5) and wins (1.0/0.0).

        Args:
        name_a: First contestant identifier.
        name_b: Second contestant identifier.
        score_a: First contestant's evaluation score.
        score_b: Second contestant's evaluation score.
        """
        self.add_contestant(name_a)
        self.add_contestant(name_b)

        diff = score_a - score_b
        if abs(diff) < 1:
            actual_a, actual_b = 0.5, 0.5
        elif diff > 0:
            actual_a, actual_b = 1.0, 0.0
        else:
            actual_a, actual_b = 0.0, 1.0

        margin = min(1.0, abs(diff) / 100.0)
        k = self.k * (1.0 + margin)

        e_a = self._expected_score(self.ratings[name_a], self.ratings[name_b])
        e_b = 1.0 - e_a

        self.ratings[name_a] += k * (actual_a - e_a)
        self.ratings[name_b] += k * (actual_b - e_b)

        self.match_counts[name_a] += 1
        self.match_counts[name_b] += 1
        self.match_history.append(
            {
                "contestant_a": name_a,
                "contestant_b": name_b,
                "score_a": score_a,
                "score_b": score_b,
                "rating_a_before": round(
                    self.ratings[name_a] - k * (actual_a - e_a), 1
                ),
                "rating_b_before": round(
                    self.ratings[name_b] - k * (actual_b - e_b), 1
                ),
                "rating_a_after": round(self.ratings[name_a], 1),
                "rating_b_after": round(self.ratings[name_b], 1),
            }
        )

    def get_rating(self, name):
        """Get the current Elo rating for a contestant.

        Args:
        name: Contestant identifier.

        Returns:
        Current Elo rating (float), or initial_elo if contestant unknown.
        """
        return self.ratings.get(name, self.initial_elo)

    def get_matches(self, name):
        """Get the match count for a contestant.

        Args:
        name: Contestant identifier.

        Returns:
        Number of recorded matches (int), or 0 if contestant unknown.
        """
        return self.match_counts.get(name, 0)

    def confidence_interval(self, name):
        """Compute 95% confidence interval for a contestant's rating.

        Requires at least ELO_MIN_MATCHES matches for meaningful statistics.

        Args:
        name: Contestant identifier.

        Returns:
        Dict with keys "rating", "matches", "ci_lower", "ci_upper",
        or None if insufficient matches.
        """
        n = self.match_counts.get(name, 0)
        if n < ELO_MIN_MATCHES:
            return None
        rating = self.ratings.get(name, self.initial_elo)
        se = 400.0 / math.sqrt(n)
        return {
            "rating": round(rating, 1),
            "matches": n,
            "ci_lower": round(rating - ELO_CONFIDENCE_Z * se, 1),
            "ci_upper": round(rating + ELO_CONFIDENCE_Z * se, 1),
        }

    def leaderboard(self, min_matches=0):
        """Generate a ranked leaderboard of contestants by Elo rating.

        Args:
        min_matches: Minimum match count for inclusion (default 0).

        Returns:
        List of dicts sorted by elo descending, each with keys:
        rank, name, elo, matches.
        """
        entries = []
        for name, rating in self.ratings.items():
            if self.match_counts.get(name, 0) >= min_matches:
                entries.append(
                    {
                        "rank": 0,
                        "name": name,
                        "elo": round(rating, 1),
                        "matches": self.match_counts.get(name, 0),
                    }
                )
        entries.sort(key=lambda x: x["elo"], reverse=True)
        for i, e in enumerate(entries):
            e["rank"] = i + 1
        return entries

    def clear(self):
        """Reset all ratings, match counts, and history."""
        self.ratings.clear()
        self.match_counts.clear()
        self.match_history.clear()
