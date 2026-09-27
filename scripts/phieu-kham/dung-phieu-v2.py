#!/usr/bin/env python3
"""Phiếu khám v2 — thu gọn tiền sử, dị ứng thuốc Có/Không, bảng CLS gập.

Góp ý phòng khám (nick bác sĩ chính + thư ký y khoa, đợt 3 — 27/09/2026):

  B1  Tiền sử: thay vì hiện tất cả thì list các lựa chọn → chọn → mới hiện ô điền.
  B2  Dị ứng thuốc: hai lựa chọn Có/Không; chọn Có mới hiện "Chi tiết".
  B3  Cận lâm sàng gần đây: tương tự — bảng gõ tay nằm trong ngăn gập, mặc định
      đóng, tự mở khi đã có ô điền.

ĐẦU VÀO LUÔN LÀ v1 ĐÃ XUẤT BẢN (migration 20260924000008 — không bao giờ sửa),
nên chạy lại bao nhiêu lần cũng ra cùng một v2. Ghi:

* `src/clinicai/phieu_kham/dinh_nghia/<form>.json` — khung v2 (máy chủ + test đọc);
* `supabase/migrations/<MIGRATION>` — xuất bản v2 cho mọi phòng khám.

GIỮ NGUYÊN MỌI `ma` của v1 (test `test_phieu_kham_v2.py` canh). Chỉ THÊM:
ô chọn `<tiền tố>_allergy_co` (Có/Không) cho NT · HMVS · SK, và cặp
`pk_allergy_co`/`pk_allergy`, `nk_allergy_co`/`nk_allergy` cho PK · NK (phiếu
nguồn không có ô dị ứng). Ô thêm mang `them_sau_nguon` để bộ đếm khoá nguồn
vẫn đếm đúng nguồn.

Trích lại từ HTML nguồn (`trich-tu-html.py`) ra v1 — chạy script này ngay sau.

Chạy:  .venv/bin/python scripts/phieu-kham/dung-phieu-v2.py
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from clinicai.phieu_kham.khung import kiem_dinh_nghia  # noqa: E402

V1 = REPO / "supabase/migrations/20260924000008_phieu_kham_luot.sql"
MIGRATION = "20260928000020_phieu_kham_v2_gon.sql"
DICH = REPO / "src/clinicai/phieu_kham/dinh_nghia"

LY_DO_THEM = "27/09/2026 — góp ý phòng khám: dị ứng thuốc Có/Không"

#: B1 — nhóm tiền sử TOÀN ô gõ tay → mọi ô `thu_gon`.
THU_GON: dict[str, list[str]] = {
    "NT": ["2. Tiền sử phụ khoa và sản khoa"],
    "HMVS": ["2. Tiền sử Phụ khoa, Sản khoa (vợ)", "3. Tiền sử Sản khoa (chồng)"],
    "PK": ["Tiền sử bệnh", "Tiền sử phụ khoa"],
    "SK": ["Tiền sử"],
    "NK": ["Tiền sử nam khoa / sinh dục – tiết niệu"],
}

#: B3 — bảng kết quả CLS gõ tay (mục B) → ngăn gập.
GAP: dict[str, list[str]] = {
    "NT": ["6. Cận lâm sàng"],
    "HMVS": ["10. Cận lâm sàng"],
    "PK": ["Cận lâm sàng"],
    "SK": ["Cận lâm sàng"],
    "NK": ["Cận lâm sàng liên quan"],
}

#: B2 — tiền tố ô dị ứng; `None` = đã có ô `<tiền tố>_allergy`, còn tên nhóm =
#: phiếu CHƯA có ô dị ứng, thêm cặp mới vào CUỐI nhóm ấy.
DI_UNG: dict[str, str | None] = {
    "NT": None,
    "HMVS": None,
    "SK": None,
    "PK": "Tiền sử bệnh",
    "NK": "Tiền sử nam khoa / sinh dục – tiết niệu",
}


def doc_v1() -> dict[str, tuple[str, list[dict[str, Any]]]]:
    sql = V1.read_text(encoding="utf-8")
    ra: dict[str, tuple[str, list[dict[str, Any]]]] = {}
    for m in re.finditer(
        r"SELECT c\.id, '(\w+)', 1, '([^']*)', 'PHIEU_KHAM', \$khung\$(.*?)\$khung\$",
        sql,
        re.S,
    ):
        ra[m.group(1)] = (m.group(2), json.loads(m.group(3)))
    return ra


def _o_chon_di_ung(tien_to: str, nhom: str | None) -> dict[str, Any]:
    ma = f"{tien_to}_allergy_co"
    o: dict[str, Any] = {
        "ma": ma,
        "ten": "Dị ứng thuốc",
        "kieu": "chon",
        "lua_chon": [
            {"ma": f"{ma}_1", "ten": "Có"},
            {"ma": f"{ma}_2", "ten": "Không"},
        ],
    }
    if nhom is not None:
        o["nhom"] = nhom
    o["them_sau_nguon"] = LY_DO_THEM
    return o


def _hien_khi_co(tien_to: str) -> dict[str, str]:
    return {"o": f"{tien_to}_allergy_co", "la": f"{tien_to}_allergy_co_1"}


def dung_v2(form_id: str, khung_v1: list[dict[str, Any]]) -> list[dict[str, Any]]:
    khung = copy.deepcopy(khung_v1)
    muc_b = next(m for m in khung if m["ma"] == "B")
    blocks: list[dict[str, Any]] = muc_b["block"]
    nhom_co = {b.get("nhom") for b in blocks}
    for ten in THU_GON.get(form_id, []) + GAP.get(form_id, []):
        if ten not in nhom_co:
            raise SystemExit(f"{form_id}: không có nhóm {ten!r} ở mục B")

    for b in blocks:
        if b.get("nhom") in THU_GON.get(form_id, []):
            b["thu_gon"] = True
        if b.get("nhom") in GAP.get(form_id, []):
            b["gap"] = True

    if form_id in DI_UNG:
        tien_to = form_id.lower()
        nhom_moi = DI_UNG[form_id]
        if nhom_moi is None:
            i = next(i for i, b in enumerate(blocks) if b["ma"] == f"{tien_to}_allergy")
            chi_tiet = blocks[i]
            chi_tiet["ten"] = "Chi tiết dị ứng thuốc"
            chi_tiet["hien_khi"] = _hien_khi_co(tien_to)
            blocks.insert(i, _o_chon_di_ung(tien_to, chi_tiet.get("nhom")))
        else:
            cuoi = max(i for i, b in enumerate(blocks) if b.get("nhom") == nhom_moi)
            blocks[cuoi + 1 : cuoi + 1] = [
                _o_chon_di_ung(tien_to, nhom_moi),
                {
                    "ma": f"{tien_to}_allergy",
                    "ten": "Chi tiết dị ứng thuốc",
                    "kieu": "doan_van",
                    "nhom": nhom_moi,
                    "hien_khi": _hien_khi_co(tien_to),
                    "them_sau_nguon": LY_DO_THEM,
                },
            ]
    return khung


def _sql_mot_phieu(form_id: str, ten: str, khung: list[dict[str, Any]]) -> str:
    k = json.dumps(khung, ensure_ascii=False)
    assert "$khung$" not in k
    return f"""WITH cu AS (
    SELECT d.clinic_id, d.version, d.nhom FROM public.form_definition d
     WHERE d.form_id = '{form_id}' AND d.trang_thai = 'PUBLISHED'
       AND d.xuat_ban_boi IS NULL
       AND d.khung IS DISTINCT FROM $khung${k}$khung$::jsonb
), doi AS (
    UPDATE public.form_definition d SET trang_thai = 'RETIRED'
      FROM cu WHERE d.clinic_id = cu.clinic_id AND d.form_id = '{form_id}'
       AND d.version = cu.version
    RETURNING d.clinic_id
)
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai,
     xuat_ban_boi, xuat_ban_luc)
