"""MẪU GỬI ĐỐI TÁC (Tuyền chốt 29/09/2026 — gói G8).

1. Dịch vụ THU HỘ đối tác (`billing_owner = EXTERNAL_PARTNER`) làm ở phòng CỦA
   phòng khám (Thủ thuật — Giải phẫu bệnh, Sinh thiết + GPB): phòng bấm Xong →
   việc lên /doi-tac (lý do MAU_GUI_DOI_TAC, nhãn "Mẫu gửi đối tác"); tích "Đã
   thu hộ cho đối tác", "Nhận mẫu · chờ tài liệu", tải tệp kết quả được (cả ngày
   cũ). Bấm Xong hai lần / sự kiện tới lần hai / phát lại: không nhân đôi. Quầy
   vẫn "thu hộ — không cộng".
2. Dịch vụ PHÒNG KHÁM thu ở phòng Thủ thuật: không lên bàn đối tác, không tải tệp
   qua cửa đối tác được.
3. Migration chốt thu hộ 10 mã CLS_* ngoài KiotViet: đổi đúng 10 mã, mã khác giữ,
   chạy lại được, đổi phòng làm không lật lại.
"""

from __future__ import annotations

import dataclasses
import pathlib
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from clinicai.api.v1.routers.doi_tac import _gui_ket_qua
from clinicai.core.clock import hom_nay_vn
from clinicai.core.exceptions import SafetyGateError
from clinicai.events.consumers.doi_tac import nhan_viec_doi_tac
from clinicai.events.worker import SuKienDaNhan
from clinicai.phieu_kham.ket_qua_chi_dinh import doc_ket_qua_theo_chi_dinh
from clinicai.services import finance_gate
from clinicai.services.bill_service import hoa_don_con_no
from clinicai.services.config_service import PriceListService
from clinicai.services.doi_tac_service import DoiTacService
from clinicai.services.nhan_tep_luong import TepDaNhan
from clinicai.services.service_execution_service import ServiceExecutionService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh, doi_tac_nhan
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _chon,
    _dung,
    _khoa,
    _thu,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

NODE_TT = "DICHVU-THUTHUAT"
PDF = b"%PDF-1.4\nket qua giai phau benh\n%%EOF"

MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase"
    / "migrations"
    / "20260929800000_mau_gui_doi_tac.sql"
)

MUOI_MA = (
    "CLS_XET_NGHIEM_MAU",
    "CLS_XN_NOI_TIET_NAM",
    "CLS_CFTR",
    "CLS_Y_MICRODELETION",
    "CLS_KARYOTYPE",
    "CLS_XET_NGHIEM_DICH_AM_DAO",
    "CLS_NUOC_TIEU_SAU_XUAT_TINH",
    "CLS_CHUP_VU_EP",
    "CLS_CHUP_MRI_VU",
    "CLS_CHUP_TU_CUNG_VOI_TRUNG",
)


@dataclasses.dataclass
class Viec:
    ca: Ca
    visit: str
    order: str
    phong: str


async def _phong_thu_thuat(pool: asyncpg.Pool, ca: Ca) -> str:  # noqa: F811
    """Phòng Thủ thuật CỦA phòng khám (node không `lam_ben_ngoai`) ở cơ sở ca thử."""
    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT lam_ben_ngoai FROM node_definition"
                " WHERE clinic_id = $1::uuid AND code = $2",
                CLINIC,
                NODE_TT,
            )
            is False
        )
        phong = str(
            await conn.fetchval(
                "INSERT INTO clinic_room (clinic_id, location_id, code, name,"
                " node_code, is_active, accepting, sort) VALUES ($1::uuid,"
                " $2::uuid, $3, 'Thủ thuật thử', $4, true, true, 0)"
                " RETURNING id::text",
                CLINIC,
                ca.loc,
                f"TT-{uuid.uuid4().hex[:6]}",
                NODE_TT,
            )
        )
        await conn.execute(
            "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
            " VALUES ($1::uuid, $2::uuid, $3)",
            CLINIC,
            phong,
            NODE_TT,
        )
    return phong


