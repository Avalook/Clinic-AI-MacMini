"""Appointment booking and lifecycle (W5, ADR-0012).

Ported from ``src/dashboard/app/api/appointments/route.ts``, the largest and
most rule-dense route in the dashboard. Two entry points:

* ``create`` — book an appointment.
* ``apply_action`` — the ten-action lifecycle state machine.

WHERE THE REAL GUARANTEES LIVE. Two invariants are enforced by Postgres, not
here: ``uq_appointment_patient_slot_live`` (một bệnh nhân chỉ có một lịch còn
sống ở mỗi mốc giờ, 20260805000007) and the atomic slot-capacity trigger
(20260714000002, per-clinic since 20260803000001, gắn lại ở 20260803000010).

KHÔNG có ``appointment_no_doctor_overlap``. Docstring này từng khai nó là một
trong hai lưới; nó bị DROP ở migration cũ 057 và chưa ai dựng lại — kiểm
``pg_constraint`` ngày 05/08 chỉ còn hai EXCLUDE, cả hai trên bảng override.
Nó cũng không nên được dựng lại: EXCLUDE cấm mọi cặp chồng lấn, tức trần bằng
1, trong khi phòng khám cho 2 chỗ đặt + 1 vãng lai mỗi bác sĩ mỗi khung. Trần
theo SỐ ĐẾM là việc của trigger sức chứa, và trigger đó chặt hơn hằng số
``DOCTOR_OVERLAP_CAP`` bên dưới. The checks in this module
run *before* the write purely to produce a sentence a receptionist can act on —
"khung 09:15–09:30 đã đủ 2 chỗ" rather than a constraint name. They are
best-effort and fail open, because the database is the actual net; that is why
the SQLSTATE handlers below matter more than the pre-checks do.

THE SEAT RULE, in the clinic's words: each doctor × slot has a few seats — some
for booked patients, the rest reserved for walk-ins. A row with no doctor
assigned is its own queue with the same limits.

The slot length and the two counts are that clinic's, not the product's: they
come from ``clinic.settings`` via ``clinic_policy.py`` (C.3). Dr4Women reads
15 minutes / 2 + 1, which is where the "2+1" in older comments came from. The
trigger reads the same row, so a clinic that changes its numbers changes both
the sentence below and the guarantee behind it in one UPDATE, with no deploy.

Check-in is the one transition that is not an optimistic update. Allocating the
daily queue number and moving the status have to be one serialized transaction,
so it goes through the ``check_in_appointment`` function — the same advisory
lock the walk-in path uses. Two receptionists checking in at once must not hand
out the same number.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import (
    DOCTOR_DESK_ROLES,
    ClinicRole,
    StaffIdentity,
    dung_vai,
)
from clinicai.core.clock import CLINIC_TZ as _CLINIC_TZ
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.shifts import (
    ca_cua_phut,
    ca_tu_settings,
    covers,
    describe,
    merge_windows,
    shift_windows,
)
from clinicai.core.trang_thai_lich import DEAD_STATUSES as DEAD_STATUSES
from clinicai.events.catalogue import (
    CskhDaGoiXacNhan,
    KhachDaToi,
    KhachKhongDen,
    LichDaDat,
    LichDaDoi,
    LichDaDoiDichVu,
    LichDaHuy,
)
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import doi_quyen
from clinicai.permissions.doc_bang import doi_mot_quyen
from clinicai.services.audit import record_event
from clinicai.services.bac_si_phu_trach import la_bac_si_khac
from clinicai.services.clinic_policy import ClinicPolicy, load_effective_policy
from clinicai.services.doi_dich_vu_kham import (
    CAU_BAC_SI_NGHI,
    QUYEN_DOI_DICH_VU_KHAM,
    QUYEN_DOI_TRONG_HO_SO,
    doc_trang_thai,
)
from clinicai.services.hoan_tac_check_in import chan_hoan_tac_neu_da_lam
from clinicai.services.lenh_kham_core import ma_uuid
from clinicai.services.lich_truc_co_so import ca_thuoc_co_so
from clinicai.services.lich_truc_phien_ban_service import giao_dich_lich_truc
from clinicai.services.slot_hold_service import release_on_booking

logger = structlog.get_logger()


# ── LÝ DO HUỶ LỊCH ─────────────────────────────────────────────────────────
#
# Ba mã đầu là BA THỜI ĐIỂM trong vòng đời lịch hẹn, không phải ba cách nói của
# "khách bận" — và mỗi thời điểm tốn của phòng khám một khoản khác nhau: báo lúc
# gọi xác nhận thì chỗ đó bán lại được, báo vào đúng giờ khám thì bác sĩ ngồi
# không. Đếm được ba con số ấy mới biết nên siết khâu nào.
#
# CHỮ Ở ĐÂY PHẢI KHỚP `src/dashboard/lib/ly-do-huy.ts`. Ba màn cùng vẽ danh sách
# này (Quản lý khách hàng, Công việc của tôi, và API tác nhân), nên chép tay là
# sớm muộn ba màn nói ba kiểu về cùng một lần huỷ. Bài kiểm chống lệch:
# src/tests/unit/test_ly_do_huy_drift.py
LY_DO_HUY: dict[str, str] = {
    "BAO_KHI_XAC_NHAN": "Gọi xác nhận trước 7 ngày — khách báo không đến được",
    "BAO_KHI_NHAC_HEN": "Đã xác nhận sẽ đến, tới lúc nhắc hẹn thì báo không đến",
    "BAO_VAO_GIO_KHAM": "Đúng giờ khám, lễ tân gọi khách mới báo không đến",
    # KHÔNG phải một thời điểm như ba mã trên — đây là DỌN DẸP, và tách riêng vì
    # gộp nó vào ba mã kia sẽ bơm phồng con số "khách báo không đến". Khách
    # không huỷ gì cả; phòng khám tự đặt trùng rồi tự bỏ bớt.
    "DAT_TRUNG": "Đặt trùng — khách có nhiều lịch, bỏ bớt giữ lại một",
    # Phòng khám chủ động huỷ vì ca trực của bác sĩ bị xoá/đổi — khách không
    # làm gì cả. remove() của RosterService ghi mã này bằng máy; người cũng
    # chọn được khi huỷ tay vì đúng lý do ấy. Tách riêng vì đếm chung với
    # BAO_* là đổ lỗi cho khách một chuyện của phòng khám.
    "BAC_SI_DOI_LICH": "Bác sĩ đổi lịch làm việc — phòng khám huỷ để đặt lại",
    "KHAC": "Lý do khác (tự viết)",
}

# Múi giờ khai báo ở core.clock — xem lý do ở đó (một hằng số ở nhiều bản
# sao là hằng số sẽ sai ở một trong các bản).
CLINIC_TZ = _CLINIC_TZ

# The slot length and the two seat counts are NOT here: they are the clinic's
# configuration, read per booking from clinic.settings (C.3, clinic_policy.py).
#
# TRẦN NÀY KHÔNG PHẢI LƯỚI, VÀ THỰC TẾ KHÔNG BAO GIỜ CHẠM TỚI.
#
# Chú thích cũ viết nó "phản chiếu `appointment_no_doctor_overlap`, một ràng
# buộc DB" — ràng buộc đó không tồn tại (xem docstring đầu file). Thứ thật sự
# chặn là trigger sức chứa: tối đa `regular_cap` + `walkin_cap` mỗi bác sĩ mỗi
# khung, mặc định 2+1. Sáu thì luôn lớn hơn ba, nên câu "đã đạt giới hạn 6 lịch"
# gần như không bao giờ hiện ra — trigger đã từ chối từ lịch thứ tư.
#
# Giữ lại vì nó vẫn là lưới cuối cho lịch DÀI HƠN MỘT KHUNG: trigger gom theo
# mốc bắt đầu, nên một lịch 60 phút lúc 9:00 không chặn được lịch 9:15.
DOCTOR_OVERLAP_CAP = 6

# Statuses that no longer hold a seat: DEAD_STATUSES — một danh sách duy nhất ở
# core/trang_thai_lich.py (29/09/2026), import ở trên; tên giữ cho nơi đang dùng.

Action = Literal[
    "complete",
    "checkin",
    "undo_checkin",
    "cskh_confirm",
    "cancel",
    "no_show",
    "reassign",
    "assign_doctor",
    "reschedule",
]

# Who may issue which action. Mirrors roles.ts: isDoctorRole / canManageAppt /
# canCheckin / canWriteIntake.
#
# DOCTOR_ROLES used to be re-declared here with its own membership list, one
# character away from identity.py's set of the same name and differing by TKYK.
# Two constants with one name is how a permission drifts without a failing test,
# so this now imports the one that identity.py publishes. Appointment actions are
# desk work — the secretary confirms and completes on the doctor's behalf — which
# is DOCTOR_DESK_ROLES, not the narrower PHYSICIAN_ROLES that gates lab orders.
DOCTOR_ROLES: frozenset[ClinicRole] = DOCTOR_DESK_ROLES
MANAGE_ROLES: frozenset[ClinicRole] = frozenset(
    # Lễ tân đổi / huỷ lịch ở màn Quản lý khách hàng (24/09/2026).
    {ClinicRole.CSKH, ClinicRole.MANAGEMENT, ClinicRole.TRUONG_CA, ClinicRole.RECEPTION}
)
#: owner_only chỉ so staff_id với người CÓ ca của mình — tức bác sĩ thật. Từ
#: 30/09/2026 đọc TÀI KHOẢN (`bac_si_phu_trach.VAI_BAC_SI`), không đọc `co_vai`;
#: tập này giữ làm tài liệu cho bài kiểm.
PHYSICIAN_ONLY_OWNER_CHECK: frozenset[ClinicRole] = frozenset(
    {ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR}
)
CHECKIN_ROLES: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.RECEPTION,
        ClinicRole.MANAGEMENT,
        # CSKH KHÔNG check-in (Tuyền chốt 15/09/2026: "đó là việc của lễ tân").
        # Thay quyết định 08/08 của giai đoạn MVP vận hành tay, khi CSKH thao
        # tác được hết. Check-in là lúc xác minh khách đứng trước quầy — người
        # ngồi gọi điện không nhìn thấy khách.
    }
)
INTAKE_ROLES: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.CSKH,
        ClinicRole.RECEPTION,
        ClinicRole.MANAGEMENT,
        ClinicRole.TRUONG_CA,
    }
)

# "keep" means the action changes fields but not the status (reschedule).
KEEP_STATUS = "__keep__"


#: Cách xác minh đúng người bệnh khi check-in (Tuyền chốt 15/09/2026). Khớp
#: CHECK `visit_xac_minh_cach_hop_le` (20260915000009) và `lib/xac-minh.ts`.
CACH_XAC_MINH: dict[str, str] = {
    "THONG_TIN_CA_NHAN": "Đối chiếu thông tin cá nhân",
    "GIAY_TO_CO_ANH": "Kiểm giấy tờ có ảnh",
    "NGUOI_NHA_XAC_NHAN": "Người nhà xác nhận",
}


def cach_xac_minh_bat_buoc(cach: str | None) -> str | None:
    """Cách xác minh khi check-in — TUỲ CHỌN (Tuyền chốt lại 15/09/2026 tối).

    Sáng 15/09 luật này bắt lễ tân chọn một trong ba cách mỗi lần check-in.
    Tuyền đảo lại: "lễ tân tự xác nhận mà, có số điện thoại và nhìn mặt là biết,
    có sẵn log rồi" — ai check-in, lúc nào đã nằm ở `visit.checked_in_by` và
    event_log. Không gửi thì không ghi gì (KHÔNG điền sẵn một cách — vẫn không
    tạo bằng chứng giả); gửi mã lạ thì vẫn từ chối.
    """
    ma = (cach or "").strip().upper()
    if not ma:
        return None
    if ma not in CACH_XAC_MINH:
        raise ValidationError(f"Cách xác minh không hợp lệ: {cach!r}.")
    return ma


def initial_status(auto_checkin: bool) -> str:
    """Lịch hẹn vừa đặt ở trạng thái nào. ĐẶT XONG LÀ XONG.

    Quyết định của Quang (2026-08-04): bỏ vòng gọi-xác-nhận. Lý do của anh:
    *"nó vốn phải là cái đã được gọi tới CSKH hoặc nhắn tin rồi mới đặt mà"*.
    Cuộc gọi ấy CHÍNH LÀ thứ sinh ra lịch hẹn này; gọi lại lần nữa để xác nhận
    cái vừa thoả thuận là bắt nhân viên làm hai lần một việc — và tệ hơn, nó
    dán nhãn "chưa chắc" lên một lịch hẹn vốn đã chắc.

    Muốn đổi/huỷ thì vào Quản lý khách hàng → lịch hẹn sắp tới → đổi hoặc huỷ
    kèm lý do; mỗi việc đó là một chuyển tiếp riêng và sinh event riêng.

    Hàm thuần, tách khỏi create() vì create() cần mười thứ khác mới chạy được —
    và luật này thì phải kiểm được mà không cần dựng cả phòng khám.
    """
    return "CHECKED_IN" if auto_checkin else "CONFIRMED"


@dataclass(frozen=True)
class Transition:
    """What an action does, and what it may be done from."""

    to_status: str
    from_statuses: frozenset[str]
    allowed_roles: frozenset[ClinicRole]
    event_type: str
    # confirm/decline/complete are the doctor's own calls on their own list.
    owner_only: bool = False
    # Có mã quyền thì QUYỀN quyết (hỏi `capability_grant` trong chính giao dịch),
    # `allowed_roles` chỉ còn để ghi nhật ký đúng vai. CORE-B3 23/09/2026:
    # check-in là bước đầu của đường khám chính.
    quyen: str | None = None


@dataclass(frozen=True)
class _KetQuaHanhDong:
    """Kết quả một hành động trong giao dịch — đủ cho các việc SAU commit."""

    new_status: str
    visit_id: str | None
    doctor_cu: str | None
    doctor_moi: str | None


_ALIVE = frozenset({"SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN"})
_PRE_ARRIVAL = frozenset({"SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"})
# SCHEDULED và CSKH_CONFIRMED là TRẠNG THÁI CŨ, không phải trạng thái chết.
# Lịch hẹn mới vào thẳng CONFIRMED (xem create()), nhưng prod còn 23 dòng
# SCHEDULED + 2 dòng CSKH_CONFIRMED đặt từ trước, và chúng vẫn phải khám được,
# đổi được, huỷ được. Xoá khỏi các tập này là làm 25 lịch hẹn thật kẹt cứng.

# Actions that take the visit off the board again. undo_checkin and cancel mean
# the arrival did not stand, so the still-open steps of that visit are cancelled
# and stop appearing in worklists. no_show is deliberately absent: a patient who
# never arrived never had a visit opened, so there is nothing to cancel.
_WORKFLOW_CANCELLING: frozenset[str] = frozenset({"undo_checkin", "cancel"})


def _chan_dat_vao_qua_khu(slot_end: datetime) -> None:
    """Không đặt được lịch vào khung giờ ĐÃ QUA.

    Trước đây KHÔNG có chốt nào — không ở backend, không ở trình duyệt. Đã đo
    ngày 06/08: lúc 16:40 vẫn đặt được một lịch cho 16:20 và server trả 201.
    Lịch ấy rơi vào lưới hôm nay như một cái hẹn bình thường, và bảng gọi số thì
    đưa người đó vào làn "đến muộn" — một người chưa bao giờ đến.

    ĐO BẰNG `slot_end`, KHÔNG PHẢI `slot_start`. Khung 18:00–18:15 lúc 18:05 thì
    CHƯA qua: khách vãng lai bước vào giữa khung phải xếp được vào chính khung
    đang chạy, và lịch của họ được tạo với `slot_start = bây giờ`. Chặn theo
    `slot_start` sẽ chặn luôn đường đó mỗi khi đồng hồ máy chủ nhanh hơn vài
    giây.

    So bằng giờ có múi (`datetime.now(timezone.utc)`): `slot_end` là timestamptz,
    và một mốc giờ trần ở đây sẽ được hiểu theo múi giờ của tiến trình — đúng ở
    máy này, lệch bảy tiếng ở máy khác.
    """
    if slot_end <= datetime.now(timezone.utc):
        raise ValidationError("Khung giờ này đã qua — chọn một khung còn ở phía trước.")


#: "Ngay bây giờ" (đổi lịch nhanh) = khung bắt đầu cách đồng hồ máy chủ không quá
#: bấy nhiêu phút. Đủ rộng cho popover mở vài phút rồi mới bấm; đủ hẹp để không
#: thành đường vòng đặt lịch ngoài ca cho một giờ khác trong ngày.
KHUNG_BAY_GIO_PHUT = 15
#: Lý do đổi lịch nhanh: bắt buộc, tối đa bấy nhiêu ký tự.
LY_DO_DOI_TOI_DA = 300


def la_khung_bay_gio(slot_start: datetime, bay_gio: datetime) -> bool:
    """Khung này có phải "ngay bây giờ" không (khách đang đứng ở quầy)."""
    return abs((slot_start - bay_gio).total_seconds()) <= KHUNG_BAY_GIO_PHUT * 60


TRANSITIONS: dict[str, Transition] = {
    # BÁC SĨ KHÔNG NHẬN / TỪ CHỐI LỊCH (Tuyền chốt 15/09/2026): quản lý xếp lịch
    # trực là bác sĩ phải làm; nghỉ đột xuất thì hệ thống báo CSKH/lễ tân/trưởng
    # ca xử lý. Hai chuyển tiếp "confirm"/"decline" của bác sĩ đã bỏ. Trạng thái
    # DOCTOR_DECLINED còn trong dữ liệu cũ và `reassign` vẫn dọn được chúng.
    # Finished only from CHECKED_IN: a patient who never arrived cannot have
    # been examined, whatever the doctor pressed.
    "complete": Transition(
        "COMPLETED",
        frozenset({"CHECKED_IN"}),
        # DOCTOR_ROLES + nhóm vận hành (Quang 08/08/2026): trong MVP vận hành
        # tay, CSKH bấm "khách check-out" và lượt khám phải ĐÓNG THẬT — không
        # đóng thì "đã khám" không bao giờ bật và nhắc tái khám không bao giờ
        # sinh. MANAGE_ROLES chứ không riêng CSKH: quản lý và trưởng ca làm
        # được mọi việc CSKH làm được — bản đầu chỉ mở CSKH và người đầu tiên
        # ăn 403 chính là tài khoản Quản lý đang chạy thử.
        # Bác sĩ vẫn giữ luật cũ: chỉ đóng được ca của chính mình.
        DOCTOR_ROLES | MANAGE_ROLES,
        "appointment.completed",
        True,
    ),
    # D21: reception checks in directly from any live appointment. The doctor's
    # accept/decline is no longer a precondition for the patient being seen.
    "checkin": Transition(
        "CHECKED_IN",
        _PRE_ARRIVAL,
        CHECKIN_ROLES,
        "appointment.checked_in",
        quyen="reception.checkin.perform",
    ),
    "undo_checkin": Transition(
        "CONFIRMED",
        frozenset({"CHECKED_IN"}),
        CHECKIN_ROLES,
        "appointment.checkin_undone",
        quyen="reception.checkin.perform",
    ),
    # BƯỚC CŨ, GIỮ LẠI CHỈ ĐỂ DỌN LỊCH CŨ.
    #
    # Quang bỏ vòng gọi-xác-nhận: lịch mới đặt xong là chắc luôn, nên không có
    # gì để xác nhận nữa. Nhưng prod còn 23 lịch SCHEDULED đặt từ trước, và
    # người đang cầm chúng vẫn cần đường đi tiếp — nên chuyển tiếp này chỉ còn
    # nhận SCHEDULED, và sẽ tự hết việc khi đám cũ khám xong.
    "cskh_confirm": Transition(
        "CSKH_CONFIRMED",
        frozenset({"SCHEDULED"}),
        INTAKE_ROLES,
        "appointment.cskh_confirmed",
        quyen="booking.create",
    ),
    # Huỷ / đổi bác sĩ / gán bác sĩ / dời lịch hỏi QUYỀN "Quản lý lịch hẹn"
    # (24/09/2026, migration 20260924000013 — cùng người với MANAGE_ROLES cũ).
    "cancel": Transition(
        "CANCELLED",
        _ALIVE,
        MANAGE_ROLES,
        "appointment.cancelled",
        quyen="booking.manage",
    ),
    "no_show": Transition(
        "NO_SHOW",
        _PRE_ARRIVAL,
        CHECKIN_ROLES,
        "appointment.no_show",
        quyen="reception.checkin.perform",
    ),
    # Bác sĩ từ chối thì lịch quay lại hàng chờ — và quay lại ở trạng thái CHẮC,
    # vì thoả thuận với bệnh nhân không mất đi khi một bác sĩ bận. Đổi bác sĩ là
    # việc nội bộ, không phải lý do gọi lại bệnh nhân để xác nhận lần nữa.
    "reassign": Transition(
        "CONFIRMED",
        frozenset({"DOCTOR_DECLINED"}),
        MANAGE_ROLES,
        "appointment.reassigned",
        quyen="booking.manage",
    ),
    # GÁN BÁC SĨ cho một lịch đã đặt mà chưa có bác sĩ.
    #
    # Việc này chưa từng có đường đi. `reassign` chỉ nhận lịch bị bác sĩ TỪ CHỐI,
    # và `reschedule` là đường duy nhất ghi được doctor_id nhưng bắt buộc phải
    # kèm giờ hẹn mới — nên muốn xếp bác sĩ cho một lịch chờ thì phải giả vờ đổi
    # giờ, tức là dời lịch của bệnh nhân để làm một việc nội bộ.
    #
    # GIỮ NGUYÊN TRẠNG THÁI: thoả thuận với bệnh nhân không đổi khi phòng khám
    # xếp được người. Không có lý do gì gọi lại họ để xác nhận lần nữa.
    "assign_doctor": Transition(
        KEEP_STATUS,
        _ALIVE,
        MANAGE_ROLES,
        "appointment.doctor_assigned",
        quyen="booking.manage",
    ),
    # Rescheduling keeps whatever status the appointment already had.
    "reschedule": Transition(
        KEEP_STATUS,
        _ALIVE,
        MANAGE_ROLES,
        "appointment.rescheduled",
        quyen="booking.manage",
    ),
}


def resolve_action(action: str) -> Transition:
    """The transition for an action. Pure, so the state machine is testable."""
    try:
        return TRANSITIONS[action]
    except KeyError:
        raise ValidationError(f"Hành động không hợp lệ: {action!r}") from None


def is_walkin(channel: str | None) -> bool:
    return (channel or "").strip().upper() == "WALK_IN"


def is_dead(status: str | None) -> bool:
    return (status or "").strip() in DEAD_STATUSES


# suggest_load() ĐÃ BỊ GỠ (20260803000005).
#
# Nó trả về một bảng phút viết cứng — khách mới 15', tái khám 5', siêu âm +12'/+8'
# — và bốn con số đó không đến từ phép đo nào. Chúng được gõ vào một lần rồi trở
# thành "sự thật": ô lịch tô màu theo chúng, cảnh báo "khung sắp đầy" tính theo
# chúng, và không ai từng kiểm xem một khách mới lúc 18:00 thứ Ba có thật sự mất
# 15 phút hay không.
#
# Hai việc vốn khác nhau, giờ tách hẳn:
#
#   GIỚI HẠN đặt lịch  = SỐ CHỖ mỗi khung. Trưởng ca / Quản lý đặt, sửa được
#                        trên giao diện, thi hành bởi trigger trong database.
#   THỜI LƯỢNG khám    = ĐO từ work_item.started_at → finished_at. Xem view
#                        v_consultation_duration / _stats.
#
# thanh_min/sono_min từ đây chỉ nhận giá trị người dùng NHẬP TAY, và NULL khi
# không ai ước lượng — chứ không phải một con số hệ thống tự bịa rồi tự tin.


def _hhmm(moment: datetime) -> str:
    return moment.astimezone(CLINIC_TZ).strftime("%H:%M")


class BookingService:
    """Book appointments and drive their lifecycle."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ---------------------------------------------------------------- create

    async def create(
        self,
        *,
        clinic_patient_id: str,
        service_type_id: str,
        location_id: str | None,
        slot_start: datetime,
        slot_end: datetime,
        identity: StaffIdentity,
        doctor_id: str | None = None,
        booking_channel: str | None = None,
        queue_number: str | None = None,
        patient_kind: str | None = None,
        need_sono: bool | None = None,
        thanh_min: int | None = None,
        sono_min: int | None = None,
        notes: str | None = None,
        lich_truoc_id: str | None = None,
        xac_minh_cach: str | None = None,
        nguoi_gioi_thieu: str | None = None,
        hen_tu_visit_id: str | None = None,
    ) -> dict[str, Any]:
        """Book one appointment. Returns its id and the status it landed in.

        `hen_tu_visit_id` = lượt khám mà bác sĩ đặt lịch tái khám này từ phiếu
        (`lich_tai_kham_service`, 02/10/2026). Màn Đặt lịch không truyền.

        `xac_minh_cach` TUỲ CHỌN khi lịch là VÃNG LAI TRONG NGÀY (đường này tự
        check-in) — gửi thì ghi như nút check-in, không gửi thì không ghi gì.

        `lich_truoc_id` = lịch hẹn mà lịch này là TÁI KHÁM của nó. Chỉ nút "Tái
        khám" ở màn Quản lý khách hàng truyền; nút "Đặt lịch khám mới" cố ý để
        None. Xem migration 20260810000007 để biết vì sao phải là một cột thật
        chứ không suy ra được từ `episode_id` hay `patient_kind`.
        """
        # Không nói cơ sở thì lấy cơ sở CỦA NGƯỜI ĐẶT, không phải cơ sở đầu tiên
        # trong một danh sách. _validate_booking_refs vẫn kiểm nó thuộc đúng
        # phòng khám, nên chỉ định cơ sở khác vẫn được — chỉ là phải cố ý.
        location_id = location_id or identity.location_id
        if slot_end <= slot_start:
            raise ValidationError("Giờ kết thúc phải sau giờ bắt đầu")
        _chan_dat_vao_qua_khu(slot_end)

        # LỊCH TRƯỚC PHẢI LÀ CỦA CHÍNH KHÁCH NÀY, và của chính phòng khám này.
        #
        # Khoá ngoại chỉ bảo đảm cái id ấy TỒN TẠI — nó không cấm trỏ sang lịch
        # của người khác. Một mã đoán được là một chuỗi lịch sử khám bị nối vào
        # nhầm bệnh nhân, và nó sẽ hiện ra ở ô "lịch sử các lần khám" như thể là
        # sự thật. Kiểm ở đây chứ không ở màn hình: màn hình nào cũng có thể
        # quên, còn đường ghi thì chỉ có một.
        if lich_truoc_id is not None:
            lich_truoc_id = (lich_truoc_id or "").strip() or None
        if lich_truoc_id is not None:
            hop_le = await self._pool.fetchval(
                """
                SELECT 1 FROM public.appointment
                 WHERE id = $1::uuid
                   AND clinic_id = $2::uuid
                   AND clinic_patient_id = $3::uuid
                """,
                lich_truoc_id,
                identity.clinic_id,
                clinic_patient_id,
            )
            if not hop_le:
                raise ValidationError(
                    "Lịch trước không phải lịch hẹn của khách hàng này."
                )

        raw_channel = (booking_channel or "").strip()
        # NO INVENTED DEFAULT, and the old one was the wrong way round.
        #
        # This used to be `raw_channel or "WALK_IN"`. BookingHub — the screen
        # CSKH books almost everything from — sends no channel at all, so every
        # appointment it created was stored as a walk-in. Walk-ins draw from the
        # small reserved pool (walkin_cap, 1 seat), so the grid filled that pool
        # and left the booked pool (regular_cap, 2 seats) permanently empty: the
        # seat rule ran inverted on the busiest screen in the clinic, and the
        # patient who actually walked in found no seat left for them.
        #
        # An unstated channel means "a member of staff entered this booking",
        # which is a booked seat. NULL says exactly that and nothing more; both
        # capacity triggers already treat anything that is not the literal
        # 'WALK_IN' as regular, so the pre-check and the net now agree.
        channel = raw_channel or None
        kind = (patient_kind or "").strip().upper() or None
        if kind not in (None, "NEW", "RETURN"):
            kind = None

        # Người nhập gì thì lưu nấy; không nhập thì NULL. Không suy diễn.
        thanh = thanh_min
        sono = sono_min

        # A walk-in booked for today is already standing at the desk, so it is
        # checked in on creation. Only when WALK_IN was chosen explicitly and
        # the slot is today — otherwise a future booking, or one phoned in
        # without a channel, would be checked in for a patient who is not here.
        auto_checkin = raw_channel.upper() == "WALK_IN" and self._is_today(slot_start)
        status = initial_status(auto_checkin)
        cach_xac_minh = cach_xac_minh_bat_buoc(xac_minh_cach) if auto_checkin else None

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await self._validate_booking_refs(
                    conn,
                    clinic_patient_id=clinic_patient_id,
                    location_id=location_id,
                    service_type_id=service_type_id,
                    doctor_id=doctor_id,
                    identity=identity,
                )
                await self._chan_dat_ngoai_khung_ca(
                    conn, slot_start=slot_start, identity=identity
                )
                if auto_checkin:
                    # Khách trực tiếp đặt xong là check-in luôn — việc của lễ
                    # tân tại quầy (Tuyền chốt 15/09/2026), nên cần đúng quyền
                    # check-in. CSKH đặt trước cho ngày khác thì không cần.
                    await doi_quyen(
                        conn,
                        identity,
                        "reception.checkin.perform",
                        cau="Khách trực tiếp do lễ tân đặt và check-in tại quầy.",
                    )

                warnings: list[str] = []

                # MỘT NGƯỜI KHÔNG NGỒI HAI CHỖ CÙNG LÚC.
                #
                # Tìm thấy trên prod ngày 04/08: một bệnh nhân có BA lịch hẹn
                # cùng khung 17:15, tạo cách nhau 10 và 5 giây — tức là bấm
                # "Đặt lịch hẹn" ba lần. Khung đó sức chứa 3, nên một người đã
                # chiếm trọn khung, và không luật nào trong hệ chặn lại: bảng
                # appointment không có ràng buộc duy nhất nào.
                #
                # Chuyện này nặng hơn kể từ khi bỏ bước xác nhận: trước đây lịch
                # thừa còn nằm ở "chờ xác nhận" nên có người rà; giờ nó chắc
                # ngay.
                dup = await self._patient_double_booked(
                    conn,
                    clinic_patient_id=clinic_patient_id,
                    slot_start=slot_start,
                    identity=identity,
                )
                if dup:
                    raise ConflictError(dup)

                if doctor_id:
                    busy = await self._doctor_conflict(
                        conn, doctor_id, slot_start, slot_end, identity
                    )
                    if busy:
                        raise ConflictError(busy)

                    off_duty = await self._roster_warning(
                        conn, doctor_id, slot_start, identity, location_id=location_id
                    )
                    if off_duty:
                        if await self._roster_is_required(conn, identity):
                            raise ConflictError(off_duty)
                        warnings.append(off_duty)

                # LUẬT BẮT BUỘC BÁC SĨ — thi hành ở ĐÂY, lúc CSKH còn đang
                # nói chuyện với khách. Luật cũ (visit_gate_rule) chỉ chạy lúc
                # chuyển phòng, tức sau khi khách đã đi tới nơi; lúc đó có phát
                # hiện sai thì cũng không sửa được nữa.
                loi_bs = await self._luat_bac_si_bat_buoc(
                    conn,
                    clinic_patient_id=clinic_patient_id,
                    service_type_id=service_type_id,
                    doctor_id=doctor_id,
                    identity=identity,
                )
                if loi_bs:
                    cau, chan = loi_bs
                    if chan:
                        raise ConflictError(cau)
                    warnings.append(cau)

                policy = await load_effective_policy(
                    conn, identity.clinic_id, doctor_id, slot_start
                )
                full = await self._slot_full(
                    conn, doctor_id, slot_start, channel, identity, policy
                )
                if full:
                    raise ConflictError(full)

                try:
                    appointment_id = await conn.fetchval(
                        """
                        INSERT INTO appointment (
                            clinic_id, clinic_patient_id, doctor_id, service_type_id,
                            location_id, slot_start, slot_end, booking_channel,
                            queue_number, status, patient_kind, thanh_min, sono_min,
                            need_sono, is_walkin, notes, lich_truoc_id,
                            hen_tu_visit_id
                        )
                        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid,
                                $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16,
                                $17::uuid, $18::uuid)
                        RETURNING id
                        """,
                        identity.clinic_id,
                        clinic_patient_id,
                        doctor_id,
                        service_type_id,
                        location_id,
                        slot_start,
                        slot_end,
                        channel,
                        # SỐ KHÁM DO DATABASE CẤP (assign_appointment_queue_number
                        # khi CHECKED_IN), KHÔNG nhận từ trình duyệt (15/09/2026):
                        # màn vãng lai từng tự tính max+1 ở client, hai quầy
                        # bấm cùng lúc là trùng số. Tham số giữ cho tương thích.
                        None,
                        status,
                        kind,
                        thanh,
                        sono,
                        need_sono,
                        # is_walkin mirrors booking_channel; the CHECK added in
                        # 20260803000004 rejects the write if they disagree.
                        is_walkin(channel),
                        (notes or "").strip() or None,
                        lich_truoc_id,
                        hen_tu_visit_id,
                    )
                except asyncpg.ExclusionViolationError as exc:
                    raise ConflictError(
                        "Bác sĩ đã có lịch trùng khung giờ này."
                    ) from exc
                except asyncpg.CheckViolationError as exc:
                    # The atomic capacity trigger lost the race to us and won.
                    if "Khung giờ đã đầy" in str(exc):
                        raise ConflictError(str(exc)) from exc
                    raise

                # Đặt xong thì thả chỗ giữ, TRONG CÙNG transaction này. Để
                # dòng giữ chỗ sống tiếp sau khi đã thành lịch hẹn là đếm cùng
                # một ghế hai lần trên màn hình CSKH bên cạnh.
                await release_on_booking(
                    conn,
                    identity=identity,
                    appointment_id=str(appointment_id),
                    slot_start=slot_start,
                )

                # NGƯỜI GIỚI THIỆU → HỒ SƠ khách (Tuyền 24/09/2026), cùng giao
                # dịch với lịch hẹn. Để trống thì giữ tên đã có, không xoá.
                gioi_thieu = " ".join((nguoi_gioi_thieu or "").split())[:200]
                if gioi_thieu:
                    await conn.execute(
                        "UPDATE patient SET nguoi_gioi_thieu = $3, updated_at = now()"
                        " WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid",
                        identity.clinic_id,
                        clinic_patient_id,
                        gioi_thieu,
                    )

                await self._attach_episode(
                    conn,
                    appointment_id=appointment_id,
                    clinic_patient_id=clinic_patient_id,
                    service_type_id=service_type_id,
                    patient_kind=kind,
                    identity=identity,
                )

                await _log(
                    conn,
                    event_type="appointment.created",
                    aggregate_id=str(appointment_id),
                    payload={
                        "appointment_id": str(appointment_id),
                        "clinic_patient_id": clinic_patient_id,
                        "doctor_id": doctor_id,
                        "slot_start": slot_start.isoformat(),
                        "booking_channel": channel,
                        "status": status,
                    },
                    identity=identity,
                    origin="api:appointment-booking",
                )
                await emit_event(
                    conn,
                    ten="appointment.booked",
                    clinic_id=identity.clinic_id,
                    aggregate_id=str(appointment_id),
                    payload=LichDaDat(
                        appointment_id=str(appointment_id),
                        bat_dau=slot_start.isoformat(),
                        kenh=channel,
                    ),
                    boi=nguoi(identity),
                )

                if auto_checkin:
                    # Same audit trail as the receptionist's check-in button, and
                    # the visit opens now so the patient shows on the board from
                    # the moment they arrive rather than when someone types.
                    await _log(
                        conn,
                        event_type="appointment.checked_in",
                        aggregate_id=str(appointment_id),
                        payload={
                            "appointment_id": str(appointment_id),
                            "auto_walk_in": True,
                            "status": "CHECKED_IN",
                            "xac_minh_cach": cach_xac_minh,
                        },
                        identity=identity,
                        origin="api:appointment-walkin-autocheckin",
                    )
                    visit_vua_mo = await self._open_visit(
                        conn,
                        appointment_id=appointment_id,
                        clinic_patient_id=clinic_patient_id,
                        doctor_id=doctor_id,
                        identity=identity,
                    )
                    # CÙNG sự kiện mở đầu hành trình như nút check-in của lễ tân.
                    # Thiếu nó (trước 24/09/2026) thì khách vãng lai không được
                    # xếp hàng tư vấn / bác sĩ cho tới khi đo sinh hiệu, và chỉ
                    # định hẹn từ lượt trước không được mang sang (H2) — bộ mô
                    # phỏng ngày khám bắt được.
                    if visit_vua_mo:
                        await emit_event(
                            conn,
                            ten="visit.checked_in",
                            clinic_id=identity.clinic_id,
                            aggregate_id=visit_vua_mo,
                            payload=KhachDaToi(
                                visit_id=visit_vua_mo,
                                appointment_id=str(appointment_id),
                            ),
                            boi=nguoi(identity),
                            correlation_id=visit_vua_mo,
                        )
                    if cach_xac_minh:
                        await self._ghi_xac_minh(
                            conn,
                            appointment_id=str(appointment_id),
                            cach=cach_xac_minh,
                            identity=identity,
                        )

        logger.info(
            "appointment_created",
            appointment_id=str(appointment_id),
            status=status,
            by_staff_id=identity.staff_id,
            warning_count=len(warnings),
        )
        return {
            "appointment_id": str(appointment_id),
            "status": status,
            # Cảnh báo KHÔNG phải lỗi: lịch đã được ghi. Nhưng người đặt phải
            # thấy điều bất thường ngay lúc đặt, không phải lúc bệnh nhân đến.
            "warnings": warnings,
        }

    # ---------------------------------------------------------------- action

    async def apply_action(
        self,
        *,
        appointment_id: str,
        action: Action,
        identity: StaffIdentity,
        cancellation_reason: str | None = None,
        ly_do_huy_ma: str | None = None,
        doctor_id: str | None = None,
        doctor_id_provided: bool = False,
        slot_start: datetime | None = None,
        slot_end: datetime | None = None,
        xac_minh_cach: str | None = None,
        service_type_id: str | None = None,
        booking_channel: str | None = None,
        booking_channel_provided: bool = False,
        nguoi_gioi_thieu: str | None = None,
        ghi_chu: str | None = None,
        ghi_chu_provided: bool = False,
    ) -> dict[str, Any]:
        """Run one lifecycle action. Returns the resulting status.

        `xac_minh_cach` tuỳ chọn với `checkin` (xem `cach_xac_minh_bat_buoc`).
        """
        transition = resolve_action(action)
        cach_xac_minh = (
            cach_xac_minh_bat_buoc(xac_minh_cach) if action == "checkin" else None
        )

        if transition.quyen is None and not identity.co_vai(transition.allowed_roles):
            raise SafetyGateError(
                f"Vai trò của bạn không được phép '{action}' lịch hẹn"
            )
        # Làm dưới vai thực sự cho phép thao tác (vd. vị trí Lễ tân hôm nay của
        # một tài khoản Điều dưỡng) — nhật ký ghi đúng ngữ cảnh.
        identity = dung_vai(identity, transition.allowed_roles)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                kq = await self._hanh_dong_trong_gd(
                    conn,
                    appointment_id=appointment_id,
                    action=action,
                    transition=transition,
                    identity=identity,
                    cach_xac_minh=cach_xac_minh,
                    cancellation_reason=cancellation_reason,
                    ly_do_huy_ma=ly_do_huy_ma,
                    doctor_id=doctor_id,
                    doctor_id_provided=doctor_id_provided,
                    slot_start=slot_start,
                    slot_end=slot_end,
                    service_type_id=service_type_id,
                    booking_channel=booking_channel,
                    booking_channel_provided=booking_channel_provided,
                    nguoi_gioi_thieu=nguoi_gioi_thieu,
                    ghi_chu=ghi_chu,
                    ghi_chu_provided=ghi_chu_provided,
                )
        new_status = kq.new_status
        visit_vua_mo = kq.visit_id
        await self._bao_neu_vua_co_bac_si(kq, appointment_id, identity)

        logger.info(
            "appointment_action",
            appointment_id=appointment_id,
            action=action,
            status=new_status,
            by_staff_id=identity.staff_id,
        )
        # Kèm mã lượt khám khi hành động vừa mở một lượt — màn hình nhờ đó bỏ
        # được một vòng nạp lại cả bảng chỉ để tìm ra lượt của chính người vừa
        # check-in. Các hành động khác không có nó, và đó là chủ ý.
        return (
            {"status": new_status, "visit_id": visit_vua_mo}
            if visit_vua_mo
            else {"status": new_status}
        )

    async def _hanh_dong_trong_gd(
        self,
        conn: asyncpg.Connection,
        *,
        appointment_id: str,
        action: str,
        transition: Transition,
        identity: StaffIdentity,
        cach_xac_minh: str | None = None,
        cancellation_reason: str | None = None,
        ly_do_huy_ma: str | None = None,
        doctor_id: str | None = None,
        doctor_id_provided: bool = False,
        slot_start: datetime | None = None,
        slot_end: datetime | None = None,
        service_type_id: str | None = None,
        booking_channel: str | None = None,
        booking_channel_provided: bool = False,
        nguoi_gioi_thieu: str | None = None,
        ghi_chu: str | None = None,
        ghi_chu_provided: bool = False,
        cho_ngoai_ca: bool = False,
        xoa_so_thu_tu: bool = False,
        quyen_da_kiem: bool = False,
    ) -> _KetQuaHanhDong:
        """Một hành động lịch hẹn TRONG giao dịch của người gọi.

        Tách khỏi `apply_action` (29/09/2026) để lệnh "đổi lịch nhanh" chạy
        đổi lịch rồi check-in trong CÙNG một giao dịch, qua đúng một đường luật.
        `cho_ngoai_ca` / `xoa_so_thu_tu` chỉ lệnh ấy dùng — xem `doi_lich_nhanh`.
        `quyen_da_kiem` = người gọi đã gác bằng luật riêng (bác sĩ huỷ lịch
        CHÍNH MÌNH đặt từ phiếu — `lich_tai_kham_service.huy_lich`).
        """
        visit_vua_mo: str | None = None
        if transition.quyen is not None and not quyen_da_kiem:
            # Đứng vị trí Lễ tân hôm nay KHÔNG tự cấp quyền check-in:
            # người đó phải được cấp quyền (CORE-B3).
            await doi_quyen(conn, identity, transition.quyen)
        appt = await conn.fetchrow(
            """
            SELECT
                a.id, a.doctor_id, a.status, a.clinic_patient_id,
                a.slot_start, a.slot_end, a.queue_number,
                a.booking_channel, a.notes,
                -- Cần cho luật bắt buộc bác sĩ lúc gán người.
                a.service_type_id,
                EXISTS (
                    SELECT 1
                      FROM patient p
                     WHERE p.clinic_patient_id = a.clinic_patient_id
                       AND p.clinic_id = a.clinic_id
                ) AS patient_in_clinic,
                EXISTS (
                    SELECT 1
                      FROM clinic_location l
                     WHERE l.id = a.location_id
                       AND l.clinic_id = a.clinic_id
                ) AS location_in_clinic,
                EXISTS (
                    SELECT 1
                      FROM service_type s
                     WHERE s.id = a.service_type_id
                       AND s.clinic_id = a.clinic_id
                ) AS service_in_clinic,
                (
                    a.doctor_id IS NULL
                    OR EXISTS (
                        SELECT 1
                          FROM staff st
                          JOIN clinic_membership m
                            ON m.staff_id = st.id
                         WHERE st.id = a.doctor_id
                           AND st.is_active
                           AND m.clinic_id = a.clinic_id
                           AND m.is_active
                           AND m.role IN (
                               'DOCTOR', 'ULTRASOUND_DOCTOR'
                           )
                    )
                ) AS doctor_in_clinic
              FROM appointment a
             WHERE a.id = $1::uuid AND a.clinic_id = $2::uuid
            """,
            appointment_id,
            identity.clinic_id,
        )
        if appt is None:
            raise NotFoundError("Không tìm thấy lịch hẹn")
        if not appt["patient_in_clinic"]:
            raise ValidationError("Bệnh nhân của lịch hẹn không thuộc phòng khám này")
        if not appt["location_in_clinic"]:
            raise ValidationError("Cơ sở của lịch hẹn không thuộc phòng khám này")
        if not appt["service_in_clinic"]:
            raise ValidationError("Dịch vụ của lịch hẹn không thuộc phòng khám này")
        repairs_doctor = action in {"cancel", "reassign"} or (
            action == "reschedule" and doctor_id_provided
        )
        if not appt["doctor_in_clinic"] and not repairs_doctor:
            raise ValidationError("Bác sĩ của lịch hẹn không thuộc phòng khám này")

        # "Ca của chính mình" là luật GIỮA CÁC BÁC SĨ — ngăn bác sĩ
        # này đóng ca của bác sĩ kia. Người không phải bác sĩ (TKYK
        # nhập hộ, nhóm vận hành đóng lượt trong MVP tay) không có "ca
        # của mình" để so; so staff_id với họ chỉ chặn sạch mọi thứ —
        # đo được trên bản thật: Quản lý bấm check-out ăn ngay
        # "Lịch hẹn này không thuộc bác sĩ".
        #
        # Mở full lego (30/09/2026): "bác sĩ" = TÀI KHOẢN bác sĩ
        # (`clinic_membership.role`, `bac_si_phu_trach`), KHÔNG phải vai
        # suy từ lego — mọi người đủ lego Bàn khám mang vai DOCTOR, hỏi
        # `co_vai` là lễ tân bấm check-out cũng bị chặn.
        if transition.owner_only and await la_bac_si_khac(
            conn,
            identity.clinic_id,
            identity.staff_id,
            str(appt["doctor_id"]) if appt["doctor_id"] else None,
        ):
            raise SafetyGateError("Lịch hẹn này không thuộc bác sĩ")

        if appt["status"] not in transition.from_statuses:
            raise ConflictError(
                f"Lịch hẹn đang ở trạng thái {appt['status']}, không thể thực hiện."
            )
        if action == "undo_checkin":
            # Đã làm rồi thì không hoàn tác (Tuyền 09/10/2026) — khoá rồi mới hỏi.
            ly_do = await chan_hoan_tac_neu_da_lam(
                conn, clinic_id=identity.clinic_id, appointment_id=appointment_id
            )
            if ly_do:
                raise ConflictError(ly_do)

        new_status = (
            appt["status"]
            if transition.to_status == KEEP_STATUS
            else transition.to_status
        )
        effective_doctor_id = str(appt["doctor_id"]) if appt["doctor_id"] else None

        patch: dict[str, Any] = {}
        if action == "checkin":
            updated = await self._check_in(conn, appointment_id, transition)
        else:
            patch = await self._build_patch(
                conn,
                action=action,
                appt=appt,
                new_status=new_status,
                cancellation_reason=cancellation_reason,
                ly_do_huy_ma=ly_do_huy_ma,
                doctor_id=doctor_id,
                doctor_id_provided=doctor_id_provided,
                slot_start=slot_start,
                slot_end=slot_end,
                identity=identity,
                service_type_id=service_type_id,
                booking_channel=booking_channel,
                booking_channel_provided=booking_channel_provided,
                cho_ngoai_ca=cho_ngoai_ca,
            )
            if xoa_so_thu_tu:
                # Số khám cấp theo NGÀY của slot_start: lịch dời ngày thì số cũ
                # (nếu còn sót từ một lần hoàn tác check-in) không còn nghĩa.
                patch["queue_number"] = None
            ghi_chu_moi = (ghi_chu or "").strip() or None
            if (
                action == "reschedule"
                and ghi_chu_provided
                and ghi_chu_moi != appt["notes"]
            ):
                # Chữ cũ không mất: nhật ký đổi lịch bên dưới mang cả hai bản.
                patch["notes"] = ghi_chu_moi
            updated = await self._update(
                conn,
                appointment_id,
                patch,
                transition.from_statuses,
                identity.clinic_id,
            )
            if "doctor_id" in patch:
                effective_doctor_id = (
                    str(patch["doctor_id"]) if patch["doctor_id"] else None
                )

        if not updated:
            # Somebody moved it between our read and our write.
            raise ConflictError("Lịch hẹn vừa được người khác cập nhật, hãy tải lại.")

        # Đổi lịch kèm người giới thiệu → HỒ SƠ khách (cùng luật với đặt
        # mới: để trống thì giữ tên đã có, không xoá).
        gioi_thieu = " ".join((nguoi_gioi_thieu or "").split())[:200]
        if action == "reschedule" and gioi_thieu:
            await conn.execute(
                "UPDATE patient SET nguoi_gioi_thieu = $3, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid",
                identity.clinic_id,
                str(appt["clinic_patient_id"]),
                gioi_thieu,
            )

        await _log(
            conn,
            event_type=transition.event_type,
            aggregate_id=appointment_id,
            payload={
                "appointment_id": appointment_id,
                "status": new_status,
                "doctor_id": effective_doctor_id,
                "clinic_patient_id": str(appt["clinic_patient_id"]),
                **({"xac_minh_cach": cach_xac_minh} if cach_xac_minh else {}),
                **(
                    {"ghi_chu_cu": appt["notes"], "ghi_chu_moi": patch["notes"]}
                    if "notes" in patch
                    else {}
                ),
            },
            identity=identity,
            origin=f"api:appointment-{action}",
        )
        await _phat_su_kien_lich(
            conn,
            identity=identity,
            action=action,
            appt=appt,
            patch=patch,
            ly_do=cancellation_reason,
            ly_do_huy_ma=ly_do_huy_ma,
        )

        if action == "checkin":
            visit_vua_mo = await self._open_visit(
                conn,
                appointment_id=appointment_id,
                clinic_patient_id=str(appt["clinic_patient_id"]),
                doctor_id=effective_doctor_id,
                identity=identity,
            )
            if visit_vua_mo:
                # Sự kiện nghiệp vụ mở đầu hành trình, CÙNG giao dịch
                # với việc mở lượt. Payload không có tên, tuổi hay số
                # điện thoại — màn nào cần thì hỏi bảng bệnh nhân, nơi
                # có quyền đọc riêng.
                await emit_event(
                    conn,
                    ten="visit.checked_in",
                    clinic_id=identity.clinic_id,
                    aggregate_id=visit_vua_mo,
                    payload=KhachDaToi(
                        visit_id=visit_vua_mo,
                        appointment_id=appointment_id,
                    ),
                    boi=nguoi(identity),
                    correlation_id=visit_vua_mo,
                )
            if cach_xac_minh:
                await self._ghi_xac_minh(
                    conn,
                    appointment_id=appointment_id,
                    cach=cach_xac_minh,
                    identity=identity,
                )
        elif action in _WORKFLOW_CANCELLING:
            await self._cancel_visit_workflow(
                conn,
                appointment_id=appointment_id,
                identity=identity,
                reason=action,
            )

        # LỊCH TRỰC PHẢI THEO KỊP PHÂN CÔNG, không thì hai màn nói
        # ngược nhau: lịch hẹn ghi "BS. X khám", còn Lịch làm việc hôm
        # ấy trống trơn — và `capacity_service` đọc chính lịch trực để
        # trả lời "bác sĩ này có đi làm hôm đó không".
        #
        # TRONG CÙNG GIAO DỊCH với việc gán bác sĩ, cố ý. Đây không
        # phải lớp phủ như thông báo: gán được bác sĩ mà không xếp được
        # ca là để lại đúng cái mâu thuẫn vừa nói. Hỏng thì cuộn lại cả
        # hai và người dùng bấm lại.
        if appt["doctor_id"] is None and effective_doctor_id:
            await self._xep_vao_lich_truc(
                conn,
                appointment_id=appointment_id,
                doctor_id=effective_doctor_id,
                slot_start=appt["slot_start"],
                identity=identity,
            )
        return _KetQuaHanhDong(
            new_status=new_status,
            visit_id=visit_vua_mo,
            doctor_cu=str(appt["doctor_id"]) if appt["doctor_id"] else None,
            doctor_moi=effective_doctor_id,
        )

    async def doi_lich_nhanh(
        self,
        *,
        appointment_id: str,
        identity: StaffIdentity,
        slot_start: datetime,
        slot_end: datetime,
        doctor_id: str,
        ly_do: str,
        check_in: bool,
    ) -> dict[str, Any]:
        """ĐỔI LỊCH TẠI CHỖ (Tuyền chốt 29/09/2026) — đổi lịch rồi check-in luôn.

        MỘT giao dịch, HAI hành động qua đúng đường luật của `apply_action`:
        ``reschedule`` (quyền "Quản lý lịch hẹn", `_build_patch`/`_guard_slot`,
        lịch sử `appointment_doi_lich`, sự kiện `appointment.rescheduled`) rồi —
        nếu ``check_in`` — ``checkin`` (quyền check-in, số khám theo ngày của
        khung MỚI). Hỏng bước nào cuộn cả hai: không có "đã đổi mà chưa vào hàng".

        KHÁCH ĐẾN SỚM NGOÀI GIỜ CA: khung = bây giờ (`la_khung_bay_gio`) + kèm
        check-in → bỏ chốt "ngoài khung ca" và "bác sĩ không có mặt lúc HH:MM"
        (bác sĩ vẫn phải có ca trong ngày), ghi "ngoài ca" vào lý do. Sức chứa
        vẫn giữ. Không kèm check-in, hoặc khung không phải bây giờ → luật cũ.
        """
        ly_do_sach = " ".join((ly_do or "").split())
        if not ly_do_sach:
            raise ValidationError("Chọn lý do đổi lịch.")
        if len(ly_do_sach) > LY_DO_DOI_TOI_DA:
            raise ValidationError(f"Lý do đổi lịch tối đa {LY_DO_DOI_TOI_DA} ký tự.")
        if slot_end <= slot_start:
            raise ValidationError("Giờ kết thúc phải sau giờ bắt đầu")
        bay_gio = datetime.now(timezone.utc)
        if (
            check_in
            and slot_start.astimezone(CLINIC_TZ).date()
            != bay_gio.astimezone(CLINIC_TZ).date()
        ):
            raise ValidationError("Chỉ check-in luôn được khi đổi sang hôm nay.")
        cho_ngoai_ca = check_in and la_khung_bay_gio(slot_start, bay_gio)

        t_doi = resolve_action("reschedule")
        t_vao = resolve_action("checkin")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                if check_in and t_vao.quyen:
                    # Hỏi TRƯỚC khi ghi gì: không có quyền check-in thì cả lệnh
                    # bị từ chối, lịch giữ nguyên (người dùng chọn "Chỉ đổi").
                    await doi_quyen(conn, identity, t_vao.quyen)
                ngoai_ca = False
                if cho_ngoai_ca:
                    try:
                        await self._chan_dat_ngoai_khung_ca(
                            conn, slot_start=slot_start, identity=identity
                        )
                    except ValidationError:
                        ngoai_ca = True
                    if not ngoai_ca and await self._roster_warning(
                        conn,
                        doctor_id,
                        slot_start,
                        identity,
                        location_id=await _co_so_lich(conn, appointment_id, identity),
                    ):
                        ngoai_ca = True
                ghi = (
                    f"{ly_do_sach} · ngoài ca (khách đã có mặt tại quầy)"
                    if ngoai_ca
                    else ly_do_sach
                )
                kq = await self._hanh_dong_trong_gd(
                    conn,
                    appointment_id=appointment_id,
                    action="reschedule",
                    transition=t_doi,
                    identity=dung_vai(identity, t_doi.allowed_roles),
                    cancellation_reason=ghi,
                    doctor_id=doctor_id,
                    doctor_id_provided=True,
                    slot_start=slot_start,
                    slot_end=slot_end,
                    cho_ngoai_ca=cho_ngoai_ca,
                    xoa_so_thu_tu=check_in,
                )
                visit_id: str | None = None
                status = kq.new_status
                if check_in:
                    kq_vao = await self._hanh_dong_trong_gd(
                        conn,
                        appointment_id=appointment_id,
                        action="checkin",
                        transition=t_vao,
                        identity=dung_vai(identity, t_vao.allowed_roles),
                    )
                    visit_id = kq_vao.visit_id
                    status = kq_vao.new_status
                so_kham = await conn.fetchval(
                    "SELECT queue_number FROM appointment"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    appointment_id,
                    identity.clinic_id,
                )
        await self._bao_neu_vua_co_bac_si(kq, appointment_id, identity)
        logger.info(
            "appointment_doi_lich_nhanh",
            appointment_id=appointment_id,
            check_in=check_in,
            ngoai_ca=ngoai_ca,
            by_staff_id=identity.staff_id,
        )
        return {
            "status": status,
            "visit_id": visit_id,
            "queue_number": so_kham,
            "ngoai_ca": ngoai_ca,
        }

    async def doi_dich_vu_kham(
        self,
        *,
        appointment_id: str,
        service_type_id: str,
        identity: StaffIdentity,
        trong_ho_so: bool = False,
    ) -> dict[str, Any]:
        """ĐỔI DỊCH VỤ KHÁM (V5, Tuyền chốt 30/09/2026) — menu ⋯ dòng lịch hẹn.

        ``trong_ho_so`` (T5, 07/10/2026): đổi ngay trong hồ sơ khám — quyền khối
        y khoa / trưởng ca (`QUYEN_DOI_TRONG_HO_SO`), đã có phiếu / đã thu / đã
        tick vẫn đổi (`ly_do_khong_doi(trong_ho_so=True)`); luật bác sĩ bắt buộc
        chỉ còn là lời nhắc. Phiếu cũ, tick dịch vụ con giữ nguyên.

        Trước check-in: đổi lịch. Sau check-in: đổi cả lượt khám, chỉ khi chưa
        vướng gì (`doi_dich_vu_kham.ly_do_khong_doi`); khối Hành trình nghe sự
        kiện rồi xếp lại hàng chờ đầu tiên. Không đổi được thì câu 409 nói rõ.

        Chọn lại đúng dịch vụ đang có = không làm gì (bấm hai lần không lỗi).
        """
        aid = ma_uuid(appointment_id, "Mã lịch hẹn không hợp lệ.")
        dv_id = ma_uuid(service_type_id, "Dịch vụ không hợp lệ.")
        cid = identity.clinic_id
        canh_bao: list[str] = []
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await doi_mot_quyen(
                    conn,
                    identity,
                    QUYEN_DOI_TRONG_HO_SO if trong_ho_so else QUYEN_DOI_DICH_VU_KHAM,
                    cau=(
                        "Bạn không có quyền đổi dịch vụ khám trong hồ sơ (cần khối"
                        " khám / ghi bệnh án hoặc điều phối khách)."
                        if trong_ho_so
                        else "Bạn không có quyền đổi dịch vụ khám (cần “Quản lý lịch "
                        "hẹn” hoặc “Check-in khách”)."
                    ),
                )
                # Khoá lịch rồi lượt (cùng thứ tự mọi đường) — tick dịch vụ con
                # (`PhiKhamService.chon`) cũng khoá lượt, nên hai bên không lọt.
                if not await conn.fetchval(
                    "SELECT 1 FROM appointment WHERE clinic_id = $1::uuid"
                    " AND id = $2::uuid FOR UPDATE",
                    cid,
                    aid,
                ):
                    raise NotFoundError("Không tìm thấy lịch hẹn")
                await conn.execute(
                    "SELECT 1 FROM visit WHERE clinic_id = $1::uuid"
                    " AND appointment_id = $2::uuid FOR UPDATE",
                    cid,
                    aid,
                )
                tt = await doc_trang_thai(conn, cid, aid)
                moi = await conn.fetchrow(
                    "SELECT id::text, name FROM service_type"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid AND is_active",
                    cid,
                    dv_id,
                )
                if moi is None:
                    raise ValidationError("Dịch vụ không hợp lệ hoặc đã tắt.")
                if tt.dich_vu_id == moi["id"]:
                    return {
                        "ok": True,
                        "doi": False,
                        "da_check_in": tt.sau_check_in,
                        "dich_vu": moi["name"],
                        "canh_bao": [],
                    }
                ly_do = tt.ly_do_khong_doi(trong_ho_so=trong_ho_so)
                if ly_do:
                    raise ConflictError(ly_do)
                if not tt.bac_si_con_kham and not trong_ho_so:
                    raise ConflictError(CAU_BAC_SI_NGHI)
                loi_bs = await self._luat_bac_si_bat_buoc(
                    conn,
                    clinic_patient_id=tt.clinic_patient_id,
                    service_type_id=moi["id"],
                    doctor_id=tt.doctor_id,
                    identity=identity,
                )
                if loi_bs:
                    cau, chan = loi_bs
                    if chan and not trong_ho_so:
                        raise ConflictError(
                            f"{cau} Đổi bác sĩ (Đổi lịch) trước rồi mới đổi dịch vụ."
                        )
                    canh_bao.append(cau)

                await conn.execute(
                    "UPDATE appointment SET service_type_id = $3::uuid,"
                    " updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    aid,
                    moi["id"],
                )
                visit_id = tt.visit_id if (tt.sau_check_in or trong_ho_so) else None
                if visit_id:
                    await conn.execute(
                        "UPDATE visit SET service_type_id = $3::uuid,"
                        " updated_at = now()"
                        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
                        cid,
                        visit_id,
                        moi["id"],
                    )
                chi_tiet = {
                    "appointment_id": aid,
                    "visit_id": visit_id,
                    "tu_dich_vu_id": tt.dich_vu_id,
                    "den_dich_vu_id": moi["id"],
                    "tu_ten": tt.ten_dich_vu,
                    "den_ten": moi["name"],
                    "trong_ho_so": trong_ho_so,
                }
                await record_event(
                    conn,
                    event_type="appointment.service_switched",
                    aggregate_type="appointment",
                    aggregate_id=aid,
                    identity=identity,
                    origin="api:appointment-doi-dich-vu-kham",
                    payload=chi_tiet,
                    correlation_id=visit_id,
                )
                await emit_event(
                    conn,
                    ten="appointment.service_switched",
                    clinic_id=cid,
                    aggregate_id=aid,
                    payload=LichDaDoiDichVu(**chi_tiet),
                    boi=nguoi(identity),
                    correlation_id=visit_id,
                )
        logger.info(
            "appointment_doi_dich_vu_kham",
            appointment_id=aid,
            sau_check_in=tt.sau_check_in,
            by_staff_id=identity.staff_id,
        )
        return {
            "ok": True,
            "doi": True,
            "da_check_in": tt.sau_check_in,
            "dich_vu": moi["name"],
            "canh_bao": canh_bao,
        }

    async def _bao_neu_vua_co_bac_si(
        self, kq: _KetQuaHanhDong, appointment_id: str, identity: StaffIdentity
    ) -> None:
        # LỊCH VỪA CÓ BÁC SĨ → BÁO CSKH. Đây là mắt xích cuối của vòng mà màn
        # Đặt lịch đã hứa với người dùng bằng chữ: *"Lịch đặt xong sẽ nằm ở màn
        # Chờ xếp bác sĩ để quản lý phân người; khi đã có bác sĩ, khách này hiện
        # lại ở Quản lý khách hàng để CSKH gọi xác nhận lịch và bác sĩ."*
        #
        # Nửa đầu câu ấy đúng từ trước — `doctor_id IS NULL` là hàng chờ. Nửa
        # sau thì không: chưa có gì đánh thức CSKH, nên họ phải tự nhớ mà vào
        # xem. Đặt ở đây, SAU khi giao dịch đã commit: giao dịch cuộn lại mà
        # thông báo đã bay đi là báo một việc chưa xảy ra.
        #
        # Chỉ khi doctor_id đi từ RỖNG sang CÓ. Đổi bác sĩ này sang bác sĩ khác
        # cũng đáng biết, nhưng nó không phải cái kết thúc chờ đợi — gộp vào là
        # CSKH nhận thông báo cho mọi lần quản lý sửa phân công.
        if kq.doctor_cu is None and kq.doctor_moi:
            await self._bao_cskh_da_co_bac_si(
                appointment_id=appointment_id,
                doctor_id=kq.doctor_moi,
                identity=identity,
            )

    @staticmethod
    async def _ghi_xac_minh(
        conn: asyncpg.Connection,
        *,
        appointment_id: str,
        cach: str,
        identity: StaffIdentity,
    ) -> None:
        """Lưu bằng chứng xác minh lên lượt khám của lịch — cùng giao dịch check-in.

        Chụp dịch vụ và bác sĩ CỦA LỊCH TẠI LÚC XÁC MINH: về sau lịch bị đổi bác
        sĩ/dịch vụ thì vẫn biết lễ tân đã xác nhận với khách điều gì. Check-in
        lại (sau hoàn tác) ghi đè bằng lần mới; từng lần vẫn nằm trong event_log.
        """
        await conn.execute(
            """
            UPDATE public.visit v
               SET xac_minh_cach       = $3,
                   xac_minh_boi        = $4::uuid,
                   xac_minh_luc        = now(),
                   xac_minh_dich_vu_id = a.service_type_id,
                   xac_minh_bac_si_id  = a.doctor_id,
                   updated_at          = now()
              FROM public.appointment a
             WHERE a.id = $1::uuid AND a.clinic_id = $2::uuid
               AND v.appointment_id = a.id AND v.clinic_id = $2::uuid
            """,
            appointment_id,
            identity.clinic_id,
            cach,
            identity.staff_id,
        )

    async def _xep_vao_lich_truc(
        self,
        conn: asyncpg.Connection,
        *,
        appointment_id: str,
        doctor_id: str,
        slot_start: datetime,
        identity: StaffIdentity,
    ) -> None:
        """Quản lý vừa gán bác sĩ → cho bác sĩ ấy một ca trực ngày hôm đó.

        Quang 09/08/2026: *"quản lý chọn bác sĩ cho thật, nhưng lúc đó thì bác
        sĩ lại chưa được tự động được xếp vào lịch làm việc"*. Đúng: gán bác sĩ
        chỉ ghi `appointment.doctor_id`, không ai đụng `work_roster`.

        BA QUYẾT ĐỊNH, NÓI RÕ VÌ CHÚNG KHÔNG SUY RA ĐƯỢC TỪ DỮ LIỆU:

        1.  CA nào — lấy theo giờ của CHÍNH lịch hẹn, hỏi `core.shifts` để
            biết giờ ấy rơi vào ca nào (giờ từng ca do phòng khám khai, và nó
            chỉ được nằm ở một chỗ). Xếp cả ngày cho một lịch 18:00 là tự ý
            tuyên bố bác sĩ đi làm từ sáng.
        2.  TRẠM là `LICH_KHAM` — "Lịch khám (Bác sĩ)" trong `lib/roster.ts`, và
            là trạm màn Đặt lịch đọc để liệt kê bác sĩ khám.
        3.  KHÔNG áp dụng tuần. Thêm một dòng trực khác hẳn với việc chốt cả
            tuần; `roster_week` vẫn là chữ ký của quản lý, và `capacity_service`
            đọc nó để phân biệt "chưa xếp" với "nghỉ". Tự áp hộ ở đây là thay
            quản lý tuyên bố những ngày còn lại của tuần không ai đi làm.

        KHÔNG GHI ĐÈ, KHÔNG NHÂN BẢN: đã có dòng APPROVED phủ ca ấy (FULL hoặc
        đúng ca) thì thôi.

        CHỈ KHI TUẦN CHƯA CÔNG BỐ (15/09/2026). Tuần đã công bố thì lịch trực
        là sự thật đã chốt: gán bác sĩ không trực đã bị `_guard_slot` chặn, và
        nếu phòng khám tắt `require_roster` thì cũng không được lặng lẽ viết
        thêm ca vào lịch đã công bố — đổi lịch trực là việc của màn Lịch làm
        việc, có người bấm và có vết. Quyết định gốc của Quang (09/08) nói về
        lúc xếp lịch cho khách đặt trước — đúng phạm vi tuần chưa công bố.
        """
        if await conn.fetchval(
            "SELECT public.tuan_lich_truc_da_cong_bo($1::uuid, $2)",
            identity.clinic_id,
            slot_start,
        ):
            return
        cuc_bo = slot_start.astimezone(CLINIC_TZ)
        ngay = cuc_bo.date()
        cai_dat = await conn.fetchval(
            "SELECT settings FROM public.clinic WHERE id = $1::uuid",
            identity.clinic_id,
        )
        ca = ca_cua_phut(
            cuc_bo.hour * 60 + cuc_bo.minute,
            ca_tu_settings((cai_dat)),
        )

        da_co = await conn.fetchval(
            """
            SELECT 1 FROM public.work_roster
             WHERE clinic_id = $1::uuid AND staff_id = $2::uuid
               AND work_date = $3 AND status = 'APPROVED'
               AND shift IN ('FULL', $4)
             LIMIT 1
            """,
            identity.clinic_id,
            doctor_id,
            ngay,
            ca,
        )
        if da_co:
            return

        # NHÂN SỰ KHÔNG CÓ CỘT `clinic_id` — quan hệ với phòng khám nằm ở
        # `clinic_membership` (nền tảng đa phòng khám, 20260730000003). Lọc theo
        # `staff.clinic_id` là truy vấn không chạy được, không phải một bộ lọc
        # chặt hơn. Dùng đúng phép nối mà `doctor_in_clinic` ở `_build_patch`
        # dùng, để hai chỗ không trả lời khác nhau về cùng một bác sĩ.
        ten = await conn.fetchval(
            """
            SELECT st.full_name
              FROM public.staff st
              JOIN public.clinic_membership m ON m.staff_id = st.id
             WHERE st.id = $1::uuid AND st.is_active
               AND m.clinic_id = $2::uuid AND m.is_active
            """,
            doctor_id,
            identity.clinic_id,
        )
        if ten is None:
            # Bác sĩ không thuộc phòng khám này — `_build_patch` đã chặn từ
            # trước (`doctor_in_clinic`), nên tới đây là dữ liệu đã lệch. Không
            # bịa một dòng trực mang tên rỗng đè lên đó.
            return

        # `week_start` là thứ Hai của tuần chứa ngày ấy — cùng công thức mà
        # `roster_week` và màn Lịch làm việc dùng.
        tuan = ngay - timedelta(days=ngay.isoweekday() - 1)
        # Người bấm cho sổ lịch sử lịch trực (trigger, Khối 3 06/10/2026).
        async with giao_dich_lich_truc(conn, identity.staff_id):
            await conn.execute(
                """
                INSERT INTO public.work_roster
                    (clinic_id, week_start, work_date, shift, station,
                     staff_id, staff_name, status)
                VALUES ($1::uuid, $2, $3, $4, 'LICH_KHAM', $5::uuid, $6, 'APPROVED')
                """,
                identity.clinic_id,
                tuan,
                ngay,
                ca,
                doctor_id,
                ten,
            )
        await _log(
            conn,
            event_type="roster.tu_xep_theo_lich_hen",
            aggregate_id=appointment_id,
            payload={
                "work_date": ngay.isoformat(),
                "week_start": tuan.isoformat(),
                "shift": ca,
                "station": "LICH_KHAM",
                "staff_id": doctor_id,
                "staff_name": ten,
            },
            identity=identity,
            origin="api:appointment-assign_doctor",
        )
        logger.info(
            "roster_tu_xep_theo_lich_hen",
            appointment_id=appointment_id,
            staff_id=doctor_id,
            work_date=ngay.isoformat(),
            shift=ca,
        )

    async def _bao_cskh_da_co_bac_si(
        self, *, appointment_id: str, doctor_id: str, identity: StaffIdentity
    ) -> None:
        """Nhắn cho vai CSKH: lịch này xếp được bác sĩ rồi, gọi xác nhận đi.

        NUỐT LỖI CÓ CHỦ Ý. Việc chính — gán bác sĩ — đã xong và đã commit. Ném
        lỗi ở đây làm người gọi thấy một lời từ chối cho một hành động ĐÃ thành
        công, và lần sau họ bấm lại, gán lại, rồi tưởng hệ thống hỏng. Thông báo
        là lớp phủ thêm; nó hỏng thì ghi log, không kéo theo việc chính.
        """
        from clinicai.services.thong_bao_service import ThongBaoService

        try:
            row = await self._pool.fetchrow(
                """
                SELECT p.full_name AS khach,
                       p.patient_code,
                       s.full_name AS bac_si,
                       a.slot_start,
                       a.clinic_patient_id::text AS kh_id
                  FROM public.appointment a
                  LEFT JOIN public.patient p
                         ON p.clinic_patient_id = a.clinic_patient_id
                        AND p.clinic_id = a.clinic_id
                  LEFT JOIN public.staff s ON s.id = $2::uuid
                 WHERE a.id = $1::uuid AND a.clinic_id = $3::uuid
                """,
                appointment_id,
                doctor_id,
                identity.clinic_id,
            )
            if row is None:
                return
            khi = row["slot_start"].astimezone(CLINIC_TZ).strftime("%H:%M %d/%m")
            await ThongBaoService(self._pool).goi(
                identity=identity,
                vai_nhan=ClinicRole.CSKH.value,
                nguon="bac_si_da_xep",
                # Khoá chống trùng theo LỊCH HẸN: quản lý sửa phân công vài lần
                # trước khi chốt là chuyện thường, và CSKH chỉ cần biết một lần.
                nguon_id=appointment_id,
                muc_do="THUONG",
                tieu_de="Lịch đã có bác sĩ — gọi xác nhận với khách",
                noi_dung=(
                    f"{row['khach'] or 'Khách'} ({row['patient_code'] or '—'}) "
                    f"· {khi} · {row['bac_si'] or 'bác sĩ vừa được xếp'}. "
                    "Gọi xác nhận lại giờ khám và tên bác sĩ."
                ),
                # Trỏ THẲNG tới khách, không phải danh sách. `?selected=` là
                # tham số màn Quản lý khách hàng đã đọc sẵn (page.tsx) để mở
                # đúng hồ sơ — bấm "Bấm để xử lý" mà đổ ra danh sách rồi bắt
                # người ta tự dò tên là đúng bước thừa mà cái nút ấy xoá bỏ.
                #
                # VÀ TỚI ĐÚNG VIỆC, KHÔNG CHỈ ĐÚNG TRANG (Quang 10/08/2026).
                # `?selected=` một mình chỉ mở hồ sơ; cột phải vẫn chạy theo
                # việc GẤP NHẤT do `v_trang_thai_cskh` suy ra, thường là một
                # việc khác hẳn việc thông báo đang nói tới. Người trực bấm "Bấm
                # để xử lý" rồi phải tự tìm lại đúng bước — đúng thao tác thừa
                # mà cái nút này sinh ra để xoá.
                #
                #   `viec=CHO_XAC_NHAN` mở đúng bộ nút "Gọi xác nhận lịch"
                #                       (HanhDongTrangThai ghi loai=XAC_NHAN_LICH)
                #   `luot=<appointment_id>` trỏ vào ĐÚNG lượt vừa được xếp bác
                #                       sĩ — khách có nhiều lịch thì không có
                #                       nó là mở nhầm lượt.
                duong_dan=(
                    f"/customers?selected={row['kh_id']}"
                    f"&viec=CHO_XAC_NHAN&luot={appointment_id}"
                ),
            )
        except Exception:  # noqa: BLE001 — xem docstring
            logger.warning(
                "bao_cskh_da_co_bac_si_that_bai",
                appointment_id=appointment_id,
                exc_info=True,
            )

    # --------------------------------------------------------------- helpers

    async def _build_patch(
        self,
        conn: asyncpg.Connection,
        *,
        action: str,
        appt: asyncpg.Record,
        new_status: str,
        cancellation_reason: str | None,
        ly_do_huy_ma: str | None,
        doctor_id: str | None,
        doctor_id_provided: bool,
        slot_start: datetime | None,
        slot_end: datetime | None,
        identity: StaffIdentity,
        service_type_id: str | None = None,
        booking_channel: str | None = None,
        booking_channel_provided: bool = False,
        cho_ngoai_ca: bool = False,
    ) -> dict[str, Any]:
        patch: dict[str, Any] = {"status": new_status}

        if action == "cancel":
            ma = (ly_do_huy_ma or "").strip() or None
            chu = (cancellation_reason or "").strip() or None
            if ma is None:
                # KHÔNG tự điền 'KHAC' cho im chuyện. Mặc định âm thầm là cách
                # cột này thành 100% "khác" trong ba tháng, và lúc đó nó vô
                # dụng đúng bằng ô chữ tự do mà nó thay thế.
                raise ValidationError("Chọn lý do huỷ.")
            if ma not in LY_DO_HUY:
                raise ValidationError(f"Lý do huỷ không hợp lệ: {ma!r}.")
            if ma == "KHAC" and not chu:
                raise ValidationError("Chọn 'lý do khác' thì phải viết rõ lý do.")
            patch["cancelled_at"] = datetime.now(timezone.utc)
            patch["cancellation_reason"] = chu
            patch["ly_do_huy_ma"] = ma
            # AI huỷ — trước đây không lưu, nên một lịch huỷ nhầm không truy
            # được về ai. Lấy từ phiên, không nhận từ client.
            patch["cancelled_by_staff_id"] = identity.staff_id

        elif action == "reassign":
            new_doctor = (doctor_id or "").strip() or None
            patch["doctor_id"] = new_doctor
            await self._guard_slot(
                conn,
                doctor_id=new_doctor,
                slot_start=appt["slot_start"],
                slot_end=appt["slot_end"],
                channel=appt["booking_channel"],
                exclude_id=str(appt["id"]),
                identity=identity,
            )

        elif action == "assign_doctor":
            new_doctor = (doctor_id or "").strip() or None
            if not new_doctor:
                raise ValidationError("Chọn bác sĩ. Muốn bỏ bác sĩ thì dùng đổi lịch.")
            if appt["doctor_id"] is not None:
                # Lịch đã có bác sĩ thì đây là ĐỔI bác sĩ, không phải xếp lần
                # đầu — việc đó đi qua reschedule/reassign, nơi có ghi lý do.
                raise ConflictError(
                    "Lịch này đã có bác sĩ. Dùng Đổi lịch nếu cần đổi người."
                )
            patch["doctor_id"] = new_doctor

            # LUẬT BẮT BUỘC BÁC SĨ cũng áp ở đây. Không có chỗ này thì hàng chờ
            # thành đường vòng: đặt lịch để trống bác sĩ, rồi gán ai cũng được.
            loi_bs = await self._luat_bac_si_bat_buoc(
                conn,
                clinic_patient_id=str(appt["clinic_patient_id"]),
                service_type_id=(
                    str(appt["service_type_id"]) if appt["service_type_id"] else None
                ),
                doctor_id=new_doctor,
                identity=identity,
            )
            if loi_bs and loi_bs[1]:
                raise ConflictError(loi_bs[0])

            # Trần số chỗ áp ở ĐÂY, đúng lúc câu hỏi trở thành thật: trước đó
            # lịch chưa chiếm ghế của ai (xem migration 20260808000002).
            await self._guard_slot(
                conn,
                doctor_id=new_doctor,
                slot_start=appt["slot_start"],
                slot_end=appt["slot_end"],
                channel=appt["booking_channel"],
                exclude_id=str(appt["id"]),
                identity=identity,
            )

        elif action == "reschedule":
            if slot_start is None or slot_end is None:
                raise ValidationError("Thiếu giờ hẹn mới")
            if slot_end <= slot_start:
                raise ValidationError("Giờ kết thúc phải sau giờ bắt đầu")
            # Đổi lịch cũng là ĐẶT một khung giờ, nên cùng chốt với create().
            # Thiếu dòng này thì cửa trước khoá còn cửa sau mở: không đặt mới
            # vào quá khứ được, nhưng đặt một lịch tương lai rồi dời nó về hôm
            # qua thì được.
            _chan_dat_vao_qua_khu(slot_end)
            # `cho_ngoai_ca` CHỈ do `doi_lich_nhanh` bật, khi khách ĐANG ĐỨNG ở
            # quầy (khung = bây giờ + check-in luôn). Sức chứa vẫn giữ.
            if not cho_ngoai_ca:
                await self._chan_dat_ngoai_khung_ca(
                    conn, slot_start=slot_start, identity=identity
                )
            patch["slot_start"] = slot_start
            patch["slot_end"] = slot_end
            # KHÔNG KHOÁ DỊCH VỤ CŨ (Tuyền 24/09/2026: "open cho chọn cái khác
            # cũng được"). Dịch vụ mới phải thuộc phòng khám và đang bật.
            if service_type_id and service_type_id != str(
                appt["service_type_id"] or ""
            ):
                if not await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM service_type WHERE id = $1::uuid"
                    " AND clinic_id = $2::uuid AND is_active)",
                    service_type_id,
                    identity.clinic_id,
                ):
                    raise ValidationError("Dịch vụ không hợp lệ hoặc đã tắt.")
                patch["service_type_id"] = service_type_id
            # Kênh đặt đổi được; `is_walkin` luôn đi theo kênh (CHECK ở DB).
            if booking_channel_provided:
                kenh = (booking_channel or "").strip() or None
                patch["booking_channel"] = kenh
                patch["is_walkin"] = (kenh or "").upper() == "WALK_IN"
            # Only touch the doctor when the field was actually sent; an absent
            # field means "leave them", an empty one means "unassign".
            if doctor_id_provided:
                patch["doctor_id"] = (doctor_id or "").strip() or None
            target_doctor = (
                patch.get("doctor_id")
                if doctor_id_provided
                else (str(appt["doctor_id"]) if appt["doctor_id"] else None)
            )
            await self._guard_slot(
                conn,
                doctor_id=target_doctor,
                slot_start=slot_start,
                slot_end=slot_end,
                channel=patch.get("booking_channel", appt["booking_channel"]),
                exclude_id=str(appt["id"]),
                identity=identity,
                cho_ngoai_ca=cho_ngoai_ca,
            )

        # GÁN ĐƯỢC BÁC SĨ LÀ CẢNH BÁO PHẢI TẮT — Ở MỘT CHỖ CHO CẢ BA ĐƯỜNG.
        #
        # `bac_si_da_go_id` là vết "ca trực của bác sĩ cũ bị xoá, khách đang
        # chờ xếp người khác" (config_service.remove). Trước 15/08/2026 không
        # đường gán bác sĩ nào xoá vết ấy, nên sau khi CSKH đã xử lý XONG —
        # gán người mới qua assign_doctor / reassign / reschedule — bảng lịch
        # tuần và màn khách hàng vẫn đỏ "X đã nghỉ — gọi khách xếp bác sĩ
        # khác" vĩnh viễn. Một cảnh báo không bao giờ tắt dạy người trực bỏ
        # qua mọi cảnh báo, kể cả cái đúng.
        #
        # Đặt ở ĐUÔI hàm thay vì lặp trong từng nhánh: nhánh ghi doctor_id
        # thứ tư thêm sau này cũng tự được phủ. Chỉ xoá khi gán ĐƯỢC người
        # (giá trị thật) — reschedule mà bỏ trống bác sĩ thì khách vẫn đang
        # chờ xếp, vết phải ở lại để màn hình còn nói được "đổi từ ai".
        if patch.get("doctor_id"):
            patch["bac_si_da_go_id"] = None
            patch["bo_bac_si_luc"] = None

        return patch

    async def _chan_dat_ngoai_khung_ca(
        self,
        conn: asyncpg.Connection,
        *,
        slot_start: datetime,
        identity: StaffIdentity,
    ) -> None:
        """Chỉ nhận lịch RƠI VÀO một ca làm việc của phòng khám.

        Trước đây giờ mở cửa rộng hơn tổng ba ca, nên vẫn đặt được vào ba
        khoảng trống: sớm hơn ca sáng, nghỉ trưa, và sau khi hết ca tối. Đo
        trên staging 21/08/2026 có 3 lịch như vậy (07:15, 07:30, và một lịch
        đúng 21:30). Chúng không lỗi ở đâu cả — chỉ lặng lẽ không thuộc ca nào,
        nên KPI theo ca của CSKH đếm thiếu đúng những lịch ấy.

        ĐO THEO GIỜ BẮT ĐẦU, KHÔNG PHẢI CẢ KHOẢNG. Khách vãng lai bước vào lúc
        12:50 được tạo lịch với ``slot_start`` = bây giờ; nếu bắt cả khoảng phải
        nằm gọn trong ca thì một dịch vụ 30 phút sẽ tràn qua 13:00 và lễ tân bị
        từ chối trước mặt người đang đứng đó. Giờ bắt đầu mới là cái người ta
        gọi là "giờ hẹn", và đó cũng là mốc mà mọi luật khác trong file này đo.

        Ngày phòng khám đóng cửa (``clinic_hours_for_date`` không trả gì) thì im
        lặng, để luật giờ mở cửa nói — hai luật cùng hét một lỗi thì người dùng
        đọc được một nửa sự thật.
        """
        local = slot_start.astimezone(CLINIC_TZ)
        row = await conn.fetchrow(
            """
            SELECT (SELECT open_minute FROM clinic_hours_for_date($1::uuid, $2))
                     AS open_minute,
                   (SELECT close_minute FROM clinic_hours_for_date($1::uuid, $2))
                     AS close_minute,
                   (SELECT settings FROM clinic WHERE id = $1::uuid) AS settings
            """,
            identity.clinic_id,
            local.date(),
        )
        if row is None or row["open_minute"] is None or row["close_minute"] is None:
            return
        ca = ca_tu_settings(row["settings"])
        windows = shift_windows("FULL", row["open_minute"], row["close_minute"], ca)
        if not windows:
            return
        minute = local.hour * 60 + local.minute
        if covers(windows, minute):
            return
        raise ValidationError(
            f"Phòng khám chỉ nhận lịch trong {describe(windows)}. "
            f"Giờ {minute // 60:02d}:{minute % 60:02d} không thuộc ca nào — "
            "chọn giờ trong ca, hoặc sửa giờ ca ở Cài đặt → Giờ ca làm việc."
        )

    async def _guard_slot(
        self,
        conn: asyncpg.Connection,
        *,
        doctor_id: str | None,
        slot_start: datetime,
        slot_end: datetime,
        channel: str | None,
        exclude_id: str,
        identity: StaffIdentity,
        cho_ngoai_ca: bool = False,
    ) -> None:
        if doctor_id:
            await self._validate_doctor_ref(conn, doctor_id, identity.clinic_id)
            busy = await self._doctor_conflict(
                conn, doctor_id, slot_start, slot_end, identity, exclude_id
            )
            if busy:
                raise ConflictError(busy)
            # LỊCH TRỰC ĐÃ CÔNG BỐ CŨNG CHẶN GÁN / ĐỔI / DỜI — không chỉ đặt mới.
            #
            # Trước 15/09/2026 chốt này chỉ nằm ở create(), nên ba đường sửa
            # lịch (assign_doctor, reassign, reschedule) đưa được khách vào tay
            # một bác sĩ không trực giờ ấy trong tuần ĐÃ công bố — và
            # assign_doctor còn tự chèn ca cho họ. Gỡ ca một bác sĩ rồi gán lại
            # chính người đó ở hàng chờ là ca tự mọc lại. `_roster_warning` chỉ
            # lên tiếng khi tuần đã áp dụng, nên tuần chưa công bố không đổi
            # (CONTEXT v1.0 §4: trước công bố nhận lịch thật).
            # Khách đến sớm ngoài giờ ca (đổi lịch nhanh): bác sĩ vẫn phải CÓ ca
            # trong ngày, chỉ bỏ câu "không có mặt lúc HH:MM".
            off_duty = await self._roster_warning(
                conn,
                doctor_id,
                slot_start,
                identity,
                chi_can_co_ca=cho_ngoai_ca,
                location_id=await _co_so_lich(conn, exclude_id, identity),
            )
            if off_duty and await self._roster_is_required(conn, identity):
                raise ConflictError(off_duty)
        policy = await load_effective_policy(
            conn, identity.clinic_id, doctor_id, slot_start
        )
        full = await self._slot_full(
            conn, doctor_id, slot_start, channel or "", identity, policy, exclude_id
        )
        if full:
            raise ConflictError(full)

    async def _validate_booking_refs(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_patient_id: str,
        location_id: str,
        service_type_id: str,
        doctor_id: str | None,
        identity: StaffIdentity,
    ) -> None:
        """Fail before INSERT when any supplied id belongs to another clinic."""
        refs = await conn.fetchrow(
            """
            SELECT
                EXISTS (
                    SELECT 1 FROM patient p
                     WHERE p.clinic_patient_id = $1::uuid
                       AND p.clinic_id = $5::uuid
                       AND p.is_active
                ) AS patient_ok,
                EXISTS (
                    SELECT 1 FROM clinic_location l
                     WHERE l.id = $2::uuid
                       AND l.clinic_id = $5::uuid
                       AND l.is_active
                ) AS location_ok,
                EXISTS (
                    SELECT 1 FROM service_type s
                     WHERE s.id = $3::uuid
                       AND s.clinic_id = $5::uuid
                       AND s.is_active
                ) AS service_ok,
                (
                    $4::uuid IS NULL
                    OR EXISTS (
                        SELECT 1
                          FROM staff st
                          JOIN clinic_membership m ON m.staff_id = st.id
                         WHERE st.id = $4::uuid
                           AND st.is_active
                           AND m.clinic_id = $5::uuid
                           AND m.is_active
                           AND m.role IN (
                               'DOCTOR', 'ULTRASOUND_DOCTOR'
                           )
                    )
                ) AS doctor_ok
            """,
            clinic_patient_id,
            location_id,
            service_type_id,
            doctor_id,
            identity.clinic_id,
        )
        if refs is None or not refs["patient_ok"]:
            raise ValidationError("Mã bệnh nhân không thuộc phòng khám này")
        if not refs["location_ok"]:
            raise ValidationError("Mã cơ sở không thuộc phòng khám này")
        if not refs["service_ok"]:
            raise ValidationError("Mã dịch vụ không thuộc phòng khám này")
        if not refs["doctor_ok"]:
            raise ValidationError("Mã bác sĩ không thuộc phòng khám này")

    async def _validate_doctor_ref(
        self,
        conn: asyncpg.Connection,
        doctor_id: str,
        clinic_id: str | None,
    ) -> None:
        valid = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                  FROM staff st
                  JOIN clinic_membership m ON m.staff_id = st.id
                 WHERE st.id = $1::uuid
                   AND st.is_active
                   AND m.clinic_id = $2::uuid
                   AND m.is_active
                   AND m.role IN ('DOCTOR', 'ULTRASOUND_DOCTOR')
            )
            """,
            doctor_id,
            clinic_id,
        )
        if not valid:
            raise ValidationError("Mã bác sĩ không thuộc phòng khám này")

    async def _update(
        self,
        conn: asyncpg.Connection,
        appointment_id: str,
        patch: dict[str, Any],
        from_statuses: frozenset[str],
        clinic_id: str | None,
    ) -> bool:
        columns = list(patch)
        assignments = ", ".join(f"{c} = ${i + 3}" for i, c in enumerate(columns))
        try:
            updated = await conn.fetchval(
                f"""
                UPDATE appointment
                   SET {assignments}, updated_at = now()
                 WHERE id = $1::uuid AND status = ANY($2::text[])
                   AND clinic_id = ${len(columns) + 3}::uuid
                RETURNING id
                """,
                appointment_id,
                list(from_statuses),
                *[patch[c] for c in columns],
                clinic_id,
            )
        except asyncpg.ExclusionViolationError as exc:
            raise ConflictError("Bác sĩ đã có lịch trùng khung giờ mới này.") from exc
        except asyncpg.CheckViolationError as exc:
            if "Khung giờ đã đầy" in str(exc):
                raise ConflictError(str(exc)) from exc
            raise
        return updated is not None

    async def _check_in(
        self,
        conn: asyncpg.Connection,
        appointment_id: str,
        transition: Transition,
    ) -> bool:
        """Status change plus daily queue number, in one serialized call."""
        rows = await conn.fetch(
            "SELECT * FROM check_in_appointment($1::uuid, $2::text[])",
            appointment_id,
            list(transition.from_statuses),
        )
        return bool(rows)

    async def _luat_bac_si_bat_buoc(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_patient_id: str,
        service_type_id: str | None,
        doctor_id: str | None,
        identity: StaffIdentity,
    ) -> tuple[str, bool] | None:
        """Câu từ chối + có chặn hẳn không; None nếu không vướng luật nào.

        BỎ QUA KHI CHƯA CHỌN BÁC SĨ. Lịch đang chờ xếp người thì chưa có gì để
        đối chiếu — luật sẽ áp lúc quản lý gán bác sĩ, cùng chỗ với trần số chỗ.
        Chặn ở đây là chặn luôn cả hàng chờ, đúng thứ nhịp trước vừa mở ra.

        "KHÁCH MỚI" SUY TỪ LỊCH SỬ, không đọc `appointment.patient_kind`. Ô đó
        do lễ tân gõ tay, nullable, và màn đặt lịch tự điền nó theo "có đợt chăm
        sóc đang mở hay không" — nên một khách gõ nhầm là luật bỏ lọt, và một
        khách cũ quay lại có thể bị bắt khám lại từ đầu.
        """
        if not service_type_id or not doctor_id:
            return None

        luat = await conn.fetchrow(
            """
            SELECT l.required_staff_id::text AS bac_si_id,
                   l.chan_han,
                   s.full_name AS ten_bac_si,
                   st.name     AS ten_dich_vu,
                   public.la_khach_moi_cua_dich_vu(
                       l.clinic_id, $2::uuid, l.service_type_id,
                       l.cach_tinh, l.so_thang) AS khach_moi
              FROM public.luat_bac_si_bat_buoc l
              JOIN public.staff s        ON s.id = l.required_staff_id
              JOIN public.service_type st ON st.id = l.service_type_id
             WHERE l.clinic_id = $1::uuid
               AND l.service_type_id = $3::uuid
               AND l.is_active
            """,
            identity.clinic_id,
            clinic_patient_id,
            service_type_id,
        )
        if luat is None or not luat["khach_moi"]:
            return None
        if str(luat["bac_si_id"]) == str(doctor_id):
            return None

        return (
            f"Khách mới của {luat['ten_dich_vu']} phải khám "
            f"{luat['ten_bac_si']} lần đầu.",
            bool(luat["chan_han"]),
        )

    async def _patient_double_booked(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_patient_id: str,
        slot_start: datetime,
        identity: StaffIdentity,
    ) -> str | None:
        """Bệnh nhân này đã có lịch ở đúng khung giờ này chưa.

        Chặn ĐÚNG cái bấm hai lần: cùng bệnh nhân, cùng thời điểm bắt đầu. Không
        chặn hai lịch khác giờ trong cùng buổi — đó là chuyện bình thường (khám
        rồi siêu âm sau).

        Chặn ở tầng dịch vụ, không phải chỉ mục duy nhất, vì prod đang có sẵn 5
        dòng trùng từ trước; tạo chỉ mục lúc này sẽ hỏng. Nó không chống được
        hai request thật sự đồng thời — nhưng cái đang xảy ra là một người bấm
        ba lần cách nhau 5 giây, và với chuyện đó thì câu này đủ.
        """
        row = await conn.fetchrow(
            """
            SELECT slot_start, status
              FROM appointment
             WHERE clinic_id = $1::uuid
               AND clinic_patient_id = $2::uuid
               AND slot_start = $3
               AND status <> ALL ($4::text[])
             LIMIT 1
            """,
            identity.clinic_id,
            clinic_patient_id,
            slot_start,
            list(DEAD_STATUSES),
        )
        if row is None:
            return None
        status_cu = {
            "SCHEDULED": "chờ xác nhận",
            "CSKH_CONFIRMED": "CSKH đã xác nhận",
            "CONFIRMED": "đã đặt lịch",
            "CHECKED_IN": "đã đến phòng khám",
        }.get(row["status"], row["status"])
        hhmm = slot_start.astimezone(CLINIC_TZ).strftime("%H:%M")
        # NÓI RÕ ĐÂY LÀ LẦN THỨ HAI, đừng chỉ từ chối.
        #
        # Quang: *"cùng 1 khách mà giờ đặt 2 lần thì hệ thống phải thông báo
        # đây là lần 2"*. Một câu từ chối trống làm người ta tưởng thao tác
        # trước đó hỏng và thử lại lần nữa — đúng vòng lặp sinh ra ba lịch
        # trùng hôm 04/08.
        return (
            f"Đây là lần đặt thứ hai — bệnh nhân này ĐÃ có lịch lúc {hhmm} "
            f"({status_cu}). Lần bấm trước đã thành công, không cần đặt lại. "
            "Muốn đổi giờ thì vào Quản lý khách hàng → Lịch hẹn sắp tới."
        )

    async def _doctor_conflict(
        self,
        conn: asyncpg.Connection,
        doctor_id: str,
        slot_start: datetime,
        slot_end: datetime,
        identity: StaffIdentity,
        exclude_id: str | None = None,
    ) -> str | None:
        """A sentence about why this doctor is unavailable, or None.

        Lưới thật là trigger sức chứa (``enforce_slot_capacity``), không phải
        ``appointment_no_doctor_overlap`` — ràng buộc đó không tồn tại. Trigger
        chặt hơn hàm này (2+1 mỗi khung so với 6), nên câu ở đây gần như chỉ
        dùng cho lịch dài hơn một khung. Lý do vẫn kiểm trước khi ghi: "đã đạt
        giới hạn 6 lịch trong khung 09:15–09:30" nói cho lễ tân biết phải làm
        gì tiếp; một tên ràng buộc thì không.
        """
        overlapping = await conn.fetchval(
            """
            SELECT count(*)
              FROM appointment
             WHERE clinic_id = $1::uuid
               AND doctor_id = $2::uuid
               AND slot_start < $4
               AND slot_end > $3
               AND status <> ALL ($5::text[])
               AND ($6::uuid IS NULL OR id <> $6::uuid)
            """,
            identity.clinic_id,
            doctor_id,
            slot_start,
            slot_end,
            ["CANCELLED", "NO_SHOW"],
            exclude_id,
        )
        if (overlapping or 0) < DOCTOR_OVERLAP_CAP:
            return None

        name = await conn.fetchval(
            "SELECT full_name FROM staff WHERE id = $1::uuid", doctor_id
        )
        day = slot_start.astimezone(CLINIC_TZ).strftime("%d/%m")
        return (
            f"Bác sĩ{' ' + name if name else ''} đã đạt giới hạn "
            f"{DOCTOR_OVERLAP_CAP} lịch hẹn trong khung giờ "
            f"{_hhmm(slot_start)}–{_hhmm(slot_end)} ngày {day}. "
            "Vui lòng chọn khung giờ khác."
        )

    async def _roster_warning(
        self,
        conn: asyncpg.Connection,
        doctor_id: str,
        slot_start: datetime,
        identity: StaffIdentity,
        chi_can_co_ca: bool = False,
        location_id: str | None = None,
    ) -> str | None:
        """Câu cảnh báo nếu bác sĩ không có ca trực hôm đó; None nếu ổn.

        ``location_id`` = cơ sở của LỊCH HẸN: ca ở cơ sở khác không tính (Hào
        Nam 08/10 — bác sĩ trực Kim Ngưu không phải đang trực Hào Nam). None =
        mọi cơ sở.

        CHỈ CẢNH BÁO KHI ĐÃ CÓ LỊCH TRỰC CHO NGÀY ĐÓ. Đây là điểm mấu chốt:
        CSKH đặt lịch trước cả tháng, lúc đó lịch trực chưa xếp. Cảnh báo mọi
        lịch tương lai sẽ biến cảnh báo thành tiếng ồn, và tiếng ồn thì bị bỏ
        qua đúng vào lần nó nói thật.

        Vậy nên: ngày chưa xếp ca → im lặng. Ngày đã xếp ca mà bác sĩ này không
        có tên → nói ra.

        "ĐÃ XẾP CA" NGHĨA LÀ TUẦN ĐÃ ĐƯỢC ÁP DỤNG, không phải "có dòng trong
        bảng". Ngày 07/08/2026 có 26 tuần lịch được trải ra từ một mẫu tuần và
        ghi thẳng APPROVED tới 31/01/2027 — toàn bộ là bản nháp. Nếu ở đây chỉ
        hỏi "có dòng không" thì mọi lịch tương lai bỗng có cảnh báo dựa trên một
        bản nháp chưa ai duyệt, và cảnh báo sai còn tệ hơn không cảnh báo.
        Xem migration 20260808000001.
        """
        local = slot_start.astimezone(CLINIC_TZ)
        work_date = local.date()
        minute = local.hour * 60 + local.minute
        row = await conn.fetchrow(
            """
            SELECT
              -- "ĐÃ XẾP CA" = TUẦN CỦA NGÀY ĐÓ ĐÃ CÔNG BỐ (24/09/2026). Bản trước
              -- hỏi "hôm đó có ai có ca đã duyệt không" — một ngày trong tuần đã
              -- công bố mà KHÔNG AI được xếp (ngày nghỉ, hoặc chỉ bác sĩ này bị
              -- bỏ) thì bị coi là "chưa xếp" và vẫn nhận đặt cho bác sĩ nghỉ,
              -- trong khi màn "chờ xếp bác sĩ" đã đánh dấu chính các lịch ấy là
              -- MẤT BÁC SĨ. Bộ mô phỏng ngày khám bắt được.
              EXISTS (
                SELECT 1 FROM roster_week rw
                 WHERE rw.clinic_id = $1::uuid
                   AND rw.week_start = date_trunc('week', $2::date)::date
              ) AS roster_exists,
              coalesce((
                SELECT array_agg(DISTINCT shift) FROM work_roster
                 WHERE clinic_id = $1::uuid AND work_date = $2
                   AND staff_id = $3::uuid
                   AND status = 'APPROVED'
                   AND EXISTS (
                     SELECT 1 FROM roster_week rw
                      WHERE rw.clinic_id = work_roster.clinic_id
                        AND rw.week_start = work_roster.week_start
                   )
                   AND """
            + ca_thuoc_co_so("work_roster", "$4")
            + """
              ), ARRAY[]::text[]) AS shifts,
              (SELECT open_minute FROM clinic_hours_for_date($1::uuid, $2))
                AS open_minute,
              (SELECT close_minute FROM clinic_hours_for_date($1::uuid, $2))
                AS close_minute,
              -- Giờ ca của phòng khám, hỏi cùng lượt với giờ mở cửa: hai thứ
              -- luôn cần cùng nhau, thêm một vòng mạng là cái giá không đáng.
              (SELECT settings FROM clinic WHERE id = $1::uuid) AS settings
            """,
            identity.clinic_id,
            work_date,
            doctor_id,
            location_id or None,
        )
        if row is None or not row["roster_exists"]:
            return None

        name = await conn.fetchval(
            "SELECT full_name FROM staff WHERE id = $1::uuid", doctor_id
        )
        who = name or "Bác sĩ này"

        shifts: list[str] = list(row["shifts"])
        if not shifts:
            return (
                f"{who} không có lịch làm việc ngày {work_date:%d/%m/%Y}. "
                "Chọn ngày khác hoặc bác sĩ khác — hoặc xếp ca cho bác sĩ này "
                "ở màn Lịch làm việc trước."
            )

        if chi_can_co_ca:
            return None
        # CÓ TÊN TRONG NGÀY VẪN CÓ THỂ SAI GIỜ. Ca sáng không phải cả ngày;
        # giờ của từng ca do phòng khám khai, xem core/shifts.py.
        open_min, close_min = row["open_minute"], row["close_minute"]
        if open_min is None or close_min is None:
            return None
        ca = ca_tu_settings((row["settings"]))
        windows = merge_windows(
            [w for s in shifts for w in shift_windows(s, open_min, close_min, ca)]
        )
        if not windows or covers(windows, minute):
            return None
        return (
            f"{who} ngày {work_date:%d/%m/%Y} chỉ trực {describe(windows)}, "
            f"không có mặt lúc {minute // 60:02d}:{minute % 60:02d}. "
            "Chọn khung giờ trong ca trực hoặc đổi bác sĩ."
        )

    @staticmethod
    async def _roster_is_required(
        conn: asyncpg.Connection, identity: StaffIdentity
    ) -> bool:
        """Có TỪ CHỐI khi đặt cho bác sĩ không có ca trực không? Mặc định CÓ.

        Mặc định cũ là KHÔNG, vì "đặt trước rồi mới xếp ca là chuyện bình
        thường". Điều đó vẫn đúng, nhưng nó đã được giải quyết ở chỗ khác:
        ``_roster_warning`` chỉ lên tiếng KHI NGÀY ĐÓ ĐÃ XẾP CA. Ngày chưa xếp
        thì hàm này không bao giờ được gọi tới, nên luồng đặt trước cả tháng
        không hề bị chạm.

        Nghĩa là cờ này chỉ quyết định đúng một tình huống: ngày đã có lịch
        trực, và bác sĩ được chọn CHẮC CHẮN không đi làm hôm ấy. Để mặc định
        cho qua tình huống đó là tạo một cái hẹn mà không ai khám — sai lầm chỉ
        vỡ ra lúc bệnh nhân đã tới nơi, và người chịu là bệnh nhân.

        Quyết định của Quang (2026-08-04): *lịch của bác sĩ là luật cao nhất.*
        Phòng khám nào muốn quay lại kiểu chỉ-cảnh-báo thì đặt
        ``settings.booking.require_roster = false`` — một cờ, không phải một
        bản build khác.
        """
        return bool(
            await conn.fetchval(
                """
                SELECT coalesce(
                    (settings #> '{booking,require_roster}')::boolean, true)
                  FROM clinic WHERE id = $1::uuid
                """,
                identity.clinic_id,
            )
        )

    async def _slot_full(
        self,
        conn: asyncpg.Connection,
        doctor_id: str | None,
        slot_start: datetime,
        channel: str | None,
        identity: StaffIdentity,
        policy: ClinicPolicy,
        exclude_id: str | None = None,
    ) -> str | None:
        """The seat rule, as a sentence. Advisory; the DB trigger is the net.

        ``policy`` is passed in rather than read here so that the sentence and
        the trigger that will reject the write are looking at the same numbers —
        both come from the one row read at the top of this transaction.
        """
        begin, end = policy.bucket(slot_start)
        # Tuần CHƯA công bố lịch trực: lịch hẹn không bị chặn bằng trần — đối
        # soát lúc công bố (CONTEXT v1.0). Cùng hàm SQL mà trigger hỏi, để câu
        # tiếng Việt và cái net không nói hai điều khác nhau. Vãng lai vẫn kiểm.
        if not is_walkin(channel) and not await conn.fetchval(
            "SELECT public.tuan_lich_truc_da_cong_bo($1::uuid, $2)",
            identity.clinic_id,
            slot_start,
        ):
            return None
        # Đếm bằng CHÍNH hàm mà trigger gọi. Vòng lặp Python cũ ở đây đếm ghế
        # vãng lai bằng đúng số dòng có `booking_channel = 'WALK_IN'` — nay
        # thiếu một nửa: khách có hẹn đến muộn cũng chiếm ghế vãng lai của khung
        # họ có mặt (20260807000001). Câu tiếng Việt và cái net phải nói cùng
        # một con số, nếu không lễ tân sẽ đọc "còn chỗ" rồi bấm và bị từ chối.
        seats = await conn.fetchrow(
            """
            SELECT slot_seats_used($1::uuid, $2::uuid, $3, $4, FALSE, $5::uuid)
                       AS regular,
                   slot_seats_used($1::uuid, $2::uuid, $3, $4, TRUE,  $5::uuid)
                       AS walkin
            """,
            identity.clinic_id,
            doctor_id,
            begin,
            end,
            exclude_id,
        )
        regular = seats["regular"] if seats else 0
        walkin = seats["walkin"] if seats else 0

        window = f"{_hhmm(begin)}–{_hhmm(end)}"
        if is_walkin(channel):
            if walkin >= policy.walkin_cap:
                return (
                    f"Khung {window} đã đủ {policy.walkin_cap} chỗ vãng lai — "
                    f"chuyển khách sang khung {policy.slot_minutes} phút kế tiếp."
                )
            return None
        if regular >= policy.regular_cap:
            return (
                f"Khung {window} đã đủ {policy.regular_cap} chỗ đặt hẹn — "
                f"chọn khung khác. {policy.walkin_cap} chỗ còn lại chỉ dành cho "
                "khách vãng lai."
            )
        return None

    async def _attach_episode(
        self,
        conn: asyncpg.Connection,
        *,
        appointment_id: Any,
        clinic_patient_id: str,
        service_type_id: str,
        patient_kind: str | None,
        identity: StaffIdentity,
    ) -> None:
        """Attach the booking to a care episode.

        NEW closes any live episode and opens a fresh one — a new problem is a
        new course of care. RETURN (or an unstated kind with a live episode)
        joins the existing one, reopening a PENDING_CLOSE because a patient who
        came back is evidently still in care.
        """
        live = await conn.fetchrow(
            """
            SELECT id, status FROM care_episode
             WHERE clinic_id = $1::uuid
               AND clinic_patient_id = $2::uuid
               AND service_type_id = $3::uuid
               AND status <> 'CLOSED'
             ORDER BY created_at DESC LIMIT 1
            """,
            identity.clinic_id,
            clinic_patient_id,
            service_type_id,
        )

        if patient_kind == "NEW" and live is not None:
            await conn.execute(
                "UPDATE care_episode SET status = 'CLOSED', closed_at = now(), "
                "close_reason = 'new_problem', updated_at = now() "
                "WHERE id = $1 AND clinic_id = $2::uuid",
                live["id"],
                identity.clinic_id,
            )
            live = None

        if live is not None:
            if live["status"] == "PENDING_CLOSE":
                await conn.execute(
                    "UPDATE care_episode SET status = 'OPEN', closed_at = NULL, "
                    "close_reason = NULL, updated_at = now() "
                    "WHERE id = $1 AND clinic_id = $2::uuid",
                    live["id"],
                    identity.clinic_id,
                )
            episode_id = live["id"]
        else:
            episode_id = await conn.fetchval(
                """
                INSERT INTO care_episode (
                    clinic_id, clinic_patient_id, service_type_id,
                    opened_appointment_id, status
                )
                VALUES ($1::uuid, $2::uuid, $3::uuid, $4, 'OPEN')
                RETURNING id
                """,
                identity.clinic_id,
                clinic_patient_id,
                service_type_id,
                appointment_id,
            )

        await conn.execute(
            "UPDATE appointment SET episode_id = $2 "
            "WHERE id = $1 AND clinic_id = $3::uuid",
            appointment_id,
            episode_id,
            identity.clinic_id,
        )

    async def _open_visit(
        self,
        conn: asyncpg.Connection,
        *,
        appointment_id: Any,
        clinic_patient_id: str,
        doctor_id: str | None,
        identity: StaffIdentity,
    ) -> str | None:
        # TRẢ VỀ MÃ LƯỢT KHÁM. Trước đây trả None, nên `/luot-kham/check-in`
        # chỉ nói được "ok" và màn hình phải nạp LẠI CẢ BẢNG để biết lượt vừa
        # mở là lượt nào — một vòng mạng thừa cho mỗi lần lễ tân bấm check-in,
        # và với bảng ngày đông là vòng đắt nhất trong màn ấy.
        """Open the visit so the patient appears on the board immediately.

        ON CONFLICT rather than catching UniqueViolationError. Catching it looks
        equivalent and is not: by the time asyncpg raises, Postgres has already
        aborted the transaction, so swallowing the exception leaves a dead
        transaction whose COMMIT silently degrades to ROLLBACK. This runs LAST
        in the check-in transaction, so the status change, the queue number and
        the audit event all disappeared with it — while the API answered
        {"ok": true, "status": "CHECKED_IN"}.

        Reproduced end to end: check in, undo, check in again (undo_checkin only
        patches the appointment, so the visit row survives). The second check-in
        returned 200 and left the appointment CONFIRMED. A receptionist is told
        the patient has arrived and the patient never reaches the board.

        clinical_record_service._ensure_visit has always done it this way.

        Also instantiates the visit's work items. Both check-in paths — the
        walk-in auto-check-in in create() and the checkin action — already funnel
        through here, so hanging the kernel off this one place covers walk-ins by
        construction instead of by remembering to add a second call.
        """
        visit_id = await conn.fetchval(
            """
            INSERT INTO visit (
                clinic_id, clinic_patient_id, appointment_id,
                attending_doctor_id, status, checked_in_at, checked_in_by,
                service_type_id, location_id
            )
            -- LOẠI KHÁM ĐI THEO LỊCH (17/09/2026). Thiếu cột này thì bàn khám
            -- báo "Chưa gán dịch vụ" và không mở được đúng phiếu khám cho một
            -- lịch đã đặt Nội tiết.
            -- CƠ SỞ ĐI THEO LỊCH (24/09/2026): trước đây cột này luôn trống, nên
            -- không chỗ nào biết khách đang khám ở cơ sở nào (tự xếp phòng từng
            -- xếp sang cơ sở khác).
            VALUES ($1::uuid, $2::uuid, $3, $4::uuid, 'OPEN', now(), $5::uuid,
                    (SELECT a.service_type_id FROM appointment a
                      WHERE a.id = $3 AND a.clinic_id = $1::uuid),
                    (SELECT a.location_id FROM appointment a
                      WHERE a.id = $3 AND a.clinic_id = $1::uuid))
            ON CONFLICT (appointment_id) WHERE appointment_id IS NOT NULL
            -- CHECK-IN LẠI SAU KHI HOÀN TÁC (bắt được khi bấm thật 18/09/2026).
            -- Hoàn tác đưa lượt về INCOMPLETE (xem _close_visit_workflow); nếu
            -- ở đây DO NOTHING thì lượt cũ nằm im INCOMPLETE — khách đứng trong
            -- hàng đợi lễ tân mà màn bác sĩ (lọc OPEN/IN_PROGRESS) không bao giờ
            -- thấy. Mở lại đúng lượt ấy. Lượt đang mở hay đã ký thì không chạm.
            -- Loại khám theo LỊCH HIỆN TẠI: lịch đổi dịch vụ lúc lượt đang
            -- hoàn tác (V5, 30/09/2026) thì lượt mở lại mang loại khám mới.
            DO UPDATE SET status = 'OPEN',
                          checked_in_at = now(),
                          checked_in_by = EXCLUDED.checked_in_by,
                          service_type_id = EXCLUDED.service_type_id,
                          incomplete_at = NULL,
                          incomplete_reason = NULL,
                          incomplete_by = NULL,
                          updated_at = now()
                    WHERE visit.status = 'INCOMPLETE'
            RETURNING visit_id
            """,
            identity.clinic_id,
            clinic_patient_id,
            appointment_id,
            doctor_id,
            identity.staff_id,
        )

        if visit_id is None:
            # Somebody opened the visit first — a nurse recording vitals, a
            # sonographer. It still needs its work items.
            visit_id = await conn.fetchval(
                "SELECT visit_id FROM visit "
                "WHERE appointment_id = $1 AND clinic_id = $2::uuid",
                appointment_id,
                identity.clinic_id,
            )

        if visit_id is None:
            return None

        created = await conn.fetchval(
            "SELECT public.instantiate_visit_workflow("
            "$1::uuid, $2::uuid, $3::uuid, $4::text)",
            identity.clinic_id,
            visit_id,
            identity.staff_id,
            identity.role.value,
        )
        if not created:
            # Zero is normal on a re-check-in (the items are already there) but
            # also what a clinic with no seeded node catalogue returns, and that
            # one is worth seeing in the log rather than discovering when the
            # board is empty.
            logger.info(
                "visit_workflow_no_new_items",
                visit_id=str(visit_id),
                clinic_id=identity.clinic_id,
            )

        # LỊCH HẸN THẲNG VỚI BÁC SĨ SIÊU ÂM → VIỆC SIÊU ÂM (Tuyền chốt 15/09/2026).
        #
        # Khám bác sĩ chính xong, bác sĩ bảo "mai đến siêu âm" và thư ký đặt lịch
        # siêu âm luôn cho khách: lịch hẹn ấy CHÍNH LÀ chỉ định. Hôm sau khách
        # check-in bình thường và phải hiện ở hàng chờ siêu âm. Trước bản này
        # không gì sinh việc DICHVU-SIEUAM cho họ — chỉ `order_services` (bác sĩ
        # chỉ định trong lượt) hoặc trưởng ca chuyển bước tay, mà đường sau đã
        # đóng ở 20260915000013. ON CONFLICT: bấm check-in lần hai không nhân đôi.
        await conn.execute(
            """
            INSERT INTO work_item (
                clinic_id, node_code, node_version_id, clinic_patient_id,
                visit_id, appointment_id, status, assigned_role, assigned_to,
                priority, payload)
            SELECT v.clinic_id, n.code, nv.id, v.clinic_patient_id,
                   v.visit_id, v.appointment_id, 'PENDING', 'ULTRASOUND_DOCTOR',
                   -- Bác sĩ thực hiện = bác sĩ siêu âm khách đã đặt lịch.
                   $3::uuid,
                   n.priority, jsonb_build_object('nguon', 'lich_hen_sieu_am')
              FROM visit v
              JOIN node_definition n
                ON n.clinic_id = v.clinic_id AND n.code = 'DICHVU-SIEUAM'
               AND n.is_active
              JOIN node_definition_version nv
                ON nv.node_definition_id = n.id AND nv.version = n.current_version
             WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
               AND EXISTS (
                   SELECT 1 FROM clinic_membership m
                    WHERE m.clinic_id = v.clinic_id AND m.staff_id = $3::uuid
                      AND m.role = 'ULTRASOUND_DOCTOR' AND m.is_active)
            ON CONFLICT (clinic_id, visit_id, node_code, lan)
               WHERE visit_id IS NOT NULL AND status <> 'CANCELLED'
            DO NOTHING
            """,
            identity.clinic_id,
            visit_id,
            doctor_id,
        )

        # ĐẶT BỆNH NHÂN VÀO TRẠM ĐẦU TIÊN — mắt xích còn thiếu giữa Lễ tân và
        # bảng điều phối.
        #
        # Check-in đã tạo lượt khám và cả danh sách bước, nhưng KHÔNG đặt con
        # trỏ vị trí (`visit.current_node_code`). Đo trên prod trước thay đổi
        # này: 24 lượt khám đã check-in, con trỏ NULL ở cả 24 — nên bảng điều
        # phối không thấy ai, dù bệnh nhân đã đứng trong phòng khám.
        #
        # Hàm SQL tự bỏ qua nếu lượt đã có vị trí, nên bấm check-in lần hai
        # không kéo bệnh nhân từ phòng siêu âm về quầy sinh hiệu.
        placed = await conn.fetchval(
            "SELECT public.place_visit_at_first_station($1::uuid, $2::uuid, $3::uuid)",
            identity.clinic_id,
            visit_id,
            identity.auth_user_id,
        )
        if placed:
            logger.info(
                "visit_placed_at_first_station",
                visit_id=str(visit_id),
                clinic_id=identity.clinic_id,
            )

        # XẾP ĐƯỜNG ĐI KHÔNG LÀM Ở ĐÂY (chuẩn lego, 24/09/2026): check-in phát
        # `visit.checked_in`, khối HÀNH TRÌNH nghe rồi xếp (dây H1). Bản 23/09
        # (F2) gọi thẳng khối lượt khám từ đây — chạy đúng nhưng trái luật cắm.
        return str(visit_id)

    async def _cancel_visit_workflow(
        self,
        conn: asyncpg.Connection,
        *,
        appointment_id: Any,
        identity: StaffIdentity,
        reason: str,
    ) -> None:
        """Cancel the still-open work items of this appointment's visit.

        Completed steps stay completed: the patient really did arrive and
        really did have their vitals taken, and undoing a mis-click does not
        make that untrue.
        """
        visit_id = await conn.fetchval(
            "SELECT visit_id FROM visit "
            "WHERE appointment_id = $1 AND clinic_id = $2::uuid",
            appointment_id,
            identity.clinic_id,
        )
        if visit_id is None:
            return

        await conn.fetchval(
            "SELECT public.cancel_visit_workflow("
            "$1::uuid, $2::uuid, $3::uuid, $4::text, $5::text)",
            identity.clinic_id,
            visit_id,
            identity.staff_id,
            identity.role.value,
            reason,
        )

        # ĐÓNG LUÔN LƯỢT KHÁM, không chỉ các bước của nó.
        #
        # `cancel_visit_workflow` chỉ chạm `work_item`; `visit.status` ở lại
        # IN_PROGRESS. Bảng lượt khám lọc đúng `status IN ('OPEN','IN_PROGRESS')`
        # nên một lịch huỷ sau khi đã check-in để lại lượt MA trên màn bác sĩ
        # tới hết ngày: không bước nào làm được, không ai đóng được, và người
        # trực phải đoán xem khách còn ở đây hay đã về. Đo được 16/09/2026 —
        # 12 lượt ma sau một buổi chạy thử.
        #
        # INCOMPLETE = "khách về giữa chừng", đúng nghĩa. Bảng cố ý không hiện
        # nó. Ràng buộc `visit_incomplete_can_ly_do` bắt phải viết lý do, nên lý
        # do ghi luôn ở đây thay vì để trống cho qua chuyện.
        #
        # CHỈ đụng lượt còn mở: FINALIZED/AMENDED là hồ sơ đã ký — huỷ một lịch
        # hẹn không được phép viết lại kết luận của bác sĩ.
        await conn.execute(
            """
            UPDATE public.visit
               SET status = 'INCOMPLETE',
                   incomplete_at = now(),
                   incomplete_reason = $3,
                   incomplete_by = $4::uuid,
                   updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND status IN ('OPEN', 'IN_PROGRESS')
            """,
            identity.clinic_id,
            visit_id,
            (
                "Lễ tân hoàn tác check-in"
                if reason == "undo_checkin"
                else "Lịch hẹn bị huỷ sau khi khách đã check-in"
            ),
            identity.staff_id,
        )

        # KHÁCH KHÔNG CÒN Ở ĐÂY → RA KHỎI HÀNG CHỜ (23/09/2026). Từ khi đường đi
        # được xếp ngay lúc check-in, hoàn tác mà không đóng hàng thì khách vẫn
        # "đang chờ" bác sĩ, bị đếm vào số người chờ của phòng. Người đang được
        # phục vụ (serving) thì không đụng. Bác sĩ chưa bắt đầu phiên nào thì xoá
        # luôn đường đi, để check-in lại được xếp đường đi từ đầu.
        await conn.execute(
            """
            UPDATE public.queue_entry
               SET status = 'cancelled', updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND status IN ('blocked', 'waiting', 'called')
            """,
            identity.clinic_id,
            visit_id,
        )
        await conn.execute(
            """
            UPDATE public.encounter_flow f
               SET route_decision = NULL, route_decided_at = NULL,
                   route_reason = NULL, version = f.version + 1, updated_at = now()
             WHERE f.clinic_id = $1::uuid AND f.visit_id = $2::uuid
               AND f.route_decision IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1 FROM public.consultation c
                    WHERE c.clinic_id = f.clinic_id AND c.visit_id = f.visit_id
                      AND c.status <> 'queued')
            """,
            identity.clinic_id,
            visit_id,
        )

    def _is_today(self, moment: datetime) -> bool:
        local = moment.astimezone(CLINIC_TZ).date()
        return local == datetime.now(CLINIC_TZ).date()


async def _phat_su_kien_lich(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    action: str,
    appt: asyncpg.Record,
    patch: dict[str, Any],
    ly_do: str | None,
    ly_do_huy_ma: str | None,
) -> None:
    """Sự kiện nghiệp vụ của lịch hẹn (nhóm 3, 24/09/2026) — cùng giao dịch.

    Đổi lịch LƯU LỊCH SỬ (Tuyền chốt): mỗi lần một dòng `appointment_doi_lich`
    từ → đến, ai đổi, lý do. Trước đây `slot_start` bị ghi đè, mất giờ cũ.
    """
    aid = str(appt["id"])
    boi = nguoi(identity)
    if action == "reschedule":
        den_bat_dau = patch.get("slot_start", appt["slot_start"])
        den_bac_si = patch["doctor_id"] if "doctor_id" in patch else appt["doctor_id"]
        await conn.execute(
            """
            INSERT INTO appointment_doi_lich
                (clinic_id, appointment_id, tu_bat_dau, tu_ket_thuc, den_bat_dau,
                 den_ket_thuc, tu_bac_si_id, den_bac_si_id, ly_do, doi_boi_staff_id)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::uuid, $8::uuid, $9,
                    $10::uuid)
            """,
            identity.clinic_id,
            aid,
            appt["slot_start"],
            appt["slot_end"],
            den_bat_dau,
            patch.get("slot_end", appt["slot_end"]),
            appt["doctor_id"],
            den_bac_si,
            (ly_do or "").strip() or None,
            identity.staff_id,
        )
        await emit_event(
            conn,
            ten="appointment.rescheduled",
            clinic_id=identity.clinic_id,
            aggregate_id=aid,
            payload=LichDaDoi(
                appointment_id=aid,
                tu_bat_dau=appt["slot_start"].isoformat()
                if appt["slot_start"]
                else None,
                den_bat_dau=den_bat_dau.isoformat() if den_bat_dau else None,
                doi_bac_si=str(den_bac_si or "") != str(appt["doctor_id"] or ""),
            ),
            boi=boi,
        )
    elif action == "cancel":
        await emit_event(
            conn,
            ten="appointment.cancelled",
            clinic_id=identity.clinic_id,
            aggregate_id=aid,
            payload=LichDaHuy(appointment_id=aid, ly_do_ma=ly_do_huy_ma),
            boi=boi,
        )
    elif action == "no_show":
        await emit_event(
            conn,
            ten="appointment.no_show",
            clinic_id=identity.clinic_id,
            aggregate_id=aid,
            payload=KhachKhongDen(appointment_id=aid),
            boi=boi,
        )
    elif action == "cskh_confirm":
        await emit_event(
            conn,
            ten="appointment.confirmed_by_call",
            clinic_id=identity.clinic_id,
            aggregate_id=aid,
            payload=CskhDaGoiXacNhan(appointment_id=aid),
            boi=boi,
        )


async def _log(
    conn: asyncpg.Connection,
    *,
    event_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    identity: StaffIdentity,
    origin: str,
) -> None:
    await conn.execute(
        """
        INSERT INTO event_log
            (clinic_id, event_type, aggregate_type, aggregate_id, payload,
             metadata, source, event_published)
        VALUES ($1::uuid, $2, 'appointment', $3, $4, $5, $6, FALSE)
        """,
        identity.clinic_id,
        event_type,
        aggregate_id,
        json.dumps(payload),
        json.dumps(
            {
                "clinic_role": identity.role.value,
                # Vai tài khoản gốc (vai dùng có thể khác).
                "vai_tai_khoan": identity.vai_goc.value,
                "clinic_staff_id": identity.staff_id,
                "actor_auth_user_id": identity.auth_user_id,
                "origin": origin,
            }
        ),
        origin,
    )


async def _co_so_lich(
    conn: asyncpg.Connection, appointment_id: str, identity: StaffIdentity
) -> str | None:
    """Cơ sở của lịch hẹn đang sửa — ca trực phải ở ĐÚNG cơ sở ấy, không phải
    cơ sở người bấm đang đứng. Lịch chưa có cơ sở thì lấy của người bấm."""
    loc = await conn.fetchval(
        "SELECT location_id::text FROM appointment"
        " WHERE id = $1::uuid AND clinic_id = $2::uuid",
        appointment_id,
        identity.clinic_id,
    )
    return loc or identity.location_id or None
