"""Các BƯỚC nghiệp vụ của bộ mô phỏng — mỗi bước gọi đúng API giao diện gọi.

Không bước nào ghi thẳng database: đi qua đăng nhập, cửa quyền, router, sự kiện,
worker y như người thật bấm. Database chỉ được ĐỌC để dò mã (lịch, lô thuốc…)
và để kiểm cuối.
"""

from __future__ import annotations

import datetime as dt
import random
import time
import uuid
from collections.abc import Callable
from typing import Any

from ket_noi import LoiApi, NguoiDung, sql

VN = dt.timezone(dt.timedelta(hours=7))
KIM_NGUU = "fe45d9f6-0d67-428d-9d16-5ba5c36befff"

_NGUOI: dict[str, NguoiDung] = {}


def ai(ten: str) -> NguoiDung:
    """Tài khoản thử theo tên ngắn: letan, bs.a, bs.sa, dd.sa, thungan, ql…"""
    if ten not in _NGUOI:
        _NGUOI[ten] = NguoiDung(f"{ten}@dr4women.local")
    return _NGUOI[ten]


def khoa() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


def id_mot(cau: str) -> str:
    r = sql(cau)
    if not r:
        raise LookupError(f"không tìm thấy: {cau}")
    return r[0][0]


def cho(dieu_kien: Callable[[], Any], *, giay: float = 20, mo_ta: str = "") -> Any:
    """Đợi worker xử lý sự kiện (giao tin bất đồng bộ)."""
    het = time.monotonic() + giay
    while True:
        kq = dieu_kien()
        if kq:
            return kq
        if time.monotonic() > het:
            raise TimeoutError(f"quá {giay}s vẫn chưa: {mo_ta}")
        time.sleep(0.5)


# ── Đọc bảng lượt khám (như màn hình) ─────────────────────────────────────


def luot(vid: str) -> dict[str, Any]:
    for x in ai("ql").get("/luot-kham/bang")["luot"]:
        if x["visit_id"] == vid:
            return x
    raise LookupError(f"lượt {vid} không có trên bảng")


def chi_dinh(vid: str, oid: str) -> dict[str, Any]:
    return next(c for c in luot(vid)["chi_dinh"] if c["id"] == oid)


# ── Khách + lịch ──────────────────────────────────────────────────────────


def tao_khach(ten: str) -> str:
    p = ai("letan").post(
        "/patients",
        {
            "full_name": ten,
            "location_id": KIM_NGUU,
            "phone_primary": f"09{random.randint(10**7, 10**8 - 1)}",
            "gender": "F",
            "birth_year": random.randint(1975, 2003),
        },
    )
    return str(p["clinic_patient_id"])


def gio_hom_nay(phut_tu_8h: int) -> dt.datetime:
    goc = dt.datetime.now(VN).replace(hour=8, minute=0, second=0, microsecond=0)
    return goc + dt.timedelta(minutes=phut_tu_8h)


def dat_lich(
    pid: str, *, phut: int, bac_si: str = "bs.a", dich_vu: str = "PHU_KHOA"
) -> str:
    st = id_mot(f"select id from service_type where code='{dich_vu}' and is_active")
    bs = id_mot(
        "select s.id from staff s join auth.users u on u.id=s.auth_user_id"
        f" where u.email='{bac_si}@dr4women.local'"
    )
    # Khung đầy (409 sức chứa) hoặc rơi giờ nghỉ trưa (422) → khung kế tiếp,
    # đúng như CSKH chọn lại giờ.
    for thu_lai in range(60):
        s = gio_hom_nay(phut + 15 * thu_lai)
        try:
            r = ai("cskh").post(
                "/appointments/bookings",
                {
                    "clinic_patient_id": pid,
                    "service_type_id": st,
                    "location_id": KIM_NGUU,
                    "slot_start": s.isoformat(),
                    "slot_end": (s + dt.timedelta(minutes=15)).isoformat(),
                    "doctor_id": bs,
                    "booking_channel": "HOTLINE",
                },
            )
            return str(r["appointment_id"])
        except LoiApi as e:
            if e.ma not in (409, 422) or thu_lai == 59:
                raise
    raise RuntimeError("không còn khung trống")


def doi_lich(aid: str, *, action: str, **them: Any) -> Any:
    return ai(them.pop("nguoi", "cskh")).goi(
        "PATCH", f"/appointments/{aid}", json={"action": action, **them}
    )


def check_in(aid: str, nguoi: str = "letan") -> str:
    return str(ai(nguoi).post("/luot-kham/check-in", {"appointment_id": aid})["visit_id"])


