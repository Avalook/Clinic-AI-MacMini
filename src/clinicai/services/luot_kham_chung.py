"""Dùng chung cho các khối của lượt khám — tập vai, luật gác theo vai, định dạng.

Bóc khỏi ``luot_kham_service`` ngày 24/09/2026 (bước 5 đợt bóc lõi) để các màn
ĐỌC (``luot_kham_doc``) và khối Khám cùng dùng mà không phải mượn nhau. Các tập
vai ở đây là HỆ CŨ (gác theo vai); đường khám chính đã hỏi QUYỀN (capability).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog

from clinicai.api.identity import (
    VAI_LAM_VIEC,
    ClinicRole,
    StaffIdentity,
    mo_quyen_tam_thoi,
)
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import luot_kham_rules as rules

# Hai lỗi có mã nay ở nền chung; xuất lại ở đây (dạng `X as X`) để nơi cũ
# `from luot_kham_service import LuotKhamConflictError` vẫn đúng.
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError as LuotKhamConflictError,
)
from clinicai.services.lenh_kham_core import (
    LuotKhamValidationError as LuotKhamValidationError,
)

logger = structlog.get_logger()

ORIGIN = "api:luot-kham"


BOARD_ROLES = frozenset(
    {
        ClinicRole.RECEPTION,
        ClinicRole.NURSE_ULTRASOUND,
        ClinicRole.DOCTOR,
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.TKYK,
        ClinicRole.TRUONG_CA,
        ClinicRole.MANAGEMENT,
    }
)
CHECKIN_ROLES = frozenset({ClinicRole.RECEPTION, ClinicRole.MANAGEMENT})
VITALS_ROLES = frozenset(
    {ClinicRole.NURSE_ULTRASOUND, ClinicRole.RECEPTION, ClinicRole.DOCTOR}
)
DOCTOR_ROLES = frozenset({ClinicRole.DOCTOR})
#: Bấm "Bắt đầu khám" / "Đã khám xong" — bác sĩ, hoặc thư ký đi kèm bác sĩ ấy
#: (Tuyền 16/09/2026: *"check-in check-out cho khách ở từng phòng sẽ do thư ký
#: đi kèm bác sĩ hoặc bác sĩ làm"*). DUYỆT chỉ định vẫn chỉ bác sĩ.
CONSULT_ROLES = frozenset({ClinicRole.DOCTOR, ClinicRole.TKYK})
NOTE_ROLES = frozenset({ClinicRole.DOCTOR, ClinicRole.TKYK})
DRAFT_ROLES = frozenset({ClinicRole.TKYK})
DISPATCH_ROLES = frozenset({ClinicRole.TRUONG_CA, ClinicRole.MANAGEMENT})
#: Duyệt kết quả + cho phép gửi (Notion v1.0.0: bác sĩ chính & bác sĩ siêu âm/xét
#: nghiệm). Không nới theo công tắc — đây là quyết định chuyên môn.
REVIEW_ROLES = frozenset({ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR})
PERFORMER_ROLES = frozenset(
    {
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.NURSE_ULTRASOUND,
        ClinicRole.DOCTOR,
        ClinicRole.TKYK,
    }
)
#: NGƯỜI ĐI KÈM Ở PHÒNG DỊCH VỤ (Tuyền 17/09/2026): điều dưỡng hoặc thư ký đi
#: cùng bác sĩ thủ thuật / siêu âm GỌI khách, CHECK-IN (Bắt đầu) và CHECK-OUT
#: (Xong) — y như ở bàn khám bác sĩ chính. Chuyên môn vẫn là của bác sĩ: node
#: giữ actor_roles = DOCTOR, và bác sĩ bấm Xong thì được ghi là người thực hiện.
HO_TRO_PHONG = frozenset({ClinicRole.NURSE_ULTRASOUND, ClinicRole.TKYK})
#: MỘT điều kiện cho câu hỏi "chỉ định `o` còn là VIỆC DỞ của lượt không" —
#: dùng chung cho Hoàn tất (`kham_xong`), tự khép lượt (`_ket_thuc_neu_xong`)
#: và check-out (`checkout_service`). Ba chỗ từng tự viết riêng, lệch nhau:
#: chỉ định khách ĐÃ BỎ (NOT_SELECTED) hay đã được bác sĩ MIỄN / chuyển THEO
#: DÕI vẫn bị đếm là việc dở → vòng đọc mở lại mãi, lượt không khép, quầy không
#: check-out được (mô phỏng 20 khách, 24/09/2026). Chỉ định CHƯA CHỌN vẫn tính:
#: khách chưa quyết. Đòi alias `o` cho `service_order`.
CHI_DINH_CON_VIEC_SQL = """
    o.exec_status IN ('authorized', 'assigned', 'in_progress')
    AND coalesce(o.selection_status, 'PENDING') <> 'NOT_SELECTED'
    AND NOT EXISTS (
        SELECT 1 FROM public.round_requirement q_mien
         WHERE q_mien.clinic_id = o.clinic_id
           AND q_mien.service_order_id = o.id
           AND q_mien.status IN ('waived', 'follow_up'))
