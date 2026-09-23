"""PHA A — ba CSKH nghe điện thoại, đặt lịch CÙNG LÚC. Mục tiêu: tìm lỗ hổng.

Mỗi "cuộc gọi" làm đúng như CSKH ngoài đời: tra khách theo số điện thoại →
chưa có thì tạo → xem khung còn chỗ → GIỮ CHỖ (để CSKH khác thấy) → đặt lịch →
thả giữ chỗ. Ba CSKH chạy ba luồng song song.

Các phép thử cố ý:
  A1  ba CSKH cùng lao vào CHỖ CUỐI của một khung → đúng 1 người được.
  A2  CSKH-1 đang giữ chỗ → CSKH-2 có THẤY không (tên người giữ, khung nào)?
  A3  hai CSKH cùng tạo MỘT khách (cùng số) cùng lúc → có ra hai hồ sơ trùng?
  A4  cùng một khách bị đặt HAI lịch trùng giờ bởi hai CSKH.
  A5  đặt lịch TUẦN SAU khi chưa có lịch trực (đặt tự do) → Quản lý công bố
      lịch trực tuần sau mà bác sĩ nghỉ đúng ngày ấy → lịch đã đặt đi đâu, ai
      được báo? Đặt tiếp vào ngày bác sĩ nghỉ sau khi công bố → phải bị chặn.
  A6  khung đã quá giờ / giờ nghỉ trưa / ngoài ca → phải bị chặn, câu báo rõ.
"""

from __future__ import annotations

import datetime as dt
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import buoc as b
from do_luong import NhatKyThaoTac
from ket_noi import LoiApi, sql

HO = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Đặng", "Bùi", "Đỗ", "Ngô"]
DEM = ["Thị", "Ngọc", "Thu", "Minh", "Thanh", "Hồng", "Mai", "Kim"]
TEN = ["Lan", "Hoa", "Hương", "Trang", "Linh", "Nga", "Yến", "Thảo", "Vy", "Hà", "Châu", "My"]


def ten_ngau_nhien() -> str:
    return f"{random.choice(HO)} {random.choice(DEM)} {random.choice(TEN)} MP"


def so_dt() -> str:
    return f"09{random.randint(10**7, 10**8 - 1)}"


def dv_id(ma: str) -> str:
    return b.id_mot(f"select id from service_type where code='{ma}' and is_active")


def khung(ngay: dt.date, gio: int, phut: int) -> tuple[str, str]:
    s = dt.datetime.combine(ngay, dt.time(gio, phut), tzinfo=b.VN)
    return s.isoformat(), (s + dt.timedelta(minutes=15)).isoformat()


def dat(cskh: str, pid: str, ngay: dt.date, gio: int, phut: int, *, bac_si: str,
        dich_vu: str = "PHU_KHOA", kenh: str = "HOTLINE", loai_khach: str | None = None) -> dict[str, Any]:
    s, e = khung(ngay, gio, phut)
    than: dict[str, Any] = {
        "clinic_patient_id": pid, "service_type_id": dv_id(dich_vu), "location_id": b.KIM_NGUU,
        "slot_start": s, "slot_end": e, "doctor_id": bac_si, "booking_channel": kenh}
    if loai_khach:
        than["patient_kind"] = loai_khach  # CSKH đánh dấu "khách tái khám" khi đặt
    return dict(b.ai(cskh).post("/appointments/bookings", than))


def khung_trong(ngay: dt.date, bac_si: str, *, tu: int = 17 * 60 + 30, den: int = 21 * 60) -> tuple[int, int]:
    """Khung 15' còn TRỐNG HẲN (0 lịch) của bác sĩ — để phép thử không đụng lịch A0."""
    for m in range(tu, den, 15):
        gio, phut = divmod(m, 60)
        bd = khung(ngay, gio, phut)[0]
        n = int(sql(f"select count(*) from appointment where doctor_id='{bac_si}'"
                    f" and slot_start='{bd}' and status not in ('CANCELLED','NO_SHOW')")[0][0])
        if n == 0:
            return gio, phut
    raise RuntimeError("không còn khung trống cho phép thử")


def tra_hoac_tao(cskh: str, ten: str, dt_: str) -> str:
    """Như CSKH: tra theo số trước; có rồi thì dùng, chưa có thì tạo."""
    co = b.ai(cskh).get(f"/patients?phone={dt_}")
    if co:
        return str(co[0]["clinic_patient_id"])
    p = b.ai(cskh).post("/patients", {"full_name": ten, "location_id": b.KIM_NGUU,
                                      "phone_primary": dt_, "gender": "F",
                                      "birth_year": random.randint(1978, 2002)})
    if p.get("duplicate"):
        return str(p["matches"][0]["clinic_patient_id"])
    return str(p["clinic_patient_id"])


