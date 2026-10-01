"""Báo cáo cuối ngày — tài chính kiểu KiotViet (Bán hàng / Thu chi). CHỈ ĐỌC.

Nguồn sự thật tiền là ``payment_cycle`` (mỗi lần thu) + ``payment_bill_line``
(ảnh chụp hoá đơn) + ``payment_refund`` (hoàn) — cùng sổ mà tab Lịch sử của
quầy thu (``quay_thu_service.lich_su``) đọc, cùng luật cộng trừ để hai màn
không lệch nhau:

* **Thu gốc** = mọi lần đã thu (PAID + đã huỷ phiếu) có ``paid_at`` trong khoảng
  (ngày theo giờ VN). Phiếu huỷ tính vào NGÀY THU của nó.
* **Huỷ phiếu** = lần thu đã VOIDED trong tập trên.
* **Hoàn** = khoản hoàn ĐÃ HOÀN (COMPLETED) tạo trong khoảng. Khoản còn CHỜ
  chuyển hiện ra danh sách nhưng không trừ.
* **Thực thu** = thu gốc − huỷ − hoàn.

Hình thức (TM / CK / QR) là hình thức HIỆU LỰC — sau mọi lần đổi hình thức
(V7, ``payment_cycle_doi_hinh_thuc``), không phải hình thức ghi lúc thu. Mục
riêng **Đổi hình thức** liệt kê các lần đổi trong khoảng (ai, lúc nào, từ →
sang); đổi hình thức KHÔNG phải huỷ, không trừ vào đâu.

Đối tác thu hộ (``doi_tac_thanh_toan``): khách trả thẳng đối tác — chỉ để
tham khảo, KHÔNG cộng vào thực thu.

Hàm thuần ``gom_bao_cao`` có test không cần DB
(``tests/unit/test_bao_cao_cuoi_ngay.py``).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.tran import canh_bao_neu_day
from clinicai.services.cashier_board_service import doc_khoang_ngay
from clinicai.services.phan_thu import (
    HINH_THUC_THU,
    chuan_hinh_thuc,
    doc_phan_db,
    nhan_phan,
    phan_mot_hinh_thuc,
)

#: Hai hình thức (01/10/2026): QR cũ cộng vào Chuyển khoản. Một lần thu chia
#: TM + CK cộng ĐÚNG từng phần vào từng dòng hình thức.
HINH_THUC = HINH_THUC_THU
TEN_HINH_THUC = {"CASH": "Tiền mặt", "TRANSFER": "Chuyển khoản", "QR": "Chuyển khoản"}


def _phan(c: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Các phần của lần thu: cột ``phan`` (hàm SQL) nếu có; không thì một phần."""
    ds = doc_phan_db(c.get("phan")) if c.get("phan") is not None else []
    return ds or phan_mot_hinh_thuc(c.get("method"), _tien(c.get("amount")))


def _nhan_doi(ma: object, tien_mat: object, chuyen_khoan: object) -> str:
    """ "Tiền mặt" / "Chuyển khoản" / "Tiền mặt X + Chuyển khoản Y" (đổi sang chia)."""
    if tien_mat is not None and chuyen_khoan is not None:
        return nhan_phan(
            [
                {"hinh_thuc": "CASH", "so_tien": _tien(tien_mat)},
                {"hinh_thuc": "TRANSFER", "so_tien": _tien(chuyen_khoan)},
            ]
        )
    return TEN_HINH_THUC.get(str(ma), "")


TEN_LOAI = {"dich_vu": "Dịch vụ", "thuoc": "Thuốc / vật tư"}
_TRAN = 5000


def doc_khoang(tu: Any, den: Any) -> tuple[date, date]:
    """Ngày rác / rỗng → hôm nay (giờ VN); đảo chiều thì đổi chỗ. Không ném."""
    return doc_khoang_ngay(tu, den)


def _tien(v: Any) -> int:
    if v is None:
        return 0
    if isinstance(v, (int, Decimal, float)):
        return int(v)
    try:
        return int(Decimal(str(v)))
    except Exception:  # noqa: BLE001 — số rác từ DB không làm sập báo cáo
        return 0