"""

# VIỆC CÒN DỞ GIỮ LƯỢT LẠI — như trên nhưng BỎ việc làm bên ngoài (đối tác).
#
# Tuyền chốt 28/09/2026: *"bên đối tác bận việc chưa nhấn cũng được không sao,
# mình cứ open nhé, cứ coi như thao tác để ghi lại sự kiện để sau này thống kê
# … quan trọng nhất vẫn là phục vụ khách"*. Nút "Đã lấy mẫu / Nhận mẫu" của đối
# tác chỉ GHI SỰ KIỆN, không phải cửa của lượt khám. Trước đây đối tác chưa bấm
# thì chỉ định vẫn "authorized" → lượt không khép (quầy thu, đóng lượt đợi mốc
# ấy) và quầy đóng lượt báo "còn dịch vụ chưa làm" — kể cả khi kết quả đã về.
# Việc chờ KẾT QUẢ đối tác vẫn được giữ đúng chỗ của nó: yêu cầu VALID_RESULT
# của vòng đọc (bác sĩ đọc, hoặc chuyển theo dõi) — không qua nút của đối tác.
#
# Chỉ dùng cho hai câu hỏi "lượt còn giữ lại không" (khép lượt, đóng lượt).
# Lúc bác sĩ kết thúc phiên vẫn dùng CHI_DINH_CON_VIEC_SQL để việc đối tác còn
# sinh yêu cầu "cần kết quả".
CHI_DINH_CON_VIEC_GIU_LUOT_SQL = (
    CHI_DINH_CON_VIEC_SQL
    + """    AND NOT EXISTS (
        SELECT 1 FROM public.node_definition n_ngoai
         WHERE n_ngoai.clinic_id = o.clinic_id
           AND n_ngoai.code = o.node_code
           AND n_ngoai.lam_ben_ngoai)
