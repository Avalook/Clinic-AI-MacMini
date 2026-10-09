"""Bảy phiếu khám — khung, khoá ổn định, kiểm dữ liệu, mang sang. Không cần DB.

Những bài ở đây canh ba lời hứa của gói phiếu khám:

1. Khung là của NGUỒN: đủ từng khoá, không thừa, không trùng — kể cả khi so
   xuyên bảy phiếu.
2. Khoá là định danh, nhãn chỉ để đọc: gửi chữ "Tuyến giáp" thay mã
   `nt_endo_hist_2` là bị chặn.
3. Khung chạy trên engine sẵn có mà engine không phải đổi một dòng.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from clinicai.core.exceptions import ValidationError
from clinicai.phieu_kham.che_do import CHE_DO, doi_ghi_duoc, ghi_duoc
from clinicai.phieu_kham.khung import (
    FORM_IDS,
    cac_o,
    dinh_nghia,
    doc_ngay,
    kiem_du_lieu,
    kiem_khung,
    tat_ca,
    tham_chieu_nguon,
)
from clinicai.phieu_kham.mang_sang import (
    TRUONG_HANH_CHINH,
    TRUONG_SINH_HIEU,
    dung_hanh_chinh,
    dung_sinh_hieu,
)
from clinicai.services.form_engine_service import _con_trong, _mac_dinh_tu_khung

GOC = Path(__file__).resolve().parents[3]

#: BA CON SỐ KHÁC NHAU — đếm bằng máy từ `ClinicAI-7-phieu-v5-final-review.html`
#: ngày 23/09. Đổi số nào = nguồn đổi: chạy lại `scripts/phieu-kham/trich-tu-html.py`,
#: không sửa tay JSON.
#:
#:   so_khoa        KHOÁ ỔN ĐỊNH của phiếu (ô + từng checkbox) — tổng 450.
#:   so_data_field  khoá lấy từ thuộc tính `data-field-key` — tổng 418 (con số
#:                  "418 controls" đếm thẳng trên HTML).
#:   so_chi_name    khoá lấy từ `name` vì nguồn không gắn `data-field-key` —
#:                  tổng 32: 18 ô tinh dịch đồ + 2 ô mục E × 7 phiếu.
#:   so_o           ô trên khung sau khi gom mỗi nhóm checkbox thành một ô
#:                  `nhieu_chon` — tổng 343.
DEM: dict[str, dict[str, int]] = {
    "NT": {"so_khoa": 86, "so_data_field": 84, "so_chi_name": 2, "so_o": 57},
    "HMVS": {"so_khoa": 183, "so_data_field": 163, "so_chi_name": 20, "so_o": 122},
    "PK": {"so_khoa": 73, "so_data_field": 71, "so_chi_name": 2, "so_o": 69},
    "SK": {"so_khoa": 54, "so_data_field": 52, "so_chi_name": 2, "so_o": 41},
    "NK": {"so_khoa": 25, "so_data_field": 23, "so_chi_name": 2, "so_o": 25},
    "THU_THUAT": {"so_khoa": 15, "so_data_field": 13, "so_chi_name": 2, "so_o": 15},
    "SAN_CHAU": {"so_khoa": 14, "so_data_field": 12, "so_chi_name": 2, "so_o": 14},
}


def _o_nguon(dn: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Ô CỦA NGUỒN — bỏ ô thêm sau khi trích (`them_sau_nguon`, bản v2 27/09)."""
    return {m: b for m, b in cac_o(dn["khung"]).items() if not b.get("them_sau_nguon")}


def _moi_khoa(dn: dict[str, Any], *, chi_nguon: bool = True) -> list[str]:
    out: list[str] = []
    for b in (_o_nguon(dn) if chi_nguon else cac_o(dn["khung"])).values():
        if b["kieu"] in {"chon", "nhieu_chon"}:
            out.extend(o["ma"] for o in b["lua_chon"])
        else:
            out.append(b["ma"])
    return out


def _khoa_chi_name(dn: dict[str, Any]) -> list[str]:
    return [b["ma"] for b in cac_o(dn["khung"]).values() if b.get("khoa_tu") == "name"]


