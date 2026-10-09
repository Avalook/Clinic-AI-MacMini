"""Báo cáo CA CỦA TÔI — nhân viên xem số bán hàng của đúng ca mình (Tuyền 09/10/2026).

Lego Báo cáo (``report.view``) chỉ còn Quản lý + Trưởng ca (migration
20261010300000). Nhân viên khác vẫn cần đếm két cuối ca, nên quyền xem ở đây
SUY TỪ LỊCH TRỰC, không thêm lego:

* có tên trong ``work_roster`` HÔM NAY (giờ VN), dòng không ``REJECTED`` → được
  xem đúng (ca, cơ sở) của dòng ấy; ca ``FULL`` = cả ba ca (``ca_xem_duoc``);
* cơ sở của dòng = vị trí → phòng → ``location_id`` (cùng luật
  ``lich_truc_co_so``). Vị trí chưa gắn cơ sở: phòng khám MỘT cơ sở thì lấy cơ
  sở ấy, nhiều cơ sở thì từ chối và nói rõ phải nhờ quản lý gắn;
* NGÀY luôn là hôm nay — hàm không nhận ngày nào từ người gọi.

Số liệu lấy thẳng ``BaoCaoCuoiNgayService.bao_cao`` (một nguồn sự thật với màn
/reports) rồi CẮT ở máy chủ những phần nhân viên không được thấy
(``cat_cho_nhan_vien``) — ẩn ở TSX là không đủ, payload vẫn lộ.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import hom_nay_vn, now_vn
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.shifts import (
    CAC_CA,
    NHAN_CA,
    ca_tu_settings,
    ca_xem_duoc,
    khung_chot_ca,
)
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.co_so_bao_cao import doc_co_so, doc_ds_co_so

#: Khối của báo cáo cuối ngày mà nhân viên KHÔNG được thấy:
#: * ``theo_nguoi_thu`` / ``theo_co_so`` — Tuyền chốt ẩn (so người với người,
#:   số cơ sở khác);
#: * ``khach_con_no`` / ``tien_thua`` — tính CẢ NGÀY (hoặc tới hiện tại), không
#:   theo ca, nên để lại là lộ số của ca khác. Nợ của ca nằm ở ``no_trong_ca``.
AN_VOI_NHAN_VIEN: tuple[str, ...] = (
    "theo_nguoi_thu",
    "theo_co_so",
    "khach_con_no",
    "tien_thua",
)

CAU_KHONG_CO_CA = (
    "Hôm nay bạn không có tên trong lịch trực ca nào — báo cáo ca chỉ mở cho "
    "người trực ca ấy. Cần xem số cả ngày thì nhờ Trưởng ca hoặc Quản lý."
)
CAU_CHUA_GAN_CO_SO = (
    "Vị trí trực hôm nay của bạn chưa gắn cơ sở nên chưa biết báo cáo của cơ sở "
    "nào — nhờ quản lý gắn cơ sở cho vị trí (Cấu trúc phòng khám)."
)
CAU_KHONG_DUOC_XEM = "Bạn chỉ xem được báo cáo của ca mình trực hôm nay, đúng cơ sở ấy."

_LICH_SQL = """
SELECT w.shift, w.status, r.location_id::text AS co_so
  FROM public.work_roster w
  LEFT JOIN public.vi_tri_lam_viec v
    ON v.clinic_id = w.clinic_id AND v.code = w.station
  LEFT JOIN public.clinic_room r ON r.id = v.room_id
 WHERE w.clinic_id = $1::uuid AND w.staff_id = $2::uuid AND w.work_date = $3
