# -*- coding: utf-8 -*-
"""Sinh bản đọc (HTML một tệp, chạy ngoại tuyến) + vault Obsidian từ MỘT nguồn nút.

Bố cục đọc-trước: cột chương bên trái · cột đọc rộng ở giữa · ngăn bằng chứng trượt
ra bên phải khi bấm một tên file. Markdown dựng sẵn ở Python nên trang không phụ
thuộc thư viện nào để hiện chữ; d3 chỉ dùng cho trang "bản đồ đầy đủ".
"""
from __future__ import annotations

import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import evidence  # noqa: E402
import render as R  # noqa: E402
import nodes_1_hienphap, nodes_2_kientruc, nodes_3_code, nodes_4_khoangcach, nodes_5_thietke, nodes_6_lotrinh  # noqa: E402

LAYERS = {
    1: {"key": "hien-phap",   "so": "01", "ten": "Hiến pháp sản phẩm",
        "phu": "Chín tài liệu Quang viết 03/09 — ontology, nguyên tắc, wedge, điều kiện dừng.",
        "mau": "#6C5FD0", "mau_d": "#9B8FEB"},
    2: {"key": "kien-truc",   "so": "02", "ten": "Kiến trúc hướng sự kiện",
        "phu": "Care Model · Event Catalog · Work Item Protocol · Experience State — hiến pháp kỹ thuật.",
        "mau": "#2F7FE8", "mau_d": "#6FA8FF"},
    3: {"key": "code",        "so": "03", "ten": "Code đang chạy",
        "phu": "Đọc mã tại main sau #163 và đo trực tiếp trên máy chủ 04–05/09/2026.",
        "mau": "#22935F", "mau_d": "#4FC488"},
    4: {"key": "khoang-cach", "so": "04", "ten": "Khoảng cách",
        "phu": "Từng khái niệm đối chiếu: có · một phần · chưa — kèm hệ quả người dùng gặp.",
        "mau": "#C98420", "mau_d": "#EDB84E"},
    5: {"key": "thiet-ke",    "so": "05", "ten": "Thiết kế đích",
        "phu": "Lược đồ, hàm, ràng buộc CI cho từng mảnh. Không hạ tầng mới.",
        "mau": "#0C7D71", "mau_d": "#3FD0BB"},
    6: {"key": "lo-trinh",    "so": "06", "ten": "Lộ trình & quyết định",
        "phu": "Bốn đợt có cổng đo, 12 bằng chứng phải xanh, 8 câu hỏi chờ Quang chốt.",
        "mau": "#C7476E", "mau_d": "#EE7E9C"},
}
STATUS = {"co": "Đã có", "mot-phan": "Một phần", "chua": "Chưa có"}

# ── Bản đồ tổng: 14 khái niệm, toạ độ đặt tay để đọc được, không phải hairball ──
MAP_NODES = [
    {"id": "reality",  "ten": "Sự thật",        "phu": "điều vừa xảy ra",        "x": 50,  "y": 92,  "to": "vong-lap",            "tt": "mot-phan"},
    {"id": "event",    "ten": "Sổ sự kiện",     "phu": "bằng chứng bất biến",    "x": 250, "y": 60,  "to": "event-log-table",     "tt": "mot-phan"},
    {"id": "state",    "ten": "Trạng thái",     "phu": "dựng lại từ sự kiện",    "x": 450, "y": 92,  "to": "state-la-projection", "tt": "mot-phan"},
    {"id": "policy",   "ten": "Luật phản ứng",  "phu": "điều gì phải xảy ra",    "x": 620, "y": 190, "to": "policy-engine",       "tt": "mot-phan"},
    {"id": "work",     "ten": "Đầu việc",       "phu": "ai chịu trách nhiệm",    "x": 620, "y": 320, "to": "work-item-commitment","tt": "mot-phan"},
    {"id": "action",   "ten": "Hành động",      "phu": "người làm thật",         "x": 450, "y": 415, "to": "product-surface",     "tt": "co"},
    {"id": "outcome",  "ten": "Kết quả",        "phu": "vòng mới khép lại",      "x": 250, "y": 448, "to": "bat-dang-thuc",       "tt": "chua"},
    {"id": "timer",    "ten": "Đồng hồ",        "phu": "điều đáng lẽ đã xảy ra", "x": 800, "y": 255, "to": "timer-expected-event","tt": "chua"},
    {"id": "comm",     "ten": "Truyền đạt",     "phu": "gửi ≠ đã hiểu",          "x": 250, "y": 320, "to": "gap-communication",   "tt": "mot-phan"},
    {"id": "exp",      "ten": "Trải nghiệm",    "phu": "chờ có được giải thích", "x": 60,  "y": 255, "to": "experience-state",    "tt": "chua"},
    {"id": "auth",     "ten": "Quyền & tenant", "phu": "ai được thấy, được làm", "x": 800, "y": 92,  "to": "multi-tenant-rls",    "tt": "co"},
    {"id": "res",      "ten": "Phòng & ca",     "phu": "năng lực phục vụ",       "x": 800, "y": 415, "to": "dispatch",            "tt": "mot-phan"},
    {"id": "rel",      "ten": "Độ tin cậy",     "phu": "hỏng phải nhìn thấy",    "x": 450, "y": 255, "to": "reliability",         "tt": "mot-phan"},
    {"id": "ai",       "ten": "AI",             "phu": "diễn giải, không quyết",  "x": 60,  "y": 415, "to": "3-muc-quyen-ai",      "tt": "mot-phan"},
]
MAP_EDGES = [("reality", "event", 1), ("event", "state", 1), ("state", "policy", 1),
             ("policy", "work", 1), ("work", "action", 1), ("action", "outcome", 1),
             ("outcome", "reality", 1),
             ("policy", "timer", 0), ("timer", "work", 0), ("work", "comm", 0),
             ("comm", "outcome", 0), ("comm", "exp", 0), ("exp", "policy", 0),
             ("auth", "event", 0), ("res", "policy", 0), ("rel", "event", 0),
             ("ai", "state", 0), ("event", "rel", 0)]

PHAT_HIEN = [
    ("Sổ sự kiện có đúng hình nhưng chưa ai điền phần hình ấy",
     "`event_log` đã append-only, đã có cột `correlation_id`/`causation_id`. Đo trên máy chủ: **0/449 dòng** từng điền hai cột ấy, **62% là `slot_hold`** (giữ chỗ khung giờ, telemetry chứ không phải mốc chăm sóc), và **29 chỗ** trong code tự viết câu INSERT, không đi qua một cửa chung. Sổ này *đang được đọc thật* ở màn Lịch sử thao tác — thiếu là nghĩa và envelope, không phải thiếu người dùng.",
     "gap-envelope"),
    ("Kernel quy trình chạy được, số đo lịch sử cho thấy dùng rất ít",
     "Gate FS/SS/FF/SF nằm trong SQL, Command API có khoá phiên bản, 41 node là dữ liệu. Số đo 04–05/09 *(chưa đo lại)*: **7 đầu việc, từ đúng 1 lượt khám**, và `work_item_event` khi ấy chỉ chứa lệnh `create`, chưa có lệnh bắt đầu hay hoàn tất nào.",
     "workflow-kernel"),
    ("Thesis và Sổ luật không mâu thuẫn về hạ tầng",
     "Care Model §23 đòi đúng thứ ADR-0001/0005 và Luật 7.1 đã chốt: một khối, một Postgres, outbox, không broker. Chỗ lệch là **nghĩa của dữ liệu**, không phải hạ tầng — nên thiết kế đích không thêm máy móc nào.",
     "kien-truc-toi-thieu"),
    ("Thiếu bộ hẹn giờ nghiệp vụ, nên \"chưa xảy ra\" là vô hình",
     "Tiến trình nền **có** vòng lặp định kỳ — relay quét `event_log` mỗi 30 giây (`worker.py`), POS mỗi 60 giây. Cái thiếu là hẹn giờ cho **hạn nghiệp vụ**: mọi thứ quá hạn hôm nay được tính **lúc mở màn hình**, không ai mở thì không ai biết; code tự khai điều này ở hai chỗ. Đây là mảnh chặn cả ownership lẫn trải nghiệm.",
     "gap-timer"),
    ("Số đo cho biết ai tạo lịch, chưa cho biết wedge nằm ở đâu",
     "Thesis chọn điểm cắm là điều phối **trong** buổi khám. Số đo cho biết **ai tạo lịch**: 65 lịch, 100% do 5 tài khoản CSKH đặt, 0 lịch kênh walk-in tại thời điểm đo, `visit_route` 0 dòng. Nó *không* cho biết chặng nào tạo ra giá trị — chính dịch vụ CSKH cũng phủ mốc trong buổi khám và trả kết quả sau khám. Kiến trúc trung lập với cả hai; chọn đo cái nào trước là quyết định sản phẩm của Quang.",
     "gap-wedge-mismatch"),
]

