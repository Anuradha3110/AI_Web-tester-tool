"""Advanced validation / assertion engine.

Provides checks for URL changes, visible text, toast messages, element
visibility, console errors, network failures, and basic accessibility.
All methods return bool (or list) and never raise — callers decide what
a False result means.
"""
import logging
from typing import Optional

_log = logging.getLogger("ValidationEngine")

_TOAST_SELECTORS = [
    "[class*='toast']",
    "[class*='snackbar']",
    "[class*='notification']",
    "[role='alert']",
    "[role='status']",
    "[class*='alert']",
    "[class*='banner']",
    "[class*='flash']",
    "[class*='message']:not(input):not(textarea)",
]


class ValidationEngine:
    def __init__(self, page, screenshot_manager=None):
        self.page = page
        self.sm = screenshot_manager

    async def check_url(self, pattern: str) -> bool:
        current = self.page.url
        result = pattern.lower() in current.lower()
        _log.debug("URL check '%s' in '%s' → %s", pattern, current, result)
        return result

    async def check_text_visible(self, text: str, timeout: int = 5000) -> bool:
        try:
            await self.page.get_by_text(text, exact=False).first.wait_for(
                state="visible", timeout=timeout
            )
            return True
        except Exception:
            # Fallback: page body text search
            try:
                body = await self.page.inner_text("body")
                return text.lower() in body.lower()
            except Exception:
                return False

    async def check_element_visible(self, selector: str) -> bool:
        try:
            return await self.page.locator(selector).first.is_visible()
        except Exception:
            return False

    async def check_element_exists(self, selector: str, timeout: int = 5000) -> bool:
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    async def check_toast(self, expected_text: Optional[str] = None, timeout: int = 5000) -> bool:
        """Return True if a toast/notification is visible (optionally matching *expected_text*)."""
        for sel in _TOAST_SELECTORS:
            try:
                loc = self.page.locator(sel)
                count = await loc.count()
                if count == 0:
                    continue
                first = loc.first
                if not await first.is_visible():
                    continue
                if expected_text:
                    txt = await first.inner_text()
                    if expected_text.lower() in txt.lower():
                        return True
                else:
                    return True
            except Exception:
                continue
        return False

    async def check_console_errors(self) -> list:
        return self.sm.get_console_errors() if self.sm else []

    async def check_network_errors(self) -> list:
        return self.sm.get_network_errors() if self.sm else []

    async def wait_for_api_response(self, url_pattern: str, timeout: int = 10000) -> bool:
        try:
            async with self.page.expect_response(
                lambda r: url_pattern in r.url, timeout=timeout
            ) as resp_info:
                response = await resp_info.value
                return response.ok
        except Exception:
            return False

    async def check_accessibility_basics(self) -> dict:
        """Very lightweight: count images without alt and unlabelled buttons."""
        try:
            images_no_alt: int = await self.page.eval_on_selector_all(
                "img:not([alt])", "els => els.length"
            )
            buttons_no_label: int = await self.page.eval_on_selector_all(
                "button:not([aria-label]):not([title])",
                "els => els.filter(el => !el.textContent.trim()).length",
            )
            return {"images_no_alt": images_no_alt, "unlabelled_buttons": buttons_no_label}
        except Exception as exc:
            return {"error": str(exc)}