def cuoc_goi(nk: NhatKyThaoTac, cskh: str, khach: dict[str, Any], ngay: dt.date,
             bac_si: str) -> str | None:
    """Một cuộc gọi trọn vẹn; thử khung kế tiếp khi khung đầy (như CSKH)."""
    pid = nk.lam(cskh, "đặt lịch", f"tra/tạo khách {khach['ten']}",
                 lambda: tra_hoac_tao(cskh, khach["ten"], khach["sdt"]), khach=khach["ten"])
    if not pid:
        return None
    khach["pid"] = pid
    bay_gio = dt.datetime.now(b.VN)
    goc = max(8 * 60, bay_gio.hour * 60 + bay_gio.minute + 20) if ngay == bay_gio.date() else 8 * 60
    for lan in range(40):
        gio, phut = divmod(goc - goc % 15 + khach["phut"] + 15 * lan, 60)
        if gio == 13 or gio >= 21:  # nghỉ trưa / hết ca
            continue
        s, e = khung(ngay, gio, phut)
        nk.lam(cskh, "giữ chỗ", f"giữ khung {gio:02d}:{phut:02d} cho {khach['ten']}",
               lambda s=s, e=e: b.ai(cskh).post("/appointments/slot-hold", {
                   "slot_start": s, "slot_end": e, "doctor_id": bac_si, "clinic_patient_id": pid}))
        try:
            r = dat(cskh, pid, ngay, gio, phut, bac_si=bac_si, dich_vu=khach.get("dv", "PHU_KHOA"),
                    loai_khach="RETURN" if khach.get("loai") == "QUEN" else None)
        except LoiApi as err:
            if err.ma in (409, 422):
                continue
            nk.lam(cskh, "đặt lịch", f"đặt {khach['ten']}", lambda err=err: (_ for _ in ()).throw(err))
            return None
        finally:
            try:
                b.ai(cskh).goi("DELETE", "/appointments/slot-hold")
            except LoiApi:
                pass
        nk.lam(cskh, "đặt lịch", f"đặt {khach['ten']} {gio:02d}:{phut:02d}", lambda r=r: r, khach=khach["ten"])
        khach["aid"] = r["appointment_id"]
        khach["gio"] = f"{gio:02d}:{phut:02d}"
        return str(r["appointment_id"])
    return None


