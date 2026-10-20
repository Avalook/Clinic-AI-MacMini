from __future__ import annotations
import hashlib, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIN_SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"
PINNED = Path(json.loads((ROOT / "MAIN-PHAM-VI.json").read_text())["snapshot"])
NOW = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
LOCAL = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def excerpt(path: str, start: int, end: int, detail: str) -> dict:
    source = PINNED / path
    lines = source.read_text().splitlines()
    if start < 1 or end < start or end > len(lines):
        raise ValueError(f"invalid range {path}:{start}-{end}")
    return {"path": path, "line": start, "end_line": end, "sha256": digest(source),
            "excerpt": "\n".join(f"{i}: {lines[i-1]}" for i in range(start, end + 1)),
            "detail": detail}

def public_evidence(specs):
    return [{k:v for k,v in excerpt(*s).items() if k in {"path","line","end_line","detail"}} for s in specs]

def hashes(specs):
    return {p:digest(PINNED/p) for p,_,_,_ in specs}

def make_finding(fid, title, severity, category, summary, trigger, impact,
                 recommendation, acceptance, result, limitations, specs,
                 tests, note, related=None):
    row = {
        "id": fid, "title": title, "severity": severity,
        "evidence_level": "confirmed_static", "category": category,
        "summary": summary, "trigger": trigger, "impact": impact,
        "evidence": public_evidence(specs),
        "validation": {"method":"round34_static_cross_layer_trace_on_pinned_main",
                       "command":None,"result":result,"limitations":limitations},
        "recommendation":recommendation,"acceptance":acceptance,
        "alignment":["Reality ngày càng dễ nhìn thấy hơn","Khoảng thời gian Unknown ngày càng ngắn hơn",
                     "Ownership ngày càng rõ hơn","Vấn đề được phát hiện sớm hơn",
                     "Bệnh nhân ít phải chờ trong bất định hơn","Quyết định dựa trên bằng chứng tốt hơn"],
        "related_tests":tests,"source_hashes":hashes(specs),"status":"open",
        "reference_version":"pinned_main","production_metadata_validation":None,
        "main_validation":{"sha":PIN_SHA,"status":"still_present_on_main","note":note,
                           "evidence":[excerpt(*s) for s in specs]}}
    if related: row["related_findings"] = related
    return row

