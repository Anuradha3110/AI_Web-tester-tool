"""Multi-strategy locator engine with semantic fallback recovery.

Priority order (per spec):
  1. get_by_role   2. get_by_label   3. get_by_placeholder   4. data-testid
  5. text          6. CSS selector   7. XPath (last resort)

When the primary locator fails, find_semantic_alternative() suggests
synonymous labels for common action words (Submit -> Save, Continue ...).
"""
import logging
import re
from typing import Optional, Tuple

_log = logging.getLogger("LocatorManager")

# Semantic synonyms for common interactive labels
_SYNONYMS: dict[str, list[str]] = {
    "submit": ["Continue", "Proceed", "Save", "Confirm", "Send", "Apply", "Next", "OK", "Done"],
    "login": ["Sign in", "Log in", "Enter", "Access", "Go"],
    "signin": ["Sign in", "Log in", "Enter", "Access"],
    "signup": ["Register", "Create account", "Join", "Get started", "Sign up"],
    "register": ["Sign up", "Create account", "Join"],
    "next": ["Continue", "Proceed", "Forward", "→", "Go"],
    "back": ["Previous", "Return", "←", "Go back"],
    "cancel": ["Close", "Dismiss", "Exit", "Discard", "No"],
    "delete": ["Remove", "Clear", "Discard", "Trash"],
    "save": ["Submit", "Apply", "Update", "Confirm", "OK"],
    "search": ["Find", "Go", "Look up", "Query"],
    "close": ["Dismiss", "Cancel", "Exit", "×", "✕"],
    "ok": ["Confirm", "Yes", "Accept", "Got it", "Continue"],
    "confirm": ["OK", "Yes", "Accept", "Proceed"],
    "proceed": ["Continue", "Next", "OK", "Go", "Submit"],
}

# Regex patterns that identify a CSS/XPath selector vs a plain text label
_CSS_PATTERN = re.compile(r'[\[#(>+~]|^\.|:[\w-]+\(|^//|^\*')


def is_css_selector(selector: str) -> bool:
    return bool(_CSS_PATTERN.search(selector))


class LocatorManager:
    def __init__(self, page):
        self.page = page

    async def resolve(self, selector: str, role_hint: str = "any") -> Optional[object]:
        """Return the first matching locator across all strategies, or None."""
        strategies = self._strategies(selector, role_hint)

        for name, loc in strategies:
            try:
                count = await loc.count()
                if count > 0:
                    _log.debug("Locator [%s] resolved for: %s", name, selector[:60])
                    return loc.first
            except Exception:
                continue

        _log.debug("No locator resolved for: %s", selector[:60])
        return None

    def _strategies(self, selector: str, role_hint: str) -> list[Tuple[str, object]]:
        """Build ordered list of (name, locator) pairs."""
        p = self.page
        strategies = []

        if is_css_selector(selector):
            # Direct CSS / XPath — try the most specific first
            strategies += [
                ("css_direct", p.locator(selector)),
                ("css_first", p.locator(selector).first),
            ]
        else:
            # Semantic / text selectors — priority order per spec
            strategies += [
                ("role_button_exact", p.get_by_role("button", name=selector, exact=True)),
                ("role_link_exact", p.get_by_role("link", name=selector, exact=True)),
                ("role_button_fuzzy", p.get_by_role("button", name=selector, exact=False)),
                ("role_link_fuzzy", p.get_by_role("link", name=selector, exact=False)),
                ("label_exact", p.get_by_label(selector, exact=True)),
                ("label_fuzzy", p.get_by_label(selector, exact=False)),
                ("placeholder", p.get_by_placeholder(selector)),
                ("testid", p.get_by_test_id(selector)),
                ("text_exact", p.get_by_text(selector, exact=True)),
                ("text_fuzzy", p.get_by_text(selector, exact=False)),
                ("css_text", p.locator(f"text={selector}")),
            ]

            if role_hint == "input":
                strategies += [
                    ("role_textbox", p.get_by_role("textbox", name=selector)),
                    ("role_combobox", p.get_by_role("combobox", name=selector)),
                    ("role_spinbutton", p.get_by_role("spinbutton", name=selector)),
                ]

            if role_hint == "checkbox":
                strategies += [
                    ("role_checkbox", p.get_by_role("checkbox", name=selector)),
                ]

        return strategies

    async def find_semantic_alternative(self, selector: str) -> Optional[str]:
        """Search for a visible element that is semantically equivalent to *selector*."""
        lower = selector.lower().strip()

        for keyword, alternatives in _SYNONYMS.items():
            if keyword in lower:
                for alt in alternatives:
                    if alt.lower() == lower:
                        continue  # skip identical
                    try:
                        loc = self.page.get_by_text(alt, exact=False)
                        if await loc.count() > 0:
                            _log.info("Semantic alt '%s' → '%s'", selector, alt)
                            return alt
                    except Exception:
                        continue

        return None

    async def inspect_interactive_elements(self) -> list:
        """Return a snapshot of visible interactive elements for recovery / debugging."""
        try:
            return await self.page.evaluate("""
                () => {
                    const sel = 'button, a[href], input, select, textarea, [role="button"], [role="link"]';
                    return [...document.querySelectorAll(sel)]
                        .filter(el => el.offsetParent !== null)
                        .slice(0, 25)
                        .map(el => ({
                            tag:  el.tagName,
                            text: el.textContent.trim().substring(0, 50),
                            id:   el.id || null,
                            name: el.getAttribute('name') || null,
                            type: el.type || null,
                            role: el.getAttribute('role') || null,
                        }));
                }
            """)
        except Exception:
            return []
