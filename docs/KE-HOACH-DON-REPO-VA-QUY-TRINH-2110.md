# Kế hoạch dọn repo + nghĩ lại quy trình code · build · deploy · lưu trữ (21/10/2026)

Mức 3 (hạ tầng + quy trình). Số đo ở mục 1 lấy lúc 21/10 sáng, trước khi dọn.

## 0. Đã làm 21/10 (Tuyền duyệt "dọn trước đã")

**Kết quả:** PR mở 98 → **34** · nhánh GitHub 536 → **74** (0 nhánh đã vào main còn
sót) · tự xoá nhánh khi merge: **bật** · worktree 106 → **34** · ổ Mac trống 111 →
**139 GB** · checkout chính về đúng bản prod (`bbd7327d`, detached). VPS / prod /
staging không bị đụng (kiểm chỉ đọc trước khi dọn).

- **G0 sao lưu:** `~/Projects/ClinicAI-Backups/code/clinicai-20261021-truoc-don.bundle`
  (48 MB, 931 ref, `git bundle verify` ok) · đồ sửa dở checkout chính → nhánh local
  `wip/checkout-chinh-1810` · tệp chưa track →
  `…/code/checkout-chinh-chua-track-20261021.tar.gz` · 4 stash → `wip/stash-0..3`.
- **G1 GitHub** (Tuyền tự chạy — hệ thống duyệt tự động của Claude chặn lệnh hàng
  loạt): đóng 62 PR đã nằm trong main, xoá 374 + 28 nhánh đã merge. Danh sách:
  `~/Projects/ClinicAI-Backups/code/don-2110/`. Bẫy: `git branch -r` lấy cả remote
  `vps`/`pr` → dòng `->` làm git từ chối cả đợt 40 nhánh (đã ghi memory).
  #410 và #486 bị đóng 09:19 bởi tài khoản Avalook, ngoài danh sách — nhánh còn,
  mở lại được.
- **G2 máy:** gỡ 68 worktree sạch (32 + 36; nhánh còn nguyên; rác nén ở
  `don-2110/rac-worktree-nhom-A.tar.gz`), xoá 35 nhánh local đã merge.

**Còn lại, chờ Tuyền:** 14 worktree nhóm B (có sửa dở thật — danh sách ở mục 6) ·
14 worktree của Codex (`backup-integrity` giữ nhánh `main`) · 4 worktree đang có
phiên chạy · 34 PR còn mở (mục 6) · G3 bí mật trên Mac (`.release-env-prod/`,
`~/.clinicai-audit.env`) + bật FileVault · G4 quy trình (mục 3) chưa duyệt.

**Đường "dễ thêm tính năng" (làm cùng ngày, theo kiểm tra
`docs/kiem-tra-su-kien-lego-2110/BAO-CAO.md`):** #513 khai chủ bảng + CI bánh cóc
chặn ghi chéo mới (bước 1) · #514 bản đồ theo khối `docs/BAN-DO-KHOI.md` (bước 2,
chồng #513) · #512 gói 1 (chuông nhận chéo + sổ nợ, chờ #511). Bước 3 tách tệp to
chờ chốt 34 PR.

## 1. Hiện trạng (đo thật)

| Chỗ | Số | Ghi chú |
|---|---|---|
| PR đang mở trên GitHub | **98** | 61 cái đầu nhánh đã nằm trong `main` · 1 cái nội dung đã có · 23 còn việc áp sạch · 13 lệch |
| Nhánh remote | **536** | 376 đã merge vào `origin/main`; GitHub **tắt** tự xoá nhánh khi merge |
| Nhánh local | 180 | 44 đã merge; cũ nhất 20/07 |
| Worktree | **106** | `.claude/worktrees` **44 GB** (mỗi cái ~0,9 GB: node_modules 650 MB + .next 87 MB + .venv 226 MB) · `.codex/worktrees` 8,6 GB · `.worktrees` 4 GB · 4 cái trỏ `/private/tmp` đã mất thư mục |
| Worktree sạch + đã merge | 42 | gỡ được ngay |
| Worktree sạch, chưa merge | 47 | cần kiểm nội dung như PR |
| Worktree có sửa dở | 14 | liệt kê, Tuyền quyết |
| Checkout chính `Dr4Women-MacMini` | nhánh **`feat/giam-gia`**, 15 tệp sửa + 29 chưa track | không phải `main`; WIP từ 13/10; `main` local tụt 59 commit |
| Stash | 4 | cũ nhất 18/08 |
| Bí mật trên Mac | `.release-env-prod/` **44 tệp `.env`** (08/2026, thời deploy từ Mac) | đã gitignore nhưng nằm trên ổ chưa mã hoá (FileVault TẮT) |
| Sao lưu DB | BÌNH THƯỜNG, bản mới 6 giờ, 8.391/8.391 tệp | 39 GB ở `~/Projects/ClinicAI-Backups` — phần này đang tốt |
| Docs | 232 tệp `.md`; `DANG-LAM.md` **2.764 dòng**, đầu tệp ghi "cập nhật 08/10" | không ai đọc hết được |
| Scripts | 72 mục, nhiều script dùng một lần có ngày trong tên | `ap-lich-tuan-2809.py`, `kiem-doi-tac-1610.sql`… |

