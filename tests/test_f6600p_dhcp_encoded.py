"""Encrypted F6600P DHCP reads and safeguarded round-trip writes."""
from __future__ import annotations

import base64
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from apps.zte_manager.model.zte import ZTE
from apps.zte_manager.model.zte_configuration import (
    zte_network_management as dhcp,
    zte_security,
)


class FakeRouter:
    session_tmp_token = "test-only-session-tmp-token"
    def __init__(self, *, declared=True, with_token=True):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.private = private
        self.public_key_pem = private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        if not with_token:
            self.session_tmp_token = None
        self.declared = declared
        self.values = {
            "IPAddr": "192.168.1.1", "SubMask": "255.255.255.0",
            "MinAddress": "192.168.1.10", "MaxAddress": "192.168.1.250",
            "ServerEnable": "1", "LeaseTime": "86400",
            "DNSServer1": "", "DNSServer2": "",
            "_InstID": "1",
        }
        self.last_fields = None
    def get_view(self, *_args, **_kwargs):
        return None
    def get_menu(self, tag):
        if tag == "Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua":
            row = dict(self.values)
            for field in ("MinAddress", "MaxAddress"):
                row[field] = zte_security.aes_encrypt_value(
                    row[field], "test-only-session-tmp-token",
                    "test-only-session-tmp-token"[::-1],
                )
            root = ET.Element("ajax_response_xml_root")
            if self.declared:
                ET.SubElement(root, "encode").text = "MinAddress,MaxAddress"
            obj = ET.SubElement(root, "OBJ_Br0AndDhcpsHosCfg_ID")
            inst = ET.SubElement(obj, "Instance")
            for name, value in row.items():
                ET.SubElement(inst, "ParaName").text = name
                ET.SubElement(inst, "ParaValue").text = value
            return ET.tostring(root, encoding="unicode")
        return "<ajax_response_xml_root/>"
    def _validar_resposta(self, value):
        if "<html" in value:
            raise ValueError("Login page")
    _parse_instances = staticmethod(ZTE._parse_instances)
    def fake_post(self, _zte, _tag, fields):
        posted = dict(fields)
        self.last_fields = posted
        if "encode" not in posted:
            raise AssertionError("Protected fields must be RSA/AES encrypted")
        pair = self.private.decrypt(
            base64.b64decode(posted["encode"]), padding.PKCS1v15()
        ).decode()
        key, iv = pair.split("+")
        for field in ("MinAddress", "MaxAddress"):
            self.values[field] = zte_security.aes_decrypt_value(
                posted[field], key, iv,
            )
        return "<ajax_response_xml_root/>"


class DhcpEncryptedTests(TestCase):
    def test_declared_and_implicit_ciphertext_decode_to_real_ip(self):
        for declared in (True, False):
            with self.subTest(declared=declared):
                router = FakeRouter(declared=declared)
                with patch.object(dhcp.ThinkLuaCrudGateway, "read",
                                  return_value=[]):
                    status = dhcp.dhcp_status(router)
                self.assertEqual(status["basic"]["MinAddress"], "192.168.1.10")
                self.assertEqual(status["basic"]["MaxAddress"], "192.168.1.250")
                self.assertEqual(status["dhcp_encoded_fields"],
                                 ["MaxAddress", "MinAddress"])
                self.assertTrue(status["write_safe"])
                self.assertNotIn("IZ9ZP", str(status))

    def test_missing_session_token_must_not_show_ciphertext_or_post(self):
        router = FakeRouter(with_token=False)
        with patch.object(dhcp.ThinkLuaCrudGateway, "read", return_value=[]):
            status = dhcp.dhcp_status(router)
            self.assertEqual(status["basic"]["MinAddress"], "")
            self.assertEqual(status["basic"]["MaxAddress"], "")
            self.assertFalse(status["write_safe"])
            self.assertNotIn("test-only-session-tmp-token", str(status))
            with self.assertRaisesRegex(ValueError, "protegidos"):
                dhcp.set_dhcp_basic(router, {"enabled": True})

    def test_protected_dhcp_post_preserves_validated_pool(self):
        router = FakeRouter()
        with (
            patch.object(dhcp.ThinkLuaCrudGateway, "read", return_value=[]),
            patch.object(dhcp, "post_menu", side_effect=router.fake_post),
        ):
            result = dhcp.set_dhcp_basic(router, {
                "min_address": "192.168.1.20",
                "max_address": "192.168.1.240",
            })
        self.assertTrue(result["verified"])
        self.assertEqual(result["after"]["basic"]["MinAddress"], "192.168.1.20")
        self.assertEqual(router.values["MaxAddress"], "192.168.1.240")
        self.assertNotEqual(router.last_fields["MinAddress"], "192.168.1.20")
        self.assertIn("encode", router.last_fields)


if __name__ == "__main__":
    import unittest
    unittest.main()
