"""Liệu trình — quầy thu đúng số khi HUỶ BUỔI / DỪNG liệu trình (31/10/2026).

Mỗi bài là một ca đã tái hiện sai ở quầy (``/api/cashier`` bảng dịch vụ +
khối liệu trình ``LieuTrinhTienService.quay``), assert đúng số nghiệp vụ:

  a   trả trước cả gói, buổi đang kê phủ → "còn trả trước" = số máy chủ cho hoàn
  a2  buổi 1 thu lẻ + trả hết, huỷ buổi 1 → tiền GIỮ TRONG GÓI (Tuyền chốt)
  a3  [Trả hết] chưa thu, huỷ buổi hôm nay → hoá đơn vẫn đủ gói
  b   trả trước 2/5, buổi 3 thu lẻ rồi huỷ → gói đã trả 3, buổi kế được phủ
  b2  buổi phủ chưa bắt đầu: hoàn được cả nó, kèm câu "buổi đang kê vào hoá đơn"
  c   trả theo buổi, buổi 2 thu rồi huỷ → giữ trong gói, buổi 3 được phủ
  d   buổi thu có giảm giá rồi huỷ → giữ 1 buổi, hoàn đúng số đã thu
  e   dừng khi đã trả trước + buổi đang kê → hết đòi tiền, buổi đang kê vẫn của gói
  e2  dừng (trả theo buổi) rồi huỷ buổi đã thu → giữ trong gói, hoàn ở quầy
  e3  dừng khi trả trước chưa thu → hoá đơn không đòi, mở lại là về

Giá thử ``GIA`` = 1.000đ/buổi (xem ``test_lieu_trinh_db``).
"""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.hoan_tac_service import HoanTacService, tien_thua_cua_luot
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from clinicai.services.lieu_trinh_tien import (
    LieuTrinhTienService,
    cau_hoan,
    toi_da_tra_truoc,
)
from clinicai.services.payment_service import PaymentService
from clinicai.services.so_sua_chi_dinh_service import SoSuaChiDinhService
from clinicai.services.tien_thua_service import tien_thua_khi_ve
from tests.services.test_lieu_trinh_db import (
    GIA,
    LT,
    _khoa,
    buoi_song,
    chi_dinh,
    doc,
    dung_ca,
    lam_xong,
    luot,
    tao,
)
from tests.services.test_lieu_trinh_tien_db import (
    hoa_don,
    khoi,
    lt_da_tra_truoc,
    thu,
    tra_truoc,
)
from tests.services.test_luot_kham_service_db import CLINIC

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


# ── Công cụ ─────────────────────────────────────────────────────────────────


async def huy(ca: LT, order: str) -> dict[str, Any]:
    return await HoanTacService(ca.pool).huy_chi_dinh(
        order_id=order, identity=ca.bac_si, xac_nhan=True, ly_do="Khách đổi ý"
    )


async def khoi_phuc(ca: LT, order: str) -> dict[str, Any]:
    so = await ca.pool.fetchval(
        "SELECT id::text FROM so_sua_chi_dinh WHERE service_order_id = $1::uuid"
        " AND hanh_dong = 'BO' AND hoan_tac_luc IS NULL ORDER BY luc DESC LIMIT 1",
        order,
    )
    assert so is not None
    return await SoSuaChiDinhService(ca.pool).hoan_tac(so_id=so, identity=ca.bac_si)


async def quay(ca: LT, visit: str) -> dict[str, Any] | None:
    """Dòng của lượt trên bảng quầy dịch vụ (None = lượt không ở quầy)."""
    b = await CashierBoardService(ca.pool).board(
        identity=ca.thu_ngan, modes=["dich_vu"]
    )
    ds = [i for i in b["items"] if i["visit_id"] == visit]
    return ds[0] if ds else None


