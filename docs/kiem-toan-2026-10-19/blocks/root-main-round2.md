# Main vòng 2 — checkpoint gốc, kết quả đã kiểm

Nguồn: `956ba4f236b1c92f1280d2097018c199e90ce8c7`, detached worktree tại
`/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini`.
Không đổi application source; các file `test_audit_1910_*` chỉ là probe chưa commit.

Các agent đã chạy lại được một đoạn rồi đều dừng vì quota. Những file checkpoint
của agent còn ghi `running`/coverage rỗng là trạng thái cũ, KHÔNG chứng minh đã đọc.
Root nhận nghi vấn từ mailbox, tự đọc lại nguồn, viết/hoàn thiện probe và kiểm chứng.

## Đã tích hợp

| ID | Bằng chứng mới | Giới hạn |
|---|---|---|
| AI-001 | Detector thật + reconciler thật + Postgres: 201 việc quá hạn, 1 nhận định bị đóng HET | Scope fixture, giữ predicate/LIMIT; hiện chỉ shadow |
| FIN-004 | HoanTienService + trigger thật: hai lần hoàn 0.5 tổng 100002 > thu 100001 | Thu synthetic, inventory gate tắt, chưa HTTP/UI |
| CLIN-005 | Hai service call với barrier: check-in commit rồi reschedule trả CONFIRMED, visit còn mở | Bỏ riêng guard giờ mở cửa để không phụ thuộc giờ chạy |
| SEC-002 | Soft-revoke mọi grant: effective rights=0, can=False nhưng file auth=True | Chưa tải tệp qua HTTP; membership vẫn active, cùng clinic |
| FE-005 | React component và autosave hook thật trên Chrome headless: 409 thay mất local draft | HTTP synthetic, không full application |
| DB-002 | Full main schema, role authenticated + synthetic nurse JWT: trước deny, sau restore grants + 2 ACL migrations đọc được draft/settings | Mô phỏng bước ACL, không full pg_dump/restore, chưa PostgREST |

32 test hiện hữu liên quan agent/refund/privacy/check-in đều xanh trên main. Điều này
giúp loại giả thuyết mọi ca đỏ chỉ do schema lệch; không chứng minh toàn hệ thống đúng.
Các RED probe giữ nguyên assert bất biến mong muốn, không sửa application để làm xanh.

## Đã đọc, có cơ chế đáng giữ

- `permissions/can.py`: query scope clinic/staff; room check bỏ cache, positive cache
  toàn clinic 5 giây; không cache deny; quyền không khai gây lỗi rõ.
- `permissions/cache.py`: đổi quyền gọi quên cache danh tính; TTL cho process khác.
  Không đánh giá TTL có chủ ý là lỗ hổng vô điều kiện.
- `permissions/ca_truc.py`, `lich.py`: có cấu hình cửa ca, ngoại lệ, nguồn quyền từ
  lịch; các bypass legacy/lượt cũ có chủ đích. Cần kiểm policy của clinic thứ hai,
  không coi “khác chuẩn kỳ vọng của auditor” tự động là bug.
- `permissions/y_khoa.py`: quyền in mở quyền đọc phiếu cho các khâu quầy; audit
  mở hồ sơ chỉ ghi cho vai ngoài chuyên môn và lỗi ghi audit không chặn đọc.
  Đây là chính sách hiện hành cần cấu hình khi bán, chưa kết luận vi phạm pháp lý.
- `agent_tom_tat.py`: input theo clinic, chỉ số đếm/nhận định rule, loại free-text
  đánh giá khỏi prompt, kill switch; chỉ đề xuất, không có tool sửa dữ liệu nghiệp vụ.
  Giữ kiến trúc này. Cần gắn snapshot/hash/version đầu vào cho replay/evaluation;
  `lan_goi_id` hiện chỉ tham chiếu token/cost log, không tái dựng được toàn input cũ.
- `orchestrator` route: cờ opt-in, quyền ops.view, rate limit; thread namespace gồm
  clinic/staff. Không báo endpoint agent công khai mặc định.
- `AnthropicClient`, `chi_phi`: có retry/log token/trần từ tổng chi phí đã ghi.
  Trần hiện không phải reservation ngân sách đồng thời; model chưa có giá trả None.
  Chưa thử overspend, không dùng claim “hard budget” khi đóng gói nhiều khách.
- `api/idempotency.py`: scope actor/endpoint, payload hash, khóa PROCESSING và TTL.
  Receipt save qua pool riêng sau domain service commit; cần kiểm crash window và
  từng safeguard domain trước khi tuyên bố ghi trùng. Booking có UNIQUE patient/slot
  nên không được kết luận retry booking luôn tạo 2 lịch.
- `core/change_broker.py`, events router: NOTIFY là invalidation signal, queue 8,
  không chứa PHI, scope clinic, tự reconnect backend; cần đọc client fallback để
  đánh giá stale. SSE sống không chứng minh LISTEN backend còn sống.

## Nghi vấn còn mở, chưa tích hợp thành phát hiện xác nhận

