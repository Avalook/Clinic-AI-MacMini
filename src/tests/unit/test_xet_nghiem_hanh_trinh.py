"""Hình bàn XN (bản mẫu 05/11): 5 mốc hành trình, nhóm khách, câu "vì sao".

Máy chủ quyết mốc nào sáng, khách mang chip gì — màn chỉ vẽ (luật 7)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from clinicai.services.xet_nghiem.hanh_trinh import (
    buoc_dang,
    hanh_trinh,
    nhom_khach,
    so_ngay_cho,
)
from clinicai.services.xet_nghiem.trang_thai import (
    SuViecXN,
    nut_cua,
    trang_thai_xet_nghiem,
)

H = date(2026, 11, 5)
L = datetime(2026, 11, 5, 2, 0, tzinfo=UTC)


def _r(**k: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "tao_luc": L,
        "thu_luc": None,
        "cho_qua_luc": None,
        "lay_luc": None,
        "tep_luc": None,
        "gui_luc": None,
        "dong_luc": None,
    }
    return base | k


def _trang(r: dict[str, Any], sv: SuViecXN) -> list[str]:
    return [m["trang_thai"] for m in hanh_trinh(r, trang_thai_xet_nghiem(sv))]


def test_moi_chi_dinh_moc_thu_dang_lam() -> None:
    assert _trang(_r(), SuViecXN(hom_nay=H)) == [
        "done",
        "current",
        "upcoming",
        "upcoming",
        "upcoming",
    ]


def test_da_lay_mau_moc_ket_qua_dang_lam() -> None:
    r = _r(thu_luc=L, lay_luc=L)
    sv = SuViecXN(hom_nay=H, ngay_thu=H, co_mau=True, hen_tra=H)
    assert _trang(r, sv) == ["done", "done", "done", "current", "upcoming"]
    assert hanh_trinh(r, trang_thai_xet_nghiem(sv))[3]["ten"] == "Chờ kết quả"


def test_buoc_dang_theo_moc_current() -> None:
    def b(r: dict[str, Any], sv: SuViecXN) -> str | None:
        return buoc_dang(hanh_trinh(r, trang_thai_xet_nghiem(sv)))

    assert b(_r(), SuViecXN(hom_nay=H)) == "thu"
    assert b(_r(thu_luc=L), SuViecXN(hom_nay=H, ngay_thu=H)) == "mau"
    co_mau = SuViecXN(hom_nay=H, ngay_thu=H, co_mau=True)
    assert b(_r(thu_luc=L, lay_luc=L), co_mau) == "ket_qua"
    co_tep = SuViecXN(hom_nay=H, ngay_thu=H, co_mau=True, co_tep=True)
    assert b(_r(thu_luc=L, lay_luc=L, tep_luc=L), co_tep) == "ket_qua"
    assert b(_r(), SuViecXN(hom_nay=H, da_huy_chi_dinh=True)) is None


def test_cho_qua_khong_thu_ghi_ro_moc_thu() -> None:
    r = _r(cho_qua_luc=L)
    moc = hanh_trinh(r, trang_thai_xet_nghiem(SuViecXN(hom_nay=H, duoc_cho_qua=True)))
    assert (moc[1]["ten"], moc[1]["trang_thai"]) == ("Cho lấy mẫu trước", "done")
    assert moc[2]["trang_thai"] == "current"


def test_doi_tac_tu_tra_moc_cuoi_va_khong_con_dang_lam() -> None:
    r = _r(thu_luc=L, lay_luc=L, dong_luc=L)
    sv = SuViecXN(hom_nay=H, ngay_thu=H, co_mau=True, da_dong=True)
    moc = hanh_trinh(r, trang_thai_xet_nghiem(sv))
    assert moc[4]["ten"] == "Đối tác đã tự trả"
    # Việc đã xong: mốc kết quả bỏ trống KHÔNG được sáng "đang làm".
    assert "current" not in [m["trang_thai"] for m in moc]


def test_huy_chi_dinh_khong_moc_nao_dang_lam() -> None:
    assert "current" not in _trang(_r(), SuViecXN(hom_nay=H, da_huy_chi_dinh=True))


def test_so_ngay_cho_khong_am_va_rong() -> None:
    assert so_ngay_cho(H - timedelta(days=3), H) == 3
    assert so_ngay_cho(H + timedelta(days=1), H) == 0
    assert so_ngay_cho(None, H) == 0


def _v(oid: str, kh: str, ngay: date, sv: SuViecXN) -> dict[str, Any]:
    return {
        "order_id": oid,
        "clinic_patient_id": kh,
        "ten_khach": f"Khách {kh}",
        "ma_bn": kh,
        "ngay_chi_dinh": ngay,
        "trang_thai": asdict(trang_thai_xet_nghiem(sv)),
    }


def test_nhom_khach_theo_ngay_va_qua_han_thang() -> None:
    qua = SuViecXN(hom_nay=H, ngay_thu=H, co_mau=True, hen_tra=H - timedelta(days=2))
    ds = [
        _v("o1", "A", H, SuViecXN(hom_nay=H)),
        _v("o2", "A", H, qua),
        _v("o3", "A", H - timedelta(days=1), SuViecXN(hom_nay=H)),
    ]
    g = nhom_khach(ds)
    assert [len(x["order_ids"]) for x in g] == [2, 1]
    assert (g[0]["nhan"], g[0]["mau"]) == ("Quá hẹn trả KQ", "warning")
    assert g[1]["nhan"] == "Chờ thu"


def test_khach_khong_ma_benh_nhan_moi_viec_mot_dong() -> None:
    ds = [_v("o1", "", H, SuViecXN(hom_nay=H)), _v("o2", "", H, SuViecXN(hom_nay=H))]
    for d in ds:
        d["clinic_patient_id"] = None
    assert len(nhom_khach(ds)) == 2


def test_vi_sao_moi_trang_thai_co_cau_va_qua_hen_noi_so_ngay() -> None:
    sv = SuViecXN(hom_nay=H, ngay_thu=H, co_mau=True, hen_tra=H - timedelta(days=3))
    assert "Quá hẹn trả 3 ngày" in trang_thai_xet_nghiem(sv).vi_sao
    for s in (
        SuViecXN(hom_nay=H),
        SuViecXN(hom_nay=H, duoc_cho_qua=True),
        SuViecXN(hom_nay=H, co_mau=True, co_tep=True),
        SuViecXN(hom_nay=H, co_tep=True, tep_moi_nhat_da_gui=True),
        SuViecXN(hom_nay=H, da_dong=True),
        SuViecXN(hom_nay=H, da_huy_chi_dinh=True),
    ):
        tt = trang_thai_xet_nghiem(s)
        assert tt.vi_sao.endswith("."), tt.ma


def test_chip_gop_qua_hen_tinh_o_ham_trang_thai() -> None:
    qua = trang_thai_xet_nghiem(
        SuViecXN(hom_nay=H, ngay_thu=H, co_mau=True, hen_tra=H - timedelta(days=2))
    )
    assert (qua.chip_nhan, qua.chip_mau, qua.mau_qua_hen) == (
        "Quá hẹn trả KQ",
        "warning",
        "danger",
    )
    mot = trang_thai_xet_nghiem(
        SuViecXN(hom_nay=H, ngay_thu=H, co_mau=True, hen_tra=H - timedelta(days=1))
    )
    assert mot.mau_qua_hen == "warning"
    thuong = trang_thai_xet_nghiem(SuViecXN(hom_nay=H))
    assert (thuong.chip_nhan, thuong.chip_mau, thuong.mau_qua_hen) == (
        thuong.nhan,
        thuong.mau,
        None,
    )


def _nut(sv: SuViecXN, **k: Any) -> dict[str, object]:
    base: dict[str, Any] = {
        "co_thu": False,
        "con_hoan": 0,
        "co_mau": False,
        "co_tep": False,
        "tep_moi_nhat_da_gui": False,
    }
    return nut_cua(trang_thai_xet_nghiem(sv), **(base | k))


def test_nut_cho_qua_chi_hien_cho_quan_ly_nhung_co_lenh_khong_doi() -> None:
    nv, ql = _nut(SuViecXN(hom_nay=H)), _nut(SuViecXN(hom_nay=H), quan_ly=True)
    assert nv["cho_qua"] is True and ql["cho_qua"] is True  # cờ lệnh: không theo vai
    assert (nv["hien_cho_qua"], ql["hien_cho_qua"]) == (False, True)


def test_go_cho_qua_khong_hien_hoan_tac_cho_nhan_vien() -> None:
    sv = SuViecXN(hom_nay=H, duoc_cho_qua=True)
    assert _nut(sv, duoc_cho_qua=True)["hoan_tac"] is None
    ql = _nut(sv, duoc_cho_qua=True, quan_ly=True)["hoan_tac"]
    assert isinstance(ql, dict) and ql["lenh"] == "go_cho_qua"


def test_hien_lay_mau_khi_con_ton_chua_co_mau() -> None:
    assert _nut(SuViecXN(hom_nay=H))["hien_lay_mau"] is True
    co_mau = SuViecXN(hom_nay=H, ngay_thu=H, co_mau=True)
    assert _nut(co_mau, co_mau=True)["hien_lay_mau"] is False
    assert _nut(SuViecXN(hom_nay=H, da_huy_chi_dinh=True))["hien_lay_mau"] is False


def test_con_ton_dung_ba_trang_thai_cuoi() -> None:
    xong = {
        trang_thai_xet_nghiem(s).ma
        for s in (
            SuViecXN(hom_nay=H, co_tep=True, tep_moi_nhat_da_gui=True),
            SuViecXN(hom_nay=H, da_dong=True),
            SuViecXN(hom_nay=H, da_huy_chi_dinh=True),
        )
    }
    assert len(xong) == 3
    assert not trang_thai_xet_nghiem(SuViecXN(hom_nay=H, da_dong=True)).con_ton
    assert trang_thai_xet_nghiem(SuViecXN(hom_nay=H)).con_ton
