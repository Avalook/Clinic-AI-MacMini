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
    # Số đo mạch thận: chỉ gợi ý đơn vị, không có con số điền sẵn. Từ v3
    # (26/09/2026, theo PDF) ô số đo nhận ra bằng đơn vị (`goi_y`).
    than = await _khung(pool, "KQ_SA_MACH_THAN")
    so_do = [b for m in than for b in m["block"] if b.get("goi_y")]
    assert so_do
    assert not any(b.get("mac_dinh") for b in so_do)
    # Câu bình thường thì có.
    obung = await _khung(pool, "KQ_SA_OBUNG")
    assert any(b.get("mac_dinh") for m in obung for b in m["block"])


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
        doi_tac = await _nguoi(conn, "PARTNER")
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
    # "In ở mọi khâu" (27/09/2026): lễ tân in được để trả khách; người không có
    # quyền in phiếu nào (tài khoản đối tác) thì không.
    assert (await svc.in_ket_qua(service_order_id=order, identity=le_tan))["phieu"]
    with pytest.raises(SafetyGateError):
        await svc.in_ket_qua(service_order_id=order, identity=doi_tac)

    # Lát 5: bản in kèm ẢNH của chỉ định; tệp CHƯA xác nhận không in; PDF chỉ đếm.
    them = (
        "INSERT INTO tep_ket_qua (clinic_id, clinic_patient_id, service_order_id,"
        " khoa, loai_tep, mime, so_byte, sha256, tai_len_boi_staff_id, ten_hien_thi,"
        " xac_nhan_trang_thai)"
        " SELECT o.clinic_id, v.clinic_patient_id, o.id, $2 || o.id::text, $3,"
        "        $4, 10, $2 || o.id::text, $5::uuid, $2, $6"
        "   FROM service_order o JOIN visit v ON v.visit_id = o.visit_id"
        "  WHERE o.id = $1::uuid"
    )
    async with pool.acquire() as conn:
        for ten, loai, mime, xn in (
            ("anh-1", "ANH", "image/jpeg", None),
            ("phieu-1", "PDF", "application/pdf", None),
            ("anh-cho", "ANH", "image/jpeg", "CHO_XAC_NHAN"),
        ):
            await conn.execute(them, order, ten, loai, mime, bs.staff_id, xn)
    ban = await svc.in_ket_qua(service_order_id=order, identity=bs)
    assert [a["ten"] for a in ban["anh"]] == ["anh-1"]
    assert ban["so_tep_khac"] == 1


async def test_phong_chua_gan_mau_van_mo_duoc_mau_goi_y(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Phòng siêu âm mở ra là điền được: chưa gắn mẫu thì mẫu gợi ý v5 chọn sẵn
    + 18 mẫu dự phòng; đã gắn thì chỉ mẫu đã gắn (quyết định của quản lý)."""
    from clinicai.phieu_kham.mau_goi_y import mau_cho_dich_vu

    async with pool.acquire() as conn:
        ds, goi_y = await mau_cho_dich_vu(
            conn, clinic_id=CLINIC, service_code="CLS_SIEU_AM_VU"
        )
        # Từ 26/09/2026 siêu âm vú ĐÃ GẮN mẫu theo mã phòng khám (SP000015 →
        # SA_VU, mẫu v3) — mẫu gợi ý vẫn là SA_VU, đứng đầu danh sách.
        assert goi_y == "SA_VU" and ds[0]["ma"] == "SA_VU"
        # Dịch vụ không có gợi ý: đủ mẫu, CHỌN SẴN mẫu CHUNG (nhập tự do).
        # 21 = 18 mẫu gốc + CHUNG + Đo mật độ xương (29/09/2026) + Phiếu điều
        # trị (07/10/2026).
        ds, goi_y = await mau_cho_dich_vu(
            conn, clinic_id=CLINIC, service_code="KHONG_CO"
        )
        assert goi_y == "CHUNG" and ds[0]["ma"] == "CHUNG" and len(ds) == 21
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