READING_PATHS = [
    {"id": "nguoi-moi", "ten": "Hiểu toàn cảnh", "mo_ta": "Mười tám nút, đi từ North Star tới lộ trình.",
     "nodes": ["north-star", "vong-lap", "ontology-9", "event-first-dao-nhan-qua", "event-envelope", "work-item-commitment",
               "stack", "event-log-table", "workflow-kernel", "cskh-views", "gap-crud-roi-log", "gap-work-item", "gap-timer",
               "tk-nguyen-tac", "tk-emit-function", "tk-work-item-protocol", "tk-expectation-timer", "lo-trinh-tong"]},
    {"id": "debate", "ten": "Debate với sếp", "mo_ta": "Điều khoản quyết định và chỗ code lệch tài liệu.",
     "nodes": ["north-star", "wedge", "kill-criteria", "7-tieu-chi-event-source", "humane-ops", "4-tang-truong-thanh",
               "15-invariant", "anti-patterns", "gap-wedge-mismatch", "gap-envelope", "gap-work-item", "tk-nguyen-tac",
               "lo-trinh-tong", "cau-hoi-mo"]},
    {"id": "phase-0", "ten": "Bắt tay đợt 0", "mo_ta": "Đúng những nút cần mở khi viết migration đầu tiên.",
     "nodes": ["tk-nguyen-tac", "event-log-table", "audit-labels", "so-cai-phan-manh", "tk-event-envelope-v2",
               "tk-event-catalog-table", "tk-emit-function", "tk-mot-so-cai", "tk-projections", "phase-0-nen",
               "chung-minh-event-driven", "ci-guards"]},
]

SOURCES_DOC = [
    ("Thesis v1", "The Operational Nervous System for Healthcare"),
    ("Thesis v2", "Why It Deserves to Exist"),
    ("Thesis v3", "Care Capacity Infrastructure for the AI Era"),
    ("Care Model v1", "Reality as a Stream of Events"),
    ("Event Catalog v1", "Canonical Language of Care Operations"),
    ("Experience State Spec v1", "Trạng thái trải nghiệm có bằng chứng"),
    ("Work Item Protocol v1", "From Signal to Accountable Outcome"),
    ("Patient Journey v1", "Một hành trình khám được nhìn thấy và phối hợp"),
    ("Partner Pilot Proposal v1", "Proving a Closed-Loop Patient Journey"),
]
SOURCES_REPO = [
    "`docs/SO-LUAT.md` — sổ luật, 12 phần, đọc trọn",
    "`docs/TAM-NHIN.md` — thang lv1→lv5 Quang chốt 24/08",
    "`docs/GIAI-THICH-CODE.md` — 8.316 dòng giải thích code, đọc phần 0 và 9",
    "`docs/kien-truc-nhieu-phong-kham.md` — bốn tầng cấu hình",
    "13 ADR trong `docs/adr/` — đọc trọn, kể cả mục trạng thái thi hành",
    "`docs/design/clinicai-system-design-v5.md` — bản thiết kế 18/07 (đã lỗi thời phần hạ tầng)",
    "119 migration trong `supabase/migrations/` — đọc các tệp kernel, dispatch, CSKH, notify",
    "212 tệp Python backend · 326 tệp TS/TSX dashboard — đọc theo đường nghiệp vụ",
]
DO_TREN_MAY = [
    ("event_log", "449 dòng · 17 loại · 62% là slot_hold · correlation 0/449 · recorded_at = occurred_at ở 100% (do cả hai cột mặc định now(), không phải do không có độ trễ)"),
    ("work_item", "7 dòng từ 1 lượt khám · work_item_event chỉ có lệnh create"),
    ("node_definition / node_dependency", "41 node · 18 cạnh FS · seed idempotent theo tenant"),
    ("Bảng luật là dữ liệu", "luat_cskh 11 · doctor_booking_override 6 · luat_bac_si_bat_buoc 2 · dispatch_threshold 1 · visit_gate_rule 0 · route_template 3"),
    ("Lượt khám và lịch hẹn", "66 lịch hẹn · 67 hồ sơ · 1 visit · 0 lab_result · 0 payment"),
    ("Việc CSKH", "nhac_tai_kham 33 · tuong_tac_cskh 16 · thong_bao 2 · follow_up_case 0 · staff_task 0"),
    ("Lược đồ", "79 bảng public · 9 view · 45 policy select · tenant-audit ceiling 0"),
]

WL = re.compile(r"\[\[([a-z0-9\-]+)\]\]")


# ────────────────────────────────────────────────────────── nạp & kiểm

def load_nodes() -> list[dict]:
    nodes: list[dict] = []
    for mod in (nodes_1_hienphap, nodes_2_kientruc, nodes_3_code,
                nodes_4_khoangcach, nodes_5_thietke, nodes_6_lotrinh):
        nodes.extend(mod.NODES)
    ids = [n["id"] for n in nodes]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise SystemExit(f"id trùng: {dup}")
    known = set(ids)
    errs = []
    for n in nodes:
        n["body"] = n["body"].strip()
        for t in n.get("links", []):
            if t not in known:
                errs.append(f"{n['id']} links → {t}")
        for t in WL.findall(n["body"]):
            if t not in known:
                errs.append(f"{n['id']} body [[{t}]]")
            elif t not in n.get("links", []):
                n.setdefault("links", []).append(t)
        n["links"] = [t for t in dict.fromkeys(n["links"]) if t != n["id"]]
    for p in READING_PATHS:
        errs += [f"lộ trình {p['id']} → {t}" for t in p["nodes"] if t not in known]
    errs += [f"bản đồ tổng → {m['to']}" for m in MAP_NODES if m["to"] not in known]
    errs += [f"phát hiện → {p[2]}" for p in PHAT_HIEN if p[2] not in known]
    if errs:
        raise SystemExit("Liên kết hỏng:\n  " + "\n  ".join(errs))
    back = defaultdict(list)
    for n in nodes:
        for t in n["links"]:
            back[t].append(n["id"])
    for n in nodes:
        n["backlinks"] = back.get(n["id"], [])
    nodes.sort(key=lambda n: (n["layer"], n["order"]))
    return nodes


# ────────────────────────────────────────────────────────── HTML

def esc(s: str) -> str:
    return html.escape(str(s), quote=False)


def esca(s: str) -> str:
    return html.escape(str(s), quote=True)


