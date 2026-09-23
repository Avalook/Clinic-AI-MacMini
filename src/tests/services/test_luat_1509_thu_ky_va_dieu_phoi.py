"""Test đơn vị cho các luật Tuyền chốt 15/09/2026 (thư ký theo bác sĩ, chuyển bác
sĩ giữa lượt, thứ tự khám kéo tay, báo kết quả về, nhận ca siêu âm, bỏ tích chỉ
định). Đường database thật đã có smoke Postgres; đây khoá nhánh Python để CI đo.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from tests.services.fake_sql import pool


@pytest.fixture(autouse=True)
def _cua_quyen_theo_nhom_mau(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kết nối giả không chạy được `v_quyen_hieu_luc` — cửa quyền trả lời theo
    nhóm mẫu của vai (tests/quyen_gia.py). 24/09: kéo thứ tự / đặt lịch hỏi quyền."""
    import clinicai.services.booking_service as bk
    import clinicai.services.thu_tu_kham_service as ttk
    from tests.quyen_gia import doi_quyen_theo_nhom_mau

    monkeypatch.setattr(ttk, "doi_quyen", doi_quyen_theo_nhom_mau)
    monkeypatch.setattr(bk, "doi_quyen", doi_quyen_theo_nhom_mau)


CLINIC = "a0000000-0000-4000-8000-000000000001"
ME = "b0000000-0000-4000-8000-000000000001"
BS1 = "b0000000-0000-4000-8000-000000000002"
BS2 = "b0000000-0000-4000-8000-000000000003"
KHACH = "d0000000-0000-4000-8000-000000000001"
VISIT = "e0000000-0000-4000-8000-000000000001"


def who(role: ClinicRole, staff: str = ME) -> StaffIdentity:
    return StaffIdentity(
        staff_id=staff,
        auth_user_id=staff,
        full_name="x",
        department=role.value,
        role=role,
        clinic_id=CLINIC,
        location_id=CLINIC,
        location_name="CS",
    )


# ── thu_ky_bac_si ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_khong_phai_thu_ky_thi_khong_loc() -> None:
    from clinicai.services.thu_ky_bac_si import (
        bac_si_cua_thu_ky,
        khach_duoc_xem,
        kiem_khach,
        pham_vi,
    )

    p = pool()
    assert await bac_si_cua_thu_ky(p, who(ClinicRole.DOCTOR)) is None
    assert await khach_duoc_xem(p, who(ClinicRole.DOCTOR)) is None
    await kiem_khach(p, who(ClinicRole.DOCTOR), KHACH)
    assert await pham_vi(p, who(ClinicRole.DOCTOR)) == {
        "la_thu_ky": False,
        "bac_si": [],
    }
    assert p.calls == []


@pytest.mark.asyncio
async def test_thu_ky_chua_phan_khong_thay_ai() -> None:
    from clinicai.services.thu_ky_bac_si import (
        CHUA_PHAN,
        khach_duoc_xem,
        kiem_khach,
        kiem_thu_ky_duoc_lam,
        pham_vi,
    )

    p = pool(("FROM public.thu_ky_bac_si", None))
    tk = who(ClinicRole.TKYK)
    assert await khach_duoc_xem(p, tk) == []
    with pytest.raises(SafetyGateError, match="chưa được phân"):
        await kiem_khach(p, tk, KHACH)
    with pytest.raises(SafetyGateError) as e:
        kiem_thu_ky_duoc_lam([], BS1)
    assert str(e.value) == CHUA_PHAN
    assert await pham_vi(p, tk) == {"la_thu_ky": True, "bac_si": []}


