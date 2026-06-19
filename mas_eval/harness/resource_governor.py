# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Resource governance for evaluation loops."""

import time

from mas_eval.domains.d4_governance_security import CircuitBreaker, CircuitBreakerState


class TokenBudget:
    def __init__(
        self,
        max_tokens: float = float("inf"),
        max_calls: int = 10_000,
        max_elapsed: float = float("inf"),
    ) -> None:
        self.max_tokens = max_tokens
        self.max_calls = max_calls
        self.max_elapsed = max_elapsed
        self.tokens_used = 0.0
        self.calls_used = 0
        self.start_time = time.time()

    @property
    def remaining_tokens(self) -> float:
        return self.max_tokens - self.tokens_used

    @property
    def remaining_calls(self) -> int:
        return self.max_calls - self.calls_used

    @property
    def remaining_elapsed(self) -> float:
        return self.max_elapsed - (time.time() - self.start_time)

    def consume(self, tokens: float = 0, calls: int = 1) -> None:
        self.tokens_used += tokens
        self.calls_used += calls

    def exceeded(self) -> bool:
        return (
            self.tokens_used >= self.max_tokens
            or self.calls_used > self.max_calls
            or time.time() - self.start_time >= self.max_elapsed
        )

    def reset(self) -> None:
        self.tokens_used = 0.0
        self.calls_used = 0
        self.start_time = time.time()


class ResourceGovernor:
    def __init__(self, budget: TokenBudget | None = None) -> None:
        self.budget = budget or TokenBudget()
        self.circuit_breaker = CircuitBreaker()
        self._tripped = False

    def check(self) -> bool:
        if self.budget.exceeded() or self.budget.remaining_calls <= 0:
            return False
        if self._tripped:
            if self.circuit_breaker.check_cooldown():
                self._tripped = False
            else:
                return False
        return self.circuit_breaker.state != CircuitBreakerState.OPEN

    def consume(self, tokens: float = 0, calls: int = 1) -> None:
        self.budget.consume(tokens=tokens, calls=calls)

    def record_failure(self) -> None:
        self.circuit_breaker.record_failure()
        if self.circuit_breaker.state == CircuitBreakerState.OPEN:
            self._tripped = True

    def record_success(self) -> None:
        self.circuit_breaker.record_success()