## 2. Vì sao bừa — gốc, không phải triệu chứng

1. **Nhánh đợt là nhánh dài thứ hai trá hình.** `gop-staging-1410m` ~211 commit; PR nhắm vào
   nhánh đợt hoặc vào `main` rồi đi đường đợt → GitHub không tự đóng PR, không tự xoá nhánh,
   mỗi đợt gỡ xung đột lại từ đầu, đợt sau đè đợt trước (memory "staging đè tính năng" LẶP 2 lần).
2. **Mỗi phiên AI = một worktree đầy đủ ~0,9 GB, không ai gỡ khi xong.** 106 cái sống mãi.
3. **GitHub để mặc định:** không tự xoá nhánh, cho cả squash/merge/rebase → lịch sử khó lần.
4. **Trạng thái nằm ba nơi trùng nhau** (DANG-LAM, MEMORY.md ~150 mục, 15 tệp KE-HOACH/RUNBOOK)
   → đọc không hết → lặp lỗi đã ghi.
5. Script dùng một lần nằm chung với script vận hành → không biết cái nào còn sống.

## 3. Quy trình mới đề xuất: phát hành từ `main` (bỏ nhánh đợt)

```
nhánh việc (≤ 2 ngày) ──PR──▶ main          CI máy xanh → merge (merge commit)
                               │
                               ├──▶ staging = main@SHA, tag staging-YYYYMMDD-HHMM
                               │       DB staging nạp lại từ prod mỗi đêm 03:30 (đã có)
                               │       người thật bấm kịch bản trong PR
                               │       việc nào lỗi → PR `git revert` trên main, việc khác đi tiếp
                               │
                               └──▶ prod = ĐÚNG SHA đã đạt trên staging, tag prod-YYYYMMDD
```

- "Đợt" chỉ còn là **một tag trên `main`**, không còn nhánh `dot/*`, `gop-staging-*`.
- `deploy-backend.sh staging` đã đòi tag `staging-*`, prod đã ghim SHA → script gần như không đổi.

**Trade-off:**

| | Nhánh đợt (hiện tại) | Phát hành từ main (đề xuất) |
|---|---|---|
| Việc lỗi trên staging | bỏ khỏi đợt (dễ) | 1 PR revert trên main (thêm ~5 phút) |
| Gỡ xung đột | mỗi đợt một lần, to | mỗi PR một lần, nhỏ |
| PR/nhánh tự đóng | không | có |
| Staging đè tính năng đã lên | đã xảy ra 2 lần | không thể: staging luôn ⊇ prod |
| `main` có code chưa lên prod | có (đã vậy) | có (prod ghim SHA nên không sao) |

- Migration: revert trên main không để rác vì DB staging nạp lại từ prod mỗi đêm. Migration
  phá dữ liệu (DROP/đổi kiểu) vẫn Mức 3, tách hai bước expand → contract như luật cũ.

**Kèm theo:** bật GitHub "Automatically delete head branches"; chỉ cho merge commit vào `main`
(tắt squash/rebase để SHA PR luôn nằm trong main → PR tự đóng, test tổ tiên đúng).

## 4. Lưu trữ — mỗi thứ một nơi gốc

