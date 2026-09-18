"""Thai kỳ — bác sĩ tạo, xác nhận và chuyển kết cục trên bảng `pregnancy` sẵn có.

Batch pilot 18/09/2026. Trước đây bảng này không có lối ghi nào trong app: RLS
chỉ-đọc và backend không có lệnh, nên không ai tạo được thai kỳ.

LUẬT (contract Tuyền/ChatGPT 18/09):
  * CHỈ BÁC SĨ tạo thai kỳ chính thức, xác nhận/sửa dự kiến sinh, chuyển kết
    cục. Lễ tân, thư ký y khoa không tạo/chuyển được — không nới theo công tắc
    mở quyền tạm thời (đây là quyết định chuyên môn).
  * Dự kiến sinh do BÁC SĨ NHẬP kèm NGUỒN. Hệ thống không tự tính dự kiến sinh
    từ kỳ kinh cuối — chưa có quy tắc Dr4Women. Tuổi thai chỉ là phép trừ từ dự
    kiến sinh đã xác nhận (định nghĩa 280 ngày), hiển thị kèm nhãn nguồn.
  * Một thai kỳ ĐANG THEO DÕI mỗi khách (chỉ mục duy nhất ở Postgres).

Ngày do người dùng gửi: rác → câu lỗi, không 500 (luật CLAUDE.md).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import now_vn
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.audit import record_event
from clinicai.services.thu_ky_bac_si import kiem_khach

ORIGIN = "api:thai-ky"
NGUON_EDD = {
    "KY_KINH_CUOI": "Kỳ kinh cuối",
    "SIEU_AM": "Siêu âm",
    "KHAC": "Khác",
}
KET_CUC = frozenset({"DELIVERED", "MISCARRIAGE", "TERMINATED", "UNKNOWN"})
DOC_ROLES = frozenset(
    {
        ClinicRole.DOCTOR,
        ClinicRole.TKYK,
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.NURSE_ULTRASOUND,
    }
)


def doc_ngay(raw: Any) -> date | None:
    """YYYY-MM-DD → date; rỗng/rác → None. Không ném."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return None


