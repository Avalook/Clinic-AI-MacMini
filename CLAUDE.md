# CLAUDE.md — ClinicAI

Phần mềm quản lý phòng khám Dr4Women. **Chạy trên một VPS** (`clinic-vps-moi`,
222.255.214.133), tên miền **https://dr4women.io.vn**, database Postgres tự dựng
trên chính máy đó. Luật: **`docs/SO-LUAT.md`**.
Giải thích code từ A tới Z (từng file, từng hàm, kèm những bẫy đã cắn thật):
`docs/GIAI-THICH-CODE.md`. Kiểm toán gần nhất: `docs/KIEM-TOAN-HE-THONG-2709.md`.

**Tìm chỗ sửa — trước khi grep:** đọc `docs/BAN-DO-SUA.md` (muốn sửa gì → màn
hay file + hàm + test; việc dữ liệu thì làm trên màn), rồi tìm route trong
`docs/BAN-DO-CODE.md` (sinh bởi `scripts/ban-do-code.py`, CI canh không lệch).
Việc chạm nhiều tầng → giao agent `tim-cho-sua` (chỉ đọc, trả danh sách điểm sửa).
Giao việc cho AI khác theo `docs/MAU-GIAO-VIEC.md`.

## QUY TRÌNH LÀM VIỆC CHUẨN — mọi phiên, mọi AI làm theo (Tuyền chốt 01/10/2026)

Đây là cách nhanh nhất, ít tốn thời gian nhất Tuyền chọn. Không tự đổi.

1. **Nhận việc → tra `docs/BAN-DO-SUA.md`.** Việc DỮ LIỆU (giá, phòng, lịch,
   dây nối, quyền…) → chỉ Tuyền tự làm trên màn, không code. Việc CODE → giao theo
   `docs/MAU-GIAO-VIEC.md` (việc · ở đâu · kết quả cần đạt · cách kiểm · không đụng).
2. **Nhiều việc làm SONG SONG:** mỗi việc một agent · một worktree · một nhánh ·
   một PR. Mỗi việc một dải giờ migration riêng và cổng web/API riêng (32xx/82xx)
   để không đè nhau. Giữ phạm vi; đụng chung file thì sửa tối thiểu.
3. **CODE TRƯỚC, TEST SAU — dùng chung, không dựng riêng:**
   - pytest: DB chung `chung_test_db` (`postgresql://postgres:postgres@127.0.0.1:55600/postgres`),
     áp migration của nhánh bằng `CLINIC_DB_CONTAINER=chung_test_db ./scripts/apply-pending-migrations.sh --apply`.
     Không tự dựng container DB, không reset DB chung.
   - bấm thật: stack local chung (`clinicai_thu_db`, khách `DEMO-*`, tài khoản
     `@dr4women.local`), API/web CỦA NHÁNH chạy ở cổng riêng trỏ vào đó.
   - CI cuối: `./scripts/ci-may.sh --bao-github` (có khoá xếp hàng — chạy lần lượt).
4. **Một PR được coi là xong khi:** CI xanh · đã bấm thật local ở 375 và 1280 ·
   có **kịch bản bấm thử cho người thật** trong thân PR · có bảng "nút/link đã đụng".
5. **GOM ĐỢT LÊN STAGING** (https://staging.dr4women.io.vn, dữ liệu khách đã che,
   đăng nhập tài khoản prod): các PR đã xanh lên cùng một đợt
   (`scripts/len-staging.sh` khi có; tạm thời `scripts/deploy-staging.sh <nhánh đợt>`
   + áp migration lên DB staging). Người thật bấm theo kịch bản.
6. **ĐẠT → merge cả đợt → deploy prod MỘT lần**, ghim đúng SHA đã thử trên staging
   (`scripts/len-prod.sh` khi có; tạm thời quy trình sao lưu → diễn tập migration →
   áp → deploy ở skill `len-prod`). Việc nào lỗi thì tách ra sửa, không
   giữ cả đợt. Lệnh ghi lên VPS (merge, deploy) do Tuyền chạy; AI soạn sẵn lệnh.
7. **Không bao giờ:** đẩy thẳng `main` · lên prod khi chưa qua staging (trừ sửa
   khẩn — ghi lý do trong PR) · mở đường hầm (cloudflared…) từ Mac khi DB local là
   bản sao prod · để thao tác nào **khoá cứng**: mọi thao tác nhân viên bấm phải
   **hoàn tác được** và cập nhật ngay ở mọi màn liên quan (Tuyền 01/10, sau buổi
   thực nghiệm thật).
8. **Tài nguyên:** Docker local (Colima) 8 CPU / 16 GB / 100 GB; container thử dùng
   xong phải xoá; không chạy CI theo cách khác `ci-may.sh`; VPS chỉ đọc khi làm việc.

## MỨC VIỆC — làm nhanh mà không ẩu (Tuyền chốt 06/10/2026)

Bổ sung cho QUY TRÌNH ở trên (không thay chữ nào của nó). **Dòng đầu câu trả lời
khi nhận việc: "Mức N · ước ~X phút".** Sai mức thì Tuyền nói ngay.

