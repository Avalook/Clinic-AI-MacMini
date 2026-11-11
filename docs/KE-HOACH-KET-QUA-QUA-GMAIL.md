# KẾ HOẠCH + GIAO VIỆC — Kết quả đối tác tự về từ Gmail (bản 2 của chặng 4)

> Soạn 09/11/2026, sửa 09/11 12:00 theo Tuyền: (1) nạp **toàn bộ** thư, kể cả thư cũ, vào một
> **Kho email kết quả (tạm)** chỉ Tuyền xem; (2) Claude Code **tự thao tác trên Chrome** để cài
> đặt Google, Tuyền chỉ đăng nhập và bấm đồng ý.
> Mức 3 (kết nối ra ngoài, dữ liệu sức khoẻ, migration). Mỗi chặng một PR, dừng sau mỗi chặng.

---

## 0. Một đoạn cho người mới

Đối tác True Medicine **không có API** (anh Đinh Tuấn Anh xác nhận 09/11): kết quả nằm trong
CSDL của họ; khi duyệt, phần mềm của họ tự sinh PDF và **gửi email** tới Gmail phòng khám.

| Phần | Ví dụ |
|---|---|
| Người gửi (một địa chỉ duy nhất) | `truemedicine.laymauxn@gmail.com` |
| Tiêu đề | `Kết quả xét nghiệm: VŨ THỊ THU HOÀI - Ngày xét nghiệm: 08-11-2026` |
| Thân | `Họ tên: VŨ THỊ THU HOÀI, NS: 1981, Giới: Nữ` |
| Đính kèm | một PDF / thư, tên `VU_THI_THU_HOAI_081126-501726_HPV_TMD.pdf` (tên · mã của họ · **mã xét nghiệm** · mã đối tác) |
| Trong PDF | họ tên, SĐT (Tuyền xác nhận: **không có** mã `081126-501726` trong PDF) |

Đã có sẵn đường "Drive tự về" (chặng 4): ghép theo tên + SĐT trong PDF → tờ kết quả
`CHO_XAC_NHAN` → báo bác sĩ + CSKH → "Đúng người, gửi"; không khớp ⇒ hàng ghép tay.
**Bản này thay chỗ lấy tệp (Gmail thay Drive), lưu mọi thư vào Kho, ghép chắc hơn.**

```
Gmail phòng khám ──▶ Clinic AI quét 3 phút, CHỈ ĐỌC, lọc đúng người gửi
                          │  MỌI thư (cũ + mới) ─▶ lưu PDF vào kho tệp Clinic AI
                          ▼                         + một dòng ở KHO EMAIL (chỉ Tuyền xem)
              thư TRƯỚC ngày bật?
               ├─ có  ─▶ chỉ nằm trong Kho ("Lưu trữ"), kèm GỢI Ý khách nếu tên + SĐT khớp
               └─ không ─▶ ghép: TÊN + SĐT · NĂM SINH · MÃ XÉT NGHIỆM
                            ├ khớp 1 việc ─▶ "Có kết quả", báo BS + CSKH
                            └ không chắc  ─▶ hàng ghép tay (tab Kết quả)
```

**Không chép sang Drive.** PDF đã nằm trong Gmail; bản lưu của Clinic AI ở kho tệp riêng
(Viettel CFS), không tính vào hạn mức Google.

---

## 1. Đã quyết (không hỏi lại)

