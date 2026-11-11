"""Gmail G11 — GÁN LẠI thư email đã gắn nhầm khách (Tuyền 11/11/2026, tab Kết quả).

Lệnh BÙ, không sửa quá khứ: (0) kiểm TRƯỚC mọi thứ đoán trước được — thư, khách mới
(khác khách đang gắn, hồ sơ đang dùng), CHỖ tờ mới sẽ vào (`gmail_goi_y._dich`); (1) tờ
cũ còn hiệu lực — chờ xác nhận ⇒ Từ chối, hợp lệ / đã gửi ⇒ Thu hồi (đúng lệnh có sẵn,
kèm lý do; quyền Xác nhận kết quả như mọi lần thu hồi); tờ cũ ĐÃ bị thu hồi / từ chối /
xoá ở chỗ khác ⇒ bỏ qua bước này (thư không được kẹt); (2) thư trở về hàng chờ
(database chỉ cho khi tờ cũ đã thu hồi / từ chối); (3) gán khách đúng bằng ĐÚNG lệnh gán
G10 (`gmail_goi_y._gan`); (4) phát `lab.email_result_reassigned`. Bước 1 hỏng (vd bác sĩ
đã bắt đầu đọc kết quả) ⇒ không đổi gì; bước 3 hỏng (tranh chấp / lỗi đọc tệp) ⇒ thư
nằm ở hàng chờ "Tệp Drive / Email chưa khớp khách" (lý do cũ của dòng), gán tiếp được
— không mất thư.
"""

from __future__ import annotations

from typing import Any, Final

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.tran import canh_bao_neu_day
from clinicai.events.catalogue import XetNghiemThuGanLai
from clinicai.events.emit import emit_event, nguoi
from clinicai.services.tep_ket_qua_service import (
    TepKetQuaService,
    co_quyen_xac_nhan,
    kiem_tra_quyen_xac_nhan,
)
from clinicai.services.xet_nghiem import ghep_khach, ghep_tay, gmail_doc, gmail_goi_y
from clinicai.services.xet_nghiem.o_nhap import doc_ly_do

TRAN: Final = 50
#: Chữ trạng thái tờ cho màn (máy chủ tính, màn chỉ vẽ). Ngoài bảng = tờ đã mất hiệu
#: lực ở chỗ khác (thu hồi / từ chối / xoá) mà thư chưa gán lại.
NHAN_TO: Final = {"CHO_XAC_NHAN": "Chờ xác nhận", "HOP_LE": "Hợp lệ"}
NHAN_MAT_HIEU_LUC: Final = "Tờ đã thu hồi / từ chối — chưa gán lại"

_DA_GAN_SQL = f"""
SELECT t.id::text AS id, t.ten, t.email_tieu_de, t.email_nhan_luc, t.ghep_luc,
       d.ten AS ten_doi_tac, coalesce(s.full_name, 'Tự ghép') AS ghep_boi,
       k.id::text AS tep_id, k.loai_tep, k.xac_nhan_trang_thai,
       k.da_xoa_luc IS NOT NULL AS da_xoa, k.gui_luc IS NOT NULL AS da_gui,
       k.service_order_id IS NOT NULL AS vao_chi_dinh,
       coalesce(o.service_name, 'Hồ sơ theo lượt khám') AS gan_vao,
       p.clinic_patient_id::text AS clinic_patient_id, p.full_name AS ten_khach,
       p.patient_code, p.phone_primary
  FROM drive_tep t
  JOIN doi_tac d ON d.id = t.doi_tac_id AND d.clinic_id = t.clinic_id
  JOIN tep_ket_qua k ON k.id = t.tep_ket_qua_id AND k.clinic_id = t.clinic_id
  JOIN patient p ON p.clinic_patient_id = k.clinic_patient_id
                AND p.clinic_id = k.clinic_id
  LEFT JOIN service_order o ON o.id = k.service_order_id AND o.clinic_id = k.clinic_id
  LEFT JOIN staff s ON s.id = t.ghep_boi
 WHERE t.clinic_id = $1::uuid AND t.nguon = 'GMAIL'
   AND (cardinality($2::uuid[]) = 0 AND $3 = ''
        OR k.clinic_patient_id = ANY($2::uuid[])
        OR ($3 <> '' AND strpos(lower(t.ten), lower($3)) > 0))
 ORDER BY (k.da_xoa_luc IS NULL
           AND k.xac_nhan_trang_thai IN ('CHO_XAC_NHAN', 'HOP_LE')),
          coalesce(t.ghep_luc, t.email_nhan_luc) DESC, t.id
 LIMIT {TRAN}
"""


