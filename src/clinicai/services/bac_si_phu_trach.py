"""Ai là BÁC SĨ của một việc — tách khỏi câu hỏi "ai được làm việc ấy".

Tuyền chốt 29/09/2026: *"Điều dưỡng và thư ký là TRỌN QUYỀN luôn — làm việc cho
bác sĩ thật sự."* Ai có quyền Bàn khám (lego `ban_kham`, hoặc được xếp lịch hôm
nay vào phòng khám — `v_quyen_thuc_te`) làm được như bác sĩ: khám, kê đơn, đính
chính đơn, Hoàn tất khám, bấm tiếp phiên bác sĩ đang mở.

Hai câu hỏi khác nhau, hai nơi trả lời:

* ĐƯỢC LÀM KHÔNG → luôn hỏi QUYỀN (`permissions/can.py`).
* AI LÀ BÁC SĨ (tên in ở chỗ ký, bác sĩ phụ trách của phiên, luật "hai bác sĩ
  không giành một lượt") → dữ liệu tài khoản: `clinic_membership.role` là
  DOCTOR / ULTRASOUND_DOCTOR. Đây là DANH TÍNH người ký, không phải quyền — trợ
  lý có trọn quyền vẫn không thành bác sĩ trên giấy.

Luật duy nhất còn chặn giữa những người có quyền: hai BÁC SĨ THẬT khác nhau
không giành một lượt / một phiên (HOLD đính chính chéo bác sĩ, Dr4Women).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime

import asyncpg

from clinicai.api.identity import vi_tri_dang_trong_ca
from clinicai.core.clock import now_vn

#: Vai tài khoản của người KÝ như bác sĩ.
VAI_BAC_SI: tuple[str, ...] = ("DOCTOR", "ULTRASOUND_DOCTOR")


async def bac_si_trong(
    conn: asyncpg.Connection, clinic_id: str, ids: Iterable[str | None]
) -> set[str]:
    """Những mã trong `ids` là tài khoản bác sĩ (còn hoạt động) của phòng khám."""
    ds = sorted({str(i) for i in ids if i})
    if not ds:
        return set()
    rows = await conn.fetch(
        "SELECT DISTINCT staff_id::text AS id FROM public.clinic_membership"
        " WHERE clinic_id = $1::uuid AND staff_id::text = ANY($2::text[])"
        " AND is_active AND role = ANY($3::text[])",
        clinic_id,
        ds,
        list(VAI_BAC_SI),
    )
    return {r["id"] for r in rows}


def hai_bac_si_khac_nhau(
    *, toi: str, bac_si_cua_viec: str | None, bac_si: set[str]
) -> bool:
    """Thuần: người bấm là bác sĩ thật VÀ việc đã thuộc một bác sĩ thật khác.

    Trợ lý (không phải bác sĩ) không bao giờ "giành" của bác sĩ; việc chưa có bác
    sĩ (hoặc đang ghi một người không phải bác sĩ) thì không có gì để giành."""
    return (
        bac_si_cua_viec is not None
        and bac_si_cua_viec != toi
        and toi in bac_si
        and bac_si_cua_viec in bac_si
    )


async def la_bac_si_khac(
    conn: asyncpg.Connection, clinic_id: str, toi: str, bac_si_cua_viec: str | None
) -> bool:
    """`hai_bac_si_khac_nhau` đọc tư cách bác sĩ từ database."""
    if not bac_si_cua_viec or bac_si_cua_viec == toi:
        return False
    return hai_bac_si_khac_nhau(
        toi=toi,
        bac_si_cua_viec=bac_si_cua_viec,
        bac_si=await bac_si_trong(conn, clinic_id, (toi, bac_si_cua_viec)),
    )


# ── BÁC SĨ THỰC HIỆN MẶC ĐỊNH CỦA PHIẾU KẾT QUẢ ──────────────────────────────
#
# Tuyền 29/09: "mặc định tên bác sĩ; trong hệ thống ghi lịch sử thì mới ghi dòng
# người nhập". Điều dưỡng bấm Hoàn tất phiếu siêu âm → chỗ ký "Bác sĩ thực hiện"
# phải là bác sĩ đứng phòng ấy hôm nay, không phải điều dưỡng. Người nhập /
# người bấm vẫn nằm ở `nhap_boi` / `hoan_tat_boi` (lịch sử).

_BAC_SI_DUNG_PHONG_SQL = """
SELECT w.staff_id::text AS id, w.station, w.shift, w.status, c.settings
  FROM public.service_order o
  JOIN public.vi_tri_lam_viec v
    ON v.clinic_id = o.clinic_id AND v.room_id = o.room_id
  JOIN public.work_roster w
    ON w.clinic_id = v.clinic_id AND w.station = v.code
  JOIN public.clinic_membership m
    ON m.clinic_id = w.clinic_id AND m.staff_id = w.staff_id
   AND m.is_active AND m.role = ANY($3::text[])
  JOIN public.clinic c ON c.id = o.clinic_id
 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
   AND w.status <> 'REJECTED'
   AND w.work_date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
 ORDER BY array_position(ARRAY['SANG', 'CHIEU', 'TOI', 'FULL'], w.shift),
          v.sort NULLS LAST, w.station, w.staff_id
