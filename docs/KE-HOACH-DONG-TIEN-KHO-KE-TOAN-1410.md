# KẾ HOẠCH ĐỢT 14/10 — Dòng tiền · Thuốc · Vật tư · Kế toán · Tài khoản

> Soạn 14/10/2026 từ recap họp phòng khám 12/10 + dò code (4 agent `tim-cho-sua`,
> Claude tự kiểm lại 2 phát hiện chính). **Chưa code dòng nào.** Mục 2 là câu hỏi
> chờ Tuyền chốt; gói nào ghi "SẴN" thì làm được ngay không cần chờ.
> Việc chưa xem / để đợt sau: **mục 8** (đọc mục này đầu mỗi phiên tới).

## 1. Phát hiện từ code (đã kiểm, có file:dòng)

| # | Phát hiện | Chỗ | Hệ quả |
|---|---|---|---|
| F1 | **Lỗi thật:** sửa khách mất im lặng địa chỉ, giới tính, dân tộc, quốc tịch, nghề, người giám hộ — `PatientUpdateDTO` không có các trường đó, Pydantic bỏ qua; màn vẫn báo "Đã lưu" | `src/clinicai/schemas/patient.py:143`, `app/api/patients/route.ts:234`, `PatientAdminEditor.tsx save()` | Đây là gốc "không sửa được khách Notion" (thật ra mọi khách). CCCD: không màn nào sửa. SĐT Notion chép thô (`nhap_lich_su_notion.py`) → SĐT lạ làm cả lần lưu bị từ chối |
| F2 | Không có email khách: `patient` không có cột; xuất MISA đọc `patient_contact_channel` mà không chỗ nào ghi bảng đó | `xuat_hoa_don_service.py:~76` | Cột email trong file kế toán luôn trống |
| F3 | Khối "Tài chính" ở báo cáo: `giam_gia` luôn `None` ("Chưa có dữ liệu") dù giảm giá đã lên prod 13/10 | `tom_tat_tai_chinh_service.py`, `TomTatCuoiNgay.tsx:70-76` | Lỗi thời; 2 test đang khoá đúng hành vi sai |
| F4 | Số "thu" hiện tại là **SAU giảm** (`payment_cycle.amount = original_amount − discount_amount`) | migration `20261013100000_giam_gia.sql:57` | Nếu cắm thẳng vào công thức khách → trừ giảm giá 2 lần |
| F5 | **Nợ ghi không phải bút toán cố định:** ghi lại nợ `UPDATE … ghi_luc = now()` đè dòng cũ; "nợ thu được" là lần thu thường, không cờ phân biệt | `cong_no_service.py:~490` | Muốn có "−Nợ" và "+Nợ thu được" đúng mọi ngày phải thêm **sổ bút toán nợ** (append-only) |
| F6 | `/hoa-don` không đọc query URL → chưa làm link từ hạng mục báo cáo sang danh sách được | `hoa-don/page.tsx` | Phải thêm deep-link |
| F7 | Kế toán không xem được hoá đơn tài chính nếu không phải vai Quản lý/Trưởng ca trực — `report_access_service.access()` chặn, lego không đủ | `report_access_service.py:181`, `danh_sach_hoa_don_service.py:249` | Tạo tài khoản chị Hoài xong vẫn bị chặn → cần vai/quyền kế toán |
| F8 | Thuế GTGT: không bảng nào có cột thuế suất; mẫu MISA cột K/L | `xuat_hoa_don_service.py` | Cần migration + màn nhập |
| F9 | Thuốc: kho theo cơ sở (`drug_batch.location_id`), chưa có kho/quầy, chưa mã vạch, `expiry_date NOT NULL`, kiểm kho ghi ADJUST ngay (không nháp, không cảnh báo); `xuat_nhap_ton` chỉ theo NGÀY nhưng tính ngược từ sổ nên thêm giờ ca dễ | `kho_thuoc_service.py:221,564`, `shifts.py:335 khung_chot_ca` | Kiểm kê ca + cột Tồn đầu/Nhập/Bán/Tồn cuối làm được trên nền có sẵn |
| F10 | Báo cáo hàng hoá lấy số từ **dòng hoá đơn**, không từ sổ kho | `bao_cao_cuoi_ngay_service.py:422 gom_hang_hoa` | Cột tồn phải lấy từ `inventory_txn` |
| F11 | Vật tư: chỉ có bán thêm ở quầy dịch vụ (`luot_vat_tu`), **không có tồn**, không gắn phòng; duyệt chỉ vai MANAGEMENT; cờ `can_ql_duyet`/`chon_nhanh` không sửa được trên màn | `vat_tu_service.py`, mig `20261003000000` | Kho vật tư là phần mới hoàn toàn |
| F12 | File vật tư chị Hà 01/10: 84 dòng, KHÔNG có cột Văn phòng phẩm/Vật tư y tế, giá nhập, phòng; 11 dòng "được bán trực tiếp" | `~/Downloads/[Dr4women] Danh sách vật tư 01.10.2026…xlsx` | Cần người phân loại |
| F13 | Tài khoản: Quản lý **đã** đặt lại mật khẩu được (`/settings/tai-khoan`); nhân sự **chưa** tự đổi được; "xoá" đã có 2 nửa ở 2 màn (Nghỉ việc `/nhan-su` + Gỡ tài khoản `/settings/tai-khoan`); `thu_hoi` không chặn tự gỡ chính mình | `staff_service.py:384`, `tai_khoan_service.py:121`, `api/admin/users/route.ts` | ~90 FK lịch sử → staff: **không xoá cứng**, chỉ khoá + nghỉ việc |
| F14 | 4 mục "quản lý" (tạo NS, tạo TK, cấu trúc phòng, bảng giá, phân quyền) **đã có màn**: `/nhan-su`, `/settings/new-user`, `/settings/clinic-config`, `/cashier/dich-vu`, `/phan-quyen` | SITEMAP | Khả năng khách chưa biết / chưa được cấp lego |

## 1b. Lối rò dòng tiền ngoài happy path (soát kiểu kế toán, 14/10)

Agent soát 20 tình huống; Claude tự kiểm lại các dòng đánh ✔ trong code. `S/` = `src/clinicai/services/`.

