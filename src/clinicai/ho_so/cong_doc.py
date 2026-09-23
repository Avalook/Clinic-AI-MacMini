"""Ráp HỒ SƠ KHÁM từ CỔNG ĐỌC của từng module (cách B — Tuyền chốt 24/09/2026).

VÌ SAO. Trước đây một hàm hồ sơ tự JOIN thẳng vào bảng của 6–7 module (bệnh án,
đơn thuốc, sinh hiệu, xét nghiệm, thai kỳ…). Nó biết ruột của từng module, nên
thêm một module là phải sửa hàm hồ sơ — đúng kiểu "đào sâu" mà lego muốn tránh.

BÂY GIỜ. Mỗi module khai trong `modules.py` (mục `cong_doc`) một hàm đọc nằm
cạnh bảng của chính nó: "tôi góp phần này vào hồ sơ, điền những khoá này". Hồ sơ
chỉ làm hai việc: chọn LƯỢT nào (bối cảnh) rồi đi qua danh sách cổng đã khai.
Thêm module = khai thêm một cổng; hồ sơ không đổi.

VÌ SAO KHÔNG DỰNG TỪ SỰ KIỆN (cách A). Đọc lúc mở nên luôn mới — bác sĩ vừa lưu
là thấy; không lưu dữ liệu y khoa hai lần; không cần phát lại sổ sự kiện khi
sai. Cái giá: mỗi lần mở chạy vài câu SQL nhỏ, tuần tự trên MỘT kết nối — ở quy
mô này (~1 lượt gọi/giây) không đáng kể.

LUẬT CỔNG (bài kiểm `test_o_cam_module` canh):
  * cổng chỉ ĐỌC, và chỉ điền đúng các khoá nó khai — điền khoá lạ là lỗi;
  * hai cổng không giành cùng một khoá;
  * cổng khai trong bản khai phải trỏ tới hàm có thật.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity


@dataclass(frozen=True)
class NguCanhHoSo:
    """Bối cảnh chung mọi cổng nhận: của ai, lượt nào, ai đang đọc."""

    identity: StaffIdentity
    clinic_id: str
    khach: str
    visit_id: str | None = None
    appointment_id: str | None = None


HamCong = Callable[[asyncpg.Connection, NguCanhHoSo], Awaitable[dict[str, Any]]]


def dong(
    r: asyncpg.Record | None, cot_json: Iterable[str] = ()
) -> dict[str, Any] | None:
    """Một dòng → dict sẵn trả JSON: giải cột jsonb (CHỈ cột khai), ngày → ISO."""
    if r is None:
        return None
    json_cot = set(cot_json)
    ra: dict[str, Any] = {}
    for k, v in dict(r).items():
        if k in json_cot and isinstance(v, str):
            try:
                v = json.loads(v)
            except ValueError:
                pass
        elif isinstance(v, (datetime, date)):
            v = v.isoformat()
        ra[k] = v
    return ra


def nap_ham(duong: str) -> HamCong:
    """ "goi.module:ten_ham" → hàm. Sai tên thì hỏng ngay (bài kiểm bắt)."""
    goi, _, ten = duong.partition(":")
    ham = getattr(importlib.import_module(goi), ten)
    if not callable(ham):
        raise TypeError(f"{duong} không phải hàm")
    return ham  # type: ignore[no-any-return]


def cac_cong() -> list[tuple[str, str, tuple[str, ...], str]]:
    """(module, tên cổng, khoá, đường hàm) theo thứ tự khai trong bản khai."""
    from clinicai.modules import MODULE

    return [
        (m.ma, c.ten, tuple(c.khoa), c.ham) for m in MODULE.values() for c in m.cong_doc
    ]


async def ghep_ho_so(conn: asyncpg.Connection, ngu_canh: NguCanhHoSo) -> dict[str, Any]:
    """Đi qua mọi cổng đã khai, ráp phần của từng module thành một hồ sơ."""
    ho_so: dict[str, Any] = {}
    for module, ten, khoa, duong in cac_cong():
        phan = await nap_ham(duong)(conn, ngu_canh)
        la = set(phan) - set(khoa)
        if la:
            raise RuntimeError(f"Cổng {module}/{ten} điền khoá chưa khai: {sorted(la)}")
        ho_so.update(phan)
    return ho_so


__all__ = ["NguCanhHoSo", "cac_cong", "dong", "ghep_ho_so", "nap_ham"]
