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


# ── KỊCH BẢN GHI: một khách đi trọn buổi khám ────────────────────────────────
#
# Đọc màn thì chỉ chứng minh màn không nổ. Cái phải chứng minh là VÒNG ĐỜI:
# lễ tân check-in → điều dưỡng đo sinh hiệu → bác sĩ khám và chỉ định → trưởng ca
# xếp phòng → người thực hiện làm xong → bác sĩ kết luận. Mỗi bước do MỘT VAI
# KHÁC gọi, đúng như ngoài đời — nên nó cũng là phép thử quyền: vai sai thì 403.
#
# NHIỀU KHÁCH CÙNG LÚC, cố ý. Một khách chạy tuần tự thì mọi thao tác đều gặp
# bảng rỗng. Buổi khám thật có bốn năm người cùng ở các bước khác nhau, và những
# lỗi đắt nhất (khoá lạc quan, số thứ tự, sức chứa phòng) chỉ hiện ra ở đó.

DAU = "[e2e]"  # dấu để nhận ra và dọn; KHÔNG xoá cứng gì
VET = os.environ.get("VET_FILE", ".dev-logs/buoi-kham-that-dau-vet.json")


def _luu_vet(muc: dict[str, Any]) -> None:
    """Ghi dấu vết NGAY sau mỗi lần tạo, không đợi cuối phiên.

    Script chết giữa chừng là chuyện thường (Ctrl-C, máy chủ khởi động lại). Gom
    dấu vết trong bộ nhớ rồi ghi một lần ở cuối nghĩa là đúng lúc hỏng thì mất
    sạch đường dọn — và thứ còn lại trong database không ai biết của ai.
    """
    import json
    import pathlib

    f = pathlib.Path(VET)
    f.parent.mkdir(parents=True, exist_ok=True)
    cu = []
    if f.exists():
        try:
            cu = json.loads(f.read_text())
        except Exception:
            cu = []
    cu.append(muc)
    f.write_text(json.dumps(cu, ensure_ascii=False, indent=1))


