"""Ba endpoint danh mục phải trả 200, kể cả khi hàng có UUID.

CẢ BA TỪNG TRẢ 500, VÌ HAI LÝ DO KHÁC NHAU.

  * ``/catalog/wards`` và ``/catalog/service-types`` chọn những cột không tồn
    tại trong schema (``ward.id``, ``ward.parent_id``, ``service_type.aliases``…).
    ``test_sql_columns_exist.py`` canh chuyện đó.
  * ``/catalog/booking-channels`` chọn đúng cột, nhưng đưa thẳng ``dict`` của
    asyncpg vào ``JSONResponse`` — cột ``id`` là UUID, và ``json.dumps`` không
    tuần tự hoá được UUID.

Lỗi thứ hai chỉ lộ ra SAU KHI lỗi thứ nhất được vá: câu SQL sai tên cột thì chết
trước, chưa bao giờ chạy tới bước tuần tự hoá. Một bài kiểm chỉ soi schema sẽ
báo xanh cho một endpoint vẫn 500. Đây là lý do bài kiểm này gọi endpoint thật
qua TestClient thay vì chỉ đọc câu SQL.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from clinicai.api.identity import ClinicRole, StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.main import app

CLINIC_ID = "a0000000-0000-4000-8000-000000000001"

# Hàng giống hệt asyncpg trả về: id là UUID thật, không phải chuỗi.
_ROWS: dict[str, list[dict[str, object]]] = {
    "/api/v1/catalog/wards": [
        {
            "code": "24823",
            "name": "1 Bảo Lộc",
            "full_name": "Phường 1 Bảo Lộc",
            "province_code": "68",
        }
    ],
    "/api/v1/catalog/service-types": [
        {
            "id": uuid.uuid4(),
            "code": "KPK",
            "name": "Khám Phụ khoa",
            "default_duration_minutes": 30,
            "is_active": True,
        }
    ],
    "/api/v1/catalog/booking-channels": [
        {"id": uuid.uuid4(), "name": "Zalo", "is_active": True}
    ],
}


@pytest.fixture
def client() -> Iterator[TestClient]:
    pool = MagicMock()
    pool.fetch = AsyncMock()
    app.dependency_overrides[get_db_pool] = lambda: pool
    app.dependency_overrides[get_current_identity] = lambda: StaffIdentity(
        staff_id="staff-1",
        auth_user_id="user-1",
        full_name="CSKH A",
        department="CSKH",
        role=ClinicRole.CSKH,
        clinic_id=CLINIC_ID,
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )
    client = TestClient(app)
    client.__dict__["_pool"] = pool
    yield client
    app.dependency_overrides.clear()


@pytest.mark.parametrize("path", sorted(_ROWS))
def test_catalog_endpoint_serialises_its_rows(path: str, client: TestClient) -> None:
    client.__dict__["_pool"].fetch.return_value = _ROWS[path]

    response = client.get(path, headers={"X-API-Key": "test"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list) and body, f"{path} trả rỗng"
    # UUID phải ra chuỗi — nếu lọt object UUID thì .json() đã nổ ở trên.
    if "id" in body[0]:
        assert isinstance(body[0]["id"], str)


def test_service_types_are_scoped_to_the_callers_clinic(client: TestClient) -> None:
    """Danh mục là dữ liệu theo phòng khám, không phải dùng chung."""
    pool = client.__dict__["_pool"]
    pool.fetch.return_value = _ROWS["/api/v1/catalog/service-types"]

    client.get("/api/v1/catalog/service-types", headers={"X-API-Key": "test"})

    sql, *args = pool.fetch.await_args.args
    assert "clinic_id = $1::uuid" in sql
    assert args == [CLINIC_ID]
