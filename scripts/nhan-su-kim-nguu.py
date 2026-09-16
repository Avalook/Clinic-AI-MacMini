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


async def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    duong_dan = sys.argv[1]
    that = "--that" in sys.argv

    if duong_dan.endswith(".json"):
        goi = json.loads(pathlib.Path(duong_dan).read_text())
        ds = goi["nhan_su"]
        vi_tri = {k: Counter(v) for k, v in goi["vi_tri"].items()}
    else:
        ds, vi_tri = doc_excel(duong_dan)

    if "--xuat" in sys.argv:
        ra = pathlib.Path(sys.argv[sys.argv.index("--xuat") + 1])
        ra.write_text(
            json.dumps(
                {"nhan_su": ds, "vi_tri": {k: dict(v) for k, v in vi_tri.items()}},
                ensure_ascii=False,
                indent=2,
            )
        )
        print(f"Đã ghi {ra} — {len(ds)} nhân sự · {len(vi_tri)} tên gọi.")
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

        print(
            f"\nXong. {so_vt} dòng vị trí · {so_ten} hồ sơ đổi sang tên đầy đủ · "
            f"{them} người mới · tất cả về cơ sở {TEN_CO_SO}."
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
