#!/usr/bin/env python3
"""Thước đo chất lượng ClinicAI dạng RATCHET — "chỉ được giảm" (Tuyền chốt 24/11/2026).

Năm chỉ số, mỗi chỉ số một tệp mốc JSON trong `scripts/`. Mốc = số đo ngày lập mốc.
Test `src/tests/unit/test_thuoc_do_ratchet.py` đỏ khi số đo VƯỢT mốc. Bớt được thì
hạ mốc (lệnh bên dưới) — mốc KHÔNG BAO GIỜ được nâng; muốn nâng là đang vi phạm luật.

    python3 scripts/thuoc-do.py                 # in số đo hiện tại so với mốc
    python3 scripts/thuoc-do.py --kiem          # như test, thoát 1 nếu vượt mốc
    python3 scripts/thuoc-do.py --ha-moc        # hạ mốc xuống số đo hiện tại (chỉ hạ)
    python3 scripts/thuoc-do.py --lap-moc       # CHỈ lần đầu: tạo mốc từ số đo hôm nay

Cách đếm (đổi cách đếm = đổi con số, phải ghi lại ở đây và lập lại mốc có lý do):

1. **tran-kich-thuoc** — số dòng (`splitlines`) mỗi tệp `.py/.ts/.tsx/.mts/.mjs/.cjs/.js`
   dưới `src/`, bỏ `node_modules`, `.next`, `__pycache__`, tệp sinh `*.generated.ts`.
   Tệp mới ≤ 400 dòng (luật TK5). Tệp đã quá 400 dòng ghi trong mốc theo TỪNG tệp,
   không được dài thêm.
2. **moc-phuc-tap** — hàm trong `src/clinicai` có độ phức tạp McCabe > 15 (`ruff
   --select C901`). Hàm vượt không được tăng số; hàm mới không được vượt 15.
3. **moc-if-theo-vai** — số DÒNG trong `src/dashboard` (app, lib, components, proxy.ts)
   mà TSX/TS tự so sánh vai: (A) so trực tiếp với tên vai `=== "DOCTOR"`…, hoặc (B) gọi
   hàm vai của `lib/roles.ts` (`isDoctorRole(`, `canWriteClinical(`…). Bỏ dòng chú thích,
   `*.test.*`, `lib/roles.ts` (nơi định nghĩa vai), tệp sinh. Mỗi dòng tính một lần.
   Cách đếm khớp bản đo 23/11 (65 dòng); con số "123" cũ không có nguồn đếm.
4. **moc-ten-ham-trung** — tên hàm CẤP MODULE (`def`/`async def`) trong `src/clinicai`
   xuất hiện ở ≥ 2 tệp Python. Mốc ghi tên → số tệp; tên mới hoặc số tệp tăng là vi phạm.
5. **moc-cua-thieu-response-model** — cửa API (`@x.get|post|put|patch|delete(...)`) trong
   `src/clinicai/api` KHÔNG có `response_model=`. Mốc theo từng tệp router.
"""

# ruff: noqa: E501
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
BACKEND = SRC / "clinicai"
DASHBOARD = SRC / "dashboard"
SCRIPTS = REPO / "scripts"

TRAN_FILE_MOI = 400  # luật TK5
NGUONG_PHUC_TAP = 15

CHI_SO = (
    "tran-kich-thuoc",
    "moc-phuc-tap",
    "moc-if-theo-vai",
    "moc-ten-ham-trung",
    "moc-cua-thieu-response-model",
)

_BO_QUA_THU_MUC = {"node_modules", ".next", "__pycache__", ".venv", "public"}
_DUOI_CODE = {".py", ".ts", ".tsx", ".mts", ".mjs", ".cjs", ".js"}


def _tep_nguon(goc: Path, duoi: set[str]) -> list[Path]:
    ket: list[Path] = []
    for p in sorted(goc.rglob("*")):
        if p.suffix not in duoi or not p.is_file():
            continue
        if _BO_QUA_THU_MUC & set(p.relative_to(goc).parts):
            continue
        if p.name.endswith(".generated.ts"):
            continue
        ket.append(p)
    return ket


