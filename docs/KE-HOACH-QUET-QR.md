# KẾ HOẠCH — Quét QR khách bằng điện thoại nhân sự (06/10/2026, bản nháp chờ Tuyền duyệt)

Nhánh: `claude/patient-qr-scan-feature-9b4b4d`. Chưa code dòng nào. Mọi đường dẫn file
dưới đây đã soát trên `main` 7b6d26fb.

## 0. Một câu

Bất kỳ nhân sự nào cầm điện thoại quét QR của khách (ảnh khách lưu trong điện thoại / Zalo) → thấy ngay **khách đang ở
đâu trong buổi**, **câu chỉ dẫn để nói với khách** (đi đâu, số mấy, trước còn mấy người)
và **việc của chính mình với khách này** theo lego + vị trí được xếp hôm nay.

## 1. Đã có gì (dùng lại, không viết luật thứ hai)

| Mảnh | Ở đâu | Dùng thế nào |
|---|---|---|
| Hành trình khách (đang ở / tiếp theo / các bước) | `services/hanh_trinh_khach_service.py` `dung_hanh_trinh_khach` :301, `doc_hanh_trinh_khach` :942 | Lõi của màn quét — đọc nguyên |
| Khung hành trình giao diện | `_lam-viec/HanhTrinhKhach.tsx` `KhungHanhTrinh` :279 | Gắn nguyên vào màn quét |
| Cắt phần được xem theo quyền | `xem_luot_service.py` `muc_duoc_xem` :156 | Lâm sàng / tài chính / thuốc ẩn theo quyền |
| Quyền thực tế = lego ∪ lịch hôm nay | `permissions/can.py` `quyen_hieu_luc` :129 (view `v_quyen_thuc_te`) | Quyết "việc của bạn" |
| Vị trí + phòng hôm nay | `api/identity.py` `doc_vi_tri_hien_hanh` :922, `GET /me/vi-tri-hom-nay` | Biết người quét đứng phòng nào |
| Cổng thu trước rồi mới làm | `services/finance_gate.py` `cua_lam` :180 | Câu chỉ dẫn "xuống quầy thu trước" |
| Số booking / số check-in | `appointment.so_booking`, `so_tiep_don`; `components/ui/SoLuot.tsx` | Hiện to để đối chiếu với khách |
| Tầng của phòng | `clinic_room.floor` (mig 20260804000011) | "Lên tầng 3 – Siêu âm 2" |
| Nhật ký mở hồ sơ | `permissions/y_khoa.py` `ghi_mo_ho_so` :80 → `services/audit.py` `record_event` | Ghi "ai quét khách nào" |
| Nghe thay đổi tức thì | `useNgheBang` (SSE `/api/events/stream`) | Màn quét tự cập nhật khi khách di chuyển |
| Màn chọn sẵn khách qua `?luot=` | `/thu-ngan/*` (`QuayThuNgan.tsx` :194), `/pharmacy` (:24) | Nút "mở màn" nhảy thẳng tới khách |

**Chưa có** (phải làm): mã QR mờ cho khách · đường quét · thư viện đọc/vẽ QR (package.json trống)
· luật "việc của người quét" (hiện `tiep_theo` chỉ theo vị trí, không theo người xem)
· đăng nhập xong quay lại đúng link (`proxy.ts` :89 xoá path, luôn về /login → /home)
· `?luot=` ở Tiếp đón / Đo sinh hiệu / Tư vấn / Bàn khám / Phòng DV.

## 2. Quyết định thiết kế (kèm trade-off)

### 2.1 QR chứa gì → **URL có mã mờ theo KHÁCH**: `https://dr4women.io.vn/q/<ma_qr>`

- `ma_qr` = 16 ký tự ngẫu nhiên (base32, ~80 bit), cột mới `patient.ma_qr` UNIQUE, sinh
  bằng `DEFAULT` trong Postgres + backfill khách cũ trong cùng migration.
