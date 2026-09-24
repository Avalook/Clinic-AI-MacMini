"""Hai đường của ĐỐI TÁC — và chỉ hai đường này.

Đối tác là người NGOÀI phòng khám: lab chạy xét nghiệm, nơi chụp MRI, phòng
chụp tử cung–vòi trứng. Họ vào để làm đúng một việc — gửi lại kết quả họ vừa
làm — rồi đi ra.

BỐN RÀNG BUỘC, và mỗi cái có một dòng mã đứng sau nó chứ không chỉ là lời hứa:

  1. CHỈ THẤY VIỆC CỦA MÌNH — truy vấn lọc theo `node_definition.lam_ben_ngoai`,
     nên bước nào không đánh dấu là họ không nhìn thấy, và tắt cờ ấy là họ thôi
     nhìn thấy ngay mà không phải sửa mã.
  2. KHÔNG TRA CỨU — không endpoint nào ở đây nhận từ khoá tìm kiếm. Họ thấy
     đúng danh sách hệ thống đưa ra, không hỏi thêm được gì.
  3. KHÔNG ĐỌC BỆNH ÁN — danh sách trả về tên, mã bệnh nhân, tên dịch vụ, ngày.
     Không số điện thoại, không ngày sinh, không chẩn đoán, không tệp cũ.
     Tên có mặt vì họ VỪA GẶP người ấy ngoài đời; giấu tên đi thì họ gắn nhầm
     tệp vào nhầm người, và cái sai đó đắt hơn nhiều.
  4. GỬI LÊN, KHÔNG LẤY VỀ — không có đường tải xuống ở đây. Kể cả tệp chính họ
     vừa gửi.

Và ràng buộc thứ năm nằm ở nơi khác, quan trọng hơn cả bốn cái trên:
`get_current_identity` TỪ CHỐI vai PARTNER, nên mọi endpoint khác trong hệ —
đang có và viết sau này — đều đóng với họ mà không ai phải nhớ liệt kê.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request

from clinicai.api.identity import StaffIdentity, get_partner_identity
from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.nhan_tep_luong import TepDaNhan

router = APIRouter()


@router.get("/doi-tac/viec")
async def viec_cua_doi_tac(
    identity: StaffIdentity = Depends(get_partner_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Khách đang chờ bàn đối tác, kèm những việc của từng người.

    Giới hạn 60 ngày gần đây: một chỉ định từ nửa năm trước mà chưa có kết quả
    thì đó là việc của phòng khám đi đòi, không phải việc để đối tác gửi hôm
    nay — và để nó nằm trong danh sách chỉ làm danh sách dài ra rồi không ai
    đọc.
    """
    from clinicai.services.doi_tac_service import DoiTacService

    return await DoiTacService(pool).viec_doi_tac(identity=identity)


@router.post("/doi-tac/viec/{chi_dinh_id}/da-lay-mau")
async def da_lay_mau(
    chi_dinh_id: UUID,
    identity: StaffIdentity = Depends(get_partner_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đối tác xác nhận đã lấy mẫu cho xét nghiệm họ tự lấy."""
    from clinicai.services.doi_tac_service import DoiTacService

    return await DoiTacService(pool).doi_tac_da_lay_mau(
        order_id=str(chi_dinh_id), identity=identity
    )


@router.post("/doi-tac/viec/{chi_dinh_id}/cho-tai-lieu")
async def cho_tai_lieu(
    chi_dinh_id: UUID,
    identity: StaffIdentity = Depends(get_partner_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đối tác nhận việc: mẫu đã có, đang làm, sẽ gửi tài liệu kết quả."""
    from clinicai.services.doi_tac_service import DoiTacService

    return await DoiTacService(pool).doi_tac_cho_tai_lieu(
        order_id=str(chi_dinh_id), identity=identity
    )


@router.post("/doi-tac/ket-qua", status_code=201)
async def gui_ket_qua(
    request: Request,
    identity: StaffIdentity = Depends(get_partner_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Gửi một tệp kết quả cho MỘT chỉ định gửi ra ngoài.

    NHẬN MÃ CHỈ ĐỊNH, KHÔNG NHẬN MÃ BỆNH NHÂN. Đây là khác biệt quan trọng nhất
    giữa cửa này và cửa tải tệp của nhân viên: nếu đối tác tự khai bệnh nhân thì
    họ gửi được tệp cho BẤT KỲ AI — chỉ cần đoán đúng một mã. Ở đây họ chỉ nói
    được "kết quả của việc này", còn việc ấy thuộc về ai là do hệ thống tra ra.
    """
    from clinicai.services.nhan_tep_luong import nhan_multipart

    # Thân chảy thẳng vào kho; quyền đối tác đã kiểm trước khi đọc byte nào.
    truong, tep = await nhan_multipart(request)
    try:
        return await _gui_ket_qua(pool, identity, truong, tep)
    finally:
        tep.duong.unlink(missing_ok=True)


async def _gui_ket_qua(
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    truong: dict[str, str],
    tep: TepDaNhan,
) -> dict[str, Any]:
    from clinicai.services.nhan_tep_luong import uuid_hoac_loi
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    chi_dinh_id = uuid_hoac_loi(truong.get("chi_dinh_id"), "Mã chỉ định", bat_buoc=True)
    async with pool.acquire() as conn:
        o = await conn.fetchrow(
            """
            SELECT v.clinic_patient_id::text AS clinic_patient_id,
                   v.appointment_id::text    AS appointment_id
              FROM public.service_order o
              JOIN public.visit v
                ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
              JOIN public.node_definition n
                ON n.clinic_id = o.clinic_id AND n.code = o.node_code
               AND n.lam_ben_ngoai
             WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
            """,
            identity.clinic_id,
            str(chi_dinh_id),
        )
    if o is None:
        # Cùng một câu cho "không có" và "có nhưng không phải việc gửi ra ngoài"
        # — nói rõ hơn là để người ngoài dò xem mã nào tồn tại.
        raise SafetyGateError("Không tìm thấy việc này trong danh sách của bạn.")

    return await TepKetQuaService(pool).tai_len(
        identity=identity,
        clinic_patient_id=o["clinic_patient_id"],
        tep_da_nhan=tep,
        ten_hien_thi=tep.ten,
        appointment_id=o["appointment_id"],
        service_order_id=str(chi_dinh_id),
    )
