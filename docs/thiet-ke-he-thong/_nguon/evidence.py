# -*- coding: utf-8 -*-
"""Nhúng BẰNG CHỨNG: đọc file thật trong repo (chỉ đọc), lấy đúng đoạn được trích,
kèm số dòng — để mỗi khẳng định trong bản thiết kế bấm ra được nguyên văn.

Không đọc .env / secret / fixture / dump. Chỉ allowlist tiền tố an toàn.
"""
from __future__ import annotations

from pathlib import Path
import re

# Gốc kho mã: suy từ vị trí tệp này (docs/thiet-ke-he-thong/_nguon/) để bản
# sinh chạy được ở bất kỳ worktree nào, không viết cứng một đường dẫn.
ROOT = Path(__file__).resolve().parents[3]

# Tên file trong bài → đường dẫn thật + neo (dòng bắt đầu, số dòng lấy).
# Neo chọn tay để mở ra là thấy đúng chỗ đang nói, không phải đầu file vô nghĩa.
MAP: dict[str, tuple[str, int, int]] = {
    # ── backend: sổ sự kiện & async
    "event_service.py":            ("src/clinicai/services/event_service.py", 24, 60),
    "notification_relay.py":       ("src/clinicai/services/notification_relay.py", 120, 90),
    "worker.py":                   ("src/clinicai/worker.py", 96, 60),
    "audit_labels.py":             ("src/clinicai/services/audit_labels.py", 30, 60),
    "services/audit_labels.py":    ("src/clinicai/services/audit_labels.py", 30, 60),
    "core/change_broker.py":       ("src/clinicai/core/change_broker.py", 1, 40),
    "change_broker.py":            ("src/clinicai/core/change_broker.py", 1, 40),
    "events.py":                   ("src/clinicai/api/v1/routers/events.py", 1, 34),
    "notification_templates.py":   ("src/clinicai/services/notification_templates.py", 1, 30),
    # ── kernel & điều phối
    "work_item_service.py":        ("src/clinicai/services/work_item_service.py", 1, 60),
    "work_items.py":               ("src/clinicai/api/v1/routers/work_items.py", 1, 40),
    "dispatch_service.py":         ("src/clinicai/services/dispatch_service.py", 1, 40),
    "gate_rule_service.py":        ("src/clinicai/services/gate_rule_service.py", 1, 40),
    "route_derivation.py":         ("src/clinicai/services/route_derivation.py", 1, 34),
    # ── nghiệp vụ
    "booking_service.py":          ("src/clinicai/services/booking_service.py", 1, 45),
    "booking_override_service.py": ("src/clinicai/services/booking_override_service.py", 1, 30),
    "tuong_tac_cskh_service.py":   ("src/clinicai/services/tuong_tac_cskh_service.py", 1, 30),
    "recall_job_service.py":       ("src/clinicai/services/recall_job_service.py", 1, 34),
    "thong_bao_service.py":        ("src/clinicai/services/thong_bao_service.py", 1, 30),
    "episode_service.py":          ("src/clinicai/services/episode_service.py", 1, 30),
    "payment_service.py":          ("src/clinicai/services/payment_service.py", 380, 30),
    "lab_safety_service.py":       ("src/clinicai/services/lab_safety_service.py", 325, 25),
    "visit_progress_service.py":   ("src/clinicai/services/visit_progress_service.py", 1, 30),
    "man_trang_chu_service.py":    ("src/clinicai/services/man_trang_chu_service.py", 1, 30),
    "ops_status.py":               ("src/clinicai/services/ops_status.py", 1, 34),
    "luat_bac_si_service.py":      ("src/clinicai/services/luat_bac_si_service.py", 1, 24),
    "pos_relay.py":                ("src/clinicai/services/pos_relay.py", 1, 30),
    # ── nền tảng
    "core/shifts.py":              ("src/clinicai/core/shifts.py", 1, 45),
    "shifts.py":                   ("src/clinicai/core/shifts.py", 1, 45),
    "api/idempotency.py":          ("src/clinicai/api/idempotency.py", 1, 34),
    "idempotency.py":              ("src/clinicai/api/idempotency.py", 1, 34),
    "identity.py":                 ("src/clinicai/api/identity.py", 40, 70),
    "core/logging.py":             ("src/clinicai/core/logging.py", 1, 30),
    "main.py":                     ("src/clinicai/main.py", 82, 45),
    # ── AI
    "graphs/lab_triage/graph.py":  ("src/clinicai/graphs/lab_triage/graph.py", 1, 30),
    "lab_triage/graph.py":         ("src/clinicai/graphs/lab_triage/graph.py", 1, 30),
    "orchestrator/graph.py":       ("src/clinicai/orchestrator/graph.py", 40, 40),
    # ── migration
    "20260730000005_workflow_kernel.sql":     ("supabase/migrations/20260730000005_workflow_kernel.sql", 1, 30),
    "workflow_kernel.sql":                    ("supabase/migrations/20260730000005_workflow_kernel.sql", 296, 70),
    "20260731000003_visit_workflow_instantiation.sql": ("supabase/migrations/20260731000003_visit_workflow_instantiation.sql", 1, 30),
    "20260804000003_dispatch_move.sql":       ("supabase/migrations/20260804000003_dispatch_move.sql", 1, 22),
    "20260804000014_gate_rule.sql":           ("supabase/migrations/20260804000014_gate_rule.sql", 1, 30),
    "20260806000001_notify_change_for_live_screens.sql": ("supabase/migrations/20260806000001_notify_change_for_live_screens.sql", 1, 22),
    "20260806000004_luot_kham_do.sql":        ("supabase/migrations/20260806000004_luot_kham_do.sql", 1, 24),
    "20260809000005_trang_thai_cskh_suy_ra.sql": ("supabase/migrations/20260809000005_trang_thai_cskh_suy_ra.sql", 1, 26),
    "20260810000009_hoan_tac_mot_lan_cham.sql": ("supabase/migrations/20260810000009_hoan_tac_mot_lan_cham.sql", 1, 26),
    "20260730000007_pos_outbox.sql":          ("supabase/migrations/20260730000007_pos_outbox.sql", 1, 20),
    "20260815000003_notify_event_log_cho_relay.sql": ("supabase/migrations/20260815000003_notify_event_log_cho_relay.sql", 1, 18),
    "multi_tenant_foundation.sql":            ("supabase/tests/multi_tenant_foundation.sql", 1, 40),
    "tenant_scoped_rls.sql":                  ("supabase/tests/tenant_scoped_rls.sql", 1, 30),
    "role_scoped_clinical_read.sql":          ("supabase/tests/role_scoped_clinical_read.sql", 1, 30),
    # ── frontend
    "roles.ts":                    ("src/dashboard/lib/roles.ts", 1, 40),
    "work-item-status.ts":         ("src/dashboard/lib/work-item-status.ts", 1, 40),
    "RealtimeRefresher.tsx":       ("src/dashboard/app/(dashboard)/RealtimeRefresher.tsx", 1, 46),
    "event-log-redaction.ts":      ("src/dashboard/lib/event-log-redaction.ts", 1, 30),
    "src/dashboard/lib/event-log-redaction.ts": ("src/dashboard/lib/event-log-redaction.ts", 1, 30),
    # ── tài liệu repo
    "SO-LUAT.md":                  ("docs/SO-LUAT.md", 209, 30),
    "docs/SO-LUAT.md":             ("docs/SO-LUAT.md", 209, 30),
    "docs/TAM-NHIN.md":            ("docs/TAM-NHIN.md", 1, 30),
    "TAM-NHIN.md":                 ("docs/TAM-NHIN.md", 1, 30),
    "docs/kien-truc-nhieu-phong-kham.md": ("docs/kien-truc-nhieu-phong-kham.md", 55, 40),
    "kien-truc-nhieu-phong-kham.md":      ("docs/kien-truc-nhieu-phong-kham.md", 55, 40),
    "docs/GIAI-THICH-CODE.md":     ("docs/GIAI-THICH-CODE.md", 204, 40),
    "docs/DANG-LAM.md":            ("docs/DANG-LAM.md", 1, 26),
    "docs/design/clinicai-system-design-v5.md": ("docs/design/clinicai-system-design-v5.md", 1, 34),
    "docker-compose.yml":          ("docker-compose.yml", 1, 26),
    "ci.yml":                      (".github/workflows/ci.yml", 16, 55),
    # ── ADR
    "0001-modular-monolith-engine-manifest.md": ("docs/adr/0001-modular-monolith-engine-manifest.md", 1, 22),
    "0002-outbox-polling-retire-rabbitmq.md":   ("docs/adr/0002-outbox-polling-retire-rabbitmq.md", 1, 24),
    "0003-concurrency-invariants-in-postgres.md": ("docs/adr/0003-concurrency-invariants-in-postgres.md", 1, 22),
    "0011-kernel-workflow-v2-dung-ngay.md":     ("docs/adr/0011-kernel-workflow-v2-dung-ngay.md", 1, 22),
    "0012-hop-dong-backend-frontend-thay-duoc.md": ("docs/adr/0012-hop-dong-backend-frontend-thay-duoc.md", 1, 22),
    # ── bài kiểm chống lệch (bằng chứng cho "luật có người canh")
    "test_audit_labels_drift.py":   ("src/tests/test_audit_labels_drift.py", 1, 34),
    "test_ly_do_huy_drift.py":      ("src/tests/unit/test_ly_do_huy_drift.py", 1, 30),
    "test_doc_dung_cot_da_chon.py": ("src/tests/unit/test_doc_dung_cot_da_chon.py", 1, 34),
    "px-tu-che-ratchet-boundary.test.mts": ("src/dashboard/tests/px-tu-che-ratchet-boundary.test.mts", 1, 34),
    "providers/zalo.py":            ("src/clinicai/services/providers/zalo.py", 1, 26),
    "baseline_schema.sql":          ("supabase/migrations/20260714000001_baseline_schema.sql", 526, 26),
    "audit_log_service.py":         ("src/clinicai/services/audit_log_service.py", 186, 40),
    "booking.py":                   ("src/clinicai/api/v1/routers/booking.py", 470, 26),
    "20260804000013_room_serves_many_nodes.sql": ("supabase/migrations/20260804000013_room_serves_many_nodes.sql", 88, 30),
    "20260805000001_v_audit_log.sql": ("supabase/migrations/20260805000001_v_audit_log.sql", 96, 26),
    "scripts/danh-dau-event-cu-truoc-khi-bat-telegram.sql": ("scripts/danh-dau-event-cu-truoc-khi-bat-telegram.sql", 1, 20),
}

