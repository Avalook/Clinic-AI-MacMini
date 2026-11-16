"""Hai trang thuốc nặng / thiếu dữ liệu vì tồn cũ (16/11/2026).

    scripts/test-nhanh.sh src/tests/services/test_giam_tai_trang_thuoc_db.py

Prod 16/11: quầy thu thuốc kéo 683 lượt (504 lượt chỉ vì sổ nợ khách PHAI_TRA,
332 trong đó chỉ còn THUỐC đã thu chưa giao — việc của Nhà thuốc); màn Nhà thuốc
lấy 300 DÒNG mới nhất trong 6.951 dòng mở, còn 56 lượt — lượt chờ giao vài hôm
trước rơi khỏi màn mà không ai biết. Quầy thuốc nay lọc theo NGÀY đang xem.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import pytest

from clinicai.core.clock import hom_nay_vn
from clinicai.events.catalogue import CONG_NO, SO_NO
from clinicai.services import ban_thuoc_service as bt
from clinicai.services import cashier_board_service as cb
from clinicai.services import so_no_service
from clinicai.services.cashier_board_service import CashierBoardService
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, _don, q, tao_quay  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _san_sang, _thu
from tests.services.test_tra_thuoc_hoan_db import _ve

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _bat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")


async def _lui(q: Quay, ngay: int) -> None:  # noqa: F811
    """Lùi MỌI mốc giờ của lượt (lượt, dòng đơn, lần thu) `ngay` ngày.

    Lần thu đã PAID bị trigger khoá (không sửa quá khứ) — chỉ trong DB test tạm,
    tắt trigger cho riêng giao dịch dựng dữ liệu này."""
    lui = "make_interval(days => $2)"
    async with q.pool.acquire() as conn, conn.transaction():
        await conn.execute("SET LOCAL session_replication_role = replica")
        for sql in (
            f"UPDATE visit SET created_at = created_at - {lui},"
            f" closed_at = closed_at - {lui}, checked_in_at = checked_in_at - {lui}"
            " WHERE visit_id = $1::uuid",
            f"UPDATE prescription SET created_at = created_at - {lui}"
            " WHERE visit_id = $1::uuid",
            f"UPDATE payment_cycle SET created_at = created_at - {lui},"
            f" paid_at = paid_at - {lui} WHERE visit_id = $1::uuid",
        ):
            await conn.execute(sql, q.visit_id, ngay)


async def _thu_chua_giao_khach_ve(q: Quay) -> None:  # noqa: F811
    """Thu tiền thuốc, CHƯA giao, khách về → sổ ghi PHAI_TRA chỉ có THUỐC."""
    await _san_sang(q, 10, 100)
    await _thu(q)
    await _ve(q)
    await chay_ben_nhan(q.pool, CONG_NO, SO_NO)


async def _loai_phai_tra(q: Quay) -> list[str]:  # noqa: F811
    ct = await q.pool.fetchval(
        "SELECT chi_tiet FROM so_no WHERE visit_id = $1::uuid AND chieu = 'PHAI_TRA'"
        " ORDER BY seq DESC LIMIT 1",
        q.visit_id,
    )
    return [d["loai"] for d in (json.loads(ct) if isinstance(ct, str) else ct or [])]


async def _tren_quay(q: Quay, modes: list[str]) -> set[str]:  # noqa: F811
    bang = await CashierBoardService(q.pool).board(identity=q.thu_ngan, modes=modes)
    return {i["visit_id"] for i in bang["items"]}


async def _man(q: Quay, **kw: Any) -> dict[str, Any]:  # noqa: F811
    return await bt.man_nha_thuoc(q.pool, identity=q.duoc_si, **kw)


def _ids(man: dict[str, Any]) -> set[str]:
    return {g["visit_id"] for g in man["luot"]}


async def test_cua_so_nha_thuoc_bang_han_quay_thu() -> None:
    # Cửa sổ "đã thu chờ giao" của Nhà thuốc = hạn đơn thuốc của quầy thu.
    assert bt.CUA_SO_SO_NGAY == cb.CU_DON_THUOC_SO_NGAY


@pytest.fixture(autouse=True)
def _tran_rong(monkeypatch: pytest.MonkeyPatch) -> None:
    """DB test chung có hàng trăm lượt hôm nay của tệp khác — trần 200 sẽ cắt
    (đúng, và màn nói ra) nhưng làm bài đỏ vì lý do khác. Trần có bài riêng."""
    monkeypatch.setattr(bt, "TRAN_LUOT", 100_000)


# ── Sửa 1: quầy thu thuốc ──────────────────────────────────────────────────


async def test_chi_con_thuoc_chua_giao_khong_vao_quay_thuoc_ma_o_nha_thuoc(
    q: Quay,  # noqa: F811
) -> None:
    await _thu_chua_giao_khach_ve(q)
    await _lui(q, 2)  # lượt hôm kia: chỉ còn vế sổ nợ kéo nó vào quầy
    assert await _loai_phai_tra(q) == [so_no_service.THUOC]
    assert q.visit_id not in await _tren_quay(q, ["thuoc"])
    # Đi đâu xem: màn Nhà thuốc — đã thu, chờ giao.
    g = next(g for g in (await _man(q))["luot"] if g["visit_id"] == q.visit_id)
    assert g["giai_doan"] == bt.DA_THU
    # Quầy gộp hai ô (CASHIER) không đổi.
    assert q.visit_id in await _tren_quay(q, ["dich_vu", "thuoc"])


# ── Quầy thuốc theo NGÀY (Tuyền 16/11) ─────────────────────────────────────


async def _bang(q: Quay, ngay: date | None = None) -> dict[str, Any]:  # noqa: F811
    return await CashierBoardService(q.pool).board(
        identity=q.thu_ngan,
        modes=["thuoc"],
        ngay=ngay.isoformat() if ngay else None,
    )


def _ngay_lui(n: int) -> date:
    return hom_nay_vn() - timedelta(days=n)


async def test_hom_nay_trong_khi_chi_co_khach_cho_ngay_cu_chon_ngay_cu_thi_hien(
    q: Quay,  # noqa: F811
) -> None:
    """ "ví dụ ngày thứ 7 14/11 thì còn khách nào chờ thanh toán ngày đó thì …
    hiện ở ngày đó để xử lý đi, còn hôm nay chưa có thì phải trống"."""
    await _san_sang(q, 10, 100)  # có đơn, CHƯA thu
    await _lui(q, 2)
    hom_nay = await _bang(q)
    assert q.visit_id not in {i["visit_id"] for i in hom_nay["items"]}
    ngay_cu = _ngay_lui(2)
    assert any(
        d["ngay"] == ngay_cu.isoformat() and d["so"] >= 1
        for d in hom_nay["ngay_khac_con_cho"]
    )
    hom_do = await _bang(q, ngay_cu)
    assert hom_do["ngay"] == ngay_cu.isoformat()
    assert q.visit_id in {i["visit_id"] for i in hom_do["items"]}
    # Đang xem ngày cũ: chính ngày ấy không nằm trong "ngày khác".
    assert all(d["ngay"] != ngay_cu.isoformat() for d in hom_do["ngay_khac_con_cho"])


