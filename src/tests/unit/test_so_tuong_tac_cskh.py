"""Sổ tương tác CSKH — ràng buộc phải nổ bằng tiếng Việt, không phải 500.

Bốn luật của bảng nằm ở CHECK trong 20260809000003. Nếu service để lời gọi sai
đi thẳng xuống database thì người dùng nhận một lỗi 500 và một dòng log Postgres
tiếng Anh. Kiểm ở đây để họ nhận một câu đọc được.
"""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.tuong_tac_cskh_service import TuongTacCskhService

CLINIC = "a0000000-0000-4000-8000-000000000001"
BN = "b0000000-0000-4000-8000-000000000001"


def _ai() -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="Chị Điều",
        department="CSKH",
        role=ClinicRole.CSKH,
        clinic_id=CLINIC,
        location_id="l1",
        location_name="Kim Ngưu",
    )


class PoolTrong:
    """Không kết nối gì cả — mọi bài dưới đây phải dừng TRƯỚC khi chạm database."""

    def acquire(self) -> "PoolTrong":
        raise AssertionError("Lời gọi sai đã đi tới database thay vì bị chặn sớm.")

    async def fetch(self, *_a: Any, **_k: Any) -> Any:
        raise AssertionError("Lời gọi sai đã đi tới database thay vì bị chặn sớm.")


def _svc() -> TuongTacCskhService:
    return TuongTacCskhService(PoolTrong())


async def _ghi(**kwargs: Any) -> Any:
    mac_dinh: dict[str, Any] = {
        "identity": _ai(),
        "clinic_patient_id": BN,
        "loai": "KHAC",
        "kenh": "GOI",
        "ket_qua": "DA_LIEN_HE",
    }
    return await _svc().ghi(**{**mac_dinh, **kwargs})


@pytest.mark.asyncio
async def test_bo_qua_phai_di_cung_khong_lien_he() -> None:
    """Tách hai nửa ra thì sẽ có dòng ghi "đã gọi điện" mà kết quả là "bỏ qua"."""
    with pytest.raises(ValidationError):
        await _ghi(kenh="GOI", ket_qua="BO_QUA")
    with pytest.raises(ValidationError):
        await _ghi(kenh="KHONG_LIEN_HE", ket_qua="DA_LIEN_HE")


@pytest.mark.asyncio
async def test_khach_xac_nhan_chi_co_nghia_o_hai_loai_viec() -> None:
    with pytest.raises(ValidationError):
        await _ghi(loai="TRA_KQ", khach_xac_nhan=True)


@pytest.mark.asyncio
async def test_ba_loai_viec_phai_gan_voi_mot_lich_hen() -> None:
    """Ghi "đã gọi xác nhận" mà không nói lịch nào.

    Lần sau mở ra không ai biết đã gọi cho lịch tuần trước hay tuần sau.
    """
    for loai in ("XAC_NHAN_LICH", "NHAC_HEN", "HOI_LY_DO_HUY"):
        with pytest.raises(ValidationError):
            await _ghi(loai=loai, appointment_id=None)


@pytest.mark.asyncio
async def test_tu_dien_dong_khong_nhan_gia_tri_la() -> None:
    with pytest.raises(ValidationError):
        await _ghi(loai="GOI_CHO_VUI")
    with pytest.raises(ValidationError):
        await _ghi(kenh="BO_CAU")
    with pytest.raises(ValidationError):
        await _ghi(ket_qua="CHUA_BIET")


# ── Việc CSKH tự hẹn ───────────────────────────────────────────────────────


def _hen() -> Any:
    from clinicai.services.tuong_tac_cskh_service import HenGoiLaiService

    return HenGoiLaiService(PoolTrong())


@pytest.mark.asyncio
async def test_hen_goi_lai_phai_co_ly_do() -> None:
    """Một việc không có lý do là việc mà tuần sau không ai biết vì sao nó ở đó."""
    from datetime import date, timedelta

    with pytest.raises(ValidationError):
        await _hen().tao(
            identity=_ai(),
            clinic_patient_id=BN,
            ngay_goi=date.today() + timedelta(days=1),
            ly_do="   ",
        )


@pytest.mark.asyncio
async def test_khong_hen_duoc_vao_qua_khu() -> None:
    from datetime import date, timedelta

    with pytest.raises(ValidationError):
        await _hen().tao(
            identity=_ai(),
            clinic_patient_id=BN,
            ngay_goi=date.today() - timedelta(days=1),
            ly_do="hỏi thăm sau thủ thuật",
        )


@pytest.mark.asyncio
async def test_ba_ket_qua_goi_hut_deu_hop_le() -> None:
    """KNM / KLLD / Hẹn GLS phải là ba giá trị KHÁC nhau.

    Gộp cả ba vào "chưa nghe máy" thì báo cáo cuối tháng nói phòng khám gọi
    hụt 30% khách, trong khi một phần ba số đó là khách chủ động hẹn giờ khác.
    """
    from clinicai.services.tuong_tac_cskh_service import KET_QUA_HOP_LE

    assert {"CHUA_NGHE_MAY", "KHONG_LIEN_LAC_DUOC", "HEN_GOI_LAI"} <= KET_QUA_HOP_LE


