"""Agent soát hệ thống (scripts/soat_he_thong) — hàng rào AN TOÀN và độ chính xác.

Ba nhóm:
1. CHỈ ĐỌC — quét mã nguồn của chính agent: không mạng, không ssh, không ghi ngoài
   thư mục kết quả, SQL chỉ SELECT. Đây là lời hứa "quét thôi, không làm hỏng prod";
   test này giữ cho lời hứa không bị ai lỡ tay phá.
2. ĐỘT BIẾN — dựng một repo GIẢ có lỗi cài sẵn, bộ quét phải bắt được; và repo GIẢ
   không lỗi thì phải im. Thiếu nhóm này thì "0 phát hiện" không có nghĩa gì.
3. REPO THẬT — chạy hết bộ quét, mọi trích dẫn phải mở lại được.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

GOC = Path(__file__).resolve().parents[3]
SCRIPTS = GOC / "scripts"
sys.path.insert(0, str(SCRIPTS))

from soat_he_thong import bat_bien, doc_du_lieu, kiem_trich_dan  # noqa: E402
from soat_he_thong.bo_quet import DANH_SACH, nap  # noqa: E402
from soat_he_thong.khuon import (  # noqa: E402
    LoaiVanDe,
    MucBangChung,
    PhatHien,
    TrichDan,
    UuTien,
)
from soat_he_thong.nguon import Nguon  # noqa: E402

GOI = SCRIPTS / "soat_he_thong"
MA_AGENT = sorted(GOI.rglob("*.py"))

# ── 1. CHỈ ĐỌC ──────────────────────────────────────────────────────────────

CAM_IMPORT = {
    "asyncpg",
    "psycopg",
    "psycopg2",
    "requests",
    "httpx",
    "aiohttp",
    "socket",
    "paramiko",
    "smtplib",
    "ftplib",
    "shutil",
}
#: Chỉ những tệp này được dùng thư viện tương ứng.
CHO_PHEP = {
    # docker exec vào container LOCAL; lệnh đọc lịch sử mã (show/diff) cho thước đo
    "subprocess": {"doc_du_lieu.py", "thuoc_do.py"},
    "http.server": {"may_xem.py"},  # nghe 127.0.0.1
    # Cổng DUY NHẤT ra Internet: HTTPS tới host trong danh sách, có trần chi tiêu.
    "urllib.request": {"khach.py"},
    "urllib.error": {"khach.py"},
}
#: Chỉ những tệp này được GHI tệp (và chỉ vào thư mục kết quả).
CHO_PHEP_GHI = {
    "chay.py",
    "may_xem.py",
    "chi_phi.py",
    "thuoc_do.py",
    "chay_model.py",
    "soat_toan_bo.py",  # sổ "đã đọc" + ứng viên thô, trong thư mục kết quả
}
HAM_GHI = {"write_text", "write_bytes", "unlink", "rmdir", "mkdir", "rename", "open"}


def _imports(cay: ast.Module) -> set[str]:
    ra: set[str] = set()
    for n in ast.walk(cay):
        if isinstance(n, ast.Import):
            ra.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            ra.add(n.module)
    return ra


@pytest.mark.parametrize("tep", MA_AGENT, ids=lambda p: p.name)
def test_agent_khong_import_mang_hay_ghi_tep_la(tep: Path) -> None:
    cay = ast.parse(tep.read_text(encoding="utf8"))
    imp = _imports(cay)
    xau = {i for i in imp if i.split(".")[0] in CAM_IMPORT}
    assert not xau, f"{tep.name} import thư viện cấm cho agent chỉ-đọc: {xau}"
    for thu_vien, ds in CHO_PHEP.items():
        if any(i == thu_vien or i.startswith(thu_vien + ".") for i in imp):
            assert tep.name in ds, f"{tep.name} không được dùng {thu_vien}"
    ghi = {
        n.func.attr
        for n in ast.walk(cay)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in HAM_GHI
        # `opener.open(req)` của urllib là gọi mạng (canh bằng CHO_PHEP), không ghi tệp.
        and not (isinstance(n.func.value, ast.Name) and n.func.value.id == "opener")
    }
    if ghi:
        assert tep.name in CHO_PHEP_GHI, f"{tep.name} ghi tệp: {ghi}"
    mo = [
        n
        for n in ast.walk(cay)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "open"
    ]
    assert not mo, f"{tep.name} dùng open(): đọc qua Nguon, ghi qua write_text"


def test_agent_khong_goi_ssh_va_khong_nghe_moi_giao_dien() -> None:
    cam = {"ssh", "scp", "rsync", "kubectl", "0.0.0.0"}  # noqa: S104
    for tep in MA_AGENT:
        cay = ast.parse(tep.read_text(encoding="utf8"))
        for n in ast.walk(cay):
            if isinstance(n, ast.Constant) and n.value in cam:
                raise AssertionError(
                    f"{tep.name}:{n.lineno} dùng chuỗi cấm {n.value!r}"
                )


def test_may_xem_chi_nghe_localhost() -> None:
    txt = (GOI / "may_xem.py").read_text(encoding="utf8")
    assert 'ThreadingHTTPServer(("127.0.0.1"' in txt


def test_chi_container_local_duoc_chay() -> None:
    for ten in ("clinicai_thu_db", "chung_test_db", "ci_may_test"):
        doc_du_lieu.kiem_container(ten)
    for xau in ("clinicai-vps", "postgres", "prod_db", "222.255.214.133", ""):
        with pytest.raises(SystemExit):
            doc_du_lieu.kiem_container(xau)


def test_moi_bat_bien_chi_la_select() -> None:
    ma = [b.ma for b in bat_bien.BAT_BIEN]
    assert len(ma) == len(set(ma))
    for b in bat_bien.BAT_BIEN:
        bat_bien.kiem_chi_select(b.sql)
        bat_bien.bao_boc(b)


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM payment",
        "UPDATE visit SET status='x'",
        "SELECT 1; DROP TABLE visit",
        "SELECT * FROM visit FOR UPDATE",
        "SELECT pg_sleep(100)",
        "SELECT nextval('s')",
        "WITH x AS (DELETE FROM a RETURNING 1) SELECT * FROM x",
        "SELECT set_config('a','b',false)",
        "",
    ],
)
def test_bat_bien_cam_cau_khong_phai_select(sql: str) -> None:
    with pytest.raises(ValueError):
        bat_bien.kiem_chi_select(sql)


def test_tep_sql_xuat_ra_chi_doc() -> None:
    s = bat_bien.tao_tep_sql()
    assert s.count("BEGIN READ ONLY;") == len(bat_bien.BAT_BIEN)
    assert s.count("ROLLBACK;") == len(bat_bien.BAT_BIEN)
    assert "COMMIT" not in s.upper()


# ── 2. ĐỘT BIẾN: repo giả có lỗi cài sẵn ────────────────────────────────────

GUARD = """
from fastapi import APIRouter, Depends
router = APIRouter()
_GHI = cua_quyen("payment.service.collect")
"""


def _dung(tmp: Path, tep: dict[str, str]) -> Nguon:
    for ten, nd in tep.items():
        p = tmp / ten
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(nd, encoding="utf8")
    return Nguon(tmp)


ROUTER_LOI = (
    GUARD
    + """
