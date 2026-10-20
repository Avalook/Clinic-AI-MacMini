# Round 14 — RLS, grants và SECURITY DEFINER (static)

- Snapshot nguồn: /tmp/clinicai-audit-main-956ba4f2
- SHA ghim: 956ba4f236b1c92f1280d2097018c199e90ce8c7
- Phạm vi: migration, RLS policies, grants, security-definer helpers và test SQL liên quan tới tenant/data boundaries.
- Kết quả: không thêm candidate riêng; view issue đã có trong ledger là SEC-017.

## Kết quả rà soát

capability_grant bật RLS và có policy SELECT cho authenticated chỉ khi clinic_id thuộc current_clinic_ids() (20260923000003_capability.sql:91-112). Cùng migration tạo v_quyen_hieu_luc không kèm security_invoker, không lọc tenant, rồi grant SELECT cho authenticated (dòng 172-188). PostgreSQL mặc định áp quyền và RLS theo chủ sở hữu view; security_invoker chuyển kiểm tra sang người gọi ([PostgreSQL CREATE VIEW](https://www.postgresql.org/docs/current/sql-createview.html)). Đây là cùng rủi ro metadata liên clinic đã ghi nhận ở SEC-017, không phải finding mới.

v_quyen_thuc_te cũng được grant cho authenticated và truy vấn lịch, vị trí, phòng, node và quyền đã cấp mà không tenant predicate (20260929000001_doi_nguoi_trong_ca.sql:168-229). Migration hardening cuối revoke EXECUTE khỏi PUBLIC/anon trên mọi function public, sau đó chỉ whitelist một nhóm helper authenticated; hai helper tra quyền theo lịch/vị trí không nằm trong danh sách grant (20261019100000_harden_public_function_acl.sql:9-24). Điều này tạo chặn ACL cho đường gọi view qua authenticated nếu migration đã áp; không biến định nghĩa view thành tenant-safe. Mở lại EXECUTE cần xem lại quyền view owner, tenant predicates và quyền các bảng nền. Phần này cũng thuộc SEC-017.

Các identity helper current_staff_id(), current_clinic_ids() và current_clinic_roles(uuid) giới hạn theo auth.uid() và membership đang hoạt động; chúng dùng SECURITY DEFINER, SET search_path = public, pg_temp, và bị revoke khỏi PUBLIC trước khi cấp EXECUTE rõ cho authenticated/service_role (20260730000003_multi_tenant_foundation.sql:221-267). Các policy tenant tổng quát dùng helper này; policy TKYK là restrictive và kiểm liên kết bác sĩ trên nhóm bảng y khoa (20260730000004_tenant_scoped_rls.sql:150-210; 20260915000021_thu_ky_rls_theo_bac_si.sql:16-117). Rà soát này không đưa ra finding mới trùng với SEC-007, SEC-011 hoặc SEC-019; các quyền/function đã nêu ở đó vẫn thuộc các finding hiện có.

Migration 20261019120000_restrict_stock_postgrest_reads.sql bỏ policy SELECT và thu hồi quyền anon/authenticated trên 11 bảng sổ kho/vật tư, chỉ cấp SELECT cho service_role (dòng 8-47). Vì vậy candidate cũ về đọc trực tiếp phieu_kho không còn đúng với exact-main. Các danh mục thuốc/barcode không nằm trong migration thu hẹp này; đó là metadata sản phẩm, không phải sổ tồn/phiếu kho trong phạm vi kiểm tra này.

Init SQL khai báo service_role BYPASSRLS; migration ACL cũng ghi FastAPI kết nối bằng database owner (docker/supabase/init/01-vai-va-extension.sql:30-39; 20261019100000_harden_public_function_acl.sql:5-6). Do đó RLS bảo vệ các vai PostgREST, còn backend phải giữ tenant predicates/authorization riêng. Không thấy migration nào dùng FORCE ROW LEVEL SECURITY. Đây phù hợp với vai trò owner/service được thiết kế để bypass, nhưng không tạo ranh giới cô lập cho truy vấn backend thiếu predicate.

## Đối chiếu và giới hạn

- SEC-017: trùng trực tiếp về hai view quyền; không tạo finding thứ hai.
- SEC-007, SEC-011, SEC-019, SEC-020 và DB-001/002/007: đã đối chiếu; không tạo finding trùng. DB-001 lifecycle RPCs được migration ACL cuối giới hạn service_role; các finding còn lại có trigger/phạm vi khác.
- Rà soát tĩnh trên snapshot ghim; không truy vấn database, không kiểm tra owner/BYPASSRLS thực tế ở production, không chạy test, không truy cập VPS, secrets hoặc PHI.
- Audit này không xác nhận migration đã áp dụng trên production. Kết luận view owner/RLS là phân tích theo định nghĩa PostgreSQL và ownership/ACL được mô tả trong mã nguồn.
