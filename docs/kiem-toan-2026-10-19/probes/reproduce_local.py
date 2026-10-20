"""Reproduce audit observations offline against unchanged source.

These tests confirm current behavior, including defects. A green result here
does not mean the application is correct. No production data, DB or network.
Run: PYTHONPATH=src .venv/bin/python <this file>
"""

from __future__ import annotations

import ast
import asyncio
import gzip
import hashlib
import os
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[3]


class AuditObservations(unittest.TestCase):
    """Synthetic observations; expected values intentionally expose problems."""

    def test_fin_001_allocation_does_not_conserve_discount(self) -> None:
        source = ROOT / "src/clinicai/services/bill_service.py"
        tree = ast.parse(source.read_text())
        node = next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "phan_bo_giam"
        )
        namespace = {
            "Decimal": Decimal,
            "DongHoaDon": SimpleNamespace,
            "CLINIC": "CLINIC",
        }
        exec(
            compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        lines = [SimpleNamespace(thanh_tien=x, ben_thu="CLINIC") for x in [100, 100, 1]]
        result = namespace["phan_bo_giam"](lines, 200)
        self.assertEqual(result, [99, 99, 1])
        self.assertNotEqual(sum(result), 200)

    def test_clin_001_review_marked_done_before_external_result(self) -> None:
        from clinicai.services.hanh_trinh_khach_service import dung_hanh_trinh_khach

        t = datetime(2026, 10, 19, 1, 0, tzinfo=UTC)
        order = dict(
            id="synthetic-order",
            lan=1,
            ten="Synthetic external test",
            tao_luc=t,
            chon=True,
            da_tra=True,
            xong=False,
            ngoai=True,
            phong="Synthetic sampling room",
            bat_dau_luc=t,
            lam_xong_luc=t + timedelta(minutes=5),
            execution_status="COMPLETED",
        )
        result = dung_hanh_trinh_khach(
            luot=dict(visit_id="synthetic-visit", checked_in_at=t),
            su_kien=[],
            chi_dinh=[order],
            hang=[],
            phien=[
                dict(
                    kind="PRIMARY",
                    status="completed",
                    started_at=t,
                    completed_at=t + timedelta(minutes=10),
                )
            ],
        )
        steps = {b["ma"]: b for b in result["buoc"]}
        self.assertEqual(steps["LAM_DV"]["trang_thai"], "doi_tac")
        self.assertEqual(steps["DOC_KQ"]["trang_thai"], "xong")
        self.assertEqual(
            steps["DOC_KQ"]["ghi_chu"], "đọc kết quả ngay trong phiên khám chính"
        )

    def test_clin_002_checkout_fills_medicine_completion_time(self) -> None:
        from clinicai.services.hanh_trinh_khach_service import dung_hanh_trinh_khach

        t = datetime(2026, 10, 19, 1, 0, tzinfo=UTC)
        closed = t + timedelta(minutes=15)
        result = dung_hanh_trinh_khach(
            luot=dict(
                visit_id="synthetic-visit",
                checked_in_at=t,
                closed_at=closed,
                status="FINALIZED",
            ),
            su_kien=[("prescription.saved", t, {})],
            chi_dinh=[],
            hang=[],
            phien=[],
        )
        medicine = next(b for b in result["buoc"] if b["ma"] == "THUOC")
        self.assertEqual(medicine["trang_thai"], "xong")
        self.assertEqual(medicine["xong"], closed)

    def test_inf_001_missing_companions_are_not_checked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="clinicai-audit-") as tmp:
            archive = Path(tmp) / "clinicai_synthetic.sql.gz"
            archive.write_bytes(
                gzip.compress(
                    b"-- PostgreSQL database dump\n"
                    b"CREATE TABLE public.patient (id int);\n"
                    b"CREATE TABLE public.appointment (id int);\n"
                    b"-- PostgreSQL database dump complete\n"
                )
            )
            sha = hashlib.sha256(archive.read_bytes()).hexdigest()
            Path(str(archive) + ".manifest").write_text(
                "format_version=1\nscope=public-schema-only\n"
                "complete_supabase_dr=false\n"
                "requires=supabase-cloud-pitr-and-auth-backup\n"
                f"archive_sha256={sha}\nmedia_artifact=none\n"
                "auth_artifact=missing_auth.sql.gz\nauth_sha256=invalid\n"
                "tep_chua_day_artifact=missing_files.tar.gz\n"
                "tep_chua_day_sha256=invalid\ntep_chua_day_skipped=7\n"
            )
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/verify-backup.sh"), str(archive)],
                env={**os.environ, "BACKUP_MIN_ARCHIVE_BYTES": "1"},
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Backup verified:", result.stdout)

    def test_inf_002_delivery_failure_is_not_retried_next_cycle(self) -> None:
        from clinicai.services import canh_gac

        class ConnectionContext:
            async def __aenter__(self):
                return SimpleNamespace()

            async def __aexit__(self, *args):
                return False

        pool = SimpleNamespace(acquire=lambda: ConnectionContext(), execute=AsyncMock())
        incident = SimpleNamespace(
            ma="synthetic",
            muc="critical",
            noi_dung="Synthetic incident",
            co_chuyen=True,
        )
        sender = AsyncMock(return_value=False)

        async def run_cycles():
            with (
                patch.object(canh_gac, "_mo", AsyncMock(side_effect=[True, False])),
                patch.object(canh_gac, "gui_telegram_ops", sender),
            ):
                await canh_gac.ap_dung(pool, [incident])
                await canh_gac.ap_dung(pool, [incident])

        asyncio.run(run_cycles())
        self.assertEqual(sender.await_count, 1)
        self.assertEqual(pool.execute.await_count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