def save(name, obj):
    (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")

ledger = json.loads((ROOT/"MAIN-PHAM-VI.json").read_text())
if ledger["sha"] != PIN_SHA or PINNED.resolve() != Path(ledger["snapshot"]).resolve():
    raise SystemExit("Pinned source SHA/root mismatch")
findings = json.loads((ROOT/"PHAT-HIEN.json").read_text())
by_id = {x["id"]:x for x in findings}
new_ids = ["CLIN-050","CLIN-051","CLIN-052","CLIN-053","OPS-010","API-007"]
for fid in new_ids:
    if fid in by_id: raise SystemExit(f"{fid} already exists")

# Extend SEC-027 with the legacy doctor-board endpoint; no active dashboard caller was found.
patient_specs = [
("src/clinicai/api/v1/routers/booking.py",593,631,"Doctor-board chỉ nhận identity chung; docstring giao giới hạn bác sĩ cho màn hình gọi."),
("src/clinicai/services/doctor_board_service.py",49,75,"SQL lọc clinic/location; doctor_id có thể bỏ trống, assignment filter chỉ áp cho TKYK."),
("src/clinicai/services/doctor_board_service.py",115,129,"Kết quả trả tên, ngày sinh, số điện thoại, địa chỉ và người giám hộ."),
("src/clinicai/api/identity.py",638,659,"get_current_identity chỉ chặn DISPLAY/PARTNER, không kiểm capability đọc hồ sơ/lịch."),
("src/clinicai/main.py",416,423,"Booking router gắn runaway_guard; không có guard quyền theo đối tượng."),
("src/tests/services/test_doctor_board.py",127,166,"Test chỉ kiểm tham số service/datetime, không có authorization test cho route."),
]
patient = by_id["SEC-027"]
patient["summary"] = (
"GET /patients/{id} và /patients?phone= chỉ dùng get_current_identity, không yêu cầu patient.list.view. "
"Cùng router, /patients/danh-sach có capability này; preset PHARMACIST không có. Các route hồ sơ hành chính/CSKH "
"cũ cũng chỉ yêu cầu identity và có thể trả liên hệ, lịch hẹn, follow-up cùng ghi chú tự do. Thêm một API cũ "
"/appointments/doctor-board: route ghi rõ để màn hình tự quyết định ai xem lịch bác sĩ nào, nhưng backend cho "
"doctor_id tuỳ chọn và trả PII bệnh nhân; phạm vi vẫn bị chặn theo clinic/location và assignment TKYK. Không thấy "
"caller dashboard hiện tại cho hai nhóm API cũ; reachability từ UI hiện hành chưa được xác nhận.")
patient["trigger"] = (
"Nhân viên nội bộ không có patient.list.view gọi API theo UUID/số điện thoại/hồ sơ đã biết; hoặc một internal caller "
"có service key gọi doctor-board với doctor_id người khác hay bỏ doctor_id. Các route vẫn cần staff auth và clinic/location scope.")
patient["impact"] = (
"Một số API trả PII cùng clinic mà thiếu capability đọc nhất quán; doctor-board để UI tự giới hạn bác sĩ nhưng backend "
"có thể trả dữ liệu nhiều bác sĩ. Không thấy dashboard caller hiện tại cho doctor-board và route yêu cầu backend service key, "
"nên chưa kết luận browser hiện tại gọi được. Không có bằng chứng đọc chéo clinic.")
patient["recommendation"] = (
"Áp capability đọc hồ sơ/lịch theo use case ở FastAPI; server tự suy doctor/location scope hoặc kiểm quyền từng đối tượng, "
"không giao cho UI. Tách quyền đọc hành chính khỏi ghi chú CSKH, trả projection tối thiểu và thêm negative tests theo role.")
patient["acceptance"] = (
"Vai thiếu capability bị từ chối ở ID, phone, hành chính, CSKH và doctor-board; bác sĩ chỉ nhận phạm vi được phép, "
"vai điều phối theo policy server-side. Kiểm hai clinic/location, assignment TKYK, projection tối thiểu và audit log bằng dữ liệu giả.")
patient["evidence"].extend(public_evidence(patient_specs))
patient["main_validation"]["evidence"].extend(excerpt(*s) for s in patient_specs)
patient["main_validation"]["note"] = (
"Exact-main: patient ID/phone/profile và doctor-board thiếu capability đọc đồng nhất. Doctor-board để UI tự giới hạn "
"bác sĩ nhưng backend cho doctor_id tuỳ chọn và trả PII; vẫn scope clinic/location và TKYK assignment. Không thấy UI caller; "
"API yêu cầu service key nên browser reachability hiện chưa xác nhận.")
patient.setdefault("source_hashes",{}).update(hashes(patient_specs))
patient["related_tests"] = list(dict.fromkeys(patient.get("related_tests",[])+[
"src/tests/services/test_doctor_board.py:127-166 — chỉ kiểm service params/datetime; không kiểm quyền ở route."]))
patient["validation"]["limitations"] = (
"Static exact-main trace only; no API/JWT runtime test. Queries retain clinic/location and TKYK assignment scope. "
"No active dashboard callsite for doctor-board was found; current browser reachability through a service-key path is unconfirmed.")

added=[]

result_specs=[
("src/clinicai/services/tep_ket_qua_service.py",1272,1308,"Danh sách theo toàn bệnh nhân, mới nhất trước, LIMIT 200; cảnh báo chỉ vào log, response vẫn là list."),
("src/clinicai/services/tep_ket_qua_service.py",1310,1338,"Danh sách khôi phục trong 30 ngày có LIMIT 100, không có completeness metadata."),
("src/dashboard/app/(dashboard)/tasks/TepCuaLuotKham.tsx",34,58,"UI tải danh sách toàn bệnh nhân rồi lọc appointment_id ở client."),
("src/dashboard/app/(dashboard)/_lam-viec/KhungTep.tsx",218,247,"UI tải danh sách toàn bệnh nhân rồi lọc service_order_id/bên ở client."),
("src/dashboard/app/api/cskh/ket-qua/route.ts",21,40,"BFF chuyển payload từ backend nguyên trạng, không thêm total/has_more/truncated.")]
f=make_finding(
"CLIN-050","Tệp kết quả cũ có thể biến mất khỏi ngữ cảnh lượt khám khi danh sách chạm trần","MEDIUM",
"clinical_result_completeness",
"Service liệt kê tối đa 200 tệp hiệu lực theo toàn bệnh nhân, mới nhất trước; hai UI tải danh sách đó rồi lọc theo appointment/order ở client. Khi có hơn 200 tệp mới hơn của lượt khác, tệp của lượt đang xem có thể nằm ngoài payload và trông như không có. Danh sách khôi phục giới hạn 100 tệp xoá trong 30 ngày nhưng không có total/has_more hoặc cờ bị cắt. Không có volume production cho thấy trần đã bị chạm.",
"Một hồ sơ có hơn 200 tệp hiệu lực mới hơn tệp cần xem ở lượt cũ, hoặc hơn 100 tệp xoá mềm trong cửa sổ 30 ngày.",
"Nhân viên có thể không thấy tài liệu đúng lượt/chỉ định hoặc không tìm thấy tệp trong danh sách khôi phục, dù tệp vẫn tồn tại. Chưa có bằng chứng mất file vật lý, sửa kết quả hay trần đã bị chạm trong vận hành.",
"Đẩy appointment_id/service_order_id/bên filter xuống backend trước LIMIT; dùng cursor ổn định và trả total hoặc has_more/truncated. Áp cùng completeness contract cho danh sách phục hồi.",
"Fixture trên 200 tệp nhiều lượt và trên 100 tệp xoá vẫn truy cập được mọi tệp bằng pagination; UI hiển thị tổng/has_more và không báo rỗng khi chưa đọc hết.",
"Static trace service → BFF → UI filters. Tests đọc, không chạy; nguồn cho thấy cap và filter-after-fetch, không có production volume.",
"Conditional on count crossing the caps. No PHI/volume inspection or runtime test. Rows remain in storage; this is list visibility/recovery completeness, not proven physical loss.",
result_specs,
["src/tests/services/test_in_anh_dot3_db.py:301-347 — test list/access with one file; not cap plus context filter; read, not run.",
"src/tests/unit/test_tran_khong_cat_im_lang.py:54-69 — warning helper is log-oriented, not UI completeness; read, not run."],
"Still present on pinned main: patient-wide LIMIT 200 precedes appointment/order filtering; deleted-file recovery is capped at 100. No production-volume evidence.",
[{"id":"CLIN-022","relationship":"Cùng thiếu completeness metadata nhưng CLIN-022 là worklist khách liệu trình."},
{"id":"CLIN-045","relationship":"Cùng pattern lịch sử bị cắt nhưng CLIN-045 là phản hồi CSKH."}])
findings.append(f); added.append(f)

marker_specs=[
("src/clinicai/services/lieu_trinh_service.py",1434,1483,"Marker mốc hiện tại được SELECT, rồi rời connection trước khi tạo tương tác ở bước riêng."),
("src/clinicai/services/tuong_tac_cskh_service.py",234,257,"Tạo tương tác trong transaction riêng; không có idempotency key cho marker."),
("supabase/migrations/20260810000002_tuong_tac_gan_trang_thai.sql",31,34,"Index tra trạng thái là index thường, không unique."),
("src/tests/services/test_lieu_trinh_sap_het_db.py",210,228,"Test retry hai lần tuần tự và mong cùng ID; không chạy song song.")]
f=make_finding(
"CLIN-051","Bấm đồng thời “Đã xử lý sắp hết liệu trình” có thể ghi trùng tương tác CSKH","LOW",
"cskh_concurrency_idempotency",
"da_xu_ly_sap_het đọc marker đang hoạt động rồi rời connection trước khi tạo tương tác trong transaction khác. Hai request đồng thời có thể cùng thấy chưa có marker và mỗi request ghi một dòng cho cùng mốc liệu trình. Index không unique. Worklist dùng DISTINCT nên marker trùng không mở lại hàng; tác động tĩnh là hai dòng lịch sử CSKH.",
"Hai nhân viên cùng xử lý một liệu trình/mốc gần như đồng thời, trước khi request đầu ghi tương tác.",
"Sổ tương tác có thể chứa hai dòng cùng mô tả mốc đã xử lý, gây nhiễu lịch sử/thống kê. Không có bằng chứng tạo hai cuộc gọi; marker được định nghĩa là thao tác không liên hệ.",
"Đưa kiểm tra và tạo marker vào transaction có khóa theo clinic/patient/liệu trình/mốc, hoặc dùng idempotency key và unique invariant theo vòng đời; xử lý rõ hoàn tác rồi làm lại.",
"Hai request song song cùng liệu trình/mốc chỉ tạo một marker và trả cùng interaction ID; sau hoàn tác, thao tác hợp lệ mới tạo marker mới.",
"Static check-then-insert trace và migration/test review. Existing test xác nhận retry tuần tự; chưa chạy concurrency probe.",
"Low-impact duplicate-history race inferred from separate read/write transactions; no dynamic reproduction or production records.",
marker_specs,["src/tests/services/test_lieu_trinh_sap_het_db.py:210-228 — sequential repeat reuses ID; no parallel requests."],
"Still present on pinned main. The active-marker read and insert are separate; sequential retry test does not cover concurrent requests.")
findings.append(f); added.append(f)

booking_specs=[
("src/dashboard/app/(dashboard)/patients/AppointmentBooking.tsx",128,185,"Form giữ location đã chọn nhưng availability hook/roster call không nhận locationId."),
("src/dashboard/app/(dashboard)/patients/AppointmentBooking.tsx",321,330,"Request tạo lịch gửi location_id đã chọn."),
("src/dashboard/app/(dashboard)/patients/dung-suc-chua-ngay.ts",42,64,"Availability request được tạo từ ngày/bác sĩ/lịch cần bỏ qua, không có location."),
("src/dashboard/app/api/appointments/luoi-ngay/route.ts",1,24,"BFF lưới ngày không truyền location."),
("src/clinicai/api/v1/routers/booking.py",510,537,"Availability route dựng ngữ cảnh ca trực từ identity.location_id."),
("src/clinicai/services/capacity_service.py",723,744,"Capacity service dùng location truyền vào để chọn ngữ cảnh ca trực."),
("src/clinicai/services/booking_service.py",609,629,"Write giữ location do người dùng chọn và kiểm ca trực theo location đó.")]
f=make_finding(
"CLIN-052","Availability khi đặt lịch không đổi theo cơ sở được chọn trong form","LOW",
"booking_location_consistency",
"Form đặt lịch cho chọn cơ sở và gửi location_id đó khi tạo lịch. Nhưng hook sức chứa, roster và BFF lưới ngày không nhận cơ sở; backend availability dùng identity.location_id. Khi chọn cơ sở khác, preview ca trực dựa trên A trong khi lệnh ghi kiểm B. Số ghế hiện được thiết kế đếm chung; phát hiện chỉ nói về ngữ cảnh ca trực.",
"Nhân viên đang ở cơ sở A chọn cơ sở B trong form đặt lịch rồi xem availability trước khi lưu.",
"Lưới có thể hiện ca không hợp lệ ở B hoặc ẩn ca hợp lệ; backend dùng cơ sở B khi ghi nên vẫn có thể từ chối lịch không hợp lệ. Đây là preview/workflow inconsistency, chưa thấy đường tạo lịch sai qua bỏ qua kiểm tra server.",
"Truyền selected location xuyên form → hook → BFF → API availability; đổi cơ sở phải tải lại roster/lịch theo cùng policy endpoint ghi dùng.",
"Fixture hai cơ sở có roster khác nhau xác nhận UI chỉ hiện ca của B; read/create dùng cùng location; server từ chối ca không hợp lệ nếu gửi tay.",
"Static form → hook/BFF → capacity API/service → booking write trace. Tests đọc, không chạy; chưa có fixture hai-location xuyên UI.",
"Low severity: authoritative write path checks selected location, so consequence is mismatched preview or rejected save. No runtime booking tested.",
booking_specs,
["src/tests/services/test_dat_lich_theo_co_so_db.py — booking validation by location; read, not run.",
"src/tests/services/test_luoi_ngay_khop_trigger_db.py — availability/trigger; no selected-location UI chain; read, not run.",
"src/dashboard/tests/luoi-ngoai-ca-truc-boundary.test.mts — shift boundary; not full form-to-BFF location; read, not run."],
"Still present on pinned main. New-booking form sends selected location on write, while availability/roster use identity location. Server validation remains authoritative.",
[{"id":"CLIN-029","relationship":"CLIN-029 là form sửa không lưu location; finding này là availability của form đặt mới dùng location context khác."}])
findings.append(f); added.append(f)

reschedule_specs=[
("src/dashboard/app/(dashboard)/appointments/cho-xep-bac-si/HangChoView.tsx",90,135,"UI PATCH đổi lịch trước, POST marker gọi báo khách sau; không kiểm response.ok và nuốt lỗi."),
("src/dashboard/app/api/appointments/route.ts",267,286,"BFF chuyển PATCH lịch xuống backend."),
("src/clinicai/api/v1/routers/booking.py",718,726,"Backend áp action đổi lịch trước marker CSKH riêng."),
("src/dashboard/app/api/cskh/tuong-tac/route.ts",37,55,"BFF tương tác CSKH chuyển response lỗi; không có retry bền."),
("src/clinicai/services/tuong_tac_cskh_service.py",234,266,"Marker được ghi trong transaction riêng khi service được gọi thành công."),
("src/dashboard/app/(dashboard)/customers/CustomersView.tsx",1040,1060,"Customer view đọc marker để hiện nhắc gọi báo khách."),
("src/dashboard/app/(dashboard)/customers/khung-bao.ts",91,110,"Logic cảnh báo dùng trạng thái marker để xác định cần liên hệ khách.")]
f=make_finding(
"CLIN-053","Đổi giờ thành công nhưng lỗi ghi nhắc gọi báo khách bị bỏ qua","MEDIUM",
"workflow_partial_commit",
"Trong hàng chờ xếp bác sĩ, UI đổi giờ bằng PATCH; sau khi PATCH thành công, UI gửi POST riêng để ghi marker CSKH nhắc gọi báo khách. Response marker không được kiểm tra và lỗi mạng bị catch bỏ qua; UI vẫn đánh dấu thao tác hoàn tất và rời hàng chờ. Lịch đã đổi nhưng reminder có thể không được tạo.",
"PATCH đổi lịch thành công, sau đó POST marker CSKH timeout, mất mạng hoặc nhận HTTP lỗi.",
"Nhân viên có thể không thấy việc gọi khách; bệnh nhân có thể không được báo giờ mới và đến theo lịch cũ. Không có retry/reconciliation cho marker phụ trong luồng này; chưa fault-inject để đo tần suất.",
"Ghi lịch đổi và follow-up qua command nguyên tử hoặc outbox bền cùng transaction; worker tạo marker idempotent. Nếu chưa thể, UI phải thể hiện trạng thái một phần và cho retry reminder độc lập.",
"Fault-injection sau PATCH commit không làm mất ý định gọi báo khách: marker được retry và eventual visible có owner/status, hoặc UI hiển thị rõ trạng thái một phần và recovery path.",
"Static UI → BFF → booking write plus independent CSKH marker/read path. Related tests read, not run; no network fault injection.",
"Failure requires the second request to fail after schedule commit. No patient data or production incident observed; this is not proof a patient missed care.",
reschedule_specs,
["src/dashboard/tests/hang-cho-bac-si-boundary.test.mts — no marker failure after successful PATCH; read, not run.",
"src/dashboard/tests/khung-bao-cskh-boundary.test.mts — reminder display, not creation failure; read, not run.",
"src/tests/unit/test_so_tuong_tac_cskh.py — no two-step UI fault case; read, not run."],
"Still present on pinned main. Schedule and reminder are separate requests; UI ignores a failed marker response. No fault-injection or production incident tested.",
[{"id":"FE-023","relationship":"FE-023 là pending state kẹt khi request lỗi; CLIN-053 là lịch đã commit nhưng reminder side-effect có thể rơi."},
{"id":"CLIN-011","relationship":"CLIN-011 thiếu audit cũ-mới cho một số field reschedule; không phải tính bền của reminder."}])
findings.append(f); added.append(f)

queue_specs=[
("src/clinicai/api/v1/routers/booking.py",328,380,"Hai nhóm lịch chờ đều LIMIT 500; response có bi_cat/tran."),
("src/dashboard/app/(dashboard)/appointments/cho-xep-bac-si/page.tsx",33,61,"Trang server chỉ nhận/render items, bỏ qua metadata bị cắt."),
("src/dashboard/tests/hang-cho-bac-si-boundary.test.mts",1,99,"Boundary tests cover list/labels, not over-500/truncated UI.")]
f=make_finding(
"OPS-010","Hàng chờ xếp bác sĩ có thể trông hết dù còn lịch sau giới hạn 500","MEDIUM",
"operational_queue_completeness",
"API lấy tối đa 500 dòng cho mỗi nhóm lịch chưa có bác sĩ và lịch vượt sức chứa, đồng thời trả bi_cat/tran. Trang xếp bác sĩ chỉ render items và bỏ cờ bị cắt. Nếu một nhóm vượt 500, các lịch sau giới hạn không hiện và trang không báo dữ liệu chưa đầy đủ. Không có volume production cho thấy trần đã bị chạm.",
"Một trong hai nhóm lịch cần xếp bác sĩ có hơn 500 dòng trong phạm vi truy vấn.",
"Quản lý có thể tưởng hàng chờ đã xử lý hết trong khi còn lịch chưa xếp hoặc điều phối. Khả năng bỏ sót vận hành có điều kiện; không có bằng chứng backlog thật vượt trần.",
"Dùng cursor/has_more hoặc chuyển cờ bi_cat đến UI và hiển thị cảnh báo; theo dõi oldest item/tổng chưa phân công độc lập với preview.",
"Fixture trên 500 dòng ở từng nhóm hiển thị has_more/count và phân trang hết; UI không báo hết việc khi payload bị cắt.",
"Static API → active page trace and test review. Tests read, not run; no production volume inspected.",
"Conditional on a group exceeding 500 rows. No production counts or runtime tests.",
queue_specs,
["src/dashboard/tests/hang-cho-bac-si-boundary.test.mts — no assertion for bi_cat; read, not run."],
"Still present on pinned main. Backend computes truncation metadata; active page consumes items only. No production volume evidence.",
[{"id":"OPS-009","relationship":"Same completeness pattern; OPS-009 is 400-row dispatch overview, this is the doctor-assignment queue."}])
findings.append(f); added.append(f)

partner_specs=[
("src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx",1153,1190,"Active room UI calls BFF detail by order UUID."),
("src/dashboard/app/api/doi-tac/viec/route.ts",11,19,"Active BFF validates UUID and forwards detail."),
("src/dashboard/lib/backend-proxy.ts",115,124,"Backend proxy attaches Bearer identity and X-Location-ID."),
("src/dashboard/lib/co-so.ts",13,22,"Location header comes from the user's current location."),
("src/clinicai/api/identity.py",674,700,"get_partner_identity requires identity and partner.work, not object location."),
("src/clinicai/api/v1/routers/doi_tac.py",107,118,"GET detail passes identity and target UUID to service."),
("src/clinicai/services/doi_tac_service.py",239,245,"Service guard checks partner.work only."),
("src/clinicai/services/doi_tac_service.py",408,431,"Detail lookup scopes clinic/UUID/type, but not location."),
("src/clinicai/services/doi_tac_service.py",487,504,"Internal staff list filters location; PARTNER is intentionally multi-location."),
("src/clinicai/api/v1/routers/doi_tac.py",295,312,"POST collection route passes target UUID to service."),
("src/clinicai/services/doi_tac_service.py",1116,1139,"Collection lookup scopes clinic/UUID but does not verify target location."),
("src/dashboard/app/api/doi-tac/da-thu-tien/route.ts",12,42,"Active BFF POST forwards collection operation."),
("src/tests/services/test_loc_co_so_nhom_b_db.py",208,228,"Two-location test covers list policy, not detail/action by UUID.")]
f=make_finding(
"API-007","Detail và thao tác việc đối tác không kiểm cơ sở của đối tượng đích","MEDIUM",
"location_object_authorization",
"Danh sách việc đối tác của nhân viên nội bộ lọc theo cơ sở hiện hành, nhưng detail và POST theo UUID chỉ kiểm clinic, loại việc và capability partner.work. BFF đang hoạt động chuyển identity cùng X-Location-ID; backend không đối chiếu location của chỉ định/lượt đích. Nhân viên có quyền partner.work tại A và biết UUID việc tại B cùng clinic có thể đọc detail hoặc thao tác nhận mẫu, trạng thái, phiếu, tệp, thu hộ/huỷ thu hộ. Vai PARTNER được chủ ý xem nhiều cơ sở. Không phải vượt xác thực hay clinic.",
"Nhân viên nội bộ tại location A có partner.work gửi request BFF hoạt động với UUID đã biết của việc thuộc location B cùng clinic; list chuẩn tại A không hiển thị việc B.",
"Có thể đọc metadata biểu mẫu/tệp/thu hộ và đổi trạng thái hoặc ghi/huỷ thu hộ cho việc cơ sở khác. Detail không thấy tên/mã bệnh nhân nên không kết luận lộ các trường đó. Backend vẫn kiểm clinic, capability, loại việc và trạng thái; không có bằng chứng cross-clinic. Vai PARTNER có phạm vi đa cơ sở theo thiết kế.",
"Trong backend, kiểm location của visit/appointment/order đích trong transaction trước mọi GET/POST đối với staff nội bộ; dùng helper object-scope chung cho detail, trạng thái, phiếu, file và thu hộ. Giữ ngoại lệ đa cơ sở của role PARTNER nếu đó là hợp đồng sản phẩm.",
"Với hai cơ sở cùng clinic, nhân viên A bị từ chối detail và mọi POST vào UUID B; thao tác A vẫn thành công; PARTNER giữ đúng đa cơ sở. Request bị từ chối không đổi event, trạng thái, phiếu, file hay payment.",
"Static active UI/BFF → FastAPI/service trace. Existing two-location tests cover list, not detail/actions; tests read, not run. Backend still enforces clinic/capability/state.",
"Same-clinic cross-location only; needs known UUID and valid staff session/capability. No cross-clinic access, PHI exposure, production event or runtime request claimed. PARTNER role's multi-location access is intentional.",
partner_specs,
["src/tests/services/test_loc_co_so_nhom_b_db.py:208-228 — list policy only; no cross-location detail/action UUID.",
"src/tests/services/test_phong_doi_tac_luong_chung_db.py:234-264 — PARTNER detail/form; no two-location staff case.",
"src/tests/services/test_lay_mau_doi_tac_db.py:74-78 — internal partner.work setup only.",
"src/tests/services/test_doi_tac_nhan_mau_la_xong_db.py:117-240 — workflow transitions, no cross-location.",
"src/tests/services/test_doi_tac_tu_thu_db.py:332-404 — collect/void, no cross-location."],
"Still present on pinned main. Active BFF passes location header but target service checks clinic/UUID/capability and omits object-location comparison; internal list filters location; PARTNER is intentionally multi-location.",
[{"id":"API-002","relationship":"Same family of missing object-level location scope; API-002 reads visit workflow."},
{"id":"API-004","relationship":"Same family of missing location scope; API-004 changes work_item, this finding concerns partner order/result/payment."}])
findings.append(f); added.append(f)

# Coverage ranges for tests read to assess missing cases.
extra = {
"src/tests/services/test_in_anh_dot3_db.py":[(301,347,"CLIN-050 test boundary; no cap/context-filter case.")],
"src/tests/unit/test_tran_khong_cat_im_lang.py":[(54,69,"CLIN-050 warning helper is log-oriented, not UI completeness.")],
"src/tests/services/test_dat_lich_theo_co_so_db.py":[(1,220,"CLIN-052 location booking tests; no full UI selected-location read chain.")],
"src/tests/services/test_luoi_ngay_khop_trigger_db.py":[(1,220,"CLIN-052 availability/trigger test; no selected-location UI contract.")],
"src/dashboard/tests/luoi-ngoai-ca-truc-boundary.test.mts":[(1,128,"CLIN-052 shift test; not form-to-BFF location chain.")],
"src/dashboard/tests/khung-bao-cskh-boundary.test.mts":[(1,99,"CLIN-053 reminder display only; no marker failure after PATCH.")],
"src/tests/unit/test_so_tuong_tac_cskh.py":[(1,220,"CLIN-053 interaction tests; no two-step UI failure case.")],
"src/tests/services/test_phong_doi_tac_luong_chung_db.py":[(234,264,"API-007 PARTNER detail/form; no two-location staff case.")],
"src/tests/services/test_lay_mau_doi_tac_db.py":[(74,78,"API-007 internal partner.work setup only.")],
"src/tests/services/test_doi_tac_nhan_mau_la_xong_db.py":[(117,240,"API-007 sample/return tests; no cross-location.")],
"src/tests/services/test_doi_tac_tu_thu_db.py":[(332,404,"API-007 collect/void tests; no cross-location.")],
}
coverage_map={}
all_evidence = [(e["path"],e["line"],e["end_line"],e["detail"])
                for f in added for e in f["main_validation"]["evidence"]]
all_evidence += [(e["path"],e["line"],e["end_line"],e["detail"])
                 for e in patient["main_validation"]["evidence"][-len(patient_specs):]]
for path,start,end,detail in all_evidence:
    row=coverage_map.setdefault(path,{"path":path,"read_ranges":[],"notes":[]})
    row["read_ranges"].append({"start":start,"end":end}); row["notes"].append(detail)
for path,ranges in extra.items():
    lines=(PINNED/path).read_text().splitlines()
    row=coverage_map.setdefault(path,{"path":path,"read_ranges":[],"notes":[]})
    for start,end,note in ranges:
        if end>len(lines): raise ValueError(f"coverage range out of bounds: {path}:{start}-{end}")
        row["read_ranges"].append({"start":start,"end":end}); row["notes"].append(note)
file_map={x["path"]:x for x in ledger["files"]}
for row in coverage_map.values():
    row["read_ranges"]=[{"start":a,"end":b} for a,b in sorted({(x["start"],x["end"]) for x in row["read_ranges"]})]
    row["sha256"]=digest(PINNED/row["path"]); row["depth"]="targeted_trace"
    row["notes"]="Round 34: "+" ".join(dict.fromkeys(row["notes"]))+" Partial path trace; tests read, not run."
    item=file_map.get(row["path"])
    if item is None: raise SystemExit("Path missing from main ledger: "+row["path"])
    if item["status"] not in {"read","traced"}: item["status"]="traced"
    suffix="Round 34 targeted semantic trace; see blocks/round34.coverage.json; partial only."
    if suffix not in item.get("method",""): item["method"]=(item.get("method","")+" | "+suffix).strip(" |")
coverage={
"round":34,"snapshot_sha":PIN_SHA,"mode":"read_only_exact_main_static_semantic_review",
"scope":["doctor-board authorization and patient PII","result-file list completeness and filter ordering",
"treatment-stage CSKH marker concurrency","new-booking selected-location availability",
"doctor assignment queue truncation and reminder recovery","partner detail/actions across clinic locations"],
"method":"Trace active UI/BFF → FastAPI/service → query/test; verify SHA and excerpts against immutable pinned Git snapshot. No ClinicAI runtime.",
"result":"Extended SEC-027; added CLIN-050/051/052/053, OPS-010 and API-007. Static only; tests read, not run.",
"files":sorted(coverage_map.values(),key=lambda x:x["path"])}
save("blocks/round34.coverage.json",coverage)
(ROOT/"blocks/round34.md").write_text(
"# Round 34 — "+LOCAL+", source-only\n\n"
"Source pin: exact Git SHA "+PIN_SHA+" at "+str(PINNED)+". No app/migration change; no production data, secrets or PHI accessed.\n\n"
"- SEC-027 extended to legacy doctor-board; no active dashboard caller found and the route requires backend service key, so current browser reachability is unconfirmed.\n"
"- CLIN-050: patient-wide file cap happens before UI filters to appointment/order; recovery list has a second cap without completeness metadata.\n"
"- CLIN-051: simultaneous near-end treatment marker requests can duplicate CSKH history; existing test is sequential.\n"
"- CLIN-052: new-booking availability uses staff identity location while create uses selected location; server write validation remains authoritative.\n"
"- CLIN-053: schedule update commits before the separate reminder marker; active UI ignores marker failure.\n"
"- OPS-010: assignment queue caps each group at 500 while the active page ignores truncation metadata.\n"
"- API-007: internal partner-work detail/actions omit target location check; PARTNER role retains intentional multi-location access.\n"
"- Tests read, not run. No app, API, DB, provider, VPS, production, secret or PHI use. Full source audit remains incomplete.\n")
save("PHAT-HIEN.json",findings)
save("MAIN-PHAM-VI.json",ledger)

state=json.loads((ROOT/"STATE.json").read_text())
counts=Counter(x["status"] for x in ledger["files"])
suffixes={".py",".pyi",".ts",".tsx",".js",".jsx",".mjs",".cjs",".sql",".sh",".bash",".go",".rs",".java",".kt",".css",".html"}
code=[x for x in ledger["files"] if Path(x["path"]).suffix.lower() in suffixes]
codecounts=Counter(x["status"] for x in code)
sev=Counter(x["severity"] for x in findings)
ev=Counter(x["evidence_level"] for x in findings)
ms=Counter(x["main_validation"]["status"] for x in findings)
state.update({
"updated_at":NOW,"status":"in_progress",
"phase":"round34_integrated_static_findings_html_qa_pending_full_source_audit_incomplete",
"next_action":"Read TIEP-TUC.md; continue exact-main semantic review from scanned/inventoried paths, prioritizing authorization/object scope, clinical/booking, finance, pharmacy and worker recovery. Full audit remains incomplete.",
"report_version":"v0.57",
"report_round_summary":"Round 34 adds CLIN-050/051/052/053, OPS-010 and API-007; extends SEC-027 with legacy doctor-board authorization and explicit no-caller limitation. Static source only; tests read, not run. Full exact-main source audit remains incomplete.",
"report_status":"v0.57 source findings integrated; report-only HTML QA and bundle verification pending; full source audit remains incomplete."
})
state["summary"]["findings"]=len(findings)
state["summary"]["severity"]=dict(sev)
state["summary"]["evidence_levels"]=dict(ev)
state["summary"]["main_status"]=dict(ms)
state["summary"]["main_coverage"]={k:counts[k] for k in ["inventoried","traced","read","scanned","excluded"]}
state["summary"]["main_partial_traces"]=counts["traced"]
state["summary"]["main_read_files"]=counts["read"]
state["summary"]["code_like_source_files"]={
"definition":"Pinned-tree paths with common code/web/sql/shell suffixes; includes app, tests, tooling and styles.",
"total":len(code),"coverage":{k:codecounts[k] for k in ["inventoried","traced","scanned","read"]},"traced_is_partial":True}
state["summary"]["new_findings_v057"]=new_ids
state["summary"]["round34_extended_findings"]=["SEC-027"]
state["blocks"]["security"].update({"status":"round34_SEC027_doctor_board_scope_extended_API007_location_gap_added; review remains open",
"next":"Continue API/object authorization and RLS scope review. SEC-017/018 runtime checks and SEC-034 synthetic permission-scope test remain unverified."})
state["blocks"]["clinical"].update({"status":"round34_CLIN050_to_CLIN053_added; review remains open",
"next":"Continue identity, results completeness, booking and CSKH workflow review; later verify static contracts with synthetic fixtures."})
state["blocks"]["operations"].update({"status":"round34_OPS010_doctor_assignment_queue_cap_added; review remains open",
"next":"Continue queue ownership, completeness and recovery review; production volume remains unknown."})
state["limits"]=list(dict.fromkeys(state.get("limits",[])+[
"Round 34 additions are static exact-main traces; tests were read but not run. No app/API/DB/provider/production/secret/PHI access.",
"CLIN-050/OPS-010 require a list cap to be reached; production volume is unknown. API-007 is same-clinic cross-location and requires known UUID plus partner.work.",
"CLIN-053 requires the reminder POST to fail after schedule PATCH commits; no fault injection or incident evidence. Doctor-board has no active dashboard caller found and requires backend service key."]))
save("STATE.json",state)
with (ROOT/"NHAT-KY.md").open("a") as log:
    log.write("\n\n## Round 34 — "+LOCAL+"\n\n"
    "Thêm CLIN-050/051/052/053, OPS-010, API-007 và mở rộng SEC-027 từ SHA ghim. Static only; tests đọc nhưng không chạy. "
    "HTML/package QA sẽ chạy sau integration. Không sửa app/migration; full audit vẫn mở.\n")
handoff=(
"# CURRENT HANDOFF — v0.57 (Round 34 source integration; QA pending)\n\n"
"Evidence source: Git SHA "+PIN_SHA+" at "+str(PINNED)+". Primary checkout ban đầu 543b9787 có WIP riêng; không dùng làm evidence. "
"Trả lời tiếng Việt. Không sửa app/migration, chạy ClinicAI tests/runtime/API/DB/provider, hoặc truy cập VPS/production/secrets/PHI.\n\n"
"Round 34 thêm CLIN-050 (tệp kết quả cap trước khi UI lọc lượt), CLIN-051 (race trùng marker CSKH), "
"CLIN-052 (availability dùng location identity thay vì location chọn), CLIN-053 (lịch đổi xong nhưng reminder có thể rơi), "
"OPS-010 (queue xếp bác sĩ cap 500, UI bỏ cờ cắt), API-007 (partner detail/actions thiếu target location scope). "
"SEC-027 mở rộng tới doctor-board với giới hạn: không thấy UI caller, route yêu cầu backend service key. Static only, tests read-not-run.\n\n"
"Tổng "+str(len(findings))+" findings ("+str(sev["HIGH"])+" HIGH, "+str(sev["MEDIUM"])+" MEDIUM, "+str(sev["LOW"])+" LOW). "
"Ledger "+str(len(ledger["files"]))+" paths: "+", ".join(f"{counts[k]} {k}" for k in ["read","traced","scanned","inventoried","excluded"])+". "
"Path counts are not behavior coverage. Full source audit remains incomplete.\n\n"
"## Tiếp tục\n"
"1. Read BAT-DAU-TU-DAY.md, STATE.json, NHAT-KY.md, MAIN-PHAM-VI.json, PHAT-HIEN.json, blocks/round34.md and blocks/round34.coverage.json.\n"
"2. Continue semantic review on remaining scanned/inventoried paths; prioritize authorization/object scope, clinical results/booking/CSKH, finance, pharmacy and worker recovery.\n"
"3. Build report, run validate_report.py and node verify_browser.cjs; then update HTML-QA, repackage with package_audit.py and verify with verify_bundle.py.\n"
"4. Do not declare the full audit complete until semantic and system-level checks are actually complete.\n")
(ROOT/"TIEP-TUC.md").write_text(handoff)
starter=ROOT/"BAT-DAU-TU-DAY.md"
st=starter.read_text()
intro=("## Latest checkpoint\n\nCurrent report v0.57. Read TIEP-TUC.md, STATE.json and blocks/round34.md first. "
"Round 34 findings integrated; report HTML QA and portable ZIP verification are pending. Full source audit remains incomplete. "
"Resume from immutable main SHA "+PIN_SHA+".\n\n")
if "## Latest checkpoint" in st: st=st.replace("## Latest checkpoint",intro.strip(),1)
else: st=intro+st
starter.write_text(st)
design=ROOT/"THIET-KE-DICH.md"
design_add=(
"## Bổ sung thiết kế từ Round 34 — scope theo đối tượng, completeness và phục hồi\n\n"
"- Quyền cơ sở phải kiểm trên đối tượng: X-Location-ID chỉ cung cấp context; backend so location của visit/order/file với identity. Ngoại lệ đa cơ sở của partner là policy riêng.\n"
"- Đọc tệp đúng ngữ cảnh: lọc appointment/order/bên trước giới hạn; mọi list cap phải trả cursor/has_more/total và không để UI biến phần chưa đọc thành “không có”. Áp cùng contract cho danh sách phục hồi.\n"
"- Availability và lệnh ghi dùng cùng location: selected location phải truyền đến roster/capacity và write; đổi cơ sở thì tải lại dữ liệu.\n"
"- Ý định phụ sau thao tác chính phải bền: đổi lịch và nhắc gọi khách là một command hoặc có outbox/retry, owner và trạng thái. UI không báo hoàn tất khi reminder chưa lưu hoặc chưa có recovery path.\n"
"- Idempotency phải chịu đồng thời: check-then-insert không bảo đảm replay an toàn; invariant/lock bao trùm entity và mốc nghiệp vụ, có quy tắc hoàn tác rồi làm lại.\n\n")
dt=design.read_text()
if "## Bổ sung thiết kế từ Round 34" not in dt: design.write_text(design_add+dt)
print(f"Integrated Round34: {len(findings)} findings; {len(coverage_map)} coverage paths; ledger {dict(counts)}")