async def _dich_vu(pool: asyncpg.Pool, ben: str) -> str:  # noqa: F811
    ma = f"GPB-{uuid.uuid4().hex[:8]}"
    await pool.execute(
        'INSERT INTO service_price (clinic_id, service_code, name, "group",'
        " unit_price, node_code, billing_owner, billing_owner_chon_tay)"
        " VALUES ($1::uuid, $2, $3, 'dich_vu', 800000, $4, $5, true)",
        CLINIC,
        ma,
        f"Giải phẫu bệnh thử {ma}",
        NODE_TT,
        ben,
    )
    return ma


async def _chi_dinh(pool: asyncpg.Pool, ca: Ca, visit: str, ma: str) -> str:  # noqa: F811
    from clinicai.services.chi_dinh_service import ChiDinhService
    from clinicai.services.luot_kham_service import LuotKhamService

    con = str(
        await pool.fetchval(
            "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'PRIMARY'",
            visit,
        )
    )
    await LuotKhamService(pool).start_consultation(
        consultation_id=con, identity=ca.bac_si
    )
    kq = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ma],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    return str(kq["order_ids"][0])


async def _den_phong(pool: asyncpg.Pool, ben: str) -> Viec:  # noqa: F811
    """Khách khám, bác sĩ chỉ định dịch vụ ở phòng Thủ thuật, quầy chốt + thu,
    hệ thống xếp phòng. Chưa làm."""
    ca = await _dung(pool)
    phong = await _phong_thu_thuat(pool, ca)
    ma = await _dich_vu(pool, ben)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    order = await _chi_dinh(pool, ca, visit, ma)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    return Viec(ca=ca, visit=visit, order=order, phong=phong)


async def _bam_xong(pool: asyncpg.Pool, v: Viec) -> None:  # noqa: F811
    """Phòng bấm Bắt đầu rồi Xong — đường thật, phát `service.completed`."""
    o = await pool.fetchrow(
        "SELECT execution_revision, routing_revision, routing_status,"
        " room_id::text AS room_id FROM service_order WHERE id = $1::uuid",
        v.order,
    )
    # Xếp vào một phòng Thủ thuật CỦA phòng khám (DB thử có thể có nhiều).
    assert o["routing_status"] == "ASSIGNED"
    assert await pool.fetchval(
        "SELECT NOT r.la_doi_tac FROM clinic_room r JOIN clinic_room_node rn"
        " ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id"
        " WHERE r.id = $1::uuid AND rn.node_code = $2",
        o["room_id"],
        NODE_TT,
    )
    ex = ServiceExecutionService(pool)
    bd = await ex.bat_dau(
        order_id=v.order,
        expected_execution_revision=int(o["execution_revision"]),
        expected_routing_revision=int(o["routing_revision"]),
        identity=v.ca.dd,
        idempotency_key=_khoa(),
    )
    khoa = _khoa()
    kq = await ex.xong(
        order_id=v.order,
        attempt_id=str(bd["attempt_id"]),
        expected_execution_revision=int(bd["execution_revision"]),
        identity=v.ca.dd,
        idempotency_key=khoa,
    )
    # Bấm Xong LẦN HAI (mạng chập, bấm đúp) — cùng khoá: trả lại kết quả cũ.
    lai = await ex.xong(
        order_id=v.order,
        attempt_id=str(bd["attempt_id"]),
        expected_execution_revision=int(bd["execution_revision"]),
        identity=v.ca.dd,
        idempotency_key=khoa,
    )
    assert lai == kq


