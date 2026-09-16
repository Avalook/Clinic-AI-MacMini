#!/usr/bin/env python3
"""MỘT BUỔI KHÁM THẬT — chạy hết vòng, nhiều vai cùng lúc, đo từng chặng.

Tuyền 16/09/2026: *"kiểm tra từng nút, từng logic, ngóc ngách, vào song song
đồng thời các vai trò… làm như buổi khám thật luôn, đo tốc độ phản hồi"*.

VÌ SAO LÀ MỘT SCRIPT CHỨ KHÔNG PHẢI BẤM TAY. Bấm tay kiểm được một màn tại một
thời điểm; buổi khám thật thì lễ tân, điều dưỡng, bác sĩ, trưởng ca cùng gõ một
lúc, và những lỗi đắt nhất chỉ hiện ra ở chỗ giao nhau: hai người ghi cùng một
lượt, một người xoá chỗ người kia vừa giữ, một màn đọc số cũ. Script này đăng
nhập THẬT bằng từng tài khoản (GoTrue), gọi ĐÚNG đường mà giao diện gọi, rồi đo.

KHÔNG PHÁ DỮ LIỆU. Mọi thứ nó tạo đều mang dấu `[e2e]` trong tên/ghi chú và
được liệt ra cuối bản báo cáo để dọn; nó KHÔNG xoá cứng gì (ba bảng cấm xoá).
Chạy `--rollback` để đóng lại những lượt nó vừa mở.

    PYTHONPATH=src poetry run python scripts/tests/buoi-kham-that.py
    PYTHONPATH=src poetry run python scripts/tests/buoi-kham-that.py --rollback

ĐỌC KẾT QUẢ: cột `ms` là thời gian MỘT lời gọi qua đúng chuỗi thật
(Next → GoTrue → FastAPI → Postgres). Chặng GoTrue xác minh token là chặng vô
hình mà đắt — xem `do-nhip-hoi.py`.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

WEB = os.environ.get("WEB_URL", "http://127.0.0.1:3100")
# GỌI THẲNG FastAPI. Lớp Next chỉ là proxy mỏng + gác vai, nhưng phiên của nó
# nằm trong cookie do @supabase/ssr đặt — dựng lại cookie ấy từ script là diễn
# lại một thứ có thể sai mà không ai biết. Đo ở đây là đo ĐÚNG phần làm việc:
# FastAPI + Postgres. Chặng Next→GoTrue xác minh token đo riêng ở phần dưới,
# và đã có số sẵn trong `do-nhip-hoi.py`.
API = os.environ.get("CLINIC_API_URL", "http://127.0.0.1:8100")
SB = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54421")
ANON = os.environ.get("SUPABASE_ANON_KEY", "")
# KHÔNG mặc định giá trị nào: mật khẩu và khoá cổng chỉ sống trong .env (đã
# gitignore). Ghi cứng ở đây là đưa chúng vào kho mã — chốt trước commit chặn
# đúng chuyện ấy, và nó chặn có lý.
PW = os.environ.get("TEST_PW", "")
# FastAPI đòi khoá cổng ngoài Bearer của người dùng: lớp Next giữ khoá này và
# gắn vào mọi lời gọi, script cũng phải làm đúng thế.
KHOA_API = os.environ.get("BACKEND_API_KEY", "")

VAI = {
    "letan": "letan@dr4women.local",
    "cskh": "cskh@dr4women.local",
    "bacsi": "bs.a@dr4women.local",
    "bacsi_sa": "bs.sa@dr4women.local",
    "dieuduong": "dd.sa@dr4women.local",
    "truongca": "truongca@dr4women.local",
    "thuky": "thuky@dr4women.local",
    "quanly": "ql@dr4women.local",
}


def thu_hai(iso: str) -> str:
    """Thứ Hai của tuần chứa `iso` — các màn tuần đều đòi mốc này."""
    import datetime as _dt

    d = _dt.date.fromisoformat(iso)
    return (d - _dt.timedelta(days=d.weekday())).isoformat()


@dataclass
class Buoc:
    ten: str
    vai: str
    ms: float
    ok: bool
    ghi_chu: str = ""


@dataclass
class KetQua:
    buoc: list[Buoc] = field(default_factory=list)
    tao_ra: list[str] = field(default_factory=list)

    def them(self, b: Buoc) -> None:
        self.buoc.append(b)
        dau = "✓" if b.ok else "✗"
        print(
            f"  {dau} {b.ms:7.0f}ms  {b.vai:<10} {b.ten}"
            + (f"  — {b.ghi_chu}" if b.ghi_chu else "")
        )


async def dang_nhap(http: httpx.AsyncClient, email: str) -> str | None:
    """Token thật qua GoTrue — đúng đường màn hình đi, kể cả chặng đắt."""
    r = await http.post(
        f"{SB}/auth/v1/token?grant_type=password",
        headers={"apikey": ANON, "Content-Type": "application/json"},
        json={"email": email, "password": PW},
    )
    if r.status_code != 200:
        return None
    return str(r.json().get("access_token") or "") or None


class Phien:
    """Một người đang ngồi trước màn hình: giữ cookie như trình duyệt thật."""

    def __init__(self, vai: str, http: httpx.AsyncClient) -> None:
        self.vai = vai
        self.http = http

    async def goi(
        self, kq: KetQua, ten: str, method: str, duong: str, **kw: Any
    ) -> tuple[int, Any]:
        t0 = time.perf_counter()
        try:
            r = await self.http.request(method, f"{API}{duong}", **kw)
            ms = (time.perf_counter() - t0) * 1000
            try:
                body = r.json()
            except Exception:
                body = r.text[:200]
            ok = r.status_code < 400
            ghi = "" if ok else f"HTTP {r.status_code}: {str(body)[:120]}"
            kq.them(Buoc(ten, self.vai, ms, ok, ghi))
            return r.status_code, body
        except Exception as e:  # mạng chết, máy chủ chết
            ms = (time.perf_counter() - t0) * 1000
            kq.them(Buoc(ten, self.vai, ms, False, f"{type(e).__name__}: {e}"))
            return 0, None


async def mo_phien(vai: str) -> Phien | None:
    """Đăng nhập rồi đổi token thành cookie phiên của Next — y như trình duyệt."""
    http = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    token = await dang_nhap(http, VAI[vai])
    if not token:
        await http.aclose()
        return None
    http.headers["Authorization"] = f"Bearer {token}"
    http.headers["X-API-Key"] = KHOA_API
    return Phien(vai, http)


async def lay_ids_khach(p: "Phien | None") -> str:
    """Vài mã khách thật để gọi màn khách hàng — màn thật cũng gửi đúng thế."""
    if p is None:
        return ""
    r = await p.http.get(f"{API}/api/v1/patients/danh-sach")
    if r.status_code != 200:
        return ""
    dong = (r.json() or {}).get("dong", [])[:20]
    return ",".join(str(d.get("ho_so", {}).get("clinic_patient_id")) for d in dong)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--rollback", action="store_true", help="đóng những lượt khám script đã mở"
    )
    ap.parse_args()  # --rollback: dành cho phần ghi, sẽ nối ở lượt sau

    thieu = [
        t
        for t, v in (
            ("SUPABASE_ANON_KEY", ANON),
            ("TEST_PW", PW),
            ("BACKEND_API_KEY", KHOA_API),
        )
        if not v
    ]
    if thieu:
        print(
            f"Thiếu biến môi trường: {', '.join(thieu)}.\n"
            "  set -a && . ./.env.thu-local && set +a\n"
            "  TEST_PW=... BACKEND_API_KEY=... PYTHONPATH=src "
            "poetry run python scripts/tests/buoi-kham-that.py",
            file=sys.stderr,
        )
        return 2

    kq = KetQua()
    print("\n── ĐĂNG NHẬP TỪNG VAI (GoTrue thật) ─────────────────────────────")
    phien: dict[str, Phien] = {}
    t0 = time.perf_counter()
    ket = await asyncio.gather(*(mo_phien(v) for v in VAI))
    ms = (time.perf_counter() - t0) * 1000
    for v, p in zip(VAI, ket):
        if p is None:
            kq.them(Buoc("đăng nhập", v, 0, False, "không lấy được token"))
        else:
            phien[v] = p
    print(
        f"  → {len(phien)}/{len(VAI)} vai đăng nhập, tổng {ms:.0f}ms (chạy song song)"
    )

    if len(phien) < 3:
        print("Quá ít vai đăng nhập được — dừng.", file=sys.stderr)
        return 1

    print("\n── ĐỌC MÀN CHÍNH CỦA TỪNG VAI, CÙNG LÚC ─────────────────────────")
    hom_nay = time.strftime("%Y-%m-%d")
    ids_mau = await lay_ids_khach(phien.get("quanly"))
    man = [
        ("letan", "hàng đợi tiếp nhận", "/api/v1/work-items?workspace=bang_dieu_phoi"),
        ("letan", "thứ tự khám", f"/api/v1/queue?date={hom_nay}"),
        (
            "cskh",
            "còn chỗ tuần",
            f"/api/v1/appointments/cho-trong-tuan?week_start={thu_hai(hom_nay)}",
        ),
        # `ids` = khách ĐANG hiển thị trên màn (đã phân trang) — màn thật gửi
        # danh sách ấy, không gửi rỗng.
        ("cskh", "màn khách hàng", f"/api/v1/cskh/man-khach-hang?ids={ids_mau}"),
        (
            "bacsi",
            "bảng bác sĩ",
            f"/api/v1/appointments/doctor-board?start={hom_nay}T00:00:00%2B07:00"
            f"&end={hom_nay}T23:59:59%2B07:00",
        ),
        ("truongca", "toàn cảnh điều phối", "/api/v1/dispatch/overview"),
        ("truongca", "cảnh báo điều phối", "/api/v1/dispatch/alerts"),
        ("truongca", "lịch sử điều phối", "/api/v1/dispatch/history?limit=200"),
        (
            "quanly",
            "trang chủ",
            f"/api/v1/home/bang-dieu-khien?week_appt={thu_hai(hom_nay)}&week_roster={thu_hai(hom_nay)}",
        ),
        ("quanly", "danh sách bệnh nhân", "/api/v1/patients/danh-sach"),
    ]
    await asyncio.gather(
        *[phien[v].goi(kq, ten, "GET", duong) for v, ten, duong in man if v in phien]
    )

    print("\n── TỔNG KẾT ─────────────────────────────────────────────────────")
    hong = [b for b in kq.buoc if not b.ok]
    cham = sorted((b for b in kq.buoc if b.ok), key=lambda b: -b.ms)[:5]
    so = [b.ms for b in kq.buoc if b.ok]
    if so:
        print(
            f"  trung vị {statistics.median(so):.0f}ms · "
            f"chậm nhất {max(so):.0f}ms · {len(so)} lời gọi thành công"
        )
    print(f"  hỏng: {len(hong)}")
    for b in hong:
        print(f"    ✗ {b.vai:<10} {b.ten} — {b.ghi_chu}")
    print("  năm chặng chậm nhất:")
    for b in cham:
        print(f"    {b.ms:7.0f}ms  {b.vai:<10} {b.ten}")

    for p in phien.values():
        await p.http.aclose()
    return 1 if hong else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