# ── Sinh hiệu + khám ──────────────────────────────────────────────────────


def do_sinh_hieu(vid: str, nguoi: str = "dd.sa") -> None:
    ai(nguoi).post(f"/luot-kham/visits/{vid}/vitals/start")
    ai(nguoi).post(
        f"/luot-kham/visits/{vid}/vitals",
        {"systolic": 118, "diastolic": 76, "pulse": 80, "temperature": 36.7},
    )


def _phien_cho(vid: str, loai: set[str]) -> dict[str, Any] | None:
    return next(
        (p for p in luot(vid)["phien"] if p["loai"] in loai and p["trang_thai"] == "queued"),
        None,
    )


def bat_dau_kham(vid: str, nguoi: str = "bs.a") -> str:
    """Khám chính: nếu loại khám qua tư vấn thì tư vấn xong trước."""
    p = cho(lambda: _phien_cho(vid, {"PRIMARY", "INTAKE"}), mo_ta="phiên khám vào hàng")
    if p["loai"] == "INTAKE":
        ai(nguoi).post(f"/luot-kham/consultations/{p['id']}/start")
        ai(nguoi).post(f"/luot-kham/consultations/{p['id']}/xong-tu-van")
        p = cho(lambda: _phien_cho(vid, {"PRIMARY"}), mo_ta="bàn giao bác sĩ chính")
    ai(nguoi).post(f"/luot-kham/consultations/{p['id']}/start")
    return str(p["id"])


def chi_dinh_dv(phien: str, ma: list[str], nguoi: str = "bs.a") -> list[str]:
    r = ai(nguoi).post(
        f"/luot-kham/consultations/{phien}/authorize-orders", {"service_codes": ma}
    )
    return list(r["order_ids"])


def kham_xong(phien: str, nguoi: str = "bs.a") -> Any:
    return ai(nguoi).post(f"/luot-kham/consultations/{phien}/kham-xong")


# ── Chọn dịch vụ + thu tiền ───────────────────────────────────────────────


def chon_dv(vid: str, chon: list[str] | None = None, nguoi: str = "letan") -> Any:
    """Lễ tân chốt khách làm những chỉ định nào (mặc định: tất cả đang chờ)."""
    dang_cho = [
        r[0]
        for r in sql(
            f"select id from service_order where visit_id='{vid}'"
            " and exec_status='authorized'"
            " and coalesce(selection_status,'PENDING')='PENDING'"
        )
    ]
    rev = int(
        id_mot(
            "select coalesce((select revision from service_selection_state"
            f" where visit_id='{vid}'),0)"
        )
    )
    return ai(nguoi).post(
        f"/luot-kham/visits/{vid}/service-selection/confirm",
        {
            "order_ids_seen": dang_cho,
            "selected_order_ids": dang_cho if chon is None else chon,
            "expected_selection_revision": rev,
        },
        headers=khoa(),
    )


def thu(vid: str, kind: str = "dich_vu", nguoi: str = "letan", key: str | None = None) -> Any:
    return ai(nguoi).post(
        "/payments",
        {"visit_id": vid, "kind": kind, "method": "CASH"},
        headers={"Idempotency-Key": key or str(uuid.uuid4())},
    )


# ── Xếp phòng + thực hiện + phiếu kết quả ─────────────────────────────────


def cho_phong(vid: str, oid: str, giay: float = 15) -> str:
    return str(
        cho(lambda: chi_dinh(vid, oid)["phong_id"], giay=giay, mo_ta=f"xếp phòng {oid}")
    )


def xep_tay(oid: str, nguoi: str = "truongca") -> str:
    u = ai(nguoi)
    rec = u.get(f"/luot-kham/orders/{oid}/routing/recommendation")
    ex = u.get(f"/luot-kham/orders/{oid}/execution")
    phong = rec["candidates"][0]["room_id"]
    u.post(
        f"/luot-kham/orders/{oid}/routing/assign",
        {
            "room_id": phong,
            "expected_routing_revision": ex["routing_revision"],
            "reason_code": "INITIAL_ASSIGNMENT",
            "recommendation_ref": rec["recommendation_ref"],
        },
        headers=khoa(),
    )
    return str(phong)


def _thuc_hien(oid: str, nguoi: str) -> dict[str, Any]:
    return dict(ai(nguoi).get(f"/luot-kham/orders/{oid}/execution"))


