"""Thước đo chất lượng dạng RATCHET — "chỉ được giảm" (Tuyền chốt 24/11/2026).

Năm chỉ số (kích thước tệp, McCabe, `if` theo vai trong TSX, tên hàm trùng, cửa API
thiếu `response_model`). Cách đếm ghi ở đầu `scripts/thuoc-do.py`; mốc nằm ở
`scripts/*.json` (mỗi chỉ số một tệp). Test đỏ khi số đo VƯỢT mốc và nói đúng tệp/hàm.

Bớt được thì hạ mốc:   python3 scripts/thuoc-do.py --ha-moc
KHÔNG nâng mốc để test xanh (thiet-ke-code.md, "Khi một luật ở đây cản việc").

Nhóm 2 (`test_do_*`) thử ngược: dựng một dự án giả có đúng một vi phạm rồi xem bộ đo
có thấy không — nếu bộ đo hỏng (đo ra rỗng) thì nhóm 1 sẽ xanh giả.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

_REPO = Path(__file__).resolve().parents[3]


def _nap() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "thuoc_do_scripts", _REPO / "scripts" / "thuoc-do.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


thuoc_do = _nap()


# ── Nhóm 1: số đo THẬT của repo so với mốc ──────────────────────────────────


@pytest.mark.parametrize("chi_so", thuoc_do.CHI_SO)
def test_khong_vuot_moc(chi_so: str) -> None:
    do_duoc = thuoc_do.DO[chi_so]()
    moc = thuoc_do.doc_moc(chi_so)
    loi = thuoc_do.so_voi_moc(chi_so, do_duoc, moc)
    assert not loi, (
        f"\nChỉ số `{chi_so}` VƯỢT MỐC ({len(loi)} chỗ):\n  - "
        + "\n  - ".join(loi)
        + f"\nCách sửa: {thuoc_do.CACH_SUA[chi_so]}\n"
        "Bớt được thì hạ mốc: python3 scripts/thuoc-do.py --ha-moc. "
        "KHÔNG nâng mốc để test xanh."
    )


@pytest.mark.parametrize("chi_so", thuoc_do.CHI_SO)
def test_moc_hop_le(chi_so: str) -> None:
    """Mốc đọc được, giá trị dương; tệp > 400 dòng mới được vào mốc kích thước."""
    tho = json.loads(thuoc_do.TEN_MOC[chi_so].read_text(encoding="utf-8"))
    chi_tiet = {k: int(v) for k, v in tho["chi_tiet"].items()}
    # Rỗng là HỢP LỆ: sửa hết vi phạm một chỉ số là tin tốt (chống đo rỗng: test sàn).
    assert all(v > 0 for v in chi_tiet.values()), chi_so
    if chi_so == "tran-kich-thuoc":
        thua = [k for k, v in chi_tiet.items() if v <= thuoc_do.TRAN_FILE_MOI]
        assert not thua, f"mốc có tệp ≤ {thuoc_do.TRAN_FILE_MOI} dòng: {thua}"
    if chi_so == "moc-phuc-tap":
        thap = [k for k, v in chi_tiet.items() if v <= thuoc_do.NGUONG_PHUC_TAP]
        assert not thap, f"mốc có hàm không vượt trần phức tạp: {thap}"


def test_bo_do_khong_do_ra_rong_tren_cay_that() -> None:
    """Sàn: dời/đổi tên thư mục làm bộ đo đo rỗng thì test xanh GIẢ — chặn ở đây."""
    # Sàn đếm thứ KHÔNG giảm khi sửa tốt (số tệp nguồn), không đếm số vi phạm — nếu
    # không, sửa hết một chỉ số về 0 sẽ làm test đỏ oan.
    assert len(thuoc_do._tep_nguon(thuoc_do.BACKEND, {".py"})) > 300
    assert len(thuoc_do._tep_nguon(thuoc_do.BACKEND / "api", {".py"})) > 20
    assert len(thuoc_do._tep_nguon(thuoc_do.DASHBOARD / "app", {".tsx"})) > 100
    assert len(thuoc_do._tep_nguon(thuoc_do.SRC, thuoc_do._DUOI_CODE)) > 500


def test_moc_khong_co_tep_ma() -> None:
    """Tệp trong mốc kích thước/vai/cửa đã bị xoá thì mốc phải được dọn (--ha-moc)."""
    ma = [
        k
        for c in ("tran-kich-thuoc", "moc-if-theo-vai", "moc-cua-thieu-response-model")
        for k in thuoc_do.doc_moc(c)
        if not (_REPO / k).exists()
    ]
    assert not ma, (
        f"mốc còn ghi tệp không tồn tại: {ma}. "
        "Chạy python3 scripts/thuoc-do.py --ha-moc "
        "(tệp bị xoá/đổi tên là tin tốt, mốc phải hạ theo)."
    )


# ── Nhóm 2: logic so sánh (ca biên) ─────────────────────────────────────────


def test_so_sanh_kich_thuoc_ca_bien() -> None:
    so = thuoc_do.so_voi_moc
    moc = {"a.py": 1000}
    assert so("tran-kich-thuoc", {"a.py": 1000}, moc) == []  # bằng mốc: được
    assert so("tran-kich-thuoc", {"a.py": 999}, moc) == []  # ngắn đi: được
    assert len(so("tran-kich-thuoc", {"a.py": 1001}, moc)) == 1  # dài thêm 1 dòng
    moi = so("tran-kich-thuoc", {"b.py": 401}, moc)  # tệp mới quá trần 400
    assert len(moi) == 1 and "b.py" in moi[0] and "MỚI" in moi[0]


def test_so_sanh_phuc_tap_ca_bien() -> None:
    so = thuoc_do.so_voi_moc
    moc = {"a.py::f": 20}
    assert so("moc-phuc-tap", {"a.py::f": 20}, moc) == []
    assert so("moc-phuc-tap", {"a.py::f": 17}, moc) == []
    loi = so("moc-phuc-tap", {"a.py::f": 21}, moc)
    assert len(loi) == 1 and "a.py::f" in loi[0]
    assert len(so("moc-phuc-tap", {"a.py::g": 16}, moc)) == 1  # hàm mới vượt 15


def test_so_sanh_ten_ham_trung_ca_bien() -> None:
    so = thuoc_do.so_voi_moc
    moc = {"tinh_no": 2}
    assert so("moc-ten-ham-trung", {"tinh_no": 2}, moc) == []
    assert len(so("moc-ten-ham-trung", {"tinh_no": 3}, moc)) == 1
    loi = so("moc-ten-ham-trung", {"tinh_no": 2, "ham_moi": 2}, moc)
    assert len(loi) == 1 and "ham_moi" in loi[0]


@pytest.mark.parametrize("chi_so", ["moc-if-theo-vai", "moc-cua-thieu-response-model"])
def test_so_sanh_dem_theo_tep_ca_bien(chi_so: str) -> None:
    so = thuoc_do.so_voi_moc
    moc = {"x": 3}
    assert so(chi_so, {"x": 3}, moc) == []
    assert so(chi_so, {"x": 2}, moc) == []
    assert len(so(chi_so, {"x": 4}, moc)) == 1
    assert len(so(chi_so, {"y": 1}, moc)) == 1  # tệp mới, mốc 0


def test_ha_moc_chi_ha_khong_nang() -> None:
    moc = {"a": 10, "b": 5, "c": 7}
    # a giảm, b bằng, c biến mất (đã sửa hết), d là khoá mới (không được lọt vào mốc)
    moi = thuoc_do.ha_moc({"a": 6, "b": 5, "d": 99}, moc)
    assert moi == {"a": 6, "b": 5}
    assert all(moi[k] <= moc[k] for k in moi)


# ── Nhóm 3: thử ngược — bộ đo phải THẤY vi phạm giả ─────────────────────────


@pytest.fixture
def du_an_gia(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Dựng cây `src/{clinicai,dashboard}` giả rồi trỏ bộ đo vào đó."""
    for ten, gia_tri in {
        "REPO": tmp_path,
        "SRC": tmp_path / "src",
        "BACKEND": tmp_path / "src" / "clinicai",
        "DASHBOARD": tmp_path / "src" / "dashboard",
    }.items():
        monkeypatch.setattr(thuoc_do, ten, gia_tri)
    (tmp_path / "src" / "clinicai" / "api").mkdir(parents=True)
    (tmp_path / "src" / "dashboard" / "app").mkdir(parents=True)
    return tmp_path


