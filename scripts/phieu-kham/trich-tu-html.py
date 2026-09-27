#!/usr/bin/env python3
"""Trích 7 phiếu khám từ tài liệu nguồn đã chốt → khung JSON của Form Engine.

    python3 scripts/phieu-kham/trich-tu-html.py \\
        ~/Downloads/ClinicAI-7-phieu-v5-final-review.html

VÌ SAO TRÍCH BẰNG MÁY CHỨ KHÔNG GÕ TAY. Bảy phiếu có 450 khoá ổn định; gõ tay
450 khoá là 450 cơ hội gõ sai — và khoá sai thì không test nào bắt được, vì nó
vẫn là một chuỗi hợp lệ. Trích bằng máy thì khoá trong JSON CHÍNH LÀ khoá
trong nguồn, và chạy lại được khi nguồn đổi.

HAI CON SỐ, ĐỪNG LẪN
  * 418 — số ô trong nguồn mang thuộc tính `data-field-key`.
  * 450 — số KHOÁ ỔN ĐỊNH của bảy phiếu = 418 + 32 ô nguồn chỉ gắn `name`
    (18 ô bảng tinh dịch đồ `hmvs_semen_<hàng>_<lần>` và 14 ô "điều trị khác /
    lời dặn" của mục E, hai ô mỗi phiếu). Ô chỉ có `name` mang cờ
    `khoa_tu: "name"` trong JSON để đếm lại được mà không cần file nguồn.

LUẬT TRÍCH
  * Khoá ô = `data-field-key`, không có thì `name`. KHÔNG BAO GIỜ suy từ nhãn.
  * Nhóm checkbox liền nhau thành MỘT ô `nhieu_chon`; mã lựa chọn = khoá của
    từng checkbox trong nguồn, mã nhóm = phần chung của các khoá ấy.
  * Mỗi ô trong bảng là một ô riêng, mang theo `bang` / `hang` / `cot` để vẽ lại
    thành bảng — dữ liệu vẫn phẳng `{ma_o: {gia_tri, nguon}}` như mọi phiếu.
  * Mục C (chỉ định CLS), E (đơn thuốc), F (thủ thuật) và dải hành chính/sinh
    hiệu là LIÊN KẾT: dữ liệu thật nằm ở chỗ khác (service_order, prescription,
    vital_measurement). Khung chỉ khai liên kết, không nhận giá trị — để không
    có hai nơi giữ cùng một sự thật.
  * Tên dịch vụ / thuốc / thủ thuật trong nguồn chỉ là NHÃN. Chúng đi vào
    `tham_chieu_nguon.json` để người làm danh mục ánh xạ sang mã thật; không
    nhãn nào được dùng làm định danh.

Ghi ra `src/clinicai/phieu_kham/dinh_nghia/`.

LƯU Ý (27/09/2026): script này ra khung v1. JSON trong repo là v2 (thu gọn tiền
sử, dị ứng Có/Không, bảng CLS gập) — trích lại xong thì chạy tiếp
`scripts/phieu-kham/dung-phieu-v2.py`.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

GOC = Path(__file__).resolve().parents[2]
DICH = GOC / "src" / "clinicai" / "phieu_kham" / "dinh_nghia"

FORM_IDS = ["NT", "HMVS", "PK", "SK", "NK", "THU_THUAT", "SAN_CHAU"]

#: Nhóm checkbox mà nguồn KHÔNG ghi tiêu đề riêng (hoặc trùng tiêu đề nhóm
#: bên cạnh). Nhãn dưới đây là của người trích, không phải của nguồn — nên mỗi
#: ô mang cờ `ten_tu_dat: true` để ai đọc cũng biết mà đối chiếu lại. Chỉ là
#: NHÃN hiển thị; khoá vẫn lấy từ nguồn.
TEN_TU_DAT = {
    "nt_mht_type": "Phác đồ MHT",
    "nt_follow_tests": "Cần kiểm tra lại khi tái khám",
    "hmvs_follow_tests": "Cần kiểm tra lại khi tái khám",
    "pk_follow_tests": "Cần kiểm tra lại khi tái khám",
}

VOID = {"input", "br", "img", "meta", "link", "hr", "source", "col"}


class Nut:
    __slots__ = ("tag", "attrs", "con", "cha")

    def __init__(self, tag: str, attrs: dict[str, str], cha: Nut | None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.con: list[Nut | str] = []
        self.cha = cha

    def cls(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())

    def chu(self) -> str:
        out = []
        for c in self.con:
            out.append(c if isinstance(c, str) else c.chu())
        return re.sub(r"\s+", " ", "".join(out)).strip()

    def tim(self, dk) -> list[Nut]:
        kq = []
        for c in self.con:
            if isinstance(c, Nut):
                if dk(c):
                    kq.append(c)
                kq.extend(c.tim(dk))
        return kq


class DungCay(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.goc = Nut("#root", {}, None)
        self.hien = self.goc

    def handle_starttag(self, tag, attrs):
        n = Nut(tag, {k: (v or "") for k, v in attrs}, self.hien)
        self.hien.con.append(n)
        if tag not in VOID:
            self.hien = n

    def handle_startendtag(self, tag, attrs):
        self.hien.con.append(Nut(tag, {k: (v or "") for k, v in attrs}, self.hien))

    def handle_endtag(self, tag):
        n = self.hien
        while n is not None and n.tag != tag:
            n = n.cha
        if n is not None and n.cha is not None:
            self.hien = n.cha

    def handle_data(self, data):
        self.hien.con.append(data)


def khoa(n: Nut) -> str | None:
    return n.attrs.get("data-field-key") or n.attrs.get("name") or None


def gan_khoa(b: dict[str, Any], n: Nut) -> dict[str, Any]:
    """Ô nguồn không có `data-field-key` (chỉ có `name`) thì khai ra."""
    if not n.attrs.get("data-field-key"):
        b["khoa_tu"] = "name"
    return b


def kieu_cua(n: Nut) -> str:
    if n.tag == "textarea":
        return "doan_van"
    t = n.attrs.get("type", "text")
    return {"number": "so", "date": "ngay", "text": "text"}.get(t, "text")


def goc_chung(keys: list[str]) -> str:
    """Phần chung của các khoá `x_1, x_2 …` → `x`. Lấy từ KHOÁ, không từ nhãn."""
    goc = {re.sub(r"_\d+$", "", k) for k in keys}
    if len(goc) != 1:
        raise SystemExit(f"Nhóm checkbox không cùng gốc khoá: {keys}")
    return goc.pop()


def trich_muc(sec: Nut) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Đi tuần tự các con của một <section>, giữ tiêu đề nhóm gần nhất."""
    blocks: list[dict[str, Any]] = []
    phu: dict[str, Any] = {}
    nhom: str | None = None

    def di(n: Nut) -> None:
        nonlocal nhom
        c = n.cls()
        if "sub" in c:
            nhom = n.chu()
            return
        if "field" in c:
            lab = n.tim(lambda x: x.tag == "label")
            o = n.tim(lambda x: x.tag in ("input", "textarea", "select"))
            if not o:
                return
            k = khoa(o[0])
            if not k:
                raise SystemExit(f"Ô không có khoá: {n.chu()[:80]}")
            b: dict[str, Any] = {
                "ma": k,
                "ten": lab[0].chu() if lab else k,
                "kieu": kieu_cua(o[0]),
            }
            if nhom:
                b["nhom"] = nhom
            ph = o[0].attrs.get("placeholder")
            if ph:
                b["goi_y"] = ph
            blocks.append(gan_khoa(b, o[0]))
            return
        if "check-grid" in c:
            hop = n.tim(
                lambda x: x.tag == "input" and x.attrs.get("type") == "checkbox"
            )
            nhan = [lb.chu() for lb in n.tim(lambda x: x.tag == "label")]
            keys = [khoa(h) for h in hop]
            if None in keys:
                raise SystemExit(f"Checkbox không có khoá trong nhóm: {nhan}")
            ma = goc_chung(keys)  # type: ignore[arg-type]
            b = {
                "ma": ma,
                "ten": TEN_TU_DAT.get(ma) or nhom or ma,
                "kieu": "nhieu_chon",
                "lua_chon": [
                    {"ma": k, "ten": t} for k, t in zip(keys, nhan, strict=True)
                ],
            }
            if ma in TEN_TU_DAT:
                b["ten_tu_dat"] = True
            if nhom:
                b["nhom"] = nhom
            blocks.append(b)
            return
        if n.tag == "table" and "source-table" in c:
            ths = [th.chu() for th in n.tim(lambda x: x.tag == "th")]
            rows = [
                r
                for r in n.tim(lambda x: x.tag == "tr")
                if r.tim(lambda x: x.tag == "td")
            ]
            o_dau = rows[0].tim(lambda x: x.tag == "input")
            bang_ma = goc_chung([khoa(o_dau[0])]) if o_dau else "bang"
            bang_ma = re.sub(r"_\d+$", "", bang_ma)
            for r in rows:
                tds = r.tim(lambda x: x.tag == "td")
                hang = tds[0].chu()
                for ci, td in enumerate(tds[1:], start=1):
                    o = td.tim(lambda x: x.tag in ("input", "textarea"))
                    if not o:
                        continue
                    k = khoa(o[0])
                    cot = ths[ci] if ci < len(ths) else ""
                    nhieu_cot = len(ths) > 2
                    b = {
                        "ma": k,
                        "ten": f"{hang} — {cot}" if nhieu_cot else hang,
                        "kieu": kieu_cua(o[0]),
                        "bang": {"ma": bang_ma, "ten": ths[0], "cot": ths[1:]},
                        "hang": hang,
                        "cot": cot,
                    }
                    if nhom:
                        b["nhom"] = nhom
                    blocks.append(gan_khoa(b, o[0]))
            return
        # Mục C / E / F: phần liên kết, trích riêng làm tham chiếu.
        if "indication-layout" in c:
            phu["chi_dinh_cls"] = trich_chi_dinh(n)
            return
        if "treatment-wrap" in c:
            for f in n.tim(lambda x: "field" in x.cls()):
                di(f)
            phu["don_thuoc"] = True
            return
        if "procedure-list" in c:
            phu["thu_thuat"] = [
                {
                    "ma_nguon": h.attrs["name"],
                    "nhan": h.attrs.get("data-procedure", ""),
                    "mau_ket_qua_nguon": (
                        lb.tim(lambda x: x.tag == "button")[0].attrs.get(
                            "data-template"
                        )
                        if lb.tim(lambda x: x.tag == "button")
                        else None
                    ),
                }
                for lb in n.tim(lambda x: x.tag == "label")
                for h in lb.tim(lambda x: x.tag == "input")
            ]
            return
        if "carryover" in c:
            src = n.tim(lambda x: "data-bind-source" in x.attrs)
            if src:
                phu["mang_sang"] = src[0].attrs["data-bind-source"]
            return
        for con in n.con:
            if isinstance(con, Nut):
                di(con)

    for con in sec.con:
        if isinstance(con, Nut):
            di(con)
    return blocks, phu


