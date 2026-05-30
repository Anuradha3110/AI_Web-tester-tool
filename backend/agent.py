"""WebTestingAgent - AI-driven web automation orchestrator.

The agent runs an iterative loop:
  1. Capture current page state (HTML + URL)
  2. Ask the LLM for the next action (JSON)
  3. Execute the action via BrowserController
  4. Record result + screenshot
  5. On failure: feed error context back to LLM and continue

New in this version:
- StructuredLogger for typed, traceable log entries per run
- Interactive elements snapshot fed to LLM after a failed step
- Retry / recovery metadata stored in step result for DB persistence
- AI recovery feedback appended to conversation so the model self-corrects
"""
import asyncio
import json
import logging
import re
import traceback
import uuid
from datetime import datetime
from typing import Optional, List

from browser import BrowserController
from llm import LLMClient
from automation.logger import StructuredLogger

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
- "type"     : Type into field (target = CSS selector or label/placeholder text, value = text to type)
- "check"    : Verify element/text exists (target = selector or text, value = expected text if any)
- "scroll"   : Scroll page (target = "down" or "up")
- "wait"     : Wait for element (target = CSS selector)
- "hover"    : Hover over element (target = CSS selector or text)
- "select"   : Choose dropdown option (target = selector or label, value = option label)
- "done"     : Mark test complete — set is_complete=true and verdict="PASSED" or "FAILED"

Selector tips:
- Prefer semantic: input[type="email"], input[name="password"], button[type="submit"]
- For text labels: use the visible text like "Login", "Sign In", "Submit"
- If a step fails, try a completely different selector strategy
- Prefer get_by_role / label / placeholder over fragile XPath