CSS = r"""
:root{
  --paper:#F5F7F6; --card:#FFFFFF; --sink:#ECF1EF; --ink:#131A19; --muted:#56655F;
  --hair:#DCE4E1; --hair2:#C6D2CE; --accent:#0C7D71; --accent-soft:#E2F1EE; --on-accent:#FFFFFF;
  --ok:#2E9A62; --warn:#B8781B; --bad:#C0453D;
  --l1:#6C5FD0; --l2:#2F7FE8; --l3:#22935F; --l4:#C98420; --l5:#0C7D71; --l6:#C7476E;
  --code-bg:#F0F4F2; --code-ink:#1E2A28; --drawer:#FFFFFF;
  --shadow-1:0 1px 2px rgba(17,32,29,.06); --shadow-2:0 24px 60px rgba(17,32,29,.16);
  --edge:#C0CDC9; --edge-hi:#0C7D71;
  --serif:'Newsreader',Georgia,'Times New Roman',serif;
  --sans:'IBM Plex Sans','Segoe UI',system-ui,-apple-system,sans-serif;
  --mono:'IBM Plex Mono',Menlo,Consolas,monospace;
  color-scheme:light;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --paper:#0D1211; --card:#141B19; --sink:#1A2321; --ink:#E8EEEB; --muted:#93A49E;
    --hair:#233029; --hair2:#31413B; --accent:#3FD0BB; --accent-soft:#132A27; --on-accent:#08110F;
    --ok:#4FC488; --warn:#E4AC48; --bad:#E1706A;
    --l1:#9B8FEB; --l2:#6FA8FF; --l3:#4FC488; --l4:#EDB84E; --l5:#3FD0BB; --l6:#EE7E9C;
    --code-bg:#101816; --code-ink:#D6E2DE; --drawer:#141B19;
    --shadow-1:0 1px 2px rgba(0,0,0,.4); --shadow-2:0 24px 60px rgba(0,0,0,.55);
    --edge:#2C3A36; --edge-hi:#3FD0BB;
    color-scheme:dark;
  }
}
:root[data-theme="dark"]{
  --paper:#0D1211; --card:#141B19; --sink:#1A2321; --ink:#E8EEEB; --muted:#93A49E;
  --hair:#233029; --hair2:#31413B; --accent:#3FD0BB; --accent-soft:#132A27; --on-accent:#08110F;
  --ok:#4FC488; --warn:#E4AC48; --bad:#E1706A;
  --l1:#9B8FEB; --l2:#6FA8FF; --l3:#4FC488; --l4:#EDB84E; --l5:#3FD0BB; --l6:#EE7E9C;
  --code-bg:#101816; --code-ink:#D6E2DE; --drawer:#141B19;
  --shadow-1:0 1px 2px rgba(0,0,0,.4); --shadow-2:0 24px 60px rgba(0,0,0,.55);
  --edge:#2C3A36; --edge-hi:#3FD0BB;
  color-scheme:dark;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important;animation:none!important}}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-underline-offset:2px}
button{font:inherit;color:inherit;cursor:pointer}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.skip{position:absolute;left:-999px;top:8px;background:var(--card);padding:8px 12px;border:1px solid var(--hair);border-radius:6px;z-index:60}
.skip:focus{left:8px}

/* ── khung ── */
.shell{display:grid;grid-template-columns:290px 1fr;min-height:100vh}
.side{position:sticky;top:0;height:100vh;overflow:auto;background:var(--card);border-right:1px solid var(--hair);padding:20px 16px 28px;display:flex;flex-direction:column;gap:20px}
.brand{display:flex;gap:11px;align-items:flex-start}
.brand .mark{width:30px;height:30px;flex:none;border-radius:8px;background:var(--accent);color:var(--on-accent);display:grid;place-items:center;font-family:var(--serif);font-size:17px;font-weight:600}
.brand b{display:block;font-family:var(--serif);font-size:17px;font-weight:600;line-height:1.15;letter-spacing:-.01em}
.brand span{display:block;font-size:10.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted);margin-top:3px}
.q{width:100%;padding:9px 11px;border:1px solid var(--hair2);border-radius:8px;background:var(--paper);color:var(--ink);font:inherit;font-size:13.5px}
.q::placeholder{color:var(--muted)}
.q:focus{border-color:var(--accent);outline:none}
.side h3{font-size:10.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted);margin:0 0 8px;font-weight:600}
.nav{display:flex;flex-direction:column;gap:1px}
.nav button{display:flex;gap:11px;align-items:baseline;width:100%;text-align:left;border:0;background:transparent;padding:7px 9px;border-radius:7px;font-size:13.5px;line-height:1.3}
.nav button:hover{background:var(--sink)}
.nav button[aria-current="page"]{background:var(--accent-soft);color:var(--accent);font-weight:600}
.nav button .no{font-family:var(--mono);font-size:11px;color:var(--muted);flex:none;width:17px}
.nav button[aria-current="page"] .no{color:var(--accent)}
.nav button .ct{margin-left:auto;font-family:var(--mono);font-size:10.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.side .foot{margin-top:auto;font-size:11.5px;color:var(--muted);line-height:1.5;border-top:1px solid var(--hair);padding-top:14px}
.side .foot b{color:var(--ink);font-family:var(--mono);font-weight:500}
.tbtn{border:1px solid var(--hair2);background:transparent;border-radius:7px;padding:5px 10px;font-size:12px;margin-top:9px}

/* ── nội dung ── */
.main{min-width:0;padding:0 0 90px}
.bar{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--paper) 88%,transparent);backdrop-filter:blur(8px);border-bottom:1px solid var(--hair);padding:11px 44px;display:flex;align-items:center;gap:12px;font-size:12.5px;color:var(--muted)}
.bar b{color:var(--ink);font-weight:600}
.bar .rt{margin-left:auto;font-family:var(--mono);font-size:11.5px}
.wrap{padding:34px 44px 0;max-width:1180px}
.col{max-width:75ch}

.hero{padding:16px 0 6px}
.kick{font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:var(--accent);font-weight:600}
.hero h1{font-family:var(--serif);font-size:clamp(34px,4.4vw,52px);line-height:1.06;letter-spacing:-.02em;margin:12px 0 14px;font-weight:600;text-wrap:balance;max-width:19ch}
.hero h1 em{font-style:italic;color:var(--accent)}
.hero .lede{font-size:17px;line-height:1.6;color:var(--muted);max-width:62ch;margin:0 0 22px}
.hero .lede b{color:var(--ink);font-weight:600}
.figs{display:flex;flex-wrap:wrap;gap:0;border:1px solid var(--hair);border-radius:11px;overflow:hidden;background:var(--card);max-width:760px}
.figs div{padding:13px 18px;flex:1 1 130px;border-right:1px solid var(--hair)}
.figs div:last-child{border-right:0}
.figs b{display:block;font-family:var(--mono);font-size:20px;font-weight:500;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.figs span{display:block;font-size:11.5px;color:var(--muted);margin-top:2px}

h2.sec{font-family:var(--serif);font-size:25px;font-weight:600;letter-spacing:-.01em;margin:44px 0 6px;text-wrap:balance}
p.secsub{color:var(--muted);margin:0 0 18px;max-width:66ch}

/* bản đồ tổng */
.mapbox{border:1px solid var(--hair);border-radius:13px;background:var(--card);overflow:hidden;box-shadow:var(--shadow-1)}
.mapbox .mh{display:flex;align-items:baseline;gap:10px;padding:13px 18px;border-bottom:1px solid var(--hair);flex-wrap:wrap}
.mapbox .mh b{font-size:13.5px}
.mapbox .mh span{font-size:12px;color:var(--muted)}
.mapbox .mh .lg{margin-left:auto;display:flex;gap:12px;font-size:11.5px;color:var(--muted)}
.mapbox .mh .lg i{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:5px;vertical-align:middle}
.mapscroll{overflow-x:auto}
.mapbox svg{display:block;width:100%;min-width:880px;height:520px}
.mn{cursor:pointer}
.mn rect{fill:var(--card);stroke:var(--hair2);stroke-width:1.2}
.mn:hover rect,.mn:focus-visible rect{stroke:var(--accent);stroke-width:2}
.mn .t{font-family:var(--sans);font-size:13px;font-weight:600;fill:var(--ink)}
.mn .s{font-family:var(--sans);font-size:11px;fill:var(--muted)}
.mn .dot{stroke:none}
.me{stroke:var(--edge);fill:none;stroke-width:1.4}
.me.loop{stroke:var(--edge-hi);stroke-width:2.2}
.mlab{font-family:var(--mono);font-size:10px;fill:var(--muted);letter-spacing:.04em}

/* phát hiện */
.finds{display:flex;flex-direction:column;gap:0;border-top:1px solid var(--hair)}
.find{display:grid;grid-template-columns:38px 1fr;gap:16px;padding:19px 0;border-bottom:1px solid var(--hair);align-items:start}
.find .n{font-family:var(--mono);font-size:12px;color:var(--muted);padding-top:3px;font-variant-numeric:tabular-nums}
.find h3{font-family:var(--serif);font-size:19px;font-weight:600;margin:0 0 5px;line-height:1.25;text-wrap:balance}
.find p{margin:0 0 8px;color:var(--muted);max-width:72ch}
.find p b{color:var(--ink)}
.find a.more{font-size:12.5px;text-decoration:none;border-bottom:1px solid currentColor}

/* lộ trình đọc */
.paths{display:grid;grid-template-columns:repeat(auto-fit,minmax(255px,1fr));gap:14px}
.pcard{border:1px solid var(--hair);border-radius:11px;padding:15px 17px;background:var(--card)}
.pcard b{font-family:var(--serif);font-size:17px;font-weight:600;display:block;margin-bottom:3px}
.pcard>span{font-size:12.5px;color:var(--muted);display:block;margin-bottom:10px}
.pcard ol{margin:0;padding-left:19px;font-size:12.5px;line-height:1.75}
.pcard ol a{text-decoration:none}
.pcard ol a:hover{text-decoration:underline}

/* chương */
.chead{border-bottom:2px solid var(--c);padding-bottom:16px;margin-bottom:8px}
.chead .no{font-family:var(--mono);font-size:12px;color:var(--c);letter-spacing:.1em}
.chead h1{font-family:var(--serif);font-size:34px;line-height:1.1;font-weight:600;letter-spacing:-.02em;margin:7px 0 8px;text-wrap:balance}
.chead p{color:var(--muted);margin:0;max-width:66ch}
article.node{padding:34px 0;border-bottom:1px solid var(--hair);scroll-margin-top:64px}
article.node:last-child{border-bottom:0}
article.node.flash{animation:fl 1.4s ease-out}
@keyframes fl{0%{background:var(--accent-soft)}100%{background:transparent}}
.eyeb{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:7px}
.pill{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:600;padding:2px 9px;border-radius:999px;border:1px solid var(--hair2)}
.pill::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--s)}
.src{font-family:var(--mono);font-size:11px;color:var(--muted)}
article.node h2{font-family:var(--serif);font-size:26px;line-height:1.18;font-weight:600;letter-spacing:-.015em;margin:0 0 8px;text-wrap:balance;max-width:26ch}
article.node .lead{font-size:16.5px;color:var(--muted);margin:0 0 18px;max-width:70ch;line-height:1.55}

/* prose */
.prose{max-width:75ch}
.prose h3{font-family:var(--serif);font-size:20px;font-weight:600;margin:26px 0 8px;letter-spacing:-.01em}
.prose h4{font-size:14px;font-weight:700;margin:20px 0 6px;letter-spacing:.01em}
.prose p{margin:0 0 13px}
.prose ul,.prose ol{margin:0 0 13px;padding-left:22px}
.prose li{margin:4px 0}
.prose li::marker{color:var(--muted)}
.prose blockquote{margin:16px 0;padding:13px 18px;border-left:3px solid var(--accent);background:var(--accent-soft);border-radius:0 9px 9px 0}
.prose blockquote p{margin:0;font-size:15.5px;font-family:var(--serif);line-height:1.55}
.prose blockquote cite{display:block;margin-top:7px;font-style:normal;font-size:12px;color:var(--muted);font-family:var(--sans)}
.prose code{font-family:var(--mono);font-size:12.5px;background:var(--code-bg);color:var(--code-ink);padding:1.5px 5px;border-radius:4px;word-break:break-word}
.prose pre.code{background:var(--code-bg);color:var(--code-ink);padding:14px 16px;border-radius:9px;overflow-x:auto;border:1px solid var(--hair);margin:14px 0}
.prose pre.code code{background:transparent;padding:0;font-size:12.5px;line-height:1.5}
.tw{overflow-x:auto;margin:14px 0;border:1px solid var(--hair);border-radius:9px}
.prose table{border-collapse:collapse;width:100%;font-size:13px}
.prose th,.prose td{padding:8px 12px;border-bottom:1px solid var(--hair);vertical-align:top;text-align:left}
.prose thead th{background:var(--sink);font-weight:600;white-space:nowrap;font-size:12px;letter-spacing:.01em}
.prose tbody tr:last-child td{border-bottom:0}
.prose a.wl{color:var(--accent);text-decoration:none;border-bottom:1px solid color-mix(in srgb,var(--accent) 45%,transparent)}
.prose a.wl:hover{background:var(--accent-soft)}
button.ev{font-family:var(--mono);font-size:12.5px;background:var(--code-bg);color:var(--code-ink);padding:1.5px 6px 1.5px 5px;border:1px solid var(--hair2);border-radius:4px;line-height:1.35}
button.ev::after{content:"↗";font-size:9px;margin-left:4px;color:var(--accent);vertical-align:2px}
button.ev:hover{border-color:var(--accent);background:var(--accent-soft)}

.rel{margin-top:22px;display:flex;flex-wrap:wrap;gap:7px;align-items:center}
.rel .lb{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-right:2px}
.rel button{border:1px solid var(--hair2);background:transparent;border-radius:999px;padding:3.5px 11px;font-size:12px;display:inline-flex;align-items:center;gap:6px;max-width:280px}
.rel button i{width:7px;height:7px;border-radius:50%;background:var(--c);flex:none}
.rel button span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rel button:hover{border-color:var(--accent);color:var(--accent)}

/* ngăn bằng chứng */
.scrim{position:fixed;inset:0;background:rgba(10,18,16,.45);z-index:40;opacity:0;transition:opacity .18s}
.scrim[hidden]{display:none}
.scrim.on{opacity:1}
.drawer{position:fixed;top:0;right:0;height:100vh;width:min(680px,94vw);background:var(--drawer);border-left:1px solid var(--hair2);z-index:41;display:flex;flex-direction:column;transform:translateX(100%);transition:transform .22s ease;box-shadow:var(--shadow-2)}
.drawer.on{transform:none}
.dh{padding:15px 20px;border-bottom:1px solid var(--hair);display:flex;gap:12px;align-items:flex-start}
.dh .k{font-size:10.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--accent);font-weight:600}
.dh b{display:block;font-family:var(--mono);font-size:13.5px;margin-top:4px;word-break:break-all}
.dh .meta{font-size:11.5px;color:var(--muted);margin-top:4px}
.dh button{margin-left:auto;border:1px solid var(--hair2);background:transparent;border-radius:7px;width:30px;height:30px;flex:none;font-size:15px;line-height:1}
.db{overflow:auto;padding:6px 0 30px;flex:1}
.db table{border-collapse:collapse;width:100%;font-family:var(--mono);font-size:12px;line-height:1.55}
.db td.ln{width:1%;text-align:right;padding:0 12px 0 18px;color:var(--muted);user-select:none;vertical-align:top;font-variant-numeric:tabular-nums}
.db td.cd{padding:0 18px 0 0;white-space:pre-wrap;word-break:break-word;color:var(--code-ink)}
.db tr.hi td{background:var(--accent-soft)}
.dnote{padding:11px 20px;border-top:1px solid var(--hair);font-size:11.5px;color:var(--muted)}

/* bản đồ đầy đủ */
.gwrap{display:grid;grid-template-columns:1fr 250px;gap:18px;align-items:start}
.gbox{border:1px solid var(--hair);border-radius:13px;background:var(--card);overflow:hidden;position:relative}
#g{width:100%;height:min(70vh,660px);display:block;cursor:grab}
#g:active{cursor:grabbing}
.gnode circle{stroke:var(--card);stroke-width:1.5}
.gnode text{font-family:var(--sans);font-size:10px;fill:var(--ink);paint-order:stroke;stroke:var(--paper);stroke-width:3px;stroke-linejoin:round;pointer-events:none}
.gnode.dim{opacity:.16}
.glink{stroke:var(--edge);stroke-opacity:.5;stroke-width:1}
.glink.dim{stroke-opacity:.07}
.glink.hi{stroke:var(--edge-hi);stroke-opacity:.9;stroke-width:1.7}
.gside .fil{display:flex;flex-direction:column;gap:5px;margin-bottom:16px}
.gside .fil button{display:flex;align-items:center;gap:9px;border:1px solid var(--hair);background:transparent;border-radius:8px;padding:6px 9px;font-size:12.5px;text-align:left}
.gside .fil button[aria-pressed="false"]{opacity:.42}
.gside .fil i{width:9px;height:9px;border-radius:50%;background:var(--c);flex:none}
.gside .fil .ct{margin-left:auto;font-family:var(--mono);font-size:10.5px;color:var(--muted)}
.gtip{position:absolute;pointer-events:none;background:var(--card);border:1px solid var(--hair2);border-radius:8px;padding:7px 10px;font-size:12.5px;box-shadow:var(--shadow-2);max-width:300px;display:none;z-index:5}
.gtip .e{font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.gfall{padding:18px}
.gfall a{display:inline-block;margin:0 10px 8px 0;font-size:12.5px}

/* tìm kiếm */
.res{display:flex;flex-direction:column;gap:0}
.res button{display:block;width:100%;text-align:left;border:0;border-bottom:1px solid var(--hair);background:transparent;padding:15px 2px}
.res button:hover{background:var(--sink)}
.res .t{font-family:var(--serif);font-size:17px;font-weight:600;margin-bottom:3px}
.res .s{font-size:13px;color:var(--muted)}
.res .m{font-size:11px;color:var(--muted);font-family:var(--mono);margin-top:5px}

/* nguồn */
.srcgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:22px}
.srcgrid ol,.srcgrid ul{padding-left:20px;margin:0;font-size:13.5px;line-height:1.7}
.mtable td:first-child{font-family:var(--mono);font-size:12px;white-space:nowrap}

@media (max-width:1080px){
  .shell{grid-template-columns:1fr}
  .side{position:static;height:auto;border-right:0;border-bottom:1px solid var(--hair)}
  .bar{padding:11px 22px}.wrap{padding:26px 22px 0}
  .gwrap{grid-template-columns:1fr}
}
@media print{
  .side,.bar,.drawer,.scrim,.mapbox .mh .lg{display:none!important}
  .wrap{padding:0;max-width:none}.shell{display:block}
  article.node{break-inside:avoid;border-bottom:1px solid #ccc}
}
"""

