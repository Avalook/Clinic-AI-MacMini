---
title: "AI đang có — lab triage với hard-block GROUP_C, brief, orchestrator LangGraph, tất cả tĩnh và có provenance"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "graphs/lab_triage · orchestrator/ · ADR-0005 · design v5 §5.7"
trang_thai: Một phần
tags: [clinicai, lop3-code]
---

# AI đang có — lab triage với hard-block GROUP_C, brief, orchestrator LangGraph, tất cả tĩnh và có provenance

> [!abstract] AI đúng chỗ Interpretation (phân loại kết quả) với cổng an toàn; scheduling graph tắt vì chưa nối tool thật.

Bốn graph (`src/clinicai/graphs/`): `lab_triage` (receive → fetch → classify → **persist** → advise | hard_block → create_review_tasks) · `pre_visit_brief` · `scheduling` · `task_manager` (trên `staff_task`, đã 0 dòng). `orchestrator/graph.py` định tuyến theo intent (scheduling/lab/communication/task/previsit/general) với stub khi thiếu pool/LLM. Checkpointer ở schema `langgraph` (ADR-0007: «disposable state»).

Cổng an toàn (`lab_triage/graph.py`): «The GROUP_C → hard_block routing is the safety gate: patient-facing responses are suppressed and an escalation note is set for BS review. […] enqueues exactly one URGENT LAB_REVIEW staff task with SLA=4h.» Không LLM → «safety-falls back to PENDING + requires_doctor_review=True and routes to hard_block». Classifier phải **persist trước khi phản hồi** («Classifier output must be durable before it can drive a response»).

Provenance trên `lab_result`: `triage_group`, `triage_reason`, `triage_classified_at`, `triage_model`, `requires_doctor_review`, `reviewed_by_staff_id`, `reviewed_at`, `is_finalized`. `clinical_release` + `clinical_sign_service`: bác sĩ ký mới cho phép gửi (`clinical.signed`, `clinical.released`).

Quyết định giữ (design v5 §5.7): «Kiến trúc là STATIC ROUTING, không phải agentic tool-use»; «GROUP_C chưa review thì KHÔNG một response nào tới BN»; D012 không chatbot tư vấn lâm sàng; D013 không risk-scoring. ADR-0005: LLM qua Anthropic API 2-tier, không local reasoning, chỉ voice STT on-prem (NĐ13).

Đo: `lab_result` prod **0 dòng** → lab triage chưa chạy thật ngoài test.

### Đối chiếu thesis

- Đúng vị trí: Interpretation (§5.1 «state không thể xác định chỉ bằng rule đơn giản») + Act có guardrail chặn.
- Provenance §20.10 ✅ (model + lý do + thời điểm). Thiếu `confidence` số và `expires_at`.
- Thesis xếp tóm tắt/brief, phát hiện nghẽn, ETA, đề xuất phân bổ lại là «vai trò AI ưu tiên» (§5.1) — chỉ brief có.
- Tổng-Quan §9 «Tầng 2 — Operations Copilot: đọc event/state projection → phát hiện nghẽn → GỢI Ý điều phối — shadow mode trước» chưa có, và **không thể có** trước khi có projection đáng tin (TAM-NHIN luật 1).

[[tk-ai-placement|AI đúng chỗ]] giữ nguyên tất cả và chỉ thêm: derived event có `evidence_level='inferred'` + `confidence` + `rule_or_model` khi AI phát hiện; allowlist work type cho system agent.

## Nối tới
- [[3-muc-quyen-ai|Ba mức quyền hành động]]
- [[tk-ai-placement|AI đúng chỗ]]
- [[gap-ai|Khoảng cách 14]]
- [[10-principles|10 nguyên tắc sản phẩm]]
- [[governance-event|Security, privacy, governance ở cấp event]]

## Được dẫn từ
- [[10-principles|10 nguyên tắc sản phẩm]]
- [[6-lop-san-pham|Product map 6 lớp]]
- [[3-muc-quyen-ai|Ba mức quyền hành động]]
- [[gap-ai|Khoảng cách 14]]
- [[tk-ai-placement|AI đúng chỗ]]
