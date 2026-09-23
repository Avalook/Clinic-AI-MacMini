"""QUẢN LÝ dựng phòng khám 3 tầng — mọi bước qua API / màn quản lý, không SQL.

Bố cục (Tuyền, 24/09/2026), ở cơ sở Kim Ngưu:
  Tầng 1  lễ tân (1 máy) · kho thuốc · bác sĩ tư vấn · bác sĩ chính + thư ký
  Tầng 2  2 phòng siêu âm — mỗi phòng 1 bác sĩ + 1 điều dưỡng
  Tầng 3  2 phòng thủ thuật — mỗi phòng 1 bác sĩ + 1 điều dưỡng; 1 phòng đối tác
Thêm: 3 CSKH nghe điện thoại đặt lịch.
Thêm để BẮT LỖI: 1 phòng siêu âm ở cơ sở Hào Nam (tự xếp phòng có lọc cơ sở?).

Mọi thao tác ghi vào sổ thao tác (`do_luong.NhatKyThaoTac`) — một bước cấu hình
hỏng cũng là một phát hiện.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import buoc as b
from do_luong import NhatKyThaoTac
from ket_noi import LoiApi, PhienWeb, _mat_khau_thu, sql

KIM_NGUU = b.KIM_NGUU
HAO_NAM = "b4607cb5-3ff1-4c20-9115-147f06aeac1b"

#: tên ngắn → (họ tên, vai chính)
NHAN_SU_MOI: dict[str, tuple[str, str]] = {
    "bs.tuvan": ("BS Tư vấn (mô phỏng)", "DOCTOR"),
    "bs.sa2": ("BS Siêu âm 2 (mô phỏng)", "ULTRASOUND_DOCTOR"),
    "dd.sa2": ("ĐD Siêu âm 2 (mô phỏng)", "NURSE_ULTRASOUND"),
    "bs.tt1": ("BS Thủ thuật 1 (mô phỏng)", "DOCTOR"),
    "dd.tt1": ("ĐD Thủ thuật 1 (mô phỏng)", "NURSE_ULTRASOUND"),
    "bs.tt2": ("BS Thủ thuật 2 (mô phỏng)", "DOCTOR"),
    "dd.tt2": ("ĐD Thủ thuật 2 (mô phỏng)", "NURSE_ULTRASOUND"),
    "cskh2": ("CSKH 2 (mô phỏng)", "CSKH"),
    "cskh3": ("CSKH 3 (mô phỏng)", "CSKH"),
}

#: (mã phòng tự đặt, tên, tầng, node chính, node phụ)
PHONG: list[tuple[str, str, str, str, list[str]]] = [
    ("letan", "T1 · Quầy lễ tân", "Tầng 1", "LUOTKHAM-01", ["LUOTKHAM-03", "LUOTKHAM-14"]),
    ("kho", "T1 · Kho thuốc", "Tầng 1", "THUOC-04", []),
    ("tuvan", "T1 · Phòng tư vấn", "Tầng 1", "KHAM-PHUKHOA", []),
    ("chinh", "T1 · Phòng khám bác sĩ chính", "Tầng 1", "KHAM-PHUKHOA",
     ["KHAM-NOITIET", "KHAM-SANKHOA", "KHAM-NAMKHOA", "KHAM-HIEMMUON-VOSINH"]),
    ("sa1", "T2 · Siêu âm 1", "Tầng 2", "DICHVU-SIEUAM", []),
    ("sa2", "T2 · Siêu âm 2", "Tầng 2", "DICHVU-SIEUAM", []),
    ("tt1", "T3 · Thủ thuật 1", "Tầng 3", "DICHVU-THUTHUAT", ["DICHVU-SANGLOC-COTUCUNG"]),
    ("tt2", "T3 · Thủ thuật 2", "Tầng 3", "DICHVU-THUTHUAT", ["DICHVU-SANGLOC-COTUCUNG"]),
]

#: vị trí làm việc: (tên ngắn người, tên vị trí, nhóm nghề, mã phòng)
VI_TRI: list[tuple[str, str, str, str]] = [
    ("letan", "T1 Lễ tân", "DIEU_DUONG", "letan"),
    ("duocsi", "T1 Kho thuốc", "CHUNG", "kho"),
    ("bs.tuvan", "T1 BS tư vấn", "BAC_SI", "tuvan"),
    ("bs.a", "T1 BS chính", "BAC_SI", "chinh"),
    ("thuky", "T1 Thư ký BS chính", "DIEU_DUONG", "chinh"),
    ("bs.sa", "T2 BS siêu âm 1", "BAC_SI", "sa1"),
    ("dd.sa", "T2 ĐD siêu âm 1", "DIEU_DUONG", "sa1"),
    ("bs.sa2", "T2 BS siêu âm 2", "BAC_SI", "sa2"),
    ("dd.sa2", "T2 ĐD siêu âm 2", "DIEU_DUONG", "sa2"),
    ("bs.tt1", "T3 BS thủ thuật 1", "BAC_SI", "tt1"),
    ("dd.tt1", "T3 ĐD thủ thuật 1", "DIEU_DUONG", "tt1"),
    ("bs.tt2", "T3 BS thủ thuật 2", "BAC_SI", "tt2"),
    ("dd.tt2", "T3 ĐD thủ thuật 2", "DIEU_DUONG", "tt2"),
    ("doitac", "T3 Đối tác", "DOI_TAC", ""),
]


def staff_id(ten: str) -> str | None:
    r = sql(
        "select s.id from staff s join auth.users u on u.id=s.auth_user_id"
        f" where u.email='{ten}@dr4women.local'"
    )
    return r[0][0] if r else None


def dung(nk: NhatKyThaoTac) -> dict[str, Any]:
    ql = b.ai("ql")
    web = PhienWeb("ql@dr4women.local")
    ket: dict[str, Any] = {"phong": {}, "vi_tri": {}, "nhan_su": {}}

    # ── 1. Nhân sự + tài khoản đăng nhập (đúng đường màn quản lý) ──────────
    for ten, (ho_ten, vai) in NHAN_SU_MOI.items():
        sid = staff_id(ten)
        if sid is None:
            tao = nk.lam("ql", "cấu hình", f"tạo nhân sự {ten} ({vai})", lambda ho_ten=ho_ten, vai=vai: ql.post(
                "/staff", {"full_name": ho_ten, "primary_department": vai,
                           "primary_location_id": KIM_NGUU, "employment_type": "FULL_TIME"}))
            if tao:
                nk.lam("ql", "cấu hình", f"tạo tài khoản đăng nhập {ten}", lambda tao=tao, ten=ten: web.goi(
                    "POST", "/api/admin/users",
                    json={"email": f"{ten}@dr4women.local", "password": _mat_khau_thu(), "staffId": tao["id"]}))
            sid = staff_id(ten)
        ket["nhan_su"][ten] = sid
    for ten in ("ql", "letan", "duocsi", "bs.a", "thuky", "bs.sa", "dd.sa", "doitac", "cskh", "truongca"):
        ket["nhan_su"][ten] = staff_id(ten)

    # ── 2. Phòng theo tầng; tắt phòng cũ trùng chức năng ─────────────────
    tong_quan = ql.get("/clinic-config/overview")
    cu = [r for loc in tong_quan["locations"] if loc["location_id"] == KIM_NGUU
          for f in loc["floors"] for r in f["rooms"] if r["is_active"]]
    for r in cu:
        nk.lam("ql", "cấu hình", f"tắt phòng cũ {r['code']} ({r['name']})", lambda r=r: ql.goi(
            "PUT", "/clinic-config/room-active", json={"room_id": r["room_id"], "is_active": False}))
    for ma, ten, tang, node, phu in PHONG:
        r = nk.lam("ql", "cấu hình", f"tạo phòng {ten}", lambda ten=ten, tang=tang, node=node: ql.post(
            "/clinic-config/rooms", {"location_id": KIM_NGUU, "name": ten, "node_code": node, "floor": tang}))
        if r:
            ket["phong"][ma] = r["room_id"]
            if phu:
                nk.lam("ql", "cấu hình", f"gán dịch vụ cho {ten}", lambda r=r, node=node, phu=phu: ql.goi(
                    "PUT", "/clinic-config/room-nodes", json={"room_id": r["room_id"], "node_codes": [node, *phu]}))
    # Phòng đối tác: KHÔNG tạo được qua API (la_doi_tac chỉ SQL) → dùng phòng có sẵn.
    dt_phong = sql("select id from clinic_room where la_doi_tac and clinic_id=(select clinic_id from clinic_location"
                   f" where id='{KIM_NGUU}') limit 1")
    if dt_phong:
        ket["phong"]["doitac"] = dt_phong[0][0]
        nk.lam("ql", "cấu hình", "bật lại phòng đối tác (có sẵn — API không tạo được phòng đối tác)",
               lambda: ql.goi("PUT", "/clinic-config/room-active", json={"room_id": dt_phong[0][0], "is_active": True}))
        nk.lam("ql", "cấu hình", "chuyển phòng đối tác lên Tầng 3", lambda: ql.goi(
            "PUT", "/clinic-config/room-floor", json={"room_id": dt_phong[0][0], "floor": "Tầng 3"}))
    # Cơ sở 2 — để kiểm tự xếp phòng có lọc theo cơ sở không.
    r = nk.lam("ql", "cấu hình", "tạo phòng siêu âm ở cơ sở Hào Nam (kiểm lọc cơ sở)", lambda: ql.post(
        "/clinic-config/rooms", {"location_id": HAO_NAM, "name": "HN · Siêu âm", "node_code": "DICHVU-SIEUAM",
                                 "floor": "Tầng 1"}))
    if r:
        ket["phong"]["hn_sa"] = r["room_id"]

    # ── 3. Vị trí làm việc + lịch trực hôm nay và tuần này ──────────────
    for nguoi, ten_vt, nhom, phong in VI_TRI:
        body: dict[str, Any] = {"ten": ten_vt, "nhom_nghe": nhom,
                                "tang": {"T1": "Tầng 1", "T2": "Tầng 2", "T3": "Tầng 3"}[ten_vt[:2]]}
        if phong and phong in ket["phong"]:
            body["room_id"] = ket["phong"][phong]
        nk.lam("ql", "cấu hình", f"tạo vị trí {ten_vt}", lambda body=body: ql.post("/day-noi/vi-tri", body))
    dn = ql.get("/day-noi")
    ma_vt = {v["ten"]: (v.get("ma") or v.get("code")) for v in dn["vi_tri"]}
    ket["vi_tri"] = {t: ma_vt.get(t) for _, t, _, _ in VI_TRI}
    # PHÁT HIỆN: vị trí vừa tạo không xếp được ai cho tới khi khai "vai nào được
    # đứng vị trí này" — Quản lý phải làm thêm bước này cho TỪNG vị trí.
    for nguoi, ten_vt, _, _ in VI_TRI:
        sid, tram = ket["nhan_su"].get(nguoi), ket["vi_tri"].get(ten_vt)
        if not sid or not tram:
            continue
        vai = sql(f"select primary_department from staff where id='{sid}'")[0][0]
        nk.lam("ql", "cấu hình", f"cho vai {vai} đứng {ten_vt}", lambda tram=tram, vai=vai: ql.goi(
            "PUT", "/roster/station-scope", json={"tram_ma": tram, "vai": vai, "cho_phep": True}))
    hom_nay = dt.datetime.now(b.VN).date()
    dau_tuan = hom_nay - dt.timedelta(days=hom_nay.weekday())
    for nguoi, ten_vt, _, _ in VI_TRI:
        sid = ket["nhan_su"].get(nguoi)
        tram = ket["vi_tri"].get(ten_vt)
        if not sid or not tram:
            continue
        for d in range(7):
            ngay = dau_tuan + dt.timedelta(days=d)
            if ngay < hom_nay:
                continue
            nk.lam("ql", "cấu hình", f"xếp ca {nguoi} {ngay:%d/%m} @ {ten_vt}", lambda sid=sid, tram=tram, ngay=ngay: ql.post(
                "/roster/shifts", {"work_date": ngay.isoformat(), "station": tram, "shift": "FULL", "staff_id": sid}))
    nk.lam("ql", "cấu hình", "công bố lịch trực tuần này",
           lambda: ql.post("/roster/weeks/apply", {"week_start": dau_tuan.isoformat()}))

    # ── 4. Thư ký theo bác sĩ chính; quyền theo việc ─────────────────────
    nk.lam("ql", "cấu hình", "phân thư ký cho BS chính", lambda: ql.goi(
        "PUT", "/clinic-config/thu-ky-bac-si",
        json={"thu_ky_staff_id": ket["nhan_su"]["thuky"], "bac_si_staff_ids": [ket["nhan_su"]["bs.a"]]}))
    # Tầng 1 không có điều dưỡng: bác sĩ tư vấn và lễ tân đo sinh hiệu.
    for nguoi in ("bs.tuvan", "letan"):
        nk.lam("ql", "cấu hình", f"cấp khối sinh_hieu cho {nguoi}", lambda nguoi=nguoi: ql.post(
            f"/phan-quyen/nhan-su/{ket['nhan_su'][nguoi]}/cap", {"khoi": "sinh_hieu", "ly_do": "Tầng 1 không có điều dưỡng"}))

    # ── 5. Loại khám: phụ khoa qua tư vấn (chuẩn) ─────────────────────────
    pk = next(x for x in dn["loai_kham"] if x["code"] == "PHU_KHOA")
    nk.lam("ql", "cấu hình", "Phụ khoa: khách mới qua bác sĩ tư vấn", lambda: ql.goi(
        "PATCH", f"/day-noi/loai-kham/{pk['id']}", json={"qua_tu_van": True}))
    return ket


def chung_minh_loc_co_so(nk: NhatKyThaoTac) -> None:
    """Không cần làm gì thêm: nếu có khách Kim Ngưu bị xếp vào phòng Hào Nam,
    báo cáo cuối sẽ thấy (bất biến `xep_phong_khac_co_so`)."""


__all__ = ["HAO_NAM", "NHAN_SU_MOI", "dung", "staff_id"]


if __name__ == "__main__":  # chạy riêng để thử
    nk = NhatKyThaoTac()
    try:
        print(dung(nk))
    except LoiApi as e:
        print("LỖI", e)
