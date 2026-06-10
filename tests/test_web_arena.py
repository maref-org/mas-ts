# SPDX-FileCopyrightText: 2026 frankiehot-tech
# SPDX-License-Identifier: Apache-2.0
"""Tests for MAS-TS-001 v3.0 WebArena Oracle."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from mas_eval.oracle.oracle_base import OracleRegistry, run_d2_with_oracle
from mas_eval.oracle.web_arena import WebArenaOracle

SAMPLE_CARD = {
    "agent_id": "test-agent-001",
    "name": "TestAgent",
    "version": "1.0.0",
    "card_version": "1.2",
    "model_backend": {
        "provider": "test",
        "model": "claude-sonnet-4",
        "deployment": "cloud",
        "endpoint": "https://api.anthropic.com/v1/messages",
    },
    "capabilities": [
        {
            "skill_id": "web_search",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-05-01",
        },
        {
            "skill_id": "web_fetch",
            "input_schema": {},
            "output_schema": {},
            "business_rule_version": "2026-05-01",
        },
    ],
}

SHOP_TRAJECTORY = {
    "events": [
        {
            "action": {
                "type": "tool_call",
                "tool_id": "web_fetch",
                "input": {"url": "https://example-shop.com"},
            }
        },
        {
            "action": {
                "type": "tool_call",
                "tool_id": "web_search",
                "input": {"query": "wireless headphones under $100"},
            }
        },
        {
            "action": {
                "type": "task_complete",
                "result": "success",
                "tool_id": "",
                "input": {},
            }
        },
    ]
}

SHOP_NO_COMPLETE = {
    "events": [
        {
            "action": {
                "type": "tool_call",
                "tool_id": "web_fetch",
                "input": {"url": "https://example-shop.com"},
            }
        },
        {
            "action": {
                "type": "tool_call",
                "tool_id": "web_search",
                "input": {"query": "wireless headphones"},
            }
        },
    ]
}

SHOP_EMPTY_TRAJECTORY: dict = {"events": []}

WRONG_TRAJECTORY = {
    "events": [
        {
            "action": {
                "type": "tool_call",
                "tool_id": "bash",
                "input": {"command": "ls"},
            }
        },
        {
            "action": {
                "type": "task_complete",
                "result": "success",
                "tool_id": "",
                "input": {},
            }
        },
    ]
}


class TestWebArenaOracle:
    def setup_method(self):
        self.oracle = WebArenaOracle()

    def test_name(self):
        assert self.oracle.name == "web-arena"

    def test_list_tasks_returns_five(self):
        tasks = self.oracle.list_tasks()
        assert len(tasks) == 5

    def test_task_ids_are_unique(self):
        tasks = self.oracle.list_tasks()
        ids = [t.task_id for t in tasks]
        assert len(ids) == len(set(ids))
        for tid in ids:
            assert tid.startswith("web-arena-")

    def test_task_fields(self):
        tasks = self.oracle.list_tasks()
        for t in tasks:
            assert len(t.prompt) > 10
            assert isinstance(t.expected_tools, list)
            assert "domain" in t.metadata
            assert "url" in t.metadata
            assert "success_criteria" in t.rubric

    def test_execute_returns_golden(self):
        task = self.oracle.list_tasks()[0]
        result = self.oracle.execute(task, SAMPLE_CARD)
        assert "events" in result
        assert len(result["events"]) >= 2

    def test_execute_event_format(self):
        task = self.oracle.list_tasks()[0]
        result = self.oracle.execute(task, SAMPLE_CARD)
        for event in result["events"]:
            assert "action" in event
            assert "type" in event["action"]
            assert "tool_id" in event["action"]
            assert "input" in event["action"]

    def test_execute_unknown_task(self):
        class FakeTask:
            task_id = "web-arena-nonexistent"

        result = self.oracle.execute(FakeTask(), SAMPLE_CARD)
        assert result == {"events": []}

    def test_validate_environment(self):
        ok, msg = self.oracle.validate_environment()
        assert ok is True
        assert "tasks" in msg

    def test_score_empty_returns_zero(self):
        task = self.oracle.list_tasks()[0]
        assert self.oracle.score(task, None) == 0.0
        assert self.oracle.score(task, []) == 0.0
        assert self.oracle.score(task, SHOP_EMPTY_TRAJECTORY) == 0.0


class TestSimulatedScore:
    def setup_method(self):
        self.oracle = WebArenaOracle()

    def test_all_keywords_and_complete_high_score(self):
        task = self.oracle.list_tasks()[0]
        score = self.oracle._simulate_score(task, SHOP_TRAJECTORY["events"])
        assert score > 50.0

    def test_keywords_without_completion(self):
        task = self.oracle.list_tasks()[0]
        score = self.oracle._simulate_score(task, SHOP_NO_COMPLETE["events"])
        assert score < 80.0
        assert score > 0.0

    def test_no_keywords_no_completion_low_score(self):
        task = self.oracle.list_tasks()[0]
        events = [
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "bash",
                    "input": {"command": "ls"},
                }
            }
        ]
        score = self.oracle._simulate_score(task, events)
        assert score < 30.0

    def test_task_has_keywords(self):
        task = self.oracle.list_tasks()[0]
        keywords = self.oracle._get_keywords(task)
        assert len(keywords) >= 2

    def test_all_domains_have_keywords(self):
        tasks = self.oracle.list_tasks()
        for t in tasks:
            keywords = self.oracle._get_keywords(t)
            assert len(keywords) >= 2, f"{t.task_id} has no keywords"

    def test_booking_keywords_score(self):
        task = self.oracle.list_tasks()[1]
        assert task.task_id == "web-arena-booking-001"
        good_events = [
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "web_fetch",
                    "input": {"url": "https://example-booking.com"},
                }
            },
            {
                "action": {
                    "type": "tool_call",
                    "tool_id": "web_search",
                    "input": {"query": "Paris hotels free cancellation July"},
                }
            },
            {"action": {"type": "task_complete", "result": "success"}},
        ]
        score = self.oracle._simulate_score(task, good_events)
        assert score > 50.0

    def test_form_task_no_tools_low_score(self):
        task = self.oracle.list_tasks()[4]
        assert task.task_id == "web-arena-form-001"
        events = [{"action": {"type": "task_complete", "result": "success"}}]
        score = self.oracle._simulate_score(task, events)
        assert score > 0


class TestWebArenaIntegration:
    def setup_method(self):
        OracleRegistry.clear()
        self.oracle = WebArenaOracle()
        OracleRegistry.register(self.oracle)
        # Force simulated mode for deterministic tests
        import mas_eval.oracle.web_arena as wa

        self._real_check = wa.check_playwright
        wa.check_playwright = lambda: (False, "mocked for test")

    def teardown_method(self):
        import mas_eval.oracle.web_arena as wa

        wa.check_playwright = self._real_check
        OracleRegistry.clear()

    def test_registered(self):
        assert OracleRegistry.get("web-arena") is self.oracle

    def test_run_d2_with_oracle(self):
        result = run_d2_with_oracle(
            SAMPLE_CARD, "web-arena", mock_trajectory=SHOP_TRAJECTORY
        )
        assert result["domain"] == "D2"
        assert 0 <= result["score"] <= 100
        assert result["summary"]["oracle_name"] == "web-arena"
        assert result["summary"]["oracle_env_ok"] is True

    def test_oracle_score_in_result(self):
        result = run_d2_with_oracle(
            SAMPLE_CARD, "web-arena", mock_trajectory=SHOP_TRAJECTORY
        )
        assert "oracle_score" in result["subscores"]
        assert result["subscores"]["oracle_score"] > 0

    def test_good_vs_wrong_score(self):
        good = run_d2_with_oracle(
            SAMPLE_CARD, "web-arena", mock_trajectory=SHOP_TRAJECTORY
        )
        wrong = run_d2_with_oracle(
            SAMPLE_CARD, "web-arena", mock_trajectory=WRONG_TRAJECTORY
        )
        assert good["subscores"]["oracle_score"] > wrong["subscores"]["oracle_score"]

    def test_empty_score_zero(self):
        result = run_d2_with_oracle(
            SAMPLE_CARD, "web-arena", mock_trajectory=SHOP_EMPTY_TRAJECTORY
        )
        assert result["subscores"]["oracle_score"] == 0.0


class TestCheckPageSuccess:
    def test_product_page_reached(self):
        page = MagicMock()
        page.locator.return_value.first.count.return_value = 1
        result = WebArenaOracle._check_page_success(
            page, {"success_criteria": "product_page_reached"}
        )
        assert result is True

    def test_product_page_not_reached(self):
        page = MagicMock()
        page.locator.return_value.first.count.return_value = 0
        result = WebArenaOracle._check_page_success(
            page, {"success_criteria": "product_page_reached"}
        )
        assert result is False

    def test_search_results_shown(self):
        page = MagicMock()
        page.locator.return_value.first.count.return_value = 1
        result = WebArenaOracle._check_page_success(
            page, {"success_criteria": "search_results_shown"}
        )
        assert result is True

    def test_flight_results_shown(self):
        page = MagicMock()
        page.locator.return_value.first.count.return_value = 1
        result = WebArenaOracle._check_page_success(
            page, {"success_criteria": "flight_results_shown"}
        )
        assert result is True

    def test_information_found(self):
        page = MagicMock()
        page.locator.return_value.first.count.return_value = 1
        result = WebArenaOracle._check_page_success(
            page, {"success_criteria": "information_found"}
        )
        assert result is True

    def test_form_submitted(self):
        page = MagicMock()
        page.locator.return_value.first.count.return_value = 1
        result = WebArenaOracle._check_page_success(
            page, {"success_criteria": "form_submitted"}
        )
        assert result is True

    def test_unknown_criteria_fallback(self):
        page = MagicMock()
        page.content.return_value = "<html>some content</html>"
        result = WebArenaOracle._check_page_success(
            page, {"success_criteria": "unknown_criteria"}
        )
        assert result is True

    def test_unknown_criteria_empty_fallback(self):
        page = MagicMock()
        page.content.return_value = ""
        result = WebArenaOracle._check_page_success(
            page, {"success_criteria": "unknown_criteria"}
        )
        assert result is False


class TestWebArenaEdgeCases:
    def setup_method(self):
        self.oracle = WebArenaOracle()

    def test_validate_env_file_missing(self):
        with patch("mas_eval.oracle.web_arena.TASKS_FILE") as mock_file:
            mock_file.exists.return_value = False
            mock_file.name = "web_arena_tasks.json"
            ok, msg = self.oracle.validate_environment()
            assert ok is False
            assert "not found" in msg

    def test_validate_env_playwright_available(self):
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.name = "web_arena_tasks.json"
        with (
            patch("mas_eval.oracle.web_arena.TASKS_FILE", mock_file),
            patch(
                "mas_eval.oracle.web_arena.check_playwright",
                return_value=(True, "pw ok"),
            ),
        ):
            ok, msg = self.oracle.validate_environment()
            assert ok is True
            assert "Playwright available" in msg

    def test_load_tasks_file_missing(self):
        with patch("mas_eval.oracle.web_arena.TASKS_FILE") as mock_file:
            mock_file.exists.return_value = False
            self.oracle._tasks_cache = None
            tasks = self.oracle._load_tasks()
            assert tasks == []

    def test_get_events_list(self):
        events = [{"action": {"type": "tool_call"}}]
        result = WebArenaOracle._get_events(events)
        assert result is events
        assert len(result) == 1

    def test_get_events_fallback(self):
        result = WebArenaOracle._get_events("not a list or dict")
        assert result == []

    def test_get_keywords_not_found(self):
        from mas_eval.oracle.oracle_base import OracleTask

        task = OracleTask(task_id="nonexistent", prompt="test")
        keywords = self.oracle._get_keywords(task)
        assert keywords == []

    def test_simulate_score_no_keywords(self):
        """When no keywords found, return 100.0"""
        with patch.object(self.oracle, "_get_keywords", return_value=[]):
            score = self.oracle._simulate_score(
                MagicMock(task_id="any"),
                [{"action": {"type": "tool_call"}}],
            )
            assert score == 100.0

    def test_score_with_trajectory_list(self):
        """Cover _get_events(list) path via score()."""
        with patch(
            "mas_eval.oracle.web_arena.check_playwright", return_value=(False, "no pw")
        ):
            task = self.oracle.list_tasks()[0]
            traj = [
                {
                    "action": {
                        "type": "tool_call",
                        "tool_id": "web_search",
                        "input": {"query": "test"},
                    }
                }
            ]
            score = self.oracle.score(task, traj)
            assert isinstance(score, float)

    def test_real_score_no_task_data(self):
        with patch(
            "mas_eval.oracle.web_arena.check_playwright", return_value=(True, "ok")
        ):
            from mas_eval.oracle.oracle_base import OracleTask

            task = OracleTask(task_id="nonexistent", prompt="test")
            score = self.oracle._real_score(task, [])
            assert score == 0.0

    def test_real_score_no_nav_events(self):
        """When no navigation events, fall back to simulate."""
        with (
            patch(
                "mas_eval.oracle.web_arena.check_playwright", return_value=(True, "ok")
            ),
            patch.object(self.oracle, "_simulate_score", return_value=50.0) as mock_sim,
        ):
            task = self.oracle.list_tasks()[0]
            events = [{"action": {"type": "tool_call", "tool_id": "bash", "input": {}}}]
            score = self.oracle._real_score(task, events)
            assert score == 50.0
            mock_sim.assert_called_once()

    def test_real_score_playwright_unavailable(self):
        """When playwright ImportError occurs, fall back to simulate."""
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "playwright.sync_api":
                raise ImportError("no playwright")
            return real_import(name, *args, **kwargs)

        with (
            patch(
                "mas_eval.oracle.web_arena.check_playwright", return_value=(True, "ok")
            ),
            patch.object(self.oracle, "_simulate_score", return_value=40.0) as mock_sim,
            patch("builtins.__import__", side_effect=mock_import),
        ):
            task = self.oracle.list_tasks()[0]
            events = [
                {
                    "action": {
                        "type": "tool_call",
                        "tool_id": "web_fetch",
                        "input": {"url": "http://example.com"},
                    }
                }
            ]
            score = self.oracle._real_score(task, events)
            assert score == 40.0
            mock_sim.assert_called_once()

    def test_real_score_page_error(self):
        """When page.goto fails, fall back to simulate."""
        with (
            patch(
                "mas_eval.oracle.web_arena.check_playwright", return_value=(True, "ok")
            ),
            patch.object(self.oracle, "_simulate_score", return_value=35.0) as mock_sim,
        ):
            mock_pw = MagicMock()
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_page.goto.side_effect = Exception("timeout")
            mock_browser.new_page.return_value = mock_page
            mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = (
                mock_browser
            )

            import builtins

            real_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "playwright.sync_api":
                    mod = MagicMock()
                    mod.sync_playwright = mock_pw
                    return mod
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                task = self.oracle.list_tasks()[0]
                events = [
                    {
                        "action": {
                            "type": "tool_call",
                            "tool_id": "web_fetch",
                            "input": {"url": "http://example.com"},
                        }
                    }
                ]
                score = self.oracle._real_score(task, events)
                assert score == 35.0
                mock_sim.assert_called_once()

    def test_score_calls_real_score_when_pw_available(self):
        """Cover score() calling _real_score when playwright is available."""
        with (
            patch(
                "mas_eval.oracle.web_arena.check_playwright", return_value=(True, "ok")
            ),
            patch.object(self.oracle, "_real_score", return_value=75.0) as mock_real,
        ):
            task = self.oracle.list_tasks()[0]
            traj = {
                "events": [
                    {
                        "action": {
                            "type": "tool_call",
                            "tool_id": "web_search",
                            "input": {"query": "test"},
                        }
                    }
                ]
            }
            score = self.oracle.score(task, traj)
            assert score == 75.0
            mock_real.assert_called_once()

    def test_real_score_no_nav_events_with_pw_import(self):
        """Cover _real_score no-nav-events path with playwright import mocked."""
        with (
            patch(
                "mas_eval.oracle.web_arena.check_playwright", return_value=(True, "ok")
            ),
            patch.object(self.oracle, "_simulate_score", return_value=60.0) as mock_sim,
        ):
            mock_pw = MagicMock()
            import builtins

            real_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "playwright.sync_api":
                    mod = MagicMock()
                    mod.sync_playwright = mock_pw
                    return mod
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                task = self.oracle.list_tasks()[0]
                events = [
                    {"action": {"type": "tool_call", "tool_id": "bash", "input": {}}}
                ]
                score = self.oracle._real_score(task, events)
                assert score == 60.0
                mock_sim.assert_called_once()

    def test_real_score_successful_check(self):
        """Cover _real_score success path with _check_page_success returning True."""
        with patch(
            "mas_eval.oracle.web_arena.check_playwright", return_value=(True, "ok")
        ):
            mock_pw = MagicMock()
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_page.goto.return_value = None
            mock_page.locator.return_value.first.count.return_value = 1
            mock_browser.new_page.return_value = mock_page
            mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = (
                mock_browser
            )

            import builtins

            real_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "playwright.sync_api":
                    mod = MagicMock()
                    mod.sync_playwright = mock_pw
                    return mod
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                task = self.oracle.list_tasks()[0]
                events = [
                    {
                        "action": {
                            "type": "tool_call",
                            "tool_id": "web_fetch",
                            "input": {"url": "http://example.com/shop"},
                        }
                    }
                ]
                score = self.oracle._real_score(task, events)
                assert score == 100.0
