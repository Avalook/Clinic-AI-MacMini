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

    def acquire(self) -> "PoolMotDong":
        return self

    def transaction(self) -> "PoolMotDong":
        return self

    async def __aenter__(self) -> "PoolMotDong":
        return self

    async def __aexit__(self, *_a: Any) -> None:
        return None


class _ContextPool:
    """Pool/connection tối thiểu để quan sát thứ tự kiểm ownership và ghi."""

    def __init__(self, fetchvals: list[Any]) -> None:
        self.fetchvals = list(fetchvals)
        self.executed: list[str] = []

    def acquire(self) -> "_ContextPool":
        return self

    async def __aenter__(self) -> "_ContextPool":
        return self

    async def __aexit__(self, *_a: Any) -> None:
        return None

    def transaction(self) -> "_ContextPool":
        return self

    async def fetchval(self, sql: str, *_a: Any) -> Any:
        self.executed.append(sql)
        return self.fetchvals.pop(0)

    async def execute(self, sql: str, *_a: Any) -> None:
        self.executed.append(sql)


@pytest.mark.asyncio
async def test_kiem_ownership_truoc_khi_doi_trang_thai_lich(monkeypatch: Any) -> None:
    """Appointment của B không được bị đổi trước khi request patient A bị từ chối."""
    pool = _ContextPool([1, None])
    svc = TuongTacCskhService(pool)
    da_doi = False

    async def doi_sai(**_k: Any) -> bool:
        nonlocal da_doi
        da_doi = True
        return True

    monkeypatch.setattr(svc, "_doi_trang_thai_lich", doi_sai)
    with pytest.raises(ValidationError, match="không phải của khách"):
        await svc.ghi(
            identity=_ai(),
            clinic_patient_id=BN,
            appointment_id="a0000000-0000-4000-8000-000000000099",
            loai="CHECK_OUT",
            kenh="TRUC_TIEP",
            ket_qua="GHI_NHAN",
        )
    assert da_doi is False


@pytest.mark.asyncio
async def test_check_in_da_do_le_tan_khong_tao_dong_co_the_undo(
    monkeypatch: Any,
) -> None:
    """No-op của CSKH không được sinh log rồi đảo check-in thật của Lễ tân."""
    pool = _ContextPool([1, 1])
    svc = TuongTacCskhService(pool)

    async def da_co_roi(**_k: Any) -> bool:
        return False

    monkeypatch.setattr(svc, "_doi_trang_thai_lich", da_co_roi)
    result = await svc.ghi(
        identity=_ai(),
        clinic_patient_id=BN,
        appointment_id="a0000000-0000-4000-8000-000000000099",
        loai="CHECK_IN",
        kenh="TRUC_TIEP",
        ket_qua="GHI_NHAN",
    )
    assert result == {"ok": True, "already_applied": True, "id": None}
    assert not any("INSERT INTO public.tuong_tac_cskh" in sql for sql in pool.executed)


@pytest.mark.asyncio
async def test_undo_checkin_tu_choi_khi_lich_khong_con_checked_in() -> None:
    class PoolUndo(_ContextPool):
        async def fetchrow(self, *_a: Any, **_k: Any) -> Any:
            return {
                "id": "t1",
                "loai": "CHECK_IN",
                "appt": "ap-1",
                "huy_luc": None,
                "bn": BN,
            }

    pool = PoolUndo(["CONFIRMED"])
    with pytest.raises(ValidationError, match="không còn ở trạng thái CHECKED_IN"):
        await TuongTacCskhService(pool).hoan_tac(identity=_ai(), tuong_tac_id="t1")
    assert not any("UPDATE public.tuong_tac_cskh" in sql for sql in pool.executed)


@pytest.mark.asyncio
async def test_undo_checkin_tu_choi_khi_quy_trinh_da_tien(monkeypatch: Any) -> None:
    from clinicai.services import booking_service

    class PoolUndo(_ContextPool):
        async def fetchrow(self, *_a: Any, **_k: Any) -> Any:
            return {
                "id": "t1",
                "loai": "CHECK_IN",
                "appt": "ap-1",
                "huy_luc": None,
                "bn": BN,
            }

    pool = PoolUndo(["CHECKED_IN", True])
    da_undo = False

    async def undo_sai(*_a: Any, **_k: Any) -> None:
        nonlocal da_undo
        da_undo = True

    monkeypatch.setattr(booking_service.BookingService, "apply_action", undo_sai)
    with pytest.raises(ValidationError, match="đã tiếp tục quy trình"):
        await TuongTacCskhService(pool).hoan_tac(identity=_ai(), tuong_tac_id="t1")
    assert da_undo is False
    assert not any("UPDATE public.tuong_tac_cskh" in sql for sql in pool.executed)


