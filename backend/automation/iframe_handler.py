"""IFrame detection and interaction support.

Automatically searches all nested frames when an element cannot be found
in the main page context, enabling seamless interaction with embedded content
(payment widgets, OAuth forms, reCAPTCHA, embedded videos, etc.).
"""
import logging
from typing import Optional, Tuple

_log = logging.getLogger("IframeHandler")


class IframeHandler:
    def __init__(self, page):
        self.page = page

    async def find_in_frames(
        self, selector: str, use_text: bool = False
    ) -> Tuple[Optional[object], Optional[object]]:
        """Search *selector* across main page and all iframes.

        Returns (frame, locator) where frame is the Playwright Frame object
        that contains the element, or (None, None) if not found anywhere.
        """
        all_frames = self.page.frames

        for frame in all_frames:
            try:
                if use_text:
                    loc = frame.get_by_text(selector, exact=False)
                else:
                    loc = frame.locator(selector)

                count = await loc.count()
                if count > 0:
                    if frame != self.page.main_frame:
                        _log.info("Found '%s' in iframe: %s", selector[:50], frame.url[:80])
                    return frame, loc.first
            except Exception:
                continue

        return None, None

    async def find_by_role_in_frames(
        self, role: str, name: str
    ) -> Tuple[Optional[object], Optional[object]]:
        """Search by ARIA role+name across all frames."""
        for frame in self.page.frames:
            try:
                loc = frame.get_by_role(role, name=name)
                count = await loc.count()
                if count > 0:
                    return frame, loc.first
            except Exception:
                continue
        return None, None

    def get_frame_count(self) -> int:
        return len(self.page.frames)

    def get_frame_urls(self) -> list:
        return [f.url for f in self.page.frames]
