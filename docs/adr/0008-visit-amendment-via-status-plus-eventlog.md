# ADR-0008 — Sửa hồ sơ đã chốt: FINALIZED→AMENDED qua RPC có audit trong event_log (thay bảng visit_amendment)

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-07-18 |
| **Deciders** | Quang (+ BS xác nhận quy trình đính chính) |
| **Liên quan** | Design doc v5 §5.5 net 1, §5.6; TT13/2011 + TT13/2025 |
| **Affected decisions (canon 06)** | Supersedes CƠ CHẾ của D009 ("chỉ tạo VisitAmendment") + mục `visit_amendment` trong D008 + A-12 ("cấm UPDATE FINALIZED row"). **GIỮ NGUYÊN INTENT**: hồ sơ chốt bất biến, mọi đính chính có dấu vết pháp lý |

## Context
Canon D009 quy định sửa hồ sơ FINALIZED bằng bảng `visit_amendment` append-only. Thực
tế: baseline 32 bảng KHÔNG có `visit_amendment` (đã bỏ khi gộp 62 migration), nhưng
guard `FINALIZED→AMENDED` trong status machine thì CÓ (baseline_schema.sql:303-315).
Nghĩa là hiện nay tồn tại một đường UPDATE hợp lệ mà **không bắt buộc audit** — vênh cả
D009 lẫn A-12, trong khi design doc vẫn viện dẫn D009 làm căn cứ compliance. Đồng thời
`event_log` append-only (retention ≥7 năm theo TT13/2011) đã là xương sống audit của hệ.

## Decision
Không khôi phục bảng `visit_amendment`. Thay bằng:
1. Đính chính CHỈ qua RPC **`amend_visit(visit_id, reason, changes jsonb)`**
   SECURITY DEFINER (service_role-only): trong **một transaction** — ghi row
   `event_log` loại `visit.amended` (payload: diff trước/sau, lý do, staff_id đã
   verify, correlation với visit) RỒI mới chuyển status FINALIZED→AMENDED và áp thay
   đổi.
2. Trigger siết lại: UPDATE trực tiếp row FINALIZED bị **CHẶN HOÀN TOÀN** ngoài đường
   RPC (kiểm tra GUC session do RPC set) — A-12 được giữ đúng tinh thần: không client
   nào UPDATE thẳng.
3. Quyền amend: giới hạn DOCTOR sở hữu + TRUONG_CA/MANAGEMENT (map quy trình "đính
   chính qua Trưởng ca" đang mô tả ở dashboard).
4. Xoá "48h age-lock" giả pháp lý ở Next route sau khi RPC + trigger sống (đợt 2,
   cùng migration 043 append-only).

## Considered Options
| Phương án | Ưu | Nhược |
|---|---|---|
| **A (chọn) status AMENDED + RPC + event_log** | tái dùng xương sống audit có sẵn (append-only, 7 năm); 0 bảng mới; 1 transaction | payload diff trong JSONB — đọc lại phải qua event_log viewer |
| B Khôi phục bảng visit_amendment (đúng nguyên văn D009) | tra cứu amendment có cấu trúc riêng | thêm bảng + luật append-only trùng vai event_log; schema đã bỏ nó có chủ đích |
| C Giữ hiện trạng (UPDATE FINALIZED→AMENDED tự do) | không phải làm gì | vi phạm D009/A-12; không dấu vết — rủi ro pháp lý thật |

## Consequences
**Tích cực:** compliance TT13 có cơ chế thật thay vì trạng thái "FINALIZED không writer";
một đường đính chính duy nhất, có phân quyền, có diff. **Tiêu cực:** cần migration
(RPC + siết trigger) + màn đọc lịch sử đính chính trong ADMIN surface (đợt 3); chữ ký
số khi FINALIZE (TT13/2025) vẫn là việc riêng ở roadmap đợt 3.
