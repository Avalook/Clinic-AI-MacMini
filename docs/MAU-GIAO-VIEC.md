# MẪU GIAO VIỆC CHO AI

> 01/10/2026. Dùng cùng `docs/BAN-DO-SUA.md` (muốn sửa gì → đi đâu) và
> `docs/BAN-DO-CODE.md` (chuỗi file của từng màn). Gốc: SO-LUAT Phần 12 —
> giao theo TÌNH HUỐNG, nói rõ "chỉ chỗ này hay mọi chỗ tương tự", bàn giao bằng
> kịch bản bấm thử.

## Trước khi giao: việc DỮ LIỆU hay việc CODE?

Mở `docs/BAN-DO-SUA.md`, tìm mục. Mục có dòng **Trên màn** và việc chỉ là đổi
giá trị (giá, tên, phòng làm dịch vụ nào, công tắc dây nối, lịch làm việc, mẫu
kết quả, lego của một người, dọn khách thử…) → **tự làm trên màn, không cần
AI**, không cần deploy. Chỉ giao AI khi màn không làm được điều đó.

## Khuôn (chép, điền, dán cho AI)

```text
Đọc CLAUDE.md của repo, rồi docs/BAN-DO-SUA.md mục <số/tên mục>.

VIỆC (một câu, lời người dùng):
  <…>

Ở ĐÂU (từ BAN-DO-SUA / BAN-DO-CODE — AI KHÔNG cần quét cả repo):
  Màn: <route> (lối vào khác theo docs/SITEMAP.md mục B: <…> — sửa đủ / cố ý bỏ: <…>)
  File + hàm: <đường dẫn:hàm>, <…>
  Bảng/migration (nếu đổi DB): <…>

KẾT QUẢ CẦN ĐẠT (hành vi quan sát được, không phải cách code):
  - Khi <ai> làm <gì> ở <màn> thì thấy <gì>.
  - Ca biên: <dữ liệu rỗng / ngày rác / hai người cùng bấm / đã thu – chưa thu…>
  - Chỉ chỗ này hay MỌI chỗ tương tự: <…>

CÁCH KIỂM:
  - Test: <tệp test có sẵn cần xanh> + test mới cho <ca biên> (thử ngược: làm hỏng code thấy đỏ).
  - Bấm thật: <màn> ở cỡ 375 và 1280, vai <…>, các bước <1-2-3>.
    (Giao diện: scripts/dev-giao-dien.sh — sửa .tsx thấy ngay; xong chạy
     scripts/dev-nap-lai.sh web để bấm lại trên bản dựng như prod.)
  - SQL kiểm (nếu đụng dữ liệu): <câu SELECT>.

KHÔNG ĐƯỢC ĐỤNG:
  <màn/luật/bảng giữ nguyên> · không luật nghiệp vụ trong TSX · đổi DB chỉ bằng
  migration mới · không deploy, không đụng prod.

ĐẦU RA:
  Nhánh việc từ origin/main → PR. ./scripts/ci-may.sh --bao-github xanh (đã chạy
  python3 scripts/ban-do-code.py nếu đổi màn/route/router). Báo cáo 4 mục
  SO-LUAT 12.4: đã đổi gì · kịch bản bấm thử · những gì KHÔNG đổi · rủi ro còn lại
  · bảng "nút/link đã đụng" (màn → nút → API → vai thấy).
```

---

## Ví dụ 1 — việc DỮ LIỆU (không giao AI)

**Việc:** "Ghế điện từ trường chỉ làm ở Phòng Sàn chậu."
**Làm:** Quản lý vào `/settings/clinic-config` → Phòng Sàn chậu → "Làm việc gì"
→ tick *Ghế điện từ trường* (×3 gói). Dịch vụ đã tick ở một phòng thì chỉ xếp
được vào các phòng có tick.
**Kiểm:** ở `/thu-ngan/dich-vu` chọn một lượt có Ghế ĐTT → ô phòng chỉ còn Phòng
Sàn chậu; xếp tay sang phòng khác bị từ chối với câu "dịch vụ chỉ làm ở: …".
(Tính năng này là code từ 30/09 — `docs/BAN-DO-SUA.md` mục 1; nay chỉ còn là dữ liệu.)

## Ví dụ 2 — việc CODE: in phiếu hướng dẫn phòng khi chưa thu

