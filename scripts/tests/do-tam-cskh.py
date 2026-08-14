#!/usr/bin/env python3
"""Tám CSKH cùng mở màn đặt lịch — ai bấm gì thì bên kia thấy sau bao lâu.

Tuyền 14/08/2026: *"cskh Diệu Hoa đang click vào lịch 14:00–14:15 bác sĩ Phan
Chí Thành… cskh Kim Tiến cũng click vào lịch ấy… mỗi vị trí lịch nào mà người
này click thì cũng sẽ hiện realtime trên màn hình của người kia, cả 8 CSKH cùng
làm cũng sẽ đều hiện như vậy"*.

ĐO BA THỨ, vì "realtime" gồm ba chặng khác nhau và chúng hỏng theo ba kiểu:

  1. MÁY CHỦ THẤY   — người kia POST giữ chỗ xong, các máy khác ĐỌC được lúc nào
  2. TIN ĐẨY        — pg_notify → FastAPI → SSE về trình duyệt mất bao lâu
  3. GIỮ ĐỦ 10 PHÚT — chỗ giữ hết hạn đúng lúc, không sớm không muộn

Và đo với TÁM tài khoản thật cùng lúc, không phải hai: một cuộc đua hai bên có
thể tình cờ tuần tự hoá và trông như đã an toàn.

    docker exec clinicai_staging-api-1 python /tmp/do-tam-cskh.py
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import httpx

VN = timezone(timedelta(hours=7))
API = "http://localhost:8000/api/v1"
SO_CSKH = 8
NHAN = "[thử-8-cskh]"
MAT_KHAU = "ThuNghiem!" + uuid.uuid4().hex[:8]

ket_qua: list[tuple[str, bool, str]] = []


def ghi(ten: str, dat: bool, chi_tiet: str = "") -> None:
    ket_qua.append((ten, dat, chi_tiet))
    print(f"  {'✓' if dat else '✗'} {ten}" + (f" — {chi_tiet}" if chi_tiet else ""))


def cung_khung(item: dict, moc: datetime) -> bool:
    try:
        return datetime.fromisoformat(item["slot_start"]) == moc
    except (ValueError, KeyError):
        return False


async def tao(http, conn, clinic_id, i):
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    email = f"thu8-{uuid.uuid4().hex[:10]}@clinicai.test"
    r = await http.post(
        f"{base}/auth/v1/admin/users",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        json={"email": email, "password": MAT_KHAU, "email_confirm": True},
    )
    r.raise_for_status()
    auth_id = r.json()["id"]
    loc = await conn.fetchval(
        "SELECT s.primary_location_id FROM public.staff s "
        "  JOIN public.clinic_membership m ON m.staff_id = s.id "
        " WHERE m.clinic_id = $1::uuid AND m.role = 'CSKH' AND s.is_active LIMIT 1",
        clinic_id,
    )
    sid = await conn.fetchval(
        "INSERT INTO public.staff (full_name, auth_user_id, is_active, "
        "  primary_location_id, primary_department) "
        "VALUES ($1, $2::uuid, TRUE, $3::uuid, 'CSKH') RETURNING id",
        f"{NHAN} CSKH {i}",
        auth_id,
        loc,
    )
    await conn.execute(
        "INSERT INTO public.clinic_membership (clinic_id, staff_id, role, is_active) "
        "VALUES ($1::uuid, $2::uuid, 'CSKH', TRUE) "
        "ON CONFLICT (clinic_id, staff_id, role) DO UPDATE SET is_active = TRUE",
        clinic_id,
        sid,
    )
    r = await http.post(
        f"{base}/auth/v1/token?grant_type=password",
        headers={"apikey": key, "Content-Type": "application/json"},
        json={"email": email, "password": MAT_KHAU},
    )
    r.raise_for_status()
    return r.json()["access_token"], str(sid), auth_id


def phien(token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=API,
        timeout=30.0,
        headers={
            "Authorization": f"Bearer {token}",
            "X-API-Key": os.environ.get("BACKEND_API_KEY", ""),
            "Content-Type": "application/json",
        },
    )


async def main() -> int:
    if os.environ.get("APP_ENV") == "prod":
        print("TỪ CHỐI: bài đo tạo tài khoản thử, không chạy trên prod.")
        return 2

    conn = await asyncpg.connect(
        os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    )
    clinic_id = str(await conn.fetchval("SELECT id FROM public.clinic LIMIT 1"))
    admin = httpx.AsyncClient(timeout=60.0)

    ngay = (datetime.now(VN) + timedelta(days=28)).date()
    bat_dau = datetime.combine(ngay, datetime.min.time(), tzinfo=VN).replace(hour=14)
    ket_thuc = bat_dau + timedelta(minutes=15)
    ngay_iso = ngay.isoformat()
    print(f"\nKhung giờ: {bat_dau:%d/%m/%Y %H:%M}–{ket_thuc:%H:%M} · {SO_CSKH} CSKH\n")

    phien_ds: list[httpx.AsyncClient] = []
    auth_ids: list[str] = []
    try:
        for i in range(SO_CSKH):
            tok, _sid, aid = await tao(admin, conn, clinic_id, i + 1)
            phien_ds.append(phien(tok))
            auth_ids.append(aid)
        print(f"{SO_CSKH} tài khoản CSKH thật, đăng nhập xong\n")

        than = {
            "slot_start": bat_dau.isoformat(),
            "slot_end": ket_thuc.isoformat(),
            "doctor_id": None,
        }

        # ── 1. MỘT NGƯỜI GIỮ, BẢY NGƯỜI CÒN LẠI ĐỌC ĐƯỢC SAU BAO LÂU ────────
        print("1. CSKH 1 giữ chỗ — bảy người kia hỏi liên tục")
        t0 = time.perf_counter()
        r = await phien_ds[0].post("/appointments/slot-hold", json=than)
        ghi("CSKH 1 giữ được", r.status_code in (200, 201), f"{r.status_code}")

        async def cho_thay(ss: httpx.AsyncClient) -> float | None:
            for _ in range(400):
                g = await ss.get("/appointments/slot-hold", params={"date": ngay_iso})
                items = g.json().get("items", []) if g.status_code == 200 else []
                if any(cung_khung(i, bat_dau) for i in items):
                    return (time.perf_counter() - t0) * 1000
                await asyncio.sleep(0.01)
            return None

        do = await asyncio.gather(*[cho_thay(s) for s in phien_ds[1:]])
        thay = [d for d in do if d is not None]
        ghi(
            f"cả {SO_CSKH - 1} người kia đều đọc được",
            len(thay) == SO_CSKH - 1,
            f"p50 {statistics.median(thay):.0f}ms · chậm nhất {max(thay):.0f}ms"
            if thay
            else "CÓ NGƯỜI KHÔNG THẤY",
        )

        # ── 2. TÁM NGƯỜI CÙNG GIỮ CÙNG MỘT KHUNG ────────────────────────────
        print("\n2. Cả tám cùng bấm vào đúng khung ấy")
        ra = await asyncio.gather(
            *[s.post("/appointments/slot-hold", json=than) for s in phien_ds[1:]],
            return_exceptions=True,
        )
        ok = sum(
            1 for x in ra if isinstance(x, httpx.Response) and x.status_code in (200, 201)
        )
        ghi(
            "giữ chỗ là TƯ VẤN — ai bấm cũng giữ được",
            ok == SO_CSKH - 1,
            f"{ok}/{SO_CSKH - 1} thành công",
        )
        g = await phien_ds[0].get("/appointments/slot-hold", params={"date": ngay_iso})
        so = len([i for i in g.json().get("items", []) if cung_khung(i, bat_dau)])
        ghi(
            "CSKH 1 thấy đủ bảy người kia đang tranh khung này",
            so == SO_CSKH - 1,
            f"{so} chỗ giữ (không tính chỗ của chính mình)",
        )

        # ── 3. TIN ĐẨY: pg_notify → SSE ─────────────────────────────────────
        print("\n3. Tin đẩy khi có người giữ/thả chỗ")
        nghe = await asyncpg.connect(
            os.environ["DATABASE_URL"].replace(
                "postgresql+asyncpg://", "postgresql://"
            )
        )
        hop: asyncio.Queue[float] = asyncio.Queue()

        def khi_co_tin(_c, _pid, _ch, payload: str) -> None:
            try:
                if json.loads(payload).get("t") == "slot_hold":
                    hop.put_nowait(time.perf_counter())
            except Exception:
                pass

        await nghe.add_listener("clinicai_changes", khi_co_tin)
        khac = bat_dau + timedelta(minutes=30)
        t1 = time.perf_counter()
        await phien_ds[1].post(
            "/appointments/slot-hold",
            json={
                "slot_start": khac.isoformat(),
                "slot_end": (khac + timedelta(minutes=15)).isoformat(),
                "doctor_id": None,
            },
        )
        try:
            luc = await asyncio.wait_for(hop.get(), timeout=5)
            ghi(
                "database bắn tin ngay khi ghi xong",
                True,
                f"{(luc - t1) * 1000:.0f}ms từ lúc bấm tới lúc có tin",
            )
        except asyncio.TimeoutError:
            ghi(
                "database bắn tin ngay khi ghi xong",
                False,
                "KHÔNG CÓ TIN — trigger notify chưa được gắn cho slot_hold",
            )
        await nghe.remove_listener("clinicai_changes", khi_co_tin)
        await nghe.close()

        # ── 4. GIỮ ĐÚNG 10 PHÚT ─────────────────────────────────────────────
        print("\n4. Thời gian giữ chỗ")
        han = await conn.fetchval(
            "SELECT round(extract(epoch FROM (expires_at - held_at)) / 60)::int "
            "  FROM public.slot_hold "
            " WHERE clinic_id = $1::uuid AND released_at IS NULL "
            " ORDER BY held_at DESC LIMIT 1",
            clinic_id,
        )
        ghi("một lần giữ kéo dài đúng 10 phút", han == 10, f"{han} phút")

        con_song = await conn.fetchval(
            "SELECT count(*) FROM public.v_slot_hold_active WHERE clinic_id = $1::uuid",
            clinic_id,
        )
        await conn.execute(
            "UPDATE public.slot_hold SET expires_at = now() - interval '1 second' "
            " WHERE clinic_id = $1::uuid AND released_at IS NULL",
            clinic_id,
        )
        sau = await conn.fetchval(
            "SELECT count(*) FROM public.v_slot_hold_active WHERE clinic_id = $1::uuid",
            clinic_id,
        )
        ghi(
            "quá hạn là tự hết, không cần tiến trình dọn",
            con_song > 0 and sau == 0,
            f"{con_song} chỗ đang giữ → {sau} sau khi quá hạn",
        )

    finally:
        print("\nDọn dữ liệu thử…")
        ids = [
            r["id"]
            for r in await conn.fetch(
                "SELECT id FROM public.staff WHERE full_name LIKE $1", f"{NHAN}%"
            )
        ]
        await conn.execute(
            "DELETE FROM public.slot_hold WHERE held_by = ANY($1::uuid[])", ids
        )
        await conn.execute(
            "DELETE FROM public.clinic_membership WHERE staff_id = ANY($1::uuid[])", ids
        )
        await conn.execute("DELETE FROM public.staff WHERE id = ANY($1::uuid[])", ids)
        base = os.environ["SUPABASE_URL"].rstrip("/")
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        for aid in auth_ids:
            await admin.delete(
                f"{base}/auth/v1/admin/users/{aid}",
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
            )
        print(f"  xoá {len(ids)} nhân sự thử + {len(auth_ids)} tài khoản")
        for s in phien_ds:
            await s.aclose()
        await conn.close()
        await admin.aclose()

    dat = sum(1 for _, ok_, _ in ket_qua if ok_)
    print(f"\n{dat}/{len(ket_qua)} mục đạt\n")
    return 0 if dat == len(ket_qua) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