@pytest.mark.asyncio
async def test_thu_ky_da_phan_chi_khach_bac_si_minh() -> None:
    from clinicai.services.thu_ky_bac_si import (
        KHAC_BAC_SI,
        khach_duoc_xem,
        kiem_khach,
        kiem_thu_ky_duoc_lam,
        pham_vi,
    )

    p = pool(
        ("FROM public.thu_ky_bac_si", [BS1]),
        ("role = 'ULTRASOUND_DOCTOR'", True),
        ("UNION", [{"id": KHACH}, {"id": None}]),
        ("SELECT s.id::text AS id, s.full_name", [{"id": BS1, "full_name": "BS Một"}]),
    )
    tk = who(ClinicRole.TKYK)
    assert await khach_duoc_xem(p, tk) == [KHACH]
    await kiem_khach(p, tk, KHACH)
    with pytest.raises(SafetyGateError, match="bác sĩ khác"):
        await kiem_khach(p, tk, "khac")
    kiem_thu_ky_duoc_lam([BS1], BS1)
    kiem_thu_ky_duoc_lam(None, BS2)
    with pytest.raises(SafetyGateError) as e:
        kiem_thu_ky_duoc_lam([BS1], None)
    assert str(e.value) == KHAC_BAC_SI
    ket_qua = await pham_vi(p, tk)
    assert ket_qua["bac_si"] == [{"id": BS1, "full_name": "BS Một"}]
    # Cờ "có theo bác sĩ siêu âm" được truyền vào câu tìm khách.
    assert p.da_goi("UNION")[0][2] is True


@pytest.mark.asyncio
async def test_dat_bac_si_cho_thu_ky() -> None:
    from clinicai.services.thu_ky_bac_si import dat_bac_si_cho_thu_ky

    with pytest.raises(SafetyGateError):
        await dat_bac_si_cho_thu_ky(
            pool(),
            identity=who(ClinicRole.TRUONG_CA),
            thu_ky_staff_id=ME,
            bac_si_staff_ids=[],
        )
    with pytest.raises(ValidationError, match="không phải thư ký"):
        await dat_bac_si_cho_thu_ky(
            pool(("role = 'TKYK'", False)),
            identity=who(ClinicRole.MANAGEMENT),
            thu_ky_staff_id=ME,
            bac_si_staff_ids=[BS1],
        )
    with pytest.raises(ValidationError, match="không phải bác sĩ"):
        await dat_bac_si_cho_thu_ky(
            pool(("role = 'TKYK'", True), ("count(DISTINCT staff_id)", 0)),
            identity=who(ClinicRole.MANAGEMENT),
            thu_ky_staff_id=ME,
            bac_si_staff_ids=[BS1],
        )
    p = pool(("role = 'TKYK'", True), ("count(DISTINCT staff_id)", 2))
    out = await dat_bac_si_cho_thu_ky(
        p,
        identity=who(ClinicRole.MANAGEMENT),
        thu_ky_staff_id=ME,
        bac_si_staff_ids=[BS2, BS1, BS1],
    )
    assert out["bac_si"] == sorted([BS1, BS2])
    assert p.da_goi("DELETE FROM public.thu_ky_bac_si")
    assert p.da_goi("INSERT INTO public.thu_ky_bac_si")
    assert p.events()


# ── doi_bac_si_service ────────────────────────────────────────────────────


def _luot(status: str = "IN_PROGRESS", bac_si: str | None = BS1) -> dict[str, Any]:
    return {
        "visit_id": VISIT,
        "status": status,
        "appointment_id": "f0000000-0000-4000-8000-000000000001",
        "bac_si_cu": bac_si,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "ly_do", "luot", "la_bac_si", "loi"),
    [
        (ClinicRole.RECEPTION, "x", _luot(), True, SafetyGateError),
        (ClinicRole.TRUONG_CA, "  ", _luot(), True, ValidationError),
        (ClinicRole.TRUONG_CA, "x", None, True, NotFoundError),
        (ClinicRole.TRUONG_CA, "x", _luot("INCOMPLETE"), True, ValidationError),
        (ClinicRole.TRUONG_CA, "x", _luot("FINALIZED"), True, ValidationError),
        (ClinicRole.TRUONG_CA, "x", _luot(bac_si=BS2), True, ValidationError),
        (ClinicRole.TRUONG_CA, "x", _luot(), False, ValidationError),
    ],
)
async def test_doi_bac_si_tu_choi(
    role: ClinicRole, ly_do: str, luot: Any, la_bac_si: bool, loi: type[Exception]
) -> None:
    from clinicai.services.doi_bac_si_service import DoiBacSiService

    p = pool(("FROM visit", luot), ("SELECT EXISTS", la_bac_si))
    with pytest.raises(loi):
        await DoiBacSiService(p).doi(
            identity=who(role), visit_id=VISIT, bac_si_moi_id=BS2, ly_do=ly_do
        )