def tuoi_thai_tu_edd(edd: date | None, hom_nay: date) -> dict[str, int] | None:
    """Tuổi thai = 280 ngày − số ngày tới dự kiến sinh. Ngoài 0–300 ngày → None."""
    if edd is None:
        return None
    ngay = 280 - (edd - hom_nay).days
    if not 0 <= ngay <= 300:
        return None
    return {"tuan": ngay // 7, "ngay": ngay % 7}


def _chi_bac_si(identity: StaffIdentity) -> None:
    if not identity.co_vai({ClinicRole.DOCTOR}):
        raise SafetyGateError("Chỉ bác sĩ tạo, xác nhận hoặc chuyển thai kỳ.")


def _ngay_bat_buoc(raw: Any, ten: str) -> date:
    ngay = doc_ngay(raw)
    if ngay is None:
        raise ValidationError(f"{ten} phải là ngày dạng YYYY-MM-DD.")
    return ngay


def _ngay_tuy_chon(raw: Any, ten: str) -> date | None:
    if raw in (None, ""):
        return None
    return _ngay_bat_buoc(raw, ten)


def _dong(r: asyncpg.Record, hom_nay: date) -> dict[str, Any]:
    edd = r["edd_date"]
    return {
        "id": str(r["id"]),
        "ket_cuc": r["outcome"],
        "ngay_ket_cuc": r["outcome_date"].isoformat() if r["outcome_date"] else None,
        "kinh_cuoi": r["lmp_date"].isoformat() if r["lmp_date"] else None,
        "du_kien_sinh": edd.isoformat() if edd else None,
        "nguon_du_kien_sinh": r["edd_nguon"],
        "nguon_du_kien_sinh_nhan": NGUON_EDD.get(r["edd_nguon"] or ""),
        # Chỉ tính cho thai kỳ đang theo dõi, và chỉ từ dự kiến sinh bác sĩ đã
        # xác nhận — nhãn nguồn đi kèm để không ai tưởng là số đo.
        "tuoi_thai": tuoi_thai_tu_edd(edd, hom_nay)
        if r["outcome"] == "ONGOING"
        else None,
        "nguy_co_cao": bool(r["is_high_risk"]),
        "ly_do_nguy_co": r["high_risk_reason"],
        "bac_si_xac_nhan": r["bac_si"],
        "cap_nhat_luc": r["updated_at"].isoformat() if r["updated_at"] else None,
    }


_SELECT = """
SELECT p.id, p.outcome, p.outcome_date, p.lmp_date, p.edd_date, p.edd_nguon,
       p.is_high_risk, p.high_risk_reason, p.updated_at,
       coalesce(u.full_name, c.full_name) AS bac_si
  FROM pregnancy p
  LEFT JOIN staff u ON u.id = p.updated_by
  LEFT JOIN staff c ON c.id = p.created_by
 WHERE p.clinic_id = $1::uuid AND p.clinic_patient_id = $2::uuid
"""


class ThaiKyService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(
        self, *, clinic_patient_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        if not identity.co_vai(DOC_ROLES):
            raise SafetyGateError("Vai của bạn không xem thai kỳ.")
        await kiem_khach(self._pool, identity, clinic_patient_id)
        hom_nay = now_vn().date()
        rows = await self._pool.fetch(
            _SELECT + " ORDER BY (p.outcome = 'ONGOING') DESC, p.created_at DESC",
            identity.clinic_id,
            clinic_patient_id,
        )
        ds = [_dong(r, hom_nay) for r in rows]
        hien_tai = next((d for d in ds if d["ket_cuc"] == "ONGOING"), None)
        return {
            "hien_tai": hien_tai,
            "truoc": [d for d in ds if d is not hien_tai],
            "duoc_ghi": identity.co_vai({ClinicRole.DOCTOR}),
            "nguon": [{"ma": k, "nhan": v} for k, v in NGUON_EDD.items()],
        }

    async def tao(
        self,
        *,
        clinic_patient_id: str,
        visit_id: str | None,
        du_lieu: dict[str, Any],
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        _chi_bac_si(identity)
        edd = _ngay_bat_buoc(du_lieu.get("du_kien_sinh"), "Dự kiến sinh")
        lmp = _ngay_tuy_chon(du_lieu.get("kinh_cuoi"), "Ngày đầu kỳ kinh cuối")
        nguon = du_lieu.get("nguon_du_kien_sinh")
        if nguon not in NGUON_EDD:
            raise ValidationError("Chọn nguồn của dự kiến sinh.")
        if lmp is not None and edd <= lmp:
            raise ValidationError("Dự kiến sinh phải sau ngày đầu kỳ kinh cuối.")
        nguy_co = bool(du_lieu.get("nguy_co_cao"))
        ly_do = str(du_lieu.get("ly_do_nguy_co") or "").strip() or None
        if nguy_co and not ly_do:
            raise ValidationError("Thai nguy cơ cao thì ghi lý do.")
        async with self._pool.acquire() as conn, conn.transaction():
            loc = await conn.fetchval(
                "SELECT location_id FROM patient WHERE clinic_id = $1::uuid"
                " AND clinic_patient_id = $2::uuid",
                identity.clinic_id,
                clinic_patient_id,
            )
            if loc is None:
                raise NotFoundError("Không tìm thấy khách hàng này.")
            if visit_id is not None:
                ok = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM visit WHERE clinic_id = $1::uuid"
                    " AND visit_id = $2::uuid AND clinic_patient_id = $3::uuid)",
                    identity.clinic_id,
                    visit_id,
                    clinic_patient_id,
                )
                if not ok:
                    raise ValidationError("Lượt khám không phải của khách này.")
            try:
                pid = await conn.fetchval(
                    """
                    INSERT INTO pregnancy
                        (clinic_id, clinic_patient_id, location_id, lmp_date,
                         edd_date, edd_nguon, is_high_risk, high_risk_reason,
                         primary_doctor_id, created_by, updated_by,
                         xac_nhan_visit_id)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8,
                            $9::uuid, $9::uuid, $9::uuid, $10::uuid)
                    RETURNING id::text
                    """,
                    identity.clinic_id,
                    clinic_patient_id,
                    loc,
                    lmp,
                    edd,
                    nguon,
                    nguy_co,
                    ly_do,
                    identity.staff_id,
                    visit_id,
                )
            except asyncpg.UniqueViolationError:
                raise ConflictError(
                    "Khách đã có một thai kỳ đang theo dõi — cập nhật thai kỳ ấy."
                ) from None
            await record_event(
                conn,
                event_type="pregnancy.created",
                aggregate_type="pregnancy",
                aggregate_id=str(pid),
                identity=identity,
                origin=ORIGIN,
                payload={"clinic_patient_id": clinic_patient_id, "visit_id": visit_id},
            )
        return {"ok": True, "id": pid}

    async def cap_nhat(
        self,
        *,
        pregnancy_id: str,
        du_lieu: dict[str, Any],
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        _chi_bac_si(identity)
        async with self._pool.acquire() as conn, conn.transaction():
            r = await conn.fetchrow(
                "SELECT outcome, lmp_date, edd_date, edd_nguon, is_high_risk,"
                " high_risk_reason FROM pregnancy WHERE clinic_id = $1::uuid"
                " AND id = $2::uuid FOR UPDATE",
                identity.clinic_id,
                pregnancy_id,
            )
            if r is None:
                raise NotFoundError("Không tìm thấy thai kỳ này.")
            if r["outcome"] != "ONGOING":
                raise ConflictError("Thai kỳ đã có kết cục — không sửa được nữa.")
            edd = r["edd_date"]
            if "du_kien_sinh" in du_lieu:
                edd = _ngay_bat_buoc(du_lieu.get("du_kien_sinh"), "Dự kiến sinh")
            lmp = r["lmp_date"]
            if "kinh_cuoi" in du_lieu:
                lmp = _ngay_tuy_chon(du_lieu.get("kinh_cuoi"), "Ngày đầu kỳ kinh cuối")
            nguon = du_lieu.get("nguon_du_kien_sinh", r["edd_nguon"])
            if "du_kien_sinh" in du_lieu and nguon not in NGUON_EDD:
                raise ValidationError("Chọn nguồn của dự kiến sinh.")
            if lmp is not None and edd is not None and edd <= lmp:
                raise ValidationError("Dự kiến sinh phải sau ngày đầu kỳ kinh cuối.")
            nguy_co = bool(du_lieu.get("nguy_co_cao", r["is_high_risk"]))
            ly_do = (
                str(du_lieu.get("ly_do_nguy_co") or "").strip() or None
                if "ly_do_nguy_co" in du_lieu
                else r["high_risk_reason"]
            )
            if nguy_co and not ly_do:
                raise ValidationError("Thai nguy cơ cao thì ghi lý do.")
            ket_cuc = du_lieu.get("ket_cuc")
            ngay_kc: date | None = None
            if ket_cuc is not None:
                if ket_cuc not in KET_CUC:
                    raise ValidationError("Kết cục thai kỳ không hợp lệ.")
                ngay_kc = _ngay_bat_buoc(du_lieu.get("ngay_ket_cuc"), "Ngày kết cục")
            await conn.execute(
                """
                UPDATE pregnancy
                   SET lmp_date = $3, edd_date = $4, edd_nguon = $5,
                       is_high_risk = $6, high_risk_reason = $7,
                       outcome = coalesce($8, outcome),
                       outcome_date = coalesce($9, outcome_date),
                       updated_by = $10::uuid, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                identity.clinic_id,
                pregnancy_id,
                lmp,
                edd,
                nguon,
                nguy_co,
                ly_do,
                ket_cuc,
                ngay_kc,
                identity.staff_id,
            )
            await record_event(
                conn,
                event_type="pregnancy.outcome_set" if ket_cuc else "pregnancy.updated",
                aggregate_type="pregnancy",
                aggregate_id=pregnancy_id,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "truong": sorted(k for k in du_lieu if du_lieu[k] is not None),
                    "ket_cuc": ket_cuc,
                },
            )
        return {"ok": True, "id": pregnancy_id}