| # | Câu | Quyết | Vì sao |
|---|---|---|---|
| 1 | Đọc Gmail bằng gì | **Gmail API, phạm vi `gmail.readonly`**, OAuth refresh token của tài khoản phòng khám, gọi bằng `httpx` như `drive_api.py` (không thêm thư viện Google) | Chỉ đọc; máy chủ tự kéo, không mở cửa cho bên ngoài gọi vào |
| 2 | Gắn nhãn / đánh dấu đã đọc trong Gmail | **Không.** Nhớ thư đã xử lý trong DB | Nhãn cần quyền sửa hộp thư; nhân viên đang tự dùng nhãn "Đã trả chưa note" |
| 3 | Lưu sự việc | **Dùng lại bảng `drive_tep`**, thêm `nguon` (`DRIVE`/`GMAIL`) + cột email + `vi_tri_tep`. `file_id` = `gmail:<messageId>:<partId>`, `md5` tự tính | Hàng ghép tay, Gán, Từ chối tệp đã chạy trên bảng này |
| 4 | Lưu byte PDF | **Mọi** PDF Gmail lưu ngay vào kho tệp Clinic AI lúc nhận (cùng cơ chế lưu/đẩy của `tep_ket_qua`), `vi_tri_tep` trỏ tới đó | Xem trước / Gán / Kho không phải gọi lại Gmail; `attachmentId` của Gmail không cố định |
| 5 | **Thư cũ** | **Nạp hết** (Tuyền 12:00). Mốc `xet_nghiem_cai_dat.gmail_tu_ngay` = ngày bật: thư **trước** mốc ⇒ trạng thái `LUU_TRU`: chỉ nằm trong Kho, **không** tự ghép, **không** báo ai, **không** đụng 420 việc bàn cũ | Có đủ lịch sử để xem mà không làm loạn bàn đang chạy |
| 6 | Nạp lịch sử thế nào | Mỗi vòng xử lý tối đa 100 thư cũ (từ mới về cũ), lưu con trỏ trong `drive_nhip`; thư mới luôn được xử lý trước | Lần đầu có thể hàng nghìn thư — không chặn kết quả mới |
| 7 | Ai xem Kho | Quyền mới `xet_nghiem.kho_email` — **không** gắn vào gói vai nào, cấp riêng cho tài khoản Tuyền ở `/phan-quyen`. Mỗi lần mở PDF ghi sự kiện `lab.archive_viewed` | "Kho tạm để mình tôi xem"; dữ liệu sức khoẻ phải có vết ai xem |
| 8 | "Tạm" là sao | Kho là **một màn**; tắt = gỡ quyền, dữ liệu giữ (không xoá vật lý) | Muốn bỏ hẳn: PR riêng sau |
| 9 | Ghép (thư sau mốc) | Tên + SĐT **bắt buộc** như `ghep_khach.khop_khach`; năm sinh (thân `NS:` ↔ `patient.birth_year`/`date_of_birth`) gỡ `NHIEU_KHACH`; mã xét nghiệm trong tên tệp ↔ cột mới `doi_tac_dich_vu.ma_ben_doi_tac` gỡ `ONG_NHIEU_VIEC` | Khách hay làm HPV + ThinPrep cùng lúc |
| 10 | Gợi ý trong Kho (thư cũ) | Tên + SĐT khớp đúng một khách ở bảng `patient` ⇒ hiện "Có thể là: <tên> · <mã BN>". **Chỉ chữ gợi ý**, không gắn | Giúp Tuyền tra nhanh, không đổi dữ liệu |
| 11 | Khớp khách nhưng việc **chưa bấm Lấy mẫu** | Hàng ghép tay lý do `CHUA_LAY_MAU` + gợi ý việc (một bấm Gán) | Nhân viên quên bấm vẫn không mất kết quả |
| 12 | Thư gửi lại (bản sửa) | Khớp việc **đã có** tờ ⇒ ghép tay lý do `CO_BAN_MOI` + gợi ý; Gán ⇒ bản 2 | Bản sửa phải có người nhìn |
| 13 | Mã `081126-501726` | Lưu vào `drive_tep.ma_ben_doi_tac_tep` để tra; **không** dùng ghép | Không có trong PDF, chưa biết luật đặt mã của họ |
| 14 | Chạy ở đâu | Dịch vụ `drive-xn` (`worker --drive`), vòng 3 phút, khoá một-tiến-trình có sẵn | Không thêm hạ tầng |
| 15 | Khoá | Docker secret `gmail_oauth` (client_id, client_secret, refresh_token), biến `GOOGLE_GMAIL_OAUTH_FILE`; tệp rỗng ⇒ tắt im lặng | Như `drive_sa_key` |
| 16 | Staging | **Không đọc hộp thư thật.** Trỏ tới Gmail THỬ, thư giả cùng định dạng | Không đưa PDF khách thật vào môi trường thử |

---

## 2. Cài đặt Google — Claude Code tự làm trên Chrome

**Claude Code điều khiển Chrome trên Mac của Tuyền** (tích hợp Chrome của Claude Code; không có
thì Playwright mở Chrome **headed** với hồ sơ riêng `~/.clinicai/chrome-gmail`). Tuyền ngồi cạnh.

| Bước | Ai làm |
|---|---|
| Mở `console.cloud.google.com`, chờ Tuyền đăng nhập **Gmail phòng khám** | Tuyền gõ mật khẩu + mã 2 bước. Claude Code **không** gõ, không đọc, không chụp màn hình ô mật khẩu |
| Tạo dự án `clinic-ai-ket-qua` (hoặc dùng dự án có sẵn của tài khoản này), bật **Gmail API** | Claude Code |
| Google Auth Platform: Branding (tên ứng dụng "Clinic AI – đọc kết quả xét nghiệm", email hỗ trợ = Gmail phòng khám) · Audience **External**, bấm **Publish app → In production** · Data access: thêm **chỉ** `.../auth/gmail.readonly` | Claude Code |
| Clients: tạo OAuth client loại **Desktop app**, tải JSON về `~/.clinicai/gmail-client.json` (quyền 600, **ngoài repo**) | Claude Code |
| Chạy `scripts/gmail-cap-quyen.py` → trình duyệt mở màn đồng ý | Claude Code chạy; **Tuyền** bấm "Nâng cao → Đi tới …" và **"Cho phép"** |
| Script ghi `~/.clinicai/gmail-oauth.json` (refresh token) | Claude Code kiểm tệp có, **không in nội dung** |
| Chạy `scripts/gmail-do-hop-thu.py` để thử quyền | Claude Code |
| Gmail THỬ cho staging: tạo tài khoản mới (Google đòi số điện thoại) | Tuyền tạo; Claude Code làm lại các bước trên cho tài khoản đó |
| Đưa tệp khoá lên VPS (`.env.prod`, `.env.staging`) | Claude Code **soạn lệnh**, Tuyền chạy (luật repo: AI không deploy) |

Trước khi bấm, Claude Code **tra tài liệu Google hiện hành**: hạn refresh token theo trạng thái
ứng dụng, giới hạn ứng dụng chưa xác minh dùng phạm vi hạn chế (`gmail.readonly`), trường hợp
chủ dự án tự dùng. Trái với bảng trên ⇒ dừng, báo Tuyền phương án thay (dự phòng: IMAP + mật
khẩu ứng dụng — kém hơn vì không giới hạn chỉ đọc). Giao diện console khác mô tả ⇒ chụp màn,
hỏi Tuyền, không đoán bấm.

