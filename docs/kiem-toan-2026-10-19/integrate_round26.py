"""Integrate exact-main dashboard and ops visibility review for Round 26."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIN = "956ba4f236b1c92f1280d2097018c199e90ce8c7"
SNAPSHOT: Path


def load(name: str):
    return json.loads((ROOT / name).read_text())


def save(name: str, value) -> None:
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def evidence(path: str, start: int, end: int, detail: str) -> dict:
    raw = (SNAPSHOT / path).read_bytes()
    lines = raw.decode().splitlines()
    if start < 1 or end < start or end > len(lines):
        raise ValueError(f"Invalid pinned-source range {path}:{start}-{end}")
    digest = hashlib.sha256(raw).hexdigest()
    excerpt = "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1))
    return {
        "path": path,
        "line": start,
        "end_line": end,
        "sha256": digest,
        "excerpt": excerpt,
        "detail": detail,
    }


def attach(finding: dict, refs: list[tuple[str, int, int, str]]) -> None:
    for ref in refs:
        proof = evidence(*ref)
        if any(
            row["path"] == proof["path"] and row["line"] == proof["line"]
            and row["end_line"] == proof["end_line"]
            for row in finding["main_validation"]["evidence"]
        ):
            continue
        finding["evidence"].append(
            {k: proof[k] for k in ("path", "line", "end_line", "detail")}
        )
        finding["main_validation"]["evidence"].append(
            {k: proof[k] for k in ("path", "line", "end_line", "sha256", "excerpt")}
        )
        finding["source_hashes"][proof["path"]] = proof["sha256"]


def make_finding(
    *, id: str, title: str, severity: str, category: str, summary: str,
    trigger: str, impact: str, recommendation: str, acceptance: str,
    alignment: list[str], refs: list[tuple[str, int, int, str]],
    result: str, limitations: str, related_tests: list[str], note: str,
) -> dict:
    proof = [evidence(*ref) for ref in refs]
    return {
        "id": id,
        "title": title,
        "severity": severity,
        "evidence_level": "confirmed_static",
        "category": category,
        "summary": summary,
        "trigger": trigger,
        "impact": impact,
        "evidence": [
            {k: row[k] for k in ("path", "line", "end_line", "detail")}
            for row in proof
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
        "source_hashes": {row["path"]: row["sha256"] for row in proof},
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": PIN,
            "status": "still_present_on_main",
            "note": note,
            "evidence": [
                {k: row[k] for k in ("path", "line", "end_line", "sha256", "excerpt")}
                for row in proof
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

    findings = load("PHAT-HIEN.json")
    ids = {item["id"] for item in findings}
    additions = [
        make_finding(
            id="FE-026",
            title="Lịch sử điều phối có thể kẹt ở trạng thái đang tải",
            severity="LOW",
            category="operations/unknown-read-state",
            summary="Panel lịch sử chỉ cập nhật khi nhận được mảng items. Khi API trung gian trả {ok:false} vì backend không phản hồi, component nuốt lỗi và giữ lichSu=null; giao diện tiếp tục hiện ‘Đang tải…’. Panel được thử lại gián tiếp khi danh sách hàng đợi đổi hoặc component được dựng lại, nhưng không có lỗi/retry riêng.",
            trigger="Backend dispatch/history lỗi kéo dài trong lúc bảng hàng đợi vẫn được dựng và không có lần refresh danh sách bệnh nhân mới.",
            impact="Trưởng ca không phân biệt được lịch sử chưa tải, không có sự kiện hay đang lỗi; khó xác minh ai vừa chuyển bệnh nhân và làm giảm khả năng phối hợp. Đây là panel phụ; chưa có bằng chứng gây chậm chăm sóc hoặc sự cố thực tế.",
            recommendation="Dùng trạng thái loading/loaded-empty/error riêng; khi lỗi, hiện dấu hiệu và nút thử lại, đồng thời giữ dữ liệu thành công gần nhất cùng thời điểm tải.",
            acceptance="Component test cho backend trả {ok:false}, HTTP lỗi, network reject, danh sách rỗng hợp lệ và lần thử lại thành công; không trường hợp lỗi nào bị hiển thị là đang tải vô hạn hoặc không có thao tác.",
            alignment=["Reality dễ nhìn thấy", "Khoảng Unknown ngắn hơn", "Ownership rõ hơn"],
            refs=[
                ("src/dashboard/app/(dashboard)/truong-ca/QueuesClient.tsx", 43, 55, "History state chỉ nhận items array; lỗi bị bỏ qua nên null không được đổi."),
                ("src/dashboard/app/api/dispatch-read/route.ts", 48, 51, "BFF biểu diễn backend không trả lời bằng HTTP 200 {ok:false}."),
                ("src/dashboard/app/(dashboard)/truong-ca/QueuesClient.tsx", 401, 415, "Khi state còn null, panel chỉ hiện ‘Đang tải…’; empty chỉ dành cho items rỗng đã tải."),
                ("src/clinicai/api/v1/routers/dispatch.py", 86, 98, "Đường đọc thành công trả {ok:true, items}; đối chiếu contract với nhánh lỗi của BFF."),
            ],
            result="Tĩnh exact-main cho thấy nhánh lỗi không cập nhật state lịch sử; lần làm mới tiếp theo phụ thuộc thay đổi danh sách bệnh nhân hoặc remount.",
            limitations="Không chạy component/browser test hay fault injection. Không kết luận panel ảnh hưởng luồng điều trị; refresh hàng đợi và SSE có thể kích hoạt lần đọc tiếp.",
            related_tests=["src/dashboard/tests/truong-ca-phong-ui-boundary.test.mts — đọc trọn, không chạy; kiểm giao diện/nhịp dữ liệu, không kiểm lỗi panel lịch sử."],
            note="Còn trên snapshot main ghim; trạng thái loading vô thời hạn là suy luận từ state/effect khi lỗi lặp lại, chưa tái hiện runtime.",
        ),
        make_finding(
            id="OPS-008",
            title="Danh sách kiểu lỗi chỉ lấy 100 dòng mà không báo còn dữ liệu",
            severity="MEDIUM",
            category="operations/observability-pagination",
            summary="Service sắp xếp các nhóm lỗi theo lần xuất hiện gần nhất rồi LIMIT 100. API chỉ trả mảng loi; giao diện không nhận tổng số, has_more hoặc cursor. Ở chế độ ‘chỉ lỗi còn phải xử lý’, hơn 100 nhóm đang mở có thể khiến nhóm cũ không xuất hiện và operator không biết danh sách bị cắt.",
            trigger="Có hơn 100 nhóm lỗi thuộc tập đang xem, đặc biệt nhiều nhóm mới hơn che các nhóm MOI/DA_BIET cũ.",
            impact="Một lỗi cũ còn cần xử lý có thể bị khuất khỏi màn theo dõi, làm giảm khả năng phát hiện sớm. Chưa có số liệu volume để kết luận điều kiện này đang xảy ra trong production.",
            recommendation="Thêm phân trang/cursor ổn định và metadata total/has_more; nếu giữ trần, hiện rõ giới hạn và ưu tiên nhóm chưa xử lý theo mức độ/tuổi thay vì chỉ thời điểm cuối.",
            acceptance="Tạo 101+ nhóm tổng hợp bằng fixture synthetic, trong đó nhóm MOI cũ nhất; màn phải phân trang hoặc báo còn dữ liệu và cho operator tìm được nhóm cũ. Kiểm tra thứ tự ổn định khi có nhóm mới đồng thời.",
            alignment=["Vấn đề được phát hiện sớm hơn", "Reality ngày càng dễ nhìn", "Quyết định dựa trên bằng chứng tốt hơn"],
            refs=[
                ("src/clinicai/api/v1/routers/ops.py", 132, 143, "Endpoint trả một mảng loi, không kèm metadata phân trang."),
                ("src/clinicai/services/kho_loi.py", 155, 171, "Mặc định giới hạn 100 nhóm; sắp xếp theo lan_cuoi DESC rồi LIMIT."),
                ("src/dashboard/app/api/ops/theo-doi/route.ts", 9, 18, "BFF chuyển tiếp endpoint loi mà không có query phân trang."),
                ("src/dashboard/app/(dashboard)/ops/LoiCanhBao.tsx", 80, 103, "UI nhận toàn bộ trường loi dưới dạng mảng, không nhận total/cursor."),
                ("src/dashboard/app/(dashboard)/ops/LoiCanhBao.tsx", 201, 220, "UI mô tả mỗi kiểu lỗi một dòng và empty state nhưng không hiển thị dấu cắt danh sách."),
            ],
            result="Trần 100, thứ tự mới nhất trước và thiếu metadata phân trang được xác nhận tĩnh xuyên service/API/BFF/UI.",
            limitations="Không truy vấn production, không đo số nhóm lỗi thực tế và không chạy test/API; tác động chỉ xảy ra khi vượt quá giới hạn.",
            related_tests=[
                "src/tests/services/test_theo_doi_pha_1_db.py — đọc đoạn liên quan, không chạy; test gom lỗi/che thông tin, không kiểm giới hạn danh sách.",
                "src/tests/unit/test_theo_doi_pha_1.py — đọc trọn, không chạy; không có test pagination/cap.",
                "src/tests/api/test_ops_api.py — đọc trọn, không chạy; kiểm quyền/status, không kiểm danh sách lỗi quá 100 nhóm.",
            ],
            note="Giới hạn 100 còn trên snapshot main ghim; mức ảnh hưởng phụ thuộc số nhóm lỗi thực tế, chưa kiểm chứng production.",
        ),
    ]
    if ids.intersection(item["id"] for item in additions):
        raise SystemExit("Round 26 finding id already exists")

    fe004 = next(item for item in findings if item["id"] == "FE-004")
    attach(fe004, [
        ("src/dashboard/app/(dashboard)/ops/ToanCanh.tsx", 57, 89, "Nguồn Toàn cảnh trả null bị đổi thành staff/events rỗng và các KPI 0."),
        ("src/dashboard/app/(dashboard)/home/page.tsx", 377, 407, "Một số KPI Trang chủ dùng fallback 0 khi gói dữ liệu null."),
        ("src/dashboard/app/(dashboard)/home/page.tsx", 456, 459, "Trang chủ có nhận biết toàn bộ gói null là lỗi."),
        ("src/dashboard/app/(dashboard)/home/page.tsx", 518, 525, "Trang chủ có banner cảnh báo dưới phần KPI; số 0 phía trên vẫn được render."),
        ("src/dashboard/app/(dashboard)/ops/PortalBoard.tsx", 513, 541, "Thẻ số liệu Toàn cảnh render giá trị đã được fallback thành 0."),
    ])
    fe004["title"] = "Một số màn báo cáo/điều hành có thể trình bày lỗi đọc thành số 0 hoặc không có hoạt động"
    fe004["summary"] = (
        "fetchFromBackend trả null khi non-2xx hoặc lỗi mạng. Trang báo cáo biến KPI null thành danh sách rỗng và nói tháng này chưa ai đặt lịch. "
        "Màn Toàn cảnh biến payload null thành staff/events rỗng và KPI 0. Trang chủ cũng render KPI 0 khi gói null, dù có banner lỗi bên dưới; banner giúp nhận ra lỗi nhưng con số phía trên vẫn giống số liệu thật."
    )
    fe004["trigger"] = "Một nguồn số liệu báo cáo hoặc vận hành lỗi/không phản hồi trong khi giao diện vẫn dựng được phần còn lại."
    fe004["impact"] = "Nhân viên có thể hiểu số 0 hoặc danh sách rỗng là hoạt động đã được kiểm tra và không tồn tại. Ở Trang chủ có cảnh báo rõ, nên rủi ro giảm nếu người dùng nhìn thấy banner; riêng KPI phía trên vẫn không biểu diễn trạng thái chưa biết."
    fe004["recommendation"] = "Dùng kết quả có trạng thái riêng cho từng nguồn, kèm thời điểm đọc. Chỉ hiện trạng thái rỗng sau response thành công; khi một nguồn lỗi, giữ dữ liệu cũ có nhãn stale hoặc che số bằng trạng thái chưa đọc được."
    fe004["acceptance"] = "Kiểm thử độc lập từng endpoint với 200 rỗng, 403, 503 và network reject trên Báo cáo, Toàn cảnh và Trang chủ; trạng thái lỗi không được hiển thị như số 0 đã xác nhận hoặc câu khẳng định không có hoạt động."
    fe004["validation"]["result"] = "Static trace trên Báo cáo, Toàn cảnh và Trang chủ xác nhận ba cách biến trạng thái chưa đọc được thành rỗng/0; Trang chủ có banner lỗi riêng nhưng vẫn dựng các KPI fallback."
    fe004["validation"]["limitations"] = "Chưa chạy browser/fault injection hoặc xác nhận lỗi trên production; Toàn cảnh và Trang chủ phụ thuộc payload nguồn tương ứng."
    fe004["main_validation"]["note"] = "Còn trên main ghim: Báo cáo và Toàn cảnh làm mất khác biệt null/empty; Trang chủ có banner nhưng vẫn render các KPI 0. Chưa có bằng chứng người dùng đã ra quyết định sai."

    fe023 = next(item for item in findings if item["id"] == "FE-023")
    attach(fe023, [
        ("src/dashboard/app/(dashboard)/patients/AppointmentBooking.tsx", 287, 313, "Bật submitting rồi gọi PATCH đổi lịch; reset chỉ chạy sau khi fetch và JSON resolve."),
        ("src/dashboard/app/(dashboard)/patients/AppointmentBooking.tsx", 322, 355, "POST đặt lịch không gửi Idempotency-Key và reset submitting sau khi JSON resolve; reject có thể bỏ qua reset."),
        ("src/dashboard/app/api/appointments/route.ts", 176, 209, "BFF chỉ chuyển tiếp Idempotency-Key nếu client gửi; backend route hỗ trợ key tùy chọn."),
        ("src/clinicai/api/idempotency.py", 23, 24, "Tài liệu code xác định không có key thì request không được cache/replay."),
        ("src/clinicai/api/idempotency.py", 276, 305, "Guard không có key trả chế độ không cache."),
        ("src/clinicai/services/booking_service.py", 601, 619, "Service kiểm tra đặt trùng cùng bệnh nhân/cùng slot trước khi ghi."),
        ("supabase/migrations/20260805000007_appointment_patient_slot_unique.sql", 67, 69, "Partial unique index bảo vệ cùng slot nếu migration đã được áp dụng."),
    ])
    fe023["summary"] = "Các màn đặt cờ gửi trước fetch nhưng chỉ dọn state sau khi promise resolve. Fetch/JSON reject có thể giữ nút disabled và để kết quả thao tác ở trạng thái chưa biết. Pattern đã xác nhận tại ThaiKy, BaoXepBacSi, DauUuTien, LichTrungCuaKhach và form đặt/đổi lịch AppointmentBooking."
    fe023["trigger"] = "Offline, timeout, connection reset hoặc lỗi parse response khi lưu thai kỳ, đổi bác sĩ, đặt ưu tiên, hủy lịch hoặc tạo/đổi lịch hẹn."
    fe023["impact"] = "Nhân viên có thể không biết thao tác đã commit chưa và nút có thể bị khóa cho tới khi component remount. Riêng đặt lịch, UI hiện không gửi khóa idempotency nên không lấy lại được response gốc sau khi mất phản hồi; service và partial unique index có guard cùng người/cùng giờ, vì vậy không có căn cứ kết luận retry tạo lịch trùng."
    fe023["recommendation"] = "Dọn trạng thái chờ trong finally nhưng biểu diễn riêng kết quả chưa xác định. Với thao tác ghi, đối soát trạng thái từ máy chủ trước retry; riêng đặt lịch, tạo Idempotency-Key ổn định cho một intent và dùng lại qua retry để lấy lại cùng biên nhận."
    fe023["acceptance"] = "Component tests mô phỏng fetch reject và JSON reject: pending được dọn, trạng thái chưa xác định hiện rõ; thao tác đặt lịch retry dùng lại cùng key và nhận lại cùng biên nhận, đồng thời bảo đảm không nhân đôi bản ghi. Kiểm tra guard duplicate hiện có vẫn hoạt động."
    fe023["validation"]["result"] = "Static trace xác nhận pending chỉ được reset sau response ở năm màn; booking BFF/backend hỗ trợ idempotency nhưng màn AppointmentBooking không gửi key. Backend duplicate guard/index giảm nguy cơ tạo cùng slot, không thay thế việc replay biên nhận."
    fe023["validation"]["limitations"] = "Chưa chạy component, network fault-injection hoặc DB concurrency test. Chưa xác minh migration unique index đã áp dụng trên production; không kết luận có duplicate booking từ pattern này."
    fe023["main_validation"]["note"] = "Pattern pending sau fetch reject còn trên main ghim ở năm màn; AppointmentBooking không phát key idempotency. Duplicate guard được đọc và không ủng hộ kết luận tạo lịch trùng; chưa tái hiện lỗi mạng."

    findings.extend(additions)
    save("PHAT-HIEN.json", findings)

    reviewed = {
        "src/dashboard/app/(dashboard)/patients/AppointmentBooking.tsx": ("traced", [(287, 355, "FE-023 pending lifecycle")]),
        "src/dashboard/app/api/appointments/route.ts": ("traced", [(176, 209, "FE-023 optional idempotency forwarding")]),
        "src/clinicai/api/idempotency.py": ("traced", [(23, 24, "FE-023 optional key contract"), (276, 305, "FE-023 no-key behavior")]),
        "src/clinicai/services/booking_service.py": ("traced", [(601, 619, "FE-023 duplicate guard; no duplicate claim")]),
        "supabase/migrations/20260805000007_appointment_patient_slot_unique.sql": ("traced", [(67, 69, "FE-023 concurrent duplicate guard; deployment unverified")]),
        "src/dashboard/app/(dashboard)/truong-ca/QueuesClient.tsx": ("read", [(1, 449, "full-file read")]),
        "src/dashboard/app/api/dispatch-read/route.ts": ("read", [(1, 52, "full-file read")]),
        "src/clinicai/api/v1/routers/dispatch.py": ("traced", [(86, 98, "FE-026 history response contract")]),
        "src/dashboard/tests/truong-ca-phong-ui-boundary.test.mts": ("read", [(1, 52, "full-file read")]),
        "src/dashboard/app/(dashboard)/ops/ToanCanh.tsx": ("read", [(1, 92, "full-file read")]),
        "src/dashboard/app/(dashboard)/ops/PortalBoard.tsx": ("traced", [(355, 422, "ops infrastructure refresh flow"), (513, 541, "OPS dashboard metric rendering")]),
        "src/dashboard/app/(dashboard)/home/page.tsx": ("traced", [(377, 407, "FE-004 KPI fallback"), (456, 459, "FE-004 source error detection"), (518, 525, "FE-004 visible error banner")]),
        "src/dashboard/components/ui/OSoXuHuong.tsx": ("read", [(1, 65, "full-file read")]),
        "src/dashboard/tests/goi-trang-chu-boundary.test.mts": ("read", [(1, 83, "full-file read")]),
        "src/clinicai/api/v1/routers/ops.py": ("traced", [(132, 143, "OPS-008 response shape")]),
        "src/clinicai/services/kho_loi.py": ("traced", [(155, 171, "OPS-008 filtering, order and cap")]),
        "src/dashboard/app/api/ops/theo-doi/route.ts": ("read", [(1, 42, "full-file read")]),
        "src/dashboard/app/(dashboard)/ops/LoiCanhBao.tsx": ("traced", [(48, 60, "OPS-008 client type"), (80, 103, "OPS-008 load/error contract"), (201, 220, "OPS-008 list/empty rendering")]),
        "src/tests/services/test_theo_doi_pha_1_db.py": ("traced", [(35, 90, "OPS-008 related tests lack cap coverage")]),
        "src/tests/unit/test_theo_doi_pha_1.py": ("read", [(1, 104, "full-file read")]),
        "src/tests/api/test_ops_api.py": ("read", [(1, 92, "full-file read")]),
        "src/dashboard/tests/menu-lich-tai-cho-boundary.test.mts": ("read", [(1, 141, "full-file read; unrelated path uses an idempotency key")]),
    }
    files = {item["path"]: item for item in scope["files"]}
    coverage_rows = []
    for path, (level, ranges) in reviewed.items():
        item = files.get(path)
        if not item:
            raise SystemExit(f"Pinned ledger path missing: {path}")
        raw = (SNAPSHOT / path).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        line_count = len(raw.decode().splitlines())
        if item.get("sha256") and item["sha256"] != digest:
            raise SystemExit(f"Ledger/source hash mismatch: {path}")
        item["sha256"] = digest
        item["lines"] = line_count
        prior = item["status"]
        if level == "read":
            item["status"] = "read"
            item["full_file_read"] = True
        elif prior not in {"read", "excluded"}:
            item["status"] = "traced"
        item["method"] = (item.get("method", "") + " | Round 26: " + "; ".join(p for _, _, p in ranges)).strip(" |")
        item["round26_note"] = "Exact-main evidence; selected spans and full-read status recorded in blocks/round26.coverage.json."
        coverage_rows.append({
            "path": path,
            "status": item["status"],
            "prior_status": prior,
            "full_file_read_this_round": level == "read",
            "read_level_this_round": "read" if level == "read" else "traced",
            "ranges": [{"start": start, "end": end, "purpose": purpose} for start, end, purpose in ranges],
            "sha256": digest,
            "line_count": line_count,
        })
    save("MAIN-PHAM-VI.json", scope)

    coverage = {
        "schema_version": 1,
        "audit": "round26_static_exact_main_dashboard_ops_visibility",
        "snapshot": {"path": str(SNAPSHOT), "sha": PIN},
        "review_mode": "read_only_static_exact_main",
        "scope": ["unknown-versus-zero KPI presentation", "booking request pending/idempotency receipt", "dispatch history read state", "operations grouped-error cap"],
        "tests_run": False,
        "runtime_db_vps_secrets_phi_touched": False,
        "coverage_note": "Two findings added (FE-026, OPS-008); FE-004 broadened across reports/ops/home and FE-023 across AppointmentBooking. Exact-main static only; no ClinicAI tests/runtime was run.",
        "held_observations": [
            "OPS-REFRESH-SCOPE-001: PortalBoard ‘Làm mới’ refreshes /api/ops/summary only, while Toàn cảnh metrics arrive as server-rendered props. Whether users expect it to refresh metrics is an unresolved UI contract; no stale production observation, so no finding.",
            "OPS-ERROR-VOLUME-001: More than 100 visible unresolved grouped errors is the condition for OPS-008 impact; production group count has not been measured.",
        ],
        "files": coverage_rows,
    }
    save("blocks/round26.coverage.json", coverage)
    save("blocks/round26_findings.json", additions)
    (ROOT / "blocks/round26.md").write_text(
        "# Round 26 — static exact-main dashboard and operations review\n\n"
        f"Snapshot `{PIN}`. Chỉ đọc nguồn ghim; không chạy test ClinicAI/API/DB/provider/VPS/prod, không đọc secrets/PHI.\n\n"
        "## Findings tích hợp\n\n"
        "- `FE-026` (LOW): panel lịch sử điều phối có thể giữ ‘Đang tải…’ khi backend lỗi; retry chỉ gián tiếp theo thay đổi queue/remount. Panel phụ; chưa có tác động lâm sàng được chứng minh.\n"
        "- `OPS-008` (MEDIUM, điều kiện): danh sách nhóm lỗi lấy tối đa 100 dòng nhưng không có metadata phân trang; volume production chưa kiểm.\n"
        "- Mở rộng `FE-004`: Báo cáo và Toàn cảnh biến null thành empty/0; Trang chủ cũng render KPI fallback 0 nhưng có banner lỗi riêng.\n"
        "- Mở rộng `FE-023`: AppointmentBooking không dọn pending khi fetch/JSON reject và không gửi Idempotency-Key. Service và partial unique index có duplicate guard; không kết luận retry tạo lịch trùng.\n\n"
        "## Held observations\n\n"
        "Nút Làm mới của PortalBoard chỉ đọc lại trạng thái hạ tầng trong khi số liệu Toàn cảnh là props phía server; contract mong đợi chưa rõ. Tác động OPS-008 cần hơn 100 nhóm đang xem; production volume chưa đo.\n\n"
        "Hashes, excerpt, path-level review status và dòng test được đọc ghi ở `round26.coverage.json`; findings mới nằm trong `round26_findings.json` và canonical `../PHAT-HIEN.json`. Không chạy test.\n"
    )

    state = load("STATE.json")
    state["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    state["status"] = "in_progress"
    state["phase"] = "round26_dashboard_ops_integrated_report_qa_pending_source_audit_incomplete"
    state["next_action"] = "Tiếp tục exact-main paths còn scanned/inventoried: patient assignment/tenant onboarding, migration/RLS và các API/service chưa semantic-read. Sau khi static review đủ, đánh giá các synthetic validation trên disposable environment. Full source audit chưa hoàn tất."
    state["report_status"] = "v0.49 evidence integrated; HTML/ZIP QA pending; static source audit incomplete"
    state["report_version"] = "v0.49"
    state["report_round_summary"] = "Round 26 thêm FE-026 và OPS-008, mở rộng FE-004/FE-023. Exact-main static; không chạy ClinicAI tests/runtime, DB, provider hoặc production. Finding OPS-008 phụ thuộc volume >100 chưa được đo; booking duplicate không bị khẳng định do service/index guard."
    state["blocks"]["round26"] = {
        "status": "round26_static_review_integrated; report_qa_pending; full_audit_open",
        "notes": "blocks/round26.md",
        "findings": "PHAT-HIEN.json: FE-026, OPS-008; FE-004 and FE-023 expanded",
        "coverage": "blocks/round26.coverage.json",
        "next": "Continue unread patient assignment/tenant onboarding, migration/RLS and API/service paths; audit remains incomplete.",
    }
    held = state.setdefault("held_observations", [])
    for item in coverage["held_observations"]:
        if item not in held:
            held.append(item)

    severity = Counter(item["severity"] for item in findings)
    levels = Counter(item["evidence_level"] for item in findings)
    main_counts = Counter(item["main_validation"]["status"] for item in findings)
    path_counts = Counter(item["status"] for item in scope["files"])
    suffixes = {".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sql", ".sh", ".bash", ".go", ".rs", ".java", ".kt", ".css", ".html"}
    code_files = [item for item in scope["files"] if Path(item["path"]).suffix.lower() in suffixes]
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
        "new_findings_v049": [item["id"] for item in additions],
        "reviewed_slice_v049": f"Round 26: {len(reviewed)} path records; two findings, FE-004/FE-023 expanded; exact-main static only.",
    })
    state["artifacts"]["qa"] = "Pending v0.49 structural/evidence and desktop/mobile report-only QA."
    state["artifacts"]["integration_script"] = "Round 26 exact-main evidence/coverage generated by integrate_round26.py; validator checks source hashes and excerpts."
    state["artifacts"]["html_sha256"] = "pending v0.49 rebuild"
    state["artifacts"]["bundle_entries"] = "pending v0.49 final rebuild"
    state["artifacts"]["bundle_integrity"] = "Pending final v0.49 audit-only ZIP verification."
    save("STATE.json", state)

    with (ROOT / "NHAT-KY.md").open("a") as handle:
        handle.write(
            "\n\n## Round 26 — 20/10/2026, v0.49 draft\n\n"
            "- Thêm FE-026 và OPS-008; mở rộng FE-004 (Báo cáo/Toàn cảnh/Trang chủ) và FE-023 (AppointmentBooking).\n"
            "- Booking không gửi idempotency key từ AppointmentBooking; service duplicate check và partial unique index là guard nên không kết luận tạo lịch trùng. OPS-008 chỉ gây mất hiển thị nếu có trên 100 nhóm trong tập lọc; production volume chưa đo.\n"
            "- Coverage theo hash và phạm vi đọc ở `blocks/round26.coverage.json`; không chạy test/runtime. Full audit tiếp tục mở; HTML/ZIP phải rebuild sau checkpoint này.\n"
        )

    counts_text = (
        f"Risk register {len(findings)} ({severity['HIGH']} HIGH, {severity['MEDIUM']} MEDIUM, {severity['LOW']} LOW); "
        f"main status {main_counts['still_present_on_main']}/{main_counts['partially_addressed_on_main']}/{main_counts['addressed_on_main']}. "
        f"Coverage {len(scope['files']):,} paths: {path_counts['read']:,} read, {path_counts['traced']:,} traced, {path_counts['scanned']:,} scanned, {path_counts['inventoried']:,} inventoried, {path_counts['excluded']:,} excluded."
    )
    (ROOT / "TIEP-TUC.md").write_text(
        f"# CURRENT HANDOFF — v0.49 (20/10/2026)\n\nExact-main `{PIN}`. {counts_text} Đây là trạng thái path-level, không phải tỷ lệ hành vi đã hiểu. Full source audit vẫn chưa xong.\n\n"
        "Round 26 thêm FE-026, OPS-008; mở rộng FE-004 và FE-023. Chi tiết: `blocks/round26.md`, `blocks/round26.coverage.json`, `blocks/round26_findings.json`. Finding không nói booking retry tạo lịch trùng; `/ops/loi` cap ảnh hưởng còn phụ thuộc volume chưa đo.\n\n"
        "HTML và ZIP cần rebuild/QA sau cập nhật này. Không chạy ClinicAI tests/API/DB/provider/VPS/prod; không đọc secrets/PHI. ZIP chỉ có hồ sơ audit, không có repo/Git history; phải giữ source exact-main để tiếp tục. Working tree gốc có WIP và không dùng làm evidence.\n\n"
        "## Tiếp quản khi đổi tài khoản\n\nĐọc `BAT-DAU-TU-DAY.md`, `STATE.json`, file này, `NHAT-KY.md`, `MAIN-PHAM-VI.json`, `PHAT-HIEN.json`, `TEST-RUNS.json`, rồi `blocks/round26.md` và `blocks/round26.coverage.json`. Tiếp tục từ exact-main SHA ghim; không coi `scanned` là đã đọc.\n\n"
        "## Việc kế tiếp\n\n1. Dựng HTML v0.49, chạy structural/evidence validator và browser QA chỉ trên báo cáo; dựng/verify ZIP audit-only.\n2. Tiếp tục patient assignment/tenant onboarding, migration/RLS và API/service còn scanned/inventoried.\n3. Full source audit chưa hoàn tất; chưa chạy tests/runtime mới trong round này.\n"
    )

    resume = (ROOT / "BAT-DAU-TU-DAY.md").read_text().splitlines()
    resume[:9] = [
        "# Trạng thái hiện hành — 20/10/2026, checkpoint v0.49",
        "",
        "## Checkpoint v0.49 — tiếp quản nhanh",
        "",
        f"Main ghim: `{PIN}`. {counts_text} Nhóm code-like: {code_counts['read']} read, {code_counts['traced']} traced một phần, {code_counts['scanned']} scanned, {code_counts['inventoried']} inventoried. Đây là coverage theo path; full source audit chưa xong.",
        "",
        "Round 26 thêm FE-026 và OPS-008; mở rộng FE-004/FE-023. Static exact-main; không chạy ClinicAI tests/API/DB/provider/VPS/prod và không đọc secrets/PHI. HTML/ZIP cần rebuild + QA report-only. Chi tiết: `blocks/round26.md`, `blocks/round26.coverage.json`, `blocks/round26_findings.json`.",
        "",
        "Khi đổi tài khoản: đọc `STATE.json`, `TIEP-TUC.md`, `NHAT-KY.md`, `PHAT-HIEN.json`, `MAIN-PHAM-VI.json`, `TEST-RUNS.json` và block round26. ZIP không chứa source/Git history; giữ repo exact SHA ghim. Không dùng WIP checkout ban đầu làm evidence.",
    ]
    (ROOT / "BAT-DAU-TU-DAY.md").write_text("\n".join(resume) + "\n")
    print(f"Integrated {len(additions)} findings, expanded FE-004/FE-023, reviewed {len(reviewed)} path records")


if __name__ == "__main__":
    main()
