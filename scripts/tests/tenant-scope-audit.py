#!/usr/bin/env python3
"""Find backend SQL that touches a tenant table without filtering clinic_id.

WHY THIS EXISTS. The FastAPI process connects as the database owner, so the
row-level security written in 20260730000004 does NOT apply to it. Inside this
process a query is exactly as wide as its WHERE clause. A statement that names a
tenant table and never mentions clinic_id reaches every clinic in the database.

That is invisible today, because there is one real clinic. It becomes a
cross-tenant read or write the day there are two, which is why this has to reach
zero before a second tenant is onboarded (ADR-0009, ADR-0012).

Run: python3 scripts/tests/tenant-scope-audit.py [--check] --tenant-tables <file>

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

# Statements known to span tenants ON PURPOSE: a relay that drains every
# clinic's rows, where scoping the query would break the job.
#
# This list is checked in BOTH directions, like the service-role allowlist. An
# entry that no longer has an unscoped statement is reported as stale and must
# be deleted — otherwise "exempt" quietly turns into "reviewed and safe" for a
# file nobody has looked at in months. notification_relay.py sat here after it
# had already been scoped per clinic, which is exactly that failure.
DELIBERATELY_CROSS_TENANT = {
    "services/pos_relay.py",  # drains the outbox for every clinic
}

# W8 drove this from 71 to 0. It stays at 0: every statement that names a
# tenant table must filter clinic_id, because the backend bypasses RLS. A new
# unscoped query is a cross-tenant read the moment a second clinic exists, so
# CI fails the PR that adds one rather than logging it for later.
CEILING = 0

# Which tables are tenant-scoped is a question the database already answers:
# every table carrying a clinic_id. It used to be answered here instead, by 36
# names typed out by hand, and a hand-written list rots in both directions at
# once. This one had come to include staff_capability, which has no clinic_id,
# while never having heard of drug_batch or inventory_txn, which do — so the two
# pharmacy tables shipped past a gate that reported zero findings.
#
# The list now arrives from a database with the migrations applied: CI generates
# it in the db_fresh job, supabase/tests/run-local.sh does it locally. There is
# deliberately no built-in fallback. An audit that quietly checks nothing looks
# exactly like an audit that passes.
def load_tenant_tables(path: pathlib.Path) -> frozenset[str]:
    """Read table names, one per line. Blank lines and ``#`` comments ignored."""
    if not path.exists():
        raise SystemExit(
            f"tenant table list not found: {path}\n"
            "It is derived from the schema, not stored in this script. Generate "
            "it with supabase/tests/run-local.sh, or point --tenant-tables at a "
            "file produced from a database with the migrations applied."
        )
    names = frozenset(
        line.split("#", 1)[0].strip()
        for line in path.read_text().splitlines()
        if line.split("#", 1)[0].strip()
    )
    # Not a description of the schema — a floor under a broken generator. A
    # psql call that fails and leaves an empty file would otherwise turn
    # --check into a no-op that passes.
    if len(names) < 30:
        raise SystemExit(
            f"{path} lists only {len(names)} tenant tables; there have been more "
            "than 40 since 20260730. Refusing to audit against a list that short."
        )
    return names


def tenant_tables_path() -> pathlib.Path:
    if "--tenant-tables" not in sys.argv:
        raise SystemExit(
            "usage: tenant-scope-audit.py [--check] --tenant-tables <file>\n"
            "The tenant table list comes from the database. See "
            "supabase/tests/run-local.sh."
        )
    index = sys.argv.index("--tenant-tables") + 1
    if index >= len(sys.argv):
        raise SystemExit("--tenant-tables needs a file path")
    return pathlib.Path(sys.argv[index])

STATEMENT = re.compile(
    r"\b(FROM|JOIN|UPDATE|INSERT\s+INTO|DELETE\s+FROM)\s+(?:public\.)?([a-z_]+)",
    re.IGNORECASE,
)
SQL_COMMENT = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)

# One statement that spans clinics on purpose, marked where it lives.
# DELIBERATELY_CROSS_TENANT exempts an entire file, which is right for
# pos_relay.py (cross-tenant end to end) and far too blunt for a file like
# staff_service.py, where a single query must look across clinics and the forty
# around it must not. Written as an SQL comment so the reason travels with the
# statement instead of living in a list somebody has to remember to open:
#     -- tenant-scope: cross-tenant by design, <why>
# Checked in both directions, like every allowlist here: mark a statement that
# turns out to be scoped and stale_markers() reports the mark.
CROSS_TENANT_MARKER = re.compile(r"--\s*tenant-scope:\s*\S")
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


def stale_exemptions(tenant_tables: frozenset[str]) -> list[str]:
    """Exempted files that no longer contain an unscoped statement."""
    stale: list[str] = []
    for rel in sorted(DELIBERATELY_CROSS_TENANT):
        path = SRC / rel
        if not path.exists():
            stale.append(f"{rel} (file no longer exists)")
            continue
        needs_exemption = False
        for _lineno, sql in sql_literals(path):
            touched = {
                m.group(2).lower()
                for m in STATEMENT.finditer(sql)
                if m.group(2).lower() in tenant_tables
            }
            if touched and (not has_clinic_scope(sql) or or_bypasses_tenant(sql)):
                needs_exemption = True
                break
        if not needs_exemption:
            stale.append(f"{rel} (every statement is now scoped)")
    return stale


def stale_markers(tenant_tables: frozenset[str]) -> list[str]:
    """Marked statements that no longer read across clinics."""
    stale: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        rel = str(path.relative_to(SRC))
        if rel in DELIBERATELY_CROSS_TENANT:
            continue
        for lineno, sql in sql_literals(path):
            if not CROSS_TENANT_MARKER.search(sql):
                continue
            touched = {
                m.group(2).lower()
                for m in STATEMENT.finditer(sql)
                if m.group(2).lower() in tenant_tables
            }
            if not touched:
                stale.append(f"{rel}:{lineno} (marked, reads no tenant table)")
            elif has_clinic_scope(sql) and not or_bypasses_tenant(sql):
                stale.append(f"{rel}:{lineno} (marked, but the statement is scoped)")
    return stale


def audit(tenant_tables: frozenset[str]) -> list[tuple[str, int, str, str]]:
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
                    if m.group(2).lower() in tenant_tables
                }
            )
            if not touched:
                continue
            if CROSS_TENANT_MARKER.search(sql):
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
    tenant_tables = load_tenant_tables(tenant_tables_path())
    unscoped = audit(tenant_tables)
    by_file: dict[str, list[tuple[int, str, str]]] = {}
    for rel, lineno, tables, snippet in unscoped:
        by_file.setdefault(rel, []).append((lineno, tables, snippet))

    for rel, items in sorted(by_file.items(), key=lambda kv: -len(kv[1])):
        print(f"{rel}  ({len(items)})")
        for lineno, tables, snippet in sorted(items):
            print(f"    L{lineno:<5} [{tables}] {snippet}")

    stale = stale_exemptions(tenant_tables) + stale_markers(tenant_tables)
    if stale:
        print("\nstale cross-tenant exemptions — delete these entries:")
        for entry in stale:
            print(f"    {entry}")

    print(f"\nunscoped statements: {len(unscoped)} (ceiling {CEILING})")

    if "--check" in sys.argv and stale:
        print(
            "\nERROR: the cross-tenant exemption list has entries it no longer "
            "earns. An exemption that is not needed reads as a review nobody "
            "did — remove it.",
            file=sys.stderr,
        )
        return 1

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