def _ngay_vn(v: Any) -> str | None:
    if isinstance(v, datetime):
        return v.astimezone(CLINIC_TZ).date().isoformat()
    return None


def _iso(v: Any) -> str | None:
    return v.isoformat() if isinstance(v, datetime) else None


def _o_tien() -> dict[str, int]:
    return {"thu": 0, "huy": 0, "hoan": 0, "thuc_thu": 0}


def _chot(o: dict[str, int]) -> dict[str, int]:
    o["thuc_thu"] = o["thu"] - o["huy"] - o["hoan"]
    return o


def gom_bao_cao(
    *,
    tu: date,
    den: date,
    lan_thu: Iterable[Mapping[str, Any]],
    hoan: Iterable[Mapping[str, Any]],
    dong: Iterable[Mapping[str, Any]],
    doi_tac: Iterable[Mapping[str, Any]],
    so_luot_kham: int,
    doi_hinh_thuc: Iterable[Mapping[str, Any]] = (),
    so_luot_khong_chon_dich_vu_kham: int = 0,
) -> dict[str, Any]:
    """Gom mọi con số của báo cáo. Thuần — chỉ cộng những gì DB trả.

    ``lan_thu``: lần thu PAID/VOIDED có paid_at trong khoảng. ``hoan``: khoản
    hoàn PENDING/COMPLETED tạo trong khoảng. ``dong``: dòng hoá đơn (CLINIC) của
    các lần thu ấy, kèm ``cycle_id``. ``doi_tac``: ghi nhận đối tác đã thu còn
    hiệu lực trong khoảng. ``doi_hinh_thuc``: các lần đổi hình thức ghi trong
    khoảng (``method`` của ``lan_thu`` đã là hình thức hiệu lực).
    """
    lan_thu = list(lan_thu)
    hoan = list(hoan)
    tong = _o_tien()
    tong.update(
        {"hoan_cho": 0, "so_phieu_thu": 0, "so_phieu_huy": 0, "so_phieu_hoan": 0}
    )
    theo_ht: dict[str, dict[str, int]] = {m: _o_tien() for m in (*HINH_THUC, "KHAC")}
    theo_loai: dict[str, dict[str, int]] = {k: _o_tien() for k in TEN_LOAI}
    theo_nguoi: dict[str, dict[str, Any]] = {}
    theo_ngay: dict[str, dict[str, int]] = {}
    ds_hoan_huy: list[dict[str, Any]] = []
    luot_da_thu: set[str] = set()
    luot_ban_le: set[str] = set()
    khach_da_thu: set[str] = set()
    cycle_paid: set[str] = set()

    def ngay_o(n: str | None) -> dict[str, int] | None:
        if n is None:
            return None
        if n not in theo_ngay:
            theo_ngay[n] = {**_o_tien(), "so_phieu": 0}
        return theo_ngay[n]

    for c in lan_thu:
        so = _tien(c.get("amount"))
        phan = _phan(c)
        loai = c.get("kind") if c.get("kind") in TEN_LOAI else None
        nguoi = str(c.get("nguoi_thu") or "Không rõ")
        huy = c.get("status") == "VOIDED"
        n = theo_nguoi.setdefault(nguoi, {"ten": nguoi, "so_phieu": 0, **_o_tien()})
        d = ngay_o(_ngay_vn(c.get("paid_at")))
        for o in (tong, n, *([theo_loai[loai]] if loai else [])):
            o["thu"] += so
            if huy:
                o["huy"] += so
        # Theo hình thức: cộng TỪNG PHẦN (200k CK + 500k TM → hai dòng).
        for p in phan:
            o = theo_ht[chuan_hinh_thuc(p.get("hinh_thuc")) or "KHAC"]
            o["thu"] += _tien(p.get("so_tien"))
            if huy:
                o["huy"] += _tien(p.get("so_tien"))
        tong["so_phieu_thu"] += 1
        n["so_phieu"] += 1
        if d is not None:
            d["thu"] += so
            d["so_phieu"] += 1
            if huy:
                d["huy"] += so
        if huy:
            tong["so_phieu_huy"] += 1
            ds_hoan_huy.append(
                {
                    "loai": "huy",
                    "id": str(c.get("id")),
                    "luc": _iso(c.get("closed_at")),
                    "khach": c.get("ten_khach"),
                    "ma_bn": c.get("ma_bn"),
                    "loai_tien": loai,
                    "hinh_thuc": chuan_hinh_thuc(c.get("method")),
                    "nhan_hinh_thuc": nhan_phan(phan),
                    "so_tien": so,
                    "nguoi": c.get("nguoi_huy"),
                    "ly_do": c.get("close_reason"),
                    "cho": False,
                }
            )
        else:
            cycle_paid.add(str(c.get("id")))
            if c.get("visit_id"):
                # V8: lượt BÁN LẺ không phải lượt khám — tiền thuốc vẫn cộng ở
                # trên, nhưng đếm riêng, không vào "lượt đã thu".
                if c.get("ban_le"):
                    luot_ban_le.add(str(c["visit_id"]))
                else:
                    luot_da_thu.add(str(c["visit_id"]))
            if c.get("khach_id"):
                khach_da_thu.add(str(c["khach_id"]))

    for r in hoan:
        so = _tien(r.get("amount"))
        xong = r.get("status") == "COMPLETED"
        loai = r.get("kind") if r.get("kind") in TEN_LOAI else None
        ht = chuan_hinh_thuc(r.get("method")) or "KHAC"
        if xong:
            tong["hoan"] += so
            tong["so_phieu_hoan"] += 1
            theo_ht[ht]["hoan"] += so
            if loai:
                theo_loai[loai]["hoan"] += so
            d = ngay_o(_ngay_vn(r.get("created_at")))
            if d is not None:
                d["hoan"] += so
        else:
            tong["hoan_cho"] += so
        ds_hoan_huy.append(
            {
                "loai": "hoan",
                "id": str(r.get("refund_id")),
                "luc": _iso(r.get("created_at")),
                "khach": r.get("ten_khach"),
                "ma_bn": r.get("ma_bn"),
                "loai_tien": loai,
                "hinh_thuc": chuan_hinh_thuc(r.get("method")),
                "nhan_hinh_thuc": TEN_HINH_THUC.get(str(r.get("method")), ""),
                "so_tien": so,
                "nguoi": r.get("nguoi"),
                "ly_do": r.get("reason"),
                "cho": not xong,
            }
        )

    # Top dịch vụ: dòng hoá đơn của lần thu CÒN HIỆU LỰC (không tính phiếu huỷ),
    # doanh thu gộp — chưa trừ hoàn từng dòng.
    top: dict[str, dict[str, Any]] = {}
    for ln in dong:
        if str(ln.get("cycle_id")) not in cycle_paid:
            continue
        if ln.get("source_type") == "prescription":
            continue
        ten = str(ln.get("ten") or "Không tên")
        t = top.setdefault(ten, {"ten": ten, "so_luong": 0.0, "doanh_thu": 0})
        t["so_luong"] += float(ln.get("so_luong") or 1)
        t["doanh_thu"] += _tien(ln.get("thanh_tien"))
    top_ds = sorted(top.values(), key=lambda t: (-t["doanh_thu"], t["ten"]))[:10]

    dt_ds = [
        {
            "id": str(r.get("id")),
            "luc": _iso(r.get("ghi_luc")),
            "khach": r.get("ten_khach"),
            "ma_bn": r.get("ma_bn"),
            "dich_vu": r.get("ten"),
            "so_tien": _tien(r.get("so_tien")),
            "hinh_thuc": r.get("hinh_thuc"),
            "nguoi": r.get("nguoi"),
        }
        for r in doi_tac
    ]

    doi_ds = [
        {
            "id": str(r.get("id")),
            "cycle_id": str(r.get("cycle_id")),
            "luc": _iso(r.get("luc")),
            "khach": r.get("ten_khach"),
            "ma_bn": r.get("ma_bn"),
            "loai_tien": r.get("kind") if r.get("kind") in TEN_LOAI else None,
            "tu": r.get("method_cu"),
            "sang": r.get("method_moi"),
            # Đổi sang CHIA (01/10/2026): hai số; null = một hình thức.
            "tien_mat": r.get("tien_mat"),
            "chuyen_khoan": r.get("chuyen_khoan"),
            "nhan_sang": _nhan_doi(
                r.get("method_moi"), r.get("tien_mat"), r.get("chuyen_khoan")
            ),
            "so_tien": _tien(r.get("amount")),
            "nguoi": r.get("nguoi"),
            "ly_do": r.get("ly_do"),
        }
        for r in doi_hinh_thuc
    ]

    ngay_ds: list[dict[str, Any]] = []
    if tu != den:
        ngay = tu
        while ngay <= den:
            k = ngay.isoformat()
            o = theo_ngay.get(k) or {**_o_tien(), "so_phieu": 0}
            ngay_ds.append({"ngay": k, **_chot(o)})
            ngay += timedelta(days=1)

    ds_hoan_huy.sort(key=lambda s: s["luc"] or "")
    _chot(tong)
    return {
        "tu": tu.isoformat(),
        "den": den.isoformat(),
        "tong": tong,
        "theo_hinh_thuc": [
            {"ma": m, "ten": TEN_HINH_THUC.get(m, "Khác (dữ liệu cũ)"), **_chot(o)}
            for m, o in theo_ht.items()
            if m != "KHAC" or any(o.values())
        ],
        "theo_loai": [
            {"ma": k, "ten": TEN_LOAI[k], **_chot(o)} for k, o in theo_loai.items()
        ],
        "theo_nguoi_thu": sorted(
            (_chot(n) for n in theo_nguoi.values()),
            key=lambda n: (-n["thuc_thu"], n["ten"]),
        ),
        "hoan_huy": ds_hoan_huy,
        "khach": {
            "so_luot_kham": int(so_luot_kham),
            "so_luot_khong_chon_dich_vu_kham": int(so_luot_khong_chon_dich_vu_kham),
            "so_luot_da_thu": len(luot_da_thu),
            "so_luot_ban_le": len(luot_ban_le),
            "so_khach_da_thu": len(khach_da_thu),
        },
        "doi_tac": {"tong": sum(d["so_tien"] for d in dt_ds), "dong": dt_ds},
        "doi_hinh_thuc": doi_ds,
        "top_dich_vu": top_ds,
        "theo_ngay": ngay_ds,
    }