# ── 1. Khung là của nguồn ───────────────────────────────────────────────────
def test_du_bay_phieu_dung_thu_tu_da_chot() -> None:
    assert FORM_IDS == ("NT", "HMVS", "PK", "SK", "NK", "THU_THUAT", "SAN_CHAU")
    assert [d["form_id"] for d in tat_ca()] == list(FORM_IDS)


@pytest.mark.parametrize("form_id", FORM_IDS)
def test_moi_phieu_dem_dung_tung_con_so(form_id: str) -> None:
    dn = dinh_nghia(form_id)
    khoa, chi_name = _moi_khoa(dn), _khoa_chi_name(dn)
    assert {
        "so_khoa": len(khoa),
        "so_data_field": len(khoa) - len(chi_name),
        "so_chi_name": len(chi_name),
        "so_o": len(_o_nguon(dn)),
    } == DEM[form_id]


def test_450_khoa_bang_418_data_field_cong_32_chi_name() -> None:
    tong = {k: sum(d[k] for d in DEM.values()) for k in DEM["NT"]}
    assert tong == {
        "so_khoa": 450,
        "so_data_field": 418,
        "so_chi_name": 32,
        "so_o": 343,
    }


def test_32_khoa_chi_name_la_dung_hai_loai_da_biet() -> None:
    """Không có ô nào khác "lọt" khỏi `data-field-key` mà không ai giải thích."""
    chi_name = [k for d in tat_ca() for k in _khoa_chi_name(d)]
    tinh_dich = [k for k in chi_name if re.fullmatch(r"hmvs_semen_\d+_[12]", k)]
    muc_e = [k for k in chi_name if k.endswith(("_treatment_other", "_treatment_note"))]
    assert len(tinh_dich) == 18 and len(muc_e) == 14
    assert sorted(tinh_dich + muc_e) == sorted(chi_name)


def test_khoa_khong_trung_xuyen_bay_phieu() -> None:
    """Một khoá chỉ có một nghĩa — gộp dữ liệu bảy phiếu cũng không va nhau."""
    tat = [k for d in tat_ca() for k in _moi_khoa(d, chi_nguon=False)]
    trung = sorted({k for k in tat if tat.count(k) > 1})
    assert trung == []


def test_moi_phieu_cung_mot_nguon() -> None:
    sha = {d["nguon"]["sha256"] for d in tat_ca()}
    assert len(sha) == 1
    assert tham_chieu_nguon()["nguon_sha256"] in sha


@pytest.mark.parametrize("form_id", FORM_IDS)
def test_bo_cuc_muc_a_toi_g(form_id: str) -> None:
    khung = dinh_nghia(form_id)["khung"]
    assert [m["ma"] for m in khung] == ["HANH_CHINH", "A", "B", "C", "D", "E", "F", "G"]
    loai = {m["ma"]: m.get("lien_ket", {}).get("loai") for m in khung}
    assert loai == {
        "HANH_CHINH": "mang_sang",
        "A": "mang_sang",
        "B": None,
        "C": "chi_dinh_cls",
        "D": None,
        "E": "don_thuoc",
        "F": "chi_dinh_thu_thuat",
        "G": None,
    }


@pytest.mark.parametrize("form_id", FORM_IDS)
def test_muc_chi_dinh_khong_giu_ban_sao(form_id: str) -> None:
    """C và F là của service_order: phiếu không có ô nào chép danh sách chỉ định."""
    khung = {m["ma"]: m for m in dinh_nghia(form_id)["khung"]}
    assert khung["C"]["block"] == [] and khung["F"]["block"] == []
    assert khung["HANH_CHINH"]["block"] == []


def test_dai_hanh_chinh_dung_khoa_bind_cua_nguon() -> None:
    truong = dinh_nghia("NT")["khung"][0]["lien_ket"]["truong"]
    assert truong == [k for k, _ in TRUONG_HANH_CHINH] + [
        k for k, _ in TRUONG_SINH_HIEU
    ]


def test_dinh_nghia_khong_tu_quyet_cach_chot() -> None:
    """Chốt hồ sơ là việc của clinical shell — định nghĩa không mang khoá nào về nó."""
    for d in tat_ca():
        assert set(d) == {"form_id", "ten", "nhom", "nguon", "khung"}


