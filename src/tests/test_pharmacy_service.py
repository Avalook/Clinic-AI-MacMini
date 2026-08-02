"""Unit tests cho luật thuần của kho thuốc (B.3).

Chỉ test phần không chạm database: chuẩn hoá số lượng/lý do và thuật toán chia
hàng FEFO. Đường ghi (khoá lô, trigger cộng tồn, event_log) do integration test
lo — ở đây tập trung vào những luật mà nếu sai thì sổ kho sai lặng lẽ.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services.pharmacy_service import (
    BatchStock,
    allocate_fefo,
    normalize_delta,
    normalize_quantity,
    normalize_reason,
)

TODAY = date(2026, 8, 2)


def batch(code: str, expiry: date, qty: str) -> BatchStock:
    return BatchStock(
        batch_id=f"id-{code}",
        batch_code=code,
        expiry_date=expiry,
        quantity_on_hand=Decimal(qty),
    )


class TestNormalizeQuantity:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (30, "30.000"),
            ("30", "30.000"),
            (0.5, "0.500"),
            (Decimal("1.25"), "1.250"),
            ("0.001", "0.001"),
        ],
    )
    def test_accepts_positive_values(self, raw: object, expected: str) -> None:
        assert str(normalize_quantity(raw)) == expected

    @pytest.mark.parametrize("raw", [0, "0", -1, Decimal("-0.5")])
    def test_rejects_non_positive(self, raw: object) -> None:
        with pytest.raises(ValidationError):
            normalize_quantity(raw)

    @pytest.mark.parametrize("raw", ["abc", "", None, "1,5", float("nan")])
    def test_rejects_non_numbers(self, raw: object) -> None:
        with pytest.raises(ValidationError):
            normalize_quantity(raw)

    def test_rejects_infinity(self) -> None:
        with pytest.raises(ValidationError):
            normalize_quantity(float("inf"))

    def test_rejects_more_than_three_decimals(self) -> None:
        # Cột là numeric(12,3): Postgres sẽ LÀM TRÒN chứ không báo lỗi, nên số
        # dược sĩ nhập và số vào kho khác nhau mà không ai được cảnh báo.
        with pytest.raises(ValidationError):
            normalize_quantity("0.0001")

    def test_rejects_absurd_magnitude(self) -> None:
        with pytest.raises(ValidationError):
            normalize_quantity("9999999")


class TestNormalizeDelta:
    def test_allows_negative(self) -> None:
        assert normalize_delta("-4") == Decimal("-4.000")

    def test_allows_positive(self) -> None:
        assert normalize_delta("4") == Decimal("4.000")

    def test_rejects_zero(self) -> None:
        with pytest.raises(ValidationError):
            normalize_delta(0)


class TestNormalizeReason:
    def test_strips_and_keeps_text(self) -> None:
        assert normalize_reason("  vỡ 2 lọ khi bốc dỡ  ") == "vỡ 2 lọ khi bốc dỡ"

    @pytest.mark.parametrize("raw", ["", "   ", None, 7])
    def test_required_reason_must_exist(self, raw: object) -> None:
        with pytest.raises(ValidationError):
            normalize_reason(raw)

    def test_rejects_too_short(self) -> None:
        with pytest.raises(ValidationError):
            normalize_reason("hết")

    def test_optional_reason_may_be_empty(self) -> None:
        assert normalize_reason("  ", required=False) is None

    def test_truncates_instead_of_rejecting_long_text(self) -> None:
        assert len(normalize_reason("x" * 900) or "") == 500


class TestAllocateFefo:
    def test_takes_earliest_expiry_first(self) -> None:
        batches = [
            batch("LATE", date(2027, 1, 1), "100"),
            batch("SOON", date(2026, 9, 1), "10"),
        ]
        result = allocate_fefo(batches, Decimal("15"), today=TODAY)
        assert [(a.batch_code, str(a.quantity)) for a in result] == [
            ("SOON", "10"),
            ("LATE", "5"),
        ]

    def test_stops_once_covered(self) -> None:
        batches = [
            batch("A", date(2026, 9, 1), "50"),
            batch("B", date(2026, 10, 1), "50"),
        ]
        result = allocate_fefo(batches, Decimal("20"), today=TODAY)
        assert len(result) == 1
        assert result[0].batch_code == "A"

    def test_skips_expired_batches(self) -> None:
        batches = [
            batch("OLD", date(2026, 8, 1), "500"),
            batch("OK", date(2026, 12, 1), "5"),
        ]
        result = allocate_fefo(batches, Decimal("5"), today=TODAY)
        assert [a.batch_code for a in result] == ["OK"]

    def test_expiring_today_is_still_usable(self) -> None:
        # Hạn dùng ghi trên vỉ là ngày cuối cùng còn dùng được, không phải ngày
        # đầu tiên hết hạn. Lệch một ngày ở đây là vứt thuốc còn hạn.
        result = allocate_fefo([batch("EDGE", TODAY, "5")], Decimal("5"), today=TODAY)
        assert [a.batch_code for a in result] == ["EDGE"]

    def test_expired_stock_does_not_cover_shortfall(self) -> None:
        batches = [
            batch("OLD", date(2026, 1, 1), "500"),
            batch("OK", date(2026, 12, 1), "3"),
        ]
        with pytest.raises(ConflictError) as err:
            allocate_fefo(batches, Decimal("10"), today=TODAY)
        assert "hết hạn" in str(err.value)

    def test_shortfall_without_expired_stock_says_only_shortage(self) -> None:
        with pytest.raises(ConflictError) as err:
            allocate_fefo(
                [batch("OK", date(2026, 12, 1), "3")], Decimal("10"), today=TODAY
            )
        assert "hết hạn" not in str(err.value)

    def test_empty_batches_raises(self) -> None:
        with pytest.raises(ConflictError):
            allocate_fefo([], Decimal("1"), today=TODAY)

    def test_same_expiry_is_ordered_deterministically(self) -> None:
        same = date(2026, 9, 1)
        forward = allocate_fefo(
            [batch("B2", same, "5"), batch("B1", same, "5")],
            Decimal("7"),
            today=TODAY,
        )
        reverse = allocate_fefo(
            [batch("B1", same, "5"), batch("B2", same, "5")],
            Decimal("7"),
            today=TODAY,
        )
        assert [a.batch_code for a in forward] == ["B1", "B2"]
        assert [a.batch_code for a in forward] == [a.batch_code for a in reverse]

    def test_allocations_sum_to_requested_quantity(self) -> None:
        batches = [
            batch("A", date(2026, 9, 1), "3.5"),
            batch("B", date(2026, 10, 1), "4.25"),
            batch("C", date(2026, 11, 1), "10"),
        ]
        wanted = Decimal("9.75")
        result = allocate_fefo(batches, wanted, today=TODAY)
        assert sum((a.quantity for a in result), Decimal(0)) == wanted

    def test_ignores_batches_already_empty(self) -> None:
        batches = [
            batch("EMPTY", date(2026, 9, 1), "0"),
            batch("HAS", date(2026, 10, 1), "5"),
        ]
        result = allocate_fefo(batches, Decimal("5"), today=TODAY)
        assert [a.batch_code for a in result] == ["HAS"]
