"""Reproduce historical authenticated GRANT surviving main ACL migration.

Uses only a disposable DB created by the repository test wrapper. Applies ACL
changes inside a rolled-back transaction; never touches production or dev DB.
The wrapper's local test connection string is deliberately not printed.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PINNED = "956ba4f236b1c92f1280d2097018c199e90ce8c7"
MIGRATION = "supabase/migrations/20261019100000_harden_public_function_acl.sql"
STOCK_ACL = "supabase/migrations/20261019120000_restrict_stock_postgrest_reads.sql"


def main() -> None:
    run = subprocess.run(
        ["scripts/test-nhanh.sh", "--giu", "src/tests/unit/test_idempotency.py", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    found = re.search(r"DB tạm (tam_[a-zA-Z0-9_]+) \(", run.stdout)
    if not found:
        raise RuntimeError("Wrapper did not report a disposable DB; no SQL was run")
    database = found.group(1)
    if not re.fullmatch(r"tam_[0-9]+_dr4women_macmini", database):
        raise RuntimeError("Disposable DB name did not match the strict allowlist")
    try:
        migration = subprocess.check_output(
            ["git", "show", f"{PINNED}:{MIGRATION}"], cwd=ROOT, text=True
        )
        migration = re.sub(r"(?m)^\s*(BEGIN|COMMIT);\s*$", "", migration)
        stock_acl = subprocess.check_output(
            ["git", "show", f"{PINNED}:{STOCK_ACL}"], cwd=ROOT, text=True
        )
        stock_acl = re.sub(r"(?m)^\s*(BEGIN|COMMIT);\s*$", "", stock_acl)
        # The shared template predates some stock tables. Empty placeholders
        # are sufficient for this ACL-only experiment, not for app/schema QA.
        stock_tables = sorted(set(re.findall(r"public\.([a-z_]+)", stock_acl)))
        names = ",".join("'" + name + "'" for name in stock_tables)
        placeholders = (
            "DO $$ DECLARE n text; BEGIN FOREACH n IN ARRAY ARRAY["
            + names
            + "] LOOP IF to_regclass('public.'||n) IS NULL THEN "
            "EXECUTE format('CREATE TABLE public.%I (id integer)',n); "
            "END IF; END LOOP; END $$;\n"
        )
        signature = "public.lieu_trinh_go_buoi(uuid,uuid,text,uuid)"
        sql = (
            "BEGIN;\n"
            f"GRANT EXECUTE ON FUNCTION {signature} TO authenticated;\n"
            + migration
            + f"\nSELECT 'after_main_acl',has_function_privilege('anon',"
            f"'{signature}','EXECUTE'),has_function_privilege('authenticated',"
            f"'{signature}','EXECUTE');\nROLLBACK;\n"
            "BEGIN;\n" + placeholders + "GRANT ALL ON ALL TABLES IN SCHEMA public "
            "TO authenticated,service_role;\n"
            + migration
            + stock_acl
            + "\nSELECT 'after_restore_columns',"
            "has_column_privilege('authenticated','public.clinical_record',"
            "'prescription_draft','SELECT'),"
            "has_column_privilege('authenticated','public.clinic','settings','SELECT');"
            "\nROLLBACK;\n"
        )
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                "chung_test_db",
                "psql",
                "-U",
                "postgres",
                "-d",
                database,
                "-X",
                "-A",
                "-t",
                "-v",
                "ON_ERROR_STOP=1",
            ],
            input=sql,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode:
            raise RuntimeError("ACL probe failed: " + result.stderr[-500:])
        observed = next(
            line
            for line in result.stdout.splitlines()
            if line.startswith("after_main_acl|")
        )
        assert observed == "after_main_acl|f|t", observed
        columns = next(
            line
            for line in result.stdout.splitlines()
            if line.startswith("after_restore_columns|")
        )
        assert columns == "after_restore_columns|t|t", columns
        print(
            json.dumps(
                dict(
                    pinned_main=PINNED,
                    environment="disposable wrapper DB; transaction rollback",
                    historical_authenticated_grant_simulated=True,
                    anon_execute_after_main=False,
                    authenticated_execute_after_main=True,
                    authenticated_select_prescription_draft_after_restore=True,
                    authenticated_select_clinic_settings_after_restore=True,
                    missing_stock_relations_stubbed_for_acl_only=True,
                    wrapper_tests_exit=run.returncode,
                    limitation="No public HTTP mutation or production inspection",
                )
            )
        )
    finally:
        subprocess.run(
            [
                "docker",
                "exec",
                "chung_test_db",
                "psql",
                "-U",
                "postgres",
                "-d",
                "template1",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                f'DROP DATABASE "{database}" WITH (FORCE)',
            ],
            capture_output=True,
            timeout=15,
            check=True,
        )


if __name__ == "__main__":
    main()