# Tên file KHÔNG có thật (thiết kế đề xuất) — không tạo chip bằng chứng, tránh hứa hão.
KHONG_CO_THAT = {
    "src/clinicai/su_kien.py", "engine/su_kien.py", "engine/viec.py", "engine/dong_ho.py",
    "engine/luat.py", "engine/policy.py", "engine/trai_nghiem.py", "engine/tin_nhan.py",
    "engine/nen.py", "engine/chieu.py", "rebuild-metric.py", "test_policy_cases.py",
    "test_ghi_su_kien_tu_choi_event_la.py", "202609xx_phase0_nen.sql",
    "202609xx_phase_a.sql", "202609xx_phase_b.sql", "phat-lai-su-kien.py",
    "kiem-duong-ghi.py", "tai.py", "kiem-vang.sh",  # ở scratchpad/chưa commit, không trong repo
}

LANG = {".py": "python", ".sql": "sql", ".ts": "ts", ".tsx": "tsx", ".mts": "ts",
        ".yml": "yaml", ".yaml": "yaml", ".md": "md", ".sh": "bash"}


def _an_toan(rel: str) -> bool:
    low = rel.lower()
    if any(t in low for t in (".env", "secret", "credential", "fixture", "dump", "seed.sql")):
        return False
    return rel.startswith(("src/", "supabase/", "docs/", ".github/", "scripts/")) or rel in {"docker-compose.yml"}


