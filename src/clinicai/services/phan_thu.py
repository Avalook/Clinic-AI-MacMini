"""MỘT LẦN THU = NHIỀU PHẦN THEO HÌNH THỨC (Tuyền 01/10/2026).

"Khách chuyển khoản 200k mà đưa tiền mặt 500k cũng ghi được. Bỏ nút QR đi,
chuyển khoản với QR là một."

* Hình thức chỉ còn HAI: Tiền mặt (``CASH``) và Chuyển khoản (``TRANSFER``).
  ``QR`` cũ vẫn được NHẬN (client cũ không gãy) và ĐỌC RA là Chuyển khoản.
* Một lần thu có 1–2 phần, mỗi hình thức tối đa một phần. TỔNG CÁC PHẦN = SỐ
  CẦN THU — máy chủ kiểm ở đây (câu dễ hiểu), Postgres ép lần cuối (trigger
  ``payment_cycle_phan_kiem_tong``, mig 20261002300000).
* Khách đưa tiền mặt DƯ: ``khach_dua`` ≥ phần tiền mặt, chỉ để in "trả lại
  khách"; sổ ghi đúng số thu.
* Lần thu có phần chuyển khoản là lần thu chuyển khoản (``hinh_thuc_chinh``)
  — nó quyết "chờ xác minh" như trước (contract A2).

Hàm thuần — test không cần DB: ``tests/unit/test_phan_thu.py``.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from clinicai.api.exceptions import ValidationError

TIEN_MAT = "CASH"
CHUYEN_KHOAN = "TRANSFER"
#: Hình thức thu còn dùng — thứ tự hiển thị (tiền mặt trước).
HINH_THUC_THU: tuple[str, ...] = (TIEN_MAT, CHUYEN_KHOAN)
#: Tên hiển thị; QR cũ = Chuyển khoản (gộp 01/10/2026).
TEN_HINH_THUC: dict[str, str] = {
    TIEN_MAT: "Tiền mặt",
    CHUYEN_KHOAN: "Chuyển khoản",
    "QR": "Chuyển khoản",
}
#: Tối đa bao nhiêu phần một lần thu (= số hình thức).
SO_PHAN_TOI_DA = len(HINH_THUC_THU)


@dataclass(frozen=True)
class PhanThu:
    hinh_thuc: str
    so_tien: int
    khach_dua: int | None = None

    def ra_dict(self) -> dict[str, Any]:
        return {
            "hinh_thuc": self.hinh_thuc,
            "so_tien": self.so_tien,
            "khach_dua": self.khach_dua,
        }


def chuan_hinh_thuc(v: object) -> str | None:
    """``CASH`` → ``CASH``; ``TRANSFER`` / ``QR`` → ``TRANSFER``; rác → None."""
    s = v.strip().upper() if isinstance(v, str) else ""
    if s == TIEN_MAT:
        return TIEN_MAT
    if s in (CHUYEN_KHOAN, "QR"):
        return CHUYEN_KHOAN
    return None


def _so_duong(raw: object) -> int | None:
    """Số hữu hạn > 0 làm tròn về đồng; bool / chuỗi / rác → None."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)) and math.isfinite(raw):
        n = round(raw)
        return n if n > 0 else None
    return None


def doc_phan(raw: object) -> list[PhanThu] | None:
    """Đọc ``phan`` trình duyệt gửi. ``None`` = không gửi (một hình thức, cũ).

    Hình dạng sai → 422 với câu nói rõ chỗ sai (không đoán, không bỏ qua).
    """
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValidationError("Phần thu phải là danh sách 1–2 hình thức.")
    if len(raw) > SO_PHAN_TOI_DA:
        raise ValidationError("Mỗi lần thu tối đa 2 phần: Tiền mặt và Chuyển khoản.")
    ra: list[PhanThu] = []
    da_co: set[str] = set()
    for p in raw:
        if not isinstance(p, Mapping):
            raise ValidationError("Phần thu không đúng dạng.")
        ht = chuan_hinh_thuc(p.get("hinh_thuc"))
        if ht is None:
            raise ValidationError(
                f"Hình thức thu không hợp lệ: {p.get('hinh_thuc')!r}"
                " (chỉ Tiền mặt hoặc Chuyển khoản)."
            )
        if ht in da_co:
            raise ValidationError(
                f"{TEN_HINH_THUC[ht]} ghi hai lần — mỗi hình thức một phần."
            )
        da_co.add(ht)
        so = _so_duong(p.get("so_tien"))
        if so is None:
            raise ValidationError(
                f"Số tiền {TEN_HINH_THUC[ht].lower()} phải là số lớn hơn 0."
            )
        dua_raw = p.get("khach_dua")
        dua: int | None = None
        if dua_raw is not None and ht == TIEN_MAT:
            dua = _so_duong(dua_raw)
            if dua is None or dua < so:
                raise ValidationError(
                    "Tiền khách đưa phải từ số tiền mặt cần thu trở lên."
                )
            if dua == so:
                dua = None
        ra.append(PhanThu(ht, so, dua))
    ra.sort(key=lambda x: HINH_THUC_THU.index(x.hinh_thuc))
    return ra


