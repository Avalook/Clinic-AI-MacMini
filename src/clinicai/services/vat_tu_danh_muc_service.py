"""Whitelist riêng cho thuộc tính vật tư; không thay điều kiện bán hiện tại."""

import uuid
from decimal import Decimal, DecimalException
from typing import Any

import asyncpg

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.audit import record_event

COT_VAT_TU = {
    "loai_vat_tu": "loai_vat_tu",
    "gia_nhap": "gia_nhap_vat_tu",
    "ma_vach": "ma_vach_vat_tu",
    "don_vi": "don_vi",
    "kinh_doanh": "kinh_doanh_vat_tu",
    "can_duyet_nhap": "can_duyet_nhap_vat_tu",
    "can_ql_duyet": "can_ql_duyet",
    "chon_nhanh": "chon_nhanh",
}


def patch_vat_tu(raw: dict[str, Any]) -> dict[str, Any]:
    """Giữ null để xoá ô tuỳ chọn; số rác/âm/phần lẻ không ghi dữ liệu."""
    if set(raw) - set(COT_VAT_TU):
        raise ValidationError("Thuộc tính vật tư không hợp lệ.")
    patch: dict[str, Any] = {}
    for ten, v in raw.items():
        if ten in {"kinh_doanh", "can_duyet_nhap", "can_ql_duyet", "chon_nhanh"}:
            if not isinstance(v, bool):
                raise ValidationError("Cờ vật tư phải là bật hoặc tắt.")
        elif ten == "gia_nhap":
            if v is None or v == "":
                v = None
            else:
                try:
                    so = Decimal(str(v))
                    if (
                        not so.is_finite()
                        or so < 0
                        or so >= Decimal("1e12")
                        or so != so.to_integral_value()
                    ):
                        raise ValidationError(
                            "Giá nhập phải là số đồng nguyên không âm."
                        )
                    v = int(so)
                except (DecimalException, ValueError, TypeError) as exc:
                    raise ValidationError("Giá nhập không hợp lệ.") from exc
        else:
            if v is not None and not isinstance(v, str):
                raise ValidationError("Thuộc tính vật tư phải là chữ.")
            v = v.strip() or None if isinstance(v, str) else None
            if ten == "loai_vat_tu" and v not in {None, "VPP", "VTYT"}:
                raise ValidationError("Chọn Văn phòng phẩm hoặc Vật tư y tế.")
            if v is not None and len(v) > (40 if ten == "don_vi" else 120):
                raise ValidationError("Thuộc tính vật tư quá dài.")
        patch = {**patch, COT_VAT_TU[ten]: v}
    return patch


# ── Đặt cờ HÀNG LOẠT theo loại vật tư (Kho vật tư → Danh mục) ────────────────────

#: Loại nhận từ màn → giá trị cột `loai_vat_tu`. "Chưa phân loại" là NULL trong DB
#: nên màn gửi một chữ riêng, không gửi rỗng (rỗng/thiếu là lỗi đầu vào).
LOAI_HANG_LOAT: dict[str, str | None] = {
    "VPP": "VPP",
    "VTYT": "VTYT",
    "CHUA_PHAN_LOAI": None,
}

#: Cờ được đặt hàng loạt → cột. Chỉ ba cờ phân loại/duyệt; "Chọn nhanh" và "Đang bán"
#: (`active`) KHÔNG nằm ở đây — đổi chúng là đổi cách bán, làm từng món.
CO_HANG_LOAT: dict[str, str] = {
    "kinh_doanh": "kinh_doanh_vat_tu",
    "can_ql_duyet": "can_ql_duyet",
    "can_duyet_nhap": "can_duyet_nhap_vat_tu",
}

_TOI_DA_ID = 2000


def kiem_hang_loat(
    loai: Any, co: Any, bat: Any, ids: Any = None
) -> tuple[str | None, str, bool, list[str] | None]:
    """Đầu vào rác (loại / cờ lạ, bật-tắt không phải bool, id sai) → 422, không 500.

    Trả `(giá trị loai_vat_tu, tên cột, bật?, ids|None)`.
    """
    if not isinstance(loai, str) or loai not in LOAI_HANG_LOAT:
        raise ValidationError(
            "Chọn loại: Văn phòng phẩm, Vật tư y tế hoặc Chưa phân loại."
        )
    if not isinstance(co, str) or co not in CO_HANG_LOAT:
        raise ValidationError(
            "Chọn cờ: Được kinh doanh, Cần QL duyệt bán hoặc Cần duyệt nhập."
        )
    if not isinstance(bat, bool):
        raise ValidationError("Chọn Bật hoặc Tắt.")
    sach: list[str] | None = None
    if ids is not None:
        if not isinstance(ids, list) or len(ids) > _TOI_DA_ID:
            raise ValidationError("Danh sách vật tư không hợp lệ.")
        try:
            sach = [str(uuid.UUID(str(i))) for i in ids]
        except ValueError as exc:
            raise ValidationError("Mã vật tư không hợp lệ.") from exc
    return LOAI_HANG_LOAT[loai], CO_HANG_LOAT[co], bat, sach


