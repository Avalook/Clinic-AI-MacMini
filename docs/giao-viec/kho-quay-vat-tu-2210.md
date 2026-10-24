# Giao việc: soát toàn diện Kho thuốc · Quầy thuốc · Kho vật tư (22/10/2026)

Người giao: Claude (điều phối), Tuyền duyệt. Người làm: Codex hoặc Claude CLI chạy trên Mac
(cần DB test + stack local — KHÔNG làm được ở cloud).
Đọc trước: `CLAUDE.md`, `docs/SO-LUAT.md` (Phần 6), `docs/BAN-DO-SUA.md` (mục kho thuốc, quầy,
vật tư), `docs/soat-he-thong-2210/0-kho-quay-bam-that.md` (12 lỗi đã thấy khi bấm staging 22/10).

Việc này là **Mức 3** (tiền + tồn kho + quyền) → làm **hai pha**. Pha 1 xong phải dừng,
Tuyền duyệt rồi mới sang pha 2.

```text
VIỆC (lời Tuyền):
  "Kho thuốc, quầy thuốc, kho vật tư phải đúng tiền, đúng số lượng, mọi thao tác phát sự kiện
   để màn khác tự cập nhật, lego + open và thống nhất với cả hệ thống, không tách biệt xa lạ.
   Ai được vào kho/quầy là do QUẢN LÝ bật cho từng người."

Ở ĐÂU (không quét cả repo — tra docs/BAN-DO-SUA.md + docs/BAN-DO-CODE.md):
  Màn: /pharmacy, /pharmacy/inventory (tab KHO + QUẦY), /pharmacy/history, /pharmacy/consult,
       /thu-ngan/thuoc (+ /lich-su), /cashier/thuoc, /kho-vat-tu; lối khác theo docs/SITEMAP.md.
  Backend: src/clinicai/services/pharmacy_service.py, các service kho vật tư / thu tiền thuốc
       (tìm qua BAN-DO-CODE), router tương ứng, src/clinicai/events/**.
  Quyền: lego pharmacy.view, pharmacy.dispense, payment.medicine.collect,
       payment.medicine.history, vat_tu.manage (src/dashboard/lib/roles.ts NAV_QUYEN + kiểm ở
       backend); màn cấp quyền /phan-quyen. Lưu ý migration 20260930900000_mo_full_lego.sql
       đã mở MỌI lego cho mọi tài khoản nội bộ.
  Bản đồ có ghi chú từng tệp: nhánh origin/claude/ban-do-hieu, thư mục docs/ban-do/hieu/.

PHA 1 — SOÁT + BẰNG CHỨNG (không sửa code sản phẩm)
  A. Mô hình nghiệp vụ: liệt kê MỌI thao tác của 3 khu (nhập lô, sửa lô/hạn, điều chỉnh, huỷ lô,
     chuyển kho→quầy, kiểm đầu/cuối ca, kiểm kê, kê đơn, thu tiền thuốc, bán thêm tại quầy,
     giao một phần/đủ, gán lô sau, chốt không giao thêm, khách trả, thuốc trả chờ kiểm nhập
     lại/huỷ, hoàn tiền, hoàn tác từng thao tác, nhập/xuất/kiểm vật tư, vật tư dùng trong dịch vụ…)
     → bảng: thao tác · hàm service · bảng ghi · sự kiện phát ra · màn nào nghe · hoàn tác bằng gì.
  B. Test giả lập trên DB test (scripts/test-nhanh.sh), theo mẫu
     src/tests/services/test_mo_phong_dong_tien_db.py:
     - gọi đúng service thật cho từng thao tác ở A;
     - sau MỖI bước kiểm bất biến:
         tồn lô = tổng sổ kho của lô; tồn không âm (thuốc) / được âm nhưng có cảnh báo (vật tư —
         Quang chốt 17/10); tiền thu − hoàn = doanh thu thuốc trong báo cáo ca; hoàn ≤ thu;
         SL giao ≤ SL đã thu; hoàn tác đưa tồn + tiền về đúng trước đó; báo cáo cuối ngày khớp sổ;
     - bài bấm ngẫu nhiên hạt cố định ≥40 lượt × 10 bước, in chuỗi gây lệch;
     - kiểm sự kiện: mỗi thao tác ghi phải có dòng notify/record_event tương ứng (trước khi kết
       luận "thiếu sự kiện" phải kiểm đủ record_event, _log, ghi_nhat_ky, cột …_boi — lần soát
       21/10 báo oan 19/20 vì bỏ qua các đường này);
     - lỗi thật đánh xfail(strict=True) làm bằng chứng.
  C. Quyền: với từng màn + API của 3 khu, ghi lego nào cho vào; backend có kiểm lego không hay chỉ
     giao diện chặn; tắt lego ở /phan-quyen thì người đó còn vào/gọi API được không.
  D. Bấm thật bằng trình duyệt (Computer Use hoặc Playwright) trên stack local
     (scripts/dev-up.sh, tài khoản @dr4women.local; API/web của nhánh chạy cổng riêng 8260/3260)
     ở 375 + 1280: MỌI nút của 3 khu, mọi ca (đủ/thiếu lô, lệch đơn vị, giao một phần, khách trả,
     hoàn tác, hai tab cùng bấm, vai không có lego). Mở 2 tab khác vai để thấy màn kia có tự cập
     nhật không. Theo dõi log API + su-kien: lỗi 4xx/5xx. Sau mỗi luồng chạy SQL đếm tồn/tiền đối
     chiếu bất biến ở B. Ghi thêm đề xuất DỄ DÙNG: nút nên gộp, bước thừa, chữ khó hiểu, thông tin
     thiếu (ngày đơn, tuổi đơn…), so với 12 lỗi đã thấy ở 0-kho-quay-bam-that.md.
  E. "Thống nhất với hệ thống": chỗ nào kho/quầy/vật tư làm khác cả hệ thống (tự viết lại thành
     phần chung, nhãn trạng thái riêng, hoàn tác riêng, không dùng TenKhach/chuông/SSE chung…).
  ĐẦU RA PHA 1: PR "docs+test" từ origin/main gồm docs/soat-he-thong-2210/6-kho-quay-vat-tu.md
     (bảng A, danh sách lỗi có mức · tệp:dòng · tái hiện có SỐ ví dụ · độ chắc) + các test giả lập
     (lỗi đánh xfail strict). Kèm KẾ HOẠCH PHA 2 chia PR nhỏ (≤400 dòng), mỗi PR ghi migration
     (nếu có), rủi ro, cách hoàn tác. DỪNG, chờ Tuyền duyệt.

PHA 2 — SỬA (sau khi Tuyền duyệt kế hoạch)
  Mỗi lỗi/nhóm một nhánh từ origin/main, một PR; test xfail tương ứng tự XPASS thì gỡ dấu.
  Quyền: chỉ backend quyết; giao diện chỉ ẩn/hiện theo lego. Việc thu hẹp ai có lego là VIỆC
  DỮ LIỆU Tuyền làm ở /phan-quyen — KHÔNG viết migration tắt lego hàng loạt nếu chưa được duyệt.

KẾT QUẢ CẦN ĐẠT (cuối pha 2):
  - Quản lý bật/tắt lego kho/quầy/vật tư cho từng người ở /phan-quyen; tắt rồi thì người đó không
    thấy màn và API trả 403.
  - Mọi thao tác ở 3 khu: đúng tiền, đúng số lượng, hoàn tác được, phát sự kiện, mọi màn liên quan
    tự cập nhật (không cần F5).
  - Bài giả lập + bài ngẫu nhiên xanh bắt buộc trong ci-may.
  - Ca biên: hai người cùng giao/cùng thu một đơn; giao khi lô lệch đơn vị (hộp/gói); thuốc
    không có lô; ngày/giờ rác → giá trị rỗng chứ không 500.

KHÔNG ĐƯỢC ĐỤNG:
  Không deploy, không đụng VPS/prod/staging. Không luật nghiệp vụ trong TSX. Đổi DB chỉ bằng
  migration MỚI (dải giờ riêng, soát trùng số với nhánh khác). Không gộp với #499 (quy đổi
  hộp↔gói, đang chờ Tuyền quyết) — chỉ ghi ảnh hưởng. Không nạp/ghép dữ liệu thuốc thật.
  Không chạy ci-may ngoài 08:00–23:00.

ĐẦU RA: như trên; ./scripts/ci-may.sh --bao-github xanh trước khi báo xong; báo cáo 4 mục
  SO-LUAT 12.4 + bảng "nút/link đã đụng".
```
