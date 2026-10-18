"""Kiểm trích dẫn — cửa chặn "bịa số dòng".

Mỗi phát hiện phải chỉ được `tệp:dòng` và đoạn chữ nằm đó. Script mở tệp ra đối
chiếu; không khớp thì phát hiện bị LOẠI trước khi đến tay người (độ chính xác của
trích dẫn đo được bằng máy, không cần người đoán).

Bộ quét tĩnh viết bằng tay hiếm khi sai chỗ này, nhưng tầng model (đợt 2) sai
thường xuyên — bài kiểm nằm sẵn ở đây để mọi tầng đi qua MỘT cửa.
"""

from __future__ import annotations

import re

from .khuon import PhatHien, TrichDan
from .nguon import Nguon

_KHOANG = re.compile(r"\s+")
CUA_SO = 3  # dòng lệch tối đa mà vẫn chấp nhận (tệp vừa sửa vài dòng)


def _gon(s: str) -> str:
    return _KHOANG.sub(" ", s).strip()


def kiem_mot(nguon: Nguon, td: TrichDan) -> str | None:
    """None = hợp lệ; ngược lại là lý do."""
    p = nguon.goc / td.tep
    if not p.is_file():
        return f"tệp không tồn tại: {td.tep}"
    ds = nguon.doc(p).splitlines()
    if not 1 <= td.dong <= len(ds):
        return f"dòng {td.dong} ngoài tệp ({len(ds)} dòng): {td.tep}"
    if not td.doan.strip():
        return f"trích dẫn rỗng: {td.tep}:{td.dong}"
    mau = _gon(td.doan)
    lo, hi = max(0, td.dong - 1 - CUA_SO), min(len(ds), td.dong + CUA_SO)
    if mau not in _gon(" ".join(ds[lo:hi])):
        return f"đoạn chữ không có quanh {td.tep}:{td.dong}"
    return None


def loc(
    nguon: Nguon, ds: list[PhatHien]
) -> tuple[list[PhatHien], list[tuple[PhatHien, str]]]:
    """(giữ, loại kèm lý do)."""
    giu: list[PhatHien] = []
    loai: list[tuple[PhatHien, str]] = []
    for ph in ds:
        if not ph.trich_dan:
            loai.append((ph, "không có trích dẫn nào"))
            continue
        loi = next((r for td in ph.trich_dan if (r := kiem_mot(nguon, td))), None)
        if loi:
            loai.append((ph, loi))
        else:
            giu.append(ph)
    return giu, loai
