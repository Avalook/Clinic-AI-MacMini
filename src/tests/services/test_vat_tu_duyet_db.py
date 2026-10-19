"""G8b — Ai duyệt vật tư cần duyệt (Trưởng ca / Quản lý) + ghi NGUYÊN NHÂN bán thêm.

    scripts/test-nhanh.sh src/tests/services/test_vat_tu_duyet_db.py

Trước: hàng `can_ql_duyet` (vòng Mirena…) chỉ vai MANAGEMENT duyệt được — viết cứng
ở Python (`_la_quan_ly`, `_QUAN_LY_SQL`) và ở trigger `luot_vat_tu_gac`. Nay
người duyệt là người có lego **Duyệt vật tư** (`vat_tu.approve`): mặc định Quản lý
(khối chỉ Quản lý giữ), Quản lý cấp thêm cho Trưởng ca ở màn Phân quyền, tài khoản
Trưởng ca đang có được cấp sẵn lúc áp migration. KHÔNG có đường vòng "vai Quản lý
thì được" — quyền đi theo lego.

BẤT BIẾN:
  D1  Hàng cần duyệt bán được ⇔ có người duyệt đang CÓ lego (lúc bán); không lego
      → từ chối ở Python VÀ ở Postgres (ghi thẳng cũng bị chặn).
  D2  Mất lego sau khi đã duyệt: dòng cũ giữ nguyên, nhưng không duyệt thêm được.
  D3  Người có lego tự bán thì chính họ là người duyệt (vẫn phải ghi lý do duyệt).
  D4  "Nguyên nhân bán thêm" luôn được GHI khi có gửi (5–500 ký tự, rác → 422);
      dây `vat_tu_bat_ly_do_ban` BẬT thì dòng thêm ở quầy PHẢI có (TẮT = tuỳ chọn);
      Bio bác sĩ chọn ở chỉ định (G9) không bao giờ đòi.
"""

from __future__ import annotations

import json
import random
import uuid
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import ClinicAIBaseException
from clinicai.permissions.can import can
from clinicai.permissions.catalogue import (
    KHOI,
    KHOI_CHI_QUAN_LY,
    KHOI_MO_FULL,
    PRESET,
    QUYEN,
)
from clinicai.services.day_noi import DAY, doc_day
from clinicai.services.permission_service import PermissionService
from clinicai.services.vat_tu_service import VatTuService
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai
from tests.services.test_permission_db import quan_ly  # noqa: F401
from tests.services.test_tien_thuoc_cp1_db import Quay, tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]

CLINIC = "a0000000-0000-4000-8000-000000000001"
KHOI_DUYET = "duyet_vat_tu"
QUYEN_DUYET = "vat_tu.approve"
DAY_LY_DO = "vat_tu_bat_ly_do_ban"

pytestmark = pytest.mark.db


async def _vt(q: Quay, ten: str, gia: int | None, *, can_duyet: bool = False) -> str:
    return str(
        await q.pool.fetchval(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " unit_price, active, billing_owner, don_vi, can_ql_duyet, chon_nhanh,"
            " category, kinh_doanh_vat_tu)"
            " VALUES ($1::uuid, $2, $3, 'vat_tu', $4, true, 'CLINIC', 'cái', $5,"
            " false, 'Nguyên liệu tiêu hao', true) RETURNING id::text",
            CLINIC,
            f"VT_TEST_{uuid.uuid4().hex[:10]}",
            f"{ten} {q.duoi}",
            gia,
            can_duyet,
        )
    )


