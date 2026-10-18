"""Tầng model của agent soát — hàng rào chi tiêu, lọc dữ liệu, cổng mạng, thước đo.

Không bài nào gọi mạng. Chúng chứng minh các cửa chặn ĐÚNG TRƯỚC khi có byte nào rời
máy: sai host, hết trần, có tệp DUNG, đường dẫn cấm, bí mật lọt trong mã.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from soat_he_thong.tang_model import (  # noqa: E402
    che_du_lieu,
    chi_phi,
    khach,
    soat_model,
    thuoc_do,
)


def test_duong_dan_cam_khong_bao_gio_gui() -> None:
    for d in (
        ".env.prod",
        "src/clinicai/.env",
        "supabase/fixtures/tai_khoan.sql",
        "scripts/staff-emails.csv",
        "x/id_rsa",
        "ket-qua/phat-hien.jsonl",
        "ClinicAI-Backups/dump.sql",
    ):
        assert not che_du_lieu.duoc_gui(d), d
    assert che_du_lieu.duoc_gui("src/clinicai/services/pharmacy_service.py")
    assert che_du_lieu.duoc_gui("src/dashboard/lib/phieu-kham.ts")


def test_sach_che_bi_mat_sdt_email_nhung_giu_ma_binh_thuong() -> None:
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJzdXBhYmFzZSJ9.abcdefghijklmnop"
    mau = (
        f'KEY = "{jwt}"\n'
        'token = "hf_abcdefghijklmnopqrstuvwxyz0123"\n'
        'password = "mat-khau-that-12345"\n'
        "sdt = '0912345678' ; mail = 'khach.that@gmail.com'\n"
        "tk = 'ql@dr4women.local'\n"
        "x = quantity_on_hand - 5\n"
    )
    ra, n = che_du_lieu.sach(mau)
    for lo in (jwt, "hf_abcdefghij", "mat-khau-that", "0912345678", "khach.that@"):
        assert lo not in ra, lo
    assert "ql@dr4women.local" in ra  # tài khoản thử, không phải người thật
    assert "quantity_on_hand - 5" in ra
    assert n >= 5


def test_tran_chi_tieu_va_cong_tac_dung(tmp_path: Path) -> None:
    so = chi_phi.SoChiPhi(tmp_path / "cp.jsonl", 0.01, tmp_path)
    so.truoc_khi_goi()  # còn trần
    usd = so.ghi("openai/gpt-oss-120b:novita", 1_000_000, 1_000_000, "t", 1.0)
    assert usd == pytest.approx(0.05 + 0.25)
    with pytest.raises(chi_phi.TuChoiError, match="trần"):
        so.truoc_khi_goi()
    so2 = chi_phi.SoChiPhi(tmp_path / "cp2.jsonl", 100.0, tmp_path)
    (tmp_path / "DUNG").write_text("", encoding="utf8")
    with pytest.raises(chi_phi.TuChoiError, match="DUNG"):
        so2.truoc_khi_goi()


def test_so_chi_phi_khong_chua_noi_dung(tmp_path: Path) -> None:
    so = chi_phi.SoChiPhi(tmp_path / "cp.jsonl", 5.0, tmp_path)
    so.ghi("zai-org/GLM-5.3-Flash:novita", 10, 20, "nhan-viec", 0.5)
    dong = (tmp_path / "cp.jsonl").read_text(encoding="utf8")
    assert set(__import__("json").loads(dong)) == {
        "luc",
        "mo_hinh",
        "nhan",
        "vao",
        "ra",
        "usd",
        "giay",
    }


def test_mo_hinh_la_tinh_gia_cao_de_tran_van_bao_ve() -> None:
    assert chi_phi.gia("hang/khong-co-trong-bang:x") == chi_phi.GIA_MAC_DINH
    assert chi_phi.gia("openai/gpt-oss-120b:novita") == (0.05, 0.25)  # bỏ hậu tố :nhà


def test_cong_mang_chi_https_toi_host_cho_phep() -> None:
    khach._kiem_url(khach.HF_URL)
    for url in (
        "http://router.huggingface.co/v1/chat/completions",  # không TLS
        "https://evil.example/v1/chat/completions",
        "https://router.huggingface.co.evil.example/x",
        "ftp://router.huggingface.co/x",
    ):
        with pytest.raises(chi_phi.TuChoiError):
            khach._kiem_url(url)


def test_goi_bi_chan_truoc_khi_co_byte_nao_ra_may(tmp_path: Path) -> None:
    so = chi_phi.SoChiPhi(tmp_path / "cp.jsonl", 0.0, tmp_path)  # trần 0
    with pytest.raises(chi_phi.TuChoiError):
        khach.goi(
            "openai/gpt-oss-120b:novita", [{"role": "user", "content": "x"}], so=so
        )
    assert not (tmp_path / "cp.jsonl").exists()  # không gọi → không có dòng sổ


def test_cat_khuc_phu_het_dong_co_chong_nhau_va_danh_so() -> None:
    nd = "\n".join(f"dong {i}" for i in range(1, 1001))
    khuc = soat_model.cat_khuc(nd)
    assert khuc[0][0] == 1
    assert len(khuc) >= 3
    thay: set[int] = set()
    for dau, van_ban in khuc:
        so_dong = [int(x.split("|")[0]) for x in van_ban.splitlines()]
        assert so_dong[0] == dau
        thay.update(so_dong)
    assert thay == set(range(1, 1001)), "mọi dòng phải nằm trong ít nhất một khúc"
    # chồng nhau: dòng cuối khúc 1 phải còn nằm ở khúc 2
    cuoi1 = int(khuc[0][1].splitlines()[-1].split("|")[0])
    assert khuc[1][0] < cuoi1
    assert len(soat_model.cat_khuc("a\nb\nc")) == 1
    assert soat_model.cat_khuc("") == [(1, "")]


@pytest.mark.parametrize(
    ("van_ban", "so_phan_tu"),
    [
        ('[{"dong_tu": 1}]', 1),
        ('```json\n[{"dong_tu": 1}, {"dong_tu": 2}]\n```', 2),
        ('<think>nghĩ [1,2]</think>\n[{"a": 1}]', 1),
        ("Không có lỗi.", 0),
        ("[]", 0),
        ("[{hỏng", 0),
        ('{"dong_tu": 1}', 0),  # đối tượng đơn, không phải mảng
    ],
)
def test_doc_json_chiu_duoc_dau_ra_xau(van_ban: str, so_phan_tu: int) -> None:
    assert len(soat_model.doc_json(van_ban)) == so_phan_tu


def test_thuoc_do_chi_goi_lenh_doc_cua_kho_ma(tmp_path: Path) -> None:
    for lenh in ("push", "reset", "checkout", "commit", "fetch", "clean", "rm"):
        with pytest.raises(ValueError):
            thuoc_do._git(tmp_path, lenh)


def test_thuoc_do_dap_an_day_du_va_moi_loi_co_ca_do() -> None:
    assert len(thuoc_do.CO_CHE) == 20
    assert {ma[0] for ma in thuoc_do.CO_CHE} == {"P", "H", "N", "T"}
    phu = {m for ca in thuoc_do.CAC_CA for m in ca.loi}
    assert phu == set(thuoc_do.CO_CHE), set(thuoc_do.CO_CHE) ^ phu


def test_trung_vi_tri_co_dung_sai() -> None:
    def u(a: int, b: int) -> soat_model.UngVien:
        return soat_model.UngVien("t", a, b, "logic_sai", "", "", "", 0.5, "m")

    vung = [(500, 505)]
    assert thuoc_do.trung_vi_tri(u(490, 495), vung)  # nằm trong vùng ±40
    assert thuoc_do.trung_vi_tri(u(540, 541), vung)
    assert not thuoc_do.trung_vi_tri(u(100, 110), vung)
    assert not thuoc_do.trung_vi_tri(u(546, 600), vung)
    assert thuoc_do.trung_vi_tri(u(1, 1), None)  # cả tệp (migration mới)