def trich_chi_dinh(n: Nut) -> list[dict[str, Any]]:
    nhom_ds = []
    for det in n.tim(lambda x: x.tag == "details"):
        sm = det.tim(lambda x: x.tag == "summary")[0]
        ten_nhom = "".join(c for c in sm.con if isinstance(c, str)).strip()
        muc = []
        for h in det.tim(lambda x: x.tag == "input" and "service-check" in x.cls()):
            muc.append(
                {
                    "nhan": h.attrs.get("data-service", ""),
                    "cach_tra_ket_qua": h.attrs.get("data-sync-mode", ""),
                    "mau_ket_qua_nguon": h.attrs.get("data-template") or None,
                }
            )
        nhom_ds.append({"nhom": ten_nhom, "muc": muc})
    return nhom_ds


TEN_MUC = {
    "A": "A. Khám của bác sĩ tư vấn",
    "B": "B. Phiếu khám / đánh giá chuyên khoa",
    "C": "C. Chỉ định cận lâm sàng",
    "D": "D. Chẩn đoán và xử lý",
    "E": "E. Chỉ định điều trị",
    "F": "F. Chỉ định thủ thuật",
    "G": "G. Theo dõi và tái khám",
}

LIEN_KET = {
    "A": {"loai": "mang_sang", "nguon": "doctor-consultation"},
    "C": {"loai": "chi_dinh_cls", "rang_buoc": "service_order_id"},
    "E": {"loai": "don_thuoc", "rang_buoc": "prescription.drug_catalog_id"},
    "F": {"loai": "chi_dinh_thu_thuat", "rang_buoc": "service_order_id"},
}


