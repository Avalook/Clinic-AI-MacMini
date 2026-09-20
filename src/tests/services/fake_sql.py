"""Pool giả TRẢ LỜI THEO NỘI DUNG CÂU SQL (không theo thứ tự gọi).

Bổ sung cho `fake_pool.py` (hàng đợi theo thứ tự): các service luật 15/09/2026
gọi nhiều câu, thứ tự đổi theo nhánh — dựng kết quả theo "câu có chứa chuỗi X
thì trả Y" dễ đọc hơn và không vỡ khi thêm một câu đọc phụ.

Như fake_pool: KHÔNG thay bài kiểm database thật (trigger, RLS, ràng buộc) —
những thứ ấy đã có smoke Postgres và test SQL riêng.
"""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Any

Rule = tuple[str, Any]


class SqlConn:
    def __init__(self, rules: list[Rule]) -> None:
        self.rules = rules
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []

    def _answer(self, kind: str, query: str, args: tuple[Any, ...]) -> Any:
        q = " ".join(query.split())
        self.calls.append((kind, q, args))
        for needle, value in self.rules:
            if needle in q:
                if isinstance(value, Exception):
                    raise value
                if callable(value):
                    return value(*args)
                return value
        return None

    async def fetchrow(self, query: str, *args: Any) -> Any:
        return self._answer("fetchrow", query, args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        return self._answer("fetchval", query, args)

    async def fetch(self, query: str, *args: Any) -> Any:
        return self._answer("fetch", query, args) or []

    async def execute(self, query: str, *args: Any) -> str:
        self._answer("execute", query, args)
        return "OK"

    async def executemany(self, query: str, args: Any) -> None:
        self.calls.append(("executemany", " ".join(query.split()), tuple(args)))

    def transaction(self, *args: Any, **kwargs: Any) -> SqlConn:
        return self

    def acquire(self) -> SqlConn:
        return self

    async def __aenter__(self) -> SqlConn:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False

    # ── tra cứu cho assert ────────────────────────────────────────────────
    def da_goi(self, needle: str) -> list[tuple[Any, ...]]:
        return [args for _, q, args in self.calls if needle in q]

    def events(self) -> list[tuple[Any, ...]]:
        return self.da_goi("INSERT INTO event_log")


def pool(*rules: Rule) -> SqlConn:
    """Một đối tượng vừa là pool vừa là connection."""
    return SqlConn(list(rules))


def luon(value: Any) -> Callable[..., Any]:
    return lambda *_: value
