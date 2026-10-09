"""Lịch trực có lịch sử thay đổi (Khối 3, Tuyền 06/10/2026) — trigger + service + API.

Kịch bản Tuyền chốt: áp dụng tuần → có phiên bản gốc. Đổi người 1 ca, xoá 1
ca, thêm người vào ca trống → mỗi lần 1 phiên bản; chọn phiên bản bất kỳ thấy
đúng bảng lịch lúc đó, ô đổi mang đúng loại (THEM / XOA / DOI_NGUOI) và người
bấm là trưởng ca.

Mỗi bài dùng một tuần ngẫu nhiên ở thập niên 2090 (DB thử dùng chung với các
luồng khác — không giẫm tuần của ai), dọn tuần ấy khi xong.
"""

from __future__ import annotations

import datetime as dt
import random
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import httpx
import pytest
import pytest_asyncio

from clinicai.api.identity import StaffIdentity, _resolve_identity
from clinicai.core.database import get_db_pool
from clinicai.main import app
from clinicai.services.booking_service import BookingService
from clinicai.services.config_service import RosterService
from clinicai.services.lich_truc_phien_ban_service import (
    LichTrucPhienBanService,
    dat_nguoi_bam,
    giao_dich_lich_truc,
)
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_luot_kham_service_db import KichBan

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _tuan_ngau_nhien() -> dt.date:
    d = dt.date(2090, 1, 2) + dt.timedelta(weeks=random.randint(0, 500))
    return d - dt.timedelta(days=d.weekday())


@pytest_asyncio.fixture
async def tuan(kb: KichBan) -> AsyncIterator[dt.date]:
    w = _tuan_ngau_nhien()
    yield w
    async with kb.pool.acquire() as conn:
        cid = kb.truong_ca.clinic_id
        await conn.execute(
            "DELETE FROM work_roster WHERE clinic_id = $1::uuid AND week_start = $2",
            cid,
            w,
        )
        await conn.execute(
            "DELETE FROM roster_week WHERE clinic_id = $1::uuid AND week_start = $2",
            cid,
            w,
        )
        for bang in ("lich_truc_anh", "lich_truc_thay_doi"):
            await conn.execute(
                f"DELETE FROM {bang} WHERE clinic_id = $1::uuid AND week_start = $2",
                cid,
                w,
            )


async def _tram(conn: asyncpg.Connection, cid: str, vai: str) -> str:
    """Một vị trí vai này được xếp vào (ma trận vai × vị trí); chưa khai → mã thử."""
    tram = await conn.fetchval(
        "SELECT tram_ma FROM vai_duoc_vao_tram WHERE clinic_id = $1::uuid"
        " AND vai = $2 AND is_active ORDER BY tram_ma LIMIT 1",
        cid,
        vai,
    )
    return str(tram) if tram else f"T-PB-{uuid.uuid4().hex[:6]}"


