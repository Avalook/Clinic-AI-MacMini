"""Bộ quét: sự kiện khai ↔ sự kiện phát ↔ bên nghe.

`events/catalogue.py` là nơi DUY NHẤT khai sự kiện. Ba kiểu đứt:

* PHÁT MÀ KHÔNG KHAI — `emit_event` sẽ từ chối lúc chạy: lệnh nghiệp vụ hỏng đúng
  lúc có người bấm. CI đã canh; bộ quét này là lớp độc lập thứ hai.
* KHAI MÀ KHÔNG AI PHÁT — danh mục nói dối: bên nghe chờ mãi một sự kiện không tới.
* PHÁT MÀ KHÔNG AI NGHE — có thể cố ý (chỉ để lưu vết), nên gom MỘT phát hiện duy
  nhất liệt kê hết, ưu tiên thấp, để người quyết cái nào cần dây nối thêm.
"""

from __future__ import annotations

import ast

from ..khuon import (
    DoPhu,
    LoaiVanDe,
    MucBangChung,
    PhatHien,
    TrichDan,
    UuTien,
)
from ..nguon import Nguon, ten_goi

TEN = "su_kien"


def _chuoi(n: ast.expr | None) -> list[str]:
    """Giá trị chuỗi hằng của một biểu thức (kể cả `'a' if x else 'b'`)."""
    if isinstance(n, ast.Constant) and isinstance(n.value, str):
        return [n.value]
    if isinstance(n, ast.IfExp):
        return _chuoi(n.body) + _chuoi(n.orelse)
    return []


