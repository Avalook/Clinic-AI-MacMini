#!/usr/bin/env python3
"""Nạp nhân sự THẬT của PK Kim Ngưu và bảng gán vị trí, từ file Excel xếp lịch.

    # trên máy (có openpyxl), đọc Excel ra dạng trung gian:
    python scripts/nhan-su-kim-nguu.py lich.xlsx --xuat nhan-su.json

    # trên máy chủ (không có openpyxl), nạp vào database:
    python scripts/nhan-su-kim-nguu.py nhan-su.json           # THỬ KHÔ
    python scripts/nhan-su-kim-nguu.py nhan-su.json --that    # làm thật

Nhận `.xlsx` thì tự đọc; nhận `.json` thì dùng bản đã đọc sẵn. Chia đôi vì ảnh
API đang chạy KHÔNG có `openpyxl`, và cài thêm thư viện vào một container đang
đón bệnh nhân để chạy một việc một lần là cái giá sai. Bản trung gian cũng là
thứ đọc được bằng mắt trước khi ghi vào database.

Làm bốn việc, theo thứ tự, và mỗi việc chỉ chạm thứ nó phải chạm:

    1. Tên đầy đủ  — `staff.full_name` lấy từ trang "Điện thoại nhân sự",
       `staff.short_name` giữ tên gọi trong lịch ("BS Quyết"). Hai cột đã có
       sẵn và đây đúng là việc của chúng.
    2. Cơ sở       — `staff.primary_location_id` → "Kim Ngưu" (Tuyền chốt 16/09).
    3. Vị trí      — `staff_vi_tri`, suy ra từ CHÍNH lịch hai tuần, kèm số ca
       thật làm bằng chứng.
    4. Người mới   — ai có trong Excel mà chưa có hồ sơ thì tạo, kèm tài khoản.

FILE EXCEL KHÔNG VÀO GIT, CÓ CHỦ Ý. Nó chứa số điện thoại và email của 35 người
thật. Kho mã đã có luật ấy từ `clinic_roster.sql`: tên gọi thì được, số điện
thoại và CCCD thì không. Script nhận đường dẫn lúc chạy; ai cần chạy thì xin
file, không lấy từ kho.

TÊN MƠ HỒ THÌ DỪNG, KHÔNG ĐOÁN. Lịch có `Vân Anh`, danh sách có **Nguyễn Vân
Anh** và **Vũ Hoàng Vân Anh** — chính người xếp lịch cũng có lúc viết `N. Vân
Anh` / `V. Vân Anh`, tức họ biết là hai người. Tương tự `Huế` (Vũ Thị Huế /
Trần Thị Thu Huế), `BS Tiến`, `BS Linh`, `BS Hằng`. Gán nhầm một trong những
tên ấy là gán ca trực của người này cho người kia, và KPI lẫn trách nhiệm đi
theo. Script in ra rồi bỏ qua; Tuyền chốt từng ca, khai vào `PHAN_XU` bên dưới.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from typing import Any

import asyncpg
import httpx

TEN_MIEN = os.environ.get("DUOI_TEN_DANG_NHAP", "dr4women.vn")
MAT_KHAU = os.environ.get("MAT_KHAU_MOI", "12345678")
TEN_CO_SO = os.environ.get("CO_SO", "Kim Ngưu")

#: Tên trong lịch → tên đầy đủ trong danh sách, cho những ca Tuyền đã chốt.
#: Để trống nghĩa là chưa ai chốt, và script sẽ bỏ qua tên ấy chứ không đoán.
PHAN_XU: dict[str, str] = {}

#: 13 TÊN LUÔN ĐỂ TRỐNG — Tuyền chốt 16/09/2026: "13 tên kia để trống".
#:
#: Không dựa vào việc bộ ghép "tình cờ không khớp" chúng. `Phương Thúy` là bằng
#: chứng: bộ ghép tự gán nó cho điều dưỡng `Đỗ Thuý Phương Anh` vì
#: {phương, thuý} ⊂ {đỗ, thuý, phương, anh} — đúng cái tên đã bị gộp nhầm một
#: lần trước đó. Lời hứa "để trống" phải là một danh sách, không phải hệ quả.
#: So bằng `khoa_goi`, nên mọi cách viết (dấu chấm, khoảng trắng thừa) đều dính.
DE_TRONG: frozenset[str] = frozenset(
    {
        "Thanh Huyền",
        "Ngọc Giầu",
        "BS Linh",
        "Anh Vũ",
        "Hồng Thơm",
        "Ngát",
        "Phương Liên",
        "BS Thùy Linh",
        "Trang A",
        "Hiền",
        "Xuân Anh",
        "Ngát - CSKH",
        "Phương Thúy",
    }
)

#: Nhóm trong trang "Điện thoại nhân sự" → vai trong hệ thống.
#: `BS.YHDP` = y học dự phòng; trong lịch người này đứng "Hỏi bệnh ban đầu".
NHOM_SANG_VAI = {
    "BS Nội tiết": "DOCTOR",
    "BS.YHDP": "DOCTOR",
    "BS Sản": "DOCTOR",
    "BS Siêu âm": "ULTRASOUND_DOCTOR",
    "ĐIỀU DƯỠNG": "NURSE_ULTRASOUND",
}

#: (Phòng, Vị trí) trong Excel → mã vị trí trong `vi_tri_lam_viec`.
#: Khai tay chứ không dò chuỗi: tên vị trí trong Excel có dấu ngoặc dài, xuống
#: dòng, và hai phòng khác tầng cùng tên "Phòng siêu âm"/"Phòng Siêu âm" chỉ
#: khác một chữ hoa.
O_SANG_MA = {
    ("Quầy tiếp đón", "Lễ tân"): "T1_LETAN",
    ("Quầy tiếp đón", "Thu ngân"): "T1_THUNGAN",
    ("Quầy tiếp đón", "Đo chỉ số sức khoẻ"): "T1_DOCHISO",
    ("Quầy tiếp đón", "Lấy mẫu"): "T1_LAYMAU",
    ("Phòng Nội tiết", "BS Nội tiết"): "T1_BS_NOITIET",
    ("Phòng Nội tiết", "Hỏi bệnh ban đầu"): "T1_HOIBENH",
    ("Phòng Nội tiết", "Thư ký y khoa"): "T1_TKYK",
    ("Phòng thủ thuật", "BS"): "T1_TT_BS",
    ("Phòng thủ thuật", "Điều dưỡng"): "T1_TT_DD",
    ("Phòng Siêu âm", "BS"): "T1_SA_BS",
    ("Phòng Siêu âm", "Điều dưỡng"): "T1_SA_DD",
    ("Thủ thuật ngoài giờ", "BS"): "T1_TTNG_BS",
    ("Thủ thuật ngoài giờ", "Điều dưỡng 1"): "T1_TTNG_DD1",
    ("Thủ thuật ngoài giờ", "Điều dưỡng 2"): "T1_TTNG_DD2",
    ("Quầy thuốc", "Xếp thuốc + Giải thích thuốc"): "T2_XEPTHUOC",
    ("Quầy thuốc", "Tạo đơn thuốc + Thu ngân"): "T2_TAODON",
    ("Phòng Sàn chậu", "BS Sàn chậu"): "T4_SANCHAU_BS",
    ("Phòng Sàn chậu", "BS Thủ thuật"): "T4_SANCHAU_BSTT",
    ("Phòng Sàn chậu", "Điều dưỡng Sàn chậu"): "T4_SANCHAU_DD",
    ("Phòng Sản - Biofeedback", "BS Sản"): "T4_SAN_BS",
    ("Phòng Sản - Biofeedback", "Điều dưỡng Sản"): "T4_SAN_DD",
    ("Phòng Sản - Biofeedback", "Điều dưỡng Bio"): "T4_BIO_DD",
    ("Phòng siêu âm", "BS 1"): "T4_SA_BS1",
    ("Phòng siêu âm", "Điều dưỡng 1"): "T4_SA_DD1",
    ("Phòng siêu âm", "BS 2"): "T4_SA_BS2",
    ("Phòng siêu âm", "Điều dưỡng 2"): "T4_SA_DD2",
    # Bảng tuần 28/09/2026 (migration 20261001200000): hai phòng siêu âm gộp
    # thành "Phòng siêu âm 2 máy" (BS 1 = vị trí T1_SA_*, BS 2 = T4_SA_*1),
    # Điều dưỡng Bio sang Phòng Sàn chậu, phòng Sản đổi tên.
    ("Phòng siêu âm 2 máy", "BS 1"): "T1_SA_BS",
    ("Phòng siêu âm 2 máy", "Điều dưỡng 1"): "T1_SA_DD",
    ("Phòng siêu âm 2 máy", "BS 2"): "T4_SA_BS1",
    ("Phòng siêu âm 2 máy", "Điều dưỡng 2"): "T4_SA_DD1",
    ("Phòng Sàn chậu", "Điều dưỡng Bio"): "T4_BIO_DD",
    ("Phòng Sản/ Siêu âm", "BS Sản / BS 3"): "T4_SAN_BS",
    ("Phòng Sản/ Siêu âm", "Điều dưỡng Sản / Điều dưỡng 3"): "T4_SAN_DD",
}


def bo_dau(s: str) -> str:
    """Bỏ dấu để so tên. `Đ` phải đổi TRƯỚC: nó là chữ cái riêng, không phải D+dấu."""
    s = s.replace("Đ", "D").replace("đ", "d")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def goi_gon(s: str) -> str:
    """Bỏ mọi tiền tố chức danh để còn lại tên gọi. "BS SA Tiến" → "tien"."""
    s = re.sub(r"^(bs\.?\s*sa|bs\.?|dr\.?|đd|dd|tl)\s+", "", s.strip(), flags=re.I)
    s = re.sub(r"\s*\(.*?\)\s*", " ", s)
    return bo_dau(s)


def slug(ten: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", bo_dau(ten)).strip("-")


def khoa_goi(s: str) -> str:
    """Khoá gộp các cách viết CỦA CÙNG MỘT TÊN, và chỉ của cùng một tên.

    Giữ nguyên tiền tố chức danh — `BS Hằng` và `ĐD Hằng` là HAI NGƯỜI, gộp
    chúng lại là gán ca của bác sĩ cho điều dưỡng. Chỉ gộp thứ vốn là một:
    khoảng trắng thừa (`"Hải Yến "` ↔ `"Hải Yến"`), dấu chấm (`BS.` ↔ `BS`),
    và `BS SA` ↔ `BS` vì lịch viết cả hai cho cùng người.
    """
    t = bo_dau(s).replace(".", " ")
    t = re.sub(r"^bs\s+sa\s+", "bs ", t)
    return re.sub(r"\s+", " ", t).strip()


#: Ô không phải MỘT NHÂN SỰ của phòng khám. Ba loại, ba lý do khác nhau:
#:   • "(Nam khoa)" là chuyên khoa của bác sĩ ở ô trên, "HSS" là một đầu việc —
#:     ghi chú lọt vào ô tên.
#:   • "NGHỈ" là trạng thái, không phải người.
#:   • "Green Lab" LÀ một bên có thật, nhưng là ĐỐI TÁC ngoài phòng khám, không
#:     phải nhân sự — họ đã có tài khoản `doi-tac-pk`, và vị trí `T1_LAYMAU`
#:     khai `nhom_nghe = DOI_TAC` chính vì ô này.
#: Không lọc thì script đi tạo hồ sơ nhân sự cho cả bốn.
KHONG_PHAI_NGUOI = {"(nam khoa)", "hss", "nghi", "green lab"}


def doc_excel(duong_dan: str) -> tuple[list[dict[str, Any]], dict[str, Counter]]:
    """Trả (danh sách nhân sự, {tên gọi trong lịch: Counter(mã vị trí)})."""
    import openpyxl  # chỉ cần khi đọc .xlsx — máy chủ không có, và không cần

    wb = openpyxl.load_workbook(duong_dan, data_only=True)

    ds: list[dict[str, Any]] = []
    ws = wb["Điện thoại nhân sự"]
    nhom = None
    for r in range(2, ws.max_row + 1):
        a, b, c = (ws.cell(r, i).value for i in (1, 2, 3))
        if not a:
            continue
        t = str(a).strip()
        if t in NHOM_SANG_VAI:
            nhom = t
            continue
        if t.isupper():
            continue
        if nhom:
            ds.append(
                {
                    "ten_day_du": re.sub(r"^Dr\s+", "", t).strip(),
                    "sdt": str(b or "").strip(),
                    "email": str(c or "").strip().lower(),
                    "nhom": nhom,
                    "vai": NHOM_SANG_VAI[nhom],
                }
            )

    vi_tri: dict[str, Counter] = defaultdict(Counter)
    ws = wb["Xếp lịch làm việc"]
    dau = [
        r
        for r in range(1, ws.max_row + 1)
        if str(ws.cell(r, 1).value).strip() == "Tầng"
    ]
    for k, r0 in enumerate(dau):
        het = dau[k + 1] if k + 1 < len(dau) else ws.max_row
        phong = None
        for r in range(r0 + 3, het):
            if str(ws.cell(r, 1).value).strip() == "Tầng":
                break
            if ws.cell(r, 2).value:
                phong = str(ws.cell(r, 2).value).strip()
            o_vt = ws.cell(r, 3).value
            if not o_vt:
                continue
            # Tên vị trí trong Excel có ngoặc dài và xuống dòng; cắt ở dấu ngoặc.
            vt = str(o_vt).split("(")[0].strip()
            ma = O_SANG_MA.get((phong or "", vt))
            if not ma:
                continue
            for c in range(4, 15):
                o = ws.cell(r, c).value
                if not o:
                    continue
                # Một ô có thể chứa hai người: "Hồng Thơm, Hà Phạm", "Bs Nam + HSS".
                for t in re.split(r"[\n,+]+", str(o)):
                    t = t.strip()
                    if t and t.upper() != "NGHỈ":
                        vi_tri[t][ma] += 1
    # Gộp các cách viết của cùng một tên. Làm ở đây, TRƯỚC khi dò hồ sơ: để sót
    # thì một người ra hai dòng `khop`, và dòng sau ghi đè số ca của dòng trước
    # bằng con số nhỏ hơn — bảng vị trí nói sai mà không có lỗi nào để thấy.
    gop: dict[str, Counter] = defaultdict(Counter)
    ten_dep: dict[str, str] = {}
    for ten, dem in vi_tri.items():
        if bo_dau(ten) in KHONG_PHAI_NGUOI:
            continue
        k = khoa_goi(ten)
        gop[k].update(dem)
        # Giữ cách viết ĐẦY ĐỦ nhất làm tên hiển thị: "BS. Hoàng" thắng "BS Hoàng"
        # chỉ khi nó dài hơn, nên "Ngọc Giầu" thắng "Giầu".
        if len(ten.strip()) > len(ten_dep.get(k, "")):
            ten_dep[k] = ten.strip()
    vi_tri = {ten_dep[k]: v for k, v in gop.items()}
    return ds, vi_tri


#: Thứ trong Excel → số ngày tính từ Thứ Hai.
THU_SANG_LECH = {
    "thu hai": 0,
    "thu ba": 1,
    "thu tu": 2,
    "thu nam": 3,
    "thu sau": 4,
    "thu bay": 5,
    "chu nhat": 6,
}
CA_EXCEL = {"sang": "SANG", "chieu": "CHIEU", "toi": "TOI"}


def doc_o_lich(duong_dan: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Đọc lịch Excel THEO ĐÚNG HÌNH: (các ô có người, các ô đóng).

    BA THỨ bản đầu bỏ sót, và cả ba đều làm bảng khác file:

    1. Ô GỘP. Excel gộp dọc "Lễ tân + Thu ngân" (20 lần), "Xếp thuốc + Tạo đơn"
       (18), "Đo chỉ số + Lấy mẫu" (8), "Hỏi bệnh + Thư ký" (1). Chữ chỉ nằm ở ô
       trên cùng; đọc ô từng cái thì Thu ngân, Tạo đơn… trống trơn, và người đứng
       ô gộp "Hỏi bệnh + Thư ký" bị gán mỗi Hỏi bệnh — đúng lý do ma trận vai từ
       chối Thủy Tiên. Nay: ô gộp phủ những hàng nào thì người ấy đứng tất cả.
    2. Ô ĐEN (`FF000000`) = vị trí không làm ca ấy. Khác ô trống.
    3. Khối NGHỈ (`FF666666`, chữ "NGHỈ") = cả ca phòng khám nghỉ.

    Màu đọc bằng openpyxl ở chế độ CÓ định dạng — `data_only=True` vẫn giữ màu,
    nhưng ô gộp chỉ ô góc trên-trái mang màu và chữ, nên phải tự trải ra.
    """
    import openpyxl

    wb = openpyxl.load_workbook(duong_dan)
    ws = wb["Xếp lịch làm việc"]

    # Trải ô gộp: mọi ô trong vùng mang chữ + màu của ô góc trên-trái.
    goc: dict[tuple[int, int], tuple[int, int]] = {}
    for rg in ws.merged_cells.ranges:
        for r in range(rg.min_row, rg.max_row + 1):
            for c in range(rg.min_col, rg.max_col + 1):
                goc[(r, c)] = (rg.min_row, rg.min_col)

    def o(r: int, c: int) -> Any:
        return ws.cell(*goc.get((r, c), (r, c)))

    def mau(r: int, c: int) -> str:
        f = o(r, c).fill
        if f is None or f.fill_type is None or f.fgColor.type != "rgb":
            return ""
        return str(f.fgColor.rgb or "").upper()

    dau = [
        r
        for r in range(1, ws.max_row + 1)
        if str(ws.cell(r, 1).value).strip() == "Tầng"
    ]
    nguoi: list[dict[str, Any]] = []
    dong: list[dict[str, Any]] = []
    for k, r0 in enumerate(dau):
        thu_cot: dict[int, int] = {}
        for c in range(4, 15):
            v = o(r0, c).value
            if v is not None and bo_dau(str(v)) in THU_SANG_LECH:
                thu_cot[c] = THU_SANG_LECH[bo_dau(str(v))]
        ca_cot = {
            c: CA_EXCEL.get(bo_dau(str(o(r0 + 2, c).value or ""))) for c in range(4, 15)
        }
        het = dau[k + 1] if k + 1 < len(dau) else ws.max_row
        phong = None
        for r in range(r0 + 3, het):
            if str(ws.cell(r, 1).value).strip() == "Tầng":
                break
            if o(r, 2).value:
                phong = str(o(r, 2).value).strip()
            o_vt = ws.cell(r, 3).value
            if not o_vt:
                continue
            ten_vt = str(o_vt).split("(")[0].strip()
            # "Đo chỉ số" và "Lấy mẫu" không thuộc phòng nào trong Excel.
            ma = O_SANG_MA.get((phong or "", ten_vt)) or O_SANG_MA.get(
                ("Quầy tiếp đón", ten_vt)
            )
            if not ma:
                continue
            for c in range(4, 15):
                if c not in thu_cot or not ca_cot.get(c):
                    continue
                vi_tri = {
                    "tuan": k,
                    "lech_ngay": thu_cot[c],
                    "ca": ca_cot[c],
                    "ma": ma,
                }
                m = mau(r, c)
                gia_tri = o(r, c).value
                if m == "FF666666" or bo_dau(str(gia_tri or "")) == "nghi":
                    dong.append({**vi_tri, "ly_do": "NGHI"})
                    continue
                if m == "FF000000":
                    dong.append({**vi_tri, "ly_do": "DONG"})
                    continue
                if not gia_tri:
                    continue
                for t in re.split(r"[\n,+]+", str(gia_tri)):
                    t = t.strip()
                    if t and bo_dau(t) not in KHONG_PHAI_NGUOI:
                        nguoi.append({**vi_tri, "ten": t})
    return nguoi, dong