---

## 3. Năm chặng

### G0 — Cài đặt Google + đo hộp thư (không đổi DB, không đổi hành vi)
- Mục 2 ở trên.
- `scripts/gmail-cap-quyen.py`: OAuth cài đặt (loopback), chỉ `gmail.readonly`, ghi JSON quyền 600.
- `scripts/gmail-do-hop-thu.py`: CHỈ ĐỌC tiêu đề + tên tệp + cỡ + ngày, **toàn bộ** thư từ người gửi
  đối tác. Báo cáo `.md` **đã che tên khách** (`KHACH_001`…):
  - tổng số thư, thư đầu tiên / gần nhất, số thư theo tháng; dung lượng PDF trung bình / lớn nhất / **tổng** (để biết kho tệp cần bao nhiêu);
  - các KIỂU tiêu đề và tên tệp dạng mẫu (`<TEN>_<6so>-<6so>_<MA>_TMD.pdf`) + số thư mỗi kiểu;
  - danh sách **mã xét nghiệm** trong tên tệp + số lần;
  - thư có 0 hoặc ≥ 2 PDF; thư không theo mẫu; cùng khách + cùng mã gửi ≥ 2 lần;
  - tỉ lệ PDF đọc được chữ (thử `chu_pdf` 20 tệp, chỉ đếm).
- **Xong khi:** khoá chạy được, có báo cáo (Tuyền dùng báo PM).

### G1 — Migration (dải `2026110920xxxx`)
- `doi_tac.email_gui_ket_qua text NULL` (chữ thường; unique theo clinic khi khác NULL).
- `doi_tac_dich_vu.ma_ben_doi_tac text NULL` (chữ hoa; unique theo (doi_tac_id, ma) khi còn hoạt động).
- `xet_nghiem_cai_dat.gmail_tu_ngay date NULL`.
- `drive_tep`: `nguon` (`DRIVE`/`GMAIL`, mặc định `DRIVE`), `email_message_id`, `email_tieu_de`,
  `email_than` (text, tối đa 2.000 ký tự), `email_nhan_luc`, `ma_ben_doi_tac_tep`,
  `goi_y_order_id`, `goi_y_clinic_patient_id`. Lý do mới: `LUU_TRU` (chỉ dòng GMAIL), `CHUA_LAY_MAU`, `CO_BAN_MOI`.
  **Đổi khi làm (09/11):** thay cho một cột `vi_tri_tep`, dòng Gmail mang **bộ cột đẩy tệp** giống
  `tep_ket_qua` (`khoa`, `sha256`, `vi_tri`, `tai_len_luc`, `da_day_luc`…) để `day_tep` đẩy PDF lên
  CFS bằng đúng đường cũ (G2 thêm `drive_tep` vào `BANG_TEP`). Trigger "sự việc không sửa" luôn cho
  sửa cột đẩy (cả sau Từ chối), nhưng một câu đổi kèm cột sự việc vẫn bị chặn.
- `drive_nhip`: thêm `nguon` vào khoá; cột `con_tro_lich_su text`, `so_lich_su_con int`.
- Quyền `xet_nghiem.kho_email` (không gắn gói vai nào; trigger Postgres bỏ khối `kho_email` khỏi
  `quyen_preset`, lệnh lưu nhóm cũng từ chối). **Đổi khi làm:** sự kiện `lab.archive_viewed` và công
  tắc lego "Kho email" khai ở **G2** cùng code phát / trang + mục thanh bên — repo có test cấm sự
  kiện không nơi phát và lego không có trang.
- Che staging: tên tệp, tiêu đề, thân thư `drive_tep` (chạy được cả khi prod chưa có cột thư).
- **Thứ tự lên prod:** áp migration rồi deploy NGAY trong cùng đợt — `drive.py` bản cũ ghi nhịp
  `ON CONFLICT (clinic_id, doi_tac_id)`, khoá chính cũ đã bỏ ⇒ nhịp Drive lỗi tới lúc deploy (không
  mất tệp). Áp ngoài giờ khám: thêm lại CHECK của `tep_ket_qua` quét cả bảng.

### G2 — Đọc Gmail + lưu tệp + KHO EMAIL (Tuyền xem được ngay sau chặng này)
- `services/xet_nghiem/gmail_api.py` (≤ 250 dòng): token; `liet_ke(q, trang)`; `doc_thu(id)` (tiêu đề,
  ngày, thân text/plain, các phần PDF kèm `partId`/`attachmentId`/tên/cỡ); `tai_phan(id, attachmentId)`.
  Lỗi ⇒ `GmailError` câu ngắn, không chứa token. Trần tệp 30 MB.
- `services/xet_nghiem/gmail.py`: mỗi vòng, mỗi đối tác có `email_gui_ket_qua`:
  (1) thư mới sau lần quét OK cuối − 2 ngày; (2) rồi tối đa 100 thư cũ theo `con_tro_lich_su`.
  Mỗi PDF: lưu byte ⇒ dòng `drive_tep` (`nguon='GMAIL'`). Thư trước mốc ⇒ `LUU_TRU` + gợi ý khách (mục 1.10).
  Ở chặng này thư sau mốc cũng tạm `LUU_TRU` (ghép bật ở G3).
