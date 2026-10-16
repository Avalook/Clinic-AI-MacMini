"""Giảm chậm màn Quản lý khách hàng + Trang chủ + Tiếp đón — kết quả GIỐNG HỆT trước.

Đo 16/10/2026 trên DB thử lớn (9.000 khách, 36.000 lịch, ~98.000 việc):

  * `/cskh/man-khach-hang` ~1,2s → ~0,24s: trạng thái mỗi khách suy từ MỘT lần
    đọc `v_viec_cskh` (view ấy gọi `lich_vuot_suc_chua()` ~225ms mỗi lần; bản cũ
    gọi 3–5 lần một request);
  * Trang chủ: xu hướng "việc đang chờ" 560ms → 30ms (cắt việc đã đóng từ lâu
    TRƯỚC khi gọi `co_so_cua_luot` từng dòng);
  * Tiếp đón: bảng lịch hẹn tuần lấy gói gọn thay vì cả gói Trang chủ.

Bài này khoá phần "không đổi kết quả": so với CHÍNH view `v_trang_thai_cskh`, với
CHÍNH câu SQL cũ, và với CHÍNH gói đầy đủ.
"""

from __future__ import annotations

import datetime as dt
from datetime import date, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.man_khach_hang_service import (
    ManKhachHangService,
    _khoa_viec_thang,
    trang_thai_tu_viec,
)
from clinicai.services.man_trang_chu_service import ManTrangChuService
from clinicai.services.tuong_tac_cskh_service import TuongTacCskhService
from tests.services.test_goi_xac_nhan_lich_dat_ho_db import _lich
from tests.services.test_lieu_trinh_db import LT, dung_ca
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_nhan_luot_db import _st_kham

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


# ── 1. Trạng thái suy từ việc == chính view v_trang_thai_cskh ──────────────


async def _tu_view(pool: asyncpg.Pool, ids: list[str]) -> dict[str, dict[str, Any]]:
    rows = await pool.fetch(
        "SELECT clinic_patient_id, trang_thai, nhan, han_xu_ly, qua_han,"
        "       so_viec_mo, co_viec_qua_han, appointment_id, da_xac_nhan"
        "  FROM v_trang_thai_cskh"
        " WHERE clinic_id = $1::uuid AND clinic_patient_id = ANY($2::uuid[])",
        CLINIC,
        ids,
    )
    return {str(r["clinic_patient_id"]): dict(r) for r in rows}


async def _hen_goi_lai(pool: asyncpg.Pool, ca: LT, ngay: int) -> None:
    await pool.execute(
        "INSERT INTO hen_goi_lai (clinic_id, clinic_patient_id, ngay_goi, ly_do,"
        " tao_boi_staff_id) VALUES ($1::uuid, $2::uuid, CURRENT_DATE + $3::int,"
        " 'thử', $4::uuid)",
        CLINIC,
        ca.khach,
        ngay,
        ca.cskh.staff_id,
    )


