"""Cửa quyền GIẢ cho bài kiểm dùng connection mock (CORE-B3, 23/09/2026).

Bài kiểm mock đếm từng lần fetch/fetchval, nên cửa quyền thật (`can` đọc
`v_quyen_hieu_luc`) không chạy được ở đó. Thay vì cho qua tất (mất nghĩa của
những bài "vai này bị chặn"), cửa giả này trả lời theo NHÓM MẪU của vai — đúng
bộ quyền một người mới vào vai ấy nhận (`cap_quyen_theo_preset`). Cửa thật có
bài kiểm riêng trên Postgres: `services/test_duong_kham_hoi_quyen_db.py`.
"""

from __future__ import annotations

from typing import Any

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.catalogue import quyen_cua_preset, tra_quyen


async def doi_quyen_theo_nhom_mau(
    _conn: Any,
    identity: StaffIdentity,
    quyen: str,
    *,
    phong_id: str | None = None,
    cau: str | None = None,
) -> None:
    if quyen not in quyen_cua_preset(identity.role.value):
        ten = tra_quyen(quyen).ten
        raise SafetyGateError(cau or f"Bạn không có quyền “{ten}”.")


async def can_theo_nhom_mau(
    _conn: Any,
    identity: StaffIdentity,
    quyen: str,
    *,
    phong_id: str | None = None,
) -> bool:
    """Như `can` thật, trả lời theo nhóm mẫu của vai (xem đầu file)."""
    tra_quyen(quyen)
    return quyen in quyen_cua_preset(identity.role.value)


class PoolGia:
    """Pool giả tối thiểu cho cửa quyền router (`cua_quyen`) — chỉ cần mở được
    một "kết nối" để truyền cho `can` giả; không chạy SQL nào."""

    def acquire(self) -> PoolGia:
        return self

    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_a: object) -> bool:
        return False


def cua_router_theo_nhom_mau(monkeypatch: Any) -> None:
    """Cửa quyền ở ROUTER (`cua_quyen`, `permissions/y_khoa`) trả lời theo nhóm
    mẫu của vai — dùng cho bài kiểm router chạy trên pool giả."""
    monkeypatch.setattr("clinicai.permissions.cua_quyen.can", can_theo_nhom_mau)
    monkeypatch.setattr("clinicai.permissions.y_khoa.can", can_theo_nhom_mau)


def dich_vu_theo_nhom_mau(monkeypatch: Any) -> None:
    """Chỗ hỏi quyền ở TẦNG SERVICE (21 lego, 25/09/2026) trả lời theo nhóm mẫu
    của vai — dùng cho bài kiểm service chạy trên pool giả (FakePool). Cửa thật
    có bài kiểm Postgres: `services/test_lego_21_db.py`."""
    from clinicai.services.clinic_config_service import ClinicConfigService
    from clinicai.services.config_service import RosterService
    from clinicai.services.doi_bac_si_service import DoiBacSiService

    async def _cau_hinh(_self: Any, identity: StaffIdentity) -> None:
        await doi_quyen_theo_nhom_mau(None, identity, "config.clinic.manage")

    async def _xep_lich(_self: Any, identity: StaffIdentity) -> bool:
        return await can_theo_nhom_mau(None, identity, "config.clinic.manage")

    async def _doi_bac_si(_self: Any, identity: StaffIdentity) -> None:
        await doi_quyen_theo_nhom_mau(None, identity, "dispatch.manage")

    monkeypatch.setattr(ClinicConfigService, "_duoc_cau_hinh", _cau_hinh)
    monkeypatch.setattr(RosterService, "_xep_lich", _xep_lich)
    monkeypatch.setattr(DoiBacSiService, "_duoc_doi_bac_si", _doi_bac_si)


def chot_bac_si_theo_nhom_mau(monkeypatch: Any) -> None:
    """Các chốt từng là "chỉ bác sĩ" nay hỏi QUYỀN (28/09/2026 — thư ký, điều
    dưỡng cùng phòng thao tác như bác sĩ): trả lời theo nhóm mẫu của vai cho bài
    kiểm chạy trên pool giả. Cửa thật hỏi `v_quyen_hieu_luc` trên Postgres."""
    for duong in (
        "clinicai.services.service_order_service.can",
        "clinicai.services.tep_ket_qua_service.can",
        "clinicai.services.thai_ky_service.can",
    ):
        monkeypatch.setattr(duong, can_theo_nhom_mau)
    for duong in (
        "clinicai.services.luot_kham_service.doi_quyen",
        "clinicai.services.clinical_sign_service.doi_quyen",
        "clinicai.services.thu_ky_bac_si.doi_quyen",
    ):
        monkeypatch.setattr(duong, doi_quyen_theo_nhom_mau)
    cua_router_theo_nhom_mau(monkeypatch)
