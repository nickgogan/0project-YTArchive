"""Shared utility functions for YTArchive services."""

import asyncio
import random
import time
from functools import wraps
from typing import Any, Callable, Coroutine, TypeVar, cast

# A TypeVar is used to create a generic type for the decorator, preserving the
# original function's signature for mypy.
F = TypeVar("F", bound=Callable[..., Coroutine[Any, Any, Any]])


def retry_with_backoff(
    retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
) -> Callable[[F], F]:
    """
    A decorator factory that creates a decorator to retry a function with
    exponential backoff.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = base_delay
            for i in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if i == retries - 1:
                        raise

                    delay = min(delay * 2, max_delay)
                    actual_delay = delay
                    if jitter:
                        actual_delay += random.uniform(0, delay / 4)

                    print(
                        f"Retry {i+1}/{retries} for {func.__name__} after delay of {actual_delay:.2f}s. Error: {e}"
                    )
                    await asyncio.sleep(actual_delay)

        # We cast the wrapper to type F to give mypy a hint that the decorated
        # function retains its original signature.
        return cast(F, wrapper)

    return decorator


class CircuitBreaker:
    """A simple circuit breaker implementation."""

    def __init__(self, failure_threshold: int, recovery_timeout: int):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "HALF_OPEN"
                else:
                    raise Exception("Circuit is open")

            try:
                result = await func(*args, **kwargs)
                self._reset()
                return result
            except Exception as e:
                self._record_failure()
                raise e

        return wrapper

    def _record_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.last_failure_time = time.time()

    def _reset(self):
        self.failure_count = 0
        self.state = "CLOSED"