@asynccontextmanager
async def _day(pool: asyncpg.Pool, bat: bool) -> AsyncIterator[None]:
    """Đặt dây "bắt ghi nguyên nhân bán thêm", trả lại như cũ sau đó."""
    cu = await pool.fetchval(
        "SELECT gia_tri::text FROM day_nghiep_vu WHERE clinic_id = $1::uuid"
        " AND ma = $2",
        CLINIC,
        DAY_LY_DO,
    )
    await pool.execute(
        "INSERT INTO day_nghiep_vu (clinic_id, ma, gia_tri)"
        " VALUES ($1::uuid, $2, $3::jsonb)"
        " ON CONFLICT (clinic_id, ma) DO UPDATE SET gia_tri = EXCLUDED.gia_tri",
        CLINIC,
        DAY_LY_DO,
        json.dumps(bat),
    )
    try:
        yield
    finally:
        if cu is None:
            await pool.execute(
                "DELETE FROM day_nghiep_vu WHERE clinic_id = $1::uuid AND ma = $2",
                CLINIC,
                DAY_LY_DO,
            )
        else:
            await pool.execute(
                "UPDATE day_nghiep_vu SET gia_tri = $3::jsonb"
                " WHERE clinic_id = $1::uuid AND ma = $2",
                CLINIC,
                DAY_LY_DO,
                cu,
            )


async def _cap(
    pool: asyncpg.Pool,
    ql: StaffIdentity,
    ai: StaffIdentity,  # noqa: F811
) -> None:
    await PermissionService(pool).cap_khoi(
        staff_id=ai.staff_id, khoi=KHOI_DUYET, identity=ql
    )


async def _thu_hoi(
    pool: asyncpg.Pool,
    ql: StaffIdentity,
    ai: StaffIdentity,  # noqa: F811
) -> None:
    await PermissionService(pool).thu_khoi(
        staff_id=ai.staff_id, khoi=KHOI_DUYET, identity=ql
    )


# ── Catalogue: lego mới KHÔNG nằm trong "mở full" ───────────────────────────


def test_duyet_vat_tu_la_lego_chi_quan_ly_giu_mac_dinh() -> None:
    assert QUYEN[QUYEN_DUYET].khoi == KHOI_DUYET
    assert KHOI_DUYET in KHOI
    # Mặc định chỉ Quản lý (như cũ) — mở cho mọi người thì "duyệt" mất nghĩa.
    assert KHOI_DUYET in KHOI_CHI_QUAN_LY
    assert KHOI_DUYET not in KHOI_MO_FULL
    assert KHOI_DUYET in PRESET["MANAGEMENT"]
    for vai, khoi in PRESET.items():
        if vai != "MANAGEMENT":
            assert KHOI_DUYET not in khoi, vai
    # Có sẵn thành dây: không viết cứng một ngưỡng nào.
    assert DAY[DAY_LY_DO].mac_dinh is False and DAY[DAY_LY_DO].kieu == "bat_tat"


# ── Ai có lego duyệt ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_quan_ly_co_san_truong_ca_duoc_cap_thi_co(
    pool: asyncpg.Pool,
    quan_ly: StaffIdentity,  # noqa: F811
) -> None:
    q = await tao_quay(pool)
    ql = await _nguoi_vai(q, "MANAGEMENT")
    truong_ca = await _nguoi_vai(q, "TRUONG_CA")
    async with pool.acquire() as conn:
        assert await can(conn, ql, QUYEN_DUYET)
        # Tài khoản Trưởng ca MỚI chưa có (mở full không đụng khối này) …
        assert not await can(conn, truong_ca, QUYEN_DUYET)
        assert not await can(conn, q.thu_ngan, QUYEN_DUYET)
    # … Quản lý cấp thì có ngay, thu thì hết ngay.
    await _cap(pool, quan_ly, truong_ca)
    async with pool.acquire() as conn:
        assert await can(conn, truong_ca, QUYEN_DUYET)
    await _thu_hoi(pool, quan_ly, truong_ca)
    async with pool.acquire() as conn:
        assert not await can(conn, truong_ca, QUYEN_DUYET)


# ── Duyệt bán: theo lego, không theo vai ─────────────────────────────────────