- **Vì sao không dùng `patient_code`** (`BN-YYYY-XXXXXX`): đoán được (đuôi lấy từ micro-giây),
  và là định danh khách → ảnh QR bị lan ra làm lộ mã khách (NĐ 13/2023). Mã mờ không mang
  nghĩa gì, đổi được khi mất giấy.
- **Vì sao không dùng `visit_id`** (UUID đã mờ sẵn, khỏi migration): chỉ sống một buổi; khách
  có lịch mà chưa check-in thì chưa có lượt → không quét được ở quầy. Theo khách thì một mã
  dùng mãi, máy chủ tự tìm lượt hôm nay.
- **Vì sao là URL chứ không chỉ mã**: camera mặc định của iPhone/Android đọc QR là mở link
  luôn → **không cần cài gì, không cần mở app trước**. Nút quét trong app là đường thứ hai.
- Mã QR **không phải chìa khoá**: `/q/*` vẫn đòi đăng nhập nhân sự. Người ngoài quét được
  chỉ thấy trang đăng nhập.

### 2.1b QR khách **BẤT BIẾN MÃI MÃI** (Tuyền hỏi 06/10) — được, ép ở Postgres

- `patient.ma_qr` NOT NULL, UNIQUE, sinh bằng `DEFAULT` lúc tạo khách; **trigger BEFORE UPDATE
  chặn mọi lần đổi** (bất biến ép ở database, không tin Python — CLAUDE.md "Luật").
- Không bao giờ dùng lại: khách không bị xoá cứng (soát 06/10: không có `DELETE FROM patient`
  trong code); 80 bit ngẫu nhiên nên trùng ngẫu nhiên coi như không thể.
- Gộp hồ sơ trùng sau này (`mpi_merge_queue` đã có hàng chờ, chưa có lệnh gộp): hồ sơ bị gộp
  **giữ nguyên mã**, máy đọc mã đi theo con trỏ sang hồ sơ còn lại → QR cũ của khách vẫn chạy.
- Mất giấy → **in lại đúng mã cũ**, khỏi cấp mới. Bỏ hẳn ý "Đổi mã QR" ở giai đoạn 3.
- **Cái giá của bất biến:** lộ ảnh QR thì không thu hồi được. Chấp nhận được CHỈ VÌ QR không
  bao giờ là chìa khoá. Đây thành **luật cứng cho mọi tính năng sau**: muốn cho khách tự xem
  kết quả bằng điện thoại thì phải có đăng nhập riêng (OTP SĐT), không bao giờ "quét QR là xem".
  Ghi luật này vào `docs/SO-LUAT.md` cùng PR A.

### 2.2 Ai thấy gì → **luật nằm ở máy chủ, theo LEGO + PHÒNG hôm nay** (không theo vai)