@router.post("/a/co-cua-co-vet")
async def tot(identity=Depends(_GHI)):
    await emit_event(None, ten="x.y")

@router.post("/a/thieu-cua")
async def thieu_cua(identity=Depends(get_current_identity)):
    await emit_event(None, ten="x.y")

@router.post("/a/thieu-vet")
async def thieu_vet(identity=Depends(_GHI)):
    await conn.execute("UPDATE service_price SET unit_price = 1")
"""
)


def test_cua_route_bat_duoc_route_thieu_cua(tmp_path: Path) -> None:
    n = _dung(tmp_path, {"src/clinicai/api/v1/routers/r.py": ROUTER_LOI})
    ds, do = nap("cua_route")(n)
    khoa = {p.khoa for p in ds}
    assert khoa == {"POST /api/v1/a/thieu-cua"}, khoa
    assert do.da_nhin["route ghi"] == 3


def test_cua_route_chap_nhan_bi_danh_sach_qua_bi_danh(tmp_path: Path) -> None:
    # `_CUA = _GHI` ở module khác — cửa được import lại dưới tên khác.
    n = _dung(
        tmp_path,
        {
            "src/clinicai/permissions/cua.py": 'cua_y_khoa = cua_quyen("clinical.x")',
            "src/clinicai/api/v1/routers/r.py": GUARD.replace("_GHI =", "_X =")
            + '_ALIAS = cua_y_khoa\n@router.post("/b")\n'
            "async def b(i=Depends(_ALIAS)):\n    return 1\n",
        },
    )
    ds, _ = nap("cua_route")(n)
    assert ds == []


def test_ghi_khong_dau_vet_bat_dung_route(tmp_path: Path) -> None:
    n = _dung(tmp_path, {"src/clinicai/api/v1/routers/r.py": ROUTER_LOI})
    ds, _ = nap("ghi_khong_dau_vet")(n)
    assert {p.khoa for p in ds} == {"POST /api/v1/a/thieu-vet"}
    assert all(p.muc_bang_chung is MucBangChung.SUY_RA for p in ds)


def test_ghi_khong_dau_vet_thay_sql_o_hang_ngoai_ham(tmp_path: Path) -> None:
    src = (
        GUARD
        + """
