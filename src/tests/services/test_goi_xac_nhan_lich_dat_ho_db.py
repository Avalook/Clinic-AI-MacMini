"""Gọi xác nhận MỌI lịch đặt hộ (Tuyền chốt 15/10/2026, migration 20261015110000).

Việc `CHO_XAC_NHAN` ("Gọi xác nhận lịch") của `v_viec_cskh`:
  - mọi lịch còn sống, kênh KHÁC `WALK_IN`, ngày khám trong [hôm nay, hôm nay + 7];
  - kể cả lịch đặt sát ngày (trước đây bị bỏ vì "cuộc gọi đặt lịch coi là lần liên hệ");
  - hạn = GREATEST(ngày khám − 7, ngày đặt) — đặt sát ngày đến hạn đúng hôm đặt,
    không sinh ra đã "Quá hạn";
  - đóng bằng một lần chạm `XAC_NHAN_LICH` chưa hoàn tác (mọi kết quả);
    KNM/KLLD/Hẹn GLS thì nhánh `GOI_LAI` đón; rút lần chạm thì việc quay lại.

Dựng lịch bằng SQL trực tiếp, mỗi lịch gắn MỘT bác sĩ mới tinh để trigger sức chứa
`enforce_slot_capacity` (2+1 mỗi bác sĩ mỗi khung 15') không bao giờ đụng lịch của
test khác trong cùng DB.
"""

from __future__ import annotations

import datetime as dt
import itertools
import re
from pathlib import Path

import asyncpg
import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.tuong_tac_cskh_service import TuongTacCskhService
from tests.services.test_lieu_trinh_db import LT, dung_ca
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_nhan_luot_db import _st_kham

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

CHO = "CHO_XAC_NHAN"
SO_NGAY = 7
_dem = itertools.count()


def _hom_nay() -> dt.date:
    return dt.datetime.now(CLINIC_TZ).date()


async def _lich(
    ca: LT,
    st: str,
    *,
    ngay: int,
    kenh: str | None = "ZALO_PK",
    tao_truoc: int = 0,
    status: str = "SCHEDULED",
) -> str:
    """Một lịch của khách `ca`: khám sau `ngay` ngày, đặt cách đây `tao_truoc` ngày."""
    gio = dt.datetime.combine(
        _hom_nay() + dt.timedelta(days=ngay),
        dt.time(7 + next(_dem) % 10, 0),
        tzinfo=CLINIC_TZ,
    )
    return str(
        await ca.pool.fetchval(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, slot_start, slot_end, status, booking_channel,"
            " created_at, ly_do_huy_ma, doctor_id, is_walkin)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7, $8,"
            " now() - make_interval(days => $9::int), $10, $11::uuid, $12)"
            " RETURNING id::text",
            CLINIC,
            ca.khach,
            ca.loc,
            st,
            gio,
            gio + dt.timedelta(minutes=15),
            status,
            kenh,
            tao_truoc,
            "BAO_KHI_XAC_NHAN" if status == "CANCELLED" else None,
            ca.bac_si.staff_id,
            # CHECK appointment_walkin_channel_agree: is_walkin khớp kênh.
            (kenh or "").upper() == "WALK_IN",
        )
    )


async def _viec(pool: asyncpg.Pool, ca: LT, appt: str, loai: str = CHO):
    """Dòng việc `loai` của lịch `appt` trên v_viec_cskh (None nếu không có)."""
    return await pool.fetchrow(
        "SELECT trang_thai, nhan, han_xu_ly, qua_han FROM v_viec_cskh"
        " WHERE clinic_patient_id = $1::uuid AND appointment_id = $2::uuid"
        "   AND trang_thai = $3",
        ca.khach,
        appt,
        loai,
    )


async def _goi(
    pool: asyncpg.Pool,
    ca: LT,
    appt: str,
    ket_qua: str = "DA_LIEN_HE",
) -> str:
    kenh = "KHONG_LIEN_HE" if ket_qua == "BO_QUA" else "GOI"
    kq = await TuongTacCskhService(pool).ghi(
        identity=ca.cskh,
        clinic_patient_id=ca.khach,
        loai="XAC_NHAN_LICH",
        kenh=kenh,
        ket_qua=ket_qua,
        appointment_id=appt,
    )
    return str(kq["id"])


