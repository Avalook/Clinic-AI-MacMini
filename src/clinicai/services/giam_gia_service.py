"""Giảm giá chưa thu: khoá cùng lượt với thu tiền, kiểm lại dấu hoá đơn."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID, uuid4

import asyncpg

from clinicai.api.exceptions import BillChangedError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import GiamGiaDaAp, GiamGiaDaHoanTac
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import doi_quyen
from clinicai.services.bill_service import (
    GiamGia,
    HoaDon,
    ap_giam_gia,
    doc_giam_gia,
    giam_duoc,
    tinh_hoa_don,
)
from clinicai.services.payment_service import QUYEN_THU, _khoa_luot_thu


def doc_gia_tri(kieu: object, gia_tri: object) -> Decimal:
    try:
        so = Decimal(str(gia_tri))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError("Giá trị giảm giá không hợp lệ.") from None
    if (
        not isinstance(kieu, str)
        or kieu not in {"PHAN_TRAM", "SO_TIEN"}
        or not so.is_finite()
        or so <= 0
    ):
        raise ValidationError("Chọn % hoặc số tiền giảm lớn hơn 0.")
    if so >= Decimal("1000000000000"):
        raise ValidationError("Giá trị giảm quá lớn.")
    if so != so.quantize(Decimal("0.01")):
        raise ValidationError("Giá trị giảm chỉ nhận tối đa hai số lẻ.")
    if kieu == "PHAN_TRAM" and so > 100:
        raise ValidationError("Phần trăm giảm không vượt 100%.")
    if kieu == "SO_TIEN" and so != so.to_integral_value():
        raise ValidationError("Số tiền giảm phải nguyên đồng.")
    if so >= Decimal("1000000000000"):
        raise ValidationError("Giá trị giảm quá lớn.")
    return so


def _uuid(value: object) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Mã lượt hoặc giảm giá không hợp lệ.") from None


def _ly_do(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 500:
        raise ValidationError("Nhập lý do giảm giá/hoàn tác (tối đa 500 ký tự).")
    return value.strip()


async def _kiem(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    visit_id: str,
    kind: str,
    revision: object,
) -> HoaDon:
    if not isinstance(kind, str) or kind not in QUYEN_THU:
        raise ValidationError("Loại hoá đơn không hợp lệ.")
    await doi_quyen(conn, identity, QUYEN_THU[kind])
    luot = await _khoa_luot_thu(conn, visit_id, identity)
    if luot is None:
        raise NotFoundError("Không tìm thấy lượt khám.")
    if await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM cong_no WHERE clinic_id=$1::uuid AND "
        "visit_id=$2::uuid AND trang_thai='CHUA_THU')",
        identity.clinic_id,
        visit_id,
    ):
        raise ValidationError("Lượt đang ghi nợ — huỷ ghi nợ → giảm → ghi nợ lại.")
    if await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM payment_cycle WHERE clinic_id=$1::uuid "
        "AND visit_id=$2::uuid AND kind=$3 AND status='PENDING_VERIFICATION')",
        identity.clinic_id,
        visit_id,
        kind,
    ):
        raise ValidationError("Huỷ lần chờ trước khi đổi giảm giá.")
    hd = await tinh_hoa_don(
        conn, clinic_id=identity.clinic_id, visit_id=visit_id, kind=kind
    )
    if not isinstance(revision, str) or revision != hd.revision:
        raise BillChangedError("Hoá đơn vừa thay đổi — tải lại rồi giảm giá.")
    if kind == "thuoc" and await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM payment_cycle WHERE clinic_id=$1::uuid "
        "AND visit_id=$2::uuid AND kind=$3 AND status='PAID')",
        identity.clinic_id,
        visit_id,
        kind,
    ):
        raise ValidationError(
            "Thuốc đã thu — hoàn tác lần thu trong ngày rồi giảm và thu lại."
        )
    return hd


async def them(
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    *,
    visit_id: object,
    kind: str,
    pham_vi: str,
    kieu: str,
    gia_tri: object,
    ly_do: object,
    bill_revision: object,
    source_type: str | None = None,
    source_id: str | None = None,
) -> dict[str, Any]:
    visit = _uuid(visit_id)
    so, reason = doc_gia_tri(kieu, gia_tri), _ly_do(ly_do)
    if (
        not isinstance(pham_vi, str)
        or pham_vi not in {"DONG", "HOA_DON"}
        or ((pham_vi == "DONG") != bool(source_type and source_id))
    ):
        raise ValidationError("Phạm vi giảm giá và dòng hoá đơn không hợp lệ.")
    if pham_vi == "HOA_DON" and (source_type is not None or source_id is not None):
        raise ValidationError("Giảm hoá đơn không nhận mã dòng.")
    if any(
        x is not None and (not isinstance(x, str) or not x or len(x) > 100)
        for x in (source_type, source_id)
    ):
        raise ValidationError("Mã dòng hoá đơn không hợp lệ.")
    gid = str(uuid4())
    async with pool.acquire() as conn, conn.transaction():
        hd = await _kiem(conn, identity, visit, kind, bill_revision)
        if hd.van_de:
            raise ValidationError("Chưa giảm được — " + "; ".join(hd.van_de))
        dong = next(
            (
                d
                for d in hd.dong
                if d.source_type == source_type and d.source_id == source_id
            ),
            None,
        )
        if pham_vi == "DONG" and (dong is None or not giam_duoc(dong)):
            raise ValidationError(
                "Dòng này không được giảm (đã thu, đối tác hoặc trả trước liệu trình)."
            )
        if pham_vi == "HOA_DON" and not any(giam_duoc(d) for d in hd.dong):
            raise ValidationError("Không có khoản chưa thu được giảm giá.")
        ds = await doc_giam_gia(
            conn, clinic_id=identity.clinic_id, visit_id=visit, kind=kind
        )
        if any(
            g.pham_vi == pham_vi
            and (
                pham_vi == "HOA_DON"
                or (g.source_type, g.source_id) == (source_type, source_id)
            )
            for g in ds
        ):
            raise ValidationError(
                "Khoản này đã có giảm giá — hoàn tác trước khi giảm lại."
            )
        moi = GiamGia(gid, pham_vi, kieu, so, source_type, source_id, reason)
        sau = ap_giam_gia(hd, [*ds, moi])
        if sau.van_de:
            raise ValidationError("; ".join(sau.van_de))
        applied = next(g for g in sau.giam_gia if g["id"] == gid)
        await conn.execute(
            "INSERT INTO giam_gia "
            "(id,clinic_id,visit_id,kind,pham_vi,source_type,source_id,"
            "kieu,gia_tri,ly_do,tao_boi) "
            "VALUES ($1::uuid,$2::uuid,$3::uuid,$4,$5,$6,$7,$8,$9,$10,$11::uuid)",
            gid,
            identity.clinic_id,
            visit,
            kind,
            pham_vi,
            source_type,
            source_id,
            kieu,
            so,
            reason,
            identity.staff_id,
        )
        await emit_event(
            conn,
            ten="payment.discount_applied",
            clinic_id=identity.clinic_id,
            aggregate_id=gid,
            payload=GiamGiaDaAp(
                visit_id=visit,
                giam_gia_id=gid,
                kind=kind,
                pham_vi=pham_vi,
                kieu=kieu,
                gia_tri=str(so),
                so_tien=applied["so_tien"],
                ten_dong=dong.ten if dong else None,
                ly_do=reason,
            ),
            boi=nguoi(identity),
            correlation_id=visit,
        )
        sau = await tinh_hoa_don(
            conn, clinic_id=identity.clinic_id, visit_id=visit, kind=kind
        )
        return {"id": gid, "hoa_don": sau.cho_api()}


async def huy(
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    *,
    giam_gia_id: object,
    bill_revision: object,
    ly_do: object,
) -> dict[str, Any]:
    gid, reason = _uuid(giam_gia_id), _ly_do(ly_do)
    async with pool.acquire() as conn, conn.transaction():
        g = await conn.fetchrow(
            "SELECT * FROM giam_gia WHERE clinic_id=$1::uuid AND id=$2::uuid",
            identity.clinic_id,
            gid,
        )
        if g is None:
            raise NotFoundError("Không tìm thấy giảm giá.")
        visit = str(g["visit_id"])
        await _kiem(conn, identity, visit, g["kind"], bill_revision)
        g = await conn.fetchrow(
            "SELECT * FROM giam_gia WHERE clinic_id=$1::uuid "
            "AND id=$2::uuid FOR UPDATE",
            identity.clinic_id,
            gid,
        )
        if g["payment_cycle_id"] is not None:
            raise ValidationError("Hoàn tác lần thu trước khi hoàn tác giảm giá.")
        if g["huy_luc"] is not None:
            raise ValidationError("Giảm giá đã hoàn tác — tải lại hoá đơn.")
        await conn.execute(
            "UPDATE giam_gia SET huy_luc=now(),huy_boi=$3::uuid,ly_do_huy=$4 "
            "WHERE clinic_id=$1::uuid AND id=$2::uuid",
            identity.clinic_id,
            gid,
            identity.staff_id,
            reason,
        )
        await emit_event(
            conn,
            ten="payment.discount_undone",
            clinic_id=identity.clinic_id,
            aggregate_id=gid,
            payload=GiamGiaDaHoanTac(
                visit_id=visit,
                giam_gia_id=gid,
                kind=g["kind"],
                pham_vi=g["pham_vi"],
                kieu=g["kieu"],
                gia_tri=str(g["gia_tri"]),
                ly_do=reason,
            ),
            boi=nguoi(identity),
            correlation_id=visit,
        )
        hd = await tinh_hoa_don(
            conn, clinic_id=identity.clinic_id, visit_id=visit, kind=g["kind"]
        )
        return {"id": gid, "hoa_don": hd.cho_api()}
