import tempfile
import unittest
from pathlib import Path

from apps.zte_manager.repositories.management_repository import (
    ManagementRepository,
)
from apps.zte_manager.services.fleet_service import (
    DriftService,
)
from apps.zte_manager.services.operations_monitoring_service import (
    IncidentCorrelationService,
    TopologyService,
)
from apps.zte_manager.services.remote_access_service import (
    GatewayCommandPolicy,
)


class ManagementRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = ManagementRepository(
            Path(
                self.temp.name
            )
            / "management.sqlite3"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_inventory_preserves_topology_on_lightweight_reconnect(self):
        first = self.repo.upsert_device({
            "key": "SN123",
            "host": "192.168.1.1",
            "model": "F670L",
            "serial": "SN123",
            "customer_name": "Cliente X",
            "pop": "POP-PVH",
            "olt": "OLT-01",
            "cto": "CTO-17",
            "tags": [
                "premium",
            ],
            "current_config": {
                "dns": {
                    "ipv4_1": "1.1.1.1",
                }
            },
        })

        second = self.repo.upsert_device({
            "key": "SN123",
            "host": "192.168.1.1",
            "model": "F670L",
            "serial": "SN123",
            "status": "online",
            "metadata": {
                "attendant": "law",
            },
        })

        self.assertEqual(
            first["id"],
            second["id"],
        )
        self.assertEqual(
            second["customer_name"],
            "Cliente X",
        )
        self.assertEqual(
            second["pop"],
            "POP-PVH",
        )
        self.assertEqual(
            second["olt"],
            "OLT-01",
        )
        self.assertEqual(
            second["cto"],
            "CTO-17",
        )
        self.assertEqual(
            second["tags"],
            [
                "premium",
            ],
        )
        self.assertEqual(
            second["current_config"]["dns"]["ipv4_1"],
            "1.1.1.1",
        )

    def test_profile_and_batch_job_are_persistent(self):
        profile = self.repo.save_profile(
            "Brasil Digital padrão",
            {
                "wifi": {
                    "2.4GHz": {
                        "auto_channel": True,
                    }
                }
            },
            is_default=True,
        )

        self.assertTrue(
            profile["is_default"]
        )

        device = self.repo.upsert_device({
            "key": "SN1",
            "host": "10.0.0.1",
        })

        job = self.repo.create_batch_job(
            "profile_remediate",
            [
                device["id"],
            ],
            {
                "profile_id": profile["id"],
            },
        )

        finished = self.repo.update_batch_job(
            job["id"],
            status="completed",
            results=[
                {
                    "device_id": device["id"],
                    "success": True,
                }
            ],
        )

        self.assertEqual(
            finished["succeeded"],
            1,
        )
        self.assertEqual(
            finished["failed"],
            0,
        )


class ConfigDriftTests(unittest.TestCase):
    def test_only_expected_fields_create_drift(self):
        drift = DriftService().compare(
            {
                "wifi": {
                    "2.4GHz": {
                        "auto_channel": False,
                        "channel": 6,
                    }
                },
                "dns": {
                    "ipv4_1": "8.8.8.8",
                },
                "unrelated": {
                    "value": 123,
                },
            },
            {
                "wifi": {
                    "2.4GHz": {
                        "auto_channel": True,
                    }
                },
                "dns": {
                    "ipv4_1": "1.1.1.1",
                },
            },
        )

        paths = {
            item["path"]
            for item in drift["items"]
        }

        self.assertEqual(
            paths,
            {
                "wifi.2.4GHz.auto_channel",
                "dns.ipv4_1",
            },
        )
        self.assertEqual(
            drift["remediable"],
            2,
        )


class GatewayCommandPolicyTests(unittest.TestCase):
    def test_rejects_shell_injection_in_host(self):
        with self.assertRaises(
            ValueError
        ):
            GatewayCommandPolicy.build(
                "ping",
                {
                    "host": "1.1.1.1; rm -rf /",
                },
            )

    def test_iperf_is_built_as_argv_without_shell(self):
        command = GatewayCommandPolicy.build(
            "iperf3",
            {
                "host": "10.10.0.2",
                "duration": 10,
                "streams": 4,
                "reverse": True,
            },
        )

        self.assertEqual(
            command.argv[:3],
            [
                "iperf3",
                "-J",
                "-c",
            ],
        )
        self.assertIn(
            "-R",
            command.argv,
        )


class TopologyAndIncidentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = ManagementRepository(
            Path(
                self.temp.name
            )
            / "management.sqlite3"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_topology_contains_physical_chain(self):
        device = self.repo.upsert_device({
            "key": "SN-TOP",
            "model": "F670L",
            "status": "online",
            "host": "192.168.1.1",
            "cto": "CTO-1",
            "olt": "OLT-1",
            "pop": "POP-1",
        })

        result = TopologyService(
            self.repo
        ).build(
            device["id"],
            current_clients={
                "wifi": [
                    {
                        "hostname": "Celular",
                        "rssi": "-82",
                    }
                ],
                "lan": [],
            },
        )

        node_ids = {
            item["id"]
            for item in result["nodes"]
        }

        self.assertTrue(
            {
                "ont",
                "cto",
                "olt",
                "pop",
                "internet",
            }.issubset(
                node_ids
            )
        )

        wifi = next(
            item
            for item in result["nodes"]
            if item["kind"] == "client_wifi"
        )

        self.assertEqual(
            wifi["status"],
            "critical",
        )

    def test_incident_correlation_groups_unhealthy_cto(self):
        for index in range(5):
            self.repo.upsert_device({
                "key": f"SN-{index}",
                "status": "offline",
                "cto": "CTO-99",
                "olt": "OLT-9",
                "pop": "POP-X",
            })

        result = IncidentCorrelationService(
            self.repo
        ).correlate(
            minimum_devices=5
        )

        keys = {
            item["incident_key"]
            for item in result["incidents"]
        }

        self.assertIn(
            "cto:CTO-99",
            keys,
        )


if __name__ == "__main__":
    unittest.main()