@pytest.mark.asyncio
async def test_truong_ca_co_lego_duyet_duoc_mirena_nguoi_khac_thi_khong(
    pool: asyncpg.Pool,
    quan_ly: StaffIdentity,  # noqa: F811
) -> None:
    q = await tao_quay(pool)
    svc = VatTuService(pool)
    mirena = await _vt(q, "Vòng Mirena", 4_000_000, can_duyet=True)
    truong_ca = await _nguoi_vai(q, "TRUONG_CA")
    ky_thuat = await _nguoi_vai(q, "TKYK")
    await _cap(pool, quan_ly, truong_ca)

    # Người "duyệt" không có lego (dù là TKYK / bác sĩ) → từ chối, không ghi gì.
    for ai in (ky_thuat.staff_id, q.bac_si.staff_id, q.thu_ngan.staff_id):
        with pytest.raises(ValidationError):
            await svc.them(
                visit_id=q.visit_id,
                service_price_id=mirena,
                duyet_boi=ai,
                ly_do_duyet="Vòng thứ hai do tụt vòng",
                identity=q.thu_ngan,
            )
    d = await svc.doc(visit_id=q.visit_id, identity=q.thu_ngan)
    assert d["dong"] == []
    # Danh sách chọn người duyệt = những ai CÓ lego, kể cả Trưởng ca được cấp.
    ds = {x["id"] for x in d["quan_ly"]}
    assert truong_ca.staff_id in ds
    assert ky_thuat.staff_id not in ds and q.thu_ngan.staff_id not in ds
    assert d["la_quan_ly"] is False

    # Trưởng ca có lego duyệt → thu ngân bán được, ghi đúng người duyệt.
    kq = await svc.them(
        visit_id=q.visit_id,
        service_price_id=mirena,
        duyet_boi=truong_ca.staff_id,
        ly_do_duyet="Vòng thứ hai: vòng đầu tụt khi đặt",
        identity=q.thu_ngan,
    )
    (dong,) = kq["dong"]
    assert dong["nguoi_duyet"] == truong_ca.full_name


@pytest.mark.asyncio
async def test_nguoi_co_lego_tu_ban_la_tu_duyet_het_lego_thi_khong(
    pool: asyncpg.Pool,
    quan_ly: StaffIdentity,  # noqa: F811
) -> None:
    q = await tao_quay(pool)
    svc = VatTuService(pool)
    mirena = await _vt(q, "Vòng Mirena", 4_000_000, can_duyet=True)
    truong_ca = await _nguoi_vai(q, "TRUONG_CA")
    await _cap(pool, quan_ly, truong_ca)

    # Có lego: tự thêm = tự duyệt, vẫn phải ghi lý do.
    with pytest.raises(ValidationError):
        await svc.them(visit_id=q.visit_id, service_price_id=mirena, identity=truong_ca)
    kq = await svc.them(
        visit_id=q.visit_id,
        service_price_id=mirena,
        ly_do_duyet="Sự cố vòng thứ hai",
        identity=truong_ca,
    )
    assert kq["dong"][0]["nguoi_duyet"] == truong_ca.full_name
    assert (await svc.doc(visit_id=q.visit_id, identity=truong_ca))["la_quan_ly"]

    # Thu lego: dòng cũ GIỮ NGUYÊN, nhưng không còn tự duyệt / làm người duyệt.
    await _thu_hoi(pool, quan_ly, truong_ca)
    d = await svc.doc(visit_id=q.visit_id, identity=q.thu_ngan)
    assert [x["nguoi_duyet"] for x in d["dong"]] == [truong_ca.full_name]
    assert truong_ca.staff_id not in {x["id"] for x in d["quan_ly"]}
    cho_khac = await _nguoi_vai(q, "RECEPTION")
    mirena2 = await _vt(q, "Vòng Mirena 2", 4_000_000, can_duyet=True)
    with pytest.raises(ValidationError):
        await svc.them(
            visit_id=q.visit_id,
            service_price_id=mirena2,
            duyet_boi=truong_ca.staff_id,
            ly_do_duyet="Đã hết quyền duyệt",
            identity=cho_khac,
        )
    with pytest.raises(ValidationError):
        await svc.them(
            visit_id=q.visit_id,
            service_price_id=mirena2,
            ly_do_duyet="Hết quyền thì không tự duyệt",
            identity=truong_ca,
        )