"""


def cat_cho_nhan_vien(bc: Mapping[str, Any]) -> dict[str, Any]:
    """Bản báo cáo cho nhân viên: bỏ hẳn các khối ``AN_VOI_NHAN_VIEN``. Thuần."""
    return {k: v for k, v in bc.items() if k not in AN_VOI_NHAN_VIEN}


def chon_cap(
    duoc: set[tuple[str, str]],
    ca: Any,
    co_so: Any,
    ca_hien_tai: str | None,
) -> tuple[str, str] | None:
    """Cặp (ca, cơ sở) sẽ xem. ``None`` = không được xem (→ 403). Thuần.

    Không gửi ca → ca HIỆN TẠI nếu được xem, không thì ca sớm nhất được xem. Ca
    rác → ``None`` (không lặng lẽ đổi sang ca khác). Không gửi cơ sở → cơ sở
    đầu tiên (theo mã) có ca ấy; cơ sở rác → ``None``.
    """
    if not duoc:
        return None
    ma = str(ca or "").strip().upper()
    if ma:
        if ma not in CAC_CA:
            return None
    else:
        cac = [c for c in CAC_CA if any(c == x for x, _ in duoc)]
        ma = ca_hien_tai if ca_hien_tai in cac else cac[0]
    cs = doc_co_so(co_so)
    if cs is None:
        ung = sorted(c for x, c in duoc if x == ma)
        return (ma, ung[0]) if ung else None
    return (ma, cs) if (ma, cs) in duoc else None


def ca_cua_luc(phut: int, settings: Any) -> str | None:
    """Ca chốt tiền chứa mốc phút này (khung khít, phủ trọn ngày). Thuần."""
    bang = ca_tu_settings(settings)
    for c in CAC_CA:
        w = khung_chot_ca(c, bang)
        if w and w[0] <= phut < w[1]:
            return c
    return None


def ds_ca_duoc_xem(
    duoc: Iterable[tuple[str, str]], ten_co_so: Mapping[str, str]
) -> list[dict[str, str]]:
    """Các tab ca cho màn — sáng → chiều → tối, rồi theo tên cơ sở. Thuần."""
    thu_tu = {c: i for i, c in enumerate(CAC_CA)}
    return [
        {
            "ca": c,
            "ten": NHAN_CA[c],
            "co_so": cs,
            "ten_co_so": ten_co_so.get(cs, ""),
        }
        for c, cs in sorted(
            duoc, key=lambda x: (thu_tu[x[0]], ten_co_so.get(x[1], ""), x[1])
        )
    ]


class BaoCaoCaCuaToiService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def bao_cao(
        self,
        *,
        identity: StaffIdentity,
        ca: Any = None,
        co_so: Any = None,
        loai: Any = None,
    ) -> dict[str, Any]:
        """Báo cáo bán hàng của một (ca, cơ sở) người gọi trực HÔM NAY.

        Không được xem (không có ca, ca / cơ sở khác, ca rác) → ``SafetyGateError``
        (403), không 500. ``loai`` như ``BaoCaoCuoiNgayService.bao_cao``.
        """
        hom_nay = hom_nay_vn()
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            lich = [
                dict(r)
                for r in await conn.fetch(_LICH_SQL, cid, identity.staff_id, hom_nay)
            ]
            ds_co_so = await doc_ds_co_so(conn, cid)
            dang_mo = await conn.fetch(
                "SELECT id::text AS id FROM public.clinic_location"
                " WHERE clinic_id = $1::uuid AND is_active",
                cid,
            )
            settings = await conn.fetchval(
                "SELECT settings FROM public.clinic WHERE id = $1::uuid", cid
            )
        mac_dinh = dang_mo[0]["id"] if len(dang_mo) == 1 else None
        duoc = ca_xem_duoc(lich, mac_dinh)
        if not duoc:
            chua_gan = any(
                d.get("co_so") is None and str(d.get("status")) != "REJECTED"
                for d in lich
            )
            raise SafetyGateError(CAU_CHUA_GAN_CO_SO if chua_gan else CAU_KHONG_CO_CA)
        bay_gio = now_vn()
        cap = chon_cap(
            duoc, ca, co_so, ca_cua_luc(bay_gio.hour * 60 + bay_gio.minute, settings)
        )
        if cap is None:
            raise SafetyGateError(CAU_KHONG_DUOC_XEM)
        ngay = hom_nay.isoformat()
        bc = await BaoCaoCuoiNgayService(self._pool).bao_cao(
            identity=identity, tu=ngay, den=ngay, loai=loai, co_so=cap[1], ca=cap[0]
        )
        ra = cat_cho_nhan_vien(bc)
        ra["ca_duoc_xem"] = ds_ca_duoc_xem(duoc, {c["id"]: c["ten"] for c in ds_co_so})
        return ra


__all__ = [
    "AN_VOI_NHAN_VIEN",
    "BaoCaoCaCuaToiService",
    "ca_cua_luc",
    "cat_cho_nhan_vien",
    "chon_cap",
    "ds_ca_duoc_xem",
]
