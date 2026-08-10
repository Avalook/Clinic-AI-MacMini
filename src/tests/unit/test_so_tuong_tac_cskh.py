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


def test_router_literal_khop_service() -> None:
    """Cửa Pydantic và từ điển của service phải là MỘT bộ từ.

    Ngày 08/08 hai lần mở rộng từ điển (KLLD/Hẹn GLS, rồi GHI_NHAN) chỉ sửa
    service — chỗ replace vào router trượt trong im lặng vì chuỗi đích đã bị
    format khác đi. Hậu quả chạy thẳng trên bản thật: CSKH chọn "không liên
    lạc được" trên màn là ăn 422, vì service nhận mà cửa Pydantic đã đóng.
    Không lớp kiểm nào bắt được — service test không đi qua Pydantic, còn
    người thử tay chỉ thử hai giá trị cũ.
    """
    from typing import get_args

    from clinicai.api.v1.routers.cskh import TuongTacRequest
    from clinicai.services.tuong_tac_cskh_service import (
        KENH_HOP_LE,
        KET_QUA_HOP_LE,
        LOAI_HOP_LE,
    )

    fields = TuongTacRequest.model_fields
    assert set(get_args(fields["loai"].annotation)) == LOAI_HOP_LE
    assert set(get_args(fields["ket_qua"].annotation)) == KET_QUA_HOP_LE
    assert set(get_args(fields["kenh"].annotation)) == KENH_HOP_LE


# ── Gửi Zalo: chỉ ghi sổ khi Zalo thật sự nhận ─────────────────────────────


@pytest.mark.asyncio
async def test_zalo_that_bai_thi_khong_ghi_so(monkeypatch: Any) -> None:
    """Đây là chỗ dễ nói dối nhất trong cả màn.

    Một dòng "đã liên hệ" ghi trước khi biết kết quả sẽ khiến người trực ca sau
    tin rằng khách đã được báo — và không ai gọi nữa.
    """
    from clinicai.services import tuong_tac_cskh_service as mod
    from clinicai.services.providers import zalo

    async def gia_lap(**_k: Any) -> dict[str, Any]:
        return {"da_gui": False, "ly_do": "CHUA_CAU_HINH", "chi_tiet": "chưa nối"}

    monkeypatch.setattr(zalo, "gui_zns", gia_lap)
    monkeypatch.setattr(zalo, "template_cho", lambda _l: "tpl")

    pool = PoolMotDong({"full_name": "Lan", "phone_primary": "0989862764"})
    d = await mod.GuiZaloService(pool).gui(
        identity=_ai(), clinic_patient_id=BN, loai_tin="NHAC_HEN"
    )
    assert d["da_gui"] is False
    # Chỉ một lần đọc bệnh nhân — KHÔNG có lần ghi nào vào sổ tương tác.
    assert len(pool.calls) == 1


@pytest.mark.asyncio
async def test_khach_khong_co_sdt_thi_bao_ngay() -> None:
    from clinicai.services import tuong_tac_cskh_service as mod

    pool = PoolMotDong({"full_name": "Lan", "phone_primary": "  "})
    with pytest.raises(ValidationError):
        await mod.GuiZaloService(pool).gui(
            identity=_ai(), clinic_patient_id=BN, loai_tin="NHAC_HEN"
        )


@pytest.mark.asyncio
async def test_loai_tin_la_thi_tu_choi() -> None:
    from clinicai.services import tuong_tac_cskh_service as mod

    with pytest.raises(ValidationError):
        await mod.GuiZaloService(PoolMotDong(None)).gui(
            identity=_ai(), clinic_patient_id=BN, loai_tin="QUANG_CAO"
        )


def test_checkout_cua_cskh_dong_luon_luot_kham() -> None:
    """CHECK_OUT phải đóng CẢ `appointment` LẪN `visit`.

    HAI MỐC "KẾT THÚC LƯỢT" TỪNG KHÔNG NÓI CHUYỆN VỚI NHAU.
    `apply_action("complete")` chỉ đặt `appointment.status = COMPLETED`; dòng
    `visit` do quầy đóng qua `CheckoutService.close`. Nên nút Checkout ở màn
    CSKH đóng đúng một nửa — và nửa còn lại là nửa mà bảng điều phối đọc.

    Đo trên staging 10/08/2026: 12 trên 15 dòng `visit` chưa đóng có lịch hẹn đã
    COMPLETED. Bệnh nhân đã về nhà vẫn nằm trong hàng đợi của một phòng.

    Đọc mã nguồn thay vì dựng cả một lượt khám: thứ cần canh là hai lời gọi có
    còn đi cùng nhau không, và điều đó đọc được.
    """
    import inspect

    from clinicai.services import tuong_tac_cskh_service as mod

    doi_tt = inspect.getsource(mod.TuongTacCskhService._doi_trang_thai_lich)
    assert 'action="complete"' in doi_tt, "nhánh CHECK_OUT đã đổi hình dạng"
    assert "_dong_luot_kham" in doi_tt, (
        "CHECK_OUT không còn gọi `_dong_luot_kham` — lịch hẹn sẽ COMPLETED "
        "trong khi dòng `visit` mở vĩnh viễn, và quầy không bao giờ thấy nó "
        "trong danh sách chờ đóng nữa."
    )

    dong = inspect.getsource(mod.TuongTacCskhService._dong_luot_kham)
    assert "CheckoutService" in dong and ".close(" in dong, (
        "`_dong_luot_kham` phải đi qua `CheckoutService.close` — đó là đường "
        "DUY NHẤT dọn đủ ba thứ: đóng bước LUOTKHAM-15, bỏ con trỏ phòng, và "
        "ghi closed_at/closed_by. Tự viết UPDATE ở đây sẽ quên một trong ba."
    )
    assert "override_reason" in dong, (
        "phải truyền lý do ngoại lệ, nếu không lượt còn vướng sẽ không đóng "
        "được và lỗi bị nuốt trong im lặng"
    )


def test_khong_ghi_event_log_voi_aggregate_id_rong() -> None:
    """`event_log.aggregate_id` là NOT NULL — đừng để lọt một câu INSERT nào.

    LỖI 10/08/2026: `hoan_tac` chèn `NULL` vào cột ấy, nên MỌI cú hoàn tác trả
    500 với *"null value in column aggregate_id"*. Câu `ghi()` ngay bên trên đã
    dùng đúng `clinic_patient_id`; chép sai một tham số là đủ.

    Sai lầm này không có gì bắt được: mypy không biết ràng buộc của database,
    và câu INSERT chỉ nổ lúc chạy thật. Nên canh bằng mã nguồn — rẻ và đúng
    chỗ hay quên.
    """
    import inspect
    import re

    from clinicai.services import tuong_tac_cskh_service as mod

    src = inspect.getsource(mod)
    # Mỗi câu INSERT vào event_log phải điền aggregate_id bằng một tham số
    # ($n) chứ không phải chữ NULL.
    for khoi in re.findall(
        r"INSERT INTO public\.event_log.*?VALUES\s*\((.*?)\)\s*\n",
        src,
        re.S,
    ):
        # Ba cột đầu là clinic_id, event_type, aggregate_type; cột thứ tư là
        # aggregate_id.
        cot = [c.strip() for c in khoi.split(",")]
        assert len(cot) >= 4, f"không đọc được câu VALUES: {khoi!r}"
        assert cot[3].upper() != "NULL", (
            "một câu INSERT vào event_log đang để aggregate_id = NULL, mà cột "
            "ấy là NOT NULL — lời gọi sẽ trả 500 ngay lần chạy đầu."
        )
