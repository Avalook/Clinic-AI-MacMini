"""Dải mốc hành trình ở đầu phiếu khám (lát 5, 26/09/2026) — hàm thuần."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from clinicai.phieu_kham.hanh_trinh import CHUA, DANG, XONG, SuKien, dung_moc

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