def test_nhom_checkbox_giu_khoa_nguon_lam_ma() -> None:
    o = cac_o(dinh_nghia("NT")["khung"])["nt_endo_hist"]
    assert o["kieu"] == "nhieu_chon"
    assert [x["ma"] for x in o["lua_chon"]] == [
        f"nt_endo_hist_{i}" for i in range(1, 11)
    ]
    assert o["lua_chon"][1]["ten"] == "Tuyến giáp"


def test_bang_tinh_dich_do_hai_lan_la_hai_o() -> None:
    o = cac_o(dinh_nghia("HMVS")["khung"])
    assert o["hmvs_semen_3_1"]["cot"] == "Kết quả lần 1"
    assert o["hmvs_semen_3_2"]["cot"] == "Kết quả lần 2"
    assert o["hmvs_semen_3_1"]["hang"] == o["hmvs_semen_3_2"]["hang"]
    assert o["hmvs_semen_3_1"]["bang"]["cot"] == ["Kết quả lần 1", "Kết quả lần 2"]


def test_nhan_tu_dat_duoc_danh_dau() -> None:
    """Nhãn không lấy từ nguồn phải tự khai ra — để còn đối chiếu lại."""
    tu_dat = {
        b["ma"]
        for d in tat_ca()
        for b in cac_o(d["khung"]).values()
        if b.get("ten_tu_dat")
    }
    assert tu_dat == {
        "nt_mht_type",
        "nt_follow_tests",
        "hmvs_follow_tests",
        "pk_follow_tests",
    }


# ── 2. Khung chạy trên engine sẵn có ────────────────────────────────────────
@pytest.mark.parametrize("form_id", FORM_IDS)
def test_engine_dem_o_trong_bo_qua_muc_lien_ket(form_id: str) -> None:
    khung = dinh_nghia(form_id)["khung"]
    assert len(_con_trong(khung, {})) == len(cac_o(khung))
    # Nguồn chỉ có gợi ý (placeholder), không có câu điền sẵn — engine không
    # được đánh dấu ô nào là TEMPLATE_DEFAULT.
    assert _mac_dinh_tu_khung(khung) == {}


def test_nhieu_chon_rong_la_o_trong_voi_engine() -> None:
    khung = dinh_nghia("NT")["khung"]
    trong = _con_trong(khung, {"nt_endo_hist": {"gia_tri": [], "nguon": "USER"}})
    assert "3. Tiền sử nội tiết" in trong


def test_kiem_khung_bat_khoa_trung_va_kieu_la() -> None:
    muc = {"ma": "B", "ten": "B", "block": [{"ma": "x_a", "ten": "A", "kieu": "text"}]}
    with pytest.raises(ValidationError, match="trùng"):
        kiem_khung([muc, {**muc, "ma": "D"}], form_id="NT")
    with pytest.raises(ValidationError, match="kiểu lạ"):
        kiem_khung(
            [
                {
                    "ma": "B",
                    "ten": "B",
                    "block": [{"ma": "x", "ten": "X", "kieu": "anh"}],
                }
            ],
            form_id="NT",
        )
    with pytest.raises(ValidationError, match="mục chỉ định"):
        kiem_khung(
            [
                {
                    "ma": "C",
                    "ten": "C",
                    "lien_ket": {"loai": "chi_dinh_cls"},
                    "block": [{"ma": "x", "ten": "X", "kieu": "text"}],
                }
            ],
            form_id="NT",
        )


def test_kiem_khung_bat_ma_lua_chon_la_chu() -> None:
    with pytest.raises(ValidationError, match="mã lựa chọn lạ"):
        kiem_khung(
            [
                {
                    "ma": "B",
                    "ten": "B",
                    "block": [
                        {
                            "ma": "x",
                            "ten": "X",
                            "kieu": "nhieu_chon",
                            "lua_chon": [{"ma": "Tuyến giáp", "ten": "Tuyến giáp"}],
                        }
                    ],
                }
            ],
            form_id="NT",
        )


# ── 3. Kiểm dữ liệu một lần lưu ─────────────────────────────────────────────
KHUNG_NT = dinh_nghia("NT")["khung"]


def _o(v: object, nguon: str = "USER") -> dict[str, Any]:
    return {"gia_tri": v, "nguon": nguon}


