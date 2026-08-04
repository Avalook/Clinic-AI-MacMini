# Spec — Bộ khám Nam khoa (`NK` / `exam_andrology_v1`)

> Trạng thái: **ĐỀ XUẤT — chưa được bác sĩ duyệt.** Đây là bản thiết kế để code, không
> phải bản đã thông qua chuyên môn. Mọi mục gắn `[ĐỀ XUẤT]` phải có chữ ký bác sĩ
> trước khi bật form. Xem §9.
>
> Ngày soạn: 2026-08-04 · Nguồn y văn: xem §10

---

## 1. Vì sao có tài liệu này

`NK` là 1 trong 5 dịch vụ khám của phòng khám (cùng PK/SK/NT/HMVS), đặt lịch được qua
`service_type.NAM_KHOA`, nhưng **không lưu được hồ sơ khám**:

| Chặn ở đâu | Trạng thái |
|---|---|
| [20260730000017_quarantine_unapproved_clinical_forms.sql](../supabase/migrations/20260730000017_quarantine_unapproved_clinical_forms.sql) | `clinical_form_catalogue.is_active = FALSE` cho `NK` |
| [src/dashboard/lib/form-schemas/index.ts](../src/dashboard/lib/form-schemas/index.ts) | registry chỉ đăng ký PK/SK/NT/HMVS |
| Notion `KHAM-NAMKHOA` | form ghi là `exam_andrology_v0-draft` |

Lý do quarantine, nguyên văn trong migration: *NK was assembled from the male sections of
the HMVS handover document* — tức nó không có tài liệu nguồn riêng được bác sĩ duyệt.

**Tài liệu bàn giao của phòng khám ([docs/forms/handover_kham.docx](forms/handover_kham.docx))
đến hôm nay vẫn chỉ có 4 mục: Nội tiết, HMVS, Phụ khoa, Sản.** Nam khoa nằm rải trong HMVS
đúng 3 mảnh:

1. "Tiền sử Sản khoa (chồng)" — 5 dòng
2. "Khám nam khoa" — 4 dòng
3. "C. Tinh dịch đồ (Chồng)" — 9 thông số

Spec này giữ nguyên 3 mảnh đó làm lõi (`[GỐC]`) và đề xuất phần còn thiếu từ hướng dẫn
quốc tế (`[ĐỀ XUẤT]`), để bác sĩ chỉ phải duyệt phần mới thay vì soạn lại từ đầu.

### 1.1 Một lỗ hổng lớn hơn cái form

Kiểm tra DB (prod-shaped local, 2026-08-04):

```
node_definition:  DICHVU-TINHDICHDO | Tinh dịch đồ     ← node CÓ tồn tại
service_price:    0 dòng khớp 'TINH|NAM|HORMONE|KARYO|TESTOS'   ← KHÔNG có dịch vụ nào
```

`DICHVU-TINHDICHDO` là **node chết**: không dịch vụ nào trỏ vào, nên `order_services()`
không bao giờ tạo được việc cho phòng xét nghiệm tinh dịch đồ. Nghĩa là kể cả khi form NK
chạy, bác sĩ **vẫn không chỉ định được xét nghiệm nam khoa nào** — vì `order_services()`
từ chối dịch vụ không có trong danh mục (thiết kế cố ý, xem
[20260801000002](../supabase/migrations/20260801000002_order_services.sql)).

→ Phải làm §6.1 (bổ sung danh mục dịch vụ nam khoa) **cùng lúc** với form, không thì form
là một tờ giấy không nối vào đâu.

---

## 2. Ràng buộc từ hệ thống hiện tại

Đọc kỹ trước khi code — spec này được viết vừa khít với các ràng buộc dưới đây.

### 2.1 Engine form chỉ có 8 kiểu field

[types.ts](../src/dashboard/lib/form-schemas/types.ts):
`text · textarea · number · date · radio · checkbox · checkbox_group · conditional`

**Không có kiểu bảng/lặp.** Tinh dịch đồ của phòng khám là bảng 2 cột (lần 1 / lần 2).
Với engine hiện tại phải làm phẳng bằng hậu tố `_l1` / `_l2`. Xem §5.6 — đây là chỗ tốn
field nhất và là lý do duy nhất đáng cân nhắc thêm kiểu field mới (§7.2).

### 2.2 Logic không được nằm trong TSX

[CLAUDE.md](../CLAUDE.md) và [ADR-0012](adr/0012-hop-dong-backend-frontend-thay-duoc.md):
router mỏng, logic ở service function Python thuần. Nên **tất cả** phần tính toán của form
này (điểm IIEF-5, BMI, gắn cờ bất thường theo ngưỡng WHO, gợi ý xét nghiệm di truyền) nằm
ở FastAPI — frontend chỉ render và hiển thị kết quả trả về.

