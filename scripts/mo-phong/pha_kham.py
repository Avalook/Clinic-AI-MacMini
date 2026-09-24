"""PHA B — một buổi khám thật ở phòng khám 3 tầng, nhiều người làm cùng lúc.

Khách đến so le. Mỗi nhân viên là MỘT người (khoá theo người): bác sĩ chính
không khám hai khách cùng lúc, phòng siêu âm không làm hai khách cùng lúc — như
ngoài đời. Mỗi khách đi đúng câu chuyện của mình:

  MOI       khách mới, Phụ khoa: lễ tân check-in + đo sinh hiệu → BS tư vấn →
            BS chính chọn trong danh sách → chỉ định → lễ tân chốt + thu →
            phòng siêu âm / thủ thuật (tự xếp) → đối tác trả kết quả → BS đọc →
            kê đơn → thu thuốc → kho giao → check-out
  QUEN      khách quen của BS chính: MUỐN vào thẳng BS chính (không qua tư vấn)
  VANG_LAI  không hẹn trước: lễ tân tạo + đặt kênh WALK_IN (tự check-in)
  VE_SOM    khách bỏ về khi đang chờ phòng dịch vụ
  KHONG_DEN khách có hẹn nhưng không đến → lễ tân ghi không đến

Mọi thao tác ghi vào sổ (`do_luong`). Những gì lệch câu chuyện là PHÁT HIỆN.
"""

from __future__ import annotations

import datetime as dt
import random
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import buoc as b
from do_luong import NhatKyThaoTac
from ket_noi import LoiApi, sql

SA = "CLS_SIEU_AM_2D_TC_BT"
SOI_CTC = "CLS_SOI_CO_TU_CUNG"  # làm ở phòng thủ thuật, kết quả qua đối tác?
THAO_VONG = "CLS_THAO_VONG"  # thủ thuật
XN_MAU = "CLS_XET_NGHIEM_MAU"  # cần phòng lấy mẫu — cấu hình 3 tầng KHÔNG có


@dataclass
class Khach:
    ma: str
    loai: str
    ten: str
    pid: str | None = None
    aid: str | None = None
    vid: str | None = None
    chi_dinh: list[str] = field(default_factory=list)
    moc: dict[str, float] = field(default_factory=dict)
    ghi_chu: list[str] = field(default_factory=list)
    xong: bool = False


class NguoiLam:
    """Khoá theo người: một người chỉ làm một việc một lúc."""

    def __init__(self) -> None:
        self._k: dict[str, threading.Lock] = defaultdict(threading.Lock)

    def __call__(self, ten: str) -> threading.Lock:
        return self._k[ten]


BAN = NguoiLam()


def khoa() -> dict[str, str]:
    return {"Idempotency-Key": uuid.uuid4().hex}


def hang(u: str, duong: str) -> list[dict[str, Any]]:
    d = b.ai(u).get(duong)
    return list(d.get("hang_cho") or d.get("items") or d.get("rows") or []) if isinstance(d, dict) else list(d)


def cho_hang(u: str, duong: str, vid: str, pred: Any = None, giay: float = 30) -> dict[str, Any]:
    def tim() -> dict[str, Any] | None:
        for r in hang(u, duong):
            if r.get("visit_id") == vid and (pred is None or pred(r)):
                return r
        return None
    return dict(b.cho(tim, giay=giay, mo_ta=f"{vid[:8]} vào {duong}"))


def luot(vid: str) -> dict[str, Any]:
    return b.luot(vid)


# ── Các bước của một khách ────────────────────────────────────────────────


def den_va_check_in(nk: NhatKyThaoTac, k: Khach) -> None:
    k.moc["den"] = time.time()
    r = nk.lam("letan", "check-in", f"{k.ma} check-in", lambda: b.ai("letan").post(
        "/luot-kham/check-in", {"appointment_id": k.aid}), khach=k.ma)
    if r:
        k.vid = r["visit_id"]
        k.moc["check_in"] = time.time()