"""


def bac_si_dang_trong_ca(
    dong: Sequence[tuple[str, str, str, str]], phut: int, settings: object
) -> list[str]:
    """Thuần: từ các dòng lịch ``(bác sĩ, trạm, ca, trạng thái)`` của phòng hôm
    nay → bác sĩ ĐANG trong ca lúc `phut` (cùng luật ca với cửa gác vai —
    `vi_tri_dang_trong_ca`; công tắc ca tắt thì mọi dòng trừ REJECTED)."""
    ket: list[str] = []
    for ai, tram, ca, trang_thai in dong:
        if vi_tri_dang_trong_ca([(tram, ca, trang_thai)], phut, settings):
            if ai not in ket:
                ket.append(ai)
    return ket


def bac_si_trong_ca_hoac_ca_ngay(
    dong: Sequence[tuple[str, str, str, str]], phut: int, settings: object
) -> list[str]:
    """Thuần: "bác sĩ của phòng" theo ca — ai ĐANG trong ca lúc `phut`; không
    ai đang trong ca (đầu / cuối ngày, nghỉ trưa) thì rơi về CẢ NGÀY (mọi dòng
    trừ REJECTED) để hàng chờ không bỗng dưng rỗng ngoài giờ ca."""
    dang = bac_si_dang_trong_ca(dong, phut, settings)
    if dang:
        return dang
    ket: list[str] = []
    for ai, _tram, _ca, trang_thai in dong:
        if trang_thai != "REJECTED" and ai not in ket:
            ket.append(ai)
    return ket


def bac_si_cung_phong(
    *,
    dong_cua_toi: Sequence[tuple[str, str, str, str]],
    dong_bac_si: Sequence[tuple[str, str, str, str, str]],
    phut: int,
    settings: object,
) -> list[str]:
    """Thuần: bác sĩ đứng CÙNG PHÒNG với tôi trong lịch hôm nay.

    `dong_cua_toi`: ``(phòng, trạm, ca, trạng thái)`` — lịch của tôi.
    `dong_bac_si`: ``(bác sĩ, phòng, trạm, ca, trạng thái)`` — lịch bác sĩ.
    Phòng của tôi = phòng tôi ĐANG trong ca (không ca nào đang diễn ra → mọi
    phòng hôm nay). Bác sĩ của các phòng ấy theo `bac_si_trong_ca_hoac_ca_ngay`.
    """
    dang = [
        (phong, tram, ca, tt)
        for phong, tram, ca, tt in dong_cua_toi
        if vi_tri_dang_trong_ca([(tram, ca, tt)], phut, settings)
    ]
    phong_toi = {
        phong for phong, _t, _c, tt in (dang or dong_cua_toi) if tt != "REJECTED"
    }
    if not phong_toi:
        return []
    return sorted(
        bac_si_trong_ca_hoac_ca_ngay(
            [
                (ai, tram, ca, tt)
                for ai, phong, tram, ca, tt in dong_bac_si
                if phong in phong_toi
            ],
            phut,
            settings,
        )
    )


_LICH_CUNG_PHONG_SQL = """
SELECT w.staff_id::text AS id, v.room_id::text AS phong, w.station, w.shift,
       w.status, (w.staff_id = $2::uuid) AS la_toi,
       EXISTS (SELECT 1 FROM public.clinic_membership m
                WHERE m.clinic_id = w.clinic_id AND m.staff_id = w.staff_id
                  AND m.is_active AND m.role = ANY($4::text[])) AS la_bac_si,
       c.settings
  FROM public.work_roster w
  JOIN public.vi_tri_lam_viec v
    ON v.clinic_id = w.clinic_id AND v.code = w.station
  JOIN public.clinic c ON c.id = w.clinic_id
 WHERE w.clinic_id = $1::uuid AND w.work_date = $3::date
   AND w.status <> 'REJECTED' AND v.room_id IS NOT NULL
   AND v.room_id IN (
       SELECT v2.room_id FROM public.work_roster w2
         JOIN public.vi_tri_lam_viec v2
           ON v2.clinic_id = w2.clinic_id AND v2.code = w2.station
        WHERE w2.clinic_id = $1::uuid AND w2.staff_id = $2::uuid
          AND w2.work_date = $3::date AND w2.status <> 'REJECTED')
 ORDER BY v.sort NULLS LAST, w.station, w.staff_id
