"""NHÓM 5 — khối chỉnh dây (H1/H2/H4/H6/H7/H8 custom được), tự nhắc việc.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_day_noi_nhac_db.py

Tuyền chốt 23–24/09/2026: "Đường nối H1–H8 phải CUSTOM được (không khoá cứng)";
"check-out quá 1 giờ chỉ nhắc lễ tân"; "nhắc tái khám… hoặc tự tạo việc cho chính
mình để tự nhắc".
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.core.exceptions import SafetyGateError
from clinicai.events.catalogue import DichVuDaXong
from clinicai.events.consumers.hanh_trinh import HEN_CHECK_OUT, HEN_KET_QUA_DOI_TAC
from clinicai.events.emit import emit_event, nguoi
from clinicai.events.hen_gio import lam_mot_hen
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.day_noi_service import DayNoiService
from clinicai.services.nhac_viec_service import HEN_NHAC, NhacViecService, doc_nhac_luc
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _chon,
    _don,
    _dung,
    _kham_va_chi_dinh,
    _thu,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _ql(pool: asyncpg.Pool, loc: str) -> Any:  # noqa: F811
    async with pool.acquire() as conn:
        return await _nguoi(conn, loc, "MANAGEMENT")


async def _toi_han(pool: asyncpg.Pool, loai: str, ve: str) -> None:  # noqa: F811
    """Cho cái hẹn tới giờ ngay rồi chạy vòng xử lý hẹn."""
    await pool.execute(
        "UPDATE hen_gio SET den_gio = now() - interval '1 second'"
        " WHERE loai = $1 AND ve_cai_gi = $2::uuid AND trang_thai = 'CHO'",
        loai,
        ve,
    )
    while await lam_mot_hen(pool):
        pass


async def _chuong(pool: asyncpg.Pool, nguon_id: str) -> list[asyncpg.Record]:  # noqa: F811
    return list(
        await pool.fetch(
            "SELECT vai_nhan, nguoi_nhan_staff_id::text AS nguoi, tieu_de"
            " FROM thong_bao WHERE nguon_id = $1",
            nguon_id,
        )
    )


async def test_chi_nguoi_co_quyen_chinh_day(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    with pytest.raises(SafetyGateError):
        await DayNoiService(pool).doc(identity=ca.le_tan)
    ql = await _ql(pool, ca.loc)
    dl = await DayNoiService(pool).doc(identity=ql)
    assert {d["ma"] for d in dl["day"]} >= {
        "h4_tu_xep_phong",
        "h8_nhac_check_out_phut",
    }
    with pytest.raises(ValidationError):
        await DayNoiService(pool).dat_day(
            identity=ql, ma="h8_nhac_check_out_phut", gia_tri=9999
        )
    with pytest.raises(ValidationError):
        await DayNoiService(pool).dat_day(identity=ql, ma="h4_tu_xep_phong", gia_tri=1)
    with pytest.raises(ValidationError):
        await DayNoiService(pool).dat_loai_kham(
            identity=ql,
            service_type_id=ca.loai_kham,
            qua_tu_van=True,
            di_thang_phong=True,
        )
    with pytest.raises(ValidationError):
        await DayNoiService(pool).dat_chuong(
            identity=ql,
            su_kien="result_file.uploaded",
            vai=["KHONG_CO"],
            bac_si_chinh=True,
            bat=True,
        )


async def test_tat_h4_thi_thu_tien_xong_khong_tu_xep(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    ql = await _ql(pool, ca.loc)
    await DayNoiService(pool).dat_day(identity=ql, ma="h4_tu_xep_phong", gia_tri=False)
    try:
        visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
        _con, order = await _kham_va_chi_dinh(pool, ca, visit)
        await _chon(pool, ca, visit, [order])
        await _thu(pool, visit, ca.le_tan)
        await chay_hanh_trinh(pool)
        assert (await _don(pool, order))["routing_status"] == "UNASSIGNED"
    finally:
        await DayNoiService(pool).dat_day(
            identity=ql, ma="h4_tu_xep_phong", gia_tri=True
        )


async def test_bat_qua_tu_van_cho_mot_loai_kham(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    ql = await _ql(pool, ca.loc)
    await DayNoiService(pool).dat_loai_kham(
        identity=ql, service_type_id=ca.loai_kham, qua_tu_van=True
    )
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    assert (
        await pool.fetchval(
            "SELECT route_decision FROM encounter_flow WHERE visit_id = $1::uuid",
            visit,
        )
        == "TU_VAN"
    )


async def test_h8_tra_tien_qua_han_chua_check_out_thi_nhac_le_tan(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM hen_gio WHERE loai = $1 AND ve_cai_gi = $2::uuid",
            HEN_CHECK_OUT,
            visit,
        )
        == 1
    )
    await _toi_han(pool, HEN_CHECK_OUT, visit)
    [c] = await _chuong(pool, f"check_out:{visit}")
    assert c["vai_nhan"] == "RECEPTION" and "chưa check-out" in c["tieu_de"]


async def test_h8_da_check_out_thi_khong_nhac_va_h6_bao_cskh_con_viec(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.thu_ngan)  # không tự xếp → dịch vụ còn chưa làm
    await chay_hanh_trinh(pool)
    await CheckoutService(pool).close(
        identity=ca.le_tan, visit_id=visit, override_reason="khách về"
    )
    await chay_hanh_trinh(pool)
    await _toi_han(pool, HEN_CHECK_OUT, visit)
    assert await _chuong(pool, f"check_out:{visit}") == []  # đã về: không nhắc
    [c] = await _chuong(pool, f"ve_con_viec:{visit}")
    assert c["vai_nhan"] == "CSKH" and "còn việc dở" in c["tieu_de"]


async def test_h7_ket_qua_doi_tac_qua_han_bao_cskh(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await pool.fetchval(
        "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
        " AND kind = 'PRIMARY'",
        visit,
    )
    order = await pool.fetchval(
        "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
        " service_code, service_name, node_code, exec_status, recorded_by,"
        " authorized_by, authorized_at, selection_status, routing_status)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, 'Xét nghiệm gửi ngoài',"
        " 'DICHVU-HINHANH-NGOAI', 'authorized', $5::uuid, $5::uuid, now(),"
        " 'SELECTED', 'UNASSIGNED') RETURNING id::text",
        CLINIC,
        visit,
        con,
        f"XN-{uuid.uuid4().hex[:6]}",
        ca.bac_si.staff_id,
    )
    async with pool.acquire() as conn, conn.transaction():
        await emit_event(
            conn,
            ten="service.completed",
            clinic_id=CLINIC,
            aggregate_id=order,
            so_ke_tiep=True,
            payload=DichVuDaXong(
                visit_id=visit,
                service_order_id=order,
                attempt_id=str(uuid.uuid4()),
                attempt_no=1,
                execution_revision=2,
            ),
            boi=nguoi(ca.dd),
            correlation_id=visit,
        )
    await chay_hanh_trinh(pool)
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM hen_gio WHERE loai = $1 AND ve_cai_gi = $2::uuid",
            HEN_KET_QUA_DOI_TAC,
            order,
        )
        == 1
    )
    await _toi_han(pool, HEN_KET_QUA_DOI_TAC, order)
    [c] = await _chuong(pool, f"qua_han:{order}")
    assert c["vai_nhan"] == "CSKH" and "chưa về" in c["tieu_de"]


def test_doc_nhac_luc_rac_thi_rong_khong_nem() -> None:
    rac_ca: list[object] = [
        None,
        "",
        "   ",
        "ngày mai",
        "2026-13-45T99:00",
        123,
        [],
        {},
    ]
    for rac in rac_ca:
        assert doc_nhac_luc(rac) is None
    v = doc_nhac_luc("2026-09-25T08:30")
    assert v is not None and v.tzinfo is not None


async def test_tu_nhac_toi_gio_thi_reo_dung_nguoi(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    svc = NhacViecService(pool)
    with pytest.raises(ValidationError):
        await svc.tao(identity=ca.le_tan, noi_dung="gọi khách", nhac_luc="mai nhé")
    kq = await svc.tao(
        identity=ca.le_tan,
        noi_dung="Gọi chị Lan hẹn tái khám",
        nhac_luc="2020-01-01T08:00",  # đã qua → tới hạn ngay
        clinic_patient_id=pid,
    )
    await _toi_han(pool, HEN_NHAC, kq["id"])
    [c] = await _chuong(pool, f"nhac:{kq['id']}")
    assert c["nguoi"] == ca.le_tan.staff_id and "Gọi chị Lan" in c["tieu_de"]
    ds = await svc.cua_toi(identity=ca.le_tan, clinic_patient_id=pid)
    assert [x["id"] for x in ds] == [kq["id"]]
    await svc.xong(identity=ca.le_tan, nhac_id=kq["id"])
    assert (await svc.cua_toi(identity=ca.le_tan, clinic_patient_id=pid))[0]["xong"]


async def test_vi_tri_truc_them_doi_ten_tat(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    ql = await _ql(pool, ca.loc)
    svc = DayNoiService(pool)
    kq = await svc.tao_vi_tri(
        identity=ql, ten="Siêu âm thử nhóm 5", nhom_nghe="DIEU_DUONG", room_id=ca.phong
    )
    await svc.sua_vi_tri(identity=ql, vi_tri_id=kq["id"], ten="Siêu âm 9")
    await svc.sua_vi_tri(identity=ql, vi_tri_id=kq["id"], is_active=False)
    r = await pool.fetchrow(
        "SELECT ten, is_active, room_id::text AS room_id FROM vi_tri_lam_viec"
        " WHERE id = $1::uuid",
        kq["id"],
    )
    assert (r["ten"], r["is_active"], r["room_id"]) == ("Siêu âm 9", False, ca.phong)
