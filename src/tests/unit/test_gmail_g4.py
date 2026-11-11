"""Gmail G4 — hàm thuần: đọc ô email / mã bên đối tác / mốc tự ghép (rác ⇒ 422, không
500) và đèn Email dùng chung luật đèn Drive (chữ Drive không đổi)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.xet_nghiem import o_nhap
from clinicai.services.xet_nghiem.drive import den_drive
from clinicai.services.xet_nghiem.gmail_cai_dat import den_email


@pytest.mark.parametrize(
    ("raw", "ra"),
    [
        (" KQ@Lab.VN ", "kq@lab.vn"),
        ("", None),
        (None, None),
        ("   ", None),
        (123, None),
    ],
)
def test_doc_email_hop_le(raw: object, ra: str | None) -> None:
    assert o_nhap.doc_email(raw) == ra


@pytest.mark.parametrize(
    "rac", ["khong-a-cong", "a@b", "@lab.vn", "a b@lab.vn", "x" * 260]
)
def test_doc_email_rac_422(rac: str) -> None:
    with pytest.raises(ValidationError):
        o_nhap.doc_email(rac)


@pytest.mark.parametrize(
    ("raw", "ra"), [(" hpv ", "HPV"), ("thin-prep.2", "THIN-PREP.2"), ("", None)]
)
def test_doc_ma_ben_doi_tac(raw: str, ra: str | None) -> None:
    assert o_nhap.doc_ma_ben_doi_tac(raw) == ra


@pytest.mark.parametrize("rac", ["HPV GENO", "-HPV", "Ố", "A" * 41])
def test_doc_ma_ben_doi_tac_rac(rac: str) -> None:
    with pytest.raises(ValidationError):
        o_nhap.doc_ma_ben_doi_tac(rac)


def test_cua_gan_khong_gui_ma_thi_khong_co_khoa_ma() -> None:
    """Giữ mã cũ khi bảng gán thứ hai (tab "Gán xét nghiệm") không gửi mã dựa vào
    `model_dump(exclude_unset=True)` ở router — khoá điều đó (test DB gọi thẳng
    service nên không bắt được ai bỏ exclude_unset)."""
    from clinicai.api.v1.routers.xet_nghiem import AnhXaIn

    d = AnhXaIn(doi_tac_id="a", service_price_id="b", gia_goi_y="1").model_dump(
        exclude_unset=True
    )
    assert "ma_ben_doi_tac" not in d and "mac_dinh" not in d
    co = AnhXaIn(doi_tac_id="a", service_price_id="b", ma_ben_doi_tac="").model_dump(
        exclude_unset=True
    )
    assert co["ma_ben_doi_tac"] == ""


def test_doc_ngay_moc() -> None:
    hom_nay = date(2026, 11, 9)
    assert o_nhap.doc_ngay_moc("2026-11-09", hom_nay) == hom_nay
    assert o_nhap.doc_ngay_moc("", hom_nay) is None
    assert o_nhap.doc_ngay_moc(None, hom_nay) is None
    for rac in ("2026-11-10", "09/11/2026", "abc", "2026-02-30"):
        with pytest.raises(ValidationError):
            o_nhap.doc_ngay_moc(rac, hom_nay)


def test_den_email_cung_luat_den_drive() -> None:
    bay_gio = datetime(2026, 11, 9, 3, tzinfo=UTC)
    gan = bay_gio - timedelta(minutes=5)
    assert den_email(None, None, None, None, bay_gio)["nhan"] == (
        "Chưa nối email gửi kết quả"
    )
    assert "chưa quét lần nào" in den_email("a@b.vn", None, None, None, bay_gio)["nhan"]
    ok = den_email("a@b.vn", gan, gan, None, bay_gio)
    assert ok["mau"] == "success" and ok["nhan"].startswith("Email ổn")
    loi = den_email("a@b.vn", gan, gan, "Mất quyền đọc Gmail", bay_gio)
    assert loi["mau"] == "danger" and "Mất quyền" in loi["nhan"]
    tre = den_email("a@b.vn", gan, bay_gio - timedelta(hours=2), None, bay_gio)
    assert tre["mau"] == "danger"
    # Chữ đèn Drive giữ nguyên sau khi tách luật chung.
    assert (
        den_drive(None, None, None, None, bay_gio)["nhan"] == "Chưa nối thư mục Drive"
    )
    assert den_drive("f", gan, gan, None, bay_gio)["nhan"].startswith("Drive ổn")
