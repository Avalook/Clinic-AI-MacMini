"""Phiếu điều trị theo chỉ định + LÀM TẠI BÀN KHÁM + thanh toán (Tuyền chốt
07/10/2026), trên Postgres thật.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55600/postgres \\
        .venv/bin/pytest src/tests/services/test_dieu_tri_ban_kham_db.py

Bác sĩ kê Laser trong lượt khám thường rồi làm luôn ở bàn khám: qua ĐÚNG cổng
tiền của phòng (chưa thu + chưa tick → chặn, gợi ý tick; tick → làm được), hoàn
tác hai bước không đụng tiền, check-out xử lý như dịch vụ làm ở phòng, quầy thu
đúng một dòng đúng giá. Lượt đặt lịch Laser: chỉ định tự sinh, bác sĩ kê lại
không thành hai dòng, phòng ghi phiếu điều trị thì bàn khám thấy đúng phiếu ấy.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.events.catalogue import DIEU_TRI_SINH_CHI_DINH
from clinicai.services import dieu_tri_ban_kham
from clinicai.services.bill_service import hoa_don_con_no
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.finance_gate import CAU_CHUA_THU, states_for_orders
from clinicai.services.form_engine_service import FormEngineService
from clinicai.services.hoan_tac_service import HoanTacService, tien_thua_cua_luot
from clinicai.services.lam_truoc_thu_sau import LamTruocThuSauService
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from clinicai.services.luot_kham_service import LuotKhamService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh, chay_het
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _chon,
    _dung,
    _khoa,
    _phong,
    _su_kien,
    _thu,
)
from tests.services.test_thu_truoc_lam_truoc_tick_db import day_thu_truoc

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture(autouse=True)
async def _thu_truoc(pool: asyncpg.Pool) -> AsyncIterator[None]:  # noqa: F811
    # Dây "thu trước khi làm" BẬT (mặc định prod): chưa thu chỉ làm khi tick.
    async with day_thu_truoc(pool, True):
        yield


async def _laser(pool: asyncpg.Pool) -> asyncpg.Record:  # noqa: F811
    """Loại khám Điều trị "Laser trẻ hoá tiền đình" + dòng giá nó trỏ tới."""
    r = await pool.fetchrow(
        "SELECT st.id::text AS loai, sp.service_code AS ma, sp.unit_price AS gia,"
        "       sp.name"
        "  FROM service_type st JOIN service_price sp ON sp.id = st.service_price_id"
        " WHERE st.clinic_id = $1::uuid AND st.code = 'DT_LASER_TIEN_DINH'",
        CLINIC,
    )
    assert r is not None, "migration 20261007600000 phải có loại Điều trị Laser"
    return r


async def _lich_ban_kham(pool: asyncpg.Pool, ca: Ca) -> str:  # noqa: F811
    """Bác sĩ có ca ĐÃ DUYỆT hôm nay ở một phòng — phòng của bàn khám."""
    ma = f"T-BK-{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        phong = await _phong(conn, ca.loc, ma[-8:])
        # Phòng bàn khám KHÔNG nhận dịch vụ siêu âm: bài khác chạy song song
        # trên cùng DB tự xếp siêu âm vào đây thì "đang ở" mang thêm tên bác sĩ
        # trực → bài hành trình khách đỏ oan (CI máy 07/10).
        await conn.execute(
            "DELETE FROM clinic_room_node WHERE room_id = $1::uuid", phong
        )
        await conn.execute(
            "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, nhom_nghe, room_id)"
            " VALUES ($1::uuid, $2, 'Bàn khám test', 'BAC_SI', $3::uuid)",
            CLINIC,
            ma,
            phong,
        )
        await conn.execute(
            "INSERT INTO work_roster (clinic_id, week_start, work_date, shift,"
            " station, staff_id, staff_name, status)"
            " SELECT $1::uuid, d - (extract(isodow FROM d)::int - 1), d, 'FULL', $2,"
            " $3::uuid, 'Test', 'APPROVED'"
            " FROM (SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS d) x",
            CLINIC,
            ma,
            ca.bac_si.staff_id,
        )
    return phong


async def _don_hang(pool: asyncpg.Pool, order: str) -> asyncpg.Record:  # noqa: F811
    return await pool.fetchrow(
        "SELECT room_id::text AS room_id, routing_status, exec_status"
        " FROM service_order WHERE id = $1::uuid",
        order,
    )


async def _vao_kham(pool: asyncpg.Pool, ca: Ca, visit: str) -> str:  # noqa: F811
    con = str(
        await pool.fetchval(
            "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'PRIMARY'",
            visit,
        )
    )
    await LuotKhamService(pool).start_consultation(
        consultation_id=con, identity=ca.bac_si
    )
    return con


async def _ke(pool: asyncpg.Pool, ca: Ca, con: str, ma: str) -> dict[str, Any]:  # noqa: F811
    return await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ma],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )


async def _the(pool: asyncpg.Pool, ca: Ca, visit: str) -> dict[str, Any]:  # noqa: F811
    goi = await dieu_tri_ban_kham.doc_the(pool, identity=ca.bac_si, visit_id=visit)
    [t] = goi["the"]
    return dict(t)


async def _bam(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    visit: str,
    t: dict[str, Any],
    lenh: str,
) -> dict[str, Any]:
    return await dieu_tri_ban_kham.thao_tac(
        pool,
        identity=ca.bac_si,
        visit_id=visit,
        order_id=t["order_id"],
        lenh=lenh,
        expected_execution_revision=t["execution_revision"],
        attempt_id=t["attempt_id"],
        idempotency_key=_khoa(),
    )


async def _tien(pool: asyncpg.Pool, order: str) -> str:  # noqa: F811
    async with pool.acquire() as conn:
        return (await states_for_orders(conn, CLINIC, [order]))[order].finance_state


async def test_lam_tai_ban_kham_qua_cua_tien_hoan_tac_khong_dung_tien_quay_thu_mot_dong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    laser = await _laser(pool)
    phong_bk = await _lich_ban_kham(pool, ca)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _vao_kham(pool, ca, visit)
    kq = await _ke(pool, ca, con, laser["ma"])
    order = kq["order_ids"][0]

    # 1. Chưa thu, chưa tick → thẻ nói vì sao; lệnh bị chặn bằng ĐÚNG câu cửa
    #    tiền của phòng (gợi ý tick).
    t = await _the(pool, ca, visit)
    assert t["order_id"] == order and t["trang_thai"] == "CHUA_LAM"
    assert t["lam_duoc"] is False and t["ly_do_khong_lam"] == CAU_CHUA_THU
    assert t["mau_chon_san"] == "PHIEU_DIEU_TRI"
    with pytest.raises(LuotKhamConflictError) as e:
        await _bam(pool, ca, visit, t, "lam")
    assert e.value.error_code == "FINANCE_NOT_READY" and str(e.value) == CAU_CHUA_THU

    # 2. Tick "Làm trước – thu sau" ở Bàn khám → làm được.
    await LamTruocThuSauService(pool).dat(visit_id=visit, bat=True, identity=ca.bac_si)
    t = await _the(pool, ca, visit)
    assert t["lam_duoc"] is True
    bd = await _bam(pool, ca, visit, t, "lam")
    assert bd["execution_status"] == "IN_PROGRESS" and bd["noi_lam"] == "BAN_KHAM"
    lan = await pool.fetchrow(
        "SELECT noi_lam, status, room_id_snapshot::text AS phong"
        " FROM service_execution_attempt WHERE id = $1::uuid",
        bd["attempt_id"],
    )
    assert (lan["noi_lam"], lan["status"], lan["phong"]) == (
        "BAN_KHAM",
        "IN_PROGRESS",
        phong_bk,
    )
    # Chỉ định chưa có phòng → xếp vào phòng bàn khám; cột cũ theo kịp (công nợ,
    # vòng đọc đọc cột cũ).
    d = await _don_hang(pool, order)
    assert (d["room_id"], d["routing_status"], d["exec_status"]) == (
        phong_bk,
        "ASSIGNED",
        "in_progress",
    )
    # Phiên bác sĩ VẪN đang phục vụ (không vướng một-chỗ-serving).
    assert (
        await pool.fetchval(
            "SELECT status FROM queue_entry WHERE ref_id = $1::uuid", con
        )
        == "serving"
    )
    [sk] = await _su_kien(pool, "service.started", order)
    assert json.loads(sk["payload"])["noi_lam"] == "BAN_KHAM"
    t = await _the(pool, ca, visit)
    assert t["trang_thai"] == "DANG_LAM_BAN_KHAM" and t["xong_duoc"]
    tien_truoc = await _tien(pool, order)
    assert tien_truoc == "DUE"

    # 3. Hoàn tác Bắt đầu → chờ làm; không đụng tiền. Làm lại → Xong.
    await _bam(pool, ca, visit, t, "huy-lam")
    t = await _the(pool, ca, visit)
    assert t["trang_thai"] == "CHUA_LAM" and await _tien(pool, order) == tien_truoc
    d = await _don_hang(pool, order)
    assert (d["room_id"], d["routing_status"], d["exec_status"]) == (
        None,
        "UNASSIGNED",
        "authorized",
    )
    await _bam(pool, ca, visit, t, "lam")
    t = await _the(pool, ca, visit)
    await _bam(pool, ca, visit, t, "xong")
    t = await _the(pool, ca, visit)
    assert t["trang_thai"] == "XONG" and t["noi_lam"] == "BAN_KHAM"
    assert t["hoan_tac_xong_duoc"]
    assert (await _don_hang(pool, order))["exec_status"] == "performed"
    # Hoàn tác Xong → đang làm tại bàn khám; Xong lại. Tiền vẫn như cũ.
    await _bam(pool, ca, visit, t, "hoan-tac-xong")
    t = await _the(pool, ca, visit)
    assert t["trang_thai"] == "DANG_LAM_BAN_KHAM"
    assert await _tien(pool, order) == tien_truoc
    await _bam(pool, ca, visit, t, "xong")
    assert (await _the(pool, ca, visit))["trang_thai"] == "XONG"
    assert await _tien(pool, order) == "DUE"

    # 4. Check-out: đã làm chưa thu = NỢ, chặn như dịch vụ làm ở phòng.
    ss = await CheckoutService(pool).readiness(identity=ca.le_tan, visit_id=visit)
    assert order in [d["source_id"] for d in ss["no_khi_ve"]["dong"]]
    assert ss["no_khi_ve"]["chan"] is True and ss["can_close"] is False

    # 5. Quầy thu ĐÚNG một dòng, ĐÚNG giá bảng giá; thu xong → dòng sổ (nguồn của
    #    báo cáo cuối ngày / doanh thu theo dịch vụ) mang đúng tên + tiền.
    async with pool.acquire() as conn:
        hd = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)
    dong = [d for d in hd.dong if d.source_id == order]
    assert len(dong) == 1 and int(dong[0].thanh_tien or 0) == int(laser["gia"])
    await _thu(pool, visit, ca.thu_ngan)
    so = await pool.fetch(
        "SELECT bl.name_snapshot, bl.line_total FROM payment_bill_line bl"
        "  JOIN payment_cycle c ON c.payment_cycle_id = bl.payment_cycle_id"
        " WHERE bl.source_type = 'service_order' AND bl.source_id = $1"
        "   AND c.status = 'PAID'",
        order,
    )
    assert len(so) == 1 and int(so[0]["line_total"]) == int(laser["gia"])
    assert so[0]["name_snapshot"] == laser["name"]
    assert await _tien(pool, order) == "PAID"
    ss = await CheckoutService(pool).readiness(identity=ca.le_tan, visit_id=visit)
    assert ss["no_khi_ve"]["chan"] is False


async def test_da_thu_thi_lam_tai_ban_kham_duoc_khong_can_tick(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    laser = await _laser(pool)
    # Không phụ thuộc DB có phòng thủ thuật để tự xếp: bàn khám có phòng.
    await _lich_ban_kham(pool, ca)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _vao_kham(pool, ca, visit)
    order = (await _ke(pool, ca, con, laser["ma"]))["order_ids"][0]
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.thu_ngan)
    await chay_hanh_trinh(pool)
    t = await _the(pool, ca, visit)
    assert t["da_thu"] and t["lam_duoc"]
    await _bam(pool, ca, visit, t, "lam")
    t = await _the(pool, ca, visit)
    # Đã xếp phòng thì chỗ chờ phòng "đợi" (khách ở bàn khám), Xong đóng nó.
    await _bam(pool, ca, visit, t, "xong")
    assert not await pool.fetchval(
        "SELECT count(*) FROM queue_entry WHERE ref_id = $1::uuid"
        " AND status NOT IN ('done', 'left', 'cancelled')",
        order,
    )


async def test_bo_chi_dinh_dieu_tri_da_thu_thanh_tien_thua(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    laser = await _laser(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _vao_kham(pool, ca, visit)
    order = (await _ke(pool, ca, con, laser["ma"]))["order_ids"][0]
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.thu_ngan)
    kq = await HoanTacService(pool).huy_chi_dinh(
        order_id=order, identity=ca.bac_si, xac_nhan=True, ly_do="Khách đổi ý Laser"
    )
    assert kq["da_thu_tien"] is True and kq["tien_thua"] == int(laser["gia"])
    async with pool.acquire() as conn:
        thua = await tien_thua_cua_luot(conn, CLINIC, [visit])
    assert thua[visit]["tong"] == int(laser["gia"])


async def test_luot_dat_laser_tu_sinh_ke_lai_khong_hai_dong_phong_ghi_ban_kham_thay(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    laser = await _laser(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), laser["loai"])
    await chay_het(pool, DIEU_TRI_SINH_CHI_DINH)
    [order] = [
        r["id"]
        for r in await pool.fetch(
            "SELECT id::text FROM service_order WHERE visit_id = $1::uuid"
            " AND exec_status <> 'cancelled'",
            visit,
        )
    ]
    t = await _the(pool, ca, visit)
    assert t["order_id"] == order and t["da_dat"] is True

    # Bác sĩ kê lại đúng dịch vụ ấy → KHÔNG thành chỉ định thứ hai.
    con = await _vao_kham(pool, ca, visit)
    kq = await _ke(pool, ca, con, laser["ma"])
    assert kq["order_ids"] == [order] and kq["da_co_san"] == [laser["ma"]]
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM service_order WHERE visit_id = $1::uuid"
            " AND exec_status <> 'cancelled'",
            visit,
        )
        == 1
    )

    # Quầy: đúng một dòng, đúng giá; lượt Điều trị không có phí khám.
    await _chon(pool, ca, visit, [order])
    async with pool.acquire() as conn:
        hd = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)
    assert not [d for d in hd.dong if d.source_type == "exam"]
    [d] = [d for d in hd.dong if d.source_type == "service_order"]
    assert d.source_id == order and int(d.thanh_tien or 0) == int(laser["gia"])
    await _thu(pool, visit, ca.thu_ngan)
    async with pool.acquire() as conn:
        assert (await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)).dong == []

    # Phòng ghi phiếu điều trị (cùng engine phiếu kết quả) → bàn khám thấy ĐÚNG
    # phiếu ấy (một form_instance), ghi tiếp được trên revision mới.
    fe = FormEngineService(pool)
    ph = await fe.mo_phieu(
        service_order_id=order, form_id="KQ_PHIEU_DIEU_TRI", identity=ca.dd
    )
    luu = await fe.luu_nhap(
        phieu_id=ph["id"],
        du_lieu={"cam_nhan": {"gia_tri": "Đỡ khô rát", "nguon": "USER"}},
        expected_revision=int(ph["revision"]),
        identity=ca.dd,
    )
    t = await _the(pool, ca, visit)
    assert t["phieu"]["phieu_id"] == ph["id"]
    assert t["phieu"]["revision"] == luu["revision"]
    assert t["mau_chon_san"] == "PHIEU_DIEU_TRI"
    lai = await fe.mo_phieu(
        service_order_id=order, form_id="KQ_PHIEU_DIEU_TRI", identity=ca.bac_si
    )
    assert lai["id"] == ph["id"]
    assert lai["du_lieu"]["cam_nhan"]["gia_tri"] == "Đỡ khô rát"


async def test_chi_lam_tai_ban_kham_chi_dinh_dieu_tri(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    from clinicai.core.exceptions import ValidationError

    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _vao_kham(pool, ca, visit)
    order = (await _ke(pool, ca, con, ca.ma_dv))["order_ids"][0]  # siêu âm
    assert (await dieu_tri_ban_kham.doc_the(pool, identity=ca.bac_si, visit_id=visit))[
        "the"
    ] == []
    with pytest.raises(ValidationError):
        await dieu_tri_ban_kham.thao_tac(
            pool,
            identity=ca.bac_si,
            visit_id=visit,
            order_id=order,
            lenh="lam",
            expected_execution_revision=0,
        )


# ── Luồng lượt Điều trị (phản hồi bấm thử staging 07/10/2026) ────────────────


async def _don_dat_san(pool: asyncpg.Pool, visit: str) -> str:  # noqa: F811
    await chay_het(pool, DIEU_TRI_SINH_CHI_DINH)
    [order] = [
        r["id"]
        for r in await pool.fetch(
            "SELECT id::text FROM service_order WHERE visit_id = $1::uuid"
            " AND exec_status <> 'cancelled'",
            visit,
        )
    ]
    return str(order)


async def _lam_o_phong(pool: asyncpg.Pool, ca: Ca, order: str) -> None:  # noqa: F811
    """Quầy xếp phòng tay → phòng Bắt đầu → Xong (đường phòng sẵn có). Phòng
    thử làm được bước của chỉ định (Laser = thủ thuật, siêu âm = siêu âm)."""
    from clinicai.services.service_execution_service import ServiceExecutionService
    from clinicai.services.service_routing_service import ServiceRoutingService

    d = await pool.fetchrow(
        "SELECT routing_revision, execution_revision, node_code FROM service_order"
        " WHERE id = $1::uuid",
        order,
    )
    async with pool.acquire() as conn:
        phong = await _phong(conn, ca.loc, uuid.uuid4().hex[:8])
        # Chỉ đúng bước của chỉ định — không thành phòng siêu âm thừa cho bài khác.
        await conn.execute(
            "DELETE FROM clinic_room_node WHERE room_id = $1::uuid", phong
        )
        await conn.execute(
            "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
            " VALUES ($1::uuid, $2::uuid, $3) ON CONFLICT DO NOTHING",
            CLINIC,
            phong,
            d["node_code"],
        )
    await ServiceRoutingService(pool).assign(
        order_id=order,
        room_id=phong,
        expected_routing_revision=int(d["routing_revision"]),
        reason_code="MANUAL_CORRECTION",
        identity=ca.thu_ngan,
        idempotency_key=_khoa(),
    )
    d = await pool.fetchrow(
        "SELECT routing_revision, execution_revision FROM service_order"
        " WHERE id = $1::uuid",
        order,
    )
    mo = await ServiceExecutionService(pool).bat_dau(
        order_id=order,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    await ServiceExecutionService(pool).xong(
        order_id=order,
        attempt_id=mo["attempt_id"],
        expected_execution_revision=mo["execution_revision"],
        identity=ca.dd,
        idempotency_key=_khoa(),
    )


async def _vong(pool: asyncpg.Pool, visit: str) -> list[str]:  # noqa: F811
    return [
        str(r["status"])
        for r in await pool.fetch(
            "SELECT status FROM review_round WHERE visit_id = $1::uuid"
            " ORDER BY round_no",
            visit,
        )
    ]


async def _cho_doc_kq(pool: asyncpg.Pool, visit: str) -> int:  # noqa: F811
    """Chỗ chờ "đọc kết quả" (REVIEW) còn sống ở hàng bác sĩ."""
    return int(
        await pool.fetchval(
            "SELECT count(*) FROM queue_entry WHERE visit_id = $1::uuid"
            " AND reason = 'REVIEW'"
            " AND status IN ('blocked', 'waiting', 'called', 'serving')",
            visit,
        )
    )


async def _con_trong_hang_bac_si(pool: asyncpg.Pool, visit: str) -> int:  # noqa: F811
    return int(
        await pool.fetchval(
            "SELECT count(*) FROM queue_entry WHERE visit_id = $1::uuid"
            " AND lane = 'DOCTOR'"
            " AND status IN ('blocked', 'waiting', 'called', 'serving')",
            visit,
        )
    )


async def test_luot_dieu_tri_lam_o_phong_check_out_khong_qua_bac_si(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Happy path A: khách đặt Laser lên thẳng phòng — phòng làm, quầy thu,
    check-out. Hàng bác sĩ là tuỳ chọn: không vướng "bác sĩ chưa khám", không
    vòng đọc kết quả; check-out xong khách rời hàng bác sĩ."""
    from tests.chay_nguoi_dua_tin import chay_ben_nhan

    ca = await _dung(pool)
    laser = await _laser(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), laser["loai"])
    order = await _don_dat_san(pool, visit)
    # Khách vẫn hiện ở hàng bác sĩ (tuỳ chọn) trước khi ai nhận.
    assert await _con_trong_hang_bac_si(pool, visit) == 1
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.thu_ngan)
    await _lam_o_phong(pool, ca, order)
    await chay_ben_nhan(pool, "vong_doc_luot_kham")

    assert await _vong(pool, visit) == []
    assert await _cho_doc_kq(pool, visit) == 0
    ss = await CheckoutService(pool).readiness(identity=ca.le_tan, visit_id=visit)
    assert ss["blockers"] == [] and ss["can_close"] is True
    await CheckoutService(pool).close(identity=ca.le_tan, visit_id=visit)
    assert await _con_trong_hang_bac_si(pool, visit) == 0