def quet(nguon: Nguon) -> tuple[list[PhatHien], DoPhu]:
    do = DoPhu(TEN)
    ra: list[PhatHien] = []
    tep = nguon.py / "events" / "catalogue.py"
    if not tep.is_file():
        do.khong_nhin_duoc.append("không thấy events/catalogue.py")
        return ra, do
    rel = nguon.tuong_doi(tep)
    cay = nguon.cay_py.get(tep)
    if cay is None:
        do.khong_nhin_duoc.append("catalogue.py không parse được")
        return ra, do

    khai: dict[str, tuple[int, list[str]]] = {}
    for n in ast.walk(cay):
        if isinstance(n, ast.Call) and ten_goi(n.func) == "SuKien":
            kw = {k.arg: k.value for k in n.keywords}
            ten = _chuoi(kw.get("ten"))
            cons = kw.get("consumers")
            ds = (
                [e.id for e in cons.elts if isinstance(e, ast.Name)]
                if isinstance(cons, (ast.List, ast.Tuple))
                else []
            )
            if ten:
                khai[ten[0]] = (n.lineno, ds)

    phat: dict[str, tuple[str, int]] = {}
    for p, c in nguon.cay_py.items():
        if p.name == "emit.py":
            continue
        for n in ast.walk(c):
            if isinstance(n, ast.Call) and ten_goi(n.func) == "emit_event":
                for k in n.keywords:
                    if k.arg == "ten":
                        for t in _chuoi(k.value):
                            phat.setdefault(t, (nguon.tuong_doi(p), n.lineno))

    for t, (rel_p, dong) in sorted(phat.items()):
        if t in khai:
            continue
        ra.append(
            PhatHien(
                bo_quet=TEN,
                khoa=f"phat-khong-khai {t}",
                loai=LoaiVanDe.LOGIC_CO_VAN_DE,
                uu_tien=UuTien.P0,
                muc_bang_chung=MucBangChung.QUAN_SAT,
                do_chac=0.9,
                tinh_huong=f'`emit_event(ten="{t}")` ({rel_p}:{dong}) nhưng danh '
                "mục sự kiện không khai tên này.",
                bang_chung=[f"{rel_p}:{dong}", f'{rel} không có SuKien(ten="{t}")'],
                rui_ro="emit_event từ chối khi chạy → lệnh nghiệp vụ đó lỗi.",
                de_xuat="Khai sự kiện trong events/catalogue.py (payload, consumers).",
                nguoi_chiu_trach_nhiem="Tuyền (dev)",
                thoi_diem="Ngay",
                ket_qua_mong_doi="Mọi sự kiện phát ra đều đã khai",
                cach_xac_nhan="Chạy lại bộ quét su_kien; test emit",
                trich_dan=[TrichDan(rel_p, dong, "emit_event")],
                muc_viec=2,
            )
        )
    nguon_p = {t for t in phat}
    for t, (dong, _) in sorted(khai.items()):
        if t in nguon_p:
            continue
        # phát gián tiếp (SQL trigger / hằng số) → chỉ báo khi không nơi nào nhắc tên
        nhac = any(t in nguon.doc(p) for p in nguon.py_nguon() if p != tep) or any(
            t in nguon.doc(m) for m in nguon.migrations()
        )
        if nhac:
            continue
        ra.append(
            PhatHien(
                bo_quet=TEN,
                khoa=f"khai-khong-phat {t}",
                loai=LoaiVanDe.LEGO_THIEU_LIEN_KET,
                uu_tien=UuTien.P5,
                muc_bang_chung=MucBangChung.SUY_RA,
                do_chac=0.6,
                tinh_huong=f"Sự kiện `{t}` được khai nhưng không nơi nào phát/nhắc.",
                bang_chung=[f"{rel}:{dong}"],
                rui_ro="Bên nghe chờ một sự kiện không bao giờ tới.",
                de_xuat="Xoá khai báo thừa, hoặc nối nơi phát còn thiếu.",
                nguoi_chiu_trach_nhiem="Tuyền (dev)",
                thoi_diem="Khi dọn catalogue",
                ket_qua_mong_doi="Mọi sự kiện khai đều có nơi phát",
                cach_xac_nhan="Chạy lại bộ quét su_kien",
                trich_dan=[TrichDan(rel, dong, nguon.dong_thu(tep, dong))],
            )
        )

    khong_nghe = sorted(t for t, (_, c) in khai.items() if not c)
    if khong_nghe:
        dong = khai[khong_nghe[0]][0]
        ra.append(
            PhatHien(
                bo_quet=TEN,
                khoa="phat-khong-ai-nghe",
                loai=LoaiVanDe.LEGO_THIEU_LIEN_KET,
                uu_tien=UuTien.P6,
                muc_bang_chung=MucBangChung.CHUA_BIET,
                do_chac=0.3,
                tinh_huong=(
                    f"{len(khong_nghe)} sự kiện được phát nhưng không bên nghe nào: "
                    + ", ".join(khong_nghe)
                    + "."
                ),
                bang_chung=[f"{rel}:{dong} (SuKien đầu tiên trong danh sách)"],
                rui_ro=(
                    "Nếu chúng chỉ để lưu vết thì không sao; nếu đáng lẽ phải báo/"
                    "tạo việc cho ai đó (vd vật tư nhập chờ duyệt, quyền được cấp) "
                    "thì chuyện đó đang không xảy ra."
                ),
                de_xuat=(
                    "Đi từng cái: 'chỉ để lưu vết' → ghi chú; 'cần báo ai đó' → thêm "
                    "consumer/dây chuông."
                ),
                nguoi_chiu_trach_nhiem="Quang chốt sự kiện nào cần báo ai; Tuyền nối",
                thoi_diem="Khi rà dây chuông",
                ket_qua_mong_doi="Mỗi sự kiện có bên nghe, hoặc ghi rõ 'chỉ lưu vết'",
                cach_xac_nhan="Chạy lại bộ quét su_kien",
                trich_dan=[TrichDan(rel, dong, nguon.dong_thu(tep, dong))],
            )
        )

    do.da_nhin = {
        "sự kiện khai": len(khai),
        "sự kiện phát (chuỗi hằng)": len(phat),
        "khai nhưng không bên nghe": len(khong_nghe),
    }
    do.khong_nhin_duoc = [
        "sự kiện phát bởi trigger/hàm SQL (chỉ kiểm tên có nhắc ở migration)",
        "tên sự kiện ghép động ngoài `'a' if x else 'b'`",
        "bên nghe có thật sự chạy đúng (cần log vận hành, không phải đọc code)",
    ]
    return ra, do
