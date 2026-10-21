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
    python3 scripts/ban-do-doc-lai.py --sql [--soat]         # hàm / view SQL
    python3 scripts/ban-do-doc-lai.py --soat --toi-da 2000 --tran-usd 80 --song-song 8
        # lượt hai cho ghi chú tệp code: vá chỗ sai / sót; chạy lại thì đi tiếp

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


DAN_SOAT_TEP = (
    DAN
    + """

LƯỢT SOÁT: kèm theo là GHI CHÚ ĐÃ CÓ của tệp. Đối chiếu từng luật / bẫy / hàm chính
với code: số dòng có trỏ đúng dòng thực thi không, câu có nói đúng điều code làm không,
có bỏ sót NHÁNH (if / else / except / return sớm) hay NGOẠI LỆ cho qua không. Sửa câu
sai, thêm cái bị bỏ, giữ nguyên câu đúng."""
    + "\n"
    + "{tra_ve}"
)
# Chỉ trả khoá ĐỔI: tệp ~1.300 dòng trả cả ghi chú thì cổng AVIS cắt 504 (đo
# 22/10, bill_service.py ba lần liền); stream của cổng trả content null.
TRA_VE_DOI = """TRẢ VỀ: DUY NHẤT một object JSON (không markdown) CHỈ GỒM các khoá cần đổi,
mỗi khoá mang GIÁ TRỊ MỚI ĐẦY ĐỦ (cả mảng, không chỉ phần thêm); khoá đúng sẵn thì BỎ.
Luôn có khoá "da_sua": ["mô tả ngắn từng chỗ đã sửa"]. Ghi chú đã đúng → {"da_sua": []}."""
DAN_SOAT_TEP = DAN_SOAT_TEP.replace("{tra_ve}", TRA_VE_DOI)
#: Script vận hành / tệp test: khuôn ghi chú KHÁC tệp code (script có chay_o,
#: ghi_prod, nguy_hiem; test có canh, yeu) — giữ đúng khoá của ghi chú cũ.
DAN_SOAT_CHUNG = (
    """Bạn SOÁT LẠI ghi chú về MỘT tệp của ClinicAI (phần mềm phòng khám: FastAPI,
Next.js, Postgres; script vận hành chạy trên Mac dev hoặc VPS; tệp test pytest / node).
Kèm theo là nội dung tệp (số dòng ở đầu mỗi dòng) và GHI CHÚ ĐÃ CÓ (JSON). Đối chiếu
từng mục với tệp: số dòng trỏ đúng dòng thực thi, câu nói đúng điều tệp làm (script:
chạy ở đâu, có GHI prod không, chạy sai thì hỏng gì; test: luật nào được canh thật,
test nào hời hợt — chỉ kiểm có chạy chứ không kiểm kết quả). Sửa câu sai, thêm cái bị
bỏ, giữ câu đúng. Chỉ dùng các khoá của ghi chú cũ. Tiếng Việt lời thường, mỗi
chuỗi ≤ 300 ký tự, không bịa.
"""
    + TRA_VE_DOI
)
SOAT_TEP = HIEU / "soat-tep.json"
#: Soát trước: khối giữ tiền / kho / quyền — sai ở đây là sai tiền.
UU_TIEN = {
    "payment",
    "pharmacy",
    "kho_vat_tu",
    "ke_toan",
    "permission",
    "cong_no",
    "billing",
    "lieu_trinh",
}


