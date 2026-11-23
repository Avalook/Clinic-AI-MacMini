"""Công tắc + cấu hình liên thông đơn thuốc quốc gia — CHỈ từ biến môi trường.

Mặc định TẮT. Tắt thì worker không gọi gì của module này: không bảng nào được
ghi, không màn nào đổi (lời hứa của công tắc — test canh).

Bí mật (mật khẩu liên thông của cơ sở và của từng bác sĩ) nằm ở `.env.prod` trên
VPS như mọi bí mật khác; không bao giờ ở `clinic.settings` (anon key đọc được cột
ấy — xem `pos_config.py`). Lỗi cấu hình không bao giờ chép giá trị bí mật.

Danh sách biến + cách điền: docs/LIEN-THONG-DON-THUOC.md.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

#: Giả lập (staging / thử) hay hệ thống thật.
GIA_LAP = "gia_lap"
THAT = "that"
#: QĐ 808/QĐ-BYT mục III–VII.
URL_MAC_DINH = "https://api.donthuocquocgia.vn"
#: Bộ ký số đã có adapter. Thêm nhà cung cấp (VNPT SmartCA, Viettel MySign…) =
#: thêm adapter `KySoDonThuoc` + tên ở đây.
KY_SO_DA_CAI = frozenset({"khong"})

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
#: Mã cơ sở KCB 5 ký tự (QĐ 384/QĐ-BYT) — 5 ký tự đầu của mọi mã đơn.
_MA_CO_SO = re.compile(r"^[0-9A-Za-z]{5}$")
_MA_LIEN_THONG = re.compile(r"^[0-9A-Za-z._-]{3,40}$")
_BAT = {"1", "true", "yes", "on", "bat"}
_BIEN = (
    "DTQG_CLINIC_ID",
    "DTQG_LOCATION_ID",
    "DTQG_MA_CO_SO",
    "DTQG_MA_LIEN_THONG_CO_SO",
    "DTQG_GUI_TU",
    "DTQG_NHA_CUNG_CAP",
    "DTQG_URL",
    "DTQG_KY_SO",
    "DTQG_BAC_SI",
)


@dataclass(frozen=True)
class TaiKhoanBacSi:
    ma_lien_thong: str
    #: repr=False: một dòng log `%r` sau này không được in mật khẩu.
    mat_khau: str | None = field(repr=False)


@dataclass(frozen=True)
class CauHinh:
    clinic_id: str
    #: Cơ sở (`clinic_location`) được cấp mã — lượt ở cơ sở khác bỏ qua.
    location_id: str
    ma_co_so: str
    #: Chỉ gửi đơn của lượt đóng TỪ ngày này (giờ VN) — tránh tự gửi bù đơn cũ
    #: khi vừa bật. Gửi bù là quyết định nghiệp vụ, phải điền tay.
    gui_tu: date
    nha_cung_cap: str
    #: staff_id → tài khoản liên thông của bác sĩ.
    bac_si: dict[str, TaiKhoanBacSi] = field(default_factory=dict)
    ma_lien_thong_co_so: str | None = None
    url: str = URL_MAC_DINH
    #: Bộ ký số; "khong" = không ký (trường `signature` để rỗng — xem docs).
    ky_so: str = "khong"
    so_lan_thu: int = 6
    #: Soát lại đơn của lượt đã đóng trong chừng này ngày (bắt đính chính muộn).
    soat_ngay: int = 3


def da_bat(env: Mapping[str, str] | None = None) -> bool:
    """Công tắc chính. Chỉ đọc một biến — rẻ, gọi mỗi vòng được."""
    e = os.environ if env is None else env
    return e.get("DTQG_BAT", "").strip().lower() in _BAT


def _so_nguyen_env(
    e: Mapping[str, str], ten: str, mac_dinh: int, tu: int, den: int
) -> int | str:
    tho = e.get(ten, "").strip()
    if not tho:
        return mac_dinh
    if not tho.isdigit() or not tu <= int(tho) <= den:
        return f"{ten} phải là số {tu}–{den}"
    return int(tho)


def doc_bac_si(tho: str, *, can_mat_khau: bool) -> dict[str, TaiKhoanBacSi] | str:
    """`DTQG_BAC_SI` = JSON {staff_id: {"ma_lien_thong": …, "mat_khau": …}}.
    Trả bảng, hoặc câu lỗi (không chép giá trị)."""
    if not tho:
        return {}
    try:
        d = json.loads(tho)
    except ValueError:
        return "DTQG_BAC_SI không phải JSON hợp lệ"
    if not isinstance(d, dict):
        return "DTQG_BAC_SI phải là một object JSON"
    ra: dict[str, TaiKhoanBacSi] = {}
    for sid, tk in d.items():
        ma = tk.get("ma_lien_thong") if isinstance(tk, dict) else None
        mk = tk.get("mat_khau") if isinstance(tk, dict) else None
        if not _UUID.match(str(sid).lower()) or not isinstance(ma, str):
            return "DTQG_BAC_SI: khoá phải là staff_id (uuid), có ma_lien_thong"
        if not _MA_LIEN_THONG.match(ma):
            return "DTQG_BAC_SI: ma_lien_thong sai dạng"
        if can_mat_khau and not (isinstance(mk, str) and mk):
            return "DTQG_BAC_SI: thiếu mat_khau của một bác sĩ"
        ra[str(sid).lower()] = TaiKhoanBacSi(ma, mk if isinstance(mk, str) else None)
    return ra


def doc_cau_hinh_dtqg(env: Mapping[str, str] | None = None) -> CauHinh | list[str]:
    """HÀM THUẦN theo `env`: cấu hình hợp lệ, hoặc danh sách lỗi (câu tiếng Việt,
    không chứa giá trị bí mật). Không bao giờ ném."""
    e = os.environ if env is None else env
    g = {k: e.get(k, "").strip() for k in _BIEN}
    loi: list[str] = []
    for ten in ("DTQG_CLINIC_ID", "DTQG_LOCATION_ID"):
        if not _UUID.match(g[ten].lower()):
            loi.append(f"{ten} phải là uuid")
    if not _MA_CO_SO.match(g["DTQG_MA_CO_SO"]):
        loi.append("DTQG_MA_CO_SO phải là mã cơ sở KCB đúng 5 ký tự chữ/số")
    gui_tu: date | None = None
    try:
        gui_tu = date.fromisoformat(g["DTQG_GUI_TU"])
    except ValueError:
        loi.append("DTQG_GUI_TU phải là ngày yyyy-mm-dd")
    ncc = (g["DTQG_NHA_CUNG_CAP"] or GIA_LAP).lower()
    if ncc not in (GIA_LAP, THAT):
        loi.append("DTQG_NHA_CUNG_CAP phải là gia_lap hoặc that")
    url = g["DTQG_URL"] or URL_MAC_DINH
    if ncc == THAT:
        # Staging nạp lại bản sao prod mỗi đêm (đơn đã che + dòng CHO_GUI chép từ
        # prod): chép nhầm DTQG_* thật sang .env.staging không được gửi gì thật.
        if e.get("APP_ENV", "").strip().lower() != "production":
            loi.append("DTQG_NHA_CUNG_CAP=that chỉ dùng được khi APP_ENV=production")
        if not url.startswith("https://"):
            loi.append("DTQG_URL phải là https://…")
        if not _MA_LIEN_THONG.match(g["DTQG_MA_LIEN_THONG_CO_SO"]):
            loi.append("Thiếu / sai DTQG_MA_LIEN_THONG_CO_SO")
    if (g["DTQG_KY_SO"] or "khong").lower() not in KY_SO_DA_CAI:
        loi.append("DTQG_KY_SO: bộ ký số này chưa được cài — để trống (= khong)")
    bac_si = doc_bac_si(g["DTQG_BAC_SI"], can_mat_khau=ncc == THAT)
    so_lan = _so_nguyen_env(e, "DTQG_SO_LAN_THU", 6, 1, 20)
    soat = _so_nguyen_env(e, "DTQG_SOAT_NGAY", 3, 1, 30)
    loi += [x for x in (bac_si, so_lan, soat) if isinstance(x, str)]
    if (
        loi
        or gui_tu is None
        or isinstance(bac_si, str)
        or isinstance(so_lan, str)
        or isinstance(soat, str)
    ):
        return loi
    return CauHinh(
        clinic_id=g["DTQG_CLINIC_ID"].lower(),
        location_id=g["DTQG_LOCATION_ID"].lower(),
        ma_co_so=g["DTQG_MA_CO_SO"],
        gui_tu=gui_tu,
        nha_cung_cap=ncc,
        bac_si=bac_si,
        ma_lien_thong_co_so=g["DTQG_MA_LIEN_THONG_CO_SO"] or None,
        url=url.rstrip("/"),
        ky_so=(g["DTQG_KY_SO"] or "khong").lower(),
        so_lan_thu=so_lan,
        soat_ngay=soat,
    )


__all__ = [
    "GIA_LAP",
    "THAT",
    "URL_MAC_DINH",
    "CauHinh",
    "TaiKhoanBacSi",
    "da_bat",
    "doc_bac_si",
    "doc_cau_hinh_dtqg",
]
