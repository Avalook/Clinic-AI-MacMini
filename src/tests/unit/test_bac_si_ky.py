"""`bac_si_ky`: chỗ ký chỉ in BÁC SĨ — không bao giờ lùi về người bấm."""

from __future__ import annotations

import datetime as dt
from typing import Any

from clinicai.core.clock import CLINIC_TZ
from clinicai.services import bac_si_ky
from clinicai.services.bac_si_ky import (
    BacSi,
    bac_si_ky_in,
    sql_join_bac_si_chi_dinh,
    sql_join_bac_si_ky_luot,
)


class _Conn:
    """Conn giả: không ai là bác sĩ, phòng không có lịch, lượt không có bác sĩ."""

    def __init__(self, phong: list[dict[str, Any]] | None = None) -> None:
        self.phong = phong or []
        self.ngay: list[Any] = []

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        if "work_roster" in sql:
            self.ngay.append(args[2])
            return self.phong
        return []  # bac_si_trong: không ai là bác sĩ

    async def fetchrow(self, sql: str, *args: Any) -> None:
        return None

    async def fetchval(self, sql: str, *args: Any) -> str:
        return "BS Phòng"


async def test_khong_ai_la_bac_si_thi_tra_none_khong_lui_ve_nguoi_bam() -> None:
    ky = await bac_si_ky_in(
        _Conn(),
        clinic_id="c",
        service_order_id="o",
        nguoi_bam=("dieu-duong", None),
        luc=dt.datetime(2026, 9, 28, 10, 0, tzinfo=CLINIC_TZ),
    )
    assert ky is None


async def test_lich_phong_theo_ngay_cua_luc_khong_phai_hom_nay() -> None:
    conn = _Conn(
        phong=[
            {
                "id": "bs-hom-qua",
                "station": "VT",
                "shift": "FULL",
                "status": "APPROVED",
                "settings": {},
            }
        ]
    )
    # 23:30 giờ UTC ngày 27 = 06:30 sáng 28/09 giờ Việt Nam.
    luc = dt.datetime(2026, 9, 27, 23, 30, tzinfo=dt.UTC)
    ky = await bac_si_ky_in(
        conn,
        clinic_id="c",
        service_order_id="o",
        nguoi_bam="dieu-duong",
        luc=luc,
    )
    assert ky == BacSi("bs-hom-qua", "BS Phòng")
    assert conn.ngay == [dt.date(2026, 9, 28)]


def test_thu_tu_ung_vien_bac_si_chi_dinh() -> None:
    sql = sql_join_bac_si_chi_dinh("o", "b")
    i = [
        sql.index(x)
        for x in (
            "o.authorized_by",
            "o.recorded_by",
            "attending_doctor_id",
            "aa.doctor_id",
        )
    ]
    assert i == sorted(i)
    assert "'DOCTOR', 'ULTRASOUND_DOCTOR'" in sql and sql.endswith(") b ON true")


def test_thu_tu_ung_vien_nguoi_ky_luot() -> None:
    sql = sql_join_bac_si_ky_luot("v", "k")
    i = [
        sql.index(x)
        for x in ("v.finalized_by", "v.attending_doctor_id", "aa.doctor_id")
    ]
    assert i == sorted(i)
    assert bac_si_ky._VAI_SQL in sql
