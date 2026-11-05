"""Bảng "Quyền" ở tab Cài đặt của bàn XN — CHỈ XEM (bản mẫu 05/11, Tuyền chốt).

Đọc `v_quyen_thuc_te` — đúng view mà `permissions.can.can()` hỏi khi gác cửa — nên bảng
nói đúng điều máy chủ làm, không phải bản chép thứ hai. Sửa quyền ở màn Phân quyền
(lego), không ở đây. Chỉ các quyền bàn XN thật sự hỏi:

* `partner.work` (lego 21 Đối tác) — vào bàn XN, làm mọi bước;
* `config.clinic.manage` — tab Tiền thu hộ, Cài đặt.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.core.tran import canh_bao_neu_day

#: (mã quyền, khoá cột trả về) — thứ tự cột trên màn.
QUYEN_BAN: tuple[tuple[str, str], ...] = (
    ("partner.work", "lam_viec"),
    ("config.clinic.manage", "quan_ly"),
)
TRAN = 500

_SQL = """
SELECT s.id::text AS staff_id, s.full_name AS ten,
       bool_or(q.capability = 'partner.work') AS lam_viec,
       bool_or(q.capability = 'config.clinic.manage') AS quan_ly
  FROM v_quyen_thuc_te q
  JOIN staff s ON s.id = q.staff_id AND s.clinic_id = q.clinic_id
 WHERE q.clinic_id = $1::uuid AND q.scope_type = 'CLINIC'
   AND q.capability = ANY($2::text[]) AND s.is_active
 GROUP BY s.id, s.full_name
 ORDER BY bool_or(q.capability = 'config.clinic.manage') DESC, lower(s.full_name)
 LIMIT 500
"""


async def bang_quyen(conn: asyncpg.Connection, cid: str) -> list[dict[str, Any]]:
    rows = await conn.fetch(_SQL, cid, [q for q, _ in QUYEN_BAN])
    canh_bao_neu_day("v_quyen_thuc_te", len(rows), TRAN, clinic_id=cid)
    return [dict(r) for r in rows]
