"""Xem lại lượt khám — một nguồn đọc, cắt theo vai (batch pilot 18/09/2026)."""

from __future__ import annotations

import uuid

import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.xem_luot_service import XemLuotService, muc_duoc_xem
from tests.services.test_luot_kham_service_db import KichBan, _vao_kham
from tests.services.test_slice1_rail_db import _chi_dinh, _lam

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _ai(vai: ClinicRole, kb: KichBan) -> StaffIdentity:
    return StaffIdentity(
        staff_id=str(uuid.uuid4()),
        auth_user_id=str(uuid.uuid4()),
        full_name="Thu ngân test",
        department=vai.value,
        role=vai,
        clinic_id=kb.bac_si.clinic_id,
        location_id=kb.location_id,
        location_name="x",
    )


def test_muc_theo_vai() -> None:
    def muc(vai: ClinicRole) -> dict[str, bool]:
        return muc_duoc_xem(
            StaffIdentity(
                staff_id="s",
                auth_user_id="a",
                full_name="x",
                department=vai.value,
                role=vai,
                clinic_id="c",
                location_id="l",
                location_name="x",
            )
        )

    assert muc(ClinicRole.NURSE_ULTRASOUND)["sinh_hieu"]
    assert not muc(ClinicRole.NURSE_ULTRASOUND)["lam_sang"]
    assert not muc(ClinicRole.RECEPTION)["sinh_hieu"]
    assert muc(ClinicRole.RECEPTION)["tai_chinh"]
    assert not muc(ClinicRole.TRUONG_CA)["lam_sang"]
    assert (
        muc(ClinicRole.CASHIER)["tai_chinh"] and not muc(ClinicRole.CASHIER)["lam_sang"]
    )
    assert muc(ClinicRole.PHARMACIST)["thuoc"]


