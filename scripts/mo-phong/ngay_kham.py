"""MỘT BUỔI KHÁM GIẢ LẬP — phòng khám 3 tầng, nhiều người làm cùng lúc.

    scripts/dev-up.sh --reset                 # bắt đầu từ trạng thái sạch
    .venv/bin/python scripts/mo-phong/ngay_kham.py

Trình tự: Quản lý dựng phòng khám → PHA A (3 CSKH đặt lịch cùng lúc) → PHA B
(khách đến so le, nhiều người làm song song) → PHA PHÁ (cố tình sai / tranh
nhau / vượt quyền) → kiểm cuối. Suốt buổi, một luồng nền nhìn 16 màn vận hành.
Báo cáo: `.dev-logs/ngay-kham-<giờ>.md` (+ .json).
"""

from __future__ import annotations

import datetime as dt
import json
import random
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

import buoc as b  # noqa: E402
import dung_phong_kham as dpk  # noqa: E402
import pha_dat_lich as pa  # noqa: E402
import pha_kham as pk  # noqa: E402
import pha_pha as pp  # noqa: E402
from do_luong import NhatKyThaoTac, SoGoi, giao_tin_sau, moc_seq, su_kien_sau  # noqa: E402
from ket_noi import REPO, ghi_sql, kiem_chi_local, sql  # noqa: E402
from theo_doi import TheoDoi  # noqa: E402

TRANG_THAI_KEYS = ("trang_thai", "status", "dich", "vong", "nhom", "dang_o", "exec_status",
                   "dispense_status", "lam_trang_thai", "can_close")


def rut_chung(data: Any) -> dict[str, str]:
    """Khách có mặt trên màn: mọi object mang visit_id (hoặc clinic_patient_id)."""
    ra: dict[str, str] = {}

    def di(x: Any) -> None:
        if isinstance(x, dict):
            k = None
            if x.get("visit_id"):
                k = f"v:{x['visit_id']}"
            elif x.get("clinic_patient_id"):
                k = f"p:{x['clinic_patient_id']}"
            if k:
                mo_ta = ",".join(f"{t}={x[t]}" for t in TRANG_THAI_KEYS if x.get(t) not in (None, "", [], {}))
                ra[k] = (ra.get(k, "") + ";" + mo_ta).strip(";")[:200] if k in ra else mo_ta[:200]
            for v in x.values():
                di(v)
        elif isinstance(x, list):
            for v in x:
                di(v)

    di(data)
    return ra


def rut_chuong(data: Any) -> dict[str, str]:
    items = data.get("items", []) if isinstance(data, dict) else data
    return {f"tb:{t.get('id')}": (t.get("tieu_de") or "")[:120] for t in items or []}


def gan_man(td: TheoDoi, phong: dict[str, str]) -> None:
    hom_nay = dt.datetime.now(b.VN).date().isoformat()
    them = td.them
    them("Lễ tân · hàng tiếp nhận", b.ai("letan"), f"/queue?date={hom_nay}", rut_chung)
    them("Lễ tân · bảng lượt khám", b.ai("letan"), "/luot-kham/bang", rut_chung)
    them("Lễ tân · check-out", b.ai("letan"), "/reception/checkout", rut_chung)
    them("Lễ tân · bảng thu tiền", b.ai("letan"), "/cashier/board?modes=dich_vu,thuoc", rut_chung)
    them("BS tư vấn · hàng tư vấn", b.ai("bs.tuvan"), "/luot-kham/hang-cho?tu_van=true", rut_chung)
    them("BS chính · danh sách khám", b.ai("bs.a"), "/luot-kham/hang-cho", rut_chung)
    them("BS chính · chờ quyết", b.ai("bs.a"), "/luot-kham/cho-quyet", rut_chung)
    for ma, ai_xem in (("sa1", "bs.sa"), ("sa2", "bs.sa2"), ("tt1", "bs.tt1"), ("tt2", "bs.tt2")):
        if ma in phong:
            them(f"Phòng {ma.upper()} · hàng chờ", b.ai(ai_xem), f"/luot-kham/hang-cho?phong={phong[ma]}", rut_chung)
    them("Kho thuốc · hàng giao", b.ai("duocsi"), "/pharmacy/queue", rut_chung)
    them("Đối tác · việc", b.ai("doitac"), "/doi-tac/viec", rut_chung)
    them("Quản lý · chỉ định hôm nay", b.ai("ql"), "/luot-kham/chi-dinh-hom-nay", rut_chung)
    them("Quản lý · hành trình", b.ai("ql"), "/hanh-trinh/hom-nay", rut_chung)
    for ai_xem in ("letan", "cskh", "bs.a", "ql"):
        them(f"Chuông · {ai_xem}", b.ai(ai_xem), "/thong-bao", rut_chuong)