```text
Đọc CLAUDE.md, rồi docs/BAN-DO-SUA.md mục 7 "Phiếu thu (80mm), phiếu hoàn, phiếu hướng dẫn phòng".

VIỆC: "Khách làm trước – thu sau thì quầy in được tờ hướng dẫn đi phòng nào, chưa có tiền trên tờ."

Ở ĐÂU:
  Màn: /thu-ngan/dich-vu (lối khác: ô tick Làm trước – thu sau ở Bàn khám
       _lam-viec/OLamTruocThuSau.tsx; khối đã thu thu-ngan/XepPhongDaThu.tsx — sửa đủ ba).
  File + hàm: src/dashboard/app/print/phieu-thu/[id]/InPhieuThu.tsx (loai=huong_dan);
    src/clinicai/api/v1/routers/cashier.py:cashier_phieu (Query loai);
    src/clinicai/services/quay_thu_service.py QuayThuService.phieu, dong_huong_dan.
  Bảng: không đổi lược đồ.

KẾT QUẢ CẦN ĐẠT:
  - Sau khi quầy chốt dịch vụ mà CHƯA thu, có nút "In phiếu hướng dẫn phòng
    (chưa thu tiền)"; tờ in khổ 80mm có tên khách, số lượt, từng dịch vụ + phòng
    + tầng, KHÔNG có cột tiền, không có chữ "Phiếu thu".
  - Ca biên: dịch vụ chưa xếp phòng → ghi "chờ xếp phòng"; mã lượt của phòng
    khám khác → 404; id rác → 422 chứ không 500.
  - Mọi chỗ in tờ này dùng chung một trang in (không chép bản thứ hai).

CÁCH KIỂM:
  - Test: src/tests/unit/test_quay_thu.py, src/tests/services/test_phieu_huong_dan_db.py
    (+ ca "chưa xếp phòng", "lượt phòng khám khác").
  - Bấm: /thu-ngan/dich-vu ở 375 và 1280 → chốt dịch vụ, không thu → In → xem bản
    in thử (Ctrl+P) đúng khổ 80mm.
  - SQL: SELECT kind, status FROM payment_cycle WHERE visit_id = '<id>';  -- không có dòng dich_vu PAID

KHÔNG ĐƯỢC ĐỤNG: phiếu thu / phiếu hoàn hiện có; luật thu_truoc_khi_lam; không
  thêm tiền vào tờ hướng dẫn.

ĐẦU RA: PR từ origin/main, ci-may xanh, báo cáo 4 mục + bảng nút đã đụng.
```

## Ví dụ 3 — việc CODE: trạng thái "Đã về" sau check-out ở mọi màn

```text
Đọc CLAUDE.md, rồi docs/BAN-DO-SUA.md mục 11 "Nhãn trạng thái lịch/lượt".

VIỆC: "Khách check-out rồi mà trang chủ, lịch hẹn vẫn hiện Đang khám."

Ở ĐÂU:
  Màn: /home, /reception/queue, /customers, /hanh-trinh, /reception/checkout
       (mọi màn hiện nhãn trạng thái — tìm route trong docs/BAN-DO-CODE.md).
  File + hàm: src/clinicai/core/trang_thai_lich.py trang_thai_hien_thi (MỘT nhãn
    cho mọi màn); src/clinicai/services/checkout_service.py CheckoutService.close
    (đổi lịch sang COMPLETED cùng giao dịch); consumer
    src/clinicai/events/consumers/hanh_trinh.py (visit.checked_out).
  Bảng/migration: appointment.status — backfill lịch lệch bằng migration MỚI
    (mẫu: supabase/migrations/20261001230100_lich_cua_luot_da_ve_dong_bo.sql).

KẾT QUẢ CẦN ĐẠT:
  - Check-out xong, cả năm màn trên cùng nói "Đã về" trong lần làm mới kế tiếp
    (màn nghe sự kiện tự đổi, không cần F5).
  - Ca biên: khách về giữa chừng (left_early) cũng đóng lịch; lịch cũ đã lệch
    được backfill; chạy migration lần hai không đổi thêm dòng nào.
  - Mọi màn: không màn nào tự suy nhãn trong TSX — đọc nhãn máy chủ trả.

CÁCH KIỂM:
  - Test: src/tests/unit/test_trang_thai_hien_thi.py,
    src/tests/services/test_thu_thuat_nhu_kham_thuong_db.py::test_check_out_moi_man_cung_noi_da_ve.
  - Bấm: check-in một khách thử → check-out ở /reception/checkout → mở /home và
    /reception/queue ở 375 và 1280, thấy "Đã về".
  - SQL: SELECT count(*) FROM appointment a JOIN visit v ON v.appointment_id = a.id
         WHERE v.closed_at IS NOT NULL AND a.status = 'CHECKED_IN';  -- phải 0

KHÔNG ĐƯỢC ĐỤNG: luật giữ chỗ (giu_cho) trong cùng tệp; không sửa migration cũ.

ĐẦU RA: PR từ origin/main, ci-may xanh (migration chạy thật trong job database),
  báo cáo 4 mục + bảng nút đã đụng.
```