def test_khoa_la_bi_chan() -> None:
    with pytest.raises(ValidationError, match="không có trong phiếu"):
        kiem_du_lieu(KHUNG_NT, {"ly_do": _o("đau bụng")})  # khoá của phiếu CŨ


def test_khoa_cua_phieu_khac_bi_chan() -> None:
    with pytest.raises(ValidationError, match="không có trong phiếu"):
        kiem_du_lieu(KHUNG_NT, {"pk_reason": _o("đau bụng")})


def test_gui_chu_thay_ma_lua_chon_bi_chan() -> None:
    with pytest.raises(ValidationError, match="gửi MÃ"):
        kiem_du_lieu(KHUNG_NT, {"nt_endo_hist": _o(["Tuyến giáp"])})


def test_nhieu_chon_giu_thu_tu_khung_bo_trung() -> None:
    sach, cb = kiem_du_lieu(
        KHUNG_NT,
        {"nt_endo_hist": _o(["nt_endo_hist_4", "nt_endo_hist_2", "nt_endo_hist_4"])},
    )
    assert sach["nt_endo_hist"]["gia_tri"] == ["nt_endo_hist_2", "nt_endo_hist_4"]
    assert cb == []


def test_nguon_la_bi_chan() -> None:
    with pytest.raises(ValidationError, match="nguồn lạ"):
        kiem_du_lieu(KHUNG_NT, {"nt_ly_do": _o("x", "TU_DAU_RA")})


def test_hinh_sai_bi_chan() -> None:
    with pytest.raises(ValidationError, match="gia_tri"):
        kiem_du_lieu(KHUNG_NT, {"nt_ly_do": "đau bụng"})
    with pytest.raises(ValidationError):
        kiem_du_lieu(KHUNG_NT, ["nt_ly_do"])
    with pytest.raises(ValidationError, match="chữ hoặc số"):
        kiem_du_lieu(KHUNG_NT, {"nt_ly_do": _o(True)})
    with pytest.raises(ValidationError, match="dài quá"):
        kiem_du_lieu(KHUNG_NT, {"nt_para": _o("x" * 2001)})


@pytest.mark.parametrize("rac", ["abc", "12 tuổi", "nan", "inf", "1e999"])
def test_so_rac_thanh_rong_kem_canh_bao_khong_nem(rac: str) -> None:
    sach, cb = kiem_du_lieu(KHUNG_NT, {"nt_menarche": _o(rac)})
    assert sach["nt_menarche"]["gia_tri"] == ""
    assert cb and cb[0]["ma"] == "nt_menarche"


@pytest.mark.parametrize(
    ("vao", "ra"),
    [("13", "13"), (13, "13"), ("12,5", "12.5"), (" 28 ", "28"), ("", "")],
)
def test_so_chuan_hoa(vao: object, ra: str) -> None:
    sach, cb = kiem_du_lieu(KHUNG_NT, {"nt_cycle": _o(vao)})
    assert sach["nt_cycle"]["gia_tri"] == ra and cb == []


@pytest.mark.parametrize(
    "rac", ["32/13/2026", "2026-02-30", "hôm qua", "20261010", "0"]
)
def test_ngay_rac_thanh_rong_kem_canh_bao_khong_nem(rac: str) -> None:
    sach, cb = kiem_du_lieu(KHUNG_NT, {"nt_follow_date": _o(rac)})
    assert sach["nt_follow_date"]["gia_tri"] == ""
    assert cb and cb[0]["ma"] == "nt_follow_date"


def test_ngay_hai_dang_ve_iso() -> None:
    for vao in ("2026-10-15", "15/10/2026"):
        sach, _ = kiem_du_lieu(KHUNG_NT, {"nt_follow_date": _o(vao)})
        assert sach["nt_follow_date"]["gia_tri"] == "2026-10-15"
    assert doc_ngay(None) is None and doc_ngay(20261015) is None
    assert doc_ngay("2026-10-15") == date(2026, 10, 15)


def test_none_la_rong_dung_kieu() -> None:
    sach, _ = kiem_du_lieu(KHUNG_NT, {"nt_ly_do": _o(None), "nt_endo_hist": _o(None)})
    assert sach["nt_ly_do"]["gia_tri"] == "" and sach["nt_endo_hist"]["gia_tri"] == []


