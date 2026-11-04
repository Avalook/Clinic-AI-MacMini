"""Chạy bóng luật "đứng đâu làm việc đó" (Tuyền 04/11/2026).

Luật MỚI đang cân nhắc: việc tại chỗ (nhóm B) chỉ làm được khi hôm nay được xếp
lịch đứng một phòng có chức năng ấy (`phong_chuc_nang`); việc ai cũng làm (A)
luôn được; việc theo người (C) chỉ khi được cấp thật (`v_quyen_hieu_luc`, không
tính lịch). Đo prod 04/11: 67/69 người có đủ 14 việc tại chỗ cả ngày từ đợt "mở
full lego", nên luật lịch hiện không giới hạn được gì — trước khi bật phải biết
ai sẽ bị chặn ở việc nào.

Ở đây CHỈ GHI: mỗi lệnh ghi qua cổng quyền thêm một dòng `quyen_chay_bong`.
Không bao giờ đổi kết quả quyền, không bao giờ làm hỏng lệnh chính — ghi trong
savepoint, lỗi thì nuốt và cảnh báo. Lệnh chính rollback thì dòng bóng đi theo:
sổ đếm lệnh đã chạy thật.

Ba nhóm việc ở `permissions/nhom_viec.py`. Trưởng ca có lý do riêng trên sổ
(chưa chốt trưởng ca mặc nhiên làm mọi việc tại chỗ).
"""

from __future__ import annotations

import asyncpg
import structlog

from clinicai.api.identity import StaffIdentity
from clinicai.permissions.catalogue import tra_quyen
from clinicai.permissions.nhom_viec import KHOI_THEO_PHONG, nhom_cua

logger = structlog.get_logger(__name__)

GIU_NGAY = 45

LY_DO: dict[str, str] = {
    "nhom_a": "Việc ai cũng có",
    "co_cap": "Việc theo người — đã được cấp",
    "chua_cap": "Việc theo người — chưa được cấp",
    "dung_phong": "Đứng phòng có chức năng này",
    "khong_lich": "Hôm nay không có lịch đứng phòng nào",
    "phong_thieu": "Phòng đang đứng không có chức năng này",
    "sai_phong": "Đứng phòng khác, không phải phòng của lệnh",
    "truong_ca": "Chỉ đứng vị trí trưởng ca (chưa chốt trưởng ca làm mọi việc tại chỗ)",
    "chua_nhom": "Khối chưa xếp nhóm",
}


# Một câu: tính phòng đứng hôm nay + luật mới + ghi. $5 = nhóm, $6 = khối theo
# phòng, $7 = kết quả cũ, $8 = cổng. Lý do B xét theo thứ tự: đúng → sai phòng
# → phòng thiếu → chỉ trưởng ca → không lịch.
_GHI = """
WITH lich AS (
    SELECT w.station
      FROM public.work_roster w
     WHERE w.clinic_id = $1::uuid AND w.staff_id = $2::uuid
       AND w.status <> 'REJECTED'
       AND w.work_date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
), phong AS (
    SELECT DISTINCT r.id AS room_id
      FROM lich l
      JOIN public.vi_tri_lam_viec v
        ON v.clinic_id = $1::uuid AND v.code = l.station
       AND v.is_active AND v.room_id IS NOT NULL
      JOIN public.clinic_room r
        ON r.id = v.room_id AND r.clinic_id = $1::uuid AND r.is_active
), so AS (
    SELECT
        coalesce((SELECT array_agg(room_id ORDER BY room_id) FROM phong),
                 '{}') AS phong_lich,
        EXISTS (SELECT 1 FROM phong p JOIN public.phong_chuc_nang f
                  ON f.room_id = p.room_id AND f.work_pack = $9
                 WHERE NOT $6 OR $4::uuid IS NULL OR p.room_id = $4::uuid) AS dung,
        EXISTS (SELECT 1 FROM phong p JOIN public.phong_chuc_nang f
                  ON f.room_id = p.room_id AND f.work_pack = $9) AS co_o_phong_khac,
        EXISTS (SELECT 1 FROM phong) AS co_phong,
        EXISTS (SELECT 1 FROM lich l JOIN public.quyen_theo_vi_tri_bang() b
                  ON b.ma_vi_tri = l.station) AS truong_ca,
        EXISTS (SELECT 1 FROM public.v_quyen_hieu_luc q
                 WHERE q.clinic_id = $1::uuid AND q.staff_id = $2::uuid
                   AND q.capability = $3
                   AND (q.scope_type = 'CLINIC'
                        OR ($4::uuid IS NOT NULL AND q.scope_id = $4::uuid))) AS co_cap
)
INSERT INTO public.quyen_chay_bong
    (clinic_id, staff_id, capability, work_pack, nhom, phong_id, phong_lich,
     cho_cu, cho_moi, ly_do, cong)
SELECT $1::uuid, $2::uuid, $3, $9, $5, $4::uuid, so.phong_lich, $7,
       CASE $5 WHEN 'A' THEN true WHEN 'B' THEN so.dung
               WHEN 'C' THEN so.co_cap ELSE $7 END,
       CASE $5
           WHEN 'A' THEN 'nhom_a'
           WHEN 'C' THEN CASE WHEN so.co_cap THEN 'co_cap' ELSE 'chua_cap' END
           WHEN 'B' THEN CASE
               WHEN so.dung THEN 'dung_phong'
               WHEN so.co_o_phong_khac THEN 'sai_phong'
               WHEN so.co_phong THEN 'phong_thieu'
               WHEN so.truong_ca THEN 'truong_ca'
               ELSE 'khong_lich' END
           ELSE 'chua_nhom'
       END,
       $8
  FROM so
"""


async def ghi_bong(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    quyen: str,
    *,
    phong_id: str | None,
    cho_cu: bool,
    cong: str = "lenh",
) -> None:
    """Ghi một dòng chạy bóng. Không bao giờ ném, không bao giờ đổi quyền."""
    try:
        khoi = tra_quyen(quyen).khoi
        async with conn.transaction():  # savepoint: hỏng không kéo lệnh chính
            await conn.execute(
                _GHI,
                identity.clinic_id,
                identity.staff_id,
                quyen,
                phong_id,
                nhom_cua(khoi),
                khoi in KHOI_THEO_PHONG,
                cho_cu,
                cong,
                khoi,
            )
    except Exception:  # noqa: BLE001 — sổ đo hỏng không được làm hỏng lệnh
        logger.warning("chay_bong_ghi_hong", quyen=quyen, exc_info=True)


async def don_cu(pool: asyncpg.Pool) -> int:
    """Xoá dòng bóng cũ hơn 45 ngày. Không bao giờ ném."""
    try:
        kq = await pool.execute(
            "DELETE FROM public.quyen_chay_bong"
            f" WHERE luc < now() - interval '{GIU_NGAY} days'"
        )
        return int(str(kq).split()[-1])
    except Exception:  # noqa: BLE001
        logger.warning("chay_bong_don_hong", exc_info=True)
        return 0


__all__ = ["GIU_NGAY", "LY_DO", "don_cu", "ghi_bong"]
