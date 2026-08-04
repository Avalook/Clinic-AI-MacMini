"""Một asyncpg.Pool giả, đủ để chạy phần SQL của service mà không cần database.

VÌ SAO CÓ FILE NÀY. Các service ghi (`consent_service`, `clinic_config_service`)
có phần lớn logic nằm giữa các lệnh SQL: kiểm tra trước khi xoá, dịch lỗi
database thành câu người vận hành đọc được, gói nhiều lệnh vào một transaction.
Phần đó chỉ chạy được khi có pool — và nếu không kiểm được thì nó không được
kiểm, vì bài kiểm tích hợp cần một Postgres thật thì CI không chạy mỗi lần.

CÁI NÀY KHÔNG THAY THẾ BÀI KIỂM TRÊN PROD. Nó không biết ràng buộc, không biết
trigger, không biết RLS. Mọi luật ở tầng database vẫn phải thử bằng SQL thật
(và đã thử — xem chú thích ở từng migration). Cái này chỉ trả lời: mã Python
gọi đúng thứ tự, và xử lý đúng thứ database trả về.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any


class FakeConn:
    """Ghi lại mọi câu lệnh, trả kết quả đã dựng sẵn theo thứ tự."""

    def __init__(self, results: list[Any]) -> None:
        #: Hàng đợi kết quả: mỗi lần fetchrow/fetchval/fetch lấy một cái. Một
        #: `Exception` trong hàng đợi sẽ được NÉM RA — đó là cách dựng lại
        #: UniqueViolationError mà không cần database thật.
        self._results = list(results)
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []

    def _next(self, kind: str, query: str, args: tuple[Any, ...]) -> Any:
        self.calls.append((kind, " ".join(query.split()), args))
        if not self._results:
            return None
        out = self._results.pop(0)
        if isinstance(out, Exception):
            raise out
        return out

    async def fetchrow(self, query: str, *args: Any) -> Any:
        return self._next("fetchrow", query, args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        return self._next("fetchval", query, args)

    async def fetch(self, query: str, *args: Any) -> Any:
        return self._next("fetch", query, args) or []

    async def execute(self, query: str, *args: Any) -> str:
        self.calls.append(("execute", " ".join(query.split()), args))
        return "OK"

    async def executemany(self, query: str, args: Any) -> None:
        self.calls.append(("executemany", " ".join(query.split()), tuple(args)))

    def transaction(self) -> FakeConn:
        return self

    async def __aenter__(self) -> FakeConn:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False


class FakePool:
    """Đủ hình dạng cho `pool.fetch`, `pool.fetchrow`, và `async with acquire()`."""

    def __init__(self, *results: Any) -> None:
        self.conn = FakeConn(list(results))

    async def fetch(self, query: str, *args: Any) -> Any:
        return await self.conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Any:
        return await self.conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        return await self.conn.fetchval(query, *args)

    def acquire(self) -> FakeConn:
        return self.conn

    # ── tra cứu cho phần assert ────────────────────────────────────────────

    def queries(self, kind: str | None = None) -> list[str]:
        return [q for k, q, _ in self.conn.calls if kind is None or k == kind]

    def wrote(self, fragment: str) -> bool:
        return any(fragment in q for q in self.queries())