def _tach(ten: str) -> tuple[str, int | None]:
    """"ten.py:273" → ("ten.py", 273). Không có dòng thì trả None."""
    if ":" in ten:
        goc, _, so = ten.rpartition(":")
        if so.split("-")[0].isdigit():
            return goc, int(so.split("-")[0])
    return ten, None


def thu_thap(ten_trong_bai: set[str]) -> dict[str, dict]:
    """Trả về {key: {path, lang, from, lines[]}} cho những tên thật sự được trích.

    Trích kèm số dòng (``ten.py:273``) được neo QUANH dòng ấy — nếu không thì
    bấm vào một khẳng định về dòng 819 lại mở ra dòng 1, đúng kiểu bằng chứng
    trông có vẻ chắc mà không kiểm được gì.
    """
    ra: dict[str, dict] = {}
    for ten in sorted(ten_trong_bai):
        goc, dong = _tach(ten)
        if goc in KHONG_CO_THAT or goc not in MAP:
            continue
        rel, start, count = MAP[goc]
        if dong is not None:
            start, count = max(1, dong - 12), max(count, 40)
        if not _an_toan(rel):
            continue
        p = ROOT / rel
        if not p.exists():
            continue
        raw = p.read_text(encoding="utf-8", errors="replace").splitlines()
        lo = max(1, start)
        hi = min(len(raw), lo + count - 1)
        ra[ten] = {
            "path": rel,
            "lang": LANG.get(p.suffix, ""),
            "from": lo,
            "total": len(raw),
            "lines": raw[lo - 1:hi],
        }
    return ra


def kiem_thieu(ten_trong_bai: set[str]) -> list[str]:
    """Tên được trích nhưng chưa map và cũng không nằm trong danh sách 'chưa có'."""
    return sorted({_tach(t)[0] for t in ten_trong_bai}
                  - set(MAP) - KHONG_CO_THAT)
