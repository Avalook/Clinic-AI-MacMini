#!/usr/bin/env python3
"""NHÓM ĐUA TRANH — hai người bấm cùng một lúc thì chuyện gì xảy ra.

Bộ kiểm thử của Tuyền (Notion, "Các trường hợp kiểm thử") có một nhóm mà **không
ai bấm tay thử được**: hai người phải bấm cách nhau vài mili-giây thì lỗi mới lộ
ra. Đây chính là nhóm đắt nhất khi nó xảy ra trên bản thật — hai lịch hẹn cho
một chỗ cuối, hai lượt khám cho một lần đến, một đơn thuốc cấp hai lần.

    SC-31  hai CSKH cùng đặt chỗ cuối        → đúng MỘT người thành công
    SC-32  hai lễ tân cùng check-in một lịch → đúng MỘT lượt khám
    SC-33  bác sĩ + thư ký cùng sửa hồ sơ    → người sau nhận 409, không ghi đè
    SC-34  hai người cùng bắt đầu một dịch vụ→ đúng MỘT người nhận việc
    SC-35  thu ngân bấm thanh toán hai lần   → đúng MỘT khoản thu
    SC-36  kho bấm cấp thuốc hai lần         → trừ tồn đúng MỘT lần

CHẠY ĐƯỢC Ở CẢ HAI NƠI. Tài khoản đọc từ `TK_<vai>` như `buoi-kham-that.py`.

    PYTHONPATH=src poetry run python scripts/tests/dua-tranh.py
    PYTHONPATH=src poetry run python scripts/tests/dua-tranh.py --rollback

CÁCH ĐỌC KẾT QUẢ: mỗi kịch bản in ra MÃ TRẢ VỀ CỦA CẢ HAI lời gọi. "1 thành công
/ 1 bị chặn" là ĐẠT. "2 thành công" là hỏng — và hỏng im lặng, vì cả hai người
đều thấy màn hình báo xong.
"""

from __future__ import annotations

import asyncio
import os
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
DAU = "[đua]"
#: Mỗi lần chạy một dấu riêng. Không có nó thì lần chạy sau đếm cả khách của
#: lần trước và báo "2 lượt khám" cho một phép thử vốn đúng — tôi đã tự vấp.
LAN = uuid.uuid4().hex[:6]

VAI = {
    v: os.environ.get(f"TK_{v}", m)
    for v, m in (
        ("letan", "letan@dr4women.local"),
        ("letan2", "letan@dr4women.local"),
        ("cskh", "cskh@dr4women.local"),
        ("cskh2", "cskh@dr4women.local"),
        ("bacsi", "bs.a@dr4women.local"),
        ("thuky", "thuky@dr4women.local"),
        ("bacsi_sa", "bs.sa@dr4women.local"),
        ("dieuduong", "dd.sa@dr4women.local"),
        ("truongca", "truongca@dr4women.local"),
        ("quanly", "ql@dr4women.local"),
        ("thungan", "thungan@dr4women.local"),
        ("duocsi", "duocsi@dr4women.local"),
    )
}

#: Mật khẩu riêng từng vai. Trên máy chủ thật, người thật dùng một mật khẩu còn
#: vài tài khoản thử cũ (thu ngân, dược sĩ) vẫn giữ mật khẩu cũ — thiếu chỗ này
#: thì hai kịch bản cuối im lặng bị bỏ qua và nhìn như "hệ chưa có tính năng".
MAT_KHAU_VAI = {v: os.environ.get(f"MK_{v}", "") for v in VAI}

dat = hong = 0
bo_qua = 0


def ket(ten: str, ok: bool, chi_tiet: str) -> None:
    global dat, hong
    if ok:
        dat += 1
        print(f"  ✓ {ten:<52} {chi_tiet}")
    else:
        hong += 1
        print(f"  ✗ {ten:<52} {chi_tiet}")


def bo(ten: str, ly_do: str) -> None:
    global bo_qua
    bo_qua += 1
    print(f"  – {ten:<52} bỏ qua: {ly_do}")


