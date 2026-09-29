"""Assemble the Access Manager Vela template from editable page modules.

Edit apps/zte_manager/templates/source/pages/*.html, NOT the generated index.html.
The generated artifact stays committed because Vela renders a static template and
legacy integration checks expect the public DOM IDs inside index.html.

Run: python tools/build_frontend_template.py
CI:  python tools/build_frontend_template.py --check
"""
from __future__ import annotations

import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT = PROJECT_ROOT / "apps" / "zte_manager" / "templates"
SOURCE = ROOT / "source"
TARGET = ROOT / "index.html"
PARTS = (
    "shell_start.html",
    "pages/connection.html",
    "pages/dashboard.html",
    "pages/wifi.html",
    "pages/wan.html",
    "pages/clients.html",
    "pages/supportDiagnostic.html",
    "pages/diagnostics.html",
    "pages/profiles.html",
    "pages/tr069.html",
    "pages/advanced.html",
    "pages/device.html",
    "pages/management.html",
    "shell_end.html"
)


def build_template() -> str:
    return "".join((SOURCE / filename).read_text(encoding="utf-8") for filename in PARTS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the modular Vela HTML.")
    parser.add_argument("--check", action="store_true", help="Verify committed index.html is current")
    args = parser.parse_args()
    generated = build_template()
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != generated:
            raise SystemExit("index.html is stale; run python tools/build_frontend_template.py")
        print(f"Modular template current: {len(PARTS)} sections")
        return
    TARGET.write_text(generated, encoding="utf-8")
    print(f"Generated {TARGET.relative_to(PROJECT_ROOT)} from {len(PARTS)} modules")


if __name__ == "__main__":
    main()
