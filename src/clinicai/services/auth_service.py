"""Đăng nhập bằng kho mật khẩu của chính ứng dụng, thay GoTrue.

VÌ SAO. GoTrue tự dựng schema `auth` và tự tạo role Postgres lúc khởi động —
cần CREATEROLE, thứ database cho thuê không cấp. Chừng nào đăng nhập còn nằm ở
GoTrue thì hệ thống còn chỉ chạy được trên database mình tự cài.

TOKEN GIỮ NGUYÊN HÌNH DẠNG CŨ, CÓ CHỦ Ý. Cùng thuật toán (HS256), cùng khoá
(SUPABASE_JWT_SECRET), cùng bộ claim (`sub`, `aud`, `role`, `email`). Nhờ vậy
`identity.py` xác thực được mà không sửa một dòng, và 249 chỗ trong dashboard
đang dựa vào phiên hiện tại vẫn chạy. Đổi hình dạng token cùng lúc với đổi nơi
cấp token là gộp hai thay đổi rủi ro vào một lần — nếu hỏng thì không biết hỏng
vì cái nào.

MẬT KHẨU KHÔNG ĐỔI. auth.users lưu bcrypt và pgcrypto `crypt()` kiểm đúng định
dạng ấy, nên bảng app_credential chép nguyên chuỗi băm sang: không ai phải đặt
lại mật khẩu.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import asyncpg
import jwt
import structlog

from clinicai.api.exceptions import ValidationError

logger = structlog.get_logger()

#: Token sống bao lâu. 12 tiếng = một ca trực dài, để nhân viên không bị đá ra
#: giữa buổi khám. Ngắn hơn thì phiền, dài hơn thì một máy bỏ quên ở quầy còn
#: mở cửa quá lâu.
TOKEN_TTL = timedelta(hours=12)

#: Khoá tạm sau bao nhiêu lần sai liên tiếp, và khoá bao lâu.
#: Năm lần là quá đủ cho người gõ nhầm; mười lăm phút đủ để một máy dò mật khẩu
#: mất hết ý nghĩa mà người thật thì đi pha xong ấm trà.
MAX_FAILED = 5
LOCK_FOR = timedelta(minutes=15)

#: GoTrue đặt aud = "authenticated"; identity.py kiểm đúng giá trị này.
AUDIENCE = "authenticated"


@dataclass(frozen=True)
class LoginResult:
    token: str
    expires_at: datetime
    staff_id: str


class AuthService:
    """Kiểm mật khẩu và cấp token."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def login(self, *, email: str, password: str) -> LoginResult:
        email = (email or "").strip()
        if not email or not password:
            raise ValidationError("Nhập email và mật khẩu.")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT c.staff_id, c.password_hash, c.locked_until,
                           c.failed_attempts, s.auth_user_id, s.is_active
                      FROM public.app_credential c
                      JOIN public.staff s ON s.id = c.staff_id
                     WHERE lower(c.email) = lower($1)
                     FOR UPDATE OF c
                    """,
                    email,
                )

                # MỘT CÂU TRẢ LỜI CHO MỌI KIỂU SAI.
                #
                # Email không tồn tại, mật khẩu sai, tài khoản đã nghỉ — cả ba
                # trả về đúng một câu. Phân biệt chúng là nói cho người đang dò
                # biết email nào CÓ THẬT trong hệ thống, tức là tặng họ nửa
                # đầu của mỗi cặp thông tin đăng nhập.
                sai = ValidationError("Email hoặc mật khẩu không đúng.")

                if row is None:
                    raise sai

                now = datetime.now(timezone.utc)
                if row["locked_until"] is not None and row["locked_until"] > now:
                    # Cái này THÌ nói thật, vì nó không tiết lộ gì thêm cho kẻ
                    # dò (họ tự biết mình vừa sai nhiều lần) mà lại là thông tin
                    # người thật cần: chờ bao lâu.
                    con_lai = int((row["locked_until"] - now).total_seconds() // 60) + 1
                    raise ValidationError(
                        f"Sai quá nhiều lần. Thử lại sau {con_lai} phút."
                    )

                khop: bool = await conn.fetchval(
                    "SELECT $1 = extensions.crypt($2, $1)",
                    row["password_hash"],
                    password,
                )

                if not khop:
                    lan = row["failed_attempts"] + 1
                    await conn.execute(
                        """
                        UPDATE public.app_credential
                           SET failed_attempts = $2,
                               locked_until = CASE WHEN $2 >= $3
                                                   THEN now() + $4::interval
                                                   ELSE locked_until END,
                               updated_at = now()
                         WHERE staff_id = $1
                        """,
                        row["staff_id"],
                        lan,
                        MAX_FAILED,
                        LOCK_FOR,
                    )
                    logger.info(
                        "login_failed", staff_id=str(row["staff_id"]), attempt=lan
                    )
                    raise sai

                # Nhân viên đã nghỉ: cùng một câu trả lời như sai mật khẩu.
                # Đúng mật khẩu mà vẫn không vào được là chuyện của quản lý,
                # không phải chuyện để giải thích ở màn đăng nhập.
                if row["is_active"] is False:
                    logger.info("login_inactive_staff", staff_id=str(row["staff_id"]))
                    raise sai

                await conn.execute(
                    """
                    UPDATE public.app_credential
                       SET failed_attempts = 0, locked_until = NULL,
                           last_login_at = now(), updated_at = now()
                     WHERE staff_id = $1
                    """,
                    row["staff_id"],
                )

        expires_at = datetime.now(timezone.utc) + TOKEN_TTL
        token = _mint(
            subject=str(row["auth_user_id"]),
            email=email,
            expires_at=expires_at,
        )
        logger.info("login_ok", staff_id=str(row["staff_id"]))
        return LoginResult(
            token=token, expires_at=expires_at, staff_id=str(row["staff_id"])
        )


def _mint(*, subject: str, email: str, expires_at: datetime) -> str:
    """Cấp token cùng hình dạng GoTrue để identity.py không phải đổi gì."""
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        # Nói thẳng thay vì cấp một token không ai xác thực được. Thiếu khoá là
        # lỗi cấu hình triển khai, và nó phải hỏng ồn ào lúc đăng nhập chứ
        # không phải im lặng ở request tiếp theo.
        raise ValidationError("Máy chủ chưa cấu hình SUPABASE_JWT_SECRET.")
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": subject,
            "aud": AUDIENCE,
            # PostgREST đọc claim này để chọn vai Postgres. Giữ nguyên để phần
            # đọc dữ liệu hiện tại không đổi gì trong lần thay này.
            "role": AUDIENCE,
            "email": email,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        },
        secret,
        algorithm="HS256",
    )
