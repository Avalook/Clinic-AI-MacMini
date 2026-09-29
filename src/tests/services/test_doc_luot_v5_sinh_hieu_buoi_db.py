"""G3 (Tuyền 29/09/2026) — ĐỌC lượt khám: phiếu v5 + sinh hiệu theo buổi.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55603/postgres \\
        .venv/bin/pytest src/tests/services/test_doc_luot_v5_sinh_hieu_buoi_db.py

1. "Lượt khám trước" không thấy phiếu v5: phiếu v5 lưu ở `phieu_kham_luot`,
   các nơi đọc lượt cũ chỉ đọc `clinical_form_response`.
2. Sinh hiệu theo buổi mới áp 4/10 chỗ: lượt 2 cùng ngày không đo lại thì hồ sơ
   CSKH + PDF, phiếu theo dịch vụ, `/clinical-records/doc`, dòng thời gian
   Check-out, BMI nam khoa, nút ký và thanh tiến trình /home đều phải có sinh
   hiệu của buổi.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from clinicai.core.clock import now_vn
from clinicai.ho_so.cong_doc import NguCanhHoSo
from clinicai.services.andrology_review_service import AndrologyReviewService
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.clinical_form_service import ClinicalFormService
from clinicai.services.clinical_record_service import (
    benh_an_cho_ho_so,
    lich_su_cho_ho_so,
)
from clinicai.services.clinical_sign_service import REQUIRED_SOAP, ClinicalSignService
from clinicai.services.ho_so_kham_service import HoSoKhamService
from clinicai.services.phieu_kham_service import PhieuKhamService, kiem_quyen_core
from clinicai.services.sinh_hieu_service import sinh_hieu_cho_ho_so
from clinicai.services.visit_progress_service import VisitProgressService
from clinicai.services.xem_luot_service import XemLuotService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_sinh_hieu_cung_buoi_db import Luot, _check_in, _do, _flow
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _dong_luot,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _o(v: object) -> dict[str, Any]:
    return {"gia_tri": v, "nguon": "USER"}


async def _hai_luot_cung_buoi(
    pool: asyncpg.Pool,  # noqa: F811
) -> tuple[Ca, str, Luot, Luot]:
    """Lượt 1 đo (có cân + cao → BMI) rồi về; lượt 2 cùng ngày KHÔNG đo lại."""
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    l1 = await _check_in(pool, ca, pid, ca.loai_kham)
    await _do(pool, ca, l1.visit, weight_kg=60, height_cm=160)
    await _dong_luot(pool, l1.visit)
    l2 = await _check_in(pool, ca, pid, ca.loai_thu_thuat)
    f = await _flow(pool, l2.visit)
    assert f["vitals_status"] == "recorded" and f["tu"] == l1.visit
    assert not await pool.fetchval(
        "SELECT count(*) FROM vital_measurement WHERE visit_id = $1::uuid", l2.visit
    )
    return ca, pid, l1, l2


# ── 2. SINH HIỆU THEO BUỔI ở bảy chỗ còn lại ────────────────────────────────


async def test_luot_2_khong_do_lai_moi_cho_doc_van_co_sinh_hieu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, pid, l1, l2 = await _hai_luot_cung_buoi(pool)

    # Hồ sơ khám CSKH (+ PDF dựng từ chính khung này).
    hs = await HoSoKhamService(pool).doc(identity=ca.le_tan, appointment_id=l2.appt)
    assert hs["sinh_hieu"] is not None
    assert hs["sinh_hieu"]["systolic"] == 118
    assert hs["sinh_hieu"]["nguon"] == "lượt trước"
    assert hs["sinh_hieu"]["nguoi_do"]

    # Phiếu theo dịch vụ đời cũ: ô sinh hiệu kèm.
    f = await ClinicalFormService(pool).get_form(
        visit_id=l2.visit, service_code="PK", identity=ca.bac_si
    )
    assert f["sinh_hieu_moi"] is not None
    assert f["sinh_hieu_moi"]["diastolic"] == 76

    # /clinical-records/doc (cổng đọc của khối Sinh hiệu).
    async with pool.acquire() as conn:
        g = await sinh_hieu_cho_ho_so(
            conn,
            NguCanhHoSo(
                identity=ca.bac_si, clinic_id=CLINIC, khach=pid, visit_id=l2.visit
            ),
        )
    assert g["vital_latest"] is not None and g["vital_latest"]["systolic"] == 118
    assert isinstance(g["vital_latest"]["created_at"], str)

    # Dòng thời gian Check-out: "Đo sinh hiệu" đã xong (lượt trước), không "Chờ".
    rd = await CheckoutService(pool).chi_tiet(identity=ca.le_tan, visit_id=l2.visit)
    [sh] = [d for d in rd["dich_vu"] if d["ten"].startswith("Đo sinh hiệu")]
    assert sh["status"] == "COMPLETED"
    assert sh["ten"] == "Đo sinh hiệu (lượt trước)"
    assert sh["xong_luc"] is not None and sh["nguoi_lam"]

    # BMI nam khoa đọc lần đo của buổi (60 kg / 1.6 m ≈ 23.4).
    bmi = await AndrologyReviewService(pool)._bmi(ca.bac_si, {}, l2.visit)
    assert bmi is not None and 23 < bmi < 24

    # Nút ký / hồ sơ hoàn tất: không báo thiếu "Khám lâm sàng".
    st = await ClinicalSignService(pool).status(identity=ca.bac_si, visit_id=l2.visit)
    assert REQUIRED_SOAP["soap_objective"] not in st["missing"]

    # Thanh tiến trình /home: đã đo.
    hom_nay = now_vn().date()
    ds = await VisitProgressService(pool).for_range(
        date_from=hom_nay, date_to=hom_nay, clinic_id=CLINIC
    )
    [tien_trinh] = [x for x in ds if x.visit_id == l2.visit]
    assert tien_trinh.vitals_recorded is True


async def test_luot_chua_do_van_la_cho_o_moi_cho(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Không đo ở đâu trong buổi → vẫn "chưa có" — đọc theo buổi không bịa số."""
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    l1 = await _check_in(pool, ca, pid, ca.loai_kham)
    hs = await HoSoKhamService(pool).doc(identity=ca.le_tan, appointment_id=l1.appt)
    assert hs["sinh_hieu"] is None
    rd = await CheckoutService(pool).chi_tiet(identity=ca.le_tan, visit_id=l1.visit)
    [sh] = [d for d in rd["dich_vu"] if d["ten"].startswith("Đo sinh hiệu")]
    assert sh["status"] == "PENDING" and sh["xong_luc"] is None
    assert (await AndrologyReviewService(pool)._bmi(ca.bac_si, {}, l1.visit)) is None
    f = await ClinicalFormService(pool).get_form(
        visit_id=l1.visit, service_code="PK", identity=ca.bac_si
    )
    assert f["sinh_hieu_moi"] is None
    hom_nay = now_vn().date()
    ds = await VisitProgressService(pool).for_range(
        date_from=hom_nay, date_to=hom_nay, clinic_id=CLINIC
    )
    [tien_trinh] = [x for x in ds if x.visit_id == l1.visit]
    assert tien_trinh.vitals_recorded is False