# ---------------------------------------------------------------------------
# CSV — UTF-8 có BOM, cùng kiểu `csv_lich_su`
# ---------------------------------------------------------------------------


def _o(v: Any) -> str:
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


def csv_bao_cao(bc: Mapping[str, Any]) -> str:
    """Tệp Excel đọc được: các khối số liền nhau, mỗi khối có dòng tiêu đề."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    t = bc["tong"]
    w.writerow(["BÁO CÁO CUỐI NGÀY", f"{bc['tu']} → {bc['den']}"])
    w.writerow([])
    w.writerow(["Tổng", "Thu gốc", "Huỷ phiếu", "Hoàn", "Thực thu", "Hoàn chờ chuyển"])
    w.writerow(["", t["thu"], t["huy"], t["hoan"], t["thuc_thu"], t["hoan_cho"]])
    w.writerow([])
    w.writerow(["Lượt khám", bc["khach"]["so_luot_kham"]])
    w.writerow(
        [
            "Lượt không chọn dịch vụ khám",
            bc["khach"]["so_luot_khong_chon_dich_vu_kham"],
        ]
    )
    for tieu_de, khoi in (
        ("Hình thức", bc["theo_hinh_thuc"]),
        ("Loại", bc["theo_loai"]),
        ("Người thu", bc["theo_nguoi_thu"]),
    ):
        w.writerow([])
        w.writerow([tieu_de, "Thu gốc", "Huỷ phiếu", "Hoàn", "Thực thu"])
        for o in khoi:
            w.writerow([_o(o["ten"]), o["thu"], o["huy"], o["hoan"], o["thuc_thu"]])
    if bc["theo_ngay"]:
        w.writerow([])
        w.writerow(["Ngày", "Số phiếu", "Thu gốc", "Huỷ phiếu", "Hoàn", "Thực thu"])
        for o in bc["theo_ngay"]:
            w.writerow(
                [o["ngay"], o["so_phieu"], o["thu"], o["huy"], o["hoan"], o["thuc_thu"]]
            )
    w.writerow([])
    w.writerow(["Top dịch vụ", "Số lượng", "Doanh thu gộp"])
    for o in bc["top_dich_vu"]:
        w.writerow([_o(o["ten"]), o["so_luong"], o["doanh_thu"]])
    w.writerow([])
    w.writerow(
        [
            "Hoàn / huỷ",
            "Lúc",
            "Khách",
            "Mã khách",
            "Hình thức",
            "Số tiền",
            "Người",
            "Lý do",
        ]
    )
    for o in bc["hoan_huy"]:
        nhan = (
            "Huỷ phiếu"
            if o["loai"] == "huy"
            else "Hoàn" + (" (chờ chuyển)" if o["cho"] else "")
        )
        w.writerow(
            [
                nhan,
                _gio(o["luc"]),
                _o(o["khach"]),
                _o(o["ma_bn"]),
                o.get("nhan_hinh_thuc") or TEN_HINH_THUC.get(str(o["hinh_thuc"]), ""),
                o["so_tien"],
                _o(o["nguoi"]),
                _o(o["ly_do"]),
            ]
        )
    w.writerow([])
    w.writerow(
        ["Đổi hình thức (không phải huỷ)", "Lúc", "Khách", "Mã khách", "Từ", "Sang"]
        + ["Số tiền", "Người đổi", "Lý do"]
    )
    for o in bc.get("doi_hinh_thuc") or []:
        w.writerow(
            [
                TEN_LOAI.get(str(o["loai_tien"]), ""),
                _gio(o["luc"]),
                _o(o["khach"]),
                _o(o["ma_bn"]),
                TEN_HINH_THUC.get(str(o["tu"]), "Không rõ"),
                o.get("nhan_sang") or TEN_HINH_THUC.get(str(o["sang"]), ""),
                o["so_tien"],
                _o(o["nguoi"]),
                _o(o["ly_do"]),
            ]
        )
    w.writerow([])
    w.writerow(
        [
            "Đối tác thu hộ (tham khảo, không cộng)",
            "Lúc",
            "Khách",
            "Số tiền",
            "Hình thức",
        ]
    )
    for o in bc["doi_tac"]["dong"]:
        w.writerow(
            [
                _o(o["dich_vu"]),
                _gio(o["luc"]),
                _o(o["khach"]),
                o["so_tien"],
                TEN_HINH_THUC.get(str(o["hinh_thuc"]), ""),
            ]
        )
    return "﻿" + buf.getvalue()


def _gio(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return (
            datetime.fromisoformat(iso).astimezone(CLINIC_TZ).strftime("%d/%m/%Y %H:%M")
        )
    except ValueError:
        return ""


# ---------------------------------------------------------------------------
# Đọc DB
# ---------------------------------------------------------------------------

_LAN_THU_SQL = """
SELECT pc.payment_cycle_id::text AS id, pc.visit_id::text AS visit_id, pc.kind,
       pc.status, pc.amount,
       hinh_thuc_hieu_luc(pc.clinic_id, pc.payment_cycle_id, pc.method) AS method,
       phan_thu_hieu_luc(pc.clinic_id, pc.payment_cycle_id, pc.method, pc.amount)
           AS phan,
       pc.paid_at, pc.closed_at, pc.close_reason,
       coalesce(xn.full_name, cb.full_name) AS nguoi_thu, dg.full_name AS nguoi_huy,
       v.clinic_patient_id::text AS khach_id, p.full_name AS ten_khach,
       p.patient_code AS ma_bn, coalesce(v.ban_le, false) AS ban_le
  FROM payment_cycle pc
  LEFT JOIN staff cb ON cb.id = pc.created_by
  LEFT JOIN staff xn ON xn.id = pc.confirmed_by
  LEFT JOIN staff dg ON dg.id = pc.closed_by
  LEFT JOIN visit v ON v.visit_id = pc.visit_id AND v.clinic_id = pc.clinic_id
  LEFT JOIN patient p
    ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
 WHERE pc.clinic_id = $1::uuid AND pc.status IN ('PAID', 'VOIDED')
   AND pc.paid_at IS NOT NULL
   AND (pc.paid_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date BETWEEN $2 AND $3
 ORDER BY pc.paid_at
 LIMIT 5000
"""

_HOAN_SQL = """
SELECT r.refund_id::text AS refund_id, r.visit_id::text AS visit_id, r.kind,
       r.amount, r.status, r.method, r.reason, r.created_at,
       coalesce(xn.full_name, tao.full_name) AS nguoi,
       p.full_name AS ten_khach, p.patient_code AS ma_bn
  FROM payment_refund r
  LEFT JOIN staff tao ON tao.id = r.created_by
  LEFT JOIN staff xn ON xn.id = r.completed_by
  LEFT JOIN visit v ON v.visit_id = r.visit_id AND v.clinic_id = r.clinic_id
  LEFT JOIN patient p
    ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
 WHERE r.clinic_id = $1::uuid AND r.status IN ('PENDING', 'COMPLETED')
   AND (r.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date BETWEEN $2 AND $3
 ORDER BY r.created_at
 LIMIT 5000
"""

_DONG_SQL = """
SELECT bl.payment_cycle_id::text AS cycle_id, bl.source_type,
       bl.name_snapshot AS ten, bl.quantity AS so_luong, bl.line_total AS thanh_tien
  FROM payment_bill_line bl
 WHERE bl.clinic_id = $1::uuid AND bl.payment_cycle_id = ANY($2::uuid[])
   AND bl.billing_owner = 'CLINIC'
"""

_DOI_TAC_SQL = """
SELECT t.id::text AS id, t.so_tien, t.hinh_thuc, t.ghi_luc, o.service_name AS ten,
       s.full_name AS nguoi, p.full_name AS ten_khach, p.patient_code AS ma_bn
  FROM doi_tac_thanh_toan t
  LEFT JOIN service_order o ON o.id = t.service_order_id AND o.clinic_id = t.clinic_id
  LEFT JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
  LEFT JOIN patient p
    ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
  LEFT JOIN staff s ON s.id = t.ghi_boi
 WHERE t.clinic_id = $1::uuid AND t.huy_luc IS NULL
   AND (t.ghi_luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date BETWEEN $2 AND $3
 ORDER BY t.ghi_luc
 LIMIT 5000
"""

#: Các lần đổi hình thức GHI trong khoảng (giờ VN) — kể cả phiếu thu ngày trước.
_DOI_HINH_THUC_SQL = """
SELECT d.id::text AS id, d.cycle_id::text AS cycle_id, d.method_cu, d.method_moi,
       d.tien_mat, d.chuyen_khoan,
       d.ly_do, d.luc, pc.kind, pc.amount, s.full_name AS nguoi,
       p.full_name AS ten_khach, p.patient_code AS ma_bn
  FROM payment_cycle_doi_hinh_thuc d
  JOIN payment_cycle pc
    ON pc.payment_cycle_id = d.cycle_id AND pc.clinic_id = d.clinic_id
  LEFT JOIN staff s ON s.id = d.boi
  LEFT JOIN visit v ON v.visit_id = pc.visit_id AND v.clinic_id = pc.clinic_id
  LEFT JOIN patient p
    ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
 WHERE d.clinic_id = $1::uuid
   AND (d.luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date BETWEEN $2 AND $3
 ORDER BY d.id
 LIMIT 5000
"""

_LUOT_SQL = """
SELECT count(*) FROM visit
 WHERE clinic_id = $1::uuid
   -- V8: lượt BÁN LẺ (khách chỉ mua thuốc) không phải lượt khám.
   AND NOT ban_le
   AND (created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date BETWEEN $2 AND $3
"""

_LUOT_KHONG_CHON_DICH_VU_KHAM_SQL = """
SELECT count(*) FROM public.visit v
  LEFT JOIN public.appointment a
    ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
  JOIN public.service_type st
    ON st.id = coalesce(v.service_type_id, a.service_type_id)
  LEFT JOIN public.encounter_flow ef
    ON ef.clinic_id = v.clinic_id AND ef.visit_id = v.visit_id
 WHERE v.clinic_id = $1::uuid
   AND NOT v.ban_le  -- V8: lượt bán lẻ không có bước khám
   AND (v.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date BETWEEN $2 AND $3
   -- Lượt đi thẳng phòng dịch vụ không có bước khám, nên không thể "chưa
   -- chọn dịch vụ khám". Nếu rẽ về bác sĩ chính thì vẫn được đếm.
   AND NOT (coalesce(st.di_thang_phong, false)
            AND coalesce(ef.route_decision, 'SERVICES') = 'SERVICES')
   AND NOT EXISTS (
       SELECT 1 FROM public.luot_phi_kham l
        WHERE l.clinic_id = v.clinic_id AND l.visit_id = v.visit_id
          AND l.bo_luc IS NULL
   )
"""


class BaoCaoCuoiNgayService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def bao_cao(
        self, *, identity: StaffIdentity, tu: Any = None, den: Any = None
    ) -> dict[str, Any]:
        """Báo cáo cuối ngày trong khoảng (giờ VN). Ngày rác → hôm nay."""
        a, b = doc_khoang(tu, den)
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            lan_thu = await conn.fetch(_LAN_THU_SQL, cid, a, b)
            hoan = await conn.fetch(_HOAN_SQL, cid, a, b)
            canh_bao_neu_day(
                "bao_cao_cuoi_ngay.lan_thu", len(lan_thu), _TRAN, tu=a, den=b
            )
            canh_bao_neu_day("bao_cao_cuoi_ngay.hoan", len(hoan), _TRAN, tu=a, den=b)
            dong = await conn.fetch(
                _DONG_SQL, cid, [r["id"] for r in lan_thu if r["status"] == "PAID"]
            )
            doi_tac = await conn.fetch(_DOI_TAC_SQL, cid, a, b)
            so_luot = await conn.fetchval(_LUOT_SQL, cid, a, b)
            doi_ht = await conn.fetch(_DOI_HINH_THUC_SQL, cid, a, b)
            so_luot_khong_chon = await conn.fetchval(
                _LUOT_KHONG_CHON_DICH_VU_KHAM_SQL, cid, a, b
            )
            # "Khách còn nợ: n — x đ" (01/10/2026): khoản đã ghi nợ lúc check-out
            # còn CHƯA THU — tính tới hiện tại, không theo khoảng ngày.
            from clinicai.services.cong_no_service import doc_khach_con_no

            con_no = await doc_khach_con_no(conn, cid)
        bao_cao = gom_bao_cao(
            tu=a,
            den=b,
            lan_thu=[dict(r) for r in lan_thu],
            hoan=[dict(r) for r in hoan],
            dong=[dict(r) for r in dong],
            doi_tac=[dict(r) for r in doi_tac],
            so_luot_kham=int(so_luot or 0),
            doi_hinh_thuc=[dict(r) for r in doi_ht],
            so_luot_khong_chon_dich_vu_kham=int(so_luot_khong_chon or 0),
        )
        bao_cao["khach_con_no"] = con_no
        return bao_cao