"""


async def bac_si_cung_phong_hom_nay(
    conn: asyncpg.Connection | asyncpg.Pool,
    clinic_id: str,
    staff_id: str,
    *,
    luc: datetime | None = None,
) -> list[str]:
    """Bác sĩ (DOCTOR / ULTRASOUND_DOCTOR) đứng cùng phòng với `staff_id` trong
    lịch hôm nay, theo ca đang diễn ra (ngoài giờ ca → cả ngày). Gồm cả chính
    người ấy nếu họ là bác sĩ."""
    moc = luc or now_vn()
    rows = await conn.fetch(
        _LICH_CUNG_PHONG_SQL, clinic_id, staff_id, moc.date(), list(VAI_BAC_SI)
    )
    if not rows:
        return []
    return bac_si_cung_phong(
        dong_cua_toi=[
            (r["phong"], str(r["station"]), str(r["shift"]), str(r["status"]))
            for r in rows
            if r["la_toi"]
        ],
        dong_bac_si=[
            (r["id"], r["phong"], str(r["station"]), str(r["shift"]), str(r["status"]))
            for r in rows
            if r["la_bac_si"]
        ],
        phut=moc.hour * 60 + moc.minute,
        settings=rows[0]["settings"],
    )


def chon_bac_si_thuc_hien(
    *, nguoi_bam: str, nguoi_bam_la_bac_si: bool, bac_si_phong: Sequence[str]
) -> str:
    """Thuần: ai đứng tên "Bác sĩ thực hiện" khi không ai chọn người thực hiện.

    * Người bấm là bác sĩ → chính họ.
    * Phòng hôm nay có ĐÚNG MỘT bác sĩ đang trong ca → bác sĩ ấy.
    * Không có, hoặc nhiều bác sĩ (không biết ai làm) → người bấm, như cũ — thà
      in người thật đã bấm còn hơn in tên một bác sĩ có thể không làm ca này.
      Muốn tên bác sĩ thì chọn "Người thực hiện" trên phiếu.
    """
    if nguoi_bam_la_bac_si:
        return nguoi_bam
    ds = list(dict.fromkeys(bac_si_phong))
    if len(ds) == 1:
        return ds[0]
    return nguoi_bam


async def bac_si_thuc_hien_mac_dinh(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    service_order_id: str,
    nguoi_bam: str,
) -> str:
    """Người đứng tên thực hiện phiếu kết quả của chỉ định khi không ai chọn."""
    if await bac_si_trong(conn, clinic_id, [nguoi_bam]):
        return nguoi_bam
    # Phòng nhiều bác sĩ (30/09/2026): quầy đã chọn bác sĩ của làn → người ký là
    # bác sĩ ấy (điều dưỡng / thư ký của làn bấm Hoàn tất thay bác sĩ).
    da_chon = await conn.fetchval(
        "SELECT bac_si_lam_id::text FROM public.service_order"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid",
        clinic_id,
        service_order_id,
    )
    if da_chon and await bac_si_trong(conn, clinic_id, [da_chon]):
        return str(da_chon)
    rows = await conn.fetch(
        _BAC_SI_DUNG_PHONG_SQL, clinic_id, service_order_id, list(VAI_BAC_SI)
    )
    if rows:
        bay_gio = now_vn()
        dang_trong_ca = bac_si_dang_trong_ca(
            [
                (r["id"], str(r["station"]), str(r["shift"]), str(r["status"]))
                for r in rows
            ],
            bay_gio.hour * 60 + bay_gio.minute,
            rows[0]["settings"],
        )
        chon = chon_bac_si_thuc_hien(
            nguoi_bam=nguoi_bam, nguoi_bam_la_bac_si=False, bac_si_phong=dang_trong_ca
        )
        if chon != nguoi_bam:
            return chon
    # KHÔNG IN TÊN NGƯỜI KHÔNG PHẢI BÁC SĨ (Tuyền 29/09/2026: "cần người ký là
    # tên bác sĩ"). Phòng không có đúng một bác sĩ trong ca → bác sĩ chính của
    # lượt → bác sĩ đã chỉ định. Chỉ khi không ai trong số đó là bác sĩ mới
    # còn người bấm.
    ung_vien = await conn.fetchrow(
        """
        SELECT v.attending_doctor_id::text AS bac_si_luot,
               coalesce(o.authorized_by, o.recorded_by)::text AS bac_si_chi_dinh
          FROM public.service_order o
          JOIN public.visit v
            ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
         WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
        """,
        clinic_id,
        service_order_id,
    )
    if ung_vien is not None:
        for ai in (ung_vien["bac_si_luot"], ung_vien["bac_si_chi_dinh"]):
            if ai and await bac_si_trong(conn, clinic_id, [ai]):
                return str(ai)
    return nguoi_bam


# ── BÁC SĨ CỦA MỘT PHIÊN KHÁM ────────────────────────────────────────────────
#
# Tuyền 29/09: "mọi chỗ hiển thị bác sĩ phải ra TÊN BÁC SĨ, không phải người
# bấm". Điều dưỡng / thư ký bấm Bắt đầu khám cho khách CHƯA gán bác sĩ thì phiên
# từng không có bác sĩ, không phòng — khách hiện ở hàng chờ MỌI phòng dù đã có
# người nhận, và màn Check-out hiện "—" ở hàng "Khám với bác sĩ".

_UNG_VIEN_PHIEN_SQL = """
WITH c AS (
    SELECT c.id, c.visit_id, c.kind, c.doctor_staff_id
      FROM public.consultation c
     WHERE c.clinic_id = $1::uuid
       AND (($2::uuid IS NOT NULL AND c.id = $2::uuid)
            OR ($2::uuid IS NULL AND c.visit_id = $3::uuid
                AND c.status <> 'cancelled'))
     ORDER BY c.round_no DESC
     LIMIT 1
)
SELECT c.doctor_staff_id::text AS phien,
       (SELECT q.doctor_staff_id::text FROM public.queue_entry q
         WHERE q.clinic_id = $1::uuid AND q.ref_id = c.id
           AND q.reason <> 'SERVICE' AND q.doctor_staff_id IS NOT NULL
         ORDER BY (q.status NOT IN ('done', 'left', 'cancelled')) DESC,
                  q.created_at DESC
         LIMIT 1) AS hang,
       v.attending_doctor_id::text AS luot,
       a.doctor_id::text AS hen,
       CASE WHEN c.kind IN ('REVIEW', 'TU_VAN') THEN
           (SELECT c1.doctor_staff_id::text FROM public.consultation c1
             WHERE c1.clinic_id = $1::uuid AND c1.visit_id = v.visit_id
               AND c1.round_no = 1)
       END AS vong_1
  FROM public.visit v
  LEFT JOIN c ON c.visit_id = v.visit_id
  LEFT JOIN public.appointment a
    ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
 WHERE v.clinic_id = $1::uuid
   AND v.visit_id = coalesce((SELECT visit_id FROM c), $3::uuid)
