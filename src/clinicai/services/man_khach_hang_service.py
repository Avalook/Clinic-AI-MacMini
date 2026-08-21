"""Gói dữ liệu làm giàu cho màn Quản lý khách hàng — MỘT vòng thay cho mười.

Vì sao tồn tại (Lát 2 của lộ trình chịu tải, chốt với Tuyền 22/08/2026):
trước đây trang /customers tự đi mười vòng PostgREST cho phần làm giàu — lịch
hẹn, ca trực, trạng thái, việc mở, tệp, phản hồi, hẹn gọi lại, sổ tương tác,
sổ cũ, lượt khám — mỗi vòng kèm nghi lễ BEGIN/set_config/COMMIT riêng. Đo một
lần mở trang: 73 câu SQL thì 44 câu là nghi lễ. Gói về đây, cùng mười câu ấy
chạy trên MỘT kết nối, không nghi lễ, một vòng HTTP.

CHỐT CHỐNG "GIẤU VÒNG SAU CÁNH CỬA" (chị Thu cảnh báo 22/08): consolidation
thật là số CÂU SQL MỖI TRANG phải giảm, không phải chỉ số lời gọi HTTP. Ở đây
nghi lễ biến mất (mười giao dịch PostgREST → một kết nối asyncpg) và mười câu
nghiệp vụ giữ nguyên hình — đo lại sau deploy phải ra ~73 → ~30 câu/trang.

MỘT KẾT NỐI, CHẠY TUẦN TỰ — không asyncio.gather mười câu trên mười kết nối:
pool của api trần 10, một request ngốn 10 kết nối là 100 người mở màn cùng lúc
bóp chết mọi endpoint khác. Mười câu × vài ms tuần tự ≈ 20–30ms, rẻ hơn nhiều
so với cái giá cạn pool.

HÌNH DẠNG TRẢ VỀ BẮT CHƯỚC POSTGREST TỪNG TRƯỜNG — kể cả lồng `service:{name}`,
`doctor:{full_name}`, `staff:{full_name}` — để code dựng map trong page.tsx giữ
nguyên từng byte. Đổi hình ở đây là đổi cả màn; có test canh hình.
"""

from __future__ import annotations

from typing import Any

import asyncpg

# Trần số dòng GIỮ NGUYÊN từ bản PostgREST — không phải số thiêng, chỉ là không
# đổi hai thứ trong một lần vá. Phân trang 50 khách khiến các trần này gần như
# không bao giờ chạm.
_TRAN_LICH = 3000
_TRAN_TEP = 300
_TRAN_TUONG_TAC = 1000


