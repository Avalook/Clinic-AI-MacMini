# KẾ HOẠCH — Bàn xét nghiệm đối tác (thu hộ · mẫu · kết quả về)

Mức 3 (tiền, migration, quyền, kết nối ra ngoài). Soạn 05/11/2026 từ bản mẫu
`Main.dc.html` của Tuyền và bản rà "Rà xét nghiệm đối tác" (đối chiếu `main @ 08d7db4c`).
**Sáu câu nghiệp vụ đã chốt 05/11.** Câu còn mở ở mục 2 có **mặc định** — làm theo
mặc định nếu Tuyền chưa trả lời, không dừng chờ.

> Đọc kèm: `docs/adr/0015-xet-nghiem-doi-tac.md` (vì sao), `.claude/rules/xet-nghiem-doi-tac.md`
> (luật khi code vùng này), `.claude/rules/thiet-ke-code.md` (luật chung).

---

## 0. Một đoạn cho người mới

Một số xét nghiệm phòng khám không tự làm mà gửi **đối tác** (phòng xét nghiệm ngoài).
Khách trả tiền xét nghiệm đó cho đối tác, phòng khám **thu hộ**. Nhân viên phòng khám
ở **bàn xét nghiệm** làm hết: ghi nhận khách đã trả, lấy mẫu, dán mã lên ống, gửi đối
tác. Đối tác **không đăng nhập hệ thống**, chỉ thả tệp kết quả vào một thư mục Google
Drive. Hệ thống tự kéo tệp về, gắn đúng khách theo mã mẫu, báo bác sĩ và CSKH. CSKH
bấm "Đúng người, gửi" để gửi khách.

```
Bác sĩ chỉ định ─▶ Ghi nhận thu hộ ─▶ Lấy mẫu (cấp mã ống) ─▶ Kết quả về ─▶ Gửi khách
                   (sổ RIÊNG,          (chỉ mở khi đã có     (Drive tự kéo   ("Đúng người,
                    không phải tiền     ghi nhận thu, hoặc    hoặc tải tay)   gửi" — một
                    phòng khám)         quản lý cho qua)                       cú bấm)
```

---

## 1. Sáu câu đã chốt (05/11/2026) — không đổi nếu Tuyền chưa nói lại

| # | Câu | Chốt | Hệ quả cho code |
|---|---|---|---|
| 1 | Thu hộ đi sổ nào? | **Sổ ghi nhận riêng**, tách hẳn tiền phòng khám. TM hay CK đều vào một bảng. Két chung (ở lễ tân) và quyết toán với đối tác **tính sau**. | Mở rộng `doi_tac_thanh_toan`. **Cấm** ghi vào `payment_cycle`, `payment`, `payment_bill_line`, két, doanh thu, báo cáo tiền phòng khám. Báo cáo cuối ngày chỉ hiện để tham khảo (như `_DOI_TAC_SQL` đang làm). |
| 2 | Chưa thu có được lấy mẫu? | **Thu xong mới lấy mẫu.** Chỉ chặn nút Lấy mẫu; không chặn chỉ định, khám, việc khác. Mọi ghi nhận còn hiệu lực đều tính (kể cả 0đ, kể cả CK chưa thấy tiền). ~~Quản lý cho qua, bắt nhập lý do.~~ **Đổi 05/11 chiều (5d): bỏ "cho qua" — chỉ thu xong mới lấy mẫu.** | Đây là **ngoại lệ** của luật "làm trước, thu sau" (30/09) và "thu hộ không chặn việc nào khác" (16/10) — chỉ cho nút Lấy mẫu của việc đối tác. Ghi vào ADR-0015 và SO-LUAT Phần 9. |
| 3 | Mã mẫu theo gì? | **Theo ống (mẫu)**, duy nhất, có **số kiểm tra**. Một ống phục vụ nhiều chỉ định **cùng một đối tác**. | Bảng `mau_xet_nghiem` + bảng nối. Cấp mã lúc bấm Lấy mẫu, không suy từ mã khách. |
| 4 | Kết quả về có chờ xác nhận? | **Tự về, hiện ngay** cho bác sĩ + CSKH. "Chặn ai tính sau." Giữ luật DB cấm gửi tệp đối tác chưa xác nhận; nút Gửi = **"Đúng người, gửi"** (xác nhận + gửi trong một cú bấm). | Không gỡ `trg_tep_ket_qua_gui_phai_duoc_cho_phep` / `CHO_XAC_NHAN`. Gom hai lệnh có sẵn (`xac_nhan_tep` + `danh_dau_da_gui`) vào một lệnh, một giao dịch. |
| 5 | Đối tác có vào hệ thống? | **Không.** Chỉ chia sẻ thư mục Drive. Hệ thống đọc bằng **tài khoản dịch vụ Google** (Changes API, 3 phút/lần). Thư mục cha "Kết quả đối tác" do phòng khám tạo, chia sẻ cho tài khoản dịch vụ (Người xem) **một lần**; mỗi đối tác một thư mục con chia sẻ cho đối tác. Dự phòng: Gmail phòng khám OAuth chỉ đọc. **Không dùng link công khai.** Có thêm **đường tải tay** của nhân viên. | Tắt dần lệnh phía đối tác (vai `PARTNER`) theo kiểu "con số chỉ được giảm". Worker kéo Drive là chặng cuối. |
| 6 | Giá thu hộ? | **Giá chỉ là gợi ý** (~~chữ mờ trong ô số tiền~~ — đổi 05/11 chiều, 5d: bấm Thu tiền thì ô **điền sẵn** giá, vẫn sửa được). Nhân viên gõ số khách thật trả, không bắt khớp. Lưu **cả hai** số. Chưa có giá thì ô trống. | Sổ có `gia_goi_y` (chụp lúc ghi) và `so_tien`. Không có validation "phải bằng giá". |

---

## 2. Câu còn mở — đang theo MẶC ĐỊNH (Tuyền đổi được, không chặn code)