async def khong_tien_thua(ca: LT, visit: str) -> None:
    """Quầy không hiện tiền thừa, check-out không chặn vì tiền thừa."""
    async with ca.pool.acquire() as conn:
        thua = await tien_thua_cua_luot(conn, CLINIC, [visit])
        ve = await tien_thua_khi_ve(conn, CLINIC, visit)
    assert visit not in thua
    assert (ve["tong"], ve["chan"]) == (0, False)
    i = await quay(ca, visit)
    assert i is None or not i.get("tien_thua")


async def bat_bien(ca: LT, lt_id: str) -> None:
    loi = await ca.pool.fetch(
        "SELECT loai, chi_tiet FROM bat_bien_lieu_trinh($1::uuid)"
        " WHERE lieu_trinh_id = $2::uuid",
        CLINIC,
        lt_id,
    )
    assert [dict(r) for r in loi] == []


async def so_tien(ca: LT, visit: str) -> tuple[int, int]:
    """(đã thu, đã hoàn) dịch vụ của lượt — sổ tiền thật."""
    r = await ca.pool.fetchrow(
        "SELECT coalesce((SELECT sum(amount) FROM payment WHERE visit_id = $1::uuid"
        "                  AND kind = 'dich_vu'), 0) AS thu,"
        "       coalesce((SELECT sum(amount) FROM payment_refund"
        "                  WHERE visit_id = $1::uuid AND status = 'COMPLETED'), 0)"
        "           AS hoan",
        visit,
    )
    return int(r["thu"]), int(r["hoan"])


def so(k: dict[str, Any], *ten: str) -> tuple[Any, ...]:
    return tuple(k[t] for t in ten)


async def hoan(ca: LT, dong: dict[str, Any], sl: int) -> dict[str, Any]:
    return await HoanTienService(ca.pool).tao(
        identity=ca.thu_ngan,
        payment_cycle_id=dong["payment_cycle_id"],
        visit_id=dong["visit_id"],
        kind="dich_vu",
        dong=[{"payment_bill_line_id": dong["payment_bill_line_id"], "so_luong": sl}],
        method="CASH",
        reason="Khách dừng liệu trình",
    )


async def dung_lt(ca: LT, lt_id: str) -> dict[str, Any]:
    d = await doc(ca, lt_id)
    kq = await ca.svc.dung(
        identity=ca.bac_si,
        lieu_trinh_id=lt_id,
        expected_revision=d["revision"],
        ly_do="Khách thôi",
        idempotency_key=_khoa(),
    )
    return dict(kq["lieu_trinh"])


async def mo_lai(ca: LT, lt_id: str) -> dict[str, Any]:
    d = await doc(ca, lt_id)
    kq = await ca.svc.mo_lai(
        identity=ca.bac_si,
        lieu_trinh_id=lt_id,
        expected_revision=d["revision"],
        idempotency_key=_khoa(),
    )
    return dict(kq["lieu_trinh"])


async def hoan_tac_lt(ca: LT, lt_id: str) -> dict[str, Any]:
    d = await doc(ca, lt_id)
    hid = await ca.pool.fetchval(
        "SELECT id::text FROM lieu_trinh_lich_su WHERE lieu_trinh_id = $1::uuid"
        " ORDER BY revision DESC LIMIT 1",
        lt_id,
    )
    kq = await ca.svc.hoan_tac(
        identity=ca.bac_si,
        lieu_trinh_id=lt_id,
        lich_su_id=hid,
        expected_revision=d["revision"],
        idempotency_key=_khoa(),
    )
    return dict(kq["lieu_trinh"])


# ── Luật thuần ──────────────────────────────────────────────────────────────


def test_toi_da_dung_hoac_het_buoi_la_0() -> None:
    def td(**kw: Any) -> int:
        return toi_da_tra_truoc(
            so_buoi=5, da_tra=1, tra_le=0, cho_noi_khac=0, buoi_hom_nay=0, **kw
        )

    assert td() == 4 and td(con_lai=3) == 4
    assert td(dung=True) == 0 and td(con_lai=0) == 0


