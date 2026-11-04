"""Chọn bác sĩ trong phòng nhiều bác sĩ (Tuyền chốt 30/09/2026) — Postgres thật.

Phòng có ≥2 bác sĩ trực hôm nay (mỗi vị trí BAC_SI một làn, `vi_tri_lam_viec.lan`)
→ quầy chọn phòng xong chọn tiếp bác sĩ; một bác sĩ → tự gán; chọn bác sĩ không
trực → từ chối; đổi phòng → trigger xoá lựa chọn; hàng chờ lọc theo làn.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55547/postgres \\
        .venv/bin/pytest -m db src/tests/services/test_chon_bac_si_trong_phong_db.py
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
import pytest_asyncio

from clinicai.api.identity import StaffIdentity
from clinicai.services.hanh_trinh_khach_service import HanhTrinhKhachService
from clinicai.services.lan_bac_si import lua_chon_bac_si
from clinicai.services.lich_su_phong import lich_su_phong_cua_luot
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.quay_thu_service import PhongQuay
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi
from tests.services.test_nhan_tai_phong_db import _cd_o, _nhan, bat  # noqa: F401
from tests.services.test_service_routing_db import (  # noqa: F401
    RB,
    _assign,
    _cd,
    _loi,
    rb,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _quyen_theo_nhom_mau(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.quyen_gia import dich_vu_theo_nhom_mau

    dich_vu_theo_nhom_mau(monkeypatch)


@dataclass
class Lan:
    """Phòng SA1 của `rb`: ô BS1 (BS A) + ô ĐD1 hỗ trợ BS1; ô BS2 (BS B) + ô ĐD2
    hỗ trợ BS2, ĐD 2 đứng ô ĐD2."""

    rb: RB
    bs_a: StaffIdentity
    bs_b: StaffIdentity
    bs_c: StaffIdentity
    dd_2: StaffIdentity
    vt: dict[str, str]


async def _vi_tri(
    b: RB,
    room_id: str,
    nhom: str,
    lan: int | None,
    sort: int,
    ho_tro: str | None = None,
) -> str:
    ma = f"VT-{b.duoi}-{uuid.uuid4().hex[:6]}"
    await b.pool.execute(
        "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, nhom_nghe, room_id,"
        " lan, sort, ho_tro_code) VALUES ($1::uuid, $2, $2, $3, $4::uuid, $5, $6, $7)",
        CLINIC,
        ma,
        nhom,
        room_id,
        lan,
        sort,
        ho_tro,
    )
    return ma


async def _truc(b: RB, ma: str, ai: StaffIdentity, ca: str = "FULL") -> None:
    await b.pool.execute(
        "INSERT INTO work_roster (clinic_id, week_start, work_date, shift, station,"
        " staff_id, staff_name, status)"
        " SELECT $1::uuid, d - (extract(isodow FROM d)::int - 1), d, $4, $2,"
        " $3::uuid, 'Test', 'APPROVED'"
        " FROM (SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS d) x",
        CLINIC,
        ma,
        ai.staff_id,
        ca,
    )


@pytest_asyncio.fixture
async def lan(rb: RB) -> Lan:  # noqa: F811
    b = rb
    async with b.pool.acquire() as conn:
        bs_a = await _nguoi(conn, b.loc, "ULTRASOUND_DOCTOR")
        bs_b = await _nguoi(conn, b.loc, "ULTRASOUND_DOCTOR")
        bs_c = await _nguoi(conn, b.loc, "ULTRASOUND_DOCTOR")
        dd_2 = await _nguoi(conn, b.loc, "NURSE_ULTRASOUND")
    vt: dict[str, str] = {}
    vt["bs1"] = await _vi_tri(b, b.sa1, "BAC_SI", 1, 1)
    vt["dd1"] = await _vi_tri(b, b.sa1, "DIEU_DUONG", 1, 2, vt["bs1"])
    vt["bs2"] = await _vi_tri(b, b.sa1, "BAC_SI", 2, 3)
    vt["dd2"] = await _vi_tri(b, b.sa1, "DIEU_DUONG", 2, 4, vt["bs2"])
    # SA2: một bác sĩ → tự gán.
    vt["bs_sa2"] = await _vi_tri(b, b.sa2, "BAC_SI", None, 1)
    await _truc(b, vt["bs1"], bs_a)
    await _truc(b, vt["bs2"], bs_b)
    await _truc(b, vt["dd2"], dd_2)
    await _truc(b, vt["bs_sa2"], bs_c)
    return Lan(rb=b, bs_a=bs_a, bs_b=bs_b, bs_c=bs_c, dd_2=dd_2, vt=vt)


async def _bs(b: RB, oid: str) -> Any:
    return await b.pool.fetchrow(
        "SELECT bac_si_lam_id::text AS id, lan_lam, bac_si_lam_boi::text AS boi,"
        " room_id::text AS room_id, routing_revision"
        " FROM service_order WHERE id = $1::uuid",
        oid,
    )


async def _su_kien_bs(b: RB, oid: str) -> list[dict[str, Any]]:
    import json

    rows = await b.pool.fetch(
        "SELECT payload, actor_staff_id::text AS ai FROM domain_event"
        " WHERE aggregate_id = $1::uuid AND event_type = 'service.doctor_chosen'"
        " ORDER BY seq",
        oid,
    )
    ra = []
    for r in rows:
        p = r["payload"]
        ra.append({**(json.loads(p) if isinstance(p, str) else p), "_ai": r["ai"]})
    return ra


async def test_goi_y_phong_hai_bac_si_tra_hai_lua_chon(lan: Lan) -> None:
    b = lan.rb
    oid = await _cd(b)
    g = await b.svc.recommend(order_id=oid, identity=b.truong_ca)
    theo = {c["room_id"]: c for c in g["candidates"]}
    ds = theo[b.sa1]["bac_si"]
    assert [(x["staff_id"], x["lan"]) for x in ds] == [
        (lan.bs_a.staff_id, 1),
        (lan.bs_b.staff_id, 2),
    ]
    assert all(x["ten"].startswith("BS ") and x["dang_cho"] == 0 for x in ds)
    # Một bác sĩ → không hỏi (không có ô chọn).
    assert theo[b.sa2]["bac_si"] == []
    # Ô phòng ở quầy thu cùng danh sách.
    async with b.pool.acquire() as conn:
        pq = PhongQuay(conn, CLINIC)
        phong = {p["id"]: p for p in await pq.cua("DICHVU-SIEUAM", b.visit_id)}
    assert [x["staff_id"] for x in phong[b.sa1]["bac_si"]] == [
        lan.bs_a.staff_id,
        lan.bs_b.staff_id,
    ]
    assert phong[b.sa2]["bac_si"] == []


async def test_chon_dung_bac_si_luu_va_phat_su_kien(lan: Lan) -> None:
    b = lan.rb
    oid = await _cd(b)
    kq = await b.svc.assign(
        order_id=oid,
        room_id=b.sa1,
        expected_routing_revision=0,
        reason_code="INITIAL_ASSIGNMENT",
        identity=b.le_tan,
        idempotency_key=f"bs-{uuid.uuid4().hex}",
        nguon="quay_thu",
        bac_si_lam_id=lan.bs_b.staff_id,
    )
    assert kq["room_id"] == b.sa1 and kq["bac_si_lam_id"] == lan.bs_b.staff_id
    o = await _bs(b, oid)
    assert (o["id"], o["lan_lam"], o["boi"]) == (
        lan.bs_b.staff_id,
        2,
        b.le_tan.staff_id,
    )
    [ev] = await _su_kien_bs(b, oid)
    assert ev["bac_si_id"] == lan.bs_b.staff_id and ev["lan"] == 2
    assert ev["nguon"] == "quay_thu" and ev["_ai"] == b.le_tan.staff_id

    # Cùng phòng, đổi sang BS A — không đổi phòng / revision, có sự kiện.
    kq2 = await b.svc.assign(
        order_id=oid,
        room_id=b.sa1,
        expected_routing_revision=int(o["routing_revision"]),
        reason_code="MANUAL_CORRECTION",
        identity=b.le_tan,
        idempotency_key=f"bs-{uuid.uuid4().hex}",
        nguon="quay_thu",
        bac_si_lam_id=lan.bs_a.staff_id,
    )
    assert kq2["changed"] and kq2["routing_revision"] == o["routing_revision"]
    assert (await _bs(b, oid))["lan_lam"] == 1
    evs = await _su_kien_bs(b, oid)
    assert evs[-1]["tu_bac_si_id"] == lan.bs_b.staff_id

    # Lịch sử trên thẻ Hành trình khách nói ra.
    async with b.pool.acquire() as conn:
        ls = await lich_su_phong_cua_luot(conn, clinic_id=CLINIC, visit_id=b.visit_id)
    cau = [d["cau"] for d in ls[oid] if d["loai"] == "service.doctor_chosen"]
    assert cau[0].startswith("Quầy thu chọn BS ")
    assert "đổi bác sĩ" in cau[1]

    # Bỏ chọn (null) → "bác sĩ nào rảnh cũng được".
    await b.svc.assign(
        order_id=oid,
        room_id=b.sa1,
        expected_routing_revision=int(o["routing_revision"]),
        reason_code="MANUAL_CORRECTION",
        identity=b.le_tan,
        idempotency_key=f"bs-{uuid.uuid4().hex}",
        nguon="quay_thu",
        bac_si_lam_id=None,
    )
    assert (await _bs(b, oid))["id"] is None


async def test_chon_bac_si_khong_truc_bi_tu_choi(lan: Lan) -> None:
    b = lan.rb
    oid = await _cd(b)
    # BS C trực phòng SA2, không trực SA1.
    loi = await _loi(
        b.svc.assign(
            order_id=oid,
            room_id=b.sa1,
            expected_routing_revision=0,
            reason_code="INITIAL_ASSIGNMENT",
            identity=b.le_tan,
            idempotency_key=f"bs-{uuid.uuid4().hex}",
            nguon="quay_thu",
            bac_si_lam_id=lan.bs_c.staff_id,
        ),
        "DOCTOR_NOT_ON_DUTY",
    )
    assert "không trực ở" in str(loi) and "chọn một trong" in str(loi)
    # Cả lệnh huỷ — phòng cũng không xếp.
    o = await _bs(b, oid)
    assert o["room_id"] is None and o["id"] is None


async def test_doi_phong_xoa_lua_chon_bac_si(lan: Lan) -> None:
    b = lan.rb
    oid = await _cd(b)
    await b.svc.assign(
        order_id=oid,
        room_id=b.sa1,
        expected_routing_revision=0,
        reason_code="INITIAL_ASSIGNMENT",
        identity=b.le_tan,
        idempotency_key=f"bs-{uuid.uuid4().hex}",
        nguon="quay_thu",
        bac_si_lam_id=lan.bs_a.staff_id,
    )
    o = await _bs(b, oid)
    # Đổi sang SA2 (một bác sĩ) → lựa chọn cũ bị xoá, SA2 tự gán BS C.
    await _assign(b, oid, b.sa2, int(o["routing_revision"]), reason="LOAD_BALANCE")
    o2 = await _bs(b, oid)
    assert o2["room_id"] == b.sa2 and o2["id"] == lan.bs_c.staff_id
    assert o2["lan_lam"] is None
    # Trigger là bất biến ở Postgres: đổi phòng bằng câu UPDATE tay cũng xoá.
    await b.pool.execute(
        "UPDATE service_order SET room_id = $2::uuid WHERE id = $1::uuid",
        oid,
        b.sa1,
    )
    assert (await _bs(b, oid))["id"] is None


async def test_mot_bac_si_tu_gan_khi_xep(lan: Lan) -> None:
    b = lan.rb
    oid = await _cd(b)
    kq = await _assign(b, oid, b.sa2, 0)
    assert kq["bac_si_lam_id"] == lan.bs_c.staff_id
    [ev] = await _su_kien_bs(b, oid)
    assert ev["tu_dong"] is True and ev["nguon"] == "tu_dong"
    # Phòng hai bác sĩ mà không ai chọn → để trống (không đoán).
    oid2 = await _cd(b)
    kq2 = await _assign(b, oid2, b.sa1, 0)
    assert "bac_si_lam_id" not in kq2
    assert (await _bs(b, oid2))["id"] is None


async def test_phong_hai_bac_si_tu_gan_bac_si_cung_lan_nguoi_bam(lan: Lan) -> None:
    """Tuyền 27/10: "điều dưỡng 1 theo bác sĩ 1 cùng phòng — tự phân luôn, không
    bắt người dùng chọn". Người bấm đứng ĐD làn 2 → BS làn 2; người không đứng
    làn nào → vẫn để trống như cũ."""
    b = lan.rb
    await _truc(b, lan.vt["dd2"], b.truong_ca)
    oid = await _cd(b)
    kq = await _assign(b, oid, b.sa1, 0, who=b.truong_ca)
    assert kq["bac_si_lam_id"] == lan.bs_b.staff_id
    o = await _bs(b, oid)
    assert (o["id"], o["lan_lam"]) == (lan.bs_b.staff_id, 2)
    [ev] = await _su_kien_bs(b, oid)
    assert ev["tu_dong"] is True and ev["theo_lan"] is True and ev["lan"] == 2
    async with b.pool.acquire() as conn:
        ls = await lich_su_phong_cua_luot(conn, clinic_id=CLINIC, visit_id=b.visit_id)
    [cau] = [d["cau"] for d in ls[oid] if d["loai"] == "service.doctor_chosen"]
    assert cau.endswith("theo lịch làm việc của người bấm")

    # Lễ tân không đứng làn nào của phòng → không đoán.
    oid2 = await _cd(b)
    kq2 = await _assign(b, oid2, b.sa1, 0, who=b.le_tan)
    assert "bac_si_lam_id" not in kq2
    assert (await _bs(b, oid2))["id"] is None


async def test_nhan_tai_phong_dieu_duong_lan_2_tu_gan_bac_si_lan_2(
    lan: Lan,
    bat: RB,  # noqa: F811
) -> None:
    """Đường bấm thật: màn phòng để sẵn BS làn của người xem ở ô chọn; bấm
    Nhận không kèm bác sĩ thì máy chủ gán đúng BS ấy."""
    b = lan.rb
    await _truc(b, lan.vt["dd2"], b.truong_ca)
    oid = await _cd_o(b, b.sa1)
    hc = await LuotKhamService(b.pool).hang_cho(identity=b.truong_ca, room_id=b.sa1)
    assert hc["bac_si_phong"], "phòng hai bác sĩ phải có ô chọn"
    assert hc["bac_si_mac_dinh"] == lan.bs_b.staff_id
    # Người không đứng làn nào: ô chọn để trống như cũ.
    hc2 = await LuotKhamService(b.pool).hang_cho(identity=b.le_tan, room_id=b.sa1)
    assert hc2["bac_si_mac_dinh"] is None

    await _nhan(b, b.sa1, oid)
    o = await _bs(b, oid)
    assert (o["id"], o["lan_lam"]) == (lan.bs_b.staff_id, 2)


async def test_phong_du_kien_giu_bac_si_khi_h4_xep_dung_phong(lan: Lan) -> None:
    b = lan.rb
    oid = await _cd(b, selection="PENDING")
    kq = await b.svc.dat_phong_du_kien(
        order_id=oid,
        room_id=b.sa1,
        identity=b.le_tan,
        bac_si_lam_id=lan.bs_b.staff_id,
    )
    assert kq["bac_si_lam_id"] == lan.bs_b.staff_id
    [ev] = await _su_kien_bs(b, oid)
    assert ev["du_kien"] is True
    await b.pool.execute(
        "UPDATE service_order SET selection_status = 'SELECTED' WHERE id = $1::uuid",
        oid,
    )
    async with b.pool.acquire() as conn, conn.transaction():
        xep = await b.svc.tu_xep_da_thu(
            conn,
            clinic_id=CLINIC,
            visit_id=b.visit_id,
            staff_id=b.truong_ca.staff_id,
            causation_id=b.visit_id,
        )
    assert oid in xep
    o = await _bs(b, oid)
    assert (o["room_id"], o["id"]) == (b.sa1, lan.bs_b.staff_id)


async def test_hang_cho_phong_loc_theo_lan_va_hien_bac_si(lan: Lan) -> None:
    b = lan.rb
    cua_b = await _cd(b)
    cua_a = await _cd(b)
    chua = await _cd(b)
    for oid, bs in ((cua_b, lan.bs_b), (cua_a, lan.bs_a), (chua, None)):
        await b.svc.assign(
            order_id=oid,
            room_id=b.sa1,
            expected_routing_revision=0,
            reason_code="INITIAL_ASSIGNMENT",
            identity=b.truong_ca,
            idempotency_key=f"bs-{uuid.uuid4().hex}",
            bac_si_lam_id=bs.staff_id if bs else None,
        )
    # Trưởng ca được xếp đứng ô ĐD2 (hỗ trợ ô BS2) → khách của tôi = của BS B.
    await _truc(b, lan.vt["dd2"], b.truong_ca)
    hc = await LuotKhamService(b.pool).hang_cho(identity=b.truong_ca, room_id=b.sa1)
    assert hc["lan_cua_toi"]["co"]
    assert hc["lan_cua_toi"]["bac_si_ids"] == [lan.bs_b.staff_id]
    dong = {d["ref_id"]: d for d in hc["hang_cho"] if d["ref_id"]}
    assert dong[cua_b]["lan_toi"] and dong[cua_b]["bac_si_lam"].startswith("BS ")
    assert not dong[cua_a]["lan_toi"]
    # Chưa chọn bác sĩ: thuộc mọi làn (ai trong phòng cũng nhận).
    assert dong[chua]["lan_toi"] and dong[chua]["bac_si_lam"] is None
    # Người không đứng làn nào: không lọc.
    hc2 = await LuotKhamService(b.pool).hang_cho(identity=b.le_tan, room_id=b.sa1)
    assert hc2["lan_cua_toi"]["co"] is False
    # Số khách đang chờ của từng bác sĩ (người thật, lượt hôm nay); khách đang
    # được xếp thì không đếm chính mình.
    async with b.pool.acquire() as conn:
        dem = (await lua_chon_bac_si(conn, CLINIC, [b.sa1]))[b.sa1]
        tru = (await lua_chon_bac_si(conn, CLINIC, [b.sa1], tru_luot=b.visit_id))[b.sa1]
    assert {x["staff_id"]: x["dang_cho"] for x in dem} == {
        lan.bs_a.staff_id: 1,
        lan.bs_b.staff_id: 1,
    }
    assert all(x["dang_cho"] == 0 for x in tru)


async def test_hanh_trinh_va_phieu_ghi_bac_si(lan: Lan) -> None:
    b = lan.rb
    oid = await _cd(b)
    await b.svc.assign(
        order_id=oid,
        room_id=b.sa1,
        expected_routing_revision=0,
        reason_code="INITIAL_ASSIGNMENT",
        identity=b.truong_ca,
        idempotency_key=f"bs-{uuid.uuid4().hex}",
        bac_si_lam_id=lan.bs_a.staff_id,
    )
    ten_phong = await b.pool.fetchval(
        "SELECT name FROM clinic_room WHERE id = $1::uuid", b.sa1
    )
    kq = await HanhTrinhKhachService(b.pool).mot_luot(
        identity=b.truong_ca, visit_id=b.visit_id
    )
    chu = str(kq)
    assert f"{ten_phong} · BS " in chu
    from clinicai.services.quay_thu_service import QuayThuService

    ph = await QuayThuService(b.pool).phieu(
        identity=b.truong_ca, id_=b.visit_id, loai="huong_dan"
    )
    [d] = [d for d in ph["dong"] if d.get("order_id") == oid]
    assert d["phong"]["ten"] == ten_phong and d["phong"]["bac_si"].startswith("BS ")


async def test_lich_xep_sau_khi_nhan_bat_dau_gan_bu_bac_si_cung_lan(
    lan: Lan,
    bat: RB,  # noqa: F811
) -> None:
    """Prod 30/10 tầng 4 Hào Nam: ĐD Nhận lúc 19:24, lịch trực xếp 19:31 →
    lúc Nhận máy chưa biết làn, chỉ định không có bác sĩ (mất KPI). Bắt đầu /
    Hoàn tất phải gán bù bác sĩ của ô phụ tá người bấm đứng."""
    import uuid as _u

    from clinicai.services.service_execution_service import ServiceExecutionService

    b = lan.rb
    oid = await _cd_o(b, b.sa1)
    await _nhan(b, b.sa1, oid)
    assert (await _bs(b, oid))["id"] is None, "chưa có lịch → chưa đoán"

    await _truc(b, lan.vt["dd2"], b.truong_ca)
    r = await _bs(b, oid)
    await ServiceExecutionService(b.pool).bat_dau(
        order_id=oid,
        expected_execution_revision=int(
            await b.pool.fetchval(
                "SELECT execution_revision FROM service_order WHERE id = $1::uuid",
                oid,
            )
        ),
        expected_routing_revision=int(r["routing_revision"]),
        identity=b.truong_ca,
        idempotency_key=str(_u.uuid4()),
    )
    o = await _bs(b, oid)
    assert (o["id"], o["lan_lam"]) == (lan.bs_b.staff_id, 2)
    [ev] = await _su_kien_bs(b, oid)
    assert ev["theo_lan"] is True and ev["tu_dong"] is True


async def _bat_dau(b: RB, oid: str, ai: StaffIdentity) -> None:
    import uuid as _u

    from clinicai.services.service_execution_service import ServiceExecutionService

    r = await _bs(b, oid)
    await ServiceExecutionService(b.pool).bat_dau(
        order_id=oid,
        expected_execution_revision=int(
            await b.pool.fetchval(
                "SELECT execution_revision FROM service_order WHERE id = $1::uuid",
                oid,
            )
        ),
        expected_routing_revision=int(r["routing_revision"]),
        identity=ai,
        idempotency_key=str(_u.uuid4()),
    )


async def test_nguoi_bam_o_phong_thang_lua_chon_truoc(
    lan: Lan,
    bat: RB,  # noqa: F811
) -> None:
    """Tuyền 04/11/2026: "dù đd 3 chọn bác sĩ 2 thì vẫn tính cho bác sĩ 3".
    Quầy đã chọn BS A; người đứng ô ĐD2 (hỗ trợ BS2 = BS B) Nhận → BS B. Bác sĩ
    đã ghi rồi mà Bắt đầu bởi người của BS B → vẫn BS B."""
    b = lan.rb
    await _truc(b, lan.vt["dd2"], b.truong_ca)
    oid = await _cd_o(b, b.sa1)
    await b.svc.dat_phong_du_kien(
        order_id=oid,
        room_id=b.sa1,
        identity=b.truong_ca,
        bac_si_lam_id=lan.bs_a.staff_id,
    )
    await _nhan(b, b.sa1, oid)
    assert (await _bs(b, oid))["id"] == lan.bs_b.staff_id

    # Ghi tay về BS A (như quầy đổi), rồi người của BS B Bắt đầu → BS B.
    await b.pool.execute(
        "UPDATE service_order SET bac_si_lam_id = $2::uuid WHERE id = $1::uuid",
        oid,
        lan.bs_a.staff_id,
    )
    await _bat_dau(b, oid, b.truong_ca)
    assert (await _bs(b, oid))["id"] == lan.bs_b.staff_id


async def test_nguoi_khong_co_lich_giu_bac_si_da_ghi(
    lan: Lan,
    bat: RB,  # noqa: F811
) -> None:
    """Người bấm không đứng ô nào của phòng → không đoán, giữ bác sĩ đã ghi."""
    b = lan.rb
    oid = await _cd_o(b, b.sa1)
    await _nhan(b, b.sa1, oid)
    await b.pool.execute(
        "UPDATE service_order SET bac_si_lam_id = $2::uuid WHERE id = $1::uuid",
        oid,
        lan.bs_a.staff_id,
    )
    await _bat_dau(b, oid, b.truong_ca)
    assert (await _bs(b, oid))["id"] == lan.bs_a.staff_id


async def test_o_ho_tro_ep_o_postgres(lan: Lan) -> None:
    """Ô phụ tá chỉ hỗ trợ ô BÁC SĨ đang dùng cùng phòng; ô bác sĩ đổi nhóm /
    tắt → ô phụ tá của nó thành chưa gắn."""
    import asyncpg

    b = lan.rb
    with pytest.raises(asyncpg.CheckViolationError):
        await b.pool.execute(
            "UPDATE vi_tri_lam_viec SET ho_tro_code = $2 WHERE code = $1",
            lan.vt["dd1"],
            lan.vt["bs_sa2"],  # ô bác sĩ PHÒNG KHÁC
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await b.pool.execute(
            "UPDATE vi_tri_lam_viec SET ho_tro_code = $2 WHERE code = $1",
            lan.vt["dd1"],
            lan.vt["dd2"],  # không phải ô bác sĩ
        )
    await b.pool.execute(
        "UPDATE vi_tri_lam_viec SET nhom_nghe = 'DIEU_DUONG' WHERE code = $1",
        lan.vt["bs2"],
    )
    assert (
        await b.pool.fetchval(
            "SELECT ho_tro_code FROM vi_tri_lam_viec WHERE code = $1", lan.vt["dd2"]
        )
        is None
    )
