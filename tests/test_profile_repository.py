import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from apps.zte_manager.repositories.profile_repository import ProfileRepository
from apps.zte_manager.services.profile_service import (
    DEFAULT_PROFILE,
    HUAWEI_EG8041X7_DEFAULT_PROFILE,
    ProfileService,
    _normalize_profile,
)


class ProfileRepositoryTest(unittest.TestCase):
    def test_persiste_perfil_por_atendente(self):
        with tempfile.TemporaryDirectory() as tmp:
            repository = ProfileRepository(
                Path(tmp) / "profiles.json"
            )

            repository.save(
                "law",
                DEFAULT_PROFILE
            )

            self.assertIn(
                "law",
                repository.list()
            )

            profile = repository.get(
                "law"
            )

            self.assertEqual(
                profile["wifi"]["2.4GHz"]["bandwidth"],
                "20MHz"
            )

    def test_huawei_eg8041x7_uses_separate_physical_defaults_and_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ProfileService(base_dir=tmp)

            zte = service.get_profile("law")
            huawei = service.get_profile(
                "law",
                provider="huawei",
                model="EG8041X7-10",
            )

            self.assertEqual(
                zte["wifi"]["2.4GHz"]["bandwidth"],
                "20MHz",
            )
            self.assertEqual(
                huawei,
                HUAWEI_EG8041X7_DEFAULT_PROFILE,
            )
            self.assertEqual(
                huawei["wifi"]["2.4GHz"]["bandwidth_code"],
                "0",
            )
            self.assertEqual(
                huawei["wifi"]["5GHz"]["bandwidth_code"],
                "4",
            )
            self.assertEqual(
                huawei["wifi"]["2.4GHz"]["standard"],
                "11ax",
            )
            self.assertEqual(
                huawei["wifi"]["5GHz"]["standard"],
                "11ax",
            )
            self.assertEqual(huawei["dns"]["domain_name"], "")
            self.assertEqual(huawei["dns"]["ipv4_1"], "177.221.56.3")
            self.assertEqual(huawei["dns"]["ipv4_2"], "177.221.56.10")
            self.assertEqual(huawei["dns"]["ipv6_1"], "2804:1128::3")
            self.assertEqual(huawei["dns"]["ipv6_2"], "2804:1128::10")
            self.assertEqual(
                {
                    (item["nome"], item["ip"])
                    for item in huawei["dns"]["hosts"]
                },
                {
                    ("cloudflare", "1.1.1.1"),
                    ("google", "8.8.8.8"),
                },
            )

            service.save_profile(
                "law",
                {
                    "wifi": {
                        "2.4GHz": {
                            "bandwidth": "40MHz",
                        },
                    },
                },
            )
            untouched_huawei = service.get_profile(
                "law",
                provider="huawei",
                model="EG8041X7-10",
            )
            self.assertEqual(
                untouched_huawei["wifi"]["2.4GHz"]["bandwidth"],
                "Auto",
            )

    def test_huawei_legacy_zte_dns_default_remains_physical_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ProfileService(base_dir=tmp)
            repository, _defaults = service._repository(
                "huawei",
                "EG8041X7-10",
            )
            legacy = deepcopy(HUAWEI_EG8041X7_DEFAULT_PROFILE)
            legacy["dns"] = deepcopy(DEFAULT_PROFILE["dns"])
            repository.save("law", legacy)

            loaded = service.get_profile(
                "law",
                provider="huawei",
                model="EG8041X7-10",
            )

            self.assertEqual(
                loaded["dns"],
                HUAWEI_EG8041X7_DEFAULT_PROFILE["dns"],
            )

    def test_huawei_one_search_legacy_default_is_migrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ProfileService(base_dir=tmp)
            repository, _defaults = service._repository(
                "huawei",
                "EG8041X7-10",
            )
            legacy = deepcopy(HUAWEI_EG8041X7_DEFAULT_PROFILE)
            legacy["dns"] = {
                "domain_name": "cloudflare.com",
                "ipv4_1": "177.221.56.3",
                "ipv4_2": "",
                "ipv6_1": "",
                "ipv6_2": "",
                "hosts": [
                    {"nome": "cloudflare", "ip": "1.1.1.1"},
                    {"nome": "google", "ip": "8.8.8.8"},
                ],
            }
            repository.save("law", legacy)

            migrated = service.get_profile(
                "law",
                provider="huawei",
                model="EG8041X7-10",
            )

            self.assertEqual(
                migrated["dns"],
                HUAWEI_EG8041X7_DEFAULT_PROFILE["dns"],
            )
            self.assertEqual(
                repository.get("law")["dns"],
                HUAWEI_EG8041X7_DEFAULT_PROFILE["dns"],
            )

    def test_huawei_custom_dns_is_not_migrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ProfileService(base_dir=tmp)
            repository, _defaults = service._repository(
                "huawei",
                "EG8041X7-10",
            )
            custom = deepcopy(HUAWEI_EG8041X7_DEFAULT_PROFILE)
            custom["dns"] = {
                **deepcopy(DEFAULT_PROFILE["dns"]),
                "domain_name": "rede.local",
                "ipv4_1": "9.9.9.9",
            }
            repository.save("law", custom)

            loaded = service.get_profile(
                "law",
                provider="huawei",
                model="EG8041X7-10",
            )

            self.assertEqual(loaded["dns"]["domain_name"], "rede.local")
            self.assertEqual(loaded["dns"]["ipv4_1"], "9.9.9.9")

    def test_normalizacao_preserva_dns_do_atendente(self):
        profile = _normalize_profile({
            "dns": {
                "domain_name": "rede.local",
                "ipv4_1": "1.1.1.1",
                "hosts": [
                    {
                        "nome": "cloudflare",
                        "ip": "1.1.1.1",
                    }
                ],
                "campo_interno": "nao-deve-entrar",
            }
        })

        self.assertEqual(
            profile["dns"]["domain_name"],
            "rede.local"
        )

        self.assertEqual(
            profile["dns"]["ipv4_1"],
            "1.1.1.1"
        )

        self.assertEqual(
            profile["dns"]["hosts"],
            [
                {
                    "nome": "cloudflare",
                    "ip": "1.1.1.1",
                }
            ]
        )

        self.assertNotIn(
            "campo_interno",
            profile["dns"]
        )


if __name__ == "__main__":
    unittest.main()
