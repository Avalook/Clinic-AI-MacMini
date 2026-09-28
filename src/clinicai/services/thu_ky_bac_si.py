"""Thư ký y khoa đi theo bác sĩ (Tuyền chốt 15/09/2026, migration 20260915000020).

Một nguồn cho câu hỏi "thư ký này làm cho những bác sĩ nào". Mọi màn và mọi lệnh
của thư ký (bảng việc, lịch bác sĩ, lượt khám, siêu âm, duyệt kết quả, hồ sơ, bệnh
án, nháp chỉ định, nhập kết quả) dùng nó.

LUẬT CỨNG (Tuyền, 15/09 khuya): "thư ký nào thì theo bác sĩ ấy, không được làm
việc của bác sĩ khác". Thư ký CHƯA được phân bác sĩ nào → danh sách RỖNG → không
thấy, không làm được khách nào; màn hiện "chưa được phân bác sĩ — báo quản lý"
(GET /thu-ky/pham-vi). Lượt trước (cùng ngày) cho thư ký chưa phân thấy cả phòng
khám — đã bỏ. Người KHÔNG phải thư ký → `None` = không lọc theo luật này.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import doi_quyen
from clinicai.services.audit import record_event

CHUA_PHAN = "Bạn chưa được phân đi cùng bác sĩ nào — báo quản lý phân trong Cấu hình."
KHAC_BAC_SI = "Khách này của bác sĩ khác — thư ký chỉ làm cho bác sĩ mình được phân."


async def bac_si_cua_thu_ky(
    conn: asyncpg.Connection | asyncpg.Pool, identity: StaffIdentity
) -> list[str] | None:
    """Bác sĩ mà thư ký được phân; None = KHÔNG lọc theo luật này.

    Tuyền chốt 26/09/2026: thư ký thấy CẢ phòng khám; ĐÃ được xếp theo bác sĩ
    nào thì chỉ thấy khách của bác sĩ ấy. Luật 15/09 cũ ("chưa phân = thấy 0
    lượt") OFF: đo trên bản chạy thật 16/09, thư ký thấy ĐÚNG 0 lượt trong khi
    điều dưỡng và lễ tân thấy 19 — vì chưa ai phân bác sĩ cho họ. Luật mới không
    phụ thuộc công tắc mở quyền tạm thời.
    """
    # THEO DỮ LIỆU PHÂN CÔNG, không theo vai (27/09 đợt 3 — "chỉ dùng lego"):
    # chỉ tài khoản thư ký mới được phân (`dat_bac_si_cho_thu_ky` kiểm), nên có
    # dòng phân = đang đi cùng bác sĩ ấy; không có dòng = không lọc.
    ids = await conn.fetchval(
        "SELECT array_agg(bac_si_staff_id::text) FROM public.thu_ky_bac_si"
        " WHERE clinic_id = $1::uuid AND thu_ky_staff_id = $2::uuid",
        identity.clinic_id,
        identity.staff_id,
    )
    return list(ids) if ids else None


def kiem_thu_ky_duoc_lam(
    bac_si_duoc_phan: list[str] | None, bac_si_cua_luot: str | None
) -> None:
    """Chặn thư ký chạm vào lượt/khách không thuộc bác sĩ mình được phân."""
    if bac_si_duoc_phan is None:
        return
    if not bac_si_duoc_phan:
        raise SafetyGateError(CHUA_PHAN)
    if bac_si_cua_luot is None or bac_si_cua_luot not in bac_si_duoc_phan:
        raise SafetyGateError(KHAC_BAC_SI)


#: Khách "của" các bác sĩ: có lịch hẹn với họ, lượt khám họ phụ trách, hoặc việc
#: siêu âm họ THỰC HIỆN (work_item.assigned_to). Việc siêu âm CHƯA có bác sĩ nhận
#: là hàng chung của khoa siêu âm: thư ký đi cùng một bác sĩ siêu âm thấy được
#: ($3 = thư ký này có theo bác sĩ siêu âm nào không).
_KHACH_CUA_BAC_SI_SQL = """
SELECT a.clinic_patient_id::text AS id
  FROM public.appointment a
 WHERE a.clinic_id = $1::uuid AND a.doctor_id::text = ANY($2::text[])
UNION
SELECT v.clinic_patient_id::text
  FROM public.visit v
 WHERE v.clinic_id = $1::uuid AND v.attending_doctor_id::text = ANY($2::text[])
UNION
SELECT w.clinic_patient_id::text
  FROM public.work_item w
 WHERE w.clinic_id = $1::uuid
   AND w.node_code = 'DICHVU-SIEUAM'
   AND w.status <> 'CANCELLED'
   -- Chưa ai nhận + thư ký theo bác sĩ siêu âm → coi như của mình (lấy tạm
   -- một phần tử của danh sách để phép so khớp); đã nhận → so đúng người nhận.
   AND coalesce(w.assigned_to::text,
                CASE WHEN $3::boolean AND w.status IN ('PENDING', 'IN_PROGRESS')
                     THEN ($2::text[])[1] END)
       = ANY($2::text[])
"""


async def bac_si_sieu_am_trong(
    conn: asyncpg.Connection | asyncpg.Pool, clinic_id: str, bac_si: list[str]
) -> bool:
    """Trong danh sách có bác sĩ siêu âm nào không."""
    if not bac_si:
        return False
    return bool(
        await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM public.clinic_membership"
            " WHERE clinic_id = $1::uuid AND staff_id::text = ANY($2::text[])"
            " AND is_active AND role = 'ULTRASOUND_DOCTOR')",
            clinic_id,
            bac_si,
        )
    )


async def khach_duoc_xem(
    pool: asyncpg.Pool | asyncpg.Connection, identity: StaffIdentity
) -> list[str] | None:
    """Mã khách thư ký được xem; None = người gọi không phải TKYK."""
    bac_si = await bac_si_cua_thu_ky(pool, identity)
    if bac_si is None:
        return None
    if not bac_si:
        return []
    co_sa = await bac_si_sieu_am_trong(pool, identity.clinic_id, bac_si)
    rows = await pool.fetch(_KHACH_CUA_BAC_SI_SQL, identity.clinic_id, bac_si, co_sa)
    return [r["id"] for r in rows if r["id"]]


async def kiem_khach(
    pool: asyncpg.Pool | asyncpg.Connection,
    identity: StaffIdentity,
    clinic_patient_id: str,
) -> None:
    """Chặn thư ký mở khách không thuộc bác sĩ mình."""
    ids = await khach_duoc_xem(pool, identity)
    if ids is None:
        return
    bac_si = await bac_si_cua_thu_ky(pool, identity)
    if not bac_si:
        raise SafetyGateError(CHUA_PHAN)
    if clinic_patient_id not in ids:
        raise SafetyGateError(KHAC_BAC_SI)


async def pham_vi(pool: asyncpg.Pool, identity: StaffIdentity) -> dict[str, Any]:
    """Cho màn hình: người gọi có phải thư ký không, đi cùng bác sĩ nào."""
    # ĐỌC PHÂN CÔNG THẬT, KHÔNG QUA CÔNG TẮC MỞ QUYỀN (17/09/2026). Công tắc
    # làm `bac_si_cua_thu_ky` trả None ("không lọc"), và màn hình đọc None thành
    # "chưa được phân bác sĩ nào" — thư ký đã gắn BS Thành vẫn bị báo lỗi.
    # Công tắc chỉ nới QUYỀN; câu trả lời "đi cùng bác sĩ nào" vẫn là dữ liệu.
    if not identity.co_vai({ClinicRole.TKYK}):
        return {"la_thu_ky": False, "bac_si": []}
    bac_si = (
        await pool.fetchval(
            "SELECT array_agg(bac_si_staff_id::text) FROM public.thu_ky_bac_si"
            " WHERE clinic_id = $1::uuid AND thu_ky_staff_id = $2::uuid",
            identity.clinic_id,
            identity.staff_id,
        )
        or []
    )
    rows = await pool.fetch(
        "SELECT s.id::text AS id, s.full_name FROM public.staff s"
        "  JOIN public.clinic_membership m"
        "    ON m.staff_id = s.id AND m.clinic_id = $1::uuid"
        " WHERE s.id::text = ANY($2::text[]) ORDER BY s.full_name",
        identity.clinic_id,
        bac_si,
    )
    return {"la_thu_ky": True, "bac_si": [dict(r) for r in rows]}


async def dat_bac_si_cho_thu_ky(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    thu_ky_staff_id: str,
    bac_si_staff_ids: list[str],
) -> dict[str, Any]:
    """Quản lý phân thư ký theo những bác sĩ nào (thay cả danh sách)."""
    ids = sorted(set(bac_si_staff_ids))
    async with pool.acquire() as conn, conn.transaction():
        # Lego 18 Cài đặt phòng khám (27/09 đợt 3), thay vai Quản lý.
        await doi_quyen(
            conn,
            identity,
            "config.clinic.manage",
            cau="Bạn không có quyền phân thư ký cho bác sĩ.",
        )
        la_thu_ky = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM public.clinic_membership"
            " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid AND is_active"
            " AND role = 'TKYK')",
            identity.clinic_id,
            thu_ky_staff_id,
        )
        if not la_thu_ky:
            raise ValidationError("Người này không phải thư ký y khoa của phòng khám.")
        if ids:
            dung = await conn.fetchval(
                "SELECT count(DISTINCT staff_id) FROM public.clinic_membership"
                " WHERE clinic_id = $1::uuid AND staff_id = ANY($2::uuid[])"
                " AND is_active AND role IN ('DOCTOR', 'ULTRASOUND_DOCTOR')",
                identity.clinic_id,
                ids,
            )
            if dung != len(ids):
                raise ValidationError("Có người trong danh sách không phải bác sĩ.")
        await conn.execute(
            "DELETE FROM public.thu_ky_bac_si"
            " WHERE clinic_id = $1::uuid AND thu_ky_staff_id = $2::uuid",
            identity.clinic_id,
            thu_ky_staff_id,
        )
        if ids:
            await conn.executemany(
                "INSERT INTO public.thu_ky_bac_si"
                " (clinic_id, thu_ky_staff_id, bac_si_staff_id, phan_boi)"
                " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid)",
                [
                    (identity.clinic_id, thu_ky_staff_id, b, identity.staff_id)
                    for b in ids
                ],
            )
        await record_event(
            conn,
            event_type="clinic_config.thu_ky_bac_si",
            aggregate_type="clinic",
            aggregate_id=identity.clinic_id,
            identity=identity,
            origin="api:clinic-config",
            payload={"doi_tuong_id": thu_ky_staff_id, "bac_si": ids},
        )
    return {"ok": True, "thu_ky_staff_id": thu_ky_staff_id, "bac_si": ids}