@pytest.mark.asyncio
async def test_doi_bac_si_thanh_cong_doi_ca_bon_cho() -> None:
    from clinicai.services.doi_bac_si_service import DoiBacSiService

    p = pool(
        ("FROM visit", _luot()),
        ("SELECT EXISTS", True),
        ("FROM clinic_membership m JOIN staff", [{"id": BS2, "full_name": "BS Hai"}]),
    )
    out = await DoiBacSiService(p).doi(
        identity=who(ClinicRole.TRUONG_CA),
        visit_id=VISIT,
        bac_si_moi_id=BS2,
        ly_do="BS Một nghỉ",
    )
    assert out["bac_si_moi_id"] == BS2
    for needle in (
        "UPDATE visit SET attending_doctor_id",
        "UPDATE appointment SET doctor_id",
        "UPDATE consultation",
        "UPDATE queue_entry",
    ):
        assert p.da_goi(needle), needle
    assert p.events()
    ds = await DoiBacSiService(p).bac_si_trong_phong_kham(
        identity=who(ClinicRole.TRUONG_CA)
    )
    assert ds == [{"id": BS2, "full_name": "BS Hai"}]


# ── thu_tu_kham_service ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_keo_thu_tu_va_uu_tien() -> None:
    from clinicai.services.thu_tu_kham_service import ThuTuKhamService

    moc = [
        {"appointment_id": "a", "visit_id": VISIT, "moc": 3000.0},
        {"appointment_id": "b", "visit_id": "v2", "moc": 1000.0},
        {"appointment_id": "c", "visit_id": "v3", "moc": 2000.0},
    ]
    p = pool(("coalesce(v.thu_tu_tay_ms", moc))
    out = await ThuTuKhamService(p).keo(
        identity=who(ClinicRole.RECEPTION),
        appointment_id="a",
        sau_appointment_id="b",
        truoc_appointment_id="c",
    )
    assert out["thu_tu_tay_ms"] == 1500.0
    assert p.da_goi("UPDATE visit") and p.events()

    with pytest.raises(ValidationError, match="cạnh chính mình"):
        await ThuTuKhamService(p).keo(
            identity=who(ClinicRole.RECEPTION),
            appointment_id="a",
            sau_appointment_id="a",
            truoc_appointment_id=None,
        )
    with pytest.raises(NotFoundError):
        await ThuTuKhamService(pool()).keo(
            identity=who(ClinicRole.RECEPTION),
            appointment_id="a",
            sau_appointment_id=None,
            truoc_appointment_id="c",
        )
    with pytest.raises(ValidationError, match="tải lại"):
        await ThuTuKhamService(pool(("coalesce(v.thu_tu_tay_ms", moc[:1]))).keo(
            identity=who(ClinicRole.RECEPTION),
            appointment_id="a",
            sau_appointment_id=None,
            truoc_appointment_id="c",
        )

    p2 = pool(("UPDATE patient", KHACH))
    ok = await ThuTuKhamService(p2).dat_uu_tien(
        identity=who(ClinicRole.CSKH),
        clinic_patient_id=KHACH,
        uu_tien=True,
        ly_do=" VIP ",
    )
    assert ok == {"ok": True, "uu_tien": True, "uu_tien_ly_do": "VIP"}
    with pytest.raises(NotFoundError):
        await ThuTuKhamService(pool()).dat_uu_tien(
            identity=who(ClinicRole.CSKH),
            clinic_patient_id=KHACH,
            uu_tien=False,
            ly_do=None,
        )
    with pytest.raises(SafetyGateError):
        await ThuTuKhamService(pool()).dat_uu_tien(
            identity=who(ClinicRole.DOCTOR),
            clinic_patient_id=KHACH,
            uu_tien=False,
            ly_do=None,
        )


