"""Khối SỔ NỢ HAI CHIỀU nghe mọi sự kiện làm đổi tiền nợ của lượt (14/10/2026).

Thu / huỷ phiếu / hoàn / về / mở lại lượt / ghi nợ / bỏ hay làm xong chỉ định /
giao thuốc / thêm vật tư → tính lại số dư "khách nợ phòng khám" và "phòng khám
nợ khách" của đúng lượt ấy rồi ghi phần chênh (`services/so_no_service.py`).

Đọc trạng thái HIỆN TẠI nên sự kiện tới trễ hay tới hai lần vẫn ra một kết quả;
một sự kiện chỉ ghi một lần mỗi chiều (chỉ mục duy nhất theo sự kiện). Phát lại
lịch sử thì im: số dư đọc bây giờ không phải số dư lúc ấy.

Không sửa nơi phát: thêm bên nghe ở danh mục sự kiện là đủ.
"""

from __future__ import annotations

from datetime import UTC, datetime

import asyncpg

from clinicai.events.catalogue import SO_NO
from clinicai.events.worker import SuKienDaNhan, dang_ky
from clinicai.services.so_no_service import LOAI_THEO_SU_KIEN, ghi_chenh_lech


async def ghi_so(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
    if su_kien.la_phat_lai:
        return
    visit_id = su_kien.payload.get("visit_id")
    if not visit_id:
        return
    luc = su_kien.occurred_at
    if not isinstance(luc, datetime):
        luc = datetime.now(UTC)
    await ghi_chenh_lech(
        conn,
        clinic_id=su_kien.clinic_id,
        visit_id=str(visit_id),
        loai=LOAI_THEO_SU_KIEN.get(su_kien.event_type, "DOI_CHIEU"),
        luc=luc,
        su_kien_id=su_kien.event_id,
        su_kien_ten=su_kien.event_type,
        boi=su_kien.actor_staff_id,
    )


dang_ky(SO_NO, ghi_so)

__all__ = ["ghi_so"]
