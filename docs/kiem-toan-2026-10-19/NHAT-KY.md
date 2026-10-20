## Round 42 — 20/10/2026, v0.65

SEC-010 được mở rộng sau independent security review: `/links` cùng consent router trả relation/name/code/form_codes nhưng route chỉ dùng identity guard, trong khi migration đặt RLS consent theo vai lâm sàng. Không tạo SEC-036 vì trùng cùng permission boundary; điều kiện DB credentials/UUID/caller chưa xác minh. Company invoice FK dedupe với DB-007; timeline projection không thêm distinct scope so với internal journey API; ThaiKy/clinical forms control slice không có candidate mới. Full router reads: thai_ky và clinical_forms; tests chỉ đọc. Không chạy app/API/DB/runtime/provider/production; không đọc secrets/PHI. Risk register 195; full source audit còn mở. Xem `blocks/round42.coverage.json`.

## Round 29 — 20/10/2026, v0.52

- Thêm FIN-017: hồ sơ khách có thể bỏ qua khoản nợ thuộc lượt cũ hơn cửa sổ năm lượt; điều kiện nhiều lượt+nợ cũ chưa được xác minh bằng dữ liệu thật.
- Thêm OPS-009: overview dispatch cắt ở 400 lượt và tổng KPI lấy từ tập đã cắt; volume kích hoạt chưa đo.
- Mở rộng FIN-004/INF-007 sang đường prepay liệu trình, FE-002 sang freshness từng panel giám sát và FE-004 sang lỗi đọc tom-tat đầu tiên.
- Đọc/trace thêm 34 đường dẫn theo blocks/round29.coverage.json; không chạy tests/app/API/DB/provider/VPS/production. Checkpoint chỉ là static exact-main. Full source audit còn mở.

## Checkpoint v0.47 — 20/10/2026, Round 24

- Exact-main `956ba4f236b1c92f1280d2097018c199e90ce8c7`; risk register 165 (26 HIGH/123 MEDIUM/16 LOW), main 161 present / 2 partial / 2 addressed; path coverage 776 read, 394 traced, 1187 scanned, 525 inventoried, 8 excluded.
- Round 24 static slices: five findings added (SEC-031/032, FE-023/024, API-005), FE-002 expanded. Forty files were read fully; targeted evidence and hashes are in `blocks/round24.coverage.json`.
- Policy/timing items remain observations; see `STATE.json` and `blocks/round24.md`. No ClinicAI test/runtime/API/DB/provider/production, secrets or PHI were used; tests were read, not run. Full source audit remains incomplete.
- RUN-085/086: HTML v0.47 passed 6/6 structural/evidence and desktop/mobile browser QA; 165 cards, 2,890 ledger rows, no overflow/page errors/external requests. Final HTML SHA-256 `26cb0522827a803cbdf4e0759700fbd26fcd31958b7a146145392a44a588af10`. RUN-087: initial ZIP 279 files passed member-set/CRC/bytes/per-file SHA; final rebuilt ZIP also passes member-set/CRC/bytes/per-file SHA; outer SHA is in `MANIFEST-GOI.json`. Artifact QA does not validate ClinicAI.

## Checkpoint v0.46 — 20/10/2026, tiếp tục qua tài khoản khác được