def test_do_tran_kich_thuoc_thay_tep_dai(du_an_gia: Path) -> None:
    (du_an_gia / "src" / "clinicai" / "vua.py").write_text("x = 1\n" * 400)
    (du_an_gia / "src" / "clinicai" / "dai.py").write_text("x = 1\n" * 401)
    (du_an_gia / "src" / "dashboard" / "types.generated.ts").write_text("x\n" * 999)
    assert thuoc_do.do_tran_kich_thuoc() == {"src/clinicai/dai.py": 401}


def test_do_phuc_tap_thay_ham_16_khong_thay_ham_15(du_an_gia: Path) -> None:
    def ham(ten: str, so_nhanh: int) -> str:
        nhanh = "\n".join(
            f"    if x == {i}:\n        return {i}" for i in range(so_nhanh)
        )
        return f"def {ten}(x: int) -> int:\n{nhanh}\n    return 0\n"

    # McCabe = số `if` + 1
    ma = ham("vua_du", 14) + "\n" + ham("rat_roi", 15)
    (du_an_gia / "src" / "clinicai" / "m.py").write_text(ma)
    assert thuoc_do.do_moc_phuc_tap() == {"src/clinicai/m.py::rat_roi": 16}


def test_do_phuc_tap_khong_bi_noqa_che(du_an_gia: Path) -> None:
    nhanh = "\n".join(f"    if x == {i}:\n        return {i}" for i in range(16))
    (du_an_gia / "src" / "clinicai" / "n.py").write_text(
        f"def lach(x: int) -> int:  # noqa: C901\n{nhanh}\n    return 0\n"
    )
    assert thuoc_do.do_moc_phuc_tap() == {"src/clinicai/n.py::lach": 17}


