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
from clinicai.api.identity import DOCTOR_DESK_ROLES, ClinicRole, StaffIdentity
from clinicai.core.clock import CLINIC_TZ as _CLINIC_TZ
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.shifts import (
    MORNING_END_MIN,
    covers,
    describe,
    merge_windows,
    shift_window,
)
from clinicai.services.clinic_policy import ClinicPolicy, load_effective_policy
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

# Statuses that no longer hold a seat.
DEAD_STATUSES: frozenset[str] = frozenset({"CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"})

Action = Literal[
    "confirm",
    "decline",
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
    {ClinicRole.CSKH, ClinicRole.MANAGEMENT, ClinicRole.TRUONG_CA}
)
#: owner_only chỉ so staff_id với người CÓ ca của mình — tức bác sĩ thật.
PHYSICIAN_ONLY_OWNER_CHECK: frozenset[ClinicRole] = frozenset(
    {ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR}
)
CHECKIN_ROLES: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.RECEPTION,
        ClinicRole.MANAGEMENT,
        # CSKH check-in được (Quang 08/08/2026): *"sản phẩm MVP này là cskh
        # thao tác được hết mà"*. Đi ĐÚNG đường thật — _check_in + _open_visit —
        # chứ không phải một cờ riêng chỉ màn CSKH nhìn thấy: khách mà CSKH
        # check-in phải hiện ở hàng đợi tiếp nhận y như khách lễ tân check-in.
        ClinicRole.CSKH,
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


_ALIVE = frozenset({"SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN"})
_PRE_ARRIVAL = frozenset({"SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"})
# SCHEDULED và CSKH_CONFIRMED là TRẠNG THÁI CŨ, không phải trạng thái chết.
# Lịch hẹn mới vào thẳng CONFIRMED (xem create()), nhưng prod còn 23 dòng
# SCHEDULED + 2 dòng CSKH_CONFIRMED đặt từ trước, và chúng vẫn phải khám được,
# đổi được, huỷ được. Xoá khỏi các tập này là làm 25 lịch hẹn thật kẹt cứng.
_AWAITING_DOCTOR = frozenset({"SCHEDULED", "CSKH_CONFIRMED"})
# Bác sĩ TỪ CHỐI được cả lịch đã chắc. Nhận thì không: lịch mới sinh ra đã
# CONFIRMED rồi, "nhận" thêm lần nữa chỉ đẻ ra một event không nói thêm gì.
_DECLINABLE = _AWAITING_DOCTOR | {"CONFIRMED"}

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