# ── bao_ket_qua_ve + thong bao dich danh ──────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("bac_si", [BS1, None])
async def test_bao_ket_qua_ve_bao_cskh_va_bac_si(bac_si: str | None) -> None:
    from clinicai.services.bao_ket_qua_ve import bao_ket_qua_ve

    p = pool(
        (
            "FROM patient p",
            {"full_name": "Khách", "patient_code": "BN1", "bac_si_id": bac_si},
        ),
        (
            "INSERT INTO public.thong_bao",
            {"id": "t1", "tao_luc": datetime.now(timezone.utc)},
        ),
    )
    await bao_ket_qua_ve(
        p,
        identity=who(ClinicRole.DOCTOR),
        loai="xet_nghiem",
        ref_id="r1",
        clinic_patient_id=KHACH,
        appointment_id=None,
        visit_id=VISIT,
    )
    thong_bao = p.da_goi("INSERT INTO public.thong_bao")
    assert len(thong_bao) == 2
    if bac_si:
        assert any(BS1 in args for args in thong_bao)
    else:
        assert any("DOCTOR" in args for args in thong_bao)


@pytest.mark.asyncio
async def test_bao_ket_qua_ve_nuot_loi_va_bo_qua_khi_khong_co_khach() -> None:
    from clinicai.services.bao_ket_qua_ve import bao_ket_qua_ve

    await bao_ket_qua_ve(
        pool(("FROM patient p", RuntimeError("mất kết nối"))),
        identity=who(ClinicRole.DOCTOR),
        loai="tep",
        ref_id="r",
        clinic_patient_id=KHACH,
        appointment_id=None,
        visit_id=None,
    )
    p = pool()
    await bao_ket_qua_ve(
        p,
        identity=who(ClinicRole.DOCTOR),
        loai="tep",
        ref_id="r",
        clinic_patient_id=KHACH,
        appointment_id=None,
        visit_id=None,
    )
    assert not p.da_goi("thong_bao")


@pytest.mark.asyncio
async def test_goi_nguoi_trung_va_sai_nguon() -> None:
    from clinicai.services.thong_bao_service import ThongBaoService

    kw: dict[str, Any] = {
        "identity": who(ClinicRole.DOCTOR),
        "nguoi_nhan_staff_id": BS1,
        "tieu_de": "t",
        "noi_dung": "n",
        "nguon_id": "x",
    }
    assert await ThongBaoService(pool()).goi_nguoi(nguon="ket_qua_ve", **kw) == {
        "ok": True,
        "da_goi_tu_truoc": True,
    }
    with pytest.raises(ValidationError):
        await ThongBaoService(pool()).goi_nguoi(nguon="khong_co", **kw)
    with pytest.raises(ValidationError):
        await ThongBaoService(pool()).goi_nguoi(nguon="ket_qua_ve", muc_do="X", **kw)


