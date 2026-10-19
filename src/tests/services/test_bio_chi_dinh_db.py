"""G9 — Đầu dò Bio chọn ở CHỈ ĐỊNH cận lâm sàng (Tuyền chốt 14/10/2026, Q14/Q14b).

    scripts/test-nhanh.sh src/tests/services/test_bio_chi_dinh_db.py

Bác sĩ chỉ định siêu âm / tập máy Bio thì chọn luôn "Bio 1 lần / nhiều lần" ở
chính chỉ định ấy. Bio là dòng `luot_vat_tu` GẮN `order_id`: tiền đi theo chỉ
định (huỷ / khách không làm → không vào hoá đơn, không thành nợ; khôi phục →
quay lại), quầy thu vẫn bỏ được TRƯỚC khi thu (bắt ghi lý do), đã thu thì khoá
(muốn đổi phải hoàn tác lần thu như mọi dòng vật tư).

BẤT BIẾN (kiểm cả bằng bài bấm ngẫu nhiên, có bên nhận sự kiện chạy XEN GIỮA):

  B1  Dòng Bio còn phải thu trên hoá đơn = đúng các dòng Bio SỐNG của chỉ định
      CÒN HIỆU LỰC và khách ĐÃ CHỌN làm, chưa nằm trong lần thu đang giữ phủ.
  B2  Màn quầy ("Mua thêm vật tư") hiện cùng tập dòng ấy — không dòng ma của
      chỉ định đã huỷ, không thiếu dòng đang tính tiền.
  B3  Một chỉ định không có hai dòng Bio sống cùng mặt hàng; chọn lại = thay,
      không cộng dồn.
  B4  Bio đã thu không bị đổi / bỏ ngầm (đổi phải hoàn tác lần thu trước).
  B5  Mọi bên nhận sự kiện xử lý xong sự kiện của lượt, không RETRY / DEAD.
"""

from __future__ import annotations

import random
import uuid
from collections import Counter
from collections.abc import AsyncIterator, Awaitable, Callable
from decimal import Decimal
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.core.exceptions import ClinicAIBaseException, SafetyGateError
from clinicai.events.catalogue import CONG_NO, DONG_THOI_GIAN_LUOT, HANH_TRINH
from clinicai.services.bill_service import hoa_don_con_no
from clinicai.services.bio_chi_dinh_service import BioChiDinhService
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.cong_no_service import no_khi_ve
from clinicai.services.hoan_tac_service import HoanTacService
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.payment_service import PaymentService
from clinicai.services.service_execution_service import ServiceExecutionService
from clinicai.services.so_sua_chi_dinh_service import SoSuaChiDinhService
from clinicai.services.vat_tu_service import VatTuService
from tests.chay_nguoi_dua_tin import chay_ben_nhan, chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_don_du_lieu_thu_db import _nguoi as _nguoi_khoi
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    NODE,
    Ca,
    _benh_nhan,
    _check_in,
    _chon,
    _don,
    _dung,
    _khoa,
)
from tests.services.test_thu_truoc_lam_truoc_tick_db import day_thu_truoc

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

GIA_BIO_1 = 300_000
GIA_BIO_N = 900_000
GIA_DV = 300_000
GIA_DV_B = 200_000


# ── dựng ca: hai chỉ định siêu âm đầu dò, mỗi cái có gợi ý Bio ─────────────


class Luot:
    def __init__(
        self,
        ca: Ca,
        visit: str,
        con: str,
        a: str,
        b: str,
        bio1: str,
        bio_n: str,
        mirena: str,
    ) -> None:
        self.ca, self.visit, self.con = ca, visit, con
        self.a, self.b = a, b  # hai chỉ định
        self.bio1, self.bio_n, self.mirena = bio1, bio_n, mirena


async def _vat_tu(
    pool: asyncpg.Pool,  # noqa: F811
    ten: str,
    gia: int | None,
    *,
    can_duyet: bool = False,
) -> str:
    return str(
        await pool.fetchval(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " unit_price, active, billing_owner, don_vi, can_ql_duyet, chon_nhanh,"
            " category, kinh_doanh_vat_tu)"
            " VALUES ($1::uuid, $2, $3, 'vat_tu', $4, true, 'CLINIC', 'cái', $5,"
            " true, 'Nguyên liệu tiêu hao', true) RETURNING id::text",
            CLINIC,
            f"VT_TEST_{uuid.uuid4().hex[:10]}",
            f"{ten} {uuid.uuid4().hex[:5]}",
            gia,
            can_duyet,
        )
    )


