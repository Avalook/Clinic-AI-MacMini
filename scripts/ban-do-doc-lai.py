#!/usr/bin/env python3
"""Đọc lại ghi chú CŨ của bản đồ code bằng API (AVIS, OpenAI-compatible, Sonnet 5.5).

Ghi chú tệp ở docs/ban-do/hieu/tep/*.json là chữ do model viết sau khi đọc kỹ
từng tệp. Code đổi thì ghi chú cũ đi — bản đồ báo "ghi chú cũ" nhờ dấu tệp trong
dau.json. Script này đọc lại đúng những tệp ấy (và tệp mới chưa có ghi chú), ghi
đè ghi chú, rồi ghi dấu mới cho riêng các tệp đã đọc lại.

    python3 scripts/ban-do-doc-lai.py --thu                # chỉ liệt kê tệp cần đọc lại
    python3 scripts/ban-do-doc-lai.py                      # đọc lại, tối đa 20 tệp / 2 USD
    python3 scripts/ban-do-doc-lai.py --toi-da 50 --tran-usd 5
    python3 scripts/ban-do-doc-lai.py --tep src/clinicai/services/bill_service.py

Khoá: biến môi trường AVIS_BASE_URL / AVIS_API_KEY / AVIS_MODEL, hoặc tệp
~/.clinicai-avis.env (chmod 600, NGOÀI repo). Không bao giờ in khoá. Chỉ gửi MÃ
NGUỒN — không gửi dữ liệu khách. Sau khi chạy: python3 scripts/ban-do-code.py
để sinh lại bản web, rồi duyệt diff docs/ban-do/hieu trước khi commit.
"""

# ruff: noqa: E501 — câu dặn model bằng tiếng Việt, cắt dòng chỉ làm khó đọc.
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
HIEU = GOC / "docs" / "ban-do" / "hieu"
DAU = HIEU / "dau.json"
TEP_MOI = HIEU / "tep" / "lat-moi.json"
BO = {"node_modules", "__pycache__", ".next", "tests", "generated"}
KHOA = {
    "lam_gi",
    "khoi",
    "ham_chinh",
    "luat",
    "doc_bang",
    "ghi_bang",
    "su_kien_phat",
    "su_kien_nghe",
    "goi_api",
    "bay",
    "muon_sua",
    "comment_cu",
    "chua_chac",
}

DAN = """Bạn đọc kỹ MỘT tệp mã nguồn của ClinicAI (phần mềm phòng khám: FastAPI ở
src/clinicai giữ mọi luật nghiệp vụ; Next.js ở src/dashboard chỉ vẽ giao diện;
Postgres). Hệ thống chia KHỐI lego (mã khối: payment, pharmacy, booking, reception,
consultation, service_order, service_routing, cskh, lieu_trinh, kho_vat_tu, ke_toan,
co_so, permission, …). Sự kiện: emit_event = bus lego; record_event / _log = nhật ký cũ.

Trả về DUY NHẤT một object JSON (không markdown, không lời dẫn) đúng khuôn:
{"lam_gi": "1–2 câu lời thường: tệp làm gì, cho ai, ở màn nào",
 "khoi": "<mã khối hoặc null>",
 "ham_chinh": [{"ten": "...", "dong": 10, "lam_gi": "..."}],
 "luat": [{"dong": 150, "noi_dung": "luật nghiệp vụ code THỰC THI, lời thường; tiền/kho kèm ví dụ số"}],
 "doc_bang": [], "ghi_bang": [], "su_kien_phat": [], "su_kien_nghe": [], "goi_api": [],
 "bay": [{"dong": 210, "noi_dung": "chỗ dễ sai khi sửa"}],
 "muon_sua": [{"viec": "muốn đổi X", "cho": "hàm Y dòng N"}],
 "comment_cu": [{"dong": 40, "vi_sao": "comment nói sai so với code / chỉ kể lịch sử"}],
 "chua_chac": []}

Luật: mỗi luật / bẫy trỏ ĐÚNG số dòng CODE thực thi (số dòng in ở đầu mỗi dòng
bên dưới), không suy từ comment hay tên hàm. Luật nghiệp vụ nằm trong TSX (giao diện
tự quyết) thì mở đầu "[TSX quyết] ". Tiếng Việt lời thường, thuật ngữ giải thích ngay.
Không bịa; không chắc thì ghi vào chua_chac. Mỗi chuỗi ≤ 300 ký tự. Tối đa 8 hàm chính.
Tệp vặt (< 40 dòng, re-export, kiểu) thì chỉ lam_gi + khoi, mảng rỗng."""


