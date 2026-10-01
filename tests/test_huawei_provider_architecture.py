from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from apps.zte_manager.infrastructure.huawei.detector import HuaweiDetector
from apps.zte_manager.model.device_adapters.huawei import (
    canonical_huawei_model,
    resolve_huawei_profile,
)
from apps.zte_manager.services.device_service import DeviceService
from apps.zte_manager.services.huawei_service import HuaweiService
import apps.zte_manager.services.huawei_service as huawei_module


FIXTURES = Path(__file__).parent / "fixtures"
DEVICE_HTML = (
    FIXTURES / "huawei_deviceinfo_eg8041x7.html"
).read_text(encoding="utf-8")


class FakeHuaweiWebClient:
    device_html = ""
    login_calls = 0

    def __init__(
        self,
        host,
        username,
        password,
        *,
        https=False,
        timeout=10.0,
    ):
        scheme = "https" if https else "http"
        self.base_url = (
            host.rstrip("/")
            if str(host).startswith(("http://", "https://"))
            else f"{scheme}://{str(host).rstrip('/')}"
        )
        self.username = username
        self.password = password
        self.timeout = timeout
        self.closed = False

    @classmethod
    def looks_like_huawei(
        cls,
        host,
        *,
        https=False,
        timeout=2.5,
    ):
        return True

    def login(self, retries=4):
        type(self).login_calls += 1
        return True

    def get_page(self, path):
        if path == "/html/ssmp/deviceinfo/deviceinfo.asp":
            return type(self).device_html
        if path == "/html/bbsp/ipincoming/ipincoming.asp":
            return (
                '<input type="hidden" id="hwonttoken" '
                'value="fixture-token-1234567890">'
            )
        return "<html><body>Huawei WebUI</body></html>"

    def close(self):
        self.closed = True


class FakeHuaweiFingerprint:
    result = False

    @classmethod
    def looks_like_huawei(
        cls,
        host,
        *,
        https=False,
        timeout=2.5,
    ):
        return cls.result


class FakeZTEProvider:
    def __init__(self):
        self.connected = False
        self.connect_calls = 0
        self.disconnect_calls = 0
        self._zte = SimpleNamespace(writes_enabled=True)
        self._selected_model = "F6600P"
        self._model_verified = True
        self._adapter = SimpleNamespace(name="zte-f6600p-thinklua")
        self._device_info = {
            "fabricante": "ZTE",
            "modelo": "F6600P",
        }
        self._session_revision = "zte-revision"
        self.current_host = None
        self.current_attendant = None

    def connect(self, **kwargs):
        self.connect_calls += 1
        self.connected = True
        self.current_host = kwargs["ip"]
        self.current_attendant = kwargs.get("attendant") or "default"
        return {
            "success": True,
            "host": self.current_host,
            "attendant": self.current_attendant,
            "reused_session": False,
            "model": "F6600P",
            "model_verified": True,
            "session_revision": self._session_revision,
            "writes_enabled": True,
            "device": self._device_info,
            "adapter": "zte-f6600p-thinklua",
        }

    def disconnect(self):
        self.disconnect_calls += 1
        self.connected = False