async def _luot(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    *,
    chon: str = "ca_hai",
) -> Luot:
    """Lượt có HAI chỉ định siêu âm đầu dò (A 300.000đ, B 200.000đ), mỗi chỉ định
    gợi ý hai Bio; khách đã chọn làm `chon` ("ca_hai" | "a" | "b")."""
    bio1 = await _vat_tu(pool, "Đầu dò Bio 1 lần", GIA_BIO_1)
    bio_n = await _vat_tu(pool, "Đầu dò Bio nhiều lần", GIA_BIO_N)
    mirena = await _vat_tu(pool, "Vòng Mirena", 4_000_000, can_duyet=True)
    ma_b = f"SB-{uuid.uuid4().hex[:8]}"
    await pool.execute(
        'INSERT INTO service_price (clinic_id, service_code, name, "group",'
        " unit_price, node_code) VALUES ($1::uuid, $2, $3, 'dich_vu', $4, $5)",
        CLINIC,
        ma_b,
        f"Tập máy Bio {ma_b}",
        GIA_DV_B,
        NODE,
    )
    for ma in (ca.ma_dv, ma_b):
        for vt in (bio1, bio_n):
            await pool.execute(
                "INSERT INTO vat_tu_goi_y (clinic_id, dich_vu_id, vat_tu_id)"
                " SELECT $1::uuid, dv.id, $3::uuid FROM service_price dv"
                " WHERE dv.clinic_id = $1::uuid AND dv.service_code = $2"
                " AND dv.\"group\" = 'dich_vu' ON CONFLICT DO NOTHING",
                CLINIC,
                ma,
                vt,
            )
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
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
        service_codes=[ca.ma_dv, ma_b],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    a, b = (str(i) for i in kq["order_ids"])
    # Thứ tự order_ids theo thứ tự mã đã gửi.
    chon_ids = {"ca_hai": [a, b], "a": [a], "b": [b]}[chon]
    await _chon(pool, ca, visit, chon_ids)
    await chay_hanh_trinh(pool)
    return Luot(ca, visit, con, a, b, bio1, bio_n, mirena)


async def _bio(
    pool: asyncpg.Pool,  # noqa: F811
    lt: Luot,
    order: str,
    vt: str | None,
    *,
    ai: str = "bac_si",
    so_luong: int = 1,
) -> dict[str, Any]:
    return await BioChiDinhService(pool).chon(
        order_id=order,
        service_price_id=vt,
        so_luong=so_luong,
        identity=getattr(lt.ca, ai),
    )


async def _hd(pool: asyncpg.Pool, visit: str) -> list[dict[str, Any]]:  # noqa: F811
    """Dòng vật tư CÒN PHẢI THU của hoá đơn dịch vụ: (source_id, order_id, tiền)."""
    async with pool.acquire() as conn:
        hd = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)
    return [
        {"id": d.source_id, "order_id": d.order_id, "tien": int(d.thanh_tien or 0)}
        for d in hd.dong
        if d.source_type == "vat_tu"
    ]


async def _tong(pool: asyncpg.Pool, visit: str) -> int:  # noqa: F811
    async with pool.acquire() as conn:
        return (await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)).tong


async def _thu(pool: asyncpg.Pool, lt: Luot, method: str = "CASH") -> str:  # noqa: F811
    kq = await PaymentService(pool).record_payment(
        visit_id=lt.visit,
        kind="dich_vu",
        amount=None,
        clinic_patient_id=None,
        identity=lt.ca.thu_ngan,
        method=method,
        idempotency_key=_khoa(),
        quay="dich_vu",
    )
    return str(kq["payment_cycle_id"])


async def _huy_phieu(pool: asyncpg.Pool, lt: Luot) -> None:  # noqa: F811
    cid = await pool.fetchval(
        "SELECT payment_cycle_id::text FROM payment_cycle WHERE visit_id = $1::uuid"
        " AND kind = 'dich_vu' AND status = 'PAID'"
        " ORDER BY created_at DESC LIMIT 1",
        lt.visit,
    )
    assert cid is not None
    await PaymentService(pool).void_payment(
        payment_cycle_id=cid,
        visit_id=lt.visit,
        kind="dich_vu",
        reason="Thu nhầm, huỷ phiếu",
        identity=lt.ca.thu_ngan,
    )


async def _huy_chi_dinh(pool: asyncpg.Pool, lt: Luot, order: str) -> None:  # noqa: F811
    await HoanTacService(pool).huy_chi_dinh(
        order_id=order, identity=lt.ca.bac_si, xac_nhan=True, ly_do="Khách đổi ý"
    )