TRANSITIONS: dict[str, Transition] = {
    # The doctor takes the case, even one CSKH already confirmed with the
    # patient — confirmation is two-step and these are the second step.
    "confirm": Transition(
        "CONFIRMED", _AWAITING_DOCTOR, DOCTOR_ROLES, "appointment.confirmed", True
    ),
    # Declining keeps doctor_id for history and surfaces to CSKH for reassignment.
    "decline": Transition(
        "DOCTOR_DECLINED", _DECLINABLE, DOCTOR_ROLES, "appointment.declined", True
    ),
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
        "CHECKED_IN", _PRE_ARRIVAL, CHECKIN_ROLES, "appointment.checked_in"
    ),
    "undo_checkin": Transition(
        "CONFIRMED",
        frozenset({"CHECKED_IN"}),
        CHECKIN_ROLES,
        "appointment.checkin_undone",
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
    ),
    "cancel": Transition("CANCELLED", _ALIVE, MANAGE_ROLES, "appointment.cancelled"),
    "no_show": Transition(
        "NO_SHOW", _PRE_ARRIVAL, CHECKIN_ROLES, "appointment.no_show"
    ),
    # Bác sĩ từ chối thì lịch quay lại hàng chờ — và quay lại ở trạng thái CHẮC,
    # vì thoả thuận với bệnh nhân không mất đi khi một bác sĩ bận. Đổi bác sĩ là
    # việc nội bộ, không phải lý do gọi lại bệnh nhân để xác nhận lần nữa.
    "reassign": Transition(
        "CONFIRMED",
        frozenset({"DOCTOR_DECLINED"}),
        MANAGE_ROLES,
        "appointment.reassigned",
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
    ),
    # Rescheduling keeps whatever status the appointment already had.
    "reschedule": Transition(
        KEEP_STATUS, _ALIVE, MANAGE_ROLES, "appointment.rescheduled"
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
    ) -> dict[str, Any]:
        """Book one appointment. Returns its id and the status it landed in."""
        # Không nói cơ sở thì lấy cơ sở CỦA NGƯỜI ĐẶT, không phải cơ sở đầu tiên
        # trong một danh sách. _validate_booking_refs vẫn kiểm nó thuộc đúng
        # phòng khám, nên chỉ định cơ sở khác vẫn được — chỉ là phải cố ý.
        location_id = location_id or identity.location_id
        if slot_end <= slot_start:
            raise ValidationError("Giờ kết thúc phải sau giờ bắt đầu")
        _chan_dat_vao_qua_khu(slot_end)

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
                        conn, doctor_id, slot_start, identity
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
                            need_sono, is_walkin, notes
                        )
                        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid,
                                $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
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
                        (queue_number or "").strip() or None,
                        status,
                        kind,
                        thanh,
                        sono,
                        need_sono,
                        # is_walkin mirrors booking_channel; the CHECK added in
                        # 20260803000004 rejects the write if they disagree.
                        is_walkin(channel),
                        (notes or "").strip() or None,
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
                        },
                        identity=identity,
                        origin="api:appointment-walkin-autocheckin",
                    )
                    await self._open_visit(
                        conn,
                        appointment_id=appointment_id,
                        clinic_patient_id=clinic_patient_id,
                        doctor_id=doctor_id,
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
    ) -> dict[str, Any]:
        """Run one lifecycle action. Returns the resulting status."""
        transition = resolve_action(action)

        if identity.role not in transition.allowed_roles:
            raise SafetyGateError(
                f"Vai trò của bạn không được phép '{action}' lịch hẹn"
            )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                appt = await conn.fetchrow(
                    """
                    SELECT
                        a.id, a.doctor_id, a.status, a.clinic_patient_id,
                        a.slot_start, a.slot_end, a.queue_number,
                        a.booking_channel,
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
                    raise ValidationError(
                        "Bệnh nhân của lịch hẹn không thuộc phòng khám này"
                    )
                if not appt["location_in_clinic"]:
                    raise ValidationError(
                        "Cơ sở của lịch hẹn không thuộc phòng khám này"
                    )
                if not appt["service_in_clinic"]:
                    raise ValidationError(
                        "Dịch vụ của lịch hẹn không thuộc phòng khám này"
                    )
                repairs_doctor = action in {"cancel", "reassign"} or (
                    action == "reschedule" and doctor_id_provided
                )
                if not appt["doctor_in_clinic"] and not repairs_doctor:
                    raise ValidationError(
                        "Bác sĩ của lịch hẹn không thuộc phòng khám này"
                    )

                # "Ca của chính mình" là luật GIỮA CÁC BÁC SĨ — ngăn bác sĩ
                # này đóng ca của bác sĩ kia. Người không phải bác sĩ (TKYK
                # nhập hộ, nhóm vận hành đóng lượt trong MVP tay) không có "ca
                # của mình" để so; so staff_id với họ chỉ chặn sạch mọi thứ —
                # đo được trên bản thật: Quản lý bấm check-out ăn ngay
                # "Lịch hẹn này không thuộc bác sĩ".
                if (
                    transition.owner_only
                    and identity.role in PHYSICIAN_ONLY_OWNER_CHECK
                    and str(appt["doctor_id"] or "") != identity.staff_id
                ):
                    raise SafetyGateError("Lịch hẹn này không thuộc bác sĩ")

                if appt["status"] not in transition.from_statuses:
                    raise ConflictError(
                        f"Lịch hẹn đang ở trạng thái {appt['status']}, "
                        "không thể thực hiện."
                    )

                new_status = (
                    appt["status"]
                    if transition.to_status == KEEP_STATUS
                    else transition.to_status
                )
                effective_doctor_id = (
                    str(appt["doctor_id"]) if appt["doctor_id"] else None
                )

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
                    )
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
                    raise ConflictError(
                        "Lịch hẹn vừa được người khác cập nhật, hãy tải lại."
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
                    },
                    identity=identity,
                    origin=f"api:appointment-{action}",
                )

                if action == "checkin":
                    await self._open_visit(
                        conn,
                        appointment_id=appointment_id,
                        clinic_patient_id=str(appt["clinic_patient_id"]),
                        doctor_id=effective_doctor_id,
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
        if appt["doctor_id"] is None and effective_doctor_id:
            await self._bao_cskh_da_co_bac_si(
                appointment_id=appointment_id,
                doctor_id=effective_doctor_id,
                identity=identity,
            )

        logger.info(
            "appointment_action",
            appointment_id=appointment_id,
            action=action,
            status=new_status,
            by_staff_id=identity.staff_id,
        )
        return {"status": new_status}

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

        1.  CA nào — lấy theo giờ của CHÍNH lịch hẹn, mốc 12:00 dùng chung với
            `core.shifts.MORNING_END_MIN` (mốc ấy là quyết định của phòng khám,
            và nó chỉ được nằm ở một chỗ). Xếp cả ngày cho một lịch 18:00 là tự
            ý tuyên bố bác sĩ đi làm từ sáng.
        2.  TRẠM là `LICH_KHAM` — "Lịch khám (Bác sĩ)" trong `lib/roster.ts`, và
            là trạm màn Đặt lịch đọc để liệt kê bác sĩ khám.
        3.  KHÔNG áp dụng tuần. Thêm một dòng trực khác hẳn với việc chốt cả
            tuần; `roster_week` vẫn là chữ ký của quản lý, và `capacity_service`
            đọc nó để phân biệt "chưa xếp" với "nghỉ". Tự áp hộ ở đây là thay
            quản lý tuyên bố những ngày còn lại của tuần không ai đi làm.

        KHÔNG GHI ĐÈ, KHÔNG NHÂN BẢN: đã có dòng APPROVED phủ ca ấy (FULL hoặc
        đúng ca) thì thôi.
        """
        cuc_bo = slot_start.astimezone(CLINIC_TZ)
        ngay = cuc_bo.date()
        ca = "SANG" if cuc_bo.hour * 60 + cuc_bo.minute < MORNING_END_MIN else "CHIEU"

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
                duong_dan=f"/customers?selected={row['kh_id']}",
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
            patch["slot_start"] = slot_start
            patch["slot_end"] = slot_end
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
                channel=appt["booking_channel"],
                exclude_id=str(appt["id"]),
                identity=identity,
            )

        return patch

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
    ) -> None:
        if doctor_id:
            await self._validate_doctor_ref(conn, doctor_id, identity.clinic_id)
            busy = await self._doctor_conflict(
                conn, doctor_id, slot_start, slot_end, identity, exclude_id
            )
            if busy:
                raise ConflictError(busy)
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
    ) -> str | None:
        """Câu cảnh báo nếu bác sĩ không có ca trực hôm đó; None nếu ổn.

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
              EXISTS (
                SELECT 1 FROM work_roster
                 WHERE clinic_id = $1::uuid AND work_date = $2
                   AND status = 'APPROVED'
                   AND EXISTS (
                     SELECT 1 FROM roster_week rw
                      WHERE rw.clinic_id = work_roster.clinic_id
                        AND rw.week_start = work_roster.week_start
                   )
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
              ), ARRAY[]::text[]) AS shifts,
              (SELECT open_minute FROM clinic_hours_for_date($1::uuid, $2))
                AS open_minute,
              (SELECT close_minute FROM clinic_hours_for_date($1::uuid, $2))
                AS close_minute
            """,
            identity.clinic_id,
            work_date,
            doctor_id,
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

        # CÓ TÊN TRONG NGÀY VẪN CÓ THỂ SAI GIỜ. Ca sáng không phải cả ngày; mốc
        # 12:00 là quyết định của phòng khám, khai ở core/shifts.py.
        open_min, close_min = row["open_minute"], row["close_minute"]
        if open_min is None or close_min is None:
            return None
        windows = merge_windows(
            [
                w
                for s in shifts
                if (w := shift_window(s, open_min, close_min)) is not None
            ]
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
    ) -> None:
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
                attending_doctor_id, status, checked_in_at, checked_in_by
            )
            VALUES ($1::uuid, $2::uuid, $3, $4::uuid, 'OPEN', now(), $5::uuid)
            ON CONFLICT (appointment_id) WHERE appointment_id IS NOT NULL
            DO NOTHING
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
            return

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

    def _is_today(self, moment: datetime) -> bool:
        local = moment.astimezone(CLINIC_TZ).date()
        return local == datetime.now(CLINIC_TZ).date()


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
                "clinic_staff_id": identity.staff_id,
                "actor_auth_user_id": identity.auth_user_id,
                "origin": origin,
            }
        ),
        origin,
    )
