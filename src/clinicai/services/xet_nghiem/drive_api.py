"""Gọi Google Drive (chỉ đọc) bằng tài khoản dịch vụ — chặng 4 bàn XN đối tác.

Không thêm thư viện: ký JWT RS256 bằng `pyjwt[crypto]` (đã có) rồi đổi lấy token ở
`https://oauth2.googleapis.com/token` (grant `jwt-bearer`, claim iss/scope/aud/exp/iat,
exp ≤ 1 giờ — tài liệu Google "OAuth 2.0 for Server to Server Applications"); gọi Drive
REST v3 bằng `httpx` (đã có). Phạm vi duy nhất `drive.readonly`.

KHOÁ: đường dẫn tệp JSON đọc từ biến môi trường `GOOGLE_DRIVE_SA_FILE` lúc chạy. Không
viết cứng đường dẫn, không ghi nội dung khoá ra log, không bao giờ gọi từ trình duyệt.
Thiếu biến ⇒ `co_cau_hinh()` False ⇒ vòng quét im lặng bỏ qua (dev/CI không có Drive).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Final

import httpx
import jwt

PHAM_VI: Final = "https://www.googleapis.com/auth/drive.readonly"
CUA_TOKEN: Final = "https://oauth2.googleapis.com/token"
CUA_DRIVE: Final = "https://www.googleapis.com/drive/v3/files"
BIEN_KHOA: Final = "GOOGLE_DRIVE_SA_FILE"
#: Trần một tệp chép về (PDF/ảnh kết quả — vài MB). Quá ⇒ hàng ghép tay (LOI_TEP).
TRAN_BYTE: Final = 30 * 1024 * 1024
#: Trần số trang một thư mục một lượt (mỗi trang 100) — chặn vòng vô hạn.
TRAN_TRANG: Final = 20
_TRUONG: Final = (
    "nextPageToken,files(id,name,mimeType,md5Checksum,size,createdTime,"
    "lastModifyingUser(displayName),owners(displayName))"
)


class DriveError(Exception):
    """Drive/token lỗi — câu ngắn, không chứa khoá hay token."""


@dataclass(frozen=True)
class TepDrive:
    file_id: str
    ten: str
    mime: str | None
    md5: str | None
    so_byte: int | None
    tao_luc: str | None
    nguoi_tai: str | None


def co_cau_hinh() -> bool:
    duong = os.environ.get(BIEN_KHOA, "").strip()
    return bool(duong) and os.path.isfile(duong)


def _doc_khoa() -> dict[str, Any]:
    duong = os.environ.get(BIEN_KHOA, "").strip()
    try:
        with open(duong, encoding="utf-8") as f:
            k = json.load(f)
    except (OSError, ValueError) as e:
        raise DriveError("Không đọc được tệp khoá Drive (kiểm biến môi trường).") from e
    if not isinstance(k, dict) or not k.get("client_email") or not k.get("private_key"):
        raise DriveError("Tệp khoá Drive thiếu client_email / private_key.")
    return k


_token: dict[str, Any] = {"gia_tri": None, "het": 0.0}


async def _lay_token(kh: httpx.AsyncClient) -> str:
    """Token còn hạn > 2 phút thì dùng lại; không thì xin mới."""
    if _token["gia_tri"] and _token["het"] - time.time() > 120:
        return str(_token["gia_tri"])
    k = _doc_khoa()
    bay_gio = int(time.time())
    claim = {
        "iss": k["client_email"],
        "scope": PHAM_VI,
        "aud": CUA_TOKEN,
        "iat": bay_gio,
        "exp": bay_gio + 3600,
    }
    assertion = jwt.encode(claim, k["private_key"], algorithm="RS256")
    r = await kh.post(
        CUA_TOKEN,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
    )
    if r.status_code != 200:
        raise DriveError(f"Google từ chối cấp token (HTTP {r.status_code}).")
    d = r.json()
    if not d.get("access_token"):
        raise DriveError("Google trả token rỗng.")
    _token["gia_tri"] = d["access_token"]
    _token["het"] = bay_gio + int(d.get("expires_in") or 3600)
    return str(d["access_token"])


def thanh_tep(f: dict[str, Any]) -> TepDrive:
    """Một mục `files[]` của Drive → `TepDrive`. Thiếu/rác trường ⇒ None, không ném."""
    nguoi = (f.get("lastModifyingUser") or {}).get("displayName") or next(
        (o.get("displayName") for o in f.get("owners") or [] if o.get("displayName")),
        None,
    )
    try:
        so_byte = int(f["size"]) if f.get("size") is not None else None
    except (TypeError, ValueError):
        so_byte = None
    return TepDrive(
        file_id=str(f.get("id") or ""),
        ten=str(f.get("name") or "")[:300],
        mime=f.get("mimeType"),
        md5=f.get("md5Checksum"),
        so_byte=so_byte,
        tao_luc=f.get("createdTime"),
        nguoi_tai=(str(nguoi)[:200] if nguoi else None),
    )


async def liet_ke(kh: httpx.AsyncClient, thu_muc: str) -> list[TepDrive]:
    """Tệp (không phải thư mục, chưa vào thùng rác) nằm trực tiếp trong `thu_muc`."""
    tk = await _lay_token(kh)
    q = (
        f"'{thu_muc}' in parents and trashed = false"
        " and mimeType != 'application/vnd.google-apps.folder'"
    )
    ra: list[TepDrive] = []
    trang: str | None = None
    for _ in range(TRAN_TRANG):
        tham: dict[str, Any] = {"q": q, "fields": _TRUONG, "pageSize": 100}
        if trang:
            tham["pageToken"] = trang
        r = await kh.get(
            CUA_DRIVE, params=tham, headers={"Authorization": f"Bearer {tk}"}
        )
        if r.status_code != 200:
            raise DriveError(f"Drive không liệt kê được thư mục ({r.status_code}).")
        d = r.json()
        ra.extend(thanh_tep(f) for f in d.get("files") or [])
        trang = d.get("nextPageToken")
        if not trang:
            break
    return ra


async def tai_ve(kh: httpx.AsyncClient, file_id: str) -> bytes:
    """Nội dung một tệp (`alt=media`), chặn ở `TRAN_BYTE`."""
    tk = await _lay_token(kh)
    async with kh.stream(
        "GET",
        f"{CUA_DRIVE}/{file_id}",
        params={"alt": "media"},
        headers={"Authorization": f"Bearer {tk}"},
    ) as r:
        if r.status_code != 200:
            raise DriveError(f"Drive không cho tải tệp (HTTP {r.status_code}).")
        phan: list[bytes] = []
        tong = 0
        async for p in r.aiter_bytes():
            tong += len(p)
            if tong > TRAN_BYTE:
                raise DriveError("Tệp trên Drive quá lớn.")
            phan.append(p)
    return b"".join(phan)
