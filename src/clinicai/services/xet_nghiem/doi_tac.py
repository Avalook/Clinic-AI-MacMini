"""Đối tác xét nghiệm + ánh xạ dịch vụ + cài đặt bàn XN (kế hoạch 4.1, 4.2, câu F).

Ghi: quyền `config.clinic.manage` (màn Cài đặt → Đối tác, chỉ Quản lý). Không xoá —
ngưng có lý do, bật lại được. Đổi ánh xạ KHÔNG đổi việc đã chỉ định (đã chụp ở
`xet_nghiem_viec`, `chup.py`).

Luật "bên thu": dịch vụ có ánh xạ đối tác ⇒ phải là `EXTERNAL_PARTNER`. Ép LÚC LƯU ánh
xạ bằng cách TỪ CHỐI (bảng giá thuộc module khác — không tự UPDATE `service_price`):
Quản lý đổi bên thu ở màn Bảng giá trước. Test đếm số ánh xạ lệch (chỉ được giảm).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.audit import record_event
from clinicai.services.tai_khoan_nhan_service import doc_id
from clinicai.services.xet_nghiem.drive import den_drive
from clinicai.services.xet_nghiem.o_nhap import (
    doc_form_doi_tac,
    doc_ly_do,
    doc_so_ngay,
    doc_tien,
)

QUYEN_QUAN_LY = "config.clinic.manage"
_ORIGIN = "api:xet-nghiem-doi-tac"
#: Cột nhịp Drive chỉ để tính `drive_den`, không trả thẳng.
_COT_NHIP = ("lan_quet_cuoi", "ok_cuoi", "loi_cuoi")


# ── Đọc DB ─────────────────────────────────────────────────────────────────
async def danh_sach(conn: asyncpg.Connection, cid: str) -> dict[str, Any]:
    doi_tac = await conn.fetch(
        """
        SELECT d.id::text, d.ten, d.ma_ngan, d.sdt, d.ghi_chu, d.drive_folder_id,
               d.tai_khoan_nhan_ck,
               d.hen_tra_so_ngay_mac_dinh, d.ngung_luc, d.ly_do_ngung,
               (d.ngung_luc IS NULL) AS gan_duoc,
               n.lan_quet_cuoi, n.ok_cuoi, n.loi_cuoi
          FROM public.doi_tac d
          LEFT JOIN public.drive_nhip n
            ON n.clinic_id = d.clinic_id AND n.doi_tac_id = d.id AND n.nguon = 'DRIVE'
         WHERE d.clinic_id = $1::uuid
         ORDER BY d.ngung_luc IS NOT NULL, lower(d.ten)
        """,
        cid,
    )
    anh_xa = await conn.fetch(
        """
        SELECT a.id::text, a.doi_tac_id::text, a.service_price_id::text,
               sp.service_code, sp.name AS ten_dich_vu, sp.unit_price,
               a.gia_goi_y, a.hen_tra_so_ngay, a.mac_dinh,
               -- Giá trị HIỆU LỰC (một nơi tính — cùng luật với chup.py): giá cặp >
               -- giá bảng giá, 0 ⇒ trống; hẹn của cặp > hẹn mặc định đối tác.
               nullif(coalesce(a.gia_goi_y, sp.unit_price), 0) AS gia_hieu_luc,
               coalesce(a.hen_tra_so_ngay, d.hen_tra_so_ngay_mac_dinh)
                   AS hen_tra_hieu_luc
          FROM public.doi_tac_dich_vu a
          JOIN public.service_price sp
            ON sp.clinic_id = a.clinic_id AND sp.id = a.service_price_id
          JOIN public.doi_tac d ON d.clinic_id = a.clinic_id AND d.id = a.doi_tac_id
         WHERE a.clinic_id = $1::uuid AND a.ngung_luc IS NULL
         ORDER BY lower(sp.name)
        """,
        cid,
    )
    dich_vu = await conn.fetch(
        """
        SELECT sp.id::text, sp.service_code, sp.name, sp.unit_price
          FROM public.service_price sp
         WHERE sp.clinic_id = $1::uuid AND sp."group" = 'dich_vu' AND sp.active
           AND sp.billing_owner = 'EXTERNAL_PARTNER'
         ORDER BY lower(sp.name)
        """,
        cid,
    )
    nguong = await doc_nguong(conn, cid)
    theo_dt: dict[str, list[dict[str, Any]]] = {}
    for a in anh_xa:
        theo_dt.setdefault(a["doi_tac_id"], []).append(dict(a))
    bay_gio = datetime.now(UTC)
    return {
        "doi_tac": [
            {
                **{k: d[k] for k in d.keys() if k not in _COT_NHIP},
                "dich_vu": theo_dt.get(d["id"], []),
                "drive_den": den_drive(
                    d["drive_folder_id"],
                    d["lan_quet_cuoi"],
                    d["ok_cuoi"],
                    d["loi_cuoi"],
                    bay_gio,
                ),
            }
            for d in doi_tac
        ],
        "dich_vu_thu_ho": [dict(r) for r in dich_vu],
        "nguong_lay_mau_ngay": nguong,
    }


async def doc_nguong(conn: asyncpg.Connection, cid: str) -> int:
    n = await conn.fetchval(
        "SELECT nguong_lay_mau_ngay FROM public.xet_nghiem_cai_dat"
        " WHERE clinic_id = $1::uuid",
        cid,
    )
    return int(n) if n is not None else 2


# ── Ghi ────────────────────────────────────────────────────────────────────
async def _vet(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    loai: str,
    bang: str,
    id_: str,
    payload: dict[str, Any] | None = None,
) -> None:
    await record_event(
        conn,
        event_type=loai,
        aggregate_type=bang,
        aggregate_id=id_,
        identity=identity,
        origin=_ORIGIN,
        payload=payload,
    )


#: $1 clinic, $2 id (NULL khi thêm), $3.. ô của form, $9 người làm, $10 TK nhận CK.
_LUU_DT = """
WITH sua AS (
    UPDATE public.doi_tac
       SET ten = $3, ma_ngan = $4, sdt = $5, ghi_chu = $6,
           drive_folder_id = $7, hen_tra_so_ngay_mac_dinh = $8,
           tai_khoan_nhan_ck = $10, sua_luc = now(), sua_boi = $9::uuid
     WHERE $2::uuid IS NOT NULL AND clinic_id = $1::uuid AND id = $2::uuid
    RETURNING id
), them AS (
    INSERT INTO public.doi_tac (clinic_id, ten, ma_ngan, sdt, ghi_chu,
        drive_folder_id, hen_tra_so_ngay_mac_dinh, tai_khoan_nhan_ck, tao_boi, sua_boi)
    SELECT $1::uuid, $3, $4, $5, $6, $7, $8, $10, $9::uuid, $9::uuid
     WHERE $2::uuid IS NULL
    RETURNING id
)
SELECT id::text FROM sua UNION ALL SELECT id::text FROM them
"""


async def luu_doi_tac(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    data: Mapping[str, Any],
    doi_tac_id: str | None = None,
) -> str:
    """Thêm (`doi_tac_id` None) hoặc sửa đối tác. Mã ngắn trùng → 409."""
    f = doc_form_doi_tac(data)
    dt_id = doc_id(doi_tac_id, cau="Đối tác không hợp lệ.")
    try:
        v = await conn.fetchval(
            _LUU_DT,
            identity.clinic_id,
            dt_id,
            f["ten"],
            f["ma_ngan"],
            f["sdt"],
            f["ghi_chu"],
            f["drive_folder_id"],
            f["hen_tra"],
            identity.staff_id,
            f["tai_khoan_nhan_ck"],
        )
    except asyncpg.UniqueViolationError:
        raise ConflictError(
            f"Mã ngắn {f['ma_ngan']} đã có đối tác khác dùng."
        ) from None
    if v is None:
        raise NotFoundError("Không tìm thấy đối tác.")
    await _vet(
        conn, identity, "lab.partner_saved", "doi_tac", v, {"moi": dt_id is None}
    )
    return str(v)


async def ngung_doi_tac(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    doi_tac_id: str,
    *,
    ngung: bool,
    ly_do: object = None,
) -> None:
    """Ngưng (có lý do) / bật lại. Việc dở của đối tác đã ngưng VẪN hiện ở bàn —
    chỉ không chọn được cho việc mới (chup.py bỏ đối tác ngưng)."""
    dt_id = doc_id(doi_tac_id, cau="Đối tác không hợp lệ.")
    ly = doc_ly_do(ly_do) if ngung else None
    v = await conn.fetchval(
        """
        UPDATE public.doi_tac
           SET ngung_luc = CASE WHEN $3 THEN now() END,
               ngung_boi = CASE WHEN $3 THEN $4::uuid END,
               ly_do_ngung = $5, sua_luc = now(), sua_boi = $4::uuid
         WHERE clinic_id = $1::uuid AND id = $2::uuid
           AND (ngung_luc IS NULL) = $3
        RETURNING id::text
        """,
        identity.clinic_id,
        dt_id,
        ngung,
        identity.staff_id,
        ly,
    )
    if v is None:
        raise ConflictError("Đối tác không có hoặc đã ở trạng thái này — tải lại màn.")
    loai = "lab.partner_paused" if ngung else "lab.partner_resumed"
    await _vet(conn, identity, loai, "doi_tac", v, {"ly_do": ly} if ly else None)


async def _kiem_gan(conn: asyncpg.Connection, cid: str, sp_id: str, dt_id: str) -> None:
    """Gán được khi: có dịch vụ + đối tác, đối tác chưa ngưng, dịch vụ đối tác thu."""
    dv = await conn.fetchrow(
        """
        SELECT sp.billing_owner, sp.name, d.ngung_luc
          FROM public.service_price sp, public.doi_tac d
         WHERE sp.clinic_id = $1::uuid AND sp.id = $2::uuid
           AND d.clinic_id = $1::uuid AND d.id = $3::uuid
        """,
        cid,
        sp_id,
        dt_id,
    )
    if dv is None:
        raise NotFoundError("Không tìm thấy dịch vụ hoặc đối tác.")
    if dv["ngung_luc"] is not None:
        raise ConflictError("Đối tác đã ngưng — bật lại trước khi gán dịch vụ.")
    if dv["billing_owner"] != "EXTERNAL_PARTNER":
        raise ConflictError(
            f"Dịch vụ «{dv['name']}» đang do phòng khám thu. Đổi bên thu sang "
            "«Đối tác thu» ở màn Bảng giá trước, rồi gán đối tác."
        )


#: Đặt mặc định cho B thì bỏ mặc định của đối tác khác trên cùng dịch vụ (câu riêng,
#: cùng giao dịch — CTE ghi không có thứ tự chắc chắn với câu chính). Chỉ mục duy nhất
#: có điều kiện vẫn là chốt cuối khi hai người chen nhau.
_BO_MAC_DINH_SQL = """
UPDATE public.doi_tac_dich_vu SET mac_dinh = false, sua_luc = now(), sua_boi = $4::uuid
 WHERE clinic_id = $1::uuid AND service_price_id = $2::uuid
   AND mac_dinh AND doi_tac_id <> $3::uuid