| # | Lối rò | Ví dụ | Kiểm |
|---|---|---|---|
| R1 | Xác minh CK ghi theo SỐ HOÁ ĐƠN, không nhập số ngân hàng thật nhận; lần CK chờ bị huỷ (CANCELLED) không hiện ở báo cáo lẫn danh sách | Khách chuyển 1.000.000, NV huỷ lần chờ vì tưởng chưa về → ngân hàng có tiền, sổ không có dấu | ✔ `S/payment_service.py:~1153`, `S/bao_cao_cuoi_ngay_service.py:835` (chỉ PAID/VOIDED) |
| R2 | Huỷ phiếu sau check-out khi dịch vụ đã làm → không sinh nợ; báo cáo ngày cũ bị đổi hồi tố; đổi TM→CK không cần bằng chứng | Hôm sau huỷ phiếu 800k của khách đã khám xong → khách thành "không nợ, không trả" | agent (`S/payment_service.py:1326`), chưa tự kiểm |
| R3 | Thuốc: đính chính đơn sau thu "tiền giữ nguyên, đối soát riêng"; thu rồi chưa giao không có sổ tích luỹ; khách trả thuốc (`drug_return`) không nối với hoàn tiền | Khách trả 2 hộp, NV quên hoàn tiền → hàng về kho, tiền không ra, không màn nào báo | agent (`S/pharmacy_service.py:1688`, `S/dinh_chinh_don.py`) |
| R4 | Đã thu mà khách về chưa làm: check-out không hỏi tiền, không có trong báo cáo, chỉ hiện ở danh sách hoá đơn và rụng sau **90 ngày** | Khách D (ví dụ Q5) — sau 3 tháng không màn nào còn nhắc 500k phải trả | ✔ `S/danh_sach_hoa_don_service.py:143,204` |
| R5 | Số trôi: hoàn thất bại không bao giờ vào "việc tồn" (chỉ lấy PENDING); nợ trả một phần không trừ; ghi lại nợ đè người/ngày gốc; "giữ lại tiền thừa" không có tổng | Hoàn CK 300k bị lỗi → biến mất khỏi mọi danh sách việc phải làm | ✔ `S/danh_sach_hoa_don_service.py:108`, `S/cong_no_service.py:~490` |
| R6 | Hoàn tiền thừa luôn ghi **tiền mặt**, kể cả khách đã trả CK | Khách CK 500k, bỏ 1 dịch vụ → hệ ghi trả TM 500k → két lệch | ✔ `S/hoan_tien_service.py:172` |
| R7 | Không chốt ca/khoá sổ: mọi sửa đều hồi tố về ngày cũ | Báo cáo hôm qua in ra 10tr, hôm nay mở lại còn 9,2tr | agent |
| R8 | Tài khoản dùng chung: sổ không biết ai cầm tiền | — | đã ở mục 8 |
| R9 | Đối tác thu hộ: không so bảng giá, không danh sách "đối tác làm mà chưa ghi đã thu" | — | agent |
| R10 | Liệu trình: buổi trả trước chưa dùng là tiền phải trả khách nhưng không có màn tổng | — | agent |

Không rò đáng kể: thu trùng (Idempotency-Key + khoá + ràng buộc DB); "tạo bill" chưa thu (không có bản ghi, đúng).

## 2. Câu hỏi cần Tuyền chốt (có đề xuất — trả lời "theo đề xuất trừ Qx")

### Dòng tiền (gói G4)
- **Q1. "Dòng tiền vào" = tổng giá trị hoá đơn TRƯỚC giảm, gồm cả phần ghi nợ**, tính trên các bút toán đã ghi trong kỳ (lần thu + nợ ghi). Chỉ định nghĩa này làm công thức khách ra đúng tiền thật (xem bảng vàng mục 5.1). *Đề xuất: đồng ý.*
- **Q2. Thêm sổ bút toán nợ** (ghi / ghi lại / huỷ / thu) để "Nợ" và "Nợ thu được" cố định theo ngày, mở lại kỳ cũ không đổi. *Đề xuất: đồng ý (mức 3, có migration + nạp ngược từ sự kiện `cong_no.ghi`).*
- **Q3. Doanh thu thuần** — khách viết 2 vế mâu thuẫn ("DTV − trả lại" ≠ "doanh thu − giảm giá"). *Đề xuất: Doanh thu thuần = Dòng tiền vào − Giảm giá − Trả lại* (= giá trị dịch vụ thật đã bán).
- **Q4. "Trả lại tiền khách" gồm hoàn tiền ĐÃ XONG + huỷ phiếu đã thu**, tách TM/CK; hoàn đang chờ chỉ ghi chú, không trừ. *Đề xuất: đồng ý.*
- **Q5. Hoá đơn "không đúng"** = phiếu có ít nhất một: huỷ, hoàn tác lần thu, đổi hình thức TM↔CK, hoàn tiền. Mỗi phiếu kèm lý do + người bấm. *Đề xuất: đồng ý.*
- **Q6. Nợ và Giảm giá không có TM/CK** (không có tiền đi qua) → hiện "—"; các mục khác hiện đủ TM/CK. Khối Dòng tiền vẫn chỉ hiện khi Quản lý bật "đầy đủ" như cũ. *Đề xuất: đồng ý.*

### Thuốc (G3, G6, G7)
- **Q7. Mã vạch:** quét mã in sẵn trên hộp (EAN nhà sản xuất — giống siêu thị, mọi lô chung mã) → hệ tự chọn lô gần hết hạn nhất (FEFO), dược sĩ đổi được. Tem in riêng từng lô để sau. *Đề xuất: đồng ý.* Cần biết: quầy đã có máy quét chưa (loại USB gõ như bàn phím là đủ).
- **Q8. Tách KHO / QUẦY làm SAU kiểm kê.** Đợt này "quầy" = tồn cơ sở hiện tại. Khi tách: tồn cũ về KHO, quầy nhận bằng phiếu chuyển; quầy hết mà kho còn → không bán, nhắc chuyển. *Đề xuất: làm sau (G7), sau khi kiểm kê chạy ổn 1 tuần.*
- **Q9. Kiểm kê đầu/cuối ca:**
  (a) quên kiểm đầu ca → chỉ nhắc, không chặn bán (luật "không khoá cứng");
  (b) đếm tồn THẬT trên kệ (thuốc đã thu tiền mà chưa giao vẫn đang trên kệ → vẫn đếm);
  (c) lệch → ghi lệch + chuông cho Trưởng ca/Quản lý; **chưa tự sửa tồn** — người rà bấm "Điều chỉnh theo kiểm kê" (hoàn tác được);
  (d) công thức: tồn cuối máy = tồn đầu + nhập + trả về − bán/xuất ± điều chỉnh. Khách viết "đầu ca − cuối ca + trả về" — đó là **số đã bán trong ca**, không phải tồn cuối. *Đề xuất: (a)(b)(c)(d) như trên.*
