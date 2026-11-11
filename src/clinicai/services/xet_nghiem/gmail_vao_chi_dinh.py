"""Gmail G13 — CHUYỂN tờ email "gắn theo lượt khám" vào chỉ định (Tuyền 11/11/2026).

Thư về lúc khách chưa có chỉ định ⇒ tờ vào hồ sơ theo lượt (G8). Nhân viên nhập chỉ
định sau ⇒ ở màn Xác nhận kết quả bấm "Chuyển vào chỉ định", chọn đúng một chỉ định.
Tuyền chọn NÚT BẤM (người kiểm), không để máy tự chuyển (lượt có hai chỉ định cùng loại
thì máy đoán nhầm được). Người cũng chọn nhầm được ⇒ tờ ĐÃ ở một chỉ định (chưa gửi
khách) cũng chuyển sang chỉ định khác của cùng khách được — nút ở mục "Thư email đã gán"
(Việc của đối tác), chỗ đó cũng phủ tờ theo lượt do người gán (đã Hợp lệ, không còn ở
hàng Xác nhận kết quả).

Chỉ định nhận được = chỉ định đối tác của CHÍNH khách đó, đúng đối tác gửi thư, chưa có
tờ, trong khung của tự ghép (`ghep_khach.doc_chi_dinh`: ≤ 60 ngày trước thư, nhập muộn ≤
7 ngày cùng lượt đã check-in trước thư) — một câu SQL, không viết bản thứ hai.

Lệnh BÙ, cùng khuôn G11: kiểm TRƯỚC (tờ còn hiệu lực, chưa gửi khách, hồ sơ khách còn
dùng, chỉ định nằm trong danh sách) ⇒ tờ cũ Từ chối / Thu hồi với lý do "Chuyển vào
chỉ định: …" ⇒ thư về hàng chờ ⇒ gán lại CÙNG khách vào chỉ định đã chọn bằng ĐÚNG
lệnh gán G10 ⇒ phát `lab.email_result_moved_to_order`.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import XetNghiemThuVaoChiDinh
from clinicai.events.emit import emit_event, nguoi
from clinicai.services.tep_ket_qua_service import kiem_tra_quyen_xac_nhan
from clinicai.services.xet_nghiem import (
    ghep_khach,
    ghep_tay,
    gmail_gan_lai,
    gmail_goi_y,
)

_TO_SQL = """
SELECT t.id::text AS id, t.doi_tac_id::text AS doi_tac_id, t.email_nhan_luc,
       k.id::text AS tep_id, k.xac_nhan_trang_thai,
       k.clinic_patient_id::text AS kh,
       (k.da_xoa_luc IS NULL AND k.xac_nhan_trang_thai
            IN ('CHO_XAC_NHAN', 'HOP_LE')) AS con_hieu_luc,
       k.gui_luc IS NOT NULL AS da_gui
  FROM tep_ket_qua k JOIN drive_tep t
    ON t.tep_ket_qua_id = k.id AND t.clinic_id = k.clinic_id AND t.nguon = 'GMAIL'
 WHERE k.clinic_id = $1::uuid AND k.id = $2::uuid
"""


async def _to(pool: asyncpg.Pool, cid: str, tep_id: object) -> asyncpg.Record:
    """Tờ email còn hiệu lực, chưa gửi khách (theo lượt hoặc đã ở một chỉ định) —
    không thì 404/409."""
    try:
        r = await pool.fetchrow(_TO_SQL, cid, str(tep_id or ""))
    except (asyncpg.DataError, ValueError):
        r = None
    if r is None:
        raise NotFoundError("Không thấy tờ kết quả email này — tải lại màn.")
    if not r["con_hieu_luc"]:
        raise ConflictError("Tờ này đã bị từ chối / thu hồi — tải lại màn.")
    if r["da_gui"]:
        raise ConflictError(
            "Tờ này đã gửi khách — không chuyển được. Dùng Gán lại ở Việc của đối tác."
        )
    return r


async def _nhan_duoc(pool: asyncpg.Pool, cid: str, r: Any) -> list[ghep_khach.UngVien]:
    async with pool.acquire() as conn:
        ds = await ghep_khach.doc_chi_dinh(
            conn, cid, r["doi_tac_id"], r["email_nhan_luc"]
        )
    return [v for v in ds if v.clinic_patient_id == r["kh"] and not v.co_tep]


async def chi_dinh_nhan_duoc(
    pool: asyncpg.Pool, identity: StaffIdentity, tep_id: object
) -> dict[str, Any]:
    """Danh sách chỉ định tờ theo lượt chuyển vào được (rỗng ⇒ màn nói cách làm)."""
    await kiem_tra_quyen_xac_nhan(pool, identity=identity)
    r = await _to(pool, identity.clinic_id, tep_id)
    ds = await _nhan_duoc(pool, identity.clinic_id, r)
    return {
        "chi_dinh": [
            {"service_order_id": v.order_id, "ten_dich_vu": v.ten_dich_vu} for v in ds
        ]
    }


async def vao_chi_dinh(
    pool: asyncpg.Pool, identity: StaffIdentity, data: dict[str, Any]
) -> dict[str, Any]:
    """Nút "Chuyển vào chỉ định". CÙNG khoá của Gán tay / Từ chối / tự ghép."""
    cid = identity.clinic_id
    await kiem_tra_quyen_xac_nhan(pool, identity=identity)
    dau = await _to(pool, cid, data.get("tep_id"))
    async with ghep_tay.khoa_tep(pool, dau["id"]):
        r = await _to(pool, cid, data.get("tep_id"))  # đọc lại TRONG khoá
        chon = str(data.get("service_order_id") or "")
        v = next(
            (v for v in await _nhan_duoc(pool, cid, r) if v.order_id == chon), None
        )
        if v is None:
            raise ConflictError(
                "Chỉ định này không nhận được tờ (khác khách / khác đối tác / đã có kết"
                " quả) — tải lại màn."
            )
        # Hồ sơ khách đã gộp / ngưng ⇒ dừng TRƯỚC khi đụng tờ cũ (G11 cũng vậy).
        await gmail_goi_y._khach(pool, cid, r["kh"])
        await gmail_gan_lai.bu_va_thao(
            pool, identity, r, f"Chuyển vào chỉ định: {v.ten_dich_vu}"
        )
        kq = await gmail_goi_y._gan(
            pool, identity, r["id"], r["kh"], dich=(v.order_id, v.visit_id, None)
        )
    async with pool.acquire() as conn:
        await emit_event(
            conn,
            ten="lab.email_result_moved_to_order",
            clinic_id=cid,
            aggregate_id=r["id"],
            payload=XetNghiemThuVaoChiDinh(
                drive_tep_id=r["id"],
                doi_tac_id=r["doi_tac_id"],
                tep_cu_id=r["tep_id"],
                tep_moi_id=str(kq["tep_id"]),
                service_order_id=v.order_id,
                clinic_patient_id=r["kh"],
            ),
            boi=nguoi(identity),
        )
    return kq