def _rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def _doc(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


# ── 1. kích thước tệp ──────────────────────────────────────────────────────


def do_tran_kich_thuoc() -> dict[str, int]:
    """{tệp: số dòng} cho mọi tệp > 400 dòng."""
    ket: dict[str, int] = {}
    for p in _tep_nguon(SRC, _DUOI_CODE):
        n = len(_doc(p).splitlines())
        if n > TRAN_FILE_MOI:
            ket[_rel(p)] = n
    return ket


# ── 2. McCabe ──────────────────────────────────────────────────────────────

_RE_PHUC_TAP = re.compile(r"`(?P<ten>[^`]+)` is too complex \((?P<so>\d+) >")


def do_moc_phuc_tap() -> dict[str, int]:
    """{tệp::hàm: độ phức tạp} cho hàm > 15. Trùng tên trong một tệp → hậu tố #2, #3."""
    ruff = Path(sys.executable).parent / "ruff"
    lenh = [
        str(ruff if ruff.exists() else "ruff"),
        "check",
        "--select",
        "C901",
        "--config",
        f"lint.mccabe.max-complexity={NGUONG_PHUC_TAP}",
        "--no-cache",
        "--isolated",
        "--output-format",
        "json",
        str(BACKEND),
    ]
    r = subprocess.run(lenh, capture_output=True, text=True, cwd=REPO, check=False)
    if r.returncode not in (0, 1):
        raise RuntimeError(f"ruff lỗi (mã {r.returncode}): {r.stderr[:500]}")
    muc = json.loads(r.stdout or "[]")
    muc.sort(key=lambda m: (m["filename"], m["location"]["row"]))
    ket: dict[str, int] = {}
    for m in muc:
        kq = _RE_PHUC_TAP.search(m["message"])
        if not kq:
            continue
        khoa = f"{_rel(Path(m['filename']))}::{kq['ten']}"
        k, d = khoa, 2
        while k in ket:
            k, d = f"{khoa}#{d}", d + 1
        ket[k] = int(kq["so"])
    return ket


# ── 3. if theo vai trong TS/TSX ────────────────────────────────────────────

_VAI = (
    "DOCTOR|ULTRASOUND_DOCTOR|NURSE_ULTRASOUND|TKYK|CSKH|MANAGEMENT|RECEPTION|CASHIER"
    "|CASHIER_THUOC|CASHIER_DV|TRUONG_CA|PHARMACIST|ACCOUNTANT|DISPLAY|PARTNER"
)
_HAM_VAI = (
    "isDoctorRole|isPhysicianRole|isAdminRole|isUltrasoundDoctorRole|isNurseRole"
    "|isThuKyRole|canWriteClinical|canReadClinical|canWriteIntake"
    "|canOperateCustomerCare|isTruongCaRole|isOpsAdmin|canCheckin|canManageAppt"
    "|canEditPatient|isCashierRole|canSeeNav|canSeeNavGoc|luonBatChoVaiGoc|vaiLamViec"
)
_RE_VAI_A = re.compile(
    rf"""(?:(?:===|!==|==|!=)\s*["'](?:{_VAI})["']|["'](?:{_VAI})["']\s*(?:===|!==|==|!=))"""
)
_RE_VAI_B = re.compile(rf"\b(?:{_HAM_VAI})\s*\(")
_RE_CHU_THICH = re.compile(r"^\s*(//|/\*|\*)")


def do_moc_if_theo_vai() -> dict[str, int]:
    """{tệp: số dòng so sánh vai}."""
    ket: dict[str, int] = {}
    cac_tep = [
        p
        for goc in ("app", "lib", "components")
        for p in _tep_nguon(DASHBOARD / goc, {".ts", ".tsx"})
    ]
    proxy = DASHBOARD / "proxy.ts"
    if proxy.exists():
        cac_tep.append(proxy)
    for p in cac_tep:
        if ".test." in p.name or p == DASHBOARD / "lib" / "roles.ts":
            continue
        n = 0
        for dong in _doc(p).splitlines():
            if _RE_CHU_THICH.match(dong):
                continue
            if _RE_VAI_A.search(dong) or _RE_VAI_B.search(dong):
                n += 1
        if n:
            ket[_rel(p)] = n
    return ket


# ── 4. tên hàm cấp module trùng ────────────────────────────────────────────


def do_moc_ten_ham_trung() -> dict[str, int]:
    """{tên hàm: số tệp} cho tên xuất hiện ở ≥ 2 tệp Python của `src/clinicai`."""
    tep_co: dict[str, set[str]] = {}
    for p in _tep_nguon(BACKEND, {".py"}):
        try:
            cay = ast.parse(_doc(p))
        except SyntaxError:
            continue
        for nut in cay.body:
            if isinstance(nut, ast.FunctionDef | ast.AsyncFunctionDef):
                tep_co.setdefault(nut.name, set()).add(_rel(p))
    return {t: len(s) for t, s in sorted(tep_co.items()) if len(s) >= 2}


# ── 5. cửa API thiếu response_model ────────────────────────────────────────

_PHUONG_THUC = {"get", "post", "put", "patch", "delete"}


def do_moc_cua_thieu_response_model() -> dict[str, int]:
    """{tệp router: số cửa không có `response_model=`}."""
    ket: dict[str, int] = {}
    for p in _tep_nguon(BACKEND / "api", {".py"}):
        try:
            cay = ast.parse(_doc(p))
        except SyntaxError:
            continue
        n = 0
        for nut in ast.walk(cay):
            if not isinstance(nut, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for dec in nut.decorator_list:
                if not (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr in _PHUONG_THUC
                    and isinstance(dec.func.value, ast.Name)
                ):
                    continue
                if not any(k.arg == "response_model" for k in dec.keywords):
                    n += 1
        if n:
            ket[_rel(p)] = n
    return ket


# ── mốc & so sánh ──────────────────────────────────────────────────────────

DO = {
    "tran-kich-thuoc": do_tran_kich_thuoc,
    "moc-phuc-tap": do_moc_phuc_tap,
    "moc-if-theo-vai": do_moc_if_theo_vai,
    "moc-ten-ham-trung": do_moc_ten_ham_trung,
    "moc-cua-thieu-response-model": do_moc_cua_thieu_response_model,
}

TEN_MOC = {
    "tran-kich-thuoc": SCRIPTS / "tran-kich-thuoc.json",
    "moc-phuc-tap": SCRIPTS / "moc-phuc-tap.json",
    "moc-if-theo-vai": SCRIPTS / "moc-if-theo-vai.json",
    "moc-ten-ham-trung": SCRIPTS / "moc-ten-ham-trung.json",
    "moc-cua-thieu-response-model": SCRIPTS / "moc-cua-thieu-response-model.json",
}

_MO_TA = {
    "tran-kich-thuoc": "tệp > 400 dòng: số dòng từng tệp (tệp mới ≤ 400, tệp cũ không dài thêm)",
    "moc-phuc-tap": "hàm McCabe > 15: tệp::hàm → độ phức tạp",
    "moc-if-theo-vai": "dòng so sánh vai trong TS/TSX: tệp → số dòng",
    "moc-ten-ham-trung": "tên hàm cấp module trùng ở ≥ 2 tệp: tên → số tệp",
    "moc-cua-thieu-response-model": "cửa API thiếu response_model: tệp router → số cửa",
}

# Hỏi "làm gì để hết đỏ" — in kèm mọi thông báo vi phạm.
CACH_SUA = {
    "tran-kich-thuoc": (
        "Tách theo nghiệp vụ sang module mới, tệp cũ chỉ giữ một dòng gọi "
        "(luật 5 của .claude/rules/thiet-ke-code.md). Tệp MỚI phải ≤ 400 dòng."
    ),
    "moc-phuc-tap": (
        "Tách hàm thành các hàm nhỏ (mỗi nhánh `if`/`for`/`except` một hàm có tên), "
        "đưa về ≤ 15. Không nâng mốc."
    ),
    "moc-if-theo-vai": (
        "Đừng tự suy 'ai được bấm' trong TSX: để API trả cờ đã tính sẵn "
        "(vd `co_the_lay_mau`) và màn chỉ hiển thị (luật 7 của thiet-ke-code.md)."
    ),
    "moc-ten-ham-trung": (
        "Một câu hỏi — một hàm (luật 1): gọi hàm đã có thay vì viết bản thứ hai; "
        "nếu hai hàm thật sự khác nhau thì đặt tên nói rõ khác ở đâu."
    ),
    "moc-cua-thieu-response-model": (
        "Thêm `response_model=` (Pydantic) cho cửa mới (luật 7 của thiet-ke-code.md)."
    ),
}


def doc_moc(chi_so: str) -> dict[str, int]:
    f = TEN_MOC[chi_so]
    if not f.exists():
        raise FileNotFoundError(
            f"Thiếu tệp mốc {_rel(f)}. Lập lần đầu: python3 scripts/thuoc-do.py --lap-moc"
        )
    return {k: int(v) for k, v in json.loads(_doc(f))["chi_tiet"].items()}


def so_voi_moc(chi_so: str, do_duoc: dict[str, int], moc: dict[str, int]) -> list[str]:
    """Danh sách câu vi phạm (tiếng Việt, chỉ đúng tệp/hàm). Rỗng = đạt."""
    loi: list[str] = []
    for khoa, gia_tri in sorted(do_duoc.items()):
        tran = moc.get(khoa)
        if chi_so == "tran-kich-thuoc":
            if tran is None:
                loi.append(
                    f"{khoa}: tệp MỚI dài {gia_tri} dòng > trần {TRAN_FILE_MOI}. "
                    "Tách theo nghiệp vụ trước khi thêm."
                )
            elif gia_tri > tran:
                loi.append(
                    f"{khoa}: {gia_tri} dòng > mốc {tran} (dài thêm {gia_tri - tran}). "
                    "Tệp đã quá trần không được dài thêm — viết ở module mới."
                )
        elif chi_so == "moc-phuc-tap":
            if tran is None:
                loi.append(
                    f"{khoa}: hàm MỚI vượt trần, độ phức tạp {gia_tri} > {NGUONG_PHUC_TAP}."
                )
            elif gia_tri > tran:
                loi.append(
                    f"{khoa}: độ phức tạp {gia_tri} > mốc {tran}. Hàm đã vượt không được rối thêm."
                )
        elif chi_so == "moc-ten-ham-trung":
            if tran is None:
                loi.append(
                    f"hàm `{khoa}` đã có ở tệp khác — nay có thêm bản thứ {gia_tri}."
                    f" Tìm: grep -rn 'def {khoa}(' src/clinicai — gọi bản có sẵn, "
                    "hoặc đặt tên khác."
                )
            elif gia_tri > tran:
                loi.append(f"hàm `{khoa}` nay ở {gia_tri} tệp > mốc {tran}.")
        else:  # đếm theo tệp: if theo vai, cửa thiếu response_model
            nhan = (
                "dòng so sánh vai"
                if chi_so == "moc-if-theo-vai"
                else "cửa thiếu response_model"
            )
            if tran is None:
                loi.append(f"{khoa}: tệp mới có {gia_tri} {nhan} (mốc 0).")
            elif gia_tri > tran:
                loi.append(f"{khoa}: {gia_tri} {nhan} > mốc {tran}.")
    return loi


def ha_moc(do_duoc: dict[str, int], moc: dict[str, int]) -> dict[str, int]:
    """Mốc mới = chỉ các khoá còn vi phạm, không khoá nào cao hơn mốc cũ.

    Gọi khi `so_voi_moc` đã rỗng (số đo ≤ mốc ở mọi khoá) nên không bao giờ nâng.
    Khoá hết vi phạm (tệp đã tách, hàm đã gọn) bị bỏ khỏi mốc.
    """
    return {k: min(v, moc[k]) for k, v in do_duoc.items() if k in moc}


def tong(d: dict[str, int], chi_so: str) -> int:
    return (
        len(d)
        if chi_so in ("moc-phuc-tap", "moc-ten-ham-trung", "tran-kich-thuoc")
        else sum(d.values())
    )


def ghi_moc(chi_so: str, du_lieu: dict[str, int]) -> None:
    tep = TEN_MOC[chi_so]
    van_ban = {
        "_ghi_chu": (
            f"MỐC RATCHET — {_MO_TA[chi_so]}. CHỈ ĐƯỢC HẠ: sửa tốt thì chạy "
            "`python3 scripts/thuoc-do.py --ha-moc`. Nâng mốc để test xanh là vi phạm "
            "(thiet-ke-code.md, mục 'Khi một luật ở đây cản việc'). Cách đếm: đầu thuoc-do.py."
        ),
        "tong": tong(du_lieu, chi_so),
        "chi_tiet": dict(sorted(du_lieu.items())),
    }
    tep.write_text(
        json.dumps(van_ban, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Thước đo ratchet ClinicAI")
    ap.add_argument("--kiem", action="store_true", help="thoát 1 nếu vượt mốc")
    ap.add_argument("--ha-moc", action="store_true", help="hạ mốc xuống số đo (chỉ hạ)")
    ap.add_argument("--lap-moc", action="store_true", help="tạo mốc lần đầu")
    a = ap.parse_args()
    do_het = {c: DO[c]() for c in CHI_SO}
    co_loi = False
    for c in CHI_SO:
        if a.lap_moc:
            ghi_moc(c, do_het[c])
            print(f"đã lập mốc {c}: {tong(do_het[c], c)}")
            continue
        moc = doc_moc(c)
        loi = so_voi_moc(c, do_het[c], moc)
        print(
            f"{c}: đo {tong(do_het[c], c)} · mốc {tong(moc, c)} · {'ĐỎ' if loi else 'đạt'}"
        )
        for dong in loi:
            print(f"   ✗ {dong}")
        if loi:
            print(f"   → {CACH_SUA[c]}")
            co_loi = True
        elif a.ha_moc:
            moi = ha_moc(do_het[c], moc)
            if moi != moc:
                ghi_moc(c, moi)
                print(f"   ↓ đã hạ mốc {c}: {tong(moc, c)} → {tong(moi, c)}")
    if co_loi and a.ha_moc:
        print("Không hạ mốc khi còn vi phạm ở trên — sửa trước.")
    return 1 if co_loi and (a.kiem or a.ha_moc) else 0


if __name__ == "__main__":
    raise SystemExit(main())