When the goal is met or you are certain it passed/failed, respond with action="done", is_complete=true,
verdict="PASSED" or "FAILED"."""


class WebTestingAgent:
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_keys: Optional[List[str]] = None,
        custom_base_url: Optional[str] = None,
        provider_keys: Optional[dict] = None,
    ):
        self.llm = LLMClient(
            provider=provider,
            model=model,
            api_keys=api_keys,
            custom_base_url=custom_base_url,
            provider_keys=provider_keys,
        )
        self.max_steps = 15

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

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
        steps: list = []
        start_time = datetime.now()
        run_id = str(uuid.uuid4())
        slog = StructuredLogger(run_id, on_log=on_log)

        async def emit(event_type: str, **data):
            if on_log:
                try:
                    await on_log({"type": event_type, **data})
                except Exception:
                    pass

        try:
            await browser.start()
            await browser.go_to(url)
            await browser.screenshot("step_0_initial")

            await emit("start", url=url, goal=goal)
            slog.info(f"Test started — URL: {url}")

            conversation: list = []

            for step_num in range(self.max_steps):
                # ── Stop-signal check ────────────────────────────────
                if stop_event and stop_event.is_set():
                    duration = (datetime.now() - start_time).total_seconds()
                    await emit("stopped", message="Test stopped by user",
                               total_steps=len(steps), duration=round(duration, 2))
                    return self._build_result(url, goal, steps, "STOPPED", start_time, "Stopped by user")

                # ── Capture page state ───────────────────────────────
                page_html = await browser.get_page_content()
                page_url = await browser.get_current_url()

                cred_hint = (
                    f"\nAvailable credential keys: {list(credentials.keys())}"
                    if credentials else ""
                )
                user_text = (
                    f"Test Goal: {goal}\n"
                    f"Current URL: {page_url}\n"
                    f"Step: {step_num + 1}/{self.max_steps}"
                    f"{cred_hint}\n\n"
                    f"Page HTML (truncated):\n{page_html}"
                )

                conversation.append({"role": "user", "content": user_text})

                # Keep last 4 messages; Anthropic requires starting with user turn
                trimmed = conversation[-4:]
                if trimmed and trimmed[0]["role"] != "user":
                    trimmed = trimmed[1:]

                async def rotate_callback(msg: str):
                    await emit("error", message=msg)

                ai_text = await self.llm.generate_response(
                    system_prompt=SYSTEM_PROMPT,
                    messages=trimmed,
                    on_key_rotate=rotate_callback,
                )
                conversation.append({"role": "assistant", "content": ai_text})

                decision = self._parse_decision(ai_text)

                slog.action(
                    step_num + 1,
                    decision.get("action", ""),
                    str(decision.get("target", "")),
                    str(decision.get("value", "") or ""),
                    decision.get("reasoning", ""),
                )

                await emit(
                    "step",
                    step=step_num + 1,
                    action=decision.get("action", ""),
                    target=str(decision.get("target", "")),
                    value=str(decision.get("value", "") or ""),
                    reasoning=decision.get("reasoning", ""),
                    url=page_url,
                )

                # ── Execute action ───────────────────────────────────
                action_result = await self._execute_action(browser, decision, credentials, slog, step_num + 1)

                screenshot_path = await browser.screenshot(f"step_{step_num + 1}")
                current_url = await browser.get_current_url()

                await emit(
                    "step_done",
                    step=step_num + 1,
                    status="passed" if action_result["success"] else "failed",
                    error=action_result.get("error"),
                    url=current_url,
                )

                steps.append({
                    "step":          step_num + 1,
                    "action":        decision.get("action"),
                    "target":        decision.get("target"),
                    "value":         decision.get("value"),
                    "reasoning":     decision.get("reasoning"),
                    "status":        "passed" if action_result["success"] else "failed",
                    "error":         action_result.get("error"),
                    "screenshot":    screenshot_path,
                    "retry_count":   action_result.get("retry_count", 0),
                    "recovery":      action_result.get("recovery"),
                })

                # ── Completion check ─────────────────────────────────
                if decision.get("is_complete"):
                    verdict = decision.get("verdict", "FAILED")
                    duration = (datetime.now() - start_time).total_seconds()
                    await emit("done", verdict=verdict,
                               total_steps=len(steps), duration=round(duration, 2))
                    return self._build_result(url, goal, steps, verdict, start_time)

                # ── On failure: enrich next LLM turn with context ────
                if not action_result["success"]:
                    # Provide visible interactive elements to help the model choose better
                    elements = await browser.locator_mgr.inspect_interactive_elements()
                    elements_hint = ""
                    if elements:
                        elem_list = ", ".join(
                            f'"{e.get("text") or e.get("id") or e.get("name") or e.get("tag")}"'
                            for e in elements[:10]
                        )
                        elements_hint = f"\nVisible interactive elements: [{elem_list}]"

                    conversation.append({
                        "role": "user",
                        "content": (
                            f"The previous action failed: {action_result.get('error')}.\n"
                            f"Please try a completely different selector or approach.{elements_hint}"
                        ),
                    })

            # Max steps reached
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

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    async def _execute_action(
        self,
        browser: BrowserController,
        decision: dict,
        credentials: Optional[dict],
        slog: StructuredLogger,
        step_num: int,
    ) -> dict:
        action = (decision.get("action") or "").lower()
        target = decision.get("target", "") or ""
        value = decision.get("value", "") or ""

        # Substitute credential placeholders: {username}, {password}, …
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
                    return {"success": False, "error": f"Check failed: '{target}' not found or mismatch"}
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
            error_msg = str(exc)
            slog.failure(step_num, action, target, error_msg, recovery_attempted=True)

            # Attempt AI self-healing (browser already ran its own recovery internally)
            try:
                recovery_context = await browser.capture_failure_snapshot(
                    f"step{step_num}_{action}"
                )
                recovery_note = (
                    f"iframe_count={browser.iframe_hdlr.get_frame_count()}, "
                    f"console_errors={len(recovery_context.get('console_errors', []))}, "
                    f"network_errors={len(recovery_context.get('network_errors', []))}"
                )
            except Exception:
                recovery_note = ""

            return {
                "success": False,
                "error": error_msg,
                "recovery": recovery_note,
                "retry_count": browser.cfg.MAX_RETRIES,
            }

    # ------------------------------------------------------------------
    # JSON parsing
    # ------------------------------------------------------------------

    def _parse_decision(self, text: str) -> dict:
        cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
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

    # ------------------------------------------------------------------
    # Result builder
    # ------------------------------------------------------------------

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
                    "step":      s["step"],
                    "action":    s["action"],
                    "status":    s["status"],
                    "reasoning": s["reasoning"],
                }
                for s in steps
            ],
        }

        return {
            "status":           "completed" if verdict in ("PASSED", "FAILED") else verdict.lower(),
            "final_verdict":    verdict,
            "steps":            steps,
            "screenshot_paths": [s["screenshot"] for s in steps if s.get("screenshot")],
            "duration":         duration,
            "url":              url,
            "goal":             goal,
            "error":            error,
            "report":           report,
        }
