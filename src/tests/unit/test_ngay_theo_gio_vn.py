"""'Hôm nay' phải là ngày giờ VIỆT NAM, không phải đồng hồ máy chủ.

VÌ SAO CÓ BÀI NÀY. Container API chạy UTC (chỉ Postgres ghim TZ trong
docker-compose). `date.today()` trong Python nên từ 0h đến 7h sáng giờ VN trả ngày
HÔM QUA: `/queue` không kèm ngày đọc nhầm hàng chờ hôm trước, luật sức chứa mới
có hiệu lực từ hôm qua. Bản đồ code đọc kỹ 21/10/2026 bắt được.

`CURRENT_DATE` của Postgres theo múi giờ phiên kết nối — hôm nay đúng vì container
DB ghim TZ, nhưng là may chứ không phải luật. ~95 chỗ SQL khác đã viết rõ
`(now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date`; giờ là mọi chỗ.

Dùng `clinicai.core.clock.hom_nay_vn()` trong Python.
"""

from __future__ import annotations

import re
from pathlib import Path

_GOC = Path(__file__).resolve().parents[2] / "clinicai"
_CAM = re.compile(r"\b(?:date|date_cls)\.today\(\)|\bCURRENT_DATE\b")


def test_khong_dung_ngay_cua_dong_ho_may_chu() -> None:
    sai = []
    for f in sorted(_GOC.rglob("*.py")):
        for i, dong in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            code = dong.split("#", 1)[0]
            if _CAM.search(code):
                sai.append(f"{f.relative_to(_GOC)}:{i}: {dong.strip()}")
    assert not sai, (
        "Lấy 'hôm nay' theo đồng hồ máy chủ (UTC → lệch ngày 0h–7h sáng giờ VN). "
        "Python dùng hom_nay_vn(); SQL dùng (now() AT TIME ZONE "
        "'Asia/Ho_Chi_Minh')::date:\n" + "\n".join(sai)
    )
