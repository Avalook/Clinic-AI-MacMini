"""Bàn XN — "Xem quá trình" của MỘT việc (bản mẫu 05/11): việc · lúc · ai.

Đọc thẳng từ các dòng SỰ VIỆC (luật 4 — không sửa quá khứ, nên mọi bước, kể cả bước bù,
còn nguyên dòng có `*_luc` / `*_boi`). Không đọc `domain_event` để khỏi phụ thuộc
payload, và không có sổ lịch sử thứ hai phải giữ khớp.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg

from clinicai.core.tran import canh_bao_neu_day

#: Trần dòng quá trình một việc (thực tế < 20; chạm trần ⇒ cảnh báo, không cắt im lặng).
TRAN = 200


#: Tiền kiểu Việt "300.000đ" — dấu phẩy trong mẫu `to_char` là chữ cố định (không theo
#: locale của DB như `G`), rồi đổi sang dấu chấm.
def _vnd(cot: str) -> str:
    return f"(replace(to_char({cot}, 'FM999,999,999,990'), ',', '.') || 'đ')"


#: $1 clinic · $2 service_order. Mỗi nhánh: (luc, viec, boi).
_QUA_TRINH_SQL = f"""
WITH b AS (
    SELECT x.tao_luc AS luc, 'Chỉ định xét nghiệm' AS viec, o.recorded_by AS boi
      FROM xet_nghiem_viec x
      JOIN service_order o ON o.id = x.service_order_id AND o.clinic_id = x.clinic_id
     WHERE x.clinic_id = $1::uuid AND x.service_order_id = $2::uuid
    UNION ALL
    SELECT x.cho_lay_mau_truoc_luc, 'Quản lý cho lấy mẫu trước: '
           || x.cho_lay_mau_truoc_ly_do, x.cho_lay_mau_truoc_boi
      FROM xet_nghiem_viec x
     WHERE x.clinic_id = $1::uuid AND x.service_order_id = $2::uuid
       AND x.cho_lay_mau_truoc_luc IS NOT NULL
    UNION ALL
    SELECT x.cho_lay_mau_go_luc, 'Gỡ cho lấy mẫu trước: ' || x.cho_lay_mau_go_ly_do,
           x.cho_lay_mau_go_boi
      FROM xet_nghiem_viec x
     WHERE x.clinic_id = $1::uuid AND x.service_order_id = $2::uuid
       AND x.cho_lay_mau_go_luc IS NOT NULL
    UNION ALL
    SELECT t.ghi_luc, 'Thu hộ ' || {_vnd("t.so_tien")} || ' (tiền mặt '
           || {_vnd("t.tien_mat")} || ', chuyển khoản '
           || {_vnd("t.chuyen_khoan")} || ')', t.ghi_boi
      FROM doi_tac_thanh_toan t
     WHERE t.clinic_id = $1::uuid AND t.service_order_id = $2::uuid
    UNION ALL
    SELECT t.huy_luc, 'Huỷ ghi nhận thu: ' || t.ly_do_huy, t.huy_boi
      FROM doi_tac_thanh_toan t
     WHERE t.clinic_id = $1::uuid AND t.service_order_id = $2::uuid
       AND t.huy_luc IS NOT NULL
    UNION ALL
    SELECT h.hoan_luc, 'Hoàn tiền ' || {_vnd("h.so_tien")} || ': ' || h.ly_do,
           h.hoan_boi
      FROM doi_tac_hoan_tien h
      JOIN doi_tac_thanh_toan t ON t.id = h.thanh_toan_id AND t.clinic_id = h.clinic_id
     WHERE h.clinic_id = $1::uuid AND t.service_order_id = $2::uuid
    UNION ALL
    SELECT m.lay_luc, 'Lấy mẫu, mã ống ' || m.ma_mau
           || coalesce(', hẹn trả ' || to_char(m.hen_tra_ngay, 'DD/MM'), ''), m.lay_boi
      FROM mau_xet_nghiem_viec mv
      JOIN mau_xet_nghiem m ON m.id = mv.mau_id
     WHERE mv.clinic_id = $1::uuid AND mv.service_order_id = $2::uuid
    UNION ALL
    SELECT m.huy_luc, 'Huỷ mẫu ' || m.ma_mau || ': ' || m.huy_ly_do, m.huy_boi
      FROM mau_xet_nghiem_viec mv
      JOIN mau_xet_nghiem m ON m.id = mv.mau_id
     WHERE mv.clinic_id = $1::uuid AND mv.service_order_id = $2::uuid
       AND m.huy_luc IS NOT NULL
    UNION ALL
    SELECT k.tai_len_luc, 'Kết quả về: ' || k.ten_hien_thi, k.tai_len_boi_staff_id
      FROM tep_ket_qua k
     WHERE k.clinic_id = $1::uuid AND k.service_order_id = $2::uuid
    UNION ALL
    SELECT k.da_xoa_luc, 'Xoá tệp kết quả: ' || coalesce(k.da_xoa_ly_do, ''),
           k.da_xoa_boi_staff_id
      FROM tep_ket_qua k
     WHERE k.clinic_id = $1::uuid AND k.service_order_id = $2::uuid
       AND k.da_xoa_luc IS NOT NULL
    UNION ALL
    SELECT mv.go_luc, 'Gỡ việc khỏi ống ' || m.ma_mau, mv.go_boi
      FROM mau_xet_nghiem_viec mv
      JOIN mau_xet_nghiem m ON m.id = mv.mau_id
     WHERE mv.clinic_id = $1::uuid AND mv.service_order_id = $2::uuid
       AND mv.go_luc IS NOT NULL AND m.huy_luc IS NULL
    UNION ALL
    SELECT k.gui_luc,
           CASE WHEN k.gui_kenh = 'NGOAI_HE_THONG'
                THEN 'Kết quả cũ — đã trả khách ngoài hệ thống'
                ELSE 'Đúng người, đã gửi khách qua ' || k.gui_kenh END,
           k.gui_boi_staff_id
      FROM tep_ket_qua k
     WHERE k.clinic_id = $1::uuid AND k.service_order_id = $2::uuid
       AND k.gui_luc IS NOT NULL
    UNION ALL
    SELECT k.xac_nhan_luc, 'Thu hồi tệp kết quả: ' || coalesce(k.xac_nhan_ly_do, ''),
           k.xac_nhan_boi_staff_id
      FROM tep_ket_qua k
     WHERE k.clinic_id = $1::uuid AND k.service_order_id = $2::uuid
       AND k.xac_nhan_trang_thai IN ('TU_CHOI', 'THU_HOI')
    UNION ALL
    SELECT d.dong_luc, 'Đối tác đã tự trả khách: ' || d.ly_do, d.dong_boi
      FROM xet_nghiem_dong d
     WHERE d.clinic_id = $1::uuid AND d.service_order_id = $2::uuid
    UNION ALL
    SELECT d.mo_lai_luc, 'Mở lại việc: ' || d.mo_lai_ly_do, d.mo_lai_boi
      FROM xet_nghiem_dong d
     WHERE d.clinic_id = $1::uuid AND d.service_order_id = $2::uuid
       AND d.mo_lai_luc IS NOT NULL
)
SELECT b.luc, b.viec, s.full_name AS ai
  FROM b
  LEFT JOIN staff s ON s.id = b.boi
 WHERE b.luc IS NOT NULL
 ORDER BY b.luc
 LIMIT {TRAN}
"""


async def doc(
    conn: asyncpg.Connection, cid: str, order_id: str
) -> list[dict[str, Any]]:
    """Mã việc rác ⇒ danh sách rỗng (không ném — luật backend)."""
    try:
        oid = str(UUID(str(order_id)))
    except ValueError:
        return []
    rows = await conn.fetch(_QUA_TRINH_SQL, cid, oid)
    canh_bao_neu_day("xet_nghiem_qua_trinh", len(rows), TRAN, clinic_id=cid)
    return [{"luc": r["luc"], "viec": r["viec"], "ai": r["ai"]} for r in rows]