def _su_kien(v: Viec, *, phat_lai: bool = False) -> SuKienDaNhan:
    return SuKienDaNhan(
        event_id=str(uuid.uuid4()),
        event_type="service.completed",
        clinic_id=CLINIC,
        aggregate_id=v.order,
        aggregate_version=None,
        occurred_at=None,
        seq=0,
        actor_type="HUMAN",
        actor_staff_id=v.ca.dd.staff_id,
        payload={"visit_id": v.visit, "service_order_id": v.order},
        replay_id=str(uuid.uuid4()) if phat_lai else None,
        attempts=0,
    )


async def _so_nhan(pool: asyncpg.Pool, order: str) -> tuple[int, int]:  # noqa: F811
    dong = await pool.fetchval(
        "SELECT count(*) FROM doi_tac_nhan_viec WHERE service_order_id = $1::uuid",
        order,
    )
    su_kien = await pool.fetchval(
        "SELECT count(*) FROM domain_event WHERE event_type ="
        " 'partner.order_received' AND aggregate_id = $1::uuid",
        order,
    )
    return int(dong), int(su_kien)


def _tren_ban(kq: dict[str, Any], order: str) -> dict[str, Any] | None:
    return next(
        (dict(v) for k in kq["khach"] for v in k["viec"] if v["chi_dinh_id"] == order),
        None,
    )


def _tep(tmp_path: pathlib.Path, ten: str) -> TepDaNhan:
    duong = tmp_path / ten
    duong.write_bytes(PDF)
    return TepDaNhan(
        duong=duong, ten=ten, so_byte=len(PDF), sha256=uuid.uuid4().hex, dau=PDF
    )


async def _nhan_su_doi_tac(pool: asyncpg.Pool, ca: Ca) -> Any:  # noqa: F811
    """Nhân sự phòng khám đứng vị trí Đối tác (lego `partner.work`)."""
    async with pool.acquire() as conn:
        nv = await _nguoi(conn, ca.loc, "CASHIER")
        await conn.execute(
            "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
            " VALUES ($1::uuid, $2::uuid, 'partner.work', 'doi_tac')"
            " ON CONFLICT DO NOTHING",
            CLINIC,
            nv.staff_id,
        )
    return nv


# ---------------------------------------------------------------------------
# 1. Thu hộ đối tác ở phòng Thủ thuật
# ---------------------------------------------------------------------------