- **Q10. Lô thật:** dùng **lần kiểm kê đầu tiên làm số tồn mở đầu** (đưa demo về 0, tồn thật = số đếm), thay kế hoạch "100/lô" 08/10. *Đề xuất: đồng ý.*

### Vật tư (G8, G9)
- **Q11. Ai duyệt:** "Quản lý hệ thống" (chị Hà) là tài khoản nào? Trưởng ca được duyệt không (hiện chỉ vai Quản lý)? Điều kiện: đánh dấu TỪNG mặt hàng ("cần duyệt khi bán", "cần duyệt khi nhập") thay cho ngưỡng giá. *Đề xuất: cờ từng mặt hàng; Trưởng ca + Quản lý duyệt.*
- **Q12. Tiêu hao theo phòng** = phiếu XUẤT kho → phòng (xuất coi như dùng); phòng kiểm kê định kỳ; không bắt nhân viên ghi từng lần dùng găng/gạc. *Đề xuất: đồng ý.*
- **Q13. Phân loại 84 vật tư** (VPP/VTYT, kinh doanh/không, cần duyệt, giá nhập, phòng dùng): chị Hà làm trên màn (mình làm màn) hay gửi lại Excel? *Đề xuất: làm màn + nạp sẵn những gì file có.*
- **Q14. Đầu dò Bio:** BS khi chỉ định siêu âm đầu dò chọn luôn "Bio 1 lần / nhiều lần" trong khối chỉ định CLS; tiền đi theo chỉ định (huỷ chỉ định = bỏ Bio); ô Bio ở quầy thu bỏ, dòng Bio vẫn hiện trên hoá đơn. Dữ liệu Bio đã thu cũ giữ nguyên. *Đề xuất: đồng ý.*

### Kế toán (G1, G5)
- **Q15. Thông tin công ty lưu THEO HOÁ ĐƠN** (tick "Xuất HĐ công ty" lúc thu / sửa sau ở danh sách hoá đơn), điền sẵn từ lần trước của khách. Thu ngân + Lễ tân + CSKH + Kế toán sửa được. *Đề xuất: đồng ý.*
- **Q16. Thuế GTGT đặt theo từng dịch vụ/thuốc/vật tư** (kế toán điền trên bảng giá). Một phiếu có nhiều thuế suất: mẫu MISA "1 thuế suất" không chứa được → **hỏi chị Hoài**: tách thành nhiều hoá đơn theo thuế suất, hay đổi mẫu nhiều thuế suất?
- **Q17. Thêm vai "Kế toán"**: xem báo cáo + danh sách/xuất hoá đơn + sửa thông tin khách/công ty + điền thuế suất; không thu tiền, không cài đặt, không nhân sự. *Đề xuất: đồng ý (mức 3, quyền).*
- **Q18. "Thống kê theo hàng hoá"** = bảng tổng theo mặt hàng trong kỳ (mã, tên, ĐVT, SL, tiền trước/sau giảm, thuế suất, tiền thuế), xuất Excel. *Đề xuất: đồng ý.*
- **Q19. HĐ công ty**: cột "Người mua hàng" để trống hay ghi tên khách? SĐT/CCCD bỏ hẳn. *Đề xuất: hỏi chị Hoài; mặc định để trống.*

### Tài khoản (G2) & quản lý
- **Q20. "Xoá tài khoản" = khoá đăng nhập + nghỉ việc trong MỘT nút** (lịch sử giữ nguyên, tên vẫn hiện); không xoá cứng; Quản lý không tự xoá mình; người còn ca trực tương lai → cảnh báo + danh sách ca để gỡ. Đổi mật khẩu (tự đổi hoặc Quản lý đặt lại) → đăng xuất mọi thiết bị khác. *Đề xuất: đồng ý.*
- **Q21. Bốn mục quản lý đã có màn (F14).** Khách cần thêm gì cụ thể, hay chỉ cần hướng dẫn + cấp lego cho chị Hà? *Đề xuất: chỉ hướng dẫn; không code.*

### 2b. Tuyền trả lời — vòng 1 (14/10)
- **Q5:** "không đúng" = MỌI thứ lệch happy path, nhìn như kế toán thực thụ. Ví dụ Tuyền: tạo bill, khách làm không đủ dịch vụ rồi về/check-out → phải vào **sổ nợ** (chiều phòng khám NỢ khách) để còn trả lại. Claude soát toàn bộ lối rò dòng tiền (agent nền 14/10) → kết quả bổ sung vào G4.
- **Q8:** làm sau theo thứ tự, nhưng **BẮT BUỘC làm** (G7 không được rơi).
- **Q12:** xuất sang phòng mà dùng không hết = **tồn ở phòng**; có kiểm kê phòng → cần lưu tồn theo phòng + phiếu kiểm phòng.
- **Q14:** **giữ cả hai chỗ** — Bio chọn được ở chỉ định CLS VÀ quầy thu; không xoá chỗ đã có.
- **Q16:** để mở, kế toán tự điền/sửa được; Tuyền chưa rõ phần thuế → Claude giải thích bằng ví dụ, chờ chị Hoài chọn mẫu.
- **Q19:** ô "Người mua" để trống mặc định, ai muốn thì điền — không ép.
- **Q20, Q21:** đồng ý; nhấn mạnh **dữ liệu người bị xoá đã làm phải giữ lại hết**.
- Các câu chưa nhắc (Q1 Q2 Q4 Q6 Q7 Q9 Q10 Q11 Q13 Q15 Q17 Q18): **chưa chốt** — bàn lần lượt từng gói, có ví dụ.
- Cách làm: bàn sâu từng dòng, có ví dụ minh hoạ, TRƯỚC khi code.

