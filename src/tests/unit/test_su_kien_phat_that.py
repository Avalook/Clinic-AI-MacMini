"""Danh mục sự kiện khớp với CODE THẬT (24/09/2026, bước 6 đợt bóc lõi).

`test_o_cam_module` chỉ so các bản KHAI với nhau. Bài này đọc mã nguồn:
  * mọi tên sự kiện code phát (`emit_event(… ten="x.y")`) đều có trong danh mục;
  * mọi sự kiện trong danh mục đều được phát ở ĐÂU ĐÓ — khai mà không ai phát
    là một dây nối chết: khối nghe nó chờ mãi mà không biết;
  * mọi file trong `events/consumers/` đều đăng ký bên nhận.
Thêm một lối phát mới mà quên khai (hoặc ngược lại) → đỏ ngay ở CI.
"""

from __future__ import annotations

import pathlib
import re

from clinicai.events.catalogue import DANH_MUC

GOC = pathlib.Path(__file__).resolve().parents[2] / "clinicai"
_TEN = re.compile(r"emit_event\(.*?\bten=([^\n]*)", re.S)
_CHUOI = re.compile(r'"([a-z_]+(?:\.[a-z_]+)+)"')


def _ten_da_phat() -> dict[str, set[str]]:
    phat: dict[str, set[str]] = {}
    for f in GOC.rglob("*.py"):
        if f.name == "emit.py":
            continue
        for m in _TEN.finditer(f.read_text(encoding="utf-8")):
            for ten in _CHUOI.findall(m.group(1)):
                phat.setdefault(ten, set()).add(str(f.relative_to(GOC)))
    return phat


def test_ten_phat_ra_deu_co_trong_danh_muc() -> None:
    la = {t: f for t, f in _ten_da_phat().items() if t not in DANH_MUC}
    assert not la, f"Phát sự kiện chưa khai trong danh mục: {la}"


def test_moi_su_kien_trong_danh_muc_deu_co_noi_phat() -> None:
    chet = sorted(set(DANH_MUC) - set(_ten_da_phat()))
    assert not chet, f"Sự kiện khai mà không code nào phát (dây chết): {chet}"


def test_moi_file_ben_nhan_deu_dang_ky() -> None:
    thieu = [
        f.name
        for f in (GOC / "events" / "consumers").glob("*.py")
        if f.name != "__init__.py"
        and "dang_ky(" not in f.read_text(encoding="utf-8")
        and "dang_ky_loai(" not in f.read_text(encoding="utf-8")
    ]
    assert not thieu, f"File bên nhận không đăng ký gì: {thieu}"
