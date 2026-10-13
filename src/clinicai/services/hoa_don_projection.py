"""Pure invoice presentation: no queries or writes."""

from datetime import datetime
from typing import Any

from clinicai.services.quay_thu_service import ma_phieu


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _sum(bills: list[dict[str, Any]]) -> dict[str, int]:
    keys = ("da_thu", "da_hoan", "cho_hoan", "thu_rong", "tong_truoc_giam", "giam_gia")
    return {k: sum(int(p[k]) for p in bills) for k in keys}


def _state(status: Any, amount: int, returned: int, pending: int) -> str:
    if status == "VOIDED":
        return "DA_HUY"
    if pending:
        return "CHO_HOAN"
    if returned > 0 and returned >= amount:
        return "HOAN_TOAN_BO"
    return "HOAN_MOT_PHAN" if returned else "DA_THU"


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
) -> dict[str, Any]:
    rs = [_refund(r, refund_lines) for r in refunds if r["cycle_id"] == row["id"]]
    amount = int(row["amount"])
    completed = sum(r["so_tien"] for r in rs if r["trang_thai"] == "COMPLETED")
    pending = sum(r["so_tien"] for r in rs if r["trang_thai"] == "PENDING")
    return {
        "id": row["id"],
        "ma": ma_phieu(row["id"]),
        "visit_id": row.get("visit_id"),
        "kind": row.get("kind"),
        "trang_thai": _state(row["status"], amount, completed, pending),
        "trang_thai_goc": row["status"],
        "so_tien": amount,
        **_discount(row),
        "da_thu": amount,
        "da_hoan": completed,
        "cho_hoan": pending,
        "thu_rong": amount - completed,
        "hinh_thuc": row.get("method"),
        "lap_luc": _iso(row.get("created_at")),
        "thu_luc": _iso(row.get("paid_at")),
        "huy_luc": _iso(row.get("closed_at")),
        "nguoi_lap": row.get("nguoi_lap"),
        "nguoi_thu": row.get("nguoi_thu"),
        "nguoi_huy": row.get("nguoi_huy"),
        "ly_do_huy": row.get("close_reason"),
        "can_doi_soat": bool(row.get("can_doi_soat")),
        "thu_trong_ky": bool(row.get("trong_ky")),
        "huy_trong_ky": bool(row.get("huy_trong_ky")),
        "dong": [_line(d) for d in lines if d["cycle_id"] == row["id"]],
        "hoan": rs,
    }


def _customer(group: dict[str, Any]) -> dict[str, Any]:
    bills = group["phieu"]
    warnings = sorted(
        {
            message
            for p in bills
            for message in (
                "Phiếu cần đối soát" if p["can_doi_soat"] else None,
                "Phiếu huỷ cần xác minh tiền trả lại"
                if p["trang_thai"] == "DA_HUY" and p["thu_rong"] > 0
                else None,
                "Có khoản hoàn thất bại"
                if any(r["trang_thai"] == "FAILED" for r in p["hoan"])
                else None,
            )
            if message is not None
        }
    )
    states = {p["trang_thai"] for p in bills}
    return {
        **group,
        **_sum(bills),
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
    return dict(
        da_thu=paid,
        tong_truoc_giam=sum(p["tong_truoc_giam"] for p in bills if p["thu_trong_ky"]),
        giam_gia=sum(p["giam_gia"] for p in bills if p["thu_trong_ky"]),
        da_hoan=completed,
        thu_rong=paid - completed,
        cho_hoan=sum(r["so_tien"] for r in refunds if r["trang_thai"] == "PENDING"),
        so_phieu=len(bills),
        so_khach=len(customers),
        so_huy=sum(bool(p["huy_trong_ky"]) for p in bills),
        gia_tri_huy=sum(p["so_tien"] for p in bills if p["huy_trong_ky"]),
    )


def gom_hoa_don(
    receipts: list[dict[str, Any]],
    refunds: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    refund_lines: list[dict[str, Any]],
    *,
    tim: str | None,
    trang_thai: str | None,
    can_kiem_tra: bool = False,
) -> dict[str, Any]:
    """Group by patient; period movement is separate from bill lifetime."""
    groups: dict[str, dict[str, Any]] = {}
    for row in receipts:
        bill = _bill(row, refunds, lines, refund_lines)
        if trang_thai and trang_thai != bill["trang_thai"]:
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
    customers = [_customer(group) for group in groups.values() if _matches(group, tim)]
    selected = [g for g in customers if not can_kiem_tra or g["can_doi_soat"]]
    return {"tong": _period(selected), "khach": selected}
