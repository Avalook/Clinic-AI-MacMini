"""Đặc tả ``doc_ngay`` / ``iso`` / ``iso_sau`` — MỘT hàm cho mỗi câu hỏi (TK1).

Trước 24/11/2026: ``doc_ngay`` 8 bản + ``_ngay`` 2 bản (7+2 thân khác nhau),
``_iso`` 25 bản + ``_gio_iso`` (14 thân). Bảng hành vi cũ từng bản trên cùng bộ
đầu vào dưới đây nằm trong thân PR gộp. Test cuối tệp canh để bản sao không
mọc lại.
"""

from __future__ import annotations

import ast
import pathlib
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest

from clinicai.core.clock import doc_ngay, doc_ngay_xem, iso, iso_sau

VN = timezone(timedelta(hours=7))
N = date(2026, 11, 8)

# (đầu vào, doc_ngay, doc_ngay(go_tay=True), doc_ngay_xem)
BANG_NGAY: list[tuple[Any, date | None, date | None, date | None]] = [
    (None, None, None, None),
    ("", None, None, None),
    ("   ", None, None, None),
    ("2026-11-08", N, N, N),
    (" 2026-11-08 ", N, N, N),
    ("2026-11-08T10:00", N, N, None),
    # Lấy phần ngày như chữ viết, KHÔNG đổi múi (giữ hành vi các bản cũ [:10]).
    ("2026-11-08T23:30:00+00:00", N, N, None),
    ("2026-11-08 10:00", N, N, None),
    ("2026-11-08abc", None, None, None),
    ("2026-11-08'; DROP TABLE visit; --", None, None, None),
    ("2026-11-8", None, N, None),
    ("20261108", None, None, None),
    ("2026-W45-1", None, None, None),
    ("08/11/2026", None, N, None),
    ("8/11/2026", None, N, None),
    ("31/02/2026", None, None, None),
    ("2026-02-30", None, None, None),
    ("2026-13-01", None, None, None),
    ("0000-01-01", None, None, None),
    ("abc", None, None, None),
    ("x" * 50, None, None, None),
    ("2019-12-31", date(2019, 12, 31), date(2019, 12, 31), None),
    (20261108, None, None, None),
    (1.5, None, None, None),
    (True, None, None, None),
    ([], None, None, None),
    ({}, None, None, None),
    (["2026-11-08"], None, None, None),
    (N, N, N, N),
    (datetime(2026, 11, 8, 23, 0, tzinfo=VN), N, N, N),
    (datetime(2026, 11, 8, 23, 0), N, N, N),
]


@pytest.mark.parametrize(("vao", "chuan", "go_tay", "xem"), BANG_NGAY)
def test_doc_ngay_bang_dac_ta(
    vao: Any, chuan: date | None, go_tay: date | None, xem: date | None
) -> None:
    assert doc_ngay(vao) == chuan
    assert doc_ngay(vao, go_tay=True) == go_tay
    assert doc_ngay_xem(vao) == xem


def test_doc_ngay_tra_date_khong_tra_datetime() -> None:
    # Bản cũ ở kho_email trả nguyên ``datetime`` — so với ``date`` thì Python ném.
    ra = doc_ngay(datetime(2026, 11, 8, 23, 0, tzinfo=VN))
    assert type(ra) is date


D = datetime(2026, 11, 8, 23, 5, tzinfo=VN)

# (đầu vào, iso, iso_sau)
BANG_ISO: list[tuple[Any, Any, Any]] = [
    (None, None, None),
    ("", None, ""),
    ("2026-11-08T10:00", "2026-11-08T10:00", "2026-11-08T10:00"),
    ("rác", None, "rác"),
    ("2026-11-08", "2026-11-08", "2026-11-08"),
    (N, "2026-11-08", "2026-11-08"),
    (D, "2026-11-08T23:05:00+07:00", "2026-11-08T23:05:00+07:00"),
    (datetime(2026, 11, 8, 10, 0), "2026-11-08T10:00:00", "2026-11-08T10:00:00"),
    (0, None, 0),
    (5, None, 5),
    ({"a": D, "b": 1}, None, {"a": "2026-11-08T23:05:00+07:00", "b": 1}),
    ([D, None], None, ["2026-11-08T23:05:00+07:00", None]),
    (
        {"x": [{"luc": N}]},
        None,
        {"x": [{"luc": "2026-11-08"}]},
    ),
    (uuid.UUID(int=1), None, uuid.UUID(int=1)),
]


@pytest.mark.parametrize(("vao", "mot", "sau"), BANG_ISO)
def test_iso_bang_dac_ta(vao: Any, mot: Any, sau: Any) -> None:
    assert iso(vao) == mot
    assert iso_sau(vao) == sau


def test_iso_dung_chu_t_khong_dung_dau_cach() -> None:
    assert iso(D) != str(D)
    assert "T" in (iso(D) or "")


# ── Canh bản sao không mọc lại ──────────────────────────────────────────────
GOC = pathlib.Path(__file__).resolve().parents[2] / "clinicai"
# (``_ngay`` cũ ở cskh / kho_email đã gộp; ``xuat_hoa_don._ngay`` là câu hỏi
# khác — ISO → "dd/mm/yyyy" để in — nên không canh tên đó.)
TEN_DA_GOP = {"doc_ngay", "_iso", "_gio_iso"}


def _dinh_nghia(ten: set[str]) -> list[str]:
    thay: list[str] = []
    for p in GOC.rglob("*.py"):
        if p.relative_to(GOC).as_posix() == "core/clock.py":
            continue
        for n in ast.parse(p.read_text(encoding="utf-8")).body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in ten:
                thay.append(f"{p.relative_to(GOC)}:{n.lineno} {n.name}")
    return sorted(thay)


def test_khong_ban_sao_doc_ngay_iso_ngoai_clock() -> None:
    thay = _dinh_nghia(TEN_DA_GOP)
    assert thay == [], (
        "Đọc ngày / đổi mốc giờ ra ISO đã có MỘT hàm ở clinicai.core.clock "
        f"(doc_ngay, iso, iso_sau) — gọi nó, đừng viết bản sao: {thay}"
    )


#: Số chỗ còn tự gọi ``fromisoformat(`` ngoài clock.py (hàm tên khác, chưa gộp
#: ở PR 24/11; trước PR là 45). CHỈ ĐƯỢC GIẢM: chỗ mới đọc ngày thì gọi
#: ``doc_ngay``; gộp thêm chỗ nào thì hạ số này xuống.
TRAN_FROMISOFORMAT = 36


def test_fromisoformat_ngoai_clock_chi_duoc_giam() -> None:
    dem = sum(
        p.read_text(encoding="utf-8").count("fromisoformat(")
        for p in GOC.rglob("*.py")
        if p.relative_to(GOC).as_posix() != "core/clock.py"
    )
    assert dem <= TRAN_FROMISOFORMAT, (
        f"{dem} chỗ tự gọi fromisoformat ngoài clinicai.core.clock (trần "
        f"{TRAN_FROMISOFORMAT}). Đọc ngày/giờ người dùng → doc_ngay."
    )
