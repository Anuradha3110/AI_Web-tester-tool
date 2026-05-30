"""Scrolling and lazy-loading support.

Provides viewport-aware scrolling utilities so elements outside the initial
viewport are reliably reached before interaction.
"""
import asyncio
import logging

from automation.config import AutomationConfig

_log = logging.getLogger("ScrollHandler")


class ScrollHandler:
    def __init__(self, page, config: AutomationConfig = None):
        self.page = page
        self.cfg = config or AutomationConfig()

    async def into_view(self, locator):
        """Scroll element into the visible viewport."""
        try:
            await locator.scroll_into_view_if_needed(timeout=5000)
        except Exception as exc:
            _log.debug("scroll_into_view failed (%s), trying JS fallback", exc)
            try:
                handle = await locator.element_handle()
                if handle:
                    await self.page.evaluate(
                        "el => el.scrollIntoView({behavior: 'smooth', block: 'center'})", handle
                    )
            except Exception:
                pass

    async def scroll_page(self, direction: str = "down", amount: int = 600):
        """Scroll the whole page up or down by *amount* pixels."""
        delta = amount if direction == "down" else -amount
        await self.page.evaluate(f"window.scrollBy(0, {delta})")
        await asyncio.sleep(self.cfg.SCROLL_SETTLE)

    async def to_top(self):
        await self.page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(self.cfg.SCROLL_SETTLE)

    async def to_bottom(self):
        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(self.cfg.SCROLL_SETTLE)

    async def scroll_to_find(self, locator, max_scrolls: int = 5) -> bool:
        """Scroll repeatedly until *locator* becomes visible, or give up."""
        for _ in range(max_scrolls):
            try:
                if await locator.first.is_visible():
                    return True
            except Exception:
                pass
            await self.scroll_page("down", 400)
        return False

    async def handle_infinite_scroll(self, iterations: int = 3):
        """Trigger lazy-loaded content by scrolling to the bottom repeatedly."""
        for i in range(iterations):
            await self.to_bottom()
            await asyncio.sleep(1.0)
            _log.debug("Infinite scroll iteration %d/%d", i + 1, iterations)
