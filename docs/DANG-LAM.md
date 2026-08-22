# ĐANG LÀM — đọc file này trước khi bắt tay

Cập nhật: **22/08/2026 trưa**, sau Lát 3 + bộ kiểm đường ghi (mục 0 là mới nhất; các mục dưới là nền, đọc kèm).

File này giữ trạng thái đang dở của dự án. Nó tồn tại vì một phiên dài đọc lại
ngữ cảnh tốn nhiều hơn cả việc làm; cách chữa đã chốt với Quang là **chia thành
nhiều phiên ngắn, mỗi phiên một chủ đề**, và dùng file này thay cho việc cõng
lịch sử hội thoại.

> Bản trước của file này **chưa từng được commit** nên đã mất theo phiên. Từ giờ
> nó nằm trong git. Cuối mỗi phiên: cập nhật lại, nhất là mục "chờ Quang quyết"
> và "cạm bẫy".

---

## 0. Phiên 21→22/08/2026 — Chịu tải: Lát 1+2+3 xong, OOM tìm ra, đường ghi đã kiểm

**BỔ SUNG TRƯA 22/08 — Lát 3 + kiểm đường ghi (staging-0822e = `026669b7`):**
- **PR #162 (Lát 3)**: trang chủ gộp 6 vòng PostgREST + 3 endpoint rời về MỘT
  `GET /api/v1/home/bang-dieu-khien`; thêm SUSPENSE — lời chào + khung hiện
  tức thì, dữ liệu rót sau (hết cảnh bấm sidebar màn trắng). Đo: 54→35 câu
  SQL, 9→3 vòng, /home p50 dưới 100 người 3,6–3,7s → 2,9s. Khối theo vai do
  backend quyết từ identity. Suýt ship lỗi rò dữ liệu giữa người dùng (Map
  module-scope khử trùng lặp) — đã đổi sang `cache()` của React, có test canh.
- **Bộ kiểm ĐƯỜNG GHI dưới tranh chấp** (scratchpad `kiem-duong-ghi.py`,
  CHỈ CHẠY TRÊN STAGING — nó tạo lịch thật rồi huỷ mềm): 6/6 PASS giữa bão
  100 người đọc — đua ghế 15 người trần 2 → đúng 2 thắng 0×500; trùng khách
  5 lần → 1 lịch; giữ chỗ hiện chéo; huỷ đồng thời an toàn; sổ tương tác
  ghi/thấy/hoàn tác; khách inactive bị chặn 422. Sổ sự kiện cân từng cặp
  (created×8=cancelled×8). TUYỆT ĐỐI không chạy bộ này trên prod.
- Chip đã tạo: endpoint GET timeline tương tác mồ côi (không màn nào dùng,
  hiện cả dòng đã hoàn tác như thật) — chờ quyết gỡ hay sửa.

**CHECKLIST DEPLOY PROD batch #150–162 (Tuyền bấm, khung 1h–4h; đã soát
ngầm chỉ-đọc 22/08: prod đủ MỌI cột/bảng/view code mới đọc, chỉ thiếu đúng
hàm của bước 1):**
1. Áp migration TRƯỚC (bỏ qua bước này là lưới đặt lịch prod 500):
   `git fetch origin main && git show FETCH_HEAD:supabase/migrations/20260821000002_dem_ghe_ca_ngay_mot_lan.sql | ssh clinic-vps 'docker exec -i clinicai_db psql -U postgres'`
2. Bấm CD như mọi khi (prod tự nhận RAM 1g từ compose — không có override).
3. Ghi sổ migration prod (9 dòng 20260812000001→20260821000002, câu INSERT
   y như đã chạy trên staging — xem lịch sử phiên 22/08).