def cau_hinh() -> dict[str, str]:
    env = {
        k: os.environ[k]
        for k in ("AVIS_BASE_URL", "AVIS_API_KEY", "AVIS_MODEL")
        if k in os.environ
    }
    tep = Path.home() / ".clinicai-avis.env"
    if len(env) < 3 and tep.exists():
        for line in tep.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    thieu = [
        k for k in ("AVIS_BASE_URL", "AVIS_API_KEY", "AVIS_MODEL") if not env.get(k)
    ]
    if thieu:
        raise SystemExit(
            f"Thiếu cấu hình: {', '.join(thieu)} (biến môi trường hoặc ~/.clinicai-avis.env)"
        )
    return env


def dau_tep(p: Path) -> str:
    du = p.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(du) + du).hexdigest()


def tep_nguon() -> list[str]:
    ra = []
    for goc, duoi in (("src/clinicai", (".py",)), ("src/dashboard", (".ts", ".tsx"))):
        for p in sorted((GOC / goc).rglob("*")):
            if (
                p.suffix in duoi
                and not any(b in p.parts for b in BO)
                and not p.name.endswith((".test.ts", ".test.mts", ".d.ts"))
                and ".generated." not in p.name  # kiểu sinh tự động — không ghi chú
            ):
                ra.append(p.relative_to(GOC).as_posix())
    return ra


def doc_ghi_chu() -> tuple[dict[str, dict], dict[str, Path]]:
    ghi: dict[str, dict] = {}
    cua: dict[str, Path] = {}
    for f in sorted((HIEU / "tep").glob("*.json")):
        for t, g in (
            json.loads(f.read_text(encoding="utf-8")).get("tep") or {}
        ).items():
            ghi[t], cua[t] = g, f
    return ghi, cua


def can_doc_lai(ghi: dict[str, dict], dau: dict[str, str]) -> list[str]:
    ra = []
    for t in tep_nguon():
        p = GOC / t
        if t not in ghi or dau.get(t) != dau_tep(p):
            ra.append(t)
    return ra


DAN_SQL = """Bạn đọc kỹ MỘT hàm / view SQL (Postgres) của ClinicAI — phần mềm phòng
khám; bản ĐANG CHẠY, dòng đầu ghi migration cuối định nghĩa nó và trigger gắn vào.
Trả về DUY NHẤT một object JSON (không markdown) đúng khuôn:
{"lam_gi": "1–2 câu lời thường: làm gì, khi nào chạy",
 "khoi": "<mã khối lego hoặc null>",
 "loai": "logic_nghiep_vu | canh_bat_bien | ha_tang | bao_cao | co_the_chet",
 "chay_khi": "trigger … trên bảng … | Python gọi | không ai gọi",
 "goi_boi": [], "doc_bang": [], "ghi_bang": [],
 "luat": [{"noi_dung": "luật nghiệp vụ thân hàm THỰC THI; tiền/kho kèm ví dụ số"}],
 "bay": [{"noi_dung": "chỗ dễ sai khi sửa: thứ tự trigger, SECURITY DEFINER, khoá, comment nói khác code…"}],
 "muon_sua": [{"viec": "muốn đổi X", "cho": "viết migration MỚI CREATE OR REPLACE — bản đang chạy ở <tệp>:<dòng>"}],
 "chua_chac": []}
Đọc từ THÂN, không suy từ tên. Tiếng Việt lời thường. Không bịa. Mỗi chuỗi ≤ 300 ký tự.
MỌI nhánh IF / ELSIF / CASE / EXCEPTION / RETURN sớm phải có mặt trong luat hoặc bay —
nhất là NGOẠI LỆ cho qua (“chặn X, TRỪ KHI …”): bỏ ngoại lệ là ghi chú nói sai.
Hàm vặt (updated_at, notify) thì lam_gi + loai + chay_khi, mảng rỗng."""
# Lượt soát: đọc lại thân + ghi chú đã có, vá nhánh bị bỏ sót (21/10: lượt đầu
# ghi gac_ban_tu_quay "lô KHO không được giao" mà quên hai ngoại lệ cho qua).
DAN_SOAT = (
    DAN_SQL
    + """
LƯỢT SOÁT: kèm theo là GHI CHÚ ĐÃ CÓ. Đối chiếu từng nhánh của thân với ghi chú;
sửa câu sai, thêm nhánh / ngoại lệ bị bỏ, giữ câu đúng. Trả object ĐẦY ĐỦ cùng khuôn,
thêm khoá "da_sua": ["mô tả ngắn từng chỗ đã sửa"] (rỗng nếu ghi chú đã đúng)."""
)
KHOA_SQL = {
    "lam_gi",
    "khoi",
    "loai",
    "chay_khi",
    "goi_boi",
    "doc_bang",
    "ghi_bang",
    "luat",
    "bay",
    "muon_sua",
    "chua_chac",
}
HAM_MOI = HIEU / "sql" / "ham-moi.json"
DB_JSON = GOC / "docs" / "ban-do" / "db.json"


