"""Khu 2 — ĐỐI CHIẾU ĐỘC LẬP kho vật tư với sổ gốc `vat_tu_txn`.

`test_vat_tu_tieu_hao_db` đã có case vàng và một bài ngẫu nhiên với mô hình tay, nhưng
GIÁ cố định và cửa sổ luôn là cả chuỗi. Ở đây thêm, từ ĐỊNH NGHĨA ghi ở đầu
`vat_tu_tieu_hao_service` (không dùng SQL của nó):

1. Sau MỖI bước ngẫu nhiên: tồn mỗi nơi chứa = cộng dồn sổ; `ton_may` của từng dòng =
   tồn đúng lúc ghi; phiếu chuyển cân bằng (Σ = 0); phiếu đảo triệt tiêu đúng dòng gốc.
2. Báo cáo tiêu hao với GIÁ ĐỔI giữa chừng và cửa sổ cắt ngang một mốc bất kỳ.
3. Quy tắc cảnh báo của màn kho: tồn âm / dưới mức tối thiểu.

Mọi thay đổi tồn đều gọi service thật; SQL chỉ dựng danh mục và đọc sổ.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.services.vat_tu_kho_service import doc_ton, hoan_phieu, tao_phieu
from clinicai.services.vat_tu_tieu_hao_service import tinh_theo_moc
from tests.services.test_vat_tu_kho_db import _bo

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]
D = Decimal

_GOC = ("NHAP", "XUAT_PHONG", "TRA_KHO", "CHUYEN_PHONG", "HUY")


# ── Đọc sổ gốc ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Dong:
    id: str
    ton_id: str
    room_id: str | None
    so: Decimal
    thuc_te: Decimal | None
    gia: Decimal
    luc: datetime
    gd: int  # thứ tự ghi sổ (xid8 của giao dịch lập phiếu)
    loai: str
    phieu_id: str
    dao: str | None
    ton_may: Decimal


async def doc_so(pool: asyncpg.Pool, vt: str) -> list[Dong]:
    rows = await pool.fetch(
        "SELECT x.id::text, x.ton_id::text, t.room_id::text AS room_id, x.so_luong,"
        " x.thuc_te, x.gia_nhap, p.tao_luc, p.giao_dich::text::bigint AS gd, p.loai,"
        " p.id::text AS phieu_id, x.dao_txn_id::text AS dao, x.ton_may"
        " FROM vat_tu_txn x JOIN vat_tu_phieu p ON p.id = x.phieu_id"
        " JOIN vat_tu_ton t ON t.id = x.ton_id WHERE x.vat_tu_id = $1::uuid"
        " ORDER BY p.giao_dich, x.id",
        vt,
    )
    return [
        Dong(
            r["id"],
            r["ton_id"],
            r["room_id"],
            D(str(r["so_luong"])),
            None if r["thuc_te"] is None else D(str(r["thuc_te"])),
            D(str(r["gia_nhap"])),
            r["tao_luc"],
            r["gd"],
            r["loai"],
            r["phieu_id"],
            r["dao"],
            D(str(r["ton_may"])),
        )
        for r in rows
    ]


async def kiem_bat_bien(pool: asyncpg.Pool, vt: str, dau: str) -> list[Dong]:
    """Bất biến (1): chạy sau mỗi bước, lỗi kèm chuỗi thao tác."""
    so = await doc_so(pool, vt)
    ton = {
        r["id"]: D(str(r["so_luong"]))
        for r in await pool.fetch(
            "SELECT id::text, so_luong FROM vat_tu_ton WHERE vat_tu_id = $1::uuid", vt
        )
    }
    theo_ton: dict[str, list[Dong]] = {}
    for d in so:
        theo_ton.setdefault(d.ton_id, []).append(d)
    for tid, ds in theo_ton.items():
        cong = D(0)
        for d in ds:  # đã sắp theo thứ tự ghi sổ
            assert d.ton_may == cong, f"{dau}: ton_may sai tại dòng {d.id}"
            cong += d.so
        assert ton[tid] == cong, f"{dau}: tồn {ton[tid]} ≠ cộng dồn sổ {cong}"
    # Phiếu chuyển cân bằng; phiếu đảo triệt tiêu đúng dòng gốc.
    theo_phieu: dict[str, list[Dong]] = {}
    for d in so:
        theo_phieu.setdefault(d.phieu_id, []).append(d)
    by_id = {d.id: d for d in so}
    for ds in theo_phieu.values():
        if ds[0].loai in ("XUAT_PHONG", "TRA_KHO", "CHUYEN_PHONG"):
            assert sum(d.so for d in ds) == 0, f"{dau}: phiếu chuyển lệch"
        if ds[0].loai == "HOAN":
            for d in ds:
                assert d.dao is not None and by_id[d.dao].so == -d.so, dau
    return so


# ── Đáp án tiêu hao độc lập ─────────────────────────────────────────────


def dap_an_tieu_hao(
    so: list[Dong], tu: datetime, den: datetime
) -> dict[str, dict[str, Decimal | bool]]:
    """room_id → kết quả, theo định nghĩa ở đầu `vat_tu_tieu_hao_service`."""
    by_id = {d.id: d for d in so}
    da_dao = {d.dao for d in so if d.dao}

    def loai_goc(d: Dong) -> str:
        return by_id[d.dao].loai if d.dao else d.loai

    def so_goc(d: Dong) -> Decimal:
        return by_id[d.dao].so if d.dao else d.so

    trong_phong = [d for d in so if d.room_id is not None]
    ra: dict[str, dict[str, Decimal | bool]] = {}
    for room in {d.room_id for d in trong_phong}:
        assert room is not None
        dong_ton = [d for d in trong_phong if d.room_id == room]
        dem = [d for d in dong_ton if d.thuc_te is not None and d.id not in da_dao]
        truoc = [d for d in dem if d.luc <= tu]
        trong = [d for d in dem if tu < d.luc <= den]
        dau = max(truoc, key=lambda d: d.gd) if truoc else None
        if dau is None and trong:
            dau = min(trong, key=lambda d: d.gd)
        con = [d for d in dem if d.luc <= den]
        cuoi = max(con, key=lambda d: d.gd) if con else None
        if dau is None or cuoi is None or cuoi.gd <= dau.gd:
            ra[room] = {"du": False}
            continue
        giua = [d for d in dong_ton if dau.gd < d.gd <= cuoi.gd and loai_goc(d) in _GOC]
        nhan = sum((d.so for d in giua if so_goc(d) > 0 and loai_goc(d) != "HUY"), D(0))
        tra = -sum((d.so for d in giua if so_goc(d) < 0 and loai_goc(d) != "HUY"), D(0))
        huy = -sum((d.so for d in giua if loai_goc(d) == "HUY"), D(0))
        if nhan < 0 or tra < 0:
            rong = nhan - tra
            nhan, tra = (rong, D(0)) if rong >= 0 else (D(0), -rong)
        gia_ung = [d for d in trong_phong if d.gd <= cuoi.gd]
        gia = max(gia_ung, key=lambda d: (d.gd, d.luc)).gia if gia_ung else D(0)
        assert dau.thuc_te is not None and cuoi.thuc_te is not None
        th = dau.thuc_te + nhan - tra - cuoi.thuc_te
        ra[room] = {
            "du": True,
            "dau": dau.thuc_te,
            "nhan": nhan,
            "tra": tra,
            "cuoi": cuoi.thuc_te,
            "tieu_hao": th,
            "huy": huy,
            "gia": gia,
            "gia_tri": th * gia,
        }
    return ra


async def khop_tieu_hao(
    pool: asyncpg.Pool, identity: Any, vt: str, tu: datetime, den: datetime, dau: str
) -> dict[str, dict[str, Decimal | bool]]:
    an = dap_an_tieu_hao(await doc_so(pool, vt), tu, den)
    thuc = {
        d["room_id"]: d
        for d in await tinh_theo_moc(pool, identity=identity, tu_luc=tu, den_luc=den)
        if d["vat_tu_id"] == vt
    }
    for room, o in an.items():
        t = thuc[room]
        assert t["du_du_lieu"] is o["du"], f"{dau}: đủ dữ liệu {room}: {t} ≠ {o}"
        if not o["du"]:
            continue
        got = (
            D(str(t["dau"])),
            D(str(t["nhan"])),
            D(str(t["tra"])),
            D(str(t["cuoi"])),
            D(str(t["tieu_hao"])),
            D(str(t["trong_do_huy"])),
            D(str(t["gia_nhap"])),
            D(str(t["gia_tri"])),
        )
        want = tuple(
            D(str(o[k]))
            for k in ("dau", "nhan", "tra", "cuoi", "tieu_hao", "huy", "gia", "gia_tri")
        )
        assert got == want, f"{dau}: phòng {room}\n  báo cáo={got}\n  sổ gốc ={want}"
    return an


async def _moc(pool: asyncpg.Pool) -> datetime:
    v = await pool.fetchval("SELECT clock_timestamp()")
    await asyncio.sleep(0.02)  # tao_luc = now() của giao dịch: phải sau mốc
    assert isinstance(v, datetime)
    return v


async def _phieu(
    pool: asyncpg.Pool,
    identity: Any,
    vt: str,
    loai: str,
    *,
    tu: str | None = None,
    den: str | None = None,
    so: Any = 3,
    gia: Any = None,
) -> dict[str, Any]:
    dong: dict[str, Any] = {
        "vat_tu_id": vt,
        "tu_room_id": tu,
        "den_room_id": den,
        "so_luong": so,
    }
    if gia is not None:
        dong["gia_nhap"] = gia
    return await tao_phieu(
        pool,
        identity=identity,
        khoa_gui=uuid.uuid4().hex,
        loai=loai,
        dong=[dong],
        ghi_chu="Đối chiếu độc lập",
    )


# ── Case vàng: số tính tay ───────────────────────────────────────────────


async def test_gia_theo_dong_so_cuoi_ky_khong_theo_gia_luc_xuat(
    pool: asyncpg.Pool,
) -> None:
    """Giá trị = tiêu hao × giá ở dòng sổ gần nhất tới lần đếm cuối (định nghĩa của
    service), nên ĐỔI GIÁ giữa kỳ đổi cách định giá. Ghi vào bảng đối chiếu như một
    điểm cần xác nhận, không phải lỗi.

    Tay: đếm đầu 0 → xuất 5 (giá 100) → đếm cuối 3 (giá danh mục lúc đếm = 200):
    tiêu hao 0 + 5 − 0 − 3 = 2; giá trị 2 × 200 = 400 (không phải 2 × 100).
    """
    identity, vt, rooms = await _bo(pool)
    p = rooms[0]
    await pool.execute(
        "UPDATE service_price SET gia_nhap_vat_tu=100 WHERE id=$1::uuid", vt
    )
    await _phieu(pool, identity, vt, "DIEU_CHINH", tu=p, so=0)
    tu = await _moc(pool)
    await _phieu(pool, identity, vt, "XUAT_PHONG", den=p, so=5)
    await pool.execute(
        "UPDATE service_price SET gia_nhap_vat_tu=200 WHERE id=$1::uuid", vt
    )
    await _phieu(pool, identity, vt, "KIEM", tu=p, so=3)
    den = await _moc(pool)
    an = await khop_tieu_hao(pool, identity, vt, tu, den, "giá đổi giữa kỳ")
    assert an[p]["tieu_hao"] == D(2)
    assert an[p]["gia"] == D(200) and an[p]["gia_tri"] == D(400)


async def test_chuyen_phong_va_hoan_tac_ra_dung_nhan_tra(pool: asyncpg.Pool) -> None:
    """Chuyển A→B 4: A trả 4, B nhận 4. Đảo phiếu chuyển → cả hai về 0.

    Tay: A đếm 10, B đếm 0 · chuyển A→B 4 · A đếm 6, B đếm 4:
    A tiêu hao 10 + 0 − 4 − 6 = 0; B tiêu hao 0 + 4 − 0 − 4 = 0.
    Sau đảo (A,B đếm lại 10 và 0): nhận/trả ròng 0.
    """
    identity, vt, (a, b) = await _bo(pool)
    await _phieu(pool, identity, vt, "DIEU_CHINH", tu=a, so=10)
    await _phieu(pool, identity, vt, "DIEU_CHINH", tu=b, so=0)
    tu = await _moc(pool)
    chuyen = await _phieu(pool, identity, vt, "CHUYEN_PHONG", tu=a, den=b, so=4)
    await _phieu(pool, identity, vt, "KIEM", tu=a, so=6)
    await _phieu(pool, identity, vt, "KIEM", tu=b, so=4)
    den = await _moc(pool)
    an = await khop_tieu_hao(pool, identity, vt, tu, den, "chuyển phòng")
    assert (an[a]["tra"], an[a]["nhan"], an[a]["tieu_hao"]) == (D(4), D(0), D(0))
    assert (an[b]["nhan"], an[b]["tra"], an[b]["tieu_hao"]) == (D(4), D(0), D(0))
    await hoan_phieu(
        pool, identity=identity, phieu_id=chuyen["id"], khoa_gui=uuid.uuid4().hex
    )
    await _phieu(pool, identity, vt, "KIEM", tu=a, so=10)
    await _phieu(pool, identity, vt, "KIEM", tu=b, so=0)
    den2 = await _moc(pool)
    an2 = await khop_tieu_hao(pool, identity, vt, tu, den2, "sau hoàn tác")
    assert (an2[a]["nhan"], an2[a]["tra"]) == (D(0), D(0))
    assert (an2[b]["nhan"], an2[b]["tra"]) == (D(0), D(0))


async def test_canh_bao_ton_am_va_duoi_muc_toi_thieu(pool: asyncpg.Pool) -> None:
    """Tồn âm luôn cảnh báo (kể cả mức tối thiểu 0); dưới mức tối thiểu thì nhắc;
    đủ mức thì im. Tay: kho 5, mức 10 → nhắc; trả 8 từ phòng chưa có → phòng −8 → âm."""
    identity, vt, (a, _b) = await _bo(pool)
    await _phieu(pool, identity, vt, "NHAP", den=None, so=5)
    await pool.execute(
        "UPDATE vat_tu_ton SET ton_toi_thieu = 10 WHERE vat_tu_id = $1::uuid"
        " AND room_id IS NULL",
        vt,
    )
    await _phieu(pool, identity, vt, "TRA_KHO", tu=a, so=8)  # phòng a: 0 − 8 = −8
    ton = {
        t["room_id"]: t
        for t in await doc_ton(pool, identity=identity)
        if t["vat_tu_id"] == vt
    }
    assert ton[None]["so_luong"] == D(13) and ton[None]["canh_bao"] == ""
    assert ton[a]["so_luong"] == D(-8) and "tồn âm" in ton[a]["canh_bao"]
    await pool.execute(
        "UPDATE vat_tu_ton SET ton_toi_thieu = 20 WHERE vat_tu_id = $1::uuid"
        " AND room_id IS NULL",
        vt,
    )
    ton = {
        t["room_id"]: t
        for t in await doc_ton(pool, identity=identity)
        if t["vat_tu_id"] == vt
    }
    assert ton[None]["canh_bao"] == "Dưới mức tối thiểu"


# ── Bấm ngẫu nhiên: sổ luôn khớp tồn, báo cáo luôn bằng đáp án độc lập ────


@pytest.mark.parametrize("seed", range(20))
async def test_bam_ngau_nhien_vat_tu(pool: asyncpg.Pool, seed: int) -> None:
    rng = random.Random(seed)
    identity, vt, rooms = await _bo(pool)
    await pool.execute(
        "UPDATE service_price SET gia_nhap_vat_tu=$2 WHERE id=$1::uuid",
        vt,
        rng.choice((50, 100, 120)),
    )
    for r in rooms:  # đếm đầu để có mốc
        await _phieu(pool, identity, vt, "DIEU_CHINH", tu=r, so=rng.randint(0, 15))
    tu = await _moc(pool)
    moc: list[datetime] = [tu]
    phieu_hoan_duoc: list[str] = []
    trace: tuple[str, ...] = ()
    for buoc in range(10):
        lenh = rng.choice(
            ("nhap", "xuat", "tra", "chuyen", "huy", "kiem", "chinh", "hoan", "gia")
        )
        a, b = rng.sample(rooms, 2)
        q = D(rng.randint(1, 6))
        trace = (*trace, f"seed={seed} buoc={buoc} {lenh} {a[-4:]}>{b[-4:]} q={q}")
        try:
            if lenh == "gia":
                await pool.execute(
                    "UPDATE service_price SET gia_nhap_vat_tu=$2 WHERE id=$1::uuid",
                    vt,
                    rng.choice((50, 100, 150, 200)),
                )
            elif lenh == "hoan":
                if phieu_hoan_duoc:
                    pid = phieu_hoan_duoc.pop(rng.randrange(len(phieu_hoan_duoc)))
                    await hoan_phieu(
                        pool, identity=identity, phieu_id=pid, khoa_gui=uuid.uuid4().hex
                    )
            else:
                kw_theo_lenh: dict[str, dict[str, Any]] = {
                    "nhap": {"den": rng.choice((a, None))},
                    "xuat": {"den": a},
                    "tra": {"tu": a},
                    "chuyen": {"tu": a, "den": b},
                    "huy": {"tu": rng.choice((a, None))},
                    "kiem": {"tu": a},
                    "chinh": {"tu": a},
                }
                kw = kw_theo_lenh[lenh]
                loai = {
                    "nhap": "NHAP",
                    "xuat": "XUAT_PHONG",
                    "tra": "TRA_KHO",
                    "chuyen": "CHUYEN_PHONG",
                    "huy": "HUY",
                    "kiem": "KIEM",
                    "chinh": "DIEU_CHINH",
                }[lenh]
                p = await _phieu(pool, identity, vt, loai, so=q, **kw)
                if loai in ("NHAP", "XUAT_PHONG", "TRA_KHO", "CHUYEN_PHONG", "HUY"):
                    phieu_hoan_duoc.append(p["id"])
        except (ConflictError, ValidationError, NotFoundError):
            pass  # thao tác bị từ chối đúng luật — sổ không được đổi, kiểm ngay dưới
        dau = " | ".join(trace)
        await kiem_bat_bien(pool, vt, dau)
        moc.append(await _moc(pool))
    den = moc[-1]
    await khop_tieu_hao(pool, identity, vt, tu, den, "cả chuỗi: " + " | ".join(trace))
    cat = rng.choice(moc[1:-1])
    await khop_tieu_hao(pool, identity, vt, cat, den, "cắt giữa: " + " | ".join(trace))
