"""Deterministic Phase-1 tests: no network access or physical ONT."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.zte_manager.application.operations.audit_executor import (
    AuditedOperation,
    ChangeOutcome,
)
from apps.zte_manager.application.operations.verifiers import (
    verify_dhcp,
    verify_ssid,
)
from apps.zte_manager.repositories.history_repository import HistoryRepository


class Recorder:
    def __init__(self) -> None:
        self.rows = []

    def save_change(self, session_id, **kwargs):
        self.rows.append(kwargs)
        return len(self.rows)


class AuditExecutorTests(unittest.TestCase):
    def setUp(self):
        self.recorder = Recorder()
        self.runner = AuditedOperation(self.recorder)

    def execute(self, action, after, verify=None):
        return self.runner.execute(
            session_id=7, operation="wifi_update", target="5GHz",
            before_reader=lambda: {"ssid": "old", "password": "super-secret"},
            action=action, after_reader=after, verify=verify,
        )

    def test_only_explicit_verifier_and_successful_readback_mean_verified(self):
        steps = []

        def action():
            steps.append("post")
            return {"success": True}

        def reader():
            steps.append("read")
            return {"ssid": "new"}

        result = self.execute(
            action, reader,
            verify=lambda before, response, after: after["ssid"] == "new",
        )
        self.assertEqual(steps, ["post", "read"])
        self.assertEqual(result.outcome, ChangeOutcome.VERIFIED)
        self.assertTrue(self.recorder.rows[0]["success"])
        self.assertEqual(self.recorder.rows[0]["outcome"], "verified")
        self.assertEqual(self.recorder.rows[0]["before"]["password"], "[REDACTED]")
        self.assertEqual(result.value, {"success": True})

    def test_no_verifier_never_claims_success_even_when_post_returns_verified(self):
        result = self.execute(
            lambda: {"success": True, "verified": True},
            lambda: {"ssid": "new"},
        )
        self.assertEqual(result.outcome, ChangeOutcome.ACCEPTED)
        self.assertFalse(self.recorder.rows[0]["success"])

    def test_readback_failure_is_uncertain_and_exception_is_not_saved(self):
        def broken_read():
            raise RuntimeError("password=hunter2 token=raw")

        with self.assertLogs(
            "apps.zte_manager.application.operations.audit_executor", "WARNING"
        ) as logged:
            result = self.execute(lambda: {"success": True}, broken_read)
        self.assertEqual(result.outcome, ChangeOutcome.UNCERTAIN)
        self.assertNotIn("hunter2", str(self.recorder.rows) + str(logged.output))
        self.assertFalse(self.recorder.rows[0]["success"])

    def test_explicit_rejection_never_retries_or_marks_accepted(self):
        reads = []
        result = self.execute(lambda: {"success": False}, lambda: reads.append(1))
        self.assertEqual(result.outcome, ChangeOutcome.FAILED)
        self.assertEqual(reads, [])
        self.assertFalse(self.recorder.rows[0]["success"])

    def test_action_exception_is_propagated_with_sanitized_audit(self):
        def fail():
            raise ValueError("password=NEVER_LOG_THIS")

        with self.assertLogs(
            "apps.zte_manager.application.operations.audit_executor", "WARNING"
        ) as logged:
            with self.assertRaises(ValueError):
                self.execute(fail, lambda: {"ssid": "new"})
        self.assertNotIn(
            "NEVER_LOG_THIS", str(self.recorder.rows) + str(logged.output)
        )
        self.assertEqual(self.recorder.rows[0]["outcome"], "failed")

    def test_verifier_false_is_uncertain_not_verified(self):
        result = self.execute(
            lambda: {"success": True}, lambda: {"ssid": "old"},
            verify=lambda before, response, after: after["ssid"] == "new",
        )
        self.assertEqual(result.outcome, ChangeOutcome.UNCERTAIN)

    def test_audit_storage_failure_does_not_repeat_hardware_command(self):
        class BrokenStorage:
            def save_change(self, *_a, **_kw):
                raise sqlite3.OperationalError("password=raw")

        sends = []
        with self.assertLogs(
            "apps.zte_manager.application.operations.audit_executor", "ERROR"
        ) as logged:
            result = AuditedOperation(BrokenStorage()).execute(
                session_id=7, operation="wifi_update", target=None,
                before_reader=lambda: {},
                action=lambda: sends.append("POST") or {"success": True},
                after_reader=lambda: {},
            )
        self.assertEqual(result.outcome, ChangeOutcome.ACCEPTED)
        self.assertEqual(sends, ["POST"])
        self.assertNotIn("password=raw", str(logged.output))

    def test_no_pre_read_cannot_prove_even_when_verifier_returns_true(self):
        result = self.runner.execute(
            session_id=7, operation="test", target=None,
            before_reader=lambda: (_ for _ in ()).throw(RuntimeError("offline")),
            action=lambda: {"success": True},
            after_reader=lambda: {"state": 1},
            verify=lambda b, r, a: True,
        )
        self.assertEqual(result.outcome, ChangeOutcome.UNCERTAIN)


class FirmwareReadbackTests(unittest.TestCase):
    def test_dhcp_checks_exact_changed_wire_fields(self):
        response = {"success": True, "verified": True}
        after = {"basic": {"ServerEnable": "0", "MinAddress": "192.168.1.10"}}
        self.assertTrue(
            verify_dhcp({"enabled": False}, {}, response, after)
        )
        self.assertFalse(
            verify_dhcp({"enabled": True}, {}, response, after)
        )
        self.assertFalse(verify_dhcp({}, {}, response, after))
        self.assertFalse(
            verify_dhcp({"enabled": False}, {}, {"success": True}, after)
        )

    def test_wifi_requires_matching_ssid_and_own_writer_proof(self):
        response = {"success": True, "verified": True}
        after = [{"id": "2", "ssid": "new", "ativo": True}]
        self.assertTrue(
            verify_ssid("2", {"ssid": "new"}, [], response, after)
        )
        self.assertFalse(
            verify_ssid("3", {"ssid": "new"}, [], response, after)
        )
        self.assertFalse(
            verify_ssid("2", {"ssid": "old"}, [], response, after)
        )


class SQLiteOutcomeTests(unittest.TestCase):
    def test_existing_legacy_db_migrates_without_relabeling_success_as_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.sqlite3"
            with sqlite3.connect(path) as connection:
                connection.executescript(
                    """
                    CREATE TABLE configuration_change (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER, created_at TEXT NOT NULL,
                        operation TEXT NOT NULL, target TEXT,
                        before_json TEXT, after_json TEXT,
                        success INTEGER NOT NULL, message TEXT
                    );
                    INSERT INTO configuration_change (
                        session_id,created_at,operation,success
                    ) VALUES (NULL, '2026-09-26', 'legacy', 1);
                    """
                )
            store = HistoryRepository(path)
            rows = store.recent()["changes"]
            self.assertEqual(rows[0]["outcome"], "legacy_success_unverified")
            self.assertTrue(rows[0]["success"])
            # Opening a second time is idempotent.
            self.assertEqual(
                HistoryRepository(path).recent()["changes"][0]["outcome"],
                "legacy_success_unverified",
            )

    def test_new_outcome_serializes_safely_and_success_means_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = HistoryRepository(Path(tmp) / "history.sqlite3")
            store.save_change(
                None, operation="wifi_update", target="test",
                before={"nested": {"session_token": "SHOULD_NOT_PERSIST"}},
                after={"wifi": [{"password": "SECRET"}, {"ssid": "test"}]},
                success=True, outcome="accepted",
            )
            row = store.recent()["changes"][0]
            self.assertFalse(row["success"])
            self.assertEqual(row["outcome"], "accepted")
            self.assertEqual(
                row["before_json"]["nested"]["session_token"], "[REDACTED]"
            )
            raw = (Path(tmp) / "history.sqlite3").read_bytes()
            self.assertNotIn(b"SHOULD_NOT_PERSIST", raw)
            self.assertNotIn(b"SECRET", raw)


if __name__ == "__main__":
    unittest.main()
