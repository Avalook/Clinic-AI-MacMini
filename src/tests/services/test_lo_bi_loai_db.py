"""Quét tem ở quầy thuốc báo SAI lý do (14/10/2026, bấm thật staging).

Đơn kê "gói" mà lô nhập "hộp" thì máy chủ không gợi ý lô ấy (luật cũ, giữ
nguyên); màn quét tem trước đây nói chung chung "không có lô còn bán được".
Nay `lo_bi_loai` nói ĐÚNG lý do (khác đơn vị / khác cơ sở). Test này chỉ khoá
phần giải thích — KHÔNG đổi luật chọn lô: `lo_goi_y` y như cũ.
"""

from __future__ import annotations

from typing import Any

import pytest

# ruff: noqa: F811
from clinicai.services.ban_thuoc_service import (
    LY_DO_LO_KHAC_CO_SO,
    LY_DO_LO_KHAC_DON_VI,
    ly_do_lo_bi_loai,
    man_nha_thuoc,
)
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _dong_da_xac_dinh

pytest_plugins = ["tests.services.test_luot_kham_service_db"]

CO_SO = "co-so-a"


def _lo(co_so: str = CO_SO, unit: str = "viên") -> dict[str, Any]:
    return {"co_so_id": co_so, "unit": unit}


@pytest.mark.parametrize(
    ("lo", "don_vi_ke", "mong_doi"),
    [
        (_lo(), "viên", None),
        # Cùng đơn vị khác hoa/thường, khoảng trắng thừa, dạng Unicode → vẫn cùng.
        (_lo(unit="  Viên "), "viên", None),
        (_lo(unit="hộp"), "viên", LY_DO_LO_KHAC_DON_VI),
        (_lo(unit="hộp"), "gói", LY_DO_LO_KHAC_DON_VI),
        # Đơn thiếu đơn vị: luật cũ KHÔNG lọc theo đơn vị.
        (_lo(unit="hộp"), "", None),
        (_lo(co_so="co-so-b"), "viên", LY_DO_LO_KHAC_CO_SO),
        # Vừa khác cơ sở vừa khác đơn vị: nói cơ sở (luật lọc cơ sở đứng trước).
        (_lo(co_so="co-so-b", unit="hộp"), "viên", LY_DO_LO_KHAC_CO_SO),
        # Đầu vào rác: không ném.
        ({"co_so_id": CO_SO, "unit": None}, "viên", LY_DO_LO_KHAC_DON_VI),
        ({"co_so_id": CO_SO, "unit": None}, "", None),
    ],
)
def test_ly_do_lo_bi_loai_thuan(
    lo: dict[str, Any], don_vi_ke: str, mong_doi: str | None
) -> None:
    assert ly_do_lo_bi_loai(lo, co_so=CO_SO, don_vi_ke=don_vi_ke) == mong_doi


@pytest.mark.db
@pytest.mark.asyncio
async def test_lo_khac_don_vi_khong_goi_y_nhung_co_ly_do(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")
    rx, drug = await _dong_da_xac_dinh(q, 3)  # đơn kê theo "viên"
    lo_hop = await _nhap_lo(q, drug, 20, don_vi="hộp")
    lo_vien = await _nhap_lo(q, drug, 20, don_vi="viên")

    man = await man_nha_thuoc(q.pool, identity=q.duoc_si)
    dong = next(d for v in man["luot"] for d in v["dong"] if d["id"] == rx)

    # Luật chọn lô KHÔNG đổi: chỉ lô cùng đơn vị được gợi ý.
    assert [lo["drug_batch_id"] for lo in dong["lo_goi_y"]] == [lo_vien]
    # Lô "hộp" không được gợi ý và nói rõ vì sao.
    assert len(dong["lo_bi_loai"]) == 1
    bi = dong["lo_bi_loai"][0]
    assert bi["drug_batch_id"] == lo_hop
    assert bi["ly_do"] == LY_DO_LO_KHAC_DON_VI
    assert (bi["don_vi_lo"], bi["don_vi_ke"]) == ("hộp", "viên")
    assert bi["batch_code"]
    # Mỗi lô chỉ nằm ở MỘT nơi.
    assert lo_hop not in {lo["drug_batch_id"] for lo in dong["lo_goi_y"]}


@pytest.mark.db
@pytest.mark.asyncio
async def test_lo_cung_don_vi_khong_co_trong_lo_bi_loai(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")
    rx, drug = await _dong_da_xac_dinh(q, 3)
    lo_vien = await _nhap_lo(q, drug, 20, don_vi="viên")

    man = await man_nha_thuoc(q.pool, identity=q.duoc_si)
    dong = next(d for v in man["luot"] for d in v["dong"] if d["id"] == rx)

    assert [lo["drug_batch_id"] for lo in dong["lo_goi_y"]] == [lo_vien]
    assert dong["lo_bi_loai"] == []