JS = r"""
'use strict';
const D = JSON.parse(document.getElementById('d').textContent);
const {nodes:NS, layers:LY, evidence:EV, paths:PATHS} = D;
const byId = Object.fromEntries(NS.map(n=>[n.id,n]));
const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

/* ── điều hướng trang ── */
let page = 'home';
function show(p, opts){
  const el = document.getElementById('p-'+p);
  if(!el) return;
  document.querySelectorAll('.page').forEach(x=>x.hidden = true);
  el.hidden = false;
  page = p;
  document.querySelectorAll('.nav button').forEach(b=>{
    if(b.dataset.page===p) b.setAttribute('aria-current','page'); else b.removeAttribute('aria-current');
  });
  $('#crumb').textContent = el.dataset.title || '';
  if(p==='map') drawGraph();
  if(!opts || !opts.keepScroll) window.scrollTo({top:0, behavior:'auto'});
}
function jump(id){
  const n = byId[id]; if(!n) return;
  show('ch'+n.layer, {keepScroll:true});
  const a = document.getElementById(id);
  if(a){
    a.scrollIntoView({block:'start'});
    a.classList.remove('flash'); void a.offsetWidth; a.classList.add('flash');
    history.replaceState(null,'','#'+id);
  }
}
document.addEventListener('click', e=>{
  const nav = e.target.closest('[data-page]');
  if(nav){ show(nav.dataset.page); return; }
  const j = e.target.closest('[data-jump]');
  if(j){ e.preventDefault(); jump(j.dataset.jump); return; }
  const ev = e.target.closest('.ev');
  if(ev){ openEv(ev.dataset.ev, ev.dataset.line); return; }
});

/* ── ngăn bằng chứng ── */
let lastFocus=null;
function openEv(key, line){
  const f = EV[key]; if(!f) return;
  lastFocus = document.activeElement;
  const from = f.from, to = f.from + f.lines.length - 1;
  let hi = 0;
  if(line){ const m = String(line).split('-'); hi = parseInt(m[0],10)||0; }
  $('#d-path').textContent = f.path;
  $('#d-meta').textContent = `Dòng ${from}–${to} trên ${f.total} · ảnh chụp tĩnh từ kho mã, không truy vấn hệ đang chạy`;
  $('#d-body').innerHTML = '<table><tbody>' + f.lines.map((l,i)=>{
    const no = from + i;
    return `<tr class="${hi&&no===hi?'hi':''}"><td class="ln">${no}</td><td class="cd">${esc(l)||' '}</td></tr>`;
  }).join('') + '</tbody></table>';
  const sc=$('#scrim'); sc.hidden=false; void sc.offsetWidth;   // ép vẽ lại: không phụ thuộc rAF (tab ẩn thì rAF không chạy)
  sc.classList.add('on'); $('#drawer').classList.add('on');
  $('#d-close').focus();
  if(hi){ const r = $('#d-body').querySelector('tr.hi'); if(r) r.scrollIntoView({block:'center'}); }
}
function closeEv(){
  $('#scrim').classList.remove('on'); $('#drawer').classList.remove('on');
  setTimeout(()=>{ $('#scrim').hidden=true; }, 200);
  if(lastFocus) lastFocus.focus();
}
$('#d-close').addEventListener('click', closeEv);
$('#scrim').addEventListener('click', closeEv);
document.addEventListener('keydown', e=>{ if(e.key==='Escape'){ if($('#drawer').classList.contains('on')) closeEv(); }});

/* ── chủ đề ── */
const tb = $('#theme');
try{ const t = localStorage.getItem('ck-theme'); if(t) document.documentElement.dataset.theme = t; }catch(e){}
tb.addEventListener('click', ()=>{
  const cur = document.documentElement.dataset.theme
    || (matchMedia('(prefers-color-scheme:dark)').matches ? 'dark':'light');
  const next = cur==='dark' ? 'light':'dark';
  document.documentElement.dataset.theme = next;
  try{ localStorage.setItem('ck-theme', next); }catch(e){}
});

/* ── tìm ── */
const qi = $('#q'); let qt=null;
qi.addEventListener('input', ()=>{
  clearTimeout(qt);
  qt = setTimeout(()=>{
    const v = qi.value.trim().toLowerCase();
    if(!v){ if(page==='search') show('home'); return; }
    const hit = NS.filter(n => (n.title+' '+n.summary+' '+n.tag+' '+n.body).toLowerCase().includes(v)).slice(0,40);
    $('#res').innerHTML = hit.length ? hit.map(n=>`
      <button data-jump="${n.id}"><div class="t">${esc(n.title)}</div><div class="s">${esc(n.summary)}</div>
      <div class="m">${esc(LY[n.layer].so)} · ${esc(LY[n.layer].ten)}${n.status?' · '+esc(D.status[n.status]):''}</div></button>`).join('')
      : '<p style="color:var(--muted)">Không có nút nào khớp. Thử tên bảng, tên hàm, hoặc số mục tài liệu.</p>';
    $('#res-q').textContent = qi.value.trim();
    $('#res-n').textContent = hit.length;
    show('search');
  }, 160);
});

/* ── bản đồ đầy đủ ── */
let gDrawn=false, gSim=null;
function drawGraph(){
  if(gDrawn) return;
  if(typeof d3==='undefined'){
    $('#gbox').innerHTML = '<div class="gfall"><p style="color:var(--muted);margin:0 0 10px">Không tải được thư viện vẽ đồ thị. Danh sách nút vẫn mở được:</p>'
      + NS.map(n=>`<a href="#${n.id}" data-jump="${n.id}">${esc(n.title.split(' — ')[0])}</a>`).join('') + '</div>';
    gDrawn=true; return;
  }
  gDrawn = true;
  const links=[], seen=new Set();
  NS.forEach(n=>n.links.forEach(t=>{ const k=n.id<t?n.id+'|'+t:t+'|'+n.id; if(!seen.has(k)){seen.add(k); links.push({source:n.id,target:t});} }));
  const deg={}; links.forEach(l=>{deg[l.source]=(deg[l.source]||0)+1; deg[l.target]=(deg[l.target]||0)+1;});
  const data = NS.map(n=>Object.assign({}, n));
  const svg = d3.select('#g'), box = $('#gbox');
  let W = box.clientWidth, H = Math.min(innerHeight*0.7, 660);
  const g = svg.append('g'), lg = g.append('g'), ng = g.append('g');
  const rr = d => 4.5 + Math.min(10, Math.sqrt(deg[d.id]||1)*2);
  const colX = l => (l-0.5)/6*W;
  gSim = d3.forceSimulation(data)
    .force('link', d3.forceLink(links).id(d=>d.id).distance(l=>62+Math.abs(l.source.layer-l.target.layer)*18).strength(.33))
    .force('charge', d3.forceManyBody().strength(-155))
    .force('x', d3.forceX(d=>colX(d.layer)).strength(.3))
    .force('y', d3.forceY(H/2).strength(.05))
    .force('collide', d3.forceCollide(d=>rr(d)+13));
  const link = lg.selectAll('line').data(links).join('line').attr('class','glink');
  const node = ng.selectAll('g').data(data).join('g').attr('class','gnode').attr('tabindex',0)
    .call(d3.drag()
      .on('start',(e,d)=>{ if(!e.active) gSim.alphaTarget(.25).restart(); d.fx=d.x; d.fy=d.y; })
      .on('drag',(e,d)=>{ d.fx=e.x; d.fy=e.y; })
      .on('end',(e,d)=>{ if(!e.active) gSim.alphaTarget(0); d.fx=null; d.fy=null; }));
  node.append('circle').attr('r',rr).attr('fill',d=>`var(--l${d.layer})`);
  node.append('text').attr('dy',d=>rr(d)+10).attr('text-anchor','middle')
    .text(d=>{ const s=d.title.split(' — ')[0]; return s.length>30?s.slice(0,28)+'…':s; });
  const tip = $('#gtip');
  node.on('mouseenter',(e,d)=>{ tip.style.display='block';
      tip.innerHTML = `<div class="e" style="color:var(--l${d.layer})">${esc(LY[d.layer].ten)}${d.status?' · '+esc(D.status[d.status]):''}</div>${esc(d.title)}`; mv(e); })
    .on('mousemove',mv).on('mouseleave',()=>tip.style.display='none')
    .on('click',(e,d)=>jump(d.id))
    .on('keydown',(e,d)=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); jump(d.id); } });
  function mv(e){ const b=box.getBoundingClientRect(); tip.style.left=(e.clientX-b.left+14)+'px'; tip.style.top=(e.clientY-b.top+14)+'px'; }
  gSim.on('tick',()=>{
    link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
    node.attr('transform',d=>`translate(${d.x},${d.y})`);
  });
  svg.call(d3.zoom().scaleExtent([.35,3]).on('zoom',e=>g.attr('transform',e.transform)));
  const on = new Set([1,2,3,4,5,6]);
  document.querySelectorAll('#gfil button').forEach(b=>{
    b.addEventListener('click',()=>{
      const k=+b.dataset.layer, isOn=b.getAttribute('aria-pressed')==='true';
      b.setAttribute('aria-pressed', String(!isOn)); if(isOn) on.delete(k); else on.add(k);
      node.classed('dim', d=>!on.has(d.layer));
      link.classed('dim', l=>!on.has(l.source.layer)||!on.has(l.target.layer));
    });
  });
  new ResizeObserver(()=>{ W=box.clientWidth; gSim.force('x', d3.forceX(d=>colX(d.layer)).strength(.3)).alpha(.25).restart(); }).observe(box);
}

/* ── vào trang ── */
const h = location.hash.replace('#','');
if(h && byId[h]) jump(h); else show('home');
"""


