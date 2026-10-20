"""Integrate Round 52: default exam-fee reconciliation after in-chart service switch."""
import hashlib, json, subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = Path("/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini")
SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"
EXTS = {".py",".pyi",".ts",".tsx",".js",".jsx",".mjs",".cjs",".sql",".sh",".bash",".go",".rs",".java",".kt",".css",".html"}

def load(name): return json.loads((ROOT / name).read_text())
def save(name, data): (ROOT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
def proof(path, start, end, detail):
    raw = subprocess.check_output(["git","show",f"{SHA}:{path}"],cwd=REPO)
    lines = raw.decode().splitlines()
    if not 1 <= start <= end <= len(lines): raise ValueError(f"Invalid pinned range {path}:{start}-{end}")
    return {"path":path,"line":start,"end_line":end,"sha256":hashlib.sha256(raw).hexdigest(),
            "excerpt":"\n".join(f"{n}: {lines[n-1]}" for n in range(start,end+1)),
            "detail":detail,"lines":len(lines)}

def main():
    findings=load("PHAT-HIEN.json")
    if any(x["id"]=="CLIN-060" for x in findings): raise ValueError("CLIN-060 already exists")
    ev_specs=[
      ("src/clinicai/services/doi_dich_vu_kham.py",71,87,"Chart-mode policy permits OPEN/IN_PROGRESS visits even when payment, form, consultation or child-service flags exist."),
      ("src/clinicai/services/doi_dich_vu_kham.py",155,188,"The normal menu path recognizes a payment for the default exam source; this does not prevent the in-chart path."),
      ("src/clinicai/services/booking_service.py",1333,1461,"The chart switch locks appointment and visit, updates both service_type_id values and emits events; this block makes no payment adjustment."),
      ("src/clinicai/services/bill_service.py",292,337,"With no explicit child exam service, current service type gia_mac_dinh becomes fallback with source_id default."),
      ("src/clinicai/services/bill_service.py",387,430,"Fallback bill source is exam-{visit_id}, without service type or fee snapshot."),
      ("src/clinicai/services/bill_service.py",769,833,"Outstanding exam amount is computed from current visit/appointment service type and gia_mac_dinh."),
      ("src/clinicai/services/bill_service.py",853,907,"Covered exam sources are found by source_id and payment-cycle state; the old line total is not compared to the newly computed amount."),
      ("src/clinicai/services/bill_service.py",925,981,"Covered source IDs are removed from the outstanding invoice without a delta adjustment."),
    ]
    ev=[proof(*s) for s in ev_specs]
    f={
      "id":"CLIN-060","title":"Đổi dịch vụ trong hồ sơ có thể làm phí mặc định mới bị coi là đã thu đủ",
      "severity":"MEDIUM","evidence_level":"confirmed_static","category":"billing_obligation_reconciliation",
      "summary":"Đổi dịch vụ trong hồ sơ cho phép lượt OPEN/IN_PROGRESS dù đã thu tiền. Khi chưa tick dịch vụ khám con, hóa đơn dựng phí mặc định từ service_type hiện tại và gia_mac_dinh mới, nhưng mã nghĩa vụ vẫn là exam-{visit_id} cho mọi loại khám. hoa_don_con_no loại mã đó khỏi khoản còn phải thu nếu payment line cùng nguồn còn hiệu lực; không so line_total cũ với mức phí mới và không tạo khoản điều chỉnh. Đổi từ phí mặc định thấp sang cao sau khi thu có thể làm phần chênh biến mất khỏi hóa đơn còn nợ; đổi xuống thấp có thể để lại tiền thu vượt mà không tạo khoản hoàn/ghi có tự động. Suy luận tĩnh, chưa tái hiện bằng DB.",
      "trigger":"Một lượt OPEN/IN_PROGRESS không có luot_phi_kham đang sống đã thu phí mặc định loại A; nhân viên đổi trong hồ sơ sang loại B có gia_mac_dinh khác.",
      "impact":"Hóa đơn còn nợ có thể báo hết nợ dù mức mới cao hơn khoản đã thu, hoặc không thể hiện tiền thừa khi mức mới thấp hơn. Nhân viên phải tự đối chiếu/điều chỉnh ngoài hệ thống. Không có bằng chứng đã xảy ra ở production.",
      "evidence":[],"validation":{
        "method":"read_only_exact_main_static_trace_of_chart_switch_and_outstanding_exam_obligation","command":None,
        "result":"Đối chiếu policy cho phép đổi sau khi thu, transaction cập nhật service_type_id, cách tính phí mặc định từ service_type hiện tại, source exam-{visit_id}, và filter khoản đã phủ. Unit test xác nhận da_thu_tien_kham vẫn cho phép khi trong_ho_so=True; DB chart-switch test giữ phiếu/tick nhưng không dựng ca đã thu phí mặc định rồi đổi sang mức khác. Tests were read-not-run.",
        "limitations":"Static exact-main inference only. Không chạy tests, DB, API, payment provider hay production. Cần synthetic DB test để kiểm mức chênh; không kết luận đã có thiếu thu hoặc hoàn sai ở production."
      },
      "recommendation":"Chốt quy tắc giá khi đổi dịch vụ sau khi đã thu. Nếu đổi loại làm đổi nghĩa vụ, giữ payment line và nghĩa vụ cũ dạng snapshot bất biến, rồi ghi debit/credit adjustment riêng cho phần chênh, liên kết hai service_type và lần đổi. Nếu chính sách giữ giá lúc đầu, hóa đơn phải tiếp tục dùng snapshot cũ thay vì tính lại từ service_type hiện tại. Không dùng một source_id chung để suy rằng hai mức nghĩa vụ khác nhau đã được phủ đủ.",
      "acceptance":"Trên disposable DB synthetic: lượt chưa tick dịch vụ con có phí mặc định A 100000đ đã thu đủ; đổi sang B 150000đ thì hóa đơn thể hiện đúng adjustment 50000đ (hoặc giữ phí cũ nếu sản phẩm chốt snapshot); đổi tiếp sang C 50000đ thì thể hiện ghi có/hoàn 50000đ theo chính sách. Payment line gốc bất biến; không mất chênh, không thu lại khoản cũ, lịch sử đổi và điều chỉnh truy vết được.",
      "alignment":["Số còn phải thu và tiền thừa nhìn thấy ngay sau khi đổi dịch vụ","Nhân viên không phải nhớ phí trước/sau hoặc hỏi nhau để đối soát","Điều chỉnh dựa trên payment snapshot và lịch sử đổi có bằng chứng"],
      "related_tests":[
        "src/tests/unit/test_doi_dich_vu_kham.py:56-68 — read-not-run; đã thu tiền vẫn đổi được trong hồ sơ, không kiểm chênh phí.",
        "src/tests/services/test_ho_so_kham_db.py:70-145 — read-not-run; giữ phiếu/tick và đổi ngược loại, không payment/default-fee adjustment.",
        "src/tests/services/test_doi_dich_vu_kham_db.py — read-not-run; đổi lịch, xếp hàng và điều kiện chặn; không có hai mức phí mặc định đã thu."
      ],
      "source_hashes":{},"status":"open","reference_version":"pinned_main",
      "main_validation":{"sha":SHA,"status":"still_present_on_main","note":"Chart-switch permission allows paid visits. The fee projection uses current service type while the default source remains stable per visit and covered sources are removed without delta adjustment.","evidence":[]},
      "related_findings":[]
    }
    for x in ev:
      f["evidence"].append({k:x[k] for k in ("path","line","end_line","detail")})
      f["main_validation"]["evidence"].append({k:x[k] for k in ("path","line","end_line","sha256","excerpt")})
      f["source_hashes"][x["path"]]=x["sha256"]
    findings.append(f); save("PHAT-HIEN.json",findings)

    specs=[
      ("src/clinicai/services/doi_dich_vu_kham.py",58,116,"Targeted read: chart-mode exception permits previously paid visits."),
      ("src/clinicai/services/doi_dich_vu_kham.py",155,188,"Targeted read: paid-source state lookup used by non-chart flow."),
      ("src/clinicai/services/ho_so_dich_vu.py",1,299,"Full-file read: chart service projection/history/switch wrapper and treatment-order creation."),
      ("src/clinicai/services/booking_service.py",1325,1461,"Targeted read: chart-switch transaction, row updates and events."),
      ("src/clinicai/services/bill_service.py",292,337,"Targeted read: fallback exam fee and default source identity."),
      ("src/clinicai/services/bill_service.py",387,430,"Targeted read: bill-line source ID derivation."),
      ("src/clinicai/services/bill_service.py",769,833,"Targeted read: current service-type fee projection."),
      ("src/clinicai/services/bill_service.py",853,907,"Targeted read: covered-source identification."),
      ("src/clinicai/services/bill_service.py",925,981,"Targeted read: covered-source removal from invoice."),
      ("src/tests/services/test_ho_so_kham_db.py",1,225,"Full-file read: chart switch and treatment-order DB cases; no paid default-fee delta case; tests read-not-run."),
      ("src/tests/services/test_doi_dich_vu_kham_db.py",1,331,"Full-file read: menu switch, queue and blocked-state DB cases; tests read-not-run."),
      ("src/tests/unit/test_doi_dich_vu_kham.py",1,77,"Full-file read: state cases including paid-in-chart exception; tests read-not-run.")
    ]
    by={}
    for s in specs:
      x=proof(*s); row=by.setdefault(x["path"],{"path":x["path"],"sha256":x["sha256"],"lines":x["lines"],"read_ranges":[],"full_read":False,"outcomes":[]})
      rng={"start":x["line"],"end":x["end_line"]}
      if rng not in row["read_ranges"]: row["read_ranges"].append(rng)
      row["full_read"] |= x["line"]==1 and x["end_line"]==x["lines"]
      row["outcomes"].append(x["detail"])
    cov=[]
    for row in by.values():
      row["read_ranges"].sort(key=lambda z:(z["start"],z["end"]))
      row["outcome"]=" ".join(row.pop("outcomes")); cov.append(row)
    save("blocks/round52.coverage.json",{
      "schema_version":1,"round":52,"report_version":"v0.75","snapshot_sha":SHA,
      "mode":"read_only_exact_main_scoped_semantic_review",
      "scope":["in-chart service switch permission and transactional write","default exam-fee projection, payment source identity and outstanding-bill coverage","current chart-switch unit and database tests"],
      "method":"Immutable pinned Git blobs via git show. Ranges line-checked and file SHA-256 checked. Tests read-not-run. No ClinicAI application/runtime/API/DB/provider/VPS/production/secrets/PHI accessed.",
      "result":{"new_findings":["CLIN-060"],"extended_findings":[],"deduplicated":["CLIN-010 is appointment/visit service-type divergence via reschedule after check-in; CLIN-060 is billing identity after the dedicated chart switch updates both rows.","Applies to default exam-fee fallback without active child exam selection; explicit child-service sources have their own service_price IDs."],"held_candidates":["Product policy must decide whether post-payment change retains original fee snapshot or records a debit/credit delta. Existing comments say differences follow surplus/debt rules; synthetic payment-level test needed."],"full_source_audit_complete":False},
      "full_files":[x for x in cov if x["full_read"]],"targeted_traces":[x for x in cov if not x["full_read"]],
      "reviewer_note":"Scoped static trace of one financial edge case. No payment DB state created and no financial outcome reproduced."
    })
    (ROOT/"blocks/round52.md").write_text(f"""# Round 52 — phí khám mặc định sau khi đổi dịch vụ trong hồ sơ

Source SHA {SHA}. Review used immutable Git blobs via git show. Tests read only and not run. No ClinicAI application, API, DB, provider, VPS, production, secrets or PHI was accessed.

## Finding

- Added CLIN-060 MEDIUM: the in-chart switch permits a visit with a prior exam payment. When no child exam service is selected, billing derives the fallback from the current service type gia_mac_dinh, but emits stable source exam-{{visit_id}}. The outstanding-bill path marks that source covered by an existing paid/pending line and removes it without comparing the old snapshot amount to the newly computed fee or recording a debit/credit adjustment.
- Changing from a lower default fee to a higher one can hide the difference from the receivable; changing to a lower one can leave an overpayment without a corresponding credit/refund adjustment. Static inference only; no payment result or production occurrence was reproduced.
- CLIN-010 concerns appointment/visit type divergence via reschedule after check-in. CLIN-060 follows the dedicated chart path that updates both rows. Explicit child exam sources are outside this finding.

## Recommendation and validation

Define fee policy after a paid visit changes service type. Keep original payment and fee snapshot immutable; if the new type changes the obligation, write a traceable debit/credit adjustment for the difference. If policy retains the original fee, continue billing from that snapshot. A synthetic DB test should collect 100,000đ, switch to a 150,000đ default, then to 50,000đ and assert exact receivable/credit under the chosen rule, with no duplicate collection and complete history.

Exact source ranges, hashes and read coverage are in blocks/round52.coverage.json and PHAT-HIEN.json. Tests read-not-run. Full source audit remains incomplete.
""")

    manifest=load("MAIN-PHAM-VI.json")
    for r in manifest["files"]:
      x=by.get(r["path"])
      if not x: continue
      if r.get("sha256") and r["sha256"]!=x["sha256"]: raise ValueError(f"Manifest SHA mismatch for {r['path']}")
      if x["full_read"]: r["status"]="read"; r["full_file_read"]=True
      elif r["status"] in {"scanned","inventoried"}: r["status"]="traced"
      ranges=", ".join(f"{q['start']}–{q['end']}" for q in x["read_ranges"])
      note=f"Round 52 exact-main {ranges}; see blocks/round52.coverage.json."
      if "Round 52 exact-main" not in r.get("method",""): r["method"]=(r.get("method","")+" | "+note).strip(" |")
      r["round52_note"]=x["outcome"]
    manifest["last_updated_round"]=52; save("MAIN-PHAM-VI.json",manifest)
    mc=Counter(x["status"] for x in manifest["files"])
    cf=[x for x in manifest["files"] if Path(x["path"]).suffix.lower() in EXTS]; cc=Counter(x["status"] for x in cf)
    fc=Counter(x["main_validation"]["status"] for x in findings); sc=Counter(x["severity"] for x in findings); ec=Counter(x["evidence_level"] for x in findings)
    st=load("STATE.json")
    st.update({"updated_at":"2026-10-20","status":"in_progress","report_version":"v0.75","phase":"round52_v075_exam_fee_reconciliation_audit_open",
      "report_round_summary":"Round 52 adds CLIN-060: after a paid in-chart switch, a changed default exam fee may reuse the same covered source ID without a delta adjustment; static inference only.",
      "next_action":"Continue exact-main review of unread/structurally scanned code, prioritizing payment/refund/reconciliation invariants, remaining service modules, clinical transitions, migrations/restore, retry receipts, freshness and worker recovery. Keep full_source_audit_complete=false until scope and validation gaps are actually closed.",
      "report_status":"Round 52 evidence integrated; v0.75 report-only QA and portable package refresh pending; full source audit remains incomplete.","full_source_audit_complete":False,
      "round52":{"status":"integrated_static_review_report_qa_pending_audit_open","notes":"blocks/round52.md","coverage":"blocks/round52.coverage.json","new_findings":["CLIN-060"],"extended_findings":[],"tests":"Chart-switch tests read-not-run; no payment/default-fee delta scenario executed.","runtime":"No ClinicAI app/API/DB/provider/VPS/production/secrets/PHI access.","full_source_audit_complete":False,"targeted_paths":len(cov),"full_file_reads":sum(x["full_read"] for x in cov)}})
    st["summary"]["findings"]=len(findings); st["summary"]["severity"]={k:sc[k] for k in ("HIGH","MEDIUM","LOW")}; st["summary"]["evidence_levels"]=dict(ec)
    st["summary"]["main_status"]={k:fc[k] for k in ("still_present_on_main","partially_addressed_on_main","addressed_on_main")}
    st["summary"]["main_files"]=len(manifest["files"]); st["summary"]["main_partial_traces"]=mc["traced"]
    st["summary"]["main_coverage"]={k:mc[k] for k in ("inventoried","traced","read","scanned","excluded")}
    st["summary"]["code_like_source_files"]={"definition":"Pinned-tree code/web/sql/shell suffixes; includes app, tests, tooling and styles.","total":len(cf),"coverage":{k:cc[k] for k in ("inventoried","traced","scanned","read")}}
    st["limits"][0]=f"Full source audit incomplete: {mc['inventoried']} inventoried, {mc['traced']} partially traced, {mc['scanned']} scanned and {mc['excluded']} excluded paths out of {len(manifest['files'])}. Path state is not behavioral coverage."
    st["limits"][1]=f"Code-like suffix group includes runtime, tests, tooling and styles; path ledger: {cc['read']} read, {cc['traced']} partially traced, {cc['scanned']} scanned, {cc['inventoried']} inventoried and {cc['excluded']} excluded out of {len(cf)}. This is not a percent-complete or correctness score."
    st["artifacts"]["integration_script"]="Round52 integrated; v0.75 report-only QA and package refresh pending."
    st["artifacts"]["qa"]="Pending v0.75 report-only validator and browser check; application behavior not validated."
    st["package"].update({"status":"pending","file_count":None,"integrity":"Pending v0.75 package rebuild after report QA."})
    st["portable_bundle_status"]="Pending final v0.75 audit-only package rebuild and verification."
    st["report_html_sha256"]=None; save("STATE.json",st)
    hand="Round 52 adds CLIN-060: a paid default exam obligation may retain one source ID after an in-chart switch changes the current default fee, without a delta adjustment. Static inference only; tests read-not-run."
    (ROOT/"TIEP-TUC.md").write_text(f"""# CURRENT HANDOFF — v0.75, Round 52

Evidence source: immutable Git SHA {SHA} in {REPO}. Read source only with git show <SHA>:<path>; do not use working-tree WIP as evidence. Only edit audit artifacts here. Do not run ClinicAI runtime/API/DB/provider/VPS/production or inspect secrets/PHI.

{hand} Evidence and test limits are in blocks/round52.md, blocks/round52.coverage.json, PHAT-HIEN.json and MAIN-PHAM-VI.json.

Full source audit remains incomplete. Path counters are inventory states, not semantic coverage. v0.75 report-only QA and audit-only ZIP refresh are pending. Resume from BAT-DAU-TU-DAY.md and STATE.json.
""")
    (ROOT/"BAT-DAU-TU-DAY.md").write_text(f"""# Bắt đầu từ đây — checkpoint v0.75, Round 52

Đọc TIEP-TUC.md, STATE.json, NHAT-KY.md, MAIN-PHAM-VI.json, PHAT-HIEN.json, blocks/round52.md và blocks/round52.coverage.json. Source chỉ từ SHA {SHA} qua git show trong worktree audit.

{hand} Không chạy runtime/DB; tests read-not-run. v0.75 report/package QA pending.

Full source audit chưa hoàn tất. Path counters không phải phần trăm đã hiểu hành vi; chỉ sửa audit artifacts. Tiếp tục theo STATE.json.next_action.
""")
    with (ROOT/"NHAT-KY.md").open("a") as out:
      out.write(f"""

## Round 52 — 20/10/2026, v0.75 integration

Static exact-main review at SHA {SHA}. Added CLIN-060: in-chart switch is allowed after fee payment; default fee recalculates from current service type while bill source remains stable per visit, and covered sources are removed without a delta adjustment. No payment/DB/runtime/production outcome reproduced. Tests read-not-run. Exact ranges in blocks/round52.coverage.json; full source audit incomplete. Report-only QA/package refresh pending.
""")
    print(f"Integrated Round 52: {len(findings)} findings; {len(cov)} path coverage records; full audit remains open")

if __name__=="__main__": main()
