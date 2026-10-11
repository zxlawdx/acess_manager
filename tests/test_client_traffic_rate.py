from __future__ import annotations

import unittest

from apps.zte_manager.model.telemetry import (
    ClientTelemetry,
    ClientTrafficRateCalculator,
)


class ClientTrafficRateTests(unittest.TestCase):
    def test_first_snapshot_has_no_invented_rate(self):
        tracker = ClientTrafficRateCalculator()
        client = ClientTelemetry(
            mac="00:11:22:33:44:55",
            rx_bytes=1_000,
            tx_bytes=2_000,
        )
        result = tracker.enrich(client, sampled_at=10.0)
        self.assertIsNone(result.rx_rate_bps)
        self.assertIsNone(result.tx_rate_bps)

    def test_second_snapshot_uses_byte_delta_times_eight_over_time(self):
        tracker = ClientTrafficRateCalculator()
        tracker.rates(
            "00:11:22:33:44:55",
            rx_bytes=1_000,
            tx_bytes=2_000,
            sampled_at=10.0,
        )
        rx, tx = tracker.rates(
            "00:11:22:33:44:55",
            rx_bytes=2_000,
            tx_bytes=2_500,
            sampled_at=12.0,
        )
        self.assertEqual(rx, 4_000)
        self.assertEqual(tx, 2_000)

    def test_real_zero_delta_is_zero_not_unknown(self):
        tracker = ClientTrafficRateCalculator()
        tracker.rates("client", rx_bytes=10, tx_bytes=20, sampled_at=1.0)
        rx, tx = tracker.rates("client", rx_bytes=10, tx_bytes=20, sampled_at=2.0)
        self.assertEqual(rx, 0)
        self.assertEqual(tx, 0)

    def test_counter_reset_returns_unknown_and_resets_baseline(self):
        tracker = ClientTrafficRateCalculator()
        tracker.rates("client", rx_bytes=1_000, tx_bytes=2_000, sampled_at=1.0)
        reset = tracker.rates("client", rx_bytes=100, tx_bytes=200, sampled_at=2.0)
        recovered = tracker.rates("client", rx_bytes=200, tx_bytes=300, sampled_at=3.0)
        self.assertEqual(reset, (None, None))
        self.assertEqual(recovered, (800, 800))

    def test_missing_counter_never_becomes_zero(self):
        tracker = ClientTrafficRateCalculator()
        self.assertEqual(
            tracker.rates("client", rx_bytes=None, tx_bytes=0, sampled_at=1.0),
            (None, None),
        )

    def test_non_positive_time_delta_is_unknown(self):
        tracker = ClientTrafficRateCalculator()
        tracker.rates("client", rx_bytes=10, tx_bytes=20, sampled_at=2.0)
        self.assertEqual(
            tracker.rates("client", rx_bytes=20, tx_bytes=30, sampled_at=2.0),
            (None, None),
        )


if __name__ == "__main__":
    unittest.main()
