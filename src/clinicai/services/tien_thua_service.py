"""TIỀN THỪA Ở QUẦY — xử lý tới nơi (Tuyền chốt phần E, 06/10/2026).

Tiền thừa = khoản đã thu cho chỉ định nay đã bỏ / không làm, hoặc dịch vụ khám
đã thu nay bỏ tick (E7), trừ phần đã hoàn. Trước đây tiền thừa chỉ hiện ở quầy:
check-out không hỏi, báo cáo không có, sang hôm sau là mất dấu (E2).

Nay:
  * **Hoàn tiền thừa** (`hoan_tien_thua`): quầy bấm một nút, máy hoàn ĐÚNG số
    còn thừa của từng dòng hoá đơn (tiền mặt) — không gõ số tuỳ ý. Ai có lego
    Thu tiền dịch vụ làm được (E2b, thay luật tạm chỉ Quản lý).
  * **Giữ lại** (`giu_lai` / `huy_giu_lai`): khách không lấy lại (đổi sang dịch
    vụ khác lần sau, gửi lại…) — ghi lý do, ai, lúc nào; hoàn tác được tới khi
    check-out. Một lượt chỉ một lần giữ lại còn hiệu lực — ép ở Postgres
    (`uq_tien_thua_giu_lai_song`, mig 20261006200003).
  * **Check-out** (`tien_thua_khi_ve`): còn tiền thừa chưa hoàn / chưa giữ lại
    thì máy chủ CHẶN, nhưng KHÔNG khoá cứng — hai lối qua ngay trong hộp
    check-out (E2a).

Luật ở đây; TSX chỉ vẽ hộp và gửi lệnh.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity

#: Dòng hoá đơn ĐÃ THU còn tiền thừa — theo lượt của CHỈ ĐỊNH (mang sang vẫn
#: là của lượt đang giữ chỉ định) hoặc theo lượt của dòng tiền khám.
_DONG_THUA_SQL = """
WITH dong AS (
    SELECT bl.id::text AS line_id, bl.visit_id::text AS line_visit_id,
           bl.payment_cycle_id::text AS payment_cycle_id, bl.source_type,
           bl.source_id, bl.name_snapshot, bl.quantity, bl.line_total,
           CASE WHEN bl.source_type = 'service_order' THEN bl.source_id
                WHEN bl.source_type = 'phu_thu' THEN (
                    SELECT p.service_order_id::text FROM public.luot_phu_thu p
                     WHERE p.clinic_id = bl.clinic_id AND p.id::text = bl.source_id)
           END AS order_id,
           coalesce(h.sl, 0) AS da_hoan_sl, coalesce(h.tien, 0) AS da_hoan
      FROM public.payment_bill_line bl
      JOIN public.payment_cycle c
        ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
      LEFT JOIN LATERAL (
           SELECT sum(l.quantity) AS sl, sum(l.amount) AS tien
             FROM public.payment_refund_line l
             JOIN public.payment_refund r
               ON r.refund_id = l.refund_id AND r.clinic_id = l.clinic_id
            WHERE l.clinic_id = bl.clinic_id AND l.payment_bill_line_id = bl.id
              AND r.status IN ('PENDING', 'COMPLETED')) h ON true
     WHERE bl.clinic_id = $1::uuid AND c.status = 'PAID'
       AND bl.billing_owner = 'CLINIC' AND bl.kind = 'dich_vu'
       AND bl.source_type IN ('service_order', 'phu_thu', 'exam')
)
SELECT d.*, coalesce(o.visit_id::text, d.line_visit_id) AS visit_id,
       o.exec_status, o.cancel_reason, o.not_performed_reason
  FROM dong d
  LEFT JOIN public.service_order o
    ON o.clinic_id = $1::uuid AND o.id::text = d.order_id
 WHERE d.line_total - d.da_hoan > 0
   AND (
        (d.source_type IN ('service_order', 'phu_thu')
         AND o.exec_status IN ('cancelled', 'not_performed')
         AND o.visit_id::text = ANY($2::text[]))
     OR (d.source_type = 'exam' AND d.line_visit_id = ANY($2::text[])
         AND d.source_id LIKE 'exam-%-selected-%'
         AND NOT EXISTS (
             SELECT 1 FROM public.luot_phi_kham k
              WHERE k.clinic_id = $1::uuid AND k.visit_id::text = d.line_visit_id
                AND k.bo_luc IS NULL
                AND d.source_id = 'exam-' || k.visit_id::text || '-selected-'
                                  || k.service_price_id::text))
   )
 ORDER BY d.line_visit_id, d.payment_cycle_id, d.line_id
