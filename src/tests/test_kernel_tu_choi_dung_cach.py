"""Kernel quy trình TỪ CHỐI thế nào — bốn cách, bốn câu khác nhau.

Đây là những nhánh chỉ chạy khi có chuyện bất thường, nên chúng cũng là những
nhánh dễ mục nhất: không ai bấm tới hằng ngày, và một câu từ chối viết sai chỉ
lộ ra đúng lúc người dùng đang bối rối nhất.

Bốn tình huống được canh ở đây đều là chuyện THẬT ở quầy:
  · bấm vào một việc vừa bị người khác huỷ  → 404
  · bấm "xong" hai lần, lần sau đã sai trạng thái → 409 nói rõ đang ở đâu
  · bấm "xong" khi còn bước chưa làm → 409 nói rõ CÒN BƯỚC NÀO
  · hai người cùng bấm một lúc → 409 bảo tải lại, không ghi đè im lặng
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.work_item_service import Command, WorkItemService


def _identity() -> StaffIdentity:
    return StaffIdentity(
        staff_id="s-le-tan",
        auth_user_id="u1",
        full_name="Lễ tân A",
        department="Tiếp đón",
        role=ClinicRole.RECEPTION,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


class _GiaoDich:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_: object) -> bool:
        return False


class _Conn:
    def __init__(
        self,
        *,
        item: dict[str, Any] | None,
        blockers: list[dict[str, Any]] | None = None,
        updated: dict[str, Any] | None = None,
    ) -> None:
        self._item = item
        self._blockers = blockers or []
        self._updated = updated

    def transaction(self) -> _GiaoDich:
        return _GiaoDich()

    async def fetchrow(self, sql: str, *_args: Any) -> Any:
        if "FROM work_item w" in sql and "FOR UPDATE" in sql:
            return self._item
        if "UPDATE" in sql:
            return self._updated
        return None

    async def fetch(self, *_args: Any) -> list[dict[str, Any]]:
        return self._blockers

    async def execute(self, *_args: Any) -> str:
        return "OK"


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    def acquire(self) -> Any:
        conn = self._conn

        class _A:
            async def __aenter__(self) -> _Conn:
                return conn

            async def __aexit__(self, *_: object) -> bool:
                return False

        return _A()


def _viec(status: str = "IN_PROGRESS") -> dict[str, Any]:
    return {
        "id": "w1",
        "status": status,
        "version": 3,
        "node_code": "LUOTKHAM-02",
        "clinic_id": "a0000000-0000-4000-8000-000000000001",
        "actor_roles": ["RECEPTION"],
        "node_name": "Xác minh người bệnh",
        "membership_role": "RECEPTION",
    }


def _chay(conn: _Conn, command: Command = "complete", **kw: Any) -> Any:
    return asyncio.run(
        WorkItemService(_Pool(conn)).issue(
            work_item_id="w1", command=command, identity=_identity(), **kw
        )
    )


def test_viec_khong_ton_tai_hoac_khac_phong_kham_thi_404() -> None:
    """Cùng một câu trả lời cho hai chuyện — CÓ CHỦ Ý.

    Truy vấn ghép cả `clinic_id` lẫn tư cách thành viên, nên "không có việc ấy"
    và "việc của phòng khám khác" ra cùng kết quả rỗng. Nói khác đi là tiết lộ
    sự tồn tại của dữ liệu phòng khám bên cạnh.
    """
    with pytest.raises(NotFoundError):
        _chay(_Conn(item=None))


def test_sai_trang_thai_thi_409_va_noi_ro_dang_o_dau() -> None:
    """Bấm 'xong' hai lần: lần sau việc đã COMPLETED."""
    with pytest.raises(ConflictError) as loi:
        _chay(_Conn(item=_viec("COMPLETED")))
    cau = str(loi.value)
    assert "COMPLETED" in cau, "phải nói việc đang ở trạng thái nào"
    assert "complete" in cau, "và nói người dùng vừa định làm gì"


def test_con_buoc_chua_xong_thi_409_va_liet_ke_ten_buoc() -> None:
    """Không nói 'còn vướng' chung chung — nói CÒN BƯỚC NÀO.

    Người ở quầy phải đi giục đúng người; một câu 'còn bước chưa xong' bắt họ
    đi hỏi vòng quanh cả phòng khám.
    """
    conn = _Conn(
        item=_viec("IN_PROGRESS"),
        blockers=[{"node_code": "LUOTKHAM-03"}, {"node_code": "LUOTKHAM-05"}],
    )
    with pytest.raises(ConflictError) as loi:
        _chay(conn)
    cau = str(loi.value)
    assert "LUOTKHAM-03" in cau and "LUOTKHAM-05" in cau


def test_hai_nguoi_cung_bam_thi_409_bao_tai_lai_chu_khong_ghi_de() -> None:
    """Khoá lạc quan: câu UPDATE kèm `version` cũ trả rỗng khi ai đó đi trước.

    Ghi đè im lặng ở đây nghĩa là thao tác của người kia biến mất mà không ai
    biết — thứ tệ hơn hẳn một câu bảo tải lại.
    """
    conn = _Conn(item=_viec("IN_PROGRESS"), updated=None)
    with pytest.raises(ConflictError) as loi:
        _chay(conn, expected_version=3)
    assert "tải lại" in str(loi.value)
