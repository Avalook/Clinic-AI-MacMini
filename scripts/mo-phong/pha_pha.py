"""PHA PHÁ — cố tình làm sai, làm cùng lúc, làm vượt quyền. Tìm lỗ hổng.

Mỗi phép thử dùng khách RIÊNG (không đụng câu chuyện của pha B).
"""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import buoc as b
import pha_kham as pk
from do_luong import NhatKyThaoTac
from ket_noi import LoiApi, sql


def _cung_luc(fns: list[Any]) -> list[str]:
    """Chạy các hàm ĐÚNG CÙNG LÚC (rào chắn), trả kết quả dạng 'OK' / mã lỗi."""
    rao = threading.Barrier(len(fns))
    ra: list[str] = [""] * len(fns)

    def chay(i: int) -> None:
        rao.wait()
        try:
            fns[i]()
            ra[i] = "OK"
        except LoiApi as e:
            ra[i] = f"{e.ma}:{str(e.noi_dung)[:90]}"
        except Exception as e:  # noqa: BLE001
            ra[i] = f"EXC:{e}"[:120]

    with ThreadPoolExecutor(len(fns)) as ex:
        list(ex.map(chay, range(len(fns))))
    return ra


def _khach_moi(nk: NhatKyThaoTac, ma: str, bs: str, phut: int) -> pk.Khach:
    k = pk.Khach(ma, "PHA", f"Phá {ma} MP")
    k.pid = b.tao_khach(k.ten)
    k.aid = b.dat_lich(k.pid, phut=phut, bac_si="bs.a")
    pk.den_va_check_in(nk, k)
    return k


