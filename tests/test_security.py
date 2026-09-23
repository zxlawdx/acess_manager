import unittest

from apps.zte_manager.model.zte_configuration.zte_security import (
    aes_decrypt_value,
    aes_encrypt_value,
    build_form_body,
    extract_session_tmp_token,
)


class SecurityTest(unittest.TestCase):
    def test_extrai_token_hex_da_menu_view(self):
        html = '_sessionTmpToken = "\\x31\\x32\\x33\\x34";'

        self.assertEqual(
            extract_session_tmp_token(
                html
            ),
            "1234"
        )

    def test_form_body_usa_encode_component_do_browser(self):
        body = build_form_body([
            ("SSID", "Minha Rede"),
            ("value", "a+b/c="),
        ])

        self.assertEqual(
            body,
            "SSID=Minha%20Rede&value=a%2Bb%2Fc%3D"
        )

    def test_aes_roundtrip_do_firmware(self):
        encrypted = aes_encrypt_value(
            "senha1234",
            "1234567890123456",
            "6543210987654321"
        )

        decrypted = aes_decrypt_value(
            encrypted,
            "1234567890123456",
            "6543210987654321"
        )

        self.assertEqual(
            decrypted,
            "senha1234"
        )


if __name__ == "__main__":
    unittest.main()
