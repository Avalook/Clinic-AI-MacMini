# Phương án Vận hành & Duy trì — ClinicAI / Dr4women

> Chuẩn startup, xây chắc từ đầu để scale. Soạn 2026-06-22.
> Nguyên tắc cốt lõi: tách **build/test/deploy** khỏi runtime · mọi thứ **as-code** ·
> **3 môi trường** rõ ràng · **không push thẳng prod**. Làm đúng từ đầu, sau scale chỉ
> tăng số chứ không đập đi xây lại.

---

## 0. Hiện trạng (cơ sở để tính)

| Hạng mục | Thực tế đang chạy |
|---|---|
| Frontend | Next.js 16 dashboard, Render **free plan** (Singapore), Docker, branch `feat/t-transform-01`, **autoDeploy mỗi push** |
| Backend API | FastAPI + RabbitMQ + LangGraph (6 sub-graph) — chạy **local Mac Mini**, chưa lên cloud |
| Database | Supabase Cloud Postgres — 26 bảng domain, dữ liệu THẬT đã load |
| AI | Anthropic Claude (cloud) + Qwen3-14B/PhoWhisper **on-premise** (audio không rời clinic) |
| Quy mô | 5.524 BN · 9.177 lịch hẹn · 14.300 đơn thuốc · 41 nhân sự / 11 vai trò · 2 cơ sở (KN+HN) |
| Đội ngũ | 1 dev (Quang) + Claude (executor) — **bus factor = 1** |

### Rủi ro đang mở (xử lý trước khi gọi là "production")
1. 🔴 Render free → ngủ sau 15ph, cold start ~50s, không SLA, không backup.
2. 🔴 Prod = branch dev + autoDeploy → push lỗi = sập màn hình lễ tân giữa giờ khám.
3. 🔴 `PATCH /api/lab-result` không check `FINALIZED` → sửa được kết quả XN sau khi visit chốt.
4. 🟠 Append-only chưa bật (migration 043) → bệnh án không có vết bất biến (rủi ro pháp lý).
5. 🟠 API + RabbitMQ + AI agents trên Mac Mini cá nhân → mất điện/mạng nhà = chết luồng AI.
6. 🟠 Backup DB chưa có chiến lược riêng + chưa test restore.
7. 🟠 Pre-commit hỏng (Poetry chết do python@3.14) → đang commit `--no-verify`.

---

## 1. Ba môi trường (bắt buộc, làm ngay)

```
local (dev máy)  →  staging (giống prod 100%)  →  production
                      ↑ test ở đây              ↑ chỉ deploy đã duyệt
```
- Mỗi env = 1 Supabase project + 1 set env vars riêng. **Không bao giờ test trên DB prod.**
- Bỏ ngay `autoDeploy` thẳng từ branch dev → prod.

---

## 2. Git & Release (GitFlow gọn)

```
main      = production (chỉ merge từ PR đã CI xanh + duyệt)
develop   = staging (auto-deploy lên staging)
feat/*    = nhánh tính năng → PR vào develop
hotfix/*  = vá khẩn → PR thẳng main + cherry-pick về develop
```
- **PR bắt buộc**: CI (lint + mypy + pytest) xanh mới merge.
- Tag version (`v0.x.0`) mỗi lần lên prod → rollback = redeploy tag cũ.
- Đổi tên branch prod hiện tại `feat/t-transform-01` → `main`.

---

## 3. CI/CD (GitHub Actions — đã có `.github/`)

```
on PR     → lint + mypy + pytest + build Docker   (gate merge)
on develop → deploy staging tự động
on tag v* → deploy prod (cần approval thủ công)
```
- Fix `pre-commit` (cài lại Poetry python3.12) — bỏ thói quen `--no-verify`.
- Không deploy trong giờ khám trừ hotfix khẩn (có rollback 1 lệnh, <2 phút).

---

## 4. Hạ tầng — chọn để scale, không chọn để rẻ tạm

| Thành phần | Bây giờ (đúng chuẩn, đủ rẻ) | Khi scale chỉ cần |
|---|---|---|
| Frontend | Render Starter / Railway (luôn bật) | tăng instance |
| API + worker | **VPS Singapore** / Railway / Fly.io (Docker) | thêm replica + load balancer |
| Queue | RabbitMQ trên cùng VPS | tách managed queue |
| DB | **Supabase Pro** (PITR backup) | lên Team / read-replica |
| AI on-prem | Mac Mini (audio/PII) + Tailscale | thêm GPU node |
| CDN/DNS/WAF | Cloudflare free | bật rate-limit/WAF |

> **Điểm dễ sai nhất:** API phải rời Mac Mini cá nhân lên VPS ngay từ đầu. Mac Mini chỉ
> giữ phần on-premise bắt buộc (PhoWhisper/Qwen vì PII audio).

### Chi phí vận hành/tháng (ước lượng, tải ~50–80 BN/ngày)

| Hạng mục | Phương án | USD/tháng | VND (~25.400đ) |
|---|---|---|---|
| Dashboard hosting | Render Starter / VPS chung | 7 | ~180k |
| API + RabbitMQ | VPS 2vCPU/4GB Singapore | 12–24 | ~300–600k |
| Database | Supabase Pro (PITR, 8GB) | 25 | ~635k |
| Anthropic Claude API¹ | agent + voice-to-EMR | 40–120 | ~1–3tr |
| Domain + TLS | .vn/.com + Cloudflare free | ~2 | ~50k |
| Backup off-site | S3/R2 dump hằng ngày | 1–3 | ~50k |
| **Cộng dồn cloud** | | **~90–180** | **~2,3–4,6tr** |
| On-prem điện + 4G dự phòng | Mac Mini đã có | — | ~300–500k |
| **TỔNG** | | | **~2,6–5,1tr/tháng** |

