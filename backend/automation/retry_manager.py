"""Universal retry mechanism with exponential backoff.

Wraps any async callable and retries it with increasing delays, structured
logging, and graceful error propagation.
"""
import asyncio
import logging
from typing import Callable, Optional, TypeVar

T = TypeVar("T")

_log = logging.getLogger("RetryManager")


class RetryManager:
    def __init__(self, max_retries: int = 3, base_delay: float = 0.5, max_delay: float = 5.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def run(
        self,
        fn: Callable,
        label: str = "action",
        on_retry: Optional[Callable] = None,
    ):
        """Execute *fn* with automatic retry on failure.

        *on_retry(attempt, error)* is called before each retry delay so callers
        can log or take corrective action (e.g. dismiss a popup) between attempts.
        """
        last_err: Exception = RuntimeError("No attempts made")

        for attempt in range(self.max_retries + 1):
            try:
                return await fn()
            except Exception as exc:
                last_err = exc
                if attempt >= self.max_retries:
                    break

                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                _log.warning(
                    "%s failed (attempt %d/%d): %s – retrying in %.1fs",
                    label, attempt + 1, self.max_retries + 1, exc, delay,
                )
                if on_retry:
                    try:
                        await on_retry(attempt + 1, exc)
                    except Exception:
                        pass
                await asyncio.sleep(delay)

        _log.error("%s exhausted %d retries. Last error: %s", label, self.max_retries, last_err)
        raise last_err
