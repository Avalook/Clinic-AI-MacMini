"""Integrate Round 36 exact-main review into the portable audit artifacts."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SNAP = Path("/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini")
SNAP_SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"

# Exact ranges/hash supplied by read-only reviewers for the pinned source tree.
FILES = {
    "src/dashboard/app/(dashboard)/thu-ngan/VatTuQuay.tsx": ([ [74, 96], [109, 127] ], "6f4307eded8d113c7fe670c372b480c312650d13aa10d9622e77f0979705759f", "Round 36: cashier add-material mutation, retry state and UI call.", "targeted_trace"),
    "src/dashboard/app/(dashboard)/_lam-viec/api.ts": ([ [212, 250] ], "ae815d5fa84b582396b10a3508193f764203a7dab930f9dfd23684c3ff90e216", "Round 36: mutation helper creates a new key and reports network failure as not recorded.", "targeted_trace"),
    "src/dashboard/app/api/luot-kham/route.ts": ([ [264, 265] ], "912e9ddf0887162cd7c21fca5e9bb54b66efa622bfe882ce0c14b890b1ba1a69", "Round 36: BFF forwards the key to the API.", "targeted_trace"),
    "src/clinicai/api/v1/routers/luot_kham.py": ([ [488, 507] ], "ddfd5649bdb8ee21a24b5ebee57e147d38675aaf72173364d5fa5e47669f986a", "Round 36: add-material endpoint does not consume the forwarded idempotency key.", "targeted_trace"),
    "src/clinicai/services/vat_tu_service.py": ([ [342, 360], [435, 453] ], "9b04c282868865dab92790c54623b8fdf4eda5b854deee34da10ce45eafc06b8", "Round 36: repeated add command increments quantity on an existing pending material line.", "targeted_trace"),
    "src/tests/services/test_vat_tu_ban_them_db.py": ([ [173, 193] ], "473d09c0840c2dd61d8120961ff30cd22a0aed60957a7ff3efca75917a2493df", "Round 36: test reads two calls as two intentional quantity additions; no response-loss case.", "targeted_test_trace"),
    "src/dashboard/tests/quay-thu-vat-tu-boundary.test.mts": ([ [59, 98] ], "0f265cb5279030e2591069eb12887ff913dad3572719cd89ce79f71f209df6b3", "Round 36: UI boundary/route allowlist coverage; no idempotency retry case.", "targeted_test_trace"),
    "src/clinicai/services/cashier_board_service.py": ([ [471, 521], [547, 588] ], "469db7b83c873eef9f0065cb93de53d67f0ff061995190841225405594097f6e", "Round 36: transaction query is capped at 1,000 and response lacks completeness metadata.", "targeted_trace"),
    "src/clinicai/api/v1/routers/cashier.py": ([ [94, 121] ], "e37295d74204bd0cb310278436e9c07a16130d563bdd41921ebb11b0a078ae00", "Round 36: cashier route returns the capped service result directly.", "targeted_trace"),
    "src/dashboard/app/api/cashier/route.ts": ([ [25, 35] ], "b01c6d21afb04b47b37c27c8b7cbe7dc1d22efd057e5ecfab71629eae88224ed", "Round 36: BFF forwards query without adding pagination metadata.", "targeted_trace"),
    "src/dashboard/app/(dashboard)/thu-ngan/GiaoDich.tsx": ([ [120, 152], [173, 181] ], "f21da62bd6b0dab34725a73ee7646376e6bc351ee68f358b41d37964fa371221", "Round 36: transaction tab renders the returned subset and computes total on that subset.", "targeted_trace"),
    "src/tests/services/test_cashier_scope_db.py": ([ [66, 112] ], "44189a0f05779c5dc36aa0a6597480b8e7c98b8a5cde5707c279a1c9f97d443a", "Round 36: test checks cashier scope/time filters, not the 1,000-row completeness cap.", "targeted_test_trace"),
    "src/dashboard/app/(dashboard)/_lam-viec/XoaTep.tsx": ([ [64, 75], [137, 143], [248, 255] ], "9c66fc8460274f0f960335ab4d4ab9919ce3c855cc6c1b5078c0be2c0d639936", "Round 36: delete/restore reports a definite network failure and refreshes only after a successful response.", "targeted_trace"),
    "src/dashboard/app/(dashboard)/_lam-viec/KhungTep.tsx": ([ [314, 326] ], "68c899dbbf086050445a870e9716d806a81f143ea6a02ff433f37adbe03797c2", "Round 36: parent reload callback for result-file changes.", "targeted_trace"),
    "src/dashboard/app/api/cskh/ket-qua/[tepId]/xoa/route.ts": ([ [9, 30] ], "29f3b32818736a36f93098c1e7fd9429c7797529802a58f61accdf2005d376c6", "Round 36: BFF delete route.", "targeted_trace"),
    "src/dashboard/app/api/cskh/ket-qua/[tepId]/khoi-phuc/route.ts": ([ [9, 20] ], "5b9268d44cdaa762075dedb07a1d069435bbf6d2b0765800c58f461280bb2b42", "Round 36: BFF restore route.", "targeted_trace"),
    "src/clinicai/api/v1/routers/cskh.py": ([ [897, 925] ], "cec03c42973f5f1c28212abbd3dc69891d0c0bb5788324d416a2ed93294d7a58", "Round 36: FastAPI delete/restore route contracts.", "targeted_trace"),
    "src/clinicai/services/tep_ket_qua_service.py": ([ [1340, 1418], [1438, 1512] ], "319301ae8f945fae34257672dc0f9777c44ff40a5f07abb8b3bf8718056ee226", "Round 36: delete/restore transaction has already-state replay branches.", "targeted_trace"),
    "src/tests/services/test_xoa_mem_tep_db.py": ([ [162, 209] ], "f6a734f2e932e7cde5fbc33253661e7fb0adfe4af028f22bfc81a02ef94a1cbe", "Round 36: delete retry is idempotent; UI response-loss is not tested.", "targeted_test_trace"),
    "src/dashboard/app/(dashboard)/_lam-viec/NutCheckOut.tsx": ([ [118, 150] ], "7383db6a0cc49df957ca8fa9b63f294e123374b900c9f14caa2fc13cb56b6a69", "Round 36: checkout network failure is shown as definitely not completed.", "targeted_trace"),
    "src/clinicai/services/checkout_service.py": ([ [760, 768] ], "538aff29032bb6ba1ad548bdcbce5a98c1c3ad005d2c51ef15040858e861f029", "Round 36: checkout retry returns already_closed after the first commit.", "targeted_trace"),
    "src/tests/services/test_hoan_tac_moi_thao_tac_db.py": ([ [490, 524] ], "1599fb995b99d283899636c3860c66cdbff782d627321775613ed7105d4ec32d", "Round 36: normal checkout/undo test read; no lost-response test.", "targeted_test_trace"),
    "src/dashboard/app/(dashboard)/phan-quyen/NhomQuyenMau.tsx": ([ [229, 231], [252, 260] ], "20bd2b051bf0a40b84a0aec38097eaa40450075e585061835db78b4476d55766", "Round 36: UI shows preset disabled and exposes a disable action; wording does not define fallback policy.", "targeted_trace"),
    "src/dashboard/app/(dashboard)/phan-quyen/BangPhanQuyen.tsx": ([ [98, 116], [214, 222] ], "3ccbea0f3f85bb65537cf0fb7e55ef6c079647cc7ae2dbfa13ac315ada16f808", "Round 36: UI apply-preset action remains available for the reviewed route.", "targeted_trace"),
    "src/dashboard/app/api/phan-quyen/route.ts": ([ [25, 35], [117, 129] ], "405aa1b031bbdeaf4ab5485917da747acdd1d7608cb7120d2325fd26cd593f2a", "Round 36: BFF apply/deactivate routes.", "targeted_trace"),
    "src/clinicai/services/permission_service.py": ([ [292, 311], [556, 603] ], "fa4aebab3761bf2487f35c8472611daa97623f46609402a55b81f5a8cb423bc3", "Round 36: deactivation leaves a row inactive; active-only lookup falls back to built-in PRESET.", "targeted_trace"),
    "src/clinicai/services/staff_service.py": ([ [141, 149] ], "10c60e19effc32cd97a35a8270827145c0018e24068d2b1f7e466fb1b1b2ff22", "Round 36: staff creation path calls default preset assignment.", "targeted_trace"),
    "supabase/migrations/20260923000016_quyen_khoi_dong.sql": ([ [24, 48] ], "9457e2c7704c45399a607f744f3a4d906ec7b9873fe67149ccb534e6b786e88c", "Round 36: SQL capability-resolution path also coalesces missing active preset to default blocks.", "targeted_trace"),
    "src/tests/services/test_permission_db.py": ([ [384, 395] ], "174834e553a18cad726220f145b1b274313a66c0c754900fccc0ed2aee8998a7", "Round 36: test checks inactive flag but not apply/create behavior after deactivation.", "targeted_test_trace"),
    "src/clinicai/services/clinic_config_service.py": ([ [514, 514] ], "890bb55bf85f7a86fe15617b4468319142ac0759b6a2dfb12cbfd0738befa332", "Round 36: room/location creation and post-commit audit boundary, extension of INF-021.", "targeted_trace"),
    "src/dashboard/app/(dashboard)/settings/clinic-config/CoSoPhong.tsx": ([ [145, 145] ], "42676851987ec0d80966a4c92e3a86dd3f83808e8d54e191b8a499ffffa1da96", "Round 36: UI reports config operation failure on returned error; retry risk is conditional.", "targeted_trace"),
    "supabase/migrations/20260804000001_dispatch_rooms.sql": ([ [15, 15] ], "e2274fe83deb99896afd63348874569037ec6592c6dde8e093c1a31f023294d0", "Round 36: room code uniqueness does not enforce uniqueness by display name.", "targeted_trace"),
    "src/dashboard/app/(dashboard)/settings/BookingPolicyCard.tsx": ([ [56, 56] ], "f10ea70d30ea2147d9e866404d1e9205c98cd38f7555b2a908db5e43d7f2b165", "Round 36: network reject may leave booking-policy UI pending; no authorization issue found.", "targeted_trace"),
    "src/clinicai/api/v1/routers/config.py": ([ [611, 611] ], "2a868481567f9f301cded3f8bd0e12b8351d0d348682f95823051ae7dc323a7f", "Round 36: backend checks config.clinic.manage and derives clinic from identity.", "targeted_trace"),
    "src/dashboard/app/(dashboard)/_lam-viec/LieuTrinhKhach.tsx": ([[64, 72], [229, 244], [327, 340]], "5c79b68416f1739cb25b4e433e734d7a2a08c230518d0a735ab3b0d65252127b", "Round 36 spot-check: soon-to-expire action and refresh-after-error behavior; sequential retry checked, concurrency is CLIN-051.", "targeted_trace"),
    "src/dashboard/app/api/cskh/lieu-trinh/[id]/route.ts": ([[31, 40]], "7b625b72fca9df26a891b5356752118350c6416c301a1e5a60e820d91cedee9c", "Round 36 spot-check: BFF route for soon-to-expire action.", "targeted_trace"),
    "src/clinicai/api/v1/routers/lieu_trinh.py": ([[233, 243]], "37dc5b3c5b4bdfba52cd488889ec833fa654e7454d750efcb74a546a7bea67ff", "Round 36 spot-check: API action route.", "targeted_trace"),
    "src/clinicai/services/lieu_trinh_service.py": ([[1434, 1483]], "fea95c576932cc63f17436ce9a74a390d8c8b400fae32e84bd0652882ad26452", "Round 36 spot-check: sequential replay returns existing interaction; simultaneous race maps to CLIN-051.", "targeted_trace"),
    "src/tests/services/test_lieu_trinh_sap_het_db.py": ([[210, 227]], "1cce39a764257ca9e9de11e71800e48084285447df01dc76aecc189b3d5d3e18", "Round 36 spot-check: sequential retry only; no concurrent test.", "targeted_test_trace"),
    "src/dashboard/app/(dashboard)/_lam-viec/SoSuaChiDinh.tsx": ([[64, 69], [93, 119]], "d6a99f0e1ed25e2ba85cefa1a4ae142a45682f457ca0d21ba91d34a8a6f7941d", "Round 36 spot-check: undo action refreshes through SSE; no separate UI defect.", "targeted_trace"),
    "src/dashboard/app/(dashboard)/_lam-viec/hoan-tac.ts": ([[30, 40]], "4799050eb62478522f4a2fa4c36687a53981561d1768c25d9d6e84887a4b6ef3", "Round 36 spot-check: undo command helper.", "targeted_trace"),
    "src/clinicai/api/v1/routers/hoan_tac.py": ([[135, 146]], "168828b95be1608837999688697eaf8d1e89551ccc0a80046271ae918bd5b3ea", "Round 36 spot-check: undo route.", "targeted_trace"),
    "src/clinicai/services/so_sua_chi_dinh_service.py": ([[653, 717]], "456259c038d2159e7c84805296a9d6b1609c3f1256cbdc6e3025d74216c2d823", "Round 36 spot-check: undo transaction and already-state branch.", "targeted_trace"),
    "src/tests/services/test_so_sua_chi_dinh_db.py": ([[152, 191]], "cf5c01991c2f2ba07b1615a80171eea3d433aee481ccc4ffcb5bda7cf54cfc46", "Round 36 spot-check: undo replay idempotency; no new finding.", "targeted_test_trace"),
    "src/dashboard/app/(dashboard)/_lam-viec/DoiPhong.tsx": ([[139, 164]], "ec2d8f1e63c32a90ba03852dee0b535dae90fa0f3a6222309590f5d09227c0bf", "Round 36 spot-check: expected revision and reload on conflict.", "targeted_trace"),
    "src/dashboard/app/api/luot-kham/route.ts": ([[69, 80], [107, 109], [264, 265]], "912e9ddf0887162cd7c21fca5e9bb54b66efa622bfe882ce0c14b890b1ba1a69", "Round 36 spot-check: action mapping and forwarded idempotency key.", "targeted_trace"),
    "src/clinicai/services/service_routing_service.py": ([[1249, 1296], [1330, 1334]], "872ba98d465a775db628d71d5a47fc8ef10c98897582ce22635c053d50712967", "Round 36 spot-check: routing revision compare-and-swap.", "targeted_trace"),
    "src/tests/services/test_service_routing_db.py": ([[454, 462], [485, 498]], "cf6e6047d34018106301cdf9b22a5e2f4724c8f74d48a62e9082234771a24741", "Round 36 spot-check: same-key replay and stale-revision competition allow one winner.", "targeted_test_trace"),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(name: str):
    return json.loads((ROOT / name).read_text())


def save(name: str, data) -> None:
    (ROOT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def excerpt(path: str, start: int, end: int) -> str:
    p = SNAP / path
    raw = p.read_bytes()
    expected = FILES[path][1]
    actual = sha256(raw)
    if actual != expected:
        raise SystemExit(f"Pinned source hash mismatch: {path} expected={expected} actual={actual}")
    lines = p.read_text().splitlines()
    if start < 1 or end > len(lines):
        raise SystemExit(f"Line range outside source: {path}:{start}-{end} ({len(lines)} lines)")
    return "\n".join(f"{i}: {lines[i - 1]}" for i in range(start, end + 1))


def add_evidence(finding: dict, path: str, start: int, end: int, detail: str) -> None:
    digest = FILES[path][1]
    general = finding.setdefault("evidence", [])
    if not any(e.get("path") == path and e.get("line") == start and e.get("end_line") == end for e in general):
        general.append({"path": path, "line": start, "end_line": end, "detail": detail})
    main = finding.setdefault("main_validation", {"sha": SNAP_SHA, "status": "still_present_on_main", "note": "", "evidence": [], "production_verified": False})
    main["sha"] = SNAP_SHA
    main["status"] = "still_present_on_main"
    main["production_verified"] = False
    entries = main.setdefault("evidence", [])
    if not any(e.get("path") == path and e.get("line") == start and e.get("end_line") == end for e in entries):
        entries.append({"path": path, "line": start, "end_line": end, "sha256": digest, "excerpt": excerpt(path, start, end)})
    hashes = finding.setdefault("source_hashes", {})
    existing = hashes.get(path)
    if existing and existing != digest:
        raise SystemExit(f"Finding source hash drift: {finding['id']} {path}")
    hashes[path] = digest


def add_text(obj: dict, key: str, text: str) -> None:
    value = obj.get(key, "")
    if text not in value:
        obj[key] = (value.rstrip() + " " + text).strip()


def main() -> None:
    head = __import__("subprocess").check_output(["git", "-C", str(SNAP), "rev-parse", "HEAD"], text=True).strip()
    if head != SNAP_SHA:
        raise SystemExit(f"Wrong audit snapshot: {head}")

    findings = load("PHAT-HIEN.json")
    by_id = {x["id"]: x for x in findings}
    # Add only exact, range-checked source evidence to existing finding families.
    f = by_id["FIN-003"]
    add_text(f, "summary", " Round 36: the same lost-response/retry family affects adding billable materials: the BFF supplies a per-call key, but the FastAPI handler does not consume it and the service increments an existing pending line. This expands the demonstrated retry risk beyond medication rows; it does not establish a production occurrence.")
    add_text(f, "trigger", " Round 36 also applies when a material-add request commits and its response is lost, then the same user intent is retried.")
    add_text(f, "impact", " For materials, the retry can increase quantity and invoice amount for one intended add; the condition is static and production frequency is unknown.")
    add_text(f, "recommendation", " Extend the stable command/receipt contract to add-material mutations; one user intent must reuse its command ID through response-loss retries, while a new intentional add gets a new ID.")
    add_text(f, "acceptance", " Add a fault-injection case that commits a material quantity increment, drops the response, and retries the same command ID; quantity and amount change once. A second intentional add with a new ID increments once more.")
    add_text(f["main_validation"], "note", " Round 36 exact-main static trace adds the analogous billable-material path; no production occurrence or HTTP response-loss reproduction is claimed.")
    add_evidence(f, "src/dashboard/app/(dashboard)/thu-ngan/VatTuQuay.tsx", 115, 122, "UI preserves the add intent after a failed request, making an operator retry possible.")
    add_evidence(f, "src/dashboard/app/(dashboard)/_lam-viec/api.ts", 212, 250, "The helper creates a fresh per-call idempotency value and labels network exception as not recorded; the material path's server handler does not consume it.")
    add_evidence(f, "src/dashboard/app/api/luot-kham/route.ts", 264, 265, "BFF forwards Idempotency-Key to the backend.")
    add_evidence(f, "src/clinicai/api/v1/routers/luot_kham.py", 488, 507, "Material add handler has no idempotency dependency.")
    add_evidence(f, "src/clinicai/services/vat_tu_service.py", 436, 442, "Existing pending line quantity is incremented on another add call.")
    add_evidence(f, "src/tests/services/test_vat_tu_ban_them_db.py", 173, 193, "Existing test treats two calls as two intentional increments; it does not cover a lost response.")
    add_evidence(f, "src/dashboard/tests/quay-thu-vat-tu-boundary.test.mts", 59, 98, "Boundary test covers route/UI structure, not retry idempotency.")

    f = by_id["FIN-005"]
    add_text(f, "summary", " Round 36: the cashier transaction tab has a separate 1,000-row cap; API/BFF expose no completeness metadata and GiaoDich.tsx computes the displayed count and paid total from only the returned subset. This is the same silent-truncation family, with a distinct endpoint and threshold from the 3,000-row history/export paths.")
    add_text(f, "trigger", " A filtered cashier period/type with more than 1,000 matching payment cycles is truncated before rendering.")
    add_text(f, "impact", " On that condition, older cycles are omitted and the tab's displayed count and paid total are lower than the full filtered result; no measured clinic volume establishes that the threshold has been crossed.")
    add_text(f, "recommendation", " Use stable keyset pagination with has_more/total_count. Compute financial aggregates from the complete filtered set, separate from the currently visible page.")
    add_text(f, "acceptance", " Test above 1,000 matching transactions: pages cover the full ordered set with no gaps; total_count and aggregate equal the full fixture; the UI clearly marks partial pages and does not label a page subtotal as the total.")
    add_text(f["main_validation"], "note", " Round 36 adds a distinct 1,000-row transaction-tab cap to the existing 3,000-row history/export evidence; actual threshold occurrence remains unverified.")
    add_evidence(f, "src/clinicai/services/cashier_board_service.py", 517, 522, "Query ends with LIMIT 1000 and returns the capped transaction set.")
    add_evidence(f, "src/clinicai/api/v1/routers/cashier.py", 94, 121, "Route returns the board service payload directly without completeness metadata.")
    add_evidence(f, "src/dashboard/app/api/cashier/route.ts", 25, 35, "BFF forwards the request without pagination/completeness fields.")
    add_evidence(f, "src/dashboard/app/(dashboard)/thu-ngan/GiaoDich.tsx", 147, 152, "Paid total is reduced from the response list.")
    add_evidence(f, "src/tests/services/test_cashier_scope_db.py", 66, 112, "Existing test checks scope and time filtering, not the row cap or completeness contract.")

    f = by_id["FE-023"]
    f["title"] = "Một số thao tác ghi chưa mô hình hóa kết quả chưa xác định khi mất phản hồi"
    add_text(f, "summary", " Round 36 extends the same UI state family to result-file delete/restore and checkout: the client reports a definite failure and does not refresh on a lost response, while the backend has already-state replay behavior. No duplicate side effect was demonstrated for these two operations; the financial duplicate cases remain separately tracked in FIN-003, PHAR-004 and LAB-001.")
    add_text(f, "trigger", " Also applies when a file delete/restore or visit checkout commits but the network response is lost before the UI receives it.")
    add_text(f, "impact", " In the delete/restore and checkout cases reviewed in Round 36, staff may see an incorrect failure message and stale status; the backend retry branches are idempotent/already-state, so no duplicate record or side effect is claimed here.")
    add_text(f, "recommendation", " For every write, distinguish rejected-before-commit from unknown-after-send. On unknown, reload authoritative state; only offer a retry after confirming it is safe, and keep the pending indicator from becoming an unsupported success/failure assertion.")
    add_text(f, "acceptance", " Add component fault-injection after backend commit but before response delivery for delete, restore and checkout: UI shows unknown then reconciles from a fresh read; repeated safe action yields already-state and no duplicate event.")
    add_text(f["main_validation"], "note", " Round 36 extends the existing UI unknown-write family to file delete/restore and checkout. Their backend already-state branches make retries safe in the inspected cases; no UI fault injection or production occurrence is claimed.")
    add_evidence(f, "src/dashboard/app/(dashboard)/_lam-viec/XoaTep.tsx", 64, 75, "Network exception is stated as definitely not written.")
    add_evidence(f, "src/dashboard/app/(dashboard)/_lam-viec/XoaTep.tsx", 137, 143, "Delete callback/refresh runs only after successful response.")
    add_evidence(f, "src/dashboard/app/(dashboard)/_lam-viec/NutCheckOut.tsx", 147, 150, "Checkout network exception is stated as definitely not checked out.")
    add_evidence(f, "src/clinicai/services/tep_ket_qua_service.py", 1364, 1367, "Repeated delete returns already after the row is deleted.")
    add_evidence(f, "src/clinicai/services/checkout_service.py", 760, 768, "Repeated close returns already_closed after checkout commit.")
    add_evidence(f, "src/tests/services/test_xoa_mem_tep_db.py", 162, 209, "Existing test verifies idempotent delete replay; no UI response-loss test.")
    add_evidence(f, "src/tests/services/test_hoan_tac_moi_thao_tac_db.py", 490, 524, "Existing normal checkout/undo test does not cover dropped response.")

    f = by_id["INF-021"]
    add_text(f, "summary", " Round 36 adds room/location creation to the same post-commit audit-boundary family: the configuration mutation and generated ID can be persisted before the audit write returns an error. Retrying after the UI reports failure may create a second room because names are not uniquely constrained in the reviewed schema. This duplicate-on-retry path is static and conditional; no fault injection or production occurrence is claimed.")
    add_text(f, "trigger", " Also applies if room/location creation commits but the post-commit audit write fails or its response is lost, followed by an operator retry.")
    add_text(f, "impact", " An operator can receive an error while a room has already been created; a retry can create a second same-named room if the server generates a new identifier. This is conditional and was not reproduced.")
    add_text(f, "recommendation", " Include room creation and audit/event persistence in one transaction or transactional outbox; use a stable command receipt for retry and enforce an explicit same-location room identity rule if duplicate names are invalid.")
    add_text(f, "acceptance", " Inject audit failure after room creation: mutation and audit either both persist or both roll back; retry of the same command returns the original room. A new intentional command follows the documented duplicate-name policy.")
    add_text(f["main_validation"], "note", " Round 36 extends this existing post-commit audit boundary to the room creation path. Static only; duplicate-on-retry is conditional and not reproduced.")
    add_evidence(f, "src/clinicai/services/clinic_config_service.py", 514, 514, "Reviewed room creation path uses the configuration service's post-commit audit helper.")
    add_evidence(f, "src/dashboard/app/(dashboard)/settings/clinic-config/CoSoPhong.tsx", 145, 145, "UI displays an error from the operation, leaving retry plausible if commit already occurred.")
    add_evidence(f, "supabase/migrations/20260804000001_dispatch_rooms.sql", 15, 15, "Reviewed room schema does not enforce uniqueness by display name.")

    # Exact-main coverage ledger: only files/ranges actually read in this round.
    manifest = load("MAIN-PHAM-VI.json")
    if manifest["sha"] != SNAP_SHA or Path(manifest["snapshot"]) != SNAP:
        raise SystemExit("MAIN-PHAM-VI is not pinned to the expected source tree")
    rows = {r["path"]: r for r in manifest["files"]}
    coverage_files = []
    for path, (ranges, expected_sha, note, depth) in FILES.items():
        p = SNAP / path
        raw = p.read_bytes()
        actual = sha256(raw)
        if actual != expected_sha:
            raise SystemExit(f"Coverage hash mismatch: {path}: {actual} != {expected_sha}")
        lines = raw.decode("utf-8").splitlines()
        for start, end in ranges:
            if end > len(lines):
                raise SystemExit(f"Coverage range exceeds file: {path}:{start}-{end}")
        if path not in rows:
            raise SystemExit(f"Source file missing from pinned scope manifest: {path}")
        row = rows[path]
        if row.get("sha256") and row["sha256"] != actual:
            raise SystemExit(f"Scope-ledger hash mismatch: {path}")
        row["sha256"] = actual
        row["lines"] = len(lines)
        row["status"] = "read" if row.get("status") == "read" else "traced"
        row["round36_ranges"] = [{"start": a, "end": b} for a, b in ranges]
        row["round36_sha256"] = actual
        prior = row.get("method", "")
        segment = "Round 36: targeted exact-main semantic trace; see blocks/round36.coverage.json."
        if segment not in prior:
            row["method"] = (prior + " | " + segment).strip(" |")
        coverage_files.append({"path": path, "read_ranges": [{"start": a, "end": b} for a, b in ranges], "sha256": actual, "lines": len(lines), "depth": depth, "notes": note})
    manifest["last_updated_round"] = 36
    save("MAIN-PHAM-VI.json", manifest)

    coverage = {
        "round": 36,
        "snapshot_sha": SNAP_SHA,
        "mode": "read_only_exact_main_static_semantic_review",
        "scope": ["cashier material addition and transaction-list completeness", "UI unknown write outcomes", "permission preset deactivation and fallback", "clinic room creation audit boundary", "booking policy and selected settings authorization"],
        "method": "Static exact-main trace with whole-file SHA-256 and line ranges. Tests read-not-run; no ClinicAI runtime/API/DB/provider, production, secrets or PHI access.",
        "result": "No independent new finding ID. FIN-003 and FIN-005 expanded; FE-023 and INF-021 expanded. Inactive permission preset fallback held for product-contract clarification; no new authorization bypass found in reviewed paths.",
        "files": coverage_files,
        "held_observations": [
            {"id": "PERMISSION-PRESET-INACTIVE-FALLBACK-001", "classification": "held_product_contract_question", "observation": "xoa_nhom sets an existing system preset active=false, while active-only service/SQL lookups fall back to the built-in PRESET when no active row is returned. A staff-create path also invokes default preset assignment. UI says 'đã tắt' but does not state whether fallback is prohibited; code/docs do not resolve whether inactive means unavailable or use built-in defaults.", "impact": "Could reapply default capabilities after a manager deactivates a preset, depending on intended product contract. The action remains manager-gated; this is not an unprivileged authorization bypass.", "evidence": [{"path": "src/clinicai/services/permission_service.py", "lines": "573-582,590-603", "sha256": FILES["src/clinicai/services/permission_service.py"][1]}, {"path": "supabase/migrations/20260923000016_quyen_khoi_dong.sql", "lines": "38-42", "sha256": FILES["supabase/migrations/20260923000016_quyen_khoi_dong.sql"][1]}, {"path": "src/dashboard/app/(dashboard)/phan-quyen/NhomQuyenMau.tsx", "lines": "229-231,252-260", "sha256": FILES["src/dashboard/app/(dashboard)/phan-quyen/NhomQuyenMau.tsx"][1]}], "next": "Product owner defines whether inactive presets are never assignable or whether immutable built-in fallback is expected; then make API/UI/docs consistent and add create/apply-after-deactivate tests."},
            {"id": "ROOM-PRESET-CONCURRENCY-001", "classification": "held_static_race", "observation": "PermissionService.doi_man may overwrite a concurrent preset edit in a read-modify-write path; full UI/race trace was not completed.", "next": "Trace the full apply/overwrite flow and validate with a barrier-driven synthetic test before promotion."}
        ],
        "not_reviewed": ["Remaining settings screens and complete clinic_config_service.py branches", "Unread cashier/payment/refund/settlement paths", "Remaining _lam-viec selection/booking/queue/partner/phieu-kham UI", "Runtime or fault-injection scenarios for the findings above"],
        "full_source_audit_complete": False
    }
    save("blocks/round36.coverage.json", coverage)

    # Keep the existing domain blocks as concise indices; round36.coverage.json is the evidence ledger.
    round_note = """# Round 36 — 20/10/2026, exact-main static review

