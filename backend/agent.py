import asyncio
import json
import logging
import os
import re
import traceback
from datetime import datetime
from typing import Optional

from anthropic import Anthropic

from browser import BrowserController

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an expert web testing assistant with deep knowledge of HTML, CSS, and browser automation.

Your job: Given a URL, a test goal, and the current page state, decide the SINGLE BEST next browser action.

IMPORTANT: Respond ONLY with a valid JSON object — no extra text, no markdown fences.

JSON format:
{
  "action": "<action_type>",
  "target": "<css_selector_or_text>",
  "value": "<text_value_if_needed>",
  "reasoning": "<one sentence explaining why>",
  "is_complete": false,
  "verdict": null
}

Action types:
- "go_to"    : Navigate to URL (target = full URL)
- "click"    : Click element (target = CSS selector OR visible text)
- "type"     : Type into field (target = CSS selector, value = text to enter)
- "check"    : Verify element/text exists (target = selector or text, value = expected text if any)
- "scroll"   : Scroll page (target = "down" or "up")
- "wait"     : Wait for element (target = CSS selector)
- "hover"    : Hover over element (target = CSS selector)
- "select"   : Choose dropdown option (target = selector, value = option label)
- "done"     : Mark test complete — set is_complete=true and verdict="PASSED" or "FAILED"

Selector tips:
- Prefer: input[type="email"], input[name="password"], button[type="submit"]
- For text: use visible text like "Login", "Sign In", "Submit"
- Check forms: look for placeholder or label text to identify correct inputs