async def test_dat_ho_sat_ngay_van_co_viec_han_la_hom_dat(pool: asyncpg.Pool) -> None:
    ca = await dung_ca(pool)
    st = await _st_kham(pool)
    # Khám sau 3 ngày, vừa đặt hôm nay: trước đây KHÔNG sinh việc (đặt < 7 ngày).
    appt = await _lich(ca, st, ngay=3, tao_truoc=0)
    v = await _viec(pool, ca, appt)
    assert v is not None
    assert v["nhan"] == "Gọi xác nhận lịch"
    # ngày khám − 7 = hôm nay − 4, nhưng không sớm hơn ngày đặt (hôm nay).
    assert v["han_xu_ly"] == _hom_nay()
    assert v["qua_han"] is False


async def test_dat_ho_kham_ngay_hom_nay_va_ngay_thu_7(pool: asyncpg.Pool) -> None:
    ca = await dung_ca(pool)
    st = await _st_kham(pool)
    hom_nay = await _lich(ca, st, ngay=0, tao_truoc=0)
    bien = await _lich(ca, st, ngay=SO_NGAY, tao_truoc=0)
    assert await _viec(pool, ca, hom_nay) is not None
    v = await _viec(pool, ca, bien)
    assert v is not None
    # Khám đúng hôm nay + 7: ngày khám − 7 = hôm nay = ngày đặt.
    assert v["han_xu_ly"] == _hom_nay()
    assert v["qua_han"] is False


async def test_dat_xa_giu_han_cu_ngay_kham_tru_7(pool: asyncpg.Pool) -> None:
    ca = await dung_ca(pool)
    st = await _st_kham(pool)
    # Khám sau 5 ngày, đặt cách đây 10 ngày: hạn cũ = hôm nay − 2 → đã quá hạn.
    appt = await _lich(ca, st, ngay=5, tao_truoc=10)
    v = await _viec(pool, ca, appt)
    assert v is not None
    assert v["han_xu_ly"] == _hom_nay() - dt.timedelta(days=2)
    assert v["qua_han"] is True


@pytest.mark.parametrize(
    "kenh", ["ZALO_PK", "HOTLINE", "REFERRAL", "FACEBOOK", None, ""]
)
async def test_moi_kenh_dat_ho_deu_co_viec(
    pool: asyncpg.Pool, kenh: str | None
) -> None:
    ca = await dung_ca(pool)
    st = await _st_kham(pool)
    appt = await _lich(ca, st, ngay=2, kenh=kenh)
    assert await _viec(pool, ca, appt) is not None


@pytest.mark.parametrize("kenh", ["WALK_IN", "walk_in", "Walk_In"])
async def test_khach_truc_tiep_walk_in_khong_co_viec(
    pool: asyncpg.Pool, kenh: str
) -> None:
    ca = await dung_ca(pool)
    st = await _st_kham(pool)
    appt = await _lich(ca, st, ngay=1, kenh=kenh)
    assert await _viec(pool, ca, appt) is None


async def test_ngoai_cua_so_va_lich_da_qua_khong_co_viec(pool: asyncpg.Pool) -> None:
    ca = await dung_ca(pool)
    st = await _st_kham(pool)
    xa = await _lich(ca, st, ngay=SO_NGAY + 1)
    # Lịch của hôm qua: đã qua, không còn gì để xác nhận.
    qua = await _lich(ca, st, ngay=-1, tao_truoc=3)
    assert await _viec(pool, ca, xa) is None
    assert await _viec(pool, ca, qua) is None


@pytest.mark.parametrize("ket_qua", ["DA_LIEN_HE", "TU_CHOI", "BO_QUA", "CAN_BAC_SI"])
async def test_da_goi_xong_thi_het_viec(pool: asyncpg.Pool, ket_qua: str) -> None:
    ca = await dung_ca(pool)
    st = await _st_kham(pool)
    appt = await _lich(ca, st, ngay=3)
    assert await _viec(pool, ca, appt) is not None
    await _goi(pool, ca, appt, ket_qua)
    assert await _viec(pool, ca, appt) is None
    # Không sinh việc gọi lại thay thế.
    assert await _viec(pool, ca, appt, "GOI_LAI") is None