- **Tách lõi chung với Drive** thay vì chép: `nhan_mot` nhận `TepVao` (tên, byte, chữ kèm, người gửi,
  nguồn). `drive.py` không dài thêm; file ≤ 400 dòng, hàm ≤ 60 dòng.
- **Màn Kho email** `/ban-xet-nghiem/kho-email` (chỉ người có `xet_nghiem.kho_email`; người khác 404 ở máy chủ):
  - bảng: ngày nhận · khách (tên trong thư) · năm sinh · mã xét nghiệm · trạng thái (Lưu trữ / Đã ghép vào … / Chờ ghép tay) · gợi ý khách;
  - lọc theo khoảng ngày, mã xét nghiệm, trạng thái; tìm theo tên (bỏ dấu) hoặc SĐT;
  - bấm dòng ⇒ hộp xem PDF (Lightbox như bàn khám) + tiêu đề + thân thư; mỗi lần mở ghi `lab.archive_viewed`;
  - thanh trên cùng: "Đã nạp 1.240 / ~1.900 thư · Email ổn · quét lúc 10:42".
- Mục thanh bên "Kho email kết quả (tạm)" — máy chủ trả cờ, chỉ hiện với người có quyền.
- **G2a xong (09/11, nhánh `claude/gmail-ket-qua-g2`)** — máy chủ: `gmail_api.py` (httpx, khoá
  `GOOGLE_GMAIL_OAUTH_FILE` / secret `gmail_oauth`, tệp rỗng ⇒ tắt; đọc cả Thùng rác), `gmail.py`
  (vòng trong `drive-xn`: thư mới sau `ok_cuoi − 2 ngày` + một trang lịch sử ≤ 100 thư theo con
  trỏ; header From thật phải đúng đối tác; tải HẾT PDF của thư rồi mới ghi; byte vào ổ VPS
  `<clinic>/gmail/<thư>/<uuid>.pdf` 0600; dòng `LUU_TRU` + gợi ý khách + mã `\d{6}-\d{6}`),
  `day_tep.BANG_TEP` thêm `drive_tep` (đẩy CFS), canh gác `GMAIL_KHONG_NHIP` (> 1 giờ).
  Sau soát G2a (3 chặn đã sửa): **khoá = hộp thư của MỘT phòng khám** — env `GMAIL_CLINIC_ID`
  (thiếu ⇒ không quét; phòng khám khác đặt trùng email đối tác không đọc được thư); **cả thư
  một giao dịch** (ghi hết byte rồi mọi dòng, lỗi ⇒ dọn tệp, không thư lưu dở); **lỗi riêng
  một thư** (quá trần 10 MB/PDF · 20 MB/thư, base64 hỏng, CHECK từ chối) ⇒ bỏ thư đó, không
  chặn đối tác; con trỏ trang bị Gmail từ chối (400) ⇒ đọc lại từ đầu; quá 5 trang thư mới ⇒
  quét lại lịch sử. Câu tìm `filename:pdf -in:spam` (Thùng rác vẫn đọc, Spam thì không). Log
  không chứa chuỗi lỗi DB. Vòng lưu tách sang `gmail_luu.py` (trần 400 dòng).
  **Đổi:** lõi chung `nhan_mot(TepVao)` với Drive dời sang **G3** — G2 chưa ghép gì nên chưa có
  gì để chung; G3 bật ghép thì tách lõi trong cùng PR. **Còn G2b:** màn Kho, sự kiện
  `lab.archive_viewed`, lego, nhánh `nguon` trong `ghep_tay` (xem/Gán dòng Gmail đọc byte ở
  `khoa`, chặn `LUU_TRU` khi không có quyền Kho). ⚠️ **G2a không lên prod trước G2b** (cửa
  `ghep_tay` theo id chưa chặn dòng Gmail — cùng một đợt).
- **Mang sang từ soát G2a (09/11):**
  - G3: kiểm `Authentication-Results` (dkim/spf pass) trước khi TỰ GHÉP — header From giả được.
  - G4: đổi `email_gui_ket_qua` ⇒ đặt lại con trỏ lịch sử (`so_lich_su_con = NULL`), không thì
    thư cũ của địa chỉ mới không bao giờ nạp.
  - `/ops` (`day_tep.so_lieu`) + canh gác `tep_cho_lau`/`tep_loi_day` chỉ đếm `tep_ket_qua` —
    PDF Gmail kẹt đẩy CFS chưa hiện (kẽ có sẵn từ ảnh CK; Gmail làm nó lớn hơn).
  - Staging: không có khoá Gmail mà `email_gui_ket_qua` được giữ khi che ⇒ `GMAIL_KHONG_NHIP`
    kêu mãi ở staging (như Drive).
- **Mang sang từ soát G1 (09/11):**
  - `ghep_tay._dong_cho` / `noi_dung_cho` mở mọi dòng `drive_tep` theo id và gọi Drive bằng
    `file_id` ⇒ phải tách theo `nguon` (Gmail đọc byte ở `khoa`), và dòng `LUU_TRU` chỉ xem / Gán /
    Từ chối được khi có `xet_nghiem.kho_email` — không thì là đường lách quyền Kho.
  - Cắt `ten` ≤ 300, `email_tieu_de` ≤ 500, `email_than` ≤ 2.000 trước khi ghi (CHECK từ chối ⇒ mất thư).
  - Ghi gợi ý `goi_y_*` phải lọc `clinic_id` (khoá ngoại không kèm clinic_id, như phần còn lại repo).
  - `khoa` của PDF Gmail riêng (`<clinic>/gmail/…`); G3 tạo `tep_ket_qua` thì CHÉP sang khoá mới,
    không dùng chung khoá — không thì `don_ban_vps` của bảng này xoá bản VPS của bảng kia.

