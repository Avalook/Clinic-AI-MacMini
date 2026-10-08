"""Đổi cơ sở thì màn vận hành chỉ hiện việc của cơ sở ấy — nhóm B (08/10/2026).

Tuyền: "sang cơ sở khác là của cơ sở đó hết, đừng sót". Nhóm B = quầy thu
(bảng thu, sổ giao dịch, sổ gom theo khách, số đếm tab "Đã thu"), check-out
(chờ đóng lượt, lượt treo), nhà thuốc (màn quầy, bán lẻ, hàng đợi, lịch sử
giao, chờ tư vấn, chờ gán lô) và bàn đối tác. Mỗi cơ sở có một lượt đã thu
dịch vụ + thuốc, đã giao thuốc không lô; danh tính mỗi cơ sở chỉ thấy của mình.
Tài khoản ĐỐI TÁC ngoài (vai PARTNER) nhận mẫu cả hai cơ sở — không lọc.
"""

# ruff: noqa: F811 — fixture `pool` đến từ pytest_plugins.

from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass
from typing import Any

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.services import ban_thuoc_service as bt
from clinicai.services.ban_le_service import BanLeService
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.doi_tac_service import DoiTacService
from clinicai.services.pharmacy_service import PharmacyService
from clinicai.services.quay_thu_service import QuayThuService
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai, _viec_da_nhan
from tests.services.test_lay_mau_doi_tac_db import _nhan_su_doi_tac
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, _thu_kham, tao_quay
from tests.services.test_tien_thuoc_cp3_db import _dong_da_xac_dinh
from tests.services.test_tien_thuoc_cp3_db import _thu as _thu_thuoc

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _tat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    # Chế độ đang chạy trên prod: thu tiền thuốc không chờ kho → giao không lô.
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


@dataclass
class CoSo:
    quay: Quay
    loc: str
    rx: str
    ban_le: str


def _o(identity: StaffIdentity, loc: str) -> StaffIdentity:
    return dataclasses.replace(identity, location_id=loc, location_name="Hào Nam")


async def _co_so_hn(pool: asyncpg.Pool) -> str:
    """Cơ sở thứ hai, is_active = false: DB test dùng chung trong một lượt chạy —
    cơ sở đang mở thứ hai đổi hành vi tự gán cơ sở của các bài khác."""
    return str(
        await pool.fetchval(
            "INSERT INTO clinic_location (clinic_id, code, name, is_active)"
            " VALUES ($1::uuid, $2, 'Hào Nam thử', false) RETURNING id::text",
            CLINIC,
            f"HN{uuid.uuid4().hex[:6]}",
        )
    )


async def _chuyen_co_so(q: Quay, loc: str) -> Quay:
    """Lượt (+ lịch hẹn) sang cơ sở ``loc``; người đứng quầy cũng ở đó."""
    await q.pool.execute(
        "UPDATE appointment SET location_id = $2::uuid WHERE id ="
        " (SELECT appointment_id FROM visit WHERE visit_id = $1::uuid)",
        q.visit_id,
        loc,
    )
    await q.pool.execute(
        "UPDATE visit SET location_id = $2::uuid WHERE visit_id = $1::uuid",
        q.visit_id,
        loc,
    )
    return dataclasses.replace(
        q,
        thu_ngan=_o(q.thu_ngan, loc),
        duoc_si=_o(q.duoc_si, loc),
        bac_si=_o(q.bac_si, loc),
    )


async def _lam_viec(q: Quay, loc: str) -> CoSo:
    """Thu dịch vụ + thuốc, giao 4/10 viên không lô, mở một lượt bán lẻ."""
    await _thu_kham(q)
    rx, _drug = await _dong_da_xac_dinh(q, 10)
    await _thu_thuoc(q)
    await PharmacyService(q.pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=None, so_luong=4
    )
    pid = await q.pool.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, 'Khách mua thuốc', $3::uuid)"
        " RETURNING clinic_patient_id::text",
        CLINIC,
        f"BL-{uuid.uuid4().hex[:8]}",
        loc,
    )
    kq = await BanLeService(q.pool).mo_luot(identity=q.duoc_si, clinic_patient_id=pid)
    return CoSo(q, loc, rx, str(kq["visit_id"]))


async def _hai_co_so(pool: asyncpg.Pool) -> tuple[CoSo, CoSo]:
    kn_q = await tao_quay(pool)
    hn_q = await _chuyen_co_so(await tao_quay(pool), await _co_so_hn(pool))
    kn = await _lam_viec(kn_q, kn_q.thu_ngan.location_id)
    hn = await _lam_viec(hn_q, hn_q.thu_ngan.location_id)
    return kn, hn


def _cap(kn: CoSo, hn: CoSo) -> list[tuple[CoSo, CoSo]]:
    return [(kn, hn), (hn, kn)]