def main() -> int:
    kiem_chi_local()
    random.seed(20260924)
    bat_dau = dt.datetime.now(dt.timezone.utc)
    seq0 = moc_seq()
    nk = NhatKyThaoTac()
    so_goi = SoGoi()
    ket: dict[str, Any] = {"bat_dau": bat_dau.isoformat()}

    print("▶ Quản lý dựng phòng khám 3 tầng", flush=True)
    cfg = dpk.dung(nk)
    ket["cau_hinh"] = cfg
    ns = cfg["nhan_su"]
    ph = cfg["phong"]
    pk.PHONG_NGUOI.update({
        ph["sa1"]: ("bs.sa", "dd.sa"), ph["sa2"]: ("bs.sa2", "dd.sa2"),
        ph["tt1"]: ("bs.tt1", "dd.tt1"), ph["tt2"]: ("bs.tt2", "dd.tt2"),
    })
    ca_cu = b.ai("ql").get("/ca-lam-viec")
    ca_cu = ca_cu.get("ca_lam_viec", ca_cu)
    CLINIC = sql(f"select clinic_id from clinic_location where id='{b.KIM_NGUU}'")[0][0]
    gio_cu = sql(f"select settings->'hours' from clinic where id='{CLINIC}'")[0][0]
    # Buổi giả lập chạy lúc sáng sớm → phải mở cửa sớm. Giờ mở cửa KHÔNG có
    # API/màn nào sửa (chỉ migration) → ghi thẳng DB, và đó là một PHÁT HIỆN.
    ghi_sql(
        "update clinic set settings = jsonb_set(settings, '{hours}', (select"
        " jsonb_object_agg(k, jsonb_build_object('open','04:00','close','22:00'))"
        f" from jsonb_object_keys(settings->'hours') k)) where id='{CLINIC}'",
        ly_do="giờ mở cửa 04:00 — không có API sửa clinic.settings.hours",
    )
    ca_moi = {**ca_cu, "SANG": {"bat_dau": "04:00", "ket_thuc": "13:00"}}
    nk.lam("ql", "cấu hình", "mở ca sáng từ 04:00 (buổi khám giả lập chạy lúc sáng sớm)",
           lambda: b.ai("ql").goi("PATCH", "/ca-lam-viec", json={"ca_lam_viec": ca_moi}))
    nk.lam("ql", "cấu hình", "dây H8: nhắc check-out sau 1 phút (để thử hẹn giờ)",
           lambda: b.ai("ql").goi("PATCH", "/day-noi/day", json={"ma": "h8_nhac_check_out_phut", "gia_tri": 1}))

    td = TheoDoi(chu_ky=2.0)
    gan_man(td, ph)
    td.bat_dau()

    # ── PHA A ─────────────────────────────────────────────────────────────
    loai = ["MOI"] * 7 + ["QUEN"] * 2 + ["VE_SOM", "KHONG_DEN"]
    khach_goi = [{"ten": pa.ten_ngau_nhien(), "sdt": pa.so_dt(), "phut": 30 * i, "loai": l}
                 for i, l in enumerate(loai)]
    ket["pha_a"] = pa.chay(nk, ns, khach_goi)

    # ── PHA E — một khách đi CHẬM, đo sự kiện từng bước ────────────────
    print("\n▶ PHA E — một khách đi từng bước một, đo thao tác nào phát sự kiện nào", flush=True)
    e1 = pk.Khach("E1", "MOI", "Đo Sự Kiện E1 MP")
    e1.pid = b.tao_khach(e1.ten)
    e1.aid = b.dat_lich(e1.pid, phut=720, bac_si="bs.a")
    nk.tuan_tu = True
    try:
        pk.chuyen_moi(nk, e1, [pk.SA, pk.SOI_CTC], co_thuoc=True, thu_ky=True)
    finally:
        nk.tuan_tu = False
    ket["ban_do_su_kien"] = [{"thao_tac": t.ten, "ai": t.ai, "kq": t.kq, "su_kien": t.su_kien}
                              for t in nk.ds if t.khach == "E1"]

    # ── PHA B ─────────────────────────────────────────────────────────────
    print("\n▶ PHA B — buổi khám: khách đến so le, nhiều người làm cùng lúc", flush=True)
    khach: list[pk.Khach] = []
    dv_theo_khach = [[pk.SA], [pk.SA, pk.SOI_CTC], [pk.THAO_VONG], [pk.SA], [], [pk.SA, pk.THAO_VONG], [pk.SOI_CTC]]
    i_moi = 0
    for i, g in enumerate(khach_goi):
        if not g.get("aid"):
            continue
        k = pk.Khach(f"B{i + 1:02d}", g["loai"], g["ten"], pid=g.get("pid"), aid=g.get("aid"))
        if g["loai"] == "MOI":
            k.chi_dinh_ke_hoach = dv_theo_khach[i_moi % len(dv_theo_khach)]  # type: ignore[attr-defined]
            i_moi += 1
        khach.append(k)
    for j in range(2):
        khach.append(pk.Khach(f"VL{j + 1}", "VANG_LAI", pa.ten_ngau_nhien()))

    def song(k: pk.Khach, tre: float) -> None:
        time.sleep(tre)
        try:
            if k.loai == "MOI":
                pk.chuyen_moi(nk, k, getattr(k, "chi_dinh_ke_hoach", []), co_thuoc=k.ma[-1] in "13579",
                              thu_ky=k.ma.endswith("2"))
            elif k.loai == "QUEN":
                pk.chuyen_quen(nk, k)
            elif k.loai == "VE_SOM":
                pk.chuyen_ve_som(nk, k)
            elif k.loai == "KHONG_DEN":
                pk.chuyen_khong_den(nk, k)
            elif k.loai == "VANG_LAI":
                pk.vang_lai(nk, k, ns["bs.a"])
                if k.vid:
                    pk.do_sinh_hieu(nk, k)
                    pk.tu_van(nk, k)
                    if pk.bs_chinh_kham(nk, k, [pk.SA]):
                        pk.le_tan_thu(nk, k)
                        for oid in k.chi_dinh:
                            pk.lam_dich_vu(nk, k, oid)
                        pk.doc_ket_qua(nk, k)
                        pk.thuoc_va_ve(nk, k, co_thuoc=False)
        except Exception as e:  # noqa: BLE001
            nk.lam("he-thong", "kịch bản", f"{k.ma} câu chuyện dừng giữa chừng",
                   lambda e=e: (_ for _ in ()).throw(e), khach=k.ma)

    t_b = time.time()
    with ThreadPoolExecutor(len(khach)) as ex:
        list(ex.map(lambda ik: song(ik[1], ik[0] * 4.0), enumerate(khach)))
    ket["pha_b_giay"] = round(time.time() - t_b, 1)
    ket["khach"] = [{"ma": k.ma, "loai": k.loai, "vid": k.vid, "xong": k.xong, "ghi_chu": k.ghi_chu,
                     "moc": {m: round(t - k.moc.get("den", t), 1) for m, t in k.moc.items()}} for k in khach]

    # ── PHA PHÁ ────────────────────────────────────────────────────────────
    ket["pha_pha"] = pp.chay(nk, ns)
    cho_nhac = next((k for k in khach if k.loai == "MOI" and k.vid and not k.xong), None)
    if cho_nhac is None:
        k9 = pp._khach_moi(nk, "P9", "bs.a", 700)
        if k9.vid:
            pk.do_sinh_hieu(nk, k9)
            pk.tu_van(nk, k9)
            pk.bs_chinh_kham(nk, k9, [])
            nk.lam("letan", "P9", "thu tiền khám, KHÔNG check-out", lambda: b.thu(k9.vid, "dich_vu", "letan"), khach="P9")
            cho_nhac = k9
    if cho_nhac:
        pp.nhac_check_out(nk, cho_nhac)

    # P10 — khách E1 đã khám xong với BS chính, CSKH đặt lại (KHÔNG đánh dấu tái
    # khám). Định nghĩa "khách quen" gồm cả "từng được BS ấy khám" → phải vào thẳng.
    print("\n▶ P10 — khách vừa khám xong với BS chính quay lại (không đánh dấu tái khám)", flush=True)
    if e1.xong and e1.pid:
        k10 = pk.Khach("P10", "QUEN", e1.ten, pid=e1.pid)
        k10.aid = nk.lam("cskh", "P10", "đặt lại khách E1 (không đánh dấu tái khám)",
                         lambda: b.dat_lich(e1.pid, phut=740, bac_si="bs.a"), khach="P10")
        if k10.aid:
            pk.den_va_check_in(nk, k10)
            time.sleep(3)
            if k10.vid:
                d = sql(f"select coalesce(route_decision,''), (visit_id='{e1.vid}') from encounter_flow"
                        f" where visit_id='{k10.vid}'")
                k10.ghi_chu.append(f"route={d}")
                nk.lam("he-thong", "P10", "khách từng khám với BS chính → vào THẲNG BS chính",
                       lambda: (d and d[0][0] == "PRIMARY") or (_ for _ in ()).throw(
                           AssertionError(f"route={d} (cùng lượt cũ? {d[0][1] if d else '?'})")), khach="P10")
        ket["P10"] = {"vid": k10.vid, "vid_cu": e1.vid, "ghi_chu": k10.ghi_chu}

    time.sleep(4)
    td.dung()
    b.ai("ql").goi("PATCH", "/day-noi/day", json={"ma": "h8_nhac_check_out_phut", "gia_tri": 60})
    b.ai("ql").goi("PATCH", "/ca-lam-viec", json={"ca_lam_viec": ca_cu})
    ghi_sql(f"update clinic set settings = jsonb_set(settings, '{{hours}}', '{gio_cu}'::jsonb)"
            f" where id='{CLINIC}'", ly_do="trả giờ mở cửa cũ")

    # ── KIỂM CUỐI ──────────────────────────────────────────────────────────
    ket["kiem_cuoi"] = kiem_cuoi(seq0, khach, ph)
    ket["man_hinh"] = td.tong_hop()
    ket["api"] = so_goi.tong_hop()
    ket["api_5xx"] = [list(g) for g in so_goi.loi_5xx()]
    ket["thao_tac"] = [t.__dict__ for t in nk.ds]
    ket["do_tre_man"] = do_tre_man(td, khach)
    ra = viet_bao_cao(ket, nk, td, khach)
    so_hong = sum(1 for t in nk.ds if t.kq in ("HỎNG", "LẼ RA PHẢI CHẶN"))
    print(f"\n══ {len(nk.ds)} thao tác · {so_hong} hỏng/lỗ hổng · báo cáo {ra}")
    return 0


