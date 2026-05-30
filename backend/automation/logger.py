"""Structured logging service for test runs.

Wraps Python's standard logger with typed helpers for actions, retries,
locators, failures and recovery so log analysis is consistent.
"""
import logging
import time
from typing import Callable, Optional


class StructuredLogger:
    def __init__(self, run_id: str, on_log: Optional[Callable] = None):
        self.run_id = run_id
        self.on_log = on_log
        self._log = logging.getLogger(f"TestRun.{run_id[:8]}")
        self._start = time.monotonic()
        self.history: list = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _elapsed(self) -> float:
        return round(time.monotonic() - self._start, 3)

    def _record(self, entry: dict):
        entry["elapsed_s"] = self._elapsed()
        self.history.append(entry)

    # ------------------------------------------------------------------
    # Public logging methods
    # ------------------------------------------------------------------

    def action(self, step: int, action: str, target: str, value: str = "", reasoning: str = ""):
        self._log.info("Step %d | %s(%s)", step, action, target[:80])
        self._record({"kind": "action", "step": step, "action": action,
                      "target": target, "value": value, "reasoning": reasoning})

    def retry(self, attempt: int, max_attempts: int, action: str, reason: str):
        self._log.warning("Retry %d/%d | %s | %s", attempt, max_attempts, action, reason[:120])
        self._record({"kind": "retry", "attempt": attempt, "action": action, "reason": reason})

    def locator(self, strategy: str, selector: str, found: bool):
        self._log.debug("Locator [%s] '%s' → %s", strategy, selector[:60], "FOUND" if found else "miss")
        self._record({"kind": "locator", "strategy": strategy, "selector": selector, "found": found})

    def failure(self, step: int, action: str, target: str, error: str, recovery_attempted: bool = False):
        self._log.error("FAIL Step %d | %s(%s) | %s", step, action, target[:60], error[:200])
        self._record({"kind": "failure", "step": step, "action": action,
                      "target": target, "error": error, "recovery_attempted": recovery_attempted})

    def recovery(self, strategy: str, success: bool, detail: str = ""):
        level = logging.INFO if success else logging.WARNING
        self._log.log(level, "Recovery [%s] → %s %s", strategy, "OK" if success else "FAIL", detail[:80])
        self._record({"kind": "recovery", "strategy": strategy, "success": success, "detail": detail})

    def info(self, msg: str):
        self._log.info(msg)
        self._record({"kind": "info", "msg": msg})

    def warning(self, msg: str):
        self._log.warning(msg)

    def debug(self, msg: str):
        self._log.debug(msg)

    def get_summary(self) -> dict:
        return {
            "run_id": self.run_id,
            "elapsed_s": self._elapsed(),
            "total_entries": len(self.history),
        }
