"""Deterministic PC-only probes; no real outbound connections."""
from __future__ import annotations

import unittest

from apps.zte_manager.services.workstation_path_diagnostic import (
    WorkstationPathDiagnostic,
)


class _Connection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class WorkstationProbeTests(unittest.TestCase):
    def test_three_real_callbacks_and_dns_with_explicit_source(self):
        observed = []
        instances = []

        def resolve(*args, **kwargs):
            observed.append((args, kwargs))
            return [(None, None, None, None, ("192.0.2.1", 443))]

        def connect(address, timeout):
            observed.append((address, timeout))
            sock = _Connection()
            instances.append(sock)
            return sock

        ticks = iter([0, .04, 1, 1.02, 2, 2.025, 3, 3.03])
        result = WorkstationPathDiagnostic(
            resolver=resolve, connector=connect,
            clock=lambda: next(ticks),
        ).run()
        self.assertEqual(result["source"], "technician_workstation")
        self.assertTrue(result["dns"]["ok"])
        self.assertEqual(result["dns"]["duration_ms"], 40.0)
        self.assertEqual(result["tcp"]["successful"], 3)
        self.assertEqual(result["tcp"]["attempts"], 3)
        self.assertAlmostEqual(result["tcp"]["mean_connect_ms"], 25, delta=1)
        self.assertEqual(result["tcp"]["variation_ms"], 10.0)
        self.assertTrue(all(item.closed for item in instances))
        self.assertEqual(
            [row[0] for row in observed[1:]],
            [("1.1.1.1", 443)] * 3,
        )

    def test_failed_probes_are_not_reported_as_icmp_packet_loss(self):
        def unavailable(*_args, **_kwargs):
            raise OSError("no route")

        ticks = iter([0, 1, 2, 3])
        result = WorkstationPathDiagnostic(
            resolver=unavailable, connector=unavailable,
            clock=lambda: next(ticks),
        ).run()
        self.assertFalse(result["dns"]["ok"])
        self.assertFalse(result["tcp"]["ok"])
        self.assertEqual(result["tcp"]["successful"], 0)
        self.assertIsNone(result["tcp"]["mean_connect_ms"])
        self.assertIn("não equivalem", result["limitations"])


if __name__ == "__main__":
    unittest.main()