async def test_ap_dung_doi_xoa_them_moi_lan_mot_phien_ban(
    kb: KichBan, tuan: dt.date
) -> None:
    roster = RosterService(kb.pool)
    lich_su = LichTrucPhienBanService(kb.pool)
    tc = kb.truong_ca
    d1, d2 = tuan, tuan + dt.timedelta(days=1)
    async with kb.pool.acquire() as conn:
        tram_bs = await _tram(conn, tc.clinic_id, "DOCTOR")
        tram_dd = await _tram(conn, tc.clinic_id, "NURSE_ULTRASOUND")

    a = await roster.add_shift(
        work_date=d1,
        station=tram_bs,
        shift="FULL",
        identity=tc,
        staff_id=kb.bac_si.staff_id,
    )
    b = await roster.add_shift(
        work_date=d2,
        station=tram_bs,
        shift="FULL",
        identity=tc,
        staff_id=kb.bac_si_2.staff_id,
    )
    c = await roster.add_shift(
        work_date=d1,
        station=tram_dd,
        shift="FULL",
        identity=tc,
        staff_id=kb.dieu_duong.staff_id,
    )

    # Trước khi áp dụng: xếp nháp, chưa có lịch sử.
    chua = await lich_su.xem(identity=tc, tuan=tuan.isoformat())
    assert chua["co_lich_su"] is False
    assert chua["da_ap_dung"] is False
    assert chua["phien_ban"] == [] and chua["dang_xem"] is None
    assert chua["nhat_ky"] == []

    await roster.apply_week(week_start=d2, identity=tc)  # ngày giữa tuần → thứ Hai
    goc = await lich_su.xem(identity=tc, tuan=tuan.isoformat())
    assert goc["co_lich_su"] is True and goc["da_ap_dung"] is True
    assert [p["loai"] for p in goc["phien_ban"]] == ["GOC"]
    assert goc["phien_ban"][0]["boi_ten"] == tc.full_name
    assert sorted(o["id"] for o in goc["dang_xem"]["dong"]) == sorted([a, b, c])
    assert all(o["thay_doi"] is None for o in goc["dang_xem"]["dong"])

    # Đổi người 1 ca · xoá 1 ca · thêm người vào ca trống.
    await roster.thay_nguoi(
        roster_id=a, staff_moi_id=kb.bs_sieu_am.staff_id, identity=tc
    )
    await roster.remove(roster_id=b, identity=tc)
    e = await roster.add_shift(
        work_date=d2,
        station=tram_dd,
        shift="FULL",
        identity=tc,
        staff_id=kb.dieu_duong.staff_id,
    )

    moi = await lich_su.xem(identity=tc, tuan=tuan.isoformat())
    ds = moi["phien_ban"]  # mới nhất trước
    assert [p["loai"] for p in ds] == ["THAY_DOI", "THAY_DOI", "THAY_DOI", "GOC"]
    assert all(p["boi_ten"] == tc.full_name for p in ds)
    assert [p["so"] for p in ds[:3]] == [
        {"them": 1, "xoa": 0, "doi_nguoi": 0},
        {"them": 0, "xoa": 1, "doi_nguoi": 0},
        {"them": 0, "xoa": 0, "doi_nguoi": 1},
    ]
    ma_them, ma_xoa, ma_doi, ma_goc = (p["ma"] for p in ds)

    # Bản mới nhất: e là THÊM; a đã là người mới, không còn tô (đổi ở bản trước).
    dx = moi["dang_xem"]
    assert dx["ma"] == ma_them and dx["moi_nhat"] is True and dx["truoc_ma"] == ma_xoa
    theo_id = {o["id"]: o for o in dx["dong"]}
    assert set(theo_id) == {a, c, e}
    assert theo_id[e]["thay_doi"] == "THEM"
    assert theo_id[a]["thay_doi"] is None
    assert theo_id[a]["staff_id"] == kb.bs_sieu_am.staff_id
    assert dx["da_xoa"] == []

    # Nhật ký tuần (nuôi "Lịch sử ô này"): ba dòng, mới nhất trước, tên chuẩn.
    nk = moi["nhat_ky"]
    assert [(n["loai"], n["roster_id"]) for n in nk] == [
        ("THEM", e),
        ("XOA", b),
        ("DOI_NGUOI", a),
    ]
    assert nk[2]["truoc_ten"] == kb.bac_si.full_name
    assert nk[2]["ten"] == kb.bs_sieu_am.full_name
    assert all(n["boi_ten"] == tc.full_name for n in nk)
    assert (nk[1]["work_date"], nk[1]["station"]) == (d2.isoformat(), tram_bs)

    # Bản đổi người: a là "BS cũ → BS mới", b còn nguyên.
    doi = (await lich_su.xem(identity=tc, tuan=tuan.isoformat(), ban=ma_doi))[
        "dang_xem"
    ]
    theo_id = {o["id"]: o for o in doi["dong"]}
    assert set(theo_id) == {a, b, c}
    assert theo_id[a]["thay_doi"] == "DOI_NGUOI"
    assert theo_id[a]["truoc_ten"] == kb.bac_si.full_name
    assert theo_id[a]["staff_name"] == kb.bs_sieu_am.full_name
    assert doi["moi_nhat"] is False

    # Bản xoá: b nằm ở danh sách đã xoá, không còn trên bảng.
    xoa = (await lich_su.xem(identity=tc, tuan=tuan.isoformat(), ban=ma_xoa))[
        "dang_xem"
    ]
    assert {o["id"] for o in xoa["dong"]} == {a, c}
    assert [(o["id"], o["thay_doi"]) for o in xoa["da_xoa"]] == [(b, "XOA")]
    assert xoa["da_xoa"][0]["staff_name"] == kb.bac_si_2.full_name

    # Bản gốc: đúng bảng lúc áp dụng.
    g = (await lich_su.xem(identity=tc, tuan=tuan.isoformat(), ban=ma_goc))["dang_xem"]
    assert {o["id"]: o["staff_id"] for o in g["dong"]} == {
        a: kb.bac_si.staff_id,
        b: kb.bac_si_2.staff_id,
        c: kb.dieu_duong.staff_id,
    }

    # Mã phiên bản rác → bản mới nhất, không ném.
    for rac in ("abc", "-1", "", None, "99999999999999999999", "1"):
        r = await lich_su.xem(identity=tc, tuan=tuan.isoformat(), ban=rac)
        assert r["dang_xem"]["ma"] == ma_them

    # Áp dụng lại → một mốc AP_DUNG_LAI.
    await roster.apply_week(week_start=tuan, identity=tc)
    lai = await lich_su.xem(identity=tc, tuan=tuan.isoformat())
    assert lai["phien_ban"][0]["loai"] == "AP_DUNG_LAI"
    assert lai["dang_xem"]["so"] == {"them": 0, "xoa": 0, "doi_nguoi": 0}

    # Sổ thô: mọi dòng sau khi áp dụng đều mang người bấm.
    async with kb.pool.acquire() as conn:
        nguoi = await conn.fetch(
            "SELECT DISTINCT boi_staff_id::text FROM lich_truc_thay_doi"
            " WHERE clinic_id = $1::uuid AND week_start = $2",
            tc.clinic_id,
            tuan,
        )
    assert [r[0] for r in nguoi] == [tc.staff_id]


