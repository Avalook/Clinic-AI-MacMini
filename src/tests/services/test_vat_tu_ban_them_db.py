"""Bán thêm vật tư ở quầy Thu tiền dịch vụ (Tuyền 01/10/2026, C13) — DB thật.

Đầu dò Bio chọn nhanh (một cú bấm = một dòng, bấm nữa = cộng số lượng), vật tư
khác tìm theo tên; giá 0 / chưa có giá = KHÔNG bán; vòng Mirena chỉ bán khi có
quản lý duyệt; quầy thuốc không thêm được; tiền vật tư là tiền DỊCH VỤ (vào hoá
đơn dịch vụ, khoá khi đã thu, "Hoàn tác lần thu" trả dòng về chờ thu).

Mỗi bài tự dựng mặt hàng riêng (mã `VT_TEST_*`) để không phụ thuộc dữ liệu nạp.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.bill_service import ghep_dich_vu, tinh_hoa_don
from clinicai.services.cong_no_service import loc_no_dich_vu
from clinicai.services.danh_muc_dich_vu_service import doc_vat_tu, dong_vat_tu
from clinicai.services.payment_service import PaymentService
from clinicai.services.quay_thu_service import QuayThuService, dung_hoa_don_quay
from clinicai.services.vat_tu_service import VatTuService, ly_do_khong_ban
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai
from tests.services.test_don_du_lieu_thu_db import _nguoi as _nguoi_khoi
from tests.services.test_tien_thuoc_cp1_db import Quay, tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]

CLINIC = "a0000000-0000-4000-8000-000000000001"

pytestmark = pytest.mark.db


async def _vt(
    q: Quay,
    ten: str,
    gia: int | None,
    *,
    active: bool = True,
    can_duyet: bool = False,
    nhanh: bool = False,
) -> str:
    return str(
        await q.pool.fetchval(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " unit_price, active, billing_owner, don_vi, can_ql_duyet, chon_nhanh,"
            " category)"
            " VALUES ($1::uuid, $2, $3, 'vat_tu', $4, $5, 'CLINIC', 'cái', $6, $7,"
            " 'Nguyên liệu tiêu hao') RETURNING id::text",
            CLINIC,
            f"VT_TEST_{uuid.uuid4().hex[:10]}",
            f"{ten} {q.duoi}",
            gia,
            active,
            can_duyet,
            nhanh,
        )
    )


async def _dong_vat_tu(q: Quay) -> list[dict[str, Any]]:
    async with q.pool.acquire() as conn:
        hd = await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=q.visit_id, kind="dich_vu"
        )
    return [d for d in hd.cho_api()["dong"] if d["source_type"] == "vat_tu"]


async def _tong(q: Quay, kind: str = "dich_vu") -> int:
    async with q.pool.acquire() as conn:
        return (
            await tinh_hoa_don(conn, clinic_id=CLINIC, visit_id=q.visit_id, kind=kind)
        ).tong


async def _thu(q: Quay) -> dict[str, Any]:
    async with q.pool.acquire() as conn:
        hd = await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=q.visit_id, kind="dich_vu"
        )
    return await PaymentService(q.pool).record_payment(
        visit_id=q.visit_id,
        kind="dich_vu",
        amount=None,
        clinic_patient_id=None,
        identity=q.thu_ngan,
        bill_revision=hd.revision,
        method="CASH",
        idempotency_key=f"vt-{uuid.uuid4().hex}",
        quay="dich_vu",
    )


# ── Luật thuần ──────────────────────────────────────────────────────────────


def test_ly_do_khong_ban_thuan() -> None:
    assert ly_do_khong_ban(active=True, don_gia=300_000) is None
    assert "chưa có giá" in str(ly_do_khong_ban(active=True, don_gia=None))
    assert "chưa có giá" in str(ly_do_khong_ban(active=True, don_gia=0))
    assert "ngưng bán" in str(ly_do_khong_ban(active=False, don_gia=300_000))
    assert (
        dong_vat_tu(
            {"id": uuid.uuid4(), "service_code": "X", "name": "A", "unit_price": 0}
        )["ban_duoc"]
        is False
    )


def test_hoa_don_thuan_vat_tu_co_so_luong_va_la_tien_dich_vu() -> None:
    vid = str(uuid.uuid4())
    hd = ghep_dich_vu(
        vid,
        None,
        [],
        vat_tu=[
            {
                "id": "a",
                "service_price_id": "sp",
                "ten": "Đầu dò Bio 1 lần",
                "don_vi": "cái",
                "don_gia": 300000,
                "so_luong": 3,
            }
        ],
    )
    assert hd.kind == "dich_vu"
    assert hd.tong == 900_000
    assert [d.source_type for d in hd.dong] == ["vat_tu"]
    # Vật tư chưa thu là NỢ khi khách về (không gắn chỉ định cha).
    assert [d.so_tien for d in loc_no_dich_vu(hd, [])] == [900_000]


def test_quay_thu_hien_vat_tu_khoa_kem_so_luong() -> None:
    hd = {
        "tong": 600000,
        "revision": "r",
        "thu_duoc": True,
        "dong": [
            {
                "source_type": "vat_tu",
                "source_id": "v1",
                "ten": "Đầu dò Bio 1 lần",
                "so_luong": 2.0,
                "thanh_tien": 600000.0,
            }
        ],
    }
    qt = dung_hoa_don_quay(hd, None)
    (dong,) = qt["phong_kham"]
    assert dong["loai"] == "vat_tu" and dong["gia"] == 600000
    assert dong["ten"].endswith("× 2")
    assert dong["sua_duoc"] is False and dong["trong_lua_chon"] is False
    assert qt["tong"] == 600000


# ── Thêm / đổi / bỏ → hoá đơn ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chon_nhanh_cong_don_so_luong_roi_bo(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    svc = VatTuService(pool)
    probe = await _vt(q, "Đầu dò Bio 1 lần", 300_000, nhanh=True)
    truoc = await _tong(q)  # tiền khám của lượt

    kq = await svc.them(
        visit_id=q.visit_id, service_price_id=probe, identity=q.thu_ngan
    )
    assert [d["so_luong"] for d in kq["dong"]] == [1] and kq["tong"] == 300_000
    assert await _tong(q) == truoc + 300_000
    (dong,) = await _dong_vat_tu(q)
    assert dong["don_gia"] == 300_000 and dong["ben_thu"] == "CLINIC"

    # Bấm chip lần nữa = cộng số lượng (không đẻ dòng thứ hai).
    kq = await svc.them(
        visit_id=q.visit_id, service_price_id=probe, identity=q.thu_ngan
    )
    assert [d["so_luong"] for d in kq["dong"]] == [2]
    assert await _tong(q) == truoc + 600_000

    # Sửa số lượng ở ô số.
    dong_id = kq["dong"][0]["id"]
    kq = await svc.dat_so_luong(dong_id=dong_id, so_luong=3, identity=q.thu_ngan)
    assert kq["tong"] == 900_000 and await _tong(q) == truoc + 900_000
    with pytest.raises(ValidationError):
        await svc.dat_so_luong(dong_id=dong_id, so_luong=0, identity=q.thu_ngan)
    with pytest.raises(ValidationError):
        await svc.dat_so_luong(dong_id=dong_id, so_luong=100, identity=q.thu_ngan)

    # Bỏ trước khi thu → hết khỏi hoá đơn, không xoá dòng (đóng dấu).
    kq = await svc.bo(dong_id=dong_id, identity=q.thu_ngan)
    assert kq["dong"] == [] and await _tong(q) == truoc
    assert await pool.fetchval(
        "SELECT bo_luc IS NOT NULL AND bo_boi IS NOT NULL FROM luot_vat_tu"
        " WHERE id = $1::uuid",
        dong_id,
    )
    with pytest.raises(NotFoundError):
        await svc.bo(dong_id=dong_id, identity=q.thu_ngan)
    # Thêm lại sau khi bỏ: dòng mới (chỉ mục duy nhất chỉ giữ dòng SỐNG).
    kq = await svc.them(
        visit_id=q.visit_id, service_price_id=probe, identity=q.thu_ngan
    )
    assert [d["so_luong"] for d in kq["dong"]] == [1]


@pytest.mark.asyncio
async def test_doc_goi_y_bio_va_danh_muc(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    probe = await _vt(q, "Đầu dò thử", 300_000, nhanh=True)
    khong_gia = await _vt(q, "Gạc thử", None)
    d = await VatTuService(pool).doc(visit_id=q.visit_id, identity=q.thu_ngan)
    theo_id = {m["id"]: m for m in d["danh_muc"]}
    assert theo_id[probe]["ban_duoc"] and theo_id[probe]["chon_nhanh"]
    assert not theo_id[khong_gia]["ban_duoc"]
    assert "chưa có giá" in theo_id[khong_gia]["ly_do_khong_ban"]
    assert d["duoc_sua"] is True and d["la_quan_ly"] is False
    # Lượt có dịch vụ gợi ý đầu dò → đầu dò `goi_y` (nổi lên đầu).
    assert theo_id[probe]["goi_y"] is False
    dv = await pool.fetchval(
        'INSERT INTO service_price (clinic_id, service_code, name, "group",'
        " unit_price, billing_owner, node_code)"
        " VALUES ($1::uuid, $2, $3, 'dich_vu', 900000, 'CLINIC', 'DICHVU-SIEUAM')"
        " RETURNING id::text",
        CLINIC,
        f"BIO-{q.duoi}",
        f"Tập máy Bio thử {q.duoi}",
    )
    await pool.execute(
        "INSERT INTO vat_tu_goi_y (clinic_id, dich_vu_id, vat_tu_id)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid)",
        CLINIC,
        dv,
        probe,
    )
    await pool.execute(
        "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
        " service_code, service_name, node_code, exec_status, recorded_by,"
        " authorized_by, authorized_at, selection_status)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, 'Tập máy Bio thử',"
        " 'DICHVU-SIEUAM', 'authorized', $5::uuid, $5::uuid, now(), 'SELECTED')",
        CLINIC,
        q.visit_id,
        q.consultation_id,
        f"BIO-{q.duoi}",
        q.bac_si.staff_id,
    )
    d = await VatTuService(pool).doc(visit_id=q.visit_id, identity=q.thu_ngan)
    assert {m["id"]: m for m in d["danh_muc"]}[probe]["goi_y"] is True


# ── Giá 0 / chưa có giá / ngưng bán: không bán ──────────────────────────────


@pytest.mark.asyncio
async def test_gia_khong_hoac_ngung_ban_bi_tu_choi(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    svc = VatTuService(pool)
    for sp in (
        await _vt(q, "Bao cao su", None),
        await _vt(q, "Gạc củ ấu", 50_000, active=False),
    ):
        with pytest.raises(ValidationError):
            await svc.them(
                visit_id=q.visit_id, service_price_id=sp, identity=q.thu_ngan
            )
    assert await _dong_vat_tu(q) == []
    # Hàng không phải vật tư (dịch vụ khác nhóm) cũng không thêm được.
    dv = str(
        await pool.fetchval(
            "SELECT id::text FROM service_price WHERE clinic_id = $1::uuid"
            " AND \"group\" = 'dich_vu' LIMIT 1",
            CLINIC,
        )
    )
    with pytest.raises(NotFoundError):
        await svc.them(visit_id=q.visit_id, service_price_id=dv, identity=q.thu_ngan)
    # Lưới cuối ở Postgres: ghi thẳng cũng bị chặn (giá chưa có).
    chua_gia = await _vt(q, "Kim chưa giá", None)
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "INSERT INTO luot_vat_tu (clinic_id, visit_id, service_price_id, ten,"
            " don_gia, so_luong) VALUES ($1::uuid, $2::uuid, $3::uuid, 'x', 1000, 1)",
            CLINIC,
            q.visit_id,
            chua_gia,
        )


# ── Mirena: cần quản lý duyệt ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mirena_can_quan_ly_duyet(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    svc = VatTuService(pool)
    mirena = await _vt(q, "Vòng Mirena", 4_000_000, can_duyet=True)
    ql = await _nguoi_vai(q, "MANAGEMENT")

    # Không duyệt → từ chối, không ghi gì.
    with pytest.raises(ValidationError):
        await svc.them(
            visit_id=q.visit_id, service_price_id=mirena, identity=q.thu_ngan
        )
    # Có người duyệt nhưng thiếu lý do → từ chối.
    with pytest.raises(ValidationError):
        await svc.them(
            visit_id=q.visit_id,
            service_price_id=mirena,
            duyet_boi=ql.staff_id,
            ly_do_duyet="",
            identity=q.thu_ngan,
        )
    # Người "duyệt" không phải quản lý → từ chối.
    with pytest.raises(ValidationError):
        await svc.them(
            visit_id=q.visit_id,
            service_price_id=mirena,
            duyet_boi=q.bac_si.staff_id,
            ly_do_duyet="Vòng thứ hai do tụt vòng",
            identity=q.thu_ngan,
        )
    assert await _dong_vat_tu(q) == []

    # Thu ngân + quản lý đã duyệt + lý do → bán được; ghi ai duyệt.
    kq = await svc.them(
        visit_id=q.visit_id,
        service_price_id=mirena,
        duyet_boi=ql.staff_id,
        ly_do_duyet="Vòng thứ hai: vòng đầu tụt khi đặt",
        identity=q.thu_ngan,
    )
    (dong,) = kq["dong"]
    assert dong["thanh_tien"] == 4_000_000 and dong["nguoi_duyet"] == ql.full_name
    assert "tụt" in dong["ly_do_duyet"]
    await svc.bo(dong_id=dong["id"], identity=q.thu_ngan)

    # Quản lý tự thêm: chính họ là người duyệt, vẫn phải ghi lý do.
    with pytest.raises(ValidationError):
        await svc.them(visit_id=q.visit_id, service_price_id=mirena, identity=ql)
    kq = await svc.them(
        visit_id=q.visit_id,
        service_price_id=mirena,
        ly_do_duyet="Sự cố vòng thứ hai",
        identity=ql,
    )
    assert kq["dong"][0]["nguoi_duyet"] == ql.full_name

    # Lưới cuối ở Postgres: ghi thẳng KHÔNG người duyệt bị chặn.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "INSERT INTO luot_vat_tu (clinic_id, visit_id, service_price_id, ten,"
            " don_gia, so_luong)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, 'x', 4000000, 1)",
            CLINIC,
            q.visit_id,
            await _vt(q, "Mirena khác", 4_000_000, can_duyet=True),
        )


# ── Quầy thuốc không bán vật tư ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_quay_thuoc_khong_them_duoc_vat_tu(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    svc = VatTuService(pool)
    probe = await _vt(q, "Đầu dò", 300_000)
    # Thu ngân quầy thuốc chỉ giữ khối "Thu tiền thuốc" (không Thu tiền dịch vụ,
    # không Chọn dịch vụ). Preset vai trên DB test được mở rộng nên cấp đúng khối.
    thuoc = await _nguoi_khoi(pool, "CASHIER_THUOC", ["thu_tien_thuoc"])
    with pytest.raises(SafetyGateError):
        await svc.them(visit_id=q.visit_id, service_price_id=probe, identity=thuoc)
    kq = await svc.them(
        visit_id=q.visit_id, service_price_id=probe, identity=q.thu_ngan
    )
    dong_id = kq["dong"][0]["id"]
    with pytest.raises(SafetyGateError):
        await svc.dat_so_luong(dong_id=dong_id, so_luong=2, identity=thuoc)
    with pytest.raises(SafetyGateError):
        await svc.bo(dong_id=dong_id, identity=thuoc)
    # Tiền vật tư KHÔNG lọt vào hoá đơn thuốc.
    async with pool.acquire() as conn:
        hd_thuoc = await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=q.visit_id, kind="thuoc"
        )
    assert all(d.source_type == "prescription" for d in hd_thuoc.dong)
    assert [d["so_luong"] for d in await _dong_vat_tu(q)] == [1.0]


# ── Thu tiền, khoá, hoàn tác lần thu ────────────────────────────────────────


@pytest.mark.asyncio
async def test_thu_roi_khoa_hoan_tac_lan_thu_tra_ve_cho_thu(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    svc = VatTuService(pool)
    ql = await _nguoi_vai(q, "MANAGEMENT")
    bao_cao = BaoCaoCuoiNgayService(pool)
    truoc = {
        k: await bao_cao.bao_cao(identity=ql, loai=k) for k in ("dich_vu", "thuoc")
    }
    probe = await _vt(q, "Đầu dò Bio nhiều lần", 900_000, nhanh=True)
    kq = await svc.them(
        visit_id=q.visit_id, service_price_id=probe, identity=q.thu_ngan
    )
    dong_id = kq["dong"][0]["id"]
    tong = await _tong(q)

    lan = await _thu(q)
    cycle = lan["payment_cycle_id"]
    # Ảnh chụp lần thu có dòng vật tư — tiền DỊCH VỤ, đúng số lượng, đúng giá.
    bl = await pool.fetch(
        "SELECT kind, source_type, quantity, unit, unit_price, line_total"
        " FROM payment_bill_line WHERE payment_cycle_id = $1::uuid"
        " AND source_type = 'vat_tu'",
        cycle,
    )
    assert len(bl) == 1 and bl[0]["kind"] == "dich_vu"
    assert bl[0]["quantity"] == Decimal(1) and bl[0]["unit"] == "cái"
    assert bl[0]["line_total"] == Decimal(900_000)
    assert await _tong(q) == 0 < tong  # hết nợ

    # Đã thu → khoá (service) và Postgres cũng chặn ghi thẳng.
    d = await svc.doc(visit_id=q.visit_id, identity=q.thu_ngan)
    assert d["dong"][0]["da_thu"] is True
    with pytest.raises(ConflictError):
        await svc.dat_so_luong(dong_id=dong_id, so_luong=2, identity=q.thu_ngan)
    with pytest.raises(ConflictError):
        await svc.bo(dong_id=dong_id, identity=q.thu_ngan)
    with pytest.raises(ConflictError):
        await svc.them(visit_id=q.visit_id, service_price_id=probe, identity=q.thu_ngan)
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE luot_vat_tu SET so_luong = 5 WHERE id = $1::uuid", dong_id
        )

    # Báo cáo cuối ngày: tiền vật tư nằm ở bên DỊCH VỤ (cùng tiền khám), thuốc
    # đứng im.
    sau = {k: await bao_cao.bao_cao(identity=ql, loai=k) for k in ("dich_vu", "thuoc")}
    assert (
        int(sau["dich_vu"]["tong"]["thuc_thu"])
        - int(truoc["dich_vu"]["tong"]["thuc_thu"])
        == tong
    )
    assert int(sau["thuoc"]["tong"]["thuc_thu"]) == int(
        truoc["thuoc"]["tong"]["thuc_thu"]
    )
    # Bản in phiếu thu (và sổ lịch sử, cùng đọc `payment_bill_line`) có dòng vật tư.
    phieu = await QuayThuService(pool).phieu(identity=q.thu_ngan, id_=cycle)
    dong_in = [d for d in phieu["dong"] if "Đầu dò Bio nhiều lần" in d["ten"]]
    assert len(dong_in) == 1 and dong_in[0]["thanh_tien"] == 900_000
    ten = await pool.fetchval(
        "SELECT name_snapshot FROM payment_bill_line WHERE payment_cycle_id = $1::uuid"
        " AND source_type = 'vat_tu'",
        cycle,
    )
    assert "Đầu dò Bio nhiều lần" in ten

    # HOÀN TÁC LẦN THU (quầy dịch vụ) → dòng về chờ thu, sửa / bỏ được lại.
    await PaymentService(pool).hoan_tac(
        payment_cycle_id=cycle, ly_do=None, identity=q.thu_ngan, quay="dich_vu"
    )
    assert await _tong(q) == tong
    d = await svc.doc(visit_id=q.visit_id, identity=q.thu_ngan)
    assert d["dong"][0]["da_thu"] is False
    kq = await svc.dat_so_luong(dong_id=dong_id, so_luong=2, identity=q.thu_ngan)
    assert kq["tong"] == 1_800_000
    kq = await svc.bo(dong_id=dong_id, identity=q.thu_ngan)
    assert kq["dong"] == []


# ── Sự kiện ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_phat_su_kien_cho_cac_man(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    svc = VatTuService(pool)
    probe = await _vt(q, "Đầu dò sự kiện", 300_000)
    kq = await svc.them(
        visit_id=q.visit_id, service_price_id=probe, identity=q.thu_ngan
    )
    await svc.dat_so_luong(dong_id=kq["dong"][0]["id"], so_luong=2, identity=q.thu_ngan)
    await svc.bo(dong_id=kq["dong"][0]["id"], identity=q.thu_ngan)
    ev = await pool.fetch(
        "SELECT payload->>'hanh_dong' AS hd, (payload->>'so_luong')::int AS sl"
        " FROM domain_event WHERE event_type = 'visit.supply_changed'"
        " AND payload->>'visit_id' = $1 ORDER BY occurred_at, aggregate_version",
        q.visit_id,
    )
    assert [(e["hd"], e["sl"]) for e in ev] == [("them", 1), ("sua", 2), ("bo", 2)]
    nhat_ky = await pool.fetchval(
        "SELECT count(*) FROM event_log WHERE event_type = 'visit.supply_changed'"
        " AND aggregate_id = $1",
        q.visit_id,
    )
    assert nhat_ky == 3
    # Postgres báo màn đang mở (trigger notify) — trigger có mặt.
    assert await pool.fetchval(
        "SELECT count(*) FROM pg_trigger WHERE tgname = 'trg_notify_luot_vat_tu'"
    )


# ── Dữ liệu nạp từ Excel + Bảng giá ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_du_lieu_nap_tu_excel_va_bang_gia(pool: asyncpg.Pool) -> None:
    rows = await pool.fetch(
        "SELECT name, unit_price, don_vi, can_ql_duyet, chon_nhanh, active"
        " FROM service_price WHERE clinic_id = $1::uuid AND \"group\" = 'vat_tu'"
        " AND service_code NOT LIKE 'VT_TEST_%'",
        CLINIC,
    )
    theo_ten = {r["name"]: r for r in rows}
    assert len(rows) == 84, (
        "84 dòng Excel 01/10 (hai tên trùng khác đơn vị vẫn là hai dòng)"
    )
    b1, bn = theo_ten["Đầu dò Bio 1 lần"], theo_ten["Đầu dò Bio nhiều lần"]
    assert (b1["unit_price"], b1["don_vi"], b1["chon_nhanh"]) == (300_000, "cái", True)
    assert (bn["unit_price"], bn["chon_nhanh"]) == (900_000, True)
    mi = theo_ten["Vòng nội tiết tránh thai Mirena"]
    assert mi["unit_price"] == 4_000_000 and mi["can_ql_duyet"] and not mi["chon_nhanh"]
    # Giá 0 trong Excel = KHÔNG bán: nạp NULL (không bao giờ nạp 0đ).
    ban_duoc = [r for r in rows if r["unit_price"] is not None]
    assert {r["name"] for r in ban_duoc} == set(
        ["Đầu dò Bio 1 lần", "Đầu dò Bio nhiều lần", "Vòng nội tiết tránh thai Mirena"]
    )
    assert all(r["unit_price"] is None for r in rows if r not in ban_duoc)

    # Chạy lại được: lần hai không đổi gì, không đè giá quản lý đã sửa.
    try:
        await pool.execute(
            "UPDATE service_price SET unit_price = 320000 WHERE clinic_id = $1::uuid"
            " AND service_code = 'VT_DAU_DO_BIO_1_LAN'",
            CLINIC,
        )
        r = await pool.fetchrow("SELECT * FROM public.dong_bo_vat_tu(false)")
        assert (r["them"], r["sua"], r["goi_y"]) == (0, 0, 0)
        gia = await pool.fetchval(
            "SELECT unit_price FROM service_price WHERE clinic_id = $1::uuid"
            " AND service_code = 'VT_DAU_DO_BIO_1_LAN'",
            CLINIC,
        )
        assert gia == 320_000
    finally:
        await pool.execute(
            "UPDATE service_price SET unit_price = 300000 WHERE clinic_id = $1::uuid"
            " AND service_code = 'VT_DAU_DO_BIO_1_LAN'",
            CLINIC,
        )

    # Vật tư KHÔNG vào danh mục dịch vụ + phòng (không "Chưa có phòng").
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM danh_muc_dich_vu($1::uuid)"
            " WHERE service_code LIKE 'VT\\_%'",
            CLINIC,
        )
        == 0
    )


@pytest.mark.asyncio
async def test_bang_gia_tra_vat_tu_rieng_khong_phong(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    await _vt(q, "Vật tư màn giá", 120_000)
    await _vt(q, "Vật tư chưa giá", None)
    async with pool.acquire() as conn:
        goi = {"vat_tu": await doc_vat_tu(conn, CLINIC)}
    vt = [v for v in goi["vat_tu"] if q.duoi in v["name"]]
    assert {v["name"].split(" " + q.duoi)[0]: v["ban_duoc"] for v in vt} == {
        "Vật tư màn giá": True,
        "Vật tư chưa giá": False,
    }
    # Không có cột phòng / cảnh báo phòng cho vật tư.
    assert all("phong" not in v and "chua_co_phong" not in v for v in vt)
