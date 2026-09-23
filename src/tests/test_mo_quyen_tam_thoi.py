"""Công tắc MỞ QUYỀN TẠM THỜI — nới đúng chỗ, và KHÔNG nới chỗ không được nới.

Tuyền chốt 16/09/2026: *"tất cả các tài khoản đều có thể thao tác đã, đừng bị
phụ thuộc lịch khám nữa, trừ bác sĩ ra thui, tại giờ đang rối, trước mắt giải
quyết vậy đã"*.

Hai nửa của bài này quan trọng ngang nhau:

  • Nửa NỚI  — chứng minh công tắc thật sự mở, để không ai phải thử bằng tay.
  • Nửa KHÔNG NỚI — chứng minh nó KHÔNG chạm vào ba thứ: cửa của bác sĩ, vai
    DISPLAY, và vai PARTNER. Một công tắc "mở tạm" mà lỡ mở cả ba thứ ấy thì
    lúc phát hiện đã là chuyện khác hẳn: người ngoài phòng khám đọc được bệnh
    án, và không có dòng log nào nói ra.
"""

from __future__ import annotations

import pytest

from clinicai.api.identity import (
    VAI_LAM_VIEC,
    ClinicRole,
    RoleGuardCoTheMo,
    StaffIdentity,
    mo_quyen_tam_thoi,
    require_role,
    require_role_co_the_mo,
)


def _danh_tinh(vai: ClinicRole) -> StaffIdentity:
    return StaffIdentity(
        staff_id="s-1",
        auth_user_id="u-1",
        clinic_id="c-1",
        location_id="l-1",
        full_name="Người thử",
        short_name="Thử",
        department=vai.value,
        role=vai,
        location_name="Cơ sở",
        clinic_name="Phòng khám",
    )