| Mức | Gồm | Cách làm | Ước |
|---|---|---|---|
| **0** hỏi/tra/giải thích | "chỗ này làm gì", "vì sao lỗi" | trả lời ngay, không đụng code | 1–3′ |
| **1** nhỏ, ít rủi ro | docs, comment, test, script dev, sửa chữ | sửa → kiểm tại chỗ (hook ruff/LSP + đúng test liên quan) → **gom việc cùng loại vào MỘT PR, MỘT lượt CI**; không bấm trình duyệt nếu không đụng giao diện | 5–10′ |
| **2** đổi hành vi | logic backend, màn hình | `tim-cho-sua` → sửa → test liên quan → bấm thật 375/1280 nếu đụng giao diện → CI một lần → PR có kịch bản bấm thử | 20–60′ |
| **3** rủi ro cao | migration, quyền, tiền, dữ liệu prod, hạ tầng | **kế hoạch ngắn cho Tuyền duyệt TRƯỚC** → làm → diễn tập → staging | theo kế hoạch |

- **PR CHỈ docs thì KHÔNG chạy CI máy** — chỉ tệp `.md` (docs/, CLAUDE.md,
  `.claude/rules|skills|agents/*.md`), trừ `docs/BAN-DO-CODE.md` (tệp sinh — sửa nó
  là đổi code/route, phải CI). Có tệp nào khác `.md` → theo mức của tệp đó.
- **Kiểm nhanh khi đang làm, CI đầy đủ một lần ở cuối** — không chạy `ci-may.sh` giữa chừng.
- **Chỉ hỏi khi cần Tuyền quyết nghiệp vụ**; chọn lựa kỹ thuật thì tự chọn, báo lý do một dòng.
- **Việc độc lập chạy song song bằng agent nền**, báo trước giờ xong dự kiến.
- **Báo cáo một khuôn:** kết quả trước · một bảng · cuối là việc Tuyền làm (lệnh bấm được).

> Máy Mac **không chạy prod** (chữ "MacMini" trong tên thư mục là dấu vết lịch sử).
> Nó là máy dev — stack thử (`scripts/dev-up.sh`), staging local từ bản sao lưu
> (`scripts/staging-tu-ban-sao.sh`), CI (`scripts/ci-may.sh`) — và là chỗ **nhận
> bản sao lưu** (chi tiết + cách kiểm: skill `len-prod`).
>
> **Đã chết, đừng dùng:** VPS cũ `clinic-vps` (222.255.215.219), VPS Vietnix,
> staging cổng 8080 và `/home/clinicai/staging`, Vercel, Supabase cloud,
> Supabase Realtime (`postgres_changes`/publication — thay bằng LISTEN/NOTIFY),
> Cloudflare Tunnel, Tailscale, Sentry, CD qua GitHub Actions (`cd.yml` đã gỡ),
> `supabase db push`. Tài liệu thời đó nằm trong `docs/legacy/` — chỉ để tra lịch sử.

## Kiến trúc

```
khách → Caddy (TLS Let's Encrypt) → dashboard (Next.js, chỉ giao diện)
             │                          ↓
             │                      api (FastAPI, mọi luật nghiệp vụ) → Postgres
             │                          ↑                                  ↑
             │                      su-kien (worker sự kiện)               │
             └─ /auth/v1 /rest/v1 /realtime/v1 → Supabase tự dựng ─────────┘
                                    (GoTrue · PostgREST · Realtime, docker-compose.supabase.yml)

      Uptime Kuma + Dozzle = theo dõi & log (chỉ nghe 127.0.0.1, vào bằng ssh -L)
```

- **Frontend chỉ là giao diện.** Mọi *quyết định* nằm ở FastAPI hoặc SQL. Frontend
  chỉ nói chuyện thẳng với Supabase (bộ tự dựng) cho **đăng nhập**. Tin thời gian
  thực đi kênh CỦA MÌNH: trigger `notify_row_change` → `pg_notify` → FastAPI SSE
  `/api/events/stream` → `RealtimeRefresher` / `useNgheBang`.
- **Theo dõi lỗi:** kho lỗi `loi_nhom` + bộ canh gác `canh_bao` (mỗi phút, trong
  su-kien) + nhật ký vận hành — xem ở `/ops` tab "Lỗi & cảnh báo", "Nhật ký vận hành".
- Lịch trên VPS đều là systemd timer (không crontab), unit trong `scripts/systemd/`;
  `clinicai-traffic-report` (nuôi `/traffic`) nằm **ngoài git** (công cụ lạ cài 30/09), chờ chốt.
- **Mọi thứ chạy trong container, cấu hình qua biến môi trường** — không địa chỉ
  hay khoá viết cứng. Tệp kết quả (ảnh/video/PDF) nằm trên ổ Viettel CFS gắn vào
  VPS (`/mnt/viettel-cfs`).

## Môi trường

