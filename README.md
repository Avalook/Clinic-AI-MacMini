# ClinicAI

Phần mềm quản lý phòng khám sản phụ khoa. Phòng khám đầu tiên: **Dr4Women**,
chạy thật tại **https://dr4women.io.vn** (một VPS, database tự dựng trên chính máy đó).

Hệ chạy trên một **workflow kernel**: mọi việc trong ngày là một `work_item`
sinh ra từ danh mục `node_definition` của phòng khám, có phụ thuộc và cổng chặn
giữa các bước. Nhân viên không thấy "kernel" — họ thấy bảng việc của mình, và
bảng đó biết ai làm được gì, khi nào.

Người (và agent) mới đọc theo thứ tự: `CLAUDE.md` → `docs/SO-LUAT.md` →
`docs/DANG-LAM.md` → `docs/GIAI-THICH-CODE.md`. Tài liệu trong `docs/legacy/`
tả hạ tầng đã chết (Mac mini, Vercel, Supabase cloud, staging) — đừng làm theo.

---

## Chạy thử trên máy dev trong 1 lệnh

```bash
scripts/dev-up.sh          # dựng cả stack local (Supabase tự dựng + api + dashboard) rồi tự kiểm
scripts/dev-up.sh --reset  # xoá sạch database THỬ rồi dựng lại
scripts/dev-up.sh --down   # dừng API + dashboard
```

Cần sẵn: **Docker Desktop**, **Python 3.12+ / Poetry**, **Node 20+**.

Xong sẽ in ra địa chỉ, tài khoản thử (`letan@`, `bs.a@`, `dd.sa@`, `thungan@`,
`ql@`… `@dr4women.local`) và mật khẩu thử. Các tài khoản này **chỉ dành cho máy dev**.

### Thử trọn một lượt khám

1. **Lễ tân** → *Hàng đợi tiếp nhận* → chọn người bệnh → **Bắt đầu xử lý** → **Hoàn tất**
2. **Điều dưỡng** → cùng màn → hoàn tất **Đo sinh hiệu**
3. **Bác sĩ** → *Bàn khám* → người bệnh vừa rồi **hết bị chặn** → **Bắt đầu khám**
4. **Bác sĩ** → *Chỉ định dịch vụ* → chọn vài dịch vụ → **Gửi chỉ định**
5. **Thu ngân** → *Bàn thu ngân* → thấy đúng những dịch vụ đó để thu tiền

Bước 3 là chỗ đáng nhìn: bác sĩ **không** khám được cho tới khi điều dưỡng xong,
và màn hình nói rõ **bước nào** đang chặn — không ai lập trình điều đó vào màn
hình, nó là cổng FS trong `node_dependency`.

---

## Kiến trúc

```
khách → Caddy (TLS) → dashboard (Next.js, CHỈ giao diện)
                          ↓
                      api (FastAPI) ── mọi luật nghiệp vụ ──→ Postgres
                          ↑                                     ↑
                      su-kien (worker sự kiện)     Supabase TỰ DỰNG (GoTrue · PostgREST · Realtime)
```

- **Frontend chỉ là UI.** Mọi luật nằm ở FastAPI hoặc SQL. Dashboard gọi Supabase
  (bộ tự dựng, `docker-compose.supabase.yml`) trực tiếp **chỉ** cho auth và realtime.
- **Backend chạy bằng chủ database** (`bypassrls = true`) → **RLS không bảo vệ
  backend**. Mọi câu lệnh phải tự lọc `clinic_id`. Có cổng CI cưỡng chế điều này
  (`scripts/tests/tenant-scope-audit.py`, ngưỡng 0).

### Kernel quy trình

| | |
|---|---|
| `node_definition` | danh mục bước việc của phòng khám |
| `node_dependency` | phụ thuộc FS/SS/FF/SF + cổng AND/OR/XOR |
| `work_item` | một việc thật của một lượt khám |
| `work_item_event` | nhật ký lệnh (create/start/complete/skip/cancel/reassign) |

Check-in sinh ra các bước xương sống bằng cách **đi ngược danh mục**, không phải
bằng danh sách cứng trong code — xem `supabase/migrations/20260731000003_*`.

Bảng việc của mỗi vai là **cùng một endpoint**, khác đúng một tham số:

```
GET /api/v1/work-items?workspace=bang_dieu_phoi      → lễ tân
GET /api/v1/work-items?workspace=khu_bac_si          → bác sĩ
GET /api/v1/work-items?workspace=thu_ngan_dong_luot  → thu ngân
```

---

## Kiểm thử

CI chạy **trên máy dev** (GitHub Actions không chạy — lỗi thanh toán từ 25/09/2026):

```bash
./scripts/ci-may.sh               # 5 job y hệt .github/workflows/ci.yml
./scripts/ci-may.sh --bao-github  # sau commit + push, cây sạch: gửi kết quả lên PR
bash scripts/restore-drill.sh     # chứng minh bản sao lưu khôi phục được
```

Hai cổng đáng chú ý, vì chúng **đỏ theo cả hai chiều**: `tenant-scope-audit.py`
(ngưỡng 0) và `service-role-boundary.test.mts` (ngưỡng 2) — một exemption không
còn cần đến cũng làm đỏ build, vì "một exemption thừa đọc như một lần review
không ai làm".

---

## Cơ sở dữ liệu

Schema **chỉ** nằm trong `supabase/migrations/*.sql`, áp bằng
`scripts/apply-pending-migrations.sh` (thử khô trước, `--apply` để áp thật; mỗi
migration áp cùng dòng ghi sổ trong một giao dịch). **Không** dùng
`supabase db push`, **không bao giờ** sửa tay lược đồ.

---

## Vận hành

Prod: VPS `clinic-vps-moi`, thư mục `/home/clinicai/clinicai`, nhánh `main`.
**Không có staging.** Deploy làm tay trên VPS: sao lưu → (có migration thì diễn
tập trên bản sao rồi áp) → `git checkout -B main origin/main` →
`./scripts/deploy-backend.sh prod`. Lệnh đầy đủ: `CLAUDE.md` mục "Lệnh hay dùng".

Bí mật chỉ nằm trong `.env.prod` trên VPS (đã gitignore). **Không bao giờ trong
code.** Mẫu: `.env.prod.example`.
