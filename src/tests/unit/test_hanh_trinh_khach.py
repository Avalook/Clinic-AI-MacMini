"""Hành trình khách (Tuyền chốt 29/09/2026) — hàm thuần, không cần DB.

Một buổi đủ: check-in 10:27 → sinh hiệu 10:48–10:52 → khám BS Linh 10:53–10:55
(chỉ định 3 dịch vụ, thu tiền 10:56) → làm song song: lấy mẫu XONG 11:05, siêu
âm ĐANG làm từ 10:58, HPV đối tác đã lấy mẫu CHỜ KẾT QUẢ → còn chỗ quay lại bác
sĩ đọc kết quả → check-out.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from clinicai.services.hanh_trinh_khach_service import (
    doc_ma_luot,
    dung_hanh_trinh_khach,
    noi_cua_hang,
)

T0 = datetime(2026, 9, 29, 3, 0, tzinfo=timezone.utc)  # 10:00 giờ VN
BS = "11111111-1111-4111-8111-111111111111"


def p(phut: int) -> datetime:
    return T0 + timedelta(minutes=phut)


def _cd(ma: str, ten: str, phong: str | None, **k: Any) -> dict[str, Any]:
    return {
        "id": ma,
        "ten": ten,
        "lan": 1,
        "tao_luc": p(55),
        "chon": True,
        "da_tra": True,
        "xong": k.get("xong", False),
        "phong": phong,
        "ngoai": k.get("ngoai", False),
        "tra_luc": p(56),
        "bat_dau_luc": k.get("bat_dau"),
        "dang_lam": k.get("dang_lam", False),
        "xong_luc": k.get("xong_luc"),
        "doi_tac_thu": False,
        "doi_tac_da_thu": False,
        "execution_status": k.get("ex", "PENDING"),
        "lam_xong_luc": k.get("lam_xong"),
    }


def _q(ma: str, reason: str, status: str, **k: Any) -> dict[str, Any]:
    return {
        "id": ma,
        "lane": "ROOM" if reason == "SERVICE" else "DOCTOR",
        "reason": reason,
        "ref_id": k.get("ref"),
        "status": status,
        "eligible_at": k.get("vao"),
        "serving_at": k.get("phuc_vu"),
        "created_at": k.get("vao"),
        "phong": k.get("phong"),
        "bac_si": k.get("bac_si"),
        "doctor_staff_id": k.get("bs"),
        "stt": k.get("stt"),
        "so_truoc": k.get("so_truoc"),
        "so_cho": k.get("so_cho"),
    }


def _buoi(dong_luc: datetime | None = None) -> dict[str, Any]:
    su_kien = [
        ("vitals.started", p(48), {}),
        ("vitals.recorded", p(52), {}),
        ("consultation.started", p(53), {"loai": "PRIMARY"}),
        ("consultation.completed", p(55), {"loai": "PRIMARY"}),
        ("payment.service_collected", p(56), {}),
        ("service.started", p(58), {}),
        ("service.started", p(62), {}),
        ("service.completed", p(65), {}),
    ]
    chi_dinh = [
        _cd(
            "cd-mau",
            "Tổng phân tích nước tiểu",
            "Lấy mẫu",
            xong=True,
            bat_dau=p(62),
            xong_luc=p(65),
            ex="COMPLETED",
        ),
        _cd(
            "cd-sa",
            "Siêu âm phụ khoa",
            "Phòng siêu âm 1",
            bat_dau=p(58),
            dang_lam=True,
            ex="IN_PROGRESS",
        ),
        _cd(
            "cd-hpv",
            "HPV PCR (40 type)",
            "Lấy mẫu",
            ngoai=True,
            dang_lam=True,
            xong_luc=p(65),
            lam_xong=p(65),
            ex="COMPLETED",
        ),
    ]
    hang = [
        _q("q-kham", "PRIMARY", "done", vao=p(27), phuc_vu=p(53), bac_si="Linh", bs=BS),
        _q("q-mau", "SERVICE", "done", ref="cd-mau", vao=p(57), phuc_vu=p(62)),
        _q(
            "q-sa",
            "SERVICE",
            "serving",
            ref="cd-sa",
            vao=p(57),
            phuc_vu=p(58),
            phong="Phòng siêu âm 1",
        ),
        _q(
            "q-doc",
            "REVIEW",
            "blocked",
            vao=p(57),
            bac_si="Linh",
            bs=BS,
            so_truoc=2,
            so_cho=2,
        ),
    ]
    if dong_luc is not None:
        for q in hang:
            if q["status"] != "done":
                q["status"] = "done"
    return dung_hanh_trinh_khach(
        luot={
            "visit_id": "v1",
            "status": "IN_PROGRESS",
            "checked_in_at": p(27),
            "closed_at": dong_luc,
            "dat_luc": None,
        },
        su_kien=su_kien,
        chi_dinh=chi_dinh,
        hang=hang,
        phien=[
            {
                "kind": "PRIMARY",
                "status": "completed",
                "started_at": p(53),
                "completed_at": p(55),
                "bac_si": "Linh",
                "doctor_staff_id": BS,
            }
        ],
        phong_bac_si={BS: "Phòng khám Phụ khoa"},
        ai={"payment.service_collected": "Vũ Thu Hà"},
    )


def _buoc(kq: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {b["ma"]: b for b in kq["buoc"]}


def test_dang_o_phong_that_dang_lam_tu_luc() -> None:
    kq = _buoi()
    o = kq["dang_o"]
    assert o["trang_thai"] == "DANG_O"
    assert o["noi"] == "Phòng siêu âm 1"
    assert o["tu_luc"] == p(58)
    assert kq["gon"]["nhan"] == "Đang ở" and not kq["gon"]["xong_buoi"]


def test_tiep_theo_la_ban_kham_doc_ket_qua() -> None:
    tiep = _buoi()["tiep_theo"]
    assert tiep == [
        {
            "noi": "Phòng khám Phụ khoa",
            "stt": None,
            "so_nguoi_cho": 2,
            "ghi_chu": "đọc kết quả",
            "du_kien": False,
        }
    ]


def test_gio_tung_buoc() -> None:
    b = _buoc(_buoi())
    assert [x["ma"] for x in _buoi()["buoc"]] == [
        "CHECK_IN",
        "SINH_HIEU",
        "KHAM",
        "LAM_DV",
        "DOC_KQ",
        "THUOC",
        "CHECK_OUT",
    ]
    assert b["CHECK_IN"]["trang_thai"] == "xong" and b["CHECK_IN"]["xong"] == p(27)
    sh = b["SINH_HIEU"]
    assert (sh["vao"], sh["bat_dau"], sh["xong"]) == (p(27), p(48), p(52))
    kh = b["KHAM"]
    assert (kh["vao"], kh["bat_dau"], kh["xong"]) == (p(27), p(53), p(55))
    assert kh["noi"] == "Phòng khám Phụ khoa" and kh["ai"] == "Linh"
    assert (kh["so_chi_dinh"], kh["thu_luc"], kh["nguoi_thu"]) == (
        3,
        p(56),
        "Vũ Thu Hà",
    )

    dv = {t["id"]: t for t in b["LAM_DV"]["dich_vu"]}
    assert b["LAM_DV"]["trang_thai"] == "dang"
    mau = dv["cd-mau"]
    assert (mau["trang_thai"], mau["vao"], mau["bat_dau"], mau["xong"]) == (
        "XONG",
        p(57),
        p(62),
        p(65),
    )
    sa = dv["cd-sa"]
    assert (sa["trang_thai"], sa["noi"], sa["vao"], sa["bat_dau"], sa["xong"]) == (
        "DANG_LAM",
        "Phòng siêu âm 1",
        p(57),
        p(58),
        None,
    )
    hpv = dv["cd-hpv"]
    assert hpv["trang_thai"] == "DOI_TAC" and hpv["doi_tac"]
    assert hpv["noi"] == "Lấy mẫu → Đối tác" and hpv["lay_mau"] == p(65)
    assert hpv["xong"] is None, "chưa có kết quả thì chưa xong"

    assert b["DOC_KQ"]["trang_thai"] == "chua"
    assert b["DOC_KQ"]["ghi_chu"] == "đọc kết quả, khi dịch vụ xong"
    assert b["CHECK_OUT"]["trang_thai"] == "chua"


def test_dong_gon_doan_va_dem() -> None:
    g = _buoi()["gon"]
    # check-in, sinh hiệu, khám, 3 dịch vụ, quay lại BS, check-out (thuốc chưa
    # biết có đơn — không chiếm đoạn).
    assert g["doan"] == [
        "xong",
        "xong",
        "xong",
        "xong",
        "dang",
        "doi_tac",
        "chua",
        "chua",
    ]
    assert (g["dv_xong"], g["dv_tong"]) == (1, 3)
    assert g["con_cho"] == ["KQ đối tác"]


def test_check_out_la_xong_buoi_tick_het() -> None:
    kq = _buoi(dong_luc=p(80))
    g = kq["gon"]
    assert g["trang_thai"] == "DA_VE" and g["xong_buoi"] and g["tu_luc"] == p(80)
    assert set(g["doan"]) == {"xong"}
    assert kq["tiep_theo"] == []
    b = _buoc(kq)
    assert b["CHECK_OUT"]["trang_thai"] == "xong" and b["CHECK_OUT"]["xong"] == p(80)
    # Bước chưa tới lúc về = không làm (không treo "chờ"); việc đối tác vẫn
    # ghi đúng là chờ kết quả.
    assert b["DOC_KQ"]["trang_thai"] == "khong"
    assert "THUOC" not in b
    dv = {t["id"]: t for t in b["LAM_DV"]["dich_vu"]}
    assert dv["cd-hpv"]["trang_thai"] == "DOI_TAC"


def test_dang_cho_co_stt() -> None:
    kq = dung_hanh_trinh_khach(
        luot={"visit_id": "v2", "status": "IN_PROGRESS", "checked_in_at": p(0)},
        su_kien=[("vitals.recorded", p(5), {})],
        chi_dinh=[],
        hang=[
            _q("q", "PRIMARY", "waiting", vao=p(6), bac_si="Nam", stt=2, so_truoc=1),
        ],
        phien=[],
    )
    g = kq["gon"]
    assert (g["trang_thai"], g["noi"], g["tu_luc"], g["stt"]) == (
        "DANG_CHO",
        "Bàn khám BS Nam",
        p(6),
        2,
    )


def test_dau_vao_rac_khong_nem() -> None:
    kq = dung_hanh_trinh_khach(
        luot={"visit_id": None, "status": None, "checked_in_at": "rác", "closed_at": 7},
        su_kien=[],
        chi_dinh=[],
        hang=[{"status": "waiting", "eligible_at": "không phải giờ"}],
        phien=[{"kind": "PRIMARY", "started_at": "x"}],
    )
    assert kq["gon"]["trang_thai"] == "DANG_CHO"
    assert kq["gon"]["tu_luc"] is None
    assert all(
        b["bat_dau"] is None or isinstance(b["bat_dau"], datetime) for b in kq["buoc"]
    )


def test_doc_ma_luot_bo_ma_rac() -> None:
    a = "8f2c1e2a-1b3c-4d5e-8f60-123456789abc"
    assert doc_ma_luot(f"{a.upper()}, rác,,{a};DROP") == [a]
    assert doc_ma_luot(None) == []
    assert doc_ma_luot(12) == []
    assert doc_ma_luot("") == []


def test_noi_cua_hang_ten_phong_that() -> None:
    assert (
        noi_cua_hang({"lane": "ROOM", "phong": "Phòng siêu âm 1"}) == "Phòng siêu âm 1"
    )
    assert (
        noi_cua_hang({"lane": "DOCTOR", "bac_si": "Linh"}, "Phòng khám 3")
        == "Phòng khám 3"
    )
    assert noi_cua_hang({"lane": "DOCTOR"}) == "Bàn khám (BS chính)"


# ── GIỜ THẬT, KHÔNG LÀM MÉO (Tuyền duyệt 29/09/2026) ─────────────────────────


def _mot_dich_vu(
    hang_dv: list[dict[str, Any]],
    lan_lam: list[dict[str, Any]] | None = None,
    **k: Any,
) -> dict[str, Any]:
    return dung_hanh_trinh_khach(
        luot={
            "visit_id": "v2",
            "status": "IN_PROGRESS",
            "checked_in_at": p(0),
            "closed_at": None,
            "dat_luc": None,
        },
        su_kien=[
            ("vitals.started", p(30), {}),
            ("vitals.recorded", p(33), {"_ai": "ĐD Lan"}),
            ("vitals.recorded", p(45), {"_ai": "ĐD Mai"}),
        ],
        chi_dinh=[
            _cd(
                "cd-sa",
                "Siêu âm phụ khoa",
                "Phòng siêu âm 1",
                bat_dau=k.get("bat_dau"),
                dang_lam=k.get("dang_lam", False),
                ex=k.get("ex", "PENDING"),
            )
        ],
        hang=hang_dv,
        phien=[],
        lan_lam={"cd-sa": lan_lam} if lan_lam else None,
    )


def test_the_dich_vu_vao_khong_muon_hon_bat_dau() -> None:
    """Chỗ chờ được mở lại (vào 11:10) sau lúc bắt đầu 11:00 → không in "vào
    11:10" (chờ âm); không có giờ vào nào ≤ bắt đầu thì bỏ trống."""
    kq = _mot_dich_vu(
        [_q("q-sa", "SERVICE", "serving", ref="cd-sa", vao=p(70), phuc_vu=p(70))],
        bat_dau=p(60),
        dang_lam=True,
        ex="IN_PROGRESS",
    )
    t = _buoc(kq)["LAM_DV"]["dich_vu"][0]
    assert t["bat_dau"] == p(60)
    assert t["vao"] is None, "vào hàng muộn hơn bắt đầu thì bỏ trống"

    kq = _mot_dich_vu(
        [
            _q("q-sa1", "SERVICE", "done", ref="cd-sa", vao=p(50), phuc_vu=p(60)),
            _q("q-sa2", "SERVICE", "serving", ref="cd-sa", vao=p(70)),
        ],
        bat_dau=p(60),
        dang_lam=True,
        ex="IN_PROGRESS",
    )
    t = _buoc(kq)["LAM_DV"]["dich_vu"][0]
    assert t["vao"] == p(50) and t["vao"] <= t["bat_dau"]
    assert t["so_lan"] == 1 and t["lan"] == []