| Thứ | Nơi gốc | Bản sao | Đổi gì |
|---|---|---|---|
| Code | GitHub `origin` | **mới:** `git bundle --all` mỗi tuần vào `ClinicAI-Backups/code/` (~400 MB) | thêm vào launchd đang có |
| Database + tệp kết quả | VPS | Viettel CFS + Mac 90 ngày | giữ nguyên (đang tốt) |
| Bí mật | `.env.prod` trên VPS | không có | xoá `.release-env-prod/`, `.release-env-staging/`, `~/.clinicai-audit.env` trên Mac |
| Trạng thái đang làm | `docs/DANG-LAM.md` ≤ 150 dòng, chỉ việc đang mở | lịch sử ở git log | dời 2.600 dòng cũ sang `docs/legacy/` |
| Kế hoạch/runbook đã xong | `docs/da-xong/` | — | dời khỏi `docs/` gốc |
| Script một lần | git log | — | xoá khỏi `scripts/` (hoặc `scripts/mot-lan/`) |
| Ổ Mac | — | — | **Quang bật FileVault** (bản sao dữ liệu khách đang không mã hoá) |

## 5. Các bước làm (sau khi Tuyền duyệt)

| Bước | Ai | Việc | Đảo ngược được? |
|---|---|---|---|
| G0 | AI | `git bundle --all` vào `ClinicAI-Backups/code/` · lưu WIP checkout chính thành nhánh `wip/checkout-chinh-1310` (commit local) · 4 stash thành nhánh `wip/stash-*` | có |
| G1 | AI | đóng 62 PR đã vào main (kèm comment "đã vào main") · xoá ~376 nhánh remote đã merge (trừ nhánh có PR mở) · bật tự xoá nhánh + chỉ merge commit | PR mở lại được; nhánh xoá còn trong bundle G0 |
| G1b | **Tuyền** | điền cột Giữ/Đóng cho 36 PR ở mục 6 | — |
| G2 | AI | gỡ 42 worktree sạch+merged · prune 4 worktree mất thư mục · xoá 44 nhánh local đã merge · 47 worktree chưa merge: kiểm nội dung như PR, cái đã có thì gỡ · checkout chính về `main` · xoá rác gốc (`tmp-*.py`, symlink) | có, nhờ bundle G0 |
| G2b | **Tuyền** | 14 worktree sửa dở + 8,6 GB worktree Codex: giữ hay bỏ | — |
| G3 | AI + **Quang** | xoá bí mật cũ trên Mac · bật FileVault | xoá bí mật: không (cố ý) |
| G4 | AI, 1 PR | sửa CLAUDE.md bước 5–6 theo mục 3 · `scripts/don-may.sh` (chạy thử mặc định, gỡ worktree/nhánh đã merge) · rút gọn DANG-LAM · dời docs/scripts cũ | có |

Ước tính giải phóng ~38 GB ngay ở G2, thêm ~10–40 GB tuỳ quyết định G2b.

## 6. PR cần Tuyền xét

Cách kiểm: áp ngược diff của PR lên `origin/main` (áp sạch = nội dung đã có); áp xuôi sạch = còn việc thật.
### 23 PR còn việc chưa vào main, áp sạch lên main hiện tại

