"""CSKH bấm "Đã gửi kết quả cho bệnh nhân" (TRA_KQ) ⇒ bàn XN thấy "Đã gửi khách".

Bàn đọc `tep_ket_qua.gui_luc`; sổ CSKH là bảng khác. Trước đây hai nơi không nói chuyện
với nhau: CSKH ghi sổ xong, bàn XN vẫn "Có kết quả". Giờ máy chủ gọi đúng lõi "Đúng
người, gửi" (`ket_qua.dung_nguoi_gui`) cho mọi tờ còn hiệu lực, chưa gửi của lượt đó.
"""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.core.clock import hom_nay_vn
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from clinicai.services.tuong_tac_cskh_service import TuongTacCskhService
from clinicai.services.xet_nghiem import ket_qua, mau, thu_ho
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import Ca
from tests.services.test_xac_nhan_tep_ket_qua_db import PDF_DUMMY
from tests.services.test_xet_nghiem_ban_db import (  # noqa: F401
    _hai_viec,
    _lam,
    _lam2,
    _tt,
    kho,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _den_lay_mau(pool: asyncpg.Pool) -> tuple[Ca, str, str]:  # noqa: F811
    """Hai việc cùng lượt, đã thu hộ + lấy mẫu chung một ống."""
    ca, o1, o2 = await _hai_viec(pool)
    for o in (o1, o2):
        await _lam2(pool, thu_ho.ghi_nhan, ca, order_id=o, tien_mat=500000)
    await _lam(pool, mau.lay_mau, ca, order_ids=[o1, o2])
    return ca, o1, o2


async def _lich_cua(pool: asyncpg.Pool, visit_id: str) -> tuple[str, str]:  # noqa: F811
    r = await pool.fetchrow(
        "SELECT clinic_patient_id::text AS kh, appointment_id::text AS ap"
        " FROM visit WHERE visit_id = $1::uuid",
        visit_id,
    )
    return r["kh"], r["ap"]


async def _tra_kq(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    kh: str,
    ap: str | None,
    kenh: str = "GOI",
    trang_thai_ma: str = "KQ_CHUA_GUI",
) -> dict[str, object]:
    """Như màn: nút "Đã gửi kết quả" đóng KQ_CHUA_GUI; hai nút tái khám đóng
    DA_TRA_KQ (cùng loai TRA_KQ)."""
    return await TuongTacCskhService(pool).ghi(
        identity=ca.bac_si,
        clinic_patient_id=kh,
        appointment_id=ap,
        loai="TRA_KQ",
        kenh=kenh,
        ket_qua="DA_LIEN_HE",
        noi_dung="Đã gửi kết quả cho bệnh nhân",
        trang_thai_ma=trang_thai_ma,
    )


async def test_tra_kq_cskh_ghi_da_gui_cho_to_chua_gui_cua_luot(
    pool: asyncpg.Pool,  # noqa: F811
    kho: None,  # noqa: F811
) -> None:
    ca, o1, o2 = await _den_lay_mau(pool)
    await ket_qua.tai_tay(
        pool, ca.bac_si, o1, hom_nay_vn(), data=PDF_DUMMY, ten="kq.pdf"
    )
    v1 = await _tt(pool, ca, o1)
    assert v1["trang_thai"]["ma"] == "CO_KET_QUA"
    kh, ap = await _lich_cua(pool, v1["visit_id"])
    assert ap, "ca test phải có lịch hẹn"
    # Không gắn lịch hẹn ⇒ không đánh dấu gì (không gửi nhầm tờ của lượt khác).
    await _tra_kq(pool, ca, kh, None)
    assert (await _tt(pool, ca, o1))["trang_thai"]["ma"] == "CO_KET_QUA"

    kq = await _tra_kq(pool, ca, kh, ap)

    assert kq["ok"] and kq["id"]
    v1 = await _tt(pool, ca, o1)
    assert v1["trang_thai"]["ma"] == "DA_GUI"
    r = await pool.fetchrow(
        "SELECT gui_luc, gui_kenh FROM tep_ket_qua WHERE id = $1::uuid", v1["tep_id"]
    )
    # Kênh GOI không phải kênh gửi tệp ⇒ ghi TRUC_TIEP.
    assert r["gui_luc"] is not None and r["gui_kenh"] == "TRUC_TIEP"
    # Việc chưa có tờ: không gửi gì, không lỗi.
    v2 = await _tt(pool, ca, o2)
    assert v2["trang_thai"]["ma"] != "DA_GUI" and v2["tep_id"] is None
    # Cùng lõi với nút "Gửi khách" ⇒ có sự kiện lab.result_sent.
    assert await pool.fetchval(
        "SELECT count(*) FROM domain_event WHERE event_type = 'lab.result_sent'"
        " AND aggregate_id = $1::uuid",
        o1,
    )
    # Bấm lần hai: tờ đã gửi ⇒ bỏ qua, sổ CSKH vẫn ghi.
    assert (await _tra_kq(pool, ca, kh, ap, kenh="ZALO"))["ok"]


@pytest.mark.parametrize("kenh", ["ZALO", "SMS", "TRUC_TIEP"])
async def test_tra_kq_chon_kenh_thi_to_ghi_dung_kenh(
    pool: asyncpg.Pool,  # noqa: F811
    kho: None,  # noqa: F811
    kenh: str,
) -> None:
    # Tuyền 12/11: nút "Đã gửi kết quả cho bệnh nhân" ở Quản lý khách hàng cho chọn
    # kênh (ChonKenhGuiKq) ⇒ tờ đối tác ghi ĐÚNG kênh đó, không đổi thành Trực tiếp.
    ca, o1, _ = await _den_lay_mau(pool)
    await ket_qua.tai_tay(
        pool, ca.bac_si, o1, hom_nay_vn(), data=PDF_DUMMY, ten="kq.pdf"
    )
    v1 = await _tt(pool, ca, o1)
    kh, ap = await _lich_cua(pool, v1["visit_id"])
    assert (await _tra_kq(pool, ca, kh, ap, kenh=kenh))["ok"]
    assert (
        await pool.fetchval(
            "SELECT gui_kenh FROM tep_ket_qua WHERE id = $1::uuid", v1["tep_id"]
        )
        == kenh
    )


async def test_nut_da_gui_ghi_ca_tep_noi_bo_cua_luot(
    pool: asyncpg.Pool,  # noqa: F811
    kho: None,  # noqa: F811
) -> None:
    # Tuyền 12/11: nút "Đã gửi kết quả cho bệnh nhân" ghi đã gửi MỌI tệp của lượt —
    # cả tệp nội bộ (ảnh siêu âm / PDF CSKH tải, gắn lịch hẹn), không chỉ tờ đối tác.
    ca, o1, _ = await _den_lay_mau(pool)
    v1 = await _tt(pool, ca, o1)
    kh, ap = await _lich_cua(pool, v1["visit_id"])
    noi_bo = await TepKetQuaService(pool).tai_len(
        identity=ca.bac_si,
        clinic_patient_id=kh,
        data=PDF_DUMMY,
        ten_hien_thi="sieu-am.pdf",
        appointment_id=ap,
    )
    assert (await _tra_kq(pool, ca, kh, ap, kenh="ZALO"))["ok"]
    assert (
        await pool.fetchval(
            "SELECT gui_kenh FROM tep_ket_qua WHERE id = $1::uuid", noi_bo["id"]
        )
        == "ZALO"
    )


async def test_hai_nut_tai_kham_khong_ghi_da_gui_to_ve_sau(
    pool: asyncpg.Pool,  # noqa: F811
    kho: None,  # noqa: F811
) -> None:
    # Lỗi cũ (Tuyền 12/11): ở bước "Đã trả kết quả", nút "Cần / Không cần tái khám"
    # cũng ghi TRA_KQ ⇒ tờ đối tác về SAU (chưa ai gửi) bị ghi "đã gửi Trực tiếp".
    ca, o1, _ = await _den_lay_mau(pool)
    await ket_qua.tai_tay(
        pool, ca.bac_si, o1, hom_nay_vn(), data=PDF_DUMMY, ten="kq.pdf"
    )
    v1 = await _tt(pool, ca, o1)
    kh, ap = await _lich_cua(pool, v1["visit_id"])
    assert (await _tra_kq(pool, ca, kh, ap, trang_thai_ma="DA_TRA_KQ"))["ok"]
    assert (
        await pool.fetchval(
            "SELECT gui_luc FROM tep_ket_qua WHERE id = $1::uuid", v1["tep_id"]
        )
        is None
    )
    assert (await _tt(pool, ca, o1))["trang_thai"]["ma"] == "CO_KET_QUA"


async def test_tra_kq_khi_chua_co_to_nao_khong_loi_khong_gui(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, o1, o2 = await _den_lay_mau(pool)
    v1 = await _tt(pool, ca, o1)
    kh, ap = await _lich_cua(pool, v1["visit_id"])

    kq = await _tra_kq(pool, ca, kh, ap)

    assert kq["ok"] and kq["id"]
    for o in (o1, o2):
        assert (await _tt(pool, ca, o))["trang_thai"]["ma"] == "CHO_KET_QUA"
    assert not await pool.fetchval(
        "SELECT count(*) FROM domain_event WHERE event_type = 'lab.result_sent'"
        " AND aggregate_id = ANY($1::uuid[])",
        [o1, o2],
    )
