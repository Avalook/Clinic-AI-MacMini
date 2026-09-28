"""Mốc "đã trả kết quả" (CSKH) KHÔNG chặn tải tệp nữa (28/09/2026).

Lỗi thật trên màn Đối tác: khách đã có mốc TRA_KQ từ trước (xét theo KHÁCH) →
đối tác tải tài liệu cho một việc còn "chờ tài liệu" bị báo "Việc này đã xác
nhận trả kết quả". Tuyền: "không cần chặn cskh cái gì nữa" — mốc TRA_KQ có
trước hay sau các tệp, tải lên và tải thêm đều được.
"""

from __future__ import annotations

import pathlib
from typing import Any

import asyncpg
import pytest

from clinicai.services.tep_ket_qua_service import TepKetQuaService
from tests.services.test_xac_nhan_tep_ket_qua_db import (
    CLINIC_A,
    PDF_DUMMY,
    _tao_benh_nhan_va_visit,
    _tao_external_order,
    _tao_staff,
    pool,  # noqa: F401
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_ket_qua_moi_cua_chi_dinh_khong_bi_moc_tra_kq_cu_chan(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: Any,
    tmp_path: pathlib.Path,
) -> None:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)
    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        cskh = await _tao_staff(conn, CLINIC_A, "CSKH")
        pid, _aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)
        # CSKH đã bấm "đã trả kết quả" cho khách (mốc theo KHÁCH, còn hiệu lực).
        await conn.execute(
            "INSERT INTO tuong_tac_cskh (clinic_id, clinic_patient_id, loai, kenh,"
            " ket_qua, nhan_vien_staff_id) VALUES ($1::uuid, $2::uuid, 'TRA_KQ',"
            " 'GOI', 'DA_LIEN_HE', $3::uuid)",
            CLINIC_A,
            pid,
            cskh.staff_id,
        )
    svc = TepKetQuaService(pool)

    async def _tai(ten: str) -> None:
        await svc.tai_len(
            identity=partner,
            clinic_patient_id=pid,
            data=PDF_DUMMY,
            ten_hien_thi=ten,
            service_order_id=oid,
        )

    # Mốc trả kết quả có TRƯỚC các tệp → gửi và gửi thêm đều được.
    await _tai("kq.pdf")
    await _tai("kq-2.pdf")
    # Mốc trả kết quả SAU tệp cuối → vẫn tải thêm được (không còn chốt).
    await pool.execute(
        "INSERT INTO tuong_tac_cskh (clinic_id, clinic_patient_id, loai, kenh,"
        " ket_qua, nhan_vien_staff_id, xay_ra_luc) VALUES ($1::uuid, $2::uuid,"
        " 'TRA_KQ', 'GOI', 'DA_LIEN_HE', $3::uuid, now() + interval '1 second')",
        CLINIC_A,
        pid,
        cskh.staff_id,
    )
    await _tai("kq-3.pdf")
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM tep_ket_qua WHERE service_order_id = $1::uuid", oid
        )
        == 3
    )