async def token(
    http: httpx.AsyncClient, email: str, mat_khau: str | None = None
) -> str | None:
    """Lấy token, có nhịp nghỉ và một lần thử lại.

    GoTrue giới hạn số lần đăng nhập trong một khoảng ngắn. Script này mở
    MƯỜI HAI phiên liền nhau, và cái thứ mười hai ăn 429 — rồi phép thử dừng
    với "thiếu vai cốt lõi", nghe như hệ thống hỏng. Nghỉ một nhịp rồi thử lại
    là đủ; đây là giới hạn của máy chủ đăng nhập, không phải lỗi của hệ.
    """
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
    """Mỗi lời gọi một khoá chống-gửi-trùng RIÊNG.

    Dùng CHUNG một khoá thì lời gọi thứ hai là "gửi lại", và hệ thống trả lại
    kết quả cũ — đúng, nhưng đó là phép thử KHÁC. Ở đây phải giả lập hai NGƯỜI
    bấm cùng lúc, tức hai thao tác độc lập cùng nhắm một chỗ.
    """
    return {"Idempotency-Key": str(uuid.uuid4())}


def gio_kham(ctx: dict[str, Any], thu_tu: int, sau_ngay: int = 2) -> tuple[str, str]:
    """Một khung CÒN Ở PHÍA TRƯỚC, nằm trong giờ NHẬN LỊCH của phòng khám.

    Không tự bịa "bây giờ + 20 phút": chạy lúc 13:10 thì khung rơi vào giờ nghỉ
    trưa và server từ chối ĐÚNG — một phép thử đỏ vì phép thử sai. Khung giờ đọc
    từ `/appointments/policy`, cùng nguồn mà lưới chọn giờ trên màn đọc.
    """
    import datetime as _dt

    tz = _dt.timezone(_dt.timedelta(hours=7))
    bay_gio = _dt.datetime.now(tz)
    # NGÀY KHÁC HẲN NGÀY HÔM NAY, mặc định +2.
    #
    # Khung của hôm nay đã bị các lượt chạy thử trước lấp đầy, và phép thử đua
    # tranh cần một khung TRỐNG để tự dựng ra tình huống "còn đúng một chỗ".
    # Chạy trên khung đã đầy thì cả hai người đều bị chặn — hệ thống đúng,
    # nhưng phép thử không chứng minh được điều nó định chứng minh.
    d = bay_gio.date() + _dt.timedelta(days=sau_ngay)
    buoc = int(ctx.get("slot_minutes") or 30)
    som_nhat = 0 if sau_ngay > 0 else bay_gio.hour * 60 + bay_gio.minute + 10
    _thu_moi = str((d.weekday() + 1) % 7)
    khung = (
        (ctx.get("khung_theo_thu") or {}).get(_thu_moi)
        or ctx.get("khung_nhan_lich")
        or [[8 * 60, 21 * 60 + 30]]
    )
    phut = None
    for dau_k, cuoi_k in khung:
        bd = max(dau_k, ((som_nhat + buoc - 1) // buoc) * buoc) + thu_tu * buoc
        if bd + buoc <= cuoi_k:
            phut = bd
            break
    if phut is None:
        d = d + _dt.timedelta(days=1)
        phut = khung[0][0] + thu_tu * buoc
    dau = _dt.datetime.combine(d, _dt.time(0, 0), tz) + _dt.timedelta(minutes=phut)
    return dau.isoformat(), (dau + _dt.timedelta(minutes=buoc)).isoformat()


async def tao_khach(p: Phien, ten: str, ctx: dict[str, Any]) -> str | None:
    ma = f"{int(time.time() * 1000) % 10_000_000:07d}"
    st, body = await p.goi(
        "POST",
        "/api/v1/patients",
        json={
            "full_name": f"{DAU}{LAN} {ten}",
            "date_of_birth": "1995-05-05",
            "phone_primary": f"097{ma}",
            "location_id": ctx["location_id"],
            "gender": "female",
        },
    )
    return body.get("clinic_patient_id") if st == 201 else None


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
        await asyncio.sleep(0.25)  # nhường nhịp cho máy chủ đăng nhập
    print(f"Đăng nhập: {len(phien)}/{len(VAI)} vai\n")
    if "cskh" not in phien or "letan" not in phien:
        print("Thiếu vai cốt lõi — dừng.", file=sys.stderr)
        return 1

    # ── Bối cảnh ────────────────────────────────────────────────────────────
    # CƠ SỞ LẤY TỪ CHÍNH BÁC SĨ, không phải "cơ sở active đầu tiên".
    #
    # Phòng khám có ba cơ sở; lấy cái đầu danh sách thì rơi vào nơi bác sĩ ấy
    # không làm việc, và mọi lịch hẹn bị từ chối — một phép thử đỏ vì phép thử
    # sai, không vì hệ thống sai. `/api/v1/me` biết người ấy thuộc cơ sở nào.
    st, dv = await phien["cskh"].goi("GET", "/api/v1/catalog/service-types")
    loai = next((x for x in dv if x.get("code") == "PHU_KHOA"), None)
    bac_si = noi = None
    if "bacsi" in phien:
        st, toi = await phien["bacsi"].goi("GET", "/api/v1/me")
        bac_si = (toi or {}).get("staff_id")
        noi = (toi or {}).get("location_id")
    if not (noi and loai and bac_si):
        print("Không dựng được bối cảnh (cơ sở / loại khám / bác sĩ).", file=sys.stderr)
        return 1
    import datetime as _dt

    _thu = str((_dt.date.today().weekday() + 1) % 7)
    st, pol = await phien["cskh"].goi("GET", "/api/v1/appointments/policy")
    ctx = {
        "location_id": noi,
        "service_type_id": loai["id"],
        "doctor_id": bac_si,
        "slot_minutes": (pol or {}).get("slot_minutes"),
        "khung_nhan_lich": ((pol or {}).get("khung_nhan_lich") or {}).get(_thu),
        "khung_theo_thu": (pol or {}).get("khung_nhan_lich") or {},
    }
    print(f"Bối cảnh: cơ sở {noi[:8]} · BS {bac_si[:8]}\n")

    da_tao: list[tuple[str, str]] = []

    # ── SC-32: hai lễ tân cùng check-in MỘT lịch hẹn ────────────────────────
    kh = await tao_khach(phien["cskh"], "SC32", ctx)
    bd, kt = gio_kham(ctx, 0)
    st, body = await phien["cskh"].goi(
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
    appt = (body or {}).get("appointment_id") or (
        ((body or {}).get("appointment") or {}).get("id")
    )
    if not appt:
        print(f"    (đặt lịch hỏng: {st} {str(body)[:140]})")
    if kh:
        da_tao.append(("patient", kh))
    if appt:
        da_tao.append(("appointment", appt))
        lt2 = phien.get("letan2") or phien["letan"]
        r1, r2 = await asyncio.gather(
            phien["letan"].goi(
                "POST", "/api/v1/luot-kham/check-in", json={"appointment_id": appt}
            ),
            lt2.goi(
                "POST", "/api/v1/luot-kham/check-in", json={"appointment_id": appt}
            ),
        )
        st, bang = await phien["letan"].goi("GET", "/api/v1/luot-kham/bang")
        so_luot = sum(
            1
            for x in (bang or {}).get("luot", [])
            if str(x.get("ten", "")).startswith(f"{DAU}{LAN} SC32")
        )
        ket(
            "SC-32 hai lễ tân cùng check-in → đúng 1 lượt khám",
            so_luot == 1,
            f"mã {r1[0]}/{r2[0]} · số lượt khám = {so_luot}",
        )
    else:
        bo("SC-32 hai lễ tân cùng check-in", "không đặt được lịch")

    # ── SC-31: nhiều CSKH cùng lao vào MỘT khung giờ ───────────────────────
    #
    # Bản đầu của phép thử cố dựng cảnh "còn đúng một chỗ" rồi thả hai người
    # vào. Nó mong manh: sức chứa đọc được và sức chứa mà trigger dùng đếm theo
    # hai khung phút khác nhau, nên "còn 2 chỗ" hoá ra còn nhiều hơn thế và cả
    # hai đều đặt được — phép thử đỏ mà hệ thống không sai.
    #
    # Phép thử đúng mạnh hơn và không cần biết trần là bao nhiêu: bắn TÁM lịch
    # cùng một lúc vào một khung TRỐNG, rồi đếm lại xem khung ấy giữ bao nhiêu
    # lịch còn sống. Bất biến phải đúng dù trần là 2, 6 hay 20:
    #
    #     số lịch được nhận  ==  số lời gọi trả 201   (không ai bị mất lịch)
    #     số lịch được nhận  <=  trần của khung       (không ai chen lọt)
    so_lao_vao = 8
    # Khung RIÊNG cho mỗi lần chạy: lần trước đã lấp đầy khung của nó, và dùng
    # lại đúng khung ấy thì phép thử đo lại dữ liệu cũ chứ không đo cuộc đua.
    bd2, kt2 = gio_kham(ctx, 1 + int(LAN[:2], 16) % 6, sau_ngay=3)
    khach: list[str] = []
    for i_k in range(so_lao_vao):
        k = await tao_khach(phien["cskh"], f"SC31-{i_k}", ctx)
        if k:
            khach.append(k)
            da_tao.append(("patient", k))
    than = {
        "service_type_id": ctx["service_type_id"],
        "location_id": ctx["location_id"],
        "slot_start": bd2,
        "slot_end": kt2,
        "doctor_id": ctx["doctor_id"],
        "booking_channel": "online",
    }
    cs2 = phien.get("cskh2") or phien["cskh"]
    ket_qua = await asyncio.gather(
        *(
            (phien["cskh"] if n % 2 == 0 else cs2).goi(
                "POST",
                "/api/v1/appointments/bookings",
                headers=khoa(),
                json={**than, "clinic_patient_id": k},
            )
            for n, k in enumerate(khach)
        )
    )
    nhan = 0
    for st_i, b_i in ket_qua:
        a = (b_i or {}).get("appointment_id")
        if st_i == 201 and a:
            nhan += 1
            da_tao.append(("appointment", a))
    # Đếm lại từ database qua chính màn đặt lịch: tin con số của hệ thống,
    # không tin con số mình vừa cộng.
    st, luoi = await phien["cskh"].goi(
        "GET",
        "/api/v1/appointments/quote"
        f"?date={bd2[:10]}&doctor_id={ctx['doctor_id']}"
        f"&location_id={ctx['location_id']}",
    )
    phut_bd = int(bd2[11:13]) * 60 + int(bd2[14:16])
    o = None
    for sl in (luoi or {}).get("slots", []):
        m = int(sl.get("minute_of_day", -1))
        if m <= phut_bd < m + int(sl.get("slot_minutes") or 15):
            o = sl
            break
    thuc_te = int((o or {}).get("regular_used", -1))
    tran = int((o or {}).get("regular_cap", -1))
    # TRẦN CHỈ CHẶN KHI TUẦN ĐÃ CÔNG BỐ LỊCH TRỰC (Tuyền chốt 15/09/2026,
    # migration 20260915000001). Tuần chưa công bố thì nhận thoải mái — nên
    # phép thử phải hỏi xem tuần ấy đã công bố chưa rồi mới biết trông đợi gì.
    # Bản đầu của tôi bỏ qua điều này và kết luận "hệ thống cho chen lọt", trong
    # khi hệ thống đang làm ĐÚNG luật.
    da_cong_bo = bool((luoi or {}).get("roster_week_published"))
    if da_cong_bo:
        ok = nhan == thuc_te and 0 <= thuc_te <= tran
        mo_ta = f"tuần ĐÃ công bố → trần {tran} phải chặn"
    else:
        # Không có trần thì bất biến còn lại vẫn phải đúng: không lịch nào rơi
        # mất giữa đường, và database đếm đúng bằng số lời gọi được nhận.
        ok = nhan == thuc_te and nhan == len(khach)
        mo_ta = "tuần CHƯA công bố lịch trực → không có trần, đúng luật"
    ket(
        f"SC-31 {so_lao_vao} lịch cùng lúc vào một khung",
        ok,
        f"{nhan} nhận · database đếm {thuc_te} · trần {tran} · {mo_ta}",
    )

    # ── SC-33: bác sĩ + thư ký cùng sửa hồ sơ, cùng một mốc bản ghi ─────────
    if appt and kh and "bacsi" in phien:
        st, b0 = await phien["bacsi"].goi(
            "POST",
            "/api/v1/clinical-records",
            json={
                "appointment_id": appt,
                "clinic_patient_id": kh,
                # Bản ghi MỚI vẫn phải khai mốc, và mốc của nó là 0. Thiếu là
                # 409 "thiếu phiên bản đang sửa" — hệ thống không cho ai ghi mù.
                "expected_revision": 0,
                "subjective": {"ly_do": "lần ghi đầu"},
            },
        )
        rev = (b0 or {}).get("revision")
        if rev is None:
            print(f"    (ghi hồ sơ lần đầu: {st} {str(b0)[:140]})")
        if rev is None:
            bo("SC-33 hai người cùng sửa hồ sơ", "không đọc được số bản ghi")
        else:
            tk = phien.get("thuky") or phien["bacsi"]
            r1, r2 = await asyncio.gather(
                phien["bacsi"].goi(
                    "POST",
                    "/api/v1/clinical-records",
                    json={
                        "appointment_id": appt,
                        "clinic_patient_id": kh,
                        "expected_revision": rev,
                        "subjective": {"ly_do": "bác sĩ ghi"},
                    },
                ),
                tk.goi(
                    "POST",
                    "/api/v1/clinical-records",
                    json={
                        "appointment_id": appt,
                        "clinic_patient_id": kh,
                        "expected_revision": rev,
                        "subjective": {"ly_do": "thư ký ghi"},
                    },
                ),
            )
            ma = sorted([r1[0], r2[0]])
            ket(
                "SC-33 bác sĩ + thư ký cùng sửa → người sau nhận 409",
                ma.count(200) == 1 and 409 in ma,
                f"mã {r1[0]}/{r2[0]}",
            )
    else:
        bo("SC-33 hai người cùng sửa hồ sơ", "thiếu lượt khám hoặc vai bác sĩ")

    # ── Dựng một lượt khám đi tới tận chỉ định, cho SC-34 ──────────────────
    #
    # Ba kịch bản còn lại cần bối cảnh sâu hơn hẳn: một lượt khám đã có chỉ định
    # được xếp phòng (SC-34), một lịch hẹn đã hoàn tất để thu tiền (SC-35), và
    # một dòng đơn thuốc có tồn kho để cấp (SC-36). Dựng một lần, dùng cho cả ba.
    order_id = visit2 = appt2 = None
    kh2 = await tao_khach(phien["cskh"], "SC34", ctx)
    if kh2:
        da_tao.append(("patient", kh2))
        bd3, kt3 = gio_kham(ctx, 2, sau_ngay=0)
        st, b = await phien["cskh"].goi(
            "POST",
            "/api/v1/appointments/bookings",
            headers=khoa(),
            json={
                "clinic_patient_id": kh2,
                "service_type_id": ctx["service_type_id"],
                "location_id": ctx["location_id"],
                "slot_start": bd3,
                "slot_end": kt3,
                "doctor_id": ctx["doctor_id"],
                "booking_channel": "den_truc_tiep",
            },
        )
        appt2 = (b or {}).get("appointment_id")
        if appt2:
            da_tao.append(("appointment", appt2))
            await phien["letan"].goi(
                "POST", "/api/v1/luot-kham/check-in", json={"appointment_id": appt2}
            )
            st, bang = await phien["bacsi"].goi("GET", "/api/v1/luot-kham/bang")
            luot = next(
                (
                    x
                    for x in (bang or {}).get("luot", [])
                    if str(x.get("ten", "")).startswith(f"{DAU}{LAN} SC34")
                ),
                None,
            )
            if luot:
                visit2 = luot["visit_id"]
                # Lần lưu đầu phải sau [Bắt đầu] (chốt 23/09/2026).
                await phien["dieuduong"].goi(
                    "POST", f"/api/v1/luot-kham/visits/{visit2}/vitals/start"
                ) if "dieuduong" in phien else None
                await phien["dieuduong"].goi(
                    "POST",
                    f"/api/v1/luot-kham/visits/{visit2}/vitals",
                    headers=khoa(),
                    json={"systolic": 118, "diastolic": 76},
                ) if "dieuduong" in phien else None
                st, bang = await phien["bacsi"].goi("GET", "/api/v1/luot-kham/bang")
                luot = next(
                    (
                        x
                        for x in (bang or {}).get("luot", [])
                        if x.get("visit_id") == visit2
                    ),
                    None,
                )
                ph = ((luot or {}).get("phien") or [None])[0]
                dvu = next(
                    (
                        d
                        for d in (bang or {}).get("dich_vu", [])
                        if "ULTRASOUND_DOCTOR" in (d.get("vai_lam") or [])
                    ),
                    None,
                )
                phong = next(
                    (
                        r
                        for r in (bang or {}).get("phong", [])
                        if dvu and (dvu.get("node") in (r.get("nodes") or []))
                    ),
                    None,
                )
                if ph and dvu and phong:
                    cons = ph["id"]
                    await phien["bacsi"].goi(
                        "POST", f"/api/v1/luot-kham/consultations/{cons}/start"
                    )
                    st, b = await phien["bacsi"].goi(
                        "POST",
                        f"/api/v1/luot-kham/consultations/{cons}/authorize-orders",
                        headers=khoa(),
                        json={"service_codes": [dvu["ma"]]},
                    )
                    ids = (b or {}).get("order_ids") or []
                    if ids:
                        order_id = ids[0]
                        await phien["bacsi"].goi(
                            "POST",
                            f"/api/v1/luot-kham/consultations/{cons}/complete",
                            headers=khoa(),
                            json={
                                "outcome": "SERVICES",
                                "requirements": [
                                    {"order_id": order_id, "need": "PERFORMED"}
                                ],
                            },
                        )
                        tc = phien.get("truongca") or phien["quanly"]
                        await tc.goi(
                            "POST",
                            f"/api/v1/luot-kham/orders/{order_id}/dispatch",
                            headers=khoa(),
                            json={"room_id": phong["id"]},
                        )

    # ── SC-34: hai người cùng NHẬN một dịch vụ ──────────────────────────────
    if order_id and "bacsi_sa" in phien:
        nguoi2 = phien.get("dieuduong") or phien["bacsi_sa"]
        r1, r2 = await asyncio.gather(
            phien["bacsi_sa"].goi("POST", f"/api/v1/luot-kham/orders/{order_id}/start"),
            nguoi2.goi("POST", f"/api/v1/luot-kham/orders/{order_id}/start"),
        )
        ma = sorted([r1[0], r2[0]])
        ket(
            "SC-34 hai người cùng nhận một dịch vụ → đúng 1 người",
            ma.count(200) == 1,
            f"mã {r1[0]}/{r2[0]}",
        )
    else:
        bo("SC-34 hai người cùng nhận một dịch vụ", "không dựng được chỉ định")

    # ── SC-35: thu ngân bấm thanh toán HAI LẦN ──────────────────────────────
    #
    # Hai lần bấm là HAI thao tác độc lập (khoá chống-gửi-trùng khác nhau), chứ
    # không phải một lần gửi lại. Bất biến: dù cả hai cùng trả 200, lượt khám
    # chỉ được mang ĐÚNG MỘT khoản thu loại ấy.
    if visit2 and appt2 and "thungan" in phien:
        await phien["quanly"].goi(
            "PATCH", f"/api/v1/appointments/{appt2}", json={"action": "complete"}
        )
        tn = phien["thungan"]
        r1, r2 = await asyncio.gather(
            tn.goi(
                "POST",
                "/api/v1/payments",
                headers=khoa(),
                json={"visit_id": visit2, "kind": "dich_vu", "amount": 100000},
            ),
            tn.goi(
                "POST",
                "/api/v1/payments",
                headers=khoa(),
                json={"visit_id": visit2, "kind": "dich_vu", "amount": 100000},
            ),
        )
        if 200 not in (r1[0], r2[0]):
            print(f"    (thanh toán hỏng: {r1[0]} {str(r1[1])[:150]})")
        st, phi = await phien["quanly"].goi("GET", f"/api/v1/visits/{visit2}/charges")
        so_thu = sum(
            1
            for x in (phi or {}).get("payments", [])
            if str(x.get("kind")) == "dich_vu"
        )
        ket(
            "SC-35 bấm thanh toán 2 lần → đúng 1 khoản thu",
            so_thu == 1,
            f"mã {r1[0]}/{r2[0]} · database đếm {so_thu} khoản",
        )
    else:
        bo("SC-35 bấm thanh toán 2 lần", "không dựng được lượt khám / thiếu thu ngân")

    # ── SC-36: kho bấm cấp thuốc HAI LẦN ────────────────────────────────────
    #
    # Phải tự dựng cả hai đầu: một dòng đơn thuốc (bác sĩ kê) và một lô hàng có
    # tồn (dược sĩ nhập). Hệ thống mới dựng thì kho rỗng và chưa ai kê đơn, nên
    # không dựng thì kịch bản này không bao giờ chạy tới.
    if visit2 and appt2 and "duocsi" in phien and "bacsi" in phien:
        st, ho_so = await phien["bacsi"].goi(
            "POST",
            "/api/v1/clinical-records",
            json={
                "appointment_id": appt2,
                "clinic_patient_id": kh2,
                "expected_revision": 0,
                "prescriptions": [
                    {
                        "drug_name": "Canxi",
                        "quantity": "10",
                        "dosage": "1 viên/ngày",
                    }
                ],
            },
        )
        st, dm = await phien["duocsi"].goi("GET", "/api/v1/pharmacy/queue")
        don = next(
            (
                x
                for x in (dm or {}).get("items", [])
                if str(x.get("patient_name", "")).startswith(f"{DAU}{LAN}")
            ),
            None,
        )
        st, kho = await phien["duocsi"].goi("GET", "/api/v1/pharmacy/inventory")
        thuoc = ((kho or {}).get("items") or [None])[0]
        if thuoc is None:
            # Danh mục thuốc KHÔNG có cửa ở FastAPI — giao diện đọc thẳng qua
            # PostgREST (`app/api/catalog/route.ts`). Script đi đúng đường ấy
            # thay vì bịa ra một cửa không tồn tại.
            rc = await phien["duocsi"].http.get(
                f"{SB}/rest/v1/drug_catalog",
                params={"select": "id", "is_active": "eq.true", "limit": "1"},
                headers={"apikey": ANON},
            )
            ma_thuoc = None
            if rc.status_code == 200:
                ds_thuoc = rc.json() or []
                ma_thuoc = ds_thuoc[0]["id"] if ds_thuoc else None
            if ma_thuoc:
                import datetime as _d

                await phien["duocsi"].goi(
                    "POST",
                    "/api/v1/pharmacy/receive",
                    json={
                        "drug_catalog_id": ma_thuoc,
                        "so_luong": 50,
                        "batch_code": f"{DAU}{LAN}",
                        "expiry_date": (
                            _d.date.today() + _d.timedelta(days=365)
                        ).isoformat(),
                        "unit": "viên",
                    },
                )
                st, kho = await phien["duocsi"].goi("GET", "/api/v1/pharmacy/inventory")
                thuoc = ((kho or {}).get("items") or [None])[0]
        if not (thuoc and don):
            bo(
                "SC-36 bấm cấp thuốc 2 lần",
                f"kho {'có' if thuoc else 'RỖNG'} · đơn {'có' if don else 'CHƯA CÓ'}",
            )
        else:
            lo = thuoc.get("drug_batch_id") or thuoc.get("id")
            ds = phien["duocsi"]
            truoc = float(thuoc.get("quantity_on_hand") or thuoc.get("ton") or 0)
            # MỘT LẦN BẤM = MỘT KHOÁ, gửi đi hai lần.
            #
            # Khác hẳn SC-31/32 nơi hai khoá khác nhau giả lập hai NGƯỜI. Ở đây
            # là MỘT người bấm một cái, trình duyệt gửi hai lần (double-click,
            # mạng chập rồi thử lại). Và phải như thế, vì "cấp một phần" là hợp
            # lệ: hai khoá khác nhau nghĩa là cố ý cấp thêm, hệ thống không có
            # quyền từ chối.
            mot_khoa = khoa()
            than_thuoc = {
                "prescription_id": don.get("prescription_id") or don.get("id"),
                "drug_batch_id": lo,
                "so_luong": 1,
            }
            r1, r2 = await asyncio.gather(
                ds.goi(
                    "POST",
                    "/api/v1/pharmacy/dispense",
                    headers=mot_khoa,
                    json=than_thuoc,
                ),
                ds.goi(
                    "POST",
                    "/api/v1/pharmacy/dispense",
                    headers=mot_khoa,
                    json=than_thuoc,
                ),
            )
            st, kho2 = await ds.goi("GET", "/api/v1/pharmacy/inventory")
            sau = next(
                (
                    float(x.get("quantity_on_hand") or 0)
                    for x in (kho2 or {}).get("items", [])
                    if (x.get("drug_batch_id") or x.get("id")) == lo
                ),
                -1.0,
            )
            ket(
                "SC-36 bấm cấp thuốc 2 lần → trừ tồn đúng 1 lần",
                abs((truoc - sau) - 1.0) < 0.001,
                f"mã {r1[0]}/{r2[0]} · tồn {truoc:g} → {sau:g} (trừ {truoc - sau:g})",
            )
    else:
        bo("SC-36 bấm cấp thuốc 2 lần", "thiếu lượt khám hoặc vai dược sĩ")

    print()
    print(f"ĐẠT {dat} · HỎNG {hong} · bỏ qua {bo_qua}")
    if da_tao:
        import json
        import pathlib

        # NỐI THÊM, KHÔNG GHI ĐÈ. Chạy hai lần mà quên dọn giữa chừng thì bản
        # ghi đè xoá mất đường dọn của lần trước, và những bản ghi ấy nằm lại
        # trong database mãi mãi — tôi đã tự vấp đúng một lần trên máy chủ.
        f = pathlib.Path(os.environ.get("VET_FILE_DUA", ".dev-logs/dua-tranh-vet.json"))
        f.parent.mkdir(parents=True, exist_ok=True)
        cu = []
        if f.exists():
            try:
                cu = json.loads(f.read_text())
            except Exception:
                cu = []
        f.write_text(json.dumps(cu + da_tao, ensure_ascii=False, indent=1))
        da_tao = cu + da_tao
        print(f"Dấu vết ({len(da_tao)} bản ghi) → {f}; chạy --rollback để dọn.")
    for p in phien.values():
        await p.http.aclose()
    await http.aclose()
    return 1 if hong else 0


async def rollback() -> int:
    import json
    import pathlib

    f = pathlib.Path(os.environ.get("VET_FILE_DUA", ".dev-logs/dua-tranh-vet.json"))
    if not f.exists():
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
    vet = json.loads(f.read_text())
    for loai, ma in vet:
        if loai == "appointment":
            await p.goi(
                "PATCH",
                f"/api/v1/appointments/{ma}",
                json={
                    "action": "cancel",
                    "ly_do_huy_ma": "KHAC",
                    "cancellation_reason": f"{DAU} dọn sau khi thử đua tranh",
                },
            )
        else:
            await p.goi("PATCH", f"/api/v1/patients/{ma}", json={"is_active": False})
    print(f"Đã dọn {len(vet)} bản ghi.")
    f.rename(f.with_suffix(".json.da-don"))
    await c.aclose()
    await http.aclose()
    return 0


if __name__ == "__main__":
    if "--rollback" in sys.argv:
        raise SystemExit(asyncio.run(rollback()))
    raise SystemExit(asyncio.run(main()))
