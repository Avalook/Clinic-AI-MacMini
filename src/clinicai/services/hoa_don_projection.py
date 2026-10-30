"""Pure invoice presentation: no queries or writes."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.quay_thu_service import ma_phieu


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _sum(bills: list[dict[str, Any]]) -> dict[str, int]:
    keys = ("da_thu", "da_hoan", "cho_hoan", "thu_rong", "tong_truoc_giam", "giam_gia")
    return {k: sum(int(p[k]) for p in bills) for k in keys}


#: Loại việc còn tồn (chỉ những gì hệ thống TỰ biết là chưa xong; quầy / CSKH
#: xử lý bằng nút có sẵn thì tự hết — màn danh sách hoá đơn chỉ để xem).
TEN_VIEC_TON: dict[str, str] = {
    "CHUA_TRA_LAI": "Chưa trả lại khách",
    "CHUA_LAM": "Đã thu – khách về chưa làm",
    "HOAN_CHUA_XONG": "Hoàn tiền chưa xong",
    "HOAN_THAT_BAI": "Hoàn tiền thất bại",
    "CK_CHUA_VE": "Chuyển khoản chưa về",
    "GHI_NO": "Ghi nợ chưa thu",
}

_TEN_HINH_THUC = {"CASH": "Tiền mặt", "TRANSFER": "Chuyển khoản", "QR": "Chuyển khoản"}


def _su_kien(
    row: dict[str, Any],
    refunds: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    doi_ht: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Những gì làm tiền của phiếu thay đổi SAU khi bấm thu, theo giờ. Thuần."""
    ev: list[dict[str, Any]] = []
    for d in doi_ht:
        cu = _TEN_HINH_THUC.get(str(d.get("method_cu") or ""), "Không rõ")
        moi = _TEN_HINH_THUC.get(str(d.get("method_moi") or ""), "Không rõ")
        ev.append(
            {
                "luc": _iso(d.get("luc")),
                "loai": "DOI_HINH_THUC",
                "nguoi": d.get("nguoi"),
                "mo_ta": f"{cu} → {moi}",
                "ly_do": d.get("ly_do"),
                "so_tien": int(row["amount"]),
            }
        )
    for d in lines:
        if d.get("da_bo"):
            ev.append(
                {
                    "luc": _iso(d.get("bo_luc")),
                    "loai": "BO_DICH_VU",
                    "nguoi": None,
                    "mo_ta": str(d.get("ten") or ""),
                    "ly_do": None,
                    "so_tien": int(d.get("thanh_tien") or 0),
                }
            )
    for r in refunds:
        ev.append(
            {
                "luc": r["hoan_luc"] or r["huy_luc"] or r["lap_luc"],
                "loai": "HOAN_TIEN",
                "nguoi": r["nguoi_hoan"] or r["nguoi_lap"],
                "mo_ta": _TEN_HINH_THUC.get(str(r.get("hinh_thuc") or ""), ""),
                "ly_do": r["ly_do"],
                "so_tien": -int(r["so_tien"]),
                "trang_thai": r["trang_thai"],
            }
        )
    if row.get("status") == "VOIDED":
        giay = None
        if isinstance(row.get("closed_at"), datetime) and isinstance(
            row.get("paid_at"), datetime
        ):
            giay = int((row["closed_at"] - row["paid_at"]).total_seconds())
        ev.append(
            {
                "luc": _iso(row.get("closed_at")),
                "loai": "HUY_PHIEU",
                "nguoi": row.get("nguoi_huy"),
                "mo_ta": "",
                "ly_do": row.get("close_reason"),
                "so_tien": -int(row["amount"]),
                "sau_giay": giay,
            }
        )
    if row.get("status") == "CANCELLED":
        ev.append(
            {
                "luc": _iso(row.get("closed_at")),
                "loai": "HUY_CHO_CK",
                "nguoi": row.get("nguoi_huy"),
                "mo_ta": "Huỷ lần chờ chuyển khoản — chưa ghi thu",
                "ly_do": row.get("close_reason"),
                "so_tien": 0,
            }
        )
    return sorted(ev, key=lambda e: e["luc"] or "9999")