def bat_dau_lam(oid: str, nguoi: str = "bs.sa") -> str:
    ex = _thuc_hien(oid, nguoi)
    ai(nguoi).post(
        f"/luot-kham/orders/{oid}/execution/bat-dau",
        {
            "expected_execution_revision": ex["execution_revision"],
            "expected_routing_revision": ex["routing_revision"],
        },
        headers=khoa(),
    )
    ex = _thuc_hien(oid, nguoi)
    return str(ex["lan_dang_chay"]["id"])


def dien_phieu(oid: str, nguoi: str = "bs.sa", *, du_lieu: dict[str, Any] | None = None) -> str:
    """Mở phiếu kết quả theo mẫu gợi ý đầu tiên, lưu rồi Hoàn tất.

    Mã phiếu = "KQ_" + mã mẫu — đúng như giao diện ghép (PhieuKetQua.tsx).
    NỢ: quy ước đặt tên này nằm ở giao diện; backend nên trả thẳng mã phiếu."""
    ex = _thuc_hien(oid, nguoi)
    mau = "KQ_" + ex["mau_ket_qua"][0]["ma"]
    u = ai(nguoi)
    p = u.post("/phieu/mo", {"service_order_id": oid, "form_id": mau})
    pid = p.get("phieu_id") or p.get("id")
    rev = p.get("revision", 0)
    if du_lieu is None:
        # Sửa đúng MỘT ô có sẵn trong khung (câu mẫu), như người gõ thật.
        co_san = p.get("du_lieu") or {}
        ma_o = next(iter(co_san), "ghi_chu")
        du_lieu = {ma_o: {"gia_tri": "Mô phỏng: bình thường.", "nguon": "USER"}}
    p = u.post(f"/phieu/{pid}/luu", {"du_lieu": du_lieu, "expected_revision": rev})
    rev = p.get("revision", rev + 1)
    u.post(f"/phieu/{pid}/hoan-tat", {"expected_revision": rev})
    return str(pid)


def xong_lam(oid: str, attempt: str, nguoi: str = "bs.sa") -> Any:
    ex = _thuc_hien(oid, nguoi)
    return ai(nguoi).post(
        f"/luot-kham/orders/{oid}/execution/xong",
        {"attempt_id": attempt, "expected_execution_revision": ex["execution_revision"]},
        headers=khoa(),
    )


def lam_tron(oid: str, nguoi: str = "bs.sa") -> None:
    """Bắt đầu → phiếu kết quả Hoàn tất. Hoàn tất phiếu TỰ đóng lần làm; chỉ bấm
    [Xong] khi lần làm vẫn còn mở (dịch vụ không có phiếu)."""
    a = bat_dau_lam(oid, nguoi)
    dien_phieu(oid, nguoi)
    if _thuc_hien(oid, nguoi).get("lan_dang_chay"):
        xong_lam(oid, a, nguoi)


# ── Đối tác ───────────────────────────────────────────────────────────────


def doi_tac_tra_ket_qua(oid: str) -> Any:
    dt_ = ai("doitac")
    tu_lay = sql(
        "select coalesce(sp.doi_tac_lay_mau,false) from service_order o"
        " join service_price sp on sp.service_code=o.service_code"
        f" and sp.clinic_id=o.clinic_id where o.id='{oid}' limit 1"
    )
    if tu_lay and tu_lay[0][0] == "t":
        dt_.post(f"/doi-tac/viec/{oid}/da-lay-mau")
    return dt_.goi(
        "POST",
        "/doi-tac/ket-qua",
        data={"chi_dinh_id": oid},
        files={"file": ("ket-qua.pdf", b"%PDF-1.4\n% mo phong\n", "application/pdf")},
    )


# ── Vòng đọc kết quả ──────────────────────────────────────────────────────


def doc_ket_qua_va_xong(vid: str, nguoi: str = "bs.a") -> str:
    p = cho(lambda: _phien_cho(vid, {"REVIEW"}), giay=25, mo_ta="phiên đọc kết quả")
    u = ai(nguoi)
    u.post(f"/luot-kham/consultations/{p['id']}/start")
    # Chỉ định khách bỏ / không làm được → bác sĩ QUYẾT (miễn có lý do) trước
    # khi đóng vòng — hệ thống không tự bỏ qua.
    for (yc_id,) in sql(
        "select q.id from round_requirement q join service_order o on o.id=q.service_order_id"
        f" where o.visit_id='{vid}' and q.status='open'"
        " and (o.selection_status='NOT_SELECTED' or o.exec_status in ('not_performed','cancelled'))"
    ):
        u.post(f"/luot-kham/yeu-cau/{yc_id}/quyet",
               {"hanh_dong": "WAIVE", "ly_do": "Khách không làm dịch vụ này"})
    for c in luot(vid)["chi_dinh"]:
        if c["trang_thai"] not in ("cancelled",) and c.get("da_xem_ket_qua_luc") is None:
            try:
                u.post(f"/luot-kham/orders/{c['id']}/duyet-ket-qua", {})
            except LoiApi:
                pass  # chỉ định không làm / chưa có kết quả — không có gì để đọc
    kham_xong(p["id"], nguoi)
    return str(p["id"])


