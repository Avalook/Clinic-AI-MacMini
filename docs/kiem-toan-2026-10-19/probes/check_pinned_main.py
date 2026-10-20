"""Check selected observations on pinned main, independently of the dirty tree."""

from __future__ import annotations

import ast
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any


def main() -> None:
    source = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(source / "src"))
    from clinicai.services.hanh_trinh_khach_service import dung_hanh_trinh_khach

    t = datetime(2026, 10, 19, 1, 0, tzinfo=UTC)
    order = dict(
        id="synthetic",
        lan=1,
        ten="Synthetic external test",
        tao_luc=t,
        chon=True,
        da_tra=True,
        xong=True,
        ngoai=True,
        phong="Synthetic room",
        bat_dau_luc=t,
        lam_xong_luc=t + timedelta(minutes=5),
        execution_status="COMPLETED",
        viec_doi_tac=True,
        nhan_mau_luc=t + timedelta(minutes=6),
        ket_qua_luc=None,
    )
    result = dung_hanh_trinh_khach(
        luot=dict(visit_id="synthetic", checked_in_at=t),
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
    review = dict(
        service_state=steps["LAM_DV"]["trang_thai"],
        review_state=steps["DOC_KQ"]["trang_thai"],
        note=steps["DOC_KQ"]["ghi_chu"],
    )
    closed = t + timedelta(minutes=15)
    result = dung_hanh_trinh_khach(
        luot=dict(
            visit_id="synthetic", checked_in_at=t, closed_at=closed, status="FINALIZED"
        ),
        su_kien=[("prescription.saved", t, {})],
        chi_dinh=[],
        hang=[],
        phien=[],
    )
    medicine = next(b for b in result["buoc"] if b["ma"] == "THUOC")
    tree = ast.parse((source / "src/clinicai/services/bill_service.py").read_text())
    nodes = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in {"_giam_duoc", "phan_bo_giam"}
    ]
    namespace: dict[str, Any] = dict(
        Sequence=Sequence,
        DongHoaDon=SimpleNamespace,
        CLINIC="CLINIC",
        DONG_KHONG_GIAM=frozenset({"lieu_trinh"}),
    )
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), "pinned-main", "exec"),
        namespace,
    )
    lines = [
        SimpleNamespace(
            thanh_tien=n, ben_thu="CLINIC", source_type="prescription", van_de=None
        )
        for n in [100, 100, 1]
    ]
    allocation = namespace["phan_bo_giam"](lines, 200)
    assert sum(allocation) == 200
    assert review["service_state"] == "doi_tac"
    assert review["review_state"] == "xong"
    assert medicine["trang_thai"] == "xong" and medicine["xong"] == closed
    print(
        json.dumps(
            dict(
                source=str(source),
                allocation=allocation,
                allocation_conserves=True,
                review=review,
                medicine=dict(
                    state=medicine["trang_thai"], completion_from_checkout=True
                ),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