### G3 — Ghép tự động cho thư sau mốc
- `ghep_khach.khop_khach` thêm `nam_sinh: int | None`, `ma_xn: str | None`:
  1. SĐT có trong chữ **và** tên (bỏ dấu, nguyên cụm) có trong chữ.
  2. Nhiều khách ⇒ giữ khách khớp năm sinh; ≠ 1 ⇒ `NHIEU_KHACH`.
  3. Một khách nhiều việc ⇒ giữ việc có `ma_ben_doi_tac == ma_xn`; ≠ 1 ⇒ `ONG_NHIEU_VIEC`.
- Đọc từ thư (hàm thuần, test bảng): `NS: (\d{4})`; mã xét nghiệm = phần giữa `\d{6}-\d{6}_` và
  `_<ma_ngan đối tác>.pdf`; `\d{6}-\d{6}` ⇒ `ma_ben_doi_tac_tep`. Không khớp mẫu ⇒ None, **không ném**.
- Chữ đem ghép = tiêu đề + thân + tên tệp + chữ PDF.
- Ứng viên: việc đang chờ kết quả (tự ghép); việc đã thu chưa lấy mẫu (`CHUA_LAY_MAU` + gợi ý);
  việc đã có tờ trong 120 ngày (`CO_BAN_MOI` + gợi ý).
- Bật ghép cho thư sau mốc; thư `LUU_TRU` sau mốc tạo ở G2 được xét lại **một lần**.
- **G5 (11/11, Tuyền duyệt "gán full"; nhánh `claude/gmail-g5-gan-full`)** — đo prod 11/11: chỉ
  1 đối tác (Medlatec), HPV/NIPT 0 việc ở Bàn XN, 0 lần bấm Lấy mẫu ⇒ luật G3 không gán được gì.
  Luật mới: ứng viên = MỌI chỉ định loại xét nghiệm lab làm (gán ở Cài đặt → Đối tác, hoặc việc
  Bàn XN chụp đúng lab), tạo trong **60 ngày trước giờ nhận thư**, không cần Lấy mẫu. Chỉ định đã
  có **tờ tải tay** ⇒ thư vẫn gắn thêm, hai tờ song song (Tuyền 11/11). Đã có tờ từ Gmail ⇒ thư
  mới hơn = CO_BAN_MOI, không mới hơn = Lưu trữ DA_CO_KET_QUA. Lý do mới: KHONG_THAY_CHI_DINH,
  KHONG_RO_MAU_THU; Lưu trữ có `luu_tru_vi_sao` (migration `20261111100000`), hiện ở Kho email.
  Gán ngược: đặt mốc lùi (01/10) trước lần quét đầu. Drive giữ luật 05/11 (Bàn XN + Lấy mẫu).
- **G3a xong (09/11, Tuyền DUYỆT luật dưới đây; nhánh `claude/gmail-ket-qua-g3`)** — máy chủ:
  `gmail_doc.py` (đọc thư từng lab, hàm thuần; đo trên thư thật: đủ tên + SĐT để xét ghép TM 97,5% ·
  HD 96,3% · GL 73% (phần còn lại đúng là "Chưa đủ kết quả") · EU ~99% PDF kết quả), `gmail_ghep.py`
  (MỘT hàm `quyet` + `gan_tu_dong` qua `tai_len` nguồn GMAIL ⇒ CHO_XAC_NHAN), `ghep_khach.khop_ds` =
  luật khớp duy nhất Drive + Gmail, DKIM/DMARC `xac_thuc_ok`, hàng ghép tay nhận thư Gmail sau mốc
  (byte đọc ở `khoa`), lý do mới CHUA_LAY_MAU / CO_BAN_MOI kèm `goi_y_order_id`. **Đổi:** mốc chỉ áp cho
  thư NHẬN SAU khi đặt mốc — thư đã vào Kho trước đó không xét lại tự động (đơn giản, không cần cột
  đánh dấu). **Còn G3b:** màn tab Kết quả hiện nguồn Email + nút "Gán theo gợi ý".
