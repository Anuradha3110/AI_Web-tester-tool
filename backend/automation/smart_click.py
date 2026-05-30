"""Smart click engine with full recovery pipeline.

Execution order per click attempt:
  1. Resolve locator (multi-strategy)
  2. Wait for element readiness
  3. Scroll into view
  4. Hover (wakes lazy-loaded tooltips / menus)
  5. Click (with retry via RetryManager)
  6. Post-click page stabilization

Recovery order when all normal clicks fail:
  1. Dismiss blocking popups and retry
  2. Try iframe search
  3. Try semantic alternative label
  4. Force click (bypasses pointer-events interception)
  5. JavaScript .click() as absolute last resort
"""
import asyncio
import logging
from typing import Optional

from automation.config import AutomationConfig
from automation.locator_manager import LocatorManager, is_css_selector
from automation.wait_manager import WaitManager
from automation.retry_manager import RetryManager
from automation.popup_handler import PopupHandler
from automation.iframe_handler import IframeHandler
from automation.scroll_handler import ScrollHandler

_log = logging.getLogger("SmartClick")


class SmartClickEngine:
    def __init__(
        self,
        page,
        locator_manager: LocatorManager,
        wait_manager: WaitManager,
        retry_manager: RetryManager,
        popup_handler: PopupHandler,
        iframe_handler: IframeHandler,
        scroll_handler: ScrollHandler,
        screenshot_manager=None,
        config: AutomationConfig = None,
    ):
        self.page = page
        self.lm = locator_manager
        self.wm = wait_manager
        self.rm = retry_manager
        self.ph = popup_handler
        self.ih = iframe_handler
        self.sh = scroll_handler
        self.sm = screenshot_manager
        self.cfg = config or AutomationConfig()

    async def click(self, selector: str) -> bool:
        """Execute a resilient click on *selector* through the full recovery pipeline."""
        _log.info("SmartClick: %s", selector[:80])

        # ── Normal path ──────────────────────────────────────────────
        try:
            locator = await self.lm.resolve(selector)
            if locator:
                await self.rm.run(
                    lambda loc=locator: self._do_click(loc),
                    label=f"click({selector[:40]})",
                    on_retry=self._on_click_retry,
                )
                return True
        except Exception as exc:
            _log.warning("Primary click failed: %s", exc)

        # ── Recovery pipeline ─────────────────────────────────────────

        # 1) Dismiss popups then retry
        dismissed = await self.ph.dismiss_popups()
        if dismissed:
            try:
                locator = await self.lm.resolve(selector)
                if locator:
                    await self._do_click(locator)
                    return True
            except Exception:
                pass

        # 2) Check iframes
        frame, iframe_loc = await self.ih.find_in_frames(
            selector, use_text=not is_css_selector(selector)
        )
        if iframe_loc:
            try:
                await iframe_loc.click(timeout=self.cfg.CLICK_TIMEOUT)
                await asyncio.sleep(self.cfg.CLICK_SETTLE)
                return True
            except Exception as exc:
                _log.warning("Iframe click failed: %s", exc)

        # 3) Semantic alternative
        alt = await self.lm.find_semantic_alternative(selector)
        if alt:
            alt_loc = await self.lm.resolve(alt)
            if alt_loc:
                try:
                    await self._do_click(alt_loc)
                    _log.info("Clicked semantic alternative: %s", alt)
                    return True
                except Exception:
                    pass

        # 4) Force click
        try:
            await self._force_click(selector)
            return True
        except Exception as exc:
            _log.warning("Force click failed: %s", exc)

        # 5) JS click
        try:
            await self._js_click(selector)
            return True
        except Exception as exc:
            _log.error("All click strategies exhausted for: %s | %s", selector[:60], exc)

        if self.sm:
            await self.sm.capture_failure(f"click_fail_{selector[:20]}")

        raise RuntimeError(f"click({selector!r}) failed after exhausting all strategies")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _do_click(self, locator):
        """Standard click: ready-check → scroll → hover → click → settle."""
        await self.wm.for_element_ready(locator)
        await self.sh.into_view(locator)
        try:
            await locator.hover(timeout=2000)
        except Exception:
            pass
        await locator.click(timeout=self.cfg.CLICK_TIMEOUT)
        await asyncio.sleep(self.cfg.CLICK_SETTLE)
        await self.wm.for_page_ready()

    async def _on_click_retry(self, attempt: int, error: Exception):
        """Called between retries; dismiss popups in case they appeared."""
        _log.debug("Click retry %d – dismissing popups", attempt)
        await self.ph.dismiss_popups()
        await asyncio.sleep(0.3)

    async def _force_click(self, selector: str):
        """Bypass pointer-events interception with force=True."""
        if is_css_selector(selector):
            await self.page.locator(selector).first.click(force=True, timeout=5000)
        else:
            await self.page.get_by_text(selector, exact=False).first.click(force=True, timeout=5000)
        await asyncio.sleep(self.cfg.CLICK_SETTLE)

    async def _js_click(self, selector: str):
        """Absolute last resort: JavaScript .click()."""
        if is_css_selector(selector):
            script = f"""
                (function() {{
                    const el = document.querySelector({selector!r});
                    if (el) {{ el.click(); return true; }}
                    return false;
                }})()
            """
        else:
            script = f"""
                (function() {{
                    const text = {selector!r}.toLowerCase();
                    const els = [...document.querySelectorAll(
                        'button, a, [role="button"], input[type="submit"]'
                    )];
                    const el = els.find(e => e.textContent.trim().toLowerCase().includes(text));
                    if (el) {{ el.click(); return true; }}
                    return false;
                }})()
            """
        result = await self.page.evaluate(script)
        if not result:
            raise RuntimeError(f"JS click found no element matching: {selector!r}")
        await asyncio.sleep(self.cfg.CLICK_SETTLE)
