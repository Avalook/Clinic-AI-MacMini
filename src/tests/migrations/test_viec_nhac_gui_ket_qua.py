"""Tệp kết quả CSKH tải lên phải sinh việc nhắc gửi.

VÌ SAO CÓ BÀI NÀY, đo được 12/08/2026:

Luật "Có kết quả, chưa gửi" (`luat_cskh.KQ_CHUA_GUI`) có thật, bật, hạn 1 ngày —
và nó đọc bảng `lab_result`. Nhưng CSKH không ghi vào `lab_result` được: mọi
endpoint viết vào bảng ấy gác cho vai lâm sàng. Cái CSKH thật sự làm là TẢI TỆP
phiếu kết quả lên `tep_ket_qua`, và `v_viec_cskh` không hề nhắc tới bảng đó.

Nghĩa là với mọi kết quả CSKH xử lý bằng cách tải tệp, KHÔNG có đường nào sinh
ra lời nhắc. Đo thật trên staging trước khi sửa: tải một tệp → 201 → không việc
nào xuất hiện → tệp nằm im với `gui_luc IS NULL`. Khách có thể không bao giờ
nhận được kết quả xét nghiệm, và phòng khám không có cách nào biết.

Đây là hậu quả nặng nhất trong danh sách tồn đọng, và nó thuộc đúng hình dạng
lỗi lặp lại của dự án: LUẬT ĐÚNG, NỐI VÀO SAI NGUỒN.

Bài này quét chuỗi trong file migration, không cần database. Nó không kiểm việc
sinh ra có đúng hạn hay không — chuyện đó đã đo bằng tay trên staging (tải lên →
việc KQ_CHUA_GUI hiện, hạn +1 ngày; đánh dấu đã gửi → việc biến mất) — nó canh
cho nhánh `tep_ket_qua` không bị đánh rơi trong một lần viết lại view sau này.
"""

from __future__ import annotations

import pathlib
import re

MIGRATIONS = pathlib.Path(__file__).resolve().parents[3] / "supabase" / "migrations"


def _bo_chu_thich(sql: str) -> str:
    """Bỏ mọi dòng chú thích `--`.

    BẮT BUỘC PHẢI LÀM, không phải cho gọn: thân view có một dòng chú thích giải
    thích vì sao nhánh mới đọc `tep_ket_qua` chứ không phải `lab_result`. Không
    bỏ nó thì bài kiểm này XANH kể cả khi ai đó xoá sạch nhánh SQL mà để lại
    chú thích — tức là nó kiểm chú thích chứ không kiểm luật.

    Cắt thô theo `--`: thân view này không có chuỗi nào chứa `--` bên trong.
    """
    return "\n".join(dong.split("--", 1)[0] for dong in sql.splitlines())


def _dinh_nghia_view_moi_nhat(ten: str) -> tuple[pathlib.Path, str]:
    """Lần CREATE OR REPLACE VIEW SAU CÙNG của một view, theo thứ tự migration.

    Đọc bản cuối chứ không phải bản đầu: `v_viec_cskh` đã được viết lại nhiều
    lần (20260810000008, 20260810000009, 20260811000001…) và chỉ bản cuối là bản
    đang chạy trên máy chủ.
    """
    mo = re.compile(
        r"CREATE\s+OR\s+REPLACE\s+VIEW\s+(?:public\.)?" + re.escape(ten) + r"\b",
        re.IGNORECASE,
    )
    tim_thay: tuple[pathlib.Path, str] | None = None
    for f in sorted(MIGRATIONS.glob("*.sql"), key=lambda p: p.name):
        if f.name.endswith(".down.sql"):
            continue
        noi_dung = f.read_text(encoding="utf-8")
        for khop in mo.finditer(noi_dung):
            # BỎ CHÚ THÍCH TRƯỚC, CẮT SAU — thứ tự này quan trọng.
            #
            # Làm ngược lại thì một dấu `;` nằm trong câu chú thích tiếng Việt sẽ
            # bị nhầm là dấu kết câu SQL và thân view bị cắt cụt ngay giữa chừng.
            # Đã xảy ra thật khi viết bài này: chú thích "...`tep_ket_qua`;
            # `lab_result` là..." làm mất đúng cái nhánh cần kiểm, và bài kiểm
            # báo đỏ cho một migration hoàn toàn đúng.
            phan_sau = _bo_chu_thich(noi_dung[khop.end() :])
            ket = phan_sau.find(";")
            tim_thay = (f, phan_sau[: ket if ket >= 0 else len(phan_sau)])
    assert tim_thay is not None, (
        f"Không tìm thấy định nghĩa nào của view `{ten}` trong {MIGRATIONS}."
    )
    return tim_thay


def test_view_viec_cskh_doc_ca_tep_ket_qua() -> None:
    duong_dan, than = _dinh_nghia_view_moi_nhat("v_viec_cskh")
    assert "tep_ket_qua" in than, (
        f"`v_viec_cskh` (bản mới nhất ở {duong_dan.name}) không đọc bảng "
        "`tep_ket_qua`. Nghĩa là phiếu kết quả CSKH tải lên rồi quên gửi sẽ "
        "không nhắc ai cả — đúng lỗi mà migration 20260812000001 sinh ra để sửa."
    )


def test_viec_nhac_gui_chi_tinh_tep_chua_gui() -> None:
    """Nhánh mới phải lọc `gui_luc IS NULL`, nếu không việc không bao giờ đóng."""
    duong_dan, than = _dinh_nghia_view_moi_nhat("v_viec_cskh")
    # Neo vào ĐÚNG mệnh đề `FROM tep_ket_qua`, không phải lần nhắc tên bảng đầu
    # tiên: `tuong_tac_cskh` cũng có cột tên `gui_luc`, nên một cửa sổ đặt lệch
    # chỗ có thể bắt trúng bộ lọc của nhánh khác và báo XANH nhầm.
    khop = re.search(r"FROM\s+(?:public\.)?tep_ket_qua\b", than, re.IGNORECASE)
    assert khop is not None, (
        f"`v_viec_cskh` ({duong_dan.name}) nhắc tên `tep_ket_qua` nhưng không "
        "có mệnh đề FROM nào đọc bảng ấy."
    )
    doan = than[khop.end() : khop.end() + 600]
    assert re.search(r"gui_luc\s+IS\s+NULL", doan, re.IGNORECASE), (
        f"Nhánh `tep_ket_qua` trong `v_viec_cskh` ({duong_dan.name}) không lọc "
        "`gui_luc IS NULL`. Thiếu nó thì việc nhắc gửi vẫn hiện SAU KHI đã gửi, "
        "và một danh sách việc không bao giờ vơi là danh sách người ta ngừng đọc."
    )
