"""LUẬT CẮM của bản khai lego — khối không tự ghi bảng của khối khác (21/10/2026).

`modules.py` khai bảng nào khối nào giữ (`bang`) và tệp nào thuộc khối nào
(`TEP_CUA_KHOI`). Bài này đọc MỌI câu SQL ghi bảng (INSERT / UPDATE / DELETE)
trong src/clinicai theo cú pháp rồi kiểm:

  1. bảng bị ghi phải có chủ, hoặc nằm trong `BANG_KY_THUAT`;
  2. tệp ghi bảng của một khối phải khai thuộc đúng một khối;
  3. tệp của khối A ghi bảng của khối B → phải có trong sổ nợ `NO_GHI_CHEO`.

Sổ nợ là KHOÁ BÁNH CÓC: chỗ ghi chéo MỚI → đỏ; chỗ cũ đã sửa mà còn trong sổ →
đỏ (gạch đi). Sổ chỉ được ngắn đi. Đỏ vì chỗ mới thì sửa theo thứ tự:
  * gọi LỆNH của khối chủ bảng, hoặc phát sự kiện để khối ấy tự nghe;
  * tệp thật ra thuộc khối chủ bảng → sửa `TEP_CUA_KHOI`;
  * không tránh được (hoàn tác trong một giao dịch…) → thêm vào sổ, nhãn
    DUNG_THIET_KE, kèm lý do trong PR.

Nhãn của sổ (đợt kiểm docs/kiem-tra-su-kien-lego-2110/BAO-CAO.md):
  VI_PHAM        đã xác nhận khi đọc code — cần chuyển sang lệnh / sự kiện;
  DUNG_THIET_KE  giữ có chủ ý;
  XEM_LAI_KHOI   có thể là khai khối của tệp chưa đúng;
  CHUA_XET       chưa ai đọc — mới lộ ra khi bảng có chủ.

Điểm mù: SQL dựng tên bảng lúc chạy; bảng ngoài schema public; hàm SQL trong
database (trigger) — những chỗ ấy không quét ở đây.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

from clinicai.modules import BANG_KY_THUAT, MODULE, TEP_CUA_KHOI, khoi_cua_tep

GOC = Path(__file__).resolve().parents[2] / "clinicai"

_GHI = re.compile(
    r"\b(?:INSERT\s+INTO\s+(?:public\.)?(?P<i>[a-z_][a-z0-9_]*)"
    r"|(?<!DO\s)(?<!FOR\s)UPDATE\s+(?:public\.)?(?P<u>[a-z_][a-z0-9_]*)"
    r"\s+(?:(?:AS\s+)?[a-z_]+\s+)?SET\b"
    r"|DELETE\s+FROM\s+(?:public\.)?(?P<d>[a-z_][a-z0-9_]*))",
    re.IGNORECASE,
)
#: Chữ regex bắt nhầm, hoặc schema / bảng tạm ngoài phạm vi bài này. "public"
#: một mình = tên bảng dựng lúc chạy (`f"DELETE FROM public.{bang}"`, phat_lai).
_KHONG_PHAI_BANG = {
    "set",
    "into",
    "from",
    "only",
    "public",
    "app_private",
    "lich_su_notion",
    "_ghep",
}

VI_PHAM = "VI_PHAM"
DUNG_THIET_KE = "DUNG_THIET_KE"
XEM_LAI_KHOI = "XEM_LAI_KHOI"
CHUA_XET = "CHUA_XET"

#: (tệp tính từ src/clinicai/, bảng) → nhãn. CHỈ ĐƯỢC NGẮN ĐI.
NO_GHI_CHEO: dict[tuple[str, str], str] = {
    ("services/ban_le_service.py", "visit"): CHUA_XET,
    ("services/ban_theo_don_service.py", "visit"): CHUA_XET,
    ("services/booking_service.py", "encounter_flow"): CHUA_XET,
    ("services/booking_service.py", "patient"): CHUA_XET,
    ("services/booking_service.py", "queue_entry"): VI_PHAM,
    ("services/booking_service.py", "visit"): CHUA_XET,
    ("services/booking_service.py", "work_item"): CHUA_XET,
    ("services/booking_service.py", "work_roster"): CHUA_XET,
    ("services/checkout_service.py", "appointment"): VI_PHAM,
    ("services/checkout_service.py", "queue_entry"): VI_PHAM,
    ("services/checkout_service.py", "work_item"): CHUA_XET,
    ("services/chuyen_luot_that.py", "service_type"): CHUA_XET,
    ("services/chuyen_luot_that.py", "staff"): CHUA_XET,
    ("services/clinic_config_service.py", "service_price"): CHUA_XET,
    ("services/clinic_config_service.py", "service_type"): CHUA_XET,
    ("services/clinic_config_service.py", "staff_node"): CHUA_XET,
    ("services/clinical_record_service.py", "visit"): CHUA_XET,
    ("services/clinical_record_service.py", "vital_measurement"): VI_PHAM,
    ("services/clinical_sign_service.py", "cskh_action"): CHUA_XET,
    ("services/clinical_sign_service.py", "hen_goi_lai"): CHUA_XET,
    ("services/clinical_sign_service.py", "ultrasound_record"): CHUA_XET,
    ("services/clinical_sign_service.py", "visit"): CHUA_XET,
    ("services/config_service.py", "appointment"): CHUA_XET,
    ("services/config_service.py", "drug_catalog"): CHUA_XET,
    ("services/config_service.py", "roster_week"): CHUA_XET,
    ("services/config_service.py", "service_price"): CHUA_XET,
    ("services/config_service.py", "vai_duoc_vao_tram"): CHUA_XET,
    ("services/config_service.py", "work_roster"): CHUA_XET,
    ("services/config_service.py", "work_roster_thay_nguoi"): CHUA_XET,
    ("services/day_noi_service.py", "day_nhan_thong_bao"): CHUA_XET,
    ("services/day_noi_service.py", "service_type"): CHUA_XET,
    ("services/day_noi_service.py", "vai_duoc_vao_tram"): CHUA_XET,
    ("services/day_noi_service.py", "vi_tri_lam_viec"): CHUA_XET,
    ("services/dinh_chinh_don.py", "drug_catalog"): CHUA_XET,
    ("services/dinh_chinh_don.py", "prescription_allocation"): VI_PHAM,
    ("services/dinh_chinh_don.py", "prescription_correction"): CHUA_XET,
    ("services/doi_bac_si_service.py", "appointment"): VI_PHAM,
    ("services/doi_bac_si_service.py", "consultation"): CHUA_XET,
    ("services/doi_bac_si_service.py", "visit"): CHUA_XET,
    ("services/doi_tac_service.py", "queue_entry"): VI_PHAM,
    ("services/doi_tac_service.py", "service_order"): VI_PHAM,
    ("services/form_engine_service.py", "form_definition"): XEM_LAI_KHOI,
    ("services/form_engine_service.py", "ket_qua_mau"): XEM_LAI_KHOI,
    ("services/form_engine_service.py", "service_order"): VI_PHAM,
    ("services/form_engine_service.py", "visit_amendment"): CHUA_XET,
    ("services/hang_cho.py", "visit"): CHUA_XET,
    ("services/hen_tai_kham_service.py", "thong_bao"): CHUA_XET,
    ("services/hoan_tac_service.py", "appointment"): DUNG_THIET_KE,
    ("services/hoan_tac_service.py", "consultation"): CHUA_XET,
    ("services/hoan_tac_service.py", "encounter_flow"): CHUA_XET,
    ("services/hoan_tac_service.py", "follow_up_case"): CHUA_XET,
    ("services/hoan_tac_service.py", "review_round"): DUNG_THIET_KE,
    ("services/hoan_tac_service.py", "round_requirement"): CHUA_XET,
    ("services/hoan_tac_service.py", "service_execution_attempt"): XEM_LAI_KHOI,
    ("services/hoan_tac_service.py", "service_order"): XEM_LAI_KHOI,
    ("services/hoan_tac_service.py", "visit"): CHUA_XET,
    ("services/hoan_tac_service.py", "work_item"): CHUA_XET,
    ("services/kho_thuoc_service.py", "clinic_location"): CHUA_XET,
    ("services/lam_them_tai_quay_service.py", "queue_entry"): DUNG_THIET_KE,
    ("services/lam_truoc_thu_sau.py", "service_order"): CHUA_XET,
    ("services/lam_truoc_thu_sau.py", "visit"): CHUA_XET,
    ("services/lenh_kham_core.py", "encounter_flow"): CHUA_XET,
    ("services/lo_thuoc_service.py", "clinic"): CHUA_XET,
    ("services/luot_kham_service.py", "appointment"): VI_PHAM,
    ("services/luot_kham_service.py", "encounter_flow"): CHUA_XET,
    ("services/luot_kham_service.py", "follow_up_case"): CHUA_XET,
    ("services/luot_kham_service.py", "queue_entry"): VI_PHAM,
    ("services/luot_kham_service.py", "review_round"): XEM_LAI_KHOI,
    ("services/luot_kham_service.py", "round_requirement"): CHUA_XET,
    ("services/luot_kham_service.py", "service_order"): VI_PHAM,
    ("services/luot_kham_service.py", "tep_ket_qua"): VI_PHAM,
    ("services/luot_kham_service.py", "visit"): CHUA_XET,
    ("services/nhan_tai_phong.py", "service_order"): CHUA_XET,
    ("services/nhap_lich_su_notion.py", "patient"): CHUA_XET,
    ("services/pharmacy_service.py", "drug_catalog"): CHUA_XET,
    ("services/pharmacy_service.py", "prescription"): CHUA_XET,
    ("services/phi_kham_service.py", "so_sua_chi_dinh"): CHUA_XET,
    ("services/quay_thuoc_service.py", "prescription"): VI_PHAM,
    ("services/service_execution_service.py", "form_instance"): VI_PHAM,
    ("services/service_execution_service.py", "queue_entry"): VI_PHAM,
    ("services/service_execution_service.py", "service_order"): CHUA_XET,
    ("services/service_order_service.py", "visit_route"): CHUA_XET,
    ("services/service_order_service.py", "work_item"): CHUA_XET,
    ("services/service_routing_service.py", "service_execution_attempt"): VI_PHAM,
    ("services/service_routing_service.py", "service_order"): CHUA_XET,
    ("services/service_selection_service.py", "luot_phu_thu"): CHUA_XET,
    ("services/service_selection_service.py", "service_order"): CHUA_XET,
    ("services/sinh_hieu_service.py", "encounter_flow"): CHUA_XET,
    ("services/so_sua_chi_dinh_service.py", "luot_phi_kham"): DUNG_THIET_KE,
    ("services/so_sua_chi_dinh_service.py", "thong_bao"): CHUA_XET,
    ("services/staff_service.py", "work_roster"): CHUA_XET,
    ("services/tep_ket_qua_service.py", "service_order"): CHUA_XET,
    ("services/thu_tu_kham_service.py", "patient"): CHUA_XET,
    ("services/thue_suat_service.py", "drug_catalog"): CHUA_XET,
    ("services/thue_suat_service.py", "service_price"): CHUA_XET,
    ("services/ultrasound_board_service.py", "ultrasound_record"): CHUA_XET,
    ("services/ultrasound_service.py", "visit"): CHUA_XET,
}


def bang_bi_ghi() -> dict[str, set[str]]:
    """Tệp → các bảng mà câu SQL trong tệp ấy ghi vào."""
    kq: dict[str, set[str]] = defaultdict(set)
    for p in sorted(GOC.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        tep = p.relative_to(GOC).as_posix()
        for ham in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if not isinstance(ham, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            sql = "\n".join(
                c.value
                for c in ast.walk(ham)
                if isinstance(c, ast.Constant) and isinstance(c.value, str)
            )
            for m in _GHI.finditer(sql):
                bang = (m.group("i") or m.group("u") or m.group("d")).lower()
                if bang not in _KHONG_PHAI_BANG:
                    kq[tep].add(bang)
    return kq


def _chu_bang() -> dict[str, str]:
    return {b: m.ma for m in MODULE.values() for b in m.bang}


def ghi_cheo_thuc_te() -> set[tuple[str, str]]:
    chu = _chu_bang()
    return {
        (tep, b)
        for tep, ds in bang_bi_ghi().items()
        for b in ds
        if b in chu and chu[b] != khoi_cua_tep(tep)
    }


def test_bang_bi_ghi_deu_co_chu() -> None:
    chu = _chu_bang()
    mo_coi = sorted(
        f"{tep}: {b}"
        for tep, ds in bang_bi_ghi().items()
        for b in ds
        if b not in chu and b not in BANG_KY_THUAT
    )
    assert not mo_coi, (
        "Bảng bị ghi mà không khối nào giữ — khai `bang` cho khối chủ trong"
        " modules.py (hoặc BANG_KY_THUAT nếu là sổ / hàng đợi kỹ thuật):\n  "
        + "\n  ".join(mo_coi)
    )


def test_bang_ky_thuat_khong_trung_bang_co_chu() -> None:
    trung = sorted(set(BANG_KY_THUAT) & set(_chu_bang()))
    assert not trung, f"Bảng vừa có chủ vừa là bảng kỹ thuật: {trung}"


def test_tep_ghi_bang_co_chu_deu_khai_khoi() -> None:
    chu = _chu_bang()
    thieu = sorted(
        tep
        for tep, ds in bang_bi_ghi().items()
        if any(b in chu for b in ds) and khoi_cua_tep(tep) is None
    )
    assert not thieu, (
        "Tệp ghi bảng của một khối nhưng chưa khai thuộc khối nào — thêm vào"
        " TEP_CUA_KHOI trong modules.py:\n  " + "\n  ".join(thieu)
    )


def test_ban_khai_tep_hop_le() -> None:
    lap: dict[str, list[str]] = defaultdict(list)
    for ma, ds in TEP_CUA_KHOI.items():
        assert ma in MODULE, f"TEP_CUA_KHOI có khối lạ: {ma}"
        for tep in ds:
            lap[tep].append(ma)
            assert (GOC / tep).is_file(), f"{ma}: tệp không còn — {tep}"
    hai_cho = {t: ms for t, ms in lap.items() if len(ms) > 1}
    assert not hai_cho, f"Một tệp khai ở nhiều khối: {hai_cho}"


def test_ghi_cheo_chi_trong_so_no() -> None:
    thuc = ghi_cheo_thuc_te()
    chu = _chu_bang()
    moi = sorted(thuc - NO_GHI_CHEO.keys())
    assert not moi, (
        "Chỗ ghi chéo MỚI — tệp của khối này ghi bảng của khối khác. Gọi lệnh /"
        " phát sự kiện cho khối chủ, hoặc sửa TEP_CUA_KHOI (đọc đầu tệp test):\n  "
        + "\n  ".join(
            f"{tep} ({khoi_cua_tep(tep)}) ghi {b} (của {chu[b]})" for tep, b in moi
        )
    )
    da_het = sorted(NO_GHI_CHEO.keys() - thuc)
    assert not da_het, (
        "Chỗ ghi chéo trong sổ nợ đã hết — gạch khỏi NO_GHI_CHEO:\n  "
        + "\n  ".join(f"{tep}: {b}" for tep, b in da_het)
    )