When the goal is met or you are certain it passed/failed, respond with action="done", is_complete=true, verdict="PASSED" or "FAILED"."""


class WebTestingAgent:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-haiku-4-5-20251001"
        self.max_steps = 15

    async def run(
        self,
        url: str,
        goal: str,
        credentials: Optional[dict] = None,
        headless: bool = True,
        slow_mo: int = 0,
        on_log=None,
        stop_event: asyncio.Event = None,
    ) -> dict:
        browser = BrowserController(headless=headless, slow_mo=slow_mo)
        steps = []
        start_time = datetime.now()

        async def emit(event_type: str, **data):
            if on_log:
                try:
                    await on_log({"type": event_type, **data})
                except Exception:
                    pass

        try:
            await browser.start()
            await browser.go_to(url)
            screenshot_path = await browser.screenshot("step_0_initial")

            await emit("start", url=url, goal=goal)

            conversation: list = []

            for step_num in range(self.max_steps):
                # Check for stop signal before starting each new step
                if stop_event and stop_event.is_set():
                    duration = (datetime.now() - start_time).total_seconds()
                    await emit("stopped", message="Test stopped by user", total_steps=len(steps), duration=round(duration, 2))
                    return self._build_result(url, goal, steps, "STOPPED", start_time, "Stopped by user")

                page_html = await browser.get_page_content()
                page_url = await browser.get_current_url()

                cred_hint = (
                    f"\nAvailable credential keys: {list(credentials.keys())}"
                    if credentials
                    else ""
                )
                user_text = (
                    f"Test Goal: {goal}\n"
                    f"Current URL: {page_url}\n"
                    f"Step: {step_num + 1}/{self.max_steps}"
                    f"{cred_hint}\n\n"
                    f"Page HTML (truncated):\n{page_html}"
                )

                conversation.append({"role": "user", "content": user_text})

                # Keep only the last 4 messages; Anthropic requires starting with a user turn
                trimmed = conversation[-4:]
                if trimmed and trimmed[0]["role"] != "user":
                    trimmed = trimmed[1:]
                response = await asyncio.to_thread(
                    self.client.messages.create,
                    model=self.model,
                    max_tokens=512,
                    system=SYSTEM_PROMPT,
                    messages=trimmed,
                )

                ai_text = response.content[0].text.strip()
                conversation.append({"role": "assistant", "content": ai_text})

                decision = self._parse_decision(ai_text)

                await emit(
                    "step",
                    step=step_num + 1,
                    action=decision.get("action", ""),
                    target=str(decision.get("target", "")),
                    value=str(decision.get("value", "") or ""),
                    reasoning=decision.get("reasoning", ""),
                    url=page_url,
                )

                action_result = await self._execute_action(browser, decision, credentials)

                screenshot_path = await browser.screenshot(f"step_{step_num + 1}")

                current_url = await browser.get_current_url()
                await emit(
                    "step_done",
                    step=step_num + 1,
                    status="passed" if action_result["success"] else "failed",
                    error=action_result.get("error"),
                    url=current_url,
                )

                steps.append(
                    {
                        "step": step_num + 1,
                        "action": decision.get("action"),
                        "target": decision.get("target"),
                        "value": decision.get("value"),
                        "reasoning": decision.get("reasoning"),
                        "status": "passed" if action_result["success"] else "failed",
                        "error": action_result.get("error"),
                        "screenshot": screenshot_path,
                    }
                )

                if decision.get("is_complete"):
                    verdict = decision.get("verdict", "FAILED")
                    duration = (datetime.now() - start_time).total_seconds()
                    await emit("done", verdict=verdict, total_steps=len(steps), duration=round(duration, 2))
                    return self._build_result(url, goal, steps, verdict, start_time)

                if not action_result["success"]:
                    conversation.append(
                        {
                            "role": "user",
                            "content": (
                                f"The previous action failed: {action_result.get('error')}. "
                                "Please try a different selector or approach."
                            ),
                        }
                    )

            duration = (datetime.now() - start_time).total_seconds()
            await emit("done", verdict="FAILED", total_steps=len(steps), duration=round(duration, 2))
            return self._build_result(url, goal, steps, "FAILED", start_time, "Max steps reached")

        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("Agent run failed:\n%s", tb)
            error_msg = str(exc) if str(exc) else f"{type(exc).__name__}: {tb.splitlines()[-1]}"
            await emit("error", message=error_msg)
            return self._build_result(url, goal, steps, "ERROR", start_time, error_msg)
        finally:
            try:
                await browser.stop()
            except Exception:
                pass

    def _parse_decision(self, text: str) -> dict:
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract the first JSON object
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return {
            "action": "done",
            "is_complete": True,
            "verdict": "FAILED",
            "reasoning": f"Could not parse AI response: {text[:200]}",
        }

    async def _execute_action(
        self,
        browser: BrowserController,
        decision: dict,
        credentials: Optional[dict],
    ) -> dict:
        action = (decision.get("action") or "").lower()
        target = decision.get("target", "")
        value = decision.get("value", "") or ""

        # Substitute credential placeholders like {username}, {password}
        if credentials:
            for key, val in credentials.items():
                value = value.replace(f"{{{key}}}", val)
                target = target.replace(f"{{{key}}}", val)

        try:
            if action == "go_to":
                await browser.go_to(target)
            elif action == "click":
                await browser.click(target)
            elif action == "type":
                await browser.type(target, value)
            elif action == "check":
                passed = await browser.check(target, value or None)
                if not passed:
                    return {"success": False, "error": f"Check failed: '{target}' not found"}
            elif action == "scroll":
                await browser.scroll(target or "down")
            elif action == "wait":
                await browser.wait_for(target)
            elif action == "hover":
                await browser.hover(target)
            elif action == "select":
                await browser.select_option(target, value)
            elif action == "done":
                pass
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _build_result(
        self,
        url: str,
        goal: str,
        steps: list,
        verdict: str,
        start_time: datetime,
        error: str = None,
    ) -> dict:
        duration = (datetime.now() - start_time).total_seconds()
        passed = sum(1 for s in steps if s["status"] == "passed")
        failed = sum(1 for s in steps if s["status"] == "failed")

        report = {
            "url": url,
            "goal": goal,
            "verdict": verdict,
            "total_steps": len(steps),
            "passed_steps": passed,
            "failed_steps": failed,
            "duration_seconds": round(duration, 2),
            "steps_summary": [
                {
                    "step": s["step"],
                    "action": s["action"],
                    "status": s["status"],
                    "reasoning": s["reasoning"],
                }
                for s in steps
            ],
        }

        return {
            "status": "completed" if verdict in ("PASSED", "FAILED") else verdict.lower(),
            "final_verdict": verdict,
            "steps": steps,
            "screenshot_paths": [s["screenshot"] for s in steps if s.get("screenshot")],
            "duration": duration,
            "url": url,
            "goal": goal,
            "error": error,
            "report": report,
        }
