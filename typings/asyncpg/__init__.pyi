# Chỉ cho pyright (LSP của Claude Code). mypy không đọc thư mục này.
# mypy trong CI coi asyncpg là Any; pyright suy kiểu thật từ mã nguồn asyncpg và
# báo ~970 lỗi giả "PoolConnectionProxy is not assignable to Connection".
# Stub này cho pyright nhìn asyncpg giống mypy — chẩn đoán sau mỗi lần sửa khỏi nhiễu.
from typing import Any

def __getattr__(name: str) -> Any: ...
