"""Gộp mọi dữ liệu và dựng MỘT file HTML báo cáo đầy đủ.

  python3 -I build_final.py --prep     # sau merge1 + dedup: ghi out/new-final-input.json (để API viết đời thường)
  python3 -I build_final.py            # dựng HTML (cần plain-existing.json, plain-new.json)
"""
import html, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

SP = Path(__file__).resolve().parent
OUT = SP / "out"
AUD = Path("/Users/quangdang/Projects/Dr4Women-MacMini/.claude/worktrees/clever-thompson-45b9eb/docs/kiem-toan-2026-10-19")
DEST = AUD / "BAO-CAO-DAY-DU.html"
SHA8 = "956ba4f2"
CHANGED = set((AUD / "dot-2-doc-toan-bo" / "tep-doi-tu-25140241.txt").read_text().split())


def touched(f):
    ev = f.get("evidence_checked") or f.get("evidence") or []
    return any(e.get("path") in CHANGED for e in ev)

esc = lambda v: html.escape(str(v if v is not None else ""), quote=True)  # noqa: E731

GROUPS = {
    "A_danh_sach_cat": ("Danh sách bị cắt, lỗi hiện thành trống", "Mọi danh sách phải báo “còn nữa không”. Màn hình không được viết “không có” khi chưa đọc hết."),
    "B_bao_xanh_gia": ("Báo xong hoặc xanh khi chưa đúng", "“Xanh” chỉ sáng khi có bằng chứng (ví dụ đã thử khôi phục thật). “Chưa biết” là một trạng thái riêng."),
    "C_bam_lai_trung": ("Bấm lại, mất mạng gây việc trùng", "Mọi thao tác ghi mang mã chống lặp, giữ qua cả lần tải lại trang."),
    "D_ghi_de": ("Hai người cùng sửa, người sau ghi đè", "Mỗi bản ghi có số phiên bản; lưu khi đã bị người khác sửa thì báo, không ghi đè lặng lẽ."),
    "E_quyen_rong": ("Quyền rộng hơn cần thiết", "Một cổng kiểm quyền duy nhất theo từng bệnh nhân và cơ sở; mọi đường đọc, ghi, in, xuất đều đi qua."),
    "F_tien_kho": ("Tiền, giá, kho, lô lệch hoặc khó đối soát", "Mọi khoản tiền và tồn kho có sổ một chiều, có giá trị cũ–mới và đối soát độc lập."),
    "G_viec_roi": ("Việc không có chủ, dễ rơi", "Một bảng “việc cần làm” thống nhất: có người nhận, hạn, nhắc và leo thang; không tự sinh khi ai đó mở màn."),
    "H_sao_luu_van_hanh": ("Sao lưu, cảnh báo, vận hành", "Diễn tập khôi phục thật; giám sát từ bên ngoài máy chủ; tự dựng lại sau khi khởi động; gỡ script phá huỷ khỏi môi trường thật."),
    "I_dong_goi_ban": ("Dữ liệu riêng Dr4Women trong lõi, khó nhân bản", "Tách phần riêng của từng phòng khám thành gói cấu hình; có quy trình tạo phòng khám mới lặp lại được."),
    "J_luat_khong_canh": ("Luật có nhưng không canh, không để vết", "Mỗi luật an toàn có kiểm tra tự động chứng minh nó chặn được; mọi lần bỏ qua ghi người và lý do."),
    "K_khac": ("Khác", "Xử lý theo từng mục."),
}
SEV = {"HIGH": ("Cao", "bad"), "MEDIUM": ("Vừa", "warn"), "LOW": ("Thấp", "idle")}
GOALS = [
    ("Thực tế dễ nhìn thấy", r"reality|nhìn thấy|thực tế|dễ thấy"),
    ("Khoảng “chưa biết” ngắn hơn", r"unknown|chưa biết"),
    ("Mỗi việc có người chịu trách nhiệm", r"ownership|chịu trách nhiệm|chủ rõ|người nhận"),
    ("Phát hiện vấn đề sớm", r"sớm|phát hiện"),
    ("Ít gián đoạn, đúng lúc", r"gián đoạn|chữa cháy|hỏi nhau|đúng lúc"),
    ("Bệnh nhân ít chờ trong bất định", r"bệnh nhân|chờ"),
    ("Nhân viên làm việc bền vững", r"bền vững|nhân viên"),
    ("Quyết định dựa trên bằng chứng", r"bằng chứng|quyết định"),
    ("Lỗi lặp lại thành cải tiến hệ thống", r"lỗi lặp|cải tiến|học"),
    ("Đóng gọn, bán được", r"bán|mở rộng|đóng gói|tenant|nhân bản"),
]


