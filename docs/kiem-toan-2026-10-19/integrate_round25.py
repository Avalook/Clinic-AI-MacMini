"""Integrate Round 25 evidence from the pinned ClinicAI source snapshot."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIN = "956ba4f236b1c92f1280d2097018c199e90ce8c7"


def load(name: str):
    return json.loads((ROOT / name).read_text())


def save(name: str, value) -> None:
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def evidence(path: str, start: int, end: int, detail: str) -> dict:
    source = SNAPSHOT / path
    raw = source.read_bytes()
    lines = raw.decode().splitlines()
    if start < 1 or end < start or end > len(lines):
        raise ValueError(f"Invalid pinned-source range {path}:{start}-{end}")
    sha = hashlib.sha256(raw).hexdigest()
    excerpt = "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1))
    return {
        "path": path,
        "line": start,
        "end_line": end,
        "sha256": sha,
        "excerpt": excerpt,
        "detail": detail,
    }


def finding(
    *, id: str, title: str, severity: str, level: str, category: str,
    summary: str, trigger: str, impact: str, recommendation: str,
    acceptance: str, alignment: list[str], references: list[tuple[str, int, int, str]],
    result: str, limitations: str, related_tests: list[str], note: str,
) -> dict:
    proof = [evidence(*item) for item in references]
    return {
        "id": id,
        "title": title,
        "severity": severity,
        "evidence_level": level,
        "category": category,
        "summary": summary,
        "trigger": trigger,
        "impact": impact,
        "evidence": [
            {k: item[k] for k in ("path", "line", "end_line", "detail")}
            for item in proof
        ],
        "validation": {
            "method": "static_exact_main_cross_layer_trace",
            "command": None,
            "result": result,
            "limitations": limitations,
        },
        "recommendation": recommendation,
        "acceptance": acceptance,
        "alignment": alignment,
        "related_tests": related_tests,
        "source_hashes": {item["path"]: item["sha256"] for item in proof},
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": PIN,
            "status": "still_present_on_main",
            "note": note,
            "evidence": [
                {k: item[k] for k in ("path", "line", "end_line", "sha256", "excerpt")}
                for item in proof
            ],
            "production_verified": False,
        },
    }


def main() -> None:
    global SNAPSHOT
    scope = load("MAIN-PHAM-VI.json")
    if scope["sha"] != PIN:
        raise SystemExit(f"Unexpected pinned SHA: {scope['sha']}")
    SNAPSHOT = Path(scope["snapshot"])
    if not SNAPSHOT.is_dir():
        raise SystemExit(f"Pinned snapshot is missing: {SNAPSHOT}")

    additions = [
        finding(
            id="FE-025", title="Lỗi kiểm tra trùng bệnh nhân có thể bị hiểu là không trùng",
            severity="MEDIUM", level="confirmed_static", category="patient-identity/unknown-check-state",
            summary="BFF đổi lỗi backend, thiếu phiên hoặc lỗi mạng thành null; route kiểm tra trùng vẫn trả HTTP 200 với danh sách rỗng. Form chỉ hiển thị ứng viên khi có kết quả, nên trạng thái chưa kiểm được trông giống không có trùng.",
            trigger="Backend trả non-2xx, chưa cấu hình API, mất session hoặc fetch/parse lỗi đúng lúc tạo hồ sơ bệnh nhân.",
            impact="Nhân viên có thể tiếp tục tạo hồ sơ khi hệ thống chưa kiểm tra được. Không có bằng chứng hồ sơ trùng thực tế đã được tạo; MPI hiện có gap review riêng trong PAT-001.",
            recommendation="Trả trạng thái ba giá trị: có kết quả trùng, đã kiểm và không thấy trùng, chưa kiểm được. Khi chưa kiểm, hiển thị rõ và áp dụng policy tạo hồ sơ có kiểm soát; không đổi lỗi thành danh sách sạch.",
            acceptance="Test backend 4xx/5xx, thiếu API, session lỗi và network reject: UI phân biệt unknown với no-match; chỉ no-match đã kiểm mới hiện trạng thái sạch.",
            alignment=["Reality dễ nhìn thấy", "Khoảng Unknown ngắn hơn", "Quyết định dựa trên bằng chứng tốt hơn"],
            references=[
                ("src/dashboard/app/api/patients/check-duplicate/route.ts", 25, 42, "Lỗi backend được map thành response rỗng với HTTP 200."),
                ("src/dashboard/lib/backend-proxy.ts", 244, 267, "fetchFromBackend trả null cho thiếu API/session, non-2xx và network/JSON exception."),
                ("src/dashboard/app/(dashboard)/patients/new/NewPatientForm.tsx", 727, 740, "Form chỉ dùng danh sách trả về; exists=false làm candidate list rỗng, catch im lặng."),
            ],
            result="Static cross-layer trace cho thấy lỗi kiểm tra có thể bị trình bày như danh sách không có ứng viên; chưa xác nhận hành vi người dùng hay hồ sơ trùng.",
            limitations="Chưa chạy browser/API hoặc fault injection; hai boundary test hiện có không kiểm tra trạng thái lỗi của route đang dùng.",
            related_tests=["src/dashboard/tests/route-da-tat-boundary.test.mts — đọc, không chạy; chỉ kiểm tra boundary route.", "src/dashboard/tests/nhieu-so-dien-thoai-boundary.test.mts — đọc, không chạy; không bao phủ lỗi duplicate check hiện tại."],
            note="Còn trên snapshot main ghim; rủi ro là trạng thái unknown bị trình bày như không có kết quả. Chưa có bằng chứng tạo trùng thực tế.",
        ),
        finding(
            id="API-006", title="Loại số điện thoại sai bị âm thầm đổi thành số chính",
            severity="LOW", level="confirmed_static", category="patient-contact/input-normalization",
            summary="BFF patient phone route chỉ kiểm tra trường loai có tồn tại; mọi giá trị ngoài NGUOI_NHA bị chuẩn hóa thành CHINH trước khi gọi FastAPI. DTO backend có Literal enum nhưng không còn nhận được giá trị sai ban đầu.",
            trigger="Một client trực tiếp hoặc request lỗi gửi loai khác CHINH/NGUOI_NHA.",
            impact="Số liên hệ vẫn được lưu nhưng có thể mang nhãn CHINH sai, làm staff đọc nhầm vai trò liên hệ. Luồng UI hiện tại gửi enum hợp lệ; chưa có bằng chứng lỗi này xảy ra trong vận hành.",
            recommendation="Validate giá trị enum ở BFF; chỉ gán CHINH nếu trường thực sự vắng mặt theo contract, còn giá trị được gửi nhưng sai phải trả 4xx.",
            acceptance="Test CHINH, NGUOI_NHA, thiếu loai và loai không hợp lệ ở BFF/backend; trường hợp sai bị từ chối và không ghi event hoặc row.",
            alignment=["Reality đáng tin", "Quyết định dựa trên bằng chứng tốt hơn"],
            references=[
                ("src/dashboard/app/api/patients/sdt-them/route.ts", 27, 43, "BFF kiểm tra sự hiện diện rồi ép mọi giá trị khác NGUOI_NHA thành CHINH."),
                ("src/clinicai/api/v1/patients.py", 209, 235, "DTO backend giới hạn enum và route truyền loại đã parse vào service."),
                ("src/clinicai/services/patient_service.py", 581, 652, "Service kiểm tra và lưu loại số liên hệ cùng event; không sửa phone_primary."),
                ("supabase/migrations/20260815000002_nhieu_so_dien_thoai.sql", 29, 31, "Schema chấp nhận hai nhãn CHINH và NGUOI_NHA."),
                ("src/tests/test_nhieu_so_dien_thoai.py", 106, 138, "Các test hiện có không kiểm tra kind sai bị BFF đổi nhãn."),
            ],
            result="Tính chất coercion được xác nhận qua code BFF→DTO→service; phạm vi bắt đầu từ request có enum sai.",
            limitations="Không chạy request/API/DB; UI chuẩn không gửi enum ngoài tập hợp. Không ghi nhận ghi đè phone_primary.",
            related_tests=["src/tests/test_nhieu_so_dien_thoai.py — đọc đoạn liên quan, không chạy; chưa kiểm tra loại enum không hợp lệ."],
            note="Còn trên snapshot main ghim; chỉ ảnh hưởng request gửi loại liên hệ không hợp lệ, không phải đường UI chuẩn đã được chứng minh.",
        ),
        finding(
            id="OPS-006", title="Giá trị giữ backup bằng 0 có thể xóa toàn bộ ngày backup trên CFS",
            severity="LOW", level="confirmed_static", category="operations/backup-retention",
            summary="Uploader nhận VIETTEL_CFS_GIU_LAI mà không kiểm tra số nguyên dương. Với giá trị 0, GNU head -n -0 chọn mọi ngày; bước xóa sau đó xóa mọi file regular trong từng ngày được chọn, gồm cả bản vừa upload.",
            trigger="Operator hoặc môi trường đặt VIETTEL_CFS_GIU_LAI=0 khi chạy uploader.",
            impact="Các artifact backup trên CFS có thể bị xóa sau lần upload đó, làm giảm khả năng khôi phục. Service units đang đọc không đặt biến này; chưa xác minh override runtime và không kết luận production hiện gặp giá trị 0.",
            recommendation="Validate retention là số nguyên >=1 trước khi upload/prune; dừng an toàn nếu sai. Chỉ prune đúng artifact backup trong phạm vi thư mục/ngày dự kiến.",
            acceptance="Synthetic CFS directory với retention 0, chuỗi sai, 1 và 30: 0/invalid bị từ chối trước xóa; giá trị hợp lệ giữ đúng số ngày và artifact mới nhất.",
            alignment=["Lỗi được phát hiện sớm", "Nhân viên ít chữa cháy hơn", "Lỗi lặp thành cải tiến hệ thống"],
            references=[
                ("scripts/day-sao-luu-len-viettel-storage.sh", 25, 27, "Giá trị retention có default nhưng chưa validate dương."),
                ("scripts/day-sao-luu-len-viettel-storage.sh", 87, 115, "Upload trước rồi lựa chọn ngày bằng head và xóa các file trong ngày."),
                ("scripts/systemd/clinicai-backup.service", 45, 45, "Service gọi uploader, không đặt VIETTEL_CFS_GIU_LAI."),
                ("scripts/systemd/clinicai-backup-15p.service", 45, 45, "Service thứ hai gọi uploader, không đặt VIETTEL_CFS_GIU_LAI."),
            ],
            result="Nhánh retention=0 có thể được suy ra từ lệnh GNU head và vòng xóa; chưa chạy trên CFS hoặc filesystem thật.",
            limitations="Không kiểm tra environment runtime/VPS/CFS; service unit chỉ cho thấy không khai báo biến trong hai caller đã đọc.",
            related_tests=[],
            note="Logic nguy hiểm chỉ được kích hoạt nếu biến được đặt bằng 0; không có bằng chứng production đang đặt như vậy.",
        ),
        finding(
            id="OPS-007", title="Chú thích Supabase cũ có thể dẫn operator vượt qua migration gate hiện hành",
            severity="LOW", level="design_gap", category="operations/migration-runbook-drift",
            summary="supabase/config.toml còn hướng dẫn link project ref và chạy supabase db push. README, AGENTS và runbook hiện tại nói self-hosted trên VPS, cấm db push, yêu cầu backup, rehearsal và scripts/apply-pending-migrations.sh.",
            trigger="Một operator mới làm theo chú thích ngay trong config thay vì đọc runbook hiện hành.",
            impact="Có thể áp migration sai môi trường hoặc bỏ qua cổng backup/rehearsal. Chưa có bằng chứng ai đã làm theo hướng dẫn cũ hoặc có thay đổi production.",
            recommendation="Sửa chú thích config để nói rõ lệnh chỉ phục vụ local reset và không chạy db push; trỏ operator đến runbook/migration script hiện hành.",
            acceptance="Tìm toàn bộ tài liệu vận hành active: không còn chỉ dẫn db push cho VPS; quy trình hiện hành thống nhất backup → rehearsal → apply-pending-migrations.sh.",
            alignment=["Ownership rõ hơn", "Quyết định dựa trên bằng chứng tốt hơn", "Nhân viên làm việc bền vững hơn"],
            references=[
                ("supabase/config.toml", 1, 5, "Chú thích config hướng dẫn link refs và db push."),
                ("supabase/README.md", 62, 71, "README mô tả self-hosted và migration apply script, không dùng db push."),
                ("AGENTS.md", 13, 39, "Quy tắc triển khai đánh dấu db push dead và yêu cầu backup/rehearsal/apply."),
                ("CLAUDE.md", 124, 126, "Runbook hiện hành nhắc migration gate."),
                (".claude/rules/migration.md", 10, 17, "Rule migration hiện hành cấm đường push và nêu apply script."),
            ],
            result="Hai chỉ dẫn văn bản cùng tồn tại và mâu thuẫn; đây là risk về vận hành/tài liệu, không phải bằng chứng hành động sai đã xảy ra.",
            limitations="Không kiểm tra shell history, VPS hay deployment runtime; chỉ đối chiếu nguồn đã ghim.",
            related_tests=[],
            note="Khoảng trống tài liệu còn trên snapshot main; chưa có bằng chứng operator đã dùng chỉ dẫn cũ.",
        ),
        finding(
            id="CLIN-043", title="Đổi bác sĩ và hoàn tác check-in có thứ tự khóa ngược nhau",
            severity="MEDIUM", level="confirmed_static", category="clinical/concurrent-lock-order",
            summary="Luồng đổi bác sĩ khóa visit trước rồi cập nhật appointment. Luồng undo check-in khóa appointment trước, sau đó visit rồi encounter_flow. Nếu cùng lúc xử lý cùng cặp appointment/visit, hai transaction có thể giữ khóa chéo và PostgreSQL hủy một giao dịch do deadlock.",
            trigger="Đổi bác sĩ và hoàn tác check-in chạy đồng thời trên cùng appointment/visit.",
            impact="Một thao tác bị rollback và người dùng phải thử lại; đây là lỗi availability/concurrency, không phải bằng chứng dữ liệu bị hỏng. Chưa có concurrent test hoặc incident được xác nhận.",
            recommendation="Chuẩn hóa lock order xuyên suốt các flow liên quan (appointment → visit → encounter_flow), sau đó revalidate điều kiện nghiệp vụ trong transaction. Thêm retry bounded chỉ khi retry semantics đã idempotent.",
            acceptance="DB test tổng hợp chạy hai transaction cùng appointment qua barrier: không deadlock; một thứ tự hoàn tất an toàn hoặc lỗi domain 409 có thể giải thích, state và audit không bị lệch.",
            alignment=["Khoảng Unknown ngắn hơn", "Con người bị gián đoạn ít hơn", "Lỗi lặp thành cải tiến hệ thống"],
            references=[
                ("src/clinicai/services/doi_bac_si_service.py", 114, 125, "Luồng đổi bác sĩ bắt đầu transaction và khóa visit."),
                ("src/clinicai/services/doi_bac_si_service.py", 169, 178, "Sau đó cập nhật appointment trong transaction."),
                ("src/clinicai/services/hoan_tac_check_in.py", 139, 158, "Undo khóa appointment rồi visit rồi encounter_flow."),
                ("src/clinicai/services/booking_service.py", 875, 897, "Command chạy trong transaction; đường undo được gọi ở action handler."),
                ("src/clinicai/services/booking_service.py", 1040, 1046, "Action handler gọi undo check-in."),
                ("src/tests/services/test_doi_bac_si_theo_quyen_db.py", 30, 58, "Test đổi bác sĩ hiện chạy tuần tự."),
                ("src/tests/services/test_hoan_tac_check_in_db.py", 44, 98, "Helper/test undo dùng cùng visit nhưng chỉ kiểm tra tuần tự."),
            ],
            result="Hai lock order ngược nhau được xác nhận trên exact-main; interleaving deadlock là suy luận concurrency cần xác nhận bằng DB test.",
            limitations="Không dựng DB, không chạy test song song và không kiểm log production. PostgreSQL sẽ rollback một bên khi deadlock được phát hiện.",
            related_tests=["src/tests/services/test_doi_bac_si_theo_quyen_db.py — đọc, không chạy; test tuần tự.", "src/tests/services/test_hoan_tac_check_in_db.py — đọc, không chạy; test tuần tự."],
            note="Lock-order inversion còn trên snapshot; deadlock là khả năng trong interleaving đồng thời, chưa được tái hiện.",
        ),
    ]

    findings = load("PHAT-HIEN.json")
    existing = {item["id"] for item in findings}
    if existing.intersection(item["id"] for item in additions):
        raise SystemExit("Round 25 finding id already exists")

    fe023 = next(item for item in findings if item["id"] == "FE-023")
    extra_ui = [
        ("src/dashboard/app/(dashboard)/customers/BaoXepBacSi.tsx", 13, 65, "Fetch reject trước khi chạy nhánh reset pending; nút bị disabled khi đang gửi."),
        ("src/dashboard/app/(dashboard)/customers/DauUuTien.tsx", 9, 91, "Fetch reject bỏ qua bước reset pending; nút ghi bị disabled khi đang gửi."),
        ("src/dashboard/app/(dashboard)/customers/LichTrungCuaKhach.tsx", 33, 168, "Fetch reject trong hủy lịch bỏ qua bước reset pending; nút hủy bị disabled khi đang gửi."),
    ]
    for path, start, end, detail in extra_ui:
        if any(e["path"] == path for e in fe023["evidence"]):
            continue
        proof = evidence(path, start, end, detail)
        fe023["evidence"].append({k: proof[k] for k in ("path", "line", "end_line", "detail")})
        fe023["main_validation"]["evidence"].append({k: proof[k] for k in ("path", "line", "end_line", "sha256", "excerpt")})
        fe023["source_hashes"][path] = proof["sha256"]
    fe023["summary"] = "Nhiều màn đặt cờ gửi trước fetch và chỉ reset sau khi promise resolve. Fetch reject có thể giữ nút disabled; đã xác nhận pattern ở ThaiKy, BaoXepBacSi, DauUuTien và LichTrungCuaKhach."
    fe023["trigger"] = "Fetch reject do offline, timeout hoặc connection reset khi lưu ThaiKy, đổi bác sĩ, đặt ưu tiên hoặc hủy lịch."
    fe023["impact"] = "Nhân viên không biết thao tác đã đến server chưa và có thể không gửi lại được cho tới khi component remount. Chưa có fault-injection; không khẳng định mọi request bị mất hoặc commit không xảy ra."
    fe023["recommendation"] = "Dùng try/catch/finally để dọn pending; khi kết quả ghi không rõ, hiển thị unknown state và đọc lại server trước retry."
    fe023["acceptance"] = "Component tests cho reject trước response ở bốn màn: pending luôn gỡ, lỗi/unknown hiện rõ, refresh đối soát state và retry không nhân đôi thao tác."
    fe023["validation"]["result"] = "Static pattern được xác nhận tại bốn màn; chưa inject lỗi mạng hoặc kiểm trạng thái commit."
    fe023["validation"]["limitations"] = "Static UI inference; chưa chạy component/browser tests, không kiểm commit/response loss."
    fe023["main_validation"]["note"] = "Pattern pending có thể kẹt sau fetch reject được xác nhận ở bốn màn; chưa tái hiện lỗi mạng."
    findings.extend(additions)
    save("PHAT-HIEN.json", findings)

    # Update ledger only for files whose full or targeted review is recorded below.
    reviewed = {
        "src/dashboard/app/api/patients/check-duplicate/route.ts": ("traced", [(25, 42, "FE-025")]),
        "src/dashboard/lib/backend-proxy.ts": ("traced", [(244, 267, "FE-025")]),
        "src/dashboard/app/(dashboard)/patients/new/NewPatientForm.tsx": ("traced", [(727, 740, "FE-025")]),
        "src/dashboard/tests/route-da-tat-boundary.test.mts": ("read", [(1, 43, "full-file read")]),
        "src/dashboard/tests/nhieu-so-dien-thoai-boundary.test.mts": ("read", [(1, 132, "full-file read")]),
        "src/dashboard/tests/cua-quyen-lego-boundary.test.mts": ("traced", [(243, 267, "FE-025 boundary context")]),
        "src/dashboard/app/api/patients/sdt-them/route.ts": ("traced", [(27, 43, "API-006")]),
        "src/clinicai/api/v1/patients.py": ("traced", [(209, 235, "API-006")]),
        "src/clinicai/services/patient_service.py": ("traced", [(581, 652, "API-006")]),
        "supabase/migrations/20260815000002_nhieu_so_dien_thoai.sql": ("traced", [(29, 31, "API-006")]),
        "src/tests/test_nhieu_so_dien_thoai.py": ("traced", [(106, 138, "API-006")]),
        "scripts/day-sao-luu-len-viettel-storage.sh": ("read", [(1, 129, "full-file read")]),
        "scripts/systemd/clinicai-backup.service": ("read", [(1, 53, "full-file read")]),
        "scripts/systemd/clinicai-backup-15p.service": ("read", [(1, 53, "full-file read")]),
        "supabase/config.toml": ("read", [(1, 20, "full-file read")]),
        "supabase/README.md": ("read", [(1, 104, "full-file read")]),
        "AGENTS.md": ("traced", [(13, 39, "OPS-007 current operational rule")]),
        "CLAUDE.md": ("traced", [(124, 126, "OPS-007 migration runbook")]),
        ".claude/rules/migration.md": ("traced", [(10, 17, "OPS-007 migration rule")]),
        "src/clinicai/services/doi_bac_si_service.py": ("traced", [(114, 125, "CLIN-043"), (169, 178, "CLIN-043")]),
        "src/clinicai/services/hoan_tac_check_in.py": ("read", [(1, 170, "full-file read"), (139, 158, "CLIN-043 lock order")]),
        "src/clinicai/services/booking_service.py": ("traced", [(875, 897, "CLIN-043 transaction"), (1040, 1046, "CLIN-043 caller")]),
        "src/tests/services/test_doi_bac_si_theo_quyen_db.py": ("traced", [(30, 58, "CLIN-043 sequential test")]),
        "src/tests/services/test_hoan_tac_check_in_db.py": ("traced", [(44, 48, "CLIN-043 shared appointment/visit"), (78, 98, "CLIN-043 sequential test")]),
        "src/dashboard/app/(dashboard)/customers/BaoXepBacSi.tsx": ("traced", [(13, 65, "FE-023")]),
        "src/dashboard/app/(dashboard)/customers/DauUuTien.tsx": ("traced", [(9, 91, "FE-023")]),
        "src/dashboard/app/(dashboard)/customers/LichTrungCuaKhach.tsx": ("traced", [(33, 168, "FE-023")]),
    }
    files = {item["path"]: item for item in scope["files"]}
    coverage_rows = []
    for path, (level, ranges) in reviewed.items():
        item = files.get(path)
        if not item:
            raise SystemExit(f"Pinned ledger path missing: {path}")
        source = SNAPSHOT / path
        raw = source.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        lines = len(raw.decode().splitlines())
        if item.get("sha256") and item["sha256"] != digest:
            raise SystemExit(f"Ledger/source hash mismatch: {path}")
        item["sha256"] = digest
        item["lines"] = lines
        prior = item["status"]
        if level == "read":
            item["status"] = "read"
            item["full_file_read"] = True
        elif prior not in {"read", "excluded"}:
            item["status"] = "traced"
        item["method"] = (item.get("method", "") + " | Round 25: " + "; ".join(p for _, _, p in ranges)).strip(" |")
        item["round25_note"] = "Exact-main evidence; review scope and line ranges recorded in blocks/round25.coverage.json."
        coverage_rows.append({
            "path": path,
            "status": item["status"],
            "prior_status": prior,
            "full_file_read_this_round": level == "read",
            "read_level_this_round": "read" if level == "read" else "traced",
            "ranges": [{"start": start, "end": end, "purpose": purpose} for start, end, purpose in ranges],
            "sha256": digest,
            "line_count": lines,
        })
    save("MAIN-PHAM-VI.json", scope)

    coverage = {
        "schema_version": 1,
        "audit": "round25_static_exact_main_multi_slice",
        "snapshot": {"path": str(SNAPSHOT), "sha": PIN},
        "review_mode": "read_only_static_exact_main",
        "scope": ["patient duplicate-check unknown state", "patient contact kind validation", "CFS backup retention", "migration operator instructions", "clinical lock-order concurrency", "network pending-state UI pattern"],
        "tests_run": False,
        "runtime_db_vps_secrets_phi_touched": False,
        "coverage_note": "Five findings added; FE-023 expanded to four screens. Source/test reads and targeted traces are listed below. No ClinicAI test/runtime was run.",
        "held_observations": ["CLIN-ROLE-CAPABILITY-001: permission-capable MANAGEMENT can be assigned as attending doctor, while doctor-name/signature resolver filters doctor roles; domain semantics unclear.", "TENANT-RLS-TEST-SCOPE-001: tenant test does not assert that every relevant table has RLS enabled; no live table leak established.", "TEST-CONTAINER-CLEANUP-001: local SQL test runner removes a fixed container name; no production impact established.", "OPS-UFW-BOOTSTRAP-001: bootstrap warning requires caller/runtime context before promotion."],
        "files": coverage_rows,
    }
    save("blocks/round25.coverage.json", coverage)
    save("blocks/round25_findings.json", additions)
    (ROOT / "blocks/round25.md").write_text(
        "# Round 25 — static exact-main review\n\n"
        f"Snapshot `{PIN}`. Không chạy test ClinicAI, API/DB/provider/production; không dùng secrets hoặc hồ sơ bệnh nhân.\n\n"
        "## Findings tích hợp\n\n"
        "- `FE-025` (MEDIUM): lỗi duplicate check có thể hiển thị như không có kết quả; khác FE-012 (stale candidate sau khi input đổi).\n"
        "- `API-006` (LOW): loại số điện thoại sai bị BFF chuẩn hóa thành CHINH; không có bằng chứng đường UI chuẩn gửi sai.\n"
        "- `OPS-006` (LOW, điều kiện): retention=0 có thể prune mọi ngày backup CFS; chưa xác minh override trên VPS.\n"
        "- `OPS-007` (LOW, design gap): chú thích `supabase/config.toml` mâu thuẫn runbook migration active; chưa có bằng chứng ai làm theo chỉ dẫn cũ.\n"
        "- `CLIN-043` (MEDIUM): lock order đổi bác sĩ/undo check-in ngược nhau có thể deadlock khi cùng appointment chạy đồng thời; chưa có concurrent DB test.\n"
        "- Mở rộng `FE-023`: pattern pending sau fetch reject có ở ThaiKy, BaoXepBacSi, DauUuTien và LichTrungCuaKhach.\n\n"
        "## Chưa promote\n\n"
        "Role capability so với doctor/signer identity còn cần owner nghiệp vụ; tenant test chưa chứng minh table nào đang tắt RLS; fixed-name container cleanup chưa gắn với prod; bootstrap warning thiếu caller context. Chi tiết và lý do giữ ở `STATE.json → held_observations`.\n\n"
        "Hashes, excerpt và trạng thái read/traced nằm trong `round25.coverage.json`; nguồn finding ở `round25_findings.json` và canonical `../PHAT-HIEN.json`.\n"
    )

    state = load("STATE.json")
    state["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    state["status"] = "in_progress"
    state["phase"] = "round25_checkpoint_v048_artifacts_pending_qa_source_audit_incomplete"
    state["next_action"] = "Tiếp tục exact-main paths còn scanned/inventoried: kết quả/lab và luồng in, event recovery/ownership, patient assignment/tenant onboarding, migration/RLS còn lại. Sau static pass, chạy synthetic tests trong môi trường dùng một lần cho duplicate unknown, phone-kind validation, backup retention=0 và concurrent lock order. Full source audit chưa hoàn tất."
    state["report_status"] = "v0.48 evidence integrated; HTML/ZIP QA pending; static source audit incomplete"
    state["report_version"] = "v0.48"
    state["report_round_summary"] = "Round 25 thêm FE-025, API-006, OPS-006, OPS-007, CLIN-043; mở rộng FE-023 thêm ba màn. Exact-main static review; held observations giữ riêng; chưa chạy ClinicAI tests/runtime, DB, providers hoặc production."
    state["blocks"]["round25"] = {
        "status": "round25_static_review_integrated; report_qa_pending; full_audit_open",
        "notes": "blocks/round25.md",
        "findings": "PHAT-HIEN.json: FE-025, API-006, OPS-006, OPS-007, CLIN-043; FE-023 expanded",
        "coverage": "blocks/round25.coverage.json",
        "next": "Continue remaining result/print, event recovery, patient assignment/tenant and migration/RLS source. Synthetic DB/UI/filesystem validation remains open.",
    }
    state["held_observations"].extend(coverage["held_observations"])
    severity = Counter(item["severity"] for item in findings)
    levels = Counter(item["evidence_level"] for item in findings)
    main_counts = Counter(item["main_validation"]["status"] for item in findings)
    path_counts = Counter(item["status"] for item in scope["files"])
    code_suffixes = {'.py', '.pyi', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.sql', '.sh', '.bash', '.go', '.rs', '.java', '.kt', '.css', '.html'}
    code_files = [item for item in scope["files"] if Path(item["path"]).suffix.lower() in code_suffixes]
    code_counts = Counter(item["status"] for item in code_files)
    state["summary"].update({
        "findings": len(findings),
        "severity": {key: severity[key] for key in ["HIGH", "MEDIUM", "LOW"]},
        "evidence_levels": {key: levels[key] for key in ["reproduced_local", "design_gap", "confirmed_static", "hypothesis"]},
        "main_status": {key: main_counts[key] for key in ["still_present_on_main", "partially_addressed_on_main", "addressed_on_main"]},
        "main_files": len(scope["files"]),
        "main_partial_traces": path_counts["traced"],
        "main_coverage": {key: path_counts[key] for key in ["inventoried", "read", "traced", "scanned", "excluded"]},
        "code_like_source_files": {
            "definition": "Pinned-tree paths with common code/web/sql/shell suffixes; includes app, tests, tooling and styles.",
            "total": len(code_files),
            "coverage": {key: code_counts[key] for key in ["inventoried", "traced", "scanned", "read"]},
            "traced_is_partial": True,
        },
        "new_findings_v048": [item["id"] for item in additions],
        "reviewed_slice_v048": f"Round 25: {len(reviewed)} path records; five findings, FE-023 expanded; exact-main static only.",
    })
    state["artifacts"]["qa"] = "Pending v0.48 structural/evidence and desktop/mobile browser QA."
    state["artifacts"]["integration_script"] = "Round 25 evidence/coverage generated from pinned Git object by integrate_round25.py; report validator checks hashes/excerpts."
    state["artifacts"]["html_sha256"] = "pending"
    state["artifacts"]["bundle_entries"] = "pending v0.48 final rebuild"
    state["artifacts"]["bundle_integrity"] = "Pending final v0.48 audit-only ZIP verification."
    save("STATE.json", state)

    (ROOT / "NHAT-KY.md").open("a").write(
        "\n\n## Round 25 — 20/10/2026, v0.48 draft\n\n"
        "- Thêm FE-025, API-006, OPS-006, OPS-007, CLIN-043; mở rộng FE-023 sang ba màn khách hàng.\n"
        "- Các bằng chứng được trích từ exact-main SHA; 5 finding chưa có runtime/app/DB/production verification. OPS-006 phụ thuộc retention override=0; OPS-007 là mâu thuẫn tài liệu; CLIN-043 là interleaving cần test concurrent.\n"
        "- Coverage ledger chỉ nâng read/traced theo phạm vi đã ghi trong `blocks/round25.coverage.json`; full audit còn mở. Held observations giữ riêng.\n"
        "- Next: rebuild/QA HTML và ZIP; sau đó tiếp tục paths còn scanned/inventoried, ưu tiên result/print, recovery, patient/tenant, migration/RLS.\n"
    )

    handoff = (
        "# CURRENT HANDOFF — v0.48 (20/10/2026)\n\n"
        f"Exact-main `{PIN}`. Risk register: {len(findings)} hồ sơ ({severity['HIGH']} HIGH, {severity['MEDIUM']} MEDIUM, {severity['LOW']} LOW); "
        f"{main_counts['still_present_on_main']} còn dấu hiệu, {main_counts['partially_addressed_on_main']} partial, {main_counts['addressed_on_main']} addressed trong phạm vi đối chiếu. "
        f"Coverage {len(scope['files']):,} path: {path_counts['read']:,} read, {path_counts['traced']:,} traced một phần, {path_counts['scanned']:,} scanned, {path_counts['inventoried']:,} inventoried, {path_counts['excluded']:,} excluded. Đây là trạng thái theo path, không phải tỷ lệ code đã hiểu. Full source audit vẫn chưa xong.\n\n"
        "Round 25 thêm FE-025, API-006, OPS-006, OPS-007, CLIN-043 và mở rộng FE-023 sang ba màn. Xem `blocks/round25.md`, `blocks/round25.coverage.json` và `blocks/round25_findings.json`. Held observations nằm trong `STATE.json`.\n\n"
        "HTML v0.48 và ZIP đang chờ rebuild/QA. Không chạy ClinicAI tests/API/DB/provider/production; không đọc secrets/PHI. ZIP chỉ chứa hồ sơ audit; phải giữ repository/Git history có SHA ghim để tiếp tục source review. Working tree gốc có WIP, không dùng làm evidence.\n\n"
        "## Điểm vào nếu đổi tài khoản\n\n"
        "Đọc `BAT-DAU-TU-DAY.md`, `STATE.json`, file này, `NHAT-KY.md`, `MAIN-PHAM-VI.json`, `PHAT-HIEN.json`, `TEST-RUNS.json`, rồi `blocks/round25.md` và `blocks/round25.coverage.json`. Làm trên exact-main SHA ghim; không coi `scanned` là đã đọc.\n\n"
        "## Việc kế tiếp\n\n"
        "1. Rebuild HTML v0.48, chạy structural/evidence và desktop/mobile QA; dựng và verify lại ZIP.\n"
        "2. Tiếp tục source còn scanned/inventoried: result/lab và print, event recovery/ownership, patient assignment/tenant onboarding, migration/RLS.\n"
        "3. Sau static pass, tạo synthetic test trong disposable environment cho unknown duplicate state, invalid contact kind, backup retention, và concurrent clinical locks.\n"
        "4. Không promote policy/timing candidates nếu chưa có owner hoặc bằng chứng; không tuyên bố sự cố production chỉ từ source.\n\n"
        "Round 25 là static exact-main review. Test files chỉ được đọc, không chạy; chưa có app/API/DB/provider/production validation. Full audit vẫn dang dở.\n"
    )
    (ROOT / "TIEP-TUC.md").write_text(handoff)

    resume = (ROOT / "BAT-DAU-TU-DAY.md").read_text()
    lines = resume.splitlines()
    lines[:7] = [
        "# Trạng thái hiện hành — 20/10/2026, checkpoint v0.48",
        "",
        f"## Checkpoint v0.48 — tiếp quản nhanh",
        "",
        f"Main ghim: `{PIN}`. Risk register {len(findings)} hồ sơ ({severity['HIGH']} HIGH, {severity['MEDIUM']} MEDIUM, {severity['LOW']} LOW); main status {main_counts['still_present_on_main']}/{main_counts['partially_addressed_on_main']}/{main_counts['addressed_on_main']} trong phạm vi đã đối chiếu. Coverage {len(scope['files']):,} path: {path_counts['read']} read, {path_counts['traced']} traced, {path_counts['scanned']} scanned, {path_counts['inventoried']} inventoried, {path_counts['excluded']} excluded; nhóm code-like: {code_counts['read']} read, {code_counts['traced']} traced, {code_counts['scanned']} scanned, {code_counts['inventoried']} inventoried. Đây là trạng thái theo path, không phải tỷ lệ đã hiểu. Full source audit chưa xong.",
        "",
        "Round 25 thêm FE-025, API-006, OPS-006, OPS-007, CLIN-043; mở rộng FE-023 thêm ba màn. Kết quả static exact-main; chưa chạy ClinicAI tests/API/DB/provider/production, không đọc secrets/PHI. HTML/ZIP v0.48 cần rebuild và QA report-only. Chi tiết tại `blocks/round25.md`, `blocks/round25.coverage.json`, `blocks/round25_findings.json`.",
        "",
        "Khi đổi tài khoản: đọc `STATE.json`, `TIEP-TUC.md`, `NHAT-KY.md`, `PHAT-HIEN.json`, `MAIN-PHAM-VI.json`, `TEST-RUNS.json` và block round25. ZIP không có source/Git history; cần giữ repo đúng SHA ghim. Không dùng WIP checkout ban đầu làm evidence.",
    ]
    (ROOT / "BAT-DAU-TU-DAY.md").write_text("\n".join(lines) + "\n")
    print(f"Integrated {len(additions)} findings and {len(reviewed)} path coverage records")


if __name__ == "__main__":
    main()
