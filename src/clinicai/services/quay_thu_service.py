"""Quầy thu dịch vụ — MỘT hoá đơn mỗi khách (Tuyền chốt 27/09/2026, bản mẫu v2).

Màn `/thu-ngan/dich-vu` chỉ VẼ. Mọi thứ nó cần để vẽ và mọi con số đều dựng ở
đây, cùng luật với lệnh:

* ``dung_hoa_don_quay`` — ghép hoá đơn còn nợ (dự kiến theo mặc định "khách làm
  mọi chỉ định chưa từ chối") với danh sách chỉ định chờ khách quyết thành MỘT
  hoá đơn: mỗi dịch vụ đúng một dòng (trước đây một dịch vụ hiện ở ba khối: ô
  chọn, tiền dịch vụ, phòng đã thu). Nhóm "Phòng khám thu" và nhóm "Khách trả
  trực tiếp đối tác · không cộng".
* ``so_sanh_chi_dinh`` — "BS chỉ định N · khách làm M · bỏ K (−X đ)" + bảng so.
* ``xep_vang_nhat`` — ô chọn phòng: vắng nhất lên đầu, kèm cờ ``vang_nhat``.
* Lịch sử gom theo khách, tổng 5 ô, xuất CSV, dữ liệu bản in phiếu thu / hoàn.

Hàm thuần có test không cần DB (``tests/unit/test_quay_thu.py``); phần đọc DB
nằm trong ``QuayThuService``.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.tran import canh_bao_neu_day
from clinicai.permissions.can import can
from clinicai.services.anh_chuyen_khoan_service import anh_cua_cac_lan_thu
from clinicai.services.cashier_board_service import (
    doc_khoang_ngay,
    hoan_tac_cua,
    quyen_thu_theo_loai,
)
from clinicai.services.day_noi import doc_day
from clinicai.services.doi_hinh_thuc_service import gan_vao_lich_su, trang_thai_doi
from clinicai.services.lan_bac_si import ten_bac_si
from clinicai.services.phan_thu import (
    HINH_THUC_THU,
    cac_hinh_thuc,
    chuan_hinh_thuc,
    doc_phan_db,
    nhan_phan,
    phan_mot_hinh_thuc,
    tra_lai,
)

# ---------------------------------------------------------------------------
# Phòng chọn được
# ---------------------------------------------------------------------------


def xep_vang_nhat(phong: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Ô chọn phòng của quầy: phòng ÍT NGƯỜI CHỜ NHẤT lên đầu, kèm ``vang_nhat``.

    Hàm thuần. Cùng số chờ thì giữ thứ tự gợi ý của máy xếp phòng (có người
    trực trước, rồi thứ tự cấu hình). Chỉ phòng đầu tiên mang cờ — hai phòng
    cùng 0 người chờ vẫn chỉ một dòng "— vắng nhất" để câu không lặp.
    """
    ds = [dict(p) for p in phong]
    thu_tu = {id(p): i for i, p in enumerate(ds)}
    ds.sort(key=lambda p: (_so_nguyen(p.get("dang_cho")), thu_tu[id(p)]))
    for i, p in enumerate(ds):
        p["vang_nhat"] = i == 0
    return ds