@pytest.mark.asyncio
async def test_khach_cua_phong_kham_khac_thi_khong_ghi_duoc() -> None:
    """RLS chỉ GIẤU dòng đi, không ngăn nó ra đời — nên phải kiểm ở service."""

    class PoolKhongThayKhach:
        def acquire(self) -> Any:
            return self

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        def transaction(self) -> Any:
            return self

        async def fetchval(self, *_a: Any, **_k: Any) -> Any:
            return None  # patient không thuộc phòng khám này

    from clinicai.api.exceptions import NotFoundError
    from clinicai.services.tuong_tac_cskh_service import (
        HenGoiLaiService,
        TuongTacCskhService,
    )

    with pytest.raises(NotFoundError):
        await TuongTacCskhService(PoolKhongThayKhach()).ghi(
            identity=_ai(),
            clinic_patient_id=BN,
            loai="KHAC",
            kenh="GOI",
            ket_qua="DA_LIEN_HE",
        )

    from datetime import date, timedelta

    with pytest.raises(NotFoundError):
        await HenGoiLaiService(PoolKhongThayKhach()).tao(
            identity=_ai(),
            clinic_patient_id=BN,
            ngay_goi=date.today() + timedelta(days=3),
            ly_do="hỏi thăm",
        )


# ── Mốc tại quầy ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_moc_quay_phai_dung_bo_ghi_nhan() -> None:
    """Mốc ⇔ GHI_NHAN ⇔ trực tiếp. Tách rời được thì sẽ có dòng
    "check-in — chưa nghe máy" hoặc "gọi điện — ghi nhận"."""
    with pytest.raises(ValidationError):
        await _ghi(loai="THANH_TOAN", kenh="TRUC_TIEP", ket_qua="DA_LIEN_HE")
    with pytest.raises(ValidationError):
        await _ghi(loai="KHAC", kenh="TRUC_TIEP", ket_qua="GHI_NHAN")
    with pytest.raises(ValidationError):
        await _ghi(loai="THANH_TOAN", kenh="GOI", ket_qua="GHI_NHAN")


@pytest.mark.asyncio
async def test_check_in_va_check_out_phai_co_lich() -> None:
    """Hai mốc này còn đổi trạng thái của chính lịch đó — không lịch thì đổi gì?"""
    for loai in ("CHECK_IN", "CHECK_OUT"):
        with pytest.raises(ValidationError):
            await _ghi(
                loai=loai, kenh="TRUC_TIEP", ket_qua="GHI_NHAN", appointment_id=None
            )


def test_cskh_duoc_check_in_va_dong_luot() -> None:
    """Quang 08/08: MVP là CSKH thao tác được hết — check-in và check-out phải
    đi đường THẬT của máy trạng thái, nên vai CSKH phải nằm trong cả hai cửa."""
    from clinicai.api.identity import ClinicRole
    from clinicai.services.booking_service import CHECKIN_ROLES, TRANSITIONS

    assert ClinicRole.CSKH in CHECKIN_ROLES
    assert ClinicRole.CSKH in TRANSITIONS["complete"].allowed_roles


class PoolMotDong:
    """Trả đúng một dòng cho fetchrow, ghi lại mọi lời gọi."""

    def __init__(self, dong: Any) -> None:
        self._dong = dong
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, sql: str, *a: Any) -> Any:
        self.calls.append((sql, a))
        return self._dong


@pytest.mark.asyncio
async def test_check_out_khi_khach_chua_den_thi_bao_ro() -> None:
    """Khách chưa check-in mà bấm check-out: lỗi phải NÓI được vì sao, và không
    được để lại dòng sổ nói việc đã xảy ra."""

    pool = PoolMotDong({"status": "CONFIRMED"})
    from clinicai.services.tuong_tac_cskh_service import TuongTacCskhService

    with pytest.raises(ValidationError) as e:
        await TuongTacCskhService(pool)._doi_trang_thai_lich(
            identity=_ai(), appointment_id="ap-1", loai="CHECK_OUT"
        )
    assert "chưa check-in" in str(e.value)


@pytest.mark.asyncio
async def test_check_in_lan_hai_chi_ghi_so_khong_loi() -> None:
    """Lễ tân đã check-in trước rồi thì CSKH bấm lại chỉ ghi sổ — không phải lỗi."""
    pool = PoolMotDong({"status": "CHECKED_IN"})
    from clinicai.services.tuong_tac_cskh_service import TuongTacCskhService

    await TuongTacCskhService(pool)._doi_trang_thai_lich(
        identity=_ai(), appointment_id="ap-1", loai="CHECK_IN"
    )
    # Chỉ một lần đọc trạng thái, không lần ghi nào.
    assert len(pool.calls) == 1
