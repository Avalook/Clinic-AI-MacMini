"""GIẢ LẬP DÒNG TIỀN — tìm lối rò TRƯỚC khi code (Tuyền 14/10/2026, G4 bước 0).

    scripts/test-nhanh.sh src/tests/services/test_mo_phong_dong_tien_db.py

Chạy đúng các lệnh thật (thu, huỷ phiếu, CK chờ, hoàn, bỏ chỉ định, ghi nợ, về)
rồi kiểm hai BẤT BIẾN KẾ TOÁN cho lượt ĐÃ VỀ:

  B1  khách còn nợ phòng khám bao nhiêu (``no_khi_ve`` — chính luật chặn
      check-out) thì "việc tồn" (``GHI_NO``) hiện ĐÚNG bấy nhiêu.
  B2  phòng khám còn nợ khách bao nhiêu (tiền thừa + đã thu chưa làm) thì việc
      tồn + "giữ lại" hiện ĐÚNG bấy nhiêu, không có hạn ngày.
  B3  hoàn tiền mặt cho khoản khách trả chuyển khoản = lệch két.

Lối rò đã biết đánh ``xfail(strict=True)``: sửa xong (G4b/G4d) thì bài tự báo
XPASS → gỡ dấu. Bài ngẫu nhiên bấm lộn xộn như người thật để bắt case chưa ai
nghĩ tới; in chuỗi thao tác gây lệch.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import AsyncIterator, Awaitable, Callable

import asyncpg
import pytest
import pytest_asyncio

from clinicai.core.exceptions import ClinicAIBaseException
from clinicai.events.catalogue import CONG_NO, SO_NO
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.cong_no_service import CongNoService, no_khi_ve
from clinicai.services.danh_sach_hoa_don_service import DanhSachHoaDonService
from clinicai.services.doi_hinh_thuc_service import DoiHinhThucService
from clinicai.services.hoan_tac_service import HoanTacService, tien_da_thu_cua_chi_dinh
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.payment_service import PaymentService
from clinicai.services.service_execution_service import ServiceExecutionService
from clinicai.services.tien_thua_service import (
    TienThuaService,
    dong_tien_thua,
    tien_thua_khi_ve,
)
from tests.chay_nguoi_dua_tin import chay_ben_nhan, chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _chon,
    _don,
    _dung,
    _kham_va_chi_dinh,
    _khoa,
)
from tests.services.test_thu_truoc_lam_truoc_tick_db import day_thu_truoc

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

LY_DO_VE = "Lễ tân cho khách về."


@pytest_asyncio.fixture(autouse=True)
async def _lam_truoc_thu_sau(pool: asyncpg.Pool) -> AsyncIterator[None]:  # noqa: F811
    # Dây "thu trước khi làm" TẮT: làm trước thu sau được (đúng ca thật nhất).
    async with day_thu_truoc(pool, False):
        yield


# ── thao tác thật ──────────────────────────────────────────────────────────


async def _luot(pool: asyncpg.Pool, ca: Ca) -> tuple[str, str]:  # noqa: F811
    """Lượt có một chỉ định siêu âm 300.000đ, khách đã chọn làm."""
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await chay_hanh_trinh(pool)
    return visit, order


async def _thu(pool: asyncpg.Pool, ca: Ca, visit: str, method: str = "CASH") -> str:  # noqa: F811
    kq = await PaymentService(pool).record_payment(
        visit_id=visit,
        kind="dich_vu",
        amount=None,
        clinic_patient_id=None,
        identity=ca.thu_ngan,
        method=method,
        idempotency_key=_khoa(),
    )
    return str(kq["payment_cycle_id"])


async def _lan_thu(pool: asyncpg.Pool, visit: str, status: str) -> str | None:  # noqa: F811
    v = await pool.fetchval(
        "SELECT payment_cycle_id::text FROM payment_cycle WHERE visit_id = $1::uuid"
        " AND kind = 'dich_vu' AND status = $2 ORDER BY created_at DESC LIMIT 1",
        visit,
        status,
    )
    return None if v is None else str(v)


async def _lam_xong(pool: asyncpg.Pool, ca: Ca, order: str) -> None:  # noqa: F811
    d = await _don(pool, order)
    bd = await ServiceExecutionService(pool).bat_dau(
        order_id=order,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    d2 = await _don(pool, order)
    await ServiceExecutionService(pool).xong(
        order_id=order,
        attempt_id=bd["attempt_id"],
        expected_execution_revision=int(d2["execution_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )


async def _ve(pool: asyncpg.Pool, ca: Ca, visit: str) -> None:  # noqa: F811
    await CheckoutService(pool).close(
        identity=ca.le_tan, visit_id=visit, ly_do_tu_dong=LY_DO_VE
    )


async def _huy_phieu(pool: asyncpg.Pool, ca: Ca, visit: str) -> None:  # noqa: F811
    cid = await _lan_thu(pool, visit, "PAID")
    assert cid is not None
    await PaymentService(pool).void_payment(
        payment_cycle_id=cid,
        visit_id=visit,
        kind="dich_vu",
        reason="Thu nhầm, huỷ phiếu",
        identity=ca.thu_ngan,
    )


async def _huy_cho(pool: asyncpg.Pool, ca: Ca, visit: str) -> None:  # noqa: F811
    cid = await _lan_thu(pool, visit, "PENDING_VERIFICATION")
    assert cid is not None
    await PaymentService(pool).huy_cho_xac_minh(
        payment_cycle_id=cid,
        visit_id=visit,
        kind="dich_vu",
        reason="Tiền chưa về, huỷ lần chờ",
        identity=ca.thu_ngan,
    )


# ── bất biến kế toán ───────────────────────────────────────────────────────


async def _so_that(conn: asyncpg.Connection, visit: str) -> tuple[int, int]:
    """(khách nợ phòng khám, phòng khám nợ khách) THẬT — theo luật đang chạy."""
    phai_thu = (await no_khi_ve(conn, clinic_id=CLINIC, visit_id=visit)).tong
    # Chuyển khoản CHỜ xác minh: tiền chưa về thì vẫn là nợ (Tuyền 14/10).
    phai_thu += int(
        await conn.fetchval(
            "SELECT coalesce(sum(coalesce(original_amount, amount)), 0)"
            " FROM payment_cycle WHERE visit_id = $1::uuid"
            " AND status = 'PENDING_VERIFICATION'",
            visit,
        )
    )
    thua = (await dong_tien_thua(conn, CLINIC, [visit])).get(visit, [])
    # Đã thu mà chưa làm khi khách đã về — cùng điều kiện `_CHUA_LAM` nhưng
    # KHÔNG có hạn 90 ngày (nợ khách không tự hết hạn).
    ids = [
        str(r["id"])
        for r in await conn.fetch(
            "SELECT id::text AS id FROM service_order WHERE visit_id = $1::uuid"
            " AND exec_status IN ('authorized', 'assigned')"
            " AND selection_status IS DISTINCT FROM 'NOT_SELECTED'",
            visit,
        )
    ]
    tien = await tien_da_thu_cua_chi_dinh(conn, CLINIC, ids)
    chua_lam = sum(max(0, t["da_thu"] - t["da_hoan"]) for t in tien.values())
    return phai_thu, sum(int(d["so_tien"]) for d in thua) + chua_lam


async def _so_hien(conn: asyncpg.Connection, visit: str) -> tuple[int, int]:
    """Số nhân viên NHÌN THẤY ở "việc tồn" (mọi ngày). Tiền "giữ lại" vẫn nằm
    trong mục "Chưa trả lại khách" — không cộng thêm lần nữa."""
    ton = [
        t
        for t in await DanhSachHoaDonService._viec_ton(conn, CLINIC, None, None)
        if t.get("visit_id") == visit
    ]
    # Nợ hiện ở hai dòng không trùng nhau: phần chưa chuyển (GHI_NO) + phần
    # chuyển khoản đang chờ (CK_CHUA_VE).
    no = sum(int(t["so_tien"]) for t in ton if t["loai"] in ("GHI_NO", "CK_CHUA_VE"))
    tra = sum(
        int(t["so_tien"])
        for t in ton
        if t["loai"] in ("CHUA_TRA_LAI", "CHUA_LAM", "HOAN_THAT_BAI")
    )
    return no, tra


async def _lech(pool: asyncpg.Pool, visit: str) -> list[str]:  # noqa: F811
    """Các bất biến bị vỡ của lượt (rỗng = sổ khớp). Chỉ xét lượt ĐÃ VỀ."""
    # Như worker thật: công nợ + sổ nợ chạy ngay sau mỗi bước.
    await chay_ben_nhan(pool, CONG_NO, SO_NO)
    async with pool.acquire() as conn:
        if (
            await conn.fetchval(
                "SELECT closed_at FROM visit WHERE visit_id = $1::uuid", visit
            )
            is None
        ):
            return []
        thu_that, tra_that = await _so_that(conn, visit)
        thu_hien, tra_hien = await _so_hien(conn, visit)
        ket = await conn.fetchval(
            "SELECT count(*) FROM payment_refund r JOIN payment_cycle c"
            "  ON c.payment_cycle_id = r.payment_cycle_id"
            " WHERE r.visit_id = $1::uuid AND r.method = 'CASH'"
            "   AND hinh_thuc_hieu_luc(c.clinic_id, c.payment_cycle_id, c.method)"
            "       IN ('TRANSFER', 'QR')",
            visit,
        )
    out = []
    if thu_that != thu_hien:
        out.append(f"B1 khách nợ {thu_that:,}đ, màn hiện {thu_hien:,}đ")
    if tra_that != tra_hien:
        out.append(f"B2 phòng khám nợ khách {tra_that:,}đ, màn hiện {tra_hien:,}đ")
    if ket:
        out.append(f"B3 {ket} lần hoàn TIỀN MẶT cho tiền khách trả chuyển khoản")
    return out


# ── đường chuẩn: bộ giả lập không được báo lệch giả ─────────────────────────


async def test_duong_chuan_va_ghi_no_khong_lech(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    # Thu đủ → làm → về.
    v1, o1 = await _luot(pool, ca)
    await _thu(pool, ca, v1)
    await _lam_xong(pool, ca, o1)
    await _ve(pool, ca, v1)
    assert await _lech(pool, v1) == []
    # Làm trước → ghi nợ → về → hôm sau thu nợ.
    v2, o2 = await _luot(pool, ca)
    await _lam_xong(pool, ca, o2)
    await CongNoService(pool).ghi(identity=ca.le_tan, visit_id=v2, ly_do="Quên ví")
    await _ve(pool, ca, v2)
    assert await _lech(pool, v2) == []
    await _thu(pool, ca, v2)
    assert await _lech(pool, v2) == []
    # Thu → bỏ chỉ định → hoàn tiền thừa → về.
    v3, o3 = await _luot(pool, ca)
    await _thu(pool, ca, v3)
    await HoanTacService(pool).huy_chi_dinh(
        order_id=o3, identity=ca.bac_si, xac_nhan=True, ly_do="Khách đổi ý"
    )
    await HoanTienService(pool).hoan_tien_thua(identity=ca.thu_ngan, visit_id=v3)
    await _ve(pool, ca, v3)
    assert await _lech(pool, v3) == []


async def test_bo_chi_dinh_giu_lai_van_hien_la_no_khach(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _thu(pool, ca, v)
    await HoanTacService(pool).huy_chi_dinh(
        order_id=o, identity=ca.bac_si, xac_nhan=True, ly_do="Khách đổi ý"
    )
    await TienThuaService(pool).giu_lai(
        identity=ca.thu_ngan, visit_id=v, ly_do="Khách để lại trừ lần sau"
    )
    await _ve(pool, ca, v)
    assert await _lech(pool, v) == []


# ── lối rò đã biết (đọc code 14/10) — chứng minh bằng chạy thật ────────────


async def test_r2_huy_phieu_sau_khi_ve(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _thu(pool, ca, v)
    await _lam_xong(pool, ca, o)
    await _ve(pool, ca, v)
    await _huy_phieu(pool, ca, v)
    assert await _lech(pool, v) == []


async def test_ck_cho_khong_dong_ghi_no_huy_cho_thi_no_con_nguyen(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Đính chính đọc code 14/10: khoản ghi nợ chỉ ĐÓNG khi tiền thật vào (thu
    tiền mặt / xác minh CK) — `payment.service_collected` không phát cho lần chờ.
    Huỷ lần chờ thì ghi nợ còn nguyên, không rò."""
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _lam_xong(pool, ca, o)
    await CongNoService(pool).ghi(identity=ca.le_tan, visit_id=v, ly_do="Quên ví")
    await _ve(pool, ca, v)
    await _thu(pool, ca, v, method="TRANSFER")
    await chay_ben_nhan(pool, CONG_NO)
    assert (
        await pool.fetchval(
            "SELECT trang_thai FROM cong_no WHERE visit_id = $1::uuid", v
        )
        == "CHUA_THU"
    )
    await _huy_cho(pool, ca, v)
    assert await _lech(pool, v) == []