async def nap_lich(
    *,
    conn: asyncpg.Connection,
    clinic_id: str,
    o_lich: list[dict[str, Any]],
    o_dong: list[dict[str, Any]],
    do_db: Any,
    that: bool,
) -> int:
    """Dựng lại lịch Excel vào các tuần chỉ định, ĐI QUA API XẾP CA THẬT.

        python scripts/nhan-su-kim-nguu.py nhan-su.json \\
            --nap-lich 2026-09-07:2,2026-09-14:1,2026-09-21:2,2026-09-28:1 --that

    Mỗi cặp `ngày-thứ-hai:tuần-excel` (tuần Excel đếm từ 1). Khai tường minh thay
    vì đoán, vì cùng một file có thể đổ vào bất kỳ tuần nào.

    NGƯỜI: qua `POST /roster/shifts` — cửa ấy kiểm ma trận vai↔vị trí, nên nạp
    xong là biết ma trận có cho lưu thật không.
    Ô ĐEN / NGHỈ: ghi thẳng `vi_tri_dong_ca` (chưa có API cho bảng này).

    TÊN CHƯA RÕ → Ô TRỐNG (Tuyền chốt). `LICH_KHAM` KHÔNG đụng.
    Chạy lại được: bỏ qua ô đã có.
    """
    import datetime as dt

    cap: list[tuple[dt.date, int]] = []
    for manh in sys.argv[sys.argv.index("--nap-lich") + 1].split(","):
        ngay, _, tuan = manh.partition(":")
        d = dt.date.fromisoformat(ngay.strip())
        if d.weekday() != 0:
            print(f"✗ {d} không phải Thứ Hai. Dừng.")
            return 2
        cap.append((d, int(tuan or "1") - 1))

    dau_min = min(d for d, _ in cap)
    da_co = {
        (str(r["work_date"]), r["station"], r["shift"], r["staff_id"])
        for r in await conn.fetch(
            """
            SELECT work_date, station, shift, staff_id::text AS staff_id
              FROM work_roster
             WHERE clinic_id = $1::uuid
               AND work_date BETWEEN $2 AND $3
               AND status <> 'REJECTED'
            """,
            clinic_id,
            dau_min,
            max(d for d, _ in cap) + dt.timedelta(days=6),
        )
    }
    de_trong = {khoa_goi(t) for t in DE_TRONG}

    se_xep: list[dict[str, Any]] = []
    se_dong: list[tuple[dt.date, str, str, str]] = []
    trong: Counter = Counter()
    trung_lap = 0
    for tuan_dau, tuan_excel in cap:
        for o in o_dong:
            if int(o["tuan"]) != tuan_excel:
                continue
            ngay = tuan_dau + dt.timedelta(days=int(o["lech_ngay"]))
            se_dong.append((ngay, o["ca"], o["ma"], o["ly_do"]))
        for o in o_lich:
            if int(o["tuan"]) != tuan_excel:
                continue
            ngay = tuan_dau + dt.timedelta(days=int(o["lech_ngay"]))
            if khoa_goi(o["ten"]) in de_trong:
                trong[o["ten"].strip()] += 1
                continue
            ten = PHAN_XU.get(o["ten"], o["ten"])
            ai = list({h["staff_id"]: h for h in do_db(ten)}.values())
            if len(ai) != 1:
                trong[o["ten"].strip()] += 1
                continue
            khoa = (ngay.isoformat(), o["ma"], o["ca"], ai[0]["staff_id"])
            if khoa in da_co:
                trung_lap += 1
                continue
            da_co.add(khoa)
            se_xep.append(
                {
                    "work_date": ngay.isoformat(),
                    "station": o["ma"],
                    "shift": o["ca"],
                    "staff_id": ai[0]["staff_id"],
                }
            )

    print(
        "Tuần: " + ", ".join(f"{d} ← Excel tuần {t + 1}" for d, t in cap) + "\n"
        f"  sẽ xếp {len(se_xep)} ô · đã có sẵn {trung_lap} · "
        f"ĐỂ TRỐNG {sum(trong.values())} · ô đen/NGHỈ {len(se_dong)}"
    )
    if trong:
        print(
            "  Để trống vì chưa rõ là ai: "
            + ", ".join(f"{t} ({n})" for t, n in trong.most_common())
        )
    if not that:
        print("\nĐây là THỬ KHÔ. Thêm --that để xếp thật.")
        return 0

    # ── Ô đen / NGHỈ ──
    dong_moi = 0
    for ngay, ca, ma, ly_do in se_dong:
        ket = await conn.execute(
            """
            INSERT INTO vi_tri_dong_ca (clinic_id, work_date, shift, station, ly_do)
            VALUES ($1::uuid, $2, $3, $4, $5)
            ON CONFLICT (clinic_id, work_date, shift, station) DO NOTHING
            """,
            clinic_id,
            ngay,
            ca,
            ma,
            ly_do,
        )
        dong_moi += int(ket.split()[-1])

    # ── Người, qua API ──
    sb = os.environ["SUPABASE_URL"].rstrip("/")
    anon = os.environ["SUPABASE_ANON_KEY"]
    api = os.environ.get("CLINIC_API_URL", "http://127.0.0.1:8000").rstrip("/")
    async with httpx.AsyncClient(timeout=30.0) as http:
        r = await http.post(
            f"{sb}/auth/v1/token?grant_type=password",
            headers={"apikey": anon, "Content-Type": "application/json"},
            json={
                "email": os.environ.get("TK_QUAN_LY", "quanlyhethong@dr4women.vn"),
                "password": os.environ.get("MK_QUAN_LY", MAT_KHAU),
            },
        )
        if r.status_code != 200:
            print(f"✗ Không đăng nhập được tài khoản quản lý: {r.status_code}")
            return 1
        h = {
            "Authorization": f"Bearer {r.json()['access_token']}",
            "X-API-Key": os.environ["BACKEND_API_KEY"],
        }
        ok = 0
        loi: Counter = Counter()
        for x in se_xep:
            rr = await http.post(f"{api}/api/v1/roster/shifts", headers=h, json=x)
            if rr.status_code in (200, 201):
                ok += 1
            else:
                loi[f"{rr.status_code} {rr.text[:110]}"] += 1
    print(f"\nĐã xếp {ok}/{len(se_xep)} ô người · thêm {dong_moi} ô đen/NGHỈ.")
    for thong_bao, so in loi.most_common():
        print(f"  ✗ {so}× {thong_bao}")
    return 0 if not loi else 1


