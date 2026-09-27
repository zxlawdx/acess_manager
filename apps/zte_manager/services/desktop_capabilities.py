"""Desktop capabilities advertised by Python host, never browser User-Agent."""
from __future__ import annotations

import sys
from typing import TypedDict


class DesktopCapabilities(TypedDict):
    platform: str
    native_clipboard: bool
    web_clipboard_allowed: bool
    webview_transport: str


def get_desktop_capabilities(
    platform_name: str | None = None,
) -> DesktopCapabilities:
    platform = sys.platform if platform_name is None else platform_name
    native = platform == "win32"
    return {
        "platform": platform,
        "native_clipboard": native,
        # Browser code must STILL require isSecureContext and Clipboard API.
        "web_clipboard_allowed": not native,
        "webview_transport": "http",
    }
