"""Gmail G3 — hàm thuần: đọc thư từng lab (mẫu tổng hợp theo định dạng thật, KHÔNG dữ
liệu khách), xác thực người gửi, mốc tự ghép, bảng quyết định ghép."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from clinicai.services.xet_nghiem.ghep_khach import UngVien
from clinicai.services.xet_nghiem.gmail_doc import (
    DocThu,
    doc_thu,
    kieu_thu,
    xac_thuc_ok,
)
from clinicai.services.xet_nghiem.gmail_ghep import (
    LUU_TRU,
    QuyetGmail,
    quyet,
    trong_moc,
)

TEN = "TRẦN THỊ MẪU"
SDT = "0900000123"


@pytest.mark.parametrize(
    ("tieu_de", "kieu", "ten", "sdt"),
    [
        (f"Kết quả xét nghiệm: {TEN} - Ngày xét nghiệm: 08/11/2026", "TM", TEN, None),
        (f"Kết quả xét nghiệm: {TEN} - Ngày xét nghiệm: 08-11-2026", "TM", TEN, None),
        (f"KQ xét nghiệm KH {TEN} (SID: 081126-1234567) - {SDT}", "GLHD", TEN, SDT),
        (
            f"KQ xét nghiệm KH {TEN} (SID: 081126-12345678) - 090 000 0123",
            "GLHD",
            TEN,
            SDT,
        ),
        (f"KQ xét nghiệm KH {TEN} (SID: 081126-1234567) - ", "GLHD", TEN, None),
        (
            f"KQ xét nghiệm KH {TEN} (SID: 081126-1234567) - 12 Kim Ngưu",
            "GLHD",
            TEN,
            None,
        ),
        (f"KẾT QUẢ NIP1234567 -{TEN}", "EU", TEN, None),
        (f"KẾT QUẢ GEN LẶN NIP1234567CCL - {TEN}", "EU", TEN, None),
        (f"KẾT QUẢ GEN LẶN Y1234567 -{TEN}", "EU", TEN, None),
        (f"Trả lời: KẾT QUẢ NIP1234567 -{TEN}", "EU", TEN, None),
        (f"THÔNG BÁO THU LẠI MẪU NIPT MÃ NIP1234567 - {TEN}", "", None, None),
        ("Quảng cáo khuyến mãi", "", None, None),
        (None, "", None, None),
        (123, "", None, None),
    ],
)
def test_kieu_thu(tieu_de: object, kieu: str, ten: str | None, sdt: str | None) -> None:
    assert kieu_thu(tieu_de) == (kieu, ten, sdt)


def test_doc_thu_tm_sdt_trong_pdf_ns_trong_than() -> None:
    d = doc_thu(
        f"Kết quả xét nghiệm: {TEN} - Ngày xét nghiệm: 08/11/2026",
        f"Họ tên: {TEN}, NS: 1990, Giới: Nữ",
        "TRAN_THI_MAU_081126-501726_HPV_TMD.pdf",
        f"Hotline: 0281234567 - 0911111111\nSĐT: {SDT}\nĐơn vị: PK 4WOMEN CLINIC",
        2026,
    )
    # Hotline của lab KHÔNG được nhận là SĐT khách (không có nhãn SĐT).
    assert d == DocThu("TM", TEN, SDT, 1990, True)
    # NS 2 chữ số (rác trong thân) ⇒ không có năm sinh.
    assert (
        doc_thu(
            f"Kết quả xét nghiệm: {TEN} - Ngày xét nghiệm: 08/11/2026",
            "NS: 99",
            "",
            f"SĐT: {SDT}",
            2026,
        ).nam_sinh
        is None
    )


def test_doc_thu_glhd_tieu_de_hong_thi_lay_pdf_va_chua_du_khong_tu_ghep() -> None:
    td_hong = f"KQ xét nghiệm KH {TEN} (SID: 081126-1234567) - 12 Kim Ngưu"
    d = doc_thu(td_hong, "", "x_1.pdf", f"Năm sinh: 1985 Số điện thoại: {SDT}", 2026)
    assert (d.sdt, d.nam_sinh, d.tu_ghep_duoc) == (SDT, 1985, True)
    chua_du = doc_thu(
        f"KQ xét nghiệm KH {TEN} (SID: 081126-1234567) - {SDT}",
        "Tên khách hàng : X Địa chỉ : Y Trạng thái : Chưa đủ kết quả",
        "x_1.pdf",
        "",
        2026,
    )
    assert chua_du.tu_ghep_duoc is False


def test_doc_thu_eu_mot_so_di_dong_va_phieu_ma_vach() -> None:
    chu = f"Họ tên: {TEN} Ngày sinh: ĐT: 15/03/1990 01/11/2026 0900 000 123"
    d = doc_thu(f"KẾT QUẢ NIP1234567 -{TEN}", "", f"NIP1234567 -{TEN}.pdf", chu, 2026)
    assert (d.sdt, d.nam_sinh, d.tu_ghep_duoc) == (SDT, 1990, True)
    hai_so = doc_thu(
        f"KẾT QUẢ NIP1234567 -{TEN}", "", "a.pdf", f"{chu} 0911222333", 2026
    )
    assert hai_so.sdt is None  # nhiều số ⇒ không đoán
    phieu = doc_thu(f"KẾT QUẢ NIP1234567 -{TEN}", "", "NIP1234567.pdf", chu, 2026)
    assert phieu.tu_ghep_duoc is False


_THAT = (
    "mx.google.com;\r\n       dkim=pass header.i=@lab.vn header.s=google header.b=Ab1;"
    "\r\n       spf=pass (google.com: domain of a@lab.vn designates 1.2.3.4 as"
    " permitted sender) smtp.mailfrom=a@lab.vn;\r\n       dmarc=pass (p=NONE sp=NONE"
    " dis=NONE) header.from=lab.vn"
)


@pytest.mark.parametrize(
    ("hdr", "tu", "ok"),
    [
        (_THAT, "a@lab.vn", True),  # đúng khuôn Gmail ghi (có chú thích, xuống dòng)
        ("mx.google.com; dkim=pass header.i=@lab.vn; spf=pass", "a@lab.vn", True),
        ("mx.google.com; dkim=pass header.d=gmail.com", "a@gmail.com", True),
        ("mx.google.com; dmarc=pass header.from=lab.vn", "a@lab.vn", True),
        ("mx.google.com; dkim=pass header.i=@ke-gian.vn; spf=fail", "a@lab.vn", False),
        ("mx.google.com; dkim=fail; spf=softfail; dmarc=fail", "a@lab.vn", False),
        # Miền đuôi dài của kẻ gian không được coi là miền lab.
        ("mx.google.com; dkim=pass header.d=lab.vn.ke-gian.com", "a@lab.vn", False),
        ("mx.google.com; dkim=pass header.i=@lab.vn.ke-gian.com", "a@lab.vn", False),
        # Từng kết quả xét riêng: dkim hỏng của lab + dkim đạt của miền khác ⇒ không.
        (
            "mx.google.com; dkim=fail header.i=@lab.vn; dkim=pass header.i=@ke-gian.vn",
            "a@lab.vn",
            False,
        ),
        # dmarc=pass phải đúng miền From.
        ("mx.google.com; dmarc=pass header.from=ke-gian.vn", "a@lab.vn", False),
        ("mx.google.com; dmarc=pass", "a@lab.vn", False),
        # Header không do Gmail ghi (người gửi tự chèn).
        ("ke-gian.vn; dmarc=pass header.from=lab.vn", "a@lab.vn", False),
        ("", "a@lab.vn", False),
        (None, "a@lab.vn", False),
        ("mx.google.com; dmarc=pass header.from=x", "khong-co-a-cong", False),
    ],
)
def test_xac_thuc_ok(hdr: object, tu: str, ok: bool) -> None:
    assert xac_thuc_ok(hdr, tu) is ok


def test_chi_lay_header_xac_thuc_tren_cung_do_gmail_ghi() -> None:
    from clinicai.services.xet_nghiem.gmail_api import _xac_thuc_gmail

    gmail = "mx.google.com; dkim=fail; dmarc=fail header.from=lab.vn"
    chen = "mx.google.com; dmarc=pass header.from=lab.vn"  # kẻ gửi tự chèn, nằm dưới
    hs = [
        {"name": "Received", "value": "x"},
        {"name": "Authentication-Results", "value": gmail},
        {"name": "authentication-results", "value": chen},
    ]
    assert _xac_thuc_gmail(hs) == gmail
    assert xac_thuc_ok(_xac_thuc_gmail(hs), "a@lab.vn") is False
    assert _xac_thuc_gmail(None) == "" and _xac_thuc_gmail([1, "x"]) == ""


def test_trong_moc() -> None:
    nhan = datetime(2026, 11, 8, 18, 0, tzinfo=UTC)  # 01:00 ngày 09/11 giờ VN
    assert trong_moc(nhan, date(2026, 11, 9)) is True
    assert trong_moc(nhan, date(2026, 11, 10)) is False
    assert trong_moc(nhan, None) is False
    assert trong_moc("rác", date(2026, 11, 9)) is False


def _v(oid: str, kh: str, *, lay: bool = True, tep: bool = False, ns: int | None = None,
       ten: str = "Trần Thị Mẫu", sdt: str = SDT) -> UngVien:  # fmt: skip
    return UngVien(oid, kh, "visit", ten, sdt, nam_sinh=ns, da_lay_mau=lay, co_tep=tep)


_D = DocThu("GLHD", TEN, SDT, 1990, True)


@pytest.mark.parametrize(
    ("d", "viec", "co_chu", "ra"),
    [
        (_D, [_v("o1", "k1")], True, QuyetGmail(None, "o1", "k1", "visit")),
        # Tên khác / SĐT khác ⇒ không khớp.
        (_D, [_v("o1", "k1", ten="Lê Thị Khác")], True, QuyetGmail("KHONG_KHOP_KHACH")),
        (_D, [_v("o1", "k1", sdt="0911222333")], True, QuyetGmail("KHONG_KHOP_KHACH")),
        # Mẹ con chung số: năm sinh gỡ được ⇒ tự ghép; không gỡ được ⇒ NHIEU_KHACH.
        (_D, [_v("o1", "k1", ns=1990), _v("o2", "k2", ns=1965)], True,
         QuyetGmail(None, "o1", "k1", "visit")),
        (_D, [_v("o1", "k1", ns=None), _v("o2", "k2", ns=None)], True,
         QuyetGmail("NHIEU_KHACH")),
        # Một khách hai việc chờ (HPV + ThinPrep) ⇒ ghép tay, gợi ý khách.
        (_D, [_v("o1", "k1"), _v("o2", "k1")], True,
         QuyetGmail("ONG_NHIEU_VIEC", goi_y_clinic_patient_id="k1")),
        # Quên bấm Lấy mẫu ⇒ CHUA_LAY_MAU + gợi ý việc.
        (_D, [_v("o1", "k1", lay=False)], True,
         QuyetGmail("CHUA_LAY_MAU", goi_y_order_id="o1", goi_y_clinic_patient_id="k1")),
        # Đã có tờ ⇒ bản sửa / bổ sung.
        (_D, [_v("o1", "k1", tep=True)], True,
         QuyetGmail("CO_BAN_MOI", goi_y_order_id="o1", goi_y_clinic_patient_id="k1")),
        # Không đọc được SĐT: PDF scan ⇒ KHONG_DOC_DUOC; có chữ ⇒ KHONG_KHOP_KHACH.
        (DocThu("TM", TEN, None, None, True), [_v("o1", "k1")], False,
         QuyetGmail("KHONG_DOC_DUOC")),
        (DocThu("TM", TEN, None, None, True), [_v("o1", "k1")], True,
         QuyetGmail("KHONG_KHOP_KHACH")),
        # Kết quả từng phần / phiếu ⇒ Lưu trữ (Kho), không ghép.
        (DocThu("GLHD", TEN, SDT, None, False), [_v("o1", "k1")], True, LUU_TRU),
        # Không nhận ra kiểu thư ⇒ người xem.
        (DocThu("", None, None, None, False), [_v("o1", "k1")], True,
         QuyetGmail("KHONG_KHOP_KHACH")),
        (_D, [], True, QuyetGmail("KHONG_KHOP_KHACH")),
    ],
)  # fmt: skip
def test_quyet(d: DocThu, viec: list[UngVien], co_chu: bool, ra: QuyetGmail) -> None:
    assert quyet(d, viec, co_chu) == ra