def _state(status: Any, amount: int, returned: int, pending: int) -> str:
    if status == "VOIDED":
        return "DA_HUY"
    if status == "CANCELLED":
        return "CK_DA_HUY"
    if pending:
        return "CHO_HOAN"
    if returned > 0 and returned >= amount:
        return "HOAN_TOAN_BO"
    return "HOAN_MOT_PHAN" if returned else "DA_THU"


def nhan_phong(phong: Mapping[str, Any] | None) -> str | None:
    """ "Phòng siêu âm 2 · BS X (dự kiến)" — đúng chữ phiếu thu in (tên phòng,
    bác sĩ của phòng nhiều bác sĩ, chưa xếp thì phòng dự kiến). Không tầng."""
    if not phong or not phong.get("ten"):
        return None
    chu = str(phong["ten"])
    if phong.get("bac_si"):
        chu += f" · {phong['bac_si']}"
    return chu + (" (dự kiến)" if phong.get("du_kien") else "")


def gan_phong(
    lines: list[dict[str, Any]],
    refund_lines: list[dict[str, Any]],
    phong_cua_dong: Mapping[str, Mapping[str, Any] | None],
) -> None:
    """Gắn nhãn phòng (``phong``) vào từng dòng dịch vụ + dòng hoàn của dòng ấy.
    ``phong_cua_dong``: id dòng hoá đơn → phòng như phiếu thu (``_phong_cua_dong``).
    Dòng đã bỏ sau thu không in phòng (như bản in lại phiếu)."""
    nhan: dict[str, str | None] = {}
    for d in lines:
        p = None if d.get("da_bo") else nhan_phong(phong_cua_dong.get(str(d["id"])))
        d["phong"] = nhan[str(d["id"])] = p
    for d in refund_lines:
        d["phong"] = nhan.get(str(d["id"]))


def _line(row: dict[str, Any]) -> dict[str, Any]:
    actual = int(row["thanh_tien"])
    discount = int(row.get("discount_allocated") or 0)
    return {
        **row,
        "so_luong": float(row["so_luong"]),
        "thanh_tien": actual,
        "thanh_tien_truoc_giam": actual + discount,
        "giam_gia": discount,
    }


def _discount(row: dict[str, Any]) -> dict[str, Any]:
    original = row.get("original_amount")
    value = row.get("discount_value")
    discount = int(row.get("discount_amount") or 0)
    return {
        "tong_truoc_giam": int(original)
        if original is not None
        else int(row["amount"]),
        "giam_gia": discount,
        "kieu_giam": row.get("discount_type"),
        "gia_tri_giam": float(value) if value is not None else None,
        "ly_do_giam": row.get("discount_reason"),
        "nguoi_giam": row.get("nguoi_giam"),
        "giam_luc": _iso(row.get("created_at")) if discount else None,
    }


def _refund(row: dict[str, Any], lines: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "ma": ma_phieu(row["id"], "hoan"),
        "so_tien": int(row["amount"]),
        "trang_thai": row["status"],
        "lap_luc": _iso(row.get("created_at")),
        "hoan_luc": _iso(row.get("completed_at")),
        "nguoi_lap": row.get("nguoi_lap"),
        "nguoi_hoan": row.get("nguoi_hoan"),
        "huy_luc": _iso(row.get("closed_at")),
        "nguoi_huy": row.get("nguoi_huy"),
        "ly_do_huy": row.get("closed_reason"),
        "ly_do": row.get("reason"),
        "hinh_thuc": row.get("method"),
        "trong_ky": bool(row.get("trong_ky")),
        "dong": [_line(d) for d in lines if d["refund_id"] == row["id"]],
    }


