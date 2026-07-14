"""User-scoped DPAPI encryption for locally persisted secrets (Windows only).

Used by the file-based clipboard hold: clipboard text can be sensitive, and
the hold file lives under ``%APPDATA%`` where backups and profile sync would
otherwise persist it in plaintext.  ctypes-only on purpose — the base CLI
install must not depend on pywin32 (daemon extra only).

DPAPI (``CryptProtectData`` / ``CryptUnprotectData``) is user-scoped: blobs
can only be decrypted by the same Windows account on the same machine, which
is exactly the boundary the hold file needs.
"""

from __future__ import annotations

import sys
from typing import Any

__all__ = ["protect", "unprotect"]

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

    _CRYPTPROTECT_UI_FORBIDDEN = 0x01  # never pop a UI prompt from a CLI

    class _DataBlob(ctypes.Structure):
        _fields_ = (
            ("cbData", ctypes.wintypes.DWORD),
            ("pbData", ctypes.c_void_p),
        )

    _libs: tuple[Any, Any] | None = None

    def _load_libs() -> tuple[Any, Any]:
        """Load crypt32/kernel32 with prototypes declared once."""
        global _libs
        if _libs is not None:
            return _libs

        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        blob_p = ctypes.POINTER(_DataBlob)
        for fn in (crypt32.CryptProtectData, crypt32.CryptUnprotectData):
            fn.argtypes = [
                blob_p,  # pDataIn
                ctypes.c_void_p,  # szDataDescr / ppszDataDescr (unused)
                ctypes.c_void_p,  # pOptionalEntropy
                ctypes.c_void_p,  # pvReserved
                ctypes.c_void_p,  # pPromptStruct
                ctypes.c_ulong,  # dwFlags
                blob_p,  # pDataOut
            ]
            fn.restype = ctypes.wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p

        _libs = (crypt32, kernel32)
        return _libs

    def _crypt_call(fn_name: str, data: bytes) -> bytes:
        crypt32, kernel32 = _load_libs()
        # min size 1: create_string_buffer rejects 0, and cbData=0 still needs
        # a valid pointer.
        buf = ctypes.create_string_buffer(data, len(data) or 1)
        blob_in = _DataBlob(len(data), ctypes.cast(buf, ctypes.c_void_p))
        blob_out = _DataBlob()
        ok = getattr(crypt32, fn_name)(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(blob_out),
        )
        if not ok:
            raise RuntimeError(f"{fn_name} failed (error {ctypes.get_last_error()})")
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)

    def protect(data: bytes) -> bytes:
        """Encrypt *data* for the current Windows user.

        Raises:
            RuntimeError: When DPAPI rejects the operation.
        """
        return _crypt_call("CryptProtectData", data)

    def unprotect(data: bytes) -> bytes:
        """Decrypt a :func:`protect` blob created by the same user/machine.

        Raises:
            RuntimeError: When the blob is corrupt or was encrypted by a
                different user or machine (DPAPI is user-scoped).
        """
        return _crypt_call("CryptUnprotectData", data)

else:  # pragma: no cover — DPAPI exists only on Windows

    def protect(data: bytes) -> bytes:  # noqa: ARG001 — cross-platform stub
        raise OSError("DPAPI is only available on Windows")

    def unprotect(data: bytes) -> bytes:  # noqa: ARG001 — cross-platform stub
        raise OSError("DPAPI is only available on Windows")
