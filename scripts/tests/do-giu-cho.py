#!/usr/bin/env python3
"""Đo THẬT: hai CSKH cùng nhắm một khung giờ thì bên kia biết sau bao lâu.

Tuyền hỏi 14/08/2026: *"cùng lúc mấy người đang đặt cùng 1 lịch thì hiện giữ
chỗ trên máy người khác đỗ trễ bao lâu"*. Câu ấy không trả lời được bằng cách
đọc code, vì độ trễ nằm ở CHỖ NỐI giữa ba con số ở ba tệp khác nhau:

    BookingHub.tsx:965   chờ 400ms rồi mới gửi lệnh giữ chỗ
    slot_hold_service    ghi một dòng vào slot_hold
    BookingHub.tsx:904   màn hình bên kia hỏi lại mỗi 15s

Script này dựng hai tài khoản thử thật, cho A giữ chỗ và B hỏi liên tục, rồi
đo bằng đồng hồ chứ không suy từ hằng số.

CHẠY TRÊN STAGING. Nó tạo bệnh nhân/lịch hẹn thử; prod đang đón bệnh nhân thật.
Cuối bài tự dọn phần mình tạo ra.

    docker cp do-giu-cho.py clinicai_staging-api-1:/tmp/
    docker exec clinicai_staging-api-1 python /tmp/do-giu-cho.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import httpx

VN = timezone(timedelta(hours=7))
API = "http://localhost:8000/api/v1"
MAT_KHAU = "ThuNghiem!" + uuid.uuid4().hex[:8]
NHAN = "[thử-giữ-chỗ]"

ket_qua: list[tuple[str, bool, str]] = []


def cung_khung(item: dict, moc: datetime) -> bool:
    """Cùng một khoảnh khắc hay không.

    KHÔNG so tiền tố chuỗi: API trả giờ UTC ("2026-09-04T03:00:00+00:00") còn
    bài đo cầm giờ VN ("2026-09-04T10:00:00+07:00"). Hai chuỗi khác nhau cho
    cùng một lúc — so chuỗi thì bài đo báo "không thấy" trong khi hệ thống
    chạy đúng, và đó là kiểu sai làm người ta đi vá thứ không hỏng.
    """
    try:
        return datetime.fromisoformat(item["slot_start"]) == moc
    except (ValueError, KeyError):
        return False


def ghi(ten: str, dat: bool, chi_tiet: str = "") -> None:
    ket_qua.append((ten, dat, chi_tiet))
    print(f"  {'✓' if dat else '✗'} {ten}" + (f" — {chi_tiet}" if chi_tiet else ""))


async def tao_tai_khoan(
    http: httpx.AsyncClient, conn: asyncpg.Connection, clinic_id: str, ten: str
) -> tuple[str, str]:
    """Một tài khoản đăng nhập thật + một nhân sự CSKH nối vào nó.

    Phải có ĐỦ CẢ HAI. Chỉ tạo tài khoản auth thì mọi request ghi trả 403 mà
    màn hình không nói được vì sao — đúng cái bẫy provision-staff-logins.sh mô
    tả: đăng nhập được nhưng không làm được gì.
    """
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    email = f"thu-giu-cho-{uuid.uuid4().hex[:10]}@clinicai.test"

    r = await http.post(
        f"{base}/auth/v1/admin/users",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        json={"email": email, "password": MAT_KHAU, "email_confirm": True},
    )
    r.raise_for_status()
    auth_user_id = r.json()["id"]

    # `primary_location_id` và `primary_department` là NOT NULL — một nhân sự
    # không thuộc cơ sở nào là thứ hệ thống không cho tồn tại. MƯỢN của một CSKH
    # đã có thật, thay vì tự tra bảng cơ sở: tài khoản thử phải giống người thật
    # ở mọi trường mà luật đọc tới, nếu không thì bài đo đo một ca không tồn tại.
    location_id = await conn.fetchval(
        """
        SELECT s.primary_location_id
          FROM public.staff s
          JOIN public.clinic_membership m ON m.staff_id = s.id
         WHERE m.clinic_id = $1::uuid AND m.role = 'CSKH' AND s.is_active
         LIMIT 1
        """,
        clinic_id,
    )
    if location_id is None:
        raise SystemExit("staging chưa có CSKH thật nào để mượn cơ sở làm việc")
    staff_id = await conn.fetchval(
        """
        INSERT INTO public.staff
            (full_name, auth_user_id, is_active, primary_location_id,
             primary_department)
        VALUES ($1, $2::uuid, TRUE, $3::uuid, 'CSKH') RETURNING id
        """,
        f"{NHAN} {ten}",
        auth_user_id,
        location_id,
    )
    # ON CONFLICT vì CHÈN `staff` ĐÃ TỰ SINH THẺ THÀNH VIÊN. Có trigger dựng
    # `clinic_membership` từ `primary_department`, nên dòng này thường là thừa —
    # nhưng vẫn viết ra để bài đo không phụ thuộc vào trigger ấy còn sống.
    await conn.execute(
        """
        INSERT INTO public.clinic_membership (clinic_id, staff_id, role, is_active)
        VALUES ($1::uuid, $2::uuid, 'CSKH', TRUE)
        ON CONFLICT (clinic_id, staff_id, role) DO UPDATE SET is_active = TRUE
        """,
        clinic_id,
        staff_id,
    )

    r = await http.post(
        f"{base}/auth/v1/token?grant_type=password",
        headers={"apikey": key, "Content-Type": "application/json"},
        json={"email": email, "password": MAT_KHAU},
    )
    r.raise_for_status()
    return r.json()["access_token"], str(staff_id)


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
        print("TỪ CHỐI: bài đo này tạo dữ liệu thử, không chạy trên prod.")
        return 2

    # `DATABASE_URL` mang tiền tố của SQLAlchemy (`postgresql+asyncpg://`);
    # asyncpg nói chuyện trực tiếp thì không hiểu cái đuôi ấy.
    conn = await asyncpg.connect(
        os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    )
    clinic_id = str(await conn.fetchval("SELECT id FROM public.clinic LIMIT 1"))
    admin = httpx.AsyncClient(timeout=30.0)

    # Khung giờ nhắm tới: 10:00 sáng của một ngày ĐỦ XA để không đụng lịch thật
    # đang có trên staging, nhưng vẫn là ngày làm việc bình thường.
    ngay = (datetime.now(VN) + timedelta(days=21)).date()
    bat_dau = datetime.combine(ngay, datetime.min.time(), tzinfo=VN).replace(hour=10)
    ket_thuc = bat_dau + timedelta(minutes=15)
    ngay_iso = ngay.isoformat()

    print(f"\nKhung giờ đem ra tranh: {bat_dau:%d/%m/%Y %H:%M}–{ket_thuc:%H:%M} (giờ VN)\n")

    try:
        tokenA, staffA = await tao_tai_khoan(admin, conn, clinic_id, "CSKH A")
        tokenB, staffB = await tao_tai_khoan(admin, conn, clinic_id, "CSKH B")
        tokenC, staffC = await tao_tai_khoan(admin, conn, clinic_id, "CSKH C")
        print(f"Ba tài khoản thử: A={staffA[:8]} B={staffB[:8]} C={staffC[:8]}\n")

        A, B, C = phien(tokenA), phien(tokenB), phien(tokenC)
        than = {
            "slot_start": bat_dau.isoformat(),
            "slot_end": ket_thuc.isoformat(),
            "doctor_id": None,
        }

        # ── 1. A giữ chỗ, B hỏi liên tục: bao lâu thì B ĐỌC được? ────────────
        print("1. A giữ chỗ — B hỏi liên tục cho tới khi thấy")
        t0 = time.perf_counter()
        r = await A.post("/appointments/slot-hold", json=than)
        t_ghi = (time.perf_counter() - t0) * 1000
        ghi("A giữ chỗ được", r.status_code in (200, 201), f"{r.status_code} · {t_ghi:.0f}ms")

        thay_luc = None
        for _ in range(200):
            g = await B.get("/appointments/slot-hold", params={"date": ngay_iso})
            items = g.json().get("items", []) if g.status_code == 200 else []
            if any(cung_khung(i, bat_dau) for i in items):
                thay_luc = (time.perf_counter() - t0) * 1000
                break
            await asyncio.sleep(0.02)
        ghi(
            "B đọc được chỗ A đang giữ",
            thay_luc is not None,
            f"{thay_luc:.0f}ms kể từ lúc A bấm" if thay_luc else "KHÔNG BAO GIỜ THẤY",
        )

        # ── 2. Tên người giữ có hiện không ───────────────────────────────────
        g = await B.get("/appointments/slot-hold", params={"date": ngay_iso})
        it = next(
            (i for i in g.json().get("items", []) if cung_khung(i, bat_dau)),
            None,
        )
        ghi(
            "B thấy TÊN người đang giữ, không phải một ô bận vô danh",
            bool(it and it.get("held_by_name") and NHAN in it["held_by_name"]),
            (it or {}).get("held_by_name", "—"),
        )

        # ── 3. A KHÔNG được thấy chỗ của chính mình ──────────────────────────
        g = await A.get("/appointments/slot-hold", params={"date": ngay_iso})
        tu_thay = [
            i for i in g.json().get("items", [])
            if cung_khung(i, bat_dau)
        ]
        ghi(
            "A KHÔNG thấy chỗ của chính mình",
            not tu_thay,
            "hiện 'đang giữ' trên ô mình vừa bấm là tự báo có người tranh chỗ",
        )

        # ── 4. Ba người cùng nhắm một khung ──────────────────────────────────
        print("\n2. Người thứ ba vào cùng khung")
        r = await C.post("/appointments/slot-hold", json=than)
        ghi("C cũng giữ được cùng khung ấy", r.status_code in (200, 201), f"{r.status_code}")
        g = await B.get("/appointments/slot-hold", params={"date": ngay_iso})
        so = len([
            i for i in g.json().get("items", [])
            if cung_khung(i, bat_dau)
        ])
        ghi(
            "B thấy CẢ HAI người đang tranh khung này",
            so == 2,
            f"{so} chỗ giữ — giữ chỗ là TƯ VẤN, không phải khoá",
        )

        # ── 5. Đổi khung thì chỗ cũ được thả ─────────────────────────────────
        print("\n3. A đổi sang khung khác")
        khac = bat_dau + timedelta(hours=1)
        await A.post(
            "/appointments/slot-hold",
            json={
                "slot_start": khac.isoformat(),
                "slot_end": (khac + timedelta(minutes=15)).isoformat(),
                "doctor_id": None,
            },
        )
        g = await B.get("/appointments/slot-hold", params={"date": ngay_iso})
        con = [
            i for i in g.json().get("items", [])
            if cung_khung(i, bat_dau)
        ]
        ghi(
            "chỗ CŨ của A được thả ngay khi A đổi khung",
            len(con) == 1,
            f"còn {len(con)} chỗ ở khung cũ (chỉ nên còn của C)",
        )

        # ── 6. Rời màn hình thì thả ──────────────────────────────────────────
        r = await A.request("DELETE", "/appointments/slot-hold")
        ghi("A rời màn hình thì chỗ được thả", r.status_code == 200, f"{r.status_code}")

        # ── 7. Hết hạn là thụ động ───────────────────────────────────────────
        print("\n4. Chỗ giữ bị bỏ quên")
        await conn.execute(
            """
            UPDATE public.slot_hold SET expires_at = now() - interval '1 second'
             WHERE held_by = $1::uuid AND released_at IS NULL
            """,
            staffC,
        )
        g = await B.get("/appointments/slot-hold", params={"date": ngay_iso})
        ghi(
            "chỗ quá hạn tự biến mất, không cần cron dọn",
            not [
                i for i in g.json().get("items", [])
                if cung_khung(i, bat_dau)
            ],
            f"tối đa {10} phút nếu người kia đóng tab mà lệnh thả không tới",
        )

        # ── 8. CHỐT CHẶN THẬT: TRANH NHAU CHỖ CUỐI CÙNG ──────────────────────
        #
        # LUẬT Ở ĐÂY KHÔNG PHẢI "mỗi khung một người". Sức chứa là ba tầng theo
        # khoảng phút, và một khung 10:00 có thể chứa nhiều lịch một cách hoàn
        # toàn hợp lệ. Hai lệnh cùng thành công ở một khung còn rộng KHÔNG phải
        # đặt trùng — đó là hai chỗ trống khác nhau.
        #
        # Chỗ duy nhất đáng đo là RANH GIỚI: lấp đầy tới còn ĐÚNG MỘT chỗ, rồi
        # cho nhiều người bấm cùng lúc vào chỗ ấy. Nếu quá một người thắng thì
        # sức chứa đã bị vượt, và đó mới là lỗi.
        print("\n5. Chốt chặn thật — nhiều người tranh CHỖ CUỐI CÙNG")

        # MƯỢN khách CÓ SẴN, không tạo khách mới. `patient` nằm trong bảy bảng
        # có chốt chống xoá cứng, nên mỗi lần chạy mà tạo khách mới là bỏ lại
        # rác không dọn được bằng lệnh xoá thường.
        benh_nhan = [
            str(r["clinic_patient_id"])
            for r in await conn.fetch(
                "SELECT clinic_patient_id FROM public.patient WHERE is_active LIMIT 12"
            )
        ]
        dich_vu = await conn.fetchrow(
            "SELECT id, code FROM public.service_type WHERE clinic_id = $1::uuid "
            "AND is_active LIMIT 1",
            clinic_id,
        )

        # PHẢI CÓ BÁC SĨ. Trigger sức chứa nói thẳng: "lịch hẹn chưa phân bác sĩ
        # → chưa chiếm ghế của ai → không kiểm". Sức chứa là ghế CỦA MỘT BÁC SĨ,
        # nên một cuộc tranh chỗ không nêu tên bác sĩ là cuộc tranh không có ghế
        # nào để tranh — bài đo bản đầu đã sai đúng chỗ này và báo nhầm là lỗi.
        bac_si = await conn.fetchval(
            """
            SELECT s.id FROM public.staff s
              JOIN public.clinic_membership m ON m.staff_id = s.id
             WHERE m.clinic_id = $1::uuid AND m.role = 'DOCTOR' AND s.is_active
             LIMIT 1
            """,
            clinic_id,
        )
        bao_gia = await B.get(
            "/appointments/quote",
            params={"date": ngay_iso, "doctor_id": str(bac_si)},
        )
        khung = None
        if bao_gia.status_code == 200:
            for k in bao_gia.json().get("slots", bao_gia.json().get("items", [])):
                if str(k.get("slot") or k.get("time") or "").startswith("10:00"):
                    khung = k
                    break
        print(f"     sức chứa khung 10:00 theo /quote: {khung}")

        # HAI LÀN ĐỘC LẬP, KHÔNG PHẢI MỘT SỐ. `/quote` trả `regular_cap` (khách
        # đặt trước) và `walkin_cap` (khách vãng lai) tách nhau, mỗi làn có mức
        # đã dùng riêng. Bài đo chỉ tranh làn đặt trước.
        suc_chua = khung.get("regular_cap") if khung else None
        da_dung = khung.get("regular_used", 0) if khung else 0
        con_trong = (suc_chua - da_dung) if isinstance(suc_chua, int) else None

        if bac_si is None or dich_vu is None or len(benh_nhan) < 3 or not con_trong:
            ghi(
                "khung thử còn chỗ trống để dựng phép thử ranh giới",
                False,
                f"sức chứa {suc_chua}, đã dùng {da_dung} — hết chỗ thì không đo được "
                "cuộc tranh chỗ cuối; dọn lịch thử cũ rồi chạy lại",
            )
        else:
            async def dat(ss: httpx.AsyncClient, cpid: str, nhan: str):
                return await ss.post(
                    "/appointments/bookings",
                    headers={"Idempotency-Key": str(uuid.uuid4())},
                    json={
                        "clinic_patient_id": cpid,
                        "service_type_id": str(dich_vu["id"]),
                        "slot_start": bat_dau.isoformat(),
                        "slot_end": ket_thuc.isoformat(),
                        "doctor_id": str(bac_si),
                        "notes": f"{NHAN} {nhan}",
                    },
                )

            # Lấp đầy tới khi CHỈ CÒN MỘT chỗ, từng lệnh một.
            da_dat = 0
            for i in range(min(con_trong - 1, len(benh_nhan) - 3)):
                r = await dat(B, benh_nhan[i], f"thu-lap-{i}")
                if r.status_code < 300:
                    da_dat += 1
                else:
                    break
            print(f"     lấp {da_dat}/{con_trong - 1} chỗ trước khi tranh "
                  f"(sức chứa {suc_chua}, đã dùng sẵn {da_dung})")
            ghi(
                "lấp đầy được tới sát ranh giới",
                da_dat == con_trong - 1,
                f"đặt thêm {da_dat}, còn đúng 1 chỗ",
            )

            # BA người bấm cùng lúc vào chỗ cuối. Ba chứ không phải hai: một
            # cuộc đua hai bên có thể tình cờ tuần tự hoá và trông như đã an
            # toàn.
            con = benh_nhan[da_dat : da_dat + 3]
            ra = await asyncio.gather(
                *[dat(s, cp, f"thu-tranh-{n}") for s, cp, n in zip((A, B, C), con, "ABC")],
                return_exceptions=True,
            )
            ma = [
                x.status_code if isinstance(x, httpx.Response) else repr(x)[:60]
                for x in ra
            ]
            thanh_cong = sum(
                1 for x in ra if isinstance(x, httpx.Response) and x.status_code < 300
            )
            print(f"     ba lệnh đặt đồng thời vào chỗ cuối → {ma}")
            ghi(
                "CHỈ MỘT người lấy được chỗ cuối",
                thanh_cong == 1,
                f"{thanh_cong}/3 lệnh thành công (sức chứa {suc_chua})",
            )
            for x in ra:
                if isinstance(x, httpx.Response) and x.status_code >= 400:
                    than_loi = x.json()
                    loi = str(
                        than_loi.get("message") or than_loi.get("detail") or than_loi
                    )[:150]
                    ghi(
                        "người thua ĐỌC ĐƯỢC vì sao mình thua, không phải lỗi 500",
                        x.status_code != 500 and "Internal" not in loi,
                        f"{x.status_code}: {loi}",
                    )
                    break

            # LỊCH KHÔNG CHỌN BÁC SĨ THÌ KHÔNG BỊ CHẶN — cố ý, và cần nói ra.
            # Ghế được kiểm lúc XẾP bác sĩ, không phải lúc đặt. Nghĩa là màn
            # hình có thể nhận nhiều lịch "chờ xếp bác sĩ" hơn số ghế thật, và
            # chỗ vỡ ra là bước xếp — không phải bước đặt.
            r_khong_bs = await B.post(
                "/appointments/bookings",
                headers={"Idempotency-Key": str(uuid.uuid4())},
                json={
                    "clinic_patient_id": benh_nhan[-1],
                    "service_type_id": str(dich_vu["id"]),
                    "slot_start": bat_dau.isoformat(),
                    "slot_end": ket_thuc.isoformat(),
                    "notes": f"{NHAN} khong-bac-si",
                },
            )
            ghi(
                "lịch CHƯA phân bác sĩ vẫn nhận, dù ghế bác sĩ đã đầy",
                r_khong_bs.status_code < 300,
                f"{r_khong_bs.status_code} — cố ý: ghế chỉ được kiểm lúc XẾP bác sĩ",
            )

            # Kiểm bằng ĐẾM THẬT, không tin mã trả về: sức chứa có bị vượt không.
            thuc_te = await conn.fetchval(
                """
                SELECT count(*) FROM public.appointment
                 WHERE clinic_id = $1::uuid AND slot_start = $2
                   AND doctor_id = $3::uuid
                   AND status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED')
                """,
                clinic_id,
                bat_dau,
                bac_si,
            )
            ghi(
                "đếm trong database: KHÔNG vượt sức chứa",
                thuc_te <= suc_chua,
                f"{thuc_te} lịch sống ở khung này, sức chứa {suc_chua}",
            )

    finally:
        # DỌN NGAY, KHÔNG ĐỂ LẠI CHO AI. Bài đo tự tạo ba nhân sự và ba tài
        # khoản đăng nhập; để chúng lại thì lần sau danh sách nhân sự trên
        # staging có người lạ, và tài khoản còn đăng nhập được.
        #
        print("\nDọn dữ liệu thử…")
        # LỊCH HẸN KHÔNG XOÁ ĐƯỢC — `appointment` có chốt chống xoá cứng. Huỷ
        # bằng ĐỔI TRẠNG THÁI, đúng cách phòng khám huỷ một lịch thật. Nhận diện
        # bằng ghi chú do chính bài đo đặt, KHÔNG bằng khung giờ: nhỡ có ai đặt
        # thật vào đúng khung ấy thì không được đụng vào.
        #
        # `ly_do_huy_ma` BẮT BUỘC: có CHECK "huỷ phải có lý do" trên bảng. Một
        # lịch biến mất khỏi màn hình mà không ai biết vì sao là thứ hệ thống
        # cố ý không cho tồn tại — kể cả với lịch của bài đo.
        huy = await conn.fetch(
            """
            UPDATE public.appointment
               SET status = 'CANCELLED', ly_do_huy_ma = 'KHAC',
                   cancellation_reason = 'dọn lịch của bài đo giữ chỗ'
             WHERE clinic_id = $1::uuid AND notes LIKE $2
               AND status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED')
            RETURNING id
            """,
            clinic_id,
            f"{NHAN}%",
        )
        print(f"  huỷ {len(huy)} lịch thử (không xoá cứng được — bảng có chốt)")
        ids = [r["id"] for r in await conn.fetch(
            "SELECT id, auth_user_id FROM public.staff WHERE full_name LIKE $1",
            f"{NHAN}%",
        )]
        auth_ids = [r["auth_user_id"] for r in await conn.fetch(
            "SELECT auth_user_id FROM public.staff WHERE full_name LIKE $1",
            f"{NHAN}%",
        )]
        await conn.execute("DELETE FROM public.slot_hold WHERE held_by = ANY($1::uuid[])", ids)
        await conn.execute(
            "DELETE FROM public.clinic_membership WHERE staff_id = ANY($1::uuid[])", ids
        )
        await conn.execute("DELETE FROM public.staff WHERE id = ANY($1::uuid[])", ids)
        base = os.environ["SUPABASE_URL"].rstrip("/")
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        for aid in auth_ids:
            if aid:
                await admin.delete(
                    f"{base}/auth/v1/admin/users/{aid}",
                    headers={"apikey": key, "Authorization": f"Bearer {key}"},
                )
        con_lai = await conn.fetchval(
            "SELECT count(*) FROM public.staff WHERE full_name LIKE $1", f"{NHAN}%"
        )
        print(f"  xoá {len(ids)} nhân sự thử + {len(auth_ids)} tài khoản; còn lại {con_lai}")
        await conn.close()
        await admin.aclose()

    dat = sum(1 for _, ok, _ in ket_qua if ok)
    print(f"\n{dat}/{len(ket_qua)} mục đạt")
    return 0 if dat == len(ket_qua) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
