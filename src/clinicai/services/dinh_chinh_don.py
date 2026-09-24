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

import hashlib
import json
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
from clinicai.services.thu_ky_bac_si import bac_si_cua_thu_ky, kiem_thu_ky_duoc_lam

LY_DO_NHA_PHAN_LO = "Bác sĩ đính chính đơn"
LY_DO_TOI_THIEU = 5
MAX_PRESCRIPTIONS_PER_AMENDMENT = 100
MAX_DRUG_NAME_LENGTH = 300
MAX_QUANTITY_LENGTH = 100
MAX_DOSAGE_LENGTH = 2000
MAX_CAUTION_LENGTH = 2000

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


def validate_amendment_prescriptions(value: Any) -> list[dict[str, Any]]:
    """Boundary service cho Rx đã ký; không để malformed row bị hiểu là xoá.

    Router có schema tương ứng, nhưng service vẫn phải tự bảo vệ vì test/job có
    thể gọi thẳng và vì đây là ranh giới dữ liệu y khoa.
    """
    if not isinstance(value, list):
        raise ValidationError("Đơn thuốc đính chính phải là một danh sách.")
    if len(value) > MAX_PRESCRIPTIONS_PER_AMENDMENT:
        raise ValidationError("Đơn thuốc đính chính có quá nhiều dòng.")

    allowed = {"id", "drug_catalog_id", "drug_name", "quantity", "dosage", "caution"}
    limits = {
        "drug_name": MAX_DRUG_NAME_LENGTH,
        "quantity": MAX_QUANTITY_LENGTH,
        "dosage": MAX_DOSAGE_LENGTH,
        "caution": MAX_CAUTION_LENGTH,
    }
    validated: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValidationError("Mỗi dòng đơn thuốc đính chính phải là một object.")
        extra = set(item) - allowed
        if extra:
            raise ValidationError("Dòng đơn thuốc đính chính có trường không hợp lệ.")
        name = item.get("drug_name")
        if not isinstance(name, str) or not name.strip():
            raise ValidationError("Tên thuốc đính chính không được để trống.")
        for field_name, limit in limits.items():
            field_value = item.get(field_name)
            if field_value is not None and not isinstance(field_value, str):
                raise ValidationError(f"{field_name} của dòng đơn thuốc phải là chuỗi.")
            if isinstance(field_value, str) and len(field_value) > limit:
                raise ValidationError(
                    f"{field_name} của dòng đơn thuốc vượt độ dài cho phép."
                )
        validated.append({**item, "drug_name": name.strip()})
    return validated


def prescription_fingerprint(rows: list[dict[str, Any]]) -> str:
    """Dấu vân tay nội dung chuyên môn của đơn hiện hành.

    Cố ý không gồm thuốc kho, phân lô, số mua, tiền hay số đã giao: các thao
    tác vận hành đó không được làm stale màn bệnh án của bác sĩ.
    """
    canonical = sorted(
        (
            str(row["id"]),
            _chu(row.get("drug_name_raw")),
            _chu(row.get("quantity")),
            _chu(row.get("dosage_instructions")),
            _chu(row.get("caution")),
        )
        for row in rows
    )
    raw = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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


@dataclass
class KeHoachDonDaKy:
    """Kế hoạch bất biến đủ để ghi snapshot trước khi sửa đơn đã ký."""

    cu: list[dict[str, Any]]
    ke_hoach: KeHoach
    correction_id: str | None
    replacement_ids: dict[str, str]
    addition_ids: dict[int, str]
    original_snapshot: list[dict[str, Any]]
    corrected_snapshot: list[dict[str, Any]]

    @property
    def changed(self) -> bool:
        kh = self.ke_hoach
        return bool(kh.sua_huong_dan or kh.sua_thuoc or kh.thay or kh.bo or kh.them)


def _chu(v: Any) -> str | None:
    s = str(v or "").strip()
    return s or None


