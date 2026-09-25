"""Área de transferência nativa para o executável Windows.

O QtWebEngine pode falhar ao copiar via navigator.clipboard/execCommand.
O backend desktop usa a API Win32, sem WebEngine nem dependências adicionais.
"""

import ctypes
import sys
import time


def copy_text(text: str) -> dict:
    if sys.platform != "win32":
        raise RuntimeError(
            "Clipboard nativo disponível somente no executável Windows."
        )

    if not isinstance(text, str) or not text or len(text) > 100_000:
        raise ValueError(
            "O texto deve ter entre 1 e 100000 caracteres."
        )

    # Use c_void_p para não truncar ponteiros em processos de 64 bits.
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p

    data = text.encode("utf-16-le") + b"\x00\x00"
    GMEM_MOVEABLE = 0x0002
    CF_UNICODETEXT = 13

    # Outro processo pode estar lendo clipboard: pequenas tentativas.
    opened = False
    for _ in range(8):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.05)

    if not opened:
        raise RuntimeError("Clipboard ocupado por outro aplicativo.")

    handle = None
    try:
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            raise RuntimeError("Não foi possível alocar memória para o clipboard.")

        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            raise RuntimeError("Não foi possível acessar a memória do clipboard.")

        try:
            ctypes.memmove(pointer, data, len(data))
        finally:
            kernel32.GlobalUnlock(handle)

        if not user32.EmptyClipboard():
            raise RuntimeError("Não foi possível liberar o clipboard.")

        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            raise RuntimeError("Não foi possível copiar o texto no Windows.")

        # Agora o Windows é responsável por liberar a memória.
        handle = None
        return {"success": True}

    finally:
        if handle:
            kernel32.GlobalFree(handle)
        user32.CloseClipboard()
