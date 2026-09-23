"""Quy trình nâng cấp sự kiện (docs/CHUAN-CAM-LEGO.md mục 2).

Sổ sự kiện chỉ thêm; đổi hình payload phải đi bằng hàm nâng cấp khi đọc. Các bài
dưới canh ba điều: chuỗi hàm không hở, không có hàm "mồ côi", và người đưa tin
thật sự nâng bản cũ trước khi đưa cho bên nhận.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from clinicai.events import nang_cap
from clinicai.events.catalogue import DANH_MUC, SuKien
from clinicai.events.worker import SuKienDaNhan, nang_len_hien_hanh


def test_chuoi_nang_cap_khong_ho() -> None:
    """Sự kiện version N phải có đủ hàm 1→2→…→N."""
    thieu = [
        f"{ten} v{v}→v{v + 1}"
        for ten, sk in DANH_MUC.items()
        for v in range(1, sk.version)
        if (ten, v) not in nang_cap.NANG_CAP
    ]
    assert not thieu, "Thiếu hàm nâng cấp: " + ", ".join(thieu)


def test_khong_co_ham_nang_cap_mo_coi() -> None:
    """Hàm nâng cấp cho sự kiện không tồn tại / version đã vượt là rác nguy hiểm."""
    mo_coi = [
        f"{ten} v{v}"
        for ten, v in nang_cap.NANG_CAP
        if ten not in DANH_MUC or v >= DANH_MUC[ten].version
    ]
    assert not mo_coi, "Hàm nâng cấp mồ côi: " + ", ".join(mo_coi)


def _su_kien(ten: str, version: int, payload: dict[str, Any]) -> SuKienDaNhan:
    return SuKienDaNhan(
        event_id="e1",
        event_type=ten,
        clinic_id="c1",
        aggregate_id="a1",
        aggregate_version=None,
        occurred_at=None,
        seq=1,
        actor_type="staff",
        actor_staff_id=None,
        payload=payload,
        replay_id=None,
        attempts=1,
        event_version=version,
    )


def test_nguoi_dua_tin_nang_ban_cu_truoc_khi_dua(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Giả lập: `visit.checked_in` lên v2 đổi `so_thu_tu` → `so_quay`. Sự kiện v1
    đã ghi trong sổ phải tới tay bên nhận dưới dạng v2."""
    goc = DANH_MUC["visit.checked_in"]
    monkeypatch.setitem(DANH_MUC, "visit.checked_in", replace(goc, version=2))
    monkeypatch.setattr(nang_cap, "NANG_CAP", dict(nang_cap.NANG_CAP))

    @nang_cap.nang_cap("visit.checked_in", tu=1)
    def _v1_v2(p: dict[str, Any]) -> dict[str, Any]:
        p = dict(p)
        p["so_quay"] = p.pop("so_thu_tu", None)
        return p

    ra = nang_len_hien_hanh(_su_kien("visit.checked_in", 1, {"so_thu_tu": 7}))
    assert ra.event_version == 2
    assert ra.payload == {"so_quay": 7}


def test_thieu_ham_thi_tu_choi_khong_dua_ban_sai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    goc: SuKien = DANH_MUC["visit.checked_in"]
    monkeypatch.setitem(DANH_MUC, "visit.checked_in", replace(goc, version=2))
    monkeypatch.setattr(nang_cap, "NANG_CAP", {})
    with pytest.raises(LookupError, match="Thiếu hàm nâng cấp"):
        nang_len_hien_hanh(_su_kien("visit.checked_in", 1, {}))


def test_so_moi_hon_code_thi_tu_choi() -> None:
    """Deploy lùi: sổ có v5 mà code chỉ biết v1 → không đoán, từ chối."""
    with pytest.raises(ValueError, match="mới hơn code"):
        nang_len_hien_hanh(_su_kien("visit.checked_in", 5, {}))
