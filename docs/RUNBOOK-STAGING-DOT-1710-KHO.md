# Runbook lên STAGING — đợt `dot/1710-kho` (soạn 17/10/2026, CHƯA chạy)

Đợt gồm **hai** PR kho thuốc, gộp ở nhánh `dot/1710-kho` (merge commit, tách từ `main` @ `25140241`):

| PR | Việc | Migration |
|---|---|---|
| #499 (A) | Quy đổi hộp ↔ gói LÚC NHẬP: kho chỉ giữ đơn vị bán | `20261017100000_thuoc_quy_doi.sql` |
| #500 (B) | Màn "Thuốc khách trả chờ kiểm": nhập lại bán được / huỷ, quyết một lần | `20261017200000_thuoc_tra_quyet_dinh_xu_ly.sql` |

**KHÔNG gồm:** #495 (bộ mô phỏng, chỉ test), #496 (7 lỗi nhỏ), #497 (chữ cảnh báo lô lệch — **hai cảnh báo nhập của #497
phải gỡ khi gộp, vì sau #499 chúng sai**), #498 (kế hoạch). Muốn đưa #496/#497 cùng đợt thì nói, tôi gộp và chạy lại CI.

**Chỉ STAGING.** Phần prod là runbook riêng, soạn sau khi staging ĐẠT. Lệnh ghi lên VPS **do Tuyền chạy**.

## 0. Điều kiện bắt đầu
- Tuyền duyệt kế hoạch (#498) + hai PR; bốn quyết định đang dùng đề xuất mặc định (bảng riêng cho hệ số · hỏi lại khi lệch >10 lần ·
  quyền `pharmacy.dispense` được bấm Nhập lại/Huỷ · lô mẫu prod nạp lại tồn thật) — chỉnh được trước khi chạy.
- Nhánh `dot/1710-kho` đã được đẩy lên GitHub (chưa đẩy — chờ Quang nói).
- CI máy xanh: **đã xanh 5/5 ở `65c199cb`** (backend 6.493+ đạt). Sau đó chỉ thêm tệp `.md` này (PR chỉ docs không chạy CI).

## 1. Đã diễn tập (local, 17/10, trên bản sao lưu prod 17/10 02:15)
Nạp bản sao lưu vào container tạm (`restore-drill.sh`, 16/16 kiểm đạt), áp **cả hai migration**:
- áp sạch, **không lỗi**; chạy lại lần hai **không lỗi** (idempotent);
- số dòng **không đổi**: `drug_return` 0 · `drug_batch` 162 · `inventory_txn` 255 · `phieu_kho_dong` 0;
- trong giao dịch rồi ROLLBACK, trên lô thật (`DEMO1709-01`, đơn vị "hộp"): bán lại → bán được **+3**, tồn giữ; huỷ → tồn **−3**;
  sửa lần hai bị chặn; huỷ không có dòng DISCARD bị chặn.
- Prod hiện **0 lần khách trả** → màn "Thuốc trả chờ kiểm" sẽ trống cho tới lần trả đầu tiên.
- Container tạm đã xoá kèm volume.

## 2. Lên staging (Tuyền chạy, trên Mac)
Staging chung VPS với prod; script tự dừng trong **giờ khám 7h–21h**. Chạy sau 21h, hoặc khi Tuyền xác nhận phòng khám vắng thì
thêm `CHO_PHEP_GIO_KHAM=1` như dòng thứ hai bên dưới.
```bash
ssh clinic-vps-moi "cd ~/clinicai-staging && ./scripts/deploy-staging.sh dot/1710-kho"
```
```bash
ssh clinic-vps-moi "cd ~/clinicai-staging && CHO_PHEP_GIO_KHAM=1 ./scripts/deploy-staging.sh dot/1710-kho"
```
Áp migration lên DATABASE STAGING (không phải prod), rồi báo lược đồ mới:
```bash
ssh clinic-vps-moi "cd ~/clinicai-staging && CLINIC_DB_CONTAINER=clinicai_stg_db ./scripts/apply-pending-migrations.sh"
```
```bash
ssh clinic-vps-moi "cd ~/clinicai-staging && CLINIC_DB_CONTAINER=clinicai_stg_db ./scripts/apply-pending-migrations.sh --apply"
```
```bash
ssh clinic-vps-moi "docker exec clinicai_stg_db psql -U postgres -c \"NOTIFY pgrst, 'reload schema'\""
```
Kiểm: dải vàng "STAGING" ở đầu trang; hai bảng/cột mới có mặt:
```bash
ssh clinic-vps-moi "docker exec clinicai_stg_db psql -U postgres -d postgres -Atc \"SELECT (SELECT count(*) FROM information_schema.tables WHERE table_name='thuoc_quy_doi'), (SELECT count(*) FROM information_schema.columns WHERE table_name='drug_return' AND column_name='disposition_txn_id')\""
```
Phải ra `1|1`. Đêm 03:30 staging nạp lại từ bản sao prod rồi **tự áp lại** migration của nhánh đang đứng.

