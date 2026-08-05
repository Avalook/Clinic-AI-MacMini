#!/usr/bin/env python3
"""Sinh bộ khoá cho một bộ Supabase tự dựng.

    python3 scripts/sinh-khoa-supabase.py            # in ra màn hình
    python3 scripts/sinh-khoa-supabase.py --ghi      # ghi ra .env.supabase-local

BA THỨ, VÀ CHÚNG KHÔNG CÙNG LOẠI:

    JWT_SECRET          bí mật THẬT. GoTrue ký token bằng nó, PostgREST và
                        Realtime kiểm token bằng nó. Lộ nó là ai cũng tự ký
                        được một token vai `service_role`.
    ANON_KEY            KHÔNG phải mật khẩu. Nó là một JWT ký sẵn mang đúng một
                        claim `role: anon`, nằm trong bundle trình duyệt và ai
                        cũng đọc được. An toàn đến từ RLS, không từ việc giấu
                        khoá này.
    SERVICE_ROLE_KEY    JWT mang `role: service_role` — vai BỎ QUA RLS. Chỉ
                        backend giữ. Lọt ra client là mở toàn bộ dữ liệu.

ĐỔI `JWT_SECRET` LÀ VÔ HIỆU MỌI PHIÊN ĐANG MỞ, và hai khoá kia phải sinh lại
theo — chúng được ký bằng chính nó.

Cố ý KHÔNG phụ thuộc thư viện ngoài: script này chạy trên một VPS vừa dựng
xong, lúc chưa cài gì ngoài Python có sẵn.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sys
from pathlib import Path

#: Mốc phát hành cố định thay vì `now()`. Chạy script hai lần với cùng
#: JWT_SECRET sẽ ra cùng khoá — dễ đối chiếu khi nghi hai nơi lệch cấu hình.
IAT = 1767225600  # 01/01/2026
EXP = IAT + 20 * 365 * 86400


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def ky_jwt(payload: dict[str, object], secret: str) -> str:
    """JWT HS256 — đủ dùng, và không kéo theo thư viện nào."""
    head = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    msg = f"{head}.{body}".encode()
    sig = _b64(hmac.new(secret.encode(), msg, hashlib.sha256).digest())
    return f"{head}.{body}.{sig}"


def sinh() -> dict[str, str]:
    # ≥32 ký tự: GoTrue từ chối bí mật ngắn hơn, và nó có lý.
    jwt_secret = secrets.token_urlsafe(48)
    khung = {"iss": "supabase", "iat": IAT, "exp": EXP}
    return {
        "SUPABASE_JWT_SECRET": jwt_secret,
        "SUPABASE_ANON_KEY": ky_jwt({**khung, "role": "anon"}, jwt_secret),
        "SUPABASE_SERVICE_ROLE_KEY": ky_jwt({**khung, "role": "service_role"}, jwt_secret),
        "SUPABASE_DB_PASSWORD": secrets.token_urlsafe(24),
    }


def main() -> int:
    khoa = sinh()
    noi_dung = (
        "# Bộ Supabase tự dựng — sinh bằng scripts/sinh-khoa-supabase.py\n"
        "#\n"
        "# TỆP NÀY LÀ BÍ MẬT. `.gitignore` đã chặn `.env.*`, nhưng kiểm lại\n"
        "# trước khi commit: `git check-ignore -v .env.supabase-local`.\n"
        "#\n"
        "# ANON_KEY không phải mật khẩu — nó nằm trong bundle trình duyệt. Còn\n"
        "# JWT_SECRET và SERVICE_ROLE_KEY thì lộ là mở toàn bộ dữ liệu.\n\n"
        + "".join(f"{k}={v}\n" for k, v in khoa.items())
        + "\nSUPABASE_DB_PORT=54332\nSUPABASE_API_PORT=54331\n"
    )

    if "--ghi" in sys.argv:
        dich = Path(".env.supabase-local")
        if dich.exists():
            # KHÔNG ghi đè. Đè lên bộ khoá đang chạy là làm mọi người đang đăng
            # nhập bị văng ra, và không lấy lại được bộ cũ.
            print(f"!! {dich} đã tồn tại — không ghi đè.", file=sys.stderr)
            print("   Xoá tay nếu thật sự muốn sinh bộ mới.", file=sys.stderr)
            return 1
        dich.write_text(noi_dung)
        dich.chmod(0o600)
        print(f"đã ghi {dich} (quyền 600)")
    else:
        print(noi_dung)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