async def _khoi_phuc(pool: asyncpg.Pool, lt: Luot, order: str) -> None:  # noqa: F811
    so = await pool.fetchval(
        "SELECT id::text FROM so_sua_chi_dinh WHERE service_order_id = $1::uuid"
        " AND hanh_dong = 'BO' AND hoan_tac_luc IS NULL"
        " ORDER BY luc DESC LIMIT 1",
        order,
    )
    assert so is not None, "chỉ định chưa bị bỏ"
    await SoSuaChiDinhService(pool).hoan_tac(so_id=so, identity=lt.ca.bac_si)


async def _lam_xong(pool: asyncpg.Pool, lt: Luot, order: str) -> None:  # noqa: F811
    d = await _don(pool, order)
    bd = await ServiceExecutionService(pool).bat_dau(
        order_id=order,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=lt.ca.dd,
        idempotency_key=_khoa(),
    )
    d2 = await _don(pool, order)
    await ServiceExecutionService(pool).xong(
        order_id=order,
        attempt_id=bd["attempt_id"],
        expected_execution_revision=int(d2["execution_revision"]),
        identity=lt.ca.dd,
        idempotency_key=_khoa(),
    )


async def _dong_song(pool: asyncpg.Pool, order: str) -> list[asyncpg.Record]:  # noqa: F811
    return list(
        await pool.fetch(
            "SELECT id::text AS id, service_price_id::text AS spid, so_luong,"
            " don_gia, bo_ly_do FROM luot_vat_tu"
            " WHERE order_id = $1::uuid AND bo_luc IS NULL ORDER BY chon_luc",
            order,
        )
    )


@pytest_asyncio.fixture(autouse=True)
async def _lam_truoc_thu_sau(pool: asyncpg.Pool) -> AsyncIterator[None]:  # noqa: F811
    # Mặc định dây "thu trước khi làm" TẮT (làm trước thu sau — ca thật nhất);
    # bài nào cần dây BẬT tự bọc `day_thu_truoc(pool, True)`.
    async with day_thu_truoc(pool, False):
        yield


# ── 1. Chọn Bio ở chỉ định → hoá đơn ────────────────────────────────────────


async def test_chon_bio_o_chi_dinh_vao_hoa_don_va_doi_la_thay(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    lt = await _luot(pool, ca)
    truoc = await _tong(pool, lt.visit)
    assert await _hd(pool, lt.visit) == []

    kq = await _bio(pool, lt, lt.a, lt.bio1)
    assert kq["visit_id"] == lt.visit
    (dong,) = await _hd(pool, lt.visit)
    assert dong["order_id"] == lt.a and dong["tien"] == GIA_BIO_1
    assert await _tong(pool, lt.visit) == truoc + GIA_BIO_1

    # Bấm CHÍNH mặt hàng ấy lần nữa = idempotent (không cộng dồn).
    await _bio(pool, lt, lt.a, lt.bio1)
    assert [d["tien"] for d in await _hd(pool, lt.visit)] == [GIA_BIO_1]

    # Đổi sang "nhiều lần" = THAY (radio), không còn dòng 1 lần.
    await _bio(pool, lt, lt.a, lt.bio_n)
    (dong,) = await _hd(pool, lt.visit)
    assert dong["tien"] == GIA_BIO_N
    (song,) = await _dong_song(pool, lt.a)
    assert song["spid"] == lt.bio_n

    # Chỉ định B độc lập với A.
    await _bio(pool, lt, lt.b, lt.bio1)
    assert sorted(d["tien"] for d in await _hd(pool, lt.visit)) == [
        GIA_BIO_1,
        GIA_BIO_N,
    ]

    # "Không dùng đầu dò" = bỏ chọn → hết khỏi hoá đơn (đóng dấu, không xoá).
    await _bio(pool, lt, lt.a, None)
    assert [d["order_id"] for d in await _hd(pool, lt.visit)] == [lt.b]
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM luot_vat_tu WHERE order_id = $1::uuid"
            " AND bo_luc IS NOT NULL AND bo_boi IS NOT NULL",
            lt.a,
        )
        == 2
    )


