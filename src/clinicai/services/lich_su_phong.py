"""LỊCH SỬ XẾP / ĐỔI PHÒNG của từng chỉ định (Tuyền 29/09/2026).

"Quầy thu vẫn đổi được phòng trưởng ca đã xếp — nhưng mọi lần xếp / đổi phải
hiện LỊCH SỬ trong Hành trình khách": giờ · ai (quầy thu / trưởng ca / tự động)
· phòng A → B · lý do nếu có.

CHỈ ĐỌC sổ sự kiện (`domain_event`) — hai loại: `service.routed` (mọi lần xếp /
đổi phòng chính thức, có `nguon`) và `service.room_transferred` (trưởng ca
chuyển khi dịch vụ đang làm, có lý do chữ). Không bảng mới, không luật mới.
Câu hiển thị dựng ở đây (hàm thuần `dong_lich_su`) — màn chỉ vẽ.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import asyncpg

LOAI_LICH_SU = ("service.routed", "service.room_transferred")

#: Ai / từ màn nào — theo `nguon` của sự kiện.
TEN_NGUON = {
    "quay_thu": "Quầy thu",
    "truong_ca": "Trưởng ca",
    "tu_dong": "Tự động",
    "khac": "Nhân viên",
}

#: Mã lý do xếp phòng (`service.routed.ly_do`) → chữ.
TEN_LY_DO = {
    "INITIAL_ASSIGNMENT": None,  # lần xếp đầu: không cần nói lý do
    "LOAD_BALANCE": "cân tải",
    "ROOM_UNAVAILABLE": "phòng không dùng được",
    "STAFF_UNAVAILABLE": "không có người làm",
    "EQUIPMENT_FAILURE": "hỏng máy",
    "PATIENT_NEED": "theo nhu cầu khách",
    "MANUAL_CORRECTION": None,  # đổi tay ở quầy / điều phối: không có lý do riêng
    "OTHER": "lý do khác",
}


def dong_lich_su(
    *,
    loai: str,
    payload: dict[str, Any],
    ten_phong: dict[str, str],
    luc: datetime | None,
    ai: str | None,
) -> dict[str, Any]:
    """Một dòng lịch sử — HÀM THUẦN. Payload thiếu trường / rác vẫn ra một dòng
    đọc được (không ném)."""
    p = payload if isinstance(payload, dict) else {}
    tu = p.get("from_room_id")
    den = p.get("room_id")
    tu_phong = ten_phong.get(str(tu)) if tu else None
    den_phong = ten_phong.get(str(den)) if den else None
    nguon = p.get("nguon") if isinstance(p.get("nguon"), str) else None
    if loai == "service.room_transferred":
        nguon = nguon or "truong_ca"
        viec = "chuyển phòng khi đang làm"
        ly_do = p.get("ly_do") if isinstance(p.get("ly_do"), str) else None
    else:
        if p.get("tu_dong") and not nguon:
            nguon = "tu_dong"
        viec = "đổi phòng" if tu else "xếp phòng"
        ma = p.get("ly_do")
        ly_do = TEN_LY_DO.get(ma, ma) if isinstance(ma, str) else None
        du_kien = p.get("du_kien_nguon")
        if nguon == "tu_dong" and du_kien in ("quay_thu", "truong_ca"):
            ly_do = f"theo phòng {TEN_NGUON[du_kien].lower()} chọn trước"
    ten_nguon = TEN_NGUON.get(nguon or "", "Nhân viên")
    phong = f"{tu_phong or '—'} → {den_phong or '—'}" if tu else f"→ {den_phong or '—'}"
    cau = f"{ten_nguon} {viec} {phong}"
    if ly_do:
        cau += f": {ly_do}"
    return {
        "luc": luc,
        "loai": loai,
        "nguon": nguon,
        "ten_nguon": ten_nguon,
        "ai": ai,
        "tu_phong": tu_phong,
        "den_phong": den_phong,
        "ly_do": ly_do,
        "cau": cau,
    }


async def lich_su_phong_cua_luot(
    conn: asyncpg.Connection, *, clinic_id: str, visit_id: str
) -> dict[str, list[dict[str, Any]]]:
    """{mã chỉ định: [dòng lịch sử, cũ → mới]} của một lượt. Hai câu SQL."""
    rows = await conn.fetch(
        """
        SELECT e.aggregate_id::text AS order_id, e.event_type, e.occurred_at,
               e.payload, s.full_name AS ai
          FROM domain_event e
          LEFT JOIN staff s ON s.id = e.actor_staff_id
         WHERE e.clinic_id = $1::uuid
           AND e.aggregate_type = 'service_order'
           AND e.event_type = ANY($3::text[])
           AND e.aggregate_id IN (
               SELECT o.id FROM service_order o
                WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid)
         ORDER BY e.occurred_at, e.seq
        """,
        clinic_id,
        visit_id,
        list(LOAI_LICH_SU),
    )
    tai: list[tuple[str, str, datetime, dict[str, Any], str | None]] = []
    phong_ids: set[str] = set()
    for r in rows:
        p = r["payload"]
        if isinstance(p, str):
            p = json.loads(p)
        p = p if isinstance(p, dict) else {}
        for k in ("from_room_id", "room_id"):
            if p.get(k):
                phong_ids.add(str(p[k]))
        tai.append((r["order_id"], r["event_type"], r["occurred_at"], p, r["ai"]))
    ten: dict[str, str] = {}
    if phong_ids:
        ten = {
            r["id"]: r["name"]
            for r in await conn.fetch(
                "SELECT id::text AS id, name FROM clinic_room"
                " WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])",
                clinic_id,
                sorted(phong_ids),
            )
        }
    ra: dict[str, list[dict[str, Any]]] = {}
    for oid, loai, luc, p, ai in tai:
        ra.setdefault(oid, []).append(
            dong_lich_su(loai=loai, payload=p, ten_phong=ten, luc=luc, ai=ai)
        )
    return ra


__all__ = ["LOAI_LICH_SU", "dong_lich_su", "lich_su_phong_cua_luot"]
