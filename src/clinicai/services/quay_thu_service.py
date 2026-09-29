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
from clinicai.services.cashier_board_service import doc_khoang_ngay

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

    Đúng tập của dây H4 (cùng cơ sở, còn nhận khách, làm được bước này, không
    phải phòng đối tác) — `eligible_rooms` + `rank_rooms` — rồi vắng nhất lên
    đầu. Dùng cho CẢ ô "phòng dự kiến" (trước thu) lẫn ô xếp phòng sau thu.
    """

    def __init__(self, conn: asyncpg.Connection, clinic_id: str) -> None:
        self._conn = conn
        self._clinic_id = clinic_id
        self._ten: dict[str, str] | None = None
        self._nho: dict[tuple[str, str | None, str], list[dict[str, Any]]] = {}

    async def cua(self, node: str | None, visit_id: str) -> list[dict[str, Any]]:
        if not node:
            return []
        from clinicai.services.service_routing_service import (
            co_so_cua_luot,
            eligible_rooms,
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
        khoa = (node, co_so, visit_id)
        if khoa not in self._nho:
            ung_vien = rank_rooms(
                await eligible_rooms(
                    self._conn, self._clinic_id, node, co_so, tru_luot=visit_id
                )
            )
            self._nho[khoa] = xep_vang_nhat(
                [
                    {
                        "id": u["room_id"],
                        "ten": self._ten.get(u["room_id"], "Phòng"),
                        "dang_cho": u["queue_load"],
                    }
                    for u in ung_vien
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
      * chỉ định còn chờ khách quyết — tick được (trừ "Bắt buộc"); bỏ tick =
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

    # Phụ thu kèm dịch vụ (đầu dò…, 28/09/2026): tick / sửa giá ở khối riêng
    # (`PhuThuKem`); trong hoá đơn là dòng khoá như tiền khám.
    phu_thu_quay: list[dict[str, Any]] = [
        {
            "id": str(d["source_id"]),
            "loai": "phu_thu",
            "ten": d.get("ten"),
            "gia": _so(d.get("thanh_tien")),
            "van_de": d.get("van_de"),
            "chon": True,
            "sua_duoc": False,
            "trong_lua_chon": False,
        }
        for d in hd.get("dong") or []
        if d.get("source_type") == "phu_thu"
    ]

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
            "sua_duoc": not c.get("bat_buoc"),
            "trong_lua_chon": True,
            "bat_buoc": bool(c.get("bat_buoc")),
            "mang_sang": bool(c.get("mang_sang")),
            "doi_tac_lam": bool(c.get("doi_tac")),
            "phong_chon_duoc": list(c.get("phong_chon_duoc") or []),
            "phong_du_kien_id": c.get("phong_du_kien_id"),
            "can_xep_phong": bool(c.get("phong_chon_duoc")),
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
        if d.get("source_type") in ("exam", "phu_thu") or sid in theo_id:
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
            }
        )
        luc = c.get("chi_dinh_luc")
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

HINH_THUC = ("CASH", "TRANSFER", "QR")
TEN_HINH_THUC = {"CASH": "Tiền mặt", "TRANSFER": "Chuyển khoản", "QR": "QR"}


def doc_hinh_thuc(v: Any) -> str | None:
    s = v.strip().upper() if isinstance(v, str) else ""
    return s if s in HINH_THUC else None


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
        g["tong_goc"] += so_tien
        g["phieu"].append(
            {
                "id": str(c["id"]),
                "ma": ma,
                "luc": _iso(c.get("paid_at")),
                "trang_thai": c.get("status"),
                "hinh_thuc": c.get("method"),
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
                "hinh_thuc": c.get("method"),
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
                    "hinh_thuc": c.get("method"),
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
                "hinh_thuc": r.get("method"),
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
        g["hinh_thuc"] = sorted({s["hinh_thuc"] for s in thu if s["hinh_thuc"]})
        g["nguoi_thu"] = sorted({s["nguoi"] for s in thu if s["nguoi"]})
        g["con_lai"] = g["tong_goc"] - g["tong_hoan"]
        g["co_hoan"] = any(s["loai"] in ("hoan", "huy") for s in g["su_kien"])
        g["so_lan_hoan"] = sum(1 for s in g["su_kien"] if s["loai"] in ("hoan", "huy"))
        out.append(g)
    out.sort(key=lambda g: g["cuoi"] or "", reverse=True)
    return out


def tong_lich_su(khach: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """5 ô tổng: Tổng thu (mọi lần đã thu) · theo hình thức · Hoàn/huỷ. Thuần."""
    t = {"tong_thu": 0, "CASH": 0, "TRANSFER": 0, "QR": 0, "hoan": 0}
    for g in khach:
        for s in g.get("su_kien") or []:
            if s["loai"] == "thu":
                t["tong_thu"] += s["so_tien"]
                if s.get("hinh_thuc") in HINH_THUC:
                    t[s["hinh_thuc"]] += s["so_tien"]
            elif not s.get("cho"):
                t["hoan"] += -s["so_tien"]
    return {
        "tong_thu": t["tong_thu"],
        "tien_mat": t["CASH"],
        "chuyen_khoan": t["TRANSFER"],
        "qr": t["QR"],
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
            w.writerow(
                [
                    _o(_gio(s.get("luc"))),
                    _o(
                        _NHAN_LOAI.get(s["loai"], s["loai"])
                        + (" (chờ chuyển)" if s.get("cho") else "")
                    ),
                    _o(s.get("ma")),
                    _o(g.get("ten")),
                    _o(g.get("ma_bn")),
                    g.get("so_booking") if g.get("so_booking") is not None else "",
                    g.get("so_tiep_don") if g.get("so_tiep_don") is not None else "",
                    _o(TEN_HINH_THUC.get(str(s.get("hinh_thuc")), "")),
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
       bl.line_total AS thanh_tien
  FROM payment_bill_line bl
 WHERE bl.clinic_id = $1::uuid AND bl.payment_cycle_id = ANY($2::uuid[])
   AND bl.billing_owner = 'CLINIC'
 ORDER BY bl.source_type = 'exam' DESC, bl.created_at, bl.id
"""

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
        async with self._pool.acquire() as conn:
            lan_thu = await conn.fetch(
                """
                SELECT pc.payment_cycle_id::text AS id, pc.visit_id::text AS visit_id,
                       pc.status, pc.amount, pc.method, pc.paid_at, pc.closed_at,
                       pc.close_reason,
                       coalesce(xn.full_name, cb.full_name) AS nguoi_thu,
                       dg.full_name AS nguoi_huy
                  FROM payment_cycle pc
                  LEFT JOIN staff cb ON cb.id = pc.created_by
                  LEFT JOIN staff xn ON xn.id = pc.confirmed_by
                  LEFT JOIN staff dg ON dg.id = pc.closed_by
                 WHERE pc.clinic_id = $1::uuid AND pc.kind = $4
                   AND pc.paid_at IS NOT NULL
                   AND (pc.paid_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                       BETWEEN $2 AND $3
                 ORDER BY pc.paid_at
                 LIMIT 3000
                """,
                cid,
                a,
                b,
                loai,
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
                 WHERE r.clinic_id = $1::uuid AND r.kind = $4
                   AND r.status IN ('PENDING', 'COMPLETED')
                   AND (r.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                       BETWEEN $2 AND $3
                 GROUP BY r.refund_id, xn.full_name, tao.full_name
                 ORDER BY r.created_at
                 LIMIT 3000
                """,
                cid,
                a,
                b,
                loai,
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
                await self._chi_tiet(conn, identity, loc)
            # Huỷ phiếu: cùng quyền thu đúng loại tiền (PaymentService.void_payment).
            co_huy = await can(conn, identity, QUYEN_THU[0 if loai == "dich_vu" else 1])
        from clinicai.services.hoan_tien_service import co_quyen_hoan

        return {
            "tu": a.isoformat(),
            "den": b.isoformat(),
            "tong": tong_lich_su(loc),
            "nguoi_thu": ds_nguoi,
            "khach": loc,
            "co_quyen_hoan": co_quyen_hoan(identity),
            "co_quyen_huy": co_huy,
        }

    async def _chi_tiet(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        khach: list[dict[str, Any]],
    ) -> None:
        from clinicai.services.bill_service import doi_tac_da_thu
        from clinicai.services.hoan_tien_service import hoan_cua_cac_lan_thu
        from clinicai.services.service_routing_service import da_tra_cho_vao_phong

        cid = identity.clinic_id
        vids = [g["visit_id"] for g in khach]
        dt_rows = await conn.fetch(_DOI_TAC_SQL, cid, vids)
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
        phong = await da_tra_cho_vao_phong(conn, cid, vids)
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
                    phong_cd = await pq.cua(x.get("node_code"), g["visit_id"])
                    d["xep_phong"] = {
                        **{k: v for k, v in x.items() if k != "node_code"},
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

    async def phieu(
        self, *, identity: StaffIdentity, id_: str, loai: str = "thu"
    ) -> dict[str, Any]:
        """Dữ liệu BẢN IN phiếu thu (``loai=thu``) hoặc phiếu hoàn (``hoan``).

        Chỉ phiếu của đúng phòng khám người gọi; không có → 404 (không nói là
        phiếu của nơi khác). Tên phòng khám + cơ sở + địa chỉ lấy như đầu phiếu
        khám (cơ sở của lượt, thiếu địa chỉ thì rơi về địa chỉ phòng khám).
        """
        cid = identity.clinic_id
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
                           pc.amount, pc.method, pc.status, pc.close_reason AS ly_do,
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
            dau = await conn.fetchrow(
                """
                SELECT ck.name AS phong_kham, lv.name AS co_so,
                       coalesce(nullif(btrim(lv.address), ''),
                                nullif(btrim(la.address), ''), ck.address) AS dia_chi
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
                """,
                cid,
                goc["visit_id"],
            )
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
                dong = [
                    {
                        "ten": r["ten"],
                        "so_luong": float(r["so_luong"]),
                        "thanh_tien": _so(r["thanh_tien"]),
                    }
                    for r in await conn.fetch(_DONG_SQL, cid, [id_])
                ]
                doi_tac = [
                    {"ten": r["ten"], "gia": _so(r["gia"])}
                    for r in await conn.fetch(_DOI_TAC_SQL, cid, [goc["visit_id"]])
                ]
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
            "hinh_thuc": goc["method"],
            "nguoi_thu": goc["nguoi"],
            "ly_do": goc["ly_do"],
            "doi_tac": doi_tac,
        }