def chay(nk: NhatKyThaoTac, nhan_su: dict[str, str], khach_hom_nay: list[dict[str, Any]]) -> dict[str, Any]:
    ket: dict[str, Any] = {}
    hom_nay = dt.datetime.now(b.VN).date()
    bs_a = nhan_su["bs.a"]
    cskh = ["cskh", "cskh2", "cskh3"]

    # ── Bão cuộc gọi: 3 CSKH song song đặt lịch hôm nay ─────────────────
    print("\n▶ A0 — 3 CSKH đặt lịch song song cho khách hôm nay", flush=True)
    with ThreadPoolExecutor(3) as ex:
        list(ex.map(lambda i_k: cuoc_goi(nk, cskh[i_k[0] % 3], i_k[1], hom_nay, bs_a),
                    enumerate(khach_hom_nay)))

    # ── A1: ba CSKH cùng lao vào chỗ cuối ────────────────────────────────
    g1, p1 = khung_trong(hom_nay, bs_a)
    print(f"\n▶ A1 — 3 CSKH cùng đặt CHỖ CUỐI của khung {g1:02d}:{p1:02d}", flush=True)
    ba = [tra_hoac_tao("cskh", ten_ngau_nhien(), so_dt()) for _ in range(4)]
    nk.lam("cskh", "A1", "lấp trước 1 chỗ (còn 1 chỗ đặt hẹn)",
           lambda: dat("cskh", ba[0], hom_nay, g1, p1, bac_si=bs_a))
    rao = threading.Barrier(3)
    kq: list[str] = []

    def lao(i: int) -> None:
        rao.wait()
        try:
            dat(cskh[i], ba[i + 1], hom_nay, g1, p1, bac_si=bs_a)
            kq.append("OK")
        except LoiApi as e:
            kq.append(f"{e.ma}")

    with ThreadPoolExecutor(3) as ex:
        list(ex.map(lao, range(3)))
    so_lich = int(sql("select count(*) from appointment a where a.doctor_id='" + bs_a + "'"
                      f" and a.slot_start = '{khung(hom_nay, g1, p1)[0]}'"
                      " and a.status not in ('CANCELLED','NO_SHOW')")[0][0])
    ket["A1"] = {"ket_qua_3_nguoi": sorted(kq), "so_lich_trong_khung": so_lich, "tran": 2}
    nk.lam("he-thong", "A1", f"khung {g1:02d}:{p1:02d} không vượt trần 2 chỗ đặt hẹn",
           lambda: so_lich <= 2 or (_ for _ in ()).throw(AssertionError(f"{so_lich} lịch > trần 2 — {kq}")))
    nk.lam("he-thong", "A1", "đúng 1 trong 3 CSKH đặt được chỗ cuối",
           lambda: kq.count("OK") == 1 or (_ for _ in ()).throw(AssertionError(str(kq))))

    # ── A2: giữ chỗ có hiện cho người khác không ──────────────────────────
    print("\n▶ A2 — CSKH-2 có thấy CSKH-1 đang giữ khung không", flush=True)
    s, e = khung(hom_nay, 19, 30)
    nk.lam("cskh", "A2", "CSKH-1 giữ khung 19:30", lambda: b.ai("cskh").post(
        "/appointments/slot-hold", {"slot_start": s, "slot_end": e, "doctor_id": bs_a}))
    thay = b.ai("cskh2").get(f"/appointments/slot-hold?date={hom_nay.isoformat()}")
    ket["A2_cskh2_thay"] = thay
    moc = dt.datetime.fromisoformat(s)
    nk.lam("cskh2", "A2", "CSKH-2 THẤY khung 19:30 đang được giữ (kèm ai giữ)", lambda: any(
        dt.datetime.fromisoformat(str(h.get("slot_start"))) == moc and h.get("held_by_name")
        for h in thay.get("items", []))
        or (_ for _ in ()).throw(AssertionError(f"không thấy: {thay}")))
    nk.lam("cskh", "A2", "CSKH-1 thả giữ chỗ", lambda: b.ai("cskh").goi("DELETE", "/appointments/slot-hold"))

    # ── A3: hai CSKH cùng tạo một khách ───────────────────────────────────
    print("\n▶ A3 — 2 CSKH cùng tạo MỘT khách (cùng số) cùng lúc", flush=True)
    sdt, ten = so_dt(), ten_ngau_nhien()
    rao2 = threading.Barrier(2)

    def tao(u: str) -> Any:
        rao2.wait()
        return b.ai(u).post("/patients", {"full_name": ten, "location_id": b.KIM_NGUU,
                                          "phone_primary": sdt, "gender": "F", "birth_year": 1991})

    with ThreadPoolExecutor(2) as ex:
        list(ex.map(lambda u: nk.lam(u, "A3", f"tạo khách {ten} {sdt}", lambda u=u: tao(u)), ["cskh", "cskh2"]))
    so_ho_so = int(sql(f"select count(*) from patient where phone_primary='{sdt}'")[0][0])
    ket["A3_so_ho_so"] = so_ho_so
    nk.lam("he-thong", "A3", "tạo đồng thời không ra HAI hồ sơ trùng",
           lambda: so_ho_so == 1 or (_ for _ in ()).throw(AssertionError(f"{so_ho_so} hồ sơ cùng số {sdt}")))

    # ── A4: cùng khách hai lịch trùng giờ ────────────────────────────────
    print("\n▶ A4 — cùng một khách, hai CSKH đặt hai lịch trùng giờ", flush=True)
    pid = tra_hoac_tao("cskh3", ten_ngau_nhien(), so_dt())
    g4, p4 = khung_trong(hom_nay, bs_a)
    nk.lam("cskh3", "A4", f"CSKH-3 đặt {g4:02d}:{p4:02d}", lambda: dat("cskh3", pid, hom_nay, g4, p4, bac_si=bs_a))
    nk.lam("cskh", "A4", f"CSKH-1 đặt TRÙNG khách đó {g4:02d}:{p4:02d} → phải bị chặn / cảnh báo",
           lambda: dat("cskh", pid, hom_nay, g4, p4, bac_si=bs_a), mong_loi=(409, 422))

    # ── A5: tuần sau chưa có lịch trực ────────────────────────────────────
    print("\n▶ A5 — đặt tuần sau khi CHƯA có lịch trực, rồi công bố lịch có bác sĩ nghỉ", flush=True)
    tuan_sau = hom_nay + dt.timedelta(days=7 - hom_nay.weekday())  # thứ Hai tuần sau
    thu5 = tuan_sau + dt.timedelta(days=3)
    lich_tu_do = []
    for i in range(3):
        p = tra_hoac_tao("cskh2", ten_ngau_nhien(), so_dt())
        r = nk.lam("cskh2", "A5", f"đặt Thứ 5 tuần sau {9 + i}:00 (chưa có lịch trực)",
                   lambda p=p, i=i: dat("cskh2", p, thu5, 9 + i, 0, bac_si=bs_a))
        if r:
            lich_tu_do.append(r["appointment_id"])
    ql = b.ai("ql")
    # Quản lý xếp lịch tuần sau: BS chính làm mọi ngày TRỪ thứ Năm.
    tram_bs = sql("select code from vi_tri_lam_viec where ten='T1 BS chính' and is_active limit 1")[0][0]
    for d in range(6):
        ngay = tuan_sau + dt.timedelta(days=d)
        if ngay == thu5:
            continue
        nk.lam("ql", "A5", f"xếp BS chính {ngay:%d/%m}", lambda ngay=ngay: ql.post(
            "/roster/shifts", {"work_date": ngay.isoformat(), "station": tram_bs, "shift": "FULL", "staff_id": bs_a}))
    nk.lam("ql", "A5", "công bố lịch trực tuần sau (BS chính NGHỈ thứ Năm)",
           lambda: ql.post("/roster/weeks/apply", {"week_start": tuan_sau.isoformat()}))
    cho = nk.lam("ql", "A5", "màn 'chờ xếp bác sĩ' thấy 3 lịch thứ Năm mất bác sĩ",
                 lambda: ql.get("/appointments/cho-xep-bac-si"))
    ids_cho = {x.get("id") or x.get("appointment_id") for x in (cho or {}).get("items", [])}
    ket["A5_cho_xep"] = sorted(i for i in ids_cho if i)
    nk.lam("he-thong", "A5", "cả 3 lịch đặt tự do nằm trong 'chờ xếp bác sĩ' (MAT_BAC_SI)",
           lambda: set(lich_tu_do) <= ids_cho or (_ for _ in ()).throw(
               AssertionError(f"thiếu {set(lich_tu_do) - ids_cho}")))
    thong_bao = b.ai("cskh").get("/thong-bao")
    ket["A5_chuong_cskh"] = [t.get("tieu_de") or t.get("noi_dung") for t in (thong_bao.get("items") or thong_bao if isinstance(thong_bao, list) else thong_bao.get("items", []))][:10] if thong_bao else []
    p = tra_hoac_tao("cskh3", ten_ngau_nhien(), so_dt())
    nk.lam("cskh3", "A5", "đặt BS chính thứ Năm SAU khi công bố (bác sĩ nghỉ) → phải bị chặn",
           lambda: dat("cskh3", p, thu5, 14, 0, bac_si=bs_a), mong_loi=(409, 422))

    # ── A6: khung vô lý ──────────────────────────────────────────────────
    print("\n▶ A6 — khung vô lý phải bị chặn, câu báo rõ", flush=True)
    p = tra_hoac_tao("cskh", ten_ngau_nhien(), so_dt())
    hom_qua = hom_nay - dt.timedelta(days=1)
    nk.lam("cskh", "A6", "đặt vào HÔM QUA", lambda: dat("cskh", p, hom_qua, 10, 0, bac_si=bs_a), mong_loi=(409, 422))
    nk.lam("cskh", "A6", "đặt giờ nghỉ trưa 13:15", lambda: dat("cskh", p, hom_nay, 13, 15, bac_si=bs_a), mong_loi=(409, 422))
    nk.lam("cskh", "A6", "đặt 23:00 (ngoài ca)", lambda: dat("cskh", p, hom_nay, 23, 0, bac_si=bs_a), mong_loi=(409, 422))
    nk.lam("cskh", "A6", "slot_end TRƯỚC slot_start", lambda: b.ai("cskh").post("/appointments/bookings", {
        "clinic_patient_id": p, "service_type_id": dv_id("PHU_KHOA"), "location_id": b.KIM_NGUU,
        "slot_start": khung(hom_nay, 10, 30)[0], "slot_end": khung(hom_nay, 10, 0)[0], "doctor_id": bs_a}),
        mong_loi=(409, 422))
    nk.lam("cskh", "A6", "mã khách rác", lambda: b.ai("cskh").post("/appointments/bookings", {
        "clinic_patient_id": "khong-phai-uuid", "service_type_id": dv_id("PHU_KHOA"),
        "slot_start": khung(hom_nay, 10, 30)[0], "slot_end": khung(hom_nay, 10, 45)[0]}), mong_loi=422)
    return ket
