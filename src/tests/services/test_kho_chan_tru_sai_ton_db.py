"""Hai đường làm sổ kho lệch kệ thật (rà vòng đời thuốc 27/10/2026).

A1 — Kiểm kho theo lô khi còn thuốc ĐÃ GIAO CHƯA GẮN LÔ: kệ đã thiếu nhưng sổ
chưa trừ. Ghi lệch theo số đếm rồi gắn lô sau = trừ hai lần (kệ 7, sổ 10, đếm 7
→ −3, gắn lô −3 → sổ 4). Kiểm CA đã chặn từ trước; kiểm KHO nay chặn cùng luật.

A2 — HUỶ bớt vào phần ĐÃ BÁN CHƯA GIAO (hoặc thuốc trả chờ kiểm): so với tồn
vật lý thì lọt, khách quay lại lấy thì không còn thuốc. Nay so với
`drug_batch_kha_dung`; huỷ cả lô hết hạn cũng vậy. ĐIỀU CHỈNH thì vẫn ghi theo
số đếm (kệ đã thiếu thì chặn chỉ làm sổ sai) — xem CP3
`test_paid_chua_ban_duoc_van_giu_phan_da_phan_lo`.

Mỗi lỗi một bài cụ thể + một bài giả lập ngẫu nhiên giữ mô hình "kệ thật" độc
lập với sổ: mọi thay đổi tồn đi qua service thật, SQL chỉ đọc (và lùi hạn lô).
"""

from __future__ import annotations

# ruff: noqa: F811 — fixture q được import từ CP1.
import random
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.core.clock import hom_nay_vn
from clinicai.services import kho_thuoc_service as kho
from clinicai.services import lo_thuoc_service as lo_svc
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_tien_thuoc_cp1_db import (  # noqa: F401
    Quay,
    _nhap_lo,
    _thuoc,
    q,
)
from tests.services.test_tien_thuoc_cp3_db import _chon, _dong_da_xac_dinh, _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _ton(q: Quay, lo: str) -> Decimal:
    return Decimal(
        str(
            await q.pool.fetchval(
                "SELECT quantity_on_hand FROM drug_batch WHERE id = $1::uuid", lo
            )
        )
    )


async def _kiem(q: Quay, lo: str, thuc_te: Decimal | int) -> dict[str, Any]:
    return await kho.kiem_kho(
        q.pool,
        identity=q.duoc_si,
        khoa_gui=uuid.uuid4().hex,
        dong=[{"drug_batch_id": lo, "thuc_te": thuc_te}],
    )


async def _cho_gan(q: Quay, rx: str) -> list[str]:
    return [
        r["id"]
        for r in await q.pool.fetch(
            "SELECT id::text FROM thuoc_giao_chua_gan_lo "
            "WHERE prescription_id = $1::uuid AND drug_batch_id IS NULL ORDER BY id",
            rx,
        )
    ]


async def _giao_khong_lo(q: Quay, rx: str, so: int) -> None:
    await PharmacyService(q.pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=None, so_luong=so
    )


async def _so_phieu_kiem(q: Quay) -> int:
    return int(
        await q.pool.fetchval(
            "SELECT count(*) FROM phieu_kho"
            " WHERE clinic_id = $1::uuid AND loai = 'KIEM'",
            q.duoc_si.clinic_id,
        )
    )


# ── A1: kiểm kho theo lô khi còn giao chưa gắn lô ────────────────────────────


@pytest.fixture
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    # Chế độ prod: lần thu không gắn lô → quầy giao không lô được.
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


@pytest.mark.usefixtures("_thu_khong_cho_kho")
async def test_kiem_kho_chan_khi_con_giao_chua_gan_lo_roi_gan_xong_thi_kiem_duoc(
    q: Quay,
) -> None:
    svc = PharmacyService(q.pool)
    rx, drug = await _dong_da_xac_dinh(q, 3)
    await _thu(q)
    # Quầy giao 3 từ hộp chưa nhập máy, rồi mới nhập lô 10 (hộp ấy).
    await _giao_khong_lo(q, rx, 3)
    lo = await _nhap_lo(q, drug, 10)
    # Kệ thật còn 7, sổ còn 10 (chưa gắn lô). Đếm 7 → phải chặn, không ghi gì.
    truoc = await _so_phieu_kiem(q)
    with pytest.raises(ConflictError, match="chưa gắn lô"):
        await _kiem(q, lo, 7)
    assert await _ton(q, lo) == 10
    assert await _so_phieu_kiem(q) == truoc, "bị chặn thì không để lại phiếu"

    # Đếm khớp sổ (lệch 0) không ghi điều chỉnh nào → không cần chặn.
    kq = await _kiem(q, lo, 10)
    assert kq["dong"][0]["lech"] == 0

    [dong] = await _cho_gan(q, rx)
    await svc.gan_lo_da_giao(identity=q.duoc_si, dong_id=dong, drug_batch_id=lo)
    assert await _ton(q, lo) == 7
    # Gắn xong: kiểm lại theo kệ thật — lệch 0, sổ = kệ.
    kq = await _kiem(q, lo, 7)
    assert kq["dong"][0]["lech"] == 0
    assert await _ton(q, lo) == 7