async def test_trang_thai_suy_tu_viec_giong_view_v_trang_thai_cskh(
    pool: asyncpg.Pool,
) -> None:
    st = await _st_kham(pool)
    # A: nhiều việc khác độ ưu tiên + khách đã bấm xác nhận một lịch.
    a = await dung_ca(pool)
    l1 = await _lich(a, st, ngay=2)  # CHO_XAC_NHAN (uu_tien 10, chưa quá hạn)
    await _lich(a, st, ngay=5)  # thêm một CHO_XAC_NHAN, hạn khác
    await _hen_goi_lai(pool, a, -1)  # HEN_GOI_LAI quá hạn (uu_tien 6) → thắng
    await TuongTacCskhService(pool).ghi(
        identity=a.cskh,
        clinic_patient_id=a.khach,
        loai="XAC_NHAN_LICH",
        kenh="GOI",
        ket_qua="DA_LIEN_HE",
        appointment_id=l1,
        khach_xac_nhan=True,
    )
    # B: chỉ một việc chưa quá hạn.
    b = await dung_ca(pool)
    await _lich(b, st, ngay=3)
    # C: một việc quá hạn cùng một việc không quá hạn → quá hạn thắng dù uu_tien lớn.
    c = await dung_ca(pool)
    await _lich(c, st, ngay=6)
    await _hen_goi_lai(pool, c, -2)
    # D: không việc nào.
    d = await dung_ca(pool)

    # E: lịch NGÀY MAI đã được khách xác nhận → việc thắng NHAC_HEN_MAI mang
    # da_xac_nhan = True (lần chạm XAC_NHAN_LICH đóng CHO_XAC_NHAN, không đóng
    # nhắc hẹn).
    e = await dung_ca(pool)
    le = await _lich(e, st, ngay=1)
    await TuongTacCskhService(pool).ghi(
        identity=e.cskh,
        clinic_patient_id=e.khach,
        loai="XAC_NHAN_LICH",
        kenh="GOI",
        ket_qua="DA_LIEN_HE",
        appointment_id=le,
        khach_xac_nhan=True,
    )

    ids = [a.khach, b.khach, c.khach, d.khach, e.khach]
    goi = await ManKhachHangService(pool).goi_du_lieu(clinic_id=CLINIC, ids=ids)
    tu_view = await _tu_view(pool, ids)

    tu_goi = {str(r["clinic_patient_id"]): r for r in goi["trang_thai"]}
    # D không có việc mở và không có sự kiện nhập tiếp nhận → không có dòng nào.
    assert set(tu_goi) == set(tu_view) and a.khach in tu_goi and d.khach not in tu_goi
    for khach, mong in tu_view.items():
        assert tu_goi[khach] == mong, f"lệch ở khách {khach}"
    # Khách A: việc thắng là quá hạn; da_xac_nhan đọc đúng từ lịch đã bấm xác nhận.
    assert tu_goi[a.khach]["trang_thai"] == "HEN_GOI_LAI"
    assert (
        tu_goi[a.khach]["so_viec_mo"] == 2
    )  # l1 đã xác nhận → chỉ còn lịch 2 + hẹn gọi lại
    assert tu_goi[a.khach]["co_viec_qua_han"] is True
    assert tu_goi[e.khach]["trang_thai"] == "NHAC_HEN_MAI"
    assert tu_goi[e.khach]["da_xac_nhan"] is True

    # viec_mo = đúng các dòng v_viec_cskh (không thừa cột da_xac_nhan).
    viec = await pool.fetch(
        "SELECT clinic_patient_id, trang_thai, nhan, uu_tien, han_xu_ly, qua_han,"
        "       appointment_id FROM v_viec_cskh"
        " WHERE clinic_id = $1::uuid AND clinic_patient_id = ANY($2::uuid[])",
        CLINIC,
        ids,
    )

    def khoa(r: dict[str, Any]) -> tuple[str, str, str]:
        return (str(r["clinic_patient_id"]), r["trang_thai"], str(r["appointment_id"]))

    assert sorted((dict(r) for r in viec), key=khoa) == sorted(goi["viec_mo"], key=khoa)


async def test_khach_chi_co_viec_goi_xac_nhan_van_ra_khi_khach_khac_co_viec(
    pool: asyncpg.Pool,
) -> None:
    """Nhánh CHO_DAT_LICH loại khách ĐÃ có việc khác đúng như `NOT EXISTS (view)` cũ."""
    st = await _st_kham(pool)
    co_viec = await dung_ca(pool)
    await _lich(co_viec, st, ngay=2)
    chi_nhap = await dung_ca(pool)
    for ca in (co_viec, chi_nhap):
        await pool.execute(
            "INSERT INTO event_log (clinic_id, event_type, aggregate_type,"
            " aggregate_id, source, payload) VALUES ($1::uuid, 'patient.created',"
            " 'patient', $2, 'api:patient-intake', '{}'::jsonb)",
            CLINIC,
            ca.khach,
        )
    goi = await ManKhachHangService(pool).goi_du_lieu(
        clinic_id=CLINIC, ids=[co_viec.khach, chi_nhap.khach]
    )
    theo = {str(r["clinic_patient_id"]): r["trang_thai"] for r in goi["trang_thai"]}
    # Khách có lịch → việc của lịch thắng; khách chỉ nhập hồ sơ → CHO_DAT_LICH.
    assert theo[co_viec.khach] == "CHO_XAC_NHAN"
    assert theo[chi_nhap.khach] == "CHO_DAT_LICH"
    assert sum(1 for r in goi["viec_mo"] if r["trang_thai"] == "CHO_DAT_LICH") == 1