### 2c. Tuyền trả lời — vòng 2 (14/10) → CHỐT
- **Đồng ý theo đề xuất:** Q1 Q2 Q3 Q4 Q6 Q7 Q9 Q10 Q11 Q13 Q15 Q17 Q18 · A (khoá sổ theo ca, sửa sau chốt = bút toán điều chỉnh ngày sửa) · B (hoàn mặc định theo hình thức gốc, đổi được) · C (xác minh CK nhập số ngân hàng thật nhận, lệch → cờ đối soát) · D (huỷ phiếu khi đã làm: bắt chọn ghi nợ / miễn + lý do) · E (trả thuốc bắt chọn hoàn tiền / đổi / giữ lại) · tách G4 thành G4b → G4a → G4d → G4c.
- **Q5:** sổ nợ hai chiều (phải thu / phải trả); "cứ thực tế xử lý các case nào thì hệ thống có thể có được" — mọi lối rò R1–R10 phải có chỗ ghi.
- **Tên cột báo cáo hàng hoá ĐẶT ĐÚNG TÊN KHÁCH ĐƯA** (Tồn đầu · Nhập trong ca · SL bán · Tồn cuối ca); số vẫn tính từ sổ kho cho khớp.
- **Q12b → OPEN:** kiểm đếm lúc nào cũng được (ca/ngày/tuần/đột xuất), trả về kho được, chuyển phòng ↔ phòng được — người thật làm được gì thì hệ ghi được nấy.
- **Q14b → mở rộng:** Bio (và vật tư nói chung) do phòng/bác sĩ chọn thì **quầy thu vẫn bỏ được** khi khách không mua nữa (trước khi thu, có lý do); đã thu → hoàn tác lần thu / hoàn tiền như cũ. Huỷ chỉ định → Bio đi kèm bỏ theo nếu chưa thu.
- **Q16 → OPEN tối đa:** kế toán đặt thuế suất theo NHÓM (dịch vụ / thuốc / vật tư), theo TỪNG mặt hàng, số % tự nhập (+ KCT, KKKNT), và sửa tay từng dòng lúc xuất. Thứ tự ưu tiên: sửa tay dòng > mặt hàng > nhóm > trống. Phiếu nhiều thuế suất: màn xuất có lựa chọn "tách theo thuế suất (mẫu 1 thuế suất)" hoặc "một hoá đơn (mẫu nhiều thuế suất — xin mẫu chị Hoài)".

### 2d. Mảng thuốc — vòng 3 (14/10) → CHỐT
- Walkthrough thuốc (mã vạch nhiều mã/thuốc, quét ở nhập/bán/kiểm, FEFO đổi được; lô không bắt buộc hạn + Sửa lô có lịch sử; cảnh báo ≤60 ngày chỉnh được + chuông hằng ngày; kiểm kê đầu/cuối ca nháp→chốt, kiểm một phần/đột xuất, "dùng số cuối ca trước", lệch → chuông, chưa tự sửa tồn, "Điều chỉnh theo kiểm kê" hoàn tác được; lần kiểm đầu = tồn mở đầu; G7 kho/quầy làm sau) — đồng ý.
- **T1:** lô đã hết hạn → **chặn bán** + nút "Huỷ lô hết hạn" (ghi `DISCARD` vào sổ kho).
- **T2:** "SL bán" tính lúc **giao tận tay** (DISPENSE), không lúc thu; cột "Đã thu chưa giao"; khách về không lấy → sổ phải trả khách.
- **Máy quét:** quầy ĐÃ CÓ máy quét. Code trước được: máy USB = bàn phím gõ dãy số + Enter → ô quét nhận "gõ nhanh + Enter", test bằng gõ tay; bấm thật bằng máy ở quầy trên staging. (Cần biết máy đọc được mã vuông 2D không.)
- **Camera (Tuyền hỏi):** (a) đọc mã vạch bằng camera điện thoại/máy tính bảng — thư viện chạy ngay trên máy, không gửi ảnh đi, cần HTTPS (prod/staging đã có); (b) mã vuông GS1 DataMatrix trên hộp (nếu có) chứa sẵn mã SP + số lô + hạn → quét là đủ, không cần AI; (c) hộp chỉ in chữ → AI đọc ảnh (đã có `src/clinicai/llm/anthropic_client.py` + sổ chi phí) tách số lô + hạn, **điền sẵn — người bấm xác nhận rồi mới lưu** (hạn đọc nhầm dính luật chặn hết hạn); ảnh lưu kèm lô làm bằng chứng.
- **T3 (CHỐT):** AI làm thì làm nhưng **con người quyết** (điền sẵn → người bấm Lưu); **mọi ảnh chụp lưu hết làm bằng chứng**.

### 2d+. Bảng "Báo cáo cuối ngày về hàng hoá" theo ghi chú Notion của khách (Tuyền gửi ảnh 14/10)
- Ghi chú khách: KHO chứa tất cả thuốc, nhập thì **dán nhãn từng lô, chip mã vạch, quản lý thời hạn**; QUẦY = quầy bán thực tế. Tồn đầu ca = kiểm thực tế (file Excel kiểm kê) → check chéo với hệ thống xem chênh lệch; kho chuyển sang quầy thì cộng vào "nhập trong ca". Bảng khách muốn: **Tồn đầu · Nhập trong ca · SL bán · Tồn cuối ca · Kiểm kê**.
- Bảng hiện có (`/reports` Hàng hoá, bản in): Mã hàng · Tên hàng · SL Bán · Doanh thu · SL Trả · GT trả · Doanh thu thuần — GIỮ, thêm cột tồn. Thứ tự cột chốt: Mã hàng · Tên hàng · **Tồn đầu · Nhập trong ca · SL bán · SL trả · Tồn cuối ca · Kiểm kê · Lệch** · Đã thu chưa giao · Doanh thu · GT trả · Doanh thu thuần. Tồn cuối ca = Tồn đầu + Nhập trong ca − SL bán + SL trả (theo sổ); Kiểm kê = số đếm cuối ca; Lệch = Kiểm kê − Tồn cuối ca. SL bán = số GIAO (T2); Doanh thu vẫn theo tiền thu, "Đã thu chưa giao" giải thích chỗ khác nhau.
- **Hệ quả thứ tự: G7 (tách kho/quầy) phải đi TRƯỚC G6 (kiểm kê ca).** Bảng của khách là tồn QUẦY; nếu chưa tách, nhân viên đếm kệ quầy nhưng máy so với tồn cả cơ sở (kho + quầy) → ca nào cũng lệch giả. Tuyền đã cho "làm sau theo thứ tự" — thứ tự đúng là G3 → G7 → G6.
- "Dán nhãn từng lô": ngoài quét mã in sẵn trên hộp, hỗ trợ **in tem mã vạch riêng cho từng lô** lúc nhập (tem chứa số lô + hạn) — quét tem ra đúng lô. Chờ biết phòng khám có máy in tem decal không (không có thì in tờ A4 tem dán).
- Dòng "Estrogel" mã hàng "—": thuốc chưa có mã KiotViet (14 mặt hàng ngoài file 08/10) — dữ liệu, chị Hà bổ sung mã trên màn.

