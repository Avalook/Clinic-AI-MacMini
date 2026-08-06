"""Bảng nhãn sự kiện phải theo kịp hệ thống, không theo hình dung của người viết.

BẰNG CHỨNG RẰNG NÓ ĐÃ LỆCH — và lệch theo cả hai chiều. Bảng nhãn cũ trong
``AuditLogBoard.tsx`` có 20 mã, trong khi prod đang phát 24 loại sự kiện:

    thiếu 15 mã đang chạy hằng ngày → 61/200 dòng hiện mã thô cho người vận hành
    thừa  8 mã chưa từng phát sinh  → nhãn cho những việc không tồn tại

Thêm nhãn cho 15 mã thiếu chỉ vá hiện trạng. Không có bài kiểm này thì đúng vòng
lặp ấy lặp lại: ai đó thêm một sự kiện mới, quên nhãn, và sáu tháng sau lại có
một nhúm dòng hiện `slot_hold.created` cho người không đọc được mã.

Bài kiểm quét CHÍNH MÃ NGUỒN chứ không quét database — nó phải chạy được trên
máy không có kết nối, và phải bắt được mã mới NGAY khi nó được viết ra, chứ
không đợi tới lúc nó phát ra dòng đầu tiên trên prod.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from clinicai.services.audit_labels import (
    EVENT_LABELS,
    WORK_ITEM_LABELS,
    action_label,
)

SRC = Path(__file__).resolve().parents[1] / "clinicai"

#: `event_type="..."` trong lời gọi `record_event`.
_KWARG = re.compile(r'event_type\s*=\s*"([a-z_]+\.[a-z_]+)"')

#: Chuỗi trong câu `INSERT INTO event_log ... VALUES (..., 'x.y', ...)`. Vài
#: service tự viết SQL thay vì gọi `record_event`; bỏ sót chúng thì bài kiểm
#: cho cảm giác an toàn giả.
#:
#: NHẬN CẢ HAI KIỂU NHÁY. Bản trước chỉ soi nháy đơn, nên mã đi vào như một
#: THAM SỐ PYTHON — `"visit.closed_incomplete" if incomplete else ...` ở cuối
#: lời gọi `conn.execute` của checkout_service — lọt qua. Nó lọt suốt từ lúc
#: được thêm, và người vận hành đọc chuỗi thô trên màn Lịch sử thao tác. Một
#: bài kiểm chống lệch mà bỏ sót đúng loại lệch nó canh thì tệ hơn không có.
_SQL_LITERAL = re.compile(r"""['"]([a-z_]+\.[a-z_]+)['"]""")


#: Câu chèn event_log, viết có hoặc không có tiền tố lược đồ.
#:
#: BẢN TRƯỚC CHỈ TÁCH THEO "INSERT INTO event_log". `checkout_service.py` viết
#: `INSERT INTO public.event_log`, nên CẢ FILE ẤY CHƯA TỪNG ĐƯỢC QUÉT — và
#: `visit.closed_incomplete` sống suốt không nhãn trong khi bài kiểm báo xanh.
_INSERT = re.compile(r"INSERT\s+INTO\s+(?:public\.)?event_log", re.IGNORECASE)

#: Cửa sổ quét sau mỗi câu chèn. Rộng hơn hẳn 1200 của bản trước: trong
#: `checkout_service` mã sự kiện là tham số CUỐI, nằm sau hai khối `json.dumps`
#: dài, cách câu INSERT 1353 ký tự — vừa đủ để lọt ra ngoài cửa sổ cũ.
_CUA_SO = 4000


def _ma_trong_ma_nguon() -> set[str]:
    ma: set[str] = set()
    for f in SRC.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        ma |= set(_KWARG.findall(text))
        # Chỉ soi chuỗi trong file CÓ ghi event_log — nếu không thì mọi chuỗi
        # dạng "a.b" trong toàn dự án (tên module, tên file) đều lọt vào.
        for m in _INSERT.finditer(text):
            ma |= set(_SQL_LITERAL.findall(text[m.end() : m.end() + _CUA_SO]))
    return ma


