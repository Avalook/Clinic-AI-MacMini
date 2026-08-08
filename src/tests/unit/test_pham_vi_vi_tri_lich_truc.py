"""Lễ tân không được xếp vào bàn khám của bác sĩ.

Quang, 08/08/2026: *"đã chọn nhân viên rồi thì vị trí chỉ ở phạm vi của họ chứ
không chọn sang khả năng của người khác được, ví dụ lễ tân chỉ chọn được lịch
làm việc và vị trí của lễ tân, không vào bác sĩ được."*

VÌ SAO KIỂM Ở ĐÂY CHỨ KHÔNG PHẢI Ở GIAO DIỆN. Bản cũ lọc bằng
`stationsForRole` trong trình duyệt. Một lời gọi API tự chế không đi qua trình
duyệt — và `RosterService.add_shift` khi đó không đọc chức danh của người được
xếp lấy một lần, nên nó nhận tất.

Ba nhánh phải giữ:
  · trong phạm vi   → cho qua
  · ngoài phạm vi   → từ chối, và NÓI RA vị trí nào hợp lệ
  · chưa khai gì    → CHO QUA (phòng khám mới cài chưa có ma trận; khoá sạch
                      màn xếp lịch ngay ngày đầu là hỏng nặng hơn bỏ sót)
"""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.config_service import RosterService

CLINIC = "a0000000-0000-4000-8000-000000000001"


def _ai(role: ClinicRole) -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="Người Gọi",
        department=role.value,
        role=role,
        clinic_id=CLINIC,
        location_id="l1",
        location_name="Kim Ngưu",
    )


class FakePool:
    """Pool tối giản: trả lần lượt các kết quả đã dọn sẵn, ghi lại lời gọi."""

    def __init__(self, *ket_qua: Any) -> None:
        self._kq = list(ket_qua)
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def _lay(self) -> Any:
        return self._kq.pop(0) if self._kq else None

    async def fetch(self, sql: str, *args: Any) -> Any:
        self.calls.append((sql, args))
        kq = self._lay()
        return kq if kq is not None else []

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        self.calls.append((sql, args))
        return self._lay()

    async def execute(self, sql: str, *args: Any) -> None:
        self.calls.append((sql, args))

    def acquire(self) -> "FakePool":
        return self

    async def __aenter__(self) -> "FakePool":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


class FakeConn:
    """Chỉ trả về ma trận vị trí — đúng phần `_kiem_pham_vi_tram` hỏi tới."""

    def __init__(self, tram: list[str]) -> None:
        self._tram = tram

    async def fetch(self, *_args: Any, **_kwargs: Any) -> list[dict[str, str]]:
        return [{"tram_ma": t} for t in self._tram]


def _service() -> RosterService:
    # Pool không được đụng tới trong nhánh này; truyền None qua cast cho gọn.
    return RosterService(None)


@pytest.mark.asyncio
async def test_trong_pham_vi_thi_cho_qua() -> None:
    await _service()._kiem_pham_vi_tram(
        FakeConn(["LE_TAN", "LAY_MAU"]),
        clinic_id=CLINIC,
        station="LAY_MAU",
        vai="RECEPTION",
        ten="Hải Yến",
    )


@pytest.mark.asyncio
async def test_le_tan_khong_vao_ban_kham_bac_si() -> None:
    with pytest.raises(ValidationError) as e:
        await _service()._kiem_pham_vi_tram(
            FakeConn(["LE_TAN", "LAY_MAU", "PHU_BS_KHAM"]),
            clinic_id=CLINIC,
            station="LICH_KHAM",
            vai="RECEPTION",
            ten="Hải Yến",
        )
    loi = str(e.value)
    assert "Hải Yến" in loi
    # Từ chối mà không nói được phép làm gì thì người dùng phải đoán. Liệt kê ra.
    assert "LAY_MAU" in loi and "LE_TAN" in loi


@pytest.mark.asyncio
async def test_chua_khai_ma_tran_thi_cho_qua() -> None:
    """Fail-open có chủ ý — xem chú thích ở đầu file."""
    await _service()._kiem_pham_vi_tram(
        FakeConn([]),
        clinic_id=CLINIC,
        station="LICH_KHAM",
        vai="RECEPTION",
        ten="Hải Yến",
    )