### 2e. Mảng vật tư — vòng 4 (14/10) → CHỐT
Walkthrough vật tư đồng ý nguyên văn: danh mục (VPP/VTYT, kinh doanh/không, giá bán, giá nhập, ĐVT, mã vạch, cần duyệt bán/nhập — chị Hà sửa trên màn; nạp 84 dòng Excel, 3 mặt hàng có giá = kinh doanh); nơi chứa = kho cơ sở + từng phòng; phiếu nhập / xuất kho→phòng / phòng trả kho / phòng→phòng / kiểm đếm bất kỳ lúc / huỷ hỏng; tiêu hao = đầu + nhận − trả − cuối, kèm giá trị theo giá nhập; mức tối thiểu theo phòng → nhắc; bán thêm bắt ghi nguyên nhân, trừ tồn ở phòng làm dịch vụ (đổi được); duyệt bán (Trưởng ca/Quản lý) + phiếu nhập "chờ duyệt"; vật tư hết trên sổ vẫn xuất/bán được + cảnh báo "tồn âm" (thuốc giữ luật không bán quá tồn).
**Nguyên tắc chung Tuyền chốt:** "cứ mở open cho quản lý tinh chỉnh tuỳ ý" — mọi ngưỡng/cờ/mức (số ngày sắp hết hạn, mức tối thiểu, cờ duyệt, thuế suất…) là dữ liệu Quản lý sửa trên màn, không viết cứng.

### 2f. Kế toán + tài khoản — vòng 5 (14/10) → CHỐT, BẮT ĐẦU CODE
- Walkthrough kế toán đồng ý: sửa khách đủ trường + lịch sử sửa (Lễ tân/CSKH/Thu ngân/Kế toán/Quản lý); vai Kế toán (xem Dòng tiền đầy đủ, hoá đơn, xuất Excel, theo hàng hoá, sửa khách/công ty, đặt thuế; không thu tiền/cài đặt/nhân sự; Quản lý cấp thêm/bớt được); HĐ công ty theo hoá đơn, nhiều công ty/khách, điền sẵn lần trước, Lễ tân/CSKH ghi trước vào hồ sơ, MST sai chỉ nhắc; HĐ công ty bỏ SĐT/CCCD khách; **đánh dấu "đã xuất sang MISA"** + danh sách "có thay đổi sau khi xuất"; thống kê theo hàng hoá.
- **K1:** giá bảng giá ĐÃ GỒM thuế → khi xuất tách ngược (đơn giá chưa thuế = giá / (1 + t), làm tròn đồng, lệch làm tròn dồn dòng cuối để tổng = tiền khách trả). **Thuế KHÔNG tính tự động trong vận hành** (quầy, hoá đơn, báo cáo ngày không đụng thuế) — chỉ tính ở màn/xuất kế toán.
- **K2:** mặc định ghi tiền SAU giảm; thêm **nút bật "Ghi giảm giá trên hoá đơn"** ở màn xuất (bật → dòng giá gốc + dòng chiết khấu).
- Tài khoản (Q20) đồng ý như tóm tắt: tự đổi mật khẩu → đăng xuất máy khác; Quản lý đặt lại (đã có); "Khoá & nghỉ việc" một nút, giữ hết dữ liệu, mở lại được; không tự khoá / không khoá người cuối có quyền cấp quyền; ca trực tương lai → danh sách, Quản lý chọn gỡ/giữ; 4 màn quản lý → hướng dẫn + cấp lego chị Hà.

## 3. Chia gói (mỗi gói = 1 nhánh = 1 PR = 1 dải migration)

| Gói | Nội dung | Mức | Ai | Chờ gì | Dải migration | Cổng web/API |
|---|---|---|---|---|---|---|
| **G1** | Sửa hồ sơ khách đủ trường (F1) + CCCD + **email** (cột `patient.email`) | 2 | Codex | **SẴN** | 20261014110000–119999 | 3211/8211 |
| **G2** | Tự đổi mật khẩu + nút "Khoá & nghỉ việc" + chặn tự xoá + đăng xuất phiên | 2–3 | Codex | Q20 (mặc định đề xuất) | 20261014120000–129999 | 3212/8212 |
| **G3** | Lô thuốc không bắt buộc hạn (kế hoạch 08/10 đã chốt) + mã vạch EAN + cảnh báo lô sắp hết hạn | 3 | Codex | Q7 | 20261014130000–139999 | 3213/8213 |
| **G4b** | Sổ nợ hai chiều (phải thu / phải trả), append-only, nạp ngược, không hạn 90 ngày | 3 | **Claude** | CHỐT | 20261014140000–144999 | 3214/8214 |
| **G4a** | Báo cáo Dòng tiền: đổi chữ, công thức, TM/CK mỗi mục, link sang `/hoa-don`, đúng/không đúng, khối sổ nợ, sửa F3 | 3 | **Claude** | sau G4b | 20261014145000–146999 | 3214/8214 |
| **G4d** | Vá rò R1 R2 R3 R6 (CK nhập số thật nhận + giữ lần CK huỷ; huỷ sau khi làm → ghi nợ/miễn; trả thuốc ↔ hoàn; hoàn theo hình thức gốc) | 3 | **Claude** | sau G4b | 20261014147000–148999 | 3220/8220 |
| **G4c** | Khoá sổ theo ca (sửa sau chốt = điều chỉnh ngày sửa) | 3 | **Claude** | sau G4a | 20261014149000–149999 | 3214/8214 |
| **G5** | Kế toán: vai Kế toán, HĐ công ty, thuế GTGT, ẩn thông tin cá nhân, thống kê theo hàng hoá | 3 | **Claude** | Q15–Q19, sau G1 | 20261014150000–159999 | 3215/8215 |
| **G7** | Tách kho/quầy + phiếu chuyển kho→quầy, quầy trả kho, "kho còn N — chuyển sang?" | 3 | Codex | CHỐT, sau G3 — **đi TRƯỚC G6** (mục 2d+) | 20261014170000–179999 | 3217/8217 |
| **G6** | Kiểm kê đầu/cuối ca ở QUẦY + bảng hàng hoá đủ cột (mục 2d+) + link | 3 | Codex | sau G7; mẫu Excel kiểm kê (anh Thắng) bổ sung sau | 20261014160000–169999 | 3216/8216 |
| **G8** | Vật tư: phân loại, kho + theo phòng, xuất dùng, nhập, duyệt, màn danh mục sửa cờ | 3 | Codex | Q11–Q13 | 20261014180000–189999 | 3218/8218 |
| **G9** | Bio vào chỉ định CLS | 3 | Claude (luồng tiền) | Q14, sau G8 | 20261014190000–199999 | 3219/8219 |

