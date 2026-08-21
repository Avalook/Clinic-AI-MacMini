"""Clinic configuration: the staff roster and the price list (W5, ADR-0012).

Ports the last two routes that built a service-role client inline:
``app/api/roster`` and ``app/api/service-price``.

ROSTER. Management schedules anybody; everyone else may only sign themselves up
and may only remove their own shift. That is enforced by ignoring the client's
``staff_id`` unless the caller is management, rather than by validating it —
there is nothing to spoof if the value is never read.

Self-registered shifts land PENDING and do not appear on the shared rota until
management approves them. Management's own entries are APPROVED immediately,
because the approval exists to stop staff writing themselves onto the schedule,
not to make managers approve themselves.

``week_start`` is computed from ``work_date`` and never taken from the client.
The form keeps the previously viewed week in state, so a client-supplied value
silently filed shifts under the wrong week.

PRICES. Cashiers, the shift lead and management maintain the list. Prices are
whole dong — no fractional currency — and a duplicate service code is a 409
rather than a second row nobody notices.
"""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from typing import Any, Literal

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.shifts import (
    CAC_CA,
    ca_tu_settings,
    covers,
    merge_windows,
    shift_windows,
)

logger = structlog.get_logger()


ROSTER_ADMIN_ROLES: frozenset[ClinicRole] = frozenset({ClinicRole.MANAGEMENT})

# LUỒNG TỰ ĐĂNG KÝ CA ĐANG ĐÓNG (Quang, 07/08/2026): quản lý tự xếp lịch cho
# mọi người rồi bấm áp dụng; nhân viên chỉ xem. Đây là ĐÓNG chứ không phải bỏ —
# bảng đăng ký và luồng duyệt vẫn còn nguyên để mở lại khi cần đường xin đổi ca.
#
# Phải siết ở ĐÂY chứ không chỉ ẩn bảng ngoài giao diện. Ẩn nút mà để nguyên
# đường ghi thì bất kỳ ai cũng còn POST thẳng vào /api/v1/roster/shifts được, và
# ca họ ghi rơi vào PENDING — vô hình với cả người xếp lịch (lưới sửa chỉ đọc
# APPROVED) lẫn màn chính thức. Treo vĩnh viễn, không ai thấy.
ROSTER_ROLES: frozenset[ClinicRole] = ROSTER_ADMIN_ROLES
PRICE_ROLES: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.CASHIER,
        ClinicRole.CASHIER_THUOC,
        ClinicRole.CASHIER_DV,
        ClinicRole.TRUONG_CA,
        ClinicRole.MANAGEMENT,
    }
)

#: Bốn nhãn ca. Giờ của từng ca do phòng khám khai — xem `core/shifts.py`.
Shift = Literal["SANG", "CHIEU", "TOI", "FULL"]
RosterDecision = Literal["approve", "reject"]
PriceGroup = Literal["thuoc", "dich_vu"]


def week_start_of(work_date: date) -> date:
    """The Monday of that date's week.

    Derived, never accepted from the client: the schedule form keeps the week
    the user was last looking at, so a posted week_start filed shifts under a
    week they were not editing.
    """
    return work_date - timedelta(days=work_date.weekday())


def parse_price(raw: Any) -> int | None:
    """A whole number of dong, or None for blank. Raises on nonsense.

    Returning None for "not set" and raising for "-5" keeps the two apart; the
    route conflated them behind a single undefined.
    """
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        raise ValidationError("Đơn giá không hợp lệ")
    try:
        number = float(raw)
    except (TypeError, ValueError):
        raise ValidationError("Đơn giá không hợp lệ") from None
    if not math.isfinite(number) or number < 0:
        raise ValidationError("Đơn giá không hợp lệ")
    return round(number)


