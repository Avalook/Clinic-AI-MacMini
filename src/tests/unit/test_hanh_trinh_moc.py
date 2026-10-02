"""Dải mốc hành trình ở đầu phiếu khám (lát 5, 26/09/2026) — hàm thuần."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from clinicai.phieu_kham.hanh_trinh import (
    BO,
    CHO_LAM,
    CHO_THU,
    CHUA,
    DA_XONG,
    DANG,
    DANG_LAM,
    XONG,
    SuKien,
    dung_moc,
    dung_tung_dich_vu,
)

T0 = datetime(2026, 9, 26, 1, 0, tzinfo=timezone.utc)  # 08:00 giờ VN


def p(phut: int) -> datetime:
    return T0 + timedelta(minutes=phut)


def _dv(lan: int | None, phut: int, **k: Any) -> dict[str, Any]:
    return {
        "lan": lan,
        "tao_luc": p(phut),
        "chon": k.get("chon", True),
        "da_tra": k.get("da_tra", False),
        "xong": k.get("xong", False),
        "phong": k.get("phong", "Phòng siêu âm"),
        "ngoai": k.get("ngoai", False),
    }


def _theo_ma(moc: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {m["ma"]: m for m in moc}


def test_khach_moi_check_in_chi_co_moc_dau_va_ve_chua() -> None:
    moc = dung_moc(
        dat_lich_luc=None, check_in_luc=p(0), ve_luc=None, su_kien=[], chi_dinh=[]
    )
    assert [m["ma"] for m in moc] == ["CHECK_IN", "SINH_HIEU", "KHAM", "VE"]
    m = _theo_ma(moc)
    assert m["CHECK_IN"]["trang_thai"] == XONG
    assert m["SINH_HIEU"]["trang_thai"] == CHUA
    assert m["VE"]["trang_thai"] == CHUA


def test_dat_lich_hom_truoc_duoc_danh_dau() -> None:
    moc = dung_moc(
        dat_lich_luc=p(-24 * 60),
        check_in_luc=p(0),
        ve_luc=None,
        su_kien=[],
        chi_dinh=[],
    )
    assert _theo_ma(moc)["DAT_LICH"]["hom_truoc"] is True


def test_nhieu_chi_dinh_cung_lan_la_mot_moc_theo_lan() -> None:
    su_kien: list[SuKien] = [
        ("vitals.started", p(5), {}),
        ("vitals.recorded", p(8), {}),
        ("consultation.started", p(10), {"loai": "TU_VAN"}),
        ("consultation.handed_over", p(20), {}),
        ("consultation.started", p(25), {"loai": "PRIMARY"}),
    ]
    chi_dinh = [_dv(1, 30), _dv(1, 30), _dv(2, 50, phong="Phòng lấy mẫu")]
    m = _theo_ma(
        dung_moc(
            dat_lich_luc=None,
            check_in_luc=p(0),
            ve_luc=None,
            su_kien=su_kien,
            chi_dinh=chi_dinh,
        )
    )
    assert m["SINH_HIEU"]["trang_thai"] == XONG
    assert m["TU_VAN"]["ket"] == p(20)
    assert m["KHAM"]["trang_thai"] == DANG
    lan = m["CHI_DINH"]["cac_lan"]
    assert [(x["lan"], x["so"]) for x in lan] == [(1, 2), (2, 1)]
    assert m["THU_TIEN"]["trang_thai"] == DANG and m["THU_TIEN"]["con_cho"] == 3
    assert m["LAM_DV"]["ten"] == "Làm dịch vụ (0/3 xong)"
    assert m["LAM_DV"]["noi"] == "Phòng siêu âm · Phòng lấy mẫu"


def test_khach_bo_o_quay_khong_tinh_vao_thu_va_lam() -> None:
    chi_dinh = [
        _dv(1, 30, da_tra=True, xong=True),
        _dv(1, 30, chon=False),
    ]
    su_kien: list[SuKien] = [
        ("payment.service_collected", p(35), {}),
        ("service.started", p(40), {}),
        ("result.ready", p(55), {}),
    ]
    m = _theo_ma(
        dung_moc(
            dat_lich_luc=None,
            check_in_luc=p(0),
            ve_luc=None,
            su_kien=su_kien,
            chi_dinh=chi_dinh,
        )
    )
    assert m["THU_TIEN"]["trang_thai"] == XONG and m["THU_TIEN"]["ket"] == p(35)
    assert m["LAM_DV"]["ten"] == "Làm dịch vụ (1/1 xong)"
    assert m["LAM_DV"]["trang_thai"] == XONG and m["LAM_DV"]["ket"] == p(55)


def test_doc_ket_qua_thuoc_va_ve() -> None:
    su_kien: list[SuKien] = [
        ("consultation.started", p(25), {"loai": "PRIMARY"}),
        ("consultation.completed", p(40), {"loai": "PRIMARY"}),
        ("consultation.started", p(90), {"loai": "REVIEW"}),
        ("consultation.completed", p(95), {"loai": "REVIEW"}),
        ("prescription.saved", p(94), {}),
        ("payment.medicine_collected", p(100), {}),
        ("medicine.dispensed", p(105), {}),
    ]
    moc = dung_moc(
        dat_lich_luc=None,
        check_in_luc=p(0),
        ve_luc=p(110),
        su_kien=su_kien,
        chi_dinh=[],
    )
    assert [m["ma"] for m in moc][-3:] == ["DOC_KQ", "THUOC", "VE"]
    assert all(m["trang_thai"] == XONG for m in moc if m["ma"] != "SINH_HIEU")


# --- Bảng "Từng dịch vụ" (27/09/2026, bản giao diện mẫu) -------------------


def _dong(phut: int, **k: Any) -> dict[str, Any]:
    them = {
        "id": k.pop("id", f"o{phut}"),
        "ten": k.pop("ten", "Siêu âm"),
        "tra_luc": k.pop("tra_luc", None),
        "bat_dau_luc": k.pop("bat_dau_luc", None),
        "xong_luc": k.pop("xong_luc", None),
    }
    if "dang_lam" in k:
        them["dang_lam"] = k.pop("dang_lam")
    return {**_dv(1, phut, **k), **them}


def test_tung_dich_vu_mot_truc_trang_thai_va_thu_tu_gui() -> None:
    ds = dung_tung_dich_vu(
        [
            _dong(40, id="c", da_tra=True, tra_luc=p(45)),
            _dong(30, id="a"),
            _dong(
                35,
                id="b",
                da_tra=True,
                tra_luc=p(38),
                bat_dau_luc=p(50),
                xong=True,
                xong_luc=p(62),
            ),
            _dong(36, id="d", da_tra=True, tra_luc=p(38), bat_dau_luc=p(55)),
            _dong(37, id="e", chon=False),
        ]
    )
    assert [d["id"] for d in ds] == ["a", "b", "d", "e", "c"], "theo giờ gửi"
    assert {d["id"]: d["trang_thai"] for d in ds} == {
        "a": CHO_THU,
        "b": DA_XONG,
        "c": CHO_LAM,
        "d": DANG_LAM,
        "e": BO,
    }
    b = ds[1]
    assert (b["gui"], b["thu"], b["bat_dau"], b["xong"]) == (
        p(35),
        p(38),
        p(50),
        p(62),
    )
    assert ds[0]["thu"] is None and ds[0]["xong"] is None


def test_tung_dich_vu_doi_tac_lay_mau_xong_la_dang_lam_chua_xong() -> None:
    (d,) = dung_tung_dich_vu(
        [
            _dong(
                30,
                da_tra=True,
                ngoai=True,
                bat_dau_luc=p(40),
                dang_lam=True,
                xong_luc=p(41),  # giờ lấy mẫu xong — CHƯA phải có kết quả
            )
        ]
    )
    assert d["noi"] == "Đối tác"
    assert d["trang_thai"] == DANG_LAM
    assert d["xong"] is None, "chưa có kết quả thì không ghi giờ xong"


def test_tung_dich_vu_bi_ngat_giu_gio_bat_dau_nhung_la_cho_lam() -> None:
    # INTERRUPTED giữ started_at cũ — cờ dang_lam quyết, không đoán theo giờ.
    (d,) = dung_tung_dich_vu(
        [_dong(30, da_tra=True, bat_dau_luc=p(40), dang_lam=False)]
    )
    assert d["trang_thai"] == CHO_LAM
    assert d["bat_dau"] == p(40)


# ── GIỜ THẬT, KHÔNG LÀM MÉO (Tuyền duyệt 29/09/2026) ─────────────────────────


def test_sinh_hieu_xong_la_lan_do_dau_do_lai_tra_rieng() -> None:
    """Đo 08:33 rồi đo lại 08:45: xong = 08:33 (không "làm 12′"); lần đo lại
    trả riêng kèm người đo."""
    su_kien: list[SuKien] = [
        ("vitals.started", p(30), {}),
        ("vitals.recorded", p(33), {"_ai": "ĐD Lan"}),
        ("vitals.started", p(44), {}),
        ("vitals.recorded", p(45), {"_ai": "ĐD Mai"}),
    ]
    sh = _theo_ma(
        dung_moc(
            dat_lich_luc=None,
            check_in_luc=p(0),
            ve_luc=None,
            su_kien=su_kien,
            chi_dinh=[],
        )
    )["SINH_HIEU"]
    assert (sh["bat"], sh["ket"], sh["trang_thai"]) == (p(30), p(33), XONG)
    assert sh["do_lai"] == [p(45)]
    assert sh["lan_do"] == [
        {"luc": p(33), "ai": "ĐD Lan"},
        {"luc": p(45), "ai": "ĐD Mai"},
    ]


def test_sinh_hieu_do_mot_lan_khong_co_do_lai() -> None:
    su_kien: list[SuKien] = [("vitals.recorded", p(8), {})]
    sh = _theo_ma(
        dung_moc(
            dat_lich_luc=None,
            check_in_luc=p(0),
            ve_luc=None,
            su_kien=su_kien,
            chi_dinh=[],
        )
    )["SINH_HIEU"]
    assert (sh["bat"], sh["ket"], sh["do_lai"]) == (p(8), p(8), [])
    assert sh["lan_do"] == [{"luc": p(8), "ai": None}]


# ── I2 (C18, 02/10/2026): mốc XONG theo TRẠNG THÁI HIỆN TẠI ─────────────────


def _su_kien_kham_xong() -> list[SuKien]:
    return [
        ("consultation.started", p(10), {"loai": "PRIMARY"}),
        ("consultation.completed", p(20), {"loai": "PRIMARY"}),
    ]


def test_hoan_tac_kham_xong_rut_moc_xong_ve_dang_kham() -> None:
    su_kien = [
        *_su_kien_kham_xong(),
        ("consultation.reopened", p(25), {"loai": "PRIMARY"}),
    ]
    moc = _theo_ma(
        dung_moc(
            dat_lich_luc=None,
            check_in_luc=p(0),
            ve_luc=None,
            su_kien=su_kien,
            chi_dinh=[],
        )
    )
    assert moc["KHAM"]["trang_thai"] == DANG
    assert moc["KHAM"]["ket"] is None
    assert moc["KHAM"]["mo_lai_luc"] == p(25)


def test_kham_xong_lai_sau_hoan_tac_thi_xong_lan_nua() -> None:
    su_kien = [
        *_su_kien_kham_xong(),
        ("consultation.reopened", p(25), {"loai": "PRIMARY"}),
        ("consultation.completed", p(40), {"loai": "PRIMARY"}),
    ]
    moc = _theo_ma(
        dung_moc(
            dat_lich_luc=None,
            check_in_luc=p(0),
            ve_luc=None,
            su_kien=su_kien,
            chi_dinh=[],
        )
    )
    assert moc["KHAM"]["trang_thai"] == XONG
    assert moc["KHAM"]["ket"] == p(40)
    assert moc["KHAM"]["mo_lai_luc"] is None


def test_mo_lai_phien_khac_khong_dong_den_kham_chinh() -> None:
    su_kien = [
        *_su_kien_kham_xong(),
        ("consultation.reopened", p(25), {"loai": "TU_VAN"}),
    ]
    moc = _theo_ma(
        dung_moc(
            dat_lich_luc=None,
            check_in_luc=p(0),
            ve_luc=None,
            su_kien=su_kien,
            chi_dinh=[],
        )
    )
    assert moc["KHAM"]["trang_thai"] == XONG


def test_hoan_tac_xong_tu_van_rut_moc_tu_van() -> None:
    su_kien = [
        ("consultation.started", p(5), {"loai": "TU_VAN"}),
        ("consultation.completed", p(9), {"loai": "TU_VAN"}),
        ("consultation.reopened", p(12), {"loai": "TU_VAN"}),
    ]
    moc = _theo_ma(
        dung_moc(
            dat_lich_luc=None,
            check_in_luc=p(0),
            ve_luc=None,
            su_kien=su_kien,
            chi_dinh=[],
        )
    )
    assert moc["TU_VAN"]["trang_thai"] == DANG