"""


async def dong_tien_thua(
    conn: asyncpg.Connection, clinic_id: str, visit_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Lượt → các DÒNG HOÁ ĐƠN còn tiền thừa (đủ để hoàn đúng từng dòng)."""
    if not visit_ids:
        return {}
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in await conn.fetch(_DONG_THUA_SQL, clinic_id, [str(v) for v in visit_ids]):
        d = dict(r)
        out[d["visit_id"]].append(
            {
                "line_id": d["line_id"],
                "line_visit_id": d["line_visit_id"],
                "payment_cycle_id": d["payment_cycle_id"],
                "source_type": d["source_type"],
                "order_id": d["order_id"],
                "ten": d["name_snapshot"],
                "con_sl": Decimal(str(d["quantity"])) - Decimal(str(d["da_hoan_sl"])),
                "so_tien": int(d["line_total"]) - int(d["da_hoan"]),
                "loai": (
                    "BO_DICH_VU_KHAM"
                    if d["source_type"] == "exam"
                    else "BO_CHI_DINH"
                    if d["exec_status"] == "cancelled"
                    else "KHONG_LAM"
                ),
                "ly_do": (
                    d["cancel_reason"]
                    if d["exec_status"] == "cancelled"
                    else d["not_performed_reason"]
                ),
            }
        )
    return dict(out)


