"""Kiểm trùng hồ sơ: mệnh đề SQL phải có đủ ba vế.

Notion §2 Lễ tân, tiêu chí kỹ thuật 2: *"kiểm tra khả năng trùng theo SĐT đã
chuẩn hoá, KẾT HỢP HỌ TÊN VÀ NĂM SINH; chỉ cảnh báo để người có quyền xử lý,
không tự động gộp hồ sơ."*

Trước đây chỉ có SĐT và CCCD. Một người khai số mới — hoặc chưa có CCCD — tạo
hồ sơ thứ hai mà không gì cảnh báo, và hai hồ sơ của cùng một người là hai lịch
sử khám bị chia đôi.

Test này kiểm CÂU TRUY VẤN được dựng ra, vì phần hành vi đã được thử trực tiếp
trên prod (6 tình huống, rollback): cùng SĐT · SĐT dạng +84 · tên không dấu +
đúng năm sinh · tên có dấu + đúng năm sinh · đúng tên sai năm (không báo) ·
người khác hẳn (không báo).
"""

from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from typing import Any

import pytest

from clinicai.schemas.patient import PatientCreateDTO
from clinicai.services.mpi_service import MPIService

CLINIC = "a0000000-0000-4000-8000-000000000001"
LOCATION = "b0000000-0000-4000-8000-000000000001"


class _Conn:
    def __init__(self) -> None:
        self.query = ""
        self.args: tuple[Any, ...] = ()

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        self.query = query
        self.args = args
        return []


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    @asynccontextmanager
    async def acquire(self):  # type: ignore[no-untyped-def]
        yield self._conn


def _dto(**over: Any) -> PatientCreateDTO:
    base: dict[str, Any] = {"location_id": LOCATION, "full_name": "Nguyễn Thị Hoa"}
    base.update(over)
    return PatientCreateDTO(**base)


async def _query_for(dto: PatientCreateDTO) -> tuple[str, tuple[Any, ...]]:
    conn = _Conn()
    await MPIService.find_candidates(_Pool(conn), dto, CLINIC)  # type: ignore[arg-type]
    return conn.query, conn.args


@pytest.mark.asyncio
async def test_name_and_birth_year_produce_a_clause() -> None:
    q, args = await _query_for(_dto(date_of_birth=datetime.date(1990, 5, 2)))
    assert "full_name_unaccent" in q
    assert "Nguyễn Thị Hoa" in args
    assert 1990.0 in args


@pytest.mark.asyncio
async def test_it_matches_against_the_generated_column_not_a_recomputed_one() -> None:
    """`full_name_unaccent` là cột GENERATED và có chỉ mục.

    Gọi `unaccent(full_name)` ở vế trái vẫn ra kết quả đúng nhưng bỏ qua
    `idx_patient_full_name_unaccent`, và mở đường cho hai công thức chuẩn hoá
    lệch nhau — một bên đổi 'đ'→'d', một bên không.
    """
    q, _ = await _query_for(_dto(date_of_birth=datetime.date(1990, 5, 2)))
    assert "full_name_unaccent =" in q
    assert "f_unaccent(full_name)" not in q


@pytest.mark.asyncio
async def test_birth_year_falls_back_to_date_of_birth() -> None:
    """Cột `birth_year` do ứng dụng ghi và trên prod chỉ điền 25/49 hồ sơ.

    Chỉ dựa vào nó thì đúng một nửa số hồ sơ âm thầm không bao giờ báo trùng —
    một lỗ hổng không có triệu chứng nào.
    """
    q, _ = await _query_for(_dto(date_of_birth=datetime.date(1990, 5, 2)))
    assert "coalesce(birth_year, date_part('year', date_of_birth))" in q


@pytest.mark.asyncio
async def test_no_birthday_means_no_name_clause() -> None:
    """Tên KHÔNG kèm năm sinh thì quá rộng: 'Nguyễn Thị Hoa' là hàng nghìn người.

    Cảnh báo trùng cho mỗi cái tên phổ biến sẽ bị Lễ tân bấm bỏ qua theo phản
    xạ, và lần nó nói thật cũng bị bỏ qua nốt.
    """
    q, _ = await _query_for(_dto(phone_primary="0912000111"))
    assert "full_name_unaccent" not in q


@pytest.mark.asyncio
async def test_nothing_to_match_on_skips_the_database_entirely() -> None:
    conn = _Conn()
    out = await MPIService.find_candidates(  # type: ignore[arg-type]
        _Pool(conn), _dto(), CLINIC
    )
    assert out == []
    assert conn.query == "", "không có gì để so thì đừng chạm database"


@pytest.mark.asyncio
async def test_the_search_stays_inside_one_clinic() -> None:
    """Trùng ở phòng khám khác KHÔNG phải là trùng — và gộp qua ranh giới đó
    vừa sai vừa là rò rỉ dữ liệu."""
    q, args = await _query_for(_dto(date_of_birth=datetime.date(1990, 5, 2)))
    assert "clinic_id =" in q
    assert CLINIC in args
