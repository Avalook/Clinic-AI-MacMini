"""Chọn MẪU KẾT QUẢ cho một dịch vụ — một luật cho cả phòng dịch vụ lẫn phiếu khám.

Tuyền 23/09/2026 khuya: "làm tiếp phần phòng siêu âm điền kết quả". Trước đây
phòng chỉ thấy mẫu ĐÃ GẮN cho dịch vụ (`dich_vu_mau_ket_qua`) — mà chưa dịch vụ
nào được gắn, nên phòng siêu âm mở ra là "chưa gắn mẫu kết quả nào".

Thứ tự:
  1. Mẫu phòng khám đã GẮN cho dịch vụ (quyết định của quản lý) — dùng đúng nó.
  2. Chưa gắn: mẫu GỢI Ý của phiếu v5 (nhãn nguồn → `form_id_ket_qua`, ghép qua
     bảng mã viết tay `anh_xa_danh_muc`) đứng đầu và được chọn sẵn, kèm 18 mẫu
     dự phòng ("Mở nhanh 18 biểu mẫu" của v5) để chọn mẫu khác.
  3. Không gắn, không gợi ý: mẫu CHUNG (nhập tự do) chọn sẵn — Tuyền 24/09/2026
     "form nào tài liệu chưa có thì cũng phải có ô để họ nhập".
Không tự GẮN gì vào `dich_vu_mau_ket_qua` — gợi ý chỉ là lựa chọn mặc định lúc
mở phiếu; gắn chính thức vẫn là việc của quản lý.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import cache
from typing import Any

import asyncpg

from clinicai.phieu_kham import anh_xa_danh_muc as ax
from clinicai.phieu_kham.khung import tham_chieu_nguon

#: Mẫu nhập tự do (migration 20260925000008) — không thuộc dịch vụ nào, nên
#: không bao giờ bị cảnh báo "mẫu của dịch vụ khác".
MAU_CHUNG = "CHUNG"


@cache
def _goi_y_theo_ma() -> dict[str, str]:
    """service_code → mã mẫu (không kèm `KQ_`), theo nhãn nguồn v5."""
    tc = tham_chieu_nguon()
    ra: dict[str, str] = {}
    for nhom in tc["chi_dinh_cls"]:
        for m in nhom["muc"]:
            dv = ax.CLS.get(m["nhan"])
            if dv and m.get("form_id_ket_qua"):
                ra.setdefault(dv.ma, m["form_id_ket_qua"].removeprefix("KQ_"))
    for t in tc["thu_thuat"]:
        dv = ax.THU_THUAT.get(t["ma"])
        if dv and t.get("form_id_ket_qua"):
            ra.setdefault(dv.ma, t["form_id_ket_qua"].removeprefix("KQ_"))
    return ra


def ma_mau_goi_y(service_code: str) -> str | None:
    return _goi_y_theo_ma().get(service_code)


def chon_mau(
    da_gan: list[dict[str, Any]],
    tat_ca: list[dict[str, Any]],
    service_code: str,
) -> dict[str, Any]:
    """Luật chọn mẫu — hàm THUẦN, một chỗ duy nhất (màn chỉ vẽ kết quả).

    Trả ``{"mau", "chon_san", "mac_dinh"}``. ``mac_dinh`` = quản lý CHƯA gắn mẫu
    nào cho dịch vụ, mẫu chọn sẵn là mặc định của máy (gợi ý v5, hoặc CHUNG nhập
    tự do). Gắn mẫu riêng sau này thì mẫu đã gắn thắng, ``mac_dinh`` về false.
    """
    if da_gan:
        return {
            "mau": [{**m, "cua_dich_vu": True} for m in da_gan],
            "chon_san": da_gan[0]["ma"],
            "mac_dinh": False,
        }
    tat_ca = list(tat_ca)
    goi_y = ma_mau_goi_y(service_code)
    if goi_y and any(m["ma"] == goi_y for m in tat_ca):
        tat_ca.sort(key=lambda m: m["ma"] != goi_y)
        return {
            "mau": [
                {**m, "cua_dich_vu": m["ma"] in (goi_y, MAU_CHUNG)} for m in tat_ca
            ],
            "chon_san": goi_y,
            "mac_dinh": True,
        }
    co_chung = any(m["ma"] == MAU_CHUNG for m in tat_ca)
    tat_ca.sort(key=lambda m: m["ma"] != MAU_CHUNG)
    return {
        "mau": [{**m, "cua_dich_vu": True} for m in tat_ca],
        "chon_san": MAU_CHUNG if co_chung else None,
        "mac_dinh": True,
    }


async def mau_cho_cac_dich_vu(
    conn: asyncpg.Connection, *, clinic_id: str, service_codes: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """`chon_mau` cho nhiều dịch vụ bằng HAI câu truy vấn (không N+1)."""
    ma_dv = sorted(set(service_codes))
    if not ma_dv:
        return {}
    da_gan: dict[str, list[dict[str, Any]]] = {}
    for r in await conn.fetch(
        "SELECT d.service_code, m.ma, m.ten, m.nhom FROM dich_vu_mau_ket_qua d"
        "  JOIN ket_qua_mau m ON m.clinic_id = d.clinic_id AND m.ma = d.mau"
        "   AND m.active"
        " WHERE d.clinic_id = $1::uuid AND d.service_code = ANY($2::text[])"
        # `thu_tu` trước tên: mẫu gắn THÊM (thu_tu > 0) không giành chỗ chọn sẵn.
        # Theo tên thôi thì "…thai quý III" đứng trước "…thai quý II - III"
        # (collation en_US bỏ qua " - ") và thành mặc định (09/10/2026).
        " ORDER BY d.thu_tu, m.ten",
        clinic_id,
        ma_dv,
    ):
        da_gan.setdefault(r["service_code"], []).append(
            {"ma": r["ma"], "ten": r["ten"], "nhom": r["nhom"]}
        )
    tat_ca = [
        dict(r)
        for r in await conn.fetch(
            "SELECT ma, ten, nhom FROM ket_qua_mau"
            " WHERE clinic_id = $1::uuid AND active ORDER BY nhom, ten",
            clinic_id,
        )
    ]
    return {c: chon_mau(da_gan.get(c, []), tat_ca, c) for c in ma_dv}


async def mau_cho_dich_vu(
    conn: asyncpg.Connection, *, clinic_id: str, service_code: str
) -> tuple[list[dict[str, Any]], str | None]:
    """(danh sách mẫu để chọn, mẫu chọn sẵn).

    Mỗi mẫu kèm ``cua_dich_vu`` — mẫu này có phải của CHÍNH dịch vụ đang làm
    không (Tuyền 24/09/2026: chọn mẫu của dịch vụ khác thì báo "khách chưa
    thanh toán dịch vụ này", không chuyển phiếu). Mẫu đã gắn: đều của dịch vụ.
    Chưa gắn: chỉ mẫu gợi ý là của dịch vụ; không có gợi ý thì không biết —
    để mọi mẫu chọn được như trước.
    """
    kq = (
        await mau_cho_cac_dich_vu(
            conn, clinic_id=clinic_id, service_codes=[service_code]
        )
    )[service_code]
    return kq["mau"], kq["chon_san"]


__all__ = [
    "MAU_CHUNG",
    "chon_mau",
    "ma_mau_goi_y",
    "mau_cho_cac_dich_vu",
    "mau_cho_dich_vu",
]
