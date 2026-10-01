from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from apps.zte_manager import api as api_module
from apps.zte_manager.infrastructure.huawei.client import HuaweiWebClient
from apps.zte_manager.services.device_service import DeviceService, DeviceSession
from apps.zte_manager.services.huawei_ipv4_filter_service import (
    HuaweiIPv4FilterRule,
    HuaweiIPv4FilterService,
)


FIXTURE = (
    Path(__file__).parent / "fixtures" / "huawei_ipincoming.html"
).read_text(encoding="utf-8")


def response(status=200, text="", url="http://192.168.18.1/"):
    return SimpleNamespace(
        status_code=status,
        text=text,
        url=url,
    )


class FakeHuaweiProvider:
    connected = True
    vendor = "huawei"
    model = "EG8041X7-10"
    current_host = "192.168.18.1"
    current_attendant = "tester"
    model_verified = True
    session_revision = "huawei-rev"
    writes_enabled = True
    capabilities = {
        "ipv4_filter": {
            "read": True,
            "create": True,
            "update": True,
            "delete": True,
            "verified": True,
        }
    }

    def device_status(self):
        return {
            "fabricante": "Huawei",
            "modelo": self.model,
            "host": self.current_host,
            "profile": "huawei_eg8041x7_10",
            "provider": "HuaweiService",
        }


class FakeZTEProvider:
    def __init__(self):
        self.connected = True
        self.calls = []
        self._zte = SimpleNamespace(writes_enabled=True)
        self._selected_model = "F6600P"
        self._model_verified = True
        self._adapter = SimpleNamespace(name="zte-f6600p-thinklua")
        self._device_info = {"modelo": "F6600P", "fabricante": "ZTE"}
        self._session_revision = "zte-rev"
        self.current_host = "192.0.2.1"
        self.current_attendant = "tester"

    def _mark(self, name, result):
        self.calls.append(name)
        return result

    def device_status(self):
        return self._mark("device_status", {"fabricante": "ZTE", "modelo": "F6600P"})

    def wan_status(self):
        return self._mark("wan_status", {"status": "ok"})

    def dhcp_status(self):
        return self._mark("dhcp_status", {"basic": {}})

    def tr069_setup(self):
        return self._mark("tr069_setup", {"available": True})

    def disconnect(self):
        self.connected = False


class MultivendorApiRoutingTests(unittest.TestCase):
    def make_huawei_manager(self):
        zte = FakeZTEProvider()
        manager = DeviceService(zte_provider=zte)
        huawei = FakeHuaweiProvider()
        manager._session = DeviceSession(
            vendor="huawei",
            model=huawei.model,
            profile="huawei_eg8041x7_10",
            provider="HuaweiService",
            service=huawei,
            capabilities=huawei.capabilities,
            model_verified=True,
            host=huawei.current_host,
            attendant=huawei.current_attendant,
            session_revision=huawei.session_revision,
        )
        return manager, zte

    def test_huawei_connected_device_status_does_not_call_zte(self):
        manager, zte = self.make_huawei_manager()
        with patch.object(api_module, "device_service", manager):
            result = api_module.device_status()
        self.assertEqual(result["fabricante"], "Huawei")
        self.assertEqual(result["modelo"], "EG8041X7-10")
        self.assertEqual(zte.calls, [])

    def test_huawei_connected_wan_status_does_not_call_zte(self):
        manager, zte = self.make_huawei_manager()
        with patch.object(api_module, "device_service", manager):
            result = api_module.wan_status()
        self.assertEqual(result["code"], "PROVIDER_FEATURE_UNAVAILABLE")
        self.assertIn("Huawei EG8041X7-10", result["error"])
        self.assertEqual(zte.calls, [])

    def test_huawei_connected_dhcp_does_not_call_zte(self):
        manager, zte = self.make_huawei_manager()
        with patch.object(api_module, "device_service", manager):
            result = api_module.dhcp_status()
        self.assertEqual(result["code"], "PROVIDER_FEATURE_UNAVAILABLE")
        self.assertEqual(zte.calls, [])

    def test_huawei_connected_tr069_does_not_call_zte(self):
        manager, zte = self.make_huawei_manager()
        with patch.object(api_module, "device_service", manager):
            result = api_module.tr069_setup()
        self.assertEqual(result["code"], "PROVIDER_FEATURE_UNAVAILABLE")
        self.assertEqual(zte.calls, [])

    def test_zte_common_route_still_uses_zte_provider(self):
        zte = FakeZTEProvider()
        manager = DeviceService(zte_provider=zte)
        manager._session = DeviceSession(
            vendor="zte",
            model="F6600P",
            profile="zte-f6600p-thinklua",
            provider="ZTEService",
            service=zte,
            model_verified=True,
            host=zte.current_host,
            attendant=zte.current_attendant,
            session_revision=zte._session_revision,
        )
        with patch.object(api_module, "device_service", manager):
            result = api_module.wan_status()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(zte.calls, ["wan_status"])


