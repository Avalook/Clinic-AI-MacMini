"""Luật đặt lịch đọc từ clinic.settings (C.3).

Ba con số này quyết định phòng khám thứ hai có dùng được sản phẩm hay không, và
quyết định lễ tân của phòng khám thứ nhất có đặt được lịch sáng mai hay không.
Nên cái đáng kiểm không phải "đọc ra đúng số", mà là: khi cấu hình sai thì hỏng
ở đâu, và mặc định có còn đúng bằng hệ thống đang chạy hay không.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from clinicai.services.clinic_policy import (
    DEFAULT_POLICY,
    DEFAULT_REGULAR_CAP,
    DEFAULT_SLOT_MINUTES,
    DEFAULT_WALKIN_CAP,
    ClinicPolicy,
    ClinicPolicyError,
    load_clinic_policy,
)

MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase"
    / "migrations"
    / "20260803000001_clinic_booking_policy.sql"
)


class TestDefaults:
    def test_an_empty_settings_behaves_like_the_system_of_today(self) -> None:
        # Migration chạy nửa chừng, fixture cũ, phòng khám vừa INSERT tay — cả
        # ba đều phải cho ra hành vi Dr4Women đang có, không phải 0 chỗ.
        assert ClinicPolicy.from_settings({}) == DEFAULT_POLICY
        assert ClinicPolicy.from_settings(None) == DEFAULT_POLICY
        assert ClinicPolicy.from_settings('{"pos": {"adapter": "none"}}') == (
            DEFAULT_POLICY
        )

    def test_a_booking_block_of_the_wrong_shape_is_not_half_read(self) -> None:
        # Nửa đọc được là cách tệ nhất: một phòng khám chạy 15 phút nhưng 0 chỗ.
        assert ClinicPolicy.from_settings({"booking": "30"}) == DEFAULT_POLICY
        assert ClinicPolicy.from_settings({"booking": None}) == DEFAULT_POLICY

    def test_only_the_keys_that_are_written_are_overridden(self) -> None:
        policy = ClinicPolicy.from_settings({"booking": {"slot_minutes": 30}})
        assert policy.slot_minutes == 30
        assert (policy.regular_cap, policy.walkin_cap) == (
            DEFAULT_REGULAR_CAP,
            DEFAULT_WALKIN_CAP,
        )

    def test_python_and_sql_agree_on_what_default_means(self) -> None:
        # Hai người đọc cùng một cột, mỗi người mang mặc định riêng. Lệch nhau
        # thì cùng một hàng cho ra hai luật, và cái đứng ra từ chối bệnh nhân là
        # cái không ai đọc.
        sql = MIGRATION.read_text(encoding="utf-8")
        reader = re.search(
            r"CREATE OR REPLACE FUNCTION public\.clinic_booking_policy\(p_clinic_id"
            r"[\s\S]*?\$function\$([\s\S]*?)\$function\$",
            sql,
        )
        assert reader is not None
        coalesced = {
            key: int(value)
            for key, value in re.findall(
                r"coalesce\(\(b ->> '(\w+)'\)::integer, (\d+)\)", reader.group(1)
            )
        }
        assert coalesced == {
            "slot_minutes": DEFAULT_SLOT_MINUTES,
            "regular_cap": DEFAULT_REGULAR_CAP,
            "walkin_cap": DEFAULT_WALKIN_CAP,
        }

        column_default = re.search(r"SET DEFAULT '(\{[^']*\})'::jsonb", sql)
        assert column_default is not None
        assert json.loads(column_default.group(1))["booking"] == {
            "slot_minutes": DEFAULT_SLOT_MINUTES,
            "regular_cap": DEFAULT_REGULAR_CAP,
            "walkin_cap": DEFAULT_WALKIN_CAP,
        }


class TestRejectedConfigurations:
    @pytest.mark.parametrize("minutes", [0, -15, 61, 90])
    def test_a_slot_length_outside_the_hour_is_refused(self, minutes: int) -> None:
        with pytest.raises(ClinicPolicyError):
            ClinicPolicy(slot_minutes=minutes)

    @pytest.mark.parametrize("minutes", [7, 45, 50])
    def test_a_slot_that_does_not_divide_the_hour_is_refused(
        self, minutes: int
    ) -> None:
        # 45 phút trông vô hại. Khung được cắt bằng làm tròn xuống trên epoch
        # UTC, nên nó sẽ trượt qua từng giờ: ô lễ tân nhìn thấy không còn là ô
        # database đếm, và hai bên bất đồng về việc khung nào đã đầy.
        with pytest.raises(ClinicPolicyError, match="chia hết"):
            ClinicPolicy(slot_minutes=minutes)

    @pytest.mark.parametrize("minutes", [1, 5, 10, 12, 15, 20, 30, 60])
    def test_the_lengths_a_clinic_may_actually_pick(self, minutes: int) -> None:
        assert ClinicPolicy(slot_minutes=minutes).slot_minutes == minutes

    def test_a_clinic_with_no_booked_seats_is_a_typo_not_a_policy(self) -> None:
        with pytest.raises(ClinicPolicyError):
            ClinicPolicy(regular_cap=0)

    def test_but_a_clinic_may_genuinely_take_no_walk_ins(self) -> None:
        assert ClinicPolicy(walkin_cap=0).cap_for(walkin=True) == 0

    @pytest.mark.parametrize("cap", [-1, 101])
    def test_a_cap_far_outside_the_range_is_refused(self, cap: int) -> None:
        with pytest.raises(ClinicPolicyError):
            ClinicPolicy(walkin_cap=cap)

    @pytest.mark.parametrize("raw", ["15", 15.5, True, [15]])
    def test_a_number_that_is_not_an_integer_is_not_guessed_at(
        self, raw: object
    ) -> None:
        # "15" cast được trong Postgres và là chuỗi trong JavaScript. Đoán hộ là
        # cách hai bên đọc ra hai giá trị khác nhau từ cùng một hàng.
        with pytest.raises(ClinicPolicyError):
            ClinicPolicy.from_settings({"booking": {"slot_minutes": raw}})


class TestBucketing:
    def test_a_thirty_minute_clinic_gets_thirty_minute_buckets(self) -> None:
        policy = ClinicPolicy(slot_minutes=30)
        begin, end = policy.bucket(datetime(2026, 7, 30, 9, 44, tzinfo=timezone.utc))
        assert (begin.hour, begin.minute) == (9, 30)
        assert (end - begin).total_seconds() == 1800

    def test_buckets_never_overlap_or_leave_a_gap(self) -> None:
        policy = ClinicPolicy(slot_minutes=20)
        moments = [
            datetime(2026, 7, 30, 9, minute, tzinfo=timezone.utc)
            for minute in range(0, 60)
        ]
        buckets = {policy.bucket(m) for m in moments}
        assert len(buckets) == 3
        for begin, end in buckets:
            assert end - begin == policy.bucket(begin)[1] - begin


class TestLoading:
    @pytest.mark.asyncio
    async def test_the_row_is_read_by_clinic_id(self) -> None:
        conn = AsyncMock()
        conn.fetchval.return_value = {"booking": {"slot_minutes": 30}}
        clinic_id = str(uuid4())

        policy = await load_clinic_policy(conn, clinic_id)

        sql, arg = conn.fetchval.await_args.args
        assert "FROM clinic WHERE id = $1::uuid" in sql
        assert arg == clinic_id
        assert policy.slot_minutes == 30

    @pytest.mark.asyncio
    async def test_settings_arriving_as_json_text_is_still_read(self) -> None:
        # asyncpg trả jsonb về dạng str khi chưa đăng ký codec. Không phải giả
        # thuyết: pos_relay.py có đúng một hàm _as_dict vì lý do này.
        conn = AsyncMock()
        conn.fetchval.return_value = '{"booking": {"regular_cap": 3}}'

        policy = await load_clinic_policy(conn, str(uuid4()))

        assert policy.regular_cap == 3

    @pytest.mark.asyncio
    async def test_a_clinic_that_is_not_there_does_not_book_at_zero_seats(
        self,
    ) -> None:
        conn = AsyncMock()
        conn.fetchval.return_value = None

        assert await load_clinic_policy(conn, str(uuid4())) == DEFAULT_POLICY
