"""Hoá đơn THEO LÔ = hoá đơn từng lượt (29/10/2026).

Bảng quầy thu tính hoá đơn cho cả danh sách lượt bằng một lần đọc
(``hoa_don_con_no_lo`` / ``hoa_don_thuoc_lo``) thay vì ~10 câu SQL mỗi lượt.
Đường một lượt (lệnh thu, check-out, công nợ) gọi lại chính hàm lô với một
lượt — bài này chốt rằng gộp NHIỀU lượt không làm lẫn dòng / tiền giữa các khách.
"""

from __future__ import annotations

import json

import asyncpg
import pytest

from clinicai.services.bill_service import (
    HoaDon,
    hoa_don_con_no,
    hoa_don_con_no_lo,
    hoa_don_thuoc_lo,
    tinh_hoa_don,
)
from tests.services.test_quay_thu_mot_hoa_don_db import _kich_ban

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _chuan(hd: HoaDon) -> str:
    return json.dumps(hd.cho_api(), sort_keys=True, default=str, ensure_ascii=False)


async def test_hoa_don_theo_lo_bang_tung_luot_khong_lan_khach(
    pool: asyncpg.Pool,
) -> None:
    # Ba khách: hai khách có SÂ + Soi (phòng khám thu) + HPV (đối tác), một
    # khách đã thu SÂ — tiền và dòng của mỗi người phải đúng của người ấy.
    q1, sa1, soi1, _hpv1 = await _kich_ban(pool)
    q2, _sa2, soi2, _hpv2 = await _kich_ban(pool)
    q3, *_ = await _kich_ban(pool)
    await pool.execute(
        "UPDATE service_order SET selection_status = 'SELECTED'"
        " WHERE id = ANY($1::uuid[])",
        [sa1, soi1],
    )
    await pool.execute(
        "UPDATE service_order SET selection_status = 'PENDING' WHERE id = $1::uuid",
        soi2,
    )
    vids = [q1.visit_id, q2.visit_id, q3.visit_id]
    cid = q1.thu_ngan.clinic_id
    async with pool.acquire() as conn:
        lo = await hoa_don_con_no_lo(conn, clinic_id=cid, visit_ids=vids)
        don = {v: await hoa_don_con_no(conn, clinic_id=cid, visit_id=v) for v in vids}
        # Hoá đơn DỰ KIẾN (chờ khách quyết tính như chọn) — chỉ khách 2 có.
        lo_q = await hoa_don_con_no_lo(
            conn, clinic_id=cid, visit_ids=vids, coi_nhu_chon={q2.visit_id: [soi2]}
        )
        don_q = await hoa_don_con_no(
            conn, clinic_id=cid, visit_id=q2.visit_id, coi_nhu_chon=[soi2]
        )
        thuoc = await hoa_don_thuoc_lo(conn, clinic_id=cid, visit_ids=vids)
        thuoc_don = {
            v: await tinh_hoa_don(conn, clinic_id=cid, visit_id=v, kind="thuoc")
            for v in vids
        }
        rong = await hoa_don_con_no_lo(conn, clinic_id=cid, visit_ids=[])
    assert set(lo) == set(vids)
    for v in vids:
        assert lo[v].visit_id == v
        assert _chuan(lo[v]) == _chuan(don[v]), v
        assert _chuan(thuoc[v]) == _chuan(thuoc_don[v]), v
        # Không dòng nào của khách khác lọt vào.
        ids = {d.source_id for d in [*lo[v].dong, *lo[v].dong_doi_tac]}
        for khac in vids:
            if khac != v:
                ids_khac = {
                    d.source_id for d in [*don[khac].dong, *don[khac].dong_doi_tac]
                }
                assert not ids & ids_khac, (v, khac)
    assert _chuan(lo_q[q2.visit_id]) == _chuan(don_q)
    assert soi2 in {d.source_id for d in lo_q[q2.visit_id].dong}
    assert soi2 not in {d.source_id for d in lo[q2.visit_id].dong}
    # Khách 1 / 3 không có chỉ định chờ quyết → dự kiến = thật.
    assert _chuan(lo_q[q1.visit_id]) == _chuan(lo[q1.visit_id])
    assert rong == {}