| PR | Ngày | Nhánh | Tên | Giữ / Đóng |
|---|---|---|---|---|
| #151 | 2026-08-21 | `huong-dan-https` | Chưa có tên miền — đó là lý do gốc của HTTP trần, không phải | |
| #170 | 2026-09-19 | `claude/chatgpt-review-handoff` | Docs: bàn giao cho external review (HANDOFF / MAP / QUESTION | |
| #242 | 2026-09-28 | `claude/lich-bs-linh` | chore(lich): điền tên bác sĩ còn thiếu cho lịch tuần 28/09 | |
| #306 | 2026-10-01 | `antigravity/e2e-luong-chinh` | e2e: Viết test Playwright cho 6 luồng chính | |
| #372 | 2026-10-08 | `claude/bai-hoc-0810` | Docs: soát trước khi code — bài học đợt mở Hào Nam | |
| #411 | 2026-10-13 | `claude/don-code-thua-1310-lib-mo-coi` | chore: gỡ lib/giao diện/script mồ côi (không ai import) | |
| #414 | 2026-10-13 | `claude/don-code-thua-1310-script` | chore(scripts): gỡ 2 script e2e trên stack Supabase CLI đã c | |
| #413 | 2026-10-13 | `claude/don-code-thua-1310` | chore: gỡ code Python không ai gọi (lớp ghi service_log đã n | |
| #432 | 2026-10-14 | `claude/huong-dan-4-man-quan-ly` | docs: hướng dẫn quản lý cho chị Hà — nhân sự, tài khoản, phò | |
| #477 | 2026-10-15 | `claude/deploy-bat-buoc-ghim-sha` | fix(deploy): prod bắt buộc ghim SHA, không còn tự git pull;  | |
| #486 | 2026-10-16 | `claude/customer-phone-sync-issue-849148` | fix(xuất hoá đơn): hoá đơn công ty ghi SĐT khách + email cá  | |
| #494 | 2026-10-16 | `claude/ke-hoach-on-dinh` | docs: kế hoạch ổn định + hợp nhất hệ thống (17/10) kèm số đo | |
| #484 | 2026-10-16 | `claude/nostalgic-solomon-ba377b` | fix: không ghép "BS " thừa trước tên bác sĩ đã có chức danh | |
| #490 | 2026-10-16 | `claude/s1-signout-local` | fix(đăng nhập): đăng xuất chỉ thu hồi phiên máy này (S1) | |
| #492 | 2026-10-16 | `claude/s2-phieu-kham-notify` | perf(realtime): phiếu khám tự lưu không phát tin cho cả phòn | |
| #491 | 2026-10-16 | `claude/s3a-patients-new-tu-tai` | perf(làm mới): /patients/new là màn tự tải (S3a) | |
| #489 | 2026-10-16 | `dot/1610-doi-tac` | Đợt đối tác 16/10: Phòng đối tác chạy chung luồng phòng + /d | |
| #498 | 2026-10-17 | `claude/ke-hoach-quy-doi-don-vi` | docs(kế hoạch): quy đổi hộp ↔ gói lúc nhập + thuốc khách trả | |
| #501 | 2026-10-17 | `claude/ke-hoach-sdt` | docs(kế hoạch): hiện SĐT cạnh tên khách + chuẩn hoá SĐT (mức | |
| #502 | 2026-10-17 | `codex/sdt-h0-ten-khach` | feat: nền TenKhach và trình bày SĐT dùng chung (H0) | |
| #505 | 2026-10-17 | `codex/sdt-h1-hien-ten-khach` | feat: show customer identity across operations screens | |
| #508 | 2026-10-19 | `codex/fix-refund-after-void` | fix: chặn hoàn tiền dịch vụ sau khi hoàn tác phiếu | |
| #511 | 2026-10-20 | `claude/on-dinh-3-bai-test-ngau-nhien` | test: cô lập 3 bài đỏ ngẫu nhiên khi ci-may chạy song song | |

### 13 PR lệch, không áp sạch nữa (phần lớn là bản cũ của thứ đã làm lại trong đợt)

| PR | Ngày | Nhánh | Tên | Giữ / Đóng |
|---|---|---|---|---|
| #144 | 2026-08-21 | `moc-gio-kham-le-tan` | Quầy lễ tân: hai nút tròn bấm được + hai mốc thời gian tách  | |
| #169 | 2026-09-18 | `claude/fix-ky-khoa-kham-xong` | Ký bệnh án không còn khoá luồng khám: vẫn Khám xong và thu t | |
| #349 | 2026-10-06 | `claude/an-luot-cu-man-theo-ngay` | Ẩn lượt hồ sơ cũ Notion ở các màn vận hành theo ngày (lịch t | |
| #393 | 2026-10-09 | `claude/bao-cao-ca-cua-toi` | feat: báo cáo ca của tôi theo lịch trực và thu quyền mở full | |
| #412 | 2026-10-13 | `claude/don-code-thua-1310-giao-dien` | chore(giao-dien): gỡ 3 component không ai render | |
| #410 | 2026-10-13 | `claude/giam-gia-bao-cao` | Báo cáo: ô Giảm giá hiện số thật (đã trừ vào doanh thu) | |
| #418 | 2026-10-14 | `claude/do-thoi-gian-api` | Vận hành: log request chậm + cảnh báo bể kết nối đầy, bể 10  | |
| #419 | 2026-10-14 | `claude/financial-reconciliation-medicine-management-1812b1` | docs: kế hoạch đợt 14/10 — dòng tiền · thuốc · vật tư · kế t | |
| #488 | 2026-10-16 | `claude/test-co-lap-1610` | test: cô lập 3 bài DB chập chờn khi CI chạy song song | |
| #493 | 2026-10-16 | `dot/1710-on-dinh` | Đợt 17/10 ổn định: đăng nhập nhiều máy + giảm dựng lại trang | |
| #497 | 2026-10-17 | `claude/kho-don-vi-dan-duong` | feat(kho): nói rõ khi lô lệch đơn vị (nhập hộp, bán gói), kh | |
| #503 | 2026-10-17 | `codex/sdt-s1-ham-chung` | feat: S1 chuẩn hoá SĐT backend và nhận số quốc tế | |
| #504 | 2026-10-17 | `codex/sdt-s2-tim-kiem` | fix: chuẩn hoá tìm kiếm SĐT ở các danh sách khách | |