# ── Đơn thuốc + quầy thuốc ────────────────────────────────────────────────


def ke_don(vid: str, so_luong: int = 10, nguoi: str = "bs.a") -> list[str]:
    thuoc = sql(
        "select id, name_base from drug_catalog where is_active and unit_price > 0"
        " order by name_base limit 1"
    )[0]
    ai(nguoi).goi(
        "PUT",
        f"/phieu-kham/luot/{vid}/don-thuoc",
        json={
            "dong": [
                {
                    "drug_catalog_id": thuoc[0],
                    "drug_name": thuoc[1],
                    "quantity": str(so_luong),
                    "dosage": "Ngày 2 lần, sau ăn",
                }
            ]
        },
    )
    return [
        r[0]
        for r in sql(
            f"select id from prescription where visit_id='{vid}' and removed_at is null"
        )
    ]


def dam_bao_lo_thuoc(drug_catalog_id: str, so_luong: int = 500) -> str:
    co = sql(
        f"select id from drug_batch where drug_catalog_id='{drug_catalog_id}'"
        f" and quantity_on_hand >= {so_luong // 10} order by expiry_date limit 1"
    )
    if co:
        return co[0][0]
    ai("duocsi").post(
        "/pharmacy/receive",
        {
            "drug_catalog_id": drug_catalog_id,
            "so_luong": so_luong,
            "batch_code": f"MP-{uuid.uuid4().hex[:6]}",
            "expiry_date": (dt.date.today() + dt.timedelta(days=365)).isoformat(),
            "unit": "viên",
        },
    )
    return id_mot(
        f"select id from drug_batch where drug_catalog_id='{drug_catalog_id}'"
        " order by created_at desc limit 1"
    )


def phan_lo(vid: str, *, mua: int | None = None, nguoi: str = "duocsi") -> None:
    """Dược sĩ chốt số khách mua (nếu khác đơn) và chọn lô — TRƯỚC khi thu tiền."""
    for pres_id, drug_id, sl in sql(
        "select id, drug_catalog_id, coalesce(quantity_num, 0) from prescription"
        f" where visit_id='{vid}' and removed_at is null"
    ):
        so = float(mua if mua is not None else sl)
        if mua is not None:
            ai(nguoi).post("/pharmacy/so-luong-mua", {"prescription_id": pres_id, "so_luong": so})
        lo = dam_bao_lo_thuoc(drug_id)
        ai(nguoi).post("/pharmacy/phan-lo", {"prescription_id": pres_id, "drug_batch_id": lo, "so_luong": so})


def giao_thuoc(vid: str, nguoi: str = "duocsi") -> None:
    """Giao thuốc. Lần thu đã gắn lô → giao đúng lô ấy; không gắn lô (thu không
    chờ kho — chế độ đang chạy) → dược sĩ chọn lô lúc giao."""
    phan = sql(
        "select a.prescription_id, a.drug_batch_id, a.quantity - coalesce(a.handed_over_qty,0)"
        f" from prescription_allocation a where a.visit_id='{vid}'"
        " and a.released_at is null and a.payment_cycle_id is not null"
    )
    if phan:
        for pres_id, lo, sl in phan:
            if float(sl) > 0:
                ai(nguoi).post("/pharmacy/dispense", {"prescription_id": pres_id, "drug_batch_id": lo, "so_luong": float(sl)})
        return
    for pres_id, drug_id, sl in sql(
        "select id, drug_catalog_id, coalesce(purchased_qty, quantity_num, 0) - coalesce(dispensed_qty,0)"
        f" from prescription where visit_id='{vid}' and removed_at is null"
    ):
        if float(sl) > 0:
            lo = dam_bao_lo_thuoc(drug_id)
            ai(nguoi).post("/pharmacy/dispense", {"prescription_id": pres_id, "drug_batch_id": lo, "so_luong": float(sl)})


def checkout(vid: str, *, bo_ve: str | None = None, nguoi: str = "letan") -> Any:
    body: dict[str, Any] = {"visit_id": vid}
    if bo_ve:
        body |= {"incomplete": True, "incomplete_reason": bo_ve}
    return ai(nguoi).post("/reception/checkout", body, headers=khoa())