"""
_GAN_SQL = """
INSERT INTO public.doi_tac_dich_vu (clinic_id, doi_tac_id, service_price_id,
    gia_goi_y, hen_tra_so_ngay, mac_dinh, tao_boi, sua_boi)
VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7::uuid, $7::uuid)
ON CONFLICT (clinic_id, doi_tac_id, service_price_id) WHERE ngung_luc IS NULL
DO UPDATE SET gia_goi_y = EXCLUDED.gia_goi_y,
              hen_tra_so_ngay = EXCLUDED.hen_tra_so_ngay,
              mac_dinh = EXCLUDED.mac_dinh,
              sua_luc = now(), sua_boi = EXCLUDED.sua_boi
RETURNING id::text
"""


async def luu_anh_xa(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    data: Mapping[str, Any],
) -> str:
    """Gán dịch vụ cho đối tác (hoặc sửa giá gợi ý / hẹn trả của cặp đó).
    Mặc định = đối tác được chụp cho chỉ định mới."""
    cid = identity.clinic_id
    dt_id = doc_id(data.get("doi_tac_id"), cau="Đối tác không hợp lệ.")
    sp_id = doc_id(data.get("service_price_id"), cau="Dịch vụ không hợp lệ.")
    if dt_id is None or sp_id is None:
        raise ValidationError("Chọn đối tác và dịch vụ.")
    gia = doc_tien(data.get("gia_goi_y"))
    hen = doc_so_ngay(data.get("hen_tra_so_ngay"))
    mac_dinh = data.get("mac_dinh", True) is not False
    await _kiem_gan(conn, cid, sp_id, dt_id)
    if mac_dinh:
        await conn.execute(_BO_MAC_DINH_SQL, cid, sp_id, dt_id, identity.staff_id)
    try:
        v = await conn.fetchval(
            _GAN_SQL, cid, dt_id, sp_id, gia, hen, mac_dinh, identity.staff_id
        )
    except asyncpg.UniqueViolationError:
        raise ConflictError(
            "Người khác vừa đặt đối tác mặc định cho dịch vụ này — tải lại màn."
        ) from None
    await _vet(
        conn,
        identity,
        "lab.partner_service_saved",
        "doi_tac_dich_vu",
        v,
        {"doi_tac_id": dt_id, "service_price_id": sp_id, "mac_dinh": mac_dinh},
    )
    return str(v)


async def bo_anh_xa(
    conn: asyncpg.Connection, identity: StaffIdentity, anh_xa_id: str
) -> None:
    """Bỏ gán (ngưng dòng, không xoá). Việc đã chỉ định giữ đối tác đã chụp."""
    a_id = doc_id(anh_xa_id, cau="Dòng gán không hợp lệ.")
    v = await conn.fetchval(
        """
        UPDATE public.doi_tac_dich_vu
           SET ngung_luc = now(), ngung_boi = $3::uuid, mac_dinh = false,
               sua_luc = now(), sua_boi = $3::uuid
         WHERE clinic_id = $1::uuid AND id = $2::uuid AND ngung_luc IS NULL
        RETURNING id::text
        """,
        identity.clinic_id,
        a_id,
        identity.staff_id,
    )
    if v is None:
        raise ConflictError("Dòng gán đã bỏ hoặc không có — tải lại màn.")
    await _vet(conn, identity, "lab.partner_service_removed", "doi_tac_dich_vu", v)


async def luu_nguong(
    conn: asyncpg.Connection, identity: StaffIdentity, raw: object
) -> int:
    n = doc_so_ngay(raw, "Số ngày cảnh báo")
    if n is None or not 1 <= n <= 30:
        raise ValidationError("Số ngày cảnh báo: 1–30.")
    await conn.execute(
        """
        INSERT INTO public.xet_nghiem_cai_dat (clinic_id, nguong_lay_mau_ngay, sua_boi)
        VALUES ($1::uuid, $2, $3::uuid)
        ON CONFLICT (clinic_id) DO UPDATE
           SET nguong_lay_mau_ngay = EXCLUDED.nguong_lay_mau_ngay,
               sua_luc = now(), sua_boi = EXCLUDED.sua_boi
        """,
        identity.clinic_id,
        n,
        identity.staff_id,
    )
    await _vet(
        conn,
        identity,
        "lab.settings_saved",
        "xet_nghiem_cai_dat",
        identity.clinic_id,
        {"nguong_lay_mau_ngay": n},
    )
    return n
