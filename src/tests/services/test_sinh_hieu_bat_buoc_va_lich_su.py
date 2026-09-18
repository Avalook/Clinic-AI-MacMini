"""Sinh hiệu: 100% đo huyết áp, có thai thêm chiều cao + cân nặng, mỗi lần đo một dòng.

Luật PM (CONTEXT v1.0), sửa 15/09/2026. Trước đó hồ sơ khám cũ chỉ bắt buộc ở
giao diện (D26: huyết áp + cân nặng + chiều cao cho MỌI khách) và ghi đè JSON —
đo lại là mất số cũ, không biết ai đo. Nay cả hai đường ghi (hồ sơ khám cũ và
màn luồng khám) dùng CÙNG luật `luot_kham_rules` và cùng bảng `vital_measurement`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole
from clinicai.services import luot_kham_rules as rules
from clinicai.services.clinical_record_service import sinh_hieu_tu_ho_so
from clinicai.services.luot_kham_rules import Vitals, thieu_sinh_hieu_khi_co_thai
from tests.services.test_clinical_record_revision import (
    PATIENT,
    VISIT,
    identity,
    setup_service,
)


def test_huyet_ap_chuoi_tach_thanh_hai_so() -> None:
    so = sinh_hieu_tu_ho_so(
        {"huyet_ap": " 120 / 80 ", "mach": "72", "nhiet_do": "36,8"}, co_thai=False
    )
    assert (so.systolic, so.diastolic, so.pulse) == (120, 80, 72)
    assert so.temperature == Decimal("36.8")


@pytest.mark.parametrize("vitals", [{}, {"mach": "80"}, {"huyet_ap": "  "}])
def test_thieu_huyet_ap_bi_tu_choi(vitals: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="huyết áp"):
        sinh_hieu_tu_ho_so(vitals, co_thai=False)


@pytest.mark.parametrize("huyet_ap", ["120", "120-80", "abc/80", "80/120", "120/80/60"])
def test_huyet_ap_sai_dang_khong_doan(huyet_ap: str) -> None:
    with pytest.raises(ValidationError):
        sinh_hieu_tu_ho_so({"huyet_ap": huyet_ap}, co_thai=False)


def test_khong_thai_khong_bat_can_nang_chieu_cao() -> None:
    # D26 cũ bắt cân nặng + chiều cao cho MỌI khách; luật PM chỉ bắt khi có thai.
    assert sinh_hieu_tu_ho_so({"huyet_ap": "110/70"}, co_thai=False).weight_kg is None


def test_co_thai_thieu_chieu_cao_can_nang_bi_tu_choi() -> None:
    with pytest.raises(ValidationError, match="chiều cao và cân nặng"):
        sinh_hieu_tu_ho_so({"huyet_ap": "110/70"}, co_thai=True)
    with pytest.raises(ValidationError, match="cân nặng"):
        sinh_hieu_tu_ho_so({"huyet_ap": "110/70", "chieu_cao": "158"}, co_thai=True)
    so = sinh_hieu_tu_ho_so(
        {"huyet_ap": "110/70", "chieu_cao": "158", "can_nang": "55"}, co_thai=True
    )
    assert (so.height_cm, so.weight_kg) == (Decimal(158), Decimal(55))


def test_luat_co_thai_dung_chung_cho_luong_kham() -> None:
    v = Vitals(systolic=110, diastolic=70)
    assert thieu_sinh_hieu_khi_co_thai(v, co_thai=False) is None
    assert "chiều cao" in (thieu_sinh_hieu_khi_co_thai(v, co_thai=True) or "")


def _service(*, co_thai: bool, stored_vitals: dict[str, Any] | None) -> Any:
    service, conn = setup_service(2)
    appointment, stored = list(conn.fetchrow.side_effect)
    conn.fetchrow.side_effect = [
        appointment,
        {**stored, "soap_objective": {"vitals": stored_vitals or {}}},
    ]

    async def fetchval(sql: str, *_: Any) -> Any:
        return co_thai if "pregnancy" in sql else 3

    conn.fetchval.side_effect = fetchval
    return service, conn


def _vital_inserts(conn: Any) -> list[tuple[Any, ...]]:
    return [
        c.args
        for c in conn.execute.await_args_list
        if "INSERT INTO vital_measurement" in c.args[0]
    ]


async def _save(service: Any, **kwargs: Any) -> dict[str, Any]:
    with patch(
        "clinicai.services.clinical_record_service.record_event", new=AsyncMock()
    ):
        out: dict[str, Any] = await service.save(
            appointment_id="40000000-0000-0000-0000-000000000001",
            clinic_patient_id=PATIENT,
            identity=kwargs.pop("identity", identity()),
            **kwargs,
        )
    return out


@pytest.mark.asyncio
async def test_don_kham_khong_huyet_ap_bi_chan_truoc_moi_lenh_ghi() -> None:
    service, conn = _service(co_thai=False, stored_vitals=None)
    with pytest.raises(ValidationError, match="huyết áp"):
        await _save(
            service,
            expected_revision=2,
            objective={"vitals": {"mach": "80"}},
            objective_sent=True,
        )
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_moi_lan_do_them_mot_dong_lich_su() -> None:
    service, conn = _service(co_thai=False, stored_vitals={"huyet_ap": "120/80"})
    await _save(
        service,
        expected_revision=2,
        objective={"vitals": {"huyet_ap": "135/85", "mach": "90"}},
        objective_sent=True,
    )
    (args,) = _vital_inserts(conn)
    assert args[2] == VISIT
    assert (args[3], args[4], args[5]) == (135, 85, 90)


@pytest.mark.asyncio
async def test_bac_si_luu_ho_so_khong_doi_sinh_hieu_thi_khong_them_dong() -> None:
    service, conn = _service(co_thai=False, stored_vitals={"huyet_ap": "120/80"})
    await _save(
        service,
        expected_revision=2,
        objective={"vitals": {"huyet_ap": ""}},
        objective_sent=True,
        assessment={"diagnosis": "x"},
    )
    assert _vital_inserts(conn) == []


@pytest.mark.asyncio
async def test_bac_si_bo_sung_sinh_hieu_kiem_bo_sau_gop() -> None:
    # Số cũ có huyết áp; bác sĩ chỉ thêm mạch → bộ sau gộp đủ luật, ghi một dòng.
    service, conn = _service(co_thai=False, stored_vitals={"huyet_ap": "120/80"})
    await _save(
        service,
        expected_revision=2,
        objective={"vitals": {"mach": "76"}},
        objective_sent=True,
    )
    (args,) = _vital_inserts(conn)
    assert (args[3], args[4], args[5]) == (120, 80, 76)


@pytest.mark.asyncio
async def test_khach_co_thai_don_kham_thieu_can_nang_bi_chan() -> None:
    service, conn = _service(co_thai=True, stored_vitals=None)
    with pytest.raises(ValidationError, match="có thai"):
        await _save(
            service,
            expected_revision=2,
            objective={"vitals": {"huyet_ap": "110/70", "chieu_cao": "160"}},
            objective_sent=True,
        )
    assert _vital_inserts(conn) == []


class TestBonChiSoThem:
    """Nhịp thở, SpO₂, BMI, thang đau — thêm vào bảng thật 16/09/2026.

    Trước đó bốn ô này có trên màn nhập nhưng không có cột, nên chúng rơi vào
    JSONB của hồ sơ khám: không vào bảng lịch sử chỉ-thêm, không so được giữa
    các lần đo, và thang đau thì không tồn tại ở đâu cả.
    """

    def test_bon_chi_so_di_qua_duoc_luat_chung(self) -> None:
        vitals, loi = rules.parse_vitals(
            {
                "systolic": 120,
                "diastolic": 80,
                "respiratory_rate": 18,
                "spo2": 99,
                "weight_kg": 54,
                "height_cm": 160.7,
                "pain_score": 3,
            }
        )
        assert loi is None
        assert vitals is not None
        assert vitals.respiratory_rate == 18
        assert vitals.spo2 == 99
        # BMI là số TÍNH RA từ cân/cao (S0-3), không nhận từ client.
        assert str(vitals.bmi) == "20.9"
        assert vitals.pain_score == 3

    def test_khong_nhap_thi_van_luu_duoc(self) -> None:
        # Bốn chỉ số này TUỲ CHỌN — ép chúng là ép điều dưỡng gõ số không đo.
        vitals, loi = rules.parse_vitals({"systolic": 120, "diastolic": 80})
        assert loi is None
        assert vitals is not None
        assert vitals.respiratory_rate is None
        assert vitals.pain_score is None

    @pytest.mark.parametrize(
        ("truong", "gia_tri", "chu"),
        [
            ("pain_score", 44, "Mức độ đau"),
            ("spo2", 30, "SpO₂"),
            ("respiratory_rate", 200, "Nhịp thở"),
        ],
    )
    def test_ngoai_khoang_bi_chan_bang_cau_doc_duoc(
        self, truong: str, gia_tri: int, chu: str
    ) -> None:
        # Khoảng ở đây phải KHỚP CHECK của database (20260916000003); rộng hơn
        # là để người đo gõ xong mới bị máy chủ từ chối.
        _, loi = rules.parse_vitals({"systolic": 120, "diastolic": 80, truong: gia_tri})
        assert loi is not None and chu in loi

    def test_spo2_va_nhip_tho_phai_la_so_nguyen(self) -> None:
        _, loi = rules.parse_vitals({"systolic": 120, "diastolic": 80, "spo2": 98.5})
        assert loi is not None and "số nguyên" in loi

    def test_ho_so_kham_cu_cung_mang_duoc_bon_chi_so(self) -> None:
        # Màn hồ sơ khám gửi khoá tiếng Việt; thiếu ánh xạ thì bốn ô ấy lại rơi
        # vào JSONB như trước.
        so = sinh_hieu_tu_ho_so(
            {
                "huyet_ap": "118/76",
                "nhip_tho": 16,
                "spo2": 98,
                "can_nang": 52,
                "chieu_cao": 160.4,
                "bmi": "35",
                "muc_do_dau": 0,
            },
            co_thai=False,
        )
        assert so.respiratory_rate == 16
        assert so.spo2 == 98
        # Ô "bmi" hồ sơ cũ gửi lên bị bỏ qua — BMI tính lại từ cân/cao (S0-3).
        assert str(so.bmi) == "20.2"
        assert so.pain_score == 0


@pytest.mark.asyncio
async def test_duong_don_kham_cu_bi_tu_choi() -> None:
    """17/09/2026 (Tuyền: "cái nào cũ thì bỏ"): lưu sinh hiệu qua biểu mẫu bệnh
    án kiểu đón-khám từng làm khách kẹt ngoài hàng chờ bác sĩ — nay từ chối."""
    service, conn = _service(co_thai=False, stored_vitals=None)
    with pytest.raises(ValidationError, match="màn Đo sinh hiệu"):
        await _save(
            service,
            identity=identity(ClinicRole.NURSE_ULTRASOUND),
            vitals_only=True,
            objective={"vitals": {"huyet_ap": "120/80"}},
        )
    conn.execute.assert_not_awaited()
