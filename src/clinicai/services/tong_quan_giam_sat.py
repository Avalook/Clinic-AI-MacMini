"""TỔNG QUAN GIÁM SÁT — một lượt gọi cho cả dashboard Agent (09/10/2026).

Tuyền: "cần một cái có thể nhìn tổng quan mọi thứ". Màn gọi MỘT lần (Luật 5.1:
gộp, không bắn tám lượt), nhận đủ bốn mảng:

    van_hanh   khách hôm nay / đang trong phòng khám / đang chờ / chờ lâu nhất,
               và số check-in theo từng giờ
    phong      tải từng phòng (cùng nguồn màn Trưởng ca — DispatchService)
    he_thong   đèn trạng thái: người đưa tin sự kiện, lỗi mới, cảnh báo hạ tầng
    agent      nhận định đang mở theo mức + vòng chạy gần nhất

Chỉ ĐỌC. Không tên khách — đếm và mã phòng là đủ để nhìn toàn cảnh.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.v1.health import danh_gia_su_kien, do_su_kien
from clinicai.services.dispatch_service import DispatchService

_KHACH_DANG_CHO = "DANG_CHO"
_KHACH_DANG_LAM = ("DANG_LAM", "DA_GOI")

_DAU_NGAY = (
    "(date_trunc('day', now() AT TIME ZONE 'Asia/Ho_Chi_Minh')"
    " AT TIME ZONE 'Asia/Ho_Chi_Minh')"
)


def van_hanh_tu_dieu_phoi(patients: list[dict[str, Any]]) -> dict[str, Any]:
    """HÀM THUẦN: từ danh sách khách đang trong phòng khám → các con số."""
    dang_cho = dang_lam = qua_nguong = 0
    cho_lau_nhat = 0
    for p in patients:
        if not isinstance(p, dict):
            continue
        nhan = p.get("trang_thai")
        ma = nhan.get("ma") if isinstance(nhan, dict) else None
        w = p.get("wait_minutes")
        w = w if isinstance(w, int) and not isinstance(w, bool) else 0
        nguong = p.get("threshold_minutes")
        nguong = nguong if isinstance(nguong, int) and nguong > 0 else 20
        if ma == _KHACH_DANG_CHO:
            dang_cho += 1
            cho_lau_nhat = max(cho_lau_nhat, w)
            if w > nguong:
                qua_nguong += 1
        elif ma in _KHACH_DANG_LAM:
            dang_lam += 1
    return {
        "dang_trong_phong_kham": sum(1 for p in patients if isinstance(p, dict)),
        "dang_cho": dang_cho,
        "dang_lam": dang_lam,
        "cho_qua_nguong": qua_nguong,
        "cho_lau_nhat_phut": cho_lau_nhat,
    }


async def doc(pool: asyncpg.Pool, *, clinic_id: str) -> dict[str, Any]:
    dv = DispatchService(pool)
    patients = await dv.overview(clinic_id=clinic_id, location_id=None)
    rooms = await dv.stations(clinic_id=clinic_id, location_id=None)

    async with pool.acquire() as conn:
        ngay = await conn.fetchrow(
            f"""
            SELECT count(*) FILTER (WHERE checked_in_at >= {_DAU_NGAY}) AS check_in,
                   count(*) FILTER (WHERE checked_in_at >= {_DAU_NGAY}
                                      AND closed_at IS NOT NULL) AS da_ve,
                   -- Hôm qua TỚI CÙNG GIỜ — so 10h sáng nay với cả ngày hôm qua
                   -- là so sai.
                   count(*) FILTER (WHERE checked_in_at
                                          >= {_DAU_NGAY} - interval '1 day'
                                      AND checked_in_at < now() - interval '1 day')
                       AS check_in_hom_qua
              FROM visit
             WHERE clinic_id = $1::uuid
               AND checked_in_at >= {_DAU_NGAY} - interval '1 day'
            """,
            clinic_id,
        )
        theo_gio = await conn.fetch(
            f"""
            SELECT extract(hour FROM checked_in_at AT TIME ZONE
                           'Asia/Ho_Chi_Minh')::int AS gio,
                   count(*) AS so
              FROM visit
             WHERE clinic_id = $1::uuid AND checked_in_at >= {_DAU_NGAY}
             GROUP BY 1
            """,
            clinic_id,
        )
        su_kien = await do_su_kien(conn)
        loi = await conn.fetchrow(
            """
            SELECT count(*) FILTER (WHERE trang_thai = 'MOI') AS moi,
                   count(*) FILTER (WHERE lan_cuoi > now() - interval '24 hours'
                                      AND trang_thai <> 'BO_QUA') AS trong_24h
              FROM loi_nhom
            """
        )
        canh = await conn.fetch(
            "SELECT ma, muc, noi_dung FROM canh_bao WHERE dong_luc IS NULL"
            " ORDER BY CASE muc WHEN 'critical' THEN 0 ELSE 1 END, lan_cuoi DESC"
        )
        agent = await conn.fetchrow(
            """
            SELECT count(*) FILTER (WHERE dong_luc IS NULL AND muc = 'critical')
                       AS critical,
                   count(*) FILTER (WHERE dong_luc IS NULL AND muc = 'warning')
                       AS warning,
                   max(lan_cuoi) AS vong_cuoi
              FROM agent_nhan_dinh WHERE clinic_id = $1::uuid
            """,
            clinic_id,
        )

    gio = {int(r["gio"]): int(r["so"]) for r in theo_gio}
    # Khung 7h–20h luôn đủ cột (giờ chưa có khách = 0), giờ ngoài khung có
    # khách thì nới ra — biểu đồ không giấu ai.
    tu = min([7, *gio.keys()])
    den = max([20, *gio.keys()])
    ly_do_su_kien = danh_gia_su_kien(su_kien)
    return {
        "van_hanh": {
            **van_hanh_tu_dieu_phoi(patients),
            "check_in_hom_nay": int(ngay["check_in"]) if ngay else 0,
            "da_ve_hom_nay": int(ngay["da_ve"]) if ngay else 0,
            "check_in_hom_qua_cung_gio": int(ngay["check_in_hom_qua"]) if ngay else 0,
            "theo_gio": [{"gio": h, "so": gio.get(h, 0)} for h in range(tu, den + 1)],
        },
        "phong": [
            {
                "id": r["id"],
                "ma": r["code"],
                "ten": r["name"],
                "tang": r["floor"],
                "dang_lam": r["serving"],
                "dang_cho": r["waiting"],
                "cho_lau_nhat": r["max_wait"],
                "nguong_phut": r["threshold_minutes"],
                "nguong_nguoi": r["threshold_waiting"],
                "trang_thai": r["state"],
                "nhan_khach": r["accepting"],
            }
            for r in rooms
        ],
        "he_thong": {
            "su_kien_on": not ly_do_su_kien,
            "su_kien_ly_do": ly_do_su_kien,
            "loi_moi": int(loi["moi"]) if loi else 0,
            "loi_24h": int(loi["trong_24h"]) if loi else 0,
            "canh_bao": [dict(r) for r in canh],
        },
        "agent": {
            "critical": int(agent["critical"]) if agent else 0,
            "warning": int(agent["warning"]) if agent else 0,
            "vong_cuoi": agent["vong_cuoi"].isoformat()
            if agent and agent["vong_cuoi"]
            else None,
        },
    }
