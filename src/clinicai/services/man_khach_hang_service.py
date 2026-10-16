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

import json
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

import asyncpg

from clinicai.core.trang_thai_lich import trang_thai_hien_thi
from clinicai.services.hanh_trinh_khach_service import dang_o_cac_luot
from clinicai.services.nhan_luot import doc_nhan_luot, tra_nhan

# Trần số dòng GIỮ NGUYÊN từ bản PostgREST — không phải số thiêng, chỉ là không
# đổi hai thứ trong một lần vá. Phân trang 50 khách khiến các trần này gần như
# không bao giờ chạm.
_TRAN_LICH = 3000
_TRAN_TEP = 300
_TRAN_TUONG_TAC = 1000

#: Kết quả cuộc gọi ĐÓNG việc "Gọi điện xác nhận" (CHO_DAT_LICH) của khách chỉ
#: lưu hồ sơ (Tuyền 15/10/2026: CSKH ghi "đã gọi" thì nhãn mất). Không nghe máy /
#: không liên lạc được / hẹn gọi lại sau thì việc CÒN MỞ — vẫn phải gọi tiếp.
#: Hoàn tác (`huy_luc`) đưa nhãn trở lại vì dòng sổ thôi được tính.
KET_QUA_DONG_CHO_DAT_LICH = ("DA_LIEN_HE", "TU_CHOI", "BO_QUA")


