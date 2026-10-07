"""Nhận khách tại phòng — dây ``nhan_tai_phong`` (Tuyền chốt 07/10/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55600/postgres \\
        .venv/bin/pytest src/tests/services/test_nhan_tai_phong_db.py

Kế hoạch: docs/KE-HOACH-NHAN-TAI-PHONG.md, mục "Kiểm". Hai phòng siêu âm riêng
của mỗi bài (fixture ``rb``); chỉ định gắn riêng phòng (`clinic_room_service`)
để "nhận theo khách" chỉ kéo đúng chỉ định phòng ấy làm được.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.events.consumers.hanh_trinh import _tu_xep_bat
from clinicai.services import nhan_tai_phong as ntp
from clinicai.services.lenh_kham_core import khoa_luot
from clinicai.services.luot_kham_doc import BangLuotKham
from clinicai.services.luot_kham_service import LuotKhamConflictError
from clinicai.services.service_execution_service import ServiceExecutionService
from clinicai.services.service_selection_service import SelectionInput, ap_lua_chon
from tests.services.test_luot_kham_service_db import CLINIC, KichBan, _vao_kham
from tests.services.test_service_routing_db import (  # noqa: F401
    RB,
    _cd,
    _loi,
    _o,
    rb,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _dat_day(pool: asyncpg.Pool, ma: str, gia_tri: Any) -> Any:
    cu = await pool.fetchval(
        "SELECT gia_tri::text FROM day_nghiep_vu WHERE clinic_id = $1::uuid"
        " AND ma = $2",
        CLINIC,
        ma,
    )
    await pool.execute(
        "INSERT INTO day_nghiep_vu (clinic_id, ma, gia_tri) VALUES ($1::uuid, $2,"
        " $3::jsonb) ON CONFLICT (clinic_id, ma) DO UPDATE SET gia_tri ="
        " EXCLUDED.gia_tri",
        CLINIC,
        ma,
        json.dumps(gia_tri),
    )
    return cu


async def _tra_day(pool: asyncpg.Pool, ma: str, cu: Any) -> None:
    if cu is None:
        await pool.execute(
            "DELETE FROM day_nghiep_vu WHERE clinic_id = $1::uuid AND ma = $2",
            CLINIC,
            ma,
        )
    else:
        await _dat_day(pool, ma, json.loads(cu))


@pytest_asyncio.fixture
async def bat(rb: RB) -> AsyncIterator[RB]:  # noqa: F811
    """Dây Nhận tại phòng BẬT cho bài này, trả lại như cũ sau đó."""
    cu = await _dat_day(rb.pool, "nhan_tai_phong", True)
    try:
        yield rb
    finally:
        await _tra_day(rb.pool, "nhan_tai_phong", cu)


async def _chi_o(b: RB, oid: str, *phong: str) -> None:
    """Dịch vụ của chỉ định chỉ làm ở các phòng này."""
    ma = await b.pool.fetchval(
        "SELECT service_code FROM service_order WHERE id = $1::uuid", oid
    )
    for p in phong:
        await b.pool.execute(
            "INSERT INTO clinic_room_service (clinic_id, room_id, service_code)"
            " VALUES ($1::uuid, $2::uuid, $3)",
            CLINIC,
            p,
            ma,
        )


async def _cd_o(b: RB, *phong: str, **kw: Any) -> str:
    oid = await _cd(b, **kw)
    await _chi_o(b, oid, *phong)
    return oid


async def _nhan(
    b: RB, room: str, *, xac_nhan: bool = False, visit_id: str | None = None
) -> dict[str, Any]:
    return await ntp.NhanTaiPhongService(b.pool).nhan(
        visit_id=visit_id or b.visit_id,
        room_id=room,
        identity=b.truong_ca,
        xac_nhan=xac_nhan,
    )


async def _cho(b: RB, oid: str) -> list[asyncpg.Record]:
    return list(
        await b.pool.fetch(
            "SELECT room_id::text AS room_id, status, eligible_at, done_at"
            " FROM queue_entry WHERE ref_id = $1::uuid AND reason = 'SERVICE'"
            " ORDER BY created_at, updated_at",
            oid,
        )
    )


async def _song(b: RB, oid: str) -> asyncpg.Record | None:
    return await b.pool.fetchrow(
        "SELECT room_id::text AS room_id, status, eligible_at FROM queue_entry"
        " WHERE ref_id = $1::uuid AND reason = 'SERVICE'"
        "   AND status NOT IN ('done', 'left', 'cancelled')",
        oid,
    )


async def _sk(b: RB, oid: str, ten: str) -> list[dict[str, Any]]:
    rows = await b.pool.fetch(
        "SELECT event_id::text AS id, payload FROM domain_event"
        " WHERE aggregate_id = $1::uuid AND event_type = $2 ORDER BY seq",
        oid,
        ten,
    )
    return [{"event_id": r["id"], **json.loads(r["payload"])} for r in rows]


async def _moc(b: RB, visit_id: str | None = None) -> list[asyncpg.Record]:
    return list(
        await b.pool.fetch(
            "SELECT * FROM v_moc_hanh_trinh WHERE visit_id = $1::uuid ORDER BY seq",
            visit_id or b.visit_id,
        )
    )


def _exe(b: RB) -> ServiceExecutionService:
    return ServiceExecutionService(b.pool)


async def _bat_dau(b: RB, oid: str, *, giai_phong: bool = False) -> dict[str, Any]:
    r = await b.pool.fetchrow(
        "SELECT execution_revision, routing_revision FROM service_order"
        " WHERE id = $1::uuid",
        oid,
    )
    assert r is not None
    return await _exe(b).bat_dau(
        order_id=oid,
        expected_execution_revision=int(r["execution_revision"]),
        expected_routing_revision=int(r["routing_revision"]),
        identity=b.bac_si,
        idempotency_key=str(uuid.uuid4()),
        giai_phong=giai_phong,
    )


async def _xong(b: RB, oid: str, attempt_id: str) -> dict[str, Any]:
    rev = await b.pool.fetchval(
        "SELECT execution_revision FROM service_order WHERE id = $1::uuid", oid
    )
    return await _exe(b).xong(
        order_id=oid,
        attempt_id=attempt_id,
        expected_execution_revision=int(rev),
        identity=b.bac_si,
        idempotency_key=str(uuid.uuid4()),
    )


async def _sap_den(b: RB, room: str) -> dict[str, Any] | None:
    async with b.pool.acquire() as conn:
        ds = await ntp.sap_den(conn, CLINIC, room)
    return next((k for k in ds if k["visit_id"] == b.visit_id), None)


# ── Sắp đến ──────────────────────────────────────────────────────────────────


async def test_sap_den_ngay_sau_chi_dinh_ke_ca_chua_chot(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1, selection="PENDING")
    k = await _sap_den(bat, bat.sa1)
    assert k is not None
    assert [(c["id"], c["chua_chot"]) for c in k["chi_dinh"]] == [(o1, True)]
    assert k["dang_o_phong"] is None and k["duoc_huong_dan"] is False
    # Phòng không làm được dịch vụ ấy thì không thấy.
    assert await _sap_den(bat, bat.sa2) is None
    # Bàn khám / phòng đọc qua hàng chờ phòng: khối Sắp đến thay khối cũ.
    hang = await BangLuotKham(bat.pool).hang_cho(
        identity=bat.truong_ca, room_id=bat.sa1
    )
    assert hang["nhan_tai_phong"] is True and hang["chua_xep_phong"] == []
    assert any(k["visit_id"] == bat.visit_id for k in hang["sap_den_phong"])


async def test_day_tat_y_nhu_cu(rb: RB) -> None:  # noqa: F811
    o1 = await _cd_o(rb, rb.sa1)
    await _loi(_nhan(rb, rb.sa1), "NHAN_TAI_PHONG_TAT")
    async with rb.pool.acquire() as conn:
        assert await _tu_xep_bat(conn, CLINIC) is True
    hang = await BangLuotKham(rb.pool).hang_cho(identity=rb.truong_ca, room_id=rb.sa1)
    assert hang["nhan_tai_phong"] is False and hang["sap_den_phong"] == []
    assert any(c["id"] == o1 for c in hang["chua_xep_phong"])
    # Chọn phòng ở quầy vẫn XẾP THẬT khi dây tắt.
    await rb.svc.dat_phong_du_kien(order_id=o1, room_id=rb.sa1, identity=rb.le_tan)
    assert (await _o(rb, o1))["routing_status"] == "ASSIGNED"


# ── Luồng chuẩn ──────────────────────────────────────────────────────────────


async def test_nhan_bat_dau_xong_roi_nhan_phong_hai(bat: RB) -> None:
    async with bat.pool.acquire() as conn:
        assert await _tu_xep_bat(conn, CLINIC) is False
    o1 = await _cd_o(bat, bat.sa1)
    o2 = await _cd_o(bat, bat.sa2)

    kq = await _nhan(bat, bat.sa1)
    assert kq["da_nhan"] == [o1] and kq["nhan_cheo"] is False
    assert (await _song(bat, o1))["status"] == "waiting"  # type: ignore[index]
    o = await _o(bat, o1)
    assert (o["routing_status"], o["room_id"]) == ("ASSIGNED", bat.sa1)
    # Phòng hai thấy khách "đang chờ ở phòng một".
    k2 = await _sap_den(bat, bat.sa2)
    assert k2 is not None and k2["dang_o_phong"]["phong_id"] == bat.sa1
    assert k2["dang_o_phong"]["trang_thai"] == "cho"

    lam = await _bat_dau(bat, o1)
    k2 = await _sap_den(bat, bat.sa2)
    assert k2 is not None and k2["dang_o_phong"]["trang_thai"] == "lam"
    await _xong(bat, o1, lam["attempt_id"])
    assert (await _cho(bat, o1))[-1]["status"] == "done"
    k2 = await _sap_den(bat, bat.sa2)
    assert k2 is not None and k2["dang_o_phong"] is None

    kq2 = await _nhan(bat, bat.sa2)
    assert kq2["da_nhan"] == [o2] and kq2["nhan_cheo"] is False
    nhan = [e for oid in (o1, o2) for e in await _sk(bat, oid, "service.routed")]
    assert [e["nguon"] for e in nhan] == ["tai_phong", "tai_phong"]
    assert [e["thu_tu_thuc_te"] for e in nhan] == [1, 2]
    loai = [r["loai_moc"] for r in await _moc(bat)]
    assert loai == ["NHAN", "BAT_DAU", "XONG", "NHAN"]
    xong = next(r for r in await _moc(bat) if r["loai_moc"] == "XONG")
    assert xong["ly_do_nha"] == "XONG" and str(xong["room_id"]) == bat.sa1

    # Ba số của phòng.
    dem = (await BangLuotKham(bat.pool).phong_hom_nay(identity=bat.truong_ca))[
        "tat_ca_phong"
    ]
    so = {p["id"]: p["dem"] for p in dem}
    assert so[bat.sa2]["dang_cho"] == 1 and so[bat.sa2]["dang_lam"] == 0
    assert so[bat.sa1]["dang_cho"] == 0


async def test_nhan_chua_chot_duoc_bat_dau_van_theo_luat_tien(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1, selection="PENDING")
    assert (await _nhan(bat, bat.sa1))["da_nhan"] == [o1]
    with pytest.raises(LuotKhamConflictError) as e:
        await _bat_dau(bat, o1)
    assert e.value.error_code == "SELECTION_NOT_CONFIRMED"


# ── Nhận chéo ────────────────────────────────────────────────────────────────


async def test_nhan_cheo_khi_dang_cho(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1)
    o2 = await _cd_o(bat, bat.sa2)
    await _nhan(bat, bat.sa1)
    loi = await _loi(_nhan(bat, bat.sa2), "KHACH_O_PHONG_KHAC")
    assert loi.chi_tiet["trang_thai"] == "cho"

    kq = await _nhan(bat, bat.sa2, xac_nhan=True)
    assert kq["da_nhan"] == [o2] and kq["nhan_cheo"] is True
    # Phòng một: rời hàng, chỉ định về Sắp đến.
    assert await _song(bat, o1) is None
    assert (await _o(bat, o1))["routing_status"] == "UNASSIGNED"
    k1 = await _sap_den(bat, bat.sa1)
    assert k1 is not None and k1["dang_o_phong"]["phong_id"] == bat.sa2
    [nha] = await _sk(bat, o1, "service.room_released")
    assert (nha["ly_do"], nha["trang_thai_truoc"]) == ("NHAN_CHEO", "cho")
    assert nha["sang_room_id"] == bat.sa2
    [nhan2] = await _sk(bat, o2, "service.routed")
    assert nhan2["nhan_cheo_tu_room_id"] == bat.sa1


async def test_nhan_cheo_khi_dang_lam_giu_lan_lam_phong_cu(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1)
    o2 = await _cd_o(bat, bat.sa2)
    await _nhan(bat, bat.sa1)
    lam = await _bat_dau(bat, o1)
    loi = await _loi(_nhan(bat, bat.sa2), "KHACH_O_PHONG_KHAC")
    assert loi.chi_tiet["trang_thai"] == "lam"

    await _nhan(bat, bat.sa2, xac_nhan=True)
    # Lần làm của phòng một GIỮ mở, chỉ định vẫn của phòng một.
    o = await bat.pool.fetchrow(
        "SELECT execution_status, room_id::text AS room_id FROM service_order"
        " WHERE id = $1::uuid",
        o1,
    )
    assert o is not None and (o["execution_status"], o["room_id"]) == (
        "IN_PROGRESS",
        bat.sa1,
    )
    st = await bat.pool.fetchval(
        "SELECT status FROM service_execution_attempt WHERE id = $1::uuid",
        lam["attempt_id"],
    )
    assert st == "IN_PROGRESS"
    assert (await _song(bat, o2))["status"] == "waiting"  # type: ignore[index]
    [nha] = await _sk(bat, o1, "service.room_released")
    assert (nha["trang_thai_truoc"], nha["attempt_id"]) == ("lam", lam["attempt_id"])
    # Thẻ ở phòng một: vẫn "đang làm", nhãn đỏ khách đã sang phòng hai.
    hang = await BangLuotKham(bat.pool).hang_cho(
        identity=bat.truong_ca, room_id=bat.sa1
    )
    the = next(d for d in hang["hang_cho"] if d["ref_id"] == o1)
    assert the["trang_thai"] == "serving" and the["da_sang_phong"]["phong"]
    # Phòng một bấm Xong muộn: chỗ chờ thành "đã xong" với giờ bấm riêng.
    await _xong(bat, o1, lam["attempt_id"])
    assert (await _cho(bat, o1))[-1]["status"] == "done"
    # Sổ: người bắt đầu ở phòng một + mốc rời + nhận ở phòng hai, đủ.
    moc = await _moc(bat)
    loai = [(r["loai_moc"], r["ly_do_nha"]) for r in moc]
    assert loai == [
        ("NHAN", None),
        ("BAT_DAU", None),
        ("NHA", "NHAN_CHEO"),
        ("NHAN", None),
        ("XONG", "XONG"),
    ]
    assert str(moc[1]["nguoi_id"]) == bat.bac_si.staff_id


async def test_bat_dau_giai_phong_khi_day_bat_khong_dung_phong_kia(bat: RB) -> None:
    """Chỉ định xếp sẵn ở phòng hai từ trước khi bật dây: Bắt đầu ở phòng hai
    khi khách đang làm ở phòng một = nhận chéo, lần làm phòng một giữ mở."""
    o1 = await _cd_o(bat, bat.sa1)
    await _nhan(bat, bat.sa1)
    lam = await _bat_dau(bat, o1)
    o2 = await _cd_o(
        bat, bat.sa2, routing="ASSIGNED", room_id=bat.sa2, routing_revision=1
    )
    await bat.pool.execute(
        "INSERT INTO queue_entry (clinic_id, visit_id, lane, room_id, reason,"
        " ref_id, status) VALUES ($1::uuid, $2::uuid, 'ROOM', $3::uuid, 'SERVICE',"
        " $4::uuid, 'blocked')",
        CLINIC,
        bat.visit_id,
        bat.sa2,
        o2,
    )
    await _loi(_bat_dau(bat, o2), "PATIENT_BUSY")
    await _bat_dau(bat, o2, giai_phong=True)
    st = await bat.pool.fetchval(
        "SELECT status FROM service_execution_attempt WHERE id = $1::uuid",
        lam["attempt_id"],
    )
    assert st == "IN_PROGRESS"
    [nha] = await _sk(bat, o1, "service.room_released")
    assert nha["ly_do"] == "NHAN_CHEO" and nha["sang_room_id"] == bat.sa2


async def test_hai_nguoi_nhan_cung_luc_chi_mot_phong_giu(bat: RB) -> None:
    await _cd_o(bat, bat.sa1)
    await _cd_o(bat, bat.sa2)
    kq = await asyncio.gather(
        _nhan(bat, bat.sa1), _nhan(bat, bat.sa2), return_exceptions=True
    )
    ok = [k for k in kq if isinstance(k, dict)]
    loi = [k for k in kq if isinstance(k, LuotKhamConflictError)]
    assert len(ok) == 1 and len(loi) == 1
    assert loi[0].error_code == "KHACH_O_PHONG_KHAC"
    phong = await bat.pool.fetch(
        "SELECT DISTINCT room_id FROM queue_entry WHERE visit_id = $1::uuid"
        " AND reason = 'SERVICE' AND status NOT IN ('done', 'left', 'cancelled')",
        bat.visit_id,
    )
    assert len(phong) == 1


# ── Hoàn tác Nhận · Nhả · hoàn tác Nhả ───────────────────────────────────────


async def test_hoan_tac_nhan_ve_sap_den_khong_de_viec(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1)
    await _nhan(bat, bat.sa1)
    svc = ntp.NhanTaiPhongService(bat.pool)
    kq = await svc.hoan_tac_nhan(
        visit_id=bat.visit_id, room_id=bat.sa1, identity=bat.truong_ca
    )
    assert kq["ve_sap_den"] == [o1]
    assert (await _o(bat, o1))["routing_status"] == "UNASSIGNED"
    assert await _song(bat, o1) is None
    assert await _sap_den(bat, bat.sa1) is not None
    viec = await bat.pool.fetchval(
        "SELECT count(*) FROM work_item WHERE visit_id = $1::uuid"
        " AND node_code = 'OPS-ROUTING-REASSIGN'",
        bat.visit_id,
    )
    assert viec == 0
    [routed] = await _sk(bat, o1, "service.routed")
    [ht] = await _sk(bat, o1, "service.room_receive_undone")
    assert ht["hoan_tac_event_id"] == routed["event_id"]
    # Bấm hai lần = already.
    lai = await svc.hoan_tac_nhan(
        visit_id=bat.visit_id, room_id=bat.sa1, identity=bat.truong_ca
    )
    assert lai["already"] is True
    nhan = next(r for r in await _moc(bat) if r["loai_moc"] == "NHAN")
    assert nhan["bi_hoan_tac"] is True and nhan["hoan_tac_luc"] is not None


async def test_nha_dieu_phoi_huong_dan_moi_roi_hoan_tac(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1, bat.sa2)
    await _nhan(bat, bat.sa1)
    vao_hang = (await _song(bat, o1))["eligible_at"]  # type: ignore[index]
    svc = ntp.NhanTaiPhongService(bat.pool)
    await svc.nha(
        visit_id=bat.visit_id,
        room_id=bat.sa1,
        identity=bat.truong_ca,
        huong_dan_room_id=bat.sa2,
    )
    o = await bat.pool.fetchrow(
        "SELECT routing_status, phong_du_kien_id::text AS hd FROM service_order"
        " WHERE id = $1::uuid",
        o1,
    )
    assert o is not None and (o["routing_status"], o["hd"]) == ("UNASSIGNED", bat.sa2)
    [nha] = await _sk(bat, o1, "service.room_released")
    assert (nha["ly_do"], nha["trang_thai_truoc"]) == ("DIEU_PHOI", "cho")
    k2 = await _sap_den(bat, bat.sa2)
    assert k2 is not None and k2["duoc_huong_dan"] is True

    await svc.hoan_tac_nha(
        visit_id=bat.visit_id, room_id=bat.sa1, identity=bat.truong_ca
    )
    song = await _song(bat, o1)
    assert song is not None and song["room_id"] == bat.sa1
    assert song["eligible_at"] == vao_hang  # giữ giờ vào hàng cũ
    [ht] = await _sk(bat, o1, "service.room_release_undone")
    assert ht["hoan_tac_event_id"] == nha["event_id"]
    lai = await svc.hoan_tac_nha(
        visit_id=bat.visit_id, room_id=bat.sa1, identity=bat.truong_ca
    )
    assert lai["already"] is True
    moc = {r["loai_moc"]: r for r in await _moc(bat)}
    assert moc["NHA"]["bi_hoan_tac"] is True
    assert moc["NHAN"]["bi_hoan_tac"] is False


async def test_nha_khi_dang_lam_bi_tu_choi(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1)
    await _nhan(bat, bat.sa1)
    await _bat_dau(bat, o1)
    await _loi(
        ntp.NhanTaiPhongService(bat.pool).nha(
            visit_id=bat.visit_id, room_id=bat.sa1, identity=bat.truong_ca
        ),
        "KHACH_DANG_LAM",
    )


# ── Hướng dẫn phòng = nháp ───────────────────────────────────────────────────


async def test_huong_dan_doi_hai_lan_hai_su_kien_khong_xep_that(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1, bat.sa2)
    for p in (bat.sa2, bat.sa1):
        kq = await bat.svc.dat_phong_du_kien(
            order_id=o1, room_id=p, identity=bat.le_tan
        )
        assert kq["huong_dan"] is True
    assert (await _o(bat, o1))["routing_status"] == "UNASSIGNED"
    hd = await _sk(bat, o1, "service.room_guided")
    assert [(e["tu_room_id"], e["room_id"]) for e in hd] == [
        (None, bat.sa2),
        (bat.sa2, bat.sa1),
    ]
    # Lệnh xếp phòng thường (quầy / trưởng ca) cũng chỉ là hướng dẫn.
    kq = await bat.svc.assign(
        order_id=o1,
        room_id=bat.sa2,
        expected_routing_revision=0,
        reason_code="INITIAL_ASSIGNMENT",
        identity=bat.truong_ca,
        idempotency_key=f"t-{uuid.uuid4().hex}",
        nguon="quay_thu",
    )
    assert kq["huong_dan"] is True and kq["routing_status"] == "UNASSIGNED"


async def test_doi_chieu_huong_dan_voi_thuc_te(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1, bat.sa2)
    await bat.svc.dat_phong_du_kien(order_id=o1, room_id=bat.sa2, identity=bat.le_tan)
    k2 = await _sap_den(bat, bat.sa2)
    assert k2 is not None and k2["duoc_huong_dan"] is True
    await _nhan(bat, bat.sa1)
    [e] = await _sk(bat, o1, "service.routed")
    assert (e["huong_dan_room_id"], e["dung_huong_dan"]) == (bat.sa2, False)
    assert (e["thu_tu_huong_dan"], e["thu_tu_thuc_te"]) == (None, 1)
    nhan = next(r for r in await _moc(bat) if r["loai_moc"] == "NHAN")
    assert str(nhan["huong_dan_phong_id"]) == bat.sa2
    assert nhan["dung_huong_dan"] is False


async def test_truong_ca_doi_phong_khi_day_bat_la_nha_va_huong_dan(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1, bat.sa2)
    await _nhan(bat, bat.sa1)
    rev = (await _o(bat, o1))["routing_revision"]
    kq = await bat.svc.assign(
        order_id=o1,
        room_id=bat.sa2,
        expected_routing_revision=int(rev),
        reason_code="MANUAL_CORRECTION",
        identity=bat.truong_ca,
        idempotency_key=f"t-{uuid.uuid4().hex}",
        nguon="truong_ca",
    )
    assert kq["changed"] is True and kq["routing_status"] == "UNASSIGNED"
    assert kq["phong_du_kien_id"] == bat.sa2
    [nha] = await _sk(bat, o1, "service.room_released")
    assert nha["ly_do"] == "DIEU_PHOI"


# ── Quầy bỏ dịch vụ → rời hàng ───────────────────────────────────────────────


async def test_quay_bo_dich_vu_da_nhan_thi_roi_hang(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1, selection="PENDING")
    await _nhan(bat, bat.sa1)
    async with bat.pool.acquire() as conn, conn.transaction():
        await khoa_luot(conn, CLINIC, bat.visit_id)
        rev = await conn.fetchval(
            "SELECT coalesce(max(revision), 0) FROM service_selection_state"
            " WHERE visit_id = $1::uuid",
            bat.visit_id,
        )
        await ap_lua_chon(
            conn,
            bat.le_tan,
            SelectionInput(bat.visit_id, (o1,), (), int(rev)),
        )
    assert await _song(bat, o1) is None
    o = await _o(bat, o1)
    assert o["routing_status"] == "UNASSIGNED"
    [nha] = await _sk(bat, o1, "service.room_released")
    assert nha["ly_do"] == "BO_DICH_VU"
    assert await _sap_den(bat, bat.sa1) is None


# ── Khám lần 2 giữ mốc lần 1 ─────────────────────────────────────────────────


async def test_kham_lai_giu_moc_lan_mot(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    moc1 = await kb.pool.fetchval(
        "SELECT serving_at FROM queue_entry WHERE ref_id = $1::uuid"
        " AND status = 'serving'",
        phien,
    )
    for lan in (2, 3):
        # Khách đi làm dịch vụ rồi quay về hàng bác sĩ.
        await kb.pool.execute(
            "UPDATE queue_entry SET status = 'waiting', eligible_at = now()"
            " WHERE ref_id = $1::uuid AND status = 'serving'",
            phien,
        )
        kq = await kb.svc.start_consultation(consultation_id=phien, identity=kb.bac_si)
        assert kq["already"] is True
        rows = await kb.pool.fetch(
            "SELECT payload FROM domain_event WHERE aggregate_id = $1::uuid"
            " AND event_type = 'consultation.resumed' ORDER BY seq",
            phien,
        )
        p = json.loads(rows[-1]["payload"])
        assert p["lan"] == lan and len(rows) == lan - 1
        if lan == 2:
            assert p["bat_dau_lan_truoc_luc"] == moc1.isoformat()
    # Mốc lần một vẫn đọc được ở sổ.
    assert await kb.pool.fetchval(
        "SELECT count(*) FROM domain_event WHERE aggregate_id = $1::uuid"
        " AND event_type = 'consultation.started'",
        phien,
    )
