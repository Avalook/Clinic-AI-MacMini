---
title: "Nguyên tắc thiết kế đích — 8 điều chốt trước khi vẽ bảng"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "tổng hợp thesis §23 × SO-LUAT × ADR"
tags: [clinicai, lop5-thiet-ke]
---

# Nguyên tắc thiết kế đích — 8 điều chốt trước khi vẽ bảng

> [!abstract] Không hạ tầng mới; mọi thứ là dữ liệu; một cửa ghi; migration cộng thêm; DB trước code; CI canh mọi bất biến; một tiến trình nền; rule trước AI.

1. **Không hạ tầng mới.** Luật 7.1/7.2 + ADR-0005 + Care Model §23 đồng ý: «Điều cần bảo vệ từ ngày đầu không phải scale hạ tầng mà là event semantics; correlation/causation; ordering boundary; immutable history; projection discipline; completion/outcome semantics.» Mọi mảnh dưới đây là bảng Postgres + hàm SQL + một vòng lặp trong `worker.py` đã có.
2. **Mọi thứ là dữ liệu** (ADR-0011, `kien-truc-nhieu-phong-kham.md`): catalog event, policy, SLA, ngưỡng, intervention — đều là dòng có `clinic_id`. Phòng khám thứ hai khai, không đợi deploy.
3. **Một cửa ghi sự kiện.** 29 → 1. Hàm SQL `ghi_su_kien()` điền envelope, cấp `stream_version`, kiểm catalog. Python chỉ gọi.
4. **Migration cộng thêm, không đổi tên.** Không đổi `event_type` đang chạy (view/relay/test đọc chúng); thêm cột, thêm bảng, thêm trigger. Tên canonical thesis nằm ở cột `canonical` của catalog.
5. **DB trước code, code sau DB** (DANG-LAM cạm bẫy). Mỗi phase = 1 migration idempotent (áp hai lần trong CI) → 1–3 PR code → 1 SQL test khẳng định.
6. **Luật không có người canh không phải luật** (SO-LUAT §3). Mỗi bất biến thesis được đưa vào [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']] thành một test có "thử ngược".
7. **Một tiến trình nền** làm ba việc: relay (có sẵn) + đồng hồ expectation + policy engine. Cùng LISTEN, cùng poll 30s, cùng heartbeat. Tách tiến trình chỉ khi có phép đo (Luật 7.2).
8. **Rule trước, AI sau** (Spec §13, v2 §3.10 «Nếu thất bại tập trung ở AI nhưng coordination loop vẫn tạo giá trị, nên bỏ bớt AI»). Mọi derived state đầu tiên là rule SQL/Python thuần, test bằng bảng tình huống như `gate_rule_service`.

Điều **không** làm, và vì sao:
- Không full event sourcing (§20.6). Bảng trạng thái giữ nguyên để CHECK/CAS/trigger (ADR-0003) tiếp tục làm việc.
- Không message broker (ADR-0002). `pg_notify` + poll đủ ở 1 RPS; relay đã chứng minh.
- Không đổi tên event sang PascalCase tiếng Anh ngay. Đổi tên là đổi hợp đồng với `audit_labels`, template, view, test — rủi ro không mua được gì; catalog ánh xạ là đủ.
- Không viết lại `booking_service`. Nó là state machine + events đúng mô hình §7; chỉ đổi cửa ghi.
- Không projector worker. View đủ; DB cùng máy <1 ms/query.

## Nối tới
- [[kien-truc-toi-thieu|Kiến trúc logic tối thiểu]]
- [[adr-so-luat|13 ADR + Sổ luật]]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-event-catalog-table|event_catalog]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
- [[tk-modular-monolith|Thi hành ADR-0001]]
- [[stack|Stack đang chạy]]

## Được dẫn từ
- [[event-first-dao-nhan-qua|Event-first]]
- [[kien-truc-toi-thieu|Kiến trúc logic tối thiểu]]
- [[tk-expectation-timer|expectation + đồng hồ]]
