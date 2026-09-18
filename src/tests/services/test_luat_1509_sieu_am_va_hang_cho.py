"""Test đơn vị: phiếu siêu âm nháp theo bác sĩ thực hiện + lần siêu âm mới,
và lễ tân kéo thứ tự hàng chờ đã check-in (15/09/2026)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import SafetyGateError
from clinicai.main import app
from tests.services.fake_sql import SqlConn, pool
from tests.services.test_luat_1509_thu_ky_va_dieu_phoi import BS1, KHACH, ME, VISIT, who

LUOT = ("SELECT clinic_patient_id FROM public.visit", {"clinic_patient_id": KHACH})
KY_LUC = datetime(2026, 9, 15, 9, tzinfo=timezone.utc)


async def _luu(p: SqlConn, role: ClinicRole) -> dict[str, Any]:
    from clinicai.services.ultrasound_board_service import UltrasoundBoardService

    return await UltrasoundBoardService(p).save_draft(
        identity=who(role),
        visit_id=VISIT,
        ultrasound_type="DAU_DO",
        findings={"tử cung": "bình thường"},
        impression="Ổn",
        gestational_age_weeks=None,
    )


@pytest.mark.asyncio
async def test_bac_si_sieu_am_luu_nhap_thanh_nguoi_thuc_hien() -> None:
    p = pool(LUOT, ("INSERT INTO public.ultrasound_record", "u-1"))
    assert (await _luu(p, ClinicRole.ULTRASOUND_DOCTOR))["ultrasound_id"] == "u-1"
    # Chạm vào ca chưa ai nhận → ghi mình là bác sĩ thực hiện.
    assert p.da_goi("AND assigned_to IS NULL")
    assert p.da_goi("INSERT INTO public.ultrasound_record")[0][3] == ME


@pytest.mark.asyncio
async def test_nguoi_nhap_ho_lay_bac_si_da_nhan_ca() -> None:
    p = pool(
        LUOT,
        ("SELECT assigned_to FROM public.work_item", BS1),
        ("INSERT INTO public.ultrasound_record", "u-2"),
    )
    await _luu(p, ClinicRole.TRUONG_CA)
    assert p.da_goi("INSERT INTO public.ultrasound_record")[0][3] == BS1


@pytest.mark.asyncio
async def test_sua_nhap_chua_ky_va_chan_phieu_da_ky() -> None:
    nhap = (
        "SELECT ultrasound_id, signed_at",
        {"ultrasound_id": "u-3", "signed_at": None},
    )
    p = pool(LUOT, nhap, ("UPDATE public.ultrasound_record", "u-3"))
    assert (await _luu(p, ClinicRole.ULTRASOUND_DOCTOR))["ultrasound_id"] == "u-3"

    da_ky = (
        "SELECT ultrasound_id, signed_at",
        {"ultrasound_id": "u-3", "signed_at": KY_LUC},
    )
    with pytest.raises(ValidationError, match="đính chính"):
        await _luu(
            pool(LUOT, da_ky, ("SELECT EXISTS", False)), ClinicRole.ULTRASOUND_DOCTOR
        )

    # Có việc siêu âm mới mở sau lúc ký → lần 2, phiếu mới.
    lan_2 = pool(
        LUOT,
        da_ky,
        ("SELECT EXISTS", True),
        ("INSERT INTO public.ultrasound_record", "u-4"),
    )
    assert (await _luu(lan_2, ClinicRole.ULTRASOUND_DOCTOR))["ultrasound_id"] == "u-4"

    with pytest.raises(ValidationError, match="Không tìm thấy"):
        await _luu(pool(), ClinicRole.ULTRASOUND_DOCTOR)


@pytest.mark.asyncio
async def test_thu_ky_chi_nhap_ho_khach_bac_si_minh() -> None:
    with pytest.raises(SafetyGateError):
        await _luu(pool(LUOT, ("FROM public.thu_ky_bac_si", [BS1])), ClinicRole.TKYK)


# ── Hàng chờ: kéo thứ tự ────────────────────────────────────────────────────

A1, A2, A3 = (f"c0000000-0000-4000-8000-00000000000{i}" for i in (1, 2, 3))


def _moc(*rows: tuple[str, float]) -> tuple[str, Any]:
    return (
        "AS moc",
        [{"appointment_id": a, "visit_id": f"v-{a[-1]}", "moc": m} for a, m in rows],
    )


@pytest.mark.asyncio
async def test_keo_giua_hai_nguoi_ghi_moc_va_nhat_ky() -> None:
    from clinicai.services.thu_tu_kham_service import ThuTuKhamService

    p = pool(_moc((A1, 1000.0), (A2, 2000.0), (A3, 3000.0)))
    out = await ThuTuKhamService(p).keo(
        identity=who(ClinicRole.RECEPTION),
        appointment_id=A3,
        sau_appointment_id=A1,
        truoc_appointment_id=A2,
    )
    assert out == {"ok": True, "visit_id": "v-3", "thu_tu_tay_ms": 1500.0}
    assert p.da_goi("SET thu_tu_tay_ms") and p.events()

    svc = ThuTuKhamService(pool(_moc((A1, 1000.0))))
    with pytest.raises(ValidationError, match="tải lại"):
        await svc.keo(
            identity=who(ClinicRole.RECEPTION),
            appointment_id=A1,
            sau_appointment_id=A2,
            truoc_appointment_id=None,
        )
    with pytest.raises(NotFoundError):
        await svc.keo(
            identity=who(ClinicRole.RECEPTION),
            appointment_id=A3,
            sau_appointment_id=None,
            truoc_appointment_id=A1,
        )
    with pytest.raises(ValidationError, match="chính mình"):
        await svc.keo(
            identity=who(ClinicRole.RECEPTION),
            appointment_id=A1,
            sau_appointment_id=A1,
            truoc_appointment_id=None,
        )
    with pytest.raises(SafetyGateError):
        await svc.keo(
            identity=who(ClinicRole.DOCTOR),
            appointment_id=A1,
            sau_appointment_id=None,
            truoc_appointment_id=A2,
        )


@pytest.fixture
def db() -> Iterator[list[SqlConn]]:
    holder: list[SqlConn] = [pool()]
    app.dependency_overrides[get_db_pool] = lambda: holder[0]
    yield holder
    app.dependency_overrides.clear()


def _lich(appt: str, phut: int, **kw: Any) -> dict[str, Any]:
    slot = datetime(2026, 9, 15, 2, tzinfo=timezone.utc)
    base = {
        "appointment_id": appt,
        "doctor_id": BS1,
        "slot_start": slot,
        "status": "CHECKED_IN",
        "queue_number": int(appt[-1]),
        "booking_channel": "ONLINE",
        "patient_name": f"Khách {appt[-1]}",
        "patient_code": f"BN{appt[-1]}",
        "doctor_name": "BS B",
        "service_name": "Khám",
        "visit_id": f"v-{appt[-1]}",
        "checked_in_at": slot + timedelta(minutes=phut),
        "thu_tu_tay_ms": None,
        "visit_status": "OPEN",
        "khach_uu_tien": False,
        "uu_tien_ly_do": None,
        "slot_minutes": 15,
    }
    base.update(kw)
    return base


def test_hang_cho_theo_gio_check_in_va_thu_tu_keo_tay(db: list[SqlConn]) -> None:
    app.dependency_overrides[get_current_identity] = lambda: who(ClinicRole.RECEPTION)
    c = TestClient(app)
    den_som = _lich(A1, 1)
    den_sau = _lich(A2, 5, khach_uu_tien=True, uu_tien_ly_do="Thai yếu")
    # Lễ tân kéo A3 (đến muộn nhất) lên đầu hàng.
    keo_len = _lich(
        A3, 9, thu_tu_tay_ms=den_som["checked_in_at"].timestamp() * 1000 - 60000
    )
    db[0] = pool(
        ("FROM appointment a JOIN patient p", [den_sau, keo_len, den_som]),
        ("FROM lab_result", []),
    )
    rows = c.get("/api/v1/queue?date=2026-09-15").json()["rows"]
    assert [r["id"] for r in rows] == [A3, A1, A2]
    assert rows[2]["uu_tien_ly_do"] == "Thai yếu" and rows[0]["visit_id"] == "v-3"

    db[0] = pool(_moc((A1, 1000.0), (A2, 2000.0)))
    r = c.post(
        "/api/v1/queue/keo", json={"appointment_id": A2, "truoc_appointment_id": A1}
    )
    # Thả lên đầu: đứng trước A1 đúng một khoảng đầu/cuối (1 giây).
    assert r.json()["thu_tu_tay_ms"] == 0.0


@pytest.mark.asyncio
async def test_nhan_ca_sieu_am_theo_vai() -> None:
    from clinicai.services.ultrasound_board_service import UltrasoundBoardService

    def svc(*rules: tuple[str, Any]) -> UltrasoundBoardService:
        return UltrasoundBoardService(pool(*rules))

    la_sa = ("SELECT EXISTS", True)
    doi = ("UPDATE public.work_item", VISIT)
    tu_nhan = await svc(la_sa, doi).nhan_ca(
        identity=who(ClinicRole.ULTRASOUND_DOCTOR), work_item_id="w", bac_si_id=BS1
    )
    assert tu_nhan["bac_si_id"] == ME  # bác sĩ SA bấm nhận → chính mình
    giao = await svc(la_sa, doi).nhan_ca(
        identity=who(ClinicRole.TRUONG_CA), work_item_id="w", bac_si_id=BS1
    )
    assert giao["bac_si_id"] == BS1
    with pytest.raises(ValidationError, match="Chọn bác sĩ"):
        await svc().nhan_ca(
            identity=who(ClinicRole.MANAGEMENT), work_item_id="w", bac_si_id=None
        )
    with pytest.raises(SafetyGateError):
        await svc().nhan_ca(
            identity=who(ClinicRole.TKYK), work_item_id="w", bac_si_id=BS1
        )
    with pytest.raises(ValidationError, match="không phải bác sĩ siêu âm"):
        await svc(("SELECT EXISTS", False)).nhan_ca(
            identity=who(ClinicRole.TRUONG_CA), work_item_id="w", bac_si_id=BS1
        )
    with pytest.raises(ValidationError, match="không còn chờ"):
        await svc(la_sa).nhan_ca(
            identity=who(ClinicRole.TRUONG_CA), work_item_id="w", bac_si_id=BS1
        )


def test_thu_ky_hoi_pham_vi_qua_backend(db: list[SqlConn]) -> None:
    c = TestClient(app)
    khac = "d0000000-0000-4000-8000-000000000009"
    db[0] = pool(
        ("FROM public.thu_ky_bac_si", [BS1]),
        ("SELECT s.id::text AS id, s.full_name", [{"id": BS1, "full_name": "BS B"}]),
        ("AS id FROM public.appointment a", [{"id": KHACH}, {"id": None}]),
    )
    app.dependency_overrides[get_current_identity] = lambda: who(ClinicRole.TKYK)
    assert c.get("/api/v1/thu-ky/pham-vi").json() == {
        "la_thu_ky": True,
        "bac_si": [{"id": BS1, "full_name": "BS B"}],
    }
    assert c.get("/api/v1/thu-ky/khach-duoc-xem").json() == {
        "gioi_han": True,
        "ids": [KHACH],
    }
    assert c.get(f"/api/v1/thu-ky/khach/{KHACH}").json() == {"ok": True}
    assert c.get(f"/api/v1/thu-ky/khach/{khac}").status_code == 403

    # Không phải thư ký: không giới hạn, xem được mọi khách.
    app.dependency_overrides[get_current_identity] = lambda: who(ClinicRole.DOCTOR)
    assert c.get("/api/v1/thu-ky/khach-duoc-xem").json() == {
        "gioi_han": False,
        "ids": [],
    }
    assert c.get("/api/v1/thu-ky/pham-vi").json()["la_thu_ky"] is False


@pytest.mark.asyncio
async def test_phieu_sieu_am_thu_ky_chi_thay_khach_bac_si_minh() -> None:
    from clinicai.services.ultrasound_board_service import UltrasoundBoardService

    phieu: dict[str, object] = {
        "ultrasound_id": "u-1",
        "visit_id": VISIT,
        "appointment_id": None,
        "clinic_patient_id": KHACH,
        "patient_name": "K",
        "patient_code": "BN",
        "gender": "F",
        "birth_year": 1990,
        "ultrasound_type": "DAU_DO",
        "findings": {},
        "impression": None,
        "image_refs": None,
        "gestational_age_weeks": None,
        "performed_at": KY_LUC,
        "performed_by_name": "BS B",
        "signed_at": None,
        "signed_by_name": None,
        "room_name": None,
        "room_floor": None,
        "updated_at": None,
    }
    p = pool(
        ("FROM public.thu_ky_bac_si", [BS1]),
        ("AS id FROM public.appointment a", [{"id": KHACH}]),
        ("FROM public.ultrasound_record u", [phieu]),
    )
    out = await UltrasoundBoardService(p).records(
        identity=who(ClinicRole.TKYK), signed=False, days=7
    )
    assert out["items"][0]["image_refs"] == [] and out["items"][0]["visit_id"] == VISIT
    assert p.da_goi("FROM public.ultrasound_record u")[0][3] == [KHACH]
