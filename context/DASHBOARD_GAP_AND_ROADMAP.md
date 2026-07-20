# DASHBOARD — GAP ANALYSIS & ROADMAP
> Tạo: 2026-06-10 · Nguồn: khảo sát code dashboard + dữ liệu phòng khám (Data khách gửi/, Xemlichsu/) + nghiên cứu thị trường VN & quốc tế (nguồn cuối file).
> Mục đích: tài liệu chuẩn để Planner cắt Task Packet hoàn thiện dashboard cho TỪNG vai trò.

---

## 1. HIỆN TRẠNG (sau đợt sửa 2026-06-10)

Dashboard đã có **xương sống luồng khám đúng chuẩn**: tạo BN chống trùng → CSKH xác nhận → BS nhận ca → check-in + sinh hiệu → SOAP → in phiếu. Phân quyền 6 role server-side (`requireNavAccess`) chặt hơn nhiều phần mềm VN phổ thông.

So với bộ module chuẩn thị trường VN (9 phân hệ: tiếp đón, EMR, điều dưỡng, CLS, thu ngân, kho, CRM, báo cáo, danh mục) thì đang phủ ~5: tiếp đón, lịch hẹn, EMR cơ bản, hàng đợi, **báo cáo (mới)**.

### Vừa làm xong (2026-06-10, commit local, CHƯA push):
1. **`/reports` — Báo cáo KPI cho Quản lý** (thay placeholder): Hôm nay (5 ô số) · Ngày mai (% đã xác nhận) · Theo bác sĩ · 30 ngày (no-show rate, BN mới) · Bar 7 ngày · Nguồn đặt lịch theo booking_channel. Toàn count-query, không fetch cả bảng. Chưa gồm doanh thu (chờ module thu ngân).
2. **`/cskh-today` — "Cần làm hôm nay" cho CSKH** (+ Quản lý): ① gọi xác nhận lịch ngày mai (SCHEDULED) ② lịch bị BS từ chối cần phân lại ③ BN đến hạn tái khám trong 7 ngày (đọc `soap_plan.tai_kham`, loại BN đã có lịch tương lai) ④ KQ XN về hôm nay — GROUP_C badge đỏ "Chờ BS duyệt — KHÔNG báo BN" (gate D022).
3. **Form khám — mục "X. Theo dõi & Tái khám"**: ngày tái khám + 5 checkbox nhóm XN (HM/SH/SA/DXA/PS theo bộ mã viết tắt phòng khám đưa) + ghi chú. Lưu vào `soap_plan.tai_kham {ngay, xn[], ghi_chu}`. Phiếu in A4 hiện dòng "Hẹn tái khám…". Đây là NGUỒN dữ liệu nuôi khối ③ của /cskh-today → khép kín vòng recall thủ công đầu tiên.

Verify: `tsc --noEmit` PASS · `npm run lint` PASS · `next build` PASS.

### Hợp đồng dữ liệu mới (KHÔNG đổi tùy tiện)
```
clinical_record.soap_plan.tai_kham = {
  ngay: "YYYY-MM-DD",            // chỉ ghi khi có
  xn: ["HM","SH","SA","DXA","PS"], // subset, thứ tự canonical
  ghi_chu: "..."                 // tùy chọn
}
```
Mã nhóm XN theo bảng viết tắt phòng khám: HM=Hormone, SH=Sinh hóa, SA=Siêu âm, DXA=Đo loãng xương, PS=Pap smear.

---

## 2. GAP CÒN LẠI THEO VAI TRÒ

### Lễ tân
- **Patient tracking board**: nâng board read-only thành bảng trạng thái sống (`Hẹn → Xác nhận → Check-in → Đang khám → Chờ SA/XN → Thanh toán → Xong`) + đồng hồ thời gian chờ đổi màu. Trạng thái tự nhảy theo thao tác role khác (D036: không tăng việc gõ tay).
- **Số thứ tự + hàng chờ theo phòng** (BS Thành 40–50 BN/buổi). Phase sau: màn TV gọi số.
- **Waitlist tự lấp slot hủy** (quốc tế thu hồi 30–50% slot hủy — số vendor, tham khảo).

