"""Bộ quét: khối quyền ↔ lego ↔ màn giao diện.

Mô hình (permissions/catalogue.py): QUYỀN thuộc một KHỐI; LEGO (= node thanh bên)
gồm nhiều khối và nhiều đường dẫn màn; quản lý bật/tắt lego cho từng người. Ba chỗ
có thể đứt dây mà không test nào kêu:

* KHỐI mồ côi — khối có quyền thật nhưng không lego nào chứa, cũng không nằm trong
  nhóm cố ý ẩn → quản lý không cấp được qua màn Phân quyền.
* LEGO trỏ màn không tồn tại — bật lego mà thanh bên dẫn tới trang 404.
* ÁNH XẠ chết — `VAI_THEO_LEGO` nhắc lego không còn trong `MAN`.

Đọc catalogue bằng cách nạp CHÍNH tệp ấy (chỉ dùng thư viện chuẩn, không database)
nên số liệu là số liệu thật, không phải bản parse regex.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

from ..khuon import (
    DoPhu,
    LoaiVanDe,
    MucBangChung,
    PhatHien,
    TrichDan,
    UuTien,
)
from ..nguon import Nguon

TEN = "quyen_lego"


def _nap_catalogue(tep: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("soat_catalogue_quyen", tep)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["soat_catalogue_quyen"] = mod  # dataclass cần tên module có thật
    spec.loader.exec_module(mod)
    return mod


def _cac_trang(nguon: Nguon) -> list[list[str]]:
    """Mọi `page.tsx` → các đoạn đường dẫn (`[id]` thành ký tự đại diện)."""
    ra: list[list[str]] = []
    goc = nguon.dash / "app"
    for p in goc.rglob("page.tsx"):
        doan = [
            "{}" if s.startswith("[") else s
            for s in p.relative_to(goc).parent.parts
            if not (s.startswith("(") and s.endswith(")"))
        ]
        ra.append(doan)
    return ra


def _co_trang(duong: str, trang: list[list[str]]) -> bool:
    ch = [s for s in duong.split("?")[0].strip("/").split("/") if s]
    return any(
        len(t) == len(ch) and all(a == b or "{}" in (a, b) for a, b in zip(t, ch))
        for t in trang
    )


def _dong_cua(nguon: Nguon, tep: Path, mau: str) -> int:
    pat = re.compile(mau)
    for i, d in enumerate(nguon.doc(tep).splitlines(), 1):
        if pat.search(d):
            return i
    return 1


def quet(nguon: Nguon) -> tuple[list[PhatHien], DoPhu]:
    do = DoPhu(TEN)
    ra: list[PhatHien] = []
    tep = nguon.py / "permissions" / "catalogue.py"
    if not tep.is_file():
        do.khong_nhin_duoc.append("không thấy permissions/catalogue.py")
        return ra, do
    c = _nap_catalogue(tep)
    rel = nguon.tuong_doi(tep)

    khoi_trong_lego = {k for m in c.MAN.values() for k in m.khoi}
    an = set(getattr(c, "KHOI_AN", set())) | set(getattr(c, "KHOI_NOI_BO", set()))
    for k in c.KHOI:
        if k in khoi_trong_lego or k in an:
            continue
        dong = _dong_cua(nguon, tep, rf'["\']{k}["\']')
        so_quyen = sum(1 for q in c.QUYEN.values() if q.khoi == k)
        ra.append(
            PhatHien(
                bo_quet=TEN,
                khoa=f"khoi-mo-coi {k}",
                loai=LoaiVanDe.LEGO_THIEU_LIEN_KET,
                uu_tien=UuTien.P5,
                muc_bang_chung=MucBangChung.QUAN_SAT,
                do_chac=0.7,
                tinh_huong=(
                    f"Khối `{k}` có {so_quyen} quyền nhưng không lego (`MAN`) nào "
                    "chứa và không nằm trong nhóm cố ý ẩn (KHOI_AN/KHOI_NOI_BO)."
                ),
                bang_chung=[
                    f"{rel} — `MAN` có {len(c.MAN)} lego, không lego nào liệt kê `{k}`",
                    "khối không thuộc KHOI_AN / KHOI_NOI_BO",
                ],
                rui_ro=(
                    "Quản lý không bật được khối này cho người khác trên màn Phân "
                    "quyền; chỉ cấp được bằng tay hoặc qua preset. Dễ thành quyền "
                    "'ai cũng không biết ai giữ'."
                ),
                de_xuat=(
                    "Nếu cố ý chỉ Quản lý dùng (như KHOI_CHI_QUAN_LY) → ghi chú một "
                    "dòng cạnh khai báo. Nếu không → gắn khối vào lego phù hợp."
                ),
                nguoi_chiu_trach_nhiem="Quang chốt ai được giữ quyền này; Tuyền sửa",
                thoi_diem="Khi chốt phân quyền lần tới",
                ket_qua_mong_doi="Mọi khối cấp được trên màn, hoặc có ghi chú lý do",
                cach_xac_nhan="Chạy lại bộ quét quyen_lego",
                trich_dan=[TrichDan(rel, dong, nguon.dong_thu(tep, dong))],
            )
        )

    trang = _cac_trang(nguon)
    n_duong = n_chet = 0
    for m in c.MAN.values():
        for d in m.cac_duong:
            n_duong += 1
            if _co_trang(d, trang):
                continue
            n_chet += 1
            dong = _dong_cua(nguon, tep, re.escape(f'"{d}"'))
            ra.append(
                PhatHien(
                    bo_quet=TEN,
                    khoa=f"lego-duong-chet {m.ma} {d}",
                    loai=LoaiVanDe.LEGO_THIEU_LIEN_KET,
                    uu_tien=UuTien.P2,
                    muc_bang_chung=MucBangChung.SUY_RA,
                    do_chac=0.6,
                    tinh_huong=(
                        f"Lego `{m.ma}` ({m.ten}) trỏ tới `{d}` nhưng không có "
                        "`page.tsx` nào cho đường dẫn này."
                    ),
                    bang_chung=[
                        f"{rel}:{dong}",
                        f"đã so với {len(trang)} trang trong src/dashboard/app",
                    ],
                    rui_ro="Bật lego cho người dùng rồi họ bấm vào trang 404.",
                    de_xuat="Kiểm đường dẫn: màn đã đổi tên/bị xoá thì sửa `MAN`.",
                    nguoi_chiu_trach_nhiem="Tuyền (dev)",
                    thoi_diem="Trước đợt lên staging kế tiếp",
                    ket_qua_mong_doi="Mọi đường dẫn của lego có trang thật",
                    cach_xac_nhan="Chạy lại bộ quét quyen_lego; bấm thanh bên 375/1280",
                    trich_dan=[TrichDan(rel, dong, nguon.dong_thu(tep, dong))],
                )
            )

    anh_xa = getattr(c, "VAI_THEO_LEGO", {})
    for ma in anh_xa:
        if ma in c.MAN:
            continue
        dong = _dong_cua(nguon, tep, rf'["\']{ma}["\']\s*:')
        ra.append(
            PhatHien(
                bo_quet=TEN,
                khoa=f"vai-theo-lego-chet {ma}",
                loai=LoaiVanDe.LEGO_THIEU_LIEN_KET,
                uu_tien=UuTien.P1,
                muc_bang_chung=MucBangChung.QUAN_SAT,
                do_chac=0.9,
                tinh_huong=(
                    f"`VAI_THEO_LEGO` gán vai cho lego `{ma}` nhưng `MAN` không có "
                    "lego này."
                ),
                bang_chung=[f"{rel}:{dong}"],
                rui_ro="Cửa cũ hỏi vai sẽ không bao giờ mở theo lego này.",
                de_xuat="Xoá dòng ánh xạ hoặc khôi phục lego.",
                nguoi_chiu_trach_nhiem="Tuyền (dev)",
                thoi_diem="Sớm",
                ket_qua_mong_doi="Ánh xạ vai chỉ trỏ lego còn sống",
                cach_xac_nhan="Chạy lại bộ quét quyen_lego",
                trich_dan=[TrichDan(rel, dong, nguon.dong_thu(tep, dong))],
            )
        )

    do.da_nhin = {
        "quyền": len(c.QUYEN),
        "khối": len(c.KHOI),
        "lego": len(c.MAN),
        "đường dẫn lego": n_duong,
        "đường dẫn không có trang": n_chet,
        "trang giao diện": len(trang),
    }
    do.khong_nhin_duoc = [
        "quyền được cấp mà không route nào ép (xem cua_route + bài test 403)",
        "preset từng vai có hợp lý với công việc thật hay không (việc của Quang)",
    ]
    return ra, do
