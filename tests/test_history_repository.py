import tempfile
import unittest
from pathlib import Path

from apps.zte_manager.repositories.history_repository import (
    HistoryRepository,
)


class HistoryRepositoryTests(unittest.TestCase):
    def test_persists_session_snapshot_diagnostic_and_change(self):
        with tempfile.TemporaryDirectory() as temp:
            repository = HistoryRepository(
                Path(temp) / "history.sqlite3"
            )

            session_id = repository.start_session(
                host="192.168.1.1",
                attendant="law",
                device={
                    "modelo": "F670L",
                    "firmware": "test",
                    "serial": "ABC",
                },
            )

            repository.save_snapshot(
                session_id,
                "test",
                {"wan": "up"},
            )

            repository.save_diagnostic(
                session_id,
                {
                    "status": "warning",
                    "summary": "Teste",
                },
            )

            repository.save_change(
                session_id,
                operation="wifi",
                target="5GHz",
                before={"channel": 36},
                after={"channel": 40},
                success=True,
            )

            repository.end_session(
                session_id
            )

            recent = repository.recent(
                10
            )

            self.assertEqual(
                recent["sessions"][0]["model"],
                "F670L",
            )
            self.assertIsNotNone(
                recent["sessions"][0]["ended_at"]
            )
            self.assertEqual(
                recent["diagnostics"][0]["status"],
                "warning",
            )
            self.assertEqual(
                recent["changes"][0]["after_json"]["channel"],
                40,
            )
            self.assertEqual(
                recent["snapshots"][0]["payload_json"]["wan"],
                "up",
            )


if __name__ == "__main__":
    unittest.main()