def test_the_dich_vu_lam_lai_giu_lan_1_va_dem_lan() -> None:
    """Lần 1 bắt đầu 11:00, dừng 11:05; khách chờ lại từ 11:06, lần 2 bắt đầu
    11:12 → thẻ ghi 2 lần, mỗi lần đủ vào / bắt đầu / xong-dừng; chờ không âm."""
    lan_lam = [
        {
            "attempt_no": 1,
            "status": "INTERRUPTED",
            "started_at": p(60),
            "completed_at": None,
            "interrupted_at": p(65),
        },
        {
            "attempt_no": 2,
            "status": "IN_PROGRESS",
            "started_at": p(72),
            "completed_at": None,
            "interrupted_at": None,
        },
    ]
    kq = _mot_dich_vu(
        [
            _q("q-1", "SERVICE", "done", ref="cd-sa", vao=p(55)),
            _q("q-2", "SERVICE", "serving", ref="cd-sa", vao=p(66), phuc_vu=p(72)),
        ],
        lan_lam,
        bat_dau=p(60),
        dang_lam=True,
        ex="IN_PROGRESS",
    )
    t = _buoc(kq)["LAM_DV"]["dich_vu"][0]
    assert t["so_lan"] == 2
    assert [(x["so"], x["vao"], x["bat_dau"], x["dung"]) for x in t["lan"]] == [
        (1, p(55), p(60), p(65)),
        (2, p(66), p(72), None),
    ]
    assert all(x["vao"] is None or x["vao"] <= x["bat_dau"] for x in t["lan"])
    # Giờ chính của thẻ = lần mới nhất.
    assert (t["vao"], t["bat_dau"]) == (p(66), p(72))
    assert kq["gon"]["lam_lai"] == [{"ten": "Siêu âm phụ khoa", "lan": 2}]