class FakeSession:
    def __init__(self, protected_pages, mutation_status=None):
        self.protected_pages = list(protected_pages)
        self.mutation_status = mutation_status
        self.cookies = requests.cookies.RequestsCookieJar()
        self.mutation_calls = 0
        self.closed = False

    def get(self, url, **kwargs):
        if url.rstrip("/") == "http://192.168.18.1":
            return response(200, "<html>Huawei</html>", url)
        if "ipincoming.asp" in url:
            if not self.protected_pages:
                raise AssertionError("unexpected protected GET")
            return self.protected_pages.pop(0)
        return response(200, "<html>Huawei</html>", url)

    def post(self, url, **kwargs):
        if "GetRandCount.asp" in url:
            return response(200, "0123456789abcdef0123456789abcdef", url)
        if "login.cgi" in url:
            return response(200, "<html>ok</html>", url)
        if "getMenuArray.asp" in url:
            return response(200, "Home Page ipincoming bbsp", url)
        if any(name in url for name in ("add.cgi", "set.cgi", "del.cgi")):
            self.mutation_calls += 1
            return response(
                self.mutation_status if self.mutation_status is not None else 200,
                "",
                url,
            )
        raise AssertionError("unexpected POST " + url)

    def close(self):
        self.closed = True


def client_with_session(session):
    client = HuaweiWebClient.__new__(HuaweiWebClient)
    client.base_url = "http://192.168.18.1"
    client.username = "Epadmin"
    client.password = "fixture"
    client.timeout = 0.1
    client.session = session
    return client


class HuaweiSessionRecoveryTests(unittest.TestCase):
    def test_huawei_get_403_relogin_retry_200_same_session(self):
        session = FakeSession([
            response(403, "Forbidden", "http://192.168.18.1/html/bbsp/ipincoming/ipincoming.asp"),
            response(200, FIXTURE, "http://192.168.18.1/html/bbsp/ipincoming/ipincoming.asp"),
        ])
        client = client_with_session(session)
        original = client.session
        page = client.get_page("/html/bbsp/ipincoming/ipincoming.asp")
        self.assertIn("RE\\x5fTEST", page)
        self.assertIs(client.session, original)

    def test_huawei_get_login_html_200_relogin(self):
        login_html = """
        <html><form action="/login.cgi">
        <input name="UserName"><input name="PassWord">
        <script src="/asp/GetRandCount.asp"></script>
        </form></html>
        """
        session = FakeSession([
            response(200, login_html, "http://192.168.18.1/"),
            response(200, FIXTURE, "http://192.168.18.1/html/bbsp/ipincoming/ipincoming.asp"),
        ])
        client = client_with_session(session)
        original = client.session
        page = client.get_page("/html/bbsp/ipincoming/ipincoming.asp")
        self.assertIn("stFilterIn", page)
        self.assertIs(client.session, original)

    @staticmethod
    def rule(name="RE_TEST_01", lan_tcp="41001", wan_tcp="42002"):
        return HuaweiIPv4FilterRule(
            domain="InternetGatewayDevice.X_HW_Security.IpFilterIn.1",
            name=name,
            protocol="TCP",
            direction="Bidirectional",
            lan_start_ip="192.168.18.240",
            lan_end_ip="192.168.18.241",
            wan_start_ip="203.0.113.10",
            wan_end_ip="203.0.113.11",
            lan_tcp_port=lan_tcp,
            wan_tcp_port=wan_tcp,
        )

    def service(self, client):
        from apps.zte_manager.model.device_adapters.huawei import (
            HuaweiIPv4FilterCapability,
        )
        return HuaweiIPv4FilterService(
            client,
            model="EG8041X7-10",
            capability=HuaweiIPv4FilterCapability(
                read=True,
                create=True,
                update=True,
                delete=True,
                verified=True,
            ),
            sleep=lambda _seconds: None,
            readback_tries=1,
        )

    def test_mutation_post_403_is_not_replayed_create_update_delete(self):
        empty = (
            '<input type="hidden" id="hwonttoken" '
            'value="fixture-token-1234567890">'
        )
        updated = FIXTURE.replace("41001", "41011").replace("42002", "42012")

        cases = (
            (
                "create",
                [response(200, empty), response(200, FIXTURE)],
                lambda svc: svc.create_ipv4_filter(self.rule()),
            ),
            (
                "update",
                [response(200, FIXTURE), response(200, updated)],
                lambda svc: svc.update_ipv4_filter(
                    "InternetGatewayDevice.X_HW_Security.IpFilterIn.1",
                    self.rule(lan_tcp="41011", wan_tcp="42012"),
                ),
            ),
            (
                "delete",
                [response(200, FIXTURE), response(200, empty)],
                lambda svc: svc.delete_ipv4_filter(
                    "InternetGatewayDevice.X_HW_Security.IpFilterIn.1"
                ),
            ),
        )

        for name, pages, action in cases:
            with self.subTest(name=name):
                session = FakeSession(pages, mutation_status=403)
                client = client_with_session(session)
                result = action(self.service(client))
                self.assertTrue(result["verified"])
                self.assertTrue(result["success"])
                self.assertEqual(session.mutation_calls, 1)


if __name__ == "__main__":
    unittest.main()