# ── ultrasound: nhận ca, lần mới ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_nhan_ca_sieu_am() -> None:
    from clinicai.services.ultrasound_board_service import (
        UltrasoundBoardService,
        co_lan_sieu_am_moi,
        ghi_bac_si_thuc_hien,
    )

    p = pool(("role = 'ULTRASOUND_DOCTOR'", True), ("UPDATE public.work_item", VISIT))
    out = await UltrasoundBoardService(p).nhan_ca(
        identity=who(ClinicRole.ULTRASOUND_DOCTOR), work_item_id="w", bac_si_id=None
    )
    assert out == {"ok": True, "bac_si_id": ME} and p.events()
    with pytest.raises(ValidationError, match="Chọn bác sĩ"):
        await UltrasoundBoardService(p).nhan_ca(
            identity=who(ClinicRole.TRUONG_CA), work_item_id="w", bac_si_id=None
        )
    with pytest.raises(SafetyGateError):
        await UltrasoundBoardService(p).nhan_ca(
            identity=who(ClinicRole.TKYK), work_item_id="w", bac_si_id=BS1
        )
    with pytest.raises(ValidationError, match="không phải bác sĩ siêu âm"):
        await UltrasoundBoardService(
            pool(("role = 'ULTRASOUND_DOCTOR'", False))
        ).nhan_ca(identity=who(ClinicRole.MANAGEMENT), work_item_id="w", bac_si_id=BS1)
    with pytest.raises(ValidationError, match="không còn chờ"):
        await UltrasoundBoardService(
            pool(("role = 'ULTRASOUND_DOCTOR'", True))
        ).nhan_ca(identity=who(ClinicRole.MANAGEMENT), work_item_id="w", bac_si_id=BS1)
    assert (
        await co_lan_sieu_am_moi(pool(("created_at > $3", True)), CLINIC, VISIT, 1)
        is True
    )
    c = pool()
    await ghi_bac_si_thuc_hien(c, clinic_id=CLINIC, visit_id=VISIT, bac_si_id=BS1)
    assert c.da_goi("assigned_to IS NULL")


# ── service_order: danh sách tích / bỏ tích ────────────────────────────────


@pytest.mark.asyncio
async def test_bo_tich_chi_dinh() -> None:
    from clinicai.api.exceptions import ConflictError
    from clinicai.services.service_order_service import ServiceOrderService

    luot = {"visit_id": VISIT, "attending_doctor_id": ME, "closed_at": None}
    base = [("SELECT visit_id, attending_doctor_id, closed_at", luot)]

    async def bo(
        p: Any, role: ClinicRole = ClinicRole.DOCTOR, ly_do: str = "Đổi ý"
    ) -> Any:
        return await ServiceOrderService(p).bo_chi_dinh(
            visit_id=VISIT, service_code="SA", ly_do=ly_do, identity=who(role)
        )

    with pytest.raises(SafetyGateError):
        await bo(pool(*base), ClinicRole.TKYK)
    with pytest.raises(ValidationError, match="lý do"):
        await bo(pool(*base), ly_do=" ")
    with pytest.raises(SafetyGateError, match="phụ trách"):
        await bo(
            pool(
                (
                    "SELECT visit_id, attending_doctor_id",
                    {**luot, "attending_doctor_id": BS2},
                )
            )
        )
    with pytest.raises(NotFoundError):
        await bo(pool(*base))
    with pytest.raises(ConflictError):
        await bo(
            pool(
                *base,
                (
                    "SELECT w.id::text AS id",
                    {"id": "w", "status": "COMPLETED", "node_code": "N"},
                ),
            )
        )
    p = pool(
        *base,
        ("SELECT w.id::text AS id", {"id": "w", "status": "PENDING", "node_code": "N"}),
        ("RETURNING jsonb_array_length", 0),
    )
    out = await bo(p)
    assert out == {"ok": True, "con_lai": 0}
    assert p.events()

    ds = pool(
        (
            "jsonb_array_elements",
            [
                {
                    "service_code": "SA",
                    "name": "Siêu âm",
                    "node_code": "N",
                    "status": "PENDING",
                    "lan": 2,
                }
            ],
        )
    )
    assert (
        await ServiceOrderService(ds).dang_chi_dinh(
            visit_id=VISIT, identity=who(ClinicRole.DOCTOR)
        )
    )[0]["lan"] == 2