Source pin: `956ba4f236b1c92f1280d2097018c199e90ce8c7` at `/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini`. Read-only semantic review. Tests were read, not run; no app/API/DB/provider, production, secrets or PHI access.

- **FIN-003 expanded:** adding billable material can be retried after an uncertain response; frontend creates per-call idempotency value, endpoint does not consume it, and service increments the existing pending quantity. This reinforces the existing duplicate-add finding; no new ID or production occurrence claim.
- **FIN-005 expanded:** cashier transaction list has a separate `LIMIT 1000`; response lacks completeness metadata and UI totals the returned subset. Threshold occurrence is unknown.
- **FE-023 expanded:** result-file delete/restore and checkout may show a definite failure and stale UI after a lost response. Backend already-state branches make these retries safe in the inspected paths; no duplicate effect or runtime reproduction is claimed. More consequential duplicate-write examples remain in LAB-001, PHAR-004 and FIN-003.
- **INF-021 expanded:** room creation joins the post-commit audit-failure family. A retry may create a same-named room under the reviewed schema; conditional static path, not reproduced.
- **Held:** inactive permission preset is excluded by active-only lookup, then built-in defaults are used. UI shows “đã tắt” without defining fallback semantics; management action is gated, so this is not an unprivileged auth bypass. Clarify product contract before severity/finding promotion. Concurrent preset overwrite remains an unvalidated race candidate.
- Settings paths reviewed did not show a new authorization bypass; API derives clinic from identity and checks `config.clinic.manage` on the booking-policy route.

