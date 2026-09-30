"""Pack C — dịch vụ / thủ thuật dùng chung vòng đời rail mới (batch pilot 18/09)."""

from __future__ import annotations

import pytest

from clinicai.services.theo_doi_thu_thuat_service import TheoDoiThuThuatService
from tests.services.test_luot_kham_service_db import (
    CLINIC,
    KichBan,
    _vao_kham,
    dieu_phoi_cu,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_thu_thuat_tren_rail_moi_co_han_goi_hoi_tham(kb: KichBan) -> None:
    ma_tt = await kb.pool.fetchval(
        "SELECT service_code FROM service_price sp WHERE clinic_id = $1::uuid"
        " AND active AND node_code = 'DICHVU-THUTHUAT'"
        # Dịch vụ gắn phòng riêng (Ghế ĐTT, máy Bio → Sàn chậu, 30/09/2026)
        # không làm ở phòng thủ thuật đầu tiên — lấy dịch vụ đi theo node.
        " AND NOT EXISTS (SELECT 1 FROM clinic_room_service s"
        " WHERE s.clinic_id = sp.clinic_id AND s.service_code = sp.service_code)"
        " ORDER BY service_code LIMIT 1",
        CLINIC,
    )
    phong = await kb.pool.fetchval(
        "SELECT r.id::text FROM clinic_room r JOIN clinic_room_node rn"
        " ON rn.room_id = r.id WHERE r.clinic_id = $1::uuid"
        " AND rn.node_code = 'DICHVU-THUTHUAT' AND r.is_active AND r.accepting"
        " ORDER BY r.sort LIMIT 1",
        CLINIC,
    )
    assert ma_tt and phong
    phien = await _vao_kham(kb)
    [tt] = (
        await kb.svc.authorize_orders(
            consultation_id=phien,
            service_codes=[ma_tt],
            draft_order_ids=None,
            identity=kb.bac_si,
        )
    )["order_ids"]
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    svc = TheoDoiThuThuatService(kb.pool)
    await svc.dat(identity=kb.bac_si, visit_id=kb.visit_id, theo_doi="CAN", sau_ngay=3)
    truoc = await svc.doc(identity=kb.bac_si, visit_id=kb.visit_id)
    assert truoc["co_thu_thuat"] is True and truoc["han_goi"] is None
    if (
        await kb.pool.fetchval(
            "SELECT exec_status FROM service_order WHERE id = $1::uuid", tt
        )
        == "authorized"
    ):
        await dieu_phoi_cu(
            kb.svc,
            order_id=tt,
            room_id=phong,
            expected_version=None,
            identity=kb.truong_ca,
        )
    await kb.svc.start_service(order_id=tt, identity=kb.bac_si)
    await kb.svc.complete_service(
        order_id=tt,
        performed=True,
        reason=None,
        result_note=None,
        identity=kb.bac_si,
    )
    sau = await svc.doc(identity=kb.bac_si, visit_id=kb.visit_id)
    assert sau["thu_thuat_xong_luc"] and sau["han_goi"]


async def test_dich_vu_khong_co_phong_hien_ro_cho_truong_ca(kb: KichBan) -> None:
    # Seed local: Đo mật độ xương (DICHVU-DXA) chưa gắn phòng nào — chỉ định sẽ
    # kẹt "chờ xếp phòng". Trưởng ca phải thấy lý do, không thấy im lặng.
    dxa = await kb.pool.fetchval(
        "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid AND active"
        " AND node_code = 'DICHVU-DXA' LIMIT 1",
        CLINIC,
    )
    co_phong = await kb.pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM clinic_room_node rn JOIN clinic_room r"
        " ON r.id = rn.room_id WHERE rn.clinic_id = $1::uuid"
        " AND rn.node_code = 'DICHVU-DXA' AND r.is_active)",
        CLINIC,
    )
    if not dxa or co_phong:
        pytest.skip("dữ liệu mẫu đã gán phòng cho DXA")
    phien = await _vao_kham(kb)
    [oid] = (
        await kb.svc.authorize_orders(
            consultation_id=phien,
            service_codes=[dxa],
            draft_order_ids=None,
            identity=kb.bac_si,
        )
    )["order_ids"]
    kq = await kb.svc.chi_dinh_hom_nay(identity=kb.truong_ca)
    [c] = [c for c in kq["chi_dinh"] if c["id"] == oid]
    assert c["nhom"] == "can_dieu_phoi" and c["khong_co_phong"] is True