def test_lap_moc_tu_choi_khi_da_co_moc(
    du_an_gia: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ten_moc = {c: du_an_gia / f"{c}.json" for c in thuoc_do.CHI_SO}
    monkeypatch.setattr(thuoc_do, "TEN_MOC", ten_moc)
    ten_moc["moc-phuc-tap"].write_text('{"chi_tiet": {"a::f": 20}}')
    monkeypatch.setattr("sys.argv", ["thuoc-do.py", "--lap-moc"])
    assert thuoc_do.main() == 2
    assert not ten_moc["tran-kich-thuoc"].exists()  # không ghi gì
    assert "Từ chối" in capsys.readouterr().out


def test_main_ha_moc_chi_ha_khong_nang(
    du_an_gia: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    b = du_an_gia / "src" / "clinicai"
    (b / "a.py").write_text("x = 1\n" * 450)  # đang 450, mốc cũ 500 → hạ về 450
    ten_moc = {c: du_an_gia / f"{c}.json" for c in thuoc_do.CHI_SO}
    monkeypatch.setattr(thuoc_do, "TEN_MOC", ten_moc)
    for c in thuoc_do.CHI_SO:
        ten_moc[c].write_text('{"chi_tiet": {}}')
    ten_moc["tran-kich-thuoc"].write_text(
        '{"chi_tiet": {"src/clinicai/a.py": 500, "src/clinicai/da_tach.py": 600}}'
    )
    monkeypatch.setattr("sys.argv", ["thuoc-do.py", "--ha-moc"])
    assert thuoc_do.main() == 0
    moi = json.loads(ten_moc["tran-kich-thuoc"].read_text())["chi_tiet"]
    assert moi == {"src/clinicai/a.py": 450}  # hạ, và bỏ tệp đã hết vi phạm
    # Dài thêm thì --ha-moc từ chối và KHÔNG ghi đè mốc
    (b / "a.py").write_text("x = 1\n" * 501)
    assert thuoc_do.main() == 1
    cu = json.loads(ten_moc["tran-kich-thuoc"].read_text())["chi_tiet"]
    assert cu == {"src/clinicai/a.py": 450}


def test_do_if_theo_vai_ca_bien(du_an_gia: Path) -> None:
    app = du_an_gia / "src" / "dashboard" / "app"
    (app / "A.tsx").write_text(
        'if (role === "DOCTOR") a();\n'
        "if (canWriteClinical(role)) b();\n"
        '// if (role === "CSKH") đã comment\n'
        'const x = "DOCTOR";\n'  # chỉ nhắc tên vai, không so sánh
        "if (x) c();\n"
    )
    (app / "A.test.tsx").write_text('if (role === "DOCTOR") a();\n')
    assert thuoc_do.do_moc_if_theo_vai() == {"src/dashboard/app/A.tsx": 2}


def test_do_ten_ham_trung_chi_dem_cap_module(du_an_gia: Path) -> None:
    b = du_an_gia / "src" / "clinicai"
    (b / "a.py").write_text("def tinh_no():\n    pass\n\ndef rieng_a():\n    pass\n")
    (b / "b.py").write_text(
        "def tinh_no():\n    pass\n\nclass K:\n    def rieng_a(self):\n        pass\n"
    )
    assert thuoc_do.do_moc_ten_ham_trung() == {"tinh_no": 2}


def test_do_cua_thieu_response_model(du_an_gia: Path) -> None:
    (du_an_gia / "src" / "clinicai" / "api" / "r.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n\n"
        "@router.get('/co', response_model=dict)\n"
        "async def co():\n    return {}\n\n"
        "@router.post('/thieu')\n"
        "async def thieu():\n    return {}\n\n"
        "@router.delete('/thieu2')\n"
        "def thieu2():\n    return {}\n"
    )
    assert thuoc_do.do_moc_cua_thieu_response_model() == {"src/clinicai/api/r.py": 2}