async def test_ngay_khac_dem_dung_va_luot_da_thu_khong_la_cho(q: Quay) -> None:  # noqa: F811
    """Hai khách chưa thu ở cùng một ngày cũ → đếm; thu xong một khách thì số
    giảm đúng một, và khách đã thu nằm ở `paid` (không phải chờ thanh toán)."""
    ngay = _ngay_lui(17)
    b = await tao_quay(q.pool)
    for x in (q, b):
        await _san_sang(x, 10, 100)
        await _lui(x, 17)

    def _so(bang: dict[str, Any]) -> int:
        return next(
            (
                d["so"]
                for d in bang["ngay_khac_con_cho"]
                if d["ngay"] == ngay.isoformat()
            ),
            0,
        )

    truoc = _so(await _bang(q))
    assert truoc >= 2
    assert (
        next(
            d
            for d in (await _bang(q))["ngay_khac_con_cho"]
            if d["ngay"] == ngay.isoformat()
        )["nhan"]
        == f"{cb._THU_VN[ngay.weekday()]} {ngay:%d/%m}"
    )
    await _thu(q)
    assert _so(await _bang(q)) == truoc - 1
    hom_do = await _bang(q, ngay)
    assert {"visit_id": q.visit_id, "kind": "thuoc"} in hom_do["paid"]
    assert b.visit_id in {i["visit_id"] for i in hom_do["items"]}
    assert {"visit_id": b.visit_id, "kind": "thuoc"} not in hom_do["paid"]


async def test_quay_dich_vu_khong_doi_va_khong_co_ngay_khac(q: Quay) -> None:  # noqa: F811
    bang = await CashierBoardService(q.pool).board(
        identity=q.thu_ngan, modes=["dich_vu"]
    )
    assert "ngay_khac_con_cho" not in bang


# ── Sửa 2: màn Nhà thuốc ───────────────────────────────────────────────────


