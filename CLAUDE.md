# CLAUDE.md — ClinicAI

Phần mềm quản lý phòng khám Dr4Women. **Chạy trên một VPS** (`clinic-vps-moi`,
222.255.214.133), tên miền **https://dr4women.io.vn**, database Postgres tự dựng
trên chính máy đó. Luật: **`docs/SO-LUAT.md`**.
Giải thích code từ A tới Z (từng file, từng hàm, kèm những bẫy đã cắn thật):
`docs/GIAI-THICH-CODE.md`. Kiểm toán gần nhất: `docs/KIEM-TOAN-HE-THONG-2709.md`.

**Tìm chỗ sửa — trước khi grep:** đọc `docs/BAN-DO-SUA.md` (muốn sửa gì → màn
hay file + hàm + test; việc dữ liệu thì làm trên màn), rồi tìm route trong
`docs/BAN-DO-CODE.md` (sinh bởi `scripts/ban-do-code.py`, CI canh không lệch).
Giao việc cho AI khác theo `docs/MAU-GIAO-VIEC.md`.

> Tên thư mục còn chữ "MacMini" là dấu vết lịch sử. Máy Mac **không chạy gì**
> của hệ thống — nó chỉ là chỗ **nhận bản sao lưu**, và đó là chủ ý: bản sao phải
> nằm ở máy khác với thứ nó sao lưu. Sao lưu đêm 02:15 trên VPS → Viettel CFS;
> Mac kéo về 0:30 và 6:30 (`~/Projects/ClinicAI-Backups/keo-ve.sh`). Kiểm nhanh:
> `cat ~/Projects/ClinicAI-Backups/TRANG-THAI.txt` phải "BÌNH THƯỜNG" (từng hỏng
> 12→27/09 vì script trỏ VPS cũ — đã sửa).
>
> **Đã chết, đừng dùng:** VPS cũ `clinic-vps` (222.255.215.219), staging cổng
> 8080 và `/home/clinicai/staging`, Vercel, Supabase cloud, Cloudflare Tunnel,
> Tailscale, Sentry, CD qua GitHub Actions, `supabase db push`. Tài liệu thời đó
> nằm trong `docs/legacy/` — chỉ để tra lịch sử.

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
  thực đi kênh CỦA MÌNH: Postgres `LISTEN/NOTIFY` → FastAPI SSE → `/api/events/stream`
  → `RealtimeRefresher` / `useNgheBang` (27/09: bỏ Supabase Realtime — nó hỏng vì
  Postgres từ chối `wal2json`).
- **Theo dõi lỗi:** kho lỗi `loi_nhom` + bộ canh gác `canh_bao` (mỗi phút, trong
  su-kien) + nhật ký vận hành — xem ở `/ops` tab "Lỗi & cảnh báo", "Nhật ký vận hành".
- **Mọi thứ chạy trong container, cấu hình qua biến môi trường** — không địa chỉ
  hay khoá viết cứng.
- Tệp kết quả (ảnh/video/PDF) nằm trên ổ Viettel CFS gắn vào VPS
  (`/mnt/viettel-cfs`).
- Chi tiết "cái gì được phép ở frontend": `docs/SO-LUAT.md` Phần 3.

## Môi trường: chỉ có prod

Trên VPS (`ssh clinic-vps-moi`):

| | Thư mục | Đứng ở | Cổng |
|---|---|---|---|
| **prod** — đang đón bệnh nhân | `/home/clinicai/clinicai` | nhánh `main` | 80/443 |

**Không có staging** (từ khi dựng lại trên VPS mới 16/09/2026). Thử trên máy dev:
`scripts/dev-up.sh` dựng cả stack local bằng chính `docker-compose.supabase.yml`.
Nghiệm thu giao diện làm trên local, rồi mới lên prod.

## Nhánh: chỉ có `main`