def _bill(
    row: dict[str, Any],
    refunds: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    refund_lines: list[dict[str, Any]],
    doi_ht: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    rs = [_refund(r, refund_lines) for r in refunds if r["cycle_id"] == row["id"]]
    my_lines = [d for d in lines if d["cycle_id"] == row["id"]]
    amount = int(row["amount"])
    completed = sum(r["so_tien"] for r in rs if r["trang_thai"] == "COMPLETED")
    pending = sum(r["so_tien"] for r in rs if r["trang_thai"] == "PENDING")
    # Lần chờ CK đã huỷ (G4d, R1): hiện để đối chiếu sao kê, KHÔNG phải tiền
    # đã thu — mọi cột tiền = 0, số tiền lần chờ chỉ để đọc ("so_tien").
    chua_thu = row["status"] == "CANCELLED"
    return {
        "id": row["id"],
        "ma": ma_phieu(row["id"]),
        "visit_id": row.get("visit_id"),
        "kind": row.get("kind"),
        "trang_thai": _state(row["status"], amount, completed, pending),
        "trang_thai_goc": row["status"],
        "so_tien": amount,
        **_discount(row),
        **({"tong_truoc_giam": 0, "giam_gia": 0} if chua_thu else {}),
        "da_thu": 0 if chua_thu else amount,
        "da_hoan": completed,
        "cho_hoan": pending,
        # Phiếu đã huỷ không còn tiền của phòng khám: thu ròng 0 — cùng định
        # nghĩa với báo cáo cuối ngày (thực thu = thu − huỷ − hoàn). Để nguyên
        # số tiền thì tổng thu ròng bị thổi lên đúng bằng tiền phiếu huỷ (staging
        # 12/10: 77.505.000 so với 74.250.000 của báo cáo).
        "thu_rong": 0
        if row["status"] in ("VOIDED", "CANCELLED")
        else amount - completed,
        "hinh_thuc": row.get("method"),
        "lap_luc": _iso(row.get("created_at")),
        "thu_luc": _iso(row.get("paid_at")),
        "huy_luc": _iso(row.get("closed_at")),
        "nguoi_lap": row.get("nguoi_lap"),
        "nguoi_thu": row.get("nguoi_thu"),
        "nguoi_huy": row.get("nguoi_huy"),
        "ly_do_huy": row.get("close_reason"),
        "can_doi_soat": bool(row.get("can_doi_soat")),
        "doi_soat_ly_do": list(row.get("doi_soat_ly_do") or []),
        "so_tien_thuc_nhan": (
            int(row["so_tien_thuc_nhan"])
            if row.get("so_tien_thuc_nhan") is not None
            else None
        ),
        "thu_trong_ky": bool(row.get("trong_ky")),
        "huy_trong_ky": bool(row.get("huy_trong_ky")),
        "dong": [_line(d) for d in my_lines],
        "su_kien": _su_kien(
            row, rs, my_lines, [d for d in doi_ht if d.get("cycle_id") == row["id"]]
        ),
        "hoan": rs,
    }


def _customer(
    group: dict[str, Any],
    tien_thua: Mapping[str, Mapping[str, Any]],
    viec_ton: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    bills = group["phieu"]
    visits = {p["visit_id"] for p in bills if p.get("visit_id")}
    # Tiền thừa (bỏ dịch vụ sau khi thu, chưa hoàn) đã trừ sẵn khoản hoàn đang
    # chờ / đã xong (`tien_thua_cua_luot`) → cộng thêm khoản hoàn đang chờ là
    # đủ "chưa trả lại khách", không đếm trùng.
    thua = [
        {**d, "visit_id": v}
        for v in sorted(visits)
        for d in (tien_thua.get(v) or {}).get("dong", [])
    ]
    warnings = sorted(
        {
            message
            for p in bills
            for message in (
                "Phiếu cần đối soát" if p["can_doi_soat"] else None,
                "Phiếu huỷ cần xác minh tiền trả lại"
                if p["trang_thai"] == "DA_HUY" and p["so_tien"] > 0
                else None,
                "Có khoản hoàn thất bại"
                if any(r["trang_thai"] == "FAILED" for r in p["hoan"])
                else None,
                "Có lần chờ chuyển khoản đã huỷ — đối chiếu sao kê"
                if p["trang_thai"] == "CK_DA_HUY"
                else None,
            )
            if message is not None
        }
    )
    states = {p["trang_thai"] for p in bills}
    tong = _sum(bills)
    return {
        **group,
        **tong,
        "da_thu_dich_vu": sum(p["da_thu"] for p in bills if p["kind"] != "thuoc"),
        "da_thu_thuoc": sum(p["da_thu"] for p in bills if p["kind"] == "thuoc"),
        "tien_thua": thua,
        "chua_tra_lai": sum(int(d["so_tien"]) for d in thua) + tong["cho_hoan"],
        "viec_ton": [v for v in viec_ton if v.get("patient_id") == group["id"]],
        "co_phieu_huy": any(p["trang_thai"] == "DA_HUY" for p in bills),
        "so_phieu": len(bills),
        "can_doi_soat": bool(warnings),
        "canh_bao": warnings,
        "trang_thai": next(iter(states)) if len(states) == 1 else "HON_HOP",
    }


def _matches(group: dict[str, Any], tim: str | None) -> bool:
    values = (
        group["ten"],
        group["ma_bn"],
        group["so_dien_thoai"],
        *[p["ma"] for p in group["phieu"]],
        *[r["ma"] for p in group["phieu"] for r in p["hoan"]],
    )
    haystack = " ".join(str(v or "") for v in values).casefold()
    return (tim or "").strip().casefold() in haystack


def _period(customers: list[dict[str, Any]]) -> dict[str, int]:
    bills = [p for g in customers for p in g["phieu"]]
    refunds = [r for p in bills for r in p["hoan"] if r["trong_ky"]]
    paid = sum(p["so_tien"] for p in bills if p["thu_trong_ky"])
    completed = sum(r["so_tien"] for r in refunds if r["trang_thai"] == "COMPLETED")
    voided = sum(p["so_tien"] for p in bills if p["huy_trong_ky"])
    return dict(
        da_thu=paid,
        tong_truoc_giam=sum(p["tong_truoc_giam"] for p in bills if p["thu_trong_ky"]),
        giam_gia=sum(p["giam_gia"] for p in bills if p["thu_trong_ky"]),
        da_hoan=completed,
        thu_rong=paid - completed - voided,
        cho_hoan=sum(r["so_tien"] for r in refunds if r["trang_thai"] == "PENDING"),
        so_phieu=len(bills),
        so_khach=len(customers),
        so_huy=sum(bool(p["huy_trong_ky"]) for p in bills),
        gia_tri_huy=voided,
        chua_tra_lai=sum(int(g["chua_tra_lai"]) for g in customers),
    )


#: Phiếu "không đúng" (Tuyền 14/10/2026: mọi thứ lệch đường chuẩn thu đủ → làm
#: đủ → về) — mỗi lý do một mã. Giảm giá có lý do + người giảm là thao tác hợp lệ
#: → không tính lệch, có bộ lọc riêng.
TEN_LECH: dict[str, str] = {
    "HUY": "Huỷ phiếu",
    "HOAN": "Có trả lại tiền",
    "DOI_HINH_THUC": "Đổi hình thức thu",
    "CAN_DOI_SOAT": "Cần đối soát",
    "HUY_CHO_CK": "Huỷ lần chờ chuyển khoản",
    "NO_KHACH": "Khách còn nợ",
    "NO_PHONG_KHAM": "Phòng khám còn nợ khách",
}
_VIEC_NO_KHACH = frozenset({"GHI_NO", "CK_CHUA_VE"})
_VIEC_NO_PHONG_KHAM = frozenset(
    {"CHUA_TRA_LAI", "CHUA_LAM", "HOAN_CHUA_XONG", "HOAN_THAT_BAI"}
)
#: Nhóm lọc của màn (``nhom``); rác = không lọc.
NHOM_LOC = frozenset(
    {
        "dung",
        "khong_dung",
        "tra_lai",
        "giam_gia",
        "doi_hinh_thuc",
        "no_khach",
        "no_phong_kham",
        "ck_da_huy",
    }
)


def lech_cua_phieu(
    bill: Mapping[str, Any], viec_luot: Mapping[str, set[str]]
) -> list[str]:
    """Các lý do phiếu lệch đường chuẩn (rỗng = phiếu đúng). Thuần.

    ``viec_luot``: visit_id → các loại việc tồn còn mở của lượt."""
    viec = viec_luot.get(str(bill.get("visit_id"))) or set()
    co = {
        "HUY": bill["trang_thai"] == "DA_HUY",
        "HOAN": bool(bill["hoan"]),
        "DOI_HINH_THUC": any(e.get("loai") == "DOI_HINH_THUC" for e in bill["su_kien"]),
        "CAN_DOI_SOAT": bool(bill["can_doi_soat"]),
        "HUY_CHO_CK": bill["trang_thai"] == "CK_DA_HUY",
        "NO_KHACH": bool(viec & _VIEC_NO_KHACH),
        "NO_PHONG_KHAM": bool(viec & _VIEC_NO_PHONG_KHAM),
    }
    return [ma for ma in TEN_LECH if co[ma]]


def hop_nhom(bill: Mapping[str, Any], nhom: str | None) -> bool:
    """Phiếu có thuộc nhóm lọc không. Thuần."""
    lech = bill["lech"]
    return {
        None: True,
        "dung": not lech,
        "khong_dung": bool(lech),
        "tra_lai": "HUY" in lech or "HOAN" in lech,
        "giam_gia": int(bill.get("giam_gia") or 0) > 0,
        "doi_hinh_thuc": "DOI_HINH_THUC" in lech,
        "no_khach": "NO_KHACH" in lech,
        "no_phong_kham": "NO_PHONG_KHAM" in lech,
        "ck_da_huy": "HUY_CHO_CK" in lech,
    }.get(nhom, True)


def hop_hinh_thuc(bill: Mapping[str, Any], hinh_thuc: str | None) -> bool:
    if hinh_thuc not in ("CASH", "TRANSFER"):
        return True
    ht = "TRANSFER" if bill.get("hinh_thuc") in ("TRANSFER", "QR") else "CASH"
    return ht == hinh_thuc


def gom_hoa_don(
    receipts: list[dict[str, Any]],
    refunds: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    refund_lines: list[dict[str, Any]],
    *,
    tim: str | None,
    trang_thai: str | None,
    can_kiem_tra: bool = False,
    doi_hinh_thuc: Sequence[Mapping[str, Any]] = (),
    tien_thua: Mapping[str, Mapping[str, Any]] | None = None,
    viec_ton: Sequence[Mapping[str, Any]] = (),
    nhom: str | None = None,
    hinh_thuc: str | None = None,
) -> dict[str, Any]:
    """Group by patient; period movement is separate from bill lifetime.

    ``viec_ton`` là danh sách việc còn tồn của MỌI ngày (không theo kỳ) — trả
    nguyên để màn có tab riêng, và gắn vào khách tương ứng. ``trang_thai`` =
    ``CON_VIEC_TON`` lọc theo khách thay vì theo phiếu.

    ``nhom`` / ``hinh_thuc`` (14/10/2026 — link từ khối Dòng tiền): lọc phiếu.
    ``tong.dung_khong_dung`` đếm phiếu ĐÚNG / KHÔNG ĐÚNG + số phiếu từng lý do,
    tính TRƯỚC khi lọc nhóm (để thấy cả hai phía)."""
    loc_phieu = trang_thai if trang_thai in TRANG_THAI_PHIEU else None
    nhom = nhom if nhom in NHOM_LOC else None
    viec_luot: dict[str, set[str]] = {}
    for v in viec_ton:
        if v.get("visit_id"):
            viec_luot.setdefault(str(v["visit_id"]), set()).add(str(v["loai"]))
    so_dung = so_khong_dung = 0
    ly_do: dict[str, int] = {ma: 0 for ma in TEN_LECH}
    groups: dict[str, dict[str, Any]] = {}
    for row in receipts:
        bill = _bill(row, refunds, lines, refund_lines, doi_hinh_thuc)
        if loc_phieu and loc_phieu != bill["trang_thai"]:
            continue
        if not hop_hinh_thuc(bill, hinh_thuc):
            continue
        bill["lech"] = lech_cua_phieu(bill, viec_luot)
        bill["ten_lech"] = [TEN_LECH[ma] for ma in bill["lech"]]
        if bill["lech"]:
            so_khong_dung += 1
        else:
            so_dung += 1
        for ma in bill["lech"]:
            ly_do[ma] += 1
        if not hop_nhom(bill, nhom):
            continue
        key = row.get("patient_id") or row["id"]
        if key not in groups:
            groups[key] = dict(
                id=key,
                ten=row.get("ten"),
                ma_bn=row.get("ma_bn"),
                so_dien_thoai=row.get("so_dien_thoai"),
                phieu=[],
            )
        groups[key]["phieu"].append(bill)
    customers = [
        _customer(group, tien_thua or {}, viec_ton)
        for group in groups.values()
        if _matches(group, tim)
    ]
    selected = [
        g
        for g in customers
        if (not can_kiem_tra or g["can_doi_soat"])
        and (trang_thai != "CON_VIEC_TON" or g["viec_ton"])
    ]
    # Khách còn việc tồn lên đầu; trong nhóm giữ thứ tự cũ (phiếu mới trước).
    selected.sort(key=lambda g: not g["viec_ton"])
    # Dòng TỔNG cuối bảng = cộng đúng các dòng khách đang hiện (toàn chứng từ),
    # khác "tong" (dòng tiền trong kỳ). Máy chủ cộng — màn không tự cộng tiền.
    tong_khach = {
        k: sum(int(g[k]) for g in selected)
        for k in ("so_phieu", "giam_gia", "da_thu", "da_hoan", "chua_tra_lai")
    }
    tong_khach["thu_rong"] = sum(int(g["thu_rong"]) for g in selected)
    tong_khach["so_khach_con_ton"] = sum(bool(g["viec_ton"]) for g in selected)
    return {
        "tong": {
            **_period(selected),
            "so_viec_ton": len(viec_ton),
            "dung_khong_dung": {
                "dung": so_dung,
                "khong_dung": so_khong_dung,
                "ly_do": ly_do,
            },
        },
        "tong_khach": tong_khach,
        "khach": selected,
        "viec_ton": list(viec_ton),
    }


TRANG_THAI_PHIEU = frozenset(
    {"DA_THU", "CHO_HOAN", "HOAN_MOT_PHAN", "HOAN_TOAN_BO", "DA_HUY", "CK_DA_HUY"}
)


def _ngay_vn(v: Any) -> str | None:
    """Ngày (giờ VN, YYYY-MM-DD) của một mốc giờ; không phải giờ → None."""
    if not isinstance(v, datetime):
        return None
    return v.astimezone(CLINIC_TZ).date().isoformat()


#: Việc tồn → màn xử lý (G4a nối màn, 14/10/2026). `lego` = quyền màn đích cần
#: (màn chỉ dùng để ẨN nút — máy chủ vẫn tự kiểm ở mọi lệnh).
LEGO_QUAY = {"dich_vu": "payment.service.collect", "thuoc": "payment.medicine.collect"}
LEGO_CHECK_OUT = "reception.checkin.perform"


def duong_xu_ly(v: Mapping[str, Any]) -> dict[str, Any] | None:
    """Đích của nút "Xử lý" cho một dòng việc tồn. Thuần.

    Quầy thu hôm nay đã gom lượt cũ còn việc (nợ, CK chờ, tiền phòng khám nợ
    khách) nên KHÔNG truyền ngày — chỉ ``?luot=``. Việc chưa có màn xử lý riêng
    (khách đã về mà chưa làm) trả ``huong_dan`` bằng chữ, không link giả."""
    loai = str(v.get("loai"))
    vid = v.get("visit_id")
    if not vid:
        return None
    quay = "thuoc" if v.get("kind") == "thuoc" else "dich_vu"
    # Đường quầy thu là `/thu-ngan/dich-vu` (gạch NGANG), mã quầy là `dich_vu`.
    duong = "thuoc" if quay == "thuoc" else "dich-vu"
    if loai == "GHI_NO":
        return {
            "href": f"/thu-ngan/{duong}?luot={vid}",
            "nhan": "Thu nợ / miễn",
            "lego": LEGO_QUAY[quay],
        }
    if loai == "CK_CHUA_VE":
        return {
            "href": f"/thu-ngan/{duong}?luot={vid}",
            "nhan": "Xác nhận đã nhận tiền",
            "lego": LEGO_QUAY[quay],
        }
    if loai == "CHUA_TRA_LAI":
        if v.get("luot_con_mo"):
            return {
                "href": f"/reception/checkout?luot={vid}",
                "nhan": "Mở lượt để xử lý",
                "lego": LEGO_CHECK_OUT,
            }
        if quay == "thuoc":
            # Tiền thuốc đã thu mà chưa giao / khách trả lại: hoàn ở QUẦY THUỐC
            # (lần thu thuốc nằm trong "Giao dịch" của quầy ấy, lego thu thuốc).
            return {
                "href": f"/thu-ngan/thuoc?luot={vid}",
                "nhan": "Hoàn tiền thuốc",
                "lego": LEGO_QUAY["thuoc"],
            }
        return {
            "href": f"/thu-ngan/dich-vu?luot={vid}",
            "nhan": "Hoàn tiền thừa",
            "lego": LEGO_QUAY["dich_vu"],
        }
    if loai == "CHUA_LAM":
        if v.get("luot_con_mo"):
            return {
                "href": f"/reception/checkout?luot={vid}",
                "nhan": "Đóng lượt / làm tiếp",
                "lego": LEGO_CHECK_OUT,
            }
        return {
            "huong_dan": (
                "Mời khách quay lại làm, hoặc đánh dấu “không làm” ở phòng dịch vụ"
                " để tiền thành tiền thừa rồi hoàn ở quầy thu."
            ),
        }
    if loai in ("HOAN_CHUA_XONG", "HOAN_THAT_BAI"):
        ngay = v.get("ngay_thu")
        if not ngay:
            return None
        return {
            "href": f"/thu-ngan/{duong}?ngay={ngay}",
            "nhan": "Xử lý hoàn tiền",
            "lego": LEGO_QUAY[quay],
            "huong_dan": (
                "Mở tab “Đã thanh toán ngày …”, tìm khách, xác nhận chuyển xong"
                " (kèm mã giao dịch) hoặc ghi không thành."
            ),
        }
    return None


def _mo_ta_chua_lam(ten: Any, luot: Mapping[str, Any]) -> str:
    """ "Đã thu – khách về chưa làm": nói đúng trạng thái lượt. Sổ coi "đã về" =
    đã đóng HOẶC tạo trước hôm nay (cố ý, R14) — lượt hôm trước CHƯA đóng vẫn có
    thể hiện ở "Lượt tồn đọng" của màn Check-out, nên không được viết "đã đóng"."""
    if isinstance(luot.get("luot_dong_luc"), datetime):
        return f"{ten} chưa làm — lượt đã đóng, khách đã về"
    ngay = _ngay_vn(luot.get("luot_tao_luc"))
    hom = f" ({ngay[8:10]}/{ngay[5:7]})" if ngay else ""
    return f"{ten} chưa làm — lượt hôm trước{hom} chưa đóng; đóng lượt hoặc làm tiếp"


def gom_viec_ton(
    *,
    hoan: Sequence[Mapping[str, Any]],
    ck: Sequence[Mapping[str, Any]],
    no: Sequence[Mapping[str, Any]],
    tien_thua: Mapping[str, Mapping[str, Any]],
    luot: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Việc còn tồn của mọi ngày, cũ nhất trước. Thuần — chỉ ghép dữ liệu đã đọc.

    ``luot``: visit_id → {patient_id, ten, ma_bn, luc} (``luc`` = mốc phát sinh
    tiền thừa: lúc bỏ chỉ định gần nhất, không có thì lúc thu).
    """
    out: list[dict[str, Any]] = []

    def them(loai: str, luc: Any, khach: Mapping[str, Any], **x: Any) -> None:
        # NGÀY THẬT của lượt (không phải giờ dòng sổ) + lượt còn mở từ hôm trước
        # hay đã đóng — để mô tả đúng và chọn đúng màn xử lý.
        dong, tao = khach.get("luot_dong_luc"), khach.get("luot_tao_luc")
        row = {
            "loai": loai,
            "ten_loai": TEN_VIEC_TON[loai],
            "luc": luc if isinstance(luc, str) or luc is None else _iso(luc),
            "patient_id": khach.get("patient_id"),
            "ten": khach.get("ten"),
            "ma_bn": khach.get("ma_bn"),
            "luot_ngay": _ngay_vn(dong or tao),
            "luot_con_mo": isinstance(tao, datetime) and not isinstance(dong, datetime),
            **x,
        }
        row["xu_ly"] = duong_xu_ly(row)
        # Nhóm của dòng cho bộ lọc / link từ báo cáo (máy chủ quyết, màn chỉ lọc).
        row["nhom_no"] = (
            "no_khach"
            if loai in _VIEC_NO_KHACH
            else "no_phong_kham"
            if loai in _VIEC_NO_PHONG_KHAM
            else None
        )
        out.append(row)

    for r in hoan:
        them(
            "HOAN_THAT_BAI" if r["status"] == "FAILED" else "HOAN_CHUA_XONG",
            r.get("closed_at") if r["status"] == "FAILED" else r.get("created_at"),
            r,
            so_tien=int(r["amount"]),
            ma=ma_phieu(str(r["refund_id"]), "hoan"),
            visit_id=r.get("visit_id"),
            kind=r.get("kind"),
            mo_ta=r.get("reason"),
            nguoi=r.get("nguoi"),
            # Ngày thu gốc — nút "Xử lý hoàn tiền" mở quầy đúng ngày ấy.
            ngay_thu=r.get("ngay_thu"),
        )
    for c in ck:
        them(
            "CK_CHUA_VE",
            c.get("created_at"),
            c,
            so_tien=int(c["amount"]),
            ma=ma_phieu(str(c["payment_cycle_id"])),
            visit_id=c.get("visit_id"),
            kind=c.get("kind"),
            mo_ta="Chờ xác minh chuyển khoản",
            nguoi=c.get("nguoi"),
        )
    for n in no:
        them(
            "GHI_NO",
            n.get("ghi_luc"),
            n,
            so_tien=int(n["so_tien"]),
            ma=None,
            visit_id=n.get("visit_id"),
            kind=n.get("quay"),
            mo_ta=n.get("ly_do"),
            nguoi=n.get("nguoi"),
        )
    for vid, t in tien_thua.items():
        k = luot.get(vid) or {}
        for d in t.get("dong", []):
            chua_lam = d.get("loai") == "CHUA_LAM"
            thuoc = d.get("loai") == "THUOC"
            them(
                "CHUA_LAM" if chua_lam else "CHUA_TRA_LAI",
                k.get("luc"),
                k,
                so_tien=int(d["so_tien"]),
                ma=None,
                visit_id=vid,
                kind="thuoc" if thuoc else "dich_vu",
                mo_ta=(
                    _mo_ta_chua_lam(d["ten"], k)
                    if chua_lam
                    else f"Thuốc {d['ten']}: đã thu mà chưa giao / khách trả lại"
                    " — phải trả khách"
                    if thuoc
                    else f"Bỏ {d['ten']} sau khi đã thu"
                    if d.get("loai") != "KHONG_LAM"
                    else f"Không làm {d['ten']} sau khi đã thu"
                ),
                nguoi=None,
            )
    out.sort(key=lambda v: v["luc"] or "")
    return out