# ── 4. Mang sang ────────────────────────────────────────────────────────────
def test_chua_do_sinh_hieu_thi_de_trong_khong_loi() -> None:
    sh = dung_sinh_hieu(None)
    assert list(sh) == [k for k, _ in TRUONG_SINH_HIEU]
    assert set(sh.values()) == {None}


def test_sinh_hieu_mot_lan_do() -> None:
    sh = dung_sinh_hieu(
        {
            "systolic": 120,
            "diastolic": 80,
            "pulse": 76,
            "temperature": Decimal("36.8"),
            "weight_kg": Decimal("52.0"),
            "height_cm": Decimal("158.0"),
            "spo2": 98,
            "bmi": None,
            "respiratory_rate": 18,
            "pain_score": 0,
        }
    )
    assert sh["vitals.blood_pressure"] == "120/80"
    assert sh["vitals.temperature"] == 36.8 and sh["vitals.weight"] == 52
    # BMI chưa lưu thì để trống — không tự tính ra một con số không ai đo.
    assert sh["vitals.bmi"] is None
    assert sh["vitals.pain_score"] == 0


def test_hanh_chinh_ngay_kham_theo_gio_phong_kham() -> None:
    hc = dung_hanh_chinh(
        {
            "full_name": "Nguyễn Thị A",
            "patient_code": "BN001",
            "birth_year": None,
            "date_of_birth": date(1990, 5, 1),
        },
        vao_luc=datetime(2026, 9, 23, 17, 30, tzinfo=UTC),  # 00:30 ngày 24 ở VN
    )
    assert hc == {
        "patient.name": "Nguyễn Thị A",
        "patient.birth_year": 1990,
        "patient.code": "BN001",
        "encounter.date": "2026-09-24",
    }
    assert set(dung_hanh_chinh(None, vao_luc=None).values()) == {None}


# ── 5. Tham chiếu nguồn: nhãn chờ ánh xạ, KHÔNG phải định danh ──────────────
def _ma_mau_ket_qua() -> set[str]:
    sql = (GOC / "supabase/migrations/20260923000004_mau_ket_qua.sql").read_text()
    return {f"KQ_{m}" for m in re.findall(r"\('([A-Z0-9_]+)', '", sql)}


def test_tham_chieu_khong_tu_dien_ma_that() -> None:
    tc = tham_chieu_nguon()
    assert all(m["service_code"] is None for g in tc["chi_dinh_cls"] for m in g["muc"])
    assert all(x["service_code"] is None for x in tc["thu_thuat"])
    assert all(x["drug_catalog_id"] is None for x in tc["mau_thuoc"])
    assert len(tc["mau_thuoc"]) == 73
    # 27/09/2026 (đợt 3): xếp theo bản giao diện mẫu — soi CTC (7) / soi âm hộ
    # (8) sang CLS, bỏ dòng tiêu đề "• Laser" (13), ghế ĐTT yếu/đau cơ (16/17)
    # sang khối điều trị.
    assert [x["ma"] for x in tc["thu_thuat"]] == [
        *(f"procedure_{i}" for i in (1, 2, 3, 4, 5, 6, 9, 10)),
        "procedure_16",
        "procedure_17",
        *(f"procedure_{i}" for i in (11, 12, 14, 15)),
    ]
    assert len({x["ma"] for x in tc["thu_thuat"]}) == len(tc["thu_thuat"])


# ── 5b. Danh mục chỉ định theo bản giao diện mẫu (27/09/2026, đợt 3) ────────
def _moi_nhan(tc: dict[str, Any]) -> list[str]:
    return [m["nhan"] for g in tc["chi_dinh_cls"] for m in g["muc"]] + [
        x["nhan"] for x in tc["thu_thuat"]
    ]


def test_nhan_danh_muc_sach_khong_dau_giay() -> None:
    """Nhãn vừa hiện cho bác sĩ vừa là khoá ánh xạ — không còn "*", "•", "-"."""
    tc = tham_chieu_nguon()
    ban = [n for n in _moi_nhan(tc) if n != n.strip() or n[:1] in "*•-"]
    assert ban == []
    nhom = [g["nhom"] for g in tc["chi_dinh_cls"]] + [
        x["nhom"] for x in tc["thu_thuat"]
    ]
    assert all(n and n[:1] not in "*•-" for n in nhom)