async def test_trigger_ghi_khi_khong_dat_nguoi_bam_va_khi_rac(
    kb: KichBan, tuan: dt.date
) -> None:
    """Lối quên đặt người bấm (hoặc đặt rác) vẫn ghi được — chỉ thiếu tên."""
    cid = kb.truong_ca.clinic_id
    async with kb.pool.acquire() as conn:
        rid = await conn.fetchval(
            "INSERT INTO work_roster (clinic_id, week_start, work_date, shift,"
            " station, staff_id, staff_name, status) VALUES ($1::uuid, $2, $2,"
            " 'FULL', 'T-PB-THO', $3::uuid, 'A', 'APPROVED') RETURNING id::text",
            cid,
            tuan,
            kb.bac_si.staff_id,
        )
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.staff_id', 'không-phải-uuid', true)"
            )
            await conn.execute(
                "UPDATE work_roster SET staff_name = 'B' WHERE id = $1::uuid", rid
            )
        # Đổi thứ không hiện trên bảng (thứ tự) → không ghi.
        await conn.execute("UPDATE work_roster SET sort = 9 WHERE id = $1::uuid", rid)
        async with giao_dich_lich_truc(conn, kb.truong_ca.staff_id):
            await conn.execute("DELETE FROM work_roster WHERE id = $1::uuid", rid)
        dong = await conn.fetch(
            "SELECT hanh_dong, boi_staff_id::text FROM lich_truc_thay_doi"
            " WHERE roster_id = $1::uuid ORDER BY id",
            rid,
        )
        # Hết giao dịch, người bấm không dính sang câu lệnh sau.
        assert await conn.fetchval("SELECT public.lich_truc_nguoi_bam()") is None
    assert [(r[0], r[1]) for r in dong] == [
        ("THEM", None),
        ("DOI_NGUOI", None),
        ("XOA", kb.truong_ca.staff_id),
    ]


async def test_doi_ngay_sang_tuan_khac_ghi_ca_hai_tuan(
    kb: KichBan, tuan: dt.date
) -> None:
    cid = kb.truong_ca.clinic_id
    tuan_sau = tuan + dt.timedelta(days=7)
    try:
        async with kb.pool.acquire() as conn:
            rid = await conn.fetchval(
                "INSERT INTO work_roster (clinic_id, week_start, work_date, shift,"
                " station, staff_name, status) VALUES ($1::uuid, $2, $2, 'FULL',"
                " 'T-PB-THO', 'A', 'APPROVED') RETURNING id::text",
                cid,
                tuan,
            )
            await conn.execute(
                "UPDATE work_roster SET week_start = $2, work_date = $2"
                " WHERE id = $1::uuid",
                rid,
                tuan_sau,
            )
            dong = await conn.fetch(
                "SELECT week_start, hanh_dong FROM lich_truc_thay_doi"
                " WHERE roster_id = $1::uuid ORDER BY id",
                rid,
            )
        assert [(r[0], r[1]) for r in dong] == [
            (tuan, "THEM"),
            (tuan, "XOA"),
            (tuan_sau, "THEM"),
        ]
    finally:
        async with kb.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM work_roster"
                " WHERE clinic_id = $1::uuid AND week_start = $2",
                cid,
                tuan_sau,
            )
            await conn.execute(
                "DELETE FROM lich_truc_thay_doi WHERE clinic_id = $1::uuid"
                " AND week_start = $2",
                cid,
                tuan_sau,
            )


