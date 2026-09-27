"""Sinh hiệu của BUỔI KHÁM — lần đo mới nhất của khách trong cùng ngày.

Góp ý phòng khám 27/09/2026: khách "đăng ký thêm dịch vụ lần 2 trong buổi"
(lễ tân check-in thêm một LƯỢT mới cùng ngày) bị đẩy về Đo sinh hiệu như khách
mới đến — vì mọi thứ sinh hiệu tính theo ``visit_id``. Tuyền đã chốt "sinh hiệu
KHÔNG chặn" và "khách đến làm thủ thuật theo lịch: check-in xong lên thủ thuật
luôn".

BUỔI = cùng ``clinic_patient_id`` + cùng NGÀY giờ Việt Nam (``core.clock``) với
lúc lượt check-in. Lượt nhìn thấy:

  * mọi lần đo của CHÍNH nó (như trước — kể cả lượt mở vắt qua nửa đêm);
  * lần đo của các lượt khác cùng buổi mà check-in TRƯỚC nó. Lượt SAU không
    chảy ngược: phiếu lượt 1 in lại hôm sau vẫn đúng con số lúc khám lượt 1.

Mới nhất thắng (ĐD đo lại ở lượt 2 thì lượt 2 dùng số mới). Số đo KHÔNG chép
sang lượt mới — một con số một chỗ sửa (``phieu_kham/mang_sang.py``).

Module NHẸ, cố ý: chỉ asyncpg + đồng hồ, để khối Khám, phiếu khám và màn Xem
lượt cùng đọc mà không kéo vòng import. Chỉ ĐỌC bảng ``vital_measurement``
(của khối Sinh hiệu); không ghi.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import asyncpg

from clinicai.core.clock import CLINIC_TZ_NAME

_SQL = """
SELECT v.visit_id::text AS visit_id,
       m.nguon_visit_id, m.systolic, m.diastolic, m.pulse, m.temperature,
       m.weight_kg, m.height_cm, m.respiratory_rate, m.spo2, m.bmi,
       m.pain_score, m.created_at, m.nguoi_do,
       EXISTS (SELECT 1 FROM vital_measurement r
                WHERE r.clinic_id = v.clinic_id AND r.visit_id = v.visit_id)
         AS co_so_do_luot_nay
  FROM visit v
  JOIN LATERAL (
        SELECT m.visit_id::text AS nguon_visit_id, m.systolic, m.diastolic,
               m.pulse, m.temperature, m.weight_kg, m.height_cm,
               m.respiratory_rate, m.spo2, m.bmi, m.pain_score, m.created_at,
               s.full_name AS nguoi_do
          FROM vital_measurement m
          JOIN visit x
            ON x.clinic_id = m.clinic_id AND x.visit_id = m.visit_id
          LEFT JOIN staff s ON s.id = m.recorded_by
         WHERE m.clinic_id = v.clinic_id
           AND x.clinic_patient_id = v.clinic_patient_id
           AND (
                x.visit_id = v.visit_id
                OR (coalesce(x.checked_in_at, x.created_at)
                        < coalesce(v.checked_in_at, v.created_at)
                    AND (m.created_at AT TIME ZONE $3)::date
                        = (coalesce(v.checked_in_at, v.created_at)
                           AT TIME ZONE $3)::date)
           )
         ORDER BY m.created_at DESC, m.id DESC
         LIMIT 1
  ) m ON true
 WHERE v.clinic_id = $1::uuid AND v.visit_id = ANY($2::uuid[])
"""


async def sinh_hieu_cua_buoi_nhieu(
    conn: asyncpg.Connection, clinic_id: str, visit_ids: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """{visit_id: lần đo mới nhất của buổi} — lượt chưa có lần đo nào thì vắng.

    Mỗi dòng: các cột số đo (tên cột bảng), ``created_at``, ``nguoi_do``,
    ``nguon_visit_id`` (lượt đã đo) và ``co_so_do_luot_nay`` (lượt này có số đo
    riêng không).
    """
    ids = [str(v) for v in visit_ids if v]
    if not ids:
        return {}
    rows = await conn.fetch(_SQL, clinic_id, ids, CLINIC_TZ_NAME)
    return {r["visit_id"]: dict(r) for r in rows}


async def sinh_hieu_cua_buoi(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> dict[str, Any] | None:
    """Lần đo MỚI NHẤT của buổi (kể cả của lượt này) + lượt nguồn + lúc đo."""
    return (await sinh_hieu_cua_buoi_nhieu(conn, clinic_id, [visit_id])).get(
        str(visit_id)
    )


__all__ = ["sinh_hieu_cua_buoi", "sinh_hieu_cua_buoi_nhieu"]
