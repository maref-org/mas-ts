# SPDX-FileCopyrightText: 2026 frankiehot-tech
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
    def __init__(self, initial_elo=ELO_INITIAL, k=ELO_K):
        self.ratings = {}
        self.match_counts = {}
        self.match_history = []
        self.initial_elo = initial_elo
        self.k = k

    def add_contestant(self, name):
        if name not in self.ratings:
            self.ratings[name] = self.initial_elo
            self.match_counts[name] = 0

    def _expected_score(self, rating_a, rating_b):
        return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

    def record_match(self, name_a, name_b, score_a, score_b):
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
        self.match_history.append({
            "contestant_a": name_a,
            "contestant_b": name_b,
            "score_a": score_a,
            "score_b": score_b,
            "rating_a_before": round(self.ratings[name_a] - k * (actual_a - e_a), 1),
            "rating_b_before": round(self.ratings[name_b] - k * (actual_b - e_b), 1),
            "rating_a_after": round(self.ratings[name_a], 1),
            "rating_b_after": round(self.ratings[name_b], 1),
        })

    def get_rating(self, name):
        return self.ratings.get(name, self.initial_elo)

    def get_matches(self, name):
        return self.match_counts.get(name, 0)

    def confidence_interval(self, name):
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
        entries = []
        for name, rating in self.ratings.items():
            if self.match_counts.get(name, 0) >= min_matches:
                entries.append({
                    "rank": 0,
                    "name": name,
                    "elo": round(rating, 1),
                    "matches": self.match_counts.get(name, 0),
                })
        entries.sort(key=lambda x: x["elo"], reverse=True)
        for i, e in enumerate(entries):
            e["rank"] = i + 1
        return entries

    def clear(self):
        self.ratings.clear()
        self.match_counts.clear()
        self.match_history.clear()
