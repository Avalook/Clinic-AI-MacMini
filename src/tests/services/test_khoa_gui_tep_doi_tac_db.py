"""Khoá hành vi ĐANG ĐÚNG trước khi đụng (ADR-0015, kế hoạch chặng 0, PR 0.3, ý 2):
Postgres TỪ CHỐI đánh dấu đã gửi một tệp kết quả của đối tác đang `CHO_XAC_NHAN` —
kể cả khi ghi thẳng bảng (script, cửa quên kiểm). Đây là cửa chống gửi nhầm kết
quả khách này cho khách khác; câu chốt 4 giữ nó nguyên ("Đúng người, gửi").

Trigger: `tep_ket_qua_gui_phai_duoc_cho_phep` (bản 20260923000021). Bài
`test_t9_db_blocks_send_after_thu_hoi` đã canh `THU_HOI`; bài này canh `CHO_XAC_NHAN`.
"""

from __future__ import annotations

import pathlib

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
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

# KHÔNG dùng `pytest_plugins` với module bài xác nhận tệp: nó có fixture autouse bật
# cờ dưới đây — nạp làm plugin là bật cho MỌI test của phiên (soát 05/11 bắt được).


async def test_db_tu_choi_gui_tep_doi_tac_cho_xac_nhan(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    # Bước xác nhận tệp đối tác đang TẮT trên prod từ 23/09 (tệp không vào
    # CHO_XAC_NHAN); bài canh cửa DB nên bật cờ để có tệp ở trạng thái ấy.
    monkeypatch.setattr(tep_mod, "XAC_NHAN_TEP_DOI_TAC", True)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        cskh = await _tao_staff(conn, CLINIC_A, "CSKH")
        pid, _aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)

    svc = TepKetQuaService(pool)
    tep_id = (
        await svc.tai_len(
            identity=partner,
            clinic_patient_id=pid,
            data=PDF_DUMMY,
            ten_hien_thi="kq-doi-tac.pdf",
            service_order_id=oid,
        )
    )["id"]
    assert (
        await pool.fetchval(
            "SELECT xac_nhan_trang_thai FROM tep_ket_qua WHERE id = $1::uuid", tep_id
        )
        == "CHO_XAC_NHAN"
    )

    # Ghi thẳng bảng — trigger phải chặn.
    with pytest.raises(
        asyncpg.CheckViolationError, match="CHO_XAC_NHAN.*không được phép gửi"
    ):
        await pool.execute(
            "UPDATE tep_ket_qua SET gui_luc = now(), gui_boi_staff_id = $1::uuid,"
            " gui_kenh = 'ZALO' WHERE id = $2::uuid",
            cskh.staff_id,
            tep_id,
        )
    # Qua dịch vụ — báo 409, không 500.
    with pytest.raises(ConflictError):
        await svc.danh_dau_da_gui(identity=cskh, tep_id=tep_id, kenh="ZALO")

    assert (
        await pool.fetchval(
            "SELECT gui_luc FROM tep_ket_qua WHERE id = $1::uuid", tep_id
        )
        is None
    )
