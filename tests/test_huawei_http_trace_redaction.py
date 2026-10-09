from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from apps.zte_manager.infrastructure.huawei.client import _trace_http


class HuaweiHttpTraceRedactionTests(unittest.TestCase):
    def test_raw_trace_alias_never_prints_credentials_tokens_or_psk(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"HUAWEI_HTTP_TRACE": "raw"}, clear=False):
            with redirect_stdout(output):
                _trace_http(
                    phase="request",
                    method="POST",
                    url="http://192.168.18.1/login.cgi",
                    payload={
                        "PassWord": "BASE64_SECRET",
                        "x.X_HW_Token": "TOKEN_SECRET",
                        "k.PreSharedKey": "WIFI_SECRET",
                        "SSID": "LAW_5G",
                    },
                    headers={
                        "Cookie": "CookieHttp=COOKIE_SECRET",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    body="BASE64_SECRET TOKEN_SECRET WIFI_SECRET COOKIE_SECRET",
                )

        text = output.getvalue()
        self.assertIn("LAW_5G", text)
        self.assertIn("<redacted>", text)
        self.assertIn("body=<omitted:", text)
        for secret in (
            "BASE64_SECRET",
            "TOKEN_SECRET",
            "WIFI_SECRET",
            "COOKIE_SECRET",
        ):
            self.assertNotIn(secret, text)


if __name__ == "__main__":
    unittest.main()