async def test_moi_vai_thay_dung_muc(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    [sa] = await _chi_dinh(kb, phien, kb.ma_sa)
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    await _lam(kb, sa, sa=True, result_note="Tử cung bình thường.")
    svc = XemLuotService(kb.pool)

    bs = await svc.doc(visit_id=kb.visit_id, identity=kb.bac_si)
    assert bs["sinh_hieu"]["luot_nay"][0]["tam_thu"] == 118
    assert bs["lam_sang"]["phien"][0]["loai"] == "PRIMARY"
    [dv] = bs["dich_vu"]
    assert dv["ket_qua_ghi"] == "Tử cung bình thường."
    viec = [m["viec"] for m in dv["moc"]]
    assert viec[:2] == ["Ghi chỉ định", "Bác sĩ duyệt chỉ định"] and "Xong" in viec

    tc = await svc.doc(visit_id=kb.visit_id, identity=kb.truong_ca)
    assert "lam_sang" not in tc and "sinh_hieu" not in tc
    assert tc["dich_vu"][0]["ket_qua_ghi"] is None  # thấy mốc, không thấy chữ
    assert tc["dich_vu"][0]["moc"]

    dd = await svc.doc(visit_id=kb.visit_id, identity=kb.dieu_duong)
    assert "sinh_hieu" in dd and "lam_sang" not in dd

    lt = await svc.doc(visit_id=kb.visit_id, identity=kb.le_tan)
    assert lt["hanh_chinh"]["da_do_sinh_hieu"] is True
    assert "tai_chinh" in lt and "lam_sang" not in lt

    tn = await svc.doc(visit_id=kb.visit_id, identity=_ai(ClinicRole.CASHIER, kb))
    assert tn["tai_chinh"] == [] and "lam_sang" not in tn

    # Thư ký chưa được phân bác sĩ này → bị chặn.
    with pytest.raises(SafetyGateError):
        await svc.doc(visit_id=kb.visit_id, identity=kb.thu_ky)
    await kb.pool.execute(
        "INSERT INTO thu_ky_bac_si (clinic_id, thu_ky_staff_id, bac_si_staff_id)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid)",
        kb.bac_si.clinic_id,
        kb.thu_ky.staff_id,
        kb.bac_si.staff_id,
    )
    tk = await svc.doc(visit_id=kb.visit_id, identity=kb.thu_ky)
    assert "lam_sang" in tk


async def test_truong_ca_thay_chi_dinh_theo_nhom(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    mau, sa = await _chi_dinh(kb, phien, kb.ma_mau, kb.ma_sa)
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    await _lam(kb, sa, sa=True)
    kq = await kb.svc.chi_dinh_hom_nay(identity=kb.truong_ca)
    cua = {c["id"]: c for c in kq["chi_dinh"]}
    assert cua[sa]["nhom"] == "da_hoan_tat" and cua[sa]["xong_luc"]
    assert cua[mau]["nhom"] in {"can_dieu_phoi", "da_dieu_phoi"}
    assert cua[mau]["can"] == "VALID_RESULT"
    with pytest.raises(SafetyGateError):
        await kb.svc.chi_dinh_hom_nay(identity=kb.bac_si)


def test_khoang_ngay_rac_ve_mac_dinh_khong_nem() -> None:
    from datetime import date, datetime

    from clinicai.core.clock import CLINIC_TZ
    from clinicai.services.cashier_board_service import doc_khoang_ngay

    hom_nay = datetime.now(CLINIC_TZ).date()
    for rac in (None, "", "abc", "2026-13-40", 7):
        assert doc_khoang_ngay(rac, rac) == (hom_nay, hom_nay)
    assert doc_khoang_ngay("2026-09-18", "2026-09-01") == (
        date(2026, 9, 1),
        date(2026, 9, 18),
    )
    a, b = doc_khoang_ngay("2025-01-01", "2026-09-18")
    assert (b - a).days == 92


async def test_thu_ngan_xem_giao_dich_ca_dong_da_huy(kb: KichBan) -> None:
    from clinicai.services.cashier_board_service import CashierBoardService

    khach = await kb.pool.fetchval(
        "SELECT clinic_patient_id FROM visit WHERE visit_id = $1::uuid", kb.visit_id
    )
    await kb.pool.execute(
        "INSERT INTO payment (clinic_id, visit_id, clinic_patient_id, kind, status,"
        " amount, paid_at, voided_at, voided_by_staff_id, void_reason)"
        " VALUES ($1::uuid, $2::uuid, $3, 'dich_vu', 'VOIDED', 150000, now(), now(),"
        " $4::uuid, 'Thu nhầm')",
        kb.bac_si.clinic_id,
        kb.visit_id,
        khach,
        kb.le_tan.staff_id,
    )
    kq = await CashierBoardService(kb.pool).giao_dich(
        identity=_ai(ClinicRole.CASHIER, kb), tu=None, den=None
    )
    [gd] = [g for g in kq["giao_dich"] if g["visit_id"] == kb.visit_id]
    assert gd["so_tien"] == 150000 and gd["ly_do_huy"] == "Thu nhầm"
    assert gd["phuong_thuc"] is None


async def test_lich_tiep_theo_khong_tinh_lich_da_check_in(kb: KichBan) -> None:
    """Smoke 18/09: lịch hôm nay vừa check-in hiện thành "lịch tiếp theo"."""
    r = await kb.pool.fetchrow(
        "SELECT clinic_patient_id, location_id FROM patient WHERE clinic_patient_id ="
        " (SELECT clinic_patient_id FROM visit WHERE visit_id = $1::uuid)",
        kb.visit_id,
    )
    assert r is not None
    st = await kb.pool.fetchval(
        "SELECT id FROM service_type WHERE clinic_id = $1::uuid LIMIT 1",
        kb.bac_si.clinic_id,
    )

    async def hen(gio: int, trang_thai: str) -> None:
        await kb.pool.execute(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, slot_start, slot_end, status, booking_channel)"
            " VALUES ($1::uuid, $2, $3, $4, now() + make_interval(hours => $5),"
            " now() + make_interval(hours => $5, mins => 15), $6, 'PHONE')",
            kb.bac_si.clinic_id,
            r["clinic_patient_id"],
            r["location_id"],
            st,
            gio,
            trang_thai,
        )

    await hen(1, "CHECKED_IN")
    svc = XemLuotService(kb.pool)
    kq = await svc.doc(visit_id=kb.visit_id, identity=kb.le_tan)
    assert kq["hanh_chinh"]["lich_tiep_theo"] is None
    await hen(48, "CONFIRMED")
    kq = await svc.doc(visit_id=kb.visit_id, identity=kb.le_tan)
    assert kq["hanh_chinh"]["lich_tiep_theo"] is not None
