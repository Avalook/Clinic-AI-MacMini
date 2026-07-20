# SO SÁNH: Web Dashboard (Next.js) vs Lõi AI (Python "đóng băng")

> Khảo sát code thật 2026-06-09 (3 luồng đọc song song, có `file:line` làm bằng). Trả lời 3 câu: (1) hai bản làm được gì, (2) web làm được thì lõi có chưa, (3) cần bổ sung gì hay đã đủ.
> ⚠️ Tài liệu này lật một giả định: **web KHÔNG phải "vỏ mỏng"** — nó là hệ vận hành gần đủ, tự viết bằng TypeScript, nối thẳng Supabase.

---

## TL;DR (5 dòng)
1. **Web** đã tự cài phần LỚN việc vận hành phòng khám bằng TS, ghi thẳng Supabase (service-role): intake+dedup nhẹ, **state machine lịch đầy đủ**, hồ sơ SOAP, lab order/nhập, CSKH log, service queue, roster tự xếp, auth/RBAC, admin user.
2. **Lõi** có 2 loại năng lực: **(A) phần AI/phán đoán mà web KHÔNG có** (lab triage GROUP_A/B/C, pre-visit brief, voice→text, orchestrator chat, MPI chấm điểm, task SLA) — đây là **giá trị thật** của lõi; **(B) phần CRUD/scheduling TRÙNG với web nhưng chưa nối UI**.
3. "Web làm được thì lõi có chưa?" → **Phần lớn CÓ** (dedup/khoá hồ sơ còn **mạnh hơn**), nhưng **chưa nối được** + **lệch bản** (patient_code có tới 3 cách sinh khác nhau).
4. "Cần bổ sung gì hay có hết?" → **Lõi gần như KHÔNG cần xây thêm capability.** Cái thiếu là **CẦU NỐI** + vài chỗ **expose API** (MPI chưa có HTTP). **Web** thiếu phần AI (lab triage, brief) — sẽ có khi bắc cầu.
5. Việc thật còn lại **không phải "hoàn thiện lõi"**, mà là: bắc cầu đọc → gộp logic trùng (chốt A/B) → surface AI vào web → deploy.

---

## PHẦN 1 — 3 nhóm năng lực (sơ đồ Venn)

```
   CHỈ WEB CÓ (bề mặt/vận hành)        CẢ HAI CÓ (TRÙNG — nợ phải gộp)        CHỈ LÕI CÓ (AI/phán đoán)
   ─────────────────────────          ───────────────────────────────       ─────────────────────────
   • State machine lịch đầy đủ         • Patient CRUD + dedup                 • Lab triage GROUP_A/B/C + safety gate
     (CSKH 2 bước, checkin, no_show,   • Sinh patient_code                    • Pre-visit brief (Sonnet tóm tắt hồ sơ)
      queue#, reassign, reschedule)    • Đặt/huỷ/xác nhận lịch                • Voice → text (PhoWhisper on-prem)
   • Hồ sơ SOAP (form ghi khám)        • Khoá hồ sơ FINALIZED (TT13)          • Orchestrator chat (phân luồng ý định)
   • Vitals điều dưỡng merge           • Event log audit                      • MPI chấm điểm có ngưỡng (70đ)
   • CSKH action log                                                          • Task SLA (staff_task quá hạn)
   • Service/procedure queue           ⚠️ Đây là chỗ LỆCH BẢN:                • Đặt lịch hội thoại (slot-filling cho Zalo)
   • Roster tự xếp lịch                  hai implementation khác nhau,        • Zalo notify (STUB, chờ key)
   • Auth + RBAC + role                  web yếu hơn lõi ở dedup/safety
   • Admin tạo user                      → phải hợp nhất
   • UI toàn bộ
```

---

## PHẦN 2 — Bảng chi tiết (theo câu hỏi "web làm được → lõi có chưa?")

