"""Centralized timeout and automation configuration.

All values are overridable via environment variables so the framework
adapts to slow/fast environments without code changes.
"""
import os


class AutomationConfig:
    # Global Playwright timeouts (milliseconds)
    DEFAULT_TIMEOUT: int = int(os.getenv("DEFAULT_TIMEOUT_MS", "30000"))
    DEFAULT_NAV_TIMEOUT: int = int(os.getenv("DEFAULT_NAV_TIMEOUT_MS", "60000"))

    # Per-action timeouts
    CLICK_TIMEOUT: int = int(os.getenv("CLICK_TIMEOUT_MS", "10000"))
    FILL_TIMEOUT: int = int(os.getenv("FILL_TIMEOUT_MS", "10000"))
    WAIT_TIMEOUT: int = int(os.getenv("WAIT_TIMEOUT_MS", "10000"))

    # Retry settings
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_BASE_DELAY: float = float(os.getenv("RETRY_BASE_DELAY_S", "0.5"))
    RETRY_MAX_DELAY: float = float(os.getenv("RETRY_MAX_DELAY_S", "5.0"))

    # Page readiness
    NETWORK_IDLE_TIMEOUT: int = int(os.getenv("NETWORK_IDLE_TIMEOUT_MS", "8000"))
    SPINNER_WAIT_TIMEOUT: int = int(os.getenv("SPINNER_WAIT_TIMEOUT_MS", "3000"))
    SPA_STABILIZE_DELAY: float = float(os.getenv("SPA_STABILIZE_DELAY_S", "0.4"))

    # Post-action settle delays (seconds)
    CLICK_SETTLE: float = float(os.getenv("CLICK_SETTLE_S", "0.6"))
    FILL_SETTLE: float = float(os.getenv("FILL_SETTLE_S", "0.3"))
    SCROLL_SETTLE: float = float(os.getenv("SCROLL_SETTLE_S", "0.5"))

    # Debug / headed mode
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"
