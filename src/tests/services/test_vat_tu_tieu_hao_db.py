"""Tiêu hao vật tư theo phòng × kỳ: đầu/cuối là SỐ ĐẾM THẬT, thiếu thì nói thiếu."""

from __future__ import annotations

import random
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from clinicai.services.vat_tu_kho_service import hoan_phieu
from clinicai.services.vat_tu_tieu_hao_service import (
    chuan_nhan_tra,
    doc_tieu_hao,
    khoang_ky,
    tinh_theo_moc,
)
from tests.services.test_vat_tu_kho_db import _bo, _ghi

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


def test_khoang_ky_tuan_thang_va_rac_khong_nem() -> None:
    thu_tu = date(2026, 10, 14)  # thứ Tư
    assert khoang_ky("tuan", None, None, thu_tu) == (date(2026, 10, 12), thu_tu)
    assert khoang_ky("thang", None, None, thu_tu) == (date(2026, 10, 1), thu_tu)
    assert khoang_ky(None, "2026-10-03", "2026-10-09", thu_tu) == (
        date(2026, 10, 3),
        date(2026, 10, 9),
    )
    # Đảo ngày thì đổi chỗ; rác / rỗng → hôm nay.
    assert khoang_ky("tuy", "2026-10-09", "2026-10-03", thu_tu) == (
        date(2026, 10, 3),
        date(2026, 10, 9),
    )
    assert khoang_ky("x", "rác", "", thu_tu) == (thu_tu, thu_tu)


@pytest.mark.parametrize(
    ("nhan", "tra", "mong"),
    [
        (5, 2, (5, 0 + 2)),
        (-3, 0, (0, 3)),  # hoàn tác phiếu xuất của kỳ trước: ròng là trả 3
        (0, -4, (4, 0)),
        (2, -1, (3, 0)),
    ],
)
def test_nhan_tra_rong_khong_am(nhan: int, tra: int, mong: tuple[int, int]) -> None:
    assert chuan_nhan_tra(Decimal(nhan), Decimal(tra)) == (
        Decimal(mong[0]),
        Decimal(mong[1]),
    )


async def _moc(pool: asyncpg.Pool) -> Any:
    return await pool.fetchval("SELECT clock_timestamp()")


def _dong_cua(ds: list[dict[str, Any]], vt: str, phong: str) -> dict[str, Any]:
    (d,) = [x for x in ds if x["vat_tu_id"] == vt and x["room_id"] == phong]
    return d


@pytest.mark.db
@pytest.mark.asyncio
async def test_danh_muc_chua_co_gia_thi_tinh_theo_lan_nhap_gan_nhat(
    pool: asyncpg.Pool,
) -> None:
    """Bấm thật 31/10: nhập 150.000đ/cái, danh mục để trống giá → Mức dùng ra 0 đ."""
    identity, vt, rooms = await _bo(pool)
    p = rooms[0]
    await pool.execute(
        "UPDATE service_price SET gia_nhap_vat_tu=NULL WHERE id=$1::uuid", vt
    )
    await _ghi(pool, identity, vt, "NHAP", so=10, gia_nhap="150000")
    await _ghi(pool, identity, vt, "XUAT_PHONG", den=p, so=5)
    await _ghi(pool, identity, vt, "DIEU_CHINH", tu=p, so=5)
    tu = await _moc(pool)
    await _ghi(pool, identity, vt, "DIEU_CHINH", tu=p, so=3)
    den = await _moc(pool)
    ds = await tinh_theo_moc(pool, identity=identity, tu_luc=tu, den_luc=den)
    d = _dong_cua(ds, vt, p)
    assert d["gia_nhap"] == 150000 and d["gia_tri"] == 300000


