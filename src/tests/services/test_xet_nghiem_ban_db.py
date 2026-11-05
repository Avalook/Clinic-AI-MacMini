"""Chặng 3 — bàn XN chạy thật (kế hoạch 4.5, 5, 5c, mục 7; kịch bản mục 8 ở service).

Bất biến ép ở Postgres: mã ống cấp bằng `cap_ma_mau` (Damm, khớp Python), một ống một
đối tác (FK ghép), một việc một mẫu còn hiệu lực, đóng việc một lần còn hiệu lực.
"""

from __future__ import annotations

import pathlib
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.core.clock import hom_nay_vn
from clinicai.services.xet_nghiem import ket_qua, mau, qua_trinh, thu_ho
from clinicai.services.xet_nghiem.ma_mau import tao_ma
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_khoa_thu_ho_doi_tac_db import _dem_tien_luot
from tests.services.test_thu_tien_xep_phong_mang_sang_db import Ca
from tests.services.test_xac_nhan_tep_ket_qua_db import PDF_DUMMY
from tests.services.test_xet_nghiem_nen_db import (
    _ca_doi_tac,
    _chi_dinh,
    _gan,
    _ma,
    _sp,
    _them_dt,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture
def kho(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)


async def _hai_viec(pool: asyncpg.Pool) -> tuple[Ca, str, str]:  # noqa: F811
    """Một khách, HAI việc của cùng đối tác (HPV + ThinPrep kiểu kịch bản bước 2)."""
    ca = await _ca_doi_tac(pool)
    a = await _them_dt(pool, ca.bac_si, _ma(), hen_tra_so_ngay_mac_dinh=3)
    await _gan(pool, ca.bac_si, a, await _sp(pool, ca.ma_dv))
    o1 = await _chi_dinh(pool, ca)
    o2 = await _chi_dinh(pool, ca)
    return ca, o1, o2


async def _lam(pool: asyncpg.Pool, ham: Any, ca: Ca, **d: object) -> Any:  # noqa: F811
    async with pool.acquire() as conn, conn.transaction():
        return await ham(conn, ca.bac_si, dict(d), hom_nay_vn())


async def _lam2(pool: asyncpg.Pool, ham: Any, ca: Ca, **d: object) -> Any:  # noqa: F811
    async with pool.acquire() as conn, conn.transaction():
        return await ham(conn, ca.bac_si, dict(d))


async def _tt(pool: asyncpg.Pool, ca: Ca, oid: str) -> dict[str, Any]:  # noqa: F811
    async with pool.acquire() as conn:
        return await mau._mot_viec(conn, ca.bac_si, oid, hom_nay_vn())


async def test_damm_sql_khop_python_1000_so(pool: asyncpg.Pool) -> None:  # noqa: F811
    rows = await pool.fetch(
        "SELECT n, 'M' || lpad(n::text, 5, '0')"
        " || public.damm_chu_so_kiem(lpad(n::text, 5, '0'))::text AS ma"
        " FROM generate_series(1, 1000) n"
    )
    assert all(r["ma"] == tao_ma(r["n"]) for r in rows)
    assert tao_ma(572) == "M005724"


async def test_kich_ban_3_den_9_o_tang_service(
    pool: asyncpg.Pool,  # noqa: F811
    kho: None,
) -> None:
    ca, o1, o2 = await _hai_viec(pool)
    v = await _tt(pool, ca, o1)
    # 3. Chờ thu, nút Lấy mẫu mờ + lý do.
    assert v["trang_thai"]["ma"] == "CHO_THU" and not v["nut"]["lay_mau"]
    assert v["trang_thai"]["ly_do_khong_lay_mau"] == "Chưa ghi nhận thu hộ"
    with pytest.raises(ConflictError, match="Chưa ghi nhận thu hộ"):
        await _lam(pool, mau.lay_mau, ca, order_ids=[o1, o2])
    truoc = await _dem_tien_luot(pool, v["visit_id"])
    # 4. Ghi 300k TM + 200k CK (lệch giá gợi ý) cho từng việc.
    for o in (o1, o2):
        await _lam2(
            pool, thu_ho.ghi_nhan, ca, order_id=o, tien_mat=300000, chuyen_khoan=200000
        )
        assert (await _tt(pool, ca, o))["trang_thai"]["ma"] == "CHO_LAY_MAU"
    # 5. Một ống cho cả hai, hẹn = hôm nay + 3.
    kq = await _lam(pool, mau.lay_mau, ca, order_ids=[o1, o2])
    assert kq["ma_mau"].startswith("M") and len(kq["ma_mau"]) == 7
    assert (kq["hen_tra_ngay"] - hom_nay_vn()).days == 3
    assert {(await _tt(pool, ca, o))["ma_mau"] for o in (o1, o2)} == {kq["ma_mau"]}
    # 6. Hoàn tác bước trước = huỷ mẫu; khoản thu còn.
    v1 = await _tt(pool, ca, o1)
    assert v1["nut"]["hoan_tac"]["lenh"] == "huy_mau"
    with pytest.raises(ConflictError, match="huỷ mẫu trước"):
        await _lam2(pool, thu_ho.huy, ca, order_id=o1, ly_do="thử huỷ thu")
    await _lam2(
        pool,
        mau.huy_mau,
        ca,
        mau_id=kq["mau_id"],
        loai="NHAP_SAI",
        ly_do="dán nhầm ống",
    )
    v1 = await _tt(pool, ca, o1)
    assert v1["trang_thai"]["ma"] == "CHO_LAY_MAU" and v1["da_thu"] == 500000
    # 7. Lấy lại = mã MỚI.
    kq2 = await _lam(pool, mau.lay_mau, ca, order_ids=[o1, o2])
    assert kq2["ma_mau"] != kq["ma_mau"]
    # 8. Tải tay ⇒ Có kết quả; tệp đi đường đối tác (đã xác nhận cùng bước).
    await ket_qua.tai_tay(
        pool, ca.bac_si, o1, hom_nay_vn(), data=PDF_DUMMY, ten="kq.pdf"
    )
    v1 = await _tt(pool, ca, o1)
    assert v1["trang_thai"]["ma"] == "CO_KET_QUA" and v1["nut"]["gui"]
    # Hộp xem (Lightbox) cần loại + mime để vẽ PDF/ảnh tại chỗ.
    assert v1["loai_tep"] == "PDF" and v1["mime_tep"] == "application/pdf"
    assert (
        await pool.fetchval(
            "SELECT xac_nhan_trang_thai FROM tep_ket_qua WHERE id = $1::uuid",
            v1["tep_id"],
        )
        == "HOP_LE"
    )
    with pytest.raises(ConflictError, match="tệp kết quả"):
        await _lam2(
            pool,
            mau.huy_mau,
            ca,
            mau_id=kq2["mau_id"],
            loai="MAU_HONG",
            ly_do="mẫu hỏng",
        )
    # 9. Đúng người, gửi (Zalo) ⇒ Đã gửi; đóng bị chặn; thu hồi giữ mốc gửi.
    with pytest.raises(ValidationError):
        await ket_qua.dung_nguoi_gui(pool, ca.bac_si, {"order_id": o1}, hom_nay_vn())
    await ket_qua.dung_nguoi_gui(
        pool, ca.bac_si, {"order_id": o1, "kenh": "zalo"}, hom_nay_vn()
    )
    v1 = await _tt(pool, ca, o1)
    assert v1["trang_thai"]["ma"] == "DA_GUI"
    tep = v1["tep_id"]
    with pytest.raises(ValidationError):
        await ket_qua.thu_hoi(pool, ca.bac_si, {"order_id": o1}, hom_nay_vn())
    await ket_qua.thu_hoi(
        pool, ca.bac_si, {"order_id": o1, "ly_do": "gửi nhầm bản"}, hom_nay_vn()
    )
    r = await pool.fetchrow(
        "SELECT xac_nhan_trang_thai, gui_luc FROM tep_ket_qua WHERE id = $1::uuid", tep
    )
    assert r["xac_nhan_trang_thai"] == "THU_HOI" and r["gui_luc"] is not None
    # 10. Tiền phòng khám không đổi.
    assert await _dem_tien_luot(pool, v["visit_id"]) == truoc


async def test_mot_ong_mot_doi_tac_ep_o_db(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca, o1, _ = await _hai_viec(pool)
    b = await _them_dt(pool, ca.bac_si, _ma())
    m = await pool.fetchval(
        "INSERT INTO mau_xet_nghiem (clinic_id, doi_tac_id, ma_mau, so_thu_tu, lay_boi)"
        " VALUES ($1::uuid, $2::uuid, 'M999990', 99999, $3::uuid) RETURNING id",
        CLINIC,
        b,
        ca.bac_si.staff_id,
    )
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await pool.execute(
            "INSERT INTO mau_xet_nghiem_viec (mau_id, service_order_id, doi_tac_id,"
            " clinic_id) VALUES ($1, $2::uuid, $3::uuid, $4::uuid)",
            m,
            o1,
            b,
            CLINIC,
        )


async def test_hai_nguoi_lay_mau_cung_viec_mot_nguoi_409(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, o1, _ = await _hai_viec(pool)
    await _lam2(pool, thu_ho.ghi_nhan, ca, order_id=o1, tien_mat=0)
    await _lam(pool, mau.lay_mau, ca, order_ids=[o1])
    with pytest.raises(ConflictError):
        await _lam(pool, mau.lay_mau, ca, order_ids=[o1])
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM mau_xet_nghiem_viec WHERE service_order_id = $1::uuid"
            " AND go_luc IS NULL",
            o1,
        )
        == 1
    )


async def test_cho_qua_cu_khong_con_mo_lay_mau_khi_chua_thu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Tuyền 05/11: BỎ "Cho lấy mẫu trước" — lấy mẫu CHỈ sau khi ghi nhận thu hộ. Việc
    đã lỡ được cho qua (dữ liệu cũ trên staging) mà chưa thu ⇒ về "Chưa thu tiền",
    nút Lấy mẫu mờ; lệnh lấy mẫu bị chặn ở máy chủ."""
    ca, o1, _ = await _hai_viec(pool)
    await pool.execute(
        "UPDATE xet_nghiem_viec SET cho_lay_mau_truoc_luc = now(),"
        " cho_lay_mau_truoc_boi = $2::uuid, cho_lay_mau_truoc_ly_do = 'dữ liệu cũ'"
        " WHERE service_order_id = $1::uuid",
        o1,
        ca.bac_si.staff_id,
    )
    v = await _tt(pool, ca, o1)
    assert v["trang_thai"]["ma"] == "CHO_THU" and not v["nut"]["lay_mau"]
    assert not {"cho_qua", "hien_cho_qua", "go_cho_qua"} & set(v["nut"])
    with pytest.raises(ConflictError):
        await _lam(pool, mau.lay_mau, ca, order_ids=[o1])


async def test_viec_do_qua_30_ngay_van_hien_tren_ban(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Việc tồn không được biến mất khỏi bàn chỉ vì cũ (soát chặng 3)."""
    ca, o1, _ = await _hai_viec(pool)
    async with pool.acquire() as conn:
        await conn.execute("SET session_replication_role = replica")
        await conn.execute(
            "UPDATE xet_nghiem_viec SET tao_luc = now() - interval '45 days'"
            " WHERE service_order_id = $1::uuid",
            o1,
        )
        await conn.execute("SET session_replication_role = origin")
    ds = await ket_qua.ban(pool, ca.bac_si, hom_nay_vn(), hom_nay_vn())
    assert o1 in {v["order_id"] for v in ds["viec"]}


async def test_viec_da_dong_truoc_van_mo_lai_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Tuyền 05/11: BỎ lệnh "Đối tác đã tự trả khách" (hệ thống chỉ ghi nhận việc làm
    trong hệ thống). Việc đã lỡ đóng trước đó vẫn MỞ LẠI được — không khoá cứng."""
    ca, o1, _ = await _hai_viec(pool)
    await _lam2(pool, thu_ho.ghi_nhan, ca, order_id=o1, chuyen_khoan=900000)
    await _lam(pool, mau.lay_mau, ca, order_ids=[o1])
    # Dữ liệu cũ: một dòng đóng ghi trước khi bỏ lệnh (staging 05/11).
    await pool.execute(
        "INSERT INTO xet_nghiem_dong (clinic_id, service_order_id, ly_do, dong_boi)"
        " VALUES ($1::uuid, $2::uuid, 'đóng trước 05/11', $3::uuid)",
        CLINIC,
        o1,
        ca.bac_si.staff_id,
    )
    v = await _tt(pool, ca, o1)
    assert "dong" not in v["nut"], "lệnh đóng đã bỏ — màn không được có nút này"
    assert v["trang_thai"]["ma"] == "DA_DONG" and v["nut"]["mo_lai"]
    assert v["nut"]["hoan_tac"]["lenh"] == "mo_lai"
    await _lam(pool, mau.mo_lai, ca, order_id=o1, ly_do="đối tác chưa trả thật")
    assert (await _tt(pool, ca, o1))["trang_thai"]["ma"] == "CHO_KET_QUA"
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute(
            "DELETE FROM xet_nghiem_dong WHERE service_order_id = $1::uuid", o1
        )


async def test_hanh_trinh_va_qua_trinh_doc_tu_su_viec(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Bản mẫu 05/11: mốc có giờ + "Xem quá trình" — kể cả bước bù vẫn còn dòng."""
    ca, o1, o2 = await _hai_viec(pool)
    await _lam2(pool, thu_ho.ghi_nhan, ca, order_id=o1, tien_mat=300000)
    m = await _lam(pool, mau.lay_mau, ca, order_ids=[o1])
    await _lam2(
        pool, mau.huy_mau, ca, mau_id=m["mau_id"], loai="NHAP_SAI", ly_do="dán nhầm"
    )
    await _lam(pool, mau.lay_mau, ca, order_ids=[o1])
    v = await _tt(pool, ca, o1)
    assert [x["trang_thai"] for x in v["hanh_trinh"]] == [
        "done",
        "done",
        "done",
        "current",
        "upcoming",
    ]
    ban = await ket_qua.ban(pool, ca.bac_si, hom_nay_vn(), hom_nay_vn())
    # `_chi_dinh` tạo bệnh nhân mới mỗi lần ⇒ hai khách, mỗi khách một dòng.
    k = next(x for x in ban["khach"] if o1 in x["order_ids"])
    # Bác sĩ không có quyền quản lý ⇒ màn không hiện tab Cài đặt.
    assert k["order_ids"] == [o1] and ban["quan_ly"] is False
    assert any(x["order_ids"] == [o2] for x in ban["khach"])
    async with pool.acquire() as conn:
        ds = await qua_trinh.doc(conn, CLINIC, o1)
        rac = await qua_trinh.doc(conn, CLINIC, "khong-phai-uuid")
        # Phòng khám khác hỏi đúng mã việc này ⇒ rỗng (mọi nhánh lọc clinic_id).
        la = await qua_trinh.doc(conn, "00000000-0000-0000-0000-0000000000ff", o1)
    assert la == []
    viec = [d["viec"] for d in ds]
    assert viec[0] == "Chỉ định xét nghiệm"
    assert any(x.startswith("Thu hộ 300.000đ") for x in viec)
    assert sum(x.startswith("Lấy mẫu, mã ống") for x in viec) == 2
    assert any(x.startswith("Huỷ mẫu") and "dán nhầm" in x for x in viec)
    assert [d["luc"] for d in ds] == sorted(d["luc"] for d in ds)
    assert rac == []


@pytest.mark.parametrize("rac", [None, "", "abc", "2026-13-40", 12])
def test_ngay_rac_tra_rong(rac: object) -> None:
    assert mau.doc_ngay(rac) is None
