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

import builtins
import hashlib
import json
import math
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any, Literal

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.shifts import (
    CAC_CA,
    ca_tu_settings,
    covers,
    merge_windows,
    shift_windows,
)
from clinicai.permissions import cache
from clinicai.permissions.can import can
from clinicai.services.nhan_vai import gan_nhan_vai

logger = structlog.get_logger()

#: Mã vị trí là CA KHÁM của bác sĩ — `LICH_KHAM` (mẫu cũ) và mọi vị trí bác sĩ của
#: lịch Kim Ngưu. Bản Python của hàm DB `public.la_ca_kham_bac_si` (migration
#: 20260917000004), dùng ở chỗ đã có sẵn dòng lịch trong tay.
MA_CA_KHAM_BAC_SI: frozenset[str] = frozenset(
    {
        "LICH_KHAM",
        "T1_BS_NOITIET",
        "T1_TT_BS",
        "T1_TTNG_BS",
        "T1_SA_BS",
        "T4_SA_BS1",
        "T4_SA_BS2",
        "T4_SANCHAU_BS",
        "T4_SANCHAU_BSTT",
        "T4_SAN_BS",
    }
)


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
    async def _xep_lich(self, identity: StaffIdentity) -> bool:
        """Người XẾP lịch trực = trưởng ca (quyền `roster.manage`, lego Điều
        phối khách — Tuyền 01/10/2026) hoặc lego 18 "Cài đặt phòng khám". Hỏi
        quyền, không hỏi vai — `ROSTER_ADMIN_ROLES` cũ giữ làm bản OFF."""
        async with self._pool.acquire() as conn:
            return await can(conn, identity, "roster.manage") or await can(
                conn, identity, "config.clinic.manage"
            )

    async def _cai_dat(self, identity: StaffIdentity) -> bool:
        """Sửa phạm vi vị trí = cấu hình phòng khám, chỉ lego 18."""
        async with self._pool.acquire() as conn:
            return await can(conn, identity, "config.clinic.manage")

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

        is_admin = await self._xep_lich(identity)
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
            if station in MA_CA_KHAM_BAC_SI and is_admin:
                await self._bao_lich_cho_xep(
                    conn,
                    roster_id=str(row_id),
                    work_date=work_date,
                    shift=shift if shift in CAC_CA else "FULL",
                    ten_bac_si=target_name,
                    identity=identity,
                )

        # Quyền theo lịch hôm nay đổi ngay (xem `thay_nguoi`).
        cache.quen(identity.clinic_id)
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
                        # Vai tài khoản gốc (vai dùng có thể khác).
                        "vai_tai_khoan": identity.vai_goc.value,
                        "clinic_staff_id": identity.staff_id,
                        "origin": "api:roster",
                    }
                ),
            )
            # Import muộn: khối chuông kéo theo danh mục sự kiện.
            from clinicai.events.consumers.chuong import ghi_chuong_vai

            # CHUÔNG TRONG APP cho người có lego CSKH (Tuyền 29/09/2026) — tin
            # Telegram đã tắt nên dòng sổ trên không còn tới ai. Khoá theo ca
            # (roster_id): sửa ca nhiều lần vẫn một chuông đang mở.
            gio = ", ".join(r["gio"] for r in trong_ca[:6])
            them = f" và {len(trong_ca) - 6} lịch khác" if len(trong_ca) > 6 else ""
            await ghi_chuong_vai(
                conn,
                clinic_id=identity.clinic_id,
                vai=ClinicRole.CSKH.value,
                tieu_de=(
                    f"BS {ten_bac_si} có ca {work_date:%d/%m} — "
                    f"{len(trong_ca)} lịch đang chờ xếp"
                ),
                noi_dung=(
                    f"Lịch chưa xếp bác sĩ trong ca này: {gio}{them}. Xếp xong "
                    "thì gọi khách xác nhận giờ khám và tên bác sĩ."
                ),
                nguon="lich_cho_xep_co_ca",
                nguon_id=roster_id,
                duong_dan="/customers",
                nguoi_goi=identity.staff_id,
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
        if not await self._cai_dat(identity):
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
        if not await self._xep_lich(identity):
            raise SafetyGateError("Chỉ trưởng ca / quản lý được duyệt ca")

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
        """Gỡ một ca trực — lịch hẹn KHÔNG CÒN KHUNG NÀO PHỦ chuyển sang hàng
        "Lịch chờ xếp bác sĩ". KHÔNG HUỶ lịch nào.

        Luật hiện hành: CONTEXT v1.0 (12/09/2026) — *đổi hay gỡ lịch trực
        không bao giờ huỷ lịch hẹn*. Lịch trực là kế hoạch của phòng khám;
        lịch hẹn là lời hứa với khách. Kế hoạch đổi thì lời hứa cần một người
        xử lý (xếp bác sĩ khác, hoặc gọi khách đổi giờ), không cần một câu
        UPDATE tự quyết thay khách.

        Lịch sử để khỏi đi vòng lại:
          · #103 (14/08): gỡ ca → gỡ bác sĩ khỏi lịch, lịch về hàng chờ xếp.
          · #115: xếp lại ca thì tự gắn lại bác sĩ — bỏ vì đụng ghế đã bị lịch
            khác chiếm.
          · #117 (15/08): đổi sang HUỶ HẲN, vì lịch còn sống không bác sĩ chặn
            việc ĐẶT LỊCH MỚI cùng khung cho cùng khách (`_patient_conflict`).
            Cái chặn ấy có thật, nhưng thuốc chữa là SỬA CHÍNH LỊCH ĐÓ ở hàng
            chờ (gán bác sĩ khác / đổi giờ) chứ không phải tạo lịch thứ hai —
            nên huỷ là chữa sai bệnh và làm mất lời hứa với khách.
          · 17/08: tính theo KHUNG GIỜ chứ không theo ngày — giữ nguyên ở đây.
            Chỉ lịch mà giờ hẹn rơi RA NGOÀI hợp các ca còn lại của chính bác
            sĩ ấy hôm đó mới bị gỡ bác sĩ; muốn đổi sáng→cả ngày thì thêm ca
            mới trước rồi gỡ ca cũ là không lịch nào phải xếp lại.

        Người xử lý: hàng "Lịch chờ xếp bác sĩ" (Quản lý + Trưởng ca), đọc
        `doctor_id IS NULL`; `bac_si_da_go_id` giữ tên người cũ để CSKH gọi
        khách nói được "đổi từ ai", và cờ `bs_go_co_ca_lai` báo khi bác sĩ cũ
        đã có ca lại (gán lại một cú bấm, không cần gọi khách).

        `dry_run=True`: đo mà không cắt — trả số lịch SẼ chuyển sang chờ xếp
        (kèm giờ) để màn hình hỏi lại người gỡ.

        CHỈ LỊCH CÒN SỐNG (chưa tới giờ, chưa check-in); câu UPDATE lặp lại
        điều kiện trạng thái + bác sĩ để một lượt check-in/gán lại chen giữa
        lúc đọc và lúc ghi không bị gỡ nhầm.
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

                if not await self._xep_lich(identity) and (
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
                    # Dòng ca bị xoá khỏi bảng thì dấu vết duy nhất còn lại
                    # là ở đây: ai gỡ ca của ai, ngày nào.
                    await conn.execute(
                        """
                        INSERT INTO public.event_log
                            (clinic_id, event_type, aggregate_type, aggregate_id,
                             payload, metadata, source, event_published)
                        VALUES ($1::uuid, 'roster.shift_removed', 'work_roster',
                                $2::uuid, $3::jsonb, $4::jsonb, 'api:roster',
                                FALSE)
                        """,
                        identity.clinic_id,
                        roster_id,
                        json.dumps(
                            {
                                "staff_id": str(row["staff_id"] or ""),
                                "work_date": row["work_date"].isoformat(),
                                "station": row["station"],
                            }
                        ),
                        json.dumps(
                            {
                                "clinic_role": identity.role.value,
                                # Vai tài khoản gốc (vai dùng có thể khác).
                                "vai_tai_khoan": identity.vai_goc.value,
                                "clinic_staff_id": identity.staff_id,
                                "origin": "api:roster",
                            }
                        ),
                    )

                if not dry_run:
                    # Người bị gỡ mất quyền theo lịch ngay (xem `thay_nguoi`).
                    cache.quen(identity.clinic_id)
                if row["station"] not in MA_CA_KHAM_BAC_SI or row["staff_id"] is None:
                    return {"so_lich_cho_xep": 0, "gio": []}

                return await self._go_lich_ngoai_ca(
                    conn,
                    identity=identity,
                    staff_id=str(row["staff_id"]),
                    work_date=row["work_date"],
                    loai_tru_id=roster_id,
                    dry_run=dry_run,
                    ly_do="ca_truc_bi_go",
                )

    async def _go_lich_ngoai_ca(
        self,
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        staff_id: str,
        work_date: date,
        loai_tru_id: str | None,
        dry_run: bool,
        ly_do: str,
    ) -> dict[str, Any]:
        """Bác sĩ `staff_id` vừa rời một ca khám ngày `work_date` (gỡ ca, hoặc
        bị thay người giữa ca) → lịch hẹn còn sống mà giờ hẹn rơi RA NGOÀI các
        ca còn lại của bác sĩ ấy chuyển sang "Lịch chờ xếp bác sĩ". Không huỷ
        lịch nào — luật và lịch sử ở docstring `remove`.

        `loai_tru_id`: dòng lịch không được tính là "ca còn lại" (dry_run chưa
        xoá thật nên phải tự loại). Gọi TRONG giao dịch của người gọi.
        """

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
               AND w.work_date = $3
               AND public.la_ca_kham_bac_si(w.clinic_id, w.station)
               AND ($4::uuid IS NULL OR w.id <> $4::uuid)
               AND coalesce(w.status, 'APPROVED') = 'APPROVED'
            """,
            identity.clinic_id,
            staff_id,
            work_date,
            loai_tru_id,
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
            staff_id,
            work_date,
        )
        # Khung nào còn được phủ thì lịch ở yên — chỉ phần rơi ra ngoài
        # mới cần xếp lại bác sĩ. Không còn khung nào thì cả ngày.
        cho_xep = [uv for uv in ung_vien if not covers(windows, uv["phut"])]

        if dry_run or not cho_xep:
            return {
                "so_lich_cho_xep": len(cho_xep),
                "gio": [uv["gio"] for uv in cho_xep],
            }

        # Gỡ BÁC SĨ, giữ LỊCH: trạng thái, giờ, khách, dịch vụ nguyên
        # vẹn. Không đụng cột huỷ (status/cancelled_*/ly_do_huy_ma).
        await conn.execute(
            """
            UPDATE public.appointment
               SET doctor_id = NULL,
                   bac_si_da_go_id = doctor_id,
                   bo_bac_si_luc = now()
             WHERE clinic_id = $1::uuid
               AND id = ANY($2::uuid[])
               AND doctor_id = $3::uuid
               AND status IN ('SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED')
            """,
            identity.clinic_id,
            [uv["id"] for uv in cho_xep],
            staff_id,
        )
        for uv in cho_xep:
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
                        "ly_do": ly_do,
                        "bac_si_da_go_id": staff_id,
                        "work_date": work_date.isoformat(),
                    }
                ),
                json.dumps(
                    {
                        "clinic_role": identity.role.value,
                        # Vai tài khoản gốc (vai dùng có thể khác).
                        "vai_tai_khoan": identity.vai_goc.value,
                        "clinic_staff_id": identity.staff_id,
                        "origin": "api:roster",
                    }
                ),
            )
        logger.info(
            "roster_shift_removed_appointments_need_doctor",
            so_lich=len(cho_xep),
            staff_id=staff_id,
            work_date=work_date.isoformat(),
        )
        return {
            "so_lich_cho_xep": len(cho_xep),
            "gio": [uv["gio"] for uv in cho_xep],
        }

    async def _doi_nguoi_duoc(self, identity: StaffIdentity) -> bool:
        """Người được ĐỔI NGƯỜI trong ca: quyền riêng `roster.shift.swap` (khối
        trưởng ca, lego Điều phối khách — 29/09/2026), hoặc người xếp lịch."""
        async with self._pool.acquire() as conn:
            return (
                await can(conn, identity, "roster.shift.swap")
                or await can(conn, identity, "roster.manage")
                or await can(conn, identity, "config.clinic.manage")
            )

    async def thay_nguoi(
        self,
        *,
        roster_id: str,
        staff_moi_id: str,
        identity: StaffIdentity,
        ly_do: str | None = None,
    ) -> dict[str, Any]:
        """Thay người đứng một ca — hôm nay (kể cả đang giữa ca) hoặc ngày tới.

        Tuyền 29/09/2026: Hà đứng Siêu âm 1 phải về giữa ca, trưởng ca xếp B vào
        thay → B có ngay trọn quyền của vị trí/phòng ấy, Hà mất ngay, lịch giữ
        vết "Hà tới HH:MM → B từ HH:MM", nhật ký ghi ai đổi.

        DÒNG LỊCH ĐỔI NGƯỜI, không xoá-rồi-thêm: mọi chỗ đọc lịch (quyền theo
        lịch, thanh bên, bác sĩ cùng phòng, hàng chờ) thấy người mới ngay mà
        không phải sửa từng chỗ đọc; người cũ nằm ở sổ `work_roster_thay_nguoi`.
        Một giao dịch: khoá dòng → đổi → ghi sổ + nhật ký → (ca khám bác sĩ)
        lịch hẹn của bác sĩ cũ không còn ca nào phủ chuyển sang chờ xếp bác sĩ,
        như gỡ ca (`remove`) — KHÔNG tự gán sang bác sĩ mới (#115).

        Không kiểm ma trận vai × vị trí: người thay vào giúp là việc của trưởng
        ca quyết tại chỗ ("open, đừng block").
        """
        if not await self._doi_nguoi_duoc(identity):
            raise SafetyGateError(
                "Bạn chưa có quyền “Đổi người trong ca” — nhờ quản lý bật ở màn"
                " Phân quyền (lego Điều phối khách)."
            )
        hom_nay = datetime.now(CLINIC_TZ).date()
        ly_do = (ly_do or "").strip()[:500] or None
        lich: dict[str, Any] = {"so_lich_cho_xep": 0, "gio": []}
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT id::text, staff_id::text, staff_name, work_date, shift,
                           station, status
                      FROM work_roster
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                       FOR UPDATE
                    """,
                    roster_id,
                    identity.clinic_id,
                )
                if row is None:
                    raise NotFoundError("Không tìm thấy ca trực")
                if row["work_date"] < hom_nay:
                    raise ValidationError(
                        "Ca này đã qua — chỉ đổi người cho hôm nay và các ngày tới."
                    )
                if row["status"] == "REJECTED":
                    raise ValidationError(
                        "Ca này đã bị từ chối — xếp ca mới thay vì đổi người."
                    )
                if row["staff_id"] == staff_moi_id:
                    raise ValidationError("Người này đang đứng chính ca ấy rồi.")
                nv = await conn.fetchrow(
                    """
                    SELECT s.full_name
                      FROM public.staff s
                      JOIN public.clinic_membership m
                        ON m.staff_id = s.id AND m.is_active
                     WHERE s.id = $1::uuid AND m.clinic_id = $2::uuid AND s.is_active
                    """,
                    staff_moi_id,
                    identity.clinic_id,
                )
                if nv is None:
                    raise ValidationError(
                        "Không tìm thấy nhân viên đang làm việc ở phòng khám này."
                    )
                trung = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM work_roster
                         WHERE clinic_id = $1::uuid AND work_date = $2
                           AND shift = $3 AND station = $4
                           AND staff_id = $5::uuid AND id <> $6::uuid
                           AND status <> 'REJECTED')
                    """,
                    identity.clinic_id,
                    row["work_date"],
                    row["shift"],
                    row["station"],
                    staff_moi_id,
                    roster_id,
                )
                if trung:
                    raise ConflictError(
                        f"{nv['full_name']} đã có trong ca này ở cùng vị trí."
                    )
                await conn.execute(
                    """
                    UPDATE work_roster
                       SET staff_id = $3::uuid, staff_name = $4,
                           status = 'APPROVED', reject_reason = NULL,
                           updated_at = now()
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                    """,
                    roster_id,
                    identity.clinic_id,
                    staff_moi_id,
                    nv["full_name"],
                )
                vet_id = await conn.fetchval(
                    """
                    INSERT INTO work_roster_thay_nguoi
                        (clinic_id, roster_id, work_date, shift, station,
                         nguoi_cu_id, nguoi_cu_ten, nguoi_moi_id, nguoi_moi_ten,
                         boi_staff_id, ly_do)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::uuid, $7,
                            $8::uuid, $9, $10::uuid, $11)
                    RETURNING id::text
                    """,
                    identity.clinic_id,
                    roster_id,
                    row["work_date"],
                    row["shift"],
                    row["station"],
                    row["staff_id"],
                    row["staff_name"],
                    staff_moi_id,
                    nv["full_name"],
                    identity.staff_id,
                    ly_do,
                )
                # Lịch sử thao tác đọc event_log (`v_audit_log`).
                await conn.execute(
                    """
                    INSERT INTO public.event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, metadata, source, event_published)
                    VALUES ($1::uuid, 'roster.shift_reassigned', 'work_roster',
                            $2::uuid, $3::jsonb, $4::jsonb, 'api:roster', FALSE)
                    """,
                    identity.clinic_id,
                    roster_id,
                    json.dumps(
                        {
                            "work_date": row["work_date"].isoformat(),
                            "shift": row["shift"],
                            "station": row["station"],
                            "nguoi_cu_id": row["staff_id"],
                            "nguoi_cu_ten": row["staff_name"],
                            "nguoi_moi_id": staff_moi_id,
                            "nguoi_moi_ten": nv["full_name"],
                            "ly_do": ly_do,
                        }
                    ),
                    json.dumps(
                        {
                            "clinic_role": identity.role.value,
                            "vai_tai_khoan": identity.vai_goc.value,
                            "clinic_staff_id": identity.staff_id,
                            "origin": "api:roster",
                        }
                    ),
                )
                if row["station"] in MA_CA_KHAM_BAC_SI:
                    if row["staff_id"] is not None:
                        lich = await self._go_lich_ngoai_ca(
                            conn,
                            identity=identity,
                            staff_id=row["staff_id"],
                            work_date=row["work_date"],
                            loai_tru_id=roster_id,
                            dry_run=False,
                            ly_do="thay_nguoi_trong_ca",
                        )
            # Tin "ca bác sĩ mới có → lịch chờ xếp" là việc phụ, tự nuốt lỗi —
            # chạy SAU khi giao dịch đã chốt để lỗi của nó không làm hỏng cú đổi.
            if row["station"] in MA_CA_KHAM_BAC_SI:
                await self._bao_lich_cho_xep(
                    conn,
                    roster_id=roster_id,
                    work_date=row["work_date"],
                    shift=row["shift"],
                    ten_bac_si=nv["full_name"],
                    identity=identity,
                )
        # Quyền theo lịch đổi NGAY: quên quyền + danh tính (vai suy từ lego)
        # đang nhớ của cả phòng khám — cả người cũ lẫn người mới.
        cache.quen(identity.clinic_id)
        logger.info(
            "roster_shift_reassigned",
            roster_id=roster_id,
            nguoi_cu=row["staff_id"],
            nguoi_moi=staff_moi_id,
            by_staff_id=identity.staff_id,
        )
        return {"id": vet_id, "nguoi_moi_ten": nv["full_name"], **lich}

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

        # LỊCH MẤT BÁC SĨ vì công bố (Tuyền chốt 24/09/2026). Khách đặt lúc tuần
        # chưa có lịch trực, chọn bác sĩ A; quản lý công bố tuần mà A nghỉ đúng
        # ngày ấy → lịch vẫn giữ A nhưng A không có ca. Màn "Chờ xếp bác sĩ" đã
        # thấy (MAT_BAC_SI), nhưng CHUÔNG chỉ báo "vượt sức chứa" — CSKH không
        # biết phải gọi khách. Cùng luật "mất bác sĩ" với màn ấy (booking.py).
        mat = await self._pool.fetch(
            """
            SELECT a.slot_start, bs.full_name AS bac_si, p.full_name AS khach
              FROM public.appointment a
              LEFT JOIN public.staff bs ON bs.id = a.doctor_id
              LEFT JOIN public.patient p
                ON p.clinic_patient_id = a.clinic_patient_id
               AND p.clinic_id = a.clinic_id
             WHERE a.clinic_id = $1::uuid
               AND a.doctor_id IS NOT NULL
               AND a.slot_start >= now()
               AND a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED',
                                    'COMPLETED')
               AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                     BETWEEN $2 AND $2 + 6
               AND NOT EXISTS (
                     SELECT 1 FROM public.work_roster w
                      WHERE w.clinic_id = a.clinic_id
                        AND w.staff_id = a.doctor_id
                        AND w.work_date =
                            (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)
             ORDER BY a.slot_start
            """,
            identity.clinic_id,
            mon,
        )
        if mat:
            await self._bao_lich_mat_bac_si(
                week_start=mon, mat=list(mat), identity=identity
            )

        # ĐỐI SOÁT LÚC CÔNG BỐ (CONTEXT v1.0). Trước khi công bố, trần không
        # chặn lịch hẹn (20260915000001), nên có thể có khung vượt trần. Giữ
        # hết lịch; liệt kê khung vượt và giao cho Trưởng ca xử lý với khách.
        vuot = await self._pool.fetch(
            """
            SELECT k.doctor_id::text AS doctor_id, s.full_name, k.bat_dau,
                   k.tran, k.da_dung
              FROM public.khung_vuot_tran_trong_tuan($1::uuid, $2) k
              LEFT JOIN public.staff s ON s.id = k.doctor_id
            """,
            identity.clinic_id,
            mon,
        )
        khung_vuot_tran = [
            {
                "doctor_id": r["doctor_id"],
                "bac_si": r["full_name"],
                "bat_dau": r["bat_dau"].isoformat(),
                "tran": int(r["tran"]),
                "da_dung": int(r["da_dung"]),
            }
            for r in vuot
        ]
        if vuot:
            await self._bao_truong_ca_vuot_tran(
                week_start=mon, vuot=list(vuot), identity=identity
            )

        logger.info(
            "roster_week_applied",
            week_start=mon.isoformat(),
            so_ca=so_ca,
            cho_xep_bac_si=int(cho_xep or 0),
            khung_vuot_tran=len(khung_vuot_tran),
            by_staff_id=identity.staff_id,
        )
        return {
            "ok": True,
            "week_start": mon.isoformat(),
            "so_ca": so_ca,
            "khung_vuot_tran": khung_vuot_tran,
        }

    async def _bao_truong_ca_vuot_tran(
        self, *, week_start: date, vuot: list[Any], identity: StaffIdentity
    ) -> None:
        """Báo khung vượt trần cho CSKH VÀ Trưởng ca (Tuyền chốt 15/09/2026).

        CSKH là người gọi khách chốt/đổi ca — từng lịch vượt nằm ở việc
        `VUOT_SUC_CHUA` màn CSKH (20260915000014). Trưởng ca cũng phải biết.
        Nuốt lỗi cùng lý do với `_bao_cskh_tuan_da_co_lich`: lịch trực đã áp và
        commit; danh sách vẫn nằm trong câu trả lời của apply_week.
        """
        from clinicai.services.thong_bao_service import ThongBaoService

        dong = [
            f"{(r['full_name'] or 'Bác sĩ')} "
            f"{r['bat_dau'].astimezone(CLINIC_TZ):%H:%M %d/%m} "
            f"({r['da_dung']}/{r['tran']})"
            for r in vuot[:8]
        ]
        them = f" và {len(vuot) - 8} khung khác" if len(vuot) > 8 else ""
        het = week_start + timedelta(days=6)
        tieu_de = (
            f"Tuần {week_start:%d/%m}–{het:%d/%m}: {len(vuot)} khung "
            "vượt sức chứa sau khi công bố lịch trực"
        )
        khung = "; ".join(dong) + them + "."
        for vai, noi_dung, duong_dan in (
            (
                ClinicRole.CSKH.value,
                "Lịch nhận lúc tuần chưa công bố, KHÔNG bị huỷ. Gọi những khách "
                "đặt sau cùng (việc 'Lịch vượt sức chứa') để chốt hoặc đổi ca: "
                + khung,
                "/customers",
            ),
            (
                ClinicRole.TRUONG_CA.value,
                "Lịch nhận lúc tuần chưa công bố, KHÔNG bị huỷ; CSKH đang gọi "
                "khách chốt hoặc đổi ca: " + khung,
                "/appointments/cho-xep-bac-si",
            ),
        ):
            try:
                await ThongBaoService(self._pool).goi(
                    identity=identity,
                    vai_nhan=vai,
                    nguon="xung_dot_suc_chua",
                    nguon_id=f"{week_start.isoformat()}:{vai}",
                    muc_do="KHAN",
                    tieu_de=tieu_de,
                    noi_dung=noi_dung,
                    duong_dan=duong_dan,
                )
            except Exception:  # noqa: BLE001 — xem docstring
                logger.warning(
                    "bao_vuot_tran_that_bai",
                    vai=vai,
                    week_start=week_start.isoformat(),
                    exc_info=True,
                )

    async def _bao_lich_mat_bac_si(
        self, *, week_start: date, mat: list[Any], identity: StaffIdentity
    ) -> None:
        """Báo CSKH (gọi khách đổi bác sĩ/giờ) và Trưởng ca (xếp lại bác sĩ).

        Nuốt lỗi cùng lý do với `_bao_truong_ca_vuot_tran`: lịch trực đã áp và
        commit; lịch mất bác sĩ vẫn nằm ở màn Chờ xếp bác sĩ.
        """
        from clinicai.services.thong_bao_service import ThongBaoService

        dong = [
            f"{r['slot_start'].astimezone(CLINIC_TZ):%H:%M %d/%m} "
            f"{r['khach'] or 'khách'} (BS {r['bac_si'] or '?'} nghỉ)"
            for r in mat[:8]
        ]
        them = f" và {len(mat) - 8} lịch khác" if len(mat) > 8 else ""
        het = week_start + timedelta(days=6)
        tieu_de = (
            f"Tuần {week_start:%d/%m}–{het:%d/%m}: {len(mat)} lịch hẹn mất bác "
            "sĩ sau khi công bố lịch trực"
        )
        ds = "; ".join(dong) + them + "."
        for vai, noi_dung, duong_dan in (
            (
                ClinicRole.CSKH.value,
                "Bác sĩ khách đã chọn không có ca ngày đó. Lịch KHÔNG bị huỷ — "
                "gọi khách đổi bác sĩ hoặc đổi ngày: " + ds,
                "/customers",
            ),
            (
                ClinicRole.TRUONG_CA.value,
                "Bác sĩ của các lịch này không có ca ngày đó — xếp bác sĩ khác "
                "ở màn Chờ xếp bác sĩ; CSKH đang gọi khách: " + ds,
                "/appointments/cho-xep-bac-si",
            ),
        ):
            try:
                await ThongBaoService(self._pool).goi(
                    identity=identity,
                    vai_nhan=vai,
                    nguon="lich_mat_bac_si",
                    nguon_id=f"{week_start.isoformat()}:{vai}",
                    muc_do="KHAN",
                    tieu_de=tieu_de,
                    noi_dung=noi_dung,
                    duong_dan=duong_dan,
                )
            except Exception:  # noqa: BLE001 — xem docstring
                logger.warning(
                    "bao_lich_mat_bac_si_that_bai",
                    vai=vai,
                    week_start=week_start.isoformat(),
                    exc_info=True,
                )

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

    async def lich_tuan(self, *, identity: StaffIdentity, tuan: date) -> dict[str, Any]:
        """Dữ liệu màn Lịch làm việc (/schedule) cho một tuần.

        24/09/2026: trang từng tự đọc 5 bảng bằng Supabase (work_roster, staff,
        vai_duoc_vao_tram, vi_tri_dong_ca, roster_week). Danh sách nhân sự + trạm
        theo vai chỉ trả cho người xếp lịch (ROSTER_ROLES) — ô "+" chỉ bày cho họ.
        `ten_chuan` = `staff.full_name` theo `staff_id` (dòng nhập tay không nối
        được ai giữ nguyên `staff_name`); giao diện rút gọn tên để hiển thị.
        """
        dau = week_start_of(tuan)
        cuoi = dau + timedelta(days=6)
        la_quan_ly = await self._xep_lich(identity)
        doi_nguoi = la_quan_ly or await self._doi_nguoi_duoc(identity)
        async with self._pool.acquire() as conn:
            dong = await conn.fetch(
                """
                SELECT w.id::text, w.work_date, w.shift, w.station,
                       w.staff_id::text, w.staff_name, w.status, w.reject_reason,
                       s.full_name AS ten_chuan,
                       -- Vai của người đứng (27/09/2026 đợt 3, A9) — cùng câu
                       -- với gói Trang chủ (`man_trang_chu_service`).
                       (SELECT m.role FROM clinic_membership m
                         WHERE m.staff_id = w.staff_id
                           AND m.clinic_id = w.clinic_id AND m.is_active
                         ORDER BY m.created_at, m.id LIMIT 1) AS vai_ma
                  FROM work_roster w
                  LEFT JOIN staff s ON s.id = w.staff_id
                 WHERE w.clinic_id = $1::uuid AND w.week_start = $2
                 ORDER BY w.sort, w.id
                """,
                identity.clinic_id,
                dau,
            )
            # Chỉ khối NGHỈ. Ô ĐEN (DONG — "vị trí không làm ca ấy") thôi trả
            # từ 28/09/2026: nó giấu nút + nên quản lý không xếp được người vào
            # ca ấy (Tuyền: "mở lại quyền đặt ca, đừng block nữa").
            dong_ca = await conn.fetch(
                """
                SELECT work_date, shift, station, ly_do FROM vi_tri_dong_ca
                 WHERE clinic_id = $1::uuid AND ly_do = 'NGHI'
                   AND work_date BETWEEN $2 AND $3
                """,
                identity.clinic_id,
                dau,
                cuoi,
            )
            da_ap_dung = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM roster_week"
                " WHERE clinic_id = $1::uuid AND week_start = $2)",
                identity.clinic_id,
                dau,
            )
            # Vết đổi người trong ca (29/09/2026) — "Hà tới 10:30 → B từ 10:30".
            thay_nguoi = await conn.fetch(
                """
                SELECT t.roster_id::text, t.work_date, t.shift, t.station,
                       t.nguoi_cu_id::text, t.nguoi_cu_ten,
                       t.nguoi_moi_id::text, t.nguoi_moi_ten,
                       to_char(t.luc AT TIME ZONE 'Asia/Ho_Chi_Minh', 'HH24:MI')
                           AS gio,
                       s.full_name AS boi_ten, t.ly_do
                  FROM work_roster_thay_nguoi t
                  LEFT JOIN staff s ON s.id = t.boi_staff_id
                 WHERE t.clinic_id = $1::uuid AND t.work_date BETWEEN $2 AND $3
                 ORDER BY t.luc
                """,
                identity.clinic_id,
                dau,
                cuoi,
            )
            nhan_su: list[asyncpg.Record] = []
            tram: list[asyncpg.Record] = []
            if doi_nguoi:
                nhan_su = await conn.fetch(
                    """
                    SELECT DISTINCT s.id::text, s.full_name, s.short_name,
                           s.primary_department
                      FROM staff s
                      JOIN clinic_membership m ON m.staff_id = s.id
                     WHERE m.clinic_id = $1::uuid AND s.is_active
                     ORDER BY s.full_name
                    """,
                    identity.clinic_id,
                )
            if la_quan_ly:
                tram = await conn.fetch(
                    "SELECT vai, tram_ma FROM vai_duoc_vao_tram"
                    " WHERE clinic_id = $1::uuid AND is_active",
                    identity.clinic_id,
                )

        def _d(r: asyncpg.Record) -> dict[str, Any]:
            return {
                k: (v.isoformat() if isinstance(v, date) else v) for k, v in r.items()
            }

        return {
            "tuan": dau.isoformat(),
            "da_ap_dung": bool(da_ap_dung),
            "la_quan_ly": la_quan_ly,
            "doi_nguoi": doi_nguoi,
            "hom_nay": datetime.now(CLINIC_TZ).date().isoformat(),
            "thay_nguoi": [_d(r) for r in thay_nguoi],
            "dong": [gan_nhan_vai(_d(r)) for r in dong],
            "dong_ca": [_d(r) for r in dong_ca],
            "nhan_su": [dict(r) for r in nhan_su],
            "tram_theo_vai": [dict(r) for r in tram],
        }

    async def bac_si_trong_ngay(
        self, *, identity: StaffIdentity, ngay: date
    ) -> dict[str, Any]:
        """Bác sĩ có ca khám trong ngày (lưới đặt lịch) + tuần đã chốt chưa.

        Chuyển từ route giao diện `/api/roster?date=` (24/09/2026) — nó từng đọc
        thẳng `roster_week` / `work_roster` bằng Supabase. Luật giữ nguyên (Quang
        10/08): CÓ phân công thì trả về; tuần chưa áp dụng chỉ là `du_kien`
        (câu nói thêm), không phải cái khoá.
        """
        async with self._pool.acquire() as conn:
            da_ap_dung = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM roster_week"
                " WHERE clinic_id = $1::uuid AND week_start = $2)",
                identity.clinic_id,
                week_start_of(ngay),
            )
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (staff_id) staff_id::text AS id,
                       coalesce(staff_name, '') AS name
                  FROM work_roster
                 WHERE clinic_id = $1::uuid AND work_date = $2
                   AND station = ANY($3::text[]) AND status = 'APPROVED'
                   AND staff_id IS NOT NULL
                 ORDER BY staff_id, created_at
                """,
                identity.clinic_id,
                ngay,
                sorted(MA_CA_KHAM_BAC_SI),
            )
        return {"doctors": [dict(r) for r in rows], "du_kien": not da_ap_dung}


def _gia_thuong(v: Any) -> Any:
    """Decimal('9.0E+5') → Decimal('900000'); None giữ None."""
    if v is None:
        return None
    try:
        return v.quantize(1) if v == v.to_integral_value() else v.normalize()
    except (AttributeError, ArithmeticError):
        return v


_MA_KV = re.compile(r"^[A-Z0-9_-]{1,32}$")


#: Bên thu của một dịch vụ (Tuyền 29/09/2026 — chọn ở màn Bảng giá).
BEN_THU_HOP_LE: tuple[str, ...] = ("CLINIC", "EXTERNAL_PARTNER")


def doc_ben_thu(v: Any) -> str | None:
    """ "CLINIC" / "EXTERNAL_PARTNER" (không phân biệt hoa thường) → giữ; rỗng /
    None → None (= không chọn, dùng mặc định theo phòng làm); rác → 422."""
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValidationError("Bên thu phải là Phòng khám thu hoặc Thu hộ đối tác.")
    ben = v.strip().upper()
    if not ben:
        return None
    if ben not in BEN_THU_HOP_LE:
        raise ValidationError("Bên thu phải là Phòng khám thu hoặc Thu hộ đối tác.")
    return ben


def _ma_kiotviet(v: str | None) -> str | None:
    """Mã phòng khám: bỏ khoảng trắng, viết hoa; rỗng → None; ký tự lạ → 422."""
    ma = (v or "").strip().upper()
    if not ma:
        return None
    if not _MA_KV.match(ma):
        raise ValidationError("Mã phòng khám chỉ gồm chữ, số, gạch — tối đa 32 ký tự.")
    return ma


def khoa_ten_dich_vu(ten: str) -> str:
    """Tên chuẩn hoá — y hệt hàm SQL `khoa_ten_dich_vu` (NFC, thường, gộp khoảng
    trắng). Hàm thuần."""
    return " ".join(unicodedata.normalize("NFC", ten or "").split()).lower()


def ma_dich_vu_theo_ten(ten: str) -> str:
    """Mã nội bộ `DV_<10 ký tự md5 của tên chuẩn hoá>` — hàm thuần."""
    return "DV_" + hashlib.md5(khoa_ten_dich_vu(ten).encode()).hexdigest()[:10].upper()


def _nhom_hang(v: str | None) -> str | None:
    """Nhóm hàng (01/10/2026): gộp khoảng trắng; rỗng → None; quá 120 → 422.

    Viết "Siêu âm › Siêu âm thai" hay "Siêu âm>>Siêu âm thai" đều lưu dạng
    KiotViet (">>") — cùng dạng với danh mục chuẩn đã nạp."""
    s = " ".join((v or "").split())
    if not s:
        return None
    s = ">>".join(p.strip() for p in s.replace("›", ">>").split(">>") if p.strip())
    if len(s) > 120:
        raise ValidationError("Nhóm hàng tối đa 120 ký tự.")
    return s or None


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
                SELECT id, service_code, name, "group", unit_price, active,
                       ma_kiotviet, node_code, gia_tam, billing_owner,
                       billing_owner_chon_tay
                  FROM service_price
                 WHERE clinic_id = $1::uuid AND "group" = $2
                 ORDER BY coalesce(ma_kiotviet, service_code)
                """,
                identity.clinic_id,
                group,
            )
            # asyncpg giải numeric có số 0 cuối thành Decimal('9.0E+5') — màn Bảng
            # giá hiện nguyên "9.0E+5" trong ô đơn giá (bấm thật 26/09/2026).
            # Tiền đồng luôn là số nguyên: trả dạng thường.
            return [
                {**dict(r), "unit_price": _gia_thuong(r["unit_price"])} for r in rows
            ]

    @staticmethod
    async def _dong_bo_gia_danh_muc_thuoc(
        conn: asyncpg.Connection, clinic_id: str, ten: str, gia: Any
    ) -> int:
        """Giá thuốc sửa ở màn Bảng giá thuốc → danh mục thuốc CÙNG TÊN CHUẨN.

        Hoá đơn (`bill_service`, HOLD J5) lấy giá ở CẢ HAI nguồn — lệch nhau là
        dòng thuốc "mâu thuẫn giá", không thu được. Màn chỉ sửa `service_price`,
        nên sửa ở đây mà danh mục không theo là tự khoá quầy (24/09). Ghép tên
        đúng cách hoá đơn ghép (`norm_name` của name_base / name_raw).
        """
        from clinicai.services.cashier_board_service import norm_name

        khoa = norm_name(ten)
        if not khoa:
            return 0
        ids = [
            r["id"]
            for r in await conn.fetch(
                "SELECT id, name_base, name_raw FROM drug_catalog"
                " WHERE clinic_id = $1::uuid",
                clinic_id,
            )
            if khoa in {norm_name(r["name_base"]), norm_name(r["name_raw"])}
        ]
        if ids:
            await conn.execute(
                "UPDATE drug_catalog SET unit_price = $2"
                " WHERE clinic_id = $3::uuid AND id = ANY($1::uuid[])"
                " AND unit_price IS DISTINCT FROM $2",
                ids,
                gia,
                clinic_id,
            )
        return len(ids)

    async def add(
        self,
        *,
        service_code: str,
        name: str,
        group: PriceGroup,
        unit_price: Any,
        identity: StaffIdentity,
        ma_kiotviet: str | None = None,
        node_code: str | None = None,
        billing_owner: str | None = None,
        nhom: str | None = None,
    ) -> str:
        ma_kv = _ma_kiotviet(ma_kiotviet)
        nhom_hang = _nhom_hang(nhom)
        ben_chon = doc_ben_thu(billing_owner)
        label = (name or "").strip()
        code = (
            (service_code or "").strip()
            or (f"KV_{ma_kv}" if ma_kv else "")
            # Dịch vụ không mã phòng khám (01/10/2026): mã nội bộ ổn định từ tên
            # — cùng cách migration danh mục chuẩn sinh `DV_<md5 tên>`.
            or (ma_dich_vu_theo_ten(label) if group == "dich_vu" and label else "")
        )
        if not code or not label:
            raise ValidationError("Thiếu mã hoặc tên dịch vụ")

        price = parse_price(unit_price)
        async with self._pool.acquire() as conn, conn.transaction():
            node = await self._phong_hop_le(conn, identity.clinic_id, node_code)
            # Chọn tay khi tạo → giữ và đánh dấu; không chọn → suy theo phòng làm.
            ben_thu = ben_chon or await self._ben_thu_theo_phong(
                conn, identity.clinic_id, node
            )
            try:
                row_id = await conn.fetchval(
                    """
                    INSERT INTO service_price
                        (clinic_id, service_code, name, "group", unit_price,
                         ma_kiotviet, node_code, billing_owner,
                         billing_owner_chon_tay, category)
                    VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    RETURNING id
                    """,
                    identity.clinic_id,
                    code,
                    label,
                    group,
                    price,
                    ma_kv,
                    node,
                    ben_thu,
                    ben_chon is not None,
                    nhom_hang,
                )
            except asyncpg.UniqueViolationError as exc:
                raise ConflictError(
                    f"Mã {ma_kv or code} đã có trong bảng giá — tìm dòng ấy mà sửa."
                ) from exc
            if group == "thuoc" and price is not None:
                await self._dong_bo_gia_danh_muc_thuoc(
                    conn, identity.clinic_id, label, price
                )
        return str(row_id)

    @staticmethod
    async def _ben_thu_theo_phong(
        conn: asyncpg.Connection, clinic_id: str, node: str | None
    ) -> str:
        """MẶC ĐỊNH bên thu: EXTERNAL_PARTNER khi phòng làm là bước làm bên
        ngoài, còn lại CLINIC (cùng luật migration 20260928000091). Chỉ dùng khi
        dòng CHƯA được chọn tay (`billing_owner_chon_tay`) — 29/09/2026."""
        if not node:
            return "CLINIC"
        ngoai = await conn.fetchval(
            "SELECT lam_ben_ngoai FROM node_definition"
            " WHERE clinic_id = $1::uuid AND code = $2",
            clinic_id,
            node,
        )
        return "EXTERNAL_PARTNER" if ngoai else "CLINIC"

    async def update(
        self,
        *,
        price_id: str,
        identity: StaffIdentity,
        name: str | None = None,
        unit_price: Any = None,
        unit_price_provided: bool = False,
        active: bool | None = None,
        ma_kiotviet: str | None = None,
        ma_kiotviet_provided: bool = False,
        node_code: str | None = None,
        billing_owner: str | None = None,
        nhom: str | None = None,
        nhom_provided: bool = False,
    ) -> None:
        patch: dict[str, Any] = {}
        if nhom_provided:
            # Nhóm hàng (01/10/2026) — gom danh mục chỉ định; rỗng = bỏ nhóm.
            patch["category"] = _nhom_hang(nhom)
        ben_chon = doc_ben_thu(billing_owner)
        if ben_chon is not None:
            # CHỌN TAY (Tuyền 29/09/2026): bên thu thuộc từng dịch vụ, và từ nay
            # đổi phòng làm không lật lại lựa chọn này.
            patch["billing_owner"] = ben_chon
            patch["billing_owner_chon_tay"] = True
        if name is not None and name.strip():
            patch["name"] = name.strip()
        if unit_price_provided:
            patch["unit_price"] = parse_price(unit_price)
            # GIÁ TẠM (Q2, 27/09/2026): quản lý sửa / lưu lại đơn giá = đã xác
            # nhận → bỏ chip "Giá tạm — cần xác nhận".
            patch["gia_tam"] = False
        if active is not None:
            patch["active"] = active
        if ma_kiotviet_provided:
            # Rỗng = gỡ mã (dịch vụ chỉ có trên hệ thống).
            patch["ma_kiotviet"] = _ma_kiotviet(ma_kiotviet)
        if not patch and node_code is None:
            raise ValidationError("Không có gì để sửa")

        async with self._pool.acquire() as conn, conn.transaction():
            if node_code is not None:
                patch["node_code"] = await self._phong_hop_le(
                    conn, identity.clinic_id, node_code
                )
                # Bên thu theo PHÒNG LÀM (Q1, 27/09/2026) chỉ là MẶC ĐỊNH: dòng
                # đã chọn tay (cờ trong database, hay chọn ngay trong lần sửa
                # này) giữ nguyên bên thu — 29/09/2026.
                chon_tay = ben_chon is not None or bool(
                    await conn.fetchval(
                        "SELECT billing_owner_chon_tay FROM service_price"
                        " WHERE id = $1::uuid AND clinic_id = $2::uuid FOR UPDATE",
                        price_id,
                        identity.clinic_id,
                    )
                )
                if not chon_tay:
                    patch["billing_owner"] = await self._ben_thu_theo_phong(
                        conn, identity.clinic_id, patch["node_code"]
                    )
            columns = list(patch)
            assignments = ", ".join(f"{c} = ${i + 3}" for i, c in enumerate(columns))
            try:
                updated = await conn.fetchrow(
                    f"""
                    UPDATE service_price SET {assignments}, updated_at = now()
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                    RETURNING id, "group", name, unit_price
                    """,
                    price_id,
                    identity.clinic_id,
                    *[patch[c] for c in columns],
                )
            except asyncpg.UniqueViolationError as exc:
                raise ConflictError(
                    f"Mã {patch.get('ma_kiotviet')} đã gắn cho dịch vụ khác."
                ) from exc
            if updated is None:
                raise NotFoundError("Không tìm thấy dòng giá")
            if (
                updated["group"] == "thuoc"
                and unit_price_provided
                and updated["unit_price"] is not None
            ):
                await self._dong_bo_gia_danh_muc_thuoc(
                    conn, identity.clinic_id, updated["name"], updated["unit_price"]
                )

    async def phong_lam(
        self, *, identity: StaffIdentity
    ) -> builtins.list[dict[str, str]]:
        """Phòng làm (node dịch vụ đang bật) để chọn cho một dịch vụ."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT code, name FROM node_definition"
                " WHERE clinic_id = $1::uuid AND code LIKE 'DICHVU-%'"
                " ORDER BY name",
                identity.clinic_id,
            )
        return [{"ma": r["code"], "ten": r["name"]} for r in rows]

    @staticmethod
    async def _phong_hop_le(
        conn: asyncpg.Connection, clinic_id: str, node_code: str | None
    ) -> str | None:
        """Rỗng = chưa chọn phòng; mã lạ → 422 (không để khoá ngoại ném 500)."""
        ma = (node_code or "").strip()
        if not ma:
            return None
        if not await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM node_definition"
            " WHERE clinic_id = $1::uuid AND code = $2)",
            clinic_id,
            ma,
        ):
            raise ValidationError("Phòng làm không hợp lệ.")
        return ma

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
