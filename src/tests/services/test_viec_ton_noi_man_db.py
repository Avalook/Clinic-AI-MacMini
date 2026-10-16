"""G4a nối màn (14/10/2026) — việc tồn phải dẫn tới MÀN XỬ LÝ có thật.

    scripts/test-nhanh.sh src/tests/services/test_viec_ton_noi_man_db.py

Phiên điều phối bấm thật trên staging thấy: việc tồn chỉ là thẻ chữ (0 nút),
chữ "lượt đã đóng" mâu thuẫn với màn Check-out, nhãn "1 giờ" là tuổi dòng SỔ,
và quầy thu không gom lượt cũ đã đóng nên dù có nút cũng không có đích.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from clinicai.events.catalogue import CONG_NO, SO_NO
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.cong_no_service import CongNoService
from clinicai.services.danh_sach_hoa_don_service import DanhSachHoaDonService
from clinicai.services.hoan_tac_service import HoanTacService
from clinicai.services.tien_thua_service import TienThuaService
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_mo_phong_dong_tien_db import (  # noqa: F401
    _lam_truoc_thu_sau,
    _lam_xong,
    _luot,
    _thu,
    _ve,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import Ca, _dung

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _lui_luot(pool: asyncpg.Pool, visit: str, ngay: int) -> None:  # noqa: F811
    """Lùi ngày TẠO / ĐÓNG của lượt `ngay` ngày (dựng "lượt cũ")."""
    await pool.execute(
        "UPDATE visit SET created_at = created_at - make_interval(days => $2),"
        " closed_at = closed_at - make_interval(days => $2)"
        " WHERE visit_id = $1::uuid",
        visit,
        ngay,
    )


async def _ton(pool: asyncpg.Pool, visit: str) -> dict[str, dict[str, Any]]:  # noqa: F811
    """Việc tồn của đúng lượt này, theo loại."""
    async with pool.acquire() as conn:
        ds = await DanhSachHoaDonService._viec_ton(conn, CLINIC, None, None)
    return {t["loai"]: t for t in ds if t.get("visit_id") == visit}


def _dich(t: dict[str, Any]) -> dict[str, Any]:
    """Đích của nút Xử lý (bỏ phần cơ sở kèm theo)."""
    return {k: t["xu_ly"][k] for k in ("href", "nhan", "lego")}


async def _tren_quay(pool: asyncpg.Pool, ca: Ca) -> dict[str, dict[str, Any]]:  # noqa: F811
    bang = await CashierBoardService(pool).board(
        identity=ca.thu_ngan, modes=["dich_vu", "thuoc"]
    )
    return {i["visit_id"]: i for i in bang["items"]}


async def test_ghi_no_co_nut_thu_no_ve_dung_quay_va_khach(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _lam_xong(pool, ca, o)
    await CongNoService(pool).ghi(identity=ca.le_tan, visit_id=v, ly_do="Quên ví")
    await _ve(pool, ca, v)
    await chay_ben_nhan(pool, CONG_NO, SO_NO)
    t = (await _ton(pool, v))["GHI_NO"]
    assert t["kind"] == "dich_vu"
    assert _dich(t) == {
        "href": f"/thu-ngan/dich-vu?luot={v}",
        "nhan": "Thu nợ / miễn",
        "lego": "payment.service.collect",
    }
    # Ngày thật của lượt, không phải giờ dòng sổ.
    assert t["luot_ngay"] is not None and t["luot_con_mo"] is False


async def test_ck_chua_ve_co_nut_xac_nhan_o_quay(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _thu(pool, ca, v, method="TRANSFER")
    await _lam_xong(pool, ca, o)
    await _ve(pool, ca, v)
    await chay_ben_nhan(pool, CONG_NO, SO_NO)
    t = (await _ton(pool, v))["CK_CHUA_VE"]
    assert t["xu_ly"]["href"] == f"/thu-ngan/dich-vu?luot={v}"
    assert t["xu_ly"]["nhan"] == "Xác nhận đã nhận tiền"


async def test_tien_thua_lan_da_dong_mo_o_quay_va_len_quay_du_cu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Lượt đã ĐÓNG 40 ngày trước còn tiền phòng khám nợ khách: nút dẫn tới quầy
    thu, và quầy PHẢI gom lượt ấy (trước đây vế "đã về" cắt ở 30 ngày + chỉ gom
    lượt còn chỉ định chưa thu → nút mở ra "không thấy khách")."""
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _thu(pool, ca, v)
    await HoanTacService(pool).huy_chi_dinh(
        order_id=o, identity=ca.bac_si, xac_nhan=True, ly_do="Khách đổi ý"
    )
    # Máy chặn check-out khi còn tiền thừa chưa xử lý; "Giữ lại" vẫn là nợ khách.
    await TienThuaService(pool).giu_lai(
        identity=ca.thu_ngan, visit_id=v, ly_do="Khách để lại"
    )
    await _ve(pool, ca, v)
    await chay_ben_nhan(pool, CONG_NO, SO_NO)
    await _lui_luot(pool, v, 40)
    t = (await _ton(pool, v))["CHUA_TRA_LAI"]
    assert _dich(t) == {
        "href": f"/thu-ngan/dich-vu?luot={v}",
        "nhan": "Hoàn tiền thừa",
        "lego": "payment.service.collect",
    }
    assert t["luot_con_mo"] is False
    tren = await _tren_quay(pool, ca)
    assert v in tren and tren[v]["tien_thua"]["tong"] == 300_000