async def test_dat_nguoi_bam_ngoai_giao_dich_la_loi_lap_trinh(kb: KichBan) -> None:
    async with kb.pool.acquire() as conn:
        with pytest.raises(RuntimeError):
            await dat_nguoi_bam(conn, kb.truong_ca.staff_id)


async def test_tu_xep_ca_khi_gan_bac_si_mang_nguoi_bam(
    kb: KichBan, tuan: dt.date
) -> None:
    """Lối thứ năm (`BookingService._xep_vao_lich_truc`, tuần chưa công bố)."""
    gio = dt.datetime.combine(tuan + dt.timedelta(days=2), dt.time(9, 0), tzinfo=dt.UTC)
    async with kb.pool.acquire() as conn, conn.transaction():
        await BookingService(kb.pool)._xep_vao_lich_truc(
            conn,
            appointment_id=str(uuid.uuid4()),
            doctor_id=kb.bac_si.staff_id,
            slot_start=gio,
            identity=kb.truong_ca,
        )
    async with kb.pool.acquire() as conn:
        boi = await conn.fetch(
            "SELECT hanh_dong, boi_staff_id::text FROM lich_truc_thay_doi"
            " WHERE clinic_id = $1::uuid AND week_start = $2",
            kb.truong_ca.clinic_id,
            tuan,
        )
    assert [(r[0], r[1]) for r in boi] == [("THEM", kb.truong_ca.staff_id)]


async def test_tuan_rac_va_tuan_chua_co_lich_su(kb: KichBan, tuan: dt.date) -> None:
    svc = LichTrucPhienBanService(kb.pool)
    rac_ds: list[object] = [None, "", "abc", "99-99-9999", "2026-02-30", 5, []]
    for rac in rac_ds:
        r = await svc.xem(identity=kb.truong_ca, tuan=rac)
        assert r["tuan"] is None and r["co_lich_su"] is False
        assert r["phien_ban"] == [] and r["dang_xem"] is None
    r = await svc.xem(identity=kb.truong_ca, tuan=tuan + dt.timedelta(days=3))
    assert r["tuan"] == tuan.isoformat()
    assert r["co_lich_su"] is False and r["da_ap_dung"] is False


# ── HTTP ─────────────────────────────────────────────────────────────────────
HIEN_TAI: dict[str, StaffIdentity] = {}


@pytest_asyncio.fixture
async def http(kb: KichBan) -> AsyncIterator[httpx.AsyncClient]:
    app.dependency_overrides[get_db_pool] = lambda: kb.pool
    app.dependency_overrides[_resolve_identity] = lambda: HIEN_TAI["ai"]
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://lich"
        ) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db_pool, None)
        app.dependency_overrides.pop(_resolve_identity, None)


async def test_api_chi_nguoi_xep_lich_xem_duoc(
    kb: KichBan, tuan: dt.date, http: httpx.AsyncClient
) -> None:
    async with kb.pool.acquire() as conn:
        await ve_goi_mau_cu(conn, kb.le_tan)  # gói lego cũ: lễ tân không xếp lịch
    HIEN_TAI["ai"] = kb.le_tan
    r = await http.get("/api/v1/roster/phien-ban", params={"tuan": tuan.isoformat()})
    assert r.status_code == 403

    HIEN_TAI["ai"] = kb.truong_ca
    r = await http.get("/api/v1/roster/phien-ban", params={"tuan": tuan.isoformat()})
    assert r.status_code == 200
    body: dict[str, Any] = r.json()
    assert body["tuan"] == tuan.isoformat() and body["co_lich_su"] is False

    # Rác ở URL: 200 + rỗng, không 422 / 500.
    for q in ({"tuan": "99-99-9999"}, {"tuan": "abc", "ban": "x"}, {}):
        r = await http.get("/api/v1/roster/phien-ban", params=q)
        assert r.status_code == 200, q
        assert r.json()["tuan"] is None