### 1 PR có nội dung đã nằm trong main (đóng được): #499

### 61 PR đã nằm nguyên trong main (SHA đầu nhánh là tổ tiên của origin/main) — đóng hàng loạt

#479 #474 #473 #472 #471 #470 #469 #468 #467 #464 #463 #462 #461 #460 #459 #458 #457 #456 #455 #454 #453 #452 #451 #450 #449 #448 #447 #446 #445 #444 #443 #442 #439 #438 #437 #436 #435 #434 #433 #431 #430 #428 #427 #426 #425 #424 #422 #421 #387 #370 #364 #363 #362 #361 #360 #358 #355 #354 #353 #351 #343 

### 14 worktree có sửa dở (G2b)

- `Dr4Women-MacMini` — nhánh `feat/giam-gia`, mod=15, untracked=29, merged, 2026-10-12
- `/Users/quangdang/.codex/worktrees/inventory-controls/Dr4Women-MacMini` — nhánh `codex/kho-vat-tu-kiem-ke-bio`, mod=45, untracked=6, merged, 2026-10-19
- `Dr4Women-MacMini/.claude/worktrees/affectionate-euler-044bb1` — nhánh `claude/ci-song-song-khuon-ram`, mod=1, untracked=1, no, 2026-10-07
- `Dr4Women-MacMini/.claude/worktrees/agent-a1c7493195cc8a1ce` — nhánh `claude/notion-cham-soc-ho-so`, mod=7, untracked=6, merged, 2026-10-06
- `Dr4Women-MacMini/.claude/worktrees/agent-a360597b1ccd40c74` — nhánh `worktree-agent-a360597b1ccd40c74`, mod=1, untracked=0, merged, 2026-10-14
- `Dr4Women-MacMini/.claude/worktrees/agent-ac373b6f7ff123925` — nhánh `claude/giam-gia-may-chu`, mod=5, untracked=6, no, 2026-10-09
- `Dr4Women-MacMini/.claude/worktrees/clever-thompson-45b9eb` — nhánh `claude/clinic-system-audit-762855`, mod=1, untracked=5, no, 2026-10-20
- `Dr4Women-MacMini/.claude/worktrees/ke-hoach-quy-doi-don-vi` — nhánh `claude/agent-soat-he-thong`, mod=3, untracked=5, no, 2026-10-18
- `Dr4Women-MacMini/.claude/worktrees/skip-doctor-consultation-bug-96e8ce` — nhánh `claude/skip-doctor-consultation-bug-96e8ce`, mod=4, untracked=0, merged, 2026-10-14
- `Dr4Women-MacMini/.claude/worktrees/thu-doi-tac-489` — nhánh `claude/thu-doi-tac-489`, mod=4, untracked=0, no, 2026-10-16
- `wt-antigravity-g5c` — nhánh `antigravity/g5c-hoa-don-cong-ty`, mod=6, untracked=1, merged, 2026-10-14
- `wt-danh-muc` — nhánh `claude/danh-muc-chuan-0110`, mod=1, untracked=9, merged, 2026-10-01
- `wt-e2e` — nhánh `antigravity/e2e-luong-chinh`, mod=1, untracked=1, no, 2026-10-01