## 3. Kịch bản bấm thử cho người thật (đăng nhập tài khoản prod, dữ liệu khách đã che)
**A — quy đổi lúc nhập** (Kho thuốc → Nhập thuốc):
1. **+ Nhập lô** (hoặc Phiếu nhập): thuốc bán theo "gói" (vd *Androgel 1% gói*), đơn vị gõ "hộp", số lượng 6, giá nhập 450000
   → khung "1 hộp = ? gói" hiện; gõ 10 → "= 60 gói" → lưu. Lô mới ở tab Thuốc trong kho: **60 gói**, giá vốn 45.000.
2. Nhập lô thứ hai cùng thuốc, đơn vị "hộp", **không gõ hệ số** → "Đã nhớ lần trước: 1 hộp = 10 gói", lưu được.
3. Gõ hệ số **500** → hiện ô tích "lệch hơn 10 lần"; bấm lưu khi chưa tích → báo lỗi, không có lô mới.
4. Phiếu nhập hai dòng: một dòng "hộp" (đổi), một dòng đúng đơn vị bán (không có khung đổi); một dòng thuốc chưa từng nhập mà bỏ trống
   hệ số → "Dòng N: … 1 hộp = ? gói", **cả phiếu không vào**.
5. Giao thuốc cho khách mua đúng thuốc ấy → **tồn kho trừ đúng** (trước đây không trừ).

**B — thuốc khách trả** (staging chưa có lần trả nào, nên tạo một lần):
6. Cho khách mua thuốc → giao → ghi **khách trả** 2 viên (chọn kết cục tiền như hiện nay).
7. Kho thuốc → **QUẦY** → **Thuốc trả chờ kiểm (N)**: thấy thẻ vừa trả; lượng bán được của lô **chưa** tăng.
8. **Nhập lại bán được** → Xác nhận → thẻ biến mất, lô có lại 2 viên bán được.
9. Một lần trả khác → **Huỷ…** → nút khoá tới khi gõ lý do → Xác nhận huỷ: tồn giảm 2; **Lịch sử kho** có dòng huỷ ghi lý do.
10. Tài khoản chỉ có quyền xem kho: thấy thẻ, không có nút quyết. Điện thoại (375): không tràn ngang.

Lô mẫu `DEMO1709-*` đang tính "hộp" vẫn còn trên staging (bản sao prod) — màn Cấp thuốc / "Đã giao, chưa trừ kho" vẫn thấy cảnh báo lệch
đơn vị ở các lô ấy. Đó là dữ liệu cũ, không phải lỗi của đợt (quyết định #4: nạp lại tồn thật theo đơn vị bán).

## 4. ĐẠT → bước sau
Tuyền báo ĐẠT → Claude soạn runbook prod (sao lưu → diễn tập lại ở đúng SHA → áp → deploy ghim SHA; bài học 30/09: không dùng `origin/main`
giữa soát và deploy). **Không có lệnh prod nào trong tệp này.**

## 5. Hoàn tác staging
Staging chỉ là bản thử: hỏng thì `ssh clinic-vps-moi "cd ~/clinicai-staging && ./scripts/deploy-staging.sh main"` (về main) và
`./scripts/staging-nap-ban-sao.sh` để nạp lại dữ liệu sạch. Hai migration chỉ **thêm** (bảng, cột nullable, ràng buộc, nới trigger) —
để nguyên được; rollback SQL ghi ở đầu từng tệp migration.