@pytest.mark.usefixtures("_thu_khong_cho_kho")
async def test_kiem_kho_khong_chan_thuoc_khac(q: Quay) -> None:
    # Giao chưa gắn lô của thuốc A không khoá kiểm kho thuốc B.
    rx, drug_a = await _dong_da_xac_dinh(q, 2)
    await _thu(q)
    await _giao_khong_lo(q, rx, 2)
    await _nhap_lo(q, drug_a, 10)
    drug_b = await _thuoc(q, ten=f"Thuốc B {uuid.uuid4().hex[:8]}")
    lo_b = await _nhap_lo(q, drug_b, 10)
    assert await _cho_gan(q, rx)
    kq = await _kiem(q, lo_b, 8)
    assert kq["dong"][0]["lech"] == -2
    assert await _ton(q, lo_b) == 8


@pytest.mark.usefixtures("_thu_khong_cho_kho")
@pytest.mark.parametrize("seed", range(20))
async def test_gia_lap_kiem_kho_va_gan_lo_so_luon_khop_ke(q: Quay, seed: int) -> None:
    """Kệ thật = sổ − phần đã giao chưa gắn lô, sau MỌI bước. Trước bản sửa,
    chuỗi "giao không lô → kiểm theo kệ → gắn lô" làm sổ thấp hơn kệ.

    Giao TRƯỚC khi có lô (quầy bán từ hộp chưa nhập máy) mới chắc có hàng chờ:
    có lô bán được thì giao tự chọn lô, trừ kho ngay. Giao sau khi có lô thì
    chạy được cả hai kiểu — mô hình chỉ cần kệ −1."""
    rng = random.Random(seed)
    svc = PharmacyService(q.pool)
    rx, drug = await _dong_da_xac_dinh(q, 10)
    await _thu(q)
    da_giao = rng.randint(1, 4)
    for _ in range(da_giao):
        await _giao_khong_lo(q, rx, 1)
    lo = await _nhap_lo(q, drug, 20)
    ke = Decimal(20 - da_giao)
    trace: tuple[str, ...] = ()
    for buoc in range(12):
        lenh = rng.choice(("giao", "giao", "gan", "kiem", "kiem", "huy", "nhap_le"))
        trace = (*trace, f"seed={seed} buoc={buoc} {lenh}")
        cho = await _cho_gan(q, rx)
        so = await _ton(q, lo)
        try:
            if lenh == "giao" and da_giao < 10:
                await svc.cap_phat(
                    identity=q.duoc_si,
                    prescription_id=rx,
                    drug_batch_id=None,
                    so_luong=1,
                )
                ke -= 1
                da_giao += 1
            elif lenh == "gan" and cho:
                await svc.gan_lo_da_giao(
                    identity=q.duoc_si, dong_id=cho[0], drug_batch_id=lo
                )
            elif lenh == "kiem":
                if cho and ke != so:
                    with pytest.raises(ConflictError, match="chưa gắn lô"):
                        await _kiem(q, lo, ke)
                    assert await _ton(q, lo) == so, trace
                else:
                    await _kiem(q, lo, ke)
            elif lenh == "huy" and ke > 0:
                await svc.huy(
                    identity=q.duoc_si, drug_batch_id=lo, so_luong=1, ly_do="Vỡ"
                )
                ke -= 1
            elif lenh == "nhap_le":
                await svc.dieu_chinh(
                    identity=q.duoc_si, drug_batch_id=lo, so_luong=2, ly_do="Thêm"
                )
                ke += 2
        except Exception as exc:
            pytest.fail(f"Chuỗi gây lỗi: {trace!r}\n{type(exc).__name__}: {exc}")
        con_cho = await q.pool.fetchval(
            "SELECT coalesce(sum(so_luong), 0) FROM thuoc_giao_chua_gan_lo "
            "WHERE prescription_id = $1::uuid AND drug_batch_id IS NULL",
            rx,
        )
        assert await _ton(q, lo) - Decimal(str(con_cho)) == ke, trace
    # Gắn hết phần còn treo: sổ phải đúng bằng kệ.
    for dong in await _cho_gan(q, rx):
        await svc.gan_lo_da_giao(identity=q.duoc_si, dong_id=dong, drug_batch_id=lo)
    assert await _ton(q, lo) == ke, trace


# ── A2: điều chỉnh / huỷ không lấn phần đã bán chưa giao ─────────────────────