async def test_hai_chi_dinh_cung_mat_hang_moi_chi_dinh_mot_dong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Hai siêu âm đầu dò trong một lượt, cả hai chọn Bio 1 lần = HAI dòng (mỗi
    dòng theo chỉ định của nó) — không bị khoá "một mặt hàng một dòng sống"."""
    ca = await _dung(pool)
    lt = await _luot(pool, ca)
    await _bio(pool, lt, lt.a, lt.bio1)
    await _bio(pool, lt, lt.b, lt.bio1)
    assert sorted(str(d["order_id"]) for d in await _hd(pool, lt.visit)) == sorted(
        [lt.a, lt.b]
    )


async def test_quay_them_tay_cung_mat_hang_khong_nuot_dong_cua_chi_dinh(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """ "Mua thêm vật tư" ở quầy (đường cũ, giữ nguyên) tạo dòng RIÊNG không gắn
    chỉ định, kể cả cùng mặt hàng với dòng của chỉ định."""
    ca = await _dung(pool)
    lt = await _luot(pool, ca)
    await _bio(pool, lt, lt.a, lt.bio1)
    await VatTuService(pool).them(
        visit_id=lt.visit, service_price_id=lt.bio1, identity=ca.thu_ngan
    )
    cac = await _hd(pool, lt.visit)
    assert sorted(str(d["order_id"]) for d in cac) == sorted([lt.a, "None"])
    # Bấm thêm lần nữa chỉ cộng dòng của QUẦY, dòng chỉ định giữ nguyên 1.
    await VatTuService(pool).them(
        visit_id=lt.visit, service_price_id=lt.bio1, identity=ca.thu_ngan
    )
    (song,) = await _dong_song(pool, lt.a)
    assert song["so_luong"] == 1
    assert sorted(d["tien"] for d in await _hd(pool, lt.visit)) == [
        GIA_BIO_1,
        2 * GIA_BIO_1,
    ]


# ── 2. Tiền đi theo chỉ định ─────────────────────────────────────────────────


async def test_huy_chi_dinh_bo_bio_di_kem_va_khoi_phuc_thi_quay_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    lt = await _luot(pool, ca)
    await _bio(pool, lt, lt.a, lt.bio_n)
    truoc = await _tong(pool, lt.visit)
    await _huy_chi_dinh(pool, lt, lt.a)
    # Hoá đơn bớt cả tiền dịch vụ A lẫn Bio của A.
    assert await _tong(pool, lt.visit) == truoc - GIA_DV - GIA_BIO_N
    assert await _hd(pool, lt.visit) == []
    # Màn quầy cũng không hiện dòng ma.
    doc = await VatTuService(pool).doc(visit_id=lt.visit, identity=ca.thu_ngan)
    assert doc["dong"] == []
    # Không chọn Bio cho chỉ định đã huỷ.
    with pytest.raises((ValidationError, ConflictError, NotFoundError)):
        await _bio(pool, lt, lt.a, lt.bio1)
    # Hoàn tác bỏ chỉ định → Bio quay lại cùng chỉ định.
    await _khoi_phuc(pool, lt, lt.a)
    assert await _tong(pool, lt.visit) == truoc
    (dong,) = await _hd(pool, lt.visit)
    assert dong["order_id"] == lt.a and dong["tien"] == GIA_BIO_N


async def test_khach_khong_chon_lam_dich_vu_thi_bio_khong_tinh_tien(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    lt = await _luot(pool, ca, chon="a")  # B bị khách bỏ (NOT_SELECTED)
    await _bio(pool, lt, lt.a, lt.bio1)
    await _bio(pool, lt, lt.b, lt.bio_n)
    assert [d["order_id"] for d in await _hd(pool, lt.visit)] == [lt.a]
    doc = await VatTuService(pool).doc(visit_id=lt.visit, identity=ca.thu_ngan)
    # Dòng của B vẫn hiện để quầy hiểu, nhưng KHÔNG tính tiền.
    tinh = {d["order_id"]: d["tinh_tien"] for d in doc["dong"]}
    assert tinh == {lt.a: True, lt.b: False}
    assert doc["tong"] == GIA_BIO_1


async def test_bio_di_cung_tien_dich_vu_trong_mot_lan_thu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Dây `thu_truoc_khi_lam` BẬT: thu một lần trả cả dịch vụ lẫn Bio của nó;
    dịch vụ chưa thu thì chưa làm được, thu xong làm được."""
    ca = await _dung(pool)
    async with day_thu_truoc(pool, True):
        lt = await _luot(pool, ca, chon="a")
        await _bio(pool, lt, lt.a, lt.bio1)
        d = await _don(pool, lt.a)
        with pytest.raises(ClinicAIBaseException):
            await ServiceExecutionService(pool).bat_dau(
                order_id=lt.a,
                expected_execution_revision=int(d["execution_revision"]),
                expected_routing_revision=int(d["routing_revision"]),
                identity=ca.dd,
                idempotency_key=_khoa(),
            )
        await _thu(pool, lt)
        assert await _hd(pool, lt.visit) == []  # Bio đã nằm trong lần thu
        paid = await pool.fetchval(
            "SELECT coalesce(sum(bl.line_total), 0) FROM payment_bill_line bl"
            " JOIN payment_cycle c ON c.payment_cycle_id = bl.payment_cycle_id"
            " WHERE c.visit_id = $1::uuid AND c.status = 'PAID'"
            " AND bl.source_type = 'vat_tu'",
            lt.visit,
        )
        assert Decimal(paid) == GIA_BIO_1
        await chay_hanh_trinh(pool)
        await _lam_xong(pool, lt, lt.a)


