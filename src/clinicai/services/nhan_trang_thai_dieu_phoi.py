"""NHÃN TRẠNG THÁI trên màn Điều phối ca (Tuyền 29/09/2026).

"Màn điều phối của trưởng ca phải có nhãn trạng thái rõ cho từng khách và từng
dịch vụ, để nhìn là biết, không chuyển bừa": Đang chờ (STT / số người trước,
phút chờ) · Đã gọi · Đang làm / đang khám (từ HH:MM · N′) · Xong · Chờ kết quả
đối tác · Khách về.

HÀM THUẦN. Máy chủ quyết trạng thái + mốc giờ (`tu_luc`); màn chỉ vẽ nhãn và
tính số phút theo đồng hồ của nó. Đầu vào rác / thiếu → vẫn ra một nhãn, không
ném.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

DANG_CHO = "DANG_CHO"
DA_GOI = "DA_GOI"
DANG_LAM = "DANG_LAM"
XONG = "XONG"
CHO_KQ_DOI_TAC = "CHO_KQ_DOI_TAC"
KHACH_VE = "KHACH_VE"
# Chỉ ở mức dịch vụ:
CHUA_THU = "CHUA_THU"
CHO_XEP = "CHO_XEP"
DA_DUNG = "DA_DUNG"
KHONG_LAM = "KHONG_LAM"
DOI_TAC_LAM = "DOI_TAC_LAM"
# Chỉ ở mức khách:
CHO_BUOC_KHAC = "CHO_BUOC_KHAC"
CHUA_VAO_HANG = "CHUA_VAO_HANG"

_LANE_KHAM = ("DOCTOR", "TU_VAN")


def _gio(v: Any) -> datetime | None:
    return v if isinstance(v, datetime) else None


def _so(v: Any) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None


def _ra(
    ma: str,
    nhan: str,
    tu_luc: Any = None,
    so_truoc: Any = None,
    *,
    cho_chuyen: bool = False,
    cho_dat: bool = False,
) -> dict[str, Any]:
    st = _so(so_truoc)
    return {
        "ma": ma,
        "nhan": nhan,
        "tu_luc": _gio(tu_luc),
        "so_truoc": st if ma == DANG_CHO else None,
        "stt": st + 1 if ma == DANG_CHO and st is not None else None,
        # [Chuyển phòng] chỉ bày ở dịch vụ đang chờ hoặc đang làm (Tuyền 29/09).
        "chuyen_duoc": cho_chuyen,
        # Chưa thu / chờ xếp: trưởng ca đặt phòng (dự kiến / xếp) được.
        "dat_phong_duoc": cho_dat,
    }


def trang_thai_dich_vu(
    *,
    exec_status: str | None,
    execution_status: str | None,
    doi_tac: bool,
    ket_qua_luc: Any,
    xong_luc: Any,
    khach_ve: bool,
    hang: str | None,
    vao_hang_luc: Any,
    goi_luc: Any,
    lam_tu: Any,
    so_truoc: Any,
    tai_chinh_xong: bool,
) -> dict[str, Any]:
    """Nhãn của MỘT chỉ định trên màn trưởng ca."""
    ex, cu = execution_status or "", exec_status or ""
    if ex == "CANCELLED" or cu == "cancelled":
        return _ra(KHONG_LAM, "Đã huỷ")
    if ex == "NOT_PERFORMED" or cu == "not_performed":
        return _ra(KHONG_LAM, "Không làm")
    if ex == "COMPLETED" or cu == "performed":
        if doi_tac and ket_qua_luc is None:
            return _ra(CHO_KQ_DOI_TAC, "Chờ kết quả đối tác", xong_luc)
        return _ra(XONG, "Xong", xong_luc)
    if khach_ve:
        return _ra(KHACH_VE, "Khách về")
    if ex == "IN_PROGRESS" or cu == "in_progress" or hang == "serving":
        return _ra(DANG_LAM, "Đang làm", lam_tu, cho_chuyen=True)
    if ex == "INTERRUPTED":
        return _ra(DA_DUNG, "Đã dừng giữa chừng")
    if hang == "called":
        return _ra(DA_GOI, "Đã gọi", goi_luc)
    if hang == "waiting":
        return _ra(DANG_CHO, "Đang chờ", vao_hang_luc, so_truoc, cho_chuyen=True)
    if hang == "blocked":
        # Khách đang ở bước khác — chỗ ở phòng này giữ, chưa tới lượt chờ.
        return _ra(DANG_CHO, "Đang chờ (khách đang ở bước khác)", cho_chuyen=True)
    if not tai_chinh_xong:
        return _ra(CHUA_THU, "Chưa thu tiền", cho_dat=True)
    if doi_tac:
        return _ra(DOI_TAC_LAM, "Đối tác làm")
    return _ra(CHO_XEP, "Chờ xếp phòng", cho_dat=True)


def trang_thai_khach(
    *,
    khach_ve: bool,
    lane: str | None,
    hang: str | None,
    vao_hang_luc: Any,
    goi_luc: Any,
    lam_tu: Any,
    so_truoc: Any,
    cho_kq_doi_tac: bool,
) -> dict[str, Any]:
    """Nhãn của MỘT khách (thẻ phòng / popup) — theo chỗ chờ sống quan trọng
    nhất của lượt (đang làm > đã gọi > đang chờ > chờ bước khác)."""
    if khach_ve:
        return _ra(KHACH_VE, "Khách về")
    kham = lane in _LANE_KHAM
    if hang == "serving":
        return _ra(DANG_LAM, "Đang khám" if kham else "Đang làm", lam_tu)
    if hang == "called":
        return _ra(DA_GOI, "Đã gọi", goi_luc)
    if hang == "waiting":
        return _ra(DANG_CHO, "Đang chờ", vao_hang_luc, so_truoc)
    if hang == "blocked":
        return _ra(CHO_BUOC_KHAC, "Chờ bước khác")
    if cho_kq_doi_tac:
        return _ra(CHO_KQ_DOI_TAC, "Chờ kết quả đối tác")
    return _ra(CHUA_VAO_HANG, "Chưa vào hàng")


__all__ = ["trang_thai_dich_vu", "trang_thai_khach"]
