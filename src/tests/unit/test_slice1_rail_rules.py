"""Slice 1 — luật thuần của rail chỉ định → kết quả → đọc lại → theo dõi.

Bốn contract (HANDOFF-NOW §3):
  * PERFORMED: làm xong là đạt.
  * VALID_RESULT: phải có kết quả hợp lệ; lấy mẫu / làm xong chưa đủ.
  * FOLLOW_UP: không giữ lượt chờ — không thành yêu cầu của vòng đọc.
  * NOT_PERFORMED: không tự đạt; bác sĩ phải quyết (miễn / chuyển theo dõi).
"""

from __future__ import annotations

import pytest

from clinicai.services import luot_kham_rules as rules


def _req(
    need: str = "PERFORMED",
    status: str = "open",
    exec_status: str = "performed",
    result: bool = False,
) -> rules.RequirementView:
    return rules.RequirementView("o1", need, status, exec_status, result)


# ── trạng thái một yêu cầu ─────────────────────────────────────────────────


def test_performed_la_dat_khi_chi_can_da_lam() -> None:
    assert rules.requirement_state(_req("PERFORMED")) == "satisfied"


def test_lay_mau_xong_chua_co_ket_qua_van_con_mo() -> None:
    assert rules.requirement_state(_req("VALID_RESULT", result=False)) == "open"
    assert rules.requirement_state(_req("VALID_RESULT", result=True)) == "satisfied"


def test_co_ket_qua_ma_chua_lam_xong_van_chua_dat() -> None:
    # Kết quả gắn vào chỉ định đang làm dở không đủ: chưa "performed".
    view = _req("VALID_RESULT", exec_status="in_progress", result=True)
    assert rules.requirement_state(view) == "open"


@pytest.mark.parametrize("exec_status", ["not_performed", "cancelled"])
@pytest.mark.parametrize("need", ["PERFORMED", "VALID_RESULT"])
def test_khong_thuc_hien_can_bac_si_quyet_khong_tu_dat(
    need: str, exec_status: str
) -> None:
    view = _req(need, exec_status=exec_status, result=True)
    assert rules.requirement_met(view) is False
    assert rules.requirement_state(view) == "needs_decision"


@pytest.mark.parametrize("status", ["waived", "follow_up"])
def test_bac_si_da_quyet_thi_giu_nguyen_quyet_dinh(status: str) -> None:
    view = _req("VALID_RESULT", status=status, exec_status="not_performed")
    assert rules.requirement_state(view) == status


# ── vòng đọc ───────────────────────────────────────────────────────────────


def test_vong_chua_san_sang_khi_con_cho_ket_qua() -> None:
    assert (
        rules.round_ready([_req("PERFORMED"), _req("VALID_RESULT", result=False)])
        is False
    )


def test_khong_thuc_hien_dua_khach_ve_bac_si_de_quyet() -> None:
    # Không kẹt mãi ở "đang thu": vòng sẵn sàng để bác sĩ gặp khách và quyết.
    views = [_req("PERFORMED"), _req("PERFORMED", exec_status="not_performed")]
    assert rules.round_ready(views) is True
    assert rules.can_quyet(views) == ["o1"]


def test_vong_da_quyet_het_thi_khong_con_viec_can_quyet() -> None:
    views = [_req("PERFORMED"), _req("PERFORMED", status="follow_up")]
    assert rules.round_ready(views) is True
    assert rules.can_quyet(views) == []


def test_tap_rong_van_khong_bao_gio_san_sang() -> None:
    assert rules.round_ready([]) is False
    assert rules.vong_khong_can_doc([]) is False


def test_mien_hoac_theo_doi_het_thi_khong_goi_khach_ve_doc() -> None:
    views = [_req(status="waived"), _req(status="follow_up")]
    assert rules.vong_khong_can_doc(views) is True
    # Còn một kết quả đã về thì bác sĩ phải đọc nó.
    assert rules.vong_khong_can_doc([*views, _req("PERFORMED")]) is False


def test_lam_tai_ban_kham_xong_thi_khong_can_doc() -> None:
    """Bác sĩ tự làm NGAY TẠI BÀN KHÁM (07/10/2026): xong là không có gì để
    đọc; chưa xong thì vòng vẫn chờ; dịch vụ làm ở phòng vẫn giữ vòng."""
    tai_bk = rules.RequirementView(
        "o2", "PERFORMED", "open", "performed", False, None, True
    )
    chua_xong = rules.RequirementView(
        "o3", "PERFORMED", "open", "in_progress", False, None, True
    )
    assert rules.vong_khong_can_doc([tai_bk]) is True
    assert rules.vong_khong_can_doc([tai_bk, _req(status="waived")]) is True
    assert rules.vong_khong_can_doc([chua_xong]) is False
    assert rules.vong_khong_can_doc([tai_bk, _req("PERFORMED")]) is False


# ── mức cần mặc định theo loại dịch vụ ─────────────────────────────────────


def test_lam_ben_ngoai_hoac_nhom_ket_qua_can_ket_qua() -> None:
    assert rules.need_mac_dinh(lam_ben_ngoai=True, flow_group="dich_vu") == (
        "VALID_RESULT"
    )
    assert rules.need_mac_dinh(lam_ben_ngoai=False, flow_group="ket_qua") == (
        "VALID_RESULT"
    )


def test_thu_thuat_sieu_am_chi_can_da_lam() -> None:
    assert rules.need_mac_dinh(lam_ben_ngoai=False, flow_group="dich_vu") == (
        "PERFORMED"
    )
    assert rules.need_mac_dinh(lam_ben_ngoai=None, flow_group=None) == "PERFORMED"


# ── kế hoạch sau phiên khám ────────────────────────────────────────────────


def test_chi_theo_doi_thi_khong_mo_vong_doc() -> None:
    assert rules.tach_ke_hoach([("o1", "FOLLOW_UP"), ("o2", "FOLLOW_UP")]) == (
        [],
        ["o1", "o2"],
    )


def test_tron_yeu_cau_va_theo_doi() -> None:
    assert rules.tach_ke_hoach(
        [("o1", "VALID_RESULT"), ("o2", "FOLLOW_UP"), ("o3", "PERFORMED")]
    ) == ([("o1", "VALID_RESULT"), ("o3", "PERFORMED")], ["o2"])


def test_muc_can_la_thi_bao_loi() -> None:
    with pytest.raises(ValueError):
        rules.tach_ke_hoach([("o1", "SOMETIME")])


# ── hạn theo dõi: đầu vào rác trả rỗng, không ném ─────────────────────────


@pytest.mark.parametrize("raw", [None, "", "abc", "2026-13-40", 12, {}, "  "])
def test_han_theo_doi_rac_tra_none(raw: object) -> None:
    assert rules.doc_han_theo_doi(raw) is None


def test_han_theo_doi_hop_le() -> None:
    assert str(rules.doc_han_theo_doi("2026-09-21")) == "2026-09-21"
