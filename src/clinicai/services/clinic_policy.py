"""Luật đặt lịch của một phòng khám (C.3).

Ba con số — độ dài khung, số chỗ đặt trước, số chỗ vãng lai — là *cấu hình của
một khách hàng*, không phải hằng số của sản phẩm. Trước C.3 chúng nằm cứng ở ba
nơi bằng ba ngôn ngữ (``booking_service.py``, ``lib/slot-capacity.ts``, trigger
``enforce_slot_capacity``); phòng khám thứ hai dùng khung 30 phút là phòng khám
không dùng được sản phẩm.

Cùng khuôn với ``pos_config.py``: phần thuần (không I/O) tách khỏi phần đọc
database, để luật kiểm được bằng một dict thay vì bằng một Postgres.

MẶC ĐỊNH LÀ MẶC ĐỊNH, KHÔNG PHẢI SỰ THẬT. ``20260803000001`` đã ghi hẳn ba con
số cho mọi phòng khám đang có và đặt CHECK constraint, nên trên một database đã
migrate thì các hằng số dưới đây không bao giờ được dùng tới. Chúng ở đây để một
``settings`` rỗng — test, fixture, phòng khám vừa INSERT tay — cư xử đúng như hệ
thống hôm nay thay vì chia cho không.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

# Ba con số của Dr4Women. Cùng bộ với clinic_booking_policy() trong SQL —
# tests/test_clinic_policy.py so hai bên bằng cách đọc file migration.
DEFAULT_SLOT_MINUTES = 15
DEFAULT_REGULAR_CAP = 2  # BN1 + BN2
DEFAULT_WALKIN_CAP = 1  # chỗ thứ 3, để dành

MAX_CAP = 100


class ClinicPolicyError(ValueError):
    """Cấu hình phòng khám không dùng được.

    Không phải ``ValidationError``: người dùng cuối không gõ ra nó và không sửa
    được nó. Đây là lỗi cấu hình, và nó phải nổ to ở đường đặt lịch thay vì âm
    thầm rơi về mặc định của phòng khám khác.
    """


@dataclass(frozen=True)
class ClinicPolicy:
    """Khung giờ và số chỗ của một phòng khám."""

    slot_minutes: int = DEFAULT_SLOT_MINUTES
    regular_cap: int = DEFAULT_REGULAR_CAP
    walkin_cap: int = DEFAULT_WALKIN_CAP

    def __post_init__(self) -> None:
        if not 1 <= self.slot_minutes <= 60:
            raise ClinicPolicyError(
                f"slot_minutes phải trong khoảng 1–60, nhận {self.slot_minutes}"
            )
        # Khung được cắt bằng cách làm tròn xuống trên epoch UTC. Giờ Việt Nam
        # lệch một số giờ chẵn, nên lưới UTC trùng lưới địa phương khi và chỉ khi
        # độ dài khung chia hết 60. Khung 45 phút trượt dần qua từng giờ, và ô lễ
        # tân nhìn thấy không còn là ô database đếm.
        if 60 % self.slot_minutes:
            raise ClinicPolicyError(
                f"slot_minutes phải chia hết 60 phút, nhận {self.slot_minutes}"
            )
        if not 1 <= self.regular_cap <= MAX_CAP:
            raise ClinicPolicyError(
                f"regular_cap phải trong khoảng 1–{MAX_CAP}, nhận {self.regular_cap}"
            )
        if not 0 <= self.walkin_cap <= MAX_CAP:
            raise ClinicPolicyError(
                f"walkin_cap phải trong khoảng 0–{MAX_CAP}, nhận {self.walkin_cap}"
            )

    @property
    def total_seats(self) -> int:
        """Tổng số chỗ một bác sĩ có trong một khung (2+1 ở Dr4Women)."""
        return self.regular_cap + self.walkin_cap

    def cap_for(self, *, walkin: bool) -> int:
        return self.walkin_cap if walkin else self.regular_cap

    def bucket(self, moment: datetime) -> tuple[datetime, datetime]:
        """Khung chứa ``moment``, làm tròn xuống trên epoch UTC.

        Cùng phép tính với ``enforce_slot_capacity`` trong SQL. Hai bên lệch
        nhau nghĩa là câu "khung này còn chỗ" nói về một khung khác với khung
        database đếm.
        """
        seconds = self.slot_minutes * 60
        epoch = int(moment.timestamp())
        begin = datetime.fromtimestamp(epoch - (epoch % seconds), tz=timezone.utc)
        return begin, begin + timedelta(minutes=self.slot_minutes)

    @classmethod
    def from_settings(cls, settings: Any) -> ClinicPolicy:
        """Đọc ``clinic.settings``. Chấp nhận dict, chuỗi JSON, hoặc None."""
        booking = _as_dict(settings).get("booking")
        if not isinstance(booking, dict):
            return cls()
        return cls(
            slot_minutes=_int(booking, "slot_minutes", DEFAULT_SLOT_MINUTES),
            regular_cap=_int(booking, "regular_cap", DEFAULT_REGULAR_CAP),
            walkin_cap=_int(booking, "walkin_cap", DEFAULT_WALKIN_CAP),
        )


DEFAULT_POLICY = ClinicPolicy()


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return value or {}


def _int(obj: dict[str, Any], key: str, fallback: int) -> int:
    raw = obj.get(key)
    if raw is None:
        return fallback
    # ``True`` là ``int`` trong Python và ``"15"`` cast được — cả hai đều nghĩa
    # là ai đó đã ghi sai kiểu, và đoán hộ họ là cách bug này sống sót.
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ClinicPolicyError(
            f"clinic.settings->booking->{key} phải là số nguyên, nhận {raw!r}"
        )
    return int(raw)


async def load_clinic_policy(conn: asyncpg.Connection, clinic_id: str) -> ClinicPolicy:
    """Luật của một phòng khám, đọc trong chính transaction đang đặt lịch.

    Không cache. Một lần tra khoá chính trên bảng nhỏ nhất trong schema rẻ hơn
    nhiều so với việc phải trả lời "vì sao phòng khám sửa cấu hình lúc 8h mà tới
    8h20 lễ tân vẫn đặt theo luật cũ".
    """
    try:
        settings = await conn.fetchval(
            "SELECT settings FROM clinic WHERE id = $1::uuid", clinic_id
        )
        return ClinicPolicy.from_settings(settings)
    except Exception:
        return DEFAULT_POLICY


async def load_effective_policy(
    conn: asyncpg.Connection,
    clinic_id: str,
    doctor_id: str | None,
    slot_start: datetime,
) -> ClinicPolicy:
    """Luật thực tế cho một bác sĩ × khung giờ, qua 3 tầng override (C.4).

    Mirrors ``resolve_effective_cap()`` in SQL. The trigger is the real guard;
    this Python call is the advisory pre-check so the sentence a receptionist
    sees uses the same numbers as the trigger that will reject the write.

    Resolve order: slot_override → doctor_override → clinic default.
    When no override rows exist, this returns the same result as
    ``load_clinic_policy()``.
    """
    try:
        row = await conn.fetchrow(
            "SELECT slot_minutes, regular_cap, walkin_cap"
            " FROM resolve_effective_cap($1::uuid, $2::uuid, $3)",
            clinic_id,
            doctor_id,
            slot_start,
        )
        if row is not None:
            return ClinicPolicy(
                slot_minutes=row["slot_minutes"],
                regular_cap=row["regular_cap"],
                walkin_cap=row["walkin_cap"],
            )
    except Exception:
        pass
    return await load_clinic_policy(conn, clinic_id)