def kiem_cuoi(seq0: int, khach: list[pk.Khach], ph: dict[str, str]) -> dict[str, Any]:
    sk = su_kien_sau(seq0)
    gt = giao_tin_sau(seq0)
    tre: dict[str, list[int]] = defaultdict(list)
    for g in gt:
        if g["tre_ms"]:
            tre[g["consumer"]].append(int(g["tre_ms"]))
    vids = [k.vid for k in khach if k.vid]
    ds = ",".join(f"'{v}'" for v in vids) or "NULL"
    ra: dict[str, Any] = {
        "so_su_kien": dict(Counter(s["event_type"] for s in sk).most_common()),
        "su_kien_theo_module": dict(Counter(s["source_module"] for s in sk).most_common()),
        "giao_tin_khong_xong": [g for g in gt if g["status"] != "DONE"],
        "tre_giao_tin_ms": {c: {"so": len(v), "p50": sorted(v)[len(v) // 2], "max": max(v)} for c, v in tre.items()},
        "su_kien_khong_nguoi_lam": sum(1 for s in sk if not s["actor_staff_id"]),
        "xep_phong_khac_co_so": sql(
            "select o.service_code, r.name, rl.name from service_order o join clinic_room r on r.id=o.room_id"
            " join clinic_location rl on rl.id=r.location_id join visit v on v.visit_id=o.visit_id"
            " join appointment a on a.id=v.appointment_id"
            " where o.created_at >= now() - interval '3 hours' and r.location_id <> a.location_id"),
        "luot_con_mo": sql(
            "select v.visit_id, p.full_name, v.status, coalesce(f.route_decision,''),"
            " (select count(*) from queue_entry q where q.visit_id=v.visit_id and q.status in ('waiting','serving','blocked','called'))"
            " from visit v join patient p on p.clinic_patient_id=v.clinic_patient_id"
            " left join encounter_flow f on f.visit_id=v.visit_id"
            f" where v.visit_id in ({ds}) and v.closed_at is null"),
        "hang_cho_luot_da_dong": sql(
            "select q.visit_id, q.lane, q.status from queue_entry q join visit v on v.visit_id=q.visit_id"
            f" where q.visit_id in ({ds}) and v.closed_at is not null and q.status in ('waiting','serving','blocked','called')"),
        "hen_gio": sql(
            "select loai, trang_thai, count(*) from hen_gio where tao_luc >= now() - interval '3 hours' group by 1,2")
        if sql("select to_regclass('public.hen_gio') is not null")[0][0] == "t" else [],
        "viec_mo": sql(
            "select node_code, status, count(*) from work_item where created_at >= now() - interval '3 hours'"
            " and status in ('PENDING','IN_PROGRESS') group by 1,2 order by 3 desc limit 15"),
    }
    # Sự kiện khai trong danh mục mà cả buổi không ai phát (dây chưa chạy tới / dây chết?)
    sys.path.insert(0, str(REPO / "src"))
    try:
        from clinicai.events.catalogue import DANH_MUC  # noqa: PLC0415

        ra["su_kien_khai_ma_khong_phat"] = sorted(set(DANH_MUC) - set(ra["so_su_kien"]))
    except Exception as e:  # noqa: BLE001
        ra["su_kien_khai_ma_khong_phat"] = [f"không đọc được danh mục: {e}"]
    return ra


def do_tre_man(td: TheoDoi, khach: list[pk.Khach]) -> list[dict[str, Any]]:
    """Từ lúc thao tác tới lúc khách HIỆN trên màn đích."""
    ra = []
    cap = [("check_in", "Lễ tân · bảng lượt khám"), ("sinh_hieu", "BS tư vấn · hàng tư vấn"),
           ("xong_tu_van", "BS chính · danh sách khám"), ("xong_bs_chinh", "Lễ tân · bảng thu tiền"),
           ("thu_dv", "Quản lý · chỉ định hôm nay")]
    for k in khach:
        if not k.vid:
            continue
        for moc, man in cap:
            if moc in k.moc:
                t = td.lan_hien_dau(man, f"v:{k.vid}", sau=k.moc[moc] - 0.5)
                ra.append({"khach": k.ma, "tu": moc, "man": man,
                           "tre_giay": round(t - k.moc[moc], 1) if t else None})
    return ra


def viet_bao_cao(ket: dict[str, Any], nk: NhatKyThaoTac, td: TheoDoi, khach: list[pk.Khach]) -> Path:
    gio = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    thu = REPO / ".dev-logs"
    thu.mkdir(exist_ok=True)
    (thu / f"ngay-kham-{gio}.json").write_text(json.dumps(ket, ensure_ascii=False, indent=1, default=str))
    L: list[str] = [f"# Buổi khám giả lập — {gio}", ""]
    hong = [t for t in nk.ds if t.kq in ("HỎNG", "LẼ RA PHẢI CHẶN")]
    L += [f"**{len(nk.ds)} thao tác · {len(hong)} hỏng/lỗ hổng · "
          f"{sum(1 for t in nk.ds if t.kq == 'CHẶN ĐÚNG')} bị chặn đúng**", "", "## Hỏng / lỗ hổng", ""]
    for t in hong:
        L.append(f"- **[{t.ai}] {t.ten}** — {t.kq} {t.ma or ''}: {(t.loi or '')[:300]}")
    L += ["", "## Hành trình khách (giây tính từ lúc đến)", ""]
    for kk in ket["khach"]:
        L.append(f"- {kk['ma']} ({kk['loai']}) xong={kk['xong']} · {kk['moc']} · {'; '.join(kk['ghi_chu'])}")
    L += ["", "## Bản đồ thao tác → sự kiện (khách E1 đi từng bước)", ""]
    for x in ket.get("ban_do_su_kien", []):
        L.append(f"- [{x['ai']}] {x['thao_tac']} ({x['kq']}) → {', '.join(x['su_kien']) or '∅ KHÔNG PHÁT SỰ KIỆN'}")
    L += ["", "## Độ trễ thao tác → màn hình", ""]
    for d in ket["do_tre_man"]:
        L.append(f"- {d['khach']}: {d['tu']} → {d['man']}: {d['tre_giay']} s")
    L += ["", "## Màn hình theo dõi", ""]
    for m in ket["man_hinh"]:
        L.append(f"- {m['man']}: {m['lan_doc']} lần đọc, p50 {m['p50_ms']} ms, max {m['max_ms']} ms, lỗi {m['so_loi']} {m['loi_mau']}"
                 f" · còn lại cuối buổi: {len(m['con_lai_cuoi_buoi'])}")
    kc = ket["kiem_cuoi"]
    L += ["", "## Sự kiện", "", f"- theo loại: {kc['so_su_kien']}", f"- theo khối: {kc['su_kien_theo_module']}",
          f"- giao tin chưa xong: {kc['giao_tin_khong_xong']}", f"- trễ giao tin (ms) theo bên nhận: {kc['tre_giao_tin_ms']}",
          f"- sự kiện không ghi người làm: {kc['su_kien_khong_nguoi_lam']}",
          f"- sự kiện khai trong danh mục mà cả buổi KHÔNG phát: {kc['su_kien_khai_ma_khong_phat']}", "",
          "## Bất biến dữ liệu", "", f"- xếp phòng sang cơ sở khác: {kc['xep_phong_khac_co_so']}",
          f"- lượt còn mở cuối buổi: {kc['luot_con_mo']}", f"- hàng chờ của lượt đã đóng: {kc['hang_cho_luot_da_dong']}",
          f"- hẹn giờ: {kc['hen_gio']}", f"- việc còn mở: {kc['viec_mo']}", "", "## Thao tác không phát sự kiện nghiệp vụ", ""]
    khong = Counter(t.loai for t in nk.ds if t.kq == "OK" and t.su_kien == [] and t.ai != "he-thong")
    L.append(f"(chỉ đo với thao tác chạy tuần tự) {dict(khong)}")
    L += ["", "## API chậm nhất (p95)", ""]
    for a in sorted(ket["api"], key=lambda x: -x["p95_ms"])[:15]:
        L.append(f"- {a['endpoint']}: {a['so_lan']} lần · p50 {a['p50_ms']} · p95 {a['p95_ms']} · max {a['max_ms']} · mã {a['ma']}")
    L += ["", f"## 5xx: {len(ket['api_5xx'])}", ""] + [f"- {g}" for g in ket["api_5xx"][:30]]
    L += ["", "## Pha A", "", "```", json.dumps(ket["pha_a"], ensure_ascii=False, indent=1, default=str)[:3000], "```",
          "", "## Pha phá", "", "```", json.dumps(ket["pha_pha"], ensure_ascii=False, indent=1, default=str)[:3000], "```"]
    ra = thu / f"ngay-kham-{gio}.md"
    ra.write_text("\n".join(L))
    return ra


if __name__ == "__main__":
    raise SystemExit(main())