| # | Câu | Mặc định đang làm | Ảnh hưởng nếu đổi |
|---|---|---|---|
| A | Mã dán ống: in tem hay viết tay? | **CHƯA CHỐT (05/11, mục 5c).** Mặc định tới lúc chốt: chặng 3 hiện mã **to, dễ chép** + nút in tem khổ nhỏ dùng khung in có sẵn (`src/dashboard/app/print/`). Có thể đối tác có tem in sẵn mã ⇒ thêm `ma_doi_tac`. | Chặng 1–2 không ảnh hưởng. |
| B | Dạng mã | `M` + số tăng dần theo phòng khám (đệm 5 chữ số) + **1 chữ số kiểm Damm**. Ví dụ số 572 → `M005724`. | Đổi hàm cấp/đọc mã + test. |
| C | Google Workspace hay Gmail thường? | Thiết kế chạy với **cả hai** (thư mục trong My Drive chia sẻ cho tài khoản dịch vụ). Shared drive là tuỳ chọn. | Không đổi code. |
| D | Bàn đối tác cũ `/doi-tac` (vai PARTNER) còn ai dùng trên prod? | Chặng 0 chạy SQL chỉ đọc để đo. Chưa đo xong thì **không xoá gì**, chỉ không thêm. | Quyết thời điểm tắt ở chặng 4. |
| E | Hẹn trả tính ngày lịch hay trừ Chủ nhật/lễ? | **ĐÃ CHỐT 05/11: đếm MỌI ngày** (ngày lịch), lưu thành **một ngày cụ thể** trên mẫu lúc lấy mẫu; nhân viên sửa được (có lý do). | Đổi một hàm tính ngày. |
| F | Ngưỡng cảnh báo | Quá hẹn trả → vàng; quá 1 ngày → đỏ. **ĐÃ CHỐT 05/11:** "Đã thu, chưa lấy mẫu" trễ sau **2 NGÀY** → vàng — **một cài đặt chung theo phòng khám** ở màn Cài đặt → Đối tác, chỉ vai Quản lý xem/sửa (PR 1.3). | Số trong cài đặt, không viết cứng rải rác. |
| G | Khách nợ thu hộ | **Không theo dõi nợ** thu hộ. Ghi số khách thật trả; lệch với giá gợi ý thì kế toán thấy. | Nếu cần nợ: kế hoạch riêng. |
| H | Dọn dữ liệu bảng giá đối tác (cặp ThinPrep/HPV trùng, vài dịch vụ nghi gắn sai bên thu, giá 0đ/NULL) | **Việc DỮ LIỆU**, Tuyền làm trên màn Bảng giá sau khi xem kết quả SQL chặng 0. Code không tự sửa giá. | — |
| I | Ai được làm gì | Mở cho mọi nhân sự nội bộ (theo "mở full lego" 30/09). **Riêng "cho lấy mẫu khi chưa thu"** chỉ Quản lý. | Đổi gói quyền, không đổi code. |

**Đã chốt 05/11 (sau PR luật):** `LIVE_TABLES` = danh sách trong `RealtimeRefresher.tsx`, không phải `truong-ca/shared.tsx` ·
sự kiện mới dùng tiền tố `lab.` (kiểu tên đang có trong catalogue), không dùng lại `partner.*` · ảnh CK thu hộ không gắn
`anh_chuyen_khoan` theo `cycle_id`, dùng lại cơ chế lưu/đẩy tệp, chọn (a) hay (b) ở PR 2.1 (mục 4.4).

---

## 3. Đang có trong repo — dùng lại, giữ, hay tắt

| Thứ | Ở đâu | Làm gì |
|---|---|---|
| Sổ thu hộ | `doi_tac_thanh_toan` (migration `20260928000091`): một ghi nhận còn hiệu lực/việc (unique index), huỷ có lý do, trigger cấm sửa/xoá | **Giữ + mở rộng** (mục 4.4). Nhớ sửa hàm trigger `doi_tac_thanh_toan_chi_huy()` để so cả cột mới. |
| Hàm thu hộ | `doi_tac_service.py: ghi_nhan_da_thu`, `huy_da_thu` | **Chuyển** lõi sang module mới; hàm cũ gọi lại hàm mới, không sao chép luật. |
| Trạng thái đối tác | `doi_tac_service.py: trang_thai_doi_tac()` | **Thay** bằng `trang_thai_xet_nghiem()` (mục 4.6). Giữ hàm cũ cho tới khi màn cũ tắt, có test so hai hàm trên cùng dữ liệu giai đoạn chuyển. |
| Tệp kết quả | `tep_ket_qua` + `tep_ket_qua_service.py` (`tai_len`, `xac_nhan_tep`, `thu_hoi_tep`, `danh_dau_da_gui`, `xoa_tep`) | **Dùng lại nguyên.** Không tạo bảng tệp thứ hai. |
| Báo kết quả về | `bao_ket_qua_ve.py` | **Dùng lại** cho cả hai đường (Drive, tải tay). |
| Bàn đối tác + vai PARTNER | router `doi_tac.py` (15 cửa), `/doi-tac`, `PRESET["PARTNER"]` | **Đóng băng** (không thêm), tắt ở chặng 4 bằng test đếm "chỉ được giảm". |
| Lý do nhận việc | `doi_tac_nhan_viec` (`DA_THU_TIEN`, `KHACH_DA_CHON`, `DA_LAY_MAU`, `MAU_GUI_DOI_TAC`, `BU_DU_LIEU`) | Giữ để đọc lịch sử; luồng mới không phụ thuộc nó. |
| Bên thu | `service_price.billing_owner` (`CLINIC`/`EXTERNAL_PARTNER`), `billing_owner_chon_tay` | Giữ. Luật mới: dịch vụ có ánh xạ đối tác đang hoạt động ⇒ phải là `EXTERNAL_PARTNER` — **ép khi lưu ánh xạ** + test đếm số dòng lệch (chỉ được giảm). Không chạy UPDATE hàng loạt. |
| Báo cáo cuối ngày + quầy thu | `bao_cao_cuoi_ngay_service.py: _DOI_TAC_SQL` **và** `quay_thu_service.py: _DOI_TAC_SQL` (hai bản cùng tên) | Giữ "chỉ tham khảo"; chặng 2 gom về **một** hàm đọc sổ thu hộ ở `services/xet_nghiem/thu_ho.py`, hai chỗ gọi lại hàm đó, đọc cột mới (TM/CK). |
| "Việc này có phải việc đối tác?" | `doi_tac_service.py: LA_VIEC_DOI_TAC_SQL` **và** `tep_ket_qua_service.py: _VIEC_DOI_TAC_SQL` (hai định nghĩa) | Luồng mới: **có dòng `xet_nghiem_viec`** là việc đối tác. Chặng 1 viết test so hai định nghĩa cũ với định nghĩa mới trên dữ liệu thử; chặng 4 thay hai chỗ cũ bằng định nghĩa mới. |

