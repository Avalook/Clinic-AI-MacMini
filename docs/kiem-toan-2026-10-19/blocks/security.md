# Security / API boundaries

Trạng thái: running. Security source coverage: 175 paths; SQL migration paths được theo dõi trong MAIN-PHAM-VI.json. Chưa kiểm runtime.

## Bước kế tiếp
Đọc cấu trúc auth, tenant, router, SSE, file export và lớp tool/LLM.

## Root checkpoint 2026-10-19T17:46:43.192198+07:00

Khối chưa hoàn tất. Nội dung agent ban đầu là baseline543b9787+WIP; ưu tiên PHAT-HIEN.json/main_validation cho kết luận mới.
- SEC-001: still_present_on_main — Root đối chiếu vùng code liên quan trên bản main ghim; kết luận giữ ở đúng mức bằng chứng, chưa kiểm production.
Tiếp theo: TIEP-TUC.md và MAIN-PHAM-VI.json. Không tự nâng scan thành đọc sâu.


## SEC-007 — phạm vi tenant của helper sức chứa RPC, 19/10/2026

- Migration ACL cuối grant authenticated trên `clinic_hours_for_date`, `resolve_effective_cap`, `resolve_effective_caps`; các function SECURITY DEFINER nhận clinic/doctor UUID do caller truyền và truy vấn settings/override theo tham số, không gọi current_clinic membership guard. Caddy public routes `/rest/v1/*` tới PostgREST.
- Scope hiện xác nhận chỉ là metadata vận hành: giờ mở cửa, slot duration và capacity rules/overrides. Chưa có bằng chứng lộ lịch hẹn/PHI, quyền ghi, token exploit hoặc production ACL. Không gộp với DB-001 (RPC nội bộ ghi liệu trình) vì grants và gốc lỗi khác.
- SEC-007 MEDIUM/confirmed_static. Cần hai-clinic PostgREST test. Lát rà allowlist ACL cuối đã kiểm thêm các helper grant cho authenticated và test draft hiện hữu; không phát hiện vấn đề thứ hai đủ căn cứ. Các caller/file/SSE boundary khác vẫn chưa audit xong.

## RUN-030 — rà allowlist RPC và helper, 19/10/2026

- Đọc full ACL migration cuối (75 dòng), full `read_prescription_draft`, `thu_ky_duoc_xem_khach`, `la_ca_kham_bac_si` và test quyền draft; đọc chọn vùng identity/clinical-role migrations. Main coverage đã đánh dấu các file được truy vết; chỉ một vài file ngắn được đọc toàn bộ.
- Helper identity truy vấn `auth.uid()`/staff active/membership active; draft reader giới hạn clinic và role; helper thư ký dùng clinic/patient argument nhưng restrictive RLS ghép AND với policy permissive hiện hữu. Đây là đánh giá source tĩnh, chưa chạy dưới JWT và không chứng minh toàn bộ policy an toàn runtime.
- Test hiện hữu `test_prescription_draft_privacy_db.py` xác nhận không đọc trực tiếp cột nháp, RPC được grant authenticated và bị từ chối anon; chưa kiểm role/tenant của kết quả trả về.
- Không thêm finding mới. Next: chạy ma trận hai clinic qua PostgREST; sau đó tiếp tục SSE, media/file và chuỗi restore/migration.

## SEC-008 — trần proxy Next và service ảnh siêu âm không khớp, 19/10/2026

- `proxy.ts` áp Next proxy cho `/api/ultrasound/image` (không nằm trong hai upload route được bỏ qua); comment ghi body buffer 10 MiB. `next.config.ts` không override `proxyClientMaxBodySize`; tài liệu Next xác nhận default 10 MiB và phần vượt trần chỉ được buffer một phần. Service siêu âm lại cho phép 12 MiB; multipart overhead làm ngưỡng file thực thấp hơn.
- MEDIUM/confirmed_static: near-limit multipart có thể không tới route nguyên vẹn. Chưa chạy Next runtime quanh ngưỡng; chưa thấy caller dashboard trong source search; không khẳng định có người dùng bị ảnh hưởng. Đây là sửa scope từ giả thuyết body không giới hạn sau khi đối chiếu proxy matcher/framework docs.
- Next docs: https://nextjs.org/docs/app/api-reference/config/next-config-js/proxyClientMaxBodySize. Next step: test 9.5/10/11/12 MiB và chunked qua disposable runtime, xác minh status/bytes, rồi chốt cap end-to-end.


## SEC-009 — ảnh feedback được ghi trước bước xác thực backend

- `proxy.ts` để API route tự phân quyền; route feedback ghi ảnh ≤8 MiB vào DIR trước khi gọi `proxyJsonToBackend`, nơi session không có thì trả 401. Route không dọn file trên lỗi. Caddy route ứng dụng công khai tới dashboard.
- Chỉ thành sink ghi đĩa chưa xác thực nếu `FEEDBACK_DIR` writable. Default `/app/../../.feedback` resolve thành `/.feedback`; runner là `USER node`, nên mặc định production có vẻ không ghi được. `.env.prod.example` không khai biến này, nhưng actual `.env.prod`/VPS chưa đọc. Vì vậy SEC-009 là MEDIUM/design_gap có điều kiện; chưa khẳng định khai thác production.
- RUN-033 là static/path trace; chưa gửi request hay dựng container. Acceptance: anonymous request tạo 0 file; authenticated flow commit DB+file; backend error không để orphan; quota/retention/rate limit được kiểm trong disposable runtime.


