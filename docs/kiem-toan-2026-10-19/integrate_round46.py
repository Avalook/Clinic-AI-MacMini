"""Integrate read-only exact-main booking/auth/payment review into the audit."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = Path("/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini")
SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"


def load(name: str):
    return json.loads((ROOT / name).read_text())


def save(name: str, data) -> None:
    (ROOT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def source(path: str) -> tuple[bytes, list[str]]:
    raw = subprocess.check_output(["git", "show", f"{SHA}:{path}"], cwd=REPO)
    return raw, raw.decode("utf-8").splitlines()


def proof(path: str, start: int, end: int, detail: str) -> dict:
    raw, lines = source(path)
    if not 1 <= start <= end <= len(lines):
        raise ValueError(f"Invalid pinned range {path}:{start}-{end} ({len(lines)} lines)")
    return {
        "path": path,
        "line": start,
        "end_line": end,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "excerpt": "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1)),
        "detail": detail,
        "lines": len(lines),
    }


def add_proofs(finding: dict, specs: list[tuple[str, int, int, str]]) -> list[dict]:
    added = []
    for path, start, end, detail in specs:
        item = proof(path, start, end, detail)
        key = (path, start, end)
        if not any((x["path"], x["line"], x["end_line"]) == key for x in finding["evidence"]):
            finding["evidence"].append({k: item[k] for k in ("path", "line", "end_line", "detail")})
        main_items = finding["main_validation"].setdefault("evidence", [])
        if not any((x["path"], x["line"], x["end_line"]) == key for x in main_items):
            main_items.append({k: item[k] for k in ("path", "line", "end_line", "sha256", "excerpt")})
        finding.setdefault("source_hashes", {})[path] = item["sha256"]
        added.append(item)
    return added


def append_once(value: str, addition: str) -> str:
    return value if addition in value else value + addition


def append_item_once(items: list, item: str) -> None:
    if item not in items:
        items.append(item)


def main() -> None:
    findings = load("PHAT-HIEN.json")
    by_id = {item["id"]: item for item in findings}

    reschedule_specs = [
        ("src/dashboard/app/(dashboard)/patients/AppointmentBooking.tsx", 290, 310,
         "First-party reschedule form sends PATCH without an idempotency key."),
        ("src/dashboard/app/api/appointments/route.ts", 267, 309,
         "BFF proxies appointment PATCH without forwarding or creating an Idempotency-Key."),
        ("src/clinicai/api/v1/routers/booking.py", 718, 744,
         "Lifecycle PATCH route accepts the reschedule action without an idempotency guard/key."),
        ("src/clinicai/services/booking_service.py", 1837, 1855,
         "Every accepted reschedule builds a patch with the requested slot, including when it already equals the current slot."),
        ("src/clinicai/services/booking_service.py", 1116, 1143,
         "Each accepted action writes an event_log record and calls the business-event publisher in the same transaction."),
        ("src/clinicai/services/booking_service.py", 2887, 2923,
         "Each reschedule inserts appointment_doi_lich and emits appointment.rescheduled; retry can record target→same target."),
        ("src/clinicai/services/booking_service.py", 417, 423,
         "The reschedule transition preserves the current live status, so the same target can be submitted again."),
        ("src/clinicai/events/emit.py", 178, 228,
         "Each publish generates a fresh UUID event_id and inserts a new domain_event/delivery row."),
        ("src/clinicai/services/notification_relay.py", 128, 145,
         "Notification relay independently selects each unpublished event_log row."),
        ("src/clinicai/services/notification_relay.py", 216, 240,
         "A matching reschedule event is sent and then marked published per event row."),
        ("src/clinicai/services/notification_templates.py", 107, 112,
         "appointment.rescheduled has an operations notification template."),
    ]
    location_specs = [
        ("src/dashboard/app/(auth)/chon-co-so/page.tsx", 26, 34,
         "Selector fetches /me/co-so; a null result redirects before rendering selectable active locations."),
        ("src/dashboard/lib/co-so.ts", 9, 23,
         "A syntactically valid clinicai_location cookie is forwarded as X-Location-ID without checking whether it remains active."),
        ("src/dashboard/lib/backend-proxy.ts", 256, 267,
         "fetchFromBackend forwards the selected location and converts every non-2xx response to null."),
        ("src/clinicai/api/identity.py", 531, 538,
         "Backend identity resolution rejects a selected location that is inactive or outside the current clinic."),
        ("src/clinicai/api/v1/routers/identity.py", 74, 78,
         "The location-list endpoint uses the same identity dependency, so an invalid selected-location header blocks recovery."),
        ("src/dashboard/app/(auth)/chon-co-so/actions.ts", 10, 24,
         "Selection writes the chosen location cookie; this action does not offer a recovery path when the list endpoint fails."),
    ]
    auth_form_specs = [
        ("src/dashboard/app/(auth)/forgot-password/ForgotPasswordForm.tsx", 20, 39,
         "Forgot-password sets loading before awaiting Supabase and has no catch/finally for rejected calls."),
        ("src/dashboard/app/(auth)/reset-password/ResetPasswordForm.tsx", 31, 44,
         "Reset-password sets loading before updateUser and does not clear it if the promise rejects."),
        ("src/dashboard/app/(auth)/reset-password/ResetPasswordForm.tsx", 46, 73,
         "Loading resets only on resolved error/success branches; a rejected network promise skips both."),
    ]
    sec027_specs = [
        ("src/clinicai/api/v1/routers/booking.py", 62, 66,
         "_ACTION_GUARD is get_current_identity, not a booking capability guard."),
        ("src/clinicai/api/v1/routers/booking.py", 226, 231,
         "Doctor assignment worklist endpoint depends only on the identity guard."),
        ("src/clinicai/api/v1/routers/booking.py", 257, 267,
         "The same-clinic worklist query returns patient name/code/phone and service metadata."),
        ("src/dashboard/app/api/appointments/route.ts", 16, 28,
         "BFF GET proxies the worklist but adds no capability check; a page-level gate is not an API boundary."),
    ]

    fe23 = by_id["FE-023"]
    fe23["title"] = "Một số thao tác và form xác thực có thể kẹt khi request lỗi mạng"
    fe23["summary"] = append_once(fe23["summary"], (
        " Round 46 xác nhận cùng pattern trong hai form khôi phục mật khẩu: promise Supabase reject trước khi reset loading."
    ))
    fe23["trigger"] = append_once(fe23["trigger"], " Hoặc request gửi email đặt lại mật khẩu / cập nhật mật khẩu reject trước khi hoàn tất.")
    fe23["impact"] = append_once(fe23["impact"], (
        " Ở form khôi phục mật khẩu, người dùng có thể phải tải lại màn để thử lại; chưa thấy bypass xác thực."
    ))
    fe23["validation"]["result"] = append_once(fe23["validation"]["result"], (
        " Round 46 đọc thêm forgot/reset forms và xác nhận loading chỉ được dọn ở nhánh promise đã resolve."
    ))
    fe23["validation"]["limitations"] = append_once(fe23["validation"]["limitations"], (
        " Chưa chạy component hoặc mô phỏng Supabase rejection; không kết luận phiên xác thực bị vượt qua."
    ))
    append_item_once(fe23.setdefault("related_tests", []),
        "src/dashboard/app/(auth)/forgot-password và reset-password forms: source đã đọc, không có test network rejection trong scope; không chạy."
    )
    add_proofs(fe23, auth_form_specs)
    fe23["main_validation"]["note"] = append_once(fe23["main_validation"]["note"], (
        " Round 46 mở rộng cùng lỗi pending-state sang hai form khôi phục mật khẩu; ảnh hưởng là khả dụng UI có điều kiện, không phải auth bypass."
    ))

    sec27 = by_id["SEC-027"]
    sec27["summary"] = append_once(sec27["summary"], (
        " Round 46 bổ sung GET /appointments/cho-xep-bac-si: _ACTION_GUARD thực chất là get_current_identity; route trả tên, mã, số điện thoại và dịch vụ của lịch chờ xếp trong cùng clinic/location, trong khi BFF chỉ proxy."
    ))
    sec27["trigger"] = append_once(sec27["trigger"], (
        " Quản trị viên chưa có capability đọc danh sách gọi trực tiếp API lịch chờ xếp bác sĩ bằng session nội bộ; quyền ở trang UI không bảo vệ endpoint."
    ))
    sec27["impact"] = append_once(sec27["impact"], (
        " Endpoint chờ xếp bác sĩ thêm PII liên hệ bệnh nhân cùng clinic/location. Không thấy bằng chứng truy cập chéo clinic; caller dashboard hiện tại và reachability runtime chưa được kiểm chứng."
    ))
    sec27["validation"]["result"] = append_once(sec27["validation"]["result"], (
        " Round 46 xác nhận route worklist phụ thuộc identity-only guard, query trả patient phone/name/code, và BFF không thêm capability gate; test đang kiểm nội dung/UI chứ không negative-authorization route."
    ))
    sec27["validation"]["limitations"] = append_once(sec27["validation"]["limitations"], (
        " Chưa chạy JWT/HTTP role matrix; kết luận chỉ về static same-clinic/location boundary."
    ))
    sec27["recommendation"] = append_once(sec27["recommendation"], (
        " Thêm capability endpoint-level cho danh sách chờ xếp bác sĩ và giữ projection tối thiểu theo quyền người gọi."
    ))
    sec27["acceptance"] = append_once(sec27["acceptance"], (
        " Negative route tests xác nhận vai thiếu capability bị từ chối trực tiếp ở API dù gọi bỏ qua trang; vai được cấp chỉ nhận clinic/location và PII tối thiểu."
    ))
    append_item_once(sec27.setdefault("related_tests", []),
        "src/dashboard/tests/hang-cho-bac-si-boundary.test.mts — đọc, không chạy; kiểm query/nhãn worklist, không kiểm quyền API trực tiếp."
    )
    add_proofs(sec27, sec027_specs)
    sec27["main_validation"]["note"] = append_once(sec27["main_validation"]["note"], (
        " Round 46 mở rộng tới worklist chờ xếp bác sĩ cùng clinic/location: route chỉ dùng identity guard và trả phone/name/code; chưa kiểm runtime."
    ))

    new_specs = [
        (
            "src/dashboard/app/(auth)/chon-co-so/page.tsx", 26, 34,
            "When the selected location has been disabled, failed /me/co-so data leads this page to redirect before an active location choice is rendered.",
        ),
        (
            "src/dashboard/lib/co-so.ts", 9, 23,
            "The dashboard forwards a valid-UUID location cookie as X-Location-ID even when that location has since been disabled.",
        ),
        (
            "src/dashboard/lib/backend-proxy.ts", 256, 267,
            "The server-side fetch returns null on backend non-2xx and does not clear the stale location cookie.",
        ),
        (
            "src/clinicai/api/identity.py", 531, 538,
            "Backend correctly rejects a disabled/out-of-clinic location; this secure rejection is the state that needs UI recovery.",
        ),
        (
            "src/clinicai/api/v1/routers/identity.py", 74, 78,
            "The endpoint to list locations resolves identity using the same current-location header, so it cannot return options under the stale context.",
        ),
        (
            "src/dashboard/app/(auth)/chon-co-so/actions.ts", 10, 24,
            "The normal form action writes a selected active location; it is unreachable when the page redirects on the failed list fetch.",
        ),
    ]
    new = {
        "id": "FE-027",
        "title": "Cookie cơ sở đã bị tắt có thể làm người dùng mắc kẹt ngoài màn chọn cơ sở",
        "severity": "LOW",
        "evidence_level": "confirmed_static",
        "category": "ui/location-context-recovery",
        "summary": (
            "Dashboard tiếp tục gửi clinicai_location thành X-Location-ID sau khi cơ sở bị tắt. Backend từ chối đúng, nhưng endpoint /me/co-so cũng bị chặn; BFF biến lỗi thành null và trang chọn cơ sở redirect trước khi vẽ các cơ sở còn hoạt động. Cookie cũ không được xóa trong đường phục hồi này."
        ),
        "trigger": (
            "Nhân viên đang chọn cơ sở A; quản lý tắt A trong khi phiên vẫn còn cookie clinicai_location=A. Khi nhân viên vào /chon-co-so hoặc cần đổi cơ sở, /me/co-so trả lỗi qua identity guard, trang redirect, và request tiếp tục mang cookie A."
        ),
        "impact": (
            "Nhân viên không thể chọn cơ sở đang hoạt động khác trong cùng phòng khám qua luồng bình thường và có thể cần đăng xuất/đăng nhập để cookie được xóa. Đây là lỗi khả dụng cùng tenant; backend vẫn chặn cơ sở tắt, không có bằng chứng vượt quyền hoặc truy cập dữ liệu sai cơ sở."
        ),
        "evidence": [],
        "validation": {
            "method": "exact_main_static_cookie_to_identity_and_selector_trace",
            "command": None,
            "result": (
                "Trace cookie → X-Location-ID → backend active-location check → /me/co-so → BFF null → redirect. Login action có đường xóa cookie; test hiện có kiểm 403 của location inactive nhưng không kiểm UX phục hồi."
            ),
            "limitations": (
                "Static exact-main only; chưa chạy Next/FastAPI hoặc mô phỏng location toggle trong phiên hoạt động. Tác động khả dụng có workaround logout/login; không phải authorization bypass."
            ),
        },
        "recommendation": (
            "Khi /me/co-so trả mã stale/disabled-location, xóa hoặc bỏ qua cookie cũ rồi hiển thị danh sách cơ sở còn hoạt động. Có thể cung cấp endpoint đổi cơ sở không dùng location header làm đầu vào identity; backend vẫn phải xác minh membership và is_active ở lần chọn và mọi request nghiệp vụ."
        ),
        "acceptance": (
            "Integration/UI test: giữ phiên đăng nhập, tắt cơ sở đang chọn, mở trang chọn cơ sở; người dùng thấy các cơ sở còn hoạt động và chuyển được sang một cơ sở hợp lệ. Request mang ID cơ sở tắt vẫn nhận 403 và không trả dữ liệu."
        ),
        "alignment": [
            "Unknown period ngắn hơn: ngữ cảnh cơ sở không hợp lệ phải được nhận diện và có đường phục hồi nhìn thấy được.",
            "Ít gián đoạn sai lúc hơn: nhân viên không cần tự đoán đăng xuất mới đổi được nơi làm việc.",
        ],
        "related_tests": [
            "src/tests/test_identity.py:394-456 — đọc, không chạy; kiểm cơ sở lạ/tắt bị 403, không kiểm trang selector phục hồi.",
            "src/dashboard/tests/identity-authority-boundary.test.mts:1-44 — đọc, không chạy; không kiểm stale location cookie.",
        ],
        "source_hashes": {},
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": SHA,
            "status": "still_present_on_main",
            "note": (
                "Main ghim tĩnh xác nhận cookie cũ được forward, backend reject location inactive, endpoint list dùng cùng identity và selector redirect khi BFF trả null. Chưa kiểm browser/runtime; workaround logout/login tồn tại."
            ),
            "evidence": [],
            "production_verified": False,
        },
        "related_findings": ["FE-009"],
    }
    new_proofs = add_proofs(new, new_specs)
    findings.append(new)

    clin = {
        "id": "CLIN-057",
        "title": "Gửi lại PATCH đổi lịch có thể nhân đôi lịch sử và sự kiện đổi lịch",
        "severity": "LOW",
        "evidence_level": "confirmed_static",
        "category": "booking/idempotency-event-integrity",
        "summary": (
            "Luồng đổi lịch gửi PATCH không có idempotency key. Nếu lần đầu đã commit nhưng mất response, lần gửi lại cùng giờ vẫn được chấp nhận vì status được giữ và service ghi lại appointment_doi_lich, event_log và domain_event với event_id mới."
        ),
        "trigger": (
            "Nhân viên đổi lịch thành công ở backend nhưng request timeout/mất phản hồi; sau khi tải lại hoặc mở lại form, gửi cùng appointment_id và target slot lần nữa. Service đọc lịch đang ở chính target đó, vẫn build/update patch và chạy các side effect lịch sử/sự kiện."
        ),
        "impact": (
            "Bảng lịch vẫn giữ một trạng thái cuối đúng, nhưng có thể có dòng đổi lịch target→target, domain event trùng và thông báo vận hành lặp. Điều này làm lịch sử/notification kém tin cậy; không có bằng chứng tạo appointment thứ hai hay bệnh nhân nhận tin nhắn trực tiếp từ finding này."
        ),
        "evidence": [],
        "validation": {
            "method": "exact_main_static_retry_to_history_outbox_trace",
            "command": None,
            "result": (
                "Trace first-party form → BFF PATCH → FastAPI action → preserved status and unconditional reschedule side effects. Each domain event gets a new UUID; event_log notifications are polled per unpublished row and appointment.rescheduled has an operations template."
            ),
            "limitations": (
                "Chưa fault-inject mất response hoặc chạy DB/event relay. Đây là hành vi tĩnh có điều kiện khi caller gửi lại; không kết luận đã xảy ra trong production. Duplicate Telegram/consumer delivery phụ thuộc relay/config; không có căn cứ nói bệnh nhân nhận thông báo trực tiếp."
            ),
        },
        "recommendation": (
            "Gắn idempotency key ổn định với một intent reschedule, lưu command receipt cùng transaction thay đổi lịch/lịch sử/outbox, và trả lại cùng receipt khi replay. Nếu không dùng command receipt, phát hiện payload target đã là trạng thái hiện tại rồi trả no-op có định danh trước khi append side effects."
        ),
        "acceptance": (
            "Integration test với key ổn định: lần đầu commit nhưng client mất response; replay trả cùng kết quả và chỉ có một appointment_doi_lich, một event nghiệp vụ/outbox và một thông báo. Cùng key khác payload bị từ chối; không key theo policy thì lỗi validation rõ."
        ),
        "alignment": [
            "Reality dễ nhìn thấy hơn: lịch sử không ghi một lần đổi giả từ giờ hiện tại sang chính giờ hiện tại.",
            "Quyết định dựa trên bằng chứng tốt hơn: mỗi intent đổi lịch có receipt và một sự kiện nghiệp vụ xác định.",
            "Lỗi lặp lại dần biến thành cải tiến hệ thống: retry sau response-loss không nhân bản lịch sử/outbox.",
        ],
        "related_tests": [
            "src/tests/test_booking_service.py — đọc, không chạy; có transition/PATCH coverage nhưng không thấy retry-after-commit response-loss case.",
            "src/tests/unit/test_idempotency.py — đọc, không chạy; test guard chung, không bao phủ route PATCH appointment.",
            "src/tests/services/test_doi_lich_nhanh_db.py — đọc, không chạy; kiểm POST đổi lịch nhanh, không kiểm PATCH replay.",
        ],
        "source_hashes": {},
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": SHA,
            "status": "still_present_on_main",
            "note": (
                "Exact-main trace xác nhận PATCH first-party thiếu idempotency key; retry cùng target vẫn đi qua transition và ghi lịch sử/event mới. Chưa chạy DB, network fault injection, event relay hoặc production."
            ),
            "evidence": [],
            "production_verified": False,
        },
        "related_findings": ["FE-023", "CLIN-011", "CLIN-024", "INF-007"],
    }
    add_proofs(clin, reschedule_specs)
    findings.append(clin)

    coverage_full = [
        "src/clinicai/core/shifts.py",
        "src/clinicai/api/v1/routers/booking.py",
        "src/clinicai/services/booking_service.py",
        "src/clinicai/api/v1/routers/payment.py",
        "src/clinicai/api/v1/routers/cashier.py",
        "src/clinicai/services/payment_service.py",
        "src/clinicai/services/cashier_scope_service.py",
        "src/clinicai/services/cashier_board_service.py",
        "src/clinicai/services/quay_thu_service.py",
        "src/clinicai/services/hoan_tien_service.py",
        "src/clinicai/api/idempotency.py",
        "src/tests/services/test_cashier_scope_db.py",
        "src/tests/services/test_cashier_board.py",
    ]
    coverage_ranges = [
        ("src/clinicai/api/v1/routers/config.py", 839, 1032, "Trace PATCH shift/opening-hours validation and transactional settings write."),
        ("src/clinicai/services/capacity_service.py", 350, 479, "Trace slot generation and filtering against half-open shift windows."),
        ("src/tests/unit/test_kiem_cau_hinh_ca.py", 1, 139, "Read validation cases; no explicit assertion for close time greater than 24:00. Test not run."),
        ("src/dashboard/lib/soat-gio-ca.ts", 37, 135, "Browser/server hour parsing has matching 24-hour bound; route remains server source of truth."),
        ("src/dashboard/app/(dashboard)/settings/GioCaLamViecCard.tsx", 43, 143, "Read state/save flow and catch/finally behavior for settings card."),
        ("src/dashboard/app/(dashboard)/settings/GioCaLamViecCard.tsx", 165, 259, "Read input, warning, and save UI; time entries are text inputs."),
        ("src/tests/unit/test_ba_ca_lam_viec.py", 1, 210, "Read shift conversion and weekday window tests; test not run."),
        ("src/dashboard/app/(dashboard)/patients/AppointmentBooking.tsx", 285, 355, "Read first-party PATCH/POST booking flows; no idempotency key in body/headers."),
        ("src/clinicai/events/catalogue.py", 470, 478, "Reschedule event contract includes from/to appointment time and doctor-change flag."),
        ("src/clinicai/services/notification_relay.py", 128, 257, "Read unpublished event polling and per-event delivery/mark-published path."),
        ("src/clinicai/services/notification_templates.py", 1, 112, "Read operations notification templates; appointment.rescheduled is registered."),
        ("src/clinicai/events/emit.py", 118, 228, "Read event ID creation and event_delivery insertion."),
        ("src/clinicai/api/identity.py", 531, 538, "Read location selector validation in authenticated identity resolution."),
        ("src/clinicai/api/v1/routers/identity.py", 74, 78, "Read /me/co-so endpoint and guard dependency."),
        ("src/dashboard/app/(auth)/chon-co-so/page.tsx", 21, 85, "Read selector loading, redirect, and option rendering."),
        ("src/dashboard/app/(auth)/chon-co-so/actions.ts", 1, 25, "Read location-choice action/cookie write."),
        ("src/dashboard/app/(auth)/login/actions.ts", 80, 105, "Read logout/login cleanup for stale location cookie workaround."),
        ("src/tests/test_identity.py", 394, 456, "Read inactive/invalid location authorization tests; no selector recovery assertion; test not run."),
        ("src/dashboard/tests/identity-authority-boundary.test.mts", 1, 44, "Read identity authority boundary tests; no selector/form network case; test not run."),
        ("src/tests/test_booking_service.py", 1, 120, "Read test structure/transition setup; test not run."),
        ("src/tests/unit/test_idempotency.py", 1, 180, "Read generic idempotency guard tests; PATCH reschedule path not covered; test not run."),
        ("src/tests/services/test_doi_lich_nhanh_db.py", 150, 185, "Read event/history assertions for the separate fast-reschedule POST flow; test not run."),
        ("src/dashboard/tests/hang-cho-bac-si-boundary.test.mts", 1, 80, "Read worklist projection/UI boundary test; no route capability test; test not run."),
    ]

    coverage_items = []
    for path in coverage_full:
        raw, lines = source(path)
        coverage_items.append({
            "path": path,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "lines": len(lines),
            "read_ranges": [{"start": 1, "end": len(lines)}],
            "full_read": True,
            "outcome": "Full read; finding/dedupe decisions recorded in round46.md.",
        })
    for path, start, end, detail in coverage_ranges:
        item = proof(path, start, end, detail)
        coverage_items.append({
            "path": path,
            "sha256": item["sha256"],
            "lines": item["lines"],
            "read_ranges": [{"start": start, "end": end}],
            "full_read": start == 1 and end == item["lines"],
            "outcome": detail,
        })

    # The findings above are the canonical evidence record. Their source ranges
    # are also included in coverage even when they overlap targeted traces.
    for f in (fe23, sec27, new, clin):
        for ev in f["main_validation"]["evidence"]:
            path = ev["path"]
            raw, lines = source(path)
            existing = next((x for x in coverage_items if x["path"] == path and x.get("full_read")), None)
            if existing:
                continue
            entry = next((x for x in coverage_items if x["path"] == path), None)
            read_range = {"start": ev["line"], "end": ev["end_line"]}
            if entry is None:
                coverage_items.append({
                    "path": path,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "lines": len(lines),
                    "read_ranges": [read_range],
                    "full_read": False,
                    "outcome": ev.get("detail", "Evidence range read and hash-checked."),
                })
            elif read_range not in entry["read_ranges"]:
                entry["read_ranges"].append(read_range)

    coverage = {
        "schema_version": 1,
        "round": 46,
        "report_version": "v0.69",
        "snapshot_sha": SHA,
        "mode": "read_only_exact_main_parallel_semantic_review",
        "scope": ["booking/reschedule lifecycle", "auth and location recovery", "cashier/payment/refund", "shift configuration"],
        "method": (
            "Immutable pinned Git blobs via git show. Full reads and targeted ranges are SHA-256/line checked. Tests read-not-run. No ClinicAI runtime/API/DB/provider/VPS/production/secrets/PHI."
        ),
        "result": {
            "new_findings": ["FE-027", "CLIN-057"],
            "extended_findings": ["FE-023", "SEC-027"],
            "deduplicated": [
                "Payment/refund candidates dedupe with INF-007, FIN-001/004/015/016 and DB-007.",
                "Doctor assignment worklist PII adds to SEC-027; no separate ID.",
                "Booking POST no-key replay path remains inside FE-023/CLIN-024; no duplicate appointment proven.",
            ],
            "held_candidates": [
                "Cashier old-date outstanding backlog scope held: comments and DB test indicate intentional cross-day work; owner policy needed.",
                "Unassigned appointment capacity precheck vs trigger retained as policy/source-of-truth question.",
                "Closing hour 24:30 is accepted by validation; no user-visible booking beyond shift/day boundary proved, so not promoted.",
                "Monitor self-health and TKYK file-write assignment remain held from prior rounds.",
            ],
            "full_source_audit_complete": False,
        },
        "full_files": [x for x in coverage_items if x["full_read"]],
        "targeted_traces": [x for x in coverage_items if not x["full_read"]],
        "reviewer_note": (
            "Booking and payment subagents read the assigned full files. Candidate severities reflect conditional same-tenant operational effects; no runtime or production behavior was claimed."
        ),
    }
    save("blocks/round46.coverage.json", coverage)

    round_md = """# Round 46 — exact-main booking, auth/location and payment review

