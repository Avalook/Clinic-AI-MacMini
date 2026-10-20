"""Integrate round-20 operational, reminder and ultrasound audit slices.

This script writes only durable audit artifacts. Evidence is read from the
immutable exact-main worktree and every excerpt is fingerprinted.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import integrate_round19 as prior

ROOT = Path(__file__).resolve().parent
SNAPSHOT = prior.SNAPSHOT
PINNED_SHA = prior.PINNED_SHA
CODE_SUFFIXES = prior.CODE_SUFFIXES


def read_json(name: str):
    return json.loads((ROOT / name).read_text())


def write_json(name: str, value) -> None:
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def refs_for(definitions: list[dict], extra: list[tuple[str, int, int, str]]):
    result: dict[str, list[tuple[int, int, str]]] = {}
    for item in definitions:
        for ev in item["evidence"]:
            result.setdefault(ev["path"], []).append(
                (ev["line"], ev["end_line"], ev["detail"])
            )
    for path, start, end, detail in extra:
        result.setdefault(path, []).append((start, end, detail))
    return result


def definitions() -> list[dict]:
    limitations = (
        "Exact-main static source trace only. No ClinicAI application test, DB, HTTP, "
        "browser application, production runtime, secrets or patient data was used in round 20."
    )
    return [
        prior.finding(
            id="OPS-005",
            title="Kết quả gọi tái khám có thể được nhận như đã ghi dù nhật ký CSKH chưa có",
            severity="LOW",
            level="confirmed_static",
            category="recall_outcome_idempotency",
            summary=(
                "Khi UPDATE việc tái khám không còn ở CHO_GOI, service trả HTTP-success "
                "với da_ghi_tu_truoc=true cho mọi trạng thái đã đóng, kể cả KHONG_CAN do "
                "lịch hẹn mới kích hoạt trigger. Nhánh này không INSERT cskh_log; UI chỉ "
                "kiểm res.ok rồi refresh, không đọc payload. Nếu trigger lịch hẹn đóng "
                "hàng trước lúc nhân viên ghi kết quả cuộc gọi, kết quả có thể không vào "
                "nhật ký CSKH nhưng thao tác vẫn trông như đã hoàn tất."
            ),
            trigger=(
                "Một kết quả cuộc gọi đang được gửi đồng thời với việc lịch hẹn mới đóng "
                "cùng recall row, hoặc nhân viên gửi từ tab cũ sau khi row đã ở KHONG_CAN."
            ),
            impact=(
                "Cuộc gọi có thể thiếu trong lịch sử CSKH dù việc tái khám đã đóng; người "
                "dùng không được báo đây là trạng thái đã được lịch hẹn thay thế. Điều kiện "
                "đua hẹp và hàng chờ có thể đã không còn cần xử lý; chưa tái hiện và không "
                "có bằng chứng production."
            ),
            recommendation=(
                "Chỉ trả already_recorded khi có bằng chứng kết quả/nhật ký đã tồn tại. "
                "Trạng thái KHONG_CAN do DA_CO_LICH nên trả kết quả stale/superseded rõ "
                "ràng, để UI thông báo và làm mới; nếu cần giữ lịch sử cuộc gọi độc lập "
                "với hàng chờ thì ghi attempt/audit riêng có idempotency."
            ),
            acceptance=(
                "Synthetic test: ghi kết quả thắng trigger thì có đúng một recall row và "
                "CSKH log; trigger thắng thì API trả trạng thái superseded, không nói đã "
                "ghi từ trước, UI hiện thông báo và tải lại; gửi lặp sau khi đã ghi phải "
                "không tạo log trùng."
            ),
            note=(
                "Static exact-main trace: trigger có thể chuyển CHO_GOI → KHONG_CAN; nhánh "
                "không update trả da_ghi_tu_truoc cho trạng thái đã đóng, trước đoạn INSERT "
                "CSKH; UI chỉ kiểm HTTP status rồi refresh. Chỉ là race/stale-action candidate."
            ),
            refs=[
                (
                    "src/clinicai/services/recall_job_service.py",
                    282,
                    300,
                    "Nhánh UPDATE không khớp trả thành công cho mọi trạng thái đã đóng, không ghi CSKH log.",
                ),
                (
                    "supabase/migrations/20260929950000_hen_tai_kham_bam_theo_luot.sql",
                    81,
                    104,
                    "Lịch hẹn phù hợp đóng recall CHO_GOI thành KHONG_CAN và đóng chuông liên quan.",
                ),
                (
                    "src/dashboard/app/(dashboard)/nhac-tai-kham/ViecGoiNhac.tsx",
                    65,
                    83,
                    "Client chỉ kiểm res.ok; mọi 2xx đều làm router.refresh mà không đọc outcome payload.",
                ),
            ],
            tests=[
                "src/tests/unit/test_cua_ngo_ghi_moi.py — kiểm replay và cskh_log happy path; không kiểm race trigger KHONG_CAN.",
                "src/tests/unit/test_recall_callback_consistency.py — kiểm callback/single update; không mô phỏng lịch hẹn đóng hàng đồng thời.",
            ],
            result=(
                "Static trace nối recall UPDATE/log, trigger lịch hẹn và UI response handling; "
                "chưa fault-inject hoặc chạy interleaving test."
            ),
            limitations=limitations,
            related=[
                {
                    "id": "CLIN-012",
                    "relationship": "Cùng chuỗi nhắc tái khám nhưng CLIN-012 là việc không được sinh từ lịch hẹn; OPS-005 là phản hồi stale khi ghi outcome.",
                }
            ],
        ),
        prior.finding(
            id="FE-022",
            title="Khối tự nhắc theo khách chỉ hiển thị tối đa 100 mục mà không báo còn trang",
            severity="LOW",
            level="confirmed_static",
            category="personal_reminder_list_truncation",
            summary=(
                "NhacViecService.cua_toi lọc reminder cá nhân theo nhân viên/clinic và "
                "(tuỳ màn) khách hàng, rồi LIMIT 100. API chỉ trả items; BFF không bổ sung "
                "has_more/cursor; TuNhac render toàn bộ mảng nhận được mà không báo đã cắt."
            ),
            trigger=(
                "Một nhân viên có trên 100 nhắc việc cá nhân còn trong cửa sổ hiển thị "
                "bảy ngày, trong cùng phạm vi khách hàng/màn đang mở."
            ),
            impact=(
                "Những mục sau 100 không xuất hiện trong khối này và nhân viên không thấy "
                "còn trang. Các timer/nhắc giờ vẫn nằm trong hệ thống; chưa có bằng chứng "
                "mục bị mất hoặc ngưỡng này từng xảy ra. Mức LOW vì đây là danh sách tự "
                "nhắc cá nhân, không phải worklist CSKH chính thức."
            ),
            recommendation=(
                "Dùng cursor/has_more hoặc tăng tải theo nhu cầu; nếu giới hạn cố định thì "
                "hiển thị số mục đang thấy và lối mở danh sách đầy đủ. Không biến cảnh báo "
                "log khi chạm giới hạn thành hợp đồng duy nhất cho người dùng."
            ),
            acceptance=(
                "Fixture 101+ reminder tổng hợp: có thể xem đủ các mục qua phân trang hoặc "
                "UI nêu rõ còn dữ liệu; bộ lọc theo khách vẫn giới hạn đúng; reminder đã "
                "hẹn giờ tiếp tục được giữ nguyên."
            ),
            note=(
                "Exact-main trace: service LIMIT 100 và log cảnh báo nhưng trả list thường; "
                "route/BFF chỉ chuyển tiếp items, còn TuNhac render mảng không có pagination. "
                "Không kết luận reminder/timer bị xoá hoặc mất."
            ),
            refs=[
                (
                    "src/clinicai/services/nhac_viec_service.py",
                    88,
                    106,
                    "Truy vấn cá nhân LIMIT 100; cảnh báo được gọi nhưng response vẫn là list.",
                ),
                (
                    "src/clinicai/api/v1/routers/day_noi.py",
                    147,
                    158,
                    "Endpoint chỉ bọc danh sách service trong trường items, không có total/has_more/cursor.",
                ),
                (
                    "src/dashboard/app/api/nhac-viec/route.ts",
                    19,
                    26,
                    "BFF chuyển tiếp đúng danh sách theo khách hoặc cá nhân, không có phân trang.",
                ),
                (
                    "src/dashboard/app/(dashboard)/_lam-viec/TuNhac.tsx",
                    44,
                    58,
                    "Client nạp items một lần và lưu nguyên mảng; không đọc metadata trang.",
                ),
                (
                    "src/dashboard/app/(dashboard)/_lam-viec/TuNhac.tsx",
                    129,
                    144,
                    "UI chỉ map mảng hiện có; không báo cắt hoặc có trang tiếp.",
                ),
            ],
            tests=[
                "src/tests/services/test_day_noi_nhac_db.py — kiểm service/DB reminder; chưa thấy fixture xác nhận hơn 100 items hay UI pagination.",
            ],
            result=(
                "Static exact-main service → router → BFF → component trace; không tạo dataset 101+ "
                "và không chạy reminder worker."
            ),
            limitations=limitations,
            related=[
                {
                    "id": "CLIN-022",
                    "relationship": "Cùng mẫu cắt worklist thiếu has_more; CLIN-022 là CSKH liệu trình, FE-022 là reminder cá nhân và có mức tác động thấp hơn.",
                },
                {
                    "id": "FE-020",
                    "relationship": "Cùng vấn đề danh sách bị giới hạn; FE-020 là inbox thông báo đang mở, FE-022 là tự nhắc cá nhân.",
                },
            ],
        ),
        prior.finding(
            id="CLIN-040",
            title="Hai lần lưu số đo siêu âm có thể ghi đè findings từ cùng một snapshot cũ",
            severity="MEDIUM",
            level="confirmed_static",
            category="clinical_ultrasound_concurrent_edit",
            summary=(
                "save_measurements đọc ultrasound_record.findings không FOR UPDATE/version, "
                "merge patch vào dict trong Python rồi UPDATE toàn JSON findings. Nếu hai "
                "request cùng đọc một snapshot, request ghi sau có thể xoá patch của request "
                "trước, kể cả hai request sửa các trường khác nhau. Nhánh ON CONFLICT cũng "
                "gán findings = EXCLUDED.findings. Request chạy trong transaction nhưng không "
                "khóa visit; helper gán work_item chỉ tạo khóa tình cờ khi còn việc DICHVU-SIEUAM "
                "chưa có người nhận."
            ),
            trigger=(
                "Hai request cùng lượt khám lưu số đo/trạng thái đồng thời, và không có "
                "work_item chưa nhận để tuần tự hoá; ví dụ task đã được gán hoặc không tồn tại."
            ),
            impact=(
                "Một phần dữ liệu đo đã lưu có thể biến mất âm thầm; response 2xx của cả hai "
                "request không báo xung đột. Đây là dữ liệu lâm sàng, nhưng hiện chưa tìm thấy "
                "dashboard caller đang bật cho đường này: ClinicalRecordForm mặc định "
                "showSono=false và không có callsite đặt true. API route vẫn tồn tại. Không có "
                "interleaving test hoặc occurrence production."
            ),
            recommendation=(
                "Thêm revision/compare-and-swap cho ultrasound_record hoặc khóa row trước khi "
                "đọc và merge. Tốt hơn, cập nhật từng JSON key theo patch nguyên tử có kiểm "
                "soát, không ghi snapshot cũ; trả 409 khi baseline stale để UI giữ số đo local "
                "và hiển thị bản mới nhất."
            ),
            acceptance=(
                "Hai transaction cùng base revision ghi hai measurement khác nhau: hệ thống "
                "phải giữ cả hai nếu patch policy cho phép hoặc trả conflict có local/remote; "
                "không có 2xx giả cho snapshot đã bị thay thế. Kiểm cả row đã assigned, chưa "
                "assigned và không có work_item."
            ),
            note=(
                "Exact-main service đọc full findings snapshot không khóa, merge Python rồi "
                "overwrite; nhánh conflict upsert cũng dùng EXCLUDED.findings. Không có khóa "
                "visit. Khi task đã assigned hoặc không tồn tại, helper ghi assignment không "
                "tạo serialization guarantee. Dashboard component hiện không được bật qua caller tìm thấy."
            ),
            refs=[
                (
                    "src/clinicai/services/ultrasound_service.py",
                    151,
                    172,
                    "Đọc trạng thái visit để kiểm sửa được nhưng không khóa visit bằng FOR UPDATE.",
                ),
                (
                    "src/clinicai/services/ultrasound_service.py",
                    199,
                    209,
                    "Đọc findings snapshot từ ultrasound_record mà không row lock hoặc revision.",
                ),
                (
                    "src/clinicai/services/ultrasound_service.py",
                    236,
                    255,
                    "Merge snapshot trong Python rồi UPDATE toàn bộ cột JSON findings.",
                ),
                (
                    "src/clinicai/services/ultrasound_service.py",
                    269,
                    288,
                    "ON CONFLICT cũng overwrite findings bằng EXCLUDED snapshot.",
                ),
                (
                    "src/clinicai/services/ultrasound_board_service.py",
                    217,
                    238,
                    "Khóa tình cờ chỉ phát sinh khi work_item active còn assigned_to IS NULL.",
                ),
                (
                    "src/clinicai/api/v1/routers/ultrasound.py",
                    69,
                    84,
                    "API measurements hiện gọi service save_measurements trực tiếp.",
                ),
            ],
            tests=[
                "src/tests/test_clinical_data_integrity.py — kiểm ownership, schema/merge và guards; không có hai transaction cùng sửa ultrasound_record.",
                "src/tests/test_hanh_trinh_trang_thai_hien_tai_db.py — có một lần ghi siêu âm; không kiểm lost update.",
            ],
            result=(
                "Static SQL/control-flow trace xác nhận full-document overwrite và thiếu revision. "
                "Chưa chạy interleaving DB test; mức tác động thực tế còn phụ thuộc caller/feature usage."
            ),
            limitations=limitations
            + " Dashboard search found no active caller enabling showSono; no external API consumer inventory was available.",
            related=[
                {
                    "id": "CLIN-039",
                    "relationship": "Cùng họ concurrent clinical write nhưng CLIN-039 là JSONB form tự lưu với hai tab; CLIN-040 là aggregate ultrasound_record và overwrite findings riêng.",
                }
            ],
        ),
    ]


def main() -> None:
    actual_sha = subprocess.check_output(
        ["git", "-C", str(SNAPSHOT), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual_sha != PINNED_SHA:
        raise SystemExit(f"Pinned source mismatch: expected {PINNED_SHA}, got {actual_sha}")

    manifest = read_json("MAIN-PHAM-VI.json")
    if manifest["sha"] != PINNED_SHA:
        raise SystemExit("MAIN-PHAM-VI.json does not reference the pinned source SHA")
    by_path = {row["path"]: row for row in manifest["files"]}
    new = definitions()
    existing = read_json("PHAT-HIEN.json")
    ids = {row["id"] for row in existing}
    collisions = sorted(ids.intersection(row["id"] for row in new))
    if collisions:
        raise SystemExit(f"Round 20 IDs already exist: {collisions}; refusing to append")

    by_id = {row["id"]: row for row in existing}
    roster = by_id["SEC-028"]
    roster["title"] = "Ca PENDING có thể cấp quyền thay bác sĩ và định vị luồng khám trước khi duyệt"
    roster["summary"] += (
        " Round 20 bổ sung cap_nhat_vi_tri: khi q.room_id chưa có, truy vấn chọn phòng/node "
        "từ work_roster với status khác REJECTED, do đó row PENDING có thể trở thành vị trí "
        "hiệu lực của khách nếu station map còn active. Đây là cùng root coi assignment chưa "
        "duyệt là ca đang có hiệu lực."
    )
    roster["impact"] += (
        " Bổ sung: hàng chờ có thể gắn vị trí phòng/bước theo ca chưa duyệt nếu visit chưa "
        "có room/node tường minh; chưa chạy dữ liệu DB hoặc chứng minh khách thực tế bị định vị sai."
    )
    roster["recommendation"] = (
        "Chỉ ca APPROVED (và quy tắc legacy NULL đã duyệt rõ) mới cấp quyền thay bác sĩ hoặc "
        "làm nguồn phòng/node hiệu lực. Khi không có ca hợp lệ, giữ vị trí tường minh của "
        "visit/queue hoặc thể hiện Unknown; thêm test PENDING/REJECTED/APPROVED cho cả gate "
        "lâm sàng và projection hàng chờ."
    )
    roster["acceptance"] = (
        "Synthetic PENDING không cấp quyền thay và không quyết định phòng/node; APPROVED "
        "đúng phòng/ca/cơ sở hoạt động; REJECTED/khác cơ sở/khác ca bị loại; q.room_id đã "
        "tường minh tiếp tục được ưu tiên; ghi nhận Unknown khi không có vị trí hợp lệ."
    )
    roster["main_validation"]["note"] += (
        " Round 20 tìm thêm cap_nhat_vi_tri dùng status <> REJECTED để lấy room/node khi "
        "q.room_id rỗng; evidence conditional theo row PENDING và station mapping."
    )
    roster["validation"]["result"] += (
        " Round 20 trace thêm projection room/node của hàng chờ; vẫn chưa có test DB/authorization runtime."
    )
    roster["related_tests"] = list(
        dict.fromkeys(
            roster.get("related_tests", [])
            + [
                "src/tests/services/test_hanh_trinh_trang_thai_hien_tai_db.py — kiểm projection/lifecycle hàng chờ với fixture đơn; không kiểm pending roster làm nguồn phòng/node."
            ]
        )
    )
    roster_ref = prior.evidence(
        (
            "src/clinicai/services/hang_cho.py",
            214,
            235,
            "Khi q.room_id chưa có, truy vấn roster lấy room theo status khác REJECTED, bao gồm PENDING.",
        )
    )
    roster["evidence"].append(
        {k: roster_ref[k] for k in ("path", "line", "end_line", "detail")}
    )
    roster["main_validation"]["evidence"].append(roster_ref)
    roster["source_hashes"][roster_ref["path"]] = roster_ref["sha256"]

    held_sono = {
        "id": "SONO-UI-CONTRACT-001",
        "classification": "held_dormant_ui_contract_not_promoted",
        "severity_assessment": "Chưa xếp mức: không tìm thấy dashboard caller truyền showSono=true; API backend vẫn tồn tại.",
        "snapshot_sha": PINNED_SHA,
        "trigger": "Nếu khối SonoBiometry được bật lại qua ClinicalRecordForm.",
        "impact": (
            "Component đọc/ghi /api/ultrasound nhưng BFF hiện mặc định GET về queue và POST "
            "tới /api/v1/ultrasound/draft; backend measurements tương thích nằm ở route khác. "
            "Chưa có bằng chứng người dùng hiện vào được component này."
        ),
        "evidence": [
            {
                "path": "src/clinicai/api/v1/routers/ultrasound.py",
                "lines": "69-84",
                "sha256": prior.source("src/clinicai/api/v1/routers/ultrasound.py")[1],
            },
            {
                "path": "src/dashboard/app/(dashboard)/tasks/ClinicalRecordForm.tsx",
                "lines": "298-324,1407-1415",
                "sha256": prior.source("src/dashboard/app/(dashboard)/tasks/ClinicalRecordForm.tsx")[1],
            },
            {
                "path": "src/dashboard/app/(dashboard)/tasks/SonoBiometry.tsx",
                "lines": "37-76",
                "sha256": prior.source("src/dashboard/app/(dashboard)/tasks/SonoBiometry.tsx")[1],
            },
            {
                "path": "src/dashboard/app/api/ultrasound/route.ts",
                "lines": "19-60",
                "sha256": prior.source("src/dashboard/app/api/ultrasound/route.ts")[1],
            },
        ],
        "not_promoted_reason": "Component mặc định ẩn và không có callsite bật showSono; chưa có bằng chứng user-facing. Giữ thành contract question để tránh coi code dormant là lỗi đang xảy ra.",
        "next": "Trước khi mở UI, nối GET theo appointment/visit tới record projection và POST tới /api/v1/ultrasound/measurements; thêm contract + concurrent-save test cho cả BFF/backend.",
    }
    held_cleanup = {
        "id": "CLEANUP-SCHEMA-001",
        "classification": "held_fail_closed_operational_observation",
        "severity_assessment": "Chưa xếp finding; script có guard/transaction và dự kiến rollback an toàn, nhưng dừng writer trước SQL có thể tạo gián đoạn ngắn.",
        "snapshot_sha": PINNED_SHA,
        "trigger": "Chạy script full-wipe cũ trên database đã áp dụng migration thêm payment_cycle_phan và anh_chuyen_khoan.",
        "impact": "SQL FK graph guard có thể từ chối xóa do bảng mới còn tham chiếu payment_cycle; script shell đã dừng writer trước khi chạy SQL, sau đó khôi phục service khi thất bại. Không xóa một phần nếu transaction rollback như thiết kế; chưa chạy trên schema/prod.",
        "evidence": [
            {
                "path": "scripts/don-prod-truoc-ban-giao.sh",
                "lines": "57-80",
                "sha256": prior.source("scripts/don-prod-truoc-ban-giao.sh")[1],
            },
            {
                "path": "scripts/don-prod-truoc-ban-giao.sql",
                "lines": "73-125",
                "sha256": prior.source("scripts/don-prod-truoc-ban-giao.sql")[1],
            },
            {
                "path": "supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql",
                "lines": "43-54,224-250",
                "sha256": prior.source("supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql")[1],
            },
            {
                "path": "supabase/migrations/20261008200000_don_khach_thu_lieu_trinh.sql",
                "lines": "88-115",
                "sha256": prior.source("supabase/migrations/20261008200000_don_khach_thu_lieu_trinh.sql")[1],
            },
        ],
        "not_promoted_reason": "Đây là script one-off cũ, DANG-LAM vẫn ghi trạng thái cũ; SQL có preflight và rollback nên chưa ghi nhận data-loss defect. Cần xác nhận script còn được giữ trong vận hành hay đã retired.",
        "next": "Đánh dấu script one-off retired hoặc cập nhật FK deletion order/stop-before-run behavior; đối chiếu runbook trước khi chuyển thành finding.",
    }

    extra_ranges = [
        ("src/dashboard/app/(dashboard)/tasks/ClinicalRecordForm.tsx", 298, 324, "showSono mặc định false; prop contract và role intent."),
        ("src/dashboard/app/(dashboard)/tasks/ClinicalRecordForm.tsx", 1407, 1415, "Component chỉ render khi showSono truthy."),
        ("src/dashboard/app/(dashboard)/tasks/SonoBiometry.tsx", 37, 76, "Component đọc và ghi generic /api/ultrasound."),
        ("src/dashboard/app/api/ultrasound/route.ts", 19, 60, "BFF GET mặc định queue, POST vào ultrasound/draft."),
        ("src/dashboard/app/api/sono/route.ts", 1, 80, "Đối chiếu BFF sono riêng; targeted route trace."),
        ("src/dashboard/tests/clinical-ultrasound-ui-boundary.test.mts", 1, 120, "UI boundary tests; không chứng minh component được mount ở màn live."),
        ("src/tests/test_clinical_data_integrity.py", 225, 315, "Ownership guards; không có two-writer lost-update test."),
        ("src/tests/services/test_day_noi_nhac_db.py", 1, 260, "Reminder service DB tests; no volume fixture beyond the cap."),
        ("src/tests/services/test_hanh_trinh_trang_thai_hien_tai_db.py", 400, 424, "One ultrasound write in workflow test; no concurrent writer."),
        ("src/tests/unit/test_cua_ngo_ghi_moi.py", 769, 797, "CSKH log happy path và replay; không kiểm trigger race."),
        ("src/tests/unit/test_recall_callback_consistency.py", 126, 175, "Recall callback/unit behavior; không interleave appointment trigger."),
        ("scripts/don-prod-truoc-ban-giao.sh", 57, 80, "Old full-wipe wrapper stops writers before SQL and restores services on failure."),
        ("scripts/don-prod-truoc-ban-giao.sql", 73, 125, "Delete list and fail-closed FK graph preflight."),
        ("scripts/don-truoc-moc.sh", 1, 171, "Full-file read of current selective cleanup helper; shared routine differs from old wipe."),
        ("supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql", 43, 54, "Payment child table FK to payment_cycle."),
        ("supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql", 224, 250, "Receipt image child table FK to payment_cycle."),
        ("supabase/migrations/20261008200000_don_khach_thu_lieu_trinh.sql", 88, 115, "Current selective cleanup includes the new payment child tables."),
    ]

    full_reads = {
        "src/clinicai/services/tiep_don_service.py",
        "src/clinicai/services/hang_cho.py",
        "src/clinicai/services/nhan_luot.py",
        "src/clinicai/services/nhan_trang_thai_dieu_phoi.py",
        "src/clinicai/services/queue_rows.py",
        "src/clinicai/services/cskh_service.py",
        "src/clinicai/services/recall_service.py",
        "src/clinicai/services/lich_tai_kham_service.py",
        "src/clinicai/services/nhac_viec_service.py",
        "src/clinicai/services/canh_gac_kho_tep.py",
        "src/clinicai/services/bao_ket_qua_ve.py",
        "src/clinicai/services/andrology_service.py",
        "src/clinicai/services/ultrasound_service.py",
        "scripts/don-prod-truoc-ban-giao.sh",
        "scripts/don-prod-truoc-ban-giao.sql",
        "scripts/don-truoc-moc.sh",
    }
    all_ranges = refs_for(new, extra_ranges)
    for path, start, end, detail in [
        ("src/clinicai/services/ultrasound_service.py", 151, 172, "No row lock on visit; writable-state check only."),
        ("src/clinicai/services/ultrasound_service.py", 199, 209, "Unprotected ultrasound row read."),
        ("src/clinicai/services/ultrasound_service.py", 236, 255, "Merge stale JSON then overwrite entire column."),
        ("src/clinicai/services/ultrasound_service.py", 269, 288, "Conflict branch overwrites with EXCLUDED snapshot."),
        ("src/clinicai/services/ultrasound_board_service.py", 217, 238, "Conditional work item assignment lock."),
        ("src/clinicai/services/recall_job_service.py", 282, 300, "Closed-state response before CSKH insert branch."),
        ("supabase/migrations/20260929950000_hen_tai_kham_bam_theo_luot.sql", 81, 104, "Appointment trigger auto-closes pending recall."),
        ("src/dashboard/app/(dashboard)/nhac-tai-kham/ViecGoiNhac.tsx", 65, 83, "Client ignores successful stale-state payload."),
        ("src/clinicai/services/nhac_viec_service.py", 88, 106, "Reminder LIMIT and logging."),
        ("src/clinicai/api/v1/routers/day_noi.py", 147, 158, "Endpoint returns items only."),
        ("src/dashboard/app/api/nhac-viec/route.ts", 19, 26, "BFF forwards list without page metadata."),
        ("src/dashboard/app/(dashboard)/_lam-viec/TuNhac.tsx", 44, 58, "Single page client load."),
        ("src/dashboard/app/(dashboard)/_lam-viec/TuNhac.tsx", 129, 144, "No UI overflow state."),
        ("src/clinicai/services/hang_cho.py", 214, 235, "Pending roster can provide room/node fallback."),
    ]:
        all_ranges.setdefault(path, []).append((start, end, detail))
    for path in full_reads:
        lines, _ = prior.source(path)
        all_ranges.setdefault(path, []).append(
            (1, len(lines), "Full-file read in round 20; outcome summarized in round20-summary.md.")
        )

    status_rank = {"inventoried": 0, "scanned": 1, "traced": 2, "read": 3, "excluded": 4}
    coverage_files = []
    for path, spans in sorted(all_ranges.items()):
        if path not in by_path:
            raise SystemExit(f"Reviewed path missing from ledger: {path}")
        lines, digest = prior.source(path)
        row = by_path[path]
        if row["sha256"] != digest or row["lines"] != len(lines):
            raise SystemExit(f"Main ledger fingerprint mismatch: {path}")
        old_status = row["status"]
        status = "read" if path in full_reads else (
            "traced" if status_rank[old_status] < status_rank["traced"] else old_status
        )
        row["status"] = status
        mode = "full_file_read" if path in full_reads else "targeted_semantic_trace"
        range_text = "; ".join(f"{a}-{b}" for a, b, _ in spans)
        row["method"] = f"{row.get('method', '')} | Round 20 {mode}: {range_text}".strip(" |")
        coverage_files.append({
            "path": path,
            "status": status,
            "prior_status": old_status,
            "read_level_this_round": mode,
            "full_file_read_this_round": path in full_reads,
            "ranges": [{"start": a, "end": b, "purpose": purpose} for a, b, purpose in spans],
            "sha256": digest,
            "line_count": len(lines),
        })

    # Persist held observations with exact-main hashes; they are not risk findings.
    held = state_held = read_json("STATE.json").get("held_observations", [])
    for item in (held_sono, held_cleanup):
        if not any(old.get("id") == item["id"] for old in held):
            state_held.append(item)

    write_json("MAIN-PHAM-VI.json", manifest)
    write_json("PHAT-HIEN.json", existing + new)
    write_json("blocks/round20_findings.json", new)
    write_json("blocks/round20_coverage.json", {
        "schema_version": 1,
        "audit": "round20_queue_recall_reminders_clinical_results_cleanup",
        "snapshot": {"path": str(SNAPSHOT), "sha": PINNED_SHA},
        "review_mode": "static_read_only_cross_layer_trace",
        "scope": [
            "appointment intake and queue service ownership/state",
            "recall call outcomes and self-reminder list contract",
            "result-file watch/return, Andrology and ultrasound service writes",
            "old destructive cleanup versus current selective cleanup and migration graph",
            "ultrasound UI mount and BFF/backend route contract; held because no caller enables showSono",
        ],
        "tests_run": False,
        "runtime_db_vps_secrets_phi_touched": False,
        "coverage_note": "16 files were read in full. Other files have exact targeted ranges and SHA excerpts. Agent-suggested adjacent tests were inspected but not run. No ClinicAI application, DB, API, provider, production, secret or patient-data validation occurred in this round.",
        "held_observations": ["SONO-UI-CONTRACT-001", "CLEANUP-SCHEMA-001"],
        "files": coverage_files,
    })

    checks = read_json("KIEM-CHUNG.json")
    known = {(row["id"], row["path"]) for row in checks["checks"]}
    for item in new + [roster]:
        for ev in item["main_validation"]["evidence"]:
            key = (item["id"], ev["path"])
            if key not in known:
                checks["checks"].append({"id": item["id"], "path": ev["path"], "valid": True})
                known.add(key)
    write_json("KIEM-CHUNG.json", checks)

    state = read_json("STATE.json")
    state["held_observations"] = state_held
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    counts = Counter(row["status"] for row in manifest["files"])
    code_files = [row for row in manifest["files"] if Path(row["path"]).suffix.lower() in CODE_SUFFIXES]
    code_counts = Counter(row["status"] for row in code_files)
    all_findings = existing + new
    severity = Counter(row["severity"] for row in all_findings)
    levels = Counter(row["evidence_level"] for row in all_findings)
    main_status = Counter(row["main_validation"]["status"] for row in all_findings)
    summary = state["summary"]
    state["updated_at"] = now
    state["phase"] = "round20_queue_recall_reminders_clinical_results_cleanup_checkpoint"
    state["next_action"] = (
        "Continue exact-main semantic reads across remaining scanned/inventoried paths. Next prioritize clinical UI caller/contract inventories, patient API and PostgREST permission matrices, fresh-migration database invariants, finance reconciliation, and event/provider failure paths. Run only bounded synthetic tests on disposable environments; preserve all conditional findings as unverified until reproduced. Keep the full source audit incomplete."
    )
    state["report_status"] = "v0.41_157_findings_HTML_and_portable_ZIP_pending_QA; full source audit incomplete"
    summary["findings"] = len(all_findings)
    summary["severity"] = {key: severity.get(key, 0) for key in ("HIGH", "MEDIUM", "LOW")}
    summary["evidence_levels"] = {key: levels.get(key, 0) for key in ("reproduced_local", "design_gap", "confirmed_static", "hypothesis")}
    summary["main_status"] = {key: main_status.get(key, 0) for key in ("still_present_on_main", "partially_addressed_on_main", "addressed_on_main")}
    summary["main_coverage"] = {key: counts.get(key, 0) for key in ("inventoried", "read", "traced", "scanned", "excluded")}
    summary["main_read_files"] = counts["read"]
    summary["main_partial_traces"] = counts["traced"]
    summary["code_like_source_files"] = {
        "definition": "Pinned-tree paths with common source-code/web/sql/shell suffixes used by the report generator; includes app, tests, tooling and styles, not only runtime code.",
        "total": len(code_files),
        "coverage": {key: code_counts.get(key, 0) for key in ("inventoried", "traced", "scanned", "read")},
        "traced_is_partial": True,
    }
    summary["reviewed_slice_v041"] = (
        "round20: 3 additions (1 MEDIUM, 2 LOW) across ultrasound concurrent writes, recall outcome stale-state response, and personal reminder list cap; SEC-028 extended with queue room/node use of PENDING roster. 16 full-file reads plus targeted traces; no application tests. SonoBiometry contract and old full-wipe script retained as held observations."
    )
    summary["new_findings_v041"] = [item["id"] for item in new]
    state.setdefault("blocks", {})["round20_queue_recall_reminders_clinical_results_cleanup"] = {
        "status": "round20 static slices integrated; 3 new findings, SEC-028 extended, 2 held observations",
        "scope": "Queue/intake, recall and self-reminder, clinical result files/Andrology/ultrasound, cleanup scripts and related migrations",
        "artifacts": "blocks/round20-summary.md; blocks/round20_findings.json; blocks/round20_coverage.json; integrate_round20.py",
        "findings": "1 MEDIUM and 2 LOW, still present on pinned main; SEC-028 extended with conditional room/node projection evidence.",
        "next": "Continue source reads and run targeted synthetic concurrency/state tests only after source audit reveals sufficient exact-main fixtures; full audit incomplete.",
    }
    state["artifacts"]["integration_script"] = "integrate_round20.py; round20 evidence/coverage in blocks/round20_*; earlier checkpoints retained."
    state["artifacts"]["qa"] = "HTML-QA.json; v0.41 report structural/evidence and desktop/mobile QA pending. Report-only, not ClinicAI validation."
    state["artifacts"]["bundle_integrity"] = "Pending v0.41 audit-only package regeneration and verification."
    state["artifacts"]["html_sha256"] = "pending v0.41 QA"
    state["artifacts"]["html_checked_at"] = "pending v0.41 QA"
    state["artifacts"]["bundle_entries"] = "pending v0.41 package verification"
    state["runtime_summary"]["round20"] = "Static exact-main traces; no application/DB/API/provider/production test, secret or PHI access. Report QA pending."
    write_json("STATE.json", state)

    print(json.dumps({
        "new_findings": [item["id"] for item in new],
        "findings_total": len(all_findings),
        "severity": dict(severity),
        "main_status": dict(main_status),
        "coverage": dict(counts),
        "code_like_total": len(code_files),
        "code_like_coverage": dict(code_counts),
        "round20_full_reads": len(full_reads),
        "round20_reviewed_paths": len(coverage_files),
        "updated_at": now,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