- **⚠️ ĐỀ XUẤT CHỈNH LUẬT G3 sau khi phân tích thư thật 4 lab (09/11) — ĐÃ DUYỆT 09/11.**
  Báo cáo đã che tên (máy Mac, không vào repo): mọi lab đều có SĐT khách ⇒ luật "tên + SĐT bắt buộc"
  áp được cả 4. Chỗ kế hoạch cũ sẽ GHÉP SAI và đề xuất thay:
  | | True Medicine | Greenlab | High Detect | Eurofins |
  |---|---|---|---|---|
  | Tên | tiêu đề | tiêu đề | tiêu đề | tiêu đề |
  | SĐT | chỉ trong PDF (nhãn `SĐT:`) | tiêu đề (kiểm `0\d{9}`, hỏng ⇒ PDF) | tiêu đề (như GL) | PDF, không nhãn — chỉ khi PDF có ĐÚNG một số di động, không thì ghép tay |
  | Năm sinh (gỡ trùng) | thân `NS:` | PDF `Năm sinh:` | PDF `NS:` | PDF (ngày có năm ≤ 2012) |
  - **Bỏ "mã xét nghiệm từ TÊN TỆP"**: tên tệp True Medicine sai loại (`_TQ` chứa HPV, `_HPV` chứa PCR).
    Một khách nhiều việc cùng đối tác ⇒ G3 bản đầu đưa **ghép tay** (`ONG_NHIEU_VIEC`), chưa tự chọn việc;
    tự chọn theo tên xét nghiệm trong CHỮ PDF ↔ `ma_ben_doi_tac` làm sau khi có dữ liệu thật.
  - **Không ghép theo mã mẫu của lab** (True Medicine có một mã gửi 4 lần với 4 tên khác nhau).
  - **Greenlab trả kết quả từng phần** (`Trạng thái: Chưa đủ / Đủ kết quả`): chỉ TỰ GHÉP thư "Đủ kết quả";
    thư "Chưa đủ" vào Kho + gợi ý (bản đầy đủ đến sau). Bản sửa thật ⇒ `CO_BAN_MOI` (ghép tay) như kế hoạch.
  - **Bỏ tệp không phải kết quả**: Eurofins `NIP\d{7}.pdf` (phiếu mã vạch) + ảnh chữ ký PNG; tệp
    `_\d{2}.pdf` scan của GL/HD (vào Kho, không tự ghép vì không đọc được chữ).
  - **Kiểm DKIM/SPF pass** (`Authentication-Results`) trước khi tự ghép (đã ghi ở "Mang sang G2a").
  - Không dùng địa chỉ cơ sở in trên PDF (Eurofins vẫn in "Kim Ngưu").
- Dời từ G4 sang G3 (cần dòng Gmail ở hàng ghép tay trước): tab Kết quả hiện dòng nguồn Email (tiêu đề +
  giờ nhận), câu lý do mới, nút **Gán theo gợi ý**; nhánh nguồn GMAIL trong `ghep_tay` (xem / Gán đọc byte
  ở `khoa`).

### G4 — Màn cài đặt + đèn + gợi ý
- **G4 xong (09/11, nhánh `claude/gmail-ket-qua-g4`)**: ô Email gửi kết quả (đổi ⇒ đặt lại con trỏ lịch sử;
  vòng quét đang chạy bằng email cũ không ghi đè được), Mã bên đối tác (giữ khi bảng gán thứ hai không gửi),
  mốc tự ghép (cửa riêng), đèn Email (luật chung `den_nhip`). "Gợi ý danh sách mã từ báo cáo G0" BỎ — mã
  lấy từ chữ PDF (xem đề xuất G3), danh mục xét nghiệm từng lab có trong báo cáo phân tích cho Tuyền điền tay.
- Cài đặt → Đối tác: ô "Email gửi kết quả"; bảng gán xét nghiệm thêm cột "Mã bên đối tác" (gợi ý danh
  sách từ báo cáo G0); ô "Tự ghép kết quả email từ ngày" (Quản lý).
- Thẻ đối tác: đèn "Email ổn · quét lúc 10:42" / "Email lỗi …" (dùng lại `den_drive`, chữ theo nguồn).
- Tab Kết quả: dòng nguồn Email hiện tiêu đề + giờ nhận; câu lý do mới; nút **Gán theo gợi ý**.
- Không luật trong TSX: chữ, màu, gợi ý, ẩn/hiện đều do máy chủ trả.

---

## 4. Ca biên — mỗi ca một test

| Ca | Phải xảy ra |
|---|---|
| Thư từ người gửi khác (kể cả cùng tiêu đề) | Không đọc, không vào Kho |
| Thư trước mốc | Vào Kho `LUU_TRU`, không ghép, không thông báo, không đụng việc bàn cũ |
| Nạp lịch sử 2.000 thư | Mỗi vòng ≤ 100 thư cũ; thư mới đến giữa chừng vẫn ghép trong ≤ 3 phút; dừng / chạy lại tiếp đúng con trỏ |
| Quét hai lần cùng thư | Lần hai không tạo gì (`email_message_id` + `partId`) |
| Thư 2 PDF | Hai dòng, mỗi PDF xử lý riêng |
| PDF scan | Không SĐT ⇒ không tự ghép (`KHONG_DOC_DUOC`); vẫn vào Kho, vẫn xem được |
| Mẹ con chung số | Năm sinh gỡ; vẫn trùng ⇒ `NHIEU_KHACH` |
| HPV + ThinPrep, thư HPV về | Ghép đúng HPV nhờ `ma_ben_doi_tac`; chưa điền mã ⇒ `ONG_NHIEU_VIEC` |
| Quên bấm Lấy mẫu | `CHUA_LAY_MAU` + gợi ý |
| Đối tác gửi bản sửa | `CO_BAN_MOI` + gợi ý; Gán ⇒ bản 2; bản 1 đã gửi ⇒ báo CSKH gửi lại |
| Người không có quyền Kho gọi thẳng API Kho / mở PDF Kho | 404, không lộ có hay không |
| Mở PDF trong Kho | Có sự kiện `lab.archive_viewed` (ai, lúc nào, dòng nào) |
| Token hết hạn / bị thu hồi | Nhịp lỗi "Mất quyền đọc Gmail — cấp lại quyền"; > 1 giờ ⇒ đèn đỏ + canh gác |
| Gmail 429 / 5xx | Lượt sau thử lại; thư chưa lưu xong không có dòng `drive_tep` |
| Hai phòng khám | Mỗi `clinic_id` một khoá, không thấy thư nhau |

