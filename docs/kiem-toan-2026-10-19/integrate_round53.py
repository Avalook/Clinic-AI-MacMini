"""Integrate Round 53: visit_gate_rule (only_when_other_staff) lead from CLAUDE-HANDOFF."""
import hashlib, json, subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = Path("/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini")
SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"
EXTS = {".py",".pyi",".ts",".tsx",".js",".jsx",".mjs",".cjs",".sql",".sh",".bash",".go",".rs",".java",".kt",".css",".html"}
FID = "OPS-014"


def load(name): return json.loads((ROOT / name).read_text())
def save(name, data): (ROOT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def proof(path, start, end, detail):
    raw = subprocess.check_output(["git", "show", f"{SHA}:{path}"], cwd=REPO)
    lines = raw.decode().splitlines()
    if end is None:
        end = len(lines)
    if not 1 <= start <= end <= len(lines):
        raise ValueError(f"Invalid pinned range {path}:{start}-{end}")
    return {"path": path, "line": start, "end_line": end, "sha256": hashlib.sha256(raw).hexdigest(),
            "excerpt": "\n".join(f"{n}: {lines[n-1]}" for n in range(start, end + 1)),
            "detail": detail, "lines": len(lines)}


def main():
    findings = load("PHAT-HIEN.json")
    if any(x["id"] == FID for x in findings):
        raise ValueError(f"{FID} already exists")

    GATE = "src/clinicai/services/gate_rule_service.py"
    DISP = "src/clinicai/services/dispatch_service.py"
    ROUTER = "src/clinicai/api/v1/routers/dispatch.py"
    ev_specs = [
        (GATE, 96, 114, "blocks(): với only_when_other_staff bật mà target_staff_id là None thì trả False (không chặn); comment hứa 'chốt sẽ xét lại khi đã có người'."),
        (GATE, 218, 244, "enforce() gọi first_block một lần với target_staff_id do người gọi truyền; không có bước xét lại sau khi có người."),
        (ROUTER, 143, 165, "MoveRequest không có trường target_staff_id; endpoint /dispatch/move không truyền trường này xuống service."),
        (ROUTER, 178, 192, "/dispatch/transfer-room cũng không truyền target_staff_id."),
        (DISP, 462, 497, "move() có target_staff_id mặc định None và truyền vào gate_enforce; nhánh luồng mới bị từ chối ngay trước đó."),
        ("src/dashboard/app/api/dispatch/[action]/route.ts", 12, 20, "BFF chỉ chuyển nguyên body xuống backend; không bổ sung người đích."),
        ("supabase/migrations/20260805000006_gate_rule_any_node.sql", 79, 98, "Luật seed duy nhất 'BS Thành khám trước' đặt only_when_other_staff = TRUE; seed ghép theo full_name cố định."),
        ("supabase/migrations/20260805000006_gate_rule_any_node.sql", 126, 138, "Khối verify bắt buộc only_when_other_staff phải TRUE; không tìm thấy nhân sự thì chỉ NOTICE và dừng."),
        ("supabase/migrations/20260808000003_luat_bac_si_bat_buoc.sql", 13, 24, "Luật mới luat_bac_si_bat_buoc được thiết kế chạy LÚC ĐẶT LỊCH và cố ý không dùng lại visit_gate_rule."),
        ("src/clinicai/services/booking_service.py", 636, 651, "Thi hành luật bác sĩ bắt buộc lúc đặt lịch; không phải lúc chuyển phòng/chỉ định sau khi khách đã đến."),
        ("src/clinicai/services/luot_kham_service.py", 3258, 3283, "dispatch_order (luồng mới) xếp phòng qua rules.dispatch_block với các tham số trạng thái chỉ định; không có tham số người gác cổng bắt buộc."),
    ]
    ev = [proof(*s) for s in ev_specs]

    f = {
        "id": FID,
        "title": "Luật 'phải gặp người gác cổng trước' (only_when_other_staff) không thể chặn qua API điều phối",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "dead_safety_control",
        "summary": "visit_gate_rule là chốt chặn thứ tự bắt buộc (ví dụ khách phải gặp BS Thành trước khi sang bác sĩ khác). Luật seed duy nhất bắt buộc only_when_other_staff=TRUE; với cờ này, blocks() cho qua khi target_staff_id là None. Hai endpoint ghi duy nhất dẫn tới gate_enforce (/dispatch/move và /dispatch/transfer-room) có MoveRequest/TransferRoomRequest không có trường người đích và không truyền target_staff_id, nên luật không bao giờ chặn qua đường này. Comment trong code hứa 'chốt sẽ xét lại khi đã có người' nhưng không có lần kiểm lại nào. Lượt khám đi luồng mới (đã đo sinh hiệu/có phiên khám) bị move() từ chối; dispatch_order của luồng mới không gọi gate và rules.dispatch_block không nhận thông tin người gác cổng. Yêu cầu 'gặp BS Thành trước' sau đó chỉ còn được thi hành ở lúc đặt lịch bằng luat_bac_si_bat_buoc (theo cách tính khách mới). Suy luận tĩnh.",
        "trigger": "Trưởng ca chuyển một lượt chưa vào luồng mới sang phòng khám của bác sĩ khác qua màn Trưởng ca khi khách chưa qua bước bắt buộc của luật cũ.",
        "impact": "Nếu phòng khám nghĩ rằng luật thứ tự bắt buộc đang canh sau khi khách đến, thì thực tế đường điều phối hiện có không chặn và không đòi lý do bỏ qua; lần bỏ qua cũng không được ghi vào visit_gate_override vì gate không bao giờ nói 'chặn'. Mức ảnh hưởng thực tế phụ thuộc dữ liệu: seed theo tên nhân sự cố định có thể không khớp dòng nào, và production chưa được kiểm. Không có bằng chứng sự cố.",
        "evidence": [],
        "validation": {
            "method": "read_only_exact_main_static_trace_router_service_sql_ui_tests",
            "command": None,
            "result": "Truy vết UI → BFF → router → DispatchService.move → gate_rule_service.enforce → blocks; kiểm migration seed/verify, migration luật mới và dispatch_order. test_gate_rule.py chỉ gọi hàm thuần với target_staff_id có giá trị; không có test mức API/DB cho trường hợp target là None. Tests read-not-run.",
            "limitations": "Static exact-main inference. Không đọc dữ liệu thật nên không biết bảng visit_gate_rule có dòng đang bật hay không (seed khớp theo tên cố định; migration luật mới ghi một seed tương tự đã khớp 0 dòng). Không xác nhận pydantic cấu hình extra field. Không kết luận luồng mới 'bỏ qua mọi luật': đây có thể là chủ ý chuyển sang luật lúc đặt lịch (cần chủ sản phẩm xác nhận).",
        },
        "recommendation": "Chốt chủ ý sản phẩm: luật thứ tự bắt buộc còn sống sau khi khách đến hay đã chuyển hoàn toàn sang luật lúc đặt lịch. Nếu đã chuyển: bỏ hoặc đánh dấu visit_gate_rule là di sản, gỡ khỏi màn/tài liệu để không ai tin nó đang canh. Nếu còn sống: truyền người đích từ API (hoặc suy từ phòng/bác sĩ được chọn), kiểm lại trong cùng transaction với ghi, và áp một chốt tương đương ở luồng mới. Khi chưa biết người đích thì mặc định nên báo 'chưa kiểm' thay vì cho qua im lặng.",
        "acceptance": "Trên DB synthetic: có luật only_when_other_staff=TRUE với người gác cổng A; một lượt chưa qua A được chuyển sang bác sĩ B qua API di chuyển — kết quả hoặc bị chặn có lý do bắt buộc, hoặc hệ thống ghi rõ 'chưa kiểm' và giao owner; có test API-level cho target không xác định. Khi người có quyền bỏ qua, visit_gate_override ghi đủ lý do và người bỏ qua.",
        "alignment": [
            "Quy tắc an toàn thật sự đang canh, không chỉ trông như đang canh",
            "Ownership: biết ai đã bỏ qua luật và vì sao",
            "Phát hiện sớm: chặn đúng lúc thay vì phát hiện sau khi khách đã đi sai",
        ],
        "related_tests": [
            "src/tests/services/test_gate_rule.py:28-52,244-263 — read-not-run; hàm thuần luôn truyền target_staff_id, không kiểm đường API.",
        ],
        "source_hashes": {},
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": SHA,
            "status": "still_present_on_main",
            "note": "Gate chỉ có một điểm gọi (DispatchService.move) và điểm đó không nhận người đích từ API.",
            "evidence": [],
        },
        "related_findings": ["FE-028", "CLIN-010"],
    }
    for x in ev:
        f["evidence"].append({k: x[k] for k in ("path", "line", "end_line", "detail")})
        f["main_validation"]["evidence"].append({k: x[k] for k in ("path", "line", "end_line", "sha256", "excerpt")})
        f["source_hashes"][x["path"]] = x["sha256"]
    findings.append(f)
    save("PHAT-HIEN.json", findings)

    specs = [
        (GATE, 1, None, "Full-file read: luật thuần, SQL tải luật/dữ kiện và enforce()."),
        (ROUTER, 118, 215, "Targeted read: MoveRequest, TransferRoomRequest, ApplyRouteRequest và endpoint ghi."),
        (DISP, 440, 520, "Targeted read: DispatchService.move và gate_enforce."),
        (DISP, 930, 941, "Targeted read: la_luong_moi."),
        ("src/dashboard/app/api/dispatch/[action]/route.ts", 1, None, "Full-file read: BFF chuyển nguyên body."),
        ("supabase/migrations/20260805000006_gate_rule_any_node.sql", 62, 145, "Targeted read: seed và verify của luật Dr4Women."),
        ("supabase/migrations/20260808000003_luat_bac_si_bat_buoc.sql", 1, 80, "Targeted read: lý do không dùng lại visit_gate_rule."),
        ("src/clinicai/services/booking_service.py", 620, 660, "Targeted read: thi hành luật bác sĩ bắt buộc lúc đặt lịch."),
        ("src/clinicai/services/luot_kham_service.py", 3197, 3290, "Targeted read: dispatch_order luồng mới."),
        ("src/tests/services/test_gate_rule.py", 28, 80, "Targeted read: dữ kiện test và luật mẫu; tests read-not-run."),
        ("src/tests/services/test_gate_rule.py", 160, None, "Targeted read: kịch bản first_block/override; luôn truyền target_staff_id; tests read-not-run."),
    ]
    by = {}
    for s in specs:
        x = proof(*s)
        row = by.setdefault(x["path"], {"path": x["path"], "sha256": x["sha256"], "lines": x["lines"], "read_ranges": [], "full_read": False, "outcomes": []})
        rng = {"start": x["line"], "end": x["end_line"]}
        if rng not in row["read_ranges"]:
            row["read_ranges"].append(rng)
        row["full_read"] |= x["line"] == 1 and x["end_line"] == x["lines"]
        row["outcomes"].append(x["detail"])
    cov = []
    for row in by.values():
        row["read_ranges"].sort(key=lambda z: (z["start"], z["end"]))
        row["outcome"] = " ".join(row.pop("outcomes"))
        cov.append(row)
    save("blocks/round53.coverage.json", {
        "schema_version": 1, "round": 53, "report_version": "v0.76", "snapshot_sha": SHA,
        "mode": "read_only_exact_main_scoped_semantic_review",
        "scope": ["visit_gate_rule only_when_other_staff handling", "dispatch move/transfer-room request contract", "new-flow dispatch_order and booking-time doctor rule"],
        "method": "Immutable pinned Git blobs via git show. Ranges line-checked and file SHA-256 checked. Tests read-not-run. No ClinicAI application/runtime/API/DB/provider/VPS/production/secrets/PHI accessed.",
        "result": {
            "new_findings": [FID], "extended_findings": [],
            "deduplicated": ["FE-028 là preview luật bác sĩ lúc đặt lịch; OPS-014 là luật cũ lúc điều phối. CLIN-010 là lệch loại khám sau đổi lịch, không liên quan."],
            "held_candidates": ["Luồng mới (dispatch_order) không có chốt thứ tự bắt buộc sau khi khách đến: có thể là chủ ý (luật chuyển sang lúc đặt lịch). Cần chủ sản phẩm xác nhận trước khi nâng thành lỗi."],
            "full_source_audit_complete": False,
        },
        "full_files": [x for x in cov if x["full_read"]], "targeted_traces": [x for x in cov if not x["full_read"]],
        "reviewer_note": "Scoped static trace of one handoff lead. Không đọc dữ liệu thật, không chạy test.",
    })
    (ROOT / "blocks/round53.md").write_text(f"""# Round 53 — luật thứ tự bắt buộc (visit_gate_rule) không chặn được qua API

Source SHA {SHA}. Review used immutable Git blobs via git show. Tests read only and not run. No ClinicAI application, API, DB, provider, VPS, production, secrets or PHI was accessed.

## Finding

- Added {FID} MEDIUM: luật seed 'BS Thành khám trước' bắt buộc only_when_other_staff=TRUE. blocks() cho qua khi target_staff_id là None. Hai endpoint ghi tới gate (/dispatch/move, /dispatch/transfer-room) không có trường người đích nên luật không bao giờ chặn; comment hứa kiểm lại khi có người nhưng không có lần kiểm lại. Lượt luồng mới bị move() từ chối; dispatch_order không gọi gate.
- Phân biệt hai khả năng của handoff: (1) luồng cũ — XÁC NHẬN tĩnh là cờ không thể chặn qua API. (2) luồng mới — dùng cơ chế khác (luat_bac_si_bat_buoc lúc đặt lịch), migration 20260808000003 ghi rõ đây là chủ ý chuyển thời điểm thi hành; KHÔNG kết luận luồng mới 'bỏ qua mọi luật'.
- Không biết bảng visit_gate_rule có dòng đang bật ở production hay không (seed khớp theo tên cố định). Không có bằng chứng sự cố.

## Recommendation

Chốt chủ ý sản phẩm rồi hoặc gỡ luật cũ khỏi cấu hình/màn để không ai tin nó đang canh, hoặc truyền người đích và kiểm lại trong transaction, cộng chốt tương đương ở luồng mới. Test API-level cho target không xác định.

Exact ranges and hashes: blocks/round53.coverage.json and PHAT-HIEN.json. Full source audit remains incomplete.
""")

    manifest = load("MAIN-PHAM-VI.json")
    for r in manifest["files"]:
        x = by.get(r["path"])
        if not x:
            continue
        if r.get("sha256") and r["sha256"] != x["sha256"]:
            raise ValueError(f"Manifest SHA mismatch for {r['path']}")
        if x["full_read"]:
            r["status"] = "read"; r["full_file_read"] = True
        elif r["status"] in {"scanned", "inventoried"}:
            r["status"] = "traced"
        ranges = ", ".join(f"{q['start']}–{q['end']}" for q in x["read_ranges"])
        note = f"Round 53 exact-main {ranges}; see blocks/round53.coverage.json."
        if "Round 53 exact-main" not in r.get("method", ""):
            r["method"] = (r.get("method", "") + " | " + note).strip(" |")
        r["round53_note"] = x["outcome"]
    manifest["last_updated_round"] = 53
    save("MAIN-PHAM-VI.json", manifest)
    mc = Counter(x["status"] for x in manifest["files"])
    cf = [x for x in manifest["files"] if Path(x["path"]).suffix.lower() in EXTS]
    cc = Counter(x["status"] for x in cf)
    fc = Counter(x["main_validation"]["status"] for x in findings)
    sc = Counter(x["severity"] for x in findings)
    ec = Counter(x["evidence_level"] for x in findings)
    hand = f"Round 53 adds {FID}: the legacy visit_gate_rule with only_when_other_staff=TRUE cannot block through the dispatch API because no caller supplies the target staff; new-flow visits use a booking-time rule instead. Static inference only; tests read-not-run."
    st = load("STATE.json")
    st.update({
        "updated_at": "2026-10-20", "status": "in_progress", "report_version": "v0.76",
        "phase": "round53_v076_gate_rule_lead_closed_audit_open",
        "report_round_summary": hand,
        "next_action": "Continue exact-main review of unread/structurally scanned code, prioritizing authorization by object/tenant/location, money/refund/reconciliation, state transition/concurrency/idempotency, outbox/worker recovery, backup/restore and patient-critical paths. Keep full_source_audit_complete=false until scope and validation gaps are actually closed.",
        "report_status": "Round 53 evidence integrated; v0.76 report-only QA and portable package refresh pending; full source audit remains incomplete.",
        "full_source_audit_complete": False,
        "round53": {"status": "integrated_static_review_report_qa_pending_audit_open", "notes": "blocks/round53.md", "coverage": "blocks/round53.coverage.json", "new_findings": [FID], "extended_findings": [], "tests": "test_gate_rule.py read-not-run.", "runtime": "No ClinicAI app/API/DB/provider/VPS/production/secrets/PHI access.", "full_source_audit_complete": False, "targeted_paths": len(cov), "full_file_reads": sum(x["full_read"] for x in cov)},
    })
    st["summary"]["findings"] = len(findings)
    st["summary"]["severity"] = {k: sc[k] for k in ("HIGH", "MEDIUM", "LOW")}
    st["summary"]["evidence_levels"] = dict(ec)
    st["summary"]["main_status"] = {k: fc[k] for k in ("still_present_on_main", "partially_addressed_on_main", "addressed_on_main")}
    st["summary"]["main_files"] = len(manifest["files"]); st["summary"]["main_partial_traces"] = mc["traced"]
    st["summary"]["main_coverage"] = {k: mc[k] for k in ("inventoried", "traced", "read", "scanned", "excluded")}
    st["summary"]["code_like_source_files"] = {"definition": "Pinned-tree code/web/sql/shell suffixes; includes app, tests, tooling and styles.", "total": len(cf), "coverage": {k: cc[k] for k in ("inventoried", "traced", "scanned", "read")}}
    st["limits"][0] = f"Full source audit incomplete: {mc['inventoried']} inventoried, {mc['traced']} partially traced, {mc['scanned']} scanned and {mc['excluded']} excluded paths out of {len(manifest['files'])}. Path state is not behavioral coverage."
    st["limits"][1] = f"Code-like suffix group includes runtime, tests, tooling and styles; path ledger: {cc['read']} read, {cc['traced']} partially traced, {cc['scanned']} scanned, {cc['inventoried']} inventoried and {cc['excluded']} excluded out of {len(cf)}. This is not a percent-complete or correctness score."
    st["artifacts"]["integration_script"] = "Round53 integrated; v0.76 report-only QA and package refresh pending."
    st["artifacts"]["qa"] = "Pending v0.76 report-only validator and browser check; application behavior not validated."
    st["package"].update({"status": "pending", "file_count": None, "integrity": "Pending v0.76 package rebuild after report QA."})
    st["portable_bundle_status"] = "Pending final v0.76 audit-only package rebuild and verification."
    st["report_html_sha256"] = None
    save("STATE.json", st)
    (ROOT / "TIEP-TUC.md").write_text(f"""# CURRENT HANDOFF — v0.76, Round 53

Evidence source: immutable Git SHA {SHA} in {REPO}. Read source only with git show <SHA>:<path>; do not use working-tree WIP as evidence. Only edit audit artifacts here. Do not run ClinicAI runtime/API/DB/provider/VPS/production or inspect secrets/PHI.

{hand} Evidence and test limits are in blocks/round53.md, blocks/round53.coverage.json, PHAT-HIEN.json and MAIN-PHAM-VI.json.

The visit_gate_rule lead from CLAUDE-HANDOFF.md is closed (see {FID}). Full source audit remains incomplete. Path counters are inventory states, not semantic coverage. v0.76 report-only QA and audit-only ZIP refresh are pending. A plain-language report for non-technical readers is BAO-CAO-DE-HIEU.html. Resume from BAT-DAU-TU-DAY.md and STATE.json.
""")
    (ROOT / "BAT-DAU-TU-DAY.md").write_text(f"""# Bắt đầu từ đây — checkpoint v0.76, Round 53

Đọc CLAUDE-HANDOFF.md, TIEP-TUC.md, STATE.json, NHAT-KY.md, MAIN-PHAM-VI.json, PHAT-HIEN.json, blocks/round53.md và blocks/round53.coverage.json. Source chỉ từ SHA {SHA} qua git show trong worktree audit.

{hand} Không chạy runtime/DB; tests read-not-run. v0.76 report/package QA pending.

Đầu mối visit_gate_rule đã đóng ({FID}). Báo cáo cho người không kỹ thuật: BAO-CAO-DE-HIEU.html (kỹ thuật chi tiết: BAO-CAO.html). Full source audit chưa hoàn tất. Tiếp tục theo STATE.json.next_action.
""")
    with (ROOT / "NHAT-KY.md").open("a") as out:
        out.write(f"""

## Round 53 — 20/10/2026, v0.76 integration

Static exact-main review at SHA {SHA}. Closed the visit_gate_rule lead from CLAUDE-HANDOFF.md: added {FID}. With only_when_other_staff=TRUE (required by the seed), blocks() passes when target_staff_id is None, and no caller of gate_enforce supplies it; the old-flow API cannot block. New-flow visits use luat_bac_si_bat_buoc at booking time by documented intent, so no claim that new-flow ignores all rules. Production rows unknown. Tests read-not-run. Exact ranges in blocks/round53.coverage.json; full source audit incomplete. Report-only QA/package refresh pending.
""")
    print(f"Integrated Round 53: {len(findings)} findings; {len(cov)} path coverage records; full audit remains open")


if __name__ == "__main__":
    main()