def main(duong: str) -> None:
    raw = Path(duong).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    p = DungCay()
    p.feed(raw.decode("utf-8"))

    tham_chieu: dict[str, Any] = {"nguon_sha256": sha}
    khoi_chung: dict[str, str] = {}
    DICH.mkdir(parents=True, exist_ok=True)

    for art in p.goc.tim(lambda x: x.tag == "article" and "data-form-id" in x.attrs):
        fid = art.attrs["data-form-id"]
        if fid == "ROOM":
            # "Khu phòng dịch vụ" là contract giao diện phòng, không phải phiếu.
            continue
        if fid not in FORM_IDS:
            raise SystemExit(f"form_id lạ trong nguồn: {fid}")
        tieu_de = art.tim(lambda x: x.tag == "h1")[0].chu()
        binds = [
            x.attrs["data-bind"] for x in art.tim(lambda x: "data-bind" in x.attrs)
        ]
        ghi_chu_nguon = [
            x.chu()
            for x in art.tim(lambda x: "source-note" in x.cls())
            if "partner-routing-note" not in x.cls()
        ]
        khung: list[dict[str, Any]] = [
            {
                "ma": "HANH_CHINH",
                "ten": "Hành chính & sinh hiệu",
                "lien_ket": {"loai": "mang_sang", "truong": binds},
                "block": [],
            }
        ]
        tc: dict[str, Any] = {}
        for sec in art.tim(lambda x: x.tag == "section" and "data-section" in x.attrs):
            ma = sec.attrs["data-section"]
            blocks, phu = trich_muc(sec)
            muc: dict[str, Any] = {"ma": ma, "ten": TEN_MUC[ma], "block": blocks}
            if ma in LIEN_KET:
                muc["lien_ket"] = LIEN_KET[ma]
            khung.append(muc)
            if phu.get("chi_dinh_cls"):
                tc["chi_dinh_cls"] = phu["chi_dinh_cls"]
            if phu.get("thu_thuat"):
                tc["thu_thuat"] = phu["thu_thuat"]
        dn = {
            "form_id": fid,
            "ten": tieu_de.capitalize() if tieu_de.isupper() else tieu_de,
            "nhom": "PHIEU_KHAM",
            "nguon": {
                "tai_lieu": Path(duong).name,
                "sha256": sha,
                "ghi_chu": ghi_chu_nguon,
            },
            "khung": khung,
        }
        (DICH / f"{fid}.json").write_text(
            json.dumps(dn, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        # C và F là KHỐI DÙNG CHUNG: bảy phiếu phải giống hệt nhau. Lệch một
        # chữ là nguồn đang nói hai điều khác nhau — dừng, đừng đoán bên nào.
        for ten_khoi, gia in (
            ("chi_dinh_cls", tc.get("chi_dinh_cls")),
            ("thu_thuat", [dict(x, ma_nguon=None) for x in tc.get("thu_thuat", [])]),
        ):
            dau = json.dumps(gia, ensure_ascii=False, sort_keys=True)
            if khoi_chung.setdefault(ten_khoi, dau) != dau:
                raise SystemExit(f"Khối {ten_khoi} của {fid} lệch các phiếu khác.")
            if ten_khoi not in tham_chieu:
                tham_chieu[ten_khoi] = gia
        n_o = sum(len(m["block"]) for m in khung)
        print(f"{fid:10} {n_o:4} ô  ({tieu_de})")

    # Danh mục thuốc gợi ý (cách dùng / lưu ý) — dữ liệu nguồn, CHƯA ánh xạ kho.
    m = re.search(
        r'<script[^>]*id="med-guide-data"[^>]*>(.*?)</script>',
        raw.decode("utf-8"),
        re.S,
    )
    if m:
        thuoc = json.loads(m.group(1))
        tham_chieu["mau_thuoc"] = [
            {"ma": f"rx_{i:03d}", "nhan_nguon": ten, **v, "drug_catalog_id": None}
            for i, (ten, v) in enumerate(sorted(thuoc.items()), start=1)
        ]

    # Mẫu kết quả nguồn `modal_sa_obung` ↔ `ket_qua_mau.ma` `SA_OBUNG` ↔ biểu
    # mẫu engine `KQ_SA_OBUNG`: đổi MÃ sang MÃ, không dò theo nhãn.
    def form_kq(mau: str | None) -> str | None:
        return f"KQ_{mau.removeprefix('modal_').upper()}" if mau else None

    for g in tham_chieu["chi_dinh_cls"]:
        for m_ in g["muc"]:
            m_["form_id_ket_qua"] = form_kq(m_.pop("mau_ket_qua_nguon"))
            # Mã dịch vụ thật do danh mục (V5-A) ánh xạ. Để trống là cố ý:
            # tên "XN máu" không phải định danh dịch vụ nào cả.
            m_["service_code"] = None
    for i, x in enumerate(tham_chieu["thu_thuat"], start=1):
        x.pop("ma_nguon")
        x["ma"] = f"procedure_{i}"  # hậu tố chung của `<form>_procedure_<i>`
        x["form_id_ket_qua"] = form_kq(x.pop("mau_ket_qua_nguon"))
        x["service_code"] = None
    (DICH / "tham_chieu_nguon.json").write_text(
        json.dumps(tham_chieu, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