async def test_luot_1_khong_thay_so_do_cua_luot_sau(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Lượt SAU không chảy ngược: hồ sơ lượt 1 (chưa đo) không lấy số lượt 2."""
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    l1 = await _check_in(pool, ca, pid, ca.loai_kham)
    await _dong_luot(pool, l1.visit)
    l2 = await _check_in(pool, ca, pid, ca.loai_kham)
    await _do(pool, ca, l2.visit)
    hs1 = await HoSoKhamService(pool).doc(identity=ca.le_tan, appointment_id=l1.appt)
    assert hs1["sinh_hieu"] is None
    hs2 = await HoSoKhamService(pool).doc(identity=ca.le_tan, appointment_id=l2.appt)
    assert hs2["sinh_hieu"]["systolic"] == 118 and hs2["sinh_hieu"]["nguon"] is None


# ── 1. PHIẾU v5 ở các nơi đọc lượt cũ ───────────────────────────────────────


async def _ghi_phieu_sk(pool: asyncpg.Pool, ca: Ca, visit: str) -> None:  # noqa: F811
    await PhieuKhamService(pool, kiem_quyen=kiem_quyen_core).luu_luot(
        visit_id=visit,
        form_id="SK",
        du_lieu=None,
        thay_doi={
            "sk_reason": _o(["sk_reason_1"]),
            "sk_history": _o("Trễ kinh 2 tuần"),
            "sk_conclusion": _o("Thai trong tử cung 6 tuần"),
            "sk_follow_date": _o("2026-12-01"),
        },
        expected_revision=0,
        identity=ca.bac_si,
    )


async def test_luot_truoc_doc_phieu_v5_va_giu_nhanh_bang_cu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, pid, l1, l2 = await _hai_luot_cung_buoi(pool)
    await _ghi_phieu_sk(pool, ca, l2.visit)
    # Lượt 1 ghi phiếu đời cũ (bảng `clinical_form_response`).
    await pool.execute(
        "INSERT INTO clinical_form_response (clinic_id, visit_id, service_code,"
        " form_data, created_by, updated_by)"
        " VALUES ($1::uuid, $2::uuid, 'PK', $3::jsonb, 'DOCTOR · x', 'DOCTOR · x')",
        CLINIC,
        l1.visit,
        '{"ly_do": "Đau bụng"}',
    )

    ls = await ClinicalFormService(pool).lich_su_kham(
        clinic_patient_id=pid, identity=ca.bac_si
    )
    theo_luot = {x["visit_id"]: x for x in ls}
    v5 = theo_luot[l2.visit]
    assert v5["phieu_v5"] is True and v5["service_code"] == "SK"
    assert v5["chan_doan"] == "Thai trong tử cung 6 tuần"
    # Chữ đọc được theo khung: nhãn lựa chọn, ngày kiểu VN, chẩn đoán ĐẦU TIÊN.
    assert next(iter(v5["form_data"])) == "sk_conclusion"
    assert v5["form_data"]["sk_reason"] == "Khám thai"
    assert v5["form_data"]["sk_follow_date"] == "01/12/2026"
    cu = theo_luot[l1.visit]
    assert cu["phieu_v5"] is False and cu["form_data"] == {"ly_do": "Đau bụng"}
    # Mới nhất trước.
    assert [x["visit_id"] for x in ls][:2] == [l2.visit, l1.visit]


async def test_xem_luot_ho_so_cskh_benh_an_doc_phieu_v5(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, pid, _l1, l2 = await _hai_luot_cung_buoi(pool)
    await _ghi_phieu_sk(pool, ca, l2.visit)

    # Xem lượt: dòng "Chẩn đoán" + phiếu SK, ai nhập.
    xem = await XemLuotService(pool).doc(visit_id=l2.visit, identity=ca.bac_si)
    ls = xem["lam_sang"]
    assert ls["benh_an"]["chan_doan"] == "Thai trong tử cung 6 tuần"
    assert ls["phieu"]["ma"] == "SK"
    ten_bs = await pool.fetchval(
        "SELECT full_name FROM staff WHERE id = $1::uuid", ca.bac_si.staff_id
    )
    assert ls["phieu"]["nguoi_tao"] == ten_bs

    # Hồ sơ khám CSKH + PDF: phiếu v5 dịch thành chữ theo khung.
    hs = await HoSoKhamService(pool).doc(identity=ca.le_tan, appointment_id=l2.appt)
    [p] = [x for x in hs["phieu_kham"] if x.get("v5")]
    assert p["form_code"] == "SK" and p["ten"]
    dong = {d["ma"]: d["chu"] for m in p["muc"] for d in m["dong"]}
    assert dong["sk_conclusion"] == "Thai trong tử cung 6 tuần"
    assert dong["sk_reason"] == "Khám thai"

    # Bệnh án cũ (`/clinical-records/doc`): cờ phiếu v5 + chẩn đoán lượt trước.
    async with pool.acquire() as conn:
        ba = await benh_an_cho_ho_so(
            conn,
            NguCanhHoSo(
                identity=ca.bac_si, clinic_id=CLINIC, khach=pid, visit_id=l2.visit
            ),
        )
        ls_ba = await lich_su_cho_ho_so(
            conn,
            NguCanhHoSo(identity=ca.bac_si, clinic_id=CLINIC, khach=pid),
        )
    assert ba["visit"]["phieu_v5"] is True
    [h] = [x for x in ls_ba["history_raw"] if x["visit_id"] == l2.visit]
    assert h["soap_assessment"] == "Thai trong tử cung 6 tuần"


async def test_luot_khong_co_phieu_v5_giu_nhu_cu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    l1 = await _check_in(pool, ca, pid, ca.loai_kham)
    xem = await XemLuotService(pool).doc(visit_id=l1.visit, identity=ca.bac_si)
    assert xem["lam_sang"]["phieu"] is None
    assert xem["lam_sang"]["benh_an"]["chan_doan"] is None
    hs = await HoSoKhamService(pool).doc(identity=ca.le_tan, appointment_id=l1.appt)
    assert hs["phieu_kham"] == []
    async with pool.acquire() as conn:
        ba = await benh_an_cho_ho_so(
            conn,
            NguCanhHoSo(
                identity=ca.bac_si, clinic_id=CLINIC, khach=pid, visit_id=l1.visit
            ),
        )
    assert ba["visit"]["phieu_v5"] is False
