"""Ghép tệp Drive theo tên + SĐT đọc trong PDF (Tuyền chốt 05/11) — hàm thuần.

Ca biên: khớp đủ tên + SĐT ⇒ ghép; chỉ tên hoặc chỉ SĐT ⇒ không; hai khách cùng khớp
⇒ không đoán; một khách hai việc chờ ⇒ ghép tay; PDF scan (không chữ) ⇒ đọc không được;
tên có dấu vs không dấu, SĐT viết +84 / có dấu chấm cách; rác không ném.
"""

from __future__ import annotations

import pytest

from clinicai.services.xet_nghiem.ghep_khach import (
    UngVien,
    chu_pdf,
    chuan,
    chuan_sdt,
    khop_khach,
    sdt_trong,
)


def pdf_co_chu(dong: list[str]) -> bytes:
    """PDF một trang thật (Helvetica, chữ ASCII) — đủ để pypdf đọc lại chữ."""
    noi = (
        "BT /F1 12 Tf 50 800 Td "
        + " ".join(f"({d.replace('(', '').replace(')', '')}) Tj 0 -16 Td" for d in dong)
        + " ET"
    )
    obj = [
        "<</Type/Catalog/Pages 2 0 R>>",
        "<</Type/Pages/Kids[3 0 R]/Count 1>>",
        "<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R"
        "/Resources<</Font<</F1 5 0 R>>>>>>",
        f"<</Length {len(noi)}>>stream\n{noi}\nendstream",
        "<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    ra = b"%PDF-1.4\n"
    vi_tri = []
    for i, o in enumerate(obj, 1):
        vi_tri.append(len(ra))
        ra += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(ra)
    ra += f"xref\n0 {len(obj) + 1}\n0000000000 65535 f \n".encode()
    ra += "".join(f"{v:010d} 00000 n \n" for v in vi_tri).encode()
    ra += (
        f"trailer<</Size {len(obj) + 1}/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return ra


def _u(oid: str, cp: str, ten: str, sdt: str) -> UngVien:
    return UngVien(order_id=oid, clinic_patient_id=cp, visit_id="v", ten=ten, sdt=sdt)


AN = _u("o1", "p1", "Nguyễn Thị An", "0901234567")
BINH = _u("o2", "p2", "Trần Thị Bình", "0912345678")


def test_doc_chu_pdf_that() -> None:
    chu = chu_pdf(pdf_co_chu(["Ho ten: NGUYEN THI AN", "SDT: 0901.234.567"]))
    assert "NGUYEN THI AN" in chu and "0901.234.567" in chu


def test_khop_du_ten_va_sdt_thi_ghep() -> None:
    chu = chu_pdf(pdf_co_chu(["Ho ten: NGUYEN THI AN", "Dien thoai: 0901 234 567"]))
    assert khop_khach(f"KQ_0211.pdf\n{chu}", [AN, BINH]) == (AN, None)


def test_sdt_dang_84_va_ten_khong_dau() -> None:
    assert khop_khach("nguyen thi an +84 901 234 567", [AN, BINH])[0] == AN


def test_chi_ten_hoac_chi_sdt_khong_ghep() -> None:
    assert khop_khach("Nguyen Thi An 0999999999", [AN]) == (None, "KHONG_KHOP_KHACH")
    assert khop_khach("Le Van C 0901234567", [AN]) == (None, "KHONG_KHOP_KHACH")


def test_ten_la_mot_phan_ten_khac_khong_tinh() -> None:
    # "Thi An" không được khớp "Nguyễn Thị An" khi tệp ghi "Nguyen Thi Anh".
    assert khop_khach("Nguyen Thi Anh 0901234567", [AN]) == (None, "KHONG_KHOP_KHACH")


def test_hai_khach_cung_khop_khong_doan() -> None:
    an2 = _u("o3", "p3", "Nguyễn Thị An", "0901234567")
    assert khop_khach("Nguyen Thi An 0901234567", [AN, an2]) == (None, "NHIEU_KHACH")


def test_mot_khach_hai_viec_cho_ghep_tay() -> None:
    an_viec_2 = _u("o9", "p1", "Nguyễn Thị An", "0901234567")
    kq = khop_khach("Nguyen Thi An 0901234567", [AN, an_viec_2])
    assert kq == (None, "ONG_NHIEU_VIEC")


def test_pdf_scan_khong_chu() -> None:
    assert chu_pdf(b"%PDF-1.4 rac") == ""
    assert chu_pdf(b"\x89PNG....") == ""
    assert khop_khach("", [AN]) == (None, "KHONG_DOC_DUOC")


@pytest.mark.parametrize("rac", [None, 12, "", "abc", "012345", "+1 555 1234 567"])
def test_sdt_rac_tra_rong(rac: object) -> None:
    assert chuan_sdt(rac) is None


def test_chuan_bo_dau_va_d() -> None:
    assert chuan("Đỗ  Thị   HẰNG!") == "do thi hang"
    assert chuan(None) == ""
    assert sdt_trong("goi 0912.345.678 hoac 84901234567") == {
        "0912345678",
        "0901234567",
    }