class ManKhachHangService:
    """Đọc một lần mọi dữ liệu làm giàu của màn Quản lý khách hàng."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def goi_du_lieu(
        self,
        *,
        clinic_id: str,
        ids: list[str],
    ) -> dict[str, list[Any]]:
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
                       a.lich_truoc_id, a.notes,
                       st.name AS ten_dich_vu, bs.full_name AS ten_bac_si,
                       -- NHÃN TRẠNG THÁI (30/09/2026): đã về hay chưa là
                       -- chuyện của LƯỢT — `trang_thai_hien_thi`.
                       lv.visit_id::text AS luot_id, lv.status AS trang_thai_luot,
                       lv.checked_in_at AS den_luc, lv.closed_at AS ve_luc,
                       (lv.exam_completed_at IS NOT NULL) AS kham_xong,
                       lv.exam_completed_at AS kham_xong_luc
                  FROM appointment a
                  LEFT JOIN service_type st ON st.id = a.service_type_id
                  LEFT JOIN staff bs ON bs.id = a.doctor_id
                  LEFT JOIN visit lv
                    ON lv.appointment_id = a.id AND lv.clinic_id = a.clinic_id
                 WHERE a.clinic_id = $1::uuid
                   AND a.clinic_patient_id = ANY($2::uuid[])
                 ORDER BY a.slot_start
                 LIMIT $3
                """,
                clinic_id,
                ids,
                _TRAN_LICH,
            )
            # CA TRỰC + TUẦN ĐÃ CÔNG BỐ trong CÙNG một câu (giữ mười câu / một
            # kết nối). "Mất bác sĩ" chỉ có nghĩa khi tuần đã công bố lịch trực:
            # chưa công bố là đặt tự do (luật 15/09), và bảng nháp thiếu ca KHÔNG
            # phải bác sĩ nghỉ (16/09/2026). Dòng tuần có staff_id NULL.
            # Kèm CƠ SỞ của ca (vị trí → phòng → cơ sở; NULL = mọi cơ sở): ca ở
            # Kim Ngưu không giữ được lịch ở Hào Nam (08/10/2026).
            ca_truc_va_tuan = await conn.fetch(
                """
                SELECT staff_id, work_date, NULL::date AS tuan_cong_bo,
                       (SELECT r.location_id
                          FROM vi_tri_lam_viec v
                          JOIN clinic_room r ON r.id = v.room_id
                         WHERE v.clinic_id = work_roster.clinic_id
                           AND v.code = work_roster.station) AS location_id
                  FROM work_roster
                 WHERE clinic_id = $1::uuid
                   AND public.la_ca_kham_bac_si(clinic_id, station)
                   AND staff_id IS NOT NULL
                   AND work_date >=
                       (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date - 1
                UNION ALL
                SELECT NULL::uuid, NULL::date, rw.week_start, NULL::uuid
                  FROM roster_week rw
                 WHERE rw.clinic_id = $1::uuid
                   AND rw.week_start >=
                       (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date - 7
                 LIMIT 5000
                """,
                clinic_id,
            )
            ca_truc = [r for r in ca_truc_va_tuan if r["staff_id"] is not None]
            tuan_cong_bo = [
                r["tuan_cong_bo"]
                for r in ca_truc_va_tuan
                if r["tuan_cong_bo"] is not None
            ]
            # MỘT LẦN ĐỌC `v_viec_cskh` cho cả hai khối (viec_mo + trang_thai).
            # View này gọi `lich_vuot_suc_chua()` — hàm KHÔNG nhận tham số, duyệt
            # mọi lịch tương lai có bác sĩ và gọi `resolve_effective_cap` từng
            # dòng (đo 16/10/2026: 2.000 lịch tương lai ≈ 225ms MỖI lần), và
            # Postgres không đẩy `clinic_patient_id = ANY(...)` xuống được. Bản
            # cũ đọc `v_trang_thai_cskh` (view ấy đọc `v_viec_cskh` HAI lần: `dem`
            # + `gap_nhat`, cộng NOT EXISTS lồng thêm hai lần ở nhánh CHO_DAT_LICH)
            # rồi đọc `v_viec_cskh` lần nữa: 3–5 lần gọi hàm một request. Nay
            # đúng một lần; trạng thái mỗi khách suy từ chính các dòng này bằng
            # `trang_thai_tu_viec` (đúng luật của `v_trang_thai_cskh` — test
            # canh bằng cách so với chính view). Không LIMIT ở đây: trạng thái và
            # "khách còn việc" phải tính trên TOÀN BỘ việc; trần `_TRAN_LICH`
            # chỉ áp cho khối `viec_mo` trả ra, như trước.
            viec = await conn.fetch(
                """
                SELECT v.clinic_patient_id, v.trang_thai, v.nhan, v.uu_tien,
                       v.han_xu_ly, v.qua_han, v.appointment_id,
                       coalesce(xn.co, false) AS da_xac_nhan
                  FROM v_viec_cskh v
                  LEFT JOIN LATERAL (
                      SELECT true AS co FROM tuong_tac_cskh t
                       WHERE t.appointment_id = v.appointment_id
                         AND t.khach_xac_nhan AND t.huy_luc IS NULL
                       LIMIT 1
                  ) xn ON TRUE
                 WHERE v.clinic_id = $1::uuid
                   AND v.clinic_patient_id = ANY($2::uuid[])
                """,
                clinic_id,
                ids,
            )
            trang_thai = trang_thai_tu_viec(viec)
            cho_dat_lich = await conn.fetch(
                """
                SELECT p.clinic_patient_id, 'CHO_DAT_LICH' AS trang_thai,
                       'Gọi điện xác nhận' AS nhan, NULL::date AS han_xu_ly,
                       false AS qua_han, 1::bigint AS so_viec_mo,
                       false AS co_viec_qua_han, NULL::uuid AS appointment_id,
                       false AS da_xac_nhan
                  FROM patient p
                 WHERE p.clinic_id = $1::uuid
                   AND p.clinic_patient_id = ANY($2::uuid[])
                   -- Khách đã có việc nào khác thì việc ấy thắng (cùng luật với
                   -- NOT EXISTS lồng view trạng thái của bản cũ — không đọc lại
                   -- view, danh sách khách có việc lấy từ khối trên).
                   AND p.clinic_patient_id <> ALL($4::uuid[])
                   -- Chỉ hồ sơ nhập từ màn tiếp nhận, không gom dữ liệu nhập cũ.
                   AND EXISTS (
                       SELECT 1 FROM event_log e
                        WHERE e.clinic_id = p.clinic_id
                          AND e.aggregate_id = p.clinic_patient_id
                          AND e.event_type = 'patient.created'
                          AND e.source = 'api:patient-intake')
                   -- Kiểm toàn bộ lịch sử, không dựa vào khối appts có LIMIT.
                   AND NOT EXISTS (
                       SELECT 1 FROM appointment a
                        WHERE a.clinic_id = p.clinic_id
                          AND a.clinic_patient_id = p.clinic_patient_id)
                   AND NOT EXISTS (
                       SELECT 1 FROM visit v
                        WHERE v.clinic_id = p.clinic_id
                          AND v.clinic_patient_id = p.clinic_patient_id)
                   -- CSKH đã gọi xong (và chưa hoàn tác) thì hết việc.
                   AND NOT EXISTS (
                       SELECT 1 FROM tuong_tac_cskh c
                        WHERE c.clinic_id = p.clinic_id
                          AND c.clinic_patient_id = p.clinic_patient_id
                          AND c.trang_thai_ma = 'CHO_DAT_LICH'
                          AND c.huy_luc IS NULL
                          AND c.ket_qua = ANY($3::text[]))
                """,
                clinic_id,
                ids,
                list(KET_QUA_DONG_CHO_DAT_LICH),
                list({r["clinic_patient_id"] for r in viec}),
            )
            trang_thai += [dict(r) for r in cho_dat_lich]
            tep = await conn.fetch(
                """
                SELECT t.id, t.clinic_patient_id, t.appointment_id,
                       t.ten_hien_thi, t.loai_tep, t.mime, t.so_byte,
                       t.tai_len_luc, t.gui_luc, t.gui_kenh,
                       t.cho_phep_gui_luc, t.xac_nhan_trang_thai,
                       bs.full_name AS cho_phep_gui_boi,
                       nv.full_name AS ten_nhan_vien,
                       -- TỆP NÀY CÓ PHẢI KẾT QUẢ XÉT NGHIỆM không (17/09/2026):
                       -- tệp siêu âm / thủ thuật không được bật ô "Có kết quả
                       -- xét nghiệm" ở màn CSKH. Tệp không gắn chỉ định (CSKH tải
                       -- tay) vẫn tính như trước.
                       (t.service_order_id IS NULL
                        OR coalesce(nd.lam_ben_ngoai, false)
                        OR so.node_code LIKE 'DICHVU-LAYMAU%'
                        OR so.node_code LIKE 'DICHVU-XETNGHIEM%'
                        OR so.node_code LIKE 'DICHVU-SANGLOC%')
                           AS la_ket_qua_xet_nghiem
                  FROM v_tep_ket_qua_hieu_luc t
                  LEFT JOIN service_order so
                    ON so.id = t.service_order_id AND so.clinic_id = t.clinic_id
                  LEFT JOIN node_definition nd
                    ON nd.code = so.node_code AND nd.clinic_id = so.clinic_id
                  LEFT JOIN staff nv ON nv.id = t.tai_len_boi_staff_id
                  LEFT JOIN staff bs ON bs.id = t.cho_phep_gui_boi_staff_id
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
            # PHẢN HỒI SAU DÙNG THUỐC cho cả trang — MỘT câu gộp theo khách
            # (16/10/2026, cột "Phản hồi thuốc"): số phản hồi còn hiệu lực + dòng
            # mới nhất. Không phụ thuộc số khách (không N+1); cùng luật hiệu lực
            # với `phan_hoi_thuoc_service._PHAN_HOI_SQL` (chưa gỡ, lượt còn tồn
            # tại). Không LIMIT: đếm phải trên TOÀN BỘ phản hồi của khách.
            phan_hoi_thuoc = await conn.fetch(
                """
                SELECT DISTINCT ON (t.clinic_patient_id)
                       t.clinic_patient_id, t.xay_ra_luc, t.kenh, t.noi_dung,
                       count(*) OVER (PARTITION BY t.clinic_patient_id)
                           AS so_phan_hoi
                  FROM tuong_tac_cskh t
                  JOIN visit pv
                    ON pv.visit_id = t.visit_id AND pv.clinic_id = t.clinic_id
                 WHERE t.clinic_id = $1::uuid
                   AND t.clinic_patient_id = ANY($2::uuid[])
                   AND t.loai = 'PHAN_HOI_THUOC' AND t.huy_luc IS NULL
                 ORDER BY t.clinic_patient_id, t.xay_ra_luc DESC
                """,
                clinic_id,
                ids,
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
                SELECT v.appointment_id, v.checked_in_at, v.closed_at,
                       v.finalized_at,
                       -- Thủ thuật + quyết định theo dõi của BÁC SĨ (16/09/2026):
                       -- hai ô khoá ở màn CSKH đọc từ đây, CSKH không tích.
                       v.theo_doi_thu_thuat, v.theo_doi_sau_ngay,
                       tt.co_thu_thuat, tt.thu_thuat_xong_luc,
                       -- VIỆC GỬI ĐỐI TÁC của lượt (17/09/2026): ô "Có kết quả
                       -- xét nghiệm" ở màn CSKH đọc trạng thái đối tác bấm —
                       -- chờ lấy mẫu / đã lấy mẫu / đã nhận mẫu (xong) / có kết quả.
                       -- Cùng thứ bậc với doi_tac_service.trang_thai_doi_tac.
                       dt.doi_tac,
                       -- KHÁCH ĐANG Ở ĐÂU (17/09/2026): chip CSKH đứng yên ở
                       -- "đang chờ khám" suốt lúc khách đi siêu âm, thủ thuật.
                       coalesce(vr.name, vn.name) AS vi_tri_hien_tai,
                       EXISTS (SELECT 1 FROM encounter_flow ef
                                WHERE ef.visit_id = v.visit_id
                                  AND ef.vitals_status = 'recorded')
                           AS da_do_sinh_hieu
                  FROM visit v
                  LEFT JOIN clinic_room vr
                    ON vr.id = v.current_room_id AND vr.clinic_id = v.clinic_id
                  LEFT JOIN node_definition vn
                    ON vn.code = v.current_node_code AND vn.clinic_id = v.clinic_id
                  LEFT JOIN LATERAL (
                      -- Thủ thuật của LƯỢT: luồng mới ghi ở service_order, luồng
                      -- cũ ở work_item — đọc cả hai (17/09/2026: ô "Đã làm thủ
                      -- thuật" nói "không có" dù vừa làm xong).
                      SELECT count(*) > 0 AS co_thu_thuat,
                             max(x.xong_luc) AS thu_thuat_xong_luc
                        FROM (
                            SELECT CASE WHEN w.status = 'COMPLETED'
                                        THEN w.finished_at END AS xong_luc
                              FROM work_item w
                             WHERE w.clinic_id = v.clinic_id
                               AND w.visit_id = v.visit_id
                               AND w.node_code = 'DICHVU-THUTHUAT'
                               AND w.status <> 'CANCELLED'
                            UNION ALL
                            SELECT CASE WHEN o.exec_status = 'performed'
                                        THEN o.finished_at END
                              FROM service_order o
                             WHERE o.clinic_id = v.clinic_id
                               AND o.visit_id = v.visit_id
                               AND o.node_code = 'DICHVU-THUTHUAT'
                               AND o.exec_status NOT IN ('draft', 'cancelled')
                        ) x
                  ) tt ON TRUE
                  LEFT JOIN LATERAL (
                      SELECT json_agg(json_build_object(
                                 'ten', coalesce(o.service_name, o.service_code),
                                 'trang_thai', CASE
                                     WHEN o.ket_qua_luc IS NOT NULL
                                         THEN 'DA_GUI_KET_QUA'
                                     WHEN o.doi_tac_cho_tai_lieu_luc IS NOT NULL
                                         THEN 'DA_NHAN_MAU'
                                     WHEN o.exec_status = 'performed' THEN 'DA_LAY_MAU'
                                     ELSE 'CHO_LAY_MAU' END,
                                 'luc', coalesce(o.ket_qua_luc,
                                                 o.doi_tac_cho_tai_lieu_luc,
                                                 o.finished_at, o.created_at)
                             ) ORDER BY o.created_at) AS doi_tac
                        FROM service_order o
                        LEFT JOIN node_definition n
                          ON n.clinic_id = o.clinic_id AND n.code = o.node_code
                       WHERE o.clinic_id = v.clinic_id
                         AND o.visit_id = v.visit_id
                         -- Bước làm bên ngoài HOẶC mẫu gửi đối tác (29/09/2026)
                         -- — cùng câu với doi_tac_service.LA_VIEC_DOI_TAC_SQL
                         -- (viết thẳng: mỗi câu SQL ở đây là MỘT chuỗi, test
                         -- khoá phòng khám đọc nguyên văn).
                         AND (coalesce(n.lam_ben_ngoai, false) OR EXISTS (
                              SELECT 1 FROM doi_tac_nhan_viec dnv
                               WHERE dnv.clinic_id = o.clinic_id
                                 AND dnv.service_order_id = o.id))
                         AND o.exec_status NOT IN ('draft', 'cancelled',
                                                   'not_performed')
                  ) dt ON TRUE
                 WHERE v.clinic_id = $1::uuid
                   AND v.clinic_patient_id = ANY($2::uuid[])
                 LIMIT $3
                """,
                clinic_id,
                ids,
                _TRAN_LICH,
            )

            # Khách đang ở / đang chờ ở đâu — cùng hàm với Hành trình khách,
            # chỉ lượt còn mở.
            dang_o = await dang_o_cac_luot(
                conn,
                clinic_id=clinic_id,
                visit_ids=[
                    str(r.get("luot_id"))
                    for r in appts
                    if r.get("luot_id")
                    and r.get("ve_luc") is None
                    # INCOMPLETE / FINALIZED / AMENDED cố ý không hỏi chỗ đứng:
                    # khách đã về / hồ sơ đã ký — nhãn do trang_thai_hien_thi.
                    and r.get("trang_thai_luot") in ("OPEN", "IN_PROGRESS")
                ],
            )

            # Nhãn đếm lượt (08/10/2026): máy chủ đếm trên MỌI lượt của khách
            # theo thời gian — `services/nhan_luot.py`.
            nhan = await doc_nhan_luot(conn, clinic_id, ids)

        return {
            "appts": [_lich(r, dang_o, nhan) for r in appts],
            "ca_truc": [dict(r) for r in ca_truc],
            "tuan_cong_bo": [str(w) for w in tuan_cong_bo],
            "trang_thai": trang_thai,
            "viec_mo": [_viec_mo(r) for r in viec[:_TRAN_LICH]]
            + [
                {
                    "clinic_patient_id": r["clinic_patient_id"],
                    "trang_thai": r["trang_thai"],
                    "nhan": r["nhan"],
                    "uu_tien": 10,
                    "han_xu_ly": None,
                    "qua_han": False,
                    "appointment_id": None,
                }
                for r in trang_thai
                if r["trang_thai"] == "CHO_DAT_LICH"
            ],
            "tep": [_kem_nhan_vien(r) for r in tep],
            "phan_hoi": [_kem_nhan_vien(r) for r in phan_hoi],
            "phan_hoi_thuoc": tom_tat_phan_hoi_thuoc(phan_hoi_thuoc),
            "hen_goi_lai": [_kem_nhan_vien(r) for r in hen_goi_lai],
            "tuong_tac": [_kem_nhan_vien(r) for r in tuong_tac],
            "cskh": [dict(r) for r in cskh],
            "visits": [
                {**dict(r), "doi_tac": json.loads(r["doi_tac"]) if r["doi_tac"] else []}
                for r in visits
            ],
        }


