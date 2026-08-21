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
    aggregate_label,
    source_label,
)

SRC = Path(__file__).resolve().parents[1] / "clinicai"
MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"

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


#: `event_type=f"x.{...}"` — MÃ GHÉP LÚC CHẠY, và lỗ thứ ba của bài kiểm này.
#:
#: `service_log.py:98` viết `f"service_log.{'started' if … else 'finished'}"`.
#: Không có chuỗi hằng nào tên `service_log.started` trong toàn dự án, nên hai
#: mã ấy lọt qua cả `_KWARG` lẫn `_SQL_LITERAL` từ ngày được viết — y hệt cách
#: `visit.closed_incomplete` từng lọt, chỉ đổi kiểu nguỵ trang.
#:
#: Lấy tiền tố trước dấu chấm rồi ghép với MỌI nhánh chuỗi trong cặp ngoặc: một
#: f-string hai nhánh cho ra hai mã, và cả hai đều phải có nhãn.
_FSTRING = re.compile(r'event_type\s*=\s*f"([a-z_]+)\.\{([^}]+)\}"')
_NHANH = re.compile(r"'([a-z_]+)'")

#: Vế phải của một phép so sánh KHÔNG phải nhánh giá trị. Trong
#: `{'started' if body.action == 'start' else 'finished'}` thì `'start'` là thứ
#: được đem ra so, không phải mã sự kiện — tính nhầm nó vào sẽ đòi nhãn cho
#: `service_log.start`, một mã không tồn tại. Cắt các vế so sánh đi trước khi
#: nhặt nhánh.
_VE_SO_SANH = re.compile(r"[=!]=\s*'[a-z_]+'")


def _ma_trong_ma_nguon() -> set[str]:
    ma: set[str] = set()
    for f in SRC.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        ma |= set(_KWARG.findall(text))
        for tien_to, than in _FSTRING.findall(text):
            nhanh = _NHANH.findall(_VE_SO_SANH.sub("", than))
            ma |= {f"{tien_to}.{n}" for n in nhanh}
        # Chỉ soi chuỗi trong file CÓ ghi event_log — nếu không thì mọi chuỗi
        # dạng "a.b" trong toàn dự án (tên module, tên file) đều lọt vào.
        for m in _INSERT.finditer(text):
            ma |= set(_SQL_LITERAL.findall(text[m.end() : m.end() + _CUA_SO]))
    return ma


