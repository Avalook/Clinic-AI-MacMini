# Frontend round 3 — kiểm tra độc lập FE-006

**Reference:** main pinned `956ba4f236b1c92f1280d2097018c199e90ce8c7`.
**Worktree:** `/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini`.
**Trạng thái:** đã chốt static trace candidate FE-006; không chạy browser/DB tests trong khối này. Không sửa app, tests, PHAT-HIEN hay HTML.

## Kết luận FE-006

**Giữ candidate MEDIUM · confirmed_static:** Một lần gọi ghi “đã xem” thất bại không được thử lại trong vòng đời component đang mở, dù danh sách kết quả được SSE làm mới và vẫn trả `da_xem_luc = null`.

Đây là thiếu ghi nhận một lần xem có thật, **không phải đánh dấu sai thành đã xem**. Không có chứng cứ từ đợt này cho rằng nó tự đóng lượt hoặc tự bỏ safety gate; không suy diễn hậu quả đó.

### Trigger cụ thể

1. Bác sĩ / thư ký / bác sĩ siêu âm mở **khối 2** của phiếu khám hiện hành. Có chỉ định thuộc lần đang hiển thị, `ket_qua_trang_thai = CO_KET_QUA`, `da_xem_luc = null`, với ít nhất một phiếu READY ở backend.
2. Component hiển thị nội dung đã được GET gộp từ `/api/phieu-kham?visit_id=...`, rồi tự gọi `/api/phieu?xem=<orderId>` để ghi bằng chứng đã xem.
3. Riêng lần request đó mất mạng **trước khi backend commit**, hoặc trả lỗi tạm thời 5xx. GET danh sách kết quả còn tiếp tục được.
4. Sau SSE `form_instance`/`service_order`/`tep_ket_qua`, hoặc catch-up tab, backend vẫn trả `da_xem_luc = null`. Effect chạy lại nhưng bỏ qua ID đã nằm trong Set, không retry.

Nếu response chỉ thất lạc SAU commit, database có thể đã ghi thành công; đó không phải tiền đề của lỗi này. Nếu actor không thuộc vai backend cho phép ghi đã xem, không coi việc không ghi là lỗi.

### Đường code và guard

| Điểm | Nguồn main, dòng 1-based | Bằng chứng |
|---|---|---|
| Live caller | `ban-kham/BanKham.tsx:1434–1450` | `PHIEU_V5 = true` (`:157`); Bàn khám render `PhieuKhamLuot key={dong.visit_id}`. Đây là path đang bật. |
| Mở khối | `_lam-viec/phieu-kham/PhieuKham.tsx:457–464` | Khối 2 render `KetQuaChiDinh` cho CLS/thủ thuật. Giữ khối đang mở và cùng kiểu component thì props ds mới không tạo ref mới. `NganGap.tsx:92–94` chỉ hidden children, gập/mở thẻ KHÔNG tạo Set mới. |
| Set lifetime | `KetQuaChiDinh.tsx:256` | `useRef(new Set<string>())` sống qua render; không có delete/clear trong module. Remount mới tạo Set sạch. |
| Gating frontend | `KetQuaChiDinh.tsx:275–283` | Chỉ xét chỉ định của lần đang hiển thị, CO_KET_QUA và chưa có da_xem_luc. `add` xảy ra TRƯỚC request. |
| Không quan sát kết quả | `KetQuaChiDinh.tsx:73–76` | Fire-and-forget fetch; không xem response.ok; rejection bị nuốt. Không rollback Set, retry, hoặc hiển thị cảnh báo. |
| Refresh danh sách | `PhieuKhamLuot.tsx:210–223,264–268` | `napKetQua` cập nhật state `ketQua`; `useNgheBang(BANG_KET_QUA, napKetQua)` với bảng :81. Không remount KetQuaChiDinh khi chỉ props data đổi. |
| Proxy | `app/api/phieu/route.ts:38–46` | UUID validation → proxy GET `/api/v1/phieu/xem/{id}`, vẫn dùng identity của request. |
| Router | `routers/phieu.py:187–196` | `get_current_identity` → FormEngineService.xem_ket_qua. |
| Vai được đọc | `form_engine_service.py:64–77,272–273` | DOC_KET_QUA gồm DOCTOR/TKYK/ULTRASOUND_DOCTOR/NURSE_ULTRASOUND/TRUONG_CA/MANAGEMENT; endpoint hỏi identity.co_vai. |
| Vai tính đã xem | `form_engine_service.py:298` + :75–77 | Chỉ vai_goc DOCTOR, ULTRASOUND_DOCTOR, TKYK; không suy vai hiển thị/capability thành chuyên môn. |
| Ghi thật | `form_engine_service.py:275–321` | Chỉ có READY phiếu và actor đúng vai mới UPDATE `da_xem_ket_qua_luc IS NULL`, emit result.viewed trong transaction. Failed request không có write giả. |

### Phạm vi và hậu quả đã chứng minh

- Backend có thể tiếp tục biểu diễn chưa xem dù người có trách nhiệm vừa nhìn bản tóm tắt. Nguồn dữ liệu và trải nghiệm bị lệch; không có thông báo tại chỗ cho việc ghi bằng chứng thất bại.
- Lỗi **không vĩnh viễn**: đổi hẳn khối của phiếu để component bị gỡ, đổi khách rồi quay lại hoặc reload làm remount và có thể gửi lại. Vì vậy mức MEDIUM phù hợp hơn HIGH.
- Không chứng minh doctor thực sự đọc hiểu nội dung; “đã xem” hiện chỉ đo điều kiện hiển thị theo quy tắc sản phẩm đã chốt.
- Chưa chạy component fault injection cho FE-006. Tất cả là static trace của main pinned.