def build_html(nodes: list[dict], ev: dict, out: Path) -> None:
    titles = {n["id"]: n["title"] for n in nodes}
    by_layer = defaultdict(list)
    for n in nodes:
        by_layer[n["layer"]].append(n)

    def st_css(s: str | None) -> str:
        return {"co": "var(--ok)", "mot-phan": "var(--warn)", "chua": "var(--bad)"}.get(s or "", "var(--muted)")

    def chip(nid: str) -> str:
        n = byId[nid]
        return (f'<button data-jump="{esca(nid)}" style="--c:var(--l{n["layer"]})"><i></i>'
                f'<span>{esc(n["title"].split(" — ")[0])}</span></button>')

    byId = {n["id"]: n for n in nodes}

    # ── sidebar
    nav = ['<button data-page="home"><span class="no">◆</span>Trang đầu</button>',
           '<button data-page="map"><span class="no">◇</span>Bản đồ đầy đủ<span class="ct">%d</span></button>' % len(nodes)]
    chap_nav = []
    for k, L in LAYERS.items():
        chap_nav.append(f'<button data-page="ch{k}"><span class="no">{L["so"]}</span>{esc(L["ten"])}'
                        f'<span class="ct">{len(by_layer[k])}</span></button>')
    nav_src = '<button data-page="sources"><span class="no">✦</span>Nguồn & phạm vi</button>'

    # ── bản đồ tổng (SVG tĩnh)
    mp = {m["id"]: m for m in MAP_NODES}
    BW, BH = 158, 52
    edges_svg = []
    for a, b, loop in MAP_EDGES:
        A, B = mp[a], mp[b]
        x1, y1 = A["x"] + BW / 2, A["y"] + BH / 2
        x2, y2 = B["x"] + BW / 2, B["y"] + BH / 2
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        curve = 26 if not loop else 14
        cx = mx + (y2 - y1) / max(1, abs(x2 - x1) + abs(y2 - y1)) * curve
        cy = my - (x2 - x1) / max(1, abs(x2 - x1) + abs(y2 - y1)) * curve
        edges_svg.append(f'<path class="me{" loop" if loop else ""}" d="M{x1:.0f},{y1:.0f} Q{cx:.0f},{cy:.0f} {x2:.0f},{y2:.0f}"/>')
    nodes_svg = []
    for m in MAP_NODES:
        nodes_svg.append(
            f'<g class="mn" tabindex="0" role="button" data-jump="{esca(m["to"])}" '
            f'aria-label="{esca(m["ten"] + " — " + m["phu"])}">'
            f'<rect x="{m["x"]}" y="{m["y"]}" width="{BW}" height="{BH}" rx="10"/>'
            f'<circle class="dot" cx="{m["x"]+13}" cy="{m["y"]+18}" r="4.5" fill="{st_css(m["tt"])}"/>'
            f'<text class="t" x="{m["x"]+24}" y="{m["y"]+22}">{esc(m["ten"])}</text>'
            f'<text class="s" x="{m["x"]+13}" y="{m["y"]+39}">{esc(m["phu"])}</text></g>')
    mapsvg = (f'<svg viewBox="0 0 990 500" role="img" aria-label="Vòng lặp: sự thật → sự kiện → trạng thái → luật → đầu việc → hành động → kết quả">'
              f'<text class="mlab" x="150" y="34">VÒNG KHÉP KÍN</text>'
              + "".join(edges_svg) + "".join(nodes_svg) + "</svg>")

    # ── trang chủ
    figs = [("101", "nút thiết kế"), ("659", "cạnh"), ("9", "tài liệu gốc"),
            (str(len(ev)), "tệp bằng chứng"), ("449", "dòng sổ sự kiện đã đo")]
    finds = "".join(
        f'<div class="find"><div class="n">{i+1:02d}</div><div><h3>{esc(t)}</h3>'
        f'<p>{R.inline(d, titles, ev)}</p>'
        f'<a class="more" href="#{esca(nid)}" data-jump="{esca(nid)}">Đọc nút này →</a></div></div>'
        for i, (t, d, nid) in enumerate(PHAT_HIEN))
    paths_html = "".join(
        f'<div class="pcard"><b>{esc(p["ten"])}</b><span>{esc(p["mo_ta"])}</span><ol>'
        + "".join(f'<li><a href="#{esca(t)}" data-jump="{esca(t)}">{esc(byId[t]["title"].split(" — ")[0])}</a></li>'
                  for t in p["nodes"]) + "</ol></div>"
        for p in READING_PATHS)

    home = f"""<section class="page" id="p-home" data-title="Trang đầu" hidden>
<div class="wrap">
  <div class="hero">
    <div class="kick">Một thiết kế · một ngôn ngữ · một vòng chăm sóc</div>
    <h1>Chín tài liệu, một kho mã, và <em>chỗ hai bên chưa gặp nhau.</em></h1>
    <p class="lede">Bản này đọc trọn chín tài liệu Quang viết ngày 03/09, đọc code đang chạy, rồi <b>đo trực tiếp trên máy chủ</b> để nói chính xác điều gì đã có, điều gì mới có một nửa, điều gì chưa có — và làm tiếp theo thứ tự nào. Mỗi khẳng định đều bấm ra được nguyên văn tài liệu hoặc dòng code.</p>
    <div class="figs">{"".join(f'<div><b>{a}</b><span>{esc(b)}</span></div>' for a, b in figs)}</div>
  </div>

  <h2 class="sec">Vòng chăm sóc mà toàn bộ thiết kế hướng tới</h2>
  <p class="secsub">Bảy nút trong vòng đậm là mạch chính tài liệu đòi: sự thật → sự kiện → trạng thái → luật → đầu việc có chủ → hành động → kết quả đóng vòng. Bảy nút quanh nó là điều kiện để mạch ấy đáng tin. Chấm màu là hiện trạng code. Bấm một nút để đọc.</p>
  <div class="mapbox">
    <div class="mh"><b>Bản đồ khái niệm</b><span>14 nút · bấm để mở chương tương ứng</span>
      <div class="lg"><span><i style="background:var(--ok)"></i>Đã có</span><span><i style="background:var(--warn)"></i>Một phần</span><span><i style="background:var(--bad)"></i>Chưa có</span></div>
    </div>
    <div class="mapscroll">{mapsvg}</div>
  </div>

  <h2 class="sec">Năm điều nên đọc trước</h2>
  <p class="secsub">Mỗi điều là một kết luận có số đo hoặc dòng code đứng sau. Số đo trên máy chủ lấy ngày 04–05/09/2026 và <b>chưa được đo lại</b> ở vòng đính chính 06/09; phần đọc code đã kiểm lại tại commit <code>9376db8</code>.</p>
  <div class="finds">{finds}</div>

  <h2 class="sec">Đọc theo lộ trình</h2>
  <p class="secsub">Ba đường đi tuỳ việc bạn cần làm. Bấm một mục để nhảy thẳng tới nút đó.</p>
  <div class="paths">{paths_html}</div>

  <h2 class="sec">Sáu chương</h2>
  <p class="secsub">Đi từ trái sang phải trong bản đồ đầy đủ: tài liệu định hướng → kiến trúc → code thật → khoảng cách → thiết kế đích → lộ trình.</p>
  <div class="paths">{"".join(f'''<div class="pcard" style="--c:var(--l{k})"><b style="color:var(--l{k})">{L["so"]} · {esc(L["ten"])}</b><span>{esc(L["phu"])}</span>
    <button data-page="ch{k}" style="border:1px solid var(--hair2);background:transparent;border-radius:8px;padding:5px 11px;font-size:12.5px">Mở chương · {len(by_layer[k])} nút</button></div>''' for k, L in LAYERS.items())}</div>
</div></section>"""

    # ── chương
    chapters = []
    for k, L in LAYERS.items():
        arts = []
        for n in by_layer[k]:
            pill = (f'<span class="pill" style="--s:{st_css(n.get("status"))}">{esc(STATUS[n["status"]])}</span>'
                    if n.get("status") else "")
            rel = ('<div class="rel"><span class="lb">Nối tới</span>'
                   + "".join(chip(t) for t in n["links"]) + "</div>") if n["links"] else ""
            back = ('<div class="rel"><span class="lb">Được dẫn từ</span>'
                    + "".join(chip(t) for t in n["backlinks"]) + "</div>") if n["backlinks"] else ""
            arts.append(
                f'<article class="node" id="{esca(n["id"])}"><div class="eyeb">{pill}'
                f'<span class="src">{esc(n["tag"])}</span></div>'
                f'<h2>{esc(n["title"])}</h2><p class="lead">{esc(n["summary"])}</p>'
                f'<div class="prose">{R.render(n["body"], titles, ev)}</div>{rel}{back}</article>')
        chapters.append(
            f'<section class="page" id="p-ch{k}" data-title="{esca(L["so"] + " · " + L["ten"])}" hidden>'
            f'<div class="wrap"><div class="chead" style="--c:var(--l{k})">'
            f'<div class="no">CHƯƠNG {L["so"]}</div><h1>{esc(L["ten"])}</h1><p>{esc(L["phu"])}</p></div>'
            + "".join(arts) + "</div></section>")

    # ── bản đồ đầy đủ
    fil = "".join(f'<button data-layer="{k}" aria-pressed="true" style="--c:var(--l{k})"><i></i>{esc(L["ten"])}'
                  f'<span class="ct">{len(by_layer[k])}</span></button>' for k, L in LAYERS.items())
    mappage = f"""<section class="page" id="p-map" data-title="Bản đồ đầy đủ" hidden><div class="wrap">
  <div class="chead" style="--c:var(--accent)"><div class="no">TOÀN BỘ</div>
  <h1>Bản đồ đầy đủ</h1><p>101 nút và mọi quan hệ giữa chúng. Sáu lớp xếp từ trái sang phải. Kéo để sắp lại, lăn để phóng, bấm một nút để mở bài viết của nó.</p></div>
  <div class="gwrap"><div class="gbox" id="gbox"><svg id="g"></svg><div class="gtip" id="gtip"></div></div>
  <aside class="gside"><h3 style="font-size:10.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted);margin:0 0 8px">Lọc theo lớp</h3>
  <div class="fil" id="gfil">{fil}</div>
  <p style="font-size:12.5px;color:var(--muted);margin:0">Cạnh là quan hệ thật giữa các nút: nút thiết kế nào đóng khoảng cách nào, khoảng cách nào sinh ra từ điều khoản nào của tài liệu.</p>
  </aside></div></div></section>"""

    # ── nguồn
    doc_rows = "".join(f"<li><b>{esc(a)}</b> — {esc(b)}</li>" for a, b in SOURCES_DOC)
    repo_rows = "".join(f"<li>{R.inline(x, titles, ev)}</li>" for x in SOURCES_REPO)
    measured = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for a, b in DO_TREN_MAY)
    sources = f"""<section class="page" id="p-sources" data-title="Nguồn & phạm vi" hidden><div class="wrap col">
  <div class="chead" style="--c:var(--accent)"><div class="no">NGUỒN</div><h1>Đã đọc gì, đo gì, và không làm gì</h1>
  <p>Bản thiết kế chỉ đáng tin bằng nguồn của nó. Đây là toàn bộ những gì đứng sau các kết luận trong sáu chương.</p></div>
  <div class="prose" style="padding-top:22px">
  <h3>Chín tài liệu định hướng</h3><ol>{doc_rows}</ol>
  <h3>Tài liệu và mã trong kho</h3><ul>{repo_rows}</ul>
  <h3>Đo trực tiếp trên máy chủ, 04–05/09/2026</h3>
  <p>Chỉ đọc, qua <code>ssh clinic-vps</code>. Không tạo, sửa, xoá dòng nào; không đọc tệp bí mật; không gửi tin. <b>Vòng đính chính 06/09 không truy cập lại máy chủ</b>, nên mọi con số dưới đây giữ nguyên trạng thái “đo một lần, chưa xác minh lại”. Những chỗ tôi từng suy từ các con số này ra kết luận quá tay đã được rút lại và ghi rõ phép đo còn thiếu.</p>
  <div class="tw"><table class="mtable"><thead><tr><th>Đo cái gì</th><th>Kết quả</th></tr></thead><tbody>{measured}</tbody></table></div>
  <h3>Đính chính 06/09/2026 — vòng phản biện của Codex</h3>
  <p>Codex đọc worktree này tại <code>9376db8</code> qua ba vòng và chỉ ra <b>mười</b> kết luận rút quá tay: phần lớn suy từ một con số hoặc từ <code>grep</code> mà không truy hết đường gọi, hai cái sai ngay trong chính đề xuất của tôi. Tôi đã đọc lại code tại chính commit ấy và sửa tại nguồn sinh. Bảng dưới là toàn bộ thay đổi.</p>
  <div class="tw"><table><thead><tr><th>Nhận định cũ</th><th>Sau khi kiểm</th><th>Bằng chứng</th></tr></thead><tbody>
  <tr><td>Mốc <code>CHECK_IN</code> của CSKH không ghi <code>appointment.checked_in</code>; hai đường hai tên</td><td><b>Sai.</b> Mốc quầy CSKH và nút lễ tân hội tụ ở cùng <code>apply_action</code>, một event, cùng transaction. 1/66 không chứng minh mất event vì mẫu số là lịch đã tạo. Có thêm nhánh <code>auto_checkin</code> cho khách vãng lai trong ngày, cùng tên event nhưng không qua <code>apply_action</code> — nên không tuyên bố “một cửa ghi duy nhất”</td><td><code>tuong_tac_cskh_service.py:188</code> · <code>:437</code> · <code>booking_service.py:273</code> · <code>:819</code> · <code>booking_service.py:464</code> · <code>:623</code></td></tr>
  <tr><td><code>event_published=TRUE</code> 449/449 ⇒ relay đang chạy và xử lý mọi thứ</td><td><b>Không suy ra được.</b> Có ít nhất ba cách đặt được cờ này mà không có tin nào tới người: script đánh dấu hàng loạt, nhánh không-có-template trong relay, và nhánh nhà cung cấp trả ok. Số đo không nói cách nào đã đặt dòng nào</td><td><code>scripts/danh-dau-event-cu-truoc-khi-bat-telegram.sql:17</code> · <code>notification_relay.py:238</code></td></tr>
  <tr><td>Nhiễu 62% khiến <code>event_log</code> không dùng được làm timeline</td><td><b>Sai.</b> Đang được đọc làm timeline thật. Tỷ lệ 62% là của toàn lịch sử, không suy ra thành phần 200 dòng mới nhất. Vấn đề đúng là lọc telemetry, ngữ nghĩa domain event và replay — ba việc khác nhau</td><td><code>audit_log_service.py:191</code> · <code>20260805000001_v_audit_log.sql</code></td></tr>
  <tr><td>100% lịch do CSKH đặt ⇒ toàn bộ giá trị nằm trước buổi khám</td><td><b>Rút lại.</b> Người tạo lịch, chức năng code phủ tới đâu, mức dùng thật và chọn wedge là bốn thứ khác nhau; dịch vụ CSKH phủ cả trong và sau buổi khám</td><td><code>tuong_tac_cskh_service.py:62</code> · <code>:71</code></td></tr>
  <tr><td><code>move_visit_to_station</code> lật <code>visit.status</code> mà không có event</td><td><b>Sai.</b> Có ghi <code>event_log</code>, mặc định <code>dispatch.moved</code>. Chỗ hụt là thiếu <i>tên</i> cho bước ngoặt vòng đời, không phải thiếu ghi</td><td><code>20260804000013_room_serves_many_nodes.sql:227</code></td></tr>
  <tr><td>Relay đánh dấu đã xử lý “ngay khi gửi”, rồi bản sửa lần đầu nói “chỉ đánh dấu sau khi gửi thành công”</td><td><b>Cả hai đều sai.</b> Cờ được đặt ở hai nhánh: sự kiện <b>không có template thì đánh dấu mà không gửi gì</b> rồi <code>continue</code>, sự kiện gửi được thì đánh dấu khi nhà cung cấp trả ok. Bộ đếm <code>processed</code> trong log cộng cả hai. Nhánh thiếu cấu hình nhà cung cấp thì để lại cho vòng sau. Bốn mức phải tách: processed · không-có-template · nhà cung cấp ok · người nhận đã biết</td><td><code>notification_relay.py:205-214</code> · <code>:238</code> · <code>:256</code></td></tr>
  <tr><td><code>recorded_at − occurred_at</code> max 0 giây ⇒ chưa từng có ghi bù hay ghi trễ</td><td><b>Không suy ra được.</b> Hai cột cùng <code>DEFAULT now()</code> và đường ghi truyền thẳng <code>now()</code>, nên bằng nhau là do cấu tạo. Điều đọc được chỉ là chưa đường ghi nào truyền mốc thật; độ trễ ngoài đời hiện không đo được</td><td><code>baseline_schema.sql:539-540</code> · <code>tuong_tac_cskh_service.py:249-256</code></td></tr>
  <tr><td>Đếm nhánh <code>auto_checkin</code> “theo <code>origin</code>” như một cột</td><td><b>Sai đường dữ liệu.</b> Không có cột <code>origin</code>: <code>_log</code> ghi giá trị ấy vào cột <code>source</code> và vào <code>metadata-&gt;&gt;'origin'</code>. Phép đo phải lọc theo <code>clinic_id</code> và một khoảng thời gian rõ ràng</td><td><code>booking_service.py:2019-2036</code></td></tr>
  <tr><td>Đề xuất của chính tôi: “cộng 12 cột”, và consumer đọc <code>seq &gt; last_seq</code>, lag = <code>max(seq) − last_seq</code></td><td><b>Sai hai chỗ.</b> Câu SQL thêm <b>14</b> cột. Và <code>bigserial</code> cấp số lúc INSERT chứ không lúc commit: transaction lấy seq sớm mà commit muộn sẽ bị bỏ qua vĩnh viễn; sequence có khoảng trống nên hiệu hai số không phải số việc tồn. Giao thức này bị đánh dấu <b>chưa an toàn, chưa kiểm chứng</b>, yêu cầu xác nhận theo từng event + idempotency + test commit đảo thứ tự và crash-retry trước khi cài. Vòng này không cài gì</td><td>tài liệu PostgreSQL <i>functions-sequence</i> và <i>Wiki FAQ</i>; nút <i>Envelope v2</i></td></tr>
  </tbody></table></div>
  <p>Bốn phép đo còn nợ, ghi lại thành <b>yêu cầu</b> chứ không thành câu SQL sẵn, vì câu viết vội dễ đo nhầm thứ khác: (1) check-in có mất event không — đối soát từng cặp <code>(clinic_id, appointment_id)</code>, xét hoàn tác và thứ tự thời gian, không so hai tổng <code>count(*)</code>; (2) <code>tuong_tac_cskh</code> tách theo <code>loai</code>, để biết CSKH đang chạm chặng nào; (3) thành phần <code>event_type</code> của đúng 200 dòng mà màn Lịch sử thao tác hiển thị — phải chạy lại chính câu trong <code>audit_log_service.py</code> (UNION <code>v_audit_log</code> với <code>work_item_event</code> rồi mới sắp xếp và cắt), không phải <code>LIMIT 200</code> trên một nguồn; (4) nhánh <code>auto_checkin</code> đã từng chạy chưa — đếm event có <code>source = 'api:appointment-walkin-autocheckin'</code> hoặc <code>metadata-&gt;&gt;'origin'</code> bằng chuỗi ấy, lọc theo <code>clinic_id</code> và khoảng thời gian; không suy từ ảnh chụp bảng lịch hẹn. Thêm (5) độ trễ ghi nhận thật: chỉ đo được sau khi có đường ghi truyền <code>occurred_at</code> thật, hiện chưa có; và (6) tách bộ đếm relay thành không-có-template so với nhà cung cấp trả ok, đọc từ log <code>relay_no_template</code> và <code>relay_poll_complete</code>.</p>

  <h3>Những gì bản này KHÔNG làm</h3>
  <ul><li>Không chạy migration, không bật worker, không đổi cấu hình nào.</li>
  <li>Không đăng nhập ứng dụng bằng tài khoản nhân viên; số liệu lấy bằng truy vấn chỉ đọc.</li>
  <li>Không kiểm chứng các con số vĩ mô, định giá hay pháp lý trong tài liệu; chúng được trích, không được thẩm định.</li>
  <li>Không tự phê duyệt quyết định nào — tám câu còn mở nằm ở chương 06.</li></ul>
  <h3>Bốn nhãn dùng xuyên suốt</h3>
  <div class="tw"><table><thead><tr><th>Nhãn</th><th>Nghĩa</th></tr></thead><tbody>
  <tr><td><span class="pill" style="--s:var(--ok)">Đã có</span></td><td>Đọc được đường code hoặc dòng dữ liệu chứng minh; không đồng nghĩa đã chạy đủ tải hay đã có người dùng.</td></tr>
  <tr><td><span class="pill" style="--s:var(--warn)">Một phần</span></td><td>Có bảng, có hàm, nhưng thiếu một mảnh khiến nó chưa làm được điều tài liệu đòi.</td></tr>
  <tr><td><span class="pill" style="--s:var(--bad)">Chưa có</span></td><td>Không tìm thấy trong phạm vi đã đọc.</td></tr>
  <tr><td><i>Thiết kế đích</i></td><td>Đề xuất của tôi. Chương 05 ghi rõ chỗ nào tôi tự quyết và đảo được.</td></tr>
  </tbody></table></div>
  </div></div></section>"""

    search = """<section class="page" id="p-search" data-title="Kết quả tìm" hidden><div class="wrap col">
  <div class="chead" style="--c:var(--accent)"><div class="no">TÌM</div>
  <h1>Kết quả cho “<span id="res-q"></span>”</h1><p><span id="res-n">0</span> nút khớp.</p></div>
  <div class="res" id="res" style="padding-top:16px"></div></div></section>"""

    data = {
        "nodes": [{"id": n["id"], "layer": n["layer"], "title": n["title"], "tag": n["tag"],
                   "summary": n["summary"], "status": n.get("status"), "links": n["links"],
                   "body": n["body"][:1400]} for n in nodes],
        "layers": {str(k): {"so": v["so"], "ten": v["ten"]} for k, v in LAYERS.items()},
        "status": STATUS,
        "evidence": ev,
        "paths": READING_PATHS,
    }
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    doc = f"""<title>Hệ thần kinh ClinicAI</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style>
<a class="skip" href="#main">Bỏ qua menu, tới nội dung</a>
<div class="shell">
  <aside class="side">
    <div class="brand"><div class="mark">C</div><div><b>Hệ thần kinh ClinicAI</b><span>Bản thiết kế thống nhất</span></div></div>
    <input class="q" id="q" type="search" placeholder="Tìm khái niệm, tên bảng, số mục…" aria-label="Tìm trong bản thiết kế" autocomplete="off">
    <div><h3>Không gian</h3><div class="nav">{"".join(nav)}</div></div>
    <div><h3>Sáu chương</h3><div class="nav">{"".join(chap_nav)}</div></div>
    <div><h3>Kiểm chứng</h3><div class="nav">{nav_src}</div></div>
    <div class="foot">Đối chiếu ngày <b>05/09/2026</b>. Chạy hoàn toàn ngoại tuyến.<br>
      Phân biệt rõ hiện trạng và thiết kế đích trong từng nút.
      <button class="tbtn" id="theme">Đổi sáng / tối</button></div>
  </aside>
  <main class="main" id="main" tabindex="-1">
    <div class="bar"><span>ClinicAI /</span><b id="crumb"></b><span class="rt">101 nút · 6 lớp</span></div>
    {home}{"".join(chapters)}{mappage}{sources}{search}
  </main>
</div>
<div class="scrim" id="scrim" hidden></div>
<aside class="drawer" id="drawer" role="dialog" aria-modal="true" aria-label="Bằng chứng">
  <div class="dh"><div><div class="k">Bằng chứng</div><b id="d-path"></b><div class="meta" id="d-meta"></div></div>
  <button id="d-close" aria-label="Đóng">✕</button></div>
  <div class="db" id="d-body"></div>
  <div class="dnote">Đoạn mã chép từ kho tại thời điểm dựng bản này. Số dòng là của tệp thật.</div>
</aside>
<script id="d" type="application/json">{blob}</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script>{JS}</script>
"""
    out.write_text(doc, encoding="utf-8")


