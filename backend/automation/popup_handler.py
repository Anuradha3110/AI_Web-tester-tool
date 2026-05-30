"""Popup / modal / overlay handling.

Detects and dismisses cookie banners, subscription popups, chat overlays,
login modals, notification prompts, and GDPR consent dialogs automatically
so they never block subsequent automation steps.
"""
import asyncio
import logging

_log = logging.getLogger("PopupHandler")

# Ordered from most specific to most generic to avoid false positives
_DISMISS_SELECTORS = [
    # Cookie / GDPR accept buttons
    "#accept-cookies", "#cookie-accept", "#cookieAccept",
    "button[id*='cookie'][id*='accept']",
    "button[id*='accept'][id*='cookie']",
    "button[class*='cookie-accept']",
    "button[class*='accept-cookie']",
    "[aria-label*='Accept all cookies']",
    "[aria-label*='Accept cookies']",
    "button[data-testid*='cookie']",
    ".gdpr-accept", "[id*='gdpr'] button",

    # Generic close / dismiss buttons
    "button[aria-label='Close']",
    "button[aria-label='Dismiss']",
    "button[aria-label='close']",
    "button[aria-label='dismiss']",
    "[data-dismiss='modal']",
    "[class*='modal-close']",
    "[class*='popup-close']",
    "[class*='overlay-close']",
    "[class*='dialog-close']",
    ".close-btn", ".btn-close",

    # Notification permission decline
    "button[class*='decline']",
    "button[class*='not-now']",
    "button[class*='no-thanks']",

    # Chat / intercom overlays
    "[class*='intercom-close']",
    "[class*='chat-close']",

    # Cookie banners by text
    "button:has-text('Accept all')",
    "button:has-text('Accept All')",
    "button:has-text('I agree')",
    "button:has-text('Got it')",
    "button:has-text('OK')",
    "button:has-text('Dismiss')",
    "button:has-text('No thanks')",
    "button:has-text('Not now')",
]


class PopupHandler:
    def __init__(self, page):
        self.page = page
        # Auto-dismiss native browser dialogs
        self.page.on("dialog", lambda dlg: asyncio.create_task(dlg.dismiss()))

    async def dismiss_popups(self) -> bool:
        """Scan and dismiss any visible popups. Returns True if at least one was dismissed."""
        dismissed = False

        for sel in _DISMISS_SELECTORS:
            try:
                loc = self.page.locator(sel)
                count = await loc.count()
                if count == 0:
                    continue
                el = loc.first
                if await el.is_visible():
                    await el.click(timeout=3000)
                    await asyncio.sleep(0.4)
                    _log.info("Dismissed popup: %s", sel)
                    dismissed = True
            except Exception:
                continue

        return dismissed

    async def has_blocking_overlay(self) -> bool:
        """Return True if a modal/overlay is currently blocking the page."""
        overlay_selectors = [
            "[class*='overlay']:not([hidden]):not([style*='display: none'])",
            "[class*='modal'][style*='display: block']",
            "[role='dialog']:not([aria-hidden='true'])",
        ]
        for sel in overlay_selectors:
            try:
                count = await self.page.locator(sel).count()
                if count > 0:
                    _log.debug("Blocking overlay detected: %s", sel)
                    return True
            except Exception:
                continue
        return False