@pytest.fixture
def _thu_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    # Lần thu gắn lô → phần đã bán chưa giao bị trừ khỏi khả dụng của lô.
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")


async def _ban_chua_giao(q: Quay, ton: int, ban: int) -> tuple[str, str]:
    rx, drug = await _dong_da_xac_dinh(q, ban)
    lo = await _nhap_lo(q, drug, ton)
    await _chon(q, rx, lo, ban)
    await _thu(q)
    return rx, lo


@pytest.mark.usefixtures("_thu_cho_kho")
async def test_huy_khong_lan_phan_da_ban_chua_giao(q: Quay) -> None:
    svc = PharmacyService(q.pool)
    rx, lo = await _ban_chua_giao(q, ton=10, ban=6)
    # Kệ 10, trong đó 6 khách đã trả tiền chưa lấy → huỷ tối đa 4.
    with pytest.raises(ValidationError, match="tối đa 4"):
        await svc.huy(identity=q.duoc_si, drug_batch_id=lo, so_luong=5, ly_do="Vỡ")
    assert await _ton(q, lo) == 10
    await svc.huy(identity=q.duoc_si, drug_batch_id=lo, so_luong=4, ly_do="Vỡ")
    assert await _ton(q, lo) == 6
    # Khách quay lại lấy đủ 6 từ đúng lô đã bán.
    await svc.cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=6
    )
    assert await _ton(q, lo) == 0


@pytest.mark.usefixtures("_thu_cho_kho")
async def test_dieu_chinh_van_ghi_so_dem_that_du_lan_phan_da_ban(q: Quay) -> None:
    svc = PharmacyService(q.pool)
    _, lo = await _ban_chua_giao(q, ton=10, ban=6)
    # Đếm kệ chỉ còn 5: sổ phải ghi đúng 5, không chặn.
    await svc.dieu_chinh(
        identity=q.duoc_si, drug_batch_id=lo, so_luong=-5, ly_do="Đếm thiếu"
    )
    assert await _ton(q, lo) == 5


@pytest.mark.usefixtures("_thu_cho_kho")
async def test_huy_lo_het_han_chan_khi_con_ban_chua_giao(q: Quay) -> None:
    _, lo = await _ban_chua_giao(q, ton=10, ban=3)
    async with q.pool.acquire() as conn:
        await conn.execute(
            "UPDATE drug_batch SET expiry_date = $2 WHERE id = $1::uuid",
            lo,
            hom_nay_vn() - timedelta(days=1),
        )
    with pytest.raises(ConflictError, match="Lô này còn 3"):
        await lo_svc.huy_lo(
            q.pool,
            identity=q.duoc_si,
            drug_batch_id=lo,
            ly_do="Hết hạn",
            khoa_gui=str(uuid.uuid4()),
        )
    assert await _ton(q, lo) == 10


@pytest.mark.usefixtures("_thu_cho_kho")
@pytest.mark.parametrize("seed", range(20))
async def test_gia_lap_bot_kho_luon_con_du_phan_da_ban(q: Quay, seed: int) -> None:
    """Sau MỌI bước: tồn lô ≥ phần khách đã trả tiền chưa lấy; cuối cùng giao nốt
    phải được. Trước bản sửa, huỷ bớt lẹm vào phần đã bán."""
    rng = random.Random(seed)
    svc = PharmacyService(q.pool)
    rx, lo = await _ban_chua_giao(q, ton=12, ban=8)
    con_no = 8
    trace: tuple[str, ...] = ()
    for buoc in range(12):
        lenh = rng.choice(("huy", "huy", "giao", "them"))
        luong = rng.randint(1, 4)
        trace = (*trace, f"seed={seed} buoc={buoc} {lenh} so={luong}")
        ton = await _ton(q, lo)
        try:
            if lenh == "huy":
                duoc = ton - con_no >= luong
                try:
                    await svc.huy(
                        identity=q.duoc_si,
                        drug_batch_id=lo,
                        so_luong=luong,
                        ly_do="Hỏng",
                    )
                except ValidationError:
                    assert not duoc, trace
                    assert await _ton(q, lo) == ton, trace
                else:
                    assert duoc, trace
                    assert await _ton(q, lo) == ton - luong, trace
            elif lenh == "giao" and con_no:
                await svc.cap_phat(
                    identity=q.duoc_si,
                    prescription_id=rx,
                    drug_batch_id=lo,
                    so_luong=1,
                )
                con_no -= 1
            elif lenh == "them":
                await svc.dieu_chinh(
                    identity=q.duoc_si, drug_batch_id=lo, so_luong=luong, ly_do="Dư"
                )
        except Exception as exc:
            pytest.fail(f"Chuỗi gây lỗi: {trace!r}\n{type(exc).__name__}: {exc}")
        assert await _ton(q, lo) >= con_no, trace
    if con_no:
        await svc.cap_phat(
            identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=con_no
        )
