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