**Chú giải:** ✅ lõi đã có (tương đương) · 💪 lõi có & MẠNH HƠN nhưng chưa nối UI · 🔶 cả hai có nhưng LỆCH bản (nợ gộp) · ❌ lõi không có (đúng — là việc bề mặt) · 🟢 CHỈ lõi có (web thiếu)

| Năng lực web đã làm | File web (bằng chứng) | Lõi có chưa? | Verdict |
|---|---|---|---|
| Tạo BN (form, validate, insert) | `api/patients/route.ts` | FastAPI `patients.py` + `patient_service.py` | 🔶 trùng |
| **Chống trùng BN (MPI)** | chỉ match SĐT chính xác + CCCD unique | `mpi_service.py`: chấm điểm SĐT 50 + CCCD 40 + tên fuzzy 0–10, ngưỡng 70 → `mpi_merge_queue`. **Nhưng chạy SAU insert, non-blocking, KHÔNG expose HTTP** | 💪 mạnh hơn, chưa nối |
| Sinh `patient_code` | `Date.now()+random`+retry | Python: microsecond; Bulk: `pg_advisory_xact_lock` | 🔶 **3 bản khác nhau** |
| Đặt lịch (book) | `api/appointments/route.ts` POST | `scheduling_service.create_appointment` + on-duty gate + exclusion constraint | 🔶 trùng |
| **State machine lịch** (CSKH 2 bước, checkin, undo, no_show, queue#, reassign, reschedule, →roster) | `appointments/route.ts:212-637` | Lõi chỉ có create/confirm/cancel — **KHÔNG có các trạng thái này** | ❌ workflow web-only |
| Hồ sơ SOAP (form ghi khám) | `api/clinical-record/route.ts` POST | Lõi không có form — chỉ ĐỌC context để sinh brief | ❌ web-only (bề mặt) |
| Vitals điều dưỡng merge | `clinical-record/route.ts:380-388` | — | ❌ web-only |
| **Khoá hồ sơ FINALIZED (TT13)** | app-check whitelist OPEN/IN_PROGRESS | **DB trigger** `trg_visit_finalize_immutable` (mig 017) — mạnh hơn | ✅ cả hai chặn (lõi ở tầng DB) |
| Lab order + nhập KQ | `api/lab-result/route.ts` (đặt `PENDING`) | (order là việc web) | ❌ order web-only |
| **Lab triage GROUP_A/B/C** | web để `triage_group='PENDING'`, **KHÔNG phân loại** | `tools/lab/` rules + LLM + **safety gate HTTP 403** tới khi BS duyệt | 🟢 **chỉ lõi — web đang thiếu** |
| **Pre-visit brief (AI tóm tắt hồ sơ)** | — | `graphs/pre_visit_brief/` + `POST /brief/{id}` (Sonnet) | 🟢 chỉ lõi — web thiếu |
| **Voice → text** | — | `POST /voice/transcribe` (PhoWhisper, draft=true) | 🟢 chỉ lõi — web thiếu |
| **Task SLA** (việc quá hạn) | `/tasks` là board lịch, không phải SLA | `graphs/task_manager/` + `staff_task` + check_sla | 🟢 chỉ lõi |
| **Orchestrator chat** (phân luồng ý định) | — | `orchestrator/` 7 route + `POST /orchestrator/chat` | 🟢 chỉ lõi |
| Đặt lịch **hội thoại** (slot-filling cho Zalo) | — | `graphs/scheduling/` (hỏi ngày→giờ→BS→xác nhận) | 🟢 chỉ lõi (khác kênh với web) |
| CSKH action log | `api/cskh-action/` + auto từ lịch | — | ❌ web-only |
| Service/procedure queue | `api/service-log/` | — | ❌ web-only |
| Roster tự xếp lịch | `api/roster/` | — | ❌ web-only |
| Auth + RBAC + role | `lib/roles.ts`, `clinic-session.ts` | Lõi chỉ có `X-API-Key` (không role) | ❌ web-only |
| Admin tạo user | `api/admin/users` | — | ❌ web-only |
| Event log audit | `lib/event-log.ts` (best-effort) | `event_service.py` (outbox pattern, mạnh hơn) | 🔶 cả hai có |
| Reports/analytics | placeholder | — | ❌ cả hai chưa |
| Zalo/Pancake notify | — | `tools/communication/send_zalo` **STUB** (chờ key) | 🟢 lõi (stub) |

---

## PHẦN 3 — Trả lời thẳng 3 câu hỏi của bạn

**(1) Hai bản làm được gì?**
- **Web = hệ VẬN HÀNH gần đủ** cho luồng phòng khám tay (đặt lịch → khám → ghi hồ sơ → lab → CSKH → roster), + auth/RBAC + admin. Đây là "tầng móng + bề mặt" đã chạy.
- **Lõi = bộ NÃO AI** (triage, brief, voice, orchestrator, MPI chấm điểm, task SLA) + một bản CRUD/scheduling song song nhưng chưa nối UI.

**(2) Web làm được thì lõi "đóng băng" có chưa?**
- **Phần CRUD/scheduling/khoá-hồ-sơ: CÓ** — thậm chí **mạnh hơn** ở dedup (MPI 70đ vs SĐT trần) và khoá FINALIZED (trigger DB vs app-check). **NHƯNG** lõi chưa nối UI và **lệch bản** với web.
- **Phần workflow vận hành** (state machine lịch, CSKH log, service queue, roster, auth, admin): **lõi KHÔNG có** — và **đúng**, đó là việc của bề mặt web, không phải của não.
- **Phần AI** (lab triage, brief, voice, orchestrator): **web không có, lõi có** → web đang có lỗ hổng chức năng mà lõi lấp được.

**(3) Cần bổ sung gì hay có hết rồi?**
- **Lõi gần như KHÔNG cần xây thêm năng lực.** 13 năng lực thật đã có. Cái thiếu là:
  - **Cầu nối** dashboard ↔ lõi (hiện 0 đường gọi).
  - **Expose vài API**: MPI hiện **chỉ chạy trong Python sau insert, chưa có endpoint HTTP** để web gọi trước khi tạo BN.
  - **Deploy** backend ra chỗ Vercel gọi được.
- **Web cần bổ sung** (khi bắc cầu): hiện AI lên UI (brief, lab triage) — bản thân web không tự làm được mấy cái này (cần Python).
- **Nợ phải gộp** (không phải "thiếu", mà "trùng-lệch"): patient_code (3 bản), dedup (web yếu/lõi mạnh) → phải hợp nhất 1 nguồn.

---

## PHẦN 4 — Việc thật còn lại (KHÔNG phải "hoàn thiện lõi")

| Việc | Bản chất | Chặn ngoài? |
|---|---|---|
| Bắc cầu ĐỌC: brief + lab triage lên web | Mới (adapter) — rủi ro thấp | Cần backend chạy tới được (local OK) |
| Expose MPI qua HTTP (nếu chọn route-qua-lõi) | Mới (1 endpoint mỏng) | Không |
| Gộp logic trùng (patient_code, dedup) → chốt **A/B** | Quyết định kiến trúc + refactor | Cần bạn/Planner chốt |
| Deploy backend reachable (Vercel→backend) | Hạ tầng | TLS/Caddy đang hoãn |
| Surface lab triage để web hết để `PENDING` trơ | Mới | Sau khi có cầu |

**Hướng A/B (cho phần GHI):** A = web ghi qua FastAPI lõi (1 não, cần deploy). B = đưa luật MPI xuống Postgres function dùng chung. → chốt trước khi đụng code ghi.

---
*Nguồn: khảo sát `src/dashboard/**` + `src/clinicai/**` + `scripts/data_*/**`, 2026-06-09. Chi tiết file:line trong báo cáo khảo sát phiên này.*
