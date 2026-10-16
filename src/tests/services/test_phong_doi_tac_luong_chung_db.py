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
(f) Phòng đối tác như MỌI phòng khi xếp (Tuyền 16/10/2026): gợi ý / quầy thu /
    trưởng ca / đổi phòng / dây H4 đưa việc đối tác làm trọn vào phòng đối tác
    (phòng không có lịch trực vẫn là ứng viên "đang vận hành"); việc thường KHÔNG
    vào phòng đối tác dù phòng ấy được gắn dịch vụ thường.
"""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.phieu_kham.hanh_trinh import NOI_PHONG_DOI_TAC, doc_hanh_trinh
from clinicai.services import nhan_tai_phong as ntp
from clinicai.services import service_routing_service as sr
from clinicai.services.dispatch_service import DispatchService
from clinicai.services.doi_tac_service import DoiTacService
from clinicai.services.luot_kham_service import LuotKhamConflictError
from clinicai.services.quay_thu_service import PhongQuay
from clinicai.services.service_execution_service import ServiceExecutionService
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi
from tests.services.test_nhan_tai_phong_db import _chi_o, _nhan, bat  # noqa: F401
from tests.services.test_service_routing_db import (  # noqa: F401
    RB,
    _assign,
    _cd,
    _hang,
    _loi,
    _o,
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


# ── (f) Xếp phòng: phòng đối tác như mọi phòng (Tuyền 16/10/2026) ────────────


async def _la_doi_tac(b: RB, ids: list[str]) -> set[bool]:
    return {
        bool(r["la_doi_tac"])
        for r in await b.pool.fetch(
            "SELECT la_doi_tac FROM clinic_room WHERE id = ANY($1::uuid[])", ids
        )
    }


async def _goi_y(b: RB, oid: str) -> dict[str, Any]:
    return await b.svc.recommend(order_id=oid, identity=b.truong_ca)


async def _hpv(b: RB, phong_dt: str) -> str:
    """HPV đối tác tự lấy mẫu trên bước KHÔNG làm bên ngoài (như prod) — dịch vụ
    gắn cả phòng đối tác lẫn phòng thường ("mở hết phòng" 01/10)."""
    hpv = await _cd(b)
    await b.pool.execute(
        "UPDATE service_price SET doi_tac_lay_mau = true WHERE clinic_id = $1::uuid"
        " AND service_code = (SELECT service_code FROM service_order"
        " WHERE id = $2::uuid)",
        CLINIC,
        hpv,
    )
    await _chi_o(b, hpv, phong_dt, b.sa1)
    return hpv


async def test_goi_y_viec_doi_tac_ra_phong_doi_tac_viec_thuong_khong(rb: RB) -> None:  # noqa: F811
    phong_dt, tron, dd = await _chuan_bi(rb)
    hpv = await _hpv(rb, phong_dt)
    # Việc thường được gắn CẢ phòng đối tác (bẫy "mở hết phòng" 01/10).
    thuong = await _cd(rb)
    await _chi_o(rb, thuong, phong_dt, rb.sa1)

    for oid in (tron, hpv):
        g = await _goi_y(rb, oid)
        assert g["trang_thai"] == sr.GOI_Y_CO_PHONG and g["cau"] is None
        ids = [c["room_id"] for c in g["candidates"]]
        assert phong_dt in ids and await _la_doi_tac(rb, ids) == {True}
        # Phòng đối tác không có lịch trực vẫn "đang vận hành".
        [dt] = [c for c in g["candidates"] if c["room_id"] == phong_dt]
        assert "STAFF_ON_SHIFT" in dt["reason_codes"]
        assert g["che_do"] == sr.CHE_DO_XEP
    # HPV chỉ gắn (phòng đối tác, SA1): ứng viên duy nhất là phòng đối tác.
    assert [c["room_id"] for c in (await _goi_y(rb, hpv))["candidates"]] == [phong_dt]
    for oid in (dd, thuong):
        ids = [c["room_id"] for c in (await _goi_y(rb, oid))["candidates"]]
        assert ids and phong_dt not in ids and await _la_doi_tac(rb, ids) == {False}

    # Quầy thu: ô "Phòng làm dịch vụ (khách đã chốt)" có việc đối tác + phòng
    # chọn được = phòng đối tác; việc thường không có phòng đối tác.
    async with rb.pool.acquire() as conn:
        da_tra = await sr.da_tra_cho_vao_phong(conn, CLINIC, [rb.visit_id])
        pq = PhongQuay(conn, CLINIC)
        theo = {c["id"]: c for c in da_tra[rb.visit_id]}
        assert {tron, hpv, dd, thuong} <= set(theo)
        for oid, mong in ((hpv, True), (thuong, False)):
            phong = await pq.cua(
                theo[oid]["node_code"], rb.visit_id, theo[oid]["service_code"]
            )
            ids = [p["id"] for p in phong]
            assert (phong_dt in ids) is mong
            assert await _la_doi_tac(rb, ids) == {mong}
    # Trưởng ca: danh sách phòng chuyển sang + nút đổi phòng.
    td = {
        c["id"]: c
        for c in await DispatchService(rb.pool).chi_dinh(
            clinic_id=CLINIC, visit_id=rb.visit_id
        )
    }
    for oid, mong in ((tron, True), (hpv, True), (dd, False), (thuong, False)):
        ids = [str(p["id"]) for p in td[oid]["phong_lam_duoc"]]
        assert (phong_dt in ids) is mong, oid
    assert td[tron]["doi_phong_duoc"] is True


async def test_khong_phong_doi_tac_nao_giu_cau_cu(rb: RB) -> None:  # noqa: F811
    phong_dt, tron, _dd = await _chuan_bi(rb)
    # Tắt MỌI phòng đối tác của phòng khám trong giao dịch thử rồi trả lại.
    cu = await rb.pool.fetch(
        "SELECT id::text AS id FROM clinic_room WHERE clinic_id = $1::uuid"
        " AND la_doi_tac AND is_active",
        CLINIC,
    )
    ids = [r["id"] for r in cu]
    await rb.pool.execute(
        "UPDATE clinic_room SET is_active = false WHERE id = ANY($1::uuid[])", ids
    )
    try:
        g = await _goi_y(rb, tron)
        assert g["trang_thai"] == sr.GOI_Y_DOI_TAC_LAM
        assert g["cau"] == sr.CAU_DOI_TAC_LAM and g["candidates"] == []
        async with rb.pool.acquire() as conn:
            da_tra = await sr.da_tra_cho_vao_phong(conn, CLINIC, [rb.visit_id])
        assert tron not in {c["id"] for c in da_tra.get(rb.visit_id, [])}
    finally:
        await rb.pool.execute(
            "UPDATE clinic_room SET is_active = true WHERE id = ANY($1::uuid[])", ids
        )
    assert phong_dt in ids


async def test_xep_tay_vao_phong_doi_tac_va_tu_choi_sai_loai(rb: RB) -> None:  # noqa: F811
    phong_dt, tron, dd = await _chuan_bi(rb)
    thuong = await _cd(rb)
    await _chi_o(rb, thuong, phong_dt, rb.sa1)
    # Việc đối tác vào phòng thường: từ chối, câu nói đúng lý do.
    e = await _loi(_assign(rb, tron, rb.khac_node, 0), "SERVICE_PARTNER_PERFORMED")
    assert sr.CAU_VIEC_DOI_TAC_CHI_PHONG_DOI_TAC in str(e)
    # Việc phòng khám làm vào phòng đối tác (kể cả khi phòng ấy được gắn dịch vụ).
    for oid in (dd, thuong):
        await _loi(_assign(rb, oid, phong_dt, 0), "PHONG_DOI_TAC_KHONG_LAM")
    # Xếp tay (trưởng ca / quầy) việc đối tác vào phòng đối tác: được.
    kq = await _assign(rb, tron, phong_dt, 0)
    assert kq["changed"] is True
    o = await _o(rb, tron)
    assert (o["routing_status"], o["room_id"]) == ("ASSIGNED", phong_dt)
    [h] = [h for h in await _hang(rb, tron) if h["status"] == "waiting"]
    assert h["room_id"] == phong_dt
    # Quầy đặt phòng dự kiến / đổi phòng cùng luật.
    with pytest.raises(LuotKhamConflictError) as loi:
        await rb.svc.dat_phong_du_kien(
            order_id=thuong, room_id=phong_dt, identity=rb.truong_ca, nguon="truong_ca"
        )
    assert loi.value.error_code == "PHONG_DOI_TAC_KHONG_LAM"


async def test_h4_tu_xep_hpv_vao_phong_doi_tac_di_tron_luong(rb: RB) -> None:  # noqa: F811
    """Kê HPV (đối tác tự lấy mẫu) → khách chốt / thu (dây H4) → TỰ XẾP vào phòng
    đối tác, có chỗ "đang chờ" → Bắt đầu → Đã nhận mẫu → khách rời hàng.
    Mọi màn đọc hàng chờ thấy phòng đối tác như phòng thường."""
    phong_dt, _tron, _dd = await _chuan_bi(rb)
    hpv = await _hpv(rb, phong_dt)
    async with rb.pool.acquire() as conn:
        # Bàn khám "Từng dịch vụ" TRƯỚC khi xếp: LÀM Ở = Phòng đối tác.
        ht = await doc_hanh_trinh(conn, clinic_id=CLINIC, visit_id=rb.visit_id)
        assert ht is not None
        [dong] = [d for d in ht["tung_dich_vu"] if d["id"] == hpv]
        assert dong["noi"] == NOI_PHONG_DOI_TAC
        xep = await rb.svc.tu_xep_da_thu(
            conn,
            clinic_id=CLINIC,
            visit_id=rb.visit_id,
            staff_id=rb.truong_ca.staff_id,
            causation_id=rb.visit_id,
        )
    assert hpv in xep
    o = await _o(rb, hpv)
    assert (o["routing_status"], o["room_id"]) == ("ASSIGNED", phong_dt)
    [h] = [h for h in await _hang(rb, hpv) if h["status"] == "waiting"]
    assert h["room_id"] == phong_dt
    ten = await rb.pool.fetchval(
        "SELECT name FROM clinic_room WHERE id = $1::uuid", phong_dt
    )
    async with rb.pool.acquire() as conn:
        # Bàn khám: LÀM Ở = tên phòng đối tác; sơ đồ /phong: thẻ phòng đối tác
        # đếm "đang chờ".
        ht = await doc_hanh_trinh(conn, clinic_id=CLINIC, visit_id=rb.visit_id)
        assert ht is not None
        [dong] = [d for d in ht["tung_dich_vu"] if d["id"] == hpv]
        assert dong["noi"] == ten
        dem = await ntp.dem_theo_phong(conn, CLINIC, bat=False)
        assert (dem.get(phong_dt) or {}).get("dang_cho") == 1
    # Trưởng ca thấy việc ở phòng đối tác.
    [td] = [
        c
        for c in await DispatchService(rb.pool).chi_dinh(
            clinic_id=CLINIC, visit_id=rb.visit_id
        )
        if c["id"] == hpv
    ]
    assert td["room_id"] == phong_dt and td["work_status"] == "waiting"

    don = await rb.pool.fetchrow(
        "SELECT execution_revision, routing_revision FROM service_order"
        " WHERE id = $1::uuid",
        hpv,
    )
    await ServiceExecutionService(rb.pool).bat_dau(
        order_id=hpv,
        expected_execution_revision=int(don["execution_revision"]),
        expected_routing_revision=int(don["routing_revision"]),
        identity=rb.truong_ca,
    )
    assert [h["status"] for h in await _hang(rb, hpv)][-1] == "serving"
    nhan = await DoiTacService(rb.pool).doi_tac_cho_tai_lieu(
        order_id=hpv, identity=rb.truong_ca, ghi_chu="mẫu đủ"
    )
    assert nhan["ok"] is True
    assert not [
        h
        for h in await _hang(rb, hpv)
        if h["status"] not in ("done", "left", "cancelled")
    ], "khách rời hàng phòng đối tác"
    # Bàn /doi-tac vẫn thấy việc (chờ kết quả).
    viec = await DoiTacService(rb.pool).mot_viec(order_id=hpv, identity=rb.truong_ca)
    assert viec["trang_thai"] == "DA_NHAN_MAU"