async def giu_lai_dang_co(
    conn: asyncpg.Connection, clinic_id: str, visit_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """Lần "giữ lại tiền thừa" còn hiệu lực của các lượt."""
    if not visit_ids:
        return {}
    rows = await conn.fetch(
        """
        SELECT g.id::text, g.visit_id::text, g.so_tien, g.ly_do, g.luc,
               s.full_name AS boi
          FROM public.tien_thua_giu_lai g
          LEFT JOIN public.staff s ON s.id = g.boi
         WHERE g.clinic_id = $1::uuid AND g.visit_id::text = ANY($2::text[])
           AND g.huy_luc IS NULL
        """,
        clinic_id,
        [str(v) for v in visit_ids],
    )
    return {
        r["visit_id"]: {
            "id": r["id"],
            "so_tien": int(r["so_tien"]),
            "ly_do": r["ly_do"],
            "boi": r["boi"],
            "luc": r["luc"].isoformat() if r["luc"] else None,
        }
        for r in rows
    }


def tom_tat_khi_ve(
    dong: list[dict[str, Any]], giu: dict[str, Any] | None
) -> dict[str, Any]:
    """Hộp tiền thừa lúc check-out. Hàm thuần.

    `chan` = còn tiền thừa mà chưa giữ lại phủ đủ (giữ lại rồi mà tiền thừa
    tăng thêm — bỏ thêm chỉ định — thì hỏi lại)."""
    tong = sum(int(d["so_tien"]) for d in dong)
    phu = giu is not None and int(giu["so_tien"]) >= tong
    return {
        "tong": tong,
        "dong": [
            {
                "ten": d["ten"],
                "so_tien": int(d["so_tien"]),
                "loai": d["loai"],
                "ly_do": d.get("ly_do"),
            }
            for d in dong
        ],
        "giu_lai": giu,
        "chan": tong > 0 and not phu,
    }


async def tien_thua_khi_ve(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> dict[str, Any]:
    dong = (await dong_tien_thua(conn, clinic_id, [visit_id])).get(visit_id, [])
    giu = (await giu_lai_dang_co(conn, clinic_id, [visit_id])).get(visit_id)
    return tom_tat_khi_ve(dong, giu)


def _ly_do(raw: Any) -> str:
    s = raw.strip() if isinstance(raw, str) else ""
    if len(s) < 3:
        raise ValidationError("Giữ lại tiền thừa thì phải ghi lý do (ít nhất 3 ký tự).")
    if len(s) > 500:
        raise ValidationError("Lý do dài quá 500 ký tự.")
    return s


async def _khoa_luot(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> asyncpg.Record:
    luot = await conn.fetchrow(
        "SELECT closed_at FROM public.visit WHERE clinic_id = $1::uuid"
        " AND visit_id = $2::uuid FOR UPDATE",
        clinic_id,
        visit_id,
    )
    if luot is None:
        raise ValidationError("Không tìm thấy lượt khám ở phòng khám này.")
    return luot


_HOAN_TIEN_THUA_SQL = """
SELECT coalesce(sum(rl.amount), 0)
  FROM public.payment_refund_line rl
  JOIN public.payment_refund r
    ON r.refund_id = rl.refund_id AND r.clinic_id = rl.clinic_id
  JOIN public.payment_bill_line bl
    ON bl.id = rl.payment_bill_line_id AND bl.clinic_id = rl.clinic_id
  LEFT JOIN public.service_order o
    ON bl.source_type = 'service_order' AND o.clinic_id = bl.clinic_id
   AND o.id::text = bl.source_id
  LEFT JOIN public.luot_phu_thu p
    ON bl.source_type = 'phu_thu' AND p.clinic_id = bl.clinic_id
   AND p.id::text = bl.source_id
  LEFT JOIN public.service_order op
    ON op.clinic_id = p.clinic_id AND op.id = p.service_order_id
 WHERE rl.clinic_id = $1::uuid AND r.status IN ('PENDING', 'COMPLETED')
   AND bl.visit_id::text = ANY($2::text[])
   AND (o.exec_status IN ('cancelled', 'not_performed')
        OR op.exec_status IN ('cancelled', 'not_performed')
        OR (bl.source_type = 'exam' AND bl.source_id LIKE 'exam-%-selected-%'
            AND NOT EXISTS (
                SELECT 1 FROM public.luot_phi_kham k
                 WHERE k.clinic_id = bl.clinic_id AND k.visit_id = bl.visit_id
                   AND k.bo_luc IS NULL
                   AND bl.source_id = 'exam-' || k.visit_id::text || '-selected-'
                                      || k.service_price_id::text)))
"""


async def bao_cao_tien_thua(
    conn: asyncpg.Connection, clinic_id: str, tu: Any, den: Any
) -> dict[str, int]:
    """Tiền thừa của các lượt trong khoảng ngày (giờ VN) cho báo cáo cuối ngày
    (06/10/2026, E2c): đã hoàn · giữ lại · còn treo (chưa hoàn, chưa giữ lại)."""
    vids = [
        str(v)
        for v in await conn.fetchval(
            "SELECT coalesce(array_agg(visit_id::text), '{}') FROM public.visit"
            " WHERE clinic_id = $1::uuid AND (coalesce(checked_in_at, created_at)"
            "   AT TIME ZONE 'Asia/Ho_Chi_Minh')::date BETWEEN $2 AND $3",
            clinic_id,
            tu,
            den,
        )
    ]
    if not vids:
        return {"da_hoan": 0, "giu_lai": 0, "con_treo": 0, "so_luot_con_treo": 0}
    dong = await dong_tien_thua(conn, clinic_id, vids)
    giu = await giu_lai_dang_co(conn, clinic_id, vids)
    giu_lai = con_treo = so_luot = 0
    for vid, ds in dong.items():
        tong = sum(int(d["so_tien"]) for d in ds)
        g = int(giu[vid]["so_tien"]) if vid in giu else 0
        giu_lai += min(g, tong)
        if tong > g:
            con_treo += tong - g
            so_luot += 1
    da_hoan = int(await conn.fetchval(_HOAN_TIEN_THUA_SQL, clinic_id, vids) or 0)
    return {
        "da_hoan": da_hoan,
        "giu_lai": giu_lai,
        "con_treo": con_treo,
        "so_luot_con_treo": so_luot,
    }


class TienThuaService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def giu_lai(
        self, *, identity: StaffIdentity, visit_id: str, ly_do: Any
    ) -> dict[str, Any]:
        """Khách không lấy lại tiền thừa — ghi lý do; check-out qua được."""
        s = _ly_do(ly_do)
        async with self._pool.acquire() as conn, conn.transaction():
            await _khoa_luot(conn, identity.clinic_id, visit_id)
            tt = await tien_thua_khi_ve(conn, identity.clinic_id, visit_id)
            if tt["tong"] <= 0:
                raise ValidationError("Lượt này không còn tiền thừa nào.")
            # Giữ lại lần nữa (tiền thừa tăng) = huỷ lần cũ rồi ghi lần mới.
            await conn.execute(
                "UPDATE public.tien_thua_giu_lai SET huy_luc = now(),"
                "       huy_boi = $3::uuid, ly_do_huy = 'Ghi lại theo số mới'"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                "   AND huy_luc IS NULL",
                identity.clinic_id,
                visit_id,
                identity.staff_id,
            )
            gid = await conn.fetchval(
                "INSERT INTO public.tien_thua_giu_lai"
                " (clinic_id, visit_id, so_tien, ly_do, boi)"
                " VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid) RETURNING id::text",
                identity.clinic_id,
                visit_id,
                tt["tong"],
                s,
                identity.staff_id,
            )
        return {"ok": True, "id": gid, "so_tien": tt["tong"]}

    async def huy_giu_lai(
        self, *, identity: StaffIdentity, visit_id: str, ly_do: Any = None
    ) -> dict[str, Any]:
        """Hoàn tác "giữ lại" (bấm nhầm) — chỉ khi khách CHƯA check-out."""
        async with self._pool.acquire() as conn, conn.transaction():
            luot = await _khoa_luot(conn, identity.clinic_id, visit_id)
            if luot["closed_at"] is not None:
                raise ValidationError(
                    "Khách đã check-out — muốn trả lại tiền thì bấm Hoàn tiền thừa."
                )
            gid = await conn.fetchval(
                "UPDATE public.tien_thua_giu_lai SET huy_luc = now(),"
                "       huy_boi = $3::uuid, ly_do_huy = $4"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                "   AND huy_luc IS NULL RETURNING id::text",
                identity.clinic_id,
                visit_id,
                identity.staff_id,
                (ly_do.strip()[:500] if isinstance(ly_do, str) else None) or None,
            )
            if gid is None:
                raise ValidationError("Lượt này chưa giữ lại tiền thừa nào.")
        return {"ok": True, "id": gid}


__all__ = [
    "TienThuaService",
    "bao_cao_tien_thua",
    "dong_tien_thua",
    "giu_lai_dang_co",
    "tien_thua_khi_ve",
    "tom_tat_khi_ve",
]