@pytest.mark.db
@pytest.mark.asyncio
async def test_tieu_hao_dau_nhan_tra_cuoi_huy_va_gia_chot(pool: asyncpg.Pool) -> None:
    identity, vt, rooms = await _bo(pool)
    p = rooms[0]
    await pool.execute(
        "UPDATE service_price SET gia_nhap_vat_tu=100 WHERE id=$1::uuid", vt
    )
    await _ghi(pool, identity, vt, "NHAP", den=p, so=10)
    await _ghi(pool, identity, vt, "DIEU_CHINH", tu=p, so=10)  # đếm đầu
    tu = await _moc(pool)
    await _ghi(pool, identity, vt, "XUAT_PHONG", den=p, so=5)
    await _ghi(pool, identity, vt, "TRA_KHO", tu=p, so=2)
    await _ghi(
        pool,
        identity,
        vt,
        "TRA_NCC",
        tu=p,
        so=1,
        nha_cung_cap="Nhà cung cấp thử",
        ghi_chu="Hàng lỗi",
    )
    await _ghi(pool, identity, vt, "HUY", tu=p, so=1)
    await _ghi(pool, identity, vt, "KIEM", tu=p, so=8)  # đếm cuối
    den = await _moc(pool)
    # Đổi giá danh mục SAU khi đã ghi sổ: lịch sử không đổi theo.
    await pool.execute(
        "UPDATE service_price SET gia_nhap_vat_tu=999 WHERE id=$1::uuid", vt
    )
    ds = await tinh_theo_moc(pool, identity=identity, tu_luc=tu, den_luc=den)
    d = _dong_cua(ds, vt, p)
    assert d["du_du_lieu"] is True
    assert (d["dau"], d["nhan"], d["tra"], d["cuoi"]) == (10, 5, 3, 8)
    assert d["tieu_hao"] == 4 and d["trong_do_huy"] == 1
    assert d["da_dung"] == 3 and d["gia_tri_da_dung"] == 300
    assert d["tra_nha_san_xuat"] == 1
    assert d["gia_nhap"] == 100 and d["gia_tri"] == 400
    # Phòng còn lại chưa có sổ thì không có dòng; số đếm KHÁC tồn sổ vẫn dùng số đếm.
    assert not [x for x in ds if x["vat_tu_id"] == vt and x["room_id"] == rooms[1]]


@pytest.mark.db
@pytest.mark.asyncio
async def test_gia_tieu_hao_chi_lay_giao_dich_cung_noi_chua(
    pool: asyncpg.Pool,
) -> None:
    identity, vt, rooms = await _bo(pool)
    from clinicai.services.vat_tu_kho_service import tao_phieu

    don_vi = await pool.fetchval(
        "SELECT don_vi FROM service_price WHERE id=$1::uuid", vt
    )

    async def nhap(room: str, gia: int) -> None:
        await tao_phieu(
            pool,
            identity=identity,
            khoa_gui=uuid.uuid4().hex,
            loai="NHAP",
            dong=[
                {
                    "vat_tu_id": vt,
                    "don_vi": don_vi,
                    "den_room_id": room,
                    "so_luong": 1,
                    "gia_nhap": gia,
                }
            ],
        )

    await nhap(rooms[0], 100)
    await nhap(rooms[1], 900)
    ds = await tinh_theo_moc(
        pool, identity=identity, tu_luc=await _moc(pool), den_luc=await _moc(pool)
    )
    assert _dong_cua(ds, vt, rooms[0])["gia_nhap"] == 100
    assert _dong_cua(ds, vt, rooms[1])["gia_nhap"] == 900


