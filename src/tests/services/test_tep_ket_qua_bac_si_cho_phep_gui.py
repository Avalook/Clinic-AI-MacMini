"""Tệp kết quả: bác sĩ cho phép gửi — nay KHÔNG còn là cửa (Tuyền chốt 23/09/2026).

Luật 15/09 "bác sĩ cho phép trước rồi CSKH mới gửi" đã TẮT (migration
20260923000021): "cứ open đi, cho gửi cũng được". Nút cho phép của bác sĩ còn
giữ (ghi vết), nhưng CSKH gửi được ngay. Tệp của ĐỐI TÁC vẫn phải xác nhận
đúng người, đúng chỉ định (HOP_LE) mới gửi được.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from tests.quyen_gia import PoolGia, chot_bac_si_theo_nhom_mau

TEP = "33333333-3333-4333-8333-333333333333"


def _identity(role: ClinicRole) -> StaffIdentity:
    return StaffIdentity(
        staff_id="11111111-1111-4111-8111-111111111111",
        auth_user_id="u1",
        full_name="x",
        department=role.value,
        role=role,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


@pytest.mark.parametrize("role", [ClinicRole.CSKH, ClinicRole.RECEPTION])
def test_khong_co_quyen_duyet_kq_thi_khong_cho_phep_gui(
    role: ClinicRole, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 28/09/2026: hỏi QUYỀN duyệt kết quả, không hỏi vai.
    chot_bac_si_theo_nhom_mau(monkeypatch)
    with pytest.raises(SafetyGateError):
        asyncio.run(
            TepKetQuaService(PoolGia()).cho_phep_gui(  # type: ignore[arg-type]
                identity=_identity(role), tep_id=TEP
            )
        )


class _Pool:
    def __init__(self, xac_nhan: str | None) -> None:
        self.xac_nhan = xac_nhan

    # Đánh dấu đã gửi chạy trong MỘT giao dịch và phát sự kiện (nhóm 3):
    # pool giả đóng vai luôn kết nối.
    def acquire(self) -> "_Pool":
        return self

    def transaction(self) -> "_Pool":
        return self

    async def __aenter__(self) -> "_Pool":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, *_: Any) -> None:
        return None

    async def executemany(self, *_: Any) -> None:
        return None

    async def fetchval(self, *_: Any) -> None:
        return None

    async def fetchrow(self, sql: str, *_: Any) -> dict[str, Any] | None:
        if sql.lstrip().startswith("UPDATE"):
            return {"id": TEP, "service_order_id": None, "appointment_id": None}
        return {
            "gui_luc": None,
            "cho_phep_gui_luc": None,
            "xac_nhan_trang_thai": self.xac_nhan,
        }


def test_chua_cho_phep_cskh_van_danh_dau_da_gui_duoc() -> None:
    kq = asyncio.run(
        TepKetQuaService(_Pool(None)).danh_dau_da_gui(
            identity=_identity(ClinicRole.CSKH), tep_id=TEP, kenh="ZALO"
        )
    )
    assert kq == {"ok": True}


def test_tep_doi_tac_chua_xac_nhan_dung_nguoi_van_bi_chan() -> None:
    with pytest.raises(ConflictError, match="chưa ở trạng thái hợp lệ"):
        asyncio.run(
            TepKetQuaService(_Pool("CHO_XAC_NHAN")).danh_dau_da_gui(
                identity=_identity(ClinicRole.CSKH), tep_id=TEP, kenh="ZALO"
            )
        )


def test_cau_update_da_gui_khong_con_doi_cho_phep() -> None:
    ma = inspect.getsource(TepKetQuaService.danh_dau_da_gui)
    dau = ma.index("UPDATE public.tep_ket_qua")
    assert "cho_phep_gui_luc IS NOT NULL" not in ma[dau : ma.index('"""', dau)]
