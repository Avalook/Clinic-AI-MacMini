"""Bán vật tư trừ kho đúng phòng + danh sách đối soát (31/10/2026).

    scripts/test-nhanh.sh src/tests/services/test_vat_tu_ban_kho_db.py

BẤT BIẾN (kiểm cả bằng bài bấm ngẫu nhiên, sự kiện giao hai lần xen giữa):

  V1  Tồn mỗi nơi chứa = tổng sổ `vat_tu_txn` của nơi ấy.
  V2  Mỗi dòng bán: tổng sổ theo `ban_id` = −số đang bán nếu "đã trừ", 0 nếu không.
  V3  Mỗi nguồn bán đúng một dòng, tối đa một phiếu BAN chưa đảo.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from collections.abc import AsyncIterator
from dataclasses import replace
from decimal import Decimal
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from clinicai.core.exceptions import SafetyGateError
from clinicai.events.catalogue import HANH_TRINH, VAT_TU_BAN
from clinicai.permissions.can import can
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services import vat_tu_ban_service as ban
from clinicai.services import vat_tu_kho_man_service as man
from clinicai.services import vat_tu_kho_service as kho
from clinicai.services import vat_tu_tieu_hao_service as tieu_hao
from clinicai.services.ban_thuoc_service import man_nha_thuoc
from clinicai.services.bill_service import tinh_hoa_don
from clinicai.services.bio_chi_dinh_service import chuyen_bio_chua_thu
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.payment_service import PaymentService
from clinicai.services.pharmacy_service import PharmacyService
from clinicai.services.service_execution_service import ServiceExecutionService
from clinicai.services.vat_tu_ban_service import (
    CHO_GAN_PHONG,
    DA_HOAN,
    DA_TRU,
    Noi,
    chon_noi,
    phong_cua_bac_si,
    so_cho_xu_ly,
)
from clinicai.services.vat_tu_service import VatTuService
from clinicai.services.vat_tu_trung_ma import thuoc_la_vat_tu
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_bio_chi_dinh_db import (  # noqa: F401
    Luot,
    _bio,
    _huy_chi_dinh,
    _huy_phieu,
    _khoi_phuc,
    _lam_truoc_thu_sau,
    _luot,
    _thu,
    _vat_tu,
)
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_don_du_lieu_thu_db import _nguoi as _nguoi_khoi
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _don,
    _dung,
    _khoa,
)
from tests.services.test_tien_thuoc_cp1_db import Quay, tao_quay

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

GIA_VON = 70_000


# ── dựng ────────────────────────────────────────────────────────────────────
async def _phong(
    pool: asyncpg.Pool,  # noqa: F811
    loc: str,
    *,
    active: bool = True,
    doi_tac: bool = False,
) -> str:
    return str(
        await pool.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
            " is_active, accepting, sort, la_doi_tac)"
            " VALUES ($1::uuid, $2::uuid, $3, $4, 'DICHVU-SIEUAM', $5, true, 999, $6)"
            " RETURNING id::text",
            CLINIC,
            loc,
            f"VTB-{uuid.uuid4().hex[:8]}",
            f"Phòng Sản {uuid.uuid4().hex[:6]}",
            active,
            doi_tac,
        )
    )


async def _nhap(
    pool: asyncpg.Pool,  # noqa: F811
    ai: Any,
    vt: str,
    room: str | None,
    so: int = 10,
    gia: int = GIA_VON,
) -> None:
    await kho.tao_phieu(
        pool,
        identity=ai,
        khoa_gui=_khoa(),
        loai="NHAP",
        dong=[
            {
                "vat_tu_id": vt,
                "den_room_id": room,
                "so_luong": so,
                "gia_nhap": gia,
            }
        ],
    )


async def _ton(
    pool: asyncpg.Pool,  # noqa: F811
    vt: str,
    room: str | None,
    loc: str | None = None,
) -> Decimal:
    v = await pool.fetchval(
        "SELECT so_luong FROM vat_tu_ton WHERE clinic_id = $1::uuid"
        " AND vat_tu_id = $2::uuid AND room_id IS NOT DISTINCT FROM $3::uuid"
        " AND ($4::uuid IS NULL OR location_id = $4::uuid)",
        CLINIC,
        vt,
        room,
        loc,
    )
    return Decimal(v or 0)


async def _dong_luot(pool: asyncpg.Pool, order: str) -> asyncpg.Record:  # noqa: F811
    r = await pool.fetchrow(
        "SELECT b.* FROM vat_tu_ban b JOIN luot_vat_tu v ON v.id = b.luot_vat_tu_id"
        " WHERE v.order_id = $1::uuid AND v.bo_luc IS NULL",
        order,
    )
    assert r is not None, "chưa có dòng bán"
    return r


async def _chi_dinh_o(pool: asyncpg.Pool, order: str, room: str | None) -> None:  # noqa: F811
    """Đặt phòng của chỉ định. Bỏ phòng đã tự xếp (dây thu trước đang tắt nên chỉ
    định được xếp ngay lúc khách chốt); `None` = chỉ định chưa có phòng."""
    await pool.execute(
        "UPDATE service_order SET room_id = NULL, routing_status = 'UNASSIGNED',"
        " exec_status = 'authorized', phong_du_kien_id = $2::uuid"
        " WHERE id = $1::uuid",
        order,
        room,
    )


async def _lich_bac_si(
    pool: asyncpg.Pool,  # noqa: F811
    bac_si: str,
    room: str,
    shift: str = "FULL",
) -> None:
    ma = f"VT-{uuid.uuid4().hex[:8]}"
    await pool.execute(
        "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, room_id, nhom_nghe)"
        " VALUES ($1::uuid, $2, $3, $4::uuid, 'BAC_SI')",
        CLINIC,
        ma,
        f"Vị trí {ma}",
        room,
    )
    await pool.execute(
        "INSERT INTO work_roster (clinic_id, week_start, work_date, shift, station,"
        " staff_id, staff_name, status)"
        " SELECT $1::uuid, d - (extract(isodow from d)::int - 1), d, $2, $3,"
        " $4::uuid, 'BS thử', 'APPROVED'"
        " FROM (SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS d) x",
        CLINIC,
        shift,
        ma,
        bac_si,
    )


async def _mot_bio(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    *,
    so_luong: int = 1,
    xep_that: bool = False,
) -> tuple[Luot, str]:
    """Lượt có Bio trên chỉ định A, chỉ định đang ở một phòng có sẵn 10 cái.
    `xep_that`: giữ phòng khối Hành trình đã xếp, để bắt đầu làm dịch vụ được."""
    lt = await _luot(pool, ca)
    if xep_that:
        room = str(
            await pool.fetchval(
                "SELECT room_id::text FROM service_order WHERE id = $1::uuid", lt.a
            )
        )
    else:
        room = await _phong(pool, ca.loc)
        await _chi_dinh_o(pool, lt.a, room)
    await _nhap(pool, ca.thu_ngan, lt.bio1, room)
    await _bio(pool, lt, lt.a, lt.bio1, so_luong=so_luong)
    return lt, room


async def _lan_thu(pool: asyncpg.Pool, lt: Luot) -> str:  # noqa: F811
    return str(
        await pool.fetchval(
            "SELECT payment_cycle_id::text FROM payment_cycle WHERE visit_id = $1::uuid"
            " AND kind = 'dich_vu' ORDER BY created_at DESC LIMIT 1",
            lt.visit,
        )
    )


async def _hoan(
    pool: asyncpg.Pool,  # noqa: F811
    lt: Luot,
    line: str,
    so: int,
    *,
    method: str = "CASH",
    tra_hang: bool = False,
) -> dict[str, Any]:
    return await HoanTienService(pool).tao(
        identity=lt.ca.thu_ngan,
        payment_cycle_id=await _lan_thu(pool, lt),
        visit_id=lt.visit,
        kind="dich_vu",
        dong=[{"payment_bill_line_id": line, "so_luong": so, "tra_hang": tra_hang}],
        method=method,
        reason="Khách đổi ý không lấy",
    )


async def _dong_hoa_don(pool: asyncpg.Pool, luot_id: str) -> str:  # noqa: F811
    return str(
        await pool.fetchval(
            "SELECT id::text FROM payment_bill_line WHERE source_type = 'vat_tu'"
            " AND source_id = $1",
            luot_id,
        )
    )


async def _xem(pool: asyncpg.Pool, ai: Any, ban_id: str) -> dict[str, Any]:  # noqa: F811
    kq = await ban.doc_ban(pool, identity=ai)
    return next(d for d in kq["items"] if d["id"] == ban_id)


async def _lech(pool: asyncpg.Pool) -> list[str]:  # noqa: F811
    """Các bất biến bị vỡ (rỗng = khớp)."""
    vo = [
        f"V1 {r['id']}"
        for r in await pool.fetch(
            "SELECT t.id FROM vat_tu_ton t LEFT JOIN vat_tu_txn x ON x.ton_id = t.id"
            " WHERE t.clinic_id = $1::uuid GROUP BY t.id, t.so_luong"
            " HAVING t.so_luong <> coalesce(sum(x.so_luong), 0)",
            CLINIC,
        )
    ]
    vo += [
        f"V2 {r['id']}"
        for r in await pool.fetch(
            "SELECT b.id FROM vat_tu_ban b"
            " LEFT JOIN vat_tu_phieu p ON p.ban_id = b.id AND p.clinic_id = b.clinic_id"
            " LEFT JOIN vat_tu_txn x ON x.phieu_id = p.id AND x.clinic_id = p.clinic_id"
            " WHERE b.clinic_id = $1::uuid GROUP BY b.id"
            " HAVING coalesce(sum(x.so_luong), 0) <> CASE WHEN b.trang_thai = 'DA_TRU'"
            "   THEN -b.so_luong ELSE 0 END",
            CLINIC,
        )
    ]
    vo += [
        f"V3 {r['ban_id']}"
        for r in await pool.fetch(
            "SELECT p.ban_id FROM vat_tu_phieu p WHERE p.clinic_id = $1::uuid"
            " AND p.loai = 'BAN' AND NOT EXISTS (SELECT 1 FROM vat_tu_phieu d"
            "   WHERE d.dao_phieu_id = p.id AND d.clinic_id = p.clinic_id)"
            " GROUP BY p.ban_id HAVING count(*) > 1",
            CLINIC,
        )
    ]
    return vo


@pytest_asyncio.fixture
async def ca(pool: asyncpg.Pool) -> AsyncIterator[Ca]:  # noqa: F811
    yield await _dung(pool)


# ── Luật thuần ──────────────────────────────────────────────────────────────
def test_chon_noi_kho_gan_roi_may_khong_doi() -> None:
    kho_gan = Noi("PHONG", "p1", "KHO")
    assert chon_noi(kho_gan, "p2", "p3") == kho_gan
    assert chon_noi(None, "p2", "p3") == Noi("PHONG", "p2", "CHI_DINH")
    assert chon_noi(Noi("PHONG", "p3", "BAC_SI"), "p2", None) == Noi(
        "PHONG", "p2", "CHI_DINH"
    )
    assert chon_noi(None, None, "p3") == Noi("PHONG", "p3", "BAC_SI")
    assert chon_noi(None, None, None) is None


def test_phong_bac_si_hai_phong_khong_phan_duoc_thi_khong_doan() -> None:
    ca = {"SANG": (420, 720), "CHIEU": (780, 1080)}
    dong = [("p1", "SANG", "APPROVED"), ("p2", "CHIEU", "APPROVED")]
    assert phong_cua_bac_si(dong, 500, ca) == "p1"
    assert phong_cua_bac_si(dong, 800, ca) == "p2"
    assert phong_cua_bac_si(dong, 750, ca) is None  # nghỉ trưa, hai phòng
    assert phong_cua_bac_si(dong, None, ca) is None
    assert phong_cua_bac_si([("p1", "SANG", "REJECTED")], 500, ca) is None
    assert phong_cua_bac_si([], 500, ca) is None


def test_so_cho_xu_ly() -> None:
    d = Decimal
    assert so_cho_xu_ly(DA_TRU, d(2), d(1), d(0)) == 1
    assert so_cho_xu_ly(DA_TRU, d(2), d(1), d(1)) == 0
    assert so_cho_xu_ly(DA_HOAN, d(2), d(0), d(0)) == 0


async def test_danh_sach_dau_vao_rac_khong_nem(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    kq = await ban.doc_ban(
        pool, identity=ca.thu_ngan, tu="rác", den="31/13", noi="xxx", trang_thai="?"
    )
    assert isinstance(kq["items"], list)
    assert await man.doc_phieu(pool, identity=ca.thu_ngan, vat_tu_id="rác") is not None


# ── Bán xong → trừ đúng phòng ───────────────────────────────────────────────
async def test_thu_tien_tru_dung_phong_chi_dinh_co_vet(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca, so_luong=2)
    await _thu(pool, lt)
    assert await _ton(pool, lt.bio1, room) == 8
    b = await _dong_luot(pool, lt.a)
    assert b["trang_thai"] == DA_TRU and b["room_id"] == uuid.UUID(room)
    assert b["noi_nguon"] == "CHI_DINH" and b["nguon"] == "CHI_DINH"
    assert b["gia_von"] == GIA_VON  # mục 8: giá nhập gần nhất, không phải 0đ
    p = await pool.fetchrow(
        "SELECT * FROM vat_tu_phieu WHERE id = $1::uuid", b["phieu_id"]
    )
    assert p["loai"] == "BAN" and p["payment_cycle_id"] is not None
    assert p["clinic_patient_id"] == b["clinic_patient_id"]
    assert p["tao_boi"] == uuid.UUID(ca.thu_ngan.staff_id)
    d = await _xem(pool, ca.thu_ngan, str(b["id"]))
    assert d["trang_thai_ten"] == "Đã trừ kho" and d["noi_lay_ten"] == d["phong"]
    assert d["thanh_tien"] == 600_000 and d["khach"] and d["nguoi_ban"]
    assert not await _lech(pool)


async def test_khong_ro_phong_cho_gan_roi_gan_doi_phong(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt = await _luot(pool, ca)
    p1, p2 = await _phong(pool, ca.loc), await _phong(pool, ca.loc)
    await _nhap(pool, ca.thu_ngan, lt.bio1, p1)
    await _chi_dinh_o(pool, lt.a, None)
    await _bio(pool, lt, lt.a, lt.bio1)
    await _thu(pool, lt)
    b = await _dong_luot(pool, lt.a)
    assert b["trang_thai"] == CHO_GAN_PHONG and b["phieu_id"] is None
    assert (await ban.doc_ban(pool, identity=ca.thu_ngan))["cho_gan"] >= 1
    assert await _ton(pool, lt.bio1, p1) == 10

    bid = str(b["id"])
    with pytest.raises(ValidationError):
        await ban.gan_noi_lay(
            pool, identity=ca.thu_ngan, ban_id=bid, room_id=p1, ly_do="x"
        )
    await ban.gan_noi_lay(
        pool, identity=ca.thu_ngan, ban_id=bid, room_id=p1, ly_do="BS Sản đưa đầu dò"
    )
    assert await _ton(pool, lt.bio1, p1) == 9
    # Gửi lại cùng nơi: không ghi sổ.
    kq = await ban.gan_noi_lay(
        pool, identity=ca.thu_ngan, ban_id=bid, room_id=p1, ly_do="BS Sản đưa đầu dò"
    )
    assert kq["gui_lai"] and await _ton(pool, lt.bio1, p1) == 9
    # Đổi phòng: đảo chỗ cũ + trừ chỗ mới, tồn âm vẫn cho.
    await ban.gan_noi_lay(
        pool, identity=ca.thu_ngan, ban_id=bid, room_id=p2, ly_do="Lấy nhầm phòng"
    )
    assert await _ton(pool, lt.bio1, p1) == 10
    assert await _ton(pool, lt.bio1, p2) == -1
    # Kho cơ sở cũng gán được.
    await ban.gan_noi_lay(
        pool, identity=ca.thu_ngan, ban_id=bid, room_id=None, ly_do="Lấy ở Kho cơ sở"
    )
    assert await _ton(pool, lt.bio1, p2) == 0
    assert await _ton(pool, lt.bio1, None) == -1
    d = await _xem(pool, ca.thu_ngan, bid)
    assert d["noi_lay_ten"] == "Kho cơ sở" and d["ly_do"] == "Lấy ở Kho cơ sở"
    ls = await man.doc_phieu(pool, identity=ca.thu_ngan, vat_tu_id=lt.bio1)
    chu = [p["ghi_chu"] for p in ls]
    assert "Lấy ở Kho cơ sở" in chu and "Đổi nơi lấy: Lấy ở Kho cơ sở" in chu
    assert all(p["khach"] for p in ls if p["ban_id"])
    assert not await _lech(pool)


async def test_phieu_ban_khong_hoan_tac_o_lich_su(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca)
    await _thu(pool, lt)
    b = await _dong_luot(pool, lt.a)
    with pytest.raises(ConflictError):
        await kho.hoan_phieu(
            pool,
            identity=ca.thu_ngan,
            phieu_id=str(b["phieu_id"]),
            khoa_gui=_khoa(),
        )
    assert await _ton(pool, lt.bio1, room) == 9


async def test_loc_lich_su_theo_mat_hang(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    a = await _vat_tu(pool, "Hàng A", 1000)
    b = await _vat_tu(pool, "Hàng B", 1000)
    await _nhap(pool, ca.thu_ngan, a, None)
    await _nhap(pool, ca.thu_ngan, b, None)
    ds = await man.doc_phieu(pool, identity=ca.thu_ngan, vat_tu_id=a)
    assert ds and all(any(d["vat_tu_id"] == a for d in p["dong"]) for p in ds)
    assert not any(any(d["vat_tu_id"] == b for d in p["dong"]) for p in ds)


# ── Nhập bù ────────────────────────────────────────────────────────────────
async def test_nhap_bu_chi_tru_kho_hoan_tac_duoc(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt = await _luot(pool, ca)
    room = await _phong(pool, ca.loc)
    await _nhap(pool, ca.thu_ngan, lt.bio1, room)
    khach = str(
        await pool.fetchval(
            "SELECT clinic_patient_id FROM visit WHERE visit_id = $1::uuid", lt.visit
        )
    )
    khoa = _khoa()
    goi: dict[str, Any] = {
        "identity": ca.thu_ngan,
        "khoa_gui": khoa,
        "clinic_patient_id": khach,
        "vat_tu_id": lt.bio1,
        "so_luong": 2,
        "room_id": room,
        "ly_do": "Quầy quên ghi hôm qua",
    }
    kq = await ban.nhap_bu(pool, **goi)
    assert await _ton(pool, lt.bio1, room) == 8
    lai = await ban.nhap_bu(pool, **goi)
    assert lai["gui_lai"] and lai["id"] == kq["id"]
    assert await _ton(pool, lt.bio1, room) == 8
    d = await _xem(pool, ca.thu_ngan, kq["id"])
    assert d["nguon_ten"] == "Nhập bù" and d["thanh_tien"] == 0
    assert d["hoan_tac_duoc"] and not d["nhan_lai_duoc"]
    with pytest.raises(ValidationError):
        await ban.nhap_bu(pool, **{**goi, "khoa_gui": _khoa(), "ly_do": ""})
    with pytest.raises(ValidationError):
        await ban.nhap_bu(pool, **{**goi, "khoa_gui": _khoa(), "so_luong": "rác"})
    with pytest.raises(NotFoundError):
        await ban.nhap_bu(
            pool, **{**goi, "khoa_gui": _khoa(), "clinic_patient_id": str(uuid.uuid4())}
        )

    await ban.hoan_tac_nhap_bu(
        pool, identity=ca.thu_ngan, ban_id=kq["id"], ly_do="Ghi nhầm khách"
    )
    assert await _ton(pool, lt.bio1, room) == 10
    lai = await ban.hoan_tac_nhap_bu(
        pool, identity=ca.thu_ngan, ban_id=kq["id"], ly_do="Ghi nhầm khách"
    )
    assert lai["gui_lai"] and await _ton(pool, lt.bio1, room) == 10
    assert not await _lech(pool)


async def test_dong_co_tien_khong_hoan_tac_nhu_nhap_bu(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, _room = await _mot_bio(pool, ca)
    await _thu(pool, lt)
    b = await _dong_luot(pool, lt.a)
    with pytest.raises(ConflictError):
        await ban.hoan_tac_nhap_bu(
            pool, identity=ca.thu_ngan, ban_id=str(b["id"]), ly_do="Thử hoàn tác"
        )


# ── Hoàn tác lần thu, thu lại ──────────────────────────────────────────────
async def test_hoan_tac_ve_dung_noi_thu_lai_tru_lai_mot_dong(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt = await _luot(pool, ca)
    p1, p2 = await _phong(pool, ca.loc), await _phong(pool, ca.loc)
    await _nhap(pool, ca.thu_ngan, lt.bio1, p1)
    await _chi_dinh_o(pool, lt.a, p1)
    await _bio(pool, lt, lt.a, lt.bio1)
    await _thu(pool, lt)
    b = await _dong_luot(pool, lt.a)
    await ban.gan_noi_lay(
        pool, identity=ca.thu_ngan, ban_id=str(b["id"]), room_id=p2, ly_do="Đổi phòng"
    )
    lan = await _lan_thu(pool, lt)
    await _huy_phieu(pool, lt)
    assert await _ton(pool, lt.bio1, p2) == 0
    assert (await _dong_luot(pool, lt.a))["trang_thai"] == DA_HOAN
    # Gửi lại lệnh hoàn tác: như cũ, không đảo lần hai.
    await PaymentService(pool).void_payment(
        payment_cycle_id=lan,
        visit_id=lt.visit,
        kind="dich_vu",
        reason="Thu nhầm, huỷ phiếu",
        identity=ca.thu_ngan,
    )
    assert await _ton(pool, lt.bio1, p2) == 0
    await _thu(pool, lt)
    assert await _ton(pool, lt.bio1, p2) == -1  # người kho đã gán thì đi theo
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM vat_tu_ban WHERE visit_id = $1::uuid", lt.visit
        )
        == 1
    )
    assert not await _lech(pool)


# ── Mục 1: làm trước, thu sau ───────────────────────────────────────────────
async def test_lam_truoc_thu_sau_tru_khi_lam_khong_tru_lai_khi_thu(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca, xep_that=True)
    d = await _don(pool, lt.a)
    await ServiceExecutionService(pool).bat_dau(
        order_id=lt.a,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    await chay_ben_nhan(pool, VAT_TU_BAN)
    assert await _ton(pool, lt.bio1, room) == 9  # chưa thu đồng nào
    b = await _dong_luot(pool, lt.a)
    assert b["trang_thai"] == DA_TRU and b["payment_cycle_id"] is None
    assert (await _xem(pool, ca.thu_ngan, str(b["id"])))["chua_thu"]

    await _thu(pool, lt)
    await chay_ben_nhan(pool, VAT_TU_BAN)
    assert await _ton(pool, lt.bio1, room) == 9  # chỉ một lần
    b = await _dong_luot(pool, lt.a)
    assert b["thanh_tien"] == 300_000 and b["payment_cycle_id"] is not None

    # Hàng đã dùng: hoàn tác lần thu thì khách thành nợ, số KHÔNG về.
    await _huy_phieu(pool, lt)
    assert await _ton(pool, lt.bio1, room) == 9
    b = await _dong_luot(pool, lt.a)
    assert b["trang_thai"] == DA_TRU and "giữ số đã trừ" in str(b["ly_do"])
    assert b["payment_cycle_id"] is None
    assert not await _lech(pool)


async def test_chi_dinh_da_lam_doi_loai_bio_truoc_thu_ve_dung_cho(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca, xep_that=True)
    await _nhap(pool, ca.thu_ngan, lt.bio_n, room, 5)
    d = await _don(pool, lt.a)
    await ServiceExecutionService(pool).bat_dau(
        order_id=lt.a,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    await chay_ben_nhan(pool, VAT_TU_BAN)
    assert await _ton(pool, lt.bio1, room) == 9
    await _bio(pool, lt, lt.a, lt.bio_n)  # 1 lần → nhiều lần, chưa thu
    assert await _ton(pool, lt.bio1, room) == 10
    assert await _ton(pool, lt.bio_n, room) == 4
    assert not await _lech(pool)


async def test_doi_bio_truoc_thu_chua_lam_khong_dung_kho_sau_thu_khoa(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca)
    await _nhap(pool, ca.thu_ngan, lt.bio_n, room, 5)
    await _bio(pool, lt, lt.a, lt.bio_n)
    assert await _ton(pool, lt.bio1, room) == 10
    await _thu(pool, lt)
    assert (
        await _ton(pool, lt.bio_n, room) == 4 and await _ton(pool, lt.bio1, room) == 10
    )
    with pytest.raises(ConflictError):
        await _bio(pool, lt, lt.a, lt.bio1)
    assert await _ton(pool, lt.bio_n, room) == 4


# ── Mục 2: miễn phí, chuyển khoản ──────────────────────────────────────────
async def test_mien_phi_100_van_tru(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca)
    await PaymentService(pool).record_payment(
        visit_id=lt.visit,
        kind="dich_vu",
        amount=None,
        clinic_patient_id=None,
        identity=ca.thu_ngan,
        method="CASH",
        idempotency_key=_khoa(),
        quay="dich_vu",
        discount_type="PERCENT",
        discount_value=100,
        discount_reason="Miễn phí cho khách",
    )
    assert await _ton(pool, lt.bio1, room) == 9
    b = await _dong_luot(pool, lt.a)
    assert b["trang_thai"] == DA_TRU and b["thanh_tien"] == 0
    assert not await _lech(pool)


async def test_chuyen_khoan_tru_luc_cho_huy_thi_dao_xac_minh_khong_tru_lai(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca)
    lan = await _thu(pool, lt, "TRANSFER")
    assert await _ton(pool, lt.bio1, room) == 9  # hàng đã đi cùng lúc khách đi tiếp
    await PaymentService(pool).huy_cho_xac_minh(
        payment_cycle_id=lan,
        visit_id=lt.visit,
        kind="dich_vu",
        reason="Khách không chuyển",
        identity=ca.thu_ngan,
    )
    assert await _ton(pool, lt.bio1, room) == 10
    assert (await _dong_luot(pool, lt.a))["trang_thai"] == DA_HOAN

    lan = await _thu(pool, lt, "TRANSFER")
    assert await _ton(pool, lt.bio1, room) == 9
    so_ck = await pool.fetchval(
        "SELECT amount FROM payment_cycle WHERE payment_cycle_id = $1::uuid", lan
    )
    await PaymentService(pool).xac_minh_dien_tu(
        payment_cycle_id=lan,
        visit_id=lt.visit,
        kind="dich_vu",
        reference=None,
        identity=ca.thu_ngan,
        so_tien_thuc_nhan=so_ck,
    )
    assert await _ton(pool, lt.bio1, room) == 9
    assert not await _lech(pool)


# ── Mục 3 + 7: hoàn tiền ≠ hàng về ──────────────────────────────────────────
async def test_hoan_tien_mot_phan_khong_tu_cong_kho_nguoi_kho_xu_ly(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca, so_luong=3)
    await _thu(pool, lt)
    b = await _dong_luot(pool, lt.a)
    bid, line = str(b["id"]), await _dong_hoa_don(pool, str(b["luot_vat_tu_id"]))
    await _hoan(pool, lt, line, 1)
    assert await _ton(pool, lt.bio1, room) == 7  # tiền ra, hàng chưa về
    d = await _xem(pool, ca.thu_ngan, bid)
    assert d["so_cho_xu_ly"] == 1 and d["khong_nhan_duoc"] and d["nhan_lai_duoc"]
    assert d["thanh_tien"] == 600_000 and "Hoàn tiền" in str(d["ly_do"])
    assert (await ban.doc_ban(pool, identity=ca.thu_ngan))["cho_xu_ly"] >= 1

    # Khách trả thật → số về đúng phòng, phần còn lại vẫn đang trừ.
    await ban.nhan_lai_hang(
        pool, identity=ca.thu_ngan, ban_id=bid, so_luong=1, ly_do="Khách trả đầu dò"
    )
    assert await _ton(pool, lt.bio1, room) == 8
    d = await _xem(pool, ca.thu_ngan, bid)
    assert d["so_luong"] == 2 and d["so_cho_xu_ly"] == 0
    with pytest.raises(ValidationError):
        await ban.nhan_lai_hang(
            pool, identity=ca.thu_ngan, ban_id=bid, so_luong=5, ly_do="Nhận quá số"
        )

    # Hoàn tiếp mà hàng không về: người kho kết luận, tồn giữ nguyên.
    await _hoan(pool, lt, line, 1)
    assert (await _xem(pool, ca.thu_ngan, bid))["so_cho_xu_ly"] == 1
    await ban.khong_nhan_lai(
        pool, identity=ca.thu_ngan, ban_id=bid, ly_do="Đầu dò đã dùng cho khách"
    )
    await ban.khong_nhan_lai(
        pool, identity=ca.thu_ngan, ban_id=bid, ly_do="Đầu dò đã dùng cho khách"
    )
    d = await _xem(pool, ca.thu_ngan, bid)
    assert d["so_cho_xu_ly"] == 0 and "Không nhận lại" in str(d["ly_do"])
    assert await _ton(pool, lt.bio1, room) == 8
    assert not await _lech(pool)


async def test_hoan_chuyen_khoan_chua_xong_chua_tinh_la_da_hoan(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca, so_luong=2)
    await _thu(pool, lt)
    b = await _dong_luot(pool, lt.a)
    line = await _dong_hoa_don(pool, str(b["luot_vat_tu_id"]))
    kq = await _hoan(pool, lt, line, 1, method="TRANSFER")
    assert (await _dong_luot(pool, lt.a))["so_hoan_tien"] == 0
    await HoanTienService(pool).xac_nhan(
        identity=ca.thu_ngan, refund_id=kq["refund_id"], reference="GD12345"
    )
    assert (await _dong_luot(pool, lt.a))["so_hoan_tien"] == 1
    assert await _ton(pool, lt.bio1, room) == 8


async def test_quay_dich_vu_hoan_kem_khach_tra_hang(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca, so_luong=2)
    await _thu(pool, lt)
    b = await _dong_luot(pool, lt.a)
    line = await _dong_hoa_don(pool, str(b["luot_vat_tu_id"]))
    await _hoan(pool, lt, line, 1, tra_hang=True)
    assert await _ton(pool, lt.bio1, room) == 9
    d = await _xem(pool, ca.thu_ngan, str(b["id"]))
    assert d["so_luong"] == 1 and d["so_cho_xu_ly"] == 0
    await _hoan(pool, lt, line, 1, tra_hang=True)
    assert await _ton(pool, lt.bio1, room) == 10
    assert (await _dong_luot(pool, lt.a))["trang_thai"] == DA_HOAN
    assert not await _lech(pool)


# ── Mục 4: chỉ định đổi trạng thái sau khi đã trừ ───────────────────────────
async def test_chi_dinh_xep_phong_sau_khi_thu_chuyen_cho_tru(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    """Thu trước, khối Hành trình xếp phòng sau: phòng bác sĩ → phòng chỉ định."""
    lt = await _luot(pool, ca)
    p_bs, p_cd = await _phong(pool, ca.loc), await _phong(pool, ca.loc)
    await _lich_bac_si(pool, ca.bac_si.staff_id, p_bs)
    await _nhap(pool, ca.thu_ngan, lt.bio1, p_bs)
    await _nhap(pool, ca.thu_ngan, lt.bio1, p_cd)
    await _chi_dinh_o(pool, lt.a, None)
    await _bio(pool, lt, lt.a, lt.bio1)
    await _thu(pool, lt)
    assert await _ton(pool, lt.bio1, p_bs) == 9
    assert (await _dong_luot(pool, lt.a))["noi_nguon"] == "BAC_SI"

    await _chi_dinh_o(pool, lt.a, p_cd)
    async with pool.acquire() as conn, conn.transaction():
        await ban.dong_bo_ban_vat_tu(
            conn, ca.thu_ngan, lt.visit, ly_do="Chỉ định đổi phòng"
        )
    assert await _ton(pool, lt.bio1, p_bs) == 10
    assert await _ton(pool, lt.bio1, p_cd) == 9
    assert (await _dong_luot(pool, lt.a))["noi_nguon"] == "CHI_DINH"
    assert not await _lech(pool)


async def test_nguoi_kho_gan_roi_chi_dinh_doi_phong_khong_keo_di(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca)
    p2 = await _phong(pool, ca.loc)
    await _thu(pool, lt)
    b = await _dong_luot(pool, lt.a)
    await ban.gan_noi_lay(
        pool, identity=ca.thu_ngan, ban_id=str(b["id"]), room_id=room, ly_do="Xác nhận"
    )
    await _chi_dinh_o(pool, lt.a, p2)
    async with pool.acquire() as conn, conn.transaction():
        await ban.dong_bo_ban_vat_tu(conn, ca.thu_ngan, lt.visit)
    assert await _ton(pool, lt.bio1, room) == 9 and await _ton(pool, lt.bio1, p2) == 0


async def test_huy_chi_dinh_sau_thu_so_ve_dong_con_khoi_phuc_thi_tru_lai(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca)
    await _thu(pool, lt)
    assert await _ton(pool, lt.bio1, room) == 9
    await _huy_chi_dinh(pool, lt, lt.a)
    await chay_ben_nhan(pool, VAT_TU_BAN)
    assert await _ton(pool, lt.bio1, room) == 10
    b = await _dong_luot(pool, lt.a)
    assert b["trang_thai"] == DA_HOAN and "Bỏ chỉ định" in str(b["ly_do"])
    assert b["thanh_tien"] == 300_000  # tiền còn đó, quầy hoàn

    await _khoi_phuc(pool, lt, lt.a)
    await chay_ben_nhan(pool, HANH_TRINH, VAT_TU_BAN)
    # Khôi phục → khối Hành trình xếp lại phòng: trừ theo phòng chỉ định hiện tại.
    b = await _dong_luot(pool, lt.a)
    assert b["trang_thai"] == DA_TRU and b["noi_nguon"] == "CHI_DINH"
    moi = str(b["room_id"])
    tru = await _ton(pool, lt.bio1, moi)
    # Sự kiện giao lần nữa (relay chạy hai lần): không trừ hai lần.
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute(
            "SELECT 1 FROM visit WHERE visit_id = $1::uuid FOR UPDATE", lt.visit
        )
        await ban.dong_bo_ban_vat_tu(conn, ca.thu_ngan, lt.visit)
    assert await _ton(pool, lt.bio1, moi) == tru
    assert (await _dong_luot(pool, lt.a))["so_phieu"] == b["so_phieu"]
    assert not await _lech(pool)


async def test_khach_khong_lam_sau_thu_so_ve(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca, xep_that=True)
    await _thu(pool, lt)
    assert await _ton(pool, lt.bio1, room) == 9
    d = await _don(pool, lt.a)
    await ServiceExecutionService(pool).khong_lam(
        order_id=lt.a,
        expected_execution_revision=int(d["execution_revision"]),
        ly_do="PATIENT_DECLINED_AT_ROOM",
        ghi_chu=None,
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    await chay_ben_nhan(pool, VAT_TU_BAN)
    assert await _ton(pool, lt.bio1, room) == 10
    b = await _dong_luot(pool, lt.a)
    assert b["trang_thai"] == DA_HOAN and "không làm" in str(b["ly_do"])


# ── Mục 5: nơi lấy không đoán bừa ───────────────────────────────────────────
@pytest.mark.parametrize("kieu", ["tat", "co_so_khac", "doi_tac"])
async def test_phong_chi_dinh_khong_dung_duoc_ve_cho_gan(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    kieu: str,
) -> None:
    lt = await _luot(pool, ca)
    loc = ca.loc
    if kieu == "co_so_khac":
        loc = str(
            await pool.fetchval(
                "INSERT INTO clinic_location (clinic_id, code, name)"
                " VALUES ($1::uuid, $2, 'Cơ sở thử') RETURNING id::text",
                CLINIC,
                f"T{uuid.uuid4().hex[:6]}",
            )
        )
    room = await _phong(pool, loc, active=kieu != "tat", doi_tac=kieu == "doi_tac")
    # Bác sĩ có phòng hẳn hoi nhưng chỉ định đã nói phòng khác: không suy tiếp.
    p_bs = await _phong(pool, ca.loc)
    await _lich_bac_si(pool, ca.bac_si.staff_id, p_bs)
    await _chi_dinh_o(pool, lt.a, room)
    await _bio(pool, lt, lt.a, lt.bio1)
    await _thu(pool, lt)
    assert (await _dong_luot(pool, lt.a))["trang_thai"] == CHO_GAN_PHONG
    assert await _ton(pool, lt.bio1, room) == 0
    assert await _ton(pool, lt.bio1, p_bs) == 0


async def test_khong_bac_si_hoac_nhieu_bac_si_ve_cho_gan(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt = await _luot(pool, ca)
    p_bs = await _phong(pool, ca.loc)
    await _lich_bac_si(pool, ca.bac_si.staff_id, p_bs)
    bs2 = await pool.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ('BS hai', 'DOCTOR', $1::uuid, true) RETURNING id",
        ca.loc,
    )
    await pool.execute(
        "INSERT INTO consultation (clinic_id, visit_id, round_no, kind, status,"
        " doctor_staff_id) VALUES ($1::uuid, $2::uuid, 9, 'REVIEW', 'queued', $3)",
        CLINIC,
        lt.visit,
        bs2,
    )
    await _chi_dinh_o(pool, lt.a, None)
    await _bio(pool, lt, lt.a, lt.bio1)
    await _thu(pool, lt)
    assert (await _dong_luot(pool, lt.a))["trang_thai"] == CHO_GAN_PHONG


async def test_dong_quay_nhieu_chi_dinh_khac_phong_lay_phong_bac_si(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt = await _luot(pool, ca)
    p1, p2, p_bs = [await _phong(pool, ca.loc) for _ in range(3)]
    await _chi_dinh_o(pool, lt.a, p1)
    await _chi_dinh_o(pool, lt.b, p2)
    await _lich_bac_si(pool, ca.bac_si.staff_id, p_bs)
    await VatTuService(pool).them(
        visit_id=lt.visit, service_price_id=lt.bio1, identity=ca.thu_ngan
    )
    await _thu(pool, lt)
    assert await _ton(pool, lt.bio1, p_bs) == -1
    assert await _ton(pool, lt.bio1, p1) == 0 and await _ton(pool, lt.bio1, p2) == 0


# ── Mục 6: đếm đã chốt ──────────────────────────────────────────────────────
async def test_doi_phong_va_hoan_tac_sau_kiem_dem_giu_so_dem_lich_su(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca, so_luong=2)

    async def dem(so: int) -> None:
        await kho.tao_phieu(
            pool,
            identity=ca.thu_ngan,
            khoa_gui=_khoa(),
            loai="KIEM",
            dong=[{"vat_tu_id": lt.bio1, "tu_room_id": room, "so_luong": so}],
        )

    await dem(10)
    await _thu(pool, lt)  # sổ 8
    await dem(7)  # đếm 7: bán 2, dùng/thất thoát 1
    bao = await tieu_hao.doc_tieu_hao(pool, identity=ca.thu_ngan)
    d = next(x for x in bao["items"] if x["vat_tu_id"] == lt.bio1)
    assert d["tieu_hao"] == 3 and d["da_ban"] == 2 and d["dung_khong_ban"] == 1
    assert d["da_dung"] == 3 and d["trong_do_huy"] == 0

    # Hoàn tác SAU lần đếm: mốc đếm không đổi; phần đảo thuộc kỳ sau.
    await _huy_phieu(pool, lt)
    bao = await tieu_hao.doc_tieu_hao(pool, identity=ca.thu_ngan)
    d = next(x for x in bao["items"] if x["vat_tu_id"] == lt.bio1)
    assert d["cuoi"] == 7 and d["tieu_hao"] == 3 and d["da_ban"] == 2
    so_dem = await pool.fetch(
        "SELECT x.thuc_te FROM vat_tu_txn x JOIN vat_tu_phieu p ON p.id = x.phieu_id"
        " WHERE x.vat_tu_id = $1::uuid AND x.thuc_te IS NOT NULL ORDER BY p.tao_luc",
        lt.bio1,
    )
    assert [r["thuc_te"] for r in so_dem] == [10, 7]
    await dem(9)
    bao = await tieu_hao.doc_tieu_hao(pool, identity=ca.thu_ngan)
    d = next(x for x in bao["items"] if x["vat_tu_id"] == lt.bio1)
    # Hai lần đếm 10 → 9, bán ròng 0: công thức giữ nguyên, số âm không giả.
    assert d["tieu_hao"] == 1 and d["da_ban"] == 0 and d["dung_khong_ban"] == 1
    assert not await _lech(pool)


async def test_doi_phong_sau_kiem_dem_moi_phong_tinh_dung_khong_doi_so_dem(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, p1 = await _mot_bio(pool, ca, so_luong=2)
    p2 = await _phong(pool, ca.loc)
    await _nhap(pool, ca.thu_ngan, lt.bio1, p2)

    async def dem(room: str, so: int) -> None:
        await kho.tao_phieu(
            pool,
            identity=ca.thu_ngan,
            khoa_gui=_khoa(),
            loai="KIEM",
            dong=[{"vat_tu_id": lt.bio1, "tu_room_id": room, "so_luong": so}],
        )

    await dem(p1, 10)
    await dem(p2, 10)
    await _thu(pool, lt)
    await dem(p1, 8)
    # Gán sang p2 SAU khi p1 đã chốt đếm: đảo ở p1 thuộc kỳ sau, p2 trừ thật.
    b = await _dong_luot(pool, lt.a)
    await ban.gan_noi_lay(
        pool,
        identity=ca.thu_ngan,
        ban_id=str(b["id"]),
        room_id=p2,
        ly_do="Thật ra lấy ở phòng 2",
    )
    await dem(p2, 8)

    def dong(bao: dict[str, Any], room: str) -> dict[str, Any]:
        return next(
            x
            for x in bao["items"]
            if x["vat_tu_id"] == lt.bio1 and x["room_id"] == room
        )

    bao = await tieu_hao.doc_tieu_hao(pool, identity=ca.thu_ngan)
    d1, d2 = dong(bao, p1), dong(bao, p2)
    assert d1["cuoi"] == 8 and d1["tieu_hao"] == 2 and d1["da_ban"] == 2
    assert d2["cuoi"] == 8 and d2["tieu_hao"] == 2 and d2["da_ban"] == 2
    assert d2["dung_khong_ban"] == 0
    # Sổ p1 cao hơn số đếm 2 đúng bằng phần vừa đảo: lần đếm sau mới phản ánh.
    assert await _ton(pool, lt.bio1, p1) == 10 and await _ton(pool, lt.bio1, p2) == 8
    assert not await _lech(pool)


async def test_bio_chua_thu_sang_chi_dinh_moi_van_mot_dong_dung_so(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    """Chỉ định đã làm (Bio đã trừ, chưa thu) bị bỏ rồi đặt lại thành chỉ định MỚI
    (`chuyen_bio_chua_thu`): dòng bán theo `luot_vat_tu`, không theo chỉ định cũ."""
    lt, room = await _mot_bio(pool, ca, xep_that=True)
    d = await _don(pool, lt.a)
    await ServiceExecutionService(pool).bat_dau(
        order_id=lt.a,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    await chay_ben_nhan(pool, VAT_TU_BAN)
    assert await _ton(pool, lt.bio1, room) == 9
    b = await _dong_luot(pool, lt.a)
    moi = await pool.fetchval(
        "INSERT INTO service_order (clinic_id, visit_id, consultation_id, service_code,"
        " service_name, node_code, exec_status, recorded_by, authorized_by,"
        " authorized_at, selection_status)"
        " SELECT clinic_id, visit_id, consultation_id, service_code || '-moi',"
        " service_name, node_code, 'authorized', recorded_by, authorized_by, now(),"
        " 'SELECTED' FROM service_order WHERE id = $1::uuid RETURNING id::text",
        lt.b,
    )
    async with pool.acquire() as conn, conn.transaction():
        await chuyen_bio_chua_thu(conn, CLINIC, lt.a, moi)
        await ban.dong_bo_ban_vat_tu(conn, ca.thu_ngan, lt.visit)
    # Chỉ định mới chưa làm, dòng chưa thu: chưa có gì để trừ.
    assert await _ton(pool, lt.bio1, room) == 10
    assert (
        await pool.fetchval("SELECT trang_thai FROM vat_tu_ban WHERE id = $1", b["id"])
        == DA_HOAN
    )
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM vat_tu_ban WHERE luot_vat_tu_id = $1",
            b["luot_vat_tu_id"],
        )
        == 1
    )
    assert not await _lech(pool)


# ── Mục 8: giá vốn, doanh thu ───────────────────────────────────────────────
async def test_gia_von_lay_lan_nhap_gan_nhat_khong_dung_doanh_thu(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca)
    await _nhap(pool, ca.thu_ngan, lt.bio1, room, 1, gia=80_000)
    async with pool.acquire() as conn:
        hd = await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=lt.visit, kind="dich_vu"
        )
    await _thu(pool, lt)
    b = await _dong_luot(pool, lt.a)
    assert b["gia_von"] == 80_000
    tong = await pool.fetchval(
        "SELECT sum(line_total) FROM payment_bill_line WHERE visit_id = $1::uuid",
        lt.visit,
    )
    assert tong == hd.tong  # bán vật tư không thêm dòng tiền nào


# ── Mục 9: không trùng, ép ở Postgres ───────────────────────────────────────
async def test_postgres_chan_dong_trung_va_phieu_ban_thu_hai(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, _room = await _mot_bio(pool, ca)
    await _thu(pool, lt)
    b = await _dong_luot(pool, lt.a)
    with pytest.raises(asyncpg.UniqueViolationError):
        await pool.execute(
            "INSERT INTO vat_tu_ban (clinic_id, location_id, nguon, luot_vat_tu_id,"
            " clinic_patient_id, vat_tu_id, ten, so_luong, ban_boi, trang_thai)"
            " SELECT clinic_id, location_id, nguon, luot_vat_tu_id, clinic_patient_id,"
            " vat_tu_id, ten, so_luong, ban_boi, 'CHO_GAN_PHONG'"
            " FROM vat_tu_ban WHERE id = $1",
            b["id"],
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "INSERT INTO vat_tu_phieu (clinic_id, location_id, ma_phieu, loai,"
            " khoa_gui, tao_boi, ban_id)"
            " VALUES ($1::uuid, $2::uuid, $3, 'BAN', $3, $4::uuid, $5)",
            CLINIC,
            b["location_id"],
            f"X-{uuid.uuid4().hex[:8]}",
            ca.thu_ngan.staff_id,
            b["id"],
        )


async def test_dong_bo_chay_dong_thoi_chi_tru_mot_lan(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca)
    lan = await _thu(pool, lt)

    async def lam() -> None:
        async with pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "SELECT 1 FROM visit WHERE visit_id = $1::uuid FOR UPDATE", lt.visit
            )
            await ban.dong_bo_ban_vat_tu(conn, ca.thu_ngan, lt.visit, lan_thu=lan)

    await asyncio.gather(*(lam() for _ in range(6)))
    assert await _ton(pool, lt.bio1, room) == 9
    assert not await _lech(pool)


# ── Quầy thuốc + mục 10: mã chung, đa cơ sở ─────────────────────────────────
async def _hang_quay_thuoc(
    q: Quay, *, ma: str | None, ma_vt: str | None = None, so: int = 1
) -> tuple[str, str]:
    """(thuốc, dòng đơn) — thuốc có `ma_hang`, vật tư trùng mã nếu `ma_vt`."""
    thuoc = str(
        await q.pool.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_base, name_raw, unit_price,"
            " ma_hang, don_vi_ban) VALUES ($1::uuid, $2, $2, 300000, $3, 'cái')"
            " RETURNING id::text",
            CLINIC,
            f"Đầu dò {uuid.uuid4().hex[:6]}",
            ma,
        )
    )
    rx = str(
        await q.pool.fetchval(
            "INSERT INTO prescription (clinic_id, source_ref, visit_id,"
            " clinic_patient_id, drug_name_raw, quantity, quantity_num, unit,"
            " drug_catalog_id, drug_mapped_by, drug_mapped_at, nguon)"
            " SELECT $1::uuid, $2, v.visit_id, v.clinic_patient_id, 'Đầu dò', $3, $4,"
            " 'cái', $5::uuid, $6::uuid, now(), 'QUAY' FROM visit v"
            " WHERE v.visit_id = $7::uuid RETURNING id::text",
            CLINIC,
            f"test-rx-{uuid.uuid4().hex}",
            f"{so} cái",
            so,
            thuoc,
            q.bac_si.staff_id,
            q.visit_id,
        )
    )
    return thuoc, rx


async def _vt_ma(pool: asyncpg.Pool, ma: str) -> str:  # noqa: F811
    vt = await _vat_tu(pool, "Đầu dò trùng mã", 300_000)
    await pool.execute(
        "UPDATE service_price SET ma_kiotviet = $2 WHERE id = $1::uuid", vt, ma
    )
    return vt


async def _thu_thuoc(q: Quay) -> str:
    async with q.pool.acquire() as conn:
        hd = await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=q.visit_id, kind="thuoc"
        )
    kq = await PaymentService(q.pool).record_payment(
        visit_id=q.visit_id,
        kind="thuoc",
        amount=None,
        clinic_patient_id=None,
        identity=q.thu_ngan,
        bill_revision=hd.revision,
        method="CASH",
        quay="thuoc",
    )
    return str(kq["payment_cycle_id"])


async def test_quay_thuoc_ban_tru_kho_vat_tu_giao_khong_vao_cho_gan_lo(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    q = await tao_quay(pool)
    ma = f"SP{uuid.uuid4().hex[:8]}"
    vt = await _vt_ma(pool, ma)
    loc = q.thu_ngan.location_id
    room = await _phong(pool, loc)
    await _nhap(pool, q.thu_ngan, vt, room)
    await _lich_bac_si(pool, q.bac_si.staff_id, room)
    thuoc, rx = await _hang_quay_thuoc(q, ma=ma, so=2)

    lan = await _thu_thuoc(q)
    assert await _ton(pool, vt, room) == 8
    b = await pool.fetchrow(
        "SELECT * FROM vat_tu_ban WHERE prescription_id = $1::uuid", rx
    )
    assert b["nguon"] == "QUAY_THUOC" and b["trang_thai"] == DA_TRU
    assert b["noi_nguon"] == "BAC_SI" and b["thanh_tien"] == 600_000
    # Doanh thu vẫn là tiền thuốc.
    assert (
        await pool.fetchval(
            "SELECT kind FROM payment_cycle WHERE payment_cycle_id = $1::uuid", lan
        )
        == "thuoc"
    )

    man_hinh = await man_nha_thuoc(pool, identity=q.duoc_si)
    dong = next(d for g in man_hinh["luot"] for d in g["dong"] if d["id"] == rx)
    assert dong["la_vat_tu"] and not dong["thao_tac"]["chon_lo"]
    assert dong["thao_tac"]["giao_khong_lo"]

    kq = await PharmacyService(pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=None, so_luong=2
    )
    assert "không cần gán lô" in str(kq["tom_tat"])
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM thuoc_giao_chua_gan_lo"
            " WHERE prescription_id = $1::uuid",
            rx,
        )
        == 0
    )
    assert await _ton(pool, vt, room) == 8  # giao không trừ lần hai

    # Hoàn tiền kèm khách trả ở quầy thuốc: số về đúng phòng.
    line = await pool.fetchval(
        "SELECT id::text FROM payment_bill_line WHERE source_type = 'prescription'"
        " AND source_id = $1",
        rx,
    )
    await HoanTienService(pool).tao(
        identity=q.thu_ngan,
        payment_cycle_id=lan,
        visit_id=q.visit_id,
        kind="thuoc",
        dong=[{"payment_bill_line_id": line, "so_luong": 1, "tra_hang": True}],
        method="CASH",
        reason="Khách trả đầu dò",
    )
    assert await _ton(pool, vt, room) == 9
    # Hoàn tác lần thu: số về nốt; thu lại trừ lại.
    await PaymentService(pool).void_payment(
        payment_cycle_id=lan,
        visit_id=q.visit_id,
        kind="thuoc",
        reason="Thu nhầm, huỷ phiếu",
        identity=q.thu_ngan,
    )
    assert await _ton(pool, vt, room) == 10
    assert not await _lech(pool)


@pytest.mark.parametrize("kieu", ["rong", "khong_co", "ma_ben_dich_vu"])
async def test_ma_khong_ro_giu_nhu_thuoc_thuong(
    pool: asyncpg.Pool,  # noqa: F811
    kieu: str,
) -> None:
    q = await tao_quay(pool)
    ma = f"SP{uuid.uuid4().hex[:8]}"
    ma_thuoc: str | None = ma
    if kieu == "rong":
        await _vt_ma(pool, f"SP{uuid.uuid4().hex[:8]}")
        ma_thuoc = "  "
    if kieu == "ma_ben_dich_vu":
        # `uq_service_price_ma_kiotviet` đã cấm trùng mã; mã thuộc nhóm dịch vụ
        # thì không phải vật tư.
        vt = await _vt_ma(pool, ma)
        await pool.execute(
            "UPDATE service_price SET \"group\" = 'dich_vu' WHERE id = $1::uuid", vt
        )
    thuoc, rx = await _hang_quay_thuoc(q, ma=ma_thuoc)
    async with pool.acquire() as conn:
        assert not await thuoc_la_vat_tu(conn, CLINIC, [thuoc])
    await _thu_thuoc(q)
    assert not await pool.fetchval(
        "SELECT count(*) FROM vat_tu_ban WHERE prescription_id = $1::uuid", rx
    )
    await PharmacyService(pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=None, so_luong=1
    )
    assert await pool.fetchval(
        "SELECT count(*) FROM thuoc_giao_chua_gan_lo WHERE prescription_id = $1::uuid",
        rx,
    )


async def test_moi_co_so_mot_so(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, room = await _mot_bio(pool, ca)
    await _thu(pool, lt)
    loc2 = str(
        await pool.fetchval(
            "INSERT INTO clinic_location (clinic_id, code, name)"
            " VALUES ($1::uuid, $2, 'Kim Ngưu thử') RETURNING id::text",
            CLINIC,
            f"K{uuid.uuid4().hex[:6]}",
        )
    )
    kn = replace(ca.thu_ngan, location_id=loc2)
    b = await _dong_luot(pool, lt.a)
    assert b["location_id"] == uuid.UUID(ca.loc)
    assert (await ban.doc_ban(pool, identity=kn))["items"] == []
    with pytest.raises(NotFoundError):
        await ban.gan_noi_lay(
            pool, identity=kn, ban_id=str(b["id"]), room_id=None, ly_do="Sai cơ sở"
        )
    # Người bấm ở cơ sở khác hoàn tác: số vẫn về đúng sổ của cơ sở lượt.
    await PaymentService(pool).void_payment(
        payment_cycle_id=await _lan_thu(pool, lt),
        visit_id=lt.visit,
        kind="dich_vu",
        reason="Thu nhầm, huỷ phiếu",
        identity=replace(ca.thu_ngan, location_id=loc2),
    )
    assert await _ton(pool, lt.bio1, room, ca.loc) == 10


# ── Mục 11: dữ liệu cũ ──────────────────────────────────────────────────────
async def test_dong_truoc_khi_len_khong_tru_nguoc(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lt, room = await _mot_bio(pool, ca)

    # Khoản bán TRƯỚC lúc lên: bản cũ thu mà không có móc, và dòng là của trước
    # migration (tru_kho = false).
    async def khong_moc(*_a: Any, **_k: Any) -> None:
        return None

    with monkeypatch.context() as m:
        m.setattr("clinicai.services.payment_service.dong_bo_ban_vat_tu", khong_moc)
        await _thu(pool, lt)
    v = await pool.fetchval(
        "UPDATE luot_vat_tu SET tru_kho = false WHERE order_id = $1::uuid"
        " RETURNING id::text",
        lt.a,
    )
    await pool.execute(
        "UPDATE service_order SET execution_status = 'IN_PROGRESS' WHERE id = $1::uuid",
        lt.a,
    )
    # Đồng bộ, hoàn tiền, hoàn tác sau khi lên: không sinh dòng, không trừ.
    async with pool.acquire() as conn, conn.transaction():
        await ban.dong_bo_ban_vat_tu(conn, ca.thu_ngan, lt.visit)
    await _hoan(pool, lt, await _dong_hoa_don(pool, v), 1)
    assert await _ton(pool, lt.bio1, room) == 10
    assert not await pool.fetchval(
        "SELECT count(*) FROM vat_tu_ban WHERE visit_id = $1::uuid", lt.visit
    )


async def test_migration_khong_doi_so_ton_dong_moi_duoc_tru(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    lt, _room = await _mot_bio(pool, ca)
    assert await pool.fetchval(
        "SELECT tru_kho FROM luot_vat_tu WHERE order_id = $1::uuid", lt.a
    )


# ── Mục 12: quyền ───────────────────────────────────────────────────────────
async def test_nguoi_chi_co_quyen_thu_van_ban_duoc(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
) -> None:
    thu = await _nguoi_khoi(pool, "CASHIER_DV", ["thu_tien_dv"])
    async with pool.acquire() as conn:
        assert not await can(conn, thu, "vat_tu.manage")
    lt, room = await _mot_bio(pool, ca)
    lt.ca = replace(ca, thu_ngan=thu)
    await _thu(pool, lt)
    assert await _ton(pool, lt.bio1, room) == 9
    assert (await _dong_luot(pool, lt.a))["ban_boi"] == uuid.UUID(thu.staff_id)
    # Tab Bán cho khách vẫn gác theo lego Kho vật tư.
    with pytest.raises(SafetyGateError):
        await cua_quyen("vat_tu.manage")(identity=thu, pool=pool)


# ── Bấm ngẫu nhiên ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("hat", [11, 23, 37])
async def test_bam_ngau_nhien_giu_bat_bien(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    hat: int,
) -> None:
    r = random.Random(hat)
    lt, room = await _mot_bio(pool, ca, so_luong=2)
    p2 = await _phong(pool, ca.loc)
    b_id: list[str] = []

    async def thu() -> None:
        await _thu(pool, lt)

    async def hoan_tac() -> None:
        await _huy_phieu(pool, lt)

    async def huy() -> None:
        await _huy_chi_dinh(pool, lt, lt.a)

    async def khoi_phuc() -> None:
        await _khoi_phuc(pool, lt, lt.a)

    async def gan() -> None:
        v = await pool.fetchrow(
            "SELECT b.id FROM vat_tu_ban b WHERE b.visit_id = $1::uuid", lt.visit
        )
        if v:
            b_id[:] = [str(v["id"])]
            await ban.gan_noi_lay(
                pool,
                identity=ca.thu_ngan,
                ban_id=str(v["id"]),
                room_id=r.choice([room, p2, None]),
                ly_do="Bấm ngẫu nhiên",
            )

    async def nhan() -> None:
        if b_id:
            await ban.nhan_lai_hang(
                pool,
                identity=ca.thu_ngan,
                ban_id=b_id[0],
                so_luong=1,
                ly_do="Bấm ngẫu nhiên",
            )

    viec = [thu, hoan_tac, huy, khoi_phuc, gan, nhan]
    for _ in range(40):
        try:
            await r.choice(viec)()
        except (ConflictError, ValidationError, AssertionError, NotFoundError):
            pass
        if r.random() < 0.5:
            await chay_ben_nhan(pool, HANH_TRINH, VAT_TU_BAN)
        assert not await _lech(pool)
    await chay_ben_nhan(pool, HANH_TRINH, VAT_TU_BAN)
    assert not await _lech(pool)
    assert not await pool.fetchval(
        "SELECT count(*) FROM event_delivery WHERE consumer = $1"
        " AND status IN ('RETRY', 'DEAD')",
        VAT_TU_BAN,
    )
