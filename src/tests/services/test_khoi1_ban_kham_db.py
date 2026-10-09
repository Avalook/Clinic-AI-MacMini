"""Khối 1 theo loại lượt — lượt Thủ thuật chọn thủ thuật đã làm = LÀM TẠI BÀN
KHÁM, lượt Điều trị mở đủ bốn khối (Tuyền chốt 09/10/2026), trên Postgres thật.

    scripts/test-nhanh.sh src/tests/services/test_khoi1_ban_kham_db.py

Chọn thủ thuật khi chưa thu → chỉ định có, Bắt đầu bị cửa tiền chặn kèm câu
"chưa thu" + mời tick tại chỗ; tick → làm được → Xong → check-out chặn nợ; hoàn
tác Bắt đầu / Xong không đụng tiền; lượt không phải Thủ thuật bị từ chối.
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.core.exceptions import ValidationError
from clinicai.phieu_kham.ket_qua_chi_dinh import doc_ket_qua_theo_chi_dinh
from clinicai.services import dieu_tri_ban_kham as dt
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.finance_gate import CAU_CHUA_THU
from clinicai.services.lam_truoc_thu_sau import LamTruocThuSauService
from clinicai.services.phieu_kham_service import PhieuKhamService, kiem_quyen_core
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_dieu_tri_ban_kham_db import (
    _bam,
    _ke,
    _laser,
    _lich_ban_kham,
    _tien,
    _vao_kham,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _dung,
    _khoa,
)
from tests.services.test_thu_truoc_lam_truoc_tick_db import day_thu_truoc

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture(autouse=True)
async def _thu_truoc(pool: asyncpg.Pool):  # type: ignore[no-untyped-def]  # noqa: F811
    async with day_thu_truoc(pool, True):
        yield


async def _loai_thu_thuat(pool: asyncpg.Pool) -> str:  # noqa: F811
    """Loại khám có phiếu THU_THUAT (khối 1 THU_THUAT) — riêng bài, qua bác sĩ
    chính (không phụ thuộc cách đi thẳng của loại seed)."""
    return str(
        await pool.fetchval(
            "INSERT INTO service_type (clinic_id, code, name, is_active, form_code)"
            " VALUES ($1::uuid, $2, $3, true, 'THU_THUAT') RETURNING id::text",
            CLINIC,
            f"TTK1-{uuid.uuid4().hex[:8]}",
            "Thủ thuật khối 1",
        )
    )


async def _ma_thu_thuat(pool: asyncpg.Pool) -> str:  # noqa: F811
    ma = f"TTK1-{uuid.uuid4().hex[:8]}"
    await pool.execute(
        'INSERT INTO service_price (clinic_id, "group", service_code, name,'
        " unit_price, billing_owner, node_code) VALUES ($1::uuid, 'dich_vu', $2,"
        " $3, 700000, 'CLINIC', 'DICHVU-THUTHUAT')",
        CLINIC,
        ma,
        f"Tháo que {ma}",
    )
    return ma


async def _chon(pool: asyncpg.Pool, ca: Ca, visit: str, ma: str) -> dict[str, Any]:  # noqa: F811
    return await dt.chon_thu_thuat(
        pool,
        identity=ca.bac_si,
        visit_id=visit,
        service_code=ma,
        idempotency_key=_khoa(),
    )


async def _goi(pool: asyncpg.Pool, ca: Ca, visit: str) -> dict[str, Any]:  # noqa: F811
    return await dt.doc_the(pool, identity=ca.bac_si, visit_id=visit)


async def test_chon_thu_thuat_chua_thu_moi_tick_roi_lam_xong_check_out_chan_no(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    await _lich_ban_kham(pool, ca)
    visit = await _check_in(
        pool, ca, await _benh_nhan(pool, ca), await _loai_thu_thuat(pool)
    )
    ma = await _ma_thu_thuat(pool)

    # Chưa bắt đầu khám: chưa có phiên → báo bấm Bắt đầu khám trước.
    with pytest.raises(ValidationError) as e:
        await _chon(pool, ca, visit, ma)
    assert str(e.value) == dt.CAU_CHUA_BAT_DAU_KHAM
    await _vao_kham(pool, ca, visit)

    # 1. Chưa thu, chưa tick → chỉ định CÓ, Bắt đầu bị chặn bằng câu cửa tiền.
    kq = await _chon(pool, ca, visit, ma)
    order = kq["order_id"]
    assert kq["bat_dau"] is False and kq["ly_do"] == CAU_CHUA_THU
    goi = await _goi(pool, ca, visit)
    assert goi["khoi1"] == "THU_THUAT" and goi["nhac_tick"] is True
    [t] = [t for t in goi["the"] if t["order_id"] == order]
    assert t["trang_thai"] == "CHUA_LAM" and t["ly_do_khong_lam"] == CAU_CHUA_THU
    assert t["nhac_tick"] is True and t["lam_duoc"] is False
    # Cờ `ban_kham` (thẻ về khối 1), `dieu_tri` giữ nguyên (bản in).
    async with pool.acquire() as conn:
        ds = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC, visit_id=visit)
    [c] = [c for c in ds if c["service_order_id"] == order]
    assert c["ban_kham"] is True and c["dieu_tri"] is False

    # Chọn lại đúng thủ thuật ấy: không đẻ dòng thứ hai.
    lai = await _chon(pool, ca, visit, ma)
    assert lai["order_id"] == order
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM service_order WHERE visit_id = $1::uuid"
            " AND service_code = $2 AND exec_status <> 'cancelled'",
            visit,
            ma,
        )
        == 1
    )

    # 2. Tick tại chỗ → ô tự ẩn, thẻ làm được → Bắt đầu → Xong.
    await LamTruocThuSauService(pool).dat(visit_id=visit, bat=True, identity=ca.bac_si)
    goi = await _goi(pool, ca, visit)
    [t] = [t for t in goi["the"] if t["order_id"] == order]
    assert goi["nhac_tick"] is False and t["nhac_tick"] is False
    assert t["lam_duoc"] is True
    tien_truoc = await _tien(pool, order)
    await _bam(pool, ca, visit, t, "lam")
    [t] = [t for t in (await _goi(pool, ca, visit))["the"] if t["order_id"] == order]
    assert t["trang_thai"] == "DANG_LAM_BAN_KHAM"

    # 3. Hoàn tác Bắt đầu → chờ làm; Bắt đầu lại; Xong; hoàn tác Xong; Xong lại.
    #    Tiền không đổi suốt (hoá đơn không bị đụng).
    await _bam(pool, ca, visit, t, "huy-lam")
    [t] = [t for t in (await _goi(pool, ca, visit))["the"] if t["order_id"] == order]
    assert t["trang_thai"] == "CHUA_LAM" and await _tien(pool, order) == tien_truoc
    await _bam(pool, ca, visit, t, "lam")
    [t] = [t for t in (await _goi(pool, ca, visit))["the"] if t["order_id"] == order]
    await _bam(pool, ca, visit, t, "xong")
    [t] = [t for t in (await _goi(pool, ca, visit))["the"] if t["order_id"] == order]
    assert t["trang_thai"] == "XONG" and t["hoan_tac_xong_duoc"]
    await _bam(pool, ca, visit, t, "hoan-tac-xong")
    [t] = [t for t in (await _goi(pool, ca, visit))["the"] if t["order_id"] == order]
    assert t["trang_thai"] == "DANG_LAM_BAN_KHAM"
    assert await _tien(pool, order) == tien_truoc
    await _bam(pool, ca, visit, t, "xong")
    assert await _tien(pool, order) == tien_truoc == "DUE"

    # 4. Check-out: đã làm chưa thu = NỢ, chặn.
    ss = await CheckoutService(pool).readiness(identity=ca.le_tan, visit_id=visit)
    assert order in [d["source_id"] for d in ss["no_khi_ve"]["dong"]]
    assert ss["no_khi_ve"]["chan"] is True and ss["can_close"] is False


async def test_luot_khong_phai_thu_thuat_bi_tu_choi_va_thu_thuat_ke_thuong_di_phong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    await _lich_ban_kham(pool, ca)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _vao_kham(pool, ca, visit)
    ma = await _ma_thu_thuat(pool)
    with pytest.raises(ValidationError) as e:
        await _chon(pool, ca, visit, ma)
    assert str(e.value) == dt.CAU_KHONG_PHAI_LUOT_THU_THUAT

    # Lượt khám thường kê thủ thuật: KHÔNG phải thẻ bàn khám (vẫn đi phòng),
    # lệnh Làm tại bàn khám bị từ chối.
    order = (await _ke(pool, ca, con, ma))["order_ids"][0]
    goi = await _goi(pool, ca, visit)
    assert goi["khoi1"] is None
    assert order not in [t["order_id"] for t in goi["the"]]
    async with pool.acquire() as conn:
        ds = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC, visit_id=visit)
    [c] = [c for c in ds if c["service_order_id"] == order]
    assert c["ban_kham"] is False
    with pytest.raises(ValidationError) as e:
        await dt.thao_tac(
            pool,
            identity=ca.bac_si,
            visit_id=visit,
            order_id=order,
            lenh="lam",
            expected_execution_revision=0,
        )
    assert str(e.value) == dt.CAU_KHONG_PHAI_BAN_KHAM


async def test_luot_thu_thuat_chon_ma_khong_phai_thu_thuat_bi_tu_choi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(
        pool, ca, await _benh_nhan(pool, ca), await _loai_thu_thuat(pool)
    )
    await _vao_kham(pool, ca, visit)
    with pytest.raises(ValidationError) as e:
        await _chon(pool, ca, visit, ca.ma_dv)  # siêu âm
    assert str(e.value) == dt.CAU_KHONG_PHAI_THU_THUAT


async def _loai_co_phieu(pool: asyncpg.Pool, phieu: str) -> str:  # noqa: F811
    """Loại khám gắn phiếu ``phieu`` như prod (Phụ khoa → PK, Sàn chậu, Thủ
    thuật). Riêng bài: seed của DB test không gắn phiếu cho loại seed."""
    return str(
        await pool.fetchval(
            "INSERT INTO service_type (clinic_id, code, name, is_active, form_code)"
            " VALUES ($1::uuid, $2, $3, true, $4) RETURNING id::text",
            CLINIC,
            f"K1-{phieu}-{uuid.uuid4().hex[:8]}",
            f"Loại {phieu}",
            phieu,
        )
    )


@pytest.mark.parametrize(
    ("khoi1", "phieu"),
    [
        (None, "PK"),  # Phụ khoa — phiếu riêng
        (None, "SAN_CHAU"),  # Sàn chậu chuyên sâu — như khám thường
        ("THU_THUAT", "THU_THUAT"),
    ],
)
async def test_doc_luot_tra_khoi1_theo_loai_kham(
    pool: asyncpg.Pool,  # noqa: F811
    khoi1: str | None,
    phieu: str,
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(
        pool, ca, await _benh_nhan(pool, ca), await _loai_co_phieu(pool, phieu)
    )
    kq = await PhieuKhamService(pool, kiem_quyen=kiem_quyen_core).doc_luot(
        visit_id=visit, form_id=None, identity=ca.bac_si
    )
    assert kq["form_id"] == phieu and kq["khoi1"] == khoi1


async def test_luot_dieu_tri_mo_du_bon_khoi_khong_bat_chon_phieu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    laser = await _laser(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), laser["loai"])
    kq = await PhieuKhamService(pool, kiem_quyen=kiem_quyen_core).doc_luot(
        visit_id=visit, form_id=None, identity=ca.bac_si
    )
    # Không còn "chọn phiếu": mở khung chung (A/B bị ẩn ở màn), khối 1 Điều trị.
    assert "chon_duoc" not in kq
    assert kq["khoi1"] == "DIEU_TRI" and kq["form_id"] == "THU_THUAT"
    assert kq["mac_dinh_theo_loai_kham"] is False
    goi = await _goi(pool, ca, visit)
    assert goi["khoi1"] == "DIEU_TRI"
