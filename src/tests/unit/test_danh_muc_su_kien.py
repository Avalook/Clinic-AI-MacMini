"""Danh mục sự kiện phải tự giữ luật — CI kiểm, không phải người kiểm.

Bài kiểm nhãn cũ (`test_audit_labels_drift`) chỉ so hai danh sách chuỗi, nên mã đi
qua hằng số hay biểu thức ba ngôi thì lọt. Ở đây danh mục LÀ nguồn sự thật: sự
kiện nào không khai thì `emit_event` từ chối phát, nên chỉ cần giữ luật cho chính
danh mục.

Bài cuối là một **bánh cóc**: số chỗ ghi thẳng `event_log` chỉ được phép giảm.
Không có nó thì mỗi lần vội lại thêm một chỗ, và việc dọn nền không bao giờ xong.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from clinicai.events.catalogue import DANH_MUC, DONG_TU_CAM, moi_consumer, tra

TEN_HOP_LE = re.compile(r"^[a-z_]+\.[a-z_]+$")
GOC_REPO = Path(__file__).resolve().parents[3]

# Ngày 23/09/2026 đếm được 15 chỗ `INSERT INTO event_log` nằm ngoài audit.py.
# Con số này CHỈ ĐƯỢC GIẢM. Muốn thêm sự kiện mới thì dùng emit_event.
TRAN_GHI_THANG_EVENT_LOG = 15


@pytest.mark.parametrize("ten", sorted(DANH_MUC))
def test_ten_dung_khuon(ten: str) -> None:
    """`danh_từ.việc_đã_xảy_ra`, chữ thường, đúng một dấu chấm."""
    assert TEN_HOP_LE.match(ten), f"'{ten}' sai khuôn tên sự kiện"


@pytest.mark.parametrize("ten", sorted(DANH_MUC))
def test_khong_dung_dong_tu_cam(ten: str) -> None:
    """Không đặt tên kiểu mệnh lệnh hay vô nghĩa.

    `service.route_needed` là VIỆC CẦN LÀM (phải thành work_item), không phải
    chuyện đã xảy ra. `visit.updated` thì không nói lên điều gì để ai phản ứng.
    """
    duoi = ten.split(".", 1)[1]
    assert duoi not in DONG_TU_CAM, (
        f"'{ten}': '{duoi}' là mệnh lệnh hoặc vô nghĩa, không phải sự thật đã xảy ra"
    )


@pytest.mark.parametrize("ten", sorted(DANH_MUC))
def test_payload_dong_kin(ten: str) -> None:
    """Trường lạ phải bị chặn ngay lúc phát, không chờ consumer đọc phải."""
    su_kien = DANH_MUC[ten]
    assert su_kien.payload.model_config.get("extra") == "forbid"


@pytest.mark.parametrize("ten", sorted(DANH_MUC))
def test_co_nhan_tieng_viet(ten: str) -> None:
    """Màn nhật ký đọc nhãn này; thiếu nhãn là màn hiện mã kỹ thuật."""
    assert DANH_MUC[ten].nhan.strip(), f"'{ten}' chưa có nhãn tiếng Việt"


@pytest.mark.parametrize("ten", sorted(DANH_MUC))
def test_khai_dung_ten_cua_chinh_no(ten: str) -> None:
    assert DANH_MUC[ten].ten == ten


def test_ten_consumer_khong_rong() -> None:
    for consumer in moi_consumer():
        assert consumer.strip() == consumer and consumer, "tên bên nhận không hợp lệ"


def test_su_kien_chua_khai_thi_hong_ngay() -> None:
    with pytest.raises(ValueError, match="chưa khai trong danh mục"):
        tra("khong_he_ton_tai.placed")


def test_so_cho_ghi_thang_event_log_chi_duoc_giam() -> None:
    """Bánh cóc: đường ghi cũ chỉ được ít đi, không được nhiều thêm."""
    ket_qua = subprocess.run(
        [
            "grep",
            "-rn",
            "INSERT INTO event_log",
            "--include=*.py",
            str(GOC_REPO / "src" / "clinicai"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    cho_ghi_thang = [
        dong
        for dong in ket_qua.stdout.splitlines()
        if dong.strip() and "/services/audit.py:" not in dong
    ]
    assert len(cho_ghi_thang) <= TRAN_GHI_THANG_EVENT_LOG, (
        "Có thêm chỗ ghi thẳng event_log. Dùng emit_event (sự kiện nghiệp vụ) "
        "hoặc record_event (nhật ký thao tác):\n" + "\n".join(cho_ghi_thang)
    )
