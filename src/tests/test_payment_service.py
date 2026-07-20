"""Unit tests for the pure payment rules (Phase 4, cluster #3).

Covers the role→kind matrix and amount normalization ported from the frontend
``payment/route.ts``. The DB paths (COMPLETED gate, upsert, delete) are exercised
by integration tests, not here.
"""

from __future__ import annotations

import math

import pytest

from clinicai.api.identity import ClinicRole
from clinicai.services.payment_service import (
    PAYMENT_KINDS,
    allowed_kinds,
    normalize_amount,
)


class TestAllowedKinds:
    def test_cashier_thuoc_only_thuoc(self) -> None:
        assert allowed_kinds(ClinicRole.CASHIER_THUOC) == frozenset({"thuoc"})

    def test_cashier_dv_only_dich_vu(self) -> None:
        assert allowed_kinds(ClinicRole.CASHIER_DV) == frozenset({"dich_vu"})

    @pytest.mark.parametrize("role", [ClinicRole.CASHIER, ClinicRole.MANAGEMENT])
    def test_general_cashier_and_management_both(self, role: ClinicRole) -> None:
        assert allowed_kinds(role) == PAYMENT_KINDS

    @pytest.mark.parametrize(
        "role",
        [ClinicRole.DOCTOR, ClinicRole.RECEPTION, ClinicRole.CSKH, ClinicRole.TKYK],
    )
    def test_non_cashier_roles_get_nothing(self, role: ClinicRole) -> None:
        assert allowed_kinds(role) == frozenset()


class TestNormalizeAmount:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (0, 0),
            (100, 100),
            (100.4, 100),
            (100.5, 100),  # banker's rounding: round(100.5) == 100
            (101.5, 102),
            (100000, 100000),
        ],
    )
    def test_valid_amounts_round(self, raw: object, expected: int) -> None:
        assert normalize_amount(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [None, -1, -0.5, "100", "", math.nan, math.inf, -math.inf, True, False, [], {}],
    )
    def test_invalid_amounts_become_none(self, raw: object) -> None:
        assert normalize_amount(raw) is None
