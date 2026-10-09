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

from clinicai.api.exceptions import ValidationError
from clinicai.events.consumers.hanh_trinh import _tu_xep_bat
from clinicai.services import nhan_tai_phong as ntp
from clinicai.services.clinic_config_service import ClinicConfigService
from clinicai.services.hoan_tac_service import HoanTacService
from clinicai.services.lenh_kham_core import khoa_luot
from clinicai.services.luot_kham_doc import BangLuotKham
from clinicai.services.luot_kham_service import LuotKhamConflictError
from clinicai.services.quay_thu_service import phong_in_huong_dan
from clinicai.services.service_execution_service import ServiceExecutionService
from clinicai.services.service_routing_service import phong_chuyen_duy_nhat
from clinicai.services.service_selection_service import SelectionInput, ap_lua_chon
from tests.services.test_luot_kham_service_db import (
    CLINIC,
    KichBan,
    _nguoi,
    _vao_kham,
)
from tests.services.test_service_routing_db import (  # noqa: F401
    NODE,
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
    b: RB,
    room: str,
    *ids: str,
    xac_nhan: bool = False,
    visit_id: str | None = None,
) -> dict[str, Any]:
    """Phòng bấm Nhận trên các dòng ``ids`` (không truyền = mọi chỉ định nhận được)."""
    return await ntp.NhanTaiPhongService(b.pool).nhan(
        visit_id=visit_id or b.visit_id,
        room_id=room,
        identity=b.truong_ca,
        chi_dinh_ids=list(ids) if ids else None,
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


async def _o_khach(b: RB, room: str) -> dict[str, dict[str, Any]]:
    """Ô khách ở hàng chờ phòng: chỉ định → trạng thái nhìn từ phòng."""
    async with b.pool.acquire() as conn:
        ds = await ntp.chi_dinh_cua_khach(conn, CLINIC, room, [b.visit_id])
    return {c["id"]: c for c in ds.get(b.visit_id, [])}


async def _dem(b: RB, room: str) -> tuple[int, int]:
    """(đang chờ, đang làm) của phòng — số KHÁCH. "Sắp đến" không so số: DB
    test chung còn chỉ định siêu âm của bài khác mà phòng test làm được."""
    async with b.pool.acquire() as conn:
        d = (await ntp.dem_theo_phong(conn, CLINIC, bat=True)).get(room, {})
    return int(d.get("dang_cho") or 0), int(d.get("dang_lam") or 0)


async def _sao(b: RB, room: str, chuyen: bool = True, node: str = NODE) -> Any:
    """Quản lý đánh / bỏ phòng chuyên ★ (lệnh thật, có nhật ký)."""
    async with b.pool.acquire() as conn:
        ql = await _nguoi(conn, b.loc, "MANAGEMENT")
    return await ClinicConfigService(b.pool).set_room_node_chuyen(
        identity=ql, room_id=room, node_code=node, chuyen=chuyen
    )


async def _huong_dan(b: RB, oid: str, room: str) -> None:
    await b.svc.dat_phong_du_kien(order_id=oid, room_id=room, identity=b.le_tan)


# ── Sắp đến ──────────────────────────────────────────────────────────────────


async def test_sap_den_ngay_sau_chi_dinh_ke_ca_chua_chot(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1, selection="PENDING")
    k = await _sap_den(bat, bat.sa1)
    assert k is not None
    assert [(c["id"], c["chua_chot"]) for c in k["chi_dinh"]] == [(o1, True)]
    assert k["duoc_huong_dan"] is False and k["tinh_so"] is True
    # Phòng không làm được dịch vụ ấy vẫn THẤY khách (mọi khách hôm nay), không
    # có chỉ định nào để nhận, không vào số.
    k2 = await _sap_den(bat, bat.sa2)
    assert k2 is not None and k2["chi_dinh"] == [] and k2["so_nhan_duoc"] == 0
    assert k2["tinh_so"] is False
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

    kq = await _nhan(bat, bat.sa1, o1)
    assert kq["da_nhan"] == [o1] and kq["nhan_cheo"] is False
    assert (await _song(bat, o1))["status"] == "waiting"  # type: ignore[index]
    o = await _o(bat, o1)
    assert (o["routing_status"], o["room_id"]) == ("ASSIGNED", bat.sa1)
    # Phòng hai thấy khách "đang chờ ở phòng một".
    ten1 = await bat.pool.fetchval(
        "SELECT name FROM clinic_room WHERE id = $1::uuid", bat.sa1
    )
    k2 = await _sap_den(bat, bat.sa2)
    assert k2 is not None and k2["dang_o"] == f"đang chờ ở {ten1}"

    lam = await _bat_dau(bat, o1)
    k2 = await _sap_den(bat, bat.sa2)
    assert k2 is not None and k2["dang_o"] == f"đang làm ở {ten1}"
    await _xong(bat, o1, lam["attempt_id"])
    assert (await _cho(bat, o1))[-1]["status"] == "done"
    k2 = await _sap_den(bat, bat.sa2)
    assert k2 is not None and ten1 not in (k2["dang_o"] or "")

    kq2 = await _nhan(bat, bat.sa2, o2)
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
    assert (await _nhan(bat, bat.sa1, o1))["da_nhan"] == [o1]
    with pytest.raises(LuotKhamConflictError) as e:
        await _bat_dau(bat, o1)
    assert e.value.error_code == "SELECTION_NOT_CONFIRMED"


# ── Nhận chéo ────────────────────────────────────────────────────────────────


async def test_nhan_cheo_khi_dang_cho(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1, bat.sa2)
    await _nhan(bat, bat.sa1, o1)
    loi = await _loi(_nhan(bat, bat.sa2, o1), "KHACH_O_PHONG_KHAC")
    assert loi.chi_tiet["trang_thai"] == "cho"

    kq = await _nhan(bat, bat.sa2, o1, xac_nhan=True)
    assert kq["da_nhan"] == [o1] and kq["nhan_cheo"] is True
    song = await _song(bat, o1)
    assert song is not None and song["room_id"] == bat.sa2
    [nha] = await _sk(bat, o1, "service.room_released")
    assert (nha["ly_do"], nha["trang_thai_truoc"]) == ("NHAN_CHEO", "cho")
    assert nha["sang_room_id"] == bat.sa2
    nhan = await _sk(bat, o1, "service.routed")
    assert nhan[-1]["nhan_cheo_tu_room_id"] == bat.sa1


async def test_nhan_chi_dinh_khac_khong_dung_phong_kia(bat: RB) -> None:
    """Nhận theo CHỈ ĐỊNH: phòng hai nhận chỉ định của mình khi khách đang CHỜ
    ở phòng một — không hỏi, không kéo khách khỏi hàng phòng một."""
    o1 = await _cd_o(bat, bat.sa1)
    o2 = await _cd_o(bat, bat.sa2)
    await _nhan(bat, bat.sa1, o1)
    kq = await _nhan(bat, bat.sa2, o2)
    assert kq["da_nhan"] == [o2] and kq["nhan_cheo"] is False
    assert (await _song(bat, o1))["room_id"] == bat.sa1  # type: ignore[index]
    assert await _sk(bat, o1, "service.room_released") == []


async def test_nhan_cheo_khi_dang_lam_giu_lan_lam_phong_cu(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1)
    o2 = await _cd_o(bat, bat.sa2)
    await _nhan(bat, bat.sa1, o1)
    lam = await _bat_dau(bat, o1)
    loi = await _loi(_nhan(bat, bat.sa2, o2), "KHACH_O_PHONG_KHAC")
    assert loi.chi_tiet["trang_thai"] == "lam"

    await _nhan(bat, bat.sa2, o2, xac_nhan=True)
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
    await _nhan(bat, bat.sa1, o1)
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
    o1 = await _cd_o(bat, bat.sa1, bat.sa2)
    kq = await asyncio.gather(
        _nhan(bat, bat.sa1, o1), _nhan(bat, bat.sa2, o1), return_exceptions=True
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


# ── Hoàn tác Nhận ────────────────────────────────────────────────────────────


async def test_hoan_tac_nhan_ve_sap_den_khong_de_viec(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1)
    await _nhan(bat, bat.sa1, o1)
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
    await _nhan(bat, bat.sa1, o1)
    [e] = await _sk(bat, o1, "service.routed")
    assert (e["huong_dan_room_id"], e["dung_huong_dan"]) == (bat.sa2, False)
    assert (e["thu_tu_huong_dan"], e["thu_tu_thuc_te"]) == (None, 1)
    nhan = next(r for r in await _moc(bat) if r["loai_moc"] == "NHAN")
    assert str(nhan["huong_dan_phong_id"]) == bat.sa2
    assert nhan["dung_huong_dan"] is False


async def test_truong_ca_doi_phong_khi_day_bat_chi_ghi_huong_dan(bat: RB) -> None:
    """Bỏ nút Nhả (07/10): trưởng ca "đổi phòng" khách đang chờ = CHỈ ghi hướng
    dẫn; khách vẫn chờ phòng một tới khi phòng hai bấm Nhận (nhận chéo)."""
    o1 = await _cd_o(bat, bat.sa1, bat.sa2)
    await _nhan(bat, bat.sa1, o1)
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
    assert kq["huong_dan"] is True and kq["phong_du_kien_id"] == bat.sa2
    assert (kq["routing_status"], kq["room_id"]) == ("ASSIGNED", bat.sa1)
    assert await _sk(bat, o1, "service.room_released") == []
    # Phòng hai thấy khách (được hướng dẫn tới), chỉ định "đang chờ ở P1".
    k2 = await _sap_den(bat, bat.sa2)
    assert k2 is not None and k2["duoc_huong_dan"] is True
    [c] = k2["chi_dinh"]
    assert (c["trang_thai"], c["nhan_duoc"]) == ("o_phong_khac", True)
    await _loi(_nhan(bat, bat.sa2), "KHACH_O_PHONG_KHAC")
    assert (await _nhan(bat, bat.sa2, xac_nhan=True))["da_nhan"] == [o1]
    [nha] = await _sk(bat, o1, "service.room_released")
    assert nha["ly_do"] == "NHAN_CHEO"


# ── Quầy bỏ dịch vụ → rời hàng ───────────────────────────────────────────────


async def test_quay_bo_dich_vu_da_nhan_thi_roi_hang(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1, selection="PENDING")
    await _nhan(bat, bat.sa1, o1)
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
    k = await _sap_den(bat, bat.sa1)
    assert k is not None and k["chi_dinh"] == [] and k["tinh_so"] is False


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


# ── Phòng chuyên ★ + nhận theo chỉ định (Tuyền chốt 07/10/2026) ──────────────


async def test_ba_chi_dinh_hai_phong_nhu_staging(bat: RB) -> None:
    """Lỗi thật trên staging: Soi CTC + Siêu âm quầy hướng dẫn phòng siêu âm
    (sa1), Monitor → phòng thủ thuật (sa2); thủ thuật làm được cả ba. Thủ thuật
    bấm Nhận trên DÒNG Monitor chỉ lấy Monitor; phòng siêu âm vẫn thấy hai chỉ
    định kèm "đang chờ ở P. thủ thuật", rồi "Nhận cả 2"."""
    soi = await _cd_o(bat, bat.sa1, bat.sa2)
    sa = await _cd_o(bat, bat.sa1, bat.sa2)
    mon = await _cd_o(bat, bat.sa2)
    for oid, p in ((soi, bat.sa1), (sa, bat.sa1), (mon, bat.sa2)):
        await _huong_dan(bat, oid, p)

    k_tt = await _sap_den(bat, bat.sa2)
    assert k_tt is not None
    assert (k_tt["so_chi_dinh"], k_tt["so_nhan_duoc"]) == (3, 3)
    hd = {c["id"]: c["huong_dan_day"] for c in k_tt["chi_dinh"]}
    assert hd == {soi: False, sa: False, mon: True}
    kq = await _nhan(bat, bat.sa2, mon)
    assert kq["da_nhan"] == [mon] and kq["nhan_cheo"] is False
    for oid in (soi, sa):
        assert (await _o(bat, oid))["routing_status"] == "UNASSIGNED"
    [e] = await _sk(bat, mon, "service.routed")
    assert e["dung_huong_dan"] is True

    ten_tt = await bat.pool.fetchval(
        "SELECT name FROM clinic_room WHERE id = $1::uuid", bat.sa2
    )
    k_sa = await _sap_den(bat, bat.sa1)
    assert k_sa is not None and k_sa["dang_o"] == f"đang chờ ở {ten_tt}"
    assert {c["id"]: c["trang_thai"] for c in k_sa["chi_dinh"]} == {
        soi: "sap_den",
        sa: "sap_den",
    }
    # Ô khách ở phòng thủ thuật: MỘT ô, ba chỉ định với trạng thái riêng.
    o_tt = await _o_khach(bat, bat.sa2)
    assert o_tt[mon]["trang_thai"] == "cho"
    assert o_tt[soi]["trang_thai"] == "sap_den"
    assert o_tt[soi]["huong_dan_id"] == bat.sa1 and o_tt[soi]["huong_dan"]
    # Đếm theo KHÁCH: thủ thuật 1 đang chờ (không phải 3); khách không lặp ở
    # Sắp đến của chính phòng đang giữ khách.
    assert await _dem(bat, bat.sa2) == (1, 0)
    assert await _sap_den(bat, bat.sa2) is None

    # Phòng siêu âm "Nhận cả 2" — Monitor ở thủ thuật không bị đụng.
    kq = await _nhan(bat, bat.sa1, soi, sa)
    assert sorted(kq["da_nhan"]) == sorted([soi, sa]) and kq["nhan_cheo"] is False
    assert (await _song(bat, mon))["room_id"] == bat.sa2  # type: ignore[index]
    assert (await _dem(bat, bat.sa1))[0] == 1


async def test_phong_chuyen_chi_la_nhan_va_thu_tu(bat: RB) -> None:
    """★ / hướng dẫn không quyết gì khi Nhận — chỉ gắn nhãn và xếp ô lên trước.
    Nhận trên một dòng = đúng chỉ định ấy; danh sách rỗng bị từ chối."""
    o1 = await _cd_o(bat, bat.sa1, bat.sa2)
    o2 = await _cd_o(bat, bat.sa1, bat.sa2)
    await _sao(bat, bat.sa1)
    k1 = await _sap_den(bat, bat.sa1)
    k2 = await _sap_den(bat, bat.sa2)
    assert k1 is not None and all(c["chuyen"] for c in k1["chi_dinh"])
    assert k2 is not None and not any(c["chuyen"] for c in k2["chi_dinh"])
    # Ô có chỉ định ★ nhận được đứng trước mọi ô khác của phòng.
    async with bat.pool.acquire() as conn:
        ds = await ntp.sap_den(conn, CLINIC, bat.sa1)
    vi_tri = next(i for i, k in enumerate(ds) if k["visit_id"] == bat.visit_id)
    assert all(
        any(
            c["nhan_duoc"] and (c["chuyen"] or c["huong_dan_day"])
            for c in k["chi_dinh"]
        )
        for k in ds[: vi_tri + 1]
    )
    await _loi(
        ntp.NhanTaiPhongService(bat.pool).nhan(
            visit_id=bat.visit_id,
            room_id=bat.sa2,
            identity=bat.truong_ca,
            chi_dinh_ids=[],
        ),
        "CHUA_CHON_CHI_DINH",
    )
    # Phòng KHÔNG chuyên vẫn nhận được từng dòng.
    assert (await _nhan(bat, bat.sa2, o2))["da_nhan"] == [o2]
    assert (await _o(bat, o1))["routing_status"] == "UNASSIGNED"


async def test_sap_den_moi_khach_hom_nay_ke_ca_chua_co_chi_dinh(bat: RB) -> None:
    """Sắp đến = mọi khách check-in hôm nay chưa check-out, ở mọi phòng — khách
    chưa có chỉ định ở phòng: ô không có gì để Nhận, nhãn nơi đang ở thật. Khách
    check-out thì biến mất."""
    for p in (bat.sa1, bat.sa2):
        k = await _sap_den(bat, p)
        assert k is not None
        assert (k["chi_dinh"], k["so_nhan_duoc"], k["tinh_so"]) == ([], 0, False)
        # Nhãn nơi khách đang ở thật, hoặc "chưa có chỉ định ở phòng này".
        assert k["dang_o"]
    await _loi(_nhan(bat, bat.sa1), "KHONG_CON_GI_DE_NHAN")
    await bat.pool.execute(
        "UPDATE visit SET closed_at = now() WHERE visit_id = $1::uuid", bat.visit_id
    )
    assert await _sap_den(bat, bat.sa1) is None
    assert await _sap_den(bat, bat.sa2) is None


async def test_cau_dang_o() -> None:
    assert ntp.cau_dang_o("ROOM", "waiting", "SA1") == "đang chờ ở SA1"
    assert ntp.cau_dang_o("ROOM", "serving", None) == "đang làm ở phòng khác"
    assert ntp.cau_dang_o("DOCTOR", "serving", None) == "đang khám ở bàn khám"
    assert ntp.cau_dang_o("DOCTOR", "waiting", "KB01") == "đang chờ khám"
    assert ntp.cau_dang_o("TU_VAN", "serving", None) == "đang tư vấn"
    assert ntp.cau_dang_o(None, None, None) is None


async def test_nhan_them_roi_hoan_tac_rieng_chi_dinh(bat: RB) -> None:
    o1 = await _cd_o(bat, bat.sa1)
    o2 = await _cd_o(bat, bat.sa1)
    await _nhan(bat, bat.sa1, o1)
    # Khách đã ở phòng → không còn ở Sắp đến; ô khách mời "Nhận thêm" o2.
    assert await _sap_den(bat, bat.sa1) is None
    o = await _o_khach(bat, bat.sa1)
    assert (o[o1]["trang_thai"], o[o2]["trang_thai"]) == ("cho", "sap_den")
    assert o[o2]["nhan_duoc"] is True and o[o1]["nhan_duoc"] is False
    assert await _dem(bat, bat.sa1) == (1, 0)

    assert (await _nhan(bat, bat.sa1, o2))["da_nhan"] == [o2]
    # Bấm lại chỉ định đã ở phòng = already.
    assert (await _nhan(bat, bat.sa1, o2))["already"] is True
    kq = await ntp.NhanTaiPhongService(bat.pool).hoan_tac_nhan(
        visit_id=bat.visit_id,
        room_id=bat.sa1,
        identity=bat.truong_ca,
        chi_dinh_ids=[o2],
    )
    assert kq["ve_sap_den"] == [o2]
    assert (await _song(bat, o1))["room_id"] == bat.sa1  # type: ignore[index]
    assert await _song(bat, o2) is None


async def test_xong_khong_tu_nha_chi_dinh_con_lai_va_hoan_tac_xong(bat: RB) -> None:
    """Chỉ ghi sự kiện thật (07/10): Xong chỉ đóng đúng chỉ định ấy; chỉ định
    đã nhận chưa làm vẫn "chờ ở đây". Hoàn tác Xong về đúng trạng thái trước."""
    o1 = await _cd_o(bat, bat.sa1)
    o2 = await _cd_o(bat, bat.sa1)
    await _nhan(bat, bat.sa1, o1, o2)
    assert (await _dem(bat, bat.sa1))[0] == 1
    lam = await _bat_dau(bat, o1)
    # Một khách một nhóm: đang làm (không đếm thêm ở đang chờ).
    assert await _dem(bat, bat.sa1) == (0, 1)
    await _xong(bat, o1, lam["attempt_id"])
    song = await _song(bat, o2)
    assert song is not None and song["room_id"] == bat.sa1
    assert song["status"] != "serving"
    assert await _sk(bat, o2, "service.room_released") == []
    assert (await _o(bat, o2))["routing_status"] == "ASSIGNED"
    assert await _dem(bat, bat.sa1) == (1, 0)
    o = await _o_khach(bat, bat.sa1)
    assert (o[o1]["trang_thai"], o[o2]["trang_thai"]) == ("xong", "cho")

    await HoanTacService(bat.pool).hoan_tac_xong_dich_vu(
        order_id=o1, identity=bat.bac_si
    )
    o = await _o_khach(bat, bat.sa1)
    assert (o[o1]["trang_thai"], o[o2]["trang_thai"]) == ("lam", "cho")
    assert await _dem(bat, bat.sa1) == (0, 1)


async def test_doi_co_chuyen_co_nhat_ky_va_khong_mat_khi_sua_viec(bat: RB) -> None:
    kq = await _sao(bat, bat.sa1)
    assert kq["chuyen"] is True and "already" not in kq
    assert (await _sao(bat, bat.sa1))["already"] is True
    # Sửa danh sách việc của phòng (giữ node) không xoá dấu ★.
    async with bat.pool.acquire() as conn:
        ql = await _nguoi(conn, bat.loc, "MANAGEMENT")
    await ClinicConfigService(bat.pool).set_room_nodes(
        identity=ql, room_id=bat.sa1, node_codes=[NODE]
    )
    assert await bat.pool.fetchval(
        "SELECT chuyen FROM clinic_room_node WHERE room_id = $1::uuid"
        " AND node_code = $2",
        bat.sa1,
        NODE,
    )
    await _sao(bat, bat.sa1, chuyen=False)
    nk = await bat.pool.fetch(
        "SELECT payload FROM event_log WHERE event_type ="
        " 'clinic_config.room_node_chuyen' AND payload->>'doi_tuong_id' = $1"
        " ORDER BY recorded_at",
        bat.sa1,
    )
    assert [
        (json.loads(r["payload"])["truoc"], json.loads(r["payload"])["chuyen"])
        for r in nk
    ] == [(False, True), (True, False)]
    # Phòng chưa làm chức năng ấy thì không đánh ★ được.
    with pytest.raises(ValidationError):
        await _sao(bat, bat.sa1, node="DICHVU-LAYMAU-MAU")


async def test_goi_y_va_phieu_huong_dan_mot_phong_chuyen() -> None:
    assert phong_chuyen_duy_nhat([{"room_id": "a", "chuyen": True}]) == "a"
    assert (
        phong_chuyen_duy_nhat(
            [{"room_id": "a", "chuyen": True}, {"room_id": "b", "chuyen": True}]
        )
        is None
    )
    assert phong_chuyen_duy_nhat([{"room_id": "a", "chuyen": False}]) is None
    assert phong_in_huong_dan(
        [{"ten": "SA", "chuyen": True}, {"ten": "TT", "chuyen": False}]
    ) == {"phong_chuyen": "SA", "phong_lam_duoc": []}
    assert phong_in_huong_dan([{"ten": "SA"}, {"ten": "TT"}]) == {
        "phong_chuyen": None,
        "phong_lam_duoc": ["SA", "TT"],
    }


async def test_sap_den_hien_ca_khach_dang_o_phong_khac_khong_dem(bat: RB) -> None:
    """Tuyền 07/10: Sắp đến ở MỌI phòng làm được hiện đủ khách — kể cả khách đã
    được phòng khác nhận hết — kèm nhãn nơi ấy, nhưng KHÔNG vào số "sắp đến"
    (đã đếm ở "đang chờ / đang làm" của phòng kia)."""

    async def so_sap_den(room: str) -> int:
        async with bat.pool.acquire() as conn:
            d = (await ntp.dem_theo_phong(conn, CLINIC, bat=True)).get(room, {})
        return int(d.get("sap_den") or 0)

    o1 = await _cd_o(bat, bat.sa1, bat.sa2)
    truoc = await so_sap_den(bat.sa1)
    await _nhan(bat, bat.sa2, o1)

    k1 = await _sap_den(bat, bat.sa1)
    assert k1 is not None and k1["tinh_so"] is False and k1["so_nhan_duoc"] == 1
    [c] = k1["chi_dinh"]
    assert (c["trang_thai"], c["o_trang_thai"]) == ("o_phong_khac", "cho")
    assert c["phong"] and c["nhan_duoc"] is True
    assert k1["dang_o"] == f"đang chờ ở {c['phong']}"
    assert await so_sap_den(bat.sa1) == truoc - 1

    # Đang LÀM ở phòng kia: vẫn hiện, nhãn "đang làm", không nhận chéo được.
    await _bat_dau(bat, o1)
    k1 = await _sap_den(bat, bat.sa1)
    assert k1 is not None and k1["so_nhan_duoc"] == 0
    assert k1["chi_dinh"][0]["o_trang_thai"] == "lam"
    assert await so_sap_den(bat.sa1) == truoc - 1