Exact ranges/hashes and remaining gaps: `blocks/round36.coverage.json`. Ledger includes 2,890 source paths but status counts are not behavioral coverage. **Full source audit remains incomplete.**
"""
    (ROOT / "blocks/round36.md").write_text(round_note)

    # Update existing domain block summaries without replacing prior history.
    for name, marker, text in [
        ("blocks/finance.md", "## Round 36", """## Round 36
FIN-003 được mở rộng sang thêm vật tư có tính tiền với retry làm tăng số lượng; FIN-005 thêm tab giao dịch có cap 1.000 và tổng chỉ tính trên subset. Chi tiết exact-main ở blocks/round36.coverage.json; không phát sinh ID mới, không có production occurrence evidence.
"""),
        ("blocks/frontend.md", "## Round 36", """## Round 36
FE-023 được mở rộng với xóa/khôi phục tệp và checkout: UI khẳng định lỗi sau exception trong khi backend có nhánh already-state. Giữ mức LOW, không kết luận duplicate side effect; không chạy UI fault injection.
"""),
        ("blocks/security.md", "## Round 36", """## Round 36
Không phát hiện bypass phân quyền mới trong lát settings. Giữ PERMISSION-PRESET-INACTIVE-FALLBACK-001 ở dạng held: active=false và fallback PRESET chưa có product contract rõ; đây không phải đường bypass cho người không có quyền quản lý. Chi tiết ở blocks/round36.coverage.json.
"""),
    ]:
        p = ROOT / name
        content = p.read_text()
        if marker not in content:
            p.write_text(content.rstrip() + "\n\n" + text)

    state = load("STATE.json")
    state["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    state["status"] = "in_progress"
    state["phase"] = "round36_v059_findings_extended_and_handoff_refresh_full_source_audit_incomplete"
    state["next_action"] = "Continue exact-main semantic review of remaining scanned/inventoried modules. Prioritize API/object authorization and RLS; unread patient/clinical and booking flows; remaining cashier/refund/settlement; _lam-viec selection/queue/partner/phieu-kham UI; and migrations/worker contracts. Resolve held preset semantics with product owner. Full source audit remains incomplete."
    state["report_status"] = "v0.59; Round 36 integrated; report validator/browser QA and portable package to be rerun; full source audit remains incomplete."
    state["report_version"] = "v0.59"
    state["report_round_summary"] = "Round 36 exact-main static review: FIN-003/FIN-005/FE-023/INF-021 expanded; no new finding ID. Inactive permission-preset fallback remains held pending product contract; no new auth bypass found in reviewed settings paths. Tests read-not-run; full source audit incomplete."
    blocks = state.setdefault("blocks", {})
    blocks.setdefault("finance", {})["status"] = "round36_FIN003_material_retry_and_FIN005_1000_row_tab_expanded_review_open"
    blocks["finance"]["notes"] = "blocks/finance.md"
    blocks["finance"]["next"] = "Verify payment/refund/settlement paths not yet covered; FIN-017 six-visit debt fixture, FIN-004 fractional course and INF-007 prepay receipt crash remain unverified."
    blocks.setdefault("frontend", {})["status"] = "round36_FE023_unknown_write_ui_expanded_review_open"
    blocks["frontend"]["notes"] = "blocks/frontend.md"
    blocks["frontend"]["next"] = "Continue remaining dashboard paths, especially booking/selection/queue/partner/phieu-kham; add focused UI response-loss and per-panel freshness tests only after completing source trace."
    blocks.setdefault("security", {})["status"] = "round36_settings_review_no_new_bypass_preset_fallback_held_review_open"
    blocks["security"]["notes"] = "blocks/security.md"
    blocks["security"]["next"] = "Continue API/object authorization and RLS scope review; clarify inactive preset fallback contract; SEC-017/018 runtime and SEC-034 synthetic permission scope remain unverified."
    blocks.setdefault("operations", {})["next"] = "Continue queue ownership, configuration mutation outcome, event completeness and recovery review; production volume/occurrence remains unknown."
    blocks["round36"] = {"status": "integrated_static_checkpoint_report_qa_pending", "notes": "blocks/round36.md", "coverage": "blocks/round36.coverage.json", "result": "No new ID; four existing findings extended; one preset-fallback contract held; full source audit incomplete."}
    bundle_count = sum(1 for p in ROOT.rglob("*") if p.is_file() and p.name not in {"tiep-quan-clinicai-2026-10-19.zip", "MANIFEST-GOI.json"} and ".DS_Store" not in p.parts and "__pycache__" not in p.parts)
    state["portable_bundle_expected_files"] = bundle_count
    state["portable_bundle_status"] = "pending_round36_rebuild_and_verification"
    state["report_html_sha256"] = "pending_rebuild"
    state["full_source_audit_complete"] = False
    save("STATE.json", state)

    # Transfer notes explicitly separate report QA from product verification.
    handoff = ROOT / "TIEP-TUC.md"
    t = handoff.read_text()
    old_header = "# CURRENT HANDOFF — v0.58 (Round 35; report QA and portable package verified)"
    t = t.replace(old_header, "# CURRENT HANDOFF — v0.59 (Round 36 integrated; report/package QA pending)")
    t = t.replace("Round 35 không thêm ID finding: mở rộng FIN-002 với lịch sử phiếu kho NHAP/KIEM giới hạn 100 theo location mà API/UI không báo thiếu; mở rộng API-002 với route clinical-status cùng thiếu location scope, chỉ trả tên/mã và metadata tiến độ, không trả SOAP. Worker slice được dedupe vào INF/LAB/CLIN hiện có; các điểm chưa đủ hợp đồng được giữ ở dạng held trong `blocks/round35.md`. Tests được đọc nhưng không chạy.", "Round 36 không thêm ID finding: mở rộng FIN-003 (retry thêm vật tư làm tăng số lượng), FIN-005 (tab giao dịch bị cap 1.000), FE-023 (kết quả ghi chưa xác định trên UI) và INF-021 (audit sau commit khi tạo phòng). Preset quyền inactive/fallback được giữ ở dạng held vì hợp đồng sản phẩm chưa rõ; không phát hiện bypass phân quyền mới trong lát settings. Chi tiết round36 ở `blocks/round36.md` và `blocks/round36.coverage.json`. Tests được đọc nhưng không chạy.")
    t = t.replace("Tổng 192 findings (26 HIGH, 139 MEDIUM, 27 LOW). Ledger 2.890 paths: 855 read, 465 traced một phần, 1.057 scanned, 505 inventoried, 8 excluded. Path count không phải behavior coverage. **Full source audit vẫn chưa hoàn tất.**", "Tổng 192 findings (26 HIGH, 139 MEDIUM, 27 LOW); Round 36 chỉ mở rộng findings hiện có. Ledger 2.890 paths; số đếm chính xác sau vòng này được sinh từ `MAIN-PHAM-VI.json`. Path count không phải behavior coverage. **Full source audit vẫn chưa hoàn tất.**")
    t = t.replace("HTML report-only QA PASS: validator 6/6; browser QA có 192 cards, 2.890 ledger rows, desktop 1280px/mobile 375px không tràn, search/print đủ, không page error hoặc external request. HTML SHA-256 `4442e4f74ee0808684fa6b8a3ae9f1d05c1f6fb63f29e6501f61cf186c0f3d79`. Đây không phải ClinicAI QA hay chứng nhận accessibility.", "HTML report-only QA của v0.58 đã PASS. V0.59 cần chạy lại validator và browser QA sau khi dựng report; checksum final được ghi trong `HTML-QA.json` và `STATE.json`. Đây không phải ClinicAI QA hay chứng nhận accessibility.")
    t = t.replace("Portable ZIP `tiep-quan-clinicai-2026-10-19.zip` verify PASS: 315 file, CRC và byte-size/member SHA-256 đều đúng. Outer SHA-256 và per-file manifest ở `MANIFEST-GOI.json`.", "ZIP v0.58 đã verify 315 file. V0.59 cần dựng và xác minh lại sau khi hoàn tất cập nhật handoff; outer SHA-256 và per-file manifest ở `MANIFEST-GOI.json`.")
    t = t.replace("`blocks/round35.md`, `blocks/round35.coverage.json`.", "`blocks/round36.md`, `blocks/round36.coverage.json`.")
    t = t.replace("## Tiếp tục\n", "## Tiếp tục\n1. Chạy lại report validator, browser QA, build package và verify ZIP sau Round 36; cập nhật checksum final vào HTML-QA/STATE và package lần cuối.\n2. ")
    t = t.replace("2. Tiếp tục semantic review", "3. Tiếp tục semantic review")
    t = t.replace("3. Chỉ hoàn tất", "4. Chỉ hoàn tất")
    handoff.write_text(t)

    start = ROOT / "BAT-DAU-TU-DAY.md"
    b = start.read_text()
    b = b.replace("# Bắt đầu từ đây — checkpoint v0.58", "# Bắt đầu từ đây — checkpoint v0.59")
    b = b.replace("Round 35 đã tích hợp bằng chứng vào FIN-002 (lịch sử phiếu kho NHAP/KIEM bị cap 100/location) và API-002 (clinical-status endpoint thiếu location scope); không thêm ID finding mới. Worker slice được dedupe vào findings đã có, còn điểm chưa đủ hợp đồng giữ ở `blocks/round35.md`.", "Round 36 đã mở rộng FIN-003 (retry thêm vật tư), FIN-005 (tab giao dịch cap 1.000), FE-023 (UI unknown write outcome) và INF-021 (audit boundary khi tạo phòng); không thêm ID finding. Inactive permission-preset fallback còn held do chưa rõ hợp đồng sản phẩm; lát settings không thấy bypass mới. Xem `blocks/round36.md` và `blocks/round36.coverage.json`.")
    b = b.replace("Báo cáo v0.58 có **192 findings** (26 HIGH, 139 MEDIUM, 27 LOW). Report validator 6/6 và browser QA PASS. HTML SHA-256: `4442e4f74ee0808684fa6b8a3ae9f1d05c1f6fb63f29e6501f61cf186c0f3d79`. Đây chỉ là QA của báo cáo, không phải ClinicAI QA.", "Báo cáo v0.59 giữ **192 findings** (các finding hiện có được mở rộng). Chạy lại validator/browser QA sau build; checksum final ở `HTML-QA.json` và `STATE.json`. Đây chỉ là QA của báo cáo, không phải ClinicAI QA.")
    b = b.replace("ZIP tiếp quản 315 file đã verify; outer SHA-256 và từng file nằm trong `MANIFEST-GOI.json`.", "ZIP v0.58 có 315 file đã verify; v0.59 phải dựng lại sau khi hoàn thiện cập nhật handoff, outer SHA và per-file hashes nằm trong `MANIFEST-GOI.json`.")
    b = b.replace("`blocks/round35.md`, `blocks/round35.coverage.json`.", "`blocks/round36.md`, `blocks/round36.coverage.json`.")
    b = b.replace("1. Đọc TIEP-TUC.md", "1. Chạy lại report validator, browser QA và package verification cho v0.59.\n2. Đọc TIEP-TUC.md")
    b = b.replace("2. Source phải", "3. Source phải").replace("3. Tiếp tục semantic", "4. Tiếp tục semantic")
    start.write_text(b)

    journal = ROOT / "NHAT-KY.md"
    journal.write_text(journal.read_text().rstrip() + "\n\n## Round 36 — 20/10/2026, exact-main static review\n\n- Round 36 mở rộng FIN-003, FIN-005, FE-023, INF-021; không tạo ID mới. Inactive permission-preset fallback được giữ held vì product contract chưa rõ; không thấy bypass phân quyền mới trong lát settings.\n- Đã trace targeted các luồng thu ngân thêm vật tư/giao dịch, UI unknown-write delete/restore/checkout, preset/quyền settings và tạo phòng; exact hashes/ranges ở `blocks/round36.coverage.json`. Tests read-not-run; không truy cập app/API/DB/provider/production/secrets/PHI.\n- Coverage ledger giữ 2.890 paths nhưng count chỉ mô tả trạng thái file; không phải behavior coverage. Full source audit chưa xong. Report v0.59, HTML QA và ZIP verification đang chờ hoàn tất.\n")

    # Timestamp and record are deterministic apart from the operational `updated_at`.
    print(f"Integrated Round 36 on {SNAP_SHA}; {len(FILES)} exact-hash files; {len(findings)} findings; full audit remains incomplete.")


if __name__ == "__main__":
    main()
