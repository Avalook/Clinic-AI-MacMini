"""ĐỢT 3 — gói quầy / kho (27/09/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_quay_kho_dot3_db.py

C7  "Không xếp được phòng": chụp phim (đối tác làm trọn) → "Đối tác làm — không
    cần xếp phòng"; không phòng nào nhận → câu rõ + chuông quầy "chờ xếp phòng"
    (trước đây dây H4 bỏ qua IM LẶNG).
C9  Dây `h4_chi_ap_phong_du_kien`: bật thì H4 CHỈ áp phòng lễ tân đã chọn.
C8  Lượt tồn đọng từ hôm trước: màn Check-out và canh gác dùng CÙNG một câu.
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.services import canh_gac
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.day_noi_service import DayNoiService
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.luot_treo import dieu_kien_luot_treo
from clinicai.services.service_routing_service import (
    CAU_DOI_TAC_LAM,
    CAU_KHONG_CO_PHONG,
    GOI_Y_CO_PHONG,
    GOI_Y_DOI_TAC_LAM,
    GOI_Y_KHONG_CO_PHONG,
    ServiceRoutingService,
    cau_cho_xep_phong,
    da_tra_cho_vao_phong,
)
from clinicai.services.service_selection_service import cho_khach_quyet
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _chon,
    _don,
    _dung,
    _khoa,
    _thu,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


# ── dựng ─────────────────────────────────────────────────────────────────────


async def _phien(pool: asyncpg.Pool, ca: Ca, visit: str) -> str:  # noqa: F811
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


async def _dat(pool: asyncpg.Pool, ca: Ca, con: str, *ma: str) -> list[str]:  # noqa: F811
    kq = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=list(ma),
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    return [str(x) for x in kq["order_ids"]]


async def _vai(pool: asyncpg.Pool, ca: Ca, vai: str) -> StaffIdentity:  # noqa: F811
    async with pool.acquire() as conn:
        return await _nguoi(conn, ca.loc, vai)


async def _chuong_cho_xep(pool: asyncpg.Pool, order: str) -> list[asyncpg.Record]:  # noqa: F811
    return list(
        await pool.fetch(
            "SELECT vai_nhan, tieu_de, noi_dung, duong_dan FROM thong_bao"
            " WHERE nguon = 'hanh_trinh' AND nguon_id = $1 ORDER BY vai_nhan",
            f"cho_xep_phong:{order}",
        )
    )


async def _dich_vu_nut_rieng(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    *,
    nhan_khach: bool,
) -> tuple[str, str]:
    """Một bước dịch vụ RIÊNG của bài kiểm + một phòng làm bước ấy (đang nhận
    khách hay tạm ngừng) — để biết chắc tập phòng hợp lệ."""
    duoi = uuid.uuid4().hex[:8]
    node = f"DICHVU-THU-{duoi}".upper()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO node_definition (clinic_id, code, name, flow_group,"
            " workspace, actor_roles, priority, is_group) VALUES ($1::uuid, $2,"
            " $3, 'dich_vu', 'khu_dieu_duong', ARRAY['NURSE_ULTRASOUND'], 'P1',"
            " false)",
            CLINIC,
            node,
            f"Bước thử {duoi}",
        )
        await conn.execute(
            "INSERT INTO node_definition_version (clinic_id, node_definition_id,"
            " version, snapshot) SELECT clinic_id, id, current_version, '{}'::jsonb"
            " FROM node_definition WHERE clinic_id = $1::uuid AND code = $2",
            CLINIC,
            node,
        )
        phong = await conn.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
            " is_active, accepting, sort) VALUES ($1::uuid, $2::uuid, $3, $4, $5,"
            " true, $6, 999) RETURNING id::text",
            CLINIC,
            ca.loc,
            f"T3-{duoi}",
            f"Phòng thử đợt 3 {duoi}",
            node,
            nhan_khach,
        )
        await conn.execute(
            "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
            " VALUES ($1::uuid, $2::uuid, $3)",
            CLINIC,
            phong,
            node,
        )
        ma = f"T3DV-{duoi}"
        await conn.execute(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " unit_price, node_code) VALUES ($1::uuid, $2, $3, 'dich_vu', 120000, $4)",
            CLINIC,
            ma,
            f"Dịch vụ thử đợt 3 {duoi}",
            node,
        )
    return ma, str(phong)


async def _dich_vu_chup_phim(pool: asyncpg.Pool) -> str:  # noqa: F811
    """Dịch vụ bước DICHVU-HINHANH-NGOAI, cờ đối tác tự làm TẮT (như DB dựng
    mới) — "đối tác làm trọn" phải nhận ra nhờ bước không có phòng nội bộ."""
    ma = f"T3CP-{uuid.uuid4().hex[:8]}"
    await pool.execute(
        'INSERT INTO service_price (clinic_id, service_code, name, "group",'
        " unit_price, node_code, doi_tac_lay_mau) VALUES ($1::uuid, $2, $3,"
        " 'dich_vu', 500000, 'DICHVU-HINHANH-NGOAI', false)",
        CLINIC,
        ma,
        f"Chụp phim thử {ma}",
    )
    return ma


async def _dat_day(pool: asyncpg.Pool, ca: Ca, ma: str, gia_tri: Any) -> None:  # noqa: F811
    ql = await _vai(pool, ca, "MANAGEMENT")
    await DayNoiService(pool).dat_day(identity=ql, ma=ma, gia_tri=gia_tri)


# ── C7a: đối tác làm trọn ────────────────────────────────────────────────────


async def test_chup_phim_goi_y_bao_doi_tac_lam_khong_hien_o_chon_phong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    tc = await _vai(pool, ca, "TRUONG_CA")
    ma = await _dich_vu_chup_phim(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _phien(pool, ca, visit)
    [order] = await _dat(pool, ca, con, ma)

    # Quầy, TRƯỚC khi chốt: ô "Làm ở phòng" không có phòng nào để chọn.
    async with pool.acquire() as conn:
        cho = (await cho_khach_quyet(conn, CLINIC, [visit]))[visit]
    [cd] = [c for c in cho["chi_dinh"] if c["id"] == order]
    assert cd["phong_chon_duoc"] == []

    await _chon(pool, ca, visit, [order])
    g = await ServiceRoutingService(pool).recommend(order_id=order, identity=tc)
    assert g["trang_thai"] == GOI_Y_DOI_TAC_LAM
    assert g["cau"] == CAU_DOI_TAC_LAM
    assert g["candidates"] == []

    # Thu xong: không vào ô "Phòng làm dịch vụ (đã thu)", H4 không xếp, KHÔNG
    # réo "chờ xếp phòng" (không có gì để xếp).
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    assert (await _don(pool, order))["routing_status"] == "UNASSIGNED"
    assert await _chuong_cho_xep(pool, order) == []
    async with pool.acquire() as conn:
        da_tra = await da_tra_cho_vao_phong(conn, CLINIC, [visit])
    assert order not in {c["id"] for c in da_tra.get(visit, [])}

    # Lệnh xếp tay cũng nói đúng câu ấy, không phải "phòng không làm dịch vụ".
    with pytest.raises(Exception) as loi:
        await ServiceRoutingService(pool).assign(
            order_id=order,
            room_id=ca.phong,
            expected_routing_revision=0,
            reason_code="INITIAL_ASSIGNMENT",
            identity=tc,
            idempotency_key=_khoa(),
        )
    assert getattr(loi.value, "error_code", None) == "SERVICE_PARTNER_PERFORMED"


# ── C7b/c + C9: không phòng nào nhận ─────────────────────────────────────────


async def test_khong_phong_nao_nhan_thi_cau_ro_va_reo_quay_cho_xep(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    tc = await _vai(pool, ca, "TRUONG_CA")
    ma, _phong = await _dich_vu_nut_rieng(pool, ca, nhan_khach=False)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _phien(pool, ca, visit)
    [order] = await _dat(pool, ca, con, ma)
    await _chon(pool, ca, visit, [order])

    g = await ServiceRoutingService(pool).recommend(order_id=order, identity=tc)
    assert g["trang_thai"] == GOI_Y_KHONG_CO_PHONG
    assert g["cau"] == CAU_KHONG_CO_PHONG and g["candidates"] == []

    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    assert (await _don(pool, order))["routing_status"] == "UNASSIGNED"
    chuong = await _chuong_cho_xep(pool, order)
    assert [c["vai_nhan"] for c in chuong] == ["CASHIER", "RECEPTION"]
    assert all(c["duong_dan"] == "/thu-ngan/dich-vu" for c in chuong)
    assert chuong[0]["noi_dung"] == cau_cho_xep_phong("KHONG_CO_PHONG")
    assert "chờ xếp phòng" in chuong[0]["tieu_de"]

    # Chạy lại lệnh H4 (giao tin "ít nhất một lần") → không nhân đôi chuông.
    async with pool.acquire() as conn, conn.transaction():
        await ServiceRoutingService(pool=None).tu_xep_da_thu(
            conn,
            clinic_id=CLINIC,
            visit_id=visit,
            staff_id=ca.le_tan.staff_id,
            causation_id=str(uuid.uuid4()),
        )
    assert len(await _chuong_cho_xep(pool, order)) == 2


async def test_giu_dieu_phoi_bao_cau_tieng_viet_khong_ma_tho(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Chỉ định còn giữ (bác sĩ dặn làm sau vòng đọc) → câu có việc cần làm."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _phien(pool, ca, visit)
    [order] = await _dat(pool, ca, con, ca.ma_dv)
    await pool.execute(
        "UPDATE service_order SET hold_until_round = 99 WHERE id = $1::uuid", order
    )
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    # Có phòng làm được → màn bày ô chọn (không câu cảnh báo).
    tc = await _vai(pool, ca, "TRUONG_CA")
    g = await ServiceRoutingService(pool).recommend(order_id=order, identity=tc)
    assert g["trang_thai"] == GOI_Y_CO_PHONG and g["cau"] is None
    assert g["candidates"]
    d = await _don(pool, order)
    with pytest.raises(Exception) as loi:
        await ServiceRoutingService(pool).assign(
            order_id=order,
            room_id=ca.phong,
            expected_routing_revision=int(d["routing_revision"]),
            reason_code="INITIAL_ASSIGNMENT",
            identity=ca.le_tan,
            idempotency_key=_khoa(),
        )
    assert getattr(loi.value, "error_code", None) == "HELD_UNTIL_ROUND"
    cau = str(getattr(loi.value, "message", "") or loi.value)
    assert "HELD_UNTIL_ROUND" not in cau and "Việc cần làm" in cau


async def test_day_chi_ap_phong_du_kien_bat_tat(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    rs = ServiceRoutingService(pool)

    async def _luot_da_chon(phong_du_kien: str | None) -> str:
        visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
        con = await _phien(pool, ca, visit)
        [order] = await _dat(pool, ca, con, ca.ma_dv)
        await _chon(pool, ca, visit, [order])
        if phong_du_kien:
            await rs.dat_phong_du_kien(
                order_id=order, room_id=phong_du_kien, identity=ca.le_tan
            )
        return order

    await _dat_day(pool, ca, "h4_chi_ap_phong_du_kien", True)
    try:
        # BẬT + chưa chọn phòng → KHÔNG tự chọn phòng vắng nhất; réo quầy.
        o1 = await _luot_da_chon(None)
        await _thu(pool, (await _don(pool, o1))["visit_id"], ca.le_tan)
        await chay_hanh_trinh(pool)
        assert (await _don(pool, o1))["routing_status"] == "UNASSIGNED"
        [c1, _] = await _chuong_cho_xep(pool, o1)
        assert c1["noi_dung"] == cau_cho_xep_phong("CHUA_CHON_PHONG")

        # BẬT + đã chọn phòng → xếp đúng phòng ấy.
        o2 = await _luot_da_chon(ca.phong)
        await _thu(pool, (await _don(pool, o2))["visit_id"], ca.le_tan)
        await chay_hanh_trinh(pool)
        d2 = await _don(pool, o2)
        assert d2["routing_status"] == "ASSIGNED" and d2["room_id"] == ca.phong

        # BẬT + phòng đã chọn TẠM NGỪNG trước lúc thu → chờ lễ tân, không đẩy
        # khách sang phòng khác.
        o3 = await _luot_da_chon(ca.phong)
        await pool.execute(
            "UPDATE clinic_room SET accepting = false WHERE id = $1::uuid", ca.phong
        )
        try:
            await _thu(pool, (await _don(pool, o3))["visit_id"], ca.le_tan)
            await chay_hanh_trinh(pool)
        finally:
            await pool.execute(
                "UPDATE clinic_room SET accepting = true WHERE id = $1::uuid", ca.phong
            )
        assert (await _don(pool, o3))["routing_status"] == "UNASSIGNED"
        [c3, _] = await _chuong_cho_xep(pool, o3)
        assert c3["noi_dung"] == cau_cho_xep_phong("PHONG_DU_KIEN_KHONG_NHAN")
    finally:
        await _dat_day(pool, ca, "h4_chi_ap_phong_du_kien", False)

    # TẮT (mặc định) + chưa chọn phòng → tự xếp phòng vắng nhất như cũ.
    o4 = await _luot_da_chon(None)
    await _thu(pool, (await _don(pool, o4))["visit_id"], ca.le_tan)
    await chay_hanh_trinh(pool)
    assert (await _don(pool, o4))["routing_status"] == "ASSIGNED"
    assert await _chuong_cho_xep(pool, o4) == []


# ── C8: lượt tồn đọng từ hôm trước ───────────────────────────────────────────


async def _la_luot_treo(pool: asyncpg.Pool, visit: str) -> bool:  # noqa: F811
    return bool(
        await pool.fetchval(
            f"SELECT EXISTS (SELECT 1 FROM visit v WHERE v.visit_id = $1::uuid"
            f" AND {dieu_kien_luot_treo('v')})",
            visit,
        )
    )


async def test_luot_ton_dong_hom_qua_dong_incomplete_roi_danh_sach(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await pool.execute(
        "UPDATE visit SET status = 'IN_PROGRESS',"
        " checked_in_at = now() - interval '1 day' WHERE visit_id = $1::uuid",
        visit,
    )
    # Lượt hôm qua ĐÃ check-out (closed_at, status vẫn IN_PROGRESS) — không phải
    # tồn đọng. Trước đợt 3 màn Check-out vẫn liệt kê loại này.
    da_ve = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await pool.execute(
        "UPDATE visit SET status = 'IN_PROGRESS', closed_at = now(),"
        " checked_in_at = now() - interval '1 day' WHERE visit_id = $1::uuid",
        da_ve,
    )
    # Lượt check-in HÔM NAY không phải tồn đọng.
    hom_nay = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)

    ds = await CheckoutService(pool).stale_list(identity=ca.le_tan)
    ids = {r["visit_id"] for r in ds}
    assert visit in ids
    assert da_ve not in ids and hom_nay not in ids
    assert await _la_luot_treo(pool, visit)
    async with pool.acquire() as conn:
        truoc = (await canh_gac.do_so(conn))["luot_treo"]

    await CheckoutService(pool).close(
        identity=ca.le_tan,
        visit_id=visit,
        incomplete=True,
        incomplete_reason="Lượt treo từ hôm qua — khách đã về, lễ tân đóng",
    )
    ds = await CheckoutService(pool).stale_list(identity=ca.le_tan)
    assert visit not in {r["visit_id"] for r in ds}
    assert not await _la_luot_treo(pool, visit)
    async with pool.acquire() as conn:
        sau = (await canh_gac.do_so(conn))["luot_treo"]
    # Canh gác đếm đúng cùng câu → giảm đúng một; hết lượt treo thì lần chạy
    # sau đóng cảnh báo (danh_gia → co_chuyen False → _dong).
    assert sau == truoc - 1
    so = {
        "su_kien": {},
        "loi_moi_15p": 0,
        "lan_loi_15p": 0,
        "kieu_loi_5p": 0,
        "hang_cho_ma": 0,
        "luot_treo": 0,
    }
    [k] = [
        k
        for k in canh_gac.danh_gia({**so, "su_kien": await _su_kien_on(pool)})
        if k.ma == "LUOT_TREO"
    ]
    assert k.co_chuyen is False


async def _su_kien_on(pool: asyncpg.Pool) -> Any:  # noqa: F811
    from clinicai.api.v1.health import do_su_kien

    async with pool.acquire() as conn:
        return await do_su_kien(conn)