def ap_phan(phan: Sequence[PhanThu] | None, method: str, tong: int) -> list[PhanThu]:
    """Các phần SẼ GHI cho lần thu ``tong`` đồng (số máy chủ tính).

    Không gửi phần → một phần: (hình thức ``method``, ``tong``). Có gửi → tổng
    phải đúng ``tong``; lệch → 422 nói rõ hai con số.
    """
    if not phan:
        ht = chuan_hinh_thuc(method)
        if ht is None:
            raise ValidationError(f"Phương thức thanh toán không hợp lệ: {method!r}")
        return [PhanThu(ht, int(tong))]
    cong = sum(p.so_tien for p in phan)
    if cong != tong:
        raise ValidationError(
            f"Tổng các phần ({cong:,}đ) khác số cần thu ({tong:,}đ) — "
            "sửa số tiền từng hình thức cho khớp."
        )
    return list(phan)


def hinh_thuc_chinh(phan: Iterable[PhanThu]) -> str:
    """Có phần chuyển khoản → lần thu là chuyển khoản (chờ xác minh)."""
    return CHUYEN_KHOAN if any(p.hinh_thuc == CHUYEN_KHOAN for p in phan) else TIEN_MAT


def doc_phan_db(raw: object) -> list[dict[str, Any]]:
    """jsonb ``phan_thu_hieu_luc`` (chuỗi hoặc list) → list dict chuẩn. Rác → []."""
    if isinstance(raw, (str, bytes)):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    if not isinstance(raw, list):
        return []
    ra: list[dict[str, Any]] = []
    for p in raw:
        if not isinstance(p, Mapping):
            continue
        so = p.get("so_tien")
        try:
            so_i = int(so) if so is not None else 0
        except (TypeError, ValueError):
            so_i = 0
        dua = p.get("khach_dua")
        try:
            dua_i = int(dua) if dua is not None else None
        except (TypeError, ValueError):
            dua_i = None
        ra.append(
            {
                # NULL = phiếu cũ trước CP2 không biết hình thức — không đoán.
                "hinh_thuc": chuan_hinh_thuc(p.get("hinh_thuc")),
                "so_tien": so_i,
                "khach_dua": dua_i,
            }
        )
    return ra


def nhan_phan(phan: Sequence[Mapping[str, Any]]) -> str:
    """ "Tiền mặt" · "Tiền mặt 500.000đ + Chuyển khoản 200.000đ" · "" (không rõ)."""
    co = [p for p in phan if p.get("hinh_thuc")]
    if not co:
        return ""
    if len(co) == 1:
        return TEN_HINH_THUC[str(co[0]["hinh_thuc"])]
    return " + ".join(
        f"{TEN_HINH_THUC[str(p['hinh_thuc'])]} {int(p.get('so_tien') or 0):,}đ".replace(
            ",", "."
        )
        for p in co
    )


def tra_lai(phan: Sequence[Mapping[str, Any]]) -> int | None:
    """Tiền thừa trả khách (khách đưa − phần tiền mặt); không có → None."""
    for p in phan:
        if p.get("hinh_thuc") == TIEN_MAT and p.get("khach_dua") is not None:
            du = int(p["khach_dua"]) - int(p.get("so_tien") or 0)
            return du if du > 0 else None
    return None


def cac_hinh_thuc(phan: Iterable[Mapping[str, Any]]) -> list[str]:
    """Các hình thức có mặt (để lọc / hiển thị), theo thứ tự chuẩn."""
    co = {str(p["hinh_thuc"]) for p in phan if p.get("hinh_thuc")}
    return [h for h in HINH_THUC_THU if h in co]


def phan_mot_hinh_thuc(hinh_thuc: object, so_tien: object) -> list[dict[str, Any]]:
    """Một phần duy nhất (khoản hoàn, dữ liệu không qua hàm SQL)."""
    try:
        so = int(so_tien) if so_tien is not None else 0  # type: ignore[call-overload]
    except (TypeError, ValueError):
        so = 0
    return [{"hinh_thuc": chuan_hinh_thuc(hinh_thuc), "so_tien": so, "khach_dua": None}]