class HetTienError(Exception):
    """Cổng API từ chối vì hết tiền / hết hạn mức — dừng hẳn, không thử tiếp."""


def than_sql() -> dict[str, str]:
    """{'ham:<tên>' / 'view:<tên>': thân đầy đủ} — từ khuôn test (= mọi migration),
    nhân bản DB tạm, chỉ đọc, xoá ngay (cùng cách scripts/ban-do-db.py)."""
    import subprocess
    import time

    def psql(db: str, lenh: str) -> str:
        r = subprocess.run(
            [
                "docker",
                "exec",
                "-e",
                "PGOPTIONS=--client-min-messages=warning",
                os.environ.get("TEST_NHANH_CONTAINER", "chung_test_db"),
                "psql",
                "-U",
                "postgres",
                "-d",
                db,
                "-v",
                "ON_ERROR_STOP=1",
                "-qtA",
                "-c",
                lenh,
            ],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        if r.returncode:
            raise SystemExit(f"psql lỗi: {r.stderr.strip()}")
        return r.stdout

    sql = """SET default_transaction_read_only = on; SELECT json_build_object(
      'ham', (SELECT json_agg(json_build_object('ten', p.proname, 'than', pg_get_functiondef(p.oid)))
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace JOIN pg_language l ON l.oid = p.prolang
        WHERE n.nspname = 'public' AND l.lanname IN ('plpgsql','sql') AND p.prokind = 'f'),
      'trigger', (SELECT json_agg(json_build_object('bang', c.relname, 'ham', pr.proname, 'than', pg_get_triggerdef(t.oid)))
        FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_proc pr ON pr.oid = t.tgfoid WHERE NOT t.tgisinternal AND n.nspname = 'public'),
      'view', (SELECT json_agg(json_build_object('ten', c.relname, 'than', pg_get_viewdef(c.oid, true)))
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relkind IN ('v','m')))"""
    tam = f"tam_doc_lai_{os.getpid()}"
    for _ in range(10):
        try:
            psql("template1", f'CREATE DATABASE "{tam}" TEMPLATE "khuon"')
            break
        except SystemExit:
            time.sleep(1)
    else:
        raise SystemExit(
            "Không nhân bản được khuôn — container chung_test_db có chạy không?"
        )
    try:
        d = json.loads(psql(tam, sql).strip().splitlines()[-1])
    finally:
        psql("template1", f'DROP DATABASE IF EXISTS "{tam}" WITH (FORCE)')
    noi = {
        h["ten"]: h["dinh_nghia"]
        for h in json.loads(DB_JSON.read_text(encoding="utf-8")).get("ham", [])
    }
    trig: dict[str, list[str]] = {}
    for t in d["trigger"] or []:
        trig.setdefault(t["ham"], []).append(f"{t['bang']}: {t['than']}")
    ra = {}
    for h in d["ham"] or []:
        n = noi.get(h["ten"], {})
        dau = f"-- HÀM {h['ten']} · định nghĩa cuối ở {n.get('tep', '?')}:{n.get('dong', 0)}\n"
        dau += "".join(f"-- GẮN TRIGGER {x}\n" for x in trig.get(h["ten"], []))
        ra[f"ham:{h['ten']}"] = dau + h["than"]
    for v in d["view"] or []:
        ra[f"view:{v['ten']}"] = f"-- VIEW {v['ten']}\n{v['than']}"
    return ra


def main_sql(argv: list[str], toi_da: int, tran: float) -> int:
    """Đọc lại ghi chú hàm / view SQL: chưa có ghi chú, hoặc hàm đã bị migration mới
    định nghĩa lại (dấu 'ham:<tên>' trong dau.json = tệp:dòng migration lúc duyệt)."""
    dau = json.loads(DAU.read_text(encoding="utf-8")) if DAU.exists() else {}
    co: dict[str, Path] = {}
    for f in sorted((HIEU / "sql").glob("ham-*.json")):
        for k in json.loads(f.read_text(encoding="utf-8")).get("muc") or {}:
            co[k] = f
    noi = {
        f"ham:{h['ten']}": f"{h['dinh_nghia']['tep']}:{h['dinh_nghia']['dong']}"
        for h in json.loads(DB_JSON.read_text(encoding="utf-8")).get("ham", [])
    }
    than = than_sql()
    soat = "--soat" in argv
    if soat:
        # Soát lại các mục chỉ định (--tep a,b) hoặc mọi mục máy đã viết (ham-moi.json).
        chi = lay_co(argv, "--tep", "")
        ds = (
            [x for x in chi.split(",") if x in than and x in co]
            if chi
            else sorted(
                k
                for k in json.loads(HAM_MOI.read_text(encoding="utf-8"))["muc"]
                if k in than
            )
        )
        cu = {}
        for f in {co[k] for k in ds}:
            cu.update(json.loads(f.read_text(encoding="utf-8"))["muc"])
    else:
        ds = [
            k
            for k in sorted(than)
            if k not in co or (k in noi and k in dau and dau[k] != noi[k])
        ]
    print(
        f"Hàm / view SQL cần đọc lại: {len(ds)}"
        + (f" (lấy {min(len(ds), toi_da)})" if len(ds) > toi_da else "")
    )
    if "--thu" in argv:
        print("\n".join(f"  {k}" for k in ds[:300]))
        return 0
    import threading
    from concurrent.futures import ThreadPoolExecutor

    env = cau_hinh()
    # Mỗi lượt gọi ~1 phút → chạy song song; ghi tệp tuần tự dưới khoá
    # (nhiều mục chung một ham-SNN.json, ghi đè lẫn nhau là mất ghi chú).
    khoa, dung = threading.Lock(), threading.Event()
    tong, xong, hong = [0.0], [0], []

    def mot(k: str) -> None:
        if dung.is_set():
            return
        try:
            if soat:
                ghi = json.dumps(cu[k], ensure_ascii=False, indent=1)
                g, tien = goi(
                    env, f"Mục: {k}\n\n{than[k]}\n\n-- GHI CHÚ ĐÃ CÓ:\n{ghi}", DAN_SOAT
                )
                sua = g.pop("da_sua", None) or []
                if sua:
                    print(f"  ~ {k}: {' | '.join(map(str, sua))[:400]}", flush=True)
            else:
                g, tien = goi(env, f"Mục: {k}\n\n{than[k]}", DAN_SQL)
        except HetTienError as e:
            dung.set()
            print(
                f"HẾT TIỀN / HẠN MỨC API: {e} — dừng, chuyển phần còn lại cho agent",
                flush=True,
            )
            return
        except (
            urllib.error.URLError,
            json.JSONDecodeError,
            KeyError,
            TimeoutError,
        ) as e:
            with khoa:
                hong.append(k)
            print(f"  ✗ {k}: {type(e).__name__} {getattr(e, 'code', '')}", flush=True)
            return
        loi = [f"khoá lạ {x}" for x in set(g) - KHOA_SQL] + (
            [] if g.get("lam_gi") else ["thiếu lam_gi"]
        )
        with khoa:
            tong[0] += tien
            if tong[0] >= tran and not dung.is_set():
                dung.set()
                print(f"DỪNG: chạm trần {tran} USD", flush=True)
            if loi:
                hong.append(k)
                print(f"  ✗ {k}: {'; '.join(loi[:3])}", flush=True)
                return
            f = co.get(k, HAM_MOI)
            du = (
                json.loads(f.read_text(encoding="utf-8"))
                if f.exists()
                else {"lat": "moi", "muc": {}}
            )
            du["muc"][k] = g
            f.write_text(json.dumps(du, ensure_ascii=False, indent=1), encoding="utf-8")
            if k in noi:
                dau[k] = noi[k]
            DAU.write_text(
                json.dumps(dict(sorted(dau.items())), indent=0), encoding="utf-8"
            )
            xong[0] += 1
        print(f"  ✓ {k}: {len(g.get('luat') or [])} luật ({tien:.4f} USD)", flush=True)

    with ThreadPoolExecutor(int(lay_co(argv, "--song-song", "8"))) as ex:
        list(ex.map(mot, ds[:toi_da]))
    print(f"Xong {xong[0]} · hỏng {len(hong)} · tổng {tong[0]:.4f} USD.", flush=True)
    if hong:
        print("Còn lại: " + " ".join(hong))
    return 1 if hong or dung.is_set() else 0


def lay_co(argv: list[str], co: str, mac_dinh: str) -> str:
    return argv[argv.index(co) + 1] if co in argv else mac_dinh


def goi(env: dict[str, str], noi_dung: str, dan: str = DAN) -> tuple[dict, float]:
    req = urllib.request.Request(
        env["AVIS_BASE_URL"].rstrip("/") + "/chat/completions",
        data=json.dumps(
            {
                "model": env["AVIS_MODEL"],
                "max_tokens": 8000,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": dan},
                    {"role": "user", "content": noi_dung},
                ],
            }
        ).encode(),
        headers={
            "Authorization": f"Bearer {env['AVIS_API_KEY']}",
            "Content-Type": "application/json",
            # Cổng AVIS chặn User-Agent mặc định của Python (đo 18/10/2026).
            "User-Agent": "clinicai-ban-do/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        # 401/402/403/429 = khoá / tiền / hạn mức — thử tiếp chỉ đốt thời gian.
        if e.code in (401, 402, 403, 429):
            raise HetTienError(f"HTTP {e.code}") from None
        raise
    u = d.get("usage") or {}
    tien = float(u.get("cost_usd_input") or 0) + float(u.get("cost_usd_output") or 0)
    van = d["choices"][0]["message"]["content"].strip()
    van = re.sub(r"^```(?:json)?\s*|\s*```$", "", van)
    return json.loads(van), tien


def kiem(g: dict, so_dong: int) -> list[str]:
    loi = [f"khoá lạ {k}" for k in set(g) - KHOA]
    if not g.get("lam_gi"):
        loi.append("thiếu lam_gi")
    for k in ("luat", "bay", "ham_chinh", "comment_cu"):
        for x in g.get(k) or []:
            if not isinstance(x, dict) or not 0 < int(x.get("dong") or 0) <= so_dong:
                loi.append(
                    f"{k} dòng ngoài tệp: {x.get('dong') if isinstance(x, dict) else x}"
                )
    return loi


def main(argv: list[str]) -> int:
    def lay(co: str, md: str) -> str:
        return argv[argv.index(co) + 1] if co in argv else md

    toi_da, tran = int(lay("--toi-da", "20")), float(lay("--tran-usd", "2"))
    if "--sql" in argv:
        return main_sql(argv, toi_da, tran)
    dau = json.loads(DAU.read_text(encoding="utf-8")) if DAU.exists() else {}
    ghi, cua = doc_ghi_chu()
    ds = [lay("--tep", "")] if "--tep" in argv else can_doc_lai(ghi, dau)
    print(
        f"Cần đọc lại: {len(ds)} tệp"
        + (f" (lấy {min(len(ds), toi_da)})" if len(ds) > toi_da else "")
    )
    if "--thu" in argv:
        print("\n".join(f"  {t}" for t in ds[:200]))
        return 0
    env = cau_hinh()
    tong, xong, hong = 0.0, [], []
    for t in ds[:toi_da]:
        if tong >= tran:
            print(f"DỪNG: chạm trần {tran} USD")
            break
        p = GOC / t
        dong = p.read_text(encoding="utf-8").splitlines()
        than = "\n".join(f"{i}: {s}" for i, s in enumerate(dong, 1))
        try:
            g, tien = goi(env, f"Tệp: {t}\n\n{than}")
        except HetTienError as e:
            print(f"HẾT TIỀN / HẠN MỨC API: {e} — dừng, chuyển phần còn lại cho agent")
            break
        except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
            hong.append(t)
            print(f"  ✗ {t}: {type(e).__name__}")
            continue
        tong += tien
        loi = kiem(g, len(dong))
        if loi:
            hong.append(t)
            print(f"  ✗ {t}: {'; '.join(loi[:3])} ({tien:.4f} USD)")
            continue
        f = cua.get(t, TEP_MOI)
        du = (
            json.loads(f.read_text(encoding="utf-8"))
            if f.exists()
            else {"lat": "moi", "tep": {}}
        )
        du["tep"][t] = g
        f.write_text(json.dumps(du, ensure_ascii=False, indent=1), encoding="utf-8")
        dau[t] = dau_tep(p)
        xong.append(t)
        print(f"  ✓ {t}: {len(g.get('luat') or [])} luật ({tien:.4f} USD)")
    DAU.write_text(json.dumps(dict(sorted(dau.items())), indent=0), encoding="utf-8")
    print(
        f"Xong {len(xong)} · hỏng {len(hong)} · tổng {tong:.4f} USD. Chạy python3 scripts/ban-do-code.py rồi duyệt diff."
    )
    return 1 if hong else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
