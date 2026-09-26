"""Mô phỏng 20 khách đi qua phòng khám bằng API THẬT, rồi tự kiểm log + dữ liệu.

    scripts/dev-up.sh                      # stack local đang chạy (API, worker, web)
    .venv/bin/python scripts/mo-phong/mo_phong.py          # chạy cả 20
    .venv/bin/python scripts/mo-phong/mo_phong.py K01 K07  # chạy vài kịch bản

Mỗi kịch bản là một người khách với một chuyện có thể xảy ra ngoài đời (huỷ lịch,
về sớm, gián đoạn, bấm đúp thu tiền…). Mọi bước gọi đúng API giao diện gọi, bằng
tài khoản thử của đúng vai. Cuối cùng in báo cáo:
  * từng bước: được / hỏng (kèm câu lỗi của hệ thống);
  * log API từ lúc bắt đầu: 5xx, Traceback;
  * sổ sự kiện: tin nào chưa giao xong / chết;
  * bất biến dữ liệu: lượt treo, chỉ định đã trả tiền mà không phòng, hàng chờ
    của lượt đã đóng, tiền thu lệch hoá đơn…
Báo cáo JSON ghi vào `.dev-logs/mo-phong-<giờ>.json`.

CHỈ LOCAL (kiểm ở `ket_noi.kiem_chi_local`). Không ghi thẳng database.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

import buoc as b  # noqa: E402
from ket_noi import REPO, LoiApi, kiem_chi_local, sql  # noqa: E402

SA = "CLS_SIEU_AM_2D_TC_BT"
XN_DOI_TAC = "CLS_XET_NGHIEM_MAU"
NUOC_TIEU = "CLS_NUOC_TIEU"


@dataclass
class Khach:
    ma: str
    mo_ta: str
    buoc: list[dict[str, Any]] = field(default_factory=list)
    pid: str | None = None
    aid: str | None = None
    vid: str | None = None
    hong: bool = False

    def lam(self, ten: str, fn: Callable[[], Any], *, mong_loi: int | None = None) -> Any:
        """Chạy một bước. `mong_loi` = bước này PHẢI bị hệ thống từ chối (mã HTTP)."""
        if self.hong:
            self.buoc.append({"buoc": ten, "kq": "BỎ QUA"})
            return None
        t = time.monotonic()
        try:
            kq = fn()
        except LoiApi as e:
            ms = int((time.monotonic() - t) * 1000)
            if mong_loi and e.ma == mong_loi:
                self.buoc.append({"buoc": ten, "kq": "BỊ CHẶN ĐÚNG", "ma": e.ma, "ms": ms,
                                  "loi": _gon(e.noi_dung)})
                return None
            self.hong = True
            self.buoc.append({"buoc": ten, "kq": "HỎNG", "ma": e.ma, "ms": ms, "loi": _gon(e.noi_dung)})
            return None
        except Exception as e:  # noqa: BLE001 — ghi lại, sang khách khác
            self.hong = True
            self.buoc.append({"buoc": ten, "kq": "HỎNG", "loi": f"{type(e).__name__}: {e}",
                              "vet": traceback.format_exc(limit=3)})
            return None
        ms = int((time.monotonic() - t) * 1000)
        if mong_loi:
            self.hong = True
            self.buoc.append({"buoc": ten, "kq": "LẼ RA PHẢI BỊ CHẶN", "ms": ms})
            return kq
        self.buoc.append({"buoc": ten, "kq": "OK", "ms": ms})
        return kq


def _gon(x: Any) -> str:
    s = json.dumps(x, ensure_ascii=False, default=str) if not isinstance(x, str) else x
    return s[:300]


# ── Nền: khách tới, đo, khám ──────────────────────────────────────────────


def _den_kham(k: Khach, phut: int, *, bac_si: str = "bs.a", dich_vu: str = "PHU_KHOA") -> str | None:
    k.pid = k.lam("tạo khách", lambda: b.tao_khach(f"Mô Phỏng {k.ma}"))
    k.aid = k.lam("CSKH đặt lịch", lambda: b.dat_lich(k.pid, phut=phut, bac_si=bac_si, dich_vu=dich_vu))
    k.vid = k.lam("lễ tân check-in", lambda: b.check_in(k.aid))
    k.lam("điều dưỡng đo sinh hiệu", lambda: b.do_sinh_hieu(k.vid))
    return k.lam("bác sĩ bắt đầu khám", lambda: b.bat_dau_kham(k.vid, bac_si))  # type: ignore[no-any-return]


def _chi_dinh_va_thu(k: Khach, ph: str, ma: list[str], *, nguoi_thu: str = "letan",
                     chon: Callable[[list[str]], list[str]] | None = None) -> list[str]:
    oids = k.lam(f"chỉ định {', '.join(ma)}", lambda: b.chi_dinh_dv(ph, ma)) or []
    k.lam("bác sĩ Hoàn tất (bàn giao làm dịch vụ)", lambda: b.kham_xong(ph))
    k.lam("lễ tân chốt khách chọn dịch vụ",
          lambda: b.chon_dv(k.vid, None if chon is None else chon(oids)))
    k.lam(f"{nguoi_thu} thu tiền dịch vụ", lambda: b.thu(k.vid, "dich_vu", nguoi_thu))
    return list(oids)


def _ket_thuc(k: Khach, *, thuoc: bool = True, mua: int | None = None) -> None:
    k.lam("bác sĩ đọc kết quả + Hoàn tất vòng đọc", lambda: b.doc_ket_qua_va_xong(k.vid))
    if thuoc:
        k.lam("bác sĩ kê đơn", lambda: b.ke_don(k.vid))
        k.lam("thu tiền thuốc (không chờ chọn lô)", lambda: b.thu(k.vid, "thuoc", "letan"))
        k.lam("dược sĩ giao thuốc", lambda: b.giao_thuoc(k.vid))
    k.lam("lễ tân check-out", lambda: b.checkout(k.vid))


# ── 20 kịch bản ───────────────────────────────────────────────────────────


def k01(k: Khach) -> None:
    ph = _den_kham(k, 0)
    sa, xn = _chi_dinh_va_thu(k, ph, [SA, XN_DOI_TAC])[:2] if ph else (None, None)
    k.lam("hệ thống tự xếp phòng siêu âm", lambda: b.cho_phong(k.vid, sa))
    k.lam("BS siêu âm làm + phiếu kết quả", lambda: b.lam_tron(sa))
    k.lam("tự xếp phòng lấy mẫu", lambda: b.cho_phong(k.vid, xn))
    k.lam("điều dưỡng lấy mẫu máu", lambda: b.lam_tron(xn, "dd.sa"))
    k.lam("đối tác nhận mẫu + trả tệp kết quả", lambda: b.doi_tac_tra_ket_qua(xn))
    _ket_thuc(k)


def k02(k: Khach) -> None:
    ph = _den_kham(k, 15)
    k.lam("bác sĩ Hoàn tất — không chỉ định", lambda: b.kham_xong(ph))
    k.lam("lễ tân chốt (không có dịch vụ)", lambda: None)
    k.lam("thu tiền khám", lambda: b.thu(k.vid, "dich_vu", "letan"))
    k.lam("lễ tân check-out", lambda: b.checkout(k.vid))


def k03(k: Khach) -> None:
    ph = _den_kham(k, 30)
    (sa,) = _chi_dinh_va_thu(k, ph, [SA], nguoi_thu="thungan")[:1] or (None,)
    # Thu ngân MẶC ĐỊNH có điều phối (Tuyền 24/09) → thu xong tự xếp (H4).
    k.lam("thu ngân thu → hệ thống tự xếp phòng", lambda: b.cho_phong(k.vid, sa))
    k.lam("quầy thu đổi phòng sau khi thu (P3)",
          lambda: b.xep_tay(sa, "thungan", nguon="quay_thu", doi_phong=True))
    k.lam("trưởng ca đổi phòng tay — đè quầy thu",
          lambda: b.xep_tay(sa, nguon="truong_ca", doi_phong=True))
    k.lam("quầy thu đổi SAU trưởng ca → bị chặn",
          lambda: b.xep_tay(sa, "thungan", nguon="quay_thu", doi_phong=True), mong_loi=409)
    k.lam("BS siêu âm làm + phiếu", lambda: b.lam_tron(sa))
    _ket_thuc(k, thuoc=False)


def k04(k: Khach) -> None:
    ph = _den_kham(k, 45)
    oids = _chi_dinh_va_thu(k, ph, [SA, NUOC_TIEU], chon=lambda o: o[:1]) if ph else []
    sa = oids[0] if oids else None
    k.lam("chỉ định khách bỏ không bị xếp phòng",
          lambda: time.sleep(3) or all(c["phong_id"] is None for c in b.luot(k.vid)["chi_dinh"] if c["id"] != sa) or (_ for _ in ()).throw(AssertionError("chỉ định bỏ vẫn xếp")))
    k.lam("tự xếp phòng phần đã chọn", lambda: b.cho_phong(k.vid, sa))
    k.lam("làm phần đã chọn", lambda: b.lam_tron(sa))
    _ket_thuc(k, thuoc=False)


def k05(k: Khach) -> None:
    ph = _den_kham(k, 60)
    (sa,) = _chi_dinh_va_thu(k, ph, [SA])[:1] or (None,)
    k.lam("tự xếp phòng", lambda: b.cho_phong(k.vid, sa))
    a1 = k.lam("bắt đầu siêu âm", lambda: b.bat_dau_lam(sa))
    k.lam("GIÁN ĐOẠN (máy hỏng)", lambda: b.ai("bs.sa").post(
        f"/luot-kham/orders/{sa}/execution/gian-doan",
        {"attempt_id": a1, "expected_execution_revision": b._thuc_hien(sa, "bs.sa")["execution_revision"],
         "ly_do": "EQUIPMENT_FAILURE"}, headers=b.khoa()))
    k.lam("chuẩn bị làm lại", lambda: b.ai("bs.sa").post(
        f"/luot-kham/orders/{sa}/execution/lam-lai",
        {"interrupted_attempt_id": a1, "expected_execution_revision": b._thuc_hien(sa, "bs.sa")["execution_revision"]},
        headers=b.khoa()))
    k.lam("làm lại + phiếu + xong", lambda: b.lam_tron(sa))
    _ket_thuc(k, thuoc=False)


def k06(k: Khach) -> None:
    ph = _den_kham(k, 75)
    (sa,) = _chi_dinh_va_thu(k, ph, [SA])[:1] or (None,)
    k.lam("tự xếp phòng", lambda: b.cho_phong(k.vid, sa))
    k.lam("KHÔNG LÀM (khách từ chối lúc vào phòng)", lambda: b.ai("bs.sa").post(
        f"/luot-kham/orders/{sa}/execution/khong-lam",
        {"expected_execution_revision": b._thuc_hien(sa, "bs.sa")["execution_revision"],
         "ly_do": "PATIENT_DECLINED_AT_ROOM"}, headers=b.khoa()))
    _ket_thuc(k, thuoc=False)


def k07(k: Khach) -> None:
    ph = _den_kham(k, 90)
    (sa,) = _chi_dinh_va_thu(k, ph, [SA])[:1] or (None,)
    k.lam("khách VỀ SỚM trước khi siêu âm", lambda: b.checkout(k.vid, bo_ve="Khách có việc gấp"))
    k.lam("lượt ghi nhận còn việc dở", lambda: sql(
        f"select status from visit where visit_id='{k.vid}'")[0][0] in ("INCOMPLETE",) or (_ for _ in ()).throw(AssertionError(sql(f"select status from visit where visit_id='{k.vid}'"))))


def k08(k: Khach) -> None:
    k.pid = k.lam("tạo khách", lambda: b.tao_khach(f"Mô Phỏng {k.ma}"))
    k.aid = k.lam("đặt lịch", lambda: b.dat_lich(k.pid, phut=105))
    k.lam("CSKH HUỶ lịch (khách báo khi xác nhận)", lambda: b.doi_lich(
        k.aid, action="cancel", cancellation_reason="Khách bận", ly_do_huy_ma="BAO_KHI_XAC_NHAN"))
    k.lam("check-in lịch đã huỷ phải bị chặn", lambda: b.check_in(k.aid), mong_loi=409)


def k09(k: Khach) -> None:
    k.pid = k.lam("tạo khách", lambda: b.tao_khach(f"Mô Phỏng {k.ma}"))
    k.aid = k.lam("đặt lịch", lambda: b.dat_lich(k.pid, phut=120))
    k.lam("lễ tân ghi KHÔNG ĐẾN", lambda: b.doi_lich(k.aid, action="no_show", nguoi="letan"))


def k10(k: Khach) -> None:
    k.pid = k.lam("tạo khách", lambda: b.tao_khach(f"Mô Phỏng {k.ma}"))
    k.aid = k.lam("đặt lịch 10:15", lambda: b.dat_lich(k.pid, phut=135))
    moi = b.gio_hom_nay(150)
    k.lam("CSKH DỜI lịch sang 10:30", lambda: b.doi_lich(
        k.aid, action="reschedule", slot_start=moi.isoformat(),
        slot_end=(moi + dt.timedelta(minutes=15)).isoformat()))
    k.vid = k.lam("check-in lịch đã dời", lambda: b.check_in(k.aid))
    k.lam("đo sinh hiệu", lambda: b.do_sinh_hieu(k.vid))
    ph = k.lam("bác sĩ khám", lambda: b.bat_dau_kham(k.vid))
    k.lam("Hoàn tất không chỉ định", lambda: b.kham_xong(ph))
    k.lam("thu tiền khám", lambda: b.thu(k.vid))
    k.lam("check-out", lambda: b.checkout(k.vid))


def k11(k: Khach) -> None:
    k.pid = k.lam("tạo khách", lambda: b.tao_khach(f"Mô Phỏng {k.ma}"))
    k.aid = k.lam("đặt lịch BS A", lambda: b.dat_lich(k.pid, phut=165))
    k.vid = k.lam("check-in", lambda: b.check_in(k.aid))
    bs_sa = b.id_mot("select s.id from staff s join auth.users u on u.id=s.auth_user_id where u.email='bs.sa@dr4women.local'")
    # Chạy lại được: thu hai khối cấp ở lần chạy trước (có thể chưa từng cấp).
    for khoi in ("kham", "hoan_tat_kham"):
        try:
            b.ai("ql").post(f"/phan-quyen/nhan-su/{bs_sa}/thu", {"khoi": khoi, "ly_do": "Đặt lại mô phỏng"})
        except LoiApi:
            pass
    doi = lambda: b.ai("truongca").post(  # noqa: E731
        "/dispatch/doi-bac-si", {"visit_id": k.vid, "bac_si_moi_id": bs_sa, "ly_do": "BS A quá tải"}, headers=b.khoa())
    # BS siêu âm chưa có khối Khám → hệ thống phải chặn (không để khách kẹt).
    k.lam("đổi sang BS SA khi BS SA CHƯA có khối Khám → bị chặn", doi, mong_loi=422)
    for khoi in ("kham", "hoan_tat_kham"):
        k.lam(f"quản lý cấp khối {khoi} cho BS SA", lambda khoi=khoi: b.ai("ql").post(
            f"/phan-quyen/nhan-su/{bs_sa}/cap", {"khoi": khoi, "ly_do": "Hỗ trợ khám hôm nay"}))
    k.lam("trưởng ca ĐỔI BÁC SĨ sang BS SA", doi)
    k.lam("đo sinh hiệu", lambda: b.do_sinh_hieu(k.vid))
    ph = k.lam("BS SA khám (bác sĩ mới)", lambda: b.bat_dau_kham(k.vid, "bs.sa"))
    k.lam("BS SA Hoàn tất", lambda: b.kham_xong(ph, "bs.sa"))
    k.lam("thu tiền khám", lambda: b.thu(k.vid))
    k.lam("check-out", lambda: b.checkout(k.vid))


def k12(k: Khach) -> None:
    ph = _den_kham(k, 180)
    k.lam("thư ký nhập phiếu khám thay bác sĩ", lambda: _thu_ky_nhap(k.vid))
    k.lam("bác sĩ Hoàn tất", lambda: b.kham_xong(ph))
    k.lam("thu tiền khám", lambda: b.thu(k.vid))
    k.lam("check-out", lambda: b.checkout(k.vid))


def _thu_ky_nhap(vid: str) -> Any:
    u = b.ai("thuky")
    hien = u.get(f"/phieu-kham/luot/{vid}/phieu")
    form = hien.get("form_id") or (hien.get("chon_duoc") or [{}])[0].get("form_id")
    khung = hien.get("khung") or []
    o = next((bl["ma"] for m in khung for bl in m.get("block", []) if bl.get("kieu") in ("text", "textarea")), None)
    if o is None:
        raise AssertionError(f"phiếu {form} không có ô chữ nào: {list(hien)}")
    return u.goi("PUT", f"/phieu-kham/luot/{vid}/phieu", json={
        "form_id": form, "du_lieu": {o: {"gia_tri": "Thư ký nhập: đau bụng dưới 3 ngày", "nguon": "USER"}},
        "expected_revision": hien.get("revision", 0)})


def k13(k: Khach) -> None:
    ph = _den_kham(k, 195)
    k.lam("chỉ định siêu âm", lambda: b.chi_dinh_dv(ph, [SA]))
    k.lam("Hoàn tất", lambda: b.kham_xong(ph))
    k.lam("chốt chọn", lambda: b.chon_dv(k.vid))
    r = k.lam("thu tiền", lambda: b.thu(k.vid))
    k.lam("HUỶ phiếu thu (thu nhầm)", lambda: b.ai("letan").goi("DELETE", "/payments", json={
        "payment_cycle_id": r["payment_cycle_id"], "visit_id": k.vid, "kind": "dich_vu", "reason": "Thu nhầm số"}))
    # FINANCE-GATE v1: PAID→VOIDED → "cần xem xét tài chính", KHÔNG tự thu lại.
    # Cách xử lý sau đó hợp đồng ghi "Chưa chốt" — chờ Tuyền quyết.
    k.lam("thu lại phải bị chặn (chờ chính sách xử lý phiếu huỷ)", lambda: b.thu(k.vid), mong_loi=422)


def k14(k: Khach) -> None:
    ph = _den_kham(k, 210)
    k.lam("Hoàn tất", lambda: b.kham_xong(ph))
    k.lam("QUẢN LÝ mở hồ sơ y khoa", lambda: b.ai("ql").get(f"/clinical-records/doc?patient_id={k.pid}"))
    k.lam("hồ sơ QL mở có nhật ký", lambda: int(sql(
        "select count(*) from event_log where event_type='clinical_record.opened'"
        f" and aggregate_id='{k.pid}'")[0][0]) >= 1 or (_ for _ in ()).throw(AssertionError("không có nhật ký")))
    k.lam("LỄ TÂN mở hồ sơ y khoa phải bị chặn",
          lambda: b.ai("letan").get(f"/clinical-records/doc?patient_id={k.pid}"), mong_loi=403)
    k.lam("thu tiền", lambda: b.thu(k.vid))
    k.lam("check-out", lambda: b.checkout(k.vid))


def k15(k: Khach) -> None:
    ph = _den_kham(k, 225)
    k.lam("Hoàn tất", lambda: b.kham_xong(ph))
    k.lam("thu tiền khám", lambda: b.thu(k.vid, "dich_vu", "letan"))
    k.lam("bác sĩ kê đơn 10", lambda: b.ke_don(k.vid, 10))
    r = k.lam("thu tiền thuốc theo đơn kê (10)", lambda: b.thu(k.vid, "thuoc"))
    rx = (b.sql(f"select id from prescription where visit_id='{k.vid}' and removed_at is null") or [[None]])[0][0]
    k.lam("khách đổi ý chỉ mua 4 khi đã thu → hệ thống chặn sửa",
          lambda: b.ai("duocsi").post("/pharmacy/so-luong-mua", {"prescription_id": rx, "so_luong": 4}),
          mong_loi=409)
    k.lam("huỷ phiếu thu thuốc", lambda: b.ai("letan").goi("DELETE", "/payments", json={
        "payment_cycle_id": r["payment_cycle_id"], "visit_id": k.vid, "kind": "thuoc",
        "reason": "Khách đổi số lượng mua"}))
    k.lam("dược sĩ chốt khách mua 4", lambda: b.ai("duocsi").post(
        "/pharmacy/so-luong-mua", {"prescription_id": rx, "so_luong": 4}))
    k.lam("thu lại tiền thuốc (4)", lambda: b.thu(k.vid, "thuoc"))
    k.lam("giao 4", lambda: b.giao_thuoc(k.vid))
    k.lam("đã giao đúng 4", lambda: float(b.sql(f"select dispensed_qty from prescription where id='{rx}'")[0][0]) == 4
          or (_ for _ in ()).throw(AssertionError(b.sql(f"select dispensed_qty, purchased_qty from prescription where id='{rx}'"))))
    k.lam("check-out", lambda: b.checkout(k.vid))


def k16(k: Khach) -> None:
    ph = _den_kham(k, 240)
    (sa,) = _chi_dinh_va_thu(k, ph, [SA])[:1] or (None,)
    k.lam("tự xếp phòng", lambda: b.cho_phong(k.vid, sa))
    k.lam("làm + phiếu", lambda: b.lam_tron(sa))
    k.lam("ĐÍNH CHÍNH kết quả (mở sửa → lưu → Hoàn tất lại)", lambda: _dinh_chinh(sa))
    _ket_thuc(k, thuoc=False)


def _dinh_chinh(oid: str) -> Any:
    u = b.ai("bs.sa")
    pid = b.id_mot(f"select id from form_instance where service_order_id='{oid}' order by tao_luc desc limit 1")
    p = u.post(f"/phieu/{pid}/mo-sua")
    rev = p.get("revision", 0)
    p = u.post(f"/phieu/{pid}/luu", {"du_lieu": {next(iter(p.get("du_lieu") or {}), "ghi_chu"): {"gia_tri": "Đính chính: nang nhỏ 5mm.", "nguon": "USER"}}, "expected_revision": rev})
    return u.post(f"/phieu/{pid}/hoan-tat", {"expected_revision": p.get("revision", rev + 1),
                                             "ly_do_sua": "Đọc lại hình"})


def k17(k: Khach) -> None:
    ph = _den_kham(k, 255)
    k.lam("Hoàn tất", lambda: b.kham_xong(ph))
    key = "mo-phong-bam-dup-" + (k.vid or "")
    r1 = k.lam("thu tiền (bấm lần 1)", lambda: b.thu(k.vid, key=key))
    r2 = k.lam("thu tiền (BẤM ĐÚP, cùng khoá)", lambda: b.thu(k.vid, key=key))
    k.lam("bấm đúp chỉ ra MỘT phiếu thu", lambda: (r1 or {}).get("payment_cycle_id") == (r2 or {}).get("payment_cycle_id")
          and int(sql(f"select count(*) from payment_cycle where visit_id='{k.vid}' and status='PAID'")[0][0]) == 1
          or (_ for _ in ()).throw(AssertionError(sql(f"select payment_cycle_id,status,amount from payment_cycle where visit_id='{k.vid}'"))))
    k.lam("check-out", lambda: b.checkout(k.vid))


def k18(k: Khach) -> None:
    ph = _den_kham(k, 270)
    (sa,) = _chi_dinh_va_thu(k, ph, [SA])[:1] or (None,)
    k.lam("tự xếp phòng", lambda: b.cho_phong(k.vid, sa))
    k.lam("làm + phiếu", lambda: b.lam_tron(sa))
    p = k.lam("phiên đọc kết quả vào hàng", lambda: b.cho(lambda: b._phien_cho(k.vid, {"REVIEW"}), giay=25))
    k.lam("bác sĩ bắt đầu đọc", lambda: b.ai("bs.a").post(f"/luot-kham/consultations/{p['id']}/start"))
    oids = k.lam("CHỈ ĐỊNH THÊM vòng 2 (nước tiểu)", lambda: b.chi_dinh_dv(p["id"], [NUOC_TIEU])) or []
    k.lam("Hoàn tất vòng đọc (mở vòng 3)", lambda: b.kham_xong(p["id"]))
    k.lam("chốt chọn chỉ định mới", lambda: b.chon_dv(k.vid))
    k.lam("thu tiền phần thêm", lambda: b.thu(k.vid))
    k.lam("tự xếp phòng lấy mẫu", lambda: b.cho_phong(k.vid, oids[0]))
    k.lam("điều dưỡng lấy mẫu + phiếu", lambda: b.lam_tron(oids[0], "dd.sa"))
    k.lam("đối tác trả kết quả nước tiểu", lambda: b.doi_tac_tra_ket_qua(oids[0]))
    _ket_thuc(k, thuoc=False)


def k19(k: Khach) -> None:
    k.pid = k.lam("tạo khách", lambda: b.tao_khach(f"Mô Phỏng {k.ma}"))
    k.aid = k.lam("đặt lịch", lambda: b.dat_lich(k.pid, phut=285))
    sid = b.id_mot("select s.id from staff s join auth.users u on u.id=s.auth_user_id where u.email='danang@dr4women.local'")
    for khoi in ("tiep_don", "sinh_hieu", "thu_tien_dv"):
        k.lam(f"quản lý cấp khối {khoi} cho người đa vai", lambda khoi=khoi: b.ai("ql").post(
            f"/phan-quyen/nhan-su/{sid}/cap", {"khoi": khoi, "ly_do": "Đứng nhiều vị trí hôm nay"}))
    k.vid = k.lam("ĐA VAI check-in", lambda: b.check_in(k.aid, "danang"))
    k.lam("ĐA VAI đo sinh hiệu", lambda: b.do_sinh_hieu(k.vid, "danang"))
    ph = k.lam("bác sĩ khám", lambda: b.bat_dau_kham(k.vid))
    k.lam("Hoàn tất", lambda: b.kham_xong(ph))
    k.lam("ĐA VAI thu tiền", lambda: b.thu(k.vid, nguoi="danang"))
    k.lam("check-out", lambda: b.checkout(k.vid))


def k20(k: Khach) -> None:
    k.pid = k.lam("tạo khách", lambda: b.tao_khach(f"Mô Phỏng {k.ma}"))
    k.aid = k.lam("đặt lịch", lambda: b.dat_lich(k.pid, phut=300))
    k.vid = k.lam("check-in", lambda: b.check_in(k.aid))
    k.lam("check-in LẦN HAI cùng lịch phải bị chặn", lambda: b.check_in(k.aid), mong_loi=409)
    k.lam("check-out ngay khi chưa khám (khách đổi ý)", lambda: b.checkout(k.vid, bo_ve="Khách đổi ý không khám"))


def k21(k: Khach) -> None:
    """Điều dưỡng tick "Bỏ qua bác sĩ tư vấn" → khách vào thẳng bác sĩ chính."""
    k.pid = k.lam("tạo khách", lambda: b.tao_khach(f"Mô Phỏng {k.ma}"))
    k.aid = k.lam("CSKH đặt lịch", lambda: b.dat_lich(k.pid, phut=45))
    k.vid = k.lam("lễ tân check-in", lambda: b.check_in(k.aid))
    k.lam("điều dưỡng đo sinh hiệu", lambda: b.do_sinh_hieu(k.vid))
    k.lam("điều dưỡng tick BỎ QUA tư vấn", lambda: b.bo_qua_tu_van(k.vid))
    ph = k.lam("vào thẳng bác sĩ chính (không qua phiên TU_VAN)", lambda: (
        b.cho(lambda: b._phien_cho(k.vid, {"PRIMARY"}), mo_ta="phiên chính vào hàng")
        and b.bat_dau_kham(k.vid)))
    k.lam("bác sĩ Hoàn tất — không chỉ định", lambda: b.kham_xong(ph))
    k.lam("thu tiền khám", lambda: b.thu(k.vid))
    k.lam("check-out", lambda: b.checkout(k.vid))


def k22(k: Khach) -> None:
    """Chỉ định "Bắt buộc": quầy thu bỏ → bị chặn; bác sĩ bỏ tick → bỏ được;
    thu xong → không đổi bắt buộc được nữa."""
    ph = _den_kham(k, 60)
    sa, xn = k.lam("chỉ định SA (BẮT BUỘC) + XN", lambda: b.dat_chi_dinh(
        ph, [SA, XN_DOI_TAC], bat_buoc=[SA])) or (None, None)
    k.lam("bác sĩ Hoàn tất", lambda: b.kham_xong(ph))
    k.lam("quầy thu BỎ dịch vụ bắt buộc → bị chặn",
          lambda: b.chon_dv(k.vid, [xn]), mong_loi=409)
    k.lam("bác sĩ bỏ tick bắt buộc", lambda: b.doi_bat_buoc(sa, False))
    k.lam("bác sĩ tick lại bắt buộc", lambda: b.doi_bat_buoc(sa, True))
    k.lam("quầy thu bỏ XN (không bắt buộc) — được", lambda: b.chon_dv(k.vid, [sa]))
    k.lam("thu tiền dịch vụ", lambda: b.thu(k.vid, "dich_vu", "letan"))
    k.lam("đã thu → đổi bắt buộc bị chặn",
          lambda: b.doi_bat_buoc(sa, False), mong_loi=409)
    k.lam("hệ thống tự xếp phòng siêu âm", lambda: b.cho_phong(k.vid, sa))
    k.lam("BS siêu âm làm + phiếu", lambda: b.lam_tron(sa))
    _ket_thuc(k, thuoc=False)


KICH_BAN: dict[str, tuple[str, Callable[[Khach], None]]] = {
    "K01": ("Luồng đủ: SA + XN đối tác → đọc KQ → thuốc → về", k01),
    "K02": ("Khám không chỉ định", k02),
    "K03": ("Thu ngân thu → tự xếp → trưởng ca đè, quầy thu bị khoá", k03),
    "K04": ("Khách bỏ bớt 1 chỉ định", k04),
    "K05": ("Gián đoạn → làm lại", k05),
    "K06": ("Đã thu tiền nhưng không làm", k06),
    "K07": ("Khách về sớm còn việc dở", k07),
    "K08": ("Huỷ lịch rồi cố check-in", k08),
    "K09": ("Không đến", k09),
    "K10": ("Dời lịch rồi đến khám", k10),
    "K11": ("Trưởng ca đổi bác sĩ", k11),
    "K12": ("Thư ký nhập phiếu khám thay bác sĩ", k12),
    "K13": ("Thu nhầm → huỷ phiếu thu → thu lại", k13),
    "K14": ("Quản lý mở hồ sơ (nhật ký) · lễ tân bị chặn", k14),
    "K15": ("Khách mua ít thuốc hơn kê", k15),
    "K16": ("Đính chính kết quả", k16),
    "K17": ("Bấm đúp thu tiền", k17),
    "K18": ("Chỉ định thêm ở vòng đọc", k18),
    "K19": ("Một người đa vai: tiếp đón + đo + thu", k19),
    "K20": ("Check-in hai lần · khách đổi ý về", k20),
    "K21": ("Điều dưỡng bỏ qua tư vấn → thẳng bác sĩ chính", k21),
    "K22": ("Chỉ định bắt buộc: quầy thu không bỏ được", k22),
}


# ── Kiểm cuối ─────────────────────────────────────────────────────────────


def kiem_cuoi(bat_dau: dt.datetime, khach: list[Khach]) -> dict[str, Any]:
    moc = bat_dau.isoformat()
    vids = [k.vid for k in khach if k.vid]
    ds = ",".join(f"'{v}'" for v in vids) or "NULL"
    kq: dict[str, Any] = {}
    kq["su_kien_chua_xong"] = sql(
        "select d.consumer, e.event_type, d.status, d.attempts, left(coalesce(d.last_error,''),160)"
        " from event_delivery d join domain_event e on e.event_id=d.event_id"
        f" where e.recorded_at >= '{moc}' and d.status <> 'DONE' order by e.seq")
    kq["so_su_kien"] = sql(
        f"select event_type, count(*) from domain_event where recorded_at >= '{moc}'"
        " group by 1 order by 2 desc")
    kq["luot"] = sql(
        "select v.visit_id, p.full_name, v.status, v.closed_at is not null,"
        " (select count(*) from service_order o where o.visit_id=v.visit_id),"
        " (select count(*) from queue_entry q where q.visit_id=v.visit_id and q.status in ('waiting','serving','blocked'))"
        f" from visit v join patient p on p.clinic_patient_id=v.clinic_patient_id where v.visit_id in ({ds})"
        " order by p.full_name")
    kq["bat_bien"] = {
        "hang_cho_cua_luot_da_dong": sql(
            "select q.visit_id, q.status from queue_entry q join visit v on v.visit_id=q.visit_id"
            f" where q.visit_id in ({ds}) and v.closed_at is not null"
            " and q.status in ('waiting','serving','blocked')"),
        "da_tra_tien_chua_phong": sql(
            "select o.visit_id, o.service_code from service_order o"
            f" where o.visit_id in ({ds}) and o.selection_status='SELECTED'"
            " and coalesce(o.routing_status,'UNASSIGNED')='UNASSIGNED'"
            " and o.exec_status='authorized' and coalesce(o.execution_status,'PENDING')='PENDING'"
            " and exists (select 1 from payment_cycle c where c.visit_id=o.visit_id and c.kind='dich_vu' and c.status='PAID')"
            # Khách về sớm (INCOMPLETE): dịch vụ đã trả mang sang lượt sau — đúng thiết kế.
            " and (select status from visit where visit_id=o.visit_id) <> 'INCOMPLETE'"
            " and not exists (select 1 from service_price sp where sp.clinic_id=o.clinic_id"
            "   and sp.service_code=o.service_code and sp.doi_tac_lay_mau)"),
        "giao_thuoc_vuot_mua": sql(
            "select p.visit_id, p.purchased_qty, coalesce(sum(a.quantity),0) from prescription p"
            " left join prescription_allocation a on a.prescription_id=p.id"
            f" where p.visit_id in ({ds}) and p.purchased_qty is not null"
            " group by 1,2 having coalesce(sum(a.quantity),0) > p.purchased_qty"),
    }
    log = REPO / ".dev-logs" / "api.log"
    loi: list[str] = []
    if log.exists():
        for dong in log.read_text(errors="replace").splitlines()[-20000:]:
            if ("Traceback" in dong or '"level": "error"' in dong or " 500 " in dong):
                loi.append(dong[:300])
    kq["log_api_loi"] = loi[-40:]
    wlog = REPO / ".dev-logs" / "su-kien.log"
    kq["log_worker_loi"] = [d[:300] for d in (wlog.read_text(errors="replace").splitlines()[-5000:] if wlog.exists() else [])
                            if "Traceback" in d or '"level": "error"' in d or "ERROR" in d][-30:]
    return kq


def main(chon: list[str]) -> int:
    kiem_chi_local()
    bat_dau = dt.datetime.now(dt.timezone.utc)
    khach: list[Khach] = []
    for ma, (mo_ta, fn) in KICH_BAN.items():
        if chon and ma not in chon:
            continue
        k = Khach(ma, mo_ta)
        print(f"\n▶ {ma} — {mo_ta}", flush=True)
        try:
            fn(k)
        except Exception as e:  # noqa: BLE001
            k.hong = True
            k.buoc.append({"buoc": "(kịch bản)", "kq": "HỎNG", "loi": f"{type(e).__name__}: {e}"})
        for s in k.buoc:
            dau = {"OK": "✓", "BỊ CHẶN ĐÚNG": "✓", "BỎ QUA": "·"}.get(s["kq"], "✗")
            print(f"  {dau} {s['buoc']}" + (f"  [{s.get('ma', '')}] {s.get('loi', '')}" if dau == "✗" else ""), flush=True)
        khach.append(k)
    time.sleep(3)  # cho worker giao nốt tin
    kq = kiem_cuoi(bat_dau, khach)
    bao_cao = {
        "bat_dau": bat_dau.isoformat(),
        "khach": [{"ma": k.ma, "mo_ta": k.mo_ta, "vid": k.vid, "hong": k.hong, "buoc": k.buoc} for k in khach],
        "kiem_cuoi": kq,
    }
    ra = REPO / ".dev-logs" / f"mo-phong-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    ra.parent.mkdir(exist_ok=True)
    ra.write_text(json.dumps(bao_cao, ensure_ascii=False, indent=2, default=str))
    so_hong = sum(k.hong for k in khach)
    print(f"\n══ {len(khach) - so_hong}/{len(khach)} kịch bản trọn vẹn · báo cáo: {ra}")
    print(f"   sự kiện chưa giao xong: {len(kq['su_kien_chua_xong'])}")
    for ten, ds in kq["bat_bien"].items():
        print(f"   bất biến {ten}: {len(ds)}")
    print(f"   log API lỗi: {len(kq['log_api_loi'])} · log worker lỗi: {len(kq['log_worker_loi'])}")
    return 1 if so_hong else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
