"""Screenshot and failure-capture system.

Captures screenshots on demand, and on failure also grabs page HTML,
console errors, and network errors so every incident is fully documented.
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

_log = logging.getLogger("ScreenshotManager")


class ScreenshotManager:
    def __init__(self, page, screenshots_dir: str):
        self.page = page
        self.dir = Path(screenshots_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._console_logs: list = []
        self._network_errors: list = []
        self._setup_listeners()

    # ------------------------------------------------------------------
    # Event listeners (set up once, run passively)
    # ------------------------------------------------------------------

    def _setup_listeners(self):
        self.page.on("console", self._on_console)
        self.page.on("requestfailed", self._on_request_failed)

    def _on_console(self, msg):
        if msg.type in ("error", "warning"):
            self._console_logs.append({
                "type": msg.type,
                "text": msg.text,
                "ts": datetime.now().isoformat(),
            })

    def _on_request_failed(self, request):
        self._network_errors.append({
            "url": request.url,
            "failure": request.failure,
            "ts": datetime.now().isoformat(),
        })

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def capture(self, name: str) -> str:
        """Take a screenshot; return the full file path (empty string on error)."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self.dir / f"{name}_{ts}.png"
        try:
            await self.page.screenshot(path=str(path), full_page=False)
            _log.debug("Screenshot: %s", path.name)
            return str(path)
        except Exception as exc:
            _log.warning("Screenshot failed (%s): %s", name, exc)
            return ""

    async def capture_failure(self, context: str) -> dict:
        """Capture screenshot + HTML + logs for a failure event."""
        screenshot = await self.capture(f"failure_{context[:30]}")

        html_path = ""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            html_file = self.dir / f"failure_{context[:30]}_{ts}.html"
            content = await self.page.content()
            html_file.write_text(content, encoding="utf-8")
            html_path = str(html_file)
        except Exception as exc:
            _log.warning("HTML capture failed: %s", exc)

        return {
            "screenshot": screenshot,
            "html": html_path,
            "console_errors": self._console_logs[-10:],
            "network_errors": self._network_errors[-10:],
        }

    def get_console_errors(self) -> list:
        return [e for e in self._console_logs if e["type"] == "error"]

    def get_network_errors(self) -> list:
        return list(self._network_errors)

    def clear(self):
        self._console_logs.clear()
        self._network_errors.clear()
