"""Tệp đối tác VÀO THẲNG phiếu khám — không bước xác nhận (23/09/2026 khuya).

Tuyền: "không cần nút xác nhận kết quả, nó phải cho vào luôn trong phiếu khám
của bác sĩ… hiện ra đó luôn là được". Cờ `XAC_NHAN_TEP_DOI_TAC = False`.
"""

from __future__ import annotations

import pathlib
from typing import Any

import asyncpg
import pytest

from clinicai.phieu_kham.ket_qua_chi_dinh import doc_ket_qua_theo_chi_dinh
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_xac_nhan_tep_ket_qua_db import (
    CLINIC_A,
    PDF_DUMMY,
    _tao_benh_nhan_va_visit,
    _tao_external_order,
    _tao_staff,
    pool,  # noqa: F401
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_doi_tac_tai_len_la_co_ket_qua_ngay_va_bao_bac_si(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: Any,
    tmp_path: pathlib.Path,
) -> None:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    assert tep_mod.XAC_NHAN_TEP_DOI_TAC is False
    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)
    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        pid, _aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)
        await conn.execute(
            "UPDATE visit SET attending_doctor_id = $2::uuid WHERE visit_id = $1::uuid",
            vid,
            doc.staff_id,
        )
    up = await TepKetQuaService(pool).tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="kq.pdf",
        service_order_id=oid,
    )
    tep = await pool.fetchrow(
        "SELECT xac_nhan_trang_thai, xac_nhan_ly_do FROM tep_ket_qua"
        " WHERE id = $1::uuid",
        up["id"],
    )
    assert tep["xac_nhan_trang_thai"] == "HOP_LE"
    assert tep["xac_nhan_ly_do"] == tep_mod.LY_DO_TU_XAC_NHAN
    # Không vào hàng chờ xác nhận.
    assert not await pool.fetchval(
        "SELECT count(*) FROM tep_ket_qua WHERE service_order_id = $1::uuid"
        " AND xac_nhan_trang_thai = 'CHO_XAC_NHAN'",
        oid,
    )
    # Phiếu khám mục C: chỉ định này CÓ KẾT QUẢ ngay.
    async with pool.acquire() as conn:
        ds = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC_A, visit_id=vid)
    assert [d["ket_qua_trang_thai"] for d in ds if d["service_order_id"] == oid] == [
        "CO_KET_QUA"
    ]
    # Chuông: bác sĩ chính được báo "đã vào hồ sơ", không phải "cần xác nhận".
    await chay_ben_nhan(pool, "chuong_thong_bao")
    # Kết quả ĐỐI TÁC (29/09/2026): một chuông / việc, "Có kết quả đối tác: …".
    chuong = await pool.fetchrow(
        "SELECT tieu_de, noi_dung FROM thong_bao WHERE nguon_id = $1"
        " AND nguoi_nhan_staff_id = $2::uuid",
        f"ket_qua_doi_tac:{oid}",
        doc.staff_id,
    )
    assert chuong is not None
    assert chuong["tieu_de"].startswith("Có kết quả đối tác:")
    assert "cần xác nhận" not in chuong["noi_dung"]