def test_moi_nhan_co_anh_xa_va_moi_anh_xa_co_nhan() -> None:
    from clinicai.phieu_kham import anh_xa_danh_muc as ax

    tc = tham_chieu_nguon()
    nhan_cls = [m["nhan"] for g in tc["chi_dinh_cls"] for m in g["muc"]]
    ma_tt = [x["ma"] for x in tc["thu_thuat"]]
    assert [n for n in nhan_cls if n not in ax.CLS] == []
    assert [m for m in ma_tt if m not in ax.THU_THUAT] == []
    # Không khoá ánh xạ nào mồ côi (đổi nhãn quên đổi khoá = dòng mất mã).
    assert set(ax.CLS) == set(nhan_cls)
    assert set(ax.THU_THUAT) == set(ma_tt)
    # Một dịch vụ chỉ ở MỘT khối — khối 2 hay khối 3 suy ra từ file này.
    ma_cls = {ax.CLS[n].ma for n in nhan_cls}
    ma_thu = {ax.THU_THUAT[m].ma for m in ma_tt}
    assert ma_cls.isdisjoint(ma_thu)


def test_nhom_theo_ban_giao_dien_mau() -> None:
    from clinicai.phieu_kham import anh_xa_danh_muc as ax

    tc = tham_chieu_nguon()
    cls = {g["nhom"]: [m["nhan"] for m in g["muc"]] for g in tc["chi_dinh_cls"]}
    assert cls["Soi & xét nghiệm dịch âm đạo"] == [
        "Soi cổ tử cung",
        "Soi âm hộ",
        "HPV",
        "ThinPrep",
        "PCR 12 loại VK",
    ]
    assert cls["Sàn chậu — đánh giá"] == [
        "Đo cơ lực âm đạo bằng máy (sàng lọc)",
        "Khám sàn chậu",
    ]
    thu: dict[str, list[str]] = {}
    for x in tc["thu_thuat"]:
        thu.setdefault(x["nhom"], []).append(x["nhan"])
    assert list(thu) == [
        "Thủ thuật",
        "Sàn chậu — trải nghiệm 5 phút ghế ĐTT",
        "Sàn chậu — định hướng điều trị",
    ]
    assert "Nong bao quy đầu ÂV" in thu["Thủ thuật"]
    assert "Tách bao quy đầu ÂV" in thu["Thủ thuật"]
    assert thu["Sàn chậu — trải nghiệm 5 phút ghế ĐTT"] == ["Yếu cơ", "Đau cơ"]
    assert "Biofeedback" in thu["Sàn chậu — định hướng điều trị"]
    # B5: Soi âm hộ ở khối 2 (CLS) → thấy khi chỉ định, kết quả hiện ở khối 2.
    ma_cls = {ax.CLS[m["nhan"]].ma for g in tc["chi_dinh_cls"] for m in g["muc"]}
    assert {"CLS_SOI_AM_HO", "CLS_SOI_CO_TU_CUNG"} <= ma_cls
    assert {"CLS_DO_CO_LUC_AM_DAO", "CLS_KHAM_SAN_CHAU"} <= ma_cls


def test_bo_hai_dong_tieu_de_khong_o_tick() -> None:
    """ "*XN dịch âm đạo" và "• Laser" là tiêu đề trên giấy — không liệt kê."""
    from clinicai.phieu_kham import anh_xa_danh_muc as ax

    tc = tham_chieu_nguon()
    ma = {d.ma for d in ax.CLS.values()} | {d.ma for d in ax.THU_THUAT.values()}
    assert ax.KHONG_LIET_KE == {"CLS_XET_NGHIEM_DICH_AM_DAO", "CLS_LASER"}
    assert ma.isdisjoint(ax.KHONG_LIET_KE)
    nhan = " | ".join(_moi_nhan(tc))
    assert "XN dịch âm đạo" not in nhan
    assert "Laser" in nhan  # Laser trẻ hoá, Laser ST/SSD vẫn còn
    assert "procedure_13" not in {x["ma"] for x in tc["thu_thuat"]}


