---
title: "Thi hành ADR-0001 — thư mục theo 6 lớp thesis: engine/ (su_kien, viec, dong_ho, luat, chieu) · modules/ · ledgers/ · platform/"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "ADR-0001 · Luật 4.4 · import-linter"
tags: [clinicai, lop5-thiet-ke]
---

# Thi hành ADR-0001 — thư mục theo 6 lớp thesis: engine/ (su_kien, viec, dong_ho, luat, chieu) · modules/ · ledgers/ · platform/

> [!abstract] Ranh giới nằm trong code: engine không biết nghiệp vụ, module không ghi chéo, manifest 7 mục máy đọc được; dời dần, mỗi cụm một PR.

```
src/clinicai/
  engine/                 # Lớp 2–3 thesis: không biết 'khám', 'siêu âm'
    su_kien.py            # ghi(), catalog, timeline          ← tk-emit-function
    viec.py               # Work Item state machine (dời từ services/work_item_service.py)
    dong_ho.py            # expectation loop                    ← tk-expectation-timer
    luat.py               # policy evaluator (hàm thuần) + runner
    trai_nghiem.py        # experience_state lifecycle
    chieu.py              # projection helpers, checkpoint, drift
    tin_nhan.py           # notification_delivery relay (dời notification_relay.py)
  modules/                # Lớp nghiệp vụ, mỗi module một manifest.py
    dat_lich/   (booking_service, booking_override_service, slot_hold_service, luat_bac_si_service, config_service phần roster)
    tiep_nhan/  (check-in, visit_progress, dispatch_service, gate_rule_service, route_derivation)
    kham/       (clinical_record, clinical_form, clinical_sign, ultrasound, service_order)
    ket_qua/    (lab_order, lab_safety, tep_ket_qua, graphs/lab_triage)
    thu_ngan/   (payment, checkout, cashier_board, pos_*)
    nha_thuoc/  (pharmacy)
    cskh/       (tuong_tac_cskh, cskh_service, recall_*, phan_hoi_khach, thong_bao, man_khach_hang)
  ledgers/    (patient_service, mpi_service, staff_service, clinic_settings_service, clinic_config_service)
  platform/   (identity, idempotency, change_broker, ops_status, telegram/zalo providers, llm, voice)
```

**Manifest 7 mục** (ADR-0001) mỗi module: `owns_tables` (writer duy nhất — Luật 4.4) · `api` · `nodes` (node_code module đăng ký) · `form_schema` · `events` (emit/listen — **đọc từ `event_catalog.producer`**) · `provides/consumes` · `permissions`. CI: `import-linter` chặn `modules/a` import `modules/b` (chỉ qua `engine`/`ledgers`); checker «mỗi bảng đúng một `owns_tables`» đọc manifest + grep `INSERT/UPDATE` → ceiling như tenant-audit.

**Vì sao làm bây giờ chứ không sau**: các mảnh mới (su_kien, dong_ho, luat, trai_nghiem) **chưa có chỗ** trong `services/` phẳng; đặt chúng vào `engine/` từ đầu là thi hành ADR-0001 với chi phí gần 0, và cho 69 file cũ một đích để dời dần (mỗi cụm một PR, đúng nhánh ≤ 2 ngày).

**worker.py** thành `engine/nen.py`: một tiến trình, ba vòng (`tin_nhan`, `dong_ho`, `luat`) chia sẻ pool + LISTEN + heartbeat; `--pos-relay` giữ profile riêng. RabbitMQ mode + `event_bus/` **xoá** (ADR-0002 phần chưa làm; `RabbitMQPublisher.publish()` vẫn `raise NotImplementedError`).

Đây cũng là bản đồ sản phẩm 6 lớp (v1 §8) nhìn thấy được trong `ls`: engine = Operational State + Coordination + Intelligence; modules = Sensing + Human Interfaces theo nghiệp vụ; platform = Governance.

## Nối tới
- [[adr-so-luat|13 ADR + Sổ luật]]
- [[kien-truc-toi-thieu|Kiến trúc logic tối thiểu]]
- [[6-lop-san-pham|Product map 6 lớp]]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[tk-policy-engine|policy + policy_case]]
- [[tk-communication-delivery|notification_delivery]]
- [[ci-guards|CI]]
- [[stack|Stack đang chạy]]

## Được dẫn từ
- [[6-lop-san-pham|Product map 6 lớp]]
- [[kien-truc-toi-thieu|Kiến trúc logic tối thiểu]]
- [[adr-so-luat|13 ADR + Sổ luật]]
- [[tk-nguyen-tac|Nguyên tắc thiết kế đích]]
- [[phase-c-intelligence|Phase C]]