@pytest.mark.asyncio
async def test_quan_ly_bi_thu_khoi_thi_khong_con_duyet_khong_duong_vong_theo_vai(
    pool: asyncpg.Pool,
    quan_ly: StaffIdentity,  # noqa: F811
) -> None:
    """Không có "vai Quản lý thì được tất": thu khối của một tài khoản Quản lý là
    họ không duyệt được nữa (quyền đi theo lego)."""
    q = await tao_quay(pool)
    svc = VatTuService(pool)
    mirena = await _vt(q, "Vòng Mirena", 4_000_000, can_duyet=True)
    ql = await _nguoi_vai(q, "MANAGEMENT")
    await _thu_hoi(pool, quan_ly, ql)
    with pytest.raises(ValidationError):
        await svc.them(
            visit_id=q.visit_id,
            service_price_id=mirena,
            duyet_boi=ql.staff_id,
            ly_do_duyet="Không còn lego duyệt",
            identity=q.thu_ngan,
        )
    with pytest.raises(ValidationError):
        await svc.them(
            visit_id=q.visit_id,
            service_price_id=mirena,
            ly_do_duyet="Không còn lego duyệt",
            identity=ql,
        )


@pytest.mark.asyncio
async def test_postgres_gac_nguoi_duyet_theo_lego(
    pool: asyncpg.Pool,
    quan_ly: StaffIdentity,  # noqa: F811
) -> None:
    q = await tao_quay(pool)
    mirena = await _vt(q, "Vòng Mirena", 4_000_000, can_duyet=True)
    truong_ca = await _nguoi_vai(q, "TRUONG_CA")
    sql = (
        "INSERT INTO luot_vat_tu (clinic_id, visit_id, service_price_id, ten,"
        " don_gia, so_luong, duyet_boi, duyet_ly_do)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, 'x', 4000000, 1, $4::uuid,"
        " 'Duyệt thử ở Postgres')"
    )
    # Ghi thẳng với người "duyệt" không có lego → Postgres chặn.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(sql, CLINIC, q.visit_id, mirena, truong_ca.staff_id)
    await _cap(pool, quan_ly, truong_ca)
    await pool.execute(sql, CLINIC, q.visit_id, mirena, truong_ca.staff_id)


# ── Nguyên nhân bán thêm ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ly_do_ban_duoc_ghi_va_rac_bi_tu_choi(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    svc = VatTuService(pool)
    vt = await _vt(q, "Gạc thử", 20_000)
    # Dây mặc định TẮT: không gửi lý do vẫn bán (hành vi cũ giữ nguyên) …
    async with pool.acquire() as conn:
        assert await doc_day(conn, CLINIC, DAY_LY_DO) is False
    kq = await svc.them(visit_id=q.visit_id, service_price_id=vt, identity=q.thu_ngan)
    assert kq["dong"][0]["ly_do_ban"] is None
    # … nhưng đã gửi thì phải hợp lệ — không ghi rác.
    for rac in ("", "   ", "abcd", "x" * 501, 123, ["lý do"], True):
        vt2 = await _vt(q, "Gạc khác", 20_000)
        with pytest.raises(ValidationError):
            await svc.them(
                visit_id=q.visit_id,
                service_price_id=vt2,
                ly_do_ban=rac,
                identity=q.thu_ngan,
            )
    vt3 = await _vt(q, "Kim thử", 20_000)
    kq = await svc.them(
        visit_id=q.visit_id,
        service_price_id=vt3,
        ly_do_ban="Khách yêu cầu thêm kim",
        identity=q.thu_ngan,
    )
    theo = {d["service_price_id"]: d for d in kq["dong"]}
    assert theo[vt3]["ly_do_ban"] == "Khách yêu cầu thêm kim"
    assert (
        await pool.fetchval(
            "SELECT ly_do_ban FROM luot_vat_tu WHERE id = $1::uuid",
            theo[vt3]["id"],
        )
        == "Khách yêu cầu thêm kim"
    )


