"""Luật thuần của luồng khám lát 1 — mỗi test là một câu trong contract v2 §3."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest

from clinicai.services import luot_kham_rules as rules

T0 = datetime(2026, 9, 11, 18, 0, tzinfo=timezone.utc)


# --- D1: đích sau check-in -------------------------------------------------


def test_chua_do_sinh_hieu_van_vao_bac_si_chinh() -> None:
    """Sinh hiệu KHÔNG chặn (luồng chuẩn bước 6, Tuyền chốt 23/09/2026)."""
    assert (
        rules.decide_route(
            vitals_recorded=False, plan_status="none", current_route=None
        )
        == rules.PRIMARY
    )


def test_luot_moi_do_xong_sinh_hieu_vao_bac_si() -> None:
    assert (
        rules.decide_route(vitals_recorded=True, plan_status="none", current_route=None)
        == rules.PRIMARY
    )


def test_ke_hoach_dang_xac_minh_thi_giu_nguyen() -> None:
    # T-P2: sinh hiệu đến trước, kế hoạch còn chờ → chưa quyết.
    assert (
        rules.decide_route(
            vitals_recorded=True, plan_status="pending", current_route=None
        )
        is None
    )


def test_ke_hoach_hop_le_di_thang_dich_vu() -> None:
    assert (
        rules.decide_route(
            vitals_recorded=True, plan_status="applied", current_route=None
        )
        == rules.SERVICES
    )


@pytest.mark.parametrize("status", ["rejected", "abandoned"])
def test_ke_hoach_bi_tu_choi_hoac_bo_qua_vao_bac_si(status: str) -> None:
    assert (
        rules.decide_route(vitals_recorded=True, plan_status=status, current_route=None)
        == rules.PRIMARY
    )


def test_dich_da_ghi_thi_khong_doi() -> None:
    # I10: kế hoạch hợp lệ đến muộn không kéo khách đã vào bác sĩ sang dịch vụ.
    assert (
        rules.decide_route(
            vitals_recorded=True, plan_status="applied", current_route=rules.PRIMARY
        )
        is None
    )


def test_trang_thai_ke_hoach_la_thi_no() -> None:
    with pytest.raises(ValueError):
        rules.decide_route(vitals_recorded=True, plan_status="???", current_route=None)


# --- D2: vòng đọc sẵn sàng -------------------------------------------------


def _req(
    need: str = "PERFORMED",
    status: str = "open",
    exec_status: str = "performed",
    result: bool = False,
) -> rules.RequirementView:
    return rules.RequirementView("o1", need, status, exec_status, result)


def test_tap_rong_khong_bao_gio_san_sang() -> None:
    # I5 / T-R7
    assert rules.round_ready([]) is False


def test_da_lam_la_du_khi_chi_can_da_lam() -> None:
    assert rules.round_ready([_req("PERFORMED")]) is True


def test_da_lam_chua_co_ket_qua_chua_du_khi_can_ket_qua() -> None:
    # T-R1: thực hiện và kết quả là hai trục.
    assert rules.round_ready([_req("VALID_RESULT", result=False)]) is False
    assert rules.round_ready([_req("VALID_RESULT", result=True)]) is True


def test_chua_lam_thi_chua_du() -> None:
    assert rules.round_ready([_req("PERFORMED", exec_status="in_progress")]) is False


def test_bac_si_mien_thi_tinh_la_du_ma_khong_doi_trang_thai_thuc_hien() -> None:
    # T-R4: miễn yêu cầu, chỉ định vẫn đang chờ kết quả.
    waived = _req(
        "VALID_RESULT", status="waived", exec_status="performed", result=False
    )
    assert rules.requirement_met(waived) is False
    assert rules.round_ready([waived]) is True


def test_mot_yeu_cau_thieu_la_ca_vong_chua_du() -> None:
    assert (
        rules.round_ready(
            [_req("PERFORMED"), _req("PERFORMED", exec_status="assigned")]
        )
        is False
    )


def test_chi_dinh_vua_bat_buoc_vua_bi_giu_toi_vong_do() -> None:
    # T-V4: SA → đọc → máu khai sai.
    assert rules.cyclic_orders(2, [("sa", None), ("mau", 2)]) == ["mau"]
    # T-V3: máu giữ tới vòng 2 nhưng là yêu cầu của vòng 3 → hợp lệ.
    assert rules.cyclic_orders(3, [("mau", 2)]) == []


# --- C7: điều phối ---------------------------------------------------------


def _block(**kw: object) -> str | None:
    base: dict[str, object] = dict(
        exec_status="authorized",
        source="VISIT_ORDER",
        authorized_by="bs",
        plan_applied=False,
        route_decision=rules.PRIMARY,
        vitals_recorded=True,
        hold_until_round=None,
        closed_rounds=set(),
    )
    base.update(kw)
    return rules.dispatch_block(**base)  # type: ignore[arg-type]


def test_chi_dinh_da_duyet_dieu_phoi_duoc() -> None:
    assert _block() is None


def test_nhap_cua_thu_ky_khong_dieu_phoi_duoc() -> None:
    # T-A3 / I1
    assert _block(exec_status="draft", authorized_by=None) == "NO_VALID_ORDER"


def test_da_lam_xong_khong_dieu_phoi_lai() -> None:
    assert _block(exec_status="performed") == "ORDER_NOT_DISPATCHABLE"


def test_chua_do_sinh_hieu_khong_con_chan_xep_phong() -> None:
    """Tuyền chốt 23/09/2026: sinh hiệu KHÔNG phải cửa chặn.

    Chưa đo vẫn đưa khách vào phòng được; chốt chặn còn lại là đích của lượt.
    """
    assert (
        _block(
            source="PRIOR_PLAN",
            plan_applied=True,
            route_decision=None,
            vitals_recorded=False,
        )
        == "ROUTE_NOT_DECIDED"
    )


def test_ke_hoach_khi_khach_da_vao_bac_si() -> None:
    assert (
        _block(source="PRIOR_PLAN", plan_applied=True, route_decision=rules.PRIMARY)
        == "PLAN_NOT_APPLIED"
    )


def test_bi_giu_toi_khi_vong_chua_dong() -> None:
    # T-V3
    assert _block(hold_until_round=2, closed_rounds=set()) == "HELD_UNTIL_ROUND"
    assert _block(hold_until_round=2, closed_rounds={2}) is None


# --- Hàng chờ --------------------------------------------------------------


def test_hang_cho_theo_luc_du_dieu_kien_khong_theo_gio_hen() -> None:
    # T-A14: A 18:10, B 18:12, C quay lại 18:15, D vào 18:16 → A, B, C, D.
    a = rules.QueueView("A", "waiting", T0 + timedelta(minutes=10), T0)
    b = rules.QueueView("B", "waiting", T0 + timedelta(minutes=12), T0)
    c = rules.QueueView(
        "C", "waiting", T0 + timedelta(minutes=15), T0 - timedelta(hours=1)
    )
    d = rules.QueueView(
        "D", "waiting", T0 + timedelta(minutes=16), T0 + timedelta(minutes=16)
    )
    assert [e.id for e in rules.order_queue([d, c, b, a])] == ["A", "B", "C", "D"]


def test_dang_phuc_vu_dung_dau_bi_chan_dung_cuoi_da_xong_bi_bo() -> None:
    serving = rules.QueueView("S", "serving", T0 + timedelta(minutes=20), T0)
    blocked = rules.QueueView("K", "blocked", None, T0)
    done = rules.QueueView("X", "done", T0, T0)
    waiting = rules.QueueView("W", "waiting", T0, T0)
    assert [e.id for e in rules.order_queue([blocked, done, waiting, serving])] == [
        "S",
        "W",
        "K",
    ]


def test_khach_dang_o_cho_khac_thi_vao_hang_o_trang_thai_cho_mo() -> None:
    assert rules.initial_queue_status(visit_busy=True) == "blocked"
    assert rules.initial_queue_status(visit_busy=False) == "waiting"


# --- Phiên khám ------------------------------------------------------------


def test_ket_qua_phien_theo_dung_loai() -> None:
    # T-C4
    assert rules.outcome_allowed("PRIMARY", "NO_SERVICES")
    assert rules.outcome_allowed("PRIMARY", "SERVICES")
    assert not rules.outcome_allowed("PRIMARY", "DONE")
    assert rules.outcome_allowed("REVIEW", "DONE")
    assert not rules.outcome_allowed("REVIEW", "NO_SERVICES")
    assert not rules.outcome_allowed("LA", "DONE")


# --- Sinh hiệu -------------------------------------------------------------


def test_sinh_hieu_hop_le() -> None:
    v, loi = rules.parse_vitals(
        {"systolic": "120", "diastolic": 80, "pulse": 72, "temperature": "36,8"}
    )
    assert loi is None and v is not None
    assert (v.systolic, v.diastolic, v.pulse, v.temperature) == (
        120,
        80,
        72,
        Decimal("36.8"),
    )


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "abc",
        [],
        {},
        {"systolic": 120},
        {"systolic": "", "diastolic": ""},
        {"systolic": "mười", "diastolic": 80},
        {"systolic": True, "diastolic": 80},
        {"systolic": 120, "diastolic": 80, "pulse": "nhanh"},
        {"systolic": 999, "diastolic": 80},
        {"systolic": 80, "diastolic": 120},
        {"systolic": 120.5, "diastolic": 80},
        {"systolic": "NaN", "diastolic": 80},
        {"systolic": 120, "diastolic": 80, "temperature": "Infinity"},
    ],
)
def test_sinh_hieu_rac_tra_cau_loi_khong_nem(raw: object) -> None:
    v, loi = rules.parse_vitals(raw)
    assert v is None
    assert isinstance(loi, str) and loi


def test_bmi_tu_tinh_khi_co_can_nang_va_chieu_cao() -> None:
    v, loi = rules.parse_vitals(
        {"systolic": 118, "diastolic": 76, "weight_kg": 54, "height_cm": 160}
    )
    assert loi is None and v is not None
    assert v.bmi == Decimal("21.1")


def test_bmi_client_gui_len_bi_bo_qua_luon_tu_tinh() -> None:
    """S0-3 (18/09/2026): BMI chỉ là số TÍNH RA, không ai nhập tay. Client gửi
    `bmi` (kể cả số sai như 99) thì backend bỏ qua và tính lại từ cân/cao."""
    v, loi = rules.parse_vitals(
        {"systolic": 118, "diastolic": 76, "weight_kg": 54, "height_cm": 160, "bmi": 99}
    )
    assert loi is None and v is not None and v.bmi == Decimal("21.1")


def test_bmi_client_gui_ma_thieu_can_hoac_cao_thi_rong() -> None:
    v, loi = rules.parse_vitals({"systolic": 118, "diastolic": 76, "bmi": 22})
    assert loi is None and v is not None and v.bmi is None


# --- Sinh hiệu: tên ô lỗi + nhắc chỉ số bất thường (27/09/2026, đợt 3) -----


@pytest.mark.parametrize(
    ("raw", "truong"),
    [
        (None, ()),
        ("abc", ()),
        ([], ()),
        ({}, ("systolic", "diastolic")),
        ({"systolic": 120}, ("diastolic",)),
        ({"systolic": "", "diastolic": ""}, ("systolic", "diastolic")),
        ({"systolic": "mười", "diastolic": 80}, ("systolic",)),
        ({"systolic": True, "diastolic": 80}, ("systolic",)),
        ({"systolic": 120, "diastolic": 80, "pulse": "nhanh"}, ("pulse",)),
        ({"systolic": 999, "diastolic": 80}, ("systolic",)),
        ({"systolic": 80, "diastolic": 120}, ("systolic", "diastolic")),
        ({"systolic": 120, "diastolic": 120}, ("systolic", "diastolic")),
        ({"systolic": 120.5, "diastolic": 80}, ("systolic",)),
        ({"systolic": "NaN", "diastolic": 80}, ("systolic",)),
        (
            {"systolic": 120, "diastolic": 80, "temperature": "Infinity"},
            ("temperature",),
        ),
        ({"systolic": 120, "diastolic": 80, "spo2": "98,5"}, ("spo2",)),
        ({"systolic": 120, "diastolic": 80, "weight_kg": {"x": 1}}, ("weight_kg",)),
    ],
)
def test_sinh_hieu_loi_noi_dung_o_nao(raw: object, truong: tuple[str, ...]) -> None:
    v, loi, ten_o = rules.parse_vitals_co_truong(raw)
    assert v is None
    assert isinstance(loi, str) and loi
    assert ten_o == truong
    # Vỏ hai phần tử nói cùng một câu.
    assert rules.parse_vitals(raw) == (None, loi)


def test_sinh_hieu_hop_le_khong_co_o_loi() -> None:
    v, loi, ten_o = rules.parse_vitals_co_truong(
        {"systolic": "120", "diastolic": 80, "temperature": "36,6"}
    )
    assert v is not None and loi is None and ten_o == ()
    assert v.temperature == Decimal("36.6")


def test_co_thai_thieu_can_cao_noi_dung_o() -> None:
    v = rules.Vitals(systolic=110, diastolic=70)
    assert rules.truong_thieu_khi_co_thai(v, co_thai=False) == ()
    assert rules.truong_thieu_khi_co_thai(v, co_thai=True) == ("height_cm", "weight_kg")
    du = rules.Vitals(
        systolic=110, diastolic=70, weight_kg=Decimal(55), height_cm=Decimal(158)
    )
    assert rules.truong_thieu_khi_co_thai(du, co_thai=True) == ()
    chi_can = rules.Vitals(systolic=110, diastolic=70, weight_kg=Decimal(55))
    assert rules.truong_thieu_khi_co_thai(chi_can, co_thai=True) == ("height_cm",)
    assert rules.thieu_sinh_hieu_khi_co_thai(chi_can, co_thai=True) == (
        "Khách đang có thai — sinh hiệu cần thêm chiều cao."
    )
    assert rules.thieu_sinh_hieu_khi_co_thai(v, co_thai=True) == (
        "Khách đang có thai — sinh hiệu cần thêm chiều cao và cân nặng."
    )


def _truong_canh_bao(**kw: Any) -> list[str]:
    v = rules.Vitals(**{"systolic": 118, "diastolic": 76, **kw})
    return [c["truong"] for c in rules.canh_bao_sinh_hieu(v)]


def test_canh_bao_binh_thuong_rong() -> None:
    assert (
        _truong_canh_bao(
            pulse=72, temperature=Decimal("36.6"), spo2=98, respiratory_rate=18
        )
        == []
    )


@pytest.mark.parametrize(
    ("kw", "truong"),
    [
        ({"systolic": 139, "diastolic": 89}, []),
        ({"systolic": 140, "diastolic": 80}, ["systolic"]),
        ({"systolic": 130, "diastolic": 90}, ["diastolic"]),
        ({"systolic": 160, "diastolic": 100}, ["systolic", "diastolic"]),
        ({"spo2": 94}, []),
        ({"spo2": 93}, ["spo2"]),
        ({"temperature": Decimal("37.9")}, []),
        ({"temperature": Decimal("38")}, ["temperature"]),
        ({"pulse": 50}, []),
        ({"pulse": 49}, ["pulse"]),
        ({"pulse": 120}, []),
        ({"pulse": 121}, ["pulse"]),
    ],
)
def test_canh_bao_nguong(kw: dict[str, Any], truong: list[str]) -> None:
    assert _truong_canh_bao(**kw) == truong


def test_canh_bao_co_cau_cho_nguoi_doc() -> None:
    v = rules.Vitals(systolic=150, diastolic=95, pulse=130, spo2=90)
    ds = rules.canh_bao_sinh_hieu(v)
    assert all(isinstance(c["cau"], str) and c["cau"] for c in ds)
    assert "150" in ds[0]["cau"] and "nhanh" in ds[2]["cau"]


@pytest.mark.parametrize("rac", [None, "abc", {}, [], 120, {"systolic": 200}])
def test_canh_bao_dau_vao_rac_tra_rong(rac: object) -> None:
    assert rules.canh_bao_sinh_hieu(rac) == []


def test_canh_bao_khong_chan_luu() -> None:
    """Chỉ số bất thường vẫn ĐỌC ĐƯỢC — nhắc, không chặn (Tuyền 15/09)."""
    v, loi, _ = rules.parse_vitals_co_truong(
        {
            "systolic": 180,
            "diastolic": 110,
            "spo2": 88,
            "temperature": "39,5",
            "pulse": 140,
        }
    )
    assert loi is None and v is not None
    assert len(rules.canh_bao_sinh_hieu(v)) == 5


# --- Đổi phòng dịch vụ (23/09/2026) ----------------------------------------


@pytest.mark.parametrize(
    ("chon", "thuc_hien", "cu", "doi_tac", "duoc"),
    [
        ("SELECTED", "PENDING", "assigned", False, True),
        ("SELECTED", None, "ordered", False, True),
        ("PENDING", "PENDING", "ordered", False, False),  # khách chưa chọn
        ("SELECTED", "IN_PROGRESS", "assigned", False, False),  # đang làm
        ("SELECTED", "COMPLETED", "performed", False, False),  # xong rồi
        ("SELECTED", "PENDING", "assigned", True, False),  # đối tác làm
    ],
)
def test_doi_phong_duoc(
    chon: str, thuc_hien: str | None, cu: str, doi_tac: bool, duoc: bool
) -> None:
    assert (
        rules.doi_phong_duoc(
            selection_status=chon,
            execution_status=thuc_hien,
            exec_status=cu,
            doi_tac=doi_tac,
        )
        is duoc
    )


# --- Màn đo sinh hiệu (27/09/2026 tối): phút chờ + chờ lâu -------------------
def test_phut_cho_va_cho_lau() -> None:
    from datetime import datetime, timedelta, timezone

    vn = timezone(timedelta(hours=7))
    ci = datetime(2026, 9, 27, 8, 0, tzinfo=vn)
    assert rules.phut_cho(ci, ci + timedelta(minutes=19, seconds=59)) == 19
    assert rules.cho_do_lau(19) is False
    assert rules.cho_do_lau(rules.phut_cho(ci, ci + timedelta(minutes=20))) is True
    # Rác / thiếu / giờ ngược / lệch múi giờ → None, không ném.
    assert rules.phut_cho(None, ci) is None
    assert rules.phut_cho("08:00", ci) is None
    assert rules.phut_cho(ci + timedelta(minutes=5), ci) is None
    assert rules.phut_cho(datetime(2026, 9, 27, 8, 0), ci) is None
    assert rules.cho_do_lau(None) is False