**Chín chỗ của bản mẫu KHÔNG được chép xuống backend** (chi tiết ở bản rà, mục 05):
trạng thái là một con số `st`; hoàn tác bằng chụp lại bản ghi (`o.prev`); mã mẫu suy từ
mã khách và hai việc chung `M0423`; tab tiền lọc theo ngày chỉ định; hoàn tác làm mất
khoản thu; hoàn tác được bước của hệ thống; ghép tay chỉ cho việc "đã lấy mẫu"; xoá tờ
đã gửi không để dấu; tên đối tác chép vào đơn thay vì id; bắt thu đúng bằng giá; hai chỗ
đặt hẹn trả.

---

## 4. Mô hình dữ liệu (phác — người code được chỉnh tên cột, không được đổi ý)

Mọi bảng mới: `clinic_id NOT NULL`, khai trong `src/clinicai/modules.py` (một module
`xet_nghiem_doi_tac` sở hữu), trigger `trg_notify_<bảng>` + thêm vào `LIVE_TABLES` trong
`src/dashboard/app/(dashboard)/RealtimeRefresher.tsx` nếu màn cần thấy tức thời — **không**
thêm vào danh sách cùng tên ở `truong-ca/shared.tsx` (chỉ cho bảng điều phối). Không xoá vật lý: đóng bằng `*_luc / *_boi / ly_do_*`.

### 4.1 `doi_tac` — đối tác
`id, clinic_id, ten, ma_ngan (unique theo clinic, không phân biệt hoa thường), sdt, ghi_chu,
drive_folder_id NULL, hen_tra_so_ngay_mac_dinh int NULL, ngung_luc NULL, ngung_boi, ly_do_ngung`.
- Đổi tên đối tác **không** đổi đơn cũ (đơn giữ `doi_tac_id`, màn đọc tên hiện tại; phiếu đã in giữ chữ lúc in).
- **Ngưng khi còn việc dở:** cho ngưng, nhưng việc dở **vẫn hiện** ở bàn (lọc theo việc, không theo đối tác đang hoạt động). Chỉ chặn *chọn* đối tác đã ngưng cho việc mới.

### 4.2 `doi_tac_dich_vu` — đối tác nào làm xét nghiệm nào
`doi_tac_id, service_price_id, gia_goi_y numeric NULL, hen_tra_so_ngay int NULL, mac_dinh bool, ngung_luc`.
- **Một nơi duy nhất** đặt hẹn trả: ở cặp (đối tác, dịch vụ); NULL thì lấy mặc định của đối tác.
- Mỗi dịch vụ tối đa một dòng `mac_dinh` còn hoạt động (unique index có điều kiện).
- Giá gợi ý: `gia_goi_y` của cặp; NULL thì `service_price.unit_price`; 0/NULL thì ô trống.

### 4.3 `xet_nghiem_viec` — chụp lúc chỉ định (1–1 với `service_order`)
`service_order_id PK, clinic_id, doi_tac_id, gia_goi_y_luc_chi_dinh, tao_luc,
cho_lay_mau_truoc_luc / _boi / _ly_do (quản lý cho qua khi chưa thu)`.
- **Bảng riêng, không thêm cột vào `service_order`** (bảng đó thuộc module lượt khám, đang chờ tách).
- Đổi đối tác cho một dịch vụ: việc đã chỉ định giữ đối tác cũ; đổi đối tác cho *một việc* là lệnh riêng có lý do, chỉ khi chưa lấy mẫu.

### 4.4 `doi_tac_thanh_toan` — mở rộng (sổ thu hộ)
Thêm: `tien_mat numeric(12,0) NOT NULL DEFAULT 0`, `chuyen_khoan numeric(12,0) NOT NULL DEFAULT 0`,
`gia_goi_y numeric(12,0) NULL`, `ma_giao_dich text NULL`.
- Ảnh CK thu hộ: KHÔNG gắn vào `anh_chuyen_khoan` theo `cycle_id` (bảng đó buộc vào
  `payment_cycle` = tiền phòng khám, trái câu chốt 1). Dùng lại CƠ CHẾ lưu/đẩy tệp của nó
  (cột vi_tri, da_day_luc… và job day_tep). Chọn một trong hai ở PR 2.1, ghi lý do:
  (a) mở rộng anh_chuyen_khoan: cycle_id cho phép NULL + cột doi_tac_thanh_toan_id,
  CHECK đúng một trong hai khác NULL — chỉ khi mọi chỗ đọc bảng đó đều lọc/join theo
  cycle_id (liệt kê đủ chỗ đọc trong PR); (b) bảng riêng anh_chuyen_khoan_thu_ho cùng
  cột tệp, và day_tep đọc thêm bảng này.
- CHECK `so_tien = tien_mat + chuyen_khoan`, cả hai ≥ 0. Bù dòng cũ: `CASH` → `tien_mat = so_tien`, `TRANSFER` → `chuyen_khoan = so_tien`.
- `hinh_thuc` cho phép thêm `MIXED`; là giá trị **suy ra** khi ghi (không cho người gõ).
- **Sửa hàm trigger** `doi_tac_thanh_toan_chi_huy()` để danh sách cột "không được sửa" có cả cột mới — quên chỗ này là sổ sửa được quá khứ.
- **Hoàn tiền** (bác sĩ bỏ chỉ định sau khi đã thu, trả lại khách): bảng `doi_tac_hoan_tien`
  (`thanh_toan_id, so_tien, tien_mat, chuyen_khoan, ly_do (bắt buộc), hoan_boi, hoan_luc`), chỉ thêm, không sửa.
  **Huỷ** (= ghi sai) và **hoàn** (= trả tiền thật) là hai việc khác nhau, hai nút khác nhau.