async def _don_cu_chua_thu(q: Quay, so_dong: int, ngay: int) -> None:  # noqa: F811
    """`so_dong` dòng đơn chưa thu của lượt `q`, lượt + dòng lùi `ngay` ngày."""
    await q.pool.execute(
        "INSERT INTO prescription (clinic_id, source_ref, visit_id,"
        " clinic_patient_id, drug_name_raw, quantity, quantity_num, unit)"
        " SELECT $1::uuid, 'test-rx-cu-' || $3 || '-' || g, v.visit_id,"
        " v.clinic_patient_id, 'thuoc cu', '1 viên', 1, 'viên'"
        " FROM visit v, generate_series(1, $2) g WHERE v.visit_id = $4::uuid",
        CLINIC,
        so_dong,
        q.duoi,
        q.visit_id,
    )
    await _lui(q, ngay)


async def test_nha_thuoc_khong_cat_luot_con_viec_khi_co_hon_300_dong_cu(
    q: Quay,  # noqa: F811
) -> None:
    """301 dòng chưa thu MỚI hơn lượt chờ giao (bản cũ: 300 dòng mới nhất → lượt
    chờ giao rơi khỏi màn, im lặng). Nay lượt chờ giao + lượt hôm nay đều hiện;
    lượt rác ngoài cửa sổ được đếm, không dựng."""
    await _san_sang(q, 10, 100)
    await _thu(q)
    await _lui(q, 3)  # đã thu 3 hôm trước, chưa giao
    rac = await tao_quay(q.pool)
    await _don_cu_chua_thu(rac, 301, 2)
    hom_nay = await tao_quay(q.pool)
    await _don(hom_nay, 2)

    man = await _man(q)
    ids = _ids(man)
    assert q.visit_id in ids, "lượt chờ giao trong cửa sổ không được rơi khỏi màn"
    assert hom_nay.visit_id in ids
    assert rac.visit_id not in ids
    assert man["luot_cu_an"] >= 1 and man["bi_cat"] is False
    assert man["tong"] == len([g for g in man["luot"] if g["dong"]])


async def test_tim_duoc_luot_cu_ngoai_cua_so(q: Quay) -> None:  # noqa: F811
    await _don_cu_chua_thu(q, 3, 10)
    assert q.visit_id not in _ids(await _man(q))
    man = await _man(q, tim=f"TT-{q.duoi}")
    assert _ids(man) == {q.visit_id} and man["tim"] == f"TT-{q.duoi}"
    assert len(next(iter(man["luot"]))["dong"]) == 3
    # Rác / quá ngắn = màn thường, không ném.
    for rac in ("x", 123, None, "   "):
        thuong = await _man(q, tim=rac)
        assert thuong["tim"] is None and q.visit_id not in _ids(thuong)


async def test_da_thu_qua_7_ngay_an_ck_cho_cu_van_hien(q: Quay) -> None:  # noqa: F811
    """Đã thu (TM) 10 hôm trước chưa giao: ngoài cửa sổ, được đếm; CK CHỜ XÁC
    MINH 10 hôm trước: tiền đang treo — luôn hiện."""
    await _san_sang(q, 10, 100)
    await _thu(q)
    await _lui(q, 10)
    man = await _man(q)
    assert q.visit_id not in _ids(man) and man["luot_cu_an"] >= 1
    assert q.visit_id in _ids(await _man(q, tim=f"TT-{q.duoi}"))

    ck = await tao_quay(q.pool)
    await _san_sang(ck, 10, 100)
    await _thu(ck, "TRANSFER")
    await _lui(ck, 10)
    assert ck.visit_id in _ids(await _man(ck))


async def test_tim_khop_qua_nhieu_khach_thi_noi_ra(
    q: Quay,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _don(q, 1)
    khac = await tao_quay(q.pool)
    await _don(khac, 1)
    monkeypatch.setattr(bt, "TRAN_TIM_KHACH", 1)
    man = await _man(q, tim="BN thử tiền thuốc")  # tên chung của mọi khách thử
    assert man["tim_bi_cat"] is True
    assert (await _man(q, tim=f"TT-{q.duoi}"))["tim_bi_cat"] is False


async def test_cham_tran_luot_thi_noi_ra(
    q: Quay,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _don(q, 1)
    khac = await tao_quay(q.pool)
    await _don(khac, 1)
    monkeypatch.setattr(bt, "TRAN_LUOT", 1)
    man = await _man(q)
    assert man["bi_cat"] is True and man["tran"] == 1 and man["tong"] >= 2
    assert len([g for g in man["luot"] if g["dong"]]) == 1