| | Ở đâu | Dữ liệu |
|---|---|---|
| **prod** — đang đón bệnh nhân | VPS `/home/clinicai/clinicai`, nhánh `main`, cổng 80/443 | thật |
| **staging** | cùng VPS, `/home/clinicai/clinicai-staging`, https://staging.dr4women.io.vn, Supabase/DB/khoá/mạng **riêng**, nạp lại bản sao prod mỗi đêm 03:30 — `docs/STAGING.md` | bản sao prod **đã che** thông tin khách |
| **staging local** | Mac, `scripts/staging-tu-ban-sao.sh` (nạp bản sao lưu đêm, đăng nhập bằng tài khoản prod) | bản sao prod **chưa che** — cấm mở đường hầm ra ngoài |
| **dev local** | Mac, `scripts/dev-up.sh` (cả stack bằng chính `docker-compose.supabase.yml`) | thử |

## Nhánh, CI, deploy, database

- **`main` là nhánh dài hạn DUY NHẤT.** Nhánh việc → PR → `main` → xoá nhánh; sống
  tối đa **2 ngày** (luật về *kích thước một lần làm* — hai lần có nhánh dài thứ hai
  thì `main` tụt 63 rồi 204 commit, 79 commit prod chỉ còn trên ổ VPS).
- **CI chạy trên máy dev:** `./scripts/ci-may.sh --bao-github`. Xanh mới merge, xanh
  mới deploy. **Không có CD.** Deploy prod làm tay, ghim SHA đã soát — skill `len-prod`.
- **Database chỉ qua migration** (`supabase/migrations/`, áp bằng
  `scripts/apply-pending-migrations.sh`, không `supabase db push`, không sửa tay,
  không áp trong lúc deploy). Chi tiết: `.claude/rules/migration.md`.

## Luật

- Bí mật chỉ nằm trong `.env.prod` trên VPS (đã gitignore). **Không bao giờ
  trong code**, không bao giờ dán vào khung chat.
- Router mỏng; luật nghiệp vụ nằm trong hàm dịch vụ (Python thuần, test được).
  **Không luật nghiệp vụ nào trong TSX.**
- Mọi bất biến có kẽ hở tranh chấp phải ép ở Postgres (`docs/SO-LUAT.md` Phần 6).
- Hàm nhận ngày/giờ từ người dùng phải **trả giá trị rỗng thay vì ném**, và phải
  có test cho đầu vào rác. Đã có ba lần 500 vì luật này bị bỏ qua.
- Trước khi đề xuất hạ tầng mới (Redis, message broker, máy tìm kiếm, thêm bản
  sao ứng dụng): **đọc `docs/SO-LUAT.md` Phần 7**. Nó ghi thứ đã cân nhắc và
  loại **ở quy mô này (~1 lượt gọi/giây, một người vận hành)**, kèm ngưỡng đo
  được để mở lại. Đừng đề xuất lại từ best-practice chung.
- Luật riêng từng vùng tự nạp khi Claude đọc/sửa file trong vùng đó
  (`.claude/rules/`): **giao diện** `src/dashboard/**` (tra SITEMAP trước, sửa đủ
  mọi lối, bấm thật 375/1280) · **backend** `src/clinicai/**` · **migration**.

## Cách làm việc với code (harness, 06/10/2026)

- **Đọc/sửa file nguồn bằng tool Read/Edit/Write, không `cat`/`sed` qua Bash** — luật
  theo vùng ở `.claude/rules/` và chẩn đoán LSP chỉ chạy khi dùng các tool đó.
- **LSP** (plugin `pyright-lsp`, `typescript-lsp`): chẩn đoán về **trễ một nhịp** —
  khối `<new-diagnostics>` gắn vào lượt tool KẾ TIẾP sau Edit, không vào kết quả Edit.
  Sửa xong thì làm thêm ít nhất một bước (Read lại file) trước khi báo xong; có lỗi
  thì sửa trước khi đi tiếp. Tìm định nghĩa/chỗ gọi bằng tool `LSP` thay vì grep chữ.
  Cấu hình pyright: `pyrightconfig.json` (nhìn thư viện không kiểu giống mypy).
- **Hook sau khi sửa** (`.claude/hooks/kiem-sau-sua.sh`): chạy đúng bản ruff của CI
  trên file `.py` vừa sửa; báo lỗi thì sửa ngay.
- **Comment:** giữ comment nói *vì sao* / *bẫy đã cắn*; comment chỉ kể *đổi lúc nào*
  thì đưa vào commit message. Đụng file nào, gọt comment lịch sử lỗi thời của file đó.
- **PR nhỏ:** quá ~400 dòng (không tính test, migration, tệp sinh) thì tách.

## Đang làm dở

Đọc **`docs/DANG-LAM.md`** trước khi bắt tay — nó giữ trạng thái giữa các phiên.
Các quyết định còn chờ chốt: `docs/KIEM-TOAN-HE-THONG-2709.md` mục 6.

Việc lớn còn lại: **đưa nốt luật nghiệp vụ ra khỏi `src/dashboard`**. Route Next
chạm thẳng database: **1** (06/10/2026 — chỉ còn `check-phone`, đã tắt; 27/09 là 2,
13/08 là 42/63) — con số ấy **chỉ được giảm**. Còn khoảng 123 chỗ `if` theo vai trong TSX.