- Tab "Tiền thu hộ" lọc theo **ngày ghi nhận** (`ghi_luc`, giờ Việt Nam); khoản hoàn tính vào ngày `hoan_luc`.

### 4.5 `mau_xet_nghiem` + `mau_xet_nghiem_viec`
`mau_xet_nghiem`: `id, clinic_id, ma_mau (unique theo clinic), doi_tac_id, so_thu_tu, lay_luc, lay_boi,
hen_tra_ngay date (CHỤP lúc lấy), hen_tra_sua_boi/_luc/_ly_do, huy_luc/_boi/_ly_do, huy_loai ('NHAP_SAI'|'MAU_HONG')`.
`mau_xet_nghiem_viec`: `mau_id, service_order_id, doi_tac_id, go_luc/_boi/_ly_do`.
- **Cùng một đối tác ép ở DB:** FK ghép `(mau_id, doi_tac_id) → mau_xet_nghiem(id, doi_tac_id)` và
  `(service_order_id, doi_tac_id) → xet_nghiem_viec(service_order_id, doi_tac_id)`.
- Một việc chỉ thuộc **một** mẫu còn hiệu lực (unique index có điều kiện).
- **Cấp mã ở Postgres** (hàm `cap_ma_mau(clinic_id)`: bộ đếm theo clinic, `UPDATE … RETURNING` giữ khoá dòng) — hai người bấm cùng lúc không trùng số.
- Chữ số kiểm **Damm**. Python có hàm đọc/kiểm cùng thuật toán; test chéo SQL ↔ Python trên 1.000 số.
  Vectơ kiểm: `572 → 4`.
- **Mẫu hỏng / đối tác từ chối mẫu:** huỷ mẫu (`MAU_HONG`) → việc về "chờ lấy mẫu", lấy lại cấp **mã mới**; **khoản thu giữ nguyên**.
- Chặn huỷ mẫu khi đã có tệp kết quả còn hiệu lực — phải "Từ chối tệp" trước.

### 4.6 Trạng thái: **một hàm**, không lưu thành số
`services/xet_nghiem/trang_thai.py: trang_thai_xet_nghiem(su_viec) -> TrangThaiXN` — Python thuần,
không I/O. Đầu vào là các sự việc đã đọc: chỉ định đã huỷ?, ghi nhận thu còn hiệu lực?, quản lý cho qua?,
mẫu còn hiệu lực + hẹn trả, tệp còn hiệu lực (không TU_CHOI/THU_HOI/xoá), tệp đã gửi?, lệnh "Đối tác đã
tự trả khách" còn hiệu lực?, hôm nay.

| Trạng thái | Khi |
|---|---|
| `DA_HUY` | chỉ định đã huỷ |
| `DA_DONG` | có lệnh "Đối tác đã tự trả khách" (đóng việc, có lý do) — mục 5c |
| `CHO_THU` | chưa có ghi nhận thu và chưa được cho qua |
| `CHO_LAY_MAU` | đã có ghi nhận (hoặc cho qua), chưa có mẫu còn hiệu lực |
| `CHO_KET_QUA` | có mẫu (lấy mẫu xong là vào đây — không có mốc "đối tác nhận mẫu"), chưa có tệp còn hiệu lực (kèm cờ `qua_hen` nếu hôm nay > hẹn) |
| `CO_KET_QUA` | có tệp còn hiệu lực, chưa gửi bản mới nhất |
| `DA_GUI` | bản mới nhất đã gửi (ghi nhận bằng "Đúng người, gửi") |

Kèm cờ phụ (không phải trạng thái): `co_ban_moi_chua_gui`, `da_hoan_tien`, `qua_han_lay_mau`.
**Mọi màn, mọi đếm, mọi lọc đọc từ hàm này** — test đếm: chuỗi `'CHO_LAY_MAU'`… chỉ xuất hiện trong module trạng thái và test.

### 4.7 `drive_tep` (chặng 4)
`id, clinic_id, doi_tac_id, file_id, md5, ten, mime, so_byte, drive_modified, nhan_luc,
trang_thai ('MOI'|'DA_GHEP'|'CHO_GHEP_TAY'|'TU_CHOI'|'LOI'), tep_ket_qua_id NULL, ly_do`.
Unique `(clinic_id, file_id, md5)`. Cùng `file_id`, `md5` khác ⇒ **bản mới**. Tệp bị từ chối nhớ theo
`(file_id, md5)` để lượt quét sau bỏ qua. Đối tác xoá tệp trên Drive ⇒ bản đã chép **giữ nguyên**, chỉ ghi chú.
Bảng `drive_nhip` (một dòng/đối tác): `lan_quet_cuoi`, `loi_cuoi`, `page_token` — quá 1 giờ không có nhịp ⇒ `canh_bao`.

---

## 5. Hoàn tác — theo từng bước, không quay bản chụp

Giao diện giữ **một nút "Hoàn tác bước trước"**, nhưng nút đó gọi **đúng lệnh bù** của bước vừa làm.
Mỗi lệnh bù: bắt lý do (≥ 3 ký tự), ghi sự kiện (khai trong `events/catalogue.py`), không xoá dòng cũ.
Tên sự kiện mới theo kiểu đang có trong catalogue (tiếng Anh, chấm, quá khứ), tiền tố `lab.`: `lab.payment_recorded`,
`lab.payment_voided`, `lab.payment_refunded`, `lab.sample_collected`, `lab.sample_voided`, `lab.result_arrived`,
`lab.result_rejected`, `lab.result_sent`, `lab.closed_by_partner` (mục 5c), `lab.reopened`. **Không** dùng lại `partner.*` (của bàn cũ, đã có consumer).

| Bước | Lệnh bù | Chặn khi |
|---|---|---|
| Ghi nhận thu | Huỷ ghi nhận (ghi sai) — hoặc Hoàn tiền (trả khách) | Huỷ: đã lấy mẫu ⇒ phải huỷ mẫu trước, hoặc quản lý cho qua |
| Lấy mẫu | Huỷ mẫu (`NHAP_SAI` / `MAU_HONG`) | Đã có tệp còn hiệu lực ⇒ Từ chối tệp trước |
| Tệp về (hệ thống tự làm) | **Từ chối tệp** (`TU_CHOI`) — không có "hoàn tác" | — |
| Gửi khách | **Thu hồi** (`THU_HOI`, lý do, báo khách) — không xoá mốc đã gửi | — |
| Đối tác đã tự trả khách (DA_DONG) | Mở lại việc (bắt lý do, sự kiện lab.reopened) | — |