def main_soat_tep(argv: list[str], toi_da: int, tran: float) -> int:
    """Lượt hai cho ghi chú tệp code: model đọc lại tệp + ghi chú cũ, vá chỗ sai /
    sót. Ghi dấu từng tệp đã soát vào soat-tep.json — chạy lại thì đi tiếp."""
    import threading
    from concurrent.futures import ThreadPoolExecutor

    dau = json.loads(DAU.read_text(encoding="utf-8")) if DAU.exists() else {}
    soat = json.loads(SOAT_TEP.read_text(encoding="utf-8")) if SOAT_TEP.exists() else {}
    # Mọi ghi chú tệp: code + script vận hành (tep/) và test (test/).
    ghi: dict[str, dict] = {}
    cua: dict[str, Path] = {}
    for thu_muc in ("tep", "test"):
        for f in sorted((HIEU / thu_muc).glob("*.json")):
            for t, g in (
                json.loads(f.read_text(encoding="utf-8")).get("tep") or {}
            ).items():
                ghi[t], cua[t] = g, f
    code = set(tep_nguon())
    chi = lay_co(argv, "--tep", "")
    ds = [
        t
        for t in (chi.split(",") if chi else sorted(ghi))
        if t in ghi and (GOC / t).is_file()
    ]
    ds = [t for t in ds if soat.get(t) != dau_tep(GOC / t)]
    # Thứ tự: code khối tiền/kho/quyền → code còn lại → script vận hành → test.
    ds.sort(
        key=lambda t: (
            0
            if t in code and ghi[t].get("khoi") in UU_TIEN
            else 1
            if t in code
            else 2
            if not t.startswith("src/tests")
            else 3,
            t,
        )
    )
    print(
        f"Tệp cần soát: {len(ds)}"
        + (f" (lấy {min(len(ds), toi_da)})" if len(ds) > toi_da else "")
    )
    if "--thu" in argv:
        print("\n".join(f"  {t}" for t in ds[:200]))
        return 0
    env = cau_hinh()
    khoa, dung = threading.Lock(), threading.Event()
    tong, xong, hong = [0.0], [0], []

    def mot(t: str) -> None:
        if dung.is_set():
            return
        p = GOC / t
        dong = p.read_text(encoding="utf-8").splitlines()
        than = "\n".join(f"{i}: {s}" for i, s in enumerate(dong, 1))
        cu = json.dumps(ghi[t], ensure_ascii=False, indent=1)
        la_code = t in code
        try:
            g, tien = goi(
                env,
                f"Tệp: {t}\n\n{than}\n\n// GHI CHÚ ĐÃ CÓ:\n{cu}",
                DAN_SOAT_TEP if la_code else DAN_SOAT_CHUNG,
                max_tokens=16000,
            )
        except HetTienError as e:
            dung.set()
            print(f"HẾT TIỀN / HẠN MỨC API: {e} — dừng", flush=True)
            return
        except (
            urllib.error.URLError,
            json.JSONDecodeError,
            KeyError,
            TimeoutError,
        ) as e:
            with khoa:
                hong.append(t)
            print(f"  ✗ {t}: {type(e).__name__} {getattr(e, 'code', '')}", flush=True)
            return
        sua = g.pop("da_sua", None) or []
        g = {**ghi[t], **g}  # model chỉ trả khoá đổi — gộp vào ghi chú cũ
        # Test: model đôi khi trả `yeu` / `canh` là câu chữ — bản đồ cần {noi_dung}.
        for k in ("yeu", "canh"):
            if isinstance(g.get(k), list):
                g[k] = [{"noi_dung": x} if isinstance(x, str) else x for x in g[k]]
        loi = kiem(g, len(dong), KHOA | set(ghi[t]))
        with khoa:
            tong[0] += tien
            if tong[0] >= tran and not dung.is_set():
                dung.set()
                print(f"DỪNG: chạm trần {tran} USD", flush=True)
            if loi:
                hong.append(t)
                print(f"  ✗ {t}: {'; '.join(loi[:3])}", flush=True)
                return
            f = cua[t]
            du = json.loads(f.read_text(encoding="utf-8"))
            du["tep"][t] = g
            f.write_text(json.dumps(du, ensure_ascii=False, indent=1), encoding="utf-8")
            soat[t] = dau_tep(p)
            if t in dau or la_code:
                dau[t] = soat[t]
            SOAT_TEP.write_text(
                json.dumps(dict(sorted(soat.items())), indent=0), encoding="utf-8"
            )
            DAU.write_text(
                json.dumps(dict(sorted(dau.items())), indent=0), encoding="utf-8"
            )
            xong[0] += 1
        nhan = " | ".join(map(str, sua))[:300] if sua else "đúng sẵn"
        print(f"  ~ {t} ({tien:.3f} USD): {nhan}", flush=True)

    with ThreadPoolExecutor(int(lay_co(argv, "--song-song", "8"))) as ex:
        list(ex.map(mot, ds[:toi_da]))
    print(f"Xong {xong[0]} · hỏng {len(hong)} · tổng {tong[0]:.4f} USD.", flush=True)
    if hong:
        print("Còn lại: " + ",".join(hong))
    return 1 if hong or dung.is_set() else 0


