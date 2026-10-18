"""Bộ quét: dây nối giao diện ↔ backend.

Hai chiều, cả hai đều là "lego thiếu liên kết":

1. ĐỨT — giao diện (Next) gọi `/api/v1/...` mà backend không có route nào khớp.
   Người bấm thấy nút không làm gì hoặc lỗi 404; không test nào bắt vì test
   backend không biết giao diện gọi gì.
2. MỒ CÔI — route ghi ở backend mà không đoạn giao diện nào nhắc tới. Có thể là
   API cho khách ngoài, cho script hay cho agent (khi đó đúng), hoặc là tính năng
   đã làm xong backend mà quên nối nút. Mức bằng chứng `chua_biet`, ưu tiên thấp.

KHỚP ĐƯỜNG DẪN theo từng đoạn: `{id}`, `{id:uuid}` (FastAPI) và `${x}` (TypeScript)
đều là ký tự đại diện. Chuỗi TS có biểu thức phức tạp trong `${…}` thì bỏ qua —
thà không báo còn hơn báo nhầm một đường chạy thật.
"""

from __future__ import annotations

import re

from ..khuon import (
    DoPhu,
    LoaiVanDe,
    MucBangChung,
    PhatHien,
    TrichDan,
    UuTien,
)
from ..nguon import Nguon

TEN = "day_fe_be"
GHI = {"POST", "PUT", "PATCH", "DELETE"}
RE_DUONG_TS = re.compile(r"""["'`](?:\$\{[^}]*\})?(/api/v1/[^"'`\s]*)""")
WILD = "{}"


def _chuan_py(duong: str) -> list[str]:
    return [WILD if s.startswith("{") else s for s in duong.strip("/").split("/")]


def _chuan_ts(duong: str) -> list[str] | None:
    duong = re.split(r"[?#]", duong, maxsplit=1)[0]
    if "*" in duong or duong.count("${") != duong.count("}"):
        return None  # biểu thức lồng — không đoán
    duong = re.sub(r"\$\{[^}]*\}", WILD, duong)
    if "$" in duong or "{" in duong.replace(WILD, ""):
        return None
    ra = duong.strip("/").split("/")
    # `…/abc${x}` (đuôi dán liền biến) — không rõ đoạn nào, bỏ.
    if any(WILD in s and s != WILD for s in ra):
        return None
    return ra


def _khop(a: list[str], b: list[str]) -> bool:
    return len(a) == len(b) and all(x == y or WILD in (x, y) for x, y in zip(a, b))


def quet(nguon: Nguon) -> tuple[list[PhatHien], DoPhu]:
    do = DoPhu(TEN)
    ra: list[PhatHien] = []
    route = nguon.routes
    mau = [(_chuan_py(r.duong), r) for r in route]

    goi: dict[str, tuple[list[str], str, int, str]] = {}
    bo_qua = 0
    for tep in nguon.ts_dashboard():
        rel = nguon.tuong_doi(tep)
        for i, txt in enumerate(nguon.doc(tep).splitlines(), 1):
            for m in RE_DUONG_TS.finditer(txt):
                ch = _chuan_ts(m.group(1))
                if ch is None:
                    bo_qua += 1
                    continue
                goi.setdefault("/".join(ch), (ch, rel, i, txt.strip()))

    da_goi = 0
    for khoa, (ch, rel, dong, doan) in sorted(goi.items()):
        if any(_khop(ch, m) for m, _ in mau):
            da_goi += 1
            continue
        ra.append(
            PhatHien(
                bo_quet=TEN,
                khoa=f"fe->be /{khoa}",
                loai=LoaiVanDe.LEGO_THIEU_LIEN_KET,
                uu_tien=UuTien.P2,
                muc_bang_chung=MucBangChung.SUY_RA,
                do_chac=0.6,
                tinh_huong=(
                    f"Giao diện gọi `/{khoa}` ({rel}:{dong}) nhưng backend không có "
                    "route nào khớp đường dẫn này."
                ),
                bang_chung=[
                    f"{rel}:{dong}",
                    f"đã so với {len(route)} route FastAPI theo từng đoạn đường dẫn",
                ],
                rui_ro=(
                    "Nút/màn gọi đường này lỗi 404 hoặc không làm gì; người bấm "
                    "không biết dữ liệu có được lưu hay không."
                ),
                de_xuat=(
                    "Mở dòng gọi: (a) đường đúng nhưng ghép chuỗi động script không "
                    "hiểu → bỏ qua; (b) route đã đổi tên/bị xoá → sửa chỗ gọi hoặc "
                    "khôi phục route."
                ),
                nguoi_chiu_trach_nhiem="Tuyền (dev)",
                thoi_diem="Trước đợt lên staging kế tiếp",
                ket_qua_mong_doi="Mọi lời gọi giao diện tìm được route backend",
                cach_xac_nhan="Chạy lại bộ quét day_fe_be; bấm thật màn liên quan",
                phuong_an_khac="Thêm bài test hợp đồng: mọi chuỗi /api/v1 trong "
                "giao diện phải khớp một route",
                trich_dan=[TrichDan(rel, dong, doan)],
            )
        )

    chuoi_ts = [ch for ch, *_ in goi.values()]
    mo_coi = 0
    for ch, r in mau:
        if r.method not in GHI or r.da_nghi:
            continue
        if any(_khop(ch, c) for c in chuoi_ts):
            continue
        mo_coi += 1
        rel = nguon.tuong_doi(r.tep)
        ra.append(
            PhatHien(
                bo_quet=TEN,
                khoa=f"be-mo-coi {r.method} {r.duong}",
                loai=LoaiVanDe.LEGO_THIEU_LIEN_KET,
                uu_tien=UuTien.P6,
                muc_bang_chung=MucBangChung.CHUA_BIET,
                do_chac=0.3,
                tinh_huong=(
                    f"Route ghi `{r.method} {r.duong}` ({rel}:{r.dong}) không có "
                    "chuỗi nào trong giao diện nhắc tới."
                ),
                bang_chung=[f"{rel}:{r.dong}", "không khớp chuỗi /api/v1 nào trong TS"],
                rui_ro="Tính năng backend đã xong nhưng người dùng không với tới được.",
                de_xuat=(
                    "Hỏi chủ route: dành cho script/đối tác/agent (ghi chú vào "
                    "docstring) hay quên nối nút."
                ),
                nguoi_chiu_trach_nhiem="Tuyền (dev)",
                thoi_diem="Khi rảnh — ưu tiên thấp",
                ket_qua_mong_doi="Route có chủ: có nút gọi, hoặc ghi rõ ai gọi",
                cach_xac_nhan="Chạy lại bộ quét day_fe_be",
                trich_dan=[TrichDan(rel, r.dong, nguon.dong_thu(r.tep, r.dong))],
            )
        )

    do.da_nhin = {
        "chuỗi /api/v1 trong giao diện": len(goi),
        "khớp route": da_goi,
        "route FastAPI": len(route),
        "route ghi không ai gọi": mo_coi,
    }
    do.khong_nhin_duoc = [
        f"{bo_qua} chuỗi đường dẫn ghép động phức tạp (bỏ qua có chủ ý)",
        "đường gọi qua bảng ánh xạ/biến ở tầng giữa (route.ts dùng khoá thao tác)",
        "phương thức HTTP (chỉ so đường dẫn)",
        "khách gọi ngoài giao diện: đối tác, script, agent",
    ]
    return ra, do
