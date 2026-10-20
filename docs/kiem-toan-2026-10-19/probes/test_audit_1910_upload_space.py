"""Audit: unknown upload length must not bypass the storage reserve."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.requests import Request

from clinicai.api.exceptions import ValidationError
from clinicai.services import media_service, nhan_tep_luong, tep_ket_qua_service

pytestmark = pytest.mark.asyncio


async def test_unknown_length_upload_respects_remaining_capacity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    free_bytes, reserve = 1024, 256
    pdf = b"%PDF-1.7\n" + b"x" * 2048
    body = (
        b'--audit\r\nContent-Disposition: form-data; name="file"; filename="audit.pdf"'
        b"\r\nContent-Type: application/pdf\r\n\r\n" + pdf + b"\r\n--audit--\r\n"
    )
    checked = 0

    def free() -> int:
        nonlocal checked
        checked += 1
        used = sum(p.stat().st_size for p in tmp_path.rglob("*.part"))
        return max(0, free_bytes - used)

    monkeypatch.setattr(media_service, "MEDIA_LOCAL_ROOT", tmp_path)
    monkeypatch.setattr(media_service, "MAX_BYTES_THEO_LOAI", {"PDF": 0})
    monkeypatch.setattr(nhan_tep_luong, "cho_trong_o_vps", free)
    monkeypatch.setattr(tep_ket_qua_service, "MEDIA_LOCAL_MIN_FREE_BYTES", reserve)
    sent = False

    async def receive() -> dict:
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/audit",
            "headers": [(b"content-type", b"multipart/form-data; boundary=audit")],
        },
        receive,
    )
    received = None
    try:
        try:
            _, received = await nhan_tep_luong.nhan_multipart(request)
        except ValidationError:
            return
        assert received.so_byte <= free_bytes - reserve, (
            f"Stored {received.so_byte} bytes with budget {free_bytes - reserve};"
            f" free-space checked only {checked} time(s)"
        )
    finally:
        if received:
            await nhan_tep_luong.don_tep_tam(received)
