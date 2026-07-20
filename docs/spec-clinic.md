# SPEC: Chuyển ClinicAI sang self-host hoàn toàn trên Mac mini (bỏ Vercel)

*Spec này để đưa cho Claude Code thực thi. Người duyệt: Avalook. Nguồn sự thật: `SYSTEM_STATE_ACTUAL.md`, `CURRENT_PROGRESS.md`.*

---

## 1. Mục tiêu

Chuyển từ **(Vercel frontend + Supabase + Mac backend)** sang **mọi thứ app tự chạy trên Mac mini bằng Docker + Supabase giữ dữ liệu**. Yêu cầu:
- Bỏ hẳn Vercel; Mac mini phục vụ cả frontend lẫn backend.
- Tách bạch frontend/backend: **frontend chỉ là giao diện; mọi logic ở backend**.
- CI/CD chạy trên Mac; deploy có kiểm thử gác.
- Có **dashboard theo dõi hệ thống + log đọc được**.
- **Đóng gói Docker** để sau bê lên VPS là "lift-and-shift", không viết lại.
- Chạy 24/7, tự phục hồi.

**Nguyên tắc bao trùm:** giữ dữ liệu ở Supabase → Mac chết chỉ là *tạm không truy cập*, KHÔNG mất dữ liệu. Đây là ràng buộc an toàn, không được phá.

---

## 2. Hiện trạng (theo mô tả của Avalook — Claude Code khảo sát code thật để xác nhận)

- 1 repo, **2 nhánh**: 1 nhánh → domain khách dùng thử thật (prod), 1 nhánh → domain team nội bộ xem (staging/preview). Merge staging → prod khi chắc chắn.
- **2 Supabase project riêng**, mỗi cái trỏ 1 domain.
- Mac mini M4 Pro 48GB đang chạy full app 24/7 qua Tailscale; Vercel đang phục vụ frontend khách.
- Backend: FastAPI + LangGraph + RabbitMQ. Frontend: Next.js. Đã có Docker trong repo.

> **Task 0 cho Claude Code:** khảo sát repo thật, xác nhận/điều chỉnh phần hiện trạng trên, và liệt kê chính xác các service đang có + cách chúng nối nhau. Không tin mô tả, kiểm code.

---

## 3. Kiến trúc đích

```
        ┌─────────── MAC MINI (Docker Compose, 24/7) ───────────┐
        │                                                        │
  khách │   ┌──────────────┐   ┌──────────────┐  ┌───────────┐  │
  ─────►│──►│ Reverse proxy│──►│  Next.js     │  │  FastAPI  │  │
  (HTTPS│   │ Caddy (TLS)  │   │ (frontend)   │  │ (backend, │  │
  qua   │   └──────────────┘──►│  giao diện   │─►│  logic)   │  │
  tunnel)│                     └──────────────┘  └─────┬─────┘  │
        │   ┌──────────────┐   ┌──────────────┐        │        │
        │   │  Worker AI   │◄──│  RabbitMQ    │◄───────┘        │
        │   │ (queue pull) │   │  (hàng đợi)  │                 │
        │   └──────────────┘   └──────────────┘                 │
        │   ┌──────────────┐   ┌──────────────┐                 │
        │   │ Uptime Kuma  │   │   Dozzle     │  ← theo dõi+log │
        │   └──────────────┘   └──────────────┘                 │
        └───────────────────────────┬────────────────────────────┘
                                     │ (internet)
                                     ▼
                        ┌────────────────────────┐
                        │  SUPABASE (cloud)      │  ← DỮ LIỆU (giữ nguyên)
                        │  DB + auth + storage   │
                        │  + realtime            │
                        │  prod project / staging project │
                        └────────────────────────┘
```

