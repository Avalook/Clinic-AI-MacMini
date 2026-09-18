---
title: "State chỉ là projection — 8 projection cốt lõi"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §8"
tags: [clinicai, lop2-kien-truc]
---

# State chỉ là projection — 8 projection cốt lõi

> [!abstract] Snapshot không phải truth độc lập; nhiều projection nhưng chỉ một source of truth; view CSKH là ví dụ đúng đang có.

Ví dụ thesis (*§8*): một encounter đang hiển thị `encounter_state: awaiting_doctor_review · current_node: consultation_room_2 · patient_presence: onsite · wait_started_at: 10:18 · assigned_clinician: doctor_lan · experience_state: informed_wait · risk_flags: [result_review_sla_approaching]`

> «Nhưng snapshot này không phải truth độc lập. Nó được fold từ event: PatientArrived → EncounterStarted → ConsultationCompleted → LabOrderPlaced → SpecimenCollected → LabResultReady → DoctorReviewWorkCreated → PatientInformed. **Nếu projection bị lỗi, ClinicAI phải có thể xóa và dựng lại nó từ stream.**» — *§8*

Tám projection cốt lõi (*§8.1*): Encounter Board · Work Queue · Patient Journey · Experience Monitor · Resource Load · Patient View · Management Analytics · Audit View. «Nhiều projection có thể khác nhau nhưng không được có nhiều source of truth.»

### Chỗ code đã làm ĐÚNG nhất

`20260809000005_trang_thai_cskh_suy_ra.sql` mở đầu bằng đúng triết lý này, bằng tiếng Việt:

> «Trạng thái khách hàng là một **HÀM CỦA DỮ LIỆU**, không phải một cột ai đó bấm. […] Một bảng việc mà không có cron thì việc chỉ ra đời khi có người mở màn — và từ giây đó nó là BẢN SAO của sự thật, tự do lệch […] View thì không lệch được: xoá một cuộc gọi thì trạng thái tự lùi về đúng chỗ.»

`v_viec_cskh` = 11 nhánh `UNION ALL`, mỗi nhánh một câu hỏi nghiệp vụ, đọc `luat_cskh`; `v_trang_thai_cskh` chọn việc gấp nhất mỗi khách («QUÁ HẠN TRƯỚC, rồi mới tới ưu tiên»). Đây **là** Work Queue projection + một phần Experience Monitor — chỉ khác nguồn: nó fold từ *bảng trạng thái* (`appointment`, `lab_result`, `tuong_tac_cskh`), không từ event stream.

Cũng đúng: `visit.current_node_code` được **trigger** `update_visit_current_node()` nuôi từ `work_item` (migration `20260803000003`) — projection có người canh, không ai ghi tay. Và `dispatch_service.alerts()`: «Tính từ chính hai truy vấn trên chứ không từ một bảng cảnh báo riêng: một bảng cảnh báo là một bản sao của sự thật, và nó sẽ cũ đúng vào lúc Trưởng ca cần tin nó nhất.»

### Chỗ chưa đúng

`appointment.status`, `visit.status`, `work_item.status` là **cột được UPDATE**, event là hệ quả. Anti-pattern §20.8 «Direct write vào projection» — theo nghĩa thesis, chính các cột status là projection bị ghi thẳng. [[tk-projections|Projection có kỷ luật]] không đổi điều đó ngay (quá đắt, và ADR-0003 cần cột để đặt CHECK/CAS); nó đòi **bất biến 1** (§22): «Mọi operational state quan trọng phải truy được về event» — tức mỗi lần UPDATE status phải có đúng một dòng event_log cùng transaction, kiểm bằng SQL test đếm cặp.

## Nối tới
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[dispatch|Điều phối Trưởng ca]]
- [[tk-projections|Projection có kỷ luật]]
- [[gap-projection-rebuild|Khoảng cách 6]]
- [[15-invariant|15 bất biến cấp 'hiến pháp']]

## Được dẫn từ
- [[anti-patterns|10 anti-pattern cần cấm]]
- [[dispatch|Điều phối Trưởng ca]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[gap-projection-rebuild|Khoảng cách 6]]
- [[tk-projections|Projection có kỷ luật]]