# ── 2. Khoá xếp việc thắng == ORDER BY của Postgres ────────────────────────


async def test_khoa_viec_thang_cung_thu_tu_voi_order_by_cua_postgres(
    pool: asyncpg.Pool,
) -> None:
    """`qua_han DESC, uu_tien, han_xu_ly`: DESC đặt NULL TRƯỚC, ASC đặt NULL SAU."""
    hom_nay = dt.datetime.now(CLINIC_TZ).date()
    cac = [
        {"qua_han": q, "uu_tien": u, "han_xu_ly": h}
        for q in (None, True, False)
        for u in (1, 2)
        for h in (None, hom_nay, hom_nay + timedelta(days=3))
    ]
    sql = await pool.fetch(
        "SELECT qua_han, uu_tien, han_xu_ly FROM unnest($1::boolean[], $2::int[],"
        " $3::date[]) AS t(qua_han, uu_tien, han_xu_ly)"
        " ORDER BY qua_han DESC, uu_tien, han_xu_ly",
        [r["qua_han"] for r in cac],
        [r["uu_tien"] for r in cac],
        [r["han_xu_ly"] for r in cac],
    )
    py = sorted(cac, key=_khoa_viec_thang)
    assert [dict(r) for r in sql] == py


# ── 3. Hàm thuần: đầu vào rác / rỗng không ném ─────────────────────────────


async def test_trang_thai_tu_viec_rong_va_nhieu_viec_khong_qua_han() -> None:
    assert trang_thai_tu_viec([]) == []
    ra = trang_thai_tu_viec(
        [
            {
                "clinic_patient_id": "k1",
                "trang_thai": "CHO_XAC_NHAN",
                "nhan": "Gọi xác nhận lịch",
                "uu_tien": 10,
                "han_xu_ly": None,
                "qua_han": None,  # han NULL → `han < hôm nay` là NULL
                "appointment_id": None,
                "da_xac_nhan": None,
            }
        ]
    )
    assert ra[0]["so_viec_mo"] == 1
    # bool_or toàn NULL là NULL, không phải False.
    assert ra[0]["co_viec_qua_han"] is None
    assert ra[0]["da_xac_nhan"] is False


# ── 4. Trang chủ: cắt trước không đổi xu hướng việc đang chờ ───────────────

# CÂU CŨ (trước 16/10/2026) — không cắt trước, gọi `co_so_cua_luot` cho MỌI việc.
_XU_HUONG_VIEC_CU = """
SELECT n.ngay, count(w.id) AS so
  FROM (SELECT d::date AS ngay,
               d::date::timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh' AS dau,
               (d::date + 1)::timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh' AS het
          FROM generate_series($2::date, $3::date, interval '1 day') d) n
  LEFT JOIN (
      SELECT w0.id, w0.clinic_id, w0.created_at, w0.status,
             w0.finished_at, w0.updated_at
        FROM work_item w0
       CROSS JOIN LATERAL (
           SELECT public.co_so_cua_luot(w0.clinic_id, w0.visit_id) AS co_so
       ) cs
       WHERE w0.clinic_id = $1::uuid
         AND coalesce(cs.co_so, $4::uuid)
             IS NOT DISTINCT FROM coalesce($4::uuid, cs.co_so)
  ) w
         ON w.clinic_id = $1::uuid
        AND w.created_at < n.het
        AND (w.status IN ('PENDING', 'IN_PROGRESS')
             OR coalesce(w.finished_at, w.updated_at) >= n.het)
 GROUP BY n.ngay ORDER BY n.ngay
"""


