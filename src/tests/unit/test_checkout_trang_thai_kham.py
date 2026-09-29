"""Ô "Trạng thái" + "Đang ở" ở màn Check-out (29/09/2026) — hàm thuần của
`checkout_service`. Bài kiểm trên Postgres:
`tests/services/test_bac_si_cua_phien_db.py`."""

from __future__ import annotations

from clinicai.services.checkout_service import dang_o_chu, trang_thai_kham


def test_trang_thai_kham_suy_tu_phien() -> None:
    assert trang_thai_kham([], vong_doc_mo=False) is None
    assert trang_thai_kham([("PRIMARY", "queued")], vong_doc_mo=False) == "Chờ khám"
    dang = trang_thai_kham(
        [("TU_VAN", "completed"), ("PRIMARY", "in_progress")], vong_doc_mo=False
    )
    assert dang == "Đang khám"
    # Khám xong, vòng đọc kết quả còn mở (đang chờ dịch vụ) → chờ đọc kết quả —
    # KHÔNG còn "Đang khám".
    assert (
        trang_thai_kham([("PRIMARY", "completed")], vong_doc_mo=True)
        == "Chờ đọc kết quả"
    )
    cho_doc = trang_thai_kham(
        [("PRIMARY", "completed"), ("REVIEW", "queued")], vong_doc_mo=True
    )
    assert cho_doc == "Chờ đọc kết quả"
    dang_doc = trang_thai_kham(
        [("PRIMARY", "completed"), ("REVIEW", "in_progress")], vong_doc_mo=True
    )
    assert dang_doc == "Đang đọc kết quả"
    xong = trang_thai_kham(
        [("PRIMARY", "completed"), ("REVIEW", "completed")], vong_doc_mo=False
    )
    assert xong == "Đã khám xong"
    # Phiên huỷ không tính.
    assert trang_thai_kham([("PRIMARY", "cancelled")], vong_doc_mo=False) is None


def test_dang_o_chu() -> None:
    assert dang_o_chu(None) is None
    assert dang_o_chu({"noi": "P.3", "nhan": "Đang khám"}) == "P.3 · Đang khám"
    assert dang_o_chu({"noi": "Quầy lễ tân", "nhan": ""}) == "Quầy lễ tân"
    assert dang_o_chu({"noi": None, "nhan": None}) is None
