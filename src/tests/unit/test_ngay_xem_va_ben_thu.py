"""Đầu vào ngày / bên thu từ người dùng: rác → None hoặc 422 có câu, KHÔNG 500.

Tuyền 29/09/2026: `/doi-tac` và phòng dịch vụ có thanh chọn ngày (`?ngay=`);
Bảng giá có ô chọn bên thu. CLAUDE.md: hàm nhận ngày giờ từ người dùng phải trả
rỗng thay vì ném, và có test cho đầu vào rác.
"""

from __future__ import annotations

import inspect
from datetime import date, datetime
from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.core.clock import CLINIC_TZ, doc_ngay_xem, hom_nay_vn
from clinicai.services import doi_tac_service
from clinicai.services.config_service import doc_ben_thu


@pytest.mark.parametrize(
    ("vao", "ra"),
    [
        ("2026-09-28", date(2026, 9, 28)),
        (" 2026-09-28 ", date(2026, 9, 28)),
        (date(2026, 9, 1), date(2026, 9, 1)),
        (datetime(2026, 9, 1, 23, 0, tzinfo=CLINIC_TZ), date(2026, 9, 1)),
        ("2030-01-01", date(2030, 1, 1)),  # tương lai: nhận, danh sách rỗng
        (None, None),
        ("", None),
        ("   ", None),
        ("rác", None),
        ("2026-13-01", None),
        ("2026-02-30", None),
        ("20260928", None),
        ("2026-W40-1", None),
        ("2026-09-28T10:00", None),
        ("2019-12-31", None),  # trước khi có dữ liệu
        ("0001-01-01", None),
        (20260928, None),
        (1.5, None),
        (True, None),
        (["2026-09-28"], None),
        ({"ngay": "2026-09-28"}, None),
        ("2026-09-28'; DROP TABLE visit; --", None),
    ],
)
def test_doc_ngay_xem_rac_tra_none(vao: Any, ra: date | None) -> None:
    assert doc_ngay_xem(vao) == ra


def test_hom_nay_vn_la_ngay() -> None:
    assert isinstance(hom_nay_vn(), date)


@pytest.mark.parametrize(
    ("vao", "ra"),
    [
        ("CLINIC", "CLINIC"),
        (" external_partner ", "EXTERNAL_PARTNER"),
        ("", None),
        ("  ", None),
        (None, None),
    ],
)
def test_doc_ben_thu(vao: Any, ra: str | None) -> None:
    assert doc_ben_thu(vao) == ra


@pytest.mark.parametrize("vao", ["PARTNER", "rác", 1, True, ["CLINIC"]])
def test_doc_ben_thu_rac_la_422(vao: Any) -> None:
    with pytest.raises(ValidationError):
        doc_ben_thu(vao)


def test_da_lay_mau_khong_con_khoa_luot() -> None:
    """Đã lấy mẫu ở ngày cũ / lượt đã Hoàn tất (Tuyền 29/09/2026): lệnh không
    được gọi `khoa_luot` (nó chặn FINALIZED / INCOMPLETE)."""
    nguon = inspect.getsource(doi_tac_service.DoiTacService.doi_tac_da_lay_mau)
    assert "khoa_luot(" not in nguon
    assert "partner.sample_noted_again" in nguon
