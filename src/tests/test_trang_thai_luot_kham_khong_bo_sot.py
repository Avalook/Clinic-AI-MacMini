"""Thêm một trạng thái lượt khám thì KHÔNG ĐƯỢC bỏ sót chỗ nào.

Đây là loại lỗi im lặng nhất trong cả hệ: một màn hình lọc theo danh sách bốn
trạng thái cũ, trạng thái thứ năm không khớp nhánh nào, và màn đó lặng lẽ hiển
thị sai — không lỗi, không cảnh báo, chỉ là một người bệnh đứng nhầm chỗ.

Đã suýt xảy ra ngay trong lần thêm INCOMPLETE này:

  · `VisitStatusBoard.displayStatus` rơi xuống `return` cuối và hiện "Chờ khám"
    cho người đã ra về — Lễ tân sẽ đi gọi tên họ.
  · `VisitProgress.reachedCount` trả 0, thanh tiến trình lùi về "mới check-in"
    cho người đã đi được nửa buổi.
  · `QueueBoard` chia nhóm bằng `!== "IN_PROGRESS"` nên người đã về nằm trong
    nhóm "đang chờ gọi".
  · `ClinicalRecordForm.locked` là danh sách ĐEN — với INCOMPLETE thì tình cờ
    đúng, nhưng trạng thái CUỐI tiếp theo sẽ lọt.

Bài này KHÔNG đòi mọi chỗ phải nhận INCOMPLETE. Nhiều chỗ cố ý loại nó ra (khách
đã về thì không nằm trong hàng đợi phòng nào). Nó đòi mỗi chỗ phải **NÓI RA chủ
ý** — hoặc nhắc trạng thái mới, hoặc có tên trong bảng miễn trừ kèm lý do.
"""

from __future__ import annotations

import pathlib
import re

GOC = pathlib.Path(__file__).resolve().parents[1]
BACKEND = GOC / "clinicai"
DASHBOARD = GOC / "dashboard" / "app"

TRANG_THAI_CU = ("OPEN", "IN_PROGRESS", "FINALIZED", "AMENDED")
TRANG_THAI_MOI = "INCOMPLETE"

BO_QUA_THU_MUC = ("node_modules", ".next", "dist", "build", "__pycache__")

# Những chỗ CỐ Ý không nhắc tới trạng thái mới. Mỗi dòng phải có lý do đọc được
# — danh sách miễn trừ không lý do là danh sách sẽ dài mãi.
MIEN_TRU: dict[str, str] = {
    "api/v1/routers/visit_progress.py": (
        "Bảng điều phối chỉ hiện người ĐANG TRONG phòng khám. Khách về giữa "
        "chừng không được đếm vào hàng đợi của phòng nào."
    ),
    "services/dispatch_service.py": (
        "LIVE_VISIT_STATUSES = đang có mặt. Khách đã về thì không 'live'."
    ),
    "services/recall_service.py": (
        "Danh sách TÁI KHÁM, đọc soap_plan và đòi lượt đã ký xong. 'Gọi lại vì "
        "khám dở' là việc khác, dữ liệu khác (visit.incomplete_reason)."
    ),
    "services/console_service.py": (
        "Ô 'lượt đang mở' của Quản lý đếm đúng status='OPEN'."
    ),
    "services/clinical_sign_service.py": (
        "Luồng ký hồ sơ: chỉ nói về FINALIZED và AMENDED."
    ),
    "api/v1/routers/voice.py": "Chú thích nhắc lại cổng ghi, không tự lọc.",
    "(dashboard)/home/page.tsx": (
        "Lọc theo appointment.status (CANCELLED/NO_SHOW), không phải visit.status."
    ),
}


def _cac_file() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for goc, duoi in ((BACKEND, (".py",)), (DASHBOARD, (".ts", ".tsx"))):
        for p in goc.rglob("*"):
            if p.suffix not in duoi:
                continue
            if any(phan in p.parts for phan in BO_QUA_THU_MUC):
                continue
            out.append(p)
    return out


def _nhac_nhieu_trang_thai(noi_dung: str) -> bool:
    """File có LIỆT KÊ trạng thái lượt khám không (≥2 cái cùng lúc)?

    Đếm số trạng thái CŨ khác nhau xuất hiện trong dấu nháy — một chuỗi trong
    nháy là dấu hiệu của phép so, không phải của văn xuôi. Ngưỡng 2 vì một
    trạng thái đứng một mình thường là phép gán, còn hai cái trở lên gần như
    luôn là một danh sách phân nhánh.
    """
    trong_nhay = set(re.findall(r"""['"]([A-Z_]{4,})['"]""", noi_dung))
    return len(trong_nhay & set(TRANG_THAI_CU)) >= 2


def _khoa_mien_tru(p: pathlib.Path) -> str | None:
    ten = str(p)
    for khoa in MIEN_TRU:
        if khoa in ten:
            return khoa
    return None


def test_moi_noi_liet_ke_trang_thai_deu_da_tinh_den_kham_do() -> None:
    thieu: list[str] = []
    for p in _cac_file():
        noi_dung = p.read_text(encoding="utf-8", errors="ignore")
        if not _nhac_nhieu_trang_thai(noi_dung):
            continue
        if TRANG_THAI_MOI in noi_dung:
            continue
        if _khoa_mien_tru(p):
            continue
        thieu.append(str(p.relative_to(GOC)))

    assert not thieu, (
        f"Những file dưới đây phân nhánh theo trạng thái lượt khám nhưng chưa "
        f"nhắc {TRANG_THAI_MOI}. Hoặc xử lý nó, hoặc thêm vào MIEN_TRU kèm lý "
        "do — im lặng bỏ qua là cách một người bệnh đứng nhầm chỗ mà không ai "
        "biết:\n  " + "\n  ".join(sorted(thieu))
    )


def test_bang_mien_tru_khong_co_dong_chet() -> None:
    """Miễn trừ cho một file không còn tồn tại là một lời giải thích cho thứ
    không còn ở đó — và nó che mất file thật trùng tên sau này."""
    con_song = [str(p) for p in _cac_file()]
    chet = [k for k in MIEN_TRU if not any(k in ten for ten in con_song)]
    assert not chet, f"MIEN_TRU trỏ vào file không còn tồn tại: {chet}"


def test_bai_canh_nay_that_su_co_quet_duoc_file() -> None:
    """Chống xanh giả: đường dẫn sai thì bài trên luôn xanh vì không quét gì."""
    files = _cac_file()
    assert len(files) > 200, f"chỉ quét được {len(files)} file"
    assert any(f.suffix == ".py" for f in files)
    assert any(f.suffix == ".tsx" for f in files)


def test_bo_do_nhan_biet_that_su_bat_duoc_mot_danh_sach() -> None:
    """Chống xanh giả kiểu hai: nếu phép nhận biết không bao giờ khớp thì bài
    trên cũng luôn xanh."""
    assert _nhac_nhieu_trang_thai("""status IN ('OPEN', 'IN_PROGRESS')""")
    assert _nhac_nhieu_trang_thai(
        """visitStatus === "FINALIZED" || visitStatus === "AMENDED\""""
    )
    # Một trạng thái đứng một mình = phép gán, không phải danh sách phân nhánh.
    assert not _nhac_nhieu_trang_thai("""SET status = 'FINALIZED'""")
    assert not _nhac_nhieu_trang_thai("không có trạng thái nào ở đây")