def chay(nk: NhatKyThaoTac, nhan_su: dict[str, str]) -> dict[str, Any]:
    ket: dict[str, Any] = {}

    # P1 — hai bác sĩ cùng nhận MỘT khách tư vấn
    print("\n▶ P1 — BS tư vấn và BS chính cùng bấm nhận một khách tư vấn", flush=True)
    k = _khach_moi(nk, "P1", "bs.a", 600)
    if k.vid:
        pk.do_sinh_hieu(nk, k)
        r = pk.cho_hang("bs.tuvan", "/luot-kham/hang-cho?tu_van=true", k.vid, giay=20)
        kq = _cung_luc([lambda: b.ai("bs.tuvan").post(f"/luot-kham/consultations/{r['ref_id']}/start"),
                        lambda: b.ai("bs.a").post(f"/luot-kham/consultations/{r['ref_id']}/start")])
        ket["P1"] = kq
        nk.lam("he-thong", "P1", "đúng MỘT bác sĩ nhận được khách tư vấn",
               lambda: kq.count("OK") == 1 or (_ for _ in ()).throw(AssertionError(str(kq))), khach="P1")

    # P2 — hai phòng siêu âm cùng bấm bắt đầu MỘT chỉ định
    print("\n▶ P2 — hai phòng siêu âm cùng bắt đầu một chỉ định", flush=True)
    k = _khach_moi(nk, "P2", "bs.a", 615)
    if k.vid:
        pk.do_sinh_hieu(nk, k)
        pk.tu_van(nk, k)
        pk.bs_chinh_kham(nk, k, [pk.SA])
        pk.le_tan_thu(nk, k)
        if k.chi_dinh:
            oid = k.chi_dinh[0]
            phong = b.cho(lambda: b.chi_dinh(k.vid, oid)["phong_id"], giay=20)
            ex = b._thuc_hien(oid, "bs.sa")
            body = {"expected_execution_revision": ex["execution_revision"],
                    "expected_routing_revision": ex["routing_revision"]}
            kq = _cung_luc([lambda: b.ai("dd.sa").post(f"/luot-kham/orders/{oid}/execution/bat-dau", body, headers=pk.khoa()),
                            lambda: b.ai("dd.sa2").post(f"/luot-kham/orders/{oid}/execution/bat-dau", body, headers=pk.khoa())])
            ket["P2"] = {"phong": phong, "kq": kq}
            nk.lam("he-thong", "P2", "đúng MỘT lần làm được mở", lambda: kq.count("OK") == 1 or (_ for _ in ()).throw(
                AssertionError(str(kq))), khach="P2")
            so_lan = int(sql(f"select count(*) from service_execution_attempt where service_order_id='{oid}'")[0][0])
            nk.lam("he-thong", "P2", "chỉ có 1 lần làm trong DB", lambda: so_lan == 1 or (_ for _ in ()).throw(
                AssertionError(f"{so_lan} lần làm")), khach="P2")
            phong_dung = pk.PHONG_NGUOI.get(str(phong), ("", ""))[1]
            nguoi_thang = "dd.sa" if kq[0] == "OK" else "dd.sa2"
            ket["P2_phong_khac_bat_dau_duoc"] = nguoi_thang != phong_dung
            if nguoi_thang != phong_dung:
                nk.lam("he-thong", "P2", "người Ở PHÒNG KHÁC không bắt đầu được chỉ định đã xếp phòng này",
                       lambda: (_ for _ in ()).throw(AssertionError(
                           f"{nguoi_thang} (phòng khác) bắt đầu được chỉ định xếp cho {phong_dung}")), khach="P2")
            # dọn: hoàn tất để khách không treo
            try:
                a = b._thuc_hien(oid, "bs.sa")["lan_dang_chay"]["id"]
                b.dien_phieu(oid, "bs.sa")
                if b._thuc_hien(oid, "bs.sa").get("lan_dang_chay"):
                    b.xong_lam(oid, a, "dd.sa")
            except Exception:  # noqa: BLE001
                pass

    # P3 — bấm đúp thu tiền (hai khoá khác nhau)
    print("\n▶ P3 — lễ tân bấm thu tiền hai lần gần như cùng lúc", flush=True)
    k = _khach_moi(nk, "P3", "bs.a", 630)
    if k.vid:
        pk.do_sinh_hieu(nk, k)
        pk.tu_van(nk, k)
        pk.bs_chinh_kham(nk, k, [pk.SA])
        bang = b.ai("letan").get("/cashier/board?modes=dich_vu")
        dong = next((x for x in bang.get("items", []) if x.get("visit_id") == k.vid), {})
        cd = dong.get("chon_dich_vu") or {}
        ds = [c["id"] for c in cd.get("chi_dinh", [])]
        if ds:
            b.ai("letan").post(f"/luot-kham/visits/{k.vid}/service-selection/confirm",
                               {"order_ids_seen": ds, "selected_order_ids": ds,
                                "expected_selection_revision": int(cd.get("revision") or 0)}, headers=pk.khoa())
        kq = _cung_luc([lambda: b.ai("letan").post("/payments", {"visit_id": k.vid, "kind": "dich_vu", "method": "CASH"}, headers=pk.khoa()),
                        lambda: b.ai("letan").post("/payments", {"visit_id": k.vid, "kind": "dich_vu", "method": "CASH"}, headers=pk.khoa())])
        so = sql(f"select count(*), coalesce(sum(amount),0) from payment_cycle where visit_id='{k.vid}' and status='PAID'")[0]
        ket["P3"] = {"kq": kq, "so_phieu_paid": so[0], "tong": so[1]}
        nk.lam("he-thong", "P3", "bấm đúp: chỉ MỘT phiếu thu, không thu hai lần",
               lambda: int(so[0]) == 1 or (_ for _ in ()).throw(AssertionError(f"{so[0]} phiếu, tổng {so[1]}: {kq}")), khach="P3")

    # P4 — BS chính và thư ký cùng lưu phiếu khám một lúc
    print("\n▶ P4 — BS chính và thư ký cùng lưu phiếu khám (cùng revision)", flush=True)
    k = _khach_moi(nk, "P4", "bs.a", 645)
    if k.vid:
        pk.do_sinh_hieu(nk, k)
        pk.tu_van(nk, k)
        r = pk.cho_hang("bs.a", "/luot-kham/hang-cho", k.vid, lambda r: r.get("vong") == "PRIMARY", giay=40)
        b.ai("bs.a").post(f"/luot-kham/consultations/{r['ref_id']}/start")
        hien = b.ai("bs.a").get(f"/phieu-kham/luot/{k.vid}/phieu")
        form = hien.get("form_id") or (hien.get("chon_duoc") or [{}])[0].get("form_id")
        o = next((bl["ma"] for m in (hien.get("khung") or []) for bl in m.get("block", []) if bl.get("kieu") in ("text", "textarea")), "ghi_chu")

        def luu(u: str, chu: str) -> Any:
            return b.ai(u).goi("PUT", f"/phieu-kham/luot/{k.vid}/phieu", json={
                "form_id": form, "du_lieu": {o: {"gia_tri": chu, "nguon": "USER"}},
                "expected_revision": hien.get("revision", 0)})

        kq = _cung_luc([lambda: luu("bs.a", "BS ghi"), lambda: luu("thuky", "Thư ký ghi")])
        ket["P4"] = kq
        nk.lam("he-thong", "P4", "hai người lưu cùng revision → một người được, một người nhận 409",
               lambda: sorted(x[:3] for x in kq) == ["409", "OK"] or (_ for _ in ()).throw(AssertionError(str(kq))), khach="P4")
        b.ai("bs.a").post(f"/luot-kham/consultations/{r['ref_id']}/kham-xong")

    # P5 — sai vai / vượt quyền
    print("\n▶ P5 — làm việc không phải của mình", flush=True)
    k = _khach_moi(nk, "P5", "bs.a", 660)
    appt2 = b.dat_lich(b.tao_khach("Phá P5b MP"), phut=661, bac_si="bs.a")
    nk.lam("cskh", "P5", "CSKH bấm check-in (luật: CSKH không check-in)",
           lambda: b.ai("cskh").post("/luot-kham/check-in", {"appointment_id": appt2}), mong_loi=403, khach="P5")
    if k.vid:
        pk.do_sinh_hieu(nk, k)
        pk.tu_van(nk, k)
        r = pk.cho_hang("bs.a", "/luot-kham/hang-cho", k.vid, lambda r: r.get("vong") == "PRIMARY", giay=40)
        nk.lam("duocsi", "P5", "dược sĩ bắt đầu khám", lambda: b.ai("duocsi").post(
            f"/luot-kham/consultations/{r['ref_id']}/start"), mong_loi=403, khach="P5")
        nk.lam("letan", "P5", "lễ tân mở hồ sơ y khoa", lambda: b.ai("letan").get(
            f"/clinical-records/doc?patient_id={k.pid}"), mong_loi=403, khach="P5")
        nk.lam("doitac", "P5", "đối tác đọc bảng lượt khám của phòng khám", lambda: b.ai("doitac").get(
            "/luot-kham/bang"), mong_loi=403, khach="P5")
        nk.lam("dd.sa", "P5", "điều dưỡng siêu âm kê đơn thuốc", lambda: b.ke_don(k.vid, nguoi="dd.sa"),
               mong_loi=403, khach="P5")
        nk.lam("doitac", "P5", "đối tác gửi kết quả cho chỉ định KHÔNG phải của mình (mã bịa)",
               lambda: b.ai("doitac").goi("POST", "/doi-tac/ket-qua", data={"chi_dinh_id": str(uuid.uuid4())},
                                          files={"file": ("x.pdf", b"%PDF-1.4\n", "application/pdf")}),
               mong_loi=(403, 404), khach="P5")

    # P6 — khách đang ở phòng này, phòng kia gọi
    print("\n▶ P6 — khách đang siêu âm thì phòng thủ thuật bắt đầu", flush=True)
    k = _khach_moi(nk, "P6", "bs.a", 675)
    if k.vid:
        pk.do_sinh_hieu(nk, k)
        pk.tu_van(nk, k)
        pk.bs_chinh_kham(nk, k, [pk.SA, pk.THAO_VONG])
        pk.le_tan_thu(nk, k)
        if len(k.chi_dinh) == 2:
            for oid in k.chi_dinh:
                b.cho(lambda oid=oid: b.chi_dinh(k.vid, oid)["phong_id"], giay=20)
            p0 = str(b.chi_dinh(k.vid, k.chi_dinh[0])["phong_id"])
            p1 = str(b.chi_dinh(k.vid, k.chi_dinh[1])["phong_id"])
            dd0 = pk.PHONG_NGUOI.get(p0, ("", "dd.sa"))[1]
            dd1 = pk.PHONG_NGUOI.get(p1, ("", "dd.tt1"))[1]
            a = nk.lam(dd0, "P6", "phòng thứ nhất bắt đầu", lambda: b.bat_dau_lam(k.chi_dinh[0], dd0), khach="P6")
            nk.lam(dd1, "P6", "phòng thứ hai bắt đầu khi khách còn ở phòng thứ nhất → PATIENT_BUSY",
                   lambda: b.bat_dau_lam(k.chi_dinh[1], dd1), mong_loi=409, khach="P6")
            if a:
                b.dien_phieu(k.chi_dinh[0], pk.PHONG_NGUOI.get(p0, ("bs.sa", ""))[0])
                nk.lam(dd1, "P6", "phòng thứ nhất xong → phòng thứ hai bắt đầu được",
                       lambda: b.bat_dau_lam(k.chi_dinh[1], dd1), khach="P6")

    # P7 — mã rác: phải 4xx, không bao giờ 500
    print("\n▶ P7 — mã rác, dữ liệu vô lý", flush=True)
    rac = str(uuid.uuid4())
    for ai, ten, fn in [
        ("bs.a", "bắt đầu phiên khám không tồn tại", lambda: b.ai("bs.a").post(f"/luot-kham/consultations/{rac}/start")),
        ("bs.a", "phiên khám mã không phải uuid", lambda: b.ai("bs.a").post("/luot-kham/consultations/abc/start")),
        ("letan", "thu tiền lượt không tồn tại", lambda: b.ai("letan").post(
            "/payments", {"visit_id": rac, "kind": "dich_vu", "method": "CASH"}, headers=pk.khoa())),
        ("letan", "thu tiền loại lạ", lambda: b.ai("letan").post(
            "/payments", {"visit_id": rac, "kind": "vang_bac", "method": "CASH"}, headers=pk.khoa())),
        ("letan", "check-in lịch không tồn tại", lambda: b.ai("letan").post("/luot-kham/check-in", {"appointment_id": rac})),
        ("bs.sa", "mở phiếu cho chỉ định không tồn tại", lambda: b.ai("bs.sa").post(
            "/phieu/mo", {"service_order_id": rac, "form_id": "KQ_SA_TC_BT"})),
        ("letan", "đo sinh hiệu số vô lý (huyết áp 999)", lambda: b.ai("letan").post(
            f"/luot-kham/visits/{rac}/vitals", {"systolic": 999, "diastolic": -5})),
    ]:
        nk.lam(ai, "P7", ten, fn, mong_loi=(400, 403, 404, 409, 410, 422), khach="P7")
    # Luật CLAUDE.md: hàm nhận ngày/giờ từ người dùng trả RỖNG thay vì ném —
    # nên hai ca này ĐÚNG là 200, miễn không 500 và không trả dữ liệu bừa.
    nk.lam("cskh", "P7", "lịch trong ngày với ngày rác → 200 rỗng (không ném)",
           lambda: b.ai("cskh").get("/appointments/lich-ngay?ngay=2026-13-45"), khach="P7")
    nk.lam("ql", "P7", "báo cáo khách với trang âm / kỳ rác → 200 (kẹp về trang 1)",
           lambda: b.ai("ql").get("/cskh/danh-sach-khach?trang=-9&period=zzz"), khach="P7")

    # P8 — xét nghiệm máu khi bố cục không có phòng lấy mẫu
    print("\n▶ P8 — chỉ định xét nghiệm máu (bố cục 3 tầng không có phòng lấy mẫu)", flush=True)
    k = _khach_moi(nk, "P8", "bs.a", 690)
    if k.vid:
        pk.do_sinh_hieu(nk, k)
        pk.tu_van(nk, k)
        pk.bs_chinh_kham(nk, k, [pk.XN_MAU])
        pk.le_tan_thu(nk, k)
        time.sleep(4)
        if k.chi_dinh:
            cd = b.chi_dinh(k.vid, k.chi_dinh[0])
            ket["P8_chi_dinh"] = {x: cd.get(x) for x in ("trang_thai", "phong_id", "trang_thai_doi_tac")}
            tc = b.ai("ql").get("/luot-kham/chi-dinh-hom-nay")
            dong = next((c for c in tc.get("chi_dinh", []) if c.get("id") == k.chi_dinh[0]), {})
            ket["P8_truong_ca_thay"] = {x: dong.get(x) for x in ("nhom", "khong_co_phong")}
            nk.lam("he-thong", "P8", "trưởng ca/QL được báo 'không có phòng làm được'",
                   lambda: dong.get("khong_co_phong") or (_ for _ in ()).throw(AssertionError(str(dong)[:300])), khach="P8")
    # P11 — thu nhầm → huỷ phiếu → THU LẠI được (Tuyền chốt 24/09/2026)
    print("\n▶ P11 — thu tiền dịch vụ, huỷ phiếu vì thu nhầm, rồi thu lại", flush=True)
    k = _khach_moi(nk, "P11", "bs.a", 710)
    if k.vid:
        pk.do_sinh_hieu(nk, k)
        pk.tu_van(nk, k)
        if pk.bs_chinh_kham(nk, k, [pk.SA]):
            pk.le_tan_thu(nk, k)
            c1 = sql(f"select payment_cycle_id from payment_cycle where visit_id='{k.vid}'"
                     " and kind='dich_vu' and status='PAID' limit 1")
            if c1:
                nk.lam("letan", "P11", "huỷ phiếu vừa thu (thu nhầm)", lambda: b.ai("letan").goi(
                    "DELETE", "/payments", json={"payment_cycle_id": c1[0][0], "visit_id": k.vid,
                                                 "kind": "dich_vu", "reason": "Thu nhầm, thu lại"}), khach="P11")
                nk.lam("letan", "P11", "thu lại sau khi huỷ phiếu", lambda: b.thu(k.vid, "dich_vu", "letan"),
                       khach="P11")
                so = sql(f"select status, count(*) from payment_cycle where visit_id='{k.vid}'"
                         " and kind='dich_vu' group by 1 order by 1")
                ket["P11"] = so
                nk.lam("he-thong", "P11", "sổ còn đủ phiếu huỷ (đối chiếu) + phiếu mới PAID",
                       lambda: dict((a, int(n)) for a, n in so) == {"PAID": 1, "VOIDED": 1}
                       or (_ for _ in ()).throw(AssertionError(str(so))), khach="P11")

    # P12 — THU NGÂN thu thì khách cũng tự được xếp phòng (Tuyền 24/09/2026)
    print("\n▶ P12 — thu ngân (không phải lễ tân) thu tiền → khách tự vào phòng", flush=True)
    k = _khach_moi(nk, "P12", "bs.a", 720)
    if k.vid:
        pk.do_sinh_hieu(nk, k)
        pk.tu_van(nk, k)
        if pk.bs_chinh_kham(nk, k, [pk.SA]) and k.chi_dinh:
            bang = b.ai("thungan").get("/cashier/board?modes=dich_vu")
            dong = next((x for x in bang.get("items", []) if x.get("visit_id") == k.vid), None)
            cd = (dong or {}).get("chon_dich_vu") or {}
            ds = [c["id"] for c in cd.get("chi_dinh", []) if c.get("selection_status") in (None, "PENDING")]
            if ds:
                nk.lam("thungan", "P12", "thu ngân chốt khách chọn dịch vụ", lambda: b.ai("thungan").post(
                    f"/luot-kham/visits/{k.vid}/service-selection/confirm",
                    {"order_ids_seen": ds, "selected_order_ids": ds,
                     "expected_selection_revision": int(cd.get("revision") or 0)},
                    headers=pk.khoa()), khach="P12")
            # Quầy CHỌN PHÒNG trước khi thu (Tuyền 24/09/2026): chọn phòng THỨ HAI
            # trong danh sách (không phải phòng vắng nhất) để chứng minh H4 nghe quầy.
            bang2 = b.ai("thungan").get("/cashier/board?modes=dich_vu")
            dong2 = next((x for x in bang2.get("items", []) if x.get("visit_id") == k.vid), None)
            cd2 = next((c for c in ((dong2 or {}).get("chon_dich_vu") or {}).get("chi_dinh", [])
                        if c["id"] == k.chi_dinh[0]), None)
            phong_ds = (cd2 or {}).get("phong_chon_duoc") or []
            chon_phong = phong_ds[1]["id"] if len(phong_ds) > 1 else (phong_ds[0]["id"] if phong_ds else None)
            ket["P12_phong_chon_duoc"] = [p["ten"] for p in phong_ds]
            if chon_phong:
                nk.lam("thungan", "P12", "quầy chọn phòng khách làm (trước khi thu)", lambda: b.ai("thungan").post(
                    f"/luot-kham/orders/{k.chi_dinh[0]}/routing/phong-du-kien", {"room_id": chon_phong}), khach="P12")
            nk.lam("thungan", "P12", "thu ngân thu tiền dịch vụ", lambda: b.thu(k.vid, "dich_vu", "thungan"),
                   khach="P12")
            xep = nk.lam("he-thong", "P12", "thu ngân thu xong → chỉ định tự được xếp phòng",
                         lambda: b.cho(lambda: b.chi_dinh(k.vid, k.chi_dinh[0])["phong_id"], giay=15,
                                       mo_ta="thu ngân thu → tự xếp"), khach="P12")
            if chon_phong:
                nk.lam("he-thong", "P12", "khách vào ĐÚNG phòng quầy đã chọn",
                       lambda: str(xep) == chon_phong or (_ for _ in ()).throw(
                           AssertionError(f"xếp {xep} ≠ chọn {chon_phong}")), khach="P12")

    return ket


def nhac_check_out(nk: NhatKyThaoTac, khach: pk.Khach) -> None:
    """P9 — nhắc check-out sau 1 phút (Quản lý chỉnh dây H8 = 1 phút ở đầu buổi)."""
    print("\n▶ P9 — trả tiền xong, không check-out → sau 1 phút lễ tân phải được nhắc", flush=True)
    truoc = {t.get("id") for t in (b.ai("letan").get("/thong-bao").get("items") or [])}
    time.sleep(75)
    sau = b.ai("letan").get("/thong-bao").get("items") or []
    moi = [t for t in sau if t.get("id") not in truoc]
    nk.lam("he-thong", "P9", f"lễ tân nhận nhắc check-out cho {khach.ma} (H8 = 1 phút)",
           lambda: any(khach.ten.split()[0] in (t.get("tieu_de") or "") + (t.get("noi_dung") or "") or "check-out" in
                       ((t.get("tieu_de") or "") + (t.get("noi_dung") or "")).lower() for t in moi)
           or (_ for _ in ()).throw(AssertionError(f"không có nhắc; chuông mới: {[t.get('tieu_de') for t in moi][:5]}")),
           khach=khach.ma)
