"""Nhánh ĐỐI TÁC (23/09/2026 khuya — "làm tiếp phòng thủ thuật và đối tác").

Hai lỗ hổng rà ra, cả hai về "đồng bộ sang bác sĩ chính":
  * xác nhận tệp đối tác HỢP LỆ → trước đây không ai được báo (chuông chỉ lúc
    TẢI LÊN, khi tệp còn chưa được xác nhận);
  * tệp bị TỪ CHỐI mà không còn tệp nào khác → chỉ định vẫn "đối tác đã gửi kết
    quả", rơi khỏi danh sách Cần làm của đối tác và nhắc quá hạn H7.
"""

from __future__ import annotations

import pathlib
from typing import Any

import asyncpg
import pytest

from clinicai.schemas.staff import Capability
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


@pytest.fixture(autouse=True)
def _bat_buoc_xac_nhan_tep_doi_tac(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bước xác nhận tệp đối tác OFF từ 23/09/2026 khuya (tệp vào thẳng phiếu
    khám). Bài này canh ĐƯỜNG CŨ (còn giữ, bật lại được) nên bật cờ."""
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(tep_mod, "XAC_NHAN_TEP_DOI_TAC", True)


async def _chuan_bi(pool: asyncpg.Pool, monkeypatch: Any, tmp: pathlib.Path) -> Any:  # noqa: F811
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)
    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        nv = await _tao_staff(
            conn, CLINIC_A, "NURSE", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        pid, _aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)
        await conn.execute(
            "UPDATE visit SET attending_doctor_id = $2::uuid WHERE visit_id = $1::uuid",
            vid,
            doc.staff_id,
        )
    return doc, partner, nv, pid, vid, oid


async def test_xac_nhan_hop_le_reo_bac_si_chinh_va_cskh(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: Any,
    tmp_path: pathlib.Path,
) -> None:
    doc, partner, nv, pid, _vid, oid = await _chuan_bi(pool, monkeypatch, tmp_path)
    svc = TepKetQuaService(pool)
    up = await svc.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="kq.pdf",
        service_order_id=oid,
    )
    await svc.xac_nhan_tep(identity=nv, tep_id=up["id"], trang_thai="HOP_LE")
    await chay_ben_nhan(pool, "chuong_thong_bao")
    nguon = f"result_file.confirmed:{up['id']}"
    rows = await pool.fetch(
        "SELECT vai_nhan, nguoi_nhan_staff_id::text AS nguoi FROM thong_bao"
        " WHERE nguon_id = $1",
        nguon,
    )
    assert {r["vai_nhan"] for r in rows if r["vai_nhan"]} == {"CSKH"}
    assert [r["nguoi"] for r in rows if r["nguoi"]] == [doc.staff_id]


async def test_tu_choi_tep_duy_nhat_thi_chi_dinh_ve_chua_co_ket_qua(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: Any,
    tmp_path: pathlib.Path,
) -> None:
    _doc, partner, nv, pid, _vid, oid = await _chuan_bi(pool, monkeypatch, tmp_path)
    svc = TepKetQuaService(pool)
    up = await svc.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="kq.pdf",
        service_order_id=oid,
    )
    assert await pool.fetchval(
        "SELECT ket_qua_luc IS NOT NULL FROM service_order WHERE id = $1::uuid", oid
    )
    await svc.xac_nhan_tep(
        identity=nv, tep_id=up["id"], trang_thai="TU_CHOI", ly_do="Sai tên khách"
    )
    assert not await pool.fetchval(
        "SELECT ket_qua_luc IS NOT NULL FROM service_order WHERE id = $1::uuid", oid
    )
    # Từ chối không réo ai.
    await chay_ben_nhan(pool, "chuong_thong_bao")
    assert not await pool.fetchval(
        "SELECT count(*) FROM thong_bao WHERE nguon_id = $1",
        f"result_file.confirmed:{up['id']}",
    )
