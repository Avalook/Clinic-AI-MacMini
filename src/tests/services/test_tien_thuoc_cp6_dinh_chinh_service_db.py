"""Đính chính đơn CHƯA KÝ — service + đọc đơn hiện hành (CP6 bước 4b, 20/09/2026).

Chạy trên DB thật: Lưu bệnh án quyết từng dòng theo mức dấu vết (A/B/C), đính
chính cần bác sĩ chính của lượt + lý do, Q3 ở xác minh chuyển khoản, huỷ lần
thu không chép kế hoạch lô cho dòng lịch sử, và các màn đọc chỉ thấy đơn hiện
hành (trừ chỗ cố ý đọc lịch sử).

Gồm cả các ca định danh dòng đơn trước đây chạy trên bảng tạm / kết nối giả
(test_prescription_row_identity*.py): giữ id khi đổi thứ tự, id lạ / lặp bị từ
chối, bản cũ thiếu id chỉ ghép khi không mơ hồ, lỗi thì không ghi dở dang.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1 (xem CP2).

from __future__ import annotations

import dataclasses
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import ClinicRole
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import ban_thuoc_service as bt
from clinicai.services.bill_service import tinh_hoa_don
from clinicai.services.dinh_chinh_don import CanLyDoDinhChinhError, DonDaDoiError
from clinicai.services.pharmacy_service import PharmacyService
from clinicai.services.xem_luot_service import XemLuotService
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi
from tests.services.test_tien_thuoc_cp1_db import Quay, _don, _nhap_lo, q  # noqa: F401
from tests.services.test_tien_thuoc_cp2_db import _luu_don
from tests.services.test_tien_thuoc_cp3_db import (
    _dong_da_xac_dinh,
    _huy_phieu,
    _san_sang,
    _thu,
    _xac_minh,
)
from tests.services.test_tien_thuoc_cp6_dinh_chinh_db import _thay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _bat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")


LY_DO = "Bác sĩ đổi thuốc theo khám lại"


def _i(rx: str | None, ten: str, sl: str, lieu: str | None = None) -> dict[str, Any]:
    return {"id": rx, "drug_name": ten, "quantity": sl, "dosage": lieu}


async def _dong(q: Quay, rx: str) -> asyncpg.Record:
    r = await q.pool.fetchrow(
        "SELECT id::text, drug_name_raw, quantity, dosage_instructions,"
        " drug_catalog_id, purchased_qty, removed_at, superseded_by_id::text,"
        " removal_reason, created_in_correction_id FROM prescription"
        " WHERE id = $1::uuid",
        rx,
    )
    assert r is not None
    return r


async def _hien_hanh(q: Quay) -> list[str]:
    return [
        r["id"]
        for r in await q.pool.fetch(
            "SELECT id::text FROM prescription WHERE visit_id = $1::uuid"
            " AND removed_at IS NULL ORDER BY created_at, id",
            q.visit_id,
        )
    ]


async def _phan_lo(q: Quay, rx: str) -> list[asyncpg.Record]:
    return list(
        await q.pool.fetch(
            "SELECT released_at, release_reason, payment_cycle_id"
            " FROM prescription_allocation WHERE prescription_id = $1::uuid"
            " ORDER BY created_at, id",
            rx,
        )
    )


# ══ A: dòng sạch ═════════════════════════════════════════════════════════


async def test_a_sua_tai_cho_giu_id_doi_thuoc_xoa_viec_nha_thuoc(q: Quay) -> None:
    rx, _ = await _dong_da_xac_dinh(q, 10)  # nhà thuốc đã xác định thuốc kho
    await _luu_don(q, [_i(rx, "thuoc go tay", "10 viên", "Sáng 1")])
    r = await _dong(q, rx)
    assert r["dosage_instructions"] == "Sáng 1" and r["drug_catalog_id"] is not None
    cu = r["drug_catalog_id"]
    await _luu_don(q, [_i(rx, "Thuốc khác", "6 viên", "Sáng 1")])
    r = await _dong(q, rx)
    assert (r["drug_name_raw"], r["quantity"]) == ("Thuốc khác", "6 viên")
    # Đổi thuốc: bỏ mã kho CŨ; 24/09/2026 tự gắn mã kho theo tên thuốc MỚI
    # (một kho, không còn "chưa gắn kho") — số mua vẫn xoá.
    assert r["drug_catalog_id"] is not None and r["drug_catalog_id"] != cu
    assert r["purchased_qty"] is None
    assert r["removed_at"] is None
    assert await q.pool.fetchval(
        "SELECT (quantity_num, unit) = (6::numeric, 'viên') FROM prescription"
        " WHERE id = $1::uuid",
        rx,
    )


async def test_a_bo_dong_la_xoa_cung_them_dong_khong_can_ly_do(q: Quay) -> None:
    rx = await _don(q, 10)
    await _luu_don(q, [_i(None, "Thuốc mới", "3 viên")])
    assert rx not in await _hien_hanh(q)
    assert not await q.pool.fetchval(
        "SELECT count(*) FROM prescription WHERE id = $1::uuid", rx
    )


# ══ B: chỉ có phân lô ═══════════════════════════════════════════════════


async def test_b_doi_lieu_tai_cho_giu_phan_lo(q: Quay) -> None:
    rx, _, _ = await _san_sang(q, 10, 100)
    await _luu_don(q, [_i(rx, "thuoc go tay", "10 viên", "Tối 2")])
    assert (await _dong(q, rx))["dosage_instructions"] == "Tối 2"
    assert [p["released_at"] for p in await _phan_lo(q, rx)] == [None]


async def test_b_doi_thuoc_thieu_ly_do_bi_409_khong_ghi_gi(q: Quay) -> None:
    rx, _, _ = await _san_sang(q, 10, 100)
    with pytest.raises(CanLyDoDinhChinhError, match="nhà thuốc đã chọn lô"):
        await _luu_don(q, [_i(rx, "Thuốc khác", "10 viên")])
    assert await _hien_hanh(q) == [rx]
    assert [p["released_at"] for p in await _phan_lo(q, rx)] == [None]


async def test_b_doi_thuoc_nha_lo_giu_lich_su_tao_dong_thay(q: Quay) -> None:
    rx, _, _ = await _san_sang(q, 10, 100)
    await _luu_don(q, [_i(rx, "Thuốc khác", "10 viên", "S1")], ly_do=LY_DO)
    cu = await _dong(q, rx)
    [moi] = await _hien_hanh(q)
    assert cu["superseded_by_id"] == moi and cu["removal_reason"] == LY_DO
    m = await _dong(q, moi)
    assert (m["drug_name_raw"], m["drug_catalog_id"], m["purchased_qty"]) == (
        "Thuốc khác",
        None,
        None,
    )
    pl = await _phan_lo(q, rx)
    assert len(pl) == 1 and pl[0]["released_at"] is not None
    assert pl[0]["release_reason"] == "Bác sĩ đính chính đơn"
    assert await _phan_lo(q, moi) == []  # không kế thừa phân lô


async def test_b_bo_dong_nha_lo_va_go(q: Quay) -> None:
    rx, _, lo = await _san_sang(q, 10, 100)
    kd_truoc = await q.pool.fetchval(
        "SELECT public.drug_batch_kha_dung($1::uuid, $2::uuid)", CLINIC, lo
    )
    await _luu_don(q, [], ly_do=LY_DO)
    assert await _hien_hanh(q) == []
    assert (await _dong(q, rx))["superseded_by_id"] is None
    assert (
        await q.pool.fetchval(
            "SELECT public.drug_batch_kha_dung($1::uuid, $2::uuid)", CLINIC, lo
        )
        >= kd_truoc
    )


# ══ C: đã chốt / khách không lấy (review 4a P1-A) ═══════════════════════


async def test_c_dong_khach_khong_lay_doi_lieu_la_dinh_chinh(q: Quay) -> None:
    rx, _ = await _dong_da_xac_dinh(q, 10)
    await PharmacyService(q.pool).tu_choi(
        identity=q.duoc_si, prescription_id=rx, ly_do="Khách đã có thuốc ở nhà"
    )
    with pytest.raises(CanLyDoDinhChinhError, match="chốt"):
        await _luu_don(q, [_i(rx, "thuoc go tay", "10 viên", "Tối 2")])
    await _luu_don(q, [_i(rx, "thuoc go tay", "10 viên", "Tối 2")], ly_do=LY_DO)
    cu = await _dong(q, rx)
    assert cu["removed_at"] is not None and cu["dosage_instructions"] is None


# ══ Ai được đính chính (Q4) ══════════════════════════════════════════════


async def test_bac_si_sieu_am_don_thuan_khong_dinh_chinh_duoc(q: Quay) -> None:
    # Hỏi QUYỀN (29/09/2026): bác sĩ siêu âm theo nhóm mẫu không có Khám (lego
    # Bàn khám) → không đính chính được đơn nhà thuốc đã đụng.
    rx, _, _ = await _san_sang(q, 10, 100)
    async with q.pool.acquire() as conn:
        bs_sa = await _nguoi(conn, q.bac_si.location_id, "ULTRASOUND_DOCTOR")
        await ve_goi_mau_cu(conn, bs_sa)  # gói lego cũ (mở full lego 30/09)
    with pytest.raises(SafetyGateError, match="quyền Bàn khám"):
        await _luu_don(q, [], ly_do=LY_DO, identity=bs_sa)
    assert await _hien_hanh(q) == [rx]


async def test_bac_si_khac_khong_dinh_chinh_duoc_luot_cua_nguoi_khac(q: Quay) -> None:
    # HOLD đính chính CHÉO BÁC SĨ: bác sĩ thật khác của lượt vẫn bị chặn.
    rx, _, _ = await _san_sang(q, 10, 100)
    async with q.pool.acquire() as conn:
        khac = await _nguoi(conn, q.bac_si.location_id, "DOCTOR")
    with pytest.raises(SafetyGateError, match="bác sĩ khác"):
        await _luu_don(q, [], ly_do=LY_DO, identity=khac)
    assert await _hien_hanh(q) == [rx]


async def test_bac_si_sieu_am_van_sua_duoc_dong_sach(q: Quay) -> None:
    """Q4 chỉ chặn ĐÍNH CHÍNH; dòng mức A vẫn như trước."""
    rx = await _don(q, 10)
    bs_sa = dataclasses.replace(
        q.bac_si, role=ClinicRole.ULTRASOUND_DOCTOR, vai_tai_khoan=None
    )
    await _luu_don(q, [_i(rx, "thuoc go tay", "10 viên", "S1")], identity=bs_sa)
    assert (await _dong(q, rx))["dosage_instructions"] == "S1"


# ══ Định danh dòng (chuyển từ bảng tạm / kết nối giả) ═══════════════════


async def test_dao_thu_tu_giu_id(q: Quay) -> None:
    a = await _don(q, 10, ten="A")
    b = await _don(q, 5, ten="B")
    await _luu_don(q, [_i(b, "B", "5 viên", "tối"), _i(a, "A", "10 viên", "sáng")])
    assert sorted(await _hien_hanh(q)) == sorted([a, b])
    assert (await _dong(q, a))["dosage_instructions"] == "sáng"


async def test_id_la_hoac_lap_bi_tu_choi_khong_ghi_do_dang(q: Quay) -> None:
    a = await _don(q, 10, ten="A")
    for gui in (
        [_i(a, "A", "10 viên", "x"), _i(a, "A", "10 viên", "y")],
        [_i(a, "A", "10 viên", "x"), _i(str(q.duoc_si.staff_id), "Lạ", "1 viên")],
    ):
        with pytest.raises(ValidationError):
            await _luu_don(q, gui)
    assert (await _dong(q, a))["dosage_instructions"] is None


async def test_gui_lai_id_da_dinh_chinh_bao_tai_lai(q: Quay) -> None:
    rx, _, _ = await _san_sang(q, 10, 100)
    await _luu_don(q, [_i(rx, "Thuốc khác", "10 viên")], ly_do=LY_DO)
    with pytest.raises(DonDaDoiError, match="tải lại"):
        await _luu_don(q, [_i(rx, "Thuốc khác", "10 viên")], ly_do=LY_DO)


async def test_ban_cu_thieu_id_ghep_khi_khong_mo_ho(q: Quay) -> None:
    rx, _, _ = await _san_sang(q, 10, 100)  # mức B
    await _luu_don(q, [_i(None, "thuoc go tay", "10 viên", "Sáng")])
    assert await _hien_hanh(q) == [rx]
    assert (await _dong(q, rx))["dosage_instructions"] == "Sáng"


async def test_ban_cu_thieu_id_mo_ho_voi_dong_co_dau_vet_bi_tu_choi(q: Quay) -> None:
    rx, _, _ = await _san_sang(q, 10, 100)
    await _don(q, 10)  # dòng thứ hai cùng tên + số lượng
    with pytest.raises(ValidationError, match="trùng tên"):
        await _luu_don(q, [_i(None, "thuoc go tay", "10 viên")])
    assert rx in await _hien_hanh(q)


# ══ Q3: xác minh sau đính chính; huỷ lần thu không chép kế hoạch lô ════


async def test_q3_xac_minh_sau_dinh_chinh_bang_duong_luu_benh_an(q: Quay) -> None:
    rx, _, _ = await _san_sang(q, 10, 100)
    lan = (await _thu(q, "QR"))["payment_cycle_id"]
    await _luu_don(q, [_i(rx, "Thuốc khác", "10 viên")], ly_do=LY_DO)
    kq = await _xac_minh(q, lan)
    assert kq["status"] == "PAID"
    assert sorted(kq["doi_soat_ly_do"]) == ["CHUA_GHI_BAN", "HOA_DON_DOI"]
    # Phân lô gắn lần thu của dòng lịch sử giữ nguyên (đối soát riêng).
    assert [p["payment_cycle_id"] is not None for p in await _phan_lo(q, rx)] == [True]


async def test_huy_phieu_sau_dinh_chinh_nha_han_khong_chep_ke_hoach(q: Quay) -> None:
    rx, _, _ = await _san_sang(q, 10, 100)
    lan = (await _thu(q))["payment_cycle_id"]
    await _thay(q, rx)
    await _huy_phieu(q, lan)
    pl = await _phan_lo(q, rx)
    assert pl and all(p["released_at"] is not None for p in pl)


async def test_huy_phieu_dong_hien_hanh_van_giu_ke_hoach_lo(q: Quay) -> None:
    rx, _, _ = await _san_sang(q, 10, 100)
    lan = (await _thu(q))["payment_cycle_id"]
    await _huy_phieu(q, lan)
    assert any(
        p["released_at"] is None and p["payment_cycle_id"] is None
        for p in await _phan_lo(q, rx)
    )


# ══ Nhà thuốc: dòng lịch sử chỉ còn đối soát ════════════════════════════


async def test_nha_thuoc_tu_choi_thao_tac_moi_tren_dong_lich_su(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)
    await _thay(q, rx)
    ph = PharmacyService(q.pool)
    for lenh in (
        ph.xac_dinh_thuoc(identity=q.duoc_si, prescription_id=rx, drug_catalog_id=drug),
        ph.khai_so_luong_mua(identity=q.duoc_si, prescription_id=rx, so_luong=3),
        ph.tu_choi(identity=q.duoc_si, prescription_id=rx, ly_do="Khách thôi"),
    ):
        with pytest.raises(ConflictError, match="đã được bác sĩ đính chính"):
            await lenh


async def test_man_nha_thuoc_hien_dong_lich_su_con_doi_soat(q: Quay) -> None:
    rx, _, lo = await _san_sang(q, 10, 100)
    await _thu(q)  # bán 10, chưa giao
    moi = await _thay(q, rx)
    await _nhap_lo(q, (await _dong(q, rx))["drug_catalog_id"], 5)
    man = await bt.man_nha_thuoc(q.pool, identity=q.duoc_si)
    luot = next(x for x in man["luot"] if x["visit_id"] == q.visit_id)
    theo_id = {d["id"]: d for d in luot["dong"]}
    cu = theo_id[rx]
    assert cu["lich_su"] and cu["thay_boi_id"] == moi
    assert cu["lo_goi_y"] == [] and cu["can_lo"] == 0
    assert not any(v for k, v in cu["thao_tac"].items() if k != "huy_chua_giao")
    assert all(not any(p["thao_tac"].values()) for p in cu["phan_lo"])
    assert not theo_id[moi]["lich_su"]
    assert lo  # lô cũ còn đó


async def test_man_nha_thuoc_dong_lich_su_chua_thu_khong_con_nut_nao(q: Quay) -> None:
    """Dòng mức B vừa đính chính (hiện vì gỡ hôm nay, lượt chưa thu): không
    nút xác định thuốc / chọn lô / chốt / khách không lấy nào — dù giai đoạn
    của lượt vẫn là 'Chọn lô'."""
    rx, _, _ = await _san_sang(q, 10, 100)
    await _luu_don(q, [_i(rx, "Thuốc khác", "10 viên")], ly_do=LY_DO)
    man = await bt.man_nha_thuoc(q.pool, identity=q.duoc_si)
    luot = next(x for x in man["luot"] if x["visit_id"] == q.visit_id)
    assert luot["giai_doan"] == bt.SAN_SANG
    cu = next(d for d in luot["dong"] if d["id"] == rx)
    assert cu["lich_su"] and not any(cu["thao_tac"].values())


# ══ Đọc đơn hiện hành ═══════════════════════════════════════════════════


async def test_hoa_don_moi_chi_gom_dong_hien_hanh(q: Quay) -> None:
    a = await _don(q, 10, ten="Thuốc A")
    moi = await _thay(q, a, "Thuốc B")
    async with q.pool.acquire() as conn:
        hd = await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=q.visit_id, kind="thuoc"
        )
    assert [d.source_id for d in hd.dong] == [moi]


async def test_xem_luot_hien_ca_dong_da_dinh_chinh(q: Quay) -> None:
    a = await _don(q, 10, ten="Thuốc A")
    moi = await _thay(q, a, "Thuốc B")
    async with q.pool.acquire() as conn:
        thuoc = await XemLuotService._thuoc(conn, CLINIC, q.visit_id)
    theo_id = {t["id"]: t for t in thuoc}
    assert theo_id[a]["da_dinh_chinh"] and theo_id[a]["thay_boi"] == moi
    assert not theo_id[moi]["da_dinh_chinh"]


async def test_ham_db_doc_don_deu_da_duyet(q: Quay) -> None:
    """Hàm DB đọc `prescription`: mỗi hàm có lý do hiện hành / theo id."""
    duyet = {
        # đọc THEO ID dòng của chính giao dịch / phân lô — tự kiểm removed_at
        "drug_return_guard": "trả thuốc theo lần giao gốc (đối soát được)",
        "inventory_txn_ban_hop_le": "theo phân lô; chặn SALE/DISPENSE lịch sử",
        # chỉ tra lượt của dòng sổ để so cơ sở kho (20261008200000)
        "inventory_txn_dung_co_so": "theo id dòng đơn — lấy lượt so cơ sở",
        "prescription_allocation_guard": "theo dòng; chặn phân lô lịch sử",
        "prescription_dinh_chinh_guard": "guard của chính bảng",
        "prescription_muc_dau_vet": "mức dấu vết theo id",
        # đọc theo lượt — phải lọc hiện hành
        "move_visit_to_station": "removed_at IS NULL",
    }
    rows = await q.pool.fetch(
        "SELECT p.proname, p.prosrc FROM pg_proc p"
        " JOIN pg_namespace n ON n.oid = p.pronamespace"
        " WHERE n.nspname = 'public'"
        "   AND p.prosrc ~* '(from|join)\\s+(public\\.)?prescription\\s'"
    )
    assert {r["proname"] for r in rows} <= set(duyet)
    mvs = next(r["prosrc"] for r in rows if r["proname"] == "move_visit_to_station")
    assert "removed_at IS NULL" in mvs
