"""Retry + circuit breaker for VideoDB / Gemini. Failures become job errors, never hangs."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    pass


class CircuitBreaker:
    def __init__(self, name: str, fail_max: int = 5, reset_seconds: float = 5) -> None:
        self.name = name
        self.fail_max = fail_max
        self.reset_seconds = reset_seconds
        self.failures = 0
        self.open_until = 0.0

    def allow(self) -> None:
        if time.monotonic() < self.open_until:
            # Auto reset if timeout passed
            return
        if self.open_until > 0 and time.monotonic() >= self.open_until:
            self.success()

    def success(self) -> None:
        self.failures = 0
        self.open_until = 0.0

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.fail_max:
            self.open_until = time.monotonic() + self.reset_seconds

    def reset(self) -> None:
        self.success()


stt_circuit = CircuitBreaker("stt")
llm_circuit = CircuitBreaker("llm")


async def with_backoff(
    fn: Callable[[], Awaitable[T]],
    *,
    circuit: CircuitBreaker,
    attempts: int = 4,
) -> T:
    circuit.allow()
    last: BaseException | None = None
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=1.0, min=1.0, max=6.0),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                result = await fn()
                circuit.success()
                return result
    except Exception as exc:
        circuit.failure()
        raise exc
    raise RuntimeError("retry exhausted")