---

## 5. Kịch bản bấm thử (staging, Gmail THỬ)

1. Từ Gmail "đối tác" (tài khoản thử thứ hai) gửi 5 thư giả đúng mẫu, ghi ngày trong tiêu đề là tuần trước.
2. Quản lý: Cài đặt → Đối tác → Email gửi kết quả = địa chỉ đó; mốc tự ghép = hôm nay; gán HPV ↔ `HPV`.
3. Cấp quyền Kho cho tài khoản Tuyền. ≤ 3 phút: Kho có 5 dòng "Lưu trữ", mở được PDF; tài khoản Quản lý khác **không** thấy mục Kho.
4. Tạo khách "Trần Thị Mẫu", NS 1990, SĐT 0900000123; chỉ định HPV + ThinPrep; thu; lấy mẫu.
5. Gửi thư mới, PDF có tên + SĐT, tệp `TRAN_THI_MAU_091126-000001_HPV_TMD.pdf` ⇒ ≤ 3 phút việc HPV "Đã có kết quả", BS + CSKH có thông báo, ThinPrep vẫn chờ; Kho có dòng "Đã ghép".
6. Thư cho khách chưa bấm Lấy mẫu ⇒ dòng đỏ "Khớp khách nhưng chưa bấm Lấy mẫu" ⇒ Gán theo gợi ý.
7. Gửi lại thư bước 5 (PDF khác) ⇒ "Có bản mới" ⇒ Gán ⇒ bản 2.
8. Thu hồi quyền ứng dụng ở tài khoản Google thử ⇒ đèn Email đỏ, câu dễ hiểu.
9. Hộp thư Gmail **không đổi gì**; Drive không có tệp mới.

---

## 6. Không được làm

- Không xin phạm vi khác ngoài `gmail.readonly`; không gửi, xoá, sửa, gắn nhãn thư.
- Không gõ / đọc / chụp mật khẩu, mã 2 bước; không tự bấm "Cho phép" thay Tuyền.
- Không ghi nội dung thư / PDF / tên khách ra log; log chỉ id thư + lý do. Báo cáo G0 che tên.
- Không đọc hộp thư thật từ staging hay máy dev (trừ script G0 chỉ đọc tiêu đề/tên tệp).
- Không commit, không dán vào chat: client secret, refresh token.
- Không tự ghép thư trước mốc; không tự ghép khi thiếu SĐT hoặc tên; không ghép theo mã `\d{6}-\d{6}`.
- Không gỡ `CHO_XAC_NHAN` / trigger cấm gửi tệp chưa xác nhận; không đổi luồng Drive (test Drive cũ xanh).
- `doi_tac_service.py` / router `doi_tac.py` đóng băng.
- Không áp migration lên prod/staging, không deploy. AI soạn lệnh, Tuyền chạy.

## 7. Đầu ra mỗi chặng

Nhánh `claude/gmail-ket-qua-g<n>` từ `origin/main` → PR; `./scripts/ci-may.sh --bao-github` xanh;
báo cáo 4 mục SO-LUAT 12.4. Cập nhật `docs/KE-HOACH-XET-NGHIEM-DOI-TAC.md` (nguồn Gmail),
`docs/DANG-LAM.md`, `docs/BAN-DO-CODE.md`.

---

## 8. Nhật ký G0 (09/11/2026)

