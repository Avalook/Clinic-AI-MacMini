"""Bàn đối tác cũ ĐÓNG BĂNG (ADR-0015, kế hoạch chặng 0, PR 0.3, ý 4).

Code xét nghiệm đối tác mới vào `services/xet_nghiem/`; `doi_tac_service.py` và router
`doi_tac.py` không được thêm hàm/cửa. Hai con số dưới đây CHỈ ĐƯỢC GIẢM: bớt được thì
hạ số trong cùng PR; muốn tăng là đang vi phạm luật 2 + 5 của `thiet-ke-code.md`.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "clinicai"

#: chỉ được giảm — ADR-0015 (05/11/2026: 1.236 dòng → 1.201 sau chặng 2: lõi
#: sổ thu hộ + `doc_so_tien` chuyển sang `services/xet_nghiem/`).
TRAN_DONG_DOI_TAC_SERVICE = 1201
#: chỉ được giảm — ADR-0015 (05/11/2026: 15 cửa).
TRAN_CUA_ROUTER_DOI_TAC = 15


def test_doi_tac_service_khong_dai_them() -> None:
    so_dong = len(
        (SRC / "services" / "doi_tac_service.py")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert so_dong <= TRAN_DONG_DOI_TAC_SERVICE, (
        f"doi_tac_service.py {so_dong} dòng > trần {TRAN_DONG_DOI_TAC_SERVICE}. "
        "Viết ở services/xet_nghiem/, file cũ chỉ thêm một dòng gọi."
    )


def test_router_doi_tac_khong_them_cua() -> None:
    ma = (SRC / "api" / "v1" / "routers" / "doi_tac.py").read_text(encoding="utf-8")
    so_cua = len(
        re.findall(
            r"^\s*@router\.(get|post|put|patch|delete|api_route|websocket)\(", ma, re.M
        )
    )
    assert so_cua <= TRAN_CUA_ROUTER_DOI_TAC, (
        f"router doi_tac.py có {so_cua} cửa > trần {TRAN_CUA_ROUTER_DOI_TAC}. "
        "Cửa mới đi router xet_nghiem.py."
    )