### Hướng sửa/tiêu chí kiểm chứng đề xuất

Tách pending khỏi confirmed cho việc ghi bằng chứng. Chỉ giữ ID trong tập confirmed sau response thành công; lỗi mạng/5xx xoá pending hoặc đưa vào retry hữu hạn/backoff. Không retry vô hạn 403; không đánh dấu UI thành công khi backend chưa xác nhận. Nếu quy trình yêu cầu xác nhận đọc theo **phiên bản kết quả**, cần contract riêng; không lén dùng order ID làm version.

Test tối thiểu: mount một kết quả READY/da_xem_luc null; request xem đầu tiên bị chặn trước server/500; trả ds mới vẫn null qua props giống SSE; chờ retry và xác nhận request thứ hai được gửi; response success thì các refresh sau không gửi lặp. Thêm actor không thuộc XEM_LA_DA_XEM không được ghi thật. Theo dõi database/result.viewed để phân biệt request đã commit nhưng mất response.

## Kết quả khác của round3 — không thành finding mới

- **Bác false positive cache ultrasound FE:** `app/api/ultrasound/image/route.ts:135` có private,max-age=300, nhưng `lib/route-da-tat.ts:15` loại route ở proxy và không có caller frontend live. Không được nói đường này đang rò PHI ở UI hiện tại. Backend endpoint trực tiếp là phạm vi security riêng, chưa suy exposure qua Caddy.
- **Bác stale XemPhieuKetQua như active finding:** component chỉ fetch một lần nhưng caller nằm ChiDinhPanel, render chỉ khi `!PHIEU_V5` (`BanKham.tsx:689–704`), trong khi PHIEU_V5 true. Path hiện hành là KetQuaChiDinh nhận summary props mới.
- **Điểm tốt correction:** live summary `KetQuaChiDinh.tsx:135` có `ban_thu`; :325–327 ghi rõ “Đang sửa lại — bản dưới vẫn chính thức”. `PhieuKetQua.tsx:301–309` flush trước hoàn tất, :357–367 nhận toàn bộ bản canonical khi mở sửa; :442–447 chỉ chuyển mẫu khi flush thành công. Không suy mọi correction đều stale.
- **Thiếu provenance khi in:** print fetch-once, không version/asof trong contract đã được root đọc. Ghi nhận đây là design gap về bản in có nguồn/phiên bản, không gắn nhãn bug mới hay duplicate.
- **Điểm tốt PHI stream/cache:** live tệp `/api/cskh/ket-qua/{id}/noi-dung` xác thực mỗi request, private/no-store, Range streaming, nosniff (:29–72). Không gom private cache của route retired thành đánh giá tất cả file.
- **Điểm tốt export:** `xuat-bang-excel.ts:3–7` neutralize =/+/@ và chuỗi - không phải số; CSV quotes escaped; :60–65 revoke Blob URL. Không thấy formula injection từ helper này.
- **Session/cache limits:** server lookup `bo-nho-tam` bắt buộc clinicId + TTL60s và không cache empty; client `doc-gop` chỉ in-flight, xoá khi settle. Chưa có bằng chứng rò chéo tenant từ hai helper. UI cũ ở tab khác khi đổi người/cơ sở vẫn là giả thuyết cần browser lifecycle test; không đưa thành kết luận lỗi.

Lưu ý kiểm chứng visibility: `NganGap` giữ children mounted khi hidden; trigger FE-006 ở trên chủ động giới hạn trường hợp thẻ đang mở và có thể nhìn thấy. Không dùng mount làm bằng chứng người đọc thực sự đã nhìn. Chưa kết luận thêm lỗi false-seen do collapsed UI trong round này.

## Hash bằng chứng FE-006

- `src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/KetQuaChiDinh.tsx` — `77076bf818e5c983d1ed8fe5f6839e976358d095c282570a6ac0416222d2da1d`
- `src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx` — `e6967fd22fff5f3b6ee5b2dd45b150eb3936c9650a07e88b1b360012192d3c62`
- `src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/PhieuKham.tsx` — `46818071ec44ffc90ba32ab8c4befd81b18861a803aef9361e64e27c9630896a`
- `src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx` — `ccd860a32d945adcf57c08cf0c409a4860a618819b223a02a34fd9e491670c24`
- `src/dashboard/app/api/phieu/route.ts` — `a54fcb14115e7dcc965b33e55b73e95332dee0441f681cacce8f17de565c0f00`
- `src/clinicai/api/v1/routers/phieu.py` — `4072fa5df01b9b056ff42fa367aceb3519edda44fe4826133d030cdb83111a3f`
- `src/clinicai/services/form_engine_service.py` — `c1f64f9466aa58e828c6d011cbf1a894e10e77129828e0a32ed5cad65e6627d0`

## Coverage và việc còn lại

File `frontend-round3.coverage.json` ghi hash, vùng đọc và giới hạn từng file. `traced` nghĩa đã theo đường code được nêu, KHÔNG có nghĩa đọc thủ công hết mọi dòng của file. Không có runtime/browser test mới trong round này. Chưa kiểm đầy đủ cache HTTP thực ở Next/Caddy/bfcache, tab khác đổi identity, ảnh/video sau logout trên thiết bị thật, toàn bộ endpoints export, tất cả legacy code route guards. Root quyết định có tích hợp candidate vào canonical findings hay không.