def vang_lai(nk: NhatKyThaoTac, k: Khach, bs: str) -> None:
    """Lễ tân: khách không hẹn — tạo hồ sơ + đặt kênh WALK_IN (tự check-in)."""
    k.moc["den"] = time.time()
    p = nk.lam("letan", "vãng lai", f"{k.ma} tạo hồ sơ tại quầy", lambda: b.ai("letan").post(
        "/patients", {"full_name": k.ten, "location_id": b.KIM_NGUU, "phone_primary": f"09{random.randint(10**7, 10**8 - 1)}",
                      "gender": "F", "birth_year": 1990}), khach=k.ma)
    if not p:
        return
    k.pid = p["clinic_patient_id"]
    bay_gio = dt.datetime.now(b.VN).replace(second=0, microsecond=0)
    for lan in range(8):
        s = bay_gio + dt.timedelta(minutes=15 * lan + 1)
        try:
            r = b.ai("letan").post("/appointments/bookings", {
                "clinic_patient_id": k.pid,
                "service_type_id": b.id_mot("select id from service_type where code='PHU_KHOA'"),
                "location_id": b.KIM_NGUU, "slot_start": s.isoformat(),
                "slot_end": (s + dt.timedelta(minutes=15)).isoformat(), "doctor_id": bs,
                "booking_channel": "WALK_IN"})
            k.aid = r["appointment_id"]
            break
        except LoiApi as e:
            if e.ma not in (409, 422):
                nk.lam("letan", "vãng lai", f"{k.ma} đặt WALK_IN", lambda e=e: (_ for _ in ()).throw(e), khach=k.ma)
                return
    nk.lam("letan", "vãng lai", f"{k.ma} đặt WALK_IN (tự check-in)", lambda: k.aid or (_ for _ in ()).throw(
        AssertionError("hết khung vãng lai")), khach=k.ma)
    v = sql(f"select visit_id from visit where appointment_id='{k.aid}'") if k.aid else []
    k.vid = v[0][0] if v else None
    k.moc["check_in"] = time.time()
    # PHÁT HIỆN (agent đọc code): WALK_IN không phát visit.checked_in → chưa được xếp hàng?
    if k.vid:
        time.sleep(3)
        dich = sql(f"select coalesce(route_decision,'') from encounter_flow where visit_id='{k.vid}'")
        k.ghi_chu.append(f"sau check-in WALK_IN 3s: route_decision='{dich[0][0] if dich else '?'}'")
        nk.lam("he-thong", "vãng lai", f"{k.ma} vãng lai được xếp đường đi NGAY sau check-in (như khách có hẹn)",
               lambda: (dich and dich[0][0]) or (_ for _ in ()).throw(AssertionError(
                   "WALK_IN check-in không xếp đường đi — không phát visit.checked_in")), khach=k.ma)


def do_sinh_hieu(nk: NhatKyThaoTac, k: Khach, nguoi: str = "letan") -> None:
    with BAN(nguoi):
        nk.lam(nguoi, "sinh hiệu", f"{k.ma} bắt đầu đo", lambda: b.ai(nguoi).post(
            f"/luot-kham/visits/{k.vid}/vitals/start"), khach=k.ma)
        nk.lam(nguoi, "sinh hiệu", f"{k.ma} ghi sinh hiệu", lambda: b.ai(nguoi).post(
            f"/luot-kham/visits/{k.vid}/vitals", {"systolic": random.randint(100, 135), "diastolic": random.randint(60, 85),
                                                  "pulse": random.randint(65, 95), "temperature": 36.6}), khach=k.ma)
    k.moc["sinh_hieu"] = time.time()


def tu_van(nk: NhatKyThaoTac, k: Khach) -> None:
    r = nk.lam("bs.tuvan", "tư vấn", f"{k.ma} vào hàng tư vấn", lambda: cho_hang(
        "bs.tuvan", "/luot-kham/hang-cho?tu_van=true", k.vid, lambda r: r.get("trang_thai") in ("waiting", "called"),
        giay=60), khach=k.ma)
    if not r:
        return
    k.moc["vao_tu_van"] = time.time()
    with BAN("bs.tuvan"):
        nk.lam("bs.tuvan", "tư vấn", f"{k.ma} BS tư vấn bắt đầu", lambda: b.ai("bs.tuvan").post(
            f"/luot-kham/consultations/{r['ref_id']}/start"), khach=k.ma)
        time.sleep(random.uniform(2, 5))  # tư vấn thật ~5–10 phút
        nk.lam("bs.tuvan", "tư vấn", f"{k.ma} tư vấn xong → chuyển BS chính", lambda: b.ai("bs.tuvan").post(
            f"/luot-kham/consultations/{r['ref_id']}/xong-tu-van"), khach=k.ma)
    k.moc["xong_tu_van"] = time.time()