def test_cong_tac_doc_luc_goi_chu_khong_phai_luc_dung(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Đổi biến môi trường SAU khi dựng cửa gác vẫn phải có tác dụng.

    Bản đầu quyết định tập vai ngay trong hàm dựng, mà hàm dựng chạy lúc import
    module — tức trước khi ai kịp đặt biến. Đặt `MO_QUYEN_TAM_THOI=0` rồi mà
    quyền vẫn mở, và không có gì trên màn hình mâu thuẫn với điều đó.
    """
    cua = require_role_co_the_mo(ClinicRole.RECEPTION)
    assert isinstance(cua, RoleGuardCoTheMo)

    monkeypatch.setenv("MO_QUYEN_TAM_THOI", "0")
    assert mo_quyen_tam_thoi() is False
    monkeypatch.setenv("MO_QUYEN_TAM_THOI", "1")
    assert mo_quyen_tam_thoi() is True


@pytest.mark.parametrize("gia_tri", ["0", "false", "no", ""])
def test_cac_cach_tat_cong_tac(monkeypatch: pytest.MonkeyPatch, gia_tri: str) -> None:
    monkeypatch.setenv("MO_QUYEN_TAM_THOI", gia_tri)
    assert mo_quyen_tam_thoi() is False


@pytest.mark.parametrize("vai", sorted(VAI_LAM_VIEC, key=lambda r: ClinicRole(r).value))
async def test_cong_tac_bat_thi_moi_vai_lam_viec_qua_duoc(
    monkeypatch: pytest.MonkeyPatch, vai: ClinicRole
) -> None:
    """Đây là điều Tuyền yêu cầu: ai cũng thao tác được."""
    monkeypatch.setenv("MO_QUYEN_TAM_THOI", "1")
    cua = require_role_co_the_mo(ClinicRole.RECEPTION)
    assert await cua(_danh_tinh(vai)) is not None


@pytest.mark.parametrize("vai", [ClinicRole.DISPLAY, ClinicRole.PARTNER])
async def test_cong_tac_khong_mo_cho_vai_ngoai_phong_kham(
    monkeypatch: pytest.MonkeyPatch, vai: ClinicRole
) -> None:
    """Cái tivi và đối tác nằm NGOÀI `VAI_LAM_VIEC`, và phải nằm ngoài.

    Cả hai vốn đã bị `get_current_identity` từ chối trước cả khi tới cửa này —
    nên bài này canh tập `VAI_LAM_VIEC` chứ không canh mã trả về: cái cần giữ
    là "công tắc không bao giờ đếm hai vai ấy là vai làm việc".
    """
    assert vai not in VAI_LAM_VIEC


async def test_cua_cua_bac_si_khong_bi_noi(monkeypatch: pytest.MonkeyPatch) -> None:
    """ "Trừ bác sĩ ra thui" — và đây là chỗ câu ấy được ép."""
    from fastapi import HTTPException

    monkeypatch.setenv("MO_QUYEN_TAM_THOI", "1")
    cua_bac_si = require_role(ClinicRole.DOCTOR)
    assert not isinstance(cua_bac_si, RoleGuardCoTheMo)

    for vai in (ClinicRole.NURSE_ULTRASOUND, ClinicRole.RECEPTION, ClinicRole.CSKH):
        with pytest.raises(HTTPException) as loi:
            await cua_bac_si(_danh_tinh(vai))
        assert loi.value.status_code == 403


def test_dung_cua_co_the_mo_o_cho_khong_phai_viec_bac_si() -> None:
    """Ba cửa vận hành còn theo vai thì mở theo công tắc; cửa lâm sàng thì không.

    Từ CORE-B3 (23/09/2026) check-in, sinh hiệu, khám, ghi chú, duyệt kết quả
    hỏi QUYỀN trong hàm dịch vụ — cửa router chỉ còn "đã đăng nhập", và công
    tắc mở quyền tạm thời KHÔNG nới được chúng: muốn ai làm thì quản lý cấp
    quyền. Việc lâm sàng vì thế vẫn không bao giờ mở theo công tắc.
    """
    from clinicai.api.identity import get_current_identity
    from clinicai.api.v1.routers import luot_kham

    for ten in ("_BANG_GUARD", "_DISPATCH_GUARD", "_PERFORMER_GUARD"):
        assert isinstance(getattr(luot_kham, ten), RoleGuardCoTheMo), (
            f"{ten} phải nới được theo công tắc — Tuyền cần mọi vai thao tác được."
        )

    for ten in (
        "_CHECKIN_GUARD",
        "_VITALS_GUARD",
        "_NOTE_GUARD",
        "_CONSULT_GUARD",
        "_REVIEW_GUARD",
    ):
        assert getattr(luot_kham, ten) is get_current_identity, (
            f"{ten}: quyền nằm ở hàm dịch vụ;"
            " cửa router không được là hệ quyền thứ hai."
        )

    for ten in ("_DOCTOR_GUARD", "_TKYK_GUARD"):
        cua = getattr(luot_kham, ten)
        assert not isinstance(cua, RoleGuardCoTheMo), (
            f"{ten} KHÔNG được nới: khám, ghi bệnh án và duyệt chỉ định là việc "
            "của bác sĩ, ranh giới ấy có luật hành nghề đứng sau."
        )


async def test_thu_ky_chua_phan_bac_si_van_lam_viec_duoc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chính triệu chứng Tuyền gặp: thư ký thấy 0 lượt, điều dưỡng thấy 19.

    `bac_si_cua_thu_ky` trả `None` = "không lọc theo luật này". Khi công tắc
    bật, nó phải trả `None` NGAY, không đọc bảng phân công.
    """
    from clinicai.services.thu_ky_bac_si import bac_si_cua_thu_ky

    class KhongDuocHoi:
        async def fetchval(self, *a: object, **k: object) -> object:
            raise AssertionError(
                "Công tắc đang bật thì không được tra bảng phân công nữa."
            )

    monkeypatch.setenv("MO_QUYEN_TAM_THOI", "1")
    assert await bac_si_cua_thu_ky(KhongDuocHoi(), _danh_tinh(ClinicRole.TKYK)) is None


def test_cua_trong_ham_dich_vu_cung_noi_theo_cong_tac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nới ở router mà quên hàm dịch vụ thì vai mới qua cửa ngoài rồi chết ở trong.

    Đúng cái đã xảy ra chiều 16/09/2026: `_BANG_GUARD` đã nới, nhưng CSKH và thu
    ngân vẫn 403 ở bảng lượt khám — vì `LuotKhamService.bang()` gọi
    `_require(identity, BOARD_ROLES, …)` một lần nữa. Nhìn cửa gác ở router thì
    thấy hoàn toàn đúng.

    Luật nghiệp vụ nằm trong hàm dịch vụ (CLAUDE.md), nên ĐÓ mới là cửa thật.
    """
    from clinicai.core.exceptions import SafetyGateError
    from clinicai.services.luot_kham_service import (
        BOARD_ROLES,
        CHECKIN_ROLES,
        CLINICAL_READ_ROLES,
        DOCTOR_ROLES,
        NOTE_ROLES,
        PERFORMER_ROLES,
        VITALS_ROLES,
        _require,
    )

    monkeypatch.setenv("MO_QUYEN_TAM_THOI", "1")

    # Nới: CSKH và thu ngân — hai vai đã bị chặn trên bản chạy thật.
    for tap in (BOARD_ROLES, CHECKIN_ROLES, VITALS_ROLES, PERFORMER_ROLES):
        for vai in (ClinicRole.CSKH, ClinicRole.CASHIER_DV, ClinicRole.PHARMACIST):
            _require(_danh_tinh(vai), tap, "đáng lẽ phải qua")

    # KHÔNG nới: việc của bác sĩ, và quyền đọc chữ bác sĩ viết trong bệnh án.
    for tap in (DOCTOR_ROLES, NOTE_ROLES, CLINICAL_READ_ROLES):
        with pytest.raises(SafetyGateError):
            _require(_danh_tinh(ClinicRole.CSKH), tap, "phải chặn")


def test_cong_tac_tat_thi_ham_dich_vu_ve_luat_goc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clinicai.core.exceptions import SafetyGateError
    from clinicai.services.luot_kham_service import BOARD_ROLES, _require

    monkeypatch.setenv("MO_QUYEN_TAM_THOI", "0")
    with pytest.raises(SafetyGateError):
        _require(_danh_tinh(ClinicRole.CSKH), BOARD_ROLES, "phải chặn")
    # Vai vốn có trong tập thì vẫn qua.
    _require(_danh_tinh(ClinicRole.RECEPTION), BOARD_ROLES, "đáng lẽ phải qua")