def load(p):
    return json.loads(Path(p).read_text())


def prep():
    raw = load(OUT / "new-findings.json")
    cl = load(OUT / "dedup.json")
    byid = {f["tmp_id"]: f for f in raw}
    final, ext = [], load(OUT / "new-extensions.json")
    seen = set()
    for c in cl:
        keep = byid.get(c["keep"])
        if not keep:
            continue
        members = [keep] + [byid[i] for i in c.get("dups", []) if i in byid]
        seen |= {m["tmp_id"] for m in members}
        if c.get("dup_of_known"):
            for m in members:
                ext.append({"id": c["dup_of_known"], "detail": f"{m['title']}: {m.get('summary','')[:300]}", "chunk": m["chunk"]})
            continue
        f = dict(keep)
        f["severity"] = c.get("severity") or keep.get("severity")
        f["prefix"] = c.get("prefix") or "CLIN"
        f["merged_from"] = [m["tmp_id"] for m in members]
        seenp = {(e["path"], e["line"]) for e in f["evidence_checked"]}
        for m in members[1:]:
            for e in m["evidence_checked"]:
                if (e["path"], e["line"]) not in seenp:
                    f["evidence_checked"].append(e)
                    seenp.add((e["path"], e["line"]))
        final.append(f)
    for f in raw:  # id mà bước gộp bỏ sót: giữ riêng
        if f["tmp_id"] not in seen:
            g = dict(f)
            g["prefix"] = "CLIN"
            g["merged_from"] = [f["tmp_id"]]
            final.append(g)
    old = load(AUD / "PHAT-HIEN.json")
    mx = defaultdict(int)
    for x in old:
        p, n = x["id"].split("-")
        mx[p] = max(mx[p], int(n))
    for f in sorted(final, key=lambda z: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(z.get("severity"), 3), z["tmp_id"])):
        mx[f["prefix"]] += 1
        f["id"] = f"{f['prefix']}-{mx[f['prefix']]:03d}"
    (OUT / "new-final.json").write_text(json.dumps(final, ensure_ascii=False, indent=1))
    (OUT / "new-extensions-final.json").write_text(json.dumps(ext, ensure_ascii=False, indent=1))
    slim = [{"id": f["id"], "severity": f.get("severity"), "title": f.get("title"), "summary": f.get("summary"),
             "trigger": f.get("trigger"), "impact": f.get("impact")} for f in final]
    (OUT / "new-final-input.json").write_text(json.dumps(slim, ensure_ascii=False, indent=1))
    print(f"phát hiện mới sau gộp: {len(final)} (từ {len(raw)} thô); extensions {len(ext)}; ghi new-final-input.json")


