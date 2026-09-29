"""Thai kỳ — bác sĩ tạo, xác nhận và chuyển kết cục trên bảng `pregnancy` sẵn có.

Batch pilot 18/09/2026. Trước đây bảng này không có lối ghi nào trong app: RLS
chỉ-đọc và backend không có lệnh, nên không ai tạo được thai kỳ.

LUẬT (contract Tuyền/ChatGPT 18/09):
  * CHỈ BÁC SĨ (từ 27/09: người có quyền Hoàn tất khám của lego Bàn khám) tạo
    thai kỳ chính thức, xác nhận/sửa dự kiến sinh, chuyển kết
    cục. Lễ tân, thư ký y khoa không tạo/chuyển được — không nới theo công tắc
    mở quyền tạm thời (đây là quyết định chuyên môn).
  * Dự kiến sinh do BÁC SĨ NHẬP kèm NGUỒN. Tuổi thai chỉ là phép trừ từ dự
    kiến sinh đã xác nhận (định nghĩa 280 ngày), hiển thị kèm nhãn nguồn.
  * Một thai kỳ ĐANG THEO DÕI mỗi khách (chỉ mục duy nhất ở Postgres).

TỪ PHIẾU SẢN KHOA v5 (Tuyền 29/09/2026: "dữ liệu phải dùng được thật", GIỮ Y
giao diện bản mẫu): hai ô `sk_lmp` (Kinh lần cuối, gõ tự do) / `sk_edd` (Dự
kiến sinh) của phiếu là chỗ bác sĩ ghi thật, nên lưu phiếu (máy chủ,
`phieu_kham_service`) ghi sang bảng `pregnancy` qua `dong_bo_tu_phieu`:
  * chỉ có kỳ kinh cuối → dự kiến sinh = kinh cuối + 280 ngày, nguồn "Kỳ kinh
    cuối" (quy tắc Tuyền chốt 29/09 — trước đó hệ thống không tự tính);
  * có dự kiến sinh gõ tay → giữ đúng ngày ấy (nguồn "Kỳ kinh cuối" nếu khớp
    kinh cuối + 280, không thì "Khác");
  * ngày rác / dự kiến sinh không sau kinh cuối / tuổi thai ngoài 0–300 ngày
    → BỎ QUA, không ném (phiếu vẫn lưu);
  * đã có thai kỳ đang theo dõi → CẬP NHẬT chính nó (không tạo trùng); dự kiến
    sinh bác sĩ đã xác nhận bằng nguồn khác (siêu âm…) KHÔNG bị kinh cuối đè.
Mở phiếu mà hai ô trống thì điền ngược từ thai kỳ bao trùm ngày khám
(`thai_ky_cua_luot`).

Ngày do người dùng gửi: rác → câu lỗi, không 500 (luật CLAUDE.md).
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import CLINIC_TZ_NAME, now_vn
from clinicai.core.exceptions import SafetyGateError
from clinicai.ho_so.cong_doc import NguCanhHoSo, dong
from clinicai.permissions.can import can
from clinicai.permissions.y_khoa import doc_duoc_y_khoa
from clinicai.services.audit import record_event
from clinicai.services.thu_ky_bac_si import kiem_khach

ORIGIN = "api:thai-ky"
#: Thai kỳ ghi theo hai ô của phiếu Sản khoa v5 (29/09/2026).
ORIGIN_PHIEU = "api:phieu-kham"
NGUON_EDD = {
    "KY_KINH_CUOI": "Kỳ kinh cuối",
    "SIEU_AM": "Siêu âm",
    "KHAC": "Khác",
}
KET_CUC = frozenset({"DELIVERED", "MISCARRIAGE", "TERMINATED", "UNKNOWN"})
#: (Cũ, không còn cửa nào đọc — giữ tên cho bài kiểm cũ.) Từ đợt 3 (27/09/2026)
#: đọc thai kỳ = cửa y khoa chung (`QUYEN_Y_KHOA`), ghi = `QUYEN_GHI_THAI_KY`.
DOC_ROLES = frozenset(
    {
        ClinicRole.DOCTOR,
        ClinicRole.TKYK,
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.NURSE_ULTRASOUND,
    }
)
#: GHI thai kỳ (tạo, xác nhận dự kiến sinh, chuyển kết cục) = người HOÀN TẤT
#: được lượt khám — quyết định chuyên môn của lego Bàn khám (Tuyền 26/09: "khám,
#: chỉ định, kê đơn CHỈ CẦN LEGO"). Thư ký (Bàn khám thiếu Hoàn tất) chỉ đọc.
# 28/09/2026: ghi = quyền GHI BỆNH ÁN (thư ký / điều dưỡng cùng phòng như bác sĩ).
QUYEN_GHI_THAI_KY = "clinical.record.write"


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


#: Định nghĩa thai kỳ đủ tháng: dự kiến sinh = ngày đầu kỳ kinh cuối + 280 ngày.
NGAY_THAI_KY = 280

#: Ghi thai kỳ TỪ PHIẾU KHÁM: người ghi bệnh án, hoặc bác sĩ tư vấn — người
#: được ghi mục B của chính phiếu khám (Tuyền 24/09: "tư vấn ghi vào chính bệnh
#: án"; `phieu_kham_service.QUYEN_GHI_THEM`). Hai ô kinh cuối / dự kiến sinh nằm
#: ở mục B, nên thiếu vế sau thì số tư vấn ghi không bao giờ sang thai kỳ.
QUYEN_GHI_THAI_KY_TU_PHIEU = (QUYEN_GHI_THAI_KY, "clinical.intake.perform")

_NGAY_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_NGAY_VN = re.compile(r"^(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{2}|\d{4})$")


def doc_ngay_tu_do(raw: Any) -> date | None:
    """Ngày GÕ TỰ DO trên phiếu: `YYYY-MM-DD`, `D/M/YYYY`, `D-M-YYYY`,
    `D.M.YYYY`, `D/M/YY` (20YY). Rác / ngày không có thật → None. Không ném."""
    if not isinstance(raw, str):
        return None
    chu = raw.strip()
    try:
        if m := _NGAY_ISO.match(chu):
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if m := _NGAY_VN.match(chu):
            nam = int(m.group(3))
            return date(
                nam + 2000 if nam < 100 else nam, int(m.group(2)), int(m.group(1))
            )
    except ValueError:
        return None
    return None


def thai_ky_tu_phieu(
    kinh_cuoi_raw: Any, du_kien_sinh_raw: Any, hom_nay: date
) -> dict[str, Any] | None:
    """HÀM THUẦN: hai ô phiếu → {lmp, edd, nguon, edd_tu_tinh}, hoặc None nếu
    không có gì dùng được (trống, rác, dự kiến sinh không sau kinh cuối, tuổi
    thai ngoài 0–300 ngày tính tới hôm nay)."""
    lmp = doc_ngay_tu_do(kinh_cuoi_raw)
    edd = doc_ngay_tu_do(du_kien_sinh_raw)
    tu_tinh = False
    if edd is None:
        if lmp is None:
            return None
        edd, tu_tinh = lmp + timedelta(days=NGAY_THAI_KY), True
    if lmp is not None and edd <= lmp:
        return None
    if tuoi_thai_tu_edd(edd, hom_nay) is None:
        return None
    khop_kinh_cuoi = lmp is not None and edd == lmp + timedelta(days=NGAY_THAI_KY)
    return {
        "lmp": lmp,
        "edd": edd,
        "nguon": "KY_KINH_CUOI" if khop_kinh_cuoi else "KHAC",
        "edd_tu_tinh": tu_tinh,
    }


async def dong_bo_tu_phieu(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    *,
    visit_id: str,
    kinh_cuoi_raw: Any,
    du_kien_sinh_raw: Any,
) -> str | None:
    """Ghi hai ô thai kỳ của phiếu sang `pregnancy` — trên giao dịch người gọi.

    Trả "tao" / "cap_nhat" / None (không có gì dùng được, không đổi, không có
    quyền). KHÔNG ném vì dữ liệu: phiếu đã lưu, thai kỳ chỉ đi theo.
    """
    tk = thai_ky_tu_phieu(kinh_cuoi_raw, du_kien_sinh_raw, now_vn().date())
    if tk is None:
        return None
    duoc = [await can(conn, identity, q) for q in QUYEN_GHI_THAI_KY_TU_PHIEU]
    if not any(duoc):
        return None
    cid = identity.clinic_id
    luot = await conn.fetchrow(
        "SELECT v.clinic_patient_id::text AS khach, p.location_id,"
        "       v.attending_doctor_id"
        "  FROM visit v JOIN patient p"
        "    ON p.clinic_id = v.clinic_id"
        "   AND p.clinic_patient_id = v.clinic_patient_id"
        " WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid",
        cid,
        visit_id,
    )
    if luot is None:
        return None
    for _ in range(2):
        cu = await conn.fetchrow(
            "SELECT id::text AS id, lmp_date, edd_date, edd_nguon FROM pregnancy"
            " WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid"
            "   AND outcome = 'ONGOING'"
            " ORDER BY created_at DESC LIMIT 1 FOR UPDATE",
            cid,
            luot["khach"],
        )
        if cu is not None:
            lmp = tk["lmp"] or cu["lmp_date"]
            edd, nguon = tk["edd"], tk["nguon"]
            # Chỉ gõ kinh cuối: dự kiến sinh bác sĩ đã xác nhận bằng nguồn KHÁC
            # (siêu âm, khác) giữ nguyên — kinh cuối không đè siêu âm.
            if (
                tk["edd_tu_tinh"]
                and cu["edd_date"] is not None
                and cu["edd_nguon"] not in (None, "KY_KINH_CUOI")
            ):
                edd, nguon = cu["edd_date"], cu["edd_nguon"]
            if lmp is not None and edd <= lmp:
                return None
            if (lmp, edd, nguon) == (cu["lmp_date"], cu["edd_date"], cu["edd_nguon"]):
                return None
            await conn.execute(
                "UPDATE pregnancy SET lmp_date = $3, edd_date = $4, edd_nguon = $5,"
                " updated_by = $6::uuid, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                cu["id"],
                lmp,
                edd,
                nguon,
                identity.staff_id,
            )
            await record_event(
                conn,
                event_type="pregnancy.updated",
                aggregate_type="pregnancy",
                aggregate_id=cu["id"],
                identity=identity,
                origin=ORIGIN_PHIEU,
                payload={
                    "visit_id": visit_id,
                    "truong": ["du_kien_sinh", "kinh_cuoi"],
                },
            )
            return "cap_nhat"
        try:
            # Điểm lưu riêng: hai người lưu cùng lúc → chỉ mục duy nhất chặn
            # người sau, lùi về điểm lưu rồi CẬP NHẬT thai kỳ vừa tạo.
            async with conn.transaction():
                pid = await conn.fetchval(
                    """
                    INSERT INTO pregnancy
                        (clinic_id, clinic_patient_id, location_id, lmp_date,
                         edd_date, edd_nguon, is_high_risk, primary_doctor_id,
                         created_by, updated_by, xac_nhan_visit_id)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, false,
                            coalesce($7::uuid, $8::uuid), $8::uuid, $8::uuid,
                            $9::uuid)
                    RETURNING id::text
                    """,
                    cid,
                    luot["khach"],
                    luot["location_id"],
                    tk["lmp"],
                    tk["edd"],
                    tk["nguon"],
                    luot["attending_doctor_id"],
                    identity.staff_id,
                    visit_id,
                )
        except asyncpg.UniqueViolationError:
            continue
        await record_event(
            conn,
            event_type="pregnancy.created",
            aggregate_type="pregnancy",
            aggregate_id=str(pid),
            identity=identity,
            origin=ORIGIN_PHIEU,
            payload={"clinic_patient_id": luot["khach"], "visit_id": visit_id},
        )
        return "tao"
    return None


async def thai_ky_cua_luot(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> dict[str, date | None] | None:
    """Thai kỳ BAO TRÙM ngày khám của lượt (để điền ngược hai ô phiếu SK).

    Bắt đầu = kinh cuối (hoặc dự kiến sinh − 280) ≤ ngày khám, và thai kỳ còn
    theo dõi hoặc ngày khám không sau ngày kết cục. Xem lại phiếu năm ngoái
    không bị điền thai kỳ năm nay.
    """
    r = await conn.fetchrow(
        """
        SELECT p.lmp_date, p.edd_date
          FROM visit v
          JOIN pregnancy p
            ON p.clinic_id = v.clinic_id
           AND p.clinic_patient_id = v.clinic_patient_id
          CROSS JOIN LATERAL (
                SELECT (coalesce(v.checked_in_at, v.created_at)
                        AT TIME ZONE $3)::date AS ngay) k
         WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
           AND coalesce(p.lmp_date, p.edd_date - $4::int) <= k.ngay
           AND (p.outcome = 'ONGOING' OR k.ngay <= p.outcome_date)
         ORDER BY p.created_at DESC
         LIMIT 1
        """,
        clinic_id,
        visit_id,
        CLINIC_TZ_NAME,
        NGAY_THAI_KY,
    )
    if r is None:
        return None
    return {"lmp": r["lmp_date"], "edd": r["edd_date"]}


async def _duoc_ghi(pool: asyncpg.Pool, identity: StaffIdentity) -> bool:
    async with pool.acquire() as conn:
        return await can(conn, identity, QUYEN_GHI_THAI_KY)


async def _chi_bac_si(pool: asyncpg.Pool, identity: StaffIdentity) -> None:
    if not await _duoc_ghi(pool, identity):
        raise SafetyGateError("Bạn không có quyền ghi thai kỳ.")


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
        async with self._pool.acquire() as conn:
            if not await doc_duoc_y_khoa(conn, identity):
                raise SafetyGateError("Bạn không có quyền xem khám / kết quả.")
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
            "duoc_ghi": await _duoc_ghi(self._pool, identity),
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
        await _chi_bac_si(self._pool, identity)
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
        await _chi_bac_si(self._pool, identity)
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


# ── CỔNG ĐỌC cho hồ sơ khám (cách B, 24/09/2026 — `ho_so/cong_doc.py`) ──────


async def thai_ky_cho_ho_so(
    conn: asyncpg.Connection, ngu_canh: NguCanhHoSo
) -> dict[str, Any]:
    """Thai kỳ gần nhất của khách (không có → None)."""
    r = await conn.fetchrow(
        """
        SELECT edd_date, gestational_age_at_registration, is_high_risk,
               high_risk_reason, outcome
          FROM pregnancy
         WHERE clinic_patient_id = $1::uuid AND clinic_id = $2::uuid
         ORDER BY created_at DESC LIMIT 1
        """,
        ngu_canh.khach,
        ngu_canh.clinic_id,
    )
    return {"pregnancy": dong(r)}
