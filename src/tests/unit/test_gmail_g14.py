"""Gmail G14 (Tuyền 12/11/2026) — tự gán khi SĐT trên phiếu lệch hồ sơ: tên trùng
nguyên + năm sinh trùng + cả phòng khám chỉ một khách tên đó + khách có chỉ định lab.
Thiếu một điều kiện ⇒ không tự gán (người gán như cũ). Dữ liệu GIẢ."""

from __future__ import annotations

import pytest

from clinicai.services.xet_nghiem.ghep_khach import UngVien
from clinicai.services.xet_nghiem.gmail_doc import DocThu
from clinicai.services.xet_nghiem.gmail_ghep import khop_ten_nam_sinh

TEN = "PHẠM THUỴ MẪU THỬ"  # phiếu: dấu đặt kiểu "uỵ"
SDT_PHIEU = "0900000188"


def _v(kh: str, ten: str = "Phạm Thụy Mẫu Thử", ns: int | None = 1983) -> UngVien:
    return UngVien(f"o-{kh}", kh, "visit", ten, "0900000177", nam_sinh=ns)


_D = DocThu("GLHD", TEN, SDT_PHIEU, 1983)


@pytest.mark.parametrize(
    ("d", "viec", "so_cung_ten", "ra"),
    [
        # Tên (khác chỗ đặt dấu) + năm sinh khớp, duy nhất, SĐT lệch ⇒ tự gán.
        (_D, [_v("k1")], 1, "k1"),
        # Hai chỉ định của CÙNG khách ⇒ vẫn là một khách (chọn chỉ định là bước sau).
        (_D, [_v("k1"), _v("k1")], 1, "k1"),
        # Cả phòng khám có 2 khách trùng tên ⇒ không tự gán.
        (_D, [_v("k1")], 2, None),
        # Không có hồ sơ nào tên đó (đếm 0) ⇒ không.
        (_D, [_v("k1")], 0, None),
        # Năm sinh lệch / hồ sơ thiếu năm sinh ⇒ không.
        (_D, [_v("k1", ns=1984)], 1, None),
        (_D, [_v("k1", ns=None)], 1, None),
        # Phiếu không có năm sinh ⇒ không.
        (DocThu("GLHD", TEN, SDT_PHIEU, None), [_v("k1")], 1, None),
        # Tên chỉ GẦN giống (thiếu tên đệm) ⇒ không — đó là việc của gợi ý G9.
        (_D, [_v("k1", ten="Phạm Mẫu Thử")], 1, None),
        # Khách không có chỉ định của lab (không trong `viec`) ⇒ không.
        (_D, [], 1, None),
        # Hai khách khác nhau cùng tên + năm sinh trong ứng viên ⇒ không đoán.
        (_D, [_v("k1"), _v("k2")], 1, None),
    ],
)
def test_khop_ten_nam_sinh(
    d: DocThu, viec: list[UngVien], so_cung_ten: int, ra: str | None
) -> None:
    assert khop_ten_nam_sinh(d, viec, so_cung_ten) == ra