Đúng mô hình đã chốt 25/09 ("có node nào làm việc node đó") và 27/09 ("xếp vào phòng nào
hôm nay làm việc phòng đó"). Hàm thuần, bảng hoá, test được:

```
viec_cua_nguoi_quet(hanh_trinh, tinh_trang, quyen: set[str], phong_hom_nay: set[room_id]) -> list[Viec]
```

Mỗi việc chỉ là **lối vào màn chuẩn** (giai đoạn 1) — không tạo thao tác ghi mới.

| Người quét có lego | Khách đang ở trạng thái | Việc hiện ra |
|---|---|---|
| Tiếp đón | Có lịch hôm nay, chưa check-in | **Check-in** → `/reception/queue?lich=<appointment_id>` (chưa có lượt) |
| Tiếp đón | Bác sĩ đã hoàn tất, chưa check-out | **Check-out** → `/reception/checkout` |
| Đo sinh hiệu | Đang chờ sinh hiệu | **Bắt đầu đo** → `/do-sinh-hieu?luot=` |
| Khám tư vấn | Đang chờ tư vấn | **Bắt đầu tư vấn** → `/tu-van?luot=` |
| Bàn khám | Chờ bác sĩ chính / quay lại đọc KQ | **Mở phiếu khám** → `/ban-kham?luot=` (khách của tôi theo `khach_cua_toi`) |
| Phòng DV (phòng X hôm nay) | Có chỉ định ở phòng X, đã đủ điều kiện làm | **Bắt đầu \<dịch vụ\>** → `/phong/X?luot=` |
| Phòng DV (phòng X) | Chỉ định ở phòng X nhưng `cua_lam` chặn (chưa thu) | Không nút; chỉ dẫn "mời khách xuống quầy thu" |
| Thanh toán DV | Có khoản chưa thu | **Thu tiền** → `/thu-ngan/dich-vu?luot=` (đã chạy) |
| Thu tiền thuốc / Kho thuốc | Có đơn chưa thu / chưa cấp | **Thu thuốc** / **Cấp thuốc** → `?luot=` (đã chạy) |
| Điều phối | Đang chờ ở bất kỳ hàng nào | **Đổi phòng** → `/truong-ca?luot=` |
| Chăm sóc khách / DS bệnh nhân | Mọi lúc | **Hồ sơ khách** → `/customers?bn=` |
| Đặt lịch | Không có lịch hôm nay | **Đặt lịch** → màn Đặt lịch `?bn=` (đã có) |
| *(không lego nào khớp)* | — | Chỉ có câu chỉ dẫn + hành trình |

Người có nhiều lego thấy nhiều việc, xếp theo "đúng chỗ khách đang đứng" trước.

### 2.3 Câu chỉ dẫn — **máy chủ dựng sẵn, nhân sự đọc to**

Từ `dang_o` + `tiep_theo` + `clinic_room.floor` + `cua_lam`:

- "Mời chị lên **Tầng 3 – Siêu âm 2**. Số của chị **5**, trước chị còn **2** người."
- "Chị cần xuống **quầy thu ngân tầng 1** thanh toán trước khi làm **Siêu âm tuyến vú**."
- "Chị đang chờ **bác sĩ đọc kết quả** ở **Phòng khám Nội tiết**."
- "Chị đã xong buổi khám. Kết quả xét nghiệm đối tác sẽ được CSKH gửi sau."

Chỉ một chỗ sinh câu (Python) → màn quét, trang khách tự khai, TV sau này dùng chung.

### 2.4 Đọc QR trong app — **BarcodeDetector khi có, jsQR khi không**

| Cách | Android Chrome | iPhone Safari | Ghi chú |
|---|---|---|---|
| Camera mặc định của máy → mở link | ✔ | ✔ | Không cần code. iPhone mở **Safari**, không mở PWA (cookie riêng) → đăng nhập Safari một lần |
| `BarcodeDetector` (API trình duyệt) | ✔ | ✘ | Nhanh, 0 KB |
| `jsqr` (JS thuần, không phụ thuộc) | ✔ | ✔ | ~40 KB, chỉ tải khi mở màn quét |

Chọn: màn `/quet` dùng `getUserMedia` (camera sau) + BarcodeDetector nếu có, rơi về jsQR.
Camera cần HTTPS: prod và staging đã HTTPS (memory "HTTP thường…" 21/08 đã lỗi thời từ
16/09). **Local qua Wi-Fi (http://192.168…) KHÔNG mở được camera** → bấm thử camera trên staging.

Vẽ QR (màn "QR của khách" + trang khách tự khai): `qrcode-generator` (không phụ thuộc, ra SVG/PNG). Cài bằng
`npm i --save-exact`, không `npx` (memory `npx-tu-tai-goi-ngoai-du-an`).

### 2.5 Nhật ký — ghi ai quét khách nào, KHÔNG ghi nội dung

`record_event("patient.qr_scanned", patient_id, noi="quet-qr")` trong cùng giao dịch đọc
mã (SO-LUAT 8.1, 8.2). Gộp: cùng người–cùng khách trong 10 phút chỉ ghi một dòng (màn tự làm
mới không đẻ rác). Thêm nhãn ở `audit_labels.py` (có test chống lệch). **Không** đưa vào dòng
thời gian của lượt — quét không phải bước khám.

### 2.6 Khách nào / lượt nào khi quét

| Tình trạng | Màn quét hiện |
|---|---|
| Có lượt đang mở hôm nay | Hành trình đầy đủ + chỉ dẫn + việc |
| Có lịch hôm nay, chưa check-in | Giờ hẹn, bác sĩ, số booking + việc Check-in |
| Không lịch hôm nay | Thẻ khách + lượt gần nhất + việc Đặt lịch / Hồ sơ |
| Mã rác / không tồn tại / khách cơ sở khác | 404 rỗng, câu "Mã không đúng" — **không 500** (test đầu vào rác) |
| Hơn một lượt mở hôm nay (hiếm) | Danh sách để chọn |

Đối chiếu đúng người: tên to + năm sinh + 4 số cuối SĐT + số booking/check-in.

### 2.7 Khách mới hoàn toàn — **ai cũng mở được "QR mời tự khai"** (Tuyền thêm 06/10)

Không còn chỉ lễ tân nhập hồ sơ. Luồng:

```
Nhân sự bất kỳ                     Điện thoại CỦA KHÁCH                 Máy chủ
──────────────                     ────────────────────                 ───────
[+ Khách mới] ─────────────────────────────────────────────────────▶  tạo phiếu tự khai
màn hiện QR to (sống 30 phút)                                          (mã 128 bit, dùng 1 lần,
                                                                        gắn người tạo + cơ sở)
                  khách quét bằng camera ──▶ /k/<mã>  (KHÔNG đăng nhập)
                                             form: họ tên · ngày sinh · giới · SĐT ·
                                             (CCCD) · địa chỉ · đến khám vì gì ·
                                             ☐ đồng ý xử lý dữ liệu (NĐ 13/2023)
                                             [Gửi] ─────────────────────────▶ lưu vào phiếu, CHƯA tạo khách
màn nhân sự TỰ NHẢY ra thông tin khách vừa khai
+ cảnh báo trùng SĐT/CCCD (dùng đúng luật trùng của PatientService)
nhân sự đối chiếu mặt người, sửa nếu sai
HAI NÚT (Tuyền chốt 06/10 — tách rõ hai việc):
[Lưu & đăng ký] ───────────────────────────────────────────────────▶  tạo khách (hoặc nối khách cũ
                                                                        nếu trùng thật) + lịch hôm nay
                                                                        (WALK_IN), CHƯA check-in →
                                                                        hiện ở Tiếp đón "chờ check-in"
[Lưu & check-in] ──────────────────────────────────────────────────▶  như trên + check-in ngay
                                                                        (số check-in, vào luồng H1)
                                             trang tự đổi: "ĐÂY LÀ MÃ QR CỦA CHỊ —
                                             dùng mãi mãi"  [Lưu ảnh] [Gửi vào Zalo]
                                             + số booking / số check-in + câu chỉ dẫn
                                             ("Mời chị lên tầng 2 đo sinh hiệu")
```

**QR đến tay khách (Tuyền chốt 06/10): khách CHỤP LẠI hoặc LƯU VÀO ZALO — không in giấy.**
- Trang khách sau khi duyệt: QR to + nút **Lưu ảnh** (tải PNG có tên phòng khám + tên gọi khách)
  + nút **Gửi vào Zalo** (Web Share API chia sẻ ảnh → khách chọn Zalo / "Cloud của tôi"; máy
  không hỗ trợ chia sẻ thì nút ẩn, còn Lưu ảnh). Cần HTTPS — prod/staging đã có.
- Khách CŨ (không qua tự khai): mọi màn có khách (màn quét `/q`, Quản lý khách hàng, Tiếp đón)
  có nút **"QR của khách"** → hiện QR to trên màn nhân sự để khách chụp lại.
- Khi khách đưa điện thoại (ảnh QR trong máy / trong Zalo) → nhân sự quét màn hình điện thoại
  khách bằng nút Quét như bình thường.

**Vì sao nhân sự bấm duyệt, không cho khách tự tạo hồ sơ thẳng:**
1. **Trùng hồ sơ** — khách cũ quên mình từng đến. Luật trùng hiện có (khoá theo SĐT, cảnh báo
   CCCD) cần người quyết; MPI chỉ xếp hàng chờ, không tự gộp.
2. **Riêng tư** — ai đó gõ SĐT của người khác thì trang công khai **không được** lộ ra hồ sơ
   hay QR của người kia. Trang khách chỉ nói "nhân viên đang kiểm tra"; nhân sự nối đúng người
   sau khi nhìn mặt, rồi khách mới nhận QR (của hồ sơ cũ nếu là khách cũ).
3. **Ghi công khai không đăng nhập** là lần đầu hệ thống có. Gắn nó vào mã do nhân sự tạo
   (dùng 1 lần, 30 phút) thì chỉ người đang đứng trong phòng khám mới khai được — không cần
   chặn tần suất, không thêm hạ tầng (SO-LUAT Phần 7).

Chi phí cho nhân sự: **một lần bấm** sau khi khách khai xong. Vẫn "không khoá": mọi ô sửa được
trước và sau khi lưu; hoàn tác = huỷ lịch (hồ sơ khách giữ, không xoá dữ liệu).

**Đã cân nhắc và bỏ:** QR tĩnh dán ở quầy (không cần nhân sự bấm). Bỏ vì ai ở nhà cũng khai
được → hồ sơ rác, không gắn được với người đang đứng trước mặt. Muốn khách khai từ nhà = tính
năng **đặt lịch online**, làm riêng.

**Kỹ thuật:**
- Bảng `phieu_tu_khai` (ma, clinic_id, location_id, tao_boi, het_han, trang_thai MOI → DA_KHAI
  → XONG | HUY, du_lieu jsonb, patient_id, appointment_id). Đổi trạng thái chỉ đi tiến, ép
  bằng CHECK + trigger; nộp hai lần → lần sau bị từ chối (một dòng UPDATE … WHERE trang_thai='MOI').
- API công khai **riêng một router** (`routers/tu_khai_cong_khai.py`): chỉ 2 lệnh — `GET` trạng
  thái (trả đúng: còn hạn? đã duyệt? `ma_qr` khi XONG) và `POST` nộp. Schema chặt, giới hạn độ
  dài, ngày sinh rác → rỗng không ném (luật 3 lần 500), SĐT qua `core/phone.normalize_vn_phone`.
  FastAPI không lộ ra ngoài (Caddy chỉ trỏ vào dashboard) → vẫn qua proxy Next kèm X-API-Key.
- Next: `/k/` vào `PUBLIC_PATHS` của `proxy.ts`; trang khách không dùng SSE (cần đăng nhập) →
  hỏi trạng thái 3 giây/lần, dừng khi XONG/hết hạn.
- Duyệt: dùng lại `PatientService.create` (giữ khoá SĐT + cảnh báo trùng) + đường tạo lịch
  WALK_IN của `scheduling_service` + check-in của `LuotKhamService.check_in` — **không viết
  đường tạo khách thứ hai**. Đồng ý NĐ13 ghi qua `ConsentService` (`/patients/consents` có sẵn).
- Trang khách sau XONG chỉ hiện tên gọi + QR + số; hết 2 giờ thì trang chỉ còn "Đã hết hạn".

## 3. Hợp đồng API (để làm SONG SONG backend/frontend)

```
GET /api/v1/quet/{ma_qr}          guard: cua_noi_bo (mọi nhân sự nội bộ)
200 {
  khach:   { id, ten, nam_sinh, gioi, sdt_cuoi, ma_khach },
  tinh_trang: "TRONG_LUOT" | "CO_LICH_CHUA_DEN" | "KHONG_LICH_HOM_NAY",
  lich:    { appointment_id, gio, bac_si, so_booking } | null,
  luot:    { visit_id, so_tiep_don, so_booking } | null,
  cac_luot_mo: [ {visit_id, so_tiep_don} ],          // >1 lượt mở thì chọn
  hanh_trinh: <đúng dạng đầy đủ của dung_hanh_trinh_khach> | null,
  chi_dan: { cau, noi, tang, stt, so_nguoi_truoc, can_thu_truoc } | null,
  viec_cua_ban: [ { ma, nhan, href, lego, uu_tien } ],
  nguoi_quet: { vi_tri, phong: [ {room_id, ten} ] }
}
404 { } khi mã không hợp lệ
```

Tự khai (§2.7):

```
POST /api/v1/tu-khai                       guard: cua_noi_bo  → { ma, het_han }      (nhân sự tạo)
GET  /api/v1/tu-khai/{ma}                  guard: cua_noi_bo  → phiếu + du_lieu + trung[]
POST /api/v1/tu-khai/{ma}/duyet            guard: cua_noi_bo* body { ...du_lieu đã sửa, loai_kham, check_in: bool }
                                                               → { patient_id, appointment_id, visit_id?, ma_qr }
POST /api/v1/tu-khai/{ma}/huy              guard: cua_noi_bo
GET  /api/v1/cong-khai/tu-khai/{ma}        KHÔNG đăng nhập → { trang_thai, het_han, ten_goi?, ma_qr?, so_tiep_don?, chi_dan? }
POST /api/v1/cong-khai/tu-khai/{ma}        KHÔNG đăng nhập → 204 | 409 (đã nộp/hết hạn) | 422
```
\* quyền duyệt: §8 câu 5.

Next proxy: thêm `app/api/quet/[ma]/route.ts` — **chỉ chuyển tiếp** (SO-LUAT 3.2), kiểm định
dạng mã trước khi gọi.

## 4. Giao diện điện thoại (375 trước, 1280 vẫn dùng được)

```
┌──────────────────────────────┐
│ ← Quét khách khác            │
│ NGUYỄN THỊ A   1990 · …1234  │  ← đối chiếu người
│ [#12 | 7]  (SoLuot)          │
├──────────────────────────────┤
│ ĐANG Ở: Chờ — Siêu âm 2 (T3) │
│ từ 9:42 · STT 5 · trước 2    │
├──────────────────────────────┤
│ 💬 NÓI VỚI KHÁCH              │
│ "Mời chị lên Tầng 3 – Siêu   │
│  âm 2. Số của chị 5, trước   │
│  chị còn 2 người."           │
├──────────────────────────────┤
│ VIỆC CỦA BẠN                 │
│ [ Bắt đầu Siêu âm tuyến vú ] │  ← Button chính, chỉ khi có
│ [ Hồ sơ khách ]              │
├──────────────────────────────┤
│ ▸ Hành trình đầy đủ (gập)    │  ← KhungHanhTrinh
└──────────────────────────────┘
   [ 📷 Quét khách tiếp ]  (thanh dính đáy)
```

- Chỉ dùng thành phần trong `components/ui` (Button, NganGap, StatusChip, SoLuot), token
  `DESIGN.md`, `<button type=…>`, không hex/px/`style={{}}` mới.
- Tự cập nhật bằng `useNgheBang` khi lượt đổi.
- Lối vào: nút **Quét** ở `BottomNav` (mọi vai, điện thoại) + biểu tượng ở `GlobalHeader`
  (máy tính — dùng với máy quét cầm tay sau này) + ô `TimNhanh` nhận dán link/mã.
- `/quet` và `/q/*` vào **LUON_BAT** (cả `catalogue.py` :1037 lẫn `roles.ts` :720) — mọi
  nhân sự đều mở được; nội dung bên trong vẫn cắt theo quyền.

## 5. Chia việc — mỗi việc một agent · một worktree · một PR

| PR | Phạm vi | Phụ thuộc | Cỡ |
|---|---|---|---|
| **A. Máy chủ** | mig `patient.ma_qr` (+backfill, UNIQUE, DEFAULT) · `services/quet_qr_service.py` (tìm khách → lượt; `viec_cua_nguoi_quet`; `cau_chi_dan`) · `routers/quet.py` · trigger chặn đổi `ma_qr` · nhật ký + nhãn · `ma_qr` trong dữ liệu khách (Quản lý khách hàng, Tiếp đón) · luật "QR không là chìa khoá" vào SO-LUAT · `BAN-DO-CODE.md` | — | M |
| **B. Màn quét** | `/quet` (camera + jsQR) · `/q/[ma]` · proxy Next · nút BottomNav/GlobalHeader · LUON_BAT · **đăng nhập xong quay lại link** (`proxy.ts` thêm `?tiep=` chỉ nhận đường nội bộ bắt đầu `/`, chặn `//` — tránh open redirect) · `SITEMAP.md` | Hợp đồng §3 (dựng giả được) | M |
| **C. QR của khách** | nút "QR của khách" (hiện QR to) ở `/q`, Quản lý khách hàng, Tiếp đón · thành phần dùng chung vẽ QR + Lưu ảnh + Gửi Zalo (dùng lại ở trang khách của E) · **không in giấy** (Tuyền 06/10) | A (trường `ma_qr`) | S |
| **E. Khách mới tự khai** | mig `phieu_tu_khai` + trigger trạng thái · router nội bộ + router công khai · màn nhân sự "Khách mới" (QR to, tự nhảy khi khách khai, cảnh báo trùng, nút Lưu & đăng ký) · trang khách `/k/[ma]` (form → chờ → QR của khách) · `PUBLIC_PATHS` · nút "+ Khách mới" cạnh nút Quét | A (`ma_qr` + `cau_chi_dan`) | M–L |
| **D. Mở thẳng khách** | `?lich=`/`?luot=` ở `/reception/queue`, `?luot=` ở `/do-sinh-hieu`, `/tu-van`, `/ban-kham`, `/phong/[ma]`: mở sẵn đúng khách | — (song song) | M |

Giai đoạn 2 (sau khi Tuyền dùng thật giai đoạn 1): **bấm tại chỗ một chạm** cho thao tác
không có ô nhập — Check-in, Bắt đầu đo/tư vấn/khám/DV, Xong DV, Check-out — gọi ĐÚNG endpoint
màn chuẩn đang gọi, kèm hoàn tác (luật 01/10). Giai đoạn 3 (tuỳ): máy quét cầm tay ở quầy,
gửi QR qua Zalo khi có kênh. (Không có "đổi mã" — QR bất biến, §2.1b.)

Thứ tự: A trước (nền) · B, C, D song song với A theo hợp đồng §3 · E sau A.

## 6. Kiểm

- **pytest (DB chung `chung_test_db`):** bảng `viec_cua_nguoi_quet` — mỗi lego × mỗi trạng
  thái một dòng; người có 0 lego; phòng DV khác phòng hôm nay → không nút; `cua_lam` chặn →
  câu "xuống quầy"; mã rác (`""`, `"../"`, 500 ký tự, unicode) → 404; khách cơ sở khác → 404;
  backfill: mọi khách có `ma_qr`, không trùng; nhật ký gộp 10 phút; nhãn không lệch.
  **Bất biến:** `UPDATE patient SET ma_qr=…` bị Postgres từ chối; khách tạo mới (mọi đường:
  quầy, CSKH, tự khai) đều có mã. **Tự khai:** nộp sau hết hạn → 409; nộp hai lần (hai yêu cầu
  cùng lúc) → đúng một lần được; mã rác → 404 không 500; ngày sinh rác → rỗng; SĐT trùng khách
  cũ → trang công khai KHÔNG trả gì của khách cũ; duyệt nối khách cũ → khách nhận đúng `ma_qr`
  cũ; hoàn tác (huỷ lịch) giữ hồ sơ.
- **vitest:** vẽ QR bằng `qrcode-generator` → đọc lại bằng jsQR ra đúng link (khứ hồi);
  `?tiep=` từ chối `//evil.com`, `https://…`.
- **Bấm thật local (375 + 1280):** mở `/q/<mã>` của khách `DEMO-*` bằng 4 tài khoản
  `@dr4women.local` khác lego (lễ tân, điều dưỡng, bác sĩ, thu ngân) → mỗi người thấy việc khác
  nhau, câu chỉ dẫn giống nhau. Đi hết một buổi khám giả, xem màn tự nhảy.
- **Staging (điện thoại thật):** iPhone + Android: (1) camera mặc định → link → đăng nhập →
  quay lại đúng khách; (2) nút Quét trong app; (3) quét QR trên màn điện thoại khách (ảnh đã
  lưu, ảnh trong Zalo, màn tối/độ sáng thấp); (4) Lưu ảnh + Gửi vào Zalo trên iPhone và Android.
- CI cuối: `./scripts/ci-may.sh --bao-github`.

## 7. Rủi ro đã thấy

| Rủi ro | Giảm thế nào |
|---|---|
| iPhone: camera mặc định mở Safari, không mở PWA → phải đăng nhập lại | Hướng dẫn nhân sự dùng nút Quét trong app; Safari đăng nhập một lần là nhớ |
| Quét màn điện thoại khách bị loá / ảnh Zalo bị nén | QR mức sửa lỗi M, viền trắng đủ rộng, ảnh lưu ≥ 600px; thử ảnh đi qua Zalo trên staging |
| Khách không lưu, lần sau không có QR | Không sao: nhân sự tìm bằng tên/SĐT như hiện nay, bấm "QR của khách" cho khách chụp lại — mã vẫn là mã cũ |
| Ảnh QR của khách lan ra ngoài | Mã mờ, không mang nghĩa, đòi đăng nhập nhân sự — lộ mã vô hại; vì thế mới cho bất biến |
| Sau này ai đó làm "khách quét QR tự xem kết quả" → mã bất biến thành chìa khoá không thu hồi được | Luật cứng ghi vào SO-LUAT (§2.1b) |
| Trang công khai đầu tiên bị dùng để dò SĐT/hồ sơ | Không bao giờ trả dữ liệu khách cũ ra trang công khai; chỉ nhận ghi khi có mã do nhân sự tạo |
| Khách lớn tuổi không tự khai được trên điện thoại | Màn "Khách mới" của nhân sự có nút "Tôi nhập hộ" — cùng form, cùng đường duyệt |
| Màn quét thành "màn thứ hai" của luật | Mọi việc chỉ trỏ về màn chuẩn; giai đoạn 2 gọi ĐÚNG endpoint cũ, không endpoint mới |
| Quét liên tục đẻ rác nhật ký | Gộp 10 phút/người/khách |

## 8. Cần Tuyền chốt

1. ~~QR đến tay khách bằng gì?~~ **Tuyền chốt 06/10: khách chụp lại hoặc lưu vào Zalo** — không
   in giấy (§2.7, PR C).
2. ~~Mã theo khách hay theo lượt?~~ **Tuyền chốt 06/10: theo khách, bất biến mãi mãi** (§2.1b).
3. **Giai đoạn 1 chỉ "xem + chỉ dẫn + mở màn", bấm tại chỗ để giai đoạn 2?** Đề xuất: **có** —
   ra nhanh, không thêm đường ghi nào, đo xem nhân sự quét ở đâu nhiều rồi mới chọn nút một chạm.
4. ~~Check-in luôn?~~ **Tuyền chốt 06/10: HAI nút** — [Lưu & đăng ký] (tạo khách + lịch hôm
   nay, chờ check-in ở Tiếp đón) và [Lưu & check-in] (thêm check-in ngay). Hoàn tác như mọi
   thao tác: huỷ check-in / huỷ lịch, hồ sơ khách giữ.
5. ~~Ai duyệt?~~ **Tuyền chốt 06/10: MỌI nhân sự** — "Khách mới" + duyệt vào nhóm luôn bật
   (`LUON_BAT` ở `catalogue.py` và `roles.ts`), giới hạn cơ sở của người duyệt, có nhật ký.
6. ~~Loại khám?~~ **Tuyền chốt 06/10:** khách chọn gợi ý trong form; người duyệt sửa được; sau đó
   **ai có node tương ứng** (Tiếp đón / Đặt lịch) sửa được như lịch thường — không thêm quyền riêng.