# ───────────────────────────── Dựng HTML ─────────────────────────────
def card(f, plain, ext_by_id, is_new):
    pl = plain.get(f["id"], {})
    sev = f.get("severity", "MEDIUM")
    sv, sc = SEV.get(sev, ("Vừa", "warn"))
    nhom = pl.get("nhom", "K_khac")
    gname = GROUPS.get(nhom, GROUPS["K_khac"])[0]
    ten = pl.get("ten") or f.get("title")
    story = pl.get("chuyen_gi") or f.get("summary", "")[:260]
    impact = pl.get("anh_huong") or f.get("impact", "")
    fix = pl.get("cach_sua") or f.get("recommendation", "")[:240]
    ev = f.get("evidence_checked") or [dict(e, excerpt="") for e in f.get("evidence", [])]
    evh = "".join(
        f'<li><span class="path">{esc(e.get("path"))}:{esc(e.get("line"))}–{esc(e.get("end_line"))}</span> {esc(e.get("detail"))}'
        + (f'<pre>{esc(e.get("excerpt"))}</pre>' if e.get("excerpt") else "") + "</li>" for e in ev[:8])
    val = f.get("validation") or {}
    lim = f.get("limitations") or val.get("limitations") or ""
    exth = "".join(f"<li>{esc(x['detail'])} <span class='id'>({esc(x.get('chunk',''))})</span></li>" for x in ext_by_id.get(f["id"], [])[:6])
    GMAP = {"A_danh_sach_cat": [0], "B_bao_xanh_gia": [0, 1], "C_bam_lai_trung": [7], "D_ghi_de": [7], "F_tien_kho": [7], "G_viec_roi": [1, 2], "H_sao_luu_van_hanh": [3], "I_dong_goi_ban": [9], "J_luat_khong_canh": [3, 8]}
    _gs = {i for i, (_n, _rx) in enumerate(GOALS) if any(re.search(_rx, a, re.I) for a in (f.get("alignment") or []))} | set(GMAP.get(plain.get(f["id"], {}).get("nhom", ""), []))
    gi = ",".join(str(i) for i in sorted(_gs))
    badge = '<span class="pill idle">Mới đợt 2</span>' if is_new else ""
    tch = touched(f)
    cx = CODEX.get(f["id"])
    cxbox = ""
    if cx:
        lab, cls = VERD[cx["ket_luan"]]
        badge += f'<span class="pill {cls}">{esc(lab)}</span>'
        if f.get("codex_ha_muc"):
            badge += '<span class="pill idle">Đã hạ xuống mức vừa</span>'
        cxbox = (f'<p class="impact" style="border-left:3px solid var(--warn);padding-left:10px"><b>{esc(lab)}</b> (mức Codex đánh giá: {esc({"CAO":"cao","VUA":"vừa","THAP":"thấp","KHONG_AP_DUNG":"không áp dụng"}.get(cx["muc_do_dung"], cx["muc_do_dung"]))}). {esc(cx["ly_do"])}'
                 + (f' <b>Chốt chặn đã tìm thấy:</b> {esc(cx["chot_chan_da_tim_thay"])}' if cx.get("chot_chan_da_tim_thay") else "") + '</p>')
    pm = PXN.get(f["id"]) or PPN.get(f["id"])
    if f["id"] in PXN:
        badge += '<span class="pill warn">Prod đo được: có dấu hiệu thật</span>'
    elif f["id"] in PPN:
        badge += '<span class="pill ok">Prod đo được: giảm nhẹ hoặc chưa ảnh hưởng</span>'
    if f.get("prod_note"):
        badge += '<span class="pill idle">Chỉ thấy khi đo prod</span>'
    pnote = (f'<p class="impact" style="border-left:3px solid var(--accent);padding-left:10px"><b>Dữ kiện đo trên prod:</b> {esc(pm["y_nghia"])} <span class="id">({esc(pm["bang_chung"][:160])})</span></p>' if pm else (f'<p class="impact" style="border-left:3px solid var(--accent);padding-left:10px"><b>Dữ kiện đo trên prod:</b> <span class="id">{esc(f["prod_note"][:200])}</span></p>' if f.get("prod_note") else ""))
    lvl = {"reproduced_local": "Đã tái hiện trên máy thử", "design_gap": "Khoảng trống thiết kế, cần quyết định"}.get(f.get("evidence_level"), "Đọc code, chưa chạy thật")
    return f'''<article class="finding" id="{esc(f["id"])}" data-sev="{sev}" data-g="{esc(nhom)}" data-goal="{gi}" data-new="{int(is_new)}" data-p="{int(tch)}">
<header><span class="pill {sc}">{sv}</span><span class="id">{esc(f["id"])}</span>{badge}<span class="gtag">{esc(gname)}</span></header>
<h3>{esc(ten)}</h3>
<p>{esc(story)}</p>
<p class="impact"><b>Hậu quả có thể có:</b> {esc(impact)}</p>
{cxbox}{pnote}<p class="fixline"><b>Hướng sửa:</b> {esc(fix)}</p>
<details><summary>Chi tiết kỹ thuật và bằng chứng</summary>
<p class="small"><b>Độ chắc:</b> {esc(lvl)}. <b>Tên kỹ thuật:</b> {esc(f.get("title"))}</p>
<p class="small"><b>Tóm tắt kỹ thuật:</b> {esc(f.get("summary"))}</p>
<p class="small"><b>Điều kiện xảy ra:</b> {esc(f.get("trigger"))}</p>
<p class="small"><b>Giới hạn:</b> {esc(lim)}</p>
<p class="small"><b>Đề xuất đầy đủ:</b> {esc(f.get("recommendation"))}</p>
<p class="small"><b>Kiểm nghiệm khi sửa:</b> {esc(f.get("acceptance"))}</p>
<h4>Dẫn chứng trong code (bản {SHA8})</h4><ul class="ev">{evh}</ul>
{('<h4>Bằng chứng bổ sung từ đợt đọc thứ hai</h4><ul class="ev">' + exth + '</ul>') if exth else ''}
</details></article>'''