_SQL = "INSERT INTO inventory_txn (id) VALUES (1)"

@router.post("/kho/nhap")
async def nhap(i=Depends(_GHI)):
    await conn.execute(_SQL)
"""
    )
    n = _dung(tmp_path, {"src/clinicai/api/v1/routers/r.py": src})
    ds, _ = nap("ghi_khong_dau_vet")(n)
    assert ds == []


def test_day_fe_be_bat_duoc_goi_den_route_khong_ton_tai(tmp_path: Path) -> None:
    n = _dung(
        tmp_path,
        {
            "src/clinicai/api/v1/routers/r.py": GUARD
            + '@router.post("/co-that/{id}")\n'
            "async def a(i=Depends(_GHI)):\n    pass\n",
            "src/dashboard/app/x.tsx": 'fetch("/api/v1/co-that/${id}")\n'
            'fetch("/api/v1/khong-co/abc")\n',
        },
    )
    ds, _ = nap("day_fe_be")(n)
    fe = {p.khoa for p in ds if p.khoa.startswith("fe->be")}
    assert fe == {"fe->be /api/v1/khong-co/abc"}
    assert not any(p.khoa.startswith("be-mo-coi") for p in ds)


CAT_LOI = """
from dataclasses import dataclass
KHOI = {"a": 1, "b": 2, "mo_coi": 3}
KHOI_AN = frozenset()
KHOI_NOI_BO = frozenset()
@dataclass
class Q:
    ma: str
    khoi: str
QUYEN = {"q1": Q("q1", "a"), "q3": Q("q3", "mo_coi")}
@dataclass
class M:
    ma: str
    ten: str
    cac_duong: list
    khoi: list
MAN = {"l1": M("l1", "L1", ["/co-trang", "/mat-trang"], ["a", "b"])}
VAI_THEO_LEGO = {"l1": "X", "ma_ma": "Y"}
"""


def test_quyen_lego_bat_khoi_mo_coi_duong_chet_va_anh_xa_chet(tmp_path: Path) -> None:
    n = _dung(
        tmp_path,
        {
            "src/clinicai/permissions/catalogue.py": CAT_LOI,
            "src/dashboard/app/(dashboard)/co-trang/page.tsx": "export default 1",
        },
    )
    ds, _ = nap("quyen_lego")(n)
    khoa = {p.khoa for p in ds}
    assert khoa == {
        "khoi-mo-coi mo_coi",
        "lego-duong-chet l1 /mat-trang",
        "vai-theo-lego-chet ma_ma",
    }, khoa


CAT_SK = """
class SuKien:
    def __init__(self, **kw): ...