### CSKH
- ĐÃ CÓ /cskh-today (v1). Nâng cấp tiếp:
  - **Khối "BN im lặng 3/6/12 tháng"** — cần RPC/materialized view (aggregate qua supabase-js không làm được sạch). Đánh dấu TODO trong code.
  - **Recall engine women's health**: tự sinh recall Pap định kỳ, hậu sản 2+6 tuần, mốc siêu âm thai NT 11–13w / hình thái 18–22w / 32w. Mở chiến dịch trước hạn ~8 tuần. (Hiện mới có recall theo phiếu BS dặn.)
  - **Nhắc lịch 3 chạm** T-48h → T-24h (2 chiều) → T-2h qua **Zalo ZNS** (~200đ/tin, template phải Zalo duyệt). Chưa có key: làm nút "Copy tin nhắn mẫu" trước.
  - **Log tương tác trên hồ sơ BN** (thay Log CSKH.xlsx): API `cskh-action` ĐÃ CÓ, thiếu UI nhập nhanh từ popup BN.
  - Khảo sát hài lòng 1 câu (NPS) sau khám 2–24h; điểm thấp → ticket cho Quản lý.

### Điều dưỡng
- **Rooming checklist** khi check-in: sinh hiệu → đối chiếu dị ứng/thuốc → cờ care-gap ("quá hạn Pap 14 tháng", "thai 22w chưa SA hình thái").
- **Lab pending board + SLA**: cột "quá hạn" (Diag hẹn 14:20 chưa về → đỏ).
- **Danh mục XN có khoảng tham chiếu** (~40 test từ biểu mẫu phòng khám, có đơn vị: FSH mIU/mL, E2 pg/mL, AMH ng/mL, T-score…): seed bảng `lab_test_catalog` → điều kiện để phân loại A/B/C tự động + nhập kết quả có cấu trúc thay text tự do.
- **Worklist siêu âm riêng**: số đo có cấu trúc (NT, BPD, CRL, niêm mạc, AFC) gắn visit.

### Bác sĩ
- **Form khám theo CHUYÊN KHOA** (từ biểu mẫu giấy phòng khám đưa 06/2026): SOAP chung làm khung + khối `specialty_data` JSONB theo service_type — 4 form: Phụ khoa / Sản / Nội tiết (MHT) / Hiếm muộn. Checklist làm dạng tick (tiền sử nội tiết 10 mục, lý do khám HMVS 12 mục…).
- **Prenatal flowsheet + EDD/EGA auto-calc** — tính năng đáng làm nhất cho phòng khám sản: nhập LMP/SA → tự tính tuổi thai mọi lần khám; lưới mỗi cột = 1 lần khám thai (cân nặng, HA, tim thai, bề cao TC). Chuẩn Meditab/eClinicalWorks/athena.
- **PARA/tiền sử phụ khoa lưu 1 lần** ở hồ sơ BN, prefill mọi lần khám (cả 4 form giấy lặp phần này).
- **Inbox kết quả bất thường** trên board: GROUP_B/C route đích danh BS chỉ định, badge đỏ trên menu.
- **Đơn mẫu / quick phrases** theo chuyên khoa.
- BMI hiện là ô NHẬP TAY trong sinh hiệu — nên đổi thành tự tính từ cân nặng + chiều cao (việc nhỏ).
- Hiếm muộn (khi thành dịch vụ chính): **hồ sơ vợ–chồng liên kết** + **STIM sheet** theo chu kỳ (đồ thị nang noãn + hormone + liều). Cần entity "chu kỳ điều trị" — vượt mô hình visit đơn lẻ.

