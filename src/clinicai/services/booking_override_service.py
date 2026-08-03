"""Luật số chỗ đặt lịch — MỘT khái niệm cho người dùng, hai bảng bên dưới.

MỘT LUẬT LÀ MỘT CÂU: *"ai — thứ mấy — khung giờ nào — mấy chỗ — áp dụng tới bao
giờ"*. Ví dụ của phòng khám:

    tất cả bác sĩ · mọi thứ  · 15 phút một khung · 3 đặt trước + 1 vãng lai · mãi mãi
    BS Thành, BS Hoa · thứ 3 · 18:00–18:15      · 8 đặt trước + 1 vãng lai · mãi mãi
    BS Thành         · —      · 18:00–19:00     · 5 đặt trước + 2 vãng lai · 03/08–09/08

Ba dòng đó ở cùng một bảng trên màn hình. Bên dưới chúng nằm ở hai bảng khác
nhau, và ``save_rule()`` chọn hộ:

  Tầng 3  ``slot_booking_override``    có khoảng NGÀY  → luật tạm, hết hạn thì thôi
  Tầng 2  ``doctor_booking_override``  không có ngày   → luật thường trực, lặp mãi
  Tầng 1  ``clinic.settings.booking``  mặc định phòng khám

VÌ SAO NGƯỜI DÙNG KHÔNG NÊN THẤY BA TẦNG. Bản trước phơi tầng 2 và tầng 3 thành
hai tab riêng, và Quang hỏi đúng câu phải hỏi: *"tại sao không cho vào một khung
thiết lập chung?"* Ba tầng là cách LƯU, không phải cách NGHĨ. Bắt người vận hành
chọn tab nghĩa là bắt họ học cấu trúc bảng trước khi đặt được một con số.

THỨ TỰ ƯU TIÊN khi nhiều luật cùng phủ một khung — ``resolve_effective_cap()``
quyết định, và nó đọc từ cụ thể nhất tới chung nhất:

  1. luật CÓ NGÀY thắng luật MÃI MÃI   ("tuần này BS bận" phải đè luật thường ngày)
  2. luật ghi rõ BÁC SĨ thắng luật "tất cả bác sĩ"
  3. luật ghi rõ THỨ thắng luật "mọi thứ"
  4. không luật nào phủ → mặc định phòng khám

Trong CÙNG một loại thì hai luật không được phủ cùng khung (ràng buộc EXCLUDE),
và lưu luật mới sẽ CẮT luật cũ thay vì báo lỗi — xem ``plan_window_trim``.

Mọi lần ghi đều gắn với phòng khám của người ghi (``identity.clinic_id``) và vào
``event_log``. CHECK trong database mới là chốt chặn thật; Python kiểm sớm để một
con số sai thành câu tiếng Việt thay vì tên ràng buộc.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()

# Safety ceiling: overrides cannot exceed these (mirrors DB CHECK).
MAX_CAP = 100
# Max date range for slot overrides (mirrors DB CHECK).
MAX_SLOT_RANGE_DAYS = 90


# ── Cắt khoảng phút ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WindowTrim:
    """Chuyện gì xảy ra với MỘT luật cũ khi một luật mới phủ lên nó."""

    action: str  # "deleted" | "trimmed" | "split"
    keep: tuple[int, int] | None
    keep_extra: tuple[int, int] | None = None


def plan_window_trim(
    old_start: int, old_end: int, new_start: int, new_end: int
) -> WindowTrim:
    """Phần nào của luật cũ sống sót khi khung ``[new_start, new_end)`` chiếm chỗ.

    Tách khỏi phần chạy SQL vì đây là chỗ dễ sai nhất và cũng dễ kiểm nhất:
    bốn nhánh, toàn số nguyên, không cần database. Ghép chung với INSERT/UPDATE
    thì muốn thử một trường hợp biên phải dựng cả một phòng khám.

    Mọi khoảng đều NỬA MỞ ``[start, end)`` — cùng quy ước với int4range trong
    ràng buộc EXCLUDE và với ``resolve_effective_cap`` (``>= start AND < end``).
    Nhờ vậy hai khung liền kề (18:00–18:15 và 18:15–18:30) KHÔNG coi là chồng
    lấn, và luật cũ bị cắt tới đúng mốc của luật mới không để lại phút hở.
    """
    if old_start >= new_start and old_end <= new_end:
        # Nằm trọn bên trong — không còn gì để giữ.
        return WindowTrim(action="deleted", keep=None)
    if old_start < new_start and old_end > new_end:
        # Khung mới nằm giữa: cắt đôi.
        return WindowTrim(
            action="split",
            keep=(old_start, new_start),
            keep_extra=(new_end, old_end),
        )
    if old_start < new_start:
        # Thò đầu bên trái.
        return WindowTrim(action="trimmed", keep=(old_start, new_start))
    # Thò đuôi bên phải.
    return WindowTrim(action="trimmed", keep=(new_end, old_end))


def validate_rule(
    *,
    weekday: int | None,
    minute_start: int,
    minute_end: int,
    regular_cap: int,
    walkin_cap: int,
    date_start: date | None,
    date_end: date | None,
) -> None:
    """Một luật có nói được thành câu không — kiểm trước khi chạm database.

    Cùng luật với các CHECK trong database, nhưng trả về câu tiếng Việt thay vì
    tên ràng buộc. Tách khỏi ``save_rule`` để thử được mà không cần phòng khám:
    đây là chỗ duy nhất biết vì sao 18:07 bị từ chối.
    """
    if (date_start is None) != (date_end is None):
        raise ValidationError("Phải có cả ngày bắt đầu và ngày kết thúc.")

    if not 0 <= minute_start <= 1439:
        raise ValidationError("Giờ bắt đầu không hợp lệ.")
    if not 1 <= minute_end <= 1440:
        raise ValidationError("Giờ kết thúc không hợp lệ.")
    if minute_end <= minute_start:
        raise ValidationError("Giờ kết thúc phải sau giờ bắt đầu.")
    # Bội số 5: mọi độ dài khung hợp lệ (chia hết 60) là bội số của 5, nên một
    # mốc lẻ chắc chắn cắt ngang một khung và để lại vùng không luật nào phủ —
    # một khoảng hở âm thầm, không báo lỗi.
    if minute_start % 5 or minute_end % 5:
        raise ValidationError("Mốc giờ phải theo bội số 5 phút.")

    if weekday is not None and not 0 <= weekday <= 6:
        raise ValidationError("Thứ không hợp lệ.")
    if not 1 <= regular_cap <= MAX_CAP:
        raise ValidationError(f"Số ca đặt trước phải từ 1 đến {MAX_CAP}.")
    if not 0 <= walkin_cap <= MAX_CAP:
        raise ValidationError(f"Số ca vãng lai phải từ 0 đến {MAX_CAP}.")

    if date_start is not None and date_end is not None:
        if date_end < date_start:
            raise ValidationError("Ngày kết thúc phải sau ngày bắt đầu.")
        if (date_end - date_start).days > MAX_SLOT_RANGE_DAYS:
            raise ValidationError(
                f"Khoảng ngày tối đa {MAX_SLOT_RANGE_DAYS} ngày. Cần lâu hơn thì"
                " chọn “Mãi mãi”."
            )
        # Tầng 3 không có cột weekday. Thà nói ra còn hơn nhận rồi bỏ qua — một
        # ô người dùng điền mà hệ thống lờ đi là dạng sai tệ nhất.
        if weekday is not None:
            raise ValidationError(
                "Luật có khoảng ngày thì áp cho mọi ngày trong khoảng đó, không"
                " chọn riêng thứ được."
            )


# ── Service ────────────────────────────────────────────────────────────────

class BookingOverrideService:
    """Đọc và ghi luật số chỗ đặt lịch. Xem docstring đầu file."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Một luật, một đường ghi ────────────────────────────────────────

    async def save_rule(
        self,
        *,
        identity: StaffIdentity,
        doctor_ids: list[str],
        weekday: int | None,
        minute_start: int,
        minute_end: int,
        regular_cap: int,
        walkin_cap: int,
        date_start: date | None,
        date_end: date | None,
        reason: str | None,
    ) -> dict[str, Any]:
        """Ghi một luật cho một hoặc nhiều bác sĩ, trong MỘT giao dịch.

        ``doctor_ids`` rỗng = áp cho mọi bác sĩ (một dòng, ``doctor_id`` NULL).
        Nhiều bác sĩ = nhiều dòng, vì mỗi bác sĩ có thể bị sửa hoặc xoá riêng về
        sau; gộp họ vào một dòng sẽ khiến "bỏ BS Hoa ra" thành một thao tác
        không làm được.

        Có ``date_start``/``date_end`` ⇒ luật TẠM (tầng 3). Không có ⇒ luật
        THƯỜNG TRỰC (tầng 2). Người dùng chỉ chọn "Mãi mãi" hay một khoảng ngày;
        họ không cần biết có hai bảng.

        Một giao dịch cho cả nhóm: chọn hai bác sĩ mà chỉ ghi được một là trạng
        thái tệ hơn không ghi được gì — màn hình báo lỗi trong khi một nửa thay
        đổi đã nằm trong database.
        """
        validate_rule(
            weekday=weekday,
            minute_start=minute_start,
            minute_end=minute_end,
            regular_cap=regular_cap,
            walkin_cap=walkin_cap,
            date_start=date_start,
            date_end=date_end,
        )

        # Rỗng ⇒ một dòng doctor_id NULL = mọi bác sĩ.
        targets: list[str | None] = list(doctor_ids) if doctor_ids else [None]
        results: list[dict[str, Any]] = []

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for doctor_id in targets:
                    if doctor_id:
                        await self._assert_doctor_in_clinic(
                            conn, clinic_id=identity.clinic_id, doctor_id=doctor_id
                        )
                    if date_start is not None and date_end is not None:
                        one = await self._write_temp(
                            conn,
                            identity=identity,
                            doctor_id=doctor_id,
                            date_start=date_start,
                            date_end=date_end,
                            minute_start=minute_start,
                            minute_end=minute_end,
                            regular_cap=regular_cap,
                            walkin_cap=walkin_cap,
                            reason=reason or "Điều chỉnh khung giờ",
                        )
                    else:
                        one = await self._write_standing(
                            conn,
                            identity=identity,
                            doctor_id=doctor_id,
                            weekday=weekday,
                            minute_start=minute_start,
                            minute_end=minute_end,
                            regular_cap=regular_cap,
                            walkin_cap=walkin_cap,
                            reason=reason,
                        )
                    results.append(one)

        logger.info(
            "booking_rule_saved",
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
            kind="temp" if date_start else "standing",
            doctors=len(targets),
            replaced=sum(len(r["replaced"]) for r in results),
        )
        return {
            "ok": True,
            "saved": results,
            # Gộp cảnh báo "luật này đang bị đè" của mọi bác sĩ vừa ghi. Màn
            # hình chỉ cần biết CÓ hay KHÔNG và tới ngày nào.
            "shadowed_by": [s for r in results for s in r["shadowed_by"]],
        }

    async def list_rules(
        self, *, identity: StaffIdentity
    ) -> list[dict[str, Any]]:
        """Mọi luật đang còn hiệu lực, HAI TẦNG GỘP LÀM MỘT DANH SÁCH.

        Người vận hành hỏi "phòng khám đang có những luật gì" và phải nhận được
        MỘT câu trả lời. Trước đây câu đó nằm ở hai bảng trên hai tab, nên không
        có chỗ nào nhìn thấy được cả hai cùng lúc — và cũng không có chỗ nào cho
        thấy luật tạm đang đè lên luật thường trực nào.

        ``shadowed`` = luật thường trực này đang bị một luật CÓ NGÀY phủ lên,
        nên hôm nay nó KHÔNG phải con số có hiệu lực. Tính ở đây một lần, thay
        vì để giao diện tự suy ra thứ tự ưu tiên và nói lệch với backend.

        Chỉ gắn cờ khi luật tạm phủ ĐÚNG tập bác sĩ ấy: luật tạm cho mọi bác sĩ
        đè lên tất cả, luật tạm của một bác sĩ chỉ đè luật của chính bác sĩ đó.
        Bản đầu còn gắn cờ khi luật thường trực là "tất cả bác sĩ" và luật tạm
        chỉ của MỘT người — sai, vì luật ấy vẫn đang chạy cho những bác sĩ còn
        lại. Một nhãn cảnh báo sai chỗ dạy người dùng bỏ qua mọi nhãn cảnh báo.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH temp AS (
                    SELECT id, doctor_id, NULL::smallint AS weekday,
                           minute_start, minute_end, regular_cap, walkin_cap,
                           reason, date_start, date_end, created_at
                      FROM slot_booking_override
                     WHERE clinic_id = $1::uuid AND date_end >= current_date
                ),
                standing AS (
                    SELECT id, doctor_id, weekday,
                           coalesce(minute_start, 0)    AS minute_start,
                           coalesce(minute_end, 1440)   AS minute_end,
                           regular_cap, walkin_cap, reason,
                           NULL::date AS date_start, NULL::date AS date_end,
                           created_at
                      FROM doctor_booking_override
                     WHERE clinic_id = $1::uuid
                       AND (effective_to IS NULL OR effective_to >= current_date)
                )
                SELECT 'temp' AS kind, t.*, FALSE AS shadowed FROM temp t
                UNION ALL
                SELECT 'standing', s.*,
                       EXISTS (
                           SELECT 1 FROM temp x
                            WHERE (x.doctor_id IS NULL
                                   OR x.doctor_id = s.doctor_id)
                              AND int4range(x.minute_start, x.minute_end)
                               && int4range(s.minute_start, s.minute_end)
                       )
                  FROM standing s
                 ORDER BY 1, minute_start, weekday NULLS FIRST
                """,
                identity.clinic_id,
            )
        return [
            {
                "id": str(r["id"]),
                "kind": r["kind"],
                "doctor_id": str(r["doctor_id"]) if r["doctor_id"] else None,
                "weekday": r["weekday"],
                "minute_start": r["minute_start"],
                "minute_end": r["minute_end"],
                "regular_cap": r["regular_cap"],
                "walkin_cap": r["walkin_cap"],
                "reason": r["reason"],
                "date_start": r["date_start"].isoformat() if r["date_start"] else None,
                "date_end": r["date_end"].isoformat() if r["date_end"] else None,
                "shadowed": r["shadowed"],
            }
            for r in rows
        ]

    # ── Người ghi từng tầng (dùng chung một conn/giao dịch) ─────────────

    async def _write_standing(
        self,
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        doctor_id: str | None,
        weekday: int | None,
        minute_start: int,
        minute_end: int,
        regular_cap: int,
        walkin_cap: int,
        reason: str | None,
    ) -> dict[str, Any]:
        """Luật THƯỜNG TRỰC (tầng 2) — LUẬT MỚI THẮNG.

        Không phải "create". Trưởng ca nói *"BS Thành, 18:00–18:15, 9 ca"* và
        điều đó phải trở thành sự thật, kể cả khi đã có luật khác phủ khung ấy.
        Bản trước chỉ INSERT, nên lần lưu thứ hai đụng ràng buộc
        ``doctor_override_no_overlap`` và trả về — qua handler toàn cục —
        *"Lịch hẹn xung đột khung giờ với appointment khác"*: một câu nói về
        LỊCH HẸN cho người đang sửa LUẬT, và không có lịch hẹn nào để đi tìm.

        Ràng buộc EXCLUDE vẫn đúng và vẫn còn: hai luật cùng phủ một khung thì
        không phải "luật nào thắng" mà là không có luật nào. Chỗ sai là bắt
        người dùng tự dọn. Ở đây luật cũ bị CẮT quanh khung mới:

            cũ  18:00 ─────────────── 19:00   (4 ca)
            mới        18:15 ─ 18:30          (9 ca)
            ⇒   18:00 ─ 18:15 (4)  18:15 ─ 18:30 (9)  18:30 ─ 19:00 (4)

        Chỉ cắt luật CÙNG bác sĩ và CÙNG thứ — nên "BS Thành thứ 3" không đụng
        tới "tất cả bác sĩ mọi thứ". Hai luật đó cùng tồn tại, và
        ``resolve_effective_cap`` chọn cái cụ thể hơn.
        """
        eff_from = date.today()
        replaced = await self._clear_minute_window(
            conn,
            clinic_id=identity.clinic_id,
            doctor_id=doctor_id,
            weekday=weekday,
            effective_from=eff_from,
            effective_to=None,
            minute_start=minute_start,
            minute_end=minute_end,
        )

        override_id = await conn.fetchval(
            """
            INSERT INTO doctor_booking_override
                (clinic_id, doctor_id, weekday, minute_start, minute_end,
                 regular_cap, walkin_cap, effective_from, created_by, reason)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9::uuid, $10)
            RETURNING id
            """,
            identity.clinic_id,
            doctor_id,
            weekday,
            minute_start,
            minute_end,
            regular_cap,
            walkin_cap,
            eff_from,
            identity.auth_user_id,
            reason,
        )

        # MỘT LUẬT ĐÚNG VẪN CÓ THỂ KHÔNG CÓ TÁC DỤNG HÔM NAY.
        #
        # Luật có ngày đè lên luật thường trực. Nên nếu còn một luật tạm phủ
        # đúng khung vừa lưu, Trưởng ca sẽ lưu thành công, quay ra lưới, và
        # KHÔNG THẤY GÌ ĐỔI — rồi kết luận là chức năng hỏng. Prod đang có đúng
        # một dòng như thế cho BS Thành (18:00–19:00, hết hạn 09/08).
        #
        # Không tự xoá nó: một luật tạm có lý do và có người chịu trách nhiệm.
        # Chỉ nói ra.
        shadowed = await self._find_shadowing_exceptions(
            conn,
            clinic_id=identity.clinic_id,
            doctor_id=doctor_id,
            minute_start=minute_start,
            minute_end=minute_end,
        )

        await self._log_event(
            conn,
            identity=identity,
            event_type="booking_override.doctor_created",
            payload={
                "override_id": str(override_id),
                "doctor_id": doctor_id,
                "weekday": weekday,
                "minute_start": minute_start,
                "minute_end": minute_end,
                "regular_cap": regular_cap,
                "walkin_cap": walkin_cap,
                "effective_from": str(eff_from),
                "reason": reason,
                # Luật cũ nào bị cắt/xoá để chỗ cho luật này. Không có nút nào
                # tạo ra dòng này, nên nếu không ghi ở đây thì nó biến mất
                # không dấu vết.
                "replaced": replaced,
            },
        )
        return {
            "id": str(override_id),
            "kind": "standing",
            "doctor_id": doctor_id,
            "replaced": replaced,
            "shadowed_by": shadowed,
        }

    async def _write_temp(
        self,
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        doctor_id: str | None,
        date_start: date,
        date_end: date,
        minute_start: int,
        minute_end: int,
        regular_cap: int,
        walkin_cap: int,
        reason: str,
    ) -> dict[str, Any]:
        """Luật TẠM (tầng 3) — có khoảng ngày, hết hạn thì tự hết tác dụng."""
        try:
            override_id = await conn.fetchval(
                """
                INSERT INTO slot_booking_override
                    (clinic_id, doctor_id, date_start, date_end,
                     minute_start, minute_end, regular_cap, walkin_cap,
                     reason, created_by)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10::uuid)
                RETURNING id
                """,
                identity.clinic_id,
                doctor_id,
                date_start,
                date_end,
                minute_start,
                minute_end,
                regular_cap,
                walkin_cap,
                reason,
                identity.auth_user_id,
            )
        except asyncpg.ExclusionViolationError as exc:
            # PHẢI BẮT Ở ĐÂY. main.py có handler toàn cục cho
            # ExclusionViolationError; nó đã biết phân biệt theo tên ràng buộc,
            # nhưng chỉ ở đây mới nói được luật NÀO đang chiếm khung — tên ràng
            # buộc không mang theo dòng mà nó va phải.
            overlapping = await self._find_overlap(
                conn,
                clinic_id=identity.clinic_id,
                doctor_id=doctor_id,
                date_start=date_start,
                date_end=date_end,
                minute_start=minute_start,
                minute_end=minute_end,
            )
            raise ValidationError(
                "Đã có một luật có ngày khác phủ khung giờ này"
                + (f" ({overlapping})" if overlapping else "")
                + ". Xoá nó ở bảng bên dưới rồi lưu lại — hai luật cho cùng một"
                " khung thì không có cách nào biết luật nào đúng."
            ) from exc

        await self._log_event(
            conn,
            identity=identity,
            event_type="booking_override.slot_created",
            payload={
                "override_id": str(override_id),
                "doctor_id": doctor_id,
                "date_start": str(date_start),
                "date_end": str(date_end),
                "minute_start": minute_start,
                "minute_end": minute_end,
                "regular_cap": regular_cap,
                "walkin_cap": walkin_cap,
                "reason": reason,
            },
        )
        return {
            "id": str(override_id),
            "kind": "temp",
            "doctor_id": doctor_id,
            "replaced": [],
            # Luật tạm là tầng cao nhất — không có gì đè lên nó được.
            "shadowed_by": [],
        }

    @staticmethod
    async def _assert_doctor_in_clinic(
        conn: asyncpg.Connection, *, clinic_id: str, doctor_id: str
    ) -> None:
        exists = await conn.fetchval(
            """
            SELECT 1 FROM clinic_membership
             WHERE clinic_id = $1::uuid AND staff_id = $2::uuid AND is_active = true
            """,
            clinic_id,
            doctor_id,
        )
        if not exists:
            raise ValidationError(
                "Bác sĩ không thuộc phòng khám này hoặc đã bị vô hiệu."
            )

    # ── Xoá ────────────────────────────────────────────────────────────
    # Hai đường vì hai bảng. Danh sách luật mang theo `kind`, nên giao diện gọi
    # đúng đường mà không phải đoán — người dùng vẫn chỉ thấy một nút "Xoá".

    async def delete_doctor_override(
        self,
        *,
        identity: StaffIdentity,
        override_id: str,
    ) -> None:
        """Delete a doctor override by id."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                deleted = await conn.fetchval(
                    """
                    DELETE FROM doctor_booking_override
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                    RETURNING id
                    """,
                    override_id,
                    identity.clinic_id,
                )
                if deleted is None:
                    raise NotFoundError("Override không tồn tại.")

                await self._log_event(
                    conn,
                    identity=identity,
                    event_type="booking_override.doctor_deleted",
                    payload={"override_id": override_id},
                )

        logger.info(
            "doctor_override_deleted",
            override_id=override_id,
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
        )

    # ── Slot overrides (Tầng 3) ────────────────────────────────────────

    async def delete_slot_override(
        self,
        *,
        identity: StaffIdentity,
        override_id: str,
    ) -> None:
        """Delete a slot override by id."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                deleted = await conn.fetchval(
                    """
                    DELETE FROM slot_booking_override
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                    RETURNING id
                    """,
                    override_id,
                    identity.clinic_id,
                )
                if deleted is None:
                    raise NotFoundError("Override không tồn tại.")

                await self._log_event(
                    conn,
                    identity=identity,
                    event_type="booking_override.slot_deleted",
                    payload={"override_id": override_id},
                )

        logger.info(
            "slot_override_deleted",
            override_id=override_id,
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
        )

    # ── Internals ──────────────────────────────────────────────────────

    @staticmethod
    async def _clear_minute_window(
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        doctor_id: str | None,
        weekday: int | None,
        effective_from: date,
        effective_to: date | None,
        minute_start: int | None,
        minute_end: int | None,
    ) -> list[dict[str, Any]]:
        """Dọn đúng khoảng phút mà luật mới sắp chiếm, giữ nguyên phần còn lại.

        Chỉ đụng những luật mà ràng buộc EXCLUDE coi là chồng lấn — cùng phòng
        khám, cùng bác sĩ (NULL = mọi bác sĩ, và NULL chỉ chồng với NULL), cùng
        thứ, khoảng NGÀY giao nhau. Luật của bác sĩ khác, thứ khác hay đợt hiệu
        lực khác không bị chạm tới.

        Cắt theo TRỤC PHÚT, không theo trục ngày. Giao diện luôn ghi luật thường
        trực từ hôm nay và không có ngày kết thúc, nên trục ngày không có gì để
        cắt; làm cả hai trục sẽ sinh ra tới chín mảnh cho một thao tác và không
        ai đọc nổi bảng luật sau đó.
        """
        # NULL = cả ngày. Quy về [0, 1440) một lần ở đây để bốn nhánh bên dưới
        # chỉ phải nghĩ về số, giống hệt cách EXCLUDE coalesce trong chỉ mục.
        new_start = 0 if minute_start is None else minute_start
        new_end = 1440 if minute_end is None else minute_end

        rows = await conn.fetch(
            """
            SELECT id, minute_start, minute_end, regular_cap, walkin_cap,
                   slot_minutes, effective_from, effective_to, reason
              FROM doctor_booking_override
             WHERE clinic_id = $1::uuid
               AND coalesce(doctor_id, '00000000-0000-0000-0000-000000000000')
                 = coalesce($2::uuid, '00000000-0000-0000-0000-000000000000')
               AND coalesce(weekday, -1) = coalesce($3::int, -1)
               AND daterange(effective_from, effective_to, '[]')
                && daterange($4::date, $5::date, '[]')
               AND int4range(coalesce(minute_start, 0), coalesce(minute_end, 1440))
                && int4range($6, $7)
             FOR UPDATE
            """,
            clinic_id,
            doctor_id,
            weekday,
            effective_from,
            effective_to,
            new_start,
            new_end,
        )

        replaced: list[dict[str, Any]] = []
        for r in rows:
            old_start = 0 if r["minute_start"] is None else r["minute_start"]
            old_end = 1440 if r["minute_end"] is None else r["minute_end"]
            plan = plan_window_trim(old_start, old_end, new_start, new_end)

            if plan.action == "deleted":
                await conn.execute(
                    "DELETE FROM doctor_booking_override WHERE id = $1", r["id"]
                )
            else:
                assert plan.keep is not None  # noqa: S101 — plan_window_trim đảm bảo
                await conn.execute(
                    "UPDATE doctor_booking_override SET minute_start = $2,"
                    " minute_end = $3 WHERE id = $1",
                    r["id"],
                    plan.keep[0],
                    plan.keep[1],
                )
            if plan.keep_extra is not None:
                # Mảnh thứ hai của một luật bị cắt đôi. Copy từ chính dòng vừa
                # thu hẹp nên mọi trường khác (số chỗ, hiệu lực, lý do, người
                # tạo) đi theo — liệt kê tay ở đây là chỗ để quên một cột.
                await conn.execute(
                    """
                    INSERT INTO doctor_booking_override
                        (clinic_id, doctor_id, weekday, minute_start, minute_end,
                         slot_minutes, regular_cap, walkin_cap,
                         effective_from, effective_to, created_by, reason)
                    SELECT clinic_id, doctor_id, weekday, $2, $3,
                           slot_minutes, regular_cap, walkin_cap,
                           effective_from, effective_to, created_by, reason
                      FROM doctor_booking_override WHERE id = $1
                    """,
                    r["id"],
                    plan.keep_extra[0],
                    plan.keep_extra[1],
                )

            replaced.append(
                {
                    "id": str(r["id"]),
                    "action": plan.action,
                    "was": [old_start, old_end],
                    "kept": [
                        list(w)
                        for w in (plan.keep, plan.keep_extra)
                        if w is not None
                    ],
                    "regular_cap": r["regular_cap"],
                    "walkin_cap": r["walkin_cap"],
                    "reason": r["reason"],
                }
            )

        return replaced

    @staticmethod
    async def _find_shadowing_exceptions(
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        doctor_id: str | None,
        minute_start: int | None,
        minute_end: int | None,
    ) -> list[dict[str, Any]]:
        """Ngoại lệ tạm thời (tầng 3) còn hiệu lực đang phủ khung này.

        Chỉ đọc, không sửa. Câu trả lời đi thẳng lên màn hình để "đã lưu" không
        bị hiểu thành "đã có tác dụng ngay".
        """
        start = 0 if minute_start is None else minute_start
        end = 1440 if minute_end is None else minute_end
        rows = await conn.fetch(
            """
            SELECT date_start, date_end, minute_start, minute_end,
                   regular_cap, walkin_cap, reason
              FROM slot_booking_override
             WHERE clinic_id = $1::uuid
               AND (doctor_id = $2::uuid OR doctor_id IS NULL)
               AND date_end >= current_date
               AND int4range(minute_start, minute_end) && int4range($3, $4)
             ORDER BY date_start, minute_start
            """,
            clinic_id,
            doctor_id,
            start,
            end,
        )
        return [
            {
                "date_start": r["date_start"].isoformat(),
                "date_end": r["date_end"].isoformat(),
                "minute_start": r["minute_start"],
                "minute_end": r["minute_end"],
                "regular_cap": r["regular_cap"],
                "walkin_cap": r["walkin_cap"],
                "reason": r["reason"],
            }
            for r in rows
        ]

    @staticmethod
    async def _find_overlap(
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        doctor_id: str | None,
        date_start: date,
        date_end: date,
        minute_start: int,
        minute_end: int,
    ) -> str | None:
        """Describe the rule that already covers this window, for the error text.

        The EXCLUDE constraint names itself, not the row it collided with. A
        person who has to go and fix the other rule needs to know which one it
        is; "slot_override_no_overlap" tells them nothing.
        """
        row = await conn.fetchrow(
            """
            SELECT date_start, date_end, minute_start, minute_end, reason
              FROM slot_booking_override
             WHERE clinic_id = $1::uuid
               AND coalesce(doctor_id, '00000000-0000-0000-0000-000000000000')
                 = coalesce($2::uuid, '00000000-0000-0000-0000-000000000000')
               AND daterange(date_start, date_end, '[]')
                && daterange($3::date, $4::date, '[]')
               AND int4range(minute_start, minute_end) && int4range($5, $6)
             LIMIT 1
            """,
            clinic_id,
            doctor_id,
            date_start,
            date_end,
            minute_start,
            minute_end,
        )
        if row is None:
            return None

        def hhmm(minutes: int) -> str:
            return f"{minutes // 60:02d}:{minutes % 60:02d}"

        return (
            f"{row['date_start']:%d/%m} – {row['date_end']:%d/%m}, "
            f"{hhmm(row['minute_start'])}–{hhmm(row['minute_end'])}"
            + (f", lý do: {row['reason']}" if row["reason"] else "")
        )

    @staticmethod
    async def _log_event(
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        await conn.execute(
            """
            INSERT INTO event_log
                (clinic_id, event_type, aggregate_type, aggregate_id,
                 payload, metadata, source, event_published)
            VALUES ($1::uuid, $2, 'booking_override', $3,
                    $4, $5, 'api:booking-override', FALSE)
            """,
            identity.clinic_id,
            event_type,
            payload.get("override_id", identity.clinic_id),
            json.dumps(payload),
            json.dumps(
                {
                    "clinic_role": identity.role.value,
                    "clinic_staff_id": identity.staff_id,
                    "actor_auth_user_id": identity.auth_user_id,
                    "origin": "api:booking-override",
                }
            ),
        )

