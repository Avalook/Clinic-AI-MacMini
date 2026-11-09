"""Gọi Gmail (CHỈ ĐỌC) bằng OAuth refresh token của hộp thư phòng khám — Gmail G2.

Không thêm thư viện Google: đổi refresh token lấy access token ở
`https://oauth2.googleapis.com/token` (grant `refresh_token`), gọi Gmail REST v1 bằng
`httpx` như `drive_api.py`. Phạm vi cấp lúc G0 (`scripts/gmail-cap-quyen.py`) duy nhất
`gmail.readonly` — không gửi, xoá, sửa, gắn nhãn thư.

KHOÁ: đường dẫn tệp JSON (`client_id`, `client_secret`, `refresh_token`) đọc từ biến
`GOOGLE_GMAIL_OAUTH_FILE` lúc chạy (Docker secret `gmail_oauth`). Tệp rỗng giữ chỗ của
compose ⇒ `co_cau_hinh()` False ⇒ vòng quét im lặng bỏ qua (dev/CI; staging không bao
giờ trỏ hộp thư thật). Không ghi khoá, token, nội dung thư ra log; lỗi là câu ngắn có
mã lý do của Google.
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parseaddr
from typing import Any, Final

import httpx

CUA_TOKEN: Final = "https://oauth2.googleapis.com/token"
CUA_GMAIL: Final = "https://gmail.googleapis.com/gmail/v1/users/me"
BIEN_KHOA: Final = "GOOGLE_GMAIL_OAUTH_FILE"
#: Trần một PDF / cả thư (kết quả vài trăm KB; báo cáo G0 lớn nhất vài MB). Một PDF
#: lúc tải chiếm ~3–4 lần (chuỗi base64 + bytes) trong `drive-xn` mem_limit 160m ⇒
#: quá trần thì BỎ THƯ ĐÓ (`ThuBoQua`), không làm tiến trình chết vì hết bộ nhớ.
TRAN_BYTE: Final = 10 * 1024 * 1024
TRAN_THU: Final = 20 * 1024 * 1024
#: Khớp CHECK của `drive_tep` (G1) — dài hơn thì CHECK từ chối và mất thư.
TRAN_TIEU_DE: Final = 500
TRAN_THAN: Final = 2000
TRAN_TEN: Final = 300
_ID_THU_RE: Final = re.compile(r"^[A-Za-z0-9_-]{6,64}$")


class GmailError(Exception):
    """Gmail/token/mạng lỗi TẠM — lượt sau thử lại. Câu ngắn, không chứa khoá, token
    hay nội dung thư; `ma_http` để phân biệt (vd 400 = con trỏ trang hỏng)."""

    def __init__(self, cau: str, ma_http: int | None = None) -> None:
        super().__init__(cau)
        self.ma_http = ma_http


class ThuBoQua(Exception):  # noqa: N818 — tên nghiệp vụ, không phải lỗi hệ thống
    """Lỗi VĨNH VIỄN của riêng một thư (quá trần, không dữ liệu) — bỏ thư đó, không
    được chặn các thư khác của đối tác."""


@dataclass(frozen=True)
class PhanPdf:
    part_id: str
    ten: str
    so_byte: int
    attachment_id: str | None
    du_lieu: str | None  # base64url khi Gmail nhúng thẳng (tệp rất nhỏ)


@dataclass(frozen=True)
class ThuGmail:
    id: str
    nhan_luc: datetime
    tu: str  # địa chỉ người gửi (header From), chữ thường
    tieu_de: str
    than: str
    pdf: list[PhanPdf] = field(default_factory=list)
    #: Header `Authentication-Results` (Gmail ghi DKIM/SPF/DMARC) — G3 chỉ TỰ ghép thư
    #: có xác thực đúng miền người gửi (`gmail_doc.xac_thuc_ok`).
    xac_thuc: str = ""


def co_cau_hinh() -> bool:
    """Có khoá thật? Tệp rỗng (`docker/khong-co-khoa-gmail`) ⇒ False. Không đọc khoá."""
    duong = os.environ.get(BIEN_KHOA, "").strip()
    try:
        return bool(duong) and os.path.getsize(duong) > 0
    except OSError:
        return False


def _doc_khoa() -> dict[str, str]:
    duong = os.environ.get(BIEN_KHOA, "").strip()
    try:
        with open(duong, encoding="utf-8") as f:
            k = json.load(f)
    except (OSError, ValueError) as e:
        raise GmailError("Không đọc được tệp khoá Gmail (kiểm biến môi trường).") from e
    can = ("client_id", "client_secret", "refresh_token")
    if not isinstance(k, dict) or not all(k.get(c) for c in can):
        raise GmailError("Tệp khoá Gmail thiếu client_id/client_secret/refresh_token.")
    return {c: str(k[c]) for c in can}


def _ly_do(r: httpx.Response) -> str:
    """Mã lý do Google (rateLimitExceeded, invalid_grant…) — không có dữ liệu thư."""
    try:
        d = r.json()
    except ValueError:
        return "?"
    loi = d.get("error") if isinstance(d, dict) else None
    if isinstance(loi, str):
        return loi[:80]
    if isinstance(loi, dict):
        ct = loi.get("errors") or [{}]
        return str(ct[0].get("reason") or loi.get("status") or "?")[:80]
    return "?"


_token: dict[str, Any] = {"gia_tri": None, "het": 0.0}


async def _lay_token(kh: httpx.AsyncClient, *, moi: bool = False) -> str:
    """Token còn hạn > 2 phút thì dùng lại (sống ~1 giờ); `moi` ⇒ xin lại ngay."""
    if not moi and _token["gia_tri"] and _token["het"] - time.time() > 120:
        return str(_token["gia_tri"])
    k = _doc_khoa()
    r = await kh.post(CUA_TOKEN, data={**k, "grant_type": "refresh_token"})
    if r.status_code != 200:
        if _ly_do(r) == "invalid_grant":
            # Quyền bị thu hồi / token quá hạn — người phải cấp lại (G0).
            raise GmailError("Mất quyền đọc Gmail — cấp lại quyền.")
        raise GmailError(f"Google từ chối cấp token (HTTP {r.status_code}).")
    d = r.json()
    if not d.get("access_token"):
        raise GmailError("Google trả token rỗng.")
    _token["gia_tri"] = d["access_token"]
    _token["het"] = time.time() + int(d.get("expires_in") or 3600)
    return str(d["access_token"])


async def _goi(
    kh: httpx.AsyncClient, duong: str, tham: dict[str, Any]
) -> dict[str, Any]:
    """GET một cửa Gmail. 401 ⇒ xin token mới một lần. 429/5xx/403 giới hạn ⇒ ném
    `GmailError` — lượt sau thử lại; thư chưa lưu xong không có dòng nào."""
    for lan in range(2):
        tk = await _lay_token(kh, moi=lan > 0)
        r = await kh.get(
            f"{CUA_GMAIL}/{duong}",
            params=tham,
            headers={"Authorization": f"Bearer {tk}"},
        )
        if r.status_code == 401 and lan == 0:
            continue
        if r.status_code != 200:
            raise GmailError(
                f"Gmail lỗi HTTP {r.status_code} ({_ly_do(r)}).", r.status_code
            )
        try:
            d = r.json()
        except ValueError as e:  # Google trả thân hỏng — tạm, lượt sau thử lại
            raise GmailError("Gmail trả dữ liệu hỏng.") from e
        return d if isinstance(d, dict) else {}
    raise GmailError("Gmail từ chối token sau khi làm mới.")


async def liet_ke(
    kh: httpx.AsyncClient, q: str, trang: str | None = None, so: int = 100
) -> tuple[list[str], str | None, int]:
    """Một trang id thư khớp `q`, MỚI TRƯỚC, gồm cả Thùng rác (nhân viên đang xoá thư
    kết quả). Trả (id, token trang sau | None, ước lượng tổng của Gmail)."""
    tham: dict[str, Any] = {"q": q, "maxResults": so, "includeSpamTrash": "true"}
    if trang:
        tham["pageToken"] = trang
    d = await _goi(kh, "messages", tham)
    ids = [str(m["id"]) for m in d.get("messages") or [] if m.get("id")]
    try:
        uoc = int(d.get("resultSizeEstimate") or 0)
    except (TypeError, ValueError):
        uoc = 0
    return ids, (str(d["nextPageToken"]) if d.get("nextPageToken") else None), uoc


def _b64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _cac_phan(p: dict[str, Any]) -> list[dict[str, Any]]:
    ra = [p]
    for con in p.get("parts") or []:
        if isinstance(con, dict):
            ra += _cac_phan(con)
    return ra


def _than(phan: list[dict[str, Any]]) -> str:
    """Thân thư dạng chữ: ưu tiên text/plain, không có thì text/html bỏ thẻ."""
    for kieu in ("text/plain", "text/html"):
        for p in phan:
            than = p.get("body")
            du_lieu = than.get("data") if isinstance(than, dict) else None
            if p.get("mimeType") == kieu and du_lieu and not p.get("filename"):
                try:
                    chu = _b64(str(du_lieu)).decode("utf-8", "replace")
                except (ValueError, TypeError):
                    continue
                if kieu == "text/html":
                    chu = html.unescape(re.sub(r"<[^>]+>", " ", chu))
                return " ".join(chu.split())[:TRAN_THAN]
    return ""


def _phan_pdf(p: dict[str, Any], goc: bool = False) -> PhanPdf | None:
    """`goc`: phần gốc của thư — Gmail để partId "" khi cả thư CHỈ là một PDF."""
    ten = str(p.get("filename") or "")
    than_tho = p.get("body")
    than: dict[str, Any] = than_tho if isinstance(than_tho, dict) else {}
    la_pdf = ten.lower().endswith(".pdf") or p.get("mimeType") == "application/pdf"
    part_id = str(p.get("partId") or ("goc" if goc else ""))
    if not ten or not la_pdf or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", part_id):
        return None
    try:
        co = int(than.get("size") or 0)
    except (TypeError, ValueError):
        co = 0
    return PhanPdf(
        part_id=part_id,
        ten=ten[:TRAN_TEN],
        so_byte=co,
        attachment_id=than.get("attachmentId"),
        du_lieu=than.get("data"),
    )


def thanh_thu(r: object) -> ThuGmail | None:
    """HÀM THUẦN: một thư `format=full` của Gmail → `ThuGmail`. Thiếu id / rác ⇒ None;
    trường lẻ hỏng ⇒ giá trị rỗng, không ném. Chỉ giữ phần PDF (tên .pdf / mime PDF)."""
    # id thư đi vào đường dẫn ổ + URL + file_id (CHECK G1) ⇒ lạ thì bỏ thư.
    if not isinstance(r, dict) or not _ID_THU_RE.fullmatch(str(r.get("id") or "")):
        return None
    tai_tho = r.get("payload")
    tai: dict[str, Any] = tai_tho if isinstance(tai_tho, dict) else {}
    dau = {
        str(h.get("name", "")).lower(): str(h.get("value", ""))
        for h in tai.get("headers") or []
        if isinstance(h, dict)
    }
    try:
        nhan = datetime.fromtimestamp(int(r.get("internalDate") or 0) / 1000, UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        nhan = datetime.fromtimestamp(0, UTC)
    phan = _cac_phan(tai)
    return ThuGmail(
        id=str(r["id"]),
        nhan_luc=nhan,
        tu=parseaddr(dau.get("from", ""))[1].strip().lower(),
        tieu_de=" ".join(dau.get("subject", "").split())[:TRAN_TIEU_DE],
        than=_than(phan),
        pdf=[x for p in phan if (x := _phan_pdf(p, p is tai)) is not None],
        # Có thể nhiều dòng (ARC thêm dòng) — gộp hết, `xac_thuc_ok` tìm trong đó.
        xac_thuc="\n".join(
            str(h.get("value", ""))
            for h in tai.get("headers") or []
            if isinstance(h, dict)
            and str(h.get("name", "")).lower() == "authentication-results"
        )[:4000],
    )


async def doc_thu(kh: httpx.AsyncClient, mid: str) -> ThuGmail | None:
    return thanh_thu(await _goi(kh, f"messages/{mid}", {"format": "full"}))


async def tai_phan(kh: httpx.AsyncClient, mid: str, p: PhanPdf) -> bytes:
    """Byte một PDF đính kèm; chặn `TRAN_BYTE`. `attachmentId` không cố định giữa các
    lần đọc ⇒ chỉ dùng ngay sau `doc_thu`, không lưu."""
    if p.so_byte > TRAN_BYTE:
        raise ThuBoQua("tep_qua_lon")
    if p.du_lieu:
        tho = p.du_lieu
    elif p.attachment_id:
        # Lỗi mạng / JSON hỏng tạm của Google ⇒ GmailError (lượt sau thử lại) — KHÔNG
        # được bọc chung với base64 hỏng, không thì thư bị bỏ vĩnh viễn vì lỗi tạm.
        d = await _goi(kh, f"messages/{mid}/attachments/{p.attachment_id}", {})
        tho = str(d.get("data") or "")
    else:
        raise ThuBoQua("khong_du_lieu")
    try:
        data = _b64(tho)
    except (ValueError, TypeError) as e:  # base64 hỏng — vĩnh viễn
        raise ThuBoQua("du_lieu_hong") from e
    if len(data) > TRAN_BYTE:
        raise ThuBoQua("tep_qua_lon")
    return data
