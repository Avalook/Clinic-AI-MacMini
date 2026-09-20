"""Kế hoạch lưu đơn theo mức dấu vết — hàm thuần (CP6 bước 4b, 20/09/2026)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from clinicai.services import ban_thuoc_service as bt
from clinicai.services.dinh_chinh_don import lap_ke_hoach


def _i(rx: str | None, ten: str, sl: str, lieu: str | None = None) -> dict[str, Any]:
    return {"id": rx, "drug_name": ten, "quantity": sl, "dosage": lieu}


def _cu(rx: str, muc: int, ten: str = "A", sl: str = "10 viên") -> dict[str, Any]:
    return {
        "id": rx,
        "drug_name_raw": ten,
        "quantity": sl,
        "dosage_instructions": "S1",
        "caution": None,
        "muc": muc,
    }


@pytest.mark.parametrize(
    ("muc", "gui", "viec"),
    [
        (0, _i("r", "A", "10 viên", "T2"), "sua_huong_dan"),
        (0, _i("r", "B", "10 viên", "S1"), "sua_thuoc"),
        (1, _i("r", "A", "10 viên", "T2"), "sua_huong_dan"),
        (1, _i("r", "A", "5 viên", "S1"), "thay"),
        (2, _i("r", "A", "10 viên", "T2"), "thay"),
        (2, _i("r", "a ", " 10  VIÊN", "S1"), None),  # khác hoa/khoảng trắng
    ],
)
def test_ke_hoach_theo_muc(muc: int, gui: dict[str, Any], viec: str | None) -> None:
    kh = lap_ke_hoach([_cu("r", muc)], [gui])
    lam = [k for k in ("sua_huong_dan", "sua_thuoc", "thay") if getattr(kh, k)]
    assert lam == ([viec] if viec else [])
    assert kh.can_dinh_chinh == (viec == "thay")


@pytest.mark.parametrize(("muc", "viec"), [(0, "xoa"), (1, "bo"), (2, "bo")])
def test_ke_hoach_bo_dong(muc: int, viec: str) -> None:
    kh = lap_ke_hoach([_cu("r", muc)], [])
    assert getattr(kh, viec) and kh.can_dinh_chinh == (viec == "bo")


def test_thao_tac_dong_lich_su_chi_con_huy_chua_giao() -> None:
    chung: dict[str, Any] = {
        "gd": bt.SAN_SANG,
        "dong_da_chot": False,
        "da_giao": Decimal(0),
        "co_thuoc_kho": True,
        "co_don_vi": True,
        "co_so_ke": True,
        "can_lo": Decimal(10),
        "da_chon": Decimal(0),
        "co_phan_lo": False,
        "so_ban": Decimal(10),
    }
    assert any(bt.thao_tac_dong(**chung).values())
    assert not any(bt.thao_tac_dong(**chung, lich_su=True).values())
    ls = bt.thao_tac_dong(
        **{**chung, "gd": bt.DA_THU},
        chua_giao=Decimal(3),
        lich_su=True,
    )
    assert [k for k, v in ls.items() if v] == ["huy_chua_giao"]
