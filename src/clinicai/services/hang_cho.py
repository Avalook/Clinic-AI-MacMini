"""Hàng chờ của lượt khám — vào hàng, chặn/mở chỗ chờ, "khách đang ở đâu".

Bóc khỏi ``luot_kham_service`` ngày 24/09/2026 (bước 3 của đợt bóc lõi). Bảng
``queue_entry`` là của khối Xếp phòng (``modules.py``: service_routing); trước
đây mọi thao tác trên nó nằm trong khối Khám, và khối Xếp phòng / Thực hiện
dịch vụ / Vòng đọc phải mượn hàm nội bộ ``LuotKhamService._release_blocked``…
Nay cả bốn dùng chung file này.

Luật giữ nguyên:
  * Khách đang được phục vụ ở một chỗ thì mọi chỗ chờ khác của khách TẠM KHOÁ
    (I9); rời phòng thì mở ra và tính giờ chờ TỪ BÂY GIỜ.
  * Một chỗ chờ sống cho mỗi (lượt, lý do, đối tượng) — Postgres ép bằng chỉ
    mục duy nhất một phần; vào hàng lần hai là không làm gì.
"""

from __future__ import annotations

import asyncpg

from clinicai.services import luot_kham_rules as rules


async def khach_dang_duoc_phuc_vu(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> bool:
    return bool(
        await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM queue_entry"
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
            " AND status = 'serving')",
            clinic_id,
            visit_id,
        )
    )


async def chan_cho_khac(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str, serving_id: str
) -> None:
    """Khách vào một phòng thì các chỗ chờ khác của khách tạm khoá (I9)."""
    await conn.execute(
        """
        UPDATE queue_entry
           SET status = 'blocked', updated_at = now(), version = version + 1
         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
           AND id <> $3::uuid AND status IN ('waiting', 'called')
        """,
        clinic_id,
        visit_id,
        serving_id,
    )


async def mo_cho_bi_chan(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> None:
    """Khách rời phòng: chỗ chờ đang khoá mở ra, tính giờ từ BÂY GIỜ.

    ``eligible_at = now()`` là luật "quay lại sau những người đang chờ,
    trước người vào sau" (START-HERE :49), không phải tiện tay.
    """
    await conn.execute(
        """
        UPDATE queue_entry
           SET status = 'waiting', eligible_at = now(),
               updated_at = now(), version = version + 1
         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
           AND status = 'blocked'
           AND NOT EXISTS (
               SELECT 1 FROM queue_entry s
                WHERE s.clinic_id = $1::uuid AND s.visit_id = $2::uuid
                  AND s.status = 'serving')
        """,
        clinic_id,
        visit_id,
    )


async def ve_lai_hang_phong(
    conn: asyncpg.Connection,
    clinic_id: str,
    visit_id: str,
    order_id: str,
    room_id: str | None,
) -> str | None:
    """Chỉ định quay lại "chờ làm" → khách hiện lại ở hàng chờ của phòng (V4).

    Dùng khi: Làm lại sau Dừng (chỗ chờ đã đóng 'done' lúc Dừng), Huỷ bắt đầu
    nhầm (chỗ chờ đang 'serving'), khách chuyển sang phòng khác giữa chừng.
    Trước 30/09/2026 Dừng → Làm lại để chỗ chờ ở 'done': màn phòng xếp khách
    vào nhóm "đã xong", không ai thấy khách đang đợi làm lại.

    Luôn đúng MỘT chỗ chờ sống cho chỉ định (Postgres giữ bằng
    `uq_queue_entry_live`): còn chỗ sống → đưa về chờ; không thì mở lại chỗ đã
    đóng gần nhất (giữ một dòng cho một chỉ định trên màn); không có gì → vào
    hàng mới. Khách đang được phục vụ ở chỗ KHÁC → 'blocked' (đợi quay lại,
    I9); không thì 'waiting' tính giờ từ bây giờ như `mo_cho_bi_chan`.

    Trả trạng thái chỗ chờ sau khi xếp; None khi chỉ định không có phòng.
    """
    if room_id is None:
        return None
    ban = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM queue_entry"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
        "   AND status = 'serving'"
        "   AND NOT (reason = 'SERVICE' AND ref_id = $3::uuid))",
        clinic_id,
        visit_id,
        order_id,
    )
    trang_thai = "blocked" if ban else "waiting"
    # Chỗ sống trước; không có thì chỗ 'done' gần nhất (Dừng đã đóng nó).
    cho = await conn.fetchval(
        "SELECT id::text FROM queue_entry"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
        "   AND reason = 'SERVICE' AND ref_id = $3::uuid"
        "   AND status IN ('blocked', 'waiting', 'called', 'serving', 'done')"
        " ORDER BY (status <> 'done') DESC, updated_at DESC LIMIT 1",
        clinic_id,
        visit_id,
        order_id,
    )
    if cho is None:
        await vao_hang(
            conn,
            clinic_id=clinic_id,
            visit_id=visit_id,
            lane="ROOM",
            reason="SERVICE",
            ref_id=order_id,
            room_id=room_id,
        )
        return str(
            await conn.fetchval(
                "SELECT status FROM queue_entry"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                "   AND reason = 'SERVICE' AND ref_id = $3::uuid"
                "   AND status NOT IN ('done', 'left', 'cancelled')",
                clinic_id,
                visit_id,
                order_id,
            )
        )
    await conn.execute(
        """
        UPDATE queue_entry
           SET status = $3, room_id = $4::uuid, lane = 'ROOM',
               serving_at = NULL, called_at = NULL, done_at = NULL,
               eligible_at = CASE WHEN status = 'done' THEN now()
                                  ELSE coalesce(eligible_at, now()) END,
               version = version + 1, updated_at = now()
         WHERE clinic_id = $1::uuid AND id = $2::uuid
        """,
        clinic_id,
        cho,
        trang_thai,
        room_id,
    )
    return trang_thai


