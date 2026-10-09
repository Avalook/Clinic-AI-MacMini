"""Sửa lỗi review đợt 07/10/2026 — nhánh LÀM TẠI BÀN KHÁM + đổi dịch vụ trong hồ
sơ, trên Postgres thật. Mỗi bài tái hiện đúng một lỗi review (số trong tên).

    scripts/test-nhanh.sh src/tests/services/test_review_0710_ban_kham_db.py
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import ConflictError
from clinicai.events.catalogue import DIEU_TRI_SINH_CHI_DINH, TRACH_NHIEM_DICH_VU
from clinicai.services import dieu_tri_ban_kham, ho_so_dich_vu
from clinicai.services import nhan_tai_phong as ntp
from clinicai.services.bill_service import hoa_don_con_no
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.service_execution_service import ServiceExecutionService
from clinicai.services.service_routing_service import ServiceRoutingService
from tests.chay_nguoi_dua_tin import chay_ben_nhan, chay_het
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_dieu_tri_ban_kham_db import (
    _bam,
    _ke,
    _laser,
    _lich_ban_kham,
    _the,
    _vao_kham,
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
)
from tests.services.test_thu_truoc_lam_truoc_tick_db import day_thu_truoc

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture(autouse=True)
async def _chua_thu_lam_duoc(pool: asyncpg.Pool) -> AsyncIterator[None]:  # noqa: F811
    # Dây "thu trước khi làm" TẮT: lượt nào cũng làm trước, thu sau — đúng
    # trường hợp [Làm tại bàn khám] phải tự chốt lựa chọn của khách (lỗi 1).
    async with day_thu_truoc(pool, False):
        yield


async def _sel(pool: asyncpg.Pool, order: str) -> str:  # noqa: F811
    return str(
        await pool.fetchval(
            "SELECT selection_status FROM service_order WHERE id = $1::uuid", order
        )
    )


async def _luot_ban_kham(
    pool: asyncpg.Pool,  # noqa: F811
) -> tuple[Ca, asyncpg.Record, str, str, str]:
    """Lượt khám thường, bác sĩ đang khám, đã kê Laser (điều trị)."""
    ca = await _dung(pool)
    laser = await _laser(pool)
    await _lich_ban_kham(pool, ca)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _vao_kham(pool, ca, visit)
    order = (await _ke(pool, ca, con, laser["ma"]))["order_ids"][0]
    return ca, laser, visit, con, order


async def _check_out(pool: asyncpg.Pool, ca: Ca, visit: str) -> None:  # noqa: F811
    await CheckoutService(pool).close(
        identity=ca.le_tan, visit_id=visit, override_reason="Khách cần về gấp"
    )


# ── Lỗi 1: chốt hộ đúng MỘT chỉ định, hoàn tác trả lại ─────────────────────────


async def test_1_lam_tai_ban_kham_chi_chot_dung_chi_dinh_hoan_tac_tra_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, _laser_dv, visit, con, o_laser = await _luot_ban_kham(pool)
    o_sa = (await _ke(pool, ca, con, ca.ma_dv))["order_ids"][0]  # CLS chưa chốt
    assert (await _sel(pool, o_laser), await _sel(pool, o_sa)) == ("PENDING", "PENDING")

    t = await _the(pool, ca, visit)
    assert t["lam_duoc"] is True
    await _bam(pool, ca, visit, t, "lam")
    # Chỉ chỉ định bác sĩ đang làm thành "khách làm"; CLS khách chưa đồng ý
    # vẫn chờ khách quyết → quầy KHÔNG có dòng nợ của nó.
    assert await _sel(pool, o_laser) == "SELECTED"
    assert await _sel(pool, o_sa) == "PENDING"
    async with pool.acquire() as conn:
        hd = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)
    assert o_sa not in [d.source_id for d in hd.dong]
    [bd] = await _su_kien(pool, "service.started", o_laser)
    assert json.loads(bd["payload"])["chot_lua_chon"] is True

    # Hoàn tác Làm tại bàn khám → lựa chọn về đúng như trước khi bấm.
    await _bam(pool, ca, visit, await _the(pool, ca, visit), "huy-lam")
    assert await _sel(pool, o_laser) == "PENDING"
    [huy] = await _su_kien(pool, "service.start_cancelled", o_laser)
    assert json.loads(huy["payload"])["tra_lua_chon_ve"] == "PENDING"

    # Làm lại; quầy chốt lượt SAU đó → hoàn tác không đè lựa chọn người sau.
    await _bam(pool, ca, visit, await _the(pool, ca, visit), "lam")
    await _chon(pool, ca, visit, [o_sa])
    await _bam(pool, ca, visit, await _the(pool, ca, visit), "huy-lam")
    assert await _sel(pool, o_laser) == "SELECTED"
    assert await _sel(pool, o_sa) == "SELECTED"
    huy2 = (await _su_kien(pool, "service.start_cancelled", o_laser))[-1]
    assert json.loads(huy2["payload"])["tra_lua_chon_ve"] is None


# ── Lỗi 2: sau check-out không đổi dịch vụ / không xếp lại / không sinh chỉ định ─


async def test_2_doi_dich_vu_trong_ho_so_sau_check_out_bi_tu_choi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    laser = await _laser(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _vao_kham(pool, ca, visit)
    await LuotKhamService(pool).kham_xong(
        consultation_id=con, identity=ca.bac_si, idempotency_key=_khoa()
    )
    await _check_out(pool, ca, visit)
    goi = await ho_so_dich_vu.doc(pool, identity=ca.bac_si, visit_id=visit)
    assert goi["doi_duoc"] is False
    assert goi["ly_do_khong_doi"] == "Lượt đã check-out — mở lại lượt trước."
    with pytest.raises(ConflictError):
        await ho_so_dich_vu.doi(
            pool, identity=ca.bac_si, visit_id=visit, service_type_id=laser["loai"]
        )
    assert (
        await pool.fetchval(
            "SELECT service_type_id::text FROM visit WHERE visit_id = $1::uuid", visit
        )
        == ca.loai_kham
    )


async def test_2_xep_lai_sau_doi_dich_vu_bo_qua_luot_da_check_out(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Sự kiện đổi dịch vụ tới SAU check-out (giao sau commit) → không đưa khách
    đã về lại hàng tư vấn / bác sĩ."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await _check_out(pool, ca, visit)
    truoc = await pool.fetchval(
        "SELECT count(*) FROM queue_entry WHERE visit_id = $1::uuid", visit
    )
    async with pool.acquire() as conn, conn.transaction():
        kq = await LuotKhamService(pool).xep_lai_sau_doi_dich_vu(
            conn, clinic_id=CLINIC, visit_id=visit
        )
    assert kq is None
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM queue_entry WHERE visit_id = $1::uuid", visit
        )
        == truoc
    )


async def test_2_khong_sinh_chi_dinh_dieu_tri_cho_luot_da_check_out(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    laser = await _laser(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), laser["loai"])
    await _check_out(pool, ca, visit)
    async with pool.acquire() as conn, conn.transaction():
        kq = await ho_so_dich_vu.sinh_chi_dinh_dieu_tri(
            conn, clinic_id=CLINIC, visit_id=visit, nguoi_bam=None
        )
    assert kq is None
    await chay_het(pool, DIEU_TRI_SINH_CHI_DINH)
    assert not await pool.fetchval(
        "SELECT count(*) FROM service_order WHERE visit_id = $1::uuid", visit
    )


# ── Lỗi 5: phòng đã Nhận rồi bác sĩ Làm tại bàn khám ──────────────────────────


async def _xep_phong(pool: asyncpg.Pool, ca: Ca, order: str) -> str:  # noqa: F811
    """Phòng X làm được bước của chỉ định; quầy xếp chỉ định vào X."""
    node = await pool.fetchval(
        "SELECT node_code FROM service_order WHERE id = $1::uuid", order
    )
    async with pool.acquire() as conn:
        phong = await _phong(conn, ca.loc, uuid.uuid4().hex[:8])
        await conn.execute(
            "DELETE FROM clinic_room_node WHERE room_id = $1::uuid", phong
        )
        await conn.execute(
            "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
            " VALUES ($1::uuid, $2::uuid, $3) ON CONFLICT DO NOTHING",
            CLINIC,
            phong,
            node,
        )
    rev = await pool.fetchval(
        "SELECT routing_revision FROM service_order WHERE id = $1::uuid", order
    )
    await ServiceRoutingService(pool).assign(
        order_id=order,
        room_id=phong,
        expected_routing_revision=int(rev),
        reason_code="MANUAL_CORRECTION",
        identity=ca.thu_ngan,
        idempotency_key=_khoa(),
    )
    return str(phong)


async def test_5_phong_da_nhan_ban_kham_lam_phong_khong_xong_ho(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, _laser_dv, visit, _con, order = await _luot_ban_kham(pool)
    await _chon(pool, ca, visit, [order])
    phong_x = await _xep_phong(pool, ca, order)
    t = await _the(pool, ca, visit)
    bd = await _bam(pool, ca, visit, t, "lam")

    # Phòng X: chỉ định hiện "đang làm ở bàn khám BS …", không phải việc của X.
    async with pool.acquire() as conn:
        ds = await ntp.chi_dinh_cua_khach(conn, CLINIC, phong_x, [visit])
        dem = (await ntp.dem_theo_phong(conn, CLINIC, bat=False)).get(phong_x, {})
    [c] = [c for c in ds[visit] if c["id"] == order]
    assert c["trang_thai"] == ntp.PHONG_KHAC and c["o_trang_thai"] == ntp.LAM
    assert c["phong"].startswith("bàn khám") and c["nhan_duoc"] is False
    assert int(dem.get("dang_lam") or 0) == 0
    assert int(dem.get("dang_cho") or 0) == 0

    exe = ServiceExecutionService(pool)
    xem = await exe.xem(order_id=order, identity=ca.dd)
    assert xem["lan_dang_chay"] is None and xem["huy_bat_dau_duoc"] is False
    assert xem["lam_o_ban_kham"]["bac_si"]
    rev = int(xem["execution_revision"])
    for lenh in (
        exe.xong(
            order_id=order,
            attempt_id=bd["attempt_id"],
            expected_execution_revision=rev,
            identity=ca.dd,
            idempotency_key=_khoa(),
        ),
        exe.gian_doan(
            order_id=order,
            attempt_id=bd["attempt_id"],
            expected_execution_revision=rev,
            ly_do="EQUIPMENT_FAILURE",
            ghi_chu=None,
            identity=ca.dd,
            idempotency_key=_khoa(),
        ),
        exe.huy_bat_dau(
            order_id=order,
            attempt_id=bd["attempt_id"],
            expected_execution_revision=rev,
            identity=ca.dd,
        ),
    ):
        with pytest.raises(LuotKhamConflictError) as e:
            await lenh
        assert e.value.error_code == "DANG_LAM_BAN_KHAM"

    # Bàn khám Xong → chỗ của X đóng đúng.
    await _bam(pool, ca, visit, await _the(pool, ca, visit), "xong")
    assert not await pool.fetchval(
        "SELECT count(*) FROM queue_entry WHERE ref_id = $1::uuid"
        " AND status NOT IN ('done', 'left', 'cancelled')",
        order,
    )


# ── Lỗi 6: check-out chen giữa → lệnh bàn khám từ chối trong giao dịch ────────


async def test_6_lam_tai_ban_kham_tu_choi_khi_check_out_chen_giua(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, _laser_dv, visit, con, order = await _luot_ban_kham(pool)
    t = await _the(pool, ca, visit)
    await LuotKhamService(pool).kham_xong(
        consultation_id=con, identity=ca.bac_si, idempotency_key=_khoa()
    )
    # Check-out xảy ra SAU lần kiểm ngoài giao dịch của `thao_tac` — gọi thẳng
    # lệnh của module Thực hiện như lúc check-out chen giữa.
    await _check_out(pool, ca, visit)
    with pytest.raises(LuotKhamConflictError) as e:
        await ServiceExecutionService(pool).bat_dau_tai_ban_kham(
            order_id=order,
            expected_execution_revision=t["execution_revision"],
            identity=ca.bac_si,
        )
    assert e.value.error_code == "VISIT_CHECKED_OUT"
    assert str(e.value) == dieu_tri_ban_kham.CAU_LUOT_DA_DONG
    assert (
        await pool.fetchval(
            "SELECT coalesce(execution_status, 'PENDING') FROM service_order"
            " WHERE id = $1::uuid",
            order,
        )
        == "PENDING"
    )


# ── Lỗi 7: gán / gỡ phòng bàn khám có mốc trong sổ ───────────────────────────


async def test_7_gan_go_phong_ban_kham_co_moc_khong_de_viec(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, _laser_dv, visit, _con, order = await _luot_ban_kham(pool)
    await _bam(pool, ca, visit, await _the(pool, ca, visit), "lam")
    [xep] = await _su_kien(pool, "service.routed", order)
    p = json.loads(xep["payload"])
    assert p["nguon"] == "ban_kham" and p["room_id"]
    await _bam(pool, ca, visit, await _the(pool, ca, visit), "huy-lam")
    [go] = await _su_kien(pool, "service.routing_invalidated", order)
    assert json.loads(go["payload"])["ly_do"] == "HUY_LAM_TAI_BAN_KHAM"

    moc = await pool.fetch(
        "SELECT loai_moc, bi_hoan_tac FROM v_moc_hanh_trinh"
        " WHERE service_order_id = $1::uuid ORDER BY seq",
        order,
    )
    assert [(m["loai_moc"], m["bi_hoan_tac"]) for m in moc] == [
        ("XEP_PHONG", True),
        ("BAT_DAU", True),
        ("HUY_XEP_PHONG", False),
        ("HUY_BAT_DAU", False),
    ] or [(m["loai_moc"], m["bi_hoan_tac"]) for m in moc] == [
        ("XEP_PHONG", True),
        ("BAT_DAU", True),
        ("HUY_BAT_DAU", False),
        ("HUY_XEP_PHONG", False),
    ]
    # Gỡ phòng bàn khám không đẻ việc "xếp lại phòng" cho trưởng ca.
    await chay_ben_nhan(pool, TRACH_NHIEM_DICH_VU)
    assert not await pool.fetchval(
        "SELECT count(*) FROM work_item WHERE visit_id = $1::uuid"
        " AND node_code = 'OPS-ROUTING-REASSIGN'",
        visit,
    )
