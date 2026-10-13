from dataclasses import replace
from datetime import date, datetime
from uuid import uuid4

import asyncpg
import pytest

from clinicai.api.identity import ClinicRole
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.cashier_scope_service import _ROSTER, allowed_roster
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
        await service.save(
            manager,
            {
                "nhan_vien_theo_ca": False,
                "truong_ca_theo_ngay": False,
                "tai_chinh_day_du": True,
            },
        )
        flag_off = await service.access(q.thu_ngan, day.isoformat())
        assert not flag_off["legacy"] and flag_off["cac_ca"] == ["SANG"]
        with pytest.raises(SafetyGateError):
            await service.authorize(
                q.thu_ngan,
                tu=day.isoformat(),
                den=day.isoformat(),
                ca="TOI",
                co_so=access["co_so_ids"][0],
            )
        await service.save(
            manager,
            {
                "nhan_vien_theo_ca": True,
                "truong_ca_theo_ngay": True,
                "tai_chinh_day_du": True,
            },
        )
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
        assert head["ngay_truc"] == [
            {
                "ngay": day.isoformat(),
                "co_so_theo_ca": head["co_so_theo_ca"],
            }
        ]
        assert "FULL" in head["cac_ca"]
        await service.save(
            manager,
            {
                "nhan_vien_theo_ca": False,
                "truong_ca_theo_ngay": False,
                "tai_chinh_day_du": True,
            },
        )
        strict_head = replace(
            q.thu_ngan, vai_theo_vi_tri=frozenset({ClinicRole.TRUONG_CA})
        )
        assert (await service.access(strict_head, day.isoformat()))["tai_chinh"]
        assert not (await service.access(strict_head, "2026-10-13"))["ban_hang"]
        other = await pool.fetchval(
            """INSERT INTO work_roster
            (clinic_id,week_start,work_date,shift,station,staff_id,staff_name,status)
            VALUES ($1::uuid,$2::date,$2::date,'SANG','T1_LETAN',
                $3::uuid,'Mixed role','APPROVED') RETURNING id""",
            manager.clinic_id,
            date(2026, 10, 11),
            q.thu_ngan.staff_id,
        )
        staff_day = await service.access(strict_head, "2026-10-11")
        assert staff_day["ban_hang"] and not staff_day["tai_chinh"]
        assert staff_day["cac_ca"] == ["SANG"]
        assert staff_day["ngay_truc"][1]["co_so_theo_ca"] == {
            "SANG": staff_day["co_so_ids"]
        }
        await pool.execute("DELETE FROM work_roster WHERE id=$1", other)
        with pytest.raises(SafetyGateError):
            await service.authorize(
                strict_head,
                tu="2026-10-13",
                den="2026-10-13",
                ca="FULL",
                co_so=strict_head.location_id,
            )
        await service.save(
            manager,
            {
                "nhan_vien_theo_ca": True,
                "truong_ca_theo_ngay": True,
                "tai_chinh_day_du": True,
            },
        )
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


@pytest.mark.db
@pytest.mark.asyncio
async def test_shared_head_locations_ignore_primary_location(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "clinicai.services.report_access_service.now_vn",
        lambda: datetime(2026, 10, 12, 8),
    )
    q = await tao_quay(pool)
    service = ReportAccessService(pool)
    day = date(2026, 10, 12)
    code = uuid4().hex[:8]
    other = await pool.fetchval(
        "INSERT INTO clinic_location(clinic_id,code,name)"
        " VALUES($1::uuid,$2,'Head other') RETURNING id::text",
        q.thu_ngan.clinic_id,
        code,
    )
    inactive = await pool.fetchval(
        "INSERT INTO clinic_location(clinic_id,code,name,is_active)"
        " VALUES($1::uuid,$2,'Inactive',false) RETURNING id::text",
        q.thu_ngan.clinic_id,
        code + "X",
    )
    foreign_clinic = await pool.fetchval(
        "INSERT INTO clinic(code,name,timezone)"
        " VALUES($1,'Foreign head','Asia/Ho_Chi_Minh') RETURNING id::text",
        code,
    )
    foreign_location = await pool.fetchval(
        "INSERT INTO clinic_location(clinic_id,code,name)"
        " VALUES($1::uuid,$2,'Foreign location') RETURNING id::text",
        foreign_clinic,
        code,
    )
    roster = await pool.fetchval(
        "INSERT INTO work_roster"
        " (clinic_id,week_start,work_date,shift,station,staff_id,staff_name,status)"
        " VALUES($1::uuid,$2::date,$2::date,'SANG','DIEU_PHOI',"
        " $3::uuid,'Head locations','APPROVED') RETURNING id",
        q.thu_ngan.clinic_id,
        day,
        q.thu_ngan.staff_id,
    )
    room = await pool.fetchval(
        "INSERT INTO clinic_room(clinic_id,location_id,code,name,node_code)"
        " VALUES($1::uuid,$2::uuid,$3,'Head bound','THU_NGAN') RETURNING id::text",
        q.thu_ngan.clinic_id,
        other,
        code,
    )
    bound_station = "TEST__DIEU_PHOI__2"
    await pool.execute(
        "INSERT INTO vi_tri_lam_viec(clinic_id,code,ten,room_id)"
        " VALUES($1::uuid,$2,'Head bound',$3::uuid)",
        q.thu_ngan.clinic_id,
        bound_station,
        room,
    )
    try:
        active = {
            r["id"]
            for r in await pool.fetch(
                "SELECT id::text FROM clinic_location WHERE clinic_id=$1::uuid"
                " AND is_active",
                q.thu_ngan.clinic_id,
            )
        }
        access = await service.access(q.thu_ngan, day.isoformat())
        assert set(access["co_so_ids"]) == active
        assert other in active and inactive not in access["co_so_ids"]
        assert foreign_location not in access["co_so_ids"]
        rows = await pool.fetch(_ROSTER, q.thu_ngan.clinic_id, q.thu_ngan.staff_id)
        assert set(allowed_roster([dict(r) for r in rows], "dich_vu")) == active
        assert not (await service.access(q.thu_ngan, "2026-10-11"))["ban_hang"]
        await pool.execute(
            "UPDATE work_roster SET station=$2 WHERE id=$1", roster, bound_station
        )
        assert (await service.access(q.thu_ngan, day.isoformat()))["co_so_ids"] == [
            other
        ]
        rows = await pool.fetch(_ROSTER, q.thu_ngan.clinic_id, q.thu_ngan.staff_id)
        assert set(allowed_roster([dict(r) for r in rows], "thuoc")) == {other}
        await pool.execute(
            "UPDATE work_roster SET status='REJECTED' WHERE id=$1", roster
        )
        assert not (await service.access(q.thu_ngan, day.isoformat()))["ban_hang"]
    finally:
        await pool.execute("DELETE FROM work_roster WHERE id=$1", roster)
        await pool.execute(
            "DELETE FROM vi_tri_lam_viec WHERE clinic_id=$1::uuid AND code=$2",
            q.thu_ngan.clinic_id,
            bound_station,
        )
        await pool.execute("DELETE FROM clinic_room WHERE id=$1::uuid", room)
        await pool.execute(
            "DELETE FROM clinic_location WHERE id=$1::uuid", foreign_location
        )
        await pool.execute("DELETE FROM clinic WHERE id=$1::uuid", foreign_clinic)
        await pool.execute(
            "DELETE FROM clinic_location WHERE id=ANY($1::uuid[])", [other, inactive]
        )