async def dat_co_hang_loat(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    loai: Any,
    co: Any,
    bat: Any,
    ap_dung: bool = False,
    ids: Any = None,
) -> dict[str, Any]:
    """Đặt MỘT cờ cho cả loại vật tư; `ap_dung=False` chỉ ĐẾM (xem trước).

    - Chỉ đổi đúng cột của cờ được chọn, và chỉ vật tư ĐANG BÁN (`active`): hàng đã tạm
      ngưng giữ nguyên mọi thứ (đếm ở `so_ngung_ban_bo_qua` để màn nói rõ).
    - Chỉ đếm / đổi dòng mà giá trị HIỆN THẤY khác đích (NULL của cờ kinh doanh = chưa
      tick = tắt), nên "sẽ đổi N" khớp những gì người dùng sẽ thấy đổi.
    - `ids` (tuỳ chọn) khoanh vào đúng những dòng đó — dùng cho HOÀN TÁC: màn gửi lại
      các id vừa đổi với giá trị ngược lại.
    - Cùng quyền với sửa thuộc tính từng món (router giữ `price.service.manage`); ghi
      một dòng event_log (ai / lúc / loại / cờ / số dòng) cùng giao dịch với UPDATE.
    """
    gia_tri_loai, cot, dich, ds_id = kiem_hang_loat(loai, co, bat, ids)
    loc_id = " AND id = ANY($4::uuid[])" if ds_id is not None else ""
    tham_so: list[Any] = [identity.clinic_id, gia_tri_loai, dich]
    if ds_id is not None:
        tham_so.append(ds_id)
    # `clinic_id = $1::uuid` viết thẳng trong từng câu SQL bên dưới (không nhét vào
    # `khung`): máy kiểm phạm vi phòng khám đọc chữ của câu, không chạy f-string.
    khung = "\"group\" = 'vat_tu' AND loai_vat_tu IS NOT DISTINCT FROM $2::text"
    doi = f"active AND coalesce({cot}, false) <> $3::bool{loc_id}"

    async with pool.acquire() as conn, conn.transaction():
        tong, ngung = await conn.fetchrow(
            f"SELECT count(*), count(*) FILTER (WHERE NOT active)"
            f" FROM service_price WHERE clinic_id = $1::uuid AND {khung}",
            identity.clinic_id,
            gia_tri_loai,
        )
        if not ap_dung:
            so_doi = await conn.fetchval(
                "SELECT count(*) FROM service_price WHERE clinic_id = $1::uuid"
                f" AND {khung} AND {doi}",
                *tham_so,
            )
            da_doi: list[str] = []
        else:
            rows = await conn.fetch(
                f"UPDATE service_price SET {cot} = $3::bool, updated_at = now()"
                f" WHERE clinic_id = $1::uuid AND {khung} AND {doi}"
                " RETURNING id::text",
                *tham_so,
            )
            da_doi = sorted(r["id"] for r in rows)
            so_doi = len(da_doi)
            if so_doi:
                await record_event(
                    conn,
                    event_type="vat_tu.co_hang_loat",
                    aggregate_type="vat_tu_danh_muc",
                    aggregate_id=identity.clinic_id,
                    identity=identity,
                    origin="api:vat-tu-hang-loat",
                    payload={
                        "loai": str(loai),
                        "co": str(co),
                        "bat": dich,
                        "so_dong": so_doi,
                        "vat_tu_ids": da_doi,
                    },
                )
    return {
        "ap_dung": ap_dung,
        "loai": str(loai),
        "co": str(co),
        "bat": dich,
        "so_doi": int(so_doi),
        "so_trong_loai": int(tong),
        "so_ngung_ban_bo_qua": int(ngung),
        "ids": da_doi,
    }
