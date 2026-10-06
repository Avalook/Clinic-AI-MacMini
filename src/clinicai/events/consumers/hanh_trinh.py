"""Khối HÀNH TRÌNH — Journey Process Manager (thesis §9; docs/CHUAN-CAM-LEGO.md mục 5).

Giữ luật THỨ TỰ khách đi. Nghe sự thật đã xảy ra, rồi gửi LỆNH của khối Khám
(không ghi bảng của ai). Dây nối (docs/BAN-DO-DAY-NOI-LEGO.md, "Bản chốt 24/09"):

    H2  visit.checked_in          → mang chỉ định chưa làm của lượt trước sang
                                    rồi xếp phòng luôn (qua cửa làm như H4;
                                    lịch đi thẳng phòng: mang cả chỉ định chưa
                                    trả)
    H1  visit.checked_in          → xếp đường đi: qua tư vấn / thẳng bác sĩ chính /
                                    thẳng dịch vụ (lịch đi thẳng phòng)
        vitals.recorded           → hàng tư vấn: "chờ đo sinh hiệu" → "chờ tư vấn"
                                    (lượt chưa có đường đi thì xếp luôn — tự chữa);
                                    điều dưỡng tick "bỏ qua tư vấn" → thẳng bác sĩ
                                    chính (25/09)
    H1b appointment.service_switched (có visit_id) → đổi dịch vụ khám sau
                                    check-in: xếp lại hàng đầu tiên (V5 30/09)
    H3  consultation.handed_over  → hàng chờ khám thật của bác sĩ chính
    H4  service_selection.confirmed → xếp phòng vắng nhất THAY người vừa chốt,
                                    bằng quyền của người ấy — chỉ chỉ định qua
                                    cửa làm (dây ``thu_truoc_khi_lam`` BẬT: đã
                                    thu, hoặc lượt tick "Làm trước – thu sau";
                                    TẮT: V10, chưa thu cũng xếp)
        service_order.desk_added  → lễ tân / người đo tick "+ dịch vụ" (làm
                                    thêm tại quầy, 01/10/2026): như trên
        service_order.restored    → hoàn tác bỏ chỉ định (06/10/2026): như trên
        visit.defer_payment_set   → vừa tick "Làm trước – thu sau": chạy lại
                                    đúng lệnh ấy bằng quyền người tick
        payment.service_collected → chạy lại đúng lệnh ấy bằng quyền người thu
                                    (chỉ định còn chưa có phòng — vô hại nếu
                                    đã xếp); cùng một dây bật/tắt
    H6  visit.checked_out / left_early → còn việc dở → báo CSKH (bật/tắt được)
    H7  service.completed / partner.sample_collected (dịch vụ đối tác)
                                  → hẹn N ngày: kết quả chưa về → báo CSKH
    H8  payment.*_collected       → hẹn N phút: chưa check-out → nhắc lễ tân
                                    (CHỈ nhắc, không tự đóng lượt)

Các thời hạn / bật tắt là DÂY NGHIỆP VỤ quản lý chỉnh trên màn (`day_noi.py`).

Loại khám nào qua tư vấn là DỮ LIỆU (`service_type.qua_tu_van`), quản lý chỉnh
được — không viết cứng ở đây.

CHẠY LẠI ĐƯỢC: người đưa tin giao "ít nhất một lần"; mỗi lệnh tự bỏ qua nếu đã
làm. PHÁT LẠI (`la_phat_lai`) thì KHÔNG làm gì — đây là node TÁC VỤ, không phải
projection (xếp lại hàng cho khách hôm qua là sai).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import asyncpg

from clinicai.events.catalogue import HANH_TRINH
from clinicai.events.consumers.chuong import ghi_chuong_vai
from clinicai.events.hen_gio import HenDenHan, dang_ky_loai, hen, huy_hen
from clinicai.events.worker import SuKienDaNhan, dang_ky
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.day_noi import doc_day
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.service_routing_service import ServiceRoutingService


async def xu_ly_hanh_trinh(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
    if su_kien.la_phat_lai:
        return
    visit_id = str(su_kien.payload.get("visit_id") or "")
    if not visit_id:
        return
    # Lệnh chạy trên CHÍNH giao dịch đánh dấu DONE (luật 3 của người đưa tin):
    # hỏng giữa chừng thì cả hai cùng cuộn lại, lần sau làm lại từ đầu.
    luot = LuotKhamService(pool=None)
    if su_kien.event_type == "visit.checked_in":
        trang_thai = await conn.fetchval(
            "SELECT status FROM visit WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid FOR UPDATE",
            su_kien.clinic_id,
            visit_id,
        )
        mang = (
            await ChiDinhService.mang_sang_luot_moi(
                conn,
                clinic_id=su_kien.clinic_id,
                visit_id=visit_id,
                causation_id=su_kien.event_id,
            )
            # Lượt vừa bị hoàn tác / khách bỏ về (INCOMPLETE) / đã đóng:
            # không kéo chỉ định cũ sang một lượt không còn ai ở đó.
            if trang_thai in ("OPEN", "IN_PROGRESS")
            else []
        )
        await luot.xep_sau_check_in(
            conn,
            clinic_id=su_kien.clinic_id,
            visit_id=visit_id,
            causation_id=su_kien.event_id,
        )
        if mang and await doc_day(conn, su_kien.clinic_id, "h4_tu_xep_phong"):
            # Mang từ lượt trước: vào thẳng hàng phòng, thay người check-in —
            # lệnh tự bỏ chỉ định không qua cửa làm (khách chưa chốt / tiền đang
            # hoàn / dây thu trước bật mà chưa thu, lượt chưa tick).
            await ServiceRoutingService(pool=None).tu_xep_da_thu(
                conn,
                clinic_id=su_kien.clinic_id,
                visit_id=visit_id,
                staff_id=su_kien.actor_staff_id,
                causation_id=su_kien.event_id,
            )
    elif su_kien.event_type == "appointment.service_switched":
        # Đổi lại lần nữa trước khi tin này tới → tin sau lo; không xếp theo
        # một loại khám đã cũ.
        hien_tai = await conn.fetchval(
            "SELECT service_type_id::text FROM visit WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid",
            su_kien.clinic_id,
            visit_id,
        )
        if hien_tai == str(su_kien.payload.get("den_dich_vu_id") or ""):
            await luot.xep_lai_sau_doi_dich_vu(
                conn,
                clinic_id=su_kien.clinic_id,
                visit_id=visit_id,
                causation_id=su_kien.event_id,
            )
    elif su_kien.event_type == "payment.service_collected":
        if await doc_day(conn, su_kien.clinic_id, "h4_tu_xep_phong"):
            await ServiceRoutingService(pool=None).tu_xep_da_thu(
                conn,
                clinic_id=su_kien.clinic_id,
                visit_id=visit_id,
                staff_id=su_kien.actor_staff_id,
                causation_id=su_kien.event_id,
            )
        await _hen_nhac_check_out(conn, su_kien, visit_id)
    elif su_kien.event_type in (
        "service_selection.confirmed",
        "visit.defer_payment_set",
        # Làm thêm tại quầy (01/10/2026): lễ tân / người đo tick là chỉ định đã
        # chốt — đi đúng cửa làm như khách vừa chốt ở quầy thu.
        "service_order.desk_added",
        # Hoàn tác bỏ chỉ định (Khối 2, 06/10/2026): chỉ định quay lại — đã thu
        # thì xếp phòng lại ngay như lúc vừa chốt.
        "service_order.restored",
    ):
        # Khách chốt xong (hoặc lượt vừa được tick "Làm trước – thu sau") → xếp
        # phòng ngay mọi chỉ định QUA CỬA LÀM của FinanceGate, bằng quyền NGƯỜI
        # BẤM. Cửa ấy theo dây ``thu_truoc_khi_lam`` (30/09/2026 tối): BẬT = chưa
        # thu thì chỉ lượt đã tick mới xếp — lượt không tick để nguyên, thu tiền
        # xong đường payment.service_collected xếp (H4 gốc); TẮT = V10 "làm
        # trước, thu sau" mọi lượt. Người bấm không có quyền điều phối thì để
        # nguyên — thu tiền sau đó chạy lại bằng quyền người thu, hoặc người có
        # quyền xếp tay.
        if await doc_day(conn, su_kien.clinic_id, "h4_tu_xep_phong"):
            await ServiceRoutingService(pool=None).tu_xep_da_thu(
                conn,
                clinic_id=su_kien.clinic_id,
                visit_id=visit_id,
                staff_id=su_kien.actor_staff_id,
                causation_id=su_kien.event_id,
            )
    elif su_kien.event_type == "payment.medicine_collected":
        await _hen_nhac_check_out(conn, su_kien, visit_id)
    elif su_kien.event_type in ("visit.checked_out", "visit.left_early"):
        await huy_hen(
            conn, clinic_id=su_kien.clinic_id, loai=HEN_CHECK_OUT, ve_cai_gi=visit_id
        )
        await _bao_ve_con_viec(conn, su_kien, visit_id)
    elif su_kien.event_type in ("service.completed", "partner.sample_collected"):
        await _hen_ket_qua_doi_tac(conn, su_kien, visit_id)
    elif su_kien.event_type == "vitals.recorded":
        # TỰ CHỮA: lượt chưa có đường đi (lỡ mất sự kiện check-in, hay lượt mở
        # theo đường cũ không phát sự kiện) thì xếp luôn ở đây. Lệnh tự bỏ qua
        # nếu đã xếp — chạy thừa không sao, thiếu mới là khách kẹt.
        await luot.xep_sau_check_in(
            conn,
            clinic_id=su_kien.clinic_id,
            visit_id=visit_id,
            causation_id=su_kien.event_id,
        )
        if su_kien.payload.get("bo_qua_tu_van"):
            await luot.bo_qua_tu_van(
                conn,
                clinic_id=su_kien.clinic_id,
                visit_id=visit_id,
                causation_id=su_kien.event_id,
            )
        else:
            await LuotKhamService.mo_hang_tu_van(
                conn, clinic_id=su_kien.clinic_id, visit_id=visit_id
            )
    elif su_kien.event_type == "consultation.handed_over":
        await luot.chuyen_bac_si_chinh(
            conn,
            clinic_id=su_kien.clinic_id,
            visit_id=visit_id,
            causation_id=su_kien.event_id,
        )


# ── H6 / H7 / H8 ────────────────────────────────────────────────────────────

HEN_CHECK_OUT = "hanh_trinh.nhac_check_out"
HEN_KET_QUA_DOI_TAC = "hanh_trinh.ket_qua_doi_tac_qua_han"


async def _ten_khach(conn: asyncpg.Connection, clinic_id: str, visit_id: str) -> Any:
    return await conn.fetchrow(
        "SELECT p.clinic_patient_id::text AS pid, p.full_name, p.patient_code,"
        "       v.closed_at, v.status"
        "  FROM visit v JOIN patient p"
        "    ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id"
        " WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid",
        clinic_id,
        visit_id,
    )


async def _hen_nhac_check_out(
    conn: asyncpg.Connection, su_kien: SuKienDaNhan, visit_id: str
) -> None:
    """H8: trả tiền xong → hẹn N phút; tới giờ còn chưa check-out thì nhắc lễ tân."""
    phut = int(await doc_day(conn, su_kien.clinic_id, "h8_nhac_check_out_phut"))
    if phut <= 0 or not su_kien.actor_staff_id:
        return
    await hen(
        conn,
        clinic_id=su_kien.clinic_id,
        loai=HEN_CHECK_OUT,
        sau=timedelta(minutes=phut),
        ve_cai_gi=visit_id,
        correlation_id=visit_id,
        chi_tiet={"nguoi_goi": su_kien.actor_staff_id, "phut": phut},
    )


async def nhac_check_out(conn: asyncpg.Connection, cai_hen: HenDenHan) -> bool:
    """Tới giờ: khách đã check-out thì thôi; chưa thì nhắc lễ tân (CHỈ nhắc —
    Tuyền 24/09: "check-out quá 1h chỉ nhắc lễ tân", không tự đóng lượt)."""
    if not cai_hen.ve_cai_gi:
        return False
    k = await _ten_khach(conn, cai_hen.clinic_id, cai_hen.ve_cai_gi)
    if k is None or k["closed_at"] is not None:
        return False
    await ghi_chuong_vai(
        conn,
        clinic_id=cai_hen.clinic_id,
        vai="RECEPTION",
        tieu_de=f"{k['full_name']} ({k['patient_code']}) đã thanh toán"
        f" hơn {cai_hen.chi_tiet.get('phut', 60)} phút, chưa check-out",
        noi_dung="Khách còn trong phòng khám hay đã về? Check-out nếu đã về.",
        nguon="hanh_trinh",
        nguon_id=f"check_out:{cai_hen.ve_cai_gi}",
        duong_dan="/reception/queue",
        nguoi_goi=str(cai_hen.chi_tiet["nguoi_goi"]),
    )
    return True


async def _bao_ve_con_viec(
    conn: asyncpg.Connection, su_kien: SuKienDaNhan, visit_id: str
) -> None:
    """H6: khách về (hoặc bỏ về giữa chừng) mà còn việc dở → báo CSKH theo dõi."""
    if not su_kien.actor_staff_id or not await doc_day(
        conn, su_kien.clinic_id, "h6_bao_cskh_khi_ve_con_viec"
    ):
        return
    con = await conn.fetchrow(
        """
        SELECT
          (SELECT count(*) FROM service_order o
             JOIN node_definition n
               ON n.clinic_id = o.clinic_id AND n.code = o.node_code
            WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
              AND n.lam_ben_ngoai AND o.ket_qua_luc IS NULL
              -- Đối tác đã nhận mẫu = việc XONG (Tuyền 29/09/2026): kết quả
              -- về sau có chuông riêng, không phải "việc dở" khi khách về.
              AND o.doi_tac_cho_tai_lieu_luc IS NULL
              AND o.exec_status NOT IN ('draft', 'cancelled', 'not_performed')
              AND o.selection_status IS DISTINCT FROM 'NOT_SELECTED') AS cho_ket_qua,
          (SELECT count(*) FROM v_tep_ket_qua_hieu_luc t
             JOIN service_order o ON o.id = t.service_order_id
                                 AND o.clinic_id = t.clinic_id
            WHERE t.clinic_id = $1::uuid AND o.visit_id = $2::uuid
              AND t.da_xem_luc IS NULL
              AND coalesce(t.xac_nhan_trang_thai, 'HOP_LE') = 'HOP_LE')
          + (SELECT count(DISTINCT o.id) FROM service_order o
               JOIN form_instance f
                 ON f.service_order_id = o.id AND f.clinic_id = o.clinic_id
              WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
                AND f.trang_thai = 'READY' AND o.da_xem_ket_qua_luc IS NULL)
            AS chua_xem,
          (SELECT count(*) FROM service_order o
            WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
              AND o.selection_status = 'SELECTED'
              AND coalesce(o.execution_status, 'PENDING') = 'PENDING') AS chua_lam
        """,
        su_kien.clinic_id,
        visit_id,
    )
    viec = []
    if con["cho_ket_qua"]:
        viec.append(f"{con['cho_ket_qua']} kết quả đối tác chưa về")
    if con["chua_xem"]:
        viec.append(f"{con['chua_xem']} kết quả chưa bác sĩ xem")
    if con["chua_lam"]:
        viec.append(f"{con['chua_lam']} dịch vụ đã chọn chưa làm")
    bo_ve = su_kien.event_type == "visit.left_early"
    if not viec and not bo_ve:
        return
    k = await _ten_khach(conn, su_kien.clinic_id, visit_id)
    if k is None:
        return
    await ghi_chuong_vai(
        conn,
        clinic_id=su_kien.clinic_id,
        vai="CSKH",
        tieu_de=f"{k['full_name']} ({k['patient_code']})"
        + (" bỏ về giữa chừng" if bo_ve else " đã về còn việc dở"),
        noi_dung=("; ".join(viec) or "Gọi hỏi thăm, hẹn lại.") + ".",
        nguon="hanh_trinh",
        nguon_id=f"ve_con_viec:{visit_id}",
        duong_dan=f"/customers?selected={k['pid']}",
        nguoi_goi=su_kien.actor_staff_id,
    )


async def _hen_ket_qua_doi_tac(
    conn: asyncpg.Connection, su_kien: SuKienDaNhan, visit_id: str
) -> None:
    """H7: dịch vụ ĐỐI TÁC đã làm/lấy mẫu → hẹn N ngày kiểm kết quả đã về chưa."""
    oid = su_kien.payload.get("service_order_id")
    if not oid or not su_kien.actor_staff_id:
        return
    ngoai = await conn.fetchval(
        "SELECT n.lam_ben_ngoai FROM service_order o JOIN node_definition n"
        "  ON n.clinic_id = o.clinic_id AND n.code = o.node_code"
        " WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid AND o.ket_qua_luc IS NULL",
        su_kien.clinic_id,
        oid,
    )
    if not ngoai:
        return
    ngay = int(
        await doc_day(conn, su_kien.clinic_id, "h7_ket_qua_doi_tac_qua_han_ngay")
    )
    await hen(
        conn,
        clinic_id=su_kien.clinic_id,
        loai=HEN_KET_QUA_DOI_TAC,
        sau=timedelta(days=ngay),
        ve_cai_gi=str(oid),
        correlation_id=visit_id,
        chi_tiet={"nguoi_goi": su_kien.actor_staff_id, "ngay": ngay},
    )


async def ket_qua_doi_tac_qua_han(conn: asyncpg.Connection, cai_hen: HenDenHan) -> bool:
    """Tới hạn: kết quả đã về (hoặc chỉ định huỷ) thì thôi; chưa thì báo CSKH."""
    o = await conn.fetchrow(
        "SELECT o.service_name, o.ket_qua_luc, o.exec_status,"
        "       o.visit_id::text AS visit_id"
        "  FROM service_order o WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid",
        cai_hen.clinic_id,
        cai_hen.ve_cai_gi,
    )
    if o is None or o["ket_qua_luc"] is not None or o["exec_status"] == "cancelled":
        return False
    k = await _ten_khach(conn, cai_hen.clinic_id, o["visit_id"])
    if k is None:
        return False
    await ghi_chuong_vai(
        conn,
        clinic_id=cai_hen.clinic_id,
        vai="CSKH",
        tieu_de=f"Kết quả {o['service_name']} của {k['full_name']}"
        f" quá {cai_hen.chi_tiet.get('ngay', 3)} ngày chưa về",
        noi_dung="Gọi đối tác hỏi kết quả, báo khách nếu cần.",
        nguon="hanh_trinh",
        nguon_id=f"qua_han:{cai_hen.ve_cai_gi}",
        duong_dan=f"/customers?selected={k['pid']}",
        nguoi_goi=str(cai_hen.chi_tiet["nguoi_goi"]),
    )
    return True


dang_ky(HANH_TRINH, xu_ly_hanh_trinh)
dang_ky_loai(HEN_CHECK_OUT, nhac_check_out)
dang_ky_loai(HEN_KET_QUA_DOI_TAC, ket_qua_doi_tac_qua_han)

__all__ = [
    "HEN_CHECK_OUT",
    "HEN_KET_QUA_DOI_TAC",
    "ket_qua_doi_tac_qua_han",
    "nhac_check_out",
    "xu_ly_hanh_trinh",
]