#: DỰ PHÒNG khi AVIS cạn tiền / hạn mức: API Claude chính hãng. Tuyền điền khoá vào
#: ~/.clinicai-claude.env (NGOÀI repo, chmod 600); khoá trống = không có dự phòng.
CLAUDE_ENV = Path.home() / ".clinicai-claude.env"
#: USD / 1 triệu token (vào, ra) — bảng giá API Claude 10/2026.
GIA_CLAUDE = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.1, 0.5),
}
_NHA = {"claude": False}  # True = AVIS đã cạn, mọi lượt sau đi thẳng Claude


def cau_hinh_claude() -> dict[str, str] | None:
    """Khoá Claude: ~/.clinicai-claude.env, hoặc `.env.claude.local` ở repo / checkout
    chính (Tuyền đặt ở đó 22/10 — gitignore `.env.*`). Không bao giờ in khoá."""
    env: dict[str, str] = {}
    tep = [CLAUDE_ENV] + [d / ".env.claude.local" for d in (GOC, *GOC.parents)]
    for f in tep:
        if not f.is_file():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                v = v.strip().strip('"').strip("'")
                if v and not env.get(k.strip()):
                    env[k.strip()] = v
    return env if env.get("ANTHROPIC_API_KEY") else None


def goi_claude(cfg: dict[str, str], noi_dung: str, dan: str) -> tuple[str, float]:
    """Một lượt qua API Claude (SDK chính hãng). Stream để câu trả lời dài không
    vướng giới hạn thời gian HTTP; max_tokens rộng vì suy nghĩ cũng tính vào."""
    import anthropic

    model = cfg.get("CLAUDE_MODEL") or "claude-opus-5-5"
    client = anthropic.Anthropic(api_key=cfg["ANTHROPIC_API_KEY"], max_retries=3)
    # Bị từ chối nhầm vì an toàn → API tự chạy lại trên model dự phòng. SDK trên máy
    # (0.111) chỉ nhận dạng mảng; Sonnet 5.5 không nhận dạng mảng → bỏ qua.
    du_phong: dict = (
        {
            "betas": ["server-side-fallback-2026-06-01"],
            "fallbacks": [{"model": "claude-opus-4-8"}],
        }
        if model.startswith("claude-opus")
        else {}
    )
    try:
        with client.beta.messages.stream(
            model=model,
            max_tokens=64000,
            system=dan,
            messages=[{"role": "user", "content": noi_dung}],
            # Đối chiếu ghi chú với code: không cần suy nghĩ sâu nhất — `medium`
            # giữ chất lượng, bớt token suy nghĩ (tính tiền như token ra).
            output_config={"effort": "medium"},
            **du_phong,
        ) as s:
            m = s.get_final_message()
    except (
        anthropic.AuthenticationError,
        anthropic.PermissionDeniedError,
        anthropic.RateLimitError,
    ) as e:
        raise HetTienError(f"Claude {type(e).__name__}") from None
    except anthropic.BadRequestError as e:
        if "credit" in str(e).lower() or "billing" in str(e).lower():
            raise HetTienError("Claude hết credit") from None
        raise urllib.error.URLError(f"Claude {e}") from None
    except anthropic.APIError as e:
        raise urllib.error.URLError(f"Claude {type(e).__name__}") from None
    if m.stop_reason == "refusal":
        raise urllib.error.URLError("Claude từ chối")
    vao, ra = GIA_CLAUDE.get(model, GIA_CLAUDE["claude-opus-5-5"])
    tien = (m.usage.input_tokens * vao + m.usage.output_tokens * ra) / 1e6
    return "".join(b.text for b in m.content if b.type == "text"), tien


