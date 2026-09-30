"""Trạng thái lịch hẹn KHÔNG còn giữ chỗ — MỘT danh sách cho cả phía Python.

Trước 29/09/2026 danh sách này chép ở bốn nơi: `lib/slot-capacity.ts`,
`lib/thong-ke-khung-gio.ts`, trigger `enforce_slot_capacity` và
`man_dat_lich_doc.py` (cộng vài bản rời trong các service). Trình duyệt nay
không giữ bản nào nữa — máy chủ trả sẵn số ghế và cờ `giu_cho`.

SQL vẫn giữ bản của nó (trigger chạy trong Postgres, không đọc được Python),
nhưng `src/tests/db/test_trang_thai_chet_khop_sql.py` so hai bên từng chữ: sửa
một bên mà quên bên kia thì test đỏ.

Cuối tệp: `trang_thai_hien_thi` — NHÃN trạng thái của một lịch / lượt cho mọi
màn (30/09/2026).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from clinicai.core.clock import CLINIC_TZ

#: Huỷ / không đến / bác sĩ từ chối chờ phân lại — không chiếm ghế của ai.
DEAD_STATUSES: frozenset[str] = frozenset({"CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"})


def giu_cho(status: str | None) -> bool:
    """Lịch ở trạng thái này có còn chiếm một ghế trong khung không."""
    return (status or "").strip() not in DEAD_STATUSES


# ---------------------------------------------------------------------------
# NHÃN TRẠNG THÁI HIỂN THỊ — MỘT hàm cho mọi màn (Tuyền 30/09/2026)
# ---------------------------------------------------------------------------
#
# "Đã checkout rồi nhưng ở mấy trang chủ hay trang lịch hẹn khám vẫn ghi là
# đang khám." Mỗi màn tự dịch `appointment.status` bằng một bảng chữ riêng
# trong TSX (lưới lịch tuần, bảng trạng thái buổi khám, CSKH, lịch sử các lần
# khám), mà cột ấy không nói được khách đã về hay chưa. Nay máy chủ suy nhãn
# từ LỊCH + LƯỢT (+ chỗ khách đang đứng theo Hành trình khách) ở đây; màn chỉ
# vẽ `nhan` bằng màu `tone` (bộ ChipTone của components/ui/Chip).
#
# Thứ tự ưu tiên:
#   1. Lịch chưa tới quầy / đã chết → nhãn theo lịch. Lượt INCOMPLETE do HOÀN
#      TÁC check-in đi kèm lịch CONFIRMED — lịch thắng: khách chưa đến.
#   2. Đã tới: về giữa chừng → đã về (check-out) → khám xong (bác sĩ khép lượt
#      / ký hồ sơ) → đã thu đủ → đang ở / đang chờ ở đâu → đã check-in.

#: Lịch chưa tới quầy.
CHUA_DEN: frozenset[str] = frozenset({"SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"})

#: Lịch chưa tới quầy / đã chết: (mã, nhãn, tone).
_NHAN_LICH: dict[str, tuple[str, str, str]] = {
    "SCHEDULED": ("CHUA_XAC_NHAN", "Chưa xác nhận", "warning"),
    "CSKH_CONFIRMED": ("DA_DAT", "Đã đặt lịch", "neutral"),
    "CONFIRMED": ("DA_DAT", "Đã đặt lịch", "neutral"),
    "CANCELLED": ("HUY", "Đã huỷ", "danger"),
    "NO_SHOW": ("KHONG_DEN", "Không đến", "neutral"),
    "DOCTOR_DECLINED": ("BS_TU_CHOI", "Bác sĩ từ chối", "warning"),
}

#: Lượt bác sĩ đã ký hồ sơ — khám xong dù quầy chưa đóng lượt.
_LUOT_DA_KY: frozenset[str] = frozenset({"FINALIZED", "AMENDED"})

#: Mã "khách đã tới" — màn dùng để đếm "đang trong phòng khám" / "đã về".
DA_TOI_CON_O: frozenset[str] = frozenset(
    {"DA_CHECK_IN", "DANG_O", "DANG_CHO", "DA_THU_DU", "KHAM_XONG"}
)
DA_ROI: frozenset[str] = frozenset({"DA_VE", "VE_GIUA_CHUNG"})


def _gio_vn(moc: Any) -> str | None:
    """hh:mm giờ Việt Nam của một mốc có múi giờ; rác → None (không ném)."""
    if not isinstance(moc, datetime) or moc.tzinfo is None:
        return None
    return moc.astimezone(CLINIC_TZ).strftime("%H:%M")


def trang_thai_hien_thi(
    *,
    lich: str | None,
    luot: str | None = None,
    ve_luc: Any = None,
    kham_xong: bool = False,
    dang_o: Any = None,
    da_thu_du: bool | None = None,
) -> dict[str, str]:
    """HÀM THUẦN: ``{"ma", "nhan", "tone"}`` của một lịch hẹn / lượt khám.

    * ``lich``  — ``appointment.status`` (None = lượt không có lịch).
    * ``luot``  — ``visit.status`` (None = chưa có lượt).
    * ``ve_luc`` — ``visit.closed_at``: có = khách đã check-out.
    * ``kham_xong`` — ``visit.exam_completed_at`` có giá trị.
    * ``dang_o`` — khối ``gon`` của Hành trình khách (lượt còn mở):
      ``{"trang_thai", "noi", ...}``. Thiếu thì nhãn thô "Đã check-in".
    * ``da_thu_du`` — đã thu đủ mọi khâu (bảng trạng thái buổi khám).

    Lượt đã check-out LUÔN là "Đã về" / "Về giữa chừng", bất kể lịch ghi gì.
    """
    lich = (lich or "").strip() or None
    if lich in _NHAN_LICH:
        ma, nhan, tone = _NHAN_LICH[lich]
        return {"ma": ma, "nhan": nhan, "tone": tone}
    if lich is not None and lich not in ("CHECKED_IN", "COMPLETED"):
        # Trạng thái lạ (thêm giá trị mới mà quên ở đây) — nói nguyên văn.
        return {"ma": "KHAC", "nhan": lich, "tone": "neutral"}
    if lich is None and not luot:
        return {"ma": "KHAC", "nhan": "—", "tone": "neutral"}

    gio_ve = _gio_vn(ve_luc)
    if luot == "INCOMPLETE":
        return {
            "ma": "VE_GIUA_CHUNG",
            "nhan": f"Về giữa chừng {gio_ve}" if gio_ve else "Về giữa chừng",
            "tone": "danger",
        }
    if ve_luc is not None:
        return {
            "ma": "DA_VE",
            "nhan": f"Đã về {gio_ve}" if gio_ve else "Đã về",
            "tone": "neutral",
        }
    if kham_xong or lich == "COMPLETED" or luot in _LUOT_DA_KY:
        if da_thu_du:
            return {
                "ma": "KHAM_XONG",
                "nhan": "Khám xong · đã thu đủ — chờ check-out",
                "tone": "success",
            }
        return {"ma": "KHAM_XONG", "nhan": "Khám xong — chưa check-out", "tone": "info"}
    if da_thu_du:
        return {"ma": "DA_THU_DU", "nhan": "Đã thu đủ", "tone": "success"}
    if isinstance(dang_o, dict):
        loai = str(dang_o.get("trang_thai") or "")
        noi = str(dang_o.get("noi") or "").strip()
        if loai == "DANG_O" and noi:
            return {"ma": "DANG_O", "nhan": f"Đang ở: {noi}", "tone": "dang_o"}
        if loai in ("DANG_CHO", "DANG_GOI", "O_QUAY") and noi:
            return {"ma": "DANG_CHO", "nhan": f"Đang chờ: {noi}", "tone": "warning"}
    return {"ma": "DA_CHECK_IN", "nhan": "Đã check-in", "tone": "success"}