async def test_bio_chua_thu_cua_chi_dinh_da_lam_la_no_con_chi_dinh_chua_lam_thi_khong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    lt = await _luot(pool, ca)
    await _bio(pool, lt, lt.a, lt.bio1)
    await _bio(pool, lt, lt.b, lt.bio_n)
    await _lam_xong(pool, lt, lt.a)  # A làm xong, B chưa làm
    async with pool.acquire() as conn:
        no = await no_khi_ve(conn, clinic_id=CLINIC, visit_id=lt.visit)
    bio_no = [d for d in no.dong if d.source_type == "vat_tu"]
    # Chỉ Bio của A (đã làm) là nợ; Bio của B (chưa làm) thì không.
    assert [d.so_tien for d in bio_no] == [GIA_BIO_1]


# ── 3. Quầy thu bỏ Bio (có lý do) · đã thu thì khoá ─────────────────────────


async def test_quay_bo_bio_cua_chi_dinh_bat_ly_do_dong_quay_cu_khong_bat(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    lt = await _luot(pool, ca)
    await _bio(pool, lt, lt.a, lt.bio1)
    (song,) = await _dong_song(pool, lt.a)
    vt = VatTuService(pool)
    for ly in (None, "", "  ", "ab"):
        with pytest.raises(ValidationError):
            await vt.bo(dong_id=song["id"], ly_do=ly, identity=ca.thu_ngan)
    assert len(await _dong_song(pool, lt.a)) == 1
    kq = await vt.bo(
        dong_id=song["id"], ly_do="Khách không mua đầu dò", identity=ca.thu_ngan
    )
    assert kq["dong"] == []
    assert await _hd(pool, lt.visit) == []
    assert (
        await pool.fetchval(
            "SELECT bo_ly_do FROM luot_vat_tu WHERE id = $1::uuid", song["id"]
        )
        == "Khách không mua đầu dò"
    )
    # Bác sĩ chọn lại được (hoàn tác theo nghĩa "đặt lại") — dòng MỚI.
    await _bio(pool, lt, lt.a, lt.bio1)
    assert len(await _dong_song(pool, lt.a)) == 1

    # Dòng quầy tự thêm (không chỉ định) bỏ như cũ — KHÔNG bắt lý do.
    await vt.them(visit_id=lt.visit, service_price_id=lt.bio_n, identity=ca.thu_ngan)
    quay = [d for d in await _hd(pool, lt.visit) if d["order_id"] is None]
    kq = await vt.bo(dong_id=str(quay[0]["id"]), identity=ca.thu_ngan)
    assert all(d["order_id"] is not None for d in await _hd(pool, lt.visit))
    assert kq["tong"] == GIA_BIO_1


async def test_bio_da_thu_khoa_hoan_tac_lan_thu_moi_doi_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    lt = await _luot(pool, ca)
    await _bio(pool, lt, lt.a, lt.bio1)
    await _thu(pool, lt)
    (song,) = await _dong_song(pool, lt.a)
    with pytest.raises(ConflictError):
        await _bio(pool, lt, lt.a, lt.bio_n)
    with pytest.raises(ConflictError):
        await _bio(pool, lt, lt.a, None)
    with pytest.raises(ConflictError):
        await VatTuService(pool).bo(
            dong_id=song["id"], ly_do="Khách đổi ý rồi", identity=ca.thu_ngan
        )
    (con,) = await _dong_song(pool, lt.a)
    assert con["id"] == song["id"] and con["spid"] == lt.bio1
    # Hoàn tác lần thu → đổi lại được.
    await _huy_phieu(pool, lt)
    await _bio(pool, lt, lt.a, lt.bio_n)
    (moi,) = await _dong_song(pool, lt.a)
    assert moi["spid"] == lt.bio_n


async def test_huy_chi_dinh_da_thu_bio_hoi_xac_nhan_va_nhac_khoan_bio(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Bio đã thu mà bỏ chỉ định: máy chủ hỏi xác nhận và NÓI RÕ khoản Bio (nó
    không tự thành "tiền thừa" — hoàn ở quầy thu như mọi dòng đã thu)."""
    ca = await _dung(pool)
    lt = await _luot(pool, ca, chon="a")
    await _bio(pool, lt, lt.a, lt.bio1)
    await _thu(pool, lt)
    # Chưa xác nhận → máy chủ hỏi (409 CAN_XAC_NHAN), câu hỏi có nhắc Bio.
    with pytest.raises(ClinicAIBaseException) as e:
        await HoanTacService(pool).huy_chi_dinh(
            order_id=lt.a, identity=ca.bac_si, xac_nhan=False, ly_do="Khách đổi ý"
        )
    assert "Bio" in str(e.value) or "đầu dò" in str(e.value).lower()


async def test_khoi_phuc_chi_dinh_sau_hoan_tien_bio_chua_thu_di_theo_chi_dinh_moi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Đã hoàn tiền rồi hoàn tác bỏ chỉ định = chỉ định MỚI (id mới). Đầu dò chưa
    thu đi theo sang chỉ định mới — không mồ côi ở chỉ định cũ (đã huỷ)."""
    ca = await _dung(pool)
    lt = await _luot(pool, ca, chon="a")
    await _thu(pool, lt)  # thu tiền dịch vụ A
    await _bio(pool, lt, lt.a, lt.bio1)  # Bio thêm SAU khi thu → chưa thu
    await HoanTacService(pool).huy_chi_dinh(
        order_id=lt.a, identity=ca.bac_si, xac_nhan=True, ly_do="Khách đổi ý"
    )
    await HoanTienService(pool).hoan_tien_thua(identity=ca.thu_ngan, visit_id=lt.visit)
    so = await pool.fetchval(
        "SELECT id::text FROM so_sua_chi_dinh WHERE service_order_id = $1::uuid"
        " AND hanh_dong = 'BO' AND hoan_tac_luc IS NULL ORDER BY luc DESC LIMIT 1",
        lt.a,
    )
    kq = await SoSuaChiDinhService(pool).hoan_tac(so_id=so, identity=ca.bac_si)
    moi = kq["chi_dinh_moi"]
    assert moi != lt.a
    assert await _dong_song(pool, lt.a) == []
    (dong,) = await _dong_song(pool, moi)
    assert dong["spid"] == lt.bio1


# ── 4. Rác & quyền ───────────────────────────────────────────────────────────


async def test_dau_vao_rac_bao_loi_khong_ghi_rong(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    lt = await _luot(pool, ca)
    svc = BioChiDinhService(pool)
    for sl in (0, -1, 100, "abc", None, 1.5):
        with pytest.raises(ValidationError):
            await svc.chon(
                order_id=lt.a,
                service_price_id=lt.bio1,
                so_luong=sl,
                identity=ca.bac_si,
            )
    for oid in ("khong-phai-uuid", "", None, str(uuid.uuid4())):
        with pytest.raises((ValidationError, NotFoundError)):
            await svc.chon(
                order_id=oid,  # type: ignore[arg-type]
                service_price_id=lt.bio1,
                so_luong=1,
                identity=ca.bac_si,
            )
    for vt in ("rac", str(uuid.uuid4())):
        with pytest.raises((ValidationError, NotFoundError)):
            await svc.chon(
                order_id=lt.a, service_price_id=vt, so_luong=1, identity=ca.bac_si
            )
    # Hàng cần quản lý duyệt (Mirena): luật duyệt giữ nguyên ở quầy, không lách ở đây.
    with pytest.raises(ValidationError):
        await svc.chon(
            order_id=lt.a, service_price_id=lt.mirena, so_luong=1, identity=ca.bac_si
        )
    # Hàng chưa có giá → không bán.
    chua_gia = await _vat_tu(pool, "Vật tư chưa giá", None)
    with pytest.raises(ValidationError):
        await svc.chon(
            order_id=lt.a, service_price_id=chua_gia, so_luong=1, identity=ca.bac_si
        )
    # Chỉ định của lượt này không bị lẫn sang lượt khác: order lạ → không ghi.
    assert await _dong_song(pool, lt.a) == []
    assert await _hd(pool, lt.visit) == []


async def test_nguoi_khong_co_quyen_chi_dinh_khong_chon_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    lt = await _luot(pool, ca)
    # Thu ngân quầy thuốc chỉ giữ khối "Thu tiền thuốc" — không có quyền chỉ định.
    duoc_si = await _nguoi_khoi(pool, "CASHIER_THUOC", ["thu_tien_thuoc"])
    with pytest.raises(SafetyGateError):
        await BioChiDinhService(pool).chon(
            order_id=lt.a,
            service_price_id=lt.bio1,
            so_luong=1,
            identity=duoc_si,
        )
    assert await _dong_song(pool, lt.a) == []


async def test_doc_goi_y_theo_chi_dinh(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    lt = await _luot(pool, ca)
    await _bio(pool, lt, lt.a, lt.bio_n)
    doc = await BioChiDinhService(pool).doc(visit_id=lt.visit, identity=ca.bac_si)
    theo = {c["order_id"]: c for c in doc["chi_dinh"]}
    assert set(theo) == {lt.a, lt.b}
    a = theo[lt.a]
    assert {g["service_price_id"] for g in a["goi_y"]} == {lt.bio1, lt.bio_n}
    assert a["da_chon"]["service_price_id"] == lt.bio_n
    assert a["da_chon"]["so_luong"] == 1 and a["da_chon"]["da_thu"] is False
    assert theo[lt.b]["da_chon"] is None


# ── 5. Bấm lộn xộn như người thật · bên nhận sự kiện chạy XEN GIỮA ──────────

Viec = Callable[[asyncpg.Pool, Luot, random.Random], Awaitable[object]]


async def _quay_bo(pool: asyncpg.Pool, lt: Luot, rnd: random.Random) -> None:  # noqa: F811
    song = list(
        await pool.fetch(
            "SELECT id::text AS id, order_id FROM luot_vat_tu"
            " WHERE visit_id = $1::uuid AND bo_luc IS NULL",
            lt.visit,
        )
    )
    assert song, "không có dòng nào để bỏ"
    d = rnd.choice(song)
    await VatTuService(pool).bo(
        dong_id=d["id"], ly_do="Khách không mua nữa", identity=lt.ca.thu_ngan
    )


def _chon_dich(rnd: random.Random, lt: Luot) -> str:
    return rnd.choice([lt.a, lt.b])


VIEC: dict[str, Viec] = {
    "bs_chon_bio_1": lambda p, lt, r: _bio(p, lt, _chon_dich(r, lt), lt.bio1),
    "bs_chon_bio_nhieu": lambda p, lt, r: _bio(p, lt, _chon_dich(r, lt), lt.bio_n),
    "bs_bo_bio": lambda p, lt, r: _bio(p, lt, _chon_dich(r, lt), None),
    "quay_bo_bio": _quay_bo,
    "quay_them_tay": lambda p, lt, r: VatTuService(p).them(
        visit_id=lt.visit, service_price_id=lt.bio1, identity=lt.ca.thu_ngan
    ),
    "huy_chi_dinh": lambda p, lt, r: _huy_chi_dinh(p, lt, _chon_dich(r, lt)),
    "khoi_phuc_chi_dinh": lambda p, lt, r: _khoi_phuc(p, lt, _chon_dich(r, lt)),
    "thu_tien_mat": lambda p, lt, r: _thu(p, lt),
    "huy_phieu": lambda p, lt, r: _huy_phieu(p, lt),
    "lam_xong": lambda p, lt, r: _lam_xong(p, lt, _chon_dich(r, lt)),
}


async def _lech(pool: asyncpg.Pool, lt: Luot) -> list[str]:  # noqa: F811
    """Các bất biến bị vỡ của lượt (rỗng = khớp). Bên nhận sự kiện chạy TRƯỚC khi
    kiểm — như worker thật chạy xen giữa các lần bấm."""
    await chay_ben_nhan(pool, HANH_TRINH, CONG_NO, DONG_THOI_GIAN_LUOT)
    vo: list[str] = []
    async with pool.acquire() as conn:
        # B1 — viết lại luật bằng SQL độc lập với mã dưới kiểm.
        mong = {
            str(r["id"])
            for r in await conn.fetch(
                """
                SELECT v.id FROM luot_vat_tu v
                  LEFT JOIN service_order o ON o.id = v.order_id
                 WHERE v.visit_id = $1::uuid AND v.bo_luc IS NULL
                   AND (v.order_id IS NULL OR (
                        o.selection_status = 'SELECTED'
                        AND o.exec_status IN ('authorized', 'assigned',
                                              'in_progress', 'performed')
                        AND coalesce(o.execution_status, 'PENDING')
                            IN ('PENDING', 'IN_PROGRESS', 'COMPLETED')))
                   AND NOT EXISTS (
                        SELECT 1 FROM payment_bill_line bl
                          JOIN payment_cycle c
                            ON c.clinic_id = bl.clinic_id
                           AND c.payment_cycle_id = bl.payment_cycle_id
                         WHERE bl.source_type = 'vat_tu'
                           AND bl.source_id = v.id::text
                           AND bl.billing_owner = 'CLINIC'
                           AND c.status IN ('PENDING_VERIFICATION', 'PAID'))
                """,
                lt.visit,
            )
        }
        hd = {str(d["id"]) for d in await _hd(pool, lt.visit)}
        if hd != mong:
            vo.append(f"B1 hoá đơn Bio {sorted(hd)} ≠ mong đợi {sorted(mong)}")

        # B2 — màn quầy cùng tập dòng.
        doc = await VatTuService(pool).doc(visit_id=lt.visit, identity=lt.ca.thu_ngan)
        man = {d["id"] for d in doc["dong"] if d["tinh_tien"] and not d["da_thu"]}
        if man != mong:
            vo.append(f"B2 màn quầy {sorted(man)} ≠ mong đợi {sorted(mong)}")

        # B3 — không hai dòng Bio sống cùng (chỉ định, mặt hàng).
        for r in await conn.fetch(
            "SELECT order_id::text AS o, service_price_id::text AS s, count(*) AS n"
            " FROM luot_vat_tu WHERE visit_id = $1::uuid AND bo_luc IS NULL"
            " AND order_id IS NOT NULL GROUP BY 1, 2 HAVING count(*) > 1",
            lt.visit,
        ):
            vo.append(f"B3 trùng dòng sống {r['o']}/{r['s']} ×{r['n']}")

        # B4 — dòng đã thu không bị đóng dấu bỏ.
        for r in await conn.fetch(
            """
            SELECT v.id::text AS id FROM luot_vat_tu v
             WHERE v.visit_id = $1::uuid AND v.bo_luc IS NOT NULL
               AND EXISTS (
                    SELECT 1 FROM payment_bill_line bl
                      JOIN payment_cycle c
                        ON c.clinic_id = bl.clinic_id
                       AND c.payment_cycle_id = bl.payment_cycle_id
                     WHERE bl.source_type = 'vat_tu' AND bl.source_id = v.id::text
                       AND c.status IN ('PENDING_VERIFICATION', 'PAID'))
            """,
            lt.visit,
        ):
            vo.append(f"B4 dòng đã thu bị bỏ ngầm {r['id']}")

        # B5 — bên nhận sự kiện không kẹt RETRY / DEAD ở sự kiện của lượt.
        hong = await conn.fetch(
            "SELECT d.consumer, d.status, d.last_error FROM event_delivery d"
            " JOIN domain_event e ON e.event_id = d.event_id"
            " WHERE e.aggregate_id = $1::uuid AND d.status IN ('RETRY', 'DEAD')",
            lt.visit,
        )
        for r in hong:
            vo.append(f"B5 {r['consumer']} {r['status']}: {r['last_error']}")
    return vo


SO_LUOT_NGAU_NHIEN = 40
SO_BUOC = 10


async def test_bam_lon_xon_bio_khong_lech(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    lech: list[str] = []
    chay: Counter[str] = Counter()
    bi_chan: Counter[str] = Counter()
    db_chan: list[str] = []
    so_lan_kiem = 0
    for hat in range(SO_LUOT_NGAU_NHIEN):
        rnd = random.Random(hat)
        lt = await _luot(pool, ca, chon=rnd.choice(["ca_hai", "ca_hai", "a", "b"]))
        da_lam: list[str] = []
        for _ in range(SO_BUOC):
            ten = rnd.choice(sorted(VIEC))
            try:
                await VIEC[ten](pool, lt, rnd)
            except (ClinicAIBaseException, AssertionError):
                bi_chan[ten] += 1  # màn không cho — người thật cũng bị chặn
                continue
            except asyncpg.PostgresError as e:
                db_chan.append(f"hạt {hat}: {' → '.join([*da_lam, ten])} ⇒ {e}")
                continue
            chay[ten] += 1
            da_lam.append(ten)
            vo = await _lech(pool, lt)
            so_lan_kiem += 1
            if vo:
                lech.append(f"hạt {hat}: {' → '.join(da_lam)} ⇒ {'; '.join(vo)}")
                break
    print(
        "\n".join(
            [
                "",
                f"BƯỚC CHẠY ĐƯỢC: {dict(chay)}",
                f"BƯỚC BỊ CHẶN: {dict(bi_chan)}",
                f"SỐ LẦN KIỂM: {so_lan_kiem}",
                "DB TỰ CHẶN (lỗi 500):",
                *db_chan,
                "LỆCH TÌM ĐƯỢC:",
                *(lech or ["(không)"]),
            ]
        )
    )
    assert lech == [] and db_chan == []
    # Bài phải THẬT SỰ bấm vào chỗ có tiền, không chỉ bị chặn hết.
    assert chay["bs_chon_bio_1"] + chay["bs_chon_bio_nhieu"] >= 40
    assert chay["thu_tien_mat"] >= 10 and chay["huy_chi_dinh"] >= 10
