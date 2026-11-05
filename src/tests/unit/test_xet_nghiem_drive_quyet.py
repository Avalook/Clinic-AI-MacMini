"""Chặng 4 — tên tệp Drive ⇒ ghép việc nào / vì sao chờ ghép tay (hàm thuần).

Ca biên kế hoạch mục 7: gõ nhầm một số ⇒ ghép tay, không gắn khách khác; không mã; hai
mã; ống của đối tác khác; ống nhiều việc chưa có kết quả; bản 2 khi việc đã có kết quả.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from clinicai.services.xet_nghiem.drive import den_drive, quyet_ghep
from clinicai.services.xet_nghiem.drive_api import doc_gio, thanh_tep
from clinicai.services.xet_nghiem.ma_mau import co_dang_ma, tao_ma

DT = "11111111-1111-1111-1111-111111111111"
KHAC = "22222222-2222-2222-2222-222222222222"
MA = tao_ma(572)  # M005724
MAU = {"mau_id": "m1", "doi_tac_id": DT}


def _v(oid: str, co_tep: bool = False) -> dict[str, Any]:
    return {
        "order_id": oid,
        "clinic_patient_id": "p1",
        "visit_id": "v1",
        "co_tep": co_tep,
    }


def test_khop_mot_viec_thi_ghep() -> None:
    q = quyet_ghep(f"{MA}_ket-qua.pdf", DT, MAU, [_v("o1")])
    assert (q.order_id, q.ly_do) == ("o1", None)


def test_go_nham_mot_so_la_sai_so_kiem_khong_ghep() -> None:
    sai = MA[:-1] + str((int(MA[-1]) + 1) % 10)
    q = quyet_ghep(f"{sai}.pdf", DT, MAU, [_v("o1")])
    assert (q.order_id, q.ly_do) == (None, "SAI_SO_KIEM")


def test_khong_co_ma() -> None:
    assert quyet_ghep("ket qua chi Mai.pdf", DT, None, []).ly_do == "KHONG_MA"
    assert not co_dang_ma("KQ_Mai_0211.pdf")


def test_hai_ma_khac_nhau_khong_doan() -> None:
    q = quyet_ghep(f"{MA}_{tao_ma(13)}.pdf", DT, MAU, [_v("o1")])
    assert q.ly_do == "NHIEU_MA"


def test_cung_ma_lap_lai_van_la_mot_ma() -> None:
    assert quyet_ghep(f"{MA}-{MA}.pdf", DT, MAU, [_v("o1")]).order_id == "o1"


def test_khong_thay_ong() -> None:
    assert quyet_ghep(f"{MA}.pdf", DT, None, []).ly_do == "KHONG_THAY_MAU"


def test_ong_cua_doi_tac_khac() -> None:
    q = quyet_ghep(f"{MA}.pdf", KHAC, MAU, [_v("o1")])
    assert (q.order_id, q.ly_do) == (None, "SAI_DOI_TAC")


def test_ong_hai_viec_chua_ket_qua_cho_ghep_tay() -> None:
    q = quyet_ghep(f"{MA}.pdf", DT, MAU, [_v("o1"), _v("o2")])
    assert (q.order_id, q.ly_do) == (None, "ONG_NHIEU_VIEC")


def test_ong_hai_viec_mot_da_co_ket_qua_thi_viec_con_lai() -> None:
    q = quyet_ghep(f"{MA}.pdf", DT, MAU, [_v("o1", co_tep=True), _v("o2")])
    assert q.order_id == "o2"


def test_mot_viec_da_co_ket_qua_thi_ban_moi() -> None:
    assert quyet_ghep(f"{MA}.pdf", DT, MAU, [_v("o1", co_tep=True)]).order_id == "o1"


def test_ong_khong_con_viec() -> None:
    assert quyet_ghep(f"{MA}.pdf", DT, MAU, []).ly_do == "KHONG_THAY_MAU"


def test_ten_rac_khong_nem() -> None:
    assert quyet_ghep(None, DT, None, []).ly_do == "KHONG_MA"  # type: ignore[arg-type]


def test_thanh_tep_doc_nguoi_tai_va_bo_qua_rac() -> None:
    t = thanh_tep(
        {
            "id": "abcDEF123456",
            "name": "M005724.pdf",
            "md5Checksum": "0" * 32,
            "size": "rác",
            "lastModifyingUser": {"displayName": "Lab Medlatec"},
        }
    )
    assert (t.nguoi_tai, t.so_byte, t.md5) == ("Lab Medlatec", None, "0" * 32)
    t2 = thanh_tep({"id": "x" * 12, "owners": [{"displayName": "Chủ thư mục"}]})
    assert t2.nguoi_tai == "Chủ thư mục" and t2.ten == ""


@pytest.mark.parametrize("rac", [None, "", "hôm qua", "2026-13-40T99:00:00Z", 12])
def test_gio_drive_rac_tra_rong(rac: object) -> None:
    assert doc_gio(rac) is None


def test_den_drive_bon_trang_thai() -> None:
    bay = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
    assert den_drive(None, None, None, None, bay)["mau"] == "neutral"
    assert "chưa quét" in den_drive("tm", None, None, None, bay)["nhan"]
    ok = den_drive("tm", bay, bay, None, bay)
    assert ok["mau"] == "success" and "16:00" in ok["nhan"]  # giờ Việt Nam
    assert den_drive("tm", bay, bay, "403", bay)["mau"] == "danger"
    cu = bay - timedelta(hours=2)
    assert den_drive("tm", bay, cu, None, bay)["mau"] == "danger"


def test_gio_drive_co_mui_gio() -> None:
    d = doc_gio("2026-11-05T08:00:00.000Z")
    assert d is not None and d.utcoffset() is not None and d.hour == 8