async def test_ck_cho_cua_luot_da_dong_qua_30_ngay_van_len_quay(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _thu(pool, ca, v, method="TRANSFER")
    await _lam_xong(pool, ca, o)
    await _ve(pool, ca, v)
    await _lui_luot(pool, v, 45)
    tren = await _tren_quay(pool, ca)
    assert v in tren, "CK chờ xác minh của lượt cũ phải có chỗ bấm 'Đã nhận tiền'"
    bang = await CashierBoardService(pool).board(
        identity=ca.thu_ngan, modes=["dich_vu", "thuoc"]
    )
    assert any(c["visit_id"] == v for c in bang["cho_xac_minh"])


async def test_quay_khong_keo_moi_luot_cu_chi_viec_ton_that(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Chốt chặn của hai nhánh mới: lượt đã đóng 45 ngày, thu đủ và đã làm xong
    (không còn khoản nào) KHÔNG được lọt vào quầy thu hôm nay."""
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _thu(pool, ca, v)
    await _lam_xong(pool, ca, o)
    await _ve(pool, ca, v)
    await chay_ben_nhan(pool, CONG_NO, SO_NO)
    await _lui_luot(pool, v, 45)
    assert v not in await _tren_quay(pool, ca)


async def test_chua_lam_luot_hom_truoc_chua_dong_noi_dung_va_dan_check_out(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Bấm thật: "lượt đã đóng" trong khi Check-out liệt kê chính khách ấy là
    lượt hôm trước CÒN MỞ. Chữ theo trạng thái lượt + nút sang Check-out."""
    ca = await _dung(pool)
    v, _o = await _luot(pool, ca)
    await _thu(pool, ca, v)  # đã thu, chưa làm, chưa đóng lượt
    await pool.execute(
        "UPDATE visit SET created_at = created_at - interval '1 day'"
        " WHERE visit_id = $1::uuid",
        v,
    )
    await chay_ben_nhan(pool, CONG_NO, SO_NO)  # sổ đọc trạng thái hiện tại
    t = (await _ton(pool, v)).get("CHUA_LAM")
    assert t is not None, "lượt hôm trước đã thu chưa làm phải là việc tồn"
    assert t["luot_con_mo"] is True
    assert "lượt hôm trước" in t["mo_ta"] and "chưa đóng" in t["mo_ta"]
    assert "lượt đã đóng" not in t["mo_ta"]
    assert t["xu_ly"]["href"] == f"/reception/checkout?luot={v}"


async def test_luot_cu_13_ngay_con_mo_xem_va_dong_duoc_qua_lien_ket(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Link `/reception/checkout?luot=` của lượt mở 13 ngày trước: màn hỏi đúng
    lượt ấy (`readiness`, không giới hạn ngày) và hiện nút Đóng lượt; đóng xong
    hỏi lại báo đã đóng. Trước đây lượt cũ không có ở đâu → link chết."""
    ca = await _dung(pool)
    v, _o = await _luot(pool, ca)
    await _thu(pool, ca, v)  # đã thu, chưa làm, chưa đóng lượt
    await pool.execute(
        "UPDATE visit SET created_at = created_at - interval '13 days',"
        " checked_in_at = checked_in_at - interval '13 days'"
        " WHERE visit_id = $1::uuid",
        v,
    )
    svc = CheckoutService(pool)
    r = await svc.readiness(identity=ca.le_tan, visit_id=v)
    assert r["visit_id"] == v and r["already_closed"] is False
    assert r["patient_name"]
    await svc.close(
        identity=ca.le_tan,
        visit_id=v,
        incomplete=True,
        incomplete_reason="Khách về từ 13 ngày trước",
    )
    assert (await svc.readiness(identity=ca.le_tan, visit_id=v))[
        "already_closed"
    ] is True