Source SHA: `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Evidence was read from immutable Git blobs with `git show`; the checkout with user WIP was not used as evidence. Tests were read only, never run. No ClinicAI app, API, DB, provider, VPS, production, secrets, or PHI was accessed.

## Decisions

- **Added FE-027 LOW:** stale `clinicai_location` cookie can block the location selector after the selected location is deactivated. Backend correctly rejects the inactive location; the selector/BFF path does not recover or clear the stale context. Same-clinic availability issue, no authorization bypass.
- **Added CLIN-057 LOW:** replaying a committed PATCH reschedule after response loss can append a target-to-same-target history row, a new event/outbox item, and an operations notification. Appointment final state remains one correct row. Conditional on caller retry; no production incident or DB reproduction claimed.
- **Extended FE-023:** same pending-state cleanup gap exists in forgot/reset-password forms. No authentication bypass was found.
- **Extended SEC-027:** doctor-assignment worklist endpoint returns same-clinic patient contact PII behind identity-only guard; page-level gate is not route authorization. Clinic/location scope remains.
- **Deduplicated payments/refunds:** receipt/replay, rounding, tender and invoice company cases remain in INF-007, FIN-001/004/015/016 and DB-007. Cashier cross-day outstanding backlog remains held because source comments and tests indicate the behavior may be intentional; owner policy is needed before changing FIN-019.
- **Held booking capacity question:** unassigned appointments are rejected by service precheck while trigger comments describe exemption; policy/source-of-truth is unclear, so no finding yet.
- **Shift config:** accepted close time `24:30` is outside normal minute-of-day semantics, but the reviewed path still clips visible booking windows at the shift/day bound; insufficient user-visible impact to promote.

## Coverage and limits

Full files, exact line counts, SHA-256 hashes, targeted ranges and dedupe notes are in `blocks/round46.coverage.json`. Booking service/router and payment/cashier services received full reads; auth/location and shift paths received cross-layer targeted traces. Tests were not run and runtime behavior was not validated. The repository audit remains open; path-level coverage is not semantic or behavioral completeness.
"""
    (ROOT / "blocks/round46.md").write_text(round_md)

    manifest = load("MAIN-PHAM-VI.json")
    round_paths = {x["path"]: x for x in coverage_items}
    for record in manifest["files"]:
        item = round_paths.get(record["path"])
        if item is None:
            continue
        if item["full_read"]:
            record["status"] = "read"
            record["full_file_read"] = True
        elif record["status"] in {"scanned", "inventoried"}:
            record["status"] = "traced"
        ranges = ", ".join(f"{r['start']}–{r['end']}" for r in item["read_ranges"])
        note = f"Round 46 exact-main {ranges}; see blocks/round46.coverage.json."
        record["method"] = (record.get("method", "") + " | " + note).strip(" |")
        record["round46_note"] = item["outcome"]
    manifest["last_updated_round"] = 46
    save("MAIN-PHAM-VI.json", manifest)
    save("PHAT-HIEN.json", findings)

    state = load("STATE.json")
    state.update({
        "updated_at": "2026-10-20",
        "status": "in_progress",
        "report_version": "v0.69",
        "phase": "round46_v069_booking_auth_payment_audit_open",
        "report_round_summary": (
            "Round 46 adds FE-027 and CLIN-057; extends FE-023 and SEC-027. Payment/refund and backlog candidates were deduplicated or held by policy."
        ),
        "next_action": (
            "Continue exact-main review of unread or only structurally scanned code, especially authorization/location matrices, clinical lifecycle, migrations/restore and dashboard behavior. Keep the source audit explicitly incomplete until semantic review and validation gaps are resolved."
        ),
        "report_status": "Round46 evidence integrated; report-only QA/package refresh pending; full source audit remains incomplete.",
    })
    state["blocks"]["security"]["status"] = "round46_SEC027_extended_security_review_open"
    state["blocks"]["clinical"]["status"] = "round46_CLIN057_added_booking_replay_review_open"
    state["blocks"]["clinical"]["next"] = "Continue service-order, visit, result and booking transitions; test idempotency/replay and assignment boundaries only in a disposable synthetic environment after static scope review."
    state["blocks"]["finance"]["status"] = "round46_payment_dedupe_cashier_backlog_policy_held"
    state["blocks"]["finance"]["next"] = "Continue settlement/refund/reconciliation review. FIN-019 cashier backlog scope remains a product-policy hold; do not hide intentional cross-day work without owner decision."
    state["blocks"]["frontend"]["status"] = "round46_FE027_added_FE023_extended_review_open"
    state["blocks"]["frontend"]["next"] = "Continue dashboard auth/location recovery, stale async state, and route-vs-page authorization; source-only until runtime scope is explicitly approved."
    state["blocks"]["booking_round46"] = {
        "status": "round46_static_slice_complete_repository_audit_open",
        "findings": "CLIN-057; SEC-027/FE-023/CLIN-024 extended or cross-referenced",
        "coverage": "blocks/round46.coverage.json",
        "next": "Review remaining API/service transition paths and idempotency receipts; no retry runtime test was run.",
    }
    state["blocks"]["auth_location_round46"] = {
        "status": "round46_static_slice_complete_repository_audit_open",
        "findings": "FE-027; FE-023 extended",
        "coverage": "blocks/round46.coverage.json",
        "next": "Test inactive-location recovery and auth form network failures only in a controlled local fixture.",
    }
    state["blocks"]["payment_round46"] = {
        "status": "round46_static_slice_complete_no_new_payment_finding",
        "findings": "Dedupe with INF-007, FIN-001/004/015/016, FIN-019 hold, DB-007",
        "coverage": "blocks/round46.coverage.json",
        "next": "Continue finance reconciliation and resolve shift/backlog policy with owner before changing access scope.",
    }
    save("STATE.json", state)

    (ROOT / "TIEP-TUC.md").write_text(
        "# CURRENT HANDOFF — v0.69, Round 46\n\n"
        f"Evidence source: immutable Git SHA `{SHA}` in `{REPO}`. Primary checkout may contain user WIP; do not use it as evidence. Read source only as `git show <SHA>:<path>`. Only modify audit artifacts under this directory; do not run ClinicAI tests/runtime/API/DB/provider/VPS/production or inspect secrets/PHI.\n\n"
        "Round 46 added FE-027 and CLIN-057; expanded FE-023 and SEC-027. Payment/refund candidates were deduplicated with existing findings; cashier backlog scope, unassigned-booking capacity, and 24:30 opening-hours boundary remain held. Details and exact hashes/ranges are in `PHAT-HIEN.json`, `blocks/round46.md`, and `blocks/round46.coverage.json`.\n\n"
        "Full source audit remains incomplete. Path states are not semantic/behavior coverage. Continue exact-main review of unread or structurally scanned API, service, migrations and dashboard; prioritize assignment/location, clinical lifecycle, recovery and test gaps. Report-only QA/package refresh is pending after integration.\n"
    )
    (ROOT / "BAT-DAU-TU-DAY.md").write_text(
        "# Bắt đầu từ đây — checkpoint v0.69, Round 46\n\n"
        "Đọc `TIEP-TUC.md`, `STATE.json`, `NHAT-KY.md`, `MAIN-PHAM-VI.json`, `PHAT-HIEN.json`, `blocks/round46.md` và `blocks/round46.coverage.json`. Source evidence chỉ từ SHA `" + SHA + "` qua `git show` trong worktree audit; không dùng working-tree WIP làm bằng chứng.\n\n"
        "Round 46 thêm FE-027 và CLIN-057; mở rộng FE-023 và SEC-027. Payment/refund candidates dedupe; cashier backlog scope và booking capacity semantics vẫn held. Tests read-not-run; không runtime/production. Report-only QA/package refresh pending.\n\n"
        "**Full source audit chưa hoàn tất.** Path counts không phải phần trăm hiểu hành vi; chỉ sửa audit artifacts.\n"
    )

    with (ROOT / "NHAT-KY.md").open("a") as handle:
        handle.write(
            "\n\n## Round 46 — 20/10/2026, v0.69 integration\n\n"
            "Read-only exact-main review at SHA `" + SHA + "`. Added FE-027 (stale inactive-location cookie recovery) and CLIN-057 (reschedule replay can duplicate history/events); extended FE-023 to password-reset forms and SEC-027 to the doctor-assignment worklist PII endpoint. Payment/refund review deduplicated with existing findings; cashier backlog, unassigned booking capacity and 24:30 hours validation remain held. Full-file reads and targeted traces are in `blocks/round46.coverage.json`. Tests read-not-run; no ClinicAI runtime/API/DB/provider/VPS/production/secrets/PHI. Full audit remains incomplete. Report-only QA and package refresh pending.\n"
        )

    print(f"Integrated Round 46: {len(findings)} findings, {len(coverage_items)} coverage records")


if __name__ == "__main__":
    main()
