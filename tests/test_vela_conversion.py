import re
import unittest
from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[1]


class VelaConversionTest(unittest.TestCase):
    def test_frontend_nao_depende_de_fastapi_5000(self):
        javascript = (
            ROOT
            / "apps"
            / "zte_manager"
            / "static"
            / "js"
            / "app.js"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'const API_BASE = "/api";',
            javascript
        )

        self.assertNotIn(
            "127.0.0.1:5000",
            javascript
        )

        self.assertNotIn(
            'method: "PATCH"',
            javascript
        )

    def test_template_usa_static_do_vela(self):
        template = (
            ROOT
            / "apps"
            / "zte_manager"
            / "templates"
            / "index.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "{{ static('zte_manager/css/style.css') }}",
            template
        )

        self.assertIn(
            "{{ static('zte_manager/js/app.js') }}",
            template
        )

        self.assertNotIn(
            'src="/static/',
            template
        )

    def test_endpoints_usados_pela_ui_estao_registrados(self):
        javascript = (
            ROOT
            / "apps"
            / "zte_manager"
            / "static"
            / "js"
            / "app.js"
        ).read_text(
            encoding="utf-8"
        )

        api_source = (
            ROOT
            / "apps"
            / "zte_manager"
            / "api.py"
        ).read_text(
            encoding="utf-8"
        )

        registered = set(
            re.findall(
                r'@api\.(?:get|post|put|delete)\("([^"]+)"\)',
                api_source
            )
        )

        called = set()

        for match in re.finditer(
            r'apiRequest\(\s*([`"])(.+?)\1',
            javascript,
            re.DOTALL
        ):
            endpoint = match.group(2).split("?", 1)[0]

            # Não há mais path dinâmico na API Vela desta versão.
            if "${" not in endpoint:
                called.add(
                    endpoint
                )

        missing = sorted(
            called - registered
        )

        self.assertEqual(
            missing,
            []
        )


class ProfileDomRegressionTest(unittest.TestCase):
    def test_profile_cards_sao_criados_antes_do_query_selector(self):
        javascript = (
            ROOT
            / "apps"
            / "zte_manager"
            / "static"
            / "js"
            / "app.js"
        ).read_text(
            encoding="utf-8"
        )

        render_start = javascript.index(
            "async function renderProfileForm(profile)"
        )

        render_end = javascript.index(
            "function renderProfileHosts",
            render_start
        )

        block = javascript[
            render_start:render_end
        ]

        self.assertIn(
            'document.getElementById(\n        "profileRadios"',
            block
        )

        self.assertIn(
            'data-profile-band="${escapeHtml(band)}"',
            block
        )

        self.assertLess(
            block.index("radiosContainer.innerHTML"),
            block.index("radiosContainer.querySelector")
        )