class HuaweiProviderArchitectureTests(unittest.TestCase):
    def setUp(self):
        FakeHuaweiWebClient.login_calls = 0
        FakeHuaweiWebClient.device_html = ""

        self.history_patchers = [
            patch.object(
                huawei_module.history_repository,
                "start_session",
                return_value=77,
            ),
            patch.object(
                huawei_module.history_repository,
                "save_snapshot",
                return_value=1,
            ),
            patch.object(
                huawei_module.history_repository,
                "save_change",
                return_value=1,
            ),
            patch.object(
                huawei_module.history_repository,
                "end_session",
                return_value=None,
            ),
        ]
        for patcher in self.history_patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def make_huawei(self):
        return HuaweiService(
            client_factory=FakeHuaweiWebClient,
            detector=HuaweiDetector,
        )

    def test_detect_huawei_eg8041x7_10(self):
        for raw in (
            "Huawei EG8041X7-10",
            "EG8041X7-10",
            "EG8041X7 10",
            "EG8041X7_10",
            "EG8041X710",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(
                    canonical_huawei_model(raw),
                    "EG8041X7-10",
                )
                profile = resolve_huawei_profile(
                    raw,
                    unknown=False,
                )
                self.assertIsNotNone(profile)
                self.assertEqual(
                    profile.key,
                    "huawei_eg8041x7_10",
                )

        client = FakeHuaweiWebClient(
            "192.168.18.1",
            "Epadmin",
            "fixture",
        )
        FakeHuaweiWebClient.device_html = DEVICE_HTML
        detection = HuaweiDetector.detect_authenticated(
            client
        )
        self.assertEqual(
            detection.vendor,
            "huawei",
        )
        self.assertEqual(
            detection.model,
            "EG8041X7-10",
        )
        self.assertTrue(
            detection.verified
        )

    def test_manual_huawei_profile_is_not_overwritten(self):
        service = self.make_huawei()
        result = service.connect(
            "192.168.18.1",
            "Epadmin",
            "fixture",
            model_hint="Huawei EG8041X7-10",
        )
        self.assertEqual(
            result["profile"],
            "huawei_eg8041x7_10",
        )
        self.assertEqual(
            result["model"],
            "EG8041X7-10",
        )
        self.assertEqual(
            result["model_source"],
            "manual_profile",
        )

    def test_eg8041x7_ipv4_filter_is_verified(self):
        service = self.make_huawei()
        result = service.connect(
            "192.168.18.1",
            "Epadmin",
            "fixture",
            model_hint="EG8041X7 10",
        )
        self.assertEqual(
            result["capabilities"]["ipv4_filter"],
            {
                "read": True,
                "create": True,
                "update": True,
                "delete": True,
                "verified": True,
            },
        )

    def test_eg8041x7_ipv4_filter_is_not_read_only(self):
        service = self.make_huawei()
        result = service.connect(
            "192.168.18.1",
            "Epadmin",
            "fixture",
            model_hint="EG8041X7-10",
        )
        self.assertTrue(
            result["writes_enabled"]
        )
        self.assertTrue(
            result["model_verified"]
        )

    def test_unknown_huawei_remains_unverified(self):
        service = self.make_huawei()
        result = service.connect(
            "192.168.18.1",
            "Epadmin",
            "fixture",
        )
        cap = result[
            "capabilities"
        ][
            "ipv4_filter"
        ]
        self.assertTrue(
            cap["read"]
        )
        self.assertFalse(
            cap["create"]
        )
        self.assertFalse(
            cap["update"]
        )
        self.assertFalse(
            cap["delete"]
        )
        self.assertFalse(
            cap["verified"]
        )
        self.assertFalse(
            result["writes_enabled"]
        )

    def test_huawei_uses_huawei_service_not_zte_service(self):
        zte = FakeZTEProvider()
        manager = DeviceService(
            zte_provider=zte,
            huawei_factory=self.make_huawei,
            huawei_client_type=FakeHuaweiFingerprint,
        )
        manager.connect(
            "192.168.18.1",
            "Epadmin",
            "fixture",
            model_hint="EG8041X7-10",
        )
        self.assertIsInstance(
            manager.session.service,
            HuaweiService,
        )
        self.assertEqual(
            zte.connect_calls,
            0,
        )

    def test_connect_dispatches_huawei_service(self):
        FakeHuaweiFingerprint.result = True
        FakeHuaweiWebClient.device_html = DEVICE_HTML
        zte = FakeZTEProvider()
        manager = DeviceService(
            zte_provider=zte,
            huawei_factory=self.make_huawei,
            huawei_client_type=FakeHuaweiFingerprint,
        )
        result = manager.connect(
            "192.168.18.1",
            "Epadmin",
            "fixture",
        )
        self.assertEqual(
            result["vendor"],
            "huawei",
        )
        self.assertEqual(
            result["provider"],
            "HuaweiService",
        )
        self.assertEqual(
            zte.connect_calls,
            0,
        )

    def test_connect_dispatches_zte_service(self):
        FakeHuaweiFingerprint.result = False
        zte = FakeZTEProvider()
        manager = DeviceService(
            zte_provider=zte,
            huawei_factory=self.make_huawei,
            huawei_client_type=FakeHuaweiFingerprint,
        )
        result = manager.connect(
            "192.168.18.1",
            "admin",
            "fixture",
        )
        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            zte.connect_calls,
            1,
        )
        self.assertEqual(
            manager.session.vendor,
            "zte",
        )
        self.assertIs(
            manager.session.service,
            zte,
        )

    def test_huawei_filter_refresh_preserves_all_capabilities(self):
        zte = FakeZTEProvider()
        manager = DeviceService(
            zte_provider=zte,
            huawei_factory=self.make_huawei,
            huawei_client_type=FakeHuaweiFingerprint,
        )
        manager.connect(
            "192.168.18.1",
            "Epadmin",
            "fixture",
            model_hint="EG8041X7-10",
        )
        before = set(manager.status()["capabilities"])
        self.assertIn("dhcp", before)
        self.assertIn("wifi_basic", before)

        manager.list_ipv4_filters()

        after = set(manager.status()["capabilities"])
        self.assertEqual(after, before)
        self.assertIn("ipv4_filter", after)

    def test_huawei_bootstrap_uses_native_capability_catalog(self):
        FakeHuaweiWebClient.device_html = DEVICE_HTML
        zte = FakeZTEProvider()
        manager = DeviceService(
            zte_provider=zte,
            huawei_factory=self.make_huawei,
            huawei_client_type=FakeHuaweiFingerprint,
        )
        manager.connect(
            "192.168.18.1",
            "Epadmin",
            "fixture",
            model_hint="EG8041X7-10",
        )

        from apps.zte_manager import api as api_module

        with patch.object(
            api_module,
            "device_service",
            manager,
        ):
            bootstrap = api_module.discovery_bootstrap()

        self.assertEqual(bootstrap["vendor"], "huawei")
        self.assertTrue(bootstrap["native_diagnostics_available"])
        self.assertEqual(
            bootstrap["catalog"]["models"][0]["model"],
            "EG8041X7-10",
        )
        self.assertIn(
            "dhcp",
            bootstrap["catalog"]["models"][0]["candidate_features"],
        )

    def test_huawei_multimodel_probe_never_calls_zte_provider(self):
        FakeHuaweiWebClient.device_html = DEVICE_HTML
        zte = FakeZTEProvider()
        manager = DeviceService(
            zte_provider=zte,
            huawei_factory=self.make_huawei,
            huawei_client_type=FakeHuaweiFingerprint,
        )
        manager.connect(
            "192.168.18.1",
            "Epadmin",
            "fixture",
            model_hint="EG8041X7-10",
        )

        from apps.zte_manager import api as api_module

        with patch.object(
            api_module,
            "device_service",
            manager,
        ), patch.object(
            api_module.zte_service,
            "multimodel_probe",
            side_effect=AssertionError("ZTE probe must not run"),
        ):
            result = api_module.multimodel_probe()

        self.assertEqual(result["model"], "EG8041X7-10")
        self.assertEqual(result["family"], "huawei_webui")
        self.assertTrue(
            any(
                item["feature"] == "dhcp"
                for item in result["capabilities"]
            )
        )

    def test_huawei_device_status_reads_authenticated_device_page(self):
        FakeHuaweiWebClient.device_html = DEVICE_HTML
        service = self.make_huawei()
        service.connect(
            "192.168.18.1",
            "Epadmin",
            "fixture",
            model_hint="EG8041X7-10",
        )
        status = service.device_status()
        self.assertEqual(status["fabricante"], "Huawei")
        self.assertEqual(status["modelo"], "Huawei EG8041X7-10")
        self.assertEqual(status["profile"], "huawei_eg8041x7_10")

    def test_huawei_capabilities_reach_frontend(self):
        FakeHuaweiWebClient.device_html = DEVICE_HTML
        zte = FakeZTEProvider()
        manager = DeviceService(
            zte_provider=zte,
            huawei_factory=self.make_huawei,
            huawei_client_type=FakeHuaweiFingerprint,
        )
        manager.connect(
            "192.168.18.1",
            "Epadmin",
            "fixture",
            model_hint="EG8041X7-10",
        )

        from apps.zte_manager import api as api_module

        with patch.object(
            api_module,
            "device_service",
            manager,
        ):
            status = api_module.connection_status()

        self.assertEqual(
            status["vendor"],
            "huawei",
        )
        self.assertEqual(
            status["profile"],
            "huawei_eg8041x7_10",
        )
        self.assertEqual(
            status["capabilities"]["ipv4_filter"]["create"],
            True,
        )
        self.assertEqual(
            status["capabilities"]["ipv4_filter"]["update"],
            True,
        )
        self.assertEqual(
            status["capabilities"]["ipv4_filter"]["delete"],
            True,
        )


if __name__ == "__main__":
    unittest.main()
