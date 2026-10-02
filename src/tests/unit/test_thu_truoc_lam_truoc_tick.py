"""Phần THUẦN của "thu trước, trừ khi tick Làm trước – thu sau" (30/09/2026 tối).

Cửa làm của FinanceGate theo dây ``thu_truoc_khi_lam`` + tick của lượt, cờ cho
màn, nhãn trạng thái dịch vụ ở quầy. Bài có database:
``services/test_thu_truoc_lam_truoc_tick_db.py``.
"""

from __future__ import annotations

from clinicai.services import finance_gate
from clinicai.services.day_noi import DAY, giai_gia_tri
from clinicai.services.lam_truoc_thu_sau import (
    CAU_BO_CHUA_LAM,
    CAU_BO_DA_LAM,
    CAU_KHONG_QUYEN,
    co_tick,
    da_lam_xong_het,
    trang_thai_dich_vu_lam_truoc,
)


def test_day_thu_truoc_mac_dinh_bat() -> None:
    assert DAY["thu_truoc_khi_lam"].mac_dinh is True
    assert giai_gia_tri("thu_truoc_khi_lam", None) is True
    assert giai_gia_tri("thu_truoc_khi_lam", "false") is False


def test_cua_lam_theo_day_va_tick() -> None:
    # Dây TẮT = V10: chưa thu vẫn làm.
    assert finance_gate.cua_lam("DUE", thu_truoc_khi_lam=False, lam_truoc_thu_sau=False)
    # Dây BẬT + không tick: chỉ tiền đã xong / chờ xác minh.
    for st, mo in (
        ("DUE", False),
        ("FINANCIAL_DATA_INCOMPLETE", False),
        ("PAID", True),
        ("NOT_REQUIRED", True),
        ("PARTNER_COLLECTS", True),
        ("PENDING_VERIFICATION", True),
        ("REFUNDED", False),
        ("FINANCIAL_REVIEW_REQUIRED", False),
    ):
        assert (
            finance_gate.cua_lam(st, thu_truoc_khi_lam=True, lam_truoc_thu_sau=False)
            is mo
        ), st
    # Tick → như V10; tiền đã hoàn / sổ lệch vẫn chặn.
    assert finance_gate.cua_lam("DUE", thu_truoc_khi_lam=True, lam_truoc_thu_sau=True)
    assert not finance_gate.cua_lam(
        "REFUNDED", thu_truoc_khi_lam=True, lam_truoc_thu_sau=True
    )


def test_co_tick_cho_man() -> None:
    kq = co_tick(
        cong_tac_bat=True, co_quyen=True, da_tick=False, da_bat_dau=False, luot_mo=True
    )
    assert (kq["tick_duoc"], kq["bo_tick_duoc"], kq["chot_thu_sau_duoc"]) == (
        True,
        False,
        False,
    )
    kq = co_tick(
        cong_tac_bat=True, co_quyen=True, da_tick=True, da_bat_dau=True, luot_mo=True
    )
    # Hoàn tác (01/10/2026): đã có dịch vụ bắt đầu làm VẪN bỏ tick được — không
    # khoá cứng; máy chủ chỉ nói rõ chuyện gì xảy ra.
    assert (kq["bo_tick_duoc"], kq["ly_do_khong_bo"]) == (True, None)
    assert kq["luu_y_bo"] == CAU_BO_DA_LAM
    assert kq["chot_thu_sau_duoc"] is True
    kq = co_tick(
        cong_tac_bat=True, co_quyen=True, da_tick=True, da_bat_dau=False, luot_mo=True
    )
    assert (kq["bo_tick_duoc"], kq["luu_y_bo"]) == (True, CAU_BO_CHUA_LAM)
    # Thiếu quyền thì không bỏ được, câu rõ; chưa tick thì không có gì để bỏ.
    kq = co_tick(
        cong_tac_bat=True, co_quyen=False, da_tick=True, da_bat_dau=False, luot_mo=True
    )
    assert (kq["bo_tick_duoc"], kq["ly_do_khong_bo"]) == (False, CAU_KHONG_QUYEN)
    kq = co_tick(
        cong_tac_bat=True, co_quyen=True, da_tick=False, da_bat_dau=False, luot_mo=True
    )
    assert (kq["bo_tick_duoc"], kq["luu_y_bo"]) == (False, None)
    # Dây tắt: không mời tick, quầy "Chốt, thu sau" như V10.
    kq = co_tick(
        cong_tac_bat=False, co_quyen=True, da_tick=False, da_bat_dau=False, luot_mo=True
    )
    assert (kq["hien"], kq["tick_duoc"], kq["chot_thu_sau_duoc"]) == (
        False,
        False,
        True,
    )
    # Lượt đã đóng / khách về: không mời tick.
    assert not co_tick(
        cong_tac_bat=True, co_quyen=True, da_tick=False, da_bat_dau=False, luot_mo=False
    )["tick_duoc"]


def test_trang_thai_dich_vu_va_xong_het() -> None:
    assert trang_thai_dich_vu_lam_truoc("COMPLETED", None) == "DA_XONG"
    assert trang_thai_dich_vu_lam_truoc(None, "performed") == "DA_XONG"
    assert trang_thai_dich_vu_lam_truoc("IN_PROGRESS", "assigned") == "DANG_LAM"
    assert trang_thai_dich_vu_lam_truoc("NOT_PERFORMED", None) == "KHONG_LAM"
    assert trang_thai_dich_vu_lam_truoc(None, "authorized") == "CHUA_LAM"
    # Rác → chưa làm, không ném.
    assert trang_thai_dich_vu_lam_truoc(123, ["x"]) == "CHUA_LAM"
    assert da_lam_xong_het(["DA_XONG", "KHONG_LAM"])
    assert not da_lam_xong_het(["DA_XONG", "DANG_LAM"])
    assert not da_lam_xong_het(["KHONG_LAM"])
    assert not da_lam_xong_het([])


def test_cau_chan_lam() -> None:
    q = finance_gate.derive_finance_state(
        finance_gate.OrderFinanceFacts(
            order_id="o",
            selection_status="SELECTED",
            exec_status="authorized",
            execution_status=None,
            gia=(100,),
            ben_thu=("CLINIC",),
            footprints=(),
            visit_allocation_unknown=False,
            thu_truoc_khi_lam=True,
        )
    )
    assert (q.finance_state, q.duoc_lam) == ("DUE", False)
    assert finance_gate.cau_chan_lam(q) == finance_gate.CAU_CHUA_THU
    assert "hoàn" in finance_gate.cau_chan_lam(None)


def test_bang_hanh_trinh_noi_cho_tra_tien_khi_cua_lam_dong() -> None:
    from clinicai.services.bang_hanh_trinh_service import con_cho

    o = {
        "ten": "Siêu âm",
        "selection_status": "SELECTED",
        "execution_status": None,
        "routing_status": "UNASSIGNED",
        "da_tra": False,
    }
    assert con_cho([], [{**o, "duoc_lam": False}], 0) == ["Chờ trả tiền: Siêu âm"]
    assert con_cho([], [{**o, "duoc_lam": True}], 0) == [
        "Chờ xếp phòng (chưa thu): Siêu âm"
    ]
