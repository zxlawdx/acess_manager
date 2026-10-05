"""Assemble the Access Manager Vela template from editable page modules.

Edit apps/zte_manager/templates/source/pages/**/*.html, NOT the generated
index.html. The generated artifact stays committed because Vela renders a
static template and legacy integration checks expect the public DOM IDs inside
index.html.

Run: python tools/build_frontend_template.py
CI:  python tools/build_frontend_template.py --check
"""
from __future__ import annotations

import argparse
import difflib
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
    "pages/advanced/workbench_discovery.html",
    "pages/advanced/network.html",
    "pages/advanced/huawei_security.html",
    "pages/advanced/inspector_close.html",
    "pages/device.html",
    "pages/management/fleet.html",
    "pages/management/remote_monitor.html",
    "pages/management/network_mesh.html",
    "pages/management/lifecycle_provisioning.html",
    "shell_end.html",
)

# The original monolithic pages used one visual blank line at these semantic
# boundaries. Preserve those bytes in composition instead of encoding a blank
# separator as ownership of either adjacent feature module.
PRESERVED_BLANK_BOUNDARIES = frozenset({
    "pages/advanced/workbench_discovery.html",
    "pages/advanced/network.html",
    "pages/advanced/huawei_security.html",
    "pages/management/fleet.html",
    "pages/management/remote_monitor.html",
    "pages/management/network_mesh.html",
    "pages/management/lifecycle_provisioning.html",
})


def build_template() -> str:
    chunks = []
    for filename in PARTS:
        chunks.append((SOURCE / filename).read_text(encoding="utf-8"))
        if filename in PRESERVED_BLANK_BOUNDARIES:
            chunks.append("\n")
    return "".join(chunks)


def mismatch_message(committed: str, generated: str) -> str:
    limit = min(len(committed), len(generated))
    index = next(
        (offset for offset in range(limit) if committed[offset] != generated[offset]),
        limit,
    )
    line = generated.count("\n", 0, index) + 1
    start = max(0, index - 45)
    end = index + 45

    committed_lines = committed.splitlines(keepends=True)
    generated_lines = generated.splitlines(keepends=True)
    matcher = difflib.SequenceMatcher(
        a=committed_lines,
        b=generated_lines,
        autojunk=False,
    )
    blocks = []
    for tag, a1, a2, b1, b2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        old = "".join(committed_lines[a1:a2])
        new = "".join(generated_lines[b1:b2])
        blocks.append(
            f"{tag}: committed L{a1 + 1}-{a2} -> generated L{b1 + 1}-{b2}\n"
            f"  committed={old[:260]!r}\n"
            f"  generated={new[:260]!r}"
        )
        if len(blocks) >= 12:
            break

    return (
        "index.html is stale; run python tools/build_frontend_template.py\n"
        f"first mismatch: char={index} line={line} "
        f"committed_len={len(committed)} generated_len={len(generated)}\n"
        f"committed={committed[start:end]!r}\n"
        f"generated={generated[start:end]!r}\n"
        + "\n".join(blocks)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the modular Vela HTML.")
    parser.add_argument("--check", action="store_true", help="Verify committed index.html is current")
    args = parser.parse_args()
    generated = build_template()
    if args.check:
        if not TARGET.exists():
            raise SystemExit("index.html is missing; run python tools/build_frontend_template.py")
        committed = TARGET.read_text(encoding="utf-8")
        if committed != generated:
            raise SystemExit(mismatch_message(committed, generated))
        print(f"Modular template current: {len(PARTS)} sections")
        return
    TARGET.write_text(generated, encoding="utf-8")
    print(f"Generated {TARGET.relative_to(PROJECT_ROOT)} from {len(PARTS)} modules")


if __name__ == "__main__":
    main()
