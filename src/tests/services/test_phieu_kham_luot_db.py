"""Phiếu khám v5 gắn vào Bàn khám (23/09/2026 tối) — chỗ lưu theo LƯỢT.

Tuyền: "form sửa theo như này đi… không cần nút lưu hồ sơ… không cần cái duyệt
kết quả nữa". Kiểm: đọc phiếu của lượt (chọn phiếu khi loại khám chưa gắn), tự
lưu có chống đè, quyền theo capability (không theo vai), dữ liệu rác không ném,
danh mục C/F có mã + giá thật, đơn thuốc mục E đi qua đường đơn bệnh án.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.core.exceptions import SafetyGateError
from clinicai.phieu_kham.khung import cac_o, dinh_nghia
from clinicai.services.phieu_kham_service import PhieuKhamService, kiem_quyen_core
from tests.services.test_phieu_kham_db import (
    _luot,
    _nguoi,
    _o,
    pool,  # noqa: F401
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _svc(pool: asyncpg.Pool) -> PhieuKhamService:  # noqa: F811
    return PhieuKhamService(pool, kiem_quyen=kiem_quyen_core)


def _o_theo_kieu(form_id: str, kieu: str) -> str:
    return next(
        ma for ma, o in cac_o(dinh_nghia(form_id)["khung"]).items() if o["kieu"] == kieu
    )


async def test_luot_chua_gan_phieu_thi_cho_chon_roi_mo_dung_phieu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
    svc = _svc(pool)
    kq = await svc.doc_luot(visit_id=luot["visit"], form_id=None, identity=bs)
    assert kq["form_id"] is None
    assert {p["form_id"] for p in kq["chon_duoc"]} == {
        "NT",
        "HMVS",
        "PK",
        "SK",
        "NK",
        "THU_THUAT",
        "SAN_CHAU",
    }
    pk = await svc.doc_luot(visit_id=luot["visit"], form_id="PK", identity=bs)
    assert pk["form_id"] == "PK" and pk["revision"] == 0 and pk["du_lieu"] == {}
    assert pk["che_do"] == "editable"


async def test_tu_luu_co_chong_de_va_mo_lai_dung_phieu_da_ghi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        tk = await _nguoi(conn, "TKYK")
        luot = await _luot(conn, bs)
    svc = _svc(pool)
    o = _o_theo_kieu("PK", "doan_van")
    r1 = await svc.luu_luot(
        visit_id=luot["visit"],
        form_id="PK",
        du_lieu={o: _o("Đau bụng dưới 3 ngày")},
        expected_revision=0,
        identity=bs,
    )
    assert r1["revision"] == 1
    # Thư ký gõ tiếp trên đúng bản mới — được.
    r2 = await svc.luu_luot(
        visit_id=luot["visit"],
        form_id="PK",
        du_lieu={o: _o("Đau bụng dưới 3 ngày, sốt nhẹ")},
        expected_revision=1,
        identity=tk,
    )
    assert r2["revision"] == 2
    # Bác sĩ còn cầm bản cũ (revision 1) → 409, không đè im lặng.
    with pytest.raises(ConflictError):
        await svc.luu_luot(
            visit_id=luot["visit"],
            form_id="PK",
            du_lieu={o: _o("bản cũ")},
            expected_revision=1,
            identity=bs,
        )
    # Mở lại không truyền form_id → đúng phiếu đã ghi, đúng nội dung mới nhất.
    kq = await svc.doc_luot(visit_id=luot["visit"], form_id=None, identity=bs)
    assert kq["form_id"] == "PK" and kq["revision"] == 2
    assert kq["du_lieu"][o]["gia_tri"] == "Đau bụng dưới 3 ngày, sốt nhẹ"


async def test_le_tan_khong_doc_khong_ghi_phieu_kham(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        le_tan = await _nguoi(conn, "RECEPTION")
        luot = await _luot(conn, bs)
    svc = _svc(pool)
    with pytest.raises(SafetyGateError):
        await svc.doc_luot(visit_id=luot["visit"], form_id="PK", identity=le_tan)
    with pytest.raises(SafetyGateError):
        await svc.luu_luot(
            visit_id=luot["visit"],
            form_id="PK",
            du_lieu={},
            expected_revision=0,
            identity=le_tan,
        )


async def test_ngay_rac_thanh_rong_kem_canh_bao_khong_nem(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    form = next(
        f
        for f in ("NT", "HMVS", "PK", "SK", "NK", "THU_THUAT", "SAN_CHAU")
        if any(o["kieu"] == "ngay" for o in cac_o(dinh_nghia(f)["khung"]).values())
    )
    o = _o_theo_kieu(form, "ngay")
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
    kq = await _svc(pool).luu_luot(
        visit_id=luot["visit"],
        form_id=form,
        du_lieu={o: _o("32/13/20xx")},
        expected_revision=0,
        identity=bs,
    )
    assert kq["canh_bao"], "ngày rác phải được nói ra"
    luu = await pool.fetchval(
        "SELECT du_lieu FROM phieu_kham_luot WHERE visit_id = $1::uuid", luot["visit"]
    )
    assert '"32/13/20xx"' not in str(luu)


async def test_danh_muc_c_f_gan_ma_that_va_gia(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
    tc = await _svc(pool).tham_chieu_that(identity=bs)
    muc = {m["nhan"]: m for n in tc["chi_dinh_cls"] for m in n["muc"]}
    co_ma = await pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM service_price WHERE service_code ="
        " 'CLS_SIEU_AM_2D_TC_BT' AND active AND \"group\" = 'dich_vu')"
    )
    if co_ma:
        assert muc["SÂ 2D TC-BT"]["service_code"] == "CLS_SIEU_AM_2D_TC_BT"
    # Mã không có trong danh mục phòng khám → null (màn khoá), không đoán.
    for m in muc.values():
        if m["service_code"] is not None:
            assert await pool.fetchval(
                "SELECT EXISTS (SELECT 1 FROM service_price WHERE service_code = $1"
                " AND active)",
                m["service_code"],
            )
    assert len(tc["thu_thuat"]) == 15 and len(tc["mau_thuoc"]) == 73


async def test_don_thuoc_muc_e_ghi_va_sua_khong_tao_trung(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
    svc = _svc(pool)
    dong: list[dict[str, Any]] = [
        {
            "id": None,
            "drug_catalog_id": None,
            "drug_name": "Duphaston (4v/2v)",
            "quantity": "2 hộp",
            "dosage": "Uống — Ngày 2 lần, mỗi lần 1 viên",
            "caution": "",
        }
    ]
    await svc.luu_don_thuoc(visit_id=luot["visit"], dong=dong, ly_do=None, identity=bs)
    doc = await svc.doc_don_thuoc(visit_id=luot["visit"], identity=bs)
    assert [d["drug_name_raw"] for d in doc] == ["Duphaston (4v/2v)"]
    # Sửa số lượng trên đúng dòng (có mã) → vẫn một dòng.
    dong[0] = {**dong[0], "id": doc[0]["id"], "quantity": "3 hộp"}
    await svc.luu_don_thuoc(visit_id=luot["visit"], dong=dong, ly_do=None, identity=bs)
    doc2 = await svc.doc_don_thuoc(visit_id=luot["visit"], identity=bs)
    assert len(doc2) == 1 and doc2[0]["quantity"] == "3 hộp"