class RosterService:
    """Sign up for shifts, approve them, remove them."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add_shift(
        self,
        *,
        work_date: date,
        station: str,
        shift: str,
        identity: StaffIdentity,
        staff_id: str | None = None,
        staff_name: str | None = None,
        sort: int = 0,
    ) -> str:
        """Add one roster cell. Returns its id."""
        station = (station or "").strip()
        if not station:
            raise ValidationError("Thiếu vị trí")

        is_admin = identity.role in ROSTER_ADMIN_ROLES
        # Only management may name somebody else. For everyone else the client's
        # value is ignored entirely rather than checked.
        assigning_other = is_admin and bool(staff_id)
        target_id = staff_id if assigning_other else identity.staff_id
        if not target_id:
            raise ValidationError("Thiếu nhân viên")

        async with self._pool.acquire() as conn:
            # TÊN VÀ CHỨC DANH LẤY TỪ DATABASE, KHÔNG TỪ TRÌNH DUYỆT.
            #
            # `staff_name` trước đây đi thẳng từ client vào bảng. Nghĩa là một
            # lời gọi API tự chế ghi được "Giám đốc Sở Y tế" vào lịch trực, và
            # nó sẽ hiện y như vậy trên màn của cả phòng khám. Cùng lúc, câu
            # truy vấn này là chỗ duy nhất kiểm được người được xếp có THUỘC
            # phòng khám này không — trước đây không kiểm.
            nv = await conn.fetchrow(
                """
                SELECT s.full_name, s.primary_department
                  FROM public.staff s
                  JOIN public.clinic_membership m
                    ON m.staff_id = s.id AND m.is_active
                 WHERE s.id = $1::uuid AND m.clinic_id = $2::uuid AND s.is_active
                """,
                target_id,
                identity.clinic_id,
            )
            if nv is None:
                raise ValidationError(
                    "Không tìm thấy nhân viên đang làm việc ở phòng khám này."
                )
            target_name = nv["full_name"]
            await self._kiem_pham_vi_tram(
                conn,
                clinic_id=identity.clinic_id,
                station=station,
                vai=nv["primary_department"],
                ten=target_name,
            )

            row_id = await conn.fetchval(
                """
                INSERT INTO work_roster (
                    clinic_id, week_start, work_date, shift, station,
                    staff_id, staff_name, sort, status
                )
                VALUES ($1::uuid, $2, $3, $4, $5, $6::uuid, $7, $8, $9)
                RETURNING id
                """,
                identity.clinic_id,
                week_start_of(work_date),
                work_date,
                shift if shift in CAC_CA else "FULL",
                station,
                target_id,
                target_name,
                sort,
                "APPROVED" if is_admin else "PENDING",
            )

            # CA MỚI VÀO MÀ CÓ LỊCH ĐANG CHỜ XẾP BÁC SĨ → BÁO CSKH (câu hỏi
            # của Đặng Dương 17/08/2026: "có cơ chế thông báo tự động cho CSKH
            # khi lịch làm việc của bác sĩ được cập nhật không?"). Màn hình đã
            # tự tươi qua realtime, nhưng màn chỉ nói với người ĐANG NHÌN —
            # tin Telegram mới gọi được người đang làm việc khác quay lại xếp.
            # Chỉ ca ĐÃ DUYỆT: đăng ký PENDING chưa phải ca trực.
            if station == "LICH_KHAM" and is_admin:
                await self._bao_lich_cho_xep(
                    conn,
                    roster_id=str(row_id),
                    work_date=work_date,
                    shift=shift if shift in CAC_CA else "FULL",
                    ten_bac_si=target_name,
                    identity=identity,
                )

        logger.info(
            "roster_shift_added",
            roster_id=str(row_id),
            self_service=not assigning_other,
            by_staff_id=identity.staff_id,
        )
        return str(row_id)

    async def _bao_lich_cho_xep(
        self,
        conn: asyncpg.Connection,
        *,
        roster_id: str,
        work_date: date,
        shift: str,
        ten_bac_si: str,
        identity: StaffIdentity,
    ) -> None:
        """Đếm lịch CHỜ-XẾP-BÁC-SĨ rơi vào khung ca vừa thêm, có thì ghi sự
        kiện cho relay đưa tin. Best-effort có chủ ý: đếm/ghi tin hỏng không
        được làm hỏng cú xếp ca — ca trực là việc chính, tin là việc phụ."""
        try:
            gio_mo = await conn.fetchrow(
                "SELECT open_minute, close_minute, "
                "       (SELECT settings FROM clinic WHERE id = $1::uuid) "
                "         AS settings "
                "FROM clinic_hours_for_date($1::uuid, $2)",
                identity.clinic_id,
                work_date,
            )
            if gio_mo is None or gio_mo["open_minute"] is None:
                return
            ca = ca_tu_settings((gio_mo["settings"]))
            khung = shift_windows(
                shift, gio_mo["open_minute"], gio_mo["close_minute"], ca
            )
            if not khung:
                return
            cho_xep = await conn.fetch(
                """
                SELECT to_char(slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh',
                               'HH24:MI') AS gio,
                       (EXTRACT(HOUR FROM slot_start
                                AT TIME ZONE 'Asia/Ho_Chi_Minh') * 60
                      + EXTRACT(MINUTE FROM slot_start
                                AT TIME ZONE 'Asia/Ho_Chi_Minh'))::int AS phut
                  FROM public.appointment
                 WHERE clinic_id = $1::uuid
                   AND doctor_id IS NULL
                   AND (slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = $2
                   AND slot_start > now()
                   AND status IN ('SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED')
                 ORDER BY slot_start
                """,
                identity.clinic_id,
                work_date,
            )
            trong_ca = [r for r in cho_xep if covers(khung, r["phut"])]
            if not trong_ca:
                return
            await conn.execute(
                """
                INSERT INTO public.event_log
                    (clinic_id, event_type, aggregate_type, aggregate_id,
                     payload, metadata, source, event_published)
                VALUES ($1::uuid, 'roster.shift_added_cho_xep', 'work_roster',
                        $2::uuid, $3::jsonb, $4::jsonb, 'api:roster', FALSE)
                """,
                identity.clinic_id,
                roster_id,
                json.dumps(
                    {
                        "ten_bac_si": ten_bac_si,
                        "ngay": work_date.strftime("%d/%m"),
                        "ca": shift,
                        "so_lich": len(trong_ca),
                        "gio": [r["gio"] for r in trong_ca][:6],
                    }
                ),
                json.dumps(
                    {
                        "clinic_role": identity.role.value,
                        "clinic_staff_id": identity.staff_id,
                        "origin": "api:roster",
                    }
                ),
            )
        except Exception:
            logger.exception("bao_lich_cho_xep_failed")

    async def _kiem_pham_vi_tram(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        station: str,
        vai: str | None,
        ten: str,
    ) -> None:
        """Chức danh này có được xếp vào vị trí đó không (bảng vai_duoc_vao_tram).

        Quang, 08/08/2026: *"lễ tân chỉ chọn được vị trí của lễ tân, không vào
        bác sĩ được."* Lọc ở trình duyệt là chưa đủ — một lời gọi API tự chế
        không đi qua trình duyệt.
        """
        # Màn hình phòng chờ là cái tivi treo tường, không phải người. Nó chưa
        # bao giờ có trong ma trận nên nhánh fail-open dưới đây sẽ cho nó qua.
        if vai == ClinicRole.DISPLAY.value:
            raise ValidationError("Màn hình phòng chờ không phải nhân sự để xếp ca.")

        rows = await conn.fetch(
            "SELECT tram_ma FROM public.vai_duoc_vao_tram "
            " WHERE clinic_id = $1::uuid AND vai = $2 AND is_active",
            clinic_id,
            vai,
        )
        # CHƯA KHAI THÌ CHO QUA, có ghi log.
        #
        # Phòng khám mới cài đặt chưa có dòng nào trong ma trận. Chặn hết ở đó
        # nghĩa là màn xếp lịch chết câm ngay ngày đầu, và người dùng không có
        # cách nào tự gỡ. Bỏ sót một ca xếp nhầm nhẹ hơn nhiều.
        if not rows:
            logger.warning(
                "roster_station_scope_empty",
                clinic_id=clinic_id,
                vai=vai,
                station=station,
            )
            return

        hop_le = {r["tram_ma"] for r in rows}
        if station not in hop_le:
            raise ValidationError(
                f"{ten} không được xếp vào vị trí này. "
                f"Vị trí hợp lệ: {', '.join(sorted(hop_le))}."
            )

    async def tram_cho_nhan_vien(
        self, *, identity: StaffIdentity, staff_id: str
    ) -> dict[str, Any]:
        """Danh sách mã vị trí mà nhân viên này được xếp vào.

        Màn xếp lịch gọi cái này để dựng ô "Vị trí" — cùng một nguồn với chỗ
        thi hành, nên giao diện không thể hứa một đằng rồi backend từ chối một
        nẻo.
        """
        async with self._pool.acquire() as conn:
            nv = await conn.fetchrow(
                """
                SELECT s.full_name, s.primary_department
                  FROM public.staff s
                  JOIN public.clinic_membership m
                    ON m.staff_id = s.id AND m.is_active
                 WHERE s.id = $1::uuid AND m.clinic_id = $2::uuid AND s.is_active
                """,
                staff_id,
                identity.clinic_id,
            )
            if nv is None:
                raise NotFoundError("Không tìm thấy nhân viên này.")
            rows = await conn.fetch(
                "SELECT tram_ma FROM public.vai_duoc_vao_tram "
                " WHERE clinic_id = $1::uuid AND vai = $2 AND is_active "
                " ORDER BY tram_ma",
                identity.clinic_id,
                nv["primary_department"],
            )
        return {
            "vai": nv["primary_department"],
            # `chua_khai` nói thẳng "phòng khám chưa cấu hình" thay vì để giao
            # diện đọc danh sách rỗng thành "người này không làm được gì".
            "chua_khai": not rows,
            "tram": [r["tram_ma"] for r in rows],
        }

    async def ma_tran_vi_tri(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        """Cả ma trận vai × vị trí, cho màn cấu hình của quản lý."""
        rows = await self._pool.fetch(
            "SELECT tram_ma, vai, is_active, ghi_chu "
            "  FROM public.vai_duoc_vao_tram WHERE clinic_id = $1::uuid "
            " ORDER BY tram_ma, vai",
            identity.clinic_id,
        )
        return [dict(r) for r in rows]

    async def dat_vi_tri_cho_vai(
        self, *, identity: StaffIdentity, tram_ma: str, vai: str, cho_phep: bool
    ) -> dict[str, Any]:
        """Bật/tắt một ô của ma trận.

        Không xoá dòng khi tắt: một ô từng bật rồi tắt là một QUYẾT ĐỊNH, và
        xoá nó đi thì lần rà sau sẽ có người bật lại rồi ngạc nhiên vì sao
        trước đó không có.
        """
        if identity.role not in ROSTER_ADMIN_ROLES:
            raise SafetyGateError("Chỉ quản lý được sửa phạm vi vị trí.")
        tram_ma = (tram_ma or "").strip()
        vai = (vai or "").strip()
        if not tram_ma or not vai:
            raise ValidationError("Thiếu vị trí hoặc chức danh.")
        if vai == ClinicRole.DISPLAY.value:
            raise ValidationError("Màn hình phòng chờ không phải nhân sự để xếp ca.")
        await self._pool.execute(
            """
            INSERT INTO public.vai_duoc_vao_tram
                (clinic_id, tram_ma, vai, is_active, ghi_chu)
            VALUES ($1::uuid, $2, $3, $4, 'quản lý đặt tay')
            ON CONFLICT (clinic_id, tram_ma, vai)
            DO UPDATE SET is_active = EXCLUDED.is_active,
                          ghi_chu   = EXCLUDED.ghi_chu
            """,
            identity.clinic_id,
            tram_ma,
            vai,
            cho_phep,
        )
        logger.info(
            "roster_station_scope_set",
            tram_ma=tram_ma,
            vai=vai,
            cho_phep=cho_phep,
            by_staff_id=identity.staff_id,
        )
        return {"ok": True}

    async def decide(
        self,
        *,
        roster_id: str,
        decision: RosterDecision,
        reason: str | None,
        identity: StaffIdentity,
    ) -> None:
        """Approve or reject a self-registered shift. Management only."""
        if identity.role not in ROSTER_ADMIN_ROLES:
            raise SafetyGateError("Chỉ quản lý được duyệt ca")

        status = "APPROVED" if decision == "approve" else "REJECTED"
        # Approving clears any earlier rejection reason, in case a manager
        # changed their mind about a shift they had turned down.
        reject_reason = (reason or "").strip() or None if status == "REJECTED" else None

        async with self._pool.acquire() as conn:
            updated = await conn.fetchval(
                """
                UPDATE work_roster
                   SET status = $3, reject_reason = $4, updated_at = now()
                 WHERE id = $1::uuid AND clinic_id = $2::uuid
                RETURNING id
                """,
                roster_id,
                identity.clinic_id,
                status,
                reject_reason,
            )
        if updated is None:
            raise NotFoundError("Không tìm thấy ca trực")

    async def remove(
        self, *, roster_id: str, identity: StaffIdentity, dry_run: bool = False
    ) -> dict[str, Any]:
        """Gỡ một ca trực — và HUỶ những lịch hẹn KHÔNG CÒN KHUNG NÀO PHỦ.

        Tuyền chốt 14/08: gỡ ca thì lịch của ca ấy phải có kết thúc (huỷ hẳn,
        mã BAC_SI_DOI_LICH — xem #117). 17/08 Tuyền bắt tiếp cái tinh hơn:
        "xoá ca sáng để thêm cả ngày thì sao — về bản chất bác sĩ vẫn khám".
        Bản cũ hỏi thô "còn ca nào TRONG NGÀY không" nên sai cả hai chiều:

          · xoá SÁNG khi còn CHIỀU → không huỷ gì — lịch buổi sáng SỐNG SÓT
            MỒ CÔI dưới tên một bác sĩ sáng đó không đến, và cờ mất-bác-sĩ
            (cũng dò theo ngày) không hề kêu;
          · xoá SÁNG rồi thêm CẢ NGÀY → lịch sáng bị huỷ oan trước khi ca mới
            kịp vào.

        Nay: huỷ theo KHUNG GIỜ — chỉ những lịch mà giờ hẹn rơi RA NGOÀI hợp
        các ca còn lại của chính bác sĩ ấy hôm đó (cùng thước đo core/shifts
        với đường đặt lịch). Hệ quả tự nhiên: muốn đổi sáng→cả ngày thì THÊM
        ca mới TRƯỚC rồi xoá ca cũ — mọi lịch nằm trong khung còn phủ được
        giữ nguyên, không cần cơ chế hồi sinh nào.

        `dry_run=True`: đo mà không cắt — trả về số lịch SẼ huỷ (kèm giờ) để
        màn hình hỏi lại người xoá trước khi làm thật. Đây đúng chỗ xứng đáng
        có hộp xác nhận: cái giá là lịch hẹn của khách, không lấy lại được —
        ngược với hoàn tác rẻ tiền đã bỏ hộp (10/08).

        CHỈ LỊCH CÒN CỨU ĐƯỢC (chưa tới giờ, chưa check-in) và NHỚ NGƯỜI BỊ
        GỠ (`bac_si_da_go_id`) — như cũ, xem #117.
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT staff_id, work_date, station FROM work_roster "
                    "WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    roster_id,
                    identity.clinic_id,
                )
                if row is None:
                    raise NotFoundError("Không tìm thấy ca trực")

                if identity.role not in ROSTER_ADMIN_ROLES and (
                    str(row["staff_id"] or "") != identity.staff_id
                ):
                    raise SafetyGateError("Chỉ được xoá ca của chính mình")

                if not dry_run:
                    await conn.execute(
                        "DELETE FROM work_roster "
                        "WHERE id = $1::uuid AND clinic_id = $2::uuid",
                        roster_id,
                        identity.clinic_id,
                    )

                if row["station"] != "LICH_KHAM" or row["staff_id"] is None:
                    return {"so_lich_huy": 0, "gio": []}

                # HỢP CÁC CA CÒN LẠI của bác sĩ hôm đó — loại trừ chính ca đang
                # xoá (dry_run chưa xoá thật nên phải tự loại). Chỉ ca ĐÃ DUYỆT
                # được tính là phủ: một đăng ký PENDING chưa phải ca trực, giữ
                # lịch của khách trên một quyết định chưa ai duyệt là treo họ
                # vào lời hứa chưa có thật (NULL đời cũ coi như đã duyệt).
                con_lai = await conn.fetch(
                    """
                    SELECT w.shift,
                           (SELECT open_minute
                              FROM clinic_hours_for_date($1::uuid, $3))
                               AS open_minute,
                           (SELECT close_minute
                              FROM clinic_hours_for_date($1::uuid, $3))
                               AS close_minute,
                           (SELECT settings FROM public.clinic
                             WHERE id = $1::uuid) AS settings
                      FROM public.work_roster w
                     WHERE w.clinic_id = $1::uuid AND w.staff_id = $2::uuid
                       AND w.work_date = $3 AND w.station = 'LICH_KHAM'
                       AND w.id <> $4::uuid
                       AND coalesce(w.status, 'APPROVED') = 'APPROVED'
                    """,
                    identity.clinic_id,
                    row["staff_id"],
                    row["work_date"],
                    roster_id,
                )
                windows: list[tuple[int, int]] = []
                if con_lai and con_lai[0]["open_minute"] is not None:
                    ca = ca_tu_settings((con_lai[0]["settings"]))
                    windows = merge_windows(
                        [
                            w
                            for r in con_lai
                            for w in shift_windows(
                                r["shift"],
                                r["open_minute"],
                                r["close_minute"],
                                ca,
                            )
                        ]
                    )

                ung_vien = await conn.fetch(
                    """
                    SELECT id::text AS id,
                           (EXTRACT(HOUR FROM slot_start
                                    AT TIME ZONE 'Asia/Ho_Chi_Minh') * 60
                          + EXTRACT(MINUTE FROM slot_start
                                    AT TIME ZONE 'Asia/Ho_Chi_Minh'))::int
                               AS phut,
                           to_char(slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh',
                                   'HH24:MI') AS gio
                      FROM public.appointment
                     WHERE clinic_id = $1::uuid
                       AND doctor_id = $2::uuid
                       AND (slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                           = $3
                       AND slot_start > now()
                       AND status IN ('SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED')
                     ORDER BY slot_start
                    """,
                    identity.clinic_id,
                    row["staff_id"],
                    row["work_date"],
                )
                # Khung nào còn được phủ thì lịch ở yên — chỉ huỷ phần rơi ra
                # ngoài. Không còn khung nào (windows rỗng) thì huỷ cả, như #117.
                se_huy = [uv for uv in ung_vien if not covers(windows, uv["phut"])]

                if dry_run or not se_huy:
                    return {
                        "so_lich_huy": len(se_huy),
                        "gio": [uv["gio"] for uv in se_huy],
                    }

                await conn.execute(
                    """
                    UPDATE public.appointment
                       SET doctor_id = NULL,
                           bac_si_da_go_id = doctor_id,
                           bo_bac_si_luc = now(),
                           status = 'CANCELLED',
                           cancelled_at = now(),
                           ly_do_huy_ma = 'BAC_SI_DOI_LICH',
                           cancelled_by_staff_id = $3::uuid
                     WHERE clinic_id = $1::uuid
                       AND id = ANY($2::uuid[])
                    """,
                    identity.clinic_id,
                    [uv["id"] for uv in se_huy],
                    identity.staff_id,
                )
                for uv in se_huy:
                    await conn.execute(
                        """
                        INSERT INTO public.event_log
                            (clinic_id, event_type, aggregate_type, aggregate_id,
                             payload, metadata, source, event_published)
                        VALUES ($1::uuid, 'appointment.doctor_removed',
                                'appointment', $2::uuid, $3::jsonb, $4::jsonb,
                                'api:roster', FALSE)
                        """,
                        identity.clinic_id,
                        uv["id"],
                        json.dumps(
                            {
                                "ly_do": "ca_truc_bi_go",
                                "bac_si_da_go_id": str(row["staff_id"]),
                                "work_date": row["work_date"].isoformat(),
                            }
                        ),
                        json.dumps(
                            {
                                "clinic_role": identity.role.value,
                                "clinic_staff_id": identity.staff_id,
                                "origin": "api:roster",
                            }
                        ),
                    )
                logger.info(
                    "roster_shift_removed_cancelled_appointments",
                    so_lich=len(se_huy),
                    staff_id=str(row["staff_id"]),
                    work_date=row["work_date"].isoformat(),
                )
                return {
                    "so_lich_huy": len(se_huy),
                    "gio": [uv["gio"] for uv in se_huy],
                }

    async def apply_week(
        self, *, week_start: date, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Quản lý chốt lịch trực của một tuần.

        Trước khi có việc này, "tuần đã xếp" và "tuần đã chốt" là một — nên một
        bản nháp trải sẵn từ mẫu tuần cũng khoá được ô đặt lịch và cũng sinh
        được cảnh báo "bác sĩ không trực hôm đó". Xem 20260808000001.

        Áp dụng lại một tuần đã áp dụng KHÔNG phải lỗi: quản lý sửa thêm vài ca
        rồi bấm lại là chuyện thường. Chỉ cập nhật lại dấu thời gian và người bấm.
        """
        mon = week_start_of(week_start)
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                so_ca = await conn.fetchval(
                    "SELECT count(*) FROM work_roster "
                    "WHERE clinic_id = $1::uuid AND week_start = $2",
                    identity.clinic_id,
                    mon,
                )
                if not so_ca:
                    # Áp dụng một tuần trống nghĩa là tuyên bố "tuần này không
                    # ai đi làm" — và vì lịch trực là luật cao nhất, nó sẽ TỪ
                    # CHỐI mọi lượt đặt của cả tuần. Không để việc đó xảy ra do
                    # bấm nhầm.
                    raise ValidationError(
                        "Tuần này chưa xếp ca nào. Xếp lịch trước rồi mới áp dụng."
                    )

                await conn.execute(
                    """
                    INSERT INTO roster_week
                        (clinic_id, week_start, applied_by_staff_id)
                    VALUES ($1::uuid, $2, $3::uuid)
                    ON CONFLICT (clinic_id, week_start) DO UPDATE
                        SET applied_at = now(),
                            applied_by_staff_id = EXCLUDED.applied_by_staff_id
                    """,
                    identity.clinic_id,
                    mon,
                    identity.staff_id,
                )
                await conn.execute(
                    """
                    INSERT INTO event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, source, occurred_at)
                    VALUES ($1::uuid, 'roster.week_applied', 'roster_week',
                            gen_random_uuid(),
                            jsonb_build_object('week_start', $2::text,
                                               'so_ca', $3::int,
                                               'by_staff_id', $4::text),
                            'config.roster', now())
                    """,
                    identity.clinic_id,
                    mon.isoformat(),
                    so_ca,
                    identity.staff_id,
                )

        # TUẦN VỪA CÓ NGƯỜI TRỰC → BÁO CSKH, nhưng CHỈ khi có ai đó đang đợi.
        #
        # Quang 09/08/2026 mô tả đúng vòng này: khách đặt vào tuần chưa xếp lịch
        # → chờ quản lý xếp lịch làm việc → "khi đó mới có lịch của bác sĩ, thì
        # CSKH mới có lịch mà gọi lại cho khách để xác nhận lịch và bác sĩ".
        # Mắt xích cuối chưa từng tồn tại: `thong_bao` trước nay chỉ có đúng hai
        # người ghi vào, và không cái nào là chỗ này.
        #
        # ĐẾM TRƯỚC KHI GỬI. Áp lịch cho một tuần không ai đặt là việc hằng
        # tuần của quản lý; bắn thông báo cho CSKH mỗi lần như thế là dạy họ
        # cách phớt lờ cái chuông. Không có lịch nào chờ thì im lặng mới đúng.
        cho_xep = await self._pool.fetchval(
            """
            SELECT count(*) FROM public.appointment
             WHERE clinic_id = $1::uuid
               AND doctor_id IS NULL
               AND status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED',
                                  'COMPLETED')
               AND (slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                     BETWEEN $2 AND $2 + 6
            """,
            identity.clinic_id,
            mon,
        )
        if cho_xep:
            await self._bao_cskh_tuan_da_co_lich(
                week_start=mon, so_lich_cho=int(cho_xep), identity=identity
            )

        logger.info(
            "roster_week_applied",
            week_start=mon.isoformat(),
            so_ca=so_ca,
            cho_xep_bac_si=int(cho_xep or 0),
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "week_start": mon.isoformat(), "so_ca": so_ca}

    async def _bao_cskh_tuan_da_co_lich(
        self, *, week_start: date, so_lich_cho: int, identity: StaffIdentity
    ) -> None:
        """Nhắn vai CSKH rằng tuần này đã chốt lịch trực.

        Nuốt lỗi cùng lý do như `_bao_cskh_da_co_bac_si` ở booking_service: lịch
        trực ĐÃ áp và đã commit. Ném lỗi ở đây là báo hỏng cho một việc đã xong,
        và quản lý sẽ bấm "Áp dụng tuần" lần nữa.
        """
        from clinicai.services.thong_bao_service import ThongBaoService

        try:
            het = week_start + timedelta(days=6)
            await ThongBaoService(self._pool).goi(
                identity=identity,
                vai_nhan=ClinicRole.CSKH.value,
                nguon="tuan_lich_truc",
                # Khoá theo TUẦN: quản lý sửa vài ca rồi bấm áp lại là chuyện
                # thường (xem docstring của apply_week), và đó vẫn là một tin.
                nguon_id=week_start.isoformat(),
                muc_do="THUONG",
                tieu_de=(f"Tuần {week_start:%d/%m}–{het:%d/%m} đã chốt lịch trực"),
                noi_dung=(
                    f"Có {so_lich_cho} lịch hẹn trong tuần này đang chờ xếp bác "
                    "sĩ. Xếp xong lịch nào thì gọi xác nhận giờ khám và tên bác "
                    "sĩ với khách của lịch đó."
                ),
                # KHÔNG TRỎ `/appointments/cho-xep-bac-si` NỮA — CSKH KHÔNG VÀO
                # ĐƯỢC ĐƯỜNG ẤY.
                #
                # `roles.ts` chỉ mở màn Chờ xếp bác sĩ cho MANAGEMENT và
                # TRUONG_CA, nên vai CSKH bấm "Bấm để xử lý" là bị đá thẳng về
                # /home, không một lời giải thích. Một thông báo dẫn vào tường
                # còn tệ hơn thông báo không bấm được: người dùng học được rằng
                # cái chuông này nói dối.
                #
                # Việc của CSKH ở đây là GỌI XÁC NHẬN, tức màn Quản lý khách
                # hàng. Cố ý KHÔNG kèm bộ lọc tuần: `period=week` của màn ấy
                # tính theo TUẦN HIỆN TẠI, còn quản lý thường áp lịch cho tuần
                # SAU — một bộ lọc đúng cú pháp mà sai tuần thì tệ hơn không lọc,
                # vì danh sách rỗng đọc thành "không có việc gì".
                #
                # Từng lịch cụ thể vẫn được đánh thức riêng bằng thông báo
                # `bac_si_da_xep`, thứ đã trỏ đúng khách và đúng việc.
                duong_dan="/customers",
            )
        except Exception:  # noqa: BLE001 — xem docstring
            logger.warning(
                "bao_cskh_tuan_da_co_lich_that_bai",
                week_start=week_start.isoformat(),
                exc_info=True,
            )

    async def applied_weeks(
        self, *, identity: StaffIdentity, tu: date, den: date
    ) -> list[str]:
        """Những tuần đã áp dụng trong khoảng — để giao diện biết tuần nào dự kiến."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT week_start FROM roster_week "
                " WHERE clinic_id = $1::uuid AND week_start BETWEEN $2 AND $3"
                " ORDER BY week_start",
                identity.clinic_id,
                week_start_of(tu),
                week_start_of(den),
            )
        return [r["week_start"].isoformat() for r in rows]