### Quản lý
- ĐÃ CÓ /reports v1. Nâng cấp: recall conversion (% BN được nhắc quay lại) · thai phụ đang quản lý theo quý thai · tỷ lệ đúng hẹn mốc SA · doanh thu (chờ thu ngân) · third-next-available.
- **Audit log thao tác** (ai sửa hành chính BN nào lúc nào) — điều kiện khi siết auth (nợ #1/#11 đã chốt 06/06).

### Thu ngân (vai có thật — 7 lễ tân kiêm; capability CASHIER đã có trong DB, D7 Finance = 0 bảng)
- KHÔNG thay KiotViet vội (parallel-run). Bước tối thiểu: ① bảng giá dịch vụ ② cột "chờ thanh toán" trên tracking board ③ ghi số tiền + hình thức trả vào visit → KPI doanh thu chạy được.
- Hóa đơn điện tử (NĐ 70/2025: xuất HĐ **tại thời điểm thu tiền**) để khi thay KiotViet mới làm.

---

## 3. ⚠️ PHÁP LÝ ẢNH HƯỞNG ROADMAP (cần nêu với Quản lý/sếp)

1. **Đơn thuốc điện tử — TT 04/2022/TT-BYT**: phòng khám tư bắt buộc kê đơn điện tử liên thông donthuocquocgia.vn từ **30/6/2023 (ĐÃ QUÁ HẠN)**. Dashboard ĐANG có mục kê đơn (IX) mà chưa sinh mã đơn quốc gia/đẩy API. Việc của phòng khám: đăng ký mã cơ sở + mã BS; việc của dev: tích hợp API đẩy đơn. Gap tuân thủ, không phải nice-to-have.
2. **Bệnh án điện tử — TT 13/2025/TT-BYT** (thay TT 46/2018): cơ sở KCB khác (gồm phòng khám) hạn chót **31/12/2026**. Hướng hiện tại (FINALIZED bất biến, append-only, amendment) đúng tinh thần; còn thiếu **chữ ký số của BS khi chốt hồ sơ**.
3. **Hóa đơn điện tử — NĐ 123/2020 + NĐ 70/2025** (hiệu lực 1/6/2025): xuất HĐ tại thời điểm thu tiền, máy tính tiền nối thuế nếu hộ KD ≥1 tỷ/năm.
4. Zalo: KHÔNG đăng kết quả vào nhóm Zalo chung (vi phạm bí mật thông tin KCB) — ZNS gửi đích danh theo SĐT.

---

## 4. ROADMAP ƯU TIÊN (1 dev, D036: không tăng việc nhân viên)

| Ưu tiên | Việc | Ghi chú |
|---|---|---|
| ~~P0~~ ✅ | Báo cáo KPI v1 + /cskh-today v1 + tái khám có cấu trúc | XONG 10/06, chưa push |
| P1 | Prenatal flowsheet + EDD/EGA + form 4 chuyên khoa (`specialty_data`) | Món BS "cảm" được — chốt schema trước |
| P1 | Tracking board + số thứ tự cho Lễ tân | Nền trạng thái chung mọi role |
| P1 | Danh mục XN ~40 test có tham chiếu (seed lab_test_catalog) | Mở đường A/B/C tự động |
| P1 | RPC "BN im lặng" + audit log | Migration mới |
| P2 | ZNS 3 chạm + NPS (CHỜ KEY Zalo — nút thắt đã nêu với sếp) | Trước mắt: nút copy tin mẫu |
| P2 | Thu ngân tối thiểu + đơn thuốc điện tử liên thông + chữ ký số (deadline 31/12/2026) | Cần sếp chốt KiotViet + đăng ký mã cơ sở |
| P3 | Hồ sơ vợ–chồng + STIM sheet hiếm muộn; kho thuốc | Khi HMVS/quầy thuốc thành trọng tâm |

---

## 5. NGUỒN THAM KHẢO CHÍNH
- VN: Medpro (medpro.vn) · YouMed Clinic (youmed.vn) · tClinic sản phụ khoa (tclinic.io) · EvoMed (evomed.vn) · MediCRM (medicrm.vn) · KiotViet (kiotviet.vn) · Diag B2B (diag.vn) · giá ZNS (miniai.vn/bang-gia-zalo-zns) · TT04/2022, TT13/2025, NĐ70/2025 (thuvienphapluat.vn, caselaw.vn).
- Quốc tế: Meditab OB/GYN + FertilityEHR (meditab.com) · eClinicalWorks OB/GYN (prenatal flowsheet) · athenahealth Women's Health · eIVF (eivf.org) · AAFP rooming/MA (aafp.org/fpm) · Artera recall (artera.io) · AppointmentReminder no-show (appointmentreminder.com) · Medesk/OmniMD KPI · AHRQ daily huddle.
- Lưu ý độ tin cậy: các con số hiệu quả (giảm 29% no-show, thu hồi 30–50% slot…) từ blog vendor — dùng định hướng, không cam kết.