@pytest.mark.db
@pytest.mark.asyncio
async def test_bao_cao_phong_co_luong_cap_trong_ky_va_so_dem_thuc_te_moi_nhat(
    pool: asyncpg.Pool,
) -> None:
    """Bảng tồn phòng cần tách số đã cấp, dùng theo kiểm kê, tồn sổ và số đếm thật."""
    identity, vt, rooms = await _bo(pool)
    phong, phong_nguon = rooms
    await _ghi(pool, identity, vt, "NHAP", den=phong_nguon, so=4)
    await _ghi(pool, identity, vt, "DIEU_CHINH", tu=phong, so=10)
    await _ghi(pool, identity, vt, "DIEU_CHINH", tu=phong_nguon, so=4)
    tu = await _moc(pool)

    cap_tu_kho = await _ghi(pool, identity, vt, "XUAT_PHONG", den=phong, so=5)
    chuyen = await _ghi(
        pool, identity, vt, "CHUYEN_PHONG", tu=phong_nguon, den=phong, so=3
    )
    await hoan_phieu(
        pool, identity=identity, phieu_id=chuyen["id"], khoa_gui=uuid.uuid4().hex
    )
    await _ghi(pool, identity, vt, "KIEM", tu=phong, so=12)
    den = await _moc(pool)
    await _ghi(pool, identity, vt, "KIEM", tu=phong, so=13)

    ds = await tinh_theo_moc(pool, identity=identity, tu_luc=tu, den_luc=den)
    d = _dong_cua(ds, vt, phong)

    assert d["du_du_lieu"] is True
    assert d["cap_trong_ky"] == 5  # Chuyển phòng đã hoàn tác nên không cộng.
    assert d["tieu_hao"] == 3 and d["trong_do_huy"] == 0
    assert d["da_dung"] == 3  # Hỏng/huỷ tách riêng khỏi lượng dùng.
    assert d["cuoi"] == 12
    assert d["thuc_te_gan_nhat"] == 13  # Số đếm mới nhất, kể cả sau kỳ báo cáo.
    assert d["thuc_te_gan_nhat_luc"] is not None
    assert cap_tu_kho["id"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_bao_cao_phong_cap_trong_ky_khong_giam_khi_chuyen_vat_tu_ra_phong(
    pool: asyncpg.Pool,
) -> None:
    """Số được cấp là lượng nhận vào phòng, không phải lượng ròng sau điều chuyển."""
    identity, vt, rooms = await _bo(pool)
    phong, phong_nguon = rooms
    await _ghi(pool, identity, vt, "DIEU_CHINH", tu=phong, so=10)
    await _ghi(pool, identity, vt, "DIEU_CHINH", tu=phong_nguon, so=10)
    tu = await _moc(pool)

    await _ghi(pool, identity, vt, "XUAT_PHONG", den=phong, so=4)
    await _ghi(pool, identity, vt, "CHUYEN_PHONG", tu=phong, den=phong_nguon, so=6)
    den = await _moc(pool)

    d = _dong_cua(
        await tinh_theo_moc(pool, identity=identity, tu_luc=tu, den_luc=den), vt, phong
    )
    assert d["cap_trong_ky"] == 4


@pytest.mark.db
@pytest.mark.asyncio
async def test_kho_co_so_khong_co_tieu_hao(pool: asyncpg.Pool) -> None:
    identity, vt, _ = await _bo(pool)
    await _ghi(pool, identity, vt, "NHAP", den=None, so=10)
    await _ghi(pool, identity, vt, "KIEM", tu=None, so=10)
    ds = await tinh_theo_moc(
        pool, identity=identity, tu_luc=await _moc(pool), den_luc=await _moc(pool)
    )
    assert not [x for x in ds if x["vat_tu_id"] == vt]


@pytest.mark.db
@pytest.mark.asyncio
async def test_thieu_so_dem_thi_noi_chua_du_du_lieu_khong_suy_ton_so(
    pool: asyncpg.Pool,
) -> None:
    identity, vt, rooms = await _bo(pool)
    p = rooms[0]
    # 1) Chỉ có luồng, chưa từng đếm.
    await _ghi(pool, identity, vt, "NHAP", den=p, so=10)
    t1 = await _moc(pool)
    d = _dong_cua(
        await tinh_theo_moc(pool, identity=identity, tu_luc=t1, den_luc=t1), vt, p
    )
    assert d["du_du_lieu"] is False and d["tieu_hao"] is None and d["dau"] is None
    assert "Chưa có lần kiểm đếm nào" in d["ly_do_thieu"]
    # 2) Mới có MỘT lần đếm (nằm trong kỳ): chưa tính được.
    await _ghi(pool, identity, vt, "KIEM", tu=p, so=7)
    t2 = await _moc(pool)
    d = _dong_cua(
        await tinh_theo_moc(pool, identity=identity, tu_luc=t1, den_luc=t2), vt, p
    )
    assert d["du_du_lieu"] is False and "một lần kiểm đếm" in d["ly_do_thieu"]
    # 3) Có số đếm trước kỳ nhưng chưa đếm lại: không lấy tồn sổ làm số cuối.
    t3 = await _moc(pool)
    await _ghi(pool, identity, vt, "XUAT_PHONG", den=p, so=2)
    t4 = await _moc(pool)
    d = _dong_cua(
        await tinh_theo_moc(pool, identity=identity, tu_luc=t3, den_luc=t4), vt, p
    )
    assert d["du_du_lieu"] is False and d["tieu_hao"] is None
    assert "một lần kiểm đếm" in d["ly_do_thieu"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_chua_co_so_dem_truoc_ky_thi_lay_lan_dem_dau_trong_ky(
    pool: asyncpg.Pool,
) -> None:
    """Hệ thống mới: cả hai lần đếm đều nằm TRONG kỳ → vẫn tính, và nói rõ đầu kỳ
    là lần đếm đầu tiên trong kỳ (giờ thật của hai lần đếm có trong dòng)."""
    identity, vt, rooms = await _bo(pool)
    p = rooms[0]
    tu = await _moc(pool)
    await _ghi(pool, identity, vt, "XUAT_PHONG", den=p, so=10)
    await _ghi(pool, identity, vt, "KIEM", tu=p, so=10)
    await _ghi(pool, identity, vt, "XUAT_PHONG", den=p, so=5)
    await _ghi(pool, identity, vt, "KIEM", tu=p, so=12)
    await _ghi(pool, identity, vt, "KIEM", tu=p, so=11)
    den = await _moc(pool)
    d = _dong_cua(
        await tinh_theo_moc(pool, identity=identity, tu_luc=tu, den_luc=den), vt, p
    )
    # Lần đếm đầu trong kỳ = 10, lần cuối = 11, nhận 5 giữa hai lần.
    assert d["dau_trong_ky"] is True and d["du_du_lieu"] is True
    assert (d["dau"], d["nhan"], d["cuoi"], d["tieu_hao"]) == (10, 5, 11, 4)
    assert d["dem_dau_luc"] and d["dem_cuoi_luc"]
    # Có lần đếm trước kỳ thì dùng nó, không dùng lần đầu trong kỳ.
    d2 = _dong_cua(
        await tinh_theo_moc(
            pool, identity=identity, tu_luc=await _moc(pool), den_luc=await _moc(pool)
        ),
        vt,
        p,
    )
    assert d2["du_du_lieu"] is False


@pytest.mark.db
@pytest.mark.asyncio
async def test_hoan_tac_phieu_luong_va_phieu_dem(pool: asyncpg.Pool) -> None:
    identity, vt, rooms = await _bo(pool)
    p = rooms[0]
    await _ghi(pool, identity, vt, "DIEU_CHINH", tu=p, so=10)
    tu = await _moc(pool)
    xuat = await _ghi(pool, identity, vt, "XUAT_PHONG", den=p, so=5)
    await hoan_phieu(
        pool, identity=identity, phieu_id=xuat["id"], khoa_gui=uuid.uuid4().hex
    )
    dem2 = await _ghi(pool, identity, vt, "KIEM", tu=p, so=10)
    den = await _moc(pool)
    d = _dong_cua(
        await tinh_theo_moc(pool, identity=identity, tu_luc=tu, den_luc=den), vt, p
    )
    # Xuất rồi hoàn tác: ròng bằng 0, tiêu hao 10 + 0 − 0 − 10 = 0.
    assert (d["nhan"], d["tra"], d["tieu_hao"]) == (0, 0, 0)
    # Hoàn tác chính lần đếm cuối: nó thôi là mốc → quay về "chưa đếm lại".
    await hoan_phieu(
        pool, identity=identity, phieu_id=dem2["id"], khoa_gui=uuid.uuid4().hex
    )
    d = _dong_cua(
        await tinh_theo_moc(
            pool, identity=identity, tu_luc=tu, den_luc=await _moc(pool)
        ),
        vt,
        p,
    )
    assert d["du_du_lieu"] is False and d["tieu_hao"] is None


@pytest.mark.db
@pytest.mark.asyncio
async def test_doc_tieu_hao_rac_khong_nem_va_co_tong(pool: asyncpg.Pool) -> None:
    identity, vt, rooms = await _bo(pool)
    await pool.execute(
        "UPDATE service_price SET gia_nhap_vat_tu=50 WHERE id=$1::uuid", vt
    )
    await _ghi(pool, identity, vt, "DIEU_CHINH", tu=rooms[0], so=4)
    for kwargs in (
        {},
        {"ky": "tuan"},
        {"ky": "thang"},
        {"ky": "tuy", "tu": "rác", "den": "99-99-99"},
        {"ky": 123, "tu": None, "den": None},
    ):
        kq = await doc_tieu_hao(pool, identity=identity, **kwargs)
        assert set(kq) >= {"ky", "tu", "den", "items", "theo_phong", "tong_gia_tri"}
    kq = await doc_tieu_hao(pool, identity=identity, ky="tuan")
    mine = [x for x in kq["items"] if x["vat_tu_id"] == vt]
    # Mới có MỘT lần đếm hôm nay: chưa đủ dữ liệu, giá trị không cộng vào tổng.
    assert len(mine) == 1 and mine[0]["du_du_lieu"] is False
    tong = {t["room_id"]: t for t in kq["theo_phong"]}[rooms[0]]
    assert tong["chua_du"] >= 1 and tong["gia_tri"] == 0


@pytest.mark.db
@pytest.mark.asyncio
async def test_bam_ngau_nhien_tieu_hao_khop_mo_hinh(pool: asyncpg.Pool) -> None:
    """Giả lập: luồng nhập/xuất/trả/chuyển/huỷ/hoàn tác giữa hai lần đếm, so với mô hình
    tính tay (cộng dồn đóng góp từng phiếu, hoàn tác = trừ lại đúng đóng góp ấy)."""
    for seed in range(12):
        rng = random.Random(seed)
        chuoi: list[str] = []
        try:
            identity, vt, rooms = await _bo(pool)
            dau = {r: rng.randint(0, 20) for r in rooms}
            for r in rooms:
                await _ghi(pool, identity, vt, "DIEU_CHINH", tu=r, so=dau[r])
            tu = await _moc(pool)
            nhan = {r: Decimal(0) for r in rooms}
            tra = {r: Decimal(0) for r in rooms}
            huy = {r: Decimal(0) for r in rooms}
            # phiếu → đóng góp (phòng, loại, số) để hoàn tác trừ lại đúng.
            ghi: list[tuple[str, list[tuple[str, str, Decimal]]]] = []
            for _ in range(rng.randint(3, 9)):
                loai = rng.choice(
                    ["NHAP", "XUAT_PHONG", "TRA_KHO", "CHUYEN_PHONG", "HUY", "HOAN"]
                )
                q = Decimal(rng.randint(1, 6))
                a, b = rooms
                if rng.random() < 0.5:
                    a, b = b, a
                chuoi.append(f"{loai}:{a[-4:]}->{b[-4:]}:{q}")
                if loai == "HOAN":
                    if not ghi:
                        continue
                    pid, dong = ghi.pop(rng.randrange(len(ghi)))
                    await hoan_phieu(
                        pool, identity=identity, phieu_id=pid, khoa_gui=uuid.uuid4().hex
                    )
                    for r, k, so in dong:
                        {"in": nhan, "out": tra, "huy": huy}[k][r] -= so
                    continue
                kw: dict[str, Any] = {
                    "NHAP": {"den": a},
                    "XUAT_PHONG": {"den": a},
                    "TRA_KHO": {"tu": a},
                    "CHUYEN_PHONG": {"tu": a, "den": b},
                    "HUY": {"tu": a},
                }[loai]
                p = await _ghi(pool, identity, vt, loai, so=q, **kw)
                dong2 = {
                    "NHAP": [(a, "in", q)],
                    "XUAT_PHONG": [(a, "in", q)],
                    "TRA_KHO": [(a, "out", q)],
                    "CHUYEN_PHONG": [(a, "out", q), (b, "in", q)],
                    "HUY": [(a, "huy", q)],
                }[loai]
                for r, k, so in dong2:
                    {"in": nhan, "out": tra, "huy": huy}[k][r] += so
                ghi.append((p["id"], dong2))
            cuoi = {r: rng.randint(0, 20) for r in rooms}
            for r in rooms:
                await _ghi(pool, identity, vt, "KIEM", tu=r, so=cuoi[r])
            den = await _moc(pool)
            ds = await tinh_theo_moc(pool, identity=identity, tu_luc=tu, den_luc=den)
            for r in rooms:
                n, t = chuan_nhan_tra(nhan[r], tra[r])
                d = _dong_cua(ds, vt, r)
                assert d["du_du_lieu"] is True
                assert d["dau"] == dau[r] and d["cuoi"] == cuoi[r]
                assert d["tieu_hao"] == dau[r] + n - t - cuoi[r]
                assert d["trong_do_huy"] == huy[r]
        except Exception as exc:
            raise AssertionError(f"seed={seed}; chuỗi={chuoi}") from exc
