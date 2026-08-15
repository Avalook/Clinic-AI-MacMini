# CLAUDE.md — ClinicAI

Phần mềm quản lý phòng khám Dr4Women. **Chạy trên VPS Vietnix**, database Postgres
tự dựng trên chính máy đó. Spec: `docs/spec-clinic.md`. Luật: **`docs/SO-LUAT.md`**.

> Tên thư mục còn chữ "MacMini" là dấu vết lịch sử. Máy Mac **không còn chạy gì**
> của hệ thống từ 07/08/2026 — thứ duy nhất còn trỏ về Mac là bản sao lưu hằng
> đêm, và đó là chủ ý: bản sao phải nằm ở máy khác với thứ nó sao lưu.

## Kiến trúc

```
khách → Caddy (TLS) → dashboard (Next.js, chỉ giao diện)
                          ↓
                      api (FastAPI, mọi luật nghiệp vụ) → Postgres
                          ↓
      Uptime Kuma + Dozzle = theo dõi & log (chỉ mở trong máy)
```

- **Frontend chỉ là giao diện.** Mọi *quyết định* nằm ở FastAPI hoặc SQL. Frontend
  chỉ nói chuyện thẳng với Supabase cho **đăng nhập** và **tin thời gian thực**.
- **Mọi thứ chạy trong container, cấu hình qua biến môi trường** — không địa chỉ
  hay khoá viết cứng.
- Chi tiết "cái gì được phép ở frontend": `docs/SO-LUAT.md` Phần 3.

## Hai môi trường, hai thư mục, một kho mã

Trên VPS (`ssh clinic-vps`):

| | Thư mục | Đứng ở | Cổng |
|---|---|---|---|
| **prod** — đang đón bệnh nhân | `/home/clinicai/clinicai` | nhánh `main` | 80 |
| **staging** — chỗ để thử | `/home/clinicai/staging` | tag `staging-*` | 8080 |

Hai thư mục **dùng chung một kho `.git`** (git worktree): tách hẳn nguồn của hai
môi trường mà không nhân đôi dung lượng. Trước 13/08 cả hai dùng chung một thư
mục — một lần `git checkout` là đổi luôn nguồn của prod.

## Nhánh: chỉ có `main`

- **`main` là nhánh dài hạn DUY NHẤT.** Nhánh việc → PR → `main` → xoá nhánh.
- Nhánh việc sống tối đa **2 ngày**. Đây là luật về *kích thước một lần làm*.
- Tag `staging-<ngày><chữ>` đánh dấu bản đang chạy trên staging.
- **Vì sao không có nhánh dài thứ hai:** đã xảy ra hai lần. Lần đầu `main` tụt
  **63 commit** sau `staging`. Lần hai (02–13/08) một nhánh `codex/staging-…`
  sống 11 ngày, đi trước `main` **204 commit** và đi sau **122** — và 79 commit
  của prod chỉ nằm trên ổ đĩa VPS, không có bản sao ở đâu cả.

## Đưa code lên máy chủ

- **staging: tự động.** Đẩy tag `staging-*` → CI xanh → CD deploy ngay.
- **prod: người bấm.** Chạy tay workflow CD trên GitHub, và **chỉ trong khung
  1h–4h sáng giờ Việt Nam**. Ngoài khung thì bị từ chối, trừ khi điền lý do vượt
  cửa — lý do ấy được ghi vào log lần chạy.
- CD chạy trên **runner của VPS** (`runs-on: [self-hosted, vps]`).
- CI chạy mọi PR và mọi lần đẩy: ruff · mypy · pytest · máy kiểm phạm vi phòng
  khám · tsc · eslint · test frontend · dựng ảnh amd64 · migration chạy thật.

## Database — chỉ qua migration

- Lược đồ = `supabase/migrations/*.sql` (theo git). Áp bằng `supabase db push`.
- **Không bao giờ** sửa lược đồ bằng tay trên giao diện.
- **Không chạy migration trong lúc deploy** — đó là một bước riêng, có người xem.

## Lệnh hay dùng

```bash
ssh clinic-vps                                        # vào máy chủ
cd /home/clinicai/clinicai && ./scripts/deploy-backend.sh prod
cd /home/clinicai/staging  && ./scripts/deploy-backend.sh staging
docker compose --env-file .env.prod -p clinicai_prod ps
supabase db push
```

## Luật

- Bí mật chỉ nằm trong `.env.prod` / `.env.staging` (đã gitignore) và trong
  GitHub Actions secrets. **Không bao giờ trong code.**
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

## Đang làm dở

Đọc **`docs/DANG-LAM.md`** trước khi bắt tay — nó giữ trạng thái giữa các phiên.

Việc lớn nhất còn lại: **đưa nốt luật nghiệp vụ ra khỏi `src/dashboard`**. Hôm
13/08 còn **42/63** route giao diện chạm thẳng database. Con số ấy chỉ được phép
giảm.