def test_cau_hoan() -> None:
    assert cau_hoan(dung=False, hoan_duoc=0, phu_chua_lam=1) is None
    assert cau_hoan(dung=False, hoan_duoc=3, phu_chua_lam=0) is None
    assert (
        cau_hoan(dung=False, hoan_duoc=3, phu_chua_lam=1)
        == "Hoàn quá 2 buổi thì buổi đang kê sẽ vào hoá đơn."
    )
    assert (
        cau_hoan(dung=False, hoan_duoc=1, phu_chua_lam=1)
        == "Hoàn tiền thì buổi đang kê sẽ vào hoá đơn."
    )
    assert cau_hoan(dung=True, hoan_duoc=4, phu_chua_lam=0) == (
        "Đã dừng, còn 4 buổi đã trả chưa dùng — hoàn bằng [Hoàn tiền] ở tab"
        " “Đã thanh toán”."
    )


# ── Ca a…e3 ─────────────────────────────────────────────────────────────────


@pytest.mark.db
@pytest.mark.asyncio
async def test_a_tra_truoc_ca_goi_buoi_dang_ke_phu(pool: asyncpg.Pool) -> None:
    """a: trả trước 5/5, đã làm 2, buổi 3 đang kê (phủ). "Còn trả trước" = 3
    (buổi chưa bắt đầu chưa tiêu tiền) = đúng số máy chủ cho hoàn; hoàn 4 bị
    chặn. Huỷ buổi 3 → vẫn 3, hết câu cảnh báo."""
    ca = await dung_ca(pool)
    lt, _ = await lt_da_tra_truoc(ca, 5, 5)
    for _i in range(2):
        v = await luot(ca, dieu_tri=True)
        await lam_xong(ca, await chi_dinh(ca, v))
    v3 = await luot(ca, dieu_tri=True)
    o3 = await chi_dinh(ca, v3)
    assert (await buoi_song(ca, o3))["tra_truoc"]  # type: ignore[index]
    k = await khoi(ca, v3, lt["id"])
    assert so(k, "da_tra", "con_tra_truoc", "chua_tra", "hoan_duoc_toi_da") == (
        5,
        3,
        0,
        3,
    )
    assert k["tra_truoc_toi_da"] == 0
    assert k["cau_hoan"] == "Hoàn quá 2 buổi thì buổi đang kê sẽ vào hoá đơn."
    (dong,) = k["dong_hoan_duoc"]
    with pytest.raises(LuotKhamConflictError) as e:
        await hoan(ca, dong, 4)
    assert e.value.error_code == "PHU_VUOT_DA_TRA"
    kq = await huy(ca, o3)
    assert (kq["tien_thua"], kq["giu_trong_lieu_trinh"]) == (0, 0)
    k = await khoi(ca, v3, lt["id"])
    assert so(k, "da_tra", "con_tra_truoc", "chua_tra", "hoan_duoc_toi_da") == (
        5,
        3,
        0,
        3,
    )
    assert k["cau_hoan"] is None
    await khong_tien_thua(ca, v3)
    await bat_bien(ca, lt["id"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_a2_tra_het_cung_ngay_huy_buoi_1_giu_trong_goi(
    pool: asyncpg.Pool,
) -> None:
    """a2 (Tuyền chốt): gói 5 buổi, thu 1 lẻ + trả trước 4 = 5.000đ. Huỷ buổi
    1 → gói vẫn đã trả 5, quầy KHÔNG có tiền thừa, KHÔNG đòi thêm; sổ tiền
    không đổi. Hoàn tác huỷ → về đúng như cũ."""
    ca = await dung_ca(pool)
    v = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v)
    lt = await tao(ca, v, 5, order=o)
    assert (await tra_truoc(ca, v, lt["id"], "het"))["so_buoi"] == 4
    assert (await hoa_don(ca, v)).tong == 5 * GIA
    await thu(ca, v)
    k = await khoi(ca, v, lt["id"])
    assert so(k, "da_tra", "tra_le", "chua_tra", "con_tra_truoc") == (4, 1, 0, 4)

    kq = await huy(ca, o)
    assert (kq["da_thu_tien"], kq["tien_thua"], kq["giu_trong_lieu_trinh"]) == (
        True,
        0,
        GIA,
    )
    k = await khoi(ca, v, lt["id"])
    assert so(k, "da_tra", "tra_le", "chua_tra", "tien_con_lai") == (5, 0, 0, 0)
    assert so(k, "con_tra_truoc", "hoan_duoc_toi_da", "tra_truoc_toi_da") == (5, 5, 0)
    assert sorted((d["loai"], d["con_hoan_duoc"]) for d in k["dong_hoan_duoc"]) == [
        ("buoi_giu", 1),
        ("tra_truoc", 4),
    ]
    assert (await hoa_don(ca, v)).dong == []
    i = await quay(ca, v)
    assert i is None or (i["quay_thu"]["tong"], i["cho_thu"]) == (0, False)
    await khong_tien_thua(ca, v)
    assert await so_tien(ca, v) == (5 * GIA, 0)
    await bat_bien(ca, lt["id"])

    # Hoàn tác huỷ → buổi 1 sống lại, là buổi thu lẻ như cũ.
    await khoi_phuc(ca, o)
    b = await buoi_song(ca, o)
    assert b is not None and b["lt"] == lt["id"] and not b["tra_truoc"]
    k = await khoi(ca, v, lt["id"])
    assert so(k, "da_tra", "tra_le", "chua_tra", "con_tra_truoc") == (4, 1, 0, 4)
    assert (await hoa_don(ca, v)).dong == []
    await khong_tien_thua(ca, v)
    await bat_bien(ca, lt["id"])

    # Huỷ lại → buổi kế (lượt mới) dùng đúng tiền gói đang giữ, 0đ.
    await huy(ca, o)
    v2 = await luot(ca, dieu_tri=True)
    o2 = await chi_dinh(ca, v2)
    assert (await buoi_song(ca, o2))["tra_truoc"]  # type: ignore[index]
    assert (await hoa_don(ca, v2)).dong == []
    await bat_bien(ca, lt["id"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_a2_dat_lai_khi_tien_giu_da_dung_cho_buoi_da_lam_thi_409(
    pool: asyncpg.Pool,
) -> None:
    """Tiền buổi lẻ đã huỷ (giữ trong gói) đã phủ một buổi ĐÃ LÀM → đặt lại
    chỉ định cũ sẽ làm buổi ấy mất tiền → 409 có câu, không 500."""
    ca = await dung_ca(pool)
    v = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v)
    lt = await tao(ca, v, 2, order=o)
    await tra_truoc(ca, v, lt["id"], "het")
    await thu(ca, v)
    await huy(ca, o)
    for _i in range(2):
        vx = await luot(ca, dieu_tri=True)
        ox = await chi_dinh(ca, vx)
        assert (await buoi_song(ca, ox))["tra_truoc"]  # type: ignore[index]
        await lam_xong(ca, ox)
    with pytest.raises(LuotKhamConflictError) as e:
        await khoi_phuc(ca, o)
    assert e.value.error_code == "PHU_VUOT_DA_TRA"
    assert "không đặt lại được" in e.value.message
    await bat_bien(ca, lt["id"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_a3_tra_het_chua_thu_huy_buoi_hom_nay_hoa_don_van_du_goi(
    pool: asyncpg.Pool,
) -> None:
    """a3: [Trả hết] (1 lẻ + trả trước 4) CHƯA thu, huỷ buổi hôm nay → hoá đơn
    vẫn đúng 5 buổi = 5.000đ (không chốt cứng 4); thu xong gói đã trả 5."""
    ca = await dung_ca(pool)
    v = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v)
    lt = await tao(ca, v, 5, order=o)
    await tra_truoc(ca, v, lt["id"], "het")
    k = await khoi(ca, v, lt["id"])
    assert k["tra_truoc_dang_chon"]["so_buoi"] == 4
    assert k["tra_truoc_dang_chon"]["tra_het"] is True
    kq = await huy(ca, o)
    assert (kq["tien_thua"], kq["giu_trong_lieu_trinh"]) == (0, 0)
    hd = await hoa_don(ca, v)
    assert [(d.source_type, int(d.so_luong)) for d in hd.dong] == [("lieu_trinh", 5)]
    assert hd.tong == 5 * GIA
    k = await khoi(ca, v, lt["id"])
    assert k["tra_truoc_dang_chon"]["so_buoi"] == 5 and k["tra_truoc_toi_da"] == 5
    cyc = await thu(ca, v)
    assert (await doc(ca, lt["id"]))["da_tra"] == 5
    # Số đã thu chốt vào dòng ý định (đối chiếu ảnh chụp, đang chờ thu nơi khác).
    assert (
        await pool.fetchval(
            "SELECT t.so_buoi FROM lieu_trinh_tra_truoc t JOIN payment_bill_line bl"
            "  ON bl.source_id = t.id::text WHERE bl.payment_cycle_id = $1::uuid",
            cyc,
        )
        == 5
    )
    assert await so_tien(ca, v) == (5 * GIA, 0)
    await bat_bien(ca, lt["id"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_b_tra_truoc_2_tren_5_buoi_3_thu_le_roi_huy(pool: asyncpg.Pool) -> None:
    """b: trả trước 2/5, buổi 1–2 phủ đã làm, buổi 3 thu lẻ rồi huỷ → gói đã
    trả 3 (2 trước + 1 giữ), còn trả trước 1, chưa trả 2; không tiền thừa;
    buổi kế được phủ 0đ."""
    ca = await dung_ca(pool)
    lt, _ = await lt_da_tra_truoc(ca, 5, 2)
    for _i in range(2):
        v = await luot(ca, dieu_tri=True)
        await lam_xong(ca, await chi_dinh(ca, v))
    v3 = await luot(ca, dieu_tri=True)
    o3 = await chi_dinh(ca, v3)
    assert (await hoa_don(ca, v3)).tong == GIA
    await thu(ca, v3)
    kq = await huy(ca, o3)
    assert (kq["tien_thua"], kq["giu_trong_lieu_trinh"]) == (0, GIA)
    k = await khoi(ca, v3, lt["id"])
    assert so(k, "da_tra", "tra_le", "con_tra_truoc", "chua_tra", "tien_con_lai") == (
        3,
        0,
        1,
        2,
        2 * GIA,
    )
    await khong_tien_thua(ca, v3)
    v4 = await luot(ca, dieu_tri=True)
    o4 = await chi_dinh(ca, v4)
    assert (await buoi_song(ca, o4))["tra_truoc"]  # type: ignore[index]
    assert (await hoa_don(ca, v4)).dong == []
    await bat_bien(ca, lt["id"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_b2_buoi_phu_chua_bat_dau_hoan_duoc_kem_canh_bao(
    pool: asyncpg.Pool,
) -> None:
    """b2: trả trước 2/5, buổi 1 đã làm, buổi 2 phủ CHƯA bắt đầu → còn trả
    trước 1 (trước: 0), máy chủ cho hoàn đúng 1 và buổi đang kê vào hoá đơn —
    câu cho thu ngân nói trước. Huỷ buổi 2 → không đòi gì."""
    ca = await dung_ca(pool)
    lt, _ = await lt_da_tra_truoc(ca, 5, 2)
    v1 = await luot(ca, dieu_tri=True)
    await lam_xong(ca, await chi_dinh(ca, v1))
    v2 = await luot(ca, dieu_tri=True)
    o2 = await chi_dinh(ca, v2)
    assert (await buoi_song(ca, o2))["tra_truoc"]  # type: ignore[index]
    k = await khoi(ca, v2, lt["id"])
    assert so(k, "con_tra_truoc", "hoan_duoc_toi_da", "phu_chua_lam") == (1, 1, 1)
    assert k["cau_hoan"] == "Hoàn tiền thì buổi đang kê sẽ vào hoá đơn."
    (dong,) = k["dong_hoan_duoc"]
    await hoan(ca, dong, 1)
    assert not (await buoi_song(ca, o2))["tra_truoc"]  # type: ignore[index]
    assert [d.source_id for d in (await hoa_don(ca, v2)).dong] == [o2]
    await huy(ca, o2)
    assert (await hoa_don(ca, v2)).dong == []
    k = await khoi(ca, v2, lt["id"])
    assert so(k, "da_tra", "con_tra_truoc", "chua_tra", "hoan_duoc_toi_da") == (
        1,
        0,
        4,
        0,
    )
    await khong_tien_thua(ca, v2)
    await bat_bien(ca, lt["id"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_c_tra_theo_buoi_buoi_2_thu_roi_huy(pool: asyncpg.Pool) -> None:
    """c: trả theo buổi — buổi 1 thu + làm, buổi 2 thu rồi huỷ → gói giữ 1
    buổi (đã trả 1, thu lẻ 1, chưa trả 3), buổi 3 được phủ 0đ."""
    ca = await dung_ca(pool)
    v1 = await luot(ca, dieu_tri=True)
    o1 = await chi_dinh(ca, v1)
    lt = await tao(ca, v1, 5, order=o1)
    await thu(ca, v1)
    await lam_xong(ca, o1)
    v2 = await luot(ca, dieu_tri=True)
    o2 = await chi_dinh(ca, v2)
    await thu(ca, v2)
    kq = await huy(ca, o2)
    assert (kq["tien_thua"], kq["giu_trong_lieu_trinh"]) == (0, GIA)
    k = await khoi(ca, v2, lt["id"])
    assert so(k, "da_tra", "tra_le", "chua_tra", "con_tra_truoc") == (1, 1, 3, 1)
    await khong_tien_thua(ca, v2)
    v3 = await luot(ca, dieu_tri=True)
    o3 = await chi_dinh(ca, v3)
    assert (await buoi_song(ca, o3))["tra_truoc"]  # type: ignore[index]
    assert (await hoa_don(ca, v3)).dong == []
    await bat_bien(ca, lt["id"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_d_buoi_thu_giam_gia_roi_huy_hoan_dung_so_da_thu(
    pool: asyncpg.Pool,
) -> None:
    """d: buổi thu có giảm 20% (800đ) rồi huỷ → giữ 1 buổi trong gói, không
    tiền thừa; dừng + hoàn dòng ấy → hoàn đúng 800đ, sổ tiền cân về 0."""
    ca = await dung_ca(pool)
    v = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v)
    lt = await tao(ca, v, 5, order=o)
    hd = await hoa_don(ca, v)
    await PaymentService(pool).record_payment(
        visit_id=v,
        kind="dich_vu",
        amount=None,
        clinic_patient_id=None,
        identity=ca.thu_ngan,
        bill_revision=hd.revision,
        method="CASH",
        idempotency_key=_khoa(),
        quay="dich_vu",
        discount_type="PERCENT",
        discount_value=20,
        discount_reason="Khách quen",
    )
    assert await so_tien(ca, v) == (GIA * 8 // 10, 0)
    kq = await huy(ca, o)
    assert (kq["tien_thua"], kq["giu_trong_lieu_trinh"]) == (0, GIA * 8 // 10)
    await khong_tien_thua(ca, v)
    await dung_lt(ca, lt["id"])
    k = await khoi(ca, v, lt["id"])
    assert so(k, "da_tra", "con_tra_truoc", "hoan_duoc_toi_da", "chua_tra") == (
        1,
        1,
        1,
        0,
    )
    (dong,) = k["dong_hoan_duoc"]
    assert (dong["loai"], dong["con_hoan_duoc"]) == ("buoi_giu", 1)
    r = await hoan(ca, dong, 1)
    assert int(r["amount"]) == GIA * 8 // 10
    assert await so_tien(ca, v) == (GIA * 8 // 10, GIA * 8 // 10)
    assert (await doc(ca, lt["id"]))["da_tra"] == 0
    await khong_tien_thua(ca, v)
    await bat_bien(ca, lt["id"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_e_dung_khi_da_tra_truoc_va_buoi_dang_ke(pool: asyncpg.Pool) -> None:
    """e: 10 buổi, trả trước 5, làm 1, buổi 2 đang kê (phủ). Trước dừng: còn trả
    trước 4, hoàn quá 3 thì buổi đang kê vào hoá đơn. Dừng (Tuyền chốt 30/10:
    có hiệu lực SAU buổi đang kê) → hết "chưa trả", tắt ô trả trước; buổi 2 VẪN
    của gói, phủ 0đ. Mở lại / hoàn tác qua lại không đổi tiền. Khách không làm
    → huỷ buổi 2 → hoàn đủ 4 buổi theo giá gói."""
    ca = await dung_ca(pool)
    lt, _ = await lt_da_tra_truoc(ca, 10, 5)
    v1 = await luot(ca, dieu_tri=True)
    await lam_xong(ca, await chi_dinh(ca, v1))
    v2 = await luot(ca, dieu_tri=True)
    o2 = await chi_dinh(ca, v2)
    k = await khoi(ca, v2, lt["id"])
    assert so(k, "con_tra_truoc", "hoan_duoc_toi_da", "chua_tra") == (4, 4, 5)
    assert k["cau_hoan"] == "Hoàn quá 3 buổi thì buổi đang kê sẽ vào hoá đơn."

    async def da_dung() -> None:
        b = await buoi_song(ca, o2)
        assert b is not None and b["lt"] == lt["id"] and b["tra_truoc"]
        assert (await hoa_don(ca, v2)).dong == []
        k = await khoi(ca, v2, lt["id"])
        assert so(k, "trang_thai", "chua_tra", "tien_con_lai") == ("DUNG", 0, 0)
        assert so(k, "con_tra_truoc", "hoan_duoc_toi_da", "tra_truoc_toi_da") == (
            4,
            4,
            0,
        )
        assert k["goi_y_tra_them"] is False
        # Đã dừng: câu quyết toán theo giá gói (mặc định) — buổi đang kê tính
        # vào gói (chi tiết ở test_lieu_trinh_chinh_sach_dung_db.py).
        assert k["cau_hoan"].startswith(
            "Tính theo giá gói: đã trả trước 5.000đ; đã dùng 2 buổi (1 đã làm, 1"
            " đang kê) × 1.000đ = 2.000đ; hoàn 3.000đ."
        )
        await khong_tien_thua(ca, v2)
        await bat_bien(ca, lt["id"])

    sau = await dung_lt(ca, lt["id"])
    assert so(sau, "con_tra_truoc", "chua_tra", "tien_con_lai") == (4, 0, 0)
    await da_dung()
    await mo_lai(ca, lt["id"])
    k = await khoi(ca, v2, lt["id"])
    assert so(k, "trang_thai", "con_tra_truoc", "chua_tra") == ("DANG_LAM", 4, 5)
    await hoan_tac_lt(ca, lt["id"])
    await da_dung()

    await huy(ca, o2)
    k = await khoi(ca, v2, lt["id"])
    assert so(k, "con_tra_truoc", "hoan_duoc_toi_da", "phu_chua_lam") == (4, 4, 0)
    (dong,) = k["dong_hoan_duoc"]
    await hoan(ca, dong, 4)
    d = await doc(ca, lt["id"])
    assert so(d, "da_tra", "con_tra_truoc") == (1, 0)
    await bat_bien(ca, lt["id"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_e2_dung_tra_theo_buoi_roi_huy_buoi_da_thu(pool: asyncpg.Pool) -> None:
    """e2: trả theo buổi, buổi 1 làm, buổi 2 đã thu chưa làm; dừng → không
    đòi buổi nào, buổi 2 (đã thu) vẫn của gói. Huỷ buổi 2 → tiền giữ trong
    gói (không tiền thừa); quầy chỉ đường hoàn đúng 1 buổi."""
    ca = await dung_ca(pool)
    v1 = await luot(ca, dieu_tri=True)
    o1 = await chi_dinh(ca, v1)
    lt = await tao(ca, v1, 10, order=o1)
    await thu(ca, v1)
    await lam_xong(ca, o1)
    v2 = await luot(ca, dieu_tri=True)
    o2 = await chi_dinh(ca, v2)
    await thu(ca, v2)
    sau = await dung_lt(ca, lt["id"])
    assert so(sau, "trang_thai", "chua_tra", "tien_con_lai", "tra_le") == (
        "DUNG",
        0,
        0,
        2,
    )
    assert (await buoi_song(ca, o2)) is not None
    q = await LieuTrinhTienService(ca.pool).quay(identity=ca.thu_ngan, visit_id=v2)
    assert [x["id"] for x in q["lieu_trinh"]] == []
    kq = await huy(ca, o2)
    assert (kq["tien_thua"], kq["giu_trong_lieu_trinh"]) == (0, GIA)
    await khong_tien_thua(ca, v2)
    k = await khoi(ca, v2, lt["id"])
    assert so(k, "da_tra", "tra_le", "con_tra_truoc", "chua_tra") == (1, 1, 1, 0)
    assert so(k, "hoan_duoc_toi_da", "tra_truoc_toi_da") == (1, 0)
    assert [d["loai"] for d in k["dong_hoan_duoc"]] == ["buoi_giu"]
    assert k["cau_hoan"].startswith(
        "Tính theo giá gói: đã trả trước 1.000đ; chưa dùng buổi nào; hoàn 1.000đ."
    )
    await bat_bien(ca, lt["id"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_e3_dung_khi_tra_truoc_chua_thu_hoa_don_khong_doi(
    pool: asyncpg.Pool,
) -> None:
    """e3: buổi 1 đang kê (chưa thu) + đang chọn trả trước 3; dừng → hoá đơn
    không đòi trả trước của gói đã dừng; buổi 1 vẫn của gói, tính ĐƠN GIÁ GÓI
    (bảng giá đổi không ảnh hưởng). Mở lại → trả trước 3 về như cũ."""
    ca = await dung_ca(pool)
    v = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v)
    lt = await tao(ca, v, 10, order=o)
    await tra_truoc(ca, v, lt["id"], 3)
    truoc = sorted(
        (d.source_type, int(d.so_luong)) for d in (await hoa_don(ca, v)).dong
    )
    assert truoc == [("lieu_trinh", 3), ("service_order", 1)]
    await pool.execute(
        "UPDATE service_price SET unit_price = 999000 WHERE id = $1::uuid", ca.sp
    )
    await dung_lt(ca, lt["id"])
    b = await buoi_song(ca, o)
    assert b is not None and b["lt"] == lt["id"]
    hd = await hoa_don(ca, v)
    assert [(d.source_type, int(d.thanh_tien or 0)) for d in hd.dong] == [
        ("service_order", GIA)
    ]
    q = await LieuTrinhTienService(ca.pool).quay(identity=ca.thu_ngan, visit_id=v)
    assert q["lieu_trinh"] == []
    with pytest.raises(LuotKhamConflictError) as e:
        await tra_truoc(ca, v, lt["id"], 1)
    assert e.value.error_code == "LIEU_TRINH_DA_DUNG"
    await mo_lai(ca, lt["id"])
    sau = sorted((d.source_type, int(d.so_luong)) for d in (await hoa_don(ca, v)).dong)
    assert sau == truoc
    k = await khoi(ca, v, lt["id"])
    assert k["tra_truoc_dang_chon"]["so_buoi"] == 3 and k["chua_tra"] == 10
    await bat_bien(ca, lt["id"])