async def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    duong_dan = sys.argv[1]
    that = "--that" in sys.argv

    o_lich: list[dict[str, Any]] = []
    o_dong: list[dict[str, Any]] = []
    if duong_dan.endswith(".json"):
        goi = json.loads(pathlib.Path(duong_dan).read_text())
        ds = goi["nhan_su"]
        vi_tri = {k: Counter(v) for k, v in goi["vi_tri"].items()}
        o_lich = goi.get("o_lich", [])
        o_dong = goi.get("o_dong", [])
    else:
        ds, vi_tri = doc_excel(duong_dan)
        o_lich, o_dong = doc_o_lich(duong_dan)

    if "--xuat" in sys.argv:
        ra = pathlib.Path(sys.argv[sys.argv.index("--xuat") + 1])
        ra.write_text(
            json.dumps(
                {
                    "nhan_su": ds,
                    "vi_tri": {k: dict(v) for k, v in vi_tri.items()},
                    "o_lich": o_lich,
                    "o_dong": o_dong,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print(
            f"Đã ghi {ra} — {len(ds)} nhân sự · {len(vi_tri)} tên gọi · "
            f"{len(o_lich)} ô có người · {len(o_dong)} ô đóng."
        )
        return 0

    print(f"Nguồn: {len(ds)} nhân sự · {len(vi_tri)} tên gọi xuất hiện trong lịch\n")

    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        clinic_id = await conn.fetchval("SELECT id FROM clinic LIMIT 1")
        co_so = await conn.fetchval(
            "SELECT id FROM clinic_location WHERE clinic_id = $1::uuid AND name = $2",
            clinic_id,
            TEN_CO_SO,
        )
        if co_so is None:
            print(f"✗ Không có cơ sở tên {TEN_CO_SO!r}. Dừng.")
            return 2

        hien_co = await conn.fetch(
            """
            SELECT s.id::text AS staff_id, s.full_name, s.short_name, m.role
              FROM clinic_membership m
              JOIN staff s ON s.id = m.staff_id
             WHERE m.clinic_id = $1::uuid AND m.is_active AND s.is_active
            """,
            clinic_id,
        )

        # SO THEO TẬP CHỮ TRONG TÊN, không so chuỗi.
        #
        # Người xếp lịch viết tên theo thứ tự nào tiện: "Phạm Hà" và "Hà Phạm"
        # và "Phạm Thị Hà" là MỘT người; "Trang Lê" và "Huyền Trang" cũng vậy
        # (Lê Huyền Trang). So chuỗi thì ba cách viết ra ba người, và phòng
        # khám có ba hồ sơ cho một điều dưỡng.
        #
        # Luật: tập chữ của tên gọi phải là TẬP CON của tập chữ tên đầy đủ.
        # "ha pham" ⊂ {pham, thi, ha} ✓ · "huyen trang" ⊂ {le, huyen, trang} ✓
        # "van anh" ⊂ {nguyen, van, anh} ✓ — và cũng ⊂ {vu, hoang, van, anh},
        # nên nó ra HAI người và rơi vào nhóm mơ hồ, đúng như phải thế.
        def chu(s: str) -> frozenset[str]:
            return frozenset(goi_gon(s).split())

        def trung(a: frozenset[str], b: frozenset[str]) -> bool:
            """Hai cách viết CÓ THỂ là một người không.

            MỘT CHỮ TRÙNG KHÔNG PHẢI BẰNG CHỨNG. Bản trước chỉ đòi tập con, nên
            {thành} ⊂ {thanh, huyền} và điều dưỡng **Thanh Huyền** bị gán thành
            **BS Thành** — tám ca đo chỉ số và lấy máu chui vào hồ sơ của người
            gánh 27 ca khám. Một dòng sai đủ để đọc sai cả tải của phòng khám.

            Nên: bằng nhau thì nhận; là tập con thì phải có ÍT NHẤT HAI chữ.
            """
            if not a or not b:
                return False
            if a == b:
                return True
            nho, lon = (a, b) if len(a) < len(b) else (b, a)
            return len(nho) >= 2 and nho <= lon

        # NHÓM NGHỀ LÀ MỘT PHẦN CỦA DANH TÍNH, không phải thuộc tính phụ.
        #
        # Luật "tập chữ, ít nhất hai chữ" vẫn để lọt hai ca thật, và cả hai đều
        # là CSKH bị kéo sang thành điều dưỡng:
        #
        #   {phương, thuý} ⊂ {đỗ, thuý, phương, anh}
        #       → CSKH Phương Thúy Nguyễn thành điều dưỡng Đỗ Thuý Phương Anh
        #   bỏ dấu thì "Giàu" = "Giầu"
        #       → CSKH Nguyễn Thị Ngọc Giàu thành điều dưỡng Nguyễn Thị Ngọc Giầu
        #
        # Hai người ấy nhận luôn ca trực của người khác. Danh sách nhân sự Kim
        # Ngưu chỉ có BÁC SĨ và ĐIỀU DƯỠNG — không có CSKH, không có quản lý —
        # nên một tên trong lịch không bao giờ được trỏ vào hồ sơ CSKH hay quản
        # lý, dù chữ có trùng đến đâu.
        vai_dieu_duong = {
            "NURSE_ULTRASOUND",
            "RECEPTION",
            "TKYK",
            "CASHIER",
            "CASHIER_THUOC",
            "CASHIER_DV",
            "PHARMACIST",
            "TRUONG_CA",
        }
        vai_bac_si = {"DOCTOR", "ULTRASOUND_DOCTOR"}

        def hop_nhom(ten_lich: str, vai_db: str) -> bool:
            la_bac_si = bool(re.match(r"^\s*(bs|dr)\b", ten_lich.strip(), flags=re.I))
            return vai_db in (vai_bac_si if la_bac_si else vai_dieu_duong)

        db_chu = [(chu(r["full_name"]), dict(r)) for r in hien_co]
        ex_chu = [(chu(n["ten_day_du"]), n) for n in ds]

        def do_db(ten: str) -> list[dict[str, Any]]:
            c = chu(ten)
            return [h for k, h in db_chu if trung(c, k) and hop_nhom(ten, h["role"])]

        def do_excel(ten: str) -> list[dict[str, Any]]:
            c = chu(ten)
            return [n for k, n in ex_chu if trung(c, k)]

        if "--nap-lich" in sys.argv:
            return await nap_lich(
                conn=conn,
                clinic_id=str(clinic_id),
                o_lich=o_lich,
                o_dong=o_dong,
                do_db=do_db,
                that=that,
            )

        khop: list[tuple[str, dict[str, Any], Counter]] = []
        mo_ho: list[tuple[str, int, list[str]]] = []
        chua_co: list[tuple[str, Counter]] = []
        for ten_lich, dem in sorted(vi_tri.items(), key=lambda x: -sum(x[1].values())):
            ten_tra = PHAN_XU.get(ten_lich, ten_lich)
            ho_so = do_db(ten_tra)
            # Cùng một hồ sơ dò ra nhiều lần thì vẫn là một người.
            ho_so = list({h["staff_id"]: h for h in ho_so}.values())
            if len(ho_so) > 1:
                mo_ho.append(
                    (ten_lich, sum(dem.values()), [h["full_name"] for h in ho_so])
                )
                continue
            if len(ho_so) == 1:
                khop.append((ten_lich, ho_so[0], dem))
                continue
            chua_co.append((ten_lich, dem))

        # HAI TÊN GỌI CÙNG TRỎ VỀ MỘT NGƯỜI. Xảy ra khi lịch viết "Trang Lê" chỗ
        # này và "Huyền Trang" chỗ kia. Gộp số ca lại, giữ cách viết nhiều ca
        # hơn, và NÓI RA — vì đây là suy đoán, dù là suy đoán có căn cứ.
        gop_nguoi: dict[str, list[tuple[str, Counter]]] = defaultdict(list)
        for ten_lich, h, dem in khop:
            gop_nguoi[h["staff_id"]].append((ten_lich, dem))
        da_gop: list[tuple[str, list[str]]] = []
        khop_gon: list[tuple[str, dict[str, Any], Counter]] = []
        theo_id = {h["staff_id"]: h for _, h, _ in khop}
        for sid, cac in gop_nguoi.items():
            tong: Counter = Counter()
            for _, dem in cac:
                tong.update(dem)
            chinh = max(cac, key=lambda x: sum(x[1].values()))[0]
            if len(cac) > 1:
                da_gop.append((theo_id[sid]["full_name"], [t for t, _ in cac]))
            khop_gon.append((chinh, theo_id[sid], tong))
        khop = sorted(khop_gon, key=lambda x: -sum(x[2].values()))

        print(f"── KHỚP {len(khop)} người ──")
        for ten_lich, h, dem in khop:
            vts = " · ".join(f"{m}×{c}" for m, c in dem.most_common(4))
            print(f"  {ten_lich:<18} → {h['full_name']:<22} {h['role']:<18} {vts}")

        if mo_ho:
            print(
                f"\n⚠ MƠ HỒ {len(mo_ho)} tên — BỎ QUA, "
                "cần Tuyền chốt rồi khai vào PHAN_XU:"
            )
            for ten_lich, so_ca, ai in mo_ho:
                print(f"    {ten_lich!r} ({so_ca} ca) ← {' / '.join(ai)}")

        if da_gop:
            print(f"\n≡ HAI CÁCH VIẾT, MỘT NGƯỜI — đã gộp ({len(da_gop)}):")
            for ten, cac in da_gop:
                print(f"    {ten:<24} ← {' + '.join(cac)}")

        if chua_co:
            print(f"\n+ CHƯA CÓ HỒ SƠ {len(chua_co)} tên:")
            for ten_lich, dem in chua_co:
                trong_excel = do_excel(ten_lich)
                nguon = (
                    trong_excel[0]["ten_day_du"]
                    if trong_excel
                    else "— không có trong danh sách nhân sự —"
                )
                print(f"    {ten_lich:<18} {sum(dem.values()):>2} ca · {nguon}")

        if not that:
            print("\nĐây là THỬ KHÔ. Thêm --that để làm thật.")
            return 0

        # ── Làm thật ────────────────────────────────────────────────────────
        so_vt = so_ten = 0
        async with httpx.AsyncClient(timeout=30.0) as http:
            base = os.environ["SUPABASE_URL"].rstrip("/")
            key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

            for ten_lich, h, dem in khop:
                chinh = dem.most_common(1)[0][0]
                for ma, so_ca in dem.items():
                    await conn.execute(
                        """
                        INSERT INTO staff_vi_tri
                            (clinic_id, staff_id, vi_tri_code, la_chinh, so_ca_mau)
                        VALUES ($1::uuid, $2::uuid, $3, $4, $5)
                        ON CONFLICT (clinic_id, staff_id, vi_tri_code)
                        DO UPDATE SET la_chinh = EXCLUDED.la_chinh,
                                      so_ca_mau = EXCLUDED.so_ca_mau
                        """,
                        clinic_id,
                        h["staff_id"],
                        ma,
                        ma == chinh,
                        so_ca,
                    )
                    so_vt += 1

                # Tên đầy đủ + số điện thoại, nếu danh sách có. Tên gọi cũ giữ
                # lại ở `short_name`: bảng xếp lịch và màn TV đang hiện tên ấy,
                # và người trong phòng khám gọi nhau bằng tên ấy.
                trong_excel = do_excel(ten_lich)
                if len(trong_excel) == 1:
                    n = trong_excel[0]
                    await conn.execute(
                        """
                        UPDATE staff
                           SET full_name = $1,
                               short_name = coalesce(short_name, $2),
                               phone = coalesce(nullif($3, ''), phone),
                               email = coalesce(nullif($4, ''), email),
                               primary_location_id = $5::uuid
                         WHERE id = $6::uuid
                        """,
                        n["ten_day_du"],
                        h["full_name"],
                        n["sdt"],
                        n["email"],
                        co_so,
                        h["staff_id"],
                    )
                    so_ten += 1
                else:
                    await conn.execute(
                        "UPDATE staff SET primary_location_id = $1::uuid "
                        "WHERE id = $2::uuid",
                        co_so,
                        h["staff_id"],
                    )

            # Người có trong Excel mà chưa có hồ sơ nào.
            them = 0
            for ten_lich, dem in chua_co:
                trong_excel = do_excel(ten_lich)
                if len(trong_excel) != 1:
                    continue  # không có trong danh sách nhân sự → không đoán vai
                n = trong_excel[0]
                # CHỐT CUỐI: tên đầy đủ có trỏ về một hồ sơ ĐÃ CÓ không?
                #
                # Lịch ghi "Trang Lê" chỗ này và "Huyền Trang" chỗ kia. Cách viết
                # đầu khớp hồ sơ `ĐD Trang Lê`; cách viết sau không khớp gì, nên
                # rơi xuống đây — và nếu cứ thế tạo thì phòng khám có hai hồ sơ
                # cho một điều dưỡng, hai dòng trong mọi ô chọn người, KPI chia
                # đôi. Dò lại bằng TÊN ĐẦY ĐỦ trước khi tạo.
                da_co = do_db(n["ten_day_du"])
                if da_co:
                    ten_cu = " / ".join(h["full_name"] for h in da_co)
                    print(
                        f"  ≡ {ten_lich:<16} {n['ten_day_du']} trùng hồ sơ đã có "
                        f"({ten_cu}) — KHÔNG tạo, cần Tuyền xác nhận"
                    )
                    continue
                tk = slug(n["ten_day_du"])
                email = f"{tk}@{TEN_MIEN}"
                r = await http.post(
                    f"{base}/auth/v1/admin/users",
                    headers={"apikey": key, "Authorization": f"Bearer {key}"},
                    json={"email": email, "password": MAT_KHAU, "email_confirm": True},
                )
                if r.status_code not in (200, 201):
                    tra = await http.get(
                        f"{base}/auth/v1/admin/users",
                        headers={"apikey": key, "Authorization": f"Bearer {key}"},
                        params={"filter": email},
                    )
                    ok = tra.status_code == 200
                    users = (tra.json() or {}).get("users", []) if ok else []
                    uid = next(
                        (u["id"] for u in users if u.get("email") == email), None
                    )
                    if uid is None:
                        print(f"  ✗ {email}: {r.status_code} {r.text[:100]}")
                        continue
                else:
                    uid = r.json()["id"]

                async with conn.transaction():
                    staff_id = await conn.fetchval(
                        """
                        INSERT INTO staff
                            (full_name, short_name, is_active, auth_user_id,
                             primary_department, primary_location_id, phone, email)
                        VALUES ($1, $2, TRUE, $3::uuid, $4, $5::uuid,
                                nullif($6, ''), nullif($7, ''))
                        RETURNING id::text
                        """,
                        n["ten_day_du"],
                        ten_lich,
                        uid,
                        n["vai"],
                        co_so,
                        n["sdt"],
                        n["email"],
                    )
                    await conn.execute(
                        """
                        INSERT INTO clinic_membership
                            (clinic_id, staff_id, role, is_active)
                        VALUES ($1::uuid, $2::uuid, $3, TRUE)
                        ON CONFLICT (clinic_id, staff_id, role)
                        DO UPDATE SET is_active = TRUE
                        """,
                        clinic_id,
                        staff_id,
                        n["vai"],
                    )
                    # Có tên mà không có quyền là người ngồi nhìn màn trắng: cấp preset
                    # theo vai ngay trong cùng giao dịch (migration 20260923000016).
                    await conn.fetch(
                        "SELECT public.cap_quyen_theo_preset($1::uuid, $2::uuid, $3)",
                        clinic_id,
                        staff_id,
                        n["vai"],
                    )
                    chinh = dem.most_common(1)[0][0]
                    for ma, so_ca in dem.items():
                        await conn.execute(
                            """
                            INSERT INTO staff_vi_tri
                                (clinic_id, staff_id, vi_tri_code, la_chinh, so_ca_mau)
                            VALUES ($1::uuid, $2::uuid, $3, $4, $5)
                            ON CONFLICT (clinic_id, staff_id, vi_tri_code) DO NOTHING
                            """,
                            clinic_id,
                            staff_id,
                            ma,
                            ma == chinh,
                            so_ca,
                        )
                them += 1
                print(f"  ✓ thêm {n['vai']:<18} {n['ten_day_du']:<24} {email}")

        # Mật khẩu GoTrue → app_credential (20261006420000); quên thì su-kien
        # cũng chép trong vòng một phút.
        db = await conn.fetchrow("SELECT * FROM public.dong_bo_app_credential()")
        print(f"app_credential: thêm {db['them']}, sửa {db['sua']}")
        print(
            f"\nXong. {so_vt} dòng vị trí · {so_ten} hồ sơ đổi sang tên đầy đủ · "
            f"{them} người mới · tất cả về cơ sở {TEN_CO_SO}."
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
