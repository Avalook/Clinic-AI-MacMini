"""Khối CÔNG NỢ nghe "đã thu tiền" (01/10/2026).

    payment.service_collected / payment.medicine_collected
        → lượt có khoản ghi nợ CHƯA THU mà nay HẾT NỢ (cùng luật `no_khi_ve`
          của check-out) → khoản ấy ĐÃ THU + phát `cong_no.da_thu`.

Thu một phần thì khoản ghi nợ còn nguyên — lượt chưa hết nợ. Đọc trạng thái
HIỆN TẠI nên sự kiện tới trễ hay tới hai lần vẫn ra một kết quả; khoá dòng
`FOR UPDATE` để hai lần thu cùng lúc chỉ đóng một lần. Phát lại thì im.

Không sửa code thu tiền: thu nợ đi đúng đường thu có sẵn ở quầy.
"""

from __future__ import annotations

import asyncpg

from clinicai.events.catalogue import CONG_NO, CongNoDaThu
from clinicai.events.emit import NguoiGayRa, emit_event
from clinicai.events.worker import SuKienDaNhan, dang_ky
from clinicai.services.cong_no_service import no_khi_ve


async def xet_da_thu(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
    if su_kien.la_phat_lai:
        return
    visit_id = su_kien.payload.get("visit_id")
    if not visit_id:
        return
    mo = await conn.fetchrow(
        """
        SELECT id::text AS id, so_tien FROM public.cong_no
         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
           AND trang_thai = 'CHUA_THU'
           FOR UPDATE
        """,
        su_kien.clinic_id,
        str(visit_id),
    )
    if mo is None:
        return
    no = await no_khi_ve(conn, clinic_id=su_kien.clinic_id, visit_id=str(visit_id))
    if no.dong:
        return
    await conn.execute(
        "UPDATE public.cong_no SET trang_thai = 'DA_THU', thu_luc = now()"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid AND trang_thai = 'CHUA_THU'",
        su_kien.clinic_id,
        mo["id"],
    )
    await emit_event(
        conn,
        ten="cong_no.da_thu",
        clinic_id=su_kien.clinic_id,
        aggregate_id=mo["id"],
        payload=CongNoDaThu(
            visit_id=str(visit_id), cong_no_id=mo["id"], so_tien=int(mo["so_tien"])
        ),
        boi=NguoiGayRa(actor_type=su_kien.actor_type, staff_id=su_kien.actor_staff_id),
        correlation_id=str(visit_id),
        causation_id=su_kien.event_id,
    )


dang_ky(CONG_NO, xet_da_thu)

__all__ = ["xet_da_thu"]