#: Chuỗi trông giống mã sự kiện nhưng không phải — tên công cụ LLM, tên module.
#: Liệt kê tường minh thay vì nới biểu thức, để một mã thật viết nhầm không lọt.
_KHONG_PHAI_SU_KIEN = {
    "brief.generate_brief",
    "communication.send_zalo_message",
    "event_log.append_event",
    "kb.read_policy",
    "lab.classify_lab_result",
    "lab.query_lab_result",
    "patient.get_patient_summary",
    "scheduling.cancel_appointment",
    "scheduling.confirm_appointment",
    "scheduling.create_appointment",
    "scheduling.find_oncall_staff",
    "scheduling.find_work_sessions",
    "service.aggregate_patient_context",
    "system.event_log",
    "task.check_task_sla",
    "task.create_task",
    "task.query_tasks",
}


class TestKhongLech:
    def test_moi_ma_trong_ma_nguon_deu_co_nhan(self) -> None:
        thieu = sorted(
            m
            for m in _ma_trong_ma_nguon() - _KHONG_PHAI_SU_KIEN
            if m not in EVENT_LABELS and m not in WORK_ITEM_LABELS
        )
        assert not thieu, (
            "Những mã sự kiện này được ghi vào event_log nhưng chưa có tên "
            f"tiếng Việt trong audit_labels.py: {thieu}. Người vận hành sẽ thấy "
            "mã thô trên màn Lịch sử thao tác."
        )

    def test_bai_kiem_that_su_tim_thay_ma(self) -> None:
        """Chốt cho chính bài kiểm: nếu biểu thức tìm kiếm hỏng thì tập rỗng sẽ
        làm bài trên LUÔN XANH mà không kiểm gì cả."""
        ma = _ma_trong_ma_nguon()
        assert len(ma) >= 20, f"chỉ tìm thấy {len(ma)} mã — biểu thức có vấn đề"
        assert "appointment.created" in ma
        assert "slot_hold.created" in ma


class TestNhan:
    @pytest.mark.parametrize(
        "ma",
        [
            "slot_hold.created",
            "clinic_settings.booking_policy_updated",
            "booking_override.slot_superseded",
            "lab_result.ordered",
            "dispatch.checkin",
            "appointment.rescheduled",
            "staff.created",
        ],
    )
    def test_nhung_ma_truoc_day_hien_tho_gio_da_co_ten(self, ma: str) -> None:
        assert action_label(ma) != ma

    def test_ma_la_thi_tra_ve_chinh_no(self) -> None:
        """Trả mã thô, KHÔNG trả chuỗi rỗng và không trả "Không rõ": ô trống
        đọc thành "không có gì xảy ra", còn mã thô thì tra cứu được và tự tố
        cáo rằng bảng nhãn đang thiếu."""
        assert action_label("chua_co.bao_gio") == "chua_co.bao_gio"

    def test_khong_nhan_nao_bo_trong(self) -> None:
        for ma, nhan in {**EVENT_LABELS, **WORK_ITEM_LABELS}.items():
            assert nhan.strip(), f"{ma} có nhãn rỗng"

    def test_khong_nhan_nao_lo_ma_ky_thuat(self) -> None:
        """Nhãn là thứ người vận hành đọc. "Tạo slot_hold" thì không giúp được
        ai — họ vẫn phải đi hỏi slot_hold là gì."""
        for ma, nhan in {**EVENT_LABELS, **WORK_ITEM_LABELS}.items():
            assert "_" not in nhan, f"{ma}: nhãn '{nhan}' còn tên bảng/cột"

    def test_khong_trung_nhan_trong_cung_mot_luong(self) -> None:
        """Hai sự kiện khác nhau mang cùng một tên thì nhật ký không phân biệt
        được chúng — và đó chính là việc của nhật ký."""
        nguoc: dict[str, list[str]] = {}
        for ma, nhan in EVENT_LABELS.items():
            nguoc.setdefault(nhan, []).append(ma)
        trung = {n: m for n, m in nguoc.items() if len(m) > 1}
        assert not trung, f"nhãn dùng lại cho nhiều mã: {trung}"