### 2.3 Form chỉ bật khi có bản ghi duyệt

Comment của migration quarantine: *clinical forms must remain inactive until the clinic
records doctor approval*. Hôm nay **chưa có chỗ nào để ghi cái approval đó** — chỉ có cờ
`is_active`. Lật cờ mà không ghi ai duyệt là làm sai đúng điều migration dặn. Xem §6.2.

### 2.4 Dữ liệu nam khoa trong bối cảnh cặp đôi

Notion `KHAM-NAMKHOA` §13: *ClinicDocument của người bệnh nam là nguồn sự thật; couple case
chỉ giữ liên kết được consent.* Hồ sơ NK mở từ luồng HMVS vẫn phải thuộc hồ sơ người chồng,
và không được hiển thị cho vợ nếu chưa có consent. Xem §6.5.

---

## 3. Ba nhánh sử dụng — không chỉ hiếm muộn

Bằng chứng phòng khám khám nam khoa rộng hơn vô sinh:

- `service_type.NAM_KHOA` đặt lịch độc lập, **không** bắt buộc qua BS Thành
  (theo [Tiêu chí phòng khám theo bộ phận](https://app.notion.com/p/3a7ccb0eac88802aa888f96e16ebf4be))
- `drug_catalog` nhóm **L9**: ZinC, CoQ10, **Tadalafil 20 / 5 mg**, Menserona, Fersen,
  Durapil, **Avanafil (Flepgo 100)** — nhóm thuốc rối loạn cương + hỗ trợ sinh sản nam

Nên form phải phục vụ 3 nhánh, chọn ở section đầu và dùng `parent` để ẩn/hiện:

| Nhánh | Mã | Section bắt buộc |
|---|---|---|
| Hiếm muộn / vô sinh nam | `HM` | 1,2,4,5,6,7,8,9,10,11 |
| Rối loạn tình dục (cương / xuất tinh) | `RLTD` | 1,2,3,4,5,7,9,10,11 |
| Khám sức khỏe sinh sản / tiền hôn nhân | `SKSS` | 1,2,4,5,6,9,11 |

---

## 4. Quy ước đặt tên

- `service_code` = `NK`, `form_schema` = `exam_andrology_v1`
- File: `src/dashboard/lib/form-schemas/nk.ts`, export `nkSchema`
- Key field: snake_case không dấu, tiền tố theo section (`ts_` tiền sử, `kls_` khám lâm sàng,
  `tdd_` tinh dịch đồ, `nt_` nội tiết, `cls_` cận lâm sàng khác)
- Bên T = trái, P = phải → hậu tố `_t` / `_p`

---

## 5. Cấu trúc form

Ký hiệu: **`[GỐC]`** có trong tài liệu bàn giao · **`[ĐỀ XUẤT]`** từ y văn, cần BS duyệt

### 5.0 — Lý do khám & nhánh

| key | label | type | options / ghi chú |
|---|---|---|---|
| `nhanh` | Nhánh khám | radio | `HM` Hiếm muộn–vô sinh · `RLTD` Rối loạn tình dục · `SKSS` Sức khỏe sinh sản | `[ĐỀ XUẤT]`
| `ly_do` | Lý do khám | checkbox_group | chưa có con · rối loạn cương · xuất tinh sớm · giảm ham muốn · tinh dịch đồ bất thường · đau/sưng bìu · viêm nhiễm · khám tiền hôn nhân · theo yêu cầu vợ đang điều trị HMVS | `[ĐỀ XUẤT]`
| `ly_do_khac` | Khác | text | fullWidth |
| `lien_ket_hmvs` | Thuộc hồ sơ cặp đôi HMVS | checkbox | bật ⇒ backend gắn `couple_case_id`, xem §6.5 | `[ĐỀ XUẤT]`

### 5.1 — Tiền sử sinh sản `[nhánh HM]`

| key | label | type | ghi chú |
|---|---|---|---|
| `ts_thoi_gian_mong_con` | Thời gian mong con | number, unit `tháng` | `[ĐỀ XUẤT]` — mốc 12 tháng (hoặc 6 nếu vợ ≥35) là định nghĩa vô sinh, đã dùng ở form HMVS
| `ts_co_con` | Đã có con | radio | chưa · có với bạn đời hiện tại · có với người khác | **`[GỐC]`** ("Tiền sử có con trước")
| `ts_so_con` | Số con | number | parent: `ts_co_con` ≠ chưa
| `ts_tan_suat_qh` | Tần suất giao hợp | radio | <1 lần/tuần · 1–2 · 3–4 · >4 | `[ĐỀ XUẤT]` — AUA yêu cầu ghi coital frequency/timing
| `ts_dung_boi_tron` | Dùng chất bôi trơn | checkbox | `[ĐỀ XUẤT]`
| `ts_dieu_tri_hm` | Đã điều trị hiếm muộn | checkbox_group | chưa · thuốc · IUI · IVF/ICSI · phẫu thuật | `[ĐỀ XUẤT]` (đối xứng với form HMVS đã có)

### 5.2 — Tiền sử bệnh & phơi nhiễm

Năm dòng đầu là **`[GỐC]`**, nguyên văn từ tài liệu bàn giao:

| key | label | type |
|---|---|---|
| `ts_benh_sinh_duc_tiet_nieu` | Bệnh lý sinh dục / tiết niệu | textarea | **`[GỐC]`**
| `ts_phau_thuat` | Phẫu thuật vùng bìu / bẹn / tuyến tiền liệt | textarea | **`[GỐC]`**
| `ts_quai_bi` | Quai bị có biến chứng | radio (không/có/không rõ) | **`[GỐC]`**
| `ts_nghe_nghiep` | Nghề nghiệp / tiếp xúc hóa chất / nhiệt độ cao | textarea | **`[GỐC]`**

Bổ sung `[ĐỀ XUẤT]` — theo AUA/ASRM Appendix I và EAU 2025, đây là các nguyên nhân có thể
đảo ngược mà bỏ sót thì mất luôn cơ hội điều trị:

| key | label | type | vì sao |
|---|---|---|---|
| `ts_tinh_hoan_an` | Tinh hoàn ẩn / xuống bìu muộn | radio (không/T/P/hai bên) | nguyên nhân sinh tinh kém thường gặp
| `ts_xoan_chan_thuong` | Xoắn tinh hoàn / chấn thương bìu | radio |
| `ts_hoa_xa_tri` | Hóa trị / xạ trị | radio + `conditional` chi tiết | gonadotoxin
| `ts_thuoc_dang_dung` | Thuốc đang dùng | textarea | **testosterone ngoại sinh gây vô tinh** — bỏ sót là chẩn đoán nhầm NOA
| `ts_testosterone_ngoai` | Đang/đã dùng testosterone, steroid đồng hóa | radio (không/đang/đã ngưng <6th/đã ngưng ≥6th) | tách riêng vì hậu quả nặng
| `ts_thuoc_lá` / `ts_ruou` | Hút thuốc · Rượu bia | radio |
| `ts_benh_toan_than` | ĐTĐ · THA · rối loạn mỡ máu · bệnh tuyến giáp · béo phì | checkbox_group | EAU 2025 gắn vô sinh nam với nguy cơ tim mạch–chuyển hóa
| `ts_nhiem_trung` | Lao · bệnh lây qua đường tình dục · viêm mào tinh | checkbox_group |
| `ts_thoat_vi_ben` | Mổ thoát vị bẹn | radio | nguy cơ tổn thương ống dẫn tinh
| `ts_di_ung` | Dị ứng thuốc | text | đồng bộ với 4 form kia

### 5.3 — Tiền sử tình dục `[nhánh RLTD]` `[ĐỀ XUẤT]`

| key | label | type | ghi chú |
|---|---|---|---|
| `td_iief5_q1..q5` | 5 mục IIEF-5 | radio 1–5 mỗi mục | **xem cảnh báo bản quyền §9.4**
| `td_iief5_tong` | Tổng điểm IIEF-5 | (read-only, backend tính) | 22–25 không RLC · 17–21 nhẹ · 12–16 nhẹ–vừa · 8–11 vừa · 5–7 nặng
| `td_xuat_tinh` | Kiểu xuất tinh | radio | bình thường · sớm · muộn · không xuất tinh · nghi ngược dòng |
| `td_ielt` | Thời gian đến khi xuất tinh (ước tính) | number, unit `phút` |
| `td_ham_muon` | Ham muốn tình dục | radio (bình thường/giảm/tăng) |
| `td_cuong_sang` | Cương buổi sáng | radio (còn/giảm/mất) | phân biệt nguyên nhân thực thể vs tâm lý

### 5.4 — Khám toàn thân `[ĐỀ XUẤT]` (theo AUA Appendix I, mục *General*)

| key | label | type |
|---|---|---|
| `kls_chieu_cao` · `kls_can_nang` | Chiều cao · Cân nặng | number (cm · kg) |
| `kls_bmi` | BMI | read-only, backend tính |
| `kls_huyet_ap` · `kls_mach` | Huyết áp · Mạch | text · number |
| `kls_nam_hoa` | Phát triển sinh dục thứ phát / nam hóa | radio (bình thường/kém/không đánh giá) |
| `kls_vu_to` | Vú to nam giới (gynecomastia) | radio (không/T/P/hai bên) | dấu chỉ rối loạn nội tiết
| `kls_seo_bung_ben` | Sẹo mổ vùng bụng / bẹn | text |

### 5.5 — Khám bộ phận sinh dục

Bốn dòng gốc, mở rộng thành trường có cấu trúc để đo được và so sánh được giữa các lần khám:

**Dương vật / niệu đạo** — **`[GỐC]`** (1 dòng) → tách:

| key | label | type |
|---|---|---|
| `kls_lo_tieu` | Vị trí lỗ tiểu | radio (bình thường · lỗ tiểu thấp · lỗ tiểu trên) | `[ĐỀ XUẤT]`
| `kls_mang_xo_dv` | Mảng xơ cứng dương vật (Peyronie) | radio (không/có) + `conditional` mô tả | `[ĐỀ XUẤT]`
| `kls_ton_thuong_dv` | Tổn thương / loét / dịch tiết niệu đạo | radio + `conditional` | `[ĐỀ XUẤT]`
| `kls_bao_quy_dau` | Bao quy đầu | radio (bình thường · hẹp · dài · đã cắt) | `[ĐỀ XUẤT]`

**Tinh hoàn** — **`[GỐC]`** ("Tinh hoàn T/P (thể tích, mật độ)"):

| key | label | type |
|---|---|---|
| `kls_th_vi_tri_t` / `_p` | Vị trí tinh hoàn T / P | radio (trong bìu · ống bẹn · không sờ thấy) | `[ĐỀ XUẤT]`
| `kls_th_the_tich_t` / `_p` | Thể tích T / P | number, unit `mL` | **`[GỐC]`**
| `kls_th_pp_do` | Phương pháp đo thể tích | radio (thước Prader · siêu âm · ước lượng) | `[ĐỀ XUẤT]` — không ghi thì số mL vô nghĩa khi so sánh
| `kls_th_mat_do_t` / `_p` | Mật độ T / P | radio (chắc · mềm · cứng) | **`[GỐC]`**
| `kls_th_khoi_bat_thuong` | Khối bất thường | radio + `conditional` | `[ĐỀ XUẤT]` — AUA: khám tinh hoàn có thể phát hiện ung thư

**Mào tinh / ống dẫn tinh** — **`[GỐC]`** (1 dòng) → tách:

| key | label | type |
|---|---|---|
| `kls_mao_tinh_t` / `_p` | Mào tinh T / P | radio (bình thường · căng giãn · chai cứng · nang/spermatocele · không sờ thấy) | `[ĐỀ XUẤT]`
| `kls_ong_dan_tinh_t` / `_p` | Ống dẫn tinh T / P | radio (sờ thấy bình thường · **không sờ thấy** · nốt sau thắt · bất thường khác) | `[ĐỀ XUẤT]` — "không sờ thấy" là cửa vào chỉ định CFTR (§8)

**Giãn tĩnh mạch tinh** — **`[GỐC]`** ("Giãn tĩnh mạch tinh (độ)"):

| key | label | type |
|---|---|---|
| `kls_gtmt_t` / `_p` | Giãn TM tinh T / P | radio: `0` dưới lâm sàng · `I` chỉ sờ thấy khi Valsalva · `II` sờ thấy không cần Valsalva · `III` nhìn thấy bằng mắt | `[ĐỀ XUẤT]` phần định nghĩa độ — phân độ Dubin–Amelar

**Thăm trực tràng** `[ĐỀ XUẤT]` — chỉ hiện khi nghi tắc ống phóng tinh:

| key | label | type |
|---|---|---|
| `kls_dre` | Thăm trực tràng | radio (không làm · bình thường · nang đường giữa · giãn túi tinh) | parent: nghi EDO

### 5.6 — Tinh dịch đồ

Chín thông số **`[GỐC]`**, giữ nguyên nhãn của phòng khám, hai cột lần 1 / lần 2
(AUA: làm ≥2 lần cách nhau ~1 tháng khi kết quả bất thường).

Với engine hiện tại, mỗi thông số thành 2 field `_l1` / `_l2`:

| key gốc | label | type | ngưỡng dưới WHO 2021 |
|---|---|---|---|
| `tdd_the_tich` | Thể tích | number `mL` | **1.4** |
| `tdd_ph` | pH | number | ≥ 7.2 *(giữ từ WHO 2010 — cần đối chiếu bản in 6th ed.)* |
| `tdd_nong_do` | Nồng độ tinh trùng | number `triệu/mL` | **16** |
| `tdd_tong_so` | Tổng số tinh trùng | number `triệu` | **39** |
| `tdd_pr` | Tiến tới (PR) | number `%` | **30** |
| `tdd_im` | Bất động (IM) | number `%` | — |
| `tdd_kruger` | Hình dạng bình thường (Kruger) | number `%` | **4** |
| `tdd_bach_cau` | Bạch cầu | number `triệu/mL` | < 1.0 ⇒ nghi pyospermia |
| `tdd_danh_gia` | Đánh giá (WHO 2021) | text | |

Ba thông số `[ĐỀ XUẤT]` bổ sung — WHO 2021 có ngưỡng nhưng phiếu gốc thiếu:

| key | label | ngưỡng |
|---|---|---|
| `tdd_di_dong_tong` | Tổng độ di động | **42 %** — phiếu gốc chỉ có PR và IM, thiếu tổng |
| `tdd_di_dong_khong_tien_toi` | Di động không tiến tới (NP) | 1 % |
| `tdd_song` | Tỷ lệ sống (vitality) | **54 %** — bắt buộc khi PR thấp, để phân biệt tinh trùng chết vs bất động |

Điều kiện lấy mẫu `[ĐỀ XUẤT]` — không có thì con số không diễn giải được:

`tdd_kieng_xuat_tinh` (ngày) · `tdd_cach_lay_mau` (thủ dâm tại chỗ / tại nhà / bao cao su chuyên dụng) ·
`tdd_thoi_gian_den_pt` (phút) · `tdd_ly_giai` (phút) · `tdd_mat_mau` (có mất một phần mẫu không)

### 5.7 — Nội tiết & xét nghiệm máu `[ĐỀ XUẤT]`

| key | label | unit | ghi chú |
|---|---|---|---|
| `nt_fsh` | FSH | mIU/mL | AUA statement 10 + 11 |
| `nt_lh` | LH | mIU/mL | chỉ định khi testosterone thấp |
| `nt_testosterone` | Testosterone toàn phần | nmol/L | EAU: ngưỡng **12 nmol/L**; phải lấy **07:00–11:00, lúc đói**, và **lặp lại lần 2** nếu thấp |
| `nt_gio_lay_mau` | Giờ lấy máu | text | không có thì kết quả không diễn giải được |
| `nt_prolactin` · `nt_estradiol` · `nt_shbg` | Prolactin · Estradiol · SHBG | | |
| `nt_tsh` · `nt_ft4` | TSH · FT4 | | |
| `sh_glucose` · `sh_hba1c` · `sh_mo_mau` | Đường đói · HbA1c · Bộ mỡ máu | | EAU 2025: sàng lọc chuyển hóa là một phần của khám vô sinh nam |

### 5.8 — Hình ảnh & di truyền `[ĐỀ XUẤT]` — tất cả đều CÓ ĐIỀU KIỆN

Quan trọng: AUA nói **không** làm siêu âm bìu thường quy trong lần khám đầu, và **không**
làm DFI thường quy. Nên các field này mặc định ẩn, chỉ hiện khi thỏa điều kiện — và hệ
thống chỉ **gợi ý**, bác sĩ mới là người chỉ định (Notion §13: AI không tự tạo chỉ định).

| key | label | điều kiện gợi ý |
|---|---|---|
| `cls_sa_bìu` | SA bìu / Doppler: thể tích T/P, echo, vi vôi hóa, đường kính TM (>3 mm), trào ngược khi Valsalva | khám bìu bất thường / nghi giãn TM tinh |
| `cls_trus` | SA qua trực tràng hoặc MRI chậu | tinh dịch **acid**, vô tinh, thể tích **<1.4 mL**, testosterone bình thường, sờ thấy ống dẫn tinh |
| `cls_sa_than` | Siêu âm thận | **không sờ thấy ống dẫn tinh** (bất sản) |
| `cls_karyotype` | Nhiễm sắc thể đồ | vô tinh **hoặc nồng độ < 5 triệu/mL** kèm FSH cao / teo tinh hoàn; **và** cho cặp sảy thai liên tiếp |
| `cls_y_microdeletion` | Mất đoạn nhỏ NST Y (AZFa/b/c) | vô tinh **hoặc nồng độ ≤ 1 triệu/mL** kèm FSH cao / teo tinh hoàn |
| `cls_cftr` | CFTR (kèm khảo sát alen 5T) | bất sản ống dẫn tinh **hoặc** vô tinh do tắc không rõ nguyên nhân |
| `cls_dfi` | Phân mảnh DNA tinh trùng (DFI) | **không** làm ở lần khám đầu; cân nhắc khi sảy thai liên tiếp, thất bại ART, giãn TM tinh |
| `cls_nuoc_tieu_sau_xuat_tinh` | Nước tiểu sau xuất tinh | thể tích tinh dịch thấp / không có tinh dịch — tìm xuất tinh ngược dòng |
| `cls_cay_tinh_dich` | Cấy tinh dịch | bạch cầu > 1 triệu/mL (pyospermia) |

### 5.9 — Chẩn đoán `[ĐỀ XUẤT]`

| key | label | type |
|---|---|---|
| `cd_phan_loai_tdd` | Phân loại tinh dịch đồ | checkbox_group: bình thường · thiểu tinh · nhược tinh · dị dạng tinh · vô tinh · không có tinh dịch |
| `cd_vo_tinh_loai` | Nếu vô tinh | radio: do tắc (OA) · không do tắc (NOA) · chưa phân loại | parent: `cd_phan_loai_tdd` chứa vô tinh
| `cd_nguyen_nhan` | Nguyên nhân | textarea |
| `cd_phan_loai` | Vô sinh nguyên phát / thứ phát | radio | đối xứng với form HMVS
| `cd_benh_kem` | Bệnh kèm theo | textarea |
| `cd_tien_luong` | Tiên lượng | radio (tốt · trung bình · dè dặt · nặng) | đối xứng form HMVS

### 5.10 — Hướng xử trí `[ĐỀ XUẤT]`

| key | label | type |
|---|---|---|
| `xt_noi_khoa` | Điều trị nội khoa | checkbox_group: bổ sung vi chất (ZinC, CoQ10) · thuốc rối loạn cương (ức chế PDE5) · điều trị nội tiết · kháng sinh · chống oxy hóa | khớp nhóm **L9** trong `drug_catalog`
| `xt_phau_thuat` | Phẫu thuật | checkbox_group: mổ giãn TM tinh · lấy tinh trùng (TESE/micro-TESE/PESA/TESA) · nối ống dẫn tinh · khác |
| `xt_art` | Hỗ trợ sinh sản | checkbox_group: IUI · IVF · ICSI · trữ tinh trùng | phải khớp danh mục của form HMVS
| `xt_loi_song` | Lối sống | checkbox_group: giảm cân · bỏ thuốc lá · hạn chế rượu · tránh nhiệt độ cao · giảm stress |
| `xt_chuyen_tuyen` | Chuyển tuyến / hội chẩn | radio + `conditional` |
| `xt_chi_tiet` | Chi tiết | textarea |

### 5.11 — Theo dõi & tái khám

| key | label | type |
|---|---|---|
| `tk_ngay_tai_kham` | Ngày tái khám | date | đồng bộ 4 form kia
| `tk_xn_lap_lai` | Xét nghiệm cần kiểm tra lại | checkbox_group | dùng lại mã viết tắt của phòng khám: `HM` Hormone · `SH` Sinh hóa · `SA` Siêu âm — **cần thêm `TDD` Tinh dịch đồ** (mã mới, phải BS xác nhận)
| `tk_ghi_chu` | Ghi chú đặc biệt | textarea |

---

## 6. Việc backend

### 6.1 Danh mục dịch vụ nam khoa — **làm trước, chặn mọi thứ khác**

Migration mới, thêm vào `service_price` + map node. Node `DICHVU-TINHDICHDO` đã có sẵn,
đang chết vì không dịch vụ nào trỏ vào.

| service_code đề xuất | name | category | node_code |
|---|---|---|---|
| `CLS_TINH_DICH_DO` | Tinh dịch đồ | Nam khoa | `DICHVU-TINHDICHDO` |
| `CLS_SIEU_AM_TINH_HOAN` | Siêu âm tinh hoàn / Doppler | Nam khoa | `DICHVU-SIEUAM` |
| `CLS_XN_NOI_TIET_NAM` | Xét nghiệm nội tiết nam (FSH/LH/Testosterone) | Nam khoa | `DICHVU-LAYMAU-MAU` |
| `CLS_NUOC_TIEU_SAU_XUAT_TINH` | Nước tiểu sau xuất tinh | Nam khoa | `DICHVU-LAYMAU-NUOCTIEU` |
| `CLS_KARYOTYPE` | Nhiễm sắc thể đồ | Nam khoa | `DICHVU-HINHANH-NGOAI`? → **hỏi phòng khám: gửi đi đâu** |
| `CLS_Y_MICRODELETION` | Mất đoạn nhỏ NST Y | Nam khoa | gửi ngoài — **hỏi** |
| `CLS_CFTR` | CFTR + alen 5T | Nam khoa | gửi ngoài — **hỏi** |
| `CLS_DFI` | Phân mảnh DNA tinh trùng | Nam khoa | gửi ngoài — **hỏi** |

Giá để trống như 31 dịch vụ hiện có. Bốn dòng cuối để `node_code = NULL` nếu phòng khám
chưa xác nhận nơi thực hiện — `order_services()` sẽ từ chối kèm tên dịch vụ, đó là hành vi
đúng (thà từ chối còn hơn tạo việc ở phòng không ai chờ).

### 6.2 Bảng ghi nhận duyệt form — điều kiện để bật NK

Hôm nay chỉ có cờ `is_active`. Cần chỗ ghi **ai duyệt, duyệt bản nào, khi nào**:

```
clinical_form_approval
  clinic_id, form_code, schema_version   (vd 'exam_andrology_v1')
  approved_by_staff_id  → staff(id)
  approved_at
  source_document        (đường dẫn/mã tài liệu bác sĩ ký)
  note
  UNIQUE (clinic_id, form_code, schema_version)
```

Chỉ khi có dòng duyệt tương ứng mới `UPDATE clinical_form_catalogue SET is_active = TRUE`.
Nên viết thành một hàm/trigger để không ai lật cờ bằng tay được nữa — đây chính là điều
migration quarantine yêu cầu.

### 6.3 Bảng ngưỡng tham chiếu tinh dịch đồ

```
semen_reference_range
  parameter, lower_limit, unit, source ('WHO_2021'), effective_from
```

Nạp sẵn: thể tích 1.4 mL · nồng độ 16 triệu/mL · tổng số 39 triệu · tổng di động 42 % ·
tiến tới 30 % · sống 54 % · hình dạng bình thường 4 %.

Lý do là **bảng chứ không phải hằng số trong code**: WHO đã đổi ngưỡng 3 lần qua 3 ấn bản;
nhốt số vào TSX thì lần sau phải sửa code và mất luôn lịch sử ngưỡng nào áp cho kết quả nào.

### 6.4 Service function (Python thuần, có test)

| hàm | vào | ra |
|---|---|---|
| `score_iief5(answers) ` | 5 giá trị 1–5 | `{score, severity}` — 22–25 / 17–21 / 12–16 / 8–11 / 5–7 |
| `flag_semen(params, ranges)` | kết quả + bảng ngưỡng | danh sách cờ "dưới ngưỡng", **không** kết luận chẩn đoán |
| `suggest_genetic_tests(concentration, fsh, testis_volume, vas_palpable)` | | danh sách **gợi ý** kèm lý do (§5.8) |
| `compute_bmi(height, weight)` | | BMI |

Tất cả **thuần túy khuyến nghị**. Không hàm nào được tự tạo `service_order` hay tự điền
chẩn đoán — Notion §13 của cả 5 node khám đều cấm rõ điều này.

### 6.5 Quyền riêng tư khi liên kết HMVS

- Hồ sơ NK luôn thuộc `patient_id` của người chồng, kể cả khi mở từ luồng HMVS
- `couple_case_id` chỉ là liên kết; RLS phải chặn vợ đọc hồ sơ NK trừ khi có consent
- Cần bản ghi consent: ai đồng ý, cho xem phần nào, lúc nào
- Đối chiếu lại [20260730000013_role_scoped_clinical_read.sql](../supabase/migrations/20260730000013_role_scoped_clinical_read.sql)
  xem policy hiện tại có rò không

### 6.6 Bật form

Sau khi 6.1–6.5 xong: thêm `TDD` vào danh mục viết tắt, và
`UPDATE clinical_form_catalogue SET is_active = TRUE WHERE form_code = 'NK'` — **qua hàm ở
6.2**, không lật tay.

---

## 7. Việc frontend

### 7.1 Bắt buộc
- `src/dashboard/lib/form-schemas/nk.ts` — dựng theo §5
- Đăng ký `NK: nkSchema` trong [index.ts](../src/dashboard/lib/form-schemas/index.ts)
- `resolveServiceCode` đã khớp "nam khoa" rồi, không phải sửa
- Hiển thị cờ bất thường + điểm IIEF-5 **từ backend trả về**, không tính lại ở TSX

### 7.2 Cân nhắc thêm kiểu field mới

Tinh dịch đồ 2 lần làm phẳng thành `_l1`/`_l2` là ~24 field lặp đôi. Đề xuất thêm
`FieldType = "measure_series"` (một thông số, N lần đo, mỗi lần có ngày) — nhưng **chỉ khi**
bác sĩ xác nhận thực tế có làm lặp lại. Nếu phòng khám hầu như chỉ làm 1 lần thì làm phẳng
là đủ và rẻ hơn nhiều. **Hỏi trước khi code.**

### 7.3 Không được làm
- Không hard-code ngưỡng WHO trong TSX (§6.3)
- Không tự động tick chỉ định di truyền — chỉ hiện gợi ý kèm lý do, bác sĩ tự tick

---

## 8. Thứ tự làm

1. **§6.1 danh mục dịch vụ nam khoa** — không có thì form không nối vào đâu
2. §6.3 bảng ngưỡng + §6.4 service function (+ test)
3. §6.2 bảng duyệt form
4. §7.1 schema `nk.ts` + đăng ký
5. §6.5 rà quyền riêng tư cặp đôi
6. §6.6 bật form — **chỉ sau khi có chữ ký bác sĩ**

---

## 9. Phải hỏi trước khi code — không được tự quyết

1. **Ai duyệt form NK?** Notion ghi vai "Bác sĩ Nam khoa" nhưng chưa có tên. Không có người
   duyệt thì §6.6 không được chạy, và toàn bộ phần `[ĐỀ XUẤT]` chỉ là bản nháp.
2. **Phạm vi Nam khoa của phòng khám tới đâu?** Có khám rối loạn cương / xuất tinh sớm
   độc lập không, hay chỉ phục vụ luồng HMVS? Câu trả lời quyết định §5.3 sống hay chết.
   (Bằng chứng gián tiếp: nhóm thuốc L9 có Tadalafil + Avanafil ⇒ có khám.)
3. **Tinh dịch đồ làm ở đâu?** Có phòng xét nghiệm tại chỗ hay gửi ngoài (như GreenLab,
   theo tiêu chí Thu ngân)? Quyết định `node_code` ở §6.1.
4. **IIEF-5 có được dùng không?** IIEF là bộ câu hỏi có bản quyền/giấy phép. Spec này
   **cố ý không chép nguyên văn 5 câu hỏi**. Trước khi code §5.3 phải xác nhận phòng khám
   có quyền dùng, hoặc thay bằng bộ câu hỏi tự soạn được bác sĩ duyệt.
5. **Karyotype / Y-microdeletion / CFTR / DFI gửi đơn vị nào?** Không biết thì để
   `node_code = NULL` (§6.1).
6. **`NPĐH` là gì?** Vẫn chưa ai giải nghĩa — mã dịch vụ đặt lịch duy nhất không có tài
   liệu. Không liên quan trực tiếp NK nhưng nên hỏi cùng dịp.

---

## 10. Nguồn

Y văn (đã đọc trực tiếp, không suy đoán):

- [WHO laboratory manual for the examination and processing of human semen, 6th ed. (2021)](https://who.int/publications/i/item/9789240030787) — ngưỡng tham chiếu §5.6
- [The Sixth Edition of the WHO Manual for Human Semen Analysis: A Critical Review and SWOT Analysis (PMC8706130)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8706130/) — bảng đối chiếu ngưỡng 2010 vs 2021
- [Diagnosis and Treatment of Infertility in Men: AUA/ASRM Guideline (2020, sửa đổi 2024)](https://www.auanet.org/documents/Guidelines/PDF/2024%20Guidelines/Male%20Infertility%20Unabridged%20Final.pdf) — Appendix I (mẫu khám thực thể) §5.4–5.5, các statement 9–25 §5.8
- [AUA Male Infertility Guideline — trang tổng quan](https://www.auanet.org/guidelines-and-quality/guidelines/male-infertility)
- [EAU Guidelines on Male Sexual and Reproductive Health: 2025 Update on Male Infertility](https://www.europeanurology.com/article/S0302-2838(25)00148-4/fulltext) — quy trình chẩn đoán, sàng lọc chuyển hóa
- [EAU — Male Hypogonadism (Uroweb)](https://uroweb.org/guidelines/sexual-and-reproductive-health/chapter/male-hypogonadism) — ngưỡng testosterone 12 nmol/L, lấy máu sáng/đói, lặp lại lần 2
- [ESUR-SPIWG khuyến nghị chẩn đoán hình ảnh bìu trong vô sinh nam](https://www.esur.org/wp-content/uploads/2025/03/ESUR-SPIWG-male-infertility.pdf) — thông số SA bìu, TM > 3 mm, trào ngược Valsalva
- [Sperm DNA fragmentation testing: summary evidence and clinical practice recommendations (PMC7988559)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7988559/) — chỉ định DFI
- [The use of the simplified IIEF-5 as a diagnostic tool (PubMed 12152112)](https://pubmed.ncbi.nlm.nih.gov/12152112/) — thang điểm IIEF-5
- Phân độ giãn TM tinh Dubin–Amelar — [Varicocele Clinical Diagnosis and Grading (Springer)](https://link.springer.com/chapter/10.1007/978-3-319-79102-9_10)

Nguồn nội bộ:

- [docs/forms/handover_kham.docx](forms/handover_kham.docx) — tài liệu bàn giao (4 mục, không có NK)
- Notion [KHAM-NAMKHOA](https://app.notion.com/p/bb9ccb0eac8882ffa92281d1a14cfcac) · [KHAM-HIEMMUON-VOSINH](https://app.notion.com/p/4d2ccb0eac8882ac8863010be626bc85)
- [docs/ClinicAI-Tong-Quan-He-Thong.md](ClinicAI-Tong-Quan-He-Thong.md) §13.3–13.4