"""
)

#: "YÊU CẦU CỦA VÒNG ĐỌC ĐÃ CÓ KẾT QUẢ CHƯA" — một chỗ cho mọi câu đọc vòng
#: (chạy lại vòng, "chờ bác sĩ quyết"). Đòi alias `o` (service_order) và `nd`
#: (node_definition, LEFT JOIN).
#:
#: VIỆC ĐỐI TÁC: NHẬN MẪU LÀ XONG (Tuyền 29/09/2026 — *"Phải xong để bác sĩ,
#: điều dưỡng, TKYK cùng thao tác cho khách còn về, chứ không 1 ca khám bao giờ
#: mới kết thúc"*). Mốc nhận mẫu (`doi_tac_cho_tai_lieu_luc`, chỉ bàn đối tác
#: ghi được) thoả yêu cầu — cả bước làm bên ngoài lẫn MẪU GỬI ĐỐI TÁC. Kết quả
#: đối tác về sau KHÔNG giữ vòng: nó báo chuông, ai cũng xem được.
#: Còn lại như cũ: làm bên ngoài cần tệp HOP_LE; nội bộ cần `ket_qua_luc`.
CO_KET_QUA_VONG_SQL = """(
    o.doi_tac_cho_tai_lieu_luc IS NOT NULL
    OR CASE
         WHEN coalesce(nd.lam_ben_ngoai, false) THEN
           EXISTS (
             SELECT 1 FROM public.v_tep_ket_qua_hieu_luc t_kq
              WHERE t_kq.clinic_id = o.clinic_id
                AND t_kq.service_order_id = o.id
                AND t_kq.xac_nhan_trang_thai = 'HOP_LE'
           )
         ELSE o.ket_qua_luc IS NOT NULL
       END
)"""

# Ai đọc được nội dung khám (ghi chú, kết quả). Lễ tân và trưởng ca làm việc
# với trạng thái, không cần đọc chữ bác sĩ viết.
CLINICAL_READ_ROLES = frozenset(
    {
        ClinicRole.DOCTOR,
        ClinicRole.TKYK,
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.NURSE_ULTRASOUND,
    }
)

_CAU_CHAN_DIEU_PHOI = {
    "NO_VALID_ORDER": "Chỉ định này chưa được bác sĩ duyệt — chưa điều phối được.",
    "ORDER_NOT_DISPATCHABLE": "Chỉ định này không còn ở trạng thái điều phối được.",
    "PLAN_NOT_APPLIED": "Kế hoạch trước chưa được áp hợp lệ cho lượt khám này.",
    # KHÔNG CÒN PHÁT từ 23/09/2026 (Tuyền chốt: sinh hiệu không chặn xếp phòng).
    # Giữ lại để đọc được nhật ký cũ — một bản ghi kiểm toán không đọc lại được
    # là một bản ghi vô dụng.
    "VITALS_REQUIRED": (
        "Khách chưa được đo huyết áp — đo sinh hiệu trước khi điều phối."
    ),
    "ROUTE_NOT_DECIDED": "Lượt khám chưa xác định bước tiếp theo.",
    "HELD_UNTIL_ROUND": "Bác sĩ dặn làm dịch vụ này sau khi đọc kết quả vòng trước.",
}

_LIVE = "('done', 'left', 'cancelled')"


#: Những tập vai NỚI ĐƯỢC theo công tắc mở quyền tạm thời. Tập nào KHÔNG có ở
#: đây thì không bao giờ nới: `DOCTOR_ROLES`, `NOTE_ROLES`, `DRAFT_ROLES` là
#: việc của bác sĩ và thư ký cạnh bác sĩ — Tuyền nói rõ "trừ bác sĩ ra thui".
#:
#: `CLINICAL_READ_ROLES` cũng KHÔNG nới: nó quyết định ai đọc được chữ bác sĩ
#: viết trong bệnh án, và đó là đọc hồ sơ y tế chứ không phải thao tác vận hành.
_TAP_NOI_DUOC: tuple[frozenset[ClinicRole], ...] = (
    BOARD_ROLES,
    CHECKIN_ROLES,
    VITALS_ROLES,
    DISPATCH_ROLES,
    PERFORMER_ROLES,
)


def _require(identity: StaffIdentity, roles: frozenset[ClinicRole], cau: str) -> None:
    """Chặn theo vai — và đây là cửa THẬT, cửa ở router chỉ là lớp ngoài.

    Luật nghiệp vụ nằm trong hàm dịch vụ (CLAUDE.md), nên nới `require_role` ở
    router mà quên chỗ này thì vai mới qua được cửa ngoài rồi ăn `SafetyGateError`
    ở cửa trong — đúng cái đã xảy ra chiều 16/09: CSKH và thu ngân vẫn 403 ở
    bảng lượt khám sau khi đã nới router, và cửa gác ở router thì trông hoàn
    toàn đúng.
    """
    # So theo ĐÚNG TẬP (is), không theo giá trị: hai tập khác nghĩa có thể trùng
    # thành phần — PERFORMER_ROLES từ 17/09 trùng khít CLINICAL_READ_ROLES, và so
    # bằng `in` đã nới nhầm quyền đọc bệnh án.
    if mo_quyen_tam_thoi() and any(roles is t for t in _TAP_NOI_DUOC):
        if identity.co_vai(VAI_LAM_VIEC):
            return
    if not identity.co_vai(roles):
        raise SafetyGateError(cau)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _num(value: Decimal | int | None) -> float | int | None:
    if value is None:
        return None
    return float(value) if isinstance(value, Decimal) else value


def _cung_ngay_vn(value: datetime) -> bool:
    """Mốc giờ này có thuộc HÔM NAY giờ Việt Nam không."""
    from clinicai.core.clock import now_vn

    return bool(value.astimezone(now_vn().tzinfo).date() == now_vn().date())


def _theo_luat_xep_hang(rows: list[Any]) -> list[Any]:
    """Hàng chờ theo phòng xếp bằng ĐÚNG MỘT luật: ``rules.order_queue``.

    S0-1 (18/09/2026): ``hang_cho`` từng tự viết ORDER BY riêng có chèn
    ``p.uu_tien DESC`` — khách VIP tự nhảy lên đầu, trái luật 15/09 "ưu tiên chỉ
    là nhãn, không tự đổi thứ tự" (COMMENT cột ``patient.uu_tien``). Bảng điều
    phối đã dùng ``order_queue``; nay hàng chờ theo phòng dùng chung, để không
    còn hai bản của một luật. Người đã xong (không thuộc hàng sống) đứng cuối,
    giữ thứ tự SQL như trước.
    """
    views = [
        rules.QueueView(r["id"], r["status"], r["eligible_at"], r["created_at"])
        for r in rows
    ]
    hang = {e.id: i for i, e in enumerate(rules.order_queue(views))}
    return sorted(
        rows,
        key=lambda r: (0, hang[r["id"]]) if r["id"] in hang else (1, 0),
    )