¹ Giảm 40–60% bằng prompt caching + dùng Haiku 4.5 cho triage nhẹ, Opus/Sonnet cho ca khó.
Cần **đo token thật 1 tuần** rồi chốt thay vì ước lượng.

---

## 5. Observability (cài 1 lần, dùng mãi)

| Lớp | Công cụ free-tier | Mục tiêu |
|---|---|---|
| Uptime | UptimeRobot ping `/health` `/login` | biết sập trước khi PK gọi |
| Error | Sentry (Next + FastAPI) | trace lỗi có context |
| Log | structlog (đã có) → JSON tập trung | truy vết |
| Cost AI | script đếm token/agent | kiểm soát chi phí Claude |
| Alert | → Telegram/Zalo bot | on-call giờ khám |

### SLA nội bộ (thực tế cho phòng khám)
- Uptime giờ khám: **99,5%** · Cold start: **0** (bỏ free tier)
- RTO ≤ **30 phút** · RPO ≤ **1 giờ** (nhờ PITR)

---

## 6. Bảo mật & Tuân thủ (y tế — không nhân nhượng)

- **Secrets**: hết hardcode → env vars + vault (1Password/Doppler). Service-role key không lộ ra client.
- **RLS bật đủ policy** (đang vá bằng service-role → trả về idiomatic).
- **Audit log + append-only** (migration 043): bệnh án bất biến, mọi sửa có vết.
- **Vá lab PATCH FINALIZED** (lỗ hổng đang mở).
- **Safety gate giữ nguyên**: GROUP_C lab, FINALIZED visit — AI gợi ý, người quyết. Không để AI tự finalize.
- PII: national_id mã hóa at-rest (đã có), audio on-prem (đã có) — giữ.

---

## 7. Backup & Phục hồi (test mới tính là có)

| Lớp | Cơ chế | Tần suất | Lưu giữ |
|---|---|---|---|
| Supabase PITR | Point-in-time recovery (Pro) | Liên tục | 7 ngày |
| Dump off-site | `pg_dump` → R2/S3 (mã hóa) | Hằng ngày 20:30 | 30 ngày |
| Snapshot tháng | Dump đầy đủ archive | Hằng tháng | 12 tháng (hồ sơ y tế) |
| Test restore | Khôi phục vào DB tạm | **Hằng quý** | — |

> Backup chưa từng test restore = chưa có backup.

---

## 8. Vận hành hàng ngày

| Thời điểm | Việc | Ai/Cái gì |
|---|---|---|
| Trước giờ khám (7:00) | Health check tự động → báo Zalo nếu fail | Cron + uptime monitor |
| Trong giờ khám | Giám sát 5xx/latency/queue; on-call phản hồi ≤15ph | Sentry/alert |
| Cuối ngày (20:30) | DB dump off-site; kiểm job CSKH nhắc gọi | Cron |
| Hằng tuần | Review event_log; rà mpi_merge_queue (trùng BN); dọn RabbitMQ DLQ | Dev |

---

## 9. Bảo trì định kỳ

| Chu kỳ | Việc |
|---|---|
| Tuần | Push commit local; review log lỗi; dọn queue |
| Tháng | Cập nhật dependency bảo mật; rà RLS; kiểm dung lượng DB |
| Quý | Nâng minor LangGraph/Anthropic SDK trên staging trước; test restore; rà quyền 11 vai trò |
| Theo nhu cầu | Migration luôn có `.down.sql`, chạy staging trước; fix runner ghi sót `schema_migrations` (thiếu 021–032) |

---

## 10. Chống bus factor (rủi ro lớn nhất)

- **Infrastructure-as-Code**: `render.yaml`/`docker-compose` (đã có) + Terraform cho Supabase/Cloudflare sau.
- Runbook 1 trang ("Dashboard sập → làm gì", "Mac Mini mất điện → lễ tân ghi tay tạm").
- Credentials vault PK truy cập được khi dev vắng.
- Backup-of-dev: ít nhất 1 người nữa biết deploy + restore.
- Duy trì kỷ luật CLAUDE.md / CURRENT_PROGRESS.md.

---

## 11. Lộ trình (2–3 tuần nền móng)

| Tuần | Việc | Kết quả |
|---|---|---|
| **1** | 3 env + đổi `main` + bỏ autoDeploy + bỏ free tier + DB dump off-site + vá lab PATCH | Hết rủi ro chết người/mất data |
| **2** | CI gate (PR + lint/mypy/pytest) + staging tự động + fix pre-commit + push 42 commit | Hết push thẳng prod |
| **3** | Sentry + uptime + alert Zalo + Supabase Pro + tách API lên VPS | Quan trắc + hết single-point-failure |
| **Tháng 2** | Append-only 043 + audit log đầy đủ + UPS/4G on-prem | Bền vững |
| **Tháng 3** | Runbook + vault + backup-of-dev + test restore quý + đo/tối ưu token | Quy trình hoàn chỉnh |

Nền này scale thẳng tới hàng nghìn BN/ngày — chỉ tăng replica + read-replica + managed queue.

---

## Tóm tắt 1 dòng cho họp PK

> Hệ thống tốt về **chức năng** nhưng đang ở **hạ tầng demo** (free tier + Mac Mini cá nhân +
> push thẳng prod). Để vận hành thật cần **~2,6–5,1tr/tháng** và **~3 tuần củng cố**; ưu tiên
> tuần đầu: **vá lỗ hổng sửa lab + backup off-site + bỏ free tier**.