def bs_chinh_kham(nk: NhatKyThaoTac, k: Khach, ma_dv: list[str], *, thu_ky_nhap: bool = False) -> str | None:
    """BS chính mở DANH SÁCH đang chờ, chọn đúng khách này (không nhất thiết người đầu)."""
    r = nk.lam("bs.a", "khám chính", f"{k.ma} hiện trong danh sách BS chính", lambda: cho_hang(
        "bs.a", "/luot-kham/hang-cho", k.vid, lambda r: r.get("vong") == "PRIMARY" and r.get("trang_thai") in ("waiting", "called"),
        giay=60), khach=k.ma)
    if not r:
        return None
    k.moc["vao_bs_chinh"] = time.time()
    ph = r["ref_id"]
    with BAN("bs.a"):
        ds = [x for x in hang("bs.a", "/luot-kham/hang-cho") if x.get("vong") == "PRIMARY" and x.get("trang_thai") == "waiting"]
        vi_tri = next((i for i, x in enumerate(ds) if x.get("visit_id") == k.vid), -1)
        k.ghi_chu.append(f"BS chính chọn khách ở vị trí {vi_tri + 1}/{len(ds)} trong danh sách chờ")
        nk.lam("bs.a", "khám chính", f"{k.ma} BS chính bắt đầu khám", lambda: b.ai("bs.a").post(
            f"/luot-kham/consultations/{ph}/start"), khach=k.ma)
        if thu_ky_nhap:
            nk.lam("thuky", "khám chính", f"{k.ma} thư ký nhập phiếu khám", lambda: _thu_ky_nhap(k.vid), khach=k.ma)
        time.sleep(random.uniform(3, 6))  # khám thật ~6–12 phút
        if ma_dv:
            ids = nk.lam("bs.a", "chỉ định", f"{k.ma} chỉ định {', '.join(ma_dv)}", lambda: b.ai("bs.a").post(
                f"/luot-kham/consultations/{ph}/service-orders", {"service_codes": ma_dv}, headers=khoa()), khach=k.ma)
            k.chi_dinh = list((ids or {}).get("order_ids") or [])
        nk.lam("bs.a", "khám chính", f"{k.ma} BS chính Hoàn tất", lambda: b.ai("bs.a").post(
            f"/luot-kham/consultations/{ph}/kham-xong"), khach=k.ma)
    k.moc["xong_bs_chinh"] = time.time()
    return str(ph)


def _thu_ky_nhap(vid: str) -> Any:
    u = b.ai("thuky")
    hien = u.get(f"/phieu-kham/luot/{vid}/phieu")
    form = hien.get("form_id") or (hien.get("chon_duoc") or [{}])[0].get("form_id")
    khung = hien.get("khung") or []
    o = next((bl["ma"] for m in khung for bl in m.get("block", []) if bl.get("kieu") in ("text", "textarea")), None)
    return u.goi("PUT", f"/phieu-kham/luot/{vid}/phieu", json={
        "form_id": form, "du_lieu": {o or "ly_do_kham": {"gia_tri": "Thư ký nhập hộ BS", "nguon": "USER"}},
        "expected_revision": hien.get("revision", 0)})


def le_tan_thu(nk: NhatKyThaoTac, k: Khach, *, chon: list[str] | None = None) -> None:
    with BAN("letan"):
        bang = b.ai("letan").get("/cashier/board?modes=dich_vu")
        dong = next((x for x in bang.get("items", []) if x.get("visit_id") == k.vid), None)
        nk.lam("letan", "thu tiền", f"{k.ma} hiện trên bảng thu ngân", lambda: dong or (_ for _ in ()).throw(
            AssertionError("không thấy khách trên bảng thu ngân")), khach=k.ma)
        if dong and dong.get("chon_dich_vu", {}).get("chi_dinh"):
            cd = dong["chon_dich_vu"]
            ds = [c["id"] for c in cd["chi_dinh"] if c.get("selection_status") in (None, "PENDING")]
            if ds:
                nk.lam("letan", "thu tiền", f"{k.ma} chốt khách chọn dịch vụ", lambda: b.ai("letan").post(
                    f"/luot-kham/visits/{k.vid}/service-selection/confirm",
                    {"order_ids_seen": ds, "selected_order_ids": ds if chon is None else chon,
                     "expected_selection_revision": int(cd.get("revision") or 0)}, headers=khoa()), khach=k.ma)
        nk.lam("letan", "thu tiền", f"{k.ma} thu tiền dịch vụ", lambda: b.ai("letan").post(
            "/payments", {"visit_id": k.vid, "kind": "dich_vu", "method": "CASH"}, headers=khoa()), khach=k.ma)
    k.moc["thu_dv"] = time.time()