# ────────────────────────────────────────────────────────── VAULT

def build_vault(nodes: list[dict], out: Path) -> None:
    by_id = {n["id"]: n for n in nodes}
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.md"):
        f.unlink()
    for n in nodes:
        L = LAYERS[n["layer"]]
        fm = ["---", f'title: "{n["title"]}"', f"lop: {n['layer']}", f"lop_ten: {L['ten']}",
              f'tag_nguon: "{n["tag"]}"']
        if n.get("status"):
            fm.append(f"trang_thai: {STATUS[n['status']]}")
        fm += [f"tags: [clinicai, lop{n['layer']}-{L['key']}]", "---"]
        body = WL.sub(lambda m: f"[[{m.group(1)}|{by_id[m.group(1)]['title'].split(' — ')[0]}]]", n["body"])
        links = "\n".join(f"- [[{t}|{by_id[t]['title'].split(' — ')[0]}]]" for t in n["links"])
        back = "\n".join(f"- [[{t}|{by_id[t]['title'].split(' — ')[0]}]]" for t in n["backlinks"])
        md = ("\n".join(fm) + f"\n\n# {n['title']}\n\n> [!abstract] {n['summary']}\n\n{body}\n\n"
              f"## Nối tới\n{links}\n")
        if back:
            md += f"\n## Được dẫn từ\n{back}\n"
        (out / f"{n['id']}.md").write_text(md, encoding="utf-8")

    moc = ["---", 'title: "00 Bản đồ"', "tags: [clinicai, moc]", "---", "",
           "# Hệ thần kinh ClinicAI — bản đồ thiết kế", "",
           f"{len(nodes)} nút, 6 lớp. Mở **Graph view** (Ctrl/Cmd+G) — sáu lớp đã tô màu sẵn theo tag.",
           "", "Bản đọc dạng trang: `thiet-ke-he-thong.html` cùng thư mục.", "", "## Lộ trình đọc", ""]
    for p in READING_PATHS:
        moc.append(f"### {p['ten']}\n{p['mo_ta']}\n")
        moc += [f"{i+1}. [[{t}|{by_id[t]['title'].split(' — ')[0]}]]" for i, t in enumerate(p["nodes"])]
        moc.append("")
    for k, L in LAYERS.items():
        moc.append(f"## {L['so']} — {L['ten']}\n{L['phu']}\n")
        for n in nodes:
            if n["layer"] == k:
                s = f" · *{STATUS[n['status']]}*" if n.get("status") else ""
                moc.append(f"- [[{n['id']}|{n['title'].split(' — ')[0]}]]{s} — {n['summary']}")
        moc.append("")
    (out / "00 Bản đồ.md").write_text("\n".join(moc), encoding="utf-8")

    (out / "README.md").write_text(
        "# Vault Obsidian — Hệ thần kinh ClinicAI\n\n"
        "Mở thư mục này bằng Obsidian (**Open folder as vault**), bắt đầu từ `00 Bản đồ.md`.\n\n"
        "- Mỗi tệp là một nút; `[[…]]` là quan hệ thật của thiết kế.\n"
        "- **Graph view**: sáu lớp tô sẵn theo tag `#lop1-hien-phap` … `#lop6-lo-trinh`.\n"
        "- Lọc `trang_thai: Chưa có` trong frontmatter để thấy đúng các lỗ hổng.\n"
        "- `thiet-ke-he-thong.html` cùng thư mục là bản đọc có ngăn bằng chứng; hai bản sinh từ một nguồn.\n\n"
        "## Nguồn sinh\n\n"
        "Toàn bộ thư mục này, kể cả tệp README bạn đang đọc, **được sinh tự động** từ\n"
        "`_nguon/build.py`. Sửa nội dung ở `_nguon/nodes_*.py` rồi chạy `python3 _nguon/build.py`;\n"
        "sửa tay `.md` hay `.html` ở đây là mất trong lần dựng sau.\n\n"
        "Quy trình kiểm chứng một khẳng định trước khi viết: `docs/DANG-LAM.md` mục 9.\n"
        "Lần đính chính gần nhất: 06/09/2026 — vòng phản biện của Codex, sáu kết luận bị rút\n"
        "hoặc thu hẹp; xem trang *Nguồn & phạm vi* trong bản đọc.\n",
        encoding="utf-8")

    ob = out / ".obsidian"
    ob.mkdir(exist_ok=True)
    (ob / "graph.json").write_text(json.dumps({
        "collapse-filter": True, "search": "", "showTags": False, "showAttachments": False,
        "hideUnresolved": True, "showOrphans": True, "collapse-color-groups": False,
        "colorGroups": [{"query": f"tag:#lop{k}-{L['key']}",
                         "color": {"a": 1, "rgb": int(L["mau"].lstrip("#"), 16)}} for k, L in LAYERS.items()],
        "collapse-display": True, "showArrow": True, "textFadeMultiplier": -1,
        "nodeSizeMultiplier": 1.1, "lineSizeMultiplier": .8, "collapse-forces": True,
        "centerStrength": .45, "repelStrength": 12, "linkStrength": .9, "linkDistance": 200,
        "scale": .6, "close": False,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (ob / "app.json").write_text("{}", encoding="utf-8")


if __name__ == "__main__":
    nodes = load_nodes()
    cited: set[str] = set()
    for n in nodes:
        cited |= R.cited_files(n["body"])
    for s in SOURCES_REPO:
        cited |= R.cited_files(s)
    thieu = evidence.kiem_thieu(cited)
    if thieu:
        print("⚠ trích nhưng chưa map bằng chứng:", thieu)
    ev = evidence.thu_thap(cited)

    # Nguồn sống ở docs/thiet-ke-he-thong/_nguon/, bản đọc sinh ra ở thư mục cha.
    OUT = HERE.parent if HERE.name == "_nguon" else HERE
    out_html = OUT / "thiet-ke-he-thong.html"
    out_vault = OUT if HERE.name == "_nguon" else OUT / "vault"
    build_html(nodes, ev, out_html)
    build_vault(nodes, out_vault)
    words = sum(len(n["body"].split()) for n in nodes)
    print(f"OK · {len(nodes)} nút · {sum(len(n['links']) for n in nodes)} cạnh · ~{words:,} từ")
    print(f"   bằng chứng nhúng: {len(ev)} tệp · html {out_html.stat().st_size//1024} KB · vault {len(list(out_vault.glob('*.md')))} tệp")
    for k, L in LAYERS.items():
        ns = [n for n in nodes if n["layer"] == k]
        print(f"   {L['so']} {L['ten']:<26} {len(ns):>3} nút")