async def vao_hang(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    visit_id: str,
    lane: str,
    reason: str,
    ref_id: str,
    doctor_id: str | None = None,
    room_id: str | None = None,
) -> None:
    status = rules.initial_queue_status(
        visit_busy=await khach_dang_duoc_phuc_vu(conn, clinic_id, visit_id)
    )
    await conn.execute(
        """
        INSERT INTO queue_entry
            (clinic_id, visit_id, lane, doctor_staff_id, room_id, reason,
             ref_id, status, eligible_at)
        VALUES ($1::uuid, $2::uuid, $3, $4::uuid, $5::uuid, $6, $7::uuid, $8,
                CASE WHEN $8 = 'waiting' THEN now() END)
        ON CONFLICT (visit_id, reason, ref_id)
            WHERE status NOT IN ('done', 'left', 'cancelled')
        DO NOTHING
        """,
        clinic_id,
        visit_id,
        lane,
        doctor_id,
        room_id,
        reason,
        ref_id,
        status,
    )


async def cap_nhat_vi_tri(conn: asyncpg.Connection, cid: str, vid: str) -> None:
    """Đặt con trỏ "khách đang ở đâu" (visit.current_node_code/room) theo
    hàng chờ của luồng khám mới.

    Bảng điều phối của trưởng ca, TV phòng chờ và bước đóng lượt đều đọc con
    trỏ này, mà luồng khám mới chưa từng dời nó: demo 17/09/2026 khám xong
    cả vòng rồi mà trưởng ca vẫn thấy khách "đang ở Đo chỉ số", và quầy
    không đóng được lượt.

    Đang được phục vụ ở đâu → ở đó; không thì chỗ đang gọi/đang chờ sớm nhất.
    Chỉ còn chỗ bị chặn (chờ kết quả) → giữ nguyên. Hết mọi chỗ → bước đóng
    lượt ở quầy tiếp đón.
    """
    r = await conn.fetchrow(
        """
        SELECT coalesce(
                   q.room_id,
                   (SELECT vt.room_id
                      FROM work_roster w
                      JOIN vi_tri_lam_viec vt
                        ON vt.clinic_id = w.clinic_id AND vt.code = w.station
                      JOIN clinic_room cr ON cr.id = vt.room_id
                     WHERE w.clinic_id = q.clinic_id
                       AND w.staff_id = coalesce(q.doctor_staff_id,
                                                 c.doctor_staff_id)
                       AND w.status <> 'REJECTED'
                       AND vt.room_id IS NOT NULL
                       -- Phòng bác sĩ ở ĐÚNG cơ sở lượt: bác sĩ có ca ở hai cơ
                       -- sở cùng ngày thì LIMIT 1 có thể vớ phòng cơ sở kia →
                       -- chốt DB phòng-cùng-cơ-sở chặn cứng (08/10/2026).
                       AND coalesce(cr.location_id,
                                    public.co_so_cua_luot(q.visit_id))
                           IS NOT DISTINCT FROM
                           coalesce(public.co_so_cua_luot(q.visit_id),
                                    cr.location_id)
                       AND w.work_date
                           = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                     ORDER BY vt.sort
                     LIMIT 1)
               ) AS room_id,
               coalesce(
                   o.node_code,
                   -- Bàn khám chưa rõ phòng (bác sĩ không có ca xếp phòng):
                   -- vẫn nói được khách đang ở bước KHÁM loại nào.
                   CASE WHEN q.reason <> 'SERVICE' THEN
                       CASE st.form_code
                           WHEN 'NT' THEN 'KHAM-NOITIET'
                           WHEN 'PK' THEN 'KHAM-PHUKHOA'
                           WHEN 'SK' THEN 'KHAM-SANKHOA'
                           WHEN 'NK' THEN 'KHAM-NAMKHOA'
                           WHEN 'HMVS' THEN 'KHAM-HIEMMUON-VOSINH'
                       END
                   END
               ) AS node_code
          FROM queue_entry q
          JOIN visit v ON v.visit_id = q.visit_id AND v.clinic_id = q.clinic_id
          LEFT JOIN service_type st ON st.id = v.service_type_id
          LEFT JOIN consultation c
            ON c.id = q.ref_id AND q.reason <> 'SERVICE'
           AND c.clinic_id = q.clinic_id
          LEFT JOIN service_order o
            ON o.id = q.ref_id AND q.reason = 'SERVICE'
           AND o.clinic_id = q.clinic_id
         WHERE q.clinic_id = $1::uuid AND q.visit_id = $2::uuid
           AND q.status IN ('serving', 'called', 'waiting')
         ORDER BY CASE q.status WHEN 'serving' THEN 0 WHEN 'called' THEN 1
                  ELSE 2 END,
                  coalesce(q.eligible_at, q.created_at)
         LIMIT 1
        """,
        cid,
        vid,
    )
    if r is not None:
        room_id = r["room_id"]
        node = r["node_code"] or (
            await conn.fetchval(
                "SELECT node_code FROM clinic_room WHERE id = $1::uuid",
                room_id,
            )
            if room_id
            else None
        )
    else:
        con_mo = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM queue_entry WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid AND status NOT IN ('done', 'left',"
            " 'cancelled'))",
            cid,
            vid,
        )
        if con_mo:
            return
        node = "LUOTKHAM-15"
        # Quầy của ĐÚNG cơ sở lượt (08/10/2026, hai cơ sở): không lọc thì khách
        # Hào Nam về quầy Kim Ngưu (quầy sort nhỏ nhất của cả phòng khám).
        room_id = await conn.fetchval(
            "SELECT id FROM clinic_room WHERE clinic_id = $1::uuid"
            " AND node_code = 'LUOTKHAM-01' AND is_active"
            " AND (public.co_so_cua_luot($2::uuid) IS NULL"
            "      OR location_id = public.co_so_cua_luot($2::uuid))"
            " ORDER BY sort LIMIT 1",
            cid,
            vid,
        )
    # Chỉ lượt còn mở: INCOMPLETE (khách bỏ về) / FINALIZED / AMENDED giữ
    # nguyên con trỏ cuối — không dời một người đã rời khỏi phòng khám.
    # node rỗng (chưa suy ra được bước) vẫn ghi: để trống còn hơn trỏ vào
    # phòng khách đã rời — trưởng ca đọc "đang ở Siêu âm" sai thì điều sai.
    await conn.execute(
        """
        UPDATE visit
           SET previous_node_code = CASE
                   WHEN current_node_code IS DISTINCT FROM $3
                   THEN current_node_code ELSE previous_node_code END,
               current_node_since = CASE
                   WHEN current_node_code IS DISTINCT FROM $3
                     OR current_room_id IS DISTINCT FROM $4::uuid
                   THEN now() ELSE current_node_since END,
               current_node_code = $3,
               current_room_id = $4::uuid,
               updated_at = now()
         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
           AND status IN ('OPEN', 'IN_PROGRESS')
        """,
        cid,
        vid,
        node,
        room_id,
    )


__all__ = [
    "cap_nhat_vi_tri",
    "chan_cho_khac",
    "khach_dang_duoc_phuc_vu",
    "mo_cho_bi_chan",
    "vao_hang",
    "ve_lai_hang_phong",
]
