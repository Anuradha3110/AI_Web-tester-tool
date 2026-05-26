import asyncio
import os
import re
from datetime import datetime
from playwright.async_api import async_playwright, Browser, Page


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class BrowserController:
    def __init__(self, headless: bool = True, slow_mo: int = 0):
        self.headless = headless
        self.slow_mo = slow_mo
        self.playwright = None
        self.browser: Browser = None
        self.page: Page = None
        self.screenshots_dir = os.path.join(_BASE_DIR, "screenshots")
        os.makedirs(self.screenshots_dir, exist_ok=True)

    async def start(self):
        self.playwright = await async_playwright().start()
        if self.headless:
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                slow_mo=self.slow_mo,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                timeout=30000,
            )
        else:
            # Use system Edge for headed mode on Windows — always available on Win11,
            # trusted by Defender, and avoids bundled Chromium GPU/init issues.
            self.browser = await self.playwright.chromium.launch(
                headless=False,
                slow_mo=self.slow_mo,
                channel="msedge",
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
        self.page.set_default_timeout(30000)

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def go_to(self, url: str):
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(1.5)

    def _is_css_selector(self, selector: str) -> bool:
        return bool(re.search(r'[\[#(>+~]|^\.|:[\w-]+\(', selector))

    def _normalize_selector(self, selector: str) -> str:
        # Convert jQuery :contains() to Playwright :has-text()
        return re.sub(r":contains\(['\"](.+?)['\"]\)", r":has-text('\1')", selector)

    async def click(self, selector: str):
        selector = self._normalize_selector(selector)
        is_css = self._is_css_selector(selector)

        if is_css:
            strategies = [
                lambda: self.page.click(selector, timeout=5000),
                lambda: self.page.locator(selector).first.click(timeout=5000),
                lambda: self._scroll_and_force_click_css(selector),
            ]
        else:
            strategies = [
                lambda: self.page.click(selector, timeout=5000),
                lambda: self.page.click(f"text={selector}", timeout=5000),
                lambda: self.page.get_by_text(selector, exact=True).first.click(timeout=5000),
                lambda: self.page.get_by_text(selector, exact=False).first.click(timeout=5000),
                lambda: self.page.get_by_role("button", name=selector, exact=True).first.click(timeout=5000),
                lambda: self.page.get_by_role("button", name=selector, exact=False).first.click(timeout=5000),
                lambda: self.page.get_by_role("link", name=selector, exact=True).first.click(timeout=5000),
                lambda: self.page.get_by_role("link", name=selector, exact=False).first.click(timeout=5000),
                lambda: self._scroll_and_force_click_text(selector),
            ]

        last_error = None
        for strategy in strategies:
            try:
                await strategy()
                await asyncio.sleep(0.8)
                return
            except Exception as e:
                last_error = e
        raise last_error

    async def _scroll_and_force_click_css(self, selector: str):
        locator = self.page.locator(selector).first
        await locator.scroll_into_view_if_needed(timeout=5000)
        await locator.click(force=True, timeout=5000)

    async def _scroll_and_force_click_text(self, selector: str):
        locator = self.page.get_by_text(selector, exact=False).first
        await locator.scroll_into_view_if_needed(timeout=5000)
        await locator.click(force=True, timeout=5000)

    async def type(self, selector: str, text: str):
        selector = self._normalize_selector(selector)
        is_css = self._is_css_selector(selector)

        if is_css:
            strategies = [
                lambda: self.page.fill(selector, text, timeout=5000),
                lambda: self.page.locator(selector).first.fill(text, timeout=5000),
                lambda: self._scroll_and_fill_css(selector, text),
            ]
        else:
            strategies = [
                lambda: self.page.fill(selector, text, timeout=5000),
                lambda: self.page.get_by_placeholder(selector).first.fill(text, timeout=5000),
                lambda: self.page.get_by_label(selector, exact=False).first.fill(text, timeout=5000),
                lambda: self._scroll_and_fill_text(selector, text),
            ]

        last_error = None
        for strategy in strategies:
            try:
                await strategy()
                await asyncio.sleep(0.3)
                return
            except Exception as e:
                last_error = e
        raise last_error

    async def _scroll_and_fill_css(self, selector: str, text: str):
        locator = self.page.locator(selector).first
        await locator.scroll_into_view_if_needed(timeout=5000)
        await locator.fill(text, force=True, timeout=5000)

    async def _scroll_and_fill_text(self, selector: str, text: str):
        locator = self.page.get_by_label(selector, exact=False).first
        await locator.scroll_into_view_if_needed(timeout=5000)
        await locator.fill(text, force=True, timeout=5000)

    async def check(self, selector: str, expected_value: str = None) -> bool:
        try:
            element = await self.page.query_selector(selector)
            if element:
                if expected_value:
                    text = await element.text_content() or ""
                    return expected_value.lower() in text.lower()
                return True
        except Exception:
            pass

        # Fallback: search page text content
        try:
            content = await self.page.inner_text("body")
            search_term = expected_value or selector
            return search_term.lower() in content.lower()
        except Exception:
            return False

    async def scroll(self, direction: str = "down"):
        if direction == "up":
            await self.page.evaluate("window.scrollBy(0, -600)")
        else:
            await self.page.evaluate("window.scrollBy(0, 600)")
        await asyncio.sleep(0.5)

    async def wait_for(self, selector: str, timeout: int = 10000):
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
        except Exception:
            await asyncio.sleep(2)

    async def hover(self, selector: str):
        await self.page.hover(selector, timeout=10000)
        await asyncio.sleep(0.3)

    async def select_option(self, selector: str, value: str):
        await self.page.select_option(selector, label=value, timeout=10000)
        await asyncio.sleep(0.3)

    async def screenshot(self, name: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{self.screenshots_dir}/{name}_{timestamp}.png"
        await self.page.screenshot(path=filename, full_page=False)
        return filename

    async def get_page_content(self) -> str:
        try:
            content = await self.page.content()
            # Strip scripts, styles, and comments to reduce token usage
            content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
            content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
            content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
            content = re.sub(r"\s+", " ", content)
            return content[:2000]
        except Exception:
            return ""

    async def get_current_url(self) -> str:
        return self.page.url
