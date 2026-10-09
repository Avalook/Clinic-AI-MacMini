"""Hành trình khách — giờ vào hàng LẦN ĐẦU + cờ "bấm dồn?" (Tuyền 09/10/2026).

Hàm thuần, không cần DB. Phần trigger giữ `queue_entry.vao_hang_luc` ở
`src/tests/services/test_queue_entry_vao_hang_luc_db.py`.

Kịch bản thật: khách vào hàng khám 18:13, bác sĩ bắt đầu khám 18:37, khách đi
làm dịch vụ rồi QUAY LẠI hàng 18:50 (`eligible_at` bị đặt lại — luật xếp hàng
cố ý). Trước bản sửa bước Khám mất hẳn "vào/chờ".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from clinicai.services.hanh_trinh_khach_service import (
    doan_bam_don,
    dung_hanh_trinh_khach,
    ly_do_bam_don,
    vao_hang_that,
)
from tests.unit.test_hanh_trinh_khach import BS, _cd, _q

# 18:00 giờ VN.
G18 = datetime(2026, 10, 9, 11, 0, tzinfo=timezone.utc)


def g(phut: int, giay: int = 0) -> datetime:
    return G18 + timedelta(minutes=phut, seconds=giay)


def _hanh_trinh(
    *,
    su_kien: list[tuple[str, datetime, dict[str, Any]]] | None = None,
    hang: list[dict[str, Any]] | None = None,
    chi_dinh: list[dict[str, Any]] | None = None,
    phien: list[dict[str, Any]] | None = None,
    lan_lam: dict[str, list[dict[str, Any]]] | None = None,
    ho_so_cu: bool = False,
) -> dict[str, Any]:
    return dung_hanh_trinh_khach(
        luot={
            "visit_id": "v1",
            "status": "IN_PROGRESS",
            "checked_in_at": g(5),
            "closed_at": None,
            "dat_luc": None,
            "ho_so_cu": ho_so_cu,
        },
        su_kien=su_kien or [],
        chi_dinh=chi_dinh or [],
        hang=hang or [],
        phien=phien or [],
        lan_lam=lan_lam,
    )


def _buoc(kq: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {b["ma"]: b for b in kq["buoc"]}


def _q_kham(dau: datetime | None, hien: datetime, status: str = "waiting") -> Any:
    q = _q("q-kham", "PRIMARY", status, vao=hien, bac_si="Linh", bs=BS)
    q["vao_hang_luc"] = dau
    return q


def _phien_kham(bat: datetime, xong: datetime | None = None) -> list[dict[str, Any]]:
    return [
        {
            "kind": "PRIMARY",
            "status": "completed" if xong else "in_progress",
            "started_at": bat,
            "completed_at": xong,
            "bac_si": "Linh",
            "doctor_staff_id": BS,
        }
    ]


# ── 7b: vào hàng lần đầu ────────────────────────────────────────────────────


def test_vao_18_13_kham_18_37_quay_lai_18_50() -> None:
    kq = _hanh_trinh(
        su_kien=[("consultation.started", g(37), {"loai": "PRIMARY"})],
        hang=[_q_kham(g(13), g(50))],
        phien=_phien_kham(g(37)),
    )
    kh = _buoc(kq)["KHAM"]
    assert kh["vao"] == g(13), "giờ vào = lần đầu vào hàng, không bỏ trống"
    assert kh["bat_dau"] == g(37)
    assert kh["bat_dau"] - kh["vao"] == timedelta(minutes=24), "chờ 24′"
    assert kh["quay_lai"] == g(50)


def test_dong_cu_chua_co_vao_hang_luc_khong_in_cho_am() -> None:
    """DB chưa có cột / dòng cũ đã bị ghi đè: rơi về eligible_at — muộn hơn
    giờ bắt đầu thì bỏ trống "vào" (như trước), vẫn nói "quay lại"."""
    kq = _hanh_trinh(
        su_kien=[("consultation.started", g(37), {"loai": "PRIMARY"})],
        hang=[_q_kham(None, g(50))],
        phien=_phien_kham(g(37)),
    )
    kh = _buoc(kq)["KHAM"]
    assert kh["vao"] is None
    assert kh["quay_lai"] == g(50)


def test_chua_kham_khong_quay_lai_thi_nhu_cu() -> None:
    kq = _hanh_trinh(hang=[_q_kham(g(13), g(13))])
    kh = _buoc(kq)["KHAM"]
    assert (kh["vao"], kh["quay_lai"], kh["trang_thai"]) == (g(13), None, "cho")


def test_vao_hang_that_ham_thuan() -> None:
    assert vao_hang_that(None, g(37)) == (None, None)
    assert vao_hang_that({"eligible_at": "rác"}, None) == (None, None)
    q = {"vao_hang_luc": g(13), "eligible_at": g(30)}
    # Bị chặn rồi mở lại TRƯỚC khi bắt đầu: vào 18:13, quay lại 18:30.
    assert vao_hang_that(q, g(37)) == (g(13), g(30))
    assert vao_hang_that(q, None) == (g(13), g(30))


def test_the_dich_vu_vao_lan_dau_va_quay_lai() -> None:
    """Chỗ chờ phòng bị khoá (khách sang phòng khác) rồi mở lại: thẻ hiện giờ vào
    hàng đầu tiên + quay lại, không phải giờ mở lại."""
    q = _q("q-sa", "SERVICE", "done", ref="cd-sa", vao=g(30), phuc_vu=g(32))
    q["vao_hang_luc"] = g(20)
    kq = _hanh_trinh(
        chi_dinh=[
            _cd(
                "cd-sa",
                "Siêu âm",
                "Phòng siêu âm 1",
                xong=True,
                bat_dau=g(32),
                xong_luc=g(40),
                ex="COMPLETED",
            )
        ],
        hang=[q],
    )
    [t] = _buoc(kq)["LAM_DV"]["dich_vu"]
    assert (t["vao"], t["quay_lai"], t["bat_dau"]) == (g(20), g(30), g(32))
    assert t["bam_don"] is False


def test_lam_lai_lan_2_van_tinh_tu_lan_mo_lai() -> None:
    """Làm lại sau Dừng mở lại chỗ 'done' (eligible_at mới) — lần 2 vào hàng
    lúc mở lại, không kéo về lần đầu của lần 1."""
    q = _q("q-sa", "SERVICE", "waiting", ref="cd-sa", vao=g(50))
    q["vao_hang_luc"] = g(20)
    kq = _hanh_trinh(
        chi_dinh=[_cd("cd-sa", "Siêu âm", "Phòng siêu âm 1", ex="PENDING")],
        hang=[q],
        lan_lam={
            "cd-sa": [
                {
                    "attempt_no": 1,
                    "status": "INTERRUPTED",
                    "started_at": g(30),
                    "completed_at": None,
                    "interrupted_at": g(40),
                }
            ]
        },
    )
    [t] = _buoc(kq)["LAM_DV"]["dich_vu"]
    l1, l2 = t["lan"]
    assert (l1["vao"], l1["bat_dau"]) == (g(20), g(30))
    assert (l2["vao"], l2["quay_lai"]) == (g(50), None)


# ── 7c: "bấm dồn?" ──────────────────────────────────────────────────────────


def test_ly_do_bam_don_ham_thuan() -> None:
    assert ly_do_bam_don(g(10), None) is None, "chưa xong thì không gắn"
    assert ly_do_bam_don(g(10), g(15)) is None, "làm 5′ là bình thường"
    assert ly_do_bam_don(g(10), g(10, 40)) == "bắt đầu và xong trong cùng một phút"
    assert ly_do_bam_don(None, g(10)) == "không có giờ bắt đầu"
    assert ly_do_bam_don(g(10), g(15), bat_dau_bu="lúc lưu kết quả") == (
        "không bấm bắt đầu — giờ bắt đầu lấy theo lúc lưu kết quả"
    )
    assert ly_do_bam_don("rác", "rác") is None


def test_sinh_hieu_khong_bam_bat_dau_la_bam_don() -> None:
    kq = _hanh_trinh(su_kien=[("vitals.recorded", g(12), {})])
    sh = _buoc(kq)["SINH_HIEU"]
    assert sh["trang_thai"] == "xong" and sh["bam_don"] is True
    assert "lúc lưu kết quả" in sh["bam_don_ly_do"]


def test_sinh_hieu_bam_dung_luc_khong_gan_co() -> None:
    kq = _hanh_trinh(
        su_kien=[("vitals.started", g(8), {}), ("vitals.recorded", g(12), {})]
    )
    sh = _buoc(kq)["SINH_HIEU"]
    assert (sh["bam_don"], sh["bam_don_ly_do"]) == (False, None)


def test_kham_va_tu_van_bat_dau_xong_cung_phut() -> None:
    kq = _hanh_trinh(
        su_kien=[
            ("consultation.started", g(20), {"loai": "TU_VAN"}),
            ("consultation.handed_over", g(20, 30), {}),
            ("consultation.started", g(37), {"loai": "PRIMARY"}),
            ("consultation.completed", g(37, 50), {"loai": "PRIMARY"}),
        ],
        phien=_phien_kham(g(37), g(37, 50)),
    )
    b = _buoc(kq)
    assert b["TU_VAN"]["bam_don"] and b["KHAM"]["bam_don"]
    assert b["KHAM"]["bam_don_ly_do"] == "bắt đầu và xong trong cùng một phút"


def test_buoc_dang_lam_khong_gan_co() -> None:
    kq = _hanh_trinh(
        su_kien=[("consultation.started", g(37), {"loai": "PRIMARY"})],
        phien=_phien_kham(g(37)),
    )
    assert _buoc(kq)["KHAM"]["bam_don"] is False


def test_the_khong_co_gio_bat_dau_lay_gio_vao_phong_bu() -> None:
    q = _q("q-mau", "SERVICE", "done", ref="cd-mau", vao=g(30), phuc_vu=g(33))
    kq = _hanh_trinh(
        chi_dinh=[
            _cd(
                "cd-mau",
                "Lấy mẫu",
                "Lấy mẫu",
                xong=True,
                xong_luc=g(40),
                ex="COMPLETED",
            )
        ],
        hang=[q],
    )
    [t] = _buoc(kq)["LAM_DV"]["dich_vu"]
    assert t["bat_dau"] == g(33)
    assert t["bam_don"] is True and "giờ vào phòng" in t["bam_don_ly_do"]
    # Thanh đoạn dòng gọn: cùng độ dài, đoạn của thẻ này mang cờ.
    gon = kq["gon"]
    assert gon["doan_bam_don"] == doan_bam_don(kq["buoc"])
    assert len(gon["doan_bam_don"]) == len(gon["doan"])
    assert [d for d, c in zip(gon["doan"], gon["doan_bam_don"], strict=True) if c] == [
        "xong"
    ]


def test_the_xong_tai_quay_khong_phai_bam_don() -> None:
    cd = _cd("cd-q", "Test nhanh", None, xong=True, xong_luc=g(40), ex="COMPLETED")
    cd.update(lam_them="Làm thêm tại quầy tiếp đón", xong_boi="Lễ tân A")
    kq = _hanh_trinh(chi_dinh=[cd])
    [t] = _buoc(kq)["LAM_DV"]["dich_vu"]
    assert t["bam_don"] is False


def test_doi_tac_lam_tron_khong_phai_bam_don() -> None:
    """Chụp phim ngoài — đối tác làm trọn, không phòng nội bộ, không bước bắt đầu."""
    cd = _cd(
        "cd-phim",
        "Chụp X-quang",
        None,
        ngoai=True,
        xong=True,
        xong_luc=g(40),
        ex="COMPLETED",
    )
    kq = _hanh_trinh(chi_dinh=[cd])
    [t] = _buoc(kq)["LAM_DV"]["dich_vu"]
    assert t["trang_thai"] == "XONG" and t["bam_don"] is False


def test_ho_so_cu_khong_gan_bam_don() -> None:
    """Hồ sơ Notion: mọi giờ 00:00 giả — không phải bấm dồn."""
    kq = _hanh_trinh(
        su_kien=[("vitals.recorded", g(12), {})],
        ho_so_cu=True,
    )
    assert not any(b["bam_don"] for b in kq["buoc"])
    assert not any(kq["gon"]["doan_bam_don"])