PHONG_NGUOI: dict[str, tuple[str, str]] = {}  # room_id → (bác sĩ, điều dưỡng)


def lam_dich_vu(nk: NhatKyThaoTac, k: Khach, oid: str) -> None:
    c = nk.lam("he-thong", "xếp phòng", f"{k.ma} chỉ định {oid[:8]} được tự xếp phòng",
               lambda: b.cho(lambda: b.chi_dinh(k.vid, oid)["phong_id"], giay=20, mo_ta="xếp phòng"), khach=k.ma)
    if not c:
        return
    phong = str(c)
    bs, dd = PHONG_NGUOI.get(phong, ("", ""))
    if not bs:
        k.ghi_chu.append(f"chỉ định {oid[:8]} xếp vào phòng NGOÀI bố cục 3 tầng ({phong[:8]})")
        nk.lam("he-thong", "xếp phòng", f"{k.ma} phòng được xếp nằm trong bố cục (cùng cơ sở)", lambda: (_ for _ in ()).throw(
            AssertionError(f"xếp vào phòng lạ {phong} — {sql(f'select name, location_id from clinic_room where id={chr(39)}{phong}{chr(39)}')}")),
            khach=k.ma)
        return
    nk.lam(bs, "phòng", f"{k.ma} hiện ở hàng chờ phòng", lambda: cho_hang(
        bs, f"/luot-kham/hang-cho?phong={phong}", k.vid, lambda r: r.get("ref_id") == oid, giay=20), khach=k.ma)
    with BAN(phong):
        a = nk.lam(dd, "phòng", f"{k.ma} {dd} bắt đầu làm {oid[:8]}", lambda: b.bat_dau_lam(oid, dd), khach=k.ma)
        if not a:
            return
        time.sleep(random.uniform(2, 5))  # siêu âm / thủ thuật thật ~5–10 phút
        nk.lam(bs, "phòng", f"{k.ma} {bs} điền phiếu kết quả + Hoàn tất", lambda: b.dien_phieu(oid, bs), khach=k.ma)
        if b._thuc_hien(oid, bs).get("lan_dang_chay"):
            nk.lam(dd, "phòng", f"{k.ma} {dd} bấm Xong", lambda: b.xong_lam(oid, a, dd), khach=k.ma)
    k.moc[f"xong_{oid[:8]}"] = time.time()


def doi_tac_neu_can(nk: NhatKyThaoTac, k: Khach, oid: str) -> None:
    ngoai = sql("select coalesce(nd.lam_ben_ngoai,false) from service_order o left join node_definition nd"
                f" on nd.code=o.node_code and nd.clinic_id=o.clinic_id where o.id='{oid}'")
    if ngoai and ngoai[0][0] == "t":
        nk.lam("doitac", "đối tác", f"{k.ma} đối tác thấy việc + trả kết quả {oid[:8]}",
               lambda: b.doi_tac_tra_ket_qua(oid), khach=k.ma)


def doc_ket_qua(nk: NhatKyThaoTac, k: Khach) -> None:
    with BAN("bs.a"):
        time.sleep(random.uniform(1, 3))
        nk.lam("bs.a", "đọc kết quả", f"{k.ma} BS chính đọc kết quả + Hoàn tất",
               lambda: b.doc_ket_qua_va_xong(k.vid), khach=k.ma)
    k.moc["doc_kq"] = time.time()


def thuoc_va_ve(nk: NhatKyThaoTac, k: Khach, *, co_thuoc: bool = True) -> None:
    if co_thuoc:
        with BAN("bs.a"):
            nk.lam("bs.a", "thuốc", f"{k.ma} BS chính kê đơn", lambda: b.ke_don(k.vid), khach=k.ma)
        with BAN("letan"):
            nk.lam("letan", "thuốc", f"{k.ma} thu tiền thuốc", lambda: b.thu(k.vid, "thuoc", "letan"), khach=k.ma)
        with BAN("duocsi"):
            nk.lam("duocsi", "thuốc", f"{k.ma} kho thấy đơn + giao thuốc", lambda: b.giao_thuoc(k.vid), khach=k.ma)
    with BAN("letan"):
        nk.lam("letan", "check-out", f"{k.ma} check-out", lambda: b.checkout(k.vid), khach=k.ma)
    k.moc["ve"] = time.time()
    k.xong = True


