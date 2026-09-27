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
from clinicai.core.exceptions import SafetyGateError, ValidationError
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


async def test_le_tan_doc_de_in_nhung_khong_ghi_phieu_kham(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """27/09/2026 (Tuyền "in ở mọi khâu"): lễ tân ĐỌC được phiếu để in cho
    khách (`QUYEN_IN_PHIEU`), nhưng vẫn KHÔNG ghi được."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        le_tan = await _nguoi(conn, "RECEPTION")
        luot = await _luot(conn, bs)
    svc = _svc(pool)
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
    # 27/09/2026 (đợt 3): 14 dòng theo bản giao diện mẫu (soi CTC/âm hộ sang
    # CLS, bỏ "• Laser", ghế ĐTT yếu/đau cơ sang điều trị).
    assert len(tc["thu_thuat"]) == 14
    assert muc["Soi âm hộ"]["form_id_ket_qua"] == "KQ_SOI_AM_HO"
    assert "*Soi âm hộ" not in muc
    # 73 thuốc của phiếu + mặt hàng kho không có trên phiếu (mã "kho:…", 25/09).
    phieu = [m for m in tc["mau_thuoc"] if not str(m["ma"]).startswith("kho:")]
    assert len(phieu) == 73


async def test_hai_dong_tieu_de_khong_hien_lai_o_dich_vu_khac(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """ "*XN dịch âm đạo" / "• Laser" bỏ khỏi danh mục (đợt 3) — kể cả khi dịch
    vụ còn bật và (giả sử) có mã phòng khám thì "Dịch vụ khác trong bảng giá"
    cũng không kéo chúng lại."""
    from clinicai.phieu_kham import anh_xa_danh_muc as ax

    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
    cu = {
        r["service_code"]: r["ma_kiotviet"]
        for r in await pool.fetch(
            "SELECT service_code, ma_kiotviet FROM service_price"
            " WHERE clinic_id = $1::uuid AND service_code = ANY($2::text[])",
            bs.clinic_id,
            sorted(ax.KHONG_LIET_KE),
        )
    }
    try:
        for ma in cu:
            await pool.execute(
                "UPDATE service_price SET ma_kiotviet = $3"
                " WHERE clinic_id = $1::uuid AND service_code = $2",
                bs.clinic_id,
                ma,
                f"TEST_{ma}",
            )
        tc = await _svc(pool).tham_chieu_that(identity=bs)
    finally:
        for ma, kv in cu.items():
            await pool.execute(
                "UPDATE service_price SET ma_kiotviet = $3"
                " WHERE clinic_id = $1::uuid AND service_code = $2",
                bs.clinic_id,
                ma,
                kv,
            )
    moi_ma = {m.get("service_code") for n in tc["chi_dinh_cls"] for m in n["muc"]} | {
        t.get("service_code") for t in tc["thu_thuat"]
    }
    assert moi_ma.isdisjoint(ax.KHONG_LIET_KE)


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
    # Dòng ngoài danh mục kho: không đơn giá, không ĐVT kho.
    assert doc2[0]["don_gia"] is None and doc2[0]["dvt_kho"] is None


async def test_don_thuoc_doc_kem_don_gia_va_dvt_cua_kho(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Cột "Đơn giá" + ĐVT chữ (27/09/2026, bản giao diện mẫu) đọc từ kho."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
        kho = await conn.fetchrow(
            "SELECT id::text, name_raw, unit_price, don_vi_ban FROM drug_catalog"
            " WHERE clinic_id = $1::uuid AND is_active AND unit_price IS NOT NULL"
            " ORDER BY name_raw LIMIT 1",
            bs.clinic_id,
        )
    if kho is None:
        pytest.skip("DB thử chưa có mặt hàng kho có giá")
    svc = _svc(pool)
    dong: list[dict[str, Any]] = [
        {
            "id": None,
            "drug_catalog_id": kho["id"],
            "drug_name": kho["name_raw"],
            "quantity": f"2 {kho['don_vi_ban'] or ''}".strip(),
            "dosage": "Uống — Ngày 2 lần",
            "caution": "",
        }
    ]
    await svc.luu_don_thuoc(visit_id=luot["visit"], dong=dong, ly_do=None, identity=bs)
    (d,) = await svc.doc_don_thuoc(visit_id=luot["visit"], identity=bs)
    assert d["don_gia"] == int(kho["unit_price"])
    assert d["dvt_kho"] == ((kho["don_vi_ban"] or "").strip() or None)


async def test_luu_theo_o_hai_nguoi_hai_o_khong_409(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Lát 2 (26/09/2026): gửi CHỈ ô vừa đổi — bác sĩ và thư ký sửa hai ô khác
    nhau cùng lúc đều được lưu, không ai 409 / mất chữ đang gõ."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        tk = await _nguoi(conn, "TKYK")
        luot = await _luot(conn, bs)
    svc = _svc(pool)
    o_van = [
        ma
        for ma, o in cac_o(dinh_nghia("PK")["khung"]).items()
        if o["kieu"] == "doan_van"
    ]
    a, b = o_van[0], o_van[1]
    v = luot["visit"]
    await svc.luu_luot(
        visit_id=v,
        form_id="PK",
        du_lieu=None,
        expected_revision=0,
        thay_doi={a: _o("bác sĩ gõ")},
        identity=bs,
    )
    # Thư ký cầm revision cũ (0) vẫn lưu được ô KHÁC.
    await svc.luu_luot(
        visit_id=v,
        form_id="PK",
        du_lieu=None,
        expected_revision=0,
        thay_doi={b: _o("thư ký gõ")},
        identity=tk,
    )
    kq = await svc.doc_luot(visit_id=v, form_id="PK", identity=bs)
    assert kq["du_lieu"][a]["gia_tri"] == "bác sĩ gõ"
    assert kq["du_lieu"][b]["gia_tri"] == "thư ký gõ"
    # Xoá ô = gửi rỗng.
    await svc.luu_luot(
        visit_id=v,
        form_id="PK",
        du_lieu=None,
        expected_revision=0,
        thay_doi={a: _o("")},
        identity=bs,
    )
    kq = await svc.doc_luot(visit_id=v, form_id="PK", identity=bs)
    assert kq["du_lieu"][a]["gia_tri"] == ""
    assert kq["du_lieu"][b]["gia_tri"] == "thư ký gõ"
    # Ô lạ vẫn bị chặn như cũ.
    with pytest.raises(ValidationError):
        await svc.luu_luot(
            visit_id=v,
            form_id="PK",
            du_lieu=None,
            expected_revision=0,
            thay_doi={"o_khong_co": _o("x")},
            identity=bs,
        )


async def test_hen_tren_phieu_v5_sinh_nhac_tai_kham(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Lát 2 (26/09/2026): ngày tái khám ở mục G phiếu v5 (`*_follow_date`)
    phải sinh việc gọi nhắc — trước đó chỉ bệnh án cũ được đọc."""
    import datetime as dt

    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
    v = luot["visit"]
    o_hen = next(
        ma for ma in cac_o(dinh_nghia("PK")["khung"]) if ma.endswith("_follow_date")
    )
    hom_nay = dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).date()
    await _svc(pool).luu_luot(
        visit_id=v,
        form_id="PK",
        du_lieu=None,
        expected_revision=0,
        thay_doi={o_hen: _o((hom_nay + dt.timedelta(days=3)).isoformat())},
        identity=bs,
    )
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE visit SET status = 'FINALIZED' WHERE visit_id = $1::uuid", v
        )
        clinic, khach = await conn.fetchrow(
            "SELECT clinic_id, clinic_patient_id FROM visit WHERE visit_id = $1::uuid",
            v,
        )
        await conn.fetch(
            "SELECT * FROM public.sinh_viec_nhac_tai_kham($1, $2)", clinic, hom_nay
        )
        viec = await conn.fetch(
            "SELECT luot_goi, ngay_hen FROM nhac_tai_kham WHERE clinic_patient_id = $1",
            khach,
        )
    assert [(r["luot_goi"], r["ngay_hen"]) for r in viec] == [
        (1, hom_nay + dt.timedelta(days=3))
    ]
