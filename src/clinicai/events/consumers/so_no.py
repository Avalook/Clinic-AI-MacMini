"""Khối SỔ NỢ HAI CHIỀU nghe mọi sự kiện làm đổi tiền nợ của lượt (14/10/2026).

Thu / huỷ phiếu / hoàn / về / mở lại lượt / ghi nợ / bỏ hay làm xong chỉ định /
giao thuốc / thêm vật tư → tính lại số dư "khách nợ phòng khám" và "phòng khám
nợ khách" của đúng lượt ấy rồi ghi phần chênh (`services/so_no_service.py`).

Đọc trạng thái HIỆN TẠI nên sự kiện tới trễ hay tới hai lần vẫn ra một kết quả;
một sự kiện chỉ ghi một lần mỗi chiều (chỉ mục duy nhất theo sự kiện). Phát lại
lịch sử thì im: số dư đọc bây giờ không phải số dư lúc ấy.

Tiền và chỉ định có thể thuộc HAI lượt khác nhau (chỉ định mang sang lượt mới,
thu ở lần thu của lượt đang đứng): sự kiện tiền mang `visit_id` của lần thu, nhưng
số dư của lượt GIỮ chỉ định cũng đổi — nên tính lại cả các lượt ấy (14/10/2026, bấm
thật: hoàn tiền thừa xong mà việc tồn của lượt cũ đứng yên).

Không sửa nơi phát: thêm bên nghe ở danh mục sự kiện là đủ.
"""

from __future__ import annotations

from datetime import UTC, datetime

import asyncpg

from clinicai.events.catalogue import SO_NO
from clinicai.events.worker import SuKienDaNhan, dang_ky
from clinicai.services.so_no_service import LOAI_THEO_SU_KIEN, ghi_chenh_lech


def _loai(su_kien: SuKienDaNhan) -> str:
    """Vì sao số dư đổi. Ghi nợ máy TỰ ghi khi huỷ phiếu sau khi khách về (G4d ·
    D) mang ``nguon`` = HUY_PHIEU: cùng giao dịch với ``payment.collection_undone``
    mà worker không giữ thứ tự giữa hai sự kiện khác nguồn — sự kiện nào tới
    trước thì dòng sổ cũng phải mang cùng một nhãn."""
    if su_kien.event_type == "cong_no.ghi" and su_kien.payload.get("nguon"):
        return str(su_kien.payload["nguon"])
    return LOAI_THEO_SU_KIEN.get(su_kien.event_type, "DOI_CHIEU")


#: Mọi lượt mà dòng hoá đơn của lần thu / lần hoàn chạm tới: lượt của dòng, lượt
#: của chỉ định (kể cả phụ thu), lượt của đơn thuốc.
_LUOT_LIEN_QUAN_SQL = """
WITH dong AS (
    SELECT bl.visit_id::text AS line_visit, bl.source_type, bl.source_id
      FROM public.payment_bill_line bl
     WHERE bl.clinic_id = $1::uuid
       AND (($2::text IS NOT NULL AND bl.payment_cycle_id::text = $2::text)
            OR ($3::text IS NOT NULL AND bl.id IN (
                SELECT l.payment_bill_line_id FROM public.payment_refund_line l
                 WHERE l.clinic_id = $1::uuid AND l.refund_id::text = $3::text)))
)
SELECT DISTINCT v FROM (
    SELECT d.line_visit AS v FROM dong d
    UNION
    SELECT o.visit_id::text FROM dong d
      JOIN public.service_order o
        ON d.source_type = 'service_order' AND o.clinic_id = $1::uuid
       AND o.id::text = d.source_id
    UNION
    SELECT o.visit_id::text FROM dong d
      JOIN public.luot_phu_thu p
        ON d.source_type = 'phu_thu' AND p.clinic_id = $1::uuid
       AND p.id::text = d.source_id
      JOIN public.service_order o
        ON o.clinic_id = $1::uuid AND o.id = p.service_order_id
    UNION
    SELECT rx.visit_id::text FROM dong d
      JOIN public.prescription rx
        /* rx:gom-ca-lich-su: tiền đã thu ở dòng đã đính chính vẫn thuộc lượt đó */
        ON d.source_type = 'prescription' AND rx.clinic_id = $1::uuid
       AND rx.id::text = d.source_id
) x WHERE v IS NOT NULL
"""


async def luot_lien_quan(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> list[str]:
    """Các lượt KHÁC `visit_id` của sự kiện mà tiền của sự kiện chạm tới."""
    chu = su_kien.payload
    lan_thu = chu.get("payment_cycle_id")
    hoan = chu.get("refund_id")
    if not lan_thu and not hoan:
        return []
    rows = await conn.fetch(
        _LUOT_LIEN_QUAN_SQL,
        su_kien.clinic_id,
        str(lan_thu) if lan_thu else None,
        str(hoan) if hoan else None,
    )
    chinh = str(chu.get("visit_id") or "")
    return sorted(str(r["v"]) for r in rows if str(r["v"]) != chinh)


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
        loai=_loai(su_kien),
        luc=luc,
        su_kien_id=su_kien.event_id,
        su_kien_ten=su_kien.event_type,
        boi=su_kien.actor_staff_id,
    )
    # Lượt khác của cùng khoản tiền: không có chỉ mục sự kiện (một sự kiện chỉ ghi
    # một lần mỗi chiều) — an toàn vì chỉ ghi PHẦN CHÊNH so với dòng cuối.
    for khac in await luot_lien_quan(conn, su_kien):
        await ghi_chenh_lech(
            conn,
            clinic_id=su_kien.clinic_id,
            visit_id=khac,
            loai="HOAN_TIEN" if su_kien.payload.get("refund_id") else "DOI_CHIEU",
            luc=luc,
            su_kien_ten=su_kien.event_type,
            boi=su_kien.actor_staff_id,
        )


dang_ky(SO_NO, ghi_so)

__all__ = ["ghi_so", "luot_lien_quan"]
