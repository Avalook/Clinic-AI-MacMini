"""Cửa đăng nhập của ứng dụng, thay signInWithPassword của GoTrue.

ĐÂY LÀ ENDPOINT DUY NHẤT KHÔNG ĐÒI TOKEN — vì nó là nơi cấp token. Mọi endpoint
khác đều đi qua get_current_identity. Chính vì thế nó cũng là endpoint duy nhất
mà một người lạ trên internet gọi được, nên chống dò mật khẩu nằm ngay trong
auth_service (đếm lần sai + khoá tạm, lưu trong DATABASE chứ không trong bộ nhớ
tiến trình — bộ nhớ mất sau mỗi lần deploy, và kẻ dò chỉ cần chờ đúng lúc đó).
"""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.core.database import get_db_pool
from clinicai.services.auth_service import AuthService

router = APIRouter()


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    # Trần 200 để một request khổng lồ không thành đường bắt máy chủ băm bcrypt
    # cho vui. Mật khẩu thật không ai dài tới đó.
    password: str = Field(min_length=1, max_length=200)


class LoginResponse(BaseModel):
    access_token: str
    expires_at: str
    staff_id: str


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> LoginResponse:
    """Kiểm mật khẩu, trả token dùng được ngay cho mọi endpoint khác."""
    result = await AuthService(pool).login(email=body.email, password=body.password)
    return LoginResponse(
        access_token=result.token,
        expires_at=result.expires_at.isoformat(),
        staff_id=result.staff_id,
    )
