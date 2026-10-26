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
    """Opens after `fail_max` consecutive failures and rejects calls for `reset_seconds`.

    After the window one trial call is let through (half-open): success closes the
    breaker, another failure opens it again straight away.
    """

    def __init__(self, name: str, fail_max: int = 5, reset_seconds: float = 5) -> None:
        self.name = name
        self.fail_max = fail_max
        self.reset_seconds = reset_seconds
        self.failures = 0
        self.open_until = 0.0

    @property
    def is_open(self) -> bool:
        return self.open_until > 0 and time.monotonic() < self.open_until

    def allow(self) -> None:
        if self.is_open:
            raise CircuitOpenError(f"{self.name} circuit open")

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

# One breaker per model, so a failing model is skipped for a while instead of being
# retried on every call, and is tried again (not forgotten) once the window has passed.
_MODEL_CIRCUITS: dict[str, CircuitBreaker] = {}


def model_circuit(model: str) -> CircuitBreaker:
    if model not in _MODEL_CIRCUITS:
        from app.core.config import get_settings

        settings = get_settings()
        _MODEL_CIRCUITS[model] = CircuitBreaker(
            f"model:{model}",
            fail_max=settings.model_circuit_fail_max,
            reset_seconds=settings.model_circuit_reset_seconds,
        )
    return _MODEL_CIRCUITS[model]


def reset_model_circuits() -> None:
    _MODEL_CIRCUITS.clear()


async def with_backoff(
    fn: Callable[[], Awaitable[T]],
    *,
    circuit: CircuitBreaker,
    attempts: int = 4,
) -> T:
    circuit.allow()
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