#: Ràng buộc CHECK định nghĩa TRỌN VẸN tập lệnh của workflow kernel. Đọc thẳng
#: từ migration thay vì chép tay sang đây — chép tay chính là cách bảng nhãn cũ
#: vừa thiếu `create` (lệnh duy nhất có dữ liệu thật) vừa thừa bốn lệnh không
#: tồn tại. Bảng nhãn KHÔNG phải nguồn sự thật; ràng buộc mới là.
_CHECK_LENH = re.compile(
    r"work_item_event_command_check\s+CHECK\s*\(\s*command\s+IN\s*\(([^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)


def _lenh_workflow() -> set[str]:
    for f in sorted(MIGRATIONS.glob("*.sql")):
        khop = _CHECK_LENH.search(f.read_text(encoding="utf-8"))
        if khop:
            return {
                "work_item." + s.strip().strip("'")
                for s in khop.group(1).split(",")
                if s.strip()
            }
    raise AssertionError(
        "không tìm thấy work_item_event_command_check trong supabase/migrations "
        "— bài kiểm mất nguồn sự thật, sửa biểu thức trước khi tin kết quả"
    )


#: Đường ghi (`event_log.source`) viết thành chuỗi hằng. Bắt cả `origin=`,
#: `"origin":` lẫn tham số vị trí trong SQL — `api:`/`config.`/`cskh.` đủ đặc
#: trưng để không quét nhầm chuỗi khác.
_NGUON = re.compile(r"""['"]((?:api:|config\.|cskh\.)[a-z0-9:._-]+)['"]""")


#: Chuỗi trông giống mã sự kiện nhưng không phải — tên công cụ LLM, tên module,
#: và giá trị cột `source` (nơi phát ra sự kiện, không phải bản thân sự kiện).
#: Liệt kê tường minh thay vì nới biểu thức, để một mã thật viết nhầm không lọt.
_KHONG_PHAI_SU_KIEN = {
    "brief.generate_brief",
    "config.roster",  # cột source của roster.week_applied
    "config.booking_rule",  # cột source của booking.doctor_rule_saved
    "communication.send_zalo_message",
    "event_log.append_event",
    "kb.read_policy",
    "lab.classify_lab_result",
    "lab.query_lab_result",
    "patient.get_patient_summary",
    "reception.queue",  # cột source của reception.called_in{,_undone}
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
        # Mã ghép lúc chạy — chốt cho nhánh `_FSTRING`.
        assert "service_log.started" in ma

    def test_lenh_workflow_khop_dung_rang_buoc_check(self) -> None:
        """Hai chiều, vì bảng nhãn cũ sai cả hai.

        THIẾU thì người vận hành đọc chuỗi thô: `work_item.create` là lệnh DUY
        NHẤT đang có dữ liệu, và nó chưa từng có nhãn. THỪA thì bảng nhãn kể về
        những việc ràng buộc CHECK không cho phép xảy ra — claim, release,
        block, unblock — làm người đọc tưởng hệ thống có các bước ấy.
        """
        lenh = _lenh_workflow()
        assert lenh, "đọc được ràng buộc nhưng không tách ra lệnh nào"

        thieu = sorted(lenh - WORK_ITEM_LABELS.keys())
        assert not thieu, f"lệnh có thật nhưng chưa có nhãn tiếng Việt: {thieu}"

        thua = sorted(WORK_ITEM_LABELS.keys() - lenh)
        assert not thua, (
            f"nhãn cho lệnh ràng buộc CHECK không cho ghi: {thua}. Chúng chưa "
            "từng và không thể xảy ra."
        )

    def test_moi_duong_ghi_deu_ra_ten_man(self) -> None:
        """Ô "Làm ở màn" không được in địa chỉ mã nguồn.

        Bảng cũ nằm trong TSX với 7 mục cho hơn 30 đường ghi, nên phần lớn dòng
        hiện "api:booking-override", "api:appointment-checkin".
        """
        nguon: set[str] = set()
        for f in SRC.rglob("*.py"):
            nguon |= set(_NGUON.findall(f.read_text(encoding="utf-8")))
        assert len(nguon) >= 15, f"chỉ tìm thấy {len(nguon)} đường ghi — biểu thức hỏng"

        tho = sorted(n for n in nguon if source_label(n) == n)
        assert not tho, (
            f"những đường ghi này chưa có tên màn: {tho}. Thêm vào "
            "SOURCE_LABELS, hoặc thêm một tiền tố vào SOURCE_PREFIXES nếu cả họ "
            "cùng thuộc một màn."
        )

    def test_duong_ghi_ghep_luc_chay_van_ra_ten_man(self) -> None:
        """`f"api:appointment-{action}"` sinh 11 chuỗi, `f"api:service-{action}"`
        thêm hai. Khớp theo tiền tố phải phủ được cả những chuỗi chưa ai viết
        ra — nếu không thì mỗi hành động mới lại lòi một dòng chữ máy."""
        for action in ("confirm", "no_show", "assign_doctor", "chua_co_bao_gio"):
            ma = f"api:appointment-{action}"
            assert source_label(ma) == "Màn Đặt lịch", ma
        assert source_label("api:service-start") == "Danh sách dịch vụ"

    def test_ma_su_kien_cua_thong_bao_deu_co_nhan(self) -> None:
        """Bảng `NGUON` của thong_bao_service là một điểm mù của bộ quét.

        Mã sự kiện ở đó đi vào `event_log` như THAM SỐ ($5), không phải chuỗi
        hằng cạnh câu INSERT — nên `_SQL_LITERAL` không thấy, và một nguồn thông
        báo mới sẽ lặng lẽ in mã thô ra màn Lịch sử thao tác đúng như
        `work_item.create` từng làm.

        Bài kiểm này đọc thẳng bảng ấy thay vì quét chuỗi, nên nó không mù.
        """
        from clinicai.services.thong_bao_service import NGUON

        thieu = sorted(
            ma
            for ma, _duong_ghi in NGUON.values()
            if ma not in EVENT_LABELS and ma not in WORK_ITEM_LABELS
        )
        assert not thieu, (
            f"nguồn thông báo chưa có nhãn tiếng Việt: {thieu}. Thêm vào "
            "EVENT_LABELS — bộ quét chuỗi KHÔNG bắt được chúng."
        )

    def test_duong_ghi_cua_thong_bao_deu_ra_ten_man(self) -> None:
        """Cùng điểm mù, cột "Làm ở màn"."""
        from clinicai.services.thong_bao_service import NGUON

        tho = sorted(dg for _ma, dg in NGUON.values() if source_label(dg) == dg)
        assert not tho, f"đường ghi của thông báo chưa có tên màn: {tho}"

    def test_loai_doi_tuong_deu_co_ten(self) -> None:
        """Cái chip ở đầu ô chi tiết in tên BẢNG khi thiếu nhãn.

        Danh sách lấy từ `aggregate_type=` trong mã nguồn cộng những giá trị chỉ
        xuất hiện trong câu SQL tự viết — `roster_week` là cái đang lộ ra trên
        bản thật.
        """
        tu_kwarg = set(
            re.findall(
                r'aggregate_type\s*=\s*"([a-z_]+)"',
                "\n".join(f.read_text(encoding="utf-8") for f in SRC.rglob("*.py")),
            )
        )
        tu_sql = {
            "appointment",
            "booking_override",
            "clinic",
            "lab_result",
            "patient",
            "payment",
            "roster_week",
            "service_log",
            "slot_hold",
            "visit",
            "work_item",
        }
        tho = sorted(m for m in tu_kwarg | tu_sql if aggregate_label(m) == m)
        assert not tho, f"loại đối tượng chưa có tên tiếng Việt: {tho}"


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