- **`main` là nhánh dài hạn DUY NHẤT.** Nhánh việc → PR → `main` → xoá nhánh.
- Nhánh việc sống tối đa **2 ngày**. Đây là luật về *kích thước một lần làm*.
- **Vì sao không có nhánh dài thứ hai:** đã xảy ra hai lần. Lần đầu `main` tụt
  **63 commit** sau `staging`. Lần hai (02–13/08) một nhánh `codex/staging-…`
  sống 11 ngày, đi trước `main` **204 commit** và đi sau **122** — và 79 commit
  của prod chỉ nằm trên ổ đĩa VPS, không có bản sao ở đâu cả.

## Đưa code lên máy chủ

- **CI chạy trên máy dev**, không trên GitHub (GitHub Actions hỏng thanh toán từ
  25/09/2026): `./scripts/ci-may.sh --bao-github` — sau khi commit + push, cây
  sạch. Nó chạy y hệt `ci.yml`: ruff · mypy · pytest · máy kiểm phạm vi phòng
  khám · tsc · eslint · test frontend · migration chạy thật (`--anh` để dựng
  thêm ảnh amd64). **Xanh mới được merge, xanh mới được deploy.**
- **Không có CD tự động.** Runner của VPS cũ đã chết; `cd.yml` không chạy.
- **Deploy prod = làm tay trên VPS**, theo đúng thứ tự:
  1. Sao lưu database (lệnh ở mục "Lệnh hay dùng").
  2. Có migration mới → **diễn tập trước** trên bản sao (khôi phục bản sao lưu
     vừa tạo vào một database phụ, áp thử ở đó), rồi mới áp thật.
  3. `git fetch origin && git checkout -B main origin/main`
  4. `./scripts/deploy-backend.sh prod` (đòi đứng trên nhánh `main`, không detached).
  5. Kiểm: log api 0 lỗi, `/health/su-kien` ok, 0 sự kiện kẹt.
- Deploy dựng lại container nên người đang dùng thấy 502 khoảng một phút. Khung
  giờ deploy (giữ 1h–4h hay cho deploy ngày) đang chờ Tuyền chốt — kiểm toán
  27/09 mục 6, câu 7.

## Database — chỉ qua migration

- Lược đồ = `supabase/migrations/*.sql` (theo git). Áp bằng
  **`scripts/apply-pending-migrations.sh`** — nó so thư mục với sổ ghi và áp mỗi
  migration cùng dòng ghi sổ trong một giao dịch. **Không dùng `supabase db push`.**
- Áp xong: `NOTIFY pgrst, 'reload schema'` để PostgREST thấy cột/bảng mới.
- **Không bao giờ** sửa lược đồ bằng tay.
- **Không chạy migration trong lúc deploy** — đó là một bước riêng, có người xem.

## Lệnh hay dùng

```bash
ssh clinic-vps-moi                                    # vào máy chủ
cd /home/clinicai/clinicai

# sao lưu — PHẢI kèm env như unit systemd; chạy trần thì thoát 1 im lặng
PG_DUMP_BIN=scripts/pg-dump-qua-container.sh CLINIC_DB_CONTAINER=clinicai_db \
  BACKUP_ENV_FILE=.env.prod CLINIC_BACKUP_DIR=/home/clinicai/backups/clinicai \
  ./scripts/backup-db.sh

CLINIC_DB_CONTAINER=clinicai_db ./scripts/apply-pending-migrations.sh          # thử khô
CLINIC_DB_CONTAINER=clinicai_db ./scripts/apply-pending-migrations.sh --apply  # áp thật
docker exec clinicai_db psql -U postgres -c "NOTIFY pgrst, 'reload schema'"

./scripts/deploy-backend.sh prod
CLINIC_ENV_FILE="$PWD/.env.prod" docker compose --env-file .env.prod -p clinicai_prod ps
```

## Luật

- Bí mật chỉ nằm trong `.env.prod` trên VPS (đã gitignore). **Không bao giờ
  trong code**, không bao giờ dán vào khung chat.