4. Trần pool supabase-stack prod (#158), lúc vắng khách:
   `docker compose -f docker-compose.supabase.yml --env-file .env.prod -p clinicai_db up -d auth rest`
5. Báo "xong" — phiên AI sẽ kiểm hậu-deploy CHỈ-ĐỌC: container có ký hiệu
   mới, /health, log sạch, RAM 1g, KHÔNG tạo dữ liệu nào trên prod.

**Nhiệm vụ Tuyền giao trước khi ngủ:** "đo lại staging → làm Lát 2 → làm hết
các nghi vấn, không làm hỏng hoặc kém đi, xong báo cáo."

**Đã lên staging (`staging-0822d` = `bc2de348`, xác minh bằng cách hỏi container):**
- **PR #157–159 (Lát 1)**: bộ nhớ tạm danh mục theo phòng khám, phân trang
  /customers 50 khách/trang, trần pool gotrue+PostgREST=10 (đăng nhập hết 500).
- **PR #160 (Lát 2)**: mười vòng PostgREST làm giàu màn khách hàng gộp về
  `GET /api/v1/cskh/man-khach-hang` — mười câu SQL chạy tuần tự trên MỘT kết
  nối asyncpg. Hình trả về bắt chước PostgREST từng trường nên page.tsx giữ
  nguyên phần dựng map. Guard 7 vai có test gương hai chiều với roles.ts.
- **Đo trước→sau** (cùng đêm, cùng máy, bảng đầy đủ trong PR #160):
  - Giải phẫu 1 lần mở /customers: 73→50 câu SQL, 14→4 vòng PostgREST,
    44→20 câu nghi lễ.
  - 100 người ảo ×3 vòng: /customers p50 5734→2705ms (−53%), p95 8144→4190ms;
    tổng 25,6→30,2 lượt/giây, 1300/1300 ok.

**Phát hiện lớn nhất đêm nay — OOM-kill worker im lặng:** `.env.staging` trên
VPS (cả hai bản) ghim `DASHBOARD_MEMORY_LIMIT=512m`, đè mặc định 1g mà #152
đưa vào compose. 4 worker ×~125MB vượt trần → kernel giết worker giữa response:
63/1300 lượt đứt kết nối (RemoteDisconnected/IncompleteRead), app-log sạch
bong. Chẩn đoán bằng `docker inspect --format '{{.State.OOMKilled}}
{{.HostConfig.Memory}}'`. Đã sửa env + `docker update --memory 1g` → 1300/1300
ok. **Prod không có override nên lần deploy tới tự nhận 1g — không cần sửa.**

**Đã ghi sổ migration staging**: 9 dòng `20260812000001`…`20260821000002` vào
`supabase_migrations.schema_migrations` (từng cái xác minh object trước khi ghi).

**Việc chờ Tuyền (prod — nút bấm của Tuyền, khung 1h–4h):**
1. Deploy batch #150–160 lên prod. **TRƯỚC đó** áp migration
   `20260821000002_dem_ghe_ca_ngay_mot_lan.sql` vào prod bằng psql
   (`git show FETCH_HEAD:supabase/migrations/20260821000002_dem_ghe_ca_ngay_mot_lan.sql | ssh clinic-vps 'docker exec -i clinicai_db psql -U postgres'`)
   — prod đã soát: đủ mọi migration khác, chỉ thiếu đúng cái này.
2. Ghi sổ prod (9 dòng, cùng câu INSERT như staging — xem PR #160 / phiên này).
3. Áp trần pool supabase-stack prod (#158): `docker compose -f
   docker-compose.supabase.yml --env-file .env.prod -p clinicai_db up -d auth rest`
   lúc vắng khách.
4. PR #144 (lễ tân) vẫn chờ quản lý duyệt trên staging.

**Nghi vấn đã đóng / còn mở:**
- ✅ RemoteDisconnected khi tải = OOM 512m (ở trên). ✅ Danh sách khách 5 giây
  = phân trang + Lát 2. ✅ Đăng nhập 500 khi đông = pool không trần (#158).
- ⏳ Suspense/streaming (P2 của cố vấn): hai trang nặng nhất (customers 1184
  dòng, home 489) đều là một server component nguyên khối, không Suspense.
  Đánh giá đêm nay: dưới tải, nút thắt là CPU render chứ không phải chuỗi
  chờ, nên streaming cải thiện cảm nhận (TTFB) chứ không tăng thông lượng —
  đáng làm thành LÁT 3 riêng, không sửa vội lúc cuối phiên.
- ⏳ /home p50 ~3,6s dưới 100 người: ứng viên Lát 3 (cùng cách gói như Lát 2).

**Cạm bẫy mới trả giá phiên này:**
- Sửa `mem_limit` trong git mà máy đích có `.env.*` ghim giá trị cũ thì
  override thắng IM LẶNG — đổi tài nguyên xong phải `docker inspect` máy đích.
- Container restart là `/tmp/tai.py` (harness đo tải) bay — chép lại trước
  mỗi lần đo, và đừng chạy đo song song với đo giải phẫu (bẩn cửa sổ log).
- 4 test biên đỏ khi Lát 2 dọn truy vấn về backend — ĐỎ ĐÚNG THIẾT KẾ; viết
  lại theo Luật 12.5: tiền đề dọn nhà thì test đi theo (giờ chúng đọc cả file
  Python). Đừng xoá assertion, đổi địa chỉ cho nó.

---

## 0.1 Phiên 21/08/2026 (Tuyền) — Ba ca làm việc, đã LÊN PROD trọn gói

**Một ngày nay chia BA ca thay vì hai, giờ do quản lý tự đặt.** PR #145–#148
đã gộp; prod deploy giữa giờ khám theo yêu cầu của Tuyền (vượt khung 1h–4h có
ghi lý do, run 32457538585, gián đoạn ~50 giây); staging = `staging-0821f`.

- **Kernel**: `core/shifts.py` viết lại — `shift_window()` (một khoảng) thành
  `shift_windows()` (danh sách), vì "cả ngày" nay là HAI khoảng rời nhau do
  nghỉ trưa. Giờ ca đọc từ `clinic.settings->'ca_lam_viec'`, mặc định Dr4Women:
  sáng 08:00–13:00 · chiều 14:00–17:30 · tối 17:30–21:30.
- **Migration `20260821000001`** đã áp CẢ HAI database (prod áp 21/08 chiều,
  đo trước khi áp: 1 lịch sống duy nhất nằm trong khung, 0 lịch từng đặt sau
  21:30 nên thu giờ đóng 23:00→22:00 không đụng ai).
- **Luật mới — chỉ đặt lịch TRONG ca** (`_chan_dat_ngoai_khung_ca`): gắn ở
  đúng 2 đường chọn giờ (đặt mới, đổi lịch); cố ý KHÔNG gắn ở đường gán bác sĩ
  để lịch cũ ngoài ca vẫn gán được. Lưới + 5 màn chọn giờ thôi mời giờ ngoài
  ca (mời-rồi-mắng làm người trực mất niềm tin vào lưới).
- **Quản lý tự sửa giờ ca**: Cài đặt → Luật đặt lịch → thẻ "Giờ ca làm việc"
  (Trưởng ca + Quản lý). Bốn luật chặn khi lưu, quan trọng nhất là "ca phải
  nằm trong giờ mở cửa" — sai kiểu này KHÔNG tự lộ, cấu hình lưu được nhưng bị
  cắt lúc đọc. Sai thì báo đủ mọi lỗi một lần, một lỗi một dòng.
- Xác minh trên CẢ prod lẫn staging bằng dữ liệu thật: 12/12 mốc giờ
  chặn/cho-qua đúng; lưới 50 khung 08:00→21:15; đổi giờ giả thì kết quả đổi
  theo (phân biệt "đọc từ DB" với "trùng mặc định").

**Kịch bản bấm thử cho quản lý (staging trước, prod đã giống hệt):**
1. Cài đặt → Luật đặt lịch → Giờ ca làm việc: sửa ca tối thành `17:30→23:00`,
   bấm Lưu → phải bị chặn, MỘT dòng "Mọi ngày mở cửa 07:00–22:00…".
2. Sửa ca chiều `12:00→17:30` → báo chồng ca sáng, có câu "KPI đếm đôi".
3. Sửa ca sáng `09:00→12:00`, Lưu → lưới đặt lịch bỏ các khung 08:00–08:45
   ngay (không cần F5). Thử xong TRẢ LẠI `08:00→13:00`.
4. Màn đặt lịch: không còn cột 13:00 (nghỉ trưa) và sau 21:15.
5. Lịch làm việc: xếp được ca **Tối** cho nhân viên.

**Việc sót lại của phiên (làm đầu phiên sau):**
- **Ghi sổ migration** — cả hai database áp `20260821000001` bằng psql tay,
  CHƯA ghi `supabase_migrations.schema_migrations` (staging còn thiếu cả
  `20260820000001` của #144). Lệnh:
  `INSERT INTO supabase_migrations.schema_migrations(version) VALUES ('20260821000001') ON CONFLICT DO NOTHING;`
- **PR #144 (lễ tân)** vẫn mở, chỉ ở staging (`staging-0820a`+), chờ quản lý
  duyệt; migration `20260820000001` của nó CHƯA áp prod — đúng, vì code chưa lên.
- Chip "siết cổng độ phủ": ngưỡng ghi 80 nhưng so sánh số ĐÃ LÀM TRÒN nên
  thực tế là 79,5. Đừng hạ số; viết thêm test vượt 80.00 rồi mới siết.
- HTTPS vẫn chưa có — toàn bộ chạy HTTP trần.

**Cạm bẫy mới trả giá phiên này:**
- `git fetch origin main && git tag X origin/main` gắn tag vào giá trị CŨ
  (chỉ `FETCH_HEAD` chắc chắn được cập nhật) → tag trỏ code cũ, CD deploy lại
  bản đang chạy, mọi thứ *trông như* đã lên. **Luôn tag vào SHA viết rõ**, và
  xác minh bằng cách hỏi CONTAINER có ký hiệu mới chưa, đừng tin nhãn CI xanh.
- `gh run list --workflow=cd.yml` hiện `headBranch=main` cho MỌI lần chạy, kể
  cả deploy tag staging → nhìn danh sách tưởng CD chưa từng chạy. Phải mở từng
  run xem JOB.
- Lệnh đưa cho người khác chạy phải trơ với ngữ cảnh: `git pull` trong
  worktree không upstream gãy im lặng giữa chuỗi `&&` (bước 2 của quy trình
  prod đã trượt kiểu này). Dùng `git show FETCH_HEAD:<file>` thay vì pull.
- Dòng giả trong test là `dict` thì có đủ khoá mình tự cho vào;
  `asyncpg.Record` thì KeyError. `capacity_service` đọc cột không SELECT, cả
  bộ test xanh, staging vỡ. Đã có `test_doc_dung_cot_da_chon.py` đối chiếu
  mọi khoá đọc với mọi cột SELECT.
- Phép đo phải PHÂN BIỆT được: giờ prod trùng giá trị mặc định nên "đọc từ
  DB" và "lùi về mặc định" cho cùng kết quả — phải thử bằng giờ giả khác hẳn.

---

## 0.2 Phiên 15/08/2026 (Tuyền) — 16 PR #112–#127 (nền gần)

**Đại tu giao diện xong cả 5 bước (0→4).** DESIGN.md là hiến pháp; nguyên tử
Button/Chip/NutInPhieu ở `components/ui/`; ratchet `[..px]` trần 102 (từ 474)
sống trong `px-tu-che-ratchet-boundary.test.mts` — vượt là CI đỏ, dọn được
thì phải hạ trần. Thanh cuộn ẩn tới khi rê vào vùng cuộn.

**Chuỗi lịch-bác-sĩ có kết thúc thật.** Xoá ca → lịch tương lai của ca ấy
HUỶ HẲN (mã `BAC_SI_DOI_LICH`, giữ vết `bac_si_da_go_id` cho câu "đổi từ
ai"); gán được bác sĩ là vết xoá, cảnh báo tắt; khung giờ trống thật để đặt
lại cùng khách + bác sĩ khác. Cơ chế "thêm lại ca thì lịch tự quay về" (#115)
đã GỠ theo quyết định của Tuyền — bia mộ kèm lý do trong
`test_khoi_phuc_lich_khi_xep_lai_ca.py`.

**Một bệnh nhân nhiều SĐT.** Bảng `patient_sdt_them` + cột gộp
`patient.sdt_tim_kiem` (trigger nuôi) — mọi đường tìm tra số nào cũng ra.
Nút "＋ Thêm số cho khách này" trong ô cảnh báo trùng (trùng SỐ lẫn trùng
TÊN — tên 3 ký tự là hỏi, không cần năm sinh); xoá số trong khối sửa hồ sơ.

**Telegram trọn bộ.** Bot `@chat_Tuyen_bot` ("Theo dõi Clinic"), token trong
`.env.prod` trên VPS; kênh: chat riêng Tuyền `8457103265` + nhóm
`-1003672911684` (MVP2: Clinic AI). Relay realtime (nghe pg_notify
`clinicai_changes`, trigger event_log CHỈ INSERT — nghe UPDATE là tự đánh
thức vô tận); 4 tin: lịch mới/huỷ/đổi/xoá ca; bot lệnh /trangthai /homnay
(chỉ trả lời kênh đã đăng ký, trả lời đúng nơi hỏi); Kuma cũng bắn cùng
kênh (4 monitor + Sao lưu đêm). KHÔNG SĐT khách nào qua Telegram — có test.
Đổi kênh: sửa `TELEGRAM_CHAT_ID` (danh sách phẩy) trong `.env.prod` rồi
`docker compose --env-file .env.prod -p clinicai_prod --profile notifications up -d notification-relay`.

**Cạm bẫy mới trả giá hôm nay:**
- PostgREST cache lược đồ — thêm bảng/FK mới thì `docker restart clinicai_rest`
  (đã ghi vào lệnh migration mẫu), không thì màn đỏ "Could not find a relationship".
- Migration prod là việc của người (classifier chặn agent ghi DB prod); thứ tự
  BẮT BUỘC: DB trước, code sau — CHECK chưa nới mà code ghi mã mới là 500.
- CI mypy chạy `src/` (không chỉ src/clinicai); tenant-scope audit đòi mọi câu
  ghi tự khoá clinic_id; drift-test audit_labels đòi nhãn Việt cho event mới.
- `gh pr merge` khi CI chưa xong sẽ trượt lặng lẽ — đợi `gh run watch` xong
  hẳn rồi mới merge + tag, không thì tag chỉa vào main cũ.

**Chờ quyết / việc treo:** dọn prod trước bàn giao
(`scripts/don-prod-truoc-ban-giao.sql` — Tuyền chạy tay); đổi mật khẩu chung
12345678 sau bàn giao; token bot đã đi qua khung chat — muốn kín thì /revoke
rồi thay trong .env.prod; nếu nhóm MVP2 thêm người ngoài thì tách kênh (tin
nghiệp vụ có tên khách + mã BN).

---

## 1. Hệ thống đang ở đâu

| | |
|---|---|
| Máy chủ | Vietnix VPS, `ssh clinic-vps` (222.255.215.219) |
| Prod | nhánh `main`, cổng 80, project `clinicai_prod` + database `clinicai_db` |
| Staging | cổng 8080, project `clinicai_staging` + database `clinicai_stg_db` |
| Migration mới nhất | `20260821000001_ba_ca_lam_viec` — đã áp cả hai (chưa ghi sổ, xem mục 0) |
| Cơ sở | **2**: Kim Ngưu (đang mở, 12 phòng, 40 nhân sự) và Hào Nam (`is_active=false`) |
| Dịch vụ khám | 5: PK · SK · NT · NK · HMVS |
| Danh mục chỉ định | 39 mục đang bật, 5 mục chưa gán phòng |
| Lịch làm việc | 2340 ô, đến **31/01/2027** (mẫu tuần 01–07/06 trải ra 26 tuần) |
| Tài khoản | 40, mật khẩu tất cả `12345678` |

**Prod KHÔNG còn rỗng.** Quang đã tự tạo 2 hồ sơ (`Lalaa`, `Nguyễn Thị Lan`) và
5 lịch hẹn ngày 07/08. Đừng coi prod là môi trường vứt đi được nữa.

Staging có 3 hồ sơ `ZZ…` (0 lượt / 1 lượt / 3 lượt) để thử màn danh sách.

## 2. Tài khoản

Dạng `<chức vụ><tên>@dr4women.vn`: `bacsithanh`, `bacsisieuamdat`,
`dieuduonghavu`, `letanthu`, `thukyvananh`, `manhinhphongcho`…

**Bốn tài khoản dùng chung còn lại** (`.local`) — vì bốn bộ phận này chưa có một
người thật nào trong danh sách nhân sự:

| tài khoản | bộ phận |
|---|---|
| `ql@dr4women.local` | Quản lý |
| `thungan@dr4women.local` | Thu ngân |
| `cskh@dr4women.local` | CSKH |
| `duocsi@dr4women.local` | Dược sĩ |

Có tên bốn người này thì tạo tài khoản riêng rồi chạy lại
`supabase/fixtures/xoa_tai_khoan_dung_chung.sql` — nó tự kiểm và tự xoá nốt.

**Đừng xoá `ql@` khi chưa có quản lý thật**: đó là vai DUY NHẤT tạo lại được tài
khoản cho người khác. Xoá xong thì không ai sửa được nữa.

Quản lý tự làm được ở `/settings/tai-khoan`: thêm tài khoản, **đổi tên đăng
nhập**, đặt lại mật khẩu, gỡ tài khoản.

## 3. Chờ Quang quyết

1. **Hào Nam** đang `is_active = false`. Cơ sở này đang mở hay chưa?
2. **Tên đầy đủ của BS Đào** — bác sĩ duy nhất còn tên tắt, nick vẫn là `bacsidao@`.
3. **Tên bốn người**: quản lý, thu ngân, CSKH, dược sĩ (xem mục 2).
4. **Hai tên trong bảng lịch làm việc chưa ghép được ai**: `Tiên` (trạm Máy
   ngoài) và `Trang A` (Lễ tân). Đang để `staff_id` NULL, giữ nguyên chữ trong
   bảng. Không đoán bừa — tên sai trong lịch trực thì không ai biết mà sửa.
5. **Mật khẩu `12345678`** hợp lý lúc chưa có bệnh nhân thật. Trước ngày nhận
   khách thì nên đổi: `./scripts/dat-lai-mat-khau.sh .env.prod 80 <mật khẩu>`.
6. **Lịch làm việc hết hạn 31/01/2027** — chạy lại
   `supabase/fixtures/lich_lam_viec_tuan_mau.sql` với `tu_ngay` mới.

## 4. Năm PR đang mở — KHÔNG phải đồ thừa

Đã đóng 5 PR có nội dung thật sự đã vào `main` theo đường khác (#7, #9, #12,
#13, #29). Năm cái còn lại đo lại rồi: **nội dung chưa có trong `main`**.

| PR | vì sao còn sống |
|---|---|
| **#43 Sentry** | `src/clinicai/core/sentry.py` CÓ trong `main` nhưng `sentry-sdk` **không có trong `pyproject.toml`**. Đã kiểm trong container prod: `ModuleNotFoundError: No module named 'sentry_sdk'`. Nghĩa là **hiện không có lỗi nào được báo về**, và log khởi động chỉ nói "SENTRY_DSN not set" nên nhìn qua tưởng cố ý tắt. Nên làm sớm nhất. |
| **#44 công cụ migration** | `scripts/apply-pending-migrations.sh` chưa có trong `main`. Hiện phải áp migration bằng tay qua `docker cp` + `psql`. |
| **#8 event_log actor** | `event_log` chưa có cột actor; "ai làm" đang chìm trong JSON, không truy vấn hay ràng buộc được. |
| **#10, #11 chọn phòng khám** | Màn cho bác sĩ làm hai nơi. Chưa cần (mới một phòng khám) nhưng không bị thay thế bởi gì cả. |

## 5. Chưa xây

- Sinh tài liệu / lưu trữ tệp: "Hồ sơ trả bệnh nhân", tệp đính kèm nhân sự.
- **208 dòng `event_log` chưa ai xử lý** — relay không chạy.
- `visit_gate_rule` chưa được thi hành ở đâu.
- ~~CD tắt~~ **CD ĐÃ CHẠY (21/08)**: runner `vps-clinicai` online. Tag `staging-*` → staging tự động; prod bấm `gh workflow run cd.yml`, chỉ khung 1h–4h (ngoài khung phải điền `ly_do_vuot_khung_gio`).

## 6. Cạm bẫy đã trả giá để biết

**Đo trên máy chủ, không đoán từ code.** Ba lỗi lớn nhất phiên này đều chỉ lộ ra
khi so prod với staging, hoặc khi mở màn hình ra nhìn:

- **`auth.uid()` bản rút gọn trong `bootstrap_plain_postgres.sql`** chỉ đọc
  `request.jwt.claim.sub`; PostgREST v12 chỉ đặt `request.jwt.claims`. Staging
  thừa hưởng bản rút gọn → mọi lượt đọc trả `[]` cho MỌI tài khoản, không lỗi,
  không cảnh báo. Đã sửa cho giống hệt bản thật.
- **`proxy.ts` gọi Supabase bằng địa chỉ trình duyệt.** Từ trong container, IP
  công cộng cổng 80 đi vòng được, cổng 8080 thì không → staging đá mọi request
  về `/login`, gõ đúng mật khẩu vẫn quay lại. **Prod đang đúng nhờ may**: một
  luật tường lửa là cả phòng khám mất đường vào. Đã sửa; nếu thấy chỗ nào khác
  còn dùng `NEXT_PUBLIC_SUPABASE_URL` phía máy chủ thì sửa nốt.
- **PostgREST giữ lược đồ trong bộ nhớ.** Migration mới không tự vào. Triệu
  chứng: `Could not find a relationship between 'appointment' and 'patient'` —
  số đếm vẫn ra nên trông như lỗi dữ liệu. `NOTIFY pgrst, 'reload schema'`.
  Đã thêm vào `dung-staging.sh`; **prod thì phải nhớ chạy tay sau mỗi migration
  có đổi bảng/khoá ngoại.**

**Khoá an toàn của script dọn từng vô dụng.** `don-du-lieu-thu.sh` có mẫu
`BN-2026-%` trong danh sách "dữ liệu thử", trong khi `_generate_patient_code()`
sinh đúng dạng `BN-<năm>-<6 số>` cho MỌI bệnh nhân thật. Khoá nhìn hồ sơ thật và
bảo "đây là đồ thử". Đã gỡ mẫu đó. **Không bao giờ thêm vào danh sách ấy một mẫu
mà chính ứng dụng sinh ra.**

**Test biên là bạn, không phải chướng ngại.** Phiên này chúng bắt tôi hai lần và
đúng cả hai: một lần chặn file mới với ra khoá service-role (ADR-0012), một lần
là chính nó siết quá chặt theo nguyên văn câu điều kiện. Đọc ý định của test rồi
mới quyết sửa test hay sửa code.

**Deploy chạy bằng docker của MÁY GÕ LỆNH.** Muốn lên VPS thì `ssh clinic-vps`
rồi chạy ở đó. `all healthy ✓` KHÔNG có nghĩa là tính năng chạy — `/health`
không chạm bảng của tính năng. Luôn gọi thẳng endpoint của nó, và mở màn hình ra
nhìn.

**Nhánh mọc từ nhánh cũ sẽ xung đột giả** sau khi PR gộp kiểu rebase (SHA đổi
hết). Chữa bằng `git rebase --onto origin/main <tip-cũ>`.

## 7. Bộ lệnh kiểm đầy đủ

```bash
poetry run ruff check src/ && poetry run ruff format --check src/
poetry run mypy src/
python3 scripts/tests/tenant-scope-audit.py --check
ANTHROPIC_API_KEY="" poetry run pytest src/tests/ -q -m "not db and not integration" \
  --cov=clinicai --cov-report=term --cov-fail-under=80
cd src/dashboard && npx tsc --noEmit && npx eslint . --max-warnings=0 \
  && npm run test:audit && npm run test:ops && npm run test:boundary && npx next build
```

Độ phủ đang **~79,8%** và cổng thực tế là 79,5 vì coverage so số đã làm tròn
(xem chip "siết cổng độ phủ"). Thêm code mới thì phải thêm test, đừng hạ ngưỡng.

## 8. Việc thường dùng

```bash
ssh clinic-vps 'cd ~/clinicai && git pull --ff-only origin main && \
  DEPLOY_EXPECTED_SHA=$(git rev-parse HEAD) ./scripts/deploy-backend.sh prod'
```

```bash
ssh clinic-vps 'cd ~/clinicai && CLINIC_ENV_FILE=.env.staging \
  docker compose --env-file .env.staging -p clinicai_staging up -d --build dashboard'
```

Áp migration (chưa có công cụ — xem PR #44):
```bash
scp supabase/migrations/<file>.sql clinic-vps:/tmp/m.sql && \
ssh clinic-vps 'docker cp /tmp/m.sql clinicai_db:/tmp/m.sql && \
  docker exec clinicai_db psql -q -v ON_ERROR_STOP=1 -U postgres -d postgres -f /tmp/m.sql'
```
Nhớ ghi vào sổ `supabase_migrations.schema_migrations`, và `NOTIFY pgrst,
'reload schema'` nếu có đổi bảng hoặc khoá ngoại.
