"""Công tắc "Hiện mã ống" (Tuyền 09/11): phòng khám chưa bàn với đối tác cách ghi mã.

Tắt (mặc định) ⇒ mã KHÔNG ra khỏi máy chủ ở bất kỳ cửa đọc nào của bàn XN (bàn, lệnh
lấy mẫu, Xem quá trình), nhưng Postgres vẫn cấp mã Damm như cũ. Bật ⇒ như trước.

Mọi test đổi công tắc nằm trong tệp này (CI `--dist loadfile` ⇒ cùng một luồng), và
trả công tắc về TẮT sau mỗi test — tệp khác không được phụ thuộc vào trạng thái bật.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from clinicai.api.identity import StaffIdentity, _resolve_identity
from clinicai.core.database import get_db_pool
from clinicai.main import app
from clinicai.services.xet_nghiem import mau, qua_trinh, thu_ho
from clinicai.services.xet_nghiem.cai_dat_ban import doc_cai_dat
from clinicai.services.xet_nghiem.ma_mau import co_dang_ma
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai
from tests.services.test_thu_tien_xep_phong_mang_sang_db import Ca
from tests.services.test_tien_thuoc_cp1_db import tao_quay
from tests.services.test_xet_nghiem_ban_db import _hai_viec, _lam, _lam2, _ma_db

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

#: Mã ống có dạng M + 6 chữ số (5 số thứ tự + 1 số kiểm Damm).
MA_ONG = re.compile(r"M\d{6}")


async def _dat_cong_tac(pool: asyncpg.Pool, bat: bool) -> None:  # noqa: F811
    await pool.execute(
        "INSERT INTO xet_nghiem_cai_dat (clinic_id, hien_ma_ong) VALUES ($1::uuid, $2)"
        " ON CONFLICT (clinic_id) DO UPDATE SET hien_ma_ong = EXCLUDED.hien_ma_ong",
        CLINIC,
        bat,
    )


@pytest.fixture
async def tat_sau(pool: asyncpg.Pool) -> AsyncIterator[None]:  # noqa: F811
    await _dat_cong_tac(pool, False)
    yield
    await _dat_cong_tac(pool, False)


async def _goi(
    pool: asyncpg.Pool,  # noqa: F811
    ai: StaffIdentity,
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    async def _pool() -> AsyncIterator[asyncpg.Pool]:
        yield pool

    app.dependency_overrides[get_db_pool] = _pool
    app.dependency_overrides[_resolve_identity] = lambda: ai
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.request(method, url, json=body)
    finally:
        app.dependency_overrides.pop(get_db_pool, None)
        app.dependency_overrides.pop(_resolve_identity, None)
    return r.status_code, r.json()


async def _co_mau(pool: asyncpg.Pool) -> tuple[Ca, str, dict[str, Any]]:  # noqa: F811
    """Một việc đã thu + đã lấy mẫu, rồi huỷ mẫu và lấy lại (đủ câu quá trình)."""
    ca, o1, _o2 = await _hai_viec(pool)
    await _lam2(pool, thu_ho.ghi_nhan, ca, order_id=o1, tien_mat=300000)
    m = await _lam(pool, mau.lay_mau, ca, order_ids=[o1])
    await _lam2(
        pool, mau.huy_mau, ca, mau_id=m["mau_id"], loai="NHAP_SAI", ly_do="dán nhầm"
    )
    m2 = await _lam(pool, mau.lay_mau, ca, order_ids=[o1])
    return ca, o1, m2


async def test_mac_dinh_tat_khi_chua_co_dong_cai_dat(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        cd = await doc_cai_dat(conn, "00000000-0000-0000-0000-0000000000ee")
    assert cd.hien_ma_ong is False and cd.nguong_lay_mau_ngay == 2


async def test_tat_ban_khong_co_ma_nao_lay_mau_200_db_van_co_ma(
    pool: asyncpg.Pool,  # noqa: F811
    tat_sau: None,
) -> None:
    ca, o1, m2 = await _co_mau(pool)
    # (2) Lệnh lấy mẫu: thành công, không trả mã; DB vẫn có mã đúng Damm.
    assert m2["ma_mau"] is None and m2["mau_id"] and m2["hen_tra_ngay"]
    assert co_dang_ma(await _ma_db(pool, m2["mau_id"]))
    # (1) Cửa GET /ban: không một chuỗi mã nào trong cả JSON; cờ cho màn = false.
    code, ban = await _goi(pool, ca.bac_si, "GET", "/api/v1/xet-nghiem/ban")
    assert code == 200, ban
    assert ban["hien_ma_ong"] is False
    assert all(v["ma_mau"] is None for v in ban["viec"])
    # Quét JSON của việc + khách CỦA TEST NÀY (tệp test Drive chạy song song đặt tên
    # tệp theo mã — tên tệp đối tác đặt là dữ liệu thật, không che).
    cua_toi = {
        "viec": [v for v in ban["viec"] if v["order_id"] == o1],
        "khach": [k for k in ban["khach"] if o1 in k["order_ids"]],
    }
    assert len(cua_toi["viec"]) == 1 and len(cua_toi["khach"]) == 1
    assert not MA_ONG.search(json.dumps(cua_toi, ensure_ascii=False))
    # (4) Xem quá trình: không câu nào kèm mã; vẫn đủ bước lấy / huỷ / lấy lại.
    async with pool.acquire() as conn:
        viec = [d["viec"] for d in await qua_trinh.doc(conn, CLINIC, o1)]
    assert not any(MA_ONG.search(x) for x in viec)
    assert viec.count("Lấy mẫu, hẹn trả " + m2["hen_tra_ngay"].strftime("%d/%m")) == 2
    assert "Huỷ mẫu: dán nhầm" in viec


async def test_bat_moi_cho_hien_ma_ke_ca_mau_lay_luc_tat(
    pool: asyncpg.Pool,  # noqa: F811
    tat_sau: None,
) -> None:
    ca, o1, m2 = await _co_mau(pool)  # lấy lúc TẮT
    ma = await _ma_db(pool, m2["mau_id"])
    await _dat_cong_tac(pool, True)
    # (3) Bật ⇒ như cũ: bàn hiện mã (cả mẫu lấy lúc tắt), lệnh lấy mẫu trả mã.
    code, ban = await _goi(pool, ca.bac_si, "GET", "/api/v1/xet-nghiem/ban")
    assert code == 200 and ban["hien_ma_ong"] is True
    assert next(v for v in ban["viec"] if v["order_id"] == o1)["ma_mau"] == ma
    async with pool.acquire() as conn:
        viec = [d["viec"] for d in await qua_trinh.doc(conn, CLINIC, o1)]
    assert any(x.startswith(f"Lấy mẫu, mã ống {ma}") for x in viec)
    assert any(x.startswith("Huỷ mẫu M") and "dán nhầm" in x for x in viec)


async def test_cong_tac_chi_quan_ly_doi_duoc(
    pool: asyncpg.Pool,  # noqa: F811
    tat_sau: None,
) -> None:
    q = await tao_quay(pool)
    url = "/api/v1/xet-nghiem/cai-dat"
    body = {"nguong_lay_mau_ngay": 2, "hien_ma_ong": True}
    # (5) Không phải Quản lý ⇒ 403, công tắc không đổi.
    for vai in ("RECEPTION", "DOCTOR", "CSKH"):
        code, _ = await _goi(pool, await _nguoi_vai(q, vai), "PUT", url, body)
        assert code == 403
    async with pool.acquire() as conn:
        assert (await doc_cai_dat(conn, CLINIC)).hien_ma_ong is False
    # Quản lý bật được; danh sách trả lại mang cờ mới.
    ql = await _nguoi_vai(q, "MANAGEMENT")
    async with pool.acquire() as conn:
        cd = await doc_cai_dat(conn, CLINIC)
    body["nguong_lay_mau_ngay"] = cd.nguong_lay_mau_ngay
    code, ds = await _goi(pool, ql, "PUT", url, body)
    assert code == 200, ds
    assert ds["hien_ma_ong"] is True
    # Lưu ngưỡng KHÔNG gửi công tắc ⇒ công tắc giữ nguyên.
    code, ds = await _goi(
        pool, ql, "PUT", url, {"nguong_lay_mau_ngay": body["nguong_lay_mau_ngay"]}
    )
    assert code == 200 and ds["hien_ma_ong"] is True
