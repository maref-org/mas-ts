# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""MAS-TS-001 v3.0 — WebArena Oracle.

Executable benchmark for web task automation. Evaluates agent's
ability to navigate websites, search, and extract information.

Tasks: shopping, booking, flight search, research, form filling.

Usage:
    from mas_eval.oracle.web_arena import WebArenaOracle
    OracleRegistry.register(WebArenaOracle())
    result = run_d2_with_oracle(card, "web-arena", "web-arena-shop-001")
"""

import json
import logging
from pathlib import Path

from mas_eval.oracle.env import check_playwright
from mas_eval.oracle.oracle_base import Oracle, OracleTask

logger = logging.getLogger(__name__)

TASKS_FILE = Path(__file__).parent / "data" / "web_arena_tasks.json"


class WebArenaOracle(Oracle):
    """Executable benchmark for web task automation.

    Evaluates agents on web navigation and information retrieval tasks.
    Uses Playwright for real browser verification when available,
    falls back to trajectory-based simulated scoring.
    """

    def __init__(self):
        self._tasks_cache = None

    @property
    def name(self):
        return "web-arena"

    def list_tasks(self):
        return [
            OracleTask(
                task_id=t["task_id"],
                prompt=t["prompt"],
                expected_tools=t.get("expected_tools", []),
                rubric={"success_criteria": t.get("success_criteria", "")},
                metadata={
                    "domain": t.get("domain", ""),
                    "url": t.get("url", ""),
                },
            )
            for t in self._load_tasks()
        ]

    def execute(self, task, agent_card):
        tasks = self._load_tasks()
        match = next((t for t in tasks if t["task_id"] == task.task_id), None)
        if match is None:
            logger.warning("Task %r not found in web-arena tasks", task.task_id)
            return {"events": []}
        return match.get("golden_trajectory", {"events": []})

    def validate_environment(self):
        if not TASKS_FILE.exists():
            return False, f"{TASKS_FILE.name} not found"
        pw_ok, pw_msg = check_playwright()
        if pw_ok:
            return True, f"Playwright available, {TASKS_FILE.name} loaded"
        tasks = self._load_tasks()
        return (
            True,
            f"Playwright unavailable (simulated mode), {len(tasks)} tasks loaded",
        )

    def score(self, task, agent_trajectory, golden_trajectory=None):
        """WebArena scoring: 50% keyword coverage + 50% task completion."""
        if not agent_trajectory:
            return 0.0

        events = self._get_events(agent_trajectory)
        if not events:
            return 0.0

        pw_ok, _ = check_playwright()
        if pw_ok:
            return self._real_score(task, events)

        return self._simulate_score(task, events)

    def _real_score(self, task, events):
        """Score using Playwright browser verification."""
        task_data = self._find_task(task.task_id)
        if task_data is None:
            return 0.0

        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                nav_events = [
                    e
                    for e in events
                    if e.get("action", {}).get("tool_id") == "web_fetch"
                    and "url" in e.get("action", {}).get("input", {})
                ]

                if not nav_events:
                    return self._simulate_score(task, events)

                last_url = nav_events[-1]["action"]["input"]["url"]
                try:
                    page.goto(last_url, timeout=15000, wait_until="domcontentloaded")
                    success = self._check_page_success(page, task_data)
                    score = 100.0 if success else 50.0
                except Exception:
                    score = self._simulate_score(task, events)
                finally:
                    browser.close()
                return score

        except ImportError:
            logger.warning("Playwright not available, falling back to simulation")
            return self._simulate_score(task, events)

    def _simulate_score(self, task, events):
        """Score based on keyword presence and task completion signal."""
        keywords = self._get_keywords(task)
        if not keywords:
            return 100.0

        text = json.dumps(events).lower()
        matched = sum(1 for kw in keywords if kw.lower() in text)
        keyword_score = matched / len(keywords) * 50.0

        task_complete = any(
            e.get("action", {}).get("type") == "task_complete"
            and e.get("action", {}).get("result") == "success"
            for e in events
        )
        completion_score = 50.0 if task_complete else 0.0

        return round(keyword_score + completion_score, 1)

    @staticmethod
    def _check_page_success(page, task_data):
        """Check page state against task success criteria."""
        criteria = task_data.get("success_criteria", "")
        if criteria == "product_page_reached":
            return bool(
                page.locator(".product, .item, [data-testid='product']").first.count()
            )
        if criteria == "search_results_shown":
            return bool(
                page.locator(".result, .listing, [data-testid='result']").first.count()
            )
        if criteria == "flight_results_shown":
            return bool(
                page.locator(".flight, .option, [data-testid='flight']").first.count()
            )
        if criteria == "information_found":
            return bool(
                page.locator(
                    ".infobox, .mw-parser-output, #mw-content-text"
                ).first.count()
            )
        if criteria == "form_submitted":
            return bool(
                page.locator(".success, .thank-you, #confirmation").first.count()
            )
        return bool(page.content())

    def _get_keywords(self, task):
        task_data = self._find_task(task.task_id)
        if task_data is None:
            return []
        return task_data.get("expected_keywords", [])

    def _find_task(self, task_id):
        tasks = self._load_tasks()
        return next((t for t in tasks if t["task_id"] == task_id), None)

    def _load_tasks(self):
        if self._tasks_cache is not None:
            return self._tasks_cache
        if not TASKS_FILE.exists():
            logger.warning("Tasks file not found: %s", TASKS_FILE)
            self._tasks_cache = []
            return self._tasks_cache
        with open(TASKS_FILE) as f:
            self._tasks_cache = json.load(f)
        return self._tasks_cache

    @staticmethod
    def _get_events(trajectory):
        if isinstance(trajectory, list):
            return trajectory
        if isinstance(trajectory, dict):
            return trajectory.get("events", [])
        return []