@pytest.mark.asyncio
async def test_bat_day_thi_dong_them_o_quay_phai_co_ly_do(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    svc = VatTuService(pool)
    vt = await _vt(q, "Gạc thử", 20_000)
    async with _day(pool, True):
        with pytest.raises(ValidationError):
            await svc.them(
                visit_id=q.visit_id, service_price_id=vt, identity=q.thu_ngan
            )
        kq = await svc.them(
            visit_id=q.visit_id,
            service_price_id=vt,
            ly_do_ban="Khách làm thêm thủ thuật cần gạc",
            identity=q.thu_ngan,
        )
        assert kq["dong"][0]["so_luong"] == 1
        # Bấm tiếp (cộng dồn) khi dòng ĐÃ có lý do: không hỏi lại.
        kq = await svc.them(
            visit_id=q.visit_id, service_price_id=vt, identity=q.thu_ngan
        )
        assert kq["dong"][0]["so_luong"] == 2
        # Đổi số lượng không đòi lý do.
        kq = await svc.dat_so_luong(
            dong_id=kq["dong"][0]["id"], so_luong=3, identity=q.thu_ngan
        )
        assert kq["dong"][0]["so_luong"] == 3
    # Tắt dây lại → như cũ.
    vt2 = await _vt(q, "Kim thử", 20_000)
    await svc.them(visit_id=q.visit_id, service_price_id=vt2, identity=q.thu_ngan)


@pytest.mark.asyncio
async def test_hang_can_duyet_bat_day_can_ca_ly_do_duyet_lan_ly_do_ban(
    pool: asyncpg.Pool,
    quan_ly: StaffIdentity,  # noqa: F811
) -> None:
    q = await tao_quay(pool)
    svc = VatTuService(pool)
    mirena = await _vt(q, "Vòng Mirena", 4_000_000, can_duyet=True)
    truong_ca = await _nguoi_vai(q, "TRUONG_CA")
    await _cap(pool, quan_ly, truong_ca)
    async with _day(pool, True):
        with pytest.raises(ValidationError):  # có duyệt, thiếu nguyên nhân bán
            await svc.them(
                visit_id=q.visit_id,
                service_price_id=mirena,
                duyet_boi=truong_ca.staff_id,
                ly_do_duyet="Vòng đầu tụt khi đặt",
                identity=q.thu_ngan,
            )
        kq = await svc.them(
            visit_id=q.visit_id,
            service_price_id=mirena,
            duyet_boi=truong_ca.staff_id,
            ly_do_duyet="Vòng đầu tụt khi đặt",
            ly_do_ban="Tụt vòng khi đặt, cần vòng thứ hai",
            identity=q.thu_ngan,
        )
    d = kq["dong"][0]
    assert d["ly_do_duyet"] == "Vòng đầu tụt khi đặt"
    assert d["ly_do_ban"] == "Tụt vòng khi đặt, cần vòng thứ hai"


# ── Bấm lộn xộn: cấp / thu lego, bật / tắt dây, bán, bỏ ─────────────────────

SO_HAT = 40
SO_BUOC = 10


@pytest.mark.asyncio
async def test_bam_lon_xon_duyet_va_ly_do_khong_lech(
    pool: asyncpg.Pool,
    quan_ly: StaffIdentity,  # noqa: F811
) -> None:
    lech: list[str] = []
    chay: Counter[str] = Counter()
    chan: Counter[str] = Counter()
    for hat in range(SO_HAT):
        rnd = random.Random(hat)
        q = await tao_quay(pool)
        svc = VatTuService(pool)
        mirena = await _vt(q, "Vòng Mirena", 4_000_000, can_duyet=True)
        gac = await _vt(q, "Gạc thử", 20_000)
        tc = await _nguoi_vai(q, "TRUONG_CA")
        co_lego = False
        dang_bat = False
        da_lam: list[str] = []
        luc_tao: dict[str, bool] = {}
        cm: Any = _day(pool, False)
        await cm.__aenter__()
        try:
            for _ in range(SO_BUOC):
                viec = rnd.choice(
                    [
                        "cap_lego",
                        "thu_lego",
                        "bat_day",
                        "tat_day",
                        "ban_mirena_qua_tc",
                        "tc_tu_ban_mirena",
                        "ban_gac_co_ly_do",
                        "ban_gac_khong_ly_do",
                        "bo_dong",
                    ]
                )
                try:
                    if viec == "cap_lego":
                        await _cap(pool, quan_ly, tc)
                        co_lego = True
                    elif viec == "thu_lego":
                        await _thu_hoi(pool, quan_ly, tc)
                        co_lego = False
                    elif viec in ("bat_day", "tat_day"):
                        await cm.__aexit__(None, None, None)
                        dang_bat = viec == "bat_day"
                        cm = _day(pool, dang_bat)
                        await cm.__aenter__()
                    elif viec == "ban_mirena_qua_tc":
                        await svc.them(
                            visit_id=q.visit_id,
                            service_price_id=mirena,
                            duyet_boi=tc.staff_id,
                            ly_do_duyet="Vòng đầu tụt khi đặt",
                            ly_do_ban="Cần vòng thứ hai",
                            identity=q.thu_ngan,
                        )
                        if not co_lego:
                            lech.append(
                                f"hạt {hat}: {da_lam + [viec]} duyệt khi không lego"
                            )
                    elif viec == "tc_tu_ban_mirena":
                        await svc.them(
                            visit_id=q.visit_id,
                            service_price_id=mirena,
                            ly_do_duyet="Sự cố vòng thứ hai",
                            ly_do_ban="Cần vòng thứ hai",
                            identity=tc,
                        )
                        if not co_lego:
                            lech.append(
                                f"hạt {hat}: {da_lam + [viec]} tự duyệt không lego"
                            )
                    elif viec == "ban_gac_co_ly_do":
                        await svc.them(
                            visit_id=q.visit_id,
                            service_price_id=gac,
                            ly_do_ban="Khách làm thêm thủ thuật",
                            identity=q.thu_ngan,
                        )
                    elif viec == "ban_gac_khong_ly_do":
                        await svc.them(
                            visit_id=q.visit_id,
                            service_price_id=gac,
                            identity=q.thu_ngan,
                        )
                    else:
                        d = await svc.doc(visit_id=q.visit_id, identity=q.thu_ngan)
                        assert d["dong"], "không có dòng để bỏ"
                        await svc.bo(dong_id=d["dong"][0]["id"], identity=q.thu_ngan)
                except (ClinicAIBaseException, AssertionError):
                    chan[viec] += 1
                    continue
                chay[viec] += 1
                da_lam.append(viec)
                # Bất biến: dòng gạc TẠO LÚC dây BẬT phải có lý do; Mirena luôn có
                # người + lý do duyệt.
                d = await svc.doc(visit_id=q.visit_id, identity=q.thu_ngan)
                for x in d["dong"]:
                    if x["service_price_id"] == gac:
                        luc_tao.setdefault(x["id"], dang_bat)
                        if luc_tao[x["id"]] and x["ly_do_ban"] is None:
                            lech.append(f"hạt {hat}: {da_lam} gạc không lý do khi BẬT")
                    if x["service_price_id"] == mirena and not (
                        x["nguoi_duyet"] and x["ly_do_duyet"]
                    ):
                        lech.append(f"hạt {hat}: {da_lam} Mirena thiếu duyệt")
                if lech:
                    break
        finally:
            await cm.__aexit__(None, None, None)
    print(f"\nCHẠY: {dict(chay)}\nBỊ CHẶN: {dict(chan)}\nLỆCH: {lech or '(không)'}")
    assert lech == []
    assert chay["ban_mirena_qua_tc"] + chay["tc_tu_ban_mirena"] >= 5
    assert chan["ban_mirena_qua_tc"] + chan["tc_tu_ban_mirena"] >= 5
