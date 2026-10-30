"""Máy quét chỉ-đọc: so bản khai lego (modules.py) với code thật.

Đo 4 thứ, mỗi phát hiện có tệp:dòng:
  ghi_cheo   — hàm ghi vào bảng mà bản khai nói thuộc khối khác
  bang_mo_coi — bảng bị ghi nhưng không khối nào khai giữ
  goi_cheo   — tệp import hàm từ tệp service của khối khác
  ghi_khong_su_kien — hàm ghi bảng state mà không phát sự kiện (trong chính hàm)
Chạy: python3 quet_backend.py <repo> <thu-muc-ket-qua>
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(sys.argv[1])
OUT = Path(sys.argv[2])
SRC = REPO / "src" / "clinicai"

GHI = re.compile(
    r"\b(?:INSERT\s+INTO\s+(?:public\.)?(?P<i>[a-z_][a-z0-9_]*)"
    r"|(?<!DO\s)(?<!FOR\s)UPDATE\s+(?:public\.)?(?P<u>[a-z_][a-z0-9_]*)\s+(?:(?:AS\s+)?[a-z_]+\s+)?SET\b"
    r"|DELETE\s+FROM\s+(?:public\.)?(?P<d>[a-z_][a-z0-9_]*))",
    re.IGNORECASE,
)
# Sổ nhật ký/sự kiện: ghi vào đây là ĐỂ LẠI DẤU VẾT, không phải đổi state của khối nào.
SO_GHI = {"event_log", "domain_event", "event_delivery", "loi_nhom", "nhat_ky_van_hanh"}


def doc_ban_khai() -> dict[str, dict[str, list[str]]]:
    cay = ast.parse((SRC / "modules.py").read_text())
    kq: dict[str, dict[str, list[str]]] = {}
    for nut in ast.walk(cay):
        if isinstance(nut, ast.Call) and getattr(nut.func, "id", None) == "Module":
            kw = {k.arg: k.value for k in nut.keywords}
            ma = ast.literal_eval(kw["ma"])
            m: dict[str, list[str]] = {}
            for ten in ("bang", "phat", "nghe", "ben_nhan", "goi_dong_bo", "lenh", "quyen"):
                v = kw.get(ten)
                try:
                    m[ten] = list(ast.literal_eval(v)) if v is not None else []
                except ValueError:
                    m[ten] = []
            kq[ma] = m
    return kq


def chuoi_trong(nut: ast.AST) -> str:
    phan: list[str] = []
    for n in ast.walk(nut):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            phan.append(n.value)
    return "\n".join(phan)


def su_kien_phat(ham: ast.AST, cua: tuple[str, ...] = ("emit_event",)) -> list[str]:
    ten: list[str] = []
    for n in ast.walk(ham):
        if isinstance(n, ast.Call):
            f = n.func
            fn = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if fn in cua:
                for k in n.keywords:
                    if k.arg in ("ten", "event_type", "loai"):
                        for c in ast.walk(k.value):
                            if isinstance(c, ast.Constant) and isinstance(c.value, str) and "." in c.value:
                                ten.append(c.value)
                for a in n.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str) and "." in a.value:
                        ten.append(a.value)
                if not ten:
                    ten.append("?")
    return ten


def main() -> None:
    khai = doc_ban_khai()
    chu_bang = {b: ma for ma, m in khai.items() for b in m["bang"]}
    ham_ghi: list[dict] = []
    imports: dict[str, set[str]] = defaultdict(set)
    tep_list = [p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts]
    for p in tep_list:
        rel = str(p.relative_to(REPO))
        try:
            cay = ast.parse(p.read_text())
        except SyntaxError:
            continue
        for n in ast.walk(cay):
            if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("clinicai.services."):
                imports[rel].add("src/clinicai/services/" + n.module.split(".")[2] + ".py")
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # chỉ lấy hàm không lồng trong hàm khác: hàm lồng tính vào hàm cha
                sql = chuoi_trong(n)
                bang = []
                for m in GHI.finditer(sql):
                    t = (m.group("i") or m.group("u") or m.group("d")).lower()
                    if t not in ("set", "into", "from", "only"):
                        bang.append(t)
                if bang:
                    ham_ghi.append({
                        "tep": rel, "ham": n.name, "dong": n.lineno,
                        "bang": sorted(set(bang)), "su_kien": sorted(set(su_kien_phat(n))),
                        "so_cu": sorted(set(su_kien_phat(n, ("record_event",)))),
                    })
    # bỏ trùng: hàm cha chứa hàm con ghi cùng bảng → giữ cả hai nhưng đánh dấu cha
    theo_tep: dict[str, Counter] = defaultdict(Counter)
    for h in ham_ghi:
        for b in h["bang"]:
            if b in chu_bang:
                theo_tep[h["tep"]][chu_bang[b]] += 1
    nha = {t: c.most_common(1)[0][0] for t, c in theo_tep.items()}

    ghi_cheo, mo_coi, khong_sk = [], Counter(), []
    for h in ham_ghi:
        n_tep = nha.get(h["tep"])
        state = [b for b in h["bang"] if b not in SO_GHI]
        for b in state:
            chu = chu_bang.get(b)
            if chu is None:
                mo_coi[b] += 1
            elif n_tep and chu != n_tep:
                ghi_cheo.append({**h, "bang_bi_ghi": b, "khoi_chu_bang": chu, "khoi_cua_tep": n_tep})
        if state and not h["su_kien"]:
            khong_sk.append({**h, "khoi_cua_tep": n_tep, "chi_so_cu": bool(h["so_cu"])})

    goi_cheo = []
    for tep, dich in imports.items():
        for d in dich:
            a, b = nha.get(tep), nha.get(d)
            if a and b and a != b:
                goi_cheo.append({"tep": tep, "goi_toi": d, "khoi_goi": a, "khoi_bi_goi": b})

    # emit cũng có ở hàm không ghi SQL trực tiếp → quét riêng mọi lời gọi emit
    moi_emit = Counter()
    for p in tep_list:
        try:
            cay = ast.parse(p.read_text())
        except SyntaxError:
            continue
        for s in su_kien_phat(cay):
            moi_emit[s] += 1
    khai_phat = {s for m in khai.values() for s in m["phat"]}

    OUT.mkdir(parents=True, exist_ok=True)
    kq = {
        "so_khoi": len(khai),
        "so_bang_co_chu": len(chu_bang),
        "so_ham_ghi": len(ham_ghi),
        "so_ham_ghi_state": sum(1 for h in ham_ghi if any(b not in SO_GHI for b in h["bang"])),
        "ghi_cheo": ghi_cheo,
        "bang_mo_coi": mo_coi.most_common(),
        "ghi_khong_su_kien": khong_sk,
        "goi_cheo": goi_cheo,
        "tep_khong_ro_khoi": sorted({h["tep"] for h in ham_ghi} - set(nha)),
        "su_kien_khai_ma_code_khong_phat": sorted(khai_phat - set(moi_emit)),
        "su_kien_code_phat_ma_khong_khai": sorted(set(moi_emit) - khai_phat - {"?"}),
        "so_su_kien_khai": len(khai_phat),
        "nha_cua_tep": nha,
        "ban_khai": khai,
    }
    (OUT / "backend.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1))
    print(f"khối={kq['so_khoi']} bảng có chủ={kq['so_bang_co_chu']} hàm ghi={kq['so_ham_ghi']} (state {kq['so_ham_ghi_state']})")
    print(f"ghi chéo={len(ghi_cheo)} (ở {len({g['tep']+g['ham'] for g in ghi_cheo})} hàm, {len({g['bang_bi_ghi'] for g in ghi_cheo})} bảng)")
    print(f"bảng mồ côi bị ghi={len(mo_coi)} · hàm ghi state không phát sự kiện lego={len(khong_sk)} (trong đó chỉ ghi sổ cũ {sum(1 for k in khong_sk if k['chi_so_cu'])})")
    print("bảng mồ côi bị ghi nhiều nhất:", ", ".join(f"{b}({c})" for b, c in mo_coi.most_common(15)))
    print(f"gọi chéo khối (import)={len(goi_cheo)} cạnh, {len({g['tep'] for g in goi_cheo})} tệp")
    print(f"sự kiện khai={len(khai_phat)} · khai mà code không phát={len(kq['su_kien_khai_ma_code_khong_phat'])} · code phát mà không khai={len(kq['su_kien_code_phat_ma_khong_khai'])}")
    print(f"tệp ghi DB mà không xác định được khối={len(kq['tep_khong_ro_khoi'])}")


main()