class PriceListService:
    """Maintain the service and medicine price list."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list(
        self, *, group: PriceGroup, identity: StaffIdentity
    ) -> list[dict[str, Any]]:
        """Bảng giá của một nhóm (thuốc hoặc dịch vụ), sắp theo mã.

        TRẢ CẢ DÒNG ĐÃ TẮT (`active = false`). Thu ngân cần thấy chúng để biết
        một mã cũ đã ngừng dùng, chứ không phải để tưởng nó chưa từng tồn tại
        rồi đi tạo lại trùng mã. Màn hình tự làm mờ dòng đã tắt.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, service_code, name, "group", unit_price, active
                  FROM service_price
                 WHERE clinic_id = $1::uuid AND "group" = $2
                 ORDER BY service_code
                 LIMIT 1000
                """,
                identity.clinic_id,
                group,
            )
            return [dict(r) for r in rows]

    async def add(
        self,
        *,
        service_code: str,
        name: str,
        group: PriceGroup,
        unit_price: Any,
        identity: StaffIdentity,
    ) -> str:
        code = (service_code or "").strip()
        label = (name or "").strip()
        if not code or not label:
            raise ValidationError("Thiếu mã hoặc tên dịch vụ")

        price = parse_price(unit_price)
        async with self._pool.acquire() as conn:
            try:
                row_id = await conn.fetchval(
                    """
                    INSERT INTO service_price
                        (clinic_id, service_code, name, "group", unit_price)
                    VALUES ($1::uuid, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    identity.clinic_id,
                    code,
                    label,
                    group,
                    price,
                )
            except asyncpg.UniqueViolationError as exc:
                raise ConflictError(f"Mã {code} đã có trong nhóm {group}.") from exc
        return str(row_id)

    async def update(
        self,
        *,
        price_id: str,
        identity: StaffIdentity,
        name: str | None = None,
        unit_price: Any = None,
        unit_price_provided: bool = False,
        active: bool | None = None,
    ) -> None:
        patch: dict[str, Any] = {}
        if name is not None and name.strip():
            patch["name"] = name.strip()
        if unit_price_provided:
            patch["unit_price"] = parse_price(unit_price)
        if active is not None:
            patch["active"] = active
        if not patch:
            raise ValidationError("Không có gì để sửa")

        columns = list(patch)
        assignments = ", ".join(f"{c} = ${i + 3}" for i, c in enumerate(columns))
        async with self._pool.acquire() as conn:
            updated = await conn.fetchval(
                f"""
                UPDATE service_price SET {assignments}, updated_at = now()
                 WHERE id = $1::uuid AND clinic_id = $2::uuid
                RETURNING id
                """,
                price_id,
                identity.clinic_id,
                *[patch[c] for c in columns],
            )
        if updated is None:
            raise NotFoundError("Không tìm thấy dòng giá")

    async def remove(self, *, price_id: str, identity: StaffIdentity) -> None:
        async with self._pool.acquire() as conn:
            deleted = await conn.fetchval(
                "DELETE FROM service_price "
                "WHERE id = $1::uuid AND clinic_id = $2::uuid RETURNING id",
                price_id,
                identity.clinic_id,
            )
        if deleted is None:
            raise NotFoundError("Không tìm thấy dòng giá")
