# CHUẨN CẮM LEGO — một khối nghiệp vụ phải có gì

Chốt với Tuyền 23/09/2026. Gom từ thiết kế đã có (`docs/thiet-ke-he-thong/`:
`event-first-dao-nhan-qua`, `journey-process-manager`, `tk-projections`,
`tk-policy-engine`, `chung-minh-event-driven`; `docs/ai/lifecycle-v1/ClinicAI-DESIGN-BASELINE-v0.2.md`
§2.2 bảy luật DE-01…07) và đối chiếu với code đang chạy (`src/clinicai/events/`,
`src/clinicai/modules.py`). Không thay thiết kế — đây là **bảng kiểm** để mọi khối
cắm cùng một kiểu.

Hướng kiến trúc (thesis, không đổi): **event-driven architecture + selective event
sourcing**. Bảng hiện hành vẫn giữ trạng thái (state-first); event là sự thật đầy đủ
đi kèm, cùng giao dịch. KHÔNG event sourcing toàn hệ thống (Baseline §2.4). Chỉ dùng
Postgres (SO-LUAT Phần 7) — ở ~1 lượt gọi/giây, outbox trên Postgres là đủ.

## 1. Tám thứ mỗi khối phải có

| # | Thứ | Luật | Mẫu chuẩn | Ở đâu trong code | Ai kiểm |
|---|---|---|---|---|---|
| 1 | **Lệnh** (command) | Người/hệ thống yêu cầu một việc. Hỏi quyền + luật TRƯỚC, trong một giao dịch. Có khoá gửi lại. | Command (CQRS) · Idempotency key | `services/*_service.py`, khai `lenh` ở `modules.py` | CI `test_o_cam_module` (lệnh gọi đồng bộ phải có thật) |
| 2 | **State riêng** | Chỉ khối này ghi bảng của nó. Khối khác muốn đổi → gửi LỆNH hoặc phát event. | Aggregate / Bounded Context (DDD) | khai `bang` ở `modules.py` | CI: không hai module cùng giữ một bảng |
| 3 | **Event có version + payload** | Là SỰ THẬT đã xảy ra (DE-01), bất biến (DE-02), cùng giao dịch với state (DE-04, outbox), payload tối thiểu (DE-06), có `event_version` (DE-05). Một aggregate = một chuỗi `aggregate_version`. | Domain Event · Transactional Outbox · Event versioning | `events/catalogue.py` (payload pydantic), `emit_event` | CI: mỗi event đúng một module phát; nâng cấp phải có hàm (mục 2) |
| 4 | **Node nghe idempotent** | Nhận trùng/đến muộn không làm hai lần; việc + đánh dấu DONE chung một giao dịch; lỗi → RETRY → DEAD. Node KHÔNG gọi ngược khối phát. | Idempotent Consumer · Retry + Dead-letter · Per-aggregate ordering | `events/worker.py`, `events/consumers/*.py`, khai `nghe`/`ben_nhan` | CI: consumer thuộc module, khai nghe đủ |
| 5 | **Màn đọc** (projection) | Dựng từ event (hoặc view từ bảng). Không ghi tay. KHÔNG dùng để ra quyết định nghiệp vụ. Xoá đi dựng lại phải ra y hệt. | CQRS read model · Projection rebuild | `luot_dong_thoi_gian`, `v_*` | bài phát lại (mục 3) |
| 6 | **Quyền** | Lệnh hỏi capability (`doi_quyen`), không hỏi vai. Quyền thuộc đúng một module. | Capability-based authorization | `permissions/`, khai `quyen` | CI: quyền không mồ côi |
| 7 | **Không gọi thẳng khối khác** | Nói chuyện bằng event. Ngoại lệ DUY NHẤT: luật an toàn phải đồng bộ trong giao dịch (cổng tiền, quyền) — và phải khai `goi_dong_bo`. | Choreography · Anti-corruption | `modules.py` `goi_dong_bo` | CI: lệnh khai phải có thật |
| 8 | **Bài khách giả** | Mỗi bước in "Sự kiện MỚI → node X ĐÃ NHẬN". Bước chỉ ghi sổ cũ = chưa cắm. | Contract/acceptance test | `scripts/tests/khach-gia-luong-chuan.py` | người đọc + CI bài DB |