_CAC_KHOI = (
    "appts",
    "ca_truc",
    "tuan_cong_bo",
    "trang_thai",
    "viec_mo",
    "tep",
    "phan_hoi",
    "phan_hoi_thuoc",
    "hen_goi_lai",
    "tuong_tac",
    "cskh",
    "visits",
)


#: Rút gọn nội dung phản hồi thuốc cho ô bảng; hover đọc đủ (cắt ở `_TRAN_NOI_DUNG`).
_RUT_GON_KY_TU = 40
_TRAN_NOI_DUNG = 400


def rut_gon(noi_dung: Any, toi_da: int = _RUT_GON_KY_TU) -> str | None:
    """Một dòng ~`toi_da` ký tự: gộp khoảng trắng/xuống dòng, thêm "…" nếu cắt.

    Thuần; không phải chuỗi / rỗng → None; `toi_da` rác → mặc định. Không ném.
    """
    if not isinstance(noi_dung, str):
        return None
    mot_dong = " ".join(noi_dung.split())
    if not mot_dong:
        return None
    if not isinstance(toi_da, int) or isinstance(toi_da, bool) or toi_da < 2:
        toi_da = _RUT_GON_KY_TU
    if len(mot_dong) <= toi_da:
        return mot_dong
    return mot_dong[: toi_da - 1].rstrip() + "…"


