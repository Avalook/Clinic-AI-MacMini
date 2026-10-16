"""Lịch hẹn tuần viết lại (14/10/2026) PHẢI trả Y HỆT bản cũ.

    scripts/test-nhanh.sh src/tests/services/test_tuan_hen_tuong_duong_db.py

Bản cũ chạy ba thứ theo TỪNG DÒNG (cả tuần ~200 dòng): `resolve_effective_cap`
(hàm SECURITY DEFINER ~0,1 ms), `EXISTS` trên view `v_viec_cskh` (chạy lại cả
`lich_vuot_suc_chua`), và mốc "khám đầu tiên" của bệnh nhân (bộ lọc cơ sở viết
bằng `coalesce(...) IS NOT DISTINCT FROM coalesce(...)` làm planner ước 1 dòng
rồi chọn vòng lặp lồng). Bản mới tính sức chứa theo (bác sĩ, giờ) KHÁC NHAU,
tính tập "vượt sức chứa" MỘT lần, và viết bộ lọc cơ sở dạng có thể ước lượng.

Bài này giữ NGUYÊN VĂN câu cũ làm thước, rồi so từng dòng · từng cột · đúng thứ
tự trên dữ liệu ngẫu nhiên: nhiều trạng thái / kênh / bác sĩ (kể cả không bác
sĩ, bác sĩ bị gỡ) / cơ sở, bệnh nhân lặp (Tái khám / Khám lần đầu), lịch VƯỢT
SỨC CHỨA thật, lịch đã check-in có lượt.
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.services.week_appointments_service import (
    _SQL,
    HIDDEN_STATUSES,
    _vn_midnight,
)
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_luot_kham_service_db import _nguoi
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

#: BẢN CŨ, nguyên văn (trước 14/10/2026), đã thay `%d` = 500 — thước đo, KHÔNG sửa.
_TUAN_SQL_CU = """WITH tuan AS (
    SELECT a.id, a.slot_start, a.status, a.queue_number, a.doctor_id,
           a.so_booking, a.so_tiep_don,
           a.booking_channel, a.clinic_patient_id, a.service_type_id,
           a.created_at, a.bac_si_da_go_id, a.notes, a.location_id
      FROM appointment a
     WHERE a.clinic_id  = $1::uuid
       AND a.slot_start >= $2
       AND a.slot_start <  $3
       AND a.status <> ALL($4::text[])
       -- Chỉ lịch của cơ sở đang đứng (hai cơ sở, 08/10/2026); NULL = mọi cơ sở.
       AND coalesce(a.location_id, $5::uuid)
           IS NOT DISTINCT FROM coalesce($5::uuid, a.location_id)
     -- THỨ TỰ PHẢI XÁC ĐỊNH, và bản cũ thì không.
     --
     -- Prod đang có BA lịch hẹn cùng mốc 10:15 ngày 15/07. Với `ORDER BY
     -- slot_start` trần, Postgres được phép trả chúng theo thứ tự bất kỳ, và
     -- thực tế nó đổi giữa các lần chạy — nghĩa là lưới trang chủ xếp ba bệnh
     -- nhân ấy khác nhau mỗi lần tải. Lễ tân đọc dọc danh sách để gọi tên thì
     -- đó không phải chuyện hình thức.
     --
     -- created_at = thứ tự đặt lịch, câu trả lời có nghĩa nhất cho "ai trước"
     -- trong cùng một khung. id chốt lại phần còn lại để không bao giờ hoà.
     ORDER BY a.slot_start, a.created_at, a.id
     LIMIT 500
),
-- Mốc hẹn SỚM NHẤT của từng bệnh nhân xuất hiện trong tuần. Chỉ những người
-- thật sự có mặt trên lưới, nên đây là một phép quét hẹp chứ không phải toàn
-- bảng — và không dòng nào phải đi qua mạng.
som_nhat AS (
    SELECT a.clinic_patient_id, min(a.slot_start) AS dau_tien
      FROM appointment a
     WHERE a.clinic_id = $1::uuid
       AND a.clinic_patient_id IN (SELECT clinic_patient_id FROM tuan)
       -- LỊCH ĐÃ HUỶ / KHÔNG ĐẾN / BÁC SĨ TỪ CHỐI KHÔNG TÍNH LÀ LẦN TRƯỚC.
       --
       -- Bản cũ quét MỌI trạng thái, nên một khách đặt rồi huỷ, hôm sau đặt
       -- lại, thì lịch thứ hai bị gọi là lần-không-phải-đầu — dù họ chưa từng
       -- bước chân tới. Cùng lúc màn Quản lý khách hàng gọi đúng người ấy là
       -- "Khách mới" (nó đếm lượt khám XONG, và cố ý bỏ lịch đã huỷ). Hai màn
       -- nói ngược nhau về cùng một người, trong cùng một ca trực.
       --
       -- Chỉ lộ ra khi đổi cách gọi tên ngày 14/08/2026: "Tái khám" là thuật
       -- ngữ về LOẠI LỊCH nên bản cũ còn đọc xuôi được, nhưng "Khám cũ" là câu
       -- khẳng định về NGƯỜI — và với khách chưa từng tới thì nó sai thẳng.
       AND a.status <> ALL($4::text[])
     GROUP BY a.clinic_patient_id
)
SELECT t.id, t.slot_start, t.status, t.queue_number, t.doctor_id,
       t.so_booking, t.so_tiep_don,
       t.booking_channel, t.notes,
       -- LỊCH NÀY VỪA MẤT BÁC SĨ: có người phụ trách, nhưng người ấy không còn
       -- ca KHÁM vào đúng ngày khám.
       --
       -- Cùng luật với cảnh báo ở màn Quản lý khách hàng (customers/page.tsx).
       -- Bảng "check đặt lịch" trước nay không có gì nói chuyện này, nên quản
       -- lý gỡ một ca trực xong thì hàng lịch của khách nằm im dưới tên một bác
       -- sĩ hôm đó không đi làm — và người trực chỉ biết khi khách tới quầy.
       --
       -- `station = 'LICH_KHAM'`: câu hỏi không phải "hôm ấy có mặt ở phòng
       -- khám không" mà "hôm ấy có ngồi bàn khám không". Một bác sĩ còn ca thủ
       -- thuật ngoài giờ vẫn là mất bác sĩ đối với lịch hẹn khám.
       --
       -- CHỈ TÍNH CHO LỊCH CÒN CỨU ĐƯỢC — chưa tới giờ và chưa check-in. Lịch
       -- đã qua mà mất bác sĩ thì không đổi lại được nữa; tô cảnh báo ở đó chỉ
       -- làm ngập bảng và dạy người đọc bỏ qua màu cảnh báo.
       (
         t.doctor_id IS NOT NULL
         AND t.slot_start > now()
         -- Tuần CHƯA công bố lịch trực = đặt tự do (luật 15/09/2026): không có
         -- ca trong bảng nháp không phải là bác sĩ nghỉ (16/09/2026).
         AND public.tuan_lich_truc_da_cong_bo($1::uuid, t.slot_start)
         AND t.status IN ('SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED')
         AND NOT EXISTS (
           SELECT 1 FROM public.work_roster w
            WHERE w.clinic_id = $1::uuid
              AND w.staff_id  = t.doctor_id
              AND public.la_ca_kham_bac_si(w.clinic_id, w.station)
              AND w.work_date =
                  (t.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
              -- Ca ở cơ sở khác không giữ được lịch ở cơ sở này.
              AND NOT EXISTS (
        SELECT 1 FROM public.vi_tri_lam_viec v_cs
          JOIN public.clinic_room r_cs ON r_cs.id = v_cs.room_id
         WHERE v_cs.clinic_id = w.clinic_id AND v_cs.code = w.station
           AND r_cs.location_id IS NOT NULL
           AND r_cs.location_id <> (t.location_id)::uuid)
         )
       ) AS mat_bac_si,
       -- BÁC SĨ ĐÃ BỊ GỠ khỏi lịch này khi ca trực của họ bị xoá.
       --
       -- Sau khi gỡ, `doctor_id` về NULL nên cờ `mat_bac_si` ở trên TẮT — nó
       -- đòi lịch phải CÓ bác sĩ. Cột này là thứ giữ cho màn hình còn nói được,
       -- và nói rõ hơn: đổi từ ai. Thiếu nó thì CSKH gọi khách chỉ nói được
       -- "lịch của chị bị đổi", không biết khách đang chờ gặp ai.
       bs_go.full_name AS bac_si_da_go,
       -- BÁC SĨ BỊ GỠ ĐÃ CÓ CA KHÁM TRỞ LẠI hôm đó chưa? Hai tình huống cần
       -- hai câu khác nhau trên màn: "đã nghỉ — xếp bác sĩ khác" (gọi khách
       -- đổi lịch) vs "ca đã xếp lại — gán lại bác sĩ" (việc nội bộ, một cú
       -- bấm). Sau bản add_shift tự gắn lại 15/08, nhánh hai chỉ còn xảy ra
       -- khi ghế của khung cũ đã bị lịch khác chiếm — nói đúng tình huống để
       -- người trực khỏi gọi khách vì một chuyện không cần gọi.
       (
         t.bac_si_da_go_id IS NOT NULL
         AND EXISTS (
           SELECT 1 FROM public.work_roster wg
            WHERE wg.clinic_id = $1::uuid
              AND wg.staff_id  = t.bac_si_da_go_id
              AND public.la_ca_kham_bac_si(wg.clinic_id, wg.station)
              AND wg.work_date =
                  (t.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
              AND NOT EXISTS (
        SELECT 1 FROM public.vi_tri_lam_viec v_cs
          JOIN public.clinic_room r_cs ON r_cs.id = v_cs.room_id
         WHERE v_cs.clinic_id = wg.clinic_id AND v_cs.code = wg.station
           AND r_cs.location_id IS NOT NULL
           AND r_cs.location_id <> (t.location_id)::uuid)
         )
       ) AS bs_go_co_ca_lai,
       -- Lịch VƯỢT SỨC CHỨA sau khi công bố lịch trực (20260915000014) — trang
       -- chủ báo cam ngay trên dòng lịch, cùng nguồn với khung báo CSKH.
       EXISTS (
         SELECT 1 FROM public.v_viec_cskh vv
          WHERE vv.clinic_id = $1::uuid
            AND vv.appointment_id = t.id
            AND vv.trang_thai = 'VUOT_SUC_CHUA'
       ) AS vuot_suc_chua,
       CASE
         WHEN p.clinic_patient_id IS NULL THEN ''
         WHEN t.slot_start > s.dau_tien  THEN 'Tái khám'
         ELSE 'Khám lần đầu'
       END AS phan_loai,
       p.clinic_patient_id, p.patient_code, p.full_name, p.date_of_birth,
       p.phone_primary, p.phone_secondary, p.gender, p.ethnicity,
       p.nationality, p.occupation, p.patient_objection, p.address,
       p.guardian_name,
       d.full_name AS doctor_name,
       st.name     AS service_name,
       v.checked_in_at,
       v.thu_tu_tay_ms,
       v.visit_id,
       -- NHÃN TRẠNG THÁI (30/09/2026): khách đã về hay chưa là chuyện của
       -- LƯỢT, không phải của `appointment.status` — `trang_thai_hien_thi`.
       v.trang_thai_luot, v.ve_luc, v.kham_xong,
       p.uu_tien AS khach_uu_tien,
       p.uu_tien_ly_do,
       cap.slot_minutes,
       -- Số ghế TRỰC TIẾP của đúng (bác sĩ × khung) này, theo luật riêng —
       -- cùng hàm trigger dùng khi chặn. Trình duyệt không lấy trần chung của
       -- phòng khám nữa (29/09/2026).
       cap.walkin_cap
  FROM tuan t
  LEFT JOIN patient p
         ON p.clinic_patient_id = t.clinic_patient_id
        AND p.clinic_id = $1::uuid
  LEFT JOIN som_nhat s ON s.clinic_patient_id = t.clinic_patient_id
  LEFT JOIN staff d    ON d.id = t.doctor_id
  LEFT JOIN staff bs_go ON bs_go.id = t.bac_si_da_go_id
  LEFT JOIN service_type st ON st.id = t.service_type_id
  -- GIỜ ĐẾN THẬT. Endpoint này trước đây không trả `checked_in_at`, nên luật
  -- "có hẹn và đến đúng giờ" ở lưới trang chủ CHƯA TỪNG CHẠY: mọi dòng đều rơi
  -- xuống làn đến-sau và xếp theo giờ hẹn. Nhìn thì giống đang hoạt động, vì
  -- xếp theo giờ hẹn cũng ra một thứ tự hợp lý — chỉ sai khi có người đến muộn.
  LEFT JOIN LATERAL (
      SELECT vi.checked_in_at, vi.thu_tu_tay_ms, vi.visit_id::text AS visit_id,
             vi.status AS trang_thai_luot, vi.closed_at AS ve_luc,
             (vi.exam_completed_at IS NOT NULL) AS kham_xong
        FROM visit vi
       WHERE vi.appointment_id = t.id AND vi.clinic_id = $1::uuid
       ORDER BY vi.checked_in_at NULLS LAST
       LIMIT 1
  ) v ON TRUE
  LEFT JOIN LATERAL public.resolve_effective_cap(
      $1::uuid, t.doctor_id, t.slot_start
  ) cap ON TRUE
 ORDER BY t.slot_start, t.created_at, t.id
"""

#: Tuần thứ Hai xa trong tương lai: không dính dữ liệu của bài khác; mọi lịch
#: đều > now() nên `mat_bac_si` / `vuot_suc_chua` có nghĩa.
TUAN = date(2031, 3, 3)

TRANG_THAI = [
    "SCHEDULED",
    "CONFIRMED",
    "CSKH_CONFIRMED",
    "CONFIRMED",
    "CANCELLED",
    "NO_SHOW",
    "DOCTOR_DECLINED",
    "COMPLETED",
]
KENH = ["WALK_IN", "HOTLINE", "ONLINE", None, "HOTLINE"]


async def _cu(
    conn: asyncpg.Connection, start: datetime, end: datetime, co_so: str | None
) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in await conn.fetch(
            _TUAN_SQL_CU, CLINIC, start, end, list(HIDDEN_STATUSES), co_so
        )
    ]


async def _moi(
    conn: asyncpg.Connection, start: datetime, end: datetime, co_so: str | None
) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in await conn.fetch(
            _SQL, CLINIC, start, end, list(HIDDEN_STATUSES), co_so
        )
    ]


async def _so_sanh(
    conn: asyncpg.Connection, tuan: date, co_so: str | None
) -> list[dict[str, Any]]:
    s = _vn_midnight(tuan)
    e = _vn_midnight(tuan + timedelta(days=7))
    cu, moi = await _cu(conn, s, e, co_so), await _moi(conn, s, e, co_so)
    assert len(moi) == len(cu), f"{tuan} {co_so}: {len(cu)} -> {len(moi)} dòng"
    for a, b in zip(cu, moi, strict=True):
        assert a == b, f"{tuan} {co_so} khác:\ncũ ={a}\nmới={b}"
    return cu


async def test_tuan_tuong_duong_du_lieu_ngau_nhien(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    async with pool.acquire() as conn:
        bs = [ca.bac_si.staff_id, (await _nguoi(conn, ca.loc, "DOCTOR")).staff_id]
        # Cơ sở thứ hai (rỗng) để thử bộ lọc cơ sở.
        co_so_khac = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO roster_week (clinic_id, week_start) VALUES ($1::uuid, $2)"
            " ON CONFLICT DO NOTHING",
            CLINIC,
            TUAN,
        )
    khach = [await _benh_nhan(pool, ca) for _ in range(14)]
    rnd = random.Random(20261014)
    them = 0
    for i in range(120):
        slot = datetime.combine(
            TUAN + timedelta(days=rnd.randint(0, 6)), datetime.min.time(), tzinfo=UTC
        ) + timedelta(hours=rnd.randint(1, 9), minutes=15 * rnd.randint(0, 3))
        try:
            await pool.execute(
                "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
                " service_type_id, slot_start, slot_end, doctor_id, status,"
                " booking_channel, bac_si_da_go_id)"
                " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid,"
                " $8, $9, $10::uuid)",
                CLINIC,
                rnd.choice(khach),
                rnd.choice([ca.loc, ca.loc, None]),
                ca.loai_kham,
                slot,
                slot + timedelta(minutes=15),
                rnd.choice([None, *bs, *bs]),
                rnd.choice(TRANG_THAI),
                rnd.choice(KENH),
                rnd.choice([None, None, None, bs[0]]),
            )
            them += 1
        except asyncpg.PostgresError:
            continue  # trigger sức chứa / ràng buộc từ chối — bỏ dòng này
    assert them >= 40, f"chỉ chèn được {them} lịch"
    # Nhiều lịch CÙNG khung của bác sĩ 2 (kênh không phải trực tiếp) để cú hạ
    # sức chứa bên dưới có chỗ cắn — mỗi lịch một bệnh nhân khác nhau.
    chung = datetime.combine(TUAN, datetime.min.time(), tzinfo=UTC) + timedelta(
        days=2, hours=3
    )
    for k in khach[:6]:
        try:
            await pool.execute(
                "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
                " service_type_id, slot_start, slot_end, doctor_id, status,"
                " booking_channel)"
                " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid,"
                " 'CONFIRMED', 'HOTLINE')",
                CLINIC,
                k,
                ca.loc,
                ca.loai_kham,
                chung,
                chung + timedelta(minutes=15),
                bs[1],
            )
        except asyncpg.PostgresError:
            continue
    # Hạ sức chứa của bác sĩ 2 xuống 1/khung SAU khi chèn → nhiều lịch VƯỢT SỨC CHỨA.
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO doctor_booking_override (clinic_id, doctor_id,"
            " regular_cap, walkin_cap, effective_from, created_by, reason)"
            " VALUES ($1::uuid, $2::uuid, 1, 1, $3, $4::uuid, 'test so sanh')",
            CLINIC,
            bs[1],
            TUAN - timedelta(days=1),
            ca.le_tan.staff_id,
        )
    # Lịch đã check-in có lượt (giờ ~ bây giờ): xét cả tuần hiện tại.
    for _ in range(4):
        await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    async with pool.acquire() as conn:
        hom_nay = datetime.now(UTC).date()
        tuan_nay = hom_nay - timedelta(days=hom_nay.weekday())
        so_dong = 0
        co_vuot = tai_kham = lan_dau = co_luot = 0
        for tuan in (TUAN, tuan_nay, tuan_nay + timedelta(days=7)):
            for co_so in (None, ca.loc, co_so_khac):
                rows = await _so_sanh(conn, tuan, co_so)
                so_dong += len(rows)
                co_vuot += sum(1 for r in rows if r["vuot_suc_chua"])
                tai_kham += sum(1 for r in rows if r["phan_loai"] == "Tái khám")
                lan_dau += sum(1 for r in rows if r["phan_loai"] == "Khám lần đầu")
                co_luot += sum(1 for r in rows if r["visit_id"])
    # Phép so phải có nghĩa: đủ dòng, đủ hai loại phân loại, có vượt sức chứa
    # và có lượt đã check-in.
    assert so_dong >= 100 and tai_kham > 0 and lan_dau > 0, (so_dong, tai_kham, lan_dau)
    assert co_vuot > 0, "không có lịch vượt sức chứa — kịch bản quá nhạt"
    assert co_luot > 0, "không có lịch đã check-in có lượt"


async def test_tuan_trong_tra_ve_rong(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Tuần không có lịch (và cơ sở lạ): hai bản cùng rỗng, không ném."""
    async with pool.acquire() as conn:
        assert await _so_sanh(conn, date(2040, 1, 2), None) == []
        assert await _so_sanh(conn, date(2040, 1, 2), str(uuid.uuid4())) == []
