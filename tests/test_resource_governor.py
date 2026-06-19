# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for resource governance budgets and circuit breaker integration."""

import time

from mas_eval.harness.resource_governor import ResourceGovernor, TokenBudget


class TestTokenBudget:
    def test_init_remaining_tokens_calls(self):
        budget = TokenBudget(max_tokens=100, max_calls=3)
        assert budget.remaining_tokens == 100
        assert budget.remaining_calls == 3

    def test_consume_tokens(self):
        budget = TokenBudget(max_tokens=100)
        budget.consume(tokens=25)
        assert budget.remaining_tokens == 75

    def test_exceeded_tokens(self):
        budget = TokenBudget(max_tokens=100)
        budget.consume(tokens=100)
        assert budget.exceeded() is True

    def test_exceeded_calls_after_limit_plus_one(self):
        budget = TokenBudget(max_calls=3)
        for _ in range(3):
            budget.consume()
        assert budget.exceeded() is False
        budget.consume()
        assert budget.exceeded() is True

    def test_exceeded_elapsed(self):
        budget = TokenBudget(max_elapsed=0.01)
        time.sleep(0.02)
        assert budget.exceeded() is True

    def test_reset_resets_tokens_calls_start(self):
        budget = TokenBudget(max_tokens=100, max_calls=3)
        original_start = budget.start_time
        time.sleep(0.01)
        budget.consume(tokens=40, calls=2)
        budget.reset()
        assert budget.remaining_tokens == 100
        assert budget.remaining_calls == 3
        assert budget.start_time > original_start


class TestResourceGovernor:
    def test_check_false_after_budget_exceeded(self):
        budget = TokenBudget(max_calls=1)
        governor = ResourceGovernor(budget=budget)
        governor.consume()
        governor.consume()
        assert governor.check() is False