async def test_luot_dieu_tri_bac_si_kham_roi_lam_tai_ban_kham_khong_vong_doc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Happy path B: bác sĩ đã Bắt đầu khám (theo luật bàn khám), Khám xong khi
    Laser chưa làm → vòng đọc chờ; bác sĩ LÀM NGAY TẠI BÀN KHÁM → vòng đóng
    không cần đọc (review.skipped, lý do lam_tai_ban_kham), không chỗ chờ "Kết
    quả cần đọc", lượt khép; thu tiền → check-out không vướng; sau check-out
    không còn trong hàng bác sĩ và thẻ chỉ đọc."""
    from tests.chay_nguoi_dua_tin import chay_ben_nhan

    ca = await _dung(pool)
    laser = await _laser(pool)
    await _lich_ban_kham(pool, ca)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), laser["loai"])
    await _don_dat_san(pool, visit)
    con = await _vao_kham(pool, ca, visit)
    await LuotKhamService(pool).kham_xong(
        consultation_id=con, identity=ca.bac_si, idempotency_key=_khoa()
    )
    assert await _vong(pool, visit) == ["collecting"]

    await LamTruocThuSauService(pool).dat(visit_id=visit, bat=True, identity=ca.bac_si)
    t = await _the(pool, ca, visit)
    await _bam(pool, ca, visit, t, "lam")
    await _bam(pool, ca, visit, await _the(pool, ca, visit), "xong")
    await chay_ben_nhan(pool, "vong_doc_luot_kham")

    assert await _vong(pool, visit) == ["closed"]
    assert await _cho_doc_kq(pool, visit) == 0
    bo_qua = await pool.fetchval(
        "SELECT payload FROM event_log WHERE aggregate_id = $1::uuid"
        " AND event_type = 'review.skipped'",
        visit,
    )
    assert json.loads(bo_qua)["ly_do"] == "lam_tai_ban_kham"
    assert await pool.fetchval(
        "SELECT exam_completed_at IS NOT NULL FROM visit WHERE visit_id = $1::uuid",
        visit,
    )

    # Tick "Làm trước – thu sau" đã chốt chỉ định khách chọn → quầy thu thẳng.
    await _thu(pool, visit, ca.thu_ngan)
    ss = await CheckoutService(pool).readiness(identity=ca.le_tan, visit_id=visit)
    assert ss["blockers"] == [] and ss["can_close"] is True
    await CheckoutService(pool).close(identity=ca.le_tan, visit_id=visit)
    assert await _con_trong_hang_bac_si(pool, visit) == 0

    # Lượt đã check-out: thẻ chỉ đọc, lệnh bị từ chối (muốn làm tiếp → mở lại).
    from clinicai.core.exceptions import ValidationError

    goi = await dieu_tri_ban_kham.doc_the(pool, identity=ca.bac_si, visit_id=visit)
    [t] = goi["the"]
    assert goi["chi_doc"] is True
    assert not (t["lam_duoc"] or t["xong_duoc"] or t["hoan_tac_xong_duoc"])
    with pytest.raises(ValidationError) as e:
        await _bam(pool, ca, visit, t, "hoan-tac-xong")
    assert str(e.value) == dieu_tri_ban_kham.CAU_LUOT_DA_DONG


async def test_luot_dieu_tri_qua_ban_kham_phong_lam_van_theo_luat_ban_kham(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Đã qua bàn khám mà dịch vụ làm ở PHÒNG khác: đúng luật lượt khám thường
    — vòng đọc kết quả mở, check-out vướng "bác sĩ chưa đọc" (không nới)."""
    from tests.chay_nguoi_dua_tin import chay_ben_nhan

    ca = await _dung(pool)
    laser = await _laser(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), laser["loai"])
    order = await _don_dat_san(pool, visit)
    con = await _vao_kham(pool, ca, visit)
    await LuotKhamService(pool).kham_xong(
        consultation_id=con, identity=ca.bac_si, idempotency_key=_khoa()
    )
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.thu_ngan)
    await _lam_o_phong(pool, ca, order)
    await chay_ben_nhan(pool, "vong_doc_luot_kham")
    assert await _vong(pool, visit) == ["ready"]
    assert await _cho_doc_kq(pool, visit) == 1
    ss = await CheckoutService(pool).readiness(identity=ca.le_tan, visit_id=visit)
    assert "exam_open" in [b["type"] for b in ss["blockers"]]


