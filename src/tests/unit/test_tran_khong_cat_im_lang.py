"""Câu có `LIMIT` phục vụ màn hình phải nói ra khi nó cắt.

VÌ SAO CÓ BÀI NÀY. Bảng "Chỉ định hôm nay" của trưởng ca cắt ở 500 dòng mà không
báo gì: hôm nào đông hơn thế, trưởng ca nhìn một bảng THIẾU NGƯỜI và tưởng đã
hết. Phát hiện tình cờ vì một bài kiểm đỏ khi database thử tích đủ dữ liệu — tức
là suốt thời gian trước đó không lớp kiểm nào thấy.

BÀI NÀY LÀ MỘT BÁNH CÓC. Số chỗ cắt-im-lặng chỉ được phép GIẢM. Thêm một câu
`LIMIT` mới mà không nói ra thì đỏ ngay, kèm hướng dẫn dùng
`clinicai.core.tran`.

Danh sách dưới đây là những chỗ **cố ý** cắt và cắt như thế là đúng: lịch sử gần
đây, gợi ý vài dòng, bản xuất dữ liệu. Chúng vẫn nằm trong danh sách để ai đọc
bài kiểm này biết chúng đã được cân nhắc, chứ không phải bị bỏ sót.
"""

from __future__ import annotations

import re
from pathlib import Path

_GOC = Path(__file__).resolve().parents[2] / "clinicai"
_LIMIT = re.compile(r"\bLIMIT\s+(\d{2,})")

#: Chỗ cắt là ĐÚNG và hiển nhiên với người dùng — không cần nói thêm.
#: Mỗi dòng là "file: vì sao". Danh sách này chỉ được phép NGẮN ĐI.
CAT_CO_CHU_Y: dict[str, str] = {
    "services/clinical_form_service.py": "20 lần khám gần nhất — màn nói rõ 'gần đây'",
    "services/consent_service.py": "20 bản đồng ý gần nhất",
    "services/console_service.py": "20 dòng bảng điều khiển chủ sản phẩm",
    "services/xem_luot_service.py": "lịch sử/sinh hiệu của MỘT lượt, 20–30 dòng",
    "services/thong_bao_service.py": "50 thông báo gần nhất của một người",
    "services/patient_service.py": "10 gợi ý trùng số điện thoại",
    "services/man_khach_hang_service.py": "bản xuất dữ liệu, 5000 dòng",
    "services/config_service.py": "danh mục cấu hình",
    "services/cashier_board_service.py": "sổ giao dịch theo khoảng ngày đã chọn",
}

#: Sáu tên đã RỜI danh sách ngày 23/09/2026 sau khi rà: nhà thuốc · nhắc tái
#: khám · ba bảng tệp kết quả · hai bảng siêu âm · lịch chờ xếp bác sĩ · kết quả
#: xét nghiệm chờ duyệt. Tất cả nay gọi `canh_bao_neu_day`, và chỗ nào trả về
#: dict thì kèm `bi_cat` + `tran` để màn nói được "đã đạt trần N".


def _file_co_limit() -> dict[str, int]:
    ket: dict[str, int] = {}
    for f in sorted(_GOC.rglob("*.py")):
        so = len(_LIMIT.findall(f.read_text(encoding="utf-8")))
        if so:
            ket[str(f.relative_to(_GOC))] = so
    return ket


def test_file_co_limit_thi_phai_noi_ra_hoac_nam_trong_danh_sach() -> None:
    thieu = []
    for ten in _file_co_limit():
        if ten in CAT_CO_CHU_Y:
            continue
        noi_dung = (_GOC / ten).read_text(encoding="utf-8")
        if "canh_bao_neu_day" in noi_dung or "dem_va_bi_cat" in noi_dung:
            continue
        if "bi_cat" in noi_dung:
            continue
        thieu.append(ten)
    assert not thieu, (
        "Những file này có câu LIMIT mà cắt trong im lặng. Dùng "
        "`clinicai.core.tran.canh_bao_neu_day` (tối thiểu) hoặc trả thêm "
        "`tong`/`bi_cat` cho màn (tốt nhất):\n  " + "\n  ".join(thieu)
    )


def test_danh_sach_cat_co_chu_y_chi_duoc_ngan_di() -> None:
    """Bánh cóc: không ai được thêm chỗ cắt-im-lặng mới vào danh sách."""
    assert len(CAT_CO_CHU_Y) <= 9, (
        "Danh sách 'cắt có chủ ý' đang dài ra. Nó chỉ được phép ngắn đi: rà từng "
        "chỗ rồi nói ra khi cắt, đừng thêm ngoại lệ."
    )


def test_khong_ai_xoa_nhan_khoi_danh_sach_ma_khong_sua_code() -> None:
    """Tên trong danh sách phải là file có thật — đổi tên file thì sửa cả đây."""
    thieu = [ten for ten in CAT_CO_CHU_Y if not (_GOC / ten).exists()]
    assert not thieu, f"Danh sách trỏ tới file không còn tồn tại: {thieu}"
