"""PHẢN HỒI SAU DÙNG THUỐC (10/10/2026) — CSKH ghi ở khung khách, gắn lượt có
đơn, người ghi gỡ được dòng của mình, bác sĩ đọc ở lịch sử lượt.

    scripts/test-nhanh.sh src/tests/services/test_phan_hoi_thuoc_db.py
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import lich_su_luot
from clinicai.services.phan_hoi_thuoc_service import (
    PhanHoiThuocService,
    doc_theo_luot,
)
from clinicai.services.tuong_tac_cskh_service import TuongTacCskhService
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)


async def _ke_don(pool: asyncpg.Pool, visit_id: str, ten: str) -> None:  # noqa: F811
    await pool.execute(
        "INSERT INTO prescription (clinic_id, source_ref, visit_id,"
        " clinic_patient_id, drug_name_raw, nguon)"
        " SELECT $1::uuid, $2, v.visit_id, v.clinic_patient_id, $3, 'BAC_SI'"
        " FROM visit v WHERE v.visit_id = $4::uuid",
        CLINIC,
        f"test-phtt-{uuid.uuid4().hex}",
        ten,
        visit_id,
    )


async def _luot_cu(pool: asyncpg.Pool, visit_id: str, ngay: int) -> None:  # noqa: F811
    """Đẩy lượt về quá khứ + đóng lại, để khách mở được lượt kế."""
    await pool.execute(
        "UPDATE visit SET checked_in_at = now() - make_interval(days => $2),"
        " closed_at = now() - make_interval(days => $2) WHERE visit_id = $1::uuid",
        visit_id,
        ngay,
    )
    await pool.execute(
        "UPDATE appointment SET status = 'COMPLETED' WHERE id ="
        " (SELECT appointment_id FROM visit WHERE visit_id = $1::uuid)",
        visit_id,
    )


@pytest.mark.asyncio
async def test_kenh_rac_va_noi_dung_rong_bi_tu_choi_truoc_db() -> None:
    sv = PhanHoiThuocService(None)
    for nd in [None, "", "   ", 5, "x" * 2001]:
        with pytest.raises(ValidationError):
            await sv.ghi(identity=None, clinic_patient_id="x", noi_dung=nd)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        await sv.ghi(identity=None, clinic_patient_id="x", noi_dung="ok", kenh="BAY")  # type: ignore[arg-type]


@pytest.mark.db
@pytest.mark.asyncio
async def test_ghi_mac_dinh_luot_co_don_gan_nhat_go_va_bac_si_doc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    cu = await _check_in(pool, ca, pid, ca.loai_kham)
    await _ke_don(pool, cu, "Duphaston 10mg")
    await _luot_cu(pool, cu, 10)
    moi = await _check_in(pool, ca, pid, ca.loai_kham)
    await _ke_don(pool, moi, "Utrogestan 200mg")
    async with pool.acquire() as conn:
        cskh = await _nguoi(conn, ca.loc, "CSKH")
    sv = PhanHoiThuocService(pool)

    doc = await sv.doc(identity=cskh, clinic_patient_id=pid)
    assert [x["visit_id"] for x in doc["luot_co_don"]] == [moi, cu]
    assert doc["luot_co_don"][1]["thuoc"] == "Duphaston 10mg"
    assert doc["items"] == []

    # Không chọn lượt → lượt có đơn GẦN NHẤT.
    a = await sv.ghi(identity=cskh, clinic_patient_id=pid, noi_dung="  Hơi buồn nôn ")
    assert a["visit_id"] == moi
    b = await sv.ghi(
        identity=ca.le_tan,
        clinic_patient_id=pid,
        visit_id=cu,
        kenh="ZALO",
        noi_dung="Hết ra huyết",
    )
    assert b["visit_id"] == cu

    doc = await sv.doc(identity=cskh, clinic_patient_id=pid)
    assert [(x["noi_dung"], x["visit_id"], x["cua_toi"]) for x in doc["items"]] == [
        ("Hết ra huyết", cu, False),
        ("Hơi buồn nôn", moi, True),
    ]
    assert doc["items"][0]["kenh"] == "ZALO"

    # Hoàn tác: CHỈ người ghi — cả đường gỡ riêng lẫn đường hoàn tác sổ chung.
    with pytest.raises(NotFoundError):
        await sv.go(identity=cskh, phan_hoi_id=b["id"])
    with pytest.raises(ValidationError):
        await TuongTacCskhService(pool).hoan_tac(identity=cskh, tuong_tac_id=b["id"])
    await sv.go(identity=cskh, phan_hoi_id=a["id"])
    with pytest.raises(NotFoundError):
        await sv.go(identity=cskh, phan_hoi_id=a["id"])
    vet = await pool.fetchrow(
        "SELECT huy_luc, huy_boi_staff_id::text AS ai FROM tuong_tac_cskh"
        " WHERE id = $1::uuid",
        a["id"],
    )
    assert vet is not None and vet["huy_luc"] is not None
    assert vet["ai"] == cskh.staff_id

    # Bác sĩ: phản hồi gắn đúng lượt, dòng đã gỡ không hiện.
    async with pool.acquire() as conn:
        theo_luot = await doc_theo_luot(conn, CLINIC, pid)
        ls = await lich_su_luot.doc(conn, clinic_id=CLINIC, clinic_patient_id=pid)
    assert {k: [x["noi_dung"] for x in v] for k, v in theo_luot.items()} == {
        cu: ["Hết ra huyết"]
    }
    gan = {
        x["visit_id"]: [p["noi_dung"] for p in x["phan_hoi_thuoc"]] for x in ls["luot"]
    }
    assert gan == {cu: ["Hết ra huyết"], moi: []}


@pytest.mark.db
@pytest.mark.asyncio
async def test_luot_khong_don_khach_la_va_khong_quyen(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    sv = PhanHoiThuocService(pool)
    khong_don = await _check_in(pool, ca, pid, ca.loai_kham)
    with pytest.raises(ValidationError, match="chưa có lượt"):
        await sv.ghi(identity=ca.le_tan, clinic_patient_id=pid, noi_dung="a")
    with pytest.raises(ValidationError, match="không có đơn"):
        await sv.ghi(
            identity=ca.le_tan, clinic_patient_id=pid, visit_id=khong_don, noi_dung="a"
        )
    # Lượt có đơn nhưng của KHÁCH KHÁC.
    pid2 = await _benh_nhan(pool, ca)
    v2 = await _check_in(pool, ca, pid2, ca.loai_kham)
    await _ke_don(pool, v2, "Thuốc khách khác")
    with pytest.raises(ValidationError):
        await sv.ghi(
            identity=ca.le_tan, clinic_patient_id=pid, visit_id=v2, noi_dung="a"
        )
    with pytest.raises(NotFoundError):
        await sv.ghi(
            identity=ca.le_tan, clinic_patient_id=str(uuid.uuid4()), noi_dung="a"
        )

    async with pool.acquire() as conn:
        duoc_si = await _nguoi(conn, ca.loc, "PHARMACIST")
        await ve_goi_mau_cu(conn, duoc_si)
    with pytest.raises(SafetyGateError):
        await sv.ghi(identity=duoc_si, clinic_patient_id=pid2, noi_dung="a")
    with pytest.raises(SafetyGateError):
        await sv.doc(identity=duoc_si, clinic_patient_id=pid2)

    # Lưới DB: phản hồi thuốc không lượt thì không vào sổ được.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "INSERT INTO tuong_tac_cskh (clinic_id, clinic_patient_id, loai, kenh,"
            " ket_qua, noi_dung, nhan_vien_staff_id) VALUES ($1::uuid, $2::uuid,"
            " 'PHAN_HOI_THUOC', 'GOI', 'DA_LIEN_HE', 'x', $3::uuid)",
            CLINIC,
            pid,
            ca.le_tan.staff_id,
        )