async def test_dich_vu_xong_sau_check_out_khong_mo_lai_ket_qua_can_doc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """GỐC lỗi staging 07/10 (lượt 016a401c): check-out 15:32 (vượt bằng lý do),
    dịch vụ xong 15:37 → khối vòng đọc mở chỗ chờ REVIEW cho khách đã về. Nay
    lượt đã check-out thì kết quả muộn không đưa khách lại hàng bác sĩ."""
    from tests.chay_nguoi_dua_tin import chay_ben_nhan

    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _vao_kham(pool, ca, visit)
    order = (await _ke(pool, ca, con, ca.ma_dv))["order_ids"][0]
    await LuotKhamService(pool).kham_xong(
        consultation_id=con, identity=ca.bac_si, idempotency_key=_khoa()
    )
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.thu_ngan)
    await CheckoutService(pool).close(
        identity=ca.le_tan, visit_id=visit, override_reason="Khách cần về gấp"
    )
    await _lam_o_phong(pool, ca, order)
    await chay_ben_nhan(pool, "vong_doc_luot_kham")
    assert await _cho_doc_kq(pool, visit) == 0
    assert await _con_trong_hang_bac_si(pool, visit) == 0


# ── Phiếu điều trị dùng chung bàn khám ↔ phòng + bản in (07/10/2026 tối) ──────