SELECT cu.clinic_id, '{form_id}',
       (SELECT max(n.version) + 1 FROM public.form_definition n
         WHERE n.clinic_id = cu.clinic_id AND n.form_id = '{form_id}'),
       '{ten}', cu.nhom, $khung${k}$khung$::jsonb, 'PUBLISHED', NULL, now()
  FROM cu JOIN doi ON doi.clinic_id = cu.clinic_id;
"""


DAU_MIGRATION = """\
-- PHIẾU KHÁM v2 GỌN (đợt 3, 27/09/2026) — góp ý phòng khám (bác sĩ chính + thư ký
-- y khoa): B1 tiền sử thu gọn thành chip, bấm mới hiện ô · B2 dị ứng thuốc Có/Không,
-- chọn Có mới hiện "Chi tiết" · B3 bảng kết quả CLS gõ tay vào ngăn gập.
-- Sinh bằng scripts/phieu-kham/dung-phieu-v2.py từ v1 (20260924000008) → cùng dữ
-- liệu với src/clinicai/phieu_kham/dinh_nghia/*.json.
--
-- GIỮ NGUYÊN MỌI `ma` của v1; chỉ thêm ô `*_allergy_co` (NT · HMVS · SK) và cặp
-- `pk_allergy_co`/`pk_allergy`, `nk_allergy_co`/`nk_allergy` (PK · NK). Ba thuộc
-- tính mới (`thu_gon`, `hien_khi`, `gap`) chỉ là cách HIỂN THỊ — engine bỏ qua.
--
-- Chỉ thay bản do HỆ THỐNG xuất bản (xuat_ban_boi NULL): phòng khám đã tự xuất bản
-- thì không đè. Bản cũ → RETIRED; phiếu đã mở ghim version cũ
-- (`phieu_kham_luot.version`) vẫn đọc đúng khung cũ. THU_THUAT, SAN_CHAU không đổi.
-- Chạy lại được (khung đã bằng v2 thì không làm gì).

"""


def main() -> None:
    v1 = doc_v1()
    if set(v1) != {"NT", "HMVS", "PK", "SK", "NK", "THU_THUAT", "SAN_CHAU"}:
        raise SystemExit(f"Không đọc đủ bảy khung v1: {sorted(v1)}")
    phan: list[str] = []
    for form_id in THU_GON:
        ten, khung_v1 = v1[form_id]
        tep = DICH / f"{form_id}.json"
        dn = json.loads(tep.read_text(encoding="utf-8"))
        dn["khung"] = dung_v2(form_id, khung_v1)
        kiem_dinh_nghia(dn)
        tep.write_text(
            json.dumps(dn, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        phan.append(_sql_mot_phieu(form_id, ten, dn["khung"]))
    (REPO / "supabase/migrations" / MIGRATION).write_text(
        DAU_MIGRATION + "\n".join(phan), encoding="utf-8"
    )
    print(f"Đã ghi {len(phan)} khung v2 + {MIGRATION}")


if __name__ == "__main__":
    main()