- Exact-main SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`; risk register 160 hồ sơ (26 HIGH, 120 MEDIUM, 14 LOW), main status 156/2/2 trong phạm vi đã đối chiếu. Coverage 2.890 paths: 736 read, 388 partial traces, 1.230 scanned, 528 inventoried, 8 excluded; đây không phải tuyên bố đọc/hiểu toàn code.
- Round 22: SEC-030 payment PostgREST scope; SEC-011 mở rộng assignment; 14 worker/provider/event files đọc trọn, không thêm finding. Round 23: 3 pharmacy/billing services đọc trọn, không thêm finding; CLIN-041 chỉ generic Form Engine, v5 đã có schema-key check trong đường được review.
- Handoff đã cập nhật ở `BAT-DAU-TU-DAY.md`, `TIEP-TUC.md` và `blocks/round22-summary.md` / `round23-summary.md`. HTML v0.46 qua structural/evidence 6/6, browser desktop/mobile và ZIP 276 file qua member-set/CRC/bytes/SHA (RUN-082..084); ZIP cuối được dựng lại sau log cuối, outer hash ở MANIFEST-GOI.json. Không chạy ClinicAI app/DB/API/PostgREST/provider/production tests; không đọc secrets/PHI. Full source audit chưa xong.

## Round 21 — patient/PostgREST, dashboard freshness, finance date and prescription amendment — 20/10/2026

- Thêm SEC-029 MEDIUM cho patient table direct SELECT qua PostgREST; mở rộng FE-002 với màn phản hồi thuốc stale sau refresh fail. Giữ cap 20 lượt phản hồi và accounting date hoàn chuyển khoản làm observation/câu hỏi policy.
- Đọc full `clinic_policy.py`, `dinh_chinh_don.py`; 32 path trong coverage slice, 2 full reads. 158 hồ sơ trên exact-main. Coverage 727 read, 370 traced, 1.257 scanned, 528 inventoried, 8 excluded.
- Không chạy app/DB/API/PostgREST/provider/production tests; không đọc secrets/PHI. Xem `blocks/round21-summary.md` và `blocks/round21_coverage.json`; HTML v0.42 qua RUN-079/080; ZIP 263 file qua RUN-081. Sau khi nhúng các run rows, HTML sẽ được kiểm lại và package được dựng/verify lần cuối. Full source audit chưa hoàn tất.

## Round 20 — queue, recall, reminders, clinical results and cleanup — 20/10/2026

- Exact-main `956ba4f236b1c92f1280d2097018c199e90ce8c7`: 3 additions (CLIN-040 MEDIUM, OPS-005 LOW, FE-022 LOW); SEC-028 expanded with queue room/node projection from PENDING roster. Round coverage 36 paths, including 16 full-file reads. Total risk register 157; coverage 725 read, 360 traced, 1.268 scanned, 529 inventoried, 8 excluded.
- Held observations: SonoBiometry has no current caller enabling `showSono`; old full-wipe script may stop after writers stop when new payment child tables exist, but preflight/transaction fail closed. Neither is promoted without usage/policy evidence.
- No ClinicAI application tests, DB/API/provider/production checks, secrets or PHI. See `blocks/round20-summary.md` and exact evidence in `blocks/round20_findings.json`/coverage.
- RUN-076: report v0.41 structural/evidence 6/6, all findings exactly once with exact pinned-source hashes/ranges. RUN-077: desktop/mobile, search/filter/print passed; 157 cards, 2.890 ledger rows, no overflow/page error/external request. RUN-078: audit-only package 259 members passed CRC/byte-count/per-file SHA; final archive regenerated and rechecked. These validate artifacts only. Full source audit remains incomplete.

## Round 19 — notification, clinical-form, patient privacy and roster — 20/10/2026

- Tích hợp trên exact-main `956ba4f236b1c92f1280d2097018c199e90ce8c7`: thêm 14 hồ sơ, mở rộng SEC-016 và SEC-018. Năm file đọc trọn; các file còn lại trace vùng liên quan. Coverage tổng: 709 read, 352 traced, 1.291 scanned, 530 inventoried, 8 excluded.
- Finding tập trung vào UI thông báo che lỗi tải/giới hạn 50; in biểu mẫu chưa làm rõ draft/release; chọn form không ràng buộc chắc với dịch vụ; autosave chưa phát hiện xung đột cùng trường; thiếu capability guard ở một số patient reads; fanout Telegram có thể gửi trùng khi một recipient lỗi; Zalo timeout không có trạng thái UNKNOWN bền; roster authority chưa nhất quán giữa PENDING/APPROVED/REJECTED; xếp lịch có thể bỏ sót ca do điều kiện truy vấn trạng thái.
- Thêm bằng chứng SEC-016 về đường ghi ghi chú lượt TKYK thiếu assignment guard và SEC-018 về bảng số điện thoại phụ có RLS clinic-only. Phạm vi vẫn cùng clinic ở các finding nêu rõ; không suy ra cross-clinic leak.
- Không chạy test ClinicAI, API, DB, PostgREST/RLS, browser app, provider, production hay fault injection; không truy cập secrets/PHI. Xem `blocks/round19-summary.md` và JSON cùng tên cho exact ranges, hashes, điều kiện, dedupe và giới hạn. Script tích hợp: `integrate_round19.py`.
- RUN-074: HTML v0.40 qua 6/6 structural/evidence checks, gồm exact-main hash/excerpt và đủ 154 hồ sơ. RUN-075: desktop/mobile report UI qua; 154 cards, 2.890 ledger rows, không overflow/page error/external request. Đây chỉ là QA trang audit. ZIP v0.40 gồm 255 file đã qua member-set/CRC/byte-count/per-file SHA-256; checksum ở MANIFEST-GOI.json. Full source audit chưa hoàn tất.

## Round 18 — clinical correction, worker recovery and tender reconciliation — 20/10/2026

- Đối chiếu exact-main và sổ cũ; trace có mục tiêu 25 path, không nhận là full-file read. Nâng 3 path từ scanned lên traced; coverage: 704 read, 343 traced, 1.305 scanned, 530 inventoried, 8 excluded.
- Thêm CLIN-036 MEDIUM/design_gap: thu hồi tệp sau khi nhân viên ghi nhận gửi chưa tạo corrective handoff; `gui_luc` không chứng minh đã giao cho bệnh nhân, cần chốt policy. INF-022 MEDIUM/confirmed_static: có một số thông báo theo vai nhưng chưa có xử lý/retry theo từng dead-letter trong app. FIN-016 LOW/confirmed_static: hoàn tiền mặc định gán một scalar method cho cycle thu hỗn hợp; chưa chứng minh sai tổng hoặc mất tiền.
- Dedupe lần lượt với CLIN-019, INF-017/018/011, FIN-004/012; xem `blocks/round18_lifecycle_worker_finance.md`. Hash/range và trạng thái path ở hai JSON cùng tên.
- Không chạy test ClinicAI, DB, API, browser, production; không chạm secrets hoặc dữ liệu bệnh nhân. RUN-072: HTML v0.39 qua 6/6 structural/evidence checks và desktop/mobile QA. RUN-073: ZIP v0.39 gồm 251 file qua member-set/CRC/byte-count/per-file SHA-256; checksum ở MANIFEST-GOI.json. Full source audit vẫn dang dở.

## Round 17 — audit visibility, commit boundary and status BFF — 20/10/2026


- Đọc trọn 8 file trên exact-main: audit writer/service/router/page, floor service, status BFF, dashboard error boundary và day-window test; trace thêm hai test liên quan. Fingerprints và giới hạn ở `blocks/round17_audit_visibility_commit_boundary.coverage.json`.
- Thêm SEC-026 (quyền cấp/thu có trong domain_event nhưng chưa hiện ở nhật ký hợp nhất), INF-021 (4 mutation tầng commit trước audit append), FE-018 (lỗi status đọc bị BFF trả HTTP 200, panel có thể throw). Cả ba là confirmed_static; FE-018 xếp LOW vì error boundary gần nhất giữ phạm vi ở dashboard route.
- Đã dedupe với SEC-013, INF-010, SEC-006 và FE-017; không trùng nguyên nhân/tác động. Candidate fallback clinic policy được giữ ở STATE.held_observations do cần xác minh policy/impact.
- Không chạy app test/fault injection; không truy cập DB, Auth, production, secrets hay patient data. Full source audit còn dang dở.
- RUN-070: HTML v0.38 qua 6/6 structural/evidence checks và desktop/mobile QA; SHA-256 hiện tại nằm ở HTML-QA.json. RUN-071: ZIP v0.38 gồm 247 file, qua member-set/CRC/byte-count/per-file SHA-256; outer checksum ở MANIFEST-GOI.json.

# Nhật ký kiểm toán

## 19/10/2026 — Khởi tạo

- Người dùng chốt audit + thiết kế sản phẩm, lưu context để đổi tài khoản và HTML cuối.
- Đã đọc quy tắc repo, bản đồ, trạng thái mới nhất trong docs (08/10; chưa xác minh prod).
- HEAD ban đầu `543b9787`, branch `feat/giam-gia`; có thay đổi chưa commit từ trước.
- Audit 27/09 và bộ 02/10 là nguồn lịch sử cần kiểm lại, không phải kết luận hiện hành.
- Bước tiếp: lập manifest, phân khối đọc, lưu chứng cứ và kiểm chứng chéo.

## Gián đoạn agent trong phiên 19/10

Các agent chuyên mảng dừng do usage limit; security báo network permission revoked. Root tiếp quản checkpoints. Không coi khối đã xong chỉ vì agent đã dừng. Còn cần kiểm chứng chéo, bổ sung security/clinical findings đang dở, HTML và thiết kế đích.

## Checkpoint 2026-10-19T17:46:43.192198+07:00 — root tổng hợp và đối chiếu main

- Baseline working tree 543b9787+WIP cũ hơn main956ba4f2; 728 đường dẫn khác. Main manifest2.890 file, structural scan2.292, trace một phần25, inventory565, binary8.
- 21 hồ sơ: 17 còn dấu hiệu trên main, 2 main đã xử lý một phần, 2 main đã có bản sửa. Không tính design gap/hypothesis thành exploit đã chứng minh.
- RUN-001:27passed. RUN-002:5 probe quan sát baseline. RUN-003/004:1 ca đỏ do code/schema lệch (đã chạy riêng), không che lỗi. RUN-005:FIN-001 main sửa đúng, CLIN-001/002 main vẫn tái hiện. RUN-006:authenticated ACL grant cũ còn sau migration main, transaction rollback/DB tạm xóa.
- Có thiết kế đích/lộ trình/nguồn standards/HTML tự chứa và QA desktop/mobile/filter/print-prep/zero external requests. File baseline không đổi bởi audit.
- Chưa hoàn tất toàn code. Tiếp đúng TIEP-TUC.md, không gọi v0.1 là final. Agent dừng vì quota nên dùng file, không chờ agent cũ.

## Checkpoint bổ sung 2026-10-19T17:51:09.540714+07:00

- RUN-007 mở rộng ACL gặp schema khuôn thiếu bảng kho, lưu là lỗi môi trường probe. RUN-008 ACL-only với bảng kho placeholder: authenticated vẫn có SELECT privilege prescription_draft/settings. Đã rollback/xóa DB tạm; chưa full restore/RLS JWT.
- Đọc thêm work_item issue/list/router và nhan_ca siêu âm; CLIN-004 design gap nhận/bàn giao trách nhiệm. Tổng22 hồ sơ, main trace một phần28 file.
- Tiếp theo đúng TIEP-TUC.md; không coi các bằng chứng trên thay cho audit toàn main.

## Main runtime 2026-10-19T17:55:19.467237+07:00

Tạo managed detached checkout956ba4f2 ở /Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini, dùng symlink .venv từ checkout gốc. Wrapper áp42 migration thiếu vào DB tạm, khuôn chung giữ nguyên. Hai probe bất biến RED đúng lỗi CLIN-003/FIN-003;31 test sẵn có cùng vùng xanh. Probe source đã lưu cả audit/probes và worktree; không sửa app. Còn browser fault injection, full restore/RLS và audit main rộng hơn.

## Main vòng 2 — tiếp tục sau yêu cầu của người dùng

Đã tích hợp thêm 5 hồ sơ AI-001/FIN-004/SEC-002/FE-005/CLIN-005; nâng DB-002 lên actual-role/full-main-schema reproduction. 32 positive controls xanh. Chi tiết và nghi vấn chưa chốt: blocks/root-main-round2.md. Các agent vòng 2 đều quota-interrupted; root tiếp quản. Audit vẫn đang làm.

### Vòng2 mở rộng: event, file và metadata prod

INF007 route+DB mất receipt →2 tương tác; CLIN006 consumer/hide/list thật làm mất chuông correctionv3 sau ẩnv2; SEC003 receiver vượt free-space budget giả lập. 14result controls và47material controls xanh. Prod read-only18:27:SHAclean956ba4f2,424Python/API+worker khớp,373migration IDs khớp,4ACLdeny. Không PHI/env/log/mutation. Cập nhật thành30hồ sơ/74file tracepartial.

### Bộ pytest rộng trên main đã hoàn tất

RUN024:9failed/6968passed/2xfailed/27warnings153.91s. Đã phân loại9failure IDs đều test_audit_1910;10probe gồm9RED+1ACLobservation xanh. Do đó6967test hiện hữu xanh+2xfail, không lỗi ngoài dự kiến trong lượt này. Không phảifullCI/E2E/coverage80%. Không reset khuôn;4DBtạm wrapper tự dọn.


## Checkpoint 2026-10-19T19:47:21+07:00 — đồng bộ tài liệu sau 32 finding

- PHAT-HIEN.json hiện có32 hồ sơ; phân bố evidence18 local,11 static,2 design gap,1 hypothesis; theo main28 còn hiện diện,2 partial,2 addressed.
- MAIN-PHAM-VI.json: 2890 file; 553 inventoried, 2201 scanned, 128 traced một phần, 8 excluded. Việc quét không được coi là đọc hiểu full.
- RUN-025–028 đã bổ sung dependency triage có điều kiện Alpine, bootstrap 2 clinic giả, giao thuốc sai qua service+ASGI, và62 test đối chứng existing pass. Chi tiết nằm trong TEST-RUNS, DEPENDENCIES và blocks/root-main-round2.
- Thay TIEP-TUC bằng checkpoint hiện hành để bỏ thứ tự ưu tiên cũ đã hoàn tất. Agent frontend round3 được giao hoàn tất riêng FE-006; DB/security/finance/infra agents trước đó quota-interrupted.
- Working tree ứng dụng không bị audit thay đổi trong lượt này; chỉ audit artifacts được cập nhật. Audit vẫn in progress.


## Đọc sâu thêm: hoàn tiền và bảo toàn tiền — 19/10/2026

- Đọc trọn `hoan_tien_service.py` trên exact main (628 dòng) cùng các router refund và hai phiên bản DB trigger. FIN-004 hiện có đã mô tả đầy đủ cả vấn đề ROUND_HALF_UP ở dòng không giảm; không tạo finding trùng.
- Xác nhận pending refund giữ lại quantity trong aggregate, mutation khóa visit→cycle→refund; cash refund phát event trong cùng transaction. Còn thiếu caller/UI và đối soát POS/báo cáo nên không coi nhánh tiền hoàn đã hoàn tất.


## FE-006 tích hợp — 2026-10-19T19:50:15+07:00

- Review frontend round3 chốt FE-006 MEDIUM/confirmed_static: Set được thêm trước request ghi đã xem, SSE refresh giữ component/ref; request thất bại không có retry. Chỉ nói trạng thái chưa được ghi, không nói false-seen/auto-close. Main snippets/hashes đã đưa vào PHAT-HIEN và HTML.
- 23 file mới trong frontend coverage được merge vào main manifest sau exact SHA-256; main ledger hiện 151 traced một phần,2178 scanned,553 inventoried,8 excluded. Không có application source thay đổi.
- Finding count33: 16 HIGH,17 MEDIUM; main29 hiện diện,2 partial,2 addressed. Evidence levels18 local,12 static,2 design gap,1 hypothesis.

## Checkpoint 2026-10-19T19:53:48+07:00 — finance round 4, report v0.5

- FIN-005: static trace main query → API → UI/export; hai danh sách thu/hoàn bị LIMIT 3000 và warning chỉ vào log. Thêm nguồn lực không thay đổi app; chưa xác minh ngưỡng trên dữ liệu production.
- Coverage exact-main: 159 traced một phần / 2170 scanned / 553 inventoried / 8 excluded; totals lấy từ ledger.
- Đối chiếu cho thấy TIEP-TUC trước đó có aggregate stale (evidence/status counts lệch sổ JSON); đã chuẩn hóa theo `PHAT-HIEN.json` và `MAIN-PHAM-VI.json`.
- Audit vẫn chưa xong; tiếp tục auth/session, recovery/migrations, event ownership, pharmacy/finance caller paths.


## Checkpoint 2026-10-19T20:01:42+07:00 — auth/session round 2, report v0.6

- Đọc ForgotPasswordForm, ResetPasswordForm, toàn bộ TaiKhoanService và route admin users; self-service reset xác nhận cùng gốc split-auth authority của SEC-001, không tạo finding trùng.
- SEC-005 MEDIUM/confirmed_static: GET staff list/read đi qua identity chung và trả CCCD/hồ sơ pháp lý; scope chỉ trong clinic. SEC-006 MEDIUM/confirmed_static: unban backend xong nhưng GoTrue lỗi vẫn trả ok:true và UI báo thành công. Có source SHA/excerpt từ exact main trong PHAT-HIEN.json.
- Coverage main: 171 traced một phần / 2,158 scanned / 553 inventoried / 8 excluded; code-like 158 traced / 2,154 scanned / 22 inventoried. Audit vẫn chưa đọc hết code. Không có sửa application source.


## Checkpoint 2026-10-19T20:06:01+07:00 — upload boundary round 1, report v0.7

- Mở rộng SEC-003: trace `nhan_multipart` qua CSKH, payment proof và upload đối tác; trần chứng từ thu 15 MiB được kiểm sau khi file tạm đã nhận. Middleware tổng thân chỉ giới hạn route CSKH và tắt khi MAX_BYTES_KET_QUA_UPLOAD=0; code per-type mặc định 0 nếu env không đặt. Không đọc cấu hình production, không kết luận có disk exhaustion thật.
- Read selected upload guards, flow streaming/cleanup, file access permission and ranged download. Existing SEC-002/003 remain distinct; no additional confirmed finding in this slice.
- Coverage exact main: 175 partial traces / 2,154 scanned / 553 inventoried / 8 excluded; code-like 162 traced / 2,150 scanned / 22 inventoried. Audit vẫn chưa đọc hết code.


## Checkpoint 2026-10-19T20:26:47+07:00 — FIN-006, report v0.8

- Truy vết exact-main sổ/xuất hoá đơn: UI gửi nguyên khoảng ngày; XuatHoaDonService dùng DanhSachHoaDonService.xem; helper chung rút kỳ dài về ngày cuối trừ 92 ngày; preview/XLSX chỉ nhận tập đã rút và UI không hiện data.tu/data.den.
- AST chạy đúng helper từ pinned source bằng Python stdlib (RUN-029): các kỳ thử bị bỏ 1, 199 và 273 ngày; returned range là 93 ngày inclusive. Không import app, không DB/ASGI/browser/XLSX, không production. FIN-006 MEDIUM/confirmed_static.
- PHAT-HIEN: 37 records = 16 HIGH / 21 MEDIUM; evidence 18 local / 16 static / 2 design gap / 1 hypothesis; main 33 still / 2 partial / 2 addressed. Main ledger: 180 partial / 2,149 scanned / 553 inventoried / 8 excluded; code-like: 167 traced / 2,145 scanned / 22 inventoried. Năm file mới chỉ ghi `traced` theo spans chọn, không phải đọc trọn.
- Chỉ audit artifacts/HTML được cập nhật; code ứng dụng, migration, DB và working-tree WIP giữ nguyên. Cần dựng/kiểm lại HTML và ZIP sau cập nhật; tiếp tục reconciliation, export runtime trên DB giả và các block còn lại. Audit chưa xong.


### Mở rộng FIN-006 — báo cáo cuối ngày

- Đọc thêm `BaoCaoCuoiNgayService` và các route JSON/CSV/XLSX: ba đường gọi `doc_khoang_ngay` qua helper chung; report payload/file name dùng ngày effective. UI gửi kỳ đã chọn, summary/link truyền loc từ selected state; bản in dùng bc.tu/bc.den. Mở rộng cùng FIN-006 vì cùng gốc clamp, không tạo ID trùng.
- Main ledger: 184 traced một phần / 2,145 scanned / 553 inventoried / 8 excluded; code-like 171 traced một phần / 2,141 scanned / 22 inventoried. FIN-006 vẫn confirmed_static; RUN-029 chỉ thực thi helper thuần, không xác minh route hay báo cáo thực.


## Checkpoint 2026-10-19T20:32:18+07:00 — SEC-007, report v0.9

- Static trace exact-main: migration ACL cuối cấp authenticated EXECUTE cho `clinic_hours_for_date`, `resolve_effective_cap/caps`; function SECURITY DEFINER đọc clinic settings/capacity theo UUID đầu vào, không kiểm membership. Caddy public chuyển `/rest/v1/*` qua PostgREST. Phạm vi bằng chứng là giờ mở cửa/capacity metadata; không phải PHI hoặc ghi dữ liệu. Không gộp DB-001 vì DB-001 là helper ghi liệu trình và lỗi grant/restore khác.
- SEC-007 MEDIUM/confirmed_static; chưa kiểm JWT/2-clinic qua PostgREST, chưa xác minh production ACL của các helper. Main ledger: 189 partial traces / 2,142 scanned / 551 inventoried / 8 excluded; code-like 174 traced partial / 2,138 scanned / 22 inventoried.
- Sổ: 38 findings (16 HIGH, 22 MEDIUM); evidence 18 local, 17 static, 2 design gap, 1 hypothesis; main 34 still / 2 partial / 2 addressed. Không sửa application source/migration/DB.

## Checkpoint 2026-10-19T20:36:43+07:00 — allowlist ACL và trace hoàn tiền

- RUN-030: đọc allowlist function cuối, các helper authenticated đã chọn và test column privilege; không có finding mới ngoài SEC-007. Chưa chạy JWT/PostgREST 2-clinic.
- Truy vết thêm năm file từ scan sang partial trace; coverage exact-main nay 194 traced / 2.137 scanned / 551 inventoried / 8 excluded; code-like 179 / 2.133 / 22.
- Đọc lại logic create/confirm/close refund, row locks, reserved pending quantities, per-line amount, event cùng transaction; đối chiếu test suite hiện có và FIN-004. Lát cắt hiện không tạo finding bổ sung; kiểm toán tiền/caller/migration vẫn chưa đủ để kết luận toàn bộ.
- Báo cáo v0.10 được dựng lại; không sửa application source, migration, DB, production hoặc Git history.

## Checkpoint 2026-10-19T20:39:37+07:00 — SEC-008, upload ảnh siêu âm

- Exact-main trace từ Next multipart route qua FastAPI UploadFile đến MediaService: request.formData và file.read chạy trước MAX_BYTES=12 MiB. Middleware body count chỉ khớp route CSKH; Next/Caddy source không có cap route này.
- SEC-008 MEDIUM/confirmed_static; cần tài khoản có quyền upload. Tác động tài nguyên là nguy cơ từ thứ tự parse/read, chưa đo RAM/spool hoặc tái hiện trên ứng dụng; chưa kiểm production. Không gộp SEC-003 vì SEC-003 chứng minh receiver kết quả ghi vượt reserve khi thiếu Content-Length, còn SEC-008 là buffered ultrasound image body trước cap.
- Test hiện có kiểm service cap sau khi nhận bytes và middleware multipart chỉ cho CSKH; chưa có upload cap test cho siêu âm. Main ledger: 196 traced / 2.135 scanned / 551 inventoried / 8 excluded; code-like 181 / 2.131 / 22.
- Sổ 39 findings: 16 HIGH, 23 MEDIUM; 18 reproduced local, 18 confirmed static, 2 design gap, 1 hypothesis. Không sửa source app/migration/DB.

### Hiệu chỉnh SEC-008 sau khi đọc proxyClientMaxBodySize — 2026-10-19T20:42:12+07:00

- Lượt đầu gọi quá sớm đây là body không giới hạn trước service. Đọc lại `proxy.ts` cho thấy route siêu âm không nằm trong matcher exclusions; Next proxy buffer mặc định 10 MiB. Tài liệu chính thức xác nhận phần vượt cap bị cắt trong buffer và route tiếp tục với phần body đã có. `next.config.ts` không override.
- Đã sửa SEC-008 thành mismatch Next 10 MiB vs service 12 MiB, không còn claim unbounded upload/host exhaustion. Multipart gần ngưỡng có thể hỏng; chưa chạy app để xác nhận parse/status cụ thể, và chưa thấy caller UI.


## Checkpoint 2026-10-19T20:45:29+07:00 — SEC-009 và câu trả lời về độ phủ

- Đọc sâu endpoint feedback ảnh, API bypass trong Next proxy, session guard của backend proxy, Docker runner, compose, script đọc feedback và env mẫu. Ghi SEC-009 MEDIUM/design_gap: `writeFile` xảy ra trước auth helper; nếu `FEEDBACK_DIR` writable, ảnh anonymous có thể thành file mồ côi trước 401; không có cleanup trên nhánh lỗi.
- Điều kiện quan trọng: default path tại WORKDIR `/app` resolve thành `/.feedback`, runner là `USER node`; `.env.prod.example` không khai báo `FEEDBACK_DIR`. `.env.prod`/VPS không được đọc, nên chưa biết cấu hình thật và không khẳng định có thể khai thác production.
- Cập nhật ledger pinned-main: 199 traced một phần / 2.133 scanned / 550 inventoried / 8 excluded; code-like 183 traced / 2.129 scanned / 22 inventoried. Main 2.890 file. Findings: 40 (16 HIGH, 24 MEDIUM); evidence 18 reproduced local, 18 confirmed static, 3 design gap, 1 hypothesis; main 36 still / 2 partial / 2 addressed.
- Đã tính path bằng Node và truy vết static; chưa chạy app/container/HTTP hoặc production. HTML/gói cần QA lại sau cập nhật v0.13. Không sửa app source, migration, database, production hoặc Git history.


## Checkpoint 2026-10-19T20:48:50+07:00 — SSE/event scaffold static trace

- RUN-034: dashboard SSE → FastAPI identity → clinic ChangeBroker → PostgreSQL LISTEN/NOTIFY; UI fallback/reconnect. Không có finding mới. INF-005 vẫn hypothesis, vì chưa fault-inject stale handler sống + worker thứ hai.
- Đọc EventService, publisher/adapter/tool wrapper/GoldenRecordEngine: generic outbox relay không có caller hiện hành trong source search; RabbitMQPublisher/GoldenRecordEngine là stub. Chưa kết luận production runtime hay mọi event pipeline.
- Main ledger: 206 partial traces / 2.126 scanned / 550 inventoried / 8 excluded; code-like 190 traced / 2.122 scanned / 22 inventoried. Tổng finding không đổi: 40 (16 HIGH, 24 MEDIUM), evidence 18 local / 18 static / 3 design gap / 1 hypothesis.
- Chỉ đọc pinned source; không sửa app/migration/DB, không gọi production.


## Checkpoint 2026-10-19T20:55+07:00 — CLIN-008, SEC-002 mở rộng, RUN-034 coverage

- Thêm CLIN-008 MEDIUM/confirmed_static: luồng sửa CCCD chỉ kiểm định dạng và cập nhật; không tìm hồ sơ trùng, không yêu cầu lý do như luồng tạo. Đã hash 5 file exact-main và nối editor → PATCH/schema/service → migration. Không DB/browser/prod test.
- Mở rộng SEC-002: cùng fallback `v_quyen_thuc_te` rỗng → vai tài khoản còn hiệu lực qua đường đọc/in phiếu. Hash route `phieu.py` và service `form_engine_service.py` exact-main; phần này static-only, chưa gọi HTTP.
- Hoàn tất lát cắt SSE ở code coverage: route, client event lifecycle/backoff, refresher và hook; đọc đầy đủ `EventService` + upcaster. `get_unpublished` không có relay caller; có reference tới `record_and_publish` từ adapter/tool wrapper, trong khi RabbitMQPublisher/GoldenRecordEngine là stub. Không finding event mới.
- Coverage tính trực tiếp từ MAIN-PHAM-VI.json: 207 traced một phần / 2.125 scanned / 550 inventoried / 8 excluded; code-like 191 / 2.121 / 22 / 0. Tổng 2.890 file. 41 findings: 16 HIGH, 25 MEDIUM; 18 reproduced local, 19 confirmed static, 3 design gap, 1 hypothesis; main status 37 still / 2 partial / 2 addressed.
- Đã sửa lệch checkpoint trước: ledger thực tế là nguồn số; HTML v0.14/ZIP cũ cần dựng và QA lại. Audit còn tiếp tục; chưa đọc toàn bộ code, không sửa source app/migration/DB hoặc production.


## 19/10/2026 — v0.16 finance / restore / tenant

- Gộp kết quả finance/pharmacy: mở rộng FIN-002 sang lịch sử 200 và tư vấn 100; thêm FIN-007 thu/hoàn cuối ngày 5.000 và FIN-008 thuốc theo khách 1.000. Các cap này chỉ xác nhận tĩnh; chưa có bằng chứng dữ liệu thật vượt ngưỡng.
- Mở rộng DB-002 và INF-006: đường restore public-only `--no-acl` không dựng migration ledger/reconcile ACL; runner sau restore coi migrations là pending. Chưa diễn tập DB restore/replay.
- Thêm INF-008 bootstrap local có thể dở dang nhưng retry qua guard ledger; chưa fault-injection.
- Thêm DB-005 về thiếu đường provision tenant/workflow rõ ràng; seed node gắn clinic cố định, hai provisioner dùng `LIMIT 1`. Chưa tạo clinic thứ hai.
- Nâng 23 hồ sơ file từ scanned/inventoried sang traced partial ở đúng lát cắt trên pinned SHA. Ở mốc trước khi clinical trace: 221 traced, 2.111 scanned, 550 inventoried, 8 excluded; đây không phải đọc hết file.
- Bước kế: refresh report + zip và QA; sau đó tiếp tục clinical identity/referral/form lifecycle và kiểm thử DB disposable.


## 19/10/2026 — v0.17 clinical identity / MPI

- Thêm SEC-010: shared-form read path statically permits same-ID path to form_data without clinical capability. Severity HIGH due sensitive medical content; no HTTP test or production evidence.
- Thêm CLIN-009: MPI pending queue has insertion/read helper but no application route/UI/consumer found by pinned-source search. Design gap; no claim about manual process outside repo.
- Updated coverage for selected evidence spans and counts from exact inventory: 225 traced partial, 2.107 scanned, 550 inventoried, 8 excluded (2.890 files). Code-like suffix scope: 209 traced, 2.103 scanned, 22 inventoried (2.334).
- v0.17 report/ZIP were rebuilt and QA-passed in RUN-035; that verification is report-only, not app E2E.


## Checkpoint 2026-10-19 — v0.18 patient-scope / workflow batch

- Tích hợp sáu finding từ exact pinned main: FE-007 stale patient history context; FE-008 decision worklist silently absent on fetch error; SEC-011 missing TKYK patient-assignment checks across clinical read paths; CLIN-010 appointment/visit service-type mismatch through CHECKED_IN reschedule; CLIN-011 missing old/new deltas for service/channel/referrer; INF-009 replacement reminder timer lost when old due timer is DANG_LAM.
- Tất cả là confirmed-static; không chạy browser/HTTP/DB fault injection hoặc production cho batch này. SEC-011 chỉ same-clinic UUID scope; CLIN-010/UI path phụ thuộc check-in sớm; FE-007 không cho thấy write chéo patient; INF-009 là race hẹp.
- Nâng 20 file trong ledger từ scanned sang traced partial theo các span được đọc, gồm cả app/test/tool code; main hiện 245 traced, 2.087 scanned, 550 inventoried, 8 excluded. Code-like 229 traced, 2.083 scanned, 22 inventoried.
- Sổ hiện 53: 19 HIGH / 34 MEDIUM; 18 reproduced-local / 29 confirmed-static / 5 design-gap / 1 hypothesis; main 49 present / 2 partial / 2 addressed.
- HTML/ZIP cần rebuild, structural + desktop/mobile QA và kiểm manifest sau batch này. Full audit vẫn đang làm; không sửa app source/migration/DB/production.


## Checkpoint v0.20 — bệnh nhân, cấu hình và điều phối

- Tái tiếp tục audit exact main `956ba4f236b1c92f1280d2097018c199e90ce8c7`; chưa kết luận toàn code.
- Đọc tiếp đường ghi/đọc bệnh nhân và audit; roster scope, display settings; config phòng ↔ routing assignment; undo completion và attempt revision.
- Tích hợp 9 hồ sơ mới (SEC-013..015, CLIN-013..018, INF-010); một HIGH, tám MEDIUM. Nâng 17 dòng ledger từ scanned sang traced-partial; tổng 269/2063/550/8.
- RUN-038: synthetic DB test 1 passed, chứng minh config mapping đổi sau eligibility check nhưng route vẫn commit ASSIGNED vào phòng đã bị loại; probe lưu trong `probes/test_audit_1910_routing_config_race_db.py`.
- Xây dựng lại HTML/ZIP và QA; các agent tiếp tục các lát cắt API/RPC/files, clinical result lifecycle và pharmacy return/reconcile. Không sửa app/production.


## Checkpoint v0.21 — result lifecycle, identity và operator recovery

- Tiếp tục từ SHA exact main `956ba4f236b1c92f1280d2097018c199e90ce8c7`; không sửa code/migration/DB nghiệp vụ, không truy cập prod/PHI/secrets.
- Tích hợp sáu finding mới: CLIN-019..022, FE-009, INF-011; mở rộng SEC-011, PHAR-001, INF-005 theo cùng root cause.
- RUN-039: synthetic DB probe thu hồi file kết quả cuối; marker `ket_qua_luc` còn, H7 BO_QUA, không tạo thông báo. Có note `blocks/scheduling-result-revoke-h7-followup.md`; source probe/stdout transient đã xóa; policy explicit undo cần chốt.
- RUN-040: HTTP ASGI + DB dùng một lần; HOAN sau void 409, GIU_LAI 200; tổng PHAI_THU/PHẢI_TRẢ 50.000/0, không ghi so_no cho `medicine.returned`. Output và seed caveat: `probes/HTTP-VOIDED-RETURN-PROBE.txt`.
- RUN-041: hai service-level synthetic tests pass: phiếu v5 save sau FINALIZED không amendment; `in_ket_qua` trả bản sửa chưa release. Probe đã xóa; module migration xác nhận release table chưa nối với đường print/send có cấu trúc.
- Identity slice: multi-clinic schema/backend có selector, dashboard hiện chặn nhiều membership active; phân loại product gap, không phải cross-tenant leak. Worker slice: INF-005 có static extension sang hen_gio; POS DEAD thiếu operator recovery nhưng relay opt-in.
- Canonical state sau tích hợp: 71 findings (21 HIGH / 50 MEDIUM; 21 reproduced-local / 38 confirmed-static / 11 design-gap / 1 hypothesis); main 67 present / 2 partial / 2 addressed. Ledger 278 trace một phần / 2.054 scanned / 550 inventoried / 8 excluded. Không coi là đã đọc hết code.
- RUN-042 report QA: structural 5/5; desktop 1280/mobile 375 không tràn ngang; 71 cards/2.890 ledger rows; search/filter/print pass; không page error/external request. ZIP 126 entry khớp bytes/SHA/CRC, SHA/bytes/CRC khớp theo MANIFEST-GOI.json; kiểm tra outer ZIP hash sau khi dựng gói cuối.
- Next: tiếp tục source audit theo TIEP-TUC.md. HTML/ZIP là checkpoint artifact QA, không phải ứng dụng đã qua E2E hay audit toàn mã.

## Checkpoint v0.22 — 19/10/2026

- RUN-043: worker lease race generic tái hiện 1 passed trên DB disposable; RUN-045: pure-helper phòng accepting=false trả nhan_duoc=true nhưng count=0; callback cũ + mới cùng commit scratch effect sau khi reclaim. Không suy ra consumer/provider/prod.
- Thêm CLIN-023..027, FE-010, INF-012; mở rộng FIN-002 và SEC-011; exact evidence/hash được sinh từ snapshot 956ba4f2.
- Rebuild HTML/ZIP và chạy report structural/browser QA là bước kế tiếp của checkpoint; nếu đang dở, đọc STATE/TIEP-TUC, không đọc lại từ đầu. Full audit còn thiếu.

## Round 8 — upload kết quả, Nam khoa và phân quyền

Round 8 exact-main checkpoint (LAB-001, CLIN-034, FE-011). Three findings were added after independent source-hash and excerpt verification: LAB-001, CLIN-034, FE-011. The permission-admin slice found no new item and corroborates SEC-012. All three additions are confirmed_static, still present in the pinned snapshot, and not runtime/production-confirmed. Main source review remains incomplete; continue from STATE.json and blocks/round8_*. The dirty working tree is not evidence; source remains /tmp/clinicai-audit-main-956ba4f2 at 956ba4f236b1c92f1280d2097018c199e90ce8c7.

## Round 8 — upload kết quả, Nam khoa, phân quyền và tenant

Round 8 exact-main checkpoint (LAB-001, CLIN-034, FE-011, SEC-018). Four findings were added after independent source-hash and excerpt verification. The permission-admin slice found no new item and corroborates SEC-012. All four additions are confirmed_static, still present in the pinned snapshot, and not runtime/production-confirmed. SEC-018 describes same-clinic role scope, not cross-tenant access. Main source review remains incomplete; continue from STATE.json and blocks/round8_*. The dirty working tree is not evidence; source remains /tmp/clinicai-audit-main-956ba4f2 at 956ba4f236b1c92f1280d2097018c199e90ce8c7.

## Round 9 — AI runtime và ranh giới agent

Checkpoint round 9 trên snapshot main ghim (AI-004). Đã đọc trọn 61 file trong tools, graphs, orchestrator, llm và event_bus; trace thêm wiring app, router lab/ops, migration và tests liên quan. AI-004 xác nhận bằng static trace rằng shared LLM client không được nối với meter; chưa kiểm app, DB, provider hay production. HTML v0.27 đã qua kiểm cấu trúc và browser QA; ZIP sẽ dựng lại sau khi nhập các lát đang chạy. Snapshot tiếp tục: 956ba4f236b1c92f1280d2097018c199e90ce8c7. Full source audit vẫn đang làm.


## Checkpoint v0.35 — 20/10/2026

- Đọc tĩnh thêm 7 module core và 6 file test liên quan (5 trọn, một đoạn test phone có mục tiêu); không có finding mới. Sentry còn được bootstrap sau `SENTRY_DSN` dù policy đánh dấu dịch vụ đã chết; code privacy options hiện có, chưa biết runtime/env nên chỉ ghi policy drift.
- RUN-064: HTML v0.35 qua 6/6 structural/evidence checks; 132 finding cards, 2.890 ledger rows, desktop/mobile không tràn, search/filter/print qua, không page errors/external requests. SHA-256 nằm trong `HTML-QA.json` và `STATE.json`. Chỉ QA báo cáo; không phải app E2E/audit toàn source.
- Kế tiếp: tạo và kiểm ZIP từ checkpoint này, rồi tiếp tục đọc source chưa semantic-read theo `STATE.json`.

- RUN-065: ZIP v0.35 audit-only được dựng và kiểm tra member set, CRC, bytes, SHA từng file; checksum tổng nằm trong `MANIFEST-GOI.json`. Gói chỉ có hồ sơ kiểm toán, cần repository/Git history đúng SHA để tiếp tục đọc code.


## Checkpoint v0.36 — 20/10/2026

- Reconciled a partial v0.35 integration: canonical ledger/findings already included INF-020 while STATE/report remained at 132; current count is 134 after adding SEC-025.
- Independent exact-main review corrected INF-020 known theoretical totals to production 112 at API=60 (default API=20 totals 72), staging 62 at API=20 (default API=10 totals 52). Added the separate API alert pool. Production Compose does not pin max_connections; no runtime/production status is claimed.
- SEC-025: password-change UI ignores resolved `signOut({scope:"others"})` error and always confirms other sessions signed out. LOW, configuration-dependent; no Auth/runtime test. Related modal test covers layout/fields only.
- Updated `MAIN-PHAM-VI.json`, `KIEM-CHUNG.json`, `STATE.json`, and `blocks/round15_*`. Exact-main evidence validation points at the detached worktree because the `/tmp` export lacks the staging Supabase compose file.
- RUN-066: v0.36 HTML rebuilt; 6/6 structural/evidence checks pass; desktop/mobile QA reports 134 cards, 2,890 ledger paths, no overflow/errors/external requests. RUN-067: 241-file ZIP passes member set, CRC, byte-count, SHA-256; outer checksum is in `MANIFEST-GOI.json`. **Full audit remains incomplete.** Next: continue unread source paths and synthetic validation candidates.


## Dashboard identity and authorization boundary — 20/10/2026, v0.37 checkpoint

- Đọc đầy đủ 10 file dashboard liên quan identity/session/validation/service-role và ba bộ boundary test; trace có mục tiêu ở POST/PATCH patient route. Fingerprint và trạng thái nằm ở `blocks/round16_dashboard_auth_boundary.coverage.json`.
- RUN-068: 22/22 test được chọn pass; Node có cảnh báo reparsing module-type, không có test fail.
- SEC-006 được corroborate qua Auth-admin BFF; không tạo finding trùng. Không có HTTP/browser/Auth provider/DB/RLS/production validation.
- Coverage exact main: 696 read, 340 traced một phần, 1.315 scanned, 531 inventoried, 8 excluded trên 2.890 paths. HTML/ZIP v0.37 cần QA sau cập nhật này. Full source audit còn dang dở.

- RUN-069: HTML v0.37 qua 6/6 structural/evidence checks và desktop/mobile browser QA; report SHA-256 `63f3238cc368f926fc013dc8d5d135182935f49afe195e4c2bf40c4e88cd4ed7`. ZIP v0.37 verification tiếp theo.

- ZIP v0.37 đã dựng lại với 243 file và qua kiểm member set, CRC, byte count, SHA-256 từng file; checksum tổng được lưu tại `MANIFEST-GOI.json`. Toàn bộ thay đổi trong checkpoint chỉ ở thư mục audit.


## Round 25 — 20/10/2026, v0.48 draft

- Thêm FE-025, API-006, OPS-006, OPS-007, CLIN-043; mở rộng FE-023 sang ba màn khách hàng.
- Các bằng chứng được trích từ exact-main SHA; 5 finding chưa có runtime/app/DB/production verification. OPS-006 phụ thuộc retention override=0; OPS-007 là mâu thuẫn tài liệu; CLIN-043 là interleaving cần test concurrent.
- Coverage ledger chỉ nâng read/traced theo phạm vi đã ghi trong `blocks/round25.coverage.json`; full audit còn mở. Held observations giữ riêng.
- Next: rebuild/QA HTML và ZIP; sau đó tiếp tục paths còn scanned/inventoried, ưu tiên result/print, recovery, patient/tenant, migration/RLS.


## Round 25 addendum — event/recovery

- Rà soát event worker/replay/retry/health/ops và test; không có finding mới đủ tách biệt ngoài INF-004/005/012/017/018/022/023.
- Giữ câu hỏi metrics tenant-scope ở `/ops/su-kien` dạng held: chưa xác nhận caller, multi-clinic runtime hoặc policy; không kết luận lộ dữ liệu.
- Đọc test files nhưng không chạy; SHA/ranges được ghi trong `blocks/round25.coverage.json`.


## Round 25 addendum — result/print lifecycle

- Thêm LAB-002: triage có thể tạo LAB_REVIEW khẩn sau khi bác sĩ finalize, do row cache cũ và active-only idempotency. LOW static concurrency inference; chưa tái hiện, không có bằng chứng production hoặc hỏng kết quả lâm sàng.
- Rà soát thêm order/entry/review/triage/in/print và BFF/API; không có lỗi độc lập khác đủ căn cứ. UI release helper/API contract giữ held vì không thấy production caller.
- Test chỉ đọc, không chạy; hashes/ranges ở `blocks/round25.coverage.json`.


## Round 26 — 20/10/2026, v0.49 draft

- Thêm FE-026 và OPS-008; mở rộng FE-004 (Báo cáo/Toàn cảnh/Trang chủ) và FE-023 (AppointmentBooking).
- Booking không gửi idempotency key từ AppointmentBooking; service duplicate check và partial unique index là guard nên không kết luận tạo lịch trùng. OPS-008 chỉ gây mất hiển thị nếu có trên 100 nhóm trong tập lọc; production volume chưa đo.
- Coverage theo hash và phạm vi đọc ở `blocks/round26.coverage.json`; không chạy test/runtime. Full audit tiếp tục mở; HTML/ZIP phải rebuild sau checkpoint này.


## Round 27 — 20/10/2026, v0.50 draft

- Mở rộng INF-021 từ danh mục tầng sang một số writer cấu hình phòng khám có cùng ranh giới audit; ghi rõ hai writer counterexample cùng transaction. Không tạo finding mới.
- Rà phân công/ownership và migration/RLS không thấy finding mới; account recovery, migration dry-run, partial-save UI được giữ như câu hỏi policy/hợp đồng.
- Coverage hash/range ở `blocks/round27.coverage.json`; không chạy ứng dụng, DB hay production. HTML/ZIP cần rebuild + QA report-only. Full source audit còn mở.


## Round 28 — 20/10/2026

Đã pin xác minh exact-main `956ba4f236b1c92f1280d2097018c199e90ce8c7`; thêm CLIN-044, PHAR-003, PHAR-004; mở rộng FE-002 cho đo sinh hiệu. Rà tĩnh UI/BFF/FastAPI/service/schema và test-source liên quan. Không chạy tests, app/API/DB/provider/VPS/production; không đọc secrets/PHI. `blocks/round28.coverage.json` ghi path, hash và line ranges. Full source audit chưa xong.

Report v0.51 đã build; `validate_report.py` PASS 6/6; `verify_browser.cjs` PASS: 176 cards, 2.890 ledger rows, desktop 1280/mobile 375 không tràn, search/print đủ 176, không page error/external request. Đây là QA HTML report, không phải kiểm thử ClinicAI. SHA-256 HTML: `904ec7347593d9cad2bd9dc6361f97e0ab432c3f950657f76bd0cb1407aa72d4`.

Sau khi cập nhật ledger và design narrative đến v0.51, rebuild HTML và chạy lại: validator 6/6 PASS; browser QA 176 finding cards, 2.890 ledger rows, desktop/mobile không tràn, search/print đủ, không page errors/external requests. Report SHA-256 `60f336b5cb30ae13609fce5f43eae4046c4dbdc543fe0519e79306bc7e777152`.


## Round 30 — 20/10/2026

Đối chiếu static exact-main các lát xuất hóa đơn/thuế, danh mục thuốc và bàn giao mốc khám. Không thêm canonical finding; thêm bốn held observations với contract/owner cần chốt. Nâng path status chỉ theo mức đọc thực tế. Không chạy test/ClinicAI/API/DB/provider/VPS/prod. Full source audit tiếp tục mở.

## Round 31 — 20/10/2026, v0.54

- Thêm CLIN-045: feedback CSKH cap 300 dòng toàn trang, API/UI không báo còn dữ liệu; điều kiện chưa đo production.
- Thêm CLIN-046: checkout → tắt phòng → undo có thể khôi phục queue waiting trong room inactive; hai test nửa luồng đã đọc riêng nhưng chưa compose.
- Dedupe OPS-009, FE-002, FE-004; giữ held question ownership/SLA khiếu nại. Đọc/trace 37 path theo `blocks/round31.coverage.json`; tests chỉ đọc, không chạy. Không gọi app/API/DB/prod. Full source audit còn mở.


## Round 32 — 20/10/2026 07:46 GMT+7, v0.55

- Thêm CLIN-047, SEC-033, CLIN-048; static exact-main, chưa reproduce. Mở rộng INF-017 sang timer CHET và SEC-011 sang GET phí khám thiếu authorization.
- Dedupe CLIN-031 cho retry chỉ định; xác nhận `duyet-chi-dinh` dùng `authorize-orders`, không route 410. Clinical form/result/lab và fee không tạo finding riêng; giữ held contract quote/current-price.
- Hash/ranges/test read-not-run ở `blocks/round32.coverage.json`; không chạy ClinicAI/API/DB/runtime/VPS/prod. Full source audit còn mở; report-only HTML QA và ZIP verification đã PASS (307 files; outer hash ở MANIFEST-GOI.json).


# Round 33 — 20/10/2026 07:55, v0.56

Source: exact pinned Git SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`; only report artifacts changed.

- Added SEC-034: removing the final selected room in an enabled room-scoped lego sends an empty scope, which becomes a clinic-wide capability grant.
- Added SEC-035: a transfer proof hidden with `go_luc` remains readable via an old authenticated GET URL by a user with payment-history scope. Migration explicitly defines this as hide/retain; LOW severity and contract limitation are stated.
- Added CLIN-049: changing doctor at the same slot time leaves the former doctor's advisory hold active for up to ten minutes.
- Extended SEC-027 with the still-registered administrative-profile and CSKH routes; treated as the same missing patient-read capability family.
- Read exact-main UI → BFF → API/service → migration/evaluator/test paths. Test files were read, not run; no app, API, DB, provider, VPS, production, secrets or PHI accessed.
- Coverage hashes and ranges: `blocks/round33.coverage.json`. Whole-source audit remains incomplete; report HTML and bundle QA are pending.


Report v0.56: `validate_report.py` PASS 6/6; report-only browser QA PASS (186 cards, 2,890 ledger rows, desktop 1280/mobile 375 no horizontal overflow, search/print pass, no page errors/external requests). HTML SHA-256: 94f0540880f325bc986d25e3480404d1acf2af56b82e4280b13468ccc548d7be. This does not test ClinicAI and the full source audit remains incomplete.

Round 33 final packaging: audit-only ZIP verified, 310 files; CRC, expected members, byte counts and per-file SHA-256 PASS. Outer SHA-256 is in MANIFEST-GOI.json. Full source audit remains incomplete.


## Round 34 — 20/10/2026 08:08

Thêm CLIN-050/051/052/053, OPS-010, API-007 và mở rộng SEC-027 từ SHA ghim. Static only; tests đọc nhưng không chạy. HTML/package QA sẽ chạy sau integration. Không sửa app/migration; full audit vẫn mở.


## Round 34 — QA báo cáo, 20/10/2026

Report-only validation PASS 6/6; browser QA PASS: 192 cards, 2.890 ledger rows, desktop/mobile không tràn, search/print đầy đủ, không page errors/external requests. HTML SHA-256 `528b84c888dbe57eee510492aab3d0826fcbae92326c197ce19b5fde46c977c7`. Chỉ kiểm tra HTML báo cáo; không phải ClinicAI tests/runtime. Full source audit vẫn chưa hoàn tất. ZIP portable dự kiến 313 file và đang chờ tạo/verify.


Round 34 package close: report-only validator 6/6 PASS; HTML browser QA PASS; portable package contains 313 files, ZIP CRC and every member byte count/SHA-256 verified. Outer SHA-256 and manifest are in `MANIFEST-GOI.json`. Report QA is not ClinicAI QA. Full source audit remains incomplete.


## Round 35 — 20/10/2026, v0.58 tích hợp tĩnh

Không thêm ID mới. Mở rộng FIN-002 (lịch sử phiếu kho NHAP/KIEM giới hạn 100/location, không có completeness trong API/UI) và API-002 (clinical status endpoint thiếu location predicate; response có tên/mã và metadata trạng thái, không có SOAP). Worker/event/POS review được dedupe vào findings hiện hữu; ghi hai held observations về mất advisory session cho day-tep và retry POS trước khi SENT persistence. Low-stock threshold tiếp tục held vì chưa có contract physical vs available-to-promise/unit. Tất cả tests chỉ được đọc, không chạy; không app/API/DB/provider/prod. Full source audit vẫn chưa xong. Coverage: `blocks/round35.coverage.json`.


Round 35 report QA: build v0.58 hoàn tất; report validator PASS 6/6; browser QA PASS (192 finding cards, 2.890 ledger rows, desktop/mobile no overflow, search/print, no page errors/external requests). HTML SHA-256 `4442e4f74ee0808684fa6b8a3ae9f1d05c1f6fb63f29e6501f61cf186c0f3d79`. Đây là QA của báo cáo, không phải ứng dụng. Gói ZIP đang chờ rebuild/verification. Full source audit vẫn mở.


Round 35 package verification: ZIP contains 315 audit files; CRC, expected members, byte counts and member SHA-256 pass. Outer SHA-256 and manifest are recorded in `MANIFEST-GOI.json`. Full source audit remains incomplete.

## Round 36 — 20/10/2026, exact-main static review

- Round 36 mở rộng FIN-003, FIN-005, FE-023, INF-021; không tạo ID mới. Inactive permission-preset fallback được giữ held vì product contract chưa rõ; không thấy bypass phân quyền mới trong lát settings.
- Đã trace targeted các luồng thu ngân thêm vật tư/giao dịch, UI unknown-write delete/restore/checkout, preset/quyền settings và tạo phòng; exact hashes/ranges ở `blocks/round36.coverage.json`. Tests read-not-run; không truy cập app/API/DB/provider/production/secrets/PHI.
- Coverage ledger: 855 read, 483 traced, 1040 scanned, 504 inventoried, 8 excluded (2.890 paths); đây không phải behavior coverage. Full source audit chưa xong. Report v0.59 validator 6/6, browser QA PASS; HTML SHA-256 `ead9a77e29ed3293019df15091ac72c1df31ad72fb1fcf3d08812ec53837c65d`. ZIP v0.59 cuối cùng đã verify 318 files; CRC, member set và SHA-256 đúng, outer SHA ở MANIFEST-GOI.json.

## 2026-10-20 08:34 +07 — Round36 evidence correction

Bổ sung exact-main evidence cho INF-021: create_room commit trước audit; UI giữ form khi request lỗi. Cùng tên sau retry chỉ ghi nhận là suy luận có điều kiện, chưa tái hiện. Cập nhật coverage ledger (2,890 paths; 484 traced, 1,039 scanned), build HTML và report-only QA PASS (validator 6/6, browser). SHA HTML f1e43f6847123102ee32bbd3971e401bd2aaa89e9fe8749b2cae36654a26b0e9. ZIP đang chờ build lại. Không sửa source/app; không chạy ClinicAI tests.

## Round 37 — 20/10/2026
Exact-main review at SHA 956ba4f236b1c92f1280d2097018c199e90ce8c7 using git show because checkout HEAD changed. Added CLIN-054 for V5-probe print fallback; extended INF-007, FIN-005, SEC-017 and API-007; reconfirmed DB-006. Refund date, VOID→REFUND and tenant lifecycle remain held. Tests read, not run; no app/API/DB/prod/secrets/PHI access. Coverage: blocks/round37.coverage.json.

## Round 38 — 20/10/2026
Exact-main static review on SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Added CLIN-055 for stale valid NEW/RETURN state on booking after a failed/pending service-history lookup; extended SEC-027 to the service-history metadata route. Pharmacy sale vs inventory remains held pending an explicit owner policy; no new finding. Tests read-not-run, no runtime/API/DB/provider/prod/secrets/PHI. Exact ranges and hashes in `blocks/round38.coverage.json`. Full source audit remains incomplete.

## Round 38 report QA and package close

HTML v0.61 report-only validation passed 6/6; browser QA passed at desktop 1280px and mobile 375px with 194 cards, 2,890 ledger rows, no overflow, page error or external request. SHA-256 `19d474b56243f207192e2d8e064139872f31e977da5bb4fb27047eb46200f96b`. This validates the audit report, not ClinicAI. ZIP packaging/verification is the remaining closeout step. Full source audit remains incomplete.

## Round 39 — 20/10/2026

Exact-main static review on SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Added FIN-018 (conditional concurrent duplicate company profile) and extended FE-004, FE-022, SEC-025. Held service-order assignment, roster clinical competency and hidden-company reuse semantics as policy questions. Tests read-not-run; no ClinicAI runtime/API/DB/provider/prod/secrets/PHI. Report v0.62 validator 6/6 and browser QA passed; 324-file audit-only ZIP passed member/CRC/size/SHA verification. Outer ZIP SHA-256 is in MANIFEST-GOI.json; full source audit remains incomplete. Coverage: `blocks/round39.coverage.json`.

## Round 40 — 20/10/2026

Read-only exact-main review on `956ba4f236b1c92f1280d2097018c199e90ce8c7`. INF-008 extended to the regular migration runner: `apply-pending-migrations.sh` wraps migration+ledger in BEGIN/COMMIT, while pinned structural scan found 23 migrations with standalone transaction control. An internal COMMIT can end the wrapper before the ledger insert, creating conditional ledger drift/replay after interruption. No replay damage or production incident was reproduced. No DB/tests/runtime/deploy. v0.63 report QA/package pending; full source audit remains incomplete. Coverage: `blocks/round40.coverage.json`.

Round 40 report QA: v0.63 passed validator 6/6 and browser QA at desktop 1280/mobile 375; 195 cards, 2,890 ledger rows, no page errors/external requests. Report SHA-256 `5d304569c70831921ebc2eaa841a86bd770e3fa0b484849743f48e0431ec82ee`. 326-file audit-only ZIP passed CRC/member/size/per-file SHA verification; outer hash is in MANIFEST-GOI.json. ClinicAI runtime was not tested.

## Round 41 — 20/10/2026

Read-only exact-main review on `956ba4f236b1c92f1280d2097018c199e90ce8c7`. INF-008 extended: 23 transaction-control migrations structurally scanned; 8 migration DML slices traced, including examples that can reapply clinic hours and role/position configuration after a conditional replay. INF-011 extended with provider-accepted-before-SENT retry window; actual POS adapter remains unfinished, no provider or crash injection. CLIN-020 gets a conditional V5 release-scope policy hold. No new finding ID; risk register remains 195. No ClinicAI test/runtime/DB/API/provider/production access. See `blocks/round41.coverage.json`.

Report v0.64 report-only QA PASS: validator 6/6; desktop 1280px/mobile 375px, 195 finding cards and 2,890 ledger rows; search/print pass, no overflow/page errors/external requests. HTML SHA-256 `f0d78af9bbd2e5a153914a2ec6e2069b2d0683b49bcde63c00335efe84cd5984` (checked 2026-10-20T02:15:01.872Z). This validates only the offline report, not ClinicAI. The 329-file audit-only ZIP passed integrity verification; outer digest is in MANIFEST-GOI.json.


## Round 42 report QA — 20/10/2026

Report v0.65 report-only QA PASS: validator 6/6; desktop 1280px/mobile 375px, 195 finding cards, 2,890 ledger rows; search/print pass, no overflow/page errors/external requests. HTML SHA-256 `266d0ad254e9b1c0a45166b88200d4cfa02ce3c6db55d9cb1ae8e50a13461f06` (checked 2026-10-20T02:25:25.508Z). This validates only the offline report, not ClinicAI. ZIP audit-only v0.65 đã verify 332 file; CRC, member set, byte count và per-file SHA-256 đạt; outer digest nằm trong MANIFEST-GOI.json. Full source audit chưa hoàn tất.


## Round 43 — 20/10/2026, v0.66 integration in progress

Read-only exact-main review on 956ba4f236b1c92f1280d2097018c199e90ce8c7. Added conditional MEDIUM OPS-011 after independent security review: test-customer cleanup lacks a server-side test-only boundary; permission, preview, XOA, open-visit check and manual archive are mitigating controls. Extended CLIN-053 for possible duplicate reminder marker only if POST is retried after ambiguous outcome without an idempotency key. Telegram, quote, clinical/BFF and operations/finance slices produced no distinct finding after dedup. Tests read-not-run; no app/API/DB/provider/VPS/production/secrets/PHI. Full source audit remains incomplete. Exact ranges/hashes: blocks/round43.coverage.json. Report/package QA pending.


## Round 43 — v0.66 report-only QA

Validator 6/6 PASS; browser QA PASS at desktop 1280px and mobile 375px; 196 finding cards, 2,890 ledger rows, search/print pass, no overflow, page errors or external requests. HTML SHA-256 f7fcb66a10bf9e4aea6d664decd016ba34c10bdee16b6b756f28dee64850306c (checked 2026-10-20T02:36:22.806Z). This validates the offline report only, not ClinicAI. Final audit-only ZIP verification remains pending; full source audit remains incomplete.


## Round 43 — v0.66 package close

Audit-only ZIP contains 334 files; CRC, exact member set, byte count, per-file SHA-256 and outer SHA-256 verification passed. Canonical outer digest is in MANIFEST-GOI.json. The package contains audit artifacts only, not source repository/Git history, secrets or patient data. Full source audit remains incomplete.


## Round 44 — 20/10/2026, clinical/auth/finance/config/recovery

Exact-main SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Thêm CLIN-056 (đơn có thể bỏ qua thay đổi catalog ID trong nhánh draft) và SEC-036 (TKYK có thể chốt kết quả cùng clinic ngoài phạm vi bác sĩ được phân); mức/điều kiện/giới hạn trong PHAT-HIEN.json. INF-006 được bổ sung mismatch cloud-PITR manifest với deployment self-hosted và giới hạn của restore drill; INF-021 được bổ sung các writer config commit trước audit. Auth/staff/finance dedupe; config parent-child và một số TOCTOU giữ ở mức candidate. 20 full-file reads hash/line-checked; tests đọc-not-run; không runtime/app/API/DB/provider/VPS/production/secrets/PHI. Xem `blocks/round44.md` và `blocks/round44.coverage.json`. Full source audit chưa xong.

Round 44 — report-only QA, 20/10/2026

v0.67 validator PASS 6/6. Browser QA PASS: 198 finding cards, 2,890 ledger rows, desktop 1280px/mobile 375px, search and print pass, no page errors or external requests. HTML SHA-256 `8c41a4e58867270822ccf846a1806594814d82af9ecae1550b0a07734f9a1ab4` (checked 2026-10-20T02:48:18.335Z). This verifies the offline report only, not ClinicAI behavior; accessibility was not certified. The 336-file audit-only ZIP passed CRC, exact member-set, byte-count, per-file SHA-256 and outer SHA-256 verification; outer SHA-256 is in the adjacent `MANIFEST-GOI.json`. Full source audit remains incomplete.


## Round 45 — 20/10/2026, v0.68 tích hợp tĩnh

Exact-main static review at SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Added FIN-019, INF-027, INF-028, OPS-012, SEC-037; expanded INF-006/SEC-011/SEC-016/SEC-018/SEC-027. Worker retry/fairness/POS deduplicate with existing findings; monitor self-health and TKYK file-write scope remain held. See `blocks/round45.coverage.json`. Tests read-not-run; no app/API/DB/provider/VPS/production/secrets/PHI. Full audit incomplete; report/package QA pending.


Round 45 report-only QA final after coverage refresh: v0.68 validator PASS 6/6; browser PASS desktop 1280/mobile 375, 203 finding cards, 2,890 ledger rows, search/print pass, no page errors or external requests. HTML SHA-256 `8de4ad1721b1f2a6fc2b984b7eaf710022ca346c1d4004fce5f597e46c7bed00` (checked 2026-10-20T03:05:01.348Z). This validates only the offline report, not ClinicAI; accessibility not certified. ZIP final verification pending. Full source audit remains incomplete.


Round 45 package close: v0.68 audit-only ZIP contains 338 files; CRC, exact member set, byte count, per-file SHA-256 and outer SHA-256 verified. Outer digest is in adjacent `MANIFEST-GOI.json`; full source audit remains incomplete.


Round 45 package final: v0.68 audit-only ZIP has 338 files and passes CRC, exact member set, byte count, per-file SHA-256 and outer SHA-256. The outer digest is stored in adjacent `MANIFEST-GOI.json`; state/handoff are included in the verified package. Full source audit remains incomplete.


## Round 46 — 20/10/2026, v0.69 integration

Read-only exact-main review at SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Added FE-027 (stale inactive-location cookie recovery) and CLIN-057 (reschedule replay can duplicate history/events); extended FE-023 to password-reset forms and SEC-027 to the doctor-assignment worklist PII endpoint. Payment/refund review deduplicated with existing findings; cashier backlog, unassigned booking capacity and 24:30 hours validation remain held. Full-file reads and targeted traces are in `blocks/round46.coverage.json`. Tests read-not-run; no ClinicAI runtime/API/DB/provider/VPS/production/secrets/PHI. Full audit remains incomplete. Report-only QA and package refresh pending.


## Round 46 — v0.69 report-only QA — 20/10/2026

Validator PASS 6/6; browser QA PASS: desktop 1280px/mobile 375px, 205 finding cards, 2,890 ledger rows, search/print pass, no overflow, page errors or external requests. HTML SHA-256 `ad5582586e36b8549bac971a21f097827bf748a0c3b4fa4b4fb93446b0283753` (checked 2026-10-20T03:15:05.744Z). This verifies the offline audit report only, not ClinicAI; accessibility is not certified. Audit-only ZIP refresh/verification pending. Full source audit remains incomplete.


Round 46 package close: v0.69 audit-only ZIP verified with 341 files; CRC, exact member set, byte count, per-file SHA-256 and outer SHA-256 passed. Outer digest is in adjacent `MANIFEST-GOI.json`. This closeout record was included in the final package rebuild, which was reverified after state and handoff updates. Full source audit remains incomplete.


## Round 47 — 20/10/2026, v0.70 integration

Static exact-main review at SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Added CLIN-058 and FE-028; extended FE-002, FE-023, FE-026, CLIN-057, FIN-003, SEC-011 and INF-027. Impossible roster date, inactive external-DB helper, GoTrue wildcard redirect, room-config partial-save and ambiguous UI outcomes remain held. Related tests were read-not-run; no ClinicAI runtime/API/DB/provider/VPS/production/secrets/PHI was accessed. Exact coverage is in `blocks/round47.coverage.json`; full source audit remains incomplete. v0.72 report-only QA passed (validator 6/6 and desktop/mobile browser check); 350-file audit-only ZIP passed CRC/member/count/SHA verification.

Report v0.70 QA hoàn tất: validator 6/6; browser desktop 1280/mobile 375, 207 cards, 2,890 ledger rows, search/print pass, không overflow/page errors/external requests. Report SHA-256 `258bfd71ae7046623e02ed61eff79200e6f24111e07a99fbb47d5cdf3dc59acc`. Đây không phải ClinicAI QA; package refresh pending.

Package v0.70 final: 344 audit-only files verified (CRC, exact members, bytes, per-file SHA-256, outer SHA-256); digest lưu ở `MANIFEST-GOI.json`. Full source audit remains incomplete.


## Round 48 — 20/10/2026, v0.71 integration

Static exact-main review at SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. No new finding ID; extended FE-002 with the shared treatment-plan chip's stale batch-key behavior and SEC-011 with the chip read endpoint's same-clinic object-assignment gap. Tests read-not-run; no ClinicAI runtime/API/DB/provider/VPS/production/secrets/PHI was accessed. Exact coverage is in `blocks/round48.coverage.json`; full source audit remains incomplete. v0.71 report-only QA passed (validator 6/6 and desktop/mobile browser check); 347-file audit-only ZIP passed CRC/member/count/SHA verification.


## Round 49 — 20/10/2026, v0.72 integration

Static exact-main review at SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Added FIN-020: the nullable split-payment CHECK/trigger does not fully reject one-sided NULL rows for privileged DB writers; the current service path validates both legs. No new runtime/production incident is claimed. Related tests were read-not-run; no ClinicAI runtime/API/DB/provider/VPS/production/secrets/PHI was accessed. Exact coverage is in `blocks/round49.coverage.json`; full source audit remains incomplete. v0.72 report-only QA passed (validator 6/6 and desktop/mobile browser check); 350-file audit-only ZIP passed CRC/member/count/SHA verification.


## Round 50 — 20/10/2026, v0.73 integration

Static exact-main review at SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Added OPS-013: roster-history replay may order a concurrent snapshot and roster delta by xid rather than commit visibility; no runtime/production occurrence is claimed. Related tests were read-not-run; no ClinicAI runtime/API/DB/provider/VPS/production/secrets/PHI was accessed. Exact ranges and PostgreSQL reference are in `blocks/round50.coverage.json`; full source audit remains incomplete. Report-only QA/package refresh pending.


## Round 51 — 20/10/2026, v0.74 integration

Static exact-main review at SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Added CLIN-059: simultaneous reschedules to different targets can both pass while status remains eligible, allowing a later write to overwrite the earlier target and recording stale from-slot history. No runtime/production occurrence is claimed. Related tests were read-not-run; no ClinicAI runtime/API/DB/provider/VPS/production/secrets/PHI was accessed. Exact ranges are in `blocks/round51.coverage.json`; full source audit remains incomplete. Report-only QA/package refresh pending.


## Round 52 — 20/10/2026, v0.75 integration

Static exact-main review at SHA 956ba4f236b1c92f1280d2097018c199e90ce8c7. Added CLIN-060: in-chart switch is allowed after fee payment; default fee recalculates from current service type while bill source remains stable per visit, and covered sources are removed without a delta adjustment. No payment/DB/runtime/production outcome reproduced. Tests read-not-run. Exact ranges in blocks/round52.coverage.json; full source audit incomplete. Report-only QA/package refresh pending.


## Round 53 — 20/10/2026, v0.76 integration

Static exact-main review at SHA 956ba4f236b1c92f1280d2097018c199e90ce8c7. Closed the visit_gate_rule lead from CLAUDE-HANDOFF.md: added OPS-014. With only_when_other_staff=TRUE (required by the seed), blocks() passes when target_staff_id is None, and no caller of gate_enforce supplies it; the old-flow API cannot block. New-flow visits use luat_bac_si_bat_buoc at booking time by documented intent, so no claim that new-flow ignores all rules. Production rows unknown. Tests read-not-run. Exact ranges in blocks/round53.coverage.json; full source audit incomplete. v0.76 report-only QA passed (validator 6/6; desktop/mobile browser, 212 cards, no overflow/page errors/external requests); 364-file audit-only ZIP passed CRC/member/count/SHA verification. Added BAO-CAO-DE-HIEU.html (plain-language report) after the reader feedback that the technical report was hard for non-technical viewers.


## Đợt đọc toàn bộ mã nguồn lần 2 — 20/10/2026 (BAO-CAO-DAY-DU.html)

43 phần (25 mã nguồn S01–S25, 18 test T01–T18) từ danh sách 1.626 tệp chưa đọc trọn, chỉ từ Git blob SHA 956ba4f2. 25 phần S và T02, T08 do agent đọc (có công cụ, tra thêm tệp ngoài danh sách); S21 và T01, T03–T07, T09–T18 đọc một lượt qua Messages API Sonnet 5.5 không công cụ (bị cắt giữa chừng vì giới hạn hạn mức nên chuyển sang API). 455 phát hiện thô, 1.921/1.922 dẫn chứng dòng khớp tệp ở SHA ghim; loại trùng bằng API còn 333 mục mới (OPS-014 của vòng 53 nằm trong 212 mục cũ+1). Chưa xác minh độc lập lần hai; chưa chạy gì; không đọc secrets hay PHI. Dữ liệu gốc: dot-2-doc-toan-bo/. Báo cáo: BAO-CAO-DAY-DU.html (545 mục). Các mục mới chưa nhập vào PHAT-HIEN.json và BAO-CAO.html; full_source_audit_complete vẫn false.


## Đối chiếu prod — 20/10/2026

Lệnh chỉ đọc qua ssh (người dùng duyệt): /home/clinicai/clinicai HEAD = 956ba4f2, working tree sạch; ảnh clinicai-api:prod dựng 19/10 13:11 và clinicai-dashboard:prod 13:12 (+07), container khởi động ngay sau đó, sau commit cuối 13:04. Kết luận: bản đã audit trùng bản prod. Chưa kiểm schema DB thật, .env, dữ liệu, Caddy/OS. Báo cáo chỉ kết luận về prod; staging/local ngoài phạm vi.


## Đo thực tế prod — 20/10/2026

Hai lần chạy lệnh chỉ đọc trên VPS prod (người dùng duyệt từng lệnh; PGOPTIONS ép database read-only; không in giá trị bí mật; không đọc dữ liệu bệnh nhân). Kết quả: prod-thuc-te/. API Opus 5.5 đối chiếu dữ kiện với 545 mục. Đã sửa tay một lỗi của API: `clinicai_exception` là cảnh báo lỗi nghiệp vụ đã xử lý (main.py:594), không phải lỗi chưa xử lý; bản gốc của API giữ ở prod-analysis.api-goc.json. Dữ kiện chính: 0 dòng ở visit_gate_rule và luat_bac_si_bat_buoc (luật thứ tự bắt buộc chưa từng bật); 373/373 migration đã áp; 4 bảng public không bật RLS; token Telegram và Zalo giống nhau giữa prod và staging, các khoá hệ thống khác nhau; Ubuntu 25.04 chờ reboot; sao lưu ngoài máy hằng ngày 07:00, mới nhất 20/10.


## Codex xác minh độc lập 40 mục mức cao — 20/10/2026

Codex (đọc blob 956ba4f2, chỉ đọc) trả 4 tệp codex-tung-phan/KET-QUA-CODEX-1..4.json: 11 DUNG, 28 DUNG_MOT_PHAN, 0 BAC_BO, 1 KHONG_XAC_DINH (DB-001: có migration thu hồi EXECUTE, trạng thái ACL thật chưa đo). 21 mục được đánh giá mức vừa hoặc không áp dụng nên hạ HIGH→MEDIUM trong BAO-CAO-DAY-DU.html (còn 19 HIGH). Điểm đáng chú ý: INF-029 (không tự bật lại) sai một phần vì có restart unless-stopped, chỉ đúng phần container unhealthy không được restart; SEC-020 và SEC-040 phần lớn là quyết định mở quyền có chủ ý của sản phẩm; nhiều mục chỉ đúng với đường legacy hoặc khi cấu hình không có chốt. Chưa sửa PHAT-HIEN.json và BAO-CAO.html (báo cáo kỹ thuật cũ vẫn ghi mức ban đầu).