async def _viec(
    pool: asyncpg.Pool,
    *,
    tao_cach: int,
    dong_cach: int | None,
    node: str = "DATLICH-01",
) -> None:
    """Một work_item không gắn lượt, tạo `tao_cach` ngày trước, đóng `dong_cach`
    ngày trước (None = còn mở)."""
    bay_gio = dt.datetime.now(dt.UTC)
    dong = None if dong_cach is None else bay_gio - timedelta(days=dong_cach)
    tao = bay_gio - timedelta(days=tao_cach)
    await pool.execute(
        "INSERT INTO work_item (clinic_id, node_code, node_version_id, status,"
        " started_at, finished_at, created_at, updated_at)"
        " SELECT n.clinic_id, n.code, nv.id, $3, $4, $4, $5, $6"
        "   FROM node_definition n"
        "   JOIN node_definition_version nv"
        "     ON nv.node_definition_id = n.id AND nv.version = n.current_version"
        "    AND nv.clinic_id = n.clinic_id"
        "  WHERE n.clinic_id = $1::uuid AND n.code = $2",
        CLINIC,
        node,
        "PENDING" if dong is None else "COMPLETED",
        dong,
        tao,
        dong or tao,
    )


async def test_xu_huong_viec_cat_truoc_giong_cau_cu(pool: asyncpg.Pool) -> None:
    ca = await dung_ca(pool)
    node = await pool.fetchval(
        "SELECT code FROM node_definition WHERE clinic_id = $1::uuid LIMIT 1", CLINIC
    )
    # Đủ các kiểu trước / trong / sau cửa sổ 7 ngày.
    await _viec(pool, tao_cach=400, dong_cach=380, node=node)  # đóng từ lâu → không đếm
    await _viec(pool, tao_cach=60, dong_cach=50, node=node)  # đóng từ lâu → không đếm
    await _viec(pool, tao_cach=300, dong_cach=None, node=node)  # mở từ lâu → mọi ngày
    await _viec(pool, tao_cach=10, dong_cach=3, node=node)  # đóng giữa cửa sổ
    await _viec(pool, tao_cach=5, dong_cach=None, node=node)  # mở, tạo giữa cửa sổ
    await _viec(pool, tao_cach=1, dong_cach=0, node=node)  # tạo + đóng trong cửa sổ

    svc = ManTrangChuService(pool)
    goi = await svc.goi_du_lieu(
        identity=ca.le_tan, week_appt=_thu_hai(), week_roster=_thu_hai()
    )
    hom_nay = dt.datetime.now(CLINIC_TZ).date()
    cu = await pool.fetch(
        _XU_HUONG_VIEC_CU,
        CLINIC,
        hom_nay - timedelta(days=6),
        hom_nay,
        ca.le_tan.location_id or None,
    )
    assert goi["xu_huong"]["viec_dang_cho"] == [r["so"] for r in cu]

    # Thêm thêm việc đã đóng từ lâu: không được làm đổi xu hướng.
    for _ in range(3):
        await _viec(pool, tao_cach=200, dong_cach=150, node=node)
    goi2 = await svc.goi_du_lieu(
        identity=ca.le_tan, week_appt=_thu_hai(), week_roster=_thu_hai()
    )
    assert goi2["xu_huong"]["viec_dang_cho"] == goi["xu_huong"]["viec_dang_cho"]
    assert min(goi["xu_huong"]["viec_dang_cho"]) >= 1, "việc mở từ lâu phải được đếm"


def _thu_hai() -> date:
    hom_nay = dt.datetime.now(CLINIC_TZ).date()
    return hom_nay - timedelta(days=hom_nay.weekday())


# ── 5. Tiếp đón: gói gọn là tập con y hệt của gói đầy đủ ───────────────────


async def test_goi_lich_hen_tuan_giong_ba_khoi_cua_goi_day_du(
    pool: asyncpg.Pool,
) -> None:
    ca = await dung_ca(pool)
    st = await _st_kham(pool)
    await _lich(ca, st, ngay=0, kenh="ZALO_PK")
    await _lich(ca, st, ngay=1, kenh="ZALO_PK")
    svc = ManTrangChuService(pool)
    tuan = _thu_hai()
    day_du = await svc.goi_du_lieu(identity=ca.le_tan, week_appt=tuan, week_roster=tuan)
    gon = await svc.goi_lich_hen_tuan(identity=ca.le_tan, week_appt=tuan)
    assert sorted(gon) == ["tien_trinh", "truc_ca", "tuan_hen"]
    for khoa in gon:
        assert gon[khoa] == day_du[khoa], f"khối {khoa} lệch gói đầy đủ"
    assert len(gon["tuan_hen"]) >= 2, "bảng lịch hẹn phải có lịch vừa tạo"
