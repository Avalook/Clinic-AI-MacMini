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
from typing import Any

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

        # NÉM LỖI SAU KHI GIAO DỊCH ĐÃ COMMIT, KHÔNG PHẢI TRONG NÓ.
        #
        # Bản đầu tăng failed_attempts rồi `raise` ngay bên trong
        # `async with conn.transaction()`. Ném lỗi trong giao dịch thì asyncpg
        # ROLLBACK — nên bộ đếm không bao giờ được ghi, và chống dò mật khẩu
        # trông như có mà thực ra không chạy. Sai kiểu tệ nhất: mọi bài kiểm
        # dùng mock đều xanh, endpoint vẫn trả đúng câu, chỉ có cái khoá là
        # không bao giờ đóng.
        #
        # Nên: quyết định trong giao dịch, ghi trong giao dịch, thoát ra bình
        # thường, RỒI mới ném.
        ket_qua: str = "ok"
        con_lai_phut = 0
        row: Any = None

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

                now = datetime.now(timezone.utc)
                if row is None:
                    ket_qua = "sai"
                elif row["locked_until"] is not None and row["locked_until"] > now:
                    ket_qua = "khoa"
                    con_lai_phut = (
                        int((row["locked_until"] - now).total_seconds() // 60) + 1
                    )
                else:
                    khop: bool = await conn.fetchval(
                        "SELECT $1 = extensions.crypt($2, $1)",
                        row["password_hash"],
                        password,
                    )
                    if not khop:
                        lan = row["failed_attempts"] + 1
                        # ÉP KIỂU TỪNG THAM SỐ. `$2` vừa được gán vào một cột
                        # integer vừa nằm trong phép so sánh, nên Postgres từ
                        # chối: "inconsistent types deduced for parameter $2 —
                        # text versus integer". Gặp thật khi chạy lần đầu, và
                        # nó biến "sai mật khẩu" thành 500 — tức là tự nó phá
                        # đúng cái tính chất một-câu-trả-lời ở trên, vì 500 và
                        # 422 phân biệt được từ ngoài.
                        await conn.execute(
                            """
                            UPDATE public.app_credential
                               SET failed_attempts = $2::int,
                                   locked_until = CASE WHEN $2::int >= $3::int
                                                       THEN now() + $4::interval
                                                       ELSE locked_until END,
                                   updated_at = now()
                             WHERE staff_id = $1::uuid
                            """,
                            row["staff_id"],
                            lan,
                            MAX_FAILED,
                            LOCK_FOR,
                        )
                        logger.info(
                            "login_failed", staff_id=str(row["staff_id"]), attempt=lan
                        )
                        ket_qua = "sai"
                    elif row["is_active"] is False:
                        # Nhân viên đã nghỉ: cùng một câu trả lời như sai mật
                        # khẩu. Đúng mật khẩu mà vẫn không vào được là chuyện
                        # của quản lý, không phải chuyện giải thích ở màn đăng
                        # nhập.
                        logger.info(
                            "login_inactive_staff", staff_id=str(row["staff_id"])
                        )
                        ket_qua = "sai"
                    else:
                        await conn.execute(
                            """
                            UPDATE public.app_credential
                               SET failed_attempts = 0, locked_until = NULL,
                                   last_login_at = now(), updated_at = now()
                             WHERE staff_id = $1::uuid
                            """,
                            row["staff_id"],
                        )

        # Giao dịch đã đóng — bộ đếm ở trên CHẮC CHẮN đã ghi. Giờ mới ném.
        if ket_qua == "khoa":
            # Cái này THÌ nói thật: nó không tiết lộ gì thêm cho kẻ dò (họ tự
            # biết mình vừa sai nhiều lần) mà lại là thông tin người thật cần.
            raise ValidationError(
                f"Sai quá nhiều lần. Thử lại sau {con_lai_phut} phút."
            )
        if ket_qua == "sai":
            # MỘT CÂU TRẢ LỜI CHO MỌI KIỂU SAI: email không tồn tại, mật khẩu
            # sai, nhân viên đã nghỉ. Phân biệt chúng là nói cho người đang dò
            # biết email nào CÓ THẬT, tức tặng họ nửa đầu của mỗi cặp thông tin
            # đăng nhập.
            raise ValidationError("Email hoặc mật khẩu không đúng.")

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