async def test_thu_ho_o_phong_thu_thuat_xong_thi_len_ban_doi_tac(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: Any,
    tmp_path: pathlib.Path,
) -> None:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)

    v = await _den_phong(pool, "EXTERNAL_PARTNER")
    nv = await _nhan_su_doi_tac(pool, v.ca)
    svc = DoiTacService(pool)

    # Quầy KHÔNG đổi: thu hộ đối tác — không cộng, FinanceGate sẵn sàng.
    async with pool.acquire() as conn:
        hd = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=v.visit)
        g = await finance_gate.states_for_orders(conn, CLINIC, [v.order])
    assert g[v.order].finance_state == finance_gate.PARTNER_COLLECTS
    assert g[v.order].financially_ready
    assert all(d.source_id != v.order for d in hd.dong)

    # Chưa làm → chưa có mẫu → chưa lên bàn.
    await doi_tac_nhan(pool)
    assert _tren_ban(await svc.viec_doi_tac(identity=nv), v.order) is None
    assert await _so_nhan(pool, v.order) == (0, 0)

    # Phòng bấm Xong (kể cả bấm đúp) → một việc, một sự kiện.
    await _bam_xong(pool, v)
    await doi_tac_nhan(pool)
    assert await _so_nhan(pool, v.order) == (1, 1)
    assert (
        await pool.fetchval(
            "SELECT ly_do FROM doi_tac_nhan_viec WHERE service_order_id = $1::uuid",
            v.order,
        )
        == "MAU_GUI_DOI_TAC"
    )
    viec = _tren_ban(await svc.viec_doi_tac(identity=nv), v.order)
    assert viec is not None
    assert viec["mau_gui_doi_tac"] is True
    assert viec["trang_thai"] == "DA_LAY_MAU"
    assert viec["doi_tac_thu"] is True and viec["da_thu"] is None

    # Sự kiện tới LẦN HAI (một sự kiện khác của lượt) + PHÁT LẠI → không nhân đôi.
    async with pool.acquire() as conn, conn.transaction():
        await nhan_viec_doi_tac(conn, _su_kien(v))
        await nhan_viec_doi_tac(conn, _su_kien(v, phat_lai=True))
    await doi_tac_nhan(pool)
    assert await _so_nhan(pool, v.order) == (1, 1)

    # Bác sĩ (phiếu kết quả) thấy trạng thái bàn đối tác của chỉ định này.
    async with pool.acquire() as conn:
        ds = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC, visit_id=v.visit)
    [cd] = [d for d in ds if d["service_order_id"] == v.order]
    assert cd["doi_tac"] == "DA_LAY_MAU"

    # Tích "Đã thu hộ cho đối tác".
    thu = await svc.ghi_nhan_da_thu(
        order_id=v.order, identity=nv, so_tien="800.000", hinh_thuc="CASH"
    )
    assert thu["already"] is False
    viec = _tren_ban(await svc.viec_doi_tac(identity=nv), v.order)
    assert viec is not None and viec["da_thu"]["so_tien"] == 800_000

    # "Nhận mẫu · chờ tài liệu".
    assert (await svc.doi_tac_cho_tai_lieu(order_id=v.order, identity=nv))[
        "already"
    ] is False

    # Tải kết quả đối tác gửi về qua CỬA ĐỐI TÁC.
    kq = await _gui_ket_qua(
        pool, nv, {"chi_dinh_id": v.order}, _tep(tmp_path, "gpb.pdf")
    )
    assert kq["ok"] is True
    viec = _tren_ban(await svc.viec_doi_tac(identity=nv), v.order)
    assert viec is not None and viec["trang_thai"] == "DA_GUI_KET_QUA"
    assert [t["ten"] for t in viec["tep"]] == ["gpb.pdf"]

    # NGÀY CŨ: việc từ hôm qua vẫn tìm lại được và gửi bổ sung được.
    await pool.execute(
        "UPDATE service_order SET created_at = created_at - interval '1 day',"
        " finished_at = finished_at - interval '1 day',"
        " ket_qua_luc = ket_qua_luc - interval '1 day',"
        " doi_tac_cho_tai_lieu_luc = doi_tac_cho_tai_lieu_luc - interval '1 day'"
        " WHERE id = $1::uuid",
        v.order,
    )
    await pool.execute(
        "UPDATE tep_ket_qua SET tai_len_luc = tai_len_luc - interval '1 day'"
        " WHERE service_order_id = $1::uuid",
        v.order,
    )
    hom_qua = (hom_nay_vn() - timedelta(days=1)).isoformat()
    cu = _tren_ban(await svc.viec_doi_tac(identity=nv, ngay=hom_qua), v.order)
    assert cu is not None and cu["mau_gui_doi_tac"] is True
    await _gui_ket_qua(
        pool, nv, {"chi_dinh_id": v.order}, _tep(tmp_path, "gpb-bo-sung.pdf")
    )
    moi = _tren_ban(await svc.viec_doi_tac(identity=nv), v.order)
    assert moi is not None
    assert [t["ten"] for t in moi["tep"]] == ["gpb.pdf", "gpb-bo-sung.pdf"]


# ---------------------------------------------------------------------------
# 2. Phòng khám thu ở phòng Thủ thuật — không phải việc đối tác
# ---------------------------------------------------------------------------