def test_mau_goi_y_chi_soi_am_ho_dung_mau_soi_am_ho() -> None:
    """B6a: tick "Đo cơ lực" từng mở mẫu Soi âm hộ. Đúng bản mẫu: chỉ Soi âm
    hộ (SP000163) dùng mẫu SOI_AM_HO; còn lại về mẫu CHUNG (không gợi ý)."""
    from clinicai.phieu_kham import mau_goi_y

    mau_goi_y._goi_y_theo_ma.cache_clear()
    assert mau_goi_y.ma_mau_goi_y("CLS_SOI_AM_HO") == "SOI_AM_HO"
    for ma in (
        "CLS_DO_CO_LUC_AM_DAO",
        "CLS_KHAM_SAN_CHAU",
        "CLS_NONG_BAO_QUY_DAU_AV",
        "CLS_TACH_BAO_QUY_DAU_AV",
    ):
        assert mau_goi_y.ma_mau_goi_y(ma) is None, ma
    assert [
        ma for ma, mau in mau_goi_y._goi_y_theo_ma().items() if mau == "SOI_AM_HO"
    ] == ["CLS_SOI_AM_HO"]
    # Mã rác / rỗng → không gợi ý, không ném.
    assert mau_goi_y.ma_mau_goi_y("") is None
    assert mau_goi_y.ma_mau_goi_y("KHONG_CO") is None


def test_mau_soi_am_ho_khong_con_ten_muc_giu_cho() -> None:
    """B6b: "(không có tiêu đề mục)" không được hiện ra — đổi TÊN, giữ `ma`."""
    import json

    v3 = json.loads(
        (GOC / "src/clinicai/phieu_kham/mau_ket_qua_v3.json").read_text(
            encoding="utf-8"
        )
    )["mau"]
    ten_muc = [m["ten"] for mau in v3.values() for m in mau["khung"]]
    assert not [t for t in ten_muc if "không có tiêu đề" in t or not t.strip()]
    khung = v3["SOI_AM_HO"]["khung"]
    assert [(m["ma"], m["ten"]) for m in khung] == [
        ("o", "Kết quả soi"),
        ("de_nghi", "Đề nghị"),
    ]
    assert [o["ma"] for o in khung[0]["block"]] == [
        "quy_dau_am_vat",
        "tien_dinh_am_ho",
        "test_ran",
        "co_luc_am_dao_theo_oxford_cai_tien",
    ]
    # Migration mới mang ĐÚNG khung của JSON (một nguồn, hai bản chép) — trừ
    # hai cờ ô thêm SAU nó (`tuy_chon`/`don_vi`, migration 20261009300000).
    truoc_0910 = [
        {
            **m,
            "block": [
                {k: v for k, v in o.items() if k not in ("tuy_chon", "don_vi")}
                for o in m["block"]
            ],
        }
        for m in khung
    ]
    sql = (
        GOC / "supabase/migrations/20260928000002_ten_muc_mau_soi_am_ho.sql"
    ).read_text(encoding="utf-8")
    assert sql.count(json.dumps(truoc_0910, ensure_ascii=False)) == 2


def test_mau_ket_qua_nguon_tro_dung_18_mau_engine() -> None:
    tc = tham_chieu_nguon()
    tro = {
        m["form_id_ket_qua"]
        for g in tc["chi_dinh_cls"]
        for m in g["muc"]
        if m["form_id_ket_qua"]
    } | {x["form_id_ket_qua"] for x in tc["thu_thuat"] if x["form_id_ket_qua"]}
    co = _ma_mau_ket_qua()
    assert len(co) == 18
    assert tro and tro <= co


# ── 6. Chế độ phiếu: nhận từ clinical shell, đóng khi nghi ngờ ─────────────
def test_che_do_ba_gia_tri() -> None:
    assert CHE_DO == {"editable", "finalized_locked", "amendment_mode"}
    assert ghi_duoc("editable") and ghi_duoc("amendment_mode")
    assert not ghi_duoc("finalized_locked")
    with pytest.raises(ValidationError, match="chỉ còn đọc"):
        doi_ghi_duoc("finalized_locked")


@pytest.mark.parametrize("la", [None, "", "EDITABLE", "locked", 1, True])
def test_che_do_la_hoac_thieu_thi_chan(la: object) -> None:
    with pytest.raises(ValidationError, match="không hợp lệ"):
        ghi_duoc(la)