def tom_tat_phan_hoi_thuoc(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Một dòng tóm tắt cho mỗi khách CÓ phản hồi (khách không có → vắng mặt).

    `ngay`/`luc` = lần ghi gần nhất (ISO); `tom_tat` = nội dung rút gọn; `noi_dung`
    = nội dung đủ (cắt 400 ký tự) cho tooltip. Thuần, rỗng → rỗng.
    """
    ra: list[dict[str, Any]] = []
    for r in rows:
        luc = r["xay_ra_luc"]
        nd = r["noi_dung"] if isinstance(r["noi_dung"], str) else None
        ra.append(
            {
                "clinic_patient_id": str(r["clinic_patient_id"]),
                "so_phan_hoi": int(r["so_phan_hoi"]),
                "luc": luc.isoformat() if luc is not None else None,
                "kenh": r["kenh"],
                "tom_tat": rut_gon(nd),
                "noi_dung": nd.strip()[:_TRAN_NOI_DUNG] if nd and nd.strip() else None,
            }
        )
    return ra


def _khoa_viec_thang(r: Mapping[str, Any]) -> tuple[int, bool, int, bool, date]:
    """Khoá xếp để chọn việc THẮNG của một khách — gương của `gap_nhat` trong
    `v_trang_thai_cskh`: `ORDER BY qua_han DESC, uu_tien, han_xu_ly`.

    DESC của Postgres đặt NULL TRƯỚC true TRƯỚC false; ASC đặt NULL CUỐI.
    """
    qua_han = r["qua_han"]
    uu_tien = r["uu_tien"]
    han = r["han_xu_ly"]
    return (
        0 if qua_han is None else (1 if qua_han else 2),
        uu_tien is None,
        uu_tien or 0,
        han is None,
        han or date.min,
    )


def trang_thai_tu_viec(viec: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Một dòng trạng thái cho mỗi khách có việc mở, suy từ các dòng `v_viec_cskh`.

    Đúng luật của `v_trang_thai_cskh` (đếm = `dem`, việc thắng = `gap_nhat`):
      * `so_viec_mo` = số việc; `co_viec_qua_han` = `bool_or(qua_han)` (NULL nếu
        không dòng nào có `qua_han`);
      * việc thắng = nhỏ nhất theo `_khoa_viec_thang`; hai việc đồng khoá thì
        lấy việc đứng trước (view cũng chọn tuỳ ý trong trường hợp ấy);
      * `da_xac_nhan` đọc từ chính dòng thắng (đã tính ở câu SQL đọc việc).
    Thuần, không đụng database; rỗng → rỗng. Thứ tự: theo lần xuất hiện đầu của
    khách trong `viec`.
    """
    theo_khach: dict[Any, list[Mapping[str, Any]]] = {}
    for r in viec:
        theo_khach.setdefault(r["clinic_patient_id"], []).append(r)
    ra: list[dict[str, Any]] = []
    for khach, ds in theo_khach.items():
        thang = min(ds, key=_khoa_viec_thang)
        co_gia_tri = [r["qua_han"] for r in ds if r["qua_han"] is not None]
        ra.append(
            {
                "clinic_patient_id": khach,
                "trang_thai": thang["trang_thai"],
                "nhan": thang["nhan"],
                "han_xu_ly": thang["han_xu_ly"],
                "qua_han": thang["qua_han"],
                "so_viec_mo": len(ds),
                "co_viec_qua_han": any(co_gia_tri) if co_gia_tri else None,
                "appointment_id": thang["appointment_id"],
                "da_xac_nhan": bool(thang["da_xac_nhan"]),
            }
        )
    return ra


def _viec_mo(r: Mapping[str, Any]) -> dict[str, Any]:
    """Một việc mở của khối `viec_mo` — bỏ cột `da_xac_nhan` chỉ dùng cho trạng thái."""
    return {
        k: r[k]
        for k in (
            "clinic_patient_id",
            "trang_thai",
            "nhan",
            "uu_tien",
            "han_xu_ly",
            "qua_han",
            "appointment_id",
        )
    }


def _lich(
    r: asyncpg.Record,
    dang_o: dict[str, Any] | None = None,
    nhan: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Một dòng lịch hẹn, LỒNG `service`/`doctor` y như PostgREST.

    page.tsx đọc `a.service?.name` và `a.doctor?.full_name` — đổi sang cột
    phẳng là phải sửa cả chuỗi dựng map phía đó. Bắt chước hình cũ rẻ hơn và
    an toàn hơn viết lại phần đọc.

    `trang_thai` (30/09/2026): nhãn máy chủ quyết; `trang_thai_luc` = mốc của
    nhãn ấy (giờ về nếu đã check-out, không thì giờ check-in) để chip danh
    sách so với lần chạm cuối của sổ chăm sóc.
    """
    d = dict(r)
    ten_dv = d.pop("ten_dich_vu", None)
    ten_bs = d.pop("ten_bac_si", None)
    luot_id = d.pop("luot_id", None)
    luot = d.pop("trang_thai_luot", None)
    den_luc = d.pop("den_luc", None)
    ve_luc = d.pop("ve_luc", None)
    kham_xong = bool(d.pop("kham_xong", False))
    kham_xong_luc = d.pop("kham_xong_luc", None)
    d["service"] = {"name": ten_dv} if ten_dv else None
    d["doctor"] = {"full_name": ten_bs} if ten_bs else None
    d["trang_thai"] = trang_thai_hien_thi(
        lich=d.get("status"),
        luot=luot,
        ve_luc=ve_luc,
        kham_xong=kham_xong,
        dang_o=(dang_o or {}).get(luot_id or ""),
    )
    moc = ve_luc or den_luc
    d["trang_thai_luc"] = moc.isoformat() if moc else None
    # GIỜ THẬT của lượt (khung phải: "khám xong hh:mm · về hh:mm") — lượt đã tới
    # không hiện giờ hẹn slot_start.
    d["den_luc"] = den_luc.isoformat() if den_luc else None
    d["kham_xong_luc"] = kham_xong_luc.isoformat() if kham_xong_luc else None
    d["ve_luc"] = ve_luc.isoformat() if ve_luc else None
    d["nhan_luot"] = tra_nhan(nhan or {}, visit_id=luot_id, appointment_id=d.get("id"))
    return d


def _kem_nhan_vien(r: asyncpg.Record) -> dict[str, Any]:
    """Lồng `staff:{full_name}` như PostgREST embed."""
    d = dict(r)
    ten = d.pop("ten_nhan_vien", None)
    d["staff"] = {"full_name": ten} if ten else None
    return d