1. In kết quả: `InKetQua.tsx` fetch một lần theo orderId, nút print dùng snapshot
   đang giữ; route nằm ngoài dashboard refresher. Có nhãn BẢN NHÁP (safeguard).
   Cần kiểm chính sách print “as-of” và correction version, tránh nhầm snapshot
   hợp lệ với yêu cầu tự cập nhật. Nên ghi revision/as_of lên bản in và kiểm trước in.
2. SSE client: agent nêu khác biệt native reconnect với hard-close retry; chưa
   xác nhận window stale, tuổi dữ liệu và poll. Đọc `lib` subscriber trước kết luận.
3. Generic idempotency: cần inject chết sau domain commit/trước receipt, hết lease,
   xác minh từng endpoint (CSKH, stock, booking, payment) có natural key/invariant gì.
4. Các module inventory/consumers mới trên main chưa được agent vòng2 hoàn tất.
   Không tăng ledger từ coverage rỗng hoặc dùng lời “đã kiểm toàn kho”.

## Hygiene và tiếp tục

Initial ACL probe thiếu auth.users fixture bị FK chặn; đã thêm user synthetic rồi
phép thử mới chạy đến actual role queries. Initial revoke probe dùng tên quyền
`clinical.read` không tồn tại; đã sửa sang `clinical.consult.perform` rồi mới
kết luận. Các lỗi harness không được tính là lỗi sản phẩm.

Tất cả test chạy bằng `scripts/test-nhanh.sh` nhân DB tạm từ khuôn; không reset khuôn,
không restart stack chung, không production. Main thiếu 42 migration trong khuôn
đã được wrapper áp vào từng DB tạm. Seed mismatch warning vẫn công khai.

## Bổ sung sau checkpoint đầu vòng2

INF007 đã RED route function+service+DB: lỗi save receipt sau commit rồi hếtlease/retry →2 dòng CSKH. Kho vật tư có natural key trong cùng domain transaction nên không được suy mọi route đều trùng. CLIN006 đã RED consumer+DB:ẩncorrectionv2 rồiv3 cùng result ID vẫn không thấy chuông. SEC003 receiver thật, free-space mô hình1024/reserve256, ghi2057byte và chỉcheck1lần; không làm đầy ổ.

Đọc thêm emit/replay/trach_nhiem/vong_doc/chuong/nhac_tai_kham, proxy identity, file streaming/MIME/path/circuit breaker và vật tư nhập/duyệt/đảo. Có transaction outbox, replay guard, capability/clinic scope, natural key, lock location và đơn vị snapshot đáng giữ. Không khẳng định đã đọc hết pharmacy/stock. Các test hiện hữu mới14+47pass. Metadata prod chỉ đọc theoPROD-CHECK.json đã xác minh; không biến probe local thành sự cố thực tế.

## Round3 mới nhất — các bổ sung sau broad pytest

CLIN-007 service+HTTP ASGI201 nhận lôB cho RxA ở no-allocation, actual guards/receipt; reviewer clinical độc lập xác nhận HIGH/P1, thiếu drug_catalog_id match, không intentional substitution. DB-004 function bootstrap thật:2clinic1item→92each, itemgốcfalse; rollback. 62 existing pharmacy controls passed. SEC-004 npm audit31packages, runtime versions checked; Alpine3.24.2/glibcnull khôngkhớp điều kiện glibc của sharp RCE, giữ MEDIUM quảnlýdependency, khôngclaimexploit. Override next.sharp cầnrá. Các agent round3 DB/security/infra/finance vẫn quota-error sau nhậnnhiệm vụ, khôngcoi phầnđó hoànthành.


## Root tiếp tục đọc tiền hoàn — 19/10/2026

Đã đọc trọn `src/clinicai/services/hoan_tien_service.py` (628 dòng) và hai endpoint tạo/xác nhận/đóng khoản hoàn trong router, cùng guard refund-line ở migration gốc và migration giảm giá. Không thêm finding mới: FIN-004 đã bao quát cả nhánh không giảm (cho phép mỗi phần làm tròn độc lập) và nhánh giảm (có cap lũy kế); test đã tái hiện phần không giảm 0.5×100001đ hai lần thành 100002đ trên khoản thu100001đ. Các guard vẫn khóa payment_cycle và cap quantity, nhưng chỉ nhánh giảm cap amount lũy kế. Đã đối chiếu transaction, lock order, PENDING/COMPLETED/FAILED/CANCELLED, tính quyền theo loại và event cùng transaction. Còn phải đọc rộng PaymentService/quầy thu, các caller UI, các migration lịch sử và đường đối soát; không nâng finance block thành hoàn tất.

## 2026-10-19 — finance round 4

Đọc sâu `PaymentService` selected lifecycle paths, API payment/refund routes, `BillService` selected billing paths, `QuayThuService.lich_su`, cashier scope/date helpers, cashier history/export endpoints và `LichSuThu`. FIN-004 vẫn là finding rounding đã tái hiện; không tạo bản ghi trùng. FIN-005 mới là confirmed-static: hai truy vấn thu/hoàn LIMIT 3000, chỉ warning nội bộ, output/UI/export không nêu cắt; manager có thể truy vấn 92 ngày. Chưa chứng minh đã chạm trần trên dữ liệu clinic. Coverage đánh dấu selected paths, không khẳng định đã đọc trọn các file ngoài `HoanTienService`.
