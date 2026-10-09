#!/usr/bin/env python3
"""Dựng 17 mẫu kết quả v3 theo PDF gốc (Tuyền 26/09/2026 — lát 3 bản giao diện mẫu).

Nguồn: `data.js` của bản giao diện mẫu Tuyền đã duyệt
(`~/Downloads/Dr4women-giao-dien-mau/data.js`, sinh từ 17 PDF phòng khám bằng
`_sinh-du-lieu/build_data.py`). Script ghi:

* `src/clinicai/phieu_kham/mau_ket_qua_v3.json` — khung từng mẫu (đọc lại được);
* `supabase/migrations/<ten>.sql` — xuất bản v(n+1) + gắn mẫu vào dịch vụ.

LƯU THEO `ma`, KHÔNG theo vị trí như bản mẫu (`gt["mid|mi.ti.ci"]`): mỗi ô có
`ma` ổn định; mục dạng BẢNG (Thai A | Thai B, trái | phải) khai `cot: [{ma, ten}]`
và giá trị một ô là `{ma_cot: giá trị}`.

An toàn lâm sàng (giữ luật bản v2): SỐ ĐO (ô có đơn vị), âm/dương và mẫu xét
nghiệm gửi ngoài KHÔNG điền sẵn; chỉ câu mô tả bình thường có `mac_dinh`.

Chạy:  python3 scripts/phieu-kham/dung-mau-ket-qua-v3.py [đường/dẫn/data.js]
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NGUON = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    Path.home() / "Downloads/Dr4women-giao-dien-mau/data.js"
)
#: Nguồn sự thật đã gộp — mã phòng khám (KiotViet) của từng PDF mẫu.
NGUON_SU_THAT = Path(sys.argv[2]) if len(sys.argv) > 2 else (
    Path.home() / "Downloads/Dr4women-nguon-su-that.html"
)
MIGRATION = "20260926000004_mau_ket_qua_v3.sql"

#: Mẫu bản mẫu → mã mẫu đang có trong hệ thống (`ket_qua_mau.ma`, form `KQ_<ma>`).
GHEP = {
    "SA-THAI-SOM": "SA_THAI_SOM",
    "SA-THAI-Q1": "SA_THAI_QUY_1",
    "SA-THAI-Q23": "SA_THAI_QUY_23",
    "SA-SONG-Q1": "SA_SONG_THAI_QUY_1",
    "SA-SONG-Q23": "SA_SONG_THAI_QUY_23",
    "SA-TC-BT": "SA_TC_BT",
    "SA-TC-PP": "SA_TC_PP",
    "SA-VU": "SA_VU",
    "SA-GIAP": "SA_GIAP",
    "SA-O-BUNG": "SA_OBUNG",
    "SA-TINH-HOAN": "SA_TINH_HOAN",
    "SA-DM-CANH": "SA_MACH_CANH",
    "SA-DM-THAN": "SA_MACH_THAN",
    "SA-AM-VAT": "SA_DOPPLER_AM_VAT",
    "SOI-AM-HO": "SOI_AM_HO",
    "XN-HPV": "XN_HPV",
    "XN-PCR13": "XN_PCR_STDS",
}

AM_DUONG = ["Âm tính", "Dương tính"]
#: `goi_y` là ĐƠN VỊ THUẦN → ô mang thêm `don_vi` (bản in "89.6 mm"); cùng
#: danh sách với migration 20261009300000_o_tuy_chon_don_vi.sql.
DON_VI_THUAN = {
    "mm", "cm", "cm/s", "chu kỳ/phút", "lần/phút", "điểm", "%", "ml", "gram", "grams"
}  # fmt: skip

#: Tên mục CHỖ GIỮ của bản mẫu (PDF không có tiêu đề mục) → tên hiện cho người
#: dùng. Chỉ đổi TÊN; `ma` vẫn sinh từ tên gốc ("o") nên dữ liệu đã điền giữ
#: nguyên. 27/09/2026 (đợt 3 — B6b): "(không có tiêu đề mục)" hiện nguyên văn ở
#: phiếu kết quả / bản in; xuất bản lại bằng migration 20260928000002.
TEN_MUC_THAY: dict[tuple[str, str], str] = {
    ("SOI-AM-HO", "(không có tiêu đề mục)"): "Kết quả soi",
}


def slug(s: str) -> str:
    s = s.split("—")[0]  # "Chiều dài đầu mông — Crown-rump…" → phần tiếng Việt
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    s = s.encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\([^)]*\)", " ", s)  # bỏ phần tiếng Anh trong ngoặc
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:40].strip("_") or "o"


def dung_khung(m: dict, mid: str = "") -> list[dict]:
    doi_tac = m.get("loai") == "doi_tac"
    # Mã MỤC và mã Ô đếm trùng RIÊNG (như v2: mục "ket_luan" chứa ô "ket_luan");
    # mã ô phải duy nhất trong cả phiếu vì `du_lieu` phẳng theo mã ô.
    muc_dung: set[str] = set()
    o_dung: set[str] = set()

    def duy_nhat(goc: str, da: set[str]) -> str:
        ma, i = goc, 2
        while ma in da:
            ma = f"{goc}_{i}"
            i += 1
        da.add(ma)
        return ma

    def ma_duy_nhat(goc: str) -> str:
        return duy_nhat(goc, o_dung)

    khung = []
    for muc in m["muc"]:
        ten_muc = muc["ten"]
        ma_muc = "ket_luan" if slug(ten_muc) == "ket_luan" else slug(ten_muc)
        muc_ra: dict = {
            "ma": duy_nhat(ma_muc, muc_dung),
            "ten": TEN_MUC_THAY.get((mid, ten_muc), ten_muc),
            "block": [],
        }
        if muc.get("cot"):
            muc_ra["cot"] = [{"ma": slug(c), "ten": c} for c in muc["cot"]]
        for t in muc["truong"]:
            ten = t["ten"].lstrip("*").strip()
            goc = "ket_luan" if slug(ten) == "ket_luan" else slug(ten)
            o: dict = {"ma": ma_duy_nhat(goc), "ten": ten}
            if t["kieu"] == "vb":
                o["kieu"] = "doan_van"
            elif t["kieu"] == "am_duong":
                o["kieu"] = "chon"
                o["chon"] = AM_DUONG
            else:
                o["kieu"] = "text"
            dvi = (t.get("dvi") or "").strip()
            if dvi:
                o["goi_y"] = dvi
            if dvi in DON_VI_THUAN and o["kieu"] == "text":
                o["don_vi"] = dvi
            mac = (t.get("mac") or "").strip()
            if mac and not dvi and not doi_tac and t["kieu"] != "am_duong":
                # Ô bảng: câu bình thường điền sẵn CHO MỖI CỘT ({trai: …, phai: …})
                # — như bản v2; số đo (có đơn vị) vẫn không điền sẵn.
                o["mac_dinh"] = (
                    {c["ma"]: mac for c in muc_ra["cot"]} if muc.get("cot") else mac
                )
            muc_ra["block"].append(o)
        khung.append(muc_ra)
    # Mục cuối "Đề nghị" như bản v2 — phòng dịch vụ dặn thêm.
    if not any(mm["ma"] == "de_nghi" for mm in khung):
        khung.append(
            {
                "ma": duy_nhat("de_nghi", muc_dung),
                "ten": "Đề nghị",
                "block": [
                    {
                        "ma": ma_duy_nhat("de_nghi"),
                        "ten": "Đề nghị / lời dặn",
                        "kieu": "doan_van",
                        "tuy_chon": True,
                    }
                ],
            }
        )
    return khung


def main() -> None:
    src = NGUON.read_text(encoding="utf-8")
    d = json.loads(src[src.index("{") : src.rstrip().rstrip(";").rindex("}") + 1])
    mau = d["MAU"]
    ht = NGUON_SU_THAT.read_text(encoding="utf-8")
    nst = json.loads(re.search(r'<script id="du-lieu"[^>]*>(.*?)</script>', ht, re.S).group(1))
    kv_theo_mau = {x["id"]: x.get("kv") or [] for x in nst["mau_ket_qua"]}
    ra: dict = {}
    for mid, ma in GHEP.items():
        m = mau[mid]
        ra[ma] = {
            "ten": m["ten"],
            "nguon_pdf": m.get("file"),
            "kv": kv_theo_mau.get(mid) or m.get("kv") or [],
            "khung": dung_khung(m, mid),
        }
    # Mẫu KHÔNG đến từ data.js (SA_THAI_QUY_3 — PDF riêng, migration
    # 20261009310000) giữ nguyên từ JSON đang có, không mất khi dựng lại.
    cu = json.loads(
        (REPO / "src/clinicai/phieu_kham/mau_ket_qua_v3.json").read_text("utf-8")
    )["mau"]
    ra.update({k: v for k, v in cu.items() if k not in ra})
    (REPO / "src/clinicai/phieu_kham/mau_ket_qua_v3.json").write_text(
        json.dumps({"mau": ra}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    L = [
        "-- 17 MẪU KẾT QUẢ v3 THEO PDF GỐC (Tuyền 26/09/2026 — lát 3 bản giao diện mẫu).",
        "-- Nguồn: bản giao diện mẫu Tuyền duyệt (dựng từ 17 PDF phòng khám). Sinh bằng",
        "-- scripts/phieu-kham/dung-mau-ket-qua-v3.py → src/clinicai/phieu_kham/",
        "-- mau_ket_qua_v3.json (cùng dữ liệu). Mẫu dựng theo chi-dinh.html (Gemini)",
        "-- như BI-RADS/TIRADS KHÔNG còn trong v3; XN_TONG_QUAT (không có PDF) giữ nguyên.",
        "--",
        "-- Lưu theo `ma`. Mục dạng BẢNG khai `cot` — giá trị ô là {ma_cột: giá trị}.",
        "-- Số đo, âm/dương, xét nghiệm gửi ngoài KHÔNG điền sẵn (an toàn lâm sàng).",
        "--",
        "-- Chỉ thay bản do HỆ THỐNG xuất bản (xuat_ban_boi NULL): phòng khám đã tự xuất",
        "-- bản thì không đè. Bản cũ → RETIRED; phiếu đã điền ghim bản cũ vẫn đọc đúng.",
        "-- Sau đó GẮN mẫu vào dịch vụ theo mã phòng khám (KiotViet) của PDF — bảng gắn",
        "-- trước giờ rỗng (chờ người duyệt); Tuyền duyệt 26/09: theo nguồn chuẩn.",
        "-- Chạy lại được.",
        "",
    ]
    for ma, m in ra.items():
        fid = f"KQ_{ma}"
        khung = json.dumps(m["khung"], ensure_ascii=False)
        ten = m["ten"].replace("'", "''")
        L.append(f"""WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = '{fid}' AND d.trang_thai = 'PUBLISHED' AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung${khung}$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = '{fid}'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, '{fid}',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = '{fid}'),
       '{ten}', cu.nhom, $khung${khung}$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;
