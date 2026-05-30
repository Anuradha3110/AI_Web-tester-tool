"""AI Recovery Engine — self-healing action flow.

When automation fails this engine runs a structured recovery pipeline
before allowing the error to propagate:

  wait → scroll → hover → dismiss_popups → check_iframe
       → semantic_alternative → dom_analysis

Only after all strategies are exhausted does the engine declare failure,
at which point it captures a full failure snapshot for debugging.
"""
import asyncio
import logging
from typing import Optional, Callable

from automation.locator_manager import LocatorManager
from automation.scroll_handler import ScrollHandler
from automation.popup_handler import PopupHandler
from automation.iframe_handler import IframeHandler
from automation.screenshot_manager import ScreenshotManager

_log = logging.getLogger("AIRecovery")


class AIRecoveryEngine:
    def __init__(
        self,
        page,
        locator_manager: LocatorManager,
        scroll_handler: ScrollHandler,
        popup_handler: PopupHandler,
        iframe_handler: IframeHandler,
        screenshot_manager: ScreenshotManager,
    ):
        self.page = page
        self.lm = locator_manager
        self.sh = scroll_handler
        self.ph = popup_handler
        self.ih = iframe_handler
        self.sm = screenshot_manager

    async def recover(
        self,
        action: str,
        selector: str,
        error: Exception,
        on_log: Optional[Callable] = None,
    ) -> bool:
        """Run the full self-healing pipeline. Returns True if recovery likely succeeded."""
        _log.warning("Recovery started for %s(%s): %s", action, selector[:60], error)

        steps = [
            ("wait",               self._step_wait),
            ("scroll",             lambda: self._step_scroll(selector)),
            ("hover",              lambda: self._step_hover(selector)),
            ("dismiss_popups",     self._step_dismiss_popups),
            ("check_iframe",       lambda: self._step_iframe(selector)),
            ("semantic_alt",       lambda: self._step_semantic(selector)),
            ("dom_analysis",       lambda: self._step_dom_analysis(selector)),
        ]

        for name, fn in steps:
            try:
                result = await fn()
                if on_log:
                    await on_log({"type": "recovery", "strategy": name, "result": result})
                _log.info("Recovery step [%s] → %s", name, "OK" if result else "miss")
                if result:
                    return True
            except Exception as exc:
                _log.debug("Recovery step [%s] raised: %s", name, exc)

        # Capture full failure snapshot
        try:
            await self.sm.capture_failure(f"{action}_{selector[:20]}")
        except Exception:
            pass

        _log.error("Recovery exhausted for %s(%s)", action, selector[:60])
        return False

    # ------------------------------------------------------------------
    # Individual recovery steps
    # ------------------------------------------------------------------

    async def _step_wait(self) -> bool:
        """Wait a moment for async rendering to settle."""
        await asyncio.sleep(2.0)
        return False  # wait alone doesn't confirm recovery; let pipeline continue

    async def _step_scroll(self, selector: str) -> bool:
        await self.sh.scroll_page("down", 400)
        loc = await self.lm.resolve(selector)
        if loc:
            return await loc.is_visible()
        return False

    async def _step_hover(self, selector: str) -> bool:
        loc = await self.lm.resolve(selector)
        if loc:
            try:
                await loc.hover(timeout=3000)
                await asyncio.sleep(0.5)
                return True
            except Exception:
                pass
        return False

    async def _step_dismiss_popups(self) -> bool:
        return await self.ph.dismiss_popups()

    async def _step_iframe(self, selector: str) -> bool:
        frame, loc = await self.ih.find_in_frames(selector)
        if frame and loc:
            _log.info("Element found inside iframe: %s", frame.url[:80])
            return True
        return False

    async def _step_semantic(self, selector: str) -> bool:
        alt = await self.lm.find_semantic_alternative(selector)
        if alt:
            _log.info("Semantic alternative found: '%s' → '%s'", selector[:40], alt)
            return True
        return False

    async def _step_dom_analysis(self, selector: str) -> bool:
        """Inspect interactive elements and log them; aids AI in next decision."""
        elements = await self.lm.inspect_interactive_elements()
        if elements:
            _log.info(
                "DOM analysis: %d interactive elements visible. First 5: %s",
                len(elements),
                [e.get("text", "") for e in elements[:5]],
            )
        # DOM analysis is informational — the AI loop uses the info, not this engine
        return False
