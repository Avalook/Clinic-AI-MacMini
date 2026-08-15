# ĐANG LÀM — đọc file này trước khi bắt tay

Cập nhật: **15/08/2026**, cuối phiên (mục 0 là mới nhất; các mục dưới là nền từ 07/08, đọc kèm).

File này giữ trạng thái đang dở của dự án. Nó tồn tại vì một phiên dài đọc lại
ngữ cảnh tốn nhiều hơn cả việc làm; cách chữa đã chốt với Quang là **chia thành
nhiều phiên ngắn, mỗi phiên một chủ đề**, và dùng file này thay cho việc cõng
lịch sử hội thoại.

> Bản trước của file này **chưa từng được commit** nên đã mất theo phiên. Từ giờ
> nó nằm trong git. Cuối mỗi phiên: cập nhật lại, nhất là mục "chờ Quang quyết"
> và "cạm bẫy".

---

## 0. Phiên 15/08/2026 (Tuyền) — 16 PR #112–#127, prod & staging đồng bộ

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
| Migration mới nhất | `20260807000008_go_co_so_trung_ten_phong_kham` — đã áp cả hai |
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
- CD (`cd.yml`) đang `disabled_manually` vì 0 runner. Không phải bug.

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

Độ phủ đang **80,3%** — sát ngưỡng 80. Thêm code mới thì phải thêm test, đừng hạ
ngưỡng.

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
