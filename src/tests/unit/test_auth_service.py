"""Cửa đăng nhập: đúng thì vào, sai thì không nói vì sao, dò thì bị khoá."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.auth_service import AUDIENCE, MAX_FAILED, AuthService

# Đủ 32 byte: khoá ngắn hơn làm PyJWT cảnh báo và làm nhiễu output test.
SECRET = "khoa-thu-cho-bai-kiem-du-32-byte-tro-len"
HASH = "$2a$06$" + "x" * 53  # 60 ký tự, đúng dạng bcrypt


def _pool(row: dict[str, Any] | None, *, khop: bool = True) -> tuple[Any, MagicMock]:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=row)
    conn.fetchval = AsyncMock(return_value=khop)
    conn.execute = AsyncMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=tx)
    acquire = MagicMock()
    acquire.__aenter__ = AsyncMock(return_value=conn)
    acquire.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire)
    return pool, conn


def _row(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "staff_id": "11111111-1111-4111-8111-111111111111",
        "password_hash": HASH,
        "locked_until": None,
        "failed_attempts": 0,
        "auth_user_id": "22222222-2222-4222-8222-222222222222",
        "is_active": True,
    }
    base.update(over)
    return base


@pytest.mark.asyncio
async def test_dang_nhap_dung_thi_cap_token_doc_duoc_boi_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Token phải cùng hình dạng GoTrue — identity.py không được sửa gì."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    pool, _ = _pool(_row())

    kq = await AuthService(pool).login(email="BS.A@dr4women.local", password="dung")

    claims = jwt.decode(kq.token, SECRET, algorithms=["HS256"], audience=AUDIENCE)
    # `sub` phải là auth_user_id: identity.py tra staff qua cột ấy.
    assert claims["sub"] == "22222222-2222-4222-8222-222222222222"
    assert claims["aud"] == AUDIENCE
    # PostgREST đọc `role` để chọn vai Postgres — thiếu nó là phần đọc dữ liệu
    # hiện tại gãy, dù đăng nhập vẫn "thành công".
    assert claims["role"] == AUDIENCE
    assert kq.expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_ba_kieu_sai_deu_tra_ve_dung_mot_cau(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Không nói cho người dò biết email nào có thật.

    Phân biệt "email không tồn tại" với "sai mật khẩu" là tặng họ nửa đầu của
    mỗi cặp thông tin đăng nhập.
    """
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    cau = "Email hoặc mật khẩu không đúng."

    # (1) email không tồn tại
    pool, _ = _pool(None)
    with pytest.raises(ValidationError) as e1:
        await AuthService(pool).login(email="ai.do@dr4women.local", password="x")

    # (2) mật khẩu sai
    pool, _ = _pool(_row(), khop=False)
    with pytest.raises(ValidationError) as e2:
        await AuthService(pool).login(email="bs.a@dr4women.local", password="sai")

    # (3) nhân viên đã nghỉ, mật khẩu vẫn đúng
    pool, _ = _pool(_row(is_active=False))
    with pytest.raises(ValidationError) as e3:
        await AuthService(pool).login(email="bs.a@dr4women.local", password="dung")

    assert str(e1.value) == str(e2.value) == str(e3.value) == cau


@pytest.mark.asyncio
async def test_sai_lan_thu_nam_thi_khoa_tam(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    pool, conn = _pool(_row(failed_attempts=MAX_FAILED - 1), khop=False)

    with pytest.raises(ValidationError):
        await AuthService(pool).login(email="bs.a@dr4women.local", password="sai")

    # Lần sai được ghi vào DATABASE, không phải bộ nhớ tiến trình: một lần
    # deploy không được xoá sạch bộ đếm cho kẻ đang dò.
    assert conn.execute.await_count == 1
    sql = conn.execute.await_args.args[0]
    assert "failed_attempts" in sql and "locked_until" in sql
    assert conn.execute.await_args.args[2] == MAX_FAILED


@pytest.mark.asyncio
async def test_dang_bi_khoa_thi_khong_kiem_mat_khau_nua(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Đang khoá thì từ chối NGAY, không băm mật khẩu.

    Băm bcrypt tốn CPU có chủ ý. Nếu vẫn băm trong lúc khoá thì cái khoá không
    còn bảo vệ máy chủ nữa — kẻ dò vẫn ép được mỗi request một lượt băm.
    """
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    khoa_toi = datetime.now(timezone.utc) + timedelta(minutes=9)
    pool, conn = _pool(_row(locked_until=khoa_toi))

    with pytest.raises(ValidationError) as e:
        await AuthService(pool).login(email="bs.a@dr4women.local", password="dung")

    assert "Thử lại sau" in str(e.value)
    conn.fetchval.assert_not_awaited()


@pytest.mark.asyncio
async def test_thieu_khoa_ky_thi_hong_on_ao(monkeypatch: pytest.MonkeyPatch) -> None:
    """Thiếu SUPABASE_JWT_SECRET phải nổ ở ĐÂY, không phải ở request sau.

    Cấp một token không ai xác thực được thì người dùng "đăng nhập thành công"
    rồi bị từ chối ở mọi thao tác tiếp theo — lỗi hiện ra xa chỗ gây ra nó.
    """
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    pool, _ = _pool(_row())

    with pytest.raises(ValidationError) as e:
        await AuthService(pool).login(email="bs.a@dr4women.local", password="dung")
    assert "SUPABASE_JWT_SECRET" in str(e.value)
