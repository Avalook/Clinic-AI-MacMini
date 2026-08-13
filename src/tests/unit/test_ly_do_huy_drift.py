"""Danh mục lý do huỷ ở backend và ở giao diện phải khớp từng chữ.

VÌ SAO CÓ BÀI NÀY. Ba màn cùng vẽ danh sách này — Quản lý khách hàng, Công việc
của tôi, và chỗ hiển thị lịch đã huỷ. Nếu mỗi nơi tự chép một bản thì một hôm
ai đó sửa chữ ở một chỗ, và cùng một lần huỷ sẽ được hai màn gọi bằng hai tên.
Tệ hơn: sửa MÃ ở một bên thì backend từ chối mọi lần huỷ từ màn kia, và lỗi ấy
chỉ lộ ra khi có người thật bấm nút thật.

Dự án đã có hai bài cùng kiểu (`test_audit_labels_drift`, `test_nav_role_drift`)
— đây là bài thứ ba, cùng lý do.
"""

from __future__ import annotations

import re
from pathlib import Path

from clinicai.services.booking_service import LY_DO_HUY

_TS = Path(__file__).resolve().parents[3] / "src" / "dashboard" / "lib" / "ly-do-huy.ts"
_MIGRATIONS = Path(__file__).resolve().parents[3] / "supabase" / "migrations"

#: BẢN THỨ BA của danh mục — ràng buộc CHECK ở database.
#:
#: Bài kiểm này ra đời để chặn lệch giữa backend và giao diện, và nó làm đúng
#: việc ấy. Nhưng danh mục có BA bản, không phải hai: cột `appointment
#: .ly_do_huy_ma` có một ràng buộc liệt kê cứng các mã hợp lệ.
#:
#: Ngày 09/08/2026 thêm mã `DAT_TRUNG` vào hai bản Python/TS, bài kiểm xanh, và
#: nút "Bỏ lịch này" trả về "An internal server error occurred." cho người dùng
#: thật — CheckViolationError từ database, nổi lên thành 500 vì nó không phải
#: ValidationError mà tầng API biết dịch. Đúng kịch bản docstring trên mô tả,
#: chỉ khác là bản trốn được nằm ở database.
_CHECK_LY_DO = re.compile(
    r"appointment_ly_do_huy_ma_check\s*\n?\s*CHECK\s*\((.*?)\);",
    re.IGNORECASE | re.DOTALL,
)


def _doc_rang_buoc() -> set[str]:
    """Mã hợp lệ theo migration MỚI NHẤT có định nghĩa ràng buộc ấy."""
    ma: set[str] | None = None
    for f in sorted(_MIGRATIONS.glob("*.sql")):
        for khop in _CHECK_LY_DO.finditer(f.read_text(encoding="utf-8")):
            tim_thay = set(re.findall(r"'([A-Z_]+)'", khop.group(1)))
            if tim_thay:
                ma = tim_thay
    assert ma, (
        "không đọc được appointment_ly_do_huy_ma_check từ supabase/migrations "
        "— bài kiểm mất nguồn sự thật, sửa biểu thức trước khi tin kết quả"
    )
    return ma


def _doc_ts() -> dict[str, str]:
    noi_dung = _TS.read_text(encoding="utf-8")
    than = re.search(
        r"export const LY_DO_HUY: Record<string, string> = \{(.*?)\n\};",
        noi_dung,
        re.S,
    )
    assert than, "không tìm thấy LY_DO_HUY trong ly-do-huy.ts"
    return dict(re.findall(r"^\s*(\w+):\s*\"([^\"]+)\",\s*$", than.group(1), re.M))


def test_ma_va_chu_khop_nhau() -> None:
    ts = _doc_ts()
    assert ts == LY_DO_HUY, (
        "Danh mục lý do huỷ đã lệch giữa backend và giao diện.\n"
        f"  chỉ có ở backend : {sorted(set(LY_DO_HUY) - set(ts))}\n"
        f"  chỉ có ở giao diện: {sorted(set(ts) - set(LY_DO_HUY))}\n"
        f"  khác chữ          : "
        f"{sorted(k for k in set(ts) & set(LY_DO_HUY) if ts[k] != LY_DO_HUY[k])}"
    )


def test_rang_buoc_database_nhan_dung_bo_ma_ay() -> None:
    """Bản thứ ba phải khớp hai bản kia — nếu không, nút huỷ trả 500.

    Thiếu một mã ở đây là database TỪ CHỐI lần huỷ mà cả backend lẫn giao diện
    đều coi là hợp lệ, và người dùng nhận một lỗi máy chủ không giải thích được.
    Thừa một mã thì ngược lại: cột dùng để đếm "khách báo không đến ở khâu nào"
    nhận được giá trị không màn nào vẽ ra, và con số lặng lẽ sai.
    """
    trong_db = _doc_rang_buoc()
    assert trong_db == set(LY_DO_HUY), (
        "Danh mục lý do huỷ lệch giữa mã nguồn và ràng buộc CHECK.\n"
        f"  database từ chối : {sorted(set(LY_DO_HUY) - trong_db)}\n"
        f"  database cho, mà mã nguồn không có: {sorted(trong_db - set(LY_DO_HUY))}"
    )


def test_thu_tu_ve_du_ma_khong_thua() -> None:
    """Ô chọn phải vẽ đủ bốn mã — thiếu một là mã đó không ai chọn được."""
    noi_dung = _TS.read_text(encoding="utf-8")
    than = re.search(r"LY_DO_HUY_THU_TU: string\[\] = \[(.*?)\];", noi_dung, re.S)
    assert than
    thu_tu = re.findall(r"\"(\w+)\"", than.group(1))
    assert set(thu_tu) == set(LY_DO_HUY)
    assert len(thu_tu) == len(set(thu_tu)), "có mã bị lặp trong thứ tự hiển thị"
    # "Khác" đứng cuối: ba mã kia là ba thời điểm theo trình tự, còn "khác" là
    # chỗ rơi. Để nó lên đầu thì người dùng chọn nó cho nhanh, và cột này thành
    # 100% "khác" — đúng thứ nó sinh ra để chống.
    assert thu_tu[-1] == "KHAC"