async def test_phieu_dieu_tri_ban_kham_ghi_phong_doc_luu_sau_xong_in_khong_nhap(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Bàn khám ghi phiếu điều trị → phòng mở CÙNG phiếu thấy chữ; thẻ chỉ đọc
    trả mỗi ô MỘT nhãn ("Cảm nhận", "Vấn đề sau điều trị") + người sửa. Phòng
    [Xong] (lệnh hoàn tất của engine) rồi vẫn lưu tiếp được — mẫu không có bước
    Hoàn tất; bản in không ghi BẢN NHÁP; khối kết quả của lượt trả nội dung kể cả
    khi phiếu còn nháp, đánh dấu chỉ định là ĐIỀU TRỊ (bản in mục riêng)."""
    from clinicai.phieu_kham.ket_qua_chi_dinh import doc_ket_qua_theo_chi_dinh

    ca = await _dung(pool)
    laser = await _laser(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), laser["loai"])
    order = await _don_dat_san(pool, visit)
    fe = FormEngineService(pool)

    # Bàn khám (bác sĩ) mở + ghi.
    bk = await fe.mo_phieu(
        service_order_id=order, form_id="KQ_PHIEU_DIEU_TRI", identity=ca.bac_si
    )
    assert bk["khong_hoan_tat"] is True
    luu = await fe.luu_nhap(
        phieu_id=bk["id"],
        du_lieu={
            "cam_nhan": {"gia_tri": "Ấm, dễ chịu", "nguon": "USER"},
            "van_de_sau": {"gia_tri": "Không", "nguon": "USER"},
        },
        expected_revision=int(bk["revision"]),
        identity=ca.bac_si,
    )
    assert luu["nguoi_sua"]

    # Phòng (điều dưỡng) mở → CÙNG phiếu, đúng chữ bàn khám vừa ghi.
    ph = await fe.mo_phieu(
        service_order_id=order, form_id="KQ_PHIEU_DIEU_TRI", identity=ca.dd
    )
    assert ph["id"] == bk["id"] and ph["revision"] == luu["revision"]
    assert ph["du_lieu"]["cam_nhan"]["gia_tri"] == "Ấm, dễ chịu"
    assert ph["nguoi_sua"] == luu["nguoi_sua"]

    # Thẻ chỉ đọc: mỗi ô một nhãn, đúng nguyên văn.
    t = await _the(pool, ca, visit)
    assert [(o["ten"], o["gia_tri"]) for o in t["phieu"]["o"]] == [
        ("Cảm nhận", "Ấm, dễ chịu"),
        ("Vấn đề sau điều trị", "Không"),
    ]

    # Khối kết quả của lượt (nguồn bản in gộp): nội dung có dù phiếu còn nháp.
    async with pool.acquire() as conn:
        ds = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC, visit_id=visit)
    [c] = [x for x in ds if x["service_order_id"] == order]
    assert c["dieu_tri"] is True
    [k] = [x for x in c["ket_qua"] if x["form_id"] == "KQ_PHIEU_DIEU_TRI"]
    assert (
        k["trang_thai"] == "DRAFT" and k["du_lieu"]["van_de_sau"]["gia_tri"] == "Không"
    )

    # Phòng bấm [Xong] (engine hoàn tất) → vẫn lưu tiếp được, không cần [Sửa lại].
    ht = await fe.hoan_tat(
        phieu_id=ph["id"], expected_revision=int(luu["revision"]), identity=ca.dd
    )
    lai = await fe.luu_nhap(
        phieu_id=ph["id"],
        du_lieu={"cam_nhan": {"gia_tri": "Ấm, dễ chịu — lần 2", "nguon": "USER"}},
        expected_revision=int(ht["revision"]),
        identity=ca.bac_si,
    )
    assert lai["revision"] == int(ht["revision"]) + 1
    # Xong lần nữa (đã chốt) vẫn trả kết quả, không ném.
    assert (
        await fe.hoan_tat(
            phieu_id=ph["id"], expected_revision=int(lai["revision"]), identity=ca.dd
        )
    )["da_hoan_tat"]
    ban_in = await fe.in_ket_qua(service_order_id=order, identity=ca.bac_si)
    [p] = ban_in["phieu"]
    assert p["ban_nhap"] is False
    assert p["du_lieu"]["cam_nhan"]["gia_tri"] == "Ấm, dễ chịu — lần 2"