**Đụng chung file — thứ tự để không đè nhau:**
- G4 và G6 cùng `bao_cao_cuoi_ngay_service.py` → G6 chỉ THÊM hàm mới ở `kho_thuoc_service.py` + một chỗ gắn ở `gom_hang_hoa`; rebase sau G4 merge.
- G4 và G5 cùng `report_access_service.py` + `danh_sach_hoa_don_service.py` → G5 xếp chồng lên G4 (nhánh G5 tạo từ nhánh G4), hoặc G5 làm phần quyền trước rồi G4 rebase. Chọn: **G5 xếp chồng G4**.
- G3 → G6 → G7 cùng kho thuốc: tuần tự.
- G8 → G9 cùng vật tư: tuần tự.
- G1 → G5 (G5 dùng `patient.email`).

**Trước khi tạo migration:** máy hiện **không kết nối được github.com** (fetch lỗi DNS 14/10) — sửa mạng, `git fetch origin`, soát lại mọi `origin/dot/*` + nhánh đang chạy staging theo memory `trung-so-migration-giua-cac-dot`; dải 20261014* đang trống trên ref local.

## 4. Từng gói — kết quả cần đạt · case biên · test

### G1 — Sửa hồ sơ khách (SẴN)
- Đạt: sửa địa chỉ/giới tính/… → mở lại vẫn còn; CCCD + email sửa được; chỉ gửi trường ĐÃ ĐỔI (SĐT cũ dạng lạ không chặn lần lưu khác); lỗi thật thì màn báo lỗi, không báo "Đã lưu".
- Case: SĐT Notion lạ (02…, có dấu cách) — chuẩn hoá phía máy chủ, hai bên (`core/phone.py` ↔ `lib/validation.ts`) cùng một luật; email rác → 422 câu tiếng Việt; hai người cùng sửa (`sua_luc` đã có) → 409; khách đã gộp.
- Test: mới `src/tests/services/test_sua_ho_so_khach_db.py` (gửi address → đọc lại đúng; rác; 409); sửa `test_patient_service.py`; FT `patient-boundary.test.mts`.

### G2 — Tài khoản
- Đạt: menu cá nhân "Đổi mật khẩu" (mật khẩu cũ + mới ≥ 8, nhập lại); Quản lý "Khoá & nghỉ việc" một nút ở `/settings/tai-khoan` = `deactivate` + `thu_hoi` trong một luồng; lịch sử vẫn tên người đó; nhật ký ghi ai làm.
- Case: tự khoá chính mình → chặn; người cuối cùng có quyền cấp quyền → chặn (`giu_nguoi_cap_quyen`); người có ca trực tương lai → cảnh báo; đổi mật khẩu → phiên cũ trên máy khác bị đăng xuất (kiểm GoTrue `/logout?scope=others` hoặc admin signOut — xác minh trên dev stack, đừng đoán).
- Test: `test_tai_khoan_db.py` (+ tự khoá, người cuối), `test_staff_service.py`; FT `service-role-boundary.test.mts`.

### G3 — Lô không hạn + mã vạch + cảnh báo hạn
- Theo memory `lo-thuoc-that-khong-han-0810` (danh sách chỗ sửa có sẵn) + cột `drug_catalog.ma_vach` (UNIQUE theo phòng khám, cho NULL) + ô quét autofocus bắt Enter ở màn bán/nhập/kiểm.
- Case: mã vạch không có trong danh mục → "chưa gắn mã — gắn cho thuốc nào?"; một mã nhiều lô → FEFO, lô không hạn xếp CUỐI; lô hết hạn không gợi ý; lô NULL hạn: chip xám, không cảnh báo; `fmtNgay(null)` không ra 01/01/1970.
- Cảnh báo: thêm khoá đếm "lô sắp hết hạn ≤ 60 ngày" vào `canh_gac.do_so` (chỉ số đếm, không tên khách).
- Test vỡ biết trước: `test_cua_ngo_ghi_moi.py:238`; test tạo lô có `expiry_date` (`test_kho_*`, `test_tien_thuoc_cp*`). Mới: `test_lo_khong_han_db.py`, `test_ma_vach_db.py`.