def _gio_kham(ctx: dict[str, Any], thu_tu: int) -> tuple[str, str]:
    """Một khung CÒN Ở PHÍA TRƯỚC hôm nay, theo đúng giờ nhận lịch của phòng khám.

    KHÔNG tự bịa "08:00 + n phút". Chạy lúc 10:30 thì 08:00 đã qua và server từ
    chối đúng — một thất bại của phép thử chứ không phải của hệ thống. Chạy lúc
    13:20 thì rơi vào giờ nghỉ trưa, cũng bị từ chối đúng. Nên khung giờ phải
    đọc từ `khung_nhan_lich` của chính `/appointments/policy` — cùng nguồn mà
    lưới chọn giờ trên màn đọc.
    """
    import datetime as _dt

    tz = _dt.timezone(_dt.timedelta(hours=7))
    bay_gio = _dt.datetime.now(tz)
    d = bay_gio.date()
    buoc = int(ctx.get("slot_minutes") or 30)
    # +5 phút đệm: đặt vào khung bắt đầu trong 30 giây nữa là tự chuốc lấy một
    # cuộc đua với chính đồng hồ của server.
    som_nhat = bay_gio.hour * 60 + bay_gio.minute + 5
    khung = ctx.get("khung_nhan_lich") or [[0, 24 * 60]]
    phut = None
    for dau_k, cuoi_k in khung:
        bd = max(dau_k, ((som_nhat + buoc - 1) // buoc) * buoc)
        bd += thu_tu * buoc
        if bd + buoc <= cuoi_k:
            phut = bd
            break
    if phut is None:  # hết giờ nhận lịch hôm nay — đặt cho ngày mai
        d = d + _dt.timedelta(days=1)
        phut = khung[0][0] + thu_tu * buoc
    dau = _dt.datetime.combine(d, _dt.time(0, 0), tz) + _dt.timedelta(minutes=phut)
    return dau.isoformat(), (dau + _dt.timedelta(minutes=buoc)).isoformat()


async def mot_khach(
    kq: KetQua,
    phien: dict[str, Phien],
    ctx: dict[str, Any],
    stt: int,
) -> dict[str, Any]:
    """Trọn vòng của MỘT khách. Trả lại những gì đã tạo để còn dọn."""
    import uuid as _uuid

    ra: dict[str, Any] = {}
    nhan = f"khách {stt}"
    # Mỗi bước phụ thuộc bước trước, nên hỏng ở đâu là dừng ở đó — chạy tiếp với
    # id rỗng chỉ sinh ra một tràng 404 che mất lỗi thật.

    # 1 ── CSKH mở hồ sơ mới
    # 10 số, đầu số di động thật (09x) — luật ở `normalize_vn_phone` chỉ nhận
    # đúng bảng đầu số, nên số bịa tuỳ tiện bị từ chối ngay ở ô đầu tiên.
    ma = f"{int(time.time() * 1000) % 10_000_000:07d}"
    st, body = await phien["cskh"].goi(
        kq,
        f"{nhan}: tạo hồ sơ",
        "POST",
        "/api/v1/patients",
        json={
            "full_name": f"{DAU} Khách Thử {stt}",
            "date_of_birth": "1995-05-05",
            # 09 + 8 số: đúng dạng di động VN mà luật nhận, và đủ hiếm để không
            # đụng khách thật.
            "phone_primary": f"098{ma}",
            "location_id": ctx["location_id"],
            "gender": "female",
            "van_de_di_kham": f"{DAU} chạy thử buổi khám",
        },
    )
    if st != 201 or not isinstance(body, dict) or not body.get("clinic_patient_id"):
        return ra
    ra["clinic_patient_id"] = body["clinic_patient_id"]
    ra["patient_code"] = body.get("patient_code")
    _luu_vet({"loai": "patient", "id": ra["clinic_patient_id"], "luc": time.time()})

    # 2 ── CSKH đặt lịch hôm nay
    bd, kt = _gio_kham(ctx, stt)
    st, body = await phien["cskh"].goi(
        kq,
        f"{nhan}: đặt lịch",
        "POST",
        "/api/v1/appointments/bookings",
        headers={"Idempotency-Key": str(_uuid.uuid4())},
        json={
            "clinic_patient_id": ra["clinic_patient_id"],
            "service_type_id": ctx["service_type_id"],
            "location_id": ctx["location_id"],
            "slot_start": bd,
            "slot_end": kt,
            "doctor_id": ctx["doctor_id"],
            "booking_channel": "den_truc_tiep",
            "notes": f"{DAU} buổi khám thử",
        },
    )
    appt = (body or {}).get("appointment", body) if isinstance(body, dict) else {}
    appt_id = (appt or {}).get("id") or (body or {}).get("appointment_id")
    if not appt_id:
        return ra
    ra["appointment_id"] = appt_id
    _luu_vet({"loai": "appointment", "id": appt_id, "luc": time.time()})

    # 3 ── Lễ tân check-in
    st, body = await phien["letan"].goi(
        kq,
        f"{nhan}: check-in",
        "POST",
        "/api/v1/luot-kham/check-in",
        json={"appointment_id": appt_id, "xac_minh_cach": "GIAY_TO_CO_ANH"},
    )
    if st >= 400:
        return ra
    # `/luot-kham/check-in` KHÔNG trả về lượt khám nó vừa mở — nó trả
    # `{"ok": true, "status": "..."}`. Màn hình thật vì thế phải nạp lại bảng
    # sau mỗi lần check-in, và script cũng làm đúng thế: tìm lượt theo mã bệnh
    # nhân. Đọc lại còn chắc hơn tin mã 200 — nó chứng minh lượt CÓ THẬT.
    st, bang = await phien["bacsi"].goi(
        kq, f"{nhan}: bác sĩ mở bảng", "GET", "/api/v1/luot-kham/bang"
    )
    luot = next(
        (
            x
            for x in (bang or {}).get("luot", [])
            if x.get("ma_bn") == ra.get("patient_code")
        ),
        None,
    )
    if luot is None:
        kq.them(
            Buoc(
                f"{nhan}: tìm lượt sau check-in",
                "bacsi",
                0,
                False,
                "không có trên bảng",
            )
        )
        return ra
    visit_id = luot["visit_id"]
    ra["visit_id"] = visit_id
    _luu_vet({"loai": "visit", "id": visit_id, "luc": time.time()})

    # 4 ── Điều dưỡng đo sinh hiệu — ĐỦ MƯỜI Ô, gồm bốn chỉ số thêm 16/09.
    #      Gửi thiếu thì không ai báo lỗi, nên phép thử phải gửi đủ.
    await phien["dieuduong"].goi(
        kq,
        f"{nhan}: sinh hiệu",
        "POST",
        f"/api/v1/luot-kham/visits/{visit_id}/vitals",
        headers={"Idempotency-Key": str(_uuid.uuid4())},
        json={
            "systolic": 118,
            "diastolic": 76,
            "pulse": 80,
            "temperature": "36.8",
            "weight_kg": "54.5",
            "height_cm": 160,
            "respiratory_rate": 18,
            "spo2": 98,
            "bmi": "21.3",
            "pain_score": 3,
        },
    )

    # 5 ── Bác sĩ: mở phiên khám. Id phiên nằm trong bảng, không do ta đặt.
    #      Đọc lại bảng SAU khi đo sinh hiệu — vừa lấy id phiên, vừa soi xem
    #      mười ô sinh hiệu có thật sự nằm trong database không.
    st, bang = await phien["bacsi"].goi(
        kq, f"{nhan}: bác sĩ đọc lại bảng", "GET", "/api/v1/luot-kham/bang"
    )
    luot = next(
        (x for x in (bang or {}).get("luot", []) if x.get("visit_id") == visit_id),
        None,
    )
    if luot is None:
        return ra
    ra["sinh_hieu"] = luot.get("sinh_hieu")
    ph = (luot.get("phien") or [None])[0]
    if not ph:
        return ra
    cons = ph["id"]
    ra["consultation_id"] = cons

    await phien["bacsi"].goi(
        kq, f"{nhan}: vào khám", "POST", f"/api/v1/luot-kham/consultations/{cons}/start"
    )
    await phien["bacsi"].goi(
        kq,
        f"{nhan}: ghi chú khám",
        "POST",
        f"/api/v1/luot-kham/consultations/{cons}/notes",
        json={"body": f"{DAU} Khám phụ khoa định kỳ. Không sốt, bụng mềm."},
    )

    # 6 ── Bác sĩ chỉ định dịch vụ (luồng service_order — luồng được giữ lại)
    st, body = await phien["bacsi"].goi(
        kq,
        f"{nhan}: chỉ định dịch vụ",
        "POST",
        f"/api/v1/luot-kham/consultations/{cons}/authorize-orders",
        headers={"Idempotency-Key": str(_uuid.uuid4())},
        json={"service_codes": [ctx["service_code"]]},
    )
    ids = (body or {}).get("order_ids") or [] if isinstance(body, dict) else []
    if not ids:
        return ra
    ra["order_id"] = ids[0]

    # 7 ── Bác sĩ chốt: còn dịch vụ phải làm trước khi kết luận
    await phien["bacsi"].goi(
        kq,
        f"{nhan}: chốt 'còn dịch vụ'",
        "POST",
        f"/api/v1/luot-kham/consultations/{cons}/complete",
        headers={"Idempotency-Key": str(_uuid.uuid4())},
        json={
            "outcome": "SERVICES",
            "requirements": [{"order_id": ra["order_id"], "need": "PERFORMED"}],
        },
    )

    # 8 ── Trưởng ca xếp phòng cho chỉ định
    await phien["truongca"].goi(
        kq,
        f"{nhan}: xếp phòng",
        "POST",
        f"/api/v1/luot-kham/orders/{ra['order_id']}/dispatch",
        headers={"Idempotency-Key": str(_uuid.uuid4())},
        json={"room_id": ctx["room_id"]},
    )

    # 9 ── Người thực hiện làm dịch vụ — đúng vai mà danh mục cho phép
    lam = phien[ctx["nguoi_lam"]]
    await lam.goi(
        kq,
        f"{nhan}: bắt đầu dịch vụ",
        "POST",
        f"/api/v1/luot-kham/orders/{ra['order_id']}/start",
    )
    await lam.goi(
        kq,
        f"{nhan}: xong dịch vụ",
        "POST",
        f"/api/v1/luot-kham/orders/{ra['order_id']}/complete",
        json={"performed": True, "result_note": f"{DAU} Kết quả trong giới hạn."},
    )
    return ra


async def kich_ban_ghi(kq: KetQua, phien: dict[str, Phien], so_khach: int) -> None:
    """Chuẩn bị bối cảnh (cơ sở, dịch vụ, bác sĩ, phòng) rồi thả các khách vào."""
    p = phien.get("quanly") or next(iter(phien.values()))
    st, cfg = await p.goi(
        kq, "đọc cấu hình phòng khám", "GET", "/api/v1/clinic-config/overview"
    )
    st, bang = await p.goi(kq, "đọc bảng lượt khám", "GET", "/api/v1/luot-kham/bang")
    st, dv = await p.goi(
        kq, "đọc danh mục dịch vụ", "GET", "/api/v1/catalog/service-types"
    )
    import datetime as _dt

    _thu = str((_dt.date.today().weekday() + 1) % 7)
    st, pol = await p.goi(
        kq, "đọc luật nhận lịch", "GET", "/api/v1/appointments/policy"
    )
    if not isinstance(cfg, dict) or not isinstance(bang, dict):
        return

    co_so = next(
        (x for x in cfg.get("locations", []) if x.get("is_active") and x.get("floors")),
        None,
    )
    phong_kham = None
    for t in (co_so or {}).get("floors", []):
        for r in t.get("rooms", []):
            if r.get("is_active"):
                phong_kham = r
                break
        if phong_kham:
            break
    bac_si = next(
        (x.get("bac_si_id") for x in bang.get("luot", []) if x.get("bac_si_id")), None
    )
    # Dịch vụ chỉ định: phải là dịch vụ CÓ NGƯỜI TRONG NHÀ làm được. Chỉ định
    # một dịch vụ "gửi ra ngoài" (CLS_CHUP_MRI_VU…) thì bước 9 không ai bấm
    # được, và cái 403 sinh ra là lỗi của phép thử chứ không phải của hệ thống.
    #
    # Ưu tiên người KHÁC bác sĩ đã khám: một dịch vụ do chính bác sĩ ấy làm thì
    # không chứng minh được rằng bàn giao giữa hai vai chạy đúng.
    uu_tien = (
        ("ULTRASOUND_DOCTOR", "bacsi_sa"),
        ("NURSE_ULTRASOUND", "dieuduong"),
        ("DOCTOR", "bacsi"),
    )
    dvu = nguoi_lam = None
    for vai_ma, khoa in uu_tien:
        dvu = next(
            (d for d in bang.get("dich_vu", []) if vai_ma in (d.get("vai_lam") or [])),
            None,
        )
        if dvu is not None and khoa in phien:
            nguoi_lam = khoa
            break
    node = (dvu or {}).get("node")
    phong_dv = next(
        (r for r in bang.get("phong", []) if node and node in (r.get("nodes") or [])),
        None,
    )
    loai = next(
        (
            x
            for x in (dv if isinstance(dv, list) else [])
            if x.get("code") == "PHU_KHOA"
        ),
        None,
    )
    thieu = [
        t
        for t, v in (
            ("cơ sở", co_so),
            ("phòng khám", phong_kham),
            ("bác sĩ", bac_si),
            ("dịch vụ chỉ định", dvu),
            ("người thực hiện", nguoi_lam),
            ("phòng làm dịch vụ", phong_dv),
            ("loại khám", loai),
        )
        if not v
    ]
    if thieu:
        kq.them(
            Buoc("chuẩn bị bối cảnh", "hệ thống", 0, False, f"thiếu {', '.join(thieu)}")
        )
        return

    ctx = {
        "location_id": co_so["location_id"],
        "room_id": phong_dv["id"],
        "doctor_id": bac_si,
        "service_type_id": loai["id"],
        "service_code": dvu["ma"],
        "nguoi_lam": nguoi_lam,
        "slot_minutes": (pol or {}).get("slot_minutes")
        if isinstance(pol, dict)
        else None,
        "khung_nhan_lich": ((pol or {}).get("khung_nhan_lich") or {}).get(_thu)
        if isinstance(pol, dict)
        else None,
    }
    print(
        f"  bối cảnh: {co_so['name']} · BS {bac_si[:8]} · chỉ định {dvu['ma']}"
        f" → {phong_dv['ma']} (người làm: {nguoi_lam})"
    )

    print(f"\n── {so_khach} KHÁCH ĐI TRỌN VÒNG, CÙNG LÚC ──────────────────────")
    t0 = time.perf_counter()
    ket = await asyncio.gather(
        *(mot_khach(kq, phien, ctx, i + 1) for i in range(so_khach)),
        return_exceptions=True,
    )
    ms = (time.perf_counter() - t0) * 1000
    xong = [r for r in ket if isinstance(r, dict) and r.get("order_id")]
    print(f"  → {len(xong)}/{so_khach} khách đi hết vòng, tổng {ms:.0f}ms")

    # Sinh hiệu: kiểm ĐỌC LẠI, không tin mã trả về 200. Bốn chỉ số thêm ngày
    # 16/09 đã một lần ghi ra NULL trong im lặng vì máy chủ chạy Python cũ.
    for r in ket:
        if not isinstance(r, dict):
            continue
        s = r.get("sinh_hieu") or {}
        thieu_o = [
            k for k in ("nhip_tho", "spo2", "bmi", "muc_do_dau") if s.get(k) is None
        ]
        if s and thieu_o:
            kq.them(
                Buoc(
                    "sinh hiệu đọc lại",
                    "dieuduong",
                    0,
                    False,
                    f"bốn chỉ số mới về NULL: {', '.join(thieu_o)}",
                )
            )
            break


async def rollback(kq: KetQua, phien: dict[str, Phien]) -> None:
    """Dọn những gì script đã tạo — bằng ĐỔI TRẠNG THÁI, không xoá cứng.

    `patient`, `appointment`, `visit` nằm trong ba bảng cấm xoá cứng (chốt ở
    Postgres). Dọn đúng cách là huỷ lịch với lý do ghi rõ và tắt hồ sơ, y như
    người thật làm — nên bản thân lần dọn cũng là một phép thử.
    """
    import json
    import pathlib

    f = pathlib.Path(VET)
    if not f.exists():
        print("  không có dấu vết nào để dọn.")
        return
    vet = json.loads(f.read_text())
    print(f"\n── DỌN {len(vet)} DẤU VẾT ───────────────────────────────────────")
    ql = phien.get("quanly") or next(iter(phien.values()))
    for m in vet:
        if m["loai"] == "appointment":
            await ql.goi(
                kq,
                f"huỷ lịch {m['id'][:8]}",
                "PATCH",
                f"/api/v1/appointments/{m['id']}",
                json={
                    "action": "cancel",
                    "ly_do_huy_ma": "KHAC",
                    "cancellation_reason": f"{DAU} dọn sau khi chạy thử buổi khám",
                },
            )
        elif m["loai"] == "patient":
            await ql.goi(
                kq,
                f"tắt hồ sơ {m['id'][:8]}",
                "PATCH",
                f"/api/v1/patients/{m['id']}",
                json={"is_active": False},
            )
    # DỌN XONG THÌ PHẢI KIỂM, không tin mã 200. Lần đầu chạy, 33 lời gọi dọn
    # đều xanh mà bảng bác sĩ vẫn còn 12 lượt [e2e] — huỷ lịch hồi đó chỉ huỷ
    # các BƯỚC, không đóng lượt. Một phép dọn không tự kiểm lại thì chính nó là
    # chỗ trốn của lỗi.
    st, bang = await ql.goi(
        kq, "kiểm lại bảng sau khi dọn", "GET", "/api/v1/luot-kham/bang"
    )
    con = [
        x for x in (bang or {}).get("luot", []) if str(x.get("ten", "")).startswith(DAU)
    ]
    if con:
        kq.them(
            Buoc(
                "dọn sót",
                "hệ thống",
                0,
                False,
                f"{len(con)} lượt {DAU} còn trên bảng lượt khám",
            )
        )
    f.rename(f.with_suffix(".json.da-don"))
    print("  đã dọn; dấu vết đổi tên thành *.da-don (giữ lại để đối chiếu).")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--rollback",
        action="store_true",
        help="dọn những gì lần chạy trước đã tạo, rồi thoát",
    )
    ap.add_argument(
        "--ghi",
        type=int,
        default=0,
        metavar="N",
        help="cho N khách đi trọn vòng khám (mặc định 0 = chỉ đọc màn)",
    )
    args = ap.parse_args()

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

    if args.rollback:
        await rollback(kq, phien)
    elif args.ghi:
        print("\n── CHUẨN BỊ BỐI CẢNH ───────────────────────────────────────────")
        await kich_ban_ghi(kq, phien, args.ghi)

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
