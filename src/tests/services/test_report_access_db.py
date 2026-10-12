from dataclasses import replace
from datetime import date, datetime

import asyncpg
import pytest

from clinicai.api.identity import ClinicRole
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.report_access_service import ReportAccessService
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai
from tests.services.test_tien_thuoc_cp1_db import tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_settings_roster_and_revoke(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "clinicai.services.report_access_service.now_vn",
        lambda: datetime(2026, 10, 12, 8),
    )
    q = await tao_quay(pool)
    manager = await _nguoi_vai(q, "MANAGEMENT")
    service = ReportAccessService(pool)
    original = await service.settings(manager)
    day = date(2026, 10, 12)
    try:
        await service.save(
            manager,
            {
                "nhan_vien_theo_ca": True,
                "truong_ca_theo_ngay": True,
                "tai_chinh_day_du": True,
            },
        )
        assert (await service.access(manager, day.isoformat()))["tai_chinh"]
        assert not (await service.access(q.thu_ngan, day.isoformat()))["ban_hang"]
        with pytest.raises(SafetyGateError):
            await service.settings(q.thu_ngan)
        roster_id = await pool.fetchval(
            """INSERT INTO work_roster
                (clinic_id,week_start,work_date,shift,station,staff_id,staff_name,status)
                VALUES ($1::uuid,$2::date,$2::date,'SANG','T1_LETAN',
                        $3::uuid,'Test report','APPROVED') RETURNING id""",
            manager.clinic_id,
            day,
            q.thu_ngan.staff_id,
        )
        access = await service.access(q.thu_ngan, day.isoformat())
        assert access["cac_ca"] == ["SANG"]
        assert access["ban_hang"] and not access["tai_chinh"]
        assert (await service.access(q.thu_ngan, None))["cac_ca"] == ["SANG"]
        await service.authorize(
            q.thu_ngan,
            tu=day.isoformat(),
            den=day.isoformat(),
            ca="SANG",
            co_so=access["co_so_ids"][0],
        )
        with pytest.raises(SafetyGateError):
            await service.authorize(
                q.thu_ngan,
                tu=day.isoformat(),
                den=day.isoformat(),
                ca="TOI",
                co_so=access["co_so_ids"][0],
            )
        await pool.execute("UPDATE work_roster SET shift='FULL' WHERE id=$1", roster_id)
        assert (await service.access(q.thu_ngan, day.isoformat()))["cac_ca"] == [
            "SANG",
            "CHIEU",
            "TOI",
            "FULL",
        ]
        await pool.execute(
            "UPDATE work_roster SET station='DIEU_PHOI',shift='TOI' WHERE id=$1",
            roster_id,
        )
        head = await service.access(q.thu_ngan, day.isoformat())
        assert head["tai_chinh"] and head["tai_chinh_day_du"]
        assert not (await service.access(q.thu_ngan, "2026-10-13"))["ban_hang"]
        past = await service.access(q.thu_ngan, "2026-10-13")
        assert past["co_the_mo"] and not past["ban_hang"]
        await service.save(
            manager,
            {
                "nhan_vien_theo_ca": False,
                "truong_ca_theo_ngay": True,
                "tai_chinh_day_du": True,
            },
        )
        current_head = replace(
            q.thu_ngan, vai_theo_vi_tri=frozenset({ClinicRole.TRUONG_CA})
        )
        assert not (await service.access(current_head, "2026-10-13"))["ban_hang"]
        with pytest.raises(SafetyGateError):
            await service.authorize(
                current_head,
                tu="2026-10-13",
                den="2026-10-13",
                ca="FULL",
                co_so=current_head.location_id,
            )
        await service.save(
            manager,
            {
                "nhan_vien_theo_ca": True,
                "truong_ca_theo_ngay": True,
                "tai_chinh_day_du": True,
            },
        )
        await pool.execute(
            "UPDATE work_roster SET status='PENDING' WHERE id=$1", roster_id
        )
        assert not (await service.access(q.thu_ngan, day.isoformat()))["ban_hang"]
        await pool.execute(
            "UPDATE work_roster SET status='REJECTED' WHERE id=$1", roster_id
        )
        assert not (await service.access(q.thu_ngan, day.isoformat()))["ban_hang"]
    finally:
        await pool.execute(
            "DELETE FROM work_roster WHERE staff_id=$1::uuid", q.thu_ngan.staff_id
        )
        await service.save(manager, original)