import glob as _glob
CODEX = {}
for _f in sorted(_glob.glob(str(AUD / "codex-tung-phan" / "KET-QUA-CODEX-*.json"))):
    for _r in json.loads(Path(_f).read_text()):
        CODEX[_r["id"]] = _r
VERD = {"DUNG": ("Codex xác minh: đúng", "bad"), "DUNG_MOT_PHAN": ("Codex xác minh: đúng một phần", "warn"), "BAC_BO": ("Codex xác minh: bị bác bỏ", "ok"), "KHONG_XAC_DINH": ("Codex xác minh: chưa xác định", "idle")}
OVERRIDE = {"INF-029": {"ten": "Worker bị treo không được tự khởi động lại", "chuyen_gi": "Các dịch vụ đã đặt tự bật lại sau khi Docker hoặc máy chủ khởi động lại (đã đo trên prod). Phần còn thiếu: container chỉ bị treo (unhealthy) thì không ai khởi động lại, và database nằm ở nhóm khác nên không có thứ tự bật.", "anh_huong": "Một worker treo có thể làm việc nền đứng im mà không ai biết cho tới khi có người kiểm tra.", "nhom": "H_sao_luu_van_hanh", "cach_sua": "Thêm bước tự khởi động lại container unhealthy và báo ra ngoài khi xảy ra."}}
PROD = load(OUT / "prod-analysis.json") if (OUT / "prod-analysis.json").exists() else {}
PXN = {m["id"]: m for m in PROD.get("xac_nhan", [])}
PPN = {m["id"]: m for m in PROD.get("phu_nhan_hoac_giam_nhe", [])}


def prod_findings():
    out, plain = [], {}
    for i, m in enumerate(PROD.get("quan_sat_moi", []), 1):
        fid = f"PRD-{i:03d}"
        g = "E_quyen_rong" if "RLS" in m["ten"] or "khóa dữ liệu theo hàng" in m["ten"] or "khóa" in m["ten"] and "Zalo" not in m["ten"] else "H_sao_luu_van_hanh"
        out.append({"id": fid, "title": m["ten"], "severity": m["muc"], "evidence_level": "confirmed_static", "summary": m["chuyen_gi"],
                    "trigger": "Đo trực tiếp trên VPS prod ngày 20/10/2026 bằng lệnh chỉ đọc.", "impact": m["chuyen_gi"],
                    "recommendation": m["cach_sua"], "acceptance": "Đo lại bằng cùng lệnh chỉ đọc sau khi sửa.", "alignment": m.get("muc_tieu", []),
                    "evidence_checked": [], "evidence": [], "limitations": "Chỉ là dữ kiện đo tại một thời điểm; nguyên nhân chưa được xác nhận.",
                    "prod_note": m["bang_chung"]})
        plain[fid] = {"ten": m["ten"], "chuyen_gi": m["chuyen_gi"], "anh_huong": "", "nhom": g, "cach_sua": m["cach_sua"]}
    return out, plain


