"""Lịch sử sửa MỌI phiếu kết quả — không cái gì sau đè cái trước (Tuyền chốt
07/10/2026). Trigger `trg_form_instance_lich_su` chụp bản CŨ mỗi khi `du_lieu` /
`trang_thai` đổi; bảng lịch sử chỉ thêm."""

from __future__ import annotations

import json

import asyncpg
import pytest

from clinicai.services.form_engine_service import FormEngineService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
    _kham_va_chi_dinh,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_moi_lan_doi_giu_ban_cu_va_lich_su_chi_them(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    fe = FormEngineService(pool)
    ph = await fe.mo_phieu(service_order_id=order, form_id="KQ_CHUNG", identity=ca.dd)

    def o(chu: str) -> dict[str, dict[str, str]]:
        return {"noi_dung": {"gia_tri": chu, "nguon": "USER"}}

    l1 = await fe.luu_nhap(
        phieu_id=ph["id"], du_lieu=o("bản 1"), expected_revision=0, identity=ca.dd
    )
    l2 = await fe.luu_nhap(
        phieu_id=ph["id"],
        du_lieu=o("bản 2"),
        expected_revision=l1["revision"],
        identity=ca.bac_si,
    )
    await fe.hoan_tat(
        phieu_id=ph["id"], expected_revision=l2["revision"], identity=ca.bac_si
    )

    ls = await pool.fetch(
        "SELECT revision, du_lieu, trang_thai, sua_boi::text AS ai"
        "  FROM form_instance_lich_su WHERE form_instance_id = $1::uuid"
        " ORDER BY revision",
        ph["id"],
    )
    # Ba lần đổi → ba bản cũ: mặc định (rev 0), "bản 1", "bản 2" (nháp trước
    # Hoàn tất). Không bản nào bị đè.
    assert [r["revision"] for r in ls] == [0, l1["revision"], l2["revision"]]
    chu = [json.loads(r["du_lieu"]).get("noi_dung", {}).get("gia_tri") for r in ls]
    assert chu[1:] == ["bản 1", "bản 2"]
    assert [r["trang_thai"] for r in ls] == ["DRAFT", "DRAFT", "DRAFT"]
    # Ai gây ra lần đổi: người gõ; lần Hoàn tất = người bấm.
    assert [r["ai"] for r in ls] == [
        ca.dd.staff_id,
        ca.bac_si.staff_id,
        ca.bac_si.staff_id,
    ]

    # Lịch sử chỉ thêm.
    with pytest.raises(asyncpg.RaiseError):
        await pool.execute(
            "UPDATE form_instance_lich_su SET du_lieu = '{}'::jsonb"
            " WHERE form_instance_id = $1::uuid",
            ph["id"],
        )
    with pytest.raises(asyncpg.RaiseError):
        await pool.execute(
            "DELETE FROM form_instance_lich_su WHERE form_instance_id = $1::uuid",
            ph["id"],
        )
    # Lần lưu y hệt / chỉ tăng revision (huỷ sửa…) không đẻ dòng.
    await pool.execute(
        "UPDATE form_instance SET revision = revision + 1 WHERE id = $1::uuid", ph["id"]
    )
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM form_instance_lich_su"
            " WHERE form_instance_id = $1::uuid",
            ph["id"],
        )
        == 3
    )