def doc_json(van: str) -> dict:
    van = re.sub(r"^```(?:json)?\s*|\s*```$", "", van.strip())
    # Lời dẫn / lời kết quanh object (lượt soát 22/10 gặp JSONDecodeError) → cắt.
    if not van.startswith("{") and "{" in van:
        van = van[van.index("{") : van.rindex("}") + 1]
    return json.loads(van)


def goi(
    env: dict[str, str], noi_dung: str, dan: str = DAN, *, max_tokens: int = 8000
) -> tuple[dict, float]:
    """AVIS trước; AVIS cạn (401/402/403/429) mà có khoá Claude → chuyển hẳn sang
    Claude cho mọi lượt còn lại."""
    if not _NHA["claude"]:
        try:
            return goi_avis(env, noi_dung, dan, max_tokens=max_tokens)
        except urllib.error.HTTPError as e:
            # Cổng AVIS cắt 504 với tệp to dù đã thử lại — riêng lượt này qua Claude.
            cfg = cau_hinh_claude()
            if e.code < 500 or cfg is None:
                raise
            van, tien = goi_claude(cfg, noi_dung, dan)
            return doc_json(van), tien
        except HetTienError:
            if cau_hinh_claude() is None:
                raise
            if not _NHA["claude"]:
                _NHA["claude"] = True
                print("AVIS CẠN — chuyển sang API Claude dự phòng", flush=True)
    cfg = cau_hinh_claude()
    if cfg is None:
        raise HetTienError("không có khoá Claude dự phòng")
    van, tien = goi_claude(cfg, noi_dung, dan)
    return doc_json(van), tien


def goi_avis(
    env: dict[str, str], noi_dung: str, dan: str = DAN, *, max_tokens: int = 8000
) -> tuple[dict, float]:
    req = urllib.request.Request(
        env["AVIS_BASE_URL"].rstrip("/") + "/chat/completions",
        data=json.dumps(
            {
                "model": env["AVIS_MODEL"],
                "max_tokens": max_tokens,
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
    import time

    for lan in range(6):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            # 401/402/403 = khoá / tiền — thử tiếp chỉ đốt thời gian.
            if e.code in (401, 402, 403):
                raise HetTienError(f"HTTP {e.code}") from None
            if e.code == 429:
                # 429 có hai nghĩa: HẾT TIỀN / hạn mức (dừng hẳn) hay chỉ gọi DỒN
                # quá nhanh (22/10: 8 luồng, tệp thứ 52) — đợi rồi thử lại.
                than = e.read().decode("utf-8", "replace").lower()
                if any(
                    # AVIS 22/10: "API key monthly spend limit reached".
                    x in than
                    for x in ("quota", "credit", "balance", "insufficient", "limit")
                ):
                    raise HetTienError(f"HTTP 429 {than[:80]}") from None
                if lan == 5:
                    raise HetTienError("HTTP 429 lặp 6 lần") from None
                time.sleep(int(e.headers.get("retry-after") or 0) or 15 * (lan + 1))
                continue
            if lan >= 2:
                raise
            # 5xx của cổng (504 khi tệp to trả lời lâu) — thử lại tối đa 2 lần.
            if e.code < 500 or lan == 2:
                raise
    u = d.get("usage") or {}
    tien = float(u.get("cost_usd_input") or 0) + float(u.get("cost_usd_output") or 0)
    return doc_json(d["choices"][0]["message"]["content"]), tien


def kiem(g: dict, so_dong: int, khoa: set[str] = KHOA) -> list[str]:
    loi = [f"khoá lạ {k}" for k in set(g) - khoa]
    if not g.get("lam_gi"):
        loi.append("thiếu lam_gi")
    # canh / yeu: mục của ghi chú tệp test — cũng trỏ số dòng.
    for k in ("luat", "bay", "ham_chinh", "comment_cu", "canh", "yeu"):
        for x in g.get(k) or []:
            # Ghi chú test: `yeu` có thể là câu chữ không kèm số dòng.
            if k in ("canh", "yeu") and not (isinstance(x, dict) and "dong" in x):
                continue
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
    if "--claude" in argv:  # AVIS đang cạn — đi thẳng API Claude dự phòng
        _NHA["claude"] = True
    if "--soat" in argv:
        return main_soat_tep(argv, toi_da, tran)
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