**Tra tài liệu Google (09/11)** — khớp kế hoạch, không đổi hướng:
- Refresh token hết hạn sau 7 ngày **chỉ khi** ứng dụng External ở trạng thái *Testing*
  ([developers.google.com/identity/protocols/oauth2](https://developers.google.com/identity/protocols/oauth2)).
  ⇒ bắt buộc **In production**.
- `gmail.readonly` là phạm vi **restricted**. Tự dùng, < 100 người ⇒ không bắt buộc xác minh; người
  cấp quyền bấm qua màn "Google chưa xác minh ứng dụng này" ([support.google.com/cloud/answer/13464323](https://support.google.com/cloud/answer/13464323)).
- Token chết khi: **đổi mật khẩu Gmail phòng khám** (token có phạm vi Gmail), 6 tháng không dùng,
  bị thu hồi, > 100 token / client. ⇒ G2 phải có nhịp lỗi "Mất quyền đọc Gmail — cấp lại quyền".
- Gmail phòng khám là tài khoản @gmail.com ⇒ không chọn được Audience *Internal*.
- Rủi ro mở: vài báo cáo diễn đàn nói ứng dụng chưa xác minh vẫn hết hạn 7 ngày dù đã
  production — tài liệu chính thức không nói vậy. Kiểm: chạy lại `gmail-do-hop-thu.py` sau ≥ 8 ngày.

**Đã cài trên Google Cloud** (tài khoản `pksanthanhluong@gmail.com`, Tuyền bấm theo hướng dẫn):

| Mục | Giá trị |
|---|---|
| Dự án | `clinic-ai-ket-qua` (không tổ chức, không billing, không bản dùng thử) |
| API bật | Gmail API (chỉ một) |
| Branding | tên "Clinic AI – đọc kết quả xét nghiệm"; trang chủ `https://dr4women.io.vn`; chính sách `https://dr4women.io.vn/chinh-sach-rieng-tu` (**chưa có trang thật** — chỉ cần nếu sau này gửi xác minh); tên miền `dr4women.io.vn`; không logo |
| Audience | External · **In production** (chưa xác minh; dải vàng "requires verification" bỏ qua) |
| Data access | đúng một phạm vi `.../auth/gmail.readonly` |
| Client | loại **Desktop app**, tệp ở `~/.clinicai/gmail-client.json` (600, ngoài repo) |
| Cấp quyền | **xong 09/11 chiều** (Google đòi xác minh chủ tài khoản trước màn "chưa xác minh"); khoá `~/.clinicai/gmail-oauth.json` trên Mac, chưa lên VPS |

**Khoá trên VPS (theo cách khoá Drive):** tệp `/home/clinicai/gmail-oauth-prod.json`, cùng chủ/quyền với
`/home/clinicai/drive-sa-prod.json`; `.env.prod` có `GOOGLE_GMAIL_OAUTH_KEY_FILE=<tệp đó>`. G2 thêm vào
`docker-compose.yml` secret `gmail_oauth: file: ${GOOGLE_GMAIL_OAUTH_KEY_FILE:-./docker/khong-co-khoa-gmail}`
và biến trong container `GOOGLE_GMAIL_OAUTH_FILE=/run/secrets/gmail_oauth`. Staging dùng Gmail THỬ, khoá riêng.

**Cấp quyền xong 09/11 chiều** (Google đòi xác minh chủ tài khoản trước màn "chưa xác minh").

**Đo True Medicine** (`gmail-do-hop-thu.py`, báo cáo che tên ở `~/.clinicai/` trên Mac):
1.432 thư hộp thư chính (31/08/2025 → nay), 963 khách, đúng 1 PDF/thư, tổng 555 MB.
Tiêu đề 100% một mẫu (ngày `dd/mm/yyyy` hoặc `dd-mm-yyyy`); tên tệp 89% `<TÊN>_<6số>-<6số>_<MÃ>_TMD.pdf`,
11% mẫu cũ không có mã; mã chỉ có `HPV` (801) và `TQ` (476 — **Tuyền cần xác nhận là gì**).
20/20 PDF thử: có chữ, SĐT, tên, năm sinh **và có mã `081126-501726`** (khác mục 0 — quyết định 13 giữ nguyên
tới khi Tuyền đổi). Gmail giới hạn tốc độ: đọc song song bị 403 `rateLimitExceeded`, lần lượt ≈ 60 thư/phút.

**Phát hiện đổi phạm vi (Tuyền 09/11):**
- **Bốn đối tác gửi kết quả về Gmail**, không chỉ True Medicine:

  | Người gửi | Thư (kể cả Thùng rác) | Ở Thùng rác | Thư mới nhất | Tệp / thư |
  |---|---|---|---|---|
  | `truemedicine.laymauxn@gmail.com` | 1.952 | 520 | 09/11/2026 | 1 PDF |
  | `cskh@greenlab.vn` | 6.640 | 2.739 | 12/05/2026 | 2 PDF |
  | `reports@highdetectlab.com` | 467 | 0 | 08/11/2026 | 1 PDF |
  | `cvn007_nipt@eurofinsasia.com` | 99 | 0 | 09/11/2026 | 2 PDF + ảnh |

  ⇒ G1–G4 phải chạy cho mỗi đối tác có `email_gui_ket_qua` (thiết kế đã cho phép); luật đọc tên tệp / mã /
  năm sinh là **theo từng đối tác** (mẫu thư khác nhau) — đo xong mới chốt.
- **Nhân viên đang xoá thư kết quả** (Thùng rác tự xoá hẳn sau 30 ngày) ⇒ G2 nên đọc cả Thùng rác
  (`includeSpamTrash`) — **chờ Tuyền quyết**.
- **Tuyền 09/11: tải về TOÀN BỘ, không che** để xem đủ mẫu từng phòng xét nghiệm — đổi mục 6 ("không đọc hộp thư
  thật từ máy dev") cho riêng lần này. Script `scripts/gmail-tai-ve.py` (chỉ đọc) lưu ở
  `~/.clinicai/ket-qua-gmail/` trên Mac (thư mục 700, tệp 600, ngoài repo) + `danh-sach.csv`. Không chép đi đâu khác.
  **Mốc xoá bản này: xong G4** (đã có Kho trên hệ thống). Bản nằm trong `~/.clinicai` có thể lọt Time Machine /
  Spotlight — xoá bằng `rm -rf ~/.clinicai/ket-qua-gmail` khi tới mốc.

**Việc mang sang G2/G3 (soát thiết kế G0, 09/11):**
- Lọc `from:` chỉ xét header From — **giả mạo được**. Trước khi TỰ GHÉP vào hồ sơ khách (G3), kiểm
  `Authentication-Results` có SPF hoặc DKIM `pass` cho đúng tên miền người gửi; không pass ⇒ ghép tay, lý do riêng.
- Access token sống ~1 giờ: lớp gọi Gmail của G2 phải tự làm mới khi 401 (script G0 đã sửa sau khi soát).
- Mục 6 "script G0 chỉ đọc tiêu đề/tên tệp" — thực tế G0 có đọc 20 PDF trong bộ nhớ để đếm, và
  `gmail-tai-ve.py` tải toàn bộ theo quyết định trên.
