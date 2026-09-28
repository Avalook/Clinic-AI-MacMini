"""Nợ còn lại sau nhóm 1–6 (24/09/2026): phiếu kết quả xem được + tự ghi đã xem,
xét nghiệm nhập tay qua sự kiện, hẹn giờ hỏng hẳn réo người trực, quyền theo màn.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_no_con_lai_db.py
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.core.exceptions import SafetyGateError
from clinicai.events.catalogue import CHUONG
from clinicai.events.hen_gio import dang_ky_loai, hen, lam_mot_hen
from clinicai.permissions.catalogue import (
    MAN,
    khoi_sau_khi_doi_man,
    man_dang_bat,
)
from clinicai.services.form_engine_service import FormEngineService
from clinicai.services.lab_order_service import LabOrderService
from clinicai.services.permission_service import PermissionService
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_form_engine_db import (
    _don_co_mau,
    pool,  # noqa: F401
)
from tests.services.test_form_engine_db import _nguoi as _nguoi_form
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

CLINIC = "a0000000-0000-4000-8000-000000000001"


# ── Phiếu kết quả: bác sĩ chính đọc được, mở là tự ghi đã xem ──────────────


async def test_bac_si_doc_phieu_ket_qua_va_tu_ghi_da_xem(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi_form(conn, "DOCTOR")
        le_tan = await _nguoi_form(conn, "RECEPTION")
        order_id, vid = await _don_co_mau(conn, bs, mode="INLINE")
    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=order_id, form_id="KQ_SA_VU", identity=bs
    )
    await svc.hoan_tat(
        phieu_id=phieu["id"], expected_revision=phieu["revision"], identity=bs
    )
    with pytest.raises(SafetyGateError):
        await svc.xem_ket_qua(service_order_id=order_id, identity=le_tan)
    kq = await svc.xem_ket_qua(service_order_id=order_id, identity=bs)
    assert [p["form_id"] for p in kq["phieu"]] == ["KQ_SA_VU"]
    assert kq["phieu"][0]["khung"]
    await svc.xem_ket_qua(service_order_id=order_id, identity=bs)  # lần 2
    r = await pool.fetchrow(
        "SELECT da_xem_ket_qua_luc, da_xem_ket_qua_boi::text AS ai"
        " FROM service_order WHERE id = $1::uuid",
        order_id,
    )
    assert r["da_xem_ket_qua_luc"] is not None and r["ai"] == bs.staff_id
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type = 'result.viewed'"
            " AND aggregate_id = $1::uuid",
            order_id,
        )
        == 1
    )
    assert vid


# ── Xét nghiệm nhập tay: qua sự kiện, không gọi chuông thẳng ────────────────


async def test_xet_nghiem_nhap_tay_ve_lan_dau_thi_reo_chuong_qua_su_kien(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    visit = await _check_in(pool, ca, pid, ca.loai_kham)
    appt = await pool.fetchval(
        "SELECT appointment_id::text FROM visit WHERE visit_id = $1::uuid", visit
    )
    lab = str(uuid.uuid4())
    await pool.execute(
        "INSERT INTO lab_result (lab_result_id, appointment_id, clinic_id,"
        " clinic_patient_id, visit_id, test_code, test_name) VALUES ($1::uuid,"
        " $2::uuid, $3::uuid, $4::uuid, $5::uuid, 'HIV', 'HIV test nhanh')",
        lab,
        appt,
        CLINIC,
        pid,
        visit,
    )
    svc = LabOrderService(pool)
    await svc.enter_result(
        lab_result_id=lab,
        result_value="Âm tính",
        result_link=None,
        lab_provider=None,
        identity=ca.dd,
    )
    # Sửa lại kết quả: KHÔNG phát lần hai.
    await svc.enter_result(
        lab_result_id=lab,
        result_value="Âm tính (sửa chính tả)",
        result_link=None,
        lab_provider=None,
        identity=ca.dd,
    )
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type ="
            " 'lab_result.arrived' AND aggregate_id = $1::uuid",
            lab,
        )
        == 1
    )
    nguon = f"lab_result.arrived:{lab}"
    assert (
        await pool.fetchval("SELECT count(*) FROM thong_bao WHERE nguon_id = $1", nguon)
        == 0
    )  # chưa chạy khối Chuông: lệnh không gọi thẳng
    await chay_ben_nhan(pool, CHUONG)
    rows = await pool.fetch(
        "SELECT vai_nhan, nguoi_nhan_staff_id::text AS nguoi FROM thong_bao"
        " WHERE nguon_id = $1",
        nguon,
    )
    assert {r["vai_nhan"] for r in rows if r["vai_nhan"]} == {"CSKH"}
    assert [r["nguoi"] for r in rows if r["nguoi"]] == [ca.bac_si.staff_id]


# ── Hẹn giờ hỏng hẳn → réo người trực ──────────────────────────────────────


async def test_hen_gio_hong_han_thi_reo_truong_ca_va_quan_ly(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: Any,
) -> None:
    import clinicai.events.hen_gio as hg

    loai = f"thu.hong_{uuid.uuid4().hex[:6]}"

    async def hong(conn: asyncpg.Connection, cai_hen: Any) -> bool:
        raise RuntimeError("hỏng thử")

    dang_ky_loai(loai, hong)
    monkeypatch.setattr(hg, "SO_LAN_THU_TOI_DA", 1)
    ca = await _dung(pool)
    async with pool.acquire() as conn, conn.transaction():
        ma = await hen(
            conn,
            clinic_id=CLINIC,
            loai=loai,
            sau=__import__("datetime").timedelta(0),
            chi_tiet={"nguoi_goi": ca.le_tan.staff_id},
        )
    while await lam_mot_hen(pool):
        pass
    assert (
        await pool.fetchval("SELECT trang_thai FROM hen_gio WHERE id = $1::uuid", ma)
        == "CHET"
    )
    vai = {
        r["vai_nhan"]
        for r in await pool.fetch(
            "SELECT vai_nhan FROM thong_bao WHERE nguon = 'hen_gio_hong'"
            " AND nguon_id = $1",
            ma,
        )
    }
    assert vai == {"TRUONG_CA", "MANAGEMENT"}


# ── Quyền theo màn ──────────────────────────────────────────────────────────


async def test_tat_man_khong_lay_mat_khoi_man_khac_con_can() -> None:
    bac_si = [
        "kham",
        "chi_dinh",
        "ghi_benh_an",
        "hoan_tat_kham",
        "thuc_hien",
        "ket_qua",
        "duyet_ket_qua",  # 28/09: thuộc cả Bàn khám lẫn Phòng dịch vụ
    ]
    assert set(man_dang_bat(bac_si)) >= {"ban_kham", "phong"}
    # Tắt lego "Phòng dịch vụ": gỡ thuc_hien; ket_qua + ghi_benh_an Bàn khám còn
    # cần nên GIỮ (lego 25/09/2026: một khối nằm được trong nhiều lego).
    sau = khoi_sau_khi_doi_man(bac_si, "phong", False)
    assert "ban_kham" in man_dang_bat(sau) and "phong" not in man_dang_bat(sau)
    assert {"ket_qua", "ghi_benh_an"} <= set(sau) and "thuc_hien" not in sau
    # Bật "Thu tiền dịch vụ": thêm đủ hai khối của màn ấy.
    assert set(MAN["thu_tien_dv"].khoi) <= set(
        khoi_sau_khi_doi_man(bac_si, "thu_tien_dv", True)
    )


async def test_quan_ly_bat_man_cho_nhom(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        ql = await _nguoi_form(conn, "MANAGEMENT")
        le_tan = await _nguoi_form(conn, "RECEPTION")
    svc = PermissionService(pool)
    with pytest.raises(SafetyGateError):
        await svc.doi_man(
            ma_nhom="RECEPTION", ma_man="do_sinh_hieu", bat=True, identity=le_tan
        )
    kq = await svc.doi_man(
        ma_nhom="RECEPTION", ma_man="do_sinh_hieu", bat=True, identity=ql
    )
    try:
        assert "do_sinh_hieu" in kq["man_bat"]
        man = await svc.theo_man(identity=ql)
        [nhom] = [n for n in man["nhom"] if n["ma"] == "RECEPTION"]
        assert "do_sinh_hieu" in nhom["man_bat"]
    finally:
        await svc.doi_man(
            ma_nhom="RECEPTION", ma_man="do_sinh_hieu", bat=False, identity=ql
        )
