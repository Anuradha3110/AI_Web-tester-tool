"""Universal page-ready system.

Provides reusable helpers that wait for DOM stability, spinner disappearance,
and SPA rendering before critical interactions.  All public methods are safe to
call even when the relevant selectors are absent – they degrade gracefully.
"""
import asyncio
import logging

from automation.config import AutomationConfig

_log = logging.getLogger("WaitManager")

# Common loading-indicator selectors across popular UI frameworks
_SPINNER_SELECTORS = [
    "[class*='loading']:not(body)",
    "[class*='spinner']",
    "[class*='loader']:not(img)",
    "[aria-busy='true']",
    ".skeleton",
    "[class*='skeleton']",
    "[data-loading='true']",
]


class WaitManager:
    def __init__(self, page, config: AutomationConfig = None):
        self.page = page
        self.cfg = config or AutomationConfig()

    async def for_page_ready(self, timeout: int = None):
        """Wait for the page to reach a stable interactive state."""
        timeout = timeout or self.cfg.NETWORK_IDLE_TIMEOUT
        # domcontentloaded is guaranteed fast; networkidle may timeout on SPAs
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
        except Exception:
            pass
        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass
        await self._wait_for_spinners()
        await asyncio.sleep(self.cfg.SPA_STABILIZE_DELAY)

    async def _wait_for_spinners(self):
        """Wait for common loading indicators to disappear."""
        for sel in _SPINNER_SELECTORS:
            try:
                loc = self.page.locator(sel)
                count = await loc.count()
                if count:
                    await loc.first.wait_for(
                        state="hidden", timeout=self.cfg.SPINNER_WAIT_TIMEOUT
                    )
            except Exception:
                pass  # spinner not found or timed out – proceed

    async def for_element_ready(self, locator, timeout: int = None):
        """Wait for *locator* to be visible and enabled."""
        timeout = timeout or self.cfg.WAIT_TIMEOUT
        try:
            await locator.wait_for(state="visible", timeout=timeout)
        except Exception:
            pass
        try:
            await locator.wait_for(state="enabled", timeout=timeout)
        except Exception:
            pass

    async def for_navigation(self):
        """Wait after a navigation or SPA route change."""
        try:
            await self.page.wait_for_load_state("networkidle", timeout=self.cfg.NETWORK_IDLE_TIMEOUT)
        except Exception:
            await asyncio.sleep(self.cfg.SPA_STABILIZE_DELAY)
