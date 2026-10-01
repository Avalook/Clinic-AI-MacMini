"""Danh mục dịch vụ & phòng (Tuyền 01/10/2026).

Nguồn sự thật: file phòng khám gửi 01/10 ("Bảng giá dịch vụ trên Kiot"), đã
đồng bộ vào `service_price` bằng migration 20261002100000. Luật "dịch vụ này là
phí khám không, cần phòng không, phòng nào làm được, đang thiếu phòng không"
nằm ở MỘT hàm Postgres `danh_muc_dich_vu(clinic)` (cùng `phong_lam_duoc` với
xếp phòng). File này chỉ đọc hàm ấy cho:

* màn Bảng giá dịch vụ & phòng (`/cashier/dich-vu`) — `doc`;
* cảnh báo "dịch vụ đang bán chưa có phòng" ở trang chủ quản lý — `dem_chua_co_phong`;
* danh mục chỉ định (`phieu_kham_service.tham_chieu_that`) — hàm thuần
  `nhom_hang_hien`, `ly_do_khoa_chi_dinh`, `thu_tu_nhom_hang`.

Gán / bỏ phòng cho một dịch vụ là đổi cấu hình phòng → `ClinicConfigService.
set_service_rooms` (quyền `config.clinic.manage`).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.permissions.can import can

#: Thứ tự nhóm hàng như file phòng khám (Excel 01/10) — nhóm lạ xếp sau, theo tên.
THU_TU_NHOM = (
    "Siêu âm",
    "Xét nghiệm",
    "XN thu hộ",
    "Thủ thuật",
    "Dịch vụ khác",
    "Chụp phim ngoài",
    "Phí khám",
)

#: Câu khoá ô chỉ định khi dịch vụ chưa có nhóm việc (máy chủ chỉ định không
#: xếp được — `SERVICE_NOT_MAPPED`). Hiện đúng việc cần làm, không im lặng.
KHOA_CHUA_NHOM_VIEC = "Chưa gắn nhóm việc — quản lý gán ở Bảng giá dịch vụ & phòng"


def nhom_hang_hien(nhom: Any) -> str | None:
    """Nhóm hàng để HIỆN — hàm thuần.

    "Siêu âm>>Siêu âm thai" (cách KiotViet viết nhóm 3 cấp) → "Siêu âm ›
    Siêu âm thai". Nhóm cũ là ghi chú nhập liệu ("KiotViet 26/09/2026 · CHƯA
    CÓ GIÁ…", "Tiền khám · GIÁ GIẢ ĐỊNH…") không phải nhóm → None.
    """
    if not isinstance(nhom, str):
        return None
    s = " ".join(nhom.split())
    if not s or "KiotViet" in s or "·" in s:
        return None
    return " › ".join(p.strip() for p in s.split(">>") if p.strip()) or None


def thu_tu_nhom_hang(ten: str) -> tuple[int, str]:
    """Khoá sắp nhóm hàng theo thứ tự file phòng khám — hàm thuần."""
    for i, goc in enumerate(THU_TU_NHOM):
        if ten == goc or ten.startswith(goc + " ›"):
            return (i, ten)
    return (len(THU_TU_NHOM), ten)


def ly_do_khoa_chi_dinh(dong: Mapping[str, Any]) -> str | None:
    """Vì sao ô chỉ định của dịch vụ này bị khoá — None = chỉ định được."""
    if not dong.get("node_code"):
        return KHOA_CHUA_NHOM_VIEC
    return None


def _so(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(Decimal(str(v)))
    except Exception:  # noqa: BLE001 — số rác: coi như chưa có giá
        return None


def _json(v: Any) -> list[dict[str, Any]]:
    if v is None:
        return []
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return []
    return [dict(x) for x in v] if isinstance(v, list) else []


def dong_danh_muc(r: Mapping[str, Any]) -> dict[str, Any]:
    """Một dòng của hàm `danh_muc_dich_vu` → dạng màn vẽ — hàm thuần."""
    phong = _json(r.get("phong"))
    return {
        "id": str(r["id"]),
        "service_code": r["service_code"],
        "name": r["name"],
        "nhom": r.get("nhom"),
        "nhom_hien": nhom_hang_hien(r.get("nhom")),
        "unit_price": _so(r.get("unit_price")),
        "active": bool(r.get("active")),
        "billing_owner": r.get("billing_owner") or "CLINIC",
        "billing_owner_chon_tay": bool(r.get("billing_owner_chon_tay")),
        "node_code": r.get("node_code"),
        "ten_nhom_viec": r.get("ten_nhom_viec"),
        "ma_kiotviet": r.get("ma_kiotviet"),
        "gia_tam": bool(r.get("gia_tam")),
        "la_phi_kham": bool(r.get("la_phi_kham")),
        "can_phong": bool(r.get("can_phong")),
        "gan_rieng": bool(r.get("gan_rieng")),
        "phong": [
            {"id": str(p["id"]), "ten": p.get("ten"), "doi_tac": bool(p.get("doi_tac"))}
            for p in phong
        ],
        "chua_co_phong": bool(r.get("chua_co_phong")),
    }


async def dem_chua_co_phong(conn: asyncpg.Connection, clinic_id: str) -> int:
    """Số dịch vụ ĐANG BÁN (trừ phí khám, việc đối tác làm trọn) chưa phòng nội
    bộ nào làm được — cảnh báo trang chủ quản lý."""
    n = await conn.fetchval(
        "SELECT count(*) FROM public.danh_muc_dich_vu($1::uuid) WHERE chua_co_phong",
        clinic_id,
    )
    return int(n or 0)


class DanhMucDichVuService:
    """Đọc danh mục dịch vụ + phòng cho màn Bảng giá dịch vụ & phòng."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(self, *, identity: StaffIdentity) -> dict[str, Any]:
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM public.danh_muc_dich_vu($1::uuid)"
                " ORDER BY coalesce(ma_kiotviet, service_code)",
                cid,
            )
            phong = await conn.fetch(
                """
                SELECT r.id, coalesce(r.name, r.code) AS ten, r.la_doi_tac,
                       l.name AS co_so
                  FROM public.clinic_room r
                  JOIN public.clinic_location l ON l.id = r.location_id
                 WHERE r.clinic_id = $1::uuid AND r.is_active
                 ORDER BY l.name, r.sort, r.code
                """,
                cid,
            )
            # Gán phòng là đổi CẤU HÌNH phòng (lego "Cài đặt phòng khám") — màn
            # Bảng giá mở cho người giữ bảng giá, nên máy chủ nói có sửa được không.
            sua_phong = await can(conn, identity, "config.clinic.manage")
        ds = [dong_danh_muc(r) for r in rows]
        nhom = sorted(
            {d["nhom_hien"] for d in ds if d["nhom_hien"]} | {g for g in THU_TU_NHOM},
            key=thu_tu_nhom_hang,
        )
        return {
            "dich_vu": ds,
            "phong": [
                {
                    "id": str(p["id"]),
                    "ten": p["ten"],
                    "doi_tac": bool(p["la_doi_tac"]),
                    "co_so": p["co_so"],
                }
                for p in phong
            ],
            "nhom_hang": nhom,
            "sua_phong_duoc": bool(sua_phong),
            "so_chua_co_phong": sum(1 for d in ds if d["chua_co_phong"]),
        }
