"""F6600P support-progress contract without physical hardware.

The GET is intentionally independent from ZTEService._lock so a Waitress
worker can return visible progress while ThinkLua commands run serially.
"""
from __future__ import annotations

import sqlite3
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from apps.zte_manager import api
from apps.zte_manager.services.zte_service import ZTEService


class SupportProgressTests(unittest.TestCase):
    def setUp(self):
        self.service = ZTEService()
        self.service._history_session_id = 17

    def _patch_readers(self):
        return (
            patch.object(self.service, "get_client", return_value=object()),
            patch.object(self.service, "_capabilities", return_value=object()),
            patch.object(self.service, "_diagnostic_thresholds", return_value=object()),
            patch.object(
                self.service, "_support_options",
                return_value=SimpleNamespace(mode="general"),
            ),
        )

    def test_progress_readable_while_router_lock_is_held(self):
        started, release = threading.Event(), threading.Event()
        outcome: list[object] = []

        def slow_run(_options, _thresholds, *, progress):
            progress("base", 1, 7)
            started.set()
            if not release.wait(timeout=3):
                raise TimeoutError("synthetic worker not released")
            progress("analysis", 7, 7)
            return {"status": "ok", "sections": {"device": {"ok": True}},
                    "errors": {}, "findings": [], "summary": "OK"}

        reader_patches = self._patch_readers()
        with (
            reader_patches[0], reader_patches[1],
            reader_patches[2], reader_patches[3],
            patch("apps.zte_manager.services.zte_service.SupportDiagnosticService") as engine,
            patch("apps.zte_manager.services.zte_service.history_repository.save_diagnostic",
                  return_value=29),
            patch("apps.zte_manager.services.zte_service.history_repository.save_snapshot"),
        ):
            engine.return_value.run.side_effect = slow_run
            def worker():
                try:
                    outcome.append(self.service.support_diagnostic({}))
                except Exception as exc:
                    outcome.append(exc)
            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
            try:
                self.assertTrue(started.wait(timeout=2))
                before = time.monotonic()
                stage = self.service.support_progress()
                elapsed = time.monotonic() - before
                self.assertLess(elapsed, 0.3, "Progress GET must not wait for ONT RLock")
                self.assertEqual(stage, {
                    "running": True, "stage": "base",
                    "completed": 1, "total": 7,
                })
                with patch.object(api, "zte_service", self.service):
                    self.assertEqual(api.support_diagnostic_progress(), stage)
            finally:
                release.set()
                thread.join(timeout=4)

        self.assertFalse(thread.is_alive())
        self.assertEqual(outcome[0]["history_id"], 29)
        self.assertEqual(outcome[0]["sections"]["device"]["ok"], True)
        self.assertEqual(
            self.service.support_progress()["stage"], "completed"
        )
        self.assertFalse(self.service.support_progress()["running"])

    def test_sqlite_failure_does_not_discard_successful_diagnostic(self):
        reader_patches = self._patch_readers()
        with (
            reader_patches[0], reader_patches[1],
            reader_patches[2], reader_patches[3],
            patch("apps.zte_manager.services.zte_service.SupportDiagnosticService") as engine,
            patch("apps.zte_manager.services.zte_service.history_repository.save_diagnostic",
                  side_effect=sqlite3.OperationalError("SECRET_DB_PASSWORD")),
            patch("apps.zte_manager.services.zte_service.history_repository.save_snapshot",
                  side_effect=sqlite3.OperationalError("SECRET_SESSION_TOKEN")),
            self.assertLogs(
                "apps.zte_manager.services.zte_service", "WARNING"
            ) as logs,
        ):
            engine.return_value.run.return_value = {
                "status": "ok", "sections": {}, "findings": [],
                "summary": "diagnostic collected", "errors": {},
            }
            response = self.service.support_diagnostic({})

        self.assertIsNone(response["history_id"])
        self.assertEqual(response["summary"], "diagnostic collected")
        self.assertNotIn("SECRET_", str(logs.output))
        self.assertEqual(self.service.support_progress()["stage"], "completed")

    def test_failed_engine_does_not_leave_progress_running(self):
        reader_patches = self._patch_readers()
        with (
            reader_patches[0], reader_patches[1],
            reader_patches[2], reader_patches[3],
            patch("apps.zte_manager.services.zte_service.SupportDiagnosticService") as engine,
            self.assertLogs(
                "apps.zte_manager.services.zte_service", "WARNING"
            ) as logs,
        ):
            engine.return_value.run.side_effect = RuntimeError("TOP_SECRET_XML")
            with self.assertRaises(RuntimeError):
                self.service.support_diagnostic({})
        self.assertEqual(self.service.support_progress()["stage"], "failed")
        self.assertFalse(self.service.support_progress()["running"])
        self.assertNotIn("TOP_SECRET_XML", str(logs.output))


if __name__ == "__main__":
    unittest.main()