async def test_quay_thu_chi_thay_cua_co_so_minh(pool: asyncpg.Pool) -> None:
    kn, hn = await _hai_co_so(pool)
    svc = CashierBoardService(pool)
    for minh, khac in _cap(kn, hn):
        nv = minh.quay.thu_ngan
        bang = await svc.board(identity=nv, modes=["dich_vu", "thuoc"])
        luot = {i["visit_id"] for i in bang["items"]}
        assert minh.quay.visit_id in luot
        assert khac.quay.visit_id not in luot

        gd = {
            g["visit_id"]
            for g in (await svc.giao_dich(identity=nv, tu=None, den=None))["giao_dich"]
        }
        assert minh.quay.visit_id in gd
        assert khac.quay.visit_id not in gd

        for loai in ("dich_vu", "thuoc"):
            so = await QuayThuService(pool).lich_su(identity=nv, kind=loai)
            khach = {g["visit_id"] for g in so["khach"]}
            assert minh.quay.visit_id in khach, loai
            assert khac.quay.visit_id not in khach, loai
            if loai == "dich_vu":
                # Số trên tab "Đã thu" khớp đúng danh sách của cơ sở ấy.
                assert bang["dem"]["da_thu_hom_nay"] == len(so["khach"])

    # Cơ sở HN mới dựng: đúng một khách đã thu.
    bang_hn = await svc.board(identity=hn.quay.thu_ngan, modes=["dich_vu"])
    assert bang_hn["dem"]["da_thu_hom_nay"] == 1


async def test_check_out_chi_thay_luot_cua_co_so_minh(pool: asyncpg.Pool) -> None:
    kn, hn = await _hai_co_so(pool)
    svc = CheckoutService(pool)
    for minh, khac in _cap(kn, hn):
        cho = {
            r["visit_id"] for r in await svc.pending_list(identity=minh.quay.thu_ngan)
        }
        assert minh.quay.visit_id in cho
        assert khac.quay.visit_id not in cho

    # Lượt treo: check-in từ hôm trước, chưa đóng.
    await pool.execute(
        "UPDATE visit SET checked_in_at = now() - interval '2 days'"
        " WHERE visit_id = ANY($1::uuid[])",
        [kn.quay.visit_id, hn.quay.visit_id],
    )
    for minh, khac in _cap(kn, hn):
        treo = {
            r["visit_id"] for r in await svc.stale_list(identity=minh.quay.thu_ngan)
        }
        assert minh.quay.visit_id in treo
        assert khac.quay.visit_id not in treo


def _ids(rows: list[dict[str, Any]], khoa: str) -> set[str]:
    return {str(r[khoa]) for r in rows}


async def test_nha_thuoc_chi_thay_don_cua_co_so_minh(pool: asyncpg.Pool) -> None:
    kn, hn = await _hai_co_so(pool)
    svc = PharmacyService(pool)
    for minh, khac in _cap(kn, hn):
        ds = minh.quay.duoc_si
        man = await bt.man_nha_thuoc(pool, identity=ds)
        luot = {g["visit_id"] for g in man["luot"]}
        assert {minh.quay.visit_id, minh.ban_le} <= luot
        assert not ({khac.quay.visit_id, khac.ban_le} & luot)

        assert minh.rx in _ids(await svc.hang_doi(identity=ds), "id")
        assert khac.rx not in _ids(await svc.hang_doi(identity=ds), "id")
        assert minh.rx in _ids(await svc.cho_tu_van(identity=ds), "id")
        assert khac.rx not in _ids(await svc.cho_tu_van(identity=ds), "id")
        assert minh.rx in _ids(await svc.lich_su_giao(identity=ds), "id")
        assert khac.rx not in _ids(await svc.lich_su_giao(identity=ds), "id")

        gan = await svc.cho_gan_lo(identity=ds)
        rx_gan = _ids(gan["dong"], "prescription_id")
        assert minh.rx in rx_gan
        assert khac.rx not in rx_gan
        assert gan["so_dong"] == len(gan["dong"])


async def test_ban_doi_tac_nhan_vien_theo_co_so_doi_tac_ngoai_thay_ca_hai(
    pool: asyncpg.Pool,
) -> None:
    kn, hn = await _hai_co_so(pool)
    viec = {kn.loc: await _viec_da_nhan(kn.quay), hn.loc: await _viec_da_nhan(hn.quay)}
    svc = DoiTacService(pool)

    def _cd(kq: dict[str, Any]) -> set[str]:
        return {v["chi_dinh_id"] for k in kq["khach"] for v in k["viec"]}

    nv = await _nhan_su_doi_tac(kn.quay)
    for loc, khac in ((kn.loc, hn.loc), (hn.loc, kn.loc)):
        thay = _cd(await svc.viec_doi_tac(identity=_o(nv, loc)))
        assert viec[loc] in thay
        assert viec[khac] not in thay

    # Đối tác ngoài nhận mẫu cả hai cơ sở, đứng ở cơ sở nào cũng vậy.
    dt = await _nguoi_vai(kn.quay, "PARTNER")
    for loc in (kn.loc, hn.loc):
        thay = _cd(await svc.viec_doi_tac(identity=_o(dt, loc)))
        assert {viec[kn.loc], viec[hn.loc]} <= thay
