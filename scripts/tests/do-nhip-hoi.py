#!/usr/bin/env python3
"""Một nhịp hỏi "ai đang giữ chỗ" tốn gì — đo từng chặng.

Tuyền muốn hạ nhịp từ 15s xuống 5s. Câu hỏi thật không phải "5 giây có nhanh
hơn không" (hiển nhiên là có) mà "gấp ba số lần hỏi thì máy chủ có chịu nổi
không". Trả lời được bằng cách đo một nhịp tốn bao nhiêu, rồi nhân lên.

MỘT NHỊP KHÔNG PHẢI MỘT TRUY VẤN. Đường đi thật:

    trình duyệt → route Next → GoTrue (xác thực token, QUA MẠNG)
                             → FastAPI → Postgres

`supabase.auth.getUser()` không đọc cookie mà GỌI SANG GoTrue để xác minh token
— đó mới là chặng đắt nhất, và nó vô hình khi chỉ nhìn code.

    docker exec clinicai_staging-api-1 python /tmp/do-nhip-hoi.py
"""

from __future__ import annotations

import asyncio
import os
import statistics
import time
from datetime import datetime, timedelta, timezone

import httpx

VN = timezone(timedelta(hours=7))
LAN = 30


async def do(ten: str, goi) -> float:
    mau: list[float] = []
    for _ in range(LAN):
        t = time.perf_counter()
        await goi()
        mau.append((time.perf_counter() - t) * 1000)
    mau.sort()
    p50, p95 = mau[len(mau) // 2], mau[int(len(mau) * 0.95)]
    print(f"  {ten:38} p50 {p50:6.1f}ms   p95 {p95:6.1f}ms")
    return p50


async def main() -> None:
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    ngay = (datetime.now(VN) + timedelta(days=21)).date().isoformat()

    async with httpx.AsyncClient(timeout=30.0) as http:
        # Một tài khoản thật để có token thật — token giả sẽ bị GoTrue từ chối
        # ở bước đầu và bài đo sẽ đo đường lỗi, không đo đường thật.
        r = await http.get(
            f"{base}/auth/v1/admin/users?per_page=1",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
        r.raise_for_status()
        print(f"\nMỗi nhịp hỏi gồm ba chặng ({LAN} lần đo mỗi chặng):\n")

        # Chặng 1 — GoTrue xác minh token. Đây là chặng route Next làm TRƯỚC khi
        # gọi FastAPI, và là chặng duy nhất đi ra khỏi tiến trình để hỏi một
        # dịch vụ khác chỉ để biết "người này là ai".
        t_auth = await do(
            "GoTrue xác minh token",
            lambda: http.get(
                f"{base}/auth/v1/settings", headers={"apikey": key}
            ),
        )

        # Chặng 2 — FastAPI đọc bảng chỗ đang giữ.
        api = httpx.AsyncClient(
            base_url="http://localhost:8000/api/v1",
            timeout=30.0,
            headers={"X-API-Key": os.environ.get("BACKEND_API_KEY", "")},
        )
        t_api = await do(
            "FastAPI + Postgres đọc chỗ đang giữ",
            lambda: api.get("/appointments/slot-hold", params={"date": ngay}),
        )
        await api.aclose()

    tong = t_auth + t_api
    print(f"\n  {'CỘNG LẠI':38} {tong:6.1f}ms mỗi nhịp\n")

    print("  Bốn CSKH mở màn đặt lịch cùng lúc:")
    for nhip in (15, 5):
        moi_giay = 4 / nhip
        print(
            f"    nhịp {nhip:2}s → {moi_giay:4.2f} lượt/giây, "
            f"máy chủ bận {moi_giay * tong / 1000 * 100:4.1f}% một lõi"
        )
    print()


if __name__ == "__main__":
    asyncio.run(main())
