"""Regression tests for the static tenant SQL gate."""

from __future__ import annotations

import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

_REPO = Path(__file__).resolve().parents[2]
_AUDIT = runpy.run_path(str(_REPO / "scripts/tests/tenant-scope-audit.py"))
has_clinic_scope = cast(Callable[[str], bool], _AUDIT["has_clinic_scope"])
or_bypasses_tenant = cast(Callable[[str], bool], _AUDIT["or_bypasses_tenant"])
stale_exemptions = cast(Callable[[], list[str]], _AUDIT["stale_exemptions"])


def test_projection_or_comment_does_not_count_as_tenant_scope() -> None:
    assert not has_clinic_scope("SELECT clinic_id, full_name FROM patient")
    assert not has_clinic_scope(
        "-- clinic_id = $1\nSELECT full_name FROM patient WHERE id = $1"
    )


def test_insert_column_and_filter_predicate_count_as_tenant_scope() -> None:
    assert has_clinic_scope(
        "INSERT INTO event_log (clinic_id, event_type) VALUES ($1, $2)"
    )
    assert has_clinic_scope(
        "SELECT full_name FROM patient WHERE clinic_id = $1 AND id = $2"
    )


def test_or_that_escapes_the_tenant_filter_is_caught() -> None:
    """The exact statement that shipped and leaked.

    SQL binds AND tighter than OR, so this reads
    (clinic_id = $2 AND phone_primary = …) OR (phone_secondary = …): a lookup by
    a patient's second phone number returned every clinic's patients. It passed
    the gate because clinic_id is present AND is a genuine predicate — which is
    why the gate had to learn about precedence, not just presence.
    """
    assert or_bypasses_tenant(
        "SELECT * FROM patient WHERE clinic_id = $2::uuid "
        "AND phone_primary = ANY($1::text[]) OR phone_secondary = ANY($1::text[])"
    )


def test_parenthesised_or_is_not_flagged() -> None:
    assert not or_bypasses_tenant(
        "SELECT * FROM patient WHERE clinic_id = $2::uuid "
        "AND (phone_primary = ANY($1::text[]) OR phone_secondary = ANY($1::text[]))"
    )


def test_tenant_repeated_in_every_branch_is_not_flagged() -> None:
    assert not or_bypasses_tenant(
        "SELECT * FROM patient WHERE (clinic_id = $1 AND a = 1) "
        "OR (clinic_id = $1 AND b = 2)"
    )


def test_or_inside_a_function_call_is_not_flagged() -> None:
    assert not or_bypasses_tenant(
        "SELECT * FROM patient WHERE clinic_id = $1 AND COALESCE(a, b) = ANY($2)"
    )


def test_no_cross_tenant_exemption_is_stale() -> None:
    """Every exemption must still be earned.

    The list is checked in both directions, like the service-role allowlist:
    adding an entry needs a reason, and KEEPING one needs the reason to still
    hold. notification_relay.py stayed on this list after its query had already
    been scoped per clinic — at which point "exempt from the tenant audit" reads
    as "someone reviewed this and it is fine", which nobody had.
    """
    assert stale_exemptions() == []


# CTE / truy vấn con (18/09/2026). hang_cho mở đầu bằng `WITH stt AS (… WHERE …)`
# rồi câu chính có `AND ( … OR … )` trong ngoặc. Bộ đọc cũ kéo mệnh đề WHERE của
# CTE tràn qua dấu `)` đóng CTE sang câu chính, đếm ngoặc lệch xuống âm, và báo
# cái OR có ngoặc là OR trần — báo động giả làm CI đỏ.
_CTE_OK = """
WITH stt AS (
  SELECT v.visit_id, row_number() OVER (ORDER BY v.checked_in_at) AS so
    FROM visit v WHERE v.clinic_id = $1::uuid AND v.checked_in_at IS NOT NULL
)
SELECT q.id FROM queue_entry q JOIN stt ON stt.visit_id = q.visit_id
 WHERE q.clinic_id = $1::uuid AND (q.lane = 'ROOM' OR q.lane = 'DOCTOR')
 ORDER BY q.id
"""


def test_cte_roi_cau_chinh_co_or_trong_ngoac_khong_bi_bao() -> None:
    assert not or_bypasses_tenant(_CTE_OK)


def test_cte_roi_cau_chinh_co_or_tran_van_bi_bat() -> None:
    # Sửa lỗi báo động giả không được làm mù phép kiểm với câu chính.
    co_ngoac = "AND (q.lane = 'ROOM' OR q.lane = 'DOCTOR')"
    tran = "AND q.lane = 'ROOM' OR q.lane = 'DOCTOR'"
    sql = _CTE_OK.replace(co_ngoac, tran)
    assert or_bypasses_tenant(sql)


def test_or_tran_ben_trong_truy_van_con_van_bi_bat() -> None:
    assert or_bypasses_tenant(
        "SELECT * FROM (SELECT id FROM patient"
        " WHERE clinic_id = $1 AND a = 1 OR b = 2) x WHERE x.id = $2"
    )