# ── Câu chuyện từng loại khách ────────────────────────────────────────────


def chuyen_moi(nk: NhatKyThaoTac, k: Khach, ma_dv: list[str], *, co_thuoc: bool = True, thu_ky: bool = False) -> None:
    den_va_check_in(nk, k)
    if not k.vid:
        return
    do_sinh_hieu(nk, k)
    tu_van(nk, k)
    if not bs_chinh_kham(nk, k, ma_dv, thu_ky_nhap=thu_ky):
        return
    if k.chi_dinh:
        le_tan_thu(nk, k)
        for oid in k.chi_dinh:
            lam_dich_vu(nk, k, oid)
            doi_tac_neu_can(nk, k, oid)
        doc_ket_qua(nk, k)
    else:
        with BAN("letan"):
            nk.lam("letan", "thu tiền", f"{k.ma} thu tiền khám", lambda: b.thu(k.vid, "dich_vu", "letan"), khach=k.ma)
    thuoc_va_ve(nk, k, co_thuoc=co_thuoc)


def chuyen_quen(nk: NhatKyThaoTac, k: Khach) -> None:
    """Khách quen: đúng ý Tuyền là vào thẳng BS chính. Hệ thống có cho không?"""
    den_va_check_in(nk, k)
    if not k.vid:
        return
    do_sinh_hieu(nk, k)
    time.sleep(2)
    dich = sql(f"select coalesce(route_decision,'') from encounter_flow where visit_id='{k.vid}'")
    k.ghi_chu.append(f"khách quen được xếp: {dich[0][0] if dich else '?'}")
    nk.lam("he-thong", "khách quen", f"{k.ma} khách quen vào THẲNG BS chính (không qua tư vấn)",
           lambda: (dich and dich[0][0] == "PRIMARY") or (_ for _ in ()).throw(AssertionError(
               f"khách quen bị đưa vào hàng '{dich[0][0] if dich else '?'}' — chưa có cách cho khách quen vào thẳng")),
           khach=k.ma)
    if dich and dich[0][0] == "TU_VAN":
        tu_van(nk, k)  # đường vòng: tư vấn bấm chuyển ngay
    if bs_chinh_kham(nk, k, [SA]):
        le_tan_thu(nk, k)
        for oid in k.chi_dinh:
            lam_dich_vu(nk, k, oid)
        doc_ket_qua(nk, k)
        thuoc_va_ve(nk, k, co_thuoc=False)


def chuyen_ve_som(nk: NhatKyThaoTac, k: Khach) -> None:
    den_va_check_in(nk, k)
    if not k.vid:
        return
    do_sinh_hieu(nk, k)
    tu_van(nk, k)
    if bs_chinh_kham(nk, k, [SA]):
        le_tan_thu(nk, k)
        with BAN("letan"):
            nk.lam("letan", "check-out", f"{k.ma} check-out khi còn chờ siêu âm → phải bị chặn, nói rõ lý do",
                   lambda: b.checkout(k.vid), khach=k.ma, mong_loi=422)
            nk.lam("letan", "check-out", f"{k.ma} khách bỏ về — check-out ghi lý do",
                   lambda: b.checkout(k.vid, bo_ve="Khách có việc gấp, hẹn quay lại"), khach=k.ma)
        time.sleep(3)
        nk.lam("he-thong", "về sớm", f"{k.ma} khách về rồi thì RỜI hàng chờ phòng",
               lambda: not [r for p in PHONG_NGUOI for r in hang(PHONG_NGUOI[p][0], f"/luot-kham/hang-cho?phong={p}")
                            if r.get("visit_id") == k.vid and r.get("trang_thai") in ("waiting", "called", "blocked")]
               or (_ for _ in ()).throw(AssertionError("khách đã về vẫn còn trong hàng chờ phòng")), khach=k.ma)
        k.xong = True


def chuyen_khong_den(nk: NhatKyThaoTac, k: Khach) -> None:
    time.sleep(5)
    nk.lam("letan", "không đến", f"{k.ma} lễ tân ghi KHÔNG ĐẾN", lambda: b.doi_lich(
        k.aid, action="no_show", nguoi="letan"), khach=k.ma)
    k.xong = True