def test_the_dich_vu_cho_lam_lai_them_dong_lan_moi() -> None:
    lan_lam = [
        {
            "attempt_no": 1,
            "status": "INTERRUPTED",
            "started_at": p(60),
            "completed_at": None,
            "interrupted_at": p(65),
        }
    ]
    kq = _mot_dich_vu(
        [_q("q-1", "SERVICE", "waiting", ref="cd-sa", vao=p(66))],
        lan_lam,
        ex="PENDING",
    )
    t = _buoc(kq)["LAM_DV"]["dich_vu"][0]
    assert [(x["so"], x["trang_thai"], x["vao"], x["bat_dau"]) for x in t["lan"]] == [
        (1, "INTERRUPTED", None, p(60)),
        (2, "PENDING", p(66), None),
    ]


def test_sinh_hieu_do_lai_dong_rieng_va_dong_gon() -> None:
    kq = _mot_dich_vu([])
    sh = _buoc(kq)["SINH_HIEU"]
    assert (sh["bat_dau"], sh["xong"]) == (p(30), p(33))
    assert sh["ai"] == "ĐD Lan", "người đo lần 1"
    assert sh["do_lai"] == [p(45)]
    assert [x["ai"] for x in sh["lan_do"]] == ["ĐD Lan", "ĐD Mai"]
    assert kq["gon"]["do_lai"] == [p(45)]


