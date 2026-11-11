"""Gmail G11 — GÁN LẠI thư email đã gắn nhầm khách (Tuyền 11/11/2026, tab Kết quả).

Lệnh BÙ, không sửa quá khứ: (1) tờ cũ — còn chờ xác nhận ⇒ Từ chối; đã hợp lệ / đã
gửi ⇒ Thu hồi (đúng lệnh có sẵn, kèm lý do; quyền Xác nhận kết quả như mọi lần thu hồi);
(2) thư trở về hàng chờ (database chỉ cho khi tờ cũ đã thu hồi / từ chối); (3) gán cho
khách đúng bằng ĐÚNG lệnh gán G10 (`gmail_goi_y._gan`: chỉ định đúng loại, không có thì
hồ sơ theo lượt). Bước 1 hỏng (vd bác sĩ đã bắt đầu đọc kết quả) ⇒ dừng, không đổi gì;
bước 3 hỏng ⇒ thư nằm ở hàng chờ "chưa khớp khách", gán tiếp được — không mất thư.
"""

from __future__ import annotations

from typing import Any, Final

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.tran import canh_bao_neu_day
from clinicai.services.tep_ket_qua_service import (
    TepKetQuaService,
    co_quyen_xac_nhan,
)
from clinicai.services.xet_nghiem import ghep_tay, gmail_goi_y
from clinicai.services.xet_nghiem.o_nhap import doc_ly_do

TRAN: Final = 50
#: Chữ trạng thái tờ cho màn (máy chủ tính, màn chỉ vẽ).
NHAN_TO: Final = {
    "CHO_XAC_NHAN": "Chờ xác nhận",
    "HOP_LE": "Hợp lệ",
}

_DA_GAN_SQL = f"""
SELECT t.id::text AS id, t.ten, t.email_tieu_de, t.email_nhan_luc, t.ghep_luc,
       d.ten AS ten_doi_tac, coalesce(s.full_name, 'Tự ghép') AS ghep_boi,
       k.id::text AS tep_id, k.xac_nhan_trang_thai, k.gui_luc IS NOT NULL AS da_gui,
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
   AND k.da_xoa_luc IS NULL AND k.xac_nhan_trang_thai IN ('CHO_XAC_NHAN', 'HOP_LE')
   AND ($2 = '' OR p.full_name_unaccent LIKE '%' || lower(replace(replace(
            public.f_unaccent($2), 'đ', 'd'), 'Đ', 'D')) || '%'
        OR (length(regexp_replace($2, '\\D', '', 'g')) >= 3
            AND p.phone_primary LIKE '%' || regexp_replace($2, '\\D', '', 'g') || '%')
        OR upper(p.patient_code) = upper($2) OR t.ten ILIKE '%' || $2 || '%')
 ORDER BY coalesce(t.ghep_luc, t.email_nhan_luc) DESC, t.id
 LIMIT {TRAN}
"""


async def da_gan(
    pool: asyncpg.Pool, identity: StaffIdentity, q: object
) -> dict[str, Any]:
    """Thư email ĐÃ gắn khách (tờ còn hiệu lực), mới nhất trước, lọc theo tên khách /
    SĐT / mã BN / tên tệp. `co_quyen_gan_lai`: người xem có quyền Xác nhận kết quả
    (thu hồi tờ cũ cần quyền đó) — màn chỉ đọc cờ này."""
    tu = " ".join(q.split())[:100] if isinstance(q, str) else ""
    async with pool.acquire() as conn:
        rows = await conn.fetch(_DA_GAN_SQL, identity.clinic_id, tu)
        co_quyen = await co_quyen_xac_nhan(conn, identity)
    canh_bao_neu_day("drive_tep", len(rows), TRAN, clinic_id=identity.clinic_id)
    return {
        "thu": [
            {**dict(r), "nhan_to": NHAN_TO.get(r["xac_nhan_trang_thai"], "")}
            for r in rows
        ],
        "co_quyen_gan_lai": co_quyen,
    }


async def gan_lai(
    pool: asyncpg.Pool, identity: StaffIdentity, data: dict[str, Any]
) -> dict[str, Any]:
    """Nút "Gán lại cho khách khác". CÙNG khoá của Gán tay / Từ chối / tự ghép."""
    ly = doc_ly_do(data.get("ly_do"))
    async with ghep_tay.khoa_tep(pool, data.get("drive_tep_id")):
        await _go(
            pool, identity, data.get("drive_tep_id"), data.get("clinic_patient_id"), ly
        )
        return await gmail_goi_y._gan(
            pool, identity, data.get("drive_tep_id"), data.get("clinic_patient_id")
        )


async def _go(
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    drive_tep_id: object,
    kh_moi: object,
    ly: str,
) -> None:
    """Bù tờ cũ + đưa thư về hàng chờ. Kiểm trước MỌI thứ có thể sai (thư, khách mới)
    để khỏi thu hồi tờ rồi mới phát hiện không gán lại được."""
    cid = identity.clinic_id
    try:
        r = await pool.fetchrow(
            "SELECT t.id::text AS id, t.nguon, k.id::text AS tep_id,"
            "       k.xac_nhan_trang_thai, k.clinic_patient_id::text AS kh"
            "  FROM drive_tep t JOIN tep_ket_qua k ON k.id = t.tep_ket_qua_id"
            " WHERE t.clinic_id = $1::uuid AND t.id = $2::uuid AND t.nguon = 'GMAIL'"
            "   AND k.da_xoa_luc IS NULL",
            cid,
            str(drive_tep_id),
        )
    except (asyncpg.DataError, ValueError):
        r = None
    if r is None:
        raise NotFoundError("Không thấy thư email đã gán này — tải lại màn.")
    if r["xac_nhan_trang_thai"] not in NHAN_TO:
        raise ConflictError("Tờ của thư này đã bị thu hồi / từ chối — tải lại màn.")
    if str(kh_moi or "") == r["kh"]:
        raise ConflictError("Thư đang gắn đúng khách này — chọn khách KHÁC.")
    await gmail_goi_y._khach(pool, cid, kh_moi)  # khách mới hỏng ⇒ dừng TRƯỚC khi bù
    cau = f"Gán nhầm khách, gán lại: {ly}"
    svc = TepKetQuaService(pool)
    if r["xac_nhan_trang_thai"] == "CHO_XAC_NHAN":
        await svc.xac_nhan_tep(
            identity=identity, tep_id=r["tep_id"], trang_thai="TU_CHOI", ly_do=cau
        )
    else:
        await svc.thu_hoi_tep(identity=identity, tep_id=r["tep_id"], ly_do=cau)
    n = await pool.execute(
        "UPDATE drive_tep SET tep_ket_qua_id = NULL, ghep_luc = NULL, ghep_boi = NULL"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid AND tep_ket_qua_id = $3::uuid",
        cid,
        r["id"],
        r["tep_id"],
    )
    if n != "UPDATE 1":
        raise ConflictError("Thư này vừa được xử lý ở chỗ khác — tải lại màn.")
