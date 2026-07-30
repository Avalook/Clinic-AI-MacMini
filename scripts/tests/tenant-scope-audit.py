#!/usr/bin/env python3
"""Find backend SQL that touches a tenant table without filtering clinic_id.

WHY THIS EXISTS. The FastAPI process connects as the database owner, so the
row-level security written in 20260730000004 does NOT apply to it. Inside this
process a query is exactly as wide as its WHERE clause. A statement that names a
tenant table and never mentions clinic_id reaches every clinic in the database.

That is invisible today, because there is one real clinic. It becomes a
cross-tenant read or write the day there are two, which is why this has to reach
zero before a second tenant is onboarded (ADR-0009, ADR-0012).

Run:  python3 scripts/tests/tenant-scope-audit.py [--check]

``--check`` exits non-zero if the count exceeds the ceiling below. The count is
now 0 and the ceiling is 0: the gate no longer tracks a backlog, it keeps one
from starting. The ceiling may only be LOWERED, never raised.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "clinicai"

# Statements known to span tenants ON PURPOSE. Each is a relay or a scheduled
# job that processes every clinic's rows; scoping them would break them.
DELIBERATELY_CROSS_TENANT = {
    "services/pos_relay.py",  # drains the outbox for every clinic
    "services/notification_relay.py",  # same, for notifications
}

# W8 drove this from 71 to 0. It stays at 0: every statement that names a
# tenant table must filter clinic_id, because the backend bypasses RLS. A new
# unscoped query is a cross-tenant read the moment a second clinic exists, so
# CI fails the PR that adds one rather than logging it for later.
CEILING = 0

TENANT_TABLES = {
    "appointment", "block_budget", "booking_channel", "care_episode",
    "clinic_location", "clinical_form_response", "clinical_record",
    "cskh_action", "cskh_log", "drug_catalog", "event_log", "follow_up_case",
    "lab_result", "mpi_merge_queue", "node_definition",
    "node_definition_version", "node_dependency", "patient",
    "patient_medical_profile", "payment", "pos_outbox", "pregnancy",
    "prescription", "service_log", "service_price", "service_type",
    "staff_capability", "staff_task", "ultrasound_record", "visit", "work_item",
    "work_item_dependency", "work_item_event", "work_roster", "work_session",
    "work_session_staff",
}

STATEMENT = re.compile(
    r"\b(FROM|JOIN|UPDATE|INSERT\s+INTO|DELETE\s+FROM)\s+(?:public\.)?([a-z_]+)",
    re.IGNORECASE,
)
SQL_COMMENT = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)
INSERT_CLINIC_COLUMN = re.compile(
    r"\bINSERT\s+INTO\s+(?:public\.)?[a-z_]+\s*"
    r"\([^)]*\bclinic_id\b",
    re.IGNORECASE | re.DOTALL,
)
CLINIC_PREDICATE = re.compile(
    r"\b(?:WHERE|AND|OR|ON)\b[^;]*?"
    r"\b(?:[a-z_][a-z0-9_]*\.)?clinic_id\b\s*"
    r"(?:=|<>|!=|\bIS\b|\bIN\b)",
    re.IGNORECASE | re.DOTALL,
)
REVERSE_CLINIC_PREDICATE = re.compile(
    r"\b(?:WHERE|AND|OR|ON)\b[^;]*?"
    r"(?:=|<>|!=)\s*(?:[a-z_][a-z0-9_]*\.)?clinic_id\b",
    re.IGNORECASE | re.DOTALL,
)


def has_clinic_scope(sql: str) -> bool:
    """Require clinic_id in an INSERT column list or an actual predicate."""
    cleaned = SQL_COMMENT.sub("", sql)
    return bool(
        INSERT_CLINIC_COLUMN.search(cleaned)
        or CLINIC_PREDICATE.search(cleaned)
        or REVERSE_CLINIC_PREDICATE.search(cleaned)
    )


# A tenant predicate is only worth having if every branch of the WHERE clause
# carries it. SQL binds AND tighter than OR, so
#
#     WHERE clinic_id = $2 AND phone_primary = ANY($1) OR phone_secondary = ANY($1)
#
# means (clinic AND primary) OR (secondary) — the second branch has no tenant at
# all and reads every clinic. That statement passed every check above, because
# clinic_id really is there and really is a predicate. It shipped, and a lookup
# by a patient's SECOND phone number returned other clinics' patients.
#
# So: split the WHERE clause on top-level OR and require a tenant predicate in
# each branch. Parenthesised ORs (`clinic_id = $1 AND (a OR b)`) are unaffected,
# and a deliberately repeated predicate (`(clinic_id=$1 AND a) OR (clinic_id=$1
# AND b)`) passes too — only a genuinely unscoped branch is reported.
WHERE_CLAUSE = re.compile(
    r"\bWHERE\b(.*?)(?=\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|"
    r"\bRETURNING\b|\bON\s+CONFLICT\b|\bUNION\b|;|$)",
    re.IGNORECASE | re.DOTALL,
)


def _split_top_level_or(clause: str) -> list[str]:
    """Split on OR that is not inside parentheses."""
    parts: list[str] = []
    depth = 0
    start = 0
    i = 0
    while i < len(clause):
        ch = clause[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and clause[i : i + 2].upper() == "OR":
            before = clause[i - 1] if i else " "
            after = clause[i + 2] if i + 2 < len(clause) else " "
            word_before = before.isalnum() or before == "_"
            word_after = after.isalnum() or after == "_"
            if not word_before and not word_after:
                parts.append(clause[start:i])
                start = i + 2
                i += 2
                continue
        i += 1
    parts.append(clause[start:])
    return parts


def or_bypasses_tenant(sql: str) -> bool:
    """True when some top-level OR branch has no clinic_id predicate."""
    cleaned = SQL_COMMENT.sub("", sql)
    for match in WHERE_CLAUSE.finditer(cleaned):
        clause = match.group(1)
        branches = _split_top_level_or(clause)
        if len(branches) < 2:
            continue
        for branch in branches:
            probe = "WHERE " + branch
            if not (
                CLINIC_PREDICATE.search(probe) or REVERSE_CLINIC_PREDICATE.search(probe)
            ):
                return True
    return False


def sql_literals(path: pathlib.Path) -> list[tuple[int, str]]:
    """Every string literal in the file that looks like SQL.

    f-strings are JoinedStr nodes whose literal halves are separate Constants,
    so they are reassembled first — otherwise a query whose clinic_id sits after
    an interpolation reads as unscoped.
    """
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return []

    inside_fstring: set[int] = set()
    # Docstrings are prose. "Insert into mpi_merge_queue for each candidate"
    # is documentation, not a statement, and flagging it teaches people to
    # ignore the report.
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                inside_fstring.add(id(value))
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            docstrings.add(id(node.value))

    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            text = "".join(
                v.value
                for v in node.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)
            )
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in inside_fstring or id(node) in docstrings:
                continue
            text = node.value
        else:
            continue
        if STATEMENT.search(text):
            found.append((node.lineno, text))
    return found


def audit() -> list[tuple[str, int, str, str]]:
    unscoped: list[tuple[str, int, str, str]] = []
    for path in sorted(SRC.rglob("*.py")):
        rel = str(path.relative_to(SRC))
        if rel in DELIBERATELY_CROSS_TENANT:
            continue
        for lineno, sql in sql_literals(path):
            touched = sorted(
                {
                    m.group(2).lower()
                    for m in STATEMENT.finditer(sql)
                    if m.group(2).lower() in TENANT_TABLES
                }
            )
            if not touched:
                continue
            if not has_clinic_scope(sql):
                unscoped.append(
                    (rel, lineno, ",".join(touched), " ".join(sql.split())[:70])
                )
            elif or_bypasses_tenant(sql):
                unscoped.append(
                    (
                        rel,
                        lineno,
                        ",".join(touched),
                        "OR bypasses the tenant filter: "
                        + " ".join(sql.split())[:70],
                    )
                )
    return unscoped


def main() -> int:
    unscoped = audit()
    by_file: dict[str, list[tuple[int, str, str]]] = {}
    for rel, lineno, tables, snippet in unscoped:
        by_file.setdefault(rel, []).append((lineno, tables, snippet))

    for rel, items in sorted(by_file.items(), key=lambda kv: -len(kv[1])):
        print(f"{rel}  ({len(items)})")
        for lineno, tables, snippet in sorted(items):
            print(f"    L{lineno:<5} [{tables}] {snippet}")

    print(f"\nunscoped statements: {len(unscoped)} (ceiling {CEILING})")

    if "--check" in sys.argv and len(unscoped) > CEILING:
        print(
            f"\nERROR: {len(unscoped)} exceeds the ceiling of {CEILING}. "
            "The backend bypasses RLS, so an unscoped query reads every clinic.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
