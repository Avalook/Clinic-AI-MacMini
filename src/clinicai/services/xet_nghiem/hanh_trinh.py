"""Bàn XN — HÌNH của hành trình (bản mẫu 05/11): 5 mốc có giờ, nhóm theo khách.

Python thuần, không I/O. Mốc nào "xong" đọc thẳng từ SỰ VIỆC (có giờ hay không);
trạng thái vẫn chỉ do `trang_thai_xet_nghiem()` tính — module này không suy trạng thái,
chỉ đọc `tt.con_ton` / `tt.qua_hen` / `tt.nhan` / `tt.mau` mà hàm đó trả.
Màn chỉ vẽ: không tự quyết mốc nào sáng, khách nào mang chip gì.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from clinicai.services.xet_nghiem.trang_thai import TrangThaiXN

#: (chữ khi đã xong, chữ khi chưa tới, cột giờ trong hàng SQL)
_MOC: tuple[tuple[str, str, str], ...] = (
    ("Đã chỉ định", "Chỉ định", "tao_luc"),
    ("Đã thu tiền", "Thu tiền", "thu_luc"),
    ("Đã lấy mẫu", "Lấy mẫu", "lay_luc"),
    ("Đã có kết quả", "Chờ kết quả", "tep_luc"),
    ("Đã gửi khách", "Gửi khách", "gui_luc"),
)


def _moc_cuoi(r: Any) -> tuple[str, datetime | None]:
    if r["gui_luc"] is None and r["dong_luc"] is not None:
        return "Đối tác đã tự trả", r["dong_luc"]
    return ("Đã gửi khách" if r["gui_luc"] else "Gửi khách"), r["gui_luc"]


def hanh_trinh(r: Any, tt: TrangThaiXN) -> list[dict[str, Any]]:
    """5 mốc: mốc đã có sự việc là `done`; mốc đầu tiên chưa có là `current`
    (chỉ khi việc còn tồn); còn lại `upcoming`."""
    out: list[dict[str, Any]] = []
    for xong, chua, cot in _MOC[:-1]:
        luc = r[cot]
        out.append({"ten": xong if luc else chua, "luc": luc})
    ten, luc = _moc_cuoi(r)
    out.append({"ten": ten, "luc": luc})
    da_dat_dang = not tt.con_ton
    for m in out:
        if m["luc"] is not None:
            m["trang_thai"] = "done"
        elif not da_dat_dang:
            m["trang_thai"], da_dat_dang = "current", True
        else:
            m["trang_thai"] = "upcoming"
    return out


#: Mốc "current" thứ i ⇒ bước nào của thẻ việc sáng (Thu hộ · Mẫu · Tờ kết quả).
_BUOC: tuple[str | None, ...] = (None, "thu", "mau", "ket_qua", "ket_qua")


def buoc_dang(moc: list[dict[str, Any]]) -> str | None:
    """Bước của thẻ đang tới lượt; None = không mốc nào đang làm (việc đã xong)."""
    for i, m in enumerate(moc):
        if m["trang_thai"] == "current":
            return _BUOC[i]
    return None


def so_ngay_cho(ngay_chi_dinh: date | None, hom_nay: date) -> int:
    return max((hom_nay - ngay_chi_dinh).days, 0) if ngay_chi_dinh else 0


def nhom_khach(viec: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Một khách một dòng THEO NGÀY CHỈ ĐỊNH (tab "Việc theo ngày").

    Chip của dòng = việc quá hẹn trả (nếu có), không thì việc đứng đầu danh sách
    (`viec` đã xếp theo THU_TU — việc cần làm trước lên đầu)."""
    nhom: dict[str, dict[str, Any]] = {}
    for v in viec:
        ai = v["clinic_patient_id"] or v.get("visit_id") or v["order_id"]
        khoa = f"{v['ngay_chi_dinh']}|{ai}"
        g = nhom.setdefault(
            khoa,
            {
                "khoa": khoa,
                "ngay": v["ngay_chi_dinh"],
                "ten": v["ten_khach"] or "Khách",
                "ma_bn": v["ma_bn"],
                # Thẻ khách như hàng chờ các phòng: số check-in · tên · SĐT · #booking.
                "sdt": v.get("sdt"),
                "so_tiep_don": v.get("so_tiep_don"),
                "so_booking": v.get("so_booking"),
                "order_ids": [],
                "_dai_dien": v,
            },
        )
        g["order_ids"].append(v["order_id"])
        if v["trang_thai"]["qua_hen"] and not g["_dai_dien"]["trang_thai"]["qua_hen"]:
            g["_dai_dien"] = v
    out = []
    for g in nhom.values():
        # Chữ/màu chip đã gộp quá hẹn do hàm trạng thái tính — ở đây chỉ chép.
        tt = g.pop("_dai_dien")["trang_thai"]
        g["nhan"], g["mau"] = tt["chip_nhan"], tt["chip_mau"]
        out.append(g)
    return out
