"""Ruột 18 mẫu kết quả (v2) + in phiếu (23/09/2026 khuya).

Tuyền: "các form này lặp lại, họ muốn mặc định là điền sẵn, sửa lại rồi lưu rồi
in được và đồng bộ sang bác sĩ chính". Kiểm luật an toàn của ruột: câu bình
thường điền sẵn, SỐ ĐO và kết quả XÉT NGHIỆM thì không; và ai in được.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import pytest

from clinicai.core.exceptions import SafetyGateError
from clinicai.services.form_engine_service import FormEngineService
from tests.services.test_form_engine_db import (
    CLINIC,
    _don_tron,
    _nguoi,
    pool,  # noqa: F401
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _khung(pool: asyncpg.Pool, form_id: str) -> list[dict[str, Any]]:  # noqa: F811
    khung: list[dict[str, Any]] = json.loads(
        await pool.fetchval(
            "SELECT khung FROM form_definition WHERE clinic_id = $1::uuid"
            " AND form_id = $2 AND trang_thai = 'PUBLISHED'",
            CLINIC,
            form_id,
        )
    )
    return khung


async def test_so_do_va_xet_nghiem_khong_dien_san(pool: asyncpg.Pool) -> None:  # noqa: F811
    # Xét nghiệm: không một ô chọn nào có sẵn "ÂM TÍNH".
    hpv = await _khung(pool, "KQ_XN_HPV")
    chon = [b for m in hpv for b in m["block"] if b["kieu"] == "chon"]
    assert len(chon) == 6 and not any(b.get("mac_dinh") for b in chon)
    # Số đo mạch thận: chỉ gợi ý đơn vị, không có con số điền sẵn.
    than = await _khung(pool, "KQ_SA_MACH_THAN")
    so_do = [
        b for m in than for b in m["block"] if b["ma"].endswith(("_psv", "_edv", "_ri"))
    ]
    assert len(so_do) == 18
    assert not any(b.get("mac_dinh") for b in so_do)
    # Câu bình thường thì có.
    obung = await _khung(pool, "KQ_SA_OBUNG")
    assert next(b for m in obung for b in m["block"] if b["ma"] == "gan").get(
        "mac_dinh"
    )


async def test_mo_phieu_moi_la_co_cau_dien_san(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        order = await _don_tron(conn, bs)
    p = await FormEngineService(pool).mo_phieu(
        service_order_id=order, form_id="KQ_SA_OBUNG", identity=bs
    )
    assert p["du_lieu"]["gan"]["nguon"] == "TEMPLATE_DEFAULT"
    assert "không có sỏi" in p["du_lieu"]["tui_mat"]["gia_tri"]


async def test_in_phieu_ai_in_duoc_va_ban_nhap_ghi_ro(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        cskh = await _nguoi(conn, "CSKH")
        le_tan = await _nguoi(conn, "RECEPTION")
        order = await _don_tron(conn, bs)
    svc = FormEngineService(pool)
    p = await svc.mo_phieu(service_order_id=order, form_id="KQ_SA_VU", identity=bs)
    ban = await svc.in_ket_qua(service_order_id=order, identity=cskh)
    assert ban["phieu"][0]["ban_nhap"] is True
    assert ban["benh_nhan"]["ho_ten"]
    await svc.hoan_tat(phieu_id=p["id"], expected_revision=p["revision"], identity=bs)
    ban = await svc.in_ket_qua(service_order_id=order, identity=bs)
    assert ban["phieu"][0]["ban_nhap"] is False
    assert ban["phieu"][0]["hoan_tat_boi"]
    with pytest.raises(SafetyGateError):
        await svc.in_ket_qua(service_order_id=order, identity=le_tan)


async def test_phong_chua_gan_mau_van_mo_duoc_mau_goi_y(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Phòng siêu âm mở ra là điền được: chưa gắn mẫu thì mẫu gợi ý v5 chọn sẵn
    + 18 mẫu dự phòng; đã gắn thì chỉ mẫu đã gắn (quyết định của quản lý)."""
    from clinicai.phieu_kham.mau_goi_y import mau_cho_dich_vu

    async with pool.acquire() as conn:
        ds, goi_y = await mau_cho_dich_vu(
            conn, clinic_id=CLINIC, service_code="CLS_SIEU_AM_VU"
        )
        # 18 mẫu + mẫu CHUNG nhập tự do (24/09/2026).
        assert goi_y == "SA_VU" and ds[0]["ma"] == "SA_VU" and len(ds) == 19
        # Dịch vụ không có gợi ý: đủ mẫu, CHỌN SẴN mẫu CHUNG (nhập tự do).
        ds, goi_y = await mau_cho_dich_vu(
            conn, clinic_id=CLINIC, service_code="KHONG_CO"
        )
        assert goi_y == "CHUNG" and ds[0]["ma"] == "CHUNG" and len(ds) == 19
        # Quản lý đã gắn mẫu → chỉ mẫu ấy.
        bs = await _nguoi(conn, "DOCTOR")
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO dich_vu_mau_ket_qua"
                " (clinic_id, service_code, mau, gan_boi)"
                " VALUES ($1::uuid, 'CLS_TEST_GAN_MAU', 'SA_GIAP', $2::uuid)"
                " ON CONFLICT DO NOTHING",
                CLINIC,
                bs.staff_id,
            )
        ds, goi_y = await mau_cho_dich_vu(
            conn, clinic_id=CLINIC, service_code="CLS_TEST_GAN_MAU"
        )
        assert [m["ma"] for m in ds] == ["SA_GIAP"] and goi_y == "SA_GIAP"