@pytest.mark.asyncio
async def test_man_hinh_phong_cho_khong_phai_nguoi() -> None:
    """DISPLAY là cái tivi treo tường; nhánh fail-open sẽ cho nó qua nếu không chặn."""
    with pytest.raises(ValidationError):
        await _service()._kiem_pham_vi_tram(
            FakeConn([]),
            clinic_id=CLINIC,
            station="LE_TAN",
            vai="DISPLAY",
            ten="TV phòng chờ",
        )


# ── Ô chọn trên màn xếp lịch hỏi cùng một nguồn với chỗ từ chối ─────────────


@pytest.mark.asyncio
async def test_tram_cho_nhan_vien_tra_dung_pham_vi() -> None:
    pool = FakePool(
        {"full_name": "Hải Yến", "primary_department": "RECEPTION"},
        [{"tram_ma": "LAY_MAU"}, {"tram_ma": "LE_TAN"}],
    )
    d = await RosterService(pool).tram_cho_nhan_vien(
        identity=_ai(ClinicRole.MANAGEMENT), staff_id="s9"
    )
    assert d["vai"] == "RECEPTION"
    assert d["tram"] == ["LAY_MAU", "LE_TAN"]
    assert d["chua_khai"] is False


@pytest.mark.asyncio
async def test_chua_khai_khac_han_khong_duoc_di_dau() -> None:
    """Danh sách rỗng có hai nghĩa; cờ `chua_khai` tách chúng ra.

    Không tách thì giao diện đọc "phòng khám chưa cấu hình" thành "người này
    không làm được việc gì", rồi ẩn sạch ô chọn.
    """
    pool = FakePool({"full_name": "A", "primary_department": "PHARMACIST"}, [])
    d = await RosterService(pool).tram_cho_nhan_vien(
        identity=_ai(ClinicRole.MANAGEMENT), staff_id="s9"
    )
    assert d["chua_khai"] is True and d["tram"] == []


@pytest.mark.asyncio
async def test_nguoi_phong_kham_khac_thi_khong_thay() -> None:
    pool = FakePool(None)
    with pytest.raises(NotFoundError):
        await RosterService(pool).tram_cho_nhan_vien(
            identity=_ai(ClinicRole.MANAGEMENT), staff_id="nguoi-la"
        )


# ── Màn cấu hình ma trận ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chi_quan_ly_sua_duoc_ma_tran() -> None:
    with pytest.raises(SafetyGateError):
        await RosterService(FakePool()).dat_vi_tri_cho_vai(
            identity=_ai(ClinicRole.TRUONG_CA),
            tram_ma="LICH_KHAM",
            vai="RECEPTION",
            cho_phep=True,
        )


@pytest.mark.asyncio
async def test_tat_mot_o_thi_giu_dong_lai() -> None:
    """Tắt = is_active false, KHÔNG xoá dòng.

    Một ô từng bật rồi tắt là một quyết định. Xoá đi thì lần rà sau có người
    bật lại và không ai biết trước đó nó đã bị tắt có chủ ý.
    """
    pool = FakePool()
    await RosterService(pool).dat_vi_tri_cho_vai(
        identity=_ai(ClinicRole.MANAGEMENT),
        tram_ma="LICH_KHAM",
        vai="RECEPTION",
        cho_phep=False,
    )
    sql, args = pool.calls[0]
    assert "INSERT" in sql and "DELETE" not in sql
    assert False in args


@pytest.mark.asyncio
async def test_khong_khai_duoc_cho_man_hinh_phong_cho() -> None:
    with pytest.raises(ValidationError):
        await RosterService(FakePool()).dat_vi_tri_cho_vai(
            identity=_ai(ClinicRole.MANAGEMENT),
            tram_ma="LE_TAN",
            vai="DISPLAY",
            cho_phep=True,
        )


@pytest.mark.asyncio
async def test_ma_tran_doc_ca_dong_da_tat() -> None:
    """Dòng đã tắt vẫn phải trả về — màn cấu hình cần vẽ ô chưa tích."""
    pool = FakePool(
        [{"tram_ma": "LE_TAN", "vai": "CSKH", "is_active": False, "ghi_chu": None}]
    )
    rows = await RosterService(pool).ma_tran_vi_tri(identity=_ai(ClinicRole.MANAGEMENT))
    assert rows[0]["is_active"] is False
