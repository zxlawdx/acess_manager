from __future__ import annotations

import unittest
from copy import deepcopy
from unittest.mock import patch

from apps.zte_manager.services.huawei_captured_features import (
    HuaweiCapturedFeatureService,
)
from apps.zte_manager.services.huawei_eg8041x7_runtime import (
    HuaweiEG8041X7CapturedFeatureService,
)


SEARCH_ROOT = "InternetGatewayDevice.X_HW_DNS.SearList"
HOST_ROOT = "InternetGatewayDevice.X_HW_DNS.HOSTS"


PHYSICAL_DNS = {
    "domain_name": "",
    "ipv4_1": "177.221.56.3",
    "ipv4_2": "177.221.56.10",
    "ipv6_1": "2804:1128::3",
    "ipv6_2": "2804:1128::10",
    "hosts": [
        {"id": HOST_ROOT + ".2", "nome": "google", "ip": "8.8.8.8"},
        {"id": HOST_ROOT + ".3", "nome": "cloudflare", "ip": "1.1.1.1"},
    ],
    "_search_rows": [
        {
            "Domain": SEARCH_ROOT + ".1",
            "DNSServer": "177.221.56.3",
            "DomainName": "",
            "Interface": "wan1.1.ppp1",
        },
        {
            "Domain": SEARCH_ROOT + ".2",
            "DNSServer": "177.221.56.10",
            "DomainName": "",
            "Interface": "wan1.1.ppp1",
        },
        {
            "Domain": SEARCH_ROOT + ".3",
            "DNSServer": "2804:1128::3",
            "DomainName": "",
            "Interface": "wan1.1.ppp1",
        },
        {
            "Domain": SEARCH_ROOT + ".4",
            "DNSServer": "2804:1128::10",
            "DomainName": "",
            "Interface": "wan1.1.ppp1",
        },
    ],
}


class DummyClient:
    def __init__(self):
        self.posts = []


class PhysicalStateService(HuaweiEG8041X7CapturedFeatureService):
    def dns_status(self):
        return deepcopy(PHYSICAL_DNS)


class HuaweiPhysicalDnsRegressionTests(unittest.TestCase):
    def test_dns_status_drops_constructor_calls_from_page_functions(self):
        raw = deepcopy(PHYSICAL_DNS)
        raw["_search_rows"].append({
            "Domain": "CurrentDomain",
            "DNSServer": 'getValue("DNSServer")',
            "DomainName": 'getValue("DSLDomainName")',
            "Interface": 'getValue("WanNameList")',
        })
        raw["hosts"].insert(0, {
            "id": "",
            "nome": 'getValue("DomainName")',
            "ip": 'getValue("IPAddress")',
        })

        service = HuaweiEG8041X7CapturedFeatureService(
            DummyClient(),
            model="EG8041X7-10",
            sleep=lambda _delay: None,
        )
        with patch.object(
            HuaweiCapturedFeatureService,
            "dns_status",
            return_value=raw,
        ):
            status = service.dns_status()

        self.assertEqual(len(status["_search_rows"]), 4)
        self.assertEqual(len(status["hosts"]), 2)
        self.assertEqual(status["domain_name"], "")
        self.assertEqual(status["ipv4_1"], "177.221.56.3")
        self.assertEqual(status["ipv4_2"], "177.221.56.10")
        self.assertEqual(status["ipv6_1"], "2804:1128::3")
        self.assertEqual(status["ipv6_2"], "2804:1128::10")
        self.assertNotIn(
            'getValue("DomainName")',
            {item["nome"] for item in status["hosts"]},
        )

    def test_physical_default_dns_is_noop_even_with_empty_domain_name(self):
        client = DummyClient()
        service = PhysicalStateService(
            client,
            model="EG8041X7-10",
            sleep=lambda _delay: None,
        )

        result = service.set_dns({
            "domain_name": "",
            "ipv4_1": "177.221.56.3",
            "ipv4_2": "177.221.56.10",
            "ipv6_1": "2804:1128::3",
            "ipv6_2": "2804:1128::10",
            "hosts": [
                {"nome": "cloudflare", "ip": "1.1.1.1"},
                {"nome": "google", "ip": "8.8.8.8"},
            ],
        })

        self.assertTrue(result["success"])
        self.assertTrue(result["verified"])
        self.assertTrue(result["semantic_verified"])
        self.assertEqual(result["results"], [])
        self.assertEqual(client.posts, [])


if __name__ == "__main__":
    unittest.main()