class ManKhachHangService:
    """Đọc một lần mọi dữ liệu làm giàu của màn Quản lý khách hàng."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def goi_du_lieu(
        self,
        *,
        clinic_id: str,
        ids: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        """Mười khối dữ liệu cho các khách đang hiển thị.

        `ids` do CHÍNH máy chủ Next đưa sang (kết quả truy vấn patient đã
        phân trang) — nhưng mọi câu dưới đây vẫn tự khoá `clinic_id`: một id
        của phòng khám khác lọt vào thì ra 0 dòng, không ra dữ liệu người ta.
        """
        if not ids:
            return {khoi: [] for khoi in _CAC_KHOI}

        async with self._pool.acquire() as conn:
            appts = await conn.fetch(
                """
                SELECT a.clinic_patient_id, a.id, a.slot_start, a.status,
                       a.created_at, a.cancelled_at, a.ly_do_huy_ma,
                       a.cancellation_reason, a.service_type_id, a.doctor_id,
                       a.bac_si_da_go_id, a.location_id, a.booking_channel,
                       a.lich_truoc_id,
                       st.name AS ten_dich_vu, bs.full_name AS ten_bac_si
                  FROM appointment a
                  LEFT JOIN service_type st ON st.id = a.service_type_id
                  LEFT JOIN staff bs ON bs.id = a.doctor_id
                 WHERE a.clinic_id = $1::uuid
                   AND a.clinic_patient_id = ANY($2::uuid[])
                 ORDER BY a.slot_start
                 LIMIT $3
                """,
                clinic_id,
                ids,
                _TRAN_LICH,
            )
            ca_truc = await conn.fetch(
                """
                SELECT staff_id, work_date FROM work_roster
                 WHERE clinic_id = $1::uuid
                   AND station = 'LICH_KHAM'
                   AND staff_id IS NOT NULL
                   AND work_date >=
                       (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date - 1
                 LIMIT 5000
                """,
                clinic_id,
            )
            trang_thai = await conn.fetch(
                """
                SELECT clinic_patient_id, trang_thai, nhan, han_xu_ly, qua_han,
                       so_viec_mo, co_viec_qua_han, appointment_id, da_xac_nhan
                  FROM v_trang_thai_cskh
                 WHERE clinic_id = $1::uuid
                   AND clinic_patient_id = ANY($2::uuid[])
                """,
                clinic_id,
                ids,
            )
            viec_mo = await conn.fetch(
                """
                SELECT clinic_patient_id, trang_thai, nhan, uu_tien, han_xu_ly,
                       qua_han, appointment_id
                  FROM v_viec_cskh
                 WHERE clinic_id = $1::uuid
                   AND clinic_patient_id = ANY($2::uuid[])
                 LIMIT $3
                """,
                clinic_id,
                ids,
                _TRAN_LICH,
            )
            tep = await conn.fetch(
                """
                SELECT t.id, t.clinic_patient_id, t.appointment_id,
                       t.ten_hien_thi, t.loai_tep, t.mime, t.so_byte,
                       t.tai_len_luc, t.gui_luc, t.gui_kenh,
                       nv.full_name AS ten_nhan_vien
                  FROM tep_ket_qua t
                  LEFT JOIN staff nv ON nv.id = t.tai_len_boi_staff_id
                 WHERE t.clinic_id = $1::uuid
                   AND t.clinic_patient_id = ANY($2::uuid[])
                 ORDER BY t.tai_len_luc DESC
                 LIMIT $3
                """,
                clinic_id,
                ids,
                _TRAN_TEP,
            )
            phan_hoi = await conn.fetch(
                """
                SELECT p.id, p.clinic_patient_id, p.loai, p.noi_dung,
                       p.trang_thai, p.huong_xu_ly, p.created_at,
                       nv.full_name AS ten_nhan_vien
                  FROM phan_hoi_khach p
                  LEFT JOIN staff nv ON nv.id = p.nguoi_tiep_nhan_staff_id
                 WHERE p.clinic_id = $1::uuid
                   AND p.clinic_patient_id = ANY($2::uuid[])
                 ORDER BY p.created_at DESC
                 LIMIT $3
                """,
                clinic_id,
                ids,
                _TRAN_TEP,
            )
            hen_goi_lai = await conn.fetch(
                """
                SELECT h.id, h.clinic_patient_id, h.ngay_goi, h.gio_goi,
                       h.ly_do, h.created_at, nv.full_name AS ten_nhan_vien
                  FROM hen_goi_lai h
                  LEFT JOIN staff nv ON nv.id = h.tao_boi_staff_id
                 WHERE h.clinic_id = $1::uuid
                   AND h.clinic_patient_id = ANY($2::uuid[])
                   AND h.dong_luc IS NULL
                 ORDER BY h.ngay_goi
                 LIMIT $3
                """,
                clinic_id,
                ids,
                _TRAN_TEP,
            )
            tuong_tac = await conn.fetch(
                """
                SELECT t.id, t.clinic_patient_id, t.appointment_id,
                       t.xay_ra_luc, t.loai, t.kenh, t.ket_qua,
                       t.khach_xac_nhan, t.noi_dung, t.trang_thai_ma,
                       t.huy_luc, nv.full_name AS ten_nhan_vien
                  FROM tuong_tac_cskh t
                  LEFT JOIN staff nv ON nv.id = t.nhan_vien_staff_id
                 WHERE t.clinic_id = $1::uuid
                   AND t.clinic_patient_id = ANY($2::uuid[])
                 ORDER BY t.xay_ra_luc DESC
                 LIMIT $3
                """,
                clinic_id,
                ids,
                _TRAN_TUONG_TAC,
            )
            cskh = await conn.fetch(
                """
                SELECT id, clinic_patient_id, category, step, status,
                       description, deadline_at, source_created_at,
                       created_by_text, last_edited_by_text
                  FROM cskh_action
                 WHERE clinic_id = $1::uuid
                   AND clinic_patient_id = ANY($2::uuid[])
                 ORDER BY source_created_at DESC
                 LIMIT $3
                """,
                clinic_id,
                ids,
                _TRAN_TUONG_TAC,
            )
            visits = await conn.fetch(
                """
                SELECT appointment_id, checked_in_at, closed_at, finalized_at
                  FROM visit
                 WHERE clinic_id = $1::uuid
                   AND clinic_patient_id = ANY($2::uuid[])
                 LIMIT $3
                """,
                clinic_id,
                ids,
                _TRAN_LICH,
            )

        return {
            "appts": [_lich(r) for r in appts],
            "ca_truc": [dict(r) for r in ca_truc],
            "trang_thai": [dict(r) for r in trang_thai],
            "viec_mo": [dict(r) for r in viec_mo],
            "tep": [_kem_nhan_vien(r) for r in tep],
            "phan_hoi": [_kem_nhan_vien(r) for r in phan_hoi],
            "hen_goi_lai": [_kem_nhan_vien(r) for r in hen_goi_lai],
            "tuong_tac": [_kem_nhan_vien(r) for r in tuong_tac],
            "cskh": [dict(r) for r in cskh],
            "visits": [dict(r) for r in visits],
        }


_CAC_KHOI = (
    "appts",
    "ca_truc",
    "trang_thai",
    "viec_mo",
    "tep",
    "phan_hoi",
    "hen_goi_lai",
    "tuong_tac",
    "cskh",
    "visits",
)


def _lich(r: asyncpg.Record) -> dict[str, Any]:
    """Một dòng lịch hẹn, LỒNG `service`/`doctor` y như PostgREST.

    page.tsx đọc `a.service?.name` và `a.doctor?.full_name` — đổi sang cột
    phẳng là phải sửa cả chuỗi dựng map phía đó. Bắt chước hình cũ rẻ hơn và
    an toàn hơn viết lại phần đọc.
    """
    d = dict(r)
    ten_dv = d.pop("ten_dich_vu", None)
    ten_bs = d.pop("ten_bac_si", None)
    d["service"] = {"name": ten_dv} if ten_dv else None
    d["doctor"] = {"full_name": ten_bs} if ten_bs else None
    return d


def _kem_nhan_vien(r: asyncpg.Record) -> dict[str, Any]:
    """Lồng `staff:{full_name}` như PostgREST embed."""
    d = dict(r)
    ten = d.pop("ten_nhan_vien", None)
    d["staff"] = {"full_name": ten} if ten else None
    return d
