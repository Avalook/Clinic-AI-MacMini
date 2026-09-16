#!/usr/bin/env python3
"""Dựng 20 khách ở ĐỦ CÁC TRẠNG THÁI để người thật ngồi bấm thử.

Khác hẳn ba bộ kiểm thử kia: chúng CHẠY rồi DỌN, còn tệp này DỰNG RỒI ĐỂ ĐẤY —
mục đích là có sẵn mỗi tình huống một khách, để người mở màn lên là thao tác
được ngay chứ không phải tự tạo dữ liệu trước.

ĐI QUA API THẬT, KHÔNG NHÉT THẲNG DATABASE. Nhét thẳng thì dựng được những
trạng thái mà hệ thống KHÔNG BAO GIỜ sinh ra, và người thử sẽ bấm vào một cảnh
không tồn tại ngoài đời. Mọi khách dưới đây đi đúng các cửa mà nhân viên đi.

    PYTHONPATH=src poetry run python scripts/tests/tao-khach-de-thao-tac.py

Hai mươi khách, chia theo việc người thử cần làm:

    A. 6 khách CHỜ CHECK-IN hôm nay      → lễ tân tập đón khách
    B. 4 khách ĐÃ CHECK-IN, chưa sinh hiệu → điều dưỡng tập đo
    C. 3 khách ĐÃ CÓ SINH HIỆU            → bác sĩ tập khám
    D. 2 khách ĐANG KHÁM, đã có chỉ định  → trưởng ca tập xếp phòng
    E. 2 khách CHỈ CÓ HỒ SƠ, chưa lịch    → CSKH tập đặt lịch cho khách cũ
    F. 2 khách CÓ LỊCH NGÀY MAI           → tập nhắc hẹn, đổi lịch, huỷ
    G. 1 khách ĐÃ HUỶ LỊCH                → xem lịch huỷ trông thế nào
    H. 2 khách CÓ ĐƠN THUỐC chờ trả tiền  → thu ngân thuốc + dược sĩ
    I. 2 khách CÓ DỊCH VỤ chờ trả tiền    → thu ngân dịch vụ
    K. 1 khách ĐÃ TRẢ TIỀN xong           → quầy thu ngân trông ra sao khi xong
    L. 2 khách CÓ CHỈ ĐỊNH GỬI RA NGOÀI   → đối tác có việc để gửi kết quả

Bốn nhóm cuối thêm 16/09/2026, sau khi Tuyền chỉ ra hai màn chưa ai dựng được
cảnh để bấm: quầy thu ngân và cửa gửi kết quả của đối tác. Một màn không có dữ
liệu thì không phân biệt được "chạy đúng mà hôm nay rỗng" với "hỏng".
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import sys
import time
import unicodedata
import uuid
from typing import Any

import httpx

API = os.environ.get("CLINIC_API_URL", "http://127.0.0.1:8100")
SB = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54421")
ANON = os.environ.get("SUPABASE_ANON_KEY", "")
PW = os.environ.get("TEST_PW", "")
KHOA_API = os.environ.get("BACKEND_API_KEY", "")
TZ = dt.timezone(dt.timedelta(hours=7))

VAI = {
    v: os.environ.get(f"TK_{v}", m)
    for v, m in (
        ("cskh", "cskh@dr4women.local"),
        ("letan", "letan@dr4women.local"),
        ("dieuduong", "dd.sa@dr4women.local"),
        ("bacsi", "bs.a@dr4women.local"),
        ("quanly", "ql@dr4women.local"),
    )
}
MAT_KHAU_VAI = {v: os.environ.get(f"MK_{v}", "") for v in VAI}

#: Tên người Việt thật, không phải "Khách 1" — người thử phải nhìn thấy một
#: danh sách giống danh sách thật thì mới phát hiện được cái gì trông sai.
TEN = [
    "Nguyễn Thị Mai Anh",
    "Trần Thu Hà",
    "Lê Ngọc Bích",
    "Phạm Thanh Vân",
    "Hoàng Thị Kim Chi",
    "Vũ Hải Yến",
    "Đỗ Thị Lan Hương",
    "Bùi Minh Thư",
    "Đặng Phương Linh",
    "Ngô Thị Hồng Nhung",
    "Dương Khánh Ly",
    "Lý Thị Thu Trang",
    "Trịnh Bảo Ngọc",
    "Cao Thị Mỹ Duyên",
    "Phan Thuỳ Dương",
    "Tạ Thị Hồng Vân",
    "Mai Thị Ánh Tuyết",
    "Hồ Ngọc Diệp",
    "Chu Thị Hạnh",
    "Lương Thị Kiều Oanh",
    # Bảy tên cho bốn nhóm thêm sau (H, I, K, L).
    "Đinh Thị Thanh Nga",
    "Võ Thị Kim Phượng",
    "Huỳnh Ngọc Trâm",
    "Nguyễn Thị Bích Ngọc",
    "Trương Mỹ Hạnh",
    "Đoàn Thị Thu Thuỷ",
    "Lâm Thị Cẩm Tú",
]


def khoa() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


async def token(http: httpx.AsyncClient, email: str, mk: str | None) -> str | None:
    for lan in range(2):
        r = await http.post(
            f"{SB}/auth/v1/token?grant_type=password",
            headers={"apikey": ANON, "Content-Type": "application/json"},
            json={"email": email, "password": mk or PW},
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


def khong_dau(s: str) -> str:
    s = s.replace("Đ", "D").replace("đ", "d")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def khung(ctx: dict[str, Any], sau_ngay: int, thu_tu: int) -> tuple[str, str]:
    """Khung giờ hợp lệ theo giờ nhận lịch thật của phòng khám."""
    bay_gio = dt.datetime.now(TZ)
    d = bay_gio.date() + dt.timedelta(days=sau_ngay)
    buoc = int(ctx.get("slot_minutes") or 15)
    som = 0 if sau_ngay > 0 else bay_gio.hour * 60 + bay_gio.minute + 10
    ds = (ctx.get("khung_theo_thu") or {}).get(str((d.weekday() + 1) % 7)) or [
        [8 * 60, 21 * 60 + 30]
    ]
    phut = ds[0][0]
    for dau_k, cuoi_k in ds:
        bd = max(dau_k, ((som + buoc - 1) // buoc) * buoc) + thu_tu * buoc
        if bd + buoc <= cuoi_k:
            phut = bd
            break
    b = dt.datetime.combine(d, dt.time(0, 0), TZ) + dt.timedelta(minutes=phut)
    return b.isoformat(), (b + dt.timedelta(minutes=buoc)).isoformat()


async def main() -> int:
    if not (ANON and PW and KHOA_API):
        print("Thiếu SUPABASE_ANON_KEY / TEST_PW / BACKEND_API_KEY", file=sys.stderr)
        return 2
    http = httpx.AsyncClient(timeout=60.0)
    phien: dict[str, Phien] = {}
    for vai, email in VAI.items():
        t = await token(http, email, MAT_KHAU_VAI.get(vai) or None)
        if not t:
            print(f"Không đăng nhập được {vai} ({email})", file=sys.stderr)
            return 1
        c = httpx.AsyncClient(timeout=60.0)
        c.headers["Authorization"] = f"Bearer {t}"
        c.headers["X-API-Key"] = KHOA_API
        phien[vai] = Phien(c)
        await asyncio.sleep(0.3)

    st, dv = await phien["cskh"].goi("GET", "/api/v1/catalog/service-types")
    st, pol = await phien["cskh"].goi("GET", "/api/v1/appointments/policy")
    st, toi = await phien["bacsi"].goi("GET", "/api/v1/me")
    hom_nay = dt.date.today()
    thu_hai = hom_nay - dt.timedelta(days=hom_nay.weekday())
    st, luoi = await phien["cskh"].goi(
        "GET",
        f"/api/v1/appointments/cho-trong-tuan?week_start={thu_hai.isoformat()}",
    )
    # AI TRỰC NGÀY NÀO — đọc thẳng từ lưới đặt lịch.
    #
    # Lịch trực đã công bố nên hệ thống TỪ CHỐI đặt cho bác sĩ không đi làm hôm
    # ấy, và nó từ chối đúng. Bản đầu của script chọn bác sĩ xoay vòng rồi ăn 17
    # cái 409 — dữ liệu không dựng được, mà lỗi thì của script.
    ngay_luoi: list[str] = (luoi or {}).get("ngay", [])
    bac_si = [b for b in (luoi or {}).get("bac_si", []) if b.get("id")]

    def truc(ngay: str) -> list[dict[str, Any]]:
        """Bác sĩ còn nhận lịch ngày ấy. `NGHI` = không đi làm, `DA_QUA` = qua rồi."""
        if ngay not in ngay_luoi:
            return bac_si
        i = ngay_luoi.index(ngay)
        return [
            b
            for b in bac_si
            if (b["o"][i] or {}).get("trang_thai") not in ("NGHI", "DA_QUA", "DONG_CUA")
        ]

    if not (dv and toi and bac_si):
        print("Không dựng được bối cảnh.", file=sys.stderr)
        return 1
    ctx = {
        "location_id": toi["location_id"],
        "slot_minutes": (pol or {}).get("slot_minutes"),
        "khung_theo_thu": (pol or {}).get("khung_nhan_lich") or {},
    }
    loai = {x["code"]: x["id"] for x in dv}
    print(f"Bối cảnh: {len(bac_si)} bác sĩ · {len(loai)} loại khám\n")

    ma_goc = int(time.time()) % 1_000_000
    da = []

    async def tao(i: int, ten: str) -> str | None:
        st, b = await phien["cskh"].goi(
            "POST",
            "/api/v1/patients",
            json={
                "full_name": ten,
                "date_of_birth": (
                    f"19{70 + (i % 30):02d}-{1 + i % 12:02d}-{1 + i % 28:02d}"
                ),
                "phone_primary": f"09{(ma_goc + i) % 100_000_000:08d}",
                "location_id": ctx["location_id"],
                "gender": "female",
                "van_de_di_kham": [
                    "Khám định kỳ",
                    "Đau bụng dưới",
                    "Chậm kinh",
                    "Khám thai",
                    "Tư vấn hiếm muộn",
                    "Ra khí hư bất thường",
                ][i % 6],
            },
        )
        return (b or {}).get("clinic_patient_id") if st == 201 else None

    async def dat(kh: str, i: int, sau_ngay: int, ma_loai: str) -> str | None:
        bd, kt = khung(ctx, sau_ngay, i)
        ds = truc(bd[:10])
        if not ds:
            print(f"    ngày {bd[:10]}: không bác sĩ nào trực")
            return None
        bs = ds[i % len(ds)]
        st, b = await phien["cskh"].goi(
            "POST",
            "/api/v1/appointments/bookings",
            headers=khoa(),
            json={
                "clinic_patient_id": kh,
                "service_type_id": loai.get(ma_loai, next(iter(loai.values()))),
                "location_id": ctx["location_id"],
                "slot_start": bd,
                "slot_end": kt,
                "doctor_id": bs["id"],
                "booking_channel": ["online", "den_truc_tiep", "dien_thoai"][i % 3],
            },
        )
        if st != 201:
            print(f"    lịch cho {i}: {st} {str(b)[:110]}")
        return (b or {}).get("appointment_id") if st == 201 else None

    loai_kham = ["PHU_KHOA", "SAN_1", "NOI_TIET_TINH_DUC", "HIEM_MUON", "NAM_KHOA"]

    # CHẠY LẠI CẢ TỆP LÀ DỰNG THÊM MỘT BỘ KHÁCH NỮA, không phải cập nhật bộ cũ:
    # cùng hai mươi cái tên, hai mươi mã bệnh nhân mới. Nên khi chỉ cần bù một
    # nhóm (thêm màn mới, hoặc một nhóm hỏng giữa chừng) thì gọi tên nhóm ấy ra:
    #
    #     CHI_NHOM=H,I,K,L python scripts/tests/tao-khach-de-thao-tac.py
    #
    # Bối cảnh dùng chung (bác sĩ trực hôm nay, dịch vụ để chỉ định) vẫn dựng
    # đủ dù bỏ nhóm nào — bốn nhóm cuối mượn lại của nhóm D.
    chi_nhom = {
        x.strip().upper()
        for x in (os.environ.get("CHI_NHOM") or "").split(",")
        if x.strip()
    }

    def lam(nhom: str) -> bool:
        return not chi_nhom or nhom in chi_nhom

    # ── A. 6 khách chờ check-in HÔM NAY ────────────────────────────────────
    if lam("A"):
        print("A. Chờ check-in hôm nay (lễ tân tập đón khách)")
        for i in range(6):
            kh = await tao(i, TEN[i])
            if not kh:
                continue
            a = await dat(kh, i, 0, loai_kham[i % len(loai_kham)])
            da.append((TEN[i], "chờ check-in hôm nay" if a else "chỉ có hồ sơ"))
            print(f"   {TEN[i]:<24} {'có lịch hôm nay' if a else 'KHÔNG đặt được'}")

    # ── B. 4 khách ĐÃ check-in, chưa đo sinh hiệu ─────────────────────────
    if lam("B"):
        print("\nB. Đã check-in, CHƯA đo sinh hiệu (điều dưỡng tập đo)")
        da_checkin: list[tuple[str, str]] = []
        for i in range(6, 10):
            kh = await tao(i, TEN[i])
            if not kh:
                continue
            a = await dat(kh, i, 0, loai_kham[i % len(loai_kham)])
            if a:
                await phien["letan"].goi(
                    "POST", "/api/v1/luot-kham/check-in", json={"appointment_id": a}
                )
                da_checkin.append((TEN[i], a))
            da.append((TEN[i], "đã check-in, chờ sinh hiệu"))
            print(f"   {TEN[i]:<24} {'đã check-in' if a else 'KHÔNG đặt được'}")

    # ── C. 3 khách ĐÃ có sinh hiệu (bác sĩ tập khám) ──────────────────────
    if lam("C"):
        print("\nC. Đã đo sinh hiệu, chờ bác sĩ")
        for i in range(10, 13):
            kh = await tao(i, TEN[i])
            if not kh:
                continue
            a = await dat(kh, i, 0, loai_kham[i % len(loai_kham)])
            if not a:
                continue
            await phien["letan"].goi(
                "POST", "/api/v1/luot-kham/check-in", json={"appointment_id": a}
            )
            st, bang = await phien["bacsi"].goi("GET", "/api/v1/luot-kham/bang")
            luot = next(
                (x for x in (bang or {}).get("luot", []) if x.get("ten") == TEN[i]),
                None,
            )
            if luot:
                await phien["dieuduong"].goi(
                    "POST",
                    f"/api/v1/luot-kham/visits/{luot['visit_id']}/vitals",
                    headers=khoa(),
                    json={
                        "systolic": 110 + i,
                        "diastolic": 70 + (i % 10),
                        "pulse": 72 + (i % 8),
                        "temperature": "36.7",
                        "weight_kg": f"5{i % 10}.0",
                        "height_cm": 155 + (i % 10),
                        "respiratory_rate": 17 + (i % 4),
                        "spo2": 97 + (i % 3),
                        "bmi": "21.5",
                        "pain_score": i % 5,
                    },
                )
            da.append((TEN[i], "đã có sinh hiệu, chờ bác sĩ"))
            print(f"   {TEN[i]:<24} sinh hiệu đã ghi")

    # ── D. 2 khách ĐANG khám, đã có chỉ định chờ xếp phòng ────────────────
    if lam("D"):
        print("\nD. Đang khám, có chỉ định chờ trưởng ca xếp phòng")
    st, bang = await phien["bacsi"].goi("GET", "/api/v1/luot-kham/bang")
    dvu = next(
        (
            d
            for d in (bang or {}).get("dich_vu", [])
            if "ULTRASOUND_DOCTOR" in (d.get("vai_lam") or [])
        ),
        None,
    )
    # BÁC SĨ PHẢI LÀ NGƯỜI ĐANG TRỰC HÔM NAY, và script phải ĐĂNG NHẬP bằng
    # chính người ấy — chỉ bác sĩ phụ trách mới chỉ định được cho lượt của mình.
    bd0, _ = khung(ctx, 0, 0)
    truc_hom_nay = [b for b in truc(bd0[:10]) if b.get("id")]
    bs_hom_nay = truc_hom_nay[0] if truc_hom_nay else None
    p_bacsi = phien["bacsi"]
    if bs_hom_nay and bs_hom_nay["id"] != toi["staff_id"]:
        ten_tk = khong_dau(bs_hom_nay["full_name"]).lower()
        ten_tk = "-".join(t for t in ten_tk.replace("-", " ").split() if t)
        t2 = await token(http, f"{ten_tk}@dr4women.vn", None)
        if t2:
            c2 = httpx.AsyncClient(timeout=60.0)
            c2.headers["Authorization"] = f"Bearer {t2}"
            c2.headers["X-API-Key"] = KHOA_API
            p_bacsi = Phien(c2)
            print(f"   (đăng nhập {bs_hom_nay['full_name']} — người trực hôm nay)")
        else:
            bs_hom_nay = None
            print("   (không đăng nhập được bác sĩ trực — bỏ nhóm D)")

    if lam("D"):
        for i in range(13, 15):
            if not bs_hom_nay:
                break
            kh = await tao(i, TEN[i])
            if not kh:
                continue
            bd, kt = khung(ctx, 0, i)
            st, b = await phien["cskh"].goi(
                "POST",
                "/api/v1/appointments/bookings",
                headers=khoa(),
                json={
                    "clinic_patient_id": kh,
                    "service_type_id": loai["PHU_KHOA"],
                    "location_id": ctx["location_id"],
                    "slot_start": bd,
                    "slot_end": kt,
                    "doctor_id": bs_hom_nay["id"],
                    "booking_channel": "den_truc_tiep",
                },
            )
            a = (b or {}).get("appointment_id")
            if not a:
                continue
            await phien["letan"].goi(
                "POST", "/api/v1/luot-kham/check-in", json={"appointment_id": a}
            )
            st, bang = await p_bacsi.goi("GET", "/api/v1/luot-kham/bang")
            luot = next(
                (x for x in (bang or {}).get("luot", []) if x.get("ten") == TEN[i]),
                None,
            )
            if not luot:
                continue
            await phien["dieuduong"].goi(
                "POST",
                f"/api/v1/luot-kham/visits/{luot['visit_id']}/vitals",
                headers=khoa(),
                json={"systolic": 118, "diastolic": 75, "pulse": 80},
            )
            st, bang = await p_bacsi.goi("GET", "/api/v1/luot-kham/bang")
            luot = next(
                (x for x in (bang or {}).get("luot", []) if x.get("ten") == TEN[i]),
                None,
            )
            ph = ((luot or {}).get("phien") or [None])[0]
            if ph and dvu:
                await p_bacsi.goi(
                    "POST", f"/api/v1/luot-kham/consultations/{ph['id']}/start"
                )
                await p_bacsi.goi(
                    "POST",
                    f"/api/v1/luot-kham/consultations/{ph['id']}/notes",
                    json={
                        "body": f"Khám {TEN[i]}: bụng mềm, không sốt. Chỉ định siêu âm."
                    },
                )
                await p_bacsi.goi(
                    "POST",
                    f"/api/v1/luot-kham/consultations/{ph['id']}/authorize-orders",
                    headers=khoa(),
                    json={"service_codes": [dvu["ma"]]},
                )
            da.append((TEN[i], "đang khám, có chỉ định chờ xếp phòng"))
            print(f"   {TEN[i]:<24} đã chỉ định {dvu['ma'] if dvu else '—'}")

    # ── E. 2 khách CHỈ có hồ sơ (CSKH tập đặt lịch cho khách cũ) ──────────
    if lam("E"):
        print("\nE. Chỉ có hồ sơ, chưa lịch (CSKH tập đặt cho khách cũ)")
        for i in range(15, 17):
            kh = await tao(i, TEN[i])
            if kh:
                da.append((TEN[i], "chỉ có hồ sơ, chưa có lịch"))
                print(f"   {TEN[i]:<24} hồ sơ đã tạo")

    # ── F. 2 khách có lịch NGÀY MAI ───────────────────────────────────────
    if lam("F"):
        print("\nF. Có lịch ngày mai (tập nhắc hẹn / đổi lịch)")
        for i in range(17, 19):
            kh = await tao(i, TEN[i])
            if not kh:
                continue
            a = await dat(kh, i, 1, loai_kham[i % len(loai_kham)])
            da.append((TEN[i], "có lịch ngày mai"))
            print(f"   {TEN[i]:<24} {'lịch ngày mai' if a else 'KHÔNG đặt được'}")

    # ── G. 1 khách đã HUỶ lịch ────────────────────────────────────────────
    if lam("G"):
        print("\nG. Lịch đã huỷ (xem lịch huỷ trông thế nào)")
        kh = await tao(19, TEN[19])
        if kh:
            a = await dat(kh, 19, 2, "PHU_KHOA")
            if a:
                await phien["cskh"].goi(
                    "PATCH",
                    f"/api/v1/appointments/{a}",
                    json={
                        "action": "cancel",
                        "ly_do_huy_ma": "BAO_KHI_NHAC_HEN",
                    },
                )
            da.append((TEN[19], "đã huỷ lịch"))
            print(f"   {TEN[19]:<24} {'đã huỷ lịch' if a else 'KHÔNG đặt được'}")

        # ── Đường chung của bốn nhóm cuối ─────────────────────────────────────
        #

    # H, I, K, L đều cần MỘT người ngồi trước mặt bác sĩ: có lịch hôm nay, đã
    # check-in, đã đo sinh hiệu, phiên khám đã mở. Viết bốn lần là bốn chỗ để
    # lệch nhau; viết một lần thì bốn nhóm cùng đi qua đúng những cửa ấy.
    async def den_ban_kham(i: int, ten: str) -> dict[str, Any] | None:
        """Dựng một khách tới tận bàn khám. Trả visit_id + phiên khám đang mở."""
        if not bs_hom_nay:
            return None
        kh = await tao(i, ten)
        if not kh:
            return None
        bd, kt = khung(ctx, 0, i)
        st, b = await phien["cskh"].goi(
            "POST",
            "/api/v1/appointments/bookings",
            headers=khoa(),
            json={
                "clinic_patient_id": kh,
                "service_type_id": loai["PHU_KHOA"],
                "location_id": ctx["location_id"],
                "slot_start": bd,
                "slot_end": kt,
                "doctor_id": bs_hom_nay["id"],
                "booking_channel": "den_truc_tiep",
            },
        )
        a = (b or {}).get("appointment_id")
        if not a:
            print(f"    {ten}: không đặt được lịch ({st})")
            return None
        await phien["letan"].goi(
            "POST", "/api/v1/luot-kham/check-in", json={"appointment_id": a}
        )
        st, bang = await p_bacsi.goi("GET", "/api/v1/luot-kham/bang")
        luot = next(
            (x for x in (bang or {}).get("luot", []) if x.get("ten") == ten), None
        )
        if not luot:
            print(f"    {ten}: không thấy trong bảng lượt khám")
            return None
        await phien["dieuduong"].goi(
            "POST",
            f"/api/v1/luot-kham/visits/{luot['visit_id']}/vitals",
            headers=khoa(),
            json={"systolic": 116, "diastolic": 74, "pulse": 78},
        )
        st, bang = await p_bacsi.goi("GET", "/api/v1/luot-kham/bang")
        luot = next(
            (x for x in (bang or {}).get("luot", []) if x.get("ten") == ten), None
        )
        ph = ((luot or {}).get("phien") or [None])[0]
        if not ph:
            print(f"    {ten}: chưa mở được phiên khám")
            return None
        await p_bacsi.goi("POST", f"/api/v1/luot-kham/consultations/{ph['id']}/start")
        return {
            "clinic_patient_id": kh,
            "appointment_id": a,
            "visit_id": luot["visit_id"],
            "phien_id": ph["id"],
        }

    # Hai quầy thu ngân là tài khoản THEO VỊ TRÍ, mới có từ 16/09 — máy nào chưa
    # có thì bỏ nhóm ấy và NÓI RA, đừng để script chết giữa chừng và bỏ dở cả
    # những nhóm sau nó.
    async def phien_phu(email: str) -> Phien | None:
        t = await token(http, email, None)
        if not t:
            return None
        c = httpx.AsyncClient(timeout=60.0)
        c.headers["Authorization"] = f"Bearer {t}"
        c.headers["X-API-Key"] = KHOA_API
        return Phien(c)

    tn_dv = await phien_phu(
        os.environ.get("TK_thungan_dv", "thu-ngan-dich-vu@dr4women.vn")
    )

    # ── H. 2 khách có ĐƠN THUỐC chờ trả tiền ──────────────────────────────
    if lam("H"):
        print("\nH. Có đơn thuốc, chờ thu ngân thuốc")
        for i, thuoc in ((20, "Canxi"), (21, "Sắt")):
            ban = await den_ban_kham(i, TEN[i])
            if not ban:
                continue
            await p_bacsi.goi(
                "POST",
                f"/api/v1/luot-kham/consultations/{ban['phien_id']}/notes",
                json={"body": f"Khám {TEN[i]}: ổn định. Kê {thuoc} uống sau ăn."},
            )
            st, _ = await p_bacsi.goi(
                "POST",
                "/api/v1/clinical-records",
                json={
                    "appointment_id": ban["appointment_id"],
                    "clinic_patient_id": ban["clinic_patient_id"],
                    "expected_revision": 0,
                    "prescriptions": [
                        {"drug_name": thuoc, "quantity": "10", "dosage": "1 viên/ngày"}
                    ],
                },
            )
            ok = st in (200, 201)
            da.append((TEN[i], "có đơn thuốc, chờ thu ngân thuốc"))
            noi = f"đơn {thuoc}" if ok else f"KHÔNG kê được ({st})"
            print(f"   {TEN[i]:<24} {noi}")

    # ── I. 2 khách có DỊCH VỤ chờ trả tiền ────────────────────────────────
    if lam("I"):
        print("\nI. Có dịch vụ, chờ thu ngân dịch vụ")
        cho_thu: list[tuple[str, str]] = []
        for i in (22, 23):
            ban = await den_ban_kham(i, TEN[i])
            if not (ban and dvu):
                continue
            await p_bacsi.goi(
                "POST",
                f"/api/v1/luot-kham/consultations/{ban['phien_id']}/notes",
                json={"body": f"Khám {TEN[i]}: chỉ định {dvu['ma']}."},
            )
            st, _ = await p_bacsi.goi(
                "POST",
                f"/api/v1/luot-kham/consultations/{ban['phien_id']}/authorize-orders",
                headers=khoa(),
                json={"service_codes": [dvu["ma"]]},
            )
            ok = st in (200, 201)
            if ok:
                cho_thu.append((TEN[i], ban["visit_id"]))
            da.append((TEN[i], "có dịch vụ, chờ thu ngân dịch vụ"))
            noi = f"đã chỉ định {dvu['ma']}" if ok else f"KHÔNG chỉ định được ({st})"
            print(f"   {TEN[i]:<24} {noi}")

    # ── K. 1 khách ĐÃ trả tiền xong ───────────────────────────────────────
    if lam("K"):
        print("\nK. Đã trả tiền xong")
        ban = await den_ban_kham(24, TEN[24]) if tn_dv else None
        if not tn_dv:
            print("   (bỏ nhóm: chưa đăng nhập được tài khoản thu ngân dịch vụ)")
        elif ban and dvu:
            await p_bacsi.goi(
                "POST",
                f"/api/v1/luot-kham/consultations/{ban['phien_id']}/authorize-orders",
                headers=khoa(),
                json={"service_codes": [dvu["ma"]]},
            )
            st, phi = await tn_dv.goi(
                "GET", f"/api/v1/visits/{ban['visit_id']}/charges"
            )
            # Trả ĐÚNG số tiền hệ thống tính, không bịa một con số tròn: một khoản
            # thu lệch với bảng giá là thứ người thử sẽ tưởng là lỗi của phần mềm.
            tien = (phi or {}).get("total") or (phi or {}).get("tong") or 0
            st, r = await tn_dv.goi(
                "POST",
                "/api/v1/payments",
                headers=khoa(),
                json={
                    "visit_id": ban["visit_id"],
                    "kind": "dich_vu",
                    "amount": int(float(tien or 0)),
                },
            )
            ok = st in (200, 201)
            da.append((TEN[24], "đã trả tiền xong"))
            noi = f"đã thu {tien}" if ok else f"KHÔNG thu được ({st} {str(r)[:80]})"
            print(f"   {TEN[24]:<24} {noi}")

    # ── L. 2 khách có chỉ định GỬI RA NGOÀI ───────────────────────────────
    if lam("L"):
        #
        # `node_definition.lam_ben_ngoai` quyết định việc nào hiện ra cho đối tác.
        # Hai mã dưới đây thuộc hai bước khác nhau (lấy máu / lấy nước tiểu) để màn
        # của đối tác có hơn một loại việc, chứ không phải hai dòng giống hệt nhau.
        print("\nL. Chỉ định gửi ra ngoài (đối tác có việc để gửi kết quả)")
        for i, ma_dv in ((25, "CLS_XET_NGHIEM_MAU"), (26, "CLS_NUOC_TIEU")):
            ban = await den_ban_kham(i, TEN[i])
            if not ban:
                continue
            await p_bacsi.goi(
                "POST",
                f"/api/v1/luot-kham/consultations/{ban['phien_id']}/notes",
                json={"body": f"Khám {TEN[i]}: gửi mẫu ra ngoài làm {ma_dv}."},
            )
            st, r = await p_bacsi.goi(
                "POST",
                f"/api/v1/luot-kham/consultations/{ban['phien_id']}/authorize-orders",
                headers=khoa(),
                json={"service_codes": [ma_dv]},
            )
            ok = st in (200, 201)
            da.append((TEN[i], f"chờ kết quả từ đối tác ({ma_dv})"))
            noi = (
                f"đã gửi ra ngoài: {ma_dv}"
                if ok
                else f"KHÔNG chỉ định được ({st} {str(r)[:80]})"
            )
            print(f"   {TEN[i]:<24} {noi}")

    if tn_dv:
        await tn_dv.http.aclose()

    print(f"\n=== Đã dựng {len(da)} khách ===")
    for ten, tt in da:
        print(f"  {ten:<24} {tt}")
    for p in phien.values():
        await p.http.aclose()
    await http.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