def _so_nguyen(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


class PhongQuay:
    """Phòng chọn được cho từng chỉ định, nhớ trong một lần đọc bảng.

    Đúng tập của dây H4 (cùng cơ sở, còn nhận khách, làm được bước + DỊCH VỤ
    này — dịch vụ gắn phòng riêng thì chỉ các phòng ấy, không phải phòng đối
    tác) — `eligible_rooms` + `rank_rooms` — rồi vắng nhất lên đầu. Dùng cho CẢ
    ô "phòng dự kiến" (trước thu) lẫn ô xếp phòng sau thu.
    """

    def __init__(self, conn: asyncpg.Connection, clinic_id: str) -> None:
        self._conn = conn
        self._clinic_id = clinic_id
        self._ten: dict[str, str] | None = None
        self._nho: dict[
            tuple[str, str | None, str | None, str], list[dict[str, Any]]
        ] = {}

    async def cua(
        self, node: str | None, visit_id: str, service_code: str | None = None
    ) -> list[dict[str, Any]]:
        if not node:
            return []
        from clinicai.services.lan_bac_si import can_chon_bac_si, lua_chon_bac_si
        from clinicai.services.service_routing_service import (
            co_so_cua_luot,
            eligible_rooms,
            phong_chuyen_duy_nhat,
            rank_rooms,
        )

        if self._ten is None:
            self._ten = {
                r["id"]: r["name"]
                for r in await self._conn.fetch(
                    "SELECT id::text AS id, name FROM clinic_room"
                    " WHERE clinic_id = $1::uuid AND is_active",
                    self._clinic_id,
                )
            }
        co_so = await co_so_cua_luot(self._conn, self._clinic_id, visit_id=visit_id)
        khoa = (node, service_code, co_so, visit_id)
        if khoa not in self._nho:
            ung_vien = rank_rooms(
                await eligible_rooms(
                    self._conn,
                    self._clinic_id,
                    node,
                    co_so,
                    tru_luot=visit_id,
                    service_code=service_code,
                )
            )
            # Phòng nhiều bác sĩ (30/09/2026): chọn phòng xong chọn tiếp bác
            # sĩ trực hôm nay — chỉ khi ≥2 bác sĩ; lọc tiếp trên tập phòng này.
            bac_si = await lua_chon_bac_si(
                self._conn,
                self._clinic_id,
                [u["room_id"] for u in ung_vien],
                tru_luot=visit_id,
            )
            goi_y = phong_chuyen_duy_nhat(ung_vien)
            self._nho[khoa] = xep_vang_nhat(
                [
                    {
                        "id": u["room_id"],
                        "ten": self._ten.get(u["room_id"], "Phòng"),
                        "dang_cho": u["queue_load"],
                        "bac_si": ds if can_chon_bac_si(ds) else [],
                        # Phòng chuyên ★ (07/10/2026); ``goi_y`` = phòng chuyên
                        # DUY NHẤT — ô hướng dẫn gợi ý, không tự lưu.
                        "chuyen": bool(u.get("chuyen")),
                        "goi_y": u["room_id"] == goi_y,
                    }
                    for u in ung_vien
                    for ds in [bac_si.get(u["room_id"], [])]
                ]
            )
        return self._nho[khoa]


# ---------------------------------------------------------------------------
# MỘT hoá đơn
# ---------------------------------------------------------------------------


def _so(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(Decimal(str(v)))
    except Exception:  # noqa: BLE001 — số rác từ dữ liệu cũ: coi như chưa có giá
        return None


def dung_hoa_don_quay(
    hoa_don: Mapping[str, Any] | None,
    chon: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Hoá đơn MỘT khách cho quầy. Hàm thuần.

    ``hoa_don`` = ``HoaDon.cho_api()`` của hoá đơn còn nợ DỰ KIẾN (chỉ định chờ
    khách quyết tính như đã chọn); ``chon`` = một lượt của ``cho_khach_quyet``.

    Mỗi dịch vụ đúng MỘT dòng:
      * tiền khám — tick khoá;
      * chỉ định còn chờ khách quyết — tick được (trừ "Bắt buộc" đang
        tick — không bỏ được, nhưng đang bỏ thì tick lại được); bỏ tick =
        ``chon`` False (màn gạch ngang + "khách không làm");
      * dòng hoá đơn không còn ở giai đoạn khách quyết (dữ liệu cũ) — tick khoá.
    Đối tác tự thu vào nhóm riêng, không cộng. Tổng / dấu hoá đơn lấy nguyên từ
    hoá đơn máy chủ — ở đây không cộng lại.
    """
    hd = hoa_don or {}
    chi_dinh = list((chon or {}).get("chi_dinh") or [])
    theo_id = {str(c["id"]): c for c in chi_dinh}
    dong_hd = {str(d["source_id"]): d for d in hd.get("dong") or []}
    dong_dt = {str(d["source_id"]): d for d in hd.get("dong_doi_tac") or []}

    phong_kham: list[dict[str, Any]] = []
    doi_tac: list[dict[str, Any]] = []

    for d in hd.get("dong") or []:
        if d.get("source_type") == "exam":
            phong_kham.append(
                {
                    "id": str(d["source_id"]),
                    "loai": "kham",
                    "ten": d.get("ten"),
                    "gia": _so(d.get("thanh_tien")),
                    "van_de": d.get("van_de"),
                    "chon": True,
                    "sua_duoc": False,
                    "trong_lua_chon": False,
                }
            )

    # Phụ thu CŨ kèm dịch vụ (đầu dò…, 28/09/2026): khối tick đã gỡ (C17,
    # 02/10/2026, thay bằng "Mua thêm vật tư") nhưng dòng đã tick từ trước vẫn
    # nằm trong hoá đơn, khoá như tiền khám, thu được như thường.
    phu_thu_quay: list[dict[str, Any]] = []
    for d in hd.get("dong") or []:
        if d.get("source_type") != "phu_thu":
            continue
        order_id = str(d.get("order_id") or "")
        cha = theo_id.get(order_id)
        phu_thu_quay.append(
            {
                "id": str(d["source_id"]),
                "order_id": order_id or None,
                "loai": "phu_thu",
                "ten": d.get("ten"),
                "gia": _so(d.get("thanh_tien")),
                "van_de": d.get("van_de"),
                "chon": cha is None or cha.get("selection_status") != "NOT_SELECTED",
                "sua_duoc": False,
                "trong_lua_chon": False,
            }
        )

    # Vật tư khách mua thêm (C13, 01/10/2026): thêm / đổi số lượng / bỏ ở khối
    # "Mua thêm vật tư" (`VatTuQuay`); trong hoá đơn là dòng khoá như tiền khám,
    # tiền DỊCH VỤ cộng vào tổng. Không có chỉ định cha, không có phòng.
    vat_tu_quay: list[dict[str, Any]] = []
    for d in hd.get("dong") or []:
        if d.get("source_type") != "vat_tu":
            continue
        sl = int(Decimal(str(d.get("so_luong") or 1)))
        ten = str(d.get("ten") or "Vật tư")
        vat_tu_quay.append(
            {
                "id": str(d["source_id"]),
                "loai": "vat_tu",
                "ten": f"{ten} × {sl}" if sl > 1 else ten,
                "gia": _so(d.get("thanh_tien")),
                "van_de": d.get("van_de"),
                "chon": True,
                "sua_duoc": False,
                "trong_lua_chon": False,
            }
        )

    # Trả trước k buổi liệu trình (08/10/2026): thêm / bỏ ở khối "Liệu trình"
    # của quầy (`/lieu-trinh/quay`); trong hoá đơn là dòng khoá như vật tư.
    lieu_trinh_quay: list[dict[str, Any]] = []
    for d in hd.get("dong") or []:
        if d.get("source_type") != "lieu_trinh":
            continue
        lieu_trinh_quay.append(
            {
                "id": str(d["source_id"]),
                "loai": "lieu_trinh",
                "lieu_trinh_id": d.get("ma"),
                "ten": d.get("ten"),
                "so_buoi": int(Decimal(str(d.get("so_luong") or 1))),
                "gia": _so(d.get("thanh_tien")),
                "van_de": d.get("van_de"),
                "chon": True,
                "sua_duoc": False,
                "trong_lua_chon": False,
            }
        )

    for c in chi_dinh:
        cid = str(c["id"])
        chon_c = c.get("selection_status") != "NOT_SELECTED"
        dong = dong_hd.get(cid) or dong_dt.get(cid)
        la_doi_tac = bool(c.get("doi_tac_thu"))
        gia = _so(dong.get("thanh_tien")) if dong else None
        if gia is None:
            gia = _so(c.get("gia"))
        muc: dict[str, Any] = {
            "id": cid,
            "loai": "chi_dinh",
            "ten": c.get("ten"),
            "gia": gia,
            "van_de": dong.get("van_de") if dong and chon_c else None,
            "chon": chon_c,
            # "Bắt buộc" chỉ cấm BỎ tick (máy chủ chặn `SERVICE_REQUIRED`).
            # Bác sĩ đánh dấu bắt buộc SAU khi khách đã bỏ → phải tick lại
            # được, không thì kẹt "không làm" (staging 08/10/2026).
            "sua_duoc": not (c.get("bat_buoc") and chon_c),
            "trong_lua_chon": True,
            "bat_buoc": bool(c.get("bat_buoc")),
            "mang_sang": bool(c.get("mang_sang")),
            # Lần chỉ định (06/10/2026) — quầy ghi "Lần 1 / Lần 2"; NULL = mang
            # sang / làm thêm tại quầy (không thuộc lần bác sĩ chốt).
            "lan": c.get("lan_chi_dinh"),
            # Làm thêm tại quầy (01/10/2026): "Làm thêm tại quầy tiếp đón".
            "lam_them": c.get("lam_them"),
            "doi_tac_lam": bool(c.get("doi_tac")),
            "phong_chon_duoc": list(c.get("phong_chon_duoc") or []),
            "phong_du_kien_id": c.get("phong_du_kien_id"),
            "bac_si_lam_id": c.get("bac_si_lam_id"),
            "can_xep_phong": bool(c.get("phong_chon_duoc")),
            # Dây Nhận tại phòng BẬT: ô phòng là hướng dẫn (không bắt buộc).
            "huong_dan": bool(c.get("huong_dan")),
            # Buổi liệu trình: {lieu_trinh_id, buoi_so, so_buoi, tra_truoc, da_lam}.
            "lieu_trinh": c.get("lieu_trinh"),
        }
        if la_doi_tac:
            muc["doi_tac_da_thu"] = (dong or {}).get("doi_tac_da_thu")
            doi_tac.append(muc)
        else:
            phong_kham.append(muc)

    # Dòng hoá đơn KHÔNG còn ở giai đoạn khách quyết (dữ liệu cũ đã xếp phòng
    # mà chưa thu…): vẫn là khoản phải thu — hiện, tick khoá.
    for d in hd.get("dong") or []:
        sid = str(d["source_id"])
        if (
            d.get("source_type") in ("exam", "phu_thu", "vat_tu", "lieu_trinh")
            or sid in theo_id
        ):
            continue
        phong_kham.append(
            {
                "id": sid,
                "loai": "chi_dinh",
                "ten": d.get("ten"),
                "gia": _so(d.get("thanh_tien")),
                "van_de": d.get("van_de"),
                "chon": True,
                "sua_duoc": False,
                "trong_lua_chon": False,
            }
        )
    phong_kham.extend(phu_thu_quay)
    phong_kham.extend(vat_tu_quay)
    phong_kham.extend(lieu_trinh_quay)
    for d in hd.get("dong_doi_tac") or []:
        sid = str(d["source_id"])
        if sid in theo_id:
            continue
        doi_tac.append(
            {
                "id": sid,
                "loai": "chi_dinh",
                "ten": d.get("ten"),
                "gia": _so(d.get("thanh_tien")),
                "van_de": None,
                "chon": True,
                "sua_duoc": False,
                "trong_lua_chon": False,
                "doi_tac_da_thu": d.get("doi_tac_da_thu"),
            }
        )

    return {
        "tong": int(hd.get("tong") or 0),
        "revision": hd.get("revision"),
        "thu_duoc": bool(hd.get("thu_duoc")),
        "van_de": list(hd.get("van_de") or []),
        "canh_bao": list(hd.get("canh_bao") or []),
        "chi_doi_tac_thu": bool(hd.get("chi_doi_tac_thu")),
        "phong_kham": phong_kham,
        "doi_tac": doi_tac,
        "so_sanh": so_sanh_chi_dinh(chi_dinh),
        # Đúng thứ lệnh thu gộp cần gửi lại (lựa chọn khách đang nhìn).
        "lua_chon": {
            "revision": int((chon or {}).get("revision") or 0),
            "order_ids_seen": [str(c["id"]) for c in chi_dinh],
        },
    }


def so_sanh_chi_dinh(chi_dinh: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """ "BS chỉ định N dịch vụ · khách làm M · bỏ K (−X đ)" + bảng so. Hàm thuần.

    N = mọi chỉ định đang hỏi khách (kể cả dịch vụ khách trả đối tác). Tiền bỏ
    chỉ cộng dịch vụ PHÒNG KHÁM thu — dịch vụ đối tác không phải tiền của quầy.
    Chân bảng: bác sĩ + lần + giờ của lần chỉ định MỚI NHẤT.
    """
    dong: list[dict[str, Any]] = []
    so_lam = so_bo = tien_bo = 0
    moi_nhat: Mapping[str, Any] | None = None
    for c in chi_dinh:
        lam = c.get("selection_status") != "NOT_SELECTED"
        doi_tac = bool(c.get("doi_tac_thu"))
        gia = _so(c.get("gia"))
        if lam:
            so_lam += 1
        else:
            so_bo += 1
            if not doi_tac and gia:
                tien_bo += gia
        dong.append(
            {
                "id": str(c["id"]),
                "ten": c.get("ten"),
                "khach": ("doi_tac" if doi_tac else "lam") if lam else "khong",
                "tien": gia,
                "doi_tac": doi_tac,
                "lam_them": c.get("lam_them"),
            }
        )
        luc = c.get("chi_dinh_luc")
        # Chân bảng nói về lần chỉ định của BÁC SĨ — làm thêm tại quầy (lễ tân /
        # người đo tick, 01/10/2026) không phải lần ấy.
        if c.get("lam_them"):
            continue
        if luc and (moi_nhat is None or str(luc) > str(moi_nhat.get("chi_dinh_luc"))):
            moi_nhat = c
    return {
        "so_chi_dinh": len(dong),
        "so_lam": so_lam,
        "so_bo": so_bo,
        "tien_bo": tien_bo,
        "dong": dong,
        # Chỉ BÁC SĨ (29/09/2026); người bấm chỉ định hộ tách riêng.
        "bac_si": (moi_nhat or {}).get("bac_si_chi_dinh"),
        "nguoi_bam": (moi_nhat or {}).get("nguoi_bam_chi_dinh"),
        "lan": (moi_nhat or {}).get("lan_chi_dinh"),
        "luc": (moi_nhat or {}).get("chi_dinh_luc"),
    }


# ---------------------------------------------------------------------------
# Mã phiếu
# ---------------------------------------------------------------------------

_HEX = re.compile(r"[^0-9a-f]")


def ma_phieu(uuid_: Any, loai: str = "thu") -> str:
    """Mã phiếu để ĐỌC / TÌM: "PT-3F2A1B9C" (thu) · "PH-…" (hoàn). Hàm thuần.

    Lấy 8 ký tự đầu của mã lần thu — đủ phân biệt trong sổ một phòng khám, và
    tìm được ngược lại (``tim_theo_ma``). Số phiếu tăng dần theo ngày cần một
    cột mới — chờ Tuyền quyết (xem báo cáo gói).
    """
    s = _HEX.sub("", str(uuid_ or "").lower())[:8].upper()
    return f"{'PH' if loai == 'hoan' else 'PT'}-{s}" if s else ""


def tim_theo_ma(tim: str) -> str | None:
    """Ô tìm có dạng mã phiếu ("PT-3f2a", "ph-3F2A1B9C") → tiền tố hex để so.

    Rác / không phải mã → None (ô tìm vẫn so theo tên / mã khách)."""
    m = re.fullmatch(r"\s*p[th]-?([0-9a-f]{3,8})\s*", (tim or "").lower())
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Bộ lọc lịch sử — đầu vào rác → bỏ qua, không ném
# ---------------------------------------------------------------------------

#: QR gộp vào Chuyển khoản (01/10/2026): lọc / cộng chỉ còn hai hình thức.
HINH_THUC = HINH_THUC_THU
TEN_HINH_THUC = {"CASH": "Tiền mặt", "TRANSFER": "Chuyển khoản", "QR": "Chuyển khoản"}


def doc_hinh_thuc(v: Any) -> str | None:
    """Bộ lọc hình thức: CASH / TRANSFER (QR cũ = TRANSFER); rác → None."""
    return chuan_hinh_thuc(v)


def _phan_cua(c: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Các phần của một lần thu: cột ``phan`` (hàm SQL) nếu có, không thì một
    phần (hình thức, số tiền) — dữ liệu không qua ``phan_thu_hieu_luc``."""
    if c.get("phan") is not None:
        ds = doc_phan_db(c.get("phan"))
        if ds:
            return ds
    return phan_mot_hinh_thuc(c.get("method"), _so(c.get("amount")) or 0)


def doc_tim(v: Any) -> str:
    """Ô tìm: bỏ khoảng trắng thừa, tối đa 80 ký tự; không phải chuỗi → rỗng."""
    if not isinstance(v, str):
        return ""
    return " ".join(v.split())[:80]


# ---------------------------------------------------------------------------
# Gom lịch sử theo khách
# ---------------------------------------------------------------------------


def _iso(v: Any) -> str | None:
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v) if v else None


def gom_theo_khach(
    lan_thu: Iterable[Mapping[str, Any]],
    hoan: Iterable[Mapping[str, Any]],
    khach: Mapping[str, Mapping[str, Any]],
    dong: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    """Mỗi khách (lượt) MỘT dòng; bên trong từng lần thu / hoàn / huỷ. Hàm thuần.

    ``lan_thu``: lần thu đã từng thu (``paid_at``) — PAID hoặc đã huỷ phiếu.
    ``hoan``: khoản hoàn đang chờ / đã hoàn. ``khach``: visit_id → tên, mã,
    số booking / check-in. ``dong``: payment_cycle_id → dòng ảnh chụp hoá đơn.

    Tiền: gốc = mọi lần đã thu; hoàn = khoản hoàn ĐÃ HOÀN + phiếu đã huỷ;
    còn lại = gốc − hoàn. Khoản hoàn còn chờ chuyển hiện ra nhưng chưa trừ.
    """
    nhom: dict[str, dict[str, Any]] = {}

    def lay(vid: str) -> dict[str, Any]:
        if vid not in nhom:
            k = khach.get(vid) or {}
            nhom[vid] = {
                "visit_id": vid,
                "ten": k.get("ten"),
                "ma_bn": k.get("ma_bn"),
                "so_booking": k.get("so_booking"),
                "so_tiep_don": k.get("so_tiep_don"),
                "bac_si": k.get("bac_si"),
                "loai_kham": k.get("loai_kham"),
                "su_kien": [],
                "phieu": [],
                "tong_goc": 0,
                "tong_hoan": 0,
            }
        return nhom[vid]

    for c in lan_thu:
        g = lay(str(c["visit_id"]))
        so_tien = _so(c.get("amount")) or 0
        dv = [str(d.get("ten")) for d in dong.get(str(c["id"]), [])]
        ma = ma_phieu(c["id"])
        phan = _phan_cua(c)
        ht = chuan_hinh_thuc(c.get("method"))
        g["tong_goc"] += so_tien
        g["phieu"].append(
            {
                "id": str(c["id"]),
                "ma": ma,
                "luc": _iso(c.get("paid_at")),
                "trang_thai": c.get("status"),
                "hinh_thuc": ht,
                "phan": phan,
                "nguoi_thu": c.get("nguoi_thu"),
                "tong": so_tien,
                "dong": [
                    {
                        "id": str(d.get("id")),
                        "source_id": d.get("source_id"),
                        "ten": d.get("ten"),
                        "so_luong": float(d.get("so_luong") or 1),
                        "thanh_tien": _so(d.get("thanh_tien")),
                    }
                    for d in dong.get(str(c["id"]), [])
                ],
            }
        )
        g["su_kien"].append(
            {
                "loai": "thu",
                "id": str(c["id"]),
                "luc": _iso(c.get("paid_at")),
                "ma": ma,
                "so_tien": so_tien,
                "hinh_thuc": ht,
                "phan": phan,
                "nhan_hinh_thuc": nhan_phan(phan),
                "nguoi": c.get("nguoi_thu"),
                "dich_vu": dv,
                "ly_do": None,
                "cho": False,
            }
        )
        if c.get("status") == "VOIDED":
            g["tong_hoan"] += so_tien
            g["su_kien"].append(
                {
                    "loai": "huy",
                    "id": str(c["id"]),
                    "luc": _iso(c.get("closed_at")),
                    "ma": ma,
                    "so_tien": -so_tien,
                    "hinh_thuc": ht,
                    "phan": phan,
                    "nhan_hinh_thuc": nhan_phan(phan),
                    "nguoi": c.get("nguoi_huy"),
                    "dich_vu": dv,
                    "ly_do": c.get("close_reason"),
                    "cho": False,
                }
            )

    for r in hoan:
        g = lay(str(r["visit_id"]))
        so_tien = _so(r.get("amount")) or 0
        xong = r.get("status") == "COMPLETED"
        if xong:
            g["tong_hoan"] += so_tien
        g["su_kien"].append(
            {
                "loai": "hoan",
                "id": str(r["refund_id"]),
                "luc": _iso(r.get("created_at")),
                "ma": ma_phieu(r["refund_id"], "hoan"),
                "so_tien": -so_tien,
                "hinh_thuc": chuan_hinh_thuc(r.get("method")),
                "phan": phan_mot_hinh_thuc(r.get("method"), so_tien),
                "nhan_hinh_thuc": nhan_phan(
                    phan_mot_hinh_thuc(r.get("method"), so_tien)
                ),
                "nguoi": r.get("nguoi"),
                "dich_vu": list(r.get("dich_vu") or []),
                "ly_do": r.get("reason"),
                "cho": not xong,
            }
        )

    out: list[dict[str, Any]] = []
    for g in nhom.values():
        g["su_kien"].sort(key=lambda s: s["luc"] or "")
        g["phieu"].sort(key=lambda p: p["luc"] or "")
        thu = [s for s in g["su_kien"] if s["loai"] == "thu"]
        g["dau"] = g["su_kien"][0]["luc"] if g["su_kien"] else None
        g["cuoi"] = g["su_kien"][-1]["luc"] if g["su_kien"] else None
        g["so_phieu"] = len(thu)
        g["ma_phieu_dau"] = thu[0]["ma"] if thu else None
        g["phieu_cuoi_id"] = thu[-1]["id"] if thu else None
        g["hinh_thuc"] = cac_hinh_thuc(p for s in thu for p in s.get("phan") or [])
        g["nguoi_thu"] = sorted({s["nguoi"] for s in thu if s["nguoi"]})
        g["con_lai"] = g["tong_goc"] - g["tong_hoan"]
        g["co_hoan"] = any(s["loai"] in ("hoan", "huy") for s in g["su_kien"])
        g["so_lan_hoan"] = sum(1 for s in g["su_kien"] if s["loai"] in ("hoan", "huy"))
        out.append(g)
    out.sort(key=lambda g: g["cuoi"] or "", reverse=True)
    return out


def tong_lich_su(khach: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """4 ô tổng: Tổng thu (mọi lần đã thu) · Tiền mặt · Chuyển khoản (cộng THEO
    PHẦN — lần thu 200k CK + 500k TM cộng đúng vào hai ô; QR cũ = CK) ·
    Hoàn/huỷ. Thuần."""
    t = {"tong_thu": 0, "CASH": 0, "TRANSFER": 0, "hoan": 0}
    for g in khach:
        for s in g.get("su_kien") or []:
            if s["loai"] == "thu":
                t["tong_thu"] += s["so_tien"]
                phan = s.get("phan") or phan_mot_hinh_thuc(
                    s.get("hinh_thuc"), s["so_tien"]
                )
                for p in phan:
                    ht = chuan_hinh_thuc(p.get("hinh_thuc"))
                    if ht is not None:
                        t[ht] += int(p.get("so_tien") or 0)
            elif not s.get("cho"):
                t["hoan"] += -s["so_tien"]
    return {
        "tong_thu": t["tong_thu"],
        "tien_mat": t["CASH"],
        "chuyen_khoan": t["TRANSFER"],
        "hoan": t["hoan"],
    }


def loc_khach(
    khach: Iterable[Mapping[str, Any]],
    *,
    tim: str = "",
    hinh_thuc: str | None = None,
    nguoi_thu: str | None = None,
) -> list[dict[str, Any]]:
    """Lọc nhóm khách theo ô tìm (tên / mã khách / mã phiếu), hình thức, người
    thu (TÊN người thu như máy chủ trả trong danh sách lọc). Thuần."""
    tim_l = tim.lower()
    tien_to = tim_theo_ma(tim) if tim else None
    out: list[dict[str, Any]] = []
    for g in khach:
        if tim_l:
            trung_ten = (
                tim_l in str(g.get("ten") or "").lower()
                or tim_l in str(g.get("ma_bn") or "").lower()
            )
            trung_ma = any(
                tim_l in str(s.get("ma") or "").lower()
                or (tien_to is not None and str(s.get("id") or "").startswith(tien_to))
                for s in g.get("su_kien") or []
            )
            if not (trung_ten or trung_ma):
                continue
        if hinh_thuc and hinh_thuc not in (g.get("hinh_thuc") or []):
            continue
        if nguoi_thu and nguoi_thu not in (g.get("nguoi_thu") or []):
            continue
        out.append(dict(g))
    return out


def _gio(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return (
            datetime.fromisoformat(iso).astimezone(CLINIC_TZ).strftime("%d/%m/%Y %H:%M")
        )
    except ValueError:
        return ""


_NHAN_LOAI = {"thu": "Thu", "hoan": "Hoàn", "huy": "Huỷ phiếu"}


def csv_lich_su(khach: Iterable[Mapping[str, Any]]) -> str:
    """Tệp CSV mở được bằng Excel: UTF-8 CÓ BOM (Excel đọc đúng dấu tiếng Việt),
    phân cách dấu phẩy, mỗi lần thu / hoàn / huỷ một dòng. Thuần.

    Ô bắt đầu bằng = + - @ bị Excel hiểu là công thức (chèn công thức vào tệp
    xuất là lỗ hổng biết trước) → thêm dấu nháy đơn đứng trước.
    """
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(
        [
            "Ngày giờ",
            "Loại",
            "Mã phiếu",
            "Khách",
            "Mã khách",
            "Booking",
            "Check-in",
            "Hình thức",
            "Người thu",
            "Dịch vụ",
            "Số tiền",
            "Lý do",
        ]
    )
    for g in khach:
        for s in g.get("su_kien") or []:
            # `loai` luôn là chuỗi "thu"/"huy"/"hoan" do lich_su() tự gán; str()
            # chỉ để kiểu của .get(loai, loai) là str chứ không `str | None`.
            loai = str(s["loai"])
            w.writerow(
                [
                    _o(_gio(s.get("luc"))),
                    _o(
                        _NHAN_LOAI.get(loai, loai)
                        + (" (chờ chuyển)" if s.get("cho") else "")
                    ),
                    _o(s.get("ma")),
                    _o(g.get("ten")),
                    _o(g.get("ma_bn")),
                    g.get("so_booking") if g.get("so_booking") is not None else "",
                    g.get("so_tiep_don") if g.get("so_tiep_don") is not None else "",
                    _o(
                        s.get("nhan_hinh_thuc")
                        or TEN_HINH_THUC.get(str(s.get("hinh_thuc")), "")
                    ),
                    _o(s.get("nguoi")),
                    _o(", ".join(s.get("dich_vu") or [])),
                    s.get("so_tien") or 0,
                    _o(s.get("ly_do")),
                ]
            )
    return "﻿" + buf.getvalue()


def _o(v: Any) -> str:
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


# ---------------------------------------------------------------------------
# Đọc DB
# ---------------------------------------------------------------------------

#: Thu tiền (một trong hai khối) — cùng cửa với bảng thu ngân.
QUYEN_THU = ("payment.service.collect", "payment.medicine.collect")

_KHACH_SQL = """
SELECT v.visit_id::text AS visit_id, p.full_name AS ten, p.patient_code AS ma_bn,
       a.so_booking, a.so_tiep_don, d.full_name AS bac_si, st.name AS loai_kham
  FROM visit v
  LEFT JOIN patient p
    ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
  LEFT JOIN appointment a ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
  LEFT JOIN staff d ON d.id = v.attending_doctor_id
  LEFT JOIN service_type st
    ON st.id = coalesce(v.service_type_id, a.service_type_id)
 WHERE v.clinic_id = $1::uuid AND v.visit_id = ANY($2::uuid[])
"""

_DONG_SQL = """
SELECT bl.id::text AS id, bl.payment_cycle_id::text AS cycle_id, bl.source_id,
       bl.source_type, bl.name_snapshot AS ten, bl.quantity AS so_luong,
       bl.line_total AS thanh_tien,
       -- Phiếu ghi "Lần k" của chỉ định và "đã bỏ" khi in lại sau khi bỏ
       -- (06/10/2026, E3) — dòng vẫn in (tiền đã thu là sự thật).
       o.lan_chi_dinh AS lan,
       coalesce(o.exec_status IN ('cancelled', 'not_performed'), false) AS da_bo
  FROM payment_bill_line bl
  LEFT JOIN service_order o
    ON bl.source_type = 'service_order' AND o.clinic_id = bl.clinic_id
   AND o.id::text = bl.source_id
 WHERE bl.clinic_id = $1::uuid AND bl.payment_cycle_id = ANY($2::uuid[])
   AND bl.billing_owner = 'CLINIC'
 ORDER BY bl.source_type = 'exam' DESC, bl.created_at, bl.id
"""

#: Phòng của từng chỉ định trong lượt — để IN trên bill (30/09/2026). Đã xếp
#: (ASSIGNED) thì phòng thật; chưa xếp thì phòng dự kiến (quầy / trưởng ca chọn
#: trước) nếu có.
_PHONG_CHI_DINH_SQL = """
SELECT o.id::text AS id,
       coalesce(rr.name, rd.name) AS ten_phong,
       coalesce(rr.floor, rd.floor) AS tang,
       (rr.id IS NULL AND rd.id IS NOT NULL) AS du_kien,
       rr.id::text AS room_id,
       o.routing_revision,
       -- Bác sĩ quầy chọn trong phòng nhiều bác sĩ (30/09/2026) — in "· BS X".
       bl.full_name AS bac_si_lam,
       -- Đổi phòng ngay trên trang phiếu (30/09/2026): khách đã chốt, chưa bắt
       -- đầu làm, chưa huỷ / không làm. Máy chủ vẫn gác lại khi gửi lệnh.
       (o.selection_status = 'SELECTED'
        AND o.exec_status NOT IN ('in_progress', 'performed', 'cancelled',
                                  'not_performed', 'draft')
        AND coalesce(o.execution_status, 'PENDING') = 'PENDING') AS doi_duoc
  FROM service_order o
  LEFT JOIN clinic_room rr
    ON rr.id = o.room_id AND rr.clinic_id = o.clinic_id
   AND coalesce(o.routing_status, '') = 'ASSIGNED'
  LEFT JOIN clinic_room rd
    ON rd.id = o.phong_du_kien_id AND rd.clinic_id = o.clinic_id
  LEFT JOIN staff bl ON bl.id = o.bac_si_lam_id
 WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
"""


def _phong_cua_dong(
    dong: Mapping[str, Any], phong: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """Phòng in kèm một dòng bill. Thuần. Chỉ dòng DỊCH VỤ (chỉ định) có phòng;
    tiền khám / phụ thu / thuốc không có. Chỉ định chưa có phòng nào (máy vừa
    thu, đang tự xếp) → ``cho_xep`` để bản in hỏi lại sau giây lát."""
    if dong.get("source_type") != "service_order":
        return {}
    r = phong.get(str(dong.get("source_id")))
    # Để trang phiếu cho XẾP / ĐỔI phòng rồi in lại (quên chọn phòng lúc thu).
    xep: dict[str, Any] = (
        {
            "order_id": str(dong.get("source_id")),
            "room_id": r.get("room_id"),
            "routing_revision": r.get("routing_revision"),
            "doi_phong_duoc": bool(r.get("doi_duoc")),
        }
        if r is not None
        else {}
    )
    if r is None or not r["ten_phong"]:
        return {"phong": None, "cho_xep": True, **xep}
    return {
        "phong": {
            "ten": r["ten_phong"],
            "tang": r["tang"],
            "du_kien": bool(r["du_kien"]),
            # Phòng nhiều bác sĩ (30/09/2026): "→ Phòng siêu âm 2 máy · BS X".
            **({"bac_si": ten_bac_si(r["bac_si_lam"])} if r.get("bac_si_lam") else {}),
        },
        "cho_xep": False,
        **xep,
    }


#: Đầu phiếu: tên phòng khám + cơ sở + địa chỉ (cơ sở của lượt, thiếu địa chỉ
#: thì rơi về địa chỉ phòng khám) — như đầu phiếu khám. Cơ sở có `ten_in` (biển
#: pháp nhân riêng, vd Hào Nam "4WOMEN") thì in tên ấy; SĐT cơ sở nối sau.
_DAU_PHIEU_SQL = """
SELECT coalesce(nullif(btrim(lv.ten_in), ''), ck.name) AS phong_kham,
       lv.name AS co_so,
       concat_ws(' · ',
                 coalesce(nullif(btrim(lv.address), ''),
                          nullif(btrim(la.address), ''), ck.address),
                 nullif(btrim(lv.phone), '')) AS dia_chi
  FROM visit v
  JOIN clinic ck ON ck.id = v.clinic_id
  LEFT JOIN appointment a
    ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
  LEFT JOIN clinic_location lv
    ON lv.id = coalesce(v.location_id, a.location_id)
   AND lv.clinic_id = v.clinic_id
  LEFT JOIN patient p
    ON p.clinic_patient_id = v.clinic_patient_id
   AND p.clinic_id = v.clinic_id
  LEFT JOIN clinic_location la
    ON la.id = p.location_id AND la.clinic_id = p.clinic_id
 WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
"""

#: PHIẾU HƯỚNG DẪN (Tuyền 30/09/2026): dịch vụ khách ĐÃ CHỐT làm, chưa làm
#: xong — in cho khách cầm đi đúng phòng, KỂ CẢ khi chưa thu tiền (làm trước,
#: thu sau). Không kèm tiền.
_HUONG_DAN_SQL = """
SELECT o.id::text AS source_id, 'service_order' AS source_type,
       o.service_name AS ten
  FROM service_order o
 WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
   AND o.selection_status = 'SELECTED'
   AND o.exec_status NOT IN ('draft', 'cancelled', 'not_performed', 'performed')
   AND coalesce(o.execution_status, 'PENDING') NOT IN ('COMPLETED', 'CANCELLED',
                                                 'NOT_PERFORMED')
 ORDER BY o.created_at, o.id
"""


async def _phong_lam_duoc_cua_luot(
    conn: asyncpg.Connection, cid: str, visit_id: str
) -> dict[str, list[dict[str, Any]]]:
    """Chỉ định → các phòng đang nhận khách làm được nó, cùng cơ sở (tên + ★)."""
    out: dict[str, list[dict[str, Any]]] = {}
    for r in await conn.fetch(
        """
        SELECT o.id::text AS id, r.name AS ten,
               phong_chuyen(r.clinic_id, r.id, o.node_code, o.service_code)
                   AS chuyen
          FROM service_order o
          JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
          LEFT JOIN appointment a
            ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
          JOIN clinic_room r
            ON r.clinic_id = o.clinic_id AND r.is_active AND r.accepting
           AND NOT r.la_doi_tac
           AND phong_lam_duoc(r.clinic_id, r.id, o.node_code, o.service_code)
           AND (r.location_id IS NULL
                OR coalesce(v.location_id, a.location_id) IS NULL
                OR r.location_id = coalesce(v.location_id, a.location_id))
         WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
         ORDER BY r.sort, r.code
        """,
        cid,
        visit_id,
    ):
        out.setdefault(r["id"], []).append(
            {"id": r["id"], "ten": r["ten"], "chuyen": bool(r["chuyen"])}
        )
    return out


def phong_in_huong_dan(phong: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Phiếu hướng dẫn, chỉ định CHƯA chọn hướng dẫn (dây Nhận tại phòng bật)
    — HÀM THUẦN: đúng MỘT phòng chuyên ★ thì in tên phòng ấy (07/10/2026);
    không thì in "các phòng làm được" như trước."""
    chuyen = [str(p["ten"]) for p in phong if p.get("chuyen")]
    if len(chuyen) == 1:
        return {"phong_chuyen": chuyen[0], "phong_lam_duoc": []}
    return {"phong_chuyen": None, "phong_lam_duoc": [str(p["ten"]) for p in phong]}


def dong_huong_dan(
    dong: Iterable[Mapping[str, Any]], phong: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Dòng phiếu hướng dẫn: tên dịch vụ + phòng, KHÔNG tiền. Thuần."""
    return [
        {
            "ten": d["ten"],
            "so_luong": 1.0,
            "thanh_tien": None,
            **_phong_cua_dong(d, phong),
        }
        for d in dong
    ]


#: Dịch vụ khách trả TRỰC TIẾP cho đối tác của các lượt (giá tham khảo).
_DOI_TAC_SQL = """
SELECT o.id::text AS id, o.visit_id::text AS visit_id, o.service_name AS ten,
       min(pr.unit_price) AS gia
  FROM service_order o
  JOIN service_price pr
    ON pr.clinic_id = o.clinic_id AND pr.service_code = o.service_code
   AND pr.active AND pr."group" = 'dich_vu'
   AND pr.billing_owner = 'EXTERNAL_PARTNER'
 WHERE o.clinic_id = $1::uuid AND o.visit_id = ANY($2::uuid[])
   AND o.selection_status = 'SELECTED'
   AND o.exec_status NOT IN ('draft', 'cancelled', 'not_performed')
 GROUP BY o.id, o.visit_id, o.service_name, o.created_at
 ORDER BY o.created_at, o.id
"""


class QuayThuService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def lich_su(
        self,
        *,
        identity: StaffIdentity,
        tu: Any = None,
        den: Any = None,
        tim: Any = None,
        hinh_thuc: Any = None,
        nguoi_thu: Any = None,
        kind: str = "dich_vu",
        chi_tiet: bool = False,
    ) -> dict[str, Any]:
        """Sổ thu / hoàn GOM THEO KHÁCH trong khoảng ngày (giờ VN). Chỉ đọc.

        Bộ lọc rác (ngày sai, hình thức lạ, người thu không phải tên có trong sổ)
        → bỏ qua bộ lọc ấy, không ném. ``chi_tiet`` (tab Đã thu hôm nay): kèm
        dịch vụ khách trả đối tác, khoản hoàn / dòng còn hoàn được từng phiếu và
        chỉ định đã thu chờ xếp phòng (ô phòng trên dòng).
        """
        a, b = doc_khoang_ngay(tu, den)
        loai = kind if kind in ("dich_vu", "thuoc") else "dich_vu"
        tim_s = doc_tim(tim)
        ht = doc_hinh_thuc(hinh_thuc)
        cid = identity.clinic_id
        co_so = identity.location_id or None
        async with self._pool.acquire() as conn:
            lan_thu = await conn.fetch(
                """
                SELECT pc.payment_cycle_id::text AS id, pc.visit_id::text AS visit_id,
                       pc.status, pc.amount,
                       -- Hình thức HIỆU LỰC (sau mọi lần đổi — V7).
                       hinh_thuc_hieu_luc(pc.clinic_id, pc.payment_cycle_id,
                                          pc.method) AS method,
                       -- Chia TM + CK hiệu lực (01/10/2026).
                       phan_thu_hieu_luc(pc.clinic_id, pc.payment_cycle_id,
                                         pc.method, pc.amount) AS phan,
                       pc.paid_at, pc.closed_at, pc.close_reason,
                       coalesce(xn.full_name, cb.full_name) AS nguoi_thu,
                       dg.full_name AS nguoi_huy
                  FROM payment_cycle pc
                  LEFT JOIN staff cb ON cb.id = pc.created_by
                  LEFT JOIN staff xn ON xn.id = pc.confirmed_by
                  LEFT JOIN staff dg ON dg.id = pc.closed_by
                  LEFT JOIN visit v
                    ON v.visit_id = pc.visit_id AND v.clinic_id = pc.clinic_id
                  LEFT JOIN appointment ah
                    ON ah.id = v.appointment_id AND ah.clinic_id = v.clinic_id
                 WHERE pc.clinic_id = $1::uuid AND pc.kind = $4
                   AND pc.paid_at IS NOT NULL
                   AND (pc.paid_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                       BETWEEN $2 AND $3
                   -- Chỉ sổ của cơ sở đang đứng ($5 NULL = không lọc).
                   AND coalesce(v.location_id, ah.location_id, $5::uuid)
                       IS NOT DISTINCT FROM
                       coalesce($5::uuid, v.location_id, ah.location_id)
                 ORDER BY pc.paid_at
                 LIMIT 3000
                """,
                cid,
                a,
                b,
                loai,
                co_so,
            )
            hoan = await conn.fetch(
                """
                SELECT r.refund_id::text AS refund_id, r.visit_id::text AS visit_id,
                       r.amount, r.status, r.method, r.reason, r.created_at,
                       coalesce(xn.full_name, tao.full_name) AS nguoi,
                       coalesce(array_agg(bl.name_snapshot ORDER BY bl.created_at)
                                FILTER (WHERE bl.id IS NOT NULL), '{}') AS dich_vu
                  FROM payment_refund r
                  LEFT JOIN staff tao ON tao.id = r.created_by
                  LEFT JOIN staff xn ON xn.id = r.completed_by
                  LEFT JOIN payment_refund_line rl
                    ON rl.refund_id = r.refund_id AND rl.clinic_id = r.clinic_id
                  LEFT JOIN payment_bill_line bl
                    ON bl.id = rl.payment_bill_line_id AND bl.clinic_id = rl.clinic_id
                  LEFT JOIN visit v
                    ON v.visit_id = r.visit_id AND v.clinic_id = r.clinic_id
                  LEFT JOIN appointment ah
                    ON ah.id = v.appointment_id AND ah.clinic_id = v.clinic_id
                 WHERE r.clinic_id = $1::uuid AND r.kind = $4
                   AND r.status IN ('PENDING', 'COMPLETED')
                   AND (r.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                       BETWEEN $2 AND $3
                   AND coalesce(v.location_id, ah.location_id, $5::uuid)
                       IS NOT DISTINCT FROM
                       coalesce($5::uuid, v.location_id, ah.location_id)
                 GROUP BY r.refund_id, xn.full_name, tao.full_name
                 ORDER BY r.created_at
                 LIMIT 3000
                """,
                cid,
                a,
                b,
                loai,
                co_so,
            )
            canh_bao_neu_day(
                "quay_thu.lich_su.lan_thu", len(lan_thu), 3000, tu=a, den=b
            )
            canh_bao_neu_day("quay_thu.lich_su.hoan", len(hoan), 3000, tu=a, den=b)
            vids = sorted(
                {r["visit_id"] for r in lan_thu} | {r["visit_id"] for r in hoan}
            )
            khach = {
                r["visit_id"]: dict(r) for r in await conn.fetch(_KHACH_SQL, cid, vids)
            }
            dong: dict[str, list[dict[str, Any]]] = {}
            for r in await conn.fetch(_DONG_SQL, cid, [r["id"] for r in lan_thu]):
                dong.setdefault(r["cycle_id"], []).append(dict(r))
            tat_ca = gom_theo_khach(lan_thu, hoan, khach, dong)
            ds_nguoi = sorted({n for g in tat_ca for n in g["nguoi_thu"]})
            nt = nguoi_thu.strip() if isinstance(nguoi_thu, str) else ""
            loc = loc_khach(
                tat_ca,
                tim=tim_s,
                hinh_thuc=ht,
                nguoi_thu=nt if nt in ds_nguoi else None,
            )
            if chi_tiet and loc:
                await self._chi_tiet(conn, identity, loc, loai)
            # [Đổi hình thức] từng phiếu (V7): cờ + lịch sử đổi do máy chủ quyết.
            gan_vao_lich_su(
                loc,
                await trang_thai_doi(
                    conn, cid, [p["id"] for g in loc for p in g["phieu"]]
                ),
            )
            # Ảnh chuyển khoản + nút Hoàn tác từng lần thu (01/10/2026).
            ids = [p["id"] for g in loc for p in g["phieu"]]
            anh = await anh_cua_cac_lan_thu(conn, cid, ids)
            quyen = await quyen_thu_theo_loai(conn, identity)
            co_hoan_rows = await conn.fetch(
                "SELECT DISTINCT payment_cycle_id::text AS id FROM payment_refund"
                " WHERE clinic_id = $1::uuid AND payment_cycle_id = ANY($2::uuid[])"
                " AND status IN ('PENDING', 'COMPLETED')",
                cid,
                ids,
            )
            co_hoan = {r["id"] for r in co_hoan_rows}
            for g in loc:
                for p in g["phieu"]:
                    p["anh_ck"] = anh.get(p["id"], [])
                    p["hoan_tac"] = hoan_tac_cua(
                        p["trang_thai"],
                        loai,
                        {"khoan_hoan": [{"status": "PENDING"}]}
                        if p["id"] in co_hoan
                        else None,
                        quyen,
                    )
                for s in g["su_kien"]:
                    if s["loai"] == "thu":
                        s["anh_ck"] = anh.get(s["id"], [])
                        s["hoan_tac"] = next(
                            (p["hoan_tac"] for p in g["phieu"] if p["id"] == s["id"]),
                            None,
                        )
            # Huỷ phiếu: cùng quyền thu đúng loại tiền (PaymentService.void_payment).
            co_huy = await can(conn, identity, QUYEN_THU[0 if loai == "dich_vu" else 1])
            # Hoàn tiền theo lego thu đúng loại tiền (Tuyền 06/10/2026, thay HOLD J4).
            from clinicai.services.hoan_tien_service import co_quyen_hoan

            quyen_hoan = await co_quyen_hoan(conn, identity, loai)

        return {
            "tu": a.isoformat(),
            "den": b.isoformat(),
            "tong": tong_lich_su(loc),
            "nguoi_thu": ds_nguoi,
            "khach": loc,
            "co_quyen_hoan": quyen_hoan,
            "co_quyen_huy": co_huy,
        }

    async def _chi_tiet(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        khach: list[dict[str, Any]],
        kind: str = "dich_vu",
    ) -> None:
        from clinicai.services.bill_service import doi_tac_da_thu
        from clinicai.services.hoan_tien_service import hoan_cua_cac_lan_thu
        from clinicai.services.service_routing_service import (
            KHOA_NOI_BO,
            da_tra_cho_vao_phong,
        )

        cid = identity.clinic_id
        vids = [g["visit_id"] for g in khach]
        # Đối tác + phòng làm là chuyện DỊCH VỤ: sổ thuốc không kèm (01/10/2026).
        la_dv = kind == "dich_vu"
        dt_rows = await conn.fetch(_DOI_TAC_SQL, cid, vids) if la_dv else []
        da_thu = await doi_tac_da_thu(conn, cid, [r["id"] for r in dt_rows])
        dt: dict[str, list[dict[str, Any]]] = {}
        for r in dt_rows:
            dt.setdefault(r["visit_id"], []).append(
                {
                    "id": r["id"],
                    "ten": r["ten"],
                    "gia": _so(r["gia"]),
                    "doi_tac_da_thu": da_thu.get(r["id"]),
                }
            )
        hoan = await hoan_cua_cac_lan_thu(
            conn, identity, [p["id"] for g in khach for p in g["phieu"]]
        )
        phong = await da_tra_cho_vao_phong(conn, cid, vids) if la_dv else {}
        pq = PhongQuay(conn, cid)
        for g in khach:
            g["doi_tac"] = dt.get(g["visit_id"], [])
            xep = {x["id"]: x for x in phong.get(g["visit_id"], [])}
            for p in g["phieu"]:
                p["hoan"] = hoan.get(p["id"])
                for d in p["dong"]:
                    x = xep.get(str(d.get("source_id")))
                    if x is None:
                        continue
                    phong_cd = await pq.cua(
                        x.get("node_code"), g["visit_id"], x.get("service_code")
                    )
                    d["xep_phong"] = {
                        **{k: v for k, v in x.items() if k not in KHOA_NOI_BO},
                        "phong_chon_duoc": phong_cd,
                    }

    async def phieu_cua_luot(
        self, *, identity: StaffIdentity, visit_id: str, kind: str
    ) -> dict[str, Any]:
        """Mọi phiếu thu ĐÃ THU (PAID) của một lượt theo loại, cũ trước (28/09).

        Bản in = đúng `phieu()` của từng lần thu — không dựng bản thứ hai.
        """
        ids = await self._pool.fetch(
            "SELECT payment_cycle_id::text AS id FROM payment_cycle"
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND kind = $3"
            " AND status = 'PAID' ORDER BY coalesce(paid_at, created_at), 1",
            identity.clinic_id,
            visit_id,
            kind,
        )
        return {
            "phieu": [
                await self.phieu(identity=identity, id_=r["id"], loai="thu")
                for r in ids
            ]
        }

    async def _phieu_huong_dan(self, *, cid: str, visit_id: str) -> dict[str, Any]:
        """PHIẾU HƯỚNG DẪN của một lượt — cùng khuôn dữ liệu với phiếu thu để
        dùng chung bản in 80mm, nhưng ``id`` là mã LƯỢT và không có tiền."""
        async with self._pool.acquire() as conn:
            dau = await conn.fetchrow(_DAU_PHIEU_SQL, cid, visit_id)
            if dau is None:
                raise NotFoundError("Không tìm thấy lượt khám này.")
            k = await conn.fetchrow(_KHACH_SQL, cid, [visit_id])
            phong = {
                str(r["id"]): r
                for r in await conn.fetch(_PHONG_CHI_DINH_SQL, cid, visit_id)
            }
            dong = dong_huong_dan(
                await conn.fetch(_HUONG_DAN_SQL, cid, visit_id), phong
            )
            # Dây Nhận tại phòng BẬT (07/10/2026): chưa hướng dẫn phòng thì in
            # "các phòng làm được" — khách đến phòng nào, phòng ấy nhận.
            huong_dan = bool(await doc_day(conn, cid, "nhan_tai_phong"))
            if huong_dan:
                lam_duoc = await _phong_lam_duoc_cua_luot(conn, cid, visit_id)
                for d in dong:
                    if d.get("phong") is None and d.get("order_id"):
                        d.update(
                            phong_in_huong_dan(lam_duoc.get(str(d["order_id"]), []))
                        )
        return {
            "id": visit_id,
            "loai": "huong_dan",
            # Dây Nhận tại phòng bật: phòng in ra là HƯỚNG DẪN (không bắt buộc).
            "huong_dan_phong": huong_dan,
            "ma": "",
            "ma_phieu_goc": None,
            "kind": "dich_vu",
            "luc": _iso(datetime.now(CLINIC_TZ)),
            "trang_thai": None,
            "phong_kham": dau["phong_kham"],
            "co_so": dau["co_so"],
            "dia_chi": dau["dia_chi"],
            "khach": k["ten"] if k else None,
            "ma_bn": k["ma_bn"] if k else None,
            "so_booking": k["so_booking"] if k else None,
            "so_tiep_don": k["so_tiep_don"] if k else None,
            "bac_si": k["bac_si"] if k else None,
            "dong": dong,
            "tong": 0,
            "hinh_thuc": None,
            "phan": [],
            "tra_lai": None,
            "nguoi_thu": None,
            "ly_do": None,
            "doi_tac": [],
        }

    async def phieu(
        self, *, identity: StaffIdentity, id_: str, loai: str = "thu"
    ) -> dict[str, Any]:
        """Dữ liệu BẢN IN phiếu thu (``loai=thu``) hoặc phiếu hoàn (``hoan``).

        Chỉ phiếu của đúng phòng khám người gọi; không có → 404 (không nói là
        phiếu của nơi khác). Tên phòng khám + cơ sở + địa chỉ lấy như đầu phiếu
        khám (cơ sở của lượt, thiếu địa chỉ thì rơi về địa chỉ phòng khám).
        """
        cid = identity.clinic_id
        if loai == "huong_dan":
            return await self._phieu_huong_dan(cid=cid, visit_id=id_)
        la_hoan = loai == "hoan"
        async with self._pool.acquire() as conn:
            if la_hoan:
                goc = await conn.fetchrow(
                    """
                    SELECT r.refund_id::text AS id, r.visit_id::text AS visit_id,
                           r.payment_cycle_id::text AS cycle_id, r.kind,
                           r.amount, r.method, r.status, r.reason AS ly_do,
                           coalesce(r.completed_at, r.created_at) AS luc,
                           coalesce(xn.full_name, tao.full_name) AS nguoi
                      FROM payment_refund r
                      LEFT JOIN staff tao ON tao.id = r.created_by
                      LEFT JOIN staff xn ON xn.id = r.completed_by
                     WHERE r.clinic_id = $1::uuid AND r.refund_id = $2::uuid
                    """,
                    cid,
                    id_,
                )
            else:
                goc = await conn.fetchrow(
                    """
                    SELECT pc.payment_cycle_id::text AS id,
                           pc.visit_id::text AS visit_id,
                           pc.payment_cycle_id::text AS cycle_id, pc.kind,
                           pc.amount,
                           hinh_thuc_hieu_luc(pc.clinic_id, pc.payment_cycle_id,
                                              pc.method) AS method,
                           phan_thu_hieu_luc(pc.clinic_id, pc.payment_cycle_id,
                                             pc.method, pc.amount) AS phan,
                           pc.status, pc.close_reason AS ly_do,
                           coalesce(pc.paid_at, pc.created_at) AS luc,
                           coalesce(xn.full_name, cb.full_name) AS nguoi
                      FROM payment_cycle pc
                      LEFT JOIN staff cb ON cb.id = pc.created_by
                      LEFT JOIN staff xn ON xn.id = pc.confirmed_by
                     WHERE pc.clinic_id = $1::uuid AND pc.payment_cycle_id = $2::uuid
                    """,
                    cid,
                    id_,
                )
            if goc is None:
                raise NotFoundError("Không tìm thấy phiếu này.")
            phan_in = (
                doc_phan_db(goc["phan"])
                if not la_hoan
                else phan_mot_hinh_thuc(goc["method"], _so(goc["amount"]) or 0)
            )
            dau = await conn.fetchrow(_DAU_PHIEU_SQL, cid, goc["visit_id"])
            k = await conn.fetchrow(_KHACH_SQL, cid, [goc["visit_id"]])
            if la_hoan:
                dong = [
                    {
                        "ten": r["ten"],
                        "so_luong": float(r["so_luong"]),
                        "thanh_tien": _so(r["thanh_tien"]),
                    }
                    for r in await conn.fetch(
                        """
                        SELECT bl.name_snapshot AS ten, rl.quantity AS so_luong,
                               rl.amount AS thanh_tien
                          FROM payment_refund_line rl
                          JOIN payment_bill_line bl
                            ON bl.id = rl.payment_bill_line_id
                           AND bl.clinic_id = rl.clinic_id
                         WHERE rl.clinic_id = $1::uuid AND rl.refund_id = $2::uuid
                         ORDER BY rl.created_at, rl.id
                        """,
                        cid,
                        id_,
                    )
                ]
                doi_tac: list[dict[str, Any]] = []
            else:
                # PHÒNG làm dịch vụ in ngay trên bill (Tuyền 30/09/2026: "in thêm
                # cả cái phòng chỉ định ra bill luôn cho khách nhìn và đi theo").
                phong = (
                    {
                        str(r["id"]): r
                        for r in await conn.fetch(
                            _PHONG_CHI_DINH_SQL, cid, goc["visit_id"]
                        )
                    }
                    if goc["kind"] == "dich_vu"
                    else {}
                )
                dong = [
                    {
                        "ten": r["ten"],
                        "so_luong": float(r["so_luong"]),
                        "thanh_tien": _so(r["thanh_tien"]),
                        "lan": r["lan"],
                        "da_bo": bool(r["da_bo"]),
                        # Dòng "‹dịch vụ› — trả trước k buổi" in kèm "(liệu
                        # trình)"; số buổi đã nằm trong tên.
                        "lieu_trinh": r["source_type"] == "lieu_trinh",
                        **({} if r["da_bo"] else _phong_cua_dong(r, phong)),
                    }
                    for r in await conn.fetch(_DONG_SQL, cid, [id_])
                ]
                # Dịch vụ khách trả đối tác là tiền DỊCH VỤ — phiếu thuốc không in
                # (thuốc và dịch vụ thu riêng hẳn, Tuyền 01/10/2026).
                doi_tac = (
                    [
                        {"ten": r["ten"], "gia": _so(r["gia"])}
                        for r in await conn.fetch(_DOI_TAC_SQL, cid, [goc["visit_id"]])
                    ]
                    if goc["kind"] == "dich_vu"
                    else []
                )
        return {
            # Mã gốc — mở / in lại đúng phiếu này (in theo lượt, 28/09/2026).
            "id": goc["id"],
            "loai": "hoan" if la_hoan else "thu",
            "ma": ma_phieu(goc["id"], "hoan" if la_hoan else "thu"),
            "ma_phieu_goc": ma_phieu(goc["cycle_id"]) if la_hoan else None,
            "kind": goc["kind"],
            "luc": _iso(goc["luc"]),
            "trang_thai": goc["status"],
            "phong_kham": dau["phong_kham"] if dau else None,
            "co_so": dau["co_so"] if dau else None,
            "dia_chi": dau["dia_chi"] if dau else None,
            "khach": k["ten"] if k else None,
            "ma_bn": k["ma_bn"] if k else None,
            "so_booking": k["so_booking"] if k else None,
            "so_tiep_don": k["so_tiep_don"] if k else None,
            "bac_si": k["bac_si"] if k else None,
            "dong": dong,
            "tong": _so(goc["amount"]) or 0,
            "hinh_thuc": chuan_hinh_thuc(goc["method"]),
            # Bản in có DÒNG HÌNH THỨC từng phần (01/10/2026: 200k CK + 500k TM
            # in thành hai dòng) + tiền khách đưa / trả lại nếu có.
            "phan": phan_in,
            "tra_lai": tra_lai(phan_in),
            "nguoi_thu": goc["nguoi"],
            "ly_do": goc["ly_do"],
            "doi_tac": doi_tac,
        }