async def test_dich_vu_phong_kham_thu_o_thu_thuat_khong_len_ban(
    pool: asyncpg.Pool,  # noqa: F811
    tmp_path: pathlib.Path,
) -> None:
    v = await _den_phong(pool, "CLINIC")
    nv = await _nhan_su_doi_tac(pool, v.ca)
    await _bam_xong(pool, v)
    await doi_tac_nhan(pool)
    async with pool.acquire() as conn, conn.transaction():
        await nhan_viec_doi_tac(conn, _su_kien(v))
    assert await _so_nhan(pool, v.order) == (0, 0)
    svc = DoiTacService(pool)
    assert _tren_ban(await svc.viec_doi_tac(identity=nv), v.order) is None
    # Cửa đối tác không nhận tệp / bấm bước cho việc nội bộ.
    with pytest.raises(SafetyGateError):
        await _gui_ket_qua(pool, nv, {"chi_dinh_id": v.order}, _tep(tmp_path, "x.pdf"))
    with pytest.raises(SafetyGateError):
        await svc.doi_tac_cho_tai_lieu(order_id=v.order, identity=nv)
    async with pool.acquire() as conn:
        ds = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC, visit_id=v.visit)
    [cd] = [d for d in ds if d["service_order_id"] == v.order]
    assert cd["doi_tac"] is None


# ---------------------------------------------------------------------------
# 3. Migration chốt thu hộ 10 mã ngoài KiotViet
# ---------------------------------------------------------------------------


async def test_migration_chot_thu_ho_muoi_ma(pool: asyncpg.Pool) -> None:  # noqa: F811
    async def doc() -> dict[str, tuple[str, bool]]:
        return {
            str(r["id"]): (r["billing_owner"], r["billing_owner_chon_tay"])
            for r in await pool.fetch(
                "SELECT id, billing_owner, billing_owner_chon_tay FROM service_price"
                " WHERE clinic_id = $1::uuid",
                CLINIC,
            )
        }

    muoi = {
        str(r["id"]): r["service_code"]
        for r in await pool.fetch(
            "SELECT id, service_code FROM service_price WHERE clinic_id = $1::uuid"
            " AND \"group\" = 'dich_vu' AND service_code = ANY($2::text[])",
            CLINIC,
            list(MUOI_MA),
        )
    }
    assert sorted(set(muoi.values())) == sorted(MUOI_MA)  # đủ 10 mã
    # Trả 10 mã về "trạng thái trước migration" (DB dựng mới đã chạy migration
    # + seed): nửa CLINIC, nửa thu hộ chưa chọn tay.
    await pool.execute(
        "UPDATE service_price SET billing_owner = CASE WHEN service_code IN"
        " ('CLS_XET_NGHIEM_MAU', 'CLS_CHUP_VU_EP', 'CLS_CHUP_MRI_VU',"
        "  'CLS_CHUP_TU_CUNG_VOI_TRUNG', 'CLS_XET_NGHIEM_DICH_AM_DAO')"
        " THEN 'CLINIC' ELSE 'EXTERNAL_PARTNER' END,"
        " billing_owner_chon_tay = false WHERE id = ANY($1::uuid[])",
        list(muoi),
    )
    truoc = await doc()

    await pool.execute(MIGRATION.read_text(encoding="utf-8"))
    sau = await doc()
    for pid in muoi:
        assert sau[pid] == ("EXTERNAL_PARTNER", True), muoi[pid]
    # Mã khác GIỮ NGUYÊN — bên thu lẫn cờ chọn tay.
    khac = {p: b for p, b in truoc.items() if p not in muoi}
    assert khac and {p: sau[p] for p in khac} == khac

    # Chạy lại được: lần hai không đổi gì.
    assert (
        await pool.fetchval("SELECT public.chot_thu_ho_dich_vu_ngoai_kiotviet()") == 0
    )
    await pool.execute(MIGRATION.read_text(encoding="utf-8"))
    assert await doc() == sau

    # Đổi phòng làm ở Bảng giá sang phòng CỦA phòng khám KHÔNG lật "thu hộ".
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        ql = await _nguoi(conn, loc, "MANAGEMENT")
    pid = next(p for p, m in muoi.items() if m == "CLS_XET_NGHIEM_MAU")
    await PriceListService(pool).update(price_id=pid, identity=ql, node_code=NODE_TT)
    assert (await doc())[pid] == ("EXTERNAL_PARTNER", True)