## 2. Nâng cấp event (quy trình)

Sổ event CHỈ THÊM (trigger chặn sửa/xoá). Event cũ không bao giờ được sửa lại — nên
đổi hình event phải đi bằng **nâng cấp khi đọc** (upcasting).

1. **Thêm trường tuỳ chọn** (có mặc định): KHÔNG tăng version. Node cũ bỏ qua trường lạ.
2. **Đổi tên / đổi nghĩa / bỏ trường / đổi kiểu**: TĂNG `version` trong `catalogue.py`
   và BẮT BUỘC viết hàm nâng cấp `vN → vN+1` ở `events/nang_cap.py`.
3. Người đưa tin nâng mọi event cũ lên version hiện hành TRƯỚC khi đưa cho node →
   node chỉ phải hiểu MỘT version (mới nhất).
4. CI đỏ nếu một event có version > 1 mà chuỗi hàm nâng cấp từ 1 bị hở, hoặc bản đã
   nâng không đọc được bằng payload hiện hành.
5. Đổi NGHĨA hẳn (sự thật khác) → đặt TÊN event mới, không tăng version.

## 3. Phát lại (replay)

- Chỉ **projection** được phát lại: xoá bảng đọc → cho lại mọi event (đã nâng cấp) qua
  node → phải ra y như trước. Đây là bài kiểm thesis "xoá dashboard dựng lại được không"
  (bằng chứng #3 trong `chung-minh-event-driven`).
- Node **tác vụ** (mở việc, gửi tin) KHÔNG được phát lại để làm lại việc. Khi thấy
  `la_phat_lai` thì không gửi gì ra ngoài.
- Phát lại không sinh event mới, không sinh dòng giao mới.

## 4. Màn đọc (học từ `tk-projections`)

- View đủ nhanh ở quy mô này → ưu tiên view. Bảng projection chỉ khi cần lịch sử
  (dòng thời gian) hoặc tính nặng.
- Mỗi projection ghi rõ nguồn (bảng hay sổ event) và cách dựng lại.
- Đối chứng: màn dựng từ bảng và màn dựng từ event phải khớp — lệch là sổ event thiếu.

## 5. Khối Hành trình (Journey Process Manager) — CẦN CÓ

Thesis §9: hành trình không phải một cột "bước hiện tại"; nó **so kế hoạch với thực
tế, giữ hẹn giờ, phát lệnh, xử lý ngoại lệ**. Không có nó thì luật thứ tự rải ở nhiều
khối (hôm nay: thu tiền, đặt lịch, lượt khám cùng chứa luật "đi đâu tiếp").

Hình dạng: tập **luật phản ứng** — `event kích hoạt → điều kiện → LỆNH của khối khác →
event kết quả`. Là một node nghe như mọi node (idempotent, DEAD khi hỏng). Chỉ gửi
LỆNH, không ghi bảng khối khác. Hẹn giờ dùng `hen_gio` (sự kiện không xảy ra).
Bước đầu viết luật bằng code (`events/consumers/hanh_trinh.py`); thiết kế đích là
luật-thành-dữ-liệu (`policy` + `policy_case`, `tk-policy-engine`) — cùng hình dạng
nên chuyển sau không phải viết lại.

## 6. Nói thật: cái gì vẫn phải sửa khi thêm tính năng

| Thay đổi | Đụng gì |
|---|---|
| Phản ứng mới cho sự thật đã có | CHỈ thêm node (file mới + 1 dòng khai) |
| Sự thật chưa ai phát | Sửa khối nguồn MỘT lần để phát |
| Event thiếu dữ liệu | Nâng version + hàm nâng cấp (mục 2) |
| Đổi luật thứ tự luồng | Sửa MỘT chỗ: khối Hành trình |
| Màn mới | Thêm projection + màn |
| Cắt ngang (quyền, nhiều phòng khám) | Vẫn đụng nhiều chỗ — event không cứu |

Giá phải trả: màn trễ ~1 giây (nhất quán sau); phải chạy người đưa tin trên VPS; lần
lỗi cần correlation id + khách giả.
