"""Lấy mẫu, mã ống, cho qua, đóng việc (kế hoạch 4.5, 5, 5c; chặng 3).

* **Lấy mẫu** chỉ khi việc ở CHO_LAY_MAU (đã ghi nhận thu hoặc quản lý cho qua) —
  ngoại lệ DUY NHẤT của "làm trước, thu sau" (ADR-0015). Một ống: mọi việc CÙNG
  đối tác (FK ghép ở DB). Mã cấp ở Postgres (`cap_ma_mau`, Damm). Hẹn trả = hôm nay +
  số ngày lớn nhất trong ống (đếm MỌI ngày, câu E), chụp thành ngày cụ thể.
* **Huỷ mẫu** (NHAP_SAI / MAU_HONG) — việc về CHO_LAY_MAU, khoản thu GIỮ NGUYÊN, lấy
  lại ra mã MỚI. Còn tệp kết quả hiệu lực ⇒ thu hồi / từ chối tệp trước.
* **Đóng** ("Đối tác đã tự trả khách") — chặn khi đã gửi; **mở lại** được.
Lệnh nào cũng: lý do ≥ 3 ký tự (trừ lấy mẫu), sự kiện `lab.*`, không xoá dòng.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import XetNghiemMau, XetNghiemViec
from clinicai.events.emit import emit_event, nguoi
from clinicai.services.tai_khoan_nhan_service import doc_id
from clinicai.services.xet_nghiem.ban import doc_viec
from clinicai.services.xet_nghiem.o_nhap import doc_ly_do

LOAI_HUY = ("NHAP_SAI", "MAU_HONG")


def doc_ids(raw: object) -> list[str]:
    if not isinstance(raw, list) or not raw or len(raw) > 20:
        raise ValidationError("Chọn 1–20 việc để lấy mẫu chung một ống.")
    ids = [doc_id(x, cau="Việc không hợp lệ.") for x in raw]
    return sorted({i for i in ids if i})


def _mau_id(raw: object) -> str:
    m = doc_id(raw, cau="Mẫu không hợp lệ.")
    if m is None:
        raise ValidationError("Chọn mẫu.")
    return m


def doc_ngay(raw: object) -> date | None:
    """'2026-11-08' → date. Rác → None (không ném — luật backend)."""
    try:
        return date.fromisoformat(str(raw).strip()[:10]) if raw else None
    except ValueError:
        return None


async def _mot_viec(
    conn: asyncpg.Connection, identity: StaffIdentity, order_id: object, hom_nay: date
) -> dict[str, Any]:
    oid = doc_id(order_id, cau="Việc không hợp lệ.")
    ds = await doc_viec(
        conn, identity.clinic_id, hom_nay=hom_nay, order_ids=[oid or ""]
    )
    if not ds:
        raise NotFoundError("Không tìm thấy việc xét nghiệm đối tác này.")
    return ds[0]


def _sk_viec(identity: StaffIdentity, v: dict[str, Any]) -> dict[str, Any]:
    return {
        "clinic_id": identity.clinic_id,
        "aggregate_id": v["order_id"],
        "payload": XetNghiemViec(
            visit_id=v["visit_id"], service_order_id=v["order_id"]
        ),
        "boi": nguoi(identity),
        "correlation_id": v["visit_id"],
    }


_HEN_SQL = """
SELECT max(coalesce(a.hen_tra_so_ngay, d.hen_tra_so_ngay_mac_dinh))
  FROM xet_nghiem_viec x
  JOIN service_order o ON o.id = x.service_order_id AND o.clinic_id = x.clinic_id
  JOIN doi_tac d ON d.id = x.doi_tac_id AND d.clinic_id = x.clinic_id
  JOIN service_price sp ON sp.clinic_id = o.clinic_id AND sp."group" = 'dich_vu'
   AND sp.service_code = o.service_code
  LEFT JOIN doi_tac_dich_vu a
    ON a.clinic_id = x.clinic_id AND a.doi_tac_id = x.doi_tac_id
   AND a.service_price_id = sp.id AND a.ngung_luc IS NULL
 WHERE x.clinic_id = $1::uuid AND x.service_order_id = ANY ($2::uuid[])