Mở lại = đóng bản ghi đóng việc (`mo_lai_luc` / `mo_lai_boi` / `mo_lai_ly_do`), **không xoá**; trạng thái
tính lại từ sự việc còn hiệu lực (thường về `CHO_KET_QUA`).

Luật CLAUDE.md "không thao tác nào khoá cứng" được giữ: mọi bước đều có lối bù.

---

## 5b. Kết quả chặng 0 (SQL prod 05/11/2026) và quyết định theo đó

| Prod nói | Quyết |
|---|---|
| 24 dịch vụ thu hộ, đều chọn tay bên thu; mẫu đều lấy ở phòng của phòng khám; 0 dịch vụ nghi sai bên thu; không có dịch vụ trùng (NIPT basic / Basic plus là hai gói khác nhau) | Không sửa dữ liệu bên thu. |
| 13 dịch vụ thu hộ giá 0đ (5 NIPT, HPV 16/40, Thinprep, combo HPV+Thinprep, Gentis, Liên cầu B, 13 bệnh STD) | Việc DỮ LIỆU, Tuyền điền trên màn Bảng giá khi rảnh. Chưa điền thì ô giá gợi ý để trống (câu 6). |
| Sổ thu hộ đang dùng thật: ~114 ghi nhận (≈115 tr), ~75% là CK | Migration chặng 2 bù TM/CK cho mọi dòng cũ; test đếm đủ 114. Ô mã GD quan trọng vì CK chiếm đa số. |
| Vai `PARTNER`: 0 thao tác 30 ngày | **Câu D:** tắt tài khoản PARTNER được ngay (việc dữ liệu ở màn Nhân sự). |
| Nhân viên nội bộ (CSKH, điều dưỡng, lễ tân) vẫn dùng bàn cũ: ghi thu hằng ngày (lần cuối 04/11); nhận mẫu / trả kết quả **dừng từ 26/10** | Lệnh của `doi_tac.py` **chưa tắt được**. PR 4.4 đổi thành: tắt sau khi nhân viên đã chuyển sang bàn mới (sau chặng 3 lên prod) và đo lại 0 thao tác 14 ngày. |
| Cờ `XAC_NHAN_TEP_DOI_TAC` **tắt** trên prod từ 23/09: tệp đối tác không qua `CHO_XAC_NHAN` | Bật cho luồng mới **cùng lúc** với nút "Đúng người, gửi" (PR 3.4) — bật trước khi có nút thì CSKH bị kẹt. Ghi trong kịch bản chặng 3. |
| 420 việc đối tác cũ chưa đóng (266 "đã lấy mẫu", 153 "có kết quả", ~1/4 có ghi nhận thu) | `xet_nghiem_viec` **chỉ tạo cho chỉ định từ ngày chặng 1 lên prod**. Việc cũ ở lại bàn cũ tới khi đóng. Không bù, không đoán đối tác/mốc. Dọn 420 việc tồn: việc riêng, Tuyền quyết sau. |
| Người thua khi ghi thu cùng lúc nhận 409 chỉ nhờ `FOR UPDATE OF o` | Chặng 2: `thu_ho.py` tự bắt lỗi unique → 409 câu tiếng Việt, test cả khi bỏ khoá dòng. |

