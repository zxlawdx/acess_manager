"""Non-secret provider profiles, PPPoE/TR069 WAN gating and named variants."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.zte_manager.repositories.profile_repository import ProfileRepository
from apps.zte_manager.services.named_preset_service import (
    NamedPresetService, PRIMARY,
)
from apps.zte_manager.services.tr069_profile_service import (
    TR069ProviderProfiles, validate_provider,
)
from apps.zte_manager.services.zte_service import ZTEService


class ProviderProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = TR069ProviderProfiles(
            Path(self.temp.name) / "acs-profiles.json"
        )

    @staticmethod
    def payload():
        return {
            "name": "Example Network", "url": "https://acs.example.net/tr069",
            "username": "operator",
            "connection_request_username": "remote",
            "periodic_inform_enabled": True,
            "periodic_inform_interval": 1200,
        }

    def test_provider_storage_excludes_passwords_and_builtin_is_editable(self):
        self.assertIn("Brasil Digital", [p["name"] for p in self.store.list()])
        profile = self.store.save(self.payload())
        self.assertEqual(profile["url"], "https://acs.example.net/tr069")
        raw = (Path(self.temp.name) / "acs-profiles.json").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("password", raw.lower())
        self.assertEqual(
            [p["name"] for p in self.store.list()],
            ["Brasil Digital", "Example Network"],
        )
        self.assertTrue(self.store.delete("Example Network"))
        self.assertEqual(len(self.store.list()), 1)

    def test_secrets_or_credentials_in_acs_url_are_rejected(self):
        for extra in [
            {"password": "NOT_FOR_DISK"},
            {"connection_request_password": "NOT_FOR_DISK"},
            {"url": "https://user:private@acs.example.net/tr069"},
        ]:
            with self.subTest(extra=tuple(extra)):
                with self.assertRaises(ValueError):
                    validate_provider({**self.payload(), **extra})

    def test_300_and_1200_second_variants(self):
        for seconds in (300, 1200):
            provider = validate_provider({
                **self.payload(), "periodic_inform_interval": seconds
            })
            self.assertEqual(provider["periodic_inform_interval"], seconds)

    def test_wan_is_rejected_without_both_ppp_and_tr069(self):
        rows = [
            {"WANCName": "Internet_TR069", "linkMode": "PPP",
             "StrServList": "INTERNET,TR069", "_InstID": "1"},
            {"WANCName": "InternetOnly", "linkMode": "PPP",
             "StrServList": "INTERNET", "_InstID": "2"},
            {"WANCName": "MgmtBridge", "linkMode": "IP",
             "StrServList": "TR069", "_InstID": "3"},
        ]
        self.assertEqual(
            [r["name"] for r in ZTEService._tr069_wan_candidates(rows)],
            ["Internet_TR069"],
        )
        instance = ZTEService()
        fake = type("FakeRouter", (), {
            "wan_configurations": lambda self: rows,
            "tr069_management_status": lambda self: {
                "available": True,
                "server": {"URL": "https://acs.example.net",
                           "UserPassword": "••••••••",
                           "ConnectionRequestPassword": "••••••••"},
            },
        })()
        with (
            patch.object(instance, "get_client", return_value=fake),
            patch(
                "apps.zte_manager.services.zte_service.tr069_provider_profiles.list",
                return_value=[self.payload()],
            ),
            patch.object(instance, "_run_change", return_value={"success":True}) as change,
        ):
            for invalid in ("InternetOnly", "MgmtBridge", ""):
                with self.subTest(invalid=invalid):
                    with self.assertRaises(ValueError):
                        instance.apply_tr069_provider(
                            "Example Network", invalid
                        )
            change.assert_not_called()
            self.assertEqual(
                instance.tr069_setup()["wan_candidates"][0]["name"],
                "Internet_TR069",
            )
            report = instance.apply_tr069_provider(
                "Example Network", "Internet_TR069"
            )
            self.assertTrue(report["success"])
            self.assertEqual(change.call_args.kwargs["operation"],
                             "tr069_provider_apply")
            self.assertEqual(change.call_args.kwargs["target"],
                             "Internet_TR069")

    def test_named_variant_isolated_by_technician(self):
        store = NamedPresetService(
            ProfileRepository(Path(self.temp.name) / "named.json")
        )
        self.assertEqual(store.list("tech-a"), [PRIMARY])
        legacy = store.get("tech-a", PRIMARY)
        custom = {**legacy, "dns": {**legacy["dns"], "ipv4_1": "1.1.1.1"}}
        store.save("tech-a", "Cliente empresarial", custom)
        self.assertEqual(
            store.list("tech-a"), [PRIMARY, "Cliente empresarial"]
        )
        self.assertEqual(store.list("tech-b"), [PRIMARY])
        self.assertEqual(
            store.get("tech-a", "Cliente empresarial")["dns"]["ipv4_1"],
            "1.1.1.1",
        )
        self.assertNotEqual(
            store.get("tech-a", PRIMARY)["dns"]["ipv4_1"], "1.1.1.1"
        )
        self.assertTrue(store.delete("tech-a", "Cliente empresarial"))
        self.assertEqual(store.list("tech-a"), [PRIMARY])


if __name__ == "__main__":
    unittest.main()