"""


def chon_bac_si_phien(
    ung_vien: Sequence[str | None], bac_si: set[str], bac_si_phong: Sequence[str]
) -> str | None:
    """Thuần: ứng viên ĐẦU TIÊN là bác sĩ thật; không ai thì bác sĩ phòng nếu
    phòng có ĐÚNG MỘT bác sĩ (nhiều bác sĩ = không biết ai → không đoán)."""
    for ai in ung_vien:
        if ai and ai in bac_si:
            return ai
    ds = list(dict.fromkeys(bac_si_phong))
    return ds[0] if len(ds) == 1 else None


async def bac_si_cua_phien(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    consultation_id: str | None = None,
    visit_id: str | None = None,
    nguoi_bam: str | None = None,
    luc: datetime | None = None,
) -> str | None:
    """BÁC SĨ của một phiên khám (hoặc phiên mới nhất của lượt) — MỘT nguồn.

    Thứ tự, mỗi ứng viên phải là tài khoản bác sĩ (`bac_si_trong`):
      1. bác sĩ đã ghi trên phiên (`consultation.doctor_staff_id`);
      2. bác sĩ của chỗ chờ (`queue_entry.doctor_staff_id`);
      3. bác sĩ chính của lượt (`visit.attending_doctor_id`);
      4. bác sĩ của lịch hẹn (`appointment.doctor_id`);
      5. phiên đọc kết quả / tư vấn: bác sĩ phiên khám chính (vòng 1);
      6. bác sĩ DUY NHẤT đang trong ca ở phòng của NGƯỜI BẤM (lịch hôm nay).
    Không ai → None (không đoán tên một bác sĩ có thể không làm ca này).
    """
    if not consultation_id and not visit_id:
        return None
    r = await conn.fetchrow(_UNG_VIEN_PHIEN_SQL, clinic_id, consultation_id, visit_id)
    ung_vien: list[str | None] = (
        [r["phien"], r["hang"], r["luot"], r["hen"], r["vong_1"]]
        if r is not None
        else []
    )
    bac_si = await bac_si_trong(conn, clinic_id, ung_vien)
    chon = chon_bac_si_phien(ung_vien, bac_si, [])
    if chon is not None or not nguoi_bam:
        return chon
    return chon_bac_si_phien(
        [], set(), await bac_si_cung_phong_hom_nay(conn, clinic_id, nguoi_bam, luc=luc)
    )


__all__ = [
    "VAI_BAC_SI",
    "bac_si_cua_phien",
    "bac_si_cung_phong",
    "bac_si_cung_phong_hom_nay",
    "bac_si_dang_trong_ca",
    "bac_si_trong_ca_hoac_ca_ngay",
    "bac_si_thuc_hien_mac_dinh",
    "bac_si_trong",
    "chon_bac_si_phien",
    "chon_bac_si_thuc_hien",
    "hai_bac_si_khac_nhau",
    "la_bac_si_khac",
]