""")
    gan = [(ma, kv) for ma, m in ra.items() for kv in m["kv"]]
    vals = ",\n  ".join(f"('{ma}', '{kv}')" for ma, kv in gan)
    L.append(f"""-- Gắn mẫu ↔ dịch vụ theo mã phòng khám. Dịch vụ đã có mẫu gắn tay thì vẫn thêm
-- (nhiều mẫu cho một dịch vụ là chuyện thường: SA TC-BT / TC-PP, combo siêu âm).
-- HÀM để seed.sql gọi lại: trên DB dựng mới migration chạy TRƯỚC khi dịch vụ có mã
-- phòng khám (chuan_hoa_danh_muc_dich_vu_kiotviet chạy trong seed).
CREATE OR REPLACE FUNCTION public.gan_mau_ket_qua_theo_kiotviet()
RETURNS integer
LANGUAGE plpgsql
SET search_path = public
AS $fn$
DECLARE n integer;
BEGIN
  INSERT INTO public.dich_vu_mau_ket_qua (clinic_id, service_code, mau)
  SELECT p.clinic_id, p.service_code, g.mau
    FROM (VALUES
    {vals}
    ) AS g(mau, ma_kv)
    JOIN public.service_price p
      ON p.ma_kiotviet = g.ma_kv AND p."group" = 'dich_vu'
    JOIN public.ket_qua_mau k ON k.clinic_id = p.clinic_id AND k.ma = g.mau
  ON CONFLICT DO NOTHING;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END;
$fn$;

SELECT public.gan_mau_ket_qua_theo_kiotviet();
""")
    # Migration đã áp thì KHÔNG sửa (luật: lược đồ/dữ liệu chỉ qua migration MỚI).
    # Khung đổi sau ngày ấy → viết migration mới theo cùng khuôn (vd 20260928000002).
    dich = REPO / "supabase/migrations" / MIGRATION
    if dich.exists():
        print(f"Giữ nguyên {MIGRATION} (đã áp) — chỉ ghi mau_ket_qua_v3.json.")
    else:
        dich.write_text("\n".join(L), encoding="utf-8")
    so_bang = sum(1 for m in ra.values() for mm in m["khung"] if mm.get("cot"))
    so_o = sum(len(mm["block"]) for m in ra.values() for mm in m["khung"])
    print(f"{len(ra)} mẫu · {so_o} ô · {so_bang} mục bảng · {len(gan)} cặp gắn")


if __name__ == "__main__":
    main()
