"""BrowserController — production-grade Playwright automation wrapper.

All public methods preserve the same interface as the original browser.py so
existing agent.py code continues to work without changes.  Internally, every
operation now flows through the modular automation subsystems:

  WaitManager        → stable page-ready detection
  RetryManager       → exponential-backoff retries
  LocatorManager     → multi-strategy locator resolution
  SmartClickEngine   → resilient click with full recovery pipeline
  PopupHandler       → automatic popup/overlay dismissal
  IframeHandler      → cross-frame element search
  ScrollHandler      → viewport-aware scrolling
  ScreenshotManager  → screenshot + failure capture
  ValidationEngine   → assertion helpers
  AIRecoveryEngine   → self-healing action flow
"""
import asyncio
import logging
import os
import re
from datetime import datetime

from playwright.async_api import async_playwright, Browser, Page

from automation.config import AutomationConfig
from automation.wait_manager import WaitManager
from automation.retry_manager import RetryManager
from automation.locator_manager import LocatorManager, is_css_selector
from automation.screenshot_manager import ScreenshotManager
from automation.scroll_handler import ScrollHandler
from automation.popup_handler import PopupHandler
from automation.iframe_handler import IframeHandler
from automation.smart_click import SmartClickEngine
from automation.validation_engine import ValidationEngine
from automation.ai_recovery import AIRecoveryEngine

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_SCREENSHOTS_DIR = os.path.join(_BASE_DIR, "screenshots")

logger = logging.getLogger(__name__)


