"""CHẶN CHECK-OUT CÒN NỢ + GHI NỢ (Tuyền chốt 01/10/2026).

    scripts/test-nhanh.sh src/tests/services/test_cong_no_check_out_db.py

Sự cố 30/09: khách về mà dịch vụ đã làm chưa thu, check-out cho qua bằng câu lý
do tự động. Nay: còn nợ → máy chủ chặn (kể cả "về giữa chừng", kể cả có lý do);
thu xong → qua; ghi nợ kèm lý do → qua, có bản ghi, báo cáo đếm; thu nợ sau ở
quầy → khoản ghi nợ ĐÃ THU. Phí khám 0đ vì chưa chọn và khoản khách không chọn
làm / chưa làm KHÔNG là nợ.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import ValidationError
from clinicai.events.catalogue import CONG_NO
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.cong_no_service import CongNoService, doc_khach_con_no
from clinicai.services.service_execution_service import ServiceExecutionService
from tests.chay_nguoi_dua_tin import chay_ben_nhan, chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _chon,
    _don,
    _dung,
    _kham_va_chi_dinh,
    _khoa,
    _thu,
)
from tests.services.test_thu_truoc_lam_truoc_tick_db import day_thu_truoc

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

LY_DO_TU_DONG = "Lễ tân cho khách về."


@pytest_asyncio.fixture(autouse=True)
async def _lam_truoc_thu_sau(pool: asyncpg.Pool) -> AsyncIterator[None]:  # noqa: F811
    # Dây "thu trước khi làm" TẮT: phòng làm được dịch vụ khi chưa thu.
    async with day_thu_truoc(pool, False):
        yield


async def _san_sang(pool: asyncpg.Pool, ca, visit: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]  # noqa: F811
    return await CheckoutService(pool).readiness(identity=ca.le_tan, visit_id=visit)


async def _lam_xong(pool: asyncpg.Pool, ca, order: str) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    """Phòng bắt đầu + làm xong dịch vụ (chưa thu)."""
    d = await _don(pool, order)
    assert d["room_id"] is not None, "dây H4 phải tự xếp phòng sau khi chốt"
    bd = await ServiceExecutionService(pool).bat_dau(
        order_id=order,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    d2 = await _don(pool, order)
    await ServiceExecutionService(pool).xong(
        order_id=order,
        attempt_id=bd["attempt_id"],
        expected_execution_revision=int(d2["execution_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )


async def _luot_da_lam_chua_thu(pool: asyncpg.Pool):  # type: ignore[no-untyped-def]  # noqa: F811
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await chay_hanh_trinh(pool)
    await _lam_xong(pool, ca, order)
    return ca, visit, order


async def _dong(pool: asyncpg.Pool, ca, visit: str, **kw) -> dict[str, Any]:  # type: ignore[no-untyped-def]  # noqa: F811
    return await CheckoutService(pool).close(
        identity=ca.le_tan, visit_id=visit, ly_do_tu_dong=LY_DO_TU_DONG, **kw
    )


async def test_con_no_chan_moi_duong_thu_xong_thi_qua(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit, order = await _luot_da_lam_chua_thu(pool)

    ss = await _san_sang(pool, ca, visit)
    no = ss["no_khi_ve"]
    assert no["chan"] is True and no["tong"] == 300000
    assert [d["source_id"] for d in no["dong"]] == [order]
    [chan] = [b for b in ss["blockers"] if b.get("chan")]
    assert chan["type"] == "con_no" and "300.000" in chan["message"]
    # Không nhắc trùng "Chưa thu tiền dịch vụ khám".
    assert not any(b["type"] == "unpaid_service" for b in ss["blockers"])
    assert ss["can_close"] is False

    # Lý do ngoại lệ, máy tự ghi lý do, về giữa chừng: đều KHÔNG vượt được.
    for kw in (
        {},
        {"override_reason": "Khách xin về, mai quay lại trả"},
        {"incomplete": True, "incomplete_reason": "Khách bận việc nhà"},
    ):
        with pytest.raises(ValidationError, match="còn nợ"):
            await _dong(pool, ca, visit, **kw)
    assert (
        await pool.fetchval(
            "SELECT closed_at FROM visit WHERE visit_id = $1::uuid", visit
        )
        is None
    )

    # Thu ngay ở quầy (đường thu có sẵn) → hết nợ → check-out qua.
    await _thu(pool, visit, ca.thu_ngan)
    ss = await _san_sang(pool, ca, visit)
    assert ss["no_khi_ve"]["dong"] == [] and ss["no_khi_ve"]["chan"] is False
    kq = await _dong(pool, ca, visit)
    assert kq["ok"] is True and kq["closed"] is True


async def test_ghi_no_thi_qua_co_ban_ghi_bao_cao_dem_thu_sau_la_da_thu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit, order = await _luot_da_lam_chua_thu(pool)
    cn = CongNoService(pool)

    with pytest.raises(ValidationError, match="lý do"):
        await cn.ghi(identity=ca.le_tan, visit_id=visit, ly_do="  ")
    kq = await cn.ghi(identity=ca.le_tan, visit_id=visit, ly_do="Khách quên ví")
    assert (kq["so_tien"], kq["so_khoan"]) == (300000, 1)

    ss = await _san_sang(pool, ca, visit)
    no = ss["no_khi_ve"]
    assert no["chan"] is False and no["ghi_no"]["phu_du"] is True
    assert no["ghi_no"]["ly_do"] == "Khách quên ví"
    assert not any(b.get("chan") for b in ss["blockers"])

    # Về giữa chừng cũng qua khi đã ghi nợ.
    await _dong(pool, ca, visit, incomplete=True, incomplete_reason="Khách về sớm")
    r = await pool.fetchrow(
        "SELECT id::text AS id, so_tien, trang_thai, ghi_boi::text AS ghi_boi,"
        " clinic_patient_id::text AS pid, dong FROM cong_no WHERE visit_id = $1::uuid",
        visit,
    )
    assert (int(r["so_tien"]), r["trang_thai"], r["ghi_boi"]) == (
        300000,
        "CHUA_THU",
        ca.le_tan.staff_id,
    )
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type = 'cong_no.ghi'"
            " AND aggregate_id = $1::uuid",
            r["id"],
        )
        == 1
    )
    # Sổ check-out ghi đã đi qua bằng khoản ghi nợ nào.
    assert (
        await pool.fetchval(
            "SELECT payload->>'cong_no_id' FROM event_log"
            " WHERE aggregate_id = $1::uuid AND event_type = 'visit.closed_incomplete'",
            visit,
        )
        == r["id"]
    )

    # Báo cáo cuối ngày + trang chủ quản lý đếm khách còn nợ.
    async with pool.acquire() as conn:
        tong = await doc_khach_con_no(conn, CLINIC)
    assert tong["so_tien"] >= 300000 and tong["so_khach"] >= 1
    assert r["id"] in {x["id"] for x in tong["ds"]}
    bc = await BaoCaoCuoiNgayService(pool).bao_cao(identity=ca.le_tan)
    assert r["id"] in {x["id"] for x in bc["khach_con_no"]["ds"]}

    # Đã check-out thì không huỷ ghi nợ được — chỉ hết khi thu.
    with pytest.raises(ValidationError, match="check-out"):
        await cn.huy(identity=ca.le_tan, visit_id=visit, ly_do="Bấm nhầm")

    # Hôm sau khách quay lại trả ở quầy → bên nhận cong_no: ĐÃ THU.
    await _thu(pool, visit, ca.thu_ngan)
    await chay_ben_nhan(pool, CONG_NO)
    r2 = await pool.fetchrow(
        "SELECT trang_thai, thu_luc FROM cong_no WHERE id = $1::uuid", r["id"]
    )
    assert r2["trang_thai"] == "DA_THU" and r2["thu_luc"] is not None
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type = 'cong_no.da_thu'"
            " AND aggregate_id = $1::uuid",
            r["id"],
        )
        == 1
    )
    async with pool.acquire() as conn:
        sau = await doc_khach_con_no(conn, CLINIC)
    assert r["id"] not in {x["id"] for x in sau["ds"]}


async def test_no_moi_sau_ghi_no_thi_chan_lai_huy_ghi_no_truoc_khi_ve(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit, order = await _luot_da_lam_chua_thu(pool)
    cn = CongNoService(pool)
    await cn.ghi(identity=ca.le_tan, visit_id=visit, ly_do="Khách quên ví")

    # Bác sĩ tick dịch vụ khám con SAU lần ghi nợ → khoản mới chưa ghi → chặn.
    gia = await pool.fetchval(
        'INSERT INTO service_price (clinic_id, service_code, name, "group",'
        " unit_price) VALUES ($1::uuid, $2, 'Khám phụ khoa thử', 'dich_vu',"
        " 200000) RETURNING id::text",
        CLINIC,
        f"PK-{order[:8]}",
    )
    await pool.execute(
        "INSERT INTO luot_phi_kham (clinic_id, visit_id, service_price_id)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid)",
        CLINIC,
        visit,
        gia,
    )
    ss = await _san_sang(pool, ca, visit)
    assert ss["no_khi_ve"]["tong"] == 500000
    assert ss["no_khi_ve"]["chan"] is True
    assert ss["no_khi_ve"]["ghi_no"]["phu_du"] is False
    with pytest.raises(ValidationError, match="còn nợ"):
        await _dong(pool, ca, visit)

    # Ghi nợ lại → cùng một dòng, số tiền mới.
    await cn.ghi(identity=ca.le_tan, visit_id=visit, ly_do="Khách quên ví, hẹn mai")
    rows = await pool.fetch(
        "SELECT so_tien, trang_thai FROM cong_no WHERE visit_id = $1::uuid", visit
    )
    assert [(int(x["so_tien"]), x["trang_thai"]) for x in rows] == [
        (500000, "CHUA_THU")
    ]

    # Huỷ ghi nợ (bấm nhầm) khi khách CHƯA về → lại bị chặn.
    with pytest.raises(ValidationError, match="lý do"):
        await cn.huy(identity=ca.le_tan, visit_id=visit, ly_do="")
    await cn.huy(identity=ca.le_tan, visit_id=visit, ly_do="Bấm nhầm, khách trả ngay")
    assert (
        await pool.fetchval(
            "SELECT trang_thai FROM cong_no WHERE visit_id = $1::uuid", visit
        )
        == "HUY"
    )
    assert (await _san_sang(pool, ca, visit))["no_khi_ve"]["chan"] is True


async def test_phi_kham_0d_chua_chon_va_khoan_khong_chon_lam_khong_tinh(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Loại khám đặt lịch 0đ, chưa chọn dịch vụ khám con: KHÔNG nợ. Chỉ định
    khách không chọn làm, hay đã chọn mà CHƯA làm: không tính."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)

    # Khách không chọn làm.
    await _chon(pool, ca, visit, [])
    ss = await _san_sang(pool, ca, visit)
    assert ss["no_khi_ve"]["dong"] == [] and ss["no_khi_ve"]["chan"] is False
    assert not any(b.get("chan") for b in ss["blockers"])

    # Lượt thứ hai: đã chọn nhưng chưa làm → không là nợ (việc dở vẫn vượt được).
    visit2 = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con2, order2 = await _kham_va_chi_dinh(pool, ca, visit2)
    await _chon(pool, ca, visit2, [order2])
    ss2 = await _san_sang(pool, ca, visit2)
    assert ss2["no_khi_ve"]["dong"] == []
    assert not any(b.get("chan") for b in ss2["blockers"])
    kq = await _dong(pool, ca, visit2, incomplete=True, incomplete_reason="Khách về")
    assert kq["ok"] is True
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM cong_no WHERE visit_id = $1::uuid", visit2
        )
        == 0
    )

    # Không còn khoản nào thì "Ghi nợ" từ chối.
    with pytest.raises(ValidationError, match="không còn khoản"):
        await CongNoService(pool).ghi(
            identity=ca.le_tan, visit_id=visit, ly_do="Thử ghi nợ"
        )
    kq = await _dong(pool, ca, visit)
    assert kq["ok"] is True
