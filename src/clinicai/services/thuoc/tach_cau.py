"""ĐỀ XUẤT cấu trúc từ câu cách dùng chữ của danh mục (để Tuyền / dược sĩ duyệt).

Cùng cách đọc với `tach_cach_dung` của trang giả lập 26/11. CHỈ là đề xuất: không
ghi gì — `scripts/de-xuat-cach-dung.py` in bảng, người duyệt khai ở Danh mục › Sửa.
Không chắc → kiểu "chu" (chỉ ghi chữ), không đoán.
"""

from __future__ import annotations

import re
from typing import Any

from clinicai.services.thuoc.cach_dung import CachDung

#: Liều không đếm theo đơn vị kho / dùng một lần / khi cần → chỉ giữ chữ (Tuyền 26/11).
_CHI_CHU = re.compile(
    r"bôi|xịt|nhát|thước|lớp mỏng|hạt đỗ|khi cần|theo chỉ định|một lần duy nhất"
    r"|liều duy nhất|1/2|1/3|tiêm"
)
_DV = r"(viên|gói|bơm|ống)"
_CHU_KY = re.compile(
    r"(?:từ )?ngày (?:thứ )?(\d+)\s*(?:đến|tới|-)\s*(?:ngày )?(\d+)\s*(?:của )?"
    r"(?:chu kỳ|ckk)"
)
_TRONG = re.compile(r"trong (\d+)(?:\s*-\s*\d+)? ngày|(\d+)(?:-\d+)? ngày liên")
_SO_LAN = re.compile(
    r"(ngày|tuần|tháng)\s*(?:uống|đặt|đặt âm đạo|dùng)?\s*(?:duy nhất\s*)?"
    r"(\d+)\s*(?:-\s*(\d+))?\s*lần"
)
#: "3 ngày uống 1 lần", "2 ngày uống 1 viên", "cách 3 ngày" → mỗi N ngày (N ≥ 2).
_MOI_N_NGAY = re.compile(
    r"(?:cách\s*0?(\d+)\s*ngày)"
    rf"|(?:\b0?(\d+)\s*ngày\s*(?:uống|đặt|dùng)?\s*(?:1|một)\s*(?:lần|{_DV[1:-1]}))"
)
_KY = {"ngày": "ngay", "tuần": "tuan", "tháng": "thang"}
_MOI_LAN = re.compile(
    rf"mỗi lần\s*(?:uống|đặt)?\s*(\d+(?:[.,]\d+)?)\s*(?:-\s*(\d+))?\s*{_DV}"
)
#: "Ngày uống 1 viên", "Tuần 03 viên", "Sáng 1 viên", "1 viên/ngày".
_GON = (
    re.compile(
        rf"(ngày|tuần|tháng)\s*(?:uống|đặt|đặt âm đạo)?\s*(?:duy nhất\s*)?0?(\d+)"
        rf"\s*(?:-\s*(\d+))?\s*{_DV}"
    ),
    re.compile(
        rf"()(?:sáng|uống|đặt)\s*0?(\d+)\s*(?:-\s*(\d+))?\s*{_DV}\s*"
        r"(?:/ngày|mỗi ngày|sau|vào)"
    ),
)


def _kieu_theo(kq: dict[str, Any], ky: str) -> None:
    if kq["kieu"] != "chu_ky":
        kq["kieu"] = _KY.get(ky, "ngay")


def _doc_moi_n_ngay(t: str, kq: dict[str, Any]) -> bool:
    """ "3 ngày uống 1 lần" / "cách 3 ngày" → kiểu mỗi N ngày. Trả True nếu đọc được."""
    m = _MOI_N_NGAY.search(t)
    n = int(m[1] or m[2]) if m else 0
    # "Cách ngày" = 2 ngày 1 lần, trừ câu đã đếm theo tuần ("tuần 3 viên, cách ngày").
    if not n and "cách ngày" in t and "tuần" not in t:
        n = 2
    if n < 2 or kq["kieu"] == "chu_ky":
        return False
    kq.update(kieu="cach_ngay", moi_n_ngay=n)
    return True


def _doc_so_lan(t: str, kq: dict[str, Any]) -> None:
    if m := _SO_LAN.search(t):
        _kieu_theo(kq, m[1])
        if m[3]:
            kq["khoang_so_lan"] = [int(m[2]), int(m[3])]
        else:
            kq["so_lan"] = int(m[2])


def _doc_moi_lan(t: str, kq: dict[str, Any]) -> None:
    if m := _MOI_LAN.search(t):
        kq["don_vi_lieu"] = m[3]
        if m[2]:
            kq["khoang_lan"] = [m[1], m[2]]
        else:
            kq["moi_lan"] = m[1].replace(",", ".")


def _doc_cau_gon(t: str, kq: dict[str, Any]) -> None:
    m = _GON[0].search(t) or _GON[1].search(t)
    if not m:
        return
    theo_ky = m[1] in ("tuần", "tháng")
    _kieu_theo(kq, m[1])
    kq["don_vi_lieu"] = m[4]
    if theo_ky:  # "Tuần 03 viên" = tuần 3 lần, mỗi lần 1 viên
        kq.update(so_lan=int(m[2]), moi_lan="1")
    elif m[3]:
        kq.update(so_lan=1, khoang_lan=[m[2], m[3]])
    else:
        kq.update(so_lan=1, moi_lan=m[2])


def _bu_mac_dinh(t: str, kq: dict[str, Any]) -> dict[str, Any]:
    co_lieu = kq.get("moi_lan") or kq.get("khoang_lan")
    co_lan = kq.get("so_lan") or kq.get("khoang_so_lan")
    if "cách ngày" in t and kq["kieu"] == "chu":
        return {**kq, "kieu": "cach_ngay", "moi_lan": kq.get("moi_lan") or "1"}
    if kq["kieu"] in ("ngay", "tuan", "thang") and not co_lan:
        return {"kieu": "chu"}
    if kq["kieu"] != "chu" and not co_lieu:
        kq["moi_lan"] = "1"
    if kq["kieu"] == "chu_ky" and not co_lan:
        kq["so_lan"] = 1
    return kq


def tach_cach_dung(cau: str | None) -> dict[str, Any]:
    t = " ".join((cau or "").lower().split())
    kq: dict[str, Any] = {"kieu": "chu"}
    if not t or _CHI_CHU.search(t):
        return kq
    if m := _CHU_KY.search(t):
        kq.update(kieu="chu_ky", tu_ngay=int(m[1]), den_ngay=int(m[2]))
    if m := _TRONG.search(t):
        kq["trong_ngay"] = int(m[1] or m[2])
    moi_n = _doc_moi_n_ngay(t, kq)
    if not moi_n:
        _doc_so_lan(t, kq)
    _doc_moi_lan(t, kq)
    if not moi_n and "so_lan" not in kq and "khoang_so_lan" not in kq:
        _doc_cau_gon(t, kq)
    elif (
        moi_n and "moi_lan" not in kq and (m := _GON[1].search(t) or _GON[0].search(t))
    ):
        kq.update(moi_lan=m[2], don_vi_lieu=m[4])
    return _bu_mac_dinh(t, kq)


def de_xuat_cach_dung(cau: str | None) -> CachDung:
    """Đề xuất đã kiểm hình; đọc ra cấu trúc vô lý thì trả "chỉ chữ"."""
    try:
        return CachDung.model_validate(tach_cach_dung(cau))
    except ValueError:  # pydantic.ValidationError là ValueError
        return CachDung(kieu="chu")


__all__ = ["de_xuat_cach_dung", "tach_cach_dung"]
