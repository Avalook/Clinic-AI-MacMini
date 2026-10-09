"""Mẫu PHIẾU ĐIỀU TRỊ (Tuyền chốt 07/10/2026) — hằng số + luật "có kết quả" dùng
chung, không import gì của dự án (engine phiếu kết quả, khối 2 hồ sơ và bản in
cùng đọc; đặt ở `mau_goi_y` thì vòng import khung ↔ form_engine)."""

from __future__ import annotations

import json
from typing import Any

#: Mẫu kết quả "Phiếu điều trị": hai ô chữ "Cảm nhận", "Vấn đề sau điều trị".
MAU_PHIEU_DIEU_TRI = "PHIEU_DIEU_TRI"

#: Biểu mẫu KHÔNG có bước "Hoàn tất": Xong dịch vụ là mốc hoàn thành, mỗi lần
#: lưu là ghi nhận (lịch sử từng bản ở `form_instance_lich_su`); bản in không
#: ghi "BẢN NHÁP"; nội dung đọc được ngay cả khi chưa ai bấm chốt.
MAU_KHONG_HOAN_TAT = frozenset({f"KQ_{MAU_PHIEU_DIEU_TRI}"})


def _co_chu(du_lieu: Any) -> bool:
    d = json.loads(du_lieu) if isinstance(du_lieu, str) else du_lieu
    if not isinstance(d, dict):
        return False
    for o in d.values():
        g = o.get("gia_tri") if isinstance(o, dict) else None
        if isinstance(g, str) and g.strip():
            return True
    return False


def phieu_co_ket_qua(
    *, form_id: str | None, trang_thai: str | None, revision: Any, du_lieu: Any
) -> bool:
    """Phiếu kết quả này ĐÃ LÀ KẾT QUẢ chưa — MỘT luật cho mọi nơi đọc (thẻ chỉ
    định, "kết quả mới", đã xem, bản in) — hàm thuần, rác → False, không ném.

    * Phiếu đã Hoàn tất (READY) → có.
    * Mẫu không có bước Hoàn tất (phiếu điều trị, 09/10/2026): đã lưu (revision
      > 0) và có ít nhất một ô có chữ → có, như CLS đã hoàn tất. Nháp rỗng /
      chưa ai lưu → chưa.
    Bản SQL cùng luật: `phieu_co_ket_qua_sql`.
    """
    if trang_thai == "READY":
        return True
    if form_id not in MAU_KHONG_HOAN_TAT:
        return False
    try:
        da_luu = int(revision or 0) > 0
    except (TypeError, ValueError):
        return False
    try:
        return da_luu and _co_chu(du_lieu)
    except ValueError:
        return False


def phieu_co_ket_qua_sql(f: str = "f") -> str:
    """Điều kiện SQL của `phieu_co_ket_qua` trên `form_instance` bí danh ``f``."""
    ma = ", ".join(f"'{m}'" for m in sorted(MAU_KHONG_HOAN_TAT))
    return (
        f"({f}.trang_thai = 'READY' OR ({f}.form_id IN ({ma}) AND {f}.revision > 0"
        f" AND EXISTS (SELECT 1 FROM jsonb_each({f}.du_lieu) o_kq"
        "  WHERE jsonb_typeof(o_kq.value) = 'object'"
        "    AND jsonb_typeof(o_kq.value -> 'gia_tri') = 'string'"
        # Như `str.strip()`: chỉ dấu cách / xuống dòng / tab là chưa có chữ.
        "    AND regexp_replace(o_kq.value ->> 'gia_tri', '\\s', '', 'g') <> '')))"
    )


__all__ = [
    "MAU_KHONG_HOAN_TAT",
    "MAU_PHIEU_DIEU_TRI",
    "phieu_co_ket_qua",
    "phieu_co_ket_qua_sql",
]
