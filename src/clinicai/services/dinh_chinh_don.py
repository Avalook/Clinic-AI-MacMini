"""Lưu đơn thuốc CHƯA KÝ theo mức dấu vết (contract tiền–thuốc CP6 bước 4b).

Bác sĩ gửi TOÀN BỘ đơn đang thấy mỗi lần Lưu bệnh án. Máy chủ so với các dòng
HIỆN HÀNH (removed_at IS NULL), đã khoá, và quyết từng dòng theo mức dấu vết do
DB tính (`prescription_muc_dau_vet`, migration 20260920000002):

    A  chưa ai đụng        → sửa tại chỗ, giữ id; đổi thuốc / số lượng thì xoá
                             thuốc kho + số mua (nhà thuốc xác định lại); bỏ
                             dòng thì xoá cứng.
    B  chỉ có phân lô      → đổi liều / lưu ý tại chỗ, GIỮ phân lô; đổi thuốc /
                             số lượng hay bỏ dòng là ĐÍNH CHÍNH.
    C  đã thu / bán / giao / trả / chốt / khách không lấy
                           → mọi thay đổi chuyên môn, kể cả liều, là ĐÍNH CHÍNH.

ĐÍNH CHÍNH = một dòng `prescription_correction` (lý do, bác sĩ, lúc), dòng cũ
gỡ khỏi đơn hiện hành và ở lại làm lịch sử, dòng thay thế id mới (không kế thừa
thuốc kho, số mua, phân lô). Phân lô CHƯA gắn lần thu của dòng bị gỡ được nhả
với lý do "Bác sĩ đính chính đơn"; phân lô đã gắn lần thu, tiền, sổ kho của dòng
cũ giữ nguyên — đối soát riêng (CP5). Bác sĩ KHÔNG phải huỷ phiếu hay hoàn tiền
trước.

Ai được đính chính (review 4 Q4, 20/09/2026): bác sĩ có quyền trên bệnh án
chính của lượt — vai Bác sĩ, và là bác sĩ chính của lượt (hoặc lượt chưa có).
Vai bác sĩ siêu âm đơn thuần không đủ. Đính chính chéo bác sĩ: HOLD Dr4Women,
mặc định từ chối. Thư ký chỉ nhập nháp; bác sĩ duyệt nháp mà đụng dòng có dấu
vết thì cũng phải ghi lý do.

Hồ sơ ĐÃ KÝ không đi đường này (`_writable_visit` từ chối; DB chặn) — đường
đính chính hồ sơ là bước 4c.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.audit import record_event
from clinicai.services.clinical_prescription_service import (
    _prescription_key,
    _validated_prescription_items,
)

LY_DO_NHA_PHAN_LO = "Bác sĩ đính chính đơn"
LY_DO_TOI_THIEU = 5

MUC_A, MUC_B, MUC_C = 0, 1, 2
NHAN_MUC = {
    MUC_B: "nhà thuốc đã chọn lô",
    MUC_C: "đã thu tiền / bán / giao / chốt",
}


class CanLyDoDinhChinhError(ConflictError):
    """Lưu đơn mà đụng dòng có dấu vết: phải ghi lý do đính chính (409)."""

    error_code = "PRESCRIPTION_CORRECTION_REASON_REQUIRED"


class DonDaDoiError(ConflictError):
    """Dòng gửi lên đã bị đính chính / đổi từ lúc bác sĩ mở bệnh án (409)."""

    error_code = "PRESCRIPTION_CHANGED"


# ── Kế hoạch: hàm thuần ──────────────────────────────────────────────────


@dataclass
class KeHoach:
    """Việc phải làm với đơn — mỗi danh sách là (dòng cũ, bản gửi lên)."""

    sua_huong_dan: list[tuple[dict[str, Any], dict[str, Any]]] = field(
        default_factory=list
    )
    sua_thuoc: list[tuple[dict[str, Any], dict[str, Any]]] = field(default_factory=list)
    xoa: list[dict[str, Any]] = field(default_factory=list)
    thay: list[tuple[dict[str, Any], dict[str, Any]]] = field(default_factory=list)
    bo: list[dict[str, Any]] = field(default_factory=list)
    them: list[dict[str, Any]] = field(default_factory=list)

    @property
    def can_dinh_chinh(self) -> bool:
        return bool(self.thay or self.bo)


def _chu(v: Any) -> str | None:
    s = str(v or "").strip()
    return s or None


def _doi_thuoc(cu: dict[str, Any], moi: dict[str, Any]) -> bool:
    return _prescription_key(cu["drug_name_raw"], cu["quantity"]) != _prescription_key(
        moi.get("drug_name"), moi.get("quantity")
    )


def _doi_huong_dan(cu: dict[str, Any], moi: dict[str, Any]) -> bool:
    return _chu(cu["dosage_instructions"]) != _chu(moi.get("dosage")) or _chu(
        cu["caution"]
    ) != _chu(moi.get("caution"))


def ghep_dong(
    cu: list[dict[str, Any]], moi: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, Any] | None], list[dict[str, Any]]]:
    """Ghép bản gửi lên với dòng hiện hành: theo id; bản cũ thiếu id chỉ ghép
    khi tên + số lượng khớp DUY NHẤT một dòng và một bản gửi (không đoán)."""
    theo_id = {m["id"]: m for m in moi if m["id"] is not None}
    ghep: dict[str, dict[str, Any] | None] = {}
    da_dung: set[int] = {id(m) for m in theo_id.values()}
    for r in cu:
        m = theo_id.get(str(r["id"]))
        if m is None:
            khoa = _prescription_key(r["drug_name_raw"], r["quantity"])
            ung = [
                c
                for c in moi
                if c["id"] is None
                and id(c) not in da_dung
                and _prescription_key(c.get("drug_name"), c.get("quantity")) == khoa
            ]
            trung = sum(
                _prescription_key(x["drug_name_raw"], x["quantity"]) == khoa for x in cu
            )
            if len(ung) == 1 and trung == 1:
                m = ung[0]
            elif ung and r["muc"] > MUC_A:
                raise ValidationError(
                    "Đơn thuốc cũ có dòng trùng tên và số lượng — "
                    "tải lại bệnh án để lấy mã dòng trước khi lưu"
                )
        if m is not None:
            da_dung.add(id(m))
        ghep[str(r["id"])] = m
    them = [m for m in moi if id(m) not in da_dung]
    return ghep, them


def lap_ke_hoach(cu: list[dict[str, Any]], moi: list[dict[str, Any]]) -> KeHoach:
    """Quyết từng dòng theo mức dấu vết. `cu`: dòng hiện hành kèm `muc`."""
    ghep, them = ghep_dong(cu, moi)
    kh = KeHoach(them=them)
    for r in cu:
        m = ghep[str(r["id"])]
        muc = int(r["muc"])
        if m is None:
            (kh.xoa.append(r) if muc == MUC_A else kh.bo.append(r))
            continue
        doi_thuoc = _doi_thuoc(r, m)
        doi_hd = _doi_huong_dan(r, m)
        if not (doi_thuoc or doi_hd):
            continue
        if muc == MUC_A:
            (kh.sua_thuoc if doi_thuoc else kh.sua_huong_dan).append((r, m))
        elif muc == MUC_B and not doi_thuoc:
            kh.sua_huong_dan.append((r, m))
        else:
            kh.thay.append((r, m))
    return kh


# ── Ghi ──────────────────────────────────────────────────────────────────


async def luu_don_chua_ky(
    conn: asyncpg.Connection,
    *,
    visit_id: Any,
    clinic_id: str | None,
    clinic_patient_id: str,
    prescriptions: list[dict[str, Any]],
    created_by: str | None,
    identity: StaffIdentity | None,
    ly_do: str | None,
) -> dict[str, Any]:
    """Người gọi ĐÃ khoá `visit` (thứ tự khoá: visit → prescription →
    prescription_allocation). Trả tóm tắt việc đã làm."""
    cu = [
        dict(r)
        for r in await conn.fetch(
            """
            SELECT r.id, r.drug_name_raw, r.quantity, r.dosage_instructions,
                   r.caution,
                   -- Mức do DB tính; cột của chính dòng (đã cấp / chốt /
                   -- khách không lấy) tính lại tại chỗ cho chắc.
                   greatest(public.prescription_muc_dau_vet(r.id, r.clinic_id),
                            CASE WHEN r.dispensed_qty > 0 OR r.closed_at IS NOT NULL
                                   OR r.refusal_reason IS NOT NULL
                                 THEN 2 ELSE 0 END) AS muc
              FROM prescription r
             WHERE r.visit_id = $1::uuid AND r.clinic_id = $2::uuid
               AND r.removed_at IS NULL
             ORDER BY r.id
               FOR UPDATE OF r
            """,
            visit_id,
            clinic_id,
        )
    ]
    hien_hanh = {str(r["id"]) for r in cu}
    gui_id = {str(p["id"]) for p in prescriptions if p.get("id") is not None}
    if gui_id - hien_hanh:
        da_go = await conn.fetchval(
            """
            SELECT count(*) FROM prescription r
             WHERE r.visit_id = $1::uuid AND r.clinic_id = $2::uuid
               AND r.id::text = ANY($3::text[])
               -- rx:gom-ca-lich-su: nhận ra id đã bị gỡ (removed_at) để báo "tải lại"
               AND r.removed_at IS NOT NULL
            """,
            visit_id,
            clinic_id,
            sorted(gui_id - hien_hanh),
        )
        if da_go:
            raise DonDaDoiError(
                "Đơn thuốc vừa được đính chính từ lúc bạn mở bệnh án — tải lại "
                "để xem đơn hiện hành rồi lưu."
            )
    moi = _validated_prescription_items(prescriptions, hien_hanh)
    kh = lap_ke_hoach(cu, moi)

    lan: str | None = None
    if kh.can_dinh_chinh:
        await _cho_phep_dinh_chinh(conn, identity=identity, visit_id=visit_id)
        ly = (ly_do or "").strip()
        if len(ly) < LY_DO_TOI_THIEU:
            dong = [r for r, _ in kh.thay] + kh.bo
            raise CanLyDoDinhChinhError(
                "Sửa hoặc bỏ dòng đã có nhà thuốc / thu ngân đụng tới là ĐÍNH "
                "CHÍNH đơn — ghi lý do (tối thiểu 5 ký tự). Dòng cũ giữ làm lịch "
                "sử; tiền / thuốc cũ đối soát riêng, không cần huỷ phiếu hay hoàn "
                "tiền trước. Dòng: "
                + "; ".join(
                    f"“{r['drug_name_raw']}” ({NHAN_MUC[int(r['muc'])]})" for r in dong
                )
            )
        assert identity is not None
        go_ids = [str(r["id"]) for r, _ in kh.thay] + [str(r["id"]) for r in kh.bo]
        # Kế hoạch lô CHƯA gắn lần thu: nhả. Đã gắn lần thu: giữ (đối soát).
        await conn.execute(
            """
            SELECT 1 FROM public.prescription_allocation
             WHERE clinic_id = $1::uuid AND prescription_id = ANY($2::uuid[])
             ORDER BY id FOR UPDATE
            """,
            clinic_id,
            go_ids,
        )
        await conn.execute(
            """
            UPDATE public.prescription_allocation
               SET released_at = now(), released_by = $3::uuid, release_reason = $4
             WHERE clinic_id = $1::uuid AND prescription_id = ANY($2::uuid[])
               AND released_at IS NULL AND payment_cycle_id IS NULL
            """,
            clinic_id,
            go_ids,
            identity.staff_id,
            LY_DO_NHA_PHAN_LO,
        )
        lan = str(
            await conn.fetchval(
                """
                INSERT INTO public.prescription_correction
                    (clinic_id, visit_id, corrected_by, reason)
                VALUES ($1::uuid, $2::uuid, $3::uuid, $4)
                RETURNING id
                """,
                clinic_id,
                visit_id,
                identity.staff_id,
                ly,
            )
        )

    for r, m in kh.sua_huong_dan:
        await conn.execute(
            "UPDATE prescription SET dosage_instructions = $3, caution = $4,"
            " updated_at = now() WHERE id = $1::uuid AND clinic_id = $2::uuid",
            r["id"],
            clinic_id,
            _chu(m.get("dosage")),
            _chu(m.get("caution")),
        )
    for r, m in kh.sua_thuoc:
        # Mức A: nhà thuốc chưa làm gì ngoài (có thể) xác định thuốc kho — đổi
        # thuốc thì xác định lại từ đầu.
        await conn.execute(
            """
            UPDATE prescription
               SET drug_name_raw = $3, quantity = $4,
                   quantity_num = public.so_luong_tu_van_ban($4),
                   unit = public.don_vi_tu_van_ban($4),
                   dosage_instructions = $5, caution = $6,
                   drug_catalog_id = NULL, drug_mapped_by = NULL,
                   drug_mapped_at = NULL, purchased_qty = NULL, updated_at = now()
             WHERE id = $1::uuid AND clinic_id = $2::uuid
            """,
            r["id"],
            clinic_id,
            _chu(m.get("drug_name")),
            _chu(m.get("quantity")),
            _chu(m.get("dosage")),
            _chu(m.get("caution")),
        )
    if kh.xoa:
        await conn.execute(
            "DELETE FROM prescription WHERE clinic_id = $1::uuid"
            " AND id = ANY($2::uuid[]) AND removed_at IS NULL",
            clinic_id,
            [r["id"] for r in kh.xoa],
        )
    for r, m in kh.thay:
        moi_id = await _chen(
            conn,
            visit_id=visit_id,
            clinic_id=clinic_id,
            clinic_patient_id=clinic_patient_id,
            item=m,
            created_by=created_by,
            lan=lan,
        )
        await conn.execute(
            "UPDATE prescription SET removed_in_correction_id = $3::uuid,"
            " superseded_by_id = $4::uuid WHERE id = $1::uuid AND clinic_id = $2::uuid",
            r["id"],
            clinic_id,
            lan,
            moi_id,
        )
    for r in kh.bo:
        await conn.execute(
            "UPDATE prescription SET removed_in_correction_id = $3::uuid"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            r["id"],
            clinic_id,
            lan,
        )
    for m in kh.them:
        await _chen(
            conn,
            visit_id=visit_id,
            clinic_id=clinic_id,
            clinic_patient_id=clinic_patient_id,
            item=m,
            created_by=created_by,
            lan=None,
        )

    if lan is not None and identity is not None:
        # Sự kiện tối thiểu: nội dung đơn nằm ở bảng đơn, không chép vào log.
        await record_event(
            conn,
            event_type="prescription.corrected",
            aggregate_type="visit",
            aggregate_id=str(visit_id),
            identity=identity,
            origin="api:clinical-record",
            payload={
                "correction_id": lan,
                "so_dong_thay": len(kh.thay),
                "so_dong_bo": len(kh.bo),
            },
        )
    return {
        "correction_id": lan,
        "so_dong_thay": len(kh.thay),
        "so_dong_bo": len(kh.bo),
    }


async def _chen(
    conn: asyncpg.Connection,
    *,
    visit_id: Any,
    clinic_id: str | None,
    clinic_patient_id: str,
    item: dict[str, Any],
    created_by: str | None,
    lan: str | None,
) -> Any:
    return await conn.fetchval(
        """
        INSERT INTO prescription (
            source_ref, clinic_patient_id, visit_id, drug_name_raw,
            quantity, dosage_instructions, caution, clinic_id,
            quantity_num, unit, created_by, created_in_correction_id
        )
        VALUES ($1, $2::uuid, $3::uuid, $4, $5, $6, $7, $8::uuid,
                public.so_luong_tu_van_ban($5),
                public.don_vi_tu_van_ban($5), $9::uuid, $10::uuid)
        RETURNING id
        """,
        # source_ref duy nhất theo dòng (uuid), không theo vị trí.
        f"dash-rx-{visit_id}-{uuid.uuid4().hex}",
        clinic_patient_id,
        str(visit_id),
        _chu(item.get("drug_name")),
        _chu(item.get("quantity")),
        _chu(item.get("dosage")),
        _chu(item.get("caution")),
        clinic_id,
        created_by,
        lan,
    )


async def _cho_phep_dinh_chinh(
    conn: asyncpg.Connection, *, identity: StaffIdentity | None, visit_id: Any
) -> None:
    if identity is None or not identity.co_vai({ClinicRole.DOCTOR}):
        raise SafetyGateError(
            "Chỉ bác sĩ chính của lượt mới đính chính được dòng đơn nhà thuốc / "
            "thu ngân đã đụng tới."
        )
    chinh = await conn.fetchval(
        "SELECT attending_doctor_id::text FROM public.visit"
        " WHERE visit_id = $1::uuid AND clinic_id = $2::uuid",
        visit_id,
        identity.clinic_id,
    )
    if chinh is not None and chinh != identity.staff_id:
        # Đính chính chéo bác sĩ: HOLD Dr4Women — mặc định từ chối.
        raise SafetyGateError(
            "Lượt này của bác sĩ khác — chỉ bác sĩ chính của lượt đính chính đơn."
        )
