# ClinicAI

Phần mềm quản lý phòng khám sản phụ khoa. Phòng khám đầu tiên: **Dr4Women**.

Hệ chạy trên một **workflow kernel**: mọi việc trong ngày là một `work_item`
sinh ra từ danh mục `node_definition` của phòng khám, có phụ thuộc và cổng chặn
giữa các bước. Nhân viên không thấy "kernel" — họ thấy bảng việc của mình, và
bảng đó biết ai làm được gì, khi nào.

---

## Chạy thử trong 1 lệnh

```bash
scripts/dev-up.sh          # dựng cả stack rồi tự kiểm
scripts/dev-up.sh --reset  # xoá sạch database local rồi dựng lại
scripts/dev-up.sh --down   # dừng API + dashboard
```

Cần sẵn: **Docker Desktop**, **Python 3.12+ / Poetry**, **Node 20+**.

Xong sẽ in ra địa chỉ và tài khoản. Mật khẩu chung `clinic-test-pw-123`:

| Tài khoản | Vai | Vào được |
|---|---|---|
| `letan@dr4women.local` | Lễ tân | Hàng đợi tiếp nhận, Bàn thu ngân (đóng lượt) |
| `bs.a@dr4women.local` | Bác sĩ | Bàn khám, Chỉ định dịch vụ |
| `dd.sa@dr4women.local` | Điều dưỡng SA | Hàng đợi tiếp nhận (sinh hiệu) |
| `thungan@dr4women.local` | Thu ngân | Bàn thu ngân |
| `ql@dr4women.local` | Quản lý | Sức khoẻ API, Vận hành |

### Thử trọn một lượt khám

1. **Lễ tân** → *Hàng đợi tiếp nhận* → chọn người bệnh → **Bắt đầu xử lý** → **Hoàn tất**
2. **Điều dưỡng** → cùng màn → hoàn tất **Đo sinh hiệu**
3. **Bác sĩ** → *Bàn khám* → người bệnh vừa rồi **hết bị chặn** → **Bắt đầu khám**
4. **Bác sĩ** → *Chỉ định dịch vụ* → chọn vài dịch vụ → **Gửi chỉ định**
5. **Thu ngân** → *Bàn thu ngân* → thấy đúng những dịch vụ đó để đối soát

Bước 3 là chỗ đáng nhìn: bác sĩ **không** khám được cho tới khi điều dưỡng xong,
và màn hình nói rõ **bước nào** đang chặn — không ai lập trình điều đó vào màn
hình, nó là cổng FS trong `node_dependency`.

---

## Kiến trúc

```
client → Caddy → dashboard (Next.js 16, CHỈ giao diện)
                     ↓
                 api (FastAPI) ── mọi luật nghiệp vụ ──→ Supabase (Postgres)
                     ↑
                 worker ← RabbitMQ (tuỳ chọn)
```

- **Frontend chỉ là UI.** Mọi luật nằm ở FastAPI hoặc SQL. Dashboard gọi Supabase
  trực tiếp **chỉ** cho auth và realtime.
- **Backend chạy bằng chủ database** (`bypassrls = true`) → **RLS không bảo vệ
  backend**. Mọi câu lệnh phải tự lọc `clinic_id`. Có gate CI cưỡng chế điều này
  (`scripts/tests/tenant-scope-audit.py`, ngưỡng 0).

### Kernel quy trình

| | |
|---|---|
| `node_definition` | danh mục bước việc của phòng khám (37 node) |
| `node_dependency` | phụ thuộc FS/SS/FF/SF + cổng AND/OR/XOR |
| `work_item` | một việc thật của một lượt khám |
| `work_item_event` | nhật ký lệnh (create/start/complete/skip/cancel/reassign) |

Check-in sinh ra 7 bước xương sống bằng cách **đi ngược danh mục**, không phải
bằng danh sách cứng trong code — xem `supabase/migrations/20260731000003_*`.

Bảng việc của mỗi vai là **cùng một endpoint**, khác đúng một tham số:

```
GET /api/v1/work-items?workspace=bang_dieu_phoi      → lễ tân
GET /api/v1/work-items?workspace=khu_bac_si          → bác sĩ
GET /api/v1/work-items?workspace=thu_ngan_dong_luot  → thu ngân
```

---

## Kiểm thử

```bash
poetry run pytest src/tests/ -q -m "not db and not integration"   # 731 test
python3 scripts/tests/tenant-scope-audit.py --check               # ngưỡng 0
bash scripts/tests/e2e-booking-local.sh                           # 20 assertion
bash scripts/restore-drill.sh                                     # khôi phục backup thật
```

Hai cổng đáng chú ý, vì chúng **đỏ theo cả hai chiều**: `tenant-scope-audit.py`
(ngưỡng 0) và `service-role-boundary.test.mts` (ngưỡng 2) — một exemption không
còn cần đến cũng làm đỏ build, vì "một exemption thừa đọc như một lần review
không ai làm".

---

## Cơ sở dữ liệu

Schema **chỉ** nằm trong `supabase/migrations/*.sql`, áp bằng `supabase db push`.
**Không bao giờ** sửa tay trên dashboard Supabase.

> **Production hiện KHÔNG cùng dòng migration với repo này** và `db push` sẽ
> hỏng giữa chừng. Đọc `docs/prod-cutover-findings.md` trước khi làm gì với
> production.

---

## Trạng thái thật

**Chạy được end-to-end ở local**: tiếp nhận → sinh hiệu → khám → chỉ định →
phòng thực hiện → đối soát.

**Chưa xong, và biết rõ là chưa:**

| | |
|---|---|
| Bảng giá | **trống hoàn toàn** — chưa thu tiền được. Màn thu ngân nói rõ điều này thay vì hiện 0đ |
| Production | đang chạy repo cũ, schema cũ — xem `docs/prod-cutover-findings.md` |
| Backup production | **chưa khôi phục được** cho tới khi áp `supabase/hotfix/20260801_prod_f_unaccent_qualify.sql` |
| `staff_task` | vẫn chạy song song với `work_item`; chưa gỡ |
| Pháp lý | chưa có consent, mã ICD, chữ ký số (TT13) |

Tài liệu: `docs/design-catalogue.md` (44 màn thiết kế),
`docs/prod-cutover-findings.md` (chẩn đoán production + 3 phương án).

---

## Vận hành

```bash
./scripts/deploy-backend.sh prod          # hoặc staging
bash scripts/backup-db.sh                 # backup có ghi rõ database nguồn
bash scripts/restore-drill.sh             # chứng minh backup khôi phục được
bash scripts/rehearse-data-migration.sh   # diễn tập chuyển dữ liệu (không chạm prod)
```

Bí mật chỉ nằm trong `.env.prod` / `.env.staging` (đã gitignore) và GitHub
Actions secrets. **Không bao giờ trong code.**