**Việc mang sang PR 1.2** (NÊN SỬA của agent soát #598): test tranh chấp huỷ task của người
ghi thứ hai khi test đỏ giữa chừng; chú thích nói rõ người thứ hai bị chặn bởi khoá
`KEY SHARE` do khoá ngoại.

**Việc mang sang từ soát #602 (chặng 2):**
- **Lên prod: áp migration `20261105210000` và deploy code SÁT NHAU, ngoài giờ khám.** CHECK
  `so_tien = tien_mat + chuyen_khoan` có hiệu lực khi áp; code cũ (chưa điền cột mới) ghi thu ở
  bàn cũ sẽ 500 trong khoảng hở; ngược lại code mới chạy trên DB cũ cũng lỗi (cột chưa có).
  Staging: chấp nhận khoảng hở vài phút.
- **"Đã thu thực = thu − hoàn" một hàm (luật 1):** `bill_service.doi_tac_da_thu`,
  `phieu_kham/ket_qua_chi_dinh.py`, `phieu_kham/hanh_trinh.py`, `luot_kham_doc.py` đọc
  `doi_tac_thanh_toan.so_tien` không trừ `doi_tac_hoan_tien` — hoàn đủ vẫn hiện "đã thu". Chặng 3
  (phần THẤY) gom về một hàm ở `thu_ho.py`.

**Ngoài vùng, chỉ ghi sổ:** dòng thời gian màn xem lại lượt chỉ đọc `event_log`, không hiện
`visit.routed`, `medicine.counter_changed` (nằm ở `domain_event`) — ghi vào `docs/DANG-LAM.md`, không sửa trong việc này.

## 5c. Tuyền trả lời 05/11

- **Sau Lấy mẫu:** mẫu sang đối tác, hệ thống **KHÔNG** theo dõi "đối tác nhận mẫu". Lấy mẫu
  xong là `CHO_KET_QUA`. Bàn mới không có nút Nhận mẫu.
- **Kết quả về:** qua Drive (chặng 4) + tải tay (chặng 3).
- **Gửi khách:** nút "Đúng người, gửi" **CHỈ GHI NHẬN** (Zalo/Pancake tính sau). Kênh chọn sẵn
  `ZALO`, đổi được. Màn quản lý khách hàng (CSKH) hiện "Đã gửi kết quả", đọc từ
  `trang_thai_xet_nghiem()` (chặng 3: `tim-cho-sua` tìm màn đó).
- ~~**Đối tác tự gửi khách:**~~ (**BỎ 05/11 chiều — 5d**) lệnh "Đối tác đã tự trả khách" (đóng việc, bắt lý do, sự kiện
  `lab.closed_by_partner`) → trạng thái mới `DA_DONG` ở bảng 4.6. Lý do: không có lối đóng là
  sinh việc tồn mãi (420 việc cũ trên prod).
- **E:** hẹn trả đếm MỌI ngày.
- **F:** "đã thu, chưa lấy mẫu" trễ sau **2 NGÀY**. Một cài đặt chung theo phòng khám ở màn
  Cài đặt → Đối tác, chỉ vai Quản lý xem/sửa. Làm ở PR 1.3.
- **A: CHƯA CHỐT.** Có thể đối tác có tem in sẵn mã. Nếu đúng: `mau_xet_nghiem` thêm
  `ma_doi_tac` (unique theo đối tác, quét/gõ lúc Lấy mẫu), Drive ghép theo `ma_doi_tac`.
  Chờ Tuyền gửi tên file mẫu trên Drive trước chặng 3. Chặng 1–2 không ảnh hưởng.

## 5d. Tuyền đổi 05/11 chiều — làm theo bản mẫu "Việc của đối tác"

Thắng các dòng cũ ở mục 1, 5, 5c nếu trái nhau.

- **Bỏ "Cho lấy mẫu trước"** (quản lý cho qua) **và "Gỡ cho lấy mẫu trước"** — câu 2 chỉ còn
  "thu xong mới lấy mẫu" (kể cả 0đ). Gỡ lệnh, cửa API, sự kiện `lab.prepay_waived/_revoked`.
  Cột `cho_lay_mau_*` của `xet_nghiem_viec` giữ (dữ liệu cũ, "Xem quá trình" còn đọc).
- **Bỏ "Đối tác đã tự trả khách"** (5c): hệ thống chỉ ghi nhận việc làm TRONG hệ thống; đối
  tác tự gửi khách thì kệ — kết quả về thì tải lên, "Đúng người, gửi". Gỡ lệnh + sự kiện
  `lab.closed_by_partner`. Việc đã lỡ đóng vẫn **Mở lại việc** được (không khoá cứng).
- **Thu tiền:** ô tiền điền sẵn giá gợi ý (sửa được); ô "Khách đưa" + "Trả lại khách" chỉ để
  hiển thị (phép trừ, không lưu); dòng "Chuyển khoản vào: …" đọc `doi_tac.tai_khoan_nhan_ck`
  (Cài đặt → Đối tác); ảnh CK thu hộ (4.4) chọn **(b) bảng riêng `anh_chuyen_khoan_thu_ho`**
  — mọi chỗ đọc `anh_chuyen_khoan` bám `cycle_id` trong luồng quyền quầy thu.
- **Chữ trạng thái** theo bản mẫu: chỉ sửa bảng `NHAN` (Chưa thu tiền · Đã thu tiền · Đã lấy
  mẫu · Đã có kết quả · Đã gửi khách · Đối tác đã tự trả khách · Đã huỷ).
- **Tab Tiền thu hộ chỉ quản lý** — chặn ở máy chủ (`GET /ban/tien`), ẩn tab.
- **Một mục thanh bên "Việc của đối tác"** = bàn mới. Bàn cũ `/doi-tac` ẩn khỏi thanh bên.
  **Đóng 420 việc cũ + xoá hẳn bàn cũ: PR riêng, Mức 3, chờ kế hoạch duyệt** (Phòng đối tác
  `/phong/[ma]` đang dùng chung cửa `/api/doi-tac/*` — phải quyết nơi đi trước khi gỡ).

## 6. Bốn chặng — mỗi PR nhỏ (≤ ~400 dòng ngoài test/migration), mỗi chặng lên prod riêng

Dải giờ migration riêng cho việc này: **`2026110520xxxx`–`2026110529xxxx`**.

### Chặng 0 — chuẩn bị (không đổi hành vi)
- **PR 0.1 (docs, không CI):** cài bộ luật + ADR + kế hoạch này + đoạn chèn CLAUDE.md, SO-LUAT Phần 9.
- **PR 0.2:** `scripts/soat-xet-nghiem-doi-tac.sql` chỉ đọc (dạng như `scripts/soat-don-vi.sql`):
  (a) dịch vụ `EXTERNAL_PARTNER`: mã, tên, giá, node, `billing_owner_chon_tay`; cặp tên gần trùng;
  (b) số dòng `doi_tac_thanh_toan` theo tháng, theo hình thức, số đã huỷ;
  (c) tài khoản vai `PARTNER`, lần thao tác gần nhất (`event_log`) 30 ngày;
  (d) `tep_ket_qua` có `xac_nhan_trang_thai` đang `CHO_XAC_NHAN`;
  (e) việc đối tác đang dở theo `trang_thai_doi_tac`. Tuyền chạy trên prod, dán kết quả vào PR.
- **PR 0.3:** test khoá hành vi đang đúng trước khi đụng: (1) ghi thu hộ không tạo dòng nào ở
  `payment_cycle`/`payment`/`payment_bill_line`/két/doanh thu; (2) DB chặn gửi tệp đối tác chưa xác nhận;
  (3) hai người ghi thu cùng việc ⇒ một người thua. Thêm `src/tests/unit/test_tran_xet_nghiem.py`: số dòng
  `doi_tac_service.py` **không tăng**, số cửa router `doi_tac.py` **không tăng**.

### Chặng 1 — nền: đối tác, ánh xạ, chụp, trạng thái
- **PR 1.1 (migration):** `doi_tac`, `doi_tac_dich_vu`, `xet_nghiem_viec` + ràng buộc + notify.
- **PR 1.2 (service + test):** package `src/clinicai/services/xet_nghiem/` —
  `trang_thai.py` (hàm 4.6, test bảng ≥ 15 ca), `doi_tac.py` (thêm/sửa/ngưng, ánh xạ, ép bên thu khi lưu),
  `chup.py` (khi chỉ định dịch vụ có ánh xạ ⇒ tạo `xet_nghiem_viec`, gọi từ **một** chỗ — tìm chỗ tạo
  `service_order` bằng `tim-cho-sua`; nếu chỗ tạo nằm trong `luot_kham_service.py` thì chỉ thêm **một dòng gọi**, không thêm luật vào đó).
- **PR 1.3 (API + màn Cài đặt đối tác):** router mỏng `xet_nghiem.py`, `response_model` cho mọi cửa mới; màn
  Cài đặt → Đối tác (tên, mã ngắn, hẹn mặc định, link thư mục Drive, dịch vụ + giá gợi ý + hẹn).
- **Xong chặng khi:** tạo đối tác, gán HPV cho đối tác A, bác sĩ chỉ định HPV ⇒ có `xet_nghiem_viec` với
  `doi_tac_id = A`; đổi gán sang B ⇒ việc cũ vẫn A.

### Chặng 2 — sổ thu hộ
- **PR 2.1 (migration):** mở rộng `doi_tac_thanh_toan`, bù dòng cũ, sửa trigger, `doi_tac_hoan_tien`.
- **PR 2.2 (service):** `services/xet_nghiem/thu_ho.py` — `ghi_nhan`, `huy`, `hoan`; `ghi_nhan_da_thu`/`huy_da_thu`
  cũ gọi lại hàm mới. Người ở bàn XN ghi được (quyền khối mới `xet_nghiem`), không chỉ vai PARTNER.
- **PR 2.3 (màn):** bàn XN — ô TM/CK (giá gợi ý chữ mờ), mã GD, ảnh CK tuỳ chọn; tab Tiền thu hộ theo ngày ghi nhận;
  báo cáo cuối ngày đọc cột mới, vẫn "chỉ tham khảo".
- **Xong chặng khi:** test (1) của PR 0.3 vẫn xanh; ghi 150k TM + 200k CK hôm qua cho việc chỉ định hôm kia ⇒ hiện ở tab ngày hôm qua; hoàn 350k hôm nay ⇒ hiện dòng hoàn hôm nay, dòng thu hôm qua không đổi.

### Chặng 3 — mẫu, mã ống, bàn XN chạy thật (kết quả vẫn tải tay)
- **PR 3.1 (migration):** `mau_xet_nghiem`, `mau_xet_nghiem_viec`, bộ đếm + `cap_ma_mau()`, FK ghép, quyền "cho qua" chỉ Quản lý.
- **PR 3.2 (service):** `services/xet_nghiem/mau.py` — `lay_mau(viec_ids)` (chặn nếu việc nào `CHO_THU` mà không được cho qua;
  chặn khác đối tác), `huy_mau`, `sua_hen_tra`, `cho_lay_mau_truoc` (quản lý, lý do); `ma_mau.py` (Damm).
  **Gỡ cho qua** (soát #600 — luật "không khoá cứng"): lệnh `go_cho_qua` (quản lý, lý do ≥ 3 ký tự, sự kiện
  `lab.prepay_waiver_revoked`), chặn khi việc đã có mẫu còn hiệu lực. Migration chặng 3 thêm cột
  `cho_lay_mau_go_luc / _boi / _ly_do` vào `xet_nghiem_viec` và sửa trigger `xet_nghiem_viec_chi_cho_qua()`
  cho phép ĐÓNG cho qua đúng một lần (khuôn `doi_tac_thanh_toan`: huỷ một lần, không sửa nội dung).
  Gỡ xong muốn cho qua lại ⇒ chưa hỗ trợ (một việc một lần cho qua); cần thì Tuyền quyết thêm.
- **PR 3.3 (service):** tải tay — `tai_ket_qua_tay(mau_id | viec_id, tep)` gọi `tep_ket_qua_service.tai_len` có sẵn với
  `service_order_id`; nhân viên đã chọn đúng việc ⇒ xác nhận **cùng bước**; báo qua `bao_ket_qua_ve`.
  Tệp cho cả ống nhiều việc: tạo một `tep_ket_qua` cho **mỗi** việc trỏ cùng nội dung (cùng `sha256`), không nhân bản tệp trên đĩa nếu kho tệp hỗ trợ; nếu không thì chép — ghi lựa chọn trong PR.
- **PR 3.4 (service):** "Đúng người, gửi" = `xac_nhan_tep(HOP_LE)` + `danh_dau_da_gui(kenh)` trong **một giao dịch**; kênh bắt buộc.
  Hai hàm đó nằm trong `tep_ket_qua_service.py` (1.901 dòng, quá trần): nếu mỗi hàm tự mở giao dịch thì
  **tách lõi** của chúng thành hàm nhận `conn` (di chuyển, không thêm luật — số dòng file không tăng), rồi
  hàm mới ở `services/xet_nghiem/gui.py` gọi hai lõi trong một giao dịch.
- **PR 3.5 (màn):** bàn XN theo bản mẫu của Tuyền (cột trạng thái lấy từ hàm 4.6), in tem mã, nút hoàn tác bước trước.
- **Xong chặng khi:** kịch bản bấm thử mục 8 (bước 1–10) chạy qua trên local, 375 và 1280.

### Chặng 4 — Drive tự về + tắt bàn đối tác cũ
- **Việc Tuyền làm tay trước (AI soạn hướng dẫn từng bước):** tạo dự án Google Cloud, bật Drive API, tạo tài khoản
  dịch vụ, tải khoá JSON **chỉ đặt vào `.env.prod` trên VPS** (biến môi trường, không vào git, không dán chat);
  tạo thư mục "Kết quả đối tác" chia sẻ cho email tài khoản dịch vụ quyền **Người xem**; mỗi đối tác một thư mục con.
- **PR 4.1 (migration):** `drive_tep`, `drive_nhip`.
- **PR 4.2 (worker):** `services/xet_nghiem/drive.py` — vòng quét 3 phút **trong worker có sẵn** (cùng kiểu bộ canh gác
  trong `su-kien`) hoặc một systemd timer trong `scripts/systemd/` — chọn cái giống mẫu đang chạy, **không thêm hạ tầng** (SO-LUAT Phần 7).
  Changes API với `page_token` lưu DB; tải tệp về kho tệp hiện có (Viettel CFS); đọc mã trong tên tệp bằng regex
  `M\d{6,}`; **kiểm chữ số Damm**; khớp đúng một mẫu còn hiệu lực của **đúng đối tác của thư mục** ⇒ ghép; mẫu có
  nhiều việc chưa có kết quả ⇒ `CHO_GHEP_TAY`; sai số kiểm / không thấy mã / sai đối tác ⇒ `CHO_GHEP_TAY`.
  Tệp ghép tự động vào `tep_ket_qua` ở `CHO_XAC_NHAN` (hiện ngay, báo bác sĩ + CSKH; gửi khách vẫn qua "Đúng người, gửi").
- **PR 4.3 (màn):** hàng "Chờ ghép tay" (ghép vào **mọi** mẫu của đúng đối tác, kể cả mẫu đã có kết quả ⇒ thành bản 2;
  bản 1 đã gửi ⇒ báo CSKH gửi lại), nút Từ chối tệp, đèn nhịp Drive.
- **PR 4.4:** tắt lệnh phía đối tác trong `doi_tac.py` theo số đo chặng 0; test đếm cửa router giảm; giữ cửa đọc lịch sử.
- **Xong chặng khi:** thả `M005724_ket-qua.pdf` vào thư mục đối tác A ⇒ ≤ 3 phút sau bác sĩ thấy; thả `M005725.pdf`
  (sai số kiểm) ⇒ vào hàng ghép tay, không báo ai; thả lại cùng tên khác nội dung ⇒ bản 2.

---

## 7. Mười hai ca biên — mỗi ca một test (tên test ghi trong PR)

| Ca | Phải xảy ra |
|---|---|
| Tên tệp gõ nhầm một số | Số kiểm sai ⇒ hàng ghép tay, **không** gắn vào khách khác, không báo bác sĩ |
| Một tệp chứa kết quả hai khách | "Đúng người, gửi" là chỗ bắt; Từ chối tệp có lý do |
| Bỏ chỉ định sau khi đã thu | Dòng hoàn trong sổ thu hộ; tiền phòng khám không đổi |
| CK chưa thấy tiền | Vẫn ghi nhận được, đủ để lấy mẫu; có ô mã GD / ảnh |
| Hai người cùng ghi thu | Unique index — một người nhận lỗi 409 dễ hiểu |
| Giảm / miễn / 0đ | Ghi số thật (kể cả 0); không bắt bằng giá gợi ý |
| Mẫu hỏng / đối tác từ chối mẫu | Huỷ `MAU_HONG`, lấy lại mã mới, khoản thu giữ |
| Đối tác tải lại cùng tên | md5 khác ⇒ bản mới; bản cũ đã gửi ⇒ báo gửi lại |
| Đối tác xoá tệp trên Drive | Bản đã chép giữ nguyên, chỉ ghi chú |
| Drive không đọc được | Nhịp ghi mỗi lượt; > 1 giờ không nhịp ⇒ `canh_bao` cho quản lý |
| Khách không quay lại lấy mẫu | "Đã thu, chưa lấy mẫu" quá ngưỡng ⇒ cảnh báo vàng |
| Đổi đối tác cho một dịch vụ | Việc cũ giữ đối tác cũ; việc mới đi đối tác mới |

Thêm: ngày giờ rác ở mọi ô ngày (luật backend: trả rỗng, không ném); hai chi nhánh không thấy dữ liệu của nhau (`clinic_id`).

---

## 8. Kịch bản bấm thử cho người thật (dán vào PR chặng 3, chặng 4)

1. Quản lý: Cài đặt → Đối tác → thêm "Medlatec" (mã `MED`, hẹn 3 ngày), gán HPV + ThinPrep.
2. Bác sĩ chỉ định HPV + ThinPrep cho khách `DEMO-0423`.
3. Bàn XN: hai việc hiện "Chờ thu". Nút Lấy mẫu **mờ**, rê chuột thấy "Chưa ghi nhận thu hộ".
4. Ghi 300k TM + 200k CK (giá gợi ý mờ hiện 550k, cố tình ghi lệch). Hai việc sang "Chờ lấy mẫu".
5. Chọn cả hai ⇒ Lấy mẫu ⇒ ra **một** mã ống, ví dụ `M005724`, hẹn trả = hôm nay + 3. In tem.
6. Hoàn tác bước trước ⇒ hỏi lý do ⇒ mẫu huỷ, việc về "Chờ lấy mẫu", khoản thu **vẫn còn** ở tab Tiền thu hộ.
7. Lấy mẫu lại ⇒ mã **mới** `M00573x`.
8. Tải tay một PDF cho ống đó ⇒ bác sĩ và CSKH thấy thông báo; trạng thái "Có kết quả".
9. CSKH bấm "Đúng người, gửi" ⇒ chọn kênh Zalo ⇒ "Đã gửi". Thử thu hồi ⇒ phải nhập lý do; mốc đã gửi vẫn còn trong lịch sử.
10. Kiểm tiền: màn Thu ngân, két, báo cáo doanh thu hôm nay **không đổi**; báo cáo cuối ngày có dòng "Thu hộ đối tác (tham khảo) 500k".

---

## 9. Không được làm

- Không ghi thu hộ vào bất kỳ bảng/báo cáo tiền nào của phòng khám; không "tiện thì cộng vào két".
- Không lưu trạng thái thành một cột số/chuỗi trên đơn; không tự tính trạng thái ở màn hay ở SQL thứ hai.
- Không hoàn tác bằng chụp/khôi phục bản ghi; không `DELETE` sổ thu, mẫu, tệp.
- Không gỡ `CHO_XAC_NHAN` hay trigger cấm gửi tệp chưa xác nhận.
- Không dùng link Drive công khai, không để khoá Google trong repo, không đọc Drive từ trình duyệt.
- Không thêm hàm vào `doi_tac_service.py` (1.236 dòng) hay `luot_kham_service.py`; code mới vào `services/xet_nghiem/`, file ≤ 400 dòng, hàm ≤ 60 dòng.
- Không thêm luật nghiệp vụ vào TSX (ẩn/hiện nút dựa trên cờ backend trả về, không tự suy).
- Không xoá cửa cũ của bàn đối tác trước khi có số đo chặng 0 và Tuyền đồng ý.
- Không áp migration lên prod/staging; không deploy. AI soạn lệnh, Tuyền chạy.
