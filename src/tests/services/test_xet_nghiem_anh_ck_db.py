"""Ảnh chuyển khoản của khoản THU HỘ đối tác (kế hoạch 4.4 phương án b, 05/11).

Bảng riêng `anh_chuyen_khoan_thu_ho` (không nối payment_cycle — câu chốt 1), cùng cơ
chế tệp với ảnh CK quầy thu: lưu → đọc → gỡ (ẩn, giữ vết); chỉ nhận ẢNH; khoản đã huỷ
không gắn được; phòng khám khác không đọc được; bàn trả ảnh theo khoản thu.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.services import media_service
from clinicai.services.nhan_tep_luong import TepDaNhan
from clinicai.services.xet_nghiem import anh_ck, thu_ho
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_nhieu_hinh_thuc_db import PNG
from tests.services.test_xet_nghiem_ban_db import _hai_viec, _lam2, _tt

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _tep(vps: Path, ten: str, noi_dung: bytes) -> TepDaNhan:
    tam = vps / ".tam" / ten
    tam.write_bytes(noi_dung)
    return TepDaNhan(
        duong=tam,
        so_byte=len(noi_dung),
        sha256=hashlib.sha256(noi_dung).hexdigest(),
        dau=noi_dung[:64],
        ten="ck.png",
    )


@pytest.fixture
def vps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    goc = tmp_path / "vps"
    (goc / ".tam").mkdir(parents=True)
    monkeypatch.setattr(media_service, "MEDIA_LOCAL_ROOT", goc)
    monkeypatch.setattr(media_service, "MEDIA_ROOT", tmp_path / "cfs")
    return goc


async def test_anh_ck_thu_ho_luu_doc_go_va_ban_tra_anh(
    pool: asyncpg.Pool,  # noqa: F811
    vps: Path,
) -> None:
    ca, o1, _ = await _hai_viec(pool)
    await _lam2(pool, thu_ho.ghi_nhan, ca, order_id=o1, chuyen_khoan=350000)
    thu_id = (await _tt(pool, ca, o1))["thu_id"]
    kq = await anh_ck.tai_len(pool, ca.bac_si, thu_id, _tep(vps, "a.part", PNG))
    noi_dung, mime = await anh_ck.doc(pool, ca.bac_si, kq["id"])
    assert (noi_dung, mime) == (PNG, "image/png")
    assert [a["id"] for a in (await _tt(pool, ca, o1))["anh_ck"]] == [kq["id"]]
    # Không phải ảnh ⇒ 422; khoản rác ⇒ 422 (không ném 500).
    with pytest.raises(ValidationError):
        await anh_ck.tai_len(
            pool, ca.bac_si, thu_id, _tep(vps, "b.part", b"%PDF-1.4 x")
        )
    with pytest.raises(ValidationError):
        await anh_ck.tai_len(pool, ca.bac_si, "rac", _tep(vps, "c.part", PNG))
    # Gỡ = ẩn khỏi bàn, dòng + tệp giữ (vết).
    await anh_ck.go(pool, ca.bac_si, kq["id"])
    assert (await _tt(pool, ca, o1))["anh_ck"] == []
    assert await pool.fetchval(
        "SELECT go_luc IS NOT NULL FROM anh_chuyen_khoan_thu_ho WHERE id = $1::uuid",
        kq["id"],
    )
    # Phòng khám khác không đọc được ảnh này.
    la = replace(ca.bac_si, clinic_id="00000000-0000-0000-0000-0000000000ff")
    with pytest.raises(NotFoundError):
        await anh_ck.doc(pool, la, kq["id"])


async def test_anh_ck_khong_gan_vao_khoan_da_huy(
    pool: asyncpg.Pool,  # noqa: F811
    vps: Path,
) -> None:
    ca, o1, _ = await _hai_viec(pool)
    await _lam2(pool, thu_ho.ghi_nhan, ca, order_id=o1, chuyen_khoan=350000)
    thu_id = (await _tt(pool, ca, o1))["thu_id"]
    await _lam2(pool, thu_ho.huy, ca, order_id=o1, ly_do="ghi nhầm khách")
    with pytest.raises(ConflictError, match="đã huỷ"):
        await anh_ck.tai_len(pool, ca.bac_si, thu_id, _tep(vps, "d.part", PNG))
    # Không có dòng nào, không đụng sổ tiền phòng khám.
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM anh_chuyen_khoan_thu_ho"
            " WHERE thanh_toan_id = $1::uuid",
            thu_id,
        )
        == 0
    )