def _doi_thuoc(cu: dict[str, Any], moi: dict[str, Any]) -> bool:
    old_catalog = _chu(cu.get("drug_catalog_id"))
    new_catalog = _chu(moi.get("drug_catalog_id"))

    if new_catalog is not None:
        if new_catalog != old_catalog:
            return True
        return _chu(cu.get("quantity")) != _chu(moi.get("quantity"))

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


def _anh_dong(
    *,
    row_id: Any,
    drug_name: Any,
    quantity: Any,
    dosage: Any,
    caution: Any,
    correction_id: str | None = None,
    superseded_by_id: str | None = None,
    replaces_id: str | None = None,
) -> dict[str, Any]:
    snapshot = {
        "id": str(row_id),
        "drug_name": _chu(drug_name),
        "quantity": _chu(quantity),
        "dosage": _chu(dosage),
        "caution": _chu(caution),
    }
    if correction_id is not None:
        snapshot["correction_id"] = correction_id
    if superseded_by_id is not None:
        snapshot["superseded_by_id"] = superseded_by_id
    if replaces_id is not None:
        snapshot["replaces_id"] = replaces_id
    return snapshot


async def chuan_bi_don_da_ky(
    conn: asyncpg.Connection,
    *,
    visit_id: Any,
    clinic_id: str | None,
    prescriptions: list[dict[str, Any]],
    identity: StaffIdentity,
    expected_rx: str,
) -> KeHoachDonDaKy:
    """Khoá và lập kế hoạch đơn đã ký, chưa ghi gì.

    Snapshot được tính trước với UUID đã cấp sẵn, để dòng ``visit_amendment``
    append-only có thể được chèn trước các thay đổi đơn mà trigger yêu cầu.
    """
    await _cho_phep_dinh_chinh(conn, identity=identity, visit_id=visit_id)
    cu = [
        dict(row)
        for row in await conn.fetch(
            """
            SELECT r.id, r.drug_catalog_id, r.drug_name_raw, r.quantity,
                   r.dosage_instructions, r.caution,
                   greatest(public.prescription_muc_dau_vet(r.id, r.clinic_id),
                            CASE WHEN r.dispensed_qty > 0 OR r.closed_at IS NOT NULL
                                   OR r.refusal_reason IS NOT NULL
                                 THEN 2 ELSE 0 END) AS muc
              FROM public.prescription r
             WHERE r.visit_id = $1::uuid AND r.clinic_id = $2::uuid
               AND r.removed_at IS NULL
               -- Chỉ đơn của BÁC SĨ; dòng quầy thêm không thuộc đính chính.
               AND r.nguon = 'BAC_SI'
             ORDER BY r.id
               FOR UPDATE OF r
            """,
            visit_id,
            clinic_id,
        )
    ]
    if prescription_fingerprint(cu) != expected_rx:
        raise DonDaDoiError(
            "Đơn thuốc vừa thay đổi từ lúc bạn mở bệnh án — tải lại rồi đính chính."
        )

    hien_hanh = {str(row["id"]) for row in cu}
    moi = _validated_prescription_items(prescriptions, hien_hanh)
    kh = lap_ke_hoach(cu, moi)
    # Hồ sơ đã ký không được DELETE dòng mức A. Bỏ dòng luôn đi qua correction;
    # sửa tại chỗ mức A/B vẫn giữ đúng semantics 4a/4b và được snapshot đầy đủ.
    kh.bo.extend(kh.xoa)
    kh.xoa = []
    can_correction = bool(kh.thay or kh.bo or kh.them)
    correction_id = str(uuid.uuid4()) if can_correction else None
    replacement_ids = {str(old["id"]): str(uuid.uuid4()) for old, _ in kh.thay}
    addition_ids = {id(item): str(uuid.uuid4()) for item in kh.them}

    thay = {str(old["id"]): item for old, item in kh.thay}
    bo = {str(old["id"]) for old in kh.bo}
    sua = {str(old["id"]): item for old, item in [*kh.sua_huong_dan, *kh.sua_thuoc]}
    original = []
    corrected = []
    for old in cu:
        old_id = str(old["id"])
        original.append(
            _anh_dong(
                row_id=old_id,
                drug_name=old["drug_name_raw"],
                quantity=old["quantity"],
                dosage=old["dosage_instructions"],
                caution=old["caution"],
                correction_id=correction_id if old_id in thay or old_id in bo else None,
                superseded_by_id=replacement_ids.get(old_id),
            )
        )
        if old_id in bo:
            continue
        item = thay.get(old_id) or sua.get(old_id)
        if item is None:
            corrected.append(
                _anh_dong(
                    row_id=old_id,
                    drug_name=old["drug_name_raw"],
                    quantity=old["quantity"],
                    dosage=old["dosage_instructions"],
                    caution=old["caution"],
                )
            )
        else:
            row_id = replacement_ids.get(old_id, old_id)
            corrected.append(
                _anh_dong(
                    row_id=row_id,
                    drug_name=item.get("drug_name"),
                    quantity=item.get("quantity"),
                    dosage=item.get("dosage"),
                    caution=item.get("caution"),
                    correction_id=correction_id if row_id != old_id else None,
                    replaces_id=old_id if row_id != old_id else None,
                )
            )
    for item in kh.them:
        corrected.append(
            _anh_dong(
                row_id=addition_ids[id(item)],
                drug_name=item.get("drug_name"),
                quantity=item.get("quantity"),
                dosage=item.get("dosage"),
                caution=item.get("caution"),
                correction_id=correction_id,
            )
        )
    original.sort(key=lambda row: row["id"])
    corrected.sort(key=lambda row: row["id"])
    return KeHoachDonDaKy(
        cu=cu,
        ke_hoach=kh,
        correction_id=correction_id,
        replacement_ids=replacement_ids,
        addition_ids=addition_ids,
        original_snapshot=original,
        corrected_snapshot=corrected,
    )