class BrowserController:
    def __init__(self, headless: bool = True, slow_mo: int = 0):
        self.headless = headless
        self.slow_mo = slow_mo
        self.playwright = None
        self.browser: Browser = None
        self.page: Page = None
        self.screenshots_dir = _SCREENSHOTS_DIR
        os.makedirs(self.screenshots_dir, exist_ok=True)

        # Automation modules — initialised in start()
        self.cfg: AutomationConfig = AutomationConfig()
        self.wait_mgr: WaitManager = None
        self.retry_mgr: RetryManager = None
        self.locator_mgr: LocatorManager = None
        self.screenshot_mgr: ScreenshotManager = None
        self.scroll_hdlr: ScrollHandler = None
        self.popup_hdlr: PopupHandler = None
        self.iframe_hdlr: IframeHandler = None
        self.smart_click: SmartClickEngine = None
        self.validation: ValidationEngine = None
        self.ai_recovery: AIRecoveryEngine = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        """Launch browser and wire up all automation subsystems."""
        # Servers without a display (e.g. Render) cannot run headed Chrome
        if not os.environ.get("DISPLAY"):
            self.headless = True

        self.playwright = await async_playwright().start()

        if self.headless:
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                slow_mo=self.slow_mo,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                timeout=30000,
            )
        else:
            try:
                self.browser = await self.playwright.chromium.launch(
                    headless=False,
                    slow_mo=self.slow_mo,
                    channel="msedge",
                    timeout=30000,
                )
            except Exception:
                # Fallback to bundled Chromium if Edge is unavailable
                self.browser = await self.playwright.chromium.launch(
                    headless=False,
                    slow_mo=self.slow_mo,
                    timeout=30000,
                )

        context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self.page = await context.new_page()

        # Apply global timeouts from config
        self.page.set_default_timeout(self.cfg.DEFAULT_TIMEOUT)
        self.page.set_default_navigation_timeout(self.cfg.DEFAULT_NAV_TIMEOUT)

        self._init_modules()
        logger.info("Browser started (headless=%s, slow_mo=%d)", self.headless, self.slow_mo)

    def _init_modules(self):
        """Instantiate and wire all automation modules."""
        self.wait_mgr = WaitManager(self.page, self.cfg)
        self.retry_mgr = RetryManager(
            max_retries=self.cfg.MAX_RETRIES,
            base_delay=self.cfg.RETRY_BASE_DELAY,
            max_delay=self.cfg.RETRY_MAX_DELAY,
        )
        self.locator_mgr = LocatorManager(self.page)
        self.screenshot_mgr = ScreenshotManager(self.page, self.screenshots_dir)
        self.scroll_hdlr = ScrollHandler(self.page, self.cfg)
        self.popup_hdlr = PopupHandler(self.page)
        self.iframe_hdlr = IframeHandler(self.page)
        self.smart_click = SmartClickEngine(
            page=self.page,
            locator_manager=self.locator_mgr,
            wait_manager=self.wait_mgr,
            retry_manager=self.retry_mgr,
            popup_handler=self.popup_hdlr,
            iframe_handler=self.iframe_hdlr,
            scroll_handler=self.scroll_hdlr,
            screenshot_manager=self.screenshot_mgr,
            config=self.cfg,
        )
        self.validation = ValidationEngine(self.page, self.screenshot_mgr)
        self.ai_recovery = AIRecoveryEngine(
            page=self.page,
            locator_manager=self.locator_mgr,
            scroll_handler=self.scroll_hdlr,
            popup_handler=self.popup_hdlr,
            iframe_handler=self.iframe_hdlr,
            screenshot_manager=self.screenshot_mgr,
        )

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser stopped")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    async def go_to(self, url: str):
        """Navigate to *url* and wait for the page to be fully ready."""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        await self.retry_mgr.run(
            lambda: self.page.goto(url, wait_until="domcontentloaded",
                                   timeout=self.cfg.DEFAULT_NAV_TIMEOUT),
            label=f"navigate({url[:60]})",
        )
        await self.wait_mgr.for_page_ready()
        # Dismiss any immediate popups (cookie banners, etc.)
        await self.popup_hdlr.dismiss_popups()
        logger.info("Navigated to: %s", url)

    # ------------------------------------------------------------------
    # Selector utilities (kept for backward-compat; SmartClick uses LocatorManager)
    # ------------------------------------------------------------------

    def _is_css_selector(self, selector: str) -> bool:
        return is_css_selector(selector)

    def _normalize_selector(self, selector: str) -> str:
        return re.sub(r":contains\(['\"](.+?)['\"]\)", r":has-text('\1')", selector)

    # ------------------------------------------------------------------
    # Click
    # ------------------------------------------------------------------

    async def click(self, selector: str):
        """Smart click with full recovery pipeline."""
        selector = self._normalize_selector(selector)
        try:
            await self.smart_click.click(selector)
        except Exception as exc:
            # Let AIRecoveryEngine attempt self-healing
            recovered = await self.ai_recovery.recover("click", selector, exc)
            if not recovered:
                raise
            # Try once more after recovery
            await self.smart_click.click(selector)

    # ------------------------------------------------------------------
    # Type / fill
    # ------------------------------------------------------------------

    async def type(self, selector: str, text: str):
        """Fill an input field using multi-strategy locator resolution."""
        selector = self._normalize_selector(selector)

        async def _do_type():
            # Use input-role hint for better locator resolution
            loc = await self.locator_mgr.resolve(selector, role_hint="input")

            # Extra fallbacks for text selectors that don't match roles
            if loc is None and not is_css_selector(selector):
                for candidate in [
                    self.page.get_by_placeholder(selector),
                    self.page.get_by_label(selector, exact=False),
                    self.page.locator(
                        f'input[name*="{selector}"], textarea[name*="{selector}"]'
                    ),
                ]:
                    try:
                        if await candidate.count() > 0:
                            loc = candidate.first
                            break
                    except Exception:
                        continue

            if loc is None:
                raise RuntimeError(f"Could not resolve input locator: {selector!r}")

            await self.wait_mgr.for_element_ready(loc)
            await self.scroll_hdlr.into_view(loc)
            await loc.fill(text, timeout=self.cfg.FILL_TIMEOUT)
            await asyncio.sleep(self.cfg.FILL_SETTLE)

        await self.retry_mgr.run(_do_type, label=f"type({selector[:40]})")

    # ------------------------------------------------------------------
    # Check / assert
    # ------------------------------------------------------------------

    async def check(self, selector: str, expected_value: str = None) -> bool:
        """Verify element state or page text. Returns True if assertion passes."""
        try:
            if is_css_selector(selector):
                visible = await self.validation.check_element_visible(selector)
                if visible and expected_value:
                    try:
                        txt = await self.page.locator(selector).first.inner_text()
                        return expected_value.lower() in txt.lower()
                    except Exception:
                        pass
                return visible
            # Text-based check
            return await self.validation.check_text_visible(selector)
        except Exception:
            # Fallback: full body text search
            try:
                body = await self.page.inner_text("body")
                return (expected_value or selector).lower() in body.lower()
            except Exception:
                return False

    # ------------------------------------------------------------------
    # Scroll
    # ------------------------------------------------------------------

    async def scroll(self, direction: str = "down"):
        await self.scroll_hdlr.scroll_page(direction)

    # ------------------------------------------------------------------
    # Wait
    # ------------------------------------------------------------------

    async def wait_for(self, selector: str, timeout: int = 10000):
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
        except Exception:
            await asyncio.sleep(2)

    # ------------------------------------------------------------------
    # Hover
    # ------------------------------------------------------------------

    async def hover(self, selector: str):
        loc = await self.locator_mgr.resolve(selector)
        if loc:
            await loc.hover(timeout=5000)
            await asyncio.sleep(0.3)
        else:
            # Best-effort fallback
            await self.page.hover(selector, timeout=5000)
            await asyncio.sleep(0.3)

    # ------------------------------------------------------------------
    # Select / dropdown
    # ------------------------------------------------------------------

    async def select_option(self, selector: str, value: str):
        """Select a dropdown option by label with locator resolution."""
        async def _do_select():
            loc = await self.locator_mgr.resolve(selector, role_hint="input")
            if loc is None:
                loc = self.page.locator("select").first
            await loc.select_option(label=value, timeout=self.cfg.WAIT_TIMEOUT)
            await asyncio.sleep(0.3)

        await self.retry_mgr.run(_do_select, label=f"select({selector[:40]}={value})")

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    async def screenshot(self, name: str) -> str:
        return await self.screenshot_mgr.capture(name)

    # ------------------------------------------------------------------
    # Page content (for AI consumption)
    # ------------------------------------------------------------------

    async def get_page_content(self) -> str:
        """Return cleaned, truncated page HTML suitable for sending to the LLM."""
        try:
            content = await self.page.content()
            content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
            content = re.sub(r"\s+", " ", content)
            return content[:3000]  # slightly wider window than original 2000
        except Exception:
            return ""

    async def get_current_url(self) -> str:
        return self.page.url

    # ------------------------------------------------------------------
    # Failure snapshot (used by agent for richer error reporting)
    # ------------------------------------------------------------------

    async def capture_failure_snapshot(self, context: str) -> dict:
        return await self.screenshot_mgr.capture_failure(context)
