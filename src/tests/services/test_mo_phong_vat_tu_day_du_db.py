"""Mô phỏng ĐẦY ĐỦ kho vật tư: nhiều vật tư × nhiều phòng, mọi loại phiếu, và các
thao tác phụ (đặt mức tối thiểu, gửi lại cùng khoá, hoàn hai lần, tranh chấp).

`test_doi_chieu_vat_tu_db` bấm ngẫu nhiên MỘT vật tư, hai phòng. Ở đây thêm, sau MỖI
bước, kiểm trên cả bộ vật tư:

  V1  tồn từng nơi chứa = cộng dồn sổ; `ton_may` đúng lúc ghi; phiếu chuyển cân bằng;
  V2  màn kho (`doc_ton`) khớp đáp án độc lập, kể cả CẢNH BÁO tồn âm / dưới mức
      (mức tối thiểu do bài tự ghi nhớ, không đọc lại từ chính màn);
  V3  thao tác trên vật tư A không đổi tồn vật tư B;
  V4  gửi lại cùng khoá → cùng phiếu, không thêm dòng sổ nào;
  V5  hoàn phiếu lần hai bị từ chối và không đổi sổ.

Cuối hạt: báo cáo tiêu hao từng vật tư = đáp án độc lập (cả chuỗi và cắt ngang).

Mọi thay đổi gọi service thật; SQL chỉ dựng danh mục và đọc sổ.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from collections import Counter
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.services.vat_tu_kho_man_service import dat_muc_toi_thieu, doc_canh_bao
from clinicai.services.vat_tu_kho_service import doc_ton, hoan_phieu, tao_phieu
from tests.services.test_doi_chieu_vat_tu_db import (
    _moc,
    doc_so,
    khop_tieu_hao,
    kiem_bat_bien,
)
from tests.services.test_vat_tu_kho_db import _bo

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]
D = Decimal

_LOAI = {
    "nhap": "NHAP",
    "xuat": "XUAT_PHONG",
    "tra": "TRA_KHO",
    "chuyen": "CHUYEN_PHONG",
    "huy": "HUY",
    "kiem": "KIEM",
    "chinh": "DIEU_CHINH",
}
_HOAN_DUOC = ("NHAP", "XUAT_PHONG", "TRA_KHO", "CHUYEN_PHONG", "HUY")


async def _them_vat_tu_va_phong(
    pool: asyncpg.Pool, identity: Any, rooms: list[str]
) -> tuple[list[str], list[str]]:
    """Từ bộ `_bo` (1 vật tư, 2 phòng) nâng lên 3 vật tư, 3 phòng."""
    vts: list[str] = []
    for ten in ("Bông mô phỏng", "Kim mô phỏng"):
        vts.append(
            str(
                await pool.fetchval(
                    'INSERT INTO service_price (clinic_id, service_code, name, "group",'
                    " don_vi) VALUES ($1::uuid, $2, $3, 'vat_tu', 'cái')"
                    " RETURNING id::text",
                    identity.clinic_id,
                    f"VT_TEST_{uuid.uuid4().hex}",
                    ten,
                )
            )
        )
    phong3 = str(
        await pool.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code)"
            " VALUES ($1::uuid, $2::uuid, $3, 'Phòng vật tư 3', 'DICHVU-SIEUAM')"
            " RETURNING id::text",
            identity.clinic_id,
            identity.location_id,
            f"VT-{uuid.uuid4().hex}",
        )
    )
    return vts, [*rooms, phong3]


async def _tao(
    pool: asyncpg.Pool,
    identity: Any,
    vt: str,
    loai: str,
    *,
    tu: str | None,
    den: str | None,
    so: Any,
    khoa: str | None = None,
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    khoa = khoa or uuid.uuid4().hex
    dong = [{"vat_tu_id": vt, "tu_room_id": tu, "den_room_id": den, "so_luong": so}]
    p = await tao_phieu(
        pool,
        identity=identity,
        khoa_gui=khoa,
        loai=loai,
        dong=dong,
        ghi_chu="Mô phỏng đầy đủ",
    )
    return p, khoa, dong


async def _ton_theo_noi(
    pool: asyncpg.Pool, vts: list[str]
) -> dict[tuple[str, str | None], Decimal]:
    """Đáp án độc lập: (vật tư, phòng) → cộng dồn sổ gốc."""
    ra: dict[tuple[str, str | None], Decimal] = {}
    for vt in vts:
        for d in await doc_so(pool, vt):
            ra[(vt, d.room_id)] = ra.get((vt, d.room_id), D(0)) + d.so
    return ra


async def kiem_man_kho(
    pool: asyncpg.Pool,
    identity: Any,
    vts: list[str],
    muc: dict[tuple[str, str | None], Decimal],
    dau: str,
) -> dict[tuple[str, str | None], Decimal]:
    """V2: màn kho = đáp án độc lập, cảnh báo đúng luật. Trả tồn để so V3."""
    an = await _ton_theo_noi(pool, vts)
    hien = [t for t in await doc_ton(pool, identity=identity) if t["vat_tu_id"] in vts]
    thay: dict[tuple[str, str | None], Decimal] = {}
    for t in hien:
        k = (t["vat_tu_id"], t["room_id"])
        so = D(str(t["so_luong"]))
        thay[k] = so
        assert so == an.get(k, D(0)), f"{dau}: màn kho {k} = {so} ≠ sổ {an.get(k)}"
        toi_thieu = muc.get(k, D(0))
        assert D(str(t["ton_toi_thieu"])) == toi_thieu, f"{dau}: mức tối thiểu {k}"
        mong = (
            "tồn âm — cần kiểm đếm"
            if so < 0
            else ("Dưới mức tối thiểu" if so < toi_thieu else "")
        )
        assert t["canh_bao"] == mong, f"{dau}: cảnh báo {k}: {t['canh_bao']!r}≠{mong!r}"
    for k, v in an.items():
        assert thay.get(k) == v or v == 0, (
            f"{dau}: nơi chứa {k} có sổ mà màn không hiện"
        )
    cb = {
        (t["vat_tu_id"], t["room_id"])
        for t in await doc_canh_bao(pool, identity=identity)
        if t["vat_tu_id"] in vts
    }
    assert cb == {k for k, t in zip(thay, hien, strict=False) if t["canh_bao"]}, dau
    return thay


@pytest.mark.parametrize("seed", range(40))
async def test_bam_ngau_nhien_nhieu_vat_tu_nhieu_phong(
    pool: asyncpg.Pool, seed: int
) -> None:
    rng = random.Random(seed)
    identity, vt0, rooms2 = await _bo(pool)
    vts_them, rooms = await _them_vat_tu_va_phong(pool, identity, rooms2)
    vts = [vt0, *vts_them]
    for vt in vts:
        await pool.execute(
            "UPDATE service_price SET gia_nhap_vat_tu=$2 WHERE id=$1::uuid",
            vt,
            rng.choice((50, 100, 120)),
        )
    muc: dict[tuple[str, str | None], Decimal] = {}
    for vt in vts:  # đếm đầu mỗi phòng để có mốc tiêu hao
        for r in rooms:
            await _tao(
                pool, identity, vt, "DIEU_CHINH", tu=r, den=None, so=rng.randint(0, 12)
            )
    tu = await _moc(pool)
    moc = [tu]
    hoan_duoc: list[str] = []
    da_tao: list[tuple[str, str, list[dict[str, Any]], dict[str, Any]]] = []
    ghi: Counter[str] = Counter()
    tu_choi: Counter[str] = Counter()
    da_chon: Counter[str] = Counter()
    trace: tuple[str, ...] = ()
    for buoc in range(20):
        lenh = rng.choice(
            (*_LOAI, "hoan", "hoan", "gia", "dat_muc", "gui_lai", "hoan_hai_lan")
        )
        vt = rng.choice(vts)
        a, b = rng.sample(rooms, 2)
        q = D(rng.randint(1, 6))
        trace = (
            *trace,
            f"seed={seed} buoc={buoc} {lenh} {vt[-4:]} {a[-4:]}>{b[-4:]} q={q}",
        )
        dau = " | ".join(trace)
        da_chon[lenh] += 1
        truoc = await _ton_theo_noi(pool, vts)
        so_phieu_truoc = await pool.fetchval(
            "SELECT count(*) FROM vat_tu_phieu WHERE clinic_id = $1::uuid",
            identity.clinic_id,
        )
        try:
            if lenh == "gia":
                await pool.execute(
                    "UPDATE service_price SET gia_nhap_vat_tu=$2 WHERE id=$1::uuid",
                    vt,
                    rng.choice((50, 100, 150, 200)),
                )
            elif lenh == "dat_muc":
                phong = rng.choice((a, None))
                m = D(rng.randint(0, 15))
                await dat_muc_toi_thieu(
                    pool, identity=identity, vat_tu_id=vt, room_id=phong, muc=m
                )
                muc[(vt, phong)] = m
            elif lenh == "hoan":
                if hoan_duoc:
                    await hoan_phieu(
                        pool,
                        identity=identity,
                        phieu_id=hoan_duoc.pop(rng.randrange(len(hoan_duoc))),
                        khoa_gui=uuid.uuid4().hex,
                    )
            elif lenh == "hoan_hai_lan":
                if hoan_duoc:
                    pid = hoan_duoc.pop(rng.randrange(len(hoan_duoc)))
                    await hoan_phieu(
                        pool, identity=identity, phieu_id=pid, khoa_gui=uuid.uuid4().hex
                    )
                    with pytest.raises((ConflictError, ValidationError)):
                        await hoan_phieu(
                            pool,
                            identity=identity,
                            phieu_id=pid,
                            khoa_gui=uuid.uuid4().hex,
                        )
            elif lenh == "gui_lai":
                if da_tao:
                    pid, khoa, dong, goc = rng.choice(da_tao)
                    lai = await tao_phieu(
                        pool,
                        identity=identity,
                        khoa_gui=khoa,
                        loai=goc["loai"],
                        dong=dong,
                        ghi_chu="Mô phỏng đầy đủ",
                    )
                    assert lai["id"] == pid, f"{dau}: gửi lại tạo phiếu khác"  # V4
            else:
                theo_lenh: dict[str, tuple[str | None, str | None]] = {
                    "nhap": (None, rng.choice((a, None))),
                    "xuat": (None, a),
                    "tra": (a, None),
                    "chuyen": (a, b),
                    "huy": (rng.choice((a, None)), None),
                    "kiem": (a, None),
                    "chinh": (a, None),
                }
                tu_phong, den_phong = theo_lenh[lenh]
                p, khoa, dong = await _tao(
                    pool, identity, vt, _LOAI[lenh], tu=tu_phong, den=den_phong, so=q
                )
                da_tao.append((p["id"], khoa, dong, {"loai": _LOAI[lenh]}))
                if _LOAI[lenh] in _HOAN_DUOC:
                    hoan_duoc.append(p["id"])
        except (ConflictError, ValidationError, NotFoundError):
            tu_choi[lenh] += 1
        sau = await _ton_theo_noi(pool, vts)
        so_phieu_sau = await pool.fetchval(
            "SELECT count(*) FROM vat_tu_phieu WHERE clinic_id = $1::uuid",
            identity.clinic_id,
        )
        if lenh == "gui_lai":  # V4
            assert sau == truoc and so_phieu_sau == so_phieu_truoc, dau
        if sau != truoc:
            ghi[lenh] += 1
        for v in vts:
            await kiem_bat_bien(pool, v, dau)  # V1
        thay = await kiem_man_kho(pool, identity, vts, muc, dau)  # V2
        assert thay is not None
        # V3: chỉ vật tư vừa đụng tới mới được đổi tồn (hoàn: vật tư của phiếu gốc).
        doi = {k[0] for k in {*truoc, *sau} if truoc.get(k, D(0)) != sau.get(k, D(0))}
        assert len(doi) <= 1, f"{dau}: một thao tác đổi tồn nhiều vật tư {doi}"
        moc.append(await _moc(pool))
    den = moc[-1]
    for v in vts:
        await khop_tieu_hao(
            pool, identity, v, tu, den, "cả chuỗi: " + " | ".join(trace)
        )
        cat = rng.choice(moc[1:-1])
        await khop_tieu_hao(
            pool, identity, v, cat, den, "cắt giữa: " + " | ".join(trace)
        )
    print(
        f"MOPHONG seed={seed} chon={dict(da_chon)} ghi={dict(ghi)}"
        f" tu_choi={dict(tu_choi)}"
    )


async def test_nhieu_phieu_cung_luc_so_van_khop_va_khong_lech_ton_may(
    pool: asyncpg.Pool,
) -> None:
    identity, vt, rooms = await _bo(pool)
    a, b = rooms

    async def lam(i: int) -> str:
        try:
            if i % 3 == 0:
                await _tao(pool, identity, vt, "NHAP", tu=None, den=None, so=5)
            elif i % 3 == 1:
                await _tao(pool, identity, vt, "XUAT_PHONG", tu=None, den=a, so=2)
            else:
                await _tao(pool, identity, vt, "CHUYEN_PHONG", tu=a, den=b, so=1)
            return "ok"
        except (ConflictError, ValidationError):
            return "tu_choi"

    kq = await asyncio.gather(*(lam(i) for i in range(12)))
    assert "ok" in kq
    await kiem_bat_bien(pool, vt, "12 phiếu cùng lúc")
    muc: dict[tuple[str, str | None], Decimal] = {}
    await kiem_man_kho(pool, identity, [vt], muc, "12 phiếu cùng lúc")
