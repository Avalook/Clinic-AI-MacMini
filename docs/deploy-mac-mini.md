# Mac mini M4 → Production backend host (Colima + Tailscale Funnel)

Backend `src/clinicai` (FastAPI + LangGraph + voice on-prem) chạy 24/7 trên Mac mini,
phơi ra internet cho dashboard (Vercel) gọi tới. **Giữ nguyên**: Supabase = DB,
Vercel = frontend khách vào xem.

**Nguyên tắc tách biệt:** server chạy từ **1 CLONE RIÊNG** (`~/clinic-server/...`),
KHÔNG dùng folder dev (nơi team test). Cùng máy nhưng khác thư mục + khác `.env` +
khác Docker project (`clinicai_prod`). Cấu hình server lỗi ⇒ KHÔNG ảnh hưởng folder dev.

> Nhánh: server clone theo `chinh` (nguồn sự thật). Deploy backend là THỦ CÔNG
> (`scripts/deploy-backend.sh`) → commit dashboard lên `chinh`/Vercel KHÔNG tự
> rebuild backend đang chạy.

---

## Kiến trúc luồng
```
Trình duyệt → Vercel (Next.js /api/*) → [Tailscale Funnel HTTPS] → Mac mini :8000 (FastAPI) → Supabase
```
- Vercel gọi FastAPI **server→server** → không CORS, `BACKEND_API_KEY` ở server.
- Ingress mặc định = **Tailscale Funnel** (không cần domain). Nâng cấp domain riêng →
  Cloudflare Tunnel (xem §H).

---

## §A. Chống Mac ngủ + tự boot lại sau mất điện (BẮT BUỘC)
System Settings → **Energy**: bật "Prevent automatic sleeping when the display is off",
KHÔNG để máy sleep. Rồi:
```bash
sudo pmset -a sleep 0 disablesleep 1
sudo pmset -a autorestart 1     # tự bật lại sau khi mất điện có lại
```

## §B. Cài Colima (Docker headless — không cần Docker Desktop / GUI)
```bash
brew install colima docker docker-compose
colima start --cpu 6 --memory 16 --disk 100    # chừa RAM cho local-LLM native sau
docker info                                     # kỳ vọng: OK
```
> Vì sao Colima (không Docker Desktop): chạy headless dưới LaunchDaemon, tự sống lại
> sau reboot mà KHÔNG cần đăng nhập GUI — đúng chất server.

## §C. Clone server RIÊNG + điền `.env`
```bash
mkdir -p ~/clinic-server && cd ~/clinic-server
git clone <repo-url> Clinic-AI-Dr4Women
cd Clinic-AI-Dr4Women && git checkout chinh
cp .env.example .env      # rồi điền (xem bảng dưới)
```
`.env` tối thiểu cho brief/patients (dùng **cùng Supabase** với folder dev):

| Biến | Ghi chú |
|---|---|
| `DATABASE_URL` | Supabase Postgres (asyncpg). **Giống hệt** folder dev. |
| `ANTHROPIC_API_KEY` | LLM (brief, lab classify, orchestrator). |
| `BACKEND_API_KEY` | Chuỗi ngẫu nhiên dài. **Phải khớp** biến cùng tên trên Vercel. |
| `CHECKPOINTER_BACKEND` | `postgres` (state LangGraph bền qua restart). |
| `DEFAULT_LOCATION_ID` | (tùy chọn) cho scheduling. |

> RabbitMQ KHÔNG cần cho brief/patients (không kết nối lúc boot).

## §D. Chạy API (compose prod, project `clinicai_prod`)
```bash
cd ~/clinic-server/Clinic-AI-Dr4Women
docker compose -f docker-compose.prod.yml up -d api
curl -f http://localhost:8000/health          # kỳ vọng: 200
```
Container tên `clinicai_prod-api-1` → KHÔNG đụng `clinicai_api` của folder dev.
**Chỉ server này được bind host :8000.**

## §E. Phơi ra internet: Tailscale Funnel (không cần domain)
```bash
brew install tailscale
sudo tailscale up
sudo tailscale set --operator=$(whoami)     # để LaunchDaemon quản funnel không cần sudo
```
Trong admin console Tailscale: bật **MagicDNS** + **HTTPS certificates** + **Funnel** cho máy này.
```bash
tailscale funnel --bg 8000
tailscale funnel status                      # in URL công khai cố định: https://<máy>.<tailnet>.ts.net
```

## §F. Nối dashboard (Vercel)
Vercel project → Environment (Production = `chinh`):

| Biến | Giá trị |
|---|---|
| `CLINIC_API_URL` | `https://<máy>.<tailnet>.ts.net` — **KHÔNG** `/api/v1`, **KHÔNG** `/` cuối. |
| `BACKEND_API_KEY` | Khớp **y hệt** `.env` trên Mac. |