DANH_MUC = {
    "a.da_khai": SuKien(ten="a.da_khai", consumers=[X]),
    "a.khong_ai_phat": SuKien(ten="a.khong_ai_phat", consumers=[X]),
    "a.khong_ai_nghe": SuKien(ten="a.khong_ai_nghe", consumers=[]),
}
"""


def test_su_kien_bat_phat_khong_khai_khai_khong_phat(tmp_path: Path) -> None:
    phat = (
        "async def f(c):\n"
        '    await emit_event(c, ten="a.da_khai")\n'
        '    await emit_event(c, ten="a.khong_ai_nghe")\n'
        '    await emit_event(c, ten="b.chua_khai")\n'
    )
    n = _dung(
        tmp_path,
        {
            "src/clinicai/events/catalogue.py": CAT_SK,
            "src/clinicai/services/s.py": phat,
        },
    )
    ds, _ = nap("su_kien")(n)
    khoa = {p.khoa for p in ds}
    assert "phat-khong-khai b.chua_khai" in khoa
    assert "khai-khong-phat a.khong_ai_phat" in khoa
    assert "phat-khong-ai-nghe" in khoa
    chua_khai = next(p for p in ds if p.khoa.startswith("phat-khong-khai"))
    assert chua_khai.uu_tien is UuTien.P0


def test_cua_trich_dan_loai_phat_hien_bia_dong(tmp_path: Path) -> None:
    n = _dung(tmp_path, {"src/a.py": "x = 1\ny = 2\nz = 3\n" + "pad\n" * 20})

    def ph(tep: str, dong: int, doan: str) -> PhatHien:
        return PhatHien(
            "t", f"{tep}{dong}", LoaiVanDe.LOGIC_CO_VAN_DE, UuTien.P1,
            MucBangChung.QUAN_SAT, 1.0, "", [], "", "", "", "", "", "",
            trich_dan=[TrichDan(tep, dong, doan)],
        )  # fmt: skip

    dung = ph("src/a.py", 2, "y = 2")
    lech_it = ph("src/a.py", 3, "y = 2")  # lệch 1 dòng — chấp nhận
    bia = ph("src/a.py", 20, "y = 2")  # bịa số dòng
    khong_tep = ph("src/khong_co.py", 1, "x")
    giu, loai = kiem_trich_dan.loc(n, [dung, lech_it, bia, khong_tep])
    assert [p.khoa for p in giu] == [dung.khoa, lech_it.khoa]
    assert {p.khoa for p, _ in loai} == {bia.khoa, khong_tep.khoa}


def test_phat_hien_id_on_dinh_va_doc_lai_duoc() -> None:
    p = PhatHien(
        "t", "k", LoaiVanDe.DU_LIEU_SAI, UuTien.P0, MucBangChung.SUY_RA, 0.5,
        "a", ["b"], "c", "d", "e", "f", "g", "h",
        trich_dan=[TrichDan("x.py", 1, "x")],
    )  # fmt: skip
    assert PhatHien.tu_dict(p.dict()).id == p.id
    assert len(p.id) == 12


def test_bat_bien_phan_tich_dau_ra_bo_dong_rac() -> None:
    txt = 'BEGIN\n{"ma": "D01", "so_dong": 2, "mau": []}\nnoise\n{"x": 1}\nROLLBACK\n'
    assert doc_du_lieu.phan_tich_dau_ra(txt) == [{"ma": "D01", "so_dong": 2, "mau": []}]


# ── 3. REPO THẬT ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("ten", DANH_SACH)
def test_bo_quet_chay_tren_repo_that_va_trich_dan_mo_lai_duoc(ten: str) -> None:
    n = Nguon()
    ds, do = nap(ten)(n)
    assert do.da_nhin, f"{ten} không báo đã nhìn gì"
    assert do.khong_nhin_duoc, f"{ten} không nói mình mù ở đâu"
    _, loai = kiem_trich_dan.loc(n, ds)
    assert not loai, [(p.khoa, ly) for p, ly in loai]
    assert len({p.id for p in ds}) == len(ds), "id phát hiện phải duy nhất"


# ── 4. MÁY XEM: chỉ ghi quyết định của người, chống CSRF ────────────────────


def _may_xem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[int, Path]:
    import threading
    from http.server import ThreadingHTTPServer

    from soat_he_thong import may_xem

    lan = tmp_path / "lan1"
    lan.mkdir()
    (lan / "phat-hien.jsonl").write_text("", encoding="utf8")
    (lan / "do-phu.json").write_text("[]", encoding="utf8")
    monkeypatch.setattr(may_xem, "KET_QUA", tmp_path)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), may_xem.tao_handler(lan))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1], tmp_path / "so-duyet.jsonl"


def _gui(cong: int, kieu: str, duong: str = "", **hdr: str) -> int:
    import http.client

    c = http.client.HTTPConnection("127.0.0.1", cong, timeout=5)
    h = {k.replace("_", "-"): v for k, v in hdr.items()}
    if kieu == "GET":
        c.request("GET", duong or "/", headers=h)
    else:
        body = b'{"id": "0123456789ab", "quyet_dinh": "bo_qua", "ly_do": "da biet"}'
        c.request("POST", duong or "/duyet", body=body, headers=h)
    return c.getresponse().status


def test_trang_theo_doi_va_nut_dung_khan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cong, _ = _may_xem(tmp_path, monkeypatch)
    assert _gui(cong, "GET", "/tien-do") == 200
    dung = tmp_path / "DUNG"
    # Trang web lạ không bấm được nút dừng/chạy tiếp thay người.
    assert _gui(cong, "POST", "/dung", Content_Type="text/plain") == 415
    assert not dung.exists()
    assert _gui(cong, "POST", "/dung", Content_Type="application/json") == 200
    assert dung.exists()
    assert _gui(cong, "POST", "/tiep", Content_Type="application/json") == 200
    assert not dung.exists()


def test_may_xem_ghi_dung_quyet_dinh_va_chan_csrf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cong, so_duyet = _may_xem(tmp_path, monkeypatch)
    assert _gui(cong, "GET") == 200
    assert _gui(cong, "GET", Host="evil.example") == 403  # DNS rebinding
    # Trang web khác gửi form/text-plain: bị chặn, không ghi gì.
    assert _gui(cong, "POST", Content_Type="text/plain") == 415
    assert (
        _gui(cong, "POST", Content_Type="application/json", Origin="http://evil.io")
        == 403
    )
    assert not so_duyet.exists()
    assert _gui(cong, "POST", Content_Type="application/json") == 200
    ghi = [json.loads(d) for d in so_duyet.read_text(encoding="utf8").splitlines()]
    assert len(ghi) == 1 and ghi[0]["quyet_dinh"] == "bo_qua" and ghi[0]["ly_do"]


def test_ghi_quyet_dinh_tu_choi_du_lieu_xau(tmp_path: Path) -> None:
    from soat_he_thong.may_xem import ghi_quyet_dinh

    f = tmp_path / "sd.jsonl"
    xau: list[dict[str, object]] = [
        {"id": "../../etc/passwd", "quyet_dinh": "chap_nhan"},
        {"id": "0123456789ab", "quyet_dinh": "xoa_het"},
        {"id": "0123456789ab", "quyet_dinh": "bo_qua", "ly_do": "  "},
        {"id": "0123456789AB", "quyet_dinh": "chap_nhan"},
    ]
    for d in xau:
        assert ghi_quyet_dinh(f, d, "u") is not None, d
    assert not f.exists()
    ok = ghi_quyet_dinh(f, {"id": "0123456789ab", "quyet_dinh": "chap_nhan"}, "u")
    assert ok is None and f.exists()
