---
title: "Experience State — giả thuyết có bằng chứng, có lifecycle, có intervention"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §12 · Experience Spec v1"
tags: [clinicai, lop2-kien-truc]
---

# Experience State — giả thuyết có bằng chứng, có lifecycle, có intervention

> [!abstract] Không phải cảm xúc do AI đọc; suy từ event + thời gian + communication coverage; 8 state v1, 3 rule mẫu.

> «Experience State là giả thuyết có bằng chứng về trải nghiệm hiện tại của bệnh nhân, được suy ra từ event, thời gian và ngữ cảnh để kích hoạt một can thiệp hữu ích. Nó không phải cảm xúc được "AI đọc", không phải điểm hài lòng và không phải thước đo y đức của nhân viên.» — *Experience Spec, mở đầu*

> «Hai bệnh nhân cùng chờ 30 phút: người thứ nhất đã được báo rõ lý do, ETA và biết ai sẽ gọi; người thứ hai không nhận được thông tin và không biết mình có bị quên hay không. Do đó, chỉ đo Waiting Time là chưa đủ.» — *Spec §1*

**Ba lớp bằng chứng** (*§3*): Observed (bấm "Tôi cần hỗ trợ") · Self-reported · Inferred («Risk + confidence + lý do»). «Không phát PatientAnxious chỉ từ thời gian chờ.»

**Data model tối thiểu** (*§4*): `experience_state_id · type · subject{patient_id, encounter_id} · status · detected_at · evidence_level · confidence · evidence_event_ids[] · rule_or_model{id, version} · severity · owner_queue · recommended_intervention · review_at · expires_at · resolved_by_event_id`.

**Lifecycle** (*§5*): Detected → Confirmed / Intervening / Dismissed / Expired; Intervening → Resolved / Escalated. «Expired không đồng nghĩa Resolved.»

**8 state v1** (*§6*): InformedWait · UnexplainedWaitRisk · RepeatedDelayRisk · NeedsExplanation · HandoffUncertaintyRisk · AbandonmentRisk · ContinuityRisk · HighAnxietyContext. «ComplaintRisk chưa nên dùng ở pilot nếu chỉ dựa trên mô hình dự đoán.»

**Rule mẫu §7.1 UnexplainedWaitRisk** — điều kiện: encounter active · onsite · đang waiting · vượt threshold của node · **không có communication coverage hợp lệ** · không suppression. Kết quả: ExperienceRiskDetected → Communication Work Item → owner + deadline → escalation nếu không ack → khi PatientInformed, đánh giá resolution. Không kích hoạt nếu: đã cập nhật còn hiệu lực · bệnh nhân yêu cầu không làm phiền · clinical safety đang xử lý · presence không đủ tin cậy.

**Communication coverage** (*§8*) chỉ "che" khi: đúng bệnh nhân · đúng chủ đề · đúng vai · trong time window · nội dung đạt policy · evidence phù hợp. «Tin nhắn "Phòng khám đã nhận yêu cầu" không che phủ việc giải thích vì sao kết quả đang chậm.» Coverage record: subject · message category · communicated_at · **valid_until** · actor · channel · acknowledgement.

**Intervention contract** (*§10*): mỗi state ↔ một intervention ↔ một completion evidence (UnexplainedWaitRisk → «Giải thích lý do + ETA + bước tiếp theo» → PatientInformed đúng subject).

**Cấu hình theo phòng khám** (*§12*): waiting threshold theo node/khung giờ/loại encounter · refresh interval · ack window · số lần delay · suppression · escalation recipient · vai được confirm/dismiss · retention · consent.

### Code có mảnh nào

- Ngưỡng chờ theo phòng: `dispatch_threshold` (wait_minutes, max_waiting, mặc định 20'/8) ✅ — chính là «waiting threshold theo node».
- Cảnh báo `wait_too_long` trong `build_alerts` — tương đương *WaitingThresholdExceeded* nhưng **không có coverage**, không lifecycle, không owner.
- Coverage: `tuong_tac_cskh` có `loai` (chủ đề), `nhan_vien_staff_id` (vai), `xay_ra_luc` — thiếu `valid_until` và `appointment_id` không bắt buộc ở `TRA_KQ`.
- Severity tách clinical: `lab_result.triage_group` (GROUP_A/B/C) là trục clinical riêng ✅ — đúng §9 «Experience severity không được ghi đè clinical priority.»

Thiết kế: [[tk-experience-state|experience_state]].

## Nối tới
- [[gap-experience-state|Khoảng cách 5]]
- [[tk-experience-state|experience_state]]
- [[timer-expected-event|Thời gian và 'sự kiện không xảy ra']]
- [[work-item-commitment|Work Item là commitment]]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[dispatch|Điều phối Trưởng ca]]
- [[humane-ops|Design for Humane Operations]]

## Được dẫn từ
- [[3-muc-quyen-ai|Ba mức quyền hành động]]
- [[patient-journey-4-chang|Patient Journey]]
- [[work-item-commitment|Work Item là commitment]]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[gap-experience-state|Khoảng cách 5]]
- [[gap-communication|Khoảng cách 8]]
- [[tk-experience-state|experience_state]]
- [[phase-b-exceptions|Phase B]]
