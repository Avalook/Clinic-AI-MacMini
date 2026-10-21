"""Vết đổi giá — ai, lúc nào, giá cũ → giá mới (Tuyền duyệt 21/10/2026).

Hoá đơn tính theo giá LÚC THU (`bill_service`), còn `service_price` /
`drug_catalog` chỉ giữ giá hiện tại: sửa 500k → 450k là giá cũ biến mất, không
ai trả lời được "sao khách trả 450?". Mỗi lần giá THẬT SỰ đổi, nơi sửa gọi
`ghi_doi_gia` trong CÙNG giao dịch; vết nằm ở `domain_event` (chỉ thêm, không
sửa được) nên không cần bảng riêng. Màn đọc "sửa lần cuối" theo lô + lịch sử
một dòng qua hai hàm dưới.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import asyncpg

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import GiaDaDoi
from clinicai.events.emit import HE_THONG, emit_event, nguoi

LoaiGia = Literal["dich_vu", "thuoc"]
#: dich_vu = một dòng `service_price` (dịch vụ, vật tư, thuốc ở Bảng giá);
#: thuoc = một thuốc trong danh mục kho (`drug_catalog`).
_GOC = {
    "dich_vu": ("service_price", "gia_dich_vu.da_doi"),
    "thuoc": ("drug_catalog", "gia_thuoc.da_doi"),
}


def _dong(v: Any) -> int | None:
    """Giá về số đồng nguyên; rỗng / rác = chưa có giá."""
    if v is None or v == "":
        return None
    try:
        return int(Decimal(str(v)))
    except (InvalidOperation, ValueError):
        return None


async def ghi_doi_gia(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    loai: LoaiGia,
    id: str,
    ten: str,
    ma: str | None,
    gia_cu: Any,
    gia_moi: Any,
    hanh_dong: Literal["THEM", "SUA", "XOA"],
) -> bool:
    """Phát sự kiện giá đã đổi khi số THẬT SỰ khác — lưu lại cùng giá (xác nhận
    giá tạm) hay đổi tên không sinh dòng lịch sử. Trả True nếu đã ghi."""
    cu, moi = _dong(gia_cu), _dong(gia_moi)
    if cu == moi:
        return False
    tai = GiaDaDoi(ma=ma, ten=ten, gia_cu=cu, gia_moi=moi, hanh_dong=hanh_dong)
    # Script / seed gọi không kèm nhân viên → ghi là hệ thống, đúng sự thật.
    boi = nguoi(identity) if getattr(identity, "staff_id", None) else HE_THONG
    if loai == "dich_vu":
        await emit_event(
            conn,
            ten="gia_dich_vu.da_doi",
            clinic_id=identity.clinic_id,
            aggregate_id=str(id),
            payload=tai,
            boi=boi,
        )
    else:
        await emit_event(
            conn,
            ten="gia_thuoc.da_doi",
            clinic_id=identity.clinic_id,
            aggregate_id=str(id),
            payload=tai,
            boi=boi,
        )
    return True


def _dong_lich_su(r: asyncpg.Record) -> dict[str, Any]:
    p = r["payload"]
    if isinstance(p, str):
        p = json.loads(p)
    p = p if isinstance(p, dict) else {}
    return {
        "luc": r["occurred_at"].isoformat(),
        "boi": r["boi"] or "Hệ thống",
        "hanh_dong": p.get("hanh_dong"),
        "gia_cu": p.get("gia_cu"),
        "gia_moi": p.get("gia_moi"),
    }


_CHON = """
    SELECT {dau} e.aggregate_id::text AS id, e.occurred_at, e.payload,
           s.full_name AS boi
      FROM domain_event e
      LEFT JOIN staff s ON s.id = e.actor_staff_id
     WHERE e.clinic_id = $1::uuid AND e.aggregate_type = $2 AND e.event_type = $3
       AND e.aggregate_id = ANY($4::uuid[])
     ORDER BY e.aggregate_id, e.occurred_at DESC, e.seq DESC
"""


async def sua_cuoi(
    conn: asyncpg.Connection, *, clinic_id: str, loai: LoaiGia, ids: list[str]
) -> dict[str, dict[str, Any]]:
    """{id dòng giá: lần đổi giá gần nhất} cho cả bảng — một câu SQL, đi index
    `ix_domain_event_aggregate`. Dòng chưa từng đổi giá thì vắng mặt."""
    if not ids:
        return {}
    agg, ten = _GOC[loai]
    rows = await conn.fetch(
        _CHON.format(dau="DISTINCT ON (e.aggregate_id)"),
        clinic_id,
        agg,
        ten,
        [str(i) for i in ids],
    )
    return {r["id"]: _dong_lich_su(r) for r in rows}


class LichSuGiaService:
    """Đọc mọi lần đổi giá của MỘT dòng, mới nhất trước — nút "Lịch sử"."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(
        self, *, identity: StaffIdentity, loai: str, id: str
    ) -> list[dict[str, Any]]:
        if loai not in _GOC:
            raise ValidationError("Loại giá không hợp lệ.")
        agg, ten = _GOC[loai]
        async with self._pool.acquire() as conn:
            try:
                rows = await conn.fetch(
                    _CHON.format(dau="") + " LIMIT 200",
                    identity.clinic_id,
                    agg,
                    ten,
                    [str(id)],
                )
            except asyncpg.DataError:
                raise ValidationError("Mã dòng giá không hợp lệ.") from None
        return [_dong_lich_su(r) for r in rows]
