"""Đọc DÂY NỐI NGHIỆP VỤ — giá trị quản lý chỉnh trên màn (nhóm 5, 24/09/2026).

Module NHẸ, cố ý: khối Hành trình, khối Điều phối… đọc dây ở đây mà không kéo cả
service quản trị vào (tránh vòng import). Ghi dây: `day_noi_service.py`.

Tuyền chốt: "Đường nối H1–H8 phải CUSTOM được". Chia dây: NGHIỆP VỤ (ở đây, chỉnh
trên màn) / LÕI (dòng thời gian, trách nhiệm tiền — khoá trong code).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import asyncpg


@dataclass(frozen=True)
class Day:
    ma: str
    nhan: str
    mac_dinh: Any
    kieu: str  # "bat_tat" | "so"
    nho_nhat: int = 0
    lon_nhat: int = 0
    don_vi: str = ""


DAY: dict[str, Day] = {
    d.ma: d
    for d in (
        Day(
            "h1_khach_quen_vao_thang_bs",
            "Khách quen của bác sĩ chính (tái khám / từng được bác sĩ ấy khám)"
            " → vào thẳng bác sĩ chính, không qua tư vấn",
            # TẮT từ 25/09/2026 (Tuyền: "cứ qua bác sĩ tư vấn như bình thường,
            # nào điều dưỡng ấn bỏ qua thì vào bác sĩ chính luôn"). Cũ thì OFF,
            # không xoá — quản lý bật lại được ở Cài đặt → Dây nối.
            False,
            "bat_tat",
        ),
        Day(
            "h4_tu_xep_phong",
            "Thu tiền dịch vụ xong → tự xếp phòng vắng nhất (thay người vừa thu)",
            True,
            "bat_tat",
        ),
        Day(
            "h6_bao_cskh_khi_ve_con_viec",
            "Khách về mà còn việc dở (kết quả chưa về / chưa ai xem) → báo CSKH",
            True,
            "bat_tat",
        ),
        Day(
            "h7_ket_qua_doi_tac_qua_han_ngay",
            "Kết quả đối tác quá bao nhiêu ngày chưa về → báo CSKH",
            3,
            "so",
            1,
            60,
            "ngày",
        ),
        Day(
            "h8_nhac_check_out_phut",
            "Trả tiền xong bao lâu chưa check-out → nhắc lễ tân (0 = tắt)",
            60,
            "so",
            0,
            600,
            "phút",
        ),
    )
}


async def doc_day(conn: asyncpg.Connection, clinic_id: str, ma: str) -> Any:
    """Giá trị hiện hành của một dây; phòng khám chưa chỉnh thì mặc định."""
    day = DAY[ma]
    gia_tri = await conn.fetchval(
        "SELECT gia_tri FROM day_nghiep_vu WHERE clinic_id = $1::uuid AND ma = $2",
        clinic_id,
        ma,
    )
    if gia_tri is None:
        return day.mac_dinh
    v = json.loads(gia_tri) if isinstance(gia_tri, str) else gia_tri
    if day.kieu == "bat_tat":
        return bool(v)
    try:
        return int(v)
    except (TypeError, ValueError):
        return day.mac_dinh


__all__ = ["DAY", "Day", "doc_day"]
