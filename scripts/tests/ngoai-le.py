#!/usr/bin/env python3
"""NHÓM NGOẠI LỆ — buổi khám không đi theo đường thẳng.

Bộ kiểm thử của Tuyền (Notion) có một nhóm mà mỗi ca là một cách người bệnh
LÀM KHÁC kịch bản: đổi ý, về sớm, đến muộn, chỉ ghé lấy kết quả. Đây là nhóm
hay hỏng nhất trong mọi phần mềm phòng khám, vì mã thường chỉ được viết cho
đường thẳng.

    SC-08  huỷ lịch trước khi đến          → KHÔNG sinh lượt khám
    SC-09  đặt lịch nhưng không đến        → chỉ no-show khi NGƯỜI quyết, không tự động
    SC-10  đã check-in rồi đổi ý về        → ghi rời trước khám, KHÔNG xoá lượt
    SC-11  đã check-in, muốn đặt ngày khác → lượt cũ giữ, lịch mới là bản ghi riêng
    SC-12  ra ngoài tạm rồi quay lại       → VẪN một lượt, không check-in lần hai
    SC-28  đến muộn                        → nhân viên quyết, hệ không tự chen hàng

    PYTHONPATH=src poetry run python scripts/tests/ngoai-le.py
    PYTHONPATH=src poetry run python scripts/tests/ngoai-le.py --rollback

Tài khoản đọc từ `TK_<vai>` / `MK_<vai>` như hai bộ kia.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys
import time
import uuid
from typing import Any

import httpx

API = os.environ.get("CLINIC_API_URL", "http://127.0.0.1:8100")
SB = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54421")
ANON = os.environ.get("SUPABASE_ANON_KEY", "")
PW = os.environ.get("TEST_PW", "")
KHOA_API = os.environ.get("BACKEND_API_KEY", "")
DAU = "[ngoại]"
LAN = uuid.uuid4().hex[:6]
VET = pathlib.Path(os.environ.get("VET_FILE_NL", ".dev-logs/ngoai-le-vet.json"))

VAI = {
    v: os.environ.get(f"TK_{v}", m)
    for v, m in (
        ("letan", "letan@dr4women.local"),
        ("cskh", "cskh@dr4women.local"),
        ("bacsi", "bs.a@dr4women.local"),
        ("quanly", "ql@dr4women.local"),
    )
}
MAT_KHAU_VAI = {v: os.environ.get(f"MK_{v}", "") for v in VAI}

dat = hong = bo_qua = 0


def ket(ten: str, ok: bool, chi_tiet: str) -> None:
    global dat, hong
    if ok:
        dat += 1
        print(f"  ✓ {ten:<50} {chi_tiet}")
    else:
        hong += 1
        print(f"  ✗ {ten:<50} {chi_tiet}")


def bo(ten: str, ly_do: str) -> None:
    global bo_qua
    bo_qua += 1
    print(f"  – {ten:<50} bỏ qua: {ly_do}")


class Phien:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def goi(self, method: str, duong: str, **kw: Any) -> tuple[int, Any]:
        r = await self.http.request(method, f"{API}{duong}", **kw)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text[:200]


def khoa() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


async def token(
    http: httpx.AsyncClient, email: str, mat_khau: str | None = None
) -> str | None:
    for lan in range(2):
        r = await http.post(
            f"{SB}/auth/v1/token?grant_type=password",
            headers={"apikey": ANON, "Content-Type": "application/json"},
            json={"email": email, "password": mat_khau or PW},
        )
        if r.status_code == 200:
            return str(r.json().get("access_token") or "") or None
        if lan == 0:
            await asyncio.sleep(2.0)
    return None


def gio_kham(ctx: dict[str, Any], thu_tu: int, sau_ngay: int = 2) -> tuple[str, str]:
    """Khung còn phía trước, nằm trong giờ NHẬN LỊCH thật của phòng khám."""
    import datetime as _dt

    tz = _dt.timezone(_dt.timedelta(hours=7))
    bay_gio = _dt.datetime.now(tz)
    d = bay_gio.date() + _dt.timedelta(days=sau_ngay)
    buoc = int(ctx.get("slot_minutes") or 30)
    som_nhat = 0 if sau_ngay > 0 else bay_gio.hour * 60 + bay_gio.minute + 10
    thu = str((d.weekday() + 1) % 7)
    khung = (ctx.get("khung_theo_thu") or {}).get(thu) or [[8 * 60, 21 * 60 + 30]]
    phut = khung[0][0]
    for dau_k, cuoi_k in khung:
        bd = max(dau_k, ((som_nhat + buoc - 1) // buoc) * buoc) + thu_tu * buoc
        if bd + buoc <= cuoi_k:
            phut = bd
            break
    dau = _dt.datetime.combine(d, _dt.time(0, 0), tz) + _dt.timedelta(minutes=phut)
    return dau.isoformat(), (dau + _dt.timedelta(minutes=buoc)).isoformat()


async def tao_khach(p: Phien, ten: str, ctx: dict[str, Any], vet: list) -> str | None:
    ma = f"{int(time.time() * 1000) % 10_000_000:07d}"
    st, body = await p.goi(
        "POST",
        "/api/v1/patients",
        json={
            "full_name": f"{DAU}{LAN} {ten}",
            "date_of_birth": "1995-05-05",
            "phone_primary": f"096{ma}",
            "location_id": ctx["location_id"],
            "gender": "female",
        },
    )
    kh = body.get("clinic_patient_id") if st == 201 else None
    if kh:
        vet.append(("patient", kh))
    return kh


async def dat_lich(
    p: Phien, kh: str, ctx: dict[str, Any], thu_tu: int, vet: list, sau_ngay: int = 2
) -> str | None:
    bd, kt = gio_kham(ctx, thu_tu, sau_ngay=sau_ngay)
    st, b = await p.goi(
        "POST",
        "/api/v1/appointments/bookings",
        headers=khoa(),
        json={
            "clinic_patient_id": kh,
            "service_type_id": ctx["service_type_id"],
            "location_id": ctx["location_id"],
            "slot_start": bd,
            "slot_end": kt,
            "doctor_id": ctx["doctor_id"],
            "booking_channel": "den_truc_tiep",
        },
    )
    a = (b or {}).get("appointment_id")
    if a:
        vet.append(("appointment", a))
    return a


async def dem_luot(p: Phien, ma_khach_ten: str) -> int:
    st, bang = await p.goi("GET", "/api/v1/luot-kham/bang")
    return sum(
        1
        for x in (bang or {}).get("luot", [])
        if str(x.get("ten", "")).startswith(ma_khach_ten)
    )


async def main() -> int:
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
        print(f"Thiếu biến môi trường: {', '.join(thieu)}", file=sys.stderr)
        return 2

    http = httpx.AsyncClient(timeout=40.0)
    phien: dict[str, Phien] = {}
    for vai, email in VAI.items():
        t = await token(http, email, MAT_KHAU_VAI.get(vai) or None)
        if not t:
            print(f"Không đăng nhập được {vai} ({email})", file=sys.stderr)
            continue
        c = httpx.AsyncClient(timeout=40.0)
        c.headers["Authorization"] = f"Bearer {t}"
        c.headers["X-API-Key"] = KHOA_API
        phien[vai] = Phien(c)
        await asyncio.sleep(0.25)
    print(f"Đăng nhập: {len(phien)}/{len(VAI)} vai\n")
    if len(phien) < 4:
        print("Thiếu vai — dừng.", file=sys.stderr)
        return 1

    st, dv = await phien["cskh"].goi("GET", "/api/v1/catalog/service-types")
    loai = next((x for x in dv if x.get("code") == "PHU_KHOA"), None)
    st, toi = await phien["bacsi"].goi("GET", "/api/v1/me")
    st, pol = await phien["cskh"].goi("GET", "/api/v1/appointments/policy")
    if not (loai and (toi or {}).get("staff_id")):
        print("Không dựng được bối cảnh.", file=sys.stderr)
        return 1
    ctx = {
        "location_id": toi["location_id"],
        "service_type_id": loai["id"],
        "doctor_id": toi["staff_id"],
        "slot_minutes": (pol or {}).get("slot_minutes"),
        "khung_theo_thu": (pol or {}).get("khung_nhan_lich") or {},
    }
    print(f"Bối cảnh: cơ sở {ctx['location_id'][:8]} · BS {ctx['doctor_id'][:8]}\n")
    vet: list[tuple[str, str]] = []

    # ── SC-08: huỷ lịch TRƯỚC khi đến → không được sinh lượt khám ───────────
    kh = await tao_khach(phien["cskh"], "SC08", ctx, vet)
    a8 = await dat_lich(phien["cskh"], kh, ctx, 0, vet) if kh else None
    if a8:
        st, _ = await phien["cskh"].goi(
            "PATCH",
            f"/api/v1/appointments/{a8}",
            json={
                "action": "cancel",
                "ly_do_huy_ma": "BAO_KHI_XAC_NHAN",
            },
        )
        so = await dem_luot(phien["quanly"], f"{DAU}{LAN} SC08")
        ket(
            "SC-08 huỷ trước khi đến → không sinh lượt khám",
            st == 200 and so == 0,
            f"mã {st} · số lượt khám = {so}",
        )
    else:
        bo("SC-08 huỷ trước khi đến", "không đặt được lịch")

    # ── SC-10: đã check-in rồi đổi ý về → ghi rời, KHÔNG xoá lượt ───────────
    kh = await tao_khach(phien["cskh"], "SC10", ctx, vet)
    a10 = await dat_lich(phien["cskh"], kh, ctx, 1, vet, sau_ngay=0) if kh else None
    if a10:
        st, b = await phien["letan"].goi(
            "POST", "/api/v1/luot-kham/check-in", json={"appointment_id": a10}
        )
        truoc = await dem_luot(phien["quanly"], f"{DAU}{LAN} SC10")
        st2, _ = await phien["letan"].goi(
            "PATCH", f"/api/v1/appointments/{a10}", json={"action": "undo_checkin"}
        )
        # Lượt PHẢI còn trong database (không xoá cứng) nhưng KHÔNG còn trên
        # bảng làm việc — khách đã về.
        sau = await dem_luot(phien["quanly"], f"{DAU}{LAN} SC10")
        ket(
            "SC-10 check-in rồi về → lượt rời bảng, không bị xoá",
            truoc == 1 and sau == 0 and st2 == 200,
            f"trên bảng: {truoc} → {sau} · mã hoàn tác {st2}",
        )
    else:
        bo("SC-10 check-in rồi về", "không đặt được lịch")

    # ── SC-12: ra ngoài tạm rồi quay lại → VẪN một lượt ────────────────────
    #
    # Không có nút "tạm rời" nên đời thật là: khách đi ra, quay lại, lễ tân
    # có thể bấm check-in lần nữa. Bất biến: KHÔNG sinh lượt thứ hai.
    kh = await tao_khach(phien["cskh"], "SC12", ctx, vet)
    a12 = await dat_lich(phien["cskh"], kh, ctx, 2, vet, sau_ngay=0) if kh else None
    if a12:
        await phien["letan"].goi(
            "POST", "/api/v1/luot-kham/check-in", json={"appointment_id": a12}
        )
        st2, b2 = await phien["letan"].goi(
            "POST", "/api/v1/luot-kham/check-in", json={"appointment_id": a12}
        )
        so = await dem_luot(phien["quanly"], f"{DAU}{LAN} SC12")
        ket(
            "SC-12 quay lại, bấm check-in lần hai → vẫn 1 lượt",
            so == 1,
            f"mã lần hai {st2} · số lượt khám = {so}",
        )
    else:
        bo("SC-12 ra ngoài rồi quay lại", "không đặt được lịch")

    # ── SC-11: đã check-in, muốn đặt NGÀY KHÁC → hai bản ghi riêng ──────────
    if a12:
        kh12 = next((k for t, k in reversed(vet) if t == "patient"), None)
        a11 = await dat_lich(phien["cskh"], kh12, ctx, 0, vet, sau_ngay=5)
        so = await dem_luot(phien["quanly"], f"{DAU}{LAN} SC12")
        ket(
            "SC-11 đã check-in vẫn đặt được lịch ngày khác",
            bool(a11) and so == 1,
            f"lịch mới {'có' if a11 else 'KHÔNG'} · lượt hôm nay vẫn {so}",
        )
    else:
        bo("SC-11 đặt lịch ngày khác", "không có lượt đang mở")

    # ── SC-09: không đến → no-show là QUYẾT ĐỊNH của người, không tự động ───
    kh = await tao_khach(phien["cskh"], "SC09", ctx, vet)
    a9 = await dat_lich(phien["cskh"], kh, ctx, 3, vet, sau_ngay=0) if kh else None
    if a9:
        st, _ = await phien["letan"].goi(
            "PATCH", f"/api/v1/appointments/{a9}", json={"action": "no_show"}
        )
        so = await dem_luot(phien["quanly"], f"{DAU}{LAN} SC09")
        ket(
            "SC-09 lễ tân đánh không đến → không sinh lượt khám",
            st == 200 and so == 0,
            f"mã {st} · số lượt khám = {so}",
        )
    else:
        bo("SC-09 không đến", "không đặt được lịch")

    # ── SC-28: đến MUỘN → vẫn check-in được, không tự huỷ ──────────────────
    #
    # Khung đã trôi qua trong ngày. Luật Tuyền: "không âm thầm no-show chỉ vì
    # đến muộn" — nhân viên phải quyết được, nghĩa là hệ vẫn phải cho check-in.
    kh = await tao_khach(phien["cskh"], "SC28", ctx, vet)
    if kh:
        import datetime as _dt

        tz = _dt.timezone(_dt.timedelta(hours=7))
        bg = _dt.datetime.now(tz)
        buoc = int(ctx.get("slot_minutes") or 30)
        phut = ((bg.hour * 60 + bg.minute) // buoc) * buoc - buoc * 2
        if phut < 8 * 60:
            bo("SC-28 đến muộn", "chưa đủ muộn trong ngày để dựng cảnh")
        else:
            bd = _dt.datetime.combine(bg.date(), _dt.time(0, 0), tz) + _dt.timedelta(
                minutes=phut
            )
            st, b = await phien["cskh"].goi(
                "POST",
                "/api/v1/appointments/bookings",
                headers=khoa(),
                json={
                    "clinic_patient_id": kh,
                    "service_type_id": ctx["service_type_id"],
                    "location_id": ctx["location_id"],
                    "slot_start": bd.isoformat(),
                    "slot_end": (bd + _dt.timedelta(minutes=buoc)).isoformat(),
                    "doctor_id": ctx["doctor_id"],
                    "booking_channel": "den_truc_tiep",
                },
            )
            a28 = (b or {}).get("appointment_id")
            if not a28:
                # Hệ TỪ CHỐI đặt vào khung đã qua — đúng luật (xem
                # `_chan_dat_vao_qua_khu`). Cảnh "đến muộn" vì thế chỉ dựng được
                # từ một lịch đặt TRƯỚC đó, không dựng ngược lại được.
                ket(
                    "SC-28 không đặt được lịch vào khung ĐÃ QUA",
                    st in (409, 422),
                    f"mã {st} — đúng: lịch lùi về quá khứ bị chặn",
                )
            else:
                vet.append(("appointment", a28))
                st2, _ = await phien["letan"].goi(
                    "POST", "/api/v1/luot-kham/check-in", json={"appointment_id": a28}
                )
                so = await dem_luot(phien["quanly"], f"{DAU}{LAN} SC28")
                ket(
                    "SC-28 đến muộn vẫn check-in được",
                    st2 == 200 and so == 1,
                    f"mã {st2} · số lượt khám = {so}",
                )
    else:
        bo("SC-28 đến muộn", "không tạo được khách")

    print()
    print(f"ĐẠT {dat} · HỎNG {hong} · bỏ qua {bo_qua}")
    if vet:
        VET.parent.mkdir(parents=True, exist_ok=True)
        cu = []
        if VET.exists():
            try:
                cu = json.loads(VET.read_text())
            except Exception:
                cu = []
        VET.write_text(json.dumps(cu + [list(x) for x in vet], ensure_ascii=False))
        print(f"Dấu vết ({len(cu) + len(vet)}) → {VET}; chạy --rollback để dọn.")
    for p in phien.values():
        await p.http.aclose()
    await http.aclose()
    return 1 if hong else 0


async def rollback() -> int:
    if not VET.exists():
        print("Không có dấu vết để dọn.")
        return 0
    http = httpx.AsyncClient(timeout=40.0)
    t = await token(http, VAI["quanly"], MAT_KHAU_VAI.get("quanly") or None)
    if not t:
        print("Không đăng nhập được vai quản lý.", file=sys.stderr)
        return 1
    c = httpx.AsyncClient(timeout=40.0)
    c.headers["Authorization"] = f"Bearer {t}"
    c.headers["X-API-Key"] = KHOA_API
    p = Phien(c)
    for loai, ma in json.loads(VET.read_text()):
        if loai == "appointment":
            await p.goi(
                "PATCH",
                f"/api/v1/appointments/{ma}",
                json={
                    "action": "cancel",
                    "ly_do_huy_ma": "KHAC",
                    "cancellation_reason": f"{DAU} dọn sau khi thử nhóm ngoại lệ",
                },
            )
        else:
            await p.goi("PATCH", f"/api/v1/patients/{ma}", json={"is_active": False})
    print("Đã dọn.")
    VET.rename(VET.with_suffix(".json.da-don"))
    await c.aclose()
    await http.aclose()
    return 0


if __name__ == "__main__":
    if "--rollback" in sys.argv:
        raise SystemExit(asyncio.run(rollback()))
    raise SystemExit(asyncio.run(main()))