async def test_rut_lai_thi_viec_quay_lai_so_van_con_nguoi_bam(
    pool: asyncpg.Pool,
) -> None:
    ca = await dung_ca(pool)
    st = await _st_kham(pool)
    appt = await _lich(ca, st, ngay=3)
    id_ = await _goi(pool, ca, appt)
    assert await _viec(pool, ca, appt) is None
    await TuongTacCskhService(pool).hoan_tac(identity=ca.cskh, tuong_tac_id=id_)
    v = await _viec(pool, ca, appt)
    assert v is not None and v["han_xu_ly"] == _hom_nay()
    # Sổ chỉ thêm: dòng cũ ở lại, ghi rõ ai bấm, lúc nào, ai rút.
    d = await pool.fetchrow(
        "SELECT nhan_vien_staff_id::text AS ai, xay_ra_luc, huy_luc,"
        "       huy_boi_staff_id::text AS ai_rut"
        "  FROM tuong_tac_cskh WHERE id = $1::uuid",
        id_,
    )
    assert d is not None
    assert d["ai"] == ca.cskh.staff_id and d["xay_ra_luc"] is not None
    assert d["huy_luc"] is not None and d["ai_rut"] == ca.cskh.staff_id


@pytest.mark.parametrize("ket_qua", ["CHUA_NGHE_MAY", "HEN_GOI_LAI"])
async def test_goi_khong_duoc_thi_sang_goi_lai(
    pool: asyncpg.Pool, ket_qua: str
) -> None:
    ca = await dung_ca(pool)
    st = await _st_kham(pool)
    appt = await _lich(ca, st, ngay=3)
    await _goi(pool, ca, appt, ket_qua)
    assert await _viec(pool, ca, appt) is None
    gl = await _viec(pool, ca, appt, "GOI_LAI")
    assert gl is not None


async def test_lich_het_song_thi_tu_het_viec(pool: asyncpg.Pool) -> None:
    ca = await dung_ca(pool)
    st = await _st_kham(pool)
    for status in (
        "CANCELLED",
        "NO_SHOW",
        "DOCTOR_DECLINED",
        "COMPLETED",
        "CHECKED_IN",
    ):
        appt = await _lich(ca, st, ngay=2)
        assert await _viec(pool, ca, appt) is not None, status
        await pool.execute(
            "UPDATE appointment SET status = $2,"
            "   ly_do_huy_ma = CASE WHEN $2 = 'CANCELLED' THEN 'BAO_KHI_XAC_NHAN' END,"
            "   cancelled_at = CASE WHEN $2 = 'CANCELLED' THEN now() END"
            " WHERE id = $1::uuid",
            appt,
            status,
        )
        assert await _viec(pool, ca, appt) is None, status


async def test_trang_thai_da_xac_nhan_van_tinh_la_lich_song(pool: asyncpg.Pool) -> None:
    """CSKH_CONFIRMED / CONFIRMED là lịch còn sống: vẫn đòi gọi nếu chưa ai chạm."""
    ca = await dung_ca(pool)
    st = await _st_kham(pool)
    for status in ("CSKH_CONFIRMED", "CONFIRMED"):
        appt = await _lich(ca, st, ngay=2, status=status)
        assert await _viec(pool, ca, appt) is not None, status


async def test_nhan_luat_cskh_khop_chip_giao_dien(pool: asyncpg.Pool) -> None:
    nhan = await pool.fetchval(
        "SELECT nhan FROM luat_cskh WHERE clinic_id = $1::uuid"
        "   AND loai_viec = 'CHO_XAC_NHAN'",
        CLINIC,
    )
    assert nhan == "Gọi xác nhận lịch"
    goc = Path(__file__).resolve().parents[2] / "dashboard/app/(dashboard)/customers"
    chip = (goc / "CustomersView.tsx").read_text(encoding="utf-8")
    assert re.search(r'CHO_XAC_NHAN:\s*"' + nhan + '"', chip)
    nut = (goc / "HanhDongTrangThai.tsx").read_text(encoding="utf-8")
    assert f'tieuDe: "{nhan}"' in nut


async def test_khong_lam_ban_khach_khac_cung_gio(pool: asyncpg.Pool) -> None:
    """Gọi cho lịch của khách A không đóng việc của lịch khác (kể cả cùng khách)."""
    ca = await dung_ca(pool)
    st = await _st_kham(pool)
    a1 = await _lich(ca, st, ngay=2)
    a2 = await _lich(ca, st, ngay=4)
    await _goi(pool, ca, a1)
    assert await _viec(pool, ca, a1) is None
    assert await _viec(pool, ca, a2) is not None