def test_buoc_chua_xay_ra_la_du_kien_khong_gio() -> None:
    b = _buoc(_buoi())
    assert b["THUOC"]["du_kien"] and b["THUOC"]["ghi_chu"] == "nếu có đơn"
    assert b["DOC_KQ"]["du_kien"]
    assert b["CHECK_OUT"]["du_kien"]
    for ma in ("THUOC", "DOC_KQ", "CHECK_OUT"):
        assert (b[ma]["vao"], b[ma]["bat_dau"], b[ma]["xong"]) == (None, None, None)
    # Bước đã xảy ra / đang chạy thật không phải dự kiến.
    assert not b["KHAM"]["du_kien"] and not b["SINH_HIEU"]["du_kien"]
    assert not b["LAM_DV"]["du_kien"]


def test_noi_giu_cho_la_du_kien() -> None:
    from clinicai.services.hanh_trinh_khach_service import noi_la_du_kien

    assert noi_la_du_kien("Bàn khám")
    assert noi_la_du_kien("Bàn khám (BS chính)")
    assert noi_la_du_kien("Bàn khám BS Linh")
    assert noi_la_du_kien("Phòng dịch vụ")
    assert not noi_la_du_kien("Phòng khám Phụ khoa")
    assert not noi_la_du_kien("")
    assert not noi_la_du_kien(None)