### G4 — Dòng tiền (Claude)
- **Bước 0 (verifier trước code):** viết `src/tests/services/test_doi_soat_bang_vang_db.py` theo đúng bảng vàng 5.1, Tuyền duyệt bảng số → test đỏ → mới code.
- Lược đồ: bảng `cong_no_but_toan` (append-only, trigger cấm UPDATE/DELETE, RLS theo phòng khám, `trg_notify`): GHI / DIEU_CHINH (ghi lại) / HUY / THU (gắn `payment_cycle_id`). Ghi trong CÙNG giao dịch với `CongNoService.ghi/huy` và lần thu đóng nợ. Nạp ngược từ `domain_event` (`cong_no.ghi`, `cong_no.da_thu`) — migration dữ liệu tách riêng, chạy hai lần không đổi thêm.
- Màn: đổi chữ ở `TomTatCuoiNgay.tsx`, `excel_report_export.py:62-72, 244-255`, `reports/page.tsx:471`; mỗi mục có TM/CK + link `/hoa-don?tu=&den=&ca=&co_so=&loai=&nhom=` (nhom: tra_lai / giam_gia / no_ghi / no_thu / doi_hinh_thuc / khong_dung).
- `/hoa-don`: đọc query URL; thẻ đếm "Đúng N · Không đúng M"; lọc `nhom`.
- Case: huỷ sau nửa đêm (huỷ tính NGÀY HUỶ hay ngày thu? hiện là ngày thu — giữ, ghi rõ trên màn); hoàn tạo hôm nay xong hôm sau (báo cáo dùng `created_at`, `/hoa-don` dùng `completed_at` → **thống nhất về một mốc**, đề xuất `completed_at`); đổi hình thức hôm sau làm số TM/CK hôm trước đổi (đã ghi sổ đổi hình thức — tính theo mốc đổi); miễn phí 100% (thu 0đ ≠ hoàn); nợ đóng bằng giảm 100% ("thu 0đ, giảm X" — #415); nợ ghi rồi huỷ trong ngày; ghi lại nợ số khác; đối tác thu hộ ngoài thực thu; liệu trình trả trước; tiền thừa; lọc ca SANG/CHIEU/TOI; hai cơ sở.
- Test vỡ biết trước: `test_tom_tat_tai_chinh.py:25`, `test_tom_tat_tai_chinh_db.py:27`, `test_excel_export.py:109-112,304-313`; e2e `reports-summary.mjs`. Liên quan: `test_bao_cao_cuoi_ngay*.py`, `test_bao_cao_cuoi_ca_db.py`, `test_danh_sach_hoa_don*_db.py`, `test_giam_gia_db.py`, `test_cong_no_check_out_db.py`, FT `danh-sach-hoa-don-boundary.test.mts`.

### G5 — Kế toán (Claude, xếp chồng G4, sau G1)
- Vai `KE_TOAN` (CHECK `staff_primary_department_check`, `ClinicRole`, preset, `report_access.access()` cho tài chính); HĐ công ty theo `payment_cycle` (bảng `hoa_don_cong_ty`: tên, địa chỉ, MST, email nhận HĐ, snapshot lúc tick) + mặc định theo khách; `vat_rate` (KCT/0/5/8/10) trên `service_price`, `drug_catalog`; ghi cột K/L MISA; HĐ công ty → C=tên cty, D=địa chỉ cty, E=MST, H/I trống; tab "Theo hàng hoá" ở `/xuat-hoa-don` + Excel.
- Case: MST sai (10 số hoặc 10 số + "-001…") → trả rỗng + báo, có test rác; đổi thông tin công ty sau khi đã xuất → snapshot trên hoá đơn không đổi, ghi lịch sử sửa; một phiếu nhiều thuế suất (theo Q16); dịch vụ chưa đặt thuế → ô trống + đếm "N dòng chưa có thuế suất"; kế toán không thấy nút thu tiền.
- Test: `test_xuat_hoa_don.py`, `test_xuat_hoa_don_db.py`, `test_report_access_db.py` (+ vai KE_TOAN), FT `xuat-hoa-don-boundary.test.mts`, `cua-quyen-lego-boundary.test.mts`.

### G6 — Kiểm kê ca thuốc (sau G3, chờ mẫu Excel)
- Bảng `kiem_ke_ca` (cơ sở, ngày, ca, DAU/CUOI, trạng thái NHAP→CHOT, người đếm, giờ) + dòng (lô, tồn máy lúc chốt, đếm, lệch); điều chỉnh là bước riêng ghi `ADJUST` có lý do, hoàn tác được.
- Báo cáo hàng hoá: `xuat_nhap_ton` nhận mốc giờ từ `khung_chot_ca`; cột Tồn đầu / Nhập / SL bán / Trả về / Tồn cuối máy / Đếm cuối ca / Lệch + link sang phiếu kiểm.
- Case: hai người mở kiểm cùng ca → một phiếu (unique cơ sở+ngày+ca+loại); có bán giữa lúc đếm → tồn máy chốt tại giờ CHỐT, ghi rõ; quên đầu ca → nhắc; trả thuốc sau ca → cộng vào ca nhận lại; ca TỐI kết thúc 24:00.
- Test mới: `test_kiem_ke_ca_db.py`, `test_xnt_theo_ca.py` (hàm thuần mốc giờ, đầu vào rác → rỗng).

### G8 — Vật tư (Codex) / G9 — Bio (Claude)
- G8: tách bảng riêng `vat_tu_ton` (mặt hàng × vị trí: kho cơ sở hoặc phòng `clinic_room`) + sổ `vat_tu_txn` append-only (NHAP / XUAT_PHONG / BAN / DIEU_CHINH / HUY) — **không** nới bảng thuốc (FK, hạn, lô thiết kế cho thuốc). Tái dùng khuôn phiếu/mã phiếu/khoá chống gửi trùng của `kho_thuoc_service`. Cột mới ở danh mục: `loai` (VPP/VTYT), `kinh_doanh`, `can_duyet_ban`, `can_duyet_nhap`, `gia_nhap`. Duyệt mở cho Trưởng ca (Q11) → sửa trigger `luot_vat_tu_gac`. Bán thêm ở quầy bắt buộc "nguyên nhân bán thêm".
- G9: `luot_vat_tu.order_id` (NULL cho dòng cũ); chọn Bio ở khối chỉ định CLS bàn khám; `huy_chi_dinh` bỏ luôn Bio; tiền theo cổng `thu_truoc_khi_lam`.
- Case: bán khi tồn không đủ (vật tư không chặn bán — chỉ cảnh báo? hỏi kèm Q12); hoàn tác lần thu có vật tư → trả tồn; Bio cũ đã thu không di chuyển; 2 cơ sở.
- Test: `test_vat_tu_ban_them_db.py` (12 test hiện có — giữ xanh), mới `test_vat_tu_kho_db.py`, `test_bio_chi_dinh_db.py`; FT `quay-thu-vat-tu-boundary.test.mts`.

## 5. Test, dữ liệu, CI — làm một lần, không lặp

### 5.1 Bảng vàng đối soát (Tuyền duyệt số TRƯỚC khi G4 code)
Ngày 1 — A: hoá đơn 1.000.000, giảm 100.000, thu 500.000 TM, ghi nợ 400.000 · B: thu 300.000 CK, huỷ (nhầm), thu lại 300.000 TM · C: thu 200.000 CK, khách đổi ý, hoàn 200.000 CK. Ngày 2 — A trả nợ 400.000 CK.

| Mục | Ngày 1 | TM / CK | Ngày 2 | TM / CK |
|---|---|---|---|---|
| Dòng tiền vào (trước giảm, gồm nợ) | 1.800.000 | — | 0 | — |
| Trả lại tiền khách (huỷ + hoàn) | 500.000 | 0 / 500.000 | 0 | |
| Nợ ghi | 400.000 | — | 0 | |
| Giảm giá | 100.000 | — | 0 | |
| Nợ thu được | 0 | | 400.000 | 0 / 400.000 |
| **Thực thu** = DTV − trả lại − nợ − giảm + nợ thu | **800.000** | 800.000 / 0 | **400.000** | 0 / 400.000 |
| Doanh thu thuần = DTV − giảm − trả lại (Q3) | 1.200.000 | | 0 | |
| Hoá đơn đúng / không đúng (Q5) | 2 (A, B thu lại) / 2 (B bị huỷ, C hoàn) | | 1 (A trả nợ) / 0 | |

Kiểm chéo: tiền thật trong két ngày 1 = 500.000 + 300.000 TM = 800.000; CK = 300 − 300 + 200 − 200 = 0 ✔. Cách đọc khách "DTV − trả lại" = 1.300.000, "doanh thu − giảm" = 1.700.000 → hai vế không bằng nhau (lý do có Q3).
*Câu nhỏ kèm Q5:* phiếu B thu lại là "đúng" hay cả cặp B tính "không đúng"? Đề xuất (đã điền ở bảng): phiếu bị huỷ = không đúng, phiếu thu lại = đúng.
Thêm 3 ca vào bảng vàng: nợ đóng bằng giảm 100% (thu 0đ, giảm 400.000 → nợ thu 400.000, giảm 400.000, thực thu 0); ghi nợ rồi ghi lại số khác cùng ngày; đổi hình thức TM→CK ngày hôm sau.

### 5.2 Kiểm khi code — đúng 2 bước (memory `chay-test-nhanh-0710`)
1. `scripts/test-nhanh.sh <tệp test mới + 1–2 tệp trực tiếp>` (DB tạm từ khuôn sạch, tự áp migration của nhánh) + `mypy <tệp vừa sửa>`; frontend `npx tsc --noEmit` + đúng tệp FT. **Không** chạy tay loạt test cũ, **không** diễn tập migration tay, đỏ nghi môi trường → để CI phân xử.
2. Xong gói: `python3 scripts/ban-do-code.py` (nếu đổi route/router) → `./scripts/ci-may.sh --bao-github` **một lần** (có khoá xếp hàng; mã 3 = bận, chạy lại). CI đỏ → sửa đúng chỗ đỏ → CI lại.

### 5.3 Dữ liệu
- Test tự dựng dữ liệu trong fixture (không dựa dữ liệu DB chung). Bảng vàng là test DB đầy đủ luồng thật (gọi service thu/huỷ/hoàn/ghi nợ, không INSERT tắt).
- Migration nạp ngược (sổ nợ, phân loại vật tư): tách (A) cấu trúc / (B) dữ liệu; (B) idempotent, có SQL đếm trước/sau ghi trong thân PR. Diễn tập thật = trên bản sao prod lúc lên staging (skill `len-prod`).
- Không bấm trình duyệt local (memory `tiet-kiem-token-bo-bam-local-0610`) — Tuyền bấm staging theo kịch bản trong thân PR.

### 5.4 Staging → prod
Một đợt gồm các gói đã xanh (`dot/1410-…`), gộp ở MỘT worktree, kiểm bản đang chạy trước khi deploy (memory `staging-khong-de-mat-tinh-nang-da-len-1310`); staging nạp lại 03:30 → kịch bản bấm phải ghi bước bật dây/dữ liệu cần có. Kiểm `git status` sạch trên VPS TRƯỚC khi áp migration prod (bẫy 13/10).

## 6. Thứ tự đề xuất

1. **Ngay (không chờ câu hỏi):** Codex làm G1; Claude viết bảng vàng G4 khi có Q1–Q5.
2. Có câu trả lời: Claude G4 → G5 (xếp chồng); Codex G2, G3 song song.
3. Có mẫu kiểm kê + Q9/Q10: Codex G6. Có Q11–Q13 + phân loại: Codex G8 → Claude G9.
4. G7 (kho/quầy) sau một tuần chạy kiểm kê.

## 7. Đầu vào phòng khám còn thiếu
Mẫu Excel kiểm kê thuốc + vật tư đầu/cuối ca (anh Thắng) · tài khoản xem mẫu KiotViet (chị Hà gửi Thu) · danh sách nhân viên · thuế suất từng dịch vụ/thuốc (kế toán) · trả lời Q16/Q19 của chị Hoài · phân loại vật tư (Q13) · quầy có máy quét mã vạch chưa (Q7) · ảnh "vị trí sửa cụ thể" của form đối soát (recap ghi có ảnh — chưa nhận được).

## 8. VIỆC CHƯA XEM / ĐỂ ĐỢT SAU — nhắc lại đầu phiên tới
(Gom từ memory + phiên 14/10. Xong mục nào thì gạch.)
- [ ] Trả lời nốt câu ở mục 2 chưa chốt (xem 2b — vòng 1 đã trả lời Q5 Q8 Q12 Q14 Q16 Q19 Q20 Q21).
- [ ] G7 tách kho/quầy: làm sau G6 nhưng BẮT BUỘC (Tuyền 14/10) — đừng để rơi.
- [ ] Commit tệp kế hoạch: 2 lần bị auto mode chặn 14/10 (rebase vướng `.agents/skills/len-prod/SKILL.md` chưa theo dõi, trùng y hệt bản trên main) — commit khi bàn xong.
- [ ] Nhãn "Đang ghi nợ" + dòng thời gian "thu 0đ, giảm X" (#415) chưa ai bấm thử ở 375/1280 — đã lên prod 14/10.
- [ ] PR #410 (ô Giảm giá ở báo cáo) nền cũ, xung đột 5 file báo cáo với main → rebase hoặc đóng (G4 sẽ thay phần này).
- [ ] PR chưa vào đợt nào: #397 #393 #389 #388 #387 #372 #370 #364 — quyết vào đợt 14/10 hay đóng.
- [ ] Sự cố 14/10 09:11 DB prod tắt sạch — **chưa biết ai/cái gì dừng**; rollback `deploy-backend.sh` không đáng tin vì ảnh cũ bị dọn (việc mức 3: giữ ảnh bản trước bằng tag cố định).
- [ ] Quầy thu: gom N+1 (~17ms/lượt), `tien_thua_service._DONG_THUA_SQL` quét mọi dòng (sau #417).
- [ ] Tài khoản "Quản lý hệ thống" từng thu tiền tại quầy → nhắc nhân viên dùng tài khoản riêng (G2/G5 làm xong thì sổ mới đúng người).
- [ ] Hướng dẫn cho khách 4 màn quản lý đã có (Q21) — soạn tài liệu ngắn khi Tuyền chốt.
- [ ] Mạng máy dev không tới github.com (14/10) — kiểm lại trước khi tạo nhánh/push.
- [ ] `docs/DANG-LAM.md` dừng ở 08/10 — cập nhật khi kết phiên (skill `ket-thuc`).