- **Reverse proxy (Caddy):** tự lo HTTPS (Let's Encrypt), route domain → frontend/backend. (Thay việc Vercel tự lo TLS.)
- **Truy cập công khai:** dùng **Cloudflare Tunnel** (khuyến nghị: HTTPS công khai, KHÔNG mở cổng vào Mac, có chống DDoS, miễn phí) — hoặc giữ **Tailscale Funnel** đang chạy. Không port-forward trực tiếp.
- **Realtime** vẫn do Supabase lo (trình duyệt nối thẳng Supabase) → bảng trạng thái sống vẫn chạy dù frontend host ở đâu.

---

## 4. Nguyên tắc bắt buộc (phải giữ khi code)

1. **Frontend (Next.js/TSX) = chỉ giao diện:** render, gọi API, nhận input, làm mượt. **KHÔNG chứa logic nghiệp vụ** (luật đặt lịch, dedup, quy tắc khám…).
2. **Backend (FastAPI/Python) = mọi logic.** Frontend gọi API backend cho mọi việc có logic. Chỉ cho phép frontend nối thẳng Supabase ở 2 việc: (a) phiên đăng nhập, (b) subscribe realtime (bảng sống). Còn lại đi qua backend.
3. **Container hoá tất cả** + **cấu hình qua biến môi trường** (không hardcode URL/khoá). Đây là chìa khoá để sau bê sang VPS.
4. **Migration DB dạng .sql trong git** (qua Supabase CLI), KHÔNG bấm tay trong dashboard.
5. **Secret** để trong file env (đã gitignore) + GitHub Actions secrets. Không bao giờ trong code/commit.
6. Router mỏng — logic nằm ở lớp service (hàm Python thuần, tách khỏi FastAPI) để test được + tái dùng.

---

## 5. Các phase (mỗi phase có tiêu chí XONG)

### Phase 0 — An toàn trước khi động vào
- [ ] Bật + xác minh backup tự động + PITR cho Supabase **prod**; **thử restore 1 lần** trên project test.
- [ ] Bật **FileVault** trên Mac mini (mã hoá đĩa — có dữ liệu bệnh nhân).
- [ ] Xác nhận Mac tự bật lại sau reboot/mất điện (LaunchDaemon self-heal đang có → **test reboot thật**).
- [ ] (Khuyến nghị) gắn **UPS** (bộ lưu điện) cho Mac + modem.
- **XONG khi:** có bản backup restore được thật + Mac sống lại sau khi rút điện thử.

### Phase 1 — Đóng gói Docker (chạy local trên Mac)
- [ ] `Dockerfile` cho **frontend** (Next.js dùng `output: 'standalone'` để chạy `next start` không cần Vercel).
- [ ] `Dockerfile` cho **backend** (FastAPI) và **worker**.
- [ ] `docker-compose.yml`: frontend + backend + worker + RabbitMQ + **Caddy** (reverse proxy auto-HTTPS).
- [ ] Mọi cấu hình qua `.env` (Supabase URL/anon key/service key, domain, RabbitMQ…); có `.env.example`.
- **XONG khi:** `docker compose up` dựng cả stack trên Mac, mở được site qua HTTPS ở máy local.

### Phase 2 — Hai môi trường (prod + staging) trên Mac
- [ ] Tham số hoá compose cho **prod** và **staging** (2 file env, 2 compose project name, cổng khác nhau, domain khác nhau).
- [ ] prod → domain khách → Supabase **prod**; staging → domain nội bộ → Supabase **staging**.
- [ ] **Staging Supabase dùng dữ liệu giả/ẩn danh**, KHÔNG phải bản sao dữ liệu bệnh nhân thật (đúng luật + an toàn).
- **XONG khi:** hai stack chạy song song trên Mac, không đụng nhau; mỗi cái trỏ đúng Supabase của nó.

### Phase 3 — Truy cập công khai (thay Vercel)
- [ ] Dựng **Cloudflare Tunnel** (hoặc giữ Tailscale Funnel) → cả 2 domain vào được Mac qua HTTPS, **không mở cổng inbound**.
- [ ] Trỏ domain khách + domain nội bộ về đúng stack.
- **XONG khi:** từ mạng ngoài (không cần Tailscale ở máy khách), mở cả 2 domain đều lên, HTTPS hợp lệ.

### Phase 4 — Dọn tách frontend/backend
- [ ] Rà toàn bộ frontend (TSX): liệt kê chỗ nào đang chứa logic nghiệp vụ (vd luật số thứ tự, dedup, quy tắc khám).
- [ ] Chuyển các logic đó xuống **FastAPI service** (hoặc hàm SQL trong Supabase).
- [ ] Frontend đổi sang gọi API backend cho các logic đó; chỉ giữ nối thẳng Supabase cho auth + realtime.
- **XONG khi:** có danh sách logic đã chuyển; frontend không còn quy tắc nghiệp vụ nào; app vẫn chạy đúng.

### Phase 5 — CI/CD (GitHub Actions + self-hosted runner trên Mac)
- [ ] Cài **self-hosted GitHub Actions runner** trên Mac mini.
- [ ] Workflow **CI** (chạy trên **đúng nhánh prod + staging + mọi pull request** — sửa lỗi hiện tại CI đang trỏ `main`): `ruff` + `mypy` + `pytest` (backend) và `tsc` + `next build` (frontend). Đỏ thì chặn merge.
- [ ] Workflow **CD**: merge vào staging → deploy stack staging; merge vào prod → deploy stack prod (runner chạy: `git pull` → `docker compose build` → `up` → **health check** → nếu fail thì rollback về image cũ).
- [ ] Secret để trong GitHub Actions secrets.
- **XONG khi:** push → test tự chạy → merge → tự deploy đúng stack → health check xanh; thử làm test đỏ → merge bị chặn.

### Phase 6 — Dashboard theo dõi + log
- [ ] **Uptime Kuma** (self-host trong compose): theo dõi frontend/backend/worker/RabbitMQ + khả năng nối Supabase + heartbeat Mac; **cảnh báo về Telegram/Zalo** khi có cái sập.
- [ ] **Dozzle** (self-host): xem log trực tiếp mọi container qua trình duyệt, đặt sau domain nội bộ (có bảo vệ đăng nhập).
- [ ] Mỗi service có endpoint `/health` đơn giản.
- **XONG khi:** một dashboard cho thấy tất cả service sống/chết + tài nguyên Mac; log đọc được trên trình duyệt; thử `docker kill` một service → cảnh báo bắn về.

### Phase 7 — Độ tin cậy + runbook
- [ ] Đặt `restart: unless-stopped` cho mọi container (tự bật lại khi crash).
- [ ] Xác minh lại backup + PITR + đã test restore (từ Phase 0).
- [ ] Viết **runbook** ngắn: Mac chết → làm gì; deploy hỏng → cách rollback; **phương án tay/giấy tạm cho phòng khám** khi Mac không truy cập được.
- **XONG khi:** có runbook; thử crash 1 service thấy nó tự bật lại; có phương án dự phòng khi Mac offline.

---

## 6. Ngoài phạm vi (đừng làm — over-engineer)

- Kubernetes, microservices, service mesh.
- HA / nhân bản máy chủ.
- Chuyển database ra khỏi Supabase (giữ Supabase — đây là ràng buộc an toàn).
- Nhiều môi trường ngoài prod + staging.
- Bọc abstraction ở mọi ngóc ngách (chỉ bọc auth/storage/realtime của Supabase sau 1 lớp mỏng để dễ đổi sau).

---

## 7. Rủi ro & giảm thiểu (ghi để không quên)

| Rủi ro | Giảm thiểu (đã đưa vào spec) |
|---|---|
| Mac chết → phòng khám không vào app được | UPS + tự bật lại + tunnel + `restart:` policy + runbook + phương án tay tạm. **Dữ liệu an toàn vì ở Supabase** → chết ≠ mất data |
| Mạng phòng khám upload yếu → web chậm/kém ổn | Cloudflare Tunnel + theo dõi; tính 4G dự phòng sau nếu cần |
| Tự host = tự lo HTTPS/vá lỗi/bảo mật | Caddy auto-TLS + FileVault + không mở cổng (tunnel) + kỷ luật secret + lịch vá định kỳ |
| Deploy hỏng làm gián đoạn khám | CI gác + health check + rollback tự động + deploy giờ vắng |

---

## 8. Ghi chú cho Claude Code

- Làm **tuần tự theo phase**, mỗi phase 1 Task Packet, chạy hết tiêu chí XONG mới sang phase sau.
- Sau mỗi phase: cập nhật `CURRENT_PROGRESS.md` (quyết định + lý do) + `SYSTEM_STATE_ACTUAL.md` nếu đổi kiến trúc.
- **Không xoá bản Vercel cho tới khi bản Mac chạy ổn định qua Phase 3 + 5** (chạy song song, cắt Vercel sau cùng khi đã chắc).
- Giữ cổng "chỉ đưa lên domain khách khi Quang OK".