def test_doc_ket_qua_ngay_trong_phien_kham_chinh() -> None:
    """Tuyền 29/09: bác sĩ chỉ định, khách đi làm dịch vụ rồi QUAY LẠI, bác sĩ
    bấm Khám xong sau đó (không mở phiên đọc riêng) → "Quay lại bác sĩ chính"
    là XONG, giờ quay lại không bị tính là chờ khám."""
    kq = dung_hanh_trinh_khach(
        luot={
            "visit_id": "v2",
            "status": "IN_PROGRESS",
            "checked_in_at": p(27),
            "closed_at": None,
            "dat_luc": None,
        },
        su_kien=[
            ("consultation.started", p(53), {"loai": "PRIMARY"}),
            ("service.started", p(58), {}),
            ("service.completed", p(62), {}),
            ("consultation.completed", p(70), {"loai": "PRIMARY"}),
        ],
        chi_dinh=[
            _cd(
                "cd-dxa",
                "Đo mật độ xương",
                "Đo sinh hiệu",
                xong=True,
                bat_dau=p(58),
                xong_luc=p(62),
                ex="COMPLETED",
            ),
        ],
        hang=[
            _q(
                "q-kham",
                "PRIMARY",
                "done",
                vao=p(66),
                phuc_vu=p(53),
                bac_si="BS Nam",
                bs=BS,
            ),
            _q("q-dxa", "SERVICE", "done", ref="cd-dxa", vao=p(57), phuc_vu=p(58)),
        ],
        phien=[
            {
                "kind": "PRIMARY",
                "status": "completed",
                "started_at": p(53),
                "completed_at": p(70),
                "bac_si": "BS Nam",
                "doctor_staff_id": BS,
            }
        ],
        phong_bac_si={BS: "Phòng Sản"},
        ai={},
    )
    b = _buoc(kq)
    assert b["KHAM"]["vao"] is None
    assert b["DOC_KQ"]["trang_thai"] == "xong"
    assert b["DOC_KQ"]["bat_dau"] == p(66) and b["DOC_KQ"]["xong"] == p(70)
    assert "BS BS" not in (b["DOC_KQ"]["noi"] or "")
