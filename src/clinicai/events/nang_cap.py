"""Nâng cấp sự kiện khi đọc (upcasting) — xem `docs/CHUAN-CAM-LEGO.md` mục 2.

Sổ sự kiện CHỈ THÊM: một sự kiện đã ghi không bao giờ bị sửa lại (trigger chặn).
Nên khi hình payload phải đổi (đổi tên, đổi kiểu, bỏ trường), ta KHÔNG sửa sổ mà
nâng bản cũ lên bản mới LÚC ĐỌC, trước khi đưa cho bên nhận. Nhờ vậy bên nhận chỉ
phải hiểu MỘT phiên bản — bản hiện hành trong `catalogue.py`.

QUY TRÌNH:
  1. Thêm trường tuỳ chọn (có mặc định)  → KHÔNG tăng version.
  2. Đổi tên / đổi kiểu / bỏ trường       → tăng `version` trong catalogue VÀ viết
     một hàm `vN → vN+1` ở đây bằng `@nang_cap("ten.su_kien", tu=N)`.
  3. Đổi hẳn NGHĨA (sự thật khác)         → đặt TÊN sự kiện mới, không tăng version.

CI (`test_nang_cap_su_kien.py`) đỏ nếu chuỗi hàm từ version 1 tới version hiện
hành bị hở. Mẫu chuẩn: "upcasting" (Greg Young, *Versioning in an Event Sourced
System*); ở đây áp cho outbox, không phải event sourcing toàn phần.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from clinicai.events.catalogue import DANH_MUC

HamNangCap = Callable[[dict[str, Any]], dict[str, Any]]

#: (tên sự kiện, version NGUỒN) → hàm nâng lên version + 1.
NANG_CAP: dict[tuple[str, int], HamNangCap] = {}


def nang_cap(ten: str, *, tu: int) -> Callable[[HamNangCap], HamNangCap]:
    """Khai hàm nâng `ten` từ version `tu` lên `tu + 1`."""

    def _khai(ham: HamNangCap) -> HamNangCap:
        khoa = (ten, tu)
        if khoa in NANG_CAP:
            raise ValueError(f"Đã có hàm nâng cấp {ten} v{tu} → v{tu + 1}.")
        NANG_CAP[khoa] = ham
        return ham

    return _khai


def version_hien_hanh(ten: str) -> int:
    su_kien = DANH_MUC.get(ten)
    return su_kien.version if su_kien is not None else 1


def len_ban_hien_hanh(
    ten: str, version: int, payload: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    """Nâng payload của một sự kiện đã ghi lên version hiện hành.

    Sự kiện MỚI HƠN code đang chạy (deploy lùi) thì từ chối — đưa bản không hiểu
    cho bên nhận là cách chắc chắn để ghi sai. Người đưa tin sẽ RETRY rồi DEAD, và
    hiện ở `v_event_delivery_suc_khoe`.
    """
    dich = version_hien_hanh(ten)
    if version > dich:
        raise ValueError(
            f"Sự kiện {ten} v{version} mới hơn code đang chạy (v{dich}) — "
            "code cũ hơn sổ, không đọc được."
        )
    ban = dict(payload)
    while version < dich:
        ham = NANG_CAP.get((ten, version))
        if ham is None:
            raise LookupError(
                f"Thiếu hàm nâng cấp {ten} v{version} → v{version + 1} "
                "(events/nang_cap.py)."
            )
        ban = ham(ban)
        version += 1
    return version, ban


__all__ = ["NANG_CAP", "len_ban_hien_hanh", "nang_cap", "version_hien_hanh"]
