"""Gmail G3 — hàm thuần: đọc thư từng lab (mẫu tổng hợp theo định dạng thật, KHÔNG dữ
liệu khách), xác thực người gửi, mốc tự ghép, bảng quyết định ghép."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from clinicai.services.xet_nghiem.ghep_khach import UngVien
from clinicai.services.xet_nghiem.gmail_doc import (
    DocThu,
    doc_thu,
    kieu_thu,
    loai_dich_vu,
    loai_ket_qua,
    xac_thuc_ok,
)
from clinicai.services.xet_nghiem.gmail_ghep import (
    QuyetGmail,
    khong_thay_chi_dinh,
    luu_tru,
    quyet,
    trong_moc,
    vi_sao_khong_xet,
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
    assert d == DocThu("TM", TEN, SDT, 1990)
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


#: Khuôn header thật của HighDetect (đo prod 11/11, chỉ phần kỹ thuật).
_HD = (
    "mx.google.com; dkim=pass header.i=@highdetectlab-com.20260707.gappssmtp.com"
    ' header.s=20260707 header.b="FVVtEeG/"; spf=pass (google.com: domain of'
    " reports@highdetectlab.com designates 209.85.220.41 as permitted sender)"
    " smtp.mailfrom=reports@highdetectlab.com; dara=pass header.i=@gmail.com"
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
        # SPF khớp miền (HighDetect: Google Workspace, DKIM gappssmtp, không DMARC).
        (_HD, "reports@highdetectlab.com", True),
        ("mx.google.com; spf=pass smtp.mailfrom=lab.vn", "a@lab.vn", True),
        ("mx.google.com; spf=pass smtp.mailfrom=x@ke-gian.vn", "a@lab.vn", False),
        (
            "mx.google.com; spf=pass smtp.mailfrom=b@lab.vn.ke-gian.com",
            "a@lab.vn",
            False,
        ),
        ("mx.google.com; spf=softfail smtp.mailfrom=a@lab.vn", "a@lab.vn", False),
        ("mx.google.com; spf=pass", "a@lab.vn", False),
        # DKIM của miền mặc định Google (gappssmtp) KHÔNG chứng được miền lab.
        (
            "mx.google.com; dkim=pass header.i=@lab-vn.20260707.gappssmtp.com",
            "a@lab.vn",
            False,
        ),
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


NHAN = datetime(2026, 10, 15, 3, 0, tzinfo=UTC)  # giờ nhận thư
TRUOC, SAU = NHAN - timedelta(days=2), NHAN + timedelta(hours=1)


def _v(
    oid: str,
    kh: str,
    *,
    lay: bool = True,
    tep: datetime | None = None,
    tay: bool = False,
    ns: int | None = None,
    ten: str = "Trần Thị Mẫu",
    sdt: str = SDT,
    dv: str | None = None,
) -> UngVien:
    """`tep` = giờ thư của tờ từ Gmail; `tay` = có tờ tải tay; `dv` = tên dịch vụ."""
    return UngVien(
        oid, kh, "visit", ten, sdt, nam_sinh=ns, da_lay_mau=lay,
        co_tep=tep is not None or tay, tep_gmail_luc=tep, ten_dich_vu=dv,
    )  # fmt: skip


_D = DocThu("GLHD", TEN, SDT, 1990)


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
        # Một khách hai chỉ định cùng loại đang chờ ⇒ ghép tay, gợi ý khách.
        (_D, [_v("o1", "k1"), _v("o2", "k1")], True,
         QuyetGmail("ONG_NHIEU_VIEC", goi_y_clinic_patient_id="k1")),
        # G5: chưa bấm Lấy mẫu VẪN tự ghép (không còn CHUA_LAY_MAU).
        (_D, [_v("o1", "k1", lay=False)], True, QuyetGmail(None, "o1", "k1", "visit")),
        # Một chờ + một đã có tờ ⇒ ghép vào cái đang chờ.
        (_D, [_v("o1", "k1", tep=TRUOC), _v("o2", "k1")], True,
         QuyetGmail(None, "o2", "k1", "visit")),
        (_D, [_v("o1", "k1", tay=True), _v("o2", "k1")], True,
         QuyetGmail(None, "o2", "k1", "visit")),
        # Tuyền 11/11: chỉ định CHỈ có tờ tải tay ⇒ thư Gmail gắn thêm, song song.
        (_D, [_v("o1", "k1", tay=True)], True, QuyetGmail(None, "o1", "k1", "visit")),
        (_D, [_v("o1", "k1", tay=True), _v("o2", "k1", tep=TRUOC)], True,
         QuyetGmail(None, "o1", "k1", "visit")),
        # Hai chỉ định cùng chỉ có tờ tay ⇒ không đoán.
        (_D, [_v("o1", "k1", tay=True), _v("o2", "k1", tay=True)], True,
         QuyetGmail("ONG_NHIEU_VIEC", goi_y_clinic_patient_id="k1")),
        # Có cả tờ tay lẫn tờ Gmail ⇒ xét theo tờ Gmail (bản sửa / thư trùng).
        (_D, [_v("o1", "k1", tep=SAU, tay=True)], True,
         luu_tru("DA_CO_KET_QUA", goi_y_order_id="o1", goi_y_clinic_patient_id="k1")),
        # Đã có tờ Gmail CŨ hơn thư ⇒ thư mới hơn: bản sửa / bổ sung (người xem).
        (_D, [_v("o1", "k1", tep=TRUOC)], True,
         QuyetGmail("CO_BAN_MOI", goi_y_order_id="o1", goi_y_clinic_patient_id="k1")),
        # Đã có tờ Gmail KHÔNG cũ hơn thư (thư trùng / thư cũ quét sau) ⇒ đã xử lý.
        (_D, [_v("o1", "k1", tep=SAU)], True,
         luu_tru("DA_CO_KET_QUA", goi_y_order_id="o1", goi_y_clinic_patient_id="k1")),
        (_D, [_v("o1", "k1", tep=NHAN)], True,
         luu_tru("DA_CO_KET_QUA", goi_y_order_id="o1", goi_y_clinic_patient_id="k1")),
        # Không đọc được SĐT: PDF scan ⇒ KHONG_DOC_DUOC; có chữ ⇒ KHONG_KHOP_KHACH.
        (DocThu("TM", TEN, None, None), [_v("o1", "k1")], False,
         QuyetGmail("KHONG_DOC_DUOC")),
        (DocThu("TM", TEN, None, None), [_v("o1", "k1")], True,
         QuyetGmail("KHONG_KHOP_KHACH")),
        # Kết quả từng phần / phiếu ⇒ Lưu trữ (Kho) KÈM lý do, không ghép.
        (DocThu("GLHD", TEN, SDT, None, "CHUA_DU_KET_QUA"), [_v("o1", "k1")], True,
         luu_tru("CHUA_DU_KET_QUA")),
        (DocThu("EU", TEN, SDT, None, "PHIEU_MA_VACH"), [_v("o1", "k1")], True,
         luu_tru("PHIEU_MA_VACH")),
        # Không nhận ra kiểu thư ⇒ người xem, nói đúng lý do.
        (DocThu("", None, None, None), [_v("o1", "k1")], True,
         QuyetGmail("KHONG_RO_MAU_THU")),
        (_D, [], True, QuyetGmail("KHONG_KHOP_KHACH")),
    ],
)  # fmt: skip
def test_quyet(d: DocThu, viec: list[UngVien], co_chu: bool, ra: QuyetGmail) -> None:
    assert quyet(d, viec, co_chu, NHAN) == ra


@pytest.mark.parametrize(
    ("chu", "ra"),
    [
        ("KẾT QUẢ XÉT NGHIỆM HPV ĐỊNH TYPE — HPV 16: Âm tính", {"HPV"}),
        ("Chlamydia trachomatis: Âm tính · Neisseria gonorrhoeae: Âm tính", {"STD"}),
        ("Tế bào học cổ tử cung (ThinPrep) — Bethesda 2014", {"THINPREP"}),
        ("NIPT — nguy cơ thấp T21", {"NIPT"}),
        ("Sàng lọc gen lặn (carrier)", {"GEN"}),
        ("Công thức máu · Glucose 5.1", set()),
        ("HPV âm tính; Chlamydia âm tính; ThinPrep NILM", {"HPV", "STD", "THINPREP"}),
        ("", set()),
        (None, set()),
    ],
)
def test_loai_ket_qua(chu: object, ra: set[str]) -> None:
    assert loai_ket_qua(chu) == frozenset(ra)


@pytest.mark.parametrize(
    ("ten", "ra"),
    [
        ("HPV định type PCR (40 type)", {"HPV"}),
        ("HPV định type PCR 16 type", {"HPV"}),
        ("Combo HPV 40 + thinprep", {"HPV", "THINPREP"}),
        ("13 bệnh lây STD", {"STD"}),
        ("Thinprep sàng lọc tế bào ung thử cổ tử cung", {"THINPREP"}),
        ("NIPT Geneva 7", {"NIPT"}),
        ("Gentis 9 bệnh gen lặn", {"GEN"}),
        ("Xét nghiệm máu", set()),
        (None, set()),
    ],
)
def test_loai_dich_vu(ten: object, ra: set[str]) -> None:
    assert loai_dich_vu(ten) == frozenset(ra)


_HPV, _STD = "HPV định type PCR (40 type)", "13 bệnh lây STD"
_COMBO = "Combo HPV 40 + thinprep"


@pytest.mark.parametrize(
    ("loai", "viec", "ra"),
    [
        # Khách chờ HPV + STD (Tâm Minh): PDF HPV ⇒ HPV; PDF STD ⇒ STD.
        ({"HPV"}, [_v("o1", "k1", dv=_HPV), _v("o2", "k1", dv=_STD)],
         QuyetGmail(None, "o1", "k1", "visit")),
        ({"STD"}, [_v("o1", "k1", dv=_HPV), _v("o2", "k1", dv=_STD)],
         QuyetGmail(None, "o2", "k1", "visit")),
        # PDF nhắc cả hai / không rõ loại ⇒ không đoán.
        ({"HPV", "STD"}, [_v("o1", "k1", dv=_HPV), _v("o2", "k1", dv=_STD)],
         QuyetGmail("ONG_NHIEU_VIEC", goi_y_clinic_patient_id="k1")),
        (set(), [_v("o1", "k1", dv=_HPV), _v("o2", "k1", dv=_STD)],
         QuyetGmail("ONG_NHIEU_VIEC", goi_y_clinic_patient_id="k1")),
        # PDF HPV nhưng khách chỉ chờ STD ⇒ KHÔNG gán nhầm vào STD.
        ({"HPV"}, [_v("o2", "k1", dv=_STD)],
         QuyetGmail("KHONG_THAY_CHI_DINH", goi_y_clinic_patient_id="k1")),
        # PDF HPV, HPV đã có tờ Gmail cũ hơn, STD đang chờ ⇒ bản sửa của HPV, không
        # rơi vào STD.
        ({"HPV"}, [_v("o1", "k1", dv=_HPV, tep=TRUOC), _v("o2", "k1", dv=_STD)],
         QuyetGmail("CO_BAN_MOI", goi_y_order_id="o1", goi_y_clinic_patient_id="k1")),
        # HPV vs Combo HPV + ThinPrep: cùng có HPV ⇒ không đoán.
        ({"HPV"}, [_v("o1", "k1", dv=_HPV), _v("o3", "k1", dv=_COMBO)],
         QuyetGmail("ONG_NHIEU_VIEC", goi_y_clinic_patient_id="k1")),
        # Chỉ định không suy được loại (máu) không bị loại.
        ({"HPV"}, [_v("o4", "k1", dv="Xét nghiệm máu")],
         QuyetGmail(None, "o4", "k1", "visit")),
    ],
)  # fmt: skip
def test_quyet_theo_loai(loai: set[str], viec: list[UngVien], ra: QuyetGmail) -> None:
    d = DocThu("TM", TEN, SDT, None, loai=frozenset(loai))
    assert quyet(d, viec, True, NHAN) == ra


def test_doc_thu_lay_loai_tu_chu_pdf_khong_tu_ten_tep() -> None:
    """True Medicine ghi sai loại ở tên tệp ⇒ loại chỉ lấy từ CHỮ PDF."""
    d = doc_thu(
        f"Kết quả xét nghiệm: {TEN} - Ngày xét nghiệm: 08/11/2026",
        "",
        "TRAN_THI_MAU_081126_HPV_TMD.pdf",
        f"SĐT: {SDT}\nChlamydia trachomatis: Âm tính",
        2026,
    )
    assert d.loai == frozenset({"STD"})


def test_khong_thay_chi_dinh_chi_doi_khi_khach_co_that() -> None:
    kk = QuyetGmail("KHONG_KHOP_KHACH")
    assert khong_thay_chi_dinh(kk, "k9") == QuyetGmail(
        "KHONG_THAY_CHI_DINH", goi_y_clinic_patient_id="k9"
    )
    assert khong_thay_chi_dinh(kk, None) == kk  # không có hồ sơ ⇒ giữ "không khớp"
    nk = QuyetGmail("NHIEU_KHACH")
    assert khong_thay_chi_dinh(nk, "k9") == nk  # lý do khác ⇒ không đụng


@pytest.mark.parametrize(
    ("moc", "xac_thuc", "ra"),
    [
        (None, True, "CHUA_DAT_MOC"),
        (date(2026, 10, 16), True, "TRUOC_MOC"),
        (date(2026, 10, 15), False, "KHONG_XAC_THUC"),
        (date(2026, 10, 15), True, None),
        (date(2026, 10, 1), True, None),  # mốc lùi ⇒ gán ngược thư cũ
    ],
)
def test_vi_sao_khong_xet(moc: date | None, xac_thuc: bool, ra: str | None) -> None:
    assert vi_sao_khong_xet(NHAN, moc, xac_thuc) == ra


def test_vi_sao_cho_moi_ma_co_cau_va_ma_la_khong_ne() -> None:
    from clinicai.services.xet_nghiem.ghep_tay import (
        LUU_TRU_VI_SAO,
        LY_DO_CHO,
        vi_sao_cho,
    )

    # Mọi mã CHECK ở migration G5 đều có câu người đọc hiểu.
    for ma in ("CHUA_DAT_MOC", "TRUOC_MOC", "KHONG_XAC_THUC", "CHUA_DU_KET_QUA",
               "PHIEU_MA_VACH", "DA_CO_KET_QUA"):  # fmt: skip
        assert vi_sao_cho("LUU_TRU", ma) == LUU_TRU_VI_SAO[ma]
    for ma in ("KHONG_THAY_CHI_DINH", "KHONG_RO_MAU_THU", "KHONG_KHOP_KHACH"):
        assert vi_sao_cho(ma, None) == LY_DO_CHO[ma]
    assert vi_sao_cho("LUU_TRU", None) == "Lưu trữ (không tự ghép)"
    assert vi_sao_cho("MA_LA", None) == "Chờ ghép tay"


def test_doc_thu_ma_ly_do_khong_tu_ghep() -> None:
    chua_du = doc_thu(
        f"KQ xét nghiệm KH {TEN} (SID: 081126-1234567) - {SDT}",
        "Trạng thái : Chưa đủ kết quả",
        "x_1.pdf",
        "",
        2026,
    )
    assert chua_du.khong_tu_ghep == "CHUA_DU_KET_QUA"
    phieu = doc_thu(f"KẾT QUẢ NIP1234567 -{TEN}", "", "NIP1234567.pdf", "", 2026)
    assert phieu.khong_tu_ghep == "PHIEU_MA_VACH"
    assert doc_thu("Quảng cáo", "", "a.pdf", "", 2026).tu_ghep_duoc is False
