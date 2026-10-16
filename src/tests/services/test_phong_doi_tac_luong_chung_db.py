"""PHÒNG ĐỐI TÁC chạy CÙNG luồng phòng (Tuyền chốt 16/10/2026).

(a) Phòng đối tác nhận việc ĐỐI TÁC LÀM TRỌN qua "Sắp đến" → Nhận; KHÔNG nhận
    mẫu lấy máu điều dưỡng lấy (bẫy: phòng đối tác gắn mọi bước làm bên
    ngoài). Phòng thường vẫn loại việc đối tác làm trọn.
(b) Bắt đầu → "Đã nhận mẫu" (cùng lệnh bàn /doi-tac) đóng lần làm, khách rời
    hàng phòng, không giữ lượt (checkout không còn dịch vụ dở / kết quả chờ).
(c) Tải tệp chưa là "Có kết quả"; [Trả kết quả] → "Có kết quả" ở bàn đối tác
    và hành trình; hoàn tác được.
(d) Thu hộ: ô số tiền tuỳ chọn — rỗng = không ghi gì, rác = lỗi rõ; không vào
    `payment_*`.
"""

from __future__ import annotations

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services import nhan_tai_phong as ntp
from clinicai.services.doi_tac_service import DoiTacService
from clinicai.services.luot_kham_service import LuotKhamConflictError
from clinicai.services.service_execution_service import ServiceExecutionService
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi
from tests.services.test_nhan_tai_phong_db import _nhan, bat  # noqa: F401
from tests.services.test_service_routing_db import (  # noqa: F401
    RB,
    _cd,
    _phong,
    rb,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

NODE_MAU = "DICHVU-LAYMAU-MAU"


async def _chuan_bi(b: RB) -> tuple[str, str, str]:
    """(phòng đối tác, chỉ định đối tác làm trọn, chỉ định lấy máu điều dưỡng)."""
    async with b.pool.acquire() as conn:
        assert await conn.fetchval(
            "SELECT lam_ben_ngoai FROM node_definition WHERE clinic_id = $1::uuid"
            " AND code = $2",
            CLINIC,
            NODE_MAU,
        ), "bước lấy máu phải là bước làm bên ngoài (migration vai đối tác)"
        phong_dt = await _phong(conn, b.loc, b.duoi, "DOITAC", node=NODE_MAU, sort=3)
        await conn.execute(
            "UPDATE clinic_room SET la_doi_tac = true WHERE id = $1::uuid", phong_dt
        )
    tron = await _cd(b)
    dd = await _cd(b)
    await b.pool.execute(
        "UPDATE service_order SET node_code = $2 WHERE id = ANY($1::uuid[])",
        [tron, dd],
        NODE_MAU,
    )
    await b.pool.execute(
        "UPDATE service_price SET node_code = $2 WHERE clinic_id = $1::uuid"
        " AND service_code IN (SELECT service_code FROM service_order"
        " WHERE id = ANY($3::uuid[]))",
        CLINIC,
        NODE_MAU,
        [tron, dd],
    )
    await b.pool.execute(
        "UPDATE service_price SET doi_tac_lay_mau = true, node_code = $2"
        " WHERE clinic_id = $1::uuid AND service_code = (SELECT service_code FROM"
        " service_order WHERE id = $3::uuid)",
        CLINIC,
        NODE_MAU,
        tron,
    )
    return phong_dt, tron, dd


async def _ids_sap_den(b: RB, room: str) -> set[str]:
    async with b.pool.acquire() as conn:
        o = await ntp.sap_den(conn, CLINIC, room)
    return {c["id"] for k in o for c in k["chi_dinh"]}


async def test_phong_doi_tac_chi_nhan_viec_doi_tac_lam_tron(bat: RB) -> None:  # noqa: F811
    phong_dt, tron, dd = await _chuan_bi(bat)
    # (a) Sắp đến: phòng đối tác thấy việc đối tác làm trọn, không thấy mẫu lấy máu.
    o_dt = await _ids_sap_den(bat, phong_dt)
    assert tron in o_dt and dd not in o_dt
    # Phòng lấy máu thường: ngược lại.
    o_mau = await _ids_sap_den(bat, bat.khac_node)
    assert dd in o_mau and tron not in o_mau
    # Nhận ở phòng thường không nhận được việc đối tác làm trọn.
    with pytest.raises(LuotKhamConflictError):
        await _nhan(bat, bat.khac_node, tron)
    # Phòng đối tác không nhận được mẫu điều dưỡng lấy.
    with pytest.raises(LuotKhamConflictError):
        await _nhan(bat, phong_dt, dd)
    kq = await _nhan(bat, phong_dt, tron)
    assert kq["da_nhan"] == [tron]
    assert (
        await bat.pool.fetchval(
            "SELECT room_id::text FROM service_order WHERE id = $1::uuid", tron
        )
        == phong_dt
    )


async def test_bat_dau_da_nhan_mau_tra_ket_qua_hoan_tac(bat: RB) -> None:  # noqa: F811
    phong_dt, tron, _dd = await _chuan_bi(bat)
    await _nhan(bat, phong_dt, tron)
    don = await bat.pool.fetchrow(
        "SELECT execution_revision, routing_revision FROM service_order"
        " WHERE id = $1::uuid",
        tron,
    )
    await ServiceExecutionService(bat.pool).bat_dau(
        order_id=tron,
        expected_execution_revision=int(don["execution_revision"]),
        expected_routing_revision=int(don["routing_revision"]),
        identity=bat.truong_ca,
    )
    svc = DoiTacService(bat.pool)
    # (b) "Đã nhận mẫu" ở phòng = lệnh của bàn đối tác.
    nhan = await svc.doi_tac_cho_tai_lieu(
        order_id=tron, identity=bat.truong_ca, ghi_chu="mẫu đủ"
    )
    assert nhan == {"ok": True, "already": False}
    o = await bat.pool.fetchrow(
        "SELECT exec_status, execution_status, doi_tac_cho_tai_lieu_luc, ket_qua_luc"
        " FROM service_order WHERE id = $1::uuid",
        tron,
    )
    assert o["exec_status"] == "performed" and o["execution_status"] == "COMPLETED"
    assert o["doi_tac_cho_tai_lieu_luc"] is not None and o["ket_qua_luc"] is None
    assert (
        await bat.pool.fetchval(
            "SELECT count(*) FROM queue_entry WHERE ref_id = $1::uuid"
            " AND status NOT IN ('done', 'left', 'cancelled')",
            tron,
        )
        == 0
    ), "khách rời hàng phòng đối tác"
    assert (
        await bat.pool.fetchval(
            "SELECT count(*) FROM service_execution_attempt"
            " WHERE service_order_id = $1::uuid AND status = 'COMPLETED'",
            tron,
        )
        == 1
    )
    viec = await svc.mot_viec(order_id=tron, identity=bat.truong_ca)
    assert viec["trang_thai"] == "DA_NHAN_MAU"
    assert viec["trang_thai_chu"] == "Đã nhận mẫu · chờ kết quả"
    assert viec["nhan_mau_duoc"] is False
    # (c) Chưa có tệp / phiếu → không trả được, báo rõ.
    assert viec["tra_ket_qua_duoc"] is False
    with pytest.raises(LuotKhamConflictError) as e:
        await svc.tra_ket_qua(order_id=tron, identity=bat.truong_ca)
    assert e.value.error_code == "CHUA_CO_KET_QUA"
    # Có kết quả ghi chữ (cùng điều kiện với tệp / phiếu) → Trả kết quả.
    await bat.pool.execute(
        "UPDATE service_order SET result_note = 'Âm tính' WHERE id = $1::uuid", tron
    )
    assert (await svc.tra_ket_qua(order_id=tron, identity=bat.truong_ca))[
        "already"
    ] is False
    viec = await svc.mot_viec(order_id=tron, identity=bat.truong_ca)
    assert viec["trang_thai"] == "DA_GUI_KET_QUA"
    assert viec["trang_thai_chu"] == "Có kết quả"
    # Hoàn tác: nhận mẫu không gỡ được khi đã trả → gỡ trả kết quả trước.
    with pytest.raises(LuotKhamConflictError):
        await svc.huy_nhan_mau(order_id=tron, identity=bat.truong_ca)
    assert (await svc.huy_tra_ket_qua(order_id=tron, identity=bat.truong_ca))[
        "already"
    ] is False
    assert (await svc.huy_nhan_mau(order_id=tron, identity=bat.truong_ca))[
        "already"
    ] is False
    viec = await svc.mot_viec(order_id=tron, identity=bat.truong_ca)
    assert viec["trang_thai_chu"] == "Chờ làm" and viec["nhan_mau_duoc"] is True


async def test_thu_ho_tuy_chon_khong_vao_tien_phong_kham(bat: RB) -> None:  # noqa: F811
    _phong_dt, tron, _dd = await _chuan_bi(bat)
    await bat.pool.execute(
        "UPDATE service_price SET billing_owner = 'EXTERNAL_PARTNER'"
        " WHERE clinic_id = $1::uuid AND service_code = (SELECT service_code FROM"
        " service_order WHERE id = $2::uuid)",
        CLINIC,
        tron,
    )
    await bat.pool.execute(
        "INSERT INTO doi_tac_nhan_viec (clinic_id, service_order_id, ly_do)"
        " VALUES ($1::uuid, $2::uuid, 'DA_LAY_MAU') ON CONFLICT DO NOTHING",
        CLINIC,
        tron,
    )
    svc = DoiTacService(bat.pool)
    truoc = await bat.pool.fetchval("SELECT count(*) FROM payment_cycle")
    # Rỗng = không ghi gì, không lỗi.
    for rong in ("", "   ", None):
        kq = await svc.ghi_nhan_da_thu(
            order_id=tron, identity=bat.truong_ca, so_tien=rong, hinh_thuc=None
        )
        assert kq == {"ok": True, "bo_qua": True, "id": None}
    assert not await bat.pool.fetchval(
        "SELECT count(*) FROM doi_tac_thanh_toan WHERE service_order_id = $1::uuid",
        tron,
    )
    with pytest.raises(ValidationError):
        await svc.ghi_nhan_da_thu(
            order_id=tron, identity=bat.truong_ca, so_tien="abc", hinh_thuc="CASH"
        )
    kq = await svc.ghi_nhan_da_thu(
        order_id=tron, identity=bat.truong_ca, so_tien="0", hinh_thuc="TRANSFER"
    )
    assert kq["already"] is False
    assert await bat.pool.fetchval("SELECT count(*) FROM payment_cycle") == truoc


async def test_tai_khoan_doi_tac_chi_dien_phieu_viec_doi_tac(bat: RB) -> None:  # noqa: F811
    """(e) Vai PARTNER: điền phiếu được cho ĐÚNG việc đối tác; chỉ định khác của
    khách thì không. Mọi cửa khác vẫn đóng (`get_current_identity` từ chối)."""
    from fastapi import HTTPException

    from clinicai.api.identity import get_current_identity
    from clinicai.core.exceptions import SafetyGateError
    from clinicai.services.form_engine_service import doi_quyen_dien

    _phong_dt, tron, _dd = await _chuan_bi(bat)
    thuong = await _cd(bat)
    async with bat.pool.acquire() as conn:
        dt = await _nguoi(conn, bat.loc, "PARTNER")
        await conn.execute(
            "INSERT INTO doi_tac_nhan_viec (clinic_id, service_order_id, ly_do)"
            " VALUES ($1::uuid, $2::uuid, 'DA_LAY_MAU') ON CONFLICT DO NOTHING",
            CLINIC,
            tron,
        )
        await doi_quyen_dien(conn, dt, service_order_id=tron)
        with pytest.raises(SafetyGateError):
            await doi_quyen_dien(conn, dt, service_order_id=thuong)
    with pytest.raises(HTTPException) as e:
        await get_current_identity(dt)
    assert e.value.status_code == 403
    # Một việc của bàn đối tác: đọc được; chỉ định thường: cùng câu "không thấy".
    assert (await DoiTacService(bat.pool).mot_viec(order_id=tron, identity=dt))[
        "xem_tep"
    ] is False
    with pytest.raises(SafetyGateError):
        await DoiTacService(bat.pool).mot_viec(order_id=thuong, identity=dt)