Set xong → **Redeploy** dashboard. Route tự ghép `${CLINIC_API_URL}/api/v1/...`.

## §G. Tự khởi động khi boot (LaunchDaemon headless)
`scripts/clinic-backend-boot.sh` (idempotent): colima start → `docker compose prod up -d api`
→ assert funnel. LaunchDaemon chạy nó lúc boot + mỗi 5 phút.
```bash
cd ~/clinic-server/Clinic-AI-Dr4Women
chmod +x scripts/clinic-backend-boot.sh scripts/deploy-backend.sh

REPO="$(pwd)"
sudo sed -e "s|__REPO__|$REPO|g" -e "s|__HOME__|$HOME|g" -e "s|__USER__|$(whoami)|g" \
  docker/com.dr4women.clinic-backend.plist \
  | sudo tee /Library/LaunchDaemons/com.dr4women.clinic-backend.plist >/dev/null

sudo launchctl bootout system/com.dr4women.clinic-backend 2>/dev/null || true
sudo launchctl bootstrap system /Library/LaunchDaemons/com.dr4women.clinic-backend.plist
sudo launchctl enable system/com.dr4women.clinic-backend
```
Kiểm tra / gỡ:
```bash
sudo launchctl print system/com.dr4women.clinic-backend | head
tail -f "$HOME/Library/Logs/clinic-backend-boot.log"
# Gỡ: sudo launchctl bootout system/com.dr4women.clinic-backend && sudo rm /Library/LaunchDaemons/com.dr4women.clinic-backend.plist
```

## §H. (Tùy chọn) Nâng cấp domain riêng → Cloudflare Tunnel
Chỉ khi muốn URL thương hiệu `api.<domain>` + WAF + băng thông thoải mái.
`*.vercel.app` KHÔNG dùng được; `*.trycloudflare.com` đổi mỗi restart (không dùng prod).
1. Mua/đưa domain vào Cloudflare. Zero Trust → Networks → **Tunnels** → tạo tunnel →
   Public hostname `api.<domain>` → service `http://api:8000`. Copy **tunnel token**.
2. `.env`: `TUNNEL_TOKEN=<token>`. Chạy: `docker compose -f docker-compose.prod.yml --profile cloudflare up -d`.
3. Vercel: đổi `CLINIC_API_URL=https://api.<domain>` → redeploy. Tắt `tailscale funnel` (giữ Tailscale cho admin/SSH).

## §I. Deploy code mới (thủ công, có kiểm soát)
```bash
cd ~/clinic-server/Clinic-AI-Dr4Women
./scripts/deploy-backend.sh        # pull → build → migrate → NOTIFY pgrst → up → healthcheck
```

## §J. Bảo mật (làm 1 lần)
- **FileVault** bật (mã hóa đĩa — bắt buộc với PII y tế): System Settings → Privacy & Security.
- macOS firewall bật. **KHÔNG** mở cổng router (Funnel/Tunnel là outbound).
- Mọi route FastAPI bị `BACKEND_API_KEY` chặn (rotate định kỳ). KHÔNG đặt service-role key
  lên FastAPI trừ khi thật cần. RabbitMQ không map cổng ra host.

## §K. Giám sát + cảnh báo
- **External uptime** (báo được cả khi Mac chết): UptimeRobot/healthchecks.io ping
  `https://<máy>.<tailnet>.ts.net/health` → cảnh báo email/Zalo.
- (Tùy chọn) Dozzle xem log docker qua web nội bộ (chỉ trong Tailscale).

## §L. Verify end-to-end
1. `curl -f http://localhost:8000/health` = 200 (trên Mac).
2. `curl -f https://<máy>.<tailnet>.ts.net/health` = 200 (từ ngoài).
3. Dashboard: vai **bác sĩ** → mở BN của mình → "Tóm tắt trước khám" → ra markdown thật (không 502).
4. Resilience: `sudo reboot` → sau khi boot (KHÔNG login tay) → bước 2 lại 200 (LaunchDaemon + Colima tự lên).

---

## Rủi ro đã biết & escape hatch
- **Mất điện/mạng nhà → API chết.** Dashboard vẫn đọc Supabase; chỉ brief/patients-qua-FastAPI
  lỗi tạm (patient create có fallback ghi thẳng Supabase). UPS + external alert giảm rủi ro.
- **Cutover VPS (backend stateless):** chạy `docker-compose.prod.yml` trên 1 VPS + đổi
  `CLINIC_API_URL` trên Vercel → chuyển trong vài phút. LƯU Ý: **voice/local-LLM on-prem
  KHÔNG chuyển sang VPS rẻ** (cần máy có GPU / dữ liệu phải on-prem theo NĐ13/2023).
- **Docker macOS không có Metal GPU** → local LLM (Qwen/MLX) sau này chạy NATIVE trên macOS,
  FastAPI-trong-Docker gọi qua `host.docker.internal:<port>`.
