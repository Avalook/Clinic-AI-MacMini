"""Mọi chỗ đọc `prescription` phải nói rõ: ĐƠN HIỆN HÀNH hay CỐ Ý GỒM LỊCH SỬ.

Contract tiền–thuốc CP6 (20/09/2026): dòng bác sĩ đã đính chính ở lại bảng làm
lịch sử (`removed_at IS NOT NULL`). Một câu đọc mới quên lọc sẽ lặng lẽ tính
thuốc cũ vào hoá đơn, nhà thuốc, checkout… — test này đỏ ngay khi điều đó xảy ra.

Luật cho MỖI câu SQL (Python) / chuỗi truy vấn Supabase (TS) có đọc bảng:
  * hiện hành   — có `removed_at IS NULL`;
  * lịch sử     — có `removed_at IS NOT NULL` (chỉ đọc dòng đã đính chính);
  * cả hai      — có dấu `rx:gom-ca-lich-su: <lý do>` NGAY TRONG câu (lý do
                  ≥ 15 ký tự), để người review thấy vì sao không lọc.
Không phải framework: chỉ đủ để câu mới quên lọc thì đỏ.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

GOC = Path(__file__).resolve().parents[2]
PY = GOC / "src" / "clinicai"
TS = [GOC / "src" / "dashboard" / "app", GOC / "src" / "dashboard" / "lib"]

DOC_BANG = re.compile(r"\b(FROM|JOIN)\s+(public\.)?prescription\b(?!_)", re.I)
LOC = re.compile(r"removed_at\s+IS\s+(NOT\s+)?NULL", re.I)
DAU = re.compile(r"rx:gom-ca-lich-su:\s*(?P<ly_do>[^*\n]{15,})")
TS_DOC = re.compile(r"""\.from\(\s*["']prescription["']\s*\)""")
TS_LOC = re.compile(r"""\.is\(\s*["']removed_at["']\s*,\s*null\s*\)""")


def _chuoi(cay: ast.AST) -> list[tuple[int, str]]:
    ra: list[tuple[int, str]] = []
    for n in ast.walk(cay):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            ra.append((n.lineno, n.value))
        elif isinstance(n, ast.JoinedStr):
            ra.append(
                (
                    n.lineno,
                    "".join(
                        v.value if isinstance(v, ast.Constant) else "{}"
                        for v in n.values
                    ),
                )
            )
    return ra


def cau_py_thieu_loc() -> list[str]:
    thieu = []
    for f in sorted(PY.rglob("*.py")):
        for dong, sql in _chuoi(ast.parse(f.read_text(encoding="utf-8"))):
            if DOC_BANG.search(sql) and not (LOC.search(sql) or DAU.search(sql)):
                thieu.append(f"{f.relative_to(GOC)}:{dong}")
    return thieu


def cau_ts_thieu_loc() -> list[str]:
    thieu = []
    for goc in TS:
        for f in sorted([*goc.rglob("*.ts"), *goc.rglob("*.tsx")]):
            if "node_modules" in f.parts:
                continue
            ma = f.read_text(encoding="utf-8")
            dong_ma = ma.splitlines()
            for m in TS_DOC.finditer(ma):
                dong = ma.count("\n", 0, m.start()) + 1
                # Câu truy vấn: từ `.from("prescription")` tới dòng có `;` ngoài
                # comment `//` (comment vẫn tính — dấu lịch sử nằm ở đó).
                cau: list[str] = []
                for d in dong_ma[dong - 1 :]:
                    cau.append(d)
                    if ";" in d.split("//", 1)[0]:
                        break
                noi = "\n".join(cau)
                if not (TS_LOC.search(noi) or DAU.search(noi)):
                    thieu.append(f"{f.relative_to(GOC)}:{dong}")
    return thieu


def test_moi_cau_python_doc_don_deu_noi_ro_hien_hanh_hay_lich_su() -> None:
    assert cau_py_thieu_loc() == []


def test_moi_truy_van_frontend_doc_don_deu_noi_ro() -> None:
    assert cau_ts_thieu_loc() == []


def test_may_kiem_bat_duoc_cau_quen_loc() -> None:
    """Máy kiểm tự kiểm: câu quên lọc phải bị bắt, câu có dấu thì qua."""
    quen = 'x = "SELECT id FROM public.prescription WHERE visit_id = $1"'
    loc = 'x = "SELECT id FROM prescription r WHERE r.removed_at IS NULL"'
    dau = (
        'x = "SELECT id FROM prescription'
        ' /* rx:gom-ca-lich-su: lịch sử bàn giao thuốc */"'
    )
    ngan = 'x = "SELECT id FROM prescription /* rx:gom-ca-lich-su: vì */"'
    bang_khac = 'x = "SELECT 1 FROM prescription_allocation"'

    def bat(ma: str) -> bool:
        return any(
            DOC_BANG.search(s) and not (LOC.search(s) or DAU.search(s))
            for _, s in _chuoi(ast.parse(ma))
        )

    assert bat(quen) and bat(ngan)
    assert not bat(loc) and not bat(dau) and not bat(bang_khac)
