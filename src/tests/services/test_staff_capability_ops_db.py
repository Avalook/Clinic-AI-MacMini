"""DB integration tests for staff capability operations (Blocker 1: ket_qua.xac_nhan).

Tests:
1. MANAGEMENT grant success
2. MANAGEMENT revoke success
3. non-management -> 403
4. self-grant / self-revoke -> 400
5. wrong clinic -> fail (404)
6. multi-clinic -> fail (fail-closed)
7. reload/read-back thấy đúng capability
8. nhân viên có capability vào được queue
9. nhân viên không có capability -> 403
"""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from clinicai.api.identity import get_current_identity
from clinicai.core.exceptions import ResourceNotFoundError, SafetyGateError
from clinicai.main import app
from clinicai.schemas.staff import Capability
from clinicai.services.staff_service import (
    add_capability,
    get_staff_capabilities,
    revoke_capability,
)
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from tests.services.test_xac_nhan_tep_ket_qua_db import (
    CLINIC_A,
    CLINIC_B,
    _tao_staff,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_TEST") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=8)
    yield p
    await p.close()


async def test_management_grant_and_revoke_service_and_queue(
    pool: asyncpg.Pool,
) -> None:
    """Kiểm tra toàn bộ chu trình cấp/thu hồi capability và ảnh hưởng hàng chờ."""
    async with pool.acquire() as conn:
        staff = await _tao_staff(conn, CLINIC_A, "NURSE_ULTRASOUND")

    tep_svc = TepKetQuaService(pool)

    # 1. Ban đầu nhân viên chưa có capability -> 403 khi vào queue
    with pytest.raises(SafetyGateError, match="chưa được cấp quyền xác nhận"):
        await tep_svc.cho_xac_nhan(identity=staff)

    # 2. MANAGEMENT cấp capability ket_qua.xac_nhan thành công
    dto = await add_capability(
        pool,
        staff_id=staff.staff_id,
        capability=Capability.KET_QUA_XAC_NHAN.value,
        clinic_id=CLINIC_A,
    )
    assert dto.capability == Capability.KET_QUA_XAC_NHAN.value

    # 3. Reload / read-back thấy đúng capability
    caps = await get_staff_capabilities(pool, staff.staff_id, CLINIC_A)
    assert len(caps) == 1
    assert caps[0].capability == Capability.KET_QUA_XAC_NHAN.value

    # 4. Nhân viên đã có capability -> vào được queue thành công
    items = await tep_svc.cho_xac_nhan(identity=staff)
    assert isinstance(items, list)

    # 5. MANAGEMENT thu hồi capability thành công
    revoked = await revoke_capability(
        pool,
        staff_id=staff.staff_id,
        capability=Capability.KET_QUA_XAC_NHAN.value,
        clinic_id=CLINIC_A,
    )
    assert revoked is True

    # 6. Read-back sau khi thu hồi -> rỗng
    caps_after = await get_staff_capabilities(pool, staff.staff_id, CLINIC_A)
    assert len(caps_after) == 0

    # 7. Nhân viên mất capability -> lại bị 403 khi vào queue
    with pytest.raises(SafetyGateError, match="chưa được cấp quyền xác nhận"):
        await tep_svc.cho_xac_nhan(identity=staff)


async def test_grant_and_revoke_fail_closed_for_wrong_or_multi_clinic(
    pool: asyncpg.Pool,
) -> None:
    """Fail-closed: wrong clinic hoặc multi-clinic không cho phép cấp/thu hồi."""
    async with pool.acquire() as conn:
        # Staff B thuộc clinic B
        staff_b = await _tao_staff(conn, CLINIC_B, "CASHIER")

        # Staff Multi thuộc clinic A và B
        staff_multi = await _tao_staff(conn, CLINIC_A, "CASHIER")
        await conn.execute(
            """
            INSERT INTO clinic (id, name, code)
            VALUES ($1::uuid, 'Clinic B Test 2', 'CLINIC_B_2')
            ON CONFLICT (id) DO NOTHING
            """,
            CLINIC_B,
        )
        await conn.execute(
            """
            INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)
            VALUES ($1::uuid, $2::uuid, 'CASHIER', true)
            ON CONFLICT (clinic_id, staff_id, role) DO UPDATE SET is_active = true
            """,
            CLINIC_B,
            staff_multi.staff_id,
        )

    # 1. Wrong clinic (Staff B ở CLINIC_B nhưng gọi từ CLINIC_A) -> fail
    with pytest.raises(ResourceNotFoundError):
        await add_capability(
            pool,
            staff_id=staff_b.staff_id,
            capability=Capability.KET_QUA_XAC_NHAN.value,
            clinic_id=CLINIC_A,
        )
    with pytest.raises(ResourceNotFoundError):
        await revoke_capability(
            pool,
            staff_id=staff_b.staff_id,
            capability=Capability.KET_QUA_XAC_NHAN.value,
            clinic_id=CLINIC_A,
        )

    # 2. Multi-clinic (Staff thuộc nhiều phòng khám) -> fail-closed
    with pytest.raises(ResourceNotFoundError):
        await add_capability(
            pool,
            staff_id=staff_multi.staff_id,
            capability=Capability.KET_QUA_XAC_NHAN.value,
            clinic_id=CLINIC_A,
        )
    with pytest.raises(ResourceNotFoundError):
        await revoke_capability(
            pool,
            staff_id=staff_multi.staff_id,
            capability=Capability.KET_QUA_XAC_NHAN.value,
            clinic_id=CLINIC_A,
        )


async def test_staff_capabilities_http_endpoints_and_guards(
    pool: asyncpg.Pool,
) -> None:
    """Kiểm tra các HTTP endpoint /api/v1/staff/{id}/capabilities."""
    from clinicai.core.database import get_db_pool

    app.dependency_overrides[get_db_pool] = lambda: pool

    async with pool.acquire() as conn:
        mgr = await _tao_staff(conn, CLINIC_A, "MANAGEMENT")
        nurse = await _tao_staff(conn, CLINIC_A, "NURSE_ULTRASOUND")
        cashier = await _tao_staff(conn, CLINIC_A, "CASHIER")

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Non-management (CASHIER) cố cấp quyền -> 403
            app.dependency_overrides[get_current_identity] = lambda: cashier
            res = await client.post(
                f"/api/v1/staff/{nurse.staff_id}/capabilities",
                json={"capability": "ket_qua.xac_nhan"},
            )
            assert res.status_code == 403

            # Non-management cố thu hồi quyền -> 403
            res = await client.delete(
                f"/api/v1/staff/{nurse.staff_id}/capabilities/ket_qua.xac_nhan",
            )
            assert res.status_code == 403

            # 2. Management tự cấp quyền cho chính mình -> 400
            app.dependency_overrides[get_current_identity] = lambda: mgr
            res_self = await client.post(
                f"/api/v1/staff/{mgr.staff_id}/capabilities",
                json={"capability": "ket_qua.xac_nhan"},
            )
            assert res_self.status_code == 400
            assert "tự cấp quyền cho chính mình" in res_self.json()["detail"]

            # Management tự thu hồi quyền của chính mình -> 400
            res_self_rev = await client.delete(
                f"/api/v1/staff/{mgr.staff_id}/capabilities/ket_qua.xac_nhan",
            )
            assert res_self_rev.status_code == 400
            assert "tự thu hồi quyền của chính mình" in res_self_rev.json()["detail"]

            # 3. Management cấp quyền thành công cho Nurse -> 201
            res_grant = await client.post(
                f"/api/v1/staff/{nurse.staff_id}/capabilities",
                json={"capability": "ket_qua.xac_nhan"},
            )
            assert res_grant.status_code == 201
            assert res_grant.json()["capability"] == "ket_qua.xac_nhan"

            # 4. GET /staff/{id}/capabilities trả về đúng capability vừa cấp
            res_get = await client.get(f"/api/v1/staff/{nurse.staff_id}/capabilities")
            assert res_get.status_code == 200
            assert "ket_qua.xac_nhan" in res_get.json()["capabilities"]

            # 5. Management thu hồi quyền thành công qua path param -> 204
            res_rev = await client.delete(
                f"/api/v1/staff/{nurse.staff_id}/capabilities/ket_qua.xac_nhan",
            )
            assert res_rev.status_code == 204

            # 6. GET /staff/{id}/capabilities xác nhận capability đã bị thu hồi
            res_get2 = await client.get(f"/api/v1/staff/{nurse.staff_id}/capabilities")
            assert res_get2.status_code == 200
            assert "ket_qua.xac_nhan" not in res_get2.json()["capabilities"]

            # 7. Management cấp lại và thu hồi qua query param -> 204
            await client.post(
                f"/api/v1/staff/{nurse.staff_id}/capabilities",
                json={"capability": "ket_qua.xac_nhan"},
            )
            res_rev_q = await client.delete(
                f"/api/v1/staff/{nurse.staff_id}/capabilities",
                params={"capability": "ket_qua.xac_nhan"},
            )
            assert res_rev_q.status_code == 204

            # 8. Cấp quyền cho staff không tồn tại -> 404
            res_missing = await client.post(
                f"/api/v1/staff/{uuid4()}/capabilities",
                json={"capability": "ket_qua.xac_nhan"},
            )
            assert res_missing.status_code == 404

            # 9. POST capability khác ket_qua.xac_nhan -> 422/400
            res_other_post = await client.post(
                f"/api/v1/staff/{nurse.staff_id}/capabilities",
                json={"capability": "CASHIER"},
            )
            assert res_other_post.status_code in (400, 422)

            # 10. DELETE capability khác ket_qua.xac_nhan qua path -> 400/422
            res_other_del_path = await client.delete(
                f"/api/v1/staff/{nurse.staff_id}/capabilities/CASHIER",
            )
            assert res_other_del_path.status_code in (400, 422)

            # 11. DELETE capability khác ket_qua.xac_nhan qua query -> 400/422
            res_other_del_query = await client.delete(
                f"/api/v1/staff/{nurse.staff_id}/capabilities",
                params={"capability": "DOCTOR_CONSULTATION"},
            )
            assert res_other_del_query.status_code in (400, 422)
    finally:
        app.dependency_overrides.pop(get_current_identity, None)
        app.dependency_overrides.pop(get_db_pool, None)