"""


async def lay_mau(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    data: dict[str, Any],
    hom_nay: date,
) -> dict[str, Any]:
    """Một ống cho các việc đã chọn. Trả mã ống + hẹn trả."""
    ids = doc_ids(data.get("order_ids"))
    cid = identity.clinic_id
    viec = await doc_viec(conn, cid, hom_nay=hom_nay, order_ids=ids)
    if len(viec) != len(ids):
        raise NotFoundError("Có việc không tìm thấy — tải lại màn.")
    chan = [v for v in viec if not v["nut"]["lay_mau"]]
    if chan:
        v = chan[0]
        raise ConflictError(
            f"«{v['ten_dich_vu']}» chưa lấy mẫu được: "
            f"{v['trang_thai']['ly_do_khong_lay_mau']}."
        )
    if len({v["doi_tac_id"] for v in viec}) != 1:
        raise ConflictError(
            "Một ống chỉ chứa việc của MỘT đối tác — tách thành hai ống."
        )
    so_ngay = await conn.fetchval(_HEN_SQL, cid, ids)
    hen = hom_nay + timedelta(days=int(so_ngay)) if so_ngay is not None else None
    cap = await conn.fetchrow("SELECT so, ma FROM public.cap_ma_mau($1::uuid)", cid)
    mau_id = await conn.fetchval(
        """
        INSERT INTO public.mau_xet_nghiem
            (clinic_id, doi_tac_id, ma_mau, so_thu_tu, lay_boi, hen_tra_ngay)
        VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid, $6) RETURNING id::text
        """,
        cid,
        viec[0]["doi_tac_id"],
        cap["ma"],
        cap["so"],
        identity.staff_id,
        hen,
    )
    try:
        await conn.executemany(
            "INSERT INTO public.mau_xet_nghiem_viec (mau_id, service_order_id,"
            " doi_tac_id, clinic_id) VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid)",
            [(mau_id, v["order_id"], v["doi_tac_id"], cid) for v in viec],
        )
    except asyncpg.UniqueViolationError:
        raise ConflictError(
            "Việc này vừa được người khác lấy mẫu — tải lại màn."
        ) from None
    await emit_event(
        conn,
        ten="lab.sample_collected",
        clinic_id=cid,
        aggregate_id=mau_id,
        payload=XetNghiemMau(mau_id=mau_id, ma_mau=cap["ma"], service_order_ids=ids),
        boi=nguoi(identity),
    )
    return {"mau_id": mau_id, "ma_mau": cap["ma"], "hen_tra_ngay": hen}


async def huy_mau(
    conn: asyncpg.Connection, identity: StaffIdentity, data: dict[str, Any]
) -> None:
    mau_id = _mau_id(data.get("mau_id"))
    loai = str(data.get("loai") or "NHAP_SAI").upper()
    if loai not in LOAI_HUY:
        raise ValidationError("Loại huỷ: nhập sai hoặc mẫu hỏng.")
    ly = doc_ly_do(data.get("ly_do"))
    cid = identity.clinic_id
    m = await conn.fetchrow(
        "SELECT ma_mau FROM public.mau_xet_nghiem WHERE clinic_id = $1::uuid"
        " AND id = $2::uuid AND huy_luc IS NULL FOR UPDATE",
        cid,
        mau_id,
    )
    if m is None:
        raise ConflictError("Mẫu đã huỷ hoặc không có — tải lại màn.")
    if await conn.fetchval(
        """
        SELECT EXISTS (SELECT 1 FROM public.mau_xet_nghiem_viec mv
          JOIN public.tep_ket_qua k ON k.clinic_id = mv.clinic_id
           AND k.service_order_id = mv.service_order_id AND k.da_xoa_luc IS NULL
           AND coalesce(k.xac_nhan_trang_thai, '') NOT IN ('TU_CHOI', 'THU_HOI')
         WHERE mv.mau_id = $1::uuid AND mv.go_luc IS NULL)
        """,
        mau_id,
    ):
        raise ConflictError(
            "Ống này đã có tệp kết quả — thu hồi tệp trước rồi huỷ mẫu."
        )
    await conn.execute(
        "UPDATE public.mau_xet_nghiem SET huy_luc = now(), huy_boi = $3::uuid,"
        " huy_ly_do = $4, huy_loai = $5 WHERE clinic_id = $1::uuid AND id = $2::uuid",
        cid,
        mau_id,
        identity.staff_id,
        ly,
        loai,
    )
    ids = await conn.fetch(
        "UPDATE public.mau_xet_nghiem_viec SET go_luc = now(), go_boi = $2::uuid,"
        " go_ly_do = $3 WHERE mau_id = $1::uuid AND go_luc IS NULL"
        " RETURNING service_order_id::text",
        mau_id,
        identity.staff_id,
        ly,
    )
    await emit_event(
        conn,
        ten="lab.sample_voided",
        clinic_id=cid,
        aggregate_id=mau_id,
        payload=XetNghiemMau(
            mau_id=mau_id, ma_mau=m["ma_mau"], service_order_ids=[r[0] for r in ids]
        ),
        boi=nguoi(identity),
    )


async def sua_hen_tra(
    conn: asyncpg.Connection, identity: StaffIdentity, data: dict[str, Any]
) -> None:
    mau_id = _mau_id(data.get("mau_id"))
    ngay = doc_ngay(data.get("hen_tra_ngay"))
    if ngay is None:
        raise ValidationError("Chọn ngày hẹn trả hợp lệ.")
    ly = doc_ly_do(data.get("ly_do"))
    v = await conn.fetchval(
        "UPDATE public.mau_xet_nghiem SET hen_tra_ngay = $3, hen_tra_sua_luc = now(),"
        " hen_tra_sua_boi = $4::uuid, hen_tra_sua_ly_do = $5"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid AND huy_luc IS NULL"
        " RETURNING id",
        identity.clinic_id,
        mau_id,
        ngay,
        identity.staff_id,
        ly,
    )
    if v is None:
        raise ConflictError("Mẫu đã huỷ hoặc không có — tải lại màn.")


async def cho_qua(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    data: dict[str, Any],
    hom_nay: date,
) -> None:
    """Quản lý cho lấy mẫu khi chưa ghi nhận thu (câu 2) — quyền gác ở router."""
    v = await _mot_viec(conn, identity, data.get("order_id"), hom_nay)
    if not v["nut"]["cho_qua"]:
        raise ConflictError("Việc này không còn ở bước chờ thu — tải lại màn.")
    try:
        await conn.execute(
            "UPDATE public.xet_nghiem_viec SET cho_lay_mau_truoc_luc = now(),"
            " cho_lay_mau_truoc_boi = $3::uuid, cho_lay_mau_truoc_ly_do = $4"
            " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid",
            identity.clinic_id,
            v["order_id"],
            identity.staff_id,
            doc_ly_do(data.get("ly_do")),
        )
    except asyncpg.InsufficientPrivilegeError:
        raise ConflictError(
            "Việc này đã cho qua một lần (đã gỡ) — chưa hỗ trợ cho qua lại."
        ) from None
    await emit_event(conn, ten="lab.prepay_waived", **_sk_viec(identity, v))


async def go_cho_qua(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    data: dict[str, Any],
    hom_nay: date,
) -> None:
    v = await _mot_viec(conn, identity, data.get("order_id"), hom_nay)
    if v["mau_id"] is not None:
        raise ConflictError("Đã lấy mẫu — huỷ mẫu trước rồi gỡ cho qua.")
    n = await conn.execute(
        "UPDATE public.xet_nghiem_viec SET cho_lay_mau_go_luc = now(),"
        " cho_lay_mau_go_boi = $3::uuid, cho_lay_mau_go_ly_do = $4"
        " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
        " AND cho_lay_mau_truoc_luc IS NOT NULL AND cho_lay_mau_go_luc IS NULL",
        identity.clinic_id,
        v["order_id"],
        identity.staff_id,
        doc_ly_do(data.get("ly_do")),
    )
    if n.endswith(" 0"):
        raise ConflictError("Việc này chưa được cho qua — không có gì để gỡ.")
    await emit_event(conn, ten="lab.prepay_waiver_revoked", **_sk_viec(identity, v))


async def dong(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    data: dict[str, Any],
    hom_nay: date,
) -> None:
    """ "Đối tác đã tự trả khách" — chặn khi đã gửi (DA_GUI thắng DA_DONG)."""
    ly = doc_ly_do(data.get("ly_do"))
    v = await _mot_viec(conn, identity, data.get("order_id"), hom_nay)
    if not v["nut"]["dong"]:
        raise ConflictError(f"Không đóng được việc đang «{v['trang_thai']['nhan']}».")
    try:
        await conn.execute(
            "INSERT INTO public.xet_nghiem_dong (clinic_id, service_order_id, ly_do,"
            " dong_boi) VALUES ($1::uuid, $2::uuid, $3, $4::uuid)",
            identity.clinic_id,
            v["order_id"],
            ly,
            identity.staff_id,
        )
    except asyncpg.UniqueViolationError:
        raise ConflictError("Việc này vừa được đóng — tải lại màn.") from None
    await emit_event(conn, ten="lab.closed_by_partner", **_sk_viec(identity, v))


async def mo_lai(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    data: dict[str, Any],
    hom_nay: date,
) -> None:
    ly = doc_ly_do(data.get("ly_do"))
    v = await _mot_viec(conn, identity, data.get("order_id"), hom_nay)
    n = await conn.execute(
        "UPDATE public.xet_nghiem_dong SET mo_lai_luc = now(), mo_lai_boi = $3::uuid,"
        " mo_lai_ly_do = $4 WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
        " AND mo_lai_luc IS NULL",
        identity.clinic_id,
        v["order_id"],
        identity.staff_id,
        ly,
    )
    if n.endswith(" 0"):
        raise ConflictError("Việc này không ở trạng thái đã đóng — tải lại màn.")
    await emit_event(conn, ten="lab.reopened", **_sk_viec(identity, v))
