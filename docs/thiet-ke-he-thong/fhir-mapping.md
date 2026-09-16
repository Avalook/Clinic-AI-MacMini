---
title: "Quan hệ với chuẩn y tế — FHIR là boundary, không phải ontology nội bộ"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §27"
tags: [clinicai, lop2-kien-truc]
---

# Quan hệ với chuẩn y tế — FHIR là boundary, không phải ontology nội bộ

> [!abstract] Map ở integration boundary; không ép mọi event thành FHIR resource; tránh semantic drift Task ↔ Work Item.

> «ClinicAI không nên dùng FHIR như internal ontology duy nhất. FHIR là boundary quan trọng để liên thông, còn event model nội bộ được tối ưu cho orchestration.» — *§27*

Mapping dự kiến: Patient/subject ↔ FHIR Patient · appointment intent ↔ Appointment · care contact ↔ **Encounter** · longitudinal grouping ↔ EpisodeOfCare · executable work ↔ **Task** · service capability ↔ HealthcareService.

Nguyên tắc: map ở integration boundary · không ép mọi operational event thành resource update · giữ correlation giữa event và external resource/version · tránh semantic drift giữa FHIR Task và Work Item nội bộ · version adapter độc lập với domain event contract.

### Nghĩa cho ClinicAI Việt Nam

Bối cảnh pháp lý đã tra trong phiên IoT 04/09: Thông tư 26/2025/TT-BYT và Quyết định 808/QĐ-BYT (Phụ lục II–VII = đặc tả kết nối HIS) — đây là boundary mà lúc nào đó ClinicAI phải map ra, đúng như §27 nói. Tổng-Quan §14.7: TT13/2025 bắt EMR trước 31/12/2026, cần ký số + CCCD.

Bảng nội bộ đã ở dạng dễ map: `patient`→Patient, `appointment`→Appointment, `visit`→Encounter, `care_episode`→EpisodeOfCare, `work_item`→Task, `service_type`→HealthcareService, `clinic_location`/`clinic_room`→Location. Thiết kế **không** thêm gì ở phase này ngoài một ghi chú trong [[tk-event-catalog-table|event_catalog]]: cột `fhir_hint` tuỳ chọn cho event liên quan (ResultReady → DiagnosticReport), để adapter sau này không phải đoán.

## Nối tới
- [[ontology-9|Ontology]]
- [[tk-event-catalog-table|event_catalog]]
- [[tk-sensing|Sensing]]

## Được dẫn từ
- [[ontology-9|Ontology]]
- [[tk-event-catalog-table|event_catalog]]
- [[tk-sensing|Sensing]]