## v0.18 — bổ sung trace

SEC-011 HIGH/confirmed-static: TKYK preset có clinical capability; clinical-forms read/history, print theo appointment và mixed patient+appointment branch thiếu patient assignment binding. Same-clinic only; cần UUID; chưa HTTP/DB reproduction. Canonical finding/evidence trong PHAT-HIEN.json.


## v0.19 — SEC-012 / thu hồi kỹ năng

SEC-012 HIGH/reproduced_local: skill assignment bị xóa ở transaction đầu; các lego thu hồi sau đó bằng nhiều transaction. Inject lỗi giữa revoke, retry trả `already` nhưng một capability vẫn active. RUN-036 dùng synthetic DB và lỗi được tiêm; không phải tần suất production. Canonical detail/hash/acceptance ở `PHAT-HIEN.json`; tiếp tục matrix quyền thực tế và các đường untraced.

## v0.21 — mở rộng SEC-011, thêm design gap FE-009

- **SEC-011 giữ nguyên một ID/root cause:** ngoài clinical form/history/print, exact-main static trace tìm thấy `read_prescription_draft(uuid)` SECURITY DEFINER được cấp cho authenticated chỉ có clinic+role guard, không có TKYK patient-assignment check; RLS table helper có assignment guard nhưng không áp vào RPC này. Các API đọc liệu trình theo patient/visit cũng chỉ kiểm capability `QUYEN_DOC`. Các đường mới chưa chạy JWT/PostgREST/DB runtime.
- **FE-009 MEDIUM/design_gap:** schema/backend cho phép membership nhiều clinic và X-Clinic-ID selector, nhưng dashboard login từ chối user có hơn một clinic active. Location picker chọn cơ sở trong tenant, không phải tenant. Đây là giới hạn sản phẩm multi-clinic, không phải cross-tenant leak; exact-main static trace, chưa browser login test.
- Mặt auth song song `app_credential`/GoTrue được xem là debt cần hợp nhất, không nâng thành security finding: route custom login không được dashboard gọi, API có API-key gate và Caddy chỉ expose Next trong public paths theo lát đã rà.

## v0.22 — mở rộng object-scope cho tệp và ảnh

- Mở rộng SEC-011: một số list/content file-result path chỉ scope clinic+capability; direct ultrasound image đọc key đã nằm trong image_refs của record cùng clinic nhưng không kiểm assignment của caller.
- Không có bằng chứng cross-clinic; với ảnh, key phải được biết/đưa ra trước đó. Static-only, chưa JWT/HTTP synthetic identities; xác minh role policy trước khi kết luận mọi caller đều bị giới hạn assignment.

## v0.23 — write scope và view quyền

SEC-016: thai-ky POST/PATCH thiếu kiem_khach dù doc() có; preset TKYK có quyền ghi. SEC-017: hai view quyền cấp SELECT authenticated, thiếu tenant filter/security_invoker; rủi ro phụ thuộc owner/ACL runtime. Chưa HTTP/DB/PostgREST. Không mở rộng SEC-011 sang bảng hành trình chung vì policy còn cần chốt.

## v0.24 — xác minh view quyền trên CI DB

SEC-017: authenticated EXPLAIN v_quyen_hieu_luc bỏ predicate RLS trong plan nhưng base table có predicate. v_quyen_thuc_te hiện lỗi thiếu EXECUTE hai helper; chỉ cấp EXECUTE có thể mở dữ liệu unscoped. Local ci_may_test PG17.11, catalog/EXPLAIN read-only, không SELECT rows/production. SEC-011 được bổ sung exact mismatch appointment/patient evidence, chưa có regression test.

## Round 36
Không phát hiện bypass phân quyền mới trong lát settings. Giữ PERMISSION-PRESET-INACTIVE-FALLBACK-001 ở dạng held: active=false và fallback PRESET chưa có product contract rõ; đây không phải đường bypass cho người không có quyền quản lý. Chi tiết ở blocks/round36.coverage.json.

## Round 38 — SEC-027 service-history

Mở rộng SEC-027: GET `/appointments/lich-su-dich-vu` dùng `get_current_identity` thay vì `_DOC_LICH_GUARD`; service trả số lần đặt cùng status/opened_at/last_visit_at của episode, query vẫn scope clinic/patient/service. Static same-clinic least-privilege concern; chưa có test JWT/runtime hay bằng chứng đọc chéo clinic. Xem `blocks/round38.md` và `blocks/round38.coverage.json`.

## Round 39

SEC-025 mở rộng: đổi mật khẩu gọi endpoint ghi audit nhưng client không kiểm HTTP status; endpoint backend ghi event trong transaction và test chỉ xác nhận success path. Giữ điều kiện về audit contract; chưa fault-inject hoặc kiểm Auth/runtime. Lát service-order chưa đủ cơ sở để kết luận thiếu assignment authorization do chưa chốt capability scope; giữ policy question trong `blocks/round39.md`.