@pytest.mark.asyncio
async def test_undo_checkin_hop_le_doi_lich_roi_moi_vo_hieu_log(
    monkeypatch: Any,
) -> None:
    """Một check-in chưa sinh bước sau được đảo thật, rồi mới gạch dòng sổ.

    Thứ tự quan trọng: gạch sổ trước mà máy trạng thái từ chối sẽ làm timeline
    nói khách chưa đến trong khi appointment vẫn CHECKED_IN.
    """
    from clinicai.services import booking_service

    events: list[str] = []

    class PoolUndo(_ContextPool):
        async def fetchrow(self, *_a: Any, **_k: Any) -> Any:
            return {
                "id": "t1",
                "loai": "CHECK_IN",
                "appt": "ap-1",
                "huy_luc": None,
                "bn": BN,
            }

        async def execute(self, sql: str, *_a: Any) -> None:
            await super().execute(sql)
            events.append("void" if "UPDATE public.tuong_tac_cskh" in sql else "event")

    pool = PoolUndo(["CHECKED_IN", False])

    async def undo(*_a: Any, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["appointment_id"] == "ap-1"
        assert kwargs["action"] == "undo_checkin"
        assert kwargs["identity"] == _ai()
        events.append("undo")
        return {"ok": True, "status": "CONFIRMED"}

    monkeypatch.setattr(booking_service.BookingService, "apply_action", undo)
    result = await TuongTacCskhService(pool).hoan_tac(identity=_ai(), tuong_tac_id="t1")

    assert result == {"ok": True}
    assert events == ["undo", "void", "event"]
    assert pool.fetchvals == []


@pytest.mark.asyncio
async def test_undo_khong_tim_thay_interaction_thi_bao_ro() -> None:
    from clinicai.api.exceptions import NotFoundError

    with pytest.raises(NotFoundError, match="Không tìm thấy thao tác"):
        await TuongTacCskhService(PoolMotDong(None)).hoan_tac(
            identity=_ai(), tuong_tac_id="t-khong-co"
        )


@pytest.mark.asyncio
async def test_undo_lan_hai_la_idempotent() -> None:
    pool = PoolMotDong(
        {
            "id": "t1",
            "loai": "CHECK_IN",
            "appt": "ap-1",
            "huy_luc": "2026-08-11T10:00:00+07:00",
            "bn": BN,
        }
    )

    result = await TuongTacCskhService(pool).hoan_tac(identity=_ai(), tuong_tac_id="t1")

    assert result == {"ok": True, "da_hoan_tac_truoc_do": True}


@pytest.mark.asyncio
async def test_undo_checkout_bi_tu_choi_vi_la_moc_khong_dao_duoc() -> None:
    pool = PoolMotDong(
        {
            "id": "t1",
            "loai": "CHECK_OUT",
            "appt": "ap-1",
            "huy_luc": None,
            "bn": BN,
        }
    )

    with pytest.raises(ValidationError, match="Không hoàn tác được lần đóng lượt"):
        await TuongTacCskhService(pool).hoan_tac(identity=_ai(), tuong_tac_id="t1")


@pytest.mark.asyncio
async def test_undo_checkin_bi_tu_choi_sau_khi_da_completed() -> None:
    class PoolUndo(_ContextPool):
        async def fetchrow(self, *_a: Any, **_k: Any) -> Any:
            return {
                "id": "t1",
                "loai": "CHECK_IN",
                "appt": "ap-1",
                "huy_luc": None,
                "bn": BN,
            }

    with pytest.raises(ValidationError, match="đã khám xong"):
        await TuongTacCskhService(PoolUndo(["COMPLETED"])).hoan_tac(
            identity=_ai(), tuong_tac_id="t1"
        )


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
async def test_check_in_lan_hai_la_noop_khong_loi() -> None:
    """Lễ tân đã check-in trước thì CSKH không được tạo transition thứ hai."""
    pool = PoolMotDong({"status": "CHECKED_IN"})
    from clinicai.services.tuong_tac_cskh_service import TuongTacCskhService

    da_doi = await TuongTacCskhService(pool)._doi_trang_thai_lich(
        identity=_ai(), appointment_id="ap-1", loai="CHECK_IN"
    )
    # Chỉ một lần đọc trạng thái, không lần ghi nào.
    assert da_doi is False
    assert len(pool.calls) == 1


@pytest.mark.asyncio
async def test_check_in_hop_le_di_qua_may_trang_thai(monkeypatch: Any) -> None:
    """Check-in thật phải dùng BookingService, không chỉ tích một dòng CSKH."""
    from clinicai.services import booking_service

    pool = PoolMotDong({"status": "CONFIRMED"})
    captured: dict[str, Any] = {}

    async def apply_action(_self: Any, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True, "status": "CHECKED_IN"}

    monkeypatch.setattr(booking_service.BookingService, "apply_action", apply_action)
    da_doi = await TuongTacCskhService(pool)._doi_trang_thai_lich(
        identity=_ai(), appointment_id="ap-1", loai="CHECK_IN"
    )

    assert da_doi is True
    assert captured == {
        "appointment_id": "ap-1",
        "action": "checkin",
        "identity": _ai(),
    }


@pytest.mark.asyncio
async def test_check_out_sach_dong_visit_truoc_appointment(
    monkeypatch: Any,
) -> None:
    """Nếu visit đóng được, appointment mới được chuyển sang COMPLETED."""
    from clinicai.services import booking_service

    pool = PoolMotDong({"status": "CHECKED_IN"})
    svc = TuongTacCskhService(pool)
    events: list[str] = []

    async def dong_visit(**kwargs: Any) -> None:
        assert kwargs["identity"] == _ai()
        assert kwargs["appointment_id"] == "ap-1"
        assert kwargs["pool"] is not None
        events.append("close_visit")

    async def complete(_self: Any, **kwargs: Any) -> dict[str, Any]:
        assert kwargs == {
            "appointment_id": "ap-1",
            "action": "complete",
            "identity": _ai(),
        }
        events.append("complete_appointment")
        return {"ok": True, "status": "COMPLETED"}

    monkeypatch.setattr(svc, "_dong_luot_kham", dong_visit)
    monkeypatch.setattr(booking_service.BookingService, "apply_action", complete)
    da_doi = await svc._doi_trang_thai_lich(
        identity=_ai(), appointment_id="ap-1", loai="CHECK_OUT"
    )

    assert da_doi is True
    assert events == ["close_visit", "complete_appointment"]


@pytest.mark.asyncio
async def test_checkout_visit_va_appointment_cung_mot_transaction(
    monkeypatch: Any,
) -> None:
    """Complete lỗi phải rollback cả visit, không để trạng thái split-brain."""
    from clinicai.services import booking_service, checkout_service

    events: list[str] = []

    class AtomicPool:
        depth = 0

        class Acquire:
            def __init__(self, conn: "AtomicPool") -> None:
                self.conn = conn

            async def __aenter__(self) -> "AtomicPool":
                return self.conn

            async def __aexit__(self, *_a: Any) -> None:
                return None

        def acquire(self) -> "AtomicPool.Acquire":
            return self.Acquire(self)

        def transaction(self) -> "AtomicPool":
            return self

        async def __aenter__(self) -> "AtomicPool":
            self.depth += 1
            events.append("begin")
            return self

        async def __aexit__(self, exc_type: Any, *_a: Any) -> None:
            events.append("rollback" if exc_type else "commit")
            self.depth -= 1

        async def fetchrow(self, sql: str, *_a: Any) -> Any:
            if "FROM public.appointment" in sql:
                events.append(f"read-appointment-depth-{self.depth}")
                return {"status": "CHECKED_IN"}
            raise AssertionError(sql)

        async def fetchval(self, sql: str, *_a: Any) -> Any:
            if "FROM public.visit" in sql:
                events.append(f"read-visit-depth-{self.depth}")
                return "visit-1"
            raise AssertionError(sql)

    pool = AtomicPool()

    async def close(_self: Any, **_kwargs: Any) -> dict[str, Any]:
        assert pool.depth >= 1
        events.append("close-visit")
        return {"ok": True}

    async def complete(_self: Any, **_kwargs: Any) -> dict[str, Any]:
        assert pool.depth >= 1
        events.append("complete-appointment")
        raise RuntimeError("event log failed")

    monkeypatch.setattr(checkout_service.CheckoutService, "close", close)
    monkeypatch.setattr(booking_service.BookingService, "apply_action", complete)

    with pytest.raises(RuntimeError, match="event log failed"):
        await TuongTacCskhService(pool)._doi_trang_thai_lich(
            identity=_ai(), appointment_id="ap-1", loai="CHECK_OUT"
        )

    assert events == [
        "begin",
        "read-appointment-depth-1",
        "read-visit-depth-1",
        "close-visit",
        "complete-appointment",
        "rollback",
    ]


@pytest.mark.asyncio
async def test_check_out_da_completed_la_noop() -> None:
    """Bấm lại sau response lag không tạo transition hay interaction thứ hai."""
    pool = PoolMotDong({"status": "COMPLETED"})

    da_doi = await TuongTacCskhService(pool)._doi_trang_thai_lich(
        identity=_ai(), appointment_id="ap-1", loai="CHECK_OUT"
    )

    assert da_doi is False
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


def test_checkout_cua_cskh_dong_luon_luot_kham_nhung_khong_override() -> None:
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

    checkout = inspect.getsource(mod.TuongTacCskhService._checkout_atomically)
    assert 'action="complete"' in checkout, "nhánh CHECK_OUT đã đổi hình dạng"
    assert "_dong_luot_kham" in checkout, (
        "CHECK_OUT không còn gọi `_dong_luot_kham` — lịch hẹn sẽ COMPLETED "
        "trong khi dòng `visit` mở vĩnh viễn, và quầy không bao giờ thấy nó "
        "trong danh sách chờ đóng nữa."
    )
    assert "conn.transaction()" in checkout
    assert "_ConnectionBoundPool(conn)" in checkout

    dong = inspect.getsource(mod.TuongTacCskhService._dong_luot_kham)
    assert "CheckoutService" in dong and ".close(" in dong, (
        "`_dong_luot_kham` phải đi qua `CheckoutService.close` — đó là đường "
        "DUY NHẤT dọn đủ ba thứ: đóng bước LUOTKHAM-15, bỏ con trỏ phòng, và "
        "ghi closed_at/closed_by. Tự viết UPDATE ở đây sẽ quên một trong ba."
    )
    assert "override_reason" not in dong, (
        "CSKH không được tự đặt lý do ngoại lệ để vượt thu tiền/lab/workflow"
    )
    assert "except Exception" not in dong, "lỗi đóng lượt không được nuốt"


@pytest.mark.asyncio
async def test_checkout_blocker_dung_truoc_khi_appointment_completed(
    monkeypatch: Any,
) -> None:
    """Nếu đóng visit bị chặn, appointment phải còn CHECKED_IN để quầy xử lý."""
    from clinicai.services import booking_service

    pool = PoolMotDong({"status": "CHECKED_IN"})
    svc = TuongTacCskhService(pool)
    da_complete = False

    async def complete_sai(*_a: Any, **_k: Any) -> None:
        nonlocal da_complete
        da_complete = True

    async def bi_chan(**_k: Any) -> None:
        raise ValidationError("Lượt khám còn việc chưa xong")

    monkeypatch.setattr(booking_service.BookingService, "apply_action", complete_sai)
    monkeypatch.setattr(svc, "_dong_luot_kham", bi_chan)
    with pytest.raises(ValidationError, match="chưa xong"):
        await svc._doi_trang_thai_lich(
            identity=_ai(), appointment_id="ap-1", loai="CHECK_OUT"
        )
    assert da_complete is False


@pytest.mark.asyncio
async def test_zalo_kiem_ownership_appointment_truoc_side_effect(
    monkeypatch: Any,
) -> None:
    """Không gửi giờ hẹn của B vào số điện thoại của A rồi mới báo 422."""
    from clinicai.services import tuong_tac_cskh_service as mod
    from clinicai.services.providers import zalo

    class PoolHaiDong:
        def __init__(self) -> None:
            self.rows = [
                {"full_name": "Lan", "phone_primary": "0989862764"},
                {"slot_start": None, "clinic_patient_id": "bn-khac"},
            ]

        async def fetchrow(self, *_a: Any, **_k: Any) -> Any:
            return self.rows.pop(0)

    da_gui = False

    async def khong_duoc_gui(**_k: Any) -> dict[str, Any]:
        nonlocal da_gui
        da_gui = True
        return {"da_gui": True}

    monkeypatch.setattr(zalo, "gui_zns", khong_duoc_gui)
    monkeypatch.setattr(zalo, "template_cho", lambda _l: "tpl")
    with pytest.raises(ValidationError, match="không phải của khách"):
        await mod.GuiZaloService(PoolHaiDong()).gui(
            identity=_ai(),
            clinic_patient_id=BN,
            appointment_id="a0000000-0000-4000-8000-000000000099",
            loai_tin="NHAC_HEN",
        )
    assert da_gui is False


@pytest.mark.asyncio
async def test_zalo_appointment_dung_khach_gui_xong_moi_ghi_so(
    monkeypatch: Any,
) -> None:
    """Đường thành công giữ đúng lịch, đúng số và chỉ ghi sau khi Zalo nhận."""
    from datetime import datetime, timezone

    from clinicai.services import tuong_tac_cskh_service as mod
    from clinicai.services.providers import zalo

    appointment_id = "a0000000-0000-4000-8000-000000000099"
    events: list[str] = []

    class PoolHaiDong:
        def __init__(self) -> None:
            self.rows = [
                {"full_name": "Lan", "phone_primary": "0989862764"},
                {
                    "slot_start": datetime(2026, 8, 12, 10, 30, tzinfo=timezone.utc),
                    "clinic_patient_id": BN,
                },
            ]

        async def fetchrow(self, *_a: Any, **_k: Any) -> Any:
            return self.rows.pop(0)

    async def gui_zns(**kwargs: Any) -> dict[str, Any]:
        assert kwargs == {
            "sdt": "0989862764",
            "template_id": "tpl-nhac-hen",
            "du_lieu": {"ten": "Lan", "gio_hen": "17:30 12/08"},
            "ma_theo_doi": BN,
        }
        events.append("send")
        return {"da_gui": True, "ly_do": "OK"}

    async def ghi_so(_self: Any, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["clinic_patient_id"] == BN
        assert kwargs["appointment_id"] == appointment_id
        assert kwargs["loai"] == "NHAC_HEN"
        assert kwargs["kenh"] == "ZALO"
        assert kwargs["ket_qua"] == "DA_LIEN_HE"
        events.append("log")
        return {"ok": True, "id": "tuong-tac-1"}

    monkeypatch.setattr(zalo, "gui_zns", gui_zns)
    monkeypatch.setattr(zalo, "template_cho", lambda _l: "tpl-nhac-hen")
    monkeypatch.setattr(mod.TuongTacCskhService, "ghi", ghi_so)

    result = await mod.GuiZaloService(PoolHaiDong()).gui(
        identity=_ai(),
        clinic_patient_id=BN,
        appointment_id=appointment_id,
        loai_tin="NHAC_HEN",
    )

    assert result == {"da_gui": True, "ly_do": "OK"}
    assert events == ["send", "log"]


@pytest.mark.asyncio
async def test_dong_luot_kham_khong_co_visit_thi_bao_ro() -> None:
    """Không có visit không được coi là checkout thành công nửa vời."""
    pool = _ContextPool([None, None])

    with pytest.raises(ValidationError, match="Không tìm thấy lượt khám"):
        await TuongTacCskhService(pool)._dong_luot_kham(
            identity=_ai(), appointment_id="ap-1"
        )


@pytest.mark.asyncio
async def test_dong_luot_kham_sach_di_qua_checkout_khong_override(
    monkeypatch: Any,
) -> None:
    """CSKH dùng chốt chuẩn; không tự chế lý do để vượt blocker."""
    from clinicai.services import checkout_service

    pool = _ContextPool(["visit-1"])
    captured: dict[str, Any] = {}

    async def close(_self: Any, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(checkout_service.CheckoutService, "close", close)
    await TuongTacCskhService(pool)._dong_luot_kham(
        identity=_ai(), appointment_id="ap-1"
    )

    assert captured == {"identity": _ai(), "visit_id": "visit-1"}
    assert "override_reason" not in captured


@pytest.mark.asyncio
async def test_checkout_retry_tu_hoi_phuc_visit_da_dong() -> None:
    """Bản cũ close visit trước: retry phải đi tiếp để complete appointment."""
    pool = _ContextPool([None, "visit-da-dong"])

    await TuongTacCskhService(pool)._dong_luot_kham(
        identity=_ai(), appointment_id="ap-1"
    )

    assert len(pool.executed) == 2


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