def nhan_to(trang_thai: object, da_xoa: object) -> str:
    """HÀM THUẦN: chữ trạng thái tờ của thư đã gán."""
    if da_xoa or trang_thai not in NHAN_TO:
        return NHAN_MAT_HIEU_LUC
    return NHAN_TO[str(trang_thai)]


async def da_gan(
    pool: asyncpg.Pool, identity: StaffIdentity, q: object
) -> dict[str, Any]:
    """Thư email ĐÃ gắn khách — tờ đã mất hiệu lực (chưa gán lại) lên đầu, rồi mới nhất
    trước. Lọc: khách theo ĐÚNG câu tìm khách chung (`tim_khach_conn`) hoặc tên tệp.
    `co_quyen_gan_lai`: người xem có quyền Xác nhận kết quả (thu hồi tờ cũ cần)."""
    from clinicai.services.ban_le_service import chuan_tu_khoa, tim_khach_conn

    tu = chuan_tu_khoa(q)
    async with pool.acquire() as conn:
        khach = [
            k["clinic_patient_id"]
            for k in await tim_khach_conn(conn, identity.clinic_id, tu)
        ]
        rows = await conn.fetch(_DA_GAN_SQL, identity.clinic_id, khach, tu)
        co_quyen = await co_quyen_xac_nhan(conn, identity)
    canh_bao_neu_day("drive_tep", len(rows), TRAN, clinic_id=identity.clinic_id)
    ra = []
    for r in rows:
        d = dict(r)
        d["nhan_to"] = nhan_to(d.pop("xac_nhan_trang_thai"), d.pop("da_xoa"))
        # Đã gửi khách mà gắn nhầm ⇒ khách ấy đã nhận kết quả người khác: nói rõ.
        d["canh_bao"] = (
            f"{r['ten_khach']} đã nhận tờ này — gán lại sẽ thu hồi, cần báo khách."
            if r["da_gui"] and d["nhan_to"] != NHAN_MAT_HIEU_LUC
            else None
        )
        ra.append(d)
    return {"thu": ra, "co_quyen_gan_lai": co_quyen}


async def gan_lai(
    pool: asyncpg.Pool, identity: StaffIdentity, data: dict[str, Any]
) -> dict[str, Any]:
    """Nút "Gán lại cho khách khác". CÙNG khoá của Gán tay / Từ chối / tự ghép."""
    ly = doc_ly_do(data.get("ly_do"))
    async with ghep_tay.khoa_tep(pool, data.get("drive_tep_id")):
        cu = await _go(
            pool, identity, data.get("drive_tep_id"), data.get("clinic_patient_id"), ly
        )
        kq = await gmail_goi_y._gan(
            pool, identity, data.get("drive_tep_id"), data.get("clinic_patient_id")
        )
    async with pool.acquire() as conn:
        await emit_event(
            conn,
            ten="lab.email_result_reassigned",
            clinic_id=identity.clinic_id,
            aggregate_id=cu["id"],
            payload=XetNghiemThuGanLai(
                drive_tep_id=cu["id"],
                doi_tac_id=cu["doi_tac_id"],
                tep_cu_id=cu["tep_id"],
                tep_moi_id=str(kq["tep_id"]),
                clinic_patient_id_cu=cu["kh"],
                clinic_patient_id_moi=cu["kh_moi"],
            ),
            boi=nguoi(identity),
        )
    return kq