- Router mỏng; luật nghiệp vụ nằm trong hàm dịch vụ (Python thuần, test được).
  **Không luật nghiệp vụ nào trong TSX.**
- Giao diện: mọi thay đổi kích thước/màu/bo góc lấy từ thang trong **`DESIGN.md`**
  (hiến pháp giao diện, chốt 15/08/2026). "To ra" = nhích một bậc thang, và
  nghiệm thu ở đủ ba cỡ màn 375/768/1280.
- Mọi bất biến có kẽ hở tranh chấp phải ép ở Postgres, không tự cài khoá trong
  Python. Xem `docs/SO-LUAT.md` Phần 6.
- Hàm nhận ngày/giờ từ người dùng phải **trả giá trị rỗng thay vì ném**, và phải
  có test cho đầu vào rác. Đã có ba lần 500 vì luật này bị bỏ qua.
- Trước khi đề xuất hạ tầng mới (Redis, message broker, máy tìm kiếm, thêm bản
  sao ứng dụng): **đọc `docs/SO-LUAT.md` Phần 7**. Nó ghi thứ đã cân nhắc và
  loại **ở quy mô này (~1 lượt gọi/giây, một người vận hành)**, kèm ngưỡng đo
  được để mở lại. Đừng đề xuất lại từ best-practice chung.

## Sửa giao diện — quy trình bắt buộc (Tuyền chốt 18/09/2026)

Vì sao có mục này: các lần sửa giao diện trước hay **sửa nhầm bản cũ** hoặc
**sửa một lối, sót lối khác**. Ví dụ có thật ngày 17/09: nút QR được gỡ ở màn
thu ngân cũ (`/tasks`), trong khi màn đang dùng là `/thu-ngan/*`.

1. **Trước khi sửa, tra `docs/SITEMAP.md`.** Mục A cho biết route nào là màn
   chuẩn. Mục B liệt kê mọi lối vào của cùng một chức năng. Phải sửa **đủ mọi
   lối** trong hàng đó, hoặc ghi rõ lối nào cố ý bỏ và vì sao. Không có trong
   bảng thì grep theo **component và API**, không grep theo tên màn.
2. **Không sửa màn đã đánh dấu GỘP hay ĐÃ CHUYỂN HƯỚNG.** Sửa ở màn chuẩn.
3. **Không tự chế giao diện.**
   - Màu, cỡ và bo góc lấy từ `DESIGN.md` và token trong `globals.css`.
   - Nút và thành phần lấy từ `src/dashboard/components/ui`. Thiếu thì thêm vào
     đó trước, rồi mới dùng.
   - Không viết hex, px tự chế hay `style={{}}` mới.
   - Không thêm `window.confirm` mới.
   - `<button>` luôn có `type=`.
4. **Thêm, xoá hay đổi một route, một mục thanh bên, hoặc quyền trong
   `NAV_ROLES`:** sửa `docs/SITEMAP.md` trong **cùng commit**.
5. **Báo cáo sau khi sửa phải có bảng "nút/link đã đụng"**, gồm: màn → nút →
   đi đâu hoặc gọi API nào → vai nào thấy.
6. **Chưa bấm thật thì không báo "xong".** Ghi rõ đã kiểm ở lớp nào:
   - test;
   - API;
   - bấm trên trình duyệt, ở cỡ 375 và 1280.

   Kiểm bằng API không chứng minh được giao diện.

## Đang làm dở

Đọc **`docs/DANG-LAM.md`** trước khi bắt tay — nó giữ trạng thái giữa các phiên.
Các quyết định còn chờ chốt: `docs/KIEM-TOAN-HE-THONG-2709.md` mục 6.

Việc lớn còn lại: **đưa nốt luật nghiệp vụ ra khỏi `src/dashboard`**. Route Next
chạm thẳng database: **2** (27/09/2026; 13/08 là 42/63) — con số ấy **chỉ được
giảm**. Còn khoảng 123 chỗ `if` theo vai trong TSX.