async def ap_dung_don_da_ky(
    conn: asyncpg.Connection,
    *,
    plan: KeHoachDonDaKy,
    amendment_id: str,
    visit_id: Any,
    clinic_id: str | None,
    clinic_patient_id: str,
    created_by: str,
    identity: StaffIdentity,
    reason: str,
) -> dict[str, Any]:
    """Ghi kế hoạch đã ký sau khi visit_amendment + SET LOCAL đã có."""
    kh = plan.ke_hoach
    lan = plan.correction_id
    if lan is not None:
        go_ids = [str(row["id"]) for row, _ in kh.thay] + [
            str(row["id"]) for row in kh.bo
        ]
        if go_ids:
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
                   SET released_at = now(), released_by = $3::uuid,
                       release_reason = $4
                 WHERE clinic_id = $1::uuid
                   AND prescription_id = ANY($2::uuid[])
                   AND released_at IS NULL AND payment_cycle_id IS NULL
                """,
                clinic_id,
                go_ids,
                identity.staff_id,
                LY_DO_NHA_PHAN_LO,
            )
        await conn.execute(
            """
            INSERT INTO public.prescription_correction
                (id, clinic_id, visit_id, corrected_by, reason, amendment_id)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6::uuid)
            """,
            lan,
            clinic_id,
            visit_id,
            identity.staff_id,
            reason,
            amendment_id,
        )

    for old, item in kh.sua_huong_dan:
        await conn.execute(
            "UPDATE prescription SET dosage_instructions = $3, caution = $4,"
            " updated_at = now() WHERE id = $1::uuid AND clinic_id = $2::uuid",
            old["id"],
            clinic_id,
            _chu(item.get("dosage")),
            _chu(item.get("caution")),
        )
    for old, item in kh.sua_thuoc:
        catalog_id = await _ma_kho(conn, clinic_id=clinic_id, item=item)
        catalog_name = await _ten_thuoc_catalog(
            conn,
            clinic_id=clinic_id,
            drug_catalog_id=catalog_id,
        )
        drug_name = catalog_name or _chu(item.get("drug_name"))
        await conn.execute(
            """
            UPDATE prescription
               SET drug_name_raw = $3, quantity = $4,
                   quantity_num = public.so_luong_tu_van_ban($4),
                   unit = public.don_vi_tu_van_ban($4),
                   dosage_instructions = $5, caution = $6,
                   drug_catalog_id = $7::uuid,
                   drug_mapped_by =
                       CASE WHEN $7::uuid IS NULL THEN NULL ELSE $8::uuid END,
                   drug_mapped_at =
                       CASE WHEN $7::uuid IS NULL THEN NULL ELSE now() END,
                   purchased_qty = NULL, updated_at = now()
             WHERE id = $1::uuid AND clinic_id = $2::uuid
            """,
            old["id"],
            clinic_id,
            drug_name,
            _chu(item.get("quantity")),
            _chu(item.get("dosage")),
            _chu(item.get("caution")),
            catalog_id,
            created_by,
        )
    for old, item in kh.thay:
        new_id = plan.replacement_ids[str(old["id"])]
        await _chen(
            conn,
            visit_id=visit_id,
            clinic_id=clinic_id,
            clinic_patient_id=clinic_patient_id,
            item=item,
            created_by=created_by,
            lan=lan,
            row_id=new_id,
        )
        await conn.execute(
            "UPDATE prescription SET removed_in_correction_id = $3::uuid,"
            " superseded_by_id = $4::uuid"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            old["id"],
            clinic_id,
            lan,
            new_id,
        )
    for old in kh.bo:
        await conn.execute(
            "UPDATE prescription SET removed_in_correction_id = $3::uuid"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            old["id"],
            clinic_id,
            lan,
        )
    for item in kh.them:
        await _chen(
            conn,
            visit_id=visit_id,
            clinic_id=clinic_id,
            clinic_patient_id=clinic_patient_id,
            item=item,
            created_by=created_by,
            lan=lan,
            row_id=plan.addition_ids[id(item)],
        )
    # Mọi thay đổi Rx của hồ sơ đã ký đều có event, kể cả sửa tại chỗ A/B
    # (correction_id khi đó là NULL). Nội dung thuốc/liều và lý do tự do không
    # chép sang event_log; amendment là nguồn có RLS để tra chi tiết.
    await record_event(
        conn,
        event_type="prescription.corrected",
        aggregate_type="visit",
        aggregate_id=str(visit_id),
        identity=identity,
        origin="api:clinical-amendment",
        correlation_id=amendment_id,
        payload={
            "amendment_id": amendment_id,
            "correction_id": lan,
            "so_dong_thay": len(kh.thay),
            "so_dong_bo": len(kh.bo),
            "so_dong_them": len(kh.them),
        },
    )
    return {
        "correction_id": lan,
        "so_dong_thay": len(kh.thay),
        "so_dong_bo": len(kh.bo),
        "so_dong_them": len(kh.them),
    }


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
            SELECT r.id, r.drug_catalog_id, r.drug_name_raw, r.quantity,
                   r.dosage_instructions, r.caution,
                   -- Mức do DB tính; cột của chính dòng (đã cấp / chốt /
                   -- khách không lấy) tính lại tại chỗ cho chắc.
                   greatest(public.prescription_muc_dau_vet(r.id, r.clinic_id),
                            CASE WHEN r.dispensed_qty > 0 OR r.closed_at IS NOT NULL
                                   OR r.refusal_reason IS NOT NULL
                                 THEN 2 ELSE 0 END) AS muc
              FROM prescription r
             WHERE r.visit_id = $1::uuid AND r.clinic_id = $2::uuid
               AND r.removed_at IS NULL
               -- Dòng QUẦY thêm (24/09/2026) không thuộc đơn bác sĩ: không so,
               -- không coi là "bị xoá" khi bác sĩ lưu lại đơn.
               AND r.nguon = 'BAC_SI'
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
        catalog_id = await _ma_kho(conn, clinic_id=clinic_id, item=m)
        catalog_name = await _ten_thuoc_catalog(
            conn,
            clinic_id=clinic_id,
            drug_catalog_id=catalog_id,
        )
        drug_name = catalog_name or _chu(m.get("drug_name"))
        await conn.execute(
            """
            UPDATE prescription
               SET drug_name_raw = $3, quantity = $4,
                   quantity_num = public.so_luong_tu_van_ban($4),
                   unit = public.don_vi_tu_van_ban($4),
                   dosage_instructions = $5, caution = $6,
                   drug_catalog_id = $7::uuid,
                   drug_mapped_by =
                       CASE WHEN $7::uuid IS NULL THEN NULL ELSE $8::uuid END,
                   drug_mapped_at =
                       CASE WHEN $7::uuid IS NULL THEN NULL ELSE now() END,
                   purchased_qty = NULL, updated_at = now()
             WHERE id = $1::uuid AND clinic_id = $2::uuid
            """,
            r["id"],
            clinic_id,
            drug_name,
            _chu(m.get("quantity")),
            _chu(m.get("dosage")),
            _chu(m.get("caution")),
            catalog_id,
            created_by,
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
        "so_dong_them": len(kh.them),
        "so_dong_sua": len(kh.sua_huong_dan) + len(kh.sua_thuoc),
        "so_dong_xoa": len(kh.xoa),
    }


async def _ma_kho(
    conn: asyncpg.Connection, *, clinic_id: str | None, item: dict[str, Any]
) -> str | None:
    """Mã thuốc KHO của một dòng đơn — không bao giờ để "chưa gắn kho".

    Tuyền 24/09/2026: "kho thuốc chỉ tập trung 1 kho, thuốc quy chuẩn về, đừng
    đẻ cái kiểu chưa gắn kho". Màn gửi mã thì dùng mã. Không có mã (thuốc mẫu
    của phiếu chưa có dòng ghép, hay tên gõ tay) → tìm theo TÊN trùng khít
    trong danh mục; vẫn không có → THÊM vào danh mục kho, đánh dấu cần soát
    (`needs_review`) để dược sĩ nhập giá. Một kho, một danh mục.
    """
    ma = _chu(item.get("drug_catalog_id"))
    if ma is not None or clinic_id is None:
        return ma
    ten = " ".join((_chu(item.get("drug_name")) or "").split())
    if not ten:
        return None
    co = await conn.fetchval(
        "SELECT id::text FROM public.drug_catalog WHERE clinic_id = $1::uuid"
        " AND is_active"
        " AND (lower(name_raw) = lower($2) OR lower(name_base) = lower($2))"
        " ORDER BY created_at, id LIMIT 1",
        clinic_id,
        ten,
    )
    if co is not None:
        return str(co)
    # Chỉ thêm khi phòng khám có thật (bài kiểm SQL dùng mã phòng khám giả
    # trên bảng tạm — không có thì giữ như cũ: dòng chưa gắn mã).
    moi = await conn.fetchval(
        "INSERT INTO public.drug_catalog (clinic_id, name_raw, name_base, needs_review)"
        " SELECT $1::uuid, $2, $2, true"
        " WHERE EXISTS (SELECT 1 FROM public.clinic WHERE id = $1::uuid)"
        " ON CONFLICT (clinic_id, name_raw) DO UPDATE SET is_active = true"
        " RETURNING id::text",
        clinic_id,
        ten,
    )
    return str(moi) if moi else None


async def _ten_thuoc_catalog(
    conn: asyncpg.Connection,
    *,
    clinic_id: str | None,
    drug_catalog_id: Any,
) -> str | None:
    if drug_catalog_id is None:
        return None

    row = await conn.fetchrow(
        """
        SELECT name_raw
          FROM public.drug_catalog
         WHERE id = $1::uuid
           AND clinic_id = $2::uuid
        """,
        str(drug_catalog_id),
        clinic_id,
    )

    if row is None:
        raise ValidationError("Thuốc đã chọn không thuộc danh mục của phòng khám này.")

    return str(row["name_raw"]).strip()


async def _chen(
    conn: asyncpg.Connection,
    *,
    visit_id: Any,
    clinic_id: str | None,
    clinic_patient_id: str,
    item: dict[str, Any],
    created_by: str | None,
    lan: str | None,
    row_id: str | None = None,
) -> Any:
    # Dòng THAY THẾ của lần đính chính phải bắt đầu trống (trigger
    # prescription_dinh_chinh_guard) — chỉ tự gắn thuốc kho cho dòng thường.
    catalog_id = (
        await _ma_kho(conn, clinic_id=clinic_id, item=item)
        if lan is None
        else _chu(item.get("drug_catalog_id"))
    )
    catalog_name = await _ten_thuoc_catalog(
        conn,
        clinic_id=clinic_id,
        drug_catalog_id=catalog_id,
    )
    drug_name = catalog_name or _chu(item.get("drug_name"))

    return await conn.fetchval(
        """
        INSERT INTO prescription (
            id, source_ref, clinic_patient_id, visit_id, drug_name_raw,
            quantity, dosage_instructions, caution, clinic_id,
            quantity_num, unit, created_by, created_in_correction_id,
            drug_catalog_id, drug_mapped_by, drug_mapped_at
        )
        VALUES ($1::uuid, $2, $3::uuid, $4::uuid, $5, $6, $7, $8, $9::uuid,
                public.so_luong_tu_van_ban($6),
                public.don_vi_tu_van_ban($6), $10::uuid, $11::uuid,
                $12::uuid,
                CASE WHEN $12::uuid IS NULL THEN NULL ELSE $10::uuid END,
                CASE WHEN $12::uuid IS NULL THEN NULL ELSE now() END)
        RETURNING id
        """,
        row_id or str(uuid.uuid4()),
        # source_ref duy nhất theo dòng (uuid), không theo vị trí.
        f"dash-rx-{visit_id}-{uuid.uuid4().hex}",
        clinic_patient_id,
        str(visit_id),
        drug_name,
        _chu(item.get("quantity")),
        _chu(item.get("dosage")),
        _chu(item.get("caution")),
        clinic_id,
        created_by,
        lan,
        catalog_id,
    )


async def _cho_phep_dinh_chinh(
    conn: asyncpg.Connection, *, identity: StaffIdentity | None, visit_id: Any
) -> None:
    # Thư ký y khoa = bác sĩ về đơn thuốc (Tuyền chốt 24/09/2026) — thư ký của
    # CHÍNH bác sĩ chính của lượt đính chính được như bác sĩ.
    if identity is None or not identity.co_vai({ClinicRole.DOCTOR, ClinicRole.TKYK}):
        raise SafetyGateError(
            "Chỉ bác sĩ chính của lượt (hoặc thư ký của bác sĩ ấy) mới đính chính"
            " được dòng đơn nhà thuốc / thu ngân đã đụng tới."
        )
    chinh = await conn.fetchval(
        "SELECT attending_doctor_id::text FROM public.visit"
        " WHERE visit_id = $1::uuid AND clinic_id = $2::uuid",
        visit_id,
        identity.clinic_id,
    )
    if identity.co_vai({ClinicRole.TKYK}) and not identity.co_vai({ClinicRole.DOCTOR}):
        kiem_thu_ky_duoc_lam(await bac_si_cua_thu_ky(conn, identity), chinh)
        return
    if chinh is not None and chinh != identity.staff_id:
        # Đính chính chéo bác sĩ: HOLD Dr4Women — mặc định từ chối.
        raise SafetyGateError(
            "Lượt này của bác sĩ khác — chỉ bác sĩ chính của lượt đính chính đơn."
        )