async def _go(
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    drive_tep_id: object,
    kh_moi: object,
    ly: str,
) -> dict[str, Any]:
    """Kiểm trước + bù tờ cũ + đưa thư về hàng chờ. Trả dòng thư (tờ cũ, khách cũ)."""
    cid = identity.clinic_id
    r = await _thu(pool, cid, drive_tep_id)
    kh = await gmail_goi_y._khach(pool, cid, kh_moi)  # chuẩn hoá id TRƯỚC khi so
    if kh == r["kh"]:
        raise ConflictError("Thư đang gắn đúng khách này — chọn khách KHÁC.")
    # Chỗ tờ mới sẽ vào — lỗi đoán trước được thì dừng TRƯỚC khi thu hồi tờ cũ.
    loai = gmail_doc.loai_ket_qua(ghep_khach.chu_pdf(await ghep_tay._byte(r)))
    await gmail_goi_y._dich(pool, cid, r["doi_tac_id"], kh, r["email_nhan_luc"], loai)
    await bu_va_thao(pool, identity, r, f"Gán nhầm khách, gán lại: {ly}")
    return {**dict(r), "kh_moi": kh}


async def bu_va_thao(
    pool: asyncpg.Pool, identity: StaffIdentity, r: asyncpg.Record, cau: str
) -> None:
    """Bù tờ cũ (chờ xác nhận ⇒ Từ chối, hợp lệ ⇒ Thu hồi, kèm `cau`) rồi đưa thư về
    hàng chờ. Dùng chung G11 (gán lại) + G13 (chuyển vào chỉ định). Gọi TRONG khoá."""
    if not r["con_hieu_luc"]:
        # Tờ đã mất hiệu lực ở chỗ khác: không cần bù, nhưng VẪN đòi quyền như mọi lần
        # gán lại (màn ẩn nút theo cùng quyền — không có lối API vòng).
        await kiem_tra_quyen_xac_nhan(pool, identity=identity)
    else:
        svc = TepKetQuaService(pool)
        if r["xac_nhan_trang_thai"] == "CHO_XAC_NHAN":
            await svc.xac_nhan_tep(
                identity=identity, tep_id=r["tep_id"], trang_thai="TU_CHOI", ly_do=cau
            )
        else:
            await svc.thu_hoi_tep(identity=identity, tep_id=r["tep_id"], ly_do=cau)
    cid = identity.clinic_id
    n = await pool.execute(
        "UPDATE drive_tep SET tep_ket_qua_id = NULL, ghep_luc = NULL, ghep_boi = NULL"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid AND tep_ket_qua_id = $3::uuid",
        cid,
        r["id"],
        r["tep_id"],
    )
    if n != "UPDATE 1":
        raise ConflictError("Thư này vừa được xử lý ở chỗ khác — tải lại màn.")


async def _thu(pool: asyncpg.Pool, cid: str, drive_tep_id: object) -> asyncpg.Record:
    try:
        r = await pool.fetchrow(
            "SELECT t.id::text AS id, t.doi_tac_id::text AS doi_tac_id, t.nguon,"
            "       t.khoa, t.vi_tri, t.file_id, t.email_nhan_luc,"
            "       k.id::text AS tep_id, k.xac_nhan_trang_thai,"
            "       k.clinic_patient_id::text AS kh,"
            "       (k.da_xoa_luc IS NULL AND k.xac_nhan_trang_thai"
            "            IN ('CHO_XAC_NHAN', 'HOP_LE')) AS con_hieu_luc"
            "  FROM drive_tep t JOIN tep_ket_qua k ON k.id = t.tep_ket_qua_id"
            " WHERE t.clinic_id = $1::uuid AND t.id = $2::uuid AND t.nguon = 'GMAIL'",
            cid,
            str(drive_tep_id),
        )
    except (asyncpg.DataError, ValueError):
        r = None
    if r is None:
        raise NotFoundError("Không thấy thư email đã gán này — tải lại màn.")
    return r
