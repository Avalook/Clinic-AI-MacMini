---
title: "experience_state — bảng đúng Spec §4, ba state pilot, communication coverage từ tuong_tac_cskh, intervention contract"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "migration 202609xx_experience_state · policy kind='experience'"
tags: [clinicai, lop5-thiet-ke]
---

# experience_state — bảng đúng Spec §4, ba state pilot, communication coverage từ tuong_tac_cskh, intervention contract

> [!abstract] Bắt đầu bằng UnexplainedWaitRisk / HandoffUncertaintyRisk / ContinuityRisk — ba cái có intervention khả thi với đội hôm nay; rule, không AI.

### Bảng (theo Spec §4 từng trường)

```sql
CREATE TABLE IF NOT EXISTS public.experience_state (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id),
    type             text NOT NULL CHECK (type IN ('informed_wait','unexplained_wait_risk','repeated_delay_risk','needs_explanation',
                                                    'handoff_uncertainty_risk','abandonment_risk','continuity_risk','high_anxiety_context')),
    clinic_patient_id uuid NOT NULL, visit_id uuid, appointment_id uuid,
    status           text NOT NULL DEFAULT 'detected' CHECK (status IN ('detected','confirmed','intervening','escalated','resolved','dismissed','expired')),
    detected_at      timestamptz NOT NULL DEFAULT now(),
    evidence_level   text NOT NULL CHECK (evidence_level IN ('observed','self_reported','inferred')),
    confidence       numeric(4,3) NOT NULL,
    evidence_event_ids uuid[] NOT NULL,
    rule_or_model    text NOT NULL, rule_version integer NOT NULL,
    severity         text NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    owner_queue      text, work_item_id uuid REFERENCES public.work_item(id),
    recommended_intervention text NOT NULL,
    review_at        timestamptz NOT NULL, expires_at timestamptz NOT NULL,
    resolved_by_event_id uuid, resolution_note text,
    dismissed_by uuid, dismiss_reason text,
    closed_at        timestamptz,
    CONSTRAINT es_closed_when_terminal CHECK ((status IN ('resolved','dismissed','expired')) = (closed_at IS NOT NULL)),
    CONSTRAINT es_dismiss_needs_reason CHECK (status <> 'dismissed' OR (dismissed_by IS NOT NULL AND dismiss_reason IS NOT NULL)),
    CONSTRAINT es_resolved_needs_event CHECK (status <> 'resolved' OR resolved_by_event_id IS NOT NULL)   -- Spec §2.6 «Resolution cần outcome event, không chỉ notification»
);
CREATE UNIQUE INDEX uq_experience_open ON public.experience_state (clinic_id, type, coalesce(visit_id, appointment_id, clinic_patient_id))
  WHERE status IN ('detected','confirmed','intervening','escalated');    -- một risk mở mỗi loại mỗi lượt
```

Lifecycle bằng Command API nhỏ: `confirm` (vai được phép — cấu hình `experience_config.confirm_roles`), `dismiss` (bắt lý do), `start_intervention` (tự khi work item ack), `resolve` (tự khi outcome event khớp — trigger giống `expectation_met_on_event`), `expire` (đồng hồ, khi `expires_at` qua mà chưa resolved — «Expired không đồng nghĩa Resolved»), `escalate` (đồng hồ + policy).

Mỗi chuyển trạng thái → `ghi_su_kien('experience.<status>', …, evidence='inferred'/'outcome', confidence, policy_id)` → stream `enc:` → hiện trên timeline.

### Communication coverage

Thêm hai cột vào `tuong_tac_cskh`: `chu_de text` (`'cho' | 'ket_qua' | 'lich' | 'huong_dan' | 'khac'` — chủ đề coverage, tách khỏi `loai`) và `hieu_luc_den timestamptz` (valid_until, mặc định `xay_ra_luc + luat_cskh.coverage_min` — cấu hình). Hàm SQL `co_coverage(patient, chu_de, tai_thoi_diem)` = tồn tại dòng `huy_luc IS NULL AND chu_de = $2 AND xay_ra_luc <= $3 AND hieu_luc_den >= $3 AND ket_qua = 'DA_LIEN_HE'`. Đúng Spec §8 sáu điều kiện (đúng bệnh nhân, đúng chủ đề, đúng vai qua `nhan_vien_staff_id`, trong window, nội dung tối thiểu qua `noi_dung NOT NULL` cho chủ đề `cho`, evidence = attestation).

### Ba state pilot và intervention contract

| State | Trigger/điều kiện (policy) | Work item | Completion evidence | Severity |
|---|---|---|---|---|
| `unexplained_wait_risk` | `time.wait_threshold` (từ move) ∧ onsite ∧ ¬coverage('cho') ∧ ¬suppression | GIAI_THICH_CHO → queue CSKH, ack 5′, complete 15′ | `cskh.tuong_tac{chu_de:'cho', ket_qua:'DA_LIEN_HE'}` | medium; high nếu > 2× ngưỡng |
| `handoff_uncertainty_risk` | `time.ack_timeout` ∧ work_item ASSIGNED | escalate → TRUONG_CA | `work_item.acknowledge` hoặc `.reassign` | medium |
| `continuity_risk` | `dispatch.checkout` ∧ open commitment | THEODOI-01 → CSKH | `work_item.acknowledge` (post-visit owner nhận) | high |

Suppression (Spec §7.1 «Không kích hoạt nếu»): `experience_config` theo tenant: `khong_lam_phien` flag trên `patient` (chưa có — thêm cột `khong_lam_phien_den`), clinical safety = có `lab_result.triage_group='GROUP_C'` chưa review → nhường clinical policy, presence không tin cậy = `visit.current_node_since` cũ hơn X giờ (freshness).

### Không làm (theo Spec)

`complaint_risk` (§6 «chưa nên dùng ở pilot nếu chỉ dựa trên mô hình dự đoán»), `high_anxiety_context` (cần self-report hoặc sensitive-service tag — có thể bật cho HMVS sau), không AI, không «bảng xếp hạng nhân viên» (§11).

### Metric (Spec §14) tính từ bảng này

precision qua `confirmed/(confirmed+dismissed)` · dismissal rate · detection latency (`detected_at − evidence occurred_at`) · % có owner · time-to-ack/intervention/resolution · unexplained waiting minutes = tổng `(coalesce(closed_at, now()) − detected_at)` của `unexplained_wait_risk` · false alarm rate.

## Nối tới
- [[experience-state|Experience State]]
- [[gap-experience-state|Khoảng cách 5]]
- [[tk-policy-engine|policy + policy_case]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[tk-communication-delivery|notification_delivery]]
- [[humane-ops|Design for Humane Operations]]
- [[tk-metrics|Metric từ event stream]]

## Được dẫn từ
- [[kill-criteria|Kill criteria, proof plan và baseline Excel + Zalo]]
- [[humane-ops|Design for Humane Operations]]
- [[journey-process-manager|Patient Journey là Process Manager]]
- [[experience-state|Experience State]]
- [[nhac-tai-kham|nhac_tai_kham + hen_goi_lai + follow_up_case]]
- [[gap-experience-state|Khoảng cách 5]]
- [[gap-process-manager|Khoảng cách 7]]
- [[gap-atc|Khoảng cách 12]]
- [[tk-policy-engine|policy + policy_case]]
- [[tk-atc-ui|Giao diện]]
- [[tk-metrics|Metric từ event stream]]
- [[tk-sensing|Sensing]]
- [[phase-b-exceptions|Phase B]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