async def test_r12_ghi_no_dang_cho_ck_hien_hai_lan(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Khách nợ 300k quay lại chuyển khoản (chờ xác minh): việc tồn hiện CẢ
    "Ghi nợ chưa thu 300k" LẪN "CK chưa về 300k" — kế toán cộng ra 600k."""
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _lam_xong(pool, ca, o)
    await CongNoService(pool).ghi(identity=ca.le_tan, visit_id=v, ly_do="Quên ví")
    await _ve(pool, ca, v)
    await _thu(pool, ca, v, method="TRANSFER")
    assert await _lech(pool, v) == []


async def test_r11_ck_cho_cho_ve_roi_huy_lan_cho(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Chuyển khoản CHỜ xác minh được coi là đã phủ hoá đơn → check-out qua,
    không ghi nợ. Tiền không về, quầy huỷ lần chờ → khách nợ mà không ai thấy."""
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _lam_xong(pool, ca, o)
    await _thu(pool, ca, v, method="TRANSFER")
    await _ve(pool, ca, v)
    await _huy_cho(pool, ca, v)
    assert await _lech(pool, v) == []


async def test_r4_da_thu_chua_lam_qua_90_ngay(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _thu(pool, ca, v)
    await _ve(pool, ca, v)
    assert await _lech(pool, v) == []  # hôm nay còn hiện
    # Giả lập 100 ngày trôi qua (chỉ đẩy lùi giờ, không đổi trạng thái).
    await pool.execute(
        "UPDATE service_order SET created_at = created_at - make_interval(days => $2)"
        " WHERE id = $1::uuid",
        o,
        100,
    )
    # (Không lùi giờ phiếu thu: Postgres cấm sửa phiếu đã PAID — đúng luật.
    # Hạn 90 ngày của "đã thu chưa làm" tính theo giờ tạo chỉ định.)
    assert await _lech(pool, v) == []


async def _ck_da_ve_roi_bo(pool: asyncpg.Pool, ca: Ca) -> str:  # noqa: F811
    """Khách trả CK 300k (đã xác minh) rồi bỏ chỉ định → thừa 300k."""
    v, o = await _luot(pool, ca)
    cid = await _thu(pool, ca, v, method="TRANSFER")
    await PaymentService(pool).xac_minh_dien_tu(
        payment_cycle_id=cid,
        visit_id=v,
        kind="dich_vu",
        reference="FT123",
        identity=ca.thu_ngan,
    )
    await HoanTacService(pool).huy_chi_dinh(
        order_id=o, identity=ca.bac_si, xac_nhan=True, ly_do="Khách đổi ý"
    )
    return v


async def _hoan_cua(pool: asyncpg.Pool, visit: str) -> str:  # noqa: F811
    """ "HÌNH THỨC:TRẠNG THÁI" của khoản hoàn (duy nhất) của lượt."""
    return str(
        await pool.fetchval(
            "SELECT method || ':' || status FROM payment_refund"
            " WHERE visit_id = $1::uuid",
            visit,
        )
    )


async def test_r6_hoan_tien_thua_theo_hinh_thuc_goc(pool: asyncpg.Pool) -> None:  # noqa: F811
    """R6 (G4d): khách trả CK → hoàn thừa mặc định CK (khoản chờ), két không lệch."""
    ca = await _dung(pool)
    v = await _ck_da_ve_roi_bo(pool, ca)
    async with pool.acquire() as conn:
        tt = await tien_thua_khi_ve(conn, CLINIC, v)
    assert tt["theo_hinh_thuc"] == {"TRANSFER": 300_000}
    kq = await HoanTienService(pool).hoan_tien_thua(identity=ca.thu_ngan, visit_id=v)
    assert kq["theo_hinh_thuc"] == {"TRANSFER": 300_000}
    assert await _hoan_cua(pool, v) == "TRANSFER:PENDING"
    await _ve(pool, ca, v)
    assert await _lech(pool, v) == []


async def test_r6_hoan_theo_hinh_thuc_sau_khi_doi(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Quầy bấm nhầm TM rồi "Đổi hình thức" sang CK → hoàn thừa mặc định CK
    (hình thức HIỆU LỰC), không phải TM lúc bấm thu."""
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    cid = await _thu(pool, ca, v, method="CASH")
    await DoiHinhThucService(pool).doi(
        identity=ca.thu_ngan,
        payment_cycle_id=cid,
        hinh_thuc="TRANSFER",
        hinh_thuc_cu="CASH",
        reference=None,
        ly_do="Khách chuyển khoản, bấm nhầm tiền mặt",
    )
    await HoanTacService(pool).huy_chi_dinh(
        order_id=o, identity=ca.bac_si, xac_nhan=True, ly_do="Khách đổi ý"
    )
    async with pool.acquire() as conn:
        tt = await tien_thua_khi_ve(conn, CLINIC, v)
    assert tt["theo_hinh_thuc"] == {"TRANSFER": 300_000}
    await HoanTienService(pool).hoan_tien_thua(identity=ca.thu_ngan, visit_id=v)
    assert await _hoan_cua(pool, v) == "TRANSFER:PENDING"
    await _ve(pool, ca, v)
    assert await _lech(pool, v) == []


async def test_r6_nguoi_bam_doi_hinh_thuc_hoan(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Khách trả CK nhưng muốn nhận tiền mặt: người bấm chọn → ghi đúng TM."""
    ca = await _dung(pool)
    v = await _ck_da_ve_roi_bo(pool, ca)
    with pytest.raises(ClinicAIBaseException):
        await HoanTienService(pool).hoan_tien_thua(
            identity=ca.thu_ngan, visit_id=v, method="VANG"
        )
    kq = await HoanTienService(pool).hoan_tien_thua(
        identity=ca.thu_ngan, visit_id=v, method="CASH"
    )
    assert kq["theo_hinh_thuc"] == {"CASH": 300_000}
    assert await _hoan_cua(pool, v) == "CASH:COMPLETED"


# ── bấm lộn xộn như người thật ─────────────────────────────────────────────

Viec = Callable[[asyncpg.Pool, Ca, str, str], Awaitable[object]]

VIEC: dict[str, Viec] = {
    "thu_tien_mat": lambda p, c, v, o: _thu(p, c, v),
    "thu_chuyen_khoan": lambda p, c, v, o: _thu(p, c, v, method="TRANSFER"),
    "xac_minh_ck": lambda p, c, v, o: _xac_minh(p, c, v),
    "huy_lan_cho": lambda p, c, v, o: _huy_cho(p, c, v),
    "huy_phieu": lambda p, c, v, o: _huy_phieu(p, c, v),
    "lam_xong": lambda p, c, v, o: _lam_xong(p, c, o),
    "bo_chi_dinh": lambda p, c, v, o: HoanTacService(p).huy_chi_dinh(
        order_id=o, identity=c.bac_si, xac_nhan=True, ly_do="Khách đổi ý"
    ),
    "ghi_no": lambda p, c, v, o: CongNoService(p).ghi(
        identity=c.le_tan, visit_id=v, ly_do="Khách quên ví"
    ),
    "hoan_tien_thua": lambda p, c, v, o: HoanTienService(p).hoan_tien_thua(
        identity=c.thu_ngan, visit_id=v
    ),
    "giu_lai": lambda p, c, v, o: TienThuaService(p).giu_lai(
        identity=c.thu_ngan, visit_id=v, ly_do="Khách để lại"
    ),
    "ve": lambda p, c, v, o: _ve(p, c, v),
}


async def _xac_minh(pool: asyncpg.Pool, ca: Ca, visit: str) -> None:  # noqa: F811
    cid = await _lan_thu(pool, visit, "PENDING_VERIFICATION")
    assert cid is not None
    await PaymentService(pool).xac_minh_dien_tu(
        payment_cycle_id=cid,
        visit_id=visit,
        kind="dich_vu",
        reference=None,
        identity=ca.thu_ngan,
    )


SO_LUOT_NGAU_NHIEN = 80
SO_BUOC = 10


async def test_bam_lon_xon_khong_lech(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    lech: list[str] = []
    chay: Counter[str] = Counter()
    bi_chan: Counter[str] = Counter()
    # Postgres tự chặn (trigger / ràng buộc) thay vì máy chủ báo câu tiếng Việt:
    # người dùng thấy lỗi 500 — cũng là một phát hiện.
    db_chan: list[str] = []
    so_lan_kiem = 0
    for hat in range(SO_LUOT_NGAU_NHIEN):
        rnd = random.Random(hat)
        v, o = await _luot(pool, ca)
        da_lam: list[str] = []
        for _ in range(SO_BUOC):
            ten = rnd.choice(sorted(VIEC))
            try:
                await VIEC[ten](pool, ca, v, o)
            except (ClinicAIBaseException, AssertionError):
                # Màn không cho làm bước này — người thật cũng bị chặn.
                bi_chan[ten] += 1
                continue
            except asyncpg.PostgresError as e:
                db_chan.append(f"hạt {hat}: {' → '.join([*da_lam, ten])} ⇒ {e}")
                continue
            chay[ten] += 1
            da_lam.append(ten)
            vo = await _lech(pool, v)
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
                f"SỐ LẦN KIỂM SỔ: {so_lan_kiem}",
                "DB TỰ CHẶN (lỗi 500):",
                *db_chan,
                "LỆCH TÌM ĐƯỢC:",
                *(lech or ["(không)"]),
            ]
        )
    )
    assert lech == [] and db_chan == []