def main():
    old = load(AUD / "PHAT-HIEN.json")
    pe = load(OUT / "plain-existing.json") if (OUT / "plain-existing.json").exists() else {}
    new = load(OUT / "new-final.json") if (OUT / "new-final.json").exists() else []
    pn = load(OUT / "plain-new.json") if (OUT / "plain-new.json").exists() else {}
    ext = load(OUT / "new-extensions-final.json") if (OUT / "new-extensions-final.json").exists() else []
    held = load(OUT / "new-held.json") if (OUT / "new-held.json").exists() else []
    goodp = load(OUT / "good-curated.json") if (OUT / "good-curated.json").exists() else []
    cov = load(OUT / "new-coverage.json") if (OUT / "new-coverage.json").exists() else []
    ext_by = defaultdict(list)
    for x in ext:
        ext_by[x["id"]].append(x)
    pf, ppl = prod_findings()
    plain = {**pe, **pn, **ppl}
    new = new + pf
    allf = [(f, False) for f in old] + [(f, True) for f in new]
    for f, _ in allf:
        c = CODEX.get(f["id"])
        if c and c["muc_do_dung"] in ("VUA", "KHONG_AP_DUNG") and f.get("severity") == "HIGH":
            f["severity"] = "MEDIUM"; f["codex_ha_muc"] = True
    for k, v in OVERRIDE.items():
        if k in plain: plain[k] = {**plain[k], **v}
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    allf.sort(key=lambda t: (order.get(t[0].get("severity"), 3), t[0]["id"]))
    sev = Counter(f.get("severity") for f, _ in allf)
    grp = Counter(plain.get(f["id"], {}).get("nhom", "K_khac") for f, _ in allf)
    n_ext = len(ext)
    total = len(allf)
    # đếm theo mục tiêu
    goal_n = []
    for name, rx in GOALS:
        n = sum(1 for f, _ in allf if any(re.search(rx, a, re.I) for a in (f.get("alignment") or [])))
        goal_n.append((name, n))
    pyes = sum(1 for f, _ in allf if touched(f)); pno = total - pyes
    hyes = sum(1 for f, _ in allf if touched(f) and f.get("severity") == "HIGH"); hno = sev["HIGH"] - hyes
    high = [(f, plain.get(f["id"], {})) for f, _ in allf if f.get("severity") == "HIGH"]
    high_rows = "".join(f'<li><span class="id">{esc(f["id"])}</span> <b>{esc(p.get("ten") or f["title"])}</b>. {esc(p.get("chuyen_gi") or "")}</li>' for f, p in high)
    grows = "".join(
        f'<tr><td><b>{esc(GROUPS[k][0])}</b></td><td class="num">{grp.get(k,0)}</td><td>{esc(GROUPS[k][1])}</td></tr>'
        for k in GROUPS if grp.get(k, 0) > 0)
    gl = "".join(f'<tr><td>{esc(n)}</td><td class="num">{c}</td></tr>' for n, c in goal_n)
    cards = "\n".join(card(f, plain, ext_by, is_new) for f, is_new in allf)
    opts = "".join(f'<option value="{k}">{esc(v[0])} ({grp.get(k,0)})</option>' for k, v in GROUPS.items() if grp.get(k, 0))
    heldh = "".join(f"<li><b>{esc(h.get('title'))}</b>: {esc(h.get('reason'))}</li>" for h in held[:40])
    goodh = "".join(f"<li><b>{esc(g.get('title'))}</b>: {esc(g.get('detail'))}</li>" for g in goodp[:20])
    covn = Counter()
    for c in cov:
        covn["đưa vào đọc"] += 1
        if c.get("full_read"):
            covn["đọc trọn"] += 1
    strengths = "".join(f"<li>{esc(s)}</li>" for s in PROD.get("khoe_manh", []))
    prod_goal = {m["ten"]: m for m in PROD.get("muc_tieu", [])}
    prows = "".join(f"<tr><td>{esc(m['ten'])}</td><td><span class='pill {'bad' if m['trang_thai']=='Chưa sẵn sàng' else ('ok' if m['trang_thai']=='Có nền' else ('idle' if m['trang_thai']=='Chưa đo được' else 'warn'))}'>{esc(m['trang_thai'])}</span></td><td>{esc(m['thuc_te_prod'])}</td></tr>" for m in PROD.get("muc_tieu", []))
    xn_n, pn_n, mo_n = len(PXN), len(PPN), len(pf)
    doc = TEMPLATE
    names = [g[0] for g in GOALS]
    idx = [0]
    def inject(mo):
        i = idx[0]; idx[0] += 1
        key = list(prod_goal.keys())[i] if i < len(prod_goal) else None
        if not key: return mo.group(0)
        m = prod_goal[key]
        return f'<p class="small" style="border-left:3px solid var(--accent);padding-left:10px"><b>Thực tế đo trên prod ({esc(m["trang_thai"])}):</b> {esc(m["thuc_te_prod"])}</p>' + mo.group(0)
    doc = re.sub(r'<div class="prop">', inject, doc)
    repl = {
        "@@TOTAL@@": str(total), "@@HIGH@@": str(sev["HIGH"]), "@@MED@@": str(sev["MEDIUM"]), "@@LOW@@": str(sev["LOW"]),
        "@@NEW@@": str(len(new)), "@@OLD@@": str(len(old)), "@@EXT@@": str(n_ext), "@@HIGHLIST@@": high_rows,
        "@@GROUPROWS@@": grows, "@@GOALROWS@@": gl, "@@CARDS@@": cards, "@@GOPTS@@": opts, "@@GOALOPTS@@": "".join(f'<option value="{i}">{esc(n)}</option>' for i, (n, _r) in enumerate(GOALS)), "@@HELD@@": heldh,
        "@@GOOD@@": goodh, "@@PYES@@": str(pyes), "@@PNO@@": str(pno), "@@HYES@@": str(hyes), "@@HNO@@": str(hno), "@@CXD@@": str(sum(1 for r in CODEX.values() if r["ket_luan"]=="DUNG")), "@@CXM@@": str(sum(1 for r in CODEX.values() if r["ket_luan"]=="DUNG_MOT_PHAN")), "@@CXB@@": str(sum(1 for r in CODEX.values() if r["ket_luan"]=="BAC_BO")), "@@CXK@@": str(sum(1 for r in CODEX.values() if r["ket_luan"]=="KHONG_XAC_DINH")), "@@CXH@@": str(sum(1 for f,_ in allf if f.get("codex_ha_muc"))), "@@PRODROWS@@": prows, "@@STRENGTHS@@": strengths, "@@XN@@": str(xn_n), "@@PN@@": str(pn_n), "@@MO@@": str(mo_n), "@@COVN@@": str(covn["đưa vào đọc"]), "@@COVFULL@@": str(covn["đọc trọn"]), "@@SHA8@@": SHA8,
    }
    for k, v in repl.items():
        doc = doc.replace(k, v)
    DEST.write_text(doc, encoding="utf-8")
    print(f"đã ghi {DEST} ({DEST.stat().st_size/1e6:.1f} MB); {total} phát hiện ({len(old)} cũ + {len(new)} mới) {dict(sev)}")


TEMPLATE = (SP / "template.html").read_text() if (SP / "template.html").exists() else "@@CARDS@@"

if __name__ == "__main__":
    prep() if "--prep" in sys.argv else main()
